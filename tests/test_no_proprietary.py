# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
"""Guard: the repository must contain no Samsung (or other) binaries, packages or colour files.

Samsung's driver files are only ever downloaded by the user (verify/Dockerfile, README).
"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {".git", "__pycache__"}
BUILD_OUTPUTS = {"c410scms-filter", "c410scms.dat", "foo2qpdl-c410scms-wrapper"}
FORBIDDEN_SUFFIXES = (".cts", ".so", ".deb", ".rpm", ".gz", ".xz", ".zip", ".tar", ".tgz", ".exe", ".dll",
                      ".icc", ".icm", ".dat", ".pbm", ".spl", ".qpdl", ".ras")
FORBIDDEN_NAMES = {"rastertospl", "libscmssc.so", "pstosecps", "smfpnetdiscovery"}
MAGICS = {
    b"\x7fELF": "ELF binary",
    b"!<arch>": "ar archive / Debian package",
    b"\x1f\x8b": "gzip data",
    b"\xfd7zXZ": "xz data",
    b"PK\x03\x04": "zip archive",
    b"\xcf\xfa\xed\xfe": "Mach-O binary",
    b"\xca\xfe\xba\xbe": "Mach-O universal binary",
}


def repo_files():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if os.path.relpath(os.path.join(dirpath, name), ROOT) in BUILD_OUTPUTS:
                continue
            yield os.path.join(dirpath, name)


class NoProprietaryFilesTest(unittest.TestCase):
    def test_no_binaries_packages_or_colour_files(self):
        problems = []
        for path in repo_files():
            rel = os.path.relpath(path, ROOT)
            name = os.path.basename(path)
            if name in FORBIDDEN_NAMES or name.lower().endswith(FORBIDDEN_SUFFIXES):
                problems.append(f"{rel}: forbidden file type")
                continue
            with open(path, "rb") as f:
                head = f.read(64)
            for magic, what in MAGICS.items():
                if head.startswith(magic):
                    problems.append(f"{rel}: {what}")
            if head[0x0C:0x10] == b"scms":
                problems.append(f"{rel}: looks like a Samsung SCMS colour file")
            if b"\0" in head and not rel.startswith("tests/"):
                problems.append(f"{rel}: binary content")
        self.assertEqual(problems, [])

    def test_ppds_are_free_foomatic_derivatives_not_samsung_ppds(self):
        for name in os.listdir(os.path.join(ROOT, "ppd")):
            with open(os.path.join(ROOT, "ppd", name), errors="replace") as f:
                text = f.read()
            with self.subTest(name=name):
                self.assertIn("published under the GNU General Public License", text)
                self.assertNotIn("rastertospl", text)
                self.assertNotIn("Samsung Electronics", text)


if __name__ == "__main__":
    unittest.main()
