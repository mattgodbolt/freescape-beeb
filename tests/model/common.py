"""What the model's tests share: Driller's database, when make data has made
it (tests that need it skip without it; nothing of Driller's is committed)."""
import functools
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
DB_PATH = ROOT / "build" / "data" / "driller.json"


@functools.lru_cache(maxsize=1)
def db():
    with open(DB_PATH) as f:
        return json.load(f)


needs_data = unittest.skipUnless(DB_PATH.exists(), "needs build/data/driller.json (make data)")


def sine_tables():
    """The 72-step sine table as the original rounds it, for tests that
    don't need the data: round(64 sin) and round(64 cos) of each 5 degrees
    (tools/freescape.py checks the original's is exactly this)."""
    import math
    return {
        "sin": [round(64 * math.sin(math.radians(5 * a))) for a in range(72)],
        "cos": [round(64 * math.cos(math.radians(5 * a))) for a in range(72)],
    }
