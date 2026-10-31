# Rich Talbot-Watkins' sources: tricks for the engine

Rich Talbot-Watkins (waitingforvsync) has published the sources of the BBC Micro programs they've
been writing. This reads them for techniques this engine could use, written on 2026-10-31 against
`docs/engine.md`, `docs/research/maths.md` and the model's counts (`docs/research/model.md`). It
doesn't re-survey what `docs/research/beeb-3d.md` covers (PORTAL's fill as measured from its disc,
boom, Solid Elite, lander, BEEB-NICCC); where the new sources explain something beeb-3d.md could
only measure from outside, it says so.

Tags, as in beeb-3d.md:

- **[source]**: what the code, its comments or its documents say, with file and lines;
- **[counted]**: cycles we added up from the instructions;
- **[inferred]**: our estimate, with the reasoning.

Unless a line says otherwise, "our" figures are maths.md's measured costs (the projection 508 c a
vertex, `dot3` 329 c, `mul` 98 c, `div_q` 876-1,217 c) and the model's medians over the 65 entrance
views (43 vertices projected, 63 transformed, 14 objects transformed, 14 faces drawn, 6 faces
2D-clipped, 249 face lines, 302 runs written, 94 bytes where two runs meet). A field is 39,936
cycles; the target is the median view in two.

Paths are relative to each repository's clone, at these commits:

| Repository | Commit | What it is |
|---|---|---|
| [portalc](https://github.com/waitingforvsync/portalc) `main` | f0aac46, 2026-10-04 | PORTAL in C and its Baron port: rotations and reciprocals |
| [portalc](https://github.com/waitingforvsync/portalc/tree/polar) `polar` | 0ca34d6, 2026-10-16 | the build on PORTAL's disc: angles, logs, a vertex cache |
| [beeb-baron](https://github.com/waitingforvsync/beeb-baron) | a25c8b2, 2026-10-31 | a Claude Code skill for 6502 in Baron: Rich's rules and measured lessons |
| [chasehq-beeb](https://github.com/waitingforvsync/chasehq-beeb) | ac08866, 2026-10-31 | Chase H.Q. from the CPC: MODE 2, a pseudo-3D road, double-buffered under a CRTC rupture |
| [teddyboy](https://github.com/waitingforvsync/teddyboy) | eb51385, 2026-10-30 | Teddy Boy from the Master System: MODE 2, 25fps, smooth scrolling by rupture; fifteen optimisation reviews |
| [exolon-beeb](https://github.com/waitingforvsync/exolon-beeb) | 712f471, 2026-10-31 | Exolon from the CPC: MODE 2, dithered zones, sprites |
| [criticalmass](https://github.com/waitingforvsync/criticalmass) | 8606c6c, 2026-10-29 | a PICO-8 game: MODE 2, one buffer, drawn by EOR deltas |
| [flow](https://github.com/waitingforvsync/flow) | 10eb08c, 2026-01-03 | a sprite engine (a prototype) |
| [spritescale](https://github.com/waitingforvsync/spritescale) | 4a881c2, 2026-05-11 | a sprite scaler, its scaler under `IF 0` |
| [nevryon](https://github.com/waitingforvsync/nevryon) | 5680d10, 2026-05-23 | a disassembly of 4th Dimension's Nevryon (1990) |
| [beebcrunch](https://github.com/waitingforvsync/beebcrunch) | d10d5f5, 2026-07-19 | a compressor: encoders in C, no 6502 decoder yet |

The remaining public repositories are tools and emulators (baron, baron-vsc, os1.20, tawny,
tawny-cpp, richc, a 6502 test suite) or were read for beeb-3d.md (boom, boomed); none is a game
**[source: `gh repo list waitingforvsync`, 2026-10-31]**. The clones were only read: nothing in them
was built or run, and nothing of theirs is copied here beyond short quotes.

## Summary: the tricks, ranked

By what they'd save on the median view, against our figures, most first. Every saving is
**[inferred]**; the sections below give the sums and the sources.

| # | Trick | From | Stage | Saving, median view | Exact? |
|---|---|---|---|---|---|
| 1 | **Flip when the view's last line has gone, not at the vertical sync** | Chase H.Q. (`irqend`), Teddy Boy (D14, `beam_past`), Exolon | 11, and the wait before 10 | The back buffer free about 168 lines (21.5K c) sooner every frame. A view needing 2.x fields shown every 2.x fields, not 3: about 20K c a frame on average for those | The image, yes; the pacing changes. **A decision** |
| 2 | **A level camera's exact fast paths**: skip the matrix's zero and unit entries; one reciprocal and one x product for a vertical edge's two ends | portalc (`rot`, `project_col`, `project_rowd`) | 3, 5 | About 16K on a turning frame, about 6K on every level frame | Yes: nothing in the model changes |
| 3 | **Polar forms for a level camera**: each world point's angle and log distance cached while the eye stands still; a turn costs lookups, a row an exp | portalc `polar` | 3, 5 | A turning frame's transform and projection 54K → 5K; a step's 26K → 10-18K | No: about a pixel at Rich's table sizes. **A decision** |
| 4 | **Reciprocals by lookup** (`256 + f`, three normalising tables) for every gradient and clip parameter | portalc | 4, 6, 8 | About 13K for a median view's edges and crossings, against 70K by `div_q` or 20-25K by a looped 16-bit divide | The model must divide the same way |
| 5 | **Row-run overheads**: each character row's routine within a page at one offset (low bytes only), the first run's entry fixed, the last run ending on the routine's own `RTS`, a run's plant and entry kept across the lines of a character row that repeat it | Teddy Boy (reviews 7, 10, 13), Chase H.Q.'s runner, Exolon's memo | 10 | About 6-11K | Yes |
| 6 | **Lines the back buffer already holds, skipped by a signature a line** (Chase H.Q.'s sky skip) | Chase H.Q. (D12), Critical Mass (D3) | 10 | About 290 c a line skipped: 5.8K for 20 sky lines | Yes, if everything else that writes the view clears the signature |
| 7 | **An edge's x on each line by a patched DDA with no compare** (`INX : BNE`, the carry known) | portalc (`WRITE_ROWS`), Chase H.Q. (Bresenham, the carry as the step) | 8 | The method to plan: 24 c an edge-line, about 12K for a median view's 249 face lines | Yes |
| 8 | **The byte where two runs meet** by `(L EOR R) AND &AA EOR R`, or from pre-masked halves, stored directly | Teddy Boy, spritescale, Chase H.Q. | 10 | 0.5-0.8K; 1.7K more if they'd have been one-byte runs | Yes |
| 9 | Arithmetic primitives inline as macros; the 17th bit left in C | portalc | 3, 5 | 1-2.5K on a turning frame | Yes |
| 10 | Self-modifying hot code in zero page (a patch 3 c, not 4) | Critical Mass (D24), flow | 5, 10 | About 0.5K | Yes |
| 11 | `SAME_PAGE` on hot branches, tables kept within a page, placement by measurement | Teddy Boy (D46), portalc | all | 0.1-0.3% of a frame | Yes |
| 12 | Palette effects through logical colours 8-15 (a flash for 100-120 c, not a redraw) | Chase H.Q., Exolon, Critical Mass | effects, the panel | A whole frame, where an effect would otherwise redraw | Yes |

Items 1, 2 and 4-8 together come to roughly 40-60K a frame against what the engine would otherwise
pay, and none of them changes the picture. Item 3 would take most of what's left of a turn's maths.

**What changes the design:**

1. **The flip** (item 1). engine.md section 1 says the buffers "swap at VSync", and `make frames`
   fails any flip outside the vertical blank. Flipping when the beam has left the view, or at once
   when a frame is handed over with the beam outside it, still shows every frame whole, and starts
   the next frame's rows up to 168 lines sooner. It needs everything outside the view identical in
   both buffers (or the panel shown from one buffer by a second D write, section 3.1), and a check
   that a Master's ACCCON D takes effect mid-field. jsbeeb applies D on every video fetch
   (`src/6502.js:1107-1109` in `/home/matthew/dev/jsbeeb`); the hardware needs checking too. Frames
   would show for a varying number of fields, which matters less for Driller's steps than for a
   scrolling game. It's Matt's call, as a numbered decision.
2. **A level-camera path** through stages 3 and 5 (item 2) is exact, so it's an implementation
   matter, but engine.md's stages 3 and 5 should name it. Item 3 is the bigger alternative; it
   changes the projection's error, so it's a decision, after a model experiment.
3. **Division** (item 4) for stages 4, 6 and 8 isn't chosen yet. This would set it, and the model
   has to make gradients and crossings the same way.
4. **Stage 10's later skip** ("a run can be skipped when the back buffer already holds it"): the
   sources agree it must be decided from records, never by reading the screen, and that the cheap
   first step is a whole line, as Chase H.Q. does its sky (item 6).

## 1. portalc: PORTAL's source

[waitingforvsync/portalc](https://github.com/waitingforvsync/portalc). Two lines of work, both a C model
of the 6502 build (the C is written the 6502's way and the 6502 must match it byte for byte, as our
model does), with a Baron port in `beeb/`:

- **`main`** (f0aac46, 2026-10-04): a 2D rotation per vertex, a normalised reciprocal for every
  divide, an in-place EOR fill and a full clear. Its journals (`JOURNAL.md`, `beeb/JOURNAL.md`) carry
  measured costs for every routine.
- **`polar`** (0ca34d6, 2026-10-16): the build on Rich's disc of the same day, which beeb-3d.md
  measured from outside. Angles and logs instead of rotations and divides, a vertex cache, and the
  transition buffer cleared by an "unplot". Its design is written up in `docs/howitworks.md` and
  `NOTES.md`, the port in `beeb/PORT.md`.

PORTAL's fill and its transition buffer are already in beeb-3d.md, so they're only cited here. What
the source adds is the "~90K of visibility, transform and set-up" that beeb-3d.md could only infer.

### 1.1 Where PORTAL's frame goes, from its own measurements

- `main`, profiled on the Beeb (sampled PC, 7,739 frames): fill 24.5%, clear 14.4%, sprite pass
  12.6%, plot 6.8%, rotation 4.9%, then "a lot of lead ones", none over 4.4%
  (`beeb/JOURNAL.md:1432-1448`) **[source]**. Capture (the walk, the clip, the transforms) splits
  clipping 36%, transforms 26%, making lines 23% (`:1212-1220`) **[source]**.
- `polar`, walking the demo map on a cycle-exact model of the Model B: 24.2fps on average, a frame's
  work 81.1K: camera tick 6.8K, capture 32.6K, fill 33.5K, sprites 2.6K, unplot 5.5K. Standing at
  the start it's 12.9fps (154K: capture 74K, fill 39K, sprites 29K, unplot 12K), the rate beeb-3d.md
  measured (`beeb/PORT.md:540-554`) **[source]**.
- `polar`'s front end against `main`'s, per frame: vertex arithmetic 6.3K (15.4 polar forms at 385
  c) against 9.0K (19 rotations at 339 c, columns, reciprocals); the glue round them about half of
  the front end on both (`docs/howitworks.md:985-1002`) **[source]**.

So on PORTAL's scenes the fill is a third to a half of the frame and the rest is spread thin. The
lesson Rich draws is the one this project already works by: no silver bullet, so every stage
written fast from its first line (`codingstandards.md:124-205` on `polar`).

### 1.2 The polar front end: turning costs table lookups

**What.** Each map vertex is held as a polar form from the eye: its world angle (1024ths of a turn)
and the log of its distance, `256 log2 r` in 16 bits. A vertex's column and depth are then

```
column    = a2c[v]                    v = angle − camera's angle, a byte
log depth = log r − lsec[v]           lsec = 256 log2 sec, 128 bytes
row       = exp(h.l − log depth)      h.l = the height's log, once per height per visit
```

no rotation, no multiply, no divide (`docs/howitworks.md:343-434`) **[source]**.

- The polar form: the offset's larger leg (the major) and the ratio `t = minor/major` as a byte from
  `exp(log minor − log major)`; the angle is `atan[t]` and `log r = log major + lhyp[t]`, `lhyp =
  128 log2(1 + t²)`, at most 128, so a byte. The quadrant comes from the offset's signs by
  `LDA dy+1 : ASL A : EOR dx+1 : ROL A : PHP : ROL A : AND #3` (`:108-153`, `:230-341`)
  **[source]**. The 6502 is `POLAR` (`beeb/src/arith_macros.6502:169-272`).
- **The vertex cache** keeps polar forms. It's emptied only when the eye's whole-unit position
  changes, through its entries (each holds its vertex, so only used slots are cleared:
  `beeb/src/vcache.6502:34-46`), "so a frame that only turns does no polar work at all"
  (`docs/howitworks.md:331-335`) **[source]**.
- **Costs.** A polar form 369-385 c, log r's own share about 15; log2 47 c and exp2 81 c on average
  (`docs/howitworks.md:212-213`, `:325-329`, `:989`); a column and depth "about 30 cycles for both, no
  multiply" (`:398`); a row 97 c by exp against 100 for `main`'s reciprocal product (`:998-999`)
  **[source]**.
- **Accuracy.** log2 within 1.15 units (0.31%), exp2 within 0.25%; log r within 2.4 units (0.6%) and
  the angle within 1.32 steps of 1,024, 0.38 on average (`:188-191`, `:210-211`, `:311-315`)
  **[source]**. At our focal length (FX = 79.25 pixels, `docs/research/maths.md`) 1.32 steps is
  0.0081 radians: 0.64 pixels at the view's middle and 0.9 at its edge (0.19 and 0.27 on average),
  against our projection's worst 2.21 sixteenths, 0.14 pixels **[inferred]**.
- **Ideas Rich lists, not built** (`:1008-1045`) **[source]**: logs of bytes by a 256-byte table
  (about 1.1K a frame); the gradient without leaving logs, `log2|o1 − o0| = l1 + F(l1 − l0)`, one
  lookup an edge (0.6K); exp by one 256-entry table per octave, about 35 c against 97 (1.3K); and
  **polar forms by coordinate**: map vertices share x and y values, so cache each distinct
  coordinate's log and sign, and a polar form becomes about 150 c ("a move along one axis would keep
  the other axis's logs").

**For us.** It's a fast path for a **level camera** (pitch and roll 0, most of Driller), replacing
stages 3 and 5 for the vertices it serves. Our current costs at the model's median view (43 vertices
projected, 63 transformed, 14 objects; `docs/research/model.md`), with the projection's measured
508 c a vertex (`docs/research/maths.md`):

| Median view | A step (camera moves) | A turn (orientation changes) |
|---|---:|---:|
| Now: transform | 63 × 3 24-bit subtractions ≈ 3.8K | 14 objects × about 2.3K (M·corner by `dot3`, three edge vectors by `mul`, the additions) ≈ 32K |
| Now: projection | 43 × 508 ≈ 21.8K | 21.8K |
| Now: both | **≈ 25.6K** | **≈ 54K** |
| Polar forms, at Rich's costs | 32 (x, z) points × (385 + 30) + 43 rows × 97 ≈ 17.5K; ≈ 10K with forms by coordinate (150 c) | 32 × 30 + 43 × 97 ≈ 5.2K |

All **[inferred]**: the turn's 2.3K a cuboid is maths.md's `dot3` (329 c) three times for the corner,
`mul` (98 c) nine times for the edge vectors and about 22 c for each of 21 coordinate additions; a
cuboid's eight vertices stand on four (x, z) points, so 63 transformed vertices on about 32.

That makes a turn about a tenth of what it costs now, and a step a half to two thirds. The price
is accuracy: at Rich's table sizes the columns are good to about a pixel, not to a sixteenth. Our
model's check against floating point allows a pixel (`docs/research/model.md`, "Checks against the
original"), so Rich's tables would sit at that line. Finer tables are possible in a sideways bank:
the angle in 2,304ths of a turn (72 × 32, so Driller's 5° steps are whole), a 12-bit ratio and 16-bit
`a2c` entries in sixteenths. **It's the largest saving found for a turning frame, and it changes the
projection, so it's a decision for Matt**: the model can be given a polar path and its error
surveyed by `tools/mkmaths.py --survey`'s method before any 6502 is written. Pitch or roll would take
the general path, which stays. Section 1.3's exact savings come first either way.

### 1.3 Zero and unit matrix entries: skip their products

**What.** `rot` looks each of sin and cos up once and branches on the table's two special values:
index 0 is a zero product (`czero`, `szero`, no multiply), and a stored 0 means 256, a unit
(`cone`, `sone`: the magnitudes copied) (`beeb/src/arith.6502:588-613` on `main`) **[source]**. It
also skips the high byte's product when a coordinate's magnitude is under 256, which 68% of x and
88% of y are on PORTAL's maps: a transform's median went from 758 to 660 c
(`beeb/JOURNAL.md:1475-1477`) **[source]**.

**For us** (stage 3, turning frames). With pitch and roll 0 our matrix is the yaw rotation alone:
four of its nine entries are 0 and one is 1.0 (64). M·corner then takes four products and a shift,
not nine products; the three edge vectors four products and a shift, not nine; and the additions
skip the edge vectors' zero components. That's about 1.2K saved a cuboid, **about 16K on a turning
frame at the median** (14 objects), and it's exact: nothing in the model changes **[inferred, from
maths.md's `dot3`, 329 c or about 110 a term, and `mul`, 98 c]**. maths.md already notes that
Driller's vertices are bytes, so an 8 × 8 `dot3` would halve each product; the high-byte skip is the
same observation made at run time.

### 1.4 One reciprocal for a vertical edge's two ends

**What.** PORTAL keeps each vertex's depth reciprocal with its view data: the column projection
and every row projection at that vertex reuse it, and a wall's two lines (floor and ceiling) share
the column (`docs/portal-spec.md:297-298` on `main`; `project_col` and `project_rowd`,
`beeb/src/arith.6502:352-394`, `:478-507`) **[source]**. `project_rowd` is one byte product, an add
and a shift: 110-116 c (`beeb/JOURNAL.md:475-511`) **[source]**.

**For us** (stage 5, level camera). A box's vertical edges stay vertical when pitch and roll are 0
(BRIEF.md section 4 lists this as a lever), so the edge's two ends share Z and X: the second end
needs no dispatch, look-up, patch, X' or x product, only its y. From maths.md's breakdown that's
about 216 c instead of 508. A median view's 43 vertices are about 20 such pairs: **about 6K a
frame**, exact **[inferred]**.

### 1.5 Reciprocals of bytes by lookup: gradients and clip parameters

**What.** One 128-byte table, `recipf[n] = round(65536/n) − 256` for n = 128-255, so a reciprocal is
always `256 + f` at a known power of two and a quotient is one add and one 8 × 8 product
(`num·(256 + f) = num·f + (num << 8)`). Three 256-byte tables normalise any byte: `nrm[b] = b <<
lz(b)`, `k8[b]` its bit length, `sbyte[b]` the shift with the power-of-two case folded in (2^16/128
is 256 << 1, kept as f = 0 at one shift less, so no multiply needs a special case). A 16-bit
denominator shifts its low byte right by `k8[hi]` and ORs in `nrm[hi]`: a one-byte shift instead
of a two-byte one (`docs/portal-spec.md:118-132`; `JOURNAL.md:695-926`; `beeb/src/arith.6502:123-188`;
`beeb/src/tables.6502:44-56`) **[source]**.

| Routine (`beeb/JOURNAL.md:466-578`) | Cycles a call **[source, measured on b2]** |
|---|---:|
| `RECIP8`, a byte's reciprocal (inline) | 15 |
| `RECIP16`, a u16's | 70 (94 over every n) |
| `MUL_RECIP8`, a byte times 256 + f | 48 |
| `MUL_RECIP16`, a u16 times 256 + f | 102 |
| `grad_mag`, dy/dx as a gradient | 127-166 |
| `div_t`, num/den as a u0.8 clip parameter | 252 |
| `lerp16`, va + t (vb − va) | 156 |

Normalising by tables against a shift loop: 22 c always against 26-66 for byte denominators
(`JOURNAL.md:916-919`) **[source]**. The precision is uniform, about 0.2% relative.

**For us** (stages 4, 6 and 8: the near clip, the 2D clip and edge set-up, none built yet). Every
edge needs a gradient and every clipped edge a parameter. maths.md's exact `div_q` costs 876-1,217 c
a coordinate; a gradient as `grad_mag` does it costs 127-166, and a clip parameter and its lerp
about 400 **[source]**. A median view has 14 faces drawn and 6 2D-clipped: at four edges a face and
two crossings a clipped face that's about 56 gradients and 12 crossings, **about 70K a frame by
`div_q` against about 13K this way** **[inferred]**. Against an 8-bit looped divide (106-170 c,
beeb-3d.md) it saves less, but that has 8 bits of quotient. The error, 0.2% of a gradient, is
under a fifth of a pixel over a full-height edge of slope 1; the model would compute gradients the
same way, and the two faces on an edge must make it from the same ends in the same order so their
rows agree.

### 1.6 An edge's rows: the DDA with no compare

**What.** `WRITE_ROWS` steps an 8.8 line along its columns into a bound table: the gradient's two
bytes patched into `ADC #` immediates; the store's base patched to the table less 256 plus the
run's end, so X counts up from 256 less the run's length and the loop ends as X wraps to 0 (`INX :
BNE`); and the carry known clear after each add (the row stays on the screen), so there's no `CLC`
and no compare a step (`beeb/src/clip_macros.6502:173-229` on `polar`; `beeb/PORT.md:364-366`)
**[source]**. The falling loop, condensed, with our cycle counts:

```
.down_store     STA bound-&100+LO(bound),X   ; 5  (the base's low byte patched: run_x1)
                LDA scan_fraction            ; 3
.down_fraction  ADC #0 : STA scan_fraction   ; 5  (the gradient's fraction, patched)
                TYA                          ; 2
.down_whole     ADC #0 : TAY                 ; 4  (its whole part, patched; C clear after)
                INX : BNE down_store         ; 5
```

24 c a step **[counted]**. Rising lines keep 255 − the fraction, so a borrow up is a carry and both
directions share the add (`beeb/PORT.md:327-328`; `beeb/JOURNAL.md:739-748` on `main`) **[source]**.

**For us** (stage 8). Our span buffer needs each face's left and right x on every line it covers:
the same DDA, a line at a time instead of a column. At 24 c an edge-line, a median view's 249 face
lines cost about 12K for both edges **[inferred]**. Solid Elite's per-row tables are 14 c a row for
the steep case (beeb-3d.md), which is the same loop with an 8-bit fraction and the compare; ours
needs the fraction, as x is in sixteenths.

### 1.7 Smaller things from portalc

- **Arithmetic primitives as macros**, expanded on the caller's own variables, so no `JSR` and no
  copying arguments into the callee's: `mulu8` 55 → 42 c, `recip8` 35 → 15, `project_rowd` 263 → 116
  (with a fast path) (`beeb/JOURNAL.md:443-511`) **[source]**. Ours are routines (`mul` 98 c with its
  `JSR` and `RTS`); inline in the transform they'd save 12-20 c a call **[inferred]**.
- **The 17th bit left in C**: products that can reach 17 bits leave 16 in the variable and the
  17th in the carry for the first `ROR`; 7-58 c off each division routine (`beeb/JOURNAL.md:529-572`)
  **[source]**.
- **A table half a page in, indexed by its key**: `recipf_n − 128` is page-aligned, so `LDA
  recipf_n-128,Y` with Y = n (128-255) never crosses a page; the sine table fills the page's first
  half (`beeb/src/tables.6502:15`, `:44-45`) **[source]**.
- **A variable shift by a self-modified branch into a run of shifts**: `STY skip+1 : … .skip BMI run
  : .run LSR A ×7`, entered where the shift count says (`EXP2_8`, `beeb/src/arith_macros.6502:142-150`
  on `polar`) **[source]**. Our projection's seventeen cases do the same job by `JMP (proj_cases,X)`.
- **Frame work overlapped with the flip**: the camera and the capture never touch a buffer, so they
  run while the last frame waits for its vsync: +13% on PORTAL's goldens, and the demo from 14.9 to
  17.5fps (`beeb/JOURNAL.md:847-855`, `:1513-1532`) **[source]**. Ours already does this
  (`frame_begin` as late as possible, engine.md section 1); Rich's figure is the case for keeping it.
- **Junk rows above and below each buffer** take a line's overrun, so the plotters do no bounds
  checks, and the buffer above the ROM uses `&8000` as its junk row, "where stores go nowhere"
  (`docs/portal-spec.md:862-867`, `:926-936`) **[source]**. Our writer writes exact rows, so it needs
  none.
- **The vertex cache and the visit cache are emptied through their entries**, so the cost is
  what was used, not the table (`codingstandards.md:233-236` on `polar`) **[source]**.
- **Smooth tables stored as a bit a delta** and unpacked by the loader with `ROR` through the carry
  (`docs/howitworks.md:941-957`) **[source]**. Not needed while HAZEL and the sideways banks have room.
- **Measured and not taken**: a steep line's whole delta at once saves 6 c a frame
  (`beeb/JOURNAL.md:781-795`); reading only the even scanlines in the sprite pass, about 1%, and wrong
  under dithers whose two lines differ (`:1587-1600`) **[source]**.

## 2. beeb-baron: Rich's written rules

[waitingforvsync/beeb-baron](https://github.com/waitingforvsync/beeb-baron) (a25c8b2, 2026-10-31) is a
Claude Code skill for writing BBC 6502 in Baron, the assembler this project uses. Its
`optimisation.md` collects what paid and what didn't over Teddy Boy's fifteen optimisation reviews,
PORTAL and Critical Mass; `hardware.md` is the machine as Rich's programs take it over. Most of it
is method this project already follows (measure, prove exact, judge by the bad frames:
`optimisation.md:7-25`). What bears on the engine:

- **Self-modifying hot loops in zero page** (Critical Mass's D24): each patch is a 3-cycle, 2-byte
  zero-page store, and a loop there can't cross a page; in zero-page code an instruction's operand
  is itself a pointer for `(zp),Y` elsewhere (flow) (`optimisation.md:198-202`) **[source]**. For us,
  `pmul`'s twelve patched operands (the projection's "patch 60", maths.md) would cost about 48 c a
  vertex instead of 60, and `mul_set`'s and `dot_set`'s patches a cycle each less: about 0.5K a
  median frame **[inferred]**. `pmul` is about 60 bytes, a quarter of zero page, so it's worth it
  only if the allocator's pool has them spare.
- **`SAME_PAGE target` after every hot branch**, failing the build if it crosses a page; tables read
  indexed kept within a page (`FITPAGE`, `INPAGE`); never a base before a table (`table-1,X`) unless
  the base is on the table's page; place by measured anchors. Teddy's crossings went from 171 to 38
  cycles a frame (`optimisation.md:80-83`, `:111-113`, `:205-210`; the macros are PORTAL's,
  `beeb/src/macros.6502:44-46` on `polar`) **[source]**. We have no such checks yet (`src/`); the row
  runs and `pmul` are where they'd go.
- **Unrolled runs entered and left by patching**: every step starts with the same opcode so the
  put-back is one constant store; a spare last entry in the step table so "stop after the last" is
  harmless; a run that ends at its own end isn't patched (-125 and -141 cycles in two reviews);
  `JSR` straight at the run, never through a trampoline (`optimisation.md:89-103`) **[source]**. Our
  row runs (stage 10) are this; a run to the view's right edge needs no planted RTS.
- **Flags and the carry**: `CLC`/`SEC` hoisted where the loop leaves C known; a value can live in
  C (no `CMP` between the `ADC` and the `ROR` that wants its carry); `EOR #&FF : ADC #k+1` with C
  clear is k − x; always-branches on known flags, each commented; `BIT flags : BMI/BVS` for two
  flags at once (`optimisation.md:65-69`, `:159-173`) **[source]**. The same list, with PORTAL's
  examples, is `codingstandards.md:124-205` on portalc's `polar`.
- **Counting up to zero**: a negative index counted up so `INX : BNE` ends the loop with no compare
  (`optimisation.md:179-180`) **[source]**; `WRITE_ROWS` (section 1.6) is the same thing.
- **Dispatch by a patched `JSR`**, states numbered from 1 so `LDA StateLo-1,Y` needs no `DEY`;
  `JMP (zp)` measured no better (`optimisation.md:186-187`) **[source]**.
- **The time spent waiting for the beam**: Teddy plots the next frame's sprites in the wait, each
  once the beam has passed its place for the last time (23.2 → 16.3 ms of a frame's work)
  (`optimisation.md:213-214`) **[source]**. With double buffering we wait only when a frame beats the
  flip; the stages before the first screen write already fill that wait.
- **Measured as losses** (`optimisation.md:227-242`) **[source]**, which bear on our stage 10's
  later idea of skipping runs the back buffer already holds:
  - reading the screen to skip work: "a read and compare costs more than a 6-cycle store";
  - skipping blank stores over an already-blank screen: wrong over lines that had been hidden;
  - wide unrolling: most under 1 cycle saved a byte spent.
  Our plan compares span lists, not screen bytes, so the read is a run's, not a byte's: at about 20-40
  c a comparison against 5 c a byte stored, it pays only for runs over 4-8 bytes **[inferred]**.
- **A free bit in MODE 2**: logical colours 8-15 set to 0-7's physical colours give every pixel a
  bit the display ignores, which Teddy uses to mark opaque sprite bytes (-1,525 c, 3.4%); the rule is
  that a mark pays only where the byte is loaded anyway (`optimisation.md:115-126`,
  `hardware.md:202-203`) **[source]**. Our palette already sets 8-15 that way (`src/screen.6502`); the
  writer never reads the screen, so there's no use for it yet.
- **Raster interrupts for a split** (`hardware.md:205-216`) **[source]**: make every System VIA T1
  reload `rows × 512 − 2`, so its low byte is always `&FE` and one store to T1L-H sets the next
  period and clears T1's flag; dispatch the handlers by `BIT &FE4D : BVS handler` with each handler
  rewriting the branch's offset; display off (R8 = `&F0`) in the CRTC cycle that isn't shown. And
  syncing to vsync to the cycle with a one-page loop of exactly 39,935 cycles (`:251-276`). For the
  panel below the view (a later layer), if it wants its own palette or mode.
- **Interrupt entry costs**: 7 cycles, then the MOS's `STA &FC : PLA : PHA : AND #&10 : BNE : JMP
  (&204)`, 19 more on NMOS (`JMP (abs)` is 6 on the 65C12); end with `LDA &FC : RTI`
  (`hardware.md:52-55`, `:354-357`) **[source]**. Ours does (`src/irq.6502`).

## 3. Chase H.Q.

A MODE 2 port of the CPC game: a 128-line playfield in two buffers in main RAM, a panel in one,
shown by a three-part CRTC rupture driven by System VIA T1 alone after one cycle-exact sync to the
vertical sync (`docs/plan.md:83-101`; `src/irq.6502`; `src/entry.6502:97-135`) **[source]**.

### 3.1 The flip at the playfield's end (item 1)

**What.** The rupture's third interrupt comes as the playfield's last line is shown. If a new
playfield is waiting, it turns `back` (the buffer the CPU draws into) to the old one there and
then, as its last line has gone; the panel's interrupt points R12 at the new one for the next cycle.
A request that comes after the playfield's end is taken at the panel's top instead. `show` only
posts the request; `wait_back` comes just before the road is drawn, after the next loop's logic
(`src/irq.6502:45-85`; `docs/decisions.md:75-87`, D13; `JOURNAL.md:70-73`) **[source]**:

```
.irqend
    LDA reqshow:BEQ @+:BMI @+           ; a new playfield waiting: the old one's last line gone
    ORA #&80:STA reqshow
    LDA back:EOR #&20:STA back          ; (the old one free to draw into)
```

**Measured** (jsbeeb, 300 loops): before, `show` waited 9,390 c a loop on average, in 199 loops of
300, up to 25,024; with the wait moved, the flip at the playfield's end and the sky skip (3.2), a loop
went from 204,644 to 188,941 c on average, 9.8 to 10.6 loops a second, and `wait_back` took 6 c in
all 300 (`JOURNAL.md:541-557`) **[source]**. Rich's own statement of the design: split "at three
points: top of the status (to reprogram the CRTC), top of the playfield (to reprogram it again), and
then bottom-ish of the playfield (the point at which it's safe to start rendering again to the
currently displayed buffer)" (`docs/decisions.md:79-82`) **[source]**. Teddy Boy starts each redraw
at the play area's bottom the same way (`docs/decisions.md:95-97`, D14) **[source]**.

**For us.** Our view is lines 8-111 of the 256 shown (`VIEW_ROW0` = 1, 13 character rows), and the
vertical sync is at row 35, line 280, of a 312-line field (`src/defs.6502`). The interrupt now shows
a frame at the sync, so the old front buffer becomes free about 168 lines (21.5K c) after the view's
last line has gone **[counted from `src/defs.6502`]**. Instead:

- A System VIA T1 one-shot, started by the vsync interrupt, fires at line 112. If a frame is
  waiting, its handler sets D (by `TSB`/`TRB`, as now) and clears `frame_ready`.
- `frame_end` reads where the beam is from T1's high byte (256 µs, four lines, a unit; never T1C-L,
  which would clear T1's flag: `hardware.md:236-237`), and flips at once if the beam is outside lines
  8-111, as Teddy Boy's `beam_past` reads it (`src/plotting.6502:353-387` there, re-reading the
  interrupt's state round the read to catch one landing between) **[source]**.
- A frame handed over at a random time then waits at most 104 lines (13.3K c) for its flip, 17 lines
  (2.2K) on average, against up to a whole field now **[inferred]**. A view whose work takes between
  two and three fields would come every 2.x fields instead of every three: at an even spread, about
  half a field (20K c) a frame, 16.7 to about 20fps **[inferred]**.

It needs everything the CRTC shows outside the view to be the same in both buffers when D changes
(the border, and the panel when it comes), or the panel kept in main RAM only and shown by a second D
write at the view's end, with D set to the front buffer again at the view's top; that's Chase H.Q.'s
single panel (`docs/plan.md:83-101`, D3), done with D instead of a rupture, and it would write the
panel once, not into both buffers **[inferred]**. A line of margin either side covers the interrupt's
jitter. Whether a mid-field change of ACCCON D shows at once on a real Master needs a check; jsbeeb
takes D at every video fetch (`src/6502.js:1107-1109`). Teddy Boy's update also waits for a minimum
number of fields (`LDA irqvsync : CMP #FramesPerUpdate : BCC noupdate`, `src/irq.6502:63-64` there)
**[source]**, which is how a 25fps cap would be kept if Matt wants one.

**The interrupt's machinery**, all three ports alike **[source]**: T1 free-running, each period
`rows × 512 − 2` so the reload's low byte is always `&FE` and one store to T1L-H (`&FE47`) sets the
next period and clears the flag (Exolon: `FramePeriod = FrameRows * 8 * 64 - 2` and an `ASSERT` on
its low byte, `src/irq.6502:8-11`); the handlers chosen by `BIT &FE4D : BVS handler`, each patching
the branch's offset to the next (Chase H.Q. `src/irq.6502:36-38`, with an `ASSERT` that all are in
reach at `:85`). The sync to the vertical sync is a 39,935-cycle loop kept within a page, then T1
started with the interrupt's latency counted (Chase H.Q. `src/entry.6502:97-135`; Teddy Boy
`src/entry.6502:112-178`).

### 3.2 The sky skip (item 6)

**What.** Each playfield remembers how many of its top lines hold sky already (`SkyTop`, with
`SkyOther` for the other buffer, swapped in when `back` changes); the road draws sky only below that
mark, and then sets it to this frame's sky. Anything else drawn over the sky (sprites, the damage
meter, the turbo icons, the pages) lowers the mark to its own top (`src/roaddraw.6502:24-33`,
`:202-208`, `:631-648`; `docs/decisions.md:70-73`, D12) **[source]**:

```
    LDA back:CMP SkyBuf:BEQ @+          ; this playfield's sky mark
    STA SkyBuf
    LDA SkyTop:LDX SkyOther:STA SkyOther:STX SkyTop
.@
    LDA SkyTop:STA skyclean
```

**Measured first**: the sky was 20 lines and 7,900 c a loop, its lines 99.7% unchanged; the road's
lines only 3% unchanged, so a general delta renderer "would save at most about 9K before its
bookkeeping": not built. The road's drawing went from 93,790 to 86,860 c on average, the sprites'
extra compare costing 474 (`JOURNAL.md:547-554`) **[source]**.

**For us** (stage 10). The model has no horizon, so a line no face covers is all sky, and as a
pattern's bytes go by `line AND 3` that line's bytes are the same in every frame of an area. Keep a
signature a line for each buffer, made as the span buffer finishes the line: the pattern when the
line is one run, or "mixed". A line whose signature matches what the back buffer holds (the frame
before last) isn't written. That takes the sky above the tallest object and the ground cuboid's
full-width lines below; a finer signature (a sum of the runs' ends and patterns) would take any line
unchanged since two frames ago. A skipped line saves its 52 stores and its run (about 290 c); the
test costs 15-20 c a line and two bytes a line **[inferred]**. Everything else that writes into the
view (a crosshair, the laser) must clear the signatures it covers, and an area change clears them
all. The model can count the skippable lines over a walk and a turn before any of it is built.

### 3.3 The row runner (item 5)

**What.** One runner of 64 `STA &xx00+col*8,X` (X the line within the character row), a spare
store and an `RTS`, all in one page (`INPAGE 196` and an `ASSERT`), so a span's ends are low bytes.
The row's pages are patched into its operands once a row. A span is entered by a `JSR` whose low
byte comes from a table by x; an `RTS` is planted where the next span starts, `STA RunnerPage,Y`, and
the `STA` put back afterwards through the same Y, which the runner never touches; the first span
starts at the runner's start, and the last ends on its permanent `RTS`
(`src/roaddraw.6502:80-89`, `:289-313`) **[source]**:

```
    LDY midjsr+1:LDA #&60:STA RunnerPage,Y  ; an RTS where the road starts
.grass1
    LDA #0                              ; self-modified: the grass
    JSR Runner
    LDA #&9D:STA RunnerPage,Y           ; the STA back (the runner keeps Y)
```

- 32 c a span on top of its stores: the plant 11, the pattern 2, `JSR` and `RTS` 12, the restore 7
  **[counted]**.
- The spare store is there because a span that ended at the last cell once put an `STA` back over
  the runner's own `RTS`, and later spans ran on into other code, "possibly the front buffer"
  (`JOURNAL.md:220-226`) **[source]**.
- The whole 128-line playfield, five spans a line: 73,415 c, of which 40,960 are the stores; about 45
  c a span with the cell lookups, and about 280 a row patch (`JOURNAL.md:50-56`) **[source]**.

**For us.** Our routine a character row (engine.md stage 10) avoids the row patch for about 1.8K more
code **[inferred: 13 routines of 157 bytes against one of 196]**, which stands. Section 4.2 has what
to take from it.

### 3.4 Smaller things from Chase H.Q.

- **Edge tables by Bresenham with the carry as the step** (item 7): the error kept in Y less the
  line count (+256), so `ADC #|d|` carries exactly when x steps and `ADC #255-lines` with that carry
  takes the bias off again and leaves C clear; |d|, the bias and the end patched in as immediates
  (`src/road.6502:1010-1046`) **[source]**. 32 c a line, 41 when x steps, with a 16-bit x and two
  stores **[counted]**. With an 8-bit x, 24 and 30. It needs the error's denominator under 256: our
  sixteenths make it up to 1,664, so it's a 16-bit error for us, or section 1.6's DDA from a
  reciprocal **[inferred]**.
- **Signs patched as opcodes**: `CLC`/`SEC` and `EOR #0`/`EOR #&FF` patched once, so one loop adds or
  subtracts (`src/road.6502:850-858`) **[source]**; ours already patches a coefficient's sign into
  `CLC`/`ADC` or `SEC`/`SBC` (maths.md).
- **A product's high byte with a `CMP` for the low byte's borrow** (`src/traffic.6502:453-482`)
  **[source]**: our `pmul` does the same (maths.md).
- **Palette animation** (item 12): the siren lights are in logical colours 8-15, flashed by eight
  palette writes in the border interrupt, about 120 c against 3-4K a loop to move their bytes
  (`JOURNAL.md:231-238`; `src/frame.6502:58-65`; `docs/decisions.md:50-55`) **[source]**.
- **Final bytes made at build time**, so nothing is masked at run time where the fill under it is
  known (`src/roaddraw.6502:4-7`, `:315-366`) **[source]**: for us, a pattern's two halves stored
  pre-masked (section 4.3).

## 4. Teddy Boy

A Master System port on a Model B with 16K of sideways RAM: MODE 2, 25fps, smooth scrolling by an
exhale-style rupture, one buffer, sprites plotted where the beam has passed. Its fifteen
optimisation reviews (`docs/review-optimisation-1.md` to `-15.md`) measure every change, losses
included; beeb-baron's `optimisation.md` (section 2) distils them.

### 4.1 The wait used, and the beam read

- **The frame loop's order**: logic, the update requested, then everything that can't be seen yet
  (`plot_ahead`: sprites the beam has finished with), and only then the wait; the visible writes come
  after it (`src/game.6502:187-220`) **[source]**. Measured: 40-50% of the plots are now made in the
  wait, the work after the update went from 23.2 to 16.3 ms in round 1, and the mean frame from 23,377
  to 18,790 µs, frames over 40 ms 0.40% to 0.24%; the rest of the wait (17-20 ms) can't be used, as
  nothing of the next frame may be written until the beam has passed it
  (`docs/review-optimisation-9.md:180-186`, `:218-236`) **[source]**. Ours has the same shape:
  stages 0-9 before `frame_begin` (engine.md section 1), and item 1 is what shortens the wait itself.
- **The beam's line from T1's high byte**, the interrupt's state read either side to catch an
  interrupt between (`src/plotting.6502:353-387`) **[source]**:

  ```
  .read
  	LDA irqvsync:STA vsync
  	LDX irq.irqbranchdest-1
  	LDY &FE45
  	CPX irq.irqbranchdest-1:BNE read
  ```

  That's item 1's test for "outside the view".

### 4.2 Run overheads (item 5)

**What the reviews measured** **[source]**:

- a run that ends at its own end isn't patched: its own `RTS` ends it, and the put-back afterwards
  rewrites an opcode that's already there, as every step starts with the same opcode: −125 c a frame
  (`docs/review-optimisation-7.md:368-394`, b2) and −141 (`review-optimisation-13.md:226-238`, p2);
- the run entered through the `JSR`'s own patched operand, not through a patched `JMP`: 3 c a call
  (`review-optimisation-10.md:202-223`);
- a routine within a page needs only its low bytes patched: about 14 c a pair
  (`review-optimisation-13.md:296-303`);
- a whole band with nothing to stop goes straight to the run, no patching: about 55 c a call
  (`review-optimisation-1.md:588-617`; `src/sprites.6502:710-712`), and a run to line 7 plants
  nothing (`:238-250`);
- patching a page into a row's stores cost 32 to save 24, so it wasn't done
  (`review-optimisation-3.md:278-283`);
- and the lesson under all of them: the machinery round the runs costs more than the bytes. The
  code that moves bytes was 38-46% of the plotter's time in every profile
  (`review-optimisation-10.md:55-64`), and a compositor that wrote each byte of a pile of sprites
  once lost by 113%, because the pile broke into pieces of 5.8 bytes at about 470 c each
  (`review-optimisation-12.md:139-155`).

Exolon's sprite walker adds a memo: it keeps the phase its unrolled steps are patched for and
patches nothing when the next walk wants the same one, `CMP DrawPhase : BEQ phased`, "so a run of
walks at one phase patches once" (exolon-beeb `src/sprites.6502:74-83`, `:205-207`) **[source]**.

**For us** (stage 10). A run costs about 73 c on top of its stores done plainly: its entry's two
bytes patched into the `JSR` (19), its stop's into the plant and the put-back (27), the plant (6),
the pattern (3), `JSR` and `RTS` (12), the put-back (6) **[counted, for a plausible sequence]**.
With each character row's routine (52 `STA abs,Y` and an `RTS`, 157 bytes) within a page at the
same offset, and its page patched once a character row:

- a run's entry is one low byte (11 c), and its plant and put-back go through an index, `LDA #&60 :
  STA page,Y` and `LDA #&99 : STA page,Y`, Y the stop's low byte (about 18 c with its lookup): about
  44 c a run;
- a line's first run enters at a fixed place, and its last ends on the routine's own `RTS`, with
  nothing planted, so a line of one run (a sky line) costs a `JSR` and its stores;
- where a line's runs end where the line above's did (a box's vertical edges, with a level camera),
  the plants and entries stay as they are and only the pattern and Y change.

At the model's 302 runs on 104 lines (2.9 a line), that's about 6-11K a frame **[inferred]**, and
302 runs at 70 c is about 21K against the 27K of the stores themselves, so the run count matters as
much as the bytes. The model's stand-in rasteriser doesn't merge runs (`docs/research/model.md`,
"The parts other tracks own"): two adjacent runs in the same pattern are one run, with no byte where
they meet.

### 4.3 The byte where two runs meet (item 8)

`(a EOR b) AND mask EOR b` keeps a's bits under the mask and b's elsewhere with no temporary
(Teddy Boy `src/spritesetup.6502:297-298`; spritescale `main.6502:97`, `LDA data0 : EOR paltab0,X :
AND #&88 : EOR data0 : STA data0`) **[source]**. For our meeting bytes, from zero page: `LDA L : EOR
R : AND #&AA : EOR R : STA abs,Y` is 16 c against 21 by `AND`, a temporary and `ORA`; with each
pattern also kept as its two halves pre-masked (`p AND &AA`, `p AND &55`, eight bytes more a pattern,
as Chase H.Q. and Critical Mass prepare theirs), `LDA L_AA : ORA R_55 : STA abs,Y` is 11 c
**[counted]**. At 94 meeting bytes, 0.5-0.9K a frame; and a meeting byte written by its own store,
not as a one-byte run (about 32 c of a run's overhead), saves about 1.7K more **[inferred]**.

### 4.4 Smaller things from Teddy Boy

- **Page crossings, measured and placed**: branches crossing a page went from 98.8 to 20.0 c a frame
  and indexed reads from 45 to 0.7, of about 62K (`docs/decisions.md:1120-1167`, D46); review 15 took
  branches from 171 to about 38 (`review-optimisation-15.md:121-135`) **[source]**. `STA abs,Y` costs 5
  whether or not it crosses, so our row runs pay nothing; only table reads and hot branches matter.
- **Charge the interrupt's time when modelling**: a py65 model without it judged a change that b2
  showed was worse (`review-optimisation-3.md:381-385`) **[source]**. Our `make bench` runs in jsbeeb
  with the real interrupt, as it should.
- **Asserted bounds instead of wrap tests**: −473 c a frame (`review-optimisation-5.md:140-159`);
  **last frame's result gating an expensive test**: −521 (`review-optimisation-4.md:78`) **[source]**.
  For us, the sort started from last frame's order, as BRIEF.md section 4 already proposes.
- **A small stack** (32 bytes, a sentinel under it, 27 the deepest measured) and **ZX02**: main RAM's
  code packed from 11,999 to 7,213 bytes, about 738K cycles to unpack, about 61 c a byte
  (`docs/budget.md:15`; `docs/decisions.md:1169-1186`) **[source]**.
- **Baron's allocator and planted `RTS`s**: a routine whose only exit is a planted `RTS` shows no
  return, so a computed `JSR` must name its targets (`ZA_CANCALL`) or its callers' variables can be
  placed over its own (`docs/baron-za-overlap.md`) **[source]**. Our row runs will be such routines.

## 5. Exolon, Critical Mass, flow, Nevryon, spritescale, beebcrunch

- **Critical Mass draws by EOR deltas** on one buffer: each ball as the difference between how it was
  drawn and how it is now, so each byte goes from old to new once and a ball at rest costs nothing
  (`src/plot.6502:1-9`; `docs/decisions.md:23-25`, D3). A first version that merged the two shapes'
  runs cost a median 16,400 c for a small move; the delta form 13,800 c a frame at the median
  (`JOURNAL.md:55-78`) **[source]**. We write every byte, so the idea that carries over is section
  3.2's: what the back buffer holds, kept as records.
- **Self-modifying loops in zero page** (item 10): Critical Mass's EOR loops are assembled into zero
  page so their patches are zero-page stores and the loops can't cross a page (`src/eor.6502:1-2`;
  `docs/decisions.md:146-150`, D24); flow uses an instruction's operand as a zero-page pointer
  (`src/zp.6502:45-88`) **[source]**.
- **Palette effects** (item 12): Exolon keeps logical colour 8 for a flashing pen, one palette write
  a pass (`src/sprites.6502:596-611`; `docs/decisions.md:278-286`); Critical Mass flashes every ball
  white with eight palette writes (`src/irq.6502:46-71`) **[source]**. For us, the view's patterns could
  use logical colours 8-15 and the panel 0-7, the same physical colours, so that a flash or a fade of
  the view alone is 8 palette writes, about 100 c **[inferred]**.
- **An overlay that restores itself** (Critical Mass's sparks): `kept = (screen EOR colour) AND mask`
  stored a byte and EORed back to remove it, 28 c a byte on and 15 off (`src/sparks.6502:6-9`,
  `:47-58`) **[source; counted]**. A pointer moved over an unchanged view could go into the shown
  buffer for about 700 c a move instead of a frame, but that breaks our rule that only the hidden
  buffer is written, so it would be a decision **[inferred]**.
- **Logs at 32 steps an octave** (Critical Mass's physics: `log16` 41-90 c, a hypotenuse from two
  logs within 1.8%; `src/physics.6502:250-349`) **[source]**: coarser than the 8-bit logs maths.md
  already rejected for the projection; possibly for the collision layer.
- **Exolon's colours**: a CPC ink with three levels a gun is matched exactly by a 50% checkerboard of
  two BBC colours whose bits add up to it, the pair closest in luma chosen (`tools/gendata.py:1-42`;
  `docs/plan.md:170-196`) **[source]**. Our 2 × 4 patterns can also make 25% and 75% mixes; this
  is the colour study's ground (decision 8), not the renderer's.
- **Exolon's bench**: a build with the plotter replaced by `RTS`s, to take the harness's own cost
  off, which had been in every figure before (`src/bench.6502:14-33`; `JOURNAL.md:222-252`)
  **[source]**. For `make bench`, a null writer would split the span building's cost from the stores'.
- **Packing**: Exolon's zones and tiles ZX02-packed, unpacked at a zone change into the blanked screen
  at about 63 c a byte (`docs/decisions.md:114-119`, `:179-184`) **[source; inferred rate]**;
  beebcrunch packs its corpus to 57.9% against Exomizer's 57.7% but has no 6502 decoder yet
  (`docs/results.md`) **[source]**. Our areas sit unpacked in sideways RAM, so neither is needed.
- **Insertion sort on a list kept from frame to frame** (Critical Mass `src/physics.6502:53-102`;
  flow `src/sprite.6502:37-85`) **[source]**: about N compares when little changes. For our sort only
  if the original's order comes out the same from last frame's start, which the model can check.
- **Not relevant**: Nevryon's software scroll (a patched `LDA abs : STA abs` pair loop, about 23 c a
  byte) and its sprite blitter; flow's occupancy masks and render lists (a prototype); spritescale's
  scaler, under `IF 0` (`main.6502:80-179`); Exolon's sprite machinery and zone scripts; Critical Mass's
  physics beyond its logs.

## 6. Measured as losses

What the sources tried and measured as no better, which bears on the engine **[source]**:

- **Reading the screen to skip a store** (an occupancy bit, "already 0", "unchanged"): a read and a
  compare cost more than the 5-6 c store (`beeb-baron/optimisation.md:232-234`; Teddy Boy
  `review-optimisation-7.md:521-545`). Rich's O11, two reads a cell to prove it blank, was wrong
  about once in 90 frames on lines that hadn't been shown, and saved nothing once made safe
  (`review-optimisation-8.md:54-160`). Our stage 10 skip has to come from records.
- **One pass that writes each byte of an overlapping pile once**: twice the plot, from fragmentation
  (Teddy Boy review 12, section 4.2).
- **A general delta renderer for Chase H.Q.'s road**: 3% of its lines unchanged (section 3.2).
- **Wide unrolling**: most of it under a cycle saved a byte spent (`beeb-baron/optimisation.md:235-236`).
- **A general vertex cache** in PORTAL's `main`: "costs more to fill than it saves"; only the one
  vertex a child walk repeats was worth keeping (portalc `beeb/JOURNAL.md:1545-1551`). Ours caches
  each object's rotated corner and edge vectors, which a step reuses whole.
- A steep line's whole delta at once: 6 c a frame (portalc `beeb/JOURNAL.md:781-795`).

## Sources

All cloned on 2026-10-31 into the session's scratch space and read there, at the commits in the
table above:

- [waitingforvsync/portalc](https://github.com/waitingforvsync/portalc), branches `main` and `polar`:
  `docs/portal-spec.md`, `JOURNAL.md`, `beeb/PLAN.md`, `beeb/JOURNAL.md`, `beeb/src/arith.6502`,
  `lines.6502`, `mode5.6502`, `hw.6502`, `tables.6502`; on `polar`, `docs/howitworks.md`, `NOTES.md`,
  `codingstandards.md`, `beeb/PORT.md`, `beeb/src/arith_macros.6502`, `vcache.6502`,
  `fill_macros.6502`, `unplot_macros.6502`, `clip_macros.6502`
- [waitingforvsync/beeb-baron](https://github.com/waitingforvsync/beeb-baron): `optimisation.md`,
  `hardware.md`, `checking.md`
- [waitingforvsync/chasehq-beeb](https://github.com/waitingforvsync/chasehq-beeb): `docs/plan.md`,
  `docs/decisions.md`, `JOURNAL.md`, `src/irq.6502`, `roaddraw.6502`, `road.6502`, `entry.6502`
- [waitingforvsync/teddyboy](https://github.com/waitingforvsync/teddyboy): the optimisation reviews,
  `docs/decisions.md`, `docs/display.md`, `docs/budget.md`, `src/game.6502`, `irq.6502`,
  `plotting.6502`, `sprites.6502`, `spritesetup.6502`
- [waitingforvsync/exolon-beeb](https://github.com/waitingforvsync/exolon-beeb),
  [criticalmass](https://github.com/waitingforvsync/criticalmass),
  [flow](https://github.com/waitingforvsync/flow),
  [spritescale](https://github.com/waitingforvsync/spritescale),
  [nevryon](https://github.com/waitingforvsync/nevryon),
  [beebcrunch](https://github.com/waitingforvsync/beebcrunch): their plans, decisions and journals,
  and the files cited above

Chase H.Q., Teddy Boy and the last six were read by three parallel readers; the claims ranked above
were checked against the cited lines afterwards. jsbeeb's handling of ACCCON D is from
`/home/matthew/dev/jsbeeb/src/6502.js`.
