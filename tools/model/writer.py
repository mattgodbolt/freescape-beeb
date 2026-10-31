"""The writer: the lines' runs to the view's bytes, in the screen's layout.

docs/engine.md, stage 10, and section 9's interface. A MODE 2 byte is two
pixels, the left one's bits in PIX_LEFT (&AA) and the right one's in
PIX_RIGHT (&55); a pattern is four bytes, one for each value of line AND 3.
So a byte one run covers is that run's pattern byte for the line, and a
byte where two runs meet is `left AND &AA OR right AND &55` of their two.
Every byte of the view is written; nothing on the screen is read.
"""

from raster import DEFS, VIEW_W, VIEW_H

VIEW_BYTES = DEFS["VIEW_BYTES"]
VIEW_ADDR = DEFS["VIEW_ADDR"]
SCREEN_ROW = DEFS["SCREEN_ROW"]
PIX_LEFT = DEFS["PIX_LEFT"]
PIX_RIGHT = DEFS["PIX_RIGHT"]


def view_bytes(lines):
    """VIEW_H rows of VIEW_BYTES bytes: line y's byte column c."""
    rows = []
    for y, runs in enumerate(lines):
        pixel = [None] * VIEW_W
        x = 0
        for x0, x1, pattern in runs:
            if x0 != x or x1 <= x0:
                raise ValueError(f"line {y}: runs don't partition it at {x}")
            pixel[x0:x1] = [pattern[y & 3]] * (x1 - x0)
            x = x1
        if x != VIEW_W:
            raise ValueError(f"line {y}: runs end at {x}")
        rows.append(bytes((pixel[2 * c] & PIX_LEFT) | (pixel[2 * c + 1] & PIX_RIGHT)
                          for c in range(VIEW_BYTES)))
    return rows


def address(y, c):
    """Where line y's byte column c is on the screen (src/defs.6502)."""
    return VIEW_ADDR + (y // 8) * SCREEN_ROW + 8 * c + (y % 8)


def screen(lines):
    """{address: byte} for every byte of the view."""
    return {address(y, c): b
            for y, row in enumerate(view_bytes(lines)) for c, b in enumerate(row)}
