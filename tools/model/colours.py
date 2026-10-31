"""Patterns from colours (docs/engine.md, section 9; decision 8).

pattern(area, index), sky(area) and ground(area) each give four bytes, one
for each value of `line AND 3`, each the MODE 2 byte for the two pixels it
covers. `area` is an area id or a record with an "id" (the model's area).

The colours follow one of Driller's colour versions (docs/research/colour.md):
its colour for each index in each area, shown by the BBC's best 2 x 4
pattern. The face colour indices come from that version's database too,
because each version recoloured the faces for its own palette: so
face_colours(area, object id) gives the object's colour nibbles to draw it
with (0 is not drawn), in place of the ZX's.

Everything is computed at build time from the fetched originals into
build/colour/bbc.json (`make colours`); nothing derived from them is
committed, so this module reads build/.
"""

import json
import pathlib

_TABLE = (pathlib.Path(__file__).resolve().parents[2]
          / "build" / "colour" / "bbc.json")

# Logical colour to RGB for pictures: logical n is physical n, and the
# patterns use only 0-7.
PALETTE = [tuple(255 * ((c >> b) & 1) for b in range(3)) for c in range(8)] * 2

_cache = None


def _areas():
    global _cache
    if _cache is None:
        if not _TABLE.exists():
            raise FileNotFoundError(f"{_TABLE} is missing: run `make colours`")
        with open(_TABLE) as f:
            _cache = json.load(f)
    return _cache["areas"]


def _area(area):
    aid = area["id"] if hasattr(area, "__getitem__") and not isinstance(
        area, int) else area
    try:
        return _areas()[str(int(aid))]
    except KeyError:
        raise KeyError(f"no colours for area {aid}") from None


def version():
    """Which original the colours follow ("st", "dos", ...)."""
    _areas()
    return _cache["version"]


def pattern(area, index):
    """The pattern for a face of colour index 1-15 in the area."""
    if not 1 <= index <= 15:
        raise ValueError(f"colour index {index}: 0 is never drawn")
    return bytes(_area(area)["patterns"][index - 1])


def sky(area):
    """What the view is cleared to above the horizon."""
    return bytes(_area(area)["sky"])


def ground(area):
    """The floor's colour below the horizon: the top face of the area's
    floor object (floor(area)), or the sky where it has none."""
    return bytes(_area(area)["ground"])


def floor(area):
    """The id of the object the ground stands for, or None."""
    return _area(area)["floor"]


def face_colours(area, object_id):
    """The object's colour nibbles in the followed version (six for a
    cuboid or pyramid, two for a flat shape, in the database's face order),
    or None if it has none there."""
    c = _area(area)["faces"].get(str(object_id))
    return list(c) if c is not None else None
