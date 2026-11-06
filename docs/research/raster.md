# The rasteriser and the writer

Stages 8-10 of `docs/engine.md`: faces nearest first into the span buffer,
the background, and the view's bytes. The model (`tools/model/raster.py`,
`writer.py`) is the specification; the 6502 (`src/raster.6502`,
`src/writer.6502`) matches it byte for byte, checked by `make raster`
(`tools/rastercheck.mjs`). Written 2026-10-31 and revised the same day for
the restructure and for four optimisation rounds after it (the rounds
below); every figure was measured that day, as each section says, in
headless jsbeeb (Master) through `tools/rastercheck.mjs`'s
instruction-level profile, unless it says otherwise.

## Running it

- `make raster`: assembles the check build, makes the scenes
  (`tools/rasterscenes.py`, checked first against the model's brute force),
  runs every scene and sequence through the 6502 and fails on any byte that
  differs. Once the whole-view model is in the tree (`tools/model/render.py`)
  it also checks every Driller entrance view (`rasterscenes.py --driller`,
  into `build/raster/driller.json`, never committed). It checks both ways:
  the engine's build in `build/raster` and the other (the painter's or the
  span buffer's, below) in `build/raster-alt`, the same check build with
  `RASTER_OTHER_WAY` defined.
- `node tools/rastercheck.mjs build/raster --verbose` prints each scene's
  cycles by part; `--json FILE` writes them with the model's counts;
  `--scene TEXT` picks scenes; `--scenes FILE` another scene file; `--hot
  FILE` each instruction's cycles and executions by address (the scenes'
  and the sequences'), to read against baron's listing (`baron -v` of
  `build/raster/check.6502`). Every run prints the scenes' cycles as min,
  median, mean, p90 (nearest rank) and max, and the sequences' frames after
  each one's first two (where what the screens hold counts) the same way,
  with their parts.
- The scenes depend on `build/raster/limits`, the 6502's limits their views
  depend on (the pools' size, the patterns', the horizon's), which
  `mk/raster.mk` rewrites only when they change.

## The specification

- **The fill rule.** A face covers a pixel when the pixel's centre is inside
  it; a centre on an edge counts for top and left edges. Per line: every
  non-horizontal edge is crossed by the lines whose centres are in
  [top, bottom) of it, and the face covers [p_left, p_right) of the edges'
  boundaries there. A vertical edge's boundary is the exact one,
  `(x + 7) >> 4`; a sloping edge's is a DDA's (below), which the exact
  boundary `ceil((x - 8) / 16)` (`edge_crossings_exact`) is the measure of.
  A line's span is the `[min, max)` of the boundaries there
  (`face_spans`), whichever chain is left on it: where a face is under a
  pixel wide its two chains' DDAs can cross, each rounding toward its own
  top vertex, so the chain left of the other on one line may be right of
  it on the next.
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
track's tables; or, where the includer names one (`RASTER_SQUARES`), the
same table already in memory: the live disc names the maths' in HAZEL.
Each chain's step in each copy of the line loop is a `BRA`
patched to the edge's kind: the 16-bit add, or none for a vertical edge.

How it's done (`chain_next`, which sets up each edge inline):

- The face's scan works out every vertex's line, `(y + 7) >> 4`, once, into
  `vk` (from `line7`, `(n + 7) >> 4`, and the high byte times 16), and
  takes its top vertex (the first on the highest line: a chain from any
  vertex on that line skips the edges to the others, which cross no line)
  and its bottom line from those bytes. An edge reads its end's line from
  `vk`; vertex indices are absolute, from `f_v0` to `f_vend` mod 256.
- X0's high byte, `(16 x0 + 127) >> 8`, is `(x0 + 7) >> 4`, the vertical
  edge's boundary, by the same table.
- The gradient's shift by 8 + s (5 to 11 on a tall edge) is a jump into
  unrolled shifts of the 24-bit product, up or down to the top two bytes.
- The first line's offset g·t0 >> 4 is (g·T) >> 8 for T = 16·t0: the high
  byte of g's low byte times T and the whole of its high byte's, two byte
  products by the same tables. No shift by four is left.
- An edge that crosses one line still steps once after it, harmlessly (its
  chain takes its next edge, or the face ends, before the x is read again).

### The span buffer

Each line keeps its gaps (what nothing covers yet) as a sorted linked list.
A face's span takes what it overlaps of them, and the pieces it takes are
**written at once**: the faces come nearest first, so a pixel a face takes is
final. A byte a piece shares with a gap waits in the gap (`gh` holds the
neighbours' halves, the left one in `PIX_LEFT`'s bits and the right one in
`PIX_RIGHT`'s) until the gap is filled, so no byte is written twice and none
is read. A line with no gaps is full; faces stop when every line is.

The gaps live in four pools, one for each value of `line AND 3`, each four
fields (gs, ge, gh, gn) of `POOL_FIELD` bytes, nodes 1 to `POOL_NODES`;
node 0 of each is a whole line, `[0, VIEW_W)` with no next, set each frame,
which the background fills a line no face touched with. Line loop copies,
one a pool, keep each pool's fields and each phase's pattern bytes at fixed
addresses. A face-line whose gaps don't fit isn't drawn, and `rs_overflow`
is set, by the model's rule (decision 20). One pool would have overflowed
on ordinary scenes (they peak at up to 460 gaps a frame).

**The pools hold 127 gaps each** (a proposed decision, below), where they
held 254, to make room in the bank for the faster code. Measured
2026-10-31 with the model (the fewest nodes a pool with which `spans`
doesn't overflow, a binary search over each scene): Driller's 65 entrance
views need at most 102 (median 30); of the synthetic scenes and the
sequences' frames, a grid of shared-edge triangles needs 136 and the
diagonal slivers 139, which now overflow, beside two pathological scenes
that overflowed before (330 and 1,040).

### Writing

- Whole bytes go through the row runs: a page a character row of
  `STA abs,Y`, entered at the piece's first whole byte with an RTS planted
  after its last. Y is the line itself: each row's addresses are 8 lines
  back for each row above it. Each row keeps one plant, moved only when a
  piece ends elsewhere, and one extra slot (storing into `rr_scratch`) so a
  plant at the line's end comes out like any other; after it, the row's own
  RTS, which ends a piece to the view's right edge without a plant when the
  row's plant is left of the piece (as Chase H.Q.'s runs end on their own
  RTS, `rtw-sources.md` 3.3).
- The hot paths enter the runs inline: `ENTER_*` puts the piece's first
  whole byte's slot into `put_go`'s jump (whose page `row_setup` patches),
  `PLANT_*` checks the row's plant against the slot after its last and
  calls `replant` to move it, and `GO_V` loads Y with the line and A with
  the pattern byte and calls `put_go`, which jumps into the run; the run's
  RTS returns to the caller. Each takes the piece's ends straight from the
  gap's fields (indexed by X) or from the span (zero page). `put_run` is
  the same as a routine, for the background's split gaps and the painter's
  build.
- A byte two runs share is `left AND &AA OR right AND &55`, through the
  row's two screen pages, stored inline (`BND_X`, `BND_ZP`, `BND_PUT`)
  where it's hot and by `put_bnd` elsewhere.
- Each copy of the line loop is entered (by `segment`) at its `entry`, which
  loads X with the line, and each line leaves X the line for the next.
  Only the paths an empty span can reach (a span inside one gap, a line no
  face has touched) test for one.
- A face whose lines are all full when it comes draws nothing, so it goes
  after the vertex scan, before its patterns and edges are set up (the
  span buffer's build only: a painted face draws over full lines).
- The background fills each line's remaining gaps from the pool's fields,
  split where the horizon crosses the line (`hsplit`, a level horizon a
  table, a sloping one an edge DDA in 16 bits, pinned when it's far
  outside; an all-sky frame after another leaves the table as it was). A
  gap wholly left of the split (every gap when there's no horizon, as in
  Driller's views) is one piece inline; one the split crosses or that lies
  right of it goes through `fill_split`. Copies 0 to 2 fall into the next.
- **What the screen already holds.** A line no face touched is background
  from end to end; if the screen being drawn (ACCCON's X) held the same
  background on it last time, it isn't written. `bg_was` keeps split + 1 for
  each screen and line, `bg_sig` the patterns those were drawn in; other
  patterns, or `raster_forget`, forget them. Every skip comes from these
  records; the screen is never read (the sources that read it measured a
  loss, `rtw-sources.md` 6).
- **A line one face takes whole** (INSERT's fresh path for a span of
  `[0, VIEW_W)`, and the stretch's whole lines) is likewise not written when
  the screen holds it in the same byte: `bg_was` is `LN_WHOLE` for it and
  `ln_v` keeps the byte (the pattern's for the line's phase, not its index,
  so a pattern table changed without `raster_forget`, as the slideshow's,
  can't fool it). The run's entry and plant are still set, as the stretch's
  next lines may need them. A line more than one piece fills has its record
  made 0 where it fills (INSERT's unlink of its last gap), so the
  background's pass leaves a full line's record alone. The records are
  checked against the patterns before the faces (`background_set`), so a
  change of background forgets the lines before the faces mark them. This
  is round 5, below.

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
  frame, the tables `raster_init` builds, and `ln_v`, which lasts from frame
  to frame but is there for the bank's room) and `RasterState` (frame to
  frame), the inputs in main RAM (decision 20). The live disc puts the first
  three in its bank and `RasterState` in main RAM below `&3000`; the
  slideshow (`src/slides.6502`) the same, as its bank, which holds its own
  quarter squares, hasn't room for `RasterState` beside `ln_v`. Both assert
  they fit.

## Checks

- The model against its brute force on every scene (and every Driller view):
  faces by edge functions, background by the horizon's cross product. The
  span buffer must give the brute force's image with the exact edges; then
  every edge's DDA must be within a pixel of the exact boundary on every
  line it crosses, and cross the same lines.
- The 6502 against the model (with the DDA), byte for byte, on 150 scenes
  (random convex polygons, Driller-like boxes, and the edge cases the brief
  lists, one of them with 256 vertices so a face's walk wraps round, one
  whose pools run out in a stretch) with the view first set to each
  expected byte's complement, so every byte must be written, and as many
  writes, shared bytes (the view's bytes written from outside the row runs)
  and runs entered (calls to `put_go`) as the model counts, and as many
  lines left open as the background begins (`nopen`, by which the faces
  stop) as the model has; nothing else of either screen may change, and
  nothing outside the rasteriser's memory may be written. The frame's own
  work (the lines' heads, the vertices' lines, the pools) is poisoned
  before every frame. Scenes alternate the screens.
- Seven sequences of frames into alternate screens, which keep what was
  drawn: still, panning, pitching, alternating scenes, a recoloured sky,
  empty, a turning horizon. Each frame must equal the model's, and a held
  frame must write exactly the bytes the background's records leave
  (`tools/rasterscenes.py`'s `held_writes`, for both builds).
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
- Mutation testing again after the three rounds (2026-10-31, the same
  way): 28 changes to the new code (the vertex lines and X0 by `line7`, the
  edges' walk and its wrap, the shift's jump table, both products' borrows
  and carries, the full-lines skip, node 0, the empty-span tests, the slot
  for pixel 0, the cut's going on, the shared bytes' page, the halves by
  `EOR`, the row check, the background's split and records, `replant`'s
  right edge, `row_setup`'s saved plant and pointer). The scenes catch all
  but one that is equivalent (an entry that loads X with the line it
  already holds); one more doesn't assemble (baron finds `r_rr` read
  before it's written). Three were missed until the check was
  strengthened: the walk's wrap (the 256-vertex scene), node 0's start (the
  poisoned work), and the background's records (the held frames' writes).
  Driller's views alone miss the wrap, the horizon's split and the records.
- Mutation testing of round 4's stretch (2026-10-31, the same way, on the
  scenes and Driller's views): a whole line not counted full, a line with
  a face taken as fresh, no plant or no `row_setup` at a new character row,
  the pool's room not checked, the kinds' bits swapped, the stretch taken
  with one chain sloping, the middle kind's halves swapped. All eight are
  caught; two only once the check was strengthened: the lines left open
  (the first, whose image is the same, as only the early stop is lost) and
  the scene whose pools run out in a stretch (the room), which Driller's
  views never do.
- Round 5's records (2026-11-06, the same way): the whole line held on its
  byte alone (without `LN_WHOLE`), in INSERT's path and in the stretch's; a
  line filled by more than one piece left with its record; and the
  background's pass making every full line's record 0, as before. All four
  fail `make raster`; the second only once the `whole-lines` sequence was
  added (lines whole, then two pieces, then whole again in the first
  bytes), which the other sequences and the live frames never do.
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
round: **min 46,748, median 109,526, mean 122,269, p90 189,141, max
319,467 cycles** for the rasteriser and writer together (a field is
39,936). Median by part (the profile's buckets; the insertion's now holds
its pieces' runs and shared bytes, entered inline): insertion 32,897,
writing bytes 28,642, background 11,002, edge set-up 10,688, face set-up
7,164, stepping 4,688, runs 4,362 (`put_go`, `replant`, `put_run`), the
line loop 3,943, rows 3,660.

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
| The same, measured again with p90 by nearest rank (the rounds below) | 125,057 | 221,578 | 364,050 | 86.5 | 78.9 | 240.7 | 1.5 | 807.9 |
| Round 1, edges: each vertex's line once, absolute vertex indices, X0's high byte by table, the gradient's shift by a jump, the offset by the product; pools of 127 | 119,915 | 211,198 | 346,036 | 74.4 | 82.1 | 230.0 | 2.0 | 599.6 |
| Round 2, runs: entered inline through `put_go`, shared bytes inline, X the line on entry, the empty-span test only where one can reach; the background from the pool's fields | 111,202 | 197,745 | 325,017 | 40.0 | 71.1 | 218.0 | 1.8 | 610.4 |
| Round 3: faces whose lines are all full skipped before their edges; the offset's own products; rows, smaller things | 109,526 | 189,141 | 319,467 | 28.1 | 59.1 | 228.9 | 2.0 | 527.4 |
| The same, measured again (track S, before round 4) | 109,505 | 189,119 | 319,505 | 27.5 | 58.7 | 229.7 | 1.9 | 526.4 |
| Round 4: the stretch (fresh lines under vertical chains) | 110,063 | 183,795 | 319,901 | 31.2 | 52.3 | 240.3 | 1.3 | 506.2 |
| The same, measured again (track Z, 2026-11-01) | 110,161 | 183,995 | 319,720 | 32.2 | 52.8 | 239.8 | 1.3 | 506.1 |
| The chains' order on every line not full (below) | 109,641 | 183,419 | 321,877 | 31.0 | 55.6 | 241.8 | 1.2 | 478.9 |

Every view writes all 5,408 bytes, so the fit can't tell bytes from lines
(d is near 0 and a takes the bytes); the profile's bytes are 5.3 cycles
each, the row runs' own RTS included. The fits' RMS error is 5-6% in every
round. On the 149 synthetic scenes the last round fits 207.5 lines + 88.4
face-lines + 107.3 runs + 4.7 bytes + 1167.2 edges (12.2% RMS).

What each round saved at the median, and where (the profile, a view's
mean over the 65): round 1, 5,142 cycles, nearly all edge set-up (a sloping
edge about 870 cycles to about 600, a vertical one about 200 to about
110, both with the chain's walk); round 2, 8,713, of which about 3,900 the
runs (12 a run: no `STA r_v` and `LDA r_v`, no copies of the ends into
`r_lo` and `r_hi`, no `JSR put_run`), about 1,300 the shared bytes (14
each), about 3,000 the background's gaps (no copies of their fields, no
`put_run`) and the rest the loop's entry; round 3, 1,676, most of it the
skipped faces (two a view arrive with every line full) and the offset's
products (about 30 an edge).

A sloping edge's set-up, with the chain's walk to it, costs about 870
cycles in the first DDA round and a vertical one about 200 (the profile's
edge routines over the views' edges); the exact rule's was 450-700 an edge
on average over both kinds. After round 3 a sloping one is about 550: its
two products are about 75 and 90 with their set-up, and the rest is the
walk, the differences, the normalising, X0, the offset's sign and the
stores and patches.

### Round 4: the stretch (track S, 2026-10-31)

A line no face has touched yet (fresh) takes a face's span by a path of
its own (INSERT's `fresh`): its gaps made outright, the piece written. On
a segment where both of the face's chains are vertical (a box's side under
a level camera, or a face the 2D clip has cut at the view's sides), every
line has the span the line before had, so a fresh line there needs none of
the line loop's work but the nodes and the write: no chain test, no
dispatch, no steps, no entry or plant for the run, which stay as the line
before left them in the character row. `STRETCH` (four copies, one a pool,
as the line loop's) takes such lines one after another from the first
fresh line's own path, while they're fresh; a line with a face goes back to
the line loop, the segment's end to `seg_end`. The span's kind (the whole
line, to an edge, or in the middle) is a byte's two bits (`st_kind`),
tested with `BIT`. It makes the same nodes, in the same order, and the same
writes as the line loop would: the model is unchanged, and the check holds
it byte for byte, writes, shared bytes and runs entered, on every scene and
view.

Measured on the model first (Driller's 65 views, a view's mean): 96.2
face-lines a view are fresh, of which 55.8 continue a fresh line above in
such a segment (31.8 spanning the whole line, 9.9 to an edge, 14.2 in the
middle). After it, over the 65 views (cycles, `tools/rastercheck.mjs`):
55 views faster, by up to 5,921, and 10 slower, by up to 852; all 65 come
to 7,776,446 cycles from 7,946,066. The slower views' fresh lines are
mostly under one vertical chain and one sloping (a floor cut at the view's
left edge): each pays the test for both chains (`sa0 + 1 AND sb0 + 1`,
non-zero when both are `STEP_NONE`, as `STEP_G` is 0) and the jump to it,
about 11 cycles against the 3 of the jump it replaces. Keeping a flag for
"both vertical" where the steps are patched cost more, at every edge, than
it saved. The median view moves by little either way: the median above is
a different view's.

### The chains crossing (track Z, 2026-11-01)

The live disc's check, with the jet's scenario, found a frame one byte off
the model's (journal, 2026-11-01): a sliver less than a pixel wide over
the right edge of the face behind it, whose chains' DDAs part one way and
then, lower down, cross, each rounding toward its own top vertex. The
6502 took the order the chains first parted in for the whole face (the
line loop's `CHECK`, patched out once it had decided) and drew nothing
where they had crossed, where the model's `[min, max)` draws a pixel. Had
they first parted the wrong way round, the face would have lost every
line but those. The model is right (its `face_spans`, and the fill rule
above); the 6502 now swaps the chains wherever a line finds them crossed:
a line with gaps and a face already tests (`LDY r_b : CPY r_a`) before
walking its gaps, a fresh line's empty test does it at no cost, and the
painter's `PAINT` likewise (`swap_chains`). The patched `BRA` that every
line paid goes. `make raster`'s scenes `crossing-chains` (after parting),
`crossing-chains-first` (first parting the way most of their lines don't)
and `crossing-chains-shared` (over the edge behind, as the frame) fail
the old code on both builds. Over the 65 views (the table above): all of
them 7,761,617 cycles from 7,770,109.

### Round 5: lines the screen holds (2026-11-06)

Every measurement above draws each view fresh. The disc doesn't: each
frame goes into the buffer that holds the frame two before, and in play
that one mostly looks the same. Measured on the model over the live
check's frames in order (eight of the logic disc's scenarios, about 1,240
frames after each one's first two), against the frame two before: walking,
66% of lines and 93% of bytes the same; turning, 69% and 91%. Most of those
lines are one run: the sky, which the background's records already skipped,
and the floor, one face across the whole line. Recording, for each screen
and line, the line's write events in order and skipping one whose record
matches at the same place, one event a line takes nearly all there is to
take (walking 69.7 events a frame, with every one a line holds 80.0;
turning 71.7 against 73.7), and of one-event lines the ones one face takes
whole are 26.7 a frame walking and 52.9 turning (1,388 and 2,752 bytes).
So the records say only that (above, "What the screen already holds"): a
byte for each screen and line, `ln_v`, in the fill's bank, and a test where a fresh line is taken
whole (INSERT's path and the stretch's).

Measured (cycles, `tools/rastercheck.mjs`):

| | before | after |
|---|---|---|
| Driller's 65 entrance views, each fresh: all / median / p90 / max | 7,761,617 / 109,641 / 183,419 / 321,877 | 7,820,772 / 109,796 / 184,644 / 322,585 |
| the live frames in order, after each sequence's first two (291, six scenarios): median / mean / p90 / max | 75,803 / 90,730 / 149,332 / 321,763 | 68,936 / 79,444 / 142,190 / 322,471 |
| ... the bytes' share | 30.9% | 21.0% |

A view drawn fresh pays the test and the record on each line taken whole,
0.8% in all. On the discs (fields a frame, median / p90 / max), the fill
on the logic's disc: walking 1.15 / 2.72 / 8.29 to 0.85 / 2.5 / 8.29,
turning 1.15 / 2.84 / 7.46 to 0.83 / 2.73 / 7.46, standing 3.49 / 3.52 /
5.3 to 3.26 / 3.3 / 5.3, entrances 2.82 / 4.68 / 8.33 to 2.83 / 4.7 / 8.34;
flip to flip, walking a median 2.41 to 2.0, turning 2.97 to 2.51. The free
camera's tour, the fill a median 4.83 to 4.69; the slideshow, whose views
are held, `raster_frame` a median 96,678 to 83,187 and 2.49 fields a frame
to 2.16.

What's still written though the screen holds it, on the same frames after
the skip (the model, a frame's mean): 1,754 bytes written on 33.7 lines,
1,350 of them the same as the screen's; 612 of those lie in the line's
first run of last time and 563 in its last, mostly the floor beside an
object that moved. Taking those would need each line's first and last runs
recorded for each screen, and since a frame's pieces on a line come in the
faces' order, not the line's, the old record is still wanted after the new
one is known: two sets for each screen, about 1K besides `ln_v`, against
the bank's room, for an estimated 3K cycles a frame less the trimming's
test on every piece. Not built.

### Measured and not built

- **Faces' lines already full** when the face comes, which its line loop
  still steps through (2026-11-06, the model on Driller's views, a view's
  mean): 2.6 before its first open line, 8.1 after its last, 0.6 between,
  of 296 face-lines. Starting a face at its first open line would need its
  edges' x there (a product an edge); not worth it.
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
  an estimated 600 cycles a view; not built. (Round 2's inline runs do it
  and more.)

Measured in the rounds after the restructure (2026-10-31, the model's
spans over Driller's 65 views unless it says the profile; a view's mean):

- **Two plants a row.** Of 324 runs, 92 move the row's plant and 39 more
  are right-edge pieces that end on the row's own RTS. Keeping two RTSs a
  row, a run fine when its end is planted and neither is in its way, would
  take 129 stores against the 184 of 92 moves, saving about 450 cycles, but
  every run's check would cost about 10 more: not built. Moving the plant
  for every right-edge piece instead of ending on the row's own RTS would
  make 127 moves: the special case stays.
- **The last face into the background.** With no horizon, nothing after
  the last face reads the gaps but the background, which could fill each
  gap as sky, the face's span, sky, so the last face would need no
  insertion. It has 37 face-lines and 44 pieces a view (14% of each): about
  2,900 cycles of insertion saved against about 1,300 more in the
  background's three-way fill, an estimated 1,600; it changes the pools'
  accounting (the model's overflow) and the background's code a good deal.
  Not built.
- **A line's first face kept compact** (its span, with no nodes, until a
  second face comes): 45.6 lines a view have one face, so at most about
  1,600 cycles of node-making, less the second face's conversion. Not
  built.
- **Faces that draw nothing.** 3.7 a view, with 27 face-lines and 7.5
  edges; 2.0 of them arrive with every line they could cover full, and
  those are skipped now (round 3). The rest need their spans to find out.
- **Skipping both steps** when both chains are vertical (one patched `BRA`
  over the two): 3 cycles on about 150 face-lines, against patching both
  chains' BRAs at every edge; a loss once the patches are counted.
- **The background without a horizon** (the gaps' split test patched out a
  frame): about 500 cycles against eight patches; not built.
- **X the line and Y the node through the insertion**, the row runs by
  `STA abs,X`: saves the walk's `TAX` and the unlink's `LDY r_y`, about 5
  cycles a face-line, but the runs' lookups need X, the shared bytes Y and
  `replant` both; not built.

Measured in round 4 (track S, 2026-10-31; the model's spans over
Driller's 65 views and the profile, a view's mean):

- **Objects rather than faces** (inserting each object's silhouette once a
  line, the round 3 estimate below). Of the face-lines that search a
  line's gaps (172.8 a view), 40.8 have a span touching the face before
  them's on the same line, as a box's faces do across a shared edge:
  those are the searches grouping by object would save, about 44 cycles
  each (the walk and its tests), under 2K a view before the grouping's own
  cost (each object's spans gathered a line, merged, and split again at
  its inner edges, which still need their own runs). Not built, and
  `RasterIn` is unchanged.
- **A line with one gap left.** Of the face-lines meeting a line with gaps
  (11,235 over the views), 34% find one gap, 43% two and 23% three or
  more; the span meets one gap in 71% and none in 17%. The insertion on a
  one-gap line is already its walk's first test and the case's (about 38
  cycles before the piece), so a path of its own has little to take away.
- **Where a face-line's cycles go** after the four rounds, at a view's
  mean: the gaps' walk and its tests about 44 cycles, a piece's entry,
  plant check and call about 45 more (with a replant on 29% of runs, about
  40), and the line loop's steps, check and next line about 25: what's
  left is mostly per piece and per line, and the 5,408 bytes' 27,040
  cycles of `STA abs,Y`.

### A column fill, priced (track U, 2026-11-01)

The fill down the screen's byte columns, PORTAL's and lander's way, with
this fill's picture: modelled exactly (`tools/model/colfill.py`), its work
counted, priced from 6502 kernels timed in jsbeeb
(`src/colfill-kernels.6502`, `tools/colfillprice.mjs`, `make colfill`) and
compared view by view with this fill's measured cycles
(`docs/research/colfill.md`). Over Driller's 65 views it's priced at a
median of 123,467 against this fill's 110,119 (p90 183,240 against
183,995, max 269,828 against 319,926), and over 738 live frames 89,837
against 75,016. Down a column a dithered pattern's byte changes every line,
so each store needs a load (8 cycles a byte against the row runs' 5), and
Driller's faces are wider than they are tall, so working a byte column at a
time saves only a third of the units of work. Not built.

## The painter's way

Built and measured 2026-10-31 (`RASTER_PAINTER`, the comparison build).
The view is the same, since painting back to front is the original's own
algorithm and the span buffer only reproduces it: `raster.painter` must
give the span buffer's bytes on every scene, and the 6502 must match them
byte for byte, with the model's count of writes.

- The backmost face (the input's last) and the background go through the
  span buffer as before, so every byte is written once; the pools need
  only a quarter page a field for one face's gaps, which leaves the
  painter build 3K smaller.
- The other faces are painted back to front: the line loop's copies jump
  (a `JMP` patched for the frame's two phases) to `PAINT`, which writes a
  span's whole bytes through the row run and reads, merges and writes back
  the byte at each odd end. A line a painted face spans is no longer
  background alone, for the screen's records.

Measured over Driller's 65 views, each drawn fresh (`tools/rastercheck.mjs`):

| | median | p90 | max | bytes written (median) |
|---|---:|---:|---:|---:|
| Span buffer | 125,406 | 224,523 | 364,241 | 5,408 |
| Painter's | 135,039 | 224,936 | 324,093 | 8,941 |

and in the slideshow (`tools/slidecheck.mjs`, each view held, the median
over views of each view's median frame): span buffer 124,983 / 225,102 /
366,124, painter's 135,245 / 225,429 / 325,189. At the median the
painter's writes 3,533 bytes more (every byte of a painted face is written
over the floor or the sky first), 18,335 cycles more of row runs, and
saves 13,200 in insertion; on the busiest views insertion is the larger.
The painter's is faster on 30 of the 65 views. Painting a view's faces
when they span more than 500 face-lines, and the span buffer otherwise,
would give 125,406 / 221,477 / 324,093; the better of the two on each view,
122,691 / 221,477 / 324,093.

The span buffer stays the engine's way: it's the faster at the median and
the same at p90. The painter's stays buildable and checked.

- **The background's restore.** Faces touch every line of at least half
  of Driller's views (and of the 90th percentile's), so the records' skip
  seldom applies to them. Restoring the
  background only over each line's hull (in whole bytes) of what the frame
  two back drew, then painting every face, would write median 9,535 bytes
  a held view, max 15,094, against 8,941 and 13,951 as built, because the
  backmost face is then painted over the background rather than written
  with it (`raster.painter`'s counts and a model of the hulls, 2026-10-31).
  Not built.

## Decisions to record

- **The span buffer's pools hold 127 gaps each, not 254** (proposed
  2026-10-31): room in the rasteriser's bank for the inline runs and the
  edges' tables. Driller's entrance views need at most 102 (median 30);
  two synthetic scenes beside the two pathological ones now overflow, and
  a face-line that doesn't fit isn't drawn, as decision 20 has it, in the
  model and the 6502 alike (above, "The span buffer").
- **Lines one face takes whole aren't rewritten when the buffer holds
  them** (decision 70, 2026-11-06, amending 20): round 5's records. The
  picture is the same; the model's `held_writes` counts the bytes it
  leaves.

Nothing else in the rounds changes the picture or the model's method:
the 6502 matches `tools/model/raster.py`'s rule as it was, byte for byte.

## What's left

- **The budget.** Round 4 took the mean over Driller's views down by
  about 2% and the median not at all; the design's floor (below) stands.
  After the three rounds the median view is about 2.7
  fields and the busiest 8.0. Writing the view's 5,408 bytes is 27,040
  cycles of `STA abs,Y` alone. What the rounds left, at the median, is
  close to what this design costs: a run about 50 cycles to enter and
  leave (the slot's patch, the plant's check, the line, the pattern, the
  call), a plant's move about 40 more (on 29% of runs), a face-line about
  90 of insertion besides its runs, and 20 to 40 of stepping and the loop,
  a sloping edge about 550 and a vertical one 110. Summed at the floors
  each of those could reach (runs 45, insertion 70, edges 400 and 100),
  the median view would be an estimated 90-95K; a median of 60K would need
  a face-line of about 40 cycles in all, which the gap lists' walk and
  bookkeeping alone exceed. Round 3 found little, so the rounds stop here.
  Further, the frame has to do less:
  - objects rather than faces: a box's faces don't overlap and share
    their edges, so inserting its silhouette once a line and splitting the
    pieces at its inner edges would take one insertion a line where it
    takes two or three now, an estimated 8K at the median; it needs the
    faces grouped by object with their shared edges, which `RasterIn`
    doesn't carry;
  - writing only what changed, from records of the last frame on the same
    screen (lines' runs, as the background's lines are recorded now): a
    still or slowly moving view would write a fraction of its bytes;
  - a routine a line rather than a row (`STA abs`, 4 cycles, and a plant
    that lasts while the line's ends don't move): about 5.4K a view off the
    bytes and most of the replants, but 16K of code, which the bank hasn't
    room for beside the rest;
  - half the lines rasterised, each written twice: an estimated quarter
    off (what's per face-line and the background halve), with half the
    vertical resolution;
  - not a column fill: priced slower at the median (above, and
    `docs/research/colfill.md`).
- **Both ways in one build**, chosen a frame by the faces' line ranges
  (the figures above): about 40K off the busiest view; it needs the span
  buffer's pools and the painter's code in the bank together.
- **More of what the screen holds.** Lines of one run, the background's or
  one face's, are skipped now (round 5); what's left of the bytes the
  screen holds is mostly in the first and last runs of lines of more than
  one, which want room (round 5, above). A view the same as the one its
  screen holds (the crosshair moved, the camera still: the live check's
  standing frames, 3.26 fields of fill a frame and 1.91 of the stages
  before) could skip both halves, but only the live loop knows that its
  inputs are those of two frames before (`lv_inputs` compares the last
  frame's).
- **Priced for Matt, not adopted** (2026-11-06, from the fresh views'
  profile): half the vertical resolution, each line rasterised once and
  written twice by row runs that store both lines' bytes (`STA a,Y : STA
  a+1,Y`, the same 5 cycles a byte), would halve what's per line and per
  face-line (insertion, the stretch, the steps, the runs' entries, rows and
  the line loop: 51% of the fresh views' cycles) and part of the
  background's, an estimated 28% off a fresh view, less on the frames round
  5 helps; constant dithers line to line save the row fill nothing (each
  phase's byte is loaded once a run either way), though they would bring a
  column fill's byte to 5 cycles (`colfill.md`), about 10K off its median
  price, still above this fill's.
