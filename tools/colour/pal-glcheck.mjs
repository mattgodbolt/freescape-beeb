// Runs jsbeeb's own PAL shader in headless Chrome over a test picture, so
// tools/pal.py can be compared with it (tools/colour/pal-glcheck.py).
//
//   node tools/colour/pal-glcheck.mjs JSBEEB_CHECKOUT IN.json OUT.json
//
// JSBEEB_CHECKOUT is a jsbeeb source tree with its node_modules (for
// Playwright, and the Vite plugin that bakes the FIR coefficients into the
// shader: the npm package ships neither). IN.json is {width, height, rgb,
// cases: [{phase, line}]}, rgb the texels' bytes row by row; OUT.json gets
// each case's output bytes, row by row from the top. The quad covers the
// texture one to one with no curvature, and samples the nearest texel, so
// every fragment is at a texel's centre, as tools/pal.py computes.

import { readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const [checkout, inPath, outPath] = process.argv.slice(2);
const load = (rel) => import(pathToFileURL(path.join(checkout, rel)).href);
const { chromium } = await load("node_modules/playwright/index.mjs");
const { applyFirCoefficients, applyLumaCoefficients } = await load("tools/vite-plugin-fir-shader.js");
const { PalCyclesPerLine, PalPhasePerLine } = await load("src/video.js");

const shaders = path.join(checkout, "src/video-filters/shaders");
const frag0 = readFileSync(path.join(shaders, "pal-composite.frag.glsl"), "utf8");
const frag = applyLumaCoefficients(applyFirCoefficients(frag0).code).code;
const vert = readFileSync(path.join(shaders, "pal-composite.vert.glsl"), "utf8");
const input = JSON.parse(readFileSync(inPath, "utf8"));

const browser = await chromium.launch({
    channel: "chrome",
    args: ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"],
});
const page = await browser.newPage();
const out = await page.evaluate(
    ({ vert, frag, input, cycles, phasePerLine }) => {
        const { width, height } = input;
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const gl = canvas.getContext("webgl", { preserveDrawingBuffer: true, antialias: false });
        const compile = (type, src) => {
            const s = gl.createShader(type);
            gl.shaderSource(s, src);
            gl.compileShader(s);
            if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
            return s;
        };
        const prog = gl.createProgram();
        gl.attachShader(prog, compile(gl.VERTEX_SHADER, vert));
        gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, frag));
        gl.linkProgram(prog);
        if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
        gl.useProgram(prog);

        const rgba = new Uint8Array(width * height * 4);
        for (let i = 0; i < width * height; i++) {
            rgba.set(input.rgb.slice(3 * i, 3 * i + 3), 4 * i);
            rgba[4 * i + 3] = 255;
        }
        const tex = gl.createTexture();
        gl.bindTexture(gl.TEXTURE_2D, tex);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, width, height, 0, gl.RGBA, gl.UNSIGNED_BYTE, rgba);

        // Texture row 0 is the picture's top; with uv = pos, window row k
        // (from the bottom, as readPixels counts) shows texture row k.
        const quad = new Float32Array([0, 0, 0, 1, 1, 0, 1, 1]);
        for (const name of ["pos", "uvIn"]) {
            const buf = gl.createBuffer();
            gl.bindBuffer(gl.ARRAY_BUFFER, buf);
            gl.bufferData(gl.ARRAY_BUFFER, quad, gl.STATIC_DRAW);
            const loc = gl.getAttribLocation(prog, name);
            gl.enableVertexAttribArray(loc);
            gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
        }
        const u = (n) => gl.getUniformLocation(prog, n);
        gl.uniform1i(u("uFramebuffer"), 0);
        gl.uniform2f(u("uResolution"), width, height);
        gl.uniform2f(u("uTexelSize"), 1 / width, 1 / height);
        gl.uniform1f(u("uCyclesPerLine"), cycles);
        gl.uniform1f(u("uPhasePerLine"), phasePerLine);
        gl.uniform2f(u("uExtentCentre"), 0.5, 0.5);
        gl.uniform2f(u("uExtentHalfSize"), 0.5, 0.5);
        gl.uniform2f(u("uCurvature"), 0, 0);
        gl.viewport(0, 0, width, height);
        const results = [];
        for (const c of input.cases) {
            gl.uniform2f(u("uLineBase"), c.line, c.line);
            gl.uniform2f(u("uPhaseBase"), c.phase, c.phase);
            gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
            const px = new Uint8Array(width * height * 4);
            gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, px);
            const rgb = [];
            for (let i = 0; i < width * height; i++) rgb.push(px[4 * i], px[4 * i + 1], px[4 * i + 2]);
            results.push(rgb);
        }
        return { renderer: gl.getParameter(gl.RENDERER), results };
    },
    { vert, frag, input, cycles: PalCyclesPerLine, phasePerLine: PalPhasePerLine },
);
await browser.close();
writeFileSync(outPath, JSON.stringify(out));
console.log(`pal-glcheck: ${input.cases.length} cases on ${out.renderer}`);
