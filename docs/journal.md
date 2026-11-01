# Journal

How the project got here, in order. What worked, what didn't, and why.

## 2026-10-31: the brief

Research into Freescape, Driller's versions and the BBC's fastest solid 3D
(`docs/research/`) led to `BRIEF.md`. Matt then asked for four colours to
be considered, then MODE 2 and ordered dithering, then "many colours and
as fast as you can make it", working autonomously with agents. That made
decision 2 (MODE 2, a 104 × 104 view at the ZX's geometry) and the design
in `docs/engine.md`.

## 2026-10-31: the screen and the frame loop (track A)

`build/freescape.ssd` boots on jsbeeb's Master into MODE 2 set in the
hardware, double-buffered in main and shadow RAM, with a test scene in
the view (`docs/engine.md`, section 1, "as built"). Measured that day
with `make frames` (jsbeeb's full video, 10s a run):

- The test scene writes its whole view a frame. It runs at 24.97 frames
  a second, every frame shown for 2 fields. Each frame spends 55,769
  cycles between `frame_begin` and `frame_end` and 20,520 waiting in
  `frame_begin`. That wait is what a renderer gains by putting its stages
  0-9 before `frame_begin`.
- With its cost varied at random, 322 frames in 502 fields were shown
  for 1, 2 or 3 fields (155, 152 and 14 frames). All 573 flips landed in
  the vertical blank, at least 30 lines before the next line shown. All
  2,317,952 screen writes went to the buffer not shown.
- The interrupt takes 80-109 cycles a field with no key held, and about
  1,000 while one is (the 28 keys read one at a time).
- `FS` is &371 bytes, the test scene about a third of it.
- MOS 3.20's MODE 2 puts the vertical sync at row 35 with `*TV 0,1`,
  where OS 1.20's table says 34. MOS 3.20 adds the `*TV` setting plus
  one, read from its ROM's table and the CRTC after `*TV 0`, `1` and
  `255`. The disc follows MOS 3.20.
- A soft BREAK while the disc runs puts IRQ1V back to MOS 3.20's and
  returns to BASIC in MODE 7, on jsbeeb.
- `make frames` was checked against deliberately broken copies, each of
  which it failed:
  - no wait in `frame_begin`;
  - the flip to the wrong buffer;
  - a flashing palette entry;
  - a key mapped wrong, or not read;
  - `frame_end` before the writes;
  - the view drawn a byte off;
  - R7 a row out, and interlace on;
  - interrupts held off for longer than the flip's window, and for
    longer than a field;
  - an interrupt longer than a field.

## 2026-10-31: the ZX oracle (track D)

Driller's ZX tape loads headless in SkoolKit's simulator, past its copy
protection and menu, to the main loop in play (`tools/zx.py --boot`).
The original's own redraw then draws any view (`--view AREA:ENTRANCE`),
and `make zxviews` draws all 65 entrance views into `build/zx/views/`.
`docs/research/zx-driller.md` has what it found, with addresses: a cell is
64 world units and the camera's position is the eye; the matrix is
`S · Rroll · Rpitch · Ryaw` in signed bytes, each step rounded; the
projection is `104 + 104·X/Z` across and `52 + 52·Y/Z` up, with `S`
giving both axes the same focal length; there's no near plane, only the
pyramid from the eye; and the sort is ScummVM's but with the area's
objects before the globals. `tools/zx_arith.py` copies the original's
maths, and its check calls the original's own routines on random inputs:
no case differed.

Measured that day (48K timing, with contention and the game's interrupt):
a redraw takes a median of 2,293,923 T-states (0.66s), from 670,879 to
4,273,507 over the 65 views. Projection is 63% of it, the sort 11% and
drawing 26%. The start view matches the frame the game drew at boot byte
for byte.

## 2026-10-31: the data and the Python model (track E)

`tools/freescape.py` reads Driller's database straight off the ZX tape
(`make data`, with its checks). `tools/model/` renders any view with the
6502's integer arithmetic (`docs/research/model.md` has the conventions),
with the maths, the rasteriser and writer, and the colours as stand-ins
until their tracks land (`tools/model/parts.py` switches).

Checked that day against the original (`make model-zx`, `make
model-check`):

- every entrance's camera lands where the game puts it;
- the objects drawn agree in 64 of the 65 views (area 27's entrance 22
  draws one extra sliver);
- 99.95% of pixels away from edges agree with the original's images;
- the projected vertices are within 13/16 of a pixel of a floating-point
  reference in the entrance views, and within 4 pixels over every yaw with
  pitch and roll, all of it from the byte matrix the original shares.

The work a view takes, over the 65 entrance views (median, 90th
percentile, maximum): objects drawn 10, 15, 19; vertices transformed 63,
92, 121; vertices projected 43, 70, 99; faces drawn 14, 25, 36;
face-lines 249, 521, 878; runs written 302, 495, 951; bytes where two
runs meet 94, 173, 424.

## 2026-10-31: the colours (track C)

`make fetch` takes Driller's DOS, CPC, ST and Amiga discs; DOS, CPC and ST
match ScummVM's md5s. `tools/colour/` reads each version's database and
colours, and `make colours` designs the BBC's patterns
(`docs/research/colour.md`). Found that day:

- Every version recoloured the faces: all 669 records match the ZX's by
  id, but 30-45% of face colour indices differ, and 23-33 faces are drawn
  in one version and not the other. So colours come from the followed
  version object by object.
- The EGA uses one fixed 16-colour table; the ST and Amiga 16 colours an
  area from 4,096; the CPC four inks an area. The sky is black everywhere
  but the CPC's Stores; the ground is the floor object's top face.
- Mean and worst error (OKLab × 100) with patterns of up to three colours
  chosen for both displays: the ST 6.1 and 24.4 on an RGB monitor, 4.2 and
  15.8 through PAL; the EGA 3.9 and 6.4, 3.7 and 6.8.
- PAL changes the choice: of the ST's 310 colours, 247 take a different
  pattern when chosen for PAL than for RGB, and the patterns chosen for
  both serve both.
- `tools/pal.py`, the NumPy port of jsbeeb's PAL shader, differs from the
  shader itself (run in headless Chrome) by at most 1/255, in under 1% of
  bytes.

## 2026-10-31: the maths (track F), and the guard band

`src/maths.6502` and `src/project.6502` match `tools/model/maths.py` bit for
bit (`make maths`; all 2^24 products checked once with `--full`). Measured
that day (cycles with the JSR and RTS): a 16 × 8 product 80-123 (mean
98) after `mul_set`'s 68; a three-term dot product 303-358 (mean 329) after
`dot_set`; a projected vertex 441-598 (mean 508). Tables 3,328 bytes in
HAZEL. `docs/research/maths.md` has the variants and their figures.

Merging it showed the model's conservative-cull test failing. With the
real projection, a vertex far to the side of a near one saturates its 16
bits, and the 2D clip then cuts a wrong edge: culled objects hid it, and
drawing without the cull showed it. Faces are now clipped in 3D to a
guard band first (decision 17), and the test passes. The focal lengths are
one rounded integer everywhere.

## 2026-10-31: the player logic (track I)

Driller's player logic is transcribed in `tools/logic/` and checked pass
by pass against the original (`make logic`); `docs/research/zx-logic.md`
has what it does. A pass of the main loop reads up to five keys and does
each one's action in the keyboard's order; a step moves the camera
through the cells a boundary at a time, testing each crossing against the
objects' faces, climbing and falling on the probe; and the areas connect
through FCL, so the interpreter is transcribed whole, its renderer's and
sound's parts left as hooks.

The oracle runs the original a pass at a time with keys held, holding
only the clock and the sensors' fire, and every variable and the whole
database must agree after every pass. What the first fuzzes found:

- a transcription slip (the rise sets its target before testing the
  level), at once;
- that the FCL's REDRAW runs the renderer, the copy and the sensors in
  the middle of a pass, so their outputs, the copy's clearing of the
  pending sound among them, are the original's after such a pass;
- that a minute ending with no energy goes straight to the game's end;
- a bug of the original's: a step ending exactly on two cells' corners
  going down can run the walk past its target and throw the probe out of
  the area (to x 20016), and a move from there hangs the game. The
  transcription hangs in the same place, and the checker requires the
  original to.

Measured that day: the multiplies and the divide against the original's
routines, 2,000 random cases each, none differing; the 22 scenarios,
1,921 passes; and a fuzz of 1,000 walks of 120 passes from random
entrances (seed 100000), 110,359 passes, none differing. Those walks
changed area 537 times (87 across an edge), climbed 189 times, fell 225
times (52 of them too far) and were stopped by an object 4,272 times.

## 2026-10-31: the rasteriser and writer (track G)

`src/raster.6502` and `src/writer.6502` match `tools/model/raster.py` and
`writer.py` byte for byte (`make raster`): 148 synthetic scenes, 7
multi-frame sequences, and all 65 of Driller's entrance views from the
model, with every screen write watched. The design: exact edge stepping in
sixteenths; per-line gap lists in four pools; each piece written at once
through the row runs, every byte once, no screen reads and no clear; a
background line left alone when the back buffer already holds it. A bug
only Driller's real views showed (a span on line 0 stopped after the
line's first gap) is fixed, with regression scenes.

It's correct but too slow. Measured that day on Driller's 65 views: a
median of 138,079 cycles for the rasteriser alone (54,712 to 399,750),
about three and a half fields, against two for the whole frame. The fit
over the views: 95.6 a line, 76.9 a face-line, 271.9 a run, 1.3 a byte and
894 an edge (rms error 6.3%). Runs and edge set-up are the cost. The track
went back to restructure it for speed, free to change the model's fill
method where the picture stays as good (decisions 11 and 12).

## 2026-10-31: Rich Talbot-Watkins's sources

Rich made a set of BBC game sources public that day; a review read eleven
of them for tricks this engine can use (`docs/research/rtw-sources.md`):
PORTAL's source and its polar branch, Rich's optimisation notes, Chase
H.Q., Teddy Boy and its optimisation reviews, Exolon, Critical Mass, flow,
Nevryon, spritescale and beebcrunch. The ranking, against our figures:
flipping as soon as the beam has left the view rather than at the vertical
sync; a level camera's zero and unit matrix entries skipped and one
reciprocal shared by a vertical edge's two ends; PORTAL's polar front end
for turns; reciprocals by lookup for gradients and clips; Chase H.Q.'s and
Teddy Boy's row-run overheads; the sky skip by per-line records. Every
source that skipped work by reading the screen measured it as a loss. Each
item went to the track that owns its stage.

## 2026-10-31: the flip as the beam leaves the view

Rich Talbot-Watkins's Chase H.Q. and Teddy Boy show a frame as soon as
the playfield's last line has gone, not at the vertical sync
(`docs/research/rtw-sources.md`, section 3.1). Built as the frame loop's
default, with the VSync flip one flag away (`-D VSYNC_FLIP=TRUE`). The
design is in `docs/engine.md`, section 1. Measured with `make frames`,
10s a run on jsbeeb's full video:

| Scene | Flip | Frames a second | Fields a frame | Waiting in `frame_begin` |
|---|---|---|---|---|
| The test scene (its whole view a frame) | at the view's end | 33.40 | 1.50 | 479 c |
| The test scene | at the vertical sync | 24.97 | 2.00 | 20,507 c |
| The scene varied (1-13 rows, delays) | at the view's end | 34.00 | 1.47 | 468 c |
| The scene varied | at the vertical sync | 32.10 | 1.56 | 4,544 c |

- The varied scene gains less because many of its frames take under a
  field, and both flips show a frame at most once a field.
- At the view's end, the test scene's frames were shown for 1.40-1.60
  fields each. The varied scene's were shown for 0.42-3.00: a frame
  flipped in the blank above the view and replaced after it is shown
  whole for less than a field.
- Of the test scene's flips, 169 came at once in `frame_end` (lines
  116-275) and 165 by T1's interrupt, all on line 114. No flip came in
  lines 6-113, the view's lines and their margins.
- `make frames` was run against deliberately broken copies again. It
  failed each of these:
  - a flip whatever the beam's place;
  - the T1 time-out 20 lines early;
  - a frame replaced before its view was shown whole;
  - the screen's edge drawn in one buffer only;
  - and every earlier mutation that still applies.

  It passes these, rightly:
  - interrupts held off for 100 lines: the old flip tore there, this
    one only waits;
  - the time-out later than it need be;
  - the handler's lateness guard removed: it only matters past 200
    lines.

## 2026-10-31: the object pipeline (track H)

Stages 1-7 in 6502 (`src/area.6502`, `matrix`, `objects`, `transform`,
`clip`, `order`) match the model exactly over 2,485 views: the 65 entrance
views, a walk from each, and every yaw, pitch and roll at eight entrances
(`make objects`). The area records are structure-of-arrays with every
position a cell, so the cull, the faces' tests and the sort are byte
compares.

Matt asked whether the cached transform pays against a straight
per-frame 3×4 transform. Measured: with the cache, the transform takes a
median 13.9K cycles on a step and 40.1K on a turn; rebuilt every frame it
takes 42.6K either way. So about 28.7K saved on every step frame and
nothing lost on a turn, for 2,304 bytes and a compare an object. The
cache stays.

The stage is correct but slow: a median 321K cycles on a turn and 293K on
a step, nearly all of it the model's exact clipping arithmetic (the guard
band 59K, the 2D clip 48K, outcodes 35K, the projection 25K, an area test
19K). The track went back to make it fast, with authority to change the
model's clipping where the picture stays as good: reciprocal tables for
crossings, outcodes from projected vertices, and the area's floor drawn as
the horizon instead of as a face.

## 2026-10-31: the first disc that draws Driller (track K)

`freescape.ssd` is now a slideshow: `tools/mkslides.py` takes each of the 65
entrance views' raster inputs from the model, `!BOOT` loads the
rasteriser into bank 4 and the views into banks 5-6 (`*SRLOAD ... Q`), and
`src/slides.6502` draws the current view every frame, holding each for 100
fields, with the area's name and the measured frame rate drawn in the
MOS's font below the view, in both buffers inside the beam's window
(decision 21). `make slides` checks it: all 65 views shown, 2,011 frames
each the model's view byte for byte, both buffers the same outside the view
at every flip, the text against the font, and the keys.

Measured that day, flipping at the view's end: a median of 3.2 fields a
frame over every frame (15.65 frames a second), the worst 12.9; views'
medians from 1.05 (Beryl, entrance 25) to 10.18 (Stores, entrance 7).
`raster_frame` takes a median of 126,253 cycles, the worst 401,680.

## 2026-10-31: the rasteriser restructured, and painter's measured

Five rounds on the span buffer (`docs/research/raster.md`): edges by a DDA
(decision 23), the first line's offset from the gradient, cheaper runs,
the background, the rasteriser's own squares. Measured over the 65 views:
the median from 137,564 cycles to 125,118, p90 from 239,476 to 224,082,
the most from 398,746 to 363,191: a tenth. The analysis said why no more:
at the median view the byte stores are 28,641 cycles, and everything
charged to a face-line about 215 cycles each, 51K over 238 face-lines.

So a plain painter's fill was measured with the model the same day: faces
back to front over each other, overdraw included, write a median of 4,952
bytes (the floor 2,542 of them) and 9,002 at most, over 251 face-lines
(879 at most), with 134 partial bytes at odd-pixel edges (695 at most).
Objects sit on the floor rather than in front of one another, so overdraw
is small, and at 5 cycles a byte and a lean ~100 a face-line painter's
should cost about half the span buffer. The picture is the same: the span
buffer only reproduced the painter's image. The track went back to build
it.

## 2026-10-31: the object pipeline's speed round

Measured over the 65 views and the walks: stages 1-7 from a median of
293K cycles to 221K on a step frame (most 351K), and from 321K to 253K on a
turn (most 394K), the model and the 6502 still exact over 2,485 views.
Crossings by one 16-bit fraction, outcodes from the projection, a cheaper
drawn test (decisions 24 and 25); the floor as the horizon measured and
not taken (decision 26). Still about seven times the part's budget, at
about 3.5K cycles a vertex, so a fresh track (M) took the front end on to
restructure it: one pass over each object's vertices, trivial accept for
faces wholly on screen, 16 bits downstream of the cached transform.

## 2026-10-31: the projection rebuilt, painter's measured, the logic in 6502

- **The projection** (`docs/research/projection.md`, decision 27): camera
  walks rendered with the model showed that per-vertex jitter is what
  shows, so the budget is "never backwards, within 4/16 of a pixel". A
  9-bit reciprocal and two byte products meet it at a median 289 cycles a
  vertex (most 404) against the first method's 508; with the entries for
  shared coordinates, a median view's projection takes 10,217 cycles
  (most 22,312) against 24,153. Polar forms in logs, after PORTAL, were
  modelled and left open (decision 29).
- **The painter's fill** was built and checked exact, and measured slower
  at the median over Driller's views (135,039 cycles against the span
  buffer's 125,406 on fresh frames): every painted face rewrites bytes the
  floor or the sky already wrote. My estimate had left the background
  out. The span buffer stays (decision 28).
- **The player logic in 6502** (`docs/research/logic6502.md`) matches the
  transcription over 6,555 passes in its scenarios and walks and 110,459
  in a fuzz of 1,000 walks, with decision 18's fix. A pass takes a median
  2,765 cycles; a step on the probe a median 10,917.
- Merging the projection broke the object check's build (its tables
  outgrew the check's HAZEL layout, and its new entries were unreachable
  there); the full check caught both before anything was pushed.

## 2026-10-31: the whole pipeline live on the BBC

`build/live.ssd` (decision 30, `docs/research/live.md`) runs stages 1-10
on the BBC every frame from a free camera, with nothing worked out off
it. Measured that day by `make live` (`tools/livecheck.mjs`, jsbeeb's full
video): 614 frames shown, over every entrance, walks and turns at five of
them, and the demo, each the model's view of its camera byte for byte.
Fields a frame, median / p90 / most:

| frames | flip to flip | 1-7 objects | 8-10 fill | the rest |
|---|---|---|---|---|
| all (614) | 13.0 / 18.5 / 22.6 | 7.25 / 9.55 / 11.64 | 5.29 / 9.33 / 11.18 | 0.07 / 0.73 / 2.78 |
| an entrance's first (70) | 10.2 / 16.0 / 21.0 | 6.12 / 8.34 / 9.38 | 3.23 / 5.67 / 9.15 | 0.82 / 2.28 / 2.78 |
| still (359) | 11.5 / 17.4 / 20.5 | 6.37 / 8.56 / 9.17 | 4.54 / 9.16 / 11.18 | 0.06 / 0.52 / 1.88 |
| a walk (65) | 14.0 / 18.5 / 19.8 | 7.76 / 8.64 / 9.11 | 6.05 / 9.68 / 10.08 | 0.10 / 0.56 / 0.95 |
| a turn (110) | 16.8 / 21.6 / 22.6 | 9.52 / 11.25 / 11.64 | 6.49 / 9.94 / 10.84 | 0.07 / 0.56 / 1.01 |

So about 3.9 frames a second at the median, against decision 2's two
fields. The front end is the larger half everywhere, and a turn (the
transform's cache refilled) costs it about three fields more than a still
frame. The rest (the keys, the text, the figures, entering an area) is
small but for an area's first frame, which waits for its name below the
view. The BBC's own timing of each half, which it shows, agreed with the
emulator's count within 8 cycles on all 1,228. Merging main's larger
projection tables pushed the transform's cache out of HAZEL into main
RAM's `&3000` (decision 31).

## 2026-10-31: area records from the logic's database

The per-area records (`AREAS4`, `AREAS5`) are gone: `area_enter` builds an
area's working copy on the BBC from Driller's database in the player
logic's bank (`docs/research/objects.md`, "The records"), and
`tools/mkareas.py` became the model of that, checked against it byte for
byte by `tools/areacheck.mjs`. Measured that day (`make objects`, `make
live`):

- **The check**: the globals and all 29 areas exact, in both builds, the
  plain one and `OBJ_LOGIC`'s; a corrupted expectation (one plane's
  normal) and a corrupted conversion (`ob_ix` left unwritten) each failed
  it. The prototype in Python of the 6502's way (the first corner's cross
  product, the shrunk apex edges) matched `mkareas.py` on every object
  before any 6502 was written.
- **The working copy** (`ObjArea`) is 2,542 bytes: the objects' 19 arrays
  of 38 (722), the faces' 6 of 128 (768), the planes' 8 of 66 (528), the
  vertices' 3 of 168 (504), the sensors' 3 of 5 (15), and the 5 counts.
  `ob_ix` (38) is new.
- **The conversion** (`AreaConv`, in a sideways bank) is 4,405 bytes:
  2,655 of code, 175 of its tables, 1,440 of colour streams (the ST's face
  colours, decision 8, with each area's pointer) and the tape's 135 bytes
  of globals. Its main RAM part (`AreaCode`: the entry points, the
  record's reader and the fixed parts' lengths) is 116 bytes.
- **Its cycles**: `area_init` 68,888; `area_enter` a median of 53,169 over
  the 29 areas, at most 157,168 (Ketar Hangar, 41 planes). With
  `OBJ_LOGIC`, which builds the globals again each time, a median of
  122,077 and at most 226,197. Most of it is the slanted faces' planes
  and reading the records through main RAM; dividing by shifts and reading
  only each record's fixed part took the median from 66,272 and the most
  from 203,717.
- **The live disc's main RAM**: what it uses below `&3000` now ends at
  `&269D`, not `&2DB3`, 1,814 bytes freed (2,403 now free): the globals'
  record, the area directory and the copy's descriptors left `ObjConst`,
  the f64 table (768 bytes) went to HAZEL after the maths' tables (on a
  page there; `ObjWork` after it still fits), and `AreaCode` shrank by 90
  bytes; `ObjArea` grew by `ob_ix`'s 38. The logic's `LOGIC` is bank 4;
  bank 5 has `LiveData`, the font and `AreaConv`, with 4,968 bytes left.
- **The object check** still matches the model on all 2,485 views; the
  page-aligned f64 table took the median view from 204,478 cycles to
  203,826. `make live` still shows all 614 frames as the model's; an
  entrance's first frame now spends a median 0.90 fields outside the two
  halves (most 5.58), against 0.82 (2.78) when the area was copied.
