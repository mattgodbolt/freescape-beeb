#!/usr/bin/env node
// The waits that read no key, on the live disc (src/live.6502's lv_pass):
// the end's first END_DEAF fields ($9B43, decision 150) and the
// information screen's INFO_SHOW frames ($C59C). The original reads no key
// during either, so a key that goes down and up inside one is lost, and
// what answers the wait is a key held when it ends or pressed after. The
// live check (tools/livecheck.mjs) holds each key until a pass takes it,
// so it never taps inside a wait; this does.
//
//   node tools/waitcheck.mjs [--disc build/live.ssd]
//
// It boots the disc on jsbeeb's full video, runs to live_loop, and:
// - sets GameOver, so the next pass finds the game over and the end comes;
//   taps Q inside the deaf period, and past it the end must still wait;
//   then holds RETURN, and a new game must begin;
// - holds I until the information screen shows; taps Q inside its frames,
//   and past them the screen must still show; then holds RETURN, and the
//   game must go on.
// Exit status 1 on any failure.
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
const disc = opt("disc", "build/live.ssd");
const NAME = path.basename(disc, ".ssd");
const syms = loadSymbols(disc.replace(/\.ssd$/, ".json"));
const sym = (name) => {
    if (!(name in syms)) throw new Error(`no symbol ${name}`);
    return syms[name];
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
const session = new MachineSession("Master");
await quietly(() => session.initialise());
const ram = session._machine.processor.ramRomOs;
session.loadDisc(path.resolve(disc));
await quietly(() => session.autoboot());
await session.runUntilAddress(sym("live_loop"), 120);

const FIELD = sym("FIELD_CYCLES");
const fields = (n) => session.runFor(n * FIELD);
const V = (name) => ram[sym(name)];
let failures = 0;
const check = (what, ok) => {
    console.log(`${NAME}: ${ok ? "ok" : "FAIL"}: ${what}`);
    if (!ok) failures++;
};
const tap = async (key, held = 3) => {
    session.keyDownRaw(BBC[key]);
    await fields(held);
    session.keyUpRaw(BBC[key]);
};
const hold = async (key, held) => {
    session.keyDownRaw(BBC[key]);
    await fields(held);
    session.keyUpRaw(BBC[key]);
};
// the loop settled: a frame or two of the start
await fields(30);
check("the game is on at the start", V("lv_over") === 0 && V("GameOver") === 0);

// The end's wait. The input finds GameOver whatever is held, and the end
// follows in the same pass (lv_pass); its wait reads no key for END_DEAF
// fields from then (lv_end_t0).
ram[sym("GameOver")] = 1;
await fields(20);
check("the end comes (lv_over 2)", V("lv_over") === 2);
const DEAF = sym("END_DEAF");
await tap("Q");
await fields(DEAF + 20 - 23);
check("a key tapped inside the deaf period doesn't answer the end's wait", V("lv_over") === 2 && V("lv_call") === 0);
await hold("RETURN", 20);
await fields(60);
check("RETURN held after it brings a new game", V("lv_over") === 0 && V("GameOver") === 0);

// The information screen: I alone, held until the pass shows it; its
// frames (INFO_SHOW) read no key.
session.keyDownRaw(BBC.I);
for (let i = 0; i < 100 && !V("lv_info"); i++) await fields(1);
session.keyUpRaw(BBC.I);
check("the information screen shows for I", V("lv_info") === 1);
await fields(3);
await tap("Q");
await fields(sym("INFO_SHOW") + 20);
check("a key tapped inside its frames doesn't answer it", V("lv_info") === 1);
await hold("RETURN", 10);
await fields(40);
check("RETURN held after them goes on with the game", V("lv_info") === 0 && V("GameOver") === 0);

console.log(failures ? `${NAME}: ${failures} FAILED` : `${NAME}: the waits ok`);
process.exit(failures ? 1 : 0);
