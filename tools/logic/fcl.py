"""The events and the FCL, transcribed: $9B6E (the events of a pass) and
$B320 (one FCL script).

Driller's area changes are FCL: walking into a doorway's rectangle, or the
rectangle on the area's edge, runs its collided script, whose GOTO calls
$9D1C. So the interpreter is here whole, with the renderer's, the sound's
and the screen's parts as hooks (tools/logic/hooks.py).

An instruction is an opcode byte (bit 7: it runs only for a shot; clear,
only for a collision or a condition) and operands; its length is the
original's table at $8939. A test that fails ends the script.
"""
from .area import lookup, go_to_entrance, word, OBJECT_HEADER

import collections

LENGTHS = 0x8939
RUN = collections.Counter()   # opcodes run, for the checker's summary


def _show_hide(s, ix, op, hooks):
    """$B424-$B4C9: TOGVIS (3), VIS (4), INVIS (5), DESTROY ($10) on this
    area's object or a global."""
    m = s.mem
    if m[ix] & 0x20:              # destroyed: nothing more
        return
    s.Wipe = 1
    if op == 0x10:
        m[ix] |= 0x20
        show = False
    elif op == 3:
        show = bool(m[ix] & 0x40)
    else:
        show = op == 4
    if show:
        m[ix] &= ~0x40 & 0xFF
        s.GameFlags = s.GameFlags | 0x04
        return
    m[ix] |= 0x40
    if m[ix] & 0x0F == 2 and s.mem[0x8A25]:
        hooks.sensor_off(s, m[ix + 7])
    if s.mem[0x8918] and hooks.undraw(s, s.FoundId):
        s.GameFlags2 = s.GameFlags2 | 0x08


def _bit(s, n):
    """$B595: FCL bit n's byte in FclBits and its mask."""
    a = 0x887B
    v = (n - 1) & 0xFF
    for _ in range(3):
        if (v - 8) & 0x80:
            break
        v = (v - 8) & 0xFF
        a += 1
    mask = 1
    for _ in range(v):
        mask = (mask << 1) & 0xFF
    return a, mask


def _limit(v, game_over, s):
    """ADDENERGY and ADDSHIELD: below 0 ends the game, above $3F is $3F."""
    v &= 0xFF
    if v & 0x80:
        s.GameOver = game_over
        return 0
    if not (v - 0x3F) & 0x80:
        return 0x3F
    return v


def run(s, ix, n, hooks):
    """$B320: run the n bytes of FCL at ix, for a shot if ShotFlag is set,
    else for a collision or a condition."""
    m = s.mem
    c = n & 0xFF
    while True:
        b = m[ix]
        op = b & 0x7F
        s.FclOp = op
        if bool(s.ShotFlag) == bool(b & 0x80):
            RUN[op] += 1
            if _execute(s, ix, op, hooks) is False:
                return
        e = m[LENGTHS + op]
        ix = (ix + e) & 0xFFFF
        c = (c - e) & 0xFF
        if c == 0 or c & 0x80:
            return


def _execute(s, ix, op, hooks):
    """One instruction. Returns False when it ends the script."""
    m = s.mem
    a1, a2 = m[ix + 1], m[ix + 2]
    if op == 1:                           # ADDSCORE: 24 bits, clamped
        lo = s.mem[0x8872] + a1
        mid = s.mem[0x8873] + a2 + (lo >> 8)
        hi = (s.mem[0x8874] + m[ix + 3] + (mid >> 8)) & 0xFF
        lo &= 0xFF
        mid &= 0xFF
        if hi & 0x80:
            if m[ix + 3] & 0x80:
                hi, mid, lo = 0, 0, 0
            else:
                hi, mid, lo = 0x7F, 0xFF, 0xFF
        s.Score = bytes((lo, mid, hi))
        s.GameFlags2 = s.GameFlags2 | 0x02
    elif op == 2:                         # ADDENERGY
        s.Energy = _limit(s.Energy + a1, 3, s)
        s.GameFlags2 = s.GameFlags2 | 0x04
    elif op == 0x13:                      # ADDSHIELD
        s.Shield = _limit(s.Shield + a1, 1, s)
        s.GameFlags2 = s.GameFlags2 | 0x10
    elif op in (3, 4, 5, 0x10, 0x1E, 0x1F):
        s.FoundId = a1
        obj = lookup(s, 0)
        if obj is None:
            return True
        if op == 0x1E:                    # on only if it's shown
            return not m[obj] & 0x40
        if op == 0x1F:                    # on only if it's hidden
            return bool(m[obj] & 0x40)
        _show_hide(s, obj, op, hooks)
    elif op in (6, 7, 8, 0x11, 0x20, 0x21):   # the same, in area a1
        s.FoundId = a2
        obj = lookup(s, a1)
        if obj is None:
            return True
        if op == 0x20:
            return not m[obj] & 0x40
        if op == 0x21:
            return bool(m[obj] & 0x40)
        if m[obj] & 0x20:
            return True
        if op == 0x11:
            m[obj] |= 0x20
            show = False
        elif op == 6:
            show = bool(m[obj] & 0x40)
        else:
            show = op == 7
        if show:
            m[obj] &= ~0x40 & 0xFF
        else:
            m[obj] |= 0x40
    elif op in (9, 0x0A, 0x0B, 0x14):     # the variables
        a = 0x887F + ((a1 - 1) & 0xFF)
        if op == 9:
            m[a] = (m[a] + 1) & 0xFF
        elif op == 0x0A:
            m[a] = (m[a] - 1) & 0xFF
        elif op == 0x14:
            m[a] = a2
        elif a2 != m[a]:
            return False
    elif op in (0x0C, 0x0D, 0x0E, 0x1D):  # the bits
        a, mask = _bit(s, a1)
        v = m[a]
        if op == 0x1D:
            op = 0x0D if v & mask else 0x0C
        if op == 0x0C:
            m[a] = mask | v
        elif op == 0x0D:
            m[a] = ~mask & v & 0xFF
        elif (1 if v & mask else 0) != a2:
            return False
    elif op == 0x0F:                      # SOUND
        hooks.sound(s, a1)
    elif op == 0x1C:                      # SYNCSND: after the copy, if one's due
        if s.GameFlags & 0x04 or s.GameFlags2 & 0x08:
            s.Sound = a1
        else:
            hooks.sound(s, a1)
    elif op == 0x12:                      # GOTO area, entrance
        s.Sound = 0x0A
        s.AreaId = a1
        s.EntranceId = a2
        go_to_entrance(s)
        s.GameFlags = 0xFC
        s.GameFlags2 = 0xFF
    elif op == 0x15:                      # SWAPJET
        _swap_jet(s)
    elif op == 0x19:                      # SPFX: the area's colours
        area_colours = (s.AreaNamePtr - 7) & 0xFFFF
        if a1 & 0xCC:
            s.AreaColours = bytes(m[area_colours:area_colours + 4])
        else:
            m[0x886E + ((a1 & 0x30) >> 4)] = m[area_colours + (a1 & 3)]
        screen_update(s, hooks)
    elif op == 0x1A:                      # REDRAW, there and then
        hooks.redraw(s)
        s.GameFlags = 0
        s.GameFlags2 = 0
    elif op == 0x1B:                      # DELAY
        wait(s, hooks, a1)
    else:
        return False
    return True


def _swap_jet(s):
    """$B635: into the jet or out of it, swapping the energy and shield
    each vehicle keeps."""
    m = s.mem
    if not s.InJet:
        m[0x887E] |= 0x80
        s.InJet = 1
        s.ProbeEnergy = s.Energy
        s.ProbeShield = s.Shield
        s.Energy = s.JetEnergy
        s.Shield = s.JetShield
    else:
        s.InJet = 0
        m[0x887E] &= 0x7F
        s.JetEnergy = s.Energy
        s.JetShield = s.Shield
        s.Energy = s.ProbeEnergy
        s.Shield = s.ProbeShield
    s.GameFlags2 = s.GameFlags2 | 0x94
    s.GameFlags = s.GameFlags | 0x08


def screen_update(s, hooks):
    """$A77A: the screen takes the area's colours, the five sensors' flash
    counters ($8A46, 6 bytes apart) restart at 2, and AreaChanged is done."""
    s.AreaChanged = 0
    s.ScreenColours = s.AreaColours
    for i in range(5):
        s.mem[0x8A46 + 6 * i] = 2
    hooks.screen_colours(s)


def wait(s, hooks, frames):
    """Countdown = frames, then wait until the interrupt has counted it to
    0 ($A56F, $A9D0, the FCL's DELAY)."""
    s.Countdown = frames
    hooks.wait(s, frames)
    s.Countdown = 0


def _conditions(s, ix, hooks):
    m = s.mem
    n = m[ix]
    if n == 0:
        return
    ix += 1
    for _ in range(n):
        length = m[ix]
        run(s, (ix + 1) & 0xFFFF, length, hooks)
        ix = (ix + 1 + length) & 0xFFFF


def events(s, hooks):
    """$9B6E: if EventsDue, the collided object's script (or, if it has
    none and the move was stopped, the bump's sound), then the global
    conditions and the area's."""
    m = s.mem
    if not s.EventsDue:
        return
    if s.Collided:
        s.FoundId = s.Collided
        obj = lookup(s, 0)
        if obj is not None:
            e = m[OBJECT_HEADER + (m[obj] & 0x0F)]
            n = (m[obj + 8] - e) & 0xFF
            if n:
                run(s, (obj + e) & 0xFFFF, n, hooks)
            elif s.Blocked:
                if s.GameFlags & 0x04 or s.GameFlags2 & 0x08:
                    s.Sound = 0x13
                else:
                    hooks.sound(s, 0x13)
    _conditions(s, word(m, 0x8922), hooks)
    _conditions(s, s.AreaCondPtr, hooks)
