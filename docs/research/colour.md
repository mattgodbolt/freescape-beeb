# The colour study (decision 8)

*Where the BBC's colours come from, and how MODE 2 shows them. Written
2026-10-31. Every figure here was measured that day by `make colours`
(tools/colour/, tools/pal.py) over the fetched originals; the build
remakes them in `build/colour/study.md`, with the colour values, which
are Driller's and so stay out of the repository. ScummVM references are
`file:line` under `engines/freescape/` at commit
`f6d50c680622aecd03108eca460f9b418782de91`, as in `freescape.md`.*

## In short

- **Every colour version recoloured the faces.** The databases share
  their geometry with the ZX's (all 669 records match by id; 12-37
  objects moved or resized), but 30-45% of the faces' colour
  indices differ, a few dozen faces are drawn in one and not the other,
  and no per-area remap of the ZX's indices reproduces any version (one
  face in three or more would be wrong). So the BBC takes **each face's colour
  index from the version whose colours it follows**, object by object,
  and its geometry from the ZX.
- **What each version gives** an index: the PC's EGA, one of 16 fixed
  colours (the same in every area); the CPC, a two-pen pattern of four
  inks an area from 27; the Amiga and ST, one of 16 colours an area from
  4,096. The sky is black in every area of every version but the CPC's,
  whose background ink is black in all but one. Driller has no ground
  plane: each platform stands on a floor object.
- **MODE 2's patterns**: a 2 × 4 tile, any of the eight colours in each
  pixel, scored in OKLab with penalties for texture, clashing hues and
  hue shifts, and, through jsbeeb's PAL TV, for crawl. Three-colour mixes
  help (the ST's mean error falls by a quarter, its hue shifts from 21 to
  8); 2 × 2 Bayer's quarters cost 45-85% more error than eighths.
- **PAL changes the choice a lot.** Chosen for an RGB monitor, the ST's
  patterns are 4.8 dE out on one and 6.7 through PAL; chosen for PAL,
  3.1 through PAL and 9.1 on RGB, with 247 of 310 colours on a different
  pattern. Chosen for both at once: 6.1 on RGB, 4.2 through PAL.
- **Recommended: the Atari ST's per-area palettes, in 2 × 4 tiles of up
  to three colours, chosen to look right on both displays.** The EGA is
  shown more faithfully (3.9 and 3.7 dE) but has a fixed palette; the ST
  has the most colours (11 an area at the median, 218 across the game),
  each area its own, and is byte-exact to ScummVM's supported release.

## 1. What was fetched, and from where

`tools/fetch.d/30-colour.sh` takes each disc image from the Internet
Archive into `originals/<version>/`; `tools/colour/images.py` reads the
executable out of it in memory (FAT12, AmigaDOS, CPC DSK), and
`tools/colour/sources.py` checks it against ScummVM's detection entry
(`detection.cpp`, md5 of the first 5,000 bytes and the size).

| Version | Archive item | File in the image | Against ScummVM |
|---|---|---|---|
| ZX (the specification) | Spectrum Computing `Driller.tzx` (`10-zx.sh`) | turbo block 5 | `DRILLER.ZX.DATA`, exact (`detection.cpp:52`) |
| DOS | `driller-1989` (`DISK01.IMA`, the PC's four drivers) | `DRILLE.EXE` | exact (`detection.cpp:135`) |
| CPC | `Driller_1987_Incentive_Software` (`.dsk`) | `DRILL.BIN`, with its AMSDOS header | exact (`detection.cpp:88`) |
| Atari ST | `Driller_1988_Incentive_Software_cr_CSM` (`.st`) | `DRILLER/X.PRG` | the budget release, exact (`detection.cpp:160`) |
| Amiga | `Driller_1988-09-27_MicroProse_cr_WOW_a_no_cracktro` (`.adf`) | `DRILLER/driller` and `DRILLER/data` | see below |

The Amiga disc's `driller` has the first 5,000 bytes of ScummVM's
budget release (`detection.cpp:211`) but is longer, and it carries only
placeholder palettes and a placeholder database: it loads both from a
file `data`, as ScummVM's Amiga demos do (`amiga.cpp:369-370`, database
at `0x442`, palettes at 0). ScummVM has no entry for this `data`, so
`sources.py` checks the md5 this study measured. Its database is the
ST's but for 19 objects' colours, and its palettes differ from the ST's
in five areas; it has no palette for area 32 (Mitral) and one labelled
30 instead, so the study gives 32 area 31's, as ScummVM does for its
demos (`palettes.cpp:233-238`). The ST is the cleaner source.

The C64 version isn't fetched. ScummVM reads it from a memory image
made by a procedure on its wiki (an emulator run), packed and protected,
and replaces its colour map with one from the executable because the
data's is wrong (`games/driller/c64.cpp:95-175`). Its colours are the
CPC's scheme with the C64's 16 (four pens an area), so it adds nothing
the CPC doesn't to this choice.

## 2. How each version colours a face

A face's colour is a nibble, 1-15 (0 is not drawn). The database's
header holds a 15-entry colour map, four bytes each
(`8bitBinaryLoader.cpp:915-945`), and each area's header four colour
bytes at +6..+9: usual background, under-fire background, paper, ink
(`8bitBinaryLoader.cpp:658-670`).

- **ZX**: each map entry is a 1-bit pattern, four rows; set bits are the
  area's ink, clear its paper (`gfx.cpp:466-493`).
- **DOS EGA**: each map entry is four bytes of 0 or `&FF`, byte k being
  plane k, so an entry names one of the 16 EGA colours
  (`gfx.cpp:594-631`, `mapEGAColor`). The same 16 in every area: on
  entering an area, `DRILLE.EXE` copies a fixed table holding the
  standard EGA order into its working palette (file offsets `0x8A19`
  and `0x977B`), which the routine at `0x7563` writes to the attribute
  controller's 16 registers (measured by disassembly, 2026-10-31). FCL's
  SPFX (`0x19`) can then load registers 0-3 from the area's four colour
  bytes (`0x7EAA`), and the under-fire flash sets register 0
  (`0x85F4`): run-time effects, not the table. ScummVM's mapping and
  default palette (`palettes.cpp:26-43`) match.
- **CPC**: each map entry is four bytes of mode 1 pixels, four to a byte
  (`freescape.cpp:86-97`), each a pen 0-3; the pens are the area's four
  colour bytes, raw CPC inks (`8bitBinaryLoader.cpp:684-693`,
  `palettes.cpp:109-142`). Every entry is a pattern of at most two pens
  (`gfx.cpp:236-272`). ScummVM draws pen 0 inside a face as black
  (`gfx.cpp:519-524`); on the hardware it is the area's background ink,
  which this study uses. The two differ only in Stores (area 19).
- **Atari ST, Amiga**: the index is the colour, from the area's own
  16-entry palette of 12-bit colours (`gfx.cpp:651-689`,
  `palettes.cpp:187-231`). Their databases keep the CPC's colour map and
  area bytes unused (measured: identical to the CPC's). Bit 14 of an
  area's first word would cycle colour 15 (`8bitBinaryLoader.cpp:633-638`);
  no Driller area sets it.

**Sky.** ScummVM's generic loader reads an area's flags as sky and
ground colours (`8bitBinaryLoader.cpp:650-656`), but for Driller it
clears the view to black on DOS, Amiga and ST, and to the background
ink on the CPC (`driller.cpp:295-304`). Every ST and Amiga
palette has black at entry 0; the CPC's background ink is black in 28
areas and blue in Stores (19).

**Ground.** There is no ground plane: each platform stands on a cuboid
(object 1 in 26 areas, 9 in Alabaster) whose top face is the ground;
Ruby (5) and the end screen (127) have none. `ground(area)` is that top
face's pattern, in the followed version's own index for it, for the
renderer's horizon fill (docs/engine.md, stage 9) if it uses one.

## 3. The database is not the same in every version

Each version's database parsed the same way (`tools/colour/database.py`;
the 16-bit versions' words narrowed to bytes), then compared with the
ZX's object by object, matching by area, id and whether the record is
an entrance (entrances have ids of their own: area 2 has a cuboid and an
entrance both numbered 16).

| Version | Objects differing | Geometry differs | Faces whose index differs | Drawn in one, not the other | Wrong under a per-area remap |
|---|---|---|---|---|---|
| DOS | 332 | 19 | 907 of 2,664 | 28 | 558 of 1,561 |
| CPC | 301 | 12 | 794 | 23 | 506 |
| ST | 453 | 37 | 1,211 | 33 | 656 |
| Amiga | 450 | 29 | 1,203 | 33 | 651 |

The DOS, ST and Amiga have three objects the ZX hasn't (the CPC one),
and a few areas move a gas pocket. The rest is colour: the artists
recoloured each version for its palette, so a ZX index says little about
a face's colour elsewhere. The BBC therefore takes the face nibbles from
the version it follows (`colours.face_colours`), and the 33 faces that
version draws and the ZX doesn't, or the reverse, follow it too.

## 4. MODE 2's patterns

A pattern is four bytes, one for each value of `line AND 3`, each two
pixels: a 2 × 4 tile of eight pixels, anchored to the screen
(docs/engine.md, section 2). A MODE 2 pixel is twice as wide as it is
tall, so the tile is square on the screen.

**Candidates** (`tools/colour/patterns.py`):

- *solid*: the eight colours;
- *bayer2*: two colours in quarters, by 2 × 2 Bayer repeated down;
- *pair*: two colours in eighths, each level's pixels spread as evenly
  as they can be on the screen (the 2:1 pixels counted), chosen per
  level since table entries needn't nest;
- *triple*: *pair* and three-colour mixes in eighths (the two smaller
  groups take a pair's cells, the smallest the most even part of them).

None needs anything of the writer: any four bytes are a pattern, and a
byte where two runs meet takes `left AND &AA OR right AND &55`
whatever the colours. All patterns use colours 0-7 only (`make
colour-check`), so logical 8-15 can be anything.

**Scoring.** OKLab, ×100 ("dE"; about 1 is a just-noticeable
difference). On an RGB monitor a dither's colour is its pixels' mean in
linear light; its *texture* is the RMS dE of the tile blurred by 0.4 of
a line, about that mean; its *clash* is the chroma that cancels in the
mix (red and cyan for grey reads as coloured noise). The score is the
mean's distance (hue differences counted twice, and any tint of a grey
counted as hue) plus 0.35 × texture plus clash. Within an area, colours
more than 3 dE apart get different patterns (by the Hungarian method
over the area's colours), so faces the original tells apart stay apart;
without that, the ST loses 113 visible edges between faces of one
object.

**Through PAL** (`tools/pal.py`, section 5): each candidate is encoded
and decoded over a block of 16 MODE 2 pixels by 16 lines for eight
successive fields and both line parities. Its colour is the decoded
block's mean in linear light; its texture the RMS dE of the blurred
decoded block about that mean, across fields; its *crawl* the part of
that which changes from field to field, which costs 0.35 more. PAL does
the mixing that clash stands for, so a PAL score has no clash term.
Decoding darkens a dither (it averages the gamma-encoded signal) and
smears its chroma over a microsecond, so PAL can show darker and
subtler colours than an RGB monitor, at the price of crawl.

**Choosing for both** scores each candidate by the mean of its two
scores.

## 5. PAL: jsbeeb's PAL TV in NumPy

Matt's steer: "try and use the PAL mode of jsbeeb where you can to see
how much that affects things: we have found it beneficial to use PAL as
that actually blurs the colours better".

`tools/pal.py` ports jsbeeb 2.16.1's shader
(`src/video-filters/shaders/pal-composite.frag.glsl`): each texel to
composite (Y + U sin ωt + V cos ωt, V switched by line), the chroma
demodulated through a 21-tap FIR for the line and the line before it
and blended half and half (the set's 1H delay line), luma through a
31-tap low-pass and subcarrier trap, back to RGB. The FIR coefficients
are those jsbeeb's Vite build bakes in, ported from its
`tools/fir-generator.js` (whose Kaiser window takes cosh, not I0) and
`tools/luma-fir-generator.js`; the subcarrier's cycles a line, with the
offset measured on Matt's Master, and its step a line and a field, from
`src/video.js`. A MODE 2 pixel is four texels of the 1,024-texel line,
and each scanline two framebuffer rows (both measured in headless
jsbeeb). It computes the shader at each texel's centre, so it leaves out
the screen's curvature, the resampling to the canvas, and the
phosphor's persistence.

**Checked** (2026-10-31): the ported coefficients equal jsbeeb's
generators' (run under node) to 7e-12. `tools/colour/pal-glcheck.py`
runs jsbeeb's own shader, with its generated coefficients, in headless
Chrome (WebGL, SwiftShader) over a 1,024 × 48 picture of random MODE 2
pixels and the study's patterns, for four phases and line parities: the
largest difference from the port is 1 of 255, in under 1% of the bytes.
It needs a jsbeeb checkout and Chrome, so it isn't in `make check`;
`make colour-check` tests that the filters pass DC and a field of each
colour comes back unchanged.

`python -I tools/pal.py IN.png OUT.png` shows a jsbeeb screenshot
through it: a full 1,024 × 625 framebuffer as it is, an active-area
screenshot with `--shrink 2`, a picture at the BBC's pixel grid with
`--texels 4 --rows 2` (MODE 2). `--phase` picks the field.

## 6. The figures

Means are over each area's used colours, then over areas; worst is the
worst colour in any area. All 2026-10-31, `build/colour/study.md`.

**On an RGB monitor, by scheme** (chosen for and seen on RGB; distinct
colours kept apart except in *solid*):

| Version | solid | bayer2 | pair | triple | Texture (triple) | Hue moved (triple) |
|---|---|---|---|---|---|---|
| DOS EGA | 16.2 / 45.0 | 5.8 / 18.0 | 4.0 / 11.3 | 3.2 / 5.1 | 8.6 | 0 of 244 |
| CPC | 13.2 / 47.6 | 3.9 / 32.3 | 2.1 / 16.1 | 0.8 / 12.0 | 7.4 | 1 of 254 |
| ST | 23.6 / 49.0 | 10.3 / 36.1 | 6.3 / 24.9 | 4.8 / 24.9 | 16.6 | 8 of 309 |
| Amiga | 23.7 / 49.0 | 10.5 / 36.1 | 6.5 / 24.9 | 5.0 / 24.9 | 16.7 | 9 of 304 |

(mean / worst dE.) Solid colours lose 175 of the ST's 309 area colours
to merges and 737 edges; any dither scheme keeps them all apart.

**Chosen for one display, seen on each** (scheme *triple*):

| Version | Chosen for | RGB: mean / worst / texture | PAL: mean / worst / texture / crawl | Used indices whose pattern differs from RGB's choice |
|---|---|---|---|---|
| DOS EGA | RGB | 3.2 / 5.1 / 8.6 | 3.8 / 6.8 / 7.4 / 4.1 | — |
| DOS EGA | PAL | 5.6 / 10.7 / 8.2 | 2.6 / 6.4 / 7.0 / 3.6 | 133 of 244 |
| DOS EGA | both | 3.9 / 6.4 / 7.6 | 3.7 / 6.8 / 6.9 / 3.8 | 43 of 244 |
| CPC | RGB | 0.8 / 12.0 / 7.4 | 5.7 / 15.4 / 5.9 / 2.9 | — |
| CPC | PAL | 5.4 / 18.3 / 7.4 | 2.1 / 8.6 / 5.5 / 2.7 | 176 of 255 |
| CPC | both | 2.0 / 11.1 / 7.5 | 4.0 / 11.9 / 5.9 / 2.6 | 77 of 255 |
| ST | RGB | 4.8 / 24.9 / 16.6 | 6.7 / 24.9 / 13.0 / 4.0 | — |
| ST | PAL | 9.1 / 22.7 / 14.2 | 3.1 / 13.9 / 10.5 / 4.8 | 247 of 310 |
| ST | both | 6.1 / 24.4 / 15.8 | 4.2 / 15.8 / 12.3 / 4.0 | 138 of 310 |

Chosen for PAL alone, the ST's greys and pinks turn to complementary
mixes (red and cyan, green and magenta) that PAL's chroma filter
averages away and an RGB monitor shows as coloured noise; chosen for
both, they stay black and white, red and white. Area by area, each area
needs one pattern per colour its faces use, 4-14 (`study.md` has every
area for every version).

**Looking at the swatches** (`build/colour/swatches/st-both/` and the
others: source, RGB monitor, PAL TV, magnified at MODE 2's aspect):
mid and light colours come out well on both; a checkerboard of two
colours reads as their mix on either display. The weak spot is dark
colours: below one lit pixel in eight (a grey of about #636363 on RGB)
the BBC has only black, so the ST's very dark shades become sparse dots
(texture about 30) or move hue to stay apart from a neighbour; the
worst, a very dark green in Quartz (12) that must differ from black and
from a slightly lighter green, goes to one green and one blue pixel in
eight (24.4 dE on RGB). PAL softens these: the same pattern is 15.8
through it, its worst.

## 7. The options

| Option | Colours an area (median, max) | Mean dE RGB / PAL (triple, for both) | Worst | For | Against |
|---|---|---|---|---|---|
| **A. Atari ST** | 11, 14; 218 in the game | 6.1 / 4.2 | 24.4 / 15.8 | The most colours, each area its own palette, as the 16-bit versions looked; byte-exact to ScummVM's supported ST release, so ScummVM renders the reference | Dark shades become sparse dots; texture twice the EGA's |
| B. Amiga | 11, 13 | 6.3 / 4.3 | 24.4 / 15.8 | As A | Its data file isn't one ScummVM knows; no palette of its own for area 32 |
| C. DOS EGA | 9, 10; 12 in the game | 3.9 / 3.7 | 6.4 / 6.8 | Shown best of the many-colour versions: 16 saturated colours suit eight; least texture | The same palette in every area; the PC's look |
| D. CPC | 9 mixes of 4 inks | 2.0 / 4.0 | 11.1 / 11.9 | The original development machine; its two-pen patterns land well | Four colours an area, not "many colours" |

Within any option: *triple* over *pair* (lower error, fewer hue shifts,
no more texture), and choose for both displays unless the project fixes
one (a one-line switch, `patterns.DISPLAY`; `bbc-st-pal.json` and
`bbc-st-rgb.json` are built too).

**Recommended: A, in *triple*, chosen for both displays.** The brief is
many colours, and the ST's per-area palettes are the version of Driller
with the most of them; the BBC holds them to a mean of 4-6 dE, against
the EGA's 4, at the cost of more visible dithering in dark areas. If
that texture looks wrong in the running game, C is the fallback with
the same code: only `CHOSEN` in `design.py` changes.

## 8. Decision 8, as proposed

> ## 8. Where the colours come from (2026-10-31, autonomous)
>
> **The Atari ST's colours, shown by MODE 2 patterns of up to three of
> the BBC's eight colours, chosen to look right on an RGB monitor and on
> a PAL television.**
>
> - The ST's per-area palettes give each face's colour index its colour
>   (16 colours an area from 4,096). Every colour version recoloured the
>   faces for its palette, so the BBC takes each face's colour index from
>   the ST's database, object by object, and its geometry from the ZX's
>   (decision 1).
> - Each colour is a 2 × 4 pattern of the eight colours, anchored to the
>   screen, chosen by OKLab distance with penalties for texture, crawl
>   through PAL, clashing hues and hue shifts; colours an area tells apart
>   get different patterns. The sky is black; the ground is the floor
>   object's top face.
> - Why: the most colours of any version, each area its own; mean error
>   6.1 dE on an RGB monitor and 4.2 through jsbeeb's PAL TV, against the
>   EGA's 3.9 and 3.7 with one fixed palette (docs/research/colour.md).

## 9. For the other tracks

- `tools/model/colours.py` (reads `build/colour/bbc.json`; run `make
  colours`, which needs `make fetch`):
  - `pattern(area, index)`, `sky(area)`, `ground(area)`: `bytes` of
    four, one for each value of `line AND 3`. `area` is an id or a
    record with an `"id"`. `index` 1-15; 0 raises.
  - `face_colours(area, object_id)`: the object's colour nibbles in the
    ST's database, in the database's face order, or `None`. **The data
    and model tracks should draw faces with these, not the ZX's**, and
    skip a face whose nibble here is 0.
  - `floor(area)`: the object the ground stands for (`None` in Ruby and
    the end screen); `version()`; `PALETTE`, logical colour to RGB.
- docs/engine.md, section 2 says a pattern is "up to two" colours; with
  *triple* it is up to three. Nothing in the writer changes.
- The palette: logical n is physical n for 0-7, as the screen track
  programs it; the patterns use nothing else.
- `tools/pal.py IN.png OUT.png` for README screenshots through PAL.

## 10. What's left

- SPFX (15 uses in the FCL) and the under-fire flash change colours at
  run time, differently in each version: the logic layer will need the
  ST's SPFX semantics (`execution_freescape.cpp:446-490`) and patterns
  for what they set.
- Tune on real views: the scores weigh each colour once (or by faces);
  weighting by the pixels each index covers in the entrance views, once
  the renderer counts them, would favour calm patterns on big faces
  (floors) and accurate ones on small.
- Check the ST colours against ScummVM's ST rendering of an entrance
  view, as the image oracle for colour.
- VideoNuLA's 16 colours from 4,096 would show the ST's palettes
  directly, an extra for a later layer.
