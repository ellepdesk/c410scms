# Verification

`verify/run` reproduces the check: it builds an x86-64 image with Samsung's driver (SULDR
`suld-driver2` 1.00.39 and `suld-ppd-4`, downloaded at build time and checked against pinned
SHA-256 sums), writes a test page directly as CUPS raster (no renderer in between), runs Samsung's
`rastertospl` at Quality 600x600_2 (Best), runs `c410scms-filter` and `foo2qpdl -z3` on the same
pixels, decodes both QPDL streams with foo2zjs' `qpdldecode -d` and compares the planes.

The test page has per-pixel random noise, 3-axis gradients, a grey ramp and 8×8 random colour
blocks with black lines, 2400×2400 pixels. Results with Samsung's trapping and edge enhancement
off:

| Samsung PPD | Result |
|---|---|
| C410 | bit-exact, all four planes |
| CLP-360 | bit-exact |
| C420 | bit-exact |

During development the same method was also used on flat patches (every dot identical, screens at
zero phase offset to the page origin) and on all 4,913 grid colours of the colour table; the
generator's computed table gives identical CMYK for all 16,777,216 RGB inputs.

Samsung's defaults enable host-side trapping (`JCLTrapping` medium) and edge enhancement
(`JCLEdgeEnhance` normal). They change only pixels next to colour edges and are not implemented
here bit-exactly; `verify/run --edges` shows their effect (about 600,000 of 23 million pixels on the test page,
almost all in its noise and colour-block areas). `qpdldecode` reports PBM heights one stripe short;
the data itself is complete.

`c410scms-filter -t` approximates the trapping part; `verify/run --trap` compares it with
Samsung's trapping (edge enhancement off) on the test page. Results and method: `docs/trapping.md`.
