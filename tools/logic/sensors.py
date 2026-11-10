"""The guard sensors, transcribed: what the redraw finds of them ($7592, in
the projection $6B7C), their line of sight after the redraw ($9841), the
interrupt's shots ($BB93-$BC94) and a hidden sensor's stop ($B467).

The lists (SensorList, $8A24 on): the count the redraw found ($8A24), the
interrupt's count ($8A25), the redraw's list ($8A26) and the interrupt's
($8A44), five entries of six bytes each: the sensor's id, its interval in
frames (its record's byte $0A), a frame counter, its state (0 off, 1 on the
screen, 2 in range but off it) and its point on the screen, as the
crosshair's (x from 1, y up from the view's bottom).

What's on the screen is the renderer's: the port's is the BBC's view
(tools/logic/view.py), so a sensor is on the screen when the BBC's frame
drew its pixel, and its point is that pixel's (decision 132).
"""
from . import area

FLAGS = 0x8A21      # bit 0: a shot shows; bit 2: the redraw's test runs (no shots)
FOUND_N = 0x8A24
FIRING_N = 0x8A25
FOUND = 0x8A26
FIRING = 0x8A44
ENTRY = 6
ENTRIES = 5
SENSOR = 2          # a sensor's type


def _records(s):
    """The area's records, then the globals', in the projection's order."""
    m = s.mem
    p = s.AreaObjPtr
    for _ in range(s.AreaObjects):
        yield p
        p += m[p + 8]
    p = area.GLOBALS
    for _ in range(m[area.N_GLOBALS]):
        yield p
        p += m[p + 8]


def _s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def _sides(s, rec):
    """$6BAF: the record's box less the camera, each axis's low and high
    face in world units (16-bit), and the six which-side bits: bit 2k the
    camera below axis k's low face, 2k + 1 above its high face."""
    m = s.mem
    cam = (s.PlayerX, s.PlayerY, s.PlayerZ)
    bits = 0
    lows = []
    for k in range(3):
        lo = (m[rec + 1 + k] * 64 - cam[k]) & 0xFFFF
        hi = (lo + m[rec + 4 + k] * 64) & 0xFFFF
        lows.append(lo)
        if lo and not lo & 0x8000:
            bits |= 1 << (2 * k)
        if hi & 0x8000:
            bits |= 1 << (2 * k + 1)
    return bits, lows


def in_range(s, rec):
    """$7592's tests before the projection: shown, the camera on the side its
    axes' mask (byte $0D) asks, and |x| + |y| + |z| (16-bit, as the
    original adds them) short of its range (bytes $0B, $0C)."""
    m = s.mem
    if m[rec] & 0x40:
        return False
    bits, (x, y, z) = _sides(s, rec)
    if not bits & m[rec + 0x0D]:
        return False
    hl = (-z if z & 0x8000 else z) & 0xFFFF
    hl = (hl - x if x & 0x8000 else hl + x) & 0xFFFF
    hl = (hl - y if y & 0x8000 else hl + y) & 0xFFFF
    rng = m[rec + 0x0B] | m[rec + 0x0C] << 8
    return bool((hl - rng) & 0x8000)


def pixel_of(v, obj_id):
    """The BBC's pixel of a sensor's point in the view v (its face's, the
    pixel whose centre the fill takes inside its square), as the
    crosshair's (x from 1, y up), or None if the view didn't draw it."""
    from tools.model.view import SUB, VIEW_H
    for f in v.faces:
        if f.id == obj_id:
            px = (min(p[0] for p in f.poly) + SUB // 2 - 1) // SUB
            py = (min(p[1] for p in f.poly) + SUB // 2 - 1) // SUB
            return 2 * px + 1, VIEW_H - py
    return None


FOUND_END = 0x8A62  # the projection's place for its next entry
FOUND_ID = 0x8916   # FoundId, which the projection leaves the last object's ($6C0F)


def project(s, view_of):
    """$6B33 and $7592 for each sensor of the area and the globals, as the
    redraw re-projects: the list at $8A26, its count and its end. view_of()
    gives the BBC's view of the state, made only if a sensor needs it. The
    projection leaves FoundId the id of the last object it takes ($6C0F):
    the globals' last, which in Driller is a sensor, taken whatever its
    state."""
    m = s.mem
    m[FOUND_N] = 0
    p = FOUND
    v = None
    last = None
    for rec in _records(s):
        last = rec
        if m[rec] & 0x0F != SENSOR:
            continue
        m[FOUND_N] = (m[FOUND_N] + 1) & 0xFF
        m[p] = m[rec + 7]
        m[p + 1] = m[rec + 0x0A]
        if not in_range(s, rec):
            m[p + 3] = 0
        else:
            if v is None:
                v = view_of()
            at = pixel_of(v, m[rec + 7]) if v is not None else None
            if at is None:
                m[p + 3] = 2
            else:
                m[p + 4], m[p + 5] = at
                m[p + 3] = 1
        p += ENTRY
    m[FOUND_END], m[FOUND_END + 1] = p & 0xFF, p >> 8
    if last is not None and m[last] & 0x0F == SENSOR:
        m[FOUND_ID] = m[last + 7]


def sight(s, shot, hooks=None):
    """$9841, after the redraw: each sensor the redraw found on the screen
    keeps its state if the shot's pick at its point hits it; each in range
    off the screen if a walk from the camera to its corner (Margin 0, as
    the jet) gets there; the rest go off. The walk and the pick leave
    Collided, FoundId and the walk's scratch as they end. Then the
    interrupt's count and list from the redraw's, each entry's counter the
    old list's at its place, or 2 for one that's 0 or 1. shot(s) is the
    pick at the crosshair (tools/logic/view.py's, of the frame drawn)."""
    from . import move   # (move's own imports reach the FCL, which reaches here)
    m = s.mem
    p = FOUND
    for _ in range(m[FOUND_N]):
        st = m[p + 3]
        if st == 1:
            cx, cy = s.CrossX, s.CrossY
            s.Collided = 0
            s.CrossX, s.CrossY = m[p + 4], m[p + 5]
            hit = shot(s)
            if hit is not None:
                s.Collided = hit
            s.CrossX, s.CrossY = cx, cy
            if s.Collided != m[p]:
                m[p + 3] = 0
        elif st == 2:
            s.FoundId = m[p]
            rec = area.lookup(s, 0)
            jet, margin = s.InJet, s.Margin
            s.InJet = 1
            s.Margin = 0
            want = tuple(m[rec + 1 + k] * 64 for k in range(3))
            s.TargetX, s.TargetY, s.TargetZ = want
            move.move(s)
            if (s.TargetX, s.TargetY, s.TargetZ) != want:
                m[p + 3] = 0
            s.Margin = margin
            s.InJet = jet
        p += ENTRY
    m[FIRING_N] = m[FOUND_N]
    for i in range(ENTRIES):
        old = m[FIRING + ENTRY * i + 2]
        m[FOUND + ENTRY * i + 2] = 2 if old in (0, 1) else old
    m[FIRING:FIRING + ENTRY * ENTRIES] = m[FOUND:FOUND + ENTRY * ENTRIES]


def tick(s, hooks):
    """The interrupt's sensors ($BB93-$BC94), a frame: each in the
    interrupt's list counts its frames round its interval; at 0, one that's
    on fires: its lines on the screen (state 1: hooks.sensor_lines, drawn
    by EOR and taken off a frame later), the border in the screen's second
    colour (taken back a frame or two later: hooks.border), sound 2, and a
    unit of Shield, or with none left the game over (1). Nothing while the
    redraw's test runs (bit 2), unless a shot showed (bit 0)."""
    m = s.mem
    f = m[FLAGS]
    if not f & 1 and f & 4:
        return
    m[FLAGS] = f & 0xFE
    p = FIRING
    for _ in range(m[FIRING_N]):
        c = (m[p + 2] + 1) & 0xFF
        m[p + 2] = c
        if c == m[p + 1]:
            m[p + 2] = c = 0
        st = m[p + 3]
        if st:
            if c == 0:
                m[FLAGS] |= 1
                if st == 1:
                    hooks.sensor_lines(s, m[p + 4], m[p + 5])
                hooks.border(s, s.ScreenColours[1])
                _shot(s, hooks)
            elif st == 1:
                if c == 1:
                    hooks.sensor_lines(s, m[p + 4], m[p + 5])
                    hooks.border(s, s.ScreenColours[0])
            elif c == 2:
                hooks.border(s, s.ScreenColours[0])
            elif c == 1:
                m[FLAGS] |= 1
        p += ENTRY


def _shot(s, hooks):
    """$BC6A: sound 2, and a unit of Shield (the panel's with it), or the
    game over (1) with none left."""
    hooks.sound(s, 2)
    if s.Shield:
        s.Shield = s.Shield - 1
        s.PanelShield = s.Shield
    else:
        s.GameOver = 1


def off(s, obj_id):
    """$B467: a hidden sensor (A its id) stops: its entry in the
    interrupt's list (of its count) goes off, and the redraw's at the same
    place."""
    m = s.mem
    p = FIRING
    for _ in range(m[FIRING_N]):
        if m[p] == obj_id:
            m[p + 3] = 0
            m[p - 0x1B] = 0         # (IY - $1B: the redraw's entry's state)
            return
        p += ENTRY


def inside(s, frame, hooks=None):
    """$9841 inside a pass, after the redraw there and then ($6B12: a rig's,
    $C286, and the FCL's REDRAW, $B6D4): the projection if that redraw
    re-projects (GameFlags bit 2), then the line of sight, always. frame is
    (view_of, shot) of the renderer's frame (tools/logic/view.py's frame):
    the hooks' redraw gives it (the check's, the state as it stands; the
    disc's, the frame the pass began with: decision 192). The screen's
    colours if the area changed ($9841's end, $A77A) are the caller's."""
    view_of, shot = frame
    if s.GameFlags & 0x04:
        project(s, view_of)
    sight(s, shot, hooks)


def redraw(s, shot, view_of, hooks=None):
    """What the original's redraw does to the sensors after a pass ($9807):
    the projection's list if it re-projects (GameFlags bit 2), and the line
    of sight if it redraws at all (or GameFlags2 bit 3)."""
    if s.GameFlags & 0x04:
        project(s, view_of)
    if s.GameFlags & 0x04 or s.GameFlags2 & 0x08:
        sight(s, shot, hooks)
        return True
    return False


def any_sensors(s):
    """Whether the area or the globals have a sensor."""
    return any(s.mem[r] & 0x0F == SENSOR for r in _records(s))
