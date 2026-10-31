# The projection: what's good enough, the fastest that is, and sharing

*Track F's second pass at stage 5 (`docs/engine.md`), 2026-10-31. The
first method and its survey are in `docs/research/maths.md`. The 6502 is
`src/project.6502`; the model, bit for bit the same, is
`tools/model/maths.py`'s `project`; `make maths` checks the one against
the other and times both on every entrance view's vertices.*

## Summary

- **The budget.** Errors that jitter are what show: an offset of up to
  1/8 px that changes from vertex to vertex as the camera moves adds
  nearly three times exact division's own flicker to a slow walk, while
  rounding every vertex to 1/4 px, an error that only steps as X or Z
  grows, adds 3-8%. So the budget is **monotone, and within 1/4 px (4
  sixteenths) on the view**.
- **The method.** A reciprocal of nine bits, the top one implicit
  (R = 256 + M, a byte), from Z's top ten bits, times two byte products a
  coordinate, each exact: worst 3.2 sixteenths on the view, never
  backwards, adding 2-4% to exact division's flicker (the first method
  1-3%).
- **Measured** on the 2,992 vertices the model projects in the 65
  entrance views: **289 cycles a vertex (median), 404 at most**, against
  the first method's 508 and 838; **a view 13,604 cycles (median), 28,670
  at most**, against 24,153 and 51,715.
- **Sharing.** `project_y` gives the y of a vertex at the last one's X and
  Z (a level camera's vertical edges) for 115 cycles (median), and
  `project_z` a vertex at the last one's Z for 216. Per object, 806 of the
  2,992 vertices need only y and 717 more share a Z: **a view 10,217
  (median), 22,312 at most**.
- **Polar forms** (portalc's polar front end) for a level camera, with
  tables for 2,304 steps a turn and 12-bit logs, are within the budget on
  the view, turn with less flicker than a byte matrix could, and would
  make a turning frame's transform and projection about a fifth of what
  they cost now: a decision for Matt, below.

## How the figures were made

All on 2026-10-31, in the model as merged that day (the rasteriser and
writer real, the ST's colours through PAL):

- **Cycles**: `make maths` (`tools/mathscheck.mjs`), jsbeeb's Master,
  headless, from each `JSR` to its return. The entrance views' vertices
  come from the model's own run (`tools/mkmaths.py --views`), object by
  object, in the order the model projects them. The first method's were
  timed the same way, from its sources at 57f2e4d built aside.
- **Errors**: `tools/mkmaths.py --survey`, 100,000 points a range, Z
  log-uniform from ZNEAR to 742,000, against exact division, in
  sixteenths of a pixel.
- **Flicker**: `tools/mkmaths.py --flicker STEP`. From every entrance,
  three walks of 40 frames (forward, sideways and up, STEP world units a
  frame, the position rounded each frame), each rendered by the model
  with each projection and with exact division rounded to a sixteenth. A
  pixel's flips are the frames it changes in; a method's **excess** is,
  pixel by pixel, the flips it makes beyond exact division's. A
  deterministic offset only moves when a pixel flips, so it adds no
  flips; jitter adds them.
- **Polar forms**: `tools/research/polar.py` (`errors`, `walk STEP`,
  `turn SUB`, `clip`), a model of portalc's tables (below).

## The budget: what flickers

Excess flips a frame, over 7,800 frames a speed (65 views, three walks,
40 frames), and the pixels a frame unlike exact division's at 2 world
units a frame. The first method's row is from the same walks run with
its own model (57f2e4d's), the rest from `--flicker`:

| World units a frame | 1 | 2 | 6 | Pixels unlike |
|---|---:|---:|---:|---:|
| exact division's own flips | 6.52 | 11.64 | 33.19 | |
| the first method | 0.213 | 0.202 | 0.316 | 7.04 |
| **chosen: Zi 10 bits, R 9** | **0.257** | **0.291** | **0.532** | 11.22 |
| Zi 9 bits | 0.288 | 0.291 | 0.554 | 11.59 |
| Zi 11 bits | 0.266 | 0.295 | 0.519 | 11.28 |
| R 17 bits | 0.308 | 0.333 | 0.558 | 11.14 |
| the chosen without its + 1 | 0.475 | 0.526 | 0.866 | 22.47 |
| log/antilog, 8-bit (Elite's) | 1.078 | 1.307 | 1.935 | 56.62 |
| log/antilog, 10-bit | 0.201 | 0.216 | 0.325 | 8.53 |
| exact, to 1/8 px | 0.257 | 0.250 | 0.453 | 8.52 |
| exact, to 1/4 px | 0.493 | 0.559 | 0.977 | 23.11 |
| exact, to 1/2 px | 0.898 | 1.045 | 1.724 | 50.64 |
| exact, to whole pixels | 0.601 | 0.822 | 1.372 | 27.15 |
| exact, then a smooth error of 1 in 512 | 0.466 | 0.538 | 0.505 | 4.80 |
| exact, then a smooth error of 1 in 256 | 0.888 | 1.271 | 1.570 | 8.38 |
| exact, then ±1/8 px of jitter | 18.283 | 15.956 | 11.409 | 16.86 |
| exact, then ±1/4 px of jitter | 36.001 | 32.684 | 24.980 | 30.55 |

"Smooth" is exact division times 1 + e, e fixed for each value of Z's top
ten bits, as a reciprocal table's rounding is; "jitter" is a different
offset for each camera-space vertex.

What it shows:

- Jitter is the thing to avoid: ±1/8 px of it adds nearly three times
  exact division's own flips to the slowest walk, ±1/4 px five and a half
  times, though ±1/8 px leaves fewer pixels unlike exact's than rounding
  to a quarter pixel does.
- Errors that are a fixed, stepped function of the vertex cost little
  even at a quarter pixel: rounding every vertex to 1/4 px adds 0.5-1.0
  flips a frame, 3-8% of exact division's own.
- The chosen method adds 0.26-0.53, 2-4%: about what rounding to 1/8 px
  adds, which is the size of its steps (X' moves in steps of R / 256,
  one to two sixteenths). The first method, whose X' had three more bits,
  adds 0.20-0.32; so does the 10-bit log, for the same reason. A
  seventeen-bit R flickers no less, so R isn't what it follows.

Sub-pixel vertices exist so edges don't shimmer (decision 12); whole
pixels add 0.6-1.4 flips a frame and leave 27 pixels a frame unlike
exact's, moving edges a pixel at a time. So the budget keeps sixteenths
and asks of the error: **it never goes backwards as X or Z grows, and
it's within 4 sixteenths on the view.** Off the view it may be relative:
about 0.3% (a guard-band vertex 16 Z to the side is out by up to 55
sixteenths, which moves the 2D clip's crossing by that share of the edge
on the view, a few sixteenths at worst). If walks were ever seen to
shimmer, the lever is X''s step: a bit more of X' halves it, for a
narrower band (12 Z) or a shift of each product.

## The methods, measured

Errors from `--survey`; x on the view is |X| <= 0.656 Z, y |Y| <= 0.328 Z;
cycles a vertex as noted.

| Method | Cycles a vertex | x on the view (mean) | y on the view | x, \|X\| <= 4 Z | Backwards |
|---|---|---:|---:|---:|---|
| The first: R 16 bits, three products, \|X\| and a slow path | 508 median, 838 max on the views (measured) | 2.21 | | 7.27 | 4 in Z |
| **Chosen: Zi 10 bits, R 9 bits, two products** | **289 median, 404 max on the views (measured)** | **3.15 (0.60)** | **3.19** | 14.07 | none |
| Zi of 9 bits (`proj_m` one page) | about 4 fewer (counted: no page bit) | 3.65 | 3.96 | 18.62 | none |
| Zi of 11 bits | about the same (counted) | 2.55 | 2.83 | 11.24 | none |
| R of 17 bits (four byte products) | about 80 more (counted: two products a coordinate, eight more patches) | 2.49 | 2.58 | 5.79 | none |
| The chosen without its + 1 | the same | 3.99 | 4.19 | 14.24 | none |
| Log/antilog, 8-bit mantissas (Elite's) | maths.md: 56 a divide, three normalisations | 23.39 | 23.78 | 133.86 | none |
| Log/antilog, 10-bit mantissas, 1/1024 octave | about 400 (maths.md, counted) | 2.69 | 2.58 | 12.33 | none |

The 9-bit R is enough: a 17-bit R costs two more products a coordinate
and flickers no less. An 11-bit Zi is a little more accurate for twice
the table, and no faster; a 9-bit one saves 256 bytes and a few cycles
for a little more error, either way within the budget. The 10-bit log is
as good as the first method on every count but its cycles.

## The method as built

For each vertex (`tools/model/maths.py` has it as the model):

1. n = bitlen(Z) picks a case by `JMP (proj_cases,X)`; Zi, Z's top ten
   bits, by constant shifts, gives M from `proj_m` and the region:
   `R = 256 FX 2^k / (Zi + 1/2)`, k = 0 for Zi >= `PROJ_T`, -1 below it,
   so R is always in [256, 512). M is patched into pmul's eight
   operands, once for x and y.
2. The region's shift t: `X' = X >> t` and `Y' = Y >> (t - 1)`, signed.
   Z >> t is then within [FX / 2, FX), so X' fits sixteen bits for any
   |X| <= 25 Z: no slow path and no clamp. That band (`PROJ_XBAND`,
   `PROJ_YBAND`) is wider than the clip's guard band (decision 17).
3. `XC + floor(X' R / 256) + 1 = (XC + x1 R) + x0 + hi(x0 M) + 1`,
   X' = x1:x0. x1 R comes signed from its own pair of tables, SQC (with
   XC added) and NGC, indexed by x1 + 128: no sign handling. x0 M's high
   byte comes from the transform's quarter squares, its low byte's borrow
   from a `CMP`. Everything is exact; the + 1 takes off the floors' bias.
4. sy is the same sum for NOT Y' = -Y' - 1, which is YC less it for Y'
   (less R / 256, a sixteenth or two, which the survey includes), so y
   needs no code of its own, and its result is left where pmul leaves it:
   y's product ends on pmul's own `RTS`.

Where the cycles go, counted for Z with bitlen 18 and Zi >= 768, which
measures 276 with x's high byte 0 and y's not: the call and return 12;
the dispatch 16; Zi 8; M 9; **the patch 34**; the block 5; x's shift 10,
its call 6, pmul 61 (x1 = 0) or 75, its store 9; y's shift 23, the jump
3, pmul 75. The products' eight table reads are about 37 a coordinate;
the rest is the sum's carries and moving bytes.

Not taken, each small: pmul in zero page (its patch 3 cycles a store: 8
a vertex, for about 70 bytes of zero page); a dispatch table on Z's top
byte that knows Zi's half (about 5 a vertex, for a table and twice the
cases); x0 added from an identity table (2 a coordinate, for 256 bytes);
`ZNEAR` raised to the clip's (decision 15), which drops four cases'
code. Rare shifts (Z under 1,024 or over 2^20) cost more cycles, and
table-driven shifts would trade a few kilobytes of HAZEL for them.

## Sharing

A vertex at the same Z as the last one projected needs no case, look-up
or patch; at the same X and Z, no x either. The results are exactly
project's (they depend only on X, Y and Z), so the model doesn't change:

- `project_z`: proj_x, proj_y to proj_sx, proj_sy, with the last Z;
- `project_y`: proj_y to proj_sy, with the last X and Z; proj_sx is left
  as it was, the column's.

"The last" is the last `project`'s, or a `project_z`'s after it.

Where Driller's vertices share (the 65 entrance views, the model's
vertices object by object, 2026-10-31):

| | Vertices | Distinct (X, Z) an object | Distinct Z an object | (X, Z) in the view | Z in the view |
|---|---:|---:|---:|---:|---:|
| The entrance views (61 of 65 level, 60 with yaw a right angle) | 2,992 | 2,186 | 1,469 | 1,887 | 931 |
| Turned 15 degrees | 2,882 | 2,118 | 2,030 | 1,836 | 1,727 |
| Tilted 15 degrees | 2,464 | 2,414 | 1,676 | 2,295 | 1,267 |
| Rolled 15 degrees | 3,093 | 3,093 | 1,657 | 2,891 | 1,140 |

- With a level camera (pitch and roll 0, most of Driller), a cuboid's
  vertical edges stay vertical: its vertices i and i + 2 (y's bit) share
  X and Z exactly, as the transform builds them from the corner and the
  edges. That holds at any yaw.
- With the yaw a right angle as well (the entrances), a box's faces are
  square to the view, and the four vertices of each of two faces share Z.
- Tilted, the vertical edges lean; rolled, nothing shares X, but Z still
  does.

What it saves, timed (`make maths`): each vertex by `project`, a view
13,604 cycles (median) and 28,670 at most; an object's vertices at one
(X, Z) together, 10,983 and 24,191; and those at one Z together too,
10,217 and 22,312 (1,469 by `project`, median 291; 717 by `project_z`,
216; 806 by `project_y`, 115). A caller gets this by ordering an
object's vertices: for a cuboid, by columns (i, i + 2), and by the face
square to the view when the yaw is a right angle.

Sharing across objects would find more (931 distinct Z in the views
against 1,469 an object), at the price of a search; and in the model's
own order, face by face, 570 vertices already follow one at their X and
Z and 710 more one at their Z, so a `project` that compared Z with the
last one's would catch most of it unasked. Comparing costs about 9
cycles a miss and saving Z 9 more, against about 50 saved a hit
(counted): worth it only for a caller that can't order its vertices.

### Across frames

A step moves every camera-space vertex and a turn rotates it, so nothing
of a projection survives either, but for a rise or fall (X and Z the
same, so sx and R are too: `project_y`'s work, if each vertex kept its
state). Turning is where reuse would pay, and it's what polar forms
give.

## Polar forms and logs (portalc's polar branch)

`docs/research/rtw-sources.md` section 1.2 describes it. For a level
camera, each world point's (x, z) offset from the eye becomes its angle
and the log of its distance, cached while the eye stands still; a
frame's camera angle then gives each point's column from a table
(`a2c`, at the angle's middle) and its depth's log by a subtract
(`lsec`), and each vertex's row is an exp of its height's log less the
depth's. No rotation, multiply or divide, and turning costs only the
lookups.

**The experiment.** A model of portalc's integer tables (its `atan`,
`lhyp`, `logf`, `expf`, `lsec` and `a2c`, the octant fold, the floored
angles and the half-step middles), with S steps an octant, tb bits of
the ratio minor / major, L bits of a log's fraction, and E bits of exp's
mantissa, columns in sixteenths. Camera space for the clip came from
exact trigonometry (64 to the unit); the projection took each vertex's
(dx, dy, dz) from the eye back out of it. The reference is exact
trigonometry with exact division. Errors are on the 61 level entrance
views, each at its own yaw and seven more, 13,061 vertices on the view:

| Tables | Worst on the view | Mean |
|---|---:|---:|
| portalc's: 1,024 steps a turn, 8-bit ratio and logs | 14.89 | 3.81 |
| 2,304 steps (Driller's 5 degrees, 32), 8-bit | 9.21 | 2.93 |
| 2,304 steps, 10-bit ratio and logs, 12-bit exp | 4.01 | 1.09 |
| 2,304 steps, 12-bit, 16-bit exp | 3.01 | 0.99 |
| 4,608 steps, 12-bit, 16-bit exp | 1.96 | 0.60 |

For comparison, the model's byte matrix (the original's, decision 11) is
out by up to 13.4 sixteenths against floating point on the entrance
views, and up to 4 pixels with pitch and roll (`docs/research/model.md`):
polar forms are nearer the true scene than the original's own maths.
1,024 steps a turn can't hold Driller's 5-degree angles exactly, which
2,304 can.

Flicker, the walks (as the budget's, the 61 level views) and turns (5/4
and 5/16 degrees a frame, both ways, 40 frames, from each level
entrance), excess flips a frame against exact trigonometry:

| | Walk, 2 a frame | Walk, 6 a frame | Turn, 5/4 degree | Turn, 5/16 degree |
|---|---:|---:|---:|---:|
| exact trigonometry's own flips | 11.66 | 33.16 | 191.39 | 63.56 |
| portalc's tables | 0.839 | 1.394 | 4.372 | 1.818 |
| 2,304 steps, 8-bit | 0.703 | 1.214 | 3.949 | 1.774 |
| 2,304 steps, 10-bit | 0.548 | 0.907 | 1.603 | 0.864 |
| 2,304 steps, 12-bit | 0.461 | 0.757 | 1.435 | 0.728 |
| 4,608 steps, 12-bit | 0.183 | 0.317 | 0.694 | 0.359 |
| byte matrix, exact division | 0.062 | 0.086 | 6.437 | 2.621 |
| byte matrix, the chosen projection (the model) | 0.286 | 0.545 | 6.764 | 2.911 |

The walks start at the entrances' yaws, nearly all right angles, where
the byte matrix is exact. Turning, the byte matrix (sines rounded to
1/64 at each in-between angle, as the model's matrix would have them)
flickers more than any of the polar tables: decision 4's in-between
frames for a turn need finer angles than the original's sine table
anyway, and polar forms take any of 2,304 steps.

**The clip in logs.** An edge with one end off the view's side is cut
where it crosses the view's edge ray, by Doom's clipper in logs
(portalc's `howitworks.md`, "Ends off the view"): the crossing's depth is
`log r + log|sin(a - w)| - log|sin(b - w)| + log cos(b - camera)` from
the in-view end's polar form, the edge's direction w and the ray's angle
b, two lookups and three adds, then an exp for its row. On Driller's own
edges (every edge of a face in the level entrance views at five yaws
that crosses a side of the view: 1,824 crossings, 1,387 of them with
their row on the view), the crossing's row against exact, in
sixteenths:

| Tables | Median | 99th percentile | Worst | A row at the view's edge, worst |
|---|---:|---:|---:|---:|
| portalc's | 0.21 | 4.92 | 12.01 | 51.08 |
| 2,304 steps, 8-bit | 0.20 | 5.10 | 9.71 | 39.95 |
| 2,304 steps, 10-bit | 0.10 | 1.78 | 3.42 | 18.95 |
| 2,304 steps, 12-bit | 0.09 | 1.66 | 3.44 | 19.09 |
| 4,608 steps, 12-bit | 0.05 | 1.22 | 2.25 | 9.69 |

(portalc's 1,024 steps put the camera's yaw a little differently, so its
crossings number 1,797.)

The last column scales the depth's relative error to a row 52 pixels
off the middle: an edge that grazes the ray (portalc measured the same
weakness) can put a far-off row a pixel out. The top and bottom are cut
in screen space by a line's gradient, in logs too (portalc's near clip of
rows): a log subtract and an exp.

**What it would cost, per vertex and per clipped edge** (portalc's
measured costs, `rtw-sources.md` 1.2 and 1.5, on its 8-bit tables; ours
want two-byte entries and a sideways bank, so somewhat more):

| Work | portalc | When |
|---|---:|---|
| A point's polar form | 369-385 | each (x, z) point, when the eye moves |
| ... by coordinate (each distinct x and z's log cached) | about 150 | idem |
| A point's column and depth | about 30 | each point, every frame |
| A vertex's row (an exp) | 81-97; about 35 by a table an octave | each vertex, every frame |
| A side crossing (Doom's clipper and its row) | about 130 | each clipped edge |

At the median view (45 vertices on about 32 (x, z) points, 14 objects),
all inferred from those costs: a turning frame about 5K (32 × 30 + 45 ×
90) against about 32K for the transform (rtw-sources.md's estimate for
`dot3` and `mul` a cuboid; about 16K with the level matrix's zero
entries skipped) plus 13.6K for the projection measured above, or 10.2K
shared; a step about 17K, or 10K with forms by coordinate, against about
3.8K for the cached transform plus the same 10.2-13.6K. A clipped edge
about 130 against a division's: `div_q` is about 1,000 cycles a quotient
(`maths.md`), a reciprocal by lookup and a product about 250-400
(`rtw-sources.md` 1.5).

What it would take: a level-camera path through stages 3 to 6 in the
model, with the tables in a sideways bank (about 12K at 2,304 steps and
10-bit logs; several banks at 12-bit); the general path kept for pitch
and roll; and the ZX oracle comparing against geometry that's truer than
the original's. **It's a decision for Matt** (below).

## Decisions to record

Proposed; the coordinator numbers them.

1. **The accuracy budget** (autonomous). A projected vertex's error must
   never go backwards as X or Z grows and must be within 4 sixteenths
   (1/4 px) on the view; off it, about 0.3%. Why: jitter is what
   flickers (±1/8 px of it adds nearly three times a slow walk's own
   flicker), while stepped errors within 1/4 px add 3-8%.
2. **The projection** (autonomous; amends decision 17's first
   paragraph). A nine-bit reciprocal, a byte under an implicit one, from
   Z's top ten bits, times two exact byte products a coordinate; y from
   NOT Y'; worst 3.2 sixteenths on the view, never backwards. Its input
   is any |X| <= 25 Z, |Y| <= 12 Z (the guard band is inside it), and
   nothing is clamped. `project_z` and `project_y` give exactly
   `project`'s result for a vertex sharing the last one's Z, or X and Z.
   Against: the first method (more precise, 1.8 times the cycles), a
   17-bit R with four products (no flicker gained, about a quarter more
   cycles), 10-bit logs (as precise, slower).
3. **Polar forms for a level camera** (Matt's call). Pitch and roll 0:
   each point's angle and log distance, kept while the eye stands still;
   columns, depths and rows by lookups and exps; the side clip by Doom's
   clipper in logs; 2,304 steps a turn (Driller's 5 degrees exactly) and
   10- or 12-bit logs. For: a turn's maths about a fifth, in-between turn
   frames at any of 2,304 steps with less flicker than a byte matrix,
   vertices nearer the true scene than the original's byte matrix puts
   them. Against: a second path through stages 3 to 6, a sideways bank of
   tables, a step costing about what it does now, and views that differ
   from the original's by its byte matrix's error (up to 13 sixteenths at
   the entrances).

## What's left

- `docs/engine.md` stage 5 and section 9 to name the method,
  `project_z` and `project_y`, and the band.
- The object pipeline's caller (track H) to order a cuboid's vertices by
  columns, and by the face square to the view at right-angle yaws, and
  call the shared entries.
- The small cuts above, if the cycles are wanted.
- If decision 3 is taken: the polar path in the model first, its tables
  sized by this experiment, then the 6502.
