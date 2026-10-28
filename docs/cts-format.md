# Samsung SCMS `.cts` colour files

Format notes for the files in Samsung's Unified Linux Driver (`/usr/share/ppd/suld/cms/*.cts`,
SCMS V4.00.07), worked out for interoperability from the C410's `C410sc.cts`. Little endian.

## Container

| Offset | Content |
|---|---|
| 0x00 | magic `xVl\0`, size, `0006scms`, vendor string, build date |
| 0x6c | u16 entry count, u16 entry size (0x20) |
| 0x70 | entries: u32 type, 20-byte signature, u32 offset, u32 size |

A lookup takes a type and a 12-byte request signature and returns the **first** entry of that type
whose signature bytes are each either 0 (wildcard) or equal to the request byte. Entry order is
therefore a priority list.

Request signature bytes as used for the colour path and screens:

| Byte | Meaning |
|---|---|
| 0 | colour family (driver colour mode mapped 0→1, 1→2, 2→3, 3→7; document type can override) |
| 1 | bit depth: 0x14 = 1 bit per dot, 0x15 = 2 bits per dot |
| 2 | paper type (plain paper = 1) |
| 3 | screen id (C=1, M=2, Y=3, K=4) |
| 4 | object type (0 image, 1 text, 2 graphics) |
| 8 | screen variant |

## Blocks

Every block starts with seven u32: unused, two u32 group counts, two u16 group counts, two u8
group counts. The data follows at +0x1c in that order (all u32, then all u16, then all u8).

| Type | Content |
|---|---|
| 5 | 3D table: u16 (grid=17, channels=4, 1), then 17³×4 bytes, R slowest, values are 255 − ink |
| 6 | 1D curves applied after the 3D table (identity unless toner save) |
| 8 | generated clustered-dot screen: 12 u32 parameters + dot-shape order + dot order |
| 9 | stored threshold matrix: u32 (width, height, step, levels, mode, …) + width×height u16 |
| 0xa | 256 × u16 tone curve per screen (maps level to threshold space) |
| 0xb | embedded ICC v2.3 printer profile (CMYK → Lab), one per bit depth |
| 0x1e | 17³ × 3 RGB → RGB table |
| 0x1f | document type control records |
| 0x20 | black optimisation parameter records (u32 count + 8 bytes each) |
| 0x3ec–0x3ef | edge enhancement / trapping parameters |

## Colour conversion

Index `v >> 4`, fraction `v & 15`; the 17th grid point corresponds to 256. Tetrahedral
interpolation along the main diagonal, rounding the delta up:
`c0 + ((Δ1·f1 + Δ2·f2 + Δ3·f3 + 15) >> 4)`, clamped to 0…255. Exact white (255,255,255) skips
conversion and prints no ink.

On Linux the driver uses the photo table (object type 0) followed by black optimisation
(parameter record 1 of type 0x20): grid points closer to neutral than a threshold lose their CMY
in favour of K, in three chroma bands. See `black_optimise()` in `tools/c410scms-gen`.

## Screens (2 bits per dot)

Each screen cell has three 8-bit thresholds `t0 ≥ t1 ≥ t2`; with `v` = 255 − ink:
`v ≥ t0` → no ink, `v ≥ t1` → level 1, `v ≥ t2` → level 2, else level 3. The screen is indexed by
page position `(y mod height, x mod width)`.

Thresholds come from a 16-bit value `T` per cell and the tone curve: level m of the cell is reached
at the smallest 8-bit value whose curve value is at least `T − m·step`.

- **Matrix (type 9):** `T` stored per cell, `step` from the header.
- **Generated (type 8):** parameters `(a, b, shift, d, e, small_at, big_at, levels, …)`; a tile of
  `d·a × e·b` pixels, row `i·b + j`, column `(i·shift + k·a + l) mod width`,
  `T = total − big[i·d + k] − small[j·a + l]·d·e·levels`, `step = d·e`.

Screen choice per id: ids 3 and 5 prefer a matrix, others a generated screen. For the C410 at
2 bits: C and M are generated 88×88 screens, Y a 128×128 matrix, K a generated 96×96 screen.

The printer receives each 2-bit level as a pair of horizontal 1200 dpi bits, most significant bit
first, which is also how `foo2qpdl -z3` packs its 1200×600 input.
