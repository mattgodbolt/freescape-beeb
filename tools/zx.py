#!/usr/bin/env python3
"""Run Driller's ZX original headless, on SkoolKit's Z80 simulator.

    .venv/bin/python -I tools/zx.py '<script>' [prefix] [--snap build/zx/driller.z80] [--map FILE]
    .venv/bin/python -I tools/zx.py --view AREA:ENTRANCE [--camera x,y,z,pitch,yaw,roll] [prefix]

The Spectrum side of the harness (the siblings' tools/zx.py, from nm).
A script is steps, comma-separated:

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

--boot takes a snapshot of the tape just loaded through the protection
and the control menu to the main loop first (make zx).

--passes SCENARIO runs a scenario (tests/logic/*.txt: keys held by pass)
on the original from the snapshot, pass by pass, and prints the camera
and what the pass did after each (tools/logic/oracle.py; tools/logic/
check.py compares the same passes with the transcription).

--view draws one view with the original's own redraw (render_view):
area AREA from entrance ENTRANCE (0 for none), the camera optionally
overridden, and writes <prefix>a<area>_e<entrance>.png and .bin (the
view's 208 x 104 pixels, 26 bytes a row, bit 7 left, set = ink) and
prints the redraw's T-states. tools/zx_views.py draws every entrance.
"""
import argparse
import sys

from PIL import Image
from skoolkit import CSimulator
from skoolkit.simulator import Simulator
from skoolkit.simutils import PC, SP, T, IYh, IYl, from_snapshot, get_state
from skoolkit.snapshot import Snapshot, write_snapshot

try:
    from skoolkit.ccmiosimulator import CCMIOSimulator
except ImportError:
    CCMIOSimulator = None
from skoolkit.cmiosimulator import CMIOSimulator

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

# The original's addresses (docs/research/zx-driller.md).
#
# Start-up: the loader jumps to START; the protection (PROTECT_*) asks for
# a word from the manual, picked from its table by a random index, and
# only once it's typed does it plant PUSH IX over the JR $ at the redraw's
# first two bytes (REDRAW); then the control menu (MENU) waits for ENTER,
# and the game enters its main loop (MAIN_LOOP).
START = 0x97A4
PROTECT_ENTRY = 0xCC6F    # PUSH IY: IY is the word's table entry
PROTECT_KEYS = 0xCC7E     # the key-reading loop
MENU = 0xC9C6
MENU_DONE = 0x97EB
MAIN_LOOP = 0x9825
# The redraw and the camera.
REDRAW = 0x6B12
REDRAW_SORT = 0x6B5C      # CALL the sort: the objects are projected
REDRAW_SORTED = 0x6B5F
REDRAW_DRAW = 0x6B72      # CALL the draw
REDRAW_END = 0x6B75       # the draw's done; the redraw pops and returns
GAME_FLAGS = 0x8920       # bit 2: moved or turned, so re-project
AREA_ID = 0x8862
ENTRANCE_ID = 0x8911
LOAD_AREA = 0xBE18
GO_TO_ENTRANCE = 0x9D1C   # loads the area (LOAD_AREA) first
CAMERA_POS = 0x8762       # x, y, z: 16-bit world units
CAMERA_ANGLES = 0x876C    # pitch, yaw, roll: 5-degree units
AREA_FLAGS = 0x889F       # non-zero: the draw clears the buffer first
N_DRAWN = 0x8918          # objects in the draw list
BUFFER = 0x5CBC           # the view: 26 bytes a row, 105 rows
VIEW_W, VIEW_H = 208, 104  # the rows the copy shows: 0-103
ROW_BYTES = 26
BUFFER_ROWS = 105
SENTINEL = 0x0008         # a return address nothing here reaches


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


def view_image(view, scale=1):
    """A view's bytes (26 a row, bit 7 left) as an image, ink white."""
    rows = len(view) // ROW_BYTES
    im = Image.new("1", (VIEW_W, rows))
    px = im.load()
    for y in range(rows):
        for c in range(ROW_BYTES):
            b = view[y * ROW_BYTES + c]
            for bit in range(8):
                px[c * 8 + bit, y] = 1 if b & (0x80 >> bit) else 0
    if scale != 1:
        im = im.resize((VIEW_W * scale, rows * scale), Image.NEAREST)
    return im


class Spectrum:
    """A 48K Spectrum, from a snapshot, with its keyboard and Kempston port
    driven by the script and the beeper's writes optionally logged
    (portlog: a list it appends (T-states, 'FE', value) to).

    contended: simulate the 48K's memory and I/O contention (SkoolKit's
    CMIO simulator), for timings as the machine runs them."""

    def __init__(self, snap, exec_map=None, portlog=None, contended=False):
        snapshot = Snapshot.get(snap)
        if contended:
            cls = CCMIOSimulator or CMIOSimulator
        else:
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
        self.interrupts = 1

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

    def write_port(self, registers, port, value, offset=0):
        if port & 1 == 0:
            self.border = value & 7
            self.outfe = value
            if self.portlog is not None:
                self.portlog.append((registers[T], "FE", value))

    def run_tstates(self, n, stop=None):
        """Run n T-states, or until PC is stop; return PC."""
        regs = self.sim.registers
        end = regs[T] + n
        self.sim.trace(regs[PC], stop, 0, end, self.interrupts, None, self.exec_map, None, None, None)
        return regs[PC]

    def call(self, addr, stops=(), limit=None):
        """Call addr with SENTINEL as its return address, on the current
        stack. Returns the T-states to reach each of stops (in order) and
        then the return."""
        m, r = self.mem, self.regs
        sp = (r[SP] - 2) & 0xFFFF
        m[sp], m[sp + 1] = SENTINEL & 0xFF, SENTINEL >> 8
        r[SP], r[PC] = sp, addr
        limit = limit or 400 * self.frame
        t0 = r[T]
        times = []
        for stop in (*stops, SENTINEL):
            pc = self.run_tstates(limit - (r[T] - t0), stop=stop)
            if pc != stop:
                raise RuntimeError(f"${addr:04X}: never reached ${stop:04X} (PC ${pc:04X})")
            times.append(r[T] - t0)
        return times

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

    def peek16(self, addr):
        return self.mem[addr] | self.mem[addr + 1] << 8

    def poke16(self, addr, v):
        self.mem[addr], self.mem[addr + 1] = v & 0xFF, (v >> 8) & 0xFF


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


def camera(spec):
    """The camera as the original holds it: x, y, z, pitch, yaw, roll."""
    pos = [spec.peek16(CAMERA_POS + 2 * i) for i in range(3)]
    return pos + [spec.mem[CAMERA_ANGLES + i] for i in range(3)]


def render_view(snap, area, entrance=0, cam=None, contended=True, interrupts=True, exec_map=None):
    """Draw one view with the original's own code, from the in-play
    snapshot (make zx):

    - area AREA_ID and, if entrance is non-zero, the camera at that
      entrance (GO_TO_ENTRANCE, which loads the area); else the area alone
      (LOAD_AREA) and the camera as it was;
    - cam (x, y, z, pitch, yaw, roll), if given, poked over that;
    - the buffer zeroed, so whatever the draw leaves is deterministic (the
      areas whose flags are 0 aren't cleared by the draw: AREA_FLAGS);
    - GAME_FLAGS bit 2 set, as a move or turn sets it, and REDRAW called
      with a sentinel return address.

    contended and interrupts: time it as the 48K runs it, with its memory
    contention and the game's 50Hz interrupt; without them the T-states
    are the instructions' own.

    Returns a dict: the view (VIEW_H rows of ROW_BYTES), the buffer's
    last row (drawn, never shown), the camera, the redraw's T-states in
    all and to each stage, and the objects in the draw list."""
    spec = Spectrum(snap, exec_map=exec_map, contended=contended)
    spec.interrupts = 1 if interrupts else 0
    m = spec.mem
    m[AREA_ID] = area
    if entrance:
        m[ENTRANCE_ID] = entrance
        spec.call(GO_TO_ENTRANCE)
    else:
        spec.call(LOAD_AREA)
    if cam is not None:
        for i in range(3):
            spec.poke16(CAMERA_POS + 2 * i, cam[i])
            m[CAMERA_ANGLES + i] = cam[3 + i]
    for a in range(BUFFER, BUFFER + ROW_BYTES * BUFFER_ROWS):
        m[a] = 0
    m[GAME_FLAGS] |= 4
    t_sort, t_sorted, t_draw, t_end, t_ret = spec.call(
        REDRAW, stops=(REDRAW_SORT, REDRAW_SORTED, REDRAW_DRAW, REDRAW_END))
    buf = bytes(m[BUFFER:BUFFER + ROW_BYTES * BUFFER_ROWS])
    return {
        "area": area,
        "entrance": entrance,
        "camera": camera(spec),
        "clears": m[AREA_FLAGS] != 0,
        "drawn": m[N_DRAWN],
        "tstates": t_ret,
        "stages": {"project": t_sort, "sort": t_sorted - t_sort,
                   "draw": t_end - t_draw, "other": t_ret - t_end + t_draw - t_sorted},
        "view": buf[:ROW_BYTES * VIEW_H],
        "last_row": buf[ROW_BYTES * VIEW_H:],
    }


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


def run_passes(snap, path):
    """--passes: a scenario on the original alone."""
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from logic import scenario
    from logic.oracle import Original
    from logic.state import State
    orig = Original(snap)
    n = 0
    for st in scenario.load(path):
        if st.kind == "expect":
            continue
        orig.begin(tick=getattr(st, "tick", False))
        if st.kind == "poke":
            orig.poke(st.addr, st.values)
            continue
        if st.kind == "fcl":
            s = State(orig.fcl(st.code, shot=st.shot))
        else:
            s = State(orig.run_pass(st.keys, st.tick))
            n += 1
        print(f"{st.line} {' '.join(getattr(st, 'keys', ())) or st.kind}: pos {s.PlayerX},{s.PlayerY},{s.PlayerZ} "
              f"angles {s.Pitch},{s.Yaw},{s.Roll} area {s.AreaId} level {s.ExtLevel} jet {s.InJet} "
              f"flags {s.GameFlags:02X}{s.GameFlags2:02X} collided {s.Collided} sound {s.Sound} over {s.GameOver}")
        if s.GameOver:
            break
    print(f"{n} passes")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", nargs="?")
    ap.add_argument("prefix", nargs="?", default="build/zx/")
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--map", help="write the addresses executed, one per line, to FILE")
    ap.add_argument("--boot", action="store_true",
                    help="the snapshot is the tape just loaded: pass the protection and the menu first")
    ap.add_argument("--view", metavar="AREA:ENTRANCE", help="draw a view with the original's redraw")
    ap.add_argument("--camera", metavar="X,Y,Z,PITCH,YAW,ROLL", help="with --view: the camera to draw from")
    ap.add_argument("--passes", metavar="SCENARIO", help="run a scenario's passes on the original")
    args = ap.parse_args()
    exec_map = set() if args.map else None
    if args.passes:
        return run_passes(args.snap, args.passes)
    if args.view:
        prefix = args.script or args.prefix  # the one positional is the prefix here
        area, _, entrance = args.view.partition(":")
        cam = [parse_num(v) for v in args.camera.split(",")] if args.camera else None
        v = render_view(args.snap, parse_num(area), parse_num(entrance or "0"), cam, exec_map=exec_map)
        name = f"{prefix}a{v['area']}_e{v['entrance']}"
        view_image(v["view"]).save(name + ".png")
        with open(name + ".bin", "wb") as f:
            f.write(v["view"])
        print(name, "camera", v["camera"], "T-states", v["tstates"], v["stages"], "drawn", v["drawn"])
    else:
        if not args.script:
            ap.error("a script, or --view")
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
