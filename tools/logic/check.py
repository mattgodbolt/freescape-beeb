#!/usr/bin/env python3
"""The player logic checked pass by pass against the original.

    .venv/bin/python -I tools/logic/check.py [--snap build/zx/driller.z80] [SCENARIO ...]
    .venv/bin/python -I tools/logic/check.py --fuzz N [--seed S] [--passes P] [--keep DIR] [--fuzz-only]
    .venv/bin/python -I tools/logic/check.py --arith N

Each scenario (tests/logic/*.txt; tools/logic/scenario.py has the format)
runs on the original (tools/logic/oracle.py) and on the transcription
(tools/logic/passes.py) from the same in-play snapshot. After every step
every variable in tools/logic/state.py and the whole database must be the
same on both sides; the "sync" variables are taken from the original as
each pass starts.

--fuzz runs N random walks: a random entrance, then random movement keys,
one to three held a pass, and now and then a minute. A failing walk is
written to DIR (tests/logic/fuzz-<seed>.txt by default) as a scenario.

Exits non-zero if anything differs.
"""
import argparse
import collections
import glob
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logic import fcl, scenario  # noqa: E402
from logic.hooks import Hooks  # noqa: E402
from logic.move import Freeze  # noqa: E402
from logic.oracle import Original, SCRIPT, Waiting  # noqa: E402
from logic.passes import run_pass  # noqa: E402
from logic.state import State, differences  # noqa: E402


class OracleHooks(Hooks):
    """The hooks, answering from the original's renderer: which objects
    the last redraw drew."""

    def __init__(self, drawn):
        super().__init__()
        self.drawn = drawn

    def undraw(self, s, obj_id):
        super().undraw(s, obj_id)
        return obj_id in self.drawn


def fmt(v):
    if isinstance(v, bytes):
        return v.hex(" ")
    return f"{v} (${v:X})"


class Mismatch(Exception):
    pass


REDRAWN = [0]   # passes in which the FCL's REDRAW ran the renderer
FROZE = [0]     # scenarios that end where the original hangs
SEEN = collections.Counter()   # what the original did in the passes compared


def note(before, after, keys):
    """Count what a pass did, from the original's state before and after."""
    b, a = State(before), State(after)
    if (a.PlayerX, a.PlayerY, a.PlayerZ) != (b.PlayerX, b.PlayerY, b.PlayerZ):
        SEEN["moved"] += 1
    if (a.Pitch, a.Yaw, a.Roll) != (b.Pitch, b.Yaw, b.Roll):
        SEEN["turned"] += 1
    if a.Blocked:
        SEEN["stopped by an object"] += 1
    if a.Sound == 4:
        SEEN["stepped up"] += 1
    if a.Sound == 3:
        SEEN["fell"] += 1
    if a.GameOver == 4:
        SEEN["fell too far"] += 1
    if a.AreaId != b.AreaId:
        SEEN["changed area"] += 1
        if a.EntranceId == 0:
            SEEN["crossed the edge"] += 1
    if a.Collided:
        SEEN["collided"] += 1
    if a.InJet:
        SEEN["in the jet"] += 1
    if a.ExtLevel != b.ExtLevel:
        SEEN["probe level changed"] += 1
    if a.ShootMode:
        SEEN["shooting mode"] += 1


def run(steps, snap, verbose=False):
    """Run steps on both sides; returns the passes compared. Raises
    Mismatch at the first difference."""
    orig = Original(snap)
    s = State(orig.memory())
    last = orig.memory()   # the original as the last step left it (a pass: at $982B)
    passes = 0
    over = False
    for st in steps:
        if over and st.kind != "expect":
            break   # the game is over: the original goes to its end ($9AB7)
        if st.kind == "expect":
            want = st.value
            got_o = getattr(State(last), st.name)
            got_p = getattr(s, st.name)
            if got_o != want or got_p != want:
                raise Mismatch(f"{st.line}: expected {st.name} = {want}: original {fmt(got_o)}, "
                               f"transcription {fmt(got_p)}")
            continue
        start = orig.begin(tick=getattr(st, "tick", False))
        s.sync_from(start)
        if st.kind == "poke":
            orig.poke(st.addr, st.values)
            for i, v in enumerate(st.values):
                s.mem[st.addr + i] = v & 0xFF
            last = orig.memory()
            continue
        hooks = OracleHooks(orig.drawn())
        if st.kind == "fcl":
            after = orig.fcl(st.code)
            s.mem[SCRIPT:SCRIPT + len(st.code)] = bytes(st.code)
            s.ShotFlag = 0
            fcl.run(s, SCRIPT, len(st.code), hooks)
        else:
            try:
                alive = run_pass(s, st.keys, st.tick, hooks)
            except Freeze as e:
                # The original hangs here too, or it's a difference.
                try:
                    orig.run_pass(st.keys, st.tick)
                except Waiting:
                    FROZE[0] += 1
                    passes += 1
                    break
                raise Mismatch(f"{st.line}: the transcription hangs ({e}); the original doesn't")
            after = orig.run_pass(st.keys, st.tick, ends=alive == "over")
            passes += 1
            note(start, after, st.keys)
        last = after
        o = State(after)
        if any(name == "redraw" for name, _ in hooks.log):
            # The FCL's REDRAW ran the renderer, the copy and the sensors
            # ($6B12, $9841) inside the pass: their outputs are the
            # original's, as at the start of a pass.
            s.sync_from(after)
            REDRAWN[0] += 1
        diffs = differences(o.snapshot(), s.snapshot())
        if verbose:
            print(f"{st.line} {' '.join(getattr(st, 'keys', ())) or st.kind}: "
                  f"pos {s.PlayerX},{s.PlayerY},{s.PlayerZ} angles {s.Pitch},{s.Yaw},{s.Roll} "
                  f"area {s.AreaId} flags {s.GameFlags:02X}{s.GameFlags2:02X}")
        if diffs:
            lines = [f"{st.line}: {len(diffs)} differ, at pass {passes} (original, transcription):"]
            lines += [f"  {name}: {fmt(a)}  {fmt(b)}" for name, a, b in diffs[:40]]
            lines.append("  calls: " + ", ".join(f"{n}{a}" for n, a in hooks.log[:20]))
            raise Mismatch("\n".join(lines))
        if st.kind == "pass" and (alive == "over" or not alive):
            over = True
    return passes


# --- fuzzing --------------------------------------------------------------

MOVE_KEYS = "O K Q W P L N M R F U A Z S X B SPACE".split()
WEIGHTS = [8, 4, 3, 3, 2, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 0.3, 0.3]


def entrances(snap):
    """Every (area, entrance) of the database, from the snapshot."""
    s = State(Original(snap).memory())
    from logic.area import word
    m = s.mem
    out = []
    base, table = word(m, 0x8912), word(m, 0x8914)
    for i in range(m[0xCF3E]):
        a = base + word(m, table + 2 * i)
        q = a + 25
        for _ in range(m[a + 1]):
            if m[q] & 0x0F == 0 and m[q + 7]:
                out.append((m[a + 2], m[q + 7]))
            q += m[q + 8]
    return out


def walk(rng, ents, n):
    area, ent = rng.choice(ents)
    lines = [f"goto {area} {ent}"]
    if rng.random() < 0.25:
        lines.append("fcl 15")          # SWAPJET: the jet
    for _ in range(n):
        if rng.random() < 0.02:
            lines.append("tick")
            continue
        k = rng.choices(MOVE_KEYS, WEIGHTS, k=rng.choice([1, 1, 1, 2, 2, 3]))
        lines.append(" ".join(dict.fromkeys(k)))
    return lines


def fuzz(snap, count, seed, n, keep):
    ents = entrances(snap)
    bad = 0
    total = 0
    for i in range(count):
        rng = random.Random(seed + i)
        lines = walk(rng, ents, n)
        text = "\n".join(lines) + "\n"
        try:
            total += run(scenario.parse(text, f"fuzz-{seed + i}"), snap)
        except Mismatch as e:
            bad += 1
            path = os.path.join(keep, f"fuzz-{seed + i}.txt")
            if os.path.exists(path):
                print(f"seed {seed + i}: differs ({path} is already kept)\n{e}")
                continue
            with open(path, "w") as f:
                f.write(f"# Found by tools/logic/check.py --fuzz, seed {seed + i}.\n" + text)
            print(f"seed {seed + i}: kept as {path}\n{e}")
    print(f"fuzz: {count} walks, {total} passes compared, {bad} differ")
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("scenarios", nargs="*")
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--fuzz", type=int, metavar="N")
    ap.add_argument("--fuzz-only", action="store_true", help="fuzz without running tests/logic/")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--passes", type=int, default=60)
    ap.add_argument("--keep", default="tests/logic")
    ap.add_argument("--arith", type=int, metavar="N", help="check the multiplies and divide too")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    bad = 0
    if args.arith:
        from logic.arith import _check
        b = _check(args.snap, args.arith)
        print(f"arith: {args.arith} cases of each routine, {b} differ")
        bad += b
    paths = args.scenarios
    if not paths and not args.fuzz_only:
        paths = sorted(glob.glob("tests/logic/*.txt"))
    total = 0
    for p in paths:
        try:
            n = run(scenario.load(p), args.snap, args.verbose)
            total += n
            print(f"{p}: {n} passes, the same")
        except Mismatch as e:
            bad += 1
            print(e)
    if paths:
        print(f"scenarios: {len(paths)}, {total} passes compared, {bad} differ")
    if args.fuzz:
        bad += fuzz(args.snap, args.fuzz, args.seed, args.passes, args.keep)
    if SEEN:
        print("the original, in those passes: " + ", ".join(f"{k} {v}" for k, v in sorted(SEEN.items())))
    if REDRAWN[0]:
        print(f"{REDRAWN[0]} steps ran the FCL's REDRAW: the renderer's outputs taken from the original")
    if FROZE[0]:
        print(f"{FROZE[0]} ended where the original hangs, and the transcription knew it would")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
