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

## 10. The keys (2026-10-31, autonomous; corrected the same day)

Driller's own, from the ZX's key table (`docs/research/zx-logic.md`):
O and K forward and back, Q and W turn, P and L look up and down, N and M
roll, R and F rise and fall, U turns round, A and Z the angle, S and X
the step; 0 fires (5 is the ZX cursor-left, so it turns), D drills, C
collects, SPACE changes mode, B shows or hides the crosshair, I shows
information (where 1 is its key), ESCAPE for the ZX's 1 in play. T and Y
do nothing in play. COPY fires too, and the cursor keys are read as the
ZX's cursor joystick. Driller has no key to centre the view, so there
isn't one. The keys are read once a field (`src/input.6502`).

The first version of this decision followed ScummVM's key map, which
differs; the ZX's table is the specification (decision 1).

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
