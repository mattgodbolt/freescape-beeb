# Journal

How the project got here, in order. What worked, what didn't, and why.

## 2026-10-31: the brief

Research into Freescape, Driller's versions and the BBC's fastest solid 3D
(`docs/research/`) led to `BRIEF.md`. Matt then asked for four colours to
be considered, then MODE 2 and ordered dithering, then "many colours and
as fast as you can make it", working autonomously with agents. That made
decision 2 (MODE 2, a 104 × 104 view at the ZX's geometry) and the design
in `docs/engine.md`.

## 2026-10-31: the screen and the frame loop (track A)

`build/freescape.ssd` boots on jsbeeb's Master into MODE 2 set in the
hardware, double-buffered in main and shadow RAM, with a test scene in
the view (`docs/engine.md`, section 1, "as built"). Measured that day
with `make frames` (jsbeeb's full video, 10s a run):

- The test scene writes its whole view a frame. It runs at 24.97 frames
  a second, every frame shown for 2 fields. Each frame spends 55,769
  cycles between `frame_begin` and `frame_end` and 20,520 waiting in
  `frame_begin`. That wait is what a renderer gains by putting its stages
  0-9 before `frame_begin`.
- With its cost varied at random, 322 frames in 502 fields were shown
  for 1, 2 or 3 fields (155, 152 and 14 frames). All 573 flips landed in
  the vertical blank, at least 30 lines before the next line shown. All
  2,317,952 screen writes went to the buffer not shown.
- The interrupt takes 80-109 cycles a field with no key held, and about
  1,000 while one is (the 28 keys read one at a time).
- `FS` is &371 bytes, the test scene about a third of it.
- MOS 3.20's MODE 2 puts the vertical sync at row 35 with `*TV 0,1`,
  where OS 1.20's table says 34. MOS 3.20 adds the `*TV` setting plus
  one, read from its ROM's table and the CRTC after `*TV 0`, `1` and
  `255`. The disc follows MOS 3.20.
- A soft BREAK while the disc runs puts IRQ1V back to MOS 3.20's and
  returns to BASIC in MODE 7, on jsbeeb.
- `make frames` was checked against deliberately broken copies, each of
  which it failed:
  - no wait in `frame_begin`;
  - the flip to the wrong buffer;
  - a flashing palette entry;
  - a key mapped wrong, or not read;
  - `frame_end` before the writes;
  - the view drawn a byte off;
  - R7 a row out, and interlace on;
  - interrupts held off for longer than the flip's window, and for
    longer than a field;
  - an interrupt longer than a field.
