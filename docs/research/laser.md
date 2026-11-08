# Driller's laser on the BBC

*2026-11-08. The laser layer of the live disc: what the original does when
0 fires (read from its listing, `make zxdisasm`), what the disc does, and
how each is checked. Addresses written `$` are the original's. Figures are
the journal's (2026-11-08, "the laser and the sensors").*

## The original

Fire (action `$16`, the key 0, in shooting mode or out of it) does
nothing unless the crosshair is shown (`CrossOn`). Then (`$AA50`-`$AA96`):

- **The lines.** Four lines, each from a point by a corner of the view's
  bottom to the crosshair: (1, 5), (2 cx, 5), (5, 1) and (2 cx − 5, 1),
  in the crosshair's coordinates (x from 1 to twice the view's centre
  `ViewCentre`, y up from the view's bottom), two from each corner, a
  pixel apart, so each beam is two pixels thick. Each is drawn by `$A803`,
  a DDA along the longer axis (y on a tie), its error starting at half that
  axis and the shorter axis stepping when the error, plus the shorter's
  length, reaches the longer's; every pixel EORed (`$A926`).
- **The sound.** Sound 1 (a rising buzz) plays between drawing the lines
  and drawing them again, which takes them off. The beeper holds the
  game meanwhile: the lines show while it sounds.
- **The pick** (`$B153`): the last redraw's draw list from its nearest
  object back. For each of an object's projected faces: its vertices must
  bracket the crosshair on both axes (one on it counts); then the polygon,
  closed, has each edge whose ends bracket the crosshair's row crossed at
  that row (by the original's divide), up to five crossings, and the face
  is round the crosshair if a crossing is on its column or they bracket
  it. A horizontal edge on the row hits at once. The first object with
  such a face is hit: its id into `Collided`. An object whose projected
  record's count has bit 7 set is hit at once. Nothing hit leaves
  `Collided` as it was (0 from the pass's start, unless a move in the same
  pass set it).
- Then `EventsDue` and `ShotFlag`: the events run the hit object's script
  with its shot instructions (FCL opcodes with bit 7), as the transcription
  had done since the logic's first track.

The pick is on the last redraw's projection, which is the camera as the
pass began: a pass that looks up and fires picks from the view before the
look.

## On the disc

`src/laser.6502`, `src/live.6502`.

- **The pick** (`lv_pick`, in `LiveGlue`, `LOGIC_BANK`'s room; the logic's
  `hook_shot` is `lv_hook_shot`, which pages it in and the pass's bank back):
  the front end leaves its draw list (`dl_*`), each
  object's faces (`tf_*`) and their clipped polygons (`out_v*`) in place
  until its next frame, so the pick walks them as the original walks its
  list: nearest first (`emit_faces`' order), and hits the first face whose
  polygon holds the crosshair pixel's centre, its edges and vertices
  counting (decision 131). The test: the vertices bracket the point on both
  axes; then no two edges' cross products with the point have opposite
  signs. The object is the face's slot's place in the logic's index
  (`ob_ix`, read with ACCCON's X clear) and its id there (`ix_id`). Nothing
  a face is stored to do it: the fifteenth round's plan of a slot a face
  (`out_fo`) wasn't needed.
- **The frame it picks from** is the one last drawn, so a pass that may
  fire (0 held or gone down) waits while the last pass's frames show, until
  the frame of its end is drawn (`lv_pass`): the original's last redraw is
  its camera.
- **The lines** (`lz_eor`): the original's four, by its own DDA, at the
  view's half width: each end's x halved as the crosshair's is (decision
  38), the DDA run in the BBC's pixels (decision 130), each pixel EORed
  with colour 7 as the crosshair's are. They're frames of their own, as the
  crosshair's: `lv_hook_laser` keeps the crosshair the shot is fired at; the
  pass's end puts the lines up (`lz_on`) for `LASER_FIELDS`, sound 1's
  fields; the frame's inputs (`lv_inputs`' `VW_LASER`) bring a frame when
  they come and go, which takes off the lines the buffer had and draws the
  frame's (`lv_cross_off`, `lv_cross_on`, with the crosshair). The next
  pass waits for the lines' fields (as `hook_wait`), as the original
  holds the game while sound 1 plays.

## The checks

- **Against the original** (`make logic`): `tools/logic/view.py` renders
  the BBC's model of the frame the pass began with (`tools/model/pick.py`
  picks over its faces, nearest first), and the transcription's
  `hook_shot` takes its answer; `tests/logic/shoot.txt` fires at the sky,
  a cuboid whose shot hides it and scores, the sky behind it once it's
  gone, the floor, a pyramid, a tall cuboid, a cuboid far up whose shot
  destroys it, a sensor (a pixel) and the wall beside it, from four views,
  after moving the crosshair and in and out of shooting mode, and the
  original's own pick agrees on each. The two projections differ by up to a
  pixel (decision 41's figures), so a target a pixel wide, or the
  crosshair within a pixel of an edge, can differ: the scenarios aim
  inside.
- **Against the model** (`make live`): `tools/mklive.py --trace` asks the
  model's pick for each shot, so every pass's state after a shot, its
  scripts run, is the model's; each shot's lines must be fired at the
  transcription's crosshair, for `LASER_FIELDS`; and every frame with the
  lines is the model's render with them, byte for byte (`tools/mklive.py`'s
  `laser`).

## What's left

- The original's pick on its own projection could be the disc's, by
  projecting the ZX's way again for the pick only: not worth it while the
  two agree away from edges.
- The lines take a field or so to draw (the journal's figures): the plot
  works out each pixel's address afresh.
