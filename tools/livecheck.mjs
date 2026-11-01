#!/usr/bin/env node
// The live discs' check: build/live.ssd (Driller's logic moves the camera)
// or, with --free, build/live-free.ssd (the free camera), booted on jsbeeb's
// full video (the CRTC and the vertical sync as the disc programs them),
// headless, driven by its keys; every frame shown compared with the model's
// render of that frame's camera (tools/model/render.py, through
// tools/mklive.py --render), byte for byte.
//
//   node tools/livecheck.mjs [--disc build/live.ssd] [--live build/live/live.json]
//                            --trace build/live/trace.json [--json OUT] [--verbose]
//   node tools/livecheck.mjs --free [--disc build/live-free.ssd] [--live ...]
//                            [--walks 0,18,26,40,57] [--json OUT] [--verbose]
//
// It boots the disc and runs to live_loop. With the logic, it then runs each
// of the trace's runs (tools/mklive.py --trace: the scenarios of tests/logic/
// and a tour of every entrance, as tools/logic/ takes them, decision 18's
// fix on) from the game's start (LogicWork and the database as the disc
// booted with them, written back): a pass's keys held on the BBC's keyboard
// until the disc's next pass takes them, a minute's end by its clock (the
// minute otherwise kept away), a poke or an FCL script's result written
// into the logic's state and the disc asked to take it (lv_request). It
// fails (exit status 1) unless:
//
// - the disc's state at boot is the game's start, and after every pass
//   every variable of the original's (tools/logic/state.py) and the whole
//   database are the transcription's; each pass answers as the
//   transcription's, and its moves' walks (hook_walked) and area loads
//   (hook_loaded) are the transcription's;
// - every frame's camera is the logic's, or, while a pass's frames show
//   (lv_setup, lv_camera), its point PASS_FIELDS fields take it to, along
//   the segment the transcription's move walked (y held on the probe's
//   step), or straight, as decision 4's rule says, in the old area while an
//   area's change waits; its objects' flags (ix_flags) the records' as the
//   logic has them; and its view the model's render of that camera, those
//   objects and the crosshair, byte for byte.
//
// With --free, as before the logic came:
//
// - the tour: SPACE, entrance after entrance, round all of them to the first
//   again, each held for TOUR_FRAMES frames;
// - at each of --walks' entrances (gone to by poking lv_want), the keys held
//   a few frames each: the cursors and Q W O K, P L N M, and turning and
//   walking together; each frame's camera must be the last frame's moved as
//   the keys held ask, and must move at least once a hold;
// - the demo: no key until it starts, then a turn of a step a frame, and on
//   to the next entrance after a whole turn (not waited for);
//
// failing unless every frame shown is the model's view of the camera and
// area its objects_frame was given (lv_cam, lv_area), each SPACE goes to the
// next entrance, each hold moves the camera as its keys ask (and only so),
// the demo turns a step a frame, and a key stops it.
//
// Both fail unless:
//
// - every flip shows the buffer of the one frame handed over since the last,
//   after it was shown whole; at every flip both buffers hold the same
//   outside the view (decision 21), and at every eighth the text there is
//   text_shown's in the widened font and its lines' inks;
// - every frame handed over wants its area's lines (its name, and the
//   entrance, or the game's end) and they're drawn;
// - every write to the view comes between frame_begin and frame_end, into
//   the buffer not shown; outside the view, a write to the buffer shown
//   comes with the beam above the written character row;
// - the BBC's own timing of each half (clock_to's span_us, from User VIA T2),
//   which its figures show, is within CLOCK_SLACK cycles of the harness's
//   count of the same call.
//
// It reports fields a frame (median, p90, max) for the whole frame (flip to
// flip, as the BBC shows them; and the loop, from frame_end to frame_end)
// and for each half: stages 1-7 (objects_frame, from its call to
// live_front_done) and stages 8-10 (raster_frame, to live_fill_done), over
// every frame and by what the frame did: an area's first frame (the
// transform's cache refilled), standing (the camera as the last frame's),
// walking (moved), turning (the angles changed, so the cache refilled); and
// the free camera's demo.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
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
const FREE = args.includes("--free");
const disc = opt("disc", FREE ? "build/live-free.ssd" : "build/live.ssd");
const liveFile = opt("live", "build/live/live.json");
const tracePath = opt("trace", "build/live/trace.json");
const walkAt = opt("walks", "0,18,26,40,57").split(",").filter(Boolean).map(Number);
const jsonOut = opt("json");
const verbose = args.includes("--verbose");
const TOUR_FRAMES = 2;
const CLOCK_SLACK = 8; // cycles: T2 counts microseconds, from its own phase
const NAME = FREE ? "live-free" : "live";

const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const sym = (name) => {
    if (!(name in syms)) throw new Error(`no symbol ${name}`);
    return syms[name];
};
const live = JSON.parse(fs.readFileSync(liveFile, "utf8"));
const ENTRANCES = live.entrances.length;
if (FREE && sym("LIVE_ENTRANCES") !== ENTRANCES) throw new Error(`${liveFile} has ${ENTRANCES} entrances, the disc ${sym("LIVE_ENTRANCES")}`);

let failures = 0;
const fail = (what) => {
    if (++failures <= 30) console.log(`${NAME}: FAIL ${what}`);
};
process.on("uncaughtException", (e) => {
    console.log(`${NAME}: FAIL ${e.stack}`);
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
const FIELD_CYCLES = sym("FIELD_CYCLES");
const viewAt = (y, c) => VIEW_ADDR + (y >> 3) * SCREEN_ROW + c * 8 + (y & 7);

const session = new MachineSession("Master");
await quietly(() => session.initialise());
const tm = session._machine;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const now = () => tm.elapsedCycles;
const word = (a) => ram[a] | (ram[a + 1] << 8);
const bufferByte = (buffer, a) => ram[a + (buffer ? 0x8000 : 0)];
const bankAt = (bank, a) => cpu.romOffset + bank * 16384 + (a - 0x8000);

session.loadDisc(path.resolve(disc));
await quietly(() => session.autoboot());
const t0 = Date.now();
try {
    await session.runUntilAddress(sym("live_loop"), 120);
} catch {
    throw new Error("didn't reach live_loop in 120s of emulated time");
}
const bootSecs = now() / 2e6;

// --- The hooks.
const video = session._video;
const R9 = video.regs[9];
const BANK_OBJ = sym("BANK_OBJ"), BANK_RASTER = sym("BANK_RASTER"), BANK_GLUE = sym("BANK_GLUE");
const OBJECTS = sym("objects_frame"), FRONT_DONE = sym("live_front_done");
const RASTER = sym("raster_frame"), FILL_DONE = sym("live_fill_done");
const FB_BEGIN = sym("frame_begin"), FB_END = sym("frame_end");
const LIVE_LOOP = sym("live_loop");
const LV_CAM = sym("lv_cam"), LV_AREA = sym("lv_area");
const SPAN_US = sym("span_us"), T_FRONT = sym("T_FRONT"), T_FILL = sym("T_FILL");
const CLOCK_TO = sym("clock_to"), CLOCK_READ = sym("clock.again");
let lastClock = null;
const TEXT_WAITING = sym("text_catch_up.waiting");
let textWaits = 0; // frames that waited for the beam to catch the text up
const JSR = 0x20;
const s16 = (v) => (v & 0x8000 ? v - 0x10000 : v);
const camera = () => {
    const b = ram.subarray(LV_CAM, LV_CAM + 9);
    return [b[0] | (b[1] << 8), b[2] | (b[3] << 8), b[4] | (b[5] << 8), b[6], b[7], b[8]];
};
// what the frame's objects_frame was given besides the camera (the logic's
// disc): set below
let frameExtra = () => ({});
let onLoop = () => {};
let onPassed = () => {};

const pending = []; // frames handed over, not yet shown
const frames = []; // every frame handed over, in order
const shown = []; // every flip: the frame and the view's bytes shown
let current = null; // the frame being made
let inFrame = false, calling = false;
let lastFlipT = null, lastEndT = null;
let flips = 0, viewWrites = 0, textWrites = 0;
let script = "start"; // what the script is doing (frames before it begins aren't counted)
let clockChecked = 0;
let afterClock = null; // the span whose clock_to is running

cpu.debugInstruction.add((addr, opcode) => {
    const bank = cpu.romsel & 15;
    if (opcode === JSR && word(addr + 1) === FB_BEGIN) calling = true;
    if (addr === LIVE_LOOP) {
        if (current && !current.ended) fail("live_loop again before frame_end");
        current = { tLoop: now() };
        onLoop();
    } else if (!FREE && addr === LIVE_PASSED) {
        onPassed(cpu.a);
    } else if (addr === TEXT_WAITING) {
        textWaits++;
    } else if (addr === CLOCK_READ) {
        lastClock = now(); // (the last of its tries is the one kept)
    } else if (addr === OBJECTS && bank === BANK_OBJ && current) {
        current.tFront = now();
        current.clockFront = lastClock;
        current.camera = camera();
        current.area = ram[LV_AREA];
        current.script = script;
        Object.assign(current, frameExtra());
    } else if (addr === FRONT_DONE && current?.tFront !== undefined) {
        current.front = now() - current.tFront;
        afterClock = "front";
    } else if (addr === RASTER && bank === BANK_RASTER && current) {
        current.tFill = now();
        current.clockFill = lastClock;
    } else if (addr === FILL_DONE && current?.tFill !== undefined) {
        current.fill = now() - current.tFill;
        afterClock = "fill";
    } else if (addr === CLOCK_TO && bank === BANK_GLUE && afterClock && current) {
        // the span the BBC times: from clock's read before the call to its
        // read after
        const from = afterClock === "front" ? current.clockFront : current.clockFill;
        current[`${afterClock}Span`] = lastClock - from;
        afterClock = null;
    } else if (addr === FB_BEGIN && calling) {
        calling = false;
        if (inFrame) fail("frame_begin twice, without frame_end");
        inFrame = true;
    } else if (addr === FB_END) {
        if (!inFrame) fail("frame_end without frame_begin");
        inFrame = false;
        if (!current || current.front === undefined || current.fill === undefined) {
            // (the frame live_loop was begun before the hooks went in)
            if (frames.length || flips) fail("frame_end without a whole frame made");
            pending.push({ n: -1, buffer: (cpu.acccon >> 2) & 1, unhooked: true });
            return false;
        }
        current.ended = true;
        current.n = frames.length;
        current.buffer = (cpu.acccon >> 2) & 1;
        if (!FREE) {
            // the crosshair this buffer has (lv_cross_on)
            const b = ram[sym("draw_buffer")];
            current.cross = ram[LV_XON + b] ? [ram[LV_XX + b], ram[LV_XY + b]] : null;
        }
        if (lastEndT !== null) current.loop = now() - lastEndT;
        lastEndT = now();
        // the BBC's own timing of each half, as its figures show it
        for (const [half, at] of [["front", T_FRONT], ["fill", T_FILL]]) {
            const us = ram[SPAN_US + at] | (ram[SPAN_US + at + 1] << 8) | (ram[SPAN_US + at + 2] << 16);
            const span = current[`${half}Span`];
            current[`${half}Bbc`] = 2 * us;
            if (span === undefined || Math.abs(2 * us - span) > CLOCK_SLACK)
                fail(`frame ${current.n}: the BBC timed ${half} at ${2 * us} cycles, the harness ${span}`);
            else clockChecked++;
        }
        checkText(current);
        frames.push(current);
        pending.push(current);
        if (pending.length > 1) fail(`frame ${current.n} handed over before frame ${pending[0].n} was shown`);
    }
    return false;
});

// The text (src/text.6502).
const TEXT_WANT = sym("text_want"), TEXT_SHOWN = sym("text_shown"), TEXT_CELLS = sym("TEXT_CELLS");
const TEXT_COLS = sym("TEXT_COLS"), GLYPH = sym("GLYPH"), TEXT_FIRST = sym("TEXT_FIRST"), TEXT_LAST = sym("TEXT_LAST");
const TEXT_FONT = sym("text_font"), TEXT_INK = sym("text_ink"), TEXT_ROW = sym("text_row");
const latin = (a, n) => Buffer.from(ram.subarray(a, a + n)).toString("latin1");
const cellAt = (cell) => (ram[TEXT_ROW + Math.floor(cell / TEXT_COLS)] << 8) + (cell % TEXT_COLS) * GLYPH;
const centred = (s) => {
    const pad = TEXT_COLS - s.length;
    return " ".repeat(pad >> 1) + s + " ".repeat(pad - (pad >> 1));
};
let textChecked = 0;
function checkText(frame) {
    const name = centred(live.areas[frame.area].name);
    let second;
    if (FREE) {
        const e = live.entrances[frame.entrance];
        second = `entrance ${String(e.entrance).padStart(2)} ${frame.demo ? "demo" : "    "}`;
        if (e.area !== frame.area) fail(`frame ${frame.n}: entrance ${e.name} in area ${frame.area}`);
    } else second = frame.over ? centred("game over") : " ".repeat(TEXT_COLS);
    const lines = name + second;
    if (latin(TEXT_WANT, lines.length) !== lines)
        fail(`frame ${frame.n} (area ${frame.area}) wants the text ${JSON.stringify(latin(TEXT_WANT, lines.length))}, not ${JSON.stringify(lines)}`);
    if (latin(TEXT_SHOWN, lines.length) !== lines)
        fail(`frame ${frame.n} (area ${frame.area}) handed over showing ${JSON.stringify(latin(TEXT_SHOWN, lines.length))}`);
    textChecked++;
}
let glyphsChecked = 0;
function checkGlyphs(buffer, what) {
    glyphsChecked++;
    for (let cell = 0; cell < TEXT_CELLS; cell++) {
        let ch = ram[TEXT_SHOWN + cell];
        if (ch < TEXT_FIRST || ch > TEXT_LAST) ch = 32;
        const ink = ram[TEXT_INK + Math.floor(cell / TEXT_COLS)];
        // (the font is in BANK_DATA, after LiveData)
        const font = fontByte(TEXT_FONT + (ch - TEXT_FIRST) * GLYPH);
        const at = cellAt(cell);
        for (let i = 0; i < GLYPH; i++)
            if (bufferByte(buffer, at + i) !== (font(i) & ink))
                return fail(`${what}: cell ${cell}'s ${hex(at + i, 4)} isn't ${JSON.stringify(String.fromCharCode(ch))}'s`);
    }
}
const BANK_DATA = sym("BANK_DATA");
const fontByte = (a) => (i) => ram[bankAt(BANK_DATA, a + i)];

// The view's bytes, by offset from SCREEN.
const SCREEN_BYTES = 0x8000 - SCREEN;
const viewMask = new Uint8Array(SCREEN_BYTES);
for (let y = 0; y < VIEW_H; y++) for (let c = 0; c < VIEW_BYTES; c++) viewMask[viewAt(y, c) - SCREEN] = 1;
const beamLine = () => video.vertCounter * (R9 + 1) + video.scanlineCounter + video.vertAdjustCounter;

function flipped(to) {
    flips++;
    const t = now();
    let bad = 0;
    for (let i = 0; i < SCREEN_BYTES; i++)
        if (!viewMask[i] && ram[SCREEN + i] !== ram[SCREEN + i + 0x8000] && bad++ < 2)
            fail(`flip ${flips}: ${hex(SCREEN + i, 4)}, outside the view, differs between the buffers`);
    if (flips % 8 === 1) checkGlyphs(to, `flip ${flips}`);
    const frame = pending.shift();
    if (!frame && !frames.length) return; // (handed over before the hooks went in)
    if (!frame) return fail(`flip ${flips} with no frame handed over`);
    if (frame.buffer !== to) return fail(`flip ${flips} to buffer ${to}, but frame ${frame.n} was drawn in ${frame.buffer}`);
    if (lastFlipT !== null) frame.flip = t - lastFlipT;
    lastFlipT = t;
    if (frame.unhooked) return;
    const rows = [];
    for (let y = 0; y < VIEW_H; y++) {
        const row = Buffer.alloc(VIEW_BYTES);
        for (let c = 0; c < VIEW_BYTES; c++) row[c] = bufferByte(to, viewAt(y, c));
        rows.push(row.toString("hex"));
    }
    shown.push({ frame, rows });
}

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

// --- The script's timing.
const FIELD = FIELD_CYCLES;
const LIMIT = 400; // fields to wait for anything before failing
async function framesMade(n, what) {
    const want = frames.length + n;
    for (let i = 0; frames.length < want; i++) {
        if (i > LIMIT) throw new Error(`${what}: no frame for ${LIMIT} fields`);
        await session.runFor(FIELD);
    }
}
async function untilFrame(test, what) {
    for (let i = 0; !(frames.length && test(frames.at(-1))); i++) {
        if (i > LIMIT * 4) throw new Error(`${what}: not after ${LIMIT * 4} fields`);
        await session.runFor(FIELD);
    }
}
async function until(test, what, limit = LIMIT * 4) {
    for (let i = 0; !test(); i++) {
        if (i > limit) throw new Error(`${what}: not after ${limit} fields`);
        await session.runFor(FIELD);
    }
}
const press = async (key) => {
    session.keyDownRaw(BBC[key]);
    await session.runFor(3 * FIELD);
    session.keyUpRaw(BBC[key]);
};

// --- The logic's disc.
const LIVE_PASSED = FREE ? -1 : sym("lv_pass.live_passed");
const LV_XON = FREE ? 0 : sym("lv_xon"), LV_XX = FREE ? 0 : sym("lv_xx"), LV_XY = FREE ? 0 : sym("lv_xy");
let summary = "";
if (!FREE) await logicScript();
else await freeScript();
const emulated = now() / 2e6 - bootSecs;

async function logicScript() {
    const trace = JSON.parse(fs.readFileSync(tracePath, "utf8"));
    const PASS_FIELDS = sym("PASS_FIELDS");
    const BANK_DB = sym("BANK_DB");
    const ZXV_ORG = sym("ZXV_ORG"), ZXV_END = sym("ZXV_END"), ZXV = sym("zxv");
    const LOGIC_DB = sym("LOGIC_DB"), DB_MOVE = sym("DB_MOVE");
    const PTRS = sym("ZXV_PTRS").map((o) => ZXV_ORG + o);
    const LOGIC_WORK = sym("LOGIC_WORK"), LOGIC_WORK_END = sym("logic_work_end");
    const S = (n) => sym(n);
    const V = (n) => ram[S(n)];
    const V16 = (n) => word(S(n));

    // Where each of the original's compared bytes is on the BBC: the mirror,
    // the rest of the variables by name in main RAM, the database in BANK_DB.
    const [dbLo, dbHi] = trace.layout.database;
    if (dbLo !== sym("ZX_DB") || LOGIC_DB + (dbHi - dbLo) !== 0xc000) throw new Error("the database's layout isn't the disc's");
    const regions = [[ZXV_ORG, ZXV_END - ZXV_ORG, ZXV, "main"]];
    for (const v of trace.layout.vars.filter((v) => v.addr < ZXV_ORG || v.addr >= ZXV_END)) regions.push([v.addr, v.size, S(v.name), "main"]);
    regions.push([dbLo, dbHi - dbLo, LOGIC_DB, "db"]);
    const names = new Map();
    for (const v of trace.layout.vars) for (let i = 0; i < v.size; i++) names.set(v.addr + i, v.size > 1 ? `${v.name}[${i}]` : v.name);
    const at = (b, space) => (space === "db" ? bankAt(BANK_DB, b) : b);
    function bbcOf(a) {
        for (const [z, n, b, space] of regions) if (a >= z && a < z + n) return at(b + a - z, space);
        throw new Error(`${hex(a, 4)} isn't a compared address`);
    }
    const isPtr = new Set(PTRS.flatMap((p) => [p, p + 1]));
    // write the original's value v of address a into the disc's state, its
    // database pointers moved
    function put(a, v) {
        if (isPtr.has(a)) {
            const p = PTRS.includes(a) ? a : a - 1;
            const w = ((exp[p] | (exp[p + 1] << 8)) + DB_MOVE) & 0xffff;
            ram[bbcOf(p)] = w & 0xff;
            ram[bbcOf(p + 1)] = w >> 8;
        } else ram[bbcOf(a)] = v;
    }
    function compare() {
        const diffs = [];
        for (const [z, n, b, space] of regions) {
            const got = Uint8Array.from(ram.subarray(at(b, space), at(b, space) + n));
            if (z === ZXV_ORG) {
                for (const p of PTRS) {
                    const o = p - ZXV_ORG;
                    const w = (got[o] | (got[o + 1] << 8)) - DB_MOVE;
                    got[o] = w & 0xff;
                    got[o + 1] = (w >> 8) & 0xff;
                }
            }
            for (let i = 0; i < n; i++) if (got[i] !== exp[z + i]) diffs.push([z + i, exp[z + i], got[i]]);
        }
        return diffs;
    }
    function report(where, diffs) {
        const lines = [`${where}: ${diffs.length} bytes differ (transcription, disc):`];
        for (const [a, e, g] of diffs.slice(0, 12)) {
            const name = names.get(a) ?? (a >= dbLo ? `Database ${hex(a, 4)}` : `ZX ${hex(a, 4)}`);
            lines.push(`  ${name.padEnd(20)} ${hex(e)}  ${hex(g)}`);
        }
        fail(lines.join("\n"));
    }
    // the logic's camera, in lv_cam's order, from the expected state
    const zw = (a) => exp[a] | (exp[a + 1] << 8);
    // (the angles mod 72, as the renderer takes them: src/live.6502's mod72)
    const expCamera = () => [zw(0x8762), zw(0x8764), zw(0x8766), exp[0x876d] % 72, exp[0x876c] % 72, exp[0x876e] % 72];
    // the objects' flags as the logic has them: each record's first byte, the
    // area's and then the globals', in the index's order
    function expFlags() {
        const out = [];
        let p = zw(0x8864);
        for (let i = 0; i < exp[0x8863]; i++, p += exp[p + 8]) out.push(exp[p]);
        p = 0x87a5;
        for (let i = 0; i < exp[0x890f]; i++, p += exp[p + 8]) out.push(exp[p]);
        return out;
    }

    const exp = new Uint8Array(0x10000);
    for (const [a, v] of trace.start) exp[a] = v;
    // The game's start, as the disc booted: its state now must be the
    // transcription's start; it's written back before each run.
    let diffs = compare();
    if (diffs.length) report("the disc's start", diffs);
    const work = Uint8Array.from(ram.subarray(LOGIC_WORK, LOGIC_WORK_END));
    const db = Uint8Array.from(ram.subarray(bankAt(BANK_DB, LOGIC_DB), bankAt(BANK_DB, 0xc000)));
    const startExp = Uint8Array.from(exp);

    // The keys: the ZX's names as the BBC's (src/input.6502's KEY_MAP).
    const bbcKey = (k) => (/^[0-9]$/.test(k) ? BBC[`K${k}`] : BBC[k]);
    let held = new Set();
    function hold(keys) {
        for (const k of held) if (!keys.includes(k)) session.keyUpRaw(bbcKey(k));
        for (const k of keys) if (!held.has(k)) session.keyDownRaw(bbcKey(k));
        held = new Set(keys);
    }

    // What the live_loop hook does next: write the queued state and ask the
    // disc to take it; keep the clock's minute away, or bring it on.
    let writes = null, minuteDue = false, applied = 0;
    const LV_MINUTE = S("lv_minute"), LV_REQUEST = S("lv_request");
    onLoop = () => {
        const f = word(S("fields"));
        const m = minuteDue ? f : f + 20000;
        ram[LV_MINUTE] = m & 0xff;
        ram[LV_MINUTE + 1] = (m >> 8) & 0xff;
        if (writes) {
            writes();
            writes = null;
            ram[LV_REQUEST] = 1;
            applied++;
        }
    };
    // A pass with no key held is the original waiting in its input
    // ($9990): what its first part has cleared, and no keys read.
    let waited = false;
    const WAITING = { 0x8920: 1, 0x8921: 1, 0x8a69: 1, 0x8bf1: 1, 0x8bf0: 1, 0x8a64: 1, 0x8a1f: 1, 0x8a1e: 1 };
    const zxOf = (n) => trace.layout.vars.find((v) => v.name === n);
    function waiting() {
        for (const a of Object.keys(WAITING)) exp[a] = 0;
        for (const n of ["ActionIndex", "KeyCount", "LastKeyCount"]) exp[zxOf(n).addr] = 0;
        const rows = zxOf("KeyRows");
        for (let i = 0; i < rows.size; i++) exp[rows.addr + i] = 0;
    }
    // The pass the disc is to take next, and what it took.
    let want = null; // {rec, where, early: asked for with the pokes before it}
    let taken = null; // an early one's step, once the disc has taken it
    let passesOk = 0, passesSeen = 0, walksOk = 0;
    const passLog = []; // each pass that ran: what its frames are to show
    let overs = 0;
    onPassed = (a) => {
        if (a === 0 || (a === 2 && !want && exp[0x8bf2])) {
            // no key: the original waits in its input; or the game's over,
            // which the input's first part finds, and no pass comes after
            waited = true;
            if (a === 2) overs++;
            return;
        }
        waited = false;
        passesSeen++;
        if (!want) return fail(`a pass (answer ${a}) the script didn't ask for, at ${script}`);
        const { rec, where } = want;
        if (want.early) taken = rec;
        want = null;
        if (a !== rec.result) fail(`${where}: the pass answered ${a}, not ${rec.result}`);
        const P0 = expCamera(), area0 = ram[LV_AREA], flags0 = expFlags();
        if (verbose) console.log(`  pass ${where}: answered ${a}, from ${P0}`);
        for (const [ad, v] of rec.changes) exp[ad] = v;
        const d = compare();
        if (d.length) report(where, d);
        else passesOk++;
        // the hooks' records: the walks and the loads
        const walks = rec.walks, n = V("lv_walks");
        let ok = n === walks.length && V("lv_loaded") === (rec.loaded ? 1 : 0);
        if (ok && n) {
            const w = walks[0];
            for (let k = 0; k < 3; k++)
                if (((w[3 + k] - w[k]) & 0xffff) !== word(S("lv_walk_d") + 2 * k)) ok = false;
            if (V("lv_walk_jet") !== w[6]) ok = false;
        }
        if (ok) walksOk++;
        else fail(`${where}: the disc's hooks saw ${n} walks (${V("lv_loaded") ? "an area loaded" : "no load"}), the transcription ${JSON.stringify(walks)}${rec.loaded ? ", a load" : ""}`);
        passLog.push({ where, P0, P1: expCamera(), walks, loaded: rec.loaded, area0, n: passLog.length, flags0, margin: exp[0x88d0] });
        for (const [ad, v] of rec.then) exp[ad] = v;
    };
    // Each frame: the animation's state as lv_camera left it, the logic's
    // view of the objects, and the pass whose frames these are.
    // (ix_flags whole: while the old area's frames show, the renderer's
    // copy indexes the old area's flags, which logic_go_shown hasn't yet
    // replaced, though the logic has indexed the new area's)
    const IX_MAX = S("IX_MAX");
    frameExtra = () => ({
        anOn: V("an_on"), e: (V16("lv_now") - V16("an_t0")) & 0xffff, pass: passLog.at(-1), over: V("lv_over") !== 0,
        ixFlags: [...ram.subarray(S("ix_flags"), S("ix_flags") + IX_MAX)], ixN: V("ix_n"),
        logicCam: expCamera(), expFlags: expFlags(), switching: V("lv_switch") !== 0,
    });

    // The runs.
    let runsOk = 0, steps = 0;
    for (const run of trace.runs) {
        script = run.name;
        const before = failures;
        hold([]);
        writes = () => {
            exp.set(startExp);
            waited = false;
            ram.set(work, LOGIC_WORK);
            ram.set(db, bankAt(BANK_DB, LOGIC_DB));
        };
        await until(() => !writes, `${run.name}: the start`);
        await framesMade(2, `${run.name}: the start`);
        for (let i = 0; i < run.steps.length; i++) {
            const rec = run.steps[i];
            const where = `${run.name} ${rec.line}`;
            steps++;
            if (rec.frames) {
                await framesMade(rec.frames, where);
            } else if (rec.poke || rec.fcl) {
                // the results of this step and those straight after it (a
                // poke's bytes, an FCL script's changes, and what the
                // renderer does after) into the disc's state, which it takes
                // as it is; a pass after them with the keys held as they
                // are is asked for now, as it may come in the same frame
                // (the expected state changes as the disc's does, at the
                // live_loop that writes it)
                const batch = [];
                let j = i;
                for (; j < run.steps.length && (run.steps[j].poke || run.steps[j].fcl); j++)
                    batch.push(...run.steps[j].changes, ...run.steps[j].then);
                steps += j - i - 1;
                i = j - 1;
                const next = run.steps[j];
                if (next?.keys && !next.tick && held.size && next.names.join() === [...held].join())
                    want = { rec: next, where: `${run.name} ${next.line}`, early: true };
                else hold([]);
                writes = () => {
                    for (const [a, v] of batch) exp[a] = v;
                    for (const [a] of batch) put(a, exp[a]);
                };
                await until(() => !writes, where);
                if (!want?.early) await framesMade(1, where);
            } else {
                minuteDue = rec.tick;
                if (taken === rec) taken = null; // (asked for with the pokes before it, and taken)
                else {
                    if (want?.rec !== rec) want = { rec, where };
                    hold(rec.names);
                    await until(() => !want, `${where}: the pass`);
                }
                minuteDue = false;
                // the next pass's keys held on now if they're the same
                const next = run.steps.slice(i + 1).find((r) => !r.frames);
                if (!next || (next.keys && (next.names.join() !== rec.names.join() || next.tick))) hold([]);
            }
        }
        hold([]);
        // the last pass's frames shown, and the state as the transcription's,
        // as the original's is while it waits in its input for a key
        await until(() => frames.length && !frames.at(-1).anOn && !frames.at(-1).switching, `${run.name}: the end`);
        await framesMade(1, `${run.name}: the end`);
        if (waited) waiting();
        const d = compare();
        if (d.length) report(`${run.name}: the end`, d);
        if (failures === before) runsOk++;
    }
    script = "end";

    // Every frame's camera: the logic's, or a pass's frames' as decision 4's
    // rule takes it (lv_setup), at the fraction its fields give it.
    const mod72 = (a) => ((a % 72) + 72) % 72;
    const turnOf = (a1, a0) => {
        const d = mod72(a1 - a0);
        return d >= 37 ? d - 72 : d;
    };
    const scale = (d, f) => Math.sign(d) * ((Math.abs(d) * f) >> 8);
    const turnBy = (t, f) => Math.sign(t) * ((Math.abs(t) * f + 128) >> 8);
    function between(p, f) {
        // the way the pass's frames go: its walk, or straight
        const same = p.P0.join() === p.P1.join();
        let d = null, hold = false, turns = [0, 0, 0];
        if (p.loaded) {
            if (p.walks.length !== 1) return null;
        } else {
            if (same) return null;
            turns = [3, 4, 5].map((k) => turnOf(p.P1[k], p.P0[k]));
        }
        if (p.walks.length === 1) {
            const w = p.walks[0];
            const wd = [0, 1, 2].map((k) => s16((w[3 + k] - w[k]) & 0xffff));
            const near = [0, 1, 2].every((k) => Math.abs(s16((p.P0[k] + wd[k] - p.P1[k]) & 0xffff)) <= p.margin);
            if (p.loaded || near) (d = wd), (hold = !w[6]);
        }
        if (!d) d = [0, 1, 2].map((k) => s16((p.P1[k] - p.P0[k]) & 0xffff));
        const c = [0, 1, 2].map((k) => (p.P0[k] + (k === 1 && hold ? 0 : scale(d[k], f))) & 0xffff);
        return [...c, ...[0, 1, 2].map((k) => mod72(p.P0[3 + k] + turnBy(turns[k], f)))];
    }
    let between_n = 0, camsOk = 0, flagsOk = 0;
    const perPass = new Map();
    for (const f of frames.filter((f) => f.camera && f.ixFlags)) {
        let want;
        if (f.anOn) {
            if (!f.pass) {
                fail(`frame ${f.n}: a pass's frames before any pass`);
                continue;
            }
            if (f.e >= PASS_FIELDS) fail(`frame ${f.n}: ${f.e} fields into a pass's frames`);
            const frac = Math.floor((256 * f.e) / PASS_FIELDS);
            want = between(f.pass, frac);
            if (!want) {
                fail(`frame ${f.n} (${f.pass.where}): frames for a pass that shows none`);
                continue;
            }
            between_n++;
            perPass.set(f.pass.n, (perPass.get(f.pass.n) ?? 0) + 1);
            if (f.pass.loaded && f.area !== f.pass.area0) fail(`frame ${f.n} (${f.pass.where}): the walk into the new area shown in area ${f.area}`);
        } else want = f.logicCam;
        if (want.join() !== f.camera.join())
            fail(`frame ${f.n} (${f.pass?.where ?? f.script}): the camera ${f.camera}, not ${want}${f.anOn ? ` (${f.e} fields into the pass's frames)` : ""}`);
        else camsOk++;
        // the objects' flags: the logic's, but the old area's while its frames
        // show (or the area's change waits for the frame after them)
        const old = f.pass?.loaded && (f.anOn || f.switching);
        const flags = old ? f.pass.flags0 : f.expFlags;
        f.flags = f.ixFlags.slice(0, old ? flags.length : f.ixN);
        f.hidden = f.flags.map((v) => (v & 0x60) !== 0);
        if (flags.join() !== f.flags.join()) fail(`frame ${f.n} (${f.pass?.where ?? f.script}): ix_flags ${f.flags}, not ${flags}`);
        else flagsOk++;
    }
    const counts = [...perPass.values()].sort((a, b) => a - b);
    summary = `${trace.runs.length} runs (${runsOk} as the transcription), ${steps} steps; ` +
        `${passesSeen} passes taken, ${passesOk} with the transcription's state, ${walksOk} with its walks and loads, ${overs} that found the game over; ` +
        `${camsOk} frames with the camera as the logic and decision 4 have it, ${between_n} of them between passes ` +
        `(${perPass.size} passes shown so, ${counts.length ? counts[counts.length >> 1] : 0} frames each at the median), ` +
        `${flagsOk} with the logic's objects' flags`;
}

async function freeScript() {
    const LV_ENTRANCE = sym("lv_entrance"), LV_DEMO = sym("lv_demo");
    frameExtra = () => ({ entrance: ram[LV_ENTRANCE], demo: ram[LV_DEMO] !== 0 });
    // The tour: SPACE from each entrance to the next, round to the first.
    script = "still";
    await untilFrame((f) => f.entrance === 0, "the first entrance");
    let spaceOk = 0;
    for (let i = 0; i < ENTRANCES; i++) {
        await framesMade(TOUR_FRAMES, `the tour at ${live.entrances[i].name}`);
        const next = (i + 1) % ENTRANCES;
        script = "entrance";
        await press("SPACE");
        await untilFrame((f) => f.entrance === next || f.entrance !== i, `SPACE at ${live.entrances[i].name}`);
        if (frames.at(-1).entrance === next) spaceOk++;
        else fail(`SPACE at ${live.entrances[i].name} went to ${live.entrances[frames.at(-1).entrance].name}`);
        script = "still";
    }

    // The walks: each hold's keys, and what each frame's camera may do.
    const STEPS = 72;
    const STEP = live.step;
    const sin = (y) => Math.sin((y * 5 * Math.PI) / 180);
    const HOLDS = [
        { keys: ["UP"], move: "on", frames: 5 },
        { keys: ["LEFT"], move: "left", frames: 4 },
        { keys: ["O"], move: "on", frames: 3 },
        { keys: ["RIGHT", "UP"], move: "right+on", frames: 4 },
        { keys: ["P"], move: "up", frames: 3 },
        { keys: ["L"], move: "down", frames: 2 },
        { keys: ["N"], move: "rolll", frames: 3 },
        { keys: ["M"], move: "rollr", frames: 2 },
        { keys: ["Q"], move: "left", frames: 2 },
        { keys: ["W"], move: "right", frames: 2 },
        { keys: ["DOWN"], move: "back", frames: 3 },
        { keys: ["K"], move: "back", frames: 2 },
    ];
    const mod = (a) => ((a % STEPS) + STEPS) % STEPS;
    // What a move does to a camera, in the disc's own step table (the model's
    // walk: tools/mklive.py), checked against the camera it reports.
    const LD = sym("st_dx"), LZ = sym("st_dz");
    const glueByte = (a) => ram[bankAt(BANK_GLUE, a)];
    const s8 = (v) => (v & 0x80 ? v - 256 : v);
    const clamp = (v) => Math.max(0, Math.min(0x7fff, v));
    function moved(c, move) {
        let [x, y, z, yaw, pitch, roll] = c;
        for (const m of move.split("+")) {
            if (m === "left") yaw = mod(yaw - 1);
            else if (m === "right") yaw = mod(yaw + 1);
            else if (m === "up") pitch = mod(pitch - 1);
            else if (m === "down") pitch = mod(pitch + 1);
            else if (m === "rolll") roll = mod(roll + 1);
            else if (m === "rollr") roll = mod(roll - 1);
        }
        for (const m of move.split("+")) {
            const dx = s8(glueByte(LD + yaw)), dz = s8(glueByte(LZ + yaw));
            if (m === "on") (x = clamp(x + dx)), (z = clamp(z + dz));
            else if (m === "back") (x = clamp(x - dx)), (z = clamp(z - dz));
        }
        return [x, y, z, yaw, pitch, roll];
    }
    // (the step table is the model's walk: floor(STEP sin / 64))
    for (let yaw = 0; yaw < STEPS; yaw++) {
        const dx = s8(glueByte(LD + yaw));
        if (Math.abs(dx - (STEP * sin(yaw))) > 1.01) fail(`the step for yaw ${yaw} is ${dx} across`);
    }
    const same = (a, b) => a.join() === b.join();
    let holdsOk = 0;
    for (const at of walkAt) {
        ram[sym("lv_want")] = at;
        script = "entrance";
        await untilFrame((f) => f.entrance === at, `going to ${live.entrances[at].name}`);
        script = "still";
        await framesMade(1, "settling");
        for (const hold of HOLDS) {
            script = "walk";
            const first = frames.length;
            for (const k of hold.keys) session.keyDownRaw(BBC[k]);
            await framesMade(hold.frames, `holding ${hold.keys}`);
            for (const k of hold.keys) session.keyUpRaw(BBC[k]);
            script = "still";
            await framesMade(2, `after ${hold.keys}`);
            // every frame from the hold's start: as the last, or moved as asked
            let movedN = 0, ok = true;
            for (let i = first; i < frames.length; i++) {
                const was = frames[i - 1].camera, got = frames[i].camera;
                if (same(got, was)) continue;
                if (same(got, moved(was, hold.move))) movedN++;
                else {
                    ok = false;
                    fail(`${hold.keys} at ${live.entrances[at].name}: frame ${i}'s camera ${got} from ${was}`);
                }
            }
            if (movedN < hold.frames - 1) fail(`${hold.keys} at ${live.entrances[at].name}: moved in ${movedN} frames of ${hold.frames}`);
            else if (ok) holdsOk++;
        }
    }

    // The demo: no key until it starts, then a step a frame.
    script = "still";
    await untilFrame((f) => f.demo, "the demo");
    script = "demo";
    const demoFrom = frames.length - 1;
    await framesMade(8, "the demo");
    let demoOk = 0;
    for (let i = demoFrom + 1; i < frames.length; i++) {
        const was = frames[i - 1].camera, got = frames[i].camera;
        if (frames[i].entrance !== frames[i - 1].entrance) continue;
        if (same(got, moved(was, "right"))) demoOk++;
        else fail(`the demo: frame ${i}'s camera ${got} from ${was}`);
    }
    // and a key stops it
    await press("LEFT");
    script = "still";
    await framesMade(2, "after the demo");
    if (frames.at(-1).demo) fail("a key didn't stop the demo");
    await session.runFor(20 * FIELD);
    summary = `${ENTRANCES} entrances (${spaceOk} by SPACE), walks at ${walkAt.length} (${holdsOk} of ` +
        `${walkAt.length * HOLDS.length} holds as asked), the demo (${demoOk} steps)`;
}

// --- Every frame shown against the model.
const requests = [];
const keyOf = (f) => `${f.area}:${f.camera.join(",")}:${f.hidden ? f.hidden.map(Number).join("") : ""}:${f.cross ?? ""}`;
const index = new Map();
for (const { frame } of shown) {
    if (frame.camera.slice(3).some((a) => a >= 72) || frame.camera.slice(0, 3).some((v) => v >= 0x8000)) {
        fail(`frame ${frame.n} (${frame.script}): the camera ${frame.camera} is outside objects_frame's range`);
        frame.camera = [0, 0, 0, 0, 0, 0];
    }
    const k = keyOf(frame);
    if (!index.has(k)) {
        index.set(k, requests.length);
        const r = { area: frame.area, camera: frame.camera };
        if (frame.hidden) r.hidden = frame.hidden;
        if (frame.cross) r.cross = frame.cross;
        requests.push(r);
    }
}
const py = spawnSync(path.join(root, ".venv/bin/python"), ["-I", path.join(root, "tools/mklive.py"),
    path.join(root, "build/data/driller.json"), "--render"], {
    input: JSON.stringify({ areas: live.areas, cameras: requests }),
    env: { ...process.env, FREESCAPE_DISPLAY: live.display },
    maxBuffer: 1 << 30,
});
if (py.status !== 0) throw new Error(`the model's render failed: ${py.stderr}`);
const views = JSON.parse(py.stdout);
let compared = 0, wrong = 0;
for (const { frame, rows } of shown) {
    const want = views[index.get(keyOf(frame))];
    compared++;
    for (let y = 0; y < VIEW_H; y++)
        if (rows[y] !== want[y]) {
            wrong++;
            const c = [...Array(VIEW_BYTES).keys()].find((c) => rows[y].slice(2 * c, 2 * c + 2) !== want[y].slice(2 * c, 2 * c + 2));
            fail(`frame ${frame.n} (${frame.script}, area ${frame.area}, camera ${frame.camera}${frame.cross ? `, cross ${frame.cross}` : ""}) shown with line ${y}, ` +
                `byte ${c} &${rows[y].slice(2 * c, 2 * c + 2)}, not the model's &${want[y].slice(2 * c, 2 * c + 2)}`);
            break;
        }
}

// --- The figures, by what each frame did: an area's first frame, the
// angles changed (the transform's cache refilled), the camera moved (the
// cache kept), nothing changed, or the free camera's demo.
for (let i = 0; i < frames.length; i++) {
    const f = frames[i], p = frames[i - 1];
    if (f.script === "start") f.kind = "start";
    else if (!p || f.area !== p.area || (FREE && f.entrance !== p.entrance)) f.kind = "entrance";
    else if (f.demo) f.kind = "demo";
    else if (f.camera.slice(3).join() !== p.camera.slice(3).join()) f.kind = "turning";
    else if (f.camera.join() !== p.camera.join()) f.kind = "walking";
    else f.kind = "standing";
}
const fields = (c) => c / FIELD_CYCLES;
const two = (v) => Math.round(v * 100) / 100;
const pct = (xs, p) => {
    const s = [...xs].sort((a, b) => a - b);
    return s[Math.min(s.length - 1, Math.ceil((p / 100) * s.length) - 1)];
};
const median = (xs) => {
    const s = [...xs].sort((a, b) => a - b);
    const m = s.length >> 1;
    return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2;
};
const stats = (xs) => (xs.length ? `${two(median(xs))} / ${two(pct(xs, 90))} / ${two(Math.max(...xs))}` : "-");
const counted = frames.filter((f) => f.kind !== "start");
const row = (label, fs) => {
    const cols = [
        fs.filter((f) => f.flip !== undefined).map((f) => fields(f.flip)),
        fs.filter((f) => f.loop !== undefined).map((f) => fields(f.loop)),
        fs.map((f) => fields(f.front)),
        fs.map((f) => fields(f.fill)),
        fs.filter((f) => f.loop !== undefined).map((f) => fields(f.loop - f.front - f.fill)),
    ];
    console.log(`  ${label.padEnd(10)} ${String(fs.length).padStart(4)}  ${cols.map((c) => stats(c).padEnd(20)).join(" ")}`);
};
console.log(`${NAME}: ${summary}; ${compared} frames shown, ` +
    `${compared - wrong} the model's view byte for byte (${requests.length} views); ${textChecked} with their lines; ` +
    `${viewWrites} writes to the view and ${textWrites} outside it, each where it may be; ${glyphsChecked} flips' text ` +
    `checked against the font; the BBC's own timing within ${CLOCK_SLACK} cycles ${clockChecked} times; ` +
    `${textWaits} waits for the beam to catch the text up`);
console.log(`${NAME}: fields a frame, median / p90 / max:`);
console.log(`  ${"frames".padEnd(10)} ${"n".padStart(4)}  ${"flip to flip".padEnd(20)} ${"loop".padEnd(20)} ` +
    `${"1-7 objects".padEnd(20)} ${"8-10 fill".padEnd(20)} ${"the rest".padEnd(20)}`);
row("all", counted);
for (const k of ["entrance", "standing", "walking", "turning", ...(FREE ? ["demo"] : [])]) row(k, counted.filter((f) => f.kind === k));
console.log(`${NAME}: ${emulated.toFixed(1)}s emulated in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
if (verbose)
    for (const f of counted)
        console.log(`  ${f.n} area ${f.area} ${f.kind} ${f.script} ${f.camera} flip ${f.flip} front ${f.front} fill ${f.fill}`);
if (jsonOut)
    fs.writeFileSync(jsonOut, JSON.stringify({
        field_cycles: FIELD_CYCLES,
        frames: counted.map((f) => ({
            n: f.n, area: f.area, script: f.script, kind: f.kind, camera: f.camera,
            flip: f.flip ?? null, loop: f.loop ?? null, front: f.front, fill: f.fill,
        })),
    }, null, 1) + "\n");
console.log(failures ? `${NAME}: ${failures} failure(s)` : `${NAME}: ok`);
process.exit(failures ? 1 : 0);
