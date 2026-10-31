# Freescape: how the original works

Research brief for a Freescape-compatible engine on the BBC Micro / Master 128. This half covers the
original engine and its data; BBC rendering prior art is in `beeb-3d.md`.

Tags: **[source]** = stated by the linked/cited source; **[measured]** = I read the bytes or ran a
parser over them myself; **[inferred]** = my reasoning, with the reasoning given. File:line references
into ScummVM are against `scummvm/scummvm` commit `f6d50c680622aecd03108eca460f9b418782de91`
(2026-10-31), path prefix `engines/freescape/` omitted. References into the Castle Master II
disassembly are line numbers in `castlemaster2-annotated.asm` of
[santiontanon/castlemaster2-disassembly](https://github.com/santiontanon/castlemaster2-disassembly)
commit `bf2961c6` (labelled "CM2 asm:NNNN").

Driller is the reference game for this project, so it gets its own deep section (section 8) built
from a parse of the real ZX Spectrum database.

---

## Summary

| Topic | Key facts |
|---|---|
| Games | Driller (1987), Dark Side (1988), Total Eclipse (1988), Total Eclipse II: The Sphinx Jinx, Castle Master (1990), Castle Master II: The Crypt (1990), 3D Construction Kit (1991), 3D Construction Kit II (1992). 8-bit: ZX, CPC, C64; 16-bit: ST, Amiga, DOS. No BBC Micro or Electron release found. 3D Construction Kit is listed for the Archimedes. |
| World units | Area = 8192 × 4096 × 8192 world units ("SDUs"). Objects sit on a 64-unit grid: 128 × 64 × 128 cells, positions and sizes stored as **bytes**. Player position is 16-bit world units. [source + measured] |
| Object types | 0 entrance, 1 cuboid, 2 sensor, 3 rectangle, 4–9 "pyramid" (truncated, 6 axis orientations, apex rectangle), 10 line, 11 triangle, 12 quad, 13 pentagon, 14 hexagon, 15 group. All boxes are axis-aligned; only polygons have free vertices (on the cell grid). [source] |
| Per-object data | 9-byte header (type/flags, x, y, z, dx, dy, dz, id, length) + colour nibbles (6 for solids, 2 for planar) + vertex/apex bytes + optional FCL bytecode. Colour 0 = face not drawn. [source + measured] |
| Typical size | Driller ZX: 29 areas, 669 object records, 576 geometric objects; 4–31 geometric objects per area (median 21); whole database 11,652 bytes. [measured] |
| Camera | Rotations in 5° steps (72 per turn), sin/cos table with 1.0 = 64. Pitch is a real rotation matrix. Castle Master II: yaw + pitch only, pitch clamped to ±90°. Driller: full 360° pitch and roll as well. [measured + source] |
| Renderer (8-bit) | Per frame: build 3×3 matrix (8-bit coefficients), transform per-object vertices (16×8-bit multiplies into 24-bit), cull by a coarse world-aligned box, 5-plane per-vertex frustum test, 3D edge clipping, per-face back-face test (cubes use a cheap world-space side test), project (two 24/16 divides per vertex), **bubble-sort objects** by per-axis bounding-box comparison relative to the player, then painter's algorithm into an off-screen 1bpp buffer with 4-row dither patterns, then block copy to screen. No Z-buffer, no far plane, no occlusion culling beyond "a face covers the whole screen". [measured from CM2 disassembly] |
| Speed | About one update per second on 8-bit machines [source: Ian Andrew's site]. No measured frame time found. Screen is redrawn only after input or events. [measured from CM2 disassembly] |
| Best sources | ScummVM `engines/freescape` (loaders for nearly every game/platform pair, FCL, sort that mirrors the original); the annotated Castle Master II Z80 disassembly (whole 8-bit pipeline); John Elliott's Driller database notes; 3DCK manuals. |

---

## 1. Games and platforms

| Title | Year | Platforms | Programmers (where known) |
|---|---|---|---|
| Driller (US: Space Station Oblivion) | 1987 | ZX, CPC, C64, Amiga, ST, DOS (EGA, CGA, Hercules, Tandy) | Program design Chris Andrew; programming Chris Andrew (Spectrum, CPC) and Stephen "Bug" Northcott (C64) [source: [ianandrew.com Driller page](https://www.ianandrew.com/copy-of-splat); ZX manual credits, measured from the Spectrum Computing "games-info" archive] |
| Dark Side | 1988 | ZX, CPC, C64, Amiga, ST, DOS | Chris Andrew, Stephen Northcott, Paul Gregory (platform split not given) [source: [ianandrew.com Dark Side](https://www.ianandrew.com/copy-of-driller)] |
| Total Eclipse | 1988 | ZX, CPC, C64, Amiga, ST, DOS | Chris Andrew, Sean Ellis, Paul Gregory. "The Freescape engine was improved for this release, adding spheres" [source: [ianandrew.com Total Eclipse](https://www.ianandrew.com/copy-of-dark-side)] |
| Total Eclipse II: The Sphinx Jinx | Wikipedia lists 1991 | ZX, CPC, C64 (8-bit only) | — [source: [3dconstructionkit.co.uk](https://3dconstructionkit.co.uk/freescape.html); ScummVM `detection.cpp:619-702`] |
| Castle Master | 1990 | ZX, CPC, C64, Amiga, ST, DOS | Chris Andrew, Paul Gregory, Sean Ellis; published by Domark and Incentive [source: [ianandrew.com Castle Master](https://www.ianandrew.com/copy-of-total-eclipse-1)] |
| Castle Master II: The Crypt | 1990 | ZX, CPC, C64, Amiga, ST, DOS | — [source: 3dconstructionkit.co.uk] |
| 3D Construction Kit (US: Virtual Reality Studio) | 1991 | ZX, CPC, C64/128, Amiga, ST, DOS, **Acorn Archimedes** | Paul Gregory, Sean Ellis [source: [Wikipedia](https://en.wikipedia.org/wiki/3D_Construction_Kit)] |
| 3D Construction Kit II | 1992 | Amiga, ST, DOS | — [source: Wikipedia] |

Notes:

- Freescape development started in September 1986 on an Amstrad CPC (128K), by Chris Andrew
  [source: [Wikipedia Freescape](https://en.wikipedia.org/wiki/Freescape), attributing Paul Gregory].
  ScummVM's CPC sound mapping cites a `DRILL.BIN` disassembly (`games/driller/cpc.cpp:32-49`),
  so the CPC binary has been studied.
- 3dconstructionkit.co.uk also lists Commodore +4 downloads for most titles; I did not verify these.
- **BBC Micro / Electron:** none of the platform lists (Wikipedia, ianandrew.com, the 3DCK fan
  site, ScummVM's 125 detection entries) include a BBC or Electron Freescape title. Incentive did
  publish earlier BBC/Electron games (Confuzion, Millionaire, The Adventure Creator, Dragon's
  Tooth) [source: [Wikipedia Incentive Software](https://en.wikipedia.org/wiki/Incentive_Software)].
  [inferred] no BBC Freescape exists.
- **Archimedes:** only the 3D Construction Kit, sold at the £49.99 16-bit price; Wikipedia cites
  an Acorn User review, "A New Dimension", March 1992, p.119. Release date conflicts (May 1991 vs
  January 1992). ScummVM has no Acorn support (`grep -i acorn` finds nothing). No disc image
  located.
- **Rights:** Incentive → renamed Dimension International in 1995 (Superscape VRT) → Superscape
  [source: Wikipedia]. Superscape was bought by Glu Mobile in January 2008 for about $35.7M
  [source: [socaltech](https://socaltech.com/superscape_to_be_acquired_by_glu_mobile/s-0013340.html)].
  Glu was itself bought by Electronic Arts in 2021 [inferred, from general knowledge, not checked
  here]. Whether the game copyrights went down that chain is not documented anywhere I found.
  Spectrum Computing lists Driller's availability as "Available" and hosts its tapes.

## 2. The data model

### 2.1 Database (8-bit, Driller/Dark Side/Total Eclipse layout)

Little-endian; offsets from the database start. [source: [seasip Driller room format](https://www.seasip.info/ZX/Driller/) and `loaders/8bitBinaryLoader.cpp:875-1065`; confirmed by my parse of Driller ZX, measured]

| Offset | Size | Meaning |
|---|---|---|
| +00 | 1 | number of areas (Driller ZX: 29) |
| +01 | 2 | database length (Driller ZX: 11,652) |
| +03 | 1 | start area id (Driller: 1) |
| +04 | 1 | start entrance id (Driller: 19) |
| +06..+09 | 4 | initial energy/shield (Driller: probe and jet) |
| +0A | 60 | 15 shade patterns × 4 bytes ("colour map") |
| +46 | 2 | offset of demo table |
| +48 | 2 | offset of global condition table |
| +B4 | 8 | time limit `'hh:mm:ss'` (Driller ZX: `04:00:00`) |
| +C2 | 1 | initial step index (Driller ZX: 7, i.e. 250) |
| +C3 | 1 | initial angle index (Driller ZX: 2, i.e. 15°) |
| +C8 | 2·n | area offset table (Driller: up to 35 entries) |

Castle Master 8-bit moves things: colour map at +06, pointers at +42 (C64 +3E), area table at +4F (C64
+4B); Amiga/ST use 16-bit big-endian words for every field and doubled pointers
(`8bitBinaryLoader.cpp:38-89, 914-1031`). The data is "pretty much machine-independent"; the
Driller database sits at $CF3E on the Spectrum, at file offset $9B40 in `DRILLE.EXE` [source: seasip].

### 2.2 Area header

| Offset | Driller | Dark Side | Castle Master (ZX/CPC/C64) |
|---|---|---|---|
| +0 | flags (low nibble sky, high nibble ground in ScummVM's reading; CM: sky/floor texture ids) | same | same |
| +1 | number of object records | | |
| +2 | area id | | |
| +3 | offset to area conditions (2 bytes) | | |
| +5 | scale | | |
| +6..+9 | 4 palette bytes: border, border-under-fire, paper, ink (ZX attributes; CPC raw inks; C64/DOS palette picks) | same | +6 one attribute byte, +7 name index |
| +10 | gas pocket x, z, radius (3 bytes) | 3 name chars | — |
| +13 | name, 12 chars | 12 chars | — |
| +25 | objects | | |

After the objects: `n` conditions, each `length` + bytecode (`8bitBinaryLoader.cpp:626-873`).
Castle Master has a global area 255 whose objects are made visible per area by an id-255 "room
structure" record listing global ids (CM2 asm:13477-13545, `Lc81c_reset_global_area_objects`).
Driller's globals (the drilling rig and the skanner) are stored outside the database
(ZX $87A5, 8 objects) [source: seasip; measured].

### 2.3 Object record

9-byte header for every type [source: seasip; CM2 asm:171-198; `8bitBinaryLoader.cpp:308-622`]:

| Byte | Meaning |
|---|---|
| 0 | bits 0–4 type (Castle Master: bits 0–3); bit 5 destroyed; bit 6 invisible; bit 7 initially invisible |
| 1–3 | x, y, z of bounding box min corner, in cells (64 world units) |
| 4–6 | dx, dy, dz in cells (entrances: pitch, yaw, roll in 5° units) |
| 7 | object id |
| 8 | total record length; bytes past the type's fixed size are FCL bytecode |

Type-specific payload (`geometricobject.cpp:31-84`; CM2 asm:499 gives the fixed sizes
`09 0C 0E 0A 10 10 10 10 10 10 10 13 16 19 1C` for types 0–14):

| Type | Payload | Fixed size |
|---|---|---|
| 0 entrance | none (Castle Master: may carry FCL; CM coordinates of 255 mean "keep current") | 9 |
| 1 cuboid | 3 bytes = 6 colour nibbles, low nibble first. Face order −X, +X, −Y, +Y, −Z, +Z (`gfx.cpp:973-1106`) | 12 |
| 2 sensor | colour, firing interval, range (16-bit, world units), axis mask (bits 0–5 = ±X, ±Y, ±Z) | 14 |
| 3 rectangle | 1 byte: front/back colour nibbles; one size must be 0; two zero sizes make it a line (`geometricobject.cpp:163-178`) | 10 |
| 4–9 pyramid E, W, Up, Down, N, S | 3 colour bytes + 4 bytes: apex rectangle corners in the two axes perpendicular to the pyramid axis, relative to the origin. Equal corners → point; one pair equal → wedge; neither → truncated (CM2 asm:5511-5549 picks pyramid/wedge/"triangle hourglass"/"hourglass" vertex sets from these) | 16 |
| 10–14 line, triangle, quad, pentagon, hexagon | 1 colour byte (two sides) + 3·(n) bytes of vertex x, y, z in **absolute cells** (Driller data, measured) | 16, 19, 22, 25, 28 |
| 15 group | 3 member ids, two offset triples, then animation opcodes (move-to positions, script, rewind) (`8bitBinaryLoader.cpp:91-306`, `objects/group.cpp`) | variable |

- **Colours:** 4-bit index; 0 = transparent (face skipped, "can be used to improve the speed of
  drawing") [source: 8-bit 3DCK manual p.7]. Index 1–15 selects one of 15 four-byte shade patterns.
- **Axis alignment:** cuboids, rectangles and pyramids are always axis-aligned (no rotation field).
  Arbitrary orientation exists only through polygons, whose vertices are still on the cell grid.
  [source + measured]
- **Pyramids collide as their bounding cube**; "it is not possible to stand on the slope"
  [source: 8-bit 3DCK manual p.7].
- **Objects must not overlap** (sorting assumption); "the number of visible objects in any one AREA
  is limited ... Excess objects are not drawn" [source: 8-bit 3DCK manual p.9].

### 2.4 Units, widths, scale

- World: 8192 × 4096 × 8192 units; 1 cell = 64 units; x/z cells 0–127, y 0–63; "one unit is the
  smallest distance that you can move through" [source: 8-bit 3DCK manual p.6]. Driller's manual:
  a platform is "8128 SDUs" per side (127 × 64) [measured from the ZX manual text].
  CM2 defines `MAX_COORDINATE equ 127*64` (CM2 asm:101).
- 8-bit games store cells as bytes; the Z80 code makes 16-bit world coordinates with `cell*64`
  (CM2 asm:2181-2230). The player position is three 16-bit words (CM2 asm:388-395).
- 16-bit games (Amiga/ST) store the same fields as 16-bit words but the values are still < 256
  (`readField` asserts it, `8bitBinaryLoader.cpp:54-76`); 16-bit 3DCK worlds use real 16-bit vectors
  (`games/3dck/3dck.cpp:331-420`). On 16-bit machines movement is any multiple of one unit
  [source: Wikipedia Freescape].
- **Area scale** (1–24 seen): makes the player bigger relative to the cells. In CM2, speed,
  player height, climb and fall limits are all multiplied by the scale on area entry
  (CM2 asm:12497-12560). Eye height = (2·scale − 0.5) cells for a standing player; ScummVM's
  `changePlayerHeight` gives the same (`movement.cpp:373-385`). Driller uses scales 1, 2, 4
  [measured]; CM2 uses 1–24 [measured].
- **Limits:** up to 254 areas plus globals area 255 [source: 3DCK manual]; Driller's table holds
  35 [source: seasip]; object count is a byte. CM2's frame buffers bound what one frame can hold:
  the projected-object list is 160 bytes (40 objects × 4 bytes) and projected polygon data has
  524 bytes ($67F4–$69FF) [inferred from the `equ` addresses at CM2 asm:240-297].

### 2.5 Typical counts

| Game (data parsed) | Areas | Geometric objects per area | Notes |
|---|---|---|---|
| Driller ZX | 29 | min 4, median 21, max 31, mean 19.9 | 669 records; 277 cuboids, 162 rectangles, 101 pyramids, 36 polygons/lines, 65 entrances, 28 sensors, 0 groups [measured] |
| Castle Master II ZX | 38 + global area 255 (75 objects) | min 2, median 6, max 39 | 170 cuboids, 153 rectangles, 75 pyramids, 20 polygons/lines, 108 entrances, 26 "spirits" (type counts include the global area) [measured from the data blocks in the disassembly] |

### 2.6 Runtime change

- 8-bit FCL toggles visibility (VIS, INVIS, TOGVIS, DESTROY, and remote-area variants); nothing
  moves except groups. Groups (type 15) hold up to three objects and step through absolute
  positions (`objects/group.cpp:114-209`), started by `STARTANIM`. Driller has no groups
  [measured]; its drilling rig is inserted by engine code (section 8.3).
- 16-bit 3DCK adds `MOVE`/`MOVETO` and animators (`language/detokeniser_3dck16.cpp:51,55`).

## 3. FCL (Freescape Command Language)

### 3.1 Game bytecode (Driller through Castle Master, 8-bit)

Each instruction byte = `eeoooooo`: `ee` is the event the instruction answers to — 00 collided
(walked into/onto), 01 timer, 10 shot, 11 activated — and `oooooo` the opcode; consecutive
instructions with the same `ee` form one `IF event THEN` block
(`language/detokeniser_freescape.cpp:33-99, 184-225`). Opcodes (`detokeniser_freescape.cpp:33-83`):

`01 ADDSCORE(3 bytes) · 02 ADD ENERGY · 03/04/05 TOGVIS/VIS/INVIS obj · 06/07/08 same in another area ·
09/0A INC/DEC var · 0B IF var != · 0C/0D SET/CLR bit · 0E IF bit != · 0F SOUND · 10/11 DESTROY (here/area) ·
12 GOTO entrance area · 13 ADD SHIELD · 14 SETVAR · 15 SWAPJET · 19 SPFX (palette swap/flash) · 1A REDRAW ·
1B DELAY n/50 s · 1C SYNCSND · 1D TOGGLE bit · 1E–21 IF (R)INVIS/(R)VIS · 22 PRINT · 23 SCREEN · 24 SETFLAGS ·
25 STARTANIM · 29/2A LOOP/AGAIN · 2C ELSE · 2D ENDIF · 2E/2F IF >= / <= · 30 EXECUTE`

CM2's interpreter uses the same numbering (CM2 asm:200-235, `RULE_TYPE_*`), with operand sizes
from a table (CM2 asm:502-505).

**Where conditions live and when they run**

- Object conditions: bytes after an object's fixed payload. Run when that object is shot,
  collided with, or (Castle Master) activated (`execution_freescape.cpp:51-77`).
- Area ("local") conditions and global conditions: lists in the area and database. Run with the
  current event flags (`execution_freescape.cpp:79-96`).
- In CM2 nothing runs unless a player event (movement/collision, shot, activate) or a timer event
  happened that tick; then the object under the pointer, the global scripts and the area scripts
  run in that order (CM2 asm:6745-6788, `La005_check_rules`; event matching CM2 asm:10845-10900).
- Variables: bytes; ScummVM's 8-bit games use 64 (`language/variables.h`: score 61, energy 62,
  Driller tank/jet energy and shield 57–60). Bits: 32 (CM2: four bytes of booleans, CM2 asm:437).

**Driller's FCL in numbers** [measured]: 2,055 bytes in total; only *shot* (561 instructions) and
*collided* (333) events are used; most common opcodes INVIS 136, SYNCSND 97, GOTO 96, TOGVIS 89,
SOUND 69, VIS 62, ADDSCORE 56, SETBIT 45. 5 global conditions (13–25 bytes each); area
conditions in 8 of 29 areas.

### 3.2 3D Construction Kit dialects

- 8-bit 3DCK: textual IF/THEN/ELSE/ENDIF (no nesting) with over 40 commands (ADDV, ADCV, SUBV, SBCV,
  ANDV, ORV, XORV, CMPV, SETV, IFEQ/IFGT/IFLT, IFSHOT, IFHIT, IFACTIVE, IFCRUSH, IFFALL, IFSENSED,
  IFTIMER, IFVIS, VIS/INVIS/TOGVIS/DESTROY, GOTO, MODE, CALL, SOUND, SYNCSND, PRINT, REDRAW,
  DELAY, TIMER, COLOUR, TEXTCOL, CROSS, END, ENDGAME). General conditions run every frame
  (general condition 1 only after RESET), local conditions every frame in the current area,
  procedures only via CALL. 128 variables, 0–111 free, 112–127 system: viewpoint position (6
  bytes), rotations in 5° steps 0–71 (3 bytes), key, interrupt counter, area, ammo, font pointer
  [source: 8-bit 3DCK manual pp.8-9 and 21-30, plus its system-variable list; measured from the PDF text].
  No object conditions; procedures instead [source: Wikipedia 3DCK].
- 16-bit 3DCK: separate tokenisation with animators, MOVE/MOVETO etc.
  (`language/detokeniser_3dck16.cpp`). The two are "similar but not interchangeable"
  [source: Wikipedia 3DCK].

### 3.3 Is the 8-bit 3DCK runtime the games' engine?

[inferred] Yes, a variant. Its object records use the same 9-byte header and payloads
(`games/3dck/8bit.cpp:214-274`; entrances gain 3 "fine position" bytes), the same 5° angles and
area scale; the area header and the FCL dialect differ, and the viewport is user-set
(`games/3dck/8bit.cpp:96-128`).

## 4. Player and camera

| Item | Castle Master II (ZX) | Driller | Source |
|---|---|---|---|
| Angle unit | 5°, 72 per turn | same | CM2 asm:158, 790-811; Driller ZX table at $8E78 identical to CM2's [measured] |
| sin/cos | signed bytes, 1.0 = 64 | same | same |
| Yaw step | 2 units (10°) per key, shift = 90° | user-selectable 5, 10, 15, 30, 45, 90° (table `06 01 02 03 06 09 12` at $88C9, in 5° units) | CM2 asm:15123, 9531-9580, 9636-9660; Driller [measured] |
| Pitch | true X-axis rotation matrix, clamped to ±18 units (±90°) | full 360°, no clamp | CM2 asm:5265-5320, 9585-9635; ScummVM `freescape.cpp:1449-1466`; Driller manual "rotate fully ... look in any direction" |
| Roll | none ("only considers 2 rotation angles") | yes, "tilted to either side" | CM2 asm header; Driller manual; ScummVM roll keys (`games/driller/driller.cpp:184-192`) |
| Step | crawl 30, walk 60, run 240 world units × area scale | 1, 2, 5, 10, 25, 50, 100, 250 SDU (table `08 01 02 05 0A 19 32 64 FA` at $88BE) | CM2 asm:15111-15115, 9422-9470; Driller [measured] and manual ("1-250 SDUs") |
| Movement | discrete steps along yaw on the XZ plane; no strafe | same, plus vertical extension levels | CM2 asm:9422-9520 |
| Height | standing eye (2·scale − 0.5) cells; crawl lower | probe "vertical extension" 4 levels; jet flies | CM2 asm:12538-12562, 9500-9512; ScummVM `movement.cpp:373-385`, `driller.cpp:62-63` |
| Collision | player box (radius 10 units) swept against object AABBs; no wall sliding; auto-climb steps ≤ climb height; falls to the highest object below, damage above fall limit | AABB (ScummVM width 12, depth 32, step-up 64 in ScummVM units) | CM2 asm:491, 8759-8930, 8640-8740, 14153-14260; `driller.cpp:72-74` |

Yaw convention: yaw 0 looks along +Z, yaw 18 (90°) along +X [inferred from CM2's movement code,
CM2 asm:9422-9470, and Driller entrance data: entrances on the west edge face yaw 90°, east edge
270°, north edge 180°, measured].

## 5. The original 8-bit renderer

### 5.1 Pipeline (Castle Master II, ZX; applies to the Freescape family)

From the annotated disassembly [measured, reading the code]:

1. **Only redraw when needed.** `L83aa_redraw_whole_screen` re-projects only if the
   "player moved/turned" flag is set, re-renders from cached 2D data if only a redraw was
   requested, and otherwise just updates the UI (CM2 asm:2048-2128).
2. **Matrix.** Yaw matrix from the table, times pitch matrix, times a constant scaling matrix
   `diag(40/64, 64/64, 32/64)` (CM2 asm:5252-5336). Coefficients are signed bytes.
3. **Coarse cull.** A world-aligned "rendering cube" built from the view quadrant (yaw/pitch ±40°)
   and the player position rejects objects entirely behind the player; byte compares on cell
   coordinates (CM2 asm:3339-3545, 2156-2170).
4. **Per object:** bounding box relative to the player in 16-bit (also yields the 6 "which side of
   each slab am I on" bits) (CM2 asm:2171-2230).
   - **Cuboid:** rotate one corner and the three size vectors (9 byte×byte products), then build
     8 vertices with additions (CM2 asm:4403-4527, 5338-5440). Back faces are removed with the
     slab-side bits, no maths (CM2 asm:5441-5495, loop at 5450).
   - **Rectangle/polygon/pyramid:** each vertex through the matrix (3×3 multiplies 16×8 → 24-bit,
     result /64) (CM2 asm:2285-2365); back-face test by 3D cross product with 32/48-bit
     arithmetic (CM2 asm:2806-3025); planar objects pick front or back colour.
5. **Frustum.** 5 bits per vertex: x ± z, y ± z, z < 0. The frustum is a 90° pyramid in scaled
   space (horizontal ±38.7°, vertical ±26.6°), **no far plane** (CM2 asm:4529-4610). Objects with all
   vertices inside skip clipping; others clip each edge in 3D against the failed planes
   (CM2 asm:2394-2800, 3574-4205). A face that projects to no vertices is checked for "covers the
   whole screen" (CM2 asm:4220-4296).
6. **Project:** `x = 96·x/z + 96`, `y = 56·y/z + 56` (24-bit by 16-bit divides), shared vertices
   projected once per object (CM2 asm:4305-4385, 3271-3330).
7. **Sort:** bubble sort over the object list until no swap. For each pair and each axis, compare
   the two boxes' extents relative to the player: overlapping on that axis → no verdict; a box
   straddling the player's coordinate is closer; both on the same side → nearer edge wins; opposite
   sides → no verdict. Keep the order only if the second is closer on some axis and the first on
   none; otherwise swap (CM2 asm:6089-6273). The annotator: "Sorting ... happens in coordinates
   *before* they are projected to camera coordinates ... I am sure this causes many issues in
   corner cases." ScummVM reproduces this exactly, seeded with globals first then file order
   (`area.cpp:322-375`, `objects/object.h:96-98`).
8. **Draw back to front** into a 24 × 113-byte 1bpp buffer (CM2 asm:240). If some objects cover
   the whole screen, everything before the nearest such object is skipped and the sky/floor
   background is not drawn (CM2 asm:6280-6360). Lines and polygons are filled with 8.8 fixed-point
   edge stepping (not Bresenham), spans written with masks or `PUSH` for long runs, pattern =
   4-byte texture indexed by `row & 3` (CM2 asm:4664-5240). The sky/floor background is drawn first
   for outdoor areas (CM2 asm:7358-7700).
9. **Copy** the buffer to screen with 24 `LDI`s per row × 112 rows (CM2 asm:7281-7330).

The annotator's overall view: "even if the individual functions are not very optimized ... the
overall structure is very nice"; math routines are "very wasteful", with 7–8 multiply routines
and 48-bit precision in places [source: CM2 asm header; santiontanon on
[msx.org](https://msx.org/es/node/65187?page=2)].

### 5.2 Viewports and colour on 8-bit machines

Viewport rectangles below are ScummVM's (`grep _viewArea games/*/*.cpp`), converted to native
pixels where noted [source; conversion inferred from ZX images being centred in 320×200,
`freescape.cpp:1693-1694`].

| Version | 3D window | Colour model |
|---|---|---|
| Driller ZX | 208 × 104 (26 × 13 cells) | 1bpp shade patterns, one paper/ink attribute pair per area over the whole window (`gfx.cpp:466-493`) |
| Castle Master II ZX | 192 × 112 (24 × 14 cells) | same; matches the disassembly |
| Driller CPC | 248 × 101 (mode 1) | 2bpp patterns mixing two of 4 pens; the 4 area bytes are raw CPC inks (`gfx.cpp:535-592`, `games/driller/cpc.cpp`) |
| Driller C64 | 256 × 104 hi-res = 128 × 104 multicolour | 2bpp multicolour patterns; ScummVM hard-codes the shade table because "the color map from the data is not correct" (`games/driller/c64.cpp:95-175`) |
| Dark Side C64 / Castle C64 | 256 × 103 / 240 × 120 | as above |
| Driller DOS EGA / CGA | 240 × 101 / CGA 4-colour patterns | `games/driller/dos.cpp:34-38` |

Shade patterns are 4 bytes repeating every 4 rows. Driller ZX's 15 shades [measured]:
`00000000, FFFFFFFF, 88228822, 77DD77DD, AA55AA55, 55AA55AA, 00880022, DD77DD77, 77EEBBDD,
88114422, 00FF00FF, 44226699, 55005500, AAFFAAFF, AAAAAAAA` (each 4 bytes, hex).

### 5.3 Frame rate

- "Frame updates ran about once per second on 8-bit machines" [source: [ianandrew.com Driller](https://www.ianandrew.com/copy-of-splat)].
- Crash #47 (1987): "whenever you move all the graphics have to be recalculated and filled in
  again"; "After a couple of hours you don't notice the jerkiness" [source: [crashonline](https://crashonline.org.uk/47/driller.htm)].
- Freescape games are "much more enjoyable in 7 MHz" [source: Spectrum Computing forum].
- No measured frame time found for any version. Section 8.4 says how to get one.

## 6. Reimplementations and documentation

### 6.1 ScummVM `engines/freescape`

Detects and loads every game above on ZX, CPC, C64, DOS, Amiga and ST except Castle Master II on
CPC/C64 (`detection.cpp:1117-1166`), plus 8- and 16-bit 3DCK worlds; some C64 variants are marked
unstable or unsupported. About 59k lines.
Where things are parsed:

| What | Where |
|---|---|
| Field readers (8-bit LE vs Amiga/ST 16-bit BE, doubled pointers) | `loaders/8bitBinaryLoader.cpp:38-89` |
| Group objects (two layouts) | `loaders/8bitBinaryLoader.cpp:91-306` |
| Object records | `loaders/8bitBinaryLoader.cpp:308-622` (colours 394-431, ordinates 434-451, FCL 453-461, entrance 478-538, sensor 540-618) |
| Area header per game | `loaders/8bitBinaryLoader.cpp:626-873` |
| Database header, colour map, global conditions, timer, area table | `loaders/8bitBinaryLoader.cpp:875-1065` |
| Global objects | `loaders/8bitBinaryLoader.cpp:1161-1175` |
| Per-platform offsets | `games/<game>/{zx,cpc,c64,dos,amiga,atari}.cpp` (Driller ZX: `games/driller/zx.cpp:42-92`) |
| ZX tape extraction (TAP/TZX, sampled recordings, two packers) | `zx_tape.cpp`, used by `detection.cpp:1572-1594` |
| C64 unpacking | `loaders/c64.cpp` |
| Object types, flags | `objects/object.h:34-99` |
| Colour/ordinate counts, bounding boxes | `objects/geometricobject.cpp:31-84, 290-428` |
| FCL opcode table and decoder | `language/detokeniser_freescape.cpp:33-225` |
| FCL interpreter | `language/execution_freescape.cpp` (entry points 41-96, `executeCode` 98+) |
| 8-bit / 16-bit 3DCK loaders and FCL | `games/3dck/8bit.cpp`, `games/3dck/3dck.cpp`, `language/*3dck*` |
| Draw order (mirrors the original sort) | `area.cpp:322-375`; culling 263-319; `Area::draw` 430-499 |
| Stipple/shade handling per platform | `gfx.cpp:127-592` |
| Primitive geometry | `gfx.cpp:761-1312` |
| Camera defaults (75° FOV, aspect 2.18, near 2 for Driller) | `freescape.cpp:259-262` |
| Movement, heights, collision | `movement.cpp`, `sweepAABB.cpp` |

ScummVM renders with OpenGL/TinyGL but with depth writes off; ordering comes from its painter's
sort (commit `19acb87f0a` "removed depth testing code"; `3d55dacb49` "reworked painters
algorithm"). Its comments cite disassemblies of DRILL.BIN (CPC), DARKCODE.BIN, TEPROG.BIN,
CM.BIN, totec1.prg (C64), the 68000 binaries and the CM2 Z80 disassembly.

### 6.2 Other sources

- **Castle Master II Z80 disassembly** by Santiago Ontañón (2023), fully annotated, ~16k lines,
  includes all area data: <https://github.com/santiontanon/castlemaster2-disassembly>; HTML version
  linked from its README. The best description of an 8-bit Freescape pipeline available.
- **John Elliott, "Driller room format"** (2001): <https://www.seasip.info/ZX/Driller/>, with
  DRILDUMP (C source; dumps Driller, Dark Side and Total Eclipse databases as text or POV-Ray).
- **Phantasma** by Thomas Harte (2013–2014, MIT): <https://github.com/TomHarte/Phantasma>; 16-bit
  loader and 8/16-bit FCL detokenisers, OpenGL; ScummVM's loader is based on it.
- **3D Construction Kit manuals** (8-bit, 16-bit, 3DCK2): <https://3dconstructionkit.co.uk/docs.html>.
- No 6502 (C64) engine disassembly is public. The Codebase64 "Driller" page referenced by ScummVM
  ticket #15044 is Matt Gray's music. ScummVM's C64 code cites call sites in its own disassembly.

## 7. Performance-relevant structure (all games)

- No far plane: anything inside the area and the frustum is drawn; outdoor areas show the whole
  127-cell platform [measured from the frustum code; Driller extents measured].
- Overdraw is the norm: painter's algorithm with every front face filled. Driller outdoor areas
  start with a 127 × 1 × 127 ground cuboid whose top face is drawn every frame [measured].
- Invisible walls: Driller's four boundary rectangles (ids 51–54) are colour 0, never drawn, but
  carry FCL [measured].
- See 8.5 for per-view counts.

## 8. Driller in depth

### 8.1 Versions and the best oracle

| Version | Data in ScummVM | Notes |
|---|---|---|
| ZX 48K tape (retail) | `DRILLER.ZX.DATA`, 37,590 bytes; DB at file 0x642C, globals at 0x1C93 (8), 4 colours (`games/driller/zx.cpp:42-92`, `detection.cpp:47-56`) | Supported. **Spectrum Computing's `Driller.tzx` (TZX turbo block 5, 37,590-byte body) has exactly ScummVM's md5 (`396c1789…`, first 5000 bytes)** [measured]. Block loads at $6B12 [inferred: seasip's DB address $CF3E − 0x642C; confirmed by globals at $87A5 = 0x1C93 + $6B12]. |
| ZX +3 disc, budget (Hit Squad) | separate offsets (`zx.cpp`) | Hit Squad tape uses a different loader (pure-data TZX blocks) [measured block list]. |
| CPC | `DRILL.BIN` 35,320 bytes; DB 0x5CCB, 16 colours (`games/driller/cpc.cpp:140-146`) | Supported; the original development machine; mode 1. |
| C64 | `DRILLER.C64.DATA` variants; one `ADGF_UNSTABLE` (packed), one unsupported (`detection.cpp:95-128`) | Protected/packed; data colour map wrong; viewport 128 × 104 multicolour. |
| DOS | `DRILLE.EXE` (EGA, DB 0x9B40, 16 colours), `DRILLC.EXE` (CGA, DB 0x7BB0, 4 colours), Hercules, Tandy (`games/driller/dos.cpp:208-280`) | Same database format. |
| Atari ST / Amiga | 16-bit-word copy of the same database (`games/driller/atari.cpp`, `amiga.cpp`) | Coordinates still cells < 256; sensor ranges in "64-units-per-cell" space (`8bitBinaryLoader.cpp:565-570`); no extra colour nibble for Driller. |
| Space Station Oblivion | US title; ScummVM entries for DOS, ST, Amiga, C64 (`detection.cpp:306-359`) | Same game [source: Wikipedia]; I did not compare data. |

Recommendation [inferred]:

- **Data source: ZX retail.** Freely downloadable from a preservation archive
  (<https://spectrumcomputing.co.uk/entry/1521> → `/pub/sinclair/games/d/Driller.tzx.zip`;
  don't redistribute), byte-identical to ScummVM's supported variant, uncompressed, plain 8-bit
  little-endian layout, and its colour model (1bpp patterns + one ink/paper pair) maps onto a BBC
  1bpp mode with no loss. Every version shares the database format, so the area/object content is
  the same; differences are colour handling (ZX attributes vs CPC inks vs C64 multicolour vs 16-bit
  palettes) and storage width.
- **Oracle: ScummVM for geometry, logic and draw order; the ZX binary for exact arithmetic.** ZX
  Z80 code can be run headless under SkoolKit: `tap2sna.py --sim-load` simulates custom loaders,
  `trace.py` runs from a snapshot with `--start/--stop/--max-tstates` and logs T-states, and
  `rzxplay.py` replays input recordings — Spectrum Computing hosts `Driller.rzx`
  [source: [SkoolKit commands](https://skoolkit.ca/docs/skoolkit/commands.html)]. The Driller ZX
  maths shares tables with the annotated CM2 code (identical sin/cos table; 3×3 identity matrix
  with 1.0 = 64 at $6EDB) [measured], so the CM2 disassembly is a map for reading it. C64 6502
  code is closer to the BBC's CPU but is packed, protected, and has no public disassembly; py65
  would need the unpacked image and some VIC/IO stubs.

How to dump the tables: extract the largest data block from the TZX (TAP-style payload minus flag
and checksum), then follow `load8bitBinary` at offset 0x642C with 4 colours and `loadGlobalObjects`
at 0x1C93 × 8. Every area's object walk ends exactly at its condition pointer, which validates the
parse [measured, all 29 areas].

### 8.2 Areas [measured]

29 areas: 18 named platforms of Mitral (Amethyst, Lapis Lazuli, Emerald, Topaz, Obsidian, Basalt,
Ochre, Graphite, Trachyte, Ruby, Malachite, Aquamarine, Beryl, Niccolite, Alabaster, Opal, Quartz,
Diamond), interiors (two Stores, K1–K4 complexes, Linker, Ketar Hangar), "Unknown Area", Mitral
(seen from space), and area 127, the end screen.

| Area | Name | Records | Geometric | Entrances | Sensors | Coloured faces | Scale | Extent (cells) |
|---|---|---|---|---|---|---|---|---|
| 1 | Amethyst | 32 | 26 | 6 | 0 | 72 | 1 | 127,63,127 |
| 2 | Lapis Lazuli | 25 | 22 | 3 | 0 | 80 | 1 | 127,63,127 |
| 3 | Emerald | 35 | 27 | 5 | 3 | 73 | 1 | 127,63,127 |
| 4 | Malachite | 31 | 26 | 3 | 2 | 85 | 1 | 127,63,127 |
| 5 | Ruby | 20 | 14 | 5 | 1 | 35 | 1 | 127,63,127 |
| 6 | Aquamarine | 27 | 23 | 4 | 0 | 51 | 1 | 127,63,127 |
| 7 | Beryl | 32 | 25 | 6 | 1 | 60 | 1 | 127,63,127 |
| 8 | Topaz | 36 | 28 | 4 | 4 | 94 | 1 | 127,63,127 |
| 9 | Niccolite | 30 | 27 | 0 | 3 | 73 | 1 | 127,63,127 |
| 10 | Alabaster | 32 | 31 | 1 | 0 | 71 | 1 | 127,63,127 |
| 11 | Opal | 25 | 24 | 1 | 0 | 43 | 1 | 127,63,127 |
| 12 | Quartz | 28 | 26 | 1 | 1 | 62 | 1 | 127,63,127 |
| 13 | Diamond | 20 | 17 | 1 | 2 | 56 | 1 | 127,99,127 |
| 14 | Obsidian | 36 | 31 | 3 | 2 | 85 | 1 | 127,63,127 |
| 15 | Basalt | 23 | 21 | 2 | 0 | 54 | 1 | 127,63,127 |
| 16 | Ochre | 19 | 15 | 1 | 3 | 35 | 1 | 127,63,127 |
| 17 | Graphite | 23 | 22 | 1 | 0 | 54 | 1 | 127,63,127 |
| 18 | Trachyte | 17 | 16 | 1 | 0 | 42 | 1 | 127,72,127 |
| 19 | Stores | 22 | 21 | 1 | 0 | 68 | 4 | 48,25,80 |
| 20 | Stores | 16 | 13 | 2 | 1 | 36 | 4 | 80,24,48 |
| 21 | K2-Complex | 16 | 14 | 2 | 0 | 37 | 2 | 48,14,80 |
| 22 | K1-Complex | 14 | 13 | 1 | 0 | 34 | 2 | 48,14,80 |
| 23 | Linker | 8 | 6 | 2 | 0 | 7 | 4 | 80,16,16 |
| 25 | K3-Complex | 17 | 16 | 1 | 0 | 22 | 4 | 96,63,96 |
| 27 | Ketar Hangar | 33 | 30 | 3 | 0 | 100 | 4 | 120,48,95 |
| 28 | K4-Complex | 17 | 12 | 1 | 4 | 33 | 1 | 48,14,80 |
| 31 | Unknown Area | 13 | 12 | 1 | 0 | 26 | 1 | 56,9,127 |
| 32 | Mitral | 7 | 4 | 2 | 1 | 12 | 1 | 127,63,127 |
| 127 | end screen | 15 | 14 | 1 | 0 | 61 | 1 | 90,24,100 |

("Coloured faces" = non-zero colour nibbles over geometric objects: an upper bound on faces
drawable in that area.)

- Totals: 669 records, 576 geometric (min 4, median 21, max 31 per area); 197 of the geometric
  objects have a zero dimension (rectangles, axis-aligned polygons, flat boxes); largest dimension median
  16 cells, max 127.
- Typical outdoor platform: a 127 × 1 × 127 ground cuboid (only its top face coloured), edge
  walls as thin cuboids, small doorway rectangles, entrances just inside each doorway, four
  invisible colour-0 boundary rectangles 127 × 63 carrying FCL, gas-pocket centre and radius in the
  area header (e.g. Amethyst x 100, z 100, radius 30 cells).
- Initially-invisible geometric objects per area: 0–10, 80 in total (made visible by FCL: crystals,
  doors, rig-like props); 4 sensors also start hidden. Entrances carry the invisible flags too.
- Ground/sky: Driller has no separate sky/floor rendering; the window is cleared to the area's
  paper colour and the ground is an object [measured data; `games/driller/driller.cpp:293-304` for
  ScummVM's per-platform handling]. ZX outdoor palette is mostly paper 0, ink 7 or 6.
- Entrances: 65; yaw is not limited to right angles (values include 40°, 45°, 170°, 305°, 310°);
  a few have pitch (−10°, 25°, 90°) or roll (90°) [measured].
- Moving between neighbouring platforms uses `GOTO` to entrance 0, which the engine handles by
  keeping the position and wrapping the crossed coordinate to the opposite edge
  (`games/driller/driller.cpp:229-258`).

### 8.3 Driller-specific features: data vs hard-coded

| Feature | Where it lives |
|---|---|
| Gas pocket (x, z, radius) | area header bytes +10..+12 (data) |
| Deploy/recall rig, energy cost 5, success = 100 − 100·(Manhattan distance in cells)/radius, ≥ 50% makes the sector safe, score = random per-area max (10–99 × 1000) × success | engine code (`games/driller/driller.cpp:516-680, 933-957`) |
| Rig placement checks (footprint, must sit on a cuboid) | engine code (`driller.cpp:716-800`) |
| Rig geometry | global objects 255–251 (pyramids + base cuboid), duplicated into the area and positioned by code (`driller.cpp:836-930`); data at ZX $87A5 [measured] |
| Skanner | global objects 248–250, added invisibly to every area at start (`driller.cpp:802-834`) |
| Probe vs jet | `SWAPJET` FCL opcode (data trigger) swaps fly mode and the saved energy/shield pairs (`execution_freescape.cpp:813-851`); flight is engine code |
| Energy, shield | variables 62 and 63/shield; −1 energy per minute (`driller.cpp:1131-1143`); ADD ENERGY/ADD SHIELD in FCL when crystals are shot |
| Timer | `04:00:00` in the database header (data); countdown is engine code |
| Laser beacons | sensor objects: interval, range (world units, 512–12,096 in Driller ZX), axis mask (data); detection and shield damage are engine code (`freescape.cpp:521-563`, `objects/sensor.cpp:85-110`) |
| Win | 18 safe sectors then area 127 (`driller.cpp:967-990`) |
| Panel (ZX) | sector name, X/Z/Y position (world units), vertical extension or "J", angle, step, score, hh:mm:ss, message line (rig status by default), energy and shield bars, plan and side compasses (`games/driller/zx.cpp:94-168`); manual adds transport, movement/attack indicator and operation lights |

### 8.4 Camera, movement and redraw

- Angles: 5° units throughout; turn angle selectable 5/10/15/30/45/90° (database starts at 15°);
  pitch unclamped; roll available [measured; manual; `freescape.cpp:1460-1466`].
- Steps: 1, 2, 5, 10, 25, 50, 100, 250 SDU (database starts at 250) [measured]. ScummVM's table
  stops at 100 and starts at index 6 (`freescape.cpp:236-242`, `driller.cpp:961`), and its units are
  ScummVM's half-scale ones, so its movement is not an exact oracle for step length [measured by
  comparison].
- Probe height: four vertical-extension levels (ScummVM: eye at 0.5, 1.5, 2.5, 3.5 cells at scale 1,
  `movement.cpp:373-385`, `driller.cpp:62-63`); probe "not able to leave the surface"; the jet flies
  by the step size.
- Redraw: no measured figure for any version. The ~1 update per second figure (5.3) is the only
  number. [inferred] like CM2, the 8-bit code redraws only after input. To measure: run
  `rzxplay.py --trace` over Spectrum Computing's `Driller.rzx` and time the interval between
  passes through the screen-copy routine, or `trace.py` a single move from a snapshot.

### 8.5 What a typical Driller view costs [measured, with stated assumptions]

Method: for each of the 65 entrances, put the eye at the entrance cell centre, (2·scale − 0.5)
cells up, facing the entrance yaw; horizontal FOV 75° and a 2:1 window (ScummVM's FOV; Driller ZX
window 208 × 104); count visible (not initially invisible) geometric objects whose box meets the
frustum, and their faces that face the eye with a non-zero colour (cuboids and pyramids by the
slab-side test; planar objects as one face). No occlusion, matching the painter's renderer, which
draws everything that survives culling.

| Per entrance view | min | median | max | mean |
|---|---|---|---|---|
| Objects drawn | 1 | 10 | 20 | 9.5 |
| Faces drawn | 1 | 14 | 39 | 14.7 |
| Polygon vertices (before clipping) | 3 | 56 | 156 | 58 |

Examples: Amethyst entrance 26 (west door, facing east): 15 objects, 23 faces; Malachite
entrance 20: 20 objects, 39 faces; Obsidian entrance 22: 19 objects, 29 faces; Stores (area 19):
15 objects, 20 faces. Pyramid side faces are approximated by their box faces, so pyramid-heavy
views are rough.

## 9. What this means for a fast 6502 renderer (all [inferred])

- **The whole Driller world fits easily.** 11.4 KB of database plus a few hundred bytes of globals;
  one area is 122–600 bytes. Area switching can decode into a fixed-format working copy.
- **Cell-grid geometry suits table-driven transforms.** Every coordinate is an integer cell
  0–127 (or 0–99 in y) and the camera changes once per frame, so per frame build, for each world
  axis, a table `T[k] = k·64·(matrix column)` for k = 0..127 (3 axes × 3 components × 128 × 2 bytes
  ≈ 2.3 KB). A cell-space vertex then transforms with nine table reads and six 16-bit adds, no
  multiplies; subtract the camera's transformed position once. Box vertices are corner + size
  vectors from the same tables (the original already does the corner + size trick).
- **Rotations are quantised to 72 steps**, so the per-frame matrix is a handful of table lookups
  even with Driller's free pitch and roll. Roll can be folded into the matrix or applied as a 2D
  rotation after projection. Yaw-only fast paths (pitch 0, roll 0) remove a third of the work for
  the common case.
- **Projection divides dominate the original's per-vertex cost**; a reciprocal or log/antilog table
  for z with 8-bit precision is enough at 208 × 104.
- **Cuboid back-face culling is free**: the six slab-side bits from the camera position decide face
  visibility with byte compares on cells. Planar objects need one side test against an
  axis-aligned plane, also a compare.
- **Sorting is cheap at Driller's scale** (≤ 20 objects in view, ≤ 31 per area) and must be the
  original's per-axis box comparison to reproduce its draw order (and its glitches). With objects
  on a grid, per-axis comparisons are byte compares against the camera cell.
- **Fill rate is the main cost.** Painter's overdraw plus a ground face that covers the lower half
  of the window on every frame. Options: treat the ground cuboid's top face as a horizon split
  (one fill per scanline span, or a background clear to two colours), and keep the original's
  "face covers the whole screen" skip. 1bpp patterns with a 4-row period make span fills a
  per-row byte constant with edge masks, as in the original.
- **Redraw only on change**, like the original; with step-based movement there is no need for a
  constant frame rate.
- **Clipping**: no far plane; near and side clipping in 3D as the original, or 2D clipping after a
  near-plane clip, since vertices are few (median 56 per view).
- **Data oracle**: decode the ZX database exactly as section 2 describes; compare draw order and
  geometry with ScummVM; compare arithmetic with the ZX code under SkoolKit.

## 10. Open questions

- Measured redraw time of each 8-bit Driller version (ZX, CPC, C64).
- Driller ZX projection constants (CM2: x scale 40/64, z 32/64, 96/56 screen half-sizes); not
  located in the Driller binary; ScummVM's 75° FOV is a fitted value.
- Exact vertical-extension heights in the original Driller (ScummVM's formula is CM2-derived).
- Whether Space Station Oblivion's data equals Driller's.

## Sources

- ScummVM Freescape engine: <https://github.com/scummvm/scummvm/tree/master/engines/freescape> (commit `f6d50c68`, sparse clone, read only).
- Castle Master II disassembly: <https://github.com/santiontanon/castlemaster2-disassembly>.
- John Elliott, Driller room format: <https://www.seasip.info/ZX/Driller/>.
- Phantasma: <https://github.com/TomHarte/Phantasma>.
- 8-bit 3D Construction Kit manual: <https://3dconstructionkit.co.uk/documentation/8-Bit_3D_Construction_Kit_Manual.pdf>; docs index <https://3dconstructionkit.co.uk/docs.html>; game list <https://3dconstructionkit.co.uk/freescape.html>.
- Wikipedia: [Freescape](https://en.wikipedia.org/wiki/Freescape), [3D Construction Kit](https://en.wikipedia.org/wiki/3D_Construction_Kit), [Incentive Software](https://en.wikipedia.org/wiki/Incentive_Software), [Driller](https://en.wikipedia.org/wiki/Driller_(video_game)).
- Ian Andrew's game pages: [Driller](https://www.ianandrew.com/copy-of-splat), [Dark Side](https://www.ianandrew.com/copy-of-driller), [Total Eclipse](https://www.ianandrew.com/copy-of-dark-side), [Castle Master](https://www.ianandrew.com/copy-of-total-eclipse-1).
- Crash #47 Driller review: <https://crashonline.org.uk/47/driller.htm>.
- MSX forum Freescape thread (santiontanon's notes): <https://msx.org/es/node/65187>.
- Spectrum Computing Driller entry (tapes, manual, RZX): <https://spectrumcomputing.co.uk/entry/1521>.
- SkoolKit commands: <https://skoolkit.ca/docs/skoolkit/commands.html>.
- ScummVM ticket on C64 support: <https://lists.scummvm.org/pipermail/scummvm-tracker/2024-March/044702.html>.
- Glu acquires Superscape: <https://socaltech.com/superscape_to_be_acquired_by_glu_mobile/s-0013340.html>.
