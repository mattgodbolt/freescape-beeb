"""What the BBC's renderer draws of the logic's state, for the hooks that
read it back: the model's render (tools/model/render.py) of the logic's
camera, area and objects as their records have them, and the shot's pick
over its faces (tools/model/pick.py).

The original's renderer is its own; the port's pick is the BBC's view's
(decision 131), so the transcription asks the model what the disc's last
frame holds: the frame drawn from the state as the pass begins (the
original's last redraw is from there too).
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.model import camera as cam, pick as mpick, render  # noqa: E402

GLOBALS = 0x87A5
N_GLOBALS = 0x890F
_DB = []


def database():
    """Driller's database as JSON (make data), read once."""
    if not _DB:
        with open(os.path.join(ROOT, "build/data/driller.json")) as f:
            _DB.append(json.load(f))
    return _DB[0]


def flags(s):
    """Each object's first byte, the area's records then the globals', in
    the logic's order (its index's): bit 6 invisible, bit 5 destroyed."""
    m = s.mem
    out = []
    p = s.AreaObjPtr
    for _ in range(s.AreaObjects):
        out.append(m[p])
        p += m[p + 8]
    p = GLOBALS
    for _ in range(m[N_GLOBALS]):
        out.append(m[p])
        p += m[p + 8]
    return out


def global_cells(s):
    """The globals' cells as their records have them (the rig's parts move)."""
    m = s.mem
    out = []
    p = GLOBALS
    for _ in range(m[N_GLOBALS]):
        out.append([m[p + 1], m[p + 2], m[p + 3]])
        p += m[p + 8]
    return out


def camera(s):
    """The logic's camera as the renderer takes it: angles mod 72."""
    return cam.Camera(s.PlayerX, s.PlayerY, s.PlayerZ, s.Yaw % 72, s.Pitch % 72, s.Roll % 72)


def scene(db, area_id, hidden, globals_at):
    """The database and area the model renders, with each object hidden or
    not (the area's records, then the globals') and the globals at their
    cells, as tools/mklive.py's render_cameras takes them; None if no area
    has that id."""
    area = next((a for a in db["areas"] if a["id"] == area_id), None)
    if area is None:
        return None
    objs = area["objects"]
    if len(hidden) != len(objs) + len(db["globals"]):
        raise ValueError(f"area {area_id}: {len(hidden)} objects' flags for {len(objs)} records "
                         f"and {len(db['globals'])} globals")
    area = dict(area, objects=[dict(o, initially_invisible=h) for o, h in zip(objs, hidden)])
    d = dict(db, globals=[dict(o, initially_invisible=h, pos=list(p))
                          for o, h, p in zip(db["globals"], hidden[len(objs):], globals_at)])
    return d, area


def view(s, db=None):
    """The model's render of the logic's state, or None (no such area)."""
    db = db or database()
    sc = scene(db, s.AreaId, [(f & 0x60) != 0 for f in flags(s)], global_cells(s))
    if sc is None:
        return None
    d, area = sc
    # (the faces' colours are no part of the pick: the database's own)
    return render.render(d, area, camera(s), followed=False)


def frame(s):
    """The BBC's frame of the state s as it stands now (the redraw after a
    pass), made when first asked for: (view_of, shot), view_of() the view
    (or None) and shot(t) the pick at t's crosshair in it, for
    tools/logic/sensors.py's redraw."""
    made = []

    def view_of():
        if not made:
            made.append(view(s))
        return made[0]

    def pick_at(t):
        v = view_of()
        if v is None:
            return None
        return mpick.pick(v.faces, *mpick.cross_pixel(t.CrossX, t.CrossY))
    return view_of, pick_at


def shot(s, drawn=None):
    """$B153 at the BBC's view: the id of the object under the crosshair
    (s's, as the shot is fired) in the view of the state drawn (the pass's
    start: the frame last drawn; s by default), or None if nothing is."""
    v = view(drawn or s)
    if v is None:
        return None
    return mpick.pick(v.faces, *mpick.cross_pixel(s.CrossX, s.CrossY))
