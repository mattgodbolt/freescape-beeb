# Freescape on the BBC Micro: the brief

*Written on 2026-10-31, before any code. The research behind it is in
`docs/research/`: `freescape.md` covers the engine and Driller, from
ScummVM, the Castle Master II disassembly and Driller's ZX data;
`beeb-3d.md` covers the fastest solid 3D on the BBC so far. The scripts
that parsed Driller's data are in `tools/research/`.*

The goal is a Freescape engine for the BBC Micro and Master, as fast as
the machine allows. It's proved on *Driller* (Incentive, 1987): Driller's
own data, its 29 areas and its camera. Run it the way the siblings are run
(`../porting-to-the-beeb.md`).

How to read the tags:

- **[measured]**: we ran it or read the bytes on 2026-10-31. The research
  file names the tool.
- **[source]**: a published source says so. The link is in the research.
- **[inferred]**: our reading or arithmetic. Check it before relying on
  it.

A field is 39,936 cycles. 25fps is two fields, 16.7fps three and
12.5fps four.

---

## In short

- **Driller ran at about one redraw a second on 8-bit machines**
  [source: Ian Andrew]. Its scenes are small:
  - The whole database is 11,652 bytes across 29 areas, with 4-31
    drawable objects an area [measured].
  - From the 65 entrances, a view holds a median of 10 objects, 14 faces
    and 56 vertices, and at most 20, 39 and 156 [measured, no occlusion].
- **The best solid 3D on the BBC today:**
  - Rich Talbot-Watkins's PORTAL runs at 12.9fps on a Model B, in a
    128×128 MODE 5 view [measured in jsbeeb].
  - Eben Upton's Solid Elite runs at 12.3fps in flight on a Master, and
    at 21.6fps with a 4MHz co-processor [source].
  - In PORTAL the fill is a quarter of the frame. Visibility, transforms
    and set-up take most of the rest [measured]. Pixels are no longer the
    limit; the maths is.
- **Freescape is unusually cheap to transform:**
  - Every object sits on a 128×64×128 cell grid stored in bytes, and
    every box is axis-aligned.
  - Angles come in 5° steps, 72 a turn, from a sine table where 1.0 is
    64.
  - A cuboid's back faces fall out of byte compares against the camera's
    cell.
  - The original already builds a cuboid from one rotated corner and
    three rotated edge vectors [source: CM2 disassembly].
- **The specification follows the screen (D1, D2).** The database is the
  same in every version; only the view and its colours differ.
  - **Two colours: the ZX Spectrum version.** Its data is byte-identical
    to the variant ScummVM supports, and the siblings' SkoolKit harness
    can run it headless. Its 208×104 view is one bit a pixel with 4-row
    patterns and one ink/paper pair an area. That lands byte for byte on
    the BBC's MODE 4, and is the cheapest view to fill.
  - **Four colours: the Amstrad CPC version**, the machine Freescape was
    developed on. Its 248×101 view lands byte for byte on the BBC's
    MODE 1, for about 20K cycles more a frame [inferred].
  - D2 also prices MODE 5 (the C64's view) and MODE 2 with ordered
    dithers (the PC's EGA colours).
- **Proposed engine:**
  - The original's transforms, made cheap.
  - The original's draw order, but processed front to back into a span
    buffer, so each view byte is written once and nothing is cleared.
  - Reckoned at about **17fps on a median Driller view and 10 on the
    busiest** in MODE 4, before any optimisation pass, against the
    original's one [inferred, section 4]. MODE 1 keeps the median at 17
    and takes the busiest to about 8 (D2).
- **The starting point is a Python model of that renderer**:
  - It counts its own work over every entrance view, which settles the
    design before any 6502 is written.
  - The ZX original, run headless, is the oracle for what each view
    looks like.
  - The BBC speed spike comes next.

---

## 1. Freescape and Driller

### The engine

From `docs/research/freescape.md`, sections 1-4:

- **Games.** Driller (1987), Dark Side, Total Eclipse, Total Eclipse II,
  Castle Master, Castle Master II and the 3D Construction Kit.
  - They shipped on the ZX, CPC, C64, ST, Amiga and DOS.
  - None came out for the BBC or the Electron. The Construction Kit was
    listed for the Archimedes [source].
- **An area** is 8192×4096×8192 world units on a 64-unit grid.
  - Each object has a 9-byte header: type and flags, x, y, z, dx, dy, dz,
    id and length.
  - Then come colour nibbles: six for a solid, two for a flat shape, with
    0 meaning "not drawn".
  - Then vertex or apex bytes, then optional FCL bytecode [source +
    measured].
- **Types.** Cuboid, six orientations of truncated pyramid, rectangle,
  line, triangle to hexagon, sensor, entrance and group.
  - Only the polygons have free vertices, and those are on the grid too.
  - Driller has no groups, and nothing in it moves. Script code shows,
    hides and destroys objects, and engine code places the drilling rigs
    [measured].
- **The camera.** Yaw, pitch and roll in 5° units.
  - Driller's turn per key is selectable: 5, 10, 15, 30, 45 or 90°.
  - Its step is selectable: 1, 2, 5, 10, 25, 50, 100 or 250 units.
  - Pitch is a full 360° and roll is real [measured: tables at ZX `$88C9`
    and `$88BE`; manual; ScummVM `driller.cpp:184-192`].
- **Driller's FCL** uses only the "shot" and "collided" events and is
  2,055 bytes in all [measured].
  - Drilling, rig placement, the skanner, the timer, energy and the laser
    beacons are engine code (ScummVM `games/driller/driller.cpp`).

### Driller's versions, and which is the specification (D1)

| Version | Data | View | Colour | Run headless by |
|---|---|---|---|---|
| **ZX 48K, retail** | `Driller.tzx` block 5, 37,590 bytes, the same md5 as ScummVM's [measured] | 208×104 | 1bpp, 15 four-row patterns, one ink/paper pair an area (ScummVM `gfx.cpp:466-493`) | SkoolKit, as nm, CE2 and Cauldron are |
| CPC | `DRILL.BIN`, the same database format | 248×101, mode 1 | 2bpp: each colour index is a 4-row pattern, 4 pixels across, of two of the area's four pens (background, under fire, paper, ink), which are raw CPC inks from 27 (ScummVM `gfx.cpp:313-324`, `palettes.cpp:233-273`) | caprice32 (`../caprice32`), no harness yet; the Z80 code may run in SkoolKit's simulator as the ZX's does [inferred] |
| C64 | packed and protected; ScummVM unpacks one variant, marked unstable | 128×104 multicolour | the CPC's scheme; ScummVM takes the pattern table from the executable because the data's is wrong (`c64.cpp:95-175`) | py65, once unpacked; no disassembly |
| DOS, EGA and CGA | `DRILLE.EXE`, `DRILLC.EXE`: the same 8-bit database (`dos.cpp:208-256`) | EGA 240×101, CGA 248×101 | EGA: 16 solid colours. CGA: the CPC's scheme, with two fixed palettes alternating by area: black, cyan, magenta, grey; black, green, red, brown (`palettes.cpp:291-306`) | DOSBox, no harness |
| ST, Amiga | the same database in 16-bit words | ~240×101 | 16 colours from 4,096, a palette an area | Hatari (as for Starglider) |

Recommended: **the version whose screen D2 picks**, the ZX for MODE 4
and the CPC for MODE 1. The database is the same in every version, so
the areas, objects and scripts don't depend on the choice; only the view
and its colours do [source: `freescape.md`, section 8.1]. The ZX gives:

- data that ScummVM already parses exactly;
- an annotated sibling to read its code by (Castle Master II's Z80
  disassembly, with the same sine table byte for byte [measured]);
- a harness the siblings have already built (SkoolKit; see the porting
  guide);
- a recording to replay: Spectrum Computing hosts `Driller.rzx`.

The CPC gives:

- four colours an area, with its pattern bytes usable on the BBC as they
  are (section 4, step 8);
- the ZX version's author, Chris Andrew, on the machine Freescape was
  developed on [source];
- Z80 code, so the ZX's oracle tooling should carry over [inferred].
  There's no annotated disassembly to map it, though ScummVM's comments
  cite one of `DRILL.BIN` [source].

The C64 version is 6502 code, but packed, protected and undocumented.
It isn't worth the unpacking for logic that ScummVM and the ZX already
describe.

### Getting it, and rights

- Spectrum Computing hosts the ZX tape, manual and RZX
  (`spectrumcomputing.co.uk/entry/1521`). A `make fetch` can take it
  from there, as the siblings fetch their originals.
- The CPC's `DRILL.BIN` (35,320 bytes; ScummVM's md5 `719f5157…`) would
  come from a CPC disc image. No source has been chosen yet.
- Nothing of Driller's needs to be checked in: the build extracts the
  database from the fetched tape.
- The rights went Incentive, then Dimension International, Superscape
  and Glu (2008). Nothing found says who holds them now [source]. A disc
  carrying Driller's data is a rights question (D6). The engine and its
  tools aren't.

---

## 2. How Driller draws, and why it took a second

The pipeline below is from the Castle Master II disassembly, which shares
Driller's tables (`freescape.md`, section 5) [measured from the source]:

1. **Redraw only after a move.** A turn or step sets a flag, and nothing
   is re-projected otherwise.
2. **The matrix:** yaw × pitch × a scaling matrix, in signed-byte
   coefficients.
3. **A coarse cull** by a world-aligned box around the view, using byte
   compares on cells.
4. **Transform each object:**
   - A cuboid is one corner and three edge vectors (nine products), then
     additions. Its back faces come from "which side of each slab am I
     on" bits.
   - Every other shape transforms every vertex with 16×8 products into
     24 bits, and tests its back face with a 32- or 48-bit cross product.
5. **Frustum:** five planes tested per vertex, no far plane, and a 3D clip
   of each edge that crosses a plane.
6. **Project:** `x = 96·x/z + 96`, `y = 56·y/z + 56`, two 24-by-16-bit
   divides a vertex.
7. **Sort:** a bubble sort, repeated until nothing swaps, by comparing
   the objects' bounding boxes axis by axis against the player.
   ScummVM reproduces it exactly.
   - It decides in world space before projection, and the annotator
     expects "many issues in corner cases".
8. **Paint back to front** into a 1bpp buffer, with spans masked or
   written by `PUSH`, using a 4-byte pattern indexed by `row & 3`.
   - Everything behind a face that covers the whole window is skipped.
     That is the only occlusion.
9. **Copy** the buffer to the screen.

The time goes on the divides, the general multiplies (seven or eight
routines, 48-bit in places), overdraw, and the copy. None of it is
inherent to the data.

---

## 3. What the BBC does best now

From `docs/research/beeb-3d.md`:

| Engine | Machine | View | Fill | Rate |
|---|---|---|---|---|
| PORTAL (Rich, disc of 2026-10-16, no source) | B + sideways RAM | MODE 5 128×128, 4K a buffer | edges EOR'd into a separate transition buffer, then `EOR trans,X : STA screen,X` down each byte column (9 c a byte), plain `STA` below the last edge (5 c); **no screen clear** | 12.9fps on one static view [measured]: fill ~39K, sprite ~19.5K, **maths and set-up ~90K** |
| Solid Elite (Eben, 2026-10) | Master + SWRAM | MODE 1 256×192, main + shadow at one address | per-row edge tables, masked ends, unrolled `STA abs,Y` runs (5 c a byte + ~167 c a row) | 12.3fps in flight; 21.6 with a 4MHz co-processor doing the maths [source] |
| lander (Eben) | B + 64K SWRAM | MODE 1 256×160 | byte columns, unrolled stores | ~10fps [source] |
| BEEB-NICCC v1.2 (Kieran) | B | MODE 5 128×100 | span fill, 169 c a row + 5 c a byte | 6.9fps [source] |

What carries over [inferred]:

- **Write each view byte once.** At 5 c a byte, the cost of writing every
  byte once sets the fill's floor. For the ZX's 208×104 view at 1bpp
  (2,704 bytes) that's 13.5K. The CPC's 248×101 view in MODE 1 is
  6,262 bytes, 31.3K.
- **The maths is now the frame.** PORTAL's 90K of non-fill work is where
  a Freescape engine can beat it, because Freescape's geometry is
  axis-aligned, byte-sized and quantised.
- **The quarter-square multiply**, with the multiplier patched into the
  operands, takes ~22 c a product (TobyLobster's tables; Solid Elite's is
  23).
- **Projection** takes 56 c a coordinate by log/antilog, at up to ~2%
  error, or 73 c by a reciprocal table and quarter squares.
- **A co-processor edition** nearly doubles Solid Elite. The parasite
  does the maths and the host does the fill.

---

## 4. The engine proposed

### The frame

1. **The camera.** Build the matrix from the 72-step table: yaw × pitch ×
   roll, about 27 products.
2. **The object pass.** For every object in the area (at most 31 in
   Driller):
   - a coarse cull and the slab-side bits, as the original does, by byte
     compares on cells;
   - a cuboid's visible faces come free;
   - a flat shape's visible side is one compare against its
     axis-aligned plane.
3. **Transform.** Use the original's corner-and-edge-vectors trick for
   boxes and pyramids.
   - Cache each object's rotated corner and edge vectors while the
     orientation is unchanged.
   - A Driller step is a pure translation, so a frame that only moves
     costs one subtraction a vertex and no products. That is DOOM's
     translation coherence, and it suits a game of fixed steps.
4. **Clip** at the near plane in 3D (there's no far plane), then the sides
   in 2D.
5. **Project** each vertex with log/antilog or reciprocal tables.
6. **Order** the objects as the original does (D3).
7. **Spans, front to back.** Take the order nearest first:
   - Each face's rows go into a span buffer (a sorted list of covered x
     runs a row), clipped against what's already covered.
   - A full row is skipped with one flag test, and the frame stops early
     once every row is full.
   - Painting back to front leaves each pixel as the last face painted
     over it. Front to back, each pixel takes the first face to claim it,
     which is the same face. So **this reproduces the original's image
     exactly, glitches included**, for any order. The port can keep the
     original's order and still write each byte once [inferred: the
     argument holds for any order].
8. **Write the view.** Walk each row's spans once:
   - a masked byte where two faces meet;
   - unrolled stores for the solid middles;
   - each face's pattern byte picked by `row & 3`;
   - paper where nothing is covered.
   No clear, and no copy. At 1bpp the ZX's own pattern bytes are used as
   they are: both machines put eight pixels in a byte, leftmost in bit 7.
   - In MODE 1 the CPC's pattern bytes are used as they are too. Both
     machines keep a pixel's two bits in bits 7 and 3 (then 6 and 2, and
     so on), with the high and low bits the other way round. Swapping
     logical colours 1 and 2 in the palette is the whole conversion
     [source: ScummVM `freescape.cpp:85-96`, against the BBC's MODE 1].
   - **An ordered dither costs nothing a byte** while it repeats within
     one byte across: 8 pixels in MODE 4, 4 in MODES 1 and 5 (a 4×4
     Bayer, as in Solid Elite), 2 in MODE 2 (a 2×2 or 2×4). The row's
     byte is loaded once and stored along the run. A pattern two bytes
     across costs more, because the 6502 has no indexed `STX` or `STY`
     to hold the second byte: lander's alternating run takes 7.5 c a
     byte, or each row takes two passes.
9. **Flip** at VSync, and update the panel.

The alternative for steps 7-8 is PORTAL's column transitions with an EOR
fill. At 1bpp with 4-row patterns it needs four line streams, so each
edge costs four writes. In the 2bpp or 4bpp modes of D2 it may win. The
Python model counts both (section 8).

### Where the time goes

All of this is **[inferred]**, at the ZX's 208×104 view in MODE 4, using
the unit costs in section 3. It's what the Python model will replace with
counts.

| Stage | Median view (10 objects, 14 faces, 56 vertices) | Busiest (20, 39, 156) |
|---|---|---|
| Camera matrix | ~1K | ~1K |
| Object pass, all objects in the area | ~1.3K | ~2K |
| Transform (when turning; ~1.5K when only moving) | ~5K | ~11K |
| Project, at ~130 c a vertex | ~7K | ~20K |
| The original's sort, run from file order | ~6K | ~15-25K |
| Edge set-up | ~6K | ~16K |
| Faces into the span buffer, at ~70 c a face-row | ~21K (~300 face-rows) | ~49K |
| Writing the view: ~200 c a row + 5 c a byte | ~34K | ~49K |
| Panel, logic, interrupts | ~8K | ~8K |
| **A frame** | **~90K: ~17fps** | **~190K: ~10fps** |

The other screens in D2 change only the row for writing the view. Without
it the frame is ~56K at the median and ~141K at the busiest.

The levers past this, for the optimisation rounds Starglider ran:

- Start each frame's sort from the last frame's order (D3).
- Fast paths for a level camera, where pitch and roll are 0, as they are
  for most of Driller:
  - A box's vertical edges stay vertical, so it has four projected
    columns, not eight vertices.
  - The ground cuboid's top face fills whole rows.
- Skip a redraw when nothing has changed, as the original does.
- A co-processor edition (D5).

---

## 5. Decisions to make first

Matt makes these calls. The recommendation comes first in each.

### D1. The specification

It follows D2 (section 1): **the ZX retail version for MODE 4, the CPC
for MODE 1**. MODE 5 would take the C64's view, and MODE 2 the PC's EGA
colours.

### D2. The screen

The renderer is the same up to step 8 in every option. Only the byte
writer, its pattern table and the palette change, so the frames differ
only in writing the view. The rest is ~56K at the median view and ~141K
at the busiest (section 4) [inferred].

| Option | View | Bytes | The look, and whose it is | Frame, median / busiest | At VSync | A buffer |
|---|---|---|---|---|---|---|
| **A: MODE 4, 1bpp** | 208×104 | 2,704 | the ZX's own: its patterns, one ink and paper an area, comparable with the ZX's buffer byte for byte | ~90K / ~190K | 16.7 / 10fps | 6K (256×192, R1 = 32) |
| B: MODE 5, 2bpp | 128×104 | 3,328 | the C64's view: four pens an area in two-pen patterns, wide pixels as in PORTAL | ~93K / ~193K | 16.7 / 10fps | 6K (128×192, R1 = 32) |
| **C: MODE 1, 2bpp** | 248×101 | 6,262 | the CPC's own: its pattern bytes, and its four pens an area mapped to the BBC's eight; Solid Elite's mode | ~108K / ~209K | 16.7 / 8.3fps | 12K (256×192, R1 = 64) |
| D: MODE 2, 4bpp | 120×101 | 6,060 | the PC's EGA view at half the width: the BBC's eight colours, with ordered dithers of pairs for EGA's sixteen | ~107K / ~208K | 16.7 / 8.3fps | 12K (128×192, R1 = 64) |

All the frame figures are [inferred]: section 4's sums, with the writer at
~200 c a row (~340 at the busiest) and 5 c a byte, and C and D splitting
each row at the page boundary. "At VSync" rounds each frame up to whole
fields. C and D assume the CPC sees as many objects as the ZX; its
projection constants aren't found yet.

What the table says:

- **The pixels are a quarter to a third of the frame**, so doubling the
  bytes costs a tenth to a fifth more time, not double.
- At the median view all four fit in three fields. At the busiest, C and
  D miss five fields by ~5%, which is within the estimate's error. The
  levers in section 4 apply to all four.
- **C and D cost the same.** MODE 2 spends the bytes on colours, MODE 1
  on width.

The colours:

- **C.** The CPC picks each area's four pens from 27 colours, and the BBC
  has 8, so some areas will lose their tint to the nearest match. The
  data step (section 8, step 2) lists every area's pens and their BBC
  matches, so the loss can be seen before C is chosen. If it's poor, the
  PC's CGA version uses the same patterns with two fixed palettes, whose
  nearest BBC colours are close: grey becomes white and brown yellow.
- **D.** No 8-bit original specifies it. The colours come from the EGA
  version and the dithers would be ours, a deviation in colour only.
  ScummVM renders the EGA version, as a reference rather than an exact
  oracle. A VideoNuLA board gives MODE 2 sixteen colours from 4,096,
  enough for the ST's and Amiga's palettes, as an extra.
- **B.** The C64 is packed and undocumented, so its view can be checked
  only against ScummVM's rendering.

The memory:

- A and B fit two buffers in a B's main RAM with room to spare (D5).
- C and D need 12K a buffer:
  - On the Master, main and shadow RAM hold one each at the same address,
    as in Solid Elite.
  - A B can't spare 24K. It can do as lander does (MODE 1 256×160, 10K a
    buffer), or double-buffer only the view's 13 character rows (6.5K
    each) and show one panel beneath them with a split screen. Either
    leaves ~8-9K of main RAM beside the sideways RAM [inferred].
- The CPC's own panel is 320 wide. A 256-wide screen keeps each view row
  inside two pages (R1 = 64), so the panel would be redrawn to fit.
  That's the panel layer's call, as is colouring the ZX's panel in A
  (palette bands, CE2's method, or a split into another mode).

**Recommended:**

- **For four colours, C.** It's the only colour option where an original
  specifies every pixel. Its bytes land as they are, it keeps the full
  width, and it costs no more than D.
- **For two colours, A**, the cheapest view and the strongest oracle.
- B is the fallback if the busiest views must hold 10fps in colour.
- The Python model (section 8, step 3) counts the work once and prices
  all four screens from the same counts. That confirms the choice with
  counts before any 6502 is written.

### D3. The draw order

| Option | Image | Cost |
|---|---|---|
| **a. The original's bubble sort, from file order, every frame** | exactly the original's, glitches included; the ZX is then an exact oracle for every view | O(n²): ~6K median, ~15-25K at the busiest [inferred] |
| b. The same comparisons, started from last frame's order | the same wherever the order is consistent; may differ where the original glitches | a pass or two most frames |
| c. A correct order compiled offline (an axis-aligned BSP over the cell grid, objects split where they must be) | no glitches; a deviation | a few K a frame |

**Recommended: a for the spike**, measured, then revisit.

### D4. The pace

The original moves one whole step or turn per key (250 units and 15° at
the start) and shows only the result, about a second later. At 10-17fps
holding a key would make the game ten times faster.

- **a. Animate each step and turn.** The logic takes the original's
  steps exactly, at a rate Matt sets (steps a second while a key is
  held). The renderer shows the frames in between: a 15° turn as three
  5° frames, a step as several part-steps along the segment that the
  original's swept collision has already checked. The game is unchanged
  at rest, and motion is smooth [inferred]. **Recommended.**
- b. The original's pace: one step per redraw, at a fixed rate. Faithful,
  but it wastes the speed.
- c. Continuous movement with collision every frame. This changes the
  game, because the paths differ from step-wise ones.

### D5. The machines

- **Recommended: a Model B with 16K of sideways RAM, and the Master, from
  one disc**, the port kit's baseline. Option A's two 6K buffers fit main
  RAM on both, so nothing needs shadow RAM.
  - With C or D, the Master leads: its shadow RAM takes the second
    buffer, as in Solid Elite. The B follows where it fits (D2).
  - The B has ~16.5K of main RAM left beside them, plus 16K of sideways
    RAM and the OS pages. The database is 11.6K [inferred].
  - The Master's 65C12 instructions (STZ, BRA, PHX) can come later as a
    second assembly.
- **For later: a co-processor edition.** The camera, transforms, sort and
  spans run on the parasite; the host writes the bytes. This split gave
  Solid Elite 1.75× on a Master.

### D6. Rights

The build reads Driller from a fetched copy and checks none of it in. A
playable disc to share would need the rights holder, as Starglider has
Argonaut's blessing. That doesn't block anything until there's a disc
to share.

### D7. Scope

Driller first. Keep the loader general:

- Dark Side and Total Eclipse share Driller's 8-bit layout.
- Castle Master adds groups.
- The Construction Kit has its own FCL dialects.

---

## 6. The oracles

1. **Data.** The loader's dump against ScummVM's parse.
   - Every area's object walk must end exactly where its conditions start.
     This already holds for all 29 areas [measured].
   - Type counts and colours are compared too.
2. **Views.** The original D1 picks, run headless: a SkoolKit snapshot in
   play, the camera variables poked, its redraw called and its buffer
   read back. For the CPC that's its Z80 code in SkoolKit's simulator
   with the CPC's memory map [inferred: not tried].
   - Compared with the Python model and the BBC's buffer, every entrance
     view and a walk through every area.
   - It should agree within a pixel at edges, and exactly where the
     original's 8.8 edge stepping is transcribed [inferred].
   - It also gives the first measured redraw time for the original.
3. **The BBC against the Python model, byte for byte.** The model uses
   the 6502's own fixed-point arithmetic.
4. **Logic, later.** Pass by pass against the ZX, for movement,
   collision, FCL, rigs and beacons. Spectrum Computing's `Driller.rzx`
   gives a long scripted game.
5. **Speed.** `make bench` renders every entrance view and a scripted walk
   through each area. It reports jsbeeb's cycles a frame as a
   distribution, beside the original's redraw time for the same views.
   This is what proves the engine.

---

## 7. Risks and unknowns

- **The span buffer's cost per face-row** is the largest unknown in
  section 4. The model counts face-rows; only the spike prices them.
- **Finding the ZX redraw entry and camera variables** means
  disassembling Driller's Z80. CM2's annotated disassembly is the map,
  since they share tables, but Driller adds roll and its own projection
  constants, which aren't found yet [source].
- **Near clipping is common:** walking up to a wall puts it across the
  near plane in most frames.
- **Roll** tilts every edge. The span buffer takes any convex polygon,
  but the level-camera fast paths don't apply then.
- **Sort cost** at the busiest views, if D3 stays at a.
- **Memory on the B**, once the panel, FCL and Driller's engine features
  are in, and more so at 12K a buffer (D2, C and D).
- **The CPC's inks on the BBC's eight colours** (D2, C).
- **Rights** (D6).

---

## 8. The starting point

In order, each step working before the next starts:

1. **Set up the repository** as the siblings are:
   - `CLAUDE.md`, `docs/journal.md`, `docs/decisions.md` (D1-D7 once
     taken);
   - a Makefile with baron at a pinned tag;
   - starglider-beeb's jsbeeb-mcp harness (`tools/beeb.mjs`, `play.mjs`,
     frametime);
   - a SkoolKit venv, and `make fetch` for `Driller.tzx`, and for the
     CPC's `DRILL.BIN` if D2 is C (neither checked in).
2. **`tools/freescape.py`**, promoted from `tools/research/fsdump.py`. It
   turns the ZX database into JSON, and `make data` checks it against the
   oracle in section 6.1.
   - For C it reads the CPC's too. It checks the two agree object by
     object, and lists each area's four pens beside their nearest BBC
     colours.
3. **`tools/view.py`, the renderer in Python with the 6502's
   arithmetic**: the matrix from the 5° table, transforms, clip, project,
   the original's sort, the spans front to back and the byte writer.
   - Over all 65 entrance views it writes PNGs and counts the work:
     objects, vertices, edges, face-rows, spans and bytes.
   - Multiplying the counts by the unit costs of section 3 prices the
     span buffer and the column transitions at every screen in D2. That
     picks the design and the view before any 6502 is written.
4. **The oracle: `tools/zx.py`, or `tools/cpc.py` for C.** A snapshot of
   Driller in play, with SkoolKit control files for its redraw and
   camera, CM2 as the map.
   - It renders every entrance view headless, to compare with `view.py`
     and to time the original's redraws.
5. **The speed spike on the BBC**: the renderer alone, one area baked in,
   a scripted camera path.
   - `make spike` checks every frame's buffer against `view.py` and
     reports cycles a frame.
   - Then optimisation rounds, as Starglider ran them: agents each
     owning a stage, gated by `make spike`, until a round finds little.

After the spike, the layers in the guide's order:

- the screen and panel;
- the data: all areas, entrances, and moving between platforms by
  wrapping at the edge;
- the player: steps, turns, pitch and roll, probe heights, the jet,
  collision and falls;
- FCL;
- Driller's engine features: rigs and gas pockets, laser beacons, the
  timer, energy and shield, the skanner;
- sound, from the beeper to the SN76489;
- the front end;
- the loader.
