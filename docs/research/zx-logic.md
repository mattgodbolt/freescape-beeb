# Driller on the ZX: the player logic

*Track I, the player logic. Found 2026-10-31 by reading Driller's ZX code
(the retail tape, decision 1) with Castle Master II's annotated listing
and ScummVM's `movement.cpp` as maps, then transcribed in `tools/logic/`
and checked pass by pass against the original running headless
(`make logic`; the journal's entry of 2026-10-31 has what it measured).
Addresses are the original's; `disasm/driller.ctl` names them and
`make zxdisasm` builds the annotated listing.*

Tags: **[checked]** means the transcription agrees with the original on
every pass the scenarios and the fuzz compared; **[read]** means read from
the code and not exercised by a check. Units are the ones in
`zx-driller.md`: a cell is 64 world units, angles are 5° units (0-71).

## For the other tracks, in short

- **A pass** (`$9825`): the input (`$9990`) waits for a key or a minute
  of the clock and does each key's action; the events (`$9B6E`) run the
  FCL; then the redraw, the copy and the sensors (`$9807`, `$9841`) if
  `GameFlags` bit 2 or `GameFlags2` bit 3 is set, and the panel
  (`$B72B`). One pass a redraw: nothing moves between redraws.
- **Keys.** Up to five are read a pass, in the keyboard's order (half-rows
  `$FEFE` to `$7FFE`, bit 0 first), and each key's action is done in that
  order: Q then O turns and then steps, whichever was pressed first. In
  play a held key acts every pass (`RepeatDelay` and `RepeatRate` are 0).
- **A step** is `StepUnits` = `Step` × `AreaScale` world units along the
  yaw: `x += ⌊step·sin(yaw)/64⌋`, `z += ⌊step·cos(yaw)/64⌋`, negated after
  the floor for a step back [checked]. The jet first splits it by the
  pitch: `y += ⌊step·(−sin(pitch))/64⌋` (negated back), and the horizontal
  step is `⌊step·|cos(pitch)|/64⌋`.
- **The move is a walk through the cells**, from the camera toward the
  target, one cell boundary at a time, nearest first, with each crossing
  tested against the objects. It stops a unit short of a face it can't
  cross, and nothing slides along a wall. On the probe it climbs onto
  objects up to `ClimbLimitScaled` cells high and falls off edges; a fall
  of more than `FallLimitScaled` cells ends the game. Then it keeps the
  camera `Margin` (10) units clear of any face within that of it
  [checked].
- **For the renderer's animation of a step** (decision 4): the camera
  ends on the straight segment from where it was toward the target, at
  the target or a unit short of the first face that stopped it, except
  that a step up or a fall changes y at the crossing where it happens
  (and ends the step there), and the margin's push then moves the end up
  to 10 units back from a face, along each axis it pushes. A rise or
  fall on the probe is a jump of `AreaScale` cells in y. An area change
  replaces the camera.
- **The redraw flags** are `GameFlags` (`$8920`) and `GameFlags2`
  (`$8921`), cleared at each pass's start and ORed by each action. Bit 2
  of `GameFlags` re-projects (`$6B12`): a step or rise that moved, any
  turn, look or roll, and an object shown. `GameFlags2` bit 3 redraws from
  the last projection: an object in the draw list hidden. The rest tell
  the panel which read-outs changed [read]: `GameFlags` bit 4 the
  position (a move), 5 the yaw, 6 the pitch, 7 the turn's size, 3 the
  vehicle; `GameFlags2` bit 0 the step's size, 1 the score, 2 the
  energy, 4 the shield, 7 the probe's level. A GOTO sets them all
  (`$FFFC`).
- **For the 6502's logic**: the 8-bit compares are the sign of the 8-bit
  difference (`CP` then `JP M`), not signed compares, and cells and sizes
  wrap at 8 bits; positions wrap at 16. The step's products are exact,
  then floored by 64; the walk's crossing points are a 16 × 16 product
  then the original's 32 / 16 divide with its rounding
  (`tools/logic/arith.py`). The logic walks the original's object
  records (type and flags, cell, size, id, length, FCL) and the eight
  globals in order, the area's first; the data track's records must keep
  that order and those fields. `tools/logic/` is the specification to
  check it against, pass by pass.
- **The areas connect by FCL**: a doorway is a rectangle on a wall's face
  whose collided script is GOTO area, entrance; an area's edge has a
  rectangle on each side (ids 51-54) whose script is GOTO area, 0, which
  wraps the camera across (`$9D1C`). So the logic needs the FCL
  interpreter, and `tools/logic/fcl.py` has it whole, with the renderer's
  and the sound's parts as hooks.

## The main loop

`$9825` [checked]:

1. `$9990`, the input:
   - clears `GameFlags` and `GameFlags2`, `Collided` (`$8A69`),
     `ShotFlag` (`$8BF1`), `Wipe` (`$8BF0`), `EventsDue` (`$8A64`),
     `Sound` (`$8A1F`), `Blocked` (`$8A1E`) and `ActionIndex`;
   - reads the keys (`$943C`) until one is held; if `GameOver` is set,
     goes to the end (`$9AB7`); if a minute has ended (`MinuteCount`,
     `$889D`, isn't `MinuteSeen`, `$88AE`), takes it and returns with
     only `EventsDue` set, whatever keys are held;
   - maps each key to an action and does them in turn: 1-`$14`
     `$A279`, `$15`-`$1E` `$A95C`, `$28` and `$2A` `$BEFA` (the rigs),
     `$29` `$C3DC` (information); the last two end the input.
2. `$9B6E`, the events, if `EventsDue`: the collided object's script, the
   global conditions, the area's.
3. `$982B`: if `GameFlags` bit 1 (set by the end, `$9B67`), a new game
   (`$9C36`, `$97CD`).
4. `$9807`: the redraw (`$6B12`); then, if `GameFlags` bit 2 or
   `GameFlags2` bit 3, `$9841`: the sensors' tests, the screen's colours
   (`$A77A`, if `AreaChanged`), the copy (`$9BF7`, or the wipe `$AB25`
   if `Wipe`; the copy then plays `Sound` and clears it) and the
   crosshair; then the panel (`$B72B`).

The input waits: with no key held it loops until a key or the minute.
That's the only pause between passes.

## The keys

`$943C` reads the half-rows into `KeyRows` (`$9404`) and turns each key
held into a code from `$9414` (five a half-row, ASCII for letters and
digits, `$0D` ENTER, `$20` SPACE, `$7F` CAPS, `$1B` SYM), at most five,
into `Keys` (`$8FBD`, `KeyCount` `$8FBC`); then the Kempston joystick's
fire, up, down, left and right as `$95`, `$91`-`$94` if `Control`
(`$8FC5`) is 2. A set of keys the same as last time's is a repeat
(`Repeating`, `$940C`): it waits `RepeatDelay` (`$8FC3`) frames the first
time and `RepeatRate` (`$8FC4`) after; both are 0 in play [checked].

The key table (`$8FC8`): twelve entries of key, action, shooting mode's
action, then twenty-four of key, action [checked, from the bytes]:

| Keys | Action | In shooting mode |
|---|---|---|
| O, 7, joystick up | 3: step forward | `$1A`: crosshair up |
| K, 6, joystick down | 4: step back | `$19`: crosshair down |
| Q, 5, joystick left | 5: turn left | `$18`: crosshair left |
| W, 8, joystick right | 6: turn right | `$17`: crosshair right |
| R | 1: rise | |
| F | 2: fall | |
| P | 7: look up | |
| L | 8: look down | |
| N | 9: roll | |
| M | `$0A`: roll the other way | |
| U | `$0D`: turn round | |
| A, Z | `$0B`, `$0C`: the turn's size up, down | |
| S, X | `$11`, `$12`: the step's size up, down | |
| 0, joystick fire | `$16`: fire | |
| B | `$15`: show or hide the crosshair | |
| SPACE | `$1E`: shooting mode | |
| D | `$28`: drill | |
| C | `$2A`: collect the rig | |
| I | `$29`: information | |
| T, Y | `$5B`, `$5E`: none (the dispatch ignores them) | |

5, 6, 7 and 8 are the cursor keys, so 5 turns; only 0 fires. 1 isn't in
the table: the information screen reads it (`$C7EB`). Any other key's
action is `$7F`, nothing.

## The actions

`$A279`, actions 1-`$14` [checked]. Each sets `EventsDue` (`$A57C`) but
the size keys, which exit at `$A581`; each ORs its flags into
`GameFlags` (C) and `GameFlags2` (B).

- **1, rise.** In the jet: the target `StepUnits` above, and a move
  (`$9F42`); flags `$14` if it moved. On the probe, if `ExtLevel` is
  below `ExtMax`: the target `AreaScale` cells above the eye, tested by
  a move as the jet's (`InJet` set for it); if it got all the way,
  `ExtLevel` up one and `BodyHeight` up `AreaScale`, flags `$8014`; else
  y put back (but not x or z, which the margin may have moved). The
  target's x and z are set to the camera's first, even when nothing more
  happens.
- **2, fall.** In the jet: down `StepUnits`, a move. On the probe, if
  `ExtLevel` isn't 1: down a level, `AreaScale` cells, with no test;
  flags `$8014`.
- **3, 4, step** (`$A364`, above). On the probe the move is made from the
  feet (the eye less `BodyHeight` − 1 cells) and the eye put back on top
  of wherever the feet end. If it's the pass's only key, `Wipe` is set.
  Flags `$14` if it moved.
- **5, 6, 7, 8, 9, `$0A`: turn, look, roll** by `Turn`, mod 72 (by the
  sign of the 8-bit sum, `CP $48 : JP M`). Flags `$24` (yaw), `$44`
  (pitch), `$04` (roll).
- **`$0D`, turn round**: yaw + 36; in the jet with a pitch, the pitch
  becomes 72 − pitch. Flags `$24`, or `$64`.
- **`$0B`, `$0C`: the turn's size** (`TurnIndex` in `TurnTable`, `$88C9`:
  1, 2, 3, 6, 9, 18), stopping at the ends; flags `$80`; then a wait of 7
  frames.
- **`$11`, `$12`: the step's size** (`StepIndex` in `StepTable`, `$88BE`:
  1, 2, 5, 10, 25, 50, 100, 250), `StepUnits` = `Step` × `AreaScale`;
  flags `$0100`; a wait of 7 frames.
- `$0E`, `$0F`, `$10`, `$13`, `$14`: nothing.

`$A95C`, actions `$15`-`$1E` [checked, but for fire]:

- **SPACE** toggles `ShootMode` (`$88AC`): the panel is redrawn with
  `GameFlags` 1 for the moment, a sound, and the crosshair shown
  (`CrossOn`, `$88A2`, `$FF`) and centred (`CrossX`, `CrossY` = the view's
  centre, `$88D9`) on the way in; on the way out, it's left as
  `CrossWanted` (`$88AD`) says. A wait of 9 frames.
- **B**, outside shooting mode, toggles `CrossWanted` and shows or hides
  the crosshair, centred.
- **`$17`-`$1A`** move the crosshair a pixel, from 1 to twice the view's
  centre, if it's shown.
- **Fire** (`$16`), if the crosshair is shown: the laser drawn, the
  object under the crosshair found (`$B153`, from the renderer's
  projected faces) into `Collided`, and `ShotFlag` and `EventsDue` set,
  so the events run that object's shot instructions [checked, 2026-11-08:
  the pick from the BBC's view, `docs/research/laser.md`;
  `tests/logic/shoot.txt`].

## Moving

### The move (`$9F42`)

Given the target (`TargetX`, `TargetY`, `TargetZ` at `$88AF`), from the
camera [checked]:

- The cells: `cell(v) = (v >> 6) AND 255` (`ADD HL,HL` twice, then H).
  `CellX`-`CellZ` (`$88B5`) start at the camera's, the target's go to
  `$9F33`. An axis moves if its cells differ, and up if the 8-bit
  difference's sign is clear. No axis moves: no walk.
- **The walk**, while any cell differs from the target's:
  - x first, if x has a boundary left: the boundary (the next cell's
    first unit going up, this cell's going down), and y and z there,
    `start + t·delta/dx` with `t` the distance to the boundary (`$9179`,
    then `$92D7`, which rounds the quotient's magnitude up when the
    remainder is at least half the divisor, floored).
  - If z moves and isn't in this cell at that point, z's boundary comes
    first; if it's exactly on z's boundary (going up: in the next cell,
    a multiple of 64), x and z cross together. Then likewise y.
  - Else z first, likewise, then y.
  - The crossing stops at the area's extent (`AreaExtent`, `$88DF`: the
    next cell 127 going up, this cell 0 going down; x, then z, then y).
  - Else `$9DCF` crosses: 0, on; 1, stopped; 2, stepped up or fell.
- **Stopped** (1): the target is the crossing point, a unit back into
  this cell where the point is in the next (going up; going down it's
  already this cell's first unit). **Stepped up or fell** (2): x and z the
  crossing point (now in the new cell), y as `$9DCF` left it; the walk
  ends there, short of the target.
- Then `$BCCB` for the eye's cell in the jet, or for each of the probe's
  `BodyHeight` cells from the feet up; then the target becomes the
  camera. Returns 1 if the camera moved.
- With `Margin` 0 it only walks (the sensors' line of sight, `$9841`,
  uses it that way after the redraw).

### A crossing (`$9DCF`)

[checked]

- `$A597` asks whether the crossing enters an object; a hit's id goes to
  `Collided`.
- **The jet**: a hit stops it (`Blocked` = 1). Else across, y too.
- **The probe** climbs: counting up from the feet, it needs `BodyHeight`
  clear cells in a row in the next column, the lowest at most
  `ClimbLimitScaled` cells up, with each cell above clear going up and
  below the area's top. The target rises by the cells it climbed
  (`Sound` 4), and the crossing returns 2; too high, it's stopped
  (`Blocked`). A probe one cell high with nothing in the way doesn't
  test.
- **Across**, the probe falls: down from the feet until a crossing down
  enters an object or the area's floor (y cell 0). A fall lowers the
  target (`Sound` 3) and returns 2; more than `FallLimitScaled` cells
  ends the game: `GameOver` 4, `Roll` 18 and `Pitch` 0. The object landed
  on is `Collided`: its collided script runs.

### Which object a crossing enters (`$A597`)

[checked] The area's objects, then the eight globals, skipping the
invisible (flag bit 6; every entrance in Driller's data is invisible).
Objects are boxes of whole cells, so the test is by cells:

- the crossing's face is the object's: going up, the next cell is the
  object's first (`cell + 1 = o`); going down, this cell is the one past
  its last (`o + size = cell`);
- and on each of the other two axes the current cell is inside the
  object (`o ≤ cell < o + size`, by the signs of 8-bit differences), or
  that axis crosses into it at the same time.
- Flat objects (size 0 on an axis) are entered only across that axis.
- A rectangle (type 3) or a line or polygon (10 on) returns at once. Any
  other type is remembered and the scan goes on; the last remembered
  returns. So a doorway's rectangle wins over the wall behind it.
- One quirk (`$A682`): crossing y with x crossing up at the same time,
  the test for x adds one to the object's end rather than the cell when
  the cell is past the object, which only matters for an object 255
  cells wide.

### Keeping clear of faces (`$BCCB`)

[checked] Each axis whose target is within `Margin` (10) of its cell's
low edge, or 54 of the high, marks a crossing that way. If those
crossings together enter an object, each marked axis's target moves to 10
from its low edge or 54 from it (the low byte only). The first such
object's id goes to `Collided`. This is how the edges are found: the walk
stops at the extent, and this finds the rectangle beyond.

## Areas and entrances

[checked]

- **`$BE18` loads an area** by id from the table at `($8914)`:
  `AreaFlags`, the objects and their count, the conditions, the scale,
  and the values scaled by it; it resets `MinuteCount` and `MinuteSeen`,
  hides three globals (`$87FE`, `$880E`, `$881E`), sets `AreaChanged`
  and `Wipe`, and places the rig (`$CD3B`: five globals shown at the
  area's rig position if `RigPlaced` has one, for areas below 19).
- **`$9D1C` puts the camera at an entrance**: `zx-driller.md` has the
  placement. An id with no object (entrance 0) means the camera crossed
  the edge: x cell 126 becomes 1, 0 becomes 125, else z likewise, y and
  the angles kept.
- **Doorways** are rectangles on walls' faces whose collided script is
  GOTO; the edges are rectangles on the area's boundary planes (ids
  51-54) whose script is GOTO area, 0. The platforms' edges are open on
  some areas (area 5's) and walled on others (area 1's).

## The events and the FCL

`$9B6E` [checked]: if `EventsDue`, the object with id `Collided` (globals
first) runs its script from its type's header length (`$8929`) on; if it
has none and the move was stopped, the bump's sound. Then every global
condition (`($8922)`) and every condition of the area (`($8868)`, read
after any GOTO: the new area's).

`$B320` runs a script [checked]: each instruction is an opcode (bit 7: a
shot's; the others run for a collision or a condition) and its operands,
its length from `$8939`. A test that fails, or an opcode the interpreter
doesn't handle (0 among them), ends the script. As Driller's ZX code has
them:

| Op | | Op | |
|---|---|---|---|
| 1 | score += 24 bits, clamped | `$12` | GOTO area, entrance (`$9D1C`); `Sound` `$0A`; flags `$FFFC` |
| 2 | energy += n, 0-63; below 0 ends the game (3) | `$13` | shield += n; below 0 ends the game (1) |
| 3, 4, 5 | toggle, show, hide an object here | `$10` | destroy (bit 5) and hide |
| 6, 7, 8, `$11` | the same in another area | `$1E`, `$1F` | go on only if shown, if hidden |
| 9, `$0A`, `$14` | variable += 1, −= 1, = n | `$20`, `$21` | the same in another area |
| `$0B` | go on only if the variable is n | `$15` | into the jet or out (swaps energy and shield) |
| `$0C`, `$0D`, `$1D` | set, clear, toggle a bit | `$19` | the area's colours (`$A77A`) |
| `$0E` | go on only if the bit is n | `$1A` | redraw, copy, panel there and then; flags 0 |
| `$0F`, `$1C` | a sound now; after the copy if one's due | `$1B` | wait n frames |

Showing an object sets `GameFlags` bit 2; hiding one in the last draw
list sets `GameFlags2` bit 3 (the renderer's list, `$B492`). A hidden
sensor leaves the interrupt's list.

## The rigs

`$BEFA` [checked, 2026-11-08: `tools/logic/rig.py`; `tests/logic/rigs.txt`,
`rig-win.txt`, `rig-sensor.txt` and the fuzz, which presses D and C].
D (action `$28`) drills and C (`$2A`) collects, only when the key is the
pass's only one; either sets `EventsDue`, and ends the input. Each of
areas 1 to 18 has `RigPlaced` (`$877B`: 0 none, 1 a rig that found no
gas, 2 one that found some, 3 one that found half or more), `RigState`
(`$878D`, its percentage) and `RigPositions` (`$882C`, its corner's
cells). The refusals, in order, each a message for 50 frames and then
`GameFlags2` bit 5 (the panel's message): an area from 19 on (AREA
NEUTRAL); a rig there already, or none to collect (ALREADY PLACED, NO RIG
PLACED); in the jet (NOT IN PROBE); `Energy` below 5 (ENERGY TOO LOW).
The messages are 14 characters each at `$8BF6` on, the panel's two first
(SECTOR CLEARED, GAS BUILD UP), then the rigs', then the end's.

- **Drilling** (`$BF9E`): the rig's corner is the probe's cell less 6 or
  12 on x and z by the yaw's sector (`$BFAA`: it goes in front, 12 cells
  across), on the feet's cell (the eye's less `BodyHeight` − 1). It must
  lie inside the area's extent, on the floor (feet cell 0) or on the top
  of a shown cuboid that holds it with 6 cells to spare each side, and no
  shown object may be in its box (12 by `$16` + 1 by 12 cells), all by the
  signs of bytes (POS UNSUITABLE). Then `Energy` − 5 and the corner kept.
  The gas: the rig's centre's distance from the area's gas (header bytes
  10 and 11, `AreaGas`) is `|dx| + |dz|` by the signs of bytes; the
  percentage is 100 − d · 100 / reach (header byte 12), by the signed
  `$928C` and the divide `$91F1`; none above 0 is NO GAS FOUND
  (`RigPlaced` 1). Else the first such rig of the game picks the yields
  (`GasYields`, `$87A3`: `$88EB` + `SecondFrames` AND 15, a rotation of
  eighteen yields in thousands of cubic feet), the score gains yield ×
  percentage × 10 by an ADDSCORE the routine builds at `$BEF6`, and a rig
  of 50% or more makes `RigPlaced` 3 and counts in `FclVar32`, whose 18th
  ends the game won (`GameOver` 5). Its messages: RIG POSITIONED, "  nn000
  CFT", " nnn% SUCCESS" (the figures written into the messages, leading
  zeros as spaces).
- **Collecting** (`$BF56`): the score loses what the rig scored (yield ×
  percentage × −10: a rig with no gas, whose yields may not be picked yet,
  reads a byte of the ROM and multiplies it by 0), `Energy` − 5, the rig
  gone, `FclVar32` down if it counted; RIG COLLECTED.
- **The redraw** (`$C259`): the rig's parts placed (`$CD3B`), PROCESSING,
  and the redraw, the copy and the panel there and then with `GameFlags`
  `$0404`, sound 5 after the copy (`Sound`), the copy wiping; then the
  messages; then the flags put back as they were and `GameFlags2` bit 5.
  The redraw's sensors' line of sight (`$9841`) walks with `Margin` 0 and
  leaves `Collided` set to what it reached, so a rig set down in a sensor's
  sight can run that object's collided script in the pass's events
  (`tests/logic/rig-sensor.txt`: a shield's loss).
- There is no animation: the rig's five parts stand where the load or the
  redraw put them (two of them only for a rig that found gas).

## The clock

The interrupt (`$BAE6`) counts frames into `Countdown` (`$8FC2`, waits)
and the clock, a second each 50; when a minute ends, it spends a unit of
`Energy` and counts `FclVar30` and `MinuteCount` up, or with no energy
left ends the game (3) [checked]. The input takes the changed
`MinuteCount` as a pass of its own. The global conditions show globals
248-250 at minute 8 and hide them at minute 9, setting `MinuteCount`
back to 0, so the next pass is a minute's too, and its keys do nothing.
The sensors' shots at the shield are the interrupt's too [checked,
2026-11-08: `docs/research/sensors.md`, `tests/logic/sensors.txt`].

## The original's bugs

Both reproduced by the transcription and checked against the original:

- **The runaway walk.** When one axis's crossing point lands exactly on
  the first unit of the current cell of another axis going down, the walk
  crosses that axis too, even when the current cell is already that
  axis's target. The walk is then a cell past the target on that axis and
  never comes back to it, so it runs on along that axis until a face or
  the area's extent stops it, the other coordinates extrapolated along
  the step. The fuzz found a step from (1743, 5123) toward (1985, 5056),
  which met x 1984 at z 5056, thrown down z to the area's wall with x at
  20016, outside the area (`tests/logic/fuzz-1239.txt`).
- **The freeze.** Out there the 8-bit cells wrap (x 20016 is cell 312,
  which the walk takes as 56), so the boundary the walk computes from the
  cell is behind the camera and its crossing points are wild. A move from
  there came to a crossing on no axis (`$A107` with no y to cross), which
  changes nothing, so the walk repeats it for ever and the game hangs
  (`tools/logic/move.py`'s `Freeze`; the checker requires the original to
  hang there too).

And behaviour to keep (not bugs, but easy to smooth over):

- a step stops at the first crossing where it steps up or falls;
- the probe raised off the floor (by a rise in mid-air, or placed there)
  hangs until a step crosses a cell, then falls;
- the margin's push moves every axis it marked, not just the one whose
  face it found;
- the first object a move touches, or lands on, is the one whose collided
  script runs;
- an FCL `SETVAR` on variable 31 swallows the next pass's keys.

## The harness

`tools/logic/oracle.py` runs the original pass by pass from the in-play
snapshot: keys held from `$9825` until the input returns (`$9828`), the
state read when the events are done (`$982B`), then on to the next
pass's top. It holds what's real time: the clock's seconds at 59 before
each pass (00 and 49 frames for a scenario's `tick`), and the sensors'
shots (below). The transcription takes the variables the renderer,
the copy and the interrupt write (`"sync"` in `tools/logic/state.py`)
from the original at each pass's start, and from its end after a pass
that ran the FCL's REDRAW; everything else it carries itself, and every
variable and the whole database must agree after every pass. Every other
byte the original writes inside a pass is a routine's own scratch: the
clock and the frame counters (`$88A3`-`$88AB`, `$8A1D`), the interrupt's
flags (`$8A21`), the divide's sign and remainder (`$92D4`-`$92D6`), and
the sound's and the panel's locals (`$9590`, `$BA1C`) [measured over the
scenarios and a fuzz, comparing all of RAM outside the screen, the view
buffer and the stack]. Since the rigs (2026-11-08) the harness also keeps
every sensor from firing (`SENSOR_SHOTS`: the interrupt's read of the fire
list answers none), as a rig's pass redraws inside itself and waits 200
frames; and a rig's pass took the original's `Collided` as its redraw
leaves it (since 2026-11-10 the transcription runs the sensors' test
inside the pass itself, `tools/logic/sensors.py`'s `inside`, and the
check keeps what it leaves through the sync after the redraw: decision
192), and keeps its own energy, shield and end through that sync. Since the sensors (the same day)
the list is no longer emptied before each pass (hiding a sensor takes it
out of the list as it stands); a scenario's `sensors N` step runs the
original's input, waiting, for a frame and then its interrupt N times
with the shots let fire; and after each pass that redraws in an area with
a sensor, the original is stopped at its sensors' test (`$9841`) as well as
after it, and the transcription's projection and test (on the BBC's
frame) are held to its (`docs/research/sensors.md`, "The checks"). The
transcription's shot is the BBC's view's (`tools/logic/view.py`).
`tests/logic/*.txt` are the scenarios (format in
`tools/logic/scenario.py`); `tools/logic/check.py --fuzz` walks random
keys from random entrances and keeps a failing walk as a scenario.

## What's left

- The renderer's parts the logic calls: the draw list's removal
  (`$B492`). (The shot's pick, the sensors' tests and their shots are
  transcribed, on the BBC's view: `tools/logic/view.py`,
  `tools/logic/sensors.py`.)
- The end of the game (`$9AB7`), a new game (`$9C36`), the demo's
  playback (`$9A27`), the clock (`$BAFA`) and the information screen
  (`$C3DC`) are transcribed since 2026-11-08 (`tools/logic/end.py`,
  `tools/logic/info.py`, `docs/research/end.md`, `docs/research/info.md`);
  its save and load to tape aren't (decision 153).
