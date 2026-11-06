# How the engine works

*The design, written 2026-10-31 before any code; keep it true as the code
lands. Every stage has a Python version in `tools/model/` and a 6502
version in `src/`, and the two must agree byte for byte. Where this file
and the model disagree, the model is right and this file gets fixed.*

The goal (decisions 2 and 5): **Driller in many colours on a BBC Master, as
fast as the machine allows.** The target is a median entrance view in two
fields (25fps) and the busiest in three (16.7fps), measured in jsbeeb.

## 1. The machine and the screen

- **BBC Master 128** (65C12, MOS 3.20), decision 5. The 65C12's
  instructions are used freely (`STZ`, `BRA`, `PHX`, `(zp)`, `TSB`/`TRB`,
  `INC A`).
- **MODE 2, set in the hardware** (never an OS mode change), with the
  CRTC narrowed to **R1 = 64: 128 pixels across, 512 bytes a character
  row.** Moving down a character row adds 2 to an address's high byte.
- **The screen is Driller's 192 lines**, as the ZX's: the view and the
  panel below it. **R6 = 24 character rows** (`SCREEN_ROWS`), from
  `SCREEN` to the top of RAM, so each buffer is 12K and main and shadow
  RAM's `&3000` up to `SCREEN` are the engine's (section 8).
- **The screen is double-buffered in main and shadow RAM at one address.**
  ACCCON's X bit picks which one the CPU writes, and its D bit which one
  the CRTC shows. They swap as soon as a frame is done and the CRTC isn't
  fetching the view's lines, mid-field. That works because everything
  outside the view is the same in both buffers. Code and tables that run
  while drawing never live in `&3000-&7FFF`, which X switches.
- **The view is 104 × 104 pixels**: the ZX's 208 × 104 at half the width,
  with the ZX's field of view (decision 2). That's 52 bytes by 104 lines,
  13 character rows. Its left edge is on a byte. `VIEW_W`, `VIEW_H` and
  the focal lengths are build constants in one place, so the view can
  change size.
- **A MODE 2 byte is two pixels.** The left pixel's colour bits 3-0 are
  in bits 7, 5, 3 and 1; the right pixel's in bits 6, 4, 2 and 0 (masks
  `&AA` and `&55`; `mode2_byte(l, r)` in `src/defs.6502`).

### The frame loop and the screen, as built

`build/freescape.ssd` (`src/main.6502`): `!BOOT` runs `FS` at `&0E00`,
which owns the machine and makes no OS call.

- **Set-up** (`start`): both buffers cleared, then MODE 2 in the hardware
  (`screen_init`): the palette with logical colour n physical n AND 7
  (MODE 2's eight; 8-15 the same, steady), the ULA's `ULA_MODE2` and the
  CRTC's `CRTC_R0`-`CRTC_R13` (`src/defs.6502`). The screen's centre is
  where MOS 3.20 puts MODE 2's at `*TV 0,1`, across and down (`CRTC_R2`
  and `CRTC_R7` move the syncs by half of what R1 and R6 take off),
  whatever the CMOS says (decision 9). Then
  `irq_install`: IRQ1V taken, and every VIA interrupt off but two: the
  vertical sync's, and User VIA T1's. Anything else goes on to the OS's
  handler. T1 runs free with a field as its period, started in step with
  the sync, so it times out at `FLIP_LINE` (just past the view) every
  field. Its count says where the beam is, whatever any interrupt's
  latency.
- **The protocol** (`src/screen.6502`), which the renderer calls:
  - `frame_begin` waits while `frame_ready` is set (the frame last
    handed over isn't shown yet), then selects the buffer not shown with
    ACCCON's X; `draw_buffer` names it.
  - `frame_end` shows the frame at once (`flip`: D to `draw_buffer`) in
    two cases: the frame shown now has had its view shown whole
    (`view_shown`), and T1 puts the beam outside the view, at least
    `FLIP_LEAD` lines short of its top. Otherwise it sets `frame_ready`,
    and T1's interrupt (`src/irq.6502`) flips as the view's last line
    goes. Either way every frame is shown whole at least once, and a
    frame that takes 2.3 fields is shown every 2.3 fields, not every 3.
  - Write the view only between the two, and call `frame_begin` as late
    as possible: stages 0-9 write nothing on the screen, so they run
    while the last frame waits for its flip.
  - **Outside the view, both buffers must hold the same at every flip**,
    because a field can show those lines from either buffer. A change
    there (the panel, text) goes into both buffers, X selecting each in
    turn, before the frame that goes with it is handed over. The shown
    buffer's copy shows at once. To keep it from showing half made for a
    field, write it while T1's high byte is at most `HI(SAFE_T1)` (the
    beam in or just above the view's lines). Or keep such a part in one
    buffer and show it from there with D, set at the view's end and back
    before its top: one more interrupt a field, and one copy to write.
  - X and D are changed only by `TSB` and `TRB`, which an interrupt
    can't split, so neither side undoes the other's bit.
  - Interrupts may be held off for anything short of a field: a late
    interrupt only delays the flip, which reads T1 first and so never
    lands in the view. A field or more misses a sync.
  - `-D VSYNC_FLIP=TRUE` (`build/freescape-vsync.ssd`) builds the
    simpler flip, by the vertical sync's interrupt in the vertical blank.
    Interrupts may then be held off for no more than `FLAG_TO_TOP`
    lines, and T1 isn't used.
- **Counters** (in `Work`, `src/zp.6502`): `fields` (vertical syncs),
  `frames` (flips) and `frames_drawn` (`frame_end`s), 16 bits each, for
  measuring. Read them between frames.
- **The keys** (`src/input.6502`): the interrupt reads Driller's keys
  from the System VIA into `keys` (held) and `keys_made` (gone down since
  `key_take`), a bit each: `K_FORWARD` and the rest. It reads them only
  while one is held or auto-scan has found one, and then a keyboard
  column's keys only when CA2 says the column has one down (2026-11-06).
- **Zero page**: `frame_ready`, `draw_buffer` and `view_shown` are
  fixed below `ZP_FIXED`; baron's pool is the rest up to `&FB`.
- **The test scene** (`src/main.6502`, until the renderer replaces it):
  bars of the eight colours moving a pixel a frame in the view, inside a
  white border, and the screen's edge in cyan.
- **Checked** by `make frames` (`tools/frames.mjs`, on jsbeeb's full
  video, for both builds). It checks the registers and the picture
  against the MOS's own MODE 2. Each flip must:
  - land while the CRTC isn't fetching the view (the VSync build: in the
    vertical blank);
  - show the one frame handed over, byte for byte, after the frame it
    replaces was shown whole;
  - find both buffers the same outside the view.

  Every write to the view must be inside a frame and to the buffer not
  shown. Every sync and flip must be counted, and every key must set its
  bit. It reports the pace both ways.

## 2. Colour

- Each face of each object has a colour index 1-15 from Driller's data (0
  means "not drawn").
- **Each index is a pattern: four bytes, one for each value of
  `line AND 3`.** Each byte is two pixels, so a pattern is a 2 × 4 ordered
  dither of up to three of the BBC's eight colours, or a solid colour
  (decision 8). Patterns are anchored to the screen, not the
  face.
- The table of patterns, and where its colours come from, is the colour
  study's (`docs/research/colour.md`, decision 8). Until then the model's
  `colours.py` holds a placeholder, and nothing else depends on its
  values.
- A pattern one byte across costs nothing extra to fill (section 4,
  stage 10). Patterns two bytes across (a 4 × 4 Bayer) would cost every
  byte more, because the 6502 has no indexed `STX` or `STY`.

## 3. The data

- `tools/freescape.py` reads Driller's database from the fetched ZX tape
  into JSON (`make data`), checked against ScummVM's parse.
- The BBC keeps the database itself, the ZX's bytes, in the player
  logic's sideways RAM bank, and entering an area builds its objects from
  it into the engine's working copy (`src/area.6502`, modelled by
  `tools/mkareas.py`): their kind, box, colours and vertices, laid out for
  the object pass (stage 2). What the ZX's database hasn't, the faces'
  colours in the version decision 8 follows, comes from a table the build
  makes from the originals.
- **Units.** Object positions and sizes are bytes in the original's cells.
  The engine's world unit is the one Driller's camera moves in, so an
  object's corner in world units is its cell coordinate times a constant
  `CELL`, **64**, as the original's (`docs/research/model.md`, "Units").
  The camera's position is the eye, in the same units, 16-bit; an
  entrance puts it at its cell's middle across, `64·L·scale − 32` above
  the cell's floor (`L` the probe's extension, 2 at the start).

## 4. The frame

In order. Formats are the model's; the 6502 matches them exactly.

0. **Camera.** Position `(cx, cy, cz)`, 16-bit unsigned world units.
   Angles yaw, pitch and roll, each 0-71 (5° steps, the original's).
1. **Matrix.** Nine signed bytes, 1.0 = 64, from the original's sine
   table, built only when an angle changes. The model fixes the order of
   composition and the rounding, following the original where it's known
   (Castle Master II's yaw × pitch; Driller adds roll).
2. **Object pass.** For each object in the area:
   - skip it if it's invisible or destroyed;
   - a coarse cull: its box wholly behind the camera or outside the view's
     wedge, by compares;
   - its visible faces: for a cuboid, which side of each slab the camera
     is on (free back-face culling); for a flat shape, one compare
     against its plane; for others, the model's rule.
3. **Transform, kept exact so it can be cached.** A camera-space vertex is
   `V = M · (v − c)` **without a shift**: 24-bit signed, 64 to the unit.
   Projection needs only ratios (`X/Z`, `Y/Z`), so the scale never comes
   off.
   - `M · v` is kept for every vertex of an object while the orientation
     is unchanged, and a frame computes `M · c` once (nine products) and
     subtracts it. A step that only moves the camera costs three 24-bit
     subtractions a vertex and no products. The result is identical to
     computing it afresh, because nothing is rounded.
   - When the orientation changes, a cuboid's eight vertices come from
     `M · corner` and three rotated edge vectors by additions, as the
     original builds them. A pyramid's and a polygon's come from their
     own vertices the same way.
4. **Which faces project whole.** Each vertex of an object's seen faces is
   tested once against the band the projection takes: in front of
   `ZNEAR`, with X within `2^(n+3)` and Y within `2^(n+2)`, n the bit length
   of Z (inside the guard band, decision 17; a byte or two's test). A face
   with every vertex in the band is projected (stages 5 and 6). Any other
   polygon goes through **the cone**: the view's rectangle clipped, in 2D,
   by its edges' planes through the eye, each a line on the screen, exactly
   the face's image with nothing cut away (`tools/model/clip.py`), so there
   is no near plane for polygons, and no far plane. An edge with an end the
   projection takes has its line through that end's projected image:
   through both images when it takes both, or a box's edge toward its
   vanishing point (proposed, `render.IMAGE_LINES`); any other edge's comes
   from its plane's normal. An edge with both ends
   behind the eye has no line (the image is inside its plane already); a
   line's crossing with a side of the rectangle is that line's own, by the
   2D clip's nine-bit reciprocal (decision 45), or exactly for a line square
   to it; and two consecutive edges' lines meet at their shared vertex's
   projected image when the projection takes it. A line or a point with
   an end outside the band is clipped in 3D to `ZNEAR` and the planes
   `x = ±z`, `2y = ±z` first.
5. **Project.** `x = XC + FX · X / Z` and `y = YC − FY · Y / Z`, in
   sixteenths of a pixel (section 9), by a 9-bit reciprocal of Z and two
   byte products (`src/project.6502`, `docs/research/projection.md`,
   decision 27): never stepping backwards as X or Z grows, within 4/16 of
   a pixel. Vertices sharing Z, or X and Z, take the cheaper `project_z`
   and `project_y`, with the same results. `ZNEAR` and the focal lengths
   are `tools/model/maths.py`'s. Each vertex is projected once, before the
   faces, in an order that puts vertices sharing X and Z (a box's vertical
   edges, under a level camera) or Z together.
6. **2D clip** of each projected face against the view's rectangle, unless
   its outcodes say it's wholly inside (taken as it is) or wholly beyond
   one edge (dropped), so every vertex the rasteriser sees is inside the
   view.
7. **Order.** The original's sort (ScummVM's `area.cpp` reproduces it) over
   the drawable objects, then taken nearest first (decision 3). The faces
   of one convex object don't overlap once its back faces are gone, so
   their order within it doesn't matter.
8. **Spans, front to back.** Each face is scan-converted row by row, by
   the model's fill rule (which pixel centres a polygon covers). Each row
   of the span buffer is a sorted list of covered runs, each with its
   pattern. A face's run on a row is clipped against what's there, and
   only the uncovered parts go in. A full row is skipped with one test,
   and the frame stops scanning once every row is full.
   - Painting back to front leaves each pixel the last face painted over
     it. Front to back, it takes the first face to claim it, which is the
     same face. So this gives exactly the painter's image, for any order,
     and writes each screen byte once.
9. **Background.** What's left uncovered is sky above the horizon and
   ground below it, in the area's colours. The horizon is a line, tilted
   by roll and moved by pitch.
10. **Write the rows.** Each row of the span buffer is then a full
    partition of the view's row into runs.
    - Whole bytes are written by unrolled row-run code: a routine per
      character row of `STA abs,Y` (Y the line within it), one per byte
      column, entered at the run's first byte with an `RTS` planted after
      its last (Solid Elite's way). 5 cycles a byte.
    - A byte where two runs meet takes `left AND &AA OR right AND &55`
      of the two patterns. Nothing on the screen is read, because the row
      is written whole.
    - No clear and no copy.
    - A line is skipped when the buffer already holds it: the back buffer
      still has the frame from two frames ago, and a record for each buffer
      and line says what that left there when it was one run, the
      background alone or one face's piece across the whole line, in what
      byte (`docs/research/raster.md`, "What the screen already holds").
      The sky and the floor mostly survive a step or a turn. Lines of more
      than one run are written whole: their records would need room the
      memory hasn't (`docs/research/raster.md`, round 5).
11. **Flip** as soon as the CRTC isn't fetching the view: ACCCON D set to
    the buffer just drawn, at once by `frame_end` or by T1's interrupt
    as the view's last line goes (section 1, as built).

Round the frame, the logic (`docs/research/logic6502.md`) and the panel
(`docs/research/panel.md`): Driller's instruments round the view, drawn
into both buffers in the beam's window as the logic's variables change.

## 5. Checking

- **Stage by stage.** Every 6502 stage has a check that writes its inputs
  into memory in headless jsbeeb (`tools/run6502.mjs`, on jsbeeb's
  TestMachine), calls the routine from a stub, reads its outputs back and
  compares them with the model's, exactly. Cases come from the model's
  run over every entrance view, plus edge cases each track adds.
- **Whole frames.** The spike renders every entrance view and scripted
  walks; its view bytes must equal the model's render of the same camera,
  byte for byte.
- **The model against the original.**
  - Geometry: the model's integer pipeline against a floating-point
    reference of the same views (ScummVM's maths), within a stated
    tolerance.
  - The image: against the ZX original run headless (`tools/zx.py`), by
    running the model at the ZX's 208 × 104 in the ZX's patterns and
    comparing its buffer with the ZX's, once that oracle exists.

## 6. Measuring

`make bench`: every entrance view and a scripted walk through each area,
headless, with jsbeeb's cycles a frame as a distribution and each stage's
share (cycles between the stages' labels), and a sampling profile on
request. It's the proof of the engine, so every optimisation round reports
against it. The model's counts (vertices, faces, face-rows, runs, bytes)
come with it, to see where the cycles go.

## 7. Where things live

| Path | What |
|---|---|
| `tools/freescape.py` | Driller's database to JSON |
| `tools/model/` | the model: `camera`, `matrix`, `objects`, `transform`, `clip`, `project`, `order`, `raster`, `writer`, `colours`, `render` (a whole view), `counts` |
| `tools/run6502.mjs`, `tools/beeb.mjs`, `tools/play.mjs` | the harness: headless runs, MCP sessions, scripted play |
| `src/*.6502` | the engine, one file per stage, named as the model's modules |
| `mk/*.mk` | each track's Makefile rules, included by the Makefile |
| `originals/` | the fetched originals (never committed) |
| `build/` | everything made (never committed) |

## 8. Memory (Master)

- Zero page: baron's allocator (`ZA_AUTO`), with long-lived state in fixed
  locations.
- `&0400-&0CFF`, the OS's pages: the engine's variables (`Work`), the
  globals' records their slots were built from (`AreaKeep`), and the
  rasteriser's input, which the object pipeline's output lies over. The
  last page of that input holds the patterns, of which the disc uses
  `LIVE_PATTERNS`; the rest of the page (`RASTER_SPARE`) holds the fill's
  line heads and scratch bytes (`RASTER_HEAD`, `RASTER_SCRATCH`) and what
  they leave is room.
- Page `&0D` below `&0D9F` (the Master's extended vectors, which a soft
  BREAK reads): the live disc's start, which runs once, once the disc is
  done with.
- `&0E00-&2FFF`: the engine's main code, and whatever is read whatever
  ACCCON's X and whatever bank is paged: the interrupt, the code that
  pages, the rasteriser's state, the player logic's variables
  (`LogicWork`, `docs/research/logic6502.md`), the maths' code (which
  patches itself).
- `&3000` up to `SCREEN`: what ACCCON's X selects, main RAM's or shadow
  RAM's. Data kept per buffer (section 4, stage 10) needs the same
  addresses free in both. The live disc keeps the front end's data in main
  RAM's (the transform's cache, the sort's memory, the pipeline's tables
  and the area's working copy), reached with X clear, as the front end
  runs (decision 31), and the logic's lists by face in shadow RAM's,
  reached with X set, as its passes run. No code goes there. The matrix's
  products read the maths' quarter squares in HAZEL and its cosines are the
  sine table a quarter turn on, the sort's memory is exactly its pairs, and
  the working copy keeps no object id, so the room before `SCREEN` is what
  `docs/journal.md` (2026-11-06, room in main RAM) counts; shadow RAM's
  past the logic's lists is free but the front end can't reach it.
- `SCREEN` to `&7FFF`: the screen, `SCREEN_ROWS` character rows (Driller's
  192 lines) in each of main and shadow RAM.
- HAZEL (`&C000-&DFFF`): tables (squares, reciprocals, the transform's
  f64 table) and the front end's work. The maths' quarter squares serve the
  logic and the fill too, and its doubled bit lengths (`proj_bl2`) the
  fill's edge set-up (`RASTER_BL2`). HAZEL holds the filing system's workspace until
  the OS is gone, so nothing goes in before.
- The fill's bank (6) holds the row runs, its code and its work. Its
  routines are fewer on the live disc (no horizon: decision 71), and the
  room it has is from `raster_work_end` to `&C000` (`docs/research/raster.md`,
  "Round 6"); the 96 bytes after each row's run in the row runs' pages are
  room besides.
- Sideways RAM banks 4-7: the code, and the database. The player logic
  has two: `LOGIC_BANK`, Driller's database in the original's layout and
  the code that reads it, and `LOGIC_CODE_BANK`, the rest of the logic,
  with room to share. The renderer reads the database too, as it enters
  an area (`src/area.6502`).
- ANDY (`&8000-&8FFF` with ROMSEL's bit 7, in place of the paged bank's
  first 4K): the front end's rarely run code, reached through trampolines
  in main RAM (decision 52, `docs/research/objects.md`, "ANDY").
- Not used yet: parts of the OS's pages, free once the engine owns the
  machine (`docs/research/live.md`, "Room").
- The disc puts it all there: `!BOOT`, the loader (`src/loader.6502`),
  reads the packed parts from one other file a track at a time and unpacks
  each into its place, HAZEL's, ANDY's and page `&0D`'s once the OS is gone
  (`docs/research/live.md`, "The disc").

The tracks size these as they go. The live disc's map, the whole engine
in one build, is `src/live.6502`'s, every boundary ASSERTed
(`docs/research/live.md`, "Memory", decisions 31 and 40).

## 9. The interfaces between the stages

The model's, which the 6502 mirrors. Tracks working at once code to these;
a change is agreed and recorded here first.

- **View coordinates**: x right, y down, relative to the view's top left,
  in **sixteenths of a pixel** (`SUB = 16`), as integers. Pixel `(px, py)`
  has its centre at `(16·px + 8, 16·py + 8)`.
- **The fill rule**: a polygon covers a pixel when the pixel's centre is
  inside it. A centre exactly on an edge counts for top and left edges
  and not for bottom and right ones. A sloping edge's boundary on each
  line it crosses is a DDA's (`tools/model/raster.py`'s `edge_crossings`),
  at most a pixel from the exact one and never past the edge's far vertex.
- **`maths.project(X, Y, Z)`** (`tools/model/maths.py`): camera-space
  24-bit signed integers (stage 3's), `Z >= ZNEAR`, to `(sx, sy)` in view
  coordinates, which may lie far outside the view. The focal lengths and
  centre are parameters (`FX`, `FY`, `XC`, `YC`, in sixteenths).
- **The rasteriser's input** (`tools/model/raster.py`):
  - the background: a sky pattern, a ground pattern, and the horizon as
    a point and a direction in view coordinates, sky to the left of the
    direction as seen on the screen; or no horizon, all sky;
  - the faces, **nearest first**, each a pattern and a convex polygon
    whose vertices are view coordinates inside `[0, 16·VIEW_W] ×
    [0, 16·VIEW_H]` (after the 2D clip), in either winding;
  - a pattern is four bytes, one for each value of `line AND 3`, each
    the MODE 2 byte for the two pixels it covers.
- **The rasteriser's output**: for each line `0 .. VIEW_H − 1`, its runs
  `(x0, x1, pattern)` in pixels, in order, covering `[0, VIEW_W)`
  exactly.
- **The writer** (`tools/model/writer.py`): the lines' runs to the view's
  bytes, in the screen's layout: line `y`, byte column `c` is at
  `VIEW_ADDR + (y DIV 8)·SCREEN_ROW + 8·c + (y MOD 8)` (`src/defs.6502`).
- **Patterns from colours** (`tools/model/colours.py`):
  `pattern(area, index)` for a face's colour index, and `sky(area)` and
  `ground(area)`, each four bytes.
