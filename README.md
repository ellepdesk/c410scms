# c410scms: Samsung colour for the Xpress C410 with foo2qpdl

Open reimplementation of the colour conversion and 2-bit screening of Samsung's proprietary
Linux driver for the **Samsung Xpress C410** (C410W/C410FW family), as a filter in front of
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
    sudo lpadmin -p <queue> -P ppd/samsung-c410-scms.ppd -o ICM=scms -o Resolution=1200x600dpi

`make install` puts `c410scms-filter` and `foo2qpdl-c410scms-wrapper` (your installed
`foo2qpdl-wrapper` plus a `-Cscms` colour mode) in `/usr/lib/cups/filter`, and the generated
`c410scms.dat` in `/usr/share/foo2qpdl`. The new mode is used only for colour jobs at
1200×600 (Best); monochrome and 600×600 jobs take foo2qpdl's original path.

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
