# Driller's guard sensors on the BBC

*2026-11-08. The sensors' layer: what the original does (read from its
listing, `make zxdisasm`), its transcription (`tools/logic/sensors.py`),
the disc's (`src/sensors.6502`), and the checks. Addresses written `$` are
the original's. Figures are the journal's (2026-11-08, "the laser and the
sensors").*

## The original

A sensor is an object of type 2: a point (its record's cell), with an
interval in frames (byte `$0A`), a range in world units (`$0B`, `$0C`) and
a mask of the sides it watches (`$0D`). Driller's areas have up to four.

**The lists** (`SensorList`, `$8A24` on): the count the redraw found
(`$8A24`), the interrupt's (`$8A25`), the redraw's list (`$8A26`) and the
interrupt's (`$8A44`), five entries of six bytes: the id, the interval, a
frame counter, a state (0 off, 1 on the screen, 2 in range off it) and the
point on the screen, as the crosshair's (x from 1, y up).

**The redraw's projection** (`$6B33`, `$6B7C`, `$7592`), when the pass
re-projects (`GameFlags` bit 2): every type-2 object of the area's records
and the globals', hidden or not, takes the next entry (its id and
interval). Hidden, it's off. Else the projection's which-side bits (the
camera below each axis's low face, above its high one, by the 16-bit
differences of the record's box and the camera) must meet the mask, and
|x| + |y| + |z| of its point less the camera, summed in 16 bits, must be
short of its range, else it's off. In range, it's projected: on the screen
it's state 1 at its point (and drawn, a pixel); off it, state 2.

**The line of sight** (`$9841`), after every redraw (`GameFlags` bit 2 or
`GameFlags2` bit 3): for each entry the redraw found, state 1 keeps only if
the shot's pick (`$B153`) at its point, with `Collided` cleared first, hits
it; state 2 keeps only if a walk (`$9F42`) from the camera to its cell's
corner, as the jet (`InJet` 1) with `Margin` 0, so the walk only walks,
gets there. The pick and the walk leave `Collided`, `FoundId` and the
walk's scratch as they end (the rigs' quirk: `tests/logic/rig-sensor.txt`).
Then the interrupt's count is the redraw's, each entry's counter is the
interrupt's old list's at the same place (2 for one that's 0 or 1, which
the interrupt is about to use), and the redraw's list is copied over the
interrupt's. (Then the screen's colours if the area changed, `$A77A`,
which puts every counter of the interrupt's list back to 2.)

**The shots** (the interrupt, `$BB93`-`$BC94`), every frame, but not while
the test runs (`$8A21` bit 2) unless a shot shows (bit 0): each entry of
the interrupt's list counts its frame counter up, back to 0 at its
interval (or past 255). One that's on fires at 0: the border to the
screen's second colour (`ScreenColours`' second byte), for state 1 four
lines (EOR) from its point to (cx ∓ 3, 0) and (cx ± 3, 2 cy), sound 2
played there in the interrupt (the game held for it), and `Shield` down a
unit (its bar with it, `PanelShield`), or with none left `GameOver` 1
(SHIELD OUT). A frame later the lines come off (state 1, counter 1) and
the border back (counter 1 or 2). The game's end (`$9AB7`) and the
information screen set bit 2 for good: no more shots.

**Hiding a sensor** (`$B467`, in the FCL's hide) takes its entry in the
interrupt's list off, and the redraw's at the same place.

## Transcribed

`tools/logic/sensors.py`: `project` and `sight` (with `redraw`, which
runs them as the redraw does), `tick` (the interrupt's frame), `off`
(the FCL's `_show_hide` calls it). What's on the screen is the BBC's
frame's (decision 132): `tools/logic/view.py` renders the model's frame of
the state (`frame`), a sensor is on the screen if that frame drew its
pixel, and its point is that pixel as the crosshair's; the pick at it is
the BBC's (`tools/model/pick.py`, decision 131).

## On the disc

`src/sensors.6502`, `src/live.6502`:

- **The redraw's part** (`sn_redraw`: `sn_project`, `sn_sight`, in shadow
  RAM with the rigs' code, run with ACCCON's X set): after a pass that
  redraws, if the area or the globals have a sensor (`sn_any`), once the
  frame of the pass's end is drawn: in `live_idle`, the loop that finds
  nothing new to draw, with no pass's frames showing; and the next pass
  waits for it (`sn_due`), as the original's comes after its test. With no
  sensor there, at once (the lists' copy alone). A sensor's pixel is its
  face's in the draw list (`lv_spot`), the pick at it `lv_pick`, the walk
  the logic's own `move`. The screen's colours after an area's change wait
  for the test too, as the original takes them after it.
- **The shots** (`sn_clock`, each loop, in `BANK_DATA`): the fields counted
  since the last loop, each a frame of the interrupt's (`sn_field`)
  (decision 133). A shot asks for sound 2 from the main loop (`snd_ask`,
  which the interrupt couldn't: it may wait), takes the unit of `Shield`
  or ends the game, and the panel's values are set again for the shield's
  bar. A sensor on the screen's lines show for `SENSOR_LINES` fields (sound
  2's and the frame the original takes them off in, decision 134), in
  frames of their own as the laser's (`sl_eor`, each buffer's set
  `sb_*`). No border: the BBC's is blank (decision 133). None once the
  game's over (`lv_over`).
- **Hiding a sensor**: the logic's own (`src/logic/fcl.6502`'s
  `show_hide`), then `hook_sensor_off`.

## The checks

- **Against the original** (`make logic`): the oracle (`tools/logic/
  oracle.py`) keeps the interrupt's read of its list answering none, so no
  shot lands in a pass, but no longer empties the list before each pass;
  a scenario's `sensors N` step is time going by between passes, with the
  sensors let fire: the original's input entered with no key (a frame of
  it), then its interrupt run N times; the transcription takes the
  original's lists, waits as its input does (`passes.waiting`) and ticks N
  times, and every variable must agree after. After every pass that
  redraws in an area with a sensor, the original is run to its test
  (`$9841`) and on to the next pass: the transcription's projection (from
  the BBC's frame) must have the original's count, ids and intervals, and
  off where the original has off; its test's lists and `Collided` the
  original's, but an entry on the screen in one view and off it in the
  other (the projections differ by up to a pixel at the view's edges),
  which is counted. `tests/logic/sensors.txt`: area 3's three, off the
  screen, walked to; area 28's four, on it, picked; shots at the shield.
  The fuzz checks every redraw it makes in a sensor's area.
- **Against the model** (`make live`): the trace's sight after each pass
  that redraws (`tools/mklive.py --trace`'s "then"), and its "sensors"
  steps, the shots: `tools/livecheck.mjs` holds the disc's clock of them
  (`sn_hold`) and gives it each step's fields (`sn_more`) once the disc's
  input waits; every variable must be the transcription's after, and the
  sounds asked for its; every frame with a shot's lines is the model's
  render with them (`tools/mklive.py`'s `slines`).

## What's left

- A rig's redraw and the FCL's `REDRAW` run the test inside their pass on
  the original; the disc runs it after a pass that redraws only, so after
  those it keeps the lists it had (`tests/logic/rig-sensor.txt` still
  takes the original's `Collided` there).
- The border's flash (decision 133).
- The test's walk to a sensor in range far off can hold the next pass for
  several fields (the journal's figures), as the original's holds its
  game.
