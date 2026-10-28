# Trapping

Trapping hides the thin white gaps that appear where two colours meet when the printer's colour
planes land slightly out of register: the lighter colour is spread a little under the darker one.
Samsung's driver does this on the host (`JCLTrapping`, default medium). `c410scms-filter -t`
does something similar; it is an approximation measured from Samsung's output, not a bit-exact
copy like the colour conversion and screens.

## How it was measured

Samsung's `rastertospl` was run on test pages with trapping on and off (edge enhancement off),
and both outputs were decoded. Because the screens are known exactly, the levels printed at many
positions along a straight edge pin down the colour value each pixel was screened from: a pixel
whose value changed between the two runs was trapped, and the interval of values consistent with
all its observed levels gives the new value, usually to within one or two steps. Hundreds of
random colour pairs, colours on white, corners, strokes of 1 to 4 pixels and mixed pages were
measured this way; the rules below were fitted to those results and then checked on pages that
were not used for fitting.

## Rules

Ink values are 0..255 per channel, after the colour table and before screening.

- **Darkness** of a colour: `C + M + Y/4 + 1.65 K`. Of two neighbouring colours the one with the
  higher value is the darker one.
- Only C, M and Y spread; K never does. Nothing is spread from or into white (no ink at all).
- The lighter colour's C, M or Y replaces the darker pixel's where it is at least **24** higher.
- Only along **step edges between flat areas**: the pixel has the same colour as the one behind it
  (away from the edge), the lighter neighbour the same as the one beyond it, and on both sides the
  edge runs straight (a neighbour along the edge has the same colour). Gradients, photos and noise
  are therefore left alone, as Samsung mostly does.
- Width: **1 pixel**, or **2 pixels** under colours with black ink of **108** or more, when that
  colour continues at least 2 pixels behind the trapped pixel (so 1 to 3 pixel black lines and the
  middle of narrow black strokes are not filled).
- Under such black-heavy colours, a lighter neighbour that is not clearly lighter (darkness within
  22) or is even darker leaves the first pixel alone and reaches only the second, reduced by
  `12 + difference / 2`.

## Agreement with Samsung

Pixels where Samsung's trapping changes the printed levels, and how many of those `-t`
reproduces exactly (C, M, Y and K planes counted separately):

| Page | Samsung changes | Reproduced |
|---|---|---|
| flat shapes on white (training) | 3,283 | 68% |
| coloured and black strokes on colour (training) | 19,454 | 94% |
| `verify/` test page (noise, gradients, 8×8 blocks) | 22,195 | 55% |
| new shapes incl. diagonal bands (not used for fitting) | 5,859 | 58% |
| smooth photo-like page (not used for fitting) | 110 | 0% (and no false traps) |

The differences that remain are mostly diagonal edges (which `-t` leaves alone), isolated pixels
in random noise, and pixels with edges on two sides, where Samsung's own edge direction logic
decides. Run `verify/run --trap` to repeat the comparison on the test page.

## Not reproduced

With trapping on, Samsung also changes the outermost pixel of colours that border white or a very
light colour: the smaller of C and M is reduced to about ¾ (or Y to ½ when C and M are both
small), and colours with a lot of black get a nearly pure black edge. These depend on the colour
in ways that were not pinned down and are not part of `-t`, nor is edge enhancement
(`JCLEdgeEnhance`).
