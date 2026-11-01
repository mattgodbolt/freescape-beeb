#!/usr/bin/env node
// The loader's check (src/loader.6502): a disc booted on jsbeeb from power
// on, as SHIFT-BREAK boots it, run to the loader's LD_EXEC, where every
// part must be in its place, byte for byte: each place's image, its parts
// one over another in their order and the gaps zero, against the parts'
// files (the disc's first pass's, in LD_BUILD's parts/). And every section
// the disc's build saved must be one of its parts, from its section's
// start to its end.
//
//   node tools/loadcheck.mjs [--disc build/live.ssd] [--until live_loop] [--json OUT]
//
// The loader's symbols are beside the disc (build/X-loader.json for
// build/X.ssd), the disc's build's beside them (build/X.json). It fails
// (exit status 1) on any byte or part out of place, and reports the disc's
// files and the boot's times from power on: to the loader's start, to
// LD_EXEC, to --until (the disc's loop) and to the first frame shown (its
// frames counter, src/zp.6502's, non-zero after --until).
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./symbols.mjs";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const jsbeeb = (file) => import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src", file)).href);
const { MachineSession } = await jsbeeb("machine-session.js");

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    return i < 0 ? dflt : args[i + 1];
};
const disc = opt("disc", "build/live.ssd");
const until = opt("until", "live_loop");
const jsonOut = opt("json");
const NAME = path.basename(disc, ".ssd");

const loader = loadSymbols(disc.replace(/\.ssd$/, "-loader.json"));
const built = JSON.parse(fs.readFileSync(disc.replace(/\.ssd$/, ".json"), "utf8"));
const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const need = (table, name) => {
    if (!(name in table)) throw new Error(`no symbol ${name}`);
    return table[name];
};
const PARTS = need(loader, "LD_PARTS"), LATE = need(loader, "LD_LATE");
const partsDir = path.resolve(root, "src", need(loader, "LD_BUILD"), "parts");
const ROMSEL_ANDY = need(loader, "ROMSEL_ANDY");

let failures = 0;
const fail = (what) => {
    if (++failures <= 20) console.log(`${NAME}: FAIL ${what}`);
};
const hex = (n, w = 4) => "&" + n.toString(16).toUpperCase().padStart(w, "0");

// Every section the build saved is a part, from its start to its end.
const parts = [...PARTS, ...LATE];
const byName = new Map(parts.map((p) => [p[0], p]));
for (const assembly of built.assemblies) {
    for (const s of assembly.sections) {
        const f = s.attributes?.filename;
        if (!f) continue;
        const p = byName.get(f);
        const org = s.attributes.org & 0xffff;
        if (!p) fail(`the section ${s.name} (${f}) isn't one of the loader's parts`);
        else if (p[2] !== org || p[3] !== org + s.size)
            fail(`${f} is ${hex(p[2])}-${hex(p[3])} to the loader, its section ${hex(org)}-${hex(org + s.size)}`);
        byName.delete(f);
    }
}
for (const f of byName.keys()) fail(`the loader's part ${f} is no section the build saved`);

// The disc's files, from its catalogue.
const ssd = fs.readFileSync(disc);
const files = [];
for (let i = 8; i <= ssd[0x105]; i += 8) {
    const name = String.fromCharCode(...ssd.subarray(i, i + 7)).trimEnd();
    const dir = String.fromCharCode(ssd[i + 7] & 0x7f);
    const length = ssd[0x104 + i] | (ssd[0x105 + i] << 8) | (((ssd[0x106 + i] >> 4) & 3) << 16);
    files.push({ name: `${dir}.${name}`, length });
}

// Boot it.
const quietly = async (f) => {
    const q = console.log;
    console.log = () => {};
    try {
        return await f();
    } finally {
        console.log = q;
    }
};
const session = new MachineSession("Master");
await quietly(() => session.initialise());
const tm = session._machine;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const t0 = tm.elapsedCycles;
const secs = (c) => (c - t0) / 2e6;
session.loadDisc(path.resolve(disc));
// (to the loader's JMP to LD_EXEC: LD_EXEC may be where the DFS's code is
// while it reads)
const START = need(loader, "ld_start"), GO = need(loader, "ld_start.go");
await quietly(() => session.autoboot());
try {
    await session.runUntilAddress(START, 60);
} catch {
    throw new Error("the loader didn't start in 60s of emulated time");
}
const tStart = tm.elapsedCycles;
try {
    await session.runUntilAddress(GO, 120);
} catch {
    throw new Error("the loader didn't finish in 120s of emulated time");
}
const tExec = tm.elapsedCycles;

// Where the CPU sees an address in a place, as ramRomOs holds it: a bank
// (and ANDY over its first 4K, with ROMSEL_ANDY), or main RAM (-1: below
// &8000, with ACCCON's X clear; HAZEL from &C000).
const bankAt = (bank, a) => cpu.romOffset + bank * 16384 + (a - 0x8000);
function at(where, a) {
    if (where < 0) {
        if (a < 0x8000) return a;
        if (a >= 0xc000 && a < 0xe000) return a - 0x3000;
        throw new Error(`${hex(a)} isn't main RAM's or HAZEL's`);
    }
    if (where & ROMSEL_ANDY && a < 0x9000) return a;
    return bankAt(where & 15, a);
}
// Each place's image, as the loader writes it, against memory: a place is
// a part's where, HAZEL apart from main RAM (src/loader.6502's ld_place).
const placeOf = (p) => (p[1] < 0 && p[2] >= 0xc000 ? -2 : p[1]);
const places = [];
for (const list of [PARTS, LATE]) {
    for (const place of [...new Set(list.map(placeOf))]) {
        const going = list.filter((p) => placeOf(p) === place);
        const where = going[0][1];
        const lo = Math.min(...going.map((p) => p[2])), hi = Math.max(...going.map((p) => p[3]));
        const image = new Uint8Array(hi - lo);
        for (const p of going) {
            const bytes = fs.readFileSync(path.join(partsDir, p[0]));
            if (bytes.length !== p[3] - p[2]) fail(`${p[0]}'s file is ${bytes.length} bytes, its part ${p[3] - p[2]}`);
            image.set(bytes.subarray(0, p[3] - p[2]), p[2] - lo);
        }
        let wrong = 0, first = null;
        for (let a = lo; a < hi; a++) {
            if (ram[at(where, a)] !== image[a - lo]) {
                if (first === null) first = a;
                wrong++;
            }
        }
        const label = where >= 0 ? `bank ${where & 15}${where & ROMSEL_ANDY ? " and ANDY" : ""}` : lo >= 0xc000 ? "HAZEL" : "main RAM";
        if (wrong)
            fail(`${label} ${hex(lo)}-${hex(hi)} (${going.map((p) => p[0]).join(" ")}): ${wrong} bytes wrong, the first at ${hex(first)}`);
        places.push({ place: label, from: lo, to: hi, parts: going.map((p) => p[0]) });
    }
}

// On to the disc's loop and its first frame shown.
let tUntil = null, tFrame = null;
if (until in syms) {
    try {
        await session.runUntilAddress(syms[until], 60);
        tUntil = tm.elapsedCycles;
    } catch {
        fail(`didn't reach ${until} within 60s of LD_EXEC`);
    }
}
if (tUntil !== null) {
    const FRAMES = syms.frames;
    for (let i = 0; FRAMES !== undefined && i < 500 && tFrame === null; i++) {
        await session.runFrames(1);
        if (ram[FRAMES] | ram[FRAMES + 1]) tFrame = tm.elapsedCycles;
    }
    if (tFrame === null) fail(`no frame shown within 500 fields of ${until}`);
} else if (!(until in syms)) fail(`no symbol ${until}`);

const report = {
    files,
    places,
    boot: {
        loader: secs(tStart),
        exec: secs(tExec),
        until: tUntil === null ? null : secs(tUntil),
        firstFrame: tFrame === null ? null : secs(tFrame),
    },
};
console.log(`${NAME}: files ${files.map((f) => `${f.name} ${f.length}`).join(", ")}`);
const t = (s) => (s === null ? "-" : `${s.toFixed(2)}s`);
console.log(
    `${NAME}: from power on, the loader at ${t(report.boot.loader)}, LD_EXEC at ${t(report.boot.exec)}, ` +
        `${until} at ${t(report.boot.until)}, the first frame shown at ${t(report.boot.firstFrame)}`,
);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify(report, null, 1) + "\n");
if (failures) {
    console.log(`${NAME}: ${failures} failures`);
    process.exit(1);
}
console.log(`${NAME}: every part in its place (${places.length} places, ${parts.length} parts)`);
