"""The original, run pass by pass, as the logic's oracle.

`Original` holds a Spectrum (tools/zx.py) in play at the main loop's top
($9825) and runs one pass at a time: the keys held from there until the
input returns ($9828), the state read when the events are done ($982B),
then on through the redraw, the copy and the panel to the top again.

The harness holds what's real time on the ZX so that a pass is the same
on both sides:

- the clock: before each pass its seconds are set to 59 and its frame
  count to 0, so no minute ends inside the pass; for a tick pass they're
  set to 00 and 49, so the interrupt ends a minute in its first frame,
  while the input waits;
- the sensors: the interrupt's read of its list of sensors to fire ($8A25)
  answers none (SENSOR_SHOTS), so no shot lands inside a pass, even one
  that redraws inside itself (a rig's, the FCL's REDRAW). A scenario's
  "sensors" step lets them: the interrupt is run that many frames
  (sensors()), its read put back, with the original waiting between
  passes.

Since the sensors' layer (2026-11-08) the list is no longer emptied before
each pass: hiding a sensor ($B467) takes it out of the list as it stands.

Everything else is the original's own code.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import zx  # noqa: E402
from skoolkit.simutils import A, IXh, IXl  # noqa: E402

MAIN_LOOP = 0x9825
AFTER_INPUT = 0x9828
AFTER_EVENTS = 0x982B
FCL_RUN = 0xB320
SCRIPT = 0x5B00          # the printer buffer: the game never uses it
CLOCK_SECONDS = 0x88AA
SECOND_FRAMES = 0x88A3
SENSOR_FIRE = 0x8A25
DRAW_LIST = 0x8A9D
N_DRAWN = 0x8918
GAME_OVER = 0x9AB7       # the input's way to the end of the game
INTERRUPT = 0xBAE6       # the frame's interrupt: the clock and the sensors
SIGHT = 0x9841           # the sensors' test after the redraw
# A pass's limit. Area 18's last condition redraws seven times, and the
# busiest redraw is 62 frames (docs/research/zx-driller.md).
PASS_FRAMES = 2000
# The interrupt's read of the fire list's count ($BBA4, LD A,($8A25)), which
# the harness makes LD A,0 : NOP: no sensor fires. A pass that redraws inside
# itself (a rig's, the FCL's REDRAW) fills the list again, and its waits let
# the interrupt fire at the shield mid-pass otherwise.
SENSOR_SHOTS = 0xBBA4
SENSOR_SHOTS_WAS = (0x3A, 0x25, 0x8A)
SENSOR_SHOTS_OFF = (0x3E, 0x00, 0x00)


class Waiting(Exception):
    """The original didn't finish the pass: it's waiting for input."""


class Original:
    def __init__(self, snap, contended=False):
        self.spec = zx.Spectrum(snap, contended=contended)
        assert self.spec.regs[zx.PC] == MAIN_LOOP, "the snapshot isn't at the main loop's top"
        m = self.spec.mem
        assert tuple(m[SENSOR_SHOTS:SENSOR_SHOTS + 3]) == SENSOR_SHOTS_WAS, "the interrupt isn't as expected"
        m[SENSOR_SHOTS:SENSOR_SHOTS + 3] = bytes(SENSOR_SHOTS_OFF)

    @property
    def mem(self):
        return self.spec.mem

    def memory(self):
        return bytes(self.spec.mem[0:0x10000])

    def drawn(self):
        """The ids of the objects in the last redraw's draw list."""
        m = self.spec.mem
        lst = m[DRAW_LIST] | m[DRAW_LIST + 1] << 8
        out = set()
        for i in range(m[N_DRAWN]):
            p = m[lst + 4 * i] | m[lst + 4 * i + 1] << 8
            out.add(m[p])
        return out

    def _hold(self, tick):
        m = self.spec.mem
        if tick:
            m[CLOCK_SECONDS], m[CLOCK_SECONDS + 1] = ord("0"), ord("0")
            m[SECOND_FRAMES] = 49
        else:
            m[CLOCK_SECONDS], m[CLOCK_SECONDS + 1] = ord("5"), ord("9")
            m[SECOND_FRAMES] = 0

    def _run_to(self, addr, frames=PASS_FRAMES):
        pc = self.spec.run_tstates(frames * self.spec.frame, stop=addr)
        if pc != addr:
            raise Waiting(f"never reached ${addr:04X} (PC ${pc:04X})")

    def begin(self, tick=False):
        """Hold the clock and the sensors for the next pass. Returns the
        memory as the pass starts, which the logic syncs from."""
        assert self.spec.regs[zx.PC] == MAIN_LOOP
        self._hold(tick)
        return self.memory()

    def run_pass(self, keys=(), tick=False, ends=False):
        """The pass begun: keys held through the input. Returns the memory
        when the events are done, and leaves the original at the next
        pass's top. ends: the input will find the game over; returns the
        memory as it goes to the end ($9AB7) instead, and stays there."""
        for k in keys:
            self.spec.key(k, True)
        try:
            self._run_to(GAME_OVER if ends else AFTER_INPUT)
        finally:
            for k in keys:
                self.spec.key(k, False)
        if ends:
            return self.memory()
        self._run_to(AFTER_EVENTS)
        after = self.memory()
        # the redraw's projection, before the sensors' test ($9841), if it
        # redraws; and after it all
        self.projected = None
        if after[0x8920] & 0x04 or after[0x8921] & 0x08:
            self._run_to(SIGHT)
            self.projected = self.memory()
        self._run_to(MAIN_LOOP)
        self.redrawn = self.memory()
        return after

    def sensors(self, frames):
        """Time going by between passes, its sensors let fire: the input
        entered with no key held, which clears its pass's flags and waits
        (a frame of it), then the interrupt ($BAE6) run frames times.
        Returns the memory after, and leaves the original at the main loop's
        top again (its stack as it was). The clock's seconds are held as for
        a pass."""
        assert self.spec.regs[zx.PC] == MAIN_LOOP
        r, m = self.spec.regs, self.spec.mem
        sp = r[zx.SP]
        self._hold(False)
        self.spec.run_tstates(self.spec.frame)
        m[SENSOR_SHOTS:SENSOR_SHOTS + 3] = bytes(SENSOR_SHOTS_WAS)
        try:
            for _ in range(frames):
                self.spec.call(INTERRUPT)
        finally:
            m[SENSOR_SHOTS:SENSOR_SHOTS + 3] = bytes(SENSOR_SHOTS_OFF)
        r[zx.PC], r[zx.SP] = MAIN_LOOP, sp
        return self.memory()

    def fcl(self, code, shot=False):
        """Run FCL bytes with the original's interpreter ($B320), from the
        main loop's top, as a scenario's set-up. Returns the memory after."""
        assert self.spec.regs[zx.PC] == MAIN_LOOP
        m = self.spec.mem
        for i, b in enumerate(code):
            m[SCRIPT + i] = b
        m[0x8BF1] = 1 if shot else 0
        r = self.spec.regs
        r[IXh], r[IXl] = SCRIPT >> 8, SCRIPT & 0xFF
        r[A] = len(code)
        self.spec.call(FCL_RUN)
        r[zx.PC] = MAIN_LOOP
        return self.memory()

    def poke(self, addr, values):
        m = self.spec.mem
        for i, v in enumerate(values):
            m[addr + i] = v & 0xFF
