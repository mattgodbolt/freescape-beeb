#!/usr/bin/env python3
"""Run Driller's ZX original headless, on SkoolKit's Z80 simulator.

    .venv/bin/python tools/zx.py '<script>' [prefix] [--snap build/zx/driller.z80] [--map FILE]

The Spectrum side of the harness (the siblings' tools/zx.py, from nm):
steps, comma-separated:

    1.5            run 1.5 seconds (50 frames a second)
    f10            run exactly 10 frames
    SPACE:tap      press and release (0.1s); SPACE:0.5 holds for 0.5s
    Q:down / Q:up  hold or release a key
    !name          screenshot to <prefix>name.png (the 256x192 screen, 2x)
    >name          save a .z80 snapshot to <prefix>name.z80
    ?addr:n        print n bytes at addr (decimal, &hex, $hex or 0xhex)
    =addr:v1/v2    poke bytes
    @addr          run until PC reaches addr (gives up after 30s)

Keys are the Spectrum's own names: A-Z, 0-9, SPACE, ENTER, CAPS, SYM, and
KL KR KU KD KF for a Kempston joystick.

The view oracle (rendering any camera with the original's own redraw) is
tools/zx_view.py, on this module's Spectrum.
"""
import argparse
import sys

from PIL import Image
from skoolkit import CSimulator
from skoolkit.simulator import Simulator
from skoolkit.simutils import PC, T, IYh, IYl, from_snapshot, get_state
from skoolkit.snapshot import Snapshot, write_snapshot

FRAME48 = 69888   # T-states in a 48K frame

# Half-row (the address line that selects it, A8..A15) and bit, per key.
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

N, B = 0xD7, 0xFF
PALETTE = [(0, 0, 0), (0, 0, N), (N, 0, 0), (N, 0, N), (0, N, 0), (0, N, N), (N, N, 0), (N, N, N),
           (0, 0, 0), (0, 0, B), (B, 0, 0), (B, 0, B), (0, B, 0), (0, B, B), (B, B, 0), (B, B, B)]


def parse_num(s):
    s = s.strip()
    if s[:1] in ("&", "$"):
        return int(s[1:], 16)
    return int(s, 0)


def screen_image(mem, scale=2):
    """The display as the Spectrum shows it (flash drawn unflashed)."""
    im = Image.new("RGB", (256, 192))
    px = im.load()
    for y in range(192):
        row = 16384 + ((y & 0xC0) << 5) + ((y & 7) << 8) + ((y & 0x38) << 2)
        for cx in range(32):
            attr = mem[22528 + (y // 8) * 32 + cx]
            bright = (attr & 0x40) >> 3
            ink = PALETTE[(attr & 7) | bright]
            paper = PALETTE[((attr >> 3) & 7) | bright]
            b = mem[row + cx]
            for bit in range(8):
                px[cx * 8 + bit, y] = ink if b & (0x80 >> bit) else paper
    if scale != 1:
        im = im.resize((256 * scale, 192 * scale), Image.NEAREST)
    return im


class Spectrum:
    """A 48K Spectrum, from a snapshot, with its keyboard and Kempston port
    driven by the script and the beeper's writes optionally logged
    (portlog: a list it appends (T-states, 'FE', value) to)."""

    def __init__(self, snap, exec_map=None, portlog=None):
        snapshot = Snapshot.get(snap)
        cls = CSimulator or Simulator
        self.sim = from_snapshot(cls, snapshot, config={"fast_djnz": False, "fast_ldir": False})
        self.sim.set_tracer(self)
        self.rows = [0] * 8
        self.kempston = 0
        self.border = snapshot.border
        self.outfe = snapshot.outfe  # get_state() wants it for a snapshot
        self.exec_map = exec_map
        self.frame = FRAME48
        self.portlog = portlog

    @property
    def mem(self):
        return self.sim.memory

    @property
    def regs(self):
        return self.sim.registers

    # Called by the simulator for IN.
    def read_port(self, registers, port):
        if port & 1 == 0:
            sel = (port >> 8) ^ 0xFF
            v = 0
            for i in range(8):
                if sel & (1 << i):
                    v |= self.rows[i]
            return (v ^ 0xFF) & 0xBF  # bit 6 is the EAR input: silence
        if port & 0xFF == 0x1F:
            return self.kempston
        return 0xFF

    def write_port(self, registers, port, value, offset):
        if port & 1 == 0:
            self.border = value & 7
            self.outfe = value
            if self.portlog is not None:
                self.portlog.append((registers[T], "FE", value))

    def run_tstates(self, n, stop=None):
        """Run n T-states, or until PC is stop; return PC."""
        regs = self.sim.registers
        end = regs[T] + n
        self.sim.trace(regs[PC], stop, 0, end, 1, None, self.exec_map, None, None, None)
        return regs[PC]

    def frames(self, n):
        self.run_tstates(n * self.frame)

    def key(self, name, down):
        if name in KEMPSTON:
            bit = KEMPSTON[name]
            self.kempston = (self.kempston | bit) if down else (self.kempston & ~bit)
            return
        row, bit = KEYS[name]
        if down:
            self.rows[row] |= 1 << bit
        else:
            self.rows[row] &= ~(1 << bit)

    def save(self, path):
        ram, registers, state, machine = get_state(self.sim)
        write_snapshot(path, ram, registers, state, machine)


# Start-up (docs/research/zx-driller.md, "Loading and the protection"):
# the loader jumps to START; the protection (PROTECT) asks for a word from
# the manual, picked from its table by a random index, and only once it's
# typed does it plant PUSH IX over the JR $ at the redraw's first two bytes
# (REDRAW); then the control menu (MENU) waits for ENTER, and the game
# enters its main loop (MAIN_LOOP).
START = 0x97A4
PROTECT_ENTRY = 0xCC6F    # PUSH IY: IY is the word's table entry
PROTECT_KEYS = 0xCC7E     # the key-reading loop
MENU = 0xC9C6
MENU_DONE = 0x97EB
MAIN_LOOP = 0x9825
REDRAW = 0x6B12


def protection_word(spec):
    """The word the protection's table entry at IY asks for: its length,
    then page, line and word (offset), then a byte a letter."""
    mem = spec.mem
    iy = spec.regs[IYh] * 256 + spec.regs[IYl]
    return "".join(chr(((mem[iy + 4 + i] & 0xBF) | 0x80) >> 1) for i in range(mem[iy]))


def boot(spec):
    """From the tape just loaded to the main loop's top, in play at the
    start: the word typed as a player would, then ENTER at the menu."""
    limit = 30 * 50 * spec.frame
    assert spec.run_tstates(limit, stop=PROTECT_ENTRY) == PROTECT_ENTRY, "no protection prompt"
    word = protection_word(spec)
    assert spec.run_tstates(limit, stop=PROTECT_KEYS) == PROTECT_KEYS
    run_script(spec, ",".join(f"{c}:tap,0.1" for c in word) + ",ENTER:tap", "")
    assert spec.mem[REDRAW] == 0xDD and spec.mem[REDRAW + 1] == 0xE5, "the protection wasn't passed"
    assert spec.run_tstates(limit, stop=MENU) == MENU, "no control menu"
    spec.key("ENTER", True)
    assert spec.run_tstates(limit, stop=MENU_DONE) == MENU_DONE, "the menu didn't take ENTER"
    spec.key("ENTER", False)
    assert spec.run_tstates(limit, stop=MAIN_LOOP) == MAIN_LOOP, "no main loop"


def run_script(spec, script, prefix):
    for raw in script.split(","):
        step = raw.strip()
        if not step:
            continue
        if step.startswith("!"):
            path = f"{prefix}{step[1:]}.png"
            screen_image(spec.mem).save(path)
            print("SHOT", path)
        elif step.startswith(">"):
            path = f"{prefix}{step[1:]}.z80"
            spec.save(path)
            print("SNAP", path)
        elif step.startswith("?"):
            addr, _, n = step[1:].partition(":")
            a = parse_num(addr)
            data = [spec.mem[a + i] for i in range(int(n or "1"))]
            print(addr, " ".join(f"{b:02x}" for b in data))
        elif step.startswith("="):
            addr, _, vals = step[1:].partition(":")
            a = parse_num(addr)
            for i, v in enumerate(vals.split("/")):
                spec.mem[a + i] = parse_num(v) & 0xFF
        elif step.startswith("@"):
            target = parse_num(step[1:])
            pc = spec.run_tstates(30 * 50 * spec.frame, stop=target)
            print("BREAK", step[1:], "hit" if pc == target else "timeout")
        elif step[0] == "f" and step[1:].isdigit():
            spec.frames(int(step[1:]))
        elif step.replace(".", "", 1).isdigit():
            spec.run_tstates(round(float(step) * 50 * spec.frame))
        else:
            key, _, action = step.partition(":")
            action = action or "tap"
            if action == "down":
                spec.key(key, True)
            elif action == "up":
                spec.key(key, False)
            else:
                secs = 0.1 if action == "tap" else float(action)
                spec.key(key, True)
                spec.run_tstates(round(secs * 50 * spec.frame))
                spec.key(key, False)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script")
    ap.add_argument("prefix", nargs="?", default="build/zx/")
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--map", help="write the addresses executed, one per line, to FILE")
    ap.add_argument("--boot", action="store_true",
                    help="the snapshot is the tape just loaded: pass the protection and the menu first")
    args = ap.parse_args()
    exec_map = set() if args.map else None
    spec = Spectrum(args.snap, exec_map)
    if args.boot:
        boot(spec)
    run_script(spec, args.script, args.prefix)
    if args.map:
        with open(args.map, "w") as f:
            for a in sorted(exec_map):
                f.write(f"${a:04X}\n")  # trace.py's format, which sna2ctl reads
        print("MAP", args.map, len(exec_map))


if __name__ == "__main__":
    sys.exit(main())
