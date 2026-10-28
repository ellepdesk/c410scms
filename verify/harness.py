# Copyright (C) 2026 Pelle van der Heide
# SPDX-License-Identifier: GPL-2.0-or-later
"""Bit-exact comparison of this project against Samsung's rastertospl (runs inside verify/Dockerfile).

Both sides get the same RGB page: Samsung's driver as CUPS raster, this project as PPM. Both
outputs are decoded with foo2zjs' qpdldecode and compared plane by plane (C, M, Y, K levels 0..3).
"""
import argparse
import gzip
import os
import struct
import subprocess
import sys
import tempfile

import numpy as np

SRC = "/src"
SULD = "/opt/suld/usr/share/ppd/suld"
CTS = "/usr/share/cups/model/uld-samsung/cms/C410sc.cts"
LIB = "/opt/smfp-common/printer/lib/libscmssc.so"
PAD = 256  # blank rows below the image; the printer's bottom margin crops the stream there

# Options Samsung's PPD lacks; appended so its host-side trapping and edge enhancement can be
# switched (their defaults are medium/normal).
EDGE_OPTIONS = """
*JCLOpenUI *JCLTrapping/Trapping: PickOne
*DefaultJCLTrapping: medium
*JCLTrapping Off/Off: ""
*JCLTrapping medium/Medium: ""
*JCLCloseUI: *JCLTrapping
*JCLOpenUI *JCLEdgeEnhance/Edge Enhance: PickOne
*DefaultJCLEdgeEnhance: normal
*JCLEdgeEnhance Off/Off: ""
*JCLEdgeEnhance normal/Normal: ""
*JCLCloseUI: *JCLEdgeEnhance
"""


def test_image(size):
    """Per-pixel noise, 3-axis gradients, a grey ramp and 8x8 colour blocks with black lines."""
    rng = np.random.default_rng(410)
    q = size // 2
    img = np.zeros((size, size, 3), np.uint8)
    img[:q, :q] = rng.integers(0, 256, (q, q, 3), dtype=np.uint8)
    y, x = np.mgrid[0:q, 0:q]
    img[:q, q:, 0] = x * 255 // (q - 1)
    img[:q, q:, 1] = y * 255 // (q - 1)
    img[:q, q:, 2] = (x + y) * 255 // (2 * q - 2)
    img[q:, :q] = (x * 255 // (q - 1))[..., None]
    blocks = rng.integers(0, 256, (q // 8, q // 8, 3), dtype=np.uint8)
    img[q:, q:] = np.kron(blocks, np.ones((8, 8, 1), np.uint8))
    img[q:, q:][::37] = 0
    return img


def cups_raster(img):
    """CUPS raster v3 (uncompressed), 8-bit RGB, 600 dpi."""
    h, w, _ = img.shape
    hdr = bytearray(1796)
    struct.pack_into("<2I", hdr, 276, 600, 600)
    struct.pack_into("<2I", hdr, 352, w * 72 // 600, h * 72 // 600)
    struct.pack_into("<5I", hdr, 372, w, h, 0, 8, 24)
    struct.pack_into("<3I", hdr, 392, w * 3, 0, 1)
    struct.pack_into("<I", hdr, 420, 3)
    return struct.pack("<I", 0x52615333) + bytes(hdr) + img.tobytes()


def decode_planes(stream, workdir, tag):
    """qpdldecode -d writes one PBM per plane; its header is one stripe short, the data is complete."""
    path = os.path.join(workdir, f"{tag}.qpdl")
    with open(path, "wb") as f:
        f.write(stream)
    subprocess.run(["qpdldecode", "-d", os.path.join(workdir, tag)], stdin=open(path, "rb"),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    planes = []
    for p in range(1, 5):
        with open(os.path.join(workdir, f"{tag}-01-{p}.pbm"), "rb") as f:
            data = f.read()
        fields, pos = [], 0
        while len(fields) < 3:
            while data[pos:pos + 1].isspace():
                pos += 1
            end = pos
            while not data[end:end + 1].isspace():
                end += 1
            fields.append(data[pos:end])
            pos = end
        pos += 1
        width = int(fields[1])
        bpr = (width + 7) // 8
        bits = np.unpackbits(np.frombuffer(data[pos:pos + (len(data) - pos) // bpr * bpr], np.uint8)
                             .reshape(-1, bpr), axis=1)[:, :width]
        planes.append(bits[:, 0::2] * 2 + bits[:, 1::2])
    return planes


def samsung(img, model, edges, workdir):
    ppd = os.path.join(workdir, "samsung.ppd")
    with gzip.open(os.path.join(SULD, f"Samsung_{model}_Series.ppd.gz"), "rt", errors="replace") as f:
        text = f.read()
    with open(ppd, "w") as f:
        f.write(text + EDGE_OPTIONS)
    opts = "Quality=600x600_2" + ("" if edges else " JCLTrapping=Off JCLEdgeEnhance=Off")
    ras = os.path.join(workdir, "page.ras")
    with open(ras, "wb") as f:
        f.write(cups_raster(img))
    env = dict(os.environ, PPD=ppd)
    out = subprocess.run(["/usr/lib/cups/filter/rastertospl", "1", "verify", "page", "1", opts, ras],
                         env=env, capture_output=True, check=True).stdout
    return decode_planes(out, workdir, "samsung")


def ours(img, workdir):
    dat = os.path.join(workdir, "c410scms.dat")
    subprocess.run([sys.executable, "-I", os.path.join(SRC, "tools", "c410scms-gen"), CTS, LIB, "-o", dat],
                   check=True, capture_output=True)
    h, w, _ = img.shape
    ppm = b"P6\n%d %d\n255\n" % (w, h) + img.tobytes()
    bitcmyk = subprocess.run([os.path.join(SRC, "c410scms-filter"), dat], input=ppm,
                             capture_output=True, check=True).stdout
    qpdl = subprocess.run(["foo2qpdl", "-z3", "-c", "-r1200x600", f"-g{2 * w}x{h}", "-p0"],
                          input=bitcmyk, capture_output=True, check=True).stdout
    return decode_planes(qpdl, workdir, "ours")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="C410", choices=("C410", "C420", "CLP-360"),
                    help="which Samsung PPD drives the reference run")
    ap.add_argument("--edges", action="store_true",
                    help="keep Samsung's trapping and edge enhancement on (not implemented here; shows their effect)")
    ap.add_argument("--size", type=int, default=2400, help="test image size in pixels (even)")
    args = ap.parse_args()

    img = np.full((args.size + PAD, args.size, 3), 255, np.uint8)
    img[:args.size] = test_image(args.size)
    with tempfile.TemporaryDirectory() as workdir:
        ref = samsung(img, args.model, args.edges, workdir)
        got = ours(img, workdir)

    q, s = args.size // 2, args.size
    regions = {"noise": (slice(0, q), slice(0, q)), "gradients": (slice(0, q), slice(q, s)),
               "grey ramp": (slice(q, s), slice(0, q)), "colour blocks": (slice(q, s), slice(q, s))}
    total = 0
    print(f"Samsung {args.model} PPD, Best quality, trapping/edge enhancement {'on' if args.edges else 'off'}")
    for p, name in enumerate("CMYK"):
        a, b = ref[p][:s, :s], got[p][:s, :s]
        diff = a != b
        total += int(diff.sum())
        per = ", ".join(f"{r} {int(diff[sl].sum())}" for r, sl in regions.items())
        print(f"  {name}: {a.size} pixels compared, {int(diff.sum())} differ ({per})")
    print("BIT-EXACT" if total == 0 else f"{total} pixels differ")
    sys.exit(0 if total == 0 or args.edges else 1)


if __name__ == "__main__":
    main()
