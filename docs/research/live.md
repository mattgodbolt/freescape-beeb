# Driller live: its own logic and the whole pipeline on the BBC

*Track L, 2026-10-31, then track P the same day. `build/live.ssd`
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
Figures are in the journal and the tracks' reports, not here.*

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
5. The camera into `cam_x` .. `cam_roll`; ACCCON's X cleared (the cache is
   in main RAM's `&3000` on); `objects_frame` with `BANK_OBJ` paged. Its
   output is the rasteriser's input already (below); the glue copies one
   byte, `out_nf` to `rs_nfaces`.
6. `frame_begin`; the crosshair this buffer had taken off (`lv_cross_off`);
   `raster_frame` with `BANK_RASTER` paged; the crosshair drawn
   (`lv_cross_on`).
7. The figures (`live_measure`), the text as the beam allows, `frame_end`.

Every frame is drawn whole, the camera still or not (decision 30), so the
figures are always the pipeline's cost; a key pressed while a still frame
is drawn waits for its end. On the free disc, `live_keys` moves the camera
in steps 1-4's place.

### Driller's logic on the disc

- **The start**: `!BOOT` loads `LOGICW` (the logic's variables, the
  original's in play: area 1, entrance 19, on the probe), `LOGIC` (its
  database and the code that reads it) and `LOGICC` (the rest of its code);
  `lv_start` indexes the area (`logic_go_init`), enters it (`area_enter`
  from the logic's records, `OBJ_LOGIC` and `AREA_GLOBALS`), takes the
  screen's colours if an area's change is pending (`logic_go_colours`) and
  the objects' flags (`logic_go_shown`).
- **A pass** is due once the last pass's frames are shown and its waits
  are done (`lv_until`). Its keys are the ones held or gone down since the
  last pass (`lv_lkeys`, the logic's `LOGIC_KEYS`): the held bitmap and
  `key_take`'s, so a key tapped between passes still acts once. The pass
  runs with ACCCON's X set, as the logic's lists by face are in shadow
  RAM. It answers 0 when no key is held (the original waits in its input;
  the disc draws another frame and asks again), 1 when it ran, 2 once the
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
  as the transcription's defaults: the sound, the panel and its key lights,
  the crosshair's drawing (the frame draws it, below), the screen's colours,
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

The logic moves a whole step (Driller's default, 250 world units) or turn
(15°) a pass; the frames between show it. A pass's frames take
`PASS_FIELDS` fields from its start, so a held key makes `50 / PASS_FIELDS`
passes a second, whatever each frame costs; a frame at `e` fields in shows
the fraction `f = 256 e / PASS_FIELDS` (`pace_f`) of the way. A held key's
next pass comes in the frame its time runs out and starts from the last
pass's end, not the frame's, so the motion goes on at one speed.

`lv_setup`'s rule, from the camera before the pass (`an_p0`, `an_a0`) to
the logic's after:

- The angles turn the short way round, each `a0 + sign(t) ((|t| f + 128) >>
  8)`, mod 72: a 15° turn in its three 5° steps, as frames allow.
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
- A pass that changed nothing shows nothing, and the next can come the
  next frame.

### The pace

`PASS_FIELDS` (`src/live.6502`) sets it. It's chosen so that at the free
disc's median turning frame a held turn shows each of its 5° steps (three
frames a 15° pass), and it comes to about the original's own pace on the
8-bit machines (a redraw a second, the brief's figure from Ian Andrew), so
Driller's sizes keep the speeds they were tuned for, now with frames
between: a step's frames are part-steps of a cell or so each. A cheaper
frame shows more of them, a dearer one fewer, at the same speed; the
busiest views still show a frame or two a pass. A and Z, S and X change the
turn and the step, as in Driller.

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

### The figures

Below the view, drawn into both buffers (`src/text.6502`): frames a second
and fields a frame from the flips and fields counted (`frames`, `fields`),
and the mean cycles a frame of each half, in thousands; each over the
frames since the figures were last drawn, every `FIGURE_FIELDS` fields.

The halves are timed on the BBC by User VIA T2, which runs free down at
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
| bank `BANK_DATA` | the logic's `LOGIC_CODE_BANK` (`LogicCode`, `LOGICC`: the pass, the moves, the walk, the object test, the arithmetic and the original's tables), then `LiveData` (`LDATA`: the areas' names, patterns and index by id, the lines' code), the text's widened font (`TextRAM`), and the working copy's conversion (`AreaConv`, `ACONV`) |
| bank `BANK_RASTER` | the rasteriser: row runs, code, work, state (decision 20) |
| bank `BANK_OBJ` | the object pipeline's code (`ObjCode`) with the maths' (`src/maths.6502`, `src/project.6502`, which patch themselves) |
| HAZEL | the maths' tables (`HAZEL`) and the transform's f64 table (`ObjTables`, `OTABLE`, on a page boundary), loaded from `HAZEL_LOAD` on by `!BOOT` and copied up once the OS is gone (ACCCON's Y then stays set); then `ObjWork` (the camera with it). The logic's multiplies read the maths' quarter squares here (`LOGIC_SQUARES`: the same table, ASSERTed) |
| `&0E00` on | `LIVE` (the loop, the screen, the interrupt, the keys, the text, the logic's entries and hooks, the glue that pages), `AreaCode` (`LAREA`: `area_init`, `area_enter` and the database's reader), `ObjConst` (`OCONST`), `ObjArea` (the working copy), `LogicWork` (`LOGICW`, the logic's variables), then `ObjMore` to `&3000` |
| `&0400` on | `Work` (`src/zp.6502`, this disc's variables with it) |
| `RASTER_IN_ORG` to `RASTER_IN_END` | `RasterIn`, with `ObjOut` over it, in the OS's pages, which nothing uses once the engine owns the machine |
| main RAM's `&3000` on | the transform's cache (`ObjCache`) and the sort's memory (`ObjMemo`), which only `objects_frame` and `cache_reset` touch, with ACCCON's X clear: `live_loop` clears it before `objects_frame`, `lv_enter_area` before `area_enter` (decision 31) |
| shadow RAM's `&3000` on | the logic's lists by face (`LogicFaces`), which only its passes touch: `lv_pass` sets ACCCON's X round `logic_go_pass` |

### Room for the front end

The object pipeline's bank is all but full. Its room is **`ObjMore`**:
main RAM from the end of `LogicWork` to `&3000`, a real section (file
`OMORE`, which `!BOOT` loads), guarded at `&3000`. It's read whatever bank
is paged and whatever ACCCON's X, so code there can be called from
`ObjCode` and tables there read from it; the maths' code (which patches
itself) could move there whole and leave its room in the bank. Elsewhere,
for things `objects_frame` doesn't touch: shadow RAM's `&3000` on past
`LogicFaces` (with X set, so not during `objects_frame`), the gap left in
`BANK_DB` before the database, and ANDY (`&8000`-`&8FFF` with ROMSEL's bit
7, the OS gone), which nothing uses yet. Main RAM's `&3000` on past
`ObjMemo` is `objects_frame`'s too, with X clear.

## The check

`tools/livecheck.mjs` boots the disc on jsbeeb's full video, headless.

On the logic's disc it runs the trace `tools/mklive.py --trace` makes
(`build/live/trace.json`): the scenarios of `tests/logic/` that
`LIVE_SCENARIOS` names (walls, climbs, falls, doorways into other areas,
the area's edges, rising and falling), a run of the keys they don't press
(the crosshair hidden, shown and moved, the turn's and step's sizes,
turning round), and a tour of every entrance by the FCL's GOTO, each as
`tools/logic/` takes it with decision 18's fix on, and each from the game's
start (`LogicWork` and the database written back as the disc booted with
them). A pass's keys are held on the BBC's keyboard until the disc's next
pass takes them; a poke or an FCL script's result is written into the
logic's state at `live_loop`'s top and the disc asked to take it
(`lv_request`); a minute's end comes by setting `lv_minute`, which is kept
away otherwise. It fails unless:

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
  its camera, with those flags and the crosshair, byte for byte.

On the free disc: SPACE round every entrance (each shown for `TOUR_FRAMES`
frames), then at each of `--walks`' entrances the keys held a few frames
each (the cursors and Q W O K, P L N M, turning and walking together), then
no key until the demo starts; every frame shown must be the model's render
of its camera, each SPACE go to the next entrance, each hold move the
camera as its keys ask (and only so), and the demo turn a step a frame.

On both:

- every flip shows the one frame handed over, after the last was shown
  whole; both buffers hold the same outside the view at every flip, and
  the text there is `text_shown`'s at every eighth;
- every frame handed over shows its area's lines below it;
- every write to the view is inside a frame, into the buffer not shown,
  and every write outside it to the buffer shown comes with the beam above
  its row;
- the BBC's own timing of each half is the emulator's (above).

It reports fields a frame, median, p90 and most: flip to flip (what the BBC
shows), the loop (`frame_end` to `frame_end`), each half (from the call to
`live_front_done` and `live_fill_done`) and the rest (the logic, the
animation, the text, the crosshair, and the wait for the last frame's
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
  `ObjCache` or `ObjMemo` needs ACCCON's X clear.
- **The player logic (J)**: the hooks this disc fills in, and the names it
  sets (`LOGIC_*`), are the logic's interface now; `tools/logiccheck.6502`
  keeps the defaults.
- **The maths (F)**: the projection's shared-coordinate entries are reached
  by a stub (`live_shared`) until a stage calls them; the logic reads the
  maths' quarter squares.

## What's left

- The hooks still empty: the sound, the panel and its key lights, the
  laser and the shot's pick (`$B153`, from the renderer's faces), the draw
  list (`hook_undraw`), the sensors' tests and shots, the rigs, the
  information screen, the game's end and a new game (the database and
  `LOGICW` would have to be kept to start again).
- Shooting mode moves the crosshair a pass a frame; the original's passes
  come as fast as it can go when nothing needs a redraw. Passes that change
  nothing the view shows could come a field apart, or the crosshair be
  moved without a redraw.
- A still frame is redrawn whole (decision 30); drawing nothing new until a
  key comes would let a pass start within a field of a key.
