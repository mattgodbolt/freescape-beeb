# Decisions

Every call the port makes that the original didn't, numbered, dated, with
the reason. Nothing changes quietly. Matt makes the design calls. Where
Matt asked for autonomous work, the call is made and marked so, to
revisit freely.

The brief's D1-D7 (`BRIEF.md`, section 5) are decisions 1-7.

## 1. The specification (2026-10-31)

**Driller's ZX retail version is the specification for the geometry, the
logic and the view**: its database, camera, steps, turns, projection and
view rectangle. Its colour isn't used (decision 2): the colours come from
the colour study (decision 8).

Why: the database is the same in every version; the ZX's is
byte-identical to ScummVM's supported variant, the siblings' SkoolKit
harness can run it headless as an oracle, and the BBC view keeps its
geometry (decision 2), so the ZX's image can still check the model's.

## 2. The screen: MODE 2, many colours (2026-10-31, Matt)

Matt: "many colours and as fast as you can make it", after "we can
consider mode 2 and ordered dithering too".

**MODE 2, 8 colours, with ordered dithers of pairs; a 104 × 104 view**,
which is the ZX's 208 × 104 at half the width with the ZX's field of view,
in a 128-wide screen (R1 = 64).

- Against the brief's option D (120 × 101, the PC's EGA view at half
  width): 104 × 104 keeps the ZX's geometry, so the ZX remains the oracle
  for which face covers which pixel, and it's 5,408 bytes a frame against
  6,060.
- Against MODE 1 (option C): twice the colours for half the width, at
  the same cost a byte.
- The view's size and focal lengths are build constants, so a larger
  view can be measured later.

## 3. The draw order (2026-10-31, autonomous)

**The original's sort, processed front to back into a span buffer**
(`docs/engine.md`, stage 8). It reproduces the original's image exactly,
glitches included. Starting each frame's sort from the last frame's
order (the brief's D3 b) is an optimisation to measure, not a change.

## 4. The pace (2026-10-31, autonomous)

**Animate the original's steps and turns** (the brief's D4 a): the logic
takes the original's steps exactly, and the renderer shows the frames in
between. The rate is to set once it can be seen.

## 5. The machine (2026-10-31, autonomous)

**The BBC Master 128 first.** Shadow RAM holds the second 16K buffer at
the same address, as in Solid Elite; the 65C12's instructions are used
freely; HAZEL and four banks of sideways RAM hold the tables and data. A
Model B edition is for later, if the Master's numbers leave room.

Why: MODE 2's 16K screen double-buffered doesn't fit a B beside the
engine, and Matt plays on a real Master.

## 6. Rights (2026-10-31)

The build reads Driller from fetched copies (`make fetch`, into
`originals/`, git-ignored) and commits nothing of it.

**The public disc, `freescape.ssd`, carries nothing of Driller's either**
(Matt asked for it to follow the work, 2026-10-31). It shows the engine on
scenes of its own; Driller's areas are rendered and timed only on the
machine that fetched them, until the rights allow otherwise.

## 7. Scope (2026-10-31)

Driller first, with the loader kept general (Dark Side and Total Eclipse
share its layout).

## 8. Where the colours come from

Open: the colour study (`docs/research/colour.md`) proposes it.
