"""The scenario format (tests/logic/*.txt): one step a line, from the
in-play snapshot (make zx: area 1, entrance 19, on the probe).

    # a comment; blank lines are ignored
    O                 a pass with O held
    Q O x3            three passes with Q and O held
    tick              a pass in which a minute of the clock ends, no keys
                      (never straight after a pass that leaves the input a
                      minute to take, as minute 9's does: the original's
                      input takes that one before the clock can end another)
    sensors 50        50 frames of the interrupt's sensors between passes
                      (the original's $BB93: their shots at the shield)
    goto 2 4          FCL GOTO area 2, entrance 4 (the original's $9D1C)
    fcl 15            FCL bytes, hex, run by $B320 (15: SWAPJET)
    shot 85 0A        FCL bytes run as a shot's (ShotFlag set)
    poke 8772 03      bytes at an address, hex, on both sides
    at 4640 160 5920  the camera's x, y, z (decimal)
    angles 0 34 0     its pitch, yaw, roll (decimal)
    end               the game's end (after the pass that ended it: the
                      original's $9AB7, from the input's next pass, which
                      finds it), its wait answered by ENTER, and the new
                      game it starts ($9C36, $97CD)
    end demo          ... its wait left to run out: the demo next
    demo x20          passes with no key held while the demo plays (a pass
                      of keys ends it, and a new game starts)
    expect AreaId 2   a variable's value after the last step (decimal or
                      $hex), on both sides: a scenario says what it shows.
                      Keys[0] is one byte of a run; a run alone reads as a
                      little-endian number

Keys are the ZX's names (tools/zx.py): A-Z, 0-9, SPACE, ENTER, CAPS, SYM.
"""
import re


class Step:
    def __init__(self, kind, line, **kw):
        self.kind = kind
        self.line = line
        self.__dict__.update(kw)

    def __repr__(self):
        return f"{self.kind}@{self.line}"


KEY = re.compile(r"^(?:[A-Z0-9]|SPACE|ENTER|CAPS|SYM)$")


def parse_num(v):
    v = v.strip()
    if v.startswith("$"):
        return int(v[1:], 16)
    return int(v, 0)


def parse(text, name="scenario"):
    steps = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        words = line.split()
        w0 = words[0]
        where = f"{name}:{n}"
        if w0 == "tick":
            repeat = 1
            if len(words) == 2 and re.fullmatch(r"x\d+", words[1]):
                repeat = int(words[1][1:])
            elif len(words) != 1:
                raise ValueError(f"{where}: a tick takes no keys: {line!r}")
            for _ in range(repeat):
                steps.append(Step("pass", where, keys=(), tick=True))
        elif w0 == "sensors":
            steps.append(Step("sensors", where, n=int(words[1])))
        elif w0 == "end":
            if words[1:] not in ([], ["demo"]):
                raise ValueError(f"{where}: an end is 'end' or 'end demo': {line!r}")
            steps.append(Step("end", where, demo=words[1:] == ["demo"]))
        elif w0 == "demo":
            repeat = 1
            if len(words) == 2 and re.fullmatch(r"x\d+", words[1]):
                repeat = int(words[1][1:])
            elif len(words) != 1:
                raise ValueError(f"{where}: the demo's passes take no keys: {line!r}")
            for _ in range(repeat):
                steps.append(Step("pass", where, keys=(), tick=False))
        elif w0 == "goto":
            steps.append(Step("fcl", where, code=[0x12, int(words[1]), int(words[2])], shot=False))
        elif w0 in ("fcl", "shot"):
            steps.append(Step("fcl", where, code=[int(b, 16) for b in words[1:]], shot=w0 == "shot"))
        elif w0 == "poke":
            steps.append(Step("poke", where, addr=int(words[1], 16), values=[int(b, 16) for b in words[2:]]))
        elif w0 == "at":
            x, y, z = (int(v) for v in words[1:4])
            vals = [x & 0xFF, x >> 8, y & 0xFF, y >> 8, z & 0xFF, z >> 8]
            steps.append(Step("poke", where, addr=0x8762, values=vals))
        elif w0 == "angles":
            steps.append(Step("poke", where, addr=0x876C, values=[int(v) for v in words[1:4]]))
        elif w0 == "expect":
            steps.append(Step("expect", where, name=words[1], value=parse_num(words[2])))
        else:
            repeat = 1
            if re.fullmatch(r"x\d+", words[-1]):
                repeat = int(words[-1][1:])
                words = words[:-1]
            for k in words:
                if not KEY.match(k):
                    raise ValueError(f"{where}: not a key or a command: {k!r}")
            for _ in range(repeat):
                steps.append(Step("pass", where, keys=tuple(words), tick=False))
    return steps


def load(path):
    with open(path) as f:
        return parse(f.read(), path)
