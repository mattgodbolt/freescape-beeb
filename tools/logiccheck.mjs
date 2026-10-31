// The 6502 logic checked pass by pass against the transcription, headless
// (make logic6502): tools/logiccheck.6502's build on a Master in jsbeeb
// (tools/run6502.mjs), against tools/logictrace.py's traces of
// tools/logic/ with decision 18's fix on.
//
//   node tools/logiccheck.mjs build/logic6502 build/logic6502/trace.json
//
// Each run (a scenario of tests/logic/, or a random walk) starts from the
// game's start, LOGICW and LOGIC loaded afresh and logic_go_init called,
// and after that and after every step every variable of the original's
// (tools/logic/state.py) and every byte of the database must be the
// transcription's. The six words that point into the database point into
// the bank's copy, moved by DB_MOVE. A pass's keys go into the keyboard's
// bitmap as the interrupt leaves it; a pass that ends a minute calls
// logic_go_minute first, as the interrupt would. The arithmetic's cases
// (cross_coord, mul_a_hl and shift6) go through in batches.
//
// It reports the cycles of each pass (logic_pass, from its first
// instruction to its return), by what the pass did: median and max.
// Exits non-zero if anything differs.
import fs from "node:fs";
import path from "node:path";
import { headless } from "./run6502.mjs";

const [dir, tracePath] = process.argv.slice(2);
const trace = JSON.parse(fs.readFileSync(tracePath, "utf8"));
const m = await headless({ symbols: path.join(dir, "symbols.json") });
const sym = (n) => m.sym(n);
const hex = (v, n = 2) => "$" + v.toString(16).toUpperCase().padStart(n, "0");

const LOGIC_BANK = sym("LOGIC_BANK");
const CODE_BANK = sym("LOGIC_CODE_BANK");
const ZXV_ORG = sym("ZXV_ORG");
const ZXV_END = sym("ZXV_END");
const ZX_DB = sym("ZX_DB");
const LOGIC_DB = sym("LOGIC_DB");
const DB_MOVE = sym("DB_MOVE");
const zxv = sym("zxv");
const PTRS = sym("ZXV_PTRS").map((o) => ZXV_ORG + o);
const work = fs.readFileSync(path.join(dir, "LOGICW"));
const bank = fs.readFileSync(path.join(dir, "LOGIC"));
m.load(path.join(dir, "CHECK"), sym("chk_code"));
m.load(path.join(dir, "LOGICC"), 0x8000, CODE_BANK);

let failures = 0;
function fail(msg) {
    if (failures++ < 20) console.log(msg);
}

// --- where each of the original's compared bytes is on the BBC ---------------

const [dbLo, dbHi] = trace.layout.database;
const outside = trace.layout.vars.filter((v) => v.addr < ZXV_ORG || v.addr >= ZXV_END);
const names = new Map(); // ZX address -> the variable's name, for reports
for (const v of trace.layout.vars) for (let i = 0; i < v.size; i++) names.set(v.addr + i, v.size > 1 ? `${v.name}[${i}]` : v.name);
// [zx address, length, bbc address, space] regions
const regions = [[ZXV_ORG, ZXV_END - ZXV_ORG, zxv, "main"]];
for (const v of outside) regions.push([v.addr, v.size, sym(v.name), "main"]);
regions.push([dbLo, dbHi - dbLo, LOGIC_DB, LOGIC_BANK]);
if (dbLo !== ZX_DB || LOGIC_DB + (dbHi - dbLo) !== 0xc000) throw new Error("the database's layout isn't the build's");

function bbcOf(a) {
    for (const [z, n, b, space] of regions) if (a >= z && a < z + n) return [b + a - z, space];
    throw new Error(`${hex(a, 4)} isn't a compared address`);
}

// The expected state: the original's address space as the transcription
// leaves it.
const exp = new Uint8Array(0x10000);
const start = new Uint8Array(0x10000);
for (const [a, v] of trace.start) start[a] = v;

// The 6502's bytes for region r, with the database pointers moved back to
// the original's addresses, so they compare byte for byte.
function got(r) {
    const [z, n, b, space] = r;
    const out = Uint8Array.from(m.read(b, n, space));
    if (z === ZXV_ORG) {
        for (const p of PTRS) {
            const o = p - ZXV_ORG;
            const w = (out[o] | (out[o + 1] << 8)) - DB_MOVE;
            out[o] = w & 0xff;
            out[o + 1] = (w >> 8) & 0xff;
        }
    }
    return out;
}

function compare() {
    const diffs = [];
    for (const r of regions) {
        const [z, n] = r;
        const g = got(r);
        for (let i = 0; i < n; i++) {
            if (g[i] !== exp[z + i]) diffs.push([z + i, exp[z + i], g[i]]);
        }
    }
    return diffs;
}

// The renderer's view of the objects (logic_go_shown): ix_flags, in the
// index's order, must be the flags of the records the original walks, the
// area's (from AreaObjPtr) and then the globals, and the index's records
// those records.
const IX_N = sym("ix_n"), IX_FLAGS = sym("ix_flags"), IX_PL = sym("ix_pl"), IX_PH = sym("ix_ph");
const toZX = (b) => (b >= LOGIC_DB ? b - DB_MOVE : b - zxv + ZXV_ORG);
async function shown(where) {
    await m.call(sym("chk_shown"));
    const word = (a) => exp[a] | (exp[a + 1] << 8);
    const recs = [];
    let p = word(0x8864);
    for (let i = 0; i < exp[0x8863]; i++, p += exp[p + 8]) recs.push(p);
    p = 0x87a5;
    for (let i = 0; i < exp[0x890f]; i++, p += exp[p + 8]) recs.push(p);
    const n = m.peek(IX_N);
    if (n !== recs.length) return fail(`${where}: ${n} objects indexed, not ${recs.length}`);
    for (let i = 0; i < n; i++) {
        const z = toZX(m.peek(IX_PL + i) | (m.peek(IX_PH + i) << 8));
        if (z !== recs[i]) return fail(`${where}: object ${i} indexed at ZX ${hex(z, 4)}, not ${hex(recs[i], 4)}`);
        if (m.peek(IX_FLAGS + i) !== exp[z]) return fail(`${where}: object ${i}'s flags ${hex(m.peek(IX_FLAGS + i))}, not ${hex(exp[z])}`);
    }
    return true;
}

function report(where, diffs) {
    const lines = [`${where}: ${diffs.length} bytes differ (transcription, 6502):`];
    for (const [a, e, g] of diffs.slice(0, 16)) {
        const name = names.get(a) ?? (a >= dbLo ? `Database ${hex(a, 4)}` : `ZX ${hex(a, 4)}`);
        lines.push(`  ${name.padEnd(20)} ${hex(e)}  ${hex(g)}`);
    }
    fail(lines.join("\n"));
}

// --- the runs ----------------------------------------------------------------

const empty = await m.empty();
const cycles = new Map(); // what a pass did -> its cycles
const slowest = []; // [cycles, where], with --slow N
const SLOW = process.argv.includes("--slow") ? Number(process.argv[process.argv.indexOf("--slow") + 1]) : 0;
function note(kind, c, where) {
    if (!cycles.has(kind)) cycles.set(kind, []);
    cycles.get(kind).push(c);
    if (SLOW) {
        slowest.push([c, `${where} (${kind})`]);
        slowest.sort((a, b) => b[0] - a[0]);
        slowest.length = Math.min(slowest.length, SLOW);
    }
}
const ACTIONS = {
    O: "step", 7: "step", K: "step back", 6: "step back", Q: "turn", 5: "turn", W: "turn", 8: "turn",
    P: "look", L: "look", N: "roll", M: "roll", R: "rise", F: "fall", U: "turn round",
    A: "the turn's size", Z: "the turn's size", S: "the step's size", X: "the step's size",
    SPACE: "shooting mode", B: "crosshair", 0: "fire",
};
const SIGHT = new Set(["O", "7", "K", "6", "Q", "5", "W", "8"]);
function kind(rec) {
    if (rec.tick) return "a minute";
    if (rec.names.length > 1) return "several keys";
    const k = rec.names[0];
    let a = ACTIONS[k] ?? "no action";
    if (rec.shoot && SIGHT.has(k)) a = "moving the sight";
    if (["step", "step back", "rise", "fall"].includes(a)) a += rec.jet ? " (jet)" : " (probe)";
    return a;
}

// --profile: sample where the passes spend their cycles, by routine (the
// nearest label below the PC in the section the PC is in), every
// PROFILE_STEP cycles. Slow; for finding what to make faster.
const PROFILE = process.argv.includes("--profile");
const PROFILE_STEP = 37;
const samples = new Map();
const labelsBy = {}; // space -> sorted [address, name]
{
    const all = JSON.parse(fs.readFileSync(path.join(dir, "symbols.json"), "utf8"));
    for (const s of all.assemblies[0].sections) {
        const space = s.name === "Logic" ? "bank4" : s.name === "LogicCode" ? "bank5" : "main";
        for (const [k, v] of Object.entries(s.labels ?? {})) {
            if (k.includes("@") || typeof v.value !== "number") continue;
            (labelsBy[space] ??= []).push([v.value, k]);
        }
    }
    for (const xs of Object.values(labelsBy)) xs.sort((a, b) => a[0] - b[0]);
}
function routineAt(pc) {
    const space = pc >= 0x8000 && pc < 0xc000 ? (m.tm.pagedBank === LOGIC_BANK ? "bank4" : "bank5") : "main";
    const xs = labelsBy[space] ?? [];
    let best = "?";
    for (const [a, k] of xs) {
        if (a > pc) break;
        best = k;
    }
    // a routine's own labels (touch.scan_xo.object) fold into it
    return best.split(".").slice(0, 2).join(".");
}
async function sampled(entry) {
    const done = 0x0144;
    m.ram.set([0x78, 0x20, entry & 0xff, entry >> 8, 0x4c, done & 0xff, done >> 8], 0x0140);
    m.cpu.pc = 0x0140;
    m.cpu.s = 0xff;
    const t0 = m.tm.elapsedCycles;
    while (m.cpu.pc !== done) {
        await m.tm.runFor(PROFILE_STEP);
        const r = routineAt(m.cpu.pc);
        samples.set(r, (samples.get(r) ?? 0) + 1);
    }
    return { marks: [0, m.tm.elapsedCycles - t0] };
}

let passes = 0, steps = 0, runsOk = 0, froze = 0;
const KEYS = sym("keys");
const SCRIPT = sym("CHK_SCRIPT");
for (const r of trace.runs) {
    m.write(sym("LOGIC_WORK"), work);
    m.write(0x8000, bank, LOGIC_BANK);
    exp.set(start);
    await m.call(sym("chk_init"));
    let diffs = compare();
    if (diffs.length) {
        report(`${r.name}: the start`, diffs);
        continue;
    }
    let ok = true;
    for (const rec of r.steps) {
        steps++;
        if (rec.poke) {
            const [a, values] = rec.poke;
            values.forEach((v, i) => {
                const [b, space] = bbcOf(a + i);
                m.poke(b, v, space);
            });
        } else if (rec.fcl) {
            m.write(SCRIPT, rec.fcl);
            m.poke(sym("chk_len"), rec.fcl.length);
            m.poke(sym("ShotFlag"), rec.shot ? 1 : 0);
            await m.call(sym("chk_fcl"));
        } else {
            m.write(KEYS, rec.keys);
            if (rec.tick) await m.call(sym("chk_minute"));
            if (rec.freeze) {
                // The original hangs in this pass, and so must the 6502.
                let returned = true;
                try {
                    await m.call(sym("chk_pass"), { secs: 1 });
                } catch {
                    returned = false;
                }
                if (returned) {
                    fail(`${rec.line}: the transcription hangs here, and the 6502 doesn't`);
                    ok = false;
                } else froze++;
                break;
            }
            const { marks } = PROFILE ? await sampled(sym("chk_pass")) :
                await m.call(sym("chk_pass"), { marks: [sym("logic_pass"), sym("chk_pass_done")] });
            passes++;
            note(kind(rec), marks[1] - marks[0], `${rec.line} ${rec.names.join(" ")}`);
            const result = m.peek(sym("chk_result"));
            if (result !== rec.result) {
                fail(`${rec.line}: logic_pass returned ${result}, not ${rec.result}`);
                ok = false;
                break;
            }
        }
        for (const [a, v] of rec.changes) exp[a] = v;
        diffs = compare();
        const where = `${rec.line} (${rec.names?.join(" ") ?? (rec.fcl ? "fcl" : "poke")})`;
        if (diffs.length) {
            report(where, diffs);
            ok = false;
            break;
        }
        if ((await shown(where)) !== true) {
            ok = false;
            break;
        }
    }
    if (ok) runsOk++;
}
const scenarios = trace.runs.filter((r) => !r.name.startsWith("fuzz-")).length;
console.log(`logic6502: ${trace.runs.length} runs (${scenarios} scenarios, ${trace.runs.length - scenarios} random walks), ` +
    `${steps} steps, ${passes} passes compared; ${trace.runs.length - runsOk} differ` +
    (froze ? `; ${froze} hung where the transcription does` : ""));

// --- the arithmetic ----------------------------------------------------------

const BUF = sym("CHK_BUF"), TOP = sym("CHK_TOP");
async function batch(entry, size, cases, fill, check) {
    const per = Math.floor((TOP - BUF) / size);
    for (let first = 0; first < cases.length; first += per) {
        const n = Math.min(per, cases.length - first);
        const buf = new Uint8Array(n * size);
        for (let i = 0; i < n; i++) buf.set(fill(cases[first + i]), i * size);
        m.write(BUF, buf);
        m.pokew(sym("chk_count"), n);
        await m.call(sym(entry), { secs: 600 });
        const out = m.read(BUF, n * size);
        for (let i = 0; i < n; i++) check(cases[first + i], out.slice(i * size, (i + 1) * size));
    }
}
const w = (v) => [v & 0xff, (v >> 8) & 0xff];
let arithBad = 0;
await batch("chk_cross", sym("CHK_CROSS"), trace.cross,
    ([t, d, dm, s]) => [...w(t), ...w(d), ...w(dm), ...w(s), 0, 0],
    ([t, d, dm, s, want], out) => {
        const g = out[8] | (out[9] << 8);
        if (g !== want) { arithBad++; fail(`cross_coord t ${hex(t, 4)} d ${hex(d, 4)} D ${hex(dm, 4)} start ${hex(s, 4)}: ${hex(g, 4)}, not ${hex(want, 4)}`); }
    });
await batch("chk_mul", sym("CHK_MUL"), trace.mul,
    ([a, hl]) => [a, ...w(hl), 0, 0, 0, 0, 0],
    ([a, hl, p, s6], out) => {
        const gp = out[3] | (out[4] << 8) | (out[5] << 16), gs = out[6] | (out[7] << 8);
        if (gp !== p || gs !== s6) { arithBad++; fail(`mul_a_hl ${hex(a)} x ${hex(hl, 4)}: ${hex(gp, 6)} ${hex(gs, 4)}, not ${hex(p, 6)} ${hex(s6, 4)}`); }
    });
console.log(`logic6502: arithmetic, ${trace.cross.length} cross_coord and ${trace.mul.length} mul_a_hl cases; ${arithBad} differ`);

// --- the cycles --------------------------------------------------------------

const median = (xs) => { const s = [...xs].sort((a, b) => a - b); return s[Math.floor(s.length / 2)]; };
const all = [...cycles.values()].flat();
if (all.length) {
    console.log(`logic6502: cycles a pass (logic_pass): median ${median(all)}, max ${Math.max(...all)}, over ${all.length} passes; by what the pass did:`);
    for (const [k, xs] of [...cycles.entries()].sort((a, b) => median(b[1]) - median(a[1]))) {
        console.log(`  ${k.padEnd(20)} ${String(xs.length).padStart(5)} passes, median ${String(median(xs)).padStart(6)}, max ${String(Math.max(...xs)).padStart(6)}`);
    }
}
for (const [c, where] of slowest) console.log(`  slow: ${c} cycles, ${where}`);
if (PROFILE) {
    const total = [...samples.values()].reduce((a, b) => a + b, 0);
    console.log(`logic6502: where the passes' cycles go (${total} samples):`);
    for (const [k, n] of [...samples.entries()].sort((a, b) => b[1] - a[1]).slice(0, 40))
        console.log(`  ${(100 * n / total).toFixed(1).padStart(5)}%  ${k}`);
}
console.log(`logic6502: ${failures ? "FAILED" : "ok"}`);
process.exit(failures ? 1 : 0);
