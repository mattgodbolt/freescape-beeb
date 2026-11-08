"""The drilling rigs, transcribed: $BEFA, D drills (action $28) and C
collects (action $2A), with $C259 and $C29A, the messages and the redraw
they show (docs/research/zx-logic.md, "The rigs").

Each of areas 1-18 has a byte in RigPlaced ($877B: 0 none, 1 a rig that
found no gas, 2 one that found some, 3 one that found half or more, which
counts in FclVar32), its percentage in RigState ($878D) and where the rig
stands in RigPositions ($882C, three cells). The rig's five global parts
are shown there as the area loads, and as a rig is placed or collected
($CD3B: tools/logic/area.py's place_rigs).

The gas: each area's header bytes 10-12 (AreaGas) are the gas's cell x and
z and its reach. A rig's centre at a distance d (the cells' |dx| + |dz|)
finds 100 - 100 d / reach percent of it; a table of sixteen rotations of
eighteen figures ($88EB, one picked by the clock's frames the first time a
rig is placed: GasTable) gives each area's yield, in thousands of cubic
feet, so a rig scores yield times percentage times ten.
"""
from .arith import minus, mul_a_hl, mul_h_l
from .area import place_rigs, word
from . import fcl

AREA_NEUTRAL = 0x8C12        # the messages, 14 characters each
RIG_POSITIONED = 0x8C20
POS_UNSUITABLE = 0x8C2E
CFT = 0x8C3C                 # "  00000 CFT   ": the yield's two digits at $8C3E
SUCCESS = 0x8C4A             # " 000% SUCCESS ": the percentage's three at $8C4B
ENERGY_TOO_LOW = 0x8C58
NOT_IN_PROBE = 0x8C66
NO_GAS_FOUND = 0x8C74
RIG_COLLECTED = 0x8C82
PROCESSING = 0x8C90
ALREADY_PLACED = 0x8C9E
NO_RIG_PLACED = 0x8CAC
MESSAGE_LEN = 14

DRILL, COLLECT = 0x28, 0x2A
RIG_COST = 5                 # energy, to drill or collect
RIG_W = 12                   # the rig's footprint, cells across x and z ...
RIG_H = 0x16                 # ... and its height less one, for the clear test
GAS_TABLE = 0x88EB           # sixteen rotations of the eighteen yields
SCRIPT = 0xBEF6              # the score's FCL instruction, made here: 01 lo mid hi
SHOWN = 50                   # frames each message shows ($C29A), and the redraw's


def _number(m, at, v, digits):
    """$9390: v's low digits, leading zeros, as ASCII at at."""
    for i in reversed(range(digits)):
        m[at + i] = 0x30 + v % 10
        v //= 10


def div_a_hl_de(n, de):
    """$91F1: A,HL / DE, signed, on the magnitudes, truncated: the quotient's
    24 bits (as the rig uses it, A and D 0 and E the gas's reach). A divisor
    of 0 gives all ones, as the restoring loop does."""
    n &= 0xFFFFFF
    de &= 0xFFFF
    if n == 0:
        return 0
    neg = False
    if de & 0x8000:
        de = -de & 0xFFFF
        neg = True
    if n & 0x800000:
        n = -n & 0xFFFFFF
        neg = not neg
    if de == 0:
        bits = n.bit_length()
        q = (1 << bits) - 1
    else:
        q = n // de
    if neg:
        q = -q & 0xFFFFFF
    return q


def _message(s, hooks, addr):
    """$C29A's: the message shown, highlighted, for SHOWN frames."""
    hooks.message(s, addr)
    fcl.wait(s, hooks, SHOWN)


def _redraw(s, hooks):
    """$C259: the rig's parts placed ($CD3B), then $C266: PROCESSING shown and
    the view redrawn there and then with sound 5 after the copy ($6B12,
    $9841, $B72B: the renderer's), the copy wiping, for SHOWN frames from
    before the redraw. Returns the redraw flags as they were, which the end
    ($C245) puts back."""
    place_rigs(s)
    saved = s.GameFlags, s.GameFlags2
    s.GameFlags, s.GameFlags2 = 0x04, 0x04
    hooks.message(s, PROCESSING)
    s.Countdown = SHOWN
    s.Sound = 5
    wipe = s.Wipe
    s.Wipe = 1
    hooks.redraw(s)
    s.Wipe = wipe
    hooks.wait(s, SHOWN)
    s.Countdown = 0
    return saved


def _end(s, saved):
    """$C245: the flags as they were before the redraw, and the panel's
    message (GameFlags2 bit 5)."""
    s.GameFlags = saved[0]
    s.GameFlags2 = saved[1] | 0x20


def _refuse(s, hooks, addr):
    """$C0EB: the message why not, and the panel's message after it."""
    _message(s, hooks, addr)
    s.GameFlags2 = s.GameFlags2 | 0x20


def rig(s, action, hooks):
    """$BEFA: action DRILL or COLLECT, alone in the pass's keys."""
    m = s.mem
    if s.KeyCount != 1:
        return
    s.EventsDue = 1
    area = s.AreaId
    if not minus(area, 0x13):
        return _refuse(s, hooks, AREA_NEUTRAL)
    c = (area - 1) & 0xFF
    placed = m[0x877B + c]
    if action == DRILL:
        if placed:
            return _refuse(s, hooks, ALREADY_PLACED)
    elif not placed:
        return _refuse(s, hooks, NO_RIG_PLACED)
    if s.InJet:
        return _refuse(s, hooks, NOT_IN_PROBE)
    if minus(s.Energy, RIG_COST):
        return _refuse(s, hooks, ENERGY_TOO_LOW)
    if action == COLLECT:
        return _collect(s, c, hooks)
    return _drill(s, c, hooks)


def _collect(s, c, hooks):
    """$BF56: the rig's score taken back, its energy spent, and the rig gone."""
    m = s.mem
    pct = m[0x878D + c]
    m[0x878D + c] = 0
    yld = m[(word(m, 0x87A3) + c) & 0xFFFF]
    _score(s, mul_a_hl(0xF6, mul_h_l(pct, yld)), hooks)
    s.Energy = s.Energy - RIG_COST
    was = m[0x877B + c]
    m[0x877B + c] = 0
    if was == 3:
        s.FclVar32 = s.FclVar32 - 1
    saved = _redraw(s, hooks)
    _message(s, hooks, RIG_COLLECTED)
    _end(s, saved)


def _score(s, v, hooks):
    """The score's change by the FCL's ADDSCORE, made at SCRIPT and run."""
    m = s.mem
    m[SCRIPT:SCRIPT + 4] = bytes((1, v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF))
    fcl.run(s, SCRIPT, 4, hooks)


# The rig's corner from the probe's cell, by the yaw ($BFAA): it goes in
# front, its 12 cells across centred on the probe's cell or beside it.
def _corner(s):
    b = (s.PlayerX >> 6) & 0xFF
    cz = (s.PlayerZ >> 6) & 0xFF
    yaw = s.Yaw
    if minus(yaw, 0x05):
        b -= 6
    elif minus(yaw, 0x0E):
        pass
    elif minus(yaw, 0x17):
        cz -= 6
    elif minus(yaw, 0x20):
        cz -= 12
    elif minus(yaw, 0x29):
        b -= 6
        cz -= 12
    elif minus(yaw, 0x32):
        b -= 12
        cz -= 12
    elif minus(yaw, 0x3B):
        b -= 12
        cz -= 6
    elif minus(yaw, 0x44):
        b -= 12
    else:
        b -= 6
    return b & 0xFF, cz & 0xFF


def _suitable(s, b, h, cz):
    """$C009-$C0E9: the rig inside the area's extent, standing on the floor
    or on the top of a shown cuboid that holds it, and no shown object in
    its box."""
    m = s.mem
    ext = s.AreaExtent       # x max, x min, y max, y min, z max, z min
    if not minus((ext[1] - 1) & 0xFF, b) or not minus((ext[5] - 1) & 0xFF, cz):
        return False
    if minus((ext[0] - RIG_W) & 0xFF, b) or minus((ext[4] - RIG_W) & 0xFF, cz):
        return False
    n = s.AreaObjects
    if h:
        if n == 0:
            return False
        ix = s.AreaObjPtr
        for _ in range(n):
            if (not m[ix] & 0x40 and m[ix] & 0x0F == 1 and (m[ix + 2] + m[ix + 5]) & 0xFF == h
                    and minus((m[ix + 1] - 6) & 0xFF, b) and not minus((m[ix + 1] - 7 + m[ix + 4]) & 0xFF, b)
                    and minus((m[ix + 3] - 6) & 0xFF, cz) and not minus((m[ix + 3] - 7 + m[ix + 6]) & 0xFF, cz)):
                break
            ix = (ix + m[ix + 8]) & 0xFFFF
        else:
            return False
    if n == 0:
        return True
    ix = s.AreaObjPtr
    for _ in range(n):
        if (not m[ix] & 0x40
                and not minus((m[ix + 1] + m[ix + 4] - 1) & 0xFF, b)
                and not minus((m[ix + 2] + m[ix + 5] - 1) & 0xFF, h)
                and not minus((m[ix + 3] + m[ix + 6] - 1) & 0xFF, cz)
                and not minus((b + 0x0B) & 0xFF, m[ix + 1])
                and not minus((h + RIG_H) & 0xFF, m[ix + 2])
                and not minus((cz + 0x0B) & 0xFF, m[ix + 3])):
            return False
        ix = (ix + m[ix + 8]) & 0xFFFF
    return True


def _drill(s, c, hooks):
    """$BF9E: the rig placed in front of the probe, where it fits, and the
    gas it finds."""
    m = s.mem
    b, cz = _corner(s)
    h = (((s.PlayerY << 2) >> 8) - (s.BodyHeight - 1)) & 0xFF    # the feet's cell
    if not _suitable(s, b, h, cz):
        return _refuse(s, hooks, POS_UNSUITABLE)
    s.Energy = s.Energy - RIG_COST
    p = 0x882C + 3 * c
    m[p], m[p + 1], m[p + 2] = b, h, cz
    b = (b + 6) & 0xFF
    cz = (cz + 6) & 0xFF
    gas = s.AreaGas
    dx = (gas[0] - b) & 0xFF
    if dx & 0x80:
        dx = -dx & 0xFF
    dz = (gas[1] - cz) & 0xFF
    if dz & 0x80:
        dz = -dz & 0xFF
    far = div_a_hl_de(mul_h_l((dx + dz) & 0xFF, 100), gas[2])
    pct = (100 - far) & 0xFFFF
    if pct & 0x8000 or pct == 0:
        return _dry(s, c, hooks)
    pct &= 0xFF
    m[0xBEF4] = pct
    if not m[0x879F]:
        m[0x879F] = 1
        t = GAS_TABLE + (s.SecondFrames & 0x0F)
        m[0x87A3], m[0x87A4] = t & 0xFF, t >> 8
    m[0x878D + c] = pct
    found = 2
    if not minus(pct, 0x32):
        found = 3
        s.FclVar32 = s.FclVar32 + 1
        if s.FclVar32 == 0x12:
            s.GameOver = 5
    m[0x877B + c] = found
    yld = m[(word(m, 0x87A3) + c) & 0xFFFF]
    m[0xBEF5] = yld
    _score(s, mul_a_hl(0x0A, mul_h_l(pct, yld)), hooks)
    _number(m, CFT + 2, yld, 2)
    if m[CFT + 2] == 0x30:
        m[CFT + 2] = 0x20
    _number(m, SUCCESS + 1, pct, 3)
    for i in range(2):
        if m[SUCCESS + 1 + i] != 0x30:
            break
        m[SUCCESS + 1 + i] = 0x20
    saved = _redraw(s, hooks)
    _message(s, hooks, RIG_POSITIONED)
    _message(s, hooks, CFT)
    _message(s, hooks, SUCCESS)
    _end(s, saved)


def _dry(s, c, hooks):
    """$C21D: no gas there: the rig stays, but finds nothing."""
    m = s.mem
    m[0x878D + c] = 0
    m[0xBEF4] = 0
    m[0x877B + c] = 1
    saved = _redraw(s, hooks)
    _message(s, hooks, RIG_POSITIONED)
    _message(s, hooks, NO_GAS_FOUND)
    _end(s, saved)


def message_text(mem, addr):
    return bytes(mem[addr:addr + MESSAGE_LEN]).decode("latin-1")
