"""The draw order (docs/engine.md, section 4, stage 7; decision 3).

The original's sort, as ScummVM's area.cpp reproduces it
(sortObjectsForRendering, compareBoundingBoxAxis), which is Castle Master
II's L9c2d_sort_objects_for_rendering: a bubble sort over the objects to be
drawn, in the order the object pass found them, comparing each adjacent pair
by their header boxes relative to the camera, axis by axis. A pair is kept
only when the second is nearer on some axis and the first on none; anything
else swaps, incomparable pairs included, so the passes are capped at n - 1
and stop early on a pass with no swap. The result runs farthest first, the
painter's order; the renderer takes it nearest first.

Everything is in integer world units relative to the camera, as the
original's 16-bit compares are.
"""

INCOMPARABLE, FIRST, SECOND = 0, 1, 2


def compare_axis(min_a, max_a, min_b, max_b):
    """Which of two boxes is nearer the camera on one axis (coordinates
    relative to the camera): FIRST, SECOND or INCOMPARABLE."""
    # Touching extents are comparable; overlapping ones aren't.
    if min_a < max_b and min_b < max_a:
        return INCOMPARABLE
    negative_a = min_a < 0
    negative_b = min_b < 0
    # A box across the camera's coordinate is the nearer.
    if negative_a != (max_a < 0):
        return FIRST
    if negative_b != (max_b < 0):
        return SECOND
    # On opposite sides of the camera: no verdict.
    if negative_a != negative_b:
        return INCOMPARABLE
    difference = min_b - min_a
    if difference == 0:
        difference = max_b - max_a
    return FIRST if (difference < 0) == negative_b else SECOND


def compare(box_a, box_b, camera):
    """The three axes' verdicts packed as the original packs them: two bits
    an axis, x highest."""
    result = 0
    for k in range(3):
        result = (result << 2) | compare_axis(
            box_a[0][k] - camera[k], box_a[1][k] - camera[k],
            box_b[0][k] - camera[k], box_b[1][k] - camera[k])
    return result


def keep(result):
    """Keep a pair's order: the second nearer on some axis, the first on none."""
    return result != 0 and (result & 0b010101) == 0


def sort(items, box, camera):
    """items in the object pass's order, farthest first after the sort.
    box(item) is its header box ((x0, y0, z0), (x1, y1, z1)) in world units.
    Returns the sorted list and the number of comparisons made."""
    out = list(items)
    n = len(out)
    comparisons = 0
    for _ in range(1, n):
        changed = False
        for j in range(n - 1):
            comparisons += 1
            if keep(compare(box(out[j]), box(out[j + 1]), camera)):
                continue
            out[j], out[j + 1] = out[j + 1], out[j]
            changed = True
        if not changed:
            break
    return out, comparisons
