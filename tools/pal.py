"""jsbeeb's PAL TV, in NumPy: what a BBC picture looks like through it.

    python -I tools/pal.py IN.png OUT.png [--phase P] [--line N]
                    [--texels N] [--rows N] [--x0 X] [--shrink N]

reads a picture of the BBC's screen and writes it as jsbeeb's "PAL TV"
display shows it. IN.png is, by default, a full 1024 x 625 jsbeeb
framebuffer (jsbeeb-mcp's `screenshot`, MachineSession.screenshot()): one
pixel a texel, two rows a scanline. jsbeeb-mcp's active-area screenshot is
the same cropped and doubled: give --shrink 2 (and --x0, the left border,
if the crop's place matters). For a picture at the BBC's own pixel
grid, give --texels (texels a pixel across: 4 in MODE 2, 2 in MODE 1, 1 in
MODE 0) and --rows 2 (rows a line); the output is then at texel
resolution. --phase is the subcarrier's phase in cycles at the first line
(it moves on by a fraction of a cycle each frame, so a still picture is
one frame of a crawl); --line is the first line's number, whose parity
sets the V switch.

This is a port of jsbeeb 2.16.1's shader, read from node_modules/jsbeeb:
- src/video-filters/shaders/pal-composite.frag.glsl: encode each texel to
  composite (Y + U sin wt + V cos wt, V switched line by line), demodulate
  the line and the line before it (the set's 1H delay line) through the
  chroma FIR and blend them half and half, take luma through the set's
  low-pass and subcarrier trap, and convert back to RGB;
- the FIR coefficients the Vite build bakes into it, from jsbeeb's
  tools/fir-generator.js (chroma: 21 taps, a Kaiser-windowed sinc, -6 dB at
  1.108 MHz) and tools/luma-fir-generator.js (luma: 31 taps), at the
  texel rate, 16 MHz;
- src/video.js: the subcarrier's cycles a line (PalCyclesPerLine, with the
  offset measured on Matt's Master) and how the phase steps a line
  (PalPhasePerLine) and a field;
- src/video-filters/pal-composite.js and src/web/canvas.js: the
  uniforms, and that the texture clamps at its edges.

It computes the shader at every texel centre, so it leaves out what the
page adds after it: the screen's curvature (a change of geometry), the
resampling to the canvas's size, and the phosphor's persistence between
frames. How it was checked against the shader itself is in
docs/research/colour.md, "PAL".
"""

import argparse
import math

import numpy as np

# src/video.js
PAL_NOMINAL_HZ = 4433618.75
PAL_OFFSET_HZ = 239            # measured on Matt's Master (video.js)
PAL_LINE_HZ = 15625
CYCLES_PER_LINE = (PAL_NOMINAL_HZ + PAL_OFFSET_HZ) / PAL_LINE_HZ
PHASE_PER_LINE = CYCLES_PER_LINE % 1
FB_WIDTH = 1024                # texels a line: 64 us at 16 MHz
LINES_A_FIELD = 312            # a non-interlaced field (R8 = 0)

# The shader's constants.
FIR_GAIN = 2.0
CHROMA_BLEND = 0.5
SAMPLE_MHZ = 16.0


def _sinc(x):
    x = np.asarray(x, dtype=float)
    out = np.ones_like(x)
    nz = np.abs(x) >= 1e-10
    out[nz] = np.sin(np.pi * x[nz]) / (np.pi * x[nz])
    return out


def chroma_fir(taps=21, cutoff_mhz=1.108, beta=5.0):
    """tools/fir-generator.js: a sinc at the cutoff under jsbeeb's Kaiser
    window, which takes cosh where Kaiser's takes I0, summing to one."""
    n = np.arange(taps)
    fc = cutoff_mhz / SAMPLE_MHZ
    h = 2 * fc * _sinc(2 * fc * (n - (taps - 1) / 2))
    w = np.cosh(beta * np.sqrt(1 - (2 * n / (taps - 1) - 1) ** 2)) / np.cosh(beta)
    k = h * w
    return k / k.sum()


def _bessel_i0(x):
    s = term = 1.0
    for k in range(1, 50):
        term *= (x / (2 * k)) ** 2
        s += term
    return s


def luma_fir():
    """tools/luma-fir-generator.js: a Hann-windowed 4.5 MHz low-pass of 13
    taps convolved with a subcarrier trap of 19 (identity less a
    Kaiser-windowed band-pass of unit gain at the subcarrier), summing to
    one."""
    lp_taps, taps = 13, 31
    notch_taps = taps - lp_taps + 1
    fc = 4.5 / SAMPLE_MHZ
    n = np.arange(lp_taps)
    hann = 0.5 - 0.5 * np.cos(2 * np.pi * (n + 1) / (lp_taps + 1))
    lp = 2 * fc * _sinc(2 * fc * (n - (lp_taps - 1) / 2)) * hann
    omega = 2 * np.pi * 4.43361875 / SAMPLE_MHZ
    m = np.arange(notch_taps)
    c = (notch_taps - 1) / 2
    r = 2 * (m + 1) / (notch_taps + 1) - 1
    kaiser = np.array([_bessel_i0(3.0 * math.sqrt(1 - x * x)) for x in r]) \
        / _bessel_i0(3.0)
    bp = np.cos(omega * (m - c)) * kaiser
    gain = np.sum(bp * np.cos(omega * (m - c)))
    notch = (m == c).astype(float) - bp / gain
    k = np.convolve(lp, notch)
    return k / k.sum()


CHROMA = chroma_fir()
LUMA = luma_fir()

# The shader's matrices (ITU-R BT.470-6 levels: white at 0.7).
RGB_TO_YUV = np.array([[0.2093, 0.4109, 0.0798],
                       [-0.102228, -0.200704, 0.302939],
                       [0.427311, -0.357823, -0.069488]])
YUV_TO_RGB = np.array([[1.42857143, -0.0000193387, 1.64048673],
                       [1.42857711, -0.567986687, -0.83560997],
                       [1.42854218, 2.92468392, -0.0000217418]])


def decode(fb, phase=0.0, line=0, x0=0, width=FB_WIDTH, clamp=True):
    """The shader's output at each texel of fb, an array (rows, cols, 3) of
    0..1 values, rows two to a scanline (row r is line line + r DIV 2, as
    when jsbeeb doubles lines), column c the texel x0 + c of a line width
    texels wide. phase is the subcarrier's phase in cycles at the start of
    the first line. Texels beyond fb's edges are its edge texels, as the
    texture clamps; give fb margins for a picture without its edges."""
    fb = np.asarray(fb, dtype=float)
    rows, cols, _ = fb.shape
    yuv = fb @ RGB_TO_YUV.T                               # (rows, cols, 3)
    cpp = CYCLES_PER_LINE / width
    r = np.arange(rows)
    lif = r // 2
    vsw = np.where((line + lif) % 2 == 0, 1.0, -1.0)[:, None]
    ph = np.mod(phase + lif * PHASE_PER_LINE, 1.0)[:, None]
    ph_prev = np.mod(ph - PHASE_PER_LINE + 1.0, 1.0)
    x = (x0 + np.arange(cols))[None, :]

    # The texture clamps at its edges: pad by the FIRs' reach once.
    reach = (max(len(CHROMA), len(LUMA)) - 1) // 2
    padded = np.pad(yuv, ((2, 0), (reach, reach), (0, 0)), mode="edge")

    def shifted(dx, dy=0):
        return padded[2 + dy:2 + dy + rows, reach + dx:reach + dx + cols]

    def chroma(dy, v, p):
        acc_u = np.zeros((rows, cols))
        acc_v = np.zeros((rows, cols))
        half = (len(CHROMA) - 1) // 2
        for i, k in enumerate(CHROMA):
            off = i - half
            s = shifted(off, dy)
            t = 2 * np.pi * ((x + off) * cpp + p)
            st, ct = np.sin(t), np.cos(t) * v
            comp = s[..., 0] + s[..., 1] * st + s[..., 2] * ct
            acc_u += FIR_GAIN * k * comp * st
            acc_v += FIR_GAIN * k * comp * ct
        return np.stack([acc_u, acc_v], axis=-1)

    uv = (1 - CHROMA_BLEND) * chroma(0, vsw, ph) + CHROMA_BLEND * chroma(-2, -vsw, ph_prev)
    y = np.zeros((rows, cols))
    half = (len(LUMA) - 1) // 2
    for i, k in enumerate(LUMA):
        off = i - half
        s = shifted(off)
        t = 2 * np.pi * ((x + off) * cpp + ph)
        y += k * (s[..., 0] + s[..., 1] * np.sin(t) + s[..., 2] * np.cos(t) * vsw)
    out = np.stack([y, uv[..., 0], uv[..., 1]], axis=-1) @ YUV_TO_RGB.T
    return np.clip(out, 0.0, 1.0) if clamp else out


def frame_phase(frame, phase=0.0):
    """The subcarrier's phase at a field's first line, frame fields on."""
    return (phase + frame * LINES_A_FIELD * PHASE_PER_LINE) % 1.0


def expand(img, texels=4, rows=2):
    """A picture at the BBC's pixel grid to the framebuffer's texels."""
    return np.repeat(np.repeat(np.asarray(img), rows, axis=0), texels, axis=1)


def main(argv=None):
    from PIL import Image
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("inp")
    ap.add_argument("out")
    ap.add_argument("--phase", type=float, default=0.0)
    ap.add_argument("--line", type=int, default=0)
    ap.add_argument("--texels", type=int, default=1,
                    help="texels a pixel of IN across (MODE 2: 4)")
    ap.add_argument("--rows", type=int, default=1,
                    help="framebuffer rows a pixel of IN down (2 for a line)")
    ap.add_argument("--x0", type=int, default=0,
                    help="the texel column IN's left edge is at")
    ap.add_argument("--shrink", type=int, default=1,
                    help="pixels of IN to a texel each way, for a magnified "
                         "picture (screenshotActive's: 2)")
    a = ap.parse_args(argv)
    img = np.asarray(Image.open(a.inp).convert("RGB"), dtype=float) / 255.0
    img = img[::a.shrink, ::a.shrink]
    fb = expand(img, a.texels, a.rows)
    out = decode(fb, a.phase, a.line, a.x0)
    Image.fromarray((out * 255 + 0.5).astype(np.uint8)).save(a.out)


if __name__ == "__main__":
    main()
