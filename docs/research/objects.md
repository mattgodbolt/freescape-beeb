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
node tools/objectcheck.mjs build/objects --entrance --quiet --json NEW.json --compare OLD.json
                                      # each stage against an earlier run's, view for view
node tools/objectcheck.mjs build/objects --entrance --profile-walks --fine --top 60
                                      # by every label, scoped ones too
node tools/objectcheck.mjs build/objects --profile-views '-y([1-9]|[0-9][0-9]+)$' --fine
                                      # the yaw sweeps' 5-degree turns alone
                                      # (--profile-turns: the entrance views')
node tools/objectcheck.mjs build/objects --entrance --fills --quiet
                                      # a turn's fills by the object's kind
.venv/bin/python -I tools/model/render.py --diff clip.SIDE_RECIP build/data/driller.json build/zx/views
                                      # a model flag's pixels, and the ZX oracle's agreement
                                      # (render.py's own flags too, such as render.IMAGE_LINES)
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

A level camera's (pitch and roll 0) is the yaw's rotation itself, the
rotations of 0 being 64 times the identity, which the rounding gives back,
so since the ninth round its build takes no products, and its image columns
(`im_cols`) two.

**An entry can be 65.** Rounding lets `M`'s entries reach ±65 in 896 of
the 373,248 orientations [measured, the model's `compose` over all of
them]; `mat_big` marks those (see the transform).

## Stage 2: the object pass (`src/objects.6502`)

For each slot: hidden (`ob_state` bit 7, the logic's) skips it; the coarse
cull is a byte compare an axis at most, the one that can cull on it (a box's
H against f + 1 ahead along the axis, or its L against e ahead against it),
which `camera_setup` patches into the pass's three slots each frame, or a
branch past the slot (since the seventh round; a level camera's y never
culls, nor an axis square to the view); a sensor's watching test is the model's
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
  use and those they're built from. Under a level camera (since the seventh
  round) the cache's edges along x and z have y 0 and the one along y has x
  and z 0, exactly, so a cuboid's 1, 4 and 5 add x and z and copy y, 2 adds
  y and copies x and z, and 3, 6 and 7 are copies.
- **The products** are all 64 u m for a cell u (0-127) and an entry m of
  M: by quarter squares, `f64(u + 64 + m) − f64(u + 64 − m)` from a
  768-byte table of 64 (n² DIV 4), both indices bytes: three byte
  subtractions a product. The fills skip a zero cell or a zero entry (a
  level camera's matrix has four; since the eighth round a level camera's
  point takes y as 4096 py and only the four entries of x and z), and a
  generic object's vertex the one before it again (a pointed pyramid's apex,
  three times over) takes that slot's vector. An orientation with an entry
  of ±65 (`mat_big`) would run the table's index off its end for a cell of
  0 or 127, so its fills use the maths' `mul` instead. Under a level
  camera (since the ninth round) the products are read at bases patched for
  M (`fill_patch`), the cell the index register, and written straight into
  the cache; M c is four of the maths' `mul` and a shift.
- **The bounds** (since the eighth round; the model's `render.beyond_view`,
  `OBJECT_CULL`): each of L = 3x + 2z, R = 2z − 3x and T = z − 3y is zero on
  a plane through the eye beyond one of the view's sides (x = ∓2z/3 against
  the view's ∓0.656z, y = z/3 against its 0.328z: asserted), so a candidate
  with every vertex where one is negative can't be seen, and `objects_frame`
  passes it over before its transform. A vertex's value is the function of
  M v less its value of M c, so an object's greatest over its vertices of
  M v's is kept (`bd_k*`, in `ObjBound`), which the orientation alone sets.
  Since the ninth round it's made from the cells, before the fill
  (`bound_object`, with its own stamp, `ob_bstamp`), so a candidate passed
  over is never filled: F(M 64 u) = 64 (phi . u), phi F of M's columns, and
  over a box's corners the greatest phi . u takes each axis's high cell
  where phi is positive, else its low, three products a function
  (`bound_box`, its nine terms patched for M by `bound_patch`, from the
  maths' 16-bit quarter squares). A cuboid, a rectangle and a sensor are a
  box each, a pyramid two (its base's and its apex's rectangles), any other
  object a box a vertex. Each product is biased by &8000 so that the sums
  are unsigned, and the object keeps 64 times its greatest; the frame's
  (`bound_frame`), made in 32 bits, is 64 ceil(F(M c) / 64) plus the same
  bias, saturated to 24 bits, so the test is exact and three compares,
  mostly of top bytes. The model asserts every coefficient within 255
  (`render.BOUND_PHI`), which the tables' bases need. The bottom of the
  view (z + 3y) was measured and left out: it caught the fewest candidates
  for its cost on a turn.

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
  pass (`BAND_TEST`; from z's middle byte `BAND_MID` up, z's top bytes
  alone decide, as past 65,536). The band is inside the guard band (the
  model asserts), so everything decision 17 bought still holds. Then each
  vertex of a face with no vertex off the band (every vertex used, when none
  is off) is projected once (`vertex_shared`), in an order for the object's
  kind, written out (`vp_cuboid`, `vp_rect_x` ..: a cuboid's vertices i and
  i + 2 share x and z under a level camera, so do a rectangle's along y)
  that lets `project_y` and `project_z` take a vertex sharing the last one's
  x and z, or z, with its outcode against the view (a `project_y` vertex's x
  part the last one's; since the seventh round each coordinate's from a table
  by its high byte, `oc_x` and `oc_y` in `ObjConst`, but for the far edge's
  own high byte, where the low byte decides). Under a level camera
  (`mat_tilt` 0) the upper vertex of such a pair goes by `vertex_up`,
  `project_y` without the compares.
- **A face projected whole** (`poly_face`): its vertices go straight into
  the output (`out_v*` from `out_vn`) as they're gathered, with their
  outcodes' AND, which drops it, and OR; a quad's gather and repeat tests
  are written out. Wholly inside, and with no vertex the one before it
  again (the first against the last), the drawn test takes them there and
  `commit` records the face; else they go to `pa` for the 2D clip, or for
  the repeats' test, which stages them back (`dedupe_stage`: straight into
  the output when they'd fit as they come, else deduped where they are and
  staged after, as before, so that only what's left is measured against the
  room). A cone's polygon and a line's take the same `dedupe_stage`,
  `drawable` and `commit`.
- **Any other polygon: the cone** (`cone_face`, the model's
  `clip.cone_clip`). Every vertex in one of the half-spaces x < −z, x > z,
  2y > z, 2y < −z, z ≤ 0 (`vertex_code3`, each a 24-bit sum's sign, N EOR V; each
  misses the view's pyramid wherever the point is) drops it; the AND stops
  once it's 0. Else each edge's
  plane through the eye becomes a line on the screen, kept if it cuts the
  view's rectangle, and the rectangle is clipped by each kept line in turn
  (`cone_pass`, Sutherland-Hodgman, its crossings as the 2D clip's). The
  face's loop winds anticlockwise about its outward normal (every loop
  does, `objects.shape`), so its inside is where (A × B) · r ≤ 0 for each
  edge A → B and every ray r through it, and the rectangle clipped by all
  its edges' planes is exactly its image: no near plane and no guard band,
  a pyramid from the eye as the original's.
  - **A line from images** (since the seventh round: `image_edge`,
    `image_line`, the model's `render._image_line` and `clip.image_line`,
    `render.IMAGE_LINES`). An edge's plane's line runs through the image of
    any point of the edge in front of the eye, so an edge with an end the
    projection takes (not in `vp_off`; projected then if it wasn't) has its
    line through that image: through both images when it takes both (as a
    face projected whole has that edge), or for a box's edge, along M's
    column d for its axis, toward its vanishing point, square to (FY dy + v
    dz, FX dx − u dz), (u, v) the image less the view's centre (N = A × d,
    and (−2 Nx, Ny) is Az / FX times that). `matrix_build` keeps FX M0k and
    FY M1k for each column (`im_cols`), so a line takes two products of a
    16-bit coordinate by a byte at most, and none for a level camera's
    vertical edge. The pair is shifted right together until both fit
    `IMAGE_BITS`, or is a unit (±1) when the other is 0, and the line is
    f(x, y) = A x + B y + C with C = −(A px + B py) (`im_term`, products of
    sixteen bits by sixteen), so it passes through the image exactly; f at
    the rectangle's corners is C, C + A W, C + A W + B H and C + B H
    (`im_w`: a coefficient by W = 128 × 13).
  - **Else the plane's own line** (`edge_normal`, `edge_line`): a generic
    object's edge with one end taken, an edge with neither, or images that
    give no direction. A box's edge runs along a world axis k, so B − A is
    a multiple of M's column k and the plane is ± A × M[:, k]: each non-zero
    entry c of the column gives two terms, A's coordinates by c, so c is
    patched into the quarter-square reader once for both (`en_mul`: a
    signed 24-bit coordinate by a byte, its raw top byte's excess taken
    off), and an entry of ±64 is a shift (`en_shl6`). Any other edge's is
    cut16(A) × cut16(B − A), 16-bit products. The normal is shifted right
    until it fits `LINE_BITS`, N', and the line is A = −2 N'x, B = N'y, C =
    2 XC N'x − YC N'y − 2 FX N'z = −R − (A W + B H) / 2, its corners'
    f by `image_line`'s tail. (Until the seventh round a level camera's
    planes had closed forms by M's cofactors, and this way was written for
    speed; it's rare now, so it's written for room.)
  - Either way the line keeps f at the rectangle's corners (`lfc`), which
    decides whether it cuts and stands for a corner's f in the passes. A
    face's lines are made in the order below, and none after one with every
    corner outside it, which leaves nothing (the model makes them so too,
    so that the vertices the images project are the same).
  - Each of the clipped polygon's vertices is tagged with the rectangle's
    sides it's on (`pa_tg`, `OC_*`; a crossing gets its ends' sides in
    common), so a pass's f at a vertex (`cone_eval`) is a corner's own, a
    side's corner f plus one product (A x along the top and bottom, B y down
    the sides), or two products inside; every way gives the same f.
  - An edge with both ends at or behind the eye (z <= 0) has no line: the
    face's image is what's in front of the eye, a convex region whose
    boundary is the images of its edges' parts in front, so it's inside
    such an edge's plane already (`render.BEHIND_EDGES`).
  - Each vertex also carries the label of its edge to the next (`pa_lb`):
    a side of the rectangle, or the kept line it runs along, so a crossing
    knows what it's on. **On a side** it's the line's own crossing with that
    side (`side_cut`, the model's `side_crossing`): from the side's corner
    inside the line, f there over |A| (or |B| down the sides), the same
    point whatever piece of the side is being cut, by the 2D clip's
    reciprocals (`clip.side_d`, `SIDE_RECIP`: a's nine bits, and a product
    of sixteen bits by nine, at most the side's length) where it was an
    eleven-step division rounded half up; for a of 1 (a unit line from
    images, square to the side), f there itself, exactly (`clip.UNIT_SIDES`,
    since the seventh round). A line square to two sides (B zero,
    a level camera's vertical edge's, or A zero) crosses both at the same
    point, which `side_cut` keeps for the second (`ln_scl`, `ln_sch`), and
    the passes add no term for a zero coefficient. **Along a line** whose edge shares a vertex with the
    cutting line's edge, the two lines meet at that vertex's image: if the
    projection takes the vertex, its projected position, clamped to the
    rectangle (projected then if the vertex pass hadn't), the point a face
    projected whole has there too (`clip.JOINS`). Any other crossing is the
    model's crossing from the inside end, as before.
  - The lines of edges with both ends in front come first, then those
    with one end behind, each in the loop's order (`render.FRONT_FIRST`):
    a floor's far edge's line before its sides', which then mostly cut
    nothing more. Side crossings and joins being the same points whatever
    the order, that leaves the general crossings, which it makes rare.
  - The first line's pass is made from the rectangle's corners' signs
    (`cone_first`), and each later pass writes the other half of one pair
    of arrays (pb follows pa, `cp_src` naming the polygon's half), so
    nothing is copied back between passes; a pass that finds every vertex
    inside its line leaves the polygon where it is.
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
  rounded half up. The cone's general crossings and a line's 3D clip take
  t so; the 2D clip's, below, by a reciprocal.
- **The 2D clip** is 16-bit (inside the band everything projects within
  the guard band's range), and runs only the passes for edges a vertex is
  beyond; its four passes, each written out (`CLIP_PASS`), are in
  `ObjMore`, outside the bank, each writing the other half of the pa and pb
  arrays as the cone's do. Its crossings' t is by a reciprocal
  (`clip_cut`, the model's `crossing_r`, `clip.RECIP_2D`), with no
  division: d = f_P − f_Q normalised to nine bits dn (d >> s, s =
  bitlen(d) − 9, or a shift left), R = 256 + `clip_m[dn − 256]` (about 2^17
  / dn: `maths.CLIP_M`, a page in `ObjMore`), and t = f_P R >> (s + 1),
  two byte products and a shift, then `lerp` as before. It's within about
  2^-8 of the division's t and still taken from the inside end, so two
  faces sharing an edge cut it at the same point.
- **The drawn test** (`clip.drawable`, on the polygon staged in the
  output): three vertices or more, one off the line through the first two,
  decided by the products' zeros and signs where it can be (from the
  differences' bytes, no size taken), then by the sizes' order (|dx| > |dy|
  and |ey| > |ex| make dx ey the larger, and the other way about), else by
  two 16 × 16 products.

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
leaves it. And a draw list the same as the last sort's, slot for slot,
under the same generation, has every compare the same, so it takes that
sort's order (`so_save`, `so_lobj`, `so_lord`; a cleared memory forgets it).

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
  in `mk/objects.mk`, where the live disc has the code): `ObjCode` (this
  track's code, and the vertex pass's and the cone's tables, in the
  pipeline's bank, `OBJ_BANK`, from `OBJ_CODE_ORG`), `ObjAndy` (its rarely
  run code, in ANDY over that bank's first 4K: "ANDY", below), `ObjMore`
  (more of it, outside the code's bank: main RAM on the live disc, which
  any bank paged sees; the 2D clip, its crossings and their reciprocals,
  the cone's side crossings, and the trampolines into ANDY),
  `ObjConst` (the loops, the sine table, the
  matrix's quarter squares, the outcodes' tables), `ObjTables` (the transform's f64 table, page-aligned in HAZEL),
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
camera-space vertices (read as `transform_object` returns; a candidate
passed over as beyond the view's sides mustn't be transformed), every
candidate's drawn faces, the order and the output, exactly; the work no
output need show, because what it would change can be cut away later (the
lines the cone makes, `edge_line`'s and `image_line`'s calls, but an
`image_line` that found no direction, and the vertices projected, the
calls of the projection's three entries); and that nothing outside the pipeline's memory was
written. It reports each stage's
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
  as subroutines (a build is a turn's alone), which costs a turn some
  cycles; and, once track P's map gave the front end `ObjMore` in main RAM,
  the 2D clip there with its four passes written out (for a while they were
  one routine taking the side by offsets, smaller and slower).

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
  table's room outside the bank (`ObjMore` has some).
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

## The fifth round: the cone restructured again (track Q)

Track Q took the cone on, and then the 2D clip's crossings, model and 6502
together (the figures, before and after, by stage, step and turn, and the
picture's, are in the journal's entry for track Q). The cone was already
in 2D (each edge's plane a line on the screen, the rectangle clipped by
them), so the round went for fewer lines, cheaper crossings and less
copying, every picture change proposed below:

- **No line for an edge behind the eye** (both ends at z <= 0): the
  face's image is the image of its part in front, a convex region whose
  boundary is the images of its edges' parts in front, so it's inside such
  an edge's plane already. A floor's back edge, and a wall's near one,
  are such edges in most frames.
- **Side crossings from the line**, an eleven-step division from the
  side's corner inside the line (`side_cut`), not a fraction along the
  piece of the side the polygon has and a product; and **joins**, two
  consecutive edges' lines meeting at their vertex's projected image. Both
  are the same point whatever the polygon's state, so the passes' order
  touches only the general crossings, which the order **lines with both
  ends in front first** then makes rare: a floor's far edge's line goes
  first, and its sides' lines then mostly cut nothing more.
- **Passes**: the first made from the rectangle's corners' signs, the rest
  writing the other half of the pa and pb arrays in turn, and one whose
  line has every vertex inside leaving the polygon where it is; the 2D
  clip's passes in turn the same way.
- **The 2D clip's crossings by a reciprocal** (above), with no division.
- **The check** compares the work as well as the output (the lines the
  cone makes, the vertices projected), which caught mutants the polygons
  alone didn't: with side crossings and joins, a redundant line changes no
  polygon.

Measured and not kept: sharing the crossing of a line parallel to two
sides (A or B zero) between them, too rare to pay; a test on N' for lines
that cut nothing, as after the behind edges nearly every line made cuts;
`vertex_code3` testing only the half-spaces the face's AND still holds,
whose tests cost what they saved; lines of eleven bits (`LINE_BITS`), so
that every f fits three bytes, measured in the model and not built (its
picture changes a few dozen pixels over the entrance views and walks).

What's left: the lines (`edge_normal` and `edge_line`) are now the cone's
largest part, with `side_cut`'s division; a level camera's horizontal box
edges have closed forms (the normal's middle term is the edge's world
offset times M's y cofactor), and the floor's share a height. Outside the
cone, the projected faces' path (vertex pass, projection, faces, drawn
test) is the frame's largest block; `vertex_shared`'s own copies and
compares cost about what the projection's arithmetic does.

## The sixth round: the room spent (track V)

Track V took stages 1-7 through another round once the 192-line screen
had freed room (`docs/research/live.md`, "Room"), each change profiled
first (`objectcheck.mjs --profile-walks`, now with `--fine` for every label
and `--compare` against an earlier run's `--json`), and kept only if it
measured faster; all exact against the model but the last, a proposed
decision. The figures, before and after, by stage, step and turn, on the
yaw sweeps as well as the entrances (most of whose cameras face along an
axis, where a level camera's horizontal edges cost least the old way), and
the live disc's, are in the journal's entry for track V.

Kept:

- **The sort's last order** (`so_save`): a draw list the same as the last
  sort's under the same generation takes its order. A step's sort, which
  the memory had made mostly look-ups, is mostly a compare of the lists.
- **A level camera's edge planes by the cofactors** (above): fewer
  products for a horizontal box edge at a general yaw, and none for a
  vertical one; at a yaw along an axis (the entrances') about even with the
  general way, whose products there were shifts.
- **The vertex pass's orders written out**, and `vertex_up` for a level
  camera's upper vertices (no compares); `vertex_shared` keeps `vs_last`.
  The orders as calls of a routine that tested the need measured slower,
  for a few hundred bytes less; the tests stay at the calls.
- **The band at middle distances** by the top bytes alone.
- **The drawn test's zeros and signs first**, the sizes only when needed.
- **Lines square to two sides**: one crossing for both, and no term for a
  zero coefficient in the passes.
- **The side crossings by a reciprocal** (proposed below).

Counted and not built:

- **A level camera's transform by copies** (an edge along y adds to y
  alone, one along x or z leaves y): copies for a third to two thirds of
  each vertex's adds, for written-out adds of their own, some hundreds of
  bytes of the bank; the room went to the above.
- **The side crossings exact by a reciprocal and a correction** (the
  remainder's sign, a step or two): about half the inexact one's saving by
  the count, with more code in `ObjMore`, which has least room.

What's left:

- **The lines** (`edge_line`, `edge_normal`) are still the frame's largest
  block. Most of a cone face's edges have one end the projection takes and
  the other behind the eye or off the band; such a line is the line through
  that end's image toward the edge's vanishing point, which needs no 32-bit
  normal and no window of it (a picture change: the image's accuracy, not
  the plane's, a proposal to measure). An edge with both ends taken is the
  line through their images, as a face projected whole has it.
- **The vertex pass and the projection**: the copies into the projection's
  arguments (it could read the vertex arrays, but its interface is the
  maths check's, `tools/mathscheck.6502`), and `pmul`'s calls (written into
  each block, if the projection's code moved into the front end's bank,
  which the live disc's map, `src/live.6502`, places).
- **The faces' gather** (`poly_face`) and the transform's adds, each a few
  per cent.

## The seventh round (track W)

Track W took stages 1-7 through another round, profiled as the sixth
(`--profile-walks`, `--fine`, `--compare`), keeping what measured faster:
all exact against the model but the first, a proposed decision. The
figures, before and after, by stage, step and turn, and the live disc's,
are in the journal's entry for track W.

Kept:

- **The cone's lines from images** (proposed below): an edge with an end
  the projection takes has its line through that end's image, through both
  when it takes both (above). Measured, the lines' saving is smaller than
  their products suggested: C = −(A px + B py) still takes two products of
  sixteen bits by sixteen, and a one-end line's image is often projected
  for it alone; the planes' level closed forms went for room, and
  `edge_line`, now rare, was written again for room. With them, **a unit
  line's side crossings exact** (`clip.UNIT_SIDES`).
- **Outcodes by table** (`oc_x`, `oc_y` by the high byte, in `ObjConst`;
  the check build's `ObjConst` moved to the OS's pages at `&0A00` for them).
- **A quad's gather and repeat tests written out**, most faces being quads;
  room from `frac16`'s division as a loop (it's rare since the side
  crossings, joins and lines from images).
- **The cull's compares patched in** (`camera_setup` into `object_pass`'s
  three slots: the compare that can cull on each axis, or a branch past it).
- **Dedupe straight into the output** (`dedupe_stage`), and the 2D clip and
  the cone staging their own polygons.
- **A level camera's cuboid vertices by copies** (the transform, above).

Measured and not kept:

- **An object passed over when every vertex its seen faces use is in one
  of code3's half-spaces** (each of its faces would be dropped anyway, so
  no pixel changes; in the model `draw_faces` would return nothing, before
  any vertex is tested or projected). It catches most of the candidates
  that draw nothing, and none that draws, but `vertex_code3` on every
  candidate's vertices, until the AND is 0, cost more than the projections
  and faces it saved (the journal's entry for track W has the figures).
- **`im_term` on the cone's readers** rather than its own: its own
  quarter-square instructions, patched, measured a little faster.

What's left:

- **Candidates that draw nothing**: about a quarter of the walks'
  candidates, with about a quarter of their vertices (the journal's entry),
  are transformed, tested and mostly projected, then dropped face by face;
  mostly objects in front but to the side. A test per object must be
  cheaper than `vertex_code3` a vertex: a box's corners against the
  view's side planes from the cache (V0 = C0 − M c and the three edges,
  so a plane's least value over the corners is V0's plus each edge's
  negative part, a few 24-bit sums), or in world space against cells
  before the transform.
- **The lines**, still the cone's largest part: C's two products of sixteen
  bits by sixteen; and the cone's passes' products (`cone_eval`), which a
  unit line could skip.
- **The projection's overheads**, unchanged: the copies into its arguments
  and `pmul`'s calls. Its code is in `ObjMore`, whose room (and the bank's)
  doesn't take the projection written out per block; the vertex pass's
  band test for a level cuboid's upper vertices could take z's and x's
  test from the vertex below.
- **The floor** is still the largest face.

## ANDY: the cold code out of the bank (track AB, decision 52)

The pipeline's bank was full but for a few dozen bytes. Matt chose ANDY
(decision 52), the Master's 4K at `&8000-&8FFF` that ROMSEL's bit 7 pages
over the paged bank's first 4K, for the front end's rarely run code, so
that its bank has room for the hot paths. What went (`ObjAndy`), each a
routine that runs in few frames or a few times a frame, so that what it
costs there is a trampoline's call, not its speed (ANDY's RAM is as fast as
the bank's):

- the lines and points: `draw_segment`, `seg_clip`, `seg_point`, `seg_f`,
  `line_quad`, `point_square` and their tables, and `band_test`;
- the planes' own lines, for the edges whose lines the images can't give:
  `edge_plane` (new: `edge_normal` then `edge_line`), with `en_mul`,
  `en_shl6`, `en_acc`, `cut16` and `smul16`;
- the matrix's build (`matrix_build`, `im_cols`), a turn's alone;
- `sensor_watching`, `frac16` (the cone's general crossings and a line's 3D
  clip) and the slow fill (`fill_slow_point`, for an orientation with an
  entry of 65).

How it's reached (`src/transform.6502`'s header, `ANDY_CALL`):

- **Trampolines** in `ObjMore` (`andy_draw_segment` and the rest), as code
  in a bank can't page another in under itself: ANDY paged in (ROMSEL
  `OBJ_BANK OR ROMSEL_ANDY`), the routine, ANDY paged out. The routine takes
  its inputs in X, Y or memory and gives back X, Y, C and V (and A, by
  `ANDY_CALL_A`'s, for `edge_plane`). The interrupt pages nothing and reads
  nothing in sideways RAM, so ANDY paged under it changes nothing.
- **What ANDY's code calls in the bank** must be past the bank's first 4K,
  which ANDY hides: the bank holds the transform's code and the object
  pass's first, nothing of which ANDY's code reaches, then `obj_andy_reach`
  (ASSERTed at `&9000` or past it) and the rest (`src/matrix.6502`,
  `clip.6502`, `order.6502`), whose routines ANDY's code calls (`umul16`,
  `lerp`, `cone_qs`, which it patches, `vertex_shared`, `drawable` and the
  rest, each ASSERTed past `obj_andy_reach` at the end of `src/clip.6502`).
  So `mmul` and `mround`, which the matrix's build calls, stay in the bank,
  and `src/matrix.6502` comes after `src/objects.6502` in both builds.
- **Nothing ANDY's code reaches calls a trampoline**, which would page ANDY
  out under it: `dedupe` and `stage_pa`, which the 2D clip reaches from a
  line's face, stay in the bank.
- **The check build has the live disc's map** for the front end's code:
  `ObjCode` in its bank from `OBJ_CODE_ORG`, `ObjAndy` in ANDY, `ObjMore`
  from a page with the maths' code and the live disc's stub, so every byte of
  the code is where the free disc has it, and the check's cycles are the
  disc's. `tools/objectcheck.mjs` lets the pipeline patch its code only with
  its bank (or ANDY) paged, and fails a view that runs anything in sideways
  RAM but its own code, the bank's with the bank paged and ANDY's with ANDY;
  its stages, calls and profile tell ANDY's addresses from the bank's.

The figures (the bank's room before and after, ANDY's, what a frame pays on
the check and on both discs, the boot) are in the journal's entry for track
AB.

## The eighth round (track AB)

With the room ANDY freed, track AB took the seventh round's first lever, the
candidates that draw nothing, profiled as before (`--profile-walks`,
`--compare`, and `--candidates`, new: each candidate's cycles from its turn
in `objects_frame`'s loop to the next's, those that draw nothing apart). The
figures, before and after, by stage, step and turn, and the live discs', are
in the journal's entry for track AB.

Kept:

- **A candidate beyond the view's sides passed over** before its transform
  (the transform's bounds, above; proposed below). Studied first in the
  model against the 6502's own cycles a candidate: of the walks' candidates
  that draw nothing, every vertex in one of code3's half-spaces (x = ±z, 2y =
  ±z) caught a minority of their cycles, the view's own side planes (x =
  ±(XC / FX) z, y = ±(YC / FY) z) nearly all, and the planes of small
  coefficients just outside those (3x + 2z, 2z − 3x, z − 3y, z + 3y) as many
  at the median; the side planes most of it, the bottom least. The bounds
  are a box's corner plus the edges that raise them, or a generic object's
  vertices' greatest, kept with the cache: a step pays three compares a
  candidate; a turn pays them as each object is filled, which views with
  nothing to pass over feel (the journal's entry has the figures).
- **A level camera's fill_point** by its known zeros, and **a generic
  object's repeated vertex** (a pointed pyramid's apex, three times over:
  most of Driller's eight-vertex objects) by a copy of the slot before,
  which the bounds' cost on a turn made worth doing.

Measured and not kept:

- **The bounds in a pass of their own** after the fill (each slot read back
  from the cache): slower than making them from the fill's own vector as it
  comes.
- **The bottom of the view** (z + 3y): it caught the fewest candidates that
  draw nothing, for a large share of the bounds' cost on a turn.

What's left:

- **A turn's fills**: every candidate is filled afresh on a turn, and its
  bounds with it, so a turn of a busy view with nothing beyond its sides
  (a tilted camera's most: no level fast path) pays for them; a pyramid's
  base as a box's corner and edges, and a level camera's y edge as a shift,
  would take some back.
- **The lines** (C's two products of sixteen bits by sixteen, `im_term`),
  the cone's passes' products, and **the projection's overheads**, as the
  seventh round left them; and **the floor**, still the largest face.

## The ninth round: the turn's rotation

The coordinator asked whether rotation could be cheaper, the turn being
the costly case (the cache refilled). Profiled first, on the entrance views
(`--profile-turns`, new) and on the check's yaw sweeps (`--profile-views`,
new; each view after a sweep's first is one 5° turn with the camera kept,
the disc's own turn, now reported as its own group), and with `--fills`
(new: each fill's cycles by the object's kind). A turn's transform was
mostly not the products: the bounds (`bd_eval` and the rest) were the
largest part, then the fills' stores and bookkeeping; a pyramid's fill took
about 5K, a cuboid's 2K. All of it is exact: the model's pictures and every
stage's output are unchanged. The figures, before and after, by stage and
group, are in the journal's entry of 2026-11-06.

Kept:

- **The bounds from the cells, before the fill** (stage 3, above): a
  candidate passed over on a turn is never filled, and a box's bounds are
  seven or nine products of a cell by a coefficient instead of a 24-bit
  evaluation of the corner and each edge. Kept at 64 times their sums, so a
  step's three compares are still mostly of top bytes: the sums' own top
  bytes are nearly always equal, and comparing them cost a step about 500
  cycles, measured, against a shift an object on a turn.
- **A step's candidates past the unfilled path**: a good cache has good
  bounds, so a step's candidate takes one stamp's test, as before.
- **A level camera's fills by patched bases**: each product 64 u m read at
  f64's `u + 64 + m` and `u + 64 - m` with the cell in X and the bases
  patched once a turn (`fill_patch`), into the cache directly, so the
  indices' arithmetic and the copy from `fill_acc` go.
- **A level camera's matrix by no products** (the yaw's rotation), its image
  columns by two, its M c by four of `mul`, and the bounds' middle column
  (L's and R's terms 0, T's -192) left as the last level camera's patch had
  it. `bound_patch` writes a level camera's six other terms out and takes
  any other camera's nine by one routine, for the bank's room.

Counted and not built:

- **Rotating the cached results by the turn's 5°**, x' = c x - s z, z' =
  s x + c z on each cached vector: four products of a 24-bit coordinate by
  a byte, three byte products each by quarter squares, so about twelve a
  vector, where a level camera's fill takes four from the cells for a point
  and two for an edge. And it isn't exact: M for yaw + 1 isn't the 5°
  rotation of M for yaw in bytes, so the cache would drift from the model's
  M v. The fill from the cells is the cheaper rotation.
- **The polar form** (portalc's, `rtw-sources.md` 1.2): a turn becomes table
  look-ups, but every step makes each point's polar form again (about 370
  cycles a point by Rich's figures, against the step's 24-bit
  subtractions now), it's good to about a pixel against the projection's
  sixteenth, and the cone needs camera-space x and z, so it would be a
  second path beside this one.
- **Log and antilog products**: a quarter-square product is already three
  table reads and subtractions a byte, exact; logs of the same width are no
  fewer reads and miss.
- **A pyramid's vertices by additions** (each after the first of its base
  and its apex one axis from the one before): two products a vertex fewer,
  for a 24-bit addition, saving a few dozen cycles a vertex.

What's left:

- **The bounds' own cost on a turn**: the shift to 64 times and the copies
  of the cells, about a quarter of `bound_object`; a 64-times quarter-square
  table wide enough for the coefficients (about 1.8K) would take the shift
  away, which the bank's room doesn't take.
- **A level cuboid's fill written out** (its corner and three edges, without
  `transform_fill`'s loop), about a tenth of a turn's transform.
- **A tilted camera's patch**: `bound_patch`'s one routine for nine terms
  costs a pitched or rolled turn about 1.7K more in the matrix stage than
  the old `bound_sel`, though its transform gains more.

## The tenth round: the cone, the vertex pass and the projection

The coordinator asked for the cone (the largest stage of a step), the
vertex pass and the projection to be made faster. Profiled first, on the
walks' steps (`--profile-walks`, `--fine`) and on a heavy cone view, with
each routine's entries counted as well as its cycles. The profile is flat:
no routine of the three stages is more than a few per cent of a step. The
cone's largest part is its lines from images (`image_line`, `im_term`,
`im_w`, about a quarter of the cone), then `side_cut`, the passes and
`image_edge`; a cone face costs several times a face projected whole. All
of what went in is exact: no model change, every stage of every check view
still the model's. The figures, before and after, by stage and group, are
in the journal's entry of 2026-11-06, "the cone, the vertex pass and the
projection".

Kept:

- **`vertex_code3` by 24-bit sums**: each half-space's test is a sum's
  sign, N EOR V past the 24 bits, with no sign bytes made; and z - 2y < 0
  exactly when h - y < 0 (h = z >> 1, z = 2h + r), so 2y isn't made either.
- **`image_line`'s A W and B H written out** (`IM_W`; `im_w` stays for
  `edge_line`), with `im_term`'s coefficient `im_c` being `im_ab`, so that A
  isn't copied.
- **`side_cut`'s shifts written out**, entered by a jump on the shift.
- **`cone_line`'s zero flags** as the coefficient's bytes ORed while it's
  patched, not from the line's bytes again.
- **`drawable`'s zero flags** as the ORs of dx's and dy's bytes.
- **The band test**: its commonest case (z's top byte non-zero) last, with
  no branch out (a page crossed on that branch cost a cycle a vertex when
  the code moved); and below `BAND_MID` (k at most 16) by v's top byte being
  0 or &FF and its middle byte EOR that being under 2^(k - 8), two tables
  fewer. Rare in the check's views, so worth little but room.

Measured and not kept:

- **A unit line's terms without products** (`cone_eval`, A or B of 1: f
  plus or less the coordinate): a few dozen cycles a step at the mean. A
  unit line's vertices are mostly on the sides it's square to, whose terms
  were already skipped (a zero coefficient), and the extra test cost the
  rest.

Counted and not built:

- **The projection's `pmul` written into its blocks**: the case patches
  `pmul`'s eight operands once for x and y both; a copy written into a block
  would need its own eight patches by every case that reaches it, which
  costs more than the call it saves.
- **Coarser lines from images** (`IMAGE_BITS` 8, A and B a byte each, so
  `im_term`, `cone_eval`'s terms and `im_w` take half their products, about
  3K a step at the mean by the counts): measured in the model, 1,182 of
  3,515,200 pixels differ over the entrance views and their walks, in 111
  views, up to 148 in one (a wall's edge two pixels off at the top of the
  view), the draw order the same; 10 bits, 205 pixels, and 12 bits, 19. The
  error grows with the distance from the image the line goes through, which
  can be many views' widths away inside the band, so a near wall's edge
  would wobble as the camera moves. Not proposed.
- **The projection reading the vertex arrays** rather than copies in
  `proj_v`: its shifts work in place, so the bytes it shifts would be copied
  anyway.

What's left:

- **The lines' products**: C = -(A px + B py) is two products of sixteen
  bits by sixteen, and every corner's f needs it; only coarser lines (above)
  make them cheaper.
- **The passes' copies** (`cone_pass` writes each vertex kept to the other
  half) and `side_cut`'s division by reciprocal, a few hundred cycles each.
- **The faces projected whole** (`poly_face`, `drawable`, the 2D clip) are
  together nearly as large as the cone at a step's median; no round has had
  them as its own.

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

From the fifth round (track Q; the pixel figures, against the model before
each and the ZX oracle, are in the journal's entry):

3. **The cone's lines and crossings** (amending decision 33): no line for
   an edge with both ends behind the eye; a crossing on the rectangle's
   side the line's own, rounded half up from the side's corner inside it;
   two consecutive edges' lines meeting at their vertex's projected image
   when the projection takes it; the lines of edges with both ends in front
   first.
4. **The 2D clip's crossings by a reciprocal** (amending decision 24): t
   from a nine-bit reciprocal of the ends' distance and two byte products,
   within about 2^-8 of the division's, still from the inside end.

From the sixth round (track V; the pixel figures, against the model before
it and the ZX oracle, are in the journal's entry, by `render.py --diff
clip.SIDE_RECIP`):

5. **The cone's side crossings by a reciprocal** (amending decision 41's
   side crossings): a line's crossing with the rectangle's side, f(K) / a,
   from the 2D clip's nine-bit reciprocal of a and a product of sixteen bits
   by nine, rounded and at most the side's length (`clip.side_d`), in place
   of an eleven-step division rounded half up; still the line's own point
   whatever the polygon. The draw order is unchanged in every view measured.

From the seventh round (track W; `render.IMAGE_LINES` and `clip.UNIT_SIDES`
together against the model before them, by a run of `render.render` both
ways over the views `render.py --diff` takes, and over all the check's):

6. **The cone's lines from images** (amending decisions 33, 41 and 45): an
   edge whose end the projection takes has its line through that end's
   projected image, not from its plane's normal: through both ends' images
   when the projection takes both, and for a box's edge with one, toward the
   edge's vanishing point (square to (FY dy + v dz, FX dx − u dz), d M's
   column for its axis, (u, v) the image less the view's centre); its
   direction shifted to `IMAGE_BITS`, or a unit when it's square to a side,
   and C exact, so the line passes through the image itself, where a face
   projected whole has that vertex. A unit line's crossing with the side
   it's square to is f there exactly, not the reciprocal's. Other edges keep
   their planes' lines. The pixel figures, over the entrance views and
   walks, every check view and against the ZX oracle, are in the journal's
   entry for track W. `IMAGE_BITS` of 12, 13 or 15 changes them by a few
   pixels at most.

From the eighth round (track AB; `render.OBJECT_CULL` against the model
without it, by `render.py --diff` and by a run of the check's views both
ways):

7. **A candidate beyond the view's sides passed over** (amending decision
   16 with a second test, an object's, after the coarse cull's): a
   candidate with every vertex of its shape where one of 3x + 2z, 2z − 3x
   or z − 3y is negative (camera space; each zero on a plane through the eye
   just beyond the view's left, right or top, so that nothing there can be
   seen) draws none of its faces, which aren't tried. It changes no pixel
   of the entrance views or their walks, nor the ZX oracle's agreement;
   over all the check's views, a few lose a sliver the cone made from an
   object wholly beyond the view. The figures are in the journal's entry
   for track AB.

## What's left

- **The target** (under 100K at a step's median, track W's brief) is met by
  the eighth round (the journal's entry for track AB); its what's left,
  above, has the largest parts (a turn's fills, the cone's lines and
  passes, the projection's overheads, the floor). Then the transform's adds
  (a 16-bit space with a block exponent is picture-free, above).
- **Size**: since ANDY took the cold code ("ANDY", above), the bank has
  room for the hot paths, and ANDY a little more (the build's guards say
  when either doesn't fit); `dedupe` and `stage_pa` could follow if a
  trampoline saved and restored ROMSEL's state.
- **The logic's side**: a build with the logic (`OBJ_LOGIC`, `AREA_GLOBALS`)
  calls `area_enter` after each of its area loads, which builds the
  globals' slots from its records with the rig's parts where it put them.
- **Area entry's cost** is mostly the slanted faces' planes (the cross
  product's products, the greatest common divisor and the divisions) and
  the reading of the records through main RAM; it now also clears the
  sort's memory.
