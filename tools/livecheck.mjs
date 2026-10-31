#!/usr/bin/env node
// The live disc's check: build/live.ssd booted on jsbeeb's full video (the
// CRTC and the vertical sync as the disc programs them), headless, driven by
// its keys through every one of Driller's entrances, walks and turns at some,
// and the demo; every frame shown compared with the model's render of that
// frame's camera (tools/model/render.py, through tools/mklive.py --render),
// byte for byte.
//
//   node tools/livecheck.mjs [--disc build/live.ssd] [--live build/live/live.json]
//                            [--walks 0,18,26,40,57] [--json OUT] [--verbose]
//
// It boots the disc and runs to live_loop, then:
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
// and fails (exit status 1) unless:
//
// - every frame shown is the model's view of the camera and area its
//   objects_frame was given (lv_cam, lv_area), byte for byte;
// - every flip shows the buffer of the one frame handed over since the last,
//   after it was shown whole; at every flip both buffers hold the same
//   outside the view (decision 21), and at every eighth the text there is
//   text_shown's in the widened font and its lines' inks;
// - every frame handed over wants its entrance's lines (the area's name, the
//   entrance) and they're drawn;
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
// every frame and by kind: an entrance's first frame (the transform's cache
// refilled), a still frame, a walk, a turn (or look or roll), the demo.
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
const disc = opt("disc", "build/live.ssd");
const liveFile = opt("live", "build/live/live.json");
const walkAt = opt("walks", "0,18,26,40,57").split(",").filter(Boolean).map(Number);
const jsonOut = opt("json");
const verbose = args.includes("--verbose");
const TOUR_FRAMES = 2;
const CLOCK_SLACK = 8; // cycles: T2 counts microseconds, from its own phase

const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const sym = (name) => {
    if (!(name in syms)) throw new Error(`no symbol ${name}`);
    return syms[name];
};
const live = JSON.parse(fs.readFileSync(liveFile, "utf8"));
const ENTRANCES = sym("LIVE_ENTRANCES");
if (live.entrances.length !== ENTRANCES) throw new Error(`${liveFile} has ${live.entrances.length} entrances, the disc ${ENTRANCES}`);

let failures = 0;
const fail = (what) => {
    if (++failures <= 30) console.log(`live: FAIL ${what}`);
};
process.on("uncaughtException", (e) => {
    console.log(`live: FAIL ${e.stack}`);
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
const BANK_OBJ = sym("BANK_OBJ"), BANK_RASTER = sym("BANK_RASTER");
const OBJECTS = sym("objects_frame"), FRONT_DONE = sym("live_front_done");
const RASTER = sym("raster_frame"), FILL_DONE = sym("live_fill_done");
const FB_BEGIN = sym("frame_begin"), FB_END = sym("frame_end");
const LIVE_LOOP = sym("live_loop");
const LV_CAM = sym("lv_cam"), LV_AREA = sym("lv_area"), LV_ENTRANCE = sym("lv_entrance"), LV_DEMO = sym("lv_demo");
const SPAN_US = sym("span_us"), T_FRONT = sym("T_FRONT"), T_FILL = sym("T_FILL");
const CLOCK_TO = sym("clock_to"), CLOCK_READ = sym("clock.again");
let lastClock = null;
const TEXT_WAITING = sym("text_catch_up.waiting");
let textWaits = 0; // frames that waited for the beam to catch the text up
const JSR = 0x20;
const camera = () => {
    const b = ram.subarray(LV_CAM, LV_CAM + 9);
    return [b[0] | (b[1] << 8), b[2] | (b[3] << 8), b[4] | (b[5] << 8), b[6], b[7], b[8]];
};

const pending = []; // frames handed over, not yet shown
const frames = []; // every frame handed over, in order
const shown = []; // every flip: the frame and the view's bytes shown
let current = null; // the frame being made
let inFrame = false, calling = false;
let lastFlipT = null, lastEndT = null;
let flips = 0, viewWrites = 0, textWrites = 0;
let script = "start"; // what the script is doing (frames before the tour aren't counted)
let clockChecked = 0;
let afterClock = null; // the span whose clock_to is running

cpu.debugInstruction.add((addr, opcode) => {
    const bank = cpu.romsel & 15;
    if (opcode === JSR && word(addr + 1) === FB_BEGIN) calling = true;
    if (addr === LIVE_LOOP) {
        if (current && !current.ended) fail("live_loop again before frame_end");
        current = { tLoop: now() };
    } else if (addr === TEXT_WAITING) {
        textWaits++;
    } else if (addr === CLOCK_READ) {
        lastClock = now(); // (the last of its tries is the one kept)
    } else if (addr === OBJECTS && bank === BANK_OBJ && current) {
        current.tFront = now();
        current.clockFront = lastClock;
        current.camera = camera();
        current.area = ram[LV_AREA];
        current.entrance = ram[LV_ENTRANCE];
        current.demo = ram[LV_DEMO] !== 0;
        current.script = script;
    } else if (addr === FRONT_DONE && current?.tFront !== undefined) {
        current.front = now() - current.tFront;
        afterClock = "front";
    } else if (addr === RASTER && bank === BANK_RASTER && current) {
        current.tFill = now();
        current.clockFill = lastClock;
    } else if (addr === FILL_DONE && current?.tFill !== undefined) {
        current.fill = now() - current.tFill;
        afterClock = "fill";
    } else if (addr === CLOCK_TO && afterClock && current) {
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
    const e = live.entrances[frame.entrance];
    const name = centred(live.areas[frame.area].name);
    const ent = `entrance ${String(e.entrance).padStart(2)} ${frame.demo ? "demo" : "    "}`;
    const lines = name + ent;
    if (latin(TEXT_WANT, lines.length) !== lines)
        fail(`frame ${frame.n} (${e.name}) wants the text ${JSON.stringify(latin(TEXT_WANT, lines.length))}, not ${JSON.stringify(lines)}`);
    if (latin(TEXT_SHOWN, lines.length) !== lines)
        fail(`frame ${frame.n} (${e.name}) handed over showing ${JSON.stringify(latin(TEXT_SHOWN, lines.length))}`);
    if (e.area !== frame.area) fail(`frame ${frame.n}: entrance ${e.name} in area ${frame.area}`);
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
const fontByte = (a) => (i) => ram[cpu.romOffset + BANK_DATA * 16384 + (a + i - 0x8000)];

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

// --- The script.
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
const press = async (key) => {
    session.keyDownRaw(BBC[key]);
    await session.runFor(3 * FIELD);
    session.keyUpRaw(BBC[key]);
};

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
const dataByte = (a) => ram[cpu.romOffset + BANK_DATA * 16384 + (a - 0x8000)];
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
        const dx = s8(dataByte(LD + yaw)), dz = s8(dataByte(LZ + yaw));
        if (m === "on") (x = clamp(x + dx)), (z = clamp(z + dz));
        else if (m === "back") (x = clamp(x - dx)), (z = clamp(z - dz));
    }
    return [x, y, z, yaw, pitch, roll];
}
// (the step table is the model's walk: floor(STEP sin / 64))
for (let yaw = 0; yaw < STEPS; yaw++) {
    const dx = s8(dataByte(LD + yaw));
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
const DEMO_FIELDS = sym("DEMO_FIELDS");
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
const emulated = now() / 2e6 - bootSecs;

// --- Every frame shown against the model.
const requests = [];
const keyOf = (f) => `${f.area}:${f.camera.join(",")}`;
const index = new Map();
for (const { frame } of shown) {
    const k = keyOf(frame);
    if (!index.has(k)) {
        index.set(k, requests.length);
        requests.push({ area: frame.area, camera: frame.camera });
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
            fail(`frame ${frame.n} (${live.entrances[frame.entrance].name}, camera ${frame.camera}) shown with line ${y}, ` +
                `byte ${c} &${rows[y].slice(2 * c, 2 * c + 2)}, not the model's &${want[y].slice(2 * c, 2 * c + 2)}`);
            break;
        }
}

// --- The figures, by what each frame did: an entrance's first frame, the
// angles changed (the transform's cache refilled), the camera moved (the
// cache kept), nothing changed, or the demo's turn.
for (let i = 0; i < frames.length; i++) {
    const f = frames[i], p = frames[i - 1];
    if (f.script === "start") f.kind = "start";
    else if (!p || f.entrance !== p.entrance) f.kind = "entrance";
    else if (f.demo) f.kind = "demo";
    else if (f.camera.slice(3).join() !== p.camera.slice(3).join()) f.kind = "turn";
    else if (!same(f.camera, p.camera)) f.kind = "walk";
    else f.kind = "still";
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
const summary = (xs) => (xs.length ? `${two(median(xs))} / ${two(pct(xs, 90))} / ${two(Math.max(...xs))}` : "-");
const counted = frames.filter((f) => f.kind !== "start");
const row = (label, fs) => {
    const cols = [
        fs.filter((f) => f.flip !== undefined).map((f) => fields(f.flip)),
        fs.filter((f) => f.loop !== undefined).map((f) => fields(f.loop)),
        fs.map((f) => fields(f.front)),
        fs.map((f) => fields(f.fill)),
        fs.filter((f) => f.loop !== undefined).map((f) => fields(f.loop - f.front - f.fill)),
    ];
    console.log(`  ${label.padEnd(10)} ${String(fs.length).padStart(4)}  ${cols.map((c) => summary(c).padEnd(20)).join(" ")}`);
};
console.log(`live: ${ENTRANCES} entrances (${spaceOk} by SPACE), walks at ${walkAt.length} (${holdsOk} of ` +
    `${walkAt.length * HOLDS.length} holds as asked), the demo (${demoOk} steps); ${compared} frames shown, ` +
    `${compared - wrong} the model's view byte for byte (${requests.length} cameras); ${textChecked} with their lines; ` +
    `${viewWrites} writes to the view and ${textWrites} outside it, each where it may be; ${glyphsChecked} flips' text ` +
    `checked against the font; the BBC's own timing within ${CLOCK_SLACK} cycles ${clockChecked} times; ` +
    `${textWaits} waits for the beam to catch the text up`);
console.log("live: fields a frame, median / p90 / max:");
console.log(`  ${"frames".padEnd(10)} ${"n".padStart(4)}  ${"flip to flip".padEnd(20)} ${"loop".padEnd(20)} ` +
    `${"1-7 objects".padEnd(20)} ${"8-10 fill".padEnd(20)} ${"the rest".padEnd(20)}`);
row("all", counted);
for (const k of ["entrance", "still", "walk", "turn", "demo"]) row(k, counted.filter((f) => f.kind === k));
console.log(`live: ${emulated.toFixed(1)}s emulated in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
if (verbose)
    for (const f of counted)
        console.log(`  ${f.n} ${live.entrances[f.entrance].name} ${f.kind} ${f.camera} flip ${f.flip} front ${f.front} fill ${f.fill}`);
if (jsonOut)
    fs.writeFileSync(jsonOut, JSON.stringify({
        field_cycles: FIELD_CYCLES,
        frames: counted.map((f) => ({
            n: f.n, entrance: live.entrances[f.entrance].name, kind: f.kind, camera: f.camera,
            flip: f.flip ?? null, loop: f.loop ?? null, front: f.front, fill: f.fill,
        })),
    }, null, 1) + "\n");
console.log(failures ? `live: ${failures} failure(s)` : "live: ok");
process.exit(failures ? 1 : 0);
