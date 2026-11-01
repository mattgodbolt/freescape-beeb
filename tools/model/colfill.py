"""The column fill: stages 8-10 down the screen's byte columns, modelled.

docs/research/colfill.md. The screen is laid out in byte columns down each
character row (8 consecutive bytes, then the next row SCREEN_ROW on), so one
unrolled routine of `LDA zp : STA row+line,X` (X the column's offset) can
write any byte column's run of lines, as Rich Talbot-Watkins's PORTAL and
Eben Upton's lander write theirs. This module is the column fill as the
6502 would run it, giving the row fill's picture (raster.py's spans,
writer.py's bytes) exactly, with a count of every operation, so that it can
be priced before any of it is built (tools/colfillprice.mjs, with the
kernels of src/colfill-kernels.6502).

fill(faces, bg) takes raster.spans' arguments and returns (rows, counts):
rows are writer.view_bytes' (VIEW_H rows of VIEW_BYTES bytes) and counts a
Counts. main() checks it against raster.spans on scene files and writes the
counts.

The design:

- **The edges are the row fill's.** Each face's span on each line is
  raster.face_spans' (the chains' DDA, decision 23), so the picture can't
  change. The chains are walked line by line as now, but a line's span goes
  into the face's column table: each pixel column's first line T and end
  line B. A convex face's pixels in a column are one run of lines with the
  DDA's boundaries too (face_columns raises if not). A segment where both
  chains are vertical changes no column, so it's passed over whole: under a
  level camera a box's sides cost nothing a line.
- **Coverage front to back, a byte column at a time.** Each byte column
  keeps, top to bottom, its nodes: runs of lines that are open (neither
  pixel taken), left-open (the right pixel taken by a face whose pattern
  waits in the node) or right-open. A face's two pixel columns' runs go into
  the byte column's nodes: lines both pixels take are written at once as one
  run through the column routine; a line one pixel takes either completes a
  half-open node (one byte, merged from the two patterns, written at once)
  or makes the open node there half-open. A byte column with no nodes is
  full, and faces stop once every column is. Each column starts the frame
  with a node of its own (the kernels' k_init); fresh and made also count
  what sharing one node among the untouched columns would make instead.
- **The background**: what's left in each byte column at the end, as sky or
  ground by horizon_split, the open nodes as runs and the half-open nodes'
  lines merged with them.
- **Writing**: a run of whole bytes enters a column routine (one for each
  half of the view's columns, either side of COL_SPLIT, and for each of
  dithered and solid patterns) at its first line, its end marked by an RTS
  planted there. Each routine keeps its plant until a run ends elsewhere;
  a run to the view's bottom ends on the routine's own RTS when the plant
  is above it. A face's pattern bytes go into zero page once. A merged byte
  is written on its own, or a run of them through the dithered routine with
  their four bytes in zero page, whichever is cheaper.

Counts (each defined by what the 6502 does for it):

- faces: faces looked at before every column was full; faces_hidden: of
  those, faces none of whose byte columns was open (or that cover no
  pixel); edges, edges_sloping: the edges set up (crossing a line), as the
  row fill counts them.
- lines_stepped: lines a face's chains are stepped on (one or both
  sloping), chain_steps: sloping chains stepped on them; lines_passed:
  lines passed over under two vertical chains; segments, segments_passed:
  the faces' segments (a pair of edges, one a chain), and those passed
  over; col_stores: pixel columns' T and B stored (two a face's column).
  col_runs: the store loops that put them there (a run of neighbouring
  columns with the same T, or B, each).
- fbc: face byte columns looked at (not full); fbc_full: passed over,
  full; fbc_same: of fbc, those whose two pixel columns have the same run;
  fbc_diff the rest.
- In the same columns: walked, nodes passed above the face's run; and the
  open nodes the run takes all of (o_whole), the end of (o_end: the node
  keeps its top), the start of (o_start: it keeps its bottom) or the middle
  of (o_mid: it splits); fresh: of these, those on a column no face had
  touched, which a shared node would make one node more for; half_hits:
  half-open nodes the run completes some lines of.
- In the differing columns: d_walked, d_hits (nodes the face's lines
  touch) and d_made (nodes made there).
- runs: whole-byte runs written through a column routine (the faces' and
  the background's): face_runs of them the faces'; runs_moved (the plant
  moved), runs_kept (the plant where the run ends already), runs_own (to
  the bottom on the routine's own RTS); run_bytes_solid / _two / _four:
  their bytes by the pattern's kind.
- merged: bytes written merged from two patterns; merged_lengths: the
  lines of each run of them in a column.
- bg_cols: byte columns the background found open; bg_nodes: their nodes.
- made: nodes made in all, the untouched columns sharing one (so the
  frame's pool needs made of them, never given back until the frame ends);
  nodes_peak: most alive at once.
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

if __package__:
    from .raster import VIEW_W, VIEW_H, face_spans, edge_crossings, horizon_split
    from .writer import VIEW_BYTES, PIX_LEFT, PIX_RIGHT
else:
    # (run as a script with python -I, as the Makefile runs the tools)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from raster import VIEW_W, VIEW_H, face_spans, edge_crossings, horizon_split
    from writer import VIEW_BYTES, PIX_LEFT, PIX_RIGHT

OPEN, LEFT_OPEN, RIGHT_OPEN = 0, 1, 2
# The byte column where the second half's routine takes over: each half's
# columns' offsets (8 per column) fit X.
COL_SPLIT = VIEW_BYTES // 2
assert 8 * max(COL_SPLIT, VIEW_BYTES - COL_SPLIT) <= 256


def kind(pattern):
    """A pattern's kind for the column routine: "solid" (one byte), "two"
    (two alternating) or "four"."""
    p = tuple(pattern)
    if p[0] == p[1] == p[2] == p[3]:
        return "solid"
    if p[0] == p[2] and p[1] == p[3]:
        return "two"
    return "four"


@dataclass
class Counts:
    faces: int = 0
    faces_hidden: int = 0
    edges: int = 0
    edges_sloping: int = 0
    lines_stepped: int = 0
    chain_steps: int = 0
    lines_passed: int = 0
    segments: int = 0
    segments_passed: int = 0
    col_stores: int = 0
    col_runs: int = 0
    fbc: int = 0
    fbc_full: int = 0
    fbc_same: int = 0
    fbc_diff: int = 0
    walked: int = 0
    o_whole: int = 0
    o_end: int = 0
    o_start: int = 0
    o_mid: int = 0
    fresh: int = 0
    half_hits: int = 0
    d_walked: int = 0
    d_hits: int = 0
    d_made: int = 0
    runs: int = 0
    face_runs: int = 0
    runs_moved: int = 0
    runs_kept: int = 0
    runs_own: int = 0
    run_bytes_solid: int = 0
    run_bytes_two: int = 0
    run_bytes_four: int = 0
    merged: int = 0
    bg_cols: int = 0
    bg_nodes: int = 0
    made: int = 0
    nodes_peak: int = 0
    merged_lengths: list = field(default_factory=list)
    run_lengths: list = field(default_factory=list)

    @property
    def bytes(self):
        return self.run_bytes_solid + self.run_bytes_two + self.run_bytes_four + self.merged

    def as_dict(self):
        d = dict(self.__dict__)
        d["bytes"] = self.bytes
        return d


def face_columns(vertices):
    """A face's pixel columns, {x: (T, B)}, the lines [T, B) it covers in
    column x by raster.face_spans' spans; and its chains' segments, a list
    of (lines, sloping chains) for each pair of edges crossing its lines in
    turn. Raises if a column's lines aren't one run."""
    spans = face_spans(vertices)
    cols = {}
    for y in sorted(spans):
        a, b = spans[y]
        for x in range(a, b):
            t, u = cols.get(x, (y, y))
            if u != y:
                raise ValueError(f"column {x}: lines {t}..{u} then {y}")
            cols[x] = (t, y + 1)
    # On each line the face's edges cross, the two edges crossing it (one
    # of each chain, a convex polygon's non-horizontal edges taking each
    # line twice); a segment is a run of lines with the same two.
    crossing = {}
    n = len(vertices)
    for i in range(n):
        (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
        for k, _ in edge_crossings(x0, y0, x1, y1):
            crossing.setdefault(k, []).append((i, x0 != x1))
    segments = []
    last = None
    for k in sorted(crossing):
        pair = tuple(sorted(crossing[k]))
        if pair != last:
            segments.append([0, sum(s for _, s in pair)])
            last = pair
        segments[-1][0] += 1
    return cols, segments


def _bg_pattern(bg, x, y):
    left, right, split = horizon_split(bg, y)
    return left if x < split else right


def fill(faces, bg):
    """faces: [(pattern, [(x, y), ...]), ...] nearest first, as raster.spans
    takes them; bg: a raster.Background. Returns (rows, counts): the view's
    bytes, VIEW_H rows of VIEW_BYTES, and the Counts."""
    c = Counts()
    out = [[None] * VIEW_BYTES for _ in range(VIEW_H)]
    # Each byte column's nodes, top to bottom: [s, e, kind, pending pattern].
    nodes = [[[0, VIEW_H, OPEN, None]] for _ in range(VIEW_BYTES)]
    fresh = [True] * VIEW_BYTES
    alive = VIEW_BYTES
    open_cols = VIEW_BYTES
    # Each column routine's plant, by (solid, half): the line its RTS is on.
    plant = {}

    def put(col, y, b):
        if out[y][col] is not None:
            raise AssertionError(f"line {y} byte {col} written twice")
        out[y][col] = b

    def run(col, y0, y1, pattern):
        if y1 <= y0:
            return
        c.runs += 1
        c.run_lengths.append(y1 - y0)
        k = kind(pattern)
        setattr(c, "run_bytes_" + k, getattr(c, "run_bytes_" + k) + y1 - y0)
        routine = (k == "solid", col >= COL_SPLIT)
        p = plant.get(routine, VIEW_H)
        if p == y1:
            c.runs_kept += 1
        elif y1 == VIEW_H and p < y0:
            c.runs_own += 1
        else:
            c.runs_moved += 1
            plant[routine] = y1
        for y in range(y0, y1):
            put(col, y, pattern[y & 3])

    def merged(col, y0, y1, left, right):
        if y1 <= y0:
            return
        c.merged += y1 - y0
        c.merged_lengths.append(y1 - y0)
        for y in range(y0, y1):
            put(col, y, (left[y & 3] & PIX_LEFT) | (right[y & 3] & PIX_RIGHT))

    for pattern, vertices in faces:
        if open_cols == 0:
            break
        pattern = tuple(pattern)
        c.faces += 1
        n = len(vertices)
        for i in range(n):
            (x0, y0), (x1, y1) = vertices[i], vertices[(i + 1) % n]
            if next(iter(edge_crossings(x0, y0, x1, y1)), None) is not None:
                c.edges += 1
                c.edges_sloping += x0 != x1
        cols, segments = face_columns(vertices)
        for lines, sloping in segments:
            c.segments += 1
            if sloping:
                c.lines_stepped += lines
                c.chain_steps += lines * sloping
            else:
                c.segments_passed += 1
                c.lines_passed += lines
        c.col_stores += 2 * len(cols)
        # Each run of neighbouring columns with the same T (or B) is one of
        # the line loop's store loops.
        xs = sorted(cols)
        for end in (0, 1):
            c.col_runs += sum(1 for i, x in enumerate(xs)
                              if i == 0 or x != xs[i - 1] + 1 or cols[x][end] != cols[xs[i - 1]][end])
        if not cols:
            c.faces_hidden += 1
            continue
        drew = False
        for col in range(min(cols) >> 1, (max(cols) >> 1) + 1):
            if not nodes[col]:
                c.fbc_full += 1
                continue
            c.fbc += 1
            drew = True
            t0, b0 = cols.get(2 * col, (0, 0))
            t1, b1 = cols.get(2 * col + 1, (0, 0))
            same = (t0, b0) == (t1, b1)
            if same:
                c.fbc_same += 1
            else:
                c.fbc_diff += 1
            top = min(t0 if t0 < b0 else VIEW_H, t1 if t1 < b1 else VIEW_H)
            bot = max(b0, b1)
            new = []
            for s, e, k, pend in nodes[col]:
                if e <= top or s >= bot:
                    if e <= top:
                        if same:
                            c.walked += 1
                        else:
                            c.d_walked += 1
                    new.append([s, e, k, pend])
                    continue
                # The node's lines by which of the face's pixels take them.
                cuts = sorted({s, e} | {v for v in (t0, b0, t1, b1) if s < v < e})
                pieces = []
                for y0, y1 in zip(cuts, cuts[1:]):
                    left = t0 <= y0 < b0
                    right = t1 <= y0 < b1
                    if k == OPEN:
                        if left and right:
                            run(col, y0, y1, pattern)
                            c.face_runs += 1
                        elif left:
                            pieces.append([y0, y1, RIGHT_OPEN, pattern])
                        elif right:
                            pieces.append([y0, y1, LEFT_OPEN, pattern])
                        else:
                            pieces.append([y0, y1, OPEN, None])
                    elif k == LEFT_OPEN and left:
                        merged(col, y0, y1, pattern, pend)
                    elif k == RIGHT_OPEN and right:
                        merged(col, y0, y1, pend, pattern)
                    else:
                        pieces.append([y0, y1, k, pend])
                # Neighbouring pieces of one kind are one node.
                joined = []
                for p in pieces:
                    if joined and joined[-1][1] == p[0] and joined[-1][2:] == p[2:]:
                        joined[-1][1] = p[1]
                    else:
                        joined.append(p)
                # A cut in place keeps one node; a fresh column's shared node
                # stays as it is, so every piece left is a node made.
                made = len(joined) if fresh[col] else max(len(joined) - 1, 0)
                c.made += made
                if same and k == OPEN:
                    keeps_top, keeps_bot = s < top, e > bot
                    if keeps_top and keeps_bot:
                        c.o_mid += 1
                    elif keeps_top:
                        c.o_end += 1
                    elif keeps_bot:
                        c.o_start += 1
                    else:
                        c.o_whole += 1
                    if fresh[col] and joined:
                        c.fresh += 1
                elif same:
                    c.half_hits += 1
                else:
                    c.d_hits += 1
                    c.d_made += made
                alive += len(joined) - 1
                new.extend(joined)
            nodes[col] = new
            fresh[col] = False
            c.nodes_peak = max(c.nodes_peak, alive)
            if not new:
                open_cols -= 1
        if not drew:
            c.faces_hidden += 1

    # The background, a byte column at a time.
    for col in range(VIEW_BYTES):
        if not nodes[col]:
            continue
        c.bg_cols += 1
        for s, e, k, pend in nodes[col]:
            c.bg_nodes += 1
            # Runs of lines with the same pair of background patterns.
            y = s
            while y < e:
                pl = _bg_pattern(bg, 2 * col, y)
                pr = _bg_pattern(bg, 2 * col + 1, y)
                y1 = y + 1
                while y1 < e and _bg_pattern(bg, 2 * col, y1) == pl and _bg_pattern(bg, 2 * col + 1, y1) == pr:
                    y1 += 1
                if k == OPEN and pl == pr:
                    run(col, y, y1, pl)
                elif k == OPEN:
                    merged(col, y, y1, pl, pr)
                elif k == LEFT_OPEN:
                    merged(col, y, y1, pl, pend)
                else:
                    merged(col, y, y1, pend, pr)
                y = y1
    for y in range(VIEW_H):
        for col in range(VIEW_BYTES):
            if out[y][col] is None:
                raise AssertionError(f"line {y} byte {col} never written")
    return [bytes(row) for row in out], c


def scenes_of(path):
    """A scene file's frames (tools/rasterscenes.py's): its scenes, then its
    sequences' frames, each (name, faces, Background)."""
    if __package__:
        from .raster import Background, Horizon
    else:
        from raster import Background, Horizon
    d = json.loads(Path(path).read_text())
    frames = [(s["name"], s) for s in d["scenes"]]
    for q in d.get("sequences") or []:
        frames += [(f"{q['name']}[{i}]", s) for i, s in enumerate(q["frames"])]
    for name, s in frames:
        bg = Background(tuple(s["sky"]), tuple(s["ground"]),
                        None if s["horizon"] is None else Horizon(*s["horizon"]))
        faces = [(tuple(f["pattern"]), [tuple(v) for v in f["vertices"]]) for f in s["faces"]]
        yield name, faces, bg


def main(argv):
    """colfill.py [--counts OUT.json] SCENES.json...: each frame's bytes by
    fill against raster.spans' (without the pools' limit, which the column
    fill hasn't), failing on any that differ; the counts into OUT.json."""
    if __package__:
        from .raster import spans
        from . import writer
    else:
        from raster import spans
        import writer
    out = None
    if argv[:1] == ["--counts"]:
        out, argv = argv[1], argv[2:]
    results, bad = [], 0
    for path in argv:
        n = 0
        for name, faces, bg in scenes_of(path):
            got, counts = fill(faces, bg)
            if got != writer.view_bytes(spans(faces, bg)[0]):
                bad += 1
                print(f"{path}: {name}: the column fill's view isn't the row fill's", file=sys.stderr)
            results.append({"file": path, "name": name, "counts": counts.as_dict()})
            n += 1
        print(f"{path}: {n} frames, the column fill's view the row fill's on {n - bad}")
    if out:
        Path(out).write_text(json.dumps(results) + "\n")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
