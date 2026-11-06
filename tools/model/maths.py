"""The engine's arithmetic, as the 6502 does it (src/maths.6502,
src/project.6502), bit for bit: the transform's products and the
projection (docs/engine.md, stages 3 and 5, and section 9).

The tables are built here, and only here: tools/mkmaths.py writes these
same lists out for the assembler, so the model and the 6502 read the same
bytes.

    mul(v, m)          v * m: a signed 16-bit coordinate by a signed byte
    dot3(row, v)       sum of three such products, wrapped to 24 bits
    project(X, Y, Z)   camera space to view coordinates (sixteenths)
    project_exact(...) the same by exact division, for comparison

docs/research/maths.md has the methods tried and their figures.
"""
from fractions import Fraction

# --- The view (docs/engine.md, section 9; docs/research/zx-driller.md) -----

SUB = 16                    # view coordinates are sixteenths of a pixel
VIEW_W = VIEW_H = 104       # src/defs.6502
# The original's focal length: 104 * 32 / 21 ZX pixels on both axes. Our
# pixels are two ZX pixels wide and one high (decision 2).
FOCAL_ZX = Fraction(104 * 32, 21)
# Rounded to whole sixteenths, so the clip's integer outcodes (clip.py)
# and the projection share one focal length.
FX = round(FOCAL_ZX * SUB / 2)      # 1268 sixteenths
FY = 2 * FX
XC = SUB * VIEW_W // 2      # the view's centre, in sixteenths
YC = SUB * VIEW_H // 2

# The projection takes FY = 2 FX, as square ZX pixels at half the width
# give: y is x's product with one bit more of Y (see project()).
assert FY == 2 * FX

# The nearest Z the projection takes, and one past the farthest. The
# method's error is relative, so ZNEAR costs nothing in precision; the two
# set how many cases the 6502 has code for (PROJ_NMIN to PROJ_NMAX).
# Camera space is 64 to a world unit. ZNEAR is the clip's (view.ZNEAR, four
# world units: nothing nearer is projected), and ZLIMIT is a power of two
# past Driller's deepest view, 8192 * sqrt(3) * 64 (a world's whole
# diagonal; docs/research/maths.md), so no case is spelt out that nothing
# reaches (decision 75).
ZNEAR = 256
ZLIMIT = 1 << 20
COORD_LIMIT = 1 << 23       # X and Y are 24-bit signed numbers

# --- Quarter squares ------------------------------------------------------
#
# a * b = f(a + b) - f(a - b), f(n) = n * n // 4, exactly, for integers
# (a + b and a - b have the same parity, so the floors cancel). The 6502
# reads f(a + b) from SQ at a + b, and f(a - b) from NG at a - b + 255,
# both indexed by a register (b is in the instruction).


def qsq(n):
    return n * n // 4


SQ = [qsq(j) for j in range(512)]           # f(j)
NG = [qsq(j - 255) for j in range(512)]     # f(j - 255)

# The projection's signed high byte x1 (-128..127) times R = 256 + m, with
# x1 + 128 in the register and m in the instruction: x1 + R is
# (x1 + 128 + m) + 128 and x1 - R is (x1 + 128 + 255 - m) - 639. SQC has
# the view's centre added, which the subtraction carries through, so the
# product comes out as XC + x1 R (pmul). The 6502 keeps sixteen bits.
SQC = [qsq(j + 128) + XC for j in range(512)]
NGC = [qsq(j - 639) for j in range(512)]


def umul8(a, b):
    """An unsigned byte product as the tables give it."""
    assert 0 <= a < 256 and 0 <= b < 256
    return (SQ[a + b] - NG[a - b + 255]) & 0xFFFF


def wrap24(v):
    v &= 0xFFFFFF
    return v - (1 << 24) if v & 0x800000 else v


def mul(v, m):
    """v * m, v a signed 16-bit coordinate, m a signed byte, to 24 bits.

    The 6502 multiplies |m| by v's bytes, the low one unsigned and the
    high one as its raw byte, takes 65536 |m| off when v is negative, and
    adds or subtracts by m's sign. All exact, so it's the product."""
    assert -32768 <= v < 32768 and -128 <= m < 128
    am, raw = abs(m), v & 0xFFFF
    t = umul8(raw & 255, am) + 256 * umul8(raw >> 8, am)
    if v < 0:
        t -= am << 16
    return wrap24(-t if m < 0 else t)


def dot3(row, v):
    """row . v for three coefficients and three coordinates, to 24 bits."""
    return wrap24(sum(mul(a, b) for b, a in zip(row, v)))


# --- The projection --------------------------------------------------------
#
# A reciprocal of nine bits, the top one implicit, times two byte products
# a coordinate (docs/research/projection.md):
#
# - n = bitlen(Z), and Zi = Z >> (n - PROJ_IBITS), Z's top ten bits;
# - R = 256 + PROJ_M[Zi - 512]: 256 FX 2^k / Z', Z' = Zi + 1/2, rounded,
#   with k = 0 from PROJ_T up (the high region) and k = -1 below it (the
#   low), so that R is always in [256, 512), a byte M under an implicit
#   one;
# - t = n - PROJ_IBITS + k: X' = X >> t and Y' = Y >> (t - 1), signed and
#   floored, so Z >> t is in [FX / 2, FX) and X' fits sixteen bits for any
#   |X| <= PROJ_XBAND Z (Y has a bit more, for FY = 2 FX);
# - P = floor(X' R / 256) + 1 = x1 R + x0 + hi(x0 M) + 1, X' = x1:x0,
#   from two byte products, exactly: x1 R with x1 signed (SQC and NGC),
#   and x0 M's high byte (SQ and NG). The 1 takes off the floors' bias;
# - sx = XC + P; sy = YC + P from NOT Y' = -Y' - 1, which is YC - P from
#   Y' less R / 256, a sixteenth or two (docs/research/projection.md).
#
# Nothing is clamped: inside the band the results fit sixteen bits, and
# the band is wider than the clip's guard band (decision 17), which every
# projected vertex is inside. The result depends only on (X, Y, Z), so a
# vertex sharing Z, or X and Z, with the last one projected gets exactly
# project's result by the 6502's shorter entries (project_z, project_y).

PROJ_IBITS = 10                     # Zi: 512-1023
PROJ_XBAND = 25                     # the band: |X| <= PROJ_XBAND Z
PROJ_YBAND = 12                     # ... and |Y| <= PROJ_YBAND Z
PROJ_NMIN = ZNEAR.bit_length()      # bitlen(Z): one case each
PROJ_NMAX = (ZLIMIT - 1).bit_length()
S16_MIN, S16_MAX = -32768, 32767


def _recip(zi):
    """(R, k) for Zi: R = 256 FX 2^k / (Zi + 1/2), rounded, in [256, 512)."""
    for k in (0, -1):
        r = round(Fraction(256 * FX * 2 ** k) / (zi + Fraction(1, 2)))
        if r < 512:
            assert r >= 256, zi
            return r, k
    raise AssertionError(zi)


_ZI0 = 1 << (PROJ_IBITS - 1)
_RK = [_recip(zi) for zi in range(_ZI0, 2 * _ZI0)]
PROJ_M = [r - 256 for r, k in _RK]
# The high region (k = 0) is Zi from PROJ_T up, the low (k = -1) below.
PROJ_T = _ZI0 + [k for r, k in _RK].index(0)
assert all((k == 0) == (_ZI0 + i >= PROJ_T) for i, (r, k) in enumerate(_RK))

# The 2D clip's reciprocal (clip.crossing_r): for d normalised to nine bits,
# dn = 256..511, R = 256 + CLIP_M[dn - 256] = 2^17 / (dn + 1/2), rounded.
CLIP_RBITS = 9
CLIP_M = [round(Fraction(1 << (2 * CLIP_RBITS - 1)) / (dn + Fraction(1, 2))) - 256
          for dn in range(1 << (CLIP_RBITS - 1), 1 << CLIP_RBITS)]
assert all(0 <= m < 256 for m in CLIP_M)


def _shr(v, k):
    return v >> k if k >= 0 else v << -k


def recip(Z):
    """(M, t) for Z: R = 256 + M, and the shift for X' (Y's is t - 1)."""
    assert ZNEAR <= Z < ZLIMIT, Z
    n = Z.bit_length()
    zi = _shr(Z, n - PROJ_IBITS)
    k = 0 if zi >= PROJ_T else -1
    return PROJ_M[zi - _ZI0], n - PROJ_IBITS + k


def pmul(v, m):
    """floor(v R / 256) + 1, R = 256 + m, for a signed 16-bit v = x1:x0, as
    the 6502 has it: x1 R (x1 signed, from SQC and NGC) + x0 + hi(x0 m) + 1
    (from SQ and NG)."""
    assert S16_MIN <= v <= S16_MAX and 0 <= m < 256
    x1, x0 = v >> 8, v & 255
    j, k = x1 + 128 + m, x1 + 128 + 255 - m
    p = (SQC[j] - XC) - NGC[k] + x0 + (umul8(x0, m) >> 8) + 1
    assert p == (v * (256 + m)) // 256 + 1
    return p


def project(X, Y, Z):
    """(sx, sy) in sixteenths of a pixel, as the 6502 computes them."""
    assert ZNEAR <= Z < ZLIMIT, Z
    assert -COORD_LIMIT <= X < COORD_LIMIT and -COORD_LIMIT <= Y < COORD_LIMIT, (X, Y)
    assert abs(X) <= PROJ_XBAND * Z and abs(Y) <= PROJ_YBAND * Z, (X, Y, Z)
    m, t = recip(Z)
    xp, yp = _shr(X, t), _shr(Y, t - 1)
    assert S16_MIN <= xp <= S16_MAX and S16_MIN <= yp <= S16_MAX, (X, Y, Z)
    # y by the same product of NOT Y' = -Y' - 1, so its centre's add is
    # x's (the 6502 folds XC into a table)
    sx, sy = XC + pmul(xp, m), YC + pmul(~yp, m)
    assert S16_MIN <= sx <= S16_MAX and S16_MIN <= sy <= S16_MAX, (X, Y, Z)
    return sx, sy


def project_exact(X, Y, Z):
    """(sx, sy) by exact division, as Fractions, unclamped."""
    assert Z > 0
    return XC + FX * X / Z, YC - FY * Y / Z
