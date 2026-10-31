"""One pass of Driller's main loop, transcribed: $9825 calls the input
($9990) and the events ($9B6E), then redraws ($6B12), copies the view and
runs the sensors ($9841) and updates the panel ($B72B). The logic is the
first two; the rest are the renderer's (hooks).

    run_pass(state, keys, tick=False, hooks=None)

keys: the keys held through the pass, by the ZX's names (tools/zx.py's
MATRIX). tick: a minute of the clock ends during the pass, as the
interrupt counts it ($BB27), which ends the pass at once. With no keys and
no tick, the original waits in its input for one or the other.
"""
from .arith import minus
from .fcl import events, wait
from .hooks import Hooks
from .move import movement

KEY_CODES = 0x9414    # a code for each key, 5 a half-row, $FEFE's first
KEY_ROWS = 0x9404     # the half-rows as read, CPL AND $1F
KEY_TABLE = 0x8FC8    # key, action, shooting action; then key, action
DEMO = 0x891F         # 3: the demo plays itself ($9A27)

# The keyboard: half-row (as the ZX's ports $FEFE ... $7FFE) and bit.
MATRIX = [
    ["CAPS", "Z", "X", "C", "V"],
    ["A", "S", "D", "F", "G"],
    ["Q", "W", "E", "R", "T"],
    ["1", "2", "3", "4", "5"],
    ["0", "9", "8", "7", "6"],
    ["P", "O", "I", "U", "Y"],
    ["ENTER", "L", "K", "J", "H"],
    ["SPACE", "SYM", "M", "N", "B"],
]
KEYS = {k: (row, bit) for row, ks in enumerate(MATRIX) for bit, k in enumerate(ks)}
KEMPSTON = {"KR": 1, "KL": 2, "KD": 4, "KU": 8, "KF": 16}


class NoInput(Exception):
    """The original would wait here for a key or the clock."""


def read_keys(s, held, hooks):
    """$943C: up to five keys held, in the keyboard's order, as codes in
    Keys; returns the first code, or None if no key is held. A held set
    seen last time waits RepeatDelay, then RepeatRate, before it counts
    again (both are 0 in play)."""
    m = s.mem
    rows = [0] * 8
    kempston = 0
    for k in held:
        if k in KEMPSTON:
            kempston |= KEMPSTON[k]
        else:
            row, bit = KEYS[k]
            rows[row] |= 1 << bit
    while True:
        for r in range(8):
            m[KEY_ROWS + r] = rows[r]
        s.KeyCount = 0
        full = False
        for r in range(8):
            v = m[KEY_ROWS + r]
            while v:
                bit = (v & -v).bit_length() - 1
                code = m[KEY_CODES + 5 * r + bit]
                m[0x8FBD + s.KeyCount] = code
                s.KeyCount = s.KeyCount + 1
                if s.KeyCount == 5:
                    full = True
                    break
                v &= (0xFE << bit) & 0xFF
                m[KEY_ROWS + r] = v
            if full:
                break
        if not full and s.Control == 2:
            for code, bit in ((0x95, 16), (0x91, 8), (0x92, 4), (0x93, 2), (0x94, 1)):
                if kempston & bit:
                    m[0x8FBD + s.KeyCount] = code
                    s.KeyCount = s.KeyCount + 1
                    if s.KeyCount == 5:
                        full = True
                        break
        n = s.KeyCount
        if not full and n == 0:
            s.LastKeyCount = 0
            return None
        if s.LastKeyCount == n and m[0x940E:0x940E + n] == m[0x8FBD:0x8FBD + n]:
            if not s.Repeating:
                s.Repeating = 1
                s.RepeatCopy = s.RepeatDelay
                s.Countdown = s.RepeatDelay
                continue
            if s.Countdown:
                hooks.wait(s, s.Countdown)   # the interrupt counts it down
                s.Countdown = 0
                continue
            s.Countdown = s.RepeatRate
            return m[0x8FBD]
        s.Repeating = 0
        s.LastKeyCount = n
        m[0x940E:0x940E + n] = m[0x8FBD:0x8FBD + n]
        return m[0x8FBD]


def _action_of(s, code):
    """$99EF-$9A1B: a key's action from the key table, $7F if none."""
    m = s.mem
    p = KEY_TABLE
    n3 = s.KeyTable3
    for _ in range(n3 if n3 else 256):
        if m[p] == code:
            return m[p + 2] if s.ShootMode else m[p + 1]
        p += 3
    n2 = s.KeyTable2
    for _ in range(n2 if n2 else 256):
        if m[p] == code:
            return m[p + 1]
        p += 2
    return 0x7F


def _centre(s):
    s.CrossX = s.mem[0x88D9]
    s.CrossY = s.mem[0x88DA]


def crosshair_action(s, a, hooks):
    """$A95C: actions $15-$1E. SPACE ($1E) toggles shooting mode, in which
    the movement keys move the crosshair ($17-$1A); B ($15) shows or hides
    the crosshair; 0 ($16) fires, if the crosshair is shown."""
    if a == 0x1E:
        s.ShootMode = ~s.ShootMode & 0xFF
        saved = s.GameFlags, s.GameFlags2
        s.GameFlags, s.GameFlags2 = 1, 0
        hooks.panel(s)
        s.GameFlags, s.GameFlags2 = saved
        hooks.sound(s, 0x13)
        if s.ShootMode:
            if s.CrossOn:
                wait(s, hooks, 9)
                return
            s.CrossOn = 0xFF
            _centre(s)
            hooks.crosshair(s)
            wait(s, hooks, 9)
            return
        if s.CrossOn:
            hooks.crosshair(s)
        s.CrossOn = s.CrossWanted
        if s.CrossOn:
            _centre(s)
            hooks.crosshair(s)
        wait(s, hooks, 9)
        return
    if a == 0x15:
        if s.ShootMode:
            return
        s.CrossWanted = ~s.CrossWanted & 0xFF
        s.CrossOn = s.CrossWanted
        if s.CrossOn:
            _centre(s)
        hooks.crosshair(s)
        wait(s, hooks, 9)
        return
    if not s.CrossOn:
        return
    m = s.mem
    if a == 0x18:
        hooks.crosshair(s)
        if s.CrossX != 1:
            s.CrossX = s.CrossX - 1
    elif a == 0x17:
        hooks.crosshair(s)
        if s.CrossX != (m[0x88D9] * 2) & 0xFF:
            s.CrossX = s.CrossX + 1
    elif a == 0x1A:
        hooks.crosshair(s)
        if s.CrossY != (m[0x88DA] * 2) & 0xFF:
            s.CrossY = s.CrossY + 1
    elif a == 0x19:
        hooks.crosshair(s)
        if s.CrossY != 1:
            s.CrossY = s.CrossY - 1
    elif a == 0x16:
        hooks.laser(s)
        hooks.sound(s, 1)
        hooks.laser(s)
        hooks.shot(s)
        s.EventsDue = 1
        s.ShotFlag = 1
        return
    else:
        return
    hooks.crosshair(s)    # $AA3F, then a busy loop of 1,000


def minute(s, hooks):
    """$BB27: the interrupt, as a minute of the clock ends: a unit of
    energy spent and the minute counters (FCL variables 30 and 31) up, or,
    with no energy left, the game over. Once the game is over the
    interrupt keeps no time."""
    if s.GameOver:
        return
    if s.Energy:
        s.FclVar30 = s.FclVar30 + 1
        s.MinuteCount = s.MinuteCount + 1
        s.Energy = s.Energy - 1
        s.PanelEnergy = s.Energy
    else:
        s.GameOver = 3


def input_pass(s, held, hooks):
    """$9990: clear the pass's flags, wait for keys (or the clock's
    minute), and do each key's action in turn. Returns False if the game
    is over (GameOver set: the original goes to its end, $9AB7)."""
    s.GameFlags = 0
    s.GameFlags2 = 0
    s.Collided = 0
    s.ShotFlag = 0
    s.Wipe = 0
    s.EventsDue = 0
    s.Sound = 0
    s.Blocked = 0
    s.ActionIndex = 0
    hooks.key_lights(s, "off")
    if s.mem[DEMO] == 3:
        raise NotImplementedError("the demo's playback ($9A27)")
    first = read_keys(s, held, hooks)
    if s.GameOver:
        hooks.game_over(s)
        return False
    if s.MinuteSeen != s.MinuteCount:
        s.MinuteSeen = s.MinuteCount
        s.EventsDue = 1
        return True
    if first is None:
        raise NoInput("no key held and no minute: the original waits")
    n = s.KeyCount
    for i in range(n):
        s.mem[0x998A + i] = _action_of(s, s.mem[0x8FBD + i])
    hooks.key_lights(s, "on")
    i = 0
    while True:
        a = s.mem[0x998A + i]
        if not minus(a, 1) and minus(a, 0x15):
            movement(s, a, hooks)
        elif not minus(a, 0x15) and minus(a, 0x1F):
            crosshair_action(s, a, hooks)
        elif a in (0x28, 0x2A):
            hooks.rig(s, a)
            return True
        elif a == 0x29:
            hooks.info(s)
            return True
        i += 1
        s.ActionIndex = i
        if i == n:
            return True


def run_pass(s, keys=(), tick=False, hooks=None):
    """One pass's logic: the minute (if tick), the input and the events.
    Returns "over" if the input found the game over (the original goes to
    its end, $9AB7, and the pass goes no further), else whether the game
    goes on after the pass. Raises move.Freeze where the original hangs."""
    hooks = hooks or Hooks()
    if tick:
        minute(s, hooks)
    if not input_pass(s, keys, hooks):
        return "over"
    events(s, hooks)
    return not s.GameOver
