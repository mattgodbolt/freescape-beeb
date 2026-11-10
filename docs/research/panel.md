# Driller's panel below the view

*Track X, 2026-11-01. The live discs (`docs/research/live.md`) show
Driller's instrument panel round the view in place of the text: the Atari
ST's console (decision 8: the ST's colours), cut to MODE 2's 128 pixels at
build time (`tools/mkpanel.py`), its instruments drawn over it from the
logic's variables (`src/panel.6502`). `tools/model/panel.py` is the
panel's specification: its font, its fields, the values the original's
panel shows and how they become cells, and the screen it makes of them.
Figures are in the dated measurements at the end.*

## Running it

```sh
make panel-data    # build/panel/: the picture and the tables, with previews (picture.png, sample.png)
make panel         # panel_values on the live disc against the model, over edge values and a fuzz
make live          # the live discs' check, which holds the panel to the model at every flip and pass
make panel-shots   # shots/panel_{start,walk,jet}.png and _pal.png: the live disc in play, RGB and PAL
```

## What it shows, and where

The original's panel routine (`$B72B`, `docs/research/zx-logic.md`) shows,
by the flags a pass sets: the score, the area's name, a message about the
area's gas, the step, the turn, the position, a compass for the heading
and one for the pitch, the energy and the shield, the vehicle (the
probe's extension, or the jet) and whether it's shooting mode. The ST
shows the same, on its console: the bars bottom left with their labels,
the compass and a pitch strip in a cluster above them, the step and turn
under the compass, the vehicle's picture in a monitor beside it, the score
in a row of holes top right, the area's name and message in a box bottom
right; the ST puts the position over the view's top left. The panel shows
each where the ST has it, but the position, which goes where the ST's
save and load buttons were:

| Field | What | From ($B72B's) |
|---|---|---|
| score | seven digits, leading zeros, the low seven of the 24 bits | `Score` |
| message | the area's gas: none past area 18, the rig's sector cleared, or building up; the game's end | `AreaId`, `RigPlaced`, the disc's end |
| name | the area's, centred | the area shown (the view's) |
| shield, energy | bars of six cells, `(min(v, 63) 3 + 7) >> 3` pixels lit, the ST's colours | `Shield`, `Energy` |
| heading | a tape a pixel to a 5° step, N E S W a quarter apart, three cells | `Yaw` (not turned in areas 13 and 18, as the original's) |
| pitch | a tape down, two lines to a step, the angle from level every 30°, ticks every step | `Pitch` |
| step | three digits | `Step` |
| turn | two digits, degrees, and a degree sign | `Turn` × 5 |
| X, Y, Z | four digits each, over the area's scale: x, z and y, as the ZX and the ST order them | `PlayerX`, `PlayerZ`, `PlayerY`, `AreaScale` |
| vehicle | the ST's picture of the jet or the probe, and a name: JET, PROBE, EXT 1 to 3 | `InJet`, `ExtLevel` |
| lights | the crosshair up; shooting mode | `CrossOn`, `ShootMode` |
| clock | hh:mm:ss, the original's text, above the view at the right, as the ZX's (`$CFC8`) and the ST's | `Clock` (`$88A4`, the interrupt's: `$BB86`) |
| FPS | the frames a second, the disc's own measure | `live_figures` |

The row above the view carries the credit, "DRILLER (C) INCENTIVE 1987",
at its left and the clock at its right (decision 190), and the strip along
the panel's foot "TECH DEMO" beside the frames a second (decision 6). With the free camera the message is the
entrance (and DEMO while the demo turns), and the position, heading and
pitch are the camera's.

## The redesign

The ST's console is 320 pixels by 200 lines round a 248 by 102 view; the
BBC's screen is 128 MODE 2 pixels by 192 lines round a 104 by 104 view.
A MODE 2 pixel is two of the ST's across (both are pixels of a PAL line's
52 microseconds, at 4 and 8 MHz), and a line is a line, so the console
can't be scaled: at two ST pixels a MODE 2 pixel it is 160 wide. It is
cut instead (`tools/mkpanel.py`'s `BANDS`): the panel's upper band, the
instruments, the vehicle's monitor and the score, drops the four arrows
the mouse clicks to move; its lower band, the bars and the message box,
drops the information button and what's round it. Each MODE 2 pixel is the
brighter of the two ST pixels it covers, so thin lines keep. The frames
beside the view are the ST's nearest it (black, and the view's edge in
yellow green); the row above the view is black, for the credit; the
panel's top two lines, the bevel's edge, go.

Over the cut (`FILLS`, `LABELS`): black boxes for the score (the ST's
empty holes go: the ST draws the score over them), for the position
(where the save and load buttons were), for the step and turn (under the
compass, one above the other: the ST's two small boxes side by side hold
its own tiny figures, too narrow for the panel's font) and for the pitch's
tape (its bar beside it, its middle marked); the heading's tape on one
purple, its middle marked; the labels in the panel's font, in white (the
ST's are red, which through PAL blurs into the console: red has a third
of white's luma).

**The colours** are the ST's, each of the console's 16 a MODE 2 pattern
chosen as the colour study chooses a face's (`tools/colour/patterns.py`,
from solid colours and pairs) for the build's display (decision 8b: PAL
by default), so the console's deep reds are red and black dithers, as
dark as PAL shows them. Text is solid: yellow for the values, as the ST's
font, white for the labels. The bars are in the colours the ST game draws
them over its console (brown edges to a yellow middle, the first cell red,
as ScummVM's `drawAmigaAtariSTUI` has them).

**The font** (`tools/model/panel.py`'s `FONT`) is the panel's own: three
pixels by five lines, a pixel's gap, in a cell of four pixels, so 32
characters across, as the ZX's panel font gives its 256 pixels; MODE 2's
pixels are twice as wide as tall, so a glyph is about square. Capitals,
figures and a few signs. The credit and labels close it up where a glyph
is narrower (I, the stops, the brackets, the space), so the credit fits a
line.

**The vehicle**: the ST shows one of five pictures (the jet, then the
probe at each extension). Halved across, the probe's four differ only in
small marks and their names, which at MODE 2's pixels are a blur, so the
panel keeps two pictures, the jet's and the probe's (tiles where they
differ: below), and names the vehicle under them in its font.

## How it's drawn

- **The picture**: everything outside the view, the same in both buffers
  always (decision 21). `tools/mkpanel.py` packs it (runs given or copied
  from up to 256 bytes back; a dither repeats every four bytes down a
  column) into the part `PANEL`, which the loader puts in the transform's
  cache in main RAM (nothing's there until `clear_work`); `panel_init`
  unpacks it into main RAM's buffer, copies that to shadow RAM's a page at
  a time through RasterIn's, and is done before `clear_work`.
- **Cells** over it. A glyph cell is two bytes across and its table's
  lines down, inside a character row (`tools/mkpanel.py` checks), so its
  lines are a byte apart: each line a nibble of the glyph, each lit pixel
  the cell's ink for the line, else its paper (the picture under it: one
  byte a line, which the fills make so), as `paper EOR ((paper EOR ink)
  AND mask)`, the masks by nibble from two tables. A tile is a byte across
  and a character row down, its eight bytes as they are: the vehicle's
  pictures. Fields of cells, in the model's order (`flat()`): their
  places, kinds (table, ink and paper by line) and the tables are the
  build's (`build/panel/panel.6502`).
- **When**: `panel_values` sets every field from the logic's variables
  after each pass that ran and as an area is entered (where the logic's
  objects' flags are given to the renderer: `lv_pass`, `lv_switched`),
  and with the free camera as each frame's camera changes. A number the
  same as last time, the vehicle and the area's name leave their cells as
  they are (`panel_cache`). The frames a second come from `live_figures`.
- **Drawing**, as the text was: `panel_set` marks a cell wanted, and
  `panel_sync`, every loop, draws each cell not shown as wanted into both
  buffers, a cell begun only while User VIA T1's high byte says the beam
  is past the screen's last line or in the view's lines (`PANEL_T1_TOP`)
  with `PANEL_CELL_US` to spare before `FLIP_LINE` and the panel's top
  row: so no flip finds a cell half drawn and the beam reaches the shown
  buffer's copy only whole. A new area's name and message are drawn
  before its first frame is handed over (`panel_wait`); the panel's
  values are set before the area's conversion, which draws cells as the
  beam allows between its records (`src/area.6502`'s `AREA_PANEL`), so
  little is left to wait for by then.
- **The window, widened** (2026-11-06, the eleventh round): it was the
  view's lines alone, about a third of a field; past the screen's last line
  the beam meets the panel's rows again only after `FLIP_LINE`, so the
  window now opens there, about two thirds of a field. The vertical sync's
  interrupt comes inside it, far from its end, so it only delays a cell
  begun well before (`tools/livecheck.mjs` leaves the interrupt's cycles
  out of a cell's own, and holds the window as begun and done before
  `FLIP_LINE` without passing it). A glyph cell writes the buffer selected
  as it makes each line and copies the lines into the other, counting
  down.
- **The clock's cells**, above the view (2026-11-09, decision 190): the
  beam scans their row as the field begins, inside that window, so they're
  begun only between the screen's last line and a cell's time before the
  vertical sync's flag (`PANEL_T1_ROW0`), done before the sync's interrupt
  and long before the beam meets the row again. They're the last cells
  (`PANEL_ABOVE` on, after the vehicle's tiles), and a frame's
  `panel_catch_up` waits only for those before them, so no frame waits for
  the clock. Its cells are set from the logic's text (`panel_clock`) with
  every pass's values, and by `lv_clock` when a second has gone.

## The check

- **`make live`** (`tools/livecheck.mjs`), on both discs, besides all it
  held before: at every flip the screen outside the view, both buffers
  alike, is the model's render of the cells `panel_shown` says are drawn
  (each different set rendered once, after the run, by `tools/mkpanel.py
  --check`); every time `panel_values` runs, the cells it wants are the
  model's for the transcription's state (with the free camera, its camera
  and its own variables), in order, but the frames a second; every frame
  handed over wants and shows its area's name and its message (with the
  free camera, its entrance); each cell is drawn wholly inside one field's
  window, before `FLIP_LINE`, within `PANEL_CELL_US`; settled means the
  panel drawn too. The scenarios include `tests/logic/fcl.txt` (the score,
  energy and shield to their limits, the jet), `jet.txt` and the clock's
  `ticks.txt` and `minutes.txt`, and the free disc's check
  sets the jet and a seven-digit score and steps, so their pictures and
  digits are drawn and rendered.
- **`make panel`** (`tools/panelcheck.mjs`): `panel_values` on the live
  disc, called from a stub with the logic's variables poked, over every
  bar length and past it, each digit's edges, every scale, yaw, pitch and
  area id, the jet and every extension, every name and the game's end,
  then a seeded fuzz; the cells against the model's.

## Memory

| Where | What |
|---|---|
| `BANK_DATA`, `PanelData` (`PDATA`), after `LiveData` | the panel's code and tables: where the text's widened MOS font (`TextRAM`) was |
| main RAM, `LIVE` | `panel_set`, so code in any bank sets a cell |
| `Work` | `panel_want`, `panel_shown`, the cache and the drawing's lines |
| main RAM's `&3000` (`PANEL_LOAD`), from the loader to `clear_work` | the packed picture (`PanelPack`, `PANEL`) |

`src/live.6502` ASSERTs that the packed picture lies inside the cache
`clear_work` clears, and the page it's copied through inside RasterIn.
The text (`src/text.6502`) stays the slideshow's.

## Decisions to record

- **The panel is the ST's console, cut to 128 pixels** (proposed
  2026-11-01; follows decisions 8 and 43): its instruments where the ST
  has them, the mouse's buttons dropped (the four arrows, the information
  button, save and load, where the position goes), each MODE 2 pixel the
  brighter of two ST pixels, the console's colours as patterns for the
  build's display; the values and labels in a font of the panel's own, the
  labels white. Why: the ST's look and instruments in a screen 4/5 as wide
  at half the resolution; scaling the ST's art would lose its text and
  shapes.
- **What it shows**: the original's panel (`$B72B`) less its clock (the
  interrupt's countdown, which the disc didn't keep; since 2026-11-09 it
  shows, decision 190), its seismograph,
  its quit indicator and the rig's animation (the rigs aren't in the
  disc's logic yet); the vehicle as two pictures and a name rather than
  five pictures. All fields are set from the logic's variables after each
  pass (and at an area's entry) rather than by the pass's flags, which
  shows the same.
- **The text goes from the live discs**: the frames a second stay on the
  screen (with "TECH DEMO" and the credit); the fields a frame and the
  halves' cycles leave it (the check times the halves itself: decision
  180 took the disc's User VIA T2 timing out), as do the keys' lines (the
  README has the keys).
- **The packed picture is loaded once into the transform's cache's
  memory** and unpacked into both buffers at the start (proposed
  2026-11-01; amends decision 40's map): `PanelData` takes the text's
  font's place in `BANK_DATA`.

## What's left

- The rig's animation in its slot (the ST's; the ZX has none). The end's
  messages by cause show in the message line till a new game, and area
  127's name the safe sectors, since 2026-11-08 (`docs/research/end.md`;
  every area's name is the original's twelve characters with a space each
  side, which is the centred name for every area but 127's). The rigs' messages show in the message line since
  2026-11-08 (decision 121; `src/live.6502`'s `lv_messages`), each its
  turn, in place of the area's message; the font has a `%` for them.
- The key lights (`hook_key_lights`): the ST's up and down buttons could
  light for R and F.
- A display switch would want the panel's patterns for the other display
  too (it's chosen at build time).
- The lights are small; a player may want them bigger.

## Measurements

### The first panel (2026-11-01, track X)

`make live`, the logic's disc with the scenarios and `fcl`, and the free
disc; `make panel`.

- **Per pass**: `panel_values` took 4,535 / 6,574 / 9,255 cycles (median /
  p90 / most) over the logic disc's 436 calls; called with every value new
  (`make panel`), 12,336 / 14,490 / 17,982 with the stub. Each glyph cell
  drawn into both buffers 826 / 831 / 1,099 cycles (3,279 cells; the most
  is the pitch's eight-line cells), each tile 395 / 395 / 409 (the free
  disc's 87); `PANEL_CELL_US` is 600.
- **Per frame**: a loop with nothing new for the panel compares one byte.
  The logic disc's frames, flip to flip, 3 / 6.11 / 23.01 fields (median /
  p90 / most) against 3 / 6 / 22.71 with the text before (the same check,
  less `fcl`); "the rest" of a frame (the logic, the animation, the panel,
  the wait for the flip) 0.18 / 0.53 / 8.14 against 0.18 / 0.42 / 8.27; a
  walking frame's 0.17 / 0.38 / 6.73 against 0.18 / 0.38 / 6.63.
- **Memory**: `PanelData` 3,591 bytes (the font it replaces was 3,040);
  `BANK_DATA` free, `area_conv_end` to `&C000`, 997 bytes against 848
  before (the live disc's own copy of the names goes too); `LIVE` 403
  bytes shorter (the text's code), so `ObjMore`'s room to `&3000` is 582
  bytes against 326; `Work` 64 bytes shorter; the packed picture 2,060
  bytes, in the cache's 2,304 until `clear_work`.
- **Mutations caught**, each on its own: one buffer drawn (the buffers
  differ at a flip); the masks swapped (the render); the beam's window's
  lower bound dropped (cells drawn across `FLIP_LINE`); the compass turned
  in areas 13 and 18 (the tour's values); the bars' rounding by one
  (`make panel`: play never reaches those values). The check's first run
  found a fault: `panel_divide` counted in X, so a position over a scale
  of 4 went into the score's cells.
