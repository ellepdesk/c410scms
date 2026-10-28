# Verification

The reimplementation was checked against Samsung's own driver (SULDR `suld-driver2` 1.00.39,
`rastertospl` + `libscmssc.so`), run once in an x86-64 container for reference output only.

Method: write CUPS raster pages directly (no renderer in between), run `rastertospl` with
Quality 600x600_2 (Best), decode the QPDL stream with foo2zjs' `qpdldecode -d`, and compare plane
by plane with the reimplementation.

Results:

- Flat colour patches: every dot identical; the reconstructed screens match with zero phase offset
  relative to the page origin.
- The full 17³ colour table, including black optimisation, recovered from 4,913 patches with no
  contradiction; the generator's computed table gives identical CMYK for all 16,777,216 RGB inputs.
- A test page of per-pixel random noise, 3-axis gradients, a grey ramp and 8×8 random colour blocks:
  0 differing pixels on all four planes, both for the filter alone and through `foo2qpdl -z3` and
  `qpdldecode`.

Samsung's defaults also enable host-side trapping (`JCLTrapping` medium) and edge enhancement
(`JCLEdgeEnhance` normal). These change only pixels next to colour edges and are not implemented
here; the bit-exact comparisons above were made with both switched off. `qpdldecode` reports PBM
heights one stripe short; the data itself is complete.
