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
- **The matrix** (`$6EE4`) [measured: `tools/zx_arith.py`, every result
  equal over 2,864 angle triples]:
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
  runs them) [measured: 16,000 vertices equal]:
  `V_i = Σ_j sign · ⌊|M_ij| · |d_j| / 64⌋`, the sign applied after the
  truncation, summed in 16 bits, with `d = vertex − camera` in world
  units. Every vertex goes through the matrix, cuboids' eight corners
  included (`$6FC2` builds them from the box; no corner-and-edges sum as
  in CM2).
- **The projection** (`$7C9D`) [measured: 16,000 vertices equal]:
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
