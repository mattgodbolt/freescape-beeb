"""Areas, entrances and objects by id, transcribed: $A8BA, $9D1C, $BE18
and $CD3B (docs/research/zx-logic.md, "Areas and entrances").

An object's record: +0 type (low nibble) and flags (bit 5 destroyed, bit 6
invisible), +1-3 its cell x, y, z, +4-6 its size in cells (an entrance's
pitch, yaw and roll), +7 its id, +8 the record's length, then its colours
and vertices, then its FCL from ObjectHeader[type] on.
"""
from .arith import mul_a_hl, mul_h_l

DB = 0xCF3E            # ($8912): the database; its first byte is the area count
AREA_TABLE = 0xD006    # ($8914): the areas' offsets from DB
GLOBALS = 0x87A5       # the eight global objects
N_GLOBALS = 0x890F
OBJECT_HEADER = 0x8929  # the header's length by type: the FCL starts there
# The three globals the area load hides ($BE25), and the rig's five parts.
HIDDEN_ON_LOAD = (0x87FE, 0x880E, 0x881E)
RIG_PARTS = (0x87A5, 0x87C0, 0x87CE, 0x87DE, 0x87EE)
RIG_POSITIONS = 0x882C


def word(m, a):
    return m[a] | m[a + 1] << 8


def find_area(s, area_id):
    """The area table's walk ($BE3B, $A8E3): the record of area area_id,
    or None."""
    m = s.mem
    table = word(m, 0x8914)
    base = word(m, 0x8912)
    n = m[DB]
    for i in range(n if n else 256):
        ix = (base + word(m, table + 2 * i)) & 0xFFFF
        if m[ix + 2] == area_id:
            return ix
    return None


def lookup(s, area_id=0):
    """$A8BA: the object with id FoundId ($8916). area_id 0: the globals,
    then the current area's objects; else that area's objects. Returns
    its record's address, or None (A = 1)."""
    m = s.mem
    want = s.FoundId
    if area_id == 0:
        ix = GLOBALS
        n = m[N_GLOBALS]
        for _ in range(n if n else 256):
            if m[ix + 7] == want:
                return ix
            ix = (ix + m[ix + 8]) & 0xFFFF
        ix, n = s.AreaObjPtr, s.AreaObjects
    else:
        area = find_area(s, area_id)
        if area is None:
            return None
        n = m[area + 1]
        ix = area + 0x19
    if n == 0:
        return None
    for _ in range(n):
        if m[ix + 7] == want:
            return ix
        ix = (ix + m[ix + 8]) & 0xFFFF
    return None


def place_rigs(s):
    """$CD3B: the rig's five global parts, shown at the area's rig if it
    has one (RigPlaced), else hidden."""
    m = s.mem
    m[0x887E] &= ~0x40
    a = s.AreaId
    rig = 0
    if not (a - 0x13) & 0x80:          # CP $13: JP P (areas 19 on: no rig)
        rig = 0
    else:
        m[0x887E] |= 0x40
        c = (a - 1) & 0xFF
        rig = m[0x877B + c]
    if rig == 0:
        for p in RIG_PARTS:
            m[p] |= 0x40
        return
    c = (a - 1) & 0xFF
    p = RIG_POSITIONS + 3 * c
    b, y, z = m[p], m[p + 1], m[p + 2]

    def put(rec, x, yy, zz):
        m[rec] &= ~0x40
        m[rec + 1], m[rec + 2], m[rec + 3] = x & 0xFF, yy & 0xFF, zz & 0xFF

    put(0x87A5, b + 2, y, z + 2)
    y = (y + 0x0A) & 0xFF
    put(0x87C0, b, y, z)
    y = (y + 1) & 0xFF
    put(0x87CE, b + 3, y, z + 3)
    if rig == 1:
        m[0x87DE] |= 0x40
        m[0x87EE] |= 0x40
        return
    y = (y + 8) & 0xFF
    put(0x87DE, b + 5, y, z + 5)
    y = (y + 1) & 0xFF
    put(0x87EE, b + 5, y, z + 5)


def load_area(s):
    """$BE18: enter area AreaId: its objects, conditions, scale and the
    values scaled by it. Nothing happens if there's no such area."""
    m = s.mem
    s.MinuteSeen = 0
    s.MinuteCount = 0
    for a in HIDDEN_ON_LOAD:
        m[a] |= 0x40
    s.AreaChanged = 1
    s.Wipe = 1
    ix = find_area(s, s.AreaId)
    if ix is None:
        return
    s.AreaFlags = m[ix]
    s.AreaObjects = m[ix + 1]
    s.AreaCondPtr = ix + word(m, ix + 3)
    scale = m[ix + 5]
    s.AreaScale = scale
    s.StepUnits = mul_a_hl(scale, s.Step)
    s.FallLimitScaled = mul_h_l(s.FallLimit, scale)
    s.ClimbLimitScaled = mul_h_l(s.ClimbLimit, scale)
    s.BodyHeight = mul_h_l(s.ExtLevel, scale)
    s.ExtMaxScaled = mul_h_l(s.ExtMax, scale)
    s.AreaGas = bytes(m[ix + 10:ix + 13])
    place_rigs(s)
    s.AreaColours = bytes(m[ix + 6:ix + 10])
    s.AreaNamePtr = ix + 13
    s.AreaObjPtr = ix + 25


def go_to_entrance(s):
    """$9D1C: load area AreaId, then put the camera at entrance
    EntranceId: the cell's centre in x and z, the eye BodyHeight - 1 cells
    above the entrance's cell on the probe, the entrance's angles.

    If there's no object with that id (entrance 0 is one), the camera has
    crossed the area's edge: x cell 126 becomes 1 and 0 becomes 125, or
    else z likewise, and nothing else changes."""
    m = s.mem
    load_area(s)
    s.FoundId = s.EntranceId
    ix = lookup(s, 0)
    wrapped = ix is None
    if not wrapped:
        a = m[ix + 1]
    else:
        a = s.CellX
        if a == 0x7E:
            a = 1
        elif a == 0:
            a = 0x7D
        else:
            a = None
    if a is not None:
        s.CellX = a
        s.PlayerX = (a << 6) + 0x20
        if wrapped:
            return
        a = m[ix + 3]
    else:
        a = s.CellZ
        if a == 0x7E:
            a = 1
        elif a == 0:
            a = 0x7D
        else:
            return
    s.CellZ = a
    s.PlayerZ = (a << 6) + 0x20
    if wrapped:
        return
    a = m[ix + 2]
    s.CellY = a
    h = a
    if not s.InJet:
        h = (s.BodyHeight - 1 + a) & 0xFF
    s.PlayerY = ((h << 6) + 0x20) & 0xFFFF
    s.Pitch, s.Yaw, s.Roll = m[ix + 4], m[ix + 5], m[ix + 6]
