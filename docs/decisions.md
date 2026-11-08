# Decisions

Every call the port makes that the original didn't, numbered, dated, with
the reason. Nothing changes quietly. Matt makes the design calls. Where
Matt asked for autonomous work, the call is made and marked so, to
revisit freely.

The brief's D1-D7 (`BRIEF.md`, section 5) are decisions 1-7.

## 1. The specification (2026-10-31)

**Driller's ZX retail version is the specification for the geometry, the
logic and the view**: its database, camera, steps, turns, projection and
view rectangle. Its colour isn't used (decision 2): the colours come from
the colour study (decision 8).

Why: the database is the same in every version; the ZX's is
byte-identical to ScummVM's supported variant, the siblings' SkoolKit
harness can run it headless as an oracle, and the BBC view keeps its
geometry (decision 2), so the ZX's image can still check the model's.

## 2. The screen: MODE 2, many colours (2026-10-31, Matt)

Matt: "many colours and as fast as you can make it", after "we can
consider mode 2 and ordered dithering too".

**MODE 2, 8 colours, with ordered dithers of pairs; a 104 × 104 view**,
which is the ZX's 208 × 104 at half the width with the ZX's field of view,
in a 128-wide screen (R1 = 64).

- Against the brief's option D (120 × 101, the PC's EGA view at half
  width): 104 × 104 keeps the ZX's geometry, so the ZX remains the oracle
  for which face covers which pixel, and it's 5,408 bytes a frame against
  6,060.
- Against MODE 1 (option C): twice the colours for half the width, at
  the same cost a byte.
- The view's size and focal lengths are build constants, so a larger
  view can be measured later.

## 3. The draw order (2026-10-31, autonomous)

**The original's sort, processed front to back into a span buffer**
(`docs/engine.md`, stage 8). It reproduces the original's image exactly,
glitches included. Starting each frame's sort from the last frame's
order (the brief's D3 b) is an optimisation to measure, not a change.

## 4. The pace (2026-10-31, autonomous)

**Animate the original's steps and turns** (the brief's D4 a): the logic
takes the original's steps exactly, and the renderer shows the frames in
between. The rate is to set once it can be seen.

## 5. The machine (2026-10-31, autonomous)

**The BBC Master 128 first.** Shadow RAM holds the second 16K buffer at
the same address, as in Solid Elite; the 65C12's instructions are used
freely; HAZEL and four banks of sideways RAM hold the tables and data. A
Model B edition is for later, if the Master's numbers leave room.

Why: MODE 2's 16K screen double-buffered doesn't fit a B beside the
engine, and Matt plays on a real Master.

Matt, later the same day: "I prefer not looking at coprocessor right now,
concentrating on what a stock Master could do." So the engine targets a
stock Master 128: no second processor, and no co-processor edition for
now.

## 6. Rights (2026-10-31)

The build reads Driller from fetched copies (`make fetch`, into
`originals/`, git-ignored) and commits nothing of it.

**The public disc, `freescape.ssd`, is a tech demo that shows Driller's
scenes, attributed** (Matt, 2026-10-31: "I think it's fair use to show
driller scenes -- we aren't misrepresenting driller here, we'd attribute
accordingly (much as the other earlier work). this is a tech demo only
though"). The disc says on it that Driller is Incentive Software's, and
it's a demonstration of the engine, not a release of the game. The
repository still commits nothing of Driller's beyond that disc: the
build derives the disc's data from the fetched copies.

## 7. Scope (2026-10-31)

Driller first, with the loader kept general (Dark Side and Total Eclipse
share its layout).

## 8. Where the colours come from (2026-10-31, autonomous)

**The Atari ST's colours, shown by MODE 2 patterns of up to three of the
BBC's eight colours, chosen to look right on an RGB monitor and on a PAL
television** (`docs/research/colour.md`).

- The ST's per-area palettes give each face's colour index its colour (16
  colours an area from 4,096). Every colour version recoloured the faces
  for its own palette, so each face's colour index comes from the ST's
  database, object by object, and the geometry from the ZX's (decision 1).
- Each colour is a 2 × 4 pattern anchored to the screen, chosen by OKLab
  distance with penalties for texture, crawl through PAL, clashing hues
  and hue shifts; colours an area tells apart get different patterns.
- Why: the most colours of any version, each area its own. The PC's EGA
  colours are the fallback if the ST's darkest shades, which become
  sparse dots, look wrong in play (one constant, `CHOSEN` in
  `tools/colour/design.py`).

Matt asked for PAL to be used where it can (2026-10-31): jsbeeb's PAL
television blurs a dither as a real one does, and the patterns were chosen
through a port of its shader (`tools/pal.py`), checked against the shader
itself.

## 8b. Patterns for each display (2026-10-31, Matt)

Matt asked for PAL against RGB to be "something controllable outside":
it is a different table of patterns, nothing else. The engine carries a
table chosen for an RGB monitor, one for a PAL television and one for
both (`make colours`; `tools/model/colours.py`'s `display`), copies the
chosen display's patterns for the area into the row writer's live table
on entering an area, and a key switches display and redraws. **The
disc's default is PAL**: Matt's preference, the README's jsbeeb link,
and a BBC on a television. The model's default is PAL too
(`FREESCAPE_DISPLAY`).

## 8a. The background (2026-10-31, autonomous)

The view is cleared to the sky, which is black in every area of the ST's
version, and the ground is the area's floor object's top face, drawn like
any other face. So the rasteriser's horizon goes unused for Driller, and
stays for games that need it.

## 9. Where the screen sits (2026-10-31, autonomous)

The screen sits where MOS 3.20 puts MODE 2 at `*TV 0,1`: the CRTC's
vertical sync at the row MOS 3.20 computes (its table's row plus the
`*TV` setting plus one), fixed in the build so the raster timing never
moves. Following the machine's CMOS `*TV` setting at start-up is the
alternative, if a real display wants it.

## 10. The keys (2026-10-31; corrected the same day; motion moved by Matt)

Driller's own, from the ZX's key table (`docs/research/zx-logic.md`), but
for motion, which is on the BBC's traditional keys at Matt's asking ("Can
you use more traditional BBC-like keys for motion please"):

- **Z and X turn left and right; : and / walk forward and back** (the
  keys printed `*` and `?`), as so many BBC games move. The cursor keys do
  the same, as the ZX's cursor joystick (5, 6, 7 and 8). Driller's own Q,
  W, O and K still work too.
- So Driller's Z and X (the turn's and the step's size down) move to **f0
  and f2**, and its A and S (up) to **f1 and f3**.
- The rest are Driller's: P and L look up and down, N and M roll, R and F
  rise and fall, U turns round, 0 or COPY fires, D drills, C collects,
  SPACE changes mode, B shows or hides the crosshair, I shows information
  (ESCAPE is the ZX's 1 there). T and Y do nothing in play. Driller has no
  key to centre the view, so there isn't one.

The keys are read once a field (`src/input.6502`).

## 11. Rounding in the matrix and transform (2026-10-31, autonomous)

The original builds `M = S · Rroll · Rpitch · Ryaw` in signed bytes, with
the projection's scaling `S = diag(32, 64, 21)` folded into the matrix,
and rounds every product of the transform
(`docs/research/zx-driller.md`). The engine keeps the composition and its
per-step rounding but leaves `S` out of the matrix (1.0 = 64 on every
axis) and puts it in the projection's focal lengths, and its transform
rounds nothing (`docs/engine.md`, stage 3).

Why: the original's z row has 21 levels to a unit, and its rounded
products can't be cached; exact products can, which is what makes a step
cost no multiplies. The views agree with the original's to within the
rounding, and the ZX oracle checks how far.

## 12. The fill rule (2026-10-31, autonomous)

The original walks each edge in whole-pixel steps; the engine covers a
pixel when its centre is inside the polygon (`docs/engine.md`, section 9),
with vertices in sixteenths of a pixel.

Why: sub-pixel vertices keep edges steady as the camera moves a frame at a
time (decision 4), which whole-pixel vertices don't. Compared with the ZX's
images, edges may differ by a pixel.

Matt, on decisions 11 and 12 (2026-10-31): "I much rather we have a faster
version than a pixel correct one." So the oracle checks the model's views
against the original's within a tolerance at edges, and speed wins
wherever exactness against the original would cost it. The 6502 still
matches the model byte for byte.

## 13. Which faces are drawn (2026-10-31, autonomous)

A face is drawn when the camera is on its front side by an exact test
against its plane in world space; the original decides from the turn of
the face's first three projected points (`docs/research/model.md`).
The two disagree only on faces seen edge-on or smaller than a pixel: over
the 65 entrance views, 891 faces drawn against the original's 892.

## 14. Lines and sensors (2026-10-31, autonomous)

A line is drawn as a quadrilateral a pixel wide, and a sensor as a single
pixel, so both go through the one rasteriser. The original draws sensors
(ScummVM doesn't) and sorts them with the objects, and so does the
engine.

## 15. A near plane (2026-10-31, autonomous)

The original's view volume is a pyramid with its apex at the eye; the
engine clips at `ZNEAR`, a few world units in front of it
(`tools/model/view.py`), so the projection never divides by a tiny `Z`.

## 16. The coarse cull (2026-10-31, autonomous)

The engine's coarse cull is a test against the view's cone, not the
original's box round the view's octant. It never removes an object that
draws: checked over 10,920 camera orientations (journal, 2026-10-31).

## 17. The projection, and a guard band (2026-10-31, autonomous)

**The projection is a normalised reciprocal times quarter squares**, to
sixteenths of a pixel (`docs/research/maths.md`): the case comes from Z's
bit length, a 10-bit index looks up a 16-bit reciprocal, which is patched
into the code once a vertex, then three byte products. It's within about
2/16 of a pixel on the view, never goes backwards as X grows, and can step
back a sixteenth as Z crosses a power of two. Against it: log and
antilog tables (less precise for more table), and a real divide (slower).
The original's focal length is rounded to whole sixteenths (`FX` = 1268,
`FY` = 2 `FX`), so the clip and the projection share it; the projection
takes any Z from one world unit, and the near clip cuts at four
(decision 15). The tables go in HAZEL.

**Faces are clipped in 3D to a guard band**, `|X| <= 16 Z` and
`|Y| <= 8 Z`, when a vertex lies outside it (`tools/model/clip.py`). A
vertex far to the side of a near one projects past 16 bits, and a
saturated vertex bends the 2D clip's edges; the band is wide enough that
few faces need it, and its planes are shifts on the 6502.

## 18. The corner that throws the probe out (2026-10-31, autonomous)

The original has a bug: a step that ends exactly on a cell corner while
moving down an axis overshoots that axis, throws the probe out of the
area, and the next move hangs the game (`docs/research/zx-logic.md`). The
port fixes it: the rule that moves the axes across together never moves
an axis already at its target cell. That removes the overshoot and the
hang, and changed nothing else in 1,000 random walks (110,359 passes)
compared with the original. The Python transcription
(`tools/logic/`) reproduces the bug, so the oracle checks it; the fix goes
into the port's own logic, with a switch in the transcription to model
it, when the 6502 logic is built.

## 19. Held keys act in the ZX's order (2026-10-31, autonomous)

The original reads up to five keys a pass and acts on them in its
keyboard's order, so turning and stepping together always turn first.
The port does the same, so combinations behave as they did.

## 20. The rasteriser's edge cases (2026-10-31, autonomous)

- A pixel centre exactly on the horizon is ground.
- When a line's pool of gaps is full (a pathological scene), the
  face-line that doesn't fit isn't drawn and `rs_overflow` is set; the
  model does the same.
- The rasteriser's code, row runs and work go in one sideways RAM bank,
  with its inputs in main RAM, leaving HAZEL to the maths tables.
- A background line the back buffer already holds isn't rewritten, so
  anything else that draws on the screens calls `raster_forget`.

## 21. The flip comes as the beam leaves the view (2026-10-31, Matt)

A finished frame is shown as soon as the CRTC has finished fetching the
view, not at the vertical sync (Rich Talbot-Watkins's Chase H.Q. and Teddy
Boy, `docs/research/rtw-sources.md` §3.1). The lines below the view are the
same in both buffers, so nothing tears, and a frame that takes 2.3 fields
is shown every 2.3 fields rather than every 3. User VIA T1 runs free with
a field's period, in step with the sync, to time it (`src/screen.6502`).
Matt: ACCCON's D is plain TTL on the video's RAM select, so it switches
instantly, as jsbeeb models it; this is the design, and the VSync flip is
only a build option (`-D VSYNC_FLIP=TRUE`).

Anything drawn outside the view must then be the same in both buffers at
every flip (`docs/engine.md`, section 1, has the two ways).

## 22. The slideshow disc (2026-10-31, autonomous)

Until the renderer's front end is fast, the public disc draws
precomputed raster inputs for Driller's 65 entrance views, not the game:
the model works out each view's faces, and the Master draws them itself.
The rasteriser lives in bank 4 and the views in banks 5 and 6, loaded by
`*SRLOAD ... Q`; the text is the MOS's font (read through OSWORD 10), 16
characters a line, kept the same in both buffers. Each view is held for 100
fields, and the figures shown are the mean since it came up, refreshed
every 25 fields. It gives way to the real thing as soon as the pipeline is
whole.

## 23. Sloping edges by a DDA (2026-10-31, autonomous)

The rasteriser steps a sloping edge by an 8.8 DDA with no divide: dy is
normalised to a byte, its reciprocal comes from a 128-byte table, and the
gradient and the first line's offset are quarter-square products
(`docs/research/raster.md`). Against the exact pixel-centre rule over
Driller's views, 98.7% of edge-lines land exactly and the rest one pixel
either way, never more; an edge never passes its far vertex. The model's
`raster.py` steps the same way, so the 6502 still matches it byte for
byte. The rasteriser builds its own quarter-square table at `raster_init`
(the slideshow has no HAZEL tables); the engine can share one later.

## 24. Clip crossings by one 16-bit fraction (2026-10-31, autonomous)

The guard band's and the 2D clip's new vertices come from one 16-bit
fraction a crossing, taken from the edge's inside end so that two faces
sharing an edge cut it at the same point; both distances are shifted
until their difference fits 16 bits, so the 6502 always does one unrolled
16-by-16 division. The near clip stays exact (its cut points are four
units from the eye). Against the exact model, 149 of 32.6 million pixels
differ over the views checked, and the order changes in 3 views
(`docs/research/objects.md`).

## 25. Outcodes from the projection, and the drawn test (2026-10-31, autonomous)

A vertex's outcodes against the view come from its projected position by
16-bit compares, and a face wholly beyond `x = ±z` or `2y = ±z` (outside
the view's sides) is dropped first by compares, which changes no pixel.
A face is drawn when it has three or more vertices not all on one line,
decided by signs first; it replaces the area test.

## 26. The floor stays a face (2026-10-31, autonomous)

Drawing each area's floor as the horizon's ground (an amendment to
decision 8a, built in the model behind `FLOOR_AS_HORIZON`, off) was
measured and not taken: 0.43% of pixels change over the views, but near a
platform's edge looking out up to a quarter of a view changes (the
original's void past the edge becomes ground), and the thick floors of
areas 14 and 18 uncover objects below their tops. Against the ZX oracle,
99.37% of pixels agree against 99.95% with the floor as a face. The floor
costs about a sixth of the front end (journal, 2026-10-31), so it gets a
cheaper path instead.

## 27. The projection's accuracy budget, and its method (2026-10-31, autonomous)

Measured with the model on camera walks from every entrance
(`docs/research/projection.md`): what shows as the camera moves is jitter,
an error that differs from vertex to vertex; an error that only steps one
way as X or Z grows hardly shows. So **the budget is: the projected
position never steps backwards as X or Z grows, and stays within 4/16 of
a pixel on the view.**

**The projection is a 9-bit reciprocal and two byte products**, within
that budget, replacing decision 17's first method (which was within 2/16
at about twice the cycles). Two entries give exactly its result more
cheaply for vertices sharing coordinates: `project_z` (the last call's Z)
and `project_y` (its X and Z, only the y). Its input must be within
`|X| <= 25 Z` and `|Y| <= 12 Z`, which the guard band (decision 17) is
inside.

## 28. The span buffer stays, against a painter's fill (2026-10-31, autonomous)

A painter's fill (faces back to front over the backmost face and the
background) was built, checked exact, and measured slower at the median
over Driller's 65 views: every painted face rewrites bytes the floor or
sky already wrote. It wins only on the busiest views. The span buffer
stays the engine's fill; the painter's build stays checked
(`RASTER_OTHER_WAY`) for comparison. Choosing per frame by its face-lines
would gain a little and needs both in the bank; not built.

## 29. Polar forms for a level camera (open, for Matt)

Rich Talbot-Watkins's PORTAL caches each point's angle and log distance
while the eye stands still, so a turn costs lookups. Modelled against
Driller's views (`docs/research/projection.md`): with 2,304 steps a turn and
12-bit logs it's within 3/16 of a pixel, and turning flicker is lower than
the byte matrix's; a turning frame's transform and projection would come
to about 5K cycles. It needs a second pipeline beside the matrix one (for
pitch and roll) and a sideways bank of tables. Open until the rest of the
frame is fast enough for it to matter.

## 30. The live disc (2026-10-31, autonomous)

**`build/live.ssd` draws every frame on the BBC from the camera alone**:
`objects_frame`, then `raster_frame`, with no faces worked out off the
BBC (`docs/research/live.md`). Its camera is free, not yet Driller's
logic: Driller's keys and the cursors turn, walk (through anything,
`LIVE_STEP` world units a frame along the view), look and roll; SPACE goes
to the next entrance; with no key for `DEMO_FIELDS` fields a demo turns on
the spot and goes on to the next entrance after a whole turn. It redraws
every frame even when nothing has moved, so the figures it shows (frames a
second, fields a frame, and each half's cycles, timed on the BBC by User
VIA T2) are always the whole pipeline's.

Why: the slideshow's figures were the fill's alone (decision 22); this is
the engine as it stands, measured on itself. Proposed: it takes the
slideshow's place as the public disc.

## 31. The live disc's memory (2026-10-31, autonomous)

- The sideways banks: the area records where `tools/mkareas.py` packs
  them (from bank 4), the rasteriser in 6, the object pipeline's code
  with the maths' in 7; the text's font and the disc's own tables after
  the records in the last records bank.
- HAZEL: the maths' tables and the pipeline's work, with ACCCON's Y set
  for good once the OS is gone.
- **The transform's cache in main RAM's `&3000-&3FFF`**, which section 8
  of `docs/engine.md` keeps for per-buffer data: only `objects_frame`
  touches it, and the frame clears ACCCON's X before calling it. The
  projection's larger tables (decision 27) left HAZEL no room for both the
  cache and the work, and main RAM below `&3000` has none.
- The rasteriser's input in the OS's pages below `&0D00`, with the object
  pipeline's output laid over it array for array, so nothing is copied
  between them. `LogicWork` will want those pages (`docs/research/live.md`
  says where the input can go then).
- `area_enter`'s code in main RAM (section `AreaCode`), since it pages the
  records' banks in.

## 32. The span buffer's pools hold 127 gaps (2026-10-31, autonomous)

Each of the span buffer's four pools holds 127 gaps rather than 254, to
free bank space for faster code. Driller's views need at most 102 (median
30, journal 2026-10-31); two synthetic scenes now overflow and take
decision 20's rule, in the model and the 6502 alike. No view of Driller's
changes.

## 33. The cone (2026-10-31, autonomous; amends 15 and 17)

A face the projection can't take whole is drawn as the view's rectangle
clipped by its edges' planes through the eye: exact, with no near plane
and no guard band (`docs/research/objects.md`). Lines and points take a 3D
clip by crossings. Against the model before it: 755 of 3,515,200 pixels
change over the entrance views and walks, none in the draw order; against
the ZX oracle 1,389,622 of 1,406,080 pixels agree (1,389,686 before). It
costs more than the clips it replaced at the median; the next round makes
its crossings cheaper.

## 34. Area records built at area entry (2026-10-31, autonomous; amends 31)

`area_enter` builds the current area's records from the logic's copy of
Driller's database (the original layout, in sideways RAM), with the ST's
colours and the globals from a build-time table, into one small working
copy; `tools/mkareas.py` is the model of the conversion, and
`tools/areacheck.mjs` holds every area to it. The conversion's own route
(a gcd-reduced cross product and a rule for collapsed apexes) matches the
model on all of Driller and isn't general. With the logic present,
visibility comes from its `ix_flags`. The logic's database sits in bank 4,
the conversion in bank 5, and the `f64` table in HAZEL.

## 35. Rectangles wind like every other face (2026-10-31, autonomous)

A rectangle's loop winds anticlockwise on both sides, like every other
face's. No pixel changes.

## 36. The pace, and the frames between passes (2026-10-31, autonomous; amends 4)

The logic takes a pass every `PASS_FIELDS` fields while a key is held, so
a held key gives a little over one step or turn a second, close to the
original's pace of about one redraw a second (`docs/research/live.md`).
The renderer draws every frame in between: a turn goes the short way in
5° steps, any other move in a straight line along the segment the logic's
move checked, at a fraction set by the fields elapsed; on the probe the
height holds until the step ends, where the climb or fall happens; the end
snaps to the logic's position. A doorway walk is shown in the old area,
then the new area appears. Matt can change the pace.

## 37. Keys tapped between passes still act (2026-10-31, autonomous)

A pass takes the keys held, or pressed since the last pass, so a tap
shorter than the time between passes isn't lost.

## 38. The crosshair at half width (2026-10-31, autonomous)

B shows or hides the original's crosshair, EORed into the view as the
original does, at MODE 2's half width.

## 39. The logic's angles taken mod 72 (2026-10-31, autonomous)

The renderer takes the logic's angles modulo 72. Area 2's entrance 16
shares its id with a cuboid, so a GOTO there takes the cuboid's bytes as
the camera's and gives a roll of 127, as the original does; modulo 72 it
draws.

## 40. The live disc's memory, with the logic (2026-10-31, autonomous; amends 31 and 34)

`docs/research/live.md` has the map, every boundary ASSERTed: the logic's
database and its code in bank 4 with the live disc's glue, the rest of the
logic, the font and the area conversion in bank 5, the rasteriser in bank
6, the front end in bank 7; LogicWork and a section for the front end's
growth (`ObjMore`) in main RAM; RasterIn in the OS's pages; the
transform's cache and the sort's memory in main RAM at `&3000` (ACCCON X
clear) and the logic's lists by face in shadow RAM at `&3000` (X set round
each pass).

## 41. The cone's lines, and the 2D clip's crossings by reciprocal (2026-10-31, autonomous; amends 24 and 33)

The cone (decision 33) makes no line for an edge with both ends behind
the eye; takes a crossing on a side of the view's rectangle from the
line itself, rounded half up from the side's corner inside it; joins two
consecutive edges' lines at their shared vertex's projected image; and
takes the lines of edges with both ends in front first. The 2D clip's
crossings come from a nine-bit reciprocal rather than a division, within
about 2^-8 of it and still from the edge's inside end, so shared edges
meet. Together, against the model before them (journal 2026-10-31): 333 of
3,515,200 pixels differ over the entrance views and walks, 8,961 of
35,314,240 over every check view, single pixels along long edges; against
the ZX oracle, 1,389,703 of 1,406,080 pixels agree (1,389,643 before).

## 42. The idle loop (2026-10-31, autonomous; amends 30, 36 and 37)

When the camera, the areas entered, the crosshair and every object's
visibility are the same as the frame last handed over, the live disc draws
nothing and flips nothing; keys, passes and the text go on, so a key starts
the next frame at once (`docs/research/live.md`). Comparing against the
last frame handed over is enough: the other buffer is never shown without
a frame drawn into it first. Each logic pass waits for a key reading made
after the last pass ended, a turn shows its first 5° step one field into
its pass, and a tap acts once (an earlier fault took one tap twice). Frame
figures are now taken over the frames drawn.

## 43. Driller's 192-line screen, and the memory it frees (2026-11-01, autonomous; amends 2, 9, 31, 34, 40)

The screen is 24 character rows, 192 lines, as Driller's and the ZX's
are: the 104-line view and ten rows below it, at `SCREEN` (12K a buffer),
kept centred where MOS 3.20 puts MODE 2. That frees 4K of main and 4K of
shadow RAM, into which the area's working copy, the front end's tables,
the maths code and the rasteriser's state moved (`docs/research/live.md`
has the map, every boundary ASSERTed). The view doesn't change; the live
disc's text is condensed into the ten rows, the attribution kept
(decision 6).

## 44. The row fill stays, against a column fill (2026-11-01, autonomous)

A column fill (faces as byte columns written straight down the screen's
layout, as PORTAL and lander fill) was modelled exactly
(`tools/model/colfill.py`, the row fill's bytes on every scene, view and
live frame) and priced from 6502 kernels measured in jsbeeb
(`docs/research/colfill.md`): a median of 123,467 cycles on Driller's 65
views drawn fresh against the row fill's measured 110,119, faster only on
the busiest. Most of Driller's bytes are dithered, and down a column the
pattern byte changes every line, so every store needs a load. The row
fill stays; `make colfill` keeps the study checked. A column fill for busy
views alone would need dithers that don't change line to line, which
changes the picture (decision 8).

## 45. The cone's side crossings by reciprocal (2026-11-01, autonomous; amends 41)

The cone's crossings on the view's sides take the 2D clip's nine-bit
reciprocal (`clip.side_d`), rounded and capped at the side's length,
instead of a division. Against the model before it: 382 of 3,515,200
pixels differ over the entrance views and walks (at most 43 in one view),
no draw order changes; against the ZX oracle away from edges, 1,293,937 of
1,294,548 pixels agree (1,294,087 of 1,294,706 before).

## 46. The cone's lines from images (2026-11-01, autonomous; amends 33, 41 and 45)

An edge with an end the projection takes gets its line through that end's
projected image: through both images when the projection takes both, or
toward the edge's vanishing point for a box edge, with no 32-bit normal;
and a unit line's side crossing is exact (`clip.UNIT_SIDES`). Against the
model before them (journal 2026-11-01): 991 of 3,515,200 pixels differ over
the entrance views and walks (at most 43 in one view), no draw order
changes there; 11,753 of 35,314,240 over every check view, the order
different in 6; against the ZX oracle away from edges, 1,294,081 of
1,294,700 pixels agree (1,293,937 of 1,294,548 before).

## 47. Driller's panel (2026-11-01, Matt chose it as the next layer)

The panel is the Atari ST version's console (taken from its program at
build time, never committed: decision 6), cut rather than scaled to
MODE 2's 128 pixels: one MODE 2 pixel is two of the ST's, each the
brighter of its pair, each ST colour a pattern from the colour study
(decision 8); the mouse's buttons (arrows, information, save and load)
are dropped to fit, with X, Y and Z where save and load were. Its fields
are the original's (`$B72B`, `docs/research/panel.md`) but for the clock,
the seismograph and the rigs' animation, which wait for those layers; the
vehicle is the ST's jet or probe picture with its name. The numbers are a
3 × 5 font of the port's own, the labels white (the ST's red blurs away
through PAL). Every field is redrawn after a pass when its value changed,
into both buffers inside the beam's window (decision 21). The frames a
second stay on the screen beside "tech demo", with the credit to Incentive
above the view (decision 6); the cycle figures and key lines are gone. The
packed picture is loaded once into the transform's cache before it's
needed, and the panel's data takes the MOS font's place.

## 48. The pace, and the sizes the game starts with (2026-11-01, autonomous, proposed for Matt; amends 4 and 36)

Matt, on the live disc: "it seems impossible to steer. tapping left seems
to always turn 3 steps". Driller starts with a turn of 15° and a step of
250 world units, and decision 36's pass every 44 fields made a tap three
5° frames and a held key a move about once a second.

- **The game starts with the smallest turn, 5°, and a step of 25 world
  units**: the database's first turn and step (its header's bytes `$C2`
  and `$C3`, which a new game takes) and the variables set from them are
  changed at build time (`tools/logic/state.py`'s `port_start`), so a tap
  turns or steps the least that's useful. f0-f3 change them in play, as
  before (decision 10).
- **A key going down gives a pass at once; the keys held alone repeat
  15 fields after it (`REPEAT_FIELDS`), then a pass every 5 fields
  (`PASS_FIELDS`)**, as a keyboard's auto-repeat: the Master's own waits
  as long before it repeats. So a tap shorter than that is one pass, and
  a held turn or walk goes on smoothly: each pass's frames shown over its
  5 fields as decision 36 has them; where frames are slower than that, a
  pass a frame, each shown most of the way. A minute's end still brings
  its pass at once.
- **Why these**: a held turn at the start's view went 49.5° a second at
  5 fields a pass, the frames keeping up, and more slowly at 4, where they
  didn't. 25 units at that pace is 250 a second (242 measured where the
  frames keep up), against the original's 250 a redraw (0.66 s at the
  median, `docs/research/zx-driller.md`); where frames are slower, a step
  a frame (about 170 a second from the start's view). 10 would crawl; 50
  would outrun the original where frames are cheap. (`docs/research/live.md`,
  "The pace", has the measurements of 2026-11-01.)

The logic is Driller's pass for pass; only when passes come and the sizes
at the start change. `make logic` holds the transcription to the original
from the original's start; `make logic6502` and `make live` start from the
port's, each scenario first putting the original's sizes back, and
`tests/logic/pace.txt` holds turns and walks at the port's sizes. The four
constants are together in `tools/logic/state.py`, for Matt to change.

## 48. Steering: small sizes to start, and keys that repeat (2026-11-01; amends 4 and 36)

Matt, trying the disc: "it seems impossible to steer. tapping left seems to
always turn 3 steps". Driller's own pace (a pass about once a second) and
starting sizes (a 15° turn, a 250-unit step) made each tap a large move
shown over many frames. So:

- **The game starts with the smallest turn, 5°, and a step of 25 world
  units**, in place of Driller's 15° and 250; f0-f3 still change them
  (decision 10).
- **A key going down gives a pass at once; keys held alone repeat 15
  fields later, then a pass every 5 fields**, as a keyboard's auto-repeat
  does (15 fields is the Master's own repeat delay). A tap is one pass; a
  held turn or walk goes on smoothly.

The logic stays Driller's pass for pass; only when passes come and the
sizes at the start change. The four constants are in
`tools/logic/state.py`, Matt's to change. `make logic` keeps the
original's start; the port's checks start from the port's.

## 49. Two packed files on the disc (2026-11-01; Matt asked)

Matt asked why the disc loaded a dozen and more files ("is there a way to
avoid all the separate files?"), and pointed at baron's compression. Each
disc is now two files: `!BOOT`, which the boot option runs into screen
memory, and one packed file (ZX02, by baron's own compressor,
`src/zx02.6502`) holding a stream for each place (each sideways bank, main
RAM, HAZEL), which `src/loader.6502` reads a track at a time by OSWORD &7F
and unpacks into place (`docs/research/live.md`). `tools/loadcheck.mjs`
holds every place to the parts' own bytes. Two files rather than one
because `*RUN` loads a whole file into main RAM, which can't hold the
packed parts; two passes of the build because a section opened in many
files can't nest, and a compressed section must be under 64K.

## 50. The fill reads HAZEL's quarter squares (2026-11-01, autonomous)

The fill no longer builds its own quarter-square tables; it reads the
maths' tables in HAZEL, which hold the same values for every index it
uses, freeing about 1K of its bank.

## 51. Run-once start-up code in page &0D (2026-11-01, autonomous)

The code that runs once at start-up lives in page &0D (below the
Master's extended vectors at &0D9F), behind an RTI, and the page is free
again once it has run.

## 52. ANDY holds the front end's cold code (2026-11-01, Matt)

The Master's ANDY (4K at &8000-&8FFF, paged by ROMSEL's top bit) holds the
front end's rarely-run code (lines and points, and the routines that run
under a thousandth of its cycles each), reached through trampolines in
main RAM, so the front end's own bank has room for faster code on its hot
paths. Matt chose it over the area conversion's home and over keeping it
in reserve.

## 53. Candidates beyond the view's sides are passed over (2026-11-05, proposed for Matt; amends 16)

A candidate with every vertex where one of 3x + 2z, 2z - 3x or z - 3y
(camera space) is negative can't be seen, so its faces aren't tried
(`render.OBJECT_CULL`; `docs/research/objects.md`, "The eighth round"). No
pixel changes in the entrance views, their walks or against the ZX oracle;
over the check's views a few lose a sliver of a cone face made from an
object wholly beyond the view (journal, 2026-11-05).

## 70. Lines one face takes whole aren't rewritten when the buffer holds them (2026-11-06, autonomous; amends 20)

As decision 20 does for the background's lines, a line one face's piece
covers from end to end isn't written when the buffer being drawn holds it in
the same byte from such a piece last time, by a record for each buffer and
line (`bg_was`'s `LN_WHOLE`, the byte in `ln_v`). The picture doesn't
change; every frame is the model's byte for byte, and the model's
`held_writes` counts the bytes the 6502 writes. Anything else that draws on
the screens still calls `raster_forget`. The record's 256 bytes go in the
fill's bank, and the slideshow's `RasterState` moves to main RAM to make
room in its bank. Lines of more than one run stay written whole (their
records would need room the memory hasn't). Figures: journal, 2026-11-06,
"the fill's fifth round".

## 71. The live disc's fill has no horizon (2026-11-06, autonomous, proposed for Matt; amends 8a)

Decision 8a left the rasteriser's horizon unused for Driller but in the
code: the level and sloping splits, the sloping one's 32-bit arithmetic,
the filling of a gap that a split cuts, and a split for each line. On the
live disc `live_init` writes `rs_horizon` once, to 0, and nothing writes it
after, so none of that has run since. The live build names
`RASTER_NO_HORIZON` and leaves it out, together with the writer's two
routines (`put_run`, `put_bnd`) that only it called: the fill's bank gains
the code and a page of lines' splits, a gap is filled whole without
the split test (nine cycles a gap), and a line of background alone is
compared with the right edge. Every frame is the model's byte for byte (the
live check), and the check builds and the slideshow keep the horizon, so a
game that needs one builds with it (the model and `tools/rastercheck.mjs`
still test it). Figures: `docs/research/raster.md`, "Round 6", and the
journal, 2026-11-06. If a later version of the game draws a horizon, the
flag comes off and the room goes (about 1,200 bytes of the fill's bank).

## 75. The projection takes the Z the engine projects (2026-11-06, autonomous, proposed for Matt; amends 17)

The model's projection (`tools/model/maths.py`) took any Z from 64 (one
world unit) to 2^23. Nothing nearer than the clip's near plane (`ZNEAR` 256,
four world units) is ever projected, and nothing farther than a world's
whole diagonal, `8192 * sqrt(3) * 64` or about 908,000 (Driller's deepest
view is 742,000, `docs/research/maths.md`), under 2^20. So `ZNEAR` is now
256 and `ZLIMIT` 2^20 (X and Y keep their 24 bits, `COORD_LIMIT`), and the
6502 spells out the cases for bit lengths 9 to 20, not 7 to 23: five cases
and their blocks less in `ObjMore`. The model asserts every Z it projects, so
a Z outside the range fails the checks; the 6502's table still has an entry
for every bit length of a 24-bit Z, the first and the last case standing in
for those it no longer spells. No result changes for a Z in range.

## 76. Room bought with cycles on the front end's cold paths (2026-11-06, autonomous, proposed for Matt)

The front end's bank, ANDY and `ObjMore` were the limit on speed. Where code
repeated itself for the sake of cycles that a frame hardly spends, the
repeats were shared, at a call's 12 cycles or a loop's overhead: the
projection's patch of `pmul` (a project), the 2D clip's passes (a pass),
`camera_setup`, `transform_setup`'s tilted rows and `bound_frame`'s ceilings
(a frame), and a level camera's bound patch (a turn's frame, the largest).
Nothing any stage outputs changes. Each is a commit of its own, and the cost
of each is in the journal, 2026-11-06, "the twelfth round"; a change can be
reverted alone if its cycles are worth more than its bytes. (Four were, once
the room was back: the level camera's bound patch, the projection's patch of
`pmul`, the 2D clip's passes and `camera_setup`'s loop; journal, 2026-11-06,
"the thirteenth round".)

## 100. A line's first and last pieces leave out what the buffer holds (2026-11-06, autonomous; amends 70)

Decision 70's records of whole lines become records of each line's ends:
for each buffer and line, the first piece's byte and where its whole bytes
end, the last piece's byte and where they start (`RasterEnds`). A first
piece in the same byte isn't written as far as the buffer holds it from the
line's start, nor a last piece from where it holds it to the line's end; a
line held whole is the case decision 70 took. The picture doesn't change;
every frame is the model's byte for byte, and the model's `held_writes`
counts the bytes the 6502 writes. The records, four bytes a line, are
per-buffer data at the same addresses in main and shadow RAM below
`SCREEN` (the last of main RAM's room there), and replace decision 70's. A view drawn
into a buffer that holds nothing of it (an entrance) pays the records'
tests on every line's ends, 6% of the fill there; walking and turning gain
more (`docs/research/raster.md`, "Round 7", and the journal, 2026-11-06).

## 101. The slanted faces' planes kept by their shape, in shadow RAM (2026-11-06, autonomous)

What a slanted face's plane is (the cross product's components, its axis or
its two axes, n reduced) depends on nothing but its loop's first two edges,
u and w, six bytes. The area conversion keeps it in a memo of 256 entries
found by a hash of those bytes (`src/area.6502`'s `AreaShapes`), the
globals' faces and every area's alike, and a face whose u and w are its
entry's takes the entry's plane; one that isn't takes the entry. This
replaces the globals' memo by place (`pm_*`, in main RAM below `SCREEN`,
which is free again). The memo's eleven pages are in shadow RAM past the
logic's lists, where only the logic reached before: the conversion sets
ACCCON's X round each access, as its working copy is main RAM's. Nothing
any stage outputs changes: an entry is taken only when its six bytes are
the face's. Figures: the journal, 2026-11-06, "the fourteenth round".

## 102. No coarser lines from images, no reduced resolution (2026-11-06, Matt)

Matt ruled out two picture-changing speed options: coarser lines from images
(fewer IMAGE_BITS, priced in the journal's tenth round) and reduced vertical
resolution (half the lines of the view). The view is already at the limit of
what can be seen, so further speed has to come with the same picture. The
other picture-changing options (the floor as the horizon, constant dithers)
stay priced and unadopted unless Matt asks.

## 110. Sounds play while the game goes on; the logic waits only for a full queue (2026-11-06, autonomous, proposed for Matt)

The original stops for every sound: its beeper needs the CPU, so `$9574`
turns interrupts off and loops until the sound ends, and the game, its
clock and its sensors stand still meanwhile (`docs/research/sound.md`). The
BBC's chip plays by itself, so the vertical sync's interrupt plays the
sounds a field at a time and the frame loop goes on. What's kept of the
original's decision: every sound plays whole, in the order asked, one after
another without a gap. A sound asked for waits in `snd_next` while one
plays; asking for another while one is waiting makes the logic wait for
that one to start.

The options, for Matt:

- **As built**: the logic waits only with a sound already waiting. Walking
  into a wall (sound 19, three fields, a pass every five) never waits; a
  held climb (sound 4, six fields a step, a pass every five) would fall a
  field a pass behind, so wait about that; the
  minute's turn in `tests/logic/minutes.txt` (global condition 0's sound
  11, 157 fields, and more behind it) waited 31 and 114 fields in the live
  check (`docs/research/sound.md`, "Measurements").
- A longer queue: the logic never waits until it's full, but sounds lag
  further behind what made them.
- A new sound cuts the playing one short: nothing waits or lags, and long
  sounds (7, 8, 11, 20) are seldom heard whole.
- The original's: the logic waits for every sound to end, the frame loop
  with it.

## 111. Where the sounds live (2026-11-06, autonomous)

The driver's tick and the hook are in main RAM below `&3000` (the
interrupt and both logic banks reach them), its segment's state and the
chip's last bytes in zero page (`&03` up to `ZP_FIXED`), the queue in
`Work`. Its rarely run part, the next segment's read (`snd_segment`), is in
HAZEL after `ObjWork`, which the interrupt always sees: in main RAM it
would have pushed `ObjMore` past a page boundary, whose alignment would
have cost `ObjMore`'s room a whole page. The scripts are in shadow RAM past
the slanted faces' memo (`SoundData`), which `snd_segment` reads setting
ACCCON's X and putting it back; the loader can't unpack into shadow RAM
(it runs from screen memory, which X would switch under it), so it puts
them in main RAM at the same addresses, which `sound_init` copies across at
the start, before `clear_work` clears main RAM there. Bytes: the journal,
2026-11-06, "Driller's sounds".

## 112. The beeper's sounds remade for the SN76489, a field at a time (2026-11-06, autonomous, proposed for Matt)

The original's sounds are timing loops on a one-bit beeper; the SN76489
has three square tones, a noise channel and 16 volumes. The build runs each
of the original's 21 routines on the ZX snapshot and measures each field of
it (`tools/mksound.py`, `docs/research/sound.md`, "From the beeper to the
chip"): its waveform's period (YIN), the strongest of that period's
harmonics as the tone, that harmonic's strength against a square's as the
attenuation; under the tone's 122Hz floor, periodic noise at the pitch; for
sound 13's random loop, white noise as busy as the beeper was. Then
straight-line segments, within a quarter of a semitone and a step of
attenuation. What differs from the original, by the choice:

- **A field is the finest step.** Sweeps faster than that (sound 1's saw,
  the chirps of 5 and 10, the ends of 8's sweeps) become a field's
  dominant tone, or its strongest harmonic.
- **Loudness from the waveform.** The beeper has one level; a narrow pulse
  sounds quieter than a square, so it plays quieter (sound 15's sweeping
  pulse width becomes a swell and fade). A square plays at attenuation 0,
  the loudest.
- **Bass as periodic noise.** Under 122Hz the tone channels can't go;
  periodic noise there is a thin pulse a fifteenth of tone 2's frequency,
  buzzier than the beeper's square (sounds 17 and 19, the ends of 7 and 20).
  An octave up on the tone channel is the other way.
- **One voice.** The original plays one sound at a time, so tone 2 and the
  noise do; tones 0 and 1 are free for anything later.

## 113. The ZX's sounds, not the CPC's or the ST's (2026-11-06, autonomous, proposed for Matt)

The logic is the ZX's (decision 1), so its sound numbers and when it asks
for them are the ZX's, and the ZX's sounds are the ones remade (decision
112). The other versions, for Matt:

- **The Atari ST's** (whose colours and panel the disc has): 25 digitised
  samples. The SN76489 can play samples only through its volume, as a
  four-bit DAC with the CPU writing every sample, which the frame loop
  can't spare.
- **The Amstrad CPC's**: the same numbers, on an AY-3-8912 at 1MHz, with
  volume and pitch envelopes from small tables (ScummVM's `sound/cpc.cpp`,
  from a disassembly of `DRILL.BIN`). An AY tone's period at 1MHz is half
  the SN76489's at 4MHz for the same note, so they would port nearly
  register for register, a closer match than the beeper's measured
  remake. It would take the CPC's disc into the build (`make fetch` has
  it) and a transcription of its table and player; the driver and its
  checks would stay as they are, with the scripts made from the CPC's
  tables instead.

## 120. The rigs' yields don't depend on the clock (2026-11-08, autonomous, proposed for Matt)

The original picks the gas yields of the whole game the first time a rig
finds gas: one of sixteen rotations of its table of eighteen (`$88EB`), by
its interrupt's frames into the second then (`$C16F`, `SecondFrames AND
15`), so a game's yields depend on the fiftieth of a second the first rig
went down. The disc's logic reads `SecondFrames` as the original does, but
nothing on the disc counts it (the disc keeps the minute, not the
seconds), so it holds the snapshot's value and every game has the same
yields: rotation 0, Amethyst's 49,000 cubic feet and so on.

Why: the checks hold the disc's logic to the transcription's byte for byte,
and the transcription's clock is the oracle's, held still (each pass starts
at 59 seconds and frame 0); a clock the disc counted would make the choice
differ from the trace's. The options, for Matt: keep it (one table, as
now); or count `SecondFrames` from the fields (`lv_now` mod 50, a few
cycles a pass) and have `tools/livecheck.mjs` write the trace's value into
the disc before the pass that picks, as it writes the minute.

## 121. A rig's messages show in the panel's message line while the game goes on (2026-11-08, autonomous, proposed for Matt)

The original shows each of a rig's messages (PROCESSING, RIG POSITIONED,
the yield, the percentage, or why not) in its message line, highlighted,
for 50 frames, with the whole game stopped, the clock too: up to 200
frames for a drilling. The disc shows each, in the panel's message line
(the panel's font: the ST's console has no inverse line), for
`RIG_SHOWN` (50) fields in turn from the pass, then the area's message
again; the logic's next pass waits as long (the waits are the logic's
`hook_wait`, as the size keys' are, decision 36), and the frames, the
sounds and the clock's minute go on. The panel's font gained a `%`.

Why: as decision 110 for the sounds, the disc never stops its frames; the
pass the original would have held up still waits, so no key acts sooner.
Against holding everything: the minute would be late by up to four
seconds a rig, as it is in the original.

## 122. A rig's redraw is the area entered again (2026-11-08, autonomous)

When a rig goes down or comes up, the original moves its five global
parts' records ($CD3B) and redraws there and then. The disc's working copy
of an area builds the globals' slots from their records as an area is
entered (decision 34, `src/area.6502`'s `ag_kept`), so a pass whose rig
redrew (it showed PROCESSING: `lv_rigged`) enters the area again
(`lv_enter_area`), which builds the slots of the parts that moved. It
costs an entry's cycles (the journal's figures for `area_enter`) once a
rig, where the original's redraw and its 50 frames' wait are anyway. The
logic's own index of the objects (`index_objects`, which the original
doesn't have: it scans the records) is made again with them.

## 130. The laser's lines at half width, shown for sound 1's fields (2026-11-08, autonomous, proposed for Matt)

The original draws its four lines to the crosshair ($AA50, by its line
$A803), plays sound 1 and draws them again, which takes them off: they
show while the sound plays, the game held. The disc draws the same four by
the same DDA, each end's x halved as the crosshair's is (decision 38), the
DDA run in the BBC's pixels, each pixel EORed with colour 7 as the
crosshair's; in frames of their own (as the crosshair's: the view isn't
drawn again), from the pass for sound 1's fields (`LASER_FIELDS`, the
sound's script's); and the next pass waits as long, as the original holds
the game. Why the DDA in the BBC's pixels: run in the ZX's, two of its
pixels fall in one of the BBC's and EOR each other away. Against: the
lines are a pixel coarser than the original's across, as the whole view
is.

## 131. The shot's pick from the BBC's frame (2026-11-08, autonomous, proposed for Matt)

The original hits the first object of its last redraw's draw list, from
the nearest, with a face round the crosshair ($B153) in its own projection.
The disc's projection is the BBC's (decision 2), within a pixel of the
ZX's but not the same, so the disc picks from its own last frame: its draw
list nearest first, the first face whose polygon holds the crosshair
pixel's centre (decision 38's pixel), its edges counting. The
transcription asks the model's frame of the state the pass began with
(`tools/logic/view.py`), so the original, the transcription and the disc
agree wherever the two projections do: `tests/logic/shoot.txt`'s targets
all do; a target a pixel wide, or the crosshair within a pixel of an edge,
can differ. The frame picked from must be the logic's camera, as the
original's is: a pass that may fire waits while the last pass's frames
show, until the frame of its end is drawn. The options, for Matt: as
built; or a projection of the ZX's own for the pick (the oracle's), which
the disc has no room or cycles for and which would hit what the BBC's view
doesn't show.

## 132. A sensor is on the screen when the BBC's frame draws it (2026-11-08, autonomous)

The original's sensor in range is in state 1 (its line of sight by the
pick at its point) when its projected point is on the screen, else state 2
(by a walk to it). The disc's is on the screen when its last frame drew
its pixel (the front end's draw list), and its point is that pixel, the
pick at it decision 131's; the transcription asks the model's frame. As
for the pick, the two views differ by up to a pixel at the view's edges,
where a sensor can be on one screen and off the other: `make logic`
counts those and checks everything else (`docs/research/sensors.md`).

## 133. The sensors' shots counted by the main loop, without the border (2026-11-08, autonomous, proposed for Matt)

The original's interrupt counts each sensor's frames and fires there, the
game held while sound 2 plays inside it, and flashes the border in the
screen's second colour. The disc's interrupt can't wait for the sound's
queue or draw the lines into the buffer being drawn, so the main loop
counts the fields since its last loop, a field at a time, as the
interrupt's frames (`sn_clock`): a shot comes up to a frame late, and the
shots' rate is the original's. Sound 2 is asked for from the main loop; the
shield's bar is drawn with the panel's values. The BBC's border is blank
(the CRTC's), so there is no flash; a flash of the panel's colours would
take a palette change for two fields, which the frames' flips would have
to follow. The sensors' test after a redraw waits for the frame of the
pass's end (it needs that frame's draw list, decision 132), and the next
pass waits for it, as the original's does: in an area with a sensor, keys
held go a frame slower a pass. Against counting in the interrupt: the
checks hold the clock from the main loop, as they hold the minute.

## 134. A sensor's shot's lines show for sound 2's fields and a frame (2026-11-08, autonomous)

The original draws a shot's four lines at the frame its counter wraps,
plays sound 2 (two fields, the game held) and takes them off at the next
frame's interrupt. The disc shows them from the shot for sound 2's fields
and one more (`SENSOR_LINES`), in frames of their own as the laser's
(decision 130), by the same line, halved the same way; a line's end at y 0,
a line below the view's bottom (where the original's row table puts it),
isn't drawn.

