"""Moving, turning and colliding, transcribed: $A279 (the movement actions),
$A364 (a step), $9F42 (the move: a walk through the cells), $9DCF (one
crossing: the step up and the fall), $A597 (which object a crossing
enters) and $BCCB (keeping clear of faces).

docs/research/zx-logic.md, "Moving", describes the rules. Every 8-bit
compare here keeps the original's sign-flag test (`minus`), and every
16-bit sum wraps, as the Z80's do.
"""
from .arith import mul_a_hl, shift6, mul_hl_de, div32, minus, neg8
from .fcl import wait

SINCOS = 0x8E78         # 72 (sin, cos) pairs, signed bytes, 1.0 = 64
OBJECTS_GLOBAL = 0x87A5
N_GLOBALS = 0x890F
REMEMBERED = 0xA596     # $A597's last solid hit
STORE_COLLIDED = 0x8A69  # where a hit's id goes: Collided
STORE_CEILING = 0x9DCA   # the step-up's test above: a dummy
STORE_MARGIN = 0xBCCA    # $BCCB's test once Collided is set: a dummy
SCRATCH = 0x9F33         # $9F33-$9F41: the target cells, crossing, delta

# Decision 18: the port fixes the original's corner bug, where the rule
# that moves the axes across together moves an axis already at its target
# cell (docs/research/zx-logic.md, "The original's bugs"). Off, this is
# the original, which make logic checks; on, it's the port's logic, which
# the 6502 is checked against (tools/logictrace.py).
FIX_CORNER = False


class Freeze(Exception):
    """The original's move never finishes: its walk has come to a crossing
    on no axis ($A107 with no y to cross), which changes nothing, so it
    comes to the same crossing again for ever. The game hangs."""


# Crossing bits, for C in $9F42, $9DCF and $A597: bit 1 x changes, bit 0
# x increases; bits 3, 2 y; bits 5, 4 z.
X_MOVES, X_UP, Y_MOVES, Y_UP, Z_MOVES, Z_UP = 2, 1, 8, 4, 0x20, 0x10


def cell(v):
    """ADD HL,HL : ADD HL,HL : LD A,H: a position's cell, 8 bits."""
    return (v >> 6) & 0xFF


def sin_cos(s, angle):
    m = s.mem
    a = SINCOS + 2 * angle
    return m[a], m[a + 1]


# --- $A597: which object a crossing enters ---------------------------------

def _face(cur, o, od, up):
    """The crossing's face is the object's: going up, the next cell is its
    first; going down, this cell is the one past its last."""
    if up:
        return (cur + 1) & 0xFF == o
    return (o + od) & 0xFF == cur


def _within(cur, o, od):
    """cur is in [o, o + od) as the original tests it: JP M on cur - o,
    then JR Z and JP P on (o + od) - cur."""
    if minus(cur, o):
        return False
    end = (o + od) & 0xFF
    return end != cur and not minus(end, cur)


def _hits(m, iy, c, cx, cy, cz):
    ox, oy, oz = m[iy + 1], m[iy + 2], m[iy + 3]
    dx, dy, dz = m[iy + 4], m[iy + 5], m[iy + 6]
    # Through an x face ($A5CE), then a y face ($A64E), then a z face ($A6CE):
    # the object must overlap the other two axes, or be entered across them
    # at the same time.
    if c & X_MOVES and _face(cx, ox, dx, c & X_UP):
        if _within(cy, oy, dy) or (c & Y_MOVES and _face(cy, oy, dy, c & Y_UP)):
            if _within(cz, oz, dz) or (c & Z_MOVES and _face(cz, oz, dz, c & Z_UP)):
                return True
    if c & Y_MOVES and _face(cy, oy, dy, c & Y_UP):
        if _within(cx, ox, dx):
            x_ok = True
        else:
            # $A682: the register holds cx if cx < ox (JP M), and ox + dx
            # otherwise; the x-increasing test adds one to it, not to cx.
            reg = cx if minus(cx, ox) else (ox + dx) & 0xFF
            if c & X_MOVES:
                if c & X_UP:
                    x_ok = (reg + 1) & 0xFF == ox
                else:
                    x_ok = (ox + dx) & 0xFF == cx
            else:
                x_ok = False
        if x_ok and (_within(cz, oz, dz) or (c & Z_MOVES and _face(cz, oz, dz, c & Z_UP))):
            return True
    if c & Z_MOVES and _face(cz, oz, dz, c & Z_UP):
        if _within(cx, ox, dx) or (c & X_MOVES and _face(cx, ox, dx, c & X_UP)):
            if _within(cy, oy, dy) or (c & Y_MOVES and _face(cy, oy, dy, c & Y_UP)):
                return True
    return False


def _scan(s, iy, n, c, store):
    """$A5C7: n objects from iy. A rectangle (type 3) or a line or polygon
    (10-15) hit returns at once; any other type's hit is remembered and the
    scan goes on. Returns 1 for the immediate return, else None."""
    m = s.mem
    cx, cy, cz = s.CellX, s.CellY, s.CellZ
    for _ in range(n if n else 256):
        t = m[iy]
        if not t & 0x40 and _hits(m, iy, c, cx, cy, cz):
            e = m[iy + 7]
            kind = t & 0x0F
            if kind == 3 or not minus(kind, 0x0A):
                m[store] = e
                return 1
            m[REMEMBERED] = e
        iy = (iy + m[iy + 8]) & 0xFFFF
    return None


def touch(s, c, store=STORE_COLLIDED):
    """$A597: does crossing c from the current cell (CellX, CellY, CellZ)
    enter a visible object: the area's, then the globals? A hit's id goes
    to store. Returns 1 or 0."""
    m = s.mem
    m[REMEMBERED] = 0
    if s.AreaObjects:
        if _scan(s, s.AreaObjPtr, s.AreaObjects, c, store):
            return 1
    if _scan(s, OBJECTS_GLOBAL, m[N_GLOBALS], c, store):
        return 1
    if m[REMEMBERED]:
        m[store] = m[REMEMBERED]
        return 1
    return 0


# --- $BCCB: keeping clear of faces -----------------------------------------

def keep_clear(s):
    """$BCCB: if the target is within Margin of its cell's edge on any
    axis, and crossing those edges (all at once) enters an object, move it
    back to Margin from each of those edges. The first such object's id
    goes to Collided."""
    m = s.mem
    h = s.Margin
    low = (0x40 - h) & 0xFF
    c = 0
    for addr, moves, up in ((0x88AF, X_MOVES, X_UP), (0x88B1, Y_MOVES, Y_UP), (0x88B3, Z_MOVES, Z_UP)):
        a = m[addr] & 0x3F
        if minus(a, h):
            c |= moves
        elif not minus(a, low):
            c |= moves | up
    store = STORE_MARGIN if s.Collided else STORE_COLLIDED
    if not c or not touch(s, c, store):
        return
    for addr, moves, up in ((0x88AF, X_MOVES, X_UP), (0x88B1, Y_MOVES, Y_UP), (0x88B3, Z_MOVES, Z_UP)):
        if c & moves:
            m[addr] = ((m[addr] & 0xC0) + (low if c & up else h)) & 0xFF


# --- $9DCF: one crossing ---------------------------------------------------

def cross(s, c):
    """$9DCF: cross into the next cell (the bits of c), if nothing's there.

    In the jet, an object stops it (1). On the probe, an object it can
    climb (a clear column of BodyHeight cells starting at most
    ClimbLimitScaled cells up) lifts the target that far (2), else it
    stops (1); and once across, the probe falls to whatever is below,
    lowering the target (2), dying if it fell more than FallLimitScaled
    cells. Returns 0 when it crossed on the level."""
    m = s.mem
    e = touch(s, c, STORE_COLLIDED)
    if s.InJet:
        if e:
            s.Blocked = 1
            return 1
        b = 0
    else:
        b = None
        if e:
            hh, ll = 0, 1
        else:
            hh = 1
            if s.BodyHeight == hh:
                b = 0
            ll = 0
        if b is None:
            d = 1
            s.SavedCellY = s.CellY
            while True:
                if s.BodyHeight == hh:
                    break
                if minus(s.ClimbLimitScaled, ll):
                    return _blocked(s)
                d = (d + 1) & 0xFF
                if (s.CellY + 1) & 0xFF == m[0x88E1]:
                    return _blocked(s)
                if touch(s, Y_MOVES | Y_UP, STORE_CEILING):
                    return _blocked(s)
                s.CellY = s.CellY + 1
                if touch(s, c, STORE_COLLIDED):
                    hh, ll = 0, d
                else:
                    hh = (hh + 1) & 0xFF
            d = neg8(s.BodyHeight - d)
            s.CellY = s.SavedCellY + d
            b = 0
            if d:
                s.TargetY = s.TargetY + (d << 6)
                b = 2
                s.Sound = 4
    # $9E8B: across.
    if c & X_MOVES:
        s.CellX = s.CellX + (1 if c & X_UP else -1)
    if c & Z_MOVES:
        s.CellZ = s.CellZ + (1 if c & Z_UP else -1)
    if s.InJet:
        if c & Y_MOVES:
            s.CellY = s.CellY + (1 if c & Y_UP else -1)
        return 0
    # $9ECA: the fall.
    if m[0x88E2] == s.CellY:
        return b
    d = 0
    while True:
        if touch(s, Y_MOVES, STORE_COLLIDED):
            break
        d = (d + 1) & 0xFF
        s.CellY = s.CellY - 1
        if m[0x88E2] == s.CellY:
            break
    if d == 0:
        return b
    s.Sound = 3
    s.TargetY = s.TargetY - (d << 6)
    if not minus(s.FallLimitScaled, d):
        return 2
    s.Roll = 0x12
    s.Pitch = 0
    s.GameOver = 4
    return 2


def _blocked(s):
    """$9E51: the step-up failed."""
    s.CellY = s.SavedCellY
    s.Blocked = 1
    return 1


# --- $9F42: the move -------------------------------------------------------

def _crossing(s, base, cur, up, delta_main, deltas, starts):
    """The point where the walk crosses its next boundary on one axis:
    that boundary in full, and the other two axes at it,
    start + (boundary - here) * delta / delta_main ($9179 then $92D7)."""
    a = (cur + 1) & 0xFF if up else cur
    bound = (a << 6) & 0xFFFF
    t = (bound - base) & 0xFFFF
    out = []
    for d, start in zip(deltas, starts):
        q, _ = div32(mul_hl_de(t, d), delta_main)
        out.append((start + q) & 0xFFFF)
    return bound, out


def _boundary_with(c, bits_moves, bits_up, cur, v):
    """At a crossing, does the other axis (cur, crossing coordinate v) stay
    in its cell (0), cross at the same point (1), or cross first (2)?
    ($A026-$A04F and its copies.)"""
    e = v & 0xFF
    h = cell(v)
    if c & bits_up:
        a = (cur - h) & 0xFF
        if a == 0:
            return 0
        if a != 0xFF or e & 0x3F:
            return 2
        return 1
    if cur != h:
        return 2
    if e & 0x3F:
        return 0
    return 1


def move(s):
    """$9F42: move the camera toward (TargetX, TargetY, TargetZ), a cell
    boundary at a time, nearest crossing first; stop at the area's extent
    or where $9DCF says. Then keep clear of faces ($BCCB) at each of the
    body's cells, and take the target as the camera. Returns 1 if the
    camera moved.

    With Margin 0 (the sensors' test after the redraw) it only walks: the
    target is left where it stopped, and the camera doesn't move."""
    m = s.mem
    c = 0
    s.CellX = cell(s.PlayerX)
    tx = cell(s.TargetX)
    m[SCRATCH] = tx
    if tx != s.CellX:
        c |= X_MOVES
        if not minus(tx, s.CellX):
            c |= X_UP
    s.CellY = cell(s.PlayerY)
    ty = cell(s.TargetY)
    m[SCRATCH + 1] = ty
    if ty != s.CellY:
        c |= Y_MOVES
        if not minus(ty, s.CellY):
            c |= Y_UP
    s.CellZ = cell(s.PlayerZ)
    tz = cell(s.TargetZ)
    m[SCRATCH + 2] = tz
    if tz != s.CellZ:
        c |= Z_MOVES
        if not minus(tz, s.CellZ):
            c |= Z_UP
    if c:
        dx = (s.TargetX - s.PlayerX) & 0xFFFF
        dy = (s.TargetY - s.PlayerY) & 0xFFFF
        dz = (s.TargetZ - s.PlayerZ) & 0xFFFF
        _put16(m, SCRATCH + 9, dx)
        _put16(m, SCRATCH + 11, dy)
        _put16(m, SCRATCH + 13, dz)
        stop = None
        while True:
            b, bx, by, bz = _next_crossing(s, c, dx, dy, dz)
            _put16(m, SCRATCH + 3, bx)
            _put16(m, SCRATCH + 5, by)
            _put16(m, SCRATCH + 7, bz)
            # $A158: the area's extent.
            if _at_extent(s, b):
                stop = 1
                break
            was = (s.CellX, s.CellY, s.CellZ, s.TargetY)
            r = cross(s, b)
            if r == 1 or r == 2:
                stop = r
                break
            if b == 0 and (s.CellX, s.CellY, s.CellZ, s.TargetY) == was:
                raise Freeze(f"$9F42 at cells {was[:3]} toward {tuple(m[SCRATCH:SCRATCH + 3])}")
            if (m[SCRATCH] == s.CellX and m[SCRATCH + 2] == s.CellZ
                    and m[SCRATCH + 1] == s.CellY):
                break
        if stop is not None:
            margin = s.Margin
            if stop == 1:
                s.TargetY = _pull_back(margin, by, s.CellY)
            s.TargetX = _pull_back(margin, bx, s.CellX)
            s.TargetZ = _pull_back(margin, bz, s.CellZ)
    # $A220
    if not s.Margin:
        return 0
    keep_clear(s)
    if not s.InJet:
        for _ in range((s.BodyHeight - 1) & 0xFF):
            s.CellY = s.CellY + 1
            keep_clear(s)
    moved = 0
    if s.TargetX != s.PlayerX:
        s.PlayerX = s.TargetX
        moved = 1
    if s.TargetY != s.PlayerY:
        s.PlayerY = s.TargetY
        moved = 1
    if s.TargetZ != s.PlayerZ:
        s.PlayerZ = s.TargetZ
        moved = 1
    return moved


def _put16(m, a, v):
    m[a], m[a + 1] = v & 0xFF, (v >> 8) & 0xFF


def _pull_back(margin, v, cur):
    """$A1D8-$A21D: where it stopped, a unit back into the current cell
    when the crossing point is in the next one (only with Margin)."""
    if margin and cell(v) != cur:
        return (v - 1) & 0xFFFF
    return v


def _at_extent(s, b):
    """$A158: would this crossing leave the area's extent ($88DF-$88E4)?
    x, then z, then y."""
    m = s.mem
    for moves, up, cur, hi, lo in ((X_MOVES, X_UP, s.CellX, 0x88DF, 0x88E0),
                                  (Z_MOVES, Z_UP, s.CellZ, 0x88E3, 0x88E4),
                                  (Y_MOVES, Y_UP, s.CellY, 0x88E1, 0x88E2)):
        if b & moves:
            if b & up:
                if m[hi] == (cur + 1) & 0xFF:
                    return True
            elif m[lo] == cur:
                return True
    return False


def _arrived(s, axis):
    """With FIX_CORNER (decision 18): is this axis (0 x, 1 y, 2 z) already
    in its target cell, so that it mustn't cross with another?"""
    if not FIX_CORNER:
        return False
    return s.mem[SCRATCH + axis] == (s.CellX, s.CellY, s.CellZ)[axis]


def _next_crossing(s, c, dx, dy, dz):
    """$9FCA-$A157: the next boundary the walk crosses, and the axes that
    cross there (b, as c's bits) and the point (bx, by, bz)."""
    m = s.mem
    x, y, z = s.PlayerX, s.PlayerY, s.PlayerZ
    # x first, if x has a crossing left.
    if c & (X_MOVES | X_UP) and m[SCRATCH] != s.CellX:
        b = c & 3
        bx, (by, bz) = _crossing(s, x, s.CellX, c & X_UP, dx, (dy, dz), (y, z))
        first = True
        if c & Z_MOVES:
            w = _boundary_with(c, Z_MOVES, Z_UP, s.CellZ, bz)
            if w == 2:
                first = False
            elif w == 1 and not _arrived(s, 2):
                b |= c & 0x30
        if first and c & Y_MOVES:
            w = _boundary_with(c, Y_MOVES, Y_UP, s.CellY, by)
            if w == 2:
                first = False
            elif w == 1 and not _arrived(s, 1):
                b |= c & 0x0C
        if first:
            return b, bx, by, bz
    # $A07E: z, if z has a crossing left.
    if c & (Z_MOVES | Z_UP) and m[SCRATCH + 2] != s.CellZ:
        b = c & 0x30
        bz, (bx, by) = _crossing(s, z, s.CellZ, c & Z_UP, dz, (dx, dy), (x, y))
        first = True
        if c & Y_MOVES:
            w = _boundary_with(c, Y_MOVES, Y_UP, s.CellY, by)
            if w == 2:
                first = False
            elif w == 1 and not _arrived(s, 1):
                b |= c & 0x0C
        if first:
            return b, bx, by, bz
    # $A107: y.
    b = c & 0x0C
    by, (bx, bz) = _crossing(s, y, s.CellY, c & Y_UP, dy, (dx, dz), (x, z))
    return b, bx, by, bz


# --- $A364: a step ----------------------------------------------------------

def _negate_if_back(v, forward):
    return v if forward else -v & 0xFFFF


def step(s, forward):
    """$A364: a step forward (action 3) or back (4) of StepUnits along the
    yaw, floor(step * sin / 64) in x and floor(step * cos / 64) in z, each
    negated after the floor for a step back. In the jet the step first
    splits by the pitch. On the probe the move is made from the feet,
    BodyHeight - 1 cells below the eye. Returns the flags (B, C)."""
    if s.KeyCount == 1:
        s.Wipe = 1
    hl = s.StepUnits
    if s.InJet:
        sp, cp = sin_cos(s, s.Pitch)
        dy = shift6(mul_a_hl(neg8(sp), hl))
        s.TargetY = s.PlayerY + _negate_if_back(dy, forward)
        hl = shift6(mul_a_hl(neg8(cp) if cp & 0x80 else cp, s.StepUnits))
    sy, cy = sin_cos(s, s.Yaw)
    dz = shift6(mul_a_hl(cy, hl))
    s.TargetZ = s.PlayerZ + _negate_if_back(dz, forward)
    dx = shift6(mul_a_hl(sy, hl))
    s.TargetX = s.PlayerX + _negate_if_back(dx, forward)
    feet = 0
    if not s.InJet:
        feet = ((s.BodyHeight - 1) & 0xFF) << 6
        s.PlayerY = s.PlayerY - feet
        s.TargetY = s.PlayerY
    bc = 0x0014 if move(s) else 0
    if not s.InJet:
        s.PlayerY = s.PlayerY + feet
    return bc


# --- $A279: the movement actions -------------------------------------------

def _rise(s):
    """Action 1 (R): in the jet, up StepUnits; on the probe, up a level if
    the head's cells above are clear."""
    s.TargetX, s.TargetZ = s.PlayerX, s.PlayerZ
    if s.InJet:
        s.TargetY = s.PlayerY + s.StepUnits
        return 0x0014 if move(s) else 0
    if not minus(s.ExtLevel, s.ExtMax):
        return 0
    y = s.PlayerY
    hl = y
    for _ in range(s.AreaScale if s.AreaScale else 256):
        hl = (hl + 0x40) & 0xFFFF
    s.TargetY = hl
    s.InJet = 1
    move(s)
    s.InJet = 0
    if hl == s.TargetY:
        s.ExtLevel = s.ExtLevel + 1
        s.BodyHeight = s.BodyHeight + s.AreaScale
        return 0x8014
    s.PlayerY = y
    return 0


def _fall(s):
    """Action 2 (F): in the jet, down StepUnits; on the probe, down a
    level, without a test."""
    if s.InJet:
        s.TargetX, s.TargetZ = s.PlayerX, s.PlayerZ
        s.TargetY = s.PlayerY - s.StepUnits
        return 0x0014 if move(s) else 0
    if s.ExtLevel == 1:
        return 0
    s.ExtLevel = s.ExtLevel - 1
    a, hl = s.BodyHeight, s.PlayerY
    for _ in range(s.AreaScale if s.AreaScale else 256):
        a = (a - 1) & 0xFF
        hl = (hl - 0x40) & 0xFFFF
    s.BodyHeight = a
    s.PlayerY = hl
    return 0x8014


def _turn(s, name, add):
    """$A4B4 (add) and $A4C5 (subtract): an angle by Turn, mod 72."""
    a = getattr(s, name)
    if add:
        a = (a + s.Turn) & 0xFF
        if not minus(a, 0x48):
            a = (a - 0x48) & 0xFF
    else:
        a = (a - s.Turn) & 0xFF
        if a & 0x80:
            a = (a + 0x48) & 0xFF
    setattr(s, name, a)


def movement(s, action, hooks):
    """$A279: actions 1-$14. Returns nothing; sets EventsDue and ORs the
    flags into GameFlags (C) and GameFlags2 (B) as the original does."""
    events = True
    bc = 0
    if action == 1:
        bc = _rise(s)
    elif action == 2:
        bc = _fall(s)
    elif action in (3, 4):
        bc = step(s, action == 3)
    elif action == 5:
        _turn(s, "Yaw", False)
        bc = 0x24
    elif action == 6:
        _turn(s, "Yaw", True)
        bc = 0x24
    elif action == 7:
        _turn(s, "Pitch", False)
        bc = 0x44
    elif action == 8:
        _turn(s, "Pitch", True)
        bc = 0x44
    elif action == 9:
        _turn(s, "Roll", True)
        bc = 0x04
    elif action == 0x0A:
        _turn(s, "Roll", False)
        bc = 0x04
    elif action == 0x0D:
        bc = 0x24
        a = (s.Yaw + 0x24) & 0xFF
        if not minus(a, 0x48):
            a = (a - 0x48) & 0xFF
        s.Yaw = a
        if s.InJet and s.Pitch:
            s.Pitch = neg8(s.Pitch - 0x48)
            bc = 0x64
    else:
        events = False
        m = s.mem
        if action in (0x0B, 0x0C):
            i = s.TurnIndex
            if action == 0x0B and i != (m[0x88C9] - 1) & 0xFF:
                i += 1
            elif action == 0x0C and i != 0:
                i -= 1
            else:
                i = None
            if i is not None:
                s.TurnIndex = i
                s.Turn = m[0x88CA + (i & 0xFF)]
                bc = 0x0080
                wait(s, hooks, 7)
        elif action in (0x11, 0x12):
            i = s.StepIndex
            if action == 0x11 and i != (m[0x88BE] - 1) & 0xFF:
                i += 1
            elif action == 0x12 and i != 0:
                i -= 1
            else:
                i = None
            if i is not None:
                s.StepIndex = i
                s.Step = m[0x88BF + (i & 0xFF)]
                s.StepUnits = mul_a_hl(s.AreaScale, s.Step)
                bc = 0x0100
                wait(s, hooks, 7)
    if events:
        s.EventsDue = 1
    s.GameFlags = s.GameFlags | (bc & 0xFF)
    s.GameFlags2 = s.GameFlags2 | (bc >> 8)
