"""The view's constants: its size, the projection's parameters, the near plane.

The screen's constants (VIEW_W, VIEW_H, SUB, the screen layout) come from
src/defs.6502, so the model and the 6502 share one definition. The
projection's (FX, FY, XC, YC) and ZNEAR are the model's, from the
original's (docs/research/model.md, "The field of view"); they move to
defs.6502 when the 6502 needs them, and tools/model/maths.py must agree
with them (tools/model/parts.py checks).
"""
import ast
import operator
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[2]
DEFS = ROOT / "src" / "defs.6502"


def _evaluate(expr, names):
    """A defs.6502 expression: integers (decimal or &hex), names already
    defined, + - * ( ) and DIV, MOD."""
    expr = re.sub(r"&([0-9A-Fa-f]+)", r"0x\1", expr)
    expr = re.sub(r"\bDIV\b", "//", expr)
    expr = re.sub(r"\bMOD\b", "%", expr)
    ops = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
           ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod}

    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value
        if isinstance(node, ast.Name):
            return names[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in ops:
            return ops[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        raise ValueError("can't evaluate %r" % expr)

    return ev(ast.parse(expr, mode="eval"))


def read_defs(path=DEFS):
    """Every plain `NAME = expression` in defs.6502 that evaluates."""
    names = {}
    for line in path.read_text().splitlines():
        m = re.match(r"\s*([A-Za-z_]\w*)\s*=\s*([^;\\]+)", line)
        if not m:
            continue
        try:
            names[m.group(1)] = _evaluate(m.group(2).strip(), names)
        except (ValueError, KeyError, SyntaxError):
            pass
    return names


_DEFS = read_defs()
VIEW_W = _DEFS["VIEW_W"]
VIEW_H = _DEFS["VIEW_H"]
VIEW_BYTES = _DEFS["VIEW_BYTES"]
SUB = _DEFS["SUB"]
SCREEN_ROW = _DEFS["SCREEN_ROW"]
PIX_LEFT = _DEFS["PIX_LEFT"]
PIX_RIGHT = _DEFS["PIX_RIGHT"]

# World units: an object's byte coordinates are cells, and a cell is CELL
# world units, the units the camera moves in (docs/research/model.md).
CELL = 64

# The projection: the original's (docs/research/zx-driller.md, "The
# matrix" and "The projection"). Its matrix has a scaling diagonal S after
# the rotations, and its projection maps camera x = z to the view's right
# edge and y = z to its top; so with S folded in, the view's half-width is
# where X/Z = S_z/S_x and its half-height where Y/Z = S_z/S_y: square
# pixels on the ZX, and the same field of view on this view, which is the
# ZX's at half the width. The model keeps S out of the matrix, for
# precision, and has it in these focal lengths, in sixteenths of a pixel
# (tests/model/test_view.py holds them to the original's S, read off the
# tape). The centre is the view's.
XC = SUB * VIEW_W // 2
YC = SUB * VIEW_H // 2
FX = 1268
FY = 2536

# The near plane, in camera-space units (64 to the world unit). The
# original has none (its view volume's apex is the eye); faces with a
# vertex nearer than this are clipped against it in 3D, so that projection
# never divides by less. It's ScummVM's near plane for Driller, 2 of its
# units at scale 1, which is 4 world units.
ZNEAR = 4 * 64


def focal_lengths(scale):
    """The focal lengths the original's scaling diagonal (x, y, z) gives
    this view, unrounded."""
    sx, sy, sz = scale
    return XC * sx / sz, YC * sy / sz
