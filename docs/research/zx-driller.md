# Driller on the ZX: the redraw, the camera and the view

*Track D, the ZX oracle. Found 2026-10-31 by disassembling Spectrum
Computing's retail `Driller.tzx` (decision 1) with Castle Master II's
annotated listing as the map, and confirmed by running the original's own
routines headless in SkoolKit 10.1's simulator (`tools/zx.py`,
`tools/zx_arith.py`). Addresses are the original's. The control file is
`disasm/driller.ctl`; `make zxdisasm` builds the annotated listing.*

Tags as in the brief: **[measured]** means run in the simulator or read
from the bytes; **[read]** means read from the code, not yet exercised
by a check.

The checks quoted below are `tools/zx_arith.py --cases 5000`, run
2026-10-31: the original's own routines called with random inputs and
compared with the transcription in that file, every result equal
(`make zxcheck` runs the same with fewer cases).

## For the other tracks, in short

- **World units.** An object's cell coordinate `c` is at `64·c` world
  units: the object pass makes `cell × 64` with two `SRL H : RR L` from
  `H = cell, L = 0` (`$6BC3`). The camera's position is in the same
  units, 16-bit: x `$8762`, y `$8764`, z `$8766` [read]. Y is up.
- **Angles** in 5° units, 0-71: pitch `$876C`, yaw `$876D`, roll `$876E`,
  taken straight from an entrance's bytes 4, 5, 6 (`$9DB0`) [read; the
  start matches, measured].
- **An entrance puts the camera at** (`$9D1C`) [read; measured at the
  start: entrance 19 of area 1, cell (72, 1, 92), gives (4640, 160, 5920)]:
  - `x = 64·ex + 32`, `z = 64·ez + 32`: the entrance cell's centre;
  - on the probe, `y = 64·(ey + h − 1) + 32` where `h = ($8776) =
    L × scale`, `L` the vertical extension (`$8772`, 1-4; the game
    starts at 2 and the panel shows `L − 1`) and `scale` the area's
    (`$8779`, header byte 5). The eye is `64·L·scale − 32` units above
    the floor of the entrance's cell, 1.5 cells at the start;
  - in the jet (`$877A ≠ 0`), `y = 64·ey + 32`.
- **The matrix** (`$6EE4`) [measured: 5,864 angle triples]:
  `M = S · Rroll · Rpitch · Ryaw`, starting from the identity (1.0 = 64),
  each product rounded to a signed byte by `(v + 32) >> 6`, a rotation
  skipped when its angle is 0. Rows are the camera's x, y, z:
  - `Ryaw = [[c, 0, −s], [0, 64, 0], [s, 0, c]]`
  - `Rpitch = [[64, 0, 0], [0, c, s], [0, −s, c]]`
  - `Rroll = [[c, s, 0], [−s, c, 0], [0, 0, 64]]`
  - `S = diag(32, 64, 21)` (`$88D2-$88D4`)
  - `s`, `c` from the table at `$8E78`: 72 pairs (sin, cos), signed
    bytes, 1.0 = 64 (CM2's table, byte for byte).
  - So yaw 0 looks along +z, yaw 18 along +x; positive pitch looks down;
    camera x is screen right.
- **The transform** (`$6E25` compiles a shift-and-add multiply for each
  of the nine coefficients into the render buffer at `$5CBC`; `$7915`
  runs them) [measured: 40,000 vertices]:
  `V_i = Σ_j sign · ⌊|M_ij| · |d_j| / 64⌋`, the sign applied after the
  truncation, summed in 16 bits, with `d = vertex − camera` in world
  units. Every vertex goes through the matrix, cuboids' eight corners
  included (`$6FC2` builds them from the box; no corner-and-edges sum as
  in CM2).
- **The projection** (`$7C9D`) [measured: 40,000 vertices, some outside
  the side planes, some at `Z = 0`]:
  - `x_s = XC + trunc(XC · X / Z)`, `y_s = YC + trunc(YC · Y / Z)`,
    `trunc` toward zero (an exact 8 × 16-bit product, `$910E`, then a
    24 / 16-bit divide on the magnitudes, `$91F1`).
  - `XC = 104`, `YC = 52` (variables at `$88D9`, `$88DA`).
  - `X ≤ −Z` gives 0 and `X ≥ Z` gives `2·XC`; likewise y. `Z = 0`
    gives the centre.
  - `y_s` counts up from the view's bottom edge: the fill draws `y_s`
    into buffer row `104 − y_s`.
  - With `S` folded into `M`, the focal length in pixels is
    `104 · 32 / 21 = 52 · 64 / 21 ≈ 158.5` on both axes, for unscaled
    camera coordinates: square pixels, a horizontal field of view of
    `2·atan(21/32) ≈ 66.5°` and a vertical one of `2·atan(21/64) ≈
    36.3°`.
- **No near plane.** The view volume is a pyramid with its apex at the
  eye: five planes `x + z ≥ 0`, `y + z ≥ 0`, `z − x ≥ 0`, `z − y ≥ 0`,
  `z ≥ 0`, classified per vertex by `$7C37` and clipped in 3D by `$799E`
  (the scaled coordinates, so the side planes are the field of view's)
  [read]. A clipped vertex moves to the crossing `P + (Q − P)·a/b` with
  the divide rounded (`$92D7`), and its coordinate on the plane set
  exactly.
- **The view buffer** is at `$5CBC`: 26 bytes (208 pixels, bit 7 left)
  by 105 rows, top row first. The copy (`$9BF7`, one `LDIR` a row through
  the row table at `($8A1B)`) shows rows 0-103 at screen (24, 16)-(231,
  119); row 104 (`y_s = 0`) is drawn but never shown [measured: the
  buffer read back after a redraw].
- **Steps and turns.** Step sizes `$88BE`: a count (8), then 1, 2, 5,
  10, 25, 50, 100, 250, indexed by `$876B` into `$876A`; the step in
  world units is `$8768 = ($876A) × scale`. Turns `$88C9`: a count (6),
  then 1, 2, 3, 6, 9, 18 (5° units), indexed by `$8770` into `$876F`
  [read; the start's values measured]. A step forward moves
  `x += ⌊step · sin(yaw) / 64⌋`, `z += ⌊step · cos(yaw) / 64⌋` (floor,
  arithmetic), negated after the floor for a step back; in the jet the
  step first splits by pitch, `y −= ⌊step · sin(pitch) / 64⌋` and the
  horizontal step is `⌊step · |cos(pitch)| / 64⌋` (`$A364`) [read].

## The object pass

`$6B7C`, for each object of the area (then each global) [read]:

- **Skipped**: type 0 (entrances), invisible (bit 6 of the type byte).
- **The coarse cull** (`$6C53` builds it, once a redraw): a box in
  cells, `$88E5-$88EA` as (x max, x min, y max, y min, z max, z min).
  - The four directions (yaw ± 8, pitch ± 8), `$88D7` = 8 being 40°,
    each pick an octant: the yaw's quadrant (0-17, 18-35, 36-53, 54-71)
    gives x and z; pitch 0-17 (down) gives −y, 54-71 (up) +y, and
    18-53 (past vertical) turns x and z round too.
  - Each octant sets the box's bound on its side of each axis to the
    area's extent that way (`$88DF-$88E4`: 127, 0, 63, 0, 127, 0 on a
    platform). A bound no direction set is the camera's cell (`x / 64`;
    plus 1 for a max).
  - An object is culled if `min > box max` or `min + size < box min`
    on any axis, as signed 8-bit compares.
  - With the corners at ±40° and the view's half-angles 33° and 18°, it
    culls only what the frustum would [inferred].
- **The box relative to the camera**, 16-bit world units, `64·min −
  camera` and `64·(min + size) − camera` an axis, kept for the sort; and
  six side bits (`$5E62`): bit 0 if the camera is below x min
  (`64·x − camera > 0`), bit 1 if above x max (`64·(x + dx) − camera <
  0`), bits 2-3 for y, 4-5 for z.
- **By type**: cuboid `$6FC2`, sensor `$7592`, rectangle `$74B7`,
  pyramid (4-9) `$70B7`, line or polygon (10-14) `$742B`.
  - **A cuboid** shows the faces its side bits allow: −X with bit 0, +X
    with bit 1, and so on, coloured by its nibbles in the database's
    order (−X, +X, −Y, +Y, −Z, +Z, low nibble first); colour 0 isn't
    drawn, and an object with no face left is dropped. Its eight
    corners all go through the matrix. No facing test.
  - **A pyramid** drops a face whose first three screen points turn
    clockwise (y up) (`$7EE5`, `$5E60` = 1).
  - **A rectangle, line or polygon** has one face, coloured by its low
    nibble when its first three screen points turn anticlockwise (y up)
    and by its high nibble otherwise (`$5E60` = 2), not drawn if that
    nibble is 0.
  - `$7EE5` returns 0 for anticlockwise and 1 for clockwise; for
    collinear points mostly 1 [measured: 20,000 random triangles; one
    near-collinear one, cross product 5, came back clockwise].
- **Vertices** are transformed and classified against the five planes
  (`$7D46`); if all are inside, the faces are projected as they are
  (`$81B6`), else each face is clipped plane by plane (`$7D8C`, `$799E`)
  and then projected (`$828D`).

## The draw list and the sort

- An object joins the draw list only if one of its faces survives (a
  non-zero colour, in front, and something left after the clip). Its
  entry (`($8A9D)`, 4 bytes) points at its projected data (`($8A99)`:
  its id; a face count, bit 7 set if a face covers the whole view; then
  per face a byte `colour << 4 | points` and the points' (x, y) bytes)
  and at its box relative to the camera (12 bytes: x min, x max, y min,
  y max, z min, z max, 16-bit world units: `64·cell − camera`). The
  count is `$8918` [read].
- **The list starts with the area's objects in the database's order,
  then the globals** (`$6B3D`, then `$6B48`). Castle Master II, and
  ScummVM after it, put the globals first. In the entrance views the
  globals (the rig and the skanner) are all invisible, so it doesn't
  show there [read].
- **The sort** (`$767E`) is Castle Master II's, and ScummVM's
  `compareBoundingBoxAxis` and `sortObjectsForRendering` case for case
  (`area.cpp:321-375`). Transcribed in `tools/zx_arith.py` (`sort`)
  [measured: 5,000 random lists of 2-20 boxes, many overlapping or tied,
  each sorted into the original's order]: up to `n − 1` bubble passes over adjacent
  pairs (P, Q), stopping after a pass with no swap. Per axis (x, then y,
  then z), on the camera-relative boxes:
  - the boxes overlap (`P.min < Q.max` and `Q.min < P.max`): no verdict;
  - P straddles the camera (`min < 0 ≤ max`): P is nearer; else if Q
    does, Q is;
  - they're on opposite sides of the camera: no verdict;
  - else the one whose min is nearer zero is nearer (if the mins are
    equal, the maxes decide: with both sides positive, P is nearer when
    `Q.max ≥ P.max`; with both negative, when `Q.max < P.max`).
  - The pair keeps its order only if Q is nearer on some axis and P on
    none; otherwise it swaps, even with no verdict on any axis.
  - Every comparison is a 16-bit subtraction's sign.
- **The draw** (`$7803`) paints the list in order, far to near. Each
  face is scanned (`$83FC`; a two-point face, a line, by `$85FF`) and
  filled (`$80C0`) at once, in its object's face order.
  - If any object has a face covering the whole view (a four-point face
    on the four corners (0, 0), (0, 104), (208, 104), (208, 0)), drawing
    starts at the last such object in the list and the buffer isn't
    cleared.
  - Otherwise the buffer's 104 shown rows are cleared to 0 first, if the
    area's flags are non-zero.

## The fill

Transcribed in `tools/zx_arith.py` (`scan`, `fill`) [measured: 5,000
random convex polygons of 1-6 points, in both windings, on and inside
the view's edges, each equal byte for byte to `$83FC` then `$80C0`
drawing into the same random buffer]:

- **Screen to pixels.** A screen point `(x, y)`, `x` 0-208 and `y` 0-104
  with `y` up, covers pixel column `x − 1` and buffer row `104 − y`.
  `x = 0` is off the view's left edge, `y = 0` is the hidden row 104.
- **Edges** (`$83FC`), in order and closing back to the first point, each
  walked from its lower end for the rows `[y_low, y_high)` (the upper
  end's row isn't written), one x a row into a table of 3 bytes a row
  (`($8A9F)`: a count and up to two x):
  - a vertical edge: its x;
  - a steep edge (`|dy| ≥ |dx|`): Bresenham with the error starting at
    `|dy| >> 1`; write x, add `|dx|`, and step x once when the error
    reaches `|dy|`;
  - a shallow edge: the error starts at `|dx| >> 1`; write the row's
    first x, then step x, adding `|dy|` each step, until the error
    reaches `|dx|`, which moves to the next row;
  - a row keeps the first two distinct x values written to it;
  - a horizontal edge counts only on the polygon's top or bottom row,
    and overwrites that row with its two ends.
- **Spans** (`$80C0`), from the top row down: each row from its lower x
  to its higher x inclusive (one pixel for a row with one x), written
  opaquely, ink and paper: the face's pattern byte for `y AND 3` (the
  screen y, so `(104 − row) AND 3`) through left and right masks
  (`$80B2`), the row's table entry cleared as it goes. The patterns are
  the database's 15 four-byte shades (`($891D)`, database `+$0A`), colour
  `c` at `4·(c − 1)`.
- So the top vertex's row is drawn only through a horizontal top edge,
  and a polygon's spans are the original's integer edge walk, not pixel
  centres: the model's fill rule (`docs/engine.md`, section 9) will
  differ from the ZX at edges unless this is transcribed.
- A line (`$85FF`) writes one x a row when steep and the whole run a row
  when shallow [read; not yet checked].

## The view oracle

`make zxviews` draws every entrance view with the original's own code
(`tools/zx_views.py`, on `tools/zx.py`'s `render_view`), into
`build/zx/views/`: for each, the view's 104 shown rows of 26 bytes (bit 7
left, set = ink) as `a<area>_e<entrance>.bin`, a PNG, and a record in
`views.json`. `tools/zx.py --view AREA:ENTRANCE [--camera
x,y,z,pitch,yaw,roll]` draws one, from any camera.

For each view, from the in-play snapshot:

1. The area (`$8862`) and entrance (`$8911`) are poked and the game's
   own placement called (`$9D1C`, which loads the area with `$BE18`);
   the probe stays at the start's extension (`L = 2`).
2. The buffer is zeroed, so the image is deterministic: the draw clears
   the buffer only when the area's flags (`$889F`) are non-zero, and the
   interiors' are 0 (areas 19, 21, 22, 23, 25, 27), their walls covering
   the view.
3. `$8920` bit 2 is set, as a step or turn sets it, and the redraw is
   called with a sentinel return address. Stops at `$6B5C`, `$6B5F`,
   `$6B72` and `$6B75` time its stages.

What it checks (`make zxcheck`) [measured 2026-10-31]:

- The start view equals, byte for byte, the buffer the game drew itself
  at boot. Against the screen it differs only in the gun sight, which the
  game draws over the view's centre after the copy.
- Of the 65 entrances, the game places the camera at 63 exactly where
  the formula above puts it. Two it can't reach: area 2's entrance 16
  shares its id with a wall earlier in the area's list, and the lookup
  (`$A8BA`: the globals, then the area's objects, the first with the id
  of any type) finds the wall; area 127's entrance has id 0, which means
  "keep the position". Those two are drawn from the formula's camera
  (`"placed": "formula"` in the JSON).
- Every view draws again identically, with and without contention.

## What a redraw costs

Measured 2026-10-31 over the 65 entrance views (`make zxviews`): T-states
from the call to `$6B12` to its return, in SkoolKit's contention-modelling
simulator (`CCMIOSimulator`) with the game's interrupt running, as a 48K
runs it. The copy to the screen (`$9BF7`) isn't included.

| | median | min | max |
|---|---|---|---|
| the redraw | 2,293,923 | 670,879 | 4,273,507 |
| the same without contention or interrupts | 2,006,570 | 612,740 | 3,861,640 |
| objects drawn | 10 | 2 | 19 |

- That's 0.66 s for the median view at 3.5 MHz (33 frames) and 1.22 s at
  the busiest (area 19's entrance 7), which matches "about one update a
  second".
- Of the 65 views' time together, projecting (cull, matrix, transform,
  clip, project: to `$6B5C`) takes 63%, the sort 11% and drawing 26%.
- Contention and the interrupt add a median 13.5%.

## Loading and the protection

- The tape's first code block is a turbo loader at `$FE40`. It loads the
  screen, then the game's 37,590 bytes at `$6B12`, then a second screen,
  wipes itself and jumps to `$97A4` [read].
- SkoolKit's `tap2sna.py` simulates the loader (`make zx`).
- **The protection** (`$CB7A`) asks for a word from the manual: page,
  line and word from a table at `$ABC1`, picked by `$8A1D` (which the
  interrupt counts up). It first writes `$DD` at `$6B12`; only the right
  word writes `$E5` at `$6B13`, so the redraw starts `PUSH IX` instead of
  `JR $` (`$18 $FE`, an endless loop) [read; measured: the bytes before
  and after].
- `tools/zx.py --boot` reads the word the table asks for and types it, as
  a player would, then presses ENTER at the control menu (`$C9C6`), and
  stops at the main loop's top, `$9825`, in play at the start: Amethyst,
  entrance 19, timer 04:00:00. `make zx` saves that as
  `build/zx/driller.z80`.

## The redraw

`$6B12` is CM2's `L83aa_redraw_whole_screen`, with Driller's variables in
the same places as CM2's (`$5E4C-$5F4C`) [read]:

| Address | What | CM2's |
|---|---|---|
| `$6B12` | the redraw: if `$8920` bit 2 (moved or turned), re-project and sort, then draw; else draw only if `$8921` bit 3 | `L83aa` |
| `$6C53` | the coarse cull's box (`$88E5-$88EA`, cells), from the yaw and pitch quadrants and `$88D7` | `L8bb7` |
| `$6EE4` | the matrix | `L95de` |
| `$7896` | `$5E55 = $5E4C · $5E55`, rounded | |
| `$6E25` | compile the nine multiplies into `($8A97)` (the render buffer) | |
| `$6B7C` | the object pass: area objects (`($8864)`, `$8863` of them), then the eight globals at `$87A5` (`$890F`) | `L8431` |
| `$6FC2` | a cuboid | `L9661` |
| `$70B7` | a pyramid | `L97bb` |
| `$74B7` | a rectangle | `L9b5b` |
| `$742B` | a line or polygon | `L9ac5` |
| `$7592` | a sensor | |
| `$7915` | the transform | `L850f` |
| `$7D46` | transform and classify an object's vertices | `L9246` |
| `$7C37` | one vertex against one frustum plane | |
| `$799E` | clip an edge against a plane | `L85ae` |
| `$7C9D` | the projection | `L90fc` |
| `$767E` | the sort | `L9c2d` |
| `$7803` | draw the sorted objects into the buffer | `L9d46` |
| `$80C0` | fill a face's spans from the edge table `($8A9F)`, patterns at `($891D)` | `L94fe` |
| `$9BF7` | copy the buffer to the screen (from the main loop, `$9974`) | `La298` |

The redraw returns at `$6B7B`. Its entry and exit are what
`tools/zx.py`'s view oracle calls.
