# The model: Driller's data, the conventions, and the work a view takes

*Track E, 2026-10-31. `tools/freescape.py` reads Driller's database off the
ZX tape; `tools/model/` renders every entrance view with the 6502's integer
arithmetic and counts the work. The model is the renderer's specification
(`docs/engine.md`), so where this file and the code disagree, the code is
right and this file gets fixed.*

Tags as in the brief: **[measured]** means run on 2026-10-31, with the
command named; **[source]** cites ScummVM (`engines/freescape/`), Castle
Master II's annotated Z80 ("CM2") or the ZX track's findings
(`docs/research/zx-driller.md`, "ZX").

## Running it

```sh
make data         # build/data/driller.json, checked
make model        # build/model/aAAA-eEEE.png, counts.json, the summary
make model-check  # tests/model, and the float reference
make model-zx     # the model against the original's views (make zxviews)
```

- `tools/model/render.py DB OUT` renders every entrance view;
  `tools/model/counts.py COUNTS` prints the summary again.
- `tools/model/floatref.py DB` and `tools/model/zxcompare.py DB ZXVIEWS
  [--out DIR]` are the checks against floats and against the original.
- Modules import each other as `tools.model.<name>`; scripts put the
  repository root on `sys.path` themselves, so they run under `python -I`.

## The data

`tools/freescape.py` follows ScummVM's 8-bit loader (`load8bitBinary`,
`load8bitArea`, `load8bitObject`; `games/driller/zx.cpp` for the ZX
retail offsets). It writes every field as the original's byte, unconverted:

- `source`: the tape block, its length and md5, where it loads.
- `tables`: the sine table (`sin`, `cos`, 72 signed bytes each, 1.0 = 64),
  the step and turn tables (`steps` in world units, `turns` in 5° units),
  the matrix's scaling diagonal `scale` and the projection's `centre`, all
  read from the block at the original's addresses (ZX).
- The header: start area and entrance, the 15 shade patterns (`shades`),
  the timer, the initial step and turn indices, the global conditions as
  FCL bytes (hex).
- `globals`: the eight objects outside the areas (the rig, the skanner).
- `areas`: each with its flags (`sky` the low nibble, `ground` the high,
  ScummVM's reading), `scale`, the four colour bytes, the gas pocket, the
  name, its `objects`, and its `conditions` (FCL, hex).
- Objects: `type` and `kind`, the three flag bits, `pos`, `size` (an
  entrance's `rotation`: pitch, yaw, roll), `id`, `length`, `colours` (the
  nibbles, low first), `apex` (pyramids), `vertices` (lines and polygons,
  in cells), `sensor` (colour, interval, range, axes) and `fcl` (hex).

`make data` checks the block's md5 and length against ScummVM's detection
entry, that every area's object walk ends where its conditions start, the
counts `BRIEF.md` measured (`tools/freescape.EXPECTED`), that the sine table
is `round(64 sin)` and `round(64 cos)` of each 5° (which also confirms the
load address), that the initial step and turn are the manual's 250 and 15°,
and that the start entrance exists.

In the data, bits 6 (invisible) and 7 (initially invisible) agree on every
area object [measured]; the globals have bit 7 only.

## The conventions

### Units

- **`CELL = 64`.** An object's byte coordinate `c` is at `64·c` world
  units, the units the camera moves in [source: ZX; CM2 asm:2181-2230].
  ScummVM works in `32·c / scale` instead, and scales the player down.
- **The camera** is the eye: x, y, z in world units, 16-bit, y up; angles
  pitch, yaw, roll in 5° units, 0-71 (`tools/model/camera.py`).
- **An entrance** puts it at `x = 64·ex + 32`, `z = 64·ez + 32` (its cell's
  middle) and `y = 64·ey + 64·L·scale − 32` on the probe, `L` the vertical
  extension, 2 at the start; the angles are the entrance's three size
  bytes, pitch, yaw, roll [source: ZX; CM2 asm:7792-7851]. All 65 match the
  original's placement (`make model-zx`) [measured].

### Axes and angles

- Yaw 0 looks along +z and yaw 18 along +x; camera x is screen right, so
  the world is left-handed with y up [source: ZX; CM2 asm:5252-5336].
  ScummVM's mapping from an entrance's yaw differs between 180° and 270°
  (`traverseEntrance`); no Driller entrance is in that range.
- Positive pitch looks down (CM2's look-down key adds to it, CM2
  asm:9585-9635); ScummVM's positive pitch looks up, and it overrides the
  end screen's entrance pitch to match.
- Positive roll rolls the camera left, so the scene turns clockwise on the
  screen, as ScummVM's roll-left key does; Mitral's rolled entrance (area
  32, entrance 7) matches the original's view.

### The matrix

`tools/model/matrix.py`: `M = Rroll · (Rpitch · Ryaw)`, row-major (camera
x, y, z), 1.0 = 64, each product's sums rounded `(v + 32) >> 6` into a
signed byte, from the original's sine table:

- `Ryaw = [[c, 0, −s], [0, 64, 0], [s, 0, c]]`
- `Rpitch = [[64, 0, 0], [0, c, s], [0, −s, c]]`
- `Rroll = [[c, s, 0], [−s, c, 0], [0, 0, 64]]`

That is the original's composition and rounding [source: ZX, checked
against its `$6EE4`]. The original then multiplies by a scaling diagonal
`S` (`tables.scale`); the model folds `S` into the focal lengths instead,
for precision (the coordinator's deviation to record).

### The transform

`tools/model/transform.py`: `V = M (v − c)`, 24-bit, 64 to the world unit,
nothing shifted (docs/engine.md, stage 3). The cached form (`M v − M c`)
and a cuboid's corner-and-edges sum are checked equal to it on every vertex
of every entrance view (`render.py`'s check mode, `make model`) and on
random cameras (`tests/model/test_transform.py`). The original truncates
each product by 64 and sums in 16 bits (ZX); the model keeps everything.

### The field of view

`tools/model/view.py`:

- `XC`, `YC`: the view's centre, in sixteenths.
- `FX`, `FY`: the original's projection with its `S` folded in,
  `XC·S_x/S_z` and `YC·S_y/S_z`, rounded; `tests/model/test_view.py` holds
  them to the `S` and centre read off the tape. On the ZX that is square
  pixels and a field of `2·atan(S_z/S_x)` by `2·atan(S_z/S_y)` [source:
  ZX]; here it's the same field on the ZX's view at half the width.
  ScummVM's 75° and aspect 2.18 are its own fit, and wider.
- `sx = XC + FX·X/Z`, `sy = YC − FY·Y/Z` (view coordinates: sixteenths, y
  down).
- `ZNEAR`, 4 world units: the original has no near plane (its view
  volume's apex is the eye); this is ScummVM's for Driller at scale 1.
- `tools/model/maths.py`, when it lands, must use these (`parts.py`
  checks).

## What is drawn

The object pass (`tools/model/objects.py`) walks the area's objects and then
the globals, as the original does (ZX; ScummVM puts globals first):

- **Skipped**: entrances and groups; hidden objects (at an area's start,
  those initially invisible; `render(state=...)` overrides by id).
- **Coarse cull**, by compares: a box is dropped when it lies wholly behind
  the camera on an axis along which every direction of the view's cone
  goes the other way (the matrix's ahead row's component at least
  `CULL_K`). The cone is the narrowest about the view axis holding the
  whole view at any roll. It's the original's octant box made exact for
  the field of view; it never drops a drawn face (`tests/model/test_render.py`,
  and 10,920 orientations from the 65 entrances [measured]).
- **Faces**, each a colour and a plane; colour 0 isn't drawn:
  - cuboid: the side bits: the low face on an axis when the camera is
    strictly below the box, the high face strictly above; colours −x, +x,
    −y, +y, −z, +z [source: ZX, CM2];
  - rectangle: the same on its zero axis, colour 0 from below, 1 from
    above; two zero sizes make a line [source: ScummVM];
  - pyramid (six orientations): ScummVM's `renderPyramid` vertices (four
    base corners, four apex corners from the apex bytes) and faces (four
    sides, base, apex), each seen when the camera is strictly outside its
    plane; normals are checked outward on every Driller pyramid;
  - polygon: colour 1 from the side its points wind anticlockwise, colour
    0 from the other [source: ScummVM `renderPolygon`];
  - line: always, in colour 0 (CM2's; Driller's lines have both colours
    equal);
  - sensor: a one-pixel point at its corner in its colour, while it's
    shown, the camera is on a side its axis bits watch (the side bits) and
    the Manhattan distance is under its range [source: ZX `$7592`, read
    2026-10-31 in the annotated listing]. ScummVM draws none.
- The plane tests are exact on integers. The original instead tests the
  turn of a face's first three projected points (ZX), which differs only
  for faces seen edge-on or so small their points fall in line.
- **A face is drawn** if anything with area is left after the near clip,
  the projection and the 2D clip. An object with a drawn face joins the
  draw list, as the original's do (CM2 asm:3574-4045).
- A line is drawn as the polygon a one-pixel line covers (half a pixel each
  way across its major axis); a sensor's point as the pixel round it.

## The order

`tools/model/order.py` is ScummVM's `sortObjectsForRendering` and
`compareBoundingBoxAxis`, which is CM2's `L9c2d` and the ZX's `$767E` case
for case [source: ZX, checked against the original]: up to `n − 1` bubble
passes over the draw list, comparing header boxes relative to the camera
axis by axis, keeping a pair only when the second is nearer on some axis and
the first on none. `tests/model/test_order.py` checks it against a second
transcription of CM2's Z80, sign bit by sign bit, on random lists. The
result runs far to near; the renderer takes it nearest first (decision 3).

Because incomparable pairs swap, the order depends on which objects are in
the list, so membership has to be the original's: drawn objects only, in
the object pass's order.

## Background

The original clears its buffer to paper before drawing when the area's
flags are non-zero, and doesn't clear interiors (flags 0), whose walls
cover the view (ZX). ScummVM fills the view with the sky colour index
(`drawBackground`) and draws object 0 first as a floor when the area has
both colours; no Driller area has an object 0, so the ground is always the
area's ground cuboid, sorted like any object. The model passes the
rasteriser no horizon (sky everywhere) and `colours.sky(area)`; a horizon
splitting sky from ground, as `docs/engine.md` stage 9 sketches, would show
the ground colour between the platform's far edge and the horizon, where
the original shows paper.

## The parts other tracks own

`tools/model/parts.py` is the one switch: for each of `maths`, `raster`,
`writer` and `colours` it takes the real module if its file is there, else
the stand-in in `tools/model/standin/`. The model calls:

- `maths.project(X, Y, Z) -> (sx, sy)`, with `FX`, `FY`, `XC`, `YC` and
  `ZNEAR` equal to `view.py`'s (`parts.py` checks any it defines);
- `raster.rasterise(faces, sky, ground, horizon=None) -> lines`: faces
  nearest first as `(pattern, polygon)`, a pattern four bytes, a horizon
  `((px, py), (dx, dy))` with sky to the left of the direction on the
  screen; each line's runs `(x0, x1, pattern)` covering `[0, VIEW_W)`.
  The stand-in also fills a `stats` dict (face lines, runs put in, full
  lines) when asked;
- `writer.write(lines) -> bytes`, the view in the screen's layout relative
  to `VIEW_ADDR` (and `decode`, if it has one, for pictures);
- `colours.pattern(area, index)`, `colours.sky(area)`,
  `colours.ground(area)`, and `PALETTE` (logical colour to RGB) if it has
  one.

The stand-ins: an exact division for the projection; a scan converter of
pixel centres with the top-left rule over a span buffer, front to back,
runs not merged; the writer; distinct placeholder patterns.

## Checks against the original [measured, `make model-check`, `make model-zx`]

- **Floats** (`floatref.py`): ScummVM's maths in floats with the model's
  field of view. Over the 65 entrance views, 2,027 projected vertices inside
  the view; the worst is 13 sixteenths of a pixel out (a yaw that isn't a
  right angle); the tolerance is one pixel. Over every yaw at five
  pitch-and-roll pairs from every entrance (190,631 vertices), the median
  error is 0.8 pixels, the 99th percentile 2.7 and the worst 4.0, all from
  the matrix's bytes, which the original shares.
- **The original's views** (`zxcompare.py`, on `make zxviews`): all 65
  cameras placed as the original places them; the objects drawn as many as
  the original's in 64 views (area 27's entrance 22 draws a sliver the
  original's integer points put in line); 99.95% of the 1,294,620 pixels
  away from the model's edges agree with the original's, in the original's
  shades.
- **The draw lists**, read from the original's own after its redraw (its
  list at `($8A9D)`, `$8918` entries; area 2's entrance 16 and area 127's
  entrance 0 left out, which the game can't reach): in 40 of 63 views the
  same objects in the same order with the same face counts; in 22 the same
  objects and order with some object's face count differing (edge-on and
  sub-pixel faces: 891 faces in all against the original's 892); in one
  the sliver above. Recording the list in `views.json` (as `"list"`) lets
  `make model-zx` check it every time.

## The counts

`tools/model/counts.py` defines each (its docstring); `make model` writes
them per view to `build/model/counts.json` and prints the summary.
[measured, the stand-in rasteriser, all 65 entrance views]

| count | median | p90 | max |
|---|---|---|---|
| records walked (area and globals) | 35 | 44 | 44 |
| objects coarse-culled | 2 | 6 | 16 |
| objects transformed | 14 | 18 | 22 |
| objects culled by the frustum after transforming | 3 | 8 | 11 |
| objects drawn (sorted) | 10 | 15 | 19 |
| sort comparisons | 81 | 196 | 324 |
| vertices transformed | 63 | 92 | 121 |
| vertices projected | 43 | 70 | 99 |
| faces seen | 21 | 32 | 46 |
| faces drawn | 14 | 25 | 36 |
| faces near-clipped | 2 | 4 | 5 |
| faces 2D-clipped | 6 | 10 | 17 |
| face lines | 249 | 521 | 878 |
| face lines not yet full | 237 | 434 | 877 |
| runs put in by faces | 228 | 447 | 951 |
| runs written (with background) | 302 | 495 | 951 |
| bytes where two runs meet | 94 | 173 | 424 |

The p90 is the nearest-rank 90th percentile. Every view writes all
`VIEW_BYTES × VIEW_H` of its bytes.

## Differences from the original, proposed as decisions

1. **The face tests are exact plane tests** on the world's integers, where
   the original tests the turn of the first three projected points. Same
   faces except edge-on and sub-pixel ones (above).
2. **A line is the one-pixel-wide polygon round it, a sensor the pixel at
   its point**, so the rasteriser takes only polygons; the original walks
   its own line routine (ZX `$85FF`).
3. **A near plane** at `ZNEAR`, where the original clips to a pyramid with
   its apex at the eye; it changes nothing an entrance view shows.
4. **No horizon**: the background is the sky pattern everywhere, as the
   original's paper and ScummVM's sky are; a ground colour below a horizon
   would differ from both.
5. **The coarse cull** is the model's cone test, not the original's octant
   box; both only drop what draws nothing, so images don't change, only
   the counts' split between culled and frustum-culled.

The pixel-centre fill rule, the projection to sixteenths and `S` folded
into the focal lengths are the design's and the coordinator's.
