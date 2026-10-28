# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
"""Generator logic on synthetic input; with C410_CTS set, also a full run on Samsung's file."""
import importlib.machinery
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEN = os.path.join(ROOT, "tools", "c410scms-gen")
_loader = importlib.machinery.SourceFileLoader("c410scms_gen", GEN)
_spec = importlib.util.spec_from_loader("c410scms_gen", _loader)
gen = importlib.util.module_from_spec(_spec)
_loader.exec_module(gen)


def block(u32=(), u16=(), u8=b""):
    hdr = struct.pack("<7I", 0, len(u32), 0, len(u16), 0, len(u8), 0)
    return hdr + struct.pack(f"<{len(u32)}I", *u32) + struct.pack(f"<{len(u16)}H", *u16) + bytes(u8)


def cts_file(entries):
    """entries: list of (type, 12-byte signature, block bytes)."""
    toc_start = 0x70
    data_start = toc_start + 0x20 * len(entries)
    toc, blobs = b"", b""
    for typ, sig, blob in entries:
        toc += struct.pack("<I", typ) + sig.ljust(20, b"\0") + struct.pack("<II", data_start + len(blobs), len(blob))
        blobs += blob
    head = bytearray(0x6C)
    return bytes(head) + struct.pack("<HH", len(entries), 0x20) + toc + blobs


class LookupTest(unittest.TestCase):
    def test_zero_signature_bytes_are_wildcards_and_first_match_wins(self):
        specific = bytes([7, 0x15, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        cts = gen.Cts(cts_file([(5, specific, block(u32=(1,))), (5, b"\0" * 12, block(u32=(2,)))]))
        self.assertEqual(cts.lookup(5, gen.signature(colour=7))[0], [1])
        self.assertEqual(cts.lookup(5, gen.signature(colour=1))[0], [2])
        with self.assertRaises(LookupError):
            cts.lookup(6, gen.signature())

    def test_block_groups_are_read_in_order(self):
        cts = gen.Cts(cts_file([(9, b"\0" * 12, block(u32=(3, 4), u16=(5, 6, 7), u8=b"\x08\x09"))]))
        self.assertEqual(cts.lookup(9, gen.signature()), ([3, 4], [5, 6, 7], b"\x08\x09"))


class BlackOptimisationTest(unittest.TestCase):
    params = (34, 8, 3, 4, 7, 1)
    identity = list(range(256))

    def table_with(self, c, m, y, k):
        return [[c, m, y, k] for _ in range(gen.GRID ** 3)]

    def test_neutral_nodes_lose_cmy(self):
        out = gen.black_optimise(self.table_with(100, 110, 120, 255), self.params, self.identity)
        grey = out[(8 * gen.GRID + 8) * gen.GRID + 8]
        self.assertEqual(grey[:3], [255, 255, 255])
        self.assertEqual(grey[3], 110)

    def test_saturated_nodes_unchanged_and_full_channel_gets_no_k(self):
        out = gen.black_optimise(self.table_with(100, 110, 120, 200), self.params, self.identity)
        red = out[(16 * gen.GRID + 0) * gen.GRID + 0]
        self.assertEqual(red, [100, 110, 120, 255])
        blue_ish = out[(0 * gen.GRID + 0) * gen.GRID + 8]
        self.assertEqual(blue_ish, [100, 110, 120, 200])


class ScreenTest(unittest.TestCase):
    def test_level_for_is_inverse_of_curve(self):
        curve = [i * 10 for i in range(256)]
        self.assertEqual(gen.level_for(curve, 0), 0)
        self.assertEqual(gen.level_for(curve, 15), 2)
        self.assertEqual(gen.level_for(curve, 10_000), 255)

    def test_generated_screen_covers_every_cell_once(self):
        # 2x1 dot shape, 3x2 dots, row shift 1, 3 levels
        params = [2, 1, 1, 3, 2, 0, 2, 3]
        u16 = [0, 1] + [5, 3, 1, 0, 2, 4]
        curve = list(range(0, 256 * 4, 4))
        width, height, thr = gen.generated_screen(params, u16, curve)
        self.assertEqual((width, height), (6, 2))
        self.assertTrue(all(cell is not None and cell[0] >= cell[1] >= cell[2] for row in thr for cell in row))


@unittest.skipUnless(os.environ.get("C410_CTS"), "set C410_CTS=/path/to/C410sc.cts to run")
class SamsungFileTest(unittest.TestCase):
    def test_generates_data_file_with_expected_layout(self):
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "c410scms.dat")
            subprocess.run([sys.executable, GEN, os.environ["C410_CTS"], "-o", out], check=True, capture_output=True)
            with open(out, "rb") as f:
                data = f.read()
        self.assertEqual(data[:8], b"C410SCMS")
        pos = 12 + gen.GRID ** 3 * 4
        sizes = []
        for _ in range(4):
            w, h = struct.unpack_from("<HH", data, pos)
            sizes.append((w, h))
            pos += 4 + w * h * 3
        self.assertEqual(pos, len(data))
        self.assertEqual(sizes, [(88, 88), (88, 88), (128, 128), (96, 96)])


if __name__ == "__main__":
    unittest.main()
