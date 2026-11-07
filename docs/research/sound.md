# Driller's sounds, and the BBC's

*Track S, 2026-11-06. What Driller's ZX code (the retail tape, decision 1)
plays and when, read from the annotated listing (`make zxdisasm`) and
measured on the original running headless (`tools/zx.py`); then the
SN76489's version, made from those measurements at build time
(`tools/mksound.py`) and played by the vertical sync's interrupt
(`src/sound.6502`). Addresses written `$` are the original's.*

## Running it

```sh
make sound      # the scripts (build/sound/), then tools/soundcheck.mjs on the live disc
node tools/soundcheck.mjs --disc build/live.ssd --sound build/sound/sound.json --log build/sound/check.json
.venv/bin/python -I tools/mksound.py build/zx/driller.z80 build/sound   # the scripts alone
```

`build/sound/sound.json` has every sound's measured ticks, its segments
and its bytes.

## The original

### How it plays a sound

`$9574` plays sound A, 1 to 21: it looks up the routine in the table at
`$954A` (a word a sound, A − 1 its index), plants the address in its own
`CALL` (`$958F`), turns interrupts off, calls it, and turns them on again,
except for sound 2, which the interrupt itself plays (`$BC6C`), so they
stay off for its `RETI`. Every routine is a timing loop toggling the
beeper, port `&FE`'s bit 4, with the border's colour from `$886A` (sound
2's from `$886B`) in bits 0-2. So **the game stops while a sound plays**:
nothing moves, the logic waits, and with interrupts off the clock
(`$BAE6`'s seconds and minutes) and the sensors' timing stand still.

The 48K tape the project uses has no other sound: no AY code, no tune.
The game's start beeps through the controls' menu (`$C9C6`: sound 6 for
each choice) and the protection (`$CB7A`: sound 6 for a right word, 17 for
a wrong one), neither of which the disc has.

### The 21 sounds

What each routine's code does (its parameters are the original's bytes);
"ROM beeper" is `$9768`, the Spectrum ROM's `BEEPER` loop copied, HL the
pitch (437,500 / (HL + 30) Hz) and DE + 1 the cycles. A loop of "beeps of
DE 1" sounds three of its half-periods and a short pulse each call, so its
pitch is two thirds of the ROM's formula.

| Sound | Routine | What the code does |
|---|---|---|
| 1 | `$95A1` | 96 cycles of a pulse whose length grows by 9 each cycle, wrapping at 256: a buzzing saw, rising |
| 2 | `$95A9` | the same, 24 cycles, border from `$886B` |
| 3 | `$95D2` | ROM beeper: HL `$7A6` for 12 cycles, then `$93C` for 10: two notes, falling |
| 4 | `$95E5` | ROM beeper: HL `$7A6` for 12, then `$66A` for 14: two notes, rising |
| 5, 10 | `$9653` | 8 times: beeps of DE 6 with HL 0 to 250 in steps of 50: a fast chirp, repeated |
| 6 | `$95F8` | ROM beeper: HL `$1F0` for 41 cycles: one high note |
| 7 | `$9602` | beeps of DE 1, HL 0 to `$C00` in steps of 20: a long fall |
| 8 | `$961C` | 8 sweeps of a 256-step pulse train, the pulse fixed and the gap shrinking: rising |
| 9 | `$963A` | half-periods of 256 down to 1 loop counts: a rise to inaudible |
| 11 | `$9673` | 1,536 cycles of a pulse growing by 1 each cycle, wrapping at 256: six slow saws |
| 12 | `$9696` | 256 cycles, the pulse growing as the gap shrinks |
| 13 | `$96B9` | 232 half-periods from a chaotic sequence: noise |
| 14 | `$96E4` | half-periods of 1 up to 255 loop counts: a fall |
| 15 | `$96FD` | 768 cycles, the high half shrinking as the low grows: one pitch, its pulse's width sweeping |
| 16, 18 | `$95A0` | nothing: a `RET` |
| 17 | `$971D` | ROM beeper: HL `$1A02` for 9 cycles, then `$2707` for 18: two low notes |
| 19 | `$9730` | ROM beeper: HL `$149E` for 4 cycles: a low bump |
| 20 | `$973A` | beeps of DE 1, HL 0 to `$1900` in steps of 20: a very long fall |
| 21 | `$9754` | beeps of DE 1, HL `$300` down to 0 in steps of 10: a rise |

### When the logic plays them

| Where | Sound | When |
|---|---|---|
| `$AA89` (fire, `$A95C`) | 1 | between drawing the laser's lines and erasing them |
| `$A97F` (SPACE) | `$13` (19) | shooting mode in or out |
| `$9BBB` (the events) | `$13` (19) | the collided object has no script and the move was stopped: the bump; after the copy if one's due |
| `$B60E` (FCL `$0F` SOUND) | n | now |
| FCL `$1C` SYNCSND | n | after the copy if one's due, else now |
| FCL `$12` GOTO | 10 | after the copy (`Sound`) |
| `$9DCF` (a crossing) | 4, 3 | the probe climbs, falls: after the copy (`Sound`) |
| `$9BF7`, `$AB25` (the copy, the wipe) | `Sound` | after the pass's redraw (`$9807`: only if `GameFlags` bit 2 or `GameFlags2` bit 3), and FCL REDRAW's copy at once; then `Sound` is cleared |
| `$BC6C` (the interrupt) | 2 | a sensor fires at the player |
| `$9AFF`, `$9B64` (the game's end) | `$14` (20), then 6 | the end's message (20 unless `GameOver` is 5), then the new game |

"After the copy if one's due" is `GameFlags` bit 2 or `GameFlags2` bit 3:
the pass will redraw, so the sound waits in `Sound` (`$8A1F`) for the
redraw to show. The database's scripts use SOUND with 5 to 19 and 21 and
SYNCSND with 5 to 10, 12 to 15 and 21; most are shots' (the targets the
laser hits), the rest collisions and the area's and global conditions
(global condition 0's SOUND 11 at the minute's turn, for one).

### The key table

Driller's ZX key table (`docs/research/zx-logic.md`, "The keys") has no
key for the sound. ScummVM's "toggle sound" is its own. So the disc has
none either.

### The other versions

- **No BBC Freescape exists** (`docs/research/freescape.md`).
- **The Atari ST** plays 25 digitised samples (ScummVM's `games/driller/
  atari.cpp` and `sound/fx.cpp`: `loadSoundsFx`, 16-bit raw PCM). The ST's
  colours and panel are the disc's (decisions 8 and 47), but samples are
  beyond the SN76489 short of using its volume as a DAC, a CPU's whole
  attention at any useful rate.
- **The Amstrad CPC** plays them on its AY-3-8912 at 1MHz, from a table of
  7-byte definitions by the same 1-based numbers, with volume and pitch
  envelopes (ScummVM's `sound/cpc.cpp`, from a disassembly of
  `DRILL.BIN`). An AY's period at 1MHz is half the SN76489's at 4MHz for
  the same note, so those would port nearly register for register
  (decision 113).

## The BBC's

### The chip

The SN76489: three square-wave tones, 10-bit periods (f = 125,000 / N Hz,
so 122Hz to 125kHz), and a noise channel, white or periodic, clocked at
one of three fixed rates or by tone 2's; each with 16 attenuations, 2dB
apart. It's written through the System VIA: the byte on port A, then the
addressable latch's bit 0 (the write enable) low for at least 8us, then
high. The vertical sync's interrupt leaves port A an output after reading
the keys (`src/input.6502`), and nothing else writes it.

### From the beeper to the chip (`tools/mksound.py`)

The build runs each of the 21 routines on the ZX snapshot (`$9574` with A
the sound), logging the beeper's level to the T-state with the 48K's
contention, and cuts the result into ticks of 69,888 T-states: a ZX frame
and a BBC field alike (312 lines of 64us both). It samples the level every
28 T-states, the SN76489's period unit (3.5MHz / 125kHz), so a period in
samples is the chip's register. In each tick:

- the waveform's own period, by YIN's difference function (the cycle the
  beeper repeats, however its loop shapes it: a ROM beeper's three
  half-periods and a pulse, a pulse train, a chirp);
- of that period's harmonics, the strongest is the tone (the fundamental
  for a square or a pulse train; a high one for the chirps of sounds 5 and
  10, whose 70Hz repetition carries little of their sound), and its
  strength against a square wave's fundamental is the attenuation, so a
  narrow pulse plays quieter, and sound 15's sweeping pulse width becomes
  a swell and fade at one pitch;
- a period past the tone's 10 bits (under 122Hz: sounds 17, 19 and the
  ends of 7 and 20) plays as periodic noise, whose output is a fifteenth
  of tone 2's frequency, at the same pitch;
- a tick with no period to be found (a sweep past what the beeper can
  sound, or the sound ending early in it) holds the last period found;
- a sound whose ticks are mostly aperiodic (sound 13 alone) is white noise,
  clocked by tone 2 so its output changes as often as the beeper's did.

Where the ROM beeper holds a note (sounds 3, 4, 6, 17 and 19), the measure
gives the formula's pitch to the chip's nearest period: 220 and 183Hz,
220 and 262Hz, 833Hz, 66 and 44Hz, 83Hz.

Each sound's ticks are then fitted with segments: some ticks of one mode,
the period and the attenuation each a straight line (12.4 and 4.4 fixed
point), as long as every tick stays within a 64th of the measured period
(a quarter of a semitone) and a step of its attenuation. The beeper's own
sweeps are straight lines in its loop counts, which are periods, so most
sounds take a few segments; the build plays every script back on the model
and requires the fitted ticks. Sounds 5 and 10, one routine, share a
script, as do 16 and 18, which are empty.

### The driver (`src/sound.6502`, `tools/model/sound.py`)

- **A tick** (`snd_tick`, from the vertical sync's interrupt after the
  keys): the segment's next tick, or its next segment (`snd_segment`), or
  the next sound's first; tone 2 plays tones and clocks the noise, the
  noise plays the periodic and white noise, tones 0 and 1 stay silent.
  Only a register that differs from what was last written is written, in a
  fixed order: tone 2's period (its latch byte, then its high six bits),
  the noise's control (only as the mode changes: writing it restarts the
  noise's shift register), tone 2's attenuation, the noise's.
- **Asking** (`snd_ask`, the logic's `hook_sound`): the sound goes into
  `snd_next`, which the driver takes as the one playing ends, so sounds
  follow one another without a gap, in the order asked, each whole, as the
  original plays them. If one is already waiting, the logic waits for it to
  be taken (decision 110). After a pass, `lv_copy_sound` asks for `Sound`
  by the original's rule for its copy; the FCL's REDRAW (`lv_hook_redraw`)
  asks for it at once and clears it, as the copy there does.
- **Where it is** (decision 111): `snd_ask` and `snd_tick` in main RAM below
  `&3000` (`LIVE`), with the segment's state and the chip's last bytes in
  zero page and the queue in `Work`; `snd_segment` in HAZEL (`SCODE`, after
  `ObjWork`); the scripts (`SoundData`, `SDATA`) in shadow RAM past the
  slanted faces' memo, which `snd_segment` reads with ACCCON's X set and
  put back. The loader puts the scripts in main RAM at the same addresses;
  `sound_init` (in `BANK_DATA`, from `start`) silences the chip and copies
  them across before `clear_work` clears main RAM there.
- **Its cost**: no cycle of the frame loop's; the interrupt's, a tick's
  writes (each the VIA's 1MHz accesses and the write enable's hold) and a
  segment's start now and then (measured below).

### The checks

- `tools/soundcheck.mjs` (`make sound`, one of `make check`'s): the live
  disc booted on jsbeeb, every sound asked for alone, then a queue of them
  each asked as the one before is taken (tones into noise and back, the
  empty ones among them); every byte the chip took (jsbeeb's instrumented
  SN76489 takes one only if the write enable was low long enough), tick by
  tick, against the model given the same asks, and `sound_init`'s writes.
- `tools/livecheck.mjs`: over the whole run, each pass's sounds asked for
  (the hook's, then the copy's) against the transcription's
  (`tools/mklive.py --trace`'s "sounds", with the disc's REDRAW), and every
  byte the chip took against the model given the asks as they came.
- `tools/mksound.py`: every script, played on the model, gives its fitted
  ticks.

What isn't checked by a machine: how close the SN76489's sound is to the
beeper's. The measure's choices are in the list above; the scripts can be
heard in jsbeeb (`make run`, then a pass that sounds: walk into a wall,
SPACE, climb).

## Decisions to record

Proposed in `docs/decisions.md`, 110-113.

## What's left

- The interrupt's sound 2, when the sensors' shots come (it can't wait:
  it would take the place of one waiting).
- The game's end's sounds (20, then 6), with the game's end.
- The laser: the original draws it, plays sound 1, erases it; the disc
  plays sound 1 as the hook asks, and the laser layer decides when the
  lines show.
- Whether the logic should wait (decision 110), and whether the CPC's
  sounds would serve better (decision 113): Matt's.

## Measurements (2026-11-06, track S)

The original's lengths in fields (the ZX's frames), and the scripts made
from them (`build/sound/sound.json`):

| Sound | Fields | Ticks | The SN76489 plays | Attenuation | Segments |
|---|---|---|---|---|---|
| 1 | 9.45 | 9 | tone, 345-1289Hz | 1-9 | 5 |
| 2 | 2.22 | 2 | tone, 430-1289Hz | 1-9 | 1 |
| 3 | 5.73 | 6 | tone, 220 then 183Hz | 0-1 | 2 |
| 4 | 5.63 | 6 | tone, 220 then 262Hz | 0-1 | 2 |
| 5, 10 | 5.79 | 6 | tone, 1582-1953Hz | 6 | 3 |
| 6 | 2.51 | 3 | tone, 833Hz | 0-3 | 2 |
| 7 | 42.11 | 42 | tone falling to periodic noise, 1147-95Hz | 1-8 | 5 |
| 8 | 59.91 | 60 | tone, 977-5682Hz | 5-12 | 24 |
| 9 | 12.47 | 12 | tone, 532-2660Hz | 0-12 | 3 |
| 11 | 156.57 | 157 | tone, 466-519Hz | 0-13 | 18 |
| 12 | 20.03 | 20 | tone, 472-969Hz | 0-7 | 3 |
| 13 | 7.26 | 7 | white noise, clocked 2778-3378Hz | 0 | 3 |
| 14 | 12.37 | 12 | tone, 541-3049Hz | 0-9 | 4 |
| 15 | 37.44 | 37 | tone, 1033Hz (and quiet partials) | 0-13 | 10 |
| 16, 18 | 0 | 0 | nothing | | 0 |
| 17 | 28.51 | 29 | periodic noise, 66 then 44Hz (a tick between at 74 and 37) | 0-1 | 3 |
| 19 | 2.74 | 3 | periodic noise, 83Hz | 0 | 1 |
| 20 | 178.71 | 179 | tone falling to periodic noise, 1147-45Hz | 1-8 | 8 |
| 21 | 5.9 | 6 | tone, 369-2273Hz | 1-9 | 3 |

The scripts and their index came to 861 bytes of shadow RAM's room past
`AreaShapes` (2,864 before); main RAM below `&3000` grew by 185 bytes
(`snd_ask` to `snd_write`, 172, `lv_hook_redraw` and the interrupt's
call), inside `ObjMore`'s page alignment, so its room is what it was
(1,292); `snd_segment` took 93 of HAZEL's 169 after `ObjWork`;
`LiveGlue` 29 (`lv_copy_sound` and its call); `sound_init` 91 of
`BANK_DATA`'s room after `AreaConv`; 13 bytes of zero page (`&03` to
`&0F`) and 3 of `Work`.

`tools/soundcheck.mjs`: 901 ticks, 43 sounds asked for, every byte the
chip took the model's; `snd_tick` 229 / 478 / 578 cycles (median / p90 /
most) a tick with a sound playing, 59 idle. `tools/livecheck.mjs` over its
whole run: 19,074 ticks, 171 sounds asked for by 2,172 passes, all the
transcription's, every byte the model's; `snd_tick` 216 / 430 / 557 with a
sound playing (1,627 ticks), 59 idle. Before and after, the live check
(fields a frame, median / p90 / max, flip to flip; `make check`'s runs):

| | before | after |
|---|---|---|
| all | 1.77 / 4.95 / 18 | 1.77 / 4.97 / 113.76 |
| entrance | 7.97 / 12.05 / 18 | 8.05 / 12.21 / 18 |
| standing | 0.53 / 1.94 / 8.19 | 0.53 / 1.96 / 113.76 |
| walking | 1.54 / 4.05 / 13.37 | 1.54 / 4.08 / 13.49 |
| turning | 2.06 / 5.37 / 11.93 | 2.07 / 5.31 / 11.92 |

The vertical sync's interrupt, `irq_handler` to its `RTI`: 832 / 1019 /
1264 cycles before, 899 / 1087 / 1660 after (the live disc); on the free
camera's disc, which asks for no sound, 868 / 953 / 974 after. An
entrance's frame now has a doorway's sound playing under it (sound 10, six
ticks: at the cycles above, 0.03 to 0.08 fields), against its 0.08 fields
more at the median. The longest
frames after are the logic waiting for a sound to be taken (decision 110):
`minutes.txt`'s passes at the minute's turn ask for global condition 0's
sound 11 (157 ticks) and more behind it, 31 and 114 fields; the original
stops for every sound's whole length.
