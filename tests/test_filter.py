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


def expected_page(table, screens, pixels, w, h):
    out = bytearray()
    for y in range(h):
        for x in range(w):
            v = interpolate(table, pixels[y * w + x])
            byte = 0
            for p, (sw, sh, cells) in enumerate(screens):
                ink = ink_level(v[p], cells[(y % sh) * sw + x % sw])
                byte |= (ink >> 1) << (7 - p)
                byte |= (ink & 1) << (3 - p)
            out.append(byte)
    if out and out[0] == ord("P"):
        out[0] = 0
    return bytes(out)


class FilterTest(unittest.TestCase):
    def run_filter(self, blob, ppm):
        with tempfile.NamedTemporaryFile(suffix=".dat", delete=False) as f:
            f.write(blob)
        try:
            return subprocess.run([FILTER, f.name], input=ppm, capture_output=True, check=True).stdout
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

    def test_exact_white_prints_nothing(self):
        rng = random.Random(1)
        table, _, blob = synthetic_data(rng)
        table_white = [255, 255, 255, 255]
        self.assertNotEqual(node(table, 16, 16, 16), table_white)
        out = self.run_filter(blob, b"P6\n4 2\n255\n" + b"\xff" * 24)
        self.assertEqual(out, b"\0" * 8)

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
