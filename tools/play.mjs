#!/usr/bin/env node
// Run a scripted session against the disc on jsbeeb-mcp and capture what
// happened.
//
//   node tools/play.mjs '<script>' [prefix] [--disc build/freescape.ssd] [--until main_loop] [--boot 0] [--model Master]
//
// It boots the disc, runs to the symbol --until (main_loop, by default:
// the machine is set up and the frames are running), waits --boot more
// seconds, then runs the script. The symbols are beside the disc
// (build/X.json for build/X.ssd).
//
// The script is a comma-separated list of steps:
//   1.5            run 1.5 seconds of emulated time
//   f10            run exactly 10 fields (jsbeeb's frames: one a paint)
//   SPACE:tap      press and release (0.1s); SPACE:0.5 holds for 0.5s
//   LEFT:down      hold a key; LEFT:up releases it
//   !name          screenshot to <prefix>name.png (the active area, 2x)
//   #name          dump both buffers (SCREEN to the top of RAM) to
//                  <prefix>name.main.bin and <prefix>name.shadow.bin
//   ?sym:n         print n bytes at a symbol (or &addr / 0xaddr)
//   =sym:v1/v2/..  poke bytes at a symbol
//   @label         run until PC reaches a symbol (execute breakpoint)
//
// Key names are jsbeeb-mcp's: the BBC's own (SPACE, RETURN, COPY, LEFT,
// A-Z, 0-9), or an internal key number.
import { startBeeb } from "./beeb.mjs";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
    const i = args.indexOf(`--${name}`);
    if (i < 0) return dflt;
    const v = args[i + 1];
    args.splice(i, 2);
    return v;
};
const disc = opt("disc", "build/freescape.ssd");
const symbols = disc.replace(/\.ssd$/, ".json");
const bootSecs = parseFloat(opt("boot", "0"));
const bootUntil = opt("until", "main_loop");
const model = opt("model", process.env.FS_MODEL || "Master");
const script = args[0] ?? "";
const prefix = args[1] ?? "shots/p_";

const beeb = await startBeeb({ disc, bootSecs, bootUntil, model, symbols });
try {
    for (const raw of script.split(",")) {
        const step = raw.trim();
        if (!step) continue;
        if (step.startsWith("!")) {
            console.log("SHOT", await beeb.shot(`${prefix}${step.slice(1)}.png`));
        } else if (step.startsWith("#")) {
            for (const [name, shadow] of [["main", false], ["shadow", true]]) {
                const file = `${prefix}${step.slice(1)}.${name}.bin`;
                await beeb.dump(file, { shadow });
                console.log("DUMP", file);
            }
        } else if (step.startsWith("?")) {
            const [sym, n] = step.slice(1).split(":");
            const bytes = await beeb.read(sym, parseInt(n || "1"));
            console.log(sym, bytes.map((b) => b.toString(16).padStart(2, "0")).join(" "));
        } else if (step.startsWith("=")) {
            const [sym, vals] = step.slice(1).split(":");
            await beeb.write(sym, vals.split("/").map((v) => parseInt(v)));
        } else if (step.startsWith("@")) {
            await beeb.breakpoint(step.slice(1));
            const r = await beeb.run(30);
            await beeb.clearBreakpoints();
            console.log("BREAK", step.slice(1), r.stopped_reason ?? "timeout");
        } else if (/^f\d+$/.test(step)) {
            await beeb.frames(parseInt(step.slice(1)));
        } else if (/^[\d.]+$/.test(step)) {
            await beeb.run(parseFloat(step));
        } else {
            const [key, action = "tap"] = step.split(":");
            if (action === "down") await beeb.keyDown(key);
            else if (action === "up") await beeb.keyUp(key);
            else if (action === "tap") await beeb.tap(key);
            else await beeb.tap(key, parseFloat(action));
        }
    }
} finally {
    await beeb.close();
}
process.exit(0);
