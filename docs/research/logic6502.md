# Driller's player logic in 6502

*Track J, 2026-10-31. Driller's player logic for the Master, transcribed
from `tools/logic/` (the specification on our side, itself checked pass by
pass against the ZX original by `make logic`; `zx-logic.md` describes
what it does) and checked against it pass by pass by `make logic6502`.
Addresses written `$` are the original's; the 6502's are symbols.*

## What's here

| File | What |
|---|---|
| `src/logic/vars.6502` | the workspace, `LogicWork`: the original's variables by its names, with their first values |
| `src/logic/pass.6502` | a pass (`logic_pass`, `$9825`-`$982B`): the input (`$9990`), the keys (`$943C`), the key table (`$99EF`), the crosshair (`$A95C`); the minute (`logic_minute`, `$BB27`) |
| `src/logic/move.6502` | the movement actions (`$A279`): rise, fall, the turns, looks and rolls, turning round, the sizes; a step (`$A364`) |
| `src/logic/walk.6502` | the move (`$9F42`): the walk through the cells, the next crossing, the area's extent; a crossing (`$9DCF`): the climb and the fall |
| `src/logic/touch.6502` | which object a crossing enters (`$A597`); keeping clear of faces (`$BCCB`) |
| `src/logic/index.6502` | the index of the area's objects, which the object test and `lookup` scan |
| `src/logic/area.6502` | objects by id (`$A8BA`), the areas (`$BE18`), the rigs' parts (`$CD3B`), the entrances (`$9D1C`) |
| `src/logic/fcl.6502` | the events (`$9B6E`) and the FCL interpreter (`$B320`), every instruction Driller's ZX code has |
| `src/logic/arith.6502` | the original's multiplies and divide as the logic uses them |
| `src/logic/hooks.6502` | where the logic calls what it leaves out (`tools/logic/hooks.py`'s list) |
| `src/logic/call.6502` | main RAM: the frame's way in, and the way between the two banks |
| `src/logic/bank.6502` | the two sideways RAM banks' layout |
| `src/input.6502` | the keyboard, as the ZX's (decision 10) |
| `tools/mklogicdata.py` | the database and the first values, from the tape and the in-play snapshot, into `build/logic6502/` |
| `tools/logictrace.py` | what the 6502 must do: `tools/logic/`'s traces, decision 18's fix on |
| `tools/logiccheck.6502`, `tools/logiccheck.mjs` | the check build and the harness |
| `mk/logic6502.mk` | `make logic6502`, `make logic6502fuzz` |

```sh
make logic6502       # build and check: the scenarios and a fuzz, with cycles a pass
make logic6502fuzz   # a longer fuzz: L6FUZZ walks from seed L6SEED
node tools/logiccheck.mjs build/logic6502 build/logic6502/trace.json --slow 20   # the slowest passes
node tools/logiccheck.mjs build/logic6502 TRACE --profile                        # where the cycles go
```

## Memory

- **`LogicWork`, main RAM, `LOGIC_WORK` to `LOGIC_WORK_END`** (the OS's
  pages &08 to &0C, unused once the engine owns the machine: its interrupt
  is the vertical sync's alone, so the OS's sound workspace, buffers, soft
  keys and characters there go untouched; &0D is the NMI's). Saved as
  `LOGICW`, holding each variable's first value: loading it starts a game.
  - **The mirror**, `zxv`: the original keeps most of the logic's
    variables in one block with its tables among them, and the FCL reaches
    into it (variable n is `$887F + n - 1` for any n to 256, so `SETVAR`
    can write the flags and tables after the 32 variables; an
    instruction's length is read at `$8939 + op`). So the block is kept
    whole at the original's offsets, `ZXV_ORG` to `ZXV_END`, and
    `zx(a)` is where the original's address a is. Its six words that
    point into the database (`AreaObjPtr`, `AreaNamePtr`, `AreaCondPtr`
    and the original's `$8912`, `$8914`, `$8922`) point into the bank's
    copy, moved by `DB_MOVE`.
  - The rest of `tools/logic/state.py`'s variables, each by its name.
  - The index of the area's objects (`ix_*`).
- **`LOGIC_BANK`**, sideways RAM (file `LOGIC`): Driller's database at
  the bank's top (`LOGIC_DB`), the ZX's bytes from the tape in the
  original's layout, so the logic walks the records the original walks;
  and below it the code that reads the database (`area`, `fcl`,
  `index`). The FCL changes the objects' flags in it as it runs, so a new
  game loads it afresh.
- **`LOGIC_CODE_BANK`**, sideways RAM (file `LOGICC`): the rest of the
  logic, the original's tables it reads (the sine table, the key codes,
  each key code's actions), the quarter squares its multiplies use, and
  the object test's lists by face. It has room to share.
- The code and the database come to more than a bank: the two halves call
  each other through main RAM (`far_events`, `far_answer`), which is where
  the frame calls in too (`src/logic/call.6502`, with the hooks).
- **Zero page**: baron's pool, routine by routine (`ZA_AUTO`); nothing
  fixed.

## The frame's interface

The entry points, in main RAM (`src/logic/call.6502`), each paging the
bank it needs in:

- `logic_go_init`, once `LOGICW`, `LOGIC` and `LOGICC` are loaded: the
  area's objects indexed.
- `logic_go_pass`: a pass, the input and the events. A = 0 if there was
  nothing to do (no key held and no minute: the original waits in its
  input, and here the frame calls again), 1 if a pass ran, 2 if the game
  is over. The pass clears the flags it reports, so the frame takes them
  before calling it again.
- `logic_go_minute`, when a minute of the clock ends (the original's
  interrupt counts the clock, `$BAE6`): the energy and the minute
  counters. The next pass takes the minute. Nothing counts the clock yet.
- `logic_go_colours`, the original's `$A77A`, for the frame's redraw when
  `AreaChanged` is set: `ScreenColours` takes the area's colours, the
  sensors' flash counters restart, `AreaChanged` is cleared.
- `logic_go_shown`: each object's flags into `ix_flags`, for the renderer
  (its own bank is in as it draws, so it can't read the records).

What the renderer reads, all in `LogicWork`:

- the camera: `PlayerX`, `PlayerY` (the eye), `PlayerZ`, 16-bit world
  units, 64 to a cell; `Pitch`, `Yaw`, `Roll`, 0-71 in 5° steps;
- what to redraw (`zx-logic.md`, "The redraw flags"): `GameFlags` bit 2
  re-project (a move, a turn, an object shown), `GameFlags2` bit 3 redraw
  from the last list (an object hidden); the rest of both, the panel's;
  `Wipe`, the screen's copy wipes; `Sound`, a sound after the copy;
- the area: `AreaId`, `AreaChanged` (an area has loaded), `AreaColours`,
  `ScreenColours`, `AreaScale`;
- the objects: `ix_flags` after `logic_go_shown`, `ix_n` of them in the
  original's order, the area's `AreaObjects` first and then the eight
  globals (the rig's parts among them, which `place_rigs` moves as an
  area loads); bit 6 of each is invisible, bit 5 destroyed. `ix_id` has
  their ids;
- the crosshair: `CrossX`, `CrossY` (up), `CrossOn`.

The hooks (`src/logic/hooks.6502`) do nothing yet, as
`tools/logic/hooks.py`'s defaults: the sound, the waits (`hook_wait`: the
original waits in the logic while the interrupt counts `Countdown` down,
for the size keys, the crosshair keys and the FCL's `DELAY`), the panel
and its key lights, the crosshair, the screen's colours, the FCL's
`REDRAW`, the draw list's removal (`hook_undraw`, which answers "not
drawn"), the sensors, the laser and the shot's pick (`hook_shot`, which
hits nothing), the rigs, the information screen and the game's end.

## The keys

`src/input.6502`'s bitmap is the ZX's keyboard: byte r is half-row r
(`$FEFE` to `$7FFE`) and bit b its key b, as the original reads them, so
`read_keys` is the original's `$943C` on it, taking up to five in the
ZX's order (decision 19). Each BBC key is the ZX key of its name; ESCAPE
is the ZX's 1, COPY and the cursor keys the ZX's cursor joystick (0, and
5 to 8). The Kempston joystick isn't read: `Control` is 0 in play.

## Where it works differently, and why it's the same

The behaviour is the original's (with decision 18's fix); the check
compares every variable and the database after every step. These are
ways of getting there faster or into the memory, each the same result:

- **The index**: the original scans every record for every crossing, and
  for an object by id. The objects' cells, sizes and ids change only as an
  area loads, so `index_objects` copies them into main RAM then, with each
  record's address; flags and types are read from the records as the
  original reads them (`answer`).
- **Lists by face**: a crossing on one axis can only enter an object
  whose face on that axis is the next cell, so `touch` follows a list of
  those, in the original's order, instead of scanning all. The lists are
  built from the index as the first crossing after a load needs them. Any
  other crossing filters the objects by their faces, then tests them as
  the original does.
- **The walk's crossings kept**: an axis's next crossing point depends on
  nothing that changes during the walk but that axis's cell, so it's kept
  until the cell moves on.
- **The divide**: the original's shifts a bit at a time from the
  dividend's top 1, which for any divisor but 0 is the floor of the
  magnitudes' quotient; `cross_coord` divides by the quickest of three
  ways that give it, and takes the original's own way for a divisor of 0
  (a crossing on no axis), whose remainder runs on in its own way.
- **The multiplies** are by quarter squares (`mul88`), and exact, as
  the original's are.
- **The key table**: the original searches it for each key; the build
  makes each code's two actions into tables by the same search.
- **The FCL**: the instruction loop keeps an offset and derives the
  original's count from it, and sets `FclOp` as the script ends, which is
  what the original leaves there.

## The check

`tools/logictrace.py` runs `tools/logic/` with `move.FIX_CORNER` on, from
the in-play snapshot, on every scenario of `tests/logic/` and on random
walks (`tools/logic/check.py`'s), and records each step: a pass's keys as
the bitmap, a minute, a poke, an FCL script, and the bytes it changed.
`tools/logiccheck.mjs` runs each on the check build in jsbeeb from the
game's start (`LOGICW` and `LOGIC` loaded afresh, `logic_go_init`), and
after each step compares the mirror, every other variable and the whole
database, the database pointers moved back; then the objects' flags
`logic_go_shown` gives against the records the original walks. A pass the
transcription finds would hang must not return. The arithmetic is checked
alone too, on edge and random cases. It reports the cycles of each pass,
from `logic_pass`'s first instruction to its return, by what the pass
did. The hooks are the transcription's defaults on both sides.

`make logic` still checks the original's behaviour: `FIX_CORNER` is off
by default, and `tools/logic/check.py --fix-corner` shows what the fix
changes against the original. `tests/logic/corner.txt` is the bug's
other form, which runs on past its target to an object without hanging.

## What's left

- The hooks (the live disc fills in the sound: `docs/research/sound.md`;
  this check build keeps the defaults): the waits' timing, the panel, the crosshair, the
  laser, the shot's pick and the draw list (the renderer's), the sensors'
  tests and their shots (`$9841` and the interrupt's), the rigs (`$BEFA`),
  the information screen (`$C3DC`), the game's end (`$9AB7`) and a new
  game (`$9C36`).
- The clock: the interrupt's seconds and minutes (`$BAE6`), which call
  `logic_go_minute`.
- The disc: loading `LOGICW` into main RAM and the two banks into
  sideways RAM, and calling the entries from the frame.
- The demo's playback (`$9A27`).
