#!/usr/bin/env node
// The frame loop on jsbeeb's full video (the CRTC and the video ULA as the
// disc programs them), headless: the screen it sets up, every flip, every
// screen write, the frames' pace, and the keyboard's bitmap.
//
//   node tools/frames.mjs [--disc build/freescape.ssd] [--load] [--secs 10] [--seed 1]
//
// It boots the disc (or with --load puts FS where *RUN would and runs it
// from start) and runs to main_loop. It fails (exit status 1) unless:
//
// - the CRTC's registers are MODE 2's as the MOS sets them (jsbeeb's own,
//   MODE 2 typed at BASIC), but for R1 = SCREEN_COLS and R6 = SCREEN_ROWS
//   from SCREEN, the syncs moved to keep MODE 2's centre, interlace off and
//   no cursor; the ULA's control register is MODE 2's; and on jsbeeb's
//   picture the screen's centre is MODE 2's;
// - the palette has logical colour n physical colour n AND 7, none
//   flashing, and the picture holds only those eight colours;
// - the view's border is where src/defs.6502 puts it, on the picture and
//   in both buffers;
// - both buffers hold the same at main_loop: 0 but the test scene's edge;
// - every write to the screen comes between frame_begin and frame_end, to
//   the buffer not shown;
// - every flip comes while the CRTC is past its last row shown, and shows
//   the buffer of the one frame handed over since the last flip, whose
//   view holds the test scene's frame for that frame byte for byte, and
//   whose bytes outside the view are as they were at main_loop;
// - every vertical sync is counted (fields) and every flip (frames);
// - each of Driller's keys (src/input.6502) sets its bit and no other,
//   alone and with another held.
//
// It reports the test scene's pace as it is (its whole view a frame):
// frames a second and fields a frame from the counters, and the cycles a
// frame spends drawing and waiting. Then it runs the scene with its cost
// varied at random each frame (scene_rows, scene_delay), so frames end all
// over the field, and reports the fields a frame there too.
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
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const flag = (name) => {
    const i = args.indexOf(`--${name}`);
    if (i >= 0) args.splice(i, 1);
    return i >= 0;
};
const disc = opt("disc", "build/freescape.ssd");
const secs = Number(opt("secs", "10"));
let seed = Number(opt("seed", "1")) >>> 0 || 1;
const load = flag("load");

const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const sym = (name) => {
    if (!(name in syms)) throw new Error(`no symbol ${name}`);
    return syms[name];
};

let failures = 0;
const fail = (what) => {
    if (++failures <= 30) console.log(`frames: FAIL ${what}`);
};
// Anything thrown (a run that never reaches its label) is a failure too.
process.on("uncaughtException", (e) => {
    console.log(`frames: FAIL ${e.message}`);
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

async function runTo(session, name, secs) {
    try {
        await session.runUntilAddress(sym(name), secs);
    } catch {
        throw new Error(`didn't reach ${name} in ${secs}s of emulated time`);
    }
}

async function machine() {
    const session = new MachineSession("Master");
    await quietly(() => session.initialise());
    return session;
}

// The files on a DFS disc, by name.
function ssdFiles(file) {
    const ssd = fs.readFileSync(file);
    const files = {};
    for (let i = 0; i < ssd[0x105] / 8; i++) {
        const name = ssd.subarray(8 + i * 8, 15 + i * 8).toString("latin1").trim();
        const o = 0x108 + i * 8;
        const len = ssd[o + 4] | (ssd[o + 5] << 8) | (((ssd[o + 6] >> 4) & 3) << 16);
        const sector = ssd[o + 7] | ((ssd[o + 6] & 3) << 8);
        files[name] = ssd.subarray(sector * 256, sector * 256 + len);
    }
    return files;
}

// --- The picture: jsbeeb's framebuffer, 1024 x 625, RGBA ------------------
const FB_W = 1024;
const FB_H = 625;
// A pixel's physical colour (bit 0 red, 1 green, 2 blue), or -1 if it isn't
// one of the BBC's eight.
const physical = (fb, x, y) => {
    const o = (y * FB_W + x) * 4;
    let c = 0;
    for (let k = 0; k < 3; k++) {
        const v = fb[o + k];
        if (v === 255) c |= 1 << k;
        else if (v !== 0) return -1;
    }
    return c;
};
// The box (x0, y0, x1, y1, exclusive) of the pixels whose colour passes.
function box(fb, pass) {
    let x0 = FB_W, y0 = FB_H, x1 = -1, y1 = -1;
    for (let y = 0; y < FB_H; y++)
        for (let x = 0; x < FB_W; x++)
            if (pass(physical(fb, x, y))) {
                x0 = Math.min(x0, x);
                y0 = Math.min(y0, y);
                x1 = Math.max(x1, x + 1);
                y1 = Math.max(y1, y + 1);
            }
    return x1 < 0 ? null : { x0, y0, x1, y1 };
}
const showBox = (b) => (b ? `(${b.x0},${b.y0})-(${b.x1},${b.y1})` : "none");

// --- MODE 2 as the MOS sets it, for reference ------------------------------
// With *TV 0,1: no vertical shift (the CMOS's own may have one) and no
// interlace, which is where the disc puts its screen whatever the CMOS says.
async function mode2() {
    const session = await machine();
    await quietly(() => session.boot());
    await quietly(() => session.type("*TV 0,1"));
    await quietly(() => session.type("MODE 2"));
    await quietly(() => session.type("COLOUR 135:CLS")); // the whole screen white
    await quietly(() => session.runUntilPrompt());
    await session.runFrames(2);
    const v = session._video;
    return {
        regs: Array.from(v.regs.slice(0, 16)),
        ulactrl: v.ulactrl,
        screen: box(session._completeFb8, (c) => c === 7),
    };
}

// --- The test scene, as src/main.6502 draws it -----------------------------
const SCREEN = sym("SCREEN");
const SCREEN_ROW = sym("SCREEN_ROW");
const SCREEN_COLS = sym("SCREEN_COLS");
const SCREEN_ROWS = sym("SCREEN_ROWS");
const SCREEN_BYTES = 0x8000 - SCREEN;
const VIEW_ADDR = sym("VIEW_ADDR");
const VIEW_BYTES = sym("VIEW_BYTES");
const VIEW_H = sym("VIEW_H");
const VIEW_W = sym("VIEW_W");
const VIEW_ROWS = VIEW_H / 8;
const left = (c) => ((c & 8) << 4) | ((c & 4) << 3) | ((c & 2) << 2) | ((c & 1) << 1);
const right = (c) => left(c) >> 1;
const at = (y, col) => SCREEN + (y >> 3) * SCREEN_ROW + col * 8 + (y & 7); // a screen line's byte
const viewAt = (y, col) => VIEW_ADDR + (y >> 3) * SCREEN_ROW + col * 8 + (y & 7);

// The buffer at main_loop: 0, with the screen's edge in SCENE_EDGE.
function staticScreen() {
    const edge = sym("SCENE_EDGE");
    const b = new Uint8Array(SCREEN_BYTES);
    for (let col = 0; col < SCREEN_COLS; col++) {
        b[at(0, col) - SCREEN] = left(edge) | right(edge);
        b[at(SCREEN_ROWS * 8 - 1, col) - SCREEN] = left(edge) | right(edge);
    }
    for (let y = 0; y < SCREEN_ROWS * 8; y++) {
        b[at(y, 0) - SCREEN] |= left(edge);
        b[at(y, SCREEN_COLS - 1) - SCREEN] |= right(edge);
    }
    return b;
}
// A frame's view line: the bars at phase p, and the border's sides.
function sceneLine(p) {
    const bar = sym("SCENE_BAR");
    const cycle = sym("SCENE_CYCLE");
    const border = sym("SCENE_BORDER");
    const colour = (x) => (x === 0 || x === VIEW_W - 1 ? border : Math.floor((((x - p) % cycle) + cycle) % cycle / bar));
    return Array.from({ length: VIEW_BYTES }, (_, c) => left(colour(2 * c)) | right(colour(2 * c + 1)));
}
// Is (y, col) of the view drawn by a frame of `rows` character rows, and
// what with?
function sceneByte(line, rows, y, col) {
    const border = sym("SCENE_BORDER");
    if (y >> 3 >= rows) return null;
    if (y === 0 || (y === VIEW_H - 1 && rows === VIEW_ROWS)) return left(border) | right(border);
    return line[col];
}
const inView = (a) => {
    const off = a - VIEW_ADDR;
    if (off < 0) return false;
    const row = Math.floor(off / SCREEN_ROW), within = off % SCREEN_ROW;
    return row < VIEW_ROWS && within < VIEW_BYTES * 8;
};

// --- The run -----------------------------------------------------------------
const reference = await mode2();
const session = await machine();
const tm = session._machine;
const cpu = tm.processor;
const ram = cpu.ramRomOs;
const video = session._video;
const now = () => tm.elapsedCycles;
// A buffer's byte: main RAM's, or shadow RAM's (jsbeeb keeps it 32K on).
const bufferByte = (buffer, a) => ram[a + (buffer ? 0x8000 : 0)];
const word = (a) => ram[a] | (ram[a + 1] << 8);

if (load) {
    await quietly(() => session.boot());
    ram.set(ssdFiles(disc).FS, 0x0e00);
    cpu.pc = sym("start");
} else {
    session.loadDisc(path.resolve(disc));
    await quietly(() => session.autoboot());
}
await runTo(session, "main_loop", 60);

// The registers.
const r = Array.from(video.regs.slice(0, 16));
const m = reference.regs;
for (const i of [0, 3, 4, 5, 9])
    if (r[i] !== m[i]) fail(`CRTC R${i} ${r[i]}, not MODE 2's ${m[i]}`);
if (r[1] !== SCREEN_COLS) fail(`CRTC R1 ${r[1]}, not SCREEN_COLS's ${SCREEN_COLS}`);
if (r[6] !== SCREEN_ROWS) fail(`CRTC R6 ${r[6]}, not SCREEN_ROWS's ${SCREEN_ROWS}`);
if (2 * r[2] - r[1] !== 2 * m[2] - m[1]) fail(`CRTC R2 ${r[2]} doesn't keep MODE 2's centre across (R2 ${m[2]} for R1 ${m[1]})`);
if (2 * r[7] - r[6] !== 2 * m[7] - m[6]) fail(`CRTC R7 ${r[7]} doesn't keep MODE 2's centre down (R7 ${m[7]} for R6 ${m[6]})`);
if (r[8] !== 0) fail(`CRTC R8 ${hex(r[8])}: interlaced, or delayed`);
if ((r[10] & 0x60) !== 0x20) fail(`CRTC R10 ${hex(r[10])}: a cursor`);
if (((r[12] << 8) | r[13]) * 8 !== SCREEN) fail(`CRTC R12/R13 ${hex(r[12])}/${hex(r[13])}, not SCREEN's`);
// (bit 0 picks which of a flashing colour's two is shown, which the MOS
// turns over as they flash: no colour of the disc's flashes)
if ((video.ulactrl ^ reference.ulactrl) & 0xfe)
    fail(`ULA control ${hex(video.ulactrl)}, not MODE 2's ${hex(reference.ulactrl & 0xfe)}`);
for (let n = 0; n < 16; n++)
    if (video.actualPal[n] !== ((n & 7) ^ 7)) fail(`palette entry ${n} ${hex(video.actualPal[n], 1)}, not physical ${n & 7} steady`);
console.log(
    `frames: CRTC R0-R13 ${r.slice(0, 14).join(" ")} (MODE 2's ${m.slice(0, 14).join(" ")}), ` +
        `ULA ${hex(video.ulactrl)}`,
);

// Both buffers at main_loop.
const initial = staticScreen();
for (const buffer of [0, 1]) {
    let bad = 0;
    for (let i = 0; i < SCREEN_BYTES; i++)
        if (bufferByte(buffer, SCREEN + i) !== initial[i] && bad++ < 3)
            fail(`${buffer ? "shadow" : "main"} RAM's buffer at main_loop: ${hex(SCREEN + i, 4)} is ` +
                `${hex(bufferByte(buffer, SCREEN + i))}, not ${hex(initial[i])}`);
}
if (cpu.acccon & 7) fail(`ACCCON ${hex(cpu.acccon)} at main_loop: D, E or X set`);

// The hooks. Frames handed over and not yet shown, and the state between
// frame_begin and frame_end.
const pending = [];
let checking = true;
let inFrame = false;
let flips = 0, writes = 0, syncs = 0;
let lastFlipField = null;
const fieldsShown = new Map(); // fields a frame was shown for -> how many frames
let minMargin = Infinity; // the fewest lines between a flip and the next line shown
let tBegin = 0, tShown = 0, drawCycles = 0, waitCycles = 0, drawn = 0;
let vary = false;
const rand = () => {
    seed ^= seed << 13;
    seed ^= seed >>> 17;
    seed ^= seed << 5;
    return (seed >>> 0) / 2 ** 32;
};

const FB_END = sym("frame_end"), FB_BEGIN = sym("frame_begin"), FB_SHOWN = sym("frame_begin.shown");
const PREPARE = sym("scene_prepare");
// (frame_begin's wait loops back to its first instruction, so a call is
// a JSR to it, whatever interrupt comes before its first instruction)
const JSR = 0x20;
let calling = false;
cpu.debugInstruction.add((addr, opcode) => {
    if (!checking) return false;
    if (opcode === JSR && word(addr + 1) === FB_BEGIN) calling = true;
    if (addr === PREPARE && vary) {
        ram[sym("scene_rows")] = 1 + Math.floor(rand() * VIEW_ROWS);
        ram[sym("scene_delay")] = Math.floor(rand() * 40);
    } else if (addr === FB_BEGIN && calling) {
        calling = false;
        if (inFrame) fail("frame_begin twice, without frame_end");
        inFrame = true;
        tBegin = now();
    } else if (addr === FB_SHOWN) {
        tShown = now();
        waitCycles += tShown - tBegin;
    } else if (addr === FB_END) {
        if (!inFrame) fail("frame_end without frame_begin");
        inFrame = false;
        drawCycles += now() - tShown;
        drawn++;
        pending.push({
            n: word(sym("frames_drawn")) + 1,
            buffer: (cpu.acccon >> 2) & 1,
            phase: ram[sym("scene_phase")],
            rows: ram[sym("scene_rows")],
        });
        if (pending.length > 1) fail(`frame ${pending.at(-1).n} handed over before frame ${pending[0].n} was shown`);
    }
    return false;
});

const syncFlag = cpu.sysvia.setVBlankInt;
cpu.sysvia.setVBlankInt = function (level) {
    if (!level) syncs++; // (the System VIA flags the sync's end)
    return syncFlag.call(this, level);
};

function flipped(to) {
    flips++;
    const rows = r[4] + 1;
    if (video.vertCounter < r[6]) fail(`flip ${flips} at character row ${video.vertCounter}, which is shown`);
    const margin = (rows - video.vertCounter) * (r[9] + 1) - video.scanlineCounter + r[5];
    minMargin = Math.min(minMargin, margin);
    const field = word(sym("fields"));
    if (lastFlipField !== null) {
        const k = (field - lastFlipField) & 0xffff;
        fieldsShown.set(k, (fieldsShown.get(k) ?? 0) + 1);
    }
    lastFlipField = field;
    const frame = pending.shift();
    if (!frame) return fail(`flip ${flips} with no frame handed over`);
    if (frame.buffer !== to) return fail(`flip ${flips} to buffer ${to}, but frame ${frame.n} was drawn in ${frame.buffer}`);
    // the view, as the frame drew it
    const line = sceneLine(frame.phase);
    let bad = 0;
    for (let y = 0; y < VIEW_H; y++)
        for (let c = 0; c < VIEW_BYTES; c++) {
            const want = sceneByte(line, frame.rows, y, c);
            const got = bufferByte(to, viewAt(y, c));
            if (want !== null && got !== want && bad++ < 3)
                fail(`frame ${frame.n} (phase ${frame.phase}) shown with view line ${y}, column ${c} ` +
                    `${hex(got)}, not ${hex(want)}`);
        }
    // and outside it, as at main_loop (a sample of lines each flip)
    const y0 = (flips * 7) % (SCREEN_ROWS * 8);
    for (const y of [y0, (y0 + 128) % (SCREEN_ROWS * 8)])
        for (let c = 0; c < SCREEN_COLS; c++) {
            const a = at(y, c);
            if (!inView(a) && bufferByte(to, a) !== initial[a - SCREEN])
                fail(`frame ${frame.n} shown with ${hex(a, 4)} outside the view changed: ${hex(bufferByte(to, a))}`);
        }
}

cpu.debugWrite.add((addr, value) => {
    if (!checking) return false;
    if (addr === sym("acccon")) {
        const was = cpu.acccon;
        if ((value ^ was) & 1) flipped(value & 1);
    } else if (addr >= SCREEN && addr < 0x8000) {
        writes++;
        const x = (cpu.acccon >> 2) & 1, d = cpu.acccon & 1;
        if (!inFrame) fail(`a screen write (${hex(addr, 4)}) outside frame_begin..frame_end`);
        if (x === d) fail(`a screen write (${hex(addr, 4)}) to the buffer shown (${d ? "shadow" : "main"} RAM's)`);
    }
    return false;
});

// Counters, read between frames (at frame_begin) so none is half written.
async function counters() {
    await runTo(session, "frame_begin", 5);
    return { t: now(), fields: word(sym("fields")), frames: word(sym("frames")), drawn: word(sym("frames_drawn")), syncs, flips };
}
const delta = (a, b, k) => (b[k] - a[k]) & 0xffff;
function verifyCounts(a, b, what) {
    if (delta(a, b, "fields") !== b.syncs - a.syncs)
        fail(`${what}: ${b.syncs - a.syncs} syncs flagged, but fields counted ${delta(a, b, "fields")}`);
    if (delta(a, b, "frames") !== b.flips - a.flips)
        fail(`${what}: ${b.flips - a.flips} flips, but frames counted ${delta(a, b, "frames")}`);
}
const histogram = () =>
    [...fieldsShown.entries()].sort((p, q) => p[0] - q[0]).map(([k, n]) => `${k}: ${n}`).join(", ");

// The scene as it is.
const a = await counters();
drawCycles = waitCycles = drawn = 0;
await session.runFor(secs * 2e6);
const b = await counters();
verifyCounts(a, b, "steady");
const seconds = (b.t - a.t) / 2e6;
const frames = delta(a, b, "frames"), fields = delta(a, b, "fields");
console.log(
    `frames: the test scene: ${frames} frames shown in ${fields} fields over ${seconds.toFixed(2)}s: ` +
        `${(frames / seconds).toFixed(2)} frames a second, ${(fields / frames).toFixed(2)} fields a frame; ` +
        `a frame ${Math.round(drawCycles / drawn)} cycles drawing, ${Math.round(waitCycles / drawn)} waiting in frame_begin`,
);
console.log(`frames: fields each frame was shown for: ${histogram()}`);

// The picture: where the screen and the view are, and their colours.
await session.runFrames(2);
const fb = session._completeFb8;
const screen = box(fb, (c) => c === sym("SCENE_EDGE"));
const border = box(fb, (c) => c === sym("SCENE_BORDER"));
const others = box(fb, (c) => c < 0);
if (others) fail(`the picture has colours that aren't the BBC's eight, in ${showBox(others)}`);
if (!screen || !reference.screen) fail(`no screen on the picture: ours ${showBox(screen)}, MODE 2's ${showBox(reference.screen)}`);
else {
    const cx = (s) => (s.x0 + s.x1) / 2, cy = (s) => (s.y0 + s.y1) / 2;
    const ref = reference.screen;
    if (cx(screen) !== cx(ref) || cy(screen) !== cy(ref))
        fail(`the screen's centre (${cx(screen)}, ${cy(screen)}) on the picture isn't MODE 2's (${cx(ref)}, ${cy(ref)})`);
    // The picture's scale: MODE 2's 160 x 256 is its box.
    const sx = (ref.x1 - ref.x0) / (m[1] * 2), sy = (ref.y1 - ref.y0) / (m[6] * 8);
    if (screen.x1 - screen.x0 !== SCREEN_COLS * 2 * sx || screen.y1 - screen.y0 !== SCREEN_ROWS * 8 * sy)
        fail(`the screen ${showBox(screen)} on the picture isn't ${SCREEN_COLS * 2} x ${SCREEN_ROWS * 8} pixels`);
    const vx = screen.x0 + sym("VIEW_COL0") * 2 * sx, vy = screen.y0 + sym("VIEW_ROW0") * 8 * sy;
    const want = { x0: vx, y0: vy, x1: vx + VIEW_W * sx, y1: vy + VIEW_H * sy };
    if (showBox(border) !== showBox(want)) fail(`the view's border ${showBox(border)} on the picture isn't at ${showBox(want)}`);
    console.log(
        `frames: on jsbeeb's picture the screen is ${showBox(screen)} (MODE 2's ${showBox(ref)}, ` +
            `${sx} x ${sy} to a pixel), the view's border ${showBox(border)}`,
    );
}

// The scene with its cost varied at random.
fieldsShown.clear();
lastFlipField = null;
vary = true;
const c = await counters();
await session.runFor(secs * 2e6);
const d = await counters();
vary = false;
verifyCounts(c, d, "varied");
console.log(
    `frames: the scene varied (1-${VIEW_ROWS} rows, 0-39 delays): ${delta(c, d, "frames")} frames in ` +
        `${delta(c, d, "fields")} fields; fields each frame was shown for: ${histogram()}`,
);
console.log(`frames: ${flips} flips, ${writes} screen writes checked; the latest flip ${minMargin} lines before the next line shown`);
checking = false;

// The keys: each alone, then with O held.
// (the ZX's keys, decision 10: ESCAPE is its 1, COPY and the cursor keys
// its cursor joystick's 0 and 5-8)
const KEYS = {
    O: "K_O", K: "K_K", Q: "K_Q", W: "K_W", P: "K_P", L: "K_L", N: "K_N", M: "K_M",
    R: "K_R", F: "K_F", U: "K_U", A: "K_A", Z: "K_Z", S: "K_S", X: "K_X",
    K0: "K_0", K5: "K_5", K6: "K_6", K7: "K_7", K8: "K_8",
    D: "K_D", C: "K_C", SPACE: "K_SPACE", B: "K_B", I: "K_I", T: "K_T", Y: "K_Y",
    ESCAPE: "K_1", COPY: "K_0", UP: "K_7", DOWN: "K_6", LEFT: "K_5", RIGHT: "K_8",
};
const KEYS_BYTES = sym("KEYS_BYTES");
const bitmap = (at) => Array.from(ram.subarray(at, at + KEYS_BYTES));
const bits = (...names) => {
    const want = new Array(KEYS_BYTES).fill(0);
    for (const n of names) want[sym(n) >> 3] |= 1 << (sym(n) & 7);
    return want;
};
const same = (p, q) => p.every((v, i) => v === q[i]);
const show = (p) => p.map((v) => hex(v)).join(" ");
const fieldsRun = (n) => session.runFor(n * sym("FIELD_CYCLES"));
const take = () => ram.fill(0, sym("keys_made"), sym("keys_made") + KEYS_BYTES);
let keysOk = 0;
for (const [key, name] of Object.entries(KEYS)) {
    take();
    session.keyDownRaw(BBC[key]);
    await fieldsRun(3);
    const held = bitmap(sym("keys")), made = bitmap(sym("keys_made"));
    session.keyDownRaw(BBC.O);
    await fieldsRun(3);
    const both = bitmap(sym("keys"));
    session.keyUpRaw(BBC.O);
    session.keyUpRaw(BBC[key]);
    await fieldsRun(3);
    const after = bitmap(sym("keys"));
    let ok = true;
    if (!same(held, bits(name))) ok = fail(`${key} held: keys ${show(held)}, not ${name}'s ${show(bits(name))}`);
    if (!same(made, bits(name))) ok = fail(`${key} made: keys_made ${show(made)}, not ${name}'s`);
    if (!same(both, bits(name, "K_O"))) ok = fail(`${key} with O: keys ${show(both)}`);
    if (!same(after, bits())) ok = fail(`${key} released: keys ${show(after)}`);
    if (ok !== false) keysOk++;
}
console.log(`frames: ${keysOk} of ${Object.keys(KEYS).length} keys read as src/input.6502 maps them`);

console.log(failures ? `frames: ${failures} failure(s)` : "frames: ok");
process.exit(failures ? 1 : 0);
