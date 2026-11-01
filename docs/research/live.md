# Driller live: the whole pipeline on the BBC

*Track L, 2026-10-31. `build/live.ssd` (`src/live.6502`, `tools/mklive.py`)
draws every frame from the camera alone: the object pipeline (stages 1-7,
`objects_frame`), then the rasteriser and writer (stages 8-10,
`raster_frame`), between `frame_begin` and `frame_end`. Nothing of a view
is worked out off the BBC. `tools/livecheck.mjs` holds every frame it shows
to the model's render of that frame's camera, byte for byte. Figures are in
the journal (2026-10-31, "the whole pipeline live"), not here.*

## Running it

```sh
make live        # build/live.ssd and its check (one of make check's)
make live-run    # screenshots of LIVE_SHOTS' entrances, RGB and PAL, into shots/
node tools/livecheck.mjs --verbose            # every frame's camera and cycles
node tools/livecheck.mjs --walks 3,30 --json build/live/check.json
```

On the disc: cursor left and right (or Q and W) turn 5° a frame, cursor
up and down (or O and K) walk `LIVE_STEP` world units along the view a
frame, through anything; P and L look up and down, N and M roll; SPACE goes
to the next entrance, in the database's order, from area to
area. With no key for `DEMO_FIELDS` fields the demo turns on the spot a
step a frame, and after a whole turn goes on to the next entrance. A key
tapped for less than a frame still acts once (`keys_made`).

## The frame

`live_loop`, once a frame:

1. `live_keys` moves the camera (`lv_cam`, in the shape of the pipeline's
   `cam_*`), or goes to an entrance (`live_go`).
2. The camera into `cam_x` .. `cam_roll`; ACCCON's X cleared (the cache is
   in main RAM's `&3000` on); `objects_frame` with `BANK_OBJ` paged. Its
   output is the rasteriser's input already (below); the glue copies one
   byte, `out_nf` to `rs_nfaces`.
3. `frame_begin`, then `raster_frame` with `BANK_RASTER` paged.
4. The figures (`live_measure`), the text as the beam allows, `frame_end`.

A still camera redraws in full every frame, so the figures are always the
pipeline's cost. Every frame shows the camera as `live_keys` left it: no
frame is skipped or reused.

### The glue

- **The output is the input.** `ObjOut` (`out_fn`, `out_fv`, `out_fc`,
  `out_vxl` ..) is laid over `RasterIn` array for array: `RasterIn` starts
  where its vertex arrays fall page-aligned straight after its face arrays,
  as `ObjOut`'s do, and `ObjOut` starts two bytes before `rs_fn`, so its
  two counts land on the horizon's bytes (unread with no horizon, decision
  8a) and `rs_overflow` (which `raster_frame` sets after `out_vn` is done
  with). `live.6502` ASSERTs each pair of arrays the same, so a change on
  either side fails the build rather than the picture.
- **Patterns by colour index** (decision 8b): `rs_pat`'s pattern 0 is the
  area's sky and patterns 1-15 its colour indices', so `out_fc` is `rs_fc`.
  `live_go` copies an area's `LIVE_PATTERNS` (`ld_pats`, from
  `tools/model/colours.py`'s table for the build's display) in on entry and
  calls `raster_forget`. The sky is the background; there's no horizon.
- **Entering an area** is `area_enter` (`src/area.6502`), which builds the
  area's working copy from Driller's database in the logic's bank
  (`objects.md`, "The records"), paging that bank and the conversion's
  (`AreaConv`, in `BANK_DATA`) in, and puts `ROMSEL_COPY`'s back. Its entry
  points and its reader of the database's records are in their own section,
  `AreaCode`, in main RAM, since code in a bank can't page another in from
  under itself; `&F4` (`ROMSEL_COPY`) is out of baron's pool.
- **Paging**: `PAGE_IN bank` sets `romsel` and `ROMSEL_COPY` together. Code
  in main RAM pages; nothing in a bank pages another.

### The figures

Below the view, drawn into both buffers (`src/text.6502`): frames a second
and fields a frame from the flips and fields counted (`frames`, `fields`),
and the mean cycles a frame of each half, in thousands; each over the
frames since the figures were last drawn, every `FIGURE_FIELDS` fields.

The halves are timed on the BBC by User VIA T2, which runs free down at
1MHz and wraps every 65,536 microseconds, beside the fields counted
(`clock`, `clock_to`). A span that saw n vertical syncs is longer than n − 1
fields and shorter than n + 1, a window of two fields, narrower than T2's
wrap (`ASSERT 2 * FIELD_US < 65536`), so its length is the one value in
that window with T2's difference modulo 65,536. A sync flagged and not yet
counted when the clock is read counts. The check holds the BBC's own figure
for every frame to the emulator's count of the same span, within
`CLOCK_SLACK` cycles.

## Memory

Each region's bounds are ASSERTed in `src/live.6502`; `build/live.json` has
the addresses.

| Where | What |
|---|---|
| bank `BANK_DB` | the player logic's database bank as the logic builds it (`LOGIC`, from `build/logic6502/`, its `LOGIC_BANK`): Driller's database at its top, which `area_enter` builds each area's working copy from, and the logic's code that reads it, unused yet |
| bank `BANK_DATA` | `LiveData` (`LDATA`: the areas' names and patterns, the entrances' cameras, the step for each yaw, and the figures' arithmetic), the text's widened font (`TextRAM`), and the working copy's conversion (`AreaConv`, `ACONV`: its code, each area's colour stream, the tape's globals). It's the logic's `LOGIC_CODE_BANK`, so the logic's arrival means sharing it |
| bank `BANK_RASTER` | the rasteriser: row runs, code, work, state (decision 20) |
| bank `BANK_OBJ` | the object pipeline's code (`ObjCode`) with the maths' (`src/maths.6502`, `src/project.6502`, which patch themselves) |
| HAZEL | the maths' tables (`HAZEL`) and the transform's f64 table (`ObjTables`, `OTABLE`, on a page boundary), loaded from `HAZEL_LOAD` on by `!BOOT` and copied up once the OS is gone (ACCCON's Y then stays set); then `ObjWork` (the camera with it) |
| `&0E00` on | `LIVE` (this code, the screen, the interrupt, the keys, the text), `AreaCode` (`LAREA`: `area_init`, `area_enter` and the database's reader), `ObjConst` (`OCONST`: the loops, the sine table, the matrix's and the clip's tables), `ObjArea`; the rest up to `&3000` free, room for `RasterIn` when `LogicWork` takes the OS's pages |
| `&0400` on | `Work` (`src/zp.6502`) |
| `RASTER_IN_ORG` to `RASTER_IN_END` | `RasterIn`, with `ObjOut` over it, in the OS's pages, which nothing uses once the engine owns the machine |
| main RAM's `&3000` on | the transform's cache (`ObjCache`), which only `objects_frame` touches: `live_loop` clears X before it, and `frame_begin` sets X for the buffer drawn after (decision 31) |

## The check

`tools/livecheck.mjs` boots the disc on jsbeeb's full video, headless, and
drives it by its keys: SPACE round every entrance (each shown for
`TOUR_FRAMES` frames), then at each of `--walks`' entrances the keys held a few frames
each (the cursors and Q W O K, P L N M, turning and walking together), then
no key until the demo starts. It fails unless:

- every frame shown is the model's render (`tools/mklive.py --render`,
  `tools/model/render.py`) of the area and camera its `objects_frame` was
  given, byte for byte;
- each SPACE goes to the next entrance, each hold moves the camera as its
  keys ask (and only so), the demo turns a step a frame, and a key stops it;
- every flip shows the one frame handed over, after the last was shown
  whole; both buffers hold the same outside the view at every flip, and
  the text there is `text_shown`'s at every eighth;
- every frame handed over shows its area's name and entrance below it;
- every write to the view is inside a frame, into the buffer not shown,
  and every write outside it to the buffer shown comes with the beam above
  its row;
- the BBC's own timing of each half is the emulator's (above).

It reports fields a frame, median, p90 and most: flip to flip (what the BBC
shows), the loop (`frame_end` to `frame_end`), each half (from the call to
`live_front_done` and `live_fill_done`) and the rest; over every frame and
by what the frame did: an entrance's first frame, a turn (the angles
changed, so the transform's cache refilled), a walk (the camera moved, the
cache kept), a still frame, the demo.

## What it needs from the other tracks

- **The front end (M)** and **the rasteriser (G)**: keep `objects_frame`,
  `raster_frame`, `raster_forget` and `area_enter`; keep `ObjOut` and
  `RasterIn` laid out alike (or agree one set of arrays for both); and fit
  their banks (`BANK_OBJ`, `BANK_RASTER`), which the ASSERTs watch.
  `AreaCode` must stay out of sideways RAM.
- **The player logic (J)**: the logic's labels `sq_lo`, `sq_hi` (and its
  two-argument `PAGE` macro) meet the maths' and this file's names in one
  assembly; and `LogicWork` (`&0800-&0CFF`) is where `RasterIn` is now.
  The working copy is built from the logic's database bank already, and
  main RAM past `ObjArea` is free for `RasterIn` to move to. With the
  logic: `OBJ_LOGIC`, `AREA_GLOBALS = Globals`, and `area_enter` after each
  of the logic's area loads (`AreaChanged`); and `LOGICC` in `BANK_DATA`
  beside `LiveData`, the font and `AreaConv`, which don't all fit there
  beside it.
- **The maths (F)**: the projection's shared-coordinate entries are reached
  by a stub (`live_shared`) until a stage calls them.
