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
# method's error is relative, so ZNEAR costs nothing in precision; it sets
# how many shifts the 6502 needs code for (PROJ_SMIN). Camera space is 64
# to a world unit, so ZNEAR is one world unit.
ZNEAR = 64
ZLIMIT = 1 << 23            # Z is a positive 24-bit number

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
# A normalised reciprocal times quarter-square products:
#
# - s = bitlen(Z) - PROJ_ZBITS, so Z >> s has PROJ_ZBITS bits;
# - R = RECIP[Zi - 512], Zi = Z >> (s + 3), the top ten bits of Z: about
#   2^16 FX / (Z >> s), rounded, for a quarter of the way into Zi's
#   interval (PROJ_DELTA);
# - X' = |X| >> s and Y' = |Y| >> (s - 1), sixteen bits each (Y has a bit
#   more, for FY = 2 FX);
# - P = X' R / 2^16, from three byte products: all of x1 r1 and the high
#   bytes of x1 r0 and x0 r1; x0 r0 is left out, and so is the carry
#   between the two low bytes; then 1 is added. PROJ_DELTA and the 1 take
#   off the truncations' bias (docs/research/maths.md);
# - sx = XC + P for X >= 0, XC - P for X < 0; sy likewise from YC, with
#   the sign the other way.
#
# Where X' doesn't fit sixteen bits (|X/Z| beyond 8 or more), X is taken
# two bits further down and P four times that, so the result is right to
# a few sixteenths up to where it saturates. Results are clamped to the
# signed 16-bit range.

PROJ_ZBITS = 13
PROJ_IBITS = 10                     # Zi: 512-1023
PROJ_DELTA = Fraction(1, 4)         # where in Zi's interval R is exact
PROJ_SMIN = ZNEAR.bit_length() - PROJ_ZBITS
PROJ_SMAX = (ZLIMIT - 1).bit_length() - PROJ_ZBITS
PROJ_SLOW = 2                       # the slow path's extra shift
S16_MIN, S16_MAX = -32768, 32767


def _recip(zi):
    # X' R / 2^16 = FX |X| / Z with Z = (Zi + delta) 2^(s + 3), X = X' 2^s
    zs = (zi + PROJ_DELTA) * (1 << (PROJ_ZBITS - PROJ_IBITS))
    return round(FX * 65536 / zs)


RECIP = [_recip(zi) for zi in range(1 << (PROJ_IBITS - 1), 1 << PROJ_IBITS)]
assert max(RECIP) < 65536 and min(RECIP) >= 256


def _shr(v, k):
    return v >> k if k >= 0 else v << -k


def pmul(xp, r):
    """X' R / 2^16 as the 6502 has it: x1 r1, and the high bytes of x1 r0
    and x0 r1 (their low bytes' carry left out), plus 1."""
    assert 0 <= xp < 65536 and 0 <= r < 65536
    x1, x0, r1, r0 = xp >> 8, xp & 255, r >> 8, r & 255
    p = umul8(x1, r1) + (umul8(x1, r0) >> 8) + (umul8(x0, r1) >> 8) + 1
    return p & 0xFFFF


def _coord(a, s, r):
    """|P| for a magnitude a at shift s, saturated at 65535."""
    xp = _shr(a, s)
    if xp < 65536:
        return pmul(xp, r)
    xp = _shr(a, s + PROJ_SLOW)
    if xp >= 65536:
        return 65535
    p = pmul(xp, r)
    return min(p << PROJ_SLOW, 65535)


def _clamp(v):
    return max(S16_MIN, min(S16_MAX, v))


def project(X, Y, Z):
    """(sx, sy) in sixteenths of a pixel, as the 6502 computes them."""
    assert ZNEAR <= Z < ZLIMIT, Z
    assert -(1 << 23) <= X < (1 << 23) and -(1 << 23) <= Y < (1 << 23)
    s = Z.bit_length() - PROJ_ZBITS
    zi = _shr(Z, s + PROJ_ZBITS - PROJ_IBITS)
    r = RECIP[zi - (1 << (PROJ_IBITS - 1))]
    px = _coord(abs(X), s, r)
    py = _coord(abs(Y), s - 1, r)
    sx = XC + px if X >= 0 else XC - px
    sy = YC - py if Y >= 0 else YC + py
    return _clamp(sx), _clamp(sy)


def project_exact(X, Y, Z):
    """(sx, sy) by exact division, as Fractions, unclamped."""
    assert Z > 0
    return XC + FX * X / Z, YC - FY * Y / Z
