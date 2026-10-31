"""The camera (docs/engine.md, section 4, stage 0).

Position in world units (16-bit unsigned; an object's cell coordinate times
CELL is its world position), the eye itself; and the three angles in the
original's 5 degree steps, 0-71. Yaw 0 looks along +z and yaw 18 along +x;
pitch is positive looking down; roll is positive rolling the camera left,
so the scene turns clockwise on the screen (docs/research/model.md, "The
camera").
"""
from dataclasses import dataclass

from tools.model.view import CELL

STEPS = 72

# The probe's vertical extension, 1-4, the game starts at (the original's
# L, docs/research/zx-driller.md).
START_LEVEL = 2


@dataclass(frozen=True)
class Camera:
    x: int
    y: int
    z: int
    yaw: int = 0
    pitch: int = 0
    roll: int = 0

    def __post_init__(self):
        for v in (self.x, self.y, self.z):
            if not 0 <= v < 0x10000:
                raise ValueError("camera position %r outside 16 bits" % (v,))
        for a in (self.yaw, self.pitch, self.roll):
            if not 0 <= a < STEPS:
                raise ValueError("camera angle %r outside 0-71" % (a,))

    @property
    def position(self):
        return (self.x, self.y, self.z)


def eye_height(scale, level=START_LEVEL):
    """The eye above the floor of the cell the camera stands on, in world
    units: level times the area's scale, in cells, less half a cell."""
    return CELL * level * scale - CELL // 2


def from_entrance(area, entrance, level=START_LEVEL):
    """Where an entrance puts the camera, as the original's placement does
    on the probe: the middle of its cell across (x and z), the eye
    eye_height above the cell's floor, facing the entrance's angles (its
    three size bytes: pitch, yaw, roll)."""
    ex, ey, ez = entrance["pos"]
    pitch, yaw, roll = entrance["rotation"]
    return Camera(
        x=CELL * ex + CELL // 2,
        y=CELL * ey + eye_height(area["scale"], level),
        z=CELL * ez + CELL // 2,
        yaw=yaw % STEPS, pitch=pitch % STEPS, roll=roll % STEPS,
    )


def entrance_views(db):
    """Every entrance in the database, as (area, entrance, camera), in the
    database's order."""
    for area in db["areas"]:
        for o in area["objects"]:
            if o["type"] == 0:
                yield area, o, from_entrance(area, o)
