#!/usr/bin/env node
// The rasteriser's check: every scene of tools/rasterscenes.py through the
// 6502 (src/raster.6502, src/writer.6502), headless, its view's bytes against
// the model's (tools/model/raster.py, writer.py) exactly.
//
//   node tools/rastercheck.mjs BUILD [--scenes FILE] [--scene TEXT] [--json OUT] [--verbose]
//
// BUILD holds the check build (RCODE, RRUNS, symbols.json) and scenes.json
// (mk/raster.mk); --scenes names another scene file. For each scene it
// writes the faces, patterns and horizon into rs_*, forgets what the screens
// held, fills the screen with bytes the frame must change (the view's with
// each expected byte's complement), calls check_frame, and checks:
//   - the view's bytes are the model's, in the screen ACCCON's X chose, and
//     as many were written as the model's counts say;
//   - nothing else of either screen changed;
//   - nothing was written outside the rasteriser's own memory (its zero
//     page, the stack, its sections) and the view;
//   - rs_overflow is set exactly when the model's pools overflowed.
// Then each sequence of frames goes into alternate screens without
// forgetting, each frame checked the same way: what the 6502 leaves alone
// must be what's wanted. It reports each scene's cycles, split by what ran
// (an instruction-level profile over the routines' labels), and the cost
// model fitted to them; --json writes them with the model's counts
// (docs/research/raster.md).
//
// Exits non-zero when any scene disagrees.
import fs from "node:fs";
import { headless } from "./run6502.mjs";

const args = process.argv.slice(2);
const dir = args[0];
if (!dir) {
    console.error("usage: rastercheck.mjs BUILD [--scene TEXT] [--json OUT] [--verbose]");
    process.exit(2);
}
const opt = (name) => {
    const i = args.indexOf(name);
    return i >= 0 ? args[i + 1] : undefined;
};
const only = opt("--scene");
const jsonOut = opt("--json");
const verbose = args.includes("--verbose");

const symFile = `${dir}/symbols.json`;
const sections = {};
for (const a of JSON.parse(fs.readFileSync(symFile, "utf8")).assemblies)
    for (const s of a.sections) if (s.name) sections[s.name] = s.attributes;
const all = JSON.parse(fs.readFileSync(opt("--scenes") || `${dir}/scenes.json`, "utf8"));
const scenes = all.scenes.filter((s) => !only || s.name.includes(only));
const sequences = (all.sequences || []).filter((q) => !only || q.name.includes(only));

const m = await headless({ symbols: symFile });
const S = (name) => m.sym(name);
// Each section's file into the space its address is in: main RAM, the
// rasteriser's sideways bank, or HAZEL.
const BANK = m.sym("RASTER_BANK");
for (const [name, a] of Object.entries(sections)) {
    if (!a.filename) continue;
    const space = a.org < 0x8000 ? "main" : a.org < 0xc000 ? BANK : "hazel";
    m.load(`${dir}/${a.filename}`, a.org, space);
}

const VIEW_W = S("VIEW_W");
const VIEW_H = S("VIEW_H");
const VIEW_BYTES = S("VIEW_BYTES");
const VIEW_ADDR = S("VIEW_ADDR");
const SCREEN = S("SCREEN");
const SCREEN_ROW = S("SCREEN_ROW");
const ACCCON_X = S("ACCCON_X");
const ACCCON_Y = S("ACCCON_Y");
const addr = (y, c) => VIEW_ADDR + Math.floor(y / 8) * SCREEN_ROW + 8 * c + (y % 8);

// Where the frame may write: its zero page, the stack, its own sections
// (its code patches itself, and the row runs take their plants), ACCCON,
// and the view.
const allowed = [
    [0x00, 0x90],
    [0x100, 0x200],
    [S("acccon"), S("acccon") + 1],
    [S("romsel"), S("romsel") + 1],
];
for (const name of ["RasterCheck", "RasterCode", "RasterIn", "RasterRuns", "RasterWork", "RasterState"]) {
    const a = sections[name];
    allowed.push([a.org, a.guard]);
}
const viewAddrs = new Set();
for (let y = 0; y < VIEW_H; y++) for (let c = 0; c < VIEW_BYTES; c++) viewAddrs.add(addr(y, c));
const writable = (a) => viewAddrs.has(a) || allowed.some(([lo, hi]) => a >= lo && a < hi);

// The profile's buckets: each executed address goes to the last of these
// labels at or below it.
const BUCKETS = [
    ["check", "check_init"],
    ["frame", "raster_init"],
    ["row", "row_setup"],
    ["run", "put_run"],
    ["join", "put_bnd"],
    ["frame", "writer_init"],
    ["face", "raster_face"],
    ["face", "seg_end"],
    // the line loop's copies: which chain is left, the insertion, the
    // chains' steps, the next line
    ...[0, 1, 2, 3].flatMap((k) => [
        ["span", `loop${k}`],
        ["insert", `chk_end${k}`],
        ["step", `step${k}`],
        ["next", `next${k}`],
    ]),
    ["edge", "patch_steps"],
    ["bg", "raster_background"],
    ["horizon", "horizon_split"],
    ["bytes", "rr_rows"],
];
const marks = BUCKETS.map(([b, l]) => [S(l), b]).sort((p, q) => p[0] - q[0]);
const bucketOf = new Map();
const bucket = (a) => {
    let b = bucketOf.get(a);
    if (b === undefined) {
        b = "other";
        if (a < 0xc000) for (const [at, name] of marks) if (a >= at) b = name;
        bucketOf.set(a, b);
    }
    return b;
};

// Instruction counts at a few addresses: the runs entered, the shared bytes.
const counted = { runs: S("put_run.jsr"), joins: S("put_bnd") };

await m.call(S("check_init"));
const stub = await m.empty();

function writeScene(s) {
    const patterns = [];
    const pid = (p) => {
        const key = p.join(",");
        let i = patterns.findIndex((q) => q.join(",") === key);
        if (i < 0) {
            i = patterns.length;
            patterns.push(p);
        }
        return i;
    };
    const sky = pid(s.sky);
    const ground = pid(s.ground);
    if (s.faces.length > S("RS_FACES")) throw new Error(`${s.name}: too many faces`);
    let v = 0;
    s.faces.forEach((f, i) => {
        m.poke(S("rs_fn") + i, f.vertices.length);
        m.poke(S("rs_fv") + i, v);
        m.poke(S("rs_fc") + i, pid(f.pattern));
        for (const [x, y] of f.vertices) {
            m.poke(S("rs_vxl") + v, x & 255);
            m.poke(S("rs_vxh") + v, x >> 8);
            m.poke(S("rs_vyl") + v, y & 255);
            m.poke(S("rs_vyh") + v, y >> 8);
            v++;
        }
    });
    if (v > S("RS_VERTICES")) throw new Error(`${s.name}: too many vertices`);
    if (patterns.length > S("RS_PATTERNS")) throw new Error(`${s.name}: too many patterns`);
    patterns.forEach((p, i) => m.write(S("rs_pat") + 4 * i, p));
    m.poke(S("rs_nfaces"), s.faces.length);
    m.poke(S("rs_sky"), sky);
    m.poke(S("rs_ground"), ground);
    const h = s.horizon;
    m.poke(S("rs_horizon"), h ? 1 : 0);
    if (h) {
        m.pokew(S("rs_hx"), h[0] & 0xffff);
        m.pokew(S("rs_hy"), h[1] & 0xffff);
        m.poke(S("rs_hdx"), h[2] & 255);
        m.poke(S("rs_hdy"), h[3] & 255);
    }
}

// One frame of scene s into a screen (shadow or not), checked: the view's
// bytes are the model's; nothing else of either screen changed; nothing was
// written outside the rasteriser's memory; rs_overflow is the model's. With
// fresh, the screens are forgotten first and the view starts as each
// expected byte's complement, so every byte must be written (and the count
// written must be the model's).
async function frame(s, shadow, fresh) {
    writeScene(s);
    const want = s.view.map((row) => Buffer.from(row, "hex"));
    const space = shadow ? "shadow" : "main";
    const other = shadow ? "main" : "shadow";
    m.poke(S("check_acccon"), ACCCON_Y | (shadow ? ACCCON_X : 0));
    if (fresh) {
        await m.call(S("check_forget"));
        for (const sp of [space, other]) {
            const fill = new Uint8Array(0x8000 - SCREEN);
            for (let a = 0; a < fill.length; a++) fill[a] = (a * 7 + (sp === space ? 0x5a : 0xa5)) & 255;
            m.write(SCREEN, fill, sp);
        }
        for (let y = 0; y < VIEW_H; y++)
            for (let c = 0; c < VIEW_BYTES; c++) m.poke(addr(y, c), want[y][c] ^ 0xff, space);
    }
    const before = { [space]: m.read(SCREEN, 0x8000 - SCREEN, space), [other]: m.read(SCREEN, 0x8000 - SCREEN, other) };

    // Profile: each instruction's cycles to its routine's bucket.
    const prof = {};
    const counts = { runs: 0, joins: 0, bytes: 0 };
    let prevAddr = null;
    let prevT = 0;
    const strays = [];
    const onInstr = m.cpu.debugInstruction.add((a) => {
        const now = m.tm.elapsedCycles;
        if (prevAddr !== null) {
            const b = bucket(prevAddr);
            prof[b] = (prof[b] || 0) + (now - prevT);
        }
        prevAddr = a;
        prevT = now;
        if (a === counted.runs) counts.runs++;
        else if (a === counted.joins) counts.joins++;
        return false;
    });
    const onWrite = m.cpu.debugWrite.add((a) => {
        if (viewAddrs.has(a)) counts.bytes++;
        else if (!writable(a) && strays.length < 8) strays.push(a);
        return false;
    });
    const { total } = await m.call(S("check_frame"));
    onInstr.remove();
    onWrite.remove();
    const cycles = total - stub;

    const problems = [];
    for (let y = 0; y < VIEW_H && problems.length < 4; y++) {
        for (let c = 0; c < VIEW_BYTES; c++) {
            const b = m.peek(addr(y, c), space);
            if (b !== want[y][c]) {
                problems.push(`line ${y} byte ${c}: &${b.toString(16)} not &${want[y][c].toString(16)}`);
                break;
            }
        }
    }
    for (const sp of [space, other]) {
        const now = m.read(SCREEN, 0x8000 - SCREEN, sp);
        for (let a = 0; a < now.length; a++) {
            const at = SCREEN + a;
            if (sp === space && viewAddrs.has(at)) continue;
            if (now[a] !== before[sp][a]) {
                problems.push(`${sp} screen &${at.toString(16)} changed`);
                break;
            }
        }
    }
    if (strays.length) problems.push(`wrote outside its memory: ${strays.map((a) => "&" + a.toString(16)).join(" ")}`);
    const overflow = m.peek(S("rs_overflow")) !== 0;
    if (overflow !== s.counts.overflow) problems.push(`rs_overflow ${overflow}, the model's ${s.counts.overflow}`);
    if (fresh && counts.bytes !== s.counts.bytes) problems.push(`${counts.bytes} view bytes written, the model's ${s.counts.bytes}`);
    return { cycles, prof, counts, problems };
}

const report = (label, r) => {
    const line = `${label.padEnd(28)} ${String(r.cycles).padStart(7)} c` +
        `  runs ${String(r.counts.runs).padStart(4)} joins ${String(r.counts.joins).padStart(4)}` +
        ` bytes ${String(r.counts.bytes).padStart(5)}`;
    if (r.problems.length) {
        failures++;
        console.log(`FAIL ${line}`);
        for (const p of r.problems) console.log(`     ${p}`);
    } else if (verbose) {
        console.log(`ok   ${line}  ` + Object.entries(r.prof).sort().map(([k, v]) => `${k} ${v}`).join(" "));
    }
};

// Each scene alone, the screens alternating so both are drawn into.
const results = [];
let failures = 0;
const totals = {};
for (const [i, s] of scenes.entries()) {
    const r = await frame(s, i % 2 === 1, true);
    report(s.name, r);
    for (const [k, v] of Object.entries(r.prof)) totals[k] = (totals[k] || 0) + v;
    results.push({ name: s.name, cycles: r.cycles, profile: r.prof, measured: r.counts, counts: s.counts, ok: !r.problems.length });
}
const sum = results.reduce((t, r) => t + r.cycles, 0);
console.log(`${results.length - failures}/${results.length} scenes match the model; ` +
    `${sum} cycles in all, by part: ` +
    Object.entries(totals).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${(100 * v / sum).toFixed(1)}%`).join(", "));

// The sequences: frames in turn into alternate screens, each keeping what
// was drawn into it two frames before.
const seqResults = [];
let seqFailures = 0;
for (const q of sequences) {
    const before = failures;
    const cycles = [];
    const written = [];
    for (const [t, s] of q.frames.entries()) {
        const r = await frame(s, t % 2 === 1, t === 0);
        report(`${q.name} frame ${t}`, r);
        cycles.push(r.cycles);
        written.push(r.counts.bytes);
    }
    if (failures > before) seqFailures++;
    seqResults.push({ name: q.name, cycles, written, alone: q.frames.map((s) => s.counts.bytes) });
    console.log(`  ${q.name.padEnd(10)} cycles ${cycles.join(" ")}; bytes written ${written.join(" ")}`);
}
console.log(`${sequences.length - seqFailures}/${sequences.length} sequences match the model frame by frame`);

// The cost model: cycles against the model's counts, by least squares over
// the scenes that didn't overflow.
const TERMS = [
    ["lines", (c) => VIEW_H - c.full_lines],    // lines the background fills
    ["face-lines", (c) => c.face_rows],         // every line of every face's range
    ["runs", (c) => c.runs],                    // pieces of faces and of background
    ["bytes", (c) => c.bytes],                  // whole bytes and shared ones
    ["edges", (c) => c.edges],
];
const fit = (rows) => {
    const n = TERMS.length;
    const A = Array.from({ length: n }, () => new Array(n + 1).fill(0));
    for (const r of rows) {
        const x = TERMS.map(([, f]) => f(r.counts));
        for (let i = 0; i < n; i++) {
            for (let j = 0; j < n; j++) A[i][j] += x[i] * x[j];
            A[i][n] += x[i] * r.cycles;
        }
    }
    for (let i = 0; i < n; i++) {
        let p = i;
        for (let k = i + 1; k < n; k++) if (Math.abs(A[k][i]) > Math.abs(A[p][i])) p = k;
        [A[i], A[p]] = [A[p], A[i]];
        for (let k = 0; k < n; k++) {
            if (k === i || A[i][i] === 0) continue;
            const f = A[k][i] / A[i][i];
            for (let j = i; j <= n; j++) A[k][j] -= f * A[i][j];
        }
    }
    const coef = A.map((row, i) => row[n] / row[i]);
    const errs = rows.map((r) => {
        const x = TERMS.map(([, f]) => f(r.counts));
        return (x.reduce((t, v, i) => t + v * coef[i], 0) - r.cycles) / r.cycles;
    });
    const rms = Math.sqrt(errs.reduce((t, e) => t + e * e, 0) / errs.length);
    return { coef, rms, worst: Math.max(...errs.map(Math.abs)) };
};
const fitted = fit(results.filter((r) => !r.counts.overflow));
console.log("cost model: cycles = " + TERMS.map(([name], i) => `${fitted.coef[i].toFixed(1)} ${name}`).join(" + ") +
    ` (rms error ${(100 * fitted.rms).toFixed(1)}%, worst ${(100 * fitted.worst).toFixed(1)}%)`);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ terms: TERMS.map(([t]) => t), fit: fitted, results, sequences: seqResults }, null, 1) + "\n");
process.exit(failures ? 1 : 0);
