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
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define GRID 17

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

int main(int argc, char **argv)
{
	/* -b ROWS: print nothing from that row of each page on (foo2qpdl band padding, see the wrapper) */
	long blank_from = -1;

	if (argc == 4 && !strcmp(argv[1], "-b")) {
		blank_from = atol(argv[2]);
		argv += 2;
		argc -= 2;
	}
	if (argc != 2)
		die("usage: c410scms-filter [-b rows] <data-file> <ppm-pages >bitcmyk-pages");
	load_data(argv[1]);

	int first_byte = 1;

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
		for (int y = 0; y < h; y++) {
			const uint8_t *row[4];

			if (fread(in, 3, w, stdin) != (size_t)w)
				die("short ppm data");
			for (int p = 0; p < 4; p++)
				row[p] = screen[p].thr + (size_t)(y % screen[p].h) * screen[p].w * 3;
			for (int x = 0; x < w; x++) {
				uint8_t v[4];
				int byte = 0;

				interpolate(in + x * 3, v);
				for (int p = 0; p < 4; p++) {
					const uint8_t *t = row[p] + (x % screen[p].w) * 3;
					int code = v[p] >= t[0] ? 3 : v[p] >= t[1] ? 2 : v[p] >= t[2] ? 1 : 0;
					int ink = 3 - code;

					byte |= (ink >> 1) << (7 - p);
					byte |= (ink & 1) << (3 - p);
				}
				out[x] = byte;
			}
			if (blank_from >= 0 && y >= blank_from)
				memset(out, 0, w);
			/* foo2qpdl takes a stream starting with 'P' for pksmraw; this pixel is in the clipped margin. */
			if (first_byte && out[0] == 'P')
				out[0] = 0;
			first_byte = 0;
			fwrite(out, 1, w, stdout);
		}
		free(in);
		free(out);
	}
	return 0;
}
