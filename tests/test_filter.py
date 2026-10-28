# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
"""c410scms-filter against an independent Python model, using a synthetic data file (no Samsung data)."""
import os
import random
import struct
import subprocess
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILTER = os.path.join(ROOT, "c410scms-filter")
GRID = 17


def node(table, r, g, b):
    return table[(r * GRID + g) * GRID + b]


def interpolate(table, rgb):
    if rgb == (255, 255, 255):
        return [255] * 4
    i = [c >> 4 for c in rgb]
    f = [c & 15 for c in rgb]
    order = sorted(range(3), key=lambda a: -f[a])
    verts, cur = [list(i)], list(i)
    for axis in order:
        cur[axis] += 1
        verts.append(list(cur))
    c = [node(table, *v) for v in verts]
    fr = [f[a] for a in order]
    out = []
    for ch in range(4):
        s = sum((c[n + 1][ch] - c[n][ch]) * fr[n] for n in range(3))
        v = c[0][ch] + ((s + 15) >> 4)
        out.append(255 if v > 254 else max(v, 0))
    return out


def ink_level(v, t):
    code = 3 if v >= t[0] else 2 if v >= t[1] else 1 if v >= t[2] else 0
    return 3 - code


def synthetic_data(rng):
    table = [[rng.randrange(256) for _ in range(4)] for _ in range(GRID ** 3)]
    screens = []
    for w, h in ((7, 5), (11, 3), (4, 9), (13, 13)):
        cells = []
        for _ in range(w * h):
            t = sorted((rng.randrange(256) for _ in range(3)), reverse=True)
            cells.append(t)
        screens.append((w, h, cells))
    blob = b"C410SCMS" + struct.pack("<I", 1) + bytes(v for n in table for v in n)
    for w, h, cells in screens:
        blob += struct.pack("<HH", w, h) + bytes(v for c in cells for v in c)
    return table, screens, blob


def darkness(k):
    return 20 * k[0] + 20 * k[1] + 5 * k[2] + 33 * k[3]


def trap(ink, w, h):
    """Reference for -t, from the rules in docs/trapping.md. ink: list of [C, M, Y, K] per pixel."""
    def at(y, x):
        return ink[y * w + x] if 0 <= y < h and 0 <= x < w else [0, 0, 0, 0]

    def straight(y, x, uy, ux):
        return at(y + ux, x + uy) == at(y, x) or at(y - ux, x - uy) == at(y, x)

    out = []
    for y in range(h):
        for x in range(w):
            p = at(y, x)
            wide = p[3] >= 108
            best = [0, 0, 0]
            for uy, ux in ((0, 1), (0, -1), (1, 0), (-1, 0)):
                if not straight(y, x, uy, ux) or at(y - uy, x - ux) != p:
                    continue
                for dist in (1, 2):
                    qy, qx = y + dist * uy, x + dist * ux
                    q = at(qy, qx)
                    e = darkness(q) - darkness(p)
                    if q == [0, 0, 0, 0] or at(qy + uy, qx + ux) != q or not straight(qy, qx, uy, ux):
                        continue
                    cut = 0
                    if dist == 1:
                        if e >= 0 or (wide and e >= -440):
                            continue
                    else:
                        if not wide or at(y + uy, x + ux) != p or at(y - 2 * uy, x - 2 * ux) != p:
                            continue
                        if e >= -440:
                            cut = max(0, (480 + e) // 40) if 480 + e > 0 else 0
                    for c in range(3):
                        v = q[c] - cut
                        if v - p[c] >= 24:
                            best[c] = max(best[c], v)
            out.append([max(p[c], best[c]) for c in range(3)] + [p[3]])
    return out


EDGE_STEPS = {0: ((58, 119, 195), (79, 146, 213)), 1: ((59, 130, 201), (77, 143, 205)),
              3: ((68, 138, 209), (68, 138, 209))}


def edge_mask(ink, w, h, y, x, p, trapping):
    """Reference for -e: the half-dot mask ORed into plane p's level, from the rules in docs/trapping.md."""
    def at(yy, xx):
        return ink[yy * w + xx] if 0 <= yy < h and 0 <= xx < w else [0, 0, 0, 0]

    if p not in EDGE_STEPS:
        return 0
    k = at(y, x)
    m = 0
    for uy, ux in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        q = at(y + uy, x + ux)
        step = k[p] - q[p]
        if step <= 0 or (trapping and q != [0, 0, 0, 0] and darkness(q) >= darkness(k)):
            continue
        if abs(at(y + ux, x + uy)[p] - k[p]) > 8 and abs(at(y - ux, x - uy)[p] - k[p]) > 8:
            continue
        m = max(m, sum(step >= t for t in EDGE_STEPS[p][uy != 0]))
    return m


def expected_page(table, screens, pixels, w, h, trapped=False, edges=False):
    plain = [[255 - v for v in interpolate(table, px)] for px in pixels]
    ink = trap(plain, w, h) if trapped else plain
    out = bytearray()
    for y in range(h):
        for x in range(w):
            v = [255 - i for i in ink[y * w + x]]
            byte = 0
            for p, (sw, sh, cells) in enumerate(screens):
                level = ink_level(v[p], cells[(y % sh) * sw + x % sw])
                if edges:
                    level |= edge_mask(plain, w, h, y, x, p, trapped)
                byte |= (level >> 1) << (7 - p)
                byte |= (level & 1) << (3 - p)
            out.append(byte)
    if out and out[0] == ord("P"):
        out[0] = 0
    return bytes(out)


class FilterTest(unittest.TestCase):
    def run_filter(self, blob, ppm, *opts):
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
            f.write(blob)
        try:
            return subprocess.run([FILTER, *opts, f.name], input=ppm, capture_output=True, check=True).stdout
        finally:
            os.unlink(f.name)

    def test_matches_python_model_on_random_pages(self):
        rng = random.Random(410)
        table, screens, blob = synthetic_data(rng)
        ppm, expected = b"", b""
        for w, h in ((37, 23), (16, 1)):
            pixels = [tuple(rng.randrange(256) for _ in range(3)) for _ in range(w * h)]
            pixels[0] = (255, 255, 255)
            pixels[1] = (255, 255, 254)
            ppm += b"P6\n# comment\n%d %d\n255\n" % (w, h) + bytes(c for p in pixels for c in p)
            expected += expected_page(table, screens, pixels, w, h)
        self.assertEqual(self.run_filter(blob, ppm), expected)

    def block_pages(self, seed, **options):
        rng = random.Random(seed)
        table, screens, blob = synthetic_data(rng)
        ppm, expected = b"", b""
        for w, h in ((41, 29), (13, 3)):
            colours = [tuple(rng.randrange(256) for _ in range(3)) for _ in range(5)] + [(255, 255, 255)]
            pixels = [colours[0]] * (w * h)
            for _ in range(12):
                c = rng.choice(colours)
                y0, x0 = rng.randrange(h), rng.randrange(w)
                for y in range(y0, min(h, y0 + rng.randrange(1, 9))):
                    for x in range(x0, min(w, x0 + rng.randrange(1, 9))):
                        pixels[y * w + x] = c
            ppm += b"P6\n%d %d\n255\n" % (w, h) + bytes(c for p in pixels for c in p)
            expected += expected_page(table, screens, pixels, w, h, **options)
        return blob, ppm, expected

    def test_trapping_matches_python_model_on_block_pages(self):
        blob, ppm, expected = self.block_pages(36, trapped=True)
        self.assertEqual(self.run_filter(blob, ppm, "-t"), expected)

    def test_edge_enhancement_matches_python_model_on_block_pages(self):
        blob, ppm, expected = self.block_pages(37, edges=True)
        self.assertNotEqual(expected, self.block_pages(37)[2])
        self.assertEqual(self.run_filter(blob, ppm, "-e"), expected)
        blob, ppm, expected = self.block_pages(38, trapped=True, edges=True)
        self.assertEqual(self.run_filter(blob, ppm, "-t", "-e"), expected)

    def test_edge_mask_grows_with_the_ink_step_and_skips_yellow(self):
        for ink, mask in ((50, 0), (60, 1), (120, 2), (200, 3)):
            page = [[ink, 0, ink, ink]] * 3 + [[0, 0, 0, 0]] * 3
            self.assertEqual([edge_mask(page * 3, 6, 3, 1, 2, p, False) for p in range(4)],
                             [mask, 0, 0, sum(ink >= t for t in (68, 138, 209))])

    def test_edge_enhancement_with_trapping_only_on_the_darker_side(self):
        light, dark = [130, 0, 0, 0], [0, 210, 0, 0]
        page = ([light] * 3 + [dark] * 3) * 3
        self.assertEqual(edge_mask(page, 6, 3, 1, 2, 0, False), 2)
        self.assertEqual(edge_mask(page, 6, 3, 1, 2, 0, True), 0)
        self.assertEqual(edge_mask(page, 6, 3, 1, 3, 1, True), 3)

    def test_trapping_spreads_the_lighter_colour_under_the_darker(self):
        light, dark = [0, 0, 180, 0], [200, 0, 0, 0]
        ink = [light] * 3 + [dark] * 3
        self.assertEqual(trap(ink * 3, 6, 3)[3], [200, 0, 180, 0])
        self.assertEqual(trap(ink * 3, 6, 3)[2], light)

    def test_trapping_is_two_pixels_wide_under_black(self):
        light, black = [0, 150, 0, 0], [0, 0, 0, 250]
        row = trap(([light] * 3 + [black] * 5) * 3, 8, 3)[8:16]
        self.assertEqual([px[1] for px in row], [150, 150, 150, 150, 150, 0, 0, 0])

    def test_trapping_leaves_white_and_thin_black_lines_alone(self):
        white, black, colour = [0, 0, 0, 0], [0, 0, 0, 250], [0, 150, 0, 0]
        ink = [white] * 3 + [black] * 3
        self.assertEqual(trap(ink * 3, 6, 3), ink * 3)
        line = [colour] * 3 + [black] + [colour] * 3
        self.assertEqual(trap(line * 3, 7, 3), line * 3)

    def test_exact_white_prints_nothing(self):
        rng = random.Random(1)
        table, _, blob = synthetic_data(rng)
        table_white = [255, 255, 255, 255]
        self.assertNotEqual(node(table, 16, 16, 16), table_white)
        out = self.run_filter(blob, b"P6\n4 2\n255\n" + b"\xff" * 24)
        self.assertEqual(out, b"\0" * 8)

    def test_blank_from_row_on_every_page(self):
        rng = random.Random(2)
        _, _, blob = synthetic_data(rng)
        page = b"P6\n6 4\n255\n" + bytes(rng.randrange(255) for _ in range(6 * 4 * 3))
        full = self.run_filter(blob, page + page)
        out = self.run_filter(blob, page + page, "-b", "3")
        expected = (full[:18] + b"\0" * 6) * 2
        self.assertNotEqual(full[18:24], b"\0" * 6)
        self.assertEqual(out, expected)

    def test_rejects_bad_data_file(self):
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
            f.write(b"NOTSCMS!")
        try:
            r = subprocess.run([FILTER, f.name], input=b"", capture_output=True)
        finally:
            os.unlink(f.name)
        self.assertNotEqual(r.returncode, 0)


if __name__ == "__main__":
    unittest.main()
