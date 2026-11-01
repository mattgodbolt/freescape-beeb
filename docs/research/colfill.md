# A column fill, priced and not built

Track U, 2026-11-01. Stages 8-10 (`docs/engine.md`) done down the screen's
byte columns rather than along its lines, the way Rich Talbot-Watkins's
PORTAL and Eben Upton's lander fill (`beeb-3d.md`, `rtw-sources.md`): the
same picture, modelled exactly, its work counted, priced from 6502 kernels
timed in headless jsbeeb, and compared view by view with the row fill's
measured cycles. The bar, set before any of it was built: at least a
quarter off at the median over Driller's 65 entrance views, the busiest no
worse. It doesn't reach it, so it isn't built. Every figure below was
measured on 2026-11-01 with the tools named, at commit 7787d66's row fill
(round 4, `raster.md`).

## Running it

- `make colfill` (one of `make check`'s): the model
  (`tools/model/colfill.py`) against the row fill's (`raster.spans` and
  `writer.view_bytes`) on every scene, sequence frame and Driller view,
  byte for byte, failing on any that differs, with its counts into
  `build/colfill/counts.json`; then the kernels (`src/colfill-kernels.6502`,
  assembled alone into main RAM) timed by `tools/colfillprice.mjs`, which
  checks every byte their runs write, the nodes they leave, the column
  table and each routine's plant, fits the unit costs, and prices each
  Driller view against the row fill's cycles on it (`rastercheck.mjs
  --json`, into `build/colfill/rows-driller.json`).
- `make colfill-live`: the same on the live discs' frames. The cameras of
  `make live`'s records (`build/live/check.json`, every
  `COLFILL_EVERY`-th frame of the logic's run, and every frame of
  `check-free.json`) are rendered by the model (`rasterscenes.py
  --cameras`, the area's objects as they start), each distinct view once,
  and each drawn fresh by the row fill and priced for the column fill.
- `colfillprice.mjs --json OUT` writes each view's price by part, its
  floor (below) and the row fill's cycles; `--verbose` prints them.

## The design (as modelled and priced)

- **The edges are the row fill's.** The chains are walked line by line
  with the row fill's DDA (decision 23), so every line's span is the row
  fill's and the picture can't change; but a line's span goes into the
  face's column table, each pixel column's first line T and end line B,
  rather than into the line's gaps. With the DDA's boundaries a convex
  face's pixels in a column are one run of lines (the model raises if not;
  it holds on every scene and view). A segment where both chains are
  vertical changes no column and is passed over whole: a box's sides under
  a level camera cost nothing a line. Pitch and roll need nothing apart:
  any convex face goes through the same table.
- **Coverage front to back, a byte column at a time.** Each byte column
  keeps its nodes top to bottom: runs of lines open (neither pixel taken),
  left-open or right-open (one pixel taken by a face whose pattern waits in
  the node). A face's two pixel columns' runs go in: lines both pixels take
  are written at once as one run; a line one takes completes a half-open
  node (one byte, merged from the two patterns) or makes an open one
  half-open. MODE 2's two pixels a byte are the half-open nodes, as the
  row fill's shared bytes are its gaps' halves. A column with no nodes is
  full, and faces stop once every column is.
- **Writing.** A column routine for each half of the view's byte columns
  (either side of `CF_SPLIT`, so that a column's offset, 8 a column, fits
  X) and each kind of pattern: `LDA cp+(line AND 3) : STA line,X` a line
  for a dithered pattern, `STA line,X` for a solid one. A run enters at
  its first line's slot with an RTS planted on its end's; each routine
  keeps its plant until a run ends elsewhere, and a run to the view's
  bottom ends on the routine's own RTS when the plant is above it. Merged
  bytes are written one at a time, or as a run through the dithered
  routine with the four merged bytes in `cp` when that's cheaper.
- **The background** fills each column's nodes left at the end.

## The counts

The model counts what the 6502 would do (`colfill.py`'s docstring defines
each). At the median of Driller's 65 views (each count's own median):

| | column fill | | row fill |
|---|---:|---|---:|
| face byte columns looked at | 149 (114 with both pixels alike) | face-lines | 238 |
| face pixel columns' T and B stored | 614 | | |
| lines stepped / passed under vertical chains | 103 / 151 | | |
| nodes walked past / taken whole / their end taken / their start / split | 51 / 52 / 14 / 3 / 30 | | |
| whole-byte runs (faces' / plant kept) | 167 (124 / 101) | runs (pieces) | 303 (228) |
| merged bytes | 95 | shared bytes | 95 |
| bytes in dithered patterns | 3,392 four-phase, 23 two-phase | | |
| bytes in solid patterns | 1,342 | | |

Driller's faces are wider than they are tall in pixels: 307 face pixel
columns against 248 face lines at the median (before occlusion), so even a
byte column at a time the column fill has only a third fewer units of work
than the row fill. The view's bytes are mostly dithered (72% on the mean
view): their pattern byte changes every line, so down a column every
store needs a load.

## The kernels

`src/colfill-kernels.6502`, the inner loops as a column fill would run
them (fixed zero page, page-aligned routines, the hot runs inline). Unit
costs, cycles on jsbeeb's Master, fitted over cases made for each path
(`colfillprice.mjs` prints them):

| | cycles |
|---|---:|
| a run's entry: plant kept / moved / to the bottom on the routine's RTS (dithered) | 43.0 / 78.1 / 58.5 |
| the same, solid | 46.8 / 82.5 / 64.4 |
| a byte: dithered / solid | 8.0 / 5.0 |
| a merged byte on its own; each more line of a run of them | 59 / 73 |
| a face byte column's loop (the head, both pixel columns' runs, the next column) | 96 |
| a full column passed | 43 |
| a node walked past | 21 |
| a node taken whole / its end taken / its start / split (each less its run) | 87 / 67 / 34 / 95 |
| a line stepped, one chain sloping; the second chain | 48; 26 |
| a column table store; each store loop | 13; 12 |
| the background: a column, a node (less its runs) | 36, 36 |
| the frame's columns set up | 1,782 |

The faces' and edges' set-up is the row fill's own code, so the price takes
it from the row fill's profile of the same view (its face and edge parts).
Three things have no kernel and are estimated from the timed parts
(`UNTIMED`): a byte column whose pixel columns differ (its loop, two more
compares, each node its lines touch at the mean case, each node made at the
split's); a half-open node's completion (as a node taken whole, its bytes
as merged bytes); and each face's own set-up (its columns' range, its
pattern's kind, the loop's start), 80 cycles a face.

## The price

Each view drawn fresh (the row fill's `raster_forget` first), cycles from
`raster_frame`'s call to its return:

| | Driller's 65 entrance views: median | p90 | max | 738 live frames: median | p90 | max |
|---|---:|---:|---:|---:|---:|---:|
| row fill, measured | 110,119 | 183,995 | 319,926 | 75,016 | 234,630 | 371,360 |
| column fill, priced | 123,467 | 183,240 | 269,828 | 89,837 | 258,327 | 371,188 |
| the better of the two, each view | 109,115 | 178,452 | 269,828 | 74,253 | 221,504 | 360,279 |
| the column fill's floor (estimated) | 87,266 | 117,534 | 166,945 | 66,276 | 160,227 | 225,596 |

The column fill is priced faster on 19 of the 65 views and 286 of the 738
frames. Its median view by part (each part's median): the faces' and edges'
set-up 18,002, the column table 15,492, coverage 34,651, the runs' entries
8,814, the bytes 38,355, merged bytes 3,789, the background 3,329, the
frame 1,782, the faces' own 1,120. The row fill's median parts on the same
views: insertion (with its runs entered inline) 31,259, bytes 28,632, edges
11,047, background 10,911, faces 7,198, stepping 4,448, runs 4,359, the
stretch 4,062, rows 3,660, next line 2,896.

It gains where the row fill is slowest: by the row fill's cycles, the
column fill's price is 26% over it in the lightest quarter of Driller's
views and 2% under in the busiest (the live frames: 52% over, 5% under).

**The floor** is no measurement: it's what a column fill of this design
couldn't get under however it was written. The faces' and edges' set-up
and the bytes as measured, every run at its kept plant's entry, and every
other operation at the fewest cycles its instructions could take (`FLOOR`
in `colfillprice.mjs`: a byte column's coverage 47 for the loads and
compares it can't do without, a column table store 4 as an unrolled
`STA abs`, a merged byte 35). Its median is 87,266 on Driller's views,
above the bar of 82,589 (three quarters of 110,119); on the live frames
66,276 against 75,016, 12% under.

## Why it doesn't win

- **The dithers.** A pattern is four bytes, one a line (decision 8); along
  a line A holds one byte for the whole run, but down a column it changes
  every line. The row fill writes a byte in 5 cycles whatever its pattern;
  a column routine shared by every column (`STA abs,X`) needs a load every
  line for a dithered one, 8 cycles. On the median view that's about 10,000
  cycles more for the same bytes, a tenth of the whole fill. The other
  ways down a column were counted and don't reach 5 within the memory:
  lander's alternating `TYA` and `LDA zp` (7.75 for four phases); the
  lines of a character row in phase order, two stores a load (6.5, but a
  run that doesn't start and end on a character row needs three entries);
  immediates patched for each pattern (7, and about 420 cycles a face to
  patch); a routine per byte column with A, X and Y holding three of the
  four bytes (about 5.5 with `STA`, `STX`, `STY abs`, but some 20K of code).
- **Driller's faces are wide.** Walls seen from the ground and the floor
  are wider than they are tall, so a byte column at a time saves only a
  third of the units of work, and each does more than a face-line's: the
  column's loop, both pixel columns' runs, the node it cuts, and its run's
  entry.
- **The column table is work the row fill doesn't do.** Every face pixel
  column's first and last line is stored (614 on the median view), and the
  chains are still stepped on every line a sloping edge crosses.
- **What it saves is real but smaller:** fewer runs (167 against 303), no
  per-line insertion under vertical chains, a background of 52 columns
  rather than 104 lines. Those make it the faster on the busiest views,
  which have the most face-lines for their bytes.

## Checks

- The model's view is the row fill's, byte for byte, on all 150 scenes,
  the sequences' 46 frames (each drawn fresh), the 65 Driller views and
  the 738 live frames. (The scenes whose pools overflow the row fill's 127
  gaps are compared with the row fill's model without the pools' limit:
  the column fill has no such limit as modelled. A frame makes up to 236
  nodes on Driller's views and up to 331 on the live frames, counted with
  the untouched columns sharing one (the model's made), so a built one
  would need more than a page of nodes or its own rule for running out, as
  decision 20 has.)
- Mutation testing (2026-11-01, on copies, each change alone): 9 changes to
  the model (the merged byte's halves, a half-open node's side and its
  completion, a face's top, the horizon's split, a run's phase, the
  background's split bytes, the right pixel column, a column counted full
  early) all fail its check; 15 to the kernels (both routines' bytes, the
  plant's removal, its line kept, the own-RTS test, a split's link, an
  unlink through the node before, the walk's previous node, the cases'
  branches, a merged byte's halves and its row, the column table's
  starts, the background's next node, the frame's nodes) all fail the
  harness. Three survived the first version of the harness (an unlink
  past the first node, the walk's previous node, the plant's line kept),
  which a case with a node after the first and a check of each routine's
  plant after every run now catch.

## Found on the way

- Two frames of the free camera's walk in area 4, pitched and rolled
  (camera [3083, 800, 560, 0, 71, 1] and the next, z 528), fail the model's
  own check in `rasterscenes.py`: its span buffer with the exact edges
  disagrees with its brute force (lines 61 and 62). The disc drew the
  model's picture for them (the live check matched every frame), so the
  DDA's view is consistent; but a face there isn't what the rasteriser's
  interface promises (convex, inside the view), perhaps a sliver the cone
  or the 2D clip left a sixteenth out of convex. `rasterscenes.py
  --cameras` leaves such frames out and names them. For the clip track.

## Decisions to record

- **The row fill stays, against a column fill** (proposed 2026-11-01, as
  decision 28 did for the painter's): the column fill gives the same
  picture but is priced slower at the median over Driller's entrance views
  and the live frames, and its floor isn't a quarter under the row fill's
  median; the dithered patterns cost it 8 cycles a byte down a column
  against 5 along a line. Not built; its model and kernels stay checked
  (`make colfill`) for comparison.

## What's left

- **Both ways, chosen a view**: the better of the two takes about 1% off
  the median and a sixth off the busiest Driller view, but needs both fills
  in the bank (the column fill's routines, tables and nodes beside the row
  runs and pools), which hasn't the room.
- **A column fill for the busy views alone** would want the dithers' cost
  gone first: patterns whose four bytes are two (`TYA`/`LDA` alternating),
  or solid colours there, which is a change to the picture and so Matt's
  call (decision 8).
