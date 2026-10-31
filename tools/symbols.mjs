// Baron's --symbols output (format 2, baron 0.5 on): assemblies of
// sections, each with its labels, assignments, za_autos and so on as
// { name: { value, source, line } }. Flattened, so callers can ask for
// sym("angle") without caring which section or kind. Names with "@" are
// anonymous scopes (loop variables, macro parameters).
import { readFileSync, existsSync } from "node:fs";

export function loadSymbols(path) {
    if (!existsSync(path)) return {};
    const all = JSON.parse(readFileSync(path, "utf8"));
    if (all.format !== 2) throw new Error(`${path}: symbol format ${all.format}, expected 2 (baron 0.5)`);
    const out = {};
    for (const assembly of all.assemblies) {
        for (const section of assembly.sections) {
            for (const kind of Object.values(section)) {
                if (kind === null || typeof kind !== "object" || Array.isArray(kind)) continue;
                for (const [k, v] of Object.entries(kind)) {
                    if (!k.includes("@") && typeof v === "object" && v && "value" in v) out[k] = v.value;
                }
            }
        }
    }
    return out;
}
