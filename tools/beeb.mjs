// A thin client for the jsbeeb MCP server, shared by the tools that drive a
// whole session (tools/play.mjs).
//
// It talks to the real MCP server over stdio (the same one Claude Code
// uses), so what the tools test is exactly what the MCP tools would do.
// Point JSBEEB_MCP at a local server.js to test against a working copy.
//
// Addresses are numbers, &hex or 0xhex strings, or symbols from baron's
// --symbols file (tools/symbols.mjs). A read or write of &3000-&7FFF can
// name the buffer: shadow true for shadow RAM's, false for main RAM's,
// whatever ACCCON says.
import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
import { writeFileSync, mkdirSync } from "fs";
import { dirname, resolve } from "path";
import { loadSymbols } from "./symbols.mjs";

export { loadSymbols };

const MCP = process.env.JSBEEB_MCP
    ? { command: "node", args: [process.env.JSBEEB_MCP] }
    : { command: "node_modules/.bin/jsbeeb-mcp", args: [] }; // (package.json's, pinned by its lock)

const text = (r) => r.content.find((c) => c.type === "text")?.text ?? "";
const image = (r) => r.content.find((c) => c.type === "image");

// bootUntil names a symbol to run to after booting (up to 30s): the way to
// know the program is running, since loading takes a while.
export async function startBeeb({
    disc,
    model = process.env.FS_MODEL || "Master",
    bootSecs = 0,
    bootUntil,
    symbols = "build/freescape.json",
} = {}) {
    const transport = new StdioClientTransport(MCP);
    const client = new Client({ name: "freescape-harness", version: "1.0.0" });
    await client.connect(transport);

    const call = async (name, args) => {
        // (A long timeout: the SDK's 60s default fails long runs when many
        // emulators share the CPUs.)
        const r = await client.callTool({ name, arguments: args }, undefined, { timeout: 30 * 60 * 1000 });
        if (r.isError) throw new Error(`${name}: ${JSON.stringify(r.content)}`);
        return r;
    };
    const json = async (name, args) => JSON.parse(text(await call(name, args)));

    const { session_id } = await json("create_machine", { model });
    const syms = loadSymbols(symbols);

    const beeb = {
        session_id,
        call,
        syms,
        // A symbol's value, or a number (or &hex, 0xhex) as it is.
        addr(a) {
            if (typeof a === "number") return a;
            if (/^(0x|&)/i.test(a)) return parseInt(a.replace("&", "0x"));
            if (!(a in syms)) throw new Error(`unknown symbol ${a}`);
            return syms[a];
        },
        async boot(path = disc) {
            await call("boot_disc", { session_id, image_path: resolve(path) });
        },
        // Seconds of emulated time. Prefer frames() when sampling the display:
        // a whole number of fields lands at the same point in the field.
        async run(secs) {
            return json("run_for_cycles", { session_id, cycles: Math.max(1, Math.round(secs * 2e6)) });
        },
        async cycles(n) {
            return json("run_for_cycles", { session_id, cycles: Math.max(1, Math.round(n)) });
        },
        // Fields painted (jsbeeb calls them frames).
        async frames(count = 1) {
            return json("run_frames", { session_id, count });
        },
        async keyDown(key) {
            await call("key_down", { session_id, key });
        },
        async keyUp(key) {
            await call("key_up", { session_id, key });
        },
        async tap(key, secs = 0.1) {
            await beeb.keyDown(key);
            await beeb.run(secs);
            await beeb.keyUp(key);
        },
        async read(address, length = 1, { shadow } = {}) {
            const a = beeb.addr(address);
            const bytes = [];
            for (let off = 0; off < length; off += 256) {
                const n = Math.min(256, length - off);
                const r = await json("read_memory", { session_id, address: a + off, length: n, shadow });
                bytes.push(...r.bytes);
            }
            return bytes;
        },
        async peek(address, opts) {
            return (await beeb.read(address, 1, opts))[0];
        },
        async peekw(address, opts) {
            const [lo, hi] = await beeb.read(address, 2, opts);
            return lo | (hi << 8);
        },
        async write(address, bytes, { shadow } = {}) {
            await call("write_memory", { session_id, address: beeb.addr(address), bytes, shadow });
        },
        async regs() {
            return text(await call("read_registers", { session_id }));
        },
        async shot(file, { activeOnly = true } = {}) {
            const img = image(await call("screenshot", { session_id, active_only: activeOnly }));
            mkdirSync(dirname(resolve(file)), { recursive: true });
            writeFileSync(resolve(file), Buffer.from(img.data, "base64"));
            return resolve(file);
        },
        // A buffer of the screen, SCREEN (src/defs.6502) to the top of RAM:
        // shadow true for shadow RAM's, false for main RAM's, or left out for
        // the one the CPU sees.
        async dump(file, { shadow } = {}) {
            const base = beeb.addr("SCREEN");
            const length = 0x8000 - base;
            let bytes;
            if (file) {
                mkdirSync(dirname(resolve(file)), { recursive: true });
                await json("save_memory", { session_id, address: base, length, path: resolve(file), shadow });
            } else {
                bytes = await beeb.read(base, length, { shadow });
            }
            return bytes;
        },
        async breakpoint(address, type = "execute") {
            return json("set_breakpoint", { session_id, address: beeb.addr(address), type });
        },
        async clearBreakpoints() {
            await call("clear_breakpoint", { session_id, id: 0 });
        },
        async saveState(label = "") {
            return (await json("save_state", { session_id, label })).state_id;
        },
        async restoreState(state_id) {
            await call("restore_state", { session_id, state_id });
        },
        async close() {
            try {
                await call("destroy_machine", { session_id });
            } catch {}
            await client.close();
        },
        async runUntil(sym, secs = 30) {
            await beeb.breakpoint(sym);
            const r = await beeb.run(secs);
            await beeb.clearBreakpoints();
            if (r.stopped_reason !== "breakpoint") throw new Error(`didn't reach ${sym} in ${secs}s`);
            return r;
        },
    };
    if (disc) {
        await beeb.boot(disc);
        if (bootUntil) await beeb.runUntil(bootUntil);
        if (bootSecs) await beeb.run(bootSecs);
    }
    return beeb;
}
