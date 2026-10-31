#!/usr/bin/env node
// The slideshow's check: the disc booted on jsbeeb's full video (the CRTC
// and the vertical sync as the disc programs them), headless, through every
// one of Driller's entrance views, each frame shown compared with the
// model's render of its view, byte for byte.
//
//   node tools/slidecheck.mjs [--disc build/slides.ssd] [--views build/slides/views.json]
//                             [--hold FIELDS] [--json OUT] [--verbose]
//
// It boots the disc and runs to slides_loop, then lets the slideshow step
// through every view on its own (each held slide_hold fields, or --hold's),
// and fails (exit status 1) unless:
//
// - every view is shown, in order;
// - every flip shows the buffer of the one frame handed over since the last,
//   and that frame's view bytes are the model's for the view it drew
//   (tools/mkslides.py's views.json, from tools/model/render.py);
// - every frame handed over wants its view's text lines, and the buffer it
//   drew holds the text wanted (src/text.6502's record of it);
// - every screen write comes between frame_begin and frame_end, to the
//   buffer not shown;
// - SPACE, cursor right and cursor down step to the next view, cursor left
//   and up to the one before, round from the first to the last.
//
// It reports, for each view, the fields each of its frames was shown for
// (the frame rate the slideshow measures, as the BBC shows it: median and
// most), raster_frame's cycles (from its call to slide_drawn) and a frame's
// work (its cycles but for frame_begin's wait for the last flip: the view's
// copy, the figures and the text besides raster_frame, and the interrupt):
// median and most. --json writes them.
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./symbols.mjs";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const jsbeeb = (file) => import(pathToFileURL(path.join(root, "node_modules/jsbeeb/src", file)).href);
const { MachineSession } = await jsbeeb("machine-session.js");
const { BBC } = await jsbeeb("keymap.js");

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    return i < 0 ? dflt : args[i + 1];
};
const disc = opt("disc", "build/slides.ssd");
const viewsFile = opt("views", "build/slides/views.json");
const hold = opt("hold");
const jsonOut = opt("json");
const verbose = args.includes("--verbose");

const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const sym = (name) => {
    if (!(name in syms)) throw new Error(`no symbol ${name}`);
    return syms[name];
};
const views = JSON.parse(fs.readFileSync(viewsFile, "utf8")).slides;
const SLIDES = sym("SLIDES");
if (views.length !== SLIDES) throw new Error(`${viewsFile} has ${views.length} views, the disc ${SLIDES}`);

let failures = 0;
const fail = (what) => {
    if (++failures <= 30) console.log(`slides: FAIL ${what}`);
};
process.on("uncaughtException", (e) => {
    console.log(`slides: FAIL ${e.message}`);
    process.exit(1);
});
const hex = (n, w = 2) => "&" + n.toString(16).toUpperCase().padStart(w, "0");
const quietly = async (f) => {
    const q = console.log;
    console.log = () => {};
    try {
        return await f();
    } finally {
        console.log = q;
    }
};

const SCREEN = sym("SCREEN");
const SCREEN_ROW = sym("SCREEN_ROW");
const VIEW_ADDR = sym("VIEW_ADDR");
const VIEW_BYTES = sym("VIEW_BYTES");
const VIEW_H = sym("VIEW_H");
const viewAt = (y, c) => VIEW_ADDR + (y >> 3) * SCREEN_ROW + c * 8 + (y & 7);
const want = views.map((v) => v.view.map((row) => Buffer.from(row, "hex")));

const session = new MachineSession("Master");
await quietly(() => session.initialise());
const tm = session._machine;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const now = () => tm.elapsedCycles;
const word = (a) => ram[a] | (ram[a + 1] << 8);
// A buffer's byte: main RAM's, or shadow RAM's (jsbeeb keeps it 32K on).
const bufferByte = (buffer, a) => ram[a + (buffer ? 0x8000 : 0)];

session.loadDisc(path.resolve(disc));
await quietly(() => session.autoboot());
const t0 = Date.now();
try {
    await session.runUntilAddress(sym("slides_loop"), 120);
} catch {
    throw new Error("didn't reach slides_loop in 120s of emulated time");
}
const bootSecs = now() / 2e6;
if (hold !== undefined) ram[sym("slide_hold")] = Number(hold);

// The hooks: frames handed over and not yet shown; whether a frame is being
// drawn; each view's frames, as fields shown for, and its raster_frame
// cycles.
const pending = [];
let inFrame = false, calling = false;
let lastFlipField = null;
let tRaster = null;
let tEnd = null, tCall = null, tShown = null;
let collecting = true;
const stats = views.map(() => ({ fields: [], cycles: [], work: [], shown: 0 }));
const order = []; // the views in the order their first frames were shown
let flips = 0, writes = 0, compared = 0;

const FB_BEGIN = sym("frame_begin"), FB_END = sym("frame_end"), FB_SHOWN = sym("frame_begin.shown");
const RASTER = sym("raster_frame"), DRAWN = sym("slide_drawn");
const BANK_RASTER = sym("BANK_RASTER");
const SLIDE_NOW = sym("slide_now");
const JSR = 0x20;
cpu.debugInstruction.add((addr, opcode) => {
    if (opcode === JSR && word(addr + 1) === FB_BEGIN) {
        calling = true;
        tCall = now();
    }
    if (addr === FB_SHOWN) tShown = now();
    else if (addr === FB_BEGIN && calling) {
        // (its wait loops back to its first instruction: a call is a JSR)
        calling = false;
        if (inFrame) fail("frame_begin twice, without frame_end");
        inFrame = true;
    } else if (addr === RASTER && (cpu.romsel & 15) === BANK_RASTER) {
        tRaster = now();
    } else if (addr === DRAWN && tRaster !== null) {
        if (collecting) stats[ram[SLIDE_NOW]].cycles.push(now() - tRaster);
        tRaster = null;
    } else if (addr === FB_END) {
        if (!inFrame) fail("frame_end without frame_begin");
        inFrame = false;
        if (collecting && tEnd !== null) stats[ram[SLIDE_NOW]].work.push(tCall - tEnd + now() - tShown);
        tEnd = now();
        const frame = { n: word(sym("frames_drawn")) + 1, buffer: (cpu.acccon >> 2) & 1, slide: ram[SLIDE_NOW] };
        pending.push(frame);
        checkText(frame);
        if (pending.length > 1) fail(`frame ${pending.at(-1).n} handed over before frame ${pending[0].n} was shown`);
    }
    return false;
});

// The text a frame hands over: the view's lines (tools/mkslides.py's) wanted,
// and the buffer it drew brought up to what's wanted.
const TEXT_WANT = sym("text_want"), TEXT_SHOWN = sym("text_shown"), TEXT_CELLS = sym("TEXT_CELLS");
const latin = (a, n) => Buffer.from(ram.subarray(a, a + n)).toString("latin1");
let textChecked = 0;
function checkText(frame) {
    const lines = views[frame.slide].text.join("");
    const wanted = latin(TEXT_WANT, TEXT_CELLS);
    if (!wanted.startsWith(lines)) fail(`frame ${frame.n} of ${views[frame.slide].name} wants the text ${JSON.stringify(wanted.slice(0, lines.length))}`);
    if (latin(TEXT_SHOWN + frame.buffer * TEXT_CELLS, TEXT_CELLS) !== wanted)
        fail(`frame ${frame.n} handed over with its buffer's text not what's wanted`);
    textChecked++;
}

function flipped(to) {
    flips++;
    const field = word(sym("fields"));
    const k = lastFlipField === null ? null : (field - lastFlipField) & 0xffff;
    lastFlipField = field;
    const frame = pending.shift();
    if (!frame) return fail(`flip ${flips} with no frame handed over`);
    if (frame.buffer !== to) return fail(`flip ${flips} to buffer ${to}, but frame ${frame.n} was drawn in ${frame.buffer}`);
    const s = frame.slide;
    if (order.at(-1) !== s) order.push(s);
    if (collecting) {
        stats[s].shown++;
        if (k !== null) stats[s].fields.push(k);
    }
    compared++;
    let bad = 0;
    for (let y = 0; y < VIEW_H; y++)
        for (let c = 0; c < VIEW_BYTES; c++) {
            const got = bufferByte(to, viewAt(y, c));
            if (got !== want[s][y][c] && bad++ < 2)
                fail(`frame ${frame.n} of ${views[s].name} shown with line ${y}, byte ${c} ${hex(got)}, ` +
                    `not the model's ${hex(want[s][y][c])}`);
        }
}

cpu.debugWrite.add((addr, value) => {
    if (addr === sym("acccon")) {
        if ((value ^ cpu.acccon) & 1) flipped(value & 1);
    } else if (addr >= SCREEN && addr < 0x8000) {
        writes++;
        const x = (cpu.acccon >> 2) & 1, d = cpu.acccon & 1;
        if (!inFrame) fail(`a screen write (${hex(addr, 4)}) outside frame_begin..frame_end`);
        if (x === d) fail(`a screen write (${hex(addr, 4)}) to the buffer shown`);
    }
    return false;
});

// The tour: until the slideshow has come round to the first view again.
const tourLimit = now() + (SLIDES + 2) * (ram[sym("slide_hold")] + 50) * sym("FIELD_CYCLES");
let seenLast = false;
for (;;) {
    await session.runFor(sym("FIELD_CYCLES") * 10);
    const s = ram[SLIDE_NOW];
    if (s === SLIDES - 1) seenLast = true;
    if (seenLast && s === 0) break;
    if (now() > tourLimit) {
        fail(`the tour didn't come round to the first view (at ${views[s].name})`);
        break;
    }
}
collecting = false;
const expected = Array.from({ length: SLIDES }, (_, i) => i);
if (order.slice(0, SLIDES).join() !== expected.join())
    fail(`the views were shown in the order ${order.slice(0, SLIDES).join(" ")}`);

// The keys: held for a few fields each, with the hold off.
const held = ram[sym("slide_hold")];
ram[sym("slide_hold")] = 0;
const FIELD = sym("FIELD_CYCLES");
const steps = [["SPACE", 1], ["RIGHT", 1], ["DOWN", 1], ["LEFT", -1], ["UP", -1], ["UP", -1], ["LEFT", -1], ["SPACE", 1]];
let keysOk = 0;
for (const [key, by] of steps) {
    const before = ram[SLIDE_NOW];
    session.keyDownRaw(BBC[key]);
    await session.runFor(3 * FIELD);
    session.keyUpRaw(BBC[key]);
    await session.runFor(12 * FIELD);
    const after = ram[SLIDE_NOW];
    const expect = (before + by + SLIDES) % SLIDES;
    if (after !== expect) fail(`${key} at ${views[before].name}: went to ${views[after].name}, not ${views[expect].name}`);
    else keysOk++;
}
await session.runFor(20 * FIELD);
const emulated = now() / 2e6 - bootSecs;

// The figures.
const median = (xs) => {
    if (!xs.length) return NaN;
    const s = [...xs].sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const rows = views.map((v, i) => {
    const st = stats[i];
    if (!st.shown) fail(`${v.name} was never shown`);
    return {
        name: v.name, area: v.area, entrance: v.entrance, faces: v.faces, vertices: v.vertices,
        frames: st.shown,
        fields_median: median(st.fields), fields_max: Math.max(...st.fields),
        cycles_median: median(st.cycles), cycles_max: Math.max(...st.cycles), cycles_first: st.cycles[0],
        work_median: median(st.work), work_max: Math.max(...st.work),
    };
});
for (const r of rows)
    if (verbose)
        console.log(`  ${r.name} ${r.area.padEnd(12)} faces ${String(r.faces).padStart(2)}: ` +
            `${String(r.frames).padStart(3)} frames, fields a frame median ${r.fields_median} most ${r.fields_max}; ` +
            `raster_frame median ${r.cycles_median} most ${r.cycles_max} first ${r.cycles_first} cycles; ` +
            `a frame's work median ${r.work_median} most ${r.work_max}`);
const all = stats.flatMap((s) => s.fields);
const allCycles = stats.flatMap((s) => s.cycles);
const allWork = stats.flatMap((s) => s.work);
const viewMedians = rows.map((r) => r.fields_median);
console.log(`slides: ${SLIDES} views, ${compared} frames shown, each the model's view byte for byte, ` +
    `${textChecked} with the view's text; ` +
    `${writes} screen writes, all inside frames to the buffer not shown; ${keysOk} of ${steps.length} key steps`);
console.log(`slides: fields a frame over every frame: median ${median(all)}, most ${Math.max(...all)}; ` +
    `views' medians from ${Math.min(...viewMedians)} to ${Math.max(...viewMedians)}, their median ${median(viewMedians)}`);
console.log(`slides: raster_frame: median ${median(allCycles)} cycles, most ${Math.max(...allCycles)}; ` +
    `a frame's work: median ${median(allWork)}, most ${Math.max(...allWork)}; ` +
    `${emulated.toFixed(1)}s emulated in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ hold: held, views: rows }, null, 1) + "\n");
console.log(failures ? `slides: ${failures} failure(s)` : "slides: ok");
process.exit(failures ? 1 : 0);
