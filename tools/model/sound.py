"""The sound driver: Driller's sounds on the SN76489, a vertical sync at a
time (src/sound.6502, docs/research/sound.md).

A sound is a script of segments, made at build time from the original's
beeper by tools/mksound.py. A segment is some ticks (vertical syncs) of
one mode, its period and attenuation each moving in a straight line, in
SEGMENT bytes:

    0       ticks, 1 to 255; 0 ends the sound (and is its only byte)
    1       the mode: SILENT, TONE, PERIODIC or WHITE
    2, 3    tone 2's period, 12.4, low byte first
    4, 5    its step a tick, signed
    6       the attenuation, 4.4
    7       its step a tick, signed

A tick plays the period's and attenuation's whole parts, then adds the
steps. Every channel but tone 2 and the noise stays silent; tone 2's
period is the noise's clock too:

    TONE        tone 2 at the period and attenuation, the noise silent
    PERIODIC    the noise periodic (its output a fifteenth of tone 2's
                frequency), tone 2 silent
    WHITE       the noise white, at tone 2's rate, tone 2 silent
    SILENT      both silent

The chip is written only where a register differs from what the driver
last wrote there, in a fixed order: tone 2's period (two bytes: the latch
with its low four bits, then the high six), the noise's control (writing
it restarts the noise's shift register, so it's written only when the mode
changes), tone 2's attenuation, the noise's.

A sound asked for waits in `next` until the one playing ends; the driver
starts it at the tick the last ends, so sounds follow one another without
a gap, in order, as the original plays them.
"""

SILENT, TONE, PERIODIC, WHITE = 0, 1, 2, 3
NOISE_CONTROL = {PERIODIC: 3, WHITE: 7}     # tone 2's rate; FB 0 periodic, 1 white
SEGMENT = 8
SOUNDS = 21                                 # the original's table at $954A

# what sound_init writes: every channel silent, tone 0 first
INIT_WRITES = [0x9F, 0xBF, 0xDF, 0xFF]


def segment_bytes(count, mode, per, dper, att, datt):
    """A segment's bytes (per and att as 12.4 and 4.4, the steps signed)."""
    assert 1 <= count <= 255
    return [count, mode, per & 0xFF, (per >> 8) & 0xFF, dper & 0xFF, (dper >> 8) & 0xFF, att & 0xFF, datt & 0xFF]


class Driver:
    """The driver's state and its tick, as src/sound.6502 has them.

    blob: the scripts' bytes; index: each sound's offset in blob (1 to
    SOUNDS)."""

    def __init__(self, blob, index):
        self.blob = blob
        self.index = index
        self.next = 0
        self.ptr = None
        self.left = 0
        self.mode = SILENT
        self.per = self.dper = 0
        self.att = self.datt = 0
        self.played = None
        # the chip as last written (sound_init: all silent; period and
        # control unknown)
        self.c_per = None
        self.c_nctl = None
        self.c_tatt = 15
        self.c_natt = 15

    def ask(self, n):
        """The hook's request (once next is free)."""
        assert self.next == 0 and 1 <= n <= SOUNDS
        self.next = n

    def busy(self):
        return self.ptr is not None or self.next != 0

    def _segment(self):
        b, p = self.blob, self.ptr
        while True:
            if p is None:
                if not self.next:
                    self.ptr = None
                    return
                p = self.index[self.next]
                self.next = 0
            if b[p] == 0:
                p = None
                continue
            self.left, self.mode = b[p], b[p + 1]
            self.per = b[p + 2] | b[p + 3] << 8
            self.dper = b[p + 4] | b[p + 5] << 8
            self.att, self.datt = b[p + 6], b[p + 7]
            self.ptr = p + SEGMENT
            return

    def tick(self):
        """A vertical sync's: the bytes written to the chip, in order."""
        if self.left == 0:
            self._segment()
        if self.ptr is None:
            mode, per, att = SILENT, None, 15
        else:
            mode, per, att = self.mode, self.per >> 4, self.att >> 4
            self.played = (mode, per, att)
            self.left -= 1
            self.per = (self.per + self.dper) & 0xFFFF
            self.att = (self.att + self.datt) & 0xFF
        return self._write(mode, per, att)

    def _write(self, mode, per, att):
        out = []
        tatt, natt, nctl = 15, 15, self.c_nctl
        if mode == TONE:
            tatt = att
        elif mode in NOISE_CONTROL:
            natt = att
            nctl = NOISE_CONTROL[mode]
        if mode != SILENT and per != self.c_per:
            out += [0xC0 | (per & 15), per >> 4]
            self.c_per = per
        if nctl != self.c_nctl:
            out.append(0xE0 | nctl)
            self.c_nctl = nctl
        if tatt != self.c_tatt:
            out.append(0xD0 | tatt)
            self.c_tatt = tatt
        if natt != self.c_natt:
            out.append(0xF0 | natt)
            self.c_natt = natt
        return out


def play(blob, index, asks, ticks):
    """The writes of each tick, 0 to ticks - 1, with asks a list of
    (tick, sound): each put in next at the start of that tick (before its
    driver runs), as the hook does between vertical syncs."""
    d = Driver(blob, index)
    out = []
    i = 0
    for t in range(ticks):
        while i < len(asks) and asks[i][0] == t:
            d.ask(asks[i][1])
            i += 1
        out.append(d.tick())
    return out
