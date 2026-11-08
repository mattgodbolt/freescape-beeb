#!/usr/bin/env node
// The sounds on the live disc (src/sound.6502) against the driver's model
// (tools/model/sound.py, through tools/mksound.py --check), write for write.
//
//   node tools/soundcheck.mjs [--disc build/live.ssd] [--sound build/sound/sound.json] [--log OUT]
//
// It boots the disc on jsbeeb (its SN76489 the instrumented one, which
// takes a byte as the System VIA's write enable has been low long enough)
// to live_loop, with no key held and the clock's minute kept away, so the
// logic asks for nothing. Then, as the logic's hook does (snd_ask: a sound
// put in snd_next once it's free), each of the original's sounds alone,
// waiting for each to end; then the sounds in a queue, each put in as soon
// as the last is taken, so each starts the tick the one before ends:
// every sound into every other kind (a tone into the noises, the noises
// into tones and each other, the silent ones among them). It hands the
// bytes the chip took, tick by tick (tools/soundcap.mjs), and the asks to
// the model, which must have written the same bytes in the same ticks:
// sound_init's first, every channel silent. Fails (exit status 1) on any
// difference. Reports snd_tick's cycles, playing and idle.
import fs from "node:fs";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./symbols.mjs";
import { soundCapture } from "./soundcap.mjs";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "..");
const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    return i < 0 ? dflt : args[i + 1];
};
const disc = opt("disc", "build/live.ssd");
const soundJson = opt("sound", "build/sound/sound.json");
const logOut = opt("log", "build/sound/check.json");
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
const cap = soundCapture(session, sym);
session.loadDisc(path.resolve(disc));
await quietly(() => session.autoboot());
await session.runUntilAddress(sym("live_loop"), 120);

const FIELD = sym("FIELD_CYCLES");
const SOUNDS = sym("SND_SOUNDS");
// (the clock held: no minute ends, src/live.6502's lv_clock)
const CL_HOLD = sym("cl_hold");
const awayMinute = () => {
    ram[CL_HOLD] = 1;
};
// run until cond(), a quarter field at a time, for at most limit fields
async function until(cond, limit, what) {
    for (let i = 0; i < 4 * limit; i++) {
        if (cond()) return;
        awayMinute();
        await session.runFor(FIELD / 4);
    }
    throw new Error(`soundcheck: ${what}: not within ${limit} fields`);
}
const LONGEST = 400; // fields: the longest sound is under four seconds
// An ask as snd_ask makes it: from the main loop, never inside the
// interrupt (which a stop of the emulator may be)
const LIVE_LOOP = sym("live_loop");
async function ask(n) {
    await session.runUntilAddress(LIVE_LOOP, 5);
    cap.ask(n);
}

// Each sound alone.
for (let n = 1; n <= SOUNDS; n++) {
    await until(() => !cap.busy(), LONGEST, `sound ${n - 1} to end`);
    await session.runFor(2 * FIELD);
    await ask(n);
}
// In a queue: each put in as soon as the last is taken.
const QUEUE = [3, 4, 19, 13, 5, 1, 16, 2, 13, 13, 17, 12, 18, 9, 21, 14, 6, 19, 19, 10, 15, 7];
for (const n of QUEUE) {
    await until(() => cap.free(), LONGEST, `the sound before ${n} to be taken`);
    await ask(n);
}
await until(() => !cap.busy(), LONGEST, "the queue to end");
await session.runFor(4 * FIELD);

const log = cap.log();
fs.mkdirSync(path.dirname(logOut), { recursive: true });
fs.writeFileSync(logOut, JSON.stringify(log));
const py = spawnSync(path.join(root, ".venv/bin/python"), ["-I", path.join(root, "tools/mksound.py"), "--check", logOut, soundJson],
    { encoding: "utf8" });
process.stdout.write(py.stdout);
process.stderr.write(py.stderr);
const pct = (xs, p) => {
    const s = [...xs].sort((a, b) => a - b);
    return s.length ? s[Math.min(s.length - 1, Math.floor((p / 100) * s.length))] : "-";
};
const cyc = (xs) => `${pct(xs, 50)} / ${pct(xs, 90)} / ${xs.length ? Math.max(...xs) : "-"} (${xs.length})`;
console.log(`sound: snd_tick's cycles (median / p90 / most), a sound playing ${cyc(cap.cycles.playing)}, idle ${cyc(cap.cycles.idle)}`);
if (py.status !== 0) {
    console.log("sound: FAIL");
    process.exit(1);
}
console.log("sound: ok");
