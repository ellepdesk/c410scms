# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
"""tools/patch-foo2qpdl-wrapper: the -Cscms pipeline and its bottom clip, with stub programs."""
import os
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The two anchors the patch looks for, with just enough around them to run the -Cscms branch.
STUB_WRAPPER = """#!/bin/sh
PREFIX=/usr
GS=gs
COLORMODE=$1; COLOR=-c; RES=1200x600; XDIM=$2; YDIM=$3; CLIP_UL="$4"; CLIP_LR="$5"
case "$COLORMODE" in
0|"")
    # Monochrome
    ;;
esac
foo2zjs-pstops $PSTOPS_OPTS | \\
$PREFILTER \\
| ($GS $PAPERSIZE -g$DIM -r$RES $GSDEV $GSOPTS \\
    -sOutputFile="|cat 1>&3" $GAMMAFILE -_ >/dev/null) 3>&1 \\
| foo2qpdl
"""

STUBS = {
    "foo2zjs-pstops": "cat",
    "gs": "cat",
    "c410scms-filter": 'echo filter "$@"',
    "foo2qpdl": 'cat; echo foo2qpdl "$@"',
}


class WrapperClipTest(unittest.TestCase):
    def foo2qpdl_args(self, ydim, clip_ul, clip_lr):
        with tempfile.TemporaryDirectory() as d:
            for name, body in STUBS.items():
                path = os.path.join(d, name)
                with open(path, "w") as f:
                    f.write(f"#!/bin/sh\n{body}\n")
                os.chmod(path, stat.S_IRWXU)
            stub = os.path.join(d, "stub-wrapper")
            with open(stub, "w") as f:
                f.write(STUB_WRAPPER)
            out = os.path.join(d, "wrapper")
            subprocess.run([sys.executable, os.path.join(ROOT, "tools", "patch-foo2qpdl-wrapper"), stub, out],
                           check=True, capture_output=True)
            env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"])
            res = subprocess.run(["sh", out, "scms", "9920", str(ydim), clip_ul, clip_lr],
                                 input=b"", env=env, check=True, capture_output=True)
            lines = dict(line.split(" ", 1) for line in res.stdout.decode().splitlines())
            return lines["filter"].split()[:-1], lines["foo2qpdl"].split()

    def clip(self, ydim, clip_ul, clip_lr):
        filter_opts, args = self.foo2qpdl_args(ydim, clip_ul, clip_lr)
        lr = args[args.index("-l") + 1]
        uly = int(args[args.index("-u") + 1].split("x")[1])
        return ydim - uly - int(lr.split("x")[1]), lr, filter_opts

    def test_a4_pads_last_band_with_blank_rows(self):
        # 7016 - 200 = 6816 rows: extend to 6912 and blank from where the old clip began
        self.assertEqual(self.clip(7016, "-u 150x100", "-l 150x100"), (6912, "150x4", ["-b", "6916"]))

    def test_letter_already_aligned_is_unchanged(self):
        self.assertEqual(self.clip(6600, "-u 150x100", "-l 150x100"), (6400, "150x100", []))

    def test_small_lower_clip_clips_to_band_instead(self):
        # 7016 - 100 - 0 = 6916 rows would need 124 rows of padding, more than the clip has
        self.assertEqual(self.clip(7016, "-u 150x100", "-l 150x0"), (6912, "150x4", []))


if __name__ == "__main__":
    unittest.main()
