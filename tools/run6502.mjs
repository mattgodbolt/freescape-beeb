// Headless jsbeeb for checks and benches: load code and data into a Master
// (or a B), call a routine from a stub, time it, read memory back.
//
//   import { headless } from "./run6502.mjs";
//   const m = await headless({ symbols: "build/x/symbols.json" });
//   m.load("build/x/CODE", m.sym("code_start"));
//   m.write(m.sym("input"), [1, 2, 3]);
//   const { total, marks } = await m.call(m.sym("routine"), { marks: [m.sym("halfway")] });
//   const out = m.read(m.sym("output"), 16);
//
// Addresses take an optional space: "main" (the default), "shadow" (the
// Master's &3000-&7FFF behind ACCCON's X), "hazel" (&C000-&DFFF), or a
// sideways bank number. The space is where the harness puts the bytes;
// what the CPU sees depends on ACCCON and ROMSEL, which the code under test
// sets up itself.
//
// call() runs a stub (SEI, JSR entry, JMP to itself) at STUB with S = &FF,
// and counts jsbeeb's cycles from the JSR to each mark in turn and to the
// stub's return. The stub's own cost (JSR and RTS) is in total, so a check
// that compares routines subtracts empty().
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { loadSymbols } from "./symbols.mjs";

const here = path.dirname(new URL(import.meta.url).pathname);
const root = path.resolve(here, "..");

export const STUB = 0x0140;

export async function headless({ model = "Master", symbols } = {}) {
    const jsbeeb = path.join(root, "node_modules/jsbeeb/src/test-machine.js");
    const { TestMachine } = await import(pathToFileURL(jsbeeb).href);
    const tm = new TestMachine(model);
    await tm.initialise();
    // The OS boots to its prompt; quieten jsbeeb's logging while it does.
    const quiet = console.log;
    console.log = () => {};
    try {
        await tm.runUntilInput();
    } finally {
        console.log = quiet;
    }
    const cpu = tm.processor;
    const ram = cpu.ramRomOs;
    const syms = symbols ? loadSymbols(symbols) : {};

    const where = (a, space = "main") => {
        if (space === "main") return a;
        if (space === "shadow") {
            if (a < 0x3000 || a >= 0x8000) throw new Error(`&${a.toString(16)} isn't shadow RAM`);
            return a + 0x8000;
        }
        if (space === "hazel") {
            if (a < 0xc000 || a >= 0xe000) throw new Error(`&${a.toString(16)} isn't HAZEL`);
            return a - 0x3000;
        }
        if (typeof space === "number") {
            if (a < 0x8000 || a >= 0xc000) throw new Error(`&${a.toString(16)} isn't in a sideways bank`);
            return cpu.romOffset + space * 16384 + (a - 0x8000);
        }
        throw new Error(`unknown space ${space}`);
    };

    const m = {
        tm,
        cpu,
        ram,
        syms,
        sym(name) {
            if (!(name in syms)) throw new Error(`no symbol ${name}`);
            return syms[name];
        },
        where,
        load(file, at, space) {
            const data = fs.readFileSync(file);
            ram.set(data, where(at, space));
            return data.length;
        },
        write(at, bytes, space) {
            ram.set(bytes, where(at, space));
        },
        read(at, n = 1, space) {
            const a = where(at, space);
            return Array.from(ram.subarray(a, a + n));
        },
        peek(at, space) {
            return ram[where(at, space)];
        },
        peekw(at, space) {
            const a = where(at, space);
            return ram[a] | (ram[a + 1] << 8);
        },
        poke(at, v, space) {
            ram[where(at, space)] = v & 0xff;
        },
        pokew(at, v, space) {
            const a = where(at, space);
            ram[a] = v & 0xff;
            ram[a + 1] = (v >> 8) & 0xff;
        },
        // Call entry from the stub; cycles to each mark (in order) and to the
        // return. Throws if the routine doesn't come back within secs.
        async call(entry, { marks = [], secs = 20 } = {}) {
            const done = STUB + 4;
            ram.set([0x78, 0x20, entry & 0xff, entry >> 8, 0x4c, done & 0xff, done >> 8], STUB);
            cpu.pc = STUB;
            cpu.s = 0xff;
            const t0 = tm.elapsedCycles;
            const times = [];
            for (const at of [...marks, done]) {
                await tm.runUntilAddress(at, secs);
                if (cpu.pc !== at) throw new Error(`didn't reach &${at.toString(16)}: pc &${cpu.pc.toString(16)}`);
                times.push(tm.elapsedCycles - t0);
            }
            const total = times.pop();
            return { total, marks: times };
        },
        // What call() costs around an empty routine (an RTS at entry).
        async empty() {
            const at = STUB + 8;
            ram[at] = 0x60;
            return (await m.call(at)).total;
        },
    };
    return m;
}
