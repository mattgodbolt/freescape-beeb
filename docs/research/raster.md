# The rasteriser and the writer

Stages 8-10 of `docs/engine.md`: faces nearest first into the span buffer,
the background, and the view's bytes. The model (`tools/model/raster.py`,
`writer.py`) is the specification; the 6502 (`src/raster.6502`,
`src/writer.6502`) matches it byte for byte, checked by `make raster`
(`tools/rastercheck.mjs`). Written 2026-10-31 and revised the same day for
the restructure (the rounds below); every figure was measured that day, as
each section says, in headless jsbeeb (Master) through
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
  [top, bottom) of it, and the face covers [p_left, p_right) of the edges'
  boundaries there. A vertical edge's boundary is the exact one,
  `(x + 7) >> 4`; a sloping edge's is a DDA's (below), which the exact
  boundary `ceil((x - 8) / 16)` (`edge_crossings_exact`) is the measure of.
- **Faster rather than exact** (decisions 11-12: Matt would "much rather
  we have a faster version than a pixel correct one"). Measured 2026-10-31
  by comparing `edge_crossings` with `edge_crossings_exact` on every edge:
  on Driller's 65 entrance views, 38,903 of 39,412 edge-lines (98.7%) get
  the exact boundary, 268 are a pixel left of it and 241 a pixel right,
  none further; 190 of 351,520 view bytes (0.054%) differ, in 41 views. On
  the 148 synthetic scenes, 0.19% of bytes differ. Every DDA term rounds
  toward the edge's top vertex, so a boundary never passes the edge's far
  end and never leaves the view.
- **The background.** A pixel is ground when its centre is on the horizon
  or right of its direction as seen on the screen; sky otherwise; all sky
  with no horizon. Driller's views have no horizon (decision 8a): the sky
  is the background and the ground is the floor object's face.
- **The interface** is the stand-in's: `rasterise(faces, sky, ground,
  horizon, stats)` and `write(lines)`, `decode(view)`. `spans(faces, bg,
  capacity, crossings)` is the algorithm itself, with the counts the cost
  model uses and, given the 6502's pool size, its overflow (below).

## The 6502

### Edges, by a DDA

A sloping edge's x steps in 8.8 fixed point from its top vertex, with no
division and no compare a line (Rich Talbot-Watkins's portalc does the
same, `docs/research/rtw-sources.md` 1.5-1.6):

- dy, in sixteenths, is normalised to n·2^s with n in [128, 255], rounded
  up when bits go (`k8` gives the bit length, `nrm` the shifted byte);
- r = 256 + f(n) ≤ 65536 / n, f from a 128-byte table (`recipf`);
- the gradient g = |dx|·r >> (8 + s) and the first line's offset
  g·t0 >> 4 (t0 the line centre's distance below the vertex); an edge no
  taller than a line crosses one line at most, has no gradient, and takes
  its offset as |dx|·t0·r >> (12 + s), since g needn't fit 16 bits;
- X = 16·(x0 - 8) + 255 ± offset, `X += ±g` a line, and the boundary is
  X's high byte.

The products by r are quarter squares, `q(u + f) - q(|u - f|)` a byte, from
a table of `n^2 DIV 4` (n up to 510) that `raster_init` builds, 1K in the
bank's work, so the rasteriser needs nothing of HAZEL or of the maths
track's tables. Each chain's step in each copy of the line loop is a `BRA`
patched to the edge's kind: the 16-bit add, or none for a vertical edge.

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
  `STA abs,Y`, entered at the piece's first whole byte with an RTS planted
  after its last. Y is the line itself: each row's addresses are 8 lines
  back for each row above it. Each row keeps one plant, moved only when a
  piece ends elsewhere, and one extra slot (storing into `rr_scratch`) so a
  plant at the line's end comes out like any other; after it, the row's own
  RTS, which ends a piece to the view's right edge without a plant when the
  row's plant is left of the piece (as Chase H.Q.'s runs end on their own
  RTS, `rtw-sources.md` 3.3). `put_run` *jumps* into the run, whose RTS
  returns to `put_run`'s caller.
- A byte two runs share is `left AND &AA OR right AND &55`, through the
  row's two screen pages (`put_bnd`).
- The background fills each line's remaining gaps, split where the horizon
  crosses the line (`hsplit`, a level horizon a table, a sloping one an edge
  DDA in 16 bits, pinned when it's far outside; an all-sky frame after
  another leaves the table as it was).
- **What the screen already holds.** A line no face touched is background
  from end to end; if the screen being drawn (ACCCON's X) held the same
  background on it last time, it isn't written. `bg_was` keeps split + 1 for
  each screen and line, `bg_sig` the patterns those were drawn in; other
  patterns, or `raster_forget`, forget them. Every skip comes from these
  records; the screen is never read (the sources that read it measured a
  loss, `rtw-sources.md` 6).

## The interface for the frame

- `raster_init` once (it builds its tables, forgets both screens and plants
  the row runs); `raster_forget` whenever something else has drawn on the
  screens; `raster_frame` each frame, with ACCCON's X selecting the screen
  drawn into.
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
- Sections: `RasterCode`, `RasterRuns` (page-aligned), `RasterWork` (per
  frame, and the tables `raster_init` builds) and `RasterState` (frame to
  frame) in one sideways bank, the inputs in main RAM (decision 20). The
  check build's sizes (2026-10-31): code 6,200 bytes, row runs 3,232. The
  slideshow (`src/slides.6502`) puts all four in its bank one after another
  and asserts they fit; they do, with the work's 1K of squares.

## Checks

- The model against its brute force on every scene (and every Driller view):
  faces by edge functions, background by the horizon's cross product. The
  span buffer must give the brute force's image with the exact edges; then
  every edge's DDA must be within a pixel of the exact boundary on every
  line it crosses, and cross the same lines.
- The 6502 against the model (with the DDA), byte for byte, on 148 scenes
  (random convex polygons, Driller-like boxes, and the edge cases the brief
  lists) with the view first set to each expected byte's complement, so
  every byte must be written, and as many writes as the model counts;
  nothing else of either screen may change, and nothing outside the
  rasteriser's memory may be written. Scenes alternate the screens.
- Seven sequences of frames into alternate screens, which keep what was
  drawn: still, panning, pitching, alternating scenes, a recoloured sky,
  empty, a turning horizon. Each frame must equal the model's.
- Mutation testing (2026-10-31, the check on copies of the source with one
  change each, run on the scenes and on Driller's views): 17 changes to the
  DDA's arithmetic (the normalising, its rounding, the reciprocal's special
  case, the shifts, the products' carries, the step), the writer's plants
  and right-edge ends, the chain swap, the line-0 unlink, the horizon's ties
  and the background's records; the scenes catch all of them but one that
  is equivalent (it sends the same cases the same way). Driller's views
  alone miss three more (the horizon's tie, the all-sky table after a
  horizon, a carry the views' products never make), which is why the
  synthetic scenes stay.
- Driller's own entrance views (65, through the whole-view model's render)
  found a bug every synthetic scene had missed: taking out a line's first
  gap branched on the flags of `LDY r_y`, so on line 0 alone a span stopped
  after its first gap. The `top-line` scenes now catch it.

## Measurements

All 2026-10-31, `tools/rastercheck.mjs` (cycles from the call to the return,
less the stub's own), each view drawn into a screen that remembers nothing
(`raster_forget` first), so the background skip never applies.

### Driller's entrance views (the work the game will see)

65 views, faces 2-36 (median 14), edges crossing a line median 34 (15 of
them sloping), face-lines median 238, runs median 278. After the last
round: **min 51,800, median 125,118, mean 141,291, p90 224,082, max
363,191 cycles** for the rasteriser and writer together (a field is
39,936). Median by part: insertion 28,806, writing bytes 28,641, edge
set-up 17,598, runs 13,895, background 11,775, face set-up 8,037, stepping
4,688, rows 4,211, the line loop 3,929, shared bytes 3,182.

### The rounds

Each round on the same 65 views (no horizon, decision 8a), with the cost
model `cycles ≈ a·lines + b·face-lines + c·runs + d·bytes + e·edges` fitted
to them after it (RMS error 5-6% each):

| Round | median | p90 | max | a | b | c | d | e |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Before: the exact edges, as merged | 137,564 | 239,476 | 398,746 | 100.5 | 76.3 | 271.8 | 1.2 | 892.6 |
| Edges by the DDA, reciprocal by table, products by quarter squares | 132,539 | 228,847 | 374,407 | 88.3 | 69.8 | 257.8 | 1.8 | 837.8 |
| The first line's offset from the gradient (one product an edge) | 131,342 | 225,361 | 367,773 | 79.9 | 69.5 | 250.7 | 2.2 | 813.1 |
| Runs: Y the line, no empty-piece test, a lighter replant, right-edge pieces on the row's own RTS | 127,046 | 224,791 | 364,006 | 81.4 | 77.0 | 240.3 | 1.9 | 796.2 |
| Background: an all-sky frame's splits kept; heads and records cleared 8 a pass | 124,796 | 223,146 | 361,588 | 83.7 | 77.0 | 239.7 | 1.6 | 795.2 |
| The rasteriser's own squares (no HAZEL; `|u - f|` by a subtraction) | 125,118 | 224,082 | 363,191 | 84.2 | 76.7 | 241.2 | 1.5 | 806.3 |

Every view writes all 5,408 bytes, so the fit can't tell bytes from lines
(d is near 0 and a takes the bytes); the profile's bytes are 5.3 cycles
each. On the 148 synthetic scenes the last round fits 185.8 lines + 108.1
face-lines + 129.4 runs + 4.0 bytes + 1400.5 edges (9.5% RMS).

A sloping edge's set-up, with the chain's walk to it, costs about 870
cycles in the first DDA round and a vertical one about 200 (the profile's
edge routines over the views' edges); the exact rule's was 450-700 an edge
on average over both kinds.

### Measured and not built

- **Edges shared between faces.** Of the 1,141 sloping edges the views'
  faces have (crossing a line), 219 (19%) have the same two endpoints as
  an earlier face's; the median view has 2. A cache would save about 2 set-ups and cost a
  lookup on each of the 15: not worth it.
- **Vertical coherence.** 74% of face-lines have the same span as the
  face's line above, but what decides the work is whether the line's gaps
  are the same too: a copy-on-write simulation of lines sharing their gap
  lists while they're equal hit 54% of face-lines, and on the busiest view
  715 of 876 missed, each at 8.2 runs, more work than now.
- **Insert first, write once.** Writing each line from its finished
  partition would merge neighbouring pieces of one pattern, but those save
  2% of runs; writing at once stays, made cheaper.
- **A `put_run` for each phase** (the pattern loaded in the copy): about 6
  cycles a face's piece against 16 more a row set-up for the extra patches,
  an estimated 600 cycles a view; not built.

## What's left

- **The budget.** The median view is about 3.1 fields and the busiest 9.1,
  against the coordinator's 40K and 80K. Writing the view's 5,408 bytes is
  27,040 cycles of `STA abs,Y` alone, two thirds of the 40K, before a face
  is inserted; what's per face-line (insertion, its run, stepping, the
  loop: about 215 cycles each) is another 51K at the median. Reaching 40K
  needs work the frame doesn't do, not cheaper work:
  - writing only what changed, from records of the last frame on the same
    screen (lines' runs, as the background's lines are recorded now): a
    still or slowly moving view would write a fraction of its bytes;
  - a routine a line rather than a row (`STA abs`, 4 cycles, and a plant
    that lasts while the line's ends don't move): about 5.4K a view off the
    bytes and most of the replants, but 16K of code, which the bank hasn't
    room for beside the rest;
  - half the lines rasterised, each written twice: an estimated quarter
    off (what's per face-line and the background halve), with half the
    vertical resolution.
- **More of what the screen holds.** Only whole background lines are skipped
  now; the background runs before the first face and after the last, on lines
  whose split didn't move, are the next step, and they need the same records.
