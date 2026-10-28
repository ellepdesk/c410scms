# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
"""The committed per-model PPDs must equal what tools/make-model-ppds derives from the C410 ones."""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PPD_DIR = os.path.join(ROOT, "ppd")


class ModelPpdTest(unittest.TestCase):
    def test_derived_ppds_are_up_to_date(self):
        with tempfile.TemporaryDirectory() as d:
            for variant in ("foo2qpdl", "scms"):
                shutil.copy(os.path.join(PPD_DIR, f"samsung-c410-{variant}.ppd"), d)
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "make-model-ppds"), d],
                           check=True, capture_output=True)
            for name in sorted(os.listdir(d)):
                with self.subTest(name=name), open(os.path.join(d, name)) as a, \
                        open(os.path.join(PPD_DIR, name)) as b:
                    self.assertEqual(a.read(), b.read(), f"{name} is stale; run tools/make-model-ppds")

    def test_each_model_has_its_own_device_id(self):
        ids = {}
        for name in os.listdir(PPD_DIR):
            with open(os.path.join(PPD_DIR, name)) as f:
                line = next(ln for ln in f if ln.startswith("*1284DeviceID:"))
            ids.setdefault(name.split("-")[1], set()).add(line.split("MDL:")[1].split(";")[0])
        self.assertEqual(ids, {"c410": {"C410 Series"}, "c420": {"C420 Series"}, "clp360": {"CLP-360 Series"}})


if __name__ == "__main__":
    unittest.main()
