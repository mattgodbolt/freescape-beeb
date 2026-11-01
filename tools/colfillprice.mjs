#!/usr/bin/env node
// The column fill, priced (docs/research/colfill.md): its kernels
// (src/colfill-kernels.6502) timed in headless jsbeeb, each path on cases
// made for it, the bytes its runs write checked; unit costs fitted from
// them; and each view's cycles priced from the model's counts
// (tools/model/colfill.py --counts) against the row fill's own, measured
// (tools/rastercheck.mjs --json), view by view.
//
//   node tools/colfillprice.mjs DIR --rows ROWS.json [--counts COUNTS.json]
//                               [--file NAME] [--json OUT] [--verbose]
//
// DIR holds the kernels' build (CKERN, symbols.json) and, unless --counts
// says otherwise, counts.json. ROWS.json is rastercheck's for the views to
// price (the scenes of one scene file, --file picking that file's counts
// when counts.json has several). It prints the unit costs, then the views'
// cycles as min / median / mean / p90 / max (p90 by nearest rank) for the
// row fill, the column fill, the better of the two on each view and the
// column fill's floor (FLOOR, below), and fails (exit status 1) if any
// kernel writes the wrong bytes, leaves the wrong nodes, column table or
// plant, or a view's counts are missing.
//
// What the price takes as measured and what it estimates:
// - the faces' and edges' set-up is the row fill's, measured on the same
//   view (its profile's face and edge parts): the column fill keeps that
//   code;
// - the runs, the merged bytes, the coverage of a byte column whose two
//   pixel columns take the same lines, the line loop's steps and stores,
//   the background and the frame's set-up are the kernels', timed;
// - what has no kernel is estimated from the timed parts, as each says
//   (UNTIMED below): a byte column whose pixel columns differ, a half-open
//   node's lines, the per-face work the kernels leave out.
import fs from "node:fs";
import path from "node:path";
import { headless } from "./run6502.mjs";

const args = process.argv.slice(2);
const opt = (name) => {
    const i = args.indexOf(`--${name}`);
    return i >= 0 ? args[i + 1] : undefined;
};
const dir = args[0];
const verbose = args.includes("--verbose");
const rowsPath = opt("rows");
const countsPath = opt("counts") ?? path.join(dir, "counts.json");
const fileSel = opt("file");
const jsonOut = opt("json");
let failures = 0;
const fail = (msg) => {
    failures++;
    console.log(`FAIL: ${msg}`);
};

const m = await headless({ symbols: path.join(dir, "symbols.json") });
const S = (n) => m.sym(n);
m.load(path.join(dir, "CKERN"), 0x1000);
const empty = await m.empty();
const time = async (entry) => (await m.call(S(entry))).total - empty;

// The view's geometry, as src/defs.6502 has it.
const VIEW_H = S("VIEW_H"), VIEW_BYTES = S("VIEW_BYTES"), VIEW_ADDR = S("VIEW_ADDR");
const SCREEN_ROW = S("SCREEN_ROW"), CF_SPLIT = S("CF_SPLIT");
const addr = (y, col) => VIEW_ADDR + Math.floor(y / 8) * SCREEN_ROW + 8 * col + (y % 8);

// Zero page and the nodes' fields (the kernels' fixed addresses).
const Z = Object.fromEntries(["cp", "c_t", "c_b", "pl", "pp", "cv_lo", "cv_hi", "cv_prev", "cv_col", "cv_end",
    "cv_px", "cv_x", "cv_node", "nfree", "nopen", "ml", "mr", "r_y", "f_yend", "ch_p", "ch_xl", "ch_gl", "ch_gh",
    "pa", "ns", "ne", "nk", "nn", "head", "ct", "cb"].map((n) => [n, S(n)]));

// Each routine's plant (d0 = 0, s0 = 2): put the RTS on line y's slot, as
// the routine's state says, after putting back whatever was planted.
const ROUTINES = [
    { base: "cr_d0", lo: "en_d_lo", hi: "en_d0_hi", op: 0xa5 },
    null,
    { base: "cr_s0", lo: "en_s_lo", hi: "en_s0_hi", op: 0x9d },
];
const slot = (i, y) => {
    const r = ROUTINES[i];
    return m.peek(S(r.lo) + y) | (m.peek(S(r.hi) + y) << 8);
};
const plantAt = (i, y) => {
    const r = ROUTINES[i];
    const was = m.peekw(Z.pp + 2 * i);
    if (was) m.poke(was, r.op);
    m.poke(Z.pl + i, y);
    m.pokew(Z.pp + 2 * i, slot(i, y));
    m.poke(slot(i, y), 0x60);
};
// A routine's plant as a run should leave it: on line y, its slot the only
// RTS in the routine, and pl and pp saying so.
const checkPlant = (what, i, y) => {
    const r = ROUTINES[i];
    if (m.peek(Z.pl + i) !== y || m.peekw(Z.pp + 2 * i) !== slot(i, y)) {
        fail(`${what}: the plant kept as line ${m.peek(Z.pl + i)}, not ${y}`);
        return;
    }
    for (let v = 0; v <= VIEW_H; v++)
        if (m.peek(slot(i, v)) !== (v === y ? 0x60 : r.op)) {
            fail(`${what}: line ${v}'s slot is &${m.peek(slot(i, v)).toString(16)}`);
            return;
        }
};
// The routines as assembled: every slot its own opcode, the plants at VIEW_H.
for (const i of [0, 2]) {
    for (let y = 0; y <= VIEW_H; y++) m.poke(slot(i, y), ROUTINES[i].op);
    m.pokew(Z.pp + 2 * i, 0);
    plantAt(i, VIEW_H);
}

const PAT = [0x12, 0x34, 0x56, 0x78];
const clearView = () => {
    for (let y = 0; y < VIEW_H; y++) for (let c = 0; c < VIEW_BYTES; c++) m.poke(addr(y, c), 0);
};
// The bytes a run should have written, and nothing else in its column.
const checkRun = (what, col, t, b, solid) => {
    for (let y = 0; y < VIEW_H; y++) {
        const want = y >= t && y < b ? (solid ? PAT[0] : PAT[y & 3]) : 0;
        if (m.peek(addr(y, col)) !== want) {
            fail(`${what}: line ${y} of column ${col} is &${m.peek(addr(y, col)).toString(16)}, not &${want.toString(16)}`);
            return;
        }
    }
};

// Least squares of y on the columns of xs (each row's terms).
const fit = (xs, ys) => {
    const n = xs[0].length;
    const a = Array.from({ length: n }, () => new Array(n).fill(0));
    const v = new Array(n).fill(0);
    for (let r = 0; r < xs.length; r++)
        for (let i = 0; i < n; i++) {
            v[i] += xs[r][i] * ys[r];
            for (let j = 0; j < n; j++) a[i][j] += xs[r][i] * xs[r][j];
        }
    for (let i = 0; i < n; i++) {
        let p = i;
        for (let r = i + 1; r < n; r++) if (Math.abs(a[r][i]) > Math.abs(a[p][i])) p = r;
        [a[i], a[p]] = [a[p], a[i]];
        [v[i], v[p]] = [v[p], v[i]];
        for (let r = 0; r < n; r++) {
            if (r === i) continue;
            const f = a[r][i] / a[i][i];
            for (let j = i; j < n; j++) a[r][j] -= f * a[i][j];
            v[r] -= f * v[i];
        }
    }
    return v.map((x, i) => x / a[i][i]);
};

const unit = {};

// --- Runs: entered, planted three ways, each length.
for (const [name, i, entry, solid] of [["d", 0, "k_run_d0", false], ["s", 2, "k_run_s0", true]]) {
    m.write(Z.cp, PAT);
    const rows = { moved: [], kept: [], own: [] };
    for (let t = 0; t < VIEW_H; t += 3)
        for (let b = t + 1; b <= VIEW_H; b += 5) {
            for (const how of ["moved", "kept", "own"]) {
                if (how === "own" && b !== VIEW_H) continue;
                const col = (t + b) % CF_SPLIT;
                clearView();
                if (how === "moved") plantAt(i, b === VIEW_H ? t : (b + 7) % VIEW_H === t ? 0 : (b + 7) % VIEW_H);
                if (how === "kept") plantAt(i, b);
                if (how === "own") {
                    if (t === 0) continue;
                    plantAt(i, t - 1);
                }
                if (how === "moved" && m.peek(Z.pl + i) === b) continue;
                m.poke(Z.c_t, t);
                m.poke(Z.c_b, b);
                m.poke(Z.cv_x, 8 * col);
                const was = m.peek(Z.pl + i);
                const c = await time(entry);
                checkRun(`${name} run [${t}, ${b}) ${how}`, col, t, b, solid);
                checkPlant(`${name} run [${t}, ${b}) ${how}`, i, how === "own" ? was : b);
                rows[how].push([[1, b - t], c]);
            }
        }
    for (const how of ["moved", "kept", "own"]) {
        const [a, per] = fit(rows[how].map((r) => r[0]), rows[how].map((r) => r[1]));
        unit[`run_${name}_${how}`] = a;
        unit[`byte_${name}_${how}`] = per;
    }
}

// --- Merged bytes: one on its own, a run of them, four phases into cp.
{
    const L = [0xff, 0xff, 0xff, 0xff], R = [0x00, 0x11, 0x22, 0x33];
    const at = 0x3800;
    m.write(at, L);
    m.write(at + 4, R);
    m.pokew(Z.ml, at);
    m.pokew(Z.mr, at + 4);
    clearView();
    m.poke(Z.c_t, 37);
    m.poke(Z.cv_x, 8 * 5);
    unit.merge1 = await time("k_merge1");
    const want = (y) => (L[y & 3] & 0xaa) | (R[y & 3] & 0x55);
    if (m.peek(addr(37, 5)) !== want(37)) fail("k_merge1 wrote the wrong byte");
    const rows = [];
    for (let n = 1; n <= 12; n++) {
        clearView();
        m.poke(Z.c_t, 20);
        m.poke(Z.c_b, 20 + n);
        const c = await time("k_merge_lines");
        for (let y = 20; y < 20 + n; y++) if (m.peek(addr(y, 5)) !== want(y)) fail(`k_merge_lines: line ${y}`);
        rows.push([[1, n], c]);
    }
    [unit.merge_lines, unit.merge_line] = fit(rows.map((r) => r[0]), rows.map((r) => r[1]));
    unit.merge4 = await time("k_merge4");
    for (let k = 0; k < 4; k++) if (m.peek(Z.cp + k) !== want(k)) fail("k_merge4: the wrong bytes");
}

// --- The frame's columns.
unit.init = await time("k_init");
for (let c = 0; c < VIEW_BYTES; c++) {
    const n = m.peek(Z.head + c);
    if (m.peek(Z.ns + n) !== 0 || m.peek(Z.ne + n) !== VIEW_H || m.peek(Z.nn + n) !== 0) fail(`k_init: column ${c}`);
}

// --- A face byte column's coverage, same lines in both pixel columns.
// Each case: the column's nodes (open runs of lines, top to bottom), the
// face's lines, what's left after, and the runs it writes; the coverage's
// own cycles are the call's less its runs' (each a moved plant) and less
// the column loop's way out.
const coverCase = async (nodes, lo, hi) => {
    m.write(Z.cp, PAT);
    const col = 3;
    clearView();
    // nodes from 1, chained
    for (let i = 0; i < nodes.length; i++) {
        const [s, e] = nodes[i];
        m.poke(Z.ns + 1 + i, s);
        m.poke(Z.ne + 1 + i, e);
        m.poke(Z.nk + 1 + i, 0);
        m.poke(Z.nn + 1 + i, i + 1 < nodes.length ? i + 2 : 0);
    }
    m.poke(Z.head + col, nodes.length ? 1 : 0);
    m.poke(Z.nfree, nodes.length + 1);
    m.poke(Z.nopen, 1);
    m.poke(Z.ct + 2 * col, lo);
    m.poke(Z.ct + 2 * col + 1, lo);
    m.poke(Z.cb + 2 * col, hi);
    m.poke(Z.cb + 2 * col + 1, hi);
    m.poke(Z.cv_col, col);
    m.poke(Z.cv_end, col + 1);
    m.poke(Z.cv_px, 2 * col);
    m.poke(Z.cv_x, 8 * col);
    // every run moves the plant: plant it on a line no run here ends on
    plantAt(0, VIEW_H);
    const c = await time("k_cover_d0");
    // what it wrote: [max(s, lo), min(e, hi)) of each node
    const runs = nodes.map(([s, e]) => [Math.max(s, lo), Math.min(e, hi)]).filter(([a, b]) => a < b);
    for (let y = 0; y < VIEW_H; y++) {
        const want = runs.some(([a, b]) => y >= a && y < b) ? PAT[y & 3] : 0;
        if (m.peek(addr(y, col)) !== want) {
            fail(`cover [${lo}, ${hi}) over ${JSON.stringify(nodes)}: line ${y}`);
            break;
        }
    }
    // the nodes after
    const left = [];
    for (let n = m.peek(Z.head + col), k = 0; n && k < 20; n = m.peek(Z.nn + n), k++)
        left.push([m.peek(Z.ns + n), m.peek(Z.ne + n)]);
    const want = [];
    for (const [s, e] of nodes) {
        if (s < lo) want.push([s, Math.min(e, lo)]);
        if (e > hi) want.push([Math.max(s, hi), e]);
    }
    if (JSON.stringify(left) !== JSON.stringify(want))
        fail(`cover [${lo}, ${hi}) over ${JSON.stringify(nodes)}: nodes ${JSON.stringify(left)}, not ${JSON.stringify(want)}`);
    if (runs.length) checkPlant(`cover [${lo}, ${hi}) over ${JSON.stringify(nodes)}`, 0, runs[runs.length - 1][1]);
    const runCost = runs.reduce((sum, [a, b]) => sum + unit.run_d_moved + unit.byte_d_moved * (b - a), 0);
    return c - runCost;
};
{
    // The column loop alone: a full column, and a column whose nodes the
    // face's lines miss (one node above it ends before, one starts after).
    unit.cover_full = await coverCase([], 10, 20);
    const miss = await coverCase([[0, 10], [50, VIEW_H]], 20, 40);
    // the walk: k nodes above the face, then one it misses
    const walks = [];
    for (let k = 0; k <= 6; k++) {
        const nodes = [];
        for (let i = 0; i < k; i++) nodes.push([4 * i, 4 * i + 2]);
        nodes.push([60, VIEW_H]);
        walks.push([[1, k], await coverCase(nodes, 40, 50)]);
    }
    const [missBase, perWalk] = fit(walks.map((r) => r[0]), walks.map((r) => r[1]));
    unit.walk = perWalk;
    unit.cover_base = missBase;
    unit.cover_miss_check = miss;
    // the cases, each on one node [10, 90) after nothing, less the base
    unit.o_mid = (await coverCase([[10, 90]], 30, 60)) - missBase;
    unit.o_start = (await coverCase([[10, 90]], 10, 60)) - missBase;
    unit.o_end_at = (await coverCase([[10, 90]], 30, 90)) - missBase;
    unit.o_whole_last = (await coverCase([[10, 90]], 10, 90)) - missBase;
    // a node taken whole and then the next: the second's own cost is the
    // case's; the first's is what's left
    const two = await coverCase([[10, 40], [50, 90]], 10, 60);
    unit.o_whole = two - missBase - unit.o_start;
    const two2 = await coverCase([[10, 40], [50, 90]], 20, 60);
    unit.o_end = two2 - missBase - unit.o_start;
    // a node after the first taken whole (unlinked from the one before it),
    // after a walk: checked, and its cost against the head's
    const third = await coverCase([[0, 10], [20, 30], [40, 90]], 15, 35);
    unit.o_whole_mid = third - missBase - unit.walk;
}

// --- The line loop: lines with one chain sloping, then two; stores apart.
{
    const patch = (bra, target) => m.poke(S(bra) + 1, (S(target) - (S(bra) + 2)) & 0xff);
    const linesCase = async (n, ga, gb) => {
        m.poke(Z.r_y, 10);
        m.poke(Z.f_yend, 10 + n);
        // chain a from pixel 60 moving left by ga/256 a line, b from 70 right by gb
        m.write(Z.ch_p, [60, 70]);
        m.write(Z.ch_xl, [0x80, 0x80]);
        m.write(Z.pa, [60, 70]);
        m.write(Z.ch_gl, [(-ga) & 0xff, gb & 0xff]);
        m.write(Z.ch_gh, [((-ga) >> 8) & 0xff, (gb >> 8) & 0xff]);
        patch("kl_sa", ga ? "kl_step_a" : "kl_a_done");
        patch("kl_sb", gb ? "kl_step_b" : "kl_b_done");
        for (let x = 0; x < 256; x++) {
            m.poke(Z.ct + x, 0xee);
            m.poke(Z.cb + x, 0xee);
        }
        const c = await time("k_lines");
        // the column table as the chains leave it: a's columns start on the
        // line it passes them (moving left), b's too (moving right)
        const want = new Array(256).fill(0xee);
        let ua = 60 * 256 + 0x80, ub = 70 * 256 + 0x80, qa = 60, qb = 70;
        for (let y = 10; y < 10 + n; y++) {
            ua -= ga;
            ub += gb;
            for (let x = ua >> 8; x < qa; x++) want[x] = y;
            for (let x = qb; x < ub >> 8; x++) want[x] = y;
            qa = Math.min(qa, ua >> 8);
            qb = Math.max(qb, ub >> 8);
        }
        for (let x = 0; x < 256; x++)
            if (m.peek(Z.ct + x) !== want[x] || m.peek(Z.cb + x) !== 0xee) {
                fail(`k_lines (${n} lines, gradients ${ga}, ${gb}): column ${x}'s T &${m.peek(Z.ct + x).toString(16)}, B &${m.peek(Z.cb + x).toString(16)}`);
                break;
            }
        // the columns stored: chain a's from 60 down, b's from 70 up
        const xa = Math.floor((60 * 256 + 0x80 - ga * n) / 256), xb = Math.floor((70 * 256 + 0x80 + gb * n) / 256);
        return { c, stores: (60 - xa) + (xb - 70), changes: (ga ? Math.min(n, 60 - xa) : 0) + (gb ? Math.min(n, xb - 70) : 0) };
    };
    // the store loop's own cost, a column
    const st = [];
    for (let k = 1; k <= 20; k += 3) {
        m.poke(Z.r_y, 5);
        m.poke(Z.cv_end, 30 + k);
        m.cpu.x = 30;
        for (let x = 0; x < 64; x++) m.poke(Z.ct + x, 0xee);
        const done = await m.call(S("k_stores"));
        st.push([[1, k], done.total - empty]);
        for (let x = 0; x < 64; x++)
            if (m.peek(Z.ct + x) !== (x >= 30 && x < 30 + k ? 5 : 0xee)) {
                fail(`k_stores: column ${x}`);
                break;
            }
    }
    // (k_stores takes X from the harness: call() leaves the registers.)
    [, unit.col_store] = fit(st.map((r) => r[0]), st.map((r) => r[1]));
    // lines with no column passed, one chain then two: a gradient too small
    // to move the boundary within the lines timed
    const flat = [];
    for (const n of [2, 4, 8, 16]) {
        const one = await linesCase(n, 1, 0);
        const both = await linesCase(n, 1, 1);
        flat.push({ n, one: one.c, both: both.c });
    }
    const [a1, l1] = fit(flat.map((r) => [1, r.n]), flat.map((r) => r.one));
    const [a2, l2] = fit(flat.map((r) => [1, r.n]), flat.map((r) => r.both));
    unit.line1 = l1;
    unit.line2_extra = l2 - l1;
    unit.lines_entry = a1;
    // a chain whose boundary moves: each change a store loop, less its stores
    const moving = [];
    for (const [n, g] of [[4, 256], [8, 256], [4, 768], [8, 768], [6, 512]]) {
        const r = await linesCase(n, g, 0);
        moving.push([[1, r.changes], r.c - a1 - l1 * n - unit.col_store * r.stores]);
    }
    [, unit.col_run] = fit(moving.map((r) => r[0]), moving.map((r) => r[1]));
}

// --- The background: per column with nodes, per node, less the runs.
{
    const bgCase = async (perCol) => {
        m.write(Z.cp, PAT);
        clearView();
        let n = 1;
        for (let col = 0; col < CF_SPLIT; col++) {
            const nodes = perCol(col);
            m.poke(Z.head + col, nodes.length ? n : 0);
            nodes.forEach(([s, e], i) => {
                m.poke(Z.ns + n, s);
                m.poke(Z.ne + n, e);
                m.poke(Z.nk + n, 0);
                m.poke(Z.nn + n, i + 1 < nodes.length ? n + 1 : 0);
                n++;
            });
        }
        m.poke(Z.cv_col, 0);
        m.poke(Z.cv_end, CF_SPLIT);
        m.poke(Z.cv_x, 0);
        plantAt(0, VIEW_H - 1);
        const c = await time("k_bg_d0");
        // the runs' own cycles, each as the plant has it when it comes
        let runCost = 0, plant = VIEW_H - 1;
        for (let col = 0; col < CF_SPLIT; col++)
            for (const [s, e] of perCol(col)) {
                const how = e === plant ? "kept" : e === VIEW_H && plant < s ? "own" : "moved";
                if (how === "moved") plant = e;
                runCost += unit[`run_d_${how}`] + unit[`byte_d_${how}`] * (e - s);
                for (let y = 0; y < VIEW_H; y++) {
                    const inRun = perCol(col).some(([a, b]) => y >= a && y < b);
                    if (m.peek(addr(y, col)) !== (inRun ? PAT[y & 3] : 0)) {
                        fail(`k_bg_d0: line ${y} of column ${col}`);
                        break;
                    }
                }
            }
        return c - runCost;
    };
    // Every column of the half is looked at: CF_SPLIT of them, those with
    // no nodes (full) included.
    const rows = [];
    for (const [cols, per] of [[CF_SPLIT, 1], [CF_SPLIT, 2], [CF_SPLIT, 3], [10, 1], [10, 2], [0, 0]]) {
        const c = await bgCase((col) => (col < cols ? Array.from({ length: per }, (_, i) => [30 * i + 2, 30 * i + 20 + (col & 1)]) : []));
        rows.push([[1, cols, cols * per], c]);
    }
    let bgAll;
    [bgAll, unit.bg_col, unit.bg_node] = fit(rows.map((r) => r[0]), rows.map((r) => r[1]));
    // what a full column costs, the call's own few cycles shared among them
    unit.bg_full_col = bgAll / CF_SPLIT;
}

// What has no kernel, estimated from the timed parts (UNTIMED):
// - a byte column whose two pixel columns differ: the same column's base
//   and walk, two more compares of its pixel columns' runs, each node its
//   lines touch at the mean of the same path's cases, each node it makes
//   at the split's (the dearest case);
// - a half-open node the face completes lines of: its removal, as a node
//   taken whole (its merged bytes are priced as merged bytes);
// - each face's own work the kernels leave out: its byte columns' range
//   from its vertices, its pattern's kind and the column loop's set-up,
//   for each half it touches.
const UNTIMED = {
    diff_extra: 20,
    face_extra: 80,
};
unit.d_hit = (unit.o_mid + unit.o_start + unit.o_end + unit.o_whole) / 4;
unit.d_made = unit.o_mid;

console.log("unit costs (cycles; jsbeeb, Master):");
for (const [k, v] of Object.entries(unit)) console.log(`  ${k.padEnd(18)} ${v.toFixed(1)}`);
console.log(`  untimed: ${JSON.stringify(UNTIMED)}`);

// --- The views.
const rowsData = JSON.parse(fs.readFileSync(rowsPath, "utf8"));
const counts = JSON.parse(fs.readFileSync(countsPath, "utf8"));
const byName = new Map(counts.filter((r) => !fileSel || r.file.includes(fileSel)).map((r) => [r.name, r.counts]));

const mergedCost = (len) => {
    // on its own a line at a time, or its four phases into cp and a run
    const alone = unit.merge_lines + unit.merge_line * len;
    const asRun = unit.merge4 + unit.run_d_moved + unit.byte_d_moved * len;
    return Math.min(alone, asRun);
};
const price = (c, row) => {
    const p = {};
    p.face_edge = (row.profile.face ?? 0) + (row.profile.edge ?? 0);
    p.face_extra = UNTIMED.face_extra * c.faces;
    p.lines = unit.line1 * c.lines_stepped + unit.line2_extra * (c.chain_steps - c.lines_stepped) +
        unit.col_run * c.col_runs + unit.col_store * c.col_stores;
    p.cover = unit.cover_full * c.fbc_full + unit.cover_base * c.fbc + unit.walk * (c.walked + c.d_walked) +
        unit.o_whole * c.o_whole + unit.o_end * c.o_end + unit.o_start * c.o_start + unit.o_mid * c.o_mid +
        UNTIMED.diff_extra * c.fbc_diff + unit.d_hit * c.d_hits + unit.d_made * c.d_made + unit.o_whole * c.half_hits;
    // the runs: dithered or solid by their bytes' share (the counts keep
    // the bytes by kind, the runs by plant)
    const dith = c.run_bytes_two + c.run_bytes_four, solid = c.run_bytes_solid;
    const share = dith + solid ? dith / (dith + solid) : 1;
    const pick = (how) => share * unit[`run_d_${how}`] + (1 - share) * unit[`run_s_${how}`];
    p.runs = pick("moved") * c.runs_moved + pick("kept") * c.runs_kept + pick("own") * c.runs_own;
    p.bytes = unit.byte_d_moved * dith + unit.byte_s_moved * solid;
    p.merged = c.merged_lengths.reduce((s, len) => s + mergedCost(len), 0);
    p.background = unit.bg_full_col * VIEW_BYTES + unit.bg_col * c.bg_cols + unit.bg_node * c.bg_nodes;
    p.frame = unit.init;
    p.total = Object.values(p).reduce((a, b) => a + b, 0);
    return p;
};

// A floor no column fill of this design gets under, estimated from
// instruction counts (not timed): the faces' and edges' set-up and the bytes
// as measured, every run at its kept plant's entry, and each other
// operation at the fewest cycles its instructions could take (FLOOR's, a
// byte column's coverage the loads and compares it can't do without, a
// column table's store an unrolled STA abs).
const FLOOR = {
    fbc: 47, walk: 18, hit: 10, made: 20, line: 25, col_store: 4, col_run: 15, merged: 35, bg_col: 15, bg_node: 15,
    frame: 4 * VIEW_BYTES,
};
const floorOf = (c, row) => {
    const dith = c.run_bytes_two + c.run_bytes_four, solid = c.run_bytes_solid;
    return (row.profile.face ?? 0) + (row.profile.edge ?? 0) +
        unit.byte_d_kept * dith + unit.byte_s_kept * solid + Math.min(unit.run_d_kept, unit.run_s_kept) * c.runs +
        FLOOR.fbc * c.fbc + FLOOR.walk * (c.walked + c.d_walked) +
        FLOOR.hit * (c.o_whole + c.o_end + c.o_start + c.o_mid + c.half_hits + c.d_hits) + FLOOR.made * c.made +
        FLOOR.line * c.lines_stepped + FLOOR.col_store * c.col_stores + FLOOR.col_run * c.col_runs +
        FLOOR.merged * c.merged + FLOOR.bg_col * c.bg_cols + FLOOR.bg_node * c.bg_nodes + FLOOR.frame;
};

const rowsCycles = [], colCycles = [], floorCycles = [], bestCycles = [], out = [];
const parts = {};
for (const row of rowsData.results) {
    const c = byName.get(row.name);
    if (!c) {
        fail(`no column counts for ${row.name}`);
        continue;
    }
    const p = price(c, row);
    rowsCycles.push(row.cycles);
    colCycles.push(p.total);
    floorCycles.push(floorOf(c, row));
    bestCycles.push(Math.min(row.cycles, p.total));
    for (const [k, v] of Object.entries(p)) (parts[k] ??= []).push(v);
    out.push({ name: row.name, rows: row.cycles, columns: Math.round(p.total), floor: Math.round(floorOf(c, row)), parts: p });
    if (verbose)
        console.log(`  ${row.name.padEnd(16)} rows ${String(row.cycles).padStart(7)}  columns ${String(Math.round(p.total)).padStart(7)}  ` +
            Object.entries(p).filter(([k]) => k !== "total").map(([k, v]) => `${k} ${Math.round(v)}`).join(" "));
}
const sorted = (xs) => [...xs].sort((a, b) => a - b);
const median = (xs) => {
    const s = sorted(xs);
    const k = s.length >> 1;
    return s.length % 2 ? s[k] : (s[k - 1] + s[k]) / 2;
};
const p90 = (xs) => sorted(xs)[Math.ceil(0.9 * xs.length) - 1];
const stats = (xs) => `min ${Math.round(Math.min(...xs))}, median ${Math.round(median(xs))}, ` +
    `mean ${Math.round(xs.reduce((a, b) => a + b, 0) / xs.length)}, p90 ${Math.round(p90(xs))}, max ${Math.round(Math.max(...xs))}`;
console.log(`${out.length} views (${path.basename(rowsPath)}):`);
console.log(`  row fill, measured:    ${stats(rowsCycles)}`);
console.log(`  column fill, priced:   ${stats(colCycles)}`);
console.log(`  the better of the two, view by view: ${stats(bestCycles)}`);
console.log(`  the column fill's floor (estimated, FLOOR): ${stats(floorCycles)}`);
const ratio = out.map((r) => r.columns / r.rows);
console.log(`  column / row, view by view: median ${median(ratio).toFixed(3)}, min ${Math.min(...ratio).toFixed(3)}, ` +
    `max ${Math.max(...ratio).toFixed(3)}; ${ratio.filter((r) => r < 1).length} of ${ratio.length} views priced faster`);
const busiest = out.reduce((a, b) => (b.rows > a.rows ? b : a));
console.log(`  the busiest view by the row fill (${busiest.name}): rows ${busiest.rows}, columns ${busiest.columns}`);
console.log("  the column fill's median by part: " +
    Object.entries(parts).filter(([k]) => k !== "total").map(([k, v]) => `${k} ${Math.round(median(v))}`).join(", "));
if (jsonOut) fs.writeFileSync(jsonOut, JSON.stringify({ unit, untimed: UNTIMED, floor: FLOOR, views: out }, null, 1) + "\n");
console.log(failures ? `colfill: ${failures} failure(s)` : "colfill: ok");
process.exit(failures ? 1 : 0);
