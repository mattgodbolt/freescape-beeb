"""The BBC's MODE 2 colours for Driller, from each colour version.

    python -I tools/colour/design.py SOURCES.json OUTDIR

For every colour version (sources.py), every pattern scheme
(patterns.candidates), and each display it can choose for (an RGB monitor,
jsbeeb's PAL TV, or both at once), it picks each area's patterns: one for
each colour index the version's faces use, and the sky and the ground.
Every choice is then seen on both displays. It writes:

- OUTDIR/study.json: the figures, chosen-for by version by scheme by
  seen-on, area by area, and how many patterns each choice changes from
  the RGB monitor's;
- OUTDIR/bbc-VERSION-FOR.json: that version's patterns in the chosen
  scheme, chosen for display FOR;
- OUTDIR/bbc-FOR.json: the model's tables, one for each display (CHOSEN's
  version and scheme), which tools/model/colours.py reads and the engine
  carries, to switch between.

A bbc json holds, for each area id, "patterns": 15 patterns for indices
1-15 (index 0 is never drawn), then "sky" and "ground", each four MODE 2
bytes; and "faces": each object's colour nibbles in that version, which is
where the indices come from (docs/research/colour.md, "The database").
"""

import json
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patterns as P  # noqa: E402

COLOUR_VERSIONS = ["dos", "cpc", "st", "amiga"]
SCHEMES = ["solid", "bayer2", "pair", "triple"]
# The variants the study compares: a scheme, and whether distinct source
# colours are kept apart (choose).
VARIANTS = {"solid": ("solid", False), "bayer2": ("bayer2", True),
            "pair-nearest": ("pair", False), "pair": ("pair", True),
            "triple": ("triple", True)}
# The model's source and scheme (decision 8). It has a table for each
# display; which one shows is the model's and the engine's choice.
CHOSEN = ("st", "triple")
CHOOSE_FOR = ("rgb", "pal", "both")
SEEN_ON = ("rgb", "pal")

# A cuboid's or pyramid's faces in pairs that are never seen together
# (database.py's face order).
OPPOSITE = {(0, 1), (2, 3), (4, 5)}

# Source colours closer than SAME (dE) count as one colour and share a
# pattern; further apart, they get different patterns, so that two faces
# the original tells apart stay apart.
SAME = 3.0


def assign(cost):
    """The Hungarian method: for an n x m cost matrix (n <= m), the column
    for each row that minimises the total, no column used twice."""
    n, m = cost.shape
    u = np.zeros(n + 1)
    v = np.zeros(m + 1)
    p = np.zeros(m + 1, dtype=int)      # p[j]: the row (1-based) at column j
    way = np.zeros(m + 1, dtype=int)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = np.full(m + 1, np.inf)
        used = np.zeros(m + 1, dtype=bool)
        while True:
            used[j0] = True
            i0 = p[j0]
            cur = cost[i0 - 1] - u[i0] - v[1:]
            free = ~used[1:]
            better = free & (cur < minv[1:])
            minv[1:][better] = cur[better]
            way[1:][better] = j0
            cand = np.where(free, minv[1:], np.inf)
            j1 = int(np.argmin(cand)) + 1
            delta = cand[j1 - 1]
            u[p[used]] += delta
            v[used] -= delta
            minv[1:][free] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while j0:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
    out = np.zeros(n, dtype=int)
    for j in range(1, m + 1):
        if p[j]:
            out[p[j] - 1] = j - 1
    return out


def colour_groups(targets, used):
    """The used indices, grouped where their colours are within SAME."""
    groups = []
    for k in used:
        for g in groups:
            if P.de(targets[g[0]], targets[k]) <= SAME:
                g.append(k)
                break
        else:
            groups.append([k])
    return groups


def choose(cols, used, cands, distinct=True, display=None):
    """{index: (Pattern, dE)} for the used indices, and the sky and ground.
    With distinct, the used indices' distinct colours take distinct
    patterns, at the least total score; otherwise each takes its best. The
    sky and the ground take their best (each is black or a face's colour)."""
    targets = {k: P.target_of(cols[str(k)])
               for k in list(used) + ["sky", "ground"]}
    out = {}
    if distinct and used:
        groups = colour_groups(targets, used)
        sc = np.array([sum(P.scores(targets[k], cands, display)[0]
                           for k in g) for g in groups])
        pick = assign(sc)
        for g, j in zip(groups, pick):
            for k in g:
                out[k] = (cands[j],
                          float(P.scores(targets[k], cands, display)[1][j]))
    # The ground is the floor's top face (decision 8a): its pattern.
    floor = cols.get("ground_index")
    if floor in out:
        out["ground"] = out[floor]
    for k in targets:
        if k not in out:
            out[k] = P.best(targets[k], cands, display)
    return out


def adjacent_merges(objects, cols, chosen):
    """Pairs of faces of one object, seen together, whose source colours
    differ but whose patterns are the same: edges the BBC loses."""
    n = 0
    for colours in objects.values():
        if len(colours) != 6:
            continue
        for i in range(6):
            for j in range(i + 1, 6):
                a, b = colours[i], colours[j]
                if not a or not b or (i, j) in OPPOSITE or a == b:
                    continue
                if cols[str(a)] == cols[str(b)]:
                    continue
                if chosen[a][0].bytes == chosen[b][0].bytes:
                    n += 1
    return n


def hue_moved(target, mean):
    """Whether a pattern seen as mean moves a colour's hue by more than 45
    degrees, or greys a colour that has some (OKLab chroma over 8), or tints
    a grey."""
    c1 = math.hypot(*target[1:])
    c2 = math.hypot(*mean[1:])
    if c1 > 4 and c2 > 4:
        dh = abs(math.atan2(target[2], target[1])
                 - math.atan2(mean[2], mean[1]))
        return min(dh, 2 * math.pi - dh) > math.pi / 4
    return (c1 > 8 and c2 <= 4) or (c1 <= 4 and c2 > 8)


def area_figures(src, v, aid, ch, display):
    """How a table of patterns for one area does on display."""
    info = src["versions"][v]["areas"][aid]
    cols = src["colours"][v][aid]
    faces = {int(k): n for k, n in info["faces"].items()}
    used = sorted(faces)
    targets = {i: P.target_of(cols[str(i)]) for i in used}
    seen = {i: ch[i][0].seen(display)[0] for i in used}
    des = [P.de(targets[i], seen[i]) for i in used]
    w = np.array([faces[i] for i in used], dtype=float)
    tex = np.array([ch[i][0].pal_texture if display == "pal"
                    else ch[i][0].texture for i in used])
    crawl = np.array([ch[i][0].pal_crawl if display == "pal" else 0.0
                      for i in used])
    # The area's distinct colours, against its patterns.
    ngroups = len(colour_groups(targets, used))
    pats = {tuple(ch[i][0].bytes) for i in used}
    return {
        "mean": float(np.mean(des)), "worst": float(np.max(des)),
        "face_mean": float(np.sum(w * des) / np.sum(w)),
        "texture": float(np.sum(w * tex) / np.sum(w)),
        "crawl": float(np.sum(w * crawl) / np.sum(w)),
        "colours": ngroups, "patterns": len(pats | {
            tuple(ch["sky"][0].bytes), tuple(ch["ground"][0].bytes)}),
        "merged": ngroups - len(pats),
        "edges_lost": adjacent_merges(info["objects"], cols, ch),
        "hue_moved": sum(hue_moved(targets[i], seen[i]) for i in used),
    }


def summary(per_area):
    r = list(per_area.values())
    return {
        "areas": per_area,
        "mean": float(np.mean([x["mean"] for x in r])),
        "worst": float(max(x["worst"] for x in r)),
        "face_mean": float(np.mean([x["face_mean"] for x in r])),
        "texture": float(np.mean([x["texture"] for x in r])),
        "crawl": float(np.mean([x["crawl"] for x in r])),
        "merged": sum(x["merged"] for x in r),
        "edges_lost": sum(x["edges_lost"] for x in r),
        "patterns_max": max(x["patterns"] for x in r),
        "hue_moved": sum(x["hue_moved"] for x in r),
        "colours_used": sum(x["colours"] for x in r),
    }


def study(src, cand):
    """figures[chosen for][version][variant][seen on], with "changed": how
    many of the used colours' patterns differ from the RGB monitor's
    choice; and tables[(chosen for, version, variant)]."""
    figures = {d: {} for d in CHOOSE_FOR}
    tables = {}
    for d in CHOOSE_FOR:
        for v in COLOUR_VERSIONS:
            figures[d][v] = {}
            for label, (s, distinct) in VARIANTS.items():
                table = tables.setdefault((d, v, label), {})
                per = {on: {} for on in SEEN_ON}
                for a in src["areas"]:
                    aid = str(a["id"])
                    used = sorted(int(k) for k in
                                  src["versions"][v]["areas"][aid]["faces"])
                    ch = choose(src["colours"][v][aid], used, cand[s],
                                distinct, d)
                    table[aid] = ch
                    for on in SEEN_ON:
                        per[on][aid] = area_figures(src, v, aid, ch, on)
                figures[d][v][label] = {on: summary(per[on]) for on in SEEN_ON}
                changed = used_n = 0
                for aid, ch in table.items():
                    ref = tables[("rgb", v, label)][aid]
                    for i in src["versions"][v]["areas"][aid]["faces"]:
                        used_n += 1
                        changed += ch[int(i)][0].bytes != ref[int(i)][0].bytes
                figures[d][v][label]["changed"] = changed
                figures[d][v][label]["used"] = used_n
    return figures, tables


def table_json(src, v, table, cands, display):
    out = {"version": v, "scheme": CHOSEN[1], "display": display, "areas": {}}
    for a in src["areas"]:
        aid = str(a["id"])
        ch = table[aid]
        cols = src["colours"][v][aid]
        pats = []
        for i in range(1, 16):
            if i not in ch:  # no face uses it, but SPFX or a later fix may
                ch[i] = P.best(P.target_of(cols[str(i)]), cands, display)
            pats.append(ch[i][0].bytes)
        out["areas"][aid] = {
            "name": a["name"],
            "patterns": pats,
            "sky": ch["sky"][0].bytes,
            "ground": ch["ground"][0].bytes,
            "ground_index": cols["ground_index"],
            "floor": a["floor"],
            "faces": src["versions"][v]["areas"][aid]["objects"],
            "describe": [ch[i][0].describe() for i in range(1, 16)],
        }
    return out


def main(src_path, outdir):
    src = json.load(open(src_path))
    cand = {s: P.candidates(s) for s in SCHEMES}
    figures, tables = study(src, cand)
    os.makedirs(outdir, exist_ok=True)
    with open(os.path.join(outdir, "study.json"), "w") as f:
        json.dump({"blur": P.BLUR, "hue": P.HUE, "clash": P.CLASH,
                   "texture": P.TEXTURE, "crawl": P.CRAWL,
                   "display": P.DISPLAY, "pal_frames": P.PAL_FRAMES,
                   "chosen": CHOSEN, "figures": figures}, f, indent=1)
    scheme = cand[VARIANTS[CHOSEN[1]][0]]
    for v in COLOUR_VERSIONS:
        for d in CHOOSE_FOR:
            t = table_json(src, v, tables[(d, v, CHOSEN[1])], scheme, d)
            with open(os.path.join(outdir, f"bbc-{v}-{d}.json"), "w") as f:
                json.dump(t, f, indent=1)
            if v == CHOSEN[0]:
                with open(os.path.join(outdir, f"bbc-{d}.json"), "w") as f:
                    json.dump(t, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
