#!/usr/bin/env python3
"""What the 6502 logic must do, pass by pass: the transcription's traces,
for tools/logiccheck.mjs.

    .venv/bin/python -I tools/logictrace.py --snap build/zx/driller.z80 --out FILE
        [--fuzz N --seed S --passes P] [--arith N] [SCENARIO ...]

Runs tools/logic/ (the transcription, itself checked against the original
by make logic) with decision 18's fix on (move.FIX_CORNER), which the port
makes, on every scenario (tests/logic/*.txt by default) and on N random
walks from random entrances (tools/logic/check.py's), each from the
in-play snapshot as make logic runs it: the 6502's start is the port's
(decision 48, tools/logic/state.py's port_start), so each run's first steps
poke the original's sizes back (original_sizes). Writes FILE, JSON:

    layout   the variables compared (tools/logic/state.py's), their
             addresses in the original, and the database's
    start    the compared bytes as each run starts, the port's start:
             [address, hex]
    runs     each run's steps: a pass's keys as the ZX's half-rows (the
             BBC's bitmap, src/input.6502), and whether a minute ends
             first; a poke; an FCL script; then the compared bytes that
             changed, as [address, value]; "freeze" where the original
             would hang
    cross, mul  the arithmetic's cases, with the transcription's answers

The hooks are tools/logic/hooks.py's defaults, which the 6502's are too
(src/logic/hooks.6502). Nothing of the original's state is compared but
the logic's variables and the database, as make logic compares them.
"""
import argparse
import glob
import json
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from logic import arith, end as lend, fcl, move, scenario  # noqa: E402
from logic.check import entrances, walk  # noqa: E402
from logic.hooks import Hooks  # noqa: E402
from logic.oracle import Original, SCRIPT  # noqa: E402
from logic.passes import KEYS, run_pass  # noqa: E402
from logic.state import VARS, State, database, original_sizes, port_start  # noqa: E402
from mklogicdata import ZXV_ORG, ZXV_END  # noqa: E402


def size_of(size):
    return size if isinstance(size, int) else size[1]


def regions(mem):
    """The compared addresses: every variable's bytes, the whole of the
    original's block of them that the 6502 keeps (tools/mklogicdata.py's
    mirror), and the database's."""
    out = list(range(ZXV_ORG, ZXV_END))
    for _, a, sz, kind, _ in VARS:
        if kind != "clock":
            out.extend(range(a, a + size_of(sz)))
    lo, hi = database(mem)
    out.extend(range(lo, hi))
    return sorted(set(out))


def rows(keys):
    """Keys held, by the ZX's names, as the eight half-rows' bits."""
    r = [0] * 8
    for k in keys:
        if k in KEYS:
            row, bit = KEYS[k]
            r[row] |= 1 << bit
    return r


def changes(before, after, where):
    return [[a, after[a]] for a in where if before[a] != after[a]]


def from_original(steps, snap_mem, name):
    """A run's steps after the pokes that put the original's start sizes
    back, from the port's start (original_sizes)."""
    return [scenario.Step("poke", f"{name}: the original's sizes", addr=a, values=v)
            for a, v in original_sizes(snap_mem)] + steps


def run(steps, start_mem, where):
    """A run's steps, as the 6502 is to take them, from start_mem, with what
    each changes."""
    s = State(start_mem)
    out = []
    over = ending = False
    for st in steps:
        if st.kind in ("expect", "sensors"):
            continue        # (checked against the original by make logic; the sensors' shots are the disc's)
        if st.kind == "end":
            if not over:
                break       # (a sensors step's shots ended it, which are the disc's)
            if not ending:
                # the input's next pass finds the game over
                before = bytes(s.mem)
                rec = {"line": st.line, "keys": rows(()), "names": [], "tick": False,
                       "jet": bool(s.InJet), "shoot": bool(s.ShootMode)}
                rec["result"] = 2 if run_pass(s, (), False, Hooks()) == "over" else 1
                rec["changes"] = changes(before, s.mem, where)
                out.append(rec)
            before = bytes(s.mem)
            lend.end(s, Hooks())
            out.append({"line": st.line, "end": True, "changes": changes(before, s.mem, where)})
            before = bytes(s.mem)
            keys = () if st.demo else ("ENTER",)
            lend.restart(s, Hooks(), keys, demo=st.demo)
            out.append({"line": st.line, "restart": True, "demo": st.demo, "keys": rows(keys),
                        "changes": changes(before, s.mem, where)})
            over = ending = False
            continue
        if over:
            break           # the game is over: the original goes to its end
        before = bytes(s.mem)
        rec = {"line": st.line}
        hooks = Hooks()
        if st.kind == "poke":
            rec["poke"] = [st.addr, list(v & 0xFF for v in st.values)]
            for i, v in enumerate(st.values):
                s.mem[st.addr + i] = v & 0xFF
        elif st.kind == "fcl":
            rec["fcl"] = list(st.code)
            rec["shot"] = bool(st.shot)
            s.mem[SCRIPT:SCRIPT + len(st.code)] = bytes(st.code)
            s.ShotFlag = 1 if st.shot else 0
            fcl.run(s, SCRIPT, len(st.code), hooks)
        else:
            rec["keys"] = rows(st.keys)
            rec["names"] = list(st.keys)
            rec["tick"] = bool(st.tick)
            rec["jet"] = bool(s.InJet)
            rec["shoot"] = bool(s.ShootMode)
            try:
                alive = run_pass(s, st.keys, st.tick, hooks)
            except move.Freeze:
                rec["freeze"] = True
                out.append(rec)
                break
            rec["result"] = {"over": 2, "new": 3}.get(alive, 1)
            if alive == "over" or not alive:
                over = True
                ending = alive == "over"
        rec["changes"] = changes(before, s.mem, where)
        out.append(rec)
    return out


def arith_cases(n, seed):
    rng = random.Random(seed)
    edge = [0, 1, 2, 0x7FFF, 0x8000, 0x8001, 0xFFFF, 0xFFFE, 64, 0xFFC0, 255, 256]

    def word():
        return rng.choice([rng.choice(edge), rng.randrange(0x10000),
                           rng.randrange(-300, 300) & 0xFFFF, rng.randrange(-1100, 1100) & 0xFFFF])

    cross = []
    for i in range(n):
        if i % 3 == 0:
            # as the walk has them: a distance to a boundary, a delta, the main delta
            t = rng.randrange(-1100, 1100) & 0xFFFF
            d = rng.randrange(-1100, 1100) & 0xFFFF
            dm = rng.choice([rng.randrange(-1100, 1100), rng.randrange(-260, 260)]) & 0xFFFF
        else:
            t, d, dm = word(), word(), word()
        if i % 17 == 0:
            dm = 0
        if i % 19 == 0:
            dm = 0x8000
        start = rng.randrange(0x10000)
        q, _ = arith.div32(arith.mul_hl_de(t, d), dm)
        cross.append([t, d, dm, start, (start + q) & 0xFFFF])
    mul = []
    for i in range(n):
        a = rng.choice([0, 1, 0x7F, 0x80, 0x81, 0xFF, 64, 0xC0, rng.randrange(256)])
        hl = word()
        p = arith.mul_a_hl(a, hl)
        mul.append([a, hl, p, arith.shift6(p)])
    return cross, mul


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*")
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fuzz", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--passes", type=int, default=80)
    ap.add_argument("--arith", type=int, default=0)
    ap.add_argument("--no-scenarios", action="store_true")
    args = ap.parse_args()
    move.FIX_CORNER = True      # decision 18: the port's logic
    snap_mem = Original(args.snap).memory()
    mem = port_start(snap_mem)          # decision 48: the 6502's start
    where = regions(mem)
    lo, hi = database(mem)
    paths = args.scenarios or ([] if args.no_scenarios else sorted(glob.glob("tests/logic/*.txt")))
    runs = []
    for p in paths:
        runs.append({"name": p, "steps": run(from_original(scenario.load(p), snap_mem, p), mem, where)})
    if args.fuzz:
        ents = entrances(args.snap)
        for i in range(args.fuzz):
            rng = random.Random(args.seed + i)
            text = "\n".join(walk(rng, ents, args.passes)) + "\n"
            name = f"fuzz-{args.seed + i}"
            steps = from_original(scenario.parse(text, name), snap_mem, name)
            runs.append({"name": name, "steps": run(steps, mem, where)})
    cross, mul = arith_cases(args.arith, args.seed)
    vars_ = [{"name": n, "addr": a, "size": size_of(sz), "kind": k} for n, a, sz, k, _ in VARS if k != "clock"]
    out = {
        "layout": {"vars": vars_, "database": [lo, hi]},
        "start": [[a, mem[a]] for a in where],
        "runs": runs,
        "cross": cross,
        "mul": mul,
    }
    with open(args.out, "w") as f:
        json.dump(out, f, separators=(",", ":"))
    steps = sum(len(r["steps"]) for r in runs)
    print(f"logictrace: {len(runs)} runs, {steps} steps, {len(cross)} + {len(mul)} arithmetic cases")


if __name__ == "__main__":
    main()
