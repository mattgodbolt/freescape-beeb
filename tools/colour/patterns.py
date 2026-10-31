"""MODE 2 patterns: what the BBC can show, and how close it comes.

A pattern is eight pixels, two across and four down (docs/engine.md,
section 2): one MODE 2 byte for each value of `line AND 3`, anchored to the
screen. A MODE 2 pixel is twice as wide as it is tall, so the tile is
square on the screen: four units across, four down, in units of a line.

Colour is compared in OKLab (Björn Ottosson, 2020), scaled by 100 so that
one unit is about a just-noticeable difference ("dE" below). A dither's
colour is the mean of its pixels in linear light, which is what the eye
sees from far enough away. What it sees from nearer is texture: the tile
blurred by a Gaussian of BLUR lines (the eye and the tube), less its mean,
as an RMS dE. And a dither of two far-apart hues (red and cyan for a grey)
reads as coloured noise before it reads as a colour: its clash is the
chroma that cancels in the mix, the pixels' mean chroma less the chroma of
their mean (in OKLab's a, b), which is nothing for a colour with black or
white. The score of a pattern for a target colour is the distance of its
mean, with the hue part of the difference counted HUE times over (a face
that changes hue reads as a different thing; one that is a little light
or dark doesn't; for a grey, any tint counts as hue), plus TEXTURE times
its texture, plus CLASH times its clash. The figures the study reports
are plain dE.

That is an RGB monitor. Through a PAL television (tools/pal.py, jsbeeb's
"PAL TV" display) the pattern is first encoded to composite and decoded:
chroma is smeared over a microsecond or so and averaged with the line
above, luma keeps most of the pixels, and the subcarrier's phase moves on
every field, so what is left of a dither crawls. pal_appearance() decodes
a block of each pattern for PAL_FRAMES successive fields and both line
parities. Its mean is the decoded block's mean in linear light; its
texture is the RMS dE of the decoded block, blurred as above, about that
mean over all the fields (so it counts the crawl too); its crawl is the
part of that which changes from field to field, and costs CRAWL more on
top, because what moves is seen before what stands still. PAL does the
mixing that CLASH stands in for, so a PAL score has no clash term.
"""

import itertools
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import pal  # noqa: E402  (tools/pal.py)

# The BBC's eight physical colours: bit 0 red, bit 1 green, bit 2 blue.
BBC = [tuple(255 * ((c >> b) & 1) for b in range(3)) for c in range(8)]
NAMES = ["black", "red", "green", "yellow", "blue", "magenta", "cyan",
         "white"]

# The model's choices, set by the study (docs/research/colour.md).
BLUR = 0.4       # lines
HUE = 2.0        # weight of a difference in hue against one in L or chroma
GREY = 4.0       # OKLab chroma below which a colour counts as a grey
TEXTURE = 0.35   # dE of mean colour that a dE of texture costs
CLASH = 1.0      # dE of mean colour that a dE of clash costs
CRAWL = 0.35     # and a dE of PAL's crawl, on top of its share of texture

# The display a score is for when none is named: "rgb", "pal", or "both"
# (the mean of the two scores: right on either). The build makes a table
# for each (design.py); PAL is the default the model shows.
DISPLAY = "pal"
# The decoded block: lines and MODE 2 pixels, and the fields it is seen in.
PAL_LINES = 16
PAL_PIXELS = 16
PAL_FRAMES = 8


def lin(c):
    c = np.asarray(c, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def oklab_lin(rgb):
    """Linear sRGB (..., 3) to OKLab (..., 3), times 100."""
    m1 = np.array([[0.4122214708, 0.5363325363, 0.0514459929],
                   [0.2119034982, 0.6806995451, 0.1073969566],
                   [0.0883024619, 0.2817188376, 0.6299787005]])
    m2 = np.array([[0.2104542553, 0.7936177850, -0.0040720468],
                   [1.9779984951, -2.4285922050, 0.4505937099],
                   [0.0259040371, 0.7827717662, -0.8086757660]])
    lms = np.cbrt(np.asarray(rgb) @ m1.T)
    return 100.0 * (lms @ m2.T)


def oklab(rgb):
    return oklab_lin(lin(rgb))


def de(a, b):
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))


# --- The tile ---------------------------------------------------------------
#
# Pixel i of a pattern is at x = i AND 1 (0 left, 1 right) and line
# y = i DIV 2. On the screen its centre is at (2x + 1, y + 0.5).

def mode2_byte(left, right):
    """The MODE 2 byte for two pixels (docs/engine.md, section 1)."""
    b = 0
    for k in range(4):
        b |= ((left >> k) & 1) << (2 * k + 1)
        b |= ((right >> k) & 1) << (2 * k)
    return b


def to_bytes(pixels):
    return [mode2_byte(pixels[2 * y], pixels[2 * y + 1]) for y in range(4)]


def from_bytes(bs):
    def colour(b, shift):
        return sum(((b >> (2 * k + shift)) & 1) << k for k in range(4))
    return [c for b in bs for c in (colour(b, 1), colour(b, 0))]


def _transfer():
    """The blur's gain at each of the tile's spatial frequencies, on the
    4 x 4 grid of line-sized squares that the tile covers."""
    f = np.fft.fftfreq(4)
    fy, fx = np.meshgrid(f, f, indexing="ij")
    return np.exp(-2 * math.pi ** 2 * BLUR ** 2 * (fx ** 2 + fy ** 2))


def _grid(values):
    """Eight per-pixel values (..., 8, ch) to the 4 x 4 grid (..., 4, 4, ch):
    each pixel covers two squares across."""
    v = np.asarray(values)
    g = v.reshape(v.shape[:-2] + (4, 2, v.shape[-1]))
    return np.repeat(g, 2, axis=-2)


def texture_of(lin_pixels):
    """RMS dE of the blurred tile about its mean, from linear RGB (8, 3)."""
    g = _grid(lin_pixels)
    spec = np.fft.fft2(g, axes=(0, 1)) * _transfer()[:, :, None]
    blurred = np.real(np.fft.ifft2(spec, axes=(0, 1)))
    blurred = np.clip(blurred, 0, None)
    mean = oklab_lin(np.mean(lin_pixels, axis=0))
    d = oklab_lin(blurred.reshape(-1, 3)) - mean
    return float(np.sqrt(np.mean(np.sum(d * d, axis=1))))


def clash_of(colours):
    """The chroma that cancels when the pixels mix: mean |ab| - |mean ab|."""
    ab = np.array([oklab(BBC[c])[1:] for c in colours])
    return float(np.mean(np.linalg.norm(ab, axis=1))
                 - np.linalg.norm(np.mean(ab, axis=0)))


# --- Arrangements ------------------------------------------------------------

def _spread(cells):
    """How evenly a set of pixels spreads over the tile, repeated: the
    smallest distance on the screen between two of them (larger is
    better), then the number of pairs that close (fewer is better)."""
    if len(cells) < 2:
        return (99.0, 0)
    pts = [(2 * (i & 1), i // 2) for i in cells]
    ds = []
    for (ax, ay), (bx, by) in itertools.combinations(pts, 2):
        dx = min(abs(ax - bx), 4 - abs(ax - bx))
        dy = min(abs(ay - by), 4 - abs(ay - by))
        ds.append(math.hypot(dx, dy))
    m = min(ds)
    return (m, -sum(1 for d in ds if abs(d - m) < 1e-9))


def best_cells(k):
    """The k of eight pixels that spread most evenly, for a two-colour mix
    of k pixels of one colour. Each level is chosen on its own: patterns
    sit in a table, so nothing requires one level's pixels to be a subset
    of the next's."""
    if k in (0, 8):
        return tuple(range(k))
    best = max(itertools.combinations(range(8), min(k, 8 - k)),
               key=lambda c: (_spread(c), [-i for i in c]))
    if k > 4:
        best = tuple(i for i in range(8) if i not in best)
    return tuple(best)


# Bayer's 2 x 2, repeated down the tile: levels of quarters only.
BAYER2 = [0, 2, 3, 1]


def bayer2_cells(k):
    """k pixels (an even number) in the 2 x 2 Bayer order, repeated."""
    if k % 2:
        raise ValueError("2 x 2 Bayer has quarters only")
    q = k // 2
    return tuple(i for i in range(8) if BAYER2[(i & 1) + 2 * ((i // 2) & 1)] < q)


def three_colour_cells(na, nb, nc):
    """Pixels for a three-colour mix: the two smaller groups together take
    the cells a two-colour mix of their size would, and the smallest of
    them takes the most even part of those."""
    (n0, g0), (n1, g1), (_n2, g2) = sorted([(na, 0), (nb, 1), (nc, 2)])
    minor = best_cells(n0 + n1)
    small = max(itertools.combinations(minor, n0),
                key=lambda c: (_spread(c), [-i for i in c]))
    return [g0 if i in small else g1 if i in minor else g2 for i in range(8)]


# --- Candidates --------------------------------------------------------------

class Pattern:
    __slots__ = ("pixels", "bytes", "mean", "texture", "clash", "colours",
                 "kind", "pal_mean", "pal_texture", "pal_crawl")

    def __init__(self, pixels, kind):
        self.pixels = tuple(pixels)
        self.bytes = to_bytes(self.pixels)
        lp = lin([BBC[c] for c in self.pixels])
        self.mean = oklab_lin(np.mean(lp, axis=0))
        mixed = len(set(self.pixels)) > 1
        self.texture = texture_of(lp) if mixed else 0.0
        self.clash = clash_of(self.pixels) if mixed else 0.0
        self.colours = sorted(set(self.pixels))
        self.kind = kind
        self.pal_mean = self.pal_texture = self.pal_crawl = None

    def seen(self, display):
        """(mean OKLab, what texture and clash add to a score) on display,
        "rgb" or "pal"."""
        if display == "pal":
            return self.pal_mean, (TEXTURE * self.pal_texture
                                   + CRAWL * self.pal_crawl)
        return self.mean, TEXTURE * self.texture + CLASH * self.clash

    def describe(self):
        if len(self.colours) == 1:
            return NAMES[self.colours[0]]
        return "+".join(f"{self.pixels.count(c)}{NAMES[c][0].upper()}"
                        f"{NAMES[c][1:3]}" for c in self.colours)


def candidates(scheme):
    """The patterns a scheme offers, with their PAL appearance:
    - "solid": the eight colours;
    - "bayer2": pairs in quarters, by 2 x 2 Bayer;
    - "pair": pairs in eighths, each level spread as evenly as it can be;
    - "triple": "pair" and three-colour mixes in eighths.
    """
    out = [Pattern([c] * 8, "solid") for c in range(8)]
    if scheme != "solid":
        levels = [2, 4, 6] if scheme == "bayer2" else range(1, 8)
        for a, b in itertools.combinations(range(8), 2):
            for k in levels:
                cells = bayer2_cells(k) if scheme == "bayer2" else best_cells(k)
                px = [b if i in cells else a for i in range(8)]
                out.append(Pattern(px, "pair"))
    if scheme == "triple":
        comps = [(x, y, 8 - x - y) for x in range(1, 7) for y in range(1, 8 - x)]
        layouts = {c: three_colour_cells(*c) for c in comps}
        for trio in itertools.combinations(range(8), 3):
            for comp in comps:
                px = [trio[g] for g in layouts[comp]]
                out.append(Pattern(px, "triple"))
    pal_appearance(out)
    return out


# --- Through PAL -------------------------------------------------------------

_MARGIN = 4      # MODE 2 pixels each side of the block: the FIRs' reach
_basis = None


def pal_block(pixels, phase=0.0, line=0):
    """A block of the pattern as jsbeeb's PAL TV shows it: (rows, texels, 3)
    sRGB values 0..1, two rows a line and four texels a MODE 2 pixel. The
    block's first line is a multiple of four (patterns are anchored to the
    screen), and its edges are decoded with the pattern beyond them."""
    lines, cols = PAL_LINES + 1, PAL_PIXELS + 2 * _MARGIN
    px = np.array([[pixels[2 * ((y - 1) % 4) + (x % 2)] for x in range(cols)]
                   for y in range(lines)])
    fb = pal.expand(lin_srgb_table()[px], 4, 2)
    out = pal.decode(fb, phase, line - 1)
    return out[2:, 4 * _MARGIN:-4 * _MARGIN]


def lin_srgb_table():
    return np.array(BBC, dtype=float) / 255.0


def _cases():
    return [(pal.frame_phase(f), parity)
            for f in range(PAL_FRAMES) for parity in (0, 1)]


def _gauss_valid(img, sigma):
    """A separable Gaussian over the last-but-one two axes, keeping only
    the samples whose whole kernel lies inside."""
    r = max(1, int(math.ceil(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    w = np.lib.stride_tricks.sliding_window_view(img, 2 * r + 1, axis=-3)
    img = np.tensordot(w, k, axes=([-1], [0]))
    w = np.lib.stride_tricks.sliding_window_view(img, 2 * r + 1, axis=-2)
    return np.tensordot(w, k, axes=([-1], [0]))


def pal_appearance(cands):
    """Set pal_mean, pal_texture and pal_crawl on each candidate.

    The decode is linear until its final clamp, so each case is decoded
    once for each of the tile's eight pixels and each of R, G and B lit on
    its own, and a pattern's block is the sum of those its colours light,
    clamped."""
    todo = [p for p in cands if p.pal_mean is None]
    if not todo:
        return
    lines, cols = PAL_LINES + 1, PAL_PIXELS + 2 * _MARGIN
    tile = np.array([[2 * ((y - 1) % 4) + (x % 2) for x in range(cols)]
                     for y in range(lines)])
    global _basis
    if _basis is None:
        _basis = []                     # per case: (24, rows, texels, 3)
        for phase, parity in _cases():
            b = []
            for k in range(8):
                for c in range(3):
                    img = np.zeros((lines, cols, 3))
                    img[..., c] = tile == k
                    out = pal.decode(pal.expand(img, 4, 2), phase, parity - 1,
                                     clamp=False)
                    b.append(out[2:, 4 * _MARGIN:-4 * _MARGIN])
            _basis.append(np.array(b))
    basis = _basis
    sigma = 2 * BLUR                    # a texel is half a line each way
    rgb = np.array(BBC, dtype=float) / 255.0
    for start in range(0, len(todo), 64):
        chunk = todo[start:start + 64]
        w = np.array([rgb[list(p.pixels)].reshape(-1) for p in chunk])
        blocks = []
        for b in basis:
            out = np.clip(np.tensordot(w, b, axes=([1], [0])), 0, 1)
            blocks.append(lin(out * 255.0))
        blocks = np.array(blocks)       # (cases, n, rows, texels, 3)
        mean_lin = blocks.mean(axis=(0, 2, 3))
        mean = oklab_lin(mean_lin)
        blurred = oklab_lin(np.clip(_gauss_valid(blocks, sigma), 0, None))
        d = blurred - mean[None, :, None, None, :]
        tex = np.sqrt(np.mean(np.sum(d * d, axis=-1), axis=(0, 2, 3)))
        over_time = blurred - blurred.mean(axis=0, keepdims=True)
        crawl = np.sqrt(np.mean(np.sum(over_time ** 2, axis=-1), axis=(0, 2, 3)))
        for p, m, t, c in zip(chunk, mean, tex, crawl):
            p.pal_mean, p.pal_texture, p.pal_crawl = m, float(t), float(c)


def target_of(mix):
    """A source colour (a mix of (r, g, b, share)) as OKLab, by its mean in
    linear light."""
    m = sum(lin(c[:3]) * c[3] for c in mix)
    return oklab_lin(m)


def scores(target, cands, display=None):
    """Each candidate's score for the target on display (DISPLAY if None),
    and its colour distance there. On "both", the mean of the two."""
    display = display or DISPLAY
    if display == "both":
        s1, d1 = scores(target, cands, "rgb")
        s2, d2 = scores(target, cands, "pal")
        return (s1 + s2) / 2, (d1 + d2) / 2
    seen = [p.seen(display) for p in cands]
    means = np.array([m for m, _ in seen])
    diff = means - target
    d = np.linalg.norm(diff, axis=1)
    if np.linalg.norm(target[1:]) < GREY:
        # A grey has no hue to keep, but any tint is a hue it never had.
        dc = np.zeros(len(cands))
        dh2 = np.sum(diff[:, 1:] ** 2, axis=1)
    else:
        dc = np.linalg.norm(means[:, 1:], axis=1) - np.linalg.norm(target[1:])
        dh2 = np.clip(np.sum(diff[:, 1:] ** 2, axis=1) - dc ** 2, 0, None)
    weighted = np.sqrt(diff[:, 0] ** 2 + dc ** 2 + HUE ** 2 * dh2)
    return weighted + np.array([c for _, c in seen]), d


def best(target, cands, display=None):
    """The candidate with the lowest score, and its colour distance."""
    s, d = scores(target, cands, display)
    i = int(np.argmin(s))
    return cands[i], float(d[i])
