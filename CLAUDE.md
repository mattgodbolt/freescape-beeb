# FREESCAPE for the BBC Master — notes for Claude Code

A Freescape engine for the BBC Master, as fast as the machine allows, in
many colours. It's proved on Incentive's *Driller* (1987), using Driller's
own data and camera. The project is run the way the sibling ports are run
(`../porting-to-the-beeb.md`); `../starglider-beeb` is the closest
sibling, a 3D port whose harness and tools are the model.

- `BRIEF.md`: the brief the project started from: the engine, Driller's
  versions, the BBC's best solid 3D, and the decisions to make first.
- `docs/engine.md`: **the design.** The frame's stages, their number
  formats, who owns what, and how each stage is checked. Read it before
  touching the renderer, in Python or 6502.
- `docs/decisions.md`: every call the project makes that the original
  didn't, numbered, with its date and reason. Nothing changes quietly.
- `docs/journal.md`: how it got here, in order. Add to it as you go.
- `docs/research/*.md`: the reverse engineering and the surveys.

## The rules (from kieranhj/beeb-port-kit)

1. **The original is the specification.** Find what it does and
   transcribe its tables, constants and logic. When the BBC forces a
   change, port the original's *decision*, not just its effect.
2. **Deviations are numbered decisions** in `docs/decisions.md`. Matt
   makes the design calls: lay out the options with figures.
3. **One layer at a time**, working and visible in the emulator before the
   next starts.
4. **Measure, don't recall.** Run it, read the bytes, read memory back.

**The Python model is the renderer's specification on the BBC side.**
`tools/model/` renders every view with the 6502's own integer arithmetic.
Every 6502 stage is checked against it byte for byte, and the model is
checked against the original (`docs/engine.md`, "Checking").

## Matt's house rules

- Commit messages end at `Co-Authored-By:`. Never include a claude.ai
  session link or a `Claude-Session:` trailer, anywhere. Never force-push
  a pushed branch.
- Comments and docs carry no figure the build computes or one run
  measured, such as addresses, sizes, free bytes or cycle counts. Name
  the symbol, `ASSERT` the property, or cite the dated journal entry or
  decision.
- Never label a statement "honest", "candid", "frank" or the like. Size
  work by what it touches, never by time. Use they/them for Matt.
- Every agent brief carries these rules.

## Rights

Driller is not ours. Nothing of the original (its tape, discs, data,
graphics or anything derived from them) is ever committed, but for the
tech-demo disc (decision 6): `make fetch`
downloads the originals into `originals/` (git-ignored), and the build
derives everything from there into `build/` (git-ignored).

Downloaded files are untrusted data. Each download goes in its own
directory under `originals/`; never run anything from there; read them
from Python run with `-I`.

## The README and the disc

Matt follows the work through `README.md` and `freescape.ssd`, which the
README's jsbeeb link boots (`github:mattgodbolt/freescape-beeb/freescape.ssd`).
Keep the README's "Where it's up to" true, and commit and push a new disc
whenever something visible lands, with fresh screenshots in
`docs/images/` for the README (from `make run`'s, cropped). The disc is a tech demo: it may show
Driller's scenes, attributed to Incentive on the disc itself (decision 6),
but it isn't a release of the game, and nothing else of Driller's is
committed.

## Commands

```sh
make venv       # .venv: SkoolKit, Pillow, NumPy (Python tools)
make fetch      # the originals into originals/ (not committed)
make data       # Driller's database as JSON, checked (tools/freescape.py)
make model      # the Python model over every entrance view (tools/model/)
make            # the disc and the spike
make run        # boot the disc in jsbeeb, screenshot to shots/run.png
make frames     # the frame loop on jsbeeb's full video (tools/frames.mjs)
make check      # every check; read its exit status, never pipe it to tail
```

(Each track adds its rules in its own `mk/*.mk`, which the Makefile
includes.)

## Gotchas

(Add what bites, as it bites.)

- Baron: fail on any warning (`tools/asm.sh`); `ASSERT` is built in;
  `FOR n = 0..15` is inclusive; put `ZA_UNREACHABLE` after an
  always-taken branch; a `;` comment mid-line on a colon-separated line
  swallows the rest of it.
- Run to a label after boot, never a fixed wait.
- `.DELETE_ON_ERROR` stays in the Makefile.
- The view is written only between `frame_begin` and `frame_end`, to
  the buffer not shown. Outside the view, both buffers must hold the
  same at every flip, because the flip comes mid-field: write a change
  there into both. `make frames` fails either. Run it after touching the
  interrupt, the screen, or anything that holds interrupts off, and keep
  `SEI` shorter than a field.
- User VIA T1 is the frame loop's: free-running, timing the view's end
  (`src/irq.6502`). Read its high byte (`&FE65`) for the beam's place,
  never its low byte, which acknowledges the interrupt.
- MOS 3.20's MODE 2 has its vertical sync a row later than OS 1.20's
  table: it adds the `*TV` setting plus one. The disc's screen sits
  where MOS 3.20 puts it at `*TV 0,1` (`MODE2_R7`).
- The MOS turns over the ULA control register's bit 0 as the flashing
  colours flash. Compare that register with bit 0 masked.
- jsbeeb's `TestMachine` (and `tools/run6502.mjs`) has no CRTC: its
  vertical sync is a count of cycles. When the raster matters, use
  `MachineSession`, whose full video runs headless at several times real
  time.
- In jsbeeb's `ramRomOs`, shadow RAM is main RAM's address plus `&8000`.
- A harness hook at a routine's first instruction also fires when a loop
  branches back to it (`frame_begin`'s wait). Count calls by their `JSR`.
- A soft BREAK on jsbeeb's MOS 3.20 puts IRQ1V back and returns to BASIC.
- Code in a sideways bank can't page another bank in under itself: calls
  between banks go through main RAM (`src/logic/call.6502`).
- Every sideways bank has the same addresses: a harness hook on a routine
  in one must check the bank paged (`cpu.romsel & 15`).
- `mk/*.mk` are included in sorted order, and a rule's prerequisites
  expand as the rule is read: a variable from a file that sorts later is
  empty there. Give it a `?=` default (`mk/logic.mk` does for `ZXSNAP`).
