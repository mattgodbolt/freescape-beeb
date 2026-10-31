# The rasteriser and the writer

Stages 8-10 of `docs/engine.md`: faces nearest first into the span buffer,
the background, and the view's bytes. The model (`tools/model/raster.py`,
`writer.py`) is the specification; the 6502 (`src/raster.6502`,
`src/writer.6502`) matches it byte for byte, checked by `make raster`
(`tools/rastercheck.mjs`). Written 2026-10-31; every figure below was
measured that day, as each section says, in headless jsbeeb (Master) through
`tools/rastercheck.mjs`'s instruction-level profile, unless it says
otherwise.

## Running it

- `make raster`: assembles the check build, makes the scenes
  (`tools/rasterscenes.py`, checked first against the model's brute force),
  runs every scene and sequence through the 6502 and fails on any byte that
  differs. Once the whole-view model is in the tree (`tools/model/render.py`)
  it also checks every Driller entrance view (`rasterscenes.py --driller`,
  into `build/raster/driller.json`, never committed).
- `node tools/rastercheck.mjs build/raster --verbose` prints each scene's
  cycles by part; `--json FILE` writes them with the model's counts;
  `--scene TEXT` picks scenes; `--scenes FILE` another scene file.

## The specification

- **The fill rule.** A face covers a pixel when the pixel's centre is inside
  it; a centre on an edge counts for top and left edges. Per line: every
  non-horizontal edge is crossed by the lines whose centres are in
  [top, bottom) of it, at the boundary `p = ceil((x - 8) / 16)` of its x
  there, and the face covers [p_left, p_right). `raster.reference` renders
  the same image from edge functions, pixel by pixel, and every scene must
  agree with it before the 6502 sees it.
- **The background.** A pixel is ground when its centre is on the horizon
  or right of its direction as seen on the screen; sky otherwise; all sky
  with no horizon. (The whole-view model's stand-in documented "a centre on
  the line is ground", so that's the rule; the first version gave a tie to
  the side the horizon was a top or left edge of, which is as consistent but
  wasn't the documented interface.)
- **The interface** is the stand-in's: `rasterise(faces, sky, ground,
  horizon, stats)` and `write(lines)`, `decode(view)`. `spans(faces, bg,
  capacity)` is the algorithm itself, with the counts the cost model uses
  and, given the 6502's pool size, its overflow (below).

## The 6502

### Edges, exactly

Vertices are in sixteenths, so an exact boundary on each line needs the
edge's sub-pixel start. With dx, dy the edge's extent (dy > 0), t0 the first
line centre's distance below the top vertex (0-15) and x0 - 8 = 16 U + w:

- a, b = floor divmod(dx, dy); W = w + a t0 = 16 W1 + W2;
- R = W2 dy + b t0; q = ceil(R / (16 dy)), which is 0, 1 or 2;
- p0 = U + W1 + q, and the error e0 = q dy - ceil(R / 16), in [0, dy);
- each line: e -= b; if that goes below 0, e += dy and p += a + 1, else
  p += a.

That's the DDA `p_k = ceil(N_k / 16 dy)` with its error divided by 16, which
is exact because the error's low four bits never change (both steps are
multiples of 16). A vertical edge is `p = (x + 7) >> 4` on every line; a
steep one (|dx| < dy) needs no division; an error that fits a byte steps in
8 bits. Each chain's step in each copy of the line loop is a `BRA` patched to
its edge's kind (`STEP8`, `STEP16` or none).

### The span buffer

Each line keeps its gaps (what nothing covers yet) as a sorted linked list.
A face's span takes what it overlaps of them, and the pieces it takes are
**written at once**: the faces come nearest first, so a pixel a face takes is
final. A byte a piece shares with a gap waits in the gap (`gh` holds the
neighbours' halves, the left one in `PIX_LEFT`'s bits and the right one in
`PIX_RIGHT`'s) until the gap is filled, so no byte is written twice and none
is read. A line with no gaps is full; faces stop when every line is.

The gaps live in four pools, one for each value of `line AND 3`, each four
pages (gs, ge, gh, gn) of `POOL_NODES` nodes. Line loop copies, one a pool,
keep each pool's fields and each phase's pattern bytes at fixed addresses.
Measured on the scenes (2026-10-31, `tools/rasterscenes.py`'s model, nodes
handed out a frame): Driller-like scenes peak under 100 a pool, the densest
realistic ones (a 72-triangle grid) at 140, against 254; the pathological
(41 slivers, 40 full-height strips) overflow. Then the model's rule, which the
6502 follows: a face-line whose gaps don't fit isn't drawn, and
`rs_overflow` is set. One pool would have overflowed on ordinary scenes
(they peak at up to 460 gaps a frame).

### Writing

- Whole bytes go through the row runs: a page a character row of
  `STA abs,Y` (Y the line in the row), entered at the piece's first whole
  byte with an RTS planted after its last. Each row keeps one plant, moved
  only when a piece ends elsewhere, and one extra slot (storing into
  `rr_scratch`) so a plant at the line's end comes out like any other.
  `put_run` *jumps* into the run, whose RTS returns to `put_run`'s caller.
- A byte two runs share is `left AND &AA OR right AND &55`, through the
  row's two screen pages (`put_bnd`).
- The background fills each line's remaining gaps, split where the horizon
  crosses the line (`hsplit`, a level horizon a table, a sloping one an edge
  DDA in 16 bits, pinned when it's far outside).
- **What the screen already holds.** A line no face touched is background
  from end to end; if the screen being drawn (ACCCON's X) held the same
  background on it last time, it isn't written. `bg_was` keeps split + 1 for
  each screen and line, `bg_sig` the patterns those were drawn in; other
  patterns, or `raster_forget`, forget them.

## The interface for the frame

- `raster_init` once (it builds `lo16`, forgets both screens and plants the
  row runs); `raster_forget` whenever something else has drawn on the
  screens; `raster_frame` each frame, with ACCCON's X selecting the screen
  drawn into and ACCCON's Y set if the sections are in HAZEL.
- Inputs (`RasterIn`): `rs_nfaces`; per face `rs_fn` (vertices), `rs_fv`
  (first vertex), `rs_fc` (pattern); vertices `rs_vxl/vxh/vyl/vyh` in
  sixteenths inside the view, each face convex, either winding; patterns
  `rs_pat + 4 c + (line AND 3)`; `rs_sky`, `rs_ground`, `rs_horizon` (0 for
  none), `rs_hx/rs_hy` (16-bit, within `RS_HMAX`) and `rs_hdx/rs_hdy`
  (signed bytes). Limits: `RS_FACES`, `RS_VERTICES`, `RS_PATTERNS`. Output:
  the view, and `rs_overflow`.
- It uses its own zero page (baron's allocator), the stack, and its sections,
  and clobbers A, X, Y. It reads nothing else but ACCCON, and writes nothing
  else but the view (the check watches every write).
- Sections: `RasterCode` and `RasterIn` anywhere outside `&3000-&7FFF`;
  `RasterRuns` page-aligned (its own section, so the build can place it);
  `RasterWork` (per frame) and `RasterState` (frame to frame). The check
  build's sizes (2026-10-31): code 6,417 bytes, row runs 3,232, work 4,616
  (with its alignment), state 286, inputs 1,792. All of it but the inputs
  fits one 16K sideways bank, which nothing else needs paged while it runs.

## Checks

- The model against its brute force on every scene (and every Driller view):
  faces by edge functions, background by the horizon's cross product.
- The 6502 against the model, byte for byte, on 148 scenes (random convex
  polygons, Driller-like boxes, and the edge cases the brief lists) with the
  view first set to each expected byte's complement, so every byte must be
  written, and as many writes as the model counts; nothing else of either
  screen may change, and nothing outside the rasteriser's memory may be
  written. Scenes alternate the screens.
- Seven sequences of frames into alternate screens, which keep what was
  drawn: still, panning, pitching, alternating scenes, a recoloured sky,
  empty, a turning horizon. Each frame must equal the model's.
- Mutation testing (2026-10-31, `tools/rastercheck.mjs` on copies of the
  source with one change each): 17 single-instruction changes to the
  arithmetic, the halves, the gap cases, the plants, the chain swap and the
  horizon's ties; every one that changes behaviour fails the check. One,
  stopping at 103 open lines rather than 104, at first didn't, which added
  the `all-but-one-line` scene; two (a logical shift where only the low byte
  is used, a product taken where a shortcut was) don't change behaviour.
- Driller's own entrance views (65, through the whole-view model's render,
  run from the main checkout 2026-10-31) found a bug every synthetic scene
  had missed: taking out a line's first gap branched on the flags of
  `LDY r_y`, so on line 0 alone a span stopped after its first gap. The
  `top-line` scenes now catch it.

## Measurements

All 2026-10-31, `tools/rastercheck.mjs` (cycles from the call to the return,
less the stub's own).

### Driller's entrance views (the work the game will see)

65 views, faces 2-36 (median 14), every line of every face's range 51-925
(median about 290), runs 104-951. After the last round: **min 54,712, median
138,079, mean 153,463, max 399,750 cycles** for the rasteriser alone (a field
is 39,936). By part: insertion 24.1%, writing bytes 18.4%, edge set-up
14.9%, runs 12.1%, background 7.8%, stepping 6.3%, face set-up 5.4%, rows
2.9%, line loop 2.9%, shared bytes 2.3%, the horizon 1.0%.

### The cost model

Least squares over every scene and view that didn't overflow (210), the
bytes' cost fixed at the 5 cycles an `STA abs,Y` takes (the profile's row-run
share confirms it; with every view writing all 5,408 bytes, a fit can't tell
bytes from lines):

    cycles ~ 123 lines + 86 face-lines + 159 runs + 5 bytes + 1574 edges

(lines: lines the background fills; face-lines: every line of every face's
range; runs: pieces of faces and background; edges: edges crossing a line).
RMS error 10.8%. The edge term carries the per-face set-up and the chain's
walk over horizontal edges, which go with edges (about 2.3 a face); the
profile's own edge share comes to 450-700 cycles an edge on the views and
Driller-like scenes, a vertical edge with the chain's step to it about 200.
Fitted to Driller's views alone: 83 face-lines + 232 runs + 841 edges +
5 bytes, 6.6% RMS.

### The rounds

| Round | driller07 (synthetic, 17 faces) | Driller's views, median |
|---|---:|---:|
| First version: a line set-up a line, a dispatch a line, steps through zero page with a general 16-bit divide | 436,241 | |
| Line loop unrolled by pool; steps by edge kind, patched; rows set up once a character row; the background unrolled | 347,619 | |
| The face's left chain found once (the chains swap); edge shifts by table; no product for a steep edge | 336,537 | |
| `put_run` jumps into the run | 331,139 | 140,773 |
| A vertical edge's own short set-up | | 138,760 |
| The chains start the way the last face's left chain did (Driller's faces share a winding) | 328,857 | 138,079 |

The background skip doesn't show in single scenes (they forget first); in
the sequences, an empty view costs about 52,000 cycles the first time on a
screen and 9,556 after, and a slowly turning horizon rewrites a third to
three fifths of the bytes. Every line of the synthetic Driller-like scenes is touched by a face,
so they don't skip; Driller's views have sky above the buildings.

## What's left

- **The budget.** The median view's rasteriser alone is about 3.5 fields,
  against a whole frame in two (decision 2's target). The fixed part
  (writing 5,408 bytes, about 27K) is a fifth of it; the rest is per face-line
  and per run, about 85-160 cycles each, and per edge.
- **Edges shared between faces.** A box's faces come together and share
  edges, set up identically from the same top vertex; a cache of the last few
  edges (keyed by their two vertices) would save most of a set-up on a hit.
- **More of what the screen holds.** Only whole background lines are skipped
  now; the background runs before the first face and after the last, on lines
  whose split didn't move, are the next step, and they need the same records.
- **Code size.** The four copies of the line loop and of the background
  carry most of it; a sideways bank holds it easily, and the alternative
  (shared code reading the pool through pointers) costs cycles a line.
