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

--fix-corner runs the transcription with decision 18's fix
(tools/logic/move.py's FIX_CORNER), to see what the fix changes against
the original: only walks that meet the corner bug should differ.

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
from logic import end as lend, fcl, info as linfo, move, scenario  # noqa: E402
from logic.hooks import Hooks  # noqa: E402
from logic.move import Freeze  # noqa: E402
from logic.oracle import Original, SCRIPT, Waiting  # noqa: E402
from logic.passes import run_pass, waiting  # noqa: E402
from logic.state import State, differences  # noqa: E402
from logic import view as lview  # noqa: E402
from logic import sensors as lsensors  # noqa: E402


class OracleHooks(Hooks):
    """The hooks, answering from the original's renderer: which objects
    the last redraw drew; and the shot's pick from the BBC's view of the
    state the pass began with (tools/logic/view.py, decision 131), which the
    original's own pick must agree with."""

    def __init__(self, drawn, after=None, start=None):
        super().__init__()
        self.drawn = drawn
        self.after = after
        self.start = start

    def undraw(self, s, obj_id):
        super().undraw(s, obj_id)
        return obj_id in self.drawn

    def shot(self, s):
        super().shot(s)
        hit = lview.shot(s, self.start)
        if hit is not None:
            s.Collided = hit
            SHOTS["hit"] += 1
        else:
            SHOTS["missed"] += 1

    def redraw(self, s):
        """A rig's redraw inside its pass runs the sensors' line of sight
        ($9841), whose walk leaves Collided for the pass's events: the
        original's, from after the pass (nothing after the redraw writes it)."""
        super().redraw(s)
        if self.after is not None:
            s.Collided = self.after[0x8A69]


def expected(s, name):
    """A variable for an expect: Name, or Name[i] for one of its bytes; a
    run of bytes reads as a little-endian number."""
    index = None
    if name.endswith("]"):
        name, _, i = name[:-1].partition("[")
        index = int(i, 0)
    v = getattr(s, name)
    if index is not None:
        return v[index]
    if isinstance(v, bytes):
        return int.from_bytes(v, "little")
    return v


def fmt(v):
    if isinstance(v, bytes):
        return v.hex(" ")
    return f"{v} (${v:X})"


class Mismatch(Exception):
    pass


REDRAWN = [0]   # passes in which the FCL's REDRAW ran the renderer
FROZE = [0]     # scenarios that end where the original hangs
SEEN = collections.Counter()   # what the original did in the passes compared
SHOTS = collections.Counter()  # the shots' picks: hit or missed


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


SENSORS = collections.Counter()   # the sensors: frames run, shots, redraws' tests compared


def sight_check(st, s, projected, redrawn):
    """The redraw after a pass (tools/logic/sensors.py's redraw, from the
    BBC's frame of the state after it), against the original's own: its
    projection's list (projected, as $9841 begins) and its test's (redrawn,
    after). Each list's count, and each entry's id, interval, counter and
    state, but its point (each screen's own). Whether a sensor in range is
    on the screen (state 1 or 2) is the renderer's, which differ by a pixel
    at the view's edges (decision 132): an entry whose projected states
    differ so is counted, not compared after its test, and nor is the
    Collided the test leaves. On a copy: the next pass takes the original's."""
    if projected is None or not lsensors.any_sensors(s):
        return
    t = s.copy()
    view_of, shot = lview.frame(t)
    if t.GameFlags & 0x04:
        lsensors.project(t, view_of)
    pre = bytes(t.mem[lsensors.FOUND_N:lsensors.FIRING])
    lsensors.sight(t, shot)
    if t.AreaChanged:
        fcl.screen_update(t, Hooks())   # ($9841's next: the counters back to 2)
    SENSORS["tests"] += 1
    E, F, N = lsensors.ENTRY, lsensors.FOUND, lsensors.FOUND_N
    bad = []
    view = set()                        # entries whose projections differ by the screen
    if pre[0] != projected[N]:
        bad.append(f"the count projected: {projected[N]} {pre[0]}")
    for i in range(min(pre[0], lsensors.ENTRIES)):
        a = F + E * i
        for k in range(4):
            o, p = projected[a + k], pre[a - N + k]
            if o == p:
                continue
            if k == 3 and o and p:
                view.add(i)
            else:
                bad.append(f"${a + k:04X} projected: {o} {p}")
    o, m = redrawn, t.mem
    for base in (F, lsensors.FIRING):
        for i in range(lsensors.ENTRIES):
            for k in range(4):
                if k == 3 and i in view:
                    continue
                a = base + E * i + k
                if m[a] != o[a]:
                    bad.append(f"${a:04X}: {o[a]} {m[a]}")
    if m[lsensors.FIRING_N] != o[lsensors.FIRING_N]:
        bad.append(f"the count firing: {o[lsensors.FIRING_N]} {m[lsensors.FIRING_N]}")
    if view:
        SENSORS["on the screen in one view only"] += len(view)
    elif t.Collided != o[0x8A69]:
        bad.append(f"Collided: {o[0x8A69]} {t.Collided}")
    for i in range(pre[0]):
        SENSORS[f"state {projected[F + E * i + 3]}"] += 1
    if bad:
        raise Mismatch(f"{st.line}: the redraw's sensors differ (original, transcription): " + ", ".join(bad))


ENDS = collections.Counter()   # the ends and new games compared, by how
INFO = collections.Counter()   # the information screens compared, by the key that answered


# What the logic's end and new game set of the variables the renderer's
# side writes too: kept when the rest are taken from the original.
KEPT = ("Energy", "Shield", "GameOver", "Sound")


def compare_drawn(st, s, mem, what):
    """After a redraw the renderer's outputs are the original's (as after
    the FCL's REDRAW), but what the logic set of them (KEPT); then every
    variable and the database must agree."""
    kept = {k: getattr(s, k) for k in KEPT}
    s.sync_from(mem)
    for k, v in kept.items():
        setattr(s, k, v)
    diffs = differences(State(mem).snapshot(), s.snapshot())
    if diffs:
        lines = [f"{st.line}: {len(diffs)} differ, {what} (original, transcription):"]
        lines += [f"  {name}: {fmt(a)}  {fmt(b)}" for name, a, b in diffs[:40]]
        raise Mismatch("\n".join(lines))


def run(steps, snap, verbose=False):
    """Run steps on both sides; returns the passes compared. Raises
    Mismatch at the first difference."""
    orig = Original(snap)
    s = State(orig.memory())
    last = orig.memory()   # the original as the last step left it (a pass: at $982B)
    passes = 0
    over = False
    ending = False     # the original is at its end ($9AB7)
    for st in steps:
        if st.kind == "end":
            # The end: the input's next pass finds the game over, unless the
            # last did; the scene; the wait answered; the new game.
            if not (over or s.GameOver):      # (a sensors step's shots may end it)
                raise Mismatch(f"{st.line}: an end with the game going on")
            if not ending:
                s.sync_from(orig.begin())
                if run_pass(s, (), False, Hooks()) != "over":
                    raise Mismatch(f"{st.line}: the transcription's input didn't find the game over")
                orig.run_pass((), False, ends=True)
            hooks = Hooks()
            lend.end(s, hooks)
            scene, restarted = orig.end(demo=st.demo)
            compare_drawn(st, s, scene, "at the end's scene")
            lend.restart(s, hooks, demo=st.demo)
            compare_drawn(st, s, restarted, "after the new game")
            ENDS[f"GameOver {State(scene).GameOver}" + (", the demo next" if st.demo else "")] += 1
            last = restarted
            over = ending = False
            continue
        if over and st.kind != "expect":
            break   # the game is over: the original goes to its end ($9AB7)
        if st.kind == "expect":
            want = st.value
            got_o = expected(State(last), st.name)
            got_p = expected(s, st.name)
            if got_o != want or got_p != want:
                raise Mismatch(f"{st.line}: expected {st.name} = {want}: original {fmt(got_o)}, "
                               f"transcription {fmt(got_p)}")
            continue
        if st.kind == "sensors":
            # frames of the interrupt's sensors, between passes: their shots
            # (tools/logic/sensors.py's tick) from the lists the original's
            # redraw left, which the state takes first
            s.sync_from(orig.memory())
            after = orig.sensors(st.n)
            hooks = Hooks()
            waiting(s, hooks)
            for _ in range(st.n):
                lsensors.tick(s, hooks)
            SENSORS["frames"] += st.n
            SENSORS["shots"] += sum(1 for n, a in hooks.log if n == "sound" and a == (2,))
            last = after
            diffs = differences(State(after).snapshot(), s.snapshot())
            if diffs:
                lines = [f"{st.line}: {len(diffs)} differ after {st.n} frames of the sensors (original, transcription):"]
                lines += [f"  {name}: {fmt(a)}  {fmt(b)}" for name, a, b in diffs[:40]]
                raise Mismatch("\n".join(lines))
            continue
        start = orig.begin(tick=getattr(st, "tick", False))
        s.sync_from(start)
        if st.kind == "poke":
            orig.poke(st.addr, st.values)
            for i, v in enumerate(st.values):
                s.mem[st.addr + i] = v & 0xFF
            last = orig.memory()
            continue
        orig_drawn = orig.drawn()
        hooks = OracleHooks(orig_drawn, start=s.copy())
        if st.kind == "fcl":
            after = orig.fcl(st.code, shot=st.shot)
            s.mem[SCRIPT:SCRIPT + len(st.code)] = bytes(st.code)
            s.ShotFlag = 1 if st.shot else 0
            fcl.run(s, SCRIPT, len(st.code), hooks)
        else:
            s0 = s.copy()
            info_keys = getattr(st, "info_keys", None)
            try:
                alive = run_pass(s, st.keys, st.tick, hooks, info_keys=info_keys)
            except Freeze as e:
                # The original hangs here too, or it's a difference.
                try:
                    orig.run_pass(st.keys, st.tick)
                except Waiting:
                    FROZE[0] += 1
                    passes += 1
                    break
                raise Mismatch(f"{st.line}: the transcription hangs ({e}); the original doesn't")
            after = orig.run_pass(st.keys, st.tick, ends=alive == "over", info_keys=info_keys)
            if info_keys is not None:
                # the information screen's text, as the original printed it
                want = linfo.lines(State(orig.info_mem))
                if want != linfo.lines(s):
                    raise Mismatch(f"{st.line}: the information screen's text differs:\n  " +
                                   "\n  ".join(f"{a!r}  {b!r}" for a, b in zip(want, linfo.lines(s)) if a != b))
                INFO[" ".join(info_keys)] += 1
            if alive == "new" or (alive != "over" and orig.new_game):
                # a new game after the pass (the demo's end, or a key in it):
                # the original's from the main loop's top after it
                if alive != "new" or not orig.new_game:
                    raise Mismatch(f"{st.line}: a new game on one side only")
                passes += 1
                compare_drawn(st, s, after, "after the new game")
                ENDS["the demo's new games"] += 1
                last = after
                continue
            if any(n == "message" for n, _ in hooks.log) and any(n == "redraw" for n, _ in hooks.log):
                # a rig's redraw: the pass again, with the original's Collided
                s = s0
                hooks = OracleHooks(orig_drawn, after, start=s0.copy())
                alive = run_pass(s, st.keys, st.tick, hooks)
            passes += 1
            note(start, after, st.keys)
            if alive != "over" and not any(n == "redraw" for n, _ in hooks.log):
                sight_check(st, s, orig.projected, orig.redrawn)
        last = after
        o = State(after)
        if any(name == "redraw" for name, _ in hooks.log):
            # The FCL's REDRAW, or a rig's, ran the renderer, the copy and
            # the sensors ($6B12, $9841) inside the pass: their outputs are
            # the original's, as at the start of a pass. A rig's pass keeps
            # its own energy, shield and end, which the rig changes and
            # the renderer doesn't.
            keep = ("Energy", "Shield", "GameOver") if any(n == "message" for n, _ in hooks.log) else ()
            kept = {k: getattr(s, k) for k in keep}
            s.sync_from(after)
            for k, v in kept.items():
                setattr(s, k, v)
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
            ending = alive == "over"
    return passes


# --- fuzzing --------------------------------------------------------------

MOVE_KEYS = "O K Q W P L N M R F U A Z S X B SPACE D C".split()
WEIGHTS = [8, 4, 3, 3, 2, 2, 1, 1, 2, 2, 1, 1, 1, 1, 1, 0.3, 0.3, 0.3, 0.2]


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
    ap.add_argument("--fix-corner", action="store_true", help="decision 18's fix on (move.FIX_CORNER)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    move.FIX_CORNER = args.fix_corner
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
    if fcl.RUN:
        print("FCL opcodes run: " + ", ".join(f"${op:02X} {n}" for op, n in sorted(fcl.RUN.items())))
    if SHOTS:
        print(f"shots picked from the BBC's view: {SHOTS['hit']} hit, {SHOTS['missed']} missed")
    if SENSORS:
        print("the sensors: " + ", ".join(f"{k} {v}" for k, v in sorted(SENSORS.items())))
    if ENDS:
        print("the ends and new games: " + ", ".join(f"{k} {v}" for k, v in sorted(ENDS.items())))
    if INFO:
        print("the information screens, their text the original's, by the key that answered: " +
              ", ".join(f"{k} {v}" for k, v in sorted(INFO.items())))
    if REDRAWN[0]:
        print(f"{REDRAWN[0]} steps ran the FCL's REDRAW: the renderer's outputs taken from the original")
    if FROZE[0]:
        print(f"{FROZE[0]} ended where the original hangs, and the transcription knew it would")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
