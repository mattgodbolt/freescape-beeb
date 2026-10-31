"""The colour study's figures as Markdown tables.

    python -I tools/colour/report.py SOURCES.json STUDY.json OUT.md

docs/research/colour.md quotes these, dated; the build remakes them. The
sky and ground table carries the originals' colours, so it stays in build/.
"""

import json
import os
import sys

VERSIONS = ["dos", "cpc", "st", "amiga"]
VARIANTS = ["solid", "bayer2", "pair-nearest", "pair", "triple"]
FOR = ["rgb", "pal", "both"]


def hexc(mix):
    if len(mix) == 1:
        return "#" + "".join(f"{int(c):02x}" for c in mix[0][:3])
    return "+".join("#" + "".join(f"{int(c):02x}" for c in m[:3])
                    + f"×{m[3]:.2f}" for m in mix)


def main(src_path, study_path, out_path):
    src = json.load(open(src_path))
    st = json.load(open(study_path))
    fig = st["figures"]
    out = []
    w = out.append
    w(f"Model parameters: blur {st['blur']} lines, hue weight {st['hue']}, "
      f"texture {st['texture']}, clash {st['clash']} (RGB), crawl "
      f"{st['crawl']} (PAL), {st['pal_frames']} PAL fields; the model's "
      f"patterns: {st['chosen'][0]}, {st['chosen'][1]}, chosen for "
      f"{st['display']}.\n")

    w("## Every version and scheme, on an RGB monitor\n")
    w("Chosen for the RGB monitor and seen on it. Means are over each "
      "area's used colours, then over areas; \"face mean\" weights each "
      "colour by its faces. dE is OKLab × 100.\n")
    w("| Version | Scheme | Mean dE | Worst dE | Face mean | Texture | "
      "Merged | Edges lost | Hue moved | Patterns (max an area) |")
    w("|---|---|---|---|---|---|---|---|---|---|")
    for v in VERSIONS:
        for s in VARIANTS:
            f = fig["rgb"][v][s]["rgb"]
            w(f"| {v} | {s} | {f['mean']:.1f} | {f['worst']:.1f} | "
              f"{f['face_mean']:.1f} | {f['texture']:.1f} | {f['merged']} | "
              f"{f['edges_lost']} | {f['hue_moved']} of {f['colours_used']} | "
              f"{f['patterns_max']} |")
    w("")

    w("## Chosen for one display, seen on each\n")
    w("Changed: the used colours whose pattern differs from the one chosen "
      "for the RGB monitor.\n")
    w("| Version | Scheme | Chosen for | RGB: mean / worst / texture | "
      "PAL: mean / worst / texture / crawl | Hue moved (RGB, PAL) | Changed |")
    w("|---|---|---|---|---|---|---|")
    for v in VERSIONS:
        for s in ("pair", "triple"):
            for d in FOR:
                f = fig[d][v][s]
                r, p = f["rgb"], f["pal"]
                w(f"| {v} | {s} | {d} | {r['mean']:.1f} / {r['worst']:.1f} / "
                  f"{r['texture']:.1f} | {p['mean']:.1f} / {p['worst']:.1f} / "
                  f"{p['texture']:.1f} / {p['crawl']:.1f} | {r['hue_moved']}, "
                  f"{p['hue_moved']} | {f['changed']} of {f['used']} |")
    w("")

    s = st["chosen"][1]
    d = st["display"]
    w(f"## Area by area, scheme {s}, chosen for {d}\n")
    w("Each cell: colours the area's faces use / patterns it needs "
      "(with sky and ground) / on RGB, mean and worst dE / through PAL, "
      "mean and worst dE.\n")
    w("| Area | Name | " + " | ".join(VERSIONS) + " |")
    w("|---|---|" + "---|" * len(VERSIONS))
    for a in src["areas"]:
        aid = str(a["id"])
        cells = []
        for v in VERSIONS:
            r = fig[d][v][s]["rgb"]["areas"][aid]
            p = fig[d][v][s]["pal"]["areas"][aid]
            cells.append(f"{r['colours']} / {r['patterns']} / "
                         f"{r['mean']:.1f}, {r['worst']:.1f} / "
                         f"{p['mean']:.1f}, {p['worst']:.1f}")
        w(f"| {aid} | {a['name']} | " + " | ".join(cells) + " |")
    w("")

    w("## Carrying a table for each display\n")
    tables = {}
    for d in FOR:
        path = os.path.join(os.path.dirname(study_path), f"bbc-{d}.json")
        tables[d] = json.load(open(path))["areas"]
    n_areas = len(src["areas"])
    full = 4 * 17 * n_areas
    bare = 4 * 15 * n_areas
    pool = {tuple(p) for t in tables.values() for e in t.values()
            for p in e["patterns"] + [e["sky"], e["ground"]]}
    differ = {(a, b): sum(tables[a][k]["patterns"][i] != tables[b][k]["patterns"][i]
                          for k in tables[a] for i in range(15))
              for a, b in (("rgb", "pal"), ("rgb", "both"), ("pal", "both"))}
    sky_black = all(e["sky"] == [0, 0, 0, 0] for t in tables.values()
                    for e in t.values())
    ground_floor = all(e["ground"] == (e["patterns"][e["ground_index"] - 1]
                                       if e["ground_index"] else e["sky"])
                       for t in tables.values() for e in t.values())
    w(f"- A table: {n_areas} areas of 15 patterns, a sky and a ground, four "
      f"bytes each: {full} bytes; {3 * full} for all three.")
    w(f"- The sky is black in every area of every table: {sky_black}. The "
      f"ground is its floor index's pattern, or the sky's without a floor: "
      f"{ground_floor}. So 15 patterns an area carry it all: {bare} bytes "
      f"a table, {3 * bare} for three.")
    w(f"- Distinct patterns across the three tables: {len(pool)}; as a "
      f"shared pool and a byte an index, {4 * len(pool)} + "
      f"{3 * 15 * n_areas} = {4 * len(pool) + 3 * 15 * n_areas} bytes.")
    w("- Entries (area and index, of " + f"{15 * n_areas}" + ") that differ: "
      + ", ".join(f"{a} and {b} {n}" for (a, b), n in differ.items()) + ".")
    w("")

    w("## Sky and ground\n")
    w("The sky is what each version clears the view to; the ground is the "
      "top face of the floor object (its id in the ZX's database), in each "
      "version's own colour index for it.\n")
    w("| Area | Floor | " + " | ".join(f"{v} sky | {v} ground"
                                      for v in VERSIONS) + " |")
    w("|---|---|" + "---|---|" * len(VERSIONS))
    for a in src["areas"]:
        aid = str(a["id"])
        cells = []
        for v in VERSIONS:
            c = src["colours"][v][aid]
            g = f"{c['ground_index']}: {hexc(c['ground'])}" \
                if c["ground_index"] else "none"
            cells += [hexc(c["sky"]), g]
        w(f"| {aid} | {a['floor']} | " + " | ".join(cells) + " |")
    w("")

    w("## The database against the ZX's\n")
    w("Objects are matched by area, id and whether they are entrances "
      "(which have ids of their own).\n")
    w("| Version | Areas differing | Objects differing | Differences by field |")
    w("|---|---|---|---|")
    for v in VERSIONS:
        diffs = src["compare"][v]
        objs = {(d[0], d[1]) for d in diffs if d[1] is not None}
        kinds = {}
        for d in diffs:
            k = d[2].split(":")[0]
            kinds[k] = kinds.get(k, 0) + 1
        w(f"| {v} | {len({d[0] for d in diffs})} | {len(objs)} | "
          + ", ".join(f"{k} {n}" for k, n in sorted(kinds.items())) + " |")
    w("")
    w("Over the objects both have with the same type: faces (colour "
      "nibbles), those whose index differs from the ZX's, those drawn in "
      "one and not the other, and the faces that a remap of the ZX's "
      "indices (one table an area, each ZX index taking the index most of "
      "its faces have in the version) would colour wrongly.\n")
    w("| Version | Objects | Geometry differs | Faces | Index differs | "
      "Drawn differs | Remap wrong (of faces drawn in the ZX) |")
    w("|---|---|---|---|---|---|---|")
    for v in VERSIONS:
        s = src["faces_compare"][v]
        w(f"| {v} | {s['objects']} | {s['geometry']} | {s['faces']} | "
          f"{s['index_differs']} | {s['drawn_differs']} | "
          f"{s['remap_wrong']} of {s['remap_faces']} |")
    w("")
    with open(out_path, "w") as f:
        f.write("\n".join(out) + "\n")


if __name__ == "__main__":
    main(*sys.argv[1:4])
