# Driller whole: what the disc has, and what it needs

*2026-11-08. An audit of every part of Driller's full game on the ZX (the
specification, decision 1) against the port: the transcription
(`tools/logic/`), the 6502 logic (`src/logic/`), the live disc
(`src/live.6502`, `src/panel.6502`, `src/sound.6502`) and the checks.
Read from the code and the original's listing (`make zxdisasm`,
`disasm/driller.ctl`), and from runs of the oracle (`tools/logic/check.py`)
and the disc's check (`tools/livecheck.mjs`), not from the docs. Addresses
written `$` are the original's. Then a plan for each layer left.*

## The audit

"Transcribed" is `tools/logic/` (Python), "6502" is `src/logic/`, "disc"
is the live disc wired to it; "shown" is the view or the panel; "checked"
names the check against the original (the oracle, `make logic`) and the
scenario. The rigs' row is as this round leaves it (the journal's entry of
2026-11-08).

| Part | Original | Transcribed | 6502 | Disc | Shown | Checked against the original | Missing |
|---|---|---|---|---|---|---|---|
| The pass, keys, actions | `$9825`, `$9990`, `$943C`, `$A279` | yes | yes | yes | camera, panel | every scenario, the fuzz | nothing |
| Moving: walk, climb, fall, margin, doorways, edges | `$9F42`, `$9DCF`, `$A597`, `$BCCB`, `$9D1C` | yes | yes | yes | view, frames between passes (decision 36) | `walls`, `climb`, `fall`, `doors`, `edge`, `rise`, `jet`, fuzz | nothing |
| The FCL, the events, the global and area conditions | `$9B6E`, `$B320` | yes, every opcode | yes | yes | view (shown/hidden objects), panel | `fcl` and every scenario | REDRAW's own redraw is the frame's next (`hook_redraw` plays the copy's sound and runs the sensors' test, decision 192) |
| **The clock**, energy spent | `$BAE6`-`$BB90`, `$BB27` | **yes, a frame at a time** (`passes.clock_frame`) | **yes** (`logic_clock`) | **yes**, a frame a field (`lv_clock`, decision 152) | energy bar; **the clock's text above the view, at its right, as the original's (decision 190)** | `ticks`, `minutes`, **`clock`** (the text, OUT OF TIME) | nothing |
| Score | FCL 1, the rigs | yes | yes | yes | panel, seven digits | `fcl`, `rigs` | nothing |
| **Rigs: placing (D)** | `$BEFA`, `$BF9E`, `$C009`-`$C10D` | **yes** (`tools/logic/rig.py`) | **yes** (`src/logic/rig.6502`, `rigdb.6502`) | **yes** | the rig's five parts in the view, where the original puts them; the panel's messages in turn | **`rigs`, `rig-win`, `rig-sensor`, the fuzz (D and C now among its keys)** | nothing: the yields' rotation is the clock's frame's, as the original's, since the clock (decision 152 amends 120) |
| **Drilling: the gas found, the score, the messages** | `$C10D`-`$C245` | **yes** | **yes** | **yes** | PROCESSING, RIG POSITIONED, the yield in CFT, the percentage, or NO GAS FOUND, each for 50 fields (decision 121) | **`rigs`** | the original's 50 frames each hold the whole game; the disc holds only the next pass (decision 121) |
| **Collecting (C)** | `$BF56` | **yes** | **yes** | **yes** | the parts gone, RIG COLLECTED | **`rigs`** | nothing |
| Refusals | `$C0EB` | **yes** | **yes** | **yes** | AREA NEUTRAL, ALREADY PLACED, NO RIG PLACED, NOT IN PROBE, ENERGY TOO LOW, POS UNSUITABLE | **`rigs`** | nothing |
| The rig's parts as areas load | `$CD3B` | yes | yes | yes | view | `rigs` (back to area 1, into its legs) | nothing |
| The rig's animation, the drill's depth | none on the ZX: the rig stands still; the ST animates a rig in its panel | - | - | - | - | - | the ST's panel animation, if wanted (decision 47 left it out) |
| The panel's area message | `$B76E` | - (the panel's model) | - | yes | GAS BUILD UP, SECTOR CLEARED, AREA NEUTRAL; **a pass's messages and the end's highlighted as the original's `$BCA6` (decision 191)** | `make panel`, `make live` | nothing |
| **The laser and shooting mode** | `$A95C`, `$AA50`-`$AA8C` | the keys, the crosshair, shooting mode; the lines the disc's (the model's `laser`) | crosshair, shooting mode | **yes**: the four lines at half width, for sound 1's fields (decision 130) | **the lines, in frames of their own** | `crosshair`, **`shoot`** (the frames, byte for byte) | nothing |
| **The shot's pick** | `$B153`, the draw list `$8A9D` | **the BBC's frame's** (`tools/logic/view.py`, decision 131) | the hook (the check build: hits nothing) | **yes** (`lv_pick`, from the front end's draw list) | - | **`shoot`, against the original's own pick** | nothing |
| **Shot scripts** | FCL bit 7, `ShotFlag` | yes | yes | **yes** | the objects hidden, destroyed | `fcl`'s `shot` steps, **`shoot`** | nothing |
| **Guard sensors: the list, line of sight** | `$7592`, `$9841` (state 1 by the pick, state 2 by a walk with `Margin` 0) | **yes** (`tools/logic/sensors.py`, on the BBC's frame: decision 132) | the hide's stop (`$B467`) | **yes** (`src/sensors.6502`, after a pass that redraws) | - | **every redraw against the original's (`sensors`, the fuzz)**; **inside a rig's redraw and the FCL's `REDRAW` too (`rig-sensor`, `rigs`, the fuzz)** | nothing: inside a pass, from the frame the pass began with (decision 192) |
| **Sensors' shots, shield** | `$BAE6`'s list, `$BB93`-`$BC94` | **yes** (`tick`; the harness lets them fire in a `sensors` step) | - | **yes**: counted by the main loop (decision 133), sound 2, `Shield`, `GameOver` 1 | **the lines to the sensor (decision 134), the shield's bar** | **`sensors`** | the border's flash (decision 133) |
| A rig redraw's line of sight | `$9841` inside `$C259` leaves `Collided` | **yes** (`sensors.inside`, from the hooks' redraw) | **yes** (`sn_inside`) | **yes** (`lv_hook_redraw`) | - | **`rig-sensor`, against the original's own `Collided`** | nothing (decision 192) |
| Energy, the jet and the probe | FCL 2, `$15`, the minute | yes | yes | yes | bars, vehicle | `fcl`, `jet` | nothing |
| **Game over** | `$9AB7`: the message (SHIELD OUT, OUT OF TIME, ENERGY OUT, NASTY FALL, TASK COMPLETED, TERMINATED), sound 20, area 127 with the safe sectors in its name, a wait for a key | **yes** (`tools/logic/end.py`) | **yes** (`src/logic/end.6502`, `logic_go_end`) | **yes**: with the pass that finds it; the wait (decision 150) | **area 127 at its entrance; the message till a new game; the name with the safe sectors** | **`end`, `clock` (each cause but TERMINATED), the scene and the new game against the original's** | TERMINATED (the information screen's 1) |
| **New game** | `$9C36`, `$BD74`, `$97CD`: the header's values, the objects' flags from bit 7, the control menu | **yes** | **yes** (`logic_go_restart`, `new_game_due`) | **yes** (RETURN, or the wait run out) | the start's area, the crosshair | **`end`, `demo`** | the control menu (decision 150) |
| **The information screen** | `$C3DC`, `$C7EB` (I alone) | **yes** (`tools/logic/info.py`) | **yes** (`src/logic/info.6502`) | **yes**: its frame, its key (decision 153) | **the original's nine lines in the panel's font, in the view** | **`info`: every rig's case, an area, 1 (TERMINATED); the text against the original's buffer** | nothing |
| Save and load | `$C3DC`: to tape by the ROM (`$04C6`, `$0562`), 333 bytes of state and every object's flags | no | no | S and L go on (decision 153) | - | - | to the BBC's disc, if wanted (decision 153's options) |
| Title, protection, control menu | `$97A4`, `$CB7A`, `$C9C6` | the menu's read of the keys (`end.start`) | the same | the disc's own boot | - | `end`, `demo` (the menu's read) | the protection is the original's copy protection (not ported); the menu's choices are the ZX's joysticks (decision 150); the title is the tape's loading screen |
| **The demo** | `$9A27` (`$891F` 3), after the end's wait | **yes** (`passes.demo_action`) | **yes** (`demo_next`) | **yes**, at a held key's pace (decision 151) | **every pass's frames** | **`demo`: the stream whole, twice, and a key** | nothing |
| Sounds | `$9574` and the interrupt's 2 | yes (hooks) | yes | yes (decisions 110-113; 2 from the main loop) | sound | every pass's, every `sensors` step's, **the end's 20 and 6** | nothing |

Two harness changes came with the rigs (`tools/logic/oracle.py`,
`tools/logic/check.py`): the oracle now keeps every sensor from firing
(its interrupt's read of the fire list answers none), since a rig's
redraw inside its pass fills the list again and its 200 frames of waits
let the interrupt fire mid-pass; and a rig's pass takes the original's
`Collided` at the redraw, which the sensors' line of sight leaves there
(since 2026-11-10 the transcription runs that test itself and the check
holds it to the original's: decision 192).
Before, the oracle emptied the list only at each pass's start. A first
check of the disc's frames with the rigs also found a fault in
`tools/livecheck.mjs` that predates them: a poke or a GOTO right after a
pass that loaded an area could go in before the disc took the area's
colours, so the disc kept the old area's (`goto 14 34`, two K's out and
back, `goto 7 13`). It now settles first.

## What each layer left needs

Costs are estimates from what each touches; cycles are the 6502's.

*The laser and the sensors are done (the journal's entry of 2026-11-08,
"the laser and the sensors"; `docs/research/laser.md`,
`docs/research/sensors.md`). Their plans, as written before, follow; what
was built differs where those notes say: the pick needed no byte a face
(the front end's draw list says which slot each face is), and the shots
are counted by the main loop.*

### The laser (done)

- **The lines**: four EOR lines from the view's bottom corners to the
  crosshair ($AA50), at half width, shown while sound 1 plays and taken
  off after. The original draws them on the screen shown; the disc writes
  the view only into the buffer not shown (`docs/engine.md`, section 1),
  so they'd be frames of their own, the view with the lines EORed over
  it and then without, as the crosshair's frames are (`lv_cross_on`,
  `live_cross_only`), but lines. A Bresenham into one buffer, a few hundred
  bytes in `LiveGlue` or `ObjMore`, about 2K cycles a line. The model needs
  its twin in `tools/mklive.py` for the check (as `crosshair`).
- **The pick** ($B153): the faces of the last frame drawn, nearest first,
  is what the original walks (its draw list, from the back). The front
  end's output (`ObjOut`/`RasterIn`: each face's pattern and its clipped
  polygon in view coordinates, nearest first) lies in the OS's pages until
  the next frame, but it doesn't say which object a face is: it needs an
  object index a face (a byte each, `out_fo`, the front end's ~100 faces
  at most: a page) or the sort's order kept. The test is the original's:
  the polygon's vertices bracket the crosshair, then the edges' crossings
  of its row. A few hundred bytes of code, a few thousand cycles a shot,
  on a frame that's already drawn. The check: the model's render can name
  the face under a pixel (its own span buffer), so `tools/livecheck.mjs`
  can hold the disc's pick to it; and against the original, the oracle's
  `Collided` after a shot from the same camera, as the scenarios' camera
  is the original's (decision 1: the ZX's view is the oracle for which
  face covers which pixel, at the ZX's 208 across: a crosshair at an odd
  ZX x falls between two BBC pixels, decision 38).
- **Shot scripts** run already (`ShotFlag`); ECDs are database objects
  whose shot scripts destroy them and score, so they come with the pick.

### The sensors (done)

- **Their list** ($7592, the projection): each visible sensor's state by
  range (|x| + |y| + |z| from the camera against its record's range) and
  its axes mask against the faces the camera is outside of, and its
  projected point. The front end projects every object's vertices already;
  a sensor is a point (type 2) the object pass culls today (decision 14).
  Up to five, 6 bytes each, in `SensorList` (the mirror has it).
- **Line of sight** ($9841): state 1 by the pick at its pixel; state 2 by
  the logic's walk with `Margin` 0 to its corner, which the 6502 logic has
  (`move`), called through a new entry. A walk costs up to a pass's
  (tens of thousands of cycles), once a redraw.
- **The shots** (the interrupt's): a counter a sensor a field; at 0, the
  border to the area's second colour for a field, four EOR lines from the
  sensor's pixel to the view's top and bottom near its centre (state 1),
  sound 2, `Shield` down one (or `GameOver` 1). On the disc the counters
  can run in the vertical sync's interrupt (a few dozen cycles a sensor),
  but the lines and the shield's bar belong to the frame and the panel,
  which the interrupt can't draw into both buffers: the interrupt sets a
  flag, the loop draws. `Shield` then changes outside the logic's passes,
  as `Energy` does at a minute: the trace needs the shots' fields as
  steps, as `tick` is for the minute.
- The oracle's silencing (`SENSOR_SHOTS`) comes off for the sensors'
  scenarios, which then hold the clock of the shots as the scenarios hold
  the minute.

### Game over and a new game (done)

*Done, with the demo (the journal's entry of 2026-11-08, "the end, a new
game and the demo"; `docs/research/end.md`). The plan as written before
follows; what was built differs: area 127 has an entrance 0 of its own, so
the end puts the camera there; the new game's code is in main RAM
(`LogicMore`), since it reads the header in one bank and calls the pass in
the other; the globals' records are not put back (the original doesn't).*

- **The end** ($9AB7): the message by cause in the panel (the six texts
  are in the original's table, `$8CBA` on), sound 20 unless won, then area
  127 entered with `FclVar32` in its name, `GameFlags` `$4004` and a
  redraw, and a wait for a key (13 × 75 frames, then the demo). On the
  disc: a state after `lv_over` that enters area 127 (the renderer has
  every area), and a key's wait in `lv_pass`.
- **A new game** ($9C36): from the database's header (the variables
  above), the objects' flags from bit 7 in place (no copy needed: the
  original restores its own database that way), `RigPlaced`, `RigState`,
  the score and the FCL's variables zeroed, area and entrance from the
  header. The port's start sizes (decision 48) instead of the header's.
  About 300 bytes in `LOGIC_BANK`, which has room after this round's code
  moved out (the journal's room figures). The globals' records (the rig's
  parts, the three globals the load hides) need their first bytes back:
  135 bytes, the mirror's at the start (`ZXV_INIT`), kept in a bank.
- **The demo** ($9A27): the header's stream of actions, a pass each;
  the disc already draws whatever the logic does. Small, once the end
  exists.

### The information screen, save and load

*The screen is done (the journal's entry of 2026-11-08, "the information
screen"; `docs/research/info.md`); save and load are not (decision 153).
The plan as written before follows.*

- The screen draws into the view (cleared) text of the panel's font: the
  view's 104 pixels take 26 characters at four pixels, as the original's
  26-character rows. The keys: 1 abort, S and L, any other to go on.
- Save and load are the ZX's tape (ROM `SA-BYTES`, `LD-BYTES`): on the BBC
  a disc file of the same 333 bytes and the objects' flags would be the
  port's (a decision for Matt), through the DFS's OSFILE before the OS is
  gone, which it isn't any more once the engine owns the machine: it
  would need the disc read the loader does, and a write.

### Memory

*Since the end, the clock and the information screen: the logic's code
that reaches both of its banks is in main RAM after `ObjMore`
(`LogicMore`), what of it reads `LOGIC_BANK` alone in that bank, and the
information screen's text, its fields' code and its font in the front
end's bank after its code (`InfoData`); the journal's entries of
2026-11-08 have the bytes ("room in main RAM again" the last). As written
after the rigs:*

After the rigs (the journal's entry of 2026-11-08 has the bytes): the
rigs' code is in both of the logic's banks (`LOGIC_BANK` the scans of the
records and the messages, `LOGIC_CODE_BANK` the rest), their entries and
the messages' queue in main RAM below `&3000`, `RigFigures` and
`RigScratch` in `LogicWork`. The free disc shares the map and its
`LiveGlue` (the free camera's tables) is what fills `LOGIC_BANK`, so a
layer that adds to that bank must take from the free camera's tables (or
give the free disc a map of its own). `BANK_DATA` has little left after
the rigs; shadow RAM past `SoundData` (data only, reached with X set) and
`ObjMore` are the largest rooms left; HAZEL and ANDY have next to none.
