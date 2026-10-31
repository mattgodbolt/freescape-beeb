# The maths: the transform's products and the projection

Track F's survey and its figures (docs/engine.md, stages 3 and 5, and
section 9). The 6502 is `src/maths.6502` and `src/project.6502`; the model,
bit for bit the same, is `tools/model/maths.py`; `tools/mkmaths.py` writes
the model's tables for the assembler; `make maths` checks the one against
the other and times it (`tools/mathscheck.6502`, `tools/mathscheck.mjs`).

**How the figures were made.** Unless a line says otherwise, every cycle
count below was measured on 2026-10-31 by `make maths`: jsbeeb's Master
(65C12), headless, counting from the `JSR` to the return, so each includes
its `JSR` and `RTS`. Error figures are from `tools/mkmaths.py --survey` on
the same day: 100,000 random points per range, Z log-uniform from ZNEAR to
742,000 (Driller's deepest view, `8192 · √2 · 64`), against exact
division, in sixteenths of a pixel. "Counted" means added up from the
instructions, not run.

## The parameters

- `FX = 16 · 158.48 / 2 ≈ 1268` and `FY = 2 FX ≈ 2536` sixteenths: the
  original's focal length of `104 · 32 / 21` ZX pixels on both axes
  (`docs/research/zx-driller.md`), our pixels being two ZX pixels wide.
  `XC = YC = 832`, the middle of the 104 × 104 view.
- `ZNEAR = 64`, one world unit. The method's error is relative, so it
  doesn't depend on Z; ZNEAR only sets how many shift cases the 6502 has
  (`PROJ_SMIN`): halving it adds one. The original has no near plane.
- Inputs are 24-bit signed, Z from ZNEAR to `2^23 − 1`; outputs are 16-bit
  signed, saturated.

A change of field of view is a change of FX and FY in the model. Only
`RECIP` depends on them, and `R = 2^16 FX / (8 (Zi + δ))` must stay below
65536 (`maths.py` asserts it): FX up to about 4,000 sixteenths, a field of
view down to about 23° across the 104 pixels. FY must stay `2 FX`, which
the pixels' aspect gives: y's product takes one more bit of Y instead of a
second table.

## The transform's products (stage 3)

`v · m`, v a signed 16-bit coordinate and m a signed byte (1.0 = 64), to
24 bits, by quarter squares: `a · b = f(a + b) − f(a − b)`, `f(n) = ⌊n²/4⌋`,
from two page-aligned tables, `sq[j] = f(j)` and `ng[j] = f(j − 255)`,
`j = 0..511`, each split into low and high bytes (2,048 bytes). The
coordinate's byte indexes them; |m| is patched into the operands' low
bytes once (`mul_set`, `dot_set`), since a coefficient multiplies many
vertices. The low byte is unsigned; the high byte is read raw, so a
negative coordinate's product comes out `65536 |m|` too big and that comes
off the top byte. m's sign is patched into the instructions that add the
term in (`CLC`/`ADC` or `SEC`/`SBC`; `mul` patches a branch into its
negation). It's exact, so the result is the product.

| Routine | Cycles: min, mean, max |
|---|---|
| `mul_set` (patch one coefficient) | 67, 67.9, 69 |
| `mul` (one product) | 80, 98.0, 123 |
| `dot_set` (patch a row) | 336, 352.7, 369 |
| `dot3` (three products summed) | 303, 329.2, 358 |

Checked: `mul` on all 2^24 pairs against `v · m` (`make maths`'s
`--full`, 2026-10-31: 2 minutes 50; `make check` takes every coefficient
by 4,096 chosen coordinates, about a million products, and 30,000 random
pairs with `mul_set` before each); `dot3` on 60,297 cases (edges, random,
and unit rows by coordinates within an area) against the model.

What a term costs: eight table reads (36 cycles with half of them crossing
a page), two byte products' combination, the sign correction and a 24-bit
add into the sum. Driller's vertices are cells times 64, bytes, so an 8 × 8
form of `dot3` (one product a term, a 16-bit sum) would be about half the
cost; it's not built, as it's the transform's choice to make.

## The projection (stage 5)

**Superseded on 2026-10-31** by a nine-bit reciprocal times two byte
products, with an accuracy budget set by what flickers in camera walks,
and entries for vertices that share Z, or X and Z
(`docs/research/projection.md`, which has the figures). What follows is
the first method as it was surveyed and built, kept for the record; its
code is in the history, last at 57f2e4d.

### The first method: a normalised reciprocal times quarter squares

For each vertex:

1. `s = bitlen(Z) − 13`, from Z's top non-zero byte and `proj_bl2`, picks
   one of seventeen cases by `JMP (proj_cases,X)`; each case shifts by
   constant amounts, the cheaper way round.
2. `Zi = Z >> (s + 3)`, Z's top ten bits (512-1023), indexes
   `proj_rlo`/`proj_rhi`: `R ≈ 2^16 FX / (Z >> s)`, rounded for a quarter
   of the way into Zi's interval (`PROJ_DELTA`). R is patched into
   `pmul`'s twelve operands, once for x and y both.
3. `X' = |X| >> s` and `Y' = |Y| >> (s − 1)`, sixteen bits each.
4. `P = x1 r1 + hi(x1 r0) + hi(x0 r1) + 1`, `X' = x1:x0`, `R = r1:r0`:
   all of one byte product and the high bytes of two more, each high byte
   exact (a `CMP` gives its low byte's borrow without storing it). `x0 r0`
   and the carry between the two low bytes are left out; the 1 and
   `PROJ_DELTA` take off the truncations' bias.
5. `sx = XC ± P` by X's sign, `sy = YC ∓ P` by Y's, clamped to 16 bits.

Where X' doesn't fit sixteen bits (|X/Z| beyond 8 to 16), X is taken two
bits further down and P is four times that, saturating: right to about
0.15% of P for a vertex 600 or more pixels off the view.

| | Cycles: min, mean, max |
|---|---|
| `project`, \|X\| ≤ 4Z, \|Y\| ≤ 2Z, Z ≤ 742,000 (2,914 cases) | 441, 507.9, 598 |
| `project`, every case of the check (2,981) | 422, 553.9, 1,000 |

Errors, sixteenths of a pixel (`--survey`): **2.21 at worst on the view**
(\|X\| ≤ 0.66 Z), 7.27 for \|X\| ≤ 4Z (0.14% of P). Never backwards as X
grows. As Z grows it goes back by one sixteenth in rare places where Z
crosses a power of two (4 times in the survey's 200 walks of Z in steps of
1/2000): the octave's last Zi and the next one's first truncate X' by a
different bit.

Checked: 104,335 cases against the model, exactly (edges at every power of
two of Z and at ZNEAR, every saturation, and 100,000 random over four
ranges of X/Z).

Where the cycles go, counted for s = 5 (Z from 2^17 to 2^18), as a guide
to what's left: the signs and |X|, |Y| about 40; the dispatch 16; Zi and
R's look-up 22; the patch 60; X' 48 and Y' 49; `pmul` about 90 a
coordinate; the clamped add about 32 a coordinate; calls and returns
about 50.

### The variants, with figures

| Method | Cycles a vertex | Worst on the view | \|X\| ≤ 4Z | Backwards in X, in Z |
|---|---:|---:|---:|---|
| **Chosen**: R 16-bit, x1 r1 and two exact high bytes | **508** mean, measured | **2.21** | 7.27 | 0, 4 |
| R 16-bit, the middle two products summed exactly | 553 mean (484-637), measured on an earlier build, which also lacked the top-byte tables for X's and Y's shifts and left P's low byte in memory; the products alone cost about 20 more a coordinate, counted | 1.89 | 7.70 | 0, 1 |
| R kept to 9 bits: two products | about 450, counted (one product and four patches fewer a coordinate) | 4.32 | 21.48 | 0, 0 |
| Log/antilog, 8-bit mantissas, the antilog to 1/32 octave (Master Elite's LL28) | 56 a divide (`beeb-3d.md`) plus three 24-bit normalisations | 22.60 | 133.55 | 0, 0 |
| Log/antilog, 10-bit mantissas, the antilog to 1/1024 octave | about 400, counted: three normalisations, five ten-bit look-ups, two shifts back; 6K of tables | 2.64 | 12.29 | 0, 0 |
| A real divide, `FX · |X| / Z` | `div_q` alone 876, 1,039.7, 1,217 a coordinate, measured: over 2,000 a vertex before `FX · |X|` | 0 (truncated) | 0 | 0, 0 |

Tried and dropped along the way (survey of 2026-10-31, the model only):
cheaper high bytes read without their borrow (two reads instead of four)
go backwards in X tens of thousands of times in the same walks, so they
fail the wobble test outright.

Why this one: Elite's 8-bit logs are fast but miss by a pixel and a half;
a divide is four times the cost; 10-bit logs are no faster and want twice
the table space; two products with a 9-bit R save about a tenth for twice
the error. The exact middle sum would cost about 40 cycles a vertex more,
counted, for 0.3 of a sixteenth, and makes Z's reversals rarer, not none.

### Speed-ups not taken, for later

- **12-bit operands, one quarter-square table of 8,192 two-byte entries**
  (a sideways bank): `X' R` from two reads with no patching, about 150
  cycles a vertex less, counted, but only for |X| below about Z, and a
  16K bank.
- **Signed throughout** (no |X|, |Y|): about 20 cycles a vertex less,
  counted, for 2K more of tables.
- **Each case with its own copy of the look-up and patch**: 12 cycles a
  vertex for about 750 bytes.

## Memory

As built on 2026-10-31 with the second projection (`make maths` prints
the sizes as `maths:`):

| What | Bytes | Where |
|---|---:|---|
| `sq_lo`, `sq_hi`, `ng_lo`, `ng_hi` (quarter squares) | 4 × 512 | HAZEL, page-aligned |
| `sqc_lo`, `sqc_hi`, `ngc_lo`, `ngc_hi` (the projection's signed products) | 4 × 512 | HAZEL, page-aligned |
| `proj_m` (the reciprocals, less 256) | 512 | HAZEL, page-aligned |
| `proj_bl2` (twice each byte's bit length) | 256 | HAZEL |
| `mul_set`, `mul`, `dot_set`, `dot3` | 430 | RAM outside `&3000-&7FFF`: they patch themselves |
| `project`, `project_z`, `project_y`, their cases and blocks | 2,084 | likewise |

The first projection's were `proj_rlo` and `proj_rhi` (2 × 512) in place
of `proj_m` and the SQC and NGC tables, and 1,835 bytes of code.

The build prints the code's sizes (`maths:` in `make maths`'s output).
Zero page is baron's: the arguments and results are `ZA_AUTO` globals
(`mv0`-`mv2`, `macc`, `mrow`; `proj_v`, `proj_s`), placed by liveness with
the routines' own.
