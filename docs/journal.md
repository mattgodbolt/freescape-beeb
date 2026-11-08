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

## 2026-10-31: the live disc, and the fill's optimisation rounds

**The live disc** (`docs/research/live.md`, decisions 30-31) runs the
whole pipeline on the BBC: `objects_frame` then `raster_frame` every
frame, from the camera alone, with a free camera, the demo, and the BBC's
own timing of the whole frame and both halves on the screen (User VIA T2
and the field count). `make live` saw 614 frames, every one the model's
render of its camera byte for byte; the BBC's own timing agreed with the
emulator's within 8 cycles on all 1,228 halves. Measured over those
frames (fields a frame, median / p90 / max): the whole frame 13.0 / 18.5 /
22.6; stages 1-7 7.25 / 9.55 / 11.64; stages 8-10 5.29 / 9.33 / 11.18. About
four frames a second at the median. It became `freescape.ssd`.

**The fill's optimisation rounds** (`docs/research/raster.md`): three
rounds on Driller's 65 views drawn fresh took the fill's median from
125,057 cycles to 109,526 (p90 221,578 to 189,141; most 364,050 to
319,467): edges worked out once per vertex and set up inline, runs
entered inline through a shared trampoline, faces already wholly behind
full lines skipped. The third round found little; the round's estimate
of this design's floor is about 90-95K. The refit: about 28 cycles a
line, 59 a face-line, 229 a run, 2 a byte and 527 an edge. Decision 32.

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

## 2026-10-31: the front end restructured (track M)

Track M restructured stages 1-7 for speed, model and 6502 together, exact
against each other on all 2,485 check views and on the live disc's 619
frames. Cycles of `objects_frame` [measured, `make objects`'s
`tools/objectcheck.mjs --entrance --json` on the 65 entrance views (each a
turn) and their 260 walk steps], median / p90 / most, against the
pipeline as the projection track left it (fb90ec2, the same check):

| | step before | step after | turn before | turn after |
|---|---|---|---|---|
| object pass | 7,051 / 14,110 / 17,991 | 7,057 / 14,106 / 17,997 | 7,051 / 14,419 / 17,991 | 7,057 / 14,420 / 17,997 |
| transform | 13,846 / 18,999 / 23,418 | 13,889 / 19,026 / 23,462 | 40,039 / 62,617 / 71,621 | 39,594 / 61,863 / 70,893 |
| vertex pass (new) | | 18,398 / 30,657 / 42,513 | | 18,421 / 30,675 / 42,513 |
| projection | 17,524 / 23,224 / 34,354 | 10,570 / 15,786 / 23,742 | 17,245 / 23,952 / 34,142 | 10,582 / 15,780 / 23,686 |
| faces' own | 48,788 / 69,632 / 98,496 | 12,859 / 19,288 / 30,126 | 48,880 / 70,973 / 98,476 | 12,781 / 19,393 / 30,126 |
| near clip + guard band | 49,806 / 98,065 / 148,972 | | 48,574 / 97,344 / 146,512 | |
| the cone (new) | | 66,867 / 139,289 / 176,567 | | 66,799 / 139,665 / 181,587 |
| 2D clip | 36,072 / 54,839 / 83,192 | 14,653 / 35,140 / 71,564 | 33,918 / 53,882 / 83,145 | 14,181 / 34,618 / 71,414 |
| drawn test | 5,143 / 9,166 / 14,515 | 4,593 / 8,728 / 14,515 | 5,143 / 9,084 / 14,517 | 4,321 / 8,563 / 14,517 |
| sort | 12,079 / 28,454 / 47,980 | 8,771 / 27,337 / 52,294 | 12,079 / 28,454 / 47,980 | 12,206 / 30,276 / 52,282 |
| **total** | **205,851 / 276,842 / 331,324** | **184,419 / 247,910 / 305,945** | **236,918 / 309,672 / 372,760** | **216,847 / 287,068 / 356,276** |

(The near clip and guard band row sums each view's two before taking the
median. Matrix, output and glue are as before.) On the live disc (`make
live`), stages 1-7 went from a median 7.25 fields a frame to 6.22, walks
7.76 to 6.69, turns 9.52 to 8.58.

- **Kept**: one pass over each object's vertices (a band test by bit
  lengths, then each vertex of a face projected whole projected once, with
  the shared entries taking about half: 22 full, 7 by Z and 16 by X and Z
  in a median step's view); faces projected whole taken or dropped by
  their outcodes, the 2D clip only for those crossing the edges; the sort's
  compares remembered by pair of slots while the camera's cells hold.
- **The cone** (proposed, amending decisions 15 and 17): faces the
  projection can't take whole drawn as the view's rectangle clipped by
  their edges' planes through the eye. Exact, and the original's pyramid
  again, but at the median it costs about what the near clip and the guard
  band did: about three such faces a view, each about four lines and five
  crossings, and the crossings' division and the lines' products are the
  frame's two largest routines. Its picture against the model before it:
  755 of 3,515,200 pixels over the entrance views and walks, none in the
  order; 5,130 of 26,877,760 over all check views, the order in 3; against
  the ZX oracle 1,389,622 of 1,406,080 pixels agree, against 1,389,686.
- **Measured and not built**: a 16-bit camera space with a block exponent
  an object changes no pixel of the check views (V >> 6, world units,
  changes 4,571); the transform's adds it would shorten aren't where the
  cycles are yet.
- **The area records** come from the logic's database at area entry
  (merged from a helper's branch: the entry above).
- The pipeline's code now fills its sideways bank on the live disc but for
  a few dozen bytes: the old near clip's arithmetic, the guard band and the
  slow fills went, and a line's quad and a point's square went to tables,
  to make room.

## 2026-10-31: walking Driller with its own logic (track P)

The live disc runs Driller's logic in 6502 with the renderer
(`docs/research/live.md`; decisions 36-40): a pass when one's due with the
keys held or tapped since the last, the area entered and its colours on a
change, the camera from the logic, and the frames between passes animated
along what the logic's move checked. `make live` drove seven scenarios
(walls, climbing, a fall, a fatal fall, doorways, the edge, rising), a run
of other keys and a tour of all 65 entrances: 316 passes, each the
transcription's state, walks and loads; 3,691 frames, each the model's
render of its camera byte for byte (1,955 views). Measured (fields a
frame, median): standing 7.70 and turning 12.94 at the entrances; up
against walls in the scenarios, standing 2.00, walking 3.32, turning
5.39. A bug the merge exposed: `area_enter`'s `cache_reset` cleared the
sort's memory in shadow RAM when ACCCON X was set; fixed. It became
`freescape.ssd`, and Driller's own start is now the disc's.

## 2026-10-31: the front end's optimisation rounds (track O), and the keys

Five exact rounds on stages 1-7 (`docs/research/objects.md`), no pixel
moved: the cone's lines and passes and `frac16`'s normalisation, projected
faces gathered straight into the output, the sort's memory kept across
cells, `M·c` updated by the step, the unrolled 2D clip moved to `ObjMore`.
Measured with `objectcheck.mjs --entrance` (median / p90 / max): a step
frame from 184,419 / 247,910 / 305,945 cycles to 153,950 / 210,662 /
252,158; a turn from 216,847 / 287,068 / 356,276 to 195,229 / 258,319 /
323,343. By stage on a step, at the median: the cone 66.9K to 52.1K, the
vertex pass 18.4K to 16.2K, the transform 13.9K to 10.2K, the 2D clip 14.7K
to 12.8K, the sort 8.8K to 6.2K. The check now also strafes four steps
along each axis from every entrance (3,265 cases), which caught mutants
the walks didn't.

Matt asked for the BBC's traditional keys for motion (decision 10): Z and
X turn, : and / walk; Driller's sizes moved to f0-f3. On the live disc's
check with both (fields a frame, median / p90 / max, mostly close to
walls): walking 3.09 / 6.30 / 16.26, turning 4.97 / 12.50 / 15.86,
standing 1.86 / 6.25 / 16.94.

## 2026-10-31: the cone restructured (track Q)

Five changes to the cone and the 2D clip (`docs/research/objects.md`,
decision 41). Measured with `objectcheck --entrance` (median / p90 / max
cycles): a step frame from 153,950 / 210,662 / 252,158 to 133,939 /
176,806 / 219,512; a turn from 195,229 / 258,319 / 323,343 to 170,605 /
215,093 / 292,559. The cone at a step's median from 52,078 to 34,770 (the
floor's share from 21,258 to 13,864), the 2D clip from 12,843 to 10,584;
the projection up from 10,570 to 11,778, since joins project some of the
cone's vertices. The check now also compares the cone's lines and the
vertices projected, and runs the crossing routine alone on 3,189 of the
model's crossings. The front end's code now nearly fills its room on the
live disc (bank 7 and `ObjMore`), so the next rounds need room found
first.

## 2026-10-31: the idle loop, and the fill's round 4 (track S)

Standing still now draws nothing (decision 42): an idle loop is a median
3,558 cycles. Measured from a key going down with nothing left to draw
(fields, median): its logic pass 0.68 against 3.31 before; the first
changed view 8.41 walking and 7.61 turning, against 16.96 and 15.44. A
fault where one tap made two passes is fixed. The fill's round 4 (a fast
path for fresh lines with both edges vertical, exact) took its mean on
Driller's views drawn fresh from 122,247 to 119,638 cycles, the median
unchanged at about 110K; grouping faces by object measured at under 2K a
view, so it wasn't built. The round's account of what's left: about 45
cycles a piece, about 70 a face-line, and 27K of byte stores.

## 2026-11-01: Driller's 192-line screen (track T)

The screen went to 24 rows (decision 43), which `make frames` checks
against MOS 3.20's MODE 2 centre, and the flip at the view's end moved
with the sync. The memory it freed went to the speed work: the front
end's code bank from 134 bytes free to 2,558, its main-RAM room at &3000
from 256 to 1,336, the fill's bank from 225 to 760, the logic's shadow
room from 2,272 to 6,368. Measured free on jsbeeb over 64 seconds of play
and not yet used: ANDY's 4K, 229 bytes of page 1, 137 of zero page, and
page &0D below &0D9F. The front end's code starts at `OBJ_CODE_ORG`, the
fastest of ten offsets measured (they spread about ±0.2%). Every frame of
both live discs is still the model's, byte for byte.

## 2026-11-01: the column fill, priced and not built (track U)

Matt had no preference among a column fill, half vertical resolution, a
smaller view and more polishing; the column fill was chosen as the one
that keeps the picture, but priced first, since the painter's estimate
had been wrong. Modelled exactly and priced from measured kernels (a byte
8 cycles dithered and 5 solid down a column; a run's entry 43 with the
plant kept and 78 when it moves; a face byte-column's loop 96): median /
p90 / max on the 65 views drawn fresh, the row fill measured 110,119 /
183,995 / 319,926 against the column fill priced at 123,467 / 183,240 /
269,828; on 738 live frames, 75,016 / 234,630 / 371,360 against 89,837 /
258,327 / 371,188. Not built (decision 44). The study also found two
free-camera frames in area 4 that fail the model's own exact-edges check;
the disc drew the model's view for them.

## 2026-11-01: the front end's sixth round (track V)

Four changes (`docs/research/objects.md`): the sort starts from the last
frame's order (its median 6,248 cycles a step to 722); a level camera's
edge normals in closed form; vertex orders written out; the band test's
middle path and the drawn test's signs first; the cone's lines square to
two sides; side crossings by reciprocal (decision 45). Measured with
`objectcheck --entrance` (median / p90 / max): a step from 133,992 /
176,870 / 219,529 cycles to 121,789 / 160,683 / 191,793; a turn from
170,659 / 215,159 / 292,572 to 162,298 / 209,373 / 287,771; over the 648
level views at every yaw, the median from 104,545 to 99,604. On the live
disc, stages 1-7 walking from a median 1.03 fields to 0.93. The floor is
now 16,147 cycles of a step's median, a third of the cone. This round's
agent was paused once, because its shell writes inside its worktree (under
`.claude/`) stopped for Matt's permission; it finished with files changed
only through the editing tools, and nothing more stopped.

## 2026-11-01: the front end's seventh round (track W)

The cone's lines from images and exact unit side crossings (decision 46),
quads gathered with the loop written out, the coarse cull's compares
patched in per frame, dedupe straight into the output, and a level
camera's cuboid vertices by copies. Measured with `objectcheck
--entrance` (median / p90 / max): a step from 121,789 / 160,683 / 191,793
cycles to 112,858 / 150,137 / 173,474; a turn from 162,298 / 209,373 /
287,771 to 152,631 / 201,728 / 270,986. On the live disc, stages 1-7
walking from a median 0.93 fields to 0.90. Skipping objects with every
vertex in one outcode half-space was measured and dropped (it cost more in
the face loop than it saved). The front end's bank has little room left
again; about a quarter of the candidates are transformed and projected
for nothing, and a per-object test from the transform's cache is the next
lever.

## 2026-11-01: Driller's instrument panel (track X)

Matt chose the panel as the next layer. `tools/mkpanel.py` cuts the ST's
console out of its program and converts it; `src/panel.6502` draws its
fields from the logic's variables after each pass (decision 47). Measured
on the logic disc's check: `panel_values` a median 4,510 cycles a pass
(p90 6,612, most 9,255), each changed cell 826-1,097 more to draw into both
buffers; nothing measurable a frame. `make panel` checks `panel_values`
against `tools/model/panel.py` over 656 value sets, and `make live` checks
every flip's screen outside the view against the model's render of the
panel; the first run caught a real fault (the position's divide
overwrote the score). Extra live scenarios showed two faults not the
panel's: with the jet, one view byte differs from the model; with the
clock's ticks, the logic differs from the transcription. Both are being
looked into.

## 2026-11-01: the jet's byte and the clock's pass (track Z)

The jet's byte was the rasteriser's. A sliver under a pixel wide, over the
right edge of the face behind it, had its chains' DDAs part one way and
cross lower down, each rounding toward its own top vertex. The model takes
each line's `[min, max)` of the boundaries; the 6502 had kept the order the
chains first parted in for the whole face, so it drew nothing where they
had crossed, and a face whose chains first parted the wrong way would have
lost nearly every line. The 6502 now swaps the chains wherever a line finds
them crossed, and `make raster` has three scenes of crossing chains that
the old code fails on both builds. Driller's 65 views come to 7,761,617
cycles from 7,770,109 (`docs/research/raster.md`, "The chains crossing").

The clock's fault wasn't the logic's: pass by pass it is the
transcription's, and the original's. At minute 9 the global conditions put
the minute counter back under the input, and the original's input takes a
minute without waiting for a key, so the disc ran a pass of no keys as soon
as the last was done, which the check's trace didn't have. Now the trace
marks such a pass (`soon`) and puts in the pass of none where the next step
isn't one of keys, and the check puts the next pass's keys down as the pass
before is taken; `tests/logic/minutes.txt` has both. Making it, the oracle
showed that a tick can't follow such a pass: the input takes the minute
left before the clock ends another. Three faults of the check's own came
out with the new scenarios: it could find the disc settled while the loop
that ended a pass's frames was drawing (a key then waited 2.58 fields for
its pass), it let keys go between passes that named the same keys in
another order, and a long run's idle loops overflowed its maximum. The live
check now takes every scenario of `tests/logic/` but `keys.txt`, whose E
(a ZX key with no action) the disc doesn't read.

## 2026-11-01: steering (track AA)

Matt found the disc unsteerable: one tap turned Driller's starting 15°,
animated as three 5° frames, and passes came about once a second
(measured on the disc: each tap of Z moved the yaw by three units).
Decision 48 starts at 5° and 25 units and makes held keys repeat like a
keyboard. Measured on the disc that day: taps of 0.1s and 0.28s each turn
5°; held Z turns 49.5° a second; a held walk covers 242 units a second
facing along an axis (frame-bound at about 170 from the start view). The
live check now holds each tap 13 fields and fails on a second pass or an
early repeat; `tests/logic/pace.txt` holds turns and walks.

The same day a fault track found the jet's stray view byte was the 6502
rasteriser's: on a face under a pixel wide the two edges' rounding can
swap them partway down, and the 6502 had fixed which was left at the
first line. It now swaps crossed chains on any line, with three
regression scenes. The ticks mismatch was the live check's own: at minute
9 the original takes a pass without waiting for a key, which the check's
trace now models. The live check runs 16 scenarios and 8 fuzz seeds,
13,014 frames, each the model's byte for byte.

## 2026-11-01: two files on the disc, and the room scavenged (track Y)

The live disc booted eighteen files, a section each. Now it's two: `!BOOT`,
a loader (`src/loader.6502`), and `DRILLER`, every other part packed by
ZX02 at assembly, which the loader reads a track at a time and unpacks into
its place as it comes; HAZEL's tables and the start go in from `!BOOT`
itself once the OS is gone. The slideshow uses it too. Baron can't nest a
section that's opened in many places, as the banks' are, in another, so
the build has two passes: `src/live.6502` writes its parts as files and
`PRINT`s where each goes, and the loader's build packs them, a stream to
each place (a bank, main RAM, HAZEL), its parts one image. One file wasn't
to be had: `*RUN` loads a file whole into main RAM, which can't hold the
packed parts, so they're read by sector from a second. The DFS's OSGBPB
was the first way tried, and on the Master it takes a revolution a sector:
40K in 38.8s, against 6.9s by OSWORD `&7F` a track at a time. From power on
the live disc shows its first frame at 11.19s, from 16.51s; the slideshow
at 6.37s, from 8.01s. The unpacking doesn't overlap the reads, so it
counts: 2.3s of the live disc's boot, about 63 cycles a byte, after its
copies were made by Y. `tools/loadcheck.mjs` holds every part's place to
its file at the loader's end, and fails a saved section the loader isn't
told of; the first mutation it caught (a run of 256 not counted) put
eleven thousand of bank 4's bytes out.

The fill now reads the maths' quarter squares in HAZEL (`RASTER_SQUARES`),
which frees its bank's 1K, and `start` runs from page `&0D`, which gives
`ObjMore` a page: 852 bytes free there, from 596, and 1,784 in the fill's
bank, from 760. The front end's bank holds the front end alone, so it
stays at 119: it gains only as the front end's code leaves it. Measured
over the free disc's tour of the entrances, 2,318 bytes of its code each
took under 0.1% of its cycles, 1.17% in all, and the lines' and points'
code (1,125 bytes) 0.29%. ANDY's 4K could be the front end's second window
for code like that, or the area conversion's place, which would free its
4,423 bytes in `BANK_DATA` with no code changed: a choice for Matt
(`docs/research/live.md`, "Decisions to record"). Nothing else was worth
keeping packed until needed: the area conversion has no buffer to unpack
into, and the rest is small or packed already.

## 2026-11-05: ANDY, and objects beyond the view (track AB)

ANDY (decision 52) now holds the front end's rarely run code: the lines and
points, the planes' own lines, the matrix's build, `sensor_watching`,
`frac16` and the slow fill, reached by trampolines in `ObjMore`
(`docs/research/objects.md`, "ANDY"). The loader puts it in from `!BOOT`
once the OS is gone. The front end's bank went from 119 bytes free to 4,022
on the logic's disc (ANDY holds 3,909 bytes, 187 free). Cost, stages 1-7 a
frame matched by camera: the logic's disc +18 cycles at the median (+0.04%),
the free disc +122 (+0.12%). The check build now has the live disc's map, and
fails a view that runs sideways RAM other than its own code.

The room went to the first lever of the seventh round: a candidate with
every vertex beyond the view's left, right or top (three planes through the
eye, kept with the transform's cache as each object's greatest values) is
passed over before it is transformed (decision 53, proposed). `make objects`
(median / p90 / max): a step from 112,933 / 150,093 / 173,804 cycles to
94,004 / 140,680 / 174,867, under the 100K aim; a turn from 152,665 /
201,634 / 271,048 to 142,269 / 211,387 / 292,496. On the live disc, stages
1-7 in fields a frame (median / p90 / max): walking 0.96 / 2.86 / 5.29 to
0.75 / 1.99 / 4.95, turning 2.28 / 4.03 / 5.83 to 2.02 / 3.52 / 5.49,
entrances 3.84 / 5.24 / 6.86 to 3.08 / 5.52 / 7.36. On the free disc's tour
walking improves and turning gets 1.3% dearer, as a turn pays for the bounds
in every fill. Four of the check's 3,265 views lose a sliver of a cone face
made from an object wholly beyond the view; no entrance view, walk or ZX
comparison changes. The cone's products, the projection's inlining and the
floor were not reached.

## 2026-11-06: the turn's rotation (the ninth round)

The coordinator asked whether rotation could be made cheaper, a turn being
the costly frame. The check now reports its yaw sweeps as their own group:
each view after a sweep's first is one 5° turn with the camera kept, as the
disc turns, and unlike the entrance views it keeps the sort's memory. On
them, profiled, a turn's transform was mostly not the products. The bounds
made in every fill were its largest part, then the fills' stores and
bookkeeping; a pyramid's fill took about 5K cycles, a cuboid's 2K.

What went in (`docs/research/objects.md`, "The ninth round"), all exact,
every stage of every view still the model's:

- each object's bounds made from its cells, before the fill and with their
  own stamp, so a candidate passed over on a turn is never filled;
- a level camera's fills read f64 at bases patched once a turn, the cell
  the index, straight into the cache;
- a level camera's matrix with no products (the yaw's rotation), its image
  columns with two, its M c with four of `mul`.

Measured by `objectcheck` on the full check (median / p90 / max / mean,
cycles), before and after:

| | before | after |
|---|---|---|
| a 5° turn (639 yaw-sweep views), total | 82,329 / 166,866 / 249,763 / 94,131 | 67,428 / 146,761 / 223,907 / 79,268 |
| ... its matrix | 4,209 / 4,241 / 4,253 / 4,211 | 1,893 / 1,907 / 1,912 / 1,894 |
| ... its transform | 29,194 / 57,390 / 79,788 / 31,247 | 15,035 / 34,906 / 57,887 / 18,575 |
| an entrance view (a new camera), total | 142,269 / 211,387 / 292,496 / 141,723 | 121,266 / 200,345 / 288,376 / 129,741 |
| ... its transform | 44,189 / 62,037 / 87,384 / 40,745 | 30,644 / 45,832 / 80,979 / 30,128 |
| a step (260 walk views), total | 94,004 / 140,680 / 174,867 / 92,809 | 94,044 / 140,806 / 174,866 / 92,816 |
| ... its transform | 7,488 / 11,887 / 14,199 / 7,593 | 7,492 / 11,891 / 14,203 / 7,597 |
| a pitch turn, total | 72,854 / 167,793 / 323,156 / 87,886 | 55,657 / 146,483 / 317,297 / 73,866 |
| a roll turn, total | 168,064 / 250,937 / 313,252 / 174,045 | 164,344 / 243,750 / 305,748 / 166,557 |

On the live disc's check, stages 1-7 in fields a frame (median / p90 /
max): turning 2.02 / 3.52 / 5.49 to 1.40 / 2.85 / 5.07, walking 0.75 / 1.99
/ 4.95 to 0.75 / 1.99 / 4.91, entrances 3.08 / 5.52 / 7.36 to 2.53 / 5.26 /
7.26; the whole frame, flip to flip, turning a median 2.97 fields and
walking 2.41. `make check` passes.

A step is unchanged. On the way, two things cost steps and were put right:
the bounds kept at their sums' own scale had top bytes nearly always equal,
so a step's compares fell to the low bytes (about 500 cycles a step); and a
second stamp test on the common path. A pitched or rolled camera's matrix
costs about 1.7K more than before (its bounds' nine terms patched by one
routine, kept small for the bank's room), but its transform gains more.

Counted and not built: rotating the cached vectors by the turn's 5°
(about twelve byte products a vector against a level fill's four for a
point, and not exact, since M for the next yaw isn't the 5° rotation of M in
bytes); the polar form (a turn of look-ups, but every step redoes each
point's polar form, it's good to a pixel, and the cone needs camera
space); log products (no fewer reads, and inexact). The front end's bank,
which ANDY had freed, has less room: the bounds' and the level fills' code
took most of what it had.

## 2026-11-06: the cone, the vertex pass and the projection

The coordinator asked for the cone, the vertex pass and the projection to
be made faster. Profiled on the walks' steps, the three stages' cycles are
spread thin: no routine is more than a few per cent of a step, and the
cone's largest part, its lines from images, is two products of sixteen bits
by sixteen a line that every corner's f needs. What went in
(`docs/research/objects.md`, "The tenth round") is exact, every stage of
every check view still the model's, and touches `src/clip.6502` alone:
`vertex_code3` by 24-bit sums' N EOR V, `image_line`'s A W and B H written
out, `side_cut`'s shifts written out, `cone_line`'s and `drawable`'s zero
flags from bytes already in hand, and the band test's commonest path last.

Measured by `objectcheck` on the full check (median / p90 / max / mean,
cycles), before and after:

| | before | after |
|---|---|---|
| a step (260 walk views), total | 94,044 / 140,806 / 174,866 / 92,816 | 92,681 / 138,413 / 172,970 / 91,589 |
| ... its cone | 24,871 / 59,284 / 83,980 / 30,673 | 23,967 / 57,184 / 82,012 / 29,746 |
| ... its vertices | 10,181 / 18,449 / 25,171 / 10,462 | 10,136 / 18,356 / 25,036 / 10,404 |
| ... its drawn test | 4,087 / 7,898 / 14,597 / 4,403 | 3,808 / 7,472 / 14,102 / 4,178 |
| a 5° turn (639 yaw-sweep views), total | 67,428 / 146,761 / 223,907 / 79,268 | 66,055 / 144,931 / 222,514 / 78,027 |
| ... its cone | 25,077 / 50,014 / 91,484 / 27,470 | 24,087 / 48,475 / 88,594 / 26,402 |
| an entrance view, total | 121,266 / 200,345 / 288,376 / 129,741 | 119,692 / 198,686 / 286,456 / 128,480 |
| all 3,265 views, total | 89,946 / 185,767 / 317,297 / 102,972 | 88,236 / 183,933 / 316,058 / 101,729 |

The projection's stage is unchanged. On the live disc's check, stages 1-7
in fields a frame (median / p90 / max): walking 0.75 / 1.99 / 4.91 to 0.73 /
1.95 / 4.87, turning 1.40 / 2.85 / 5.07 to 1.38 / 2.83 / 5.04, entrances
2.53 / 5.26 / 7.26 to 2.50 / 5.24 / 7.21. The front end's bank and ANDY each
have a little more room than before, `ObjMore` a little less (`side_cut`'s
jump tables). `make check` passes.

Not kept, or not built: a unit line's terms in the passes without products
(a few dozen cycles a step: its vertices are mostly on the sides it's square
to, whose terms were already skipped); `pmul` written into the projection's
blocks (each copy would need the case's eight patches again); and coarser
lines from images, `IMAGE_BITS` 8, which would halve the lines' and passes'
products (about 3K a step at the mean by the counts) but in the model moves
1,182 pixels over the entrance views and their walks, up to 148 in one view,
a near wall's edge off by two pixels and liable to wobble as the camera
moves; not proposed. A step's largest unworked block is now the faces
projected whole (`poly_face`, the drawn test, the 2D clip), nearly as large
as the cone at the median.

## 2026-11-06: the fill's fifth round

The fill was the frame's largest part on the disc. Every earlier round
measured it on views drawn fresh, where its cost is close to its design's
floor; the disc's frames aren't fresh. Each goes into the buffer that holds
the frame two before, and measured on the model over the live check's
frames in order, walking keeps 66% of lines and 93% of bytes from that one,
turning 69% and 91%. Most such lines are one run: the sky, which the
background's records already skipped, and the floor across the whole line.
So a line one face takes whole is now not written when the buffer holds it
in that byte (decision 70, amending 20; `docs/research/raster.md`, round
5): a record a buffer and line, in the fill's bank, and the background's
records checked before the faces rather than after. The picture doesn't
change, and the model counts what each held frame writes; a new sequence
in `make raster` (lines whole, then two pieces, then whole again) catches
the one mutation the others missed.

Fields a frame on the logic's disc (median / p90 / max), the fill: walking
1.15 / 2.72 / 8.29 to 0.85 / 2.5 / 8.29, turning 1.15 / 2.84 / 7.46 to 0.83 /
2.73 / 7.46, standing 3.49 to 3.26, entrances 2.82 to 2.83 at the median;
flip to flip, walking 2.41 to 2.0 and turning 2.97 to 2.51. Fresh views pay
0.8% for the test (Driller's 65, a median 109,641 to 109,796 cycles). The
slideshow, whose views are held, went from 2.49 fields a frame to 2.16. The
slideshow's bank had no room for the record beside its own squares, so its
rasteriser state went to main RAM, as the live disc's is. The free
camera's tour held SPACE for three fields, and a view drawn faster than
that went on twice; it now lets go once the entrance changes.

What's left of the bytes the buffer holds is mostly in the first and last
runs of lines with an object on the floor, about 1,200 bytes a frame, and
taking them would want two more records a buffer the bank hasn't room for.
The faces' own work was looked at again and has nothing big left: lines
already full that a face still steps through are 11 of its 296 face-lines
a view. A still camera with the crosshair moving redraws a view its buffer
already holds (the check's standing frames, 5.4 fields flip to flip); only
the live loop could know to skip both halves. Half the vertical resolution
is priced at about 28% off a fresh view, for Matt; constant dithers line
to line save this fill nothing.

## 2026-11-06: the rest of the frame (the tenth round)

The coordinator asked for the front end's remaining costs outside the cone,
the projection and the fill, which other tracks had: the floor, the sort,
the 2D clip and the live disc's "the rest" (a frame's loop but its two
halves). `livecheck.mjs --profile-rest` (new) put the rest by routine. At
an entrance, of 197,098 cycles a frame, the area's conversion took about
113K (the slanted faces' products, greatest common divisors and divisions
about 75K, nearly all of it the globals', which every entry builds again
with the logic), the sort's memory cleared 17K, and the area's name and
message drawn 35K. A standing frame (the crosshair moved) ran both halves
again for the same view, 5.4 fields of them. Walking (15,530 cycles) and
turning (17,745), the panel's scan of its cells, the camera's fractions and
the inputs' compare were the largest parts.

What went in (`docs/research/objects.md`, "The tenth round"; nothing any
stage outputs changes, so no picture changes):

- the globals' slanted faces kept from their last build by their edge
  vectors (a memo in `ObjMemo`, main RAM's `&3000` on);
- the conversion's products by the maths' quarter squares, none with a
  factor 0;
- the sort's memory forgotten on entry by a new generation, not cleared;
- `panel_sync` scanning from where it left off;
- `lv_camera`'s fractions by quarter squares, none for 0;
- the objects' flags compared only after `logic_go_shown`;
- a frame of the crosshair alone when the buffer it draws already holds its
  view (`live_cross_only`, `docs/research/live.md`, "The crosshair").

`areacheck` (median / most, cycles): `area_enter` with the logic 138,893 /
242,897 to 81,062 / 171,245; without, 70,078 / 174,072 to 48,940 /
139,141. The live disc's check, fields a frame, median / p90 / max (mean),
before and after:

| | flip to flip, before | after | the rest, before | after |
|---|---|---|---|---|
| entrance (75) | 10.77 / 15.87 / 22.92 (11.20) | 9.35 / 14 / 20.94 (9.79) | 4.74 / 5.97 / 9.82 | 3.44 / 4.56 / 7.64 |
| standing (669) | 5.65 / 5.94 / 10.42 (5.23) | 0.52 / 2.62 / 9.44 (1.12) | 0.26 / 0.44 / 4.58 | 0.22 / 0.33 / 3.58 |
| walking | 2.41 / 5.03 / 13.82 (2.80) | 2.18 / 5 / 13.69 (2.67) | 0.27 / 0.68 / 7.14 | 0.12 / 0.58 / 5.02 |
| turning | 2.97 / 6.33 / 14.9 (3.50) | 2.87 / 5.99 / 12.92 (3.35) | 0.22 / 0.57 / 7.06 | 0.11 / 0.49 / 5.05 |

557 of the 669 standing frames were the crosshair alone. The rest by the
profile, cycles a frame: entrance 140,241, standing 11,940, walking 10,915,
turning 11,695. An idle loop went from 1,816 / 3,083 / 81,432 cycles to 741
/ 1,163 / 79,766, so a key pressed with nothing to draw shows its first
changed view sooner: walking 5.52 to 5.29 fields at the median, turning
5.61 to 5.55, the crosshair and the rest 3.77 to 1.96. On the free disc a
walking frame's rest went from 13,661 cycles to 10,165. `make check`
passes.

Measured and not kept: the sort's memory forgotten slot by slot as a
ceiling cell moves (each changed slot's row and column cleared, a new
generation past four): over the check's walks the sort's mean step went
from 1,800 cycles to 1,516 and its worst from 32,792 to 18,138, but the 90th
percentile rose from 1,976 to 2,386 and it took about 140 bytes of the
front end's bank. Not reached: the floor (the guard band's and the cone's,
another track's) and the 2D clip, whose cost is spread over its passes;
counted and not built, a level cuboid's fill written out, `bp_site`'s
unchanged pages, the crosshair's EOR and the panel's numbers, each a few
hundred cycles. The room: `AreaConv` took 273 bytes of its bank's (705
left); `ObjMemo` 363 bytes, leaving 41 of main RAM's `&3000` up to
`SCREEN`; `LiveGlue` 54; the front end's bank is unchanged.

## 2026-11-06: the eleventh round

The coordinator asked for more speed wherever it could be found, measured
as the live disc's whole frame. Profiled on the disc first, with
`livecheck.mjs` now timing the interrupt itself (`irq_handler` to its
`RTI`): the vertical sync's took 1,376 / 1,392 / 1,413 cycles (median / p90
/ most) whenever it read the keys, which it did in most fields of the
check's runs, as a key held means reading every key it maps, each by two
accesses to the System VIA at 1MHz. At an entrance the rest of the frame
(140,502 cycles) was the area's conversion, the panel's cells (830 cycles a
glyph) and the panel waiting for the beam (panel_sync's loop, about 22K a
frame); every frame the crosshair's EOR took 1,413 cycles, off and on.

What went in (`docs/research/objects.md`, "The eleventh round"), each
committed apart, none changing what any stage outputs or the picture:

- the panel: its values set before an area's conversion, which draws cells
  as the beam allows after each record; the beam's window widened to the
  lines past the screen's last as well as the view's (the panel's rows are
  met again only after `FLIP_LINE`); a glyph cell writes the buffer
  selected as it makes each line and copies them into the other;
- the keys read by column: each column looked at once, its keys only when
  CA2 says it has one down;
- the crosshair's EOR by its columns' addresses, made once each;
- `clock_to` without its product for a span of one field or none;
- a level camera's cuboid's edges straight into the level fills;
- the globals' slots kept when their records are those they were last built
  from (`G_BYTES` of them copied into `AreaKeep`, after `Work` in the OS's
  pages; on the check's runs they were the same at 159 of 160 entries).

The live disc's check, fields a frame, median / p90 / max, before and after:

| | flip to flip, before | after | the rest, before | after |
|---|---|---|---|---|
| all (3,928 / 3,964 frames) | 2 / 5.51 / 20.95 | 1.93 / 5.28 / 19.14 | 0.14 / 0.56 / 7.62 | 0.1 / 0.53 / 5.18 |
| entrance (75) | 9.28 / 13.99 / 20.95 | 8.45 / 12.56 / 19.14 | 3.43 / 4.63 / 7.62 | 2.42 / 3.24 / 5.18 |
| standing (669) | 0.52 / 2.6 / 9.44 | 0.53 / 2.57 / 8.57 | 0.22 / 0.33 / 3.59 | 0.21 / 0.32 / 2.49 |
| walking | 1.92 / 4.62 / 13.67 | 1.86 / 4.54 / 13.61 | 0.12 / 0.57 / 5 | 0.1 / 0.55 / 4.24 |
| turning | 2.43 / 5.7 / 12.93 | 2.31 / 5.58 / 12.47 | 0.11 / 0.42 / 5.11 | 0.09 / 0.41 / 4.69 |

The pieces, on the same runs: the vertical sync reading the keys 1,376 /
1,392 / 1,413 cycles to 834 / 1,020 / 1,264 (it read them in 16,481 of
18,987 fields; on the free disc 1,375 to 803 at the median); a glyph cell
830 / 1,091 / 1,102 to 688 / 872 / 912, and 66 waits for the beam to none;
the crosshair's EOR 1,413 cycles a walking frame to 1,004; `clock_to` 570
to 379. `objectcheck`: a 5° turn's transform 15,035 / 34,906 / 57,887 to
14,406 / 33,433 / 55,180 and its total 66,056 / 144,940 / 222,527 to
65,460 / 143,791 / 219,883; an entrance view's total median 119,704 to
118,016. `areacheck` with the logic: `area_enter` a median 81,062 before;
after, 83,082 over the areas that find a byte of the globals' records
changed (the check changes one for every other area) and 56,835 over those
that keep them. `make check` passes.

The room it took: `AreaKeep` `G_BYTES` + 1 bytes of the OS's pages
(`work_end` to `RASTER_IN_ORG`); `ag_same` in `ObjMore`; the keys' column
table and two bytes of `Work`; the front end's bank, `AreaConv`'s and
`LiveGlue`'s by a few bytes each way.

Counted and not built: the lines whose first or last run the buffer holds
(raster.md, round 5: about 3K cycles a walking frame, the largest found),
whose records, a byte end and a pattern byte for each of 2 screens, 104
lines and both ends, are 832 bytes against the fill's bank's 1,272 free
(`raster_work_end` to `&C000`), before the trimming code in INSERT's and
the stretch's four copies each and the background's gaps; the globals
compared by a checksum (inexact); the vertical sync's byte loop unrolled
(under a hundred cycles a field); `drawable`'s products decided by bit
lengths first (little of a few hundred cycles a step).

## 2026-11-06: room in main RAM's `&3000` up to `SCREEN`

The eleventh round left `ObjMemo` 41 bytes of room before `SCREEN`, and a
memo of each area's own slanted faces (`ac_plane_face`, about 20K cycles an
entrance) wants more. Four pieces went, none changing what any stage
outputs, and none costing a cycle that a check shows:

- `msq_lo` and `msq_hi` (the matrix's quarter squares, n = 0..128, 258
  bytes of `ObjConst`) are the first 129 entries of the maths' `sq_lo` and
  `sq_hi` in HAZEL, which `mmul` can read as the transform's own products
  do: `mmul` now indexes those, the same instructions.
- the cosine table (72 bytes of `ObjConst`) is the sine table a quarter turn
  on, so `mkareas.py` emits the sine and its first 18 entries again
  (`cos_table = sin_table + 18`), asserting the tape's cosines are exactly
  that: 54 bytes freed.
- `so_memo` was rounded to whole pages for `so_clear`; it is now exactly
  `N_OBJ * N_OBJ` bytes and `so_clear` clears the whole pages and then the
  bytes past them (92 bytes; the clear runs when generations run out, and
  once at the start).
- `ob_id`, the working copy's object id, was written by the conversion and
  read by nothing (the logic finds slots by `ob_ix`): the array is gone,
  `N_OBJ` bytes and an instruction pair per object in `ac_slot` (38 bytes).

Together 442 bytes, so `ObjBound`'s end sits that far lower and the room
before `SCREEN` is 483 bytes (from 41). `objectcheck`: an entrance view's
total median 117,987 (118,016 before), the walks' and sweeps' within a few
cycles; `areacheck` with the logic: `area_enter` 82,972 building the
globals again (83,082) and 56,762 keeping them (56,835). `make check`
passes.

Counted and not built: the transform's cache has 256 slots an array (nine
pages); with 128 slots two arrays could share a page at no cost a access,
freeing 1,152 bytes, at the price of the cache emptying whenever an area's
objects need more than 128 slots, and one compare more in `transform_fill`.
Not measured on the walks, so not built. The sort's memory held as nibbles
would halve `so_memo` but adds cycles to every pair looked up, and a pair's
verdict is not its reverse's (ties go to the second below, the first above),
so a triangle is not exact. `oc_x` and `oc_y` (512 bytes) have different
edges and bits, so don't share. The shadow RAM from `logic_faces_end` to
`SCREEN` is free but the front end reads its data with X clear, so only the
logic can use it.

## 2026-11-06: the rooms emptied

Memory is the limit on speed now: the first and last runs of a line (raster.md,
round 5) need 832 bytes of records in the fill's bank and the trimming in
four copies of INSERT and the stretch, against 1,272 free. The coordinator
asked for bytes in the fill's bank, `AreaConv`'s, `LiveGlue`'s, HAZEL's
`ObjWork` and the OS's pages, at no cost in cycles, each commit
passing the checks. What came out (`docs/research/raster.md`, "Round 6"):

| region | free before | after | by |
|---|---|---|---|
| the fill's bank (`raster_work_end` to `&C000`) | 1,272 | 3,072 | `bl2` is HAZEL's `proj_bl2` (256); no horizon on the live disc (1,133 of code, 104 of splits: decision 71); `rr_en` is `rr_pl` a byte on (104); the line heads and scratch bytes in the OS's pages (112); the work then starting on the next page after the code |
| `AreaConv`'s bank (`area_conv_end` to `&C000`) | 684 | 1,316 | the areas' patterns by index into the 172 distinct of 464 (`ld_pat_ix`, `ld_pool0`-`3`: 1,856 bytes to 1,152 and `live_patterns`) |
| the OS's pages | 52 (and page `&0D`'s 12) | 132 (and 12) | the unused tail of `rs_pat`'s page, less the line heads and scratch bytes it now holds |
| main RAM below `&3000` | | about 35 more | the pattern copy out of `lv_enter_area` (a `JSR` now) |
| `ObjWork` (`obj_work_end` to `&E000`), `LiveGlue` | 92, 11 | 92, 11 | nothing found that costs no cycles (below) |

Cycles. `tools/rastercheck.mjs`'s Driller views (the check build, which keeps
the horizon, so only the table changes show): 7,820,772 for the 65 to
7,813,661, every view the model's; `bl2` costs a wide edge 2 and saves a tall
edge 4, and the rest is where the tables fall against their pages. On the
logic disc the fill's fields a frame (median / p90 / max), before and after:
walking 0.78 / 2.44 / 8.15 to 0.74 / 2.4 / 8.15, turning 0.79 / 2.72 / 7.35
to 0.78 / 2.67 / 7.31, standing 0 / 1.74 / 5.22 to 0 / 1.69 / 5.17; flip to
flip, walking 1.87 to 1.82, turning 2.35 to 2.29. The horizon's removal is
most of it: a gap is filled with nine cycles less, and a line of background
alone no longer loads its split.

Looked at and left: `ObjWork`'s arrays that are never live together would
want each stage's use traced (the transform's `tf_fn`/`tf_fv`/`tf_fc` 384
bytes and `lfc` 128 are the largest candidates); `LiveGlue` is code that
runs (`live_figures`, `fig_divide`, the camera's glue) and moves only
with a bank's paging; `ld_area_of` is 128 bytes for 29 ids (1 to 32, and
127), about 95 to be had by trimming it and testing 127; the row runs'
pages each have 96 free bytes after their 160, twelve gaps for routines of
that size (`swap_chains`, `product`, `fill_split` are 92, 92, 95) or per-row
records indexed by `(r_rr),Y` (raster.md, round 6). `bnd_ofs` has an
entry for every pixel and reads only the odd ones.

## 2026-11-06: the twelfth round, room in the front end

Memory was the limit on speed (a quarter-square table at 64 times the scale
for `bound_object` wants about 1.8K), and the front end's regions had little
left: the bank (`ObjCode`) 477 bytes free, ANDY 70, `ObjMore` 383. This round
freed bytes there without changing what any stage outputs
(`docs/research/objects.md`, "The twelfth round"; decisions 75 and 76), each
change a commit of its own so one can be reverted alone. `objectcheck`
agrees on every view after each, and `make check` passes on the last.

Bytes freed and cycles changed, the entrance views' median in cycles a view
(118,016 before) and the yaw sweeps' (a 5-degree turn, 65,460 before), then
the walks' (92,740):

| change | region | bytes | entrances | turns | walks |
|---|---|---|---|---|---|
| the projection's cases, 9 to 20 of bit length | `ObjMore` | 615 | -16 | | |
| the never-called stub for the shared entries | `ObjMore` | 38 | | | |
| `transform_object` makes vertex 0 once | bank | 264 | +3 | | |
| a level camera's bound patch by `bp_site` | bank | 594 | +546 | +581 | |
| one patch of `pmul` for the cases | `ObjMore` | 381 | +241 | | +120 |
| the 2D clip's passes share a body per axis | `ObjMore` | 284 | +252 | | +127 |
| `transform_setup`'s tilted rows a loop | bank | 121 | +21 | | |
| `fill_patch` once for both sites of an entry | bank | 48 | | -36 | |
| `bound_frame`'s ceilings one routine | bank | 89 | | | |
| `camera_setup` a loop | bank | 243 | +84 | | |

(The cycles are `objectcheck`'s, each against the change before it, and a
change that moves code moves the page crossings of what comes after, so
differences under about 50 cycles are that.) In all, from 15,779 bytes of
code in the bank to 14,420 (1,836 free, from 477), `ObjMore` from 4,901 to
3,583 (1,701 free, from 383), ANDY unchanged (70). The whole: entrances
118,016 / 197,496 / 286,805 (median / p90 / max) to 119,091 / 198,665 /
287,405 (+0.9%); walks 92,740 / 138,505 / 173,145 to 93,161 / 138,916 /
173,839 (+0.45%); the yaw sweeps 65,460 / 143,791 / 219,883 to 66,156 /
145,213 / 221,535 (+1.1%); all views 88,144 / 183,851 / 316,392 to 88,567 /
184,766 / 318,457. The level camera's bound patch is over half of that
(594 bytes for about 580 cycles on a turn's frame): the one change here
that is more than a trivial price, and its commit can be reverted alone.

The projection's cases were the largest find: the model took Z from 64 to
2^23, and nothing nearer than the clip's 256 or farther than a world's
diagonal (under 2^20) is projected, so `ZNEAR` and `ZLIMIT` came to those
and five cases and their blocks went (decision 75). The 6502's table of
cases still has an entry for every bit length of a 24-bit Z.

Looked at and left (`docs/research/objects.md` has them): ANDY's `band_test`
is the vertex pass's inline test again, but sharing it costs the bank 12
cycles a vertex; the two `BD_BEYOND` triples; `CE_TERM`; `dot3`'s three
terms; the fills' unrolled cells. ANDY could not give the bank anything:
its 70 bytes free are what it has, and the setup routines that would fit
there (`transform_setup`, `bound_frame`) reach code in the bank's first 4K,
which ANDY hides, or patch it (`fill_patch`).

## 2026-11-06: the thirteenth round, the room spent

The coordinator asked for the room the last two rounds freed to be spent on
speed, the optimisations that waited for memory first, then whatever else
the profiles found, each kept only if faster and passing `make check`, each
a commit of its own. The whole frame on the logic's disc before the round
(flip to flip, fields a frame, median / p90 / max): walking 1.83 / 4.53 /
13.6, turning 2.32 / 5.53 / 12.49, entrances 8.46 / 12.62 / 19.17.

**The first and last pieces the screen holds** (decision 100;
`docs/research/raster.md`, "Round 7"). Each screen's records of each line's
ends, 1K in the fill's bank, replace the whole-line records: a line's first
piece starts writing where the screen stops holding it, its last stops where
the screen holds it again. On the model's estimate, walking frames wrote
1,665 bytes a frame by the old records and 559 by these. Measured: the live
frames in order, `raster_frame` a median 39,396 cycles to 32,025 (p90
99,182 to 91,547); a view drawn fresh 6% slower (Driller's views, a median
109,803 to 116,242), as it pays the records' tests on every line. On the
disc, flip to flip: walking 1.83 / 4.53 / 13.6 to 1.61 / 4.37 / 13.98,
turning 2.32 / 5.53 / 12.49 to 2.13 / 5.53 / 12.95, entrances 8.46 / 12.62
/ 19.17 to 8.6 / 13 / 19.5. The routines are shared by the four copies of
the line loop and the background's: inline, the first attempt overran the
bank by about 3K. The slideshow's bank had no room for the code; its line
heads, scratch bytes and the records went to main RAM, which leaves its bank
exactly full. The fill's bank: 3,072 bytes free to 1,536.

**The 64-times quarter squares for the bounds: not built.** Measured first
by the cheaper way to the same end: an object's bounds kept at a 64th of the
scale (no `BD_STORE` shifts at all) and the frame's three ceilings shifted
down instead. `objectcheck`'s yaw sweeps went from 66,188 to 65,654 at the
median, but its walks from 93,124 to 93,625: `objects_frame`'s
`BD_BEYOND` reads every candidate's bounds every frame, and at a 64th of the
scale their top byte holds two bits, so the compare falls through to the low
two bytes nearly always, about 390 cycles a frame, besides the ceilings'
shifts. The table would keep the scale, but makes each of `bound_box`'s nine
terms a byte wider, about the cycles the shifts take. Reverted.

**A level camera's bound patch written out again** (decision 76's largest
cost, its commit reverted): `objectcheck`'s yaw sweeps 66,188 to 65,628 at
the median, entrance views 119,104 to 118,538; 594 bytes of the front end's
bank. On the disc, flip to flip: turning 2.13 to 2.1 at the median.

**The projection's patch of `pmul` and the 2D clip's passes written out
again** (decision 76's next two, each its commit reverted): `objectcheck`'s
entrance views 118,538 to 118,274 to 118,088 at the median, its walks 93,180
to 92,950 to 92,897; 665 bytes of `ObjMore`, which had 1,957 free.

**The records per buffer by ACCCON's X.** The fill's records moved from its
bank to the last of main RAM's room before `SCREEN`, whose addresses shadow
RAM has free too, so the buffer drawn selects its records and a line's are
at its own index (`docs/research/raster.md`, "Round 7"): Driller's views
fresh a median 116,242 to 114,458, the live frames in order 32,025 to
30,679. On the disc, with the reverts before it, flip to flip: walking 1.6 /
4.36 / 13.63 to 1.57 / 4.12 / 13.52, turning 2.1 / 5.51 / 12.95 to 2.09 /
5.48 / 12.96, entrances 8.59 / 13 / 19.49 to 8.55 / 13.03 / 19.4. The fill's
bank has 2,816 bytes free.

**`camera_setup`'s axes written out again** (decision 76's, reverted):
`objectcheck`'s walks 92,897 to 92,765, yaw sweeps 65,582 to 65,501; 243
bytes of the front end's bank.

The round's whole frame on the disc, flip to flip, median / p90 / max, from
the start of the round to its end: walking 1.83 / 4.53 / 13.6 to 1.56 /
4.12 / 13.53, turning 2.32 / 5.53 / 12.49 to 2.1 / 5.49 / 12.94, entrances
8.46 / 12.62 / 19.17 to 8.54 / 13.02 / 19.39. Room left: the fill's bank
2,816 bytes, the front end's bank 990, `ObjMore` 1,292, `AreaConv`'s 1,322,
main RAM before `SCREEN` none (shadow RAM's past the logic's lists still
free), ANDY 70, `ObjWork` 92, the OS's pages 52 as before. `make check`
passes.

Counted and not built (`docs/research/objects.md`, "The thirteenth round"):
the bounds at a 64th of the scale (walks lose more than turns gain) and the
64-times quarter squares (each term a byte wider costs what the shifts
did); a memo of the areas' own slanted faces (483 faces of 312 shapes: a
first visit keeps little, and its 5K fits only shadow RAM). Left of
decision 76's shares: three that cost a frame next to nothing.

What's left, and what blocks it:

- inlining `end_first` and `end_last` at the hot sites (about ten cycles an
  end, a few hundred a held frame, up to 2K a fresh one): the slideshow's
  bank is full, unless the slideshow drops the horizon's code as the live
  disc did (its views have none), about 1.2K;
- a fill routine a line rather than a row (about 5.4K a fresh view): 16K of
  code, which no bank has;
- both fills in one build, painting a frame's faces when they span many
  lines (about 40K off the busiest fresh view, nothing at the median): about
  half a K of the fill's bank, which has it now, but a painted frame's
  lines lose their records, so the frames after it write more;
- the last face into the background (about 1.6K a fresh view) and a line's
  first face kept compact (at most 1.6K): no memory needed, a good deal of
  the line loop's code;
- the transform's cache at 128 slots an array (1,152 bytes of main RAM):
  nothing found worth that room yet;
- the floor as the horizon (about 43K a turn): a picture change past the
  thin band (the platform's edge), so not taken; decision 8a.

## 2026-11-06: the fourteenth round

The coordinator asked for more speed, profiled first, each change kept
only if faster and passing `make check`, each a commit of its own. The
profiles: `livecheck.mjs --profile-rest`, and a new `--profile-all` that
counts the whole loop by routine, halves too; `objectcheck.mjs`'s; and
`rastercheck.mjs --hot` over the live check's frames in order (eight of
the logic disc's scenarios, 1,369 frames, rendered by the model into a
sequence file, a scratch script's), each instruction against baron's
listing. At an entrance the rest of the frame was 98,510 cycles (the
panel's name and message 19K, the slanted faces' planes 20K, the area's
other records most of the rest), and the front end's largest routine the
sort (12.6K a view); walking, the crosshair's EOR, the fill's calls to its
ends, and a long tail of a percent each.

What went in, none changing what any stage outputs or the picture:

- **The slanted faces' planes kept by their shape** (decision 101;
  `docs/research/objects.md`, "The fourteenth round"): a memo of 256
  entries by a hash of u and w, the globals' faces and every area's, in
  shadow RAM past the logic's lists, X set round each access. The globals'
  memo by place went from main RAM. `areacheck` (which now enters every
  area a second time, after all of them): `area_enter` a median 48,828
  cycles to 42,247 (40,647 the second time); with the logic 75,780 to
  71,807. On the disc the entrances' rest went from 98,510 cycles a frame
  to 90,674 (`ac_reduce` 8,406 to 2,824).
- **The sort's passes carry the entry moving right** and its row of the
  memory (`src/order.6502`): `objectcheck`'s entrance views, the sort a
  median 11,794 cycles to 11,218 (most 49,415 to 43,760), the view 118,117
  to 117,864; walks 92,974 to 92,891.
- **No `raster_forget` at an entry** (`docs/research/raster.md`, "Round
  8"): what each screen holds is the bytes written, which hold in any
  area's colours. Entrances, flip to flip, a median 8.48 fields to 8.15.
- **The crosshair's EOR from one column's address**: 996 cycles a walking
  frame to 686.
- **A face's vertex mask from its caller**, the loops being fixed:
  `area_enter` 42,247 to 40,990 (with the logic 71,807 to 70,287).
- **The fill's commonest ends written out** (`RASTER_ENDS_INLINE`, the live
  disc and the fill's check build, whose work moves to main RAM for it;
  raster.md, "Round 8"): Driller's views fresh a median 114,441 cycles to
  114,029, the live frames in order 36,177 to 35,579; the fill walking 0.66
  fields to 0.64.
- **A pyramid's vertices without a `CLC` a coordinate**: `area_enter` to
  40,714 (70,007).
- **The reduction by exact divisions mod 256** (each quotient a low byte
  times the divisor's odd part's inverse): `area_enter` to 38,970, most
  138,365 to 131,066 (with the logic 64,853).

The live disc's check, fields a frame, median / p90 / max, from the start
of the round to its end:

| | flip to flip, before | after | the rest, before | after |
|---|---|---|---|---|
| all | 1.81 / 5.03 / 19.39 | 1.77 / 4.95 / 18 | 0.1 / 0.53 / 5.2 | 0.09 / 0.51 / 4.94 |
| entrance (75) | 8.54 / 13.02 / 19.39 | 7.97 / 12.05 / 18 | 2.44 / 3.25 / 5.2 | 2.11 / 2.88 / 4.94 |
| standing (669) | 0.53 / 2.04 / 8.47 | 0.53 / 1.94 / 8.19 | 0.21 / 0.31 / 2.51 | 0.2 / 0.3 / 2.25 |
| walking | 1.56 / 4.12 / 13.53 | 1.54 / 4.05 / 13.37 | 0.1 / 0.54 / 4.27 | 0.09 / 0.52 / 3.55 |
| turning | 2.1 / 5.49 / 12.94 | 2.06 / 5.37 / 11.93 | 0.09 / 0.41 / 4.66 | 0.09 / 0.4 / 3.48 |

The fill, walking 0.69 / 2.18 / 8.49 to 0.65 / 2.09 / 8.18; the rest at an
entrance 98,510 cycles a frame to 86,091 (the mean); a key's first changed
view, walking 4.77 fields to 4.66 and turning 4.89 to 4.7 at the median.
`objectcheck` over every view (the check without the logic): the entrance
views 117,737 / 196,616 / 280,749, walks 92,678 / 137,430 / 173,076, yaw
sweeps 65,457 / 143,329 / 215,476. `make check` passes.

The room, at the end: the fill's bank 1,024 bytes (from 2,816: the ends
written out); the front end's bank 933 (990); `AreaConv`'s 1,191 (1,322:
the inverses); `ObjMore` 1,292; ANDY 70; `ObjWork` 169 (92: `dl_rl`,
`dl_rh` and `ac_pm` gone); main RAM before `RasterEnds` 382 (none: the
globals' memo gone); shadow RAM after `AreaShapes` to `RasterEnds` 2,864,
and the 224 bytes between the logic's lists and it.

Counted and not built (`docs/research/objects.md`, "The fourteenth
round"): a cuboid's seen faces from its box (about 600 cycles a frame, a
byte a face a slot of main RAM's new room); a pyramid's vertices written
out for each type (about 4K an entry, 1K of `AreaConv`'s bank);
`area_copy` unrolled (about 1K an entry); the sort's compare overhead
(about 1K an entrance) and a pass repeating the one two before (87 of
5,740 pairs come after one); the stretch's ends written out too (a few a
frame); the panel's glyphs by a table of their addresses in place of the
stride's additions (about 50 cycles a glyph); the keys' scan (as tight as
the VIA's 1MHz accesses let it be). Still open from before: the last face
into the background and a line's first face kept compact (much of the line
loop's code), both fills in one build (the busiest fresh views), the
transform's cache at 128 slots, and the three remaining decision 76
shares.

## 2026-11-06: Driller's sounds (track S)

Matt chose the sound as the layer after the panel. The research is
`docs/research/sound.md`. Driller's ZX code has 21 sounds, each a timing
loop on the beeper behind `$9574`, which turns interrupts off while it
plays: the whole game stops for every sound, the clock too. Two are empty
(`RET`), 5 and 10 are one routine, 13 is noise; the rest are notes and
sweeps, from a three-field bump (19, a wall and SPACE) to a 179-field fall
(20, the game's end). The logic asks for them on the laser (1), shooting
mode and the bump (19), the climb and the fall (4, 3, after the copy), a
GOTO (10, after the copy) and the FCL's SOUND and SYNCSND (5 to 21); the
interrupt plays 2 when a sensor fires. No key turns the sound off. The ST
plays samples, the CPC an AY's tables by the same numbers.

The SN76489's versions are made at build time (`tools/mksound.py`): each
routine run on the ZX snapshot, its beeper logged to the T-state, cut into
fields (the ZX's frame and the BBC's field are both 69,888 of the ZX's
T-states), and each field measured: the waveform's period by YIN, its
strongest harmonic as the tone, that harmonic's strength as the
attenuation, periodic noise under the tone's 122Hz floor, white noise for
sound 13. Sampling every 28 T-states makes a period in samples the chip's
register. Then straight-line segments within a quarter of a semitone and
a step of attenuation: 819 bytes of scripts and 42 of index for all 21
(decision 112). Two fixes after reading the first tables: a median
of two aperiodicities is their mean (sound 2 had come out as noise), and
a field with no period holds the last one (the ends of sweeps had come out
as stray low notes).

The driver (`src/sound.6502`, its model `tools/model/sound.py`) plays a
tick from the vertical sync's interrupt after the keys, tone 2 for tones
and as the noise's clock, writing only the registers that change.
`hook_sound` is `snd_ask`: the sound waits for the one playing, and the
logic waits only if one is waiting already (decision 110). After a pass,
`lv_copy_sound` asks for `Sound` by the original's copy's rule (only if
the pass redraws); the FCL's REDRAW asks for it at once and clears it.
Where it lives (decision 111): 185 bytes more of main RAM below `&3000`,
which stays inside `ObjMore`'s page alignment, so its room is still 1,292
(the first build, with the segment's read there too, pushed `ObjMore` a
page and cost it 256); the segment's read in HAZEL after `ObjWork` (93 of
its 169); the scripts in shadow RAM past `AreaShapes` (861 of its 2,864),
put in main RAM's same addresses by the loader and copied across by
`sound_init` at the start; 13 bytes of zero page; 29 of `LiveGlue`; 91 of
`BANK_DATA` for `sound_init`.

The checks: `tools/soundcheck.mjs` (`make sound`, in `make check`) boots
the disc and asks for every sound alone and a queue of 22 back to back;
every byte jsbeeb's SN76489 took, tick by tick, is the model's (901 ticks,
1,559 bytes). `tools/livecheck.mjs` now captures the chip over its whole
run too, and checks each pass asked for the transcription's sounds
(`tools/mklive.py --trace` records them): 2,172 passes, 171 sounds, every
byte of 19,074 ticks the model's. A first soundcheck failed by a tick: the
harness had put a sound in while the emulator stood inside the interrupt;
it now asks from `live_loop`, as the logic does.

The cost, `make check`'s live check before and after: the vertical sync's
interrupt 832 / 1019 / 1264 cycles (median / p90 / most) to 899 / 1087 /
1660; `snd_tick` 216 / 430 / 557 with a sound playing, 59 idle. Fields a
frame, flip to flip: all 1.77 / 4.95 / 18 to 1.77 / 4.97 / 113.76; walking
1.54 / 4.05 / 13.37 to 1.54 / 4.08 / 13.49; turning 2.06 / 5.37 / 11.93 to
2.07 / 5.31 / 11.92; entrances 7.97 / 12.05 / 18 to 8.05 / 12.21 / 18. The
113.76 is the logic waiting for a sound to be taken at the minute's turn
in `minutes.txt` (sound 11, 157 fields, with more queued behind it), where
the original would stop for each whole sound.

Left for Matt: decisions 110 (whether and how long the logic waits), 112
(the measured remake's choices) and 113 (the CPC's AY sounds instead).
Left for the layers after: sound 2 with the sensors, 20 and 6 with the
game's end, and when the laser's lines show around sound 1.

## 2026-11-08: the audit, and Driller's drilling rigs

Toward Driller whole, in Matt's order of layers (rigs, laser, sensors, the
end and a new game; the sound and the panel done). First an audit of every
part of the full game against the port, from the original's listing and
the code (`docs/research/game-audit.md`, with what each layer left needs);
then the rigs.

**The original** (`$BEFA`, read from the listing; `zx-logic.md`, "The
rigs"): D drills and C collects, alone in a pass. A rig goes 12 cells
across in front of the probe by the yaw's sector, on the floor or on a
shown cuboid wide enough, with nothing in its box; it finds 100 − 100 d /
reach percent of the area's gas, d the cells from the gas; its yield is one
of eighteen figures in a rotation picked by the clock's frames the first
time; the score gains yield × percentage × 10; half or more counts a safe
sector, and the eighteenth wins (`GameOver` 5). Every step shows a message
for 50 frames with the game stopped, and a rig's redraw runs there and
then. There's no animation of the rig on the ZX.

**Transcribed** (`tools/logic/rig.py`) and checked against the original:
`tests/logic/rigs.txt` (every refusal, no gas, 87%, 57%, 45% on a
platform, 11%, walking into the legs before and after the area loads them,
collecting), `rig-win.txt` (the eighteenth), and the fuzz with D and C
among its keys (120 walks, 9,112 passes, the same). The fuzz found two
things the harness had to hold: the sensors fired at the shield during a
rig's 200 frames of waits (the oracle now keeps every sensor from firing:
its interrupt's read of the fire list answers none), and the rig's redraw's
line of sight leaves `Collided` for the pass's events, a quirk of the
original's kept as `tests/logic/rig-sensor.txt` (the oracle's `Collided` is
taken at the redraw).

**In 6502** (`src/logic/rig.6502`, `rigdb.6502`): 1,352 bytes as first
written, more than `LOGIC_BANK`'s room, so the part that scans the records
stays there with the messages and the rest went to `LOGIC_CODE_BANK`, with
the far calls in main RAM. `make logic6502`: every scenario and 60 walks,
and a 300-walk fuzz, the same as the transcription.

**On the disc**: a rig's pass enters the area again (decision 122), so the
rig's parts are drawn where the logic moved them, and its messages show in
the panel's message line in turn (decision 121; the font gained a `%`).
The disc's yields are rotation 0 always, as nothing counts the seconds
(decision 120). The live check renders each frame with the globals where
the logic has them, and holds each message to the transcription's in its
turn. Its first run with the rigs also found a fault older than them: a
poke or a GOTO right after a pass that loaded an area could go in before
the disc took the area's colours (`goto 14 34`, out and back by K, `goto 7
13`); the check now settles first. `make check` passes.

The cost, on the live check's scenarios before the rigs, the disc before and
after (fields a frame, flip to flip, median / p90 / max): all 1.77 / 4.97 /
113.76 to 1.76 / 5 / 113.75; walking 1.54 / 4.08 / 13.49 to 1.55 / 4.08 /
13.49; turning 2.07 / 5.31 / 11.92 to 2.07 / 5.38 / 11.93; entrances 8.05 /
12.21 / 18 to 8.05 / 12.22 / 18 (the check's settling before pokes moves
its timings a little: 4,069 frames to 4,084). With the rigs' scenarios, all
4,160 frames: 1.8 / 5.1 / 113.75; the rigs' own frames, after a rig's
entry, are entrances' (8.35 / 12.98 / 18.2 over 87). The room, logic disc,
before and after: `LOGIC_BANK` (`live_glue_end` to `LOGIC_DB`) 863 to 482
bytes; `BANK_DATA` (`area_conv_end` to `&C000`) 1,100 to 135; `ObjMore` to
`&3000` 1,292 to 780 (`LIVE` and `LogicWork` grew past a page of the maths'
alignment); `Work` 185 to 180. The free disc, whose `LiveGlue` shares
`LOGIC_BANK`, has 19 bytes left there.

Not done: the laser (the audit's plan: the lines as frames of their own,
as the crosshair is, and the pick from the front end's faces, which needs
an object a face), the sensors, the end and a new game. Left for Matt:
decisions 120 to 122.

## 2026-11-08: room in the logic's banks

The layers to come (laser, sensors, the end, the information screen) need
room, and `LOGIC_CODE_BANK` had 135 bytes, `LOGIC_BANK` 482 (the
free-camera disc's `LiveGlue` 19). Nothing the logic does changed: every
pass is the transcription's (`make logic6502`) and every frame the model's
(`make live`); `make check` passes after each commit.

**Denser tables** (`LOGIC_CODE_BANK`, 372 bytes):
- The key actions were two 128-byte tables by code, for 40 codes. Now one
  table of the codes from `KEY_LOW` up, SPACE below it and none above it
  in `action_of`, and in shooting mode the four movement actions 3 to 6
  become 29 less (the original's shooting table says exactly that for
  every key). `tools/mklogicdata.py` asserts the dense scheme against the
  original's search, every code, both modes. 185 bytes, for 14 to 27
  cycles a pass.
- The 72 (sin, cos) pairs are the sines of the first 36 angles, the next
  36 their negatives, a cosine the sine 18 on; `tools/mklogicdata.py`
  asserts the symmetries. 88 bytes, for about 60 cycles in a step.
- `ld_area_of` (128 bytes, by area id, 29 used) is the 29 ids, searched by
  `lv_switched` when an area changes. 99 bytes.

**Axes by index** (`LOGIC_CODE_BANK`, 309 bytes): `next_crossing` had a
written-out block for each of x, z and y, with the original's quirks
between them (a later axis that crosses first sends the search to the
next axis, whichever it was). Now one body, the axes by position in the
order x, z, y, a later axis that crosses first restarting from the next
position. `move`'s cells and crossing bits, deltas and stop pulls are
loops over the axes too. Together: a probe step's pass 9,711 to 10,258
cycles (5.6%), a jet step's 10,941 to 12,071 (10%), the rest within 15
cycles; 309 bytes. (A pass is a field or two of a frame's work: the step's
frames are the pass's PASS_FIELDS.) `keep_clear`, `at_extent` and
`cross`'s `across` have the same three blocks and were left: 20 to 65
bytes each for 60 to 300 cycles a walk.

**Code that only a pass runs, in shadow RAM** (1,288 bytes out of the
banks, 907 of them `LOGIC_CODE_BANK`'s and 381 `LOGIC_BANK`'s): a pass
runs with ACCCON's X set (`lv_pass`), so code at shadow RAM's addresses
runs as fast as anywhere, and the pass already reads its lists by face
there. `RigCode` holds the rigs' code (`rig.6502`), `suitable` and the
rigs' unchanging messages (`rigdb.6502`), after the sounds' scripts. The
loader puts it in main RAM at those addresses (part `RIGC`) and
`sound_init` copies it across with the scripts. It calls nothing in the
banks: the far calls (`far_rig_*`, which page `LOGIC_BANK` for `suitable`
too), `wait` and the hooks are main RAM's. The logic's
check build declares `RigCode` in main RAM (`RIGC`, loaded by
`tools/logiccheck.mjs`), so the shadow placement itself is the live
check's, over the rigs' scenarios. Cost in cycles: none.

**The room, logic disc, before and after:** `LOGIC_BANK` (`live_glue_end`
to `LOGIC_DB`) 482 to 863 bytes (the free-camera disc's 19 to 400);
`BANK_DATA` (`area_conv_end` to `&C000`) 135 to 1,723; `ObjMore` to `&3000`
780, untouched; shadow RAM past `rig_code_end` to `RasterEnds` 715 bytes.
The main RAM below `&3000` has a gap of its own: `ObjMore` starts on the
next page after `LogicWork` for the maths' alignment, so `LIVE`,
`AreaCode` and `LogicWork` can grow into that gap for nothing (the bytes
before the page), but shrinking them gives `ObjMore` nothing; left alone
as the other agent works in `ObjMore`.

Not done, and how far each would go: the FCL's cold handlers
(`fcl_swapjet`, `fcl_goto`, the bit and variable ones) to `RigCode`, about
300 bytes of `LOGIC_BANK` for nothing in cycles, when shadow RAM has the
room to spare; the figures' arithmetic in `LiveGlue` shared (`div_times`
and `fig_ratio` are two shift-and-add loops), tens of bytes.
