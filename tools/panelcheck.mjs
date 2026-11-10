#!/usr/bin/env node
// The panel's values, stage by stage: src/panel.6502's panel_values on the
// live disc against the model's cells (tools/model/panel.py, through
// tools/mkpanel.py --check), over the values play rarely or never reaches:
// every energy and shield a bar can show and past it, scores and positions
// at each digit's edges and past them, every area scale, every yaw and
// pitch byte, every area id (the gas's message, the rig, the compass that
// doesn't turn), the vehicle at each extension and in the jet, the lights,
// the area names and the game's end; then a seeded fuzz of all at once.
//
//   node tools/panelcheck.mjs [--disc build/live.ssd] [--fuzz 400] [--seed 1]
//
// It boots the disc to live_loop, then calls panel_values from a stub (the
// bank paged, interrupts off) with each set of values poked into the
// logic's variables (its mirror of the original's: tools/model/panel.py's
// ZX addresses), panel_area and panel_over, and holds the cells it wants to
// the model's for the same bytes, read back, in order (the heading stays as
// it was where the compass doesn't turn). The frames a second aren't
// panel_values': their cells aren't compared. Fails (exit status 1) on any
// difference; reports panel_values' cycles.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./symbols.mjs";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    return i < 0 ? dflt : args[i + 1];
};
const disc = opt("disc", "build/live.ssd");
const fuzz = Number(opt("fuzz", "400"));
let seed = Number(opt("seed", "1"));
const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const sym = (n) => {
    if (!(n in syms)) throw new Error(`no symbol ${n}`);
    return syms[n];
};
const quietly = async (f) => {
    const q = console.log;
    console.log = () => {};
    try {
        return await f();
    } finally {
        console.log = q;
    }
};

const { MachineSession } = await import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src/machine-session.js")).href);
const session = new MachineSession("Master");
await quietly(() => session.initialise());
const tm = session._machine;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
session.loadDisc(path.resolve(disc));
await quietly(() => session.autoboot());
await session.runUntilAddress(sym("live_loop"), 120);

// The stub: interrupts off, the panel's bank in, panel_values, then a jump
// to itself.
const STUB = 0x0140, BANK = sym("BANK_DATA"), ROMSEL_COPY = 0xf4, END = STUB + 11;
const VALUES = sym("panel_values");
ram.set([0x78, 0xa9, BANK, 0x85, ROMSEL_COPY, 0x8d, 0x30, 0xfe,     // SEI : LDA #bank : STA ROMSEL_COPY : STA romsel
    0x20, VALUES & 0xff, VALUES >> 8, 0x4c, END & 0xff, END >> 8], STUB); // JSR panel_values : JMP END

// The original's variables, in the logic's mirror.
const ZXV = sym("zxv"), ZXV_ORG = sym("ZXV_ORG");
const zx = (a) => ZXV + a - ZXV_ORG;
const VARS = { Score: [0x8872, 3], Energy: [0x8875, 1], Shield: [0x8878, 1], Step: [0x876a, 1], Turn: [0x876f, 1],
    PlayerX: [0x8762, 2], PlayerY: [0x8764, 2], PlayerZ: [0x8766, 2], Pitch: [0x876c, 1], Yaw: [0x876d, 1],
    InJet: [0x877a, 1], ExtLevel: [0x8772, 1], AreaScale: [0x8779, 1], AreaId: [0x8862, 1],
    CrossOn: [0x88a2, 1], ShootMode: [0x88ac, 1] };
const RIG_PLACED = 0x877b, CLOCK = 0x88a4;
// a clock's text from a number of seconds (the original's counts from
// 04:00:00 down)
const clockOf = (t) => [Math.floor(t / 3600), Math.floor(t / 60) % 60, t % 60].map((n) => String(n).padStart(2, "0")).join(":");
const PANEL_WANT = sym("panel_want"), PANEL_CELLS = sym("PANEL_CELLS");
const PANEL_AREA = sym("panel_area"), PANEL_OVER = sym("panel_over");
const PF_FPS = sym("PF_FPS"), PN_FPS = sym("PN_FPS");

const vectors = [];
const pick = (list, i) => list[i % list.length];
const SCORES = [0, 1, 9, 10, 99, 100, 99999, 100000, 999999, 1000000, 1234567, 9999999, 10000000, 0x7fffff, 0xffffff];
const WORDS = [0, 1, 63, 64, 999, 1000, 9999, 10000, 12345, 32767, 32768, 65535];
const SCALES = [1, 2, 4, 0, 3, 255];
for (let i = 0; i < 256; i++) {
    vectors.push({
        Score: pick(SCORES, i), Energy: i, Shield: 255 - i, Step: (i * 7) & 0xff, Turn: i % 64,
        PlayerX: pick(WORDS, i), PlayerY: pick(WORDS, i + 5), PlayerZ: pick(WORDS, i * 3), AreaScale: pick(SCALES, i >> 1),
        Yaw: i, Pitch: 255 - i, InJet: i % 9 === 8 ? 1 : 0, ExtLevel: i % 9,
        AreaId: i, rig: i & 1 ? 3 : (i >> 1) & 3, CrossOn: i & 2 ? 0xff : 0, ShootMode: i & 4 ? 0xff : 0,
        area: i % 32 === 31 ? 255 : i % 31, over: i % 17 === 0 ? 1 : 0,
        clock: clockOf(pick([14400, 14399, 14340, 3600, 3599, 600, 599, 60, 59, 10, 9, 1, 0], i)),
    });
}
const rnd = (n) => {
    seed = (seed * 1103515245 + 12345) & 0x7fffffff;
    return seed % n;
};
for (let i = 0; i < fuzz; i++) {
    vectors.push({
        Score: rnd(0x1000000), Energy: rnd(256), Shield: rnd(256), Step: rnd(256), Turn: rnd(256),
        PlayerX: rnd(65536), PlayerY: rnd(65536), PlayerZ: rnd(65536), AreaScale: rnd(6),
        Yaw: rnd(256), Pitch: rnd(256), InJet: rnd(2), ExtLevel: rnd(8), AreaId: rnd(256), rig: rnd(5),
        CrossOn: rnd(2) * 0xff, ShootMode: rnd(2) * 0xff, area: rnd(40), over: rnd(2),
        clock: clockOf(rnd(14401)),
    });
}

const valued = [], wants = [], cycles = [];
for (const v of vectors) {
    const at = new Set();
    for (const [name, [a, n]] of Object.entries(VARS)) {
        for (let k = 0; k < n; k++) {
            ram[zx(a + k)] = (v[name] >> (8 * k)) & 0xff;
            at.add(a + k);
        }
    }
    // the rig's byte, unless it's one of the others
    const rig = RIG_PLACED + ((v.AreaId - 1) & 0xff);
    if (!at.has(rig)) ram[zx(rig)] = v.rig;
    at.add(rig);
    // the clock's text, hh:mm:ss
    for (let k = 0; k < 8; k++) {
        ram[zx(CLOCK + k)] = v.clock.charCodeAt(k);
        at.add(CLOCK + k);
    }
    ram[PANEL_AREA] = v.area;
    ram[PANEL_OVER] = v.over;
    cpu.pc = STUB;
    cpu.s = 0xff;
    const t0 = tm.elapsedCycles;
    await session.runUntilAddress(END, 5);
    if (cpu.pc !== END) throw new Error(`panel_values didn't return: pc &${cpu.pc.toString(16)}`);
    cycles.push(tm.elapsedCycles - t0);
    wants.push([...ram.subarray(PANEL_WANT, PANEL_WANT + PANEL_CELLS)]);
    valued.push({ mem: [...at].map((a) => [a, ram[zx(a)]]), area: v.area, over: v.over });
}

const py = spawnSync(path.join(root, ".venv/bin/python"), ["-I", path.join(root, "tools/mkpanel.py"), "--check"], {
    input: JSON.stringify({ shown: [], valued }),
    maxBuffer: 1 << 28,
});
if (py.status !== 0) throw new Error(`the model failed: ${py.stderr}`);
const model = JSON.parse(py.stdout);
const fieldOf = (i) => {
    for (let f = 0, at = 0; f < model.fields.length; at += model.fields[f][1], f++)
        if (i < at + model.fields[f][1]) return `${model.fields[f][0]} ${i - at}`;
    return `cell ${i}`;
};
let failures = 0, ok = 0;
wants.forEach((want, n) => {
    const exp = model.valued[n];
    const i = want.findIndex((g, i) => (i < PF_FPS || i >= PF_FPS + PN_FPS) && g !== exp[i]);
    if (i < 0) return ok++;
    if (++failures <= 20)
        console.log(`panel: FAIL values ${n}: ${fieldOf(i)} is ${want[i]}, the model's ${exp[i]} (from ${JSON.stringify(vectors[n])})`);
});
const s = [...cycles].sort((a, b) => a - b);
console.log(`panel: ${vectors.length} sets of values, ${ok} with the model's cells; panel_values (and the stub) ` +
    `${s[s.length >> 1]} / ${s[Math.ceil(0.9 * s.length) - 1]} / ${s.at(-1)} cycles (median / p90 / most)`);
console.log(failures ? `panel: ${failures} failure(s)` : "panel: ok");
process.exit(failures ? 1 : 0);
