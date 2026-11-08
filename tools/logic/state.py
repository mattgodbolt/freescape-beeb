"""The player logic's state: the original's variables, by name, at the
original's addresses.

The state is a 64K memory image, as the ZX's, with a property for every
variable the logic reads or writes. Keeping the image (rather than a field
each) keeps the original's aliases: the FCL's variable 31 is the minute
counter `MinuteCount`, its bit 32 is `InJet`'s twin in `FclBits`, and the
objects' records are the database's bytes, which the FCL changes in place.

Each variable is one of:

- "logic": the pass (tools/logic/passes.py) owns it, and the oracle
  compares it after every pass;
- "sync": something outside the pass writes it (the interrupt, the redraw
  and the screen copy, the sensors' line-of-sight test after the redraw),
  so the oracle copies it from the original at the start of each pass and
  compares it after;
- "clock": the interrupt counts it while the pass runs (the clock): copied
  from the original at the start of each pass, never compared;
- "const": a table or setting the pass only reads; compared, never synced.

Addresses are the original's (docs/research/zx-logic.md).

The port's start and pace (decision 48) are here too, for Matt to change
in this one place: the 6502's data takes them (tools/mklogicdata.py), so
the 6502 logic and the live disc start from the port's start, as the
traces of their checks do (tools/logictrace.py, tools/mklive.py --trace).
The check against the original (make logic) keeps the original's start.
"""
from .arith import mul_a_hl

# The port's start: the step's and the turn's sizes the game starts with,
# as indices into the original's StepTable and TurnTable (in world units
# times the area's scale, and in 5-degree units: docs/research/zx-logic.md),
# in place of the database's own (its header's bytes $C2 and $C3), so that
# a tap of a movement key moves a little. f0-f3 change them in play
# (decision 10).
START_STEP_INDEX = 4
START_TURN_INDEX = 0
# The live disc's pace (src/live.6502, docs/research/live.md, "The pace"):
# a pass's frames take PASS_FIELDS fields, so a held key's passes come that
# often; a key going down gives a pass at once, and the keys held repeat
# REPEAT_FIELDS fields after it, so a tap shorter than that is one pass (the
# Master's own keyboard waits as long before it repeats: live.md's
# measurements of 2026-11-01).
PASS_FIELDS = 5
REPEAT_FIELDS = 15

# (name, address, size, kind, what): size 1 is a byte, 2 a little-endian
# word, and a tuple ("bytes", n) n bytes, read as a bytes object.
VARS = [
    # The camera and the probe (docs/research/zx-driller.md for the units).
    ("PlayerX", 0x8762, 2, "logic", "camera x, world units (64 to a cell)"),
    ("PlayerY", 0x8764, 2, "logic", "camera y: the eye"),
    ("PlayerZ", 0x8766, 2, "logic", "camera z"),
    ("StepUnits", 0x8768, 2, "logic", "the step in world units: Step times AreaScale"),
    ("Step", 0x876A, 1, "logic", "the step, from StepTable"),
    ("StepIndex", 0x876B, 1, "logic", "the step's index in StepTable"),
    ("Pitch", 0x876C, 1, "logic", "5-degree units, 0-71; positive looks down"),
    ("Yaw", 0x876D, 1, "logic", "5-degree units, 0-71; 0 looks along +z"),
    ("Roll", 0x876E, 1, "logic", "5-degree units, 0-71"),
    ("Turn", 0x876F, 1, "logic", "the turn, 5-degree units, from TurnTable"),
    ("TurnIndex", 0x8770, 1, "logic", "the turn's index in TurnTable"),
    ("ExtMax", 0x8771, 1, "logic", "the probe's highest extension level"),
    ("ExtLevel", 0x8772, 1, "logic", "the probe's extension level, 1-ExtMax"),
    ("FallLimit", 0x8773, 1, "logic", "the most cells the probe survives falling"),
    ("ClimbLimit", 0x8774, 1, "logic", "the most cells the probe steps up"),
    ("ExtMaxScaled", 0x8775, 1, "logic", "ExtMax times AreaScale"),
    ("BodyHeight", 0x8776, 1, "logic", "ExtLevel times AreaScale: the probe's height in cells"),
    ("FallLimitScaled", 0x8777, 1, "logic", "FallLimit times AreaScale"),
    ("ClimbLimitScaled", 0x8778, 1, "logic", "ClimbLimit times AreaScale"),
    ("AreaScale", 0x8779, 1, "logic", "the area's scale (its header byte 5)"),
    ("InJet", 0x877A, 1, "logic", "non-zero in the jet"),
    ("RigPlaced", 0x877B, ("bytes", 18), "logic", "a rig in each of areas 1-18 (0: none)"),
    ("RigState", 0x878D, ("bytes", 18), "logic", "the rigs' second byte an area"),
    ("GasChosen", 0x879F, 1, "logic", "non-zero once GasYields is chosen (the first rig placed)"),
    ("AreaGas", 0x87A0, ("bytes", 3), "logic", "the area's header bytes 10-12: the gas's cell x, z and reach"),
    ("GasYields", 0x87A3, 2, "logic", "the yields, one an area, from GasTable: picked by the clock"),
    ("Globals", 0x87A5, ("bytes", 0x882C - 0x87A5), "logic", "the eight global objects' records"),
    ("RigPositions", 0x882C, ("bytes", 54), "logic", "where each area's rig stands, 3 cells an area"),
    # The area.
    ("AreaId", 0x8862, 1, "logic", "the current area's id"),
    ("AreaObjects", 0x8863, 1, "logic", "its object count"),
    ("AreaObjPtr", 0x8864, 2, "logic", "its first object's record"),
    ("AreaNamePtr", 0x8866, 2, "logic", "its name (header byte 13)"),
    ("AreaCondPtr", 0x8868, 2, "logic", "its conditions"),
    ("ScreenColours", 0x886A, ("bytes", 4), "sync", "the colours the screen shows (the copy, $A77A)"),
    ("AreaColours", 0x886E, ("bytes", 4), "logic", "the area's colours (header bytes 6-9; SPFX)"),
    ("Score", 0x8872, ("bytes", 3), "logic", "the score, 24 bits"),
    ("Energy", 0x8875, 1, "sync", "the vehicle's energy (the interrupt spends it a minute)"),
    ("JetEnergy", 0x8876, 1, "logic", "the jet's energy, kept while in the probe"),
    ("ProbeEnergy", 0x8877, 1, "logic", "the probe's energy, kept while in the jet"),
    ("Shield", 0x8878, 1, "sync", "the vehicle's shield (the sensors' shots, in the interrupt)"),
    ("JetShield", 0x8879, 1, "logic", "the jet's shield, kept while in the probe"),
    ("ProbeShield", 0x887A, 1, "logic", "the probe's shield, kept while in the jet"),
    ("FclBits", 0x887B, ("bytes", 4), "logic", "the FCL's 32 bits; bit 32 (887E bit 7) is in the jet"),
    ("FclVars", 0x887F, ("bytes", 29), "logic", "the FCL's variables 1-29"),
    ("FclVar30", 0x889C, 1, "logic", "the FCL's variable 30: minutes, all told"),
    ("MinuteCount", 0x889D, 1, "logic", "the FCL's variable 31: minutes in this area (the interrupt)"),
    ("FclVar32", 0x889E, 1, "logic", "the FCL's variable 32"),
    ("AreaFlags", 0x889F, 1, "logic", "the area's header byte 0"),
    ("CrossX", 0x88A0, 1, "logic", "the crosshair, screen x"),
    ("CrossY", 0x88A1, 1, "logic", "the crosshair, screen y (up)"),
    ("CrossOn", 0x88A2, 1, "logic", "non-zero: the crosshair is shown"),
    ("SecondFrames", 0x88A3, 1, "clock", "the interrupt's frames into the second"),
    ("Clock", 0x88A4, ("bytes", 8), "clock", "the clock's text, hh:mm:ss"),
    ("ShootMode", 0x88AC, 1, "logic", "non-zero: the movement keys move the crosshair"),
    ("CrossWanted", 0x88AD, 1, "logic", "the crosshair outside shooting mode (key B)"),
    ("MinuteSeen", 0x88AE, 1, "logic", "MinuteCount as the input last saw it"),
    # The move's scratch: the sensors' test after the redraw writes these too.
    ("TargetX", 0x88AF, 2, "sync", "where the move is going; then where it stopped"),
    ("TargetY", 0x88B1, 2, "sync", ""),
    ("TargetZ", 0x88B3, 2, "sync", ""),
    ("CellX", 0x88B5, 1, "sync", "the move's current cell"),
    ("CellY", 0x88B6, 1, "sync", ""),
    ("CellZ", 0x88B7, 1, "sync", ""),
    ("StepTable", 0x88BE, ("bytes", 9), "const", "a count, then the steps"),
    ("TurnTable", 0x88C9, ("bytes", 7), "const", "a count, then the turns"),
    ("Margin", 0x88D0, 1, "const", "how near a face the camera may stand; 0 makes $9F42 a test"),
    ("ViewCentre", 0x88D9, ("bytes", 2), "const", "XC, YC: the crosshair's limits are twice these"),
    ("AreaExtent", 0x88DF, ("bytes", 6), "const", "x max, x min, y max, y min, z max, z min, in cells"),
    ("AreaChanged", 0x8910, 1, "sync", "set by the area load, cleared by the screen ($A77A)"),
    ("EntranceId", 0x8911, 1, "logic", "the entrance the area load puts the camera at"),
    ("FoundId", 0x8916, 1, "sync", "the id $A8BA looks up (the sensors' test after the redraw too)"),
    ("GameFlags", 0x8920, 1, "logic", "what changed: bit 2 re-project (moved or turned), and more"),
    ("GameFlags2", 0x8921, 1, "logic", "what changed: bit 3 redraw from the list, and the panel's"),
    ("SensorList", 0x8A24, ("bytes", 0x8A64 - 0x8A24), "sync", "the sensors the redraw found, and the interrupt's copy"),
    ("EventsDue", 0x8A64, 1, "logic", "non-zero: run the events ($9B6E) this pass"),
    ("Collided", 0x8A69, 1, "sync", "the id of the object the move hit"),
    ("Blocked", 0x8A1E, 1, "sync", "the move was stopped"),
    ("Sound", 0x8A1F, 1, "sync", "a sound to play after the screen copy, which clears it"),
    ("Wipe", 0x8BF0, 1, "logic", "non-zero: the screen copy wipes ($AB25)"),
    ("ShotFlag", 0x8BF1, 1, "logic", "non-zero: the events are a shot's"),
    ("GameOver", 0x8BF2, 1, "sync", "why the game ended: 1 shield, 2 time, 3 energy, 4 a fall, 5 won, 6 abandoned"),
    ("KeyCount", 0x8FBC, 1, "logic", "the keys read this pass, at most 5"),
    ("Keys", 0x8FBD, ("bytes", 5), "logic", "their codes, in the keyboard's order"),
    ("Countdown", 0x8FC2, 1, "sync", "frames to wait, counted down by the interrupt"),
    ("PanelEnergy", 0x8A67, 1, "sync", "the energy the panel shows"),
    ("PanelShield", 0x8A68, 1, "sync", "the shield the panel shows"),
    ("RepeatDelay", 0x8FC3, 1, "const", "frames before a held key repeats"),
    ("RepeatRate", 0x8FC4, 1, "const", "frames between repeats"),
    ("Control", 0x8FC5, 1, "const", "2: the Kempston joystick too"),
    ("KeyTable3", 0x8FC6, 1, "const", "entries in the first key table (key, action, shooting action)"),
    ("KeyTable2", 0x8FC7, 1, "const", "entries in the second (key, action)"),
    ("KeyRows", 0x9404, ("bytes", 8), "logic", "the half-rows as last read, less the keys taken"),
    ("Repeating", 0x940C, 1, "logic", "the held keys have been seen before"),
    ("LastKeyCount", 0x940D, 1, "logic", "the keys last read"),
    ("LastKeys", 0x940E, ("bytes", 5), "logic", ""),
    ("RepeatCopy", 0x9413, 1, "logic", "RepeatDelay, copied"),
    ("Actions", 0x998A, ("bytes", 5), "logic", "the keys' actions this pass"),
    ("ActionIndex", 0x998F, 1, "logic", "the action being done"),
    ("SavedCellY", 0x9DC9, 1, "logic", "the step-up's starting cell"),
    ("MoveScratch", 0x9F33, ("bytes", 15), "sync", "the move's target cells, crossing point and delta"),
    ("HitRemembered", 0xA596, 1, "sync", "$A597's last solid hit"),
    ("FclOp", 0xB31F, 1, "logic", "the FCL instruction being run"),
    ("RigFigures", 0x8C3C, ("bytes", 28), "logic", "the rig's two messages its figures are written into"),
    ("RigScratch", 0xBEF4, ("bytes", 6), "logic", "the rig's percentage and yield, then the score's FCL instruction"),
]

# The database (areas, objects, conditions), as long as its header says:
# the FCL changes the objects' flag bytes in place. Compared after every
# pass. (The stack is above it.)
DATABASE = 0xCF3E


def database(mem):
    return DATABASE, DATABASE + (mem[DATABASE + 1] | mem[DATABASE + 2] << 8)


# The database header's first step and turn, which a new game takes into
# StepIndex and TurnIndex ($9C36).
DB_STEP_INDEX = 0xC2
DB_TURN_INDEX = 0xC3
# The sizes' variables in the original's block, two runs of bytes: StepUnits,
# Step and StepIndex; Turn and TurnIndex. As (address, length).
_ADDR = {name: addr for name, addr, *_ in VARS}
SIZES = tuple((_ADDR[a], _ADDR[b] + 1 - _ADDR[a]) for a, b in (("StepUnits", "StepIndex"), ("Turn", "TurnIndex")))


def port_start(mem):
    """The in-play snapshot's memory (the original's start) as the port's:
    the database's first step and turn START_STEP_INDEX and
    START_TURN_INDEX, and the variables set from them as a new game sets
    them ($9C36, then the area's load): StepIndex and TurnIndex, Step and
    Turn from their tables, and StepUnits Step times AreaScale."""
    s = State(mem)
    assert START_STEP_INDEX < s.StepTable[0] and START_TURN_INDEX < s.TurnTable[0], \
        "the port's start isn't in the original's tables"
    s.mem[DATABASE + DB_STEP_INDEX] = START_STEP_INDEX
    s.mem[DATABASE + DB_TURN_INDEX] = START_TURN_INDEX
    s.StepIndex = START_STEP_INDEX
    s.Step = s.StepTable[1 + START_STEP_INDEX]
    s.StepUnits = mul_a_hl(s.AreaScale, s.Step)
    s.TurnIndex = START_TURN_INDEX
    s.Turn = s.TurnTable[1 + START_TURN_INDEX]
    return bytes(s.mem)


def original_sizes(mem):
    """The original's start sizes, from its in-play memory, as pokes
    [(address, bytes)]: a trace's run puts them in first, so that it runs
    from the original's start, as make logic runs the scenarios (which were
    written for it, and the fuzz walks found there), while the disc starts
    from the port's (port_start)."""
    return [(a, list(mem[a:a + n])) for a, n in SIZES]


def _prop(addr, size):
    if size == 1:
        return property(lambda s: s.mem[addr], lambda s, v: s.mem.__setitem__(addr, v & 0xFF))
    if size == 2:
        def get(s):
            return s.mem[addr] | s.mem[addr + 1] << 8

        def put(s, v):
            s.mem[addr] = v & 0xFF
            s.mem[addr + 1] = (v >> 8) & 0xFF
        return property(get, put)
    n = size[1]

    def getb(s):
        return bytes(s.mem[addr:addr + n])

    def putb(s, v):
        assert len(v) == n
        s.mem[addr:addr + n] = bytes(v)
    return property(getb, putb)


class State:
    """The memory image, with the variables above as properties."""

    def __init__(self, mem):
        self.mem = bytearray(mem)
        assert len(self.mem) == 0x10000

    def copy(self):
        return State(self.mem)

    def snapshot(self, kinds=("logic", "sync", "const")):
        """The named variables as a dict, for comparing and printing."""
        out = {name: getattr(self, name) for name, _, _, kind, _ in VARS if kind in kinds}
        lo, hi = database(self.mem)
        out["Database"] = bytes(self.mem[lo:hi])
        return out

    def sync_from(self, mem):
        """Take the "sync" variables from the original's memory."""
        for name, addr, size, kind, _ in VARS:
            if kind in ("sync", "clock"):
                n = size if isinstance(size, int) else size[1]
                self.mem[addr:addr + n] = bytes(mem[addr:addr + n])


for _name, _addr, _size, _kind, _what in VARS:
    setattr(State, _name, _prop(_addr, _size))


def differences(a, b):
    """The variables that differ between two snapshots, as (name, a, b);
    the database by object byte."""
    out = []
    for k in a:
        if a[k] == b[k]:
            continue
        if k == "Database":
            lo = DATABASE
            for i, (x, y) in enumerate(zip(a[k], b[k])):
                if x != y:
                    out.append((f"Database ${lo + i:04X}", x, y))
        else:
            out.append((k, a[k], b[k]))
    return out
