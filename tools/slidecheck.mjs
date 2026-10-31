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
// - at every flip, both buffers hold the same outside the view (the flip
//   comes mid-field: decision 21); at every eighth, the text's characters
//   there are text_shown's, in the widened font and their lines' inks;
// - every frame handed over wants its view's text lines, and they're
//   drawn, and the rest of the text is never behind for TEXT_PATIENCE
//   frames running;
// - every write to the view comes between frame_begin and frame_end, into
//   the buffer not shown; outside the view, a write to the buffer shown
//   comes with the beam above the written character row;
// - SPACE, cursor right and cursor down step to the next view, cursor left
//   and up to the one before, round from the first to the last.
//
// It reports, for each view, the fields each of its frames was shown for
// (by the clock, flip to flip: the frame rate as the BBC shows it, median
// and most), raster_frame's cycles (from its call to slide_drawn) and a frame's
// work (from frame_begin's return to frame_end: the figures, the text and
// the interrupts besides raster_frame): median and most. --json writes
// them.
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
const video = session._video;
const R9 = video.regs[9];
const FIELD_CYCLES = sym("FIELD_CYCLES");
const pending = [];
let inFrame = false, calling = false;
let lastFlipT = null;
let tRaster = null;
let tShown = null;
let collecting = true;
const stats = views.map(() => ({ fields: [], cycles: [], work: [], shown: 0 }));
const order = []; // the views in the order their first frames were shown
let flips = 0, viewWrites = 0, textWrites = 0, compared = 0;

const FB_BEGIN = sym("frame_begin"), FB_END = sym("frame_end"), FB_SHOWN = sym("frame_begin.shown");
const RASTER = sym("raster_frame"), DRAWN = sym("slide_drawn");
const BANK_RASTER = sym("BANK_RASTER");
const SLIDE_NOW = sym("slide_now");
const JSR = 0x20;
cpu.debugInstruction.add((addr, opcode) => {
    if (opcode === JSR && word(addr + 1) === FB_BEGIN) calling = true;
    if (addr === FB_SHOWN) tShown = now();
    else if (addr === TEXT_WAITING) textWaits++;
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
        if (collecting && tShown !== null) stats[ram[SLIDE_NOW]].work.push(now() - tShown);
        const frame = { n: word(sym("frames_drawn")) + 1, buffer: (cpu.acccon >> 2) & 1, slide: ram[SLIDE_NOW] };
        pending.push(frame);
        checkText(frame);
        if (pending.length > 1) fail(`frame ${pending.at(-1).n} handed over before frame ${pending[0].n} was shown`);
    }
    return false;
});

// The text (src/text.6502): what's wanted and what both buffers show, and
// where each line's characters are on the screen.
const TEXT_WANT = sym("text_want"), TEXT_SHOWN = sym("text_shown"), TEXT_CELLS = sym("TEXT_CELLS");
const TEXT_COLS = sym("TEXT_COLS"), GLYPH = sym("GLYPH"), TEXT_FIRST = sym("TEXT_FIRST"), TEXT_LAST = sym("TEXT_LAST");
const TEXT_FONT = sym("text_font"), TEXT_INK = sym("text_ink"), TEXT_ROW = sym("text_row");
const RECORD_TEXT = sym("RECORD_TEXT");
const latin = (a, n) => Buffer.from(ram.subarray(a, a + n)).toString("latin1");
const cellAt = (cell) => (ram[TEXT_ROW + Math.floor(cell / TEXT_COLS)] << 8) + (cell % TEXT_COLS) * GLYPH;
// A frame handed over wants its view's lines (tools/mkslides.py's), and
// they're drawn.
let textChecked = 0, textBehind = 0, behindRun = 0, textWaits = 0;
const TEXT_PATIENCE = sym("TEXT_PATIENCE"), TEXT_WAITING = sym("text_catch_up.waiting");
function checkText(frame) {
    const lines = views[frame.slide].text.join("");
    const wanted = latin(TEXT_WANT, TEXT_CELLS);
    if (!wanted.startsWith(lines)) fail(`frame ${frame.n} of ${views[frame.slide].name} wants the text ${JSON.stringify(wanted.slice(0, lines.length))}`);
    if (latin(TEXT_SHOWN, RECORD_TEXT) !== lines)
        fail(`frame ${frame.n} of ${views[frame.slide].name} handed over showing ${JSON.stringify(latin(TEXT_SHOWN, RECORD_TEXT))}`);
    textChecked++;
    // and the rest of the text (the figures) is never behind for long
    if (latin(TEXT_SHOWN, TEXT_CELLS) === wanted) behindRun = 0;
    else {
        textBehind++;
        if (++behindRun >= TEXT_PATIENCE) fail(`frame ${frame.n} handed over with the text behind ${behindRun} frames running`);
    }
}
// The screen's characters are text_shown's, in the font text_init widened
// and each line's ink.
let glyphsChecked = 0;
function checkGlyphs(buffer, what) {
    glyphsChecked++;
    for (let cell = 0; cell < TEXT_CELLS; cell++) {
        let ch = ram[TEXT_SHOWN + cell];
        if (ch < TEXT_FIRST || ch > TEXT_LAST) ch = 32;
        const ink = ram[TEXT_INK + Math.floor(cell / TEXT_COLS)];
        const font = TEXT_FONT + (ch - TEXT_FIRST) * GLYPH, at = cellAt(cell);
        for (let i = 0; i < GLYPH; i++)
            if (bufferByte(buffer, at + i) !== (ram[font + i] & ink))
                return fail(`${what}: cell ${cell}'s ${hex(at + i, 4)} isn't ${JSON.stringify(String.fromCharCode(ch))}'s`);
    }
}

// The view's bytes, by offset from SCREEN.
const SCREEN_BYTES = 0x8000 - SCREEN;
const viewMask = new Uint8Array(SCREEN_BYTES);
for (let y = 0; y < VIEW_H; y++) for (let c = 0; c < VIEW_BYTES; c++) viewMask[viewAt(y, c) - SCREEN] = 1;
// The beam's line, from the field's first shown.
const beamLine = () => video.vertCounter * (R9 + 1) + video.scanlineCounter + video.vertAdjustCounter;

function flipped(to) {
    flips++;
    const t = now();
    const k = lastFlipT === null ? null : (t - lastFlipT) / FIELD_CYCLES;
    lastFlipT = t;
    // flipping mid-field shows what's outside the view from both buffers
    let bad = 0;
    for (let i = 0; i < SCREEN_BYTES; i++)
        if (!viewMask[i] && ram[SCREEN + i] !== ram[SCREEN + i + 0x8000] && bad++ < 2)
            fail(`flip ${flips}: ${hex(SCREEN + i, 4)}, outside the view, differs between the buffers`);
    if (flips % 8 === 1) checkGlyphs(to, `flip ${flips}`);
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
    bad = 0;
    for (let y = 0; y < VIEW_H; y++)
        for (let c = 0; c < VIEW_BYTES; c++) {
            const got = bufferByte(to, viewAt(y, c));
            if (got !== want[s][y][c] && bad++ < 2)
                fail(`frame ${frame.n} of ${views[s].name} shown with line ${y}, byte ${c} ${hex(got)}, ` +
                    `not the model's ${hex(want[s][y][c])}`);
        }
}

// The view is written only inside a frame, into the buffer not shown;
// outside it, into the buffer shown only while the beam is above the
// written character row, so the change is whole before it's shown (and
// both buffers must be alike at every flip: flipped).
cpu.debugWrite.add((addr, value) => {
    if (addr === sym("acccon")) {
        if ((value ^ cpu.acccon) & 1) flipped(value & 1);
    } else if (addr >= SCREEN && addr < 0x8000) {
        const x = (cpu.acccon >> 2) & 1, d = cpu.acccon & 1;
        if (viewMask[addr - SCREEN]) {
            viewWrites++;
            if (!inFrame) fail(`a write to the view (${hex(addr, 4)}) outside frame_begin..frame_end`);
            if (x === d) fail(`a write to the view (${hex(addr, 4)}) of the buffer shown`);
        } else {
            textWrites++;
            const row = Math.floor((addr - SCREEN) / SCREEN_ROW) * (R9 + 1);
            if (x === d && beamLine() >= row)
                fail(`a write (${hex(addr, 4)}) to the buffer shown with the beam on line ${beamLine()}, at or past its row's top, ${row}`);
        }
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
const two = (v) => Math.round(v * 100) / 100;
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
        fields_median: two(median(st.fields)), fields_max: two(Math.max(...st.fields)),
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
    `${textChecked} with the view's text (${textBehind} with the figures behind; ` +
    `${textWaits} waits for the beam to catch them up); ` +
    `${viewWrites} writes to the view and ${textWrites} outside it, each where it may be; ` +
    `${glyphsChecked} flips' text checked against the font; ${keysOk} of ${steps.length} key steps`);
const rate = 2e6 / FIELD_CYCLES;
console.log(`slides: fields a frame over every frame: median ${two(median(all))} (${two(rate / median(all))} frames a second), ` +
    `most ${two(Math.max(...all))}; views' medians from ${Math.min(...viewMedians)} to ${Math.max(...viewMedians)}, ` +
    `their median ${two(median(viewMedians))}`);
console.log(`slides: raster_frame: median ${median(allCycles)} cycles, most ${Math.max(...allCycles)}; ` +
    `a frame's work: median ${median(allWork)}, most ${Math.max(...allWork)}; ` +
    `${emulated.toFixed(1)}s emulated in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ hold: held, views: rows }, null, 1) + "\n");
console.log(failures ? `slides: ${failures} failure(s)` : "slides: ok");
process.exit(failures ? 1 : 0);
