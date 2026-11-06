#!/usr/bin/env node
// The object pipeline's check: the 6502 (src/area.6502, matrix, objects,
// transform, clip, order) headless on every case of tools/objectcases.py,
// each stage's output against the model's exactly.
//
//   node tools/objectcheck.mjs BUILD [--db build/logic6502/LOGIC] [--cases CASES.json]
//                              [--areas build/gen/areas.json] [--entrance]
//                              [--view TEXT] [--verbose] [--json OUT]
//                              [--profile | --profile-walks | --profile-turns] [--floor] [--candidates]
//
// BUILD holds the check build (OCODE, into the front end's bank, OANDY, into
// ANDY, OMORE, OCHECK, OAREA, OCONST, OMATHS, OTABLES, ACONV, symbols.json)
// and, unless --cases names them, cases.json (mk/objects.mk);
// --db is the logic's database bank (LOGIC), which area_enter builds each
// area's working copy from (tools/areacheck.mjs checks that). It checks:
//   - stage 1: every matrix of cases.json's (matrix_build);
//   - stage 6's crossings alone: every one of cases.json's (clip_cut);
//   - for each view, through objects_frame:
//     - stage 2: the candidates, their seen faces and the vertices those use;
//     - stage 3: each candidate's camera-space vertices, read as
//       transform_object returns, but those the model passes over as
//       beyond the view's sides (render.beyond_view), which mustn't be
//       transformed;
//     - stages 4-6: each candidate's drawn faces, colour and polygon;
//     - stage 7: the drawn objects' order;
//     - the output, the faces nearest first, as the rasteriser reads them;
//     - the work no output need show (a clip's step later cut away): the
//       lines the cone made, and the polygon objects' vertices projected;
//   - that nothing outside the pipeline's own memory was written, and
//     nothing in sideways RAM run but its own code, the bank's with the
//     bank paged and ANDY's with ANDY.
// A build that takes what's hidden from the logic's flags (OBJ_LOGIC) gets
// them in ix_flags as the logic would have them at the area's start (from
// --areas): each hidden object's invisible or destroyed, each shown one's
// flags but those, and ob_state saying every slot is hidden, so a pass that
// read the wrong flags, or ob_state, would change the candidates.
// It reports each stage's cycles, median and maximum over the entrance
// views and over all the views: an instruction-level count, each
// instruction's cycles going to the innermost stage routine on the stack
// (STAGES below). With --json it writes each view's.
//
// Exits non-zero when anything disagrees.
import fs from "node:fs";
import { headless } from "./run6502.mjs";

const args = process.argv.slice(2);
const dir = args[0];
if (!dir) {
    console.error(
        "usage: objectcheck.mjs BUILD [--db LOGIC] [--cases CASES.json] [--areas AREAS.json] [--entrance] " +
            "[--view TEXT] [--verbose] [--json OUT]",
    );
    process.exit(2);
}
const opt = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : undefined;
};
const only = opt("--view");
const jsonOut = opt("--json");
const verbose = args.includes("--verbose");
const dbFile = opt("--db") ?? "build/logic6502/LOGIC";

const symFile = `${dir}/symbols.json`;
const sections = {};
const sizes = {};
const andyNames = new Set(); // ObjAndy's labels, which share their addresses with the bank's
for (const a of JSON.parse(fs.readFileSync(symFile, "utf8")).assemblies)
    for (const s of a.sections) {
        if (!s.name) continue;
        sections[s.name] = s.attributes;
        sizes[s.name] = s.size;
        if (s.name === "ObjAndy") for (const k of Object.keys(s.labels ?? {})) andyNames.add(k);
    }
const cases = JSON.parse(fs.readFileSync(opt("--cases") ?? `${dir}/cases.json`, "utf8"));
const entranceOnly = args.includes("--entrance");
const views = cases.views.filter(
    (v) => (!only || v.name.includes(only)) && (!entranceOnly || /^a\d+-e\d+(-w\d+)?$/.test(v.name)),
);

const m = await headless({ symbols: symFile });
const S = (name) => m.sym(name);
const has = (name) => name in m.syms;
const space = (a) => (a >= 0xc000 && a < 0xe000 ? "hazel" : "main");
// The front end's code is where the live disc has it: ObjCode in its bank,
// ObjAndy in ANDY over that bank's first 4K (decision 52), ObjMore in main
// RAM.
const OBJ_BANK = S("OBJ_BANK");
const codeSpace = { ObjCode: OBJ_BANK, ObjAndy: "andy" };
for (const [file, section] of [["OCODE", "ObjCode"], ["OANDY", "ObjAndy"], ["OCONST", "ObjConst"],
                               ["OAREA", "AreaCode"], ["OMATHS", "ObjMaths"], ["OTABLES", "ObjTables"],
                               ["OMORE", "ObjMore"], ["OCHECK", "ObjCheck"]])
    if (sections[section])
        m.load(`${dir}/${file}`, sections[section].org, codeSpace[section] ?? space(sections[section].org));
// An instruction's place, as a key: ANDY's addresses apart from the bank's.
const ANDY_KEY = 0x10000;
const keyOf = (pc) => (m.paged(pc) === "andy" ? pc + ANDY_KEY : pc);
const K = (name) => (andyNames.has(name) ? S(name) + ANDY_KEY : S(name));
m.load(`${dir}/ACONV`, sections.AreaConv.org, has("AREA_CONV_BANK") ? S("AREA_CONV_BANK") : undefined);
m.load(dbFile, 0x8000, S("AREA_DB_BANK"));
const logic = has("OBJ_LOGIC");
const layout = logic ? JSON.parse(fs.readFileSync(opt("--areas") ?? "build/gen/areas.json", "utf8")) : null;

const s8 = (v) => (v & 0x80 ? v - 256 : v);
const s16 = (lo, hi) => {
    const v = lo | (hi << 8);
    return v & 0x8000 ? v - 0x10000 : v;
};
const s24 = (b0, b1, b2) => {
    const v = b0 | (b1 << 8) | (b2 << 16);
    return v & 0x800000 ? v - 0x1000000 : v;
};
const arr = (name, i) => m.peek(S(name) + i, space(S(name)));

let failures = 0;
const fail = (what) => {
    failures++;
    if (args.includes("--quiet") ? failures <= 8 : failures <= 40)
        console.log(`FAIL ${args.includes("--quiet") ? what.slice(0, 200) : what}`);
};

// --- Where the pipeline may write: its zero page, the stack, its own
// sections (its code patches itself: the bank's with the bank paged, and
// ANDY's with ANDY), romsel and its copy.
const allowed = [
    [0x10, 0x90],
    [0x100, 0x200],
    [0xf4, 0xf5],
    [0xfe30, 0xfe31],
];
allowed.push([S("acccon"), S("acccon") + 1]);
for (const name of ["ObjArea", "ObjWork", "ObjCache", "ObjOut", "ObjMemo", "ObjBound", "ObjMore", "ObjCheck", "AreaKeep"]) {
    const a = sections[name];
    if (a) allowed.push([a.org, a.guard]);
}
const code = Object.entries(codeSpace).filter(([name]) => sections[name])
    .map(([name, p]) => ({ lo: sections[name].org, hi: sections[name].org + sizes[name], guard: sections[name].guard, p }));
const badWrites = [];
m.tm.processor.debugWrite.add((addr) => {
    if (!allowed.some(([lo, hi]) => addr >= lo && addr < hi) &&
        !code.some((c) => addr >= c.lo && addr < c.guard && m.paged(addr) === c.p)) {
        if (badWrites.length < 10) badWrites.push(addr);
    }
});
// ... and run nothing in sideways RAM but its own code: the bank's, with
// the bank paged, and ANDY's, with ANDY (what ANDY's code calls in the bank
// must be past its first 4K, which ANDY hides).
const strayRuns = [];
const ranOwn = (pc) => code.some((c) => pc >= c.lo && pc < c.hi && m.paged(pc) === c.p);

// --- The stages, for the cycle count: each instruction's cycles go to the
// innermost of these routines being run (entered and not yet returned
// from), or to "frame" outside them all.
const STAGES = [
    ["matrix_update", "matrix"],
    ["camera_setup", "pass"],
    ["object_pass", "pass"],
    ["transform_setup", "transform"],
    ["transform_object", "transform"],
    ["transform_fill", "transform"],
    ["bound_object", "transform"],
    ["near_clip", "near"],
    ["guard_clip", "guard"],
    ["project", "project"],
    ["project_z", "project"],
    ["project_y", "project"],
    ["vertex_pass", "vertices"],
    ["poly_face", "faces"],
    ["draw_face3d", "faces3d"],
    ["cone_face", "cone"],
    ["clip2d", "clip2d"],
    ["dedupe", "clip2d"],
    ["drawable", "drawable"],
    ["draw_object", "faces"],
    ["sort_objects", "sort"],
    ["emit_faces", "emit"],
];
const entries = new Map();
for (const [label, stage] of STAGES) if (has(label)) entries.set(K(label), stage);
const STAGE_NAMES = [...new Set(STAGES.map(([, s]) => s)), "frame"];

// --profile: every instruction's cycles to the routine it's in (the last
// label at or below it that isn't inside a scope), over all the views;
// --profile-walks, over the walks' steps alone (the frames that only move).
// --fine: by every label, scoped ones too; --top N: the N largest.
const walksOnly = args.includes("--profile-walks");
// --profile-turns: over the entrance views alone (each a turn: the cache
// refilled); --profile-views RE: over the views whose names RE matches
// (-y[1-9]: the yaw sweeps' first turns)
const turnsOnly = args.includes("--profile-turns");
const viewsRe = opt("--profile-views") ? new RegExp(opt("--profile-views")) : null;
const profile = args.includes("--profile") || walksOnly || turnsOnly || viewsRe ? new Map() : null;
const fine = args.includes("--fine");
let profiling = false;
const routines = [];
if (profile) {
    const all = JSON.parse(fs.readFileSync(symFile, "utf8"));
    for (const a of all.assemblies)
        for (const s of a.sections)
            if ((s.name === "ObjCode" || s.name === "ObjAndy" || s.name === "ObjMore") && s.labels)
                for (const [k, v] of Object.entries(s.labels))
                    if (!k.includes("@") && (fine || !k.includes(".")))
                        routines.push([v.value + (s.name === "ObjAndy" ? ANDY_KEY : 0), k]);
    routines.sort((a, b) => a[0] - b[0]);
}
const routineOf = (pc) => {
    let lo = 0;
    let hi = routines.length - 1;
    if (hi < 0 || pc < routines[0][0]) return "?";
    while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (routines[mid][0] <= pc) lo = mid;
        else hi = mid - 1;
    }
    return routines[lo][1];
};

let tally = null; // stage -> cycles, while counting
const stack = [];
let lastPc = -1; // (keyOf's)
let lastCycles = 0;
let current = "frame";
const watches = new Map(); // keyOf's address -> callback, run as the instruction is reached
m.tm.processor.debugInstruction.add((at) => {
    if (!tally) return false;
    const cpu = m.tm.processor;
    const now = m.tm.elapsedCycles;
    const pc = keyOf(at);
    if (at >= 0x8000 && at < 0xc000 && !ranOwn(at) && strayRuns.length < 10)
        strayRuns.push(`&${at.toString(16)} (${m.paged(at) === "andy" ? "ANDY" : `bank ${m.paged(at)}`})`);
    if (lastPc >= 0) {
        tally[current] = (tally[current] || 0) + (now - lastCycles);
        if (fill) {
            if (cpu.s > fill.sp) {
                fills[fill.kind] = fills[fill.kind] || { n: 0, cycles: 0 };
                fills[fill.kind].n++;
                fills[fill.kind].cycles += now - fill.t;
                fill = null;
            }
        }
        if (inFloor) floorTally[current] = (floorTally[current] || 0) + (now - lastCycles);
        if (profiling) {
            const r = routineOf(lastPc);
            profile.set(r, (profile.get(r) || 0) + (now - lastCycles));
        }
    }
    lastPc = pc;
    lastCycles = now;
    while (stack.length && cpu.s > stack[stack.length - 1].sp) stack.pop();
    const stage = entries.get(pc);
    if (stage) stack.push({ stage, sp: cpu.s });
    current = stack.length ? stack[stack.length - 1].stage : "frame";
    const w = watches.get(pc);
    if (w) w();
    if (fillsWanted && fillsOn && pc === fillAt && !fill) {
        const kind = ["cuboid", "rectangle", "generic", "sensor"][arr("ob_flags", cpu.x) & 3];
        fill = { kind: kind === "generic" ? `generic, ${arr("ob_nv", cpu.x)} vertices` : kind, t: now, sp: cpu.s };
    }
    const k = callees.get(pc);
    if (k) calls[k] = (calls[k] || 0) + 1;
    // each candidate's cycles, from its turn in objects_frame's loop to the
    // next's: the floor's apart (decision 8a), and (--candidates) those that
    // draw nothing
    if (pc === candidateAt || pc === sortAt) {
        if (cand) cands.push({ slot: cand.slot, cycles: now - cand.t, drew: m.peek(S("tf_n"), space(S("tf_n"))) > cand.faces });
        cand = pc === candidateAt ? { t: now, slot: arr("cd_obj", cpu.x), faces: m.peek(S("tf_n"), space(S("tf_n"))) } : null;
    }
    if (pc === candidateAt) inFloor = floorSlot !== null && arr("cd_obj", cpu.x) === floorSlot;
    else if (pc === sortAt) inFloor = false;
    return false;
});
// --fills: each transform_fill's cycles (its bounds' too), by the object's
// kind, over the entrance views (each a turn)
const fillsWanted = args.includes("--fills");
const fillAt = has("transform_fill") ? K("transform_fill") : -1;
let fill = null;
let fillsOn = false;
const fills = {};
let inFloor = false;
let floorTally = {};
let floorSlot = null;
let cand = null; // the candidate being drawn: its start and the faces drawn before it
let cands = []; // each candidate's cycles, and whether it drew a face
const candidateAt = has("of_candidate") ? K("of_candidate") : -1;
const sortAt = has("of_sort") ? K("of_sort") : -1;

// The calls a frame makes of the arithmetic's routines, for the cost model
// (docs/research/objects.md): each counted as its first instruction runs.
const CALLEES = ["rdiv", "umul32", "frac16", "lerp", "near_point", "guard_point", "clip_cut", "project",
                 "project_z", "project_y", "band_test", "vertex_shared", "vertex_up", "poly_face", "draw_face3d",
                 "cone_face", "edge_line", "image_line", "image_line.none", "cone_pass", "cone_cut", "smul16",
                 "cone_mul",
                 "umul16", "fill_point", "fill_edge", "transform_fill"];
const callees = new Map();
for (const c of CALLEES) if (has(c)) callees.set(K(c), c);
let calls = {};

async function counted(entry) {
    tally = {};
    calls = {};
    floorTally = {};
    inFloor = false;
    cand = null;
    cands = [];
    stack.length = 0;
    lastPc = -1;
    const r = await m.call(entry, { secs: 30 });
    if (lastPc >= 0) tally[current] = (tally[current] || 0) + (m.tm.elapsedCycles - lastCycles);
    const t = tally;
    tally = null;
    return { total: r.total, stages: t, calls, floor: floorTally, cands };
}

// --- Stage 1: the matrices.
await m.call(S("check_init"));
let matrixBad = 0;
for (const [yaw, pitch, roll, want] of cases.matrices) {
    m.poke(S("mat_angles"), yaw);
    m.poke(S("mat_angles") + 1, pitch);
    m.poke(S("mat_angles") + 2, roll);
    await m.call(S("check_matrix"));
    const got = m.read(S("mat"), 9).map(s8);
    if (got.join() !== want.join()) {
        matrixBad++;
        fail(`matrix ${yaw},${pitch},${roll}: ${got} want ${want}`);
    }
}
console.log(`stage 1: ${cases.matrices.length} matrices, ${matrixBad} wrong`);

// --- The 2D clip's crossings, alone (clip_cut): edge cases no view need reach.
let cutBad = 0;
for (const [fp, fq, po, qo, want] of cases.crossings ?? []) {
    [fp, fq, po, qo].forEach((v, k) => m.pokew(S("cut_args") + 2 * k, v & 0xffff));
    await m.call(S("check_cut"));
    const got = s16(m.peek(S("cut_args") + 8), m.peek(S("cut_args") + 9));
    if (got !== want) {
        cutBad++;
        fail(`crossing fp ${fp} fq ${fq} po ${po} qo ${qo}: ${got} want ${want}`);
    }
}
console.log(`stage 6: ${(cases.crossings ?? []).length} crossings of the 2D clip, ${cutBad} wrong`);

// --- The views.
const full = has("of_transformed");
const results = [];
let area = -1;
const counts = { views: 0, cands: 0, verts: 0, faces: 0, out: 0, passed: 0 };
for (const view of views) {
    if (view.area !== area) {
        m.poke(S("check_area"), view.area);
        await m.call(S("check_enter"));
        area = view.area;
        if (logic) {
            // the logic's flags for its index (the area's records, then the
            // globals'): the hidden invisible or destroyed by turns, the
            // shown with every other bit set; and ob_state, which mustn't be
            // read, hiding everything
            const hidden = [...layout.areas[area].hidden, ...layout.globals.hidden];
            hidden.forEach((h, i) => m.poke(S("ix_flags") + i, h ? (i & 1 ? 0x20 : 0x40) : 0x9f));
            for (let s = 0; s < S("N_OBJ"); s++) m.poke(S("ob_state") + s, 0x80);
        }
    }
    const [x, y, z, yaw, pitch, roll] = view.camera;
    m.pokew(S("cam_x"), x);
    m.pokew(S("cam_y"), y);
    m.pokew(S("cam_z"), z);
    m.poke(S("cam_yaw"), yaw);
    m.poke(S("cam_pitch"), pitch);
    m.poke(S("cam_roll"), roll);
    const seen = [];
    if (full) {
        watches.set(K("of_transformed"), () => {
            const c = m.peek(S("of_cand"));
            const slot = arr("cd_obj", c);
            const vmask = arr("cd_vmask", c);
            const verts = {};
            for (let j = 0; j < 8; j++) {
                if (!(vmask & (1 << j))) continue;
                const g = (p) => [0, 1, 2].map((b) => arr(`${p}${b}`, j));
                verts[j] = [s24(...g("vx")), s24(...g("vy")), s24(...g("vz"))];
            }
            seen.push({ slot, verts, off: null });
        });
        // the vertex pass: which of a polygon's vertices it found it can't project
        watches.set(K("draw_object.passed"), () => {
            seen[seen.length - 1].off = m.peek(S("vp_off"));
        });
    }
    badWrites.length = 0;
    strayRuns.length = 0;
    floorSlot = view.floor ?? null;
    profiling = profile !== null && (!walksOnly || /-w\d+$/.test(view.name)) &&
        (!turnsOnly || /^a\d+-e\d+$/.test(view.name)) && (!viewsRe || viewsRe.test(view.name));
    fillsOn = /^a\d+-e\d+$/.test(view.name);
    const { total, stages, calls: made, floor, cands: drawing } = await counted(S(full ? "check_frame" : "check_pass"));
    const name = view.name;
    if (badWrites.length) fail(`${name}: wrote outside its memory at ${badWrites.map((a) => "&" + a.toString(16)).join(" ")}`);
    if (strayRuns.length) fail(`${name}: ran outside its code at ${strayRuns.join(" ")}`);

    // stage 1 again, as the frame built it
    const mat = m.read(S("mat"), 9).map(s8);
    if (mat.join() !== view.matrix.join()) fail(`${name}: matrix ${mat} want ${view.matrix}`);

    // stage 2: the candidates
    const n = m.peek(S("cd_n"));
    const cands = [];
    for (let i = 0; i < n; i++) cands.push([arr("cd_obj", i), arr("cd_mask", i), arr("cd_vmask", i)]);
    const want = view.cands.map((c) => [c.slot, c.mask, c.vmask]);
    if (JSON.stringify(cands) !== JSON.stringify(want)) {
        fail(`${name}: candidates ${JSON.stringify(cands)} want ${JSON.stringify(want)}`);
        results.push({ name, total, stages });
        continue;
    }
    counts.views++;
    counts.cands += n;
    if (full) {
        // stage 3: camera-space vertices, of every candidate but those passed
        // over as beyond the view's sides, which aren't transformed
        let t = 0;
        for (let i = 0; i < view.cands.length; i++) {
            const w = view.cands[i];
            if (w.culled) {
                if (seen[t] && seen[t].slot === w.slot) {
                    fail(`${name}: candidate ${i} transformed, beyond the view's sides`);
                    t++;
                }
                continue;
            }
            const g = seen[t++];
            if (!g || g.slot !== w.slot) {
                fail(`${name}: candidate ${i} not transformed`);
                continue;
            }
            if (w.off !== null && g.off !== w.off)
                fail(`${name}: slot ${w.slot} vertices off the band ${g.off} want ${w.off}`);
            for (const [j, v] of Object.entries(w.verts)) {
                counts.verts++;
                if (!g.verts[j] || g.verts[j].join() !== v.join())
                    fail(`${name}: slot ${w.slot} vertex ${j} ${g.verts[j]} want ${v}`);
            }
        }
        if (t !== seen.length) fail(`${name}: ${seen.length} candidates transformed, want ${t}`);
        counts.passed += view.cands.filter((w) => w.culled).length;
        // stages 4-6: each candidate's drawn faces, then 7 and the output
        const faceAt = (f, base) => {
            const nv = arr(`${base}_fn`, f);
            const v0 = arr(`${base}_fv`, f);
            const poly = [];
            for (let k = 0; k < nv; k++) {
                const v = v0 + k;
                poly.push([s16(arr("out_vxl", v), arr("out_vxh", v)), s16(arr("out_vyl", v), arr("out_vyh", v))]);
            }
            return [arr(`${base}_fc`, f), poly];
        };
        const dn = m.peek(S("dl_n"));
        const drawn = new Map();
        for (let d = 0; d < dn; d++) {
            const f0 = arr("dl_f0", d);
            const nf = arr("dl_nf", d);
            const faces = [];
            for (let k = 0; k < nf; k++) faces.push(faceAt(f0 + k, "tf"));
            drawn.set(arr("dl_obj", d), faces);
        }
        for (const w of view.cands) {
            const got = drawn.get(w.slot) || [];
            counts.faces += w.faces.length;
            if (JSON.stringify(got) !== JSON.stringify(w.faces))
                fail(`${name}: slot ${w.slot} faces ${JSON.stringify(got)} want ${JSON.stringify(w.faces)}`);
        }
        const order = [];
        for (let d = 0; d < dn; d++) order.push(arr("dl_obj", arr("dl_ord", d)));
        if (order.join() !== view.order.join()) fail(`${name}: order ${order} want ${view.order}`);
        const on = arr("out_nf", 0);
        const out = [];
        for (let f = 0; f < on; f++) out.push(faceAt(f, "out"));
        counts.out += on;
        if (JSON.stringify(out) !== JSON.stringify(view.out))
            fail(`${name}: output ${JSON.stringify(out)} want ${JSON.stringify(view.out)}`);
        // the work no output need show: the cone's lines (from their planes or
        // from images: an image_line that found no direction is no line), and
        // the vertices projected, each by one of the projection's entries (by
        // way of vertex_shared, vertex_up or vertex_shared.full)
        const lines = (made.edge_line || 0) + (made.image_line || 0) - (made["image_line.none"] || 0);
        const projected = (made.project || 0) + (made.project_z || 0) + (made.project_y || 0);
        if (lines !== view.work.lines) fail(`${name}: the cone made ${lines} lines, want ${view.work.lines}`);
        if (projected !== view.work.projected)
            fail(`${name}: ${projected} vertices projected, want ${view.work.projected}`);
    }
    if (verbose) console.log(name, total, JSON.stringify(stages));
    const idle = drawing.filter((c) => !c.drew);
    results.push({ name, total, stages, calls: made, floor, entrance: /^a\d+-e\d+$/.test(name),
                   nothing: { n: idle.length, of: drawing.length, cycles: idle.reduce((a, c) => a + c.cycles, 0) },
                   ...(args.includes("--candidates") ? { cands: drawing } : {}) });
}

// --- The cycles.
const median = (v) => {
    const s = [...v].sort((a, b) => a - b);
    const n = s.length;
    return n ? (n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2) : 0;
};
// the 90th percentile: the smallest value at least 90% of the views are at or under
const p90 = (v) => {
    const s = [...v].sort((a, b) => a - b);
    return s.length ? s[Math.ceil(0.9 * s.length) - 1] : 0;
};
// --quiet: each group's total alone; --compare OLD.json: each stage's
// median / p90 / max / mean against an earlier run's --json, view for view.
const quiet = args.includes("--quiet");
const compareFile = opt("--compare");
const before = compareFile ? new Map(JSON.parse(fs.readFileSync(compareFile, "utf8")).map((r) => [r.name, r])) : null;
const mean = (v) => Math.round(v.reduce((a, b) => a + b, 0) / (v.length || 1));
const report = (label, rows) => {
    if (!rows.length) return;
    console.log(`${label}: ${rows.length} views, cycles median / p90 / max${before ? " / mean, before and now" : ""}`);
    const line = (name, vals, old) => {
        const top = Math.max(...vals);
        const who = rows[vals.indexOf(top)].name;
        if (old) {
            const f = (v) => `${median(v)} / ${p90(v)} / ${Math.max(...v)} / ${mean(v)}`;
            const d = mean(vals) - mean(old);
            if (Math.max(...vals, ...old) > 0)
                console.log(`  ${name.padEnd(10)} ${f(old).padEnd(34)} ${f(vals).padEnd(34)} (${d >= 0 ? "+" : ""}${d})`);
            return;
        }
        console.log(
            `  ${name.padEnd(10)} ${String(median(vals)).padStart(8)} ${String(p90(vals)).padStart(8)} ` +
                `${String(top).padStart(8)}  ${who}`,
        );
    };
    const was = before ? rows.map((r) => before.get(r.name)).filter(Boolean) : null;
    if (was && was.length === rows.length) {
        for (const st of STAGE_NAMES) line(st, rows.map((r) => r.stages[st] || 0), was.map((r) => r.stages[st] || 0));
        line("total", rows.map((r) => r.total), was.map((r) => r.total));
        return;
    }
    if (quiet) {
        line("total", rows.map((r) => r.total));
        return;
    }
    for (const st of STAGE_NAMES) line(st, rows.map((r) => r.stages[st] || 0));
    line("total", rows.map((r) => r.total));
    if (rows[0].calls) {
        console.log(`  calls a view, median / max:`);
        for (const c of CALLEES) line(` ${c}`, rows.map((r) => (r.calls && r.calls[c]) || 0));
    }
    if (args.includes("--candidates") && rows[0].nothing) {
        // the candidates that draw no face: how many, and their cycles (from
        // their turn in objects_frame's loop to the next's)
        const sum = (f) => rows.reduce((a, r) => a + f(r), 0);
        console.log(`  candidates that draw nothing: ${sum((r) => r.nothing.n)} of ${sum((r) => r.nothing.of)}; ` +
            `their cycles a view, median / p90 / max, and their share of all`);
        line("nothing", rows.map((r) => r.nothing.cycles));
        console.log(`  ${"share".padEnd(10)} ${(100 * sum((r) => r.nothing.cycles) / sum((r) => r.total)).toFixed(1)}%`);
    }
    if (args.includes("--floor") && rows[0].floor) {
        console.log(`  the floor's share (decision 8a): median / max of its cycles, and of the stage's`);
        for (const st of STAGE_NAMES) {
            const f = rows.map((r) => r.floor[st] || 0);
            const all = rows.map((r) => r.stages[st] || 0);
            const share = all.reduce((a, b) => a + b, 0) ? f.reduce((a, b) => a + b, 0) / all.reduce((a, b) => a + b, 0) : 0;
            console.log(`  ${st.padEnd(10)} ${String(median(f)).padStart(8)} ${String(Math.max(...f)).padStart(8)}  ${(100 * share).toFixed(0)}%`);
        }
        const ft = rows.map((r) => Object.values(r.floor).reduce((a, b) => a + b, 0));
        const share = ft.reduce((a, b) => a + b, 0) / rows.map((r) => r.total).reduce((a, b) => a + b, 0);
        console.log(`  ${"total".padEnd(10)} ${String(median(ft)).padStart(8)} ${String(Math.max(...ft)).padStart(8)}  ${(100 * share).toFixed(0)}%`);
    }
};
report("entrance views, each a turn (the cache refilled)", results.filter((r) => r.entrance));
report("their walks, each a step (the cache kept)", results.filter((r) => /-w\d+$/.test(r.name)));
// a yaw sweep's views after its first: each a turn of one step, 5 degrees,
// from the view before, the camera where it was (the disc's turn: the cache
// refilled, the sort's memory kept)
report("yaw sweeps, each a 5-degree turn", results.filter((r) => /-y([1-9]|\d\d+)$/.test(r.name)));
report("all views", results);
console.log(
    `checked ${counts.views} views: ${counts.cands} candidates (${counts.passed} passed over as beyond the view), ` +
        `${counts.verts} vertices, ${counts.faces} faces, ${counts.out} output faces`,
);
if (profile) {
    const total = [...profile.values()].reduce((a, b) => a + b, 0);
    const n = walksOnly ? results.filter((r) => /-w\d+$/.test(r.name)).length
        : turnsOnly ? results.filter((r) => r.entrance).length
        : viewsRe ? results.filter((r) => viewsRe.test(r.name)).length : results.length;
    console.log(`profile: cycles by routine over ${n} ${walksOnly ? "walk steps" : turnsOnly ? "turns" : "views"}`);
    for (const [r, c] of [...profile.entries()].sort((a, b) => b[1] - a[1]).slice(0, Number(opt("--top") ?? 40)))
        console.log(`  ${r.padEnd(20)} ${String(Math.round(c / n)).padStart(9)} a view  ${((100 * c) / total).toFixed(1)}%`);
}
if (fillsWanted) {
    const turns = results.filter((r) => r.entrance).length;
    console.log(`fills over ${turns} turns: by kind, fills and cycles a turn, and cycles a fill`);
    for (const [k, f] of Object.entries(fills).sort((a, b) => b[1].cycles - a[1].cycles))
        console.log(`  ${k.padEnd(22)} ${(f.n / turns).toFixed(2).padStart(6)} ${String(Math.round(f.cycles / turns)).padStart(7)}` +
            ` ${String(Math.round(f.cycles / f.n)).padStart(6)}`);
}
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(results, null, 1) + "\n");
if (failures) {
    console.log(`${failures} failures`);
    process.exit(1);
}
console.log("objects: ok");
