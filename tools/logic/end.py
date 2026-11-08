"""The game's end and a new game, transcribed: $9AB7 (the end), $9B62 (its
way out), $9C36 (a new game) and $97CD (a game's start, after it).

The input finds GameOver set ($99C8) and goes to the end instead of
returning: the shots stop, the panel's message line says why, sound 20
plays unless the game was won, and area 127 is entered (its name takes the
safe sectors, FclVar32), redrawn, the panel with it. Then the original
waits for a key: none is read for 75 frames, then any key ends the wait,
for up to 12 x 75 frames more; with none, the demo comes next ($891F 3).
Either way sound 6, GameFlags bit 1, and back through the main loop
($982B) to a new game from the database's header, and its start.

    end(s, hooks)                   the end, to the wait for a key
    restart(s, hooks, demo=False)   the wait answered (demo: no key came),
                                    the new game, and its start

The redraws are the renderer's (hooks.ended, hooks.started), and the
control menu is the ZX's joysticks (not ported).
"""
from .area import go_to_entrance
from .fcl import events, wait

# Each end's message, by GameOver ($8CBA on): anything past 5 is 6's.
MESSAGES = {1: 0x8CC8, 2: 0x8CBA, 3: 0x8CD6, 4: 0x8CE4, 5: 0x8D00}
TERMINATED = 0x8CF2
SHOTS = 0x8A21          # the interrupt's sensors: bit 2 stops their shots, bit 0 a shot shows
DEMO = 0x891F           # 3: the demo plays itself ($9A27)
DEMO_ON = 3
END_AREA = 0x7F
WON = 5
END_SOUND = 0x14        # the end's (not when won) ...
RESTART_SOUND = 6       # ... and the way out's
START_WAIT = 0x28       # the start's frames before its crosshair ($97F0)


def message_of(over):
    return MESSAGES.get(over, TERMINATED)


def number(s, at, n, value):
    """$9390: value's n lowest decimal digits as characters at at on (the
    original's divide by 10, rounding, then corrected down: the floor)."""
    m = s.mem
    for i in range(n):
        m[at + n - 1 - i] = 0x30 + value % 10
        value //= 10


def end(s, hooks):
    """$9AB7-$9B40: the end, as the input finds GameOver set."""
    m = s.mem
    m[SHOTS] |= 4                       # (and waits for a shot's lines to go)
    over = s.GameOver
    hooks.message(s, message_of(over))
    if over != WON:
        hooks.sound(s, END_SOUND)
    s.AreaId = END_AREA
    s.EntranceId = 0
    s.CrossOn = 0
    go_to_entrance(s)
    name = (s.AreaNamePtr + 1) & 0xFFFF
    number(s, name, 2, s.FclVar32)
    if m[name] == 0x30:
        m[name] = 0x20
    s.GameFlags = 0x04
    s.GameFlags2 = 0x40
    hooks.ended(s)
    m[SHOTS] &= ~4                      # ($9841's last: the shots go on, of area 127's none)


def new_game(s, hooks):
    """$9C36: a new game from the database's header: the probe's level,
    the step's and turn's sizes, the vehicles' energy and shields; the
    score, the FCL's bits and variables, the rigs, the crosshair and the
    sensors' lists cleared; then $BD74's pointers and limits, the clock,
    the vehicle; area and entrance from the header; and every object's
    flags as the database began (bit 7: invisible at the start)."""
    m = s.mem
    s.ExtLevel = m[0xCFFC]
    s.StepIndex = m[0xD000]
    s.TurnIndex = m[0xD001]
    s.GameOver = 1
    s.Wipe = 1
    m[0x8A20] = 0x3F
    s.CrossOn = 0
    m[0x8A24] = 0
    m[0x8A25] = 0
    s.FclVar32 = 0
    s.GasChosen = 0
    s.Sound = 0
    s.ShootMode = 0
    s.CrossWanted = 0
    m[0x8872:0x8875] = bytes(3)         # the score
    m[0x887B:0x887F] = bytes(4)         # the FCL's bits
    m[0x887F:0x889F] = bytes(32)        # its variables, 1-32
    m[0x877B:0x878D] = bytes(18)        # RigPlaced
    m[0x878D:0x879F] = bytes(18)        # RigState
    s.JetEnergy = m[0xCF44]
    s.ProbeEnergy = m[0xCF46]
    s.JetShield = m[0xCF45]
    s.ProbeShield = m[0xCF47]
    s.Step = m[0x88BF + s.StepIndex]
    s.Turn = m[0x88CA + s.TurnIndex]
    _header(s)
    s.AreaId = m[0xCF41]
    s.EntranceId = m[0xCF42]
    go_to_entrance(s)
    _flags(s)


def _word(m, a):
    return m[a] | m[a + 1] << 8


def _header(s):
    """$BD74: the database's pointers, the probe's limits, the keys' repeat,
    the clock's text, and the vehicle the game starts in, with its energy
    and shield."""
    m = s.mem
    m[0x8912:0x8914] = (0xCF3E).to_bytes(2, "little")
    m[0x8A1B:0x8A1D] = m[0x8BE4:0x8BE6]
    m[0x8914:0x8916] = (0xD006).to_bytes(2, "little")
    m[0x891D:0x891F] = (0xCF48).to_bytes(2, "little")
    m[0x8A81:0x8A83] = (0xCDDC).to_bytes(2, "little")
    demo = (_word(m, 0xCF84) + _word(m, 0x8912)) & 0xFFFF
    m[0x8924:0x8926] = demo.to_bytes(2, "little")
    m[0x8927:0x8929] = demo.to_bytes(2, "little")
    m[0x8926] = 0
    m[0x8922:0x8924] = ((_word(m, 0xCF86) + _word(m, 0x8912)) & 0xFFFF).to_bytes(2, "little")
    s.FallLimit = m[0xCFFA]
    s.ClimbLimit = m[0xCFFB]
    s.ExtMax = m[0xCFFD]
    s.RepeatDelay = m[0xD002]
    s.RepeatRate = m[0xD003]
    m[0x8A65:0x8A67] = m[0xD004:0xD006]
    m[0x8BF3:0x8BF6] = m[0xCFA4:0xCFA7]
    m[0x88A4:0x88AC] = m[0xCFF2:0xCFFA]  # the clock: 04:00:00
    s.InJet = m[0xCFFF]
    if s.InJet:
        m[0x887E] |= 0x80
        s.Energy = s.JetEnergy
        s.Shield = s.JetShield
    else:
        m[0x887E] &= 0x7F
        s.Energy = s.ProbeEnergy
        s.Shield = s.ProbeShield


def _flags(s):
    """$9CDD: every area's objects' flags as the database began: destroyed
    and invisible cleared, and invisible again where bit 7 says it was."""
    m = s.mem
    n = m[0xCF3E]
    table = _word(m, 0x8914)
    for i in range(n if n else 256):
        a = (_word(m, 0x8912) + _word(m, table + 2 * i)) & 0xFFFF
        k = m[a + 1]
        if not k:
            continue
        p = (a + 0x19) & 0xFFFF
        for _ in range(k):
            f = m[p] & 0x9F
            if f & 0x80:
                f |= 0x40
            m[p] = f
            p = (p + m[p + 8]) & 0xFFFF


def start(s, hooks, keys=("ENTER",), demo=False):
    """$97CD-$9804: a game's start: everything redrawn, the panel, the
    clock's text, the control menu (not in the demo), the sensors' test;
    then, but in the demo, 40 frames and the crosshair shown as B shows it;
    and the game goes on."""
    from .passes import crosshair_action, read_keys
    s.GameFlags = 0xFD
    s.GameFlags2 = 0xFF
    hooks.started(s)
    if not demo:
        # (the control menu reads the keys until ENTER: the end's key,
        # still held, a repeat)
        read_keys(s, keys, hooks)
        wait(s, hooks, START_WAIT)
        crosshair_action(s, 0x15, hooks)
    s.GameOver = 0


def restart(s, hooks, keys=("ENTER",), demo=False):
    """$9B43-$9B6D, then $9825's $982B: the end's wait answered by keys
    (read as $943C reads them, from none held before), or with none the
    demo next; sound 6, the end's flag, and the main loop's new game
    ($9C36) and start ($97CD)."""
    from .passes import new_game_due, read_keys
    read_keys(s, (), hooks)
    if demo:
        s.mem[DEMO] = 3
    else:
        read_keys(s, keys, hooks)
    hooks.sound(s, RESTART_SOUND)
    s.GameFlags = 0x02
    s.GameFlags2 = 0
    events(s, hooks)                    # (none due: the input cleared EventsDue)
    new_game_due(s, hooks, keys)
