# Driller's end, a new game and the demo on the BBC

*2026-11-08. The end of the game, the new game after it and the demo:
what the original does (read from its listing, `make zxdisasm`), its
transcription (`tools/logic/end.py`, `tools/logic/passes.py`), the 6502's
(`src/logic/end.6502`), the disc's (`src/live.6502`), and the checks.
Addresses written `$` are the original's.*

## The original

**The end** (`$9AB7`). The input finds `GameOver` set after its read of the
keys, held or not, and goes there instead of returning:

- the sensors' shots stop (`$8A21` bit 2, until the sensors' test at its
  redraw clears it again), once a shot's lines are off;
- the message by cause, from the table at `$8CBA` (14 characters each):
  1 SHIELD OUT, 2 OUT OF TIME, 3 ENERGY OUT, 4 NASTY FALL, 5 TASK
  COMPLETED, anything else TERMINATED (6, the information screen's 1);
  printed in the panel's message line and highlighted (`$93C4`, `$BCA6`);
- sound 20, unless won (5);
- area 127 entered at entrance 0 (`$9D1C`), the crosshair off. Area 127 is
  a row of cuboids, quads, a triangle and a pyramid, and an invisible
  entrance of id 0, so the camera goes there, as to any entrance;
- the safe sectors (`FclVar32`) written into area 127's name in the
  database, two digits after its first character, the first a space for 0
  (`$9390`): "  0 CLEARED " becomes " 18 CLEARED ". Nothing puts it back;
- everything redrawn (`GameFlags` `$4004`), the sensors' test, the panel,
  the highlight off;
- a wait: 75 frames in which no key is read, then up to 12 x 75 frames in
  which any key ends it. With none, the demo is next (`$891F` 3).

Then sound 6 and `GameFlags` bit 1, and the input returns. The main loop's
events find none due, and its `$982B` sees bit 1: a new game (`$9C36`) and
its start (`$97CD`).

**A new game** (`$9C36`, with `$BD74`): from the database's header, the
probe's level, the step's and turn's sizes, the vehicles' energy and
shields, the falls' and climbs' limits, the probe's highest level, the
keys' repeat, the clock's text (04:00:00) and the vehicle; the score, the
FCL's 32 bits and 32 variables, the rigs (`RigPlaced`, `RigState`,
`GasChosen`), the crosshair, shooting mode and the sensors' lists' counts
cleared; area and entrance from the header; then every object of every
area has its flags as at the start: destroyed and invisible cleared, and
invisible again where bit 7 (invisible at the start) says. The globals'
records are kept as they are (the rig's parts, which the area's load
places or hides). `GameOver` is 1 while it runs (the interrupt keeps no
time), and 0 at the start's end.

**The start** (`$97CD`): everything to redraw, the panel, the clock's text;
but in the demo, the control menu (the ZX's joysticks, which reads the keys
until ENTER), the sensors' test, 40 frames, and the crosshair shown as B
shows it ($A95C action `$15`).

**The demo** (`$9A27`): each pass, a key held ends it (`$891F` 1, sound 6,
a new game with the menu); else the header's stream of actions (`$CF84`
on, 117 bytes, 476 passes): a byte an action, or `$80 + n` and an action
done n times; 0 ends it, and a new game begins the demo again. The action
goes through the input's dispatch as one key's would, not kept in
`Actions`. The demo's actions include drilling, shooting mode and fire.

## Transcribed

`tools/logic/end.py`: `end` ($9AB7 to the wait), `restart` (the wait
answered by keys or run out, sound 6, then the main loop's `$982B`),
`new_game` ($9C36, $BD74, $9CDD), `start` ($97CD). The wait's reads of the
keys are the original's `$943C` (none held, then the key; the control
menu's read again, a repeat). `tools/logic/passes.py`: `demo_action`
($9A27) in the input, and `new_game_due` ($982B) after the events; a pass
after which a new game began answers `"new"`. The redraws are hooks
(`ended`, `started`).

## In 6502

`src/logic/end.6502`, in a section of main RAM (`LogicMore`, after
`ObjMore` on the disc), since it reads the database's header and records
in `LOGIC_BANK` and calls the pass's code in `LOGIC_CODE_BANK`:
`logic_go_end`, `logic_go_restart` (A 0 for keys in the logic's bitmap, else
the demo), `new_game_due`, `new_game`, `demo_next` (the stream, from
`input_pass`'s demo branch in `src/logic/pass.6502`). `logic_pass` answers
3 for a pass after which a new game began. The end's six messages are the
original's bytes (`tools/mklogicdata.py`'s `ZX_END_MSG`). The demo's two
pointers into the database are moved as the mirror's others are
(`ZXV_PTRS`). The header's pointers (`$BD74`'s first part) never change and
aren't written again.

## On the disc

`src/live.6502`'s `lv_pass`:

- The game over comes at once: with `GameOver` set the next loop's pass
  runs whatever is held (as the original's input finds it after its read of
  the keys), answers 2, and `logic_go_end` follows in the same call. The
  pass's frames are an area's change (area 127, at its entrance), the
  message is the panel's (`lv_hook_message`, shown till a new game), sound
  20 the sound driver's; the sensors' test after its redraw as after any.
- The wait (`lv_waited`): no key read for `END_DEAF` fields, then any held
  or gone down (RETURN is the ZX's ENTER now), until `END_FIELDS`, when it
  has run out. Either way the next pass's call is `logic_go_restart`
  (`lv_call`), answered as 3: the area entered, the clock's minute from
  now. The start's waits (40 and 9 frames) are the next pass's.
- The demo's passes come with no key, a pass each `PASS_FIELDS` with the
  frames between as a held key's (decision 151); any key ends it.
- The panel: area 127's name shows the safe sectors (`panel_values`, from
  `FclVar32`, as the end writes them); every name is the original's twelve
  characters with a space each side (`tools/model/panel.py`'s
  `name_text`), which is what the panel showed already for every other
  area.

## The checks

- **Against the original** (`make logic`): a scenario's `end` step runs
  the original's end to its wait, the scene's state compared (the
  renderer's outputs taken from the original, the logic's own kept), then
  ENTER held from its 75th frame through the control menu, to the main
  loop's top, and the new game compared; `end demo` lets the wait run out.
  `demo x30` is passes with no key while the demo plays; a pass of keys
  ends it, the original's menu taking ENTER. `tests/logic/end.txt`: a
  fall, energy out on a minute, won (no sound 20), the demo's first 30
  passes and a key, shield out by a sensor's shot; `tests/logic/demo.txt`:
  the demo whole, its new game, the demo again, and a key.
- **The 6502** (`make logic6502`): the same steps (`chk_end`,
  `chk_restart`), every variable and the database after each. The shield's
  end is left to the disc (the trace leaves the sensors' shots out).
- **The disc** (`make live`): the end comes with the pass that finds the
  game over, by itself; RETURN once the wait reads keys, or none for the
  demo; every pass's state, sounds, messages and frames as everywhere
  else, area 127's frames the model's, its name with the safe sectors.

## What's left

- The highlight of the message line (decision 121: the panel's font has no
  inverse).
- Save and load: the ZX's tape, not ported.
