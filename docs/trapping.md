# Trapping and edge enhancement

Trapping hides the thin white gaps that appear where two colours meet when the printer's colour
planes land slightly out of register: the lighter colour is spread a little under the darker one.
Samsung's driver does this on the host (`JCLTrapping`, default medium). `c410scms-filter -t`
does something similar; it is an approximation measured from Samsung's output, not a bit-exact
copy like the colour conversion and screens. Edge enhancement (`-e`) is covered further down.

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

## Edge enhancement

Samsung's edge enhancement (`JCLEdgeEnhance`, default normal) sharpens the edges of text and
graphics after screening. `c410scms-filter -e` reproduces it the same way, from measurements.

Each printed level is two 1200 dpi half-dots (level 1 = `01`, 2 = `10`, 3 = `11`). On the
outermost pixel of an area, Samsung ORs extra half-dots into the screened level: the result was
exactly `level | m` for every one of about 2,000 measured edges, with `m` constant along an edge.
`m` depends on how much more of that ink the pixel has than its neighbour (the step):

| Plane | Edge between left/right neighbours: m = 1, 2, 3 from step | Edge between rows |
|---|---|---|
| C | 58, 119, 195 | 79, 146, 213 |
| M | 59, 130, 201 | 77, 143, 205 |
| K | 68, 138, 209 | 68, 138, 209 |
| Y | never | never |

A pixel takes the largest `m` over its four neighbours, counting only edges that run straight (a
neighbour along the edge within 8 of the pixel's ink), so photographic texture is mostly left
alone. With trapping on as well, only the darker side of an edge between two colours is enhanced
(edges against white always are), because the lighter side already receives the trap. Colours
near a threshold sometimes get the next lower or higher `m` from Samsung; the other inks of the
colour play a small part that is not modelled.

Pixels Samsung's edge enhancement changes (trapping off), and how many `-e` reproduces:

| Page | Samsung changes | Reproduced |
|---|---|---|
| flat shapes on white (training) | 28,539 | 80% |
| strokes on colour (training) | 26,771 | 91% |
| new shapes (not used for fitting) | 42,180 | 74% |
| smooth photo-like page | 1,638 | 74% |
| photo-like page with fine texture | 8,357 | none (`-e` changes about as many pixels elsewhere) |

With Samsung's defaults (both on) against `-t -e`: 73% on shapes, 68% on strokes, 65% on new
shapes, 70% on the smooth photo-like page. On the `verify/` test page, dominated by per-pixel
noise, it is 30%; `verify/run --edges` repeats that comparison.

## Not reproduced

With trapping on, Samsung also changes the outermost pixel of colours that border white or a very
light colour: the smaller of C and M is reduced to about ¾ (or Y to ½ when C and M are both
small), and colours with a lot of black get a nearly pure black edge. These depend on the colour
in ways that were not pinned down and are not part of `-t`.
