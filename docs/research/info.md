# Driller's information screen on the BBC

*2026-11-08. The information screen (I): what the original does (read
from its listing, `make zxdisasm`), its transcription
(`tools/logic/info.py`), the 6502's (`src/logic/info.6502`), the disc's
(`src/info.6502`, `src/live.6502`) and the checks. Addresses written `$`
are the original's.*

## The original

`$C3DC`, action `$29`, I, only alone in the pass's keys:

- the sensors' shots stop (`$8A21` bit 2) and `GameOver` is 6 while it
  shows, so the interrupt keeps no time either;
- 25 frames counted (`Countdown`) while it draws;
- the view's colours black and yellow: `$A77A` with the area's last two
  colours set to 0 and 6 a moment (so `ScreenColours`, the sensors' flash
  counters and `AreaChanged` as any `$A77A` leaves them);
- the view cleared and nine lines of 26 characters printed into it, on
  character rows 1-5, 7, 8, 10 and 11, from its buffer at `$C2B2`, whose
  static parts never change: SECTOR (or AREA from area `$13` on) and the
  name; the rig: NOT REQUIRED (an area), UNPOSITIONED (none), POSITIONED;
  the gas found (the yield of the area's rotation, two digits and 000
  CFT), the share tapped (`RigState`, three digits and %), the gas tapped
  (yield x 10 x share, five digits and CFT), or NONE, ZERO, NONE for a
  rig that found none, or dashes; TOTAL SECTORS: 18; SAFE SECTORS
  (`FclVar32`); the keys. Leading zeros are spaces;
- the 25 frames done, the keys read until one is held (I still held
  counts, so a long press shows it only a moment): S and L save and load
  the game to tape; 1 returns with `GameOver` 6 kept (the next pass's
  input goes to the end: TERMINATED); any other: 11 frames, `$A77A` again
  (the area's colours back), the view wiped back from the buffer, the
  crosshair, `GameOver` 0 and the shots on.

## Transcribed

`tools/logic/info.py`: `begin` (to the key's read), `answer`, `build` (the
text into the original's buffer, so it's compared byte for byte),
`lines`. `tools/logic/passes.py`: the input's `$29` calls `begin`;
`run_pass(info_keys=...)` answers it in the pass, or stops there
(`"info"`) and `info_answered` goes on. The scenario step `info K` is I
alone, answered by K once read; `info` (or I alone) by I held on.

## In 6502

`src/logic/info.6502`: `info_begin` and `logic_go_info` in main RAM
(`LogicMore`), with `info_name` (the clearing and the name, from the
database in `LOGIC_BANK`); the text, the original's words and
`info_build` (the rest of the fields) in section `InfoData`, which the
includer places (the live disc: the front end's bank, after its code;
the check build: main RAM), reached with `INFO_BANK` paged.
`logic_pass` answers 4 while the screen waits for its key.

## On the disc

`src/live.6502`: a pass that answers 4 shows the screen (`lv_info`): its
frame (`live_info`) clears the view and draws the text (`src/info.6502`'s
`info_draw`, in `LogicMore`, the panel's font in the front end's bank)
into the buffer being drawn, in yellow on black, four pixels a character
as the panel's; that buffer's crosshair and lines go with the view, and
neither buffer holds what the rasteriser last drew (`raster_forget`).
The sensors' clock stops while it shows (`sn_clock`), as does the clock
(`GameOver` 6). Its 25 frames are the pass's waits; then any key held or
gone down is the next pass's call (`lv_call` 3, `logic_go_info`), and its
11 frames that one's. The next frame is drawn whole. The BBC's 1 is the
ZX's 1 now (ESCAPE was alone), for ABORT.

## The checks

- **Against the original** (`make logic`): the original runs the info's
  pass with I held to its key's read (`$C5A2`), where its buffer must be
  the transcription's text, then the answering key; every variable after.
  `tests/logic/info.txt`: Amethyst with no rig, I held on, a rig with no
  gas, one with 87%, an area past the sectors, I with another key (no
  screen), and 1, the end and a new game.
- **The 6502** (`make logic6502`): each screen's text in `InfoText`
  against the transcription's, and every variable after its key.
- **The disc** (`make live`): each screen's frame against the model's
  (`tools/mklive.py`'s `info_view` of the transcription's text), byte for
  byte, and the state after its key.

## What's left

- Save and load (decision 153).
- The original wipes the view back in ($AB25, a dissolve in four sweeps);
  the disc draws the next frame whole (decision 193 says why, and
  what a dissolve would take).
