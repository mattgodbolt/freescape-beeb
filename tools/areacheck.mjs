#!/usr/bin/env node
// The working copy's check: src/area.6502's area_init and area_enter,
// headless, building the globals' slots and every area's from Driller's
// database where the player logic keeps it, held to tools/mkareas.py's
// working copy (its model), byte for byte.
//
//   node tools/areacheck.mjs BUILD [--areas build/gen/areas.json]
//                            [--db build/logic6502/LOGIC] [--verbose]
//
// BUILD holds the objects' check build (mk/objects.mk). The harness loads
// it and the logic's database bank (--db, LOGIC, into AREA_DB_BANK), and
// fails (exit status 1) unless:
// - the build's AREA_DB and AREA_DB_BANK are the logic build's LOGIC_DB and
//   LOGIC_BANK (its symbols.json, beside --db);
// - after area_init, the globals' slots are mkareas.py's: every array's
//   first G_ entries;
// - after area_enter for each area in turn, with the working copy past the
//   globals' (all of it, with OBJ_LOGIC, which builds them again) filled
//   with junk first: the globals' slots, with ob_ix their places in the
//   logic's index after the area's records; the area's, every array's
//   entries from G_ for its counts; ob_n and ar_counts; and, without
//   OBJ_LOGIC, ob_state, each slot's F_HIDDEN;
// - nothing outside the working copy, ObjWork, the sort's memory (ObjMemo),
//   zero page, the stack, romsel
//   and its copy (&F4) was written.
// It reports the cycles of area_init and of area_enter, median and most
// over the areas.
import fs from "node:fs";
import path from "node:path";
import { headless } from "./run6502.mjs";
import { loadSymbols } from "./symbols.mjs";

const args = process.argv.slice(2);
const dir = args[0];
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    return i < 0 ? dflt : args[i + 1];
};
if (!dir) {
    console.error("usage: areacheck.mjs BUILD [--areas AREAS.json] [--db LOGIC] [--verbose] [--profile [--fine] [--top N]]");
    process.exit(2);
}
const areasFile = opt("areas", "build/gen/areas.json");
const dbFile = opt("db", "build/logic6502/LOGIC");
const verbose = args.includes("--verbose");
const layout = JSON.parse(fs.readFileSync(areasFile, "utf8"));

const symFile = `${dir}/symbols.json`;
const sections = {};
for (const a of JSON.parse(fs.readFileSync(symFile, "utf8")).assemblies)
    for (const s of a.sections) if (s.name) sections[s.name] = s.attributes;
const m = await headless({ symbols: symFile });
const S = (name) => m.sym(name);
const has = (name) => name in m.syms;
const logic = has("OBJ_LOGIC");

let failures = 0;
const fail = (what) => {
    if (++failures <= 40) console.log(`areas: FAIL ${what}`);
};

// The logic's bank, where the logic build puts its database.
const logicSyms = loadSymbols(path.join(path.dirname(dbFile), "symbols.json"));
for (const [ours, theirs] of [["AREA_DB", "LOGIC_DB"], ["AREA_DB_BANK", "LOGIC_BANK"]]) {
    if (!(theirs in logicSyms)) fail(`no ${theirs} in the logic build's symbols`);
    else if (logicSyms[theirs] !== S(ours)) fail(`${ours} is ${S(ours)}, the logic's ${theirs} ${logicSyms[theirs]}`);
}

const space = (a) => (a >= 0xc000 && a < 0xe000 ? "hazel" : "main");
const load = (file, section, where) => {
    if (!sections[section]) return;
    const org = sections[section].org;
    m.load(`${dir}/${file}`, org, where ?? space(org));
};
// (the front end's code where the live disc has it: its bank, ANDY over
// that bank's first 4K, and main RAM)
load("OCODE", "ObjCode", S("OBJ_BANK"));
load("OANDY", "ObjAndy", "andy");
load("OCONST", "ObjConst");
load("OAREA", "AreaCode");
load("OMATHS", "ObjMaths");
load("OTABLES", "ObjTables");
load("OMORE", "ObjMore");
load("OCHECK", "ObjCheck");
load("ACONV", "AreaConv", has("AREA_CONV_BANK") ? S("AREA_CONV_BANK") : undefined);
m.load(dbFile, 0x8000, S("AREA_DB_BANK"));

// --profile: every instruction's cycles over all the areas' area_enter to
// the label it's in (--fine: scoped labels too), the conversion's and the
// pipeline's code apart
const profile = args.includes("--profile") ? new Map() : null;
let profiling = false;
if (profile) {
    const fine = args.includes("--fine");
    const labels = [];
    for (const a of JSON.parse(fs.readFileSync(symFile, "utf8")).assemblies)
        for (const s of a.sections)
            for (const [k, v] of Object.entries(s.labels ?? {}))
                if (!k.includes("@") && (fine || !k.includes(".")))
                    labels.push([v.value + (s.name === "ObjAndy" ? 0x10000 : s.name === "AreaConv" ? 0x20000 : 0), k]);
    labels.sort((a, b) => a[0] - b[0]);
    const labelOf = (key) => {
        let lo = 0, hi = labels.length - 1;
        while (lo < hi) {
            const mid = (lo + hi + 1) >> 1;
            if (labels[mid][0] <= key) lo = mid;
            else hi = mid - 1;
        }
        return labels[lo]?.[1] ?? "?";
    };
    const convBank = has("AREA_CONV_BANK") ? S("AREA_CONV_BANK") : -1;
    let lastKey = -1, lastT = 0;
    m.tm.processor.debugInstruction.add((at) => {
        const t = m.tm.elapsedCycles;
        if (profiling && lastKey >= 0) {
            const r = labelOf(lastKey);
            profile.set(r, (profile.get(r) || 0) + (t - lastT));
        }
        const p = m.paged(at);
        lastKey = at + (p === "andy" ? 0x10000 : p === convBank ? 0x20000 : 0);
        lastT = t;
        return false;
    });
}

// Where the conversion may write.
const allowed = [
    [0x10, 0x90],
    [0x100, 0x200],
    [0xf4, 0xf5],
    [0xfe30, 0xfe31],
];
allowed.push([S("acccon"), S("acccon") + 1]); // (the check's stubs page HAZEL in and out)
for (const name of ["ObjArea", "ObjWork", "ObjMemo"]) allowed.push([sections[name].org, sections[name].guard]);
const badWrites = [];
m.tm.processor.debugWrite.add((addr) => {
    if (!allowed.some(([lo, hi]) => addr >= lo && addr < hi) && badWrites.length < 10) badWrites.push(addr);
});

// Each array of the working copy, and the space it's indexed by.
const arrays = layout.arrays.map(([name]) => name);
const spaceOf = Object.fromEntries(layout.arrays);
const N = (s) => S(`N_${s.toUpperCase()}`);
const G = (s) => S(`G_${s.toUpperCase()}`);
const hex = (n) => "&" + n.toString(16).toUpperCase();

function compare(what, name, at, want) {
    const got = m.read(S(name) + at, want.length);
    for (let i = 0; i < want.length; i++) {
        if (got[i] !== want[i]) {
            fail(`${what}: ${name}[${at + i}] ${got[i]}, want ${want[i]}`);
            return;
        }
    }
}

function junk(from) {
    // the working copy from each array's entry `from(space)` on, filled with
    // what a conversion that missed an entry would leave
    let k = 0x5a;
    for (const name of arrays) {
        const s = spaceOf[name];
        for (let i = from(s); i < N(s); i++) {
            m.poke(S(name) + i, k);
            k = (k * 37 + 11) & 255;
        }
    }
}

// The globals.
badWrites.length = 0;
const init = (await m.call(S("check_init"))).total;
if (badWrites.length) fail(`area_init wrote outside its memory at ${badWrites.map(hex).join(" ")}`);
for (const name of arrays) compare("globals", name, 0, layout.globals.arrays[name]);
if (m.peek(S("ob_n")) !== G("obj")) fail(`area_init: ob_n ${m.peek(S("ob_n"))}, want ${G("obj")}`);

// The areas.
const cycles = [];
for (const area of layout.areas) {
    const what = `area ${area.id} (${area.name})`;
    junk((s) => (logic ? 0 : G(s)));
    m.poke(S("check_area"), area.index);
    badWrites.length = 0;
    profiling = true;
    const { total } = await m.call(S("check_enter"));
    profiling = false;
    cycles.push([total, area]);
    if (badWrites.length) fail(`${what}: wrote outside its memory at ${badWrites.map(hex).join(" ")}`);
    for (const name of arrays) {
        const g = name === "ob_ix" ? area.globals_index : layout.globals.arrays[name];
        compare(`${what}, the globals`, name, 0, g);
        compare(what, name, G(spaceOf[name]), area.arrays[name]);
    }
    const n = G("obj") + area.counts.obj;
    if (m.peek(S("ob_n")) !== n) fail(`${what}: ob_n ${m.peek(S("ob_n"))}, want ${n}`);
    const counts = m.read(S("ar_counts"), layout.spaces.length);
    const want = layout.spaces.map((s) => area.counts[s]);
    if (counts.join() !== want.join()) fail(`${what}: ar_counts ${counts}, want ${want}`);
    if (!logic) {
        const flags = m.read(S("ob_flags"), n);
        const state = m.read(S("ob_state"), n);
        for (let s = 0; s < n; s++)
            if (state[s] !== (flags[s] & S("F_HIDDEN"))) fail(`${what}: ob_state[${s}] ${state[s]}, flags ${flags[s]}`);
    }
    if (verbose) console.log(`${what}: ${total} cycles, counts ${JSON.stringify(area.counts)}`);
}

const sorted = cycles.map(([c]) => c).sort((a, b) => a - b);
const median = sorted.length % 2 ? sorted[(sorted.length - 1) / 2] : (sorted[sorted.length / 2 - 1] + sorted[sorted.length / 2]) / 2;
const [most, mostArea] = cycles.reduce((a, b) => (b[0] > a[0] ? b : a));
console.log(
    `areas${logic ? " (OBJ_LOGIC)" : ""}: the globals and ${layout.areas.length} areas built and compared ` +
        `(${arrays.length} arrays); cycles: area_init ${init}, area_enter median ${median}, ` +
        `most ${most} (area ${mostArea.id})`,
);
if (profile) {
    const all = [...profile.values()].reduce((a, b) => a + b, 0);
    console.log(`areas: area_enter's cycles by label, a mean over the ${layout.areas.length} areas`);
    for (const [r, c] of [...profile.entries()].sort((a, b) => b[1] - a[1]).slice(0, Number(opt("top", 30))))
        console.log(`  ${r.padEnd(28)} ${String(Math.round(c / layout.areas.length)).padStart(8)} ${(100 * c / all).toFixed(1).padStart(5)}%`);
}
if (failures) {
    console.log(`areas: ${failures} failures`);
    process.exit(1);
}
console.log("areas: ok");
