/*
 * Copyright (C) 2026 Pelle van der Heide
 * SPDX-License-Identifier: GPL-2.0-or-later
 *
 * c410scms-filter: Samsung SCMS colour conversion and 2-bit screening for the Xpress C410,
 * reimplemented from observing the Samsung ULD driver and verified bit-exact against its output.
 *
 * stdin:  Ghostscript ppmraw pages (RGB, 8 bit, 600x600 dpi)
 * stdout: Ghostscript bitcmyk pages at 1200x600 dpi for foo2qpdl -z3, where each pair of
 *         horizontal 1200 dpi bits carries one 2-bit 600 dpi level (MSB first).
 *
 * Data file (little endian): "C410SCMS" u32 version, 17^3*4 table bytes (255 - ink, CMYK),
 * then for C, M, Y, K: u16 width, u16 height, width*height*3 threshold bytes.
 *
 * Trapping (-t) approximates Samsung's host-side trapping from measurements of its output, not
 * bit-exact: along straight edges between flat areas, the lighter side's C/M/Y spread under the
 * darker side, 1 pixel, or 2 under areas with much black.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GRID 17
#define TRAP_GAP 24		/* ink difference below which a colour is not spread */
#define TRAP_WIDE_K 108		/* black ink from which traps are 2 pixels wide */
#define TRAP_CLOSE (22 * 20)	/* darkness margin (x20) below which a wide trap only reaches its 2nd pixel */
#define WIN 3			/* rows a trap looks above and below a pixel */
#define RING (2 * WIN + 1)

static uint8_t table[GRID * GRID * GRID * 4];

static struct {
	int w, h;
	uint8_t *thr;
} screen[4];

static void die(const char *msg)
{
	fprintf(stderr, "c410scms-filter: %s\n", msg);
	exit(1);
}

static void load_data(const char *path)
{
	FILE *f = fopen(path, "rb");
	char magic[8];
	uint32_t version;

	if (!f)
		die("cannot open data file");
	if (fread(magic, 1, 8, f) != 8 || memcmp(magic, "C410SCMS", 8) || fread(&version, 4, 1, f) != 1 || version != 1)
		die("bad data file header");
	if (fread(table, 1, sizeof(table), f) != sizeof(table))
		die("short table");
	for (int p = 0; p < 4; p++) {
		uint16_t wh[2];
		size_t n;

		if (fread(wh, 2, 2, f) != 2)
			die("short screen header");
		screen[p].w = wh[0];
		screen[p].h = wh[1];
		n = (size_t)wh[0] * wh[1] * 3;
		screen[p].thr = malloc(n);
		if (!screen[p].thr || fread(screen[p].thr, 1, n, f) != n)
			die("short screen data");
	}
	fclose(f);
}

static inline const uint8_t *node(int r, int g, int b)
{
	return &table[((r * GRID + g) * GRID + b) * 4];
}

/* Samsung rounds the interpolated delta up: c0 + ((sum + 15) >> 4), clamped to 0..255. */
static void interpolate(const uint8_t *rgb, uint8_t *out)
{
	int r = rgb[0] >> 4, g = rgb[1] >> 4, b = rgb[2] >> 4;
	int fr = rgb[0] & 15, fg = rgb[1] & 15, fb = rgb[2] & 15;
	const uint8_t *c0 = node(r, g, b), *c1, *c2, *c3 = node(r + 1, g + 1, b + 1);
	int f1, f2, f3;

	/* Samsung leaves exact white untouched; the table would otherwise give a faint cyan. */
	if (rgb[0] == 255 && rgb[1] == 255 && rgb[2] == 255) {
		memset(out, 255, 4);
		return;
	}
	if (fr >= fg && fg >= fb) {
		c1 = node(r + 1, g, b); c2 = node(r + 1, g + 1, b); f1 = fr; f2 = fg; f3 = fb;
	} else if (fr >= fb && fb >= fg) {
		c1 = node(r + 1, g, b); c2 = node(r + 1, g, b + 1); f1 = fr; f2 = fb; f3 = fg;
	} else if (fb >= fr && fr >= fg) {
		c1 = node(r, g, b + 1); c2 = node(r + 1, g, b + 1); f1 = fb; f2 = fr; f3 = fg;
	} else if (fg >= fr && fr >= fb) {
		c1 = node(r, g + 1, b); c2 = node(r + 1, g + 1, b); f1 = fg; f2 = fr; f3 = fb;
	} else if (fg >= fb && fb >= fr) {
		c1 = node(r, g + 1, b); c2 = node(r, g + 1, b + 1); f1 = fg; f2 = fb; f3 = fr;
	} else {
		c1 = node(r, g, b + 1); c2 = node(r, g + 1, b + 1); f1 = fb; f2 = fg; f3 = fr;
	}
	for (int ch = 0; ch < 4; ch++) {
		int sum = (c1[ch] - c0[ch]) * f1 + (c2[ch] - c1[ch]) * f2 + (c3[ch] - c2[ch]) * f3;
		int v = c0[ch] + ((sum + 15) >> 4);

		out[ch] = v > 254 ? 255 : v < 0 ? 0 : v;
	}
}

static int read_int(FILE *f)
{
	int c, v = 0;

	do {
		c = getc(f);
		if (c == '#')
			while (c != '\n' && c != EOF)
				c = getc(f);
	} while (c == ' ' || c == '\t' || c == '\n' || c == '\r');
	if (c < '0' || c > '9')
		die("bad ppm header");
	while (c >= '0' && c <= '9') {
		v = v * 10 + c - '0';
		c = getc(f);
	}
	return v;
}

static int page_w, page_h;
static uint8_t *ring[RING];	/* ink (not 255 - ink) of rows y - WIN .. y + WIN, at y % RING */
static const uint8_t white_px[4];

static const uint8_t *px(int y, int x)
{
	if (y < 0 || y >= page_h || x < 0 || x >= page_w)
		return white_px;
	return ring[y % RING] + (size_t)x * 4;
}

static int same(const uint8_t *a, const uint8_t *b)
{
	return !memcmp(a, b, 4);
}

/* 20 x (C + M + Y/4 + 1.65 K): decides which side of an edge is the darker one */
static int darkness(const uint8_t *k)
{
	return 20 * k[0] + 20 * k[1] + 5 * k[2] + 33 * k[3];
}

/* the edge runs straight past (y, x): a sideways neighbour has the same colour */
static int straight(int y, int x, int uy, int ux)
{
	const uint8_t *p = px(y, x);

	return same(px(y + ux, x + uy), p) || same(px(y - ux, x - uy), p);
}

static void trap_pixel(int y, int x, uint8_t *out)
{
	static const int dirs[4][2] = { { 0, 1 }, { 0, -1 }, { 1, 0 }, { -1, 0 } };
	const uint8_t *p = px(y, x);
	int dp = darkness(p), wide = p[3] >= TRAP_WIDE_K;
	int best[3] = { 0, 0, 0 };

	memcpy(out, p, 4);
	/* inside a flat area there is nothing to spread */
	if (same(px(y, x - 1), p) && same(px(y, x + 1), p) && same(px(y - 1, x), p) && same(px(y + 1, x), p) &&
	    (!wide || (same(px(y, x - 2), p) && same(px(y, x + 2), p) && same(px(y - 2, x), p) && same(px(y + 2, x), p))))
		return;
	for (int d = 0; d < 4; d++) {
		int uy = dirs[d][0], ux = dirs[d][1];

		if (!straight(y, x, uy, ux) || !same(px(y - uy, x - ux), p))
			continue;
		for (int dist = 1; dist <= 2; dist++) {
			int qy = y + dist * uy, qx = x + dist * ux;
			const uint8_t *q = px(qy, qx);
			int e = darkness(q) - dp, cut = 0;

			if (same(q, white_px) || !same(px(qy + uy, qx + ux), q) || !straight(qy, qx, uy, ux))
				continue;
			if (dist == 1) {
				if (e >= 0 || (wide && e >= -TRAP_CLOSE))
					continue;
			} else {
				if (!wide || !same(px(y + uy, x + ux), p) || !same(px(y - 2 * uy, x - 2 * ux), p))
					continue;
				/* next to a colour about as dark as itself, black only takes a reduced trap */
				if (e >= -TRAP_CLOSE)
					cut = 480 + e > 0 ? (480 + e) / 40 : 0;
			}
			for (int c = 0; c < 3; c++) {
				int v = q[c] - cut;

				if (v - p[c] >= TRAP_GAP && v > best[c])
					best[c] = v;
			}
		}
	}
	for (int c = 0; c < 3; c++)
		if (best[c] > out[c])
			out[c] = best[c];
}

int main(int argc, char **argv)
{
	/* -b ROWS: print nothing from that row of each page on (foo2qpdl band padding, see the wrapper) */
	long blank_from = -1;
	int trap = 0;

	while (argc > 2 && argv[1][0] == '-') {
		if (!strcmp(argv[1], "-t")) {
			trap = 1;
			argv++;
			argc--;
		} else if (!strcmp(argv[1], "-b") && argc > 3) {
			blank_from = atol(argv[2]);
			argv += 2;
			argc -= 2;
		} else {
			break;
		}
	}
	if (argc != 2)
		die("usage: c410scms-filter [-t] [-b rows] <data-file> <ppm-pages >bitcmyk-pages");
	load_data(argv[1]);

	int first_byte = 1, delay = trap ? WIN : 0;

	for (;;) {
		int c1 = getc(stdin), c2 = getc(stdin);

		if (c1 == EOF)
			break;
		if (c1 != 'P' || c2 != '6')
			die("input is not ppmraw");
		int w = read_int(stdin), h = read_int(stdin);

		if (read_int(stdin) != 255)
			die("only 8-bit ppm supported");
		uint8_t *in = malloc((size_t)w * 3), *out = malloc(w);

		if (!in || !out)
			die("out of memory");
		for (int i = 0; i < RING; i++)
			if (!(ring[i] = malloc((size_t)w * 4)))
				die("out of memory");
		page_w = w;
		page_h = h;
		for (int y = 0; y < h + delay; y++) {
			if (y < h) {
				uint8_t *ink = ring[y % RING];

				if (fread(in, 3, w, stdin) != (size_t)w)
					die("short ppm data");
				for (int x = 0; x < w; x++) {
					interpolate(in + x * 3, ink + x * 4);
					for (int p = 0; p < 4; p++)
						ink[x * 4 + p] = 255 - ink[x * 4 + p];
				}
			}

			int oy = y - delay;
			const uint8_t *row[4];

			if (oy < 0)
				continue;
			for (int p = 0; p < 4; p++)
				row[p] = screen[p].thr + (size_t)(oy % screen[p].h) * screen[p].w * 3;
			for (int x = 0; x < w; x++) {
				uint8_t k[4];
				int byte = 0;

				if (trap)
					trap_pixel(oy, x, k);
				else
					memcpy(k, px(oy, x), 4);
				for (int p = 0; p < 4; p++) {
					const uint8_t *t = row[p] + (x % screen[p].w) * 3;
					int v = 255 - k[p];
					int code = v >= t[0] ? 3 : v >= t[1] ? 2 : v >= t[2] ? 1 : 0;
					int level = 3 - code;

					byte |= (level >> 1) << (7 - p);
					byte |= (level & 1) << (3 - p);
				}
				out[x] = byte;
			}
			if (blank_from >= 0 && oy >= blank_from)
				memset(out, 0, w);
			/* foo2qpdl takes a stream starting with 'P' for pksmraw; this pixel is in the clipped margin. */
			if (first_byte && out[0] == 'P')
				out[0] = 0;
			first_byte = 0;
			fwrite(out, 1, w, stdout);
		}
		for (int i = 0; i < RING; i++)
			free(ring[i]);
		free(in);
		free(out);
	}
	return 0;
}
