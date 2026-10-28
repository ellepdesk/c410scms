# c410scms: Samsung colour for the Xpress C410 with foo2qpdl

Open reimplementation of the colour conversion and 2-bit screening of Samsung's proprietary
Linux driver for the **Samsung Xpress C410**, which Samsung also uses for the CLP-360/365 and
Xpress C420 (see [Supported printers](#supported-printers)), as a filter in front of
[foo2zjs](https://github.com/koenkooi/foo2zjs)' `foo2qpdl -z3`. Output is bit-identical to
Samsung's `rastertospl` at its Best (2-bit) quality with trapping and edge enhancement off.
No x86 binaries or emulation are needed at print time, so it works on ARM print servers.

## What you need

- foo2zjs (`printer-driver-foo2zjs` on Debian), Ghostscript, CUPS, a C compiler, Python 3.
- Samsung's colour file `C410sc.cts`. It is **not** included: it is part of Samsung's driver.
  One source is the SULDR repository (`suld-ppd-4` package):

      mkdir suld && cd suld
      curl -LO https://www.bchemnet.com/suldr/pool/debian/extra/su/suld-ppd-4_1.00.39-2_all.deb
      ar x suld-ppd-4_1.00.39-2_all.deb && tar xf data.tar.*
      ls usr/share/ppd/suld/cms/C410sc.cts

- Optional: `libscmssc.so` from SULDR's `suld-driver2` package. With it the generator reads one
  exact tone curve; without it a formula is used, which changes the CMYK values of about 0.007%
  of RGB colours slightly.

## Build and install

    make
    make data CTS=/path/to/C410sc.cts [LIB=/path/to/libscmssc.so]
    make check
    sudo make install
    sudo lpadmin -p <queue> -P ppd/samsung-<model>-scms.ppd -o ICM=scms -o Resolution=1200x600dpi

`make install` puts `c410scms-filter` and `foo2qpdl-c410scms-wrapper` (your installed
`foo2qpdl-wrapper` plus a `-Cscms` colour mode) in `/usr/lib/cups/filter`, and the generated
`c410scms.dat` in `/usr/share/foo2qpdl`. The new mode is used only for colour jobs at
1200×600 (Best); monochrome and 600×600 jobs take foo2qpdl's original path.

## Supported printers

Samsung's current driver (SULDR 1.00.39) uses one and the same colour file for these models
(`C410sc.cts`, `C420sc.cts` and `CLP-360sc.cts` are byte-identical) and configures them
identically, so they get the same result:

| Printer | PPDs | Status |
|---|---|---|
| Xpress C410 / C410W | `samsung-c410-*.ppd` | tested on a C410W |
| CLP-360, CLP-365, CLP-365W | `samsung-clp360-*.ppd` | same driver data; foo2qpdl supports it (`-z3`); not tested on hardware |
| Xpress C420 / C420W | `samsung-c420-*.ppd` | same driver data; foo2qpdl support and device ID unconfirmed |

Reports from owners of the untested models are welcome.

### Possible future models

The colour files of the **CLP-620**, **CLP-320**, **CLX-3180** and **CLX-6220** use the same
container and the same 17³ colour-table format, which this project already reads, but store their
screens differently (block type 7, see `docs/cts-format.md`). Supporting them is feasible with a
new screen decoder, checked with the same `verify/` method:

- **CLP-620:** closest. foo2qpdl drives it with `-z3` like the C410, and Samsung's default quality
  (Normal) is 2 bits per dot, the mode this filter produces. Samsung's Best quality uses 4 bits.
- **CLP-320, CLX-3180:** foo2qpdl drives them with `-z2` at 1 bit per dot, so the filter would also
  need a 1-bit output mode.
- **CLX-6220:** the colour file is in SULDR, but none of its packages has a PPD for this model, so
  how Samsung's driver handles it still has to be found out.

Each model has two PPDs:

- `*-scms.ppd`: this project's Samsung colour mode (needs `make install` and Samsung's colour file).
- `*-foo2qpdl.ppd`: just foo2qpdl set up correctly, with the stock `foo2qpdl-wrapper` and no
  Samsung file. Use this instead of the borrowed CLP-365 PPD: correct name and device ID, and the
  real resolution choices (Best = 600 dpi at 2 bits per dot, Normal = 600 dpi at 1 bit; no 1200×1200).

The CLP-360 and C420 PPDs are generated from the C410 ones by `tools/make-model-ppds`.

## Verifying against Samsung's driver

    verify/run                    # C410 PPD
    verify/run --model CLP-360    # or C420
    verify/run --edges            # keep Samsung's trapping/edge enhancement on, to see what they add

This builds a local x86-64 Docker image that downloads Samsung's driver from SULDR
(checksum-pinned), renders a test page through Samsung's `rastertospl` and through this project,
decodes both printer streams with `qpdldecode` and compares them pixel by pixel. No printer is
needed; on an ARM machine Docker runs the image emulated. Samsung's files only ever live in that
local image, never in this repository (`tests/test_no_proprietary.py` guards against it).

## How it works

    gs (RGB, 600 dpi) → c410scms-filter → foo2qpdl -z3 → printer

`c410scms-filter` interpolates Samsung's RGB→CMYK table and applies Samsung's four screens,
writing foo2qpdl's 1200×600 input in which each pair of bits is one 2-bit dot.
`tools/c410scms-gen` builds the filter's data file from `C410sc.cts`: the photo colour table,
Samsung's black optimisation (greys printed with black toner only) and the screens.
See `docs/cts-format.md` for the file format and `docs/verification.md` for how it was checked.

Not implemented (yet): Samsung's host-side trapping and edge enhancement, which add ink in the
one or two pixels along colour boundaries.

## Licence and legal

GPL-2.0-or-later (see `COPYING`). `tools/patch-foo2qpdl-wrapper` modifies foo2zjs' GPL wrapper;
`ppd/samsung-c410-scms.ppd` derives from the GPL foomatic PPD for foo2qpdl.

This project contains no Samsung code and no Samsung data. The format and behaviour were worked
out for interoperability (EU Software Directive 2009/24/EC, articles 5(3) and 6) by analysing the
data file, studying how the driver behaves and works, and comparing output; everything here was
written anew from that understanding; Samsung's colour data stays in Samsung's file, which each user
obtains themselves. Samsung is a trademark of Samsung Electronics; this project is not affiliated
with Samsung or HP.
