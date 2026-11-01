# Driller live: its own logic and the whole pipeline on the BBC

*Track L, 2026-10-31, then tracks P and S the same day. `build/live.ssd`
(`src/live.6502`, `tools/mklive.py`) is Driller: its own player logic
(`src/logic/`, `docs/research/logic6502.md`) takes the keys a pass at a
time, as the original does, and every frame is drawn from the camera alone:
the object pipeline (stages 1-7, `objects_frame`), then the rasteriser and
writer (stages 8-10, `raster_frame`), between `frame_begin` and
`frame_end`. Nothing of a view is worked out off the BBC.
`build/live-free.ssd` (`-D FREE_CAMERA=TRUE`) is the same disc with the
free camera instead of the logic, for checking views. `tools/livecheck.mjs`
holds every frame either shows to the model's render of that frame's
camera, byte for byte, and the logic's every pass to the transcription's.
Figures are in the journal and the tracks' reports, and in the dated
measurements at the end.*

## Running it

```sh
make live        # both discs and their checks (one of make check's)
make live-run    # screenshots of LIVE_SHOTS' entrances on the free disc, RGB and PAL, into shots/
node tools/livecheck.mjs --trace build/live/trace.json --verbose     # every frame's camera and cycles
node tools/livecheck.mjs --free --walks 3,30 --json build/live/check-free.json
make live LIVE_SCENARIOS="walls jet turns"                           # other scenarios of tests/logic/
```

On the logic's disc the keys are Driller's (decision 10, `src/input.6502`):
O and K step, Q and W turn, P and L look, N and M roll, R and F rise and
fall, U turns round, A and Z the turn's size, S and X the step's; B shows
and hides the crosshair, SPACE is shooting mode (the movement keys move the
crosshair), 0 fires (nothing is hit yet). The cursor keys are the ZX's
cursor joystick. On the free disc: cursor left and right (or Q and W) turn
5° a frame, cursor up and down (or O and K) walk `LIVE_STEP` world units
along the view a frame, through anything; P and L look up and down, N and
M roll; SPACE goes to the next entrance; with no key for `DEMO_FIELDS`
fields a demo turns on the spot and goes on after a whole turn.

## The frame

`live_loop`, once a frame, on the logic's disc:

1. `lv_now`: the fields counted, the frame's one time.
2. `lv_requested`, if the check has set the logic's state from outside
   (`lv_request`; below).
3. `lv_pass`: the logic's pass, if one is due (below), and the frames that
   show it set up (`lv_setup`).
4. `lv_camera`: the frame's camera into `lv_cam`: the logic's, or a point
   on the way to it while a pass's frames show.
5. `lv_inputs`: has anything the view is made from changed since the frame
   last handed over? If not, nothing is drawn: the figures if a window's
   frames are all shown (`live_idle_measure`), and on to the next loop
   (`live_idle`; below, "The idle loop").
6. The camera into `cam_x` .. `cam_roll`; ACCCON's X cleared (the cache is
   in main RAM's `&3000` on); `objects_frame` with `BANK_OBJ` paged. Its
   output is the rasteriser's input already (below); the glue copies one
   byte, `out_nf` to `rs_nfaces`.
7. `frame_begin`; the crosshair this buffer had taken off (`lv_cross_off`);
   `raster_frame` with `BANK_RASTER` paged; the crosshair drawn
   (`lv_cross_on`).
8. The figures (`live_measure`), the panel as the beam allows
   (`docs/research/panel.md`), `frame_end`.

A frame that's drawn is drawn whole (decision 30), so the figures are
always the pipeline's cost. On the free disc, `live_keys` moves the camera
in steps 1-4's place.

### The idle loop

The original redraws only after a move. The disc draws a frame only when
something its view is made from has changed since the frame last handed
over (shown, or waiting for its flip); otherwise the loop goes round again
at once, taking the keys and the logic's passes, so the next frame starts
as soon as anything changes, rather than when a still frame drawn again
ends.

- **What a view is made from** (`lv_inputs`, its record `vw_rec` in
  `LiveGlue`): the camera (`lv_cam`); the area and how many areas have
  been entered (`lv_entered`: entering builds the area's working copy
  again, and the logic moves the rig's parts as it loads one); with the
  logic, what's hidden of every object it indexes (`ix_flags AND
  IX_HIDDEN`, all `IX_MAX` of them, a superset of what the object pass
  reads through `ob_ix`), and the crosshair (`CrossOn`, and `CrossX` and
  `CrossY` while it's on). Nothing else a frame reads changes but as an
  area is entered (the patterns, the working copy, `raster_forget`). The
  panel round the view is no input: it's drawn into both buffers outside
  the frames.
- **The last frame handed over is enough.** The buffer not shown may hold
  an older view: it's never shown without a frame drawn into it first, as
  only `frame_end` hands a buffer over, and each buffer's own records (the
  rasteriser's backgrounds, `bg_was`; the crosshair it holds, `lv_xon`)
  are kept by buffer. So no frame is drawn to make the buffers alike
  first, which would hold a key up by a frame.
- **Each pass on a reading of the keys made after the last.** A pass that
  shows nothing no longer waits for a frame to be drawn before the next,
  and the keys are read once a field, at the vertical sync
  (`src/input.6502`), so a key held against a wall would make passes as
  fast as the loop goes round, each on a reading already taken. The next
  pass comes after the waits the pass asked for and after the vertical
  sync that follows its end (`lv_until`, from the fields counted as it
  ends), so passes that change nothing come at the keyboard's rate. (The
  original reads its keys and passes again as soon as nothing needs a
  redraw, at whatever rate its pass takes.)
- **The keys taken whole.** A pass takes each half-row's keys as those gone
  down since the last take (`key_take`) and those held (`keys`) with the
  interrupt held off between the two (`lv_pass`, and the free camera's
  `live_keys`): otherwise a key the vertical sync read between them was
  taken as held, left as gone down, and so taken again by the next pass,
  a tap acting twice. (The window is a few cycles; the idle loop's quicker
  passes showed it.)
- **A turn shows from its first field.** The frame at a pass's start (its
  fraction 0) is the camera before it, which the idle loop draws nothing
  for, so the first frame comes a field in. A turn's angles round up
  (`lv_camera`): each 5-degree step from the field its fraction enters it,
  so a 15-degree pass shows its first step then, as a step's frames move
  from their first field; rounding to the nearest held the first 5
  degrees back for a sixth of the pass. The steps keep their spacing.
- **The figures.** A window of frames is measured when `FIGURE_FIELDS` have
  passed, as before, or as soon as the loop goes idle with all its frames
  shown (`live_idle_measure`); a window with no frames starts again from
  each idle loop, so frames a second and fields a frame are over the
  frames drawn, not the fields nothing was drawn in.
- **The panel** needs no waiting for in the idle loop: `panel_sync`, once
  a loop, finds the beam's window.

### Driller's logic on the disc

- **The start**: `!BOOT` loads `LOGICW` (the logic's variables, the
  original's in play: area 1, entrance 19, on the probe, with the port's
  first step and turn: "The pace", below), `LOGIC` (its database and the
  code that reads it) and `LOGICC` (the rest of its code);
  `lv_start` indexes the area (`logic_go_init`), enters it (`area_enter`
  from the logic's records, `OBJ_LOGIC` and `AREA_GLOBALS`), takes the
  screen's colours if an area's change is pending (`logic_go_colours`) and
  the objects' flags (`logic_go_shown`).
- **A pass** is due once the last pass's frames are shown and its waits
  are done (`lv_until`), on a reading of the keys made after the last
  ended (the idle loop, above), and on keys held alone once they repeat
  (`lv_repeat`: "The pace", below). Its keys are the ones held or gone down since the last
  pass (`lv_lkeys`, the logic's `LOGIC_KEYS`): the held bitmap and
  `key_take`'s, so a key tapped between passes still acts once. The pass
  runs with ACCCON's X set, as the logic's lists by face are in shadow
  RAM. It answers 0 when no key is held (the original waits in its input;
  the disc goes round its loop and asks again), 1 when it ran, 2 once the
  game is over, after which no pass comes and the second line says so.
  After a pass that ran, `logic_go_shown` gives the renderer the objects'
  flags (but after an area's change, below).
- **The hooks** (`src/logic/hooks.6502`, the logic's calls to what it
  leaves out): this disc fills in three. `hook_wait` (the size keys', the
  crosshair keys' and the FCL's `DELAY`): the original waits that many
  frames of its interrupt in the logic; here the next pass waits that many
  fields more, and frames go on being drawn. `hook_walked` (each move's
  walk, before the margin's push) and `hook_loaded` (an area's load) are
  the disc's own, for the frames between passes. The rest do nothing yet,
  as the transcription's defaults: the sound, the panel (the disc draws
  its own from the logic's variables after each pass: `panel_values`,
  `docs/research/panel.md`) and its key lights, the crosshair's drawing
  (the frame draws it, below), the screen's colours,
  the FCL's `REDRAW`, the draw list, the sensors, the laser and the shot,
  the rigs, the information screen and the game's end.
- **The clock**: a minute is `MINUTE_FIELDS` fields, as the original's
  interrupt counts 50 to a second; `logic_go_minute` goes in just before
  the pass the minute's end comes before, which takes it.
- **An area's change** (a doorway, an area's edge, any GOTO): the pass's
  walk into it is shown in the old area, its angles as they were, and the
  new area comes the frame after (`lv_switch`, `lv_switched`): the area's
  working copy built from the logic's records (`area_enter`, ACCCON's X
  cleared, as its `cache_reset` clears the sort's memory in main RAM's
  `&3000` on), its patterns, `raster_forget`, its name, the screen's
  colours and the objects' flags. The renderer's copy indexes the old
  area's flags until then (`ix_flags`, which the logic's new index doesn't
  touch).
- **The logic's angles** are bytes, and the database can put any byte in
  one: a GOTO to an id an entrance shares with an earlier object (area 2's
  16 is a cuboid's too) puts the camera at that object, with its size for
  angles, as the original does. The renderer takes each angle mod 72
  (`mod72`), as the model's entrance cameras do.

### The frames between passes (decision 4)

The logic moves a whole step or turn a pass (of the sizes f0-f3 set, from
the port's start: "The pace", below); the frames between show it. A pass's
frames take `PASS_FIELDS` fields from its start; a frame at `e` fields in
shows the fraction `f = 256 e / PASS_FIELDS` (`pace_f`) of the way. A held
key's next pass comes in the frame its time runs out and starts from the
last pass's end, not the frame's, so the motion goes on at one speed; but
no earlier than `PASS_FIELDS - 1` fields before the frame. Where frames are
slower than the pace, the loop takes a pass a frame (one a loop), and each
frame shows its pass most of the way (chaining from the last end alone
lets a pass's first frame be its end, so the next starts afresh from a
field on, and frames show part-steps of uneven sizes); and a pass's first
frame is never its last, so an area's change still comes before the
logic's camera is shown (`lv_pass`'s `lv_switch`).

`lv_setup`'s rule, from the camera before the pass (`an_p0`, `an_a0`) to
the logic's after:

- The angles turn the short way round, each `a0 + sign(t) ((|t| f + 255) >>
  8)`, mod 72: a 15° turn in its three 5° steps, as frames allow, each
  from the field the fraction enters it (the idle loop, above).
- The position goes along the segment the pass's move walked
  (`hook_walked`: where it stopped less where it began, before the margin's
  push), each coordinate `p0 + sign(d) ((|d| f) >> 8)`, when the pass had
  one move and ended within the margin's push (`Margin`, on each axis) of
  the segment's end; the last frame is where the logic put it. So every
  frame between is a point the move checked: the camera ends on the
  straight segment toward the target, a unit short of the first face, and
  the margin then moves the end up to `Margin` off it
  (`docs/research/zx-logic.md`). On the probe's step y holds until the
  end: a climb or a fall comes at the crossing that ends the step. In the
  jet, and for the probe's rise, y goes along with the rest.
- Any other pass that moves (more than one move, a rise that didn't get
  there and fell back, the probe's fall, which isn't a move) goes straight
  from where it was to where it is.
- A pass that loaded an area shows its walk, if it had just one, in the old
  area, its angles held; with none, the new area comes at once.
- A pass that changed nothing shows nothing, and the next can come on the
  next reading of the keys.

### The pace

Decision 48 (amending 4 and 36, after Matt found the disc "impossible to
steer"). Four constants, together in `tools/logic/state.py` for Matt to
change there: the build takes them into `build/logic6502/data.6502`, so
into the logic's start and `src/live.6502`, and into the checks' traces.

- `START_STEP_INDEX`, `START_TURN_INDEX`: the step's and the turn's sizes
  the game starts with, as indices into the original's `StepTable` and
  `TurnTable`, in place of the database's (its header's `$C2` and `$C3`,
  which a new game takes, `$9C36`): a step of 25 world units and the
  smallest turn, 5°, where Driller starts at 250 and 15°. `port_start`
  puts them in the database and sets the variables a new game sets from
  them (`StepIndex`, `Step`, `StepUnits`, `TurnIndex`, `Turn`). f0-f3 change
  them in play (decision 10).
- `PASS_FIELDS`: a pass's frames take that many fields, and keys held
  pass that often once they repeat.
- `REPEAT_FIELDS`: a key going down (`keys_made`, read, not taken) brings
  a pass as soon as one is due; the keys held alone repeat only once that
  many fields have passed since the last pass that took a key gone down
  (`lv_repeat`, from `lv_made`), as a keyboard's auto-repeat, so a tap
  shorter than that is one pass. A minute's end brings its pass whatever
  is held, as the original's input takes a minute without a key.

The logic is Driller's pass for pass: only when passes come, and the sizes
at the start, are the port's. `make logic` holds the transcription to the
original from the original's start. `make logic6502` and `make live` start
from the port's (`tools/logictrace.py`, `tools/mklive.py --trace`), the 6502's
start held to it, and each scenario's run first pokes the original's sizes
back (`original_sizes`), so that it runs as `make logic` runs it: the
scenarios were written for those sizes, and the fuzz found its walks with
them. `tests/logic/pace.txt` brings the sizes down itself and holds turns
and walks; the live disc's own run of the keys and its tour run from the
port's start. `tools/livecheck.mjs` holds each tap's keys down until nearly
`REPEAT_FIELDS` after they went down, and fails on a second pass of them,
or on keys held alone repeating sooner after a key went down; it reports
the held keys' passes, and their speed in `pace.txt`'s run.

#### Measured (2026-11-01, track AA)

On jsbeeb (`tools/play.mjs`), the logic's disc from the start (area 1,
entrance 19, yaw 34):

- Driller's own start and pace, before: Z held for 2 s turned 15° every
  0.9 s or so, as Matt found.
- A tap of Z for 0.1 s and for 0.28 s each turned 5°; held for 0.5 s, 15°
  (the pass at once, the repeat, one more); a tap of the cursor up stepped
  25 units.
- Z held: 19 passes in 96 fields (49.5° a second, the frames keeping up).
  With `PASS_FIELDS` 4, 17 in 104 (back-to-back frames wait on the
  panel), so 5.
- The cursor up held: from the start's view, 13 passes in 95 fields (a
  frame of 7.3 fields, a pass each: about 170 units a second, frame-bound);
  facing yaw 4, 495 units in 102 fields (242 a second, the frames keeping
  up).
- The Master's own keyboard (MOS 3.20 on jsbeeb, after its CMOS):
  `&0254`, `&0255` (OSBYTE `&C4`, `&C5`) are 30 and 5: a 30 cs delay before
  it repeats, 15 fields, so `REPEAT_FIELDS`.

`make live`, every scenario (`LIVE_SCENARIOS`, `pace` with them): 715 taps
held 13 fields, each one pass; the keys held alone repeated 15 / 15 / 24
fields after their pass (median / p90 / max, 144 times), then passed every
6 / 7 / 27 fields (1,123); in `pace.txt`'s run, held turns went 44.9° a
second and held walks 232.9 units a second. Fields a frame on the logic's
disc (median / p90 / max): walking 2.82 / 5.89 / 14, turning 4 / 7.45 /
14.94, over 1,273 and 1,312 frames; a key pressed with nothing left to draw
had its pass after 0.57 / 0.97 / 1.09 fields, and its first changed view
shown after 5.9 / 9.69 / 28.05 walking (261 keys) and 6.19 / 10.24 / 13.36
turning (151).

### The crosshair

The original's (`$AAA0`) at half the width, as the view is: its centre the
view's pixel `((CrossX - 1) DIV 2, VIEW_H - CrossY)`, an arm a pixel across
at two each side, and two lines up and two down at two and three; each
pixel inside the view EORed with colour 7, its opposite, as the original
EORs its own. The frame draws it into the buffer it drew, after the
rasteriser, and takes it off that buffer again before the rasteriser next
draws there, so the buffer holds what the rasteriser drew, which its
background memory relies on (decision 20). `CrossOn`, `CrossX` and
`CrossY` are the logic's (B, SPACE and the movement keys in shooting mode
move them), so the logic's own `hook_crosshair` does nothing.
`tools/mklive.py`'s `crosshair` is the model of it.

### The glue

- **The output is the input.** `ObjOut` (`out_fn`, `out_fv`, `out_fc`,
  `out_vxl` ..) is laid over `RasterIn` array for array: `RasterIn` starts
  where its vertex arrays fall page-aligned straight after its face arrays,
  as `ObjOut`'s do, and `ObjOut` starts two bytes before `rs_fn`, so its
  two counts land on the horizon's bytes (unread with no horizon, decision
  8a) and `rs_overflow` (which `raster_frame` sets after `out_vn` is done
  with). `live.6502` ASSERTs each pair of arrays the same, so a change on
  either side fails the build rather than the picture.
- **Patterns by colour index** (decision 8b): `rs_pat`'s pattern 0 is the
  area's sky and patterns 1-15 its colour indices', so `out_fc` is `rs_fc`.
  `lv_enter_area` copies an area's `LIVE_PATTERNS` (`ld_pats`, from
  `tools/model/colours.py`'s table for the build's display) in on entry and
  calls `raster_forget`. The sky is the background; there's no horizon.
  The logic names an area by its id: `ld_area_of` gives its index.
- **Paging**: `PAGE_IN bank` sets `romsel` and `ROMSEL_COPY` together. Code
  in main RAM pages; nothing in a bank pages another. The logic's entries
  page their own banks (`LOGIC_PAGE`, with `logic_paged`) and leave one of
  them in; the glue pages back what it needs.

### The panel and the figures

The screen is Driller's 192 lines (`docs/engine.md`, section 1): round the
view, drawn into both buffers, is Driller's panel (`src/panel.6502`,
`docs/research/panel.md`), the ST's console with the logic's instruments,
the area's name and its message (the entrance, with the free camera), the
credit and the frames a second: from the flips and fields counted
(`frames`, `fields`), over the frames since the figure was last drawn,
every `FIGURE_FIELDS` fields.

The window is measured early when the loop goes idle with its frames all
shown (the idle loop, above). The halves (no longer on the screen) are
timed on the BBC by User VIA T2, which runs free down at
1MHz and wraps every 65,536 microseconds, beside the fields counted
(`clock`, `clock_to`). A span that saw n vertical syncs is longer than n − 1
fields and shorter than n + 1, a window of two fields, narrower than T2's
wrap (`ASSERT 2 * FIELD_US < 65536`), so its length is the one value in
that window with T2's difference modulo 65,536. A sync flagged and not yet
counted when the clock is read counts. The check holds the BBC's own figure
for every frame to the emulator's count of the same span, within
`CLOCK_SLACK` cycles.

## Memory

Each region's bounds are ASSERTed at the end of `src/live.6502`, and the
logic's places are the includer's (`LOGIC_WORK_ORG`, `LOGIC_KEYS`,
`LOGIC_SQUARES`, the section `LogicFaces`, the `LOGIC_HOOK_*`s, which
`src/logic/` takes, the check build keeping its own). `build/live.json`
has the addresses. Both discs have the same map; the free one leaves the
logic's code and variables unused.

| Where | What |
|---|---|
| bank `BANK_DB` | the logic's `LOGIC_BANK` (`Logic`, file `LOGIC`): Driller's database at its top, which the logic walks and `area_enter` builds each area's working copy from, and the logic's code that reads it (the areas, the FCL, the index); in the gap between, `LiveGlue` (`LGLUE`, loaded after `LOGIC`): the figures and the clock's arithmetic, the frames between passes and the crosshair, or the free camera's code and tables |
| bank `BANK_DATA` | the logic's `LOGIC_CODE_BANK` (`LogicCode`, `LOGICC`: the pass, the moves, the walk, the object test, the arithmetic and the original's tables), then `LiveData` (`LDATA`: the areas' patterns and index by id, the lines' code), the panel's code and tables (`PanelData`, `PDATA`), and the working copy's conversion (`AreaConv`, `ACONV`) |
| bank `BANK_RASTER` | the rasteriser: row runs, code and work (decision 20) |
| bank `BANK_OBJ` | the object pipeline's code (`ObjCode`), from `OBJ_CODE_ORG` (`src/defs.6502`; below) |
| HAZEL | the maths' tables (`HAZEL`) and the transform's f64 table (`ObjTables`, `OTABLE`, on a page boundary), loaded from `HAZEL_LOAD` (the screen) on by `!BOOT` and copied up once the OS is gone (ACCCON's Y then stays set); then `ObjWork` (the camera with it). The logic's multiplies read the maths' quarter squares here (`LOGIC_SQUARES`: the same table, ASSERTed) |
| `&0E00` on | `RasterState` (the rasteriser's state, from a page, so its `ALIGN` costs nothing), `LIVE` (the loop, the screen, the interrupt, the keys, `panel_set`, the logic's entries and hooks, the glue that pages), `AreaCode` (`LAREA`: `area_init`, `area_enter` and the database's reader), `LogicWork` (`LOGICW`, the logic's variables), then `ObjMore` (`OMORE`) to `&3000`: the maths' code (`src/maths.6502`, `src/project.6502`, which patch themselves), from a page as in its own check, then the 2D clip's |
| `&0400` on | `Work` (`src/zp.6502`, this disc's variables with it) |
| `RASTER_IN_ORG` to `RASTER_IN_END` | `RasterIn`, with `ObjOut` over it, in the OS's pages, which nothing uses once the engine owns the machine |
| main RAM's `&3000` up to `SCREEN` | the front end's data: the transform's cache (`ObjCache`), the sort's memory (`ObjMemo`), the pipeline's tables (`ObjConst`, `OCONST`) and the area's working copy (`ObjArea`), which only `objects_frame` and `area_enter` touch, with ACCCON's X clear: `live_loop` clears it before `objects_frame`, `lv_enter_area` before `area_enter` (decision 31); until `clear_work` at the start, the panel's packed picture (`PanelPack`, `PANEL`) in the cache's place |
| shadow RAM's `&3000` up to `SCREEN` | the logic's lists by face (`LogicFaces`), which only its passes touch: `lv_pass` sets ACCCON's X round `logic_go_pass` |
| `SCREEN` up to `&8000` | the screen, main RAM's and shadow RAM's: Driller's 192 lines (`docs/engine.md`, section 1) |

The screen at 192 lines leaves main and shadow RAM's `&3000` up to `SCREEN`
to the engine, against `&3000-&3FFF` before. Main RAM's is reached with X
clear, so it holds what only the front end reads (it runs with X clear);
code stays out of it, as the rest of the map keeps code and what the frame
reads whatever X below `&3000`, in HAZEL or in a bank. So the working copy
and the pipeline's tables went up there, and the maths' code (which patches
itself, so needs RAM) came out of the front end's bank into the main RAM
they left.

### Room

Each owner's room is the rest of its section's span, up to the guard its
`ASSERT`s hold; `build/live.json` has the addresses, and the measurements
below the bytes (2026-11-01).

- **The front end**: its bank from `obj_code_end` to `&C000`; `ObjMore`
  from `obj_more_end` to `&3000` (code or tables, read whatever bank and
  X); main RAM from `obj_area_end` to `SCREEN` (tables or work it reads
  with X clear only); HAZEL from `obj_work_end` to `&E000`. The bytes
  before `OBJ_CODE_ORG` in its bank are the price of where its hot loops
  fall (below); aligning those loops would take them back.
  `mk/objects.mk`'s check build keeps room for the bank full
  (`CHECK_CODE_GUARD`, ASSERTed against `OBJ_CODE_ORG`), and for
  `ObjMore`'s room without the maths.
- **The fill**: its bank from `raster_work_end` to `&C000`. Its own
  quarter squares (`rq_lo`, `rq_hi`, built by `raster_init`) are the
  maths' `sq_lo` and `sq_hi` in HAZEL for every index it uses, as the
  logic's are (`LOGIC_SQUARES`): reading those would free their pages in
  the bank, a change to `src/raster.6502` (a `RASTER_SQUARES` as
  `LOGIC_SQUARES`; the slideshow, which has no maths, keeps its own).
- **Both, at the same address**: main RAM's room past `obj_area_end` and
  shadow RAM's at the same addresses, if the front end leaves it, is
  per-buffer room (ACCCON's X picks the buffer drawn), for the fill's
  later skipping of runs the buffer already holds (`docs/engine.md`,
  stage 10).
- **The logic's**: shadow RAM from `logic_faces_end` to `SCREEN` (with X
  set, as its passes run); `BANK_DB` from `live_glue_end` to `LOGIC_DB`;
  `BANK_DATA` from `area_conv_end` to `&C000`.
- **Not used yet**, measured on jsbeeb with the OS gone (below):
  - ANDY, `&8000-&8FFF` with ROMSEL's bit 7: the Master's private RAM, the
    MOS's own (it pages it only in set-up, through the font's OSWORD 10),
    so free once the engine owns the machine. It stands in for the first
    4K of whichever bank is paged, so it adds room only where that bank's
    first 4K isn't needed while it's paged in.
  - the OS's pages: from `work_end` to `RASTER_IN_ORG`; page `&0D` below
    `&0D9F` (the NMI's, free with no disc access; a soft BREAK reads the
    Master's extended vectors from `&0D9F` on, and pages 2 and 3, so those
    stay the MOS's); page 1 below the stack's deepest; zero page above
    baron's pool's highest allocation up to `&FB` (`&FC` is the MOS's IRQ
    entry's, `&F4` `ROMSEL_COPY`).

## The check

`tools/livecheck.mjs` boots the disc on jsbeeb's full video, headless.

On the logic's disc it runs the trace `tools/mklive.py --trace` makes
(`build/live/trace.json`): the scenarios of `tests/logic/` that
`LIVE_SCENARIOS` names (all but `keys.txt`, whose E the disc doesn't read:
walls, climbs, falls, doorways into other areas, the area's edges, rising
and falling, the FCL's limits, the jet, the clock's minutes, the steps' and
turns' sizes, the corner, the crosshair, the fuzz's finds), a run of the
keys they don't press (the crosshair hidden, shown and moved, the turn's
and step's sizes, turning round), and a tour of every entrance by the
FCL's GOTO, each as
`tools/logic/` takes it with decision 18's fix on, and each from the game's
start (`LogicWork` and the database written back as the disc booted with
them). A pass's keys go down on the BBC's keyboard once the disc has
settled (nothing left to draw: a loop has drawn nothing since the last
frame was handed over and the last pass's frames ended, the request is
taken, and no wait is left), at a point in the field from a fixed
pseudo-random sequence, as a player's keys go down at any point; they're
held until the disc's pass takes them, and in that instant held on if the
next step is a pass with the same keys, in any order (any pokes between put
in at once, before the disc can take another pass, so the logic sees the
keys held throughout as the transcription does), or let go. A pass that
leaves the logic's input a minute to take (the global conditions put
`MinuteCount` back under it at minute 9) has the next pass come at once,
whatever is held, as the original's input waits for a key only with no
minute to take: in that instant the next pass's keys go down instead, and
where the next step isn't a pass of keys the trace puts in a pass of none
before it (`soon`; `tests/logic/minutes.txt`). A poke or an FCL script's
result is written into the logic's state at `live_loop`'s top and the disc
asked to take it (`lv_request`); a minute's end comes by setting
`lv_minute`, which is kept away otherwise, with its pass's keys put in as
gone down at the same loop. It fails unless:

- the disc's state at boot is the game's start; after every pass every
  variable of the original's (`tools/logic/state.py`) and the whole
  database are the transcription's, the pass answers as the
  transcription's, and the disc's hooks saw the transcription's moves'
  walks and area loads; at each run's end the state is the transcription's
  as the original's is while it waits in its input;
- every frame's camera is the logic's or, while a pass's frames show, the
  point `lv_setup`'s rule gives at the frame's fraction, from the
  transcription's camera before the pass to its camera after, along the
  transcription's walk, in the old area while an area's change waits;
- every frame's objects' flags are the records' as the logic has them (the
  old area's while its frames show), and its view is the model's render of
  its camera, with those flags and the crosshair, byte for byte;
- a key pressed when the disc has settled is taken by a pass (`lv_pass`'s
  `key_take`) within `KEY_FIELDS` fields of its going down: the next
  vertical sync reads it, and the next loop's pass takes it, after the loop
  going round then (which may be drawing the panel or working out the
  figures);
- with the camera still at the end, every indexed object hidden in
  `ix_flags` (written between loops, as `logic_go_shown` writes them), and
  then shown again as they were, must each bring a frame, the model's
  render with those flags: the FCL's own VIS and INVIS reach the disc by a
  request, which enters the area again and so draws a frame whatever the
  flags.

On the free disc: SPACE round every entrance (each until the disc settles),
then at each of `--walks`' entrances the keys held a few frames
each (the cursors and Q W O K, P L N M, turning and walking together), then
no key until the demo starts; every frame shown must be the model's render
of its camera, each SPACE go to the next entrance, each hold move the
camera as its keys ask (and only so), and the demo turn a step a frame.

On both:

- every flip shows the one frame handed over, after the last was shown
  whole; both buffers hold the same outside the view at every flip, and
  that is the panel's model's render of the cells drawn
  (`docs/research/panel.md`, "The check", which has the panel's other
  checks);
- every frame handed over shows its area's name and message;
- every write to the view is inside a frame, into the buffer not shown,
  and every write outside it to the buffer shown comes with the beam above
  its row;
- the BBC's own timing of each half is the emulator's (above);
- every loop that draws nothing (`live_idle`) finds the inputs of the frame
  last handed over (its camera, area and entries, every index's hidden
  flags, its crosshair), so the view shown, or about to be, is the model's
  render of what the loop has; and no frame is drawn with the inputs of
  the frame before it.

For each key pressed when settled it reports when its pass took it and
when the first view it changed was shown (the view's bytes at each flip
against the last shown, from frames begun after the key and before a
second pass), by what changed: walking, turning, or anything else (the
crosshair, the objects shown); and each idle loop's cycles.

It reports fields a frame, median, p90 and most: flip to flip (what the BBC
shows), the loop (`frame_end` to `frame_end`, or after loops that drew
nothing from the frame's own loop's start), each half (from the call to
`live_front_done` and `live_fill_done`) and the rest (the logic, the
animation, the panel, the crosshair, and the wait for the last frame's
flip); over every frame and by what the frame did: an area's first frame,
standing (the camera as the last frame's), walking (moved: the transform's
cache kept), turning (the angles changed: the cache refilled), and the free
disc's demo.

## What it needs from the other tracks

- **The front end (M)** and **the rasteriser (G)**: keep `objects_frame`,
  `raster_frame`, `raster_forget` and `area_enter`; keep `ObjOut` and
  `RasterIn` laid out alike (or agree one set of arrays for both); and fit
  their banks (`BANK_OBJ`, `BANK_RASTER`) and `ObjMore`, which the ASSERTs
  watch. `AreaCode` must stay out of sideways RAM, and whatever touches
  `ObjCache`, `ObjMemo`, `ObjConst` or `ObjArea` needs ACCCON's X clear.
  The front end's hot loops fall where `OBJ_CODE_ORG` puts them; aligning
  them (an `ASSERT` that their branches stay on a page) would free the
  bytes before it. The fill could read the maths' quarter squares rather
  than keep its own ("Room").
- **The player logic (J)**: the hooks this disc fills in, and the names it
  sets (`LOGIC_*`), are the logic's interface now; `tools/logiccheck.6502`
  keeps the defaults.
- **The maths (F)**: the projection's shared-coordinate entries are reached
  by a stub (`live_shared`) until a stage calls them; the logic reads the
  maths' quarter squares. The maths' code is in `ObjMore`, from a page, as
  in `tools/mathscheck.6502`.

## What's left

- The hooks still empty: the sound, the panel's key lights (and what else
  `docs/research/panel.md` leaves), the laser and the shot's pick (`$B153`, from the renderer's faces), the draw
  list (`hook_undraw`), the sensors' tests and shots, the rigs, the
  information screen, the game's end and a new game (the database and
  `LOGICW` would have to be kept to start again).
- Shooting mode moves the crosshair a pass a frame, each a whole frame
  drawn; it could be moved without a redraw, by taking it off and drawing
  it again in a buffer that holds the frame's view, which would mean
  drawing the frame into both buffers first.
- A key that goes down while a frame is being drawn still waits for its
  end: a frame is a few fields, and the pass comes after it.
- The first frame of a pass from rest comes a field after the pass (its
  fraction 0 is the camera before it, which the idle loop skips). Timing a
  pass from rest from the field before would show the first part-step at
  once.

## Decisions to record

(The idle loop and the tap that acts once, proposed here before, are
decision 42.)

- **The screen is Driller's 192 lines** (proposed 2026-11-01, amends
  decisions 2 and 9): the CRTC shows 24 character rows, not MODE 2's 32,
  from `SCREEN` to the top of RAM in each buffer, centred where MOS 3.20
  puts MODE 2 at `*TV 0,1`; the view stays a row down, and the text takes
  the ten rows below it, the live disc's figures two to a line. Why: the
  ZX's own screen is 192 lines, the view and the panel; the rows below the
  view are the panel's room; and 4K of main RAM and 4K of shadow RAM come
  free. No view's pixels change, and the flip's lines are the view's as
  before. Measured below.
- **The live disc's memory, with the 192-line screen** (proposed
  2026-11-01, amends decisions 31, 34 and 40): main RAM's `&3000` up to
  `SCREEN` holds the front end's data (the transform's cache, the sort's
  memory, the pipeline's tables and the area's working copy), reached with
  ACCCON's X clear as decision 31's cache is; the maths' code moves out of
  the front end's bank into `ObjMore`, from a page; the rasteriser's state
  out of its bank into main RAM at `&0E00`; and the front end's code starts
  `OBJ_CODE_ORG` into its bank, the page offset measured fastest. Shadow
  RAM's `&3000` up to `SCREEN` stays the logic's. Measured below.

## Measurements

### The idle loop (2026-10-31, track S)

`make live` (`tools/livecheck.mjs`), on the discs before the idle loop
(the same check, which also times their keys) and after it, with the trace
of 316 passes it had before the keys' run moved the crosshair up and down
(the fill's round 4 not in yet). A key pressed
with nothing left to draw: the fields from its going down to the pass that
takes it, and to the flip that first shows a view it changed (median /
p90 / max, and how many keys):

| | its pass | walking | turning | anything else |
|---|---|---|---|---|
| logic's disc, before | 3.31 / 7.44 / 13.15 | 16.96 / 25.4 / 40.28 (31) | 15.44 / 27.35 / 27.35 (9) | 14.62 / 15.56 / 15.56 (3) |
| logic's disc, after | 0.69 / 1 / 1.27 | 8.88 / 15.37 / 29.93 (30) | 7.65 / 11.46 / 13.24 (10) | 7.85 / 8.55 / 8.55 (3) |
| free disc, before | - | 21.72 / 30.66 / 31.91 (25) | 25.79 / 33.36 / 34.93 (35) | - |
| free disc, after | - | 12.41 / 16.11 / 16.91 (25) | 15.29 / 19.07 / 19.47 (35) | - |

(Of the logic's 77 keys, 34 changed nothing shown: a step's size, or a
walk into a wall. The logic disc's walking figures are the scenarios', at
walls, where the first frames' movement is often less than a pixel.)

Fields a frame on the logic's disc (median / p90 / max), before and after:
standing 1.86 / 6 / 17.02 over 1,818 frames, after none drawn (9 frames
whose camera stood but whose crosshair or objects changed); walking
3.09 / 6.3 / 16.02, after 3.12 / 6.38 / 16.02; turning 4.89 / 12.34 / 16,
after 4.98 / 12.54 / 16.08. The check's runs drew 4,024 frames before and
2,258 after. A loop that draws nothing took 3,558 / 4,235 / 78,511 cycles
(the most with a pass that ran and changed nothing shown) over 26,926
loops, every one with the last frame's inputs.

Mutation testing (the check on copies of `src/live.6502` with one change
each): the comparison skipped, or always made; the crosshair, its y, the
flags, the areas entered or a camera byte left out of it; a pass on a
reading of the keys taken during the last; turns rounded to the nearest;
and on the free disc the comparison skipped or its yaw left out. Each is
caught.

### With the fill's round 4 (2026-10-31, track S)

`make live` with the stretch (`docs/research/raster.md`, round 4) and the
trace of 319 passes: stages 8-10 on the logic's disc (fields, median /
p90 / max) walking 1.36 / 2.14 / 8.39 and turning 1.62 / 3.39 / 4.94, from
1.44 / 2.23 / 8.38 and 1.65 / 3.45 / 4.95 without it; the whole frame, flip
to flip, walking 3 / 6.31 / 16.04 and turning 5 / 12.49 / 16.07. On the
free disc, at the entrances, stages 8-10 walking 5.03 / 8.53 / 8.94 and
turning 5.38 / 8.53 / 9.35, from 5.14 / 8.52 / 8.92 and 5.41 / 8.52 / 9.34.
A key pressed with nothing left to draw had its pass after 0.68 / 0.95 /
1.23 fields, and its first changed view shown after 8.41 / 15.22 / 28.18
walking (30 keys) and 7.61 / 11.12 / 13.24 turning (10).

### The 192-line screen and the room it frees (2026-11-01, track T)

**The screen.** `make frames`: the CRTC's R0-R13 127 64 90 40 38 0 24 31 0
7 32 19 10 0 against MOS 3.20's MODE 2 at `*TV 0,1`, 127 80 98 40 38 0 32
35 0 7 103 8 6 0; on jsbeeb's picture the screen is (264,128)-(776,512),
MODE 2's (200,64)-(840,576), the same centre; the view's border
(312,144)-(728,352). The vertical sync's flag now comes on line 250 of 312
(282 before), and `T1_SYNC` follows: the interrupt's flips came on line 114
(the view's lines 8-111), `frame_end`'s own on lines 239-243 for the test
scene and 1-309 with its cost varied; the VSync build's on line 251. The
text's window starts a page of T1 later (`TEXT_T1_MIN` 5, from 4), for the
row straight below the view; with no lead it was still whole in practice,
and a window ending within a page of `FLIP_LINE` fails `make slides`.

**The free bytes**, on the logic's disc (the tighter of the two), before
(the idle loop's disc) and after:

| | before | after |
|---|---|---|
| the front end's bank, `obj_code_end` to `&C000` | 134 | 2,558 (and 128 before `OBJ_CODE_ORG`) |
| `ObjMore`, to `&3000` | 45 | 198 |
| main RAM's `&3000` room, to `SCREEN` | 256 | 1,336 |
| HAZEL, `obj_work_end` to `&E000` | 179 | 179 |
| the fill's bank, `raster_work_end` (before, `raster_state_end`) to `&C000` | 225 | 760 |
| `BANK_DATA`, `area_conv_end` to `&C000` | 800 | 848 |
| `BANK_DB`, `live_glue_end` to `LOGIC_DB` | 734 | 734 |
| shadow RAM's `&3000` room, `logic_faces_end` to `SCREEN` | 2,272 | 6,368 |
| the OS's pages, `work_end` to `RASTER_IN_ORG` | 37 | 133 |

The maths' code is 2,552 bytes with `live_shared`. The text's ten lines,
against thirteen, give `LiveData` and `Work` the rest.

**Where the front end's code starts.** With the maths gone from the start
of its bank, the rest of the front end's code moved down the bank, and its
cycles moved with it. The free disc's check, frames matched by area and
camera against the disc before, the median change in stages 1-7's cycles
a frame by `OBJ_CODE_ORG`'s page offset (the maths' code on a page in
`ObjMore`):

| offset | &00 | &20 | &40 | &60 | &80 | &A0 | &C0 | &E0 | &F0 | &F8 |
|---|---|---|---|---|---|---|---|---|---|---|
| median change | +169 | +87 | +230 | +17 | −280 | −113 | −182 | +6 | +34 | −16 |

(&F8 puts the code where it was. The maths' code not on a page added
about 170 more at &00; the screen's change alone, −35.) With `&8080`, the
disc's own check: stages 1-7 −0.11% over the free disc's frames (median
−254 cycles a frame) and −0.25% over the logic disc's; stages 8-10 within
±0.02%. Every frame is the model's, byte for byte, on both discs.

**The room not yet used**, on jsbeeb, the logic's disc from `live_loop` on
through walks, turns, looks, rolls, rises, turning round, the crosshair
and shooting mode (64 seconds emulated), every write watched: nothing
written in main RAM past `obj_area_end`, shadow RAM past
`logic_faces_end`, HAZEL past `obj_work_end`, either bank past its code or
work, or pages 2 and 3; the deepest stack `S = &E4`, so 229 bytes of page
1 never reached; zero page written up to `&71`, baron's highest allocation
(so `&72-&F3` and `&F5-&FB`, 137 bytes, are free); page `&0D` never
written. ANDY: paged only by the MOS, in set-up (once a character of
`text_init`'s OSWORD 10s), never written by the disc, and left holding
3,633 non-zero bytes of the MOS's own: 4K for the engine once the OS is
gone.
