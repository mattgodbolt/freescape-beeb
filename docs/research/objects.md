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
```

`make objects` needs `make colours` and the maths' tables (`make maths`'s
`build/maths/`), which its rules build. It fails if any stage of any case
differs from the model, or if the pipeline writes outside its own memory.

## The records (`tools/mkareas.py`)

Driller's areas in the engine's layout, generated into `build/gen/` from
`build/data/driller.json` (nothing of Driller's is committed):
`areas.6502` for the assembler, `areas.json` for the check.

- **A slot an object**, structure of arrays, the globals in the first
  `G_OBJ` slots and the area's after them. Only objects the model can draw
  get a slot (`objects.shape()` isn't `None`); the object pass walks the
  area's slots and then the globals', which is the model's order with the
  undrawable ones left out. The faces' colours are the model's
  (`render.recolour`, decision 8), and the generator checks the globals are
  coloured alike in every area, since they're copied once.
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
  of loops shared by every area (`lp_table`, each distinct loop once); the
  mask of its object's vertices it uses; and its test (`fa_test`,
  `fa_tval`):
  - an **axis test** for a face in a plane x, y or z = P: seen from below
    when the camera's floor cell f < P (`T_AXLO + 2 axis`, tval P), from
    above when P < its ceiling cell e, stored as 255 − e < 255 − P
    (`T_AXHI + 2 axis`), so both are `thr[test] < tval`, one compare;
  - a **plane test** (`T_PLANE`, tval the plane's index in `pl_*`): the
    reduced normal's two non-zero components (every slanted face in Driller
    has two) and a point of the plane on those axes;
  - `T_ALWAYS` for a line and a sensor's point.
- **Packed** in the arrays' order, each as long as its count, into
  sideways RAM from bank 4 (decision 5). `area_enter` copies an area's into
  the working copy (`ObjArea`), so every array has one address and the
  stages index it with `abs,X`.

Sizes [measured, `make objects`'s `mkareas.py` line]: 29 areas in **24,985
bytes** (bank 4: 16,125, bank 5: 8,860); the globals' record 686 bytes,
resident; 70 bytes of shared loops. The largest any area needs, globals
included: 38 objects, 128 faces, 66 planes, 168 generic vertices, 5
sensors, so the working copy is 2,504 bytes.

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

- **M c** once a frame, by the maths' `dot3` a row at a time.
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

Each seen face as `render.draw_faces` takes it: the near clip in 3D
(Sutherland-Hodgman; a line as a segment), each vertex's outcode, the guard
band's clip in 3D (decision 17), the projection (the maths' `project`), a
line widened to its quad and a point to its square, the 2D clip (or only
repeats dropped), and the area test. A vertex the faces share is coded and
projected once (`vflag`'s bits); the clips' new vertices follow the
object's in the same arrays.

- **Outcodes** are exact: A p > B z for each side, with quick tests first:
  outside from w = z >> SHI, inside below w/2 and below 5w/8, outside from
  6w/8, each rounded down; between, two products in full
  (`tools/mkareas.py`'s `outcode_shifts` asserts each test for every z ≥
  ZNEAR). Only 3 vertices a median view reach the products [measured].
- **The guard band's test** is made with the outcode: a vertex inside a
  side's plane is far inside the band's (ASSERTed), so only one outside a
  plane compares with z << GUARD_XS (or YS).
- **Every new coordinate** (near clip, guard band, 2D clip) is the model's
  `round_div` exactly: a product of up to four bytes by four (`umul32`, a
  column at a time on the maths' quarter squares) and a long division
  (`udiv`, by whole bytes until the quotient's size, with a two- or
  three-byte remainder when the divisor allows).
- **The area test** is the model's: the fan's cross products from vertex 0,
  16-bit, by `smul16`.

## Stage 7: the sort (`src/order.6502`)

The original's bubble sort, the model's `compare_axis` case for case, on
cells: each draw-list entry's box and its side of the camera (across, below,
above) on each axis are found once, so a compare is byte compares on two
index registers. 12,103 cycles at the median entrance view, 48,405 at the
most (19 objects, 324 compares) [measured].

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
| `area_init` | the globals copied in, once | | the working copy's first slots | A X Y, the cache |
| `area_enter` | an area's record copied in | A: its index in `ar_*` | the working copy, `ob_n`, `ob_state` | A X Y, the cache; pages and restores the bank |
| `objects_frame` | stages 1-7 | `cam_x/y/z` (16-bit, below &8000), `cam_yaw/pitch/roll` (0-71) | `out_*`; also `mat`, `cd_*`, `dl_*`, `tf_*` | A X Y, its zero page |
| `cache_reset` | every cache emptied | | | A X |

- **Paging**: the records' bank only during `area_enter` (it restores
  `romsel` and its copy at &F4); the maths' tables readable throughout
  `objects_frame` (HAZEL in the engine: ACCCON's Y); the working copy and
  the work areas never in `&3000-&7FFF` while the screen's X bit is set, nor
  in sideways RAM.
- **The logic** hides and shows by `ob_state`'s bit 7, finds slots by
  `ob_id`, and must call `cache_reset` if it moves an object (the rig).
- **Sections** (each placed by the build's memory map; the check build's
  in `mk/objects.mk`): `ObjCode` (12.2K of this track's code [measured]),
  `ObjConst` (2,232 bytes: the f64 table, quarter squares, loops, the area
  directory, the copy's descriptors, the sine table, the globals' record),
  `ObjArea` (2,504), `ObjWork` (1,902), `ObjCache` (2,304), `ObjOut`
  (1,410), and the records' `AreaBank4`, `AreaBank5`.

## The check (`tools/objectcheck.mjs`)

`tools/objectcases.py` runs the model's own functions (render.render's
stages 1-7, asserted equal to `render()` on every entrance view) on 2,485
cameras: the 65 entrance views, a four-step walk from each, and from eight
entrances every yaw, every pitch and every roll with the others kept, and
24 random angles. The checker runs each through `objects_frame` headless
and compares the matrix, the candidates and their masks, every candidate's
camera-space vertices (read as `transform_object` returns), every
candidate's drawn faces, the order and the output, exactly; and that
nothing outside the pipeline's memory was written. It reports each stage's
cycles (each instruction's to the innermost stage routine running) and the
arithmetic's calls; `--profile` gives cycles by routine.

[measured] All 2,485 views and 8,472 matrices agree: 29,508 candidates,
141,989 vertices, 23,753 faces.

## Where the cycles go [measured]

Entrance views (each a turn) and their walks (each a step), median and
maximum:

| stage | turn median | turn max | step median | step max |
|---|---:|---:|---:|---:|
| matrix | 1,620 | 1,628 | 44 | 44 |
| object pass | 7,051 | 17,990 | 7,051 | 17,990 |
| transform | 40,054 | 71,734 | 13,889 | 23,462 |
| near clip | 13,095 | 38,875 | 13,505 | 40,351 |
| guard band | 58,942 | 147,706 | 59,405 | 153,657 |
| projection (the maths') | 24,937 | 53,036 | 24,934 | 53,064 |
| outcodes | 34,579 | 66,448 | 34,968 | 67,209 |
| 2D clip | 47,688 | 116,925 | 47,706 | 117,129 |
| area test | 19,244 | 48,136 | 19,124 | 48,464 |
| the faces' own | 34,781 | 76,016 | 34,856 | 76,016 |
| sort | 12,103 | 48,405 | 12,103 | 48,405 |
| output | 1,089 | 2,561 | 1,089 | 2,561 |
| **total** | **320,952** | **524,354** | **292,918** | **474,432** |

At a median turn the clips make 60 exact `round_div`s: 6 near-clip points
(two each), 10 guard-band points (three each) and 18 2D cuts. Each is a
product and a long division of 1.5K-3K cycles, about 140K of the frame.
That is the model's rule, not a choice here; it's the first proposal below.

## Proposals, with figures

1. **Clip crossings from one parameter, by reciprocal tables** (the near
   clip, the guard band and the 2D clip). Where the model now rounds each
   new coordinate `a + round_div(Δ f_a, f_a − f_b)` exactly, it would take
   t = f_a / (f_a − f_b) once a crossing, as a 16-bit fraction from a
   normalised reciprocal (`rtw-sources.md` section 1.5), and each
   coordinate as `a + round(Δ t)`. [counted] about 1.6K cycles a guard-band
   point (t, then three products of four bytes by two), 1.2K a near-clip
   point and 550 a 2D cut, against 7K, 4.6K and 2.3K now: **about 100K off
   a median frame**. The cost is precision: t's
   2^-16 moves a cut point by up to |Δ|·2^-16. At the guard band (16 views
   wide) that is invisible after the 2D clip; at the near plane a visible
   cut point could move by pixels when Δ is large, so the near clip may
   need more bits of t (24, at about twice the cost). The model would make
   crossings the same way. A decision for the coordinator and Matt.
2. **No area test**, as the original has none (its object joins the draw
   list when a face has "something left after the clip",
   `zx-driller.md`): a face is drawn when three distinct vertices are left.
   A degenerate face covers no pixel, but it can put its object on the draw
   list and so change the sort. Saves the area test: **19K at the median,
   48K at most** [measured].
3. **Outcodes from the projected vertices**: decide the side-plane
   rejection and the need to clip in 2D from (sx, sy) against the view's
   rectangle, after the guard band and the projection, instead of from the
   3D planes. Byte compares on 16-bit values in place of most of the
   outcodes' **35K**, less the projections of vertices only rejected faces
   use. It changes which edge-on slivers are rejected, as the projection's
   rounding does.

Proposals 2 and 3 are simple to make in both the model and the 6502; 1 is
the one that matters.

## What's left

- **Speed, exact**: a level camera's paths (`rtw-sources.md` 1.3-1.4: the
  edges' zero components skipped in the vertex adds, one projection a
  vertical edge); the area test's signs before its products; the outcodes'
  quick tests on fewer bytes; the arithmetic as macros where it's hot; the
  sort's compare.
- **Size**: this track's code is 12.2K, too big for main RAM beside the
  rest; the engine's build should put it in a sideways bank with the
  working copy (and the records in the others), which needs only the
  sections' placement.
- **The logic's side**: moving an object (the rig) means updating its
  record's cells and calling `cache_reset`.
- **The glue** to the rasteriser: `out_*` to `rs_*` (or the same arrays),
  colour indices to patterns.
