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
