"""The information screen, transcribed: $C3DC (I, alone in the pass's
keys) and its key's answer ($C5A2-$C80D).

The original stops the sensors' shots, sets GameOver 6 while it shows,
waits 25 frames (counting from here), gives the view the colours black
and yellow ($A77A with the area's last two colours 0 and 6 a moment),
clears it and prints nine lines of 26 characters into it: the sector (or
area, from area $13 on) and its name, its rig's status, the gas found,
the share tapped, the gas tapped, the sectors in all and the safe ones,
and the keys. Then it reads the keys until one is held: S and L save and
load the game to tape (not ported: decision 153), 1 abandons the game
(GameOver 6 kept: the input's next pass goes to the end, TERMINATED), and
any other goes on: 11 frames, the area's colours back, the view redrawn
from the buffer, the crosshair, GameOver 0 and the shots on.

    begin(s, hooks)         to the wait for a key; False if not shown
    answer(s, hooks, keys)  the wait answered by the keys held
    lines(s)                the nine lines, as the original's buffer
                            ($C2B2) holds them once printed
"""
from .area import word
from .arith import mul_a_hl, mul_h_l
from .fcl import screen_update, wait

SHOTS = 0x8A21          # the interrupt's sensors: bit 2 stops their shots
TERMINATED = 6
SHOW_FRAMES = 0x19      # before a key is read
BACK_FRAMES = 0x0B      # after one that goes on
COLS = 26
TEXT = 0xC2B2           # the original's nine lines, COLS each
ROWS = (1, 2, 3, 4, 5, 7, 8, 10, 11)    # each line's character row in the view
ABORT, SAVE, LOAD = 0x31, 0x53, 0x4C
FIRST_AREA = 0x13       # from here on an area, not a sector, and no rig
WORDS = 0xC39C          # "  AREA", "SECTOR", "NOT REQUIRED", "UNPOSITIONED", "POSITIONED", "NONE", "ZERO"
N_WORDS = 0x36


def begin(s, hooks):
    """$C3DC-$C59C: shown only for I alone in the pass's keys. The text
    is built and printed into the view (hooks.info_shown, the renderer's)
    while the 25 frames count."""
    if s.KeyCount != 1:
        return False
    m = s.mem
    m[SHOTS] |= 4
    s.GameOver = TERMINATED
    s.Countdown = SHOW_FRAMES
    kept = bytes(m[0x8870:0x8872])
    m[0x8870], m[0x8871] = 0x00, 0x06
    screen_update(s, hooks)
    m[0x8870:0x8872] = kept
    build(s)
    hooks.info_shown(s)
    wait(s, hooks, SHOW_FRAMES)
    return True


def answer(s, hooks, keys):
    """$C5A2-$C80D: the keys read (as $943C reads them) until one is held;
    1 abandons the game, any other goes on (S and L too: decision 153)."""
    from .passes import read_keys
    first = read_keys(s, keys, hooks)
    if first is None:
        raise ValueError("the information screen's answer has no key")
    if first == ABORT:
        return
    wait(s, hooks, BACK_FRAMES)
    screen_update(s, hooks)
    hooks.info_gone(s)
    s.GameOver = 0
    s.mem[SHOTS] = 0


def _number(m, at, v, digits):
    """$9390: v's low digits, leading zeros, as ASCII at at."""
    for i in reversed(range(digits)):
        m[at + i] = 0x30 + v % 10
        v //= 10


def _put(m, at, text):
    m[at:at + len(text)] = text


def _blank_zeros(m, at, n):
    """Up to n leading '0's from at as spaces, stopping at the first other."""
    for i in range(n):
        if m[at + i] != 0x30:
            return
        m[at + i] = 0x20


def build(s):
    """$C40D-$C561: the text, in the original's buffer (the view's clearing
    and printing are the renderer's)."""
    m = s.mem
    for k in range(5):                  # the right halves of the first five lines
        _put(m, TEXT + COLS * k + 13, b" " * 13)
    _put(m, TEXT + 13, m[s.AreaNamePtr:s.AreaNamePtr + 12])
    words = bytes(m[WORDS:WORDS + N_WORDS])
    area = s.AreaId
    dashes = (TEXT + 2 * COLS + 13, TEXT + 3 * COLS + 13, TEXT + 4 * COLS + 13)
    if not (area - FIRST_AREA) & 0x80:  # (CP $13 : JP M)
        _put(m, TEXT + 5, words[0:6])
        _put(m, TEXT + COLS + 13, words[12:24])
        for a in dashes:
            m[a] = 0x2D
    else:
        _put(m, TEXT + 5, words[6:12])
        c = (area - 1) & 0xFF
        placed = m[0x877B + c]
        if placed == 0:
            _put(m, TEXT + COLS + 13, words[24:36])
            for a in dashes:
                m[a] = 0x2D
        else:
            if not (placed - 2) & 0x80:   # (CP 2 : JP P) a rig that found gas
                yld = m[(word(m, 0x87A3) + c) & 0xFFFF]
                at = TEXT + 2 * COLS + 13
                _number(m, at, yld, 2)
                if m[at] == 0x30:
                    m[at] = 0x20
                _put(m, at + 2, b"000")
                _put(m, at + 6, b"CFT")
                pct = m[0x878D + c]
                at = TEXT + 3 * COLS + 15
                _number(m, at, pct, 3)
                _blank_zeros(m, at, 2)
                m[TEXT + 3 * COLS + 19] = 0x25
                at = TEXT + 4 * COLS + 13
                _number(m, at, mul_a_hl(pct, mul_h_l(0x0A, yld)), 5)
                _blank_zeros(m, at, 4)
                _put(m, TEXT + 4 * COLS + 19, b"CFT")
            else:
                _put(m, TEXT + 2 * COLS + 13, words[46:50])
                _put(m, TEXT + 4 * COLS + 13, words[46:50])
                _put(m, TEXT + 3 * COLS + 13, words[50:54])
            _put(m, TEXT + COLS + 13, words[36:46])
    at = TEXT + 6 * COLS + 19
    _number(m, at, s.FclVar32, 2)
    if m[at] == 0x30:
        m[at] = 0x20


def lines(s):
    """The nine lines as text, from the original's buffer."""
    m = s.mem
    return [bytes(m[TEXT + COLS * k:TEXT + COLS * (k + 1)]).decode("ascii") for k in range(len(ROWS))]
