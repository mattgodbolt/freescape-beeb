"""Stand-in for tools/model/writer.py: the lines' runs to the view's bytes
(docs/engine.md, section 4, stage 10; section 9's interface).

write(lines) returns the view's bytes in the screen's layout, relative to
VIEW_ADDR: line y, byte column c is at (y DIV 8) * SCREEN_ROW + 8 c +
(y MOD 8). Bytes outside the view (the columns beyond VIEW_BYTES in each
character row) are 0. Each run's pixels take its pattern's byte for
line AND 3; a byte where two runs meet takes the left pixel from one and the
right from the other (left AND &AA OR right AND &55).

decode(view) turns the bytes back into the view's logical colours, a list of
VIEW_H lines of VIEW_W pixels, for pictures and checks.
"""
from tools.model.view import PIX_LEFT, PIX_RIGHT, SCREEN_ROW, VIEW_BYTES, VIEW_H, VIEW_W

LENGTH = (VIEW_H - 1) // 8 * SCREEN_ROW + 8 * (VIEW_BYTES - 1) + (VIEW_H - 1) % 8 + 1


def address(y, c):
    return (y // 8) * SCREEN_ROW + 8 * c + (y % 8)


def write(lines):
    out = bytearray(LENGTH)
    for y, runs in enumerate(lines):
        row = [0] * VIEW_BYTES
        at = 0
        for x0, x1, pattern in runs:
            if x0 != at or x1 <= x0:
                raise ValueError("line %d's runs don't partition it" % y)
            b = pattern[y & 3]
            for x in range(x0, x1):
                mask = PIX_RIGHT if x & 1 else PIX_LEFT
                row[x >> 1] = (row[x >> 1] & ~mask) | (b & mask)
            at = x1
        if at != VIEW_W:
            raise ValueError("line %d's runs end at %d" % (y, at))
        for c, b in enumerate(row):
            out[address(y, c)] = b
    return bytes(out)


def pixel_colours(b):
    """A MODE 2 byte's two logical colours, left then right."""
    left = sum(((b >> (2 * i + 1)) & 1) << i for i in range(4))
    right = sum(((b >> (2 * i)) & 1) << i for i in range(4))
    return left, right


def decode(view):
    out = []
    for y in range(VIEW_H):
        line = []
        for c in range(VIEW_BYTES):
            line.extend(pixel_colours(view[address(y, c)]))
        out.append(line)
    return out
