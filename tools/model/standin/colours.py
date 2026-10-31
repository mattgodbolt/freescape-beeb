"""Stand-in for tools/model/colours.py: a placeholder palette, distinct MODE 2
patterns for each colour index, so faces can be told apart in the model's
pictures. Nothing depends on its values (docs/engine.md, section 2).

pattern(area, index), sky(area), ground(area): four bytes each, one for each
value of line AND 3, each the MODE 2 byte for the two pixels it covers.
PALETTE: logical colour to RGB, the BBC's default (8-15 shown as 0-7).
"""

PALETTE = [(0, 0, 0), (255, 0, 0), (0, 255, 0), (255, 255, 0),
           (0, 0, 255), (255, 0, 255), (0, 255, 255), (255, 255, 255)] * 2


def mode2(left, right):
    """The MODE 2 byte for two pixels' logical colours."""
    b = 0
    for i in range(4):
        b |= ((left >> i) & 1) << (2 * i + 1)
        b |= ((right >> i) & 1) << (2 * i)
    return b


def solid(c):
    return bytes([mode2(c, c)] * 4)


# A 2 x 4 Bayer order: (x, line) in the order its pixels turn on.
_ORDER = [(0, 0), (0, 2), (1, 1), (1, 3), (1, 0), (1, 2), (0, 1), (0, 3)]


def dither(a, b, level):
    """A 2 x 4 ordered dither of b over a: level 0-8 pixels of eight are b."""
    on = set(_ORDER[:level])
    return bytes([mode2(b if (0, y) in on else a, b if (1, y) in on else a) for y in range(4)])


# Index 1-15: solids and half dithers of the BBC's colours, all distinct.
_PATTERNS = [
    solid(7), solid(1), solid(2), solid(3), solid(4), solid(5), solid(6),
    dither(1, 7, 4), dither(2, 7, 4), dither(4, 7, 4), dither(0, 7, 4),
    dither(1, 3, 4), dither(4, 6, 4), dither(0, 5, 4), dither(2, 6, 4),
]
_SKY = dither(0, 4, 2)


def pattern(area, index):
    if not 1 <= index <= 15:
        raise ValueError("colour index %d" % index)
    return _PATTERNS[index - 1]


def sky(area):
    i = area["sky"]
    return _PATTERNS[i - 1] if i else _SKY


def ground(area):
    i = area["ground"]
    return _PATTERNS[i - 1] if i else solid(0)
