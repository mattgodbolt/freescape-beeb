# Solid 3D on the BBC Micro and Master: the fastest pipelines

What the fastest filled-polygon and solid 3D renderers on the BBC Micro (2MHz 6502) and Master 128
(65C12) do, stage by stage, and what each stage costs. Written on 2026-10-31 for a Freescape-style
engine (convex solids, one colour a face, first-person camera). It extends
`../../../starglider-beeb/docs/research/beeb.md` sections 1-4 (written 2026-10-18), which covers
Elite's lines, Master memory, the 65C12 and line-drawing measurements; that isn't repeated here.

Tags:

- **[source]**: someone else's published figure or code, with a link or file:line.
- **[measured]**: cycles counted by us from the instructions, or run by us in jsbeeb (method given).
- **[inferred]**: our arithmetic or reading, with the reasoning.

A field is 39,936 cycles; 25fps is two fields (79,872 c), 16.7fps three (119,808 c), 12.5fps four.

Repository paths are given relative to the clone of each repository, at these commits: boom
2c709dc (2025-11-17), waitingforvsync.github.io 231fbc9 (2026-10-31), solid-elite-bbc-master
88f07f3 (2026-10-30), solid-elite-6502-second-processor 7e51a97 (2026-10-30), lander 47cf90e,
doom fed01ab, virus 468719e.

## Summary

| Engine | Machine | Screen | Visibility | Fill | Erase | c/byte (fill) | Frame rate |
|---|---|---|---|---|---|---:|---|
| **PORTAL** (Rich Talbot-Watkins, disc of 2026-10-16) | B + sideways RAM | MODE 5 128×128, 4K ×2, R1 = 32 | portals through a 2D map of convex subzones; sprite merged per byte column | EOR from an off-screen **transition buffer** into the screen down to each column's last edge, then `STA abs,X` | **none**: every screen byte written once a frame; used transition bytes zeroed | **9**, then **5** | **12.9fps** [measured, jsbeeb, one static view] |
| boom (repository, 2025-11-17) | B | MODE 5 128×128, 4K ×2 | portals (the walk isn't in the repository) | EOR in place, down columns, even/odd lines as two dither streams | full clear, 21.8K | 9 + 5.3 clear | none stated; ~25fps for its 4-edge test [inferred] |
| camera / spritescale (RTW discs, 2026-08) | B | MODE 5 128×128 | boxes / scaled sprites | camera: background `STA abs,Y` and rectangles; spritescale not profiled | every byte rewritten | 5 | 33.0 / 16.4fps [measured] |
| **Solid Elite** (Eben Upton, 2026-10) | Master 128 + 4 SWRAM banks | MODE 1 256×192, 12K, main + shadow at one address | painter's between ships, back-face culling within | per-row edge tables (exact DDA), masked RMW ends, JSR into `STA abs,Y` row runs | per-row dirty extents per buffer; kept solid rows | **5** + ~167 a row | flight 12.3, docking 7.05, capped 25 [source] |
| Solid Elite, Tube, Master host | Master + 4MHz 65C102 | as above | as above (on the parasite) | `STA abs` straight-line runs, 37.6K | as above | **4** + 47 a span | flight 21.6, docking 10.75 [source] |
| Solid Elite, Tube, Model B host | B + 64K SWRAM + 3MHz 6502SP | as above | as above | row runs per buffer | as above | 5 | flight 17.8, docking 10.2 [source] |
| lander (Eben) | B + 64K SWRAM | MODE 1 256×160, 10K ×2 | strips far to near; projection baked into tables | byte columns, `STA abs,Y` column tables, planted RTS | per-column top/bottom records | 7.5 (5 in two passes) | ~10, capped 12.5 [source] |
| BEEB-NICCC v1.2 (Kieran, 2026-10-19) | B (+16K SWRAM for music) | MODE 5 128×100 (even lines of 128×200) | 2D stream, painter's, 1.24× overdraw | per-line edge tables, masked RMW ends, `STA abs,Y` | full or masked clear | 5 + 169 a row | 6.9 [source] |
| The Sentinel (1986) | B | MODE 5-like 160×192 | painter's, tile rows back to front, ray-cast tile visibility | per-line edge tables, `LDY #8n : STA (P),Y` | full redraw under a blue palette; pans by strip + hardware scroll | 8 + ~180 a line | not stated |
| Revs (1985) | B | custom MODE 5, 80-line track view | painter's | edges into "dash data" columns, copied and zeroed | the copy zeroes it | 15-25 | ~11 [inferred] |
| Nick Jameson's 3D demo (1994) | B | MODE 5, 96×192 window | screen-space culling of one convex model | EOR from a back (edge) buffer into the front buffer | 5 c a byte wipe of the edge buffer | 9-10 | not stated |
| Stunt Car Racer (scr-beeb, Kieran 2019) | Master | MODE 5, 128 wide | front to back against a per-column floating horizon | lines only; sky filled per column | 5.5 c a byte clear | — | not stated |
| DOOM E1M1 (Eben, wireframe) | B + SWRAM | MODE 4 256×160 | BSP + analytical span-list occlusion | lines | clear scheduled behind the raster | — | ~7 [source] |

**The fastest pipelines** for walls and solids are Rich's 128×128 portal engine (12.9fps on a
Model B for walls, floor, ceiling and a sprite, with the fill only a quarter of the frame) and
Solid Elite (12.3fps in flight on a Master at 256×192, 21.6 with a 4MHz co-processor). Neither
author states a frame rate for a busy scene.

**New since beeb.md (2026-10-18)**:
- Eben's two Solid Elite repositories (created 2026-10-20 and 2026-10-26): the first big filled
  3D renderer on the Master with measured costs.
- Rich's newer portal engine exists only as `portal.ssd` (2026-10-16) on his GitHub Pages. It
  replaces boom's in-place EOR fill and 21.8K clear with a transition buffer, so each screen byte
  is written once. The boom repository itself hasn't changed since 2025-11-17.
- Kieran's BEEB-NICCC v1.2 (2026-10-19): a span filler 28.6% faster than the 2020 release.

**Cost by stage**, the best found:

| Stage | Best | Where |
|---|---|---|
| 8×8 multiply, multiplier reused | ~22 c (quarter squares, patched operands) | mult14 (TobyLobster's table); Solid Elite's MU11: 23 c |
| rotate a vertex (3×3, 8-bit entries) | ~360 c | Jameson's matrix patched once a frame |
| project (divide by z) | 56 c (log/antilog, ≤ ~2% error); 73 c (reciprocal table × quarter squares) | Master Elite LL28; boom `calc_gradient` |
| edge into per-row tables | 14 c a row steep, ~30 shallow | Solid Elite phase A |
| edge as per-column transitions | 31 c a column flat, 71 steep (two lines high) | boom `drawline.6502` |
| span set-up | ~167-180 c a row (two masked ends + entry) | Solid Elite, BEEB-NICCC, Sentinel |
| whole bytes | 4 c (`STA abs`), 5 c (`STA abs,X/Y`) | Solid Elite Tube host; everywhere |
| fill a 128×128 view, every byte once | ~39K (EOR then STA) | PORTAL |
| clear | 5-5.3 c a byte, or none | everywhere; PORTAL and Solid Elite avoid most of it |

## 1. Rich Talbot-Watkins (waitingforvsync)

### What's new since 2026-10-18

- **The boom repository has no commits since 2025-11-17** (2c709dc, "change of approach from polar
  (angle-based) capture to transformation-based capture") **[source: `git log`]**. Its README is still
  one line. Its source draws a fixed four-edge test scene (`src/capture.6502:4-64`); the portal walk
  itself isn't in it.
- **[boomed](https://github.com/waitingforvsync/boomed)** (2026-01 to 2026-02) is the start of a C++
  map editor for the engine: GLFW, vec2/mat22/box2 maths, an empty `world` struct
  (`src/src/world/world.h`). Nothing about the map format yet **[source]**.
- **Newer builds exist only as disc images** in
  [waitingforvsync.github.io/beeb](https://github.com/waitingforvsync/waitingforvsync.github.io/tree/main/beeb)
  ("Dumping ground for disk images"), with no source **[source]**:

| Disc | Uploaded | What it shows | Rate in jsbeeb (Model B) |
|---|---|---|---|
| `portal.ssd` | 2026-10-01, replaced 2026-10-16 | the portal engine: walls, floor and ceiling in dithers, a scaled Cacodemon sprite and a weapon, 128×128; needs sideways RAM | **12.9fps** (130 flips in 500 fields) on a static scene |
| `camera.ssd` | 2026-08-21 | a moving camera over a field of flat-shaded boxes on a dithered sky and floor, 128×128 | 33.0fps (330 flips in 500 fields) |
| `spritescale.ssd` | 2026-08-25 | ten scaled Cacodemon sprites on a moving camera, 128×128 | 16.4fps |

The rates are **[measured]**: each disc booted on jsbeeb's `B-DFS1.2` (`/home/matthew/dev/jsbeeb`
c1c27525) through `MachineSession`, run 10 s to settle, then every CRTC R12 write logged for 500
fields. All three write R12 only to flip between two buffers (values 12 and 14: &6000 and &7000),
so writes per second are frames per second. PORTAL's scene doesn't respond to the cursor keys or
Z/X, and its two screenshots 10 s apart are identical, so 12.9fps is its rate for that one view.

### PORTAL (2026-10-16 build): measured

Run and read in jsbeeb as above; nothing here is from source, which isn't published.

- **Memory.** `$.PORTAL` loads at &1200, 22,615 bytes, entry &65DE; `!BOOT` checks for sideways RAM
  ("PORTAL needs sideways RAM") **[measured: DFS catalogue and `!BOOT` bytes]**. Screens at &6000
  and &7000, 4K each (MODE 5 layout, 32 columns × 16 character rows, one page a character row)
  **[measured: R12 values and the fill's store addresses]**.
- **Where the time goes** (PC-sampled, cycles by address over 100 fields, 3,993,599 cycles)
  **[measured]**:

| Address range | Share | What runs there (from disassembly) |
|---|---|---|
| &B6C0-&BC02 (sideways RAM) | 25.1% | the screen fill: its column driver and two generated column runs per buffer |
| &9000-&9FFF | 24.0% | geometry: quarter-square products `LDA (p),Y : SBC (q),Y` as in boom (&9747-&975D, 1.8%), comparisons and per-edge tables at &0400-&06FF |
| &A000-&AFFF | 12.9% | edge plotting into the transition buffer (`LDA col : EOR (p),Y : STA (p),Y`, &A3C0-&A401: 2.1%), set-up |
| &1400-&18FF (main RAM) | 17.2% | the sprite's column renderer (&1560-&17BF: 12.6%) |
| &8000-&8FFF | 7.9% | clearing the used transition bytes (`LDA #0 : STA (p),Y : INY : STA (p),Y`, &8C3B-&8C4C: 1.2%), more geometry |
| everything else | ~10% | |

- **The fill writes every screen byte once, with no screen clear.** Edges are EOR-plotted into a
  separate 4K **transition buffer** at &4F00-&5EFF laid out like the screen. Each byte column is
  then filled by generated code that reads that buffer and writes the screen:

  ```
  &B785  EOR &4F00,X   ; 4  one line's transitions (X = column × 8 + line parity)
  &B788  STA &6000,X   ; 5  the screen byte
  &B78B  EOR &4F02,X   ;    lines step by 2: even and odd lines are separate dither streams
  &B78E  STA &6002,X   ;    ... 9 c a byte, 64 lines of one parity
  ...
  &B996  STA &6C02,X   ;    the plain-store run, entered after the column's last transition
  &B999  STA &6C04,X   ;    ... 5 c a byte to the bottom
  ```

  The EOR run is ended by an RTS planted at the column's last transition row (`LDA #&60 : STA`
  into the run, put back to &5D afterwards, &B706/&B71C), and the column then JSRs into the
  `STA abs,X` run at that row, so rows below the last edge cost 5 c, not 9
  **[measured: disassembly of &B6C0-&B790, &B980-&BC02]**.
- **Write counts over two frames** (one into each buffer), logged with jsbeeb's write hook
  **[measured]**:
  - each 4,096-byte screen: **4,620 writes; 3,572 bytes written once and 524 twice** (the sprite and
    weapon, drawn over the fill), none unwritten;
  - the transition buffer: 1,382 writes over the two frames (about 690 a frame), touching 416 of
    its 4,096 bytes.
- **The sprite** is drawn per byte column by merging the four pixel columns' span lists (a list a
  pixel column at &2A00, the next boundary in each of four zero-page bytes, the smallest taken)
  **[measured: &16F8-&17B7]**. The runs it writes, two lines a step:
  - one colour on both lines: `STA (p),Y : DEY : STA (p),Y : DEY`, 23 c for 2 bytes (11.5 c a byte);
  - a dither: `LDA a : STA (p),Y : DEY : LDA b : STA (p),Y : DEY`, 29 c for 2 (14.5);
  - some pixels transparent: `LDA (p),Y : AND keep : ORA ink : STA (p),Y`, 45 c for 2 (22.5)
    **[measured: &1573-&15D1, loop overhead `BMI/DEX/BPL` included]**.
- **Frame cost** **[inferred from the profile]**: 12.9fps is 3.87 fields, ~154.5K cycles a frame on
  a Model B: the fill ~38.8K (25.1%, close to boom's 37.6K EOR pass, but with no 21.8K clear), the
  sprite ~19.5K, edge plotting ~3.2K and the transition clear ~1.9K. **The rest, ~90K, is
  visibility, transform and set-up**: on this scene the maths, not the pixels, sets the rate.

### boom (repository, 2025-11-17): the pipeline

**Screen and buffers.**
- MODE 5 pixels (ULA &C4), R1 = 32, R6 = 16: 128×128, 4K a buffer, 256 bytes a character row
  (`src/entry.6502:43`, `:184-198`, `src/defines.6502:1-2`) **[source]**.
- Buffers at &1800 and &7000, both main RAM (`src/defines.6502:44,63`). The flip is R12 alone
  (both 2K-aligned), written by an IRQ that a System VIA T1 fires one line before the top of the
  view, synced to the cycle at start-up (`src/entry.6502:58-121`, `src/irq.6502:57-104`)
  **[source]**.
- A second IRQ at the bottom switches R12 to a 3-row HUD at &800 and loads its own palette (a
  vertical rupture: R4/R6/R7 rewritten each half) (`src/irq.6502:10-42`) **[source]**.
- **Dithered colour.** 22 colours from MODE 5's four, each a 4×2 pattern: `colourtab0` for even
  lines and `colourtab1` for odd (`src/indexeddata.6502:27-86`). The fill runs even and odd lines
  as separate EOR streams so that each stream carries its own dither byte **[source]**.

**The frame loop** (`src/main.6502:18-69`) **[source]**: capture (visibility; still a test) →
wait until the back buffer is off screen → clear → render edges → fill → flip → timer bars.

**Map format** (`src/demomap.6502`, `src/map.6502`) **[source]**:
- 16-bit vertices (x, y split into lo/hi tables);
- **contours**: closed lists of vertex indices, each edge with a neighbouring **subzone** (0 = solid
  wall) and an edge colour: a 2D polygonal map where an edge to another subzone is a portal;
- **subzones** (convex areas), each in a **zone** with floor and ceiling heights and colours;
- the map's tables are reached through operands patched at load (`initialise_map`,
  `src/map.6502:5-66`), so every map read is `LDA abs,X`, not `(zp),Y`;
- a subzone cache (`initialise_subzone`, `clear_subzone_cache`) gives each subzone visited this
  frame a slot.

**Visibility.** The engine walks subzones through portals; the clipping window is two lines,
"the lower line" and "the upper line" (`src/capture.6502:67-99`). The last commit replaced
angle-space clipping (`src/unused/getworldangle.6502`, `clippeddistance.6502`,
`distancealongray.6502`: atan and sine tables, a 16-bit arctan by reciprocal and quarter squares)
with a view transform (`src/mulsin.6502`) **[source]**. The capture code itself isn't in the
repository.

**Maths** (all built at start-up by `src/buildtables.6502`) **[source]**:
- quarter squares f(x) = ⌊x²/4⌋ for x = 0..511 and f(x - 255), 2K at &400-&7FF, &B00-&CFF
  and &1100-&12FF (`src/defines.6502:25-33`); products by `LDA (lo_ptr),Y : SBC (neglo_ptr),Y`,
  with the pointers set to the multiplier;
- a 256-entry 16-bit reciprocal table, 65536/x (`:44-64`);
- a 128-entry sine table for 0-180° from run-length deltas (`:66-98`);
- `calc_gradient` (`src/gradient.6502`): dy × (65536/dx) as an 8.8 slope, **73 c + JSR**
  **[measured]**;
- `mulsin16` (`src/mulsin.6502`): a 16-bit value times sin(angle), with the pointers set from the
  sine **[source]**.

**Edges: one EOR transition per pixel column** (`src/drawline.6502`) **[source]**:
- each edge carries the XOR of the colours above and below it (`line_colour0/1`), so EOR-ing it
  in turns one fill colour into the other;
- every pixel column gets a transition two lines high (one even, one odd), `AND linecolours,Y :
  EOR (write),Y : STA (write),Y` with the pixel's mask;
- **steep edges** (≥ 2 rows a column) step a column at a time: **71 c a column** without a
  character-row crossing, ~22 c more with one (`:87-119`) **[measured]**;
- **shallow edges** take a byte (4 pixel columns) at a time: four DDA steps build a 4-bit shape
  index, and a table of pre-drawn blocks (`src/linesprites.6502`) gives the masks for each row the
  byte's run touches. A flat run costs **~123 c a byte, 31 c a column**; up to 8 rows a byte near
  1:2 (~52 c a column) (`:170-215`) **[measured]**.

**Fill and clear** (generated at start-up: `src/buildcode.6502`) **[source]**:
- fill: per X (column × 8 + parity), `LDA row0 / EOR rowN,X / STA rowN,X` down 64 rows of one
  parity, 9 c a byte; 64 passes: **37,568 c for 4K** (`:20-60`) **[measured]**;
- clear: 16 × `STA abs,X` + `INX : BNE`: **21,765 c for 4K**, 5.3 c a byte (`:83-97`)
  **[measured]**;
- together **~59.3K c a frame whatever the scene**: 1.49 fields, leaving ~20.5K for everything else
  at 25fps **[inferred]**. PORTAL's separate transition buffer removes the 21.8K clear.

**The HUD and timer bars.** The 3-row HUD shows profiling bars: each `starttimer`/`endtimer`
pair reads User VIA T2 (`src/timerbars.6502:14-32`) **[source]**.

**Frame rate.** None stated anywhere. The test scene is four full-width edges, ~10-20K cycles, so
fill + clear + edges is ~70-80K: about two fields **[inferred]**. The snap beebasm here couldn't
write its disc image into the scratchpad, so it wasn't run.

### Other waitingforvsync repositories

None of the others is 3D: baron (the assembler), os1.20, beebcrunch, nevryon, flow (sprites),
spritescale (May 2026: a sprite scaler in BeebAsm, one commit; perhaps where the discs' scaled
sprites began), tawny and tawny-cpp (emulators), richc (a C library)
**[source: `gh repo list waitingforvsync`]**.

## 2. Eben Upton (ebenupton)

### What's new since 2026-10-18

Two new repositories, both filled 3D on the BBC **[source: `gh repo list ebenupton`]**:

- **[solid-elite-bbc-master](https://github.com/ebenupton/solid-elite-bbc-master)** (created
  2026-10-20, 576 commits): BBC Master Elite with filled, sunlit ships and solid planets.
- **[solid-elite-6502-second-processor](https://github.com/ebenupton/solid-elite-6502-second-processor)**
  (created 2026-10-26, 884 commits): the same game on a 6502 Second Processor, the BBC (Master or
  Model B) as a "dumb renderer" host.

No commits to doom (last 2026-09-05), virus (2026-07-07) or doom-z80 (2026-09-06); lander's last
are 2026-10-17, already covered. No Freescape-like or filled Doom work is public.

### Solid Elite for the BBC Master

**Machine and screen** **[source: `docs/renderer.md:14-34`]**:
- Master 128 with sideways RAM in banks 4-7 (it refuses to run without);
- custom MODE 1, 256 wide, one fixed palette (black, cyan, magenta, yellow); a face's colour is a
  **4×4 Bayer dither** of the four inks;
- space view 192 lines at &4000-&6FFF (12K) in **main and shadow RAM: the same address in both
  buffers**, ACCCON X choosing the one written and D the one shown; dashboard in shadow &7000;
- a timer-1 IRQ phase-locked once to vsync sets ACCCON D in line 191's horizontal blanking
  (64-cycle window; measured 45-55 c latency over 62,000 frames) (`:36-66`).

**The frame** **[source: `docs/renderer.md:68-163`]**:
1. the game logic runs unchanged, and its drawing routines' hooks record what they would have
   drawn (ships as their part-6 inputs, 29 bytes a ship);
2. at the end of each iteration the frame layer waits for the previous flip, erases the old stars,
   updates the planet/sun disc rows incrementally, then **fills the ships far to near**, each
   projected as it is drawn, each face a dithered convex polygon in its lit shade; lines,
   particles, flare, text, then stars only into wholly black bytes;
3. flip at the next vsync, **capped at 25fps** (a frame shows for at least two fields).

**Visibility**: painter's order between ships (sorted far to near), back-face culling within a
ship (convex, so the visible faces don't overlap); faces are rebuilt from the blueprints' edges by
`2-build-files/faces.py`, with coplanar faces merged and fins split out (`docs/renderer.md:914-925`)
**[source]**.

**Lighting**: per face `round(31 × max(0, n·L))` with exact quarter-square products, picking one of
32 shades in one of nine shared ramps (`docs/renderer.md:409-428`) **[source]**.

**The polygon fill, `R_POLY`** (`1-source-files/main-sources/gfx-raster_poly.asm`) **[source]**:
- ≤ 16 vertices; an 8-bit fast path when every coordinate is 0-255 (`:13-46`), else a 16-bit phase A;
- **phase A** walks both chains from the top vertex into per-row left and right tables with an
  exact DDA, x = x0 + ⌈dx·k/dy⌉ (one 8-bit divide an edge, `r_dvq`), in self-patched loops:
  `STA tab,Y : INY : ADC #a : CPY #end : BCC` = **14 c a row** for |dx| < dy, ~29-31 c a row for
  shallower edges (`:419-466`) **[measured]**;
- **phase B** fills each row: a left partial byte by read-modify-write with a mask (`LDA (p),Y :
  EOR col : AND mask : EOR (p),Y : STA (p),Y`, 23 c), then `JSR` into the character row's
  **row-run page** (64 × `STA abs,Y`, Y = the line) with an RTS planted after the span's last
  whole byte (kept planted while successive rows end in the same byte), then the right partial
  byte (`:470-711`);
- per row **~167 c fixed** (both partial bytes, dirty extents, entry, plant check, row step) **+
  5 c a whole byte** **[measured: counted from `:521-580`, without a replant (+22 c)]**;
- even and odd rows take different colour bytes, toggled every row pair: the 4×4 dither
  (`:278-310`, `:711-718`).

**Erase**: per row and buffer, the dirty extent (leftmost and rightmost byte touched); the next
frame on that buffer blacks what nothing new covers, through the same row runs, 5 c a byte
(`docs/renderer.md:152-153, 204-205`; `SOLIDSPAN-REPORT.md:41-43` in the second-processor
repository) **[source]**.
**Kept solid rows**: near the station, a row that one face covered last time on this buffer is
left alone, or only its changed ends are written: docking 7.6-10.6% faster, single frames up to
27% (`docs/renderer.md:374-407`) **[source]**.

**Speed** **[source: second-processor README, "Speed"; master `docs/renderer.md:949-964`]**:

| Window (main-loop iterations a second = frames a second) | Original SNG47 (wireframe) | Solid Elite, Master |
|---|---:|---:|
| flight (iterations 1000-1400) | 12.69 | 12.30 |
| docking (3420-3550) | 12.61 | 7.05 |
| beach-ball planet approaches | 8.11 / 9.09 | 6.46 / 5.84 |
| the gate's whole flight run | 13.97 | 11.13 (179,751 c an iteration) |
| the gate's run with plain disc planets | | 17.24 (115,992 c) |

At docking, with the station across the screen, about 550 spans a frame and 301K cycles an
iteration; bytes written a docking iteration 15,065, of which 14,060 through row runs, 437 runs
entered (`TUBE-REPORT.md:1275-1282`) **[source]**.

**The game's multiplies** are quarter squares (`elite-qs.asm`: ⌊n²/4⌋ for n = 0..511, 1K,
page-aligned) with the fixed factor patched into the operands:
`CPX #b : BCC : LDA QSL+b,X : SBC QSL-b,X : STA P : LDA QSH+b,X : SBC QSH-b,X`, **23 c** for an
8×8→16 product once b is patched (`elite-source.asm:14270-14290`) **[measured]**. The five
multiplies rewritten this way, plus the divides' common cases, saved 31,377 c an iteration (22%)
(`docs/speedups.md`) **[source]**.

### Solid Elite on the 6502 Second Processor

- The whole game and the rasteriser's bookkeeping run on the parasite (65C02, 3MHz, or the
  Master's internal 4MHz 65C102); the BBC draws lines, points, **spans**, text and the dashboard,
  streamed through Tube register 1 **[source: README]**.
- **Master host**: two buffers at &4000 (main and shadow), spans through **37.6K of straight-line
  `STA abs` runs** in sideways RAM, 192 lines × (64 × `STA abs` + RTS), **4 c a byte**; fixed cost
  47 c a span against the row runs' 50 (`TUBE-REPORT.md:754, 1249-1293`) **[source]**.
- **Model B host** (64K sideways RAM): buffers at &1000 and &4000, a set of row runs per buffer
  (75K for full `STA abs` runs for two buffers at different addresses wouldn't fit), the dashboard
  split by a CRTC vertical rupture **[source]**.
- **Speed** **[source: README]**: flight / docking / beach-ball:

| | Flight | Docking | Beach 300-403 |
|---|---:|---:|---:|
| Tube, Master host, 4MHz parasite | 21.59 | 10.75 | 10.58 |
| Tube, Model B host, 3MHz parasite | 17.77 | 10.21 | 8.72 |

- Host busy 41% in flight, **78% at docking**: filling, not maths, is the limit up close
  (`TUBE-REPORT.md:785-787`) **[source]**.
- "Phase 4", writing each screen byte once by merging spans per row against a model of both
  buffers, was not built: no room on the parasite; computing coverage instead cost the parasite
  ~64K cycles to save the host ~38K (`TUBE-REPORT.md:1226-1227`)
  **[source]**.
- Full `STA abs` runs over row runs (`STA abs,Y`): 1 c a byte saved, ~6,200 c an iteration at
  docking (~2%), nothing in flight (`TUBE-REPORT.md:1275-1282`) **[source]**.

### Lander (re-checked)

**[source: `README.md` "How it works"; `src/land.s:95-125`; `tools/landgen.py:15-40`]**
- Model B + 64K sideways RAM, MODE 1 256×160 (10K a buffer, &3000 and &5800), flip by R12;
  ~10fps, capped at 12.5.
- The landscape is drawn as strips far to near (painter's), **each byte column of a strip filled
  top to floor** through unrolled store tables entered at the first line and ended by a planted
  RTS; a column no rung crosses is one box.
- Store tables `STAB`: `STA line,Y` (Y = 8 × column within a half-row of 32 bytes) then `LDA vo`
  after even lines and `TXA` after odd: **7 or 8 c a byte, 7.5 average**, for a 2×2 dither;
  `run2` stores even lines then odd lines in two passes through one-parity tables: **5 c a byte**
  plus two entries **[measured: from the tables' description]**.
- Erase: per screen and column, the land's highest and lowest line last time; only what's gone is
  blacked.
- The projection is baked: rows at fixed depths, y for every height and x for every camera
  fraction in tables, so "projecting a frame is table lookups and additions with no multiplies".

### DOOM (wireframe; for its visibility, re-checked)

**[source: `README.md:20-50, 82-87`]** A Model B with sideways RAM, MODE 4 256×160, ~7fps.
Hidden-surface removal is analytical: the visible region is a linked list of up to 32 trapezoid
spans with linear top and bottom edges; solid walls `mark_solid` a column range, portals
`tighten` the aperture, and the BSP walk prunes subtrees with `has_gap`/`is_full`. Vertices go
through an s24 view transform built from one 8×8→16 quarter-square multiply and a 9.1 reciprocal
table. Translation coherence (vertex view coordinates shift by one per-frame constant between
same-angle frames) replaces a 1,100-cycle transform with six loads and adds.

## 3. Kieran Connell (kieranhj)

### stnicc-beeb (BEEB-NICCC), v1.2 of 2026-10-19: new since 2026-10-18

The STNICCC-2000 polygon stream on a Model B: screen-space 2D convex polygons (≤ 7 vertices), so
no transform or projection in its costs, but the purest measure here of a span-fill rasteriser.

- **Machine and screen.** Model B with an 8271; the stream comes off a double-sided disc as raw
  tracks; 16K sideways RAM for music; VideoNuLA optional. MODE 5 (ULA &C4), R1 = 32, R6 = 25:
  128×200, 256 bytes a character row, buffers of 6,400 bytes at &6700 and &4E00. The default
  ("LOW") player draws 128×100 on even lines only (`stnicc-beeb.asm:161-171, 1077-1091`;
  `src/plot_spans_fast.asm:9-14`) **[source]**.
- **Order.** Painter's, in stream order, ~40 polygons a frame, 1.24× overdraw; v1.2's encoder drops
  1,353 polygons hidden in every frame and adds per-polygon row trims and per-frame clear masks
  (`docs/cpc-column-stream.md`; commit 2d3e5f6) **[source]**.
- **Edges.** Into per-line start/end tables (256 bytes each at &E00/&F00) by Bresenham walkers:
  28 c a row steep, 35 c on rows with an x step **[measured: from the loop in
  `src/plot_poly_fast_steep.asm`]**.
- **Spans** in four passes, one per (y AND 3), so the dither byte and the scanline stay fixed while
  the pointer steps a page a row (`src/plot_spans_fast.asm:60-74`) **[source]**. Ends by masked
  RMW, 22 c a byte; whole bytes by a computed `JMP` into one unrolled block of 32 × `STA abs,Y` per
  character row and screen (4,950 bytes), 5 c a byte.
- **Per row: 169 + 5n c** for n ≥ 1 whole bytes, 86 c for a one-byte row, 123 c for two
  **[measured: `src/plot_spans_fast.asm:76-154`, re-counted by us]**. The fixed part equals 34 bytes
  of fill. The CPC build's profile: per-row set-up 58%, edges 28%, stores 13%
  (`docs/cpc-column-stream.md`) **[source]**.
- **Clear.** 25 × `STA abs,X` a pass: ~16.9K for 3,200 bytes (5.3 c a byte); v1.2's masked clear
  costs 212 c per flagged 32-byte row and 21 c per skipped one, as the polygons leave only ~378 of
  3,200 bytes uncovered (`src/screen.asm:12-114`; commit 10d112b) **[measured/source]**.
- **Rate.** 900 frames: 2020 release 8,804 fields (5.1fps); **v1.2 6,485 fields (6.9fps)**, ~236K
  cycles a frame of rendering; render 81% of wall time, disc NMI 6%, waiting 6%, music 5%
  (`tools/harness/baseline.json`; commits 3dba802, c30558b, 799cfd8) **[source]**.
- **Design notes.** A two-chain scanline filler was modelled and rejected ("saves little over the
  span buffer"); a column-stream redesign is parked at an estimated 75-80K cycles a frame; its
  doc puts an XOR fill at 9-10 c a byte against 5 c for `STA abs,X` (`docs/cpc-column-stream.md`)
  **[source]**.

### scr-beeb (Stunt Car Racer, Master 128, last commit 2021)

- Master only (65C12, sideways RAM, HAZEL, ANDY). MODE 5 in game, two 8K buffers at &4000/&6000
  in the C64 bitmap layout, a 128-pixel 3D window in a three-part CRTC split
  (`scr-beeb.asm:1315-1316`; `game/kernel-ram.asm:7860-7870`; `game/beeb-code.asm:31-260`)
  **[source]**.
- **No polygon fill.** The track is drawn front to back as lines against a per-column floating
  horizon; the window is cleared and the sky filled down to the horizon in each column
  (`kernel-ram.asm:7944-7958`; `cart-ram.asm:4613-4730`) **[source]**. Its pixel loop is 57 c a
  visible pixel and 31 c a hidden one; the BBC-only sky fill is 10.9 c a byte, column-wise through
  `(zp),Y` **[measured]**.
- **Maths.** Projection is x/z = antilog(log x − log z) with log tables in HAZEL
  (`hazel-ram.asm:461/480`, `core-ram.asm:27-110`); the multiply is a squares-table
  ab = (a² + b² − (a−b)²)/2 at ~100 c, slower than the 4-table quarter-square ~55 c **[source;
  measured]**. No frame rate is stated.

### Other kieranhj repositories

No other BBC filled 3D: line-test (line routines), beeb-port-kit, raster-fx, funky-fresh, 256-beeb,
stipple-256, beebgame (a fork), elite-beebasm (wireframe); stniccc-archie, archie-verse and globe
are Archimedes **[source: `gh repo list kieranhj`, grep]**.

### llm-beeb-wiki

It has **no pages** on polygon fill, EOR fill, span fill, edge tables, division, projection or a
3D pipeline; `techniques/division` is requested but unwritten **[source: the wiki's repository]**.
What it has, with the errors found against code:

- `techniques/multiplication.md`: shift-add ~113 c; quarter squares with 4 tables ~55 c and 1K
  (re-counted: 55 c with RTS); 3 tables ~67 c and 768 bytes.
- `techniques/fixed-point.md`: base-127 fixed point, S8×S8 ~58 c, S15×S8 ~170 c. Wrong: "9 ×
  S15_x_Fixed = ~1530c … hundreds of vertices" a frame (1,530 c a vertex is ~26 vertices a field
  for the rotation alone); a "127/n LUT gives a/b in ~70c, one-byte-precise" (127/n rounds to 1
  for every n ≥ 85, up to 33% error); S15×S8 called a "perspective divide".
- `techniques/bresenham-line.md` (already used in beeb.md §1), with two arithmetic slips: "RTW
  260c beats NJ 240c" on a 5-pixel line, and the open-endpoint saving for a closed 4-gon (3
  re-inits, 90 c, not 4 × 30).
- `techniques/copper-bars.md`: "10,240 cycles" to fill 20,480 bytes of MODE 0 is 0.5 c a byte; at
  5 c it's ~102K, 2.6 fields. `fast-animation.md`'s `LDA/STA (zp),Y` loop is 16 c a byte, not 15.
- `video/plot-codes.md`: the MOS's PLOT 80-87 triangle fill and the Master's fills, with no costs.
- `memory/shadow-ram.md`: Master double buffering by ACCCON D in the vsync handler.

These are **[source: the wiki's pages]**, with our re-counts **[measured]**.

## 4. Other solid 3D on the BBC

### The Sentinel (Geoff Crammond, 1986; [thesentinel.bbcelite.com](https://thesentinel.bbcelite.com))

All **[source: Mark Moxon's deep dives]** unless tagged.
- **Screen.** A MODE 5 derivative, 160×200 in 4 colours, 8K at &6000-&7FFF, hardware-scrolled; the
  landscape view is 160×192 (deep dive "the custom screen mode").
- **Order.** Painter's: tile rows back to front, each row drawn from both outer edges inwards
  towards the viewer; objects with their tile, stacks back to front; a self-overlapping object
  takes a two-phase polygon order. A tile-visibility table, precomputed by ray-casting, skips
  hidden empty tiles ("drawing the landscape view", "drawing 3D objects").
- **Culling.** A polygon is dropped if its top lies below its bottom, or its middle span has right
  < left ("drawing filled polygons").
- **Projection.** Equirectangular, as in Revs: yaw and pitch angles map straight to screen x and y
  through an arctan table on a 16/16 divide's output; 28.125° field of view ("the projection
  system").
- **Fill.** Edges traced into one-byte left/right tables (wide polygons in two parts); edge bytes
  read-modify-written in a separate edge colour; the interior an unrolled `LDY #8*n : STA (P),Y`,
  entered by a self-modified branch: **8 c a byte (2 c a pixel)**, ~180 c a line of overhead
  (part 2 ~25, right edge ~59, left edge ~57, entry ~39) **[measured: counted from
  DrawPolygonLines parts 2-4]**.
- **Buffering.** A full redraw happens under an all-blue palette; a pan draws a 64×192 or 160×64
  strip into an off-screen buffer, which the IRQ scrolls in at 50Hz ("screen buffers", "panning
  and hardware scrolling"). No time for a full screen is given.

### Revs (Crammond, 1985; [revs.bbcelite.com](https://revs.bbcelite.com))

- Custom screen: mostly MODE 5 with a MODE 4 top, five palette bands, 7 colours on screen, at
  &5A80-&7AFF (8,320 bytes); an 80-line track view **[source]**.
- Edges only go into 40 one-byte-wide "dash data" columns (36-77 bytes each, shaped around the
  dashboard); cars and signs paint whole bytes **[source]**.
- The copy-and-fill is 40 unrolled `DRAW_BYTE`s a line: `LDY dash,X : BEQ : LDA #0 : STA dash,X :
  LDA zeroIfYIs55,Y : LDY #col : STA (P),Y`: **15 c** where a byte repeats the colour above, **25 c**
  at an edge byte, which it also zeroes **[measured; confirms beeb.md's 15-25]**. A frame
  copies 1,440-3,080 bytes, ~22-48K cycles **[inferred]**.
- No stated frame rate; the race timers add 9/100 s a main-loop pass, which suggests ~11fps
  **[inferred: "scheduling tasks in the main loop"]**.

### Nick Jameson's 3D demo (1994; [simondotm/bbc-micro-3d](https://github.com/simondotm/bbc-micro-3d))

- Quarter-square multiplies from 1.5K of overlapped tables (the origin of TobyLobster's
  mult65/66), an 8-bit perspective-factor table (`&FF*d/(d+oz+Z)`), screen-space hidden-surface
  removal, cached transformed vertices and visible faces **[source: README, `source/maths.asm`]**.
- **The solid mode is the transition-buffer EOR fill PORTAL uses**: edges are drawn as top-most
  pixels into a back buffer, then a fully unrolled pass does
  `EOR back,X : STA front,X` down each column into the screen, 9-10 c a byte over a 96×192 window
  (4,608 bytes, ~41K), and the back buffer is wiped at ~5 c a byte (~23K)
  (`source/renderer.asm:56-80`) **[source; measured]**.
- One convex model, ≤ 16 faces, 3 colours; no stated frame rate.

### Aviator, and searches that found nothing

- Aviator's deep dives cover lines, points, line buffers and colour-cycling animation; no fill
  **[source]**.
- `gh search repos` for "bbc micro 3d", "6502 polygon fill", "bbc micro raycaster" and the like found
  only simondotm/bbc-micro-3d; no BBC raycaster turned up; Stardot isn't indexed by the search
  engines **[source: our searches]**.
- For scale: the C64 Driller's converter recalls "Frame update was about once per second on 8 bit
  machines" ([ianandrew.com](https://www.ianandrew.com/copy-of-splat)) **[source]**.

## 5. 6502 maths at the limit

Cycle counts include the RTS and not the JSR, as TobyLobster's tables do. All the routines are
NMOS code, and none would get faster on a 65C12 (no instruction they use changes timing there)
**[inferred]**. TobyLobster has no division benchmark (`gh repo list TobyLobster`: only
`multiply_test` and `sqrt_test` are maths) **[source]**.

### Multiplication

From [TobyLobster/multiply_test](https://github.com/TobyLobster/multiply_test) (README tables at
`README.md:191-367`, `results/results_*.json`, `tests/*.a`) **[source]** unless tagged:

| Routine | Operation | Cycles avg (min-max) | Bytes | Method |
|---|---|---|---:|---|
| mult66 (from Nick Jameson's 1994 code) | u8×8→16 | 45.49 (44-47) | 1,580 | ⌊x²/4⌋ tables through `(zp),Y` pointers |
| mult14 (JackAsser) | u8×8→16 | 45.99 (44-48); **27.99 with the multiplier fixed** | 2,077 | sum and difference tables, operands patched |
| mult65 (Jameson's original) | u8×8→16 | 47.49 (45-50) | 1,061 | `(zp),Y` |
| smult11 (Fusik variant) | s8×8→16 | 51.99 (50-54) | 2,334 | signed-offset square tables, patched |
| smult8 / smult1 | s8×8→16 | 62.99 (56-70) | 1,068 / 2,095 | unsigned + sign fix-up |
| mult86 (Repose) | u16×16→32 | 187.07 (177-203) | 2,170 | four `(zp),Y` pointers into square tables |
| smult12 | s16×16→32 | 234.57 (207-268) | 2,210 | mult86 + sign fix-up |
| omult31 | u24×8, high 24 bits | 168.90 (161-181) | 2,162 | patched squares |
| omult9 (Krill) | 8×8, high byte, approximate | **22.97** (22-23) | 780 | log/exp tables; error −5..+5, 41,848 of 65,536 exact |
| omult11 | 8×8, high byte | 43.00 (40-46) | 547 | squares, high byte only; ±1 |
| omult7 (Master Elite's FMLTU) | 8×8, high byte | 46.72 (max 47) | 802 | log; −6..+1 |
| omult8 (6502SP Elite) | 8×8, high byte | 49.20 (max 50) | 1,075 | log + odd antilog; −3..0 |

**Amortised: a multiplier reused across many products** (a matrix entry times every vertex):

- mult14 with its four operands patched once per multiplier (`STA sm1 : STA sm3 : EOR #&FF : STA
  sm2 : STA sm4`, 18 c) leaves **~22 c a product inline** (20-24 with page crossings)
  (`tests/mult14.a:36-50`) **[measured]**:

  ```
  SEC                  ; 2
  LDA sq1_lo+M,X       ; 4 (+1)
  SBC sq2_lo+~M,X      ; 4 (+1)
  TAY                  ; 2
  LDA sq1_hi+M,X       ; 4 (+1)
  SBC sq2_hi+~M,X      ; 4 (+1)
  ```

- Solid Elite's game multiplies do the same with a 1K table (⌊n²/4⌋, n = 0..511) and a compare
  for |a| < b: **23 c** (`elite-source.asm:14270-14290`) **[measured]**. boom and PORTAL use the
  `(zp),Y` pointer form: 4 indirect loads, ~22 c, the pointers set once per multiplier (14 c)
  **[measured: `src/gradient.6502`, PORTAL &9747-&975D]**.
- High byte only: `LDA (p1),Y : SEC : SBC (p2),Y`, **12-14 c**, up to 1 low from the dropped borrow
  **[measured from codebase64's perspective page; error inferred]**.
- Signed: storing coordinates biased (EOR #&80) lets a signed product cost what an unsigned one
  does, ~22 c **[inferred]**.
- 16×8→24 has no table entry; built like mult86, about 14 c set-up + 2 × 22 + ~10 combine ≈ 70 c
  **[inferred]**.

**Rotation.** Jameson's transform patches the nine matrix entries into the operands once a frame
(`bbc-micro-3d/source/maths.asm:313`), so a vertex costs 9 products of ~26 c and six 16-bit adds of
~20 c: **~360 c a vertex** **[measured]**. Eben's DOOM uses only an 8×8→16
quarter-square multiply for an s24 view transform, and translation coherence replaces its
1,100-cycle transform with six loads and adds between frames at the same angle **[source]**.

**Square root** (`TobyLobster/sqrt_test`): sqrt15 (hexwab) averages 33.7 c, worst 87, 512 bytes;
sqrt9 39.8 c, worst 129, 847 bytes, and can share the square tables **[source]**.

### Division, reciprocal and projection

| Routine | Operation | Cycles | Tables | Accuracy |
|---|---|---|---|---|
| Cassette Elite LL28 | 256·A/Q, A < Q | ~167 (8 passes of 18-20) | none | exact, truncated **[measured]** |
| **Master Elite LL28** | 256·A/Q | **56** | `logL`, `log`, `alogh`: 768 bytes | quantised to 1/32 octave: up to ~2.2% low (≈ −6 at 255) **[measured; error inferred]** |
| 6502SP Elite LL28 | same, odd antilog | ~57 | 1,024 bytes | about half the error **[inferred from omult8]** |
| boom `calc_gradient` | dy × 65536/dx (8.8) | 73 | 256-entry 16-bit reciprocals + quarter squares | 16-bit reciprocal, then 8×16 product **[measured]** |
| White Flame 8/8 (codebase64) | 8-bit quotient | 154-170 looped; 106-127 unrolled | 19 bytes code | exact **[source]** |
| codebase64 16/16 | 16-bit quotient | ~790 | none | exact **[measured]** |

Master Elite's LL28 core: `LDA logL,X : LDX Q : SEC : SBC logL,X : LDX widget : LDA log,X : LDX Q :
SBC log,X : BCS : TAX : LDA alogh,X : STA R : RTS`, after a 12 c `CMP Q : BCS : STA widget : TAX :
BEQ` ([LL28](https://elite.bbcelite.com/master/main/subroutine/ll28.html)) **[source]**.

**Projection options** for a world (not one object near a fixed distance):

1. **An 8-bit z through a perspective-factor table** (Jameson): ~14 c a vertex plus 12-14 c a
   coordinate, but 8-bit z only suits a single object near a fixed distance **[measured;
   inferred]**.
2. **Log/antilog** (Master Elite): ~50-56 c a divide, ≤ ~2.2% error: ±1.8 px at the edge of an
   80-pixel half-width **[inferred]**.
3. **Normalised reciprocal** (boom's and DOOM's approach): normalise 16-bit z by its leading zeros
   (~10-15 c), look up a 16-bit reciprocal of the 8-bit mantissa (512 bytes), set one pointer per
   vertex (14 c) shared by x and y, then two partial products and a shift per coordinate:
   **~150-200 c a vertex**, relative error ≤ 2⁻⁸ (~0.3 px at an 80-pixel half-width)
   **[inferred]**. DOOM uses a 9.1 reciprocal table; boom's is 65536/x for x = 0..255.
4. **Baked tables** (lander): a fixed camera pitch and rows at fixed depths make projection pure
   lookups and adds; it doesn't fit free 6-degree movement **[source; inferred]**.
5. **Angles** (The Sentinel, Revs; boom before 2025-11): screen x and y from arctan of a 16/16
   quotient. boom dropped it for a view transform ("No longer requires high precision sine table or
   arctan/angletocolumn tables", 2c709dc) **[source]**.

## 6. Fill strategies compared

### Cycles a byte, from the code read

| Store pattern | c/byte | Who | Notes |
|---|---:|---|---|
| `STA abs`, one instruction per screen byte, entered by JSR with an RTS planted | **4** | Solid Elite Tube, Master host | 3 bytes of code per screen byte: 37.6K for 12K of screen; one set serves both buffers only when they share an address (Master shadow) **[source]** |
| `STA abs,X` / `abs,Y` unrolled down a column or along a row, planted RTS | **5** | boom's clear, Solid Elite's row runs, lander, PORTAL's lower column | ~20-50 c to enter and plant a span **[measured]** |
| `STZ abs,X` (65C12) | 5 | starglider-beeb clears | frees A; no faster than STA **[measured]** |
| `STA abs,Y : LDA zp` / `: TXA` alternating, one run | 7.5 | lander | a 2×2 dither in one pass; two one-parity passes bring it back to 5 **[measured]** |
| `EOR abs,X : STA abs,X` (EOR fill) | **9** | boom (in place), PORTAL (from a transition buffer) | sub-byte pixel columns compose for free; needs zeroed transitions **[measured]** |
| EOR fill in place + full clear | 14.3 | boom | 9 + 5.3 c a byte for the clear, whatever the scene **[measured]** |
| `STA (zp),Y : DEY` pairs | 11.5 | PORTAL's sprite | dither on alternate lines: 14.5 **[measured]** |
| masked RMW, `LDA (p),Y : EOR col : AND mask : EOR (p),Y : STA (p),Y` | 23 a byte | Solid Elite's span ends | the price of a byte two faces share **[measured]** |
| masked RMW in a loop, `LDA (p),Y : AND keep : ORA ink : STA (p),Y` | 22.5 | PORTAL's sprite edges | **[measured]** |

The floor is 4 c a byte (`STA abs`), and 5 c with any index. A fill whose inner loop isn't
unrolled into one store a byte loses at least 2-3 c a byte to the loop.

### The fixed cost of a span

Per-span overhead dominates small faces:
- Solid Elite's phase B: ~167 c a row for both partial bytes and the entry, +5 c a whole byte.
  A face 40 rows high and 20 bytes wide costs ~10.7K, 62% of it overhead **[inferred]**.
- The Tube host's span core: 47 c a span with 4 c stores (`TUBE-REPORT.md:754`) **[source]**.
- boom's edge cost is per pixel column, not per row: 31-71 c a column; the fill then costs the
  same for any scene.

### Screen layouts for a column renderer

The BBC screen is laid out in character rows: within a row, byte column c's 8 lines are 8
consecutive bytes at c×8, and the next character row is R1×8 bytes on.

| R1 (bytes a line) | Modes and widths | Character row | Column addressing |
|---|---|---|---|
| 32 | MODE 5 128px, MODE 4 256px, MODE 1 128px, MODE 2 64px | **256 bytes: one page** | X = c×8 + line covers every column: one unrolled `op page_k+line,X` routine fills any column of a buffer (boom, PORTAL) |
| 64 | MODE 1 256px, MODE 2 128px, MODE 0 512px | 512 bytes | c×8 runs to 504: two halves, so two column routines a buffer (lander's TPE/TPO halves) or a split at column 32 (Solid Elite's RZ_PA/RZ_PB) |
| 80 | standard MODE 0/1/2 | 640 bytes | rows not page-aligned; avoid |

**Pixels a byte.** MODE 2: 2 px a byte (masks &AA, &55), 8 colours (16 with a VideoNuLA); MODE 1 and
MODE 5: 4 px (masks &88, &44, &22, &11), 4 colours; MODE 4: 8 px, 2 colours. A column renderer
works in byte columns, so it must merge 2 (MODE 2) or 4 (MODE 1/5) pixel columns' spans into
each byte.

### Writing each screen byte once

Three ways were found to write each byte once a frame:

1. **EOR fill from a separate transition buffer** (PORTAL). Edges put per-pixel colour-XOR
   transitions in an off-screen buffer laid out like the screen. The fill accumulates them down
   each byte column and stores to the screen, so the 4 pixel columns of a byte merge by
   themselves.
   - Cost: 9 c a byte down to the column's last transition, 5 c below it, plus each edge's
     transitions (31-71 c a pixel column in boom's two-line scheme), plus clearing the
     transition bytes used.
   - Measured: 4,096 screen bytes written once each (4,620 writes with the sprite) and ~690
     transition-buffer writes a frame.
   - It needs a planar partition: every edge in a column must be a real boundary between two
     visible colours. Overlapping objects have to be clipped to their visible parts first (a
     portal walk does that), or the hidden edges' transitions must be cancelled.
2. **Explicit merge per byte column** (PORTAL's sprite, lander's rungs). Each pixel column has a
   sorted span list; the renderer walks the byte column taking the nearest boundary, and writes
   each run once. It costs ~50-100 c per boundary event (&16F8-&17B7) plus 11.5-14.5 c a byte in
   PORTAL. MODE 2's 2 px a byte halves the merging against MODE 1/5's 4.
3. **Rows instead of columns** (Solid Elite's "phase 4", not built): merge each row's spans
   against what the buffer already holds. It wasn't built because it needs a model of both
   buffers' rows.

The layout that makes it cheapest is **R1 = 32 (one page a character row)**: one index register
reaches every byte of a column, so one generated column routine serves a buffer, and on a Master
one routine serves both buffers at the same address in main and shadow RAM **[inferred]**.

### Whole-view fill budgets

Cycles to write every byte of the view once, before edges or maths; a field is 39,936 c
**[inferred: bytes × c/byte]**:

| View | Bytes | `STA abs` 4 c | 5 c | EOR 9 c | EOR + clear 14.3 c |
|---|---:|---:|---:|---:|---:|
| MODE 5 128×128 (R1 = 32) | 4,096 | 16.4K | 20.5K | 36.9K | 58.6K |
| MODE 5 128×160 | 5,120 | 20.5K | 25.6K | 46.1K | 73.2K |
| MODE 1 256×128 / MODE 2 128×128 | 8,192 | 32.8K | 41.0K | 73.7K | 117K |
| MODE 1 256×160 / MODE 2 128×160 | 10,240 | 41.0K | 51.2K | 92.2K | 146K |
| MODE 1 256×192 (Solid Elite) | 12,288 | 49.2K | 61.4K | 110.6K | 176K |

At 25fps (79,872 c) a 128×128 MODE 5 view leaves 43-63K for everything else; a 256×160 MODE 1 view
leaves 29-39K writing every byte once at 4-5 c, and nothing with an EOR fill. This is why every
fast engine here uses either a small window (boom/PORTAL: 4K) or writes only what changed
(Solid Elite's dirty extents and kept rows, lander's column records).

## 7. What to lift for a renderer of convex solids

All **[inferred]** from the above.

1. **A 128-pixel-wide window in an R1 = 32 layout** (MODE 5, or MODE 1 cut to 32 columns). Each
   character row is then one page, so one generated column routine reaches every byte of a buffer
   with X = column × 8 + line (boom, PORTAL). A 4K 128×128 view costs 16-20K to write once at 4-5 c
   a byte, 37K with an EOR fill; 256×160 MODE 1 costs 51-92K.
2. **Dithered colour as two (or four) line-parity streams** (boom's 22 colours from 4×2 patterns;
   Solid Elite's 4×4 Bayer; BEEB-NICCC's four passes by y AND 3). The fill runs each parity as its
   own stream, so each carries its own dither byte at no extra cost a byte.
3. **PORTAL's fill: edges into an off-screen transition buffer, then one pass that EORs them down
   each column into the screen and stores plainly below the last edge.**
   - Every screen byte is written once, with no screen clear, and sub-byte pixel columns compose
     by themselves.
   - Measured on PORTAL's scene: ~39K a frame for 128×128, 4,096 screen bytes each written once.
   - On a Master the two buffers can share an address (main and shadow), so one copy of the
     generated fill serves both.
4. **It needs a planar partition per column**: overlapping solids must be clipped to their
   visible parts before their edges go in. For convex solids:
   - draw objects front to back;
   - keep each pixel column's uncovered interval(s): a floating horizon, as Stunt Car Racer does,
     or DOOM's list of trapezoid spans;
   - clip each face's top and bottom per column to them, and emit transitions only for the
     visible part.
   Within one convex solid, back-face culling alone leaves faces that don't overlap. The other way,
   painter's order with a span fill (Solid Elite, The Sentinel, BEEB-NICCC), costs ~170 c a row
   plus overdraw.
5. **Edges per pixel column, boom-style**: 31 c a column flat (pre-drawn 4-pixel blocks indexed by
   four DDA steps), 71 c steep. A per-column clip naturally works in the same units.
6. **Maths**:
   - quarter squares with the multiplier patched into operands (~22 c a product), the rotation
     matrix's nine entries patched once a frame (~360 c a vertex);
   - a normalised reciprocal for projection (~150-200 c a vertex), or log/antilog (~56 c, ~2%);
   - DOOM's translation coherence: at an unchanged view angle a vertex's view coordinates shift by
     one per-frame constant, so a moving camera needn't re-rotate.
   The axis-aligned cuboids of a Freescape world make faces' normals and many products trivial.
7. **Budget**: in PORTAL, the fill is a quarter of a 155K frame and visibility, transform and
   set-up take ~90K. Once the fill is down to one write a byte, the frame rate is set by the maths
   and the per-edge and per-column set-up.

## Sources

**Repositories read** (cloned 2026-10-31):
- [waitingforvsync/boom](https://github.com/waitingforvsync/boom) (2c709dc),
  [boomed](https://github.com/waitingforvsync/boomed),
  [waitingforvsync.github.io](https://github.com/waitingforvsync/waitingforvsync.github.io)
  (`beeb/portal.ssd`, `camera.ssd`, `spritescale.ssd`),
  [spritescale](https://github.com/waitingforvsync/spritescale)
- [ebenupton/solid-elite-bbc-master](https://github.com/ebenupton/solid-elite-bbc-master)
  (`README.md`, `docs/renderer.md`, `docs/speedups.md`,
  `1-source-files/main-sources/gfx-raster_poly.asm`, `elite-qs.asm`, `elite-source.asm`)
- [ebenupton/solid-elite-6502-second-processor](https://github.com/ebenupton/solid-elite-6502-second-processor)
  (`README.md`, `TUBE-REPORT.md`, `SOLIDSPAN-REPORT.md`, `docs/TUBE-PLAN.md`)
- [ebenupton/lander](https://github.com/ebenupton/lander), [doom](https://github.com/ebenupton/doom),
  [virus](https://github.com/ebenupton/virus)
- [kieranhj/stnicc-beeb](https://github.com/kieranhj/stnicc-beeb),
  [scr-beeb](https://github.com/kieranhj/scr-beeb),
  [llm-beeb-wiki](https://github.com/kieranhj/llm-beeb-wiki)
- [TobyLobster/multiply_test](https://github.com/TobyLobster/multiply_test),
  [sqrt_test](https://github.com/TobyLobster/sqrt_test)
- [simondotm/bbc-micro-3d](https://github.com/simondotm/bbc-micro-3d) (Nick Jameson's 1994 code)

**Web**:
- [thesentinel.bbcelite.com](https://thesentinel.bbcelite.com) deep dives: the custom screen
  mode, drawing the landscape view, drawing 3D objects, drawing filled polygons, the projection
  system, screen buffers, panning and hardware scrolling; DrawPolygonLines parts 1-4
- [revs.bbcelite.com](https://revs.bbcelite.com): hidden secrets of the custom screen mode,
  drawing the track view, drawing around the dashboard, scheduling tasks in the main loop
- [aviator.bbcelite.com](https://aviator.bbcelite.com) deep-dive index
- [elite.bbcelite.com LL28 (Master)](https://elite.bbcelite.com/master/main/subroutine/ll28.html)
  and the deep dive on multiplication and division using logarithms
- [codebase64](https://codebase64.net): 8-bit divide, perspective, 16-bit divide pages
- [bitshifters.github.io BEEB-NICCC](https://bitshifters.github.io/posts/prods/bs-beeb-niccc.html)
- [ianandrew.com](https://www.ianandrew.com/copy-of-splat) (Driller on 8-bit machines)

**Measurements of our own** (jsbeeb at `/home/matthew/dev/jsbeeb` c1c27525, model `B-DFS1.2`,
Node scripts using `MachineSession`; the scripts aren't kept in this repository):
- frame rates: CRTC R12 writes logged by wrapping `video.crtc.write`, over 500 fields after 10 s;
- profile: cycles per PC from `cpu.debugInstruction`, using `cycleCount` from `src/lockstep.js`,
  over 100 fields;
- write counts: `cpu.debugWrite`, between the first and third R12 write;
- disassembly: `cpu.disassembler` on the running image.
