# The object pipeline in 6502: records, matrix, object pass, transform, clips and sort

*Track H, 2026-10-31. Stages 1 to 7 of `docs/engine.md` in 6502
(`src/area.6502`, `matrix.6502`, `objects.6502`, `transform.6502`,
`clip.6502`, `order.6502`), the area records they read
(`tools/mkareas.py`), and the check that holds every stage to the model
(`tools/objectcheck.mjs` on `tools/objectcases.py`). The model
(`tools/model/`) is the specification; where this file and the code
disagree, the code is right and this file gets fixed.*

Tags as in `model.md`: **[measured]** means `make objects` (or `make
objects-nocache`) on 2026-10-31 with the build of that day;
**[counted]** means cycles added up from the code, not run.

## Running it

```sh
make objects          # the records, the check build, and the check: every stage, every case
make objects-nocache  # the same with the transform's cache off (the measurement below)
node tools/objectcheck.mjs build/objects --entrance --profile   # the entrance views and their
                                                                # walks, cycles by routine
node tools/objectcheck.mjs build/objects --entrance --profile-walks   # the walks' steps alone
```

`make objects` needs `make colours` and the maths' tables (`make maths`'s
`build/maths/`), which its rules build. It fails if any stage of any case
differs from the model, or if the pipeline writes outside its own memory.

## The records (`src/area.6502`, modelled by `tools/mkareas.py`)

The stages read an area's objects from one **working copy** (`ObjArea`),
which `area_enter` builds as the area is entered, on the BBC, from the
records of Driller's own database: the ZX's bytes in the original's
layout, at the top of the player logic's bank (`LOGIC_BANK`, `LOGIC_DB`:
`logic6502.md`), where the logic walks them too. Nothing per area is
precomputed. `tools/mkareas.py` is the model of what it builds, from
`build/data/driller.json`, into `build/gen/` (nothing of Driller's is
committed): `areas.6502` for the assembler, `areas.json` with every area's
working copy for the check.

- **A slot an object**, structure of arrays, so every array has one
  address and the stages index it with `abs,X`: the globals in the first
  `G_OBJ` slots, built once by `area_init`, and the area's after them. Only
  objects the model can draw get a slot (`objects.shape()` isn't `None`);
  the object pass walks the area's slots and then the globals', which is
  the model's order with the undrawable ones left out.
- **Kinds** (`ob_flags`' low bits): a cuboid (its box: vertex i has bit k
  set for the high side on axis k), a rectangle (its box and its zero axis,
  `ob_aux`), a generic object (pyramids, polygons, lines; its vertices'
  cells in `gv_*` from `ob_aux`) and a sensor (a point at its box's corner;
  `ob_aux` indexes `sn_*`). `F_LINE` marks a line; `F_HIDDEN` the
  initially invisible.
- **Everything compared is a byte.** Positions are cells (world position
  over `CELL`); the boxes for the coarse cull (`ob_bl*`, `ob_bh*`, the
  bounds) and for the sort (`ob_l*`, `ob_h*`, the header box) are cells.
- **Each face** (`fa_*`): its colour; its loop, an offset into one table
  of loops shared by every area (`lp_table`, in `ObjConst`); the mask of
  its object's vertices it uses; and its test (`fa_test`, `fa_tval`):
  - an **axis test** for a face in a plane x, y or z = P: seen from below
    when the camera's floor cell f < P (`T_AXLO + 2 axis`, tval P), from
    above when P < its ceiling cell e, stored as 255 − e < 255 − P
    (`T_AXHI + 2 axis`), so both are `thr[test] < tval`, one compare;
  - a **plane test** (`T_PLANE`, tval the plane's index in `pl_*`): the
    reduced normal's two non-zero components (every slanted face in Driller
    has two) and a point of the plane on those axes;
  - `T_ALWAYS` for a line and a sensor's point.
- **`ob_ix`**: each slot's place in the logic's index of the area's objects
  (`ix_*`: the area's records, then the globals'), which says where its
  flags are when the logic is there (below).

**How it's built.** For each record in turn, area by area in the
database's order (`DB_AREAS`, the database's table of areas): its fixed
part is read into `rec` by `area_record`, in main RAM (`AreaCode`) so that
it can page the database's bank in; the conversion itself (`AreaConv`) can
sit in any bank. It does what `objects.shape()` does, in bytes, but in
three places, each of which `mkareas.py` asserts on every object, so a
database it couldn't convert fails the build with the reason:

- a slanted face's plane is the cross product at its loop's first corner,
  (v1 − v0) × (v2 − v1), whose edges are signed bytes, reduced by the
  greatest common divisor of its two non-zero components (Stein's way, and
  a division by shifts), not Newell's normal over the whole loop;
- a pyramid's side loses its apex corner when the apex edge has shrunk to
  a point, and its apex face goes when any apex edge has, rather than
  removing repeated corners in general;
- every loop is one the conversion finds by a constant: `lp_table` holds
  them in a fixed order (the cuboid's face f at 4 f, a polygon's forward
  and backward, a pyramid's sides whole and shrunk, its base and apex),
  and `mkareas.py` refuses a loop that isn't one of them.

**What isn't in the ZX's database** comes from tables `mkareas.py`
generates from the originals into `AreaConv` (decision 6): each face's
colour in the version the colours follow (`render.recolour`, decision 8),
as a stream of colour bytes for each area and the globals, in the records'
order and layout, which the conversion takes in place of the records' own;
and the globals' records as the tape has them, for a build without the
logic, which keeps its own (`AREA_GLOBALS`: the logic's `Globals`).

**The logic's flags** (`OBJ_LOGIC`, a build option). Without it the object
pass skips a slot whose `ob_state` has bit 7 set, as the data first has
them. With it, the pass reads the logic's `ix_flags` at the slot's `ob_ix`
(bit 6 invisible, bit 5 destroyed, as `logic_go_shown` copies them) and
`area_enter` builds the globals' slots again too, since the logic moves the
rig's parts as an area loads (`place_rigs`).

**Checked** by `tools/areacheck.mjs` (in `make objects`): the globals'
slots after `area_init`, then every area after `area_enter`, with the
working copy past the globals' filled with junk first, against
`mkareas.py`'s, byte for byte; the build's `AREA_DB` and `AREA_DB_BANK`
against the logic build's `LOGIC_DB` and `LOGIC_BANK`; nothing written
outside the working copy and `ObjWork`; and the same on the `OBJ_LOGIC`
build. It reports the cycles of `area_init` and `area_enter`. The sizes and
cycles are in the journal (2026-10-31, "area records from the logic's
database").

## Cells (stages 2 and 7)

With c the camera's coordinate on an axis, f = c DIV 64 and e = −(−c DIV
64) (each clamped to a byte; cells are below 255): a corner 64 L is above
the camera (the model's L − c > 0) when f < L, below it (< 0) when L < e.
So the side bits, the cuboids' and rectangles' faces, the coarse cull
(H ≤ f, L ≥ e) and every compare of the sort are byte compares on cells
(`camera_setup`). The coarse cull's thresholds are set once a frame from
the matrix's ahead row, so an object's cull is six compares against them.

## Stage 1: the matrix (`src/matrix.6502`)

`M = Rroll (Rpitch Ryaw)` from the original's sine table, the model's
composition and rounding: written out, the first row of `Rpitch Ryaw` and
the last of M are exact, and the rest is 14 byte products by quarter
squares (a 129-entry table), each sum rounded `(v + 32) >> 6`. Built only
when an angle changes (`matrix_update`). Checked on 8,472 angle triples
(every yaw at every pitch, every roll at four of those, and 3,000 random)
and on every case [measured]: 1,620 cycles a build, 44 when the angles
hold.

**An entry can be 65.** Rounding lets `M`'s entries reach ±65 in 896 of
the 373,248 orientations [measured, the model's `compose` over all of
them]; `mat_big` marks those (see the transform).

## Stage 2: the object pass (`src/objects.6502`)

For each slot: hidden (`ob_state` bit 7, the logic's) skips it; the coarse
cull is six byte compares; a sensor's watching test is the model's
(`sensor_watching`: side bits and the Manhattan distance); then each face's
test, one compare (a plane's: the two terms' signs settle most, else two of
the maths' `mul`). The candidates go into `cd_obj` (slots in order),
`cd_mask` (bit j: face `ob_f0 + j` seen) and `cd_vmask` (the vertices those
faces use).

7,051 cycles at the median entrance view, 17,990 at the most [measured].

## Stage 3: the transform (`src/transform.6502`)

`V = M (v − c)`, exact, 24-bit, as `M v − M c`:

- **M c** once a frame: by the maths' `dot3` a row at a time; or, while the
  matrix holds (`matrix_build` clears `mc_valid`) and the camera has moved
  under 64 units on each axis (a step), the last M c plus M times the move,
  a byte product (`mmul`) a non-zero term. Nothing is rounded, so the two
  are the same.
- **An object's cache**, filled when it's first transformed under an
  orientation: for a box, `M` times its low corner and times each of its
  edges (four vectors, three for a rectangle); for a generic object or a
  sensor, `M v` for each vertex. Slots are handed out in order and all
  taken back when the orientation changes (`cache_reset`: a stamp's
  increment, and a clear of the stamps when it wraps) or they run out.
- **A box's vertices** from the corner: `V0 = C0 − M c`, then each wanted
  vertex its parent plus an edge (7 from 3 from 1 from 0, 5 from 1, 6 from
  2): one 24-bit vector add a vertex, only for the vertices the seen faces
  use and those they're built from.
- **The products** are all 64 u m for a cell u (0-127) and an entry m of
  M: by quarter squares, `f64(u + 64 + m) − f64(u + 64 − m)` from a
  768-byte table of 64 (n² DIV 4), both indices bytes: three byte
  subtractions a product. The fills skip a zero cell or a zero entry (a
  level camera's matrix has four). An orientation with an entry of ±65
  (`mat_big`) would run the table's index off its end for a cell of 0 or
  127, so its fills use the maths' `mul` instead.

**Does the cache pay?** Matt asked (via the coordinator) for the cached
form against a straight per-frame transform. `make objects-nocache` builds
the same pipeline with the cache emptied every frame, so every object's
corner and edges are made afresh; the check holds both to the model. Over
the 65 entrance views, each reached by a turn, and the four-step walks
from them, each a step with the angles kept [measured]:

| transform, cycles | turn: median | max | step: median | max |
|---|---:|---:|---:|---:|
| cached | 40,054 | 71,734 | 13,889 | 23,462 |
| afresh every frame | 42,579 | 71,734 | 42,580 | 71,734 |

So the cache saves about 28.7K cycles on every frame that only moves, two
thirds of the stage, and costs nothing on a turn. Its memory is 2,304 bytes
(nine 256-byte arrays) and two bytes an object (stamp and slot); its
bookkeeping is a compare an object, a slot allocation a fill, and a stamp's
increment a turn. **It pays its way: keep it.**

The original's own form, `M · (v − c)` on 16-bit relative coordinates, is
dearer here by the maths' figures (`maths.md`: `dot_set` 353, `dot3` 329
cycles): about 2K a box's corner by three rows of `dot3` [counted], against
nine quarter-square products of about 50 each and the subtraction of M c.
It wasn't built.

## Stages 4-6: the faces (`src/clip.6502`)

Each candidate as `render.draw_faces` takes it since the third round (track
M, below). A polygon object's vertices go first, then its faces:

- **The vertex pass** (`vertex_pass`). Each vertex the seen faces use is
  tested once against the band the projection takes (`band_test`, the
  model's `clip.projectable`): in front of `ZNEAR`, x within 2^(n + 3) and y
  within 2^(n + 2), n the bit length of z, as two's complement, so a byte or
  two of each coordinate against tables indexed by n (`band_*`), and z's
  top two bytes for the near plane (`ZNEAR` is 256, ASSERTed), inline in the
  pass (`BAND_TEST`). The band is inside the guard band (the model asserts),
  so everything decision 17 bought still holds. Then each vertex of a face
  with no vertex off the band (every vertex used, when none is off) is
  projected once (`vertex_shared`), in an order for the object's kind
  (`vp_order`: a cuboid's vertices i and i + 2 share x and z under a level
  camera, so do a rectangle's along y) that lets `project_y` and
  `project_z` take a vertex sharing the last one's x and z, or z, with its
  outcode against the view (a `project_y` vertex's x part the last one's).
- **A face projected whole** (`poly_face`): its vertices go straight into
  the output (`out_v*` from `out_vn`) as they're gathered, with their
  outcodes' AND, which drops it, and OR. Wholly inside, and with no vertex
  the one before it again (the first against the last), the drawn test
  takes them there and `commit` records the face; else they go to `pa` for
  the 2D clip, or for `dedupe`, and are staged back (`stage_pa`). A cone's
  polygon and a line's take the same `stage_pa`, `drawable` and `commit`.
- **Any other polygon: the cone** (`cone_face`, the model's
  `clip.cone_clip`). Every vertex in one of the half-spaces x < −z, x > z,
  2y > z, 2y < −z, z ≤ 0 (`vertex_code3`, each a 32-bit sum's sign; each
  misses the view's pyramid wherever the point is) drops it; the AND stops
  once it's 0. Else each edge's
  plane through the eye (`edge_normal`) becomes a line on the screen
  (`edge_line`), kept if it cuts the view's rectangle, and the rectangle is
  clipped by each kept line in turn (`cone_pass`, Sutherland-Hodgman, its
  crossings as the 2D clip's). The face's loop winds anticlockwise about its
  outward normal (every loop does, `objects.shape`), so its inside is where
  (A × B) · r ≤ 0 for each edge A → B and every ray r through it, and the
  rectangle clipped by all its edges' planes is exactly its image: no near
  plane and no guard band, a pyramid from the eye as the original's.
  - A box's edge runs along a world axis k, so B − A is a multiple of M's
    column k and the plane is ± A × M[:, k]: each non-zero entry c of the
    column gives two terms, A's coordinates by c, so c is patched into the
    quarter-square reader once for both (`en_mul`: a signed 24-bit
    coordinate by a byte, its raw top byte's excess taken off), and an entry
    of ±64 is a shift (`en_shl6`; a level camera's column for y is (0, 64,
    0)). Any other edge's is cut16(A) × cut16(B − A), 16-bit products.
  - The normal is shifted right until it fits `LINE_BITS`, N' (one bit
    length for the three components, then their 16-bit windows shifted
    together), and the line is f(x, y) = A x + B y + C, A = −2 N'x, B =
    N'y, C = P − Q − R, P = 2 XC N'x, Q = YC N'y, R = 2 FX N'z, by
    quarter-square products by 13 and 61 in the instructions on the raw
    bytes (2 XC = 128 × 13, YC = 64 × 13, 2 FX = 8 × 317, ASSERTed). The
    line keeps f at the rectangle's corners, ±P ± Q − R (`lfc`), which
    decides whether it cuts and stands for a corner's f in the passes.
  - Each of the clipped polygon's vertices is tagged with the rectangle's
    sides it's on (`pa_tg`, `OC_*`; a crossing gets its ends' sides in
    common), so a pass's f at a vertex (`cone_eval`) is a corner's own, a
    side's corner f plus one product (A x along the top and bottom, B y down
    the sides), or two products inside; every way gives the same f.
- **A line's face, or a point's** (`draw_segment`): with an end off the
  band, a point isn't drawn and a line is clipped in 3D to `ZNEAR` and the
  planes x = ±z, 2y = ±z, by crossings from the inside end (`seg_clip`, the
  model's `segment_clip`), after which both ends are in the band; then
  projected, wholly beyond one edge dropped, widened (`line_quad`,
  `point_square`) and clipped in 2D.
- **Crossings** (decision 24: `frac16`, `lerp`): one fraction t from the
  edge's inside end, f_P / (f_P − f_Q), both shifted right until the
  difference fits 16 bits (by the difference's bit length: whole bytes,
  then the rest right, or the other way left and a byte down), then sixteen
  unrolled steps; `frac16` patches t's bytes into `lerp`'s quarter-square
  readers, and `lerp` takes the size of P to Q (up to 24 bits) by them,
  rounded half up.
- **The 2D clip** is 16-bit (inside the band everything projects within
  the guard band's range), and runs only the passes for edges a vertex is
  beyond; the four passes are one routine (`clip_pass`) taking the side's
  axis as offsets into the coordinates' arrays.
- **The drawn test** (`clip.drawable`, on the polygon staged in the
  output): three vertices or more, one off the line through the first two,
  decided by the products' signs and zeros where it can be, then by the
  sizes' order (|dx| > |dy| and |ey| > |ex| make dx ey the larger, and the
  other way about), else by two 16 × 16 products.

## Stage 7: the sort (`src/order.6502`)

The original's bubble sort, the model's `compare_axis` case for case, on
cells: each draw-list entry's box and its side of the camera (across, below,
above) on each axis, so a compare is byte compares on two index registers.

A compare depends on nothing but the two boxes and each box's side of the
camera on each axis (L ≥ e above, H < e below, else across, e the ceiling
cell), so its verdict (keep or swap) is remembered by the pair of slots
(`so_memo`, a byte a pair: the generation shifted left one, OR keep), under
a generation (`so_gen`) that moves on when a ceiling cell moves past some
slot's L or H on its axis (any slot's, since the memory keeps every pair's);
a cell that moves past none leaves every side, and so the memory, as it
was. When the generations run out the memory is cleared. A frame reads a
pair's verdict from it when it has it, through each draw-list entry's row
of the memory (`dl_rl`, `dl_rh`, found once a frame), with a pass's place
in a register, and works out the entries' keys only when it doesn't. A turn
keeps the cells, so a turning frame's compares are remembered; so is every
repeat of a pair within a frame. `cache_reset` (a new area, or an object
moved) clears the memory (`sort_forget`); `cache_empty` (a new orientation)
leaves it.

## The output: what the rasteriser reads

Faces nearest first, in the rasteriser's input's shape
(`docs/engine.md` section 9; `src/raster.6502`'s `rs_*`), section `ObjOut`:

- `out_nf` faces; face f has `out_fn,f` vertices from `out_fv,f` and colour
  index `out_fc,f` (1-15; the glue maps it to a pattern);
- vertex v at (`out_vxl/out_vxh,v`, `out_vyl/out_vyh,v`), view coordinates
  in sixteenths, 16-bit, inside the view after the 2D clip;
- `out_over` set if a frame's faces or vertices didn't fit (128 and 256).

## Interfaces

| Entry | Does | Inputs | Outputs | Clobbers |
|---|---|---|---|---|
| `area_init` | the globals' slots built, once | | the working copy's first slots, `ob_n`, `ob_state` | A X Y, the cache; pages and restores the bank |
| `area_enter` | an area's slots built (and the globals' again, with `OBJ_LOGIC`) | A: its index in the database's table of areas | the working copy (`ob_ix` too), `ob_n`, `ar_counts`, `ob_state` | A X Y, the cache; pages and restores the bank |
| `objects_frame` | stages 1-7 | `cam_x/y/z` (16-bit, below &8000), `cam_yaw/pitch/roll` (0-71) | `out_*`; also `mat`, `cd_*`, `dl_*`, `tf_*` | A X Y, its zero page |
| `cache_reset` | every cache emptied, and the sort's memory cleared | | | A X Y |
| `cache_empty` | the transform's cache emptied | | | A X |

- **Paging**: `area_init` and `area_enter` are called with the pipeline's
  bank in, page in the conversion's (`AREA_CONV_BANK`) and, a record at a
  time, the database's (`AREA_DB_BANK`), and restore `romsel` and its copy
  at &F4; the maths' tables readable throughout `objects_frame` (HAZEL in
  the engine: ACCCON's Y); the working copy and the work areas never in
  `&3000-&7FFF` while the screen's X bit is set, nor in sideways RAM.
- **The logic** hides and shows by `ob_state`'s bit 7, or, with
  `OBJ_LOGIC`, by its own `ix_flags` at each slot's `ob_ix`; it finds slots
  by `ob_id`, and must call `area_enter` again after loading an area (the
  rig's parts move) and `cache_reset` if it moves an object otherwise.
- **Sections** (each placed by the build's memory map; the check build's
  in `mk/objects.mk`): `ObjCode` (this track's code, and the vertex pass's
  and the cone's tables), `ObjConst` (the loops, the sine table, the
  matrix's quarter squares), `ObjTables` (the transform's f64 table, page-aligned in HAZEL),
  `ObjArea` (the working copy), `ObjWork`, `ObjCache`, `ObjMemo` (the
  sort's memory, whole pages, only `objects_frame` and `cache_reset` touch
  it: beside the cache in the live disc), `ObjOut`;
  `AreaCode` (`area_init`, `area_enter` and the database's reader, never in
  sideways RAM) and `AreaConv` (the conversion and its tables, anywhere).

## The check (`tools/objectcheck.mjs`)

`tools/objectcases.py` runs the model's own functions (render.render's
stages 1-7, asserted equal to `render()` on every entrance view) on its
cameras: the 65 entrance views, a four-step walk from each, a four-step
strafe from each along each axis (`STRAFE_STEP` a frame, so that the
camera's cells pass boxes' sides one at a time, which the sort's memory
must see), and from eight entrances every yaw, every pitch and every roll
with the others kept, and 24 random angles (the strafes since the fourth
round: before it, 2,485 cameras). The checker runs each through
`objects_frame` headless
and compares the matrix, the candidates and their masks, every candidate's
camera-space vertices (read as `transform_object` returns), every
candidate's drawn faces, the order and the output, exactly; and that
nothing outside the pipeline's memory was written. It reports each stage's
cycles (each instruction's to the innermost stage routine running) and the
arithmetic's calls; `--profile` gives cycles by routine.

[measured] All 2,485 views and 8,472 matrices agree: 29,508 candidates,
141,989 vertices, 23,760 faces (with the second round's model).

## Where the cycles go [measured]

Entrance views (each a turn: the cache refilled) and four-step walks from
each (each a step: the cache kept), median and maximum, cycles. "First"
is the pipeline as first merged (exact against the first model); "now" is
after the second round below.

| stage | turn, first | turn, now | step, first | step, now |
|---|---:|---:|---:|---:|
| matrix | 1,620 | 1,620 | 44 | 44 |
| object pass | 7,051 | 7,051 | 7,051 | 7,051 |
| transform | 40,054 | 40,054 | 13,889 | 13,889 |
| near clip | 13,095 | 13,083 | 13,505 | 13,493 |
| guard band | 58,942 | 35,690 | 59,405 | 35,861 |
| projection (the maths') | 24,937 | 29,649 | 24,934 | 29,601 |
| outcodes (3D, first; from the projection now, in it) | 34,579 | - | 34,968 | - |
| 2D clip | 47,688 | 34,157 | 47,706 | 36,157 |
| area test, first; drawn test, now | 19,244 | 5,143 | 19,124 | 5,143 |
| the faces' own (and the beyond and guard tests, now) | 34,781 | 48,710 | 34,856 | 48,810 |
| sort | 12,103 | 12,086 | 12,103 | 12,086 |
| output | 1,089 | 1,080 | 1,089 | 1,080 |
| **total, median** | **320,952** | **253,073** | **292,918** | **220,860** |
| **total, max** | 524,354 | 393,945 | 474,432 | 350,597 |

On the way [measured, the same views]: the crossings, the outcodes from the
projection and the drawn test (the approved proposals) took a median turn
to 278,674 and a step to 246,565; the drop of faces beyond x = ±z, 2y = ±z
to 271,344 and 242,414; the normalised fractions and the 2D clip's skipped
passes to 257,135 and 225,807; z << 4 once a vertex to the figures above.

**The target (about 30K a step and 45K a turn at the median) is not met:
a step is 221K, a turn 253K.** (Before the third round, below.) At a median turn now: 30 crossings' fractions
(`frac16`, 20K), 64 products of up to four bytes by four (`umul32`, 16K),
12 exact near-clip divisions, 56 projections (30K, the maths'), 29 fills
(17K), the guard and beyond tests (about 20K), the faces' loops and
copies (about 25K), and the sort (12K).

## The third round: the front end restructured (track M)

Track M took the front end on to restructure it (journal, 2026-10-31,
"the front end restructured"): one pass over each object's vertices, faces
projected whole taken or dropped by their outcodes, the cone for the rest,
the sort's compares remembered, the area records built at area entry. The
figures, before and after, by stage, are in that journal entry; in short
[measured], a step's median went from 205,851 to 184,419 cycles and a
turn's from 236,918 to 216,847, against the projection track's pipeline
(fb90ec2), exact against the model throughout.

What it found:

- **The vertex pass and the faces projected whole pay.** At a median
  step [measured], the faces' own work went from 48.8K to 12.9K, with
  18.4K more for the vertex pass; the projection from 17.5K to 10.6K, the
  shared entries taking about half the projections; the 2D clip from
  36.1K to 14.7K.
- **The cone doesn't pay yet.** Its picture is exact, and it needs no near
  plane or guard band, but at the median it costs about what the near
  clip, the guard band and their share of the 2D clip did: a view has
  about three such faces, each about four edge lines (a plane's normal by
  byte products, cut to `LINE_BITS`, and three constant products) and five
  crossings (a sixteen-step division and two products each). The crossings
  (`frac16`) and the lines (`edge_line`) are the two largest routines of the
  frame.
- **The sort's memory** pays on a step (the cells hold) and is even on a
  turn the check's views see (each entrance view a new camera).
- **A 16-bit camera space**: the brief's suggestion, measured in the model
  and not built. With a block exponent an object (its vertices shifted
  right together until they fit 16 bits), no pixel of the 2,485 check views
  changes; cut to world units (V >> 6), 4,571 of 26,877,760 change, none
  in the entrance views [measured]. The 24-bit adds and tests it would
  shorten aren't where the cycles went, so it waits for a vertex path that
  uses it.

## The fourth round: optimisation (track O)

Track O took stages 1-7 through optimisation rounds (the figures, before and
after, by stage, step and turn, are in the journal, 2026-10-31, "the front
end's optimisation rounds (track O)"). Each round profiled first
(`objectcheck.mjs --profile`, and `--profile-walks` for the walks' steps
alone, the frames that only move), took the hottest routines against the
checklist (`../chuckie-egg-2-beeb/docs/optimising.md`), and kept a change
only if it measured faster and stayed exact: the model is unchanged, so no
pixel moved, and every stage of every check view and every frame of the
live disc agree with it as before.

Kept:

- **The cone's planes** (`edge_normal`): a column entry's two terms share
  one patched multiplier, a ±64 entry is a shift, and a coordinate's sign
  comes from its raw top byte's excess rather than from its size first.
- **The cone's lines** (`edge_line`): one bit length for all of N, the
  three components' windows shifted together, the constant products on raw
  bytes with the sign's excess taken off (no negations), and the corners' f
  kept for the passes.
- **The cone's passes**: vertices tagged with the rectangle's sides they're
  on, so a corner's f is the line's own and a side's one product; the
  rectangle's first pass needs none. `vertex_code3`'s AND stops at 0.
- **Crossings**: `frac16` normalises by the difference's bit length instead
  of a bit at a time.
- **The transform**: no near flag (the band test reads z); M c moved on by
  the step while the matrix holds.
- **The vertex pass**: the band test inline; every vertex used is projected
  when none is off the band, without the faces' loop; a `project_y`
  vertex's x outcode is the last one's.
- **Faces projected whole** gathered straight into the output; the drawn
  test on the staged polygon, with the sizes' order before the products.
- **The sort**: each entry's memory row once a frame and a pass's place in
  a register; the memory kept across a cell that passes no box's L or H.
- **For room** in the live disc's bank: the matrix's products and roundings
  as subroutines (a build is a turn's alone), and the 2D clip's four passes
  as one routine. Both cost some cycles for their bytes.

Measured and not kept:

- **Skipping `vertex_shared`'s compares** for the pairs the vertex orders
  know share x and z under a level camera: the test cost about what it
  saved.
- **Ending the sort at a cycle of two** (an order the same as two passes
  before, after which the rest alternate, which would be exact): in the
  model, too few of the entrance views and walks reach one early to pay.
- **A shared edge's plane**: two faces of a box sharing an edge have planes
  exactly opposite (A_k × col = A_i × col, the edge being along col), so one
  normal would serve both; but two cone faces of one object rarely share an
  edge in the check's views.

What's left:

- **The cone's crossings**: `frac16`'s sixteen-step division is the frame's
  largest routine. A crossing by a reciprocal table and products (rtw-sources
  §1.5) is several times cheaper; for the cone, whose polygon's edges lie in
  the view, a reciprocal of nine or ten bits puts a crossing within a
  fraction of a pixel. It's a change to the model's crossings (a decision,
  with pixel figures against the model and the ZX oracle) and needs a
  table's room outside the bank.
- **The lines** (`edge_line`) are next; then the vertex pass's copies into
  the projection's arguments, which a projection reading the vertex arrays
  would save.
- **Still frames**: on the live disc stages 1-7 run in full when nothing
  moved. `objects_frame` could return at once with the camera and every
  object's state as last frame's, if the logic said when an object's state
  changed (the live loop's, track P's).
- **The target** (about 60K at a median step) is still far off: the cone is
  about a third of a step, and the projected faces' path (vertex pass,
  projection, faces, 2D clip, drawn test) as much again.

## The floor (decision 8a)

The coordinator asked how much of each stage the floor takes: the area's
floor object (`colours.floor`), one face 127 cells on a side in most areas,
whose vertices lie far to the side every frame. `objectcheck.mjs --floor`
counts each candidate's cycles, from its turn in `objects_frame`'s loop to
the next's, the floor's apart [measured]:

| | turn, first | turn, now | step, now |
|---|---:|---:|---:|
| the floor, median | 64,573 (19%) | 43,290 (16%) | 42,488 (18%) |
| its share of the guard band | 47% | 41% | 42% |
| ... of the near clip | 27% | 27% | 27% |
| ... of the 2D clip | 21% | 23% | 23% |

**The floor as the horizon**, measured and not taken. `render.py`'s
`floor_as_horizon` (off: `FLOOR_AS_HORIZON`) draws no floor face and passes
the rasteriser a horizon from the matrix alone: a view ray (X / FX, −Y / FY,
1) is level when it's square to the camera's up, M's second column, which
with FY = 2 FX is 2 m01 X − m11 Y + m21 FY = 0, sky where positive; as the
rasteriser takes it, a point on the centre line across the line's steeper
axis and the direction (m11, 2 m01), the ground the floor's top face's
pattern. Against the floor as a face [measured, every check view, the model]:

- 141,224 of 32,603,200 pixels differ (0.43%): 3,562 over the 65 entrance
  views (0.5%), mostly the thin band past the floor's far edge;
- but up to 2,574 of a view's 10,816 near the platform's edge looking out
  (area 8's entrance 11, turned): the original shows the void past the
  edge, the horizon ground to infinity;
- and areas 14 and 18, whose floors are 11 cells thick, show objects the
  floor's top hides;
- against the original (`zxcompare.py`, with the ground given the floor's
  colour so it's fair: a scratch variant, as `zxcompare` itself renders no
  horizon): 99.37% of pixels away from edges agree, against 99.95% with the
  floor as a face; the worst views 91.4% (area 4's entrance 28), 91.6% and
  93.3%.

It would save about 43K a frame, but it isn't only the thin band: the edge
of the world goes. The 6502 side isn't built; it's the decision below.

## Decisions proposed

For the coordinator to number. From the first and second rounds (approved,
now decisions 24-26): clip crossings by one fraction; outcodes from the
projection and the drawn test; the floor stays a face.

From the third round:

1. **The cone** (amending decisions 15 and 17): a polygon the projection
   can't take whole (a vertex nearer than `ZNEAR`, or outside the band) is
   drawn as the view's rectangle clipped by its edges' planes through the
   eye, its exact image; so polygons have no near plane, and the guard
   band's clip goes. The band a face is projected whole inside is by bit
   lengths (x within 2^(n + 3), y within 2^(n + 2)), inside the guard band. A
   line or a point with an end outside it is clipped in 3D to `ZNEAR` and
   the planes x = ±z, 2y = ±z by crossings, no longer the exact near clip.
   Against the model before it [measured, `tools/model` both ways]: 755 of
   3,515,200 pixels differ over the 65 entrance views and their walks (57
   in the worst view, the draw order the same); 5,130 of 26,877,760 over all
   2,485 check views, the order differing in 3. Against the ZX oracle, all
   of each view's pixels: 1,389,622 of 1,406,080 agree, against 1,389,686
   before; away from edges 99.95% either way (`make model-zx`).
2. **No picture change, recorded for the record**: every face's loop winds
   anticlockwise about its outward normal (a rectangle's high or low face
   was the other way), so its output polygon's vertices run the other way.

## What's left

- **The target** (about 40K at the median) is far off. The cone is the
  largest part: its crossings and its lines. What would move it: a level
  camera's normals (a box's vertical edges' planes are A's x and z, no
  products; a horizontal face's other edges share its height's products,
  by the cofactor identity A x M e = cof(M) (D x e)); fewer crossings (a
  line's crossing with the rectangle's side is one division, not a
  fraction and a product); fewer lines (an edge whose plane can't reach
  the rectangle). Then the vertex pass's own overhead, the transform's adds
  (a 16-bit space with a block exponent is picture-free, above), and the
  object pass.
- **Size**: the pipeline's code fills its sideways bank on the live disc
  but for a few dozen bytes (the build's guard says when it doesn't fit);
  cold code (a line's 3D clip, the slow fills, the generic cone edges)
  could move to the main RAM the per-area records freed.
- **The logic's side**: a build with the logic (`OBJ_LOGIC`, `AREA_GLOBALS`)
  calls `area_enter` after each of its area loads, which builds the
  globals' slots from its records with the rig's parts where it put them.
- **Area entry's cost** is mostly the slanted faces' planes (the cross
  product's products, the greatest common divisor and the divisions) and
  the reading of the records through main RAM; it now also clears the
  sort's memory.
