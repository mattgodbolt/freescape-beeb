"""Montages of the live disc in play, through PAL, for the README.

    .venv/bin/python -I tools/mkgameshots.py SHOTS_DIR OUT_DIR

SHOTS_DIR holds the PAL shots (tools/pal.py --shrink 2 of tools/play.mjs's
screenshots) the `make game-shots` rule takes. Writes OUT_DIR/disc_game.png
(the start, a rig set down, the laser firing) and OUT_DIR/disc_screens.png
(the information screen and the end's scene). Driller is Incentive
Software's (decision 6: the tech-demo disc's screenshots only).
"""

import sys
from pathlib import Path

from PIL import Image

# The active picture within the shrunk PAL screenshot: view and panel.
CROP = (174, 118, 706, 502)
GAP = 8

ROWS = {
    "disc_game.png": ["start", "rig", "laser"],
    "disc_screens.png": ["info", "end"],
}


def montage(names, shots):
    tiles = [Image.open(shots / f"game_{n}_pal.png").convert("RGB").crop(CROP) for n in names]
    w, h = tiles[0].size
    out = Image.new("RGB", (w * len(tiles) + GAP * (len(tiles) - 1), h), (0, 0, 0))
    for i, t in enumerate(tiles):
        out.paste(t, (i * (w + GAP), 0))
    return out


def main():
    shots, out = Path(sys.argv[1]), Path(sys.argv[2])
    for name, parts in ROWS.items():
        montage(parts, shots).save(out / name, optimize=True)


main()
