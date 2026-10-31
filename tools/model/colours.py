"""Patterns from colours (docs/engine.md, section 9; decision 8).

pattern(area, index), sky(area) and ground(area) each give four bytes, one
for each value of `line AND 3`, each the MODE 2 byte for the two pixels it
covers. `area` is an area id or a record with an "id" (the model's area).

The colours follow one of Driller's colour versions (docs/research/colour.md):
its colour for each index in each area, shown by the BBC's best 2 x 4
pattern. Which pattern is best depends on the display, so there is a table
for each: "rgb" (an RGB monitor), "pal" (jsbeeb's PAL TV, and a television)
and "both" (right on either). Each call takes `display`; without one it
uses DISPLAY, which the environment variable FREESCAPE_DISPLAY sets and
which is "pal" otherwise, as the README's jsbeeb link shows the game.

The face colour indices come from that version's database too, because
each version recoloured the faces for its own palette: so
face_colours(area, object id) gives the object's colour nibbles to draw it
with (0 is not drawn), in place of the ZX's. They are the same in every
display's table.

Everything is computed at build time from the fetched originals into
build/colour/bbc-DISPLAY.json (`make colours`); nothing derived from them is
committed, so this module reads build/.
"""

import json
import os
import pathlib

DISPLAYS = ("rgb", "pal", "both")
DISPLAY = os.environ.get("FREESCAPE_DISPLAY", "pal")
if DISPLAY not in DISPLAYS:
    raise ValueError(f"FREESCAPE_DISPLAY is {DISPLAY!r}, not one of {DISPLAYS}")

_DIR = pathlib.Path(__file__).resolve().parents[2] / "build" / "colour"

# Logical colour to RGB for pictures: logical n is physical n, and the
# patterns use only 0-7.
PALETTE = [tuple(255 * ((c >> b) & 1) for b in range(3)) for c in range(8)] * 2

_cache = {}


def _table(display=None):
    display = display or DISPLAY
    if display not in DISPLAYS:
        raise ValueError(f"display {display!r}: not one of {DISPLAYS}")
    if display not in _cache:
        path = _DIR / f"bbc-{display}.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing: run `make colours`")
        with open(path) as f:
            _cache[display] = json.load(f)
    return _cache[display]


def _area(area, display=None):
    aid = area["id"] if hasattr(area, "__getitem__") and not isinstance(
        area, int) else area
    try:
        return _table(display)["areas"][str(int(aid))]
    except KeyError:
        raise KeyError(f"no colours for area {aid}") from None


def version(display=None):
    """Which original the colours follow ("st", "dos", ...)."""
    return _table(display)["version"]


def pattern(area, index, display=None):
    """The pattern for a face of colour index 1-15 in the area."""
    if not 1 <= index <= 15:
        raise ValueError(f"colour index {index}: 0 is never drawn")
    return bytes(_area(area, display)["patterns"][index - 1])


def sky(area, display=None):
    """What the view is cleared to above the horizon."""
    return bytes(_area(area, display)["sky"])


def ground(area, display=None):
    """The floor's colour below the horizon: the top face of the area's
    floor object (floor(area)), or the sky where it has none."""
    return bytes(_area(area, display)["ground"])


def floor(area):
    """The id of the object the ground stands for, or None."""
    return _area(area)["floor"]


def face_colours(area, object_id):
    """The object's colour nibbles in the followed version (six for a
    cuboid or pyramid, two for a flat shape, in the database's face order),
    or None if it has none there."""
    c = _area(area)["faces"].get(str(object_id))
    return list(c) if c is not None else None
