"""Stand-in for tools/model/maths.py: the projection by exact division.

project(X, Y, Z): camera-space 24-bit integers, Z >= ZNEAR, to (sx, sy) in
view coordinates (sixteenths of a pixel, y down), each rounded to the
nearest sixteenth, half up. The real one uses the 6502's tables and may
round differently; nothing else here depends on how.
"""
from tools.model.view import FX, FY, XC, YC, ZNEAR


def _round_div(n, d):
    return (2 * n + d) // (2 * d)


def project(X, Y, Z):
    if Z < ZNEAR:
        raise ValueError("projecting a vertex nearer than ZNEAR")
    return XC + _round_div(FX * X, Z), YC - _round_div(FY * Y, Z)
