#!/usr/bin/env node
// The rasteriser's check: every scene of tools/rasterscenes.py through the
// 6502 (src/raster.6502, src/writer.6502), headless, its view's bytes against
// the model's (tools/model/raster.py, writer.py) exactly.
//
//   node tools/rastercheck.mjs BUILD [--scene TEXT] [--json OUT] [--verbose]
//
// BUILD holds the check build (RCODE, RRUNS, symbols.json) and scenes.json
// (mk/raster.mk). For each scene it writes the faces, patterns and horizon
// into rs_*, fills the screen with bytes the frame must change (the view's
// with each expected byte's complement), calls check_frame, and checks:
//   - the view's bytes are the model's, in the screen ACCCON's X chose;
//   - nothing else of either screen changed;
//   - nothing was written outside the rasteriser's own memory (its zero
//     page, the stack, its sections) and the view;
//   - rs_overflow is set exactly when the model's pools overflowed.
// It reports each scene's cycles, split by what ran (an instruction-level
// profile over the routines' labels), and with --json writes them with the
// model's counts, for the cost model (docs/research/raster.md).
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
const scenes = JSON.parse(fs.readFileSync(`${dir}/scenes.json`, "utf8")).scenes.filter(
    (s) => !only || s.name.includes(only),
);

const m = await headless({ symbols: symFile });
const S = (name) => m.sym(name);
m.load(`${dir}/RCODE`, sections.RasterCode.org);
m.load(`${dir}/RRUNS`, sections.RasterRuns.org, "hazel");

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
];
for (const name of ["RasterCode", "RasterIn", "RasterRuns", "RasterWork", "RasterState"]) {
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
const runsEnd = sections.RasterRuns.guard;
const bucketOf = new Map();
const bucket = (a) => {
    let b = bucketOf.get(a);
    if (b === undefined) {
        b = "other";
        if (a < runsEnd) for (const [at, name] of marks) if (a >= at) b = name;
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

const results = [];
let failures = 0;
const totals = {};
for (const [i, s] of scenes.entries()) {
    writeScene(s);
    const want = s.view.map((row) => Buffer.from(row, "hex"));
    // Alternate the screens, so both are drawn into.
    const shadow = i % 2 === 1;
    const space = shadow ? "shadow" : "main";
    const other = shadow ? "main" : "shadow";
    m.poke(S("check_acccon"), ACCCON_Y | (shadow ? ACCCON_X : 0));
    // Every byte of the view starts as its expected value's complement, and
    // the rest of both screens as something the frame mustn't touch.
    const before = { [space]: [], [other]: [] };
    for (const sp of [space, other]) {
        const fill = new Uint8Array(0x8000 - SCREEN);
        for (let a = 0; a < fill.length; a++) fill[a] = (a * 7 + (sp === space ? 0x5a : 0xa5)) & 255;
        m.write(SCREEN, fill, sp);
        before[sp] = fill;
    }
    for (let y = 0; y < VIEW_H; y++)
        for (let c = 0; c < VIEW_BYTES; c++) m.poke(addr(y, c), want[y][c] ^ 0xff, space);

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
        const got = m.read(addr(y, 0) - 0, 1, space);
        for (let c = 0; c < VIEW_BYTES; c++) {
            const b = m.peek(addr(y, c), space);
            if (b !== want[y][c]) {
                problems.push(`line ${y} byte ${c}: &${b.toString(16)} not &${want[y][c].toString(16)}`);
                break;
            }
        }
        void got;
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
    if (counts.bytes !== s.counts.bytes) problems.push(`${counts.bytes} view bytes written, the model's ${s.counts.bytes}`);

    for (const [k, v] of Object.entries(prof)) totals[k] = (totals[k] || 0) + v;
    const line = `${s.name.padEnd(28)} ${String(cycles).padStart(7)} c` +
        `  runs ${String(counts.runs).padStart(4)} joins ${String(counts.joins).padStart(4)}`;
    if (problems.length) {
        failures++;
        console.log(`FAIL ${line}`);
        for (const p of problems) console.log(`     ${p}`);
    } else if (verbose) {
        console.log(`ok   ${line}  ` + Object.entries(prof).sort().map(([k, v]) => `${k} ${v}`).join(" "));
    }
    results.push({ name: s.name, cycles, profile: prof, measured: counts, counts: s.counts, ok: !problems.length });
}

const sum = results.reduce((t, r) => t + r.cycles, 0);
console.log(`${results.length - failures}/${results.length} scenes match the model; ` +
    `${sum} cycles in all, by part: ` +
    Object.entries(totals).sort((a, b) => b[1] - a[1]).map(([k, v]) => `${k} ${(100 * v / sum).toFixed(1)}%`).join(", "));

// The cost model: cycles against the model's counts, by least squares over
// the scenes that didn't overflow.
const TERMS = [
    ["lines", (c) => VIEW_H - c.full_lines],    // lines the background fills
    ["face-lines", (c) => c.face_lines],
    ["runs", (c) => c.runs],
    ["bytes", (c) => c.whole],                  // whole bytes, through the row runs
    ["joins", (c) => c.joins],                  // bytes two runs share
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
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ terms: TERMS.map(([t]) => t), fit: fitted, results }, null, 1) + "\n");
process.exit(failures ? 1 : 0);
