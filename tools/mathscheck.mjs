// The maths checked on the 65C12, headless (make maths): src/maths.6502's
// mul and dot3 and src/project.6502's project, project_z and project_y,
// built by tools/mathscheck.6502, against tools/model/maths.py exactly,
// with their cycles.
//
//   node tools/mathscheck.mjs build/maths [--quick | --full]
//
// - mul: every coefficient by every high byte with the low bytes that
//   carry most and every low byte with those high bytes, and random pairs
//   with mul_set before each, against v * m (the model's mul is exactly
//   that: tools/mkmaths.py checks it); --full takes all 2^24 pairs, which
//   is too slow for make check;
// - dot3 and project: tools/mkmaths.py's cases (cases.json), with the
//   model's answers, edges and random; project_z and project_y each after
//   a project, against the model's project of the same vertex;
// - every entrance view's projected vertices (views.json, the model's
//   own), each by project, then shared by project_y and project_z, timed
//   call by call: a vertex's and a view's cycles;
// - cycles: from the JSR to the return, over a spread of cases each,
//   reported as minimum, mean and maximum.
//
// Cases go through in batches: the build's loops run a buffer of records
// at a time. --quick takes fewer of mul's pairs.
import fs from "node:fs";
import path from "node:path";
import { headless } from "./run6502.mjs";

const dir = process.argv[2];
const quick = process.argv.includes("--quick");
const full = process.argv.includes("--full");
const m = await headless({ symbols: path.join(dir, "symbols.json") });
m.load(path.join(dir, "CODE"), m.sym("chk_code"));
m.load(path.join(dir, "HAZEL"), 0xc000, "hazel");
const cases = JSON.parse(fs.readFileSync(path.join(dir, "cases.json"), "utf8"));
// The entrance views' vertices (tools/mkmaths.py --views).
const views = JSON.parse(fs.readFileSync(path.join(dir, "views.json"), "utf8"));

const BUF = m.sym("CHK_BUF");
const TOP = m.sym("CHK_TOP");
const s8 = (v) => (v & 0x80 ? v - 256 : v);
const u24 = (a) => a[0] | (a[1] << 8) | (a[2] << 16);
const s24 = (a) => { const v = u24(a); return v & 0x800000 ? v - 0x1000000 : v; };
const s16 = (a) => { const v = a[0] | (a[1] << 8); return v & 0x8000 ? v - 0x10000 : v; };
const bytes = (v, n) => Array.from({ length: n }, (_, i) => (v >> (8 * i)) & 0xff);

let failures = 0;
function fail(msg) {
    if (failures++ < 10) console.log(msg);
}

// Run records through entry, a buffer at a time: fill(i) gives record i's
// input bytes, check(i, out) its output bytes.
async function batch(entry, size, n, fill, inLen, check) {
    const per = Math.floor((TOP - BUF) / size);
    for (let first = 0; first < n; first += per) {
        const count = Math.min(per, n - first);
        const buf = new Uint8Array(count * size);
        for (let i = 0; i < count; i++) buf.set(fill(first + i), i * size);
        m.write(BUF, buf);
        m.pokew(m.sym("chk_count"), count);
        await m.call(m.sym(entry), { secs: 600 });
        const out = m.read(BUF, count * size);
        for (let i = 0; i < count; i++) check(first + i, out.slice(i * size + inLen, (i + 1) * size));
    }
}

const stats = () => ({ n: 0, sum: 0, min: Infinity, max: -Infinity });
function add(st, c) {
    st.n++; st.sum += c; st.min = Math.min(st.min, c); st.max = Math.max(st.max, c);
}
const show = (name, st) =>
    console.log(`  ${name.padEnd(12)} min ${st.min}, mean ${(st.sum / st.n).toFixed(1)}, max ${st.max} cycles (${st.n} calls)`);

// Time one call: the record at BUF, marks round the routine's JSR.
async function timed(entry, marks, record) {
    m.write(BUF, record);
    const { marks: t } = await m.call(m.sym(entry), { marks: marks.map((k) => m.sym(k)) });
    return t.slice(1).map((v, i) => v - t[i]);
}

// --- mul ---------------------------------------------------------------------

// Every coefficient by the coordinates vs, mul_set once each (chk_mulv).
async function mulAll(vs) {
    const size = m.sym("CHK_MULV");
    const per = Math.floor((TOP - BUF) / size);
    const buf = new Uint8Array(per * size);
    for (let c = -128; c < 128; c++) {
        m.poke(m.sym("chk_m"), c);
        for (let first = 0; first < vs.length; first += per) {
            const count = Math.min(per, vs.length - first);
            for (let i = 0; i < count; i++) {
                buf[i * size] = vs[first + i] & 0xff;
                buf[i * size + 1] = (vs[first + i] >> 8) & 0xff;
            }
            m.write(BUF, buf.subarray(0, count * size));
            m.pokew(m.sym("chk_count"), count);
            await m.call(m.sym("chk_mulv"), { secs: 600 });
            const out = m.read(BUF, count * size);
            for (let i = 0; i < count; i++) {
                const o = i * size + 2;
                let got = out[o] | (out[o + 1] << 8) | (out[o + 2] << 16);
                if (got & 0x800000) got -= 0x1000000;
                const v = vs[first + i];
                if (got !== v * c) fail(`mul ${v} * ${c}: ${got}, want ${v * c}`);
            }
        }
    }
    return 256 * vs.length;
}

const MUL = m.sym("CHK_MUL");
{
    // By default every high byte with the low bytes that carry most, and
    // every low byte with those high bytes; --full, every coordinate.
    let vs = [];
    if (full) {
        for (let v = -32768; v < 32768; v++) vs.push(v);
    } else {
        const edge = [0, 1, 2, 127, 128, 129, 254, 255];
        for (let b = 0; b < 256; b++)
            for (const e of edge) vs.push(((b << 8) | e) << 16 >> 16, ((e << 8) | b) << 16 >> 16);
        if (quick) vs = vs.filter((_, i) => i % 13 === 0);
    }
    const n = await mulAll(vs);
    // and mul_set before every product, on random pairs (chk_mul)
    const rnd = (() => { let s = 1987; return () => (s = (s * 1103515245 + 12345) >>> 0) / 2 ** 32; })();
    const pairs = Array.from({ length: quick ? 2000 : 30000 }, () => [Math.floor(rnd() * 256) - 128, Math.floor(rnd() * 65536) - 32768]);
    await batch("chk_mul", MUL, pairs.length,
        (i) => [pairs[i][0] & 0xff, ...bytes(pairs[i][1], 2), 0, 0, 0],
        3,
        (i, out) => {
            const [c, v] = pairs[i], got = s24(out);
            if (got !== v * c) fail(`mul_set, mul ${v} * ${c}: ${got}, want ${v * c}`);
        });
    console.log(`mul: ${n} products${full ? ", every one" : ""}; ${pairs.length} more, mul_set before each`);
    const set = stats(), mul = stats();
    for (const c of [-128, -64, -1, 0, 1, 64, 127])
        for (const v of [-32768, -1, 0, 1, 8191, 32767, 12345, -12345]) {
            const [ts, tm] = await timed("chk_mul1", ["chk_mul1_set", "chk_mul1_go", "chk_mul1_done"], [c & 0xff, ...bytes(v, 2)]);
            add(set, ts); add(mul, tm);
        }
    show("mul_set", set);
    show("mul", mul);
}

// --- dot3 --------------------------------------------------------------------

const DOT = m.sym("CHK_DOT");
{
    const d = cases.dot;
    await batch("chk_dot", DOT, d.length,
        (i) => { const [a, b, c, x, y, z] = d[i]; return [a & 0xff, b & 0xff, c & 0xff, ...bytes(x, 2), ...bytes(y, 2), ...bytes(z, 2), 0, 0, 0]; },
        9,
        (i, out) => {
            const got = s24(out), want = d[i][6];
            if (got !== want) fail(`dot3 ${d[i].slice(0, 6)}: ${got}, want ${want}`);
        });
    console.log(`dot3: ${d.length} cases`);
    const set = stats(), dot = stats();
    for (let i = 0; i < d.length; i += Math.ceil(d.length / 1500)) {
        const [a, b, c, x, y, z] = d[i];
        const [ts, td] = await timed("chk_dot1", ["chk_dot1_set", "chk_dot1_go", "chk_dot1_done"],
            [a & 0xff, b & 0xff, c & 0xff, ...bytes(x, 2), ...bytes(y, 2), ...bytes(z, 2)]);
        add(set, ts); add(dot, td);
    }
    show("dot_set", set);
    show("dot3", dot);
}

// --- project -----------------------------------------------------------------

const PROJ = m.sym("CHK_PROJ");
{
    const p = cases.proj;
    await batch("chk_proj", PROJ, p.length,
        (i) => { const [x, y, z] = p[i]; return [...bytes(x, 3), ...bytes(y, 3), ...bytes(z, 3), 0, 0, 0, 0]; },
        9,
        (i, out) => {
            const sx = s16(out.slice(0, 2)), sy = s16(out.slice(2, 4));
            const [x, y, z, wx, wy] = p[i];
            if (sx !== wx || sy !== wy) fail(`project ${x} ${y} ${z}: (${sx}, ${sy}), want (${wx}, ${wy})`);
        });
    console.log(`project: ${p.length} cases`);
    // Cycles over the views' own ranges: |X/Z| up to 4 (cases.json's second
    // band), and over everything.
    const near = stats(), all = stats();
    const band = p.filter(([x, y, z]) => z <= 742000 && Math.abs(x) <= 4 * z && Math.abs(y) <= 2 * z);
    for (let i = 0; i < band.length; i += Math.ceil(band.length / 3000)) {
        const [x, y, z] = band[i];
        const [t] = await timed("chk_proj1", ["chk_proj1_go", "chk_proj1_done"], [...bytes(x, 3), ...bytes(y, 3), ...bytes(z, 3)]);
        add(near, t);
    }
    for (let i = 0; i < p.length; i += Math.ceil(p.length / 3000)) {
        const [x, y, z] = p[i];
        const [t] = await timed("chk_proj1", ["chk_proj1_go", "chk_proj1_done"], [...bytes(x, 3), ...bytes(y, 3), ...bytes(z, 3)]);
        add(all, t);
    }
    show("project", near);
    show("project*", all);
    console.log("  (project: |X| <= 4 Z, |Y| <= 2 Z, Z <= 742000; project*: every case)");
}

// --- project_z and project_y, after project ----------------------------------

const SHARE = m.sym("CHK_SHARE"), SHARE_IN = m.sym("CHK_SHARE_IN");
{
    const sh = cases.share;
    const input = (i) => sh[i].slice(0, 6).flatMap((v) => bytes(v, 3));
    await batch("chk_share", SHARE, sh.length,
        (i) => [...input(i), ...new Array(SHARE - SHARE_IN).fill(0)],
        SHARE_IN,
        (i, out) => {
            const got = [0, 2, 4, 6, 8].map((k) => s16(out.slice(k, k + 2)));
            const want = sh[i].slice(6);
            if (got.some((v, k) => v !== want[k])) fail(`project, project_z, project_y ${sh[i].slice(0, 6)}: ${got}, want ${want}`);
        });
    console.log(`project_z, project_y: ${sh.length} cases, each after project`);
    const z = stats(), y = stats();
    const band = sh.filter(([x, , zz, x2, y2, y3]) => zz <= 742000 && Math.abs(x2) <= 4 * zz && Math.abs(y2) <= 2 * zz && Math.abs(y3) <= 2 * zz);
    for (let i = 0; i < band.length; i += Math.ceil(band.length / 1500)) {
        const [tz, , ty] = await timed("chk_share1", ["chk_share1_z", "chk_share1_zdone", "chk_share1_y", "chk_share1_ydone"],
            band[i].slice(0, 6).flatMap((v) => bytes(v, 3)));
        add(z, tz); add(y, ty);
    }
    show("project_z", z);
    show("project_y", y);
    console.log("  (|X| <= 4 Z, |Y| <= 2 Z, Z <= 742000)");
}

// --- every entrance view's vertices, unshared and shared ----------------------

// A schedule: each of an object's vertices by project (op 0), or by
// project_z (1) after a vertex at its Z, or project_y (2) after one at its
// X and Z. "each": every vertex by project, in the model's order; "columns":
// an object's vertices at one (X, Z) one after the other, as a level
// camera's vertical edges are; "shared": and at one Z.
const SCHED = m.sym("CHK_SCHED");
{
    function schedule(objects, how) {
        const out = [];
        for (const obj of objects) {
            let vs = obj;
            if (how !== "each") {
                const key = how === "columns" ? (v) => [v[0], v[2]] : (v) => [v[2], v[0]];
                vs = [...obj].sort((a, b) => key(a)[0] - key(b)[0] || key(a)[1] - key(b)[1]);
            }
            let last = null;
            for (const v of vs) {
                let op = 0;
                if (how === "each") op = 0;
                else if (last && v[2] === last[2] && v[0] === last[0]) op = 2;
                else if (last && how === "shared" && v[2] === last[2]) op = 1;
                out.push([op, ...v]);
                last = v;
            }
        }
        return out;
    }
    const sites = { 0: ["chk_sched_p", "chk_sched_pd"], 1: ["chk_sched_z", "chk_sched_zd"], 2: ["chk_sched_y", "chk_sched_yd"] };
    const per = Math.floor((TOP - BUF) / SCHED);
    const summary = {};
    for (const how of ["each", "columns", "shared"]) {
        const perVertex = [], perView = [], ops = [0, 0, 0], byOp = [[], [], []];
        for (const view of views) {
            const recs = schedule(view.objects, how);
            let total = 0;
            for (let first = 0; first < recs.length; first += per) {
                const chunk = recs.slice(first, first + per);
                const buf = new Uint8Array(chunk.length * SCHED);
                chunk.forEach(([op, x, y, z], i) => buf.set([op, ...bytes(x, 3), ...bytes(y, 3), ...bytes(z, 3)], i * SCHED));
                m.write(BUF, buf);
                m.pokew(m.sym("chk_count"), chunk.length);
                const marks = chunk.flatMap(([op]) => sites[op].map((s) => m.sym(s)));
                const { marks: t } = await m.call(m.sym("chk_sched"), { marks, secs: 600 });
                const out = m.read(BUF, chunk.length * SCHED);
                chunk.forEach(([op, x, y, z, wx, wy], i) => {
                    const c = t[2 * i + 1] - t[2 * i];
                    perVertex.push(c); total += c; ops[op]++; byOp[op].push(c);
                    const o = out.slice(i * SCHED + 10, i * SCHED + 14);
                    const sx = s16(o.slice(0, 2)), sy = s16(o.slice(2, 4));
                    if (sy !== wy || (op !== 2 && sx !== wx)) fail(`${view.view} ${how} op ${op} ${x} ${y} ${z}: (${sx}, ${sy}), want (${wx}, ${wy})`);
                });
            }
            perView.push(total);
        }
        const med = (a) => { const s = [...a].sort((p, q) => p - q), n = s.length; return n % 2 ? s[(n - 1) / 2] : (s[n / 2 - 1] + s[n / 2]) / 2; };
        summary[how] = { perVertex, perView, ops };
        console.log(`  ${how.padEnd(8)} a vertex: median ${med(perVertex)}, mean ${(perVertex.reduce((p, q) => p + q, 0) / perVertex.length).toFixed(1)}, max ${Math.max(...perVertex)}; ` +
            `a view: median ${med(perView)}, max ${Math.max(...perView)}`);
        const names = ["project", "project_z", "project_y"];
        console.log("           " + byOp.map((a, k) => a.length ? `${a.length} by ${names[k]} (median ${med(a)}, max ${Math.max(...a)})` : "")
            .filter((s) => s).join(", "));
    }
    console.log(`  (the ${views.length} entrance views' ${summary.each.perVertex.length} projected vertices, cycles from each JSR to its return)`);
}

// --- the real divide, for comparison (docs/research/maths.md) ----------------

{
    // A coordinate's quotient FX |X| / Z, FX rounded, over the views' range.
    const fx = 1268, st = stats();
    const band = cases.proj.filter(([x, , z]) => z <= 742000 && Math.abs(x) <= 4 * z);
    for (let i = 0; i < band.length; i += Math.ceil(band.length / 1000)) {
        const [x, , z] = band[i];
        const n = BigInt(Math.abs(x)) * BigInt(fx);
        const nb = Array.from({ length: 5 }, (_, k) => Number((n >> BigInt(8 * k)) & 0xffn));
        const [t] = await timed("chk_div1", ["chk_div1_go", "chk_div1_done"], [...nb, ...bytes(z, 3)]);
        add(st, t);
        const q = m.peek(BUF + 8) | (m.peek(BUF + 9) << 8);
        if (BigInt(q) !== n / BigInt(z)) fail(`div ${n} / ${z}: ${q}, want ${n / BigInt(z)}`);
    }
    show("divide", st);
    console.log("  (div_q, tools/mathscheck.6502: one coordinate's 40/24-bit divide, without FX |X|)");
}

console.log(failures ? `mathscheck: ${failures} wrong` : "mathscheck: all agree with the model");
process.exit(failures ? 1 : 0);
