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
// booted with them, written back): a pass's keys pressed on the BBC's
// keyboard once the disc has settled (nothing left to draw: below), at a
// point in the field from a fixed pseudo-random sequence, and held until the
// disc's pass takes them; then, in that instant, held on for the next pass
// if it has the same keys (with any pokes between put in at once), or let
// go, as a tap, once nearly REPEAT_FIELDS have passed since they went down
// (the pace, decision 48); or, if the pass leaves the logic's input a
// minute to take (the trace's "soon"), the next pass comes at once, so its
// keys go down then
// (none, for the pass of none the trace puts in where the next step isn't
// one of keys). A minute's end comes by its clock (the minute otherwise
// kept away), with its pass's keys; a poke or an FCL script's result is
// written into the logic's state and the disc asked to take it
// (lv_request). It fails (exit status 1) unless:
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
//   objects and the crosshair, byte for byte;
// - a key pressed with nothing left to draw is taken by a pass (lv_pass's
//   key_take) within KEY_FIELDS fields; a tap is one pass; and the keys
//   held alone repeat no sooner than REPEAT_FIELDS after the last pass that
//   took a key gone down (lv_made). It reports the held keys' passes, and
//   in tests/logic/pace.txt's run their speed;
// - at the end, with the camera still, every indexed object hidden in
//   ix_flags, and then shown again, each brings a frame (its view the
//   model's with those flags).
//
// With --free, as before the logic came:
//
// - the tour: SPACE, entrance after entrance, round all of them to the first
//   again, each until the disc settles;
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
//   outside the view (decision 21), and that is the panel's picture with
//   the cells panel_shown has drawn over it, as the model renders them
//   (src/panel.6502, tools/model/panel.py: through tools/mkpanel.py
//   --check, after the run);
// - every time the disc sets the panel's values (panel_values: after each
//   pass, with the logic), the cells it wants are the model's for the
//   original's variables (the transcription's state, with the logic; with
//   the free camera, its camera and the variables as the game starts), but
//   the frames a second; and settled, the panel is drawn as wanted within
//   PANEL_FIELDS fields;
// - every frame handed over wants its area's name and message (with the
//   free camera, its entrance), and they're drawn;
// - every write to the view comes between frame_begin and frame_end, into
//   the buffer not shown; outside the view, a write to the buffer shown
//   comes with the beam above the written character row;
// - the BBC's own timing of each half (clock_to's span_us, from User VIA T2)
//   is within CLOCK_SLACK cycles of the harness's count of the same call;
// - the idle loop (docs/research/live.md): every loop that draws nothing
//   (live_idle) finds the inputs of the frame last handed over, all its view
//   is made from (the area and its entries, the camera, the objects' hidden
//   flags, the crosshair), so the view shown is the one they make; and no
//   frame is drawn with the inputs of the frame before it.
//
// "Settled" is: a loop has drawn nothing since the last frame was handed
// over, and with the logic, since the last pass's frames ended (a loop
// while they show may find the camera standing a field, and the one that
// ends them draw), the request is taken and no wait is left. It reports
// when each key pressed so had its pass and when the first view it changed
// was shown (by the frame's flip, the view's bytes compared with the last
// shown), by what changed: the latency a player sees.
//
// It reports fields a frame (median, p90, max) for the whole frame (flip to
// flip, as the BBC shows them; and the loop, from frame_end to frame_end,
// or after loops that drew nothing from the frame's own loop's start)
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
// --profile-rest: the cycles of each frame's "the rest" (its loop but its two
// halves) by routine, the last label at or below each instruction that isn't
// inside a scope (--fine: every label), summed by what the frame did; --top N
const profileRest = args.includes("--profile-rest");
const fineRest = args.includes("--fine");
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
let redrawn = 0; // frames drawn with the last frame's inputs
let visibilityFrames = 0; // frames the visibility probe brought
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
const PANEL_WAITING = sym("panel_catch_up.waiting");
let panelWaits = 0; // frames that waited for the beam to catch the panel up
// The idle loop (docs/research/live.md): live_idle is where live_loop finds the
// frame's inputs as the last frame handed over had them and draws nothing.
// (A disc without it draws every frame: then "settled" means a standing
// frame drawn.)
const IDLE = syms.live_idle;
let idles = 0, idlesOk = 0, idlesAtEnd = 0; // (idlesAtEnd: idles when the last frame was handed over)
// An idle loop since the last frame was handed over, with no pass's frames
// left to show (an_on, with the logic): one while they show only finds the
// camera standing for a field, and the loop that ends them may draw.
let idleSeen = false;
const AN_ON = syms.an_on;
const JSR = 0x20;
const s16 = (v) => (v & 0x8000 ? v - 0x10000 : v);
const camera = () => {
    const b = ram.subarray(LV_CAM, LV_CAM + 9);
    return [b[0] | (b[1] << 8), b[2] | (b[3] << 8), b[4] | (b[5] << 8), b[6], b[7], b[8]];
};
// what the frame's objects_frame was given besides the camera (the logic's
// disc): set below
let frameExtra = () => ({});
// A frame's inputs, all that its view is made from, as live_loop compares
// them (docs/research/live.md, "The idle loop"): the area and how many times one has been entered,
// the camera, and with the logic what's hidden of each object it indexes
// (ix_flags AND IX_HIDDEN, all IX_MAX) and the crosshair.
const LV_ENTERED = syms.lv_entered;
const genNow = () => (LV_ENTERED === undefined ? 0 : ram[LV_ENTERED]);
const IX_FLAGS = FREE ? 0 : sym("ix_flags"), IX_MAX = FREE ? 0 : sym("IX_MAX");
const CROSS_ON = FREE ? 0 : sym("CrossOn"), CROSS_X = FREE ? 0 : sym("CrossX"), CROSS_Y = FREE ? 0 : sym("CrossY");
const hiddenOf = (flags) => flags.map((v) => v & 0x60).join(",");
const inputsOf = (f) => `area ${f.area} (entered ${f.gen}), camera ${f.camera}` +
    (FREE ? "" : `, hidden ${f.hiddenAll}, crosshair ${f.cross ?? "off"}`);
function inputsNow() {
    const f = { area: ram[LV_AREA], gen: genNow(), camera: camera() };
    if (!FREE) {
        f.hiddenAll = hiddenOf([...ram.subarray(IX_FLAGS, IX_FLAGS + IX_MAX)]);
        f.cross = ram[CROSS_ON] ? [ram[CROSS_X], ram[CROSS_Y]] : null;
    }
    return inputsOf(f);
}
// Every idle loop must find the inputs of the frame last handed over: so
// the view shown (or about to be) is the one they make.
const idleLoops = []; // cycles from live_loop to live_idle, each loop that drew nothing
function onIdle() {
    idles++;
    if (current) idleLoops.push(now() - current.tLoop);
    if (AN_ON === undefined || !ram[AN_ON]) idleSeen = true;
    const last = frames.at(-1);
    if (!last) return; // (before the hooks' first frame)
    const inputs = inputsNow();
    if (inputs !== last.inputs) fail(`an idle loop after frame ${last.n} (${script}) with ${inputs}, not the frame's ${last.inputs}`);
    else idlesOk++;
}
let events = 0; // passes taken and requests made: what a standing frame comes after
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

// --profile-rest's routines: each sideways section's labels keyed by its bank
// (ANDY's as bank 16), so the banks' shared addresses are told apart
const restRoutines = [];
const restKey = (bank, addr) => (addr >= 0x8000 && addr < 0xc000 ? (bank < 0 ? 16 : bank) + 1 : 0) * 0x10000 + addr;
if (profileRest) {
    const bankOf = {
        Logic: sym("BANK_DB"), LiveGlue: sym("BANK_GLUE"), LogicCode: sym("BANK_DATA"), LiveData: sym("BANK_DATA"),
        PanelData: sym("BANK_DATA"), AreaConv: sym("BANK_DATA"), ObjCode: sym("BANK_OBJ"), ObjAndy: -1,
        RasterRuns: sym("BANK_RASTER"), RasterCode: sym("BANK_RASTER"), RasterWork: sym("BANK_RASTER"),
    };
    const all = JSON.parse(fs.readFileSync(disc.replace(/\.ssd$/, ".json"), "utf8"));
    for (const a of all.assemblies)
        for (const s of a.sections)
            for (const [k, v] of Object.entries(s.labels ?? {}))
                if (!k.includes("@") && (fineRest || !k.includes(".")))
                    restRoutines.push([restKey(bankOf[s.name] ?? 0, v.value), k]);
    restRoutines.sort((a, b) => a[0] - b[0]);
}
const restRoutineOf = (key) => {
    let lo = 0, hi = restRoutines.length - 1;
    if (hi < 0 || key < restRoutines[0][0]) return "?";
    while (lo < hi) {
        const mid = (lo + hi + 1) >> 1;
        if (restRoutines[mid][0] <= key) lo = mid;
        else hi = mid - 1;
    }
    return restRoutines[lo][1];
};
let restAcc = new Map(), restInHalf = false, restLastKey = -1, restLastT = 0;

cpu.debugInstruction.add((addr, opcode) => {
    // the bank paged at a hooked address, unless ANDY (ROMSEL's bit 7, over
    // a bank's first 4K) is there instead: none then
    const bank = cpu.isBankPagedAt(cpu.romsel & 15, addr) ? cpu.romsel & 15 : -1;
    if (profileRest) {
        const t = now();
        if (restLastKey >= 0 && !restInHalf) {
            const r = restRoutineOf(restLastKey);
            restAcc.set(r, (restAcc.get(r) || 0) + (t - restLastT));
        }
        restLastKey = restKey(bank, addr);
        restLastT = t;
        if (addr === OBJECTS && bank === BANK_OBJ) restInHalf = true;
        else if (addr === FRONT_DONE || addr === FILL_DONE) restInHalf = false;
        else if (addr === RASTER && bank === BANK_RASTER) restInHalf = true;
        // (a loop that drew nothing: the next frame's loop starts at its own)
        else if (addr === LIVE_LOOP && current && current.tFront === undefined) restAcc = new Map();
        else if (addr === FB_END && current && current.fill !== undefined) {
            current.restProf = restAcc;
            restAcc = new Map();
        }
    }
    if (opcode === JSR && word(addr + 1) === FB_BEGIN) calling = true;
    if (addr === LIVE_LOOP) {
        // (a loop that drew nothing leaves its frame unbegun)
        if (current && current.tFront !== undefined && !current.ended) fail("live_loop again before frame_end");
        current = { tLoop: now() };
        onLoop();
    } else if (!FREE && addr === LIVE_PASSED) {
        onPassed(cpu.a);
    } else if (!FREE && addr === LV_TAKING) {
        lastTaking = now();
    } else if (addr === PANEL_WAITING && bank === BANK_DATA) {
        panelWaits++;
    } else if (addr === PANEL_VALUES && bank === BANK_DATA) {
        valuesFrom = now();
    } else if (addr === PANEL_VALUED && bank === BANK_DATA) {
        if (valuesFrom !== null) valuesCycles.push(now() - valuesFrom);
        valuesFrom = null;
        onValued();
    } else if (addr === PANEL_DRAW && bank === BANK_DATA) {
        drawFrom = { t: now(), tile: cpu.x >= PANEL_GLYPHS, line: beamLine(), field: word(FIELDS_AT) };
    } else if (addr === PANEL_DRAWN && bank === BANK_DATA && drawFrom) {
        (drawFrom.tile ? tileCycles : glyphCycles).push(now() - drawFrom.t);
        // each cell drawn wholly in the beam's window: begun and done in one
        // field, before the flip's line, so neither a flip nor the beam
        // finds it half drawn
        const line = beamLine();
        const later = drawFrom.field !== word(FIELDS_AT);
        if (later || drawFrom.line >= FLIP_LINE_ || line >= FLIP_LINE_)
            fail(`a cell of the panel drawn from line ${drawFrom.line} to ${line}${later ? " of a later field" : ""}, not inside the window before line ${FLIP_LINE_}`);
        else cellsInWindow++;
        drawFrom = null;
    } else if (addr === IDLE) {
        onIdle();
    } else if (addr === CLOCK_READ) {
        lastClock = now(); // (the last of its tries is the one kept)
    } else if (addr === OBJECTS && bank === BANK_OBJ && current) {
        current.tFront = now();
        current.clockFront = lastClock;
        current.camera = camera();
        current.area = ram[LV_AREA];
        current.script = script;
        current.gen = genNow();
        current.ev = events;
        current.afterIdle = idles > idlesAtEnd;
        Object.assign(current, frameExtra());
        if (!FREE) current.hiddenAll = hiddenOf(current.ixFlags);
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
        current.inputs = inputsOf(current);
        // nothing is drawn again that's drawn already (the idle loop)
        if (IDLE && frames.length && frames.at(-1).inputs === current.inputs) {
            redrawn++;
            fail(`frame ${current.n} (${script}) drawn with the inputs of frame ${frames.at(-1).n}: ${current.inputs}`);
        }
        idleSeen = false;
        idlesAtEnd = idles;
        // (after loops that drew nothing, from its own loop's start)
        if (current.afterIdle) current.loop = now() - current.tLoop;
        else if (lastEndT !== null) current.loop = now() - lastEndT;
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
        checkLines(current);
        frames.push(current);
        pending.push(current);
        if (pending.length > 1) fail(`frame ${current.n} handed over before frame ${pending[0].n} was shown`);
    }
    return false;
});

// The panel (src/panel.6502, tools/model/panel.py). Its cells (panel_want,
// panel_shown) are the model's flat() order; tools/mkpanel.py --check gives
// what the model makes of them, after the run (below the scripts).
const BANK_DATA = sym("BANK_DATA");
const PANEL_WANT = sym("panel_want"), PANEL_SHOWN = sym("panel_shown"), PANEL_CELLS = sym("PANEL_CELLS");
const PANEL_AREA = sym("panel_area"), PANEL_OVER = sym("panel_over"), PANEL_VALUED = sym("panel_values.valued");
// what the panel costs: each panel_values (from its call to .valued), and
// each cell's draw (panel_draw, from its call to panel_sync's .drawn)
const PANEL_VALUES = sym("panel_values"), PANEL_DRAW = sym("panel_draw"), PANEL_DRAWN = sym("panel_sync.drawn");
const PANEL_GLYPHS = sym("PANEL_GLYPHS"), PANEL_CELL_US = sym("PANEL_CELL_US");
const valuesCycles = [], glyphCycles = [], tileCycles = [];
let valuesFrom = null, drawFrom = null, cellsInWindow = 0;
const FLIP_LINE_ = sym("FLIP_LINE"), FIELDS_AT = sym("fields");
const PF = (f) => [sym(`PF_${f}`), sym(`PN_${f}`)];
const [PF_NAME, PN_NAME] = PF("NAME"), [PF_MESSAGE, PN_MESSAGE] = PF("MESSAGE"), [PF_FPS, PN_FPS] = PF("FPS");
const panelBuild = JSON.parse(fs.readFileSync(path.join(root, "build/panel/panel.json"), "utf8"));
const charset = panelBuild.charset;
const cellsOf = (s) => [...s.toUpperCase()].map((ch) => charset.indexOf(ch));
const centred = (s, n) => {
    s = s.trim();
    const pad = n - s.length;
    return " ".repeat(pad >> 1) + s + " ".repeat(pad - (pad >> 1));
};
const panelCells = (a) => [...ram.subarray(a, a + PANEL_CELLS)];
// the free camera's message (tools/model/panel.py's entrance_message)
const entranceMessage = (id, demo) => ` ${demo ? "    DEMO" : "ENTRANCE"} ${id >= 10 ? Math.floor(id / 10) : " "}${id % 10}  `;
// Every frame handed over wants its area's name, and shows it, and its
// message: with the free camera, its entrance (and the demo); with the
// logic, what the panel's values set (checked against the model's, below).
let linesChecked = 0;
function checkLines(frame) {
    const want = panelCells(PANEL_WANT), shown = panelCells(PANEL_SHOWN);
    const name = cellsOf(centred(live.areas[frame.area].name, PN_NAME)).join();
    const range = (cells, f, n) => cells.slice(f, f + n).join();
    if (range(want, PF_NAME, PN_NAME) !== name || range(shown, PF_NAME, PN_NAME) !== name)
        fail(`frame ${frame.n} (area ${frame.area}) doesn't want and show its name: ${range(want, PF_NAME, PN_NAME)} and ${range(shown, PF_NAME, PN_NAME)}, not ${name}`);
    if (range(want, PF_MESSAGE, PN_MESSAGE) !== range(shown, PF_MESSAGE, PN_MESSAGE))
        fail(`frame ${frame.n} (area ${frame.area}) handed over without its message drawn`);
    if (FREE) {
        const e = live.entrances[frame.entrance];
        const message = cellsOf(entranceMessage(e.entrance, frame.demo)).join();
        if (range(want, PF_MESSAGE, PN_MESSAGE) !== message)
            fail(`frame ${frame.n}: the message's cells ${range(want, PF_MESSAGE, PN_MESSAGE)}, not ${message} (${e.name}${frame.demo ? ", demo" : ""})`);
        if (e.area !== frame.area) fail(`frame ${frame.n}: entrance ${e.name} in area ${frame.area}`);
    }
    linesChecked++;
}
// Each flip: the cells shown and the screen outside the view (both buffers
// alike, as flipped() checks): each different set of cells shown is
// rendered by the model after the run, and a set seen again must have the
// same screen.
const shownStates = new Map(); // cells shown, joined -> {index, screen, flip}
let panelFlips = 0;
function recordPanel(buffer, flip) {
    const cells = panelCells(PANEL_SHOWN);
    const key = cells.join();
    const screen = Uint8Array.from(ram.subarray(SCREEN + (buffer ? 0x8000 : 0), 0x8000 + (buffer ? 0x8000 : 0)));
    panelFlips++;
    const was = shownStates.get(key);
    if (!was) shownStates.set(key, { index: shownStates.size, cells, screen, flip });
    else {
        for (let i = 0; i < SCREEN_BYTES; i++)
            if (!viewMask[i] && was.screen[i] !== screen[i])
                return fail(`flip ${flip}: ${hex(SCREEN + i, 4)} isn't as at flip ${was.flip}, with the same cells shown`);
    }
}
// Each time the disc sets the panel's values (panel_values): the cells it
// wants, and what they're from: the original's variables (with the logic
// the transcription's, panelMem; with the free camera its own, which stay
// as the game starts), the area whose name shows, the game's end, and with
// the free camera its position, yaw and pitch.
const ZXV_ = sym("zxv");
const PANEL_ZX = { Score: [0x8872, 3], Energy: [0x8875, 1], Shield: [0x8878, 1], Step: [0x876a, 1], Turn: [0x876f, 1],
    Player: [0x8762, 6], Pitch: [0x876c, 2], InJet: [0x877a, 1], ExtLevel: [0x8772, 1], AreaScale: [0x8779, 1],
    AreaId: [0x8862, 1], CrossOn: [0x88a2, 1], ShootMode: [0x88ac, 1] };
const RIG_PLACED = 0x877b;
const memOf = (byte) => {
    const out = [];
    for (const [a, n] of Object.values(PANEL_ZX)) for (let i = 0; i < n; i++) out.push([a + i, byte(a + i)]);
    const rig = RIG_PLACED + ((byte(0x8862) - 1) & 0xff);
    out.push([rig, byte(rig)]);
    return out;
};
let panelMem = () => memOf((a) => ram[ZXV_ + a - sym("ZXV_ORG")]);
const valued = [];
function onValued() {
    const v = { want: panelCells(PANEL_WANT), mem: panelMem(), area: ram[PANEL_AREA], over: ram[PANEL_OVER], script };
    if (FREE) {
        const c = camera();
        v.cam = [c[0], c[1], c[2], c[3], c[4]];
    }
    valued.push(v);
}

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
    recordPanel(to, flips);
    const frame = pending.shift();
    if (!frame && !frames.length) return; // (handed over before the hooks went in)
    if (!frame) return fail(`flip ${flips} with no frame handed over`);
    if (frame.buffer !== to) return fail(`flip ${flips} to buffer ${to}, but frame ${frame.n} was drawn in ${frame.buffer}`);
    if (frame.afterIdle) frame.flip = t - frame.tLoop;
    else if (lastFlipT !== null) frame.flip = t - lastFlipT;
    lastFlipT = t;
    if (frame.unhooked) return;
    const rows = [];
    for (let y = 0; y < VIEW_H; y++) {
        const row = Buffer.alloc(VIEW_BYTES);
        for (let c = 0; c < VIEW_BYTES; c++) row[c] = bufferByte(to, viewAt(y, c));
        rows.push(row.toString("hex"));
    }
    // the first view a key pressed while settled changes
    const was = shown.at(-1);
    if (probe && !probe.closed && probe.tShown === undefined && frame.tLoop >= probe.tKey && was && rows.join() !== was.rows.join()) {
        probe.tShown = t;
        probe.frame = frame;
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
// Settled: nothing left to draw until a key comes. With the idle loop: a
// loop has found nothing new since the last frame was handed over (and,
// with the logic, the request taken, no pass's frames showing and no wait
// for the next pass). On a disc that draws every frame, the last two
// frames since the last pass or request standing.
let settledExtra = () => true;
const standing = () => {
    const [a, b] = [frames.at(-2), frames.at(-1)];
    return a && b.ev === events && a.ev === events && !b.anOn && a.area === b.area && a.camera.join() === b.camera.join();
};
// (and the panel drawn as wanted, so each pass's panel is shown before the
// next)
const panelDone = () => panelCells(PANEL_WANT).join() === panelCells(PANEL_SHOWN).join();
const settledNow = () => settledExtra() && (IDLE ? idleSeen : standing()) && panelDone();
const settle = (what) => until(settledNow, `${what}: settling`);
// Settled, every cell of the panel is drawn as wanted within PANEL_FIELDS
// fields: the loops that draw nothing find the beam's window once a field.
const PANEL_FIELDS = 8;
let panelSettled = 0;
async function panelDrawn(what) {
    for (let i = 0; !panelDone(); i++) {
        if (i >= PANEL_FIELDS) return fail(`${what}: the panel isn't drawn as wanted ${PANEL_FIELDS} fields on`);
        await session.runFor(FIELD);
    }
    panelSettled++;
}
// ... then on to a point in the field from a fixed pseudo-random sequence,
// so keys go down at any point of a field, as a player's do, the same
// points on any disc
let phase = Number(opt("seed", "12345"));
async function settleAndPress(what) {
    await settle(what);
    phase = (phase * 1103515245 + 12345) & 0x7fffffff;
    await session.runFor(phase % FIELD);
    if (!settledNow()) await settle(what);
}
// A key pressed while settled: when its pass comes, and when the first
// view it changes is shown (flipped). Each probe lasts until the next.
// A key pressed while idle is taken by a pass within KEY_FIELDS: it's
// read at the next vertical sync (a field at most), and the next loop's
// pass takes it, after the loop going round then, which may be drawing
// the panel (panel_sync, the beam's window at most) or working out the
// figures (live_figures).
const KEY_FIELDS = 2;
const probes = [];
let probe = null;
function startProbe(what) {
    probe = { what, tKey: now(), cam: camera() };
    probes.push(probe);
}
const press = async (key) => {
    session.keyDownRaw(BBC[key]);
    await session.runFor(3 * FIELD);
    session.keyUpRaw(BBC[key]);
};

// --- The logic's disc.
const LIVE_PASSED = FREE ? -1 : sym("lv_pass.live_passed");
const LV_TAKING = FREE ? -1 : sym("lv_pass.timed"); // (where a pass takes the keys)
let lastTaking = null;
const LV_XON = FREE ? 0 : sym("lv_xon"), LV_XX = FREE ? 0 : sym("lv_xx"), LV_XY = FREE ? 0 : sym("lv_xy");
let summary = "";
let pace = null; // (the logic's disc: the taps and the held keys' passes, reported below)
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
    // the panel's values are the transcription's state's (onValued)
    panelMem = () => memOf((a) => exp[a]);
    // The game's start, as the disc booted: its state now must be the
    // transcription's start; it's written back before each run.
    let diffs = compare();
    if (diffs.length) report("the disc's start", diffs);
    const work = Uint8Array.from(ram.subarray(LOGIC_WORK, LOGIC_WORK_END));
    const db = Uint8Array.from(ram.subarray(bankAt(BANK_DB, LOGIC_DB), bankAt(BANK_DB, 0xc000)));
    const startExp = Uint8Array.from(exp);

    // The keys: the ZX's names as the BBC's (src/input.6502's KEY_MAP).
    // Driller's Z, X, A and S (the turn's and the step's sizes) are on the
    // function keys, the BBC's Z and X being motion (decision 10).
    const MOVED = { Z: "F0", A: "F1", X: "F2", S: "F3" };
    const bbcKey = (k) => (/^[0-9]$/.test(k) ? BBC[`K${k}`] : BBC[MOVED[k] ?? k]);
    let held = new Set();
    function hold(keys) {
        for (const k of held) if (!keys.includes(k)) session.keyUpRaw(bbcKey(k));
        for (const k of keys) if (!held.has(k)) session.keyDownRaw(bbcKey(k));
        held = new Set(keys);
    }

    // What the live_loop hook does next: write the queued state and ask the
    // disc to take it; keep the clock's minute away, or bring it on.
    let writes = null, minuteDue = false, applied = 0;
    // the visibility probe's flags: to be written at the next loop, and as
    // they stand (the frames' expected flags, not the logic's records)
    let flagWrites = null, visibility = null;
    const LV_MINUTE = S("lv_minute"), LV_REQUEST = S("lv_request"), KEYS_MADE = S("keys_made");
    onLoop = () => {
        if (flagWrites) {
            ram.set(flagWrites, S("ix_flags"));
            visibility = flagWrites;
            flagWrites = null;
            idleSeen = false;
        }
        const f = word(S("fields"));
        const m = minuteDue ? f : f + 20000;
        ram[LV_MINUTE] = m & 0xff;
        ram[LV_MINUTE + 1] = (m >> 8) & 0xff;
        if (minuteDue) {
            // the minute and its pass's keys at once (as gone down since the
            // last pass), as this loop's pass takes the minute: the keys
            // alone may not have been read yet
            minuteDue = false;
            want.rec.keys.forEach((r, i) => (ram[KEYS_MADE + i] |= r));
        }
        if (writes) {
            writes();
            writes = null;
            ram[LV_REQUEST] = 1;
            applied++;
            events++;
            idleSeen = false;
        }
    };
    // (settled, with the logic: the request taken, no pass's frames, no
    // wait for the next pass)
    settledExtra = () => !writes && !V("lv_request") && !V("an_on") && !V("lv_switch") &&
        s16((V16("lv_until") - V16("fields")) & 0xffff) <= 0;
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
    // The pass the disc is to take next ({rec, where, steps, i: its step}),
    // and the steps whose passes it has taken. A pass's keys are held until
    // it's taken; in that instant (the hook) the next pass is asked for if
    // it's the next step with the same keys, which stay held (a held key's
    // passes follow on), and otherwise the keys go up: for keys the script
    // pressed, a tap, once nearly REPEAT_FIELDS have passed since they went
    // down (tapUntil), so the disc's pace (lv_pass) must make it one pass.
    let want = null;
    const done = new Set(), early = new Set(); // (early: pokes the hook has put in)
    let passesOk = 0, passesSeen = 0, walksOk = 0;
    const passLog = []; // each pass that ran: what its frames are to show
    let overs = 0;
    const REPEAT_FIELDS = sym("REPEAT_FIELDS");
    let tapUntil = null, taps = 0;
    // the pace: the fields counted (lv_now) at the last pass that took a key
    // gone down, and the fields from each pass to a pass after it on the
    // keys held alone: the first repeat, and those after
    let lastMade = null;
    const firstRepeats = [], repeats = [];
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
        events++;
        idleSeen = false; // (what it changes may want a frame: not settled till a loop draws nothing)
        if (!want) return fail(`a pass (answer ${a}) the script didn't ask for, at ${script}, on the keys ${[...ram.subarray(S("lv_lkeys"), S("lv_lkeys") + 8)]} (held ${[...held]})`);
        // (a probe's view is its first pass's: a second pass closes it)
        if (probe && probe.tPass !== undefined && probe.tShown === undefined) probe.closed = true;
        if (probe && probe.tPass === undefined) probe.tPass = lastTaking;
        const { rec, where } = want;
        done.add(rec);
        // The pace (decision 48): the keys held alone repeat no sooner than
        // REPEAT_FIELDS after the last pass that took a key gone down (but a
        // minute's end brings its pass whatever is held).
        const tPass = V16("lv_now"), made = V("lv_made") !== 0;
        const prev = passLog.at(-1);
        if (made) lastMade = tPass;
        else if (!rec.tick) {
            const gap = (tPass - (lastMade ?? tPass)) & 0xffff;
            if (lastMade !== null && gap < REPEAT_FIELDS) fail(`${where}: the keys held repeated ${gap} fields after a key went down, not ${REPEAT_FIELDS}`);
            if (prev && prev.run === script && rec.names.length) (prev.made ? firstRepeats : repeats).push((tPass - prev.t) & 0xffff);
        }
        // (the next pass, if it has these keys: after pokes, which go in
        // now, before the disc can take another pass, as the original
        // takes it without a pass with no key between)
        const { steps, i } = want;
        // (the same keys in any order: the scenario may name them so)
        const keySet = (r) => [...r.names].sort().join();
        const same = (r) => r?.keys && !r.tick && keySet(r) === keySet(rec);
        let j = i + 1;
        const batch = [];
        for (; steps[j] && (steps[j].poke || steps[j].fcl); j++) batch.push(...steps[j].changes, ...steps[j].then);
        if (rec.soon) {
            // the logic's input has a minute to take, so the next pass comes
            // at once, on the keys held then: the next step's, down now
            // (tools/mklive.py makes it a pass, of no keys if need be)
            want = { rec: steps[i + 1], where: `${script} ${steps[i + 1].line}`, steps, i: i + 1 };
            hold(steps[i + 1].names);
        } else if (same(steps[j])) {
            want = { rec: steps[j], where: `${script} ${steps[j].line}`, steps, i: j };
            if (batch.length) {
                early.add(steps[i + 1]);
                writes = () => {
                    for (const [a, v] of batch) exp[a] = v;
                    for (const [a] of batch) put(a, exp[a]);
                };
            }
        } else {
            // A tap: keys the script pressed are held on until nearly
            // REPEAT_FIELDS after they went down, as a player's tap lasts a
            // while, and no second pass may come of them (the script asks
            // for none: above)
            if (want.tDown !== undefined && rec.names.length) tapUntil = want.tDown + (REPEAT_FIELDS - 2) * FIELD;
            else hold([]);
            want = null;
        }
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
        passLog.push({ where, P0, P1: expCamera(), walks, loaded: rec.loaded, area0, n: passLog.length, flags0, margin: exp[0x88d0],
            run: script, t: tPass, made });
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
        logicCam: expCamera(), expFlags: visibility ? visibility.slice(0, V("ix_n")) : expFlags(), switching: V("lv_switch") !== 0,
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
        await settle(`${run.name}: the start`);
        for (let i = 0; i < run.steps.length; i++) {
            const rec = run.steps[i];
            const where = `${run.name} ${rec.line}`;
            steps++;
            if (rec.frames) {
                await settle(where);
            } else if (rec.poke || rec.fcl) {
                // the results of this step and those straight after it (a
                // poke's bytes, an FCL script's changes, and what the
                // renderer does after) into the disc's state, which it takes
                // as it is (the expected state changes as the disc's does,
                // at the live_loop that writes it)
                const batch = [];
                let j = i;
                for (; j < run.steps.length && (run.steps[j].poke || run.steps[j].fcl); j++)
                    batch.push(...run.steps[j].changes, ...run.steps[j].then);
                steps += j - i - 1;
                i = j - 1;
                if (early.has(rec)) {
                    // (put in by the hook, with the keys held for the pass after)
                    await until(() => !writes, where);
                    continue;
                }
                hold([]);
                writes = () => {
                    for (const [a, v] of batch) exp[a] = v;
                    for (const [a] of batch) put(a, exp[a]);
                };
                await settle(where);
            } else if (!done.has(rec)) {
                // keys going down (not held on from the last pass's, which
                // the hook asks for): pressed once the disc has settled, and
                // timed but with a minute, whose keys come with it (onLoop)
                if (want?.rec !== rec) {
                    hold([]);
                    await settleAndPress(where);
                    if (!rec.tick) startProbe(rec.names.join("+"));
                    want = { rec, where, steps: run.steps, i, tDown: now() };
                    minuteDue = rec.tick;
                    hold(rec.names);
                }
                await until(() => done.has(rec), `${where}: the pass`);
                if (tapUntil !== null) {
                    // (the tap held on: onPassed)
                    await until(() => now() >= tapUntil, `${where}: the tap`);
                    hold([]);
                    tapUntil = null;
                    taps++;
                    // (a field, so the vertical sync reads them up before a
                    // key goes down again: the disc may be settled already,
                    // and a key let go and pressed again inside a field is a
                    // key held)
                    await session.runFor(FIELD);
                }
            }
        }
        hold([]);
        // the last pass's frames shown, and the state as the transcription's,
        // as the original's is while it waits in its input for a key
        await settle(`${run.name}: the end`);
        if (waited) waiting();
        const d = compare();
        if (d.length) report(`${run.name}: the end`, d);
        await panelDrawn(`${run.name}: the end`);
        if (failures === before) runsOk++;
    }

    // What's shown alone, with the camera still: every object the index has
    // hidden (ix_flags, written between loops, as logic_go_shown writes it
    // after a pass), then shown again as it was. Each must bring a frame
    // (lv_inputs compares the flags), and each frame is held to the model's
    // render with those flags. (The FCL's own VIS and INVIS reach the disc
    // by a request, which enters the area again, and so draws a frame
    // whatever the flags.)
    script = "visibility";
    await settle("visibility");
    const IXF = S("ix_flags");
    const shownFlags = [...ram.subarray(IXF, IXF + IX_MAX)];
    for (const want of [shownFlags.map((v, i) => (i < V("ix_n") ? v | 0x40 : v)), shownFlags]) {
        const n0 = frames.length;
        flagWrites = want;
        await until(() => !flagWrites, "visibility");
        await settle("visibility");
        if (frames.length === n0) fail("the objects' flags changed, with the camera still, and no frame came");
        else visibilityFrames += frames.length - n0;
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
    const turnBy = (t, f) => Math.sign(t) * ((Math.abs(t) * f + 255) >> 8);
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
        `${flagsOk} with the logic's objects' flags; ${visibilityFrames} frames from the objects' flags alone`;
    // The held keys' speed in tests/logic/pace.txt's run (at the port's
    // start sizes): over each pass on the keys held alone with another after
    // it, its turn or its walk (one, not both) over the fields to that one.
    const speed = { turn: [0, 0], walk: [0, 0] };
    for (let k = 0; k + 1 < passLog.length; k++) {
        const [p, q] = [passLog[k], passLog[k + 1]];
        if (p.run !== "pace" || q.run !== "pace" || p.made || q.made) continue;
        const turn = Math.abs(turnOf(p.P1[3], p.P0[3]));
        const walk = Math.hypot(...[0, 1, 2].map((a) => s16((p.P1[a] - p.P0[a]) & 0xffff)));
        const kind = turn && !walk ? "turn" : walk && !turn ? "walk" : null;
        if (!kind) continue;
        speed[kind][0] += kind === "turn" ? 5 * turn : walk;
        speed[kind][1] += (q.t - p.t) & 0xffff;
    }
    pace = { taps, firstRepeats, repeats, speed };
}

async function freeScript() {
    const LV_ENTRANCE = sym("lv_entrance"), LV_DEMO = sym("lv_demo");
    frameExtra = () => ({ entrance: ram[LV_ENTRANCE], demo: ram[LV_DEMO] !== 0 });
    // The tour: SPACE from each entrance to the next, round to the first.
    script = "still";
    await untilFrame((f) => f.entrance === 0, "the first entrance");
    let spaceOk = 0;
    for (let i = 0; i < ENTRANCES; i++) {
        await settle(`the tour at ${live.entrances[i].name}`);
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
        await settle(`at ${live.entrances[at].name}`);
        for (const hold of HOLDS) {
            script = "walk";
            await settleAndPress(`before ${hold.keys}`);
            const first = frames.length;
            startProbe(hold.keys.join("+"));
            for (const k of hold.keys) session.keyDownRaw(BBC[k]);
            await framesMade(hold.frames, `holding ${hold.keys}`);
            for (const k of hold.keys) session.keyUpRaw(BBC[k]);
            script = "still";
            await settle(`after ${hold.keys}`);
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

    // The panel's values the free camera's play never changes, its
    // variables staying as the game starts: the jet's picture and a score
    // of seven digits, then back. Each set by a step and drawn whole
    // (settled), so the model renders it.
    script = "panel";
    const zxPoke = (a, v) => (ram[ZXV_ + a - sym("ZXV_ORG")] = v);
    const zxStart = [0x877a, 0x8872, 0x8873, 0x8874].map((a) => [a, ram[ZXV_ + a - sym("ZXV_ORG")]]);
    for (const set of [[[0x877a, 1], [0x8872, 0x87], [0x8873, 0xd6], [0x8874, 0x12]], zxStart]) {
        await settle("the panel's values");
        for (const [a, v] of set) zxPoke(a, v);
        session.keyDownRaw(BBC.UP);
        await framesMade(1, "the panel's values");
        session.keyUpRaw(BBC.UP);
        await settle("the panel's values");
        await panelDrawn("the panel's values");
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
    await settle("after the demo");
    if (frames.at(-1).demo) fail("a key didn't stop the demo");
    await panelDrawn("after the demo");
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

// --- The panel against the model (tools/mkpanel.py --check): every set of
// cells a flip showed, rendered, is what the screen held outside the view
// (the picture, and the cells' bytes); every time the disc set the
// panel's values, the cells it wanted are the model's for the original's
// variables then (the transcription's, with the logic), but the frames a
// second (the disc's own measure) and with the free camera the message
// (checkLines holds it to the entrance).
const states = [...shownStates.values()];
const pyPanel = spawnSync(path.join(root, ".venv/bin/python"), ["-I", path.join(root, "tools/mkpanel.py"), "--check"], {
    input: JSON.stringify({ shown: states.map((s) => s.cells), valued }),
    env: { ...process.env, FREESCAPE_DISPLAY: live.display },
    maxBuffer: 1 << 30,
});
if (pyPanel.status !== 0) throw new Error(`the panel's model failed: ${pyPanel.stderr}`);
const panelModel = JSON.parse(pyPanel.stdout);
const picture = Buffer.from(panelModel.picture, "hex");
const cellOffset = new Map(panelModel.offsets.map((o, k) => [o, k]));
let statesOk = 0, valuedOk = 0;
const fieldOf = (i) => {
    for (let f = 0, at = 0; f < panelModel.fields.length; at += panelModel.fields[f][1], f++)
        if (i < at + panelModel.fields[f][1]) return `${panelModel.fields[f][0]} ${i - at}`;
    return `cell ${i}`;
};
for (const s of states) {
    const cells = Buffer.from(panelModel.shown[s.index], "hex");
    let bad = null;
    for (let i = 0; i < SCREEN_BYTES && !bad; i++) {
        if (viewMask[i]) continue;
        const k = cellOffset.get(i);
        const want = k === undefined ? picture[i] : cells[k];
        if (s.screen[i] !== want) bad = `${hex(SCREEN + i, 4)} is &${s.screen[i].toString(16)}, the model's &${want.toString(16)}`;
    }
    if (bad) fail(`flip ${s.flip}: the panel ${bad}`);
    else statesOk++;
}
const skipped = new Set();
for (let i = PF_FPS; i < PF_FPS + PN_FPS; i++) skipped.add(i);
if (FREE) for (let i = PF_MESSAGE; i < PF_MESSAGE + PN_MESSAGE; i++) skipped.add(i);
valued.forEach((v, n) => {
    const want = panelModel.valued[n];
    const i = v.want.findIndex((g, i) => !skipped.has(i) && g !== want[i]);
    if (i >= 0) fail(`the panel's values ${n} (${v.script}): ${fieldOf(i)} wants ${v.want[i]}, the model's ${want[i]} ` +
        `(the cells ${v.want.join(",")}; the model's ${want.join(",")}; from ${JSON.stringify(v.mem)})`);
    else valuedOk++;
});
// Each cell's draw must fit the beam's window it was begun in: PANEL_CELL_US.
const drawMost = Math.max(0, ...glyphCycles, ...tileCycles);
if (drawMost > 2 * PANEL_CELL_US) fail(`a cell took ${drawMost} cycles to draw, past PANEL_CELL_US (${PANEL_CELL_US} us)`);
const cyc = (xs) => {
    const s = [...xs].sort((a, b) => a - b);
    return s.length ? `${s[s.length >> 1]} / ${s[Math.min(s.length - 1, Math.ceil(0.9 * s.length) - 1)]} / ${s.at(-1)}` : "-";
};
console.log(`${NAME}: the panel: ${panelFlips} flips showed ${states.length} sets of cells, ${statesOk} the model's ` +
    `outside the view; its values set ${valued.length} times, ${valuedOk} as the model's; drawn as wanted when settled ` +
    `${panelSettled} times; ${linesChecked} frames with their area's name and message; ${panelWaits} waits for the beam`);
console.log(`${NAME}: the panel's cycles (median / p90 / most): panel_values ${cyc(valuesCycles)} (${valuesCycles.length}); ` +
    `a glyph cell drawn ${cyc(glyphCycles)} (${glyphCycles.length}), a tile ${cyc(tileCycles)} (${tileCycles.length}); ` +
    `${cellsInWindow} cells drawn inside the beam's window`);

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
// (the most by a fold: a long run's idle loops are more than a call's
// arguments can be)
const most = (xs) => xs.reduce((a, b) => Math.max(a, b), -Infinity);
const stats = (xs) => (xs.length ? `${two(median(xs))} / ${two(pct(xs, 90))} / ${two(most(xs))}` : "-");
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
    `${compared - wrong} the model's view byte for byte (${requests.length} views); ` +
    `${viewWrites} writes to the view and ${textWrites} outside it, each where it may be; ` +
    `the BBC's own timing within ${CLOCK_SLACK} cycles ${clockChecked} times`);
if (pace) {
    const rate = ([d, f], unit) => (f ? `${((2e6 / FIELD_CYCLES) * d / f).toFixed(1)} ${unit} a second over ${f} fields` : "-");
    console.log(`${NAME}: the pace: ${pace.taps} taps held ${sym("REPEAT_FIELDS") - 2} fields, each one pass; ` +
        `the keys held alone repeat ${stats(pace.firstRepeats)} fields after their pass (${pace.firstRepeats.length}), ` +
        `then a pass every ${stats(pace.repeats)} fields (${pace.repeats.length}) (median / p90 / max); ` +
        `held in pace's run, turning ${rate(pace.speed.turn, "degrees")}, walking ${rate(pace.speed.walk, "units")}`);
}
// --- The keys pressed while settled: each one's pass (within KEY_FIELDS,
// with the idle loop) and the first view it changed, by what changed.
const kinds = { walking: [], turning: [], other: [] };
let unchanged = 0;
const passWaits = [];
for (const p of probes) {
    if (p.tPass !== undefined) {
        passWaits.push(fields(p.tPass - p.tKey));
        if (IDLE && p.tPass - p.tKey > KEY_FIELDS * FIELD_CYCLES)
            fail(`${p.what}, pressed while idle: its pass ${fields(p.tPass - p.tKey).toFixed(2)} fields after, not within ${KEY_FIELDS}`);
    }
    if (p.tShown === undefined) {
        unchanged++;
        continue;
    }
    const c = p.frame.camera;
    const kind = c.slice(0, 3).join() !== p.cam.slice(0, 3).join() ? "walking" : c.slice(3).join() !== p.cam.slice(3).join() ? "turning" : "other";
    kinds[kind].push(fields(p.tShown - p.tKey));
}
console.log(`${NAME}: ${probes.length} keys pressed with nothing left to draw: ` +
    (FREE ? "" : `the pass after ${stats(passWaits)} fields (median / p90 / max); `) +
    `the first view they changed shown after ` +
    Object.entries(kinds).map(([k, v]) => `${k} ${stats(v)} (${v.length})`).join(", ") +
    ` fields; ${unchanged} changed nothing shown`);
if (IDLE) console.log(`${NAME}: ${idles} idle loops, ${idlesOk} with the last frame's inputs, each ` +
    `${stats(idleLoops)} cycles from live_loop to live_idle; ${redrawn} frames drawn with the last frame's inputs`);
console.log(`${NAME}: fields a frame, median / p90 / max:`);
console.log(`  ${"frames".padEnd(10)} ${"n".padStart(4)}  ${"flip to flip".padEnd(20)} ${"loop".padEnd(20)} ` +
    `${"1-7 objects".padEnd(20)} ${"8-10 fill".padEnd(20)} ${"the rest".padEnd(20)}`);
row("all", counted);
for (const k of ["entrance", "standing", "walking", "turning", ...(FREE ? ["demo"] : [])]) row(k, counted.filter((f) => f.kind === k));
if (profileRest)
    for (const k of ["entrance", "standing", "walking", "turning"]) {
        const fs_ = counted.filter((f) => f.kind === k && f.restProf);
        if (!fs_.length) continue;
        const sum = new Map();
        for (const f of fs_) for (const [r, c] of f.restProf) sum.set(r, (sum.get(r) || 0) + c);
        const total = [...sum.values()].reduce((a, b) => a + b, 0);
        console.log(`${NAME}: the rest by routine, ${k} (${fs_.length} frames, ${Math.round(total / fs_.length)} cycles a frame):`);
        for (const [r, c] of [...sum.entries()].sort((a, b) => b[1] - a[1]).slice(0, Number(opt("top", 25))))
            console.log(`  ${r.padEnd(28)} ${String(Math.round(c / fs_.length)).padStart(8)} ${(100 * c / total).toFixed(1).padStart(5)}%`);
    }
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
        // the keys pressed while settled: cycles to their pass and to the
        // first view they changed shown (null: none)
        keys: probes.map((p) => ({
            keys: p.what, pass: p.tPass === undefined ? null : p.tPass - p.tKey,
            shown: p.tShown === undefined ? null : p.tShown - p.tKey,
        })),
        idle_loops: idleLoops,
    }, null, 1) + "\n");
console.log(failures ? `${NAME}: ${failures} failure(s)` : `${NAME}: ok`);
process.exit(failures ? 1 : 0);
