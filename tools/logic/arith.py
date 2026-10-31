"""The original's multiplies and divide that the logic uses, transcribed.

Each takes and returns register values as unsigned integers, as the Z80
holds them. `python -m tools.logic.arith --snap build/zx/driller.z80`
checks each against the original's own routine on random inputs
(tools/logic/check.py runs it too).
"""


def s8(v):
    v &= 0xFF
    return v - 0x100 if v & 0x80 else v


def s16(v):
    v &= 0xFFFF
    return v - 0x10000 if v & 0x8000 else v


def neg8(v):
    return -v & 0xFF


def minus(a, b):
    """The sign flag of the 8-bit a - b, as CP sets it (JP M / JP P)."""
    return bool((a - b) & 0x80)


def mul_a_hl(a, hl):
    """$910E: A,HL = A * HL, signed byte by signed word, exact (24 bits).
    Returns the 24-bit result; HL is its low 16 bits."""
    if a & 0xFF == 0 or hl & 0xFFFF == 0:
        return 0
    return (s8(a) * s16(hl)) & 0xFFFFFF


def shift6(p):
    """The step's `SLA L : RL H : RL A` twice, then H,A as the result: bits
    6-21 of the 24-bit product, which is floor(product / 64) to 16 bits."""
    return (p >> 6) & 0xFFFF


def mul_hl_de(hl, de):
    """$9179: DE,HL = HL * DE, signed words, exact (32 bits)."""
    if hl & 0xFFFF == 0 or de & 0xFFFF == 0:
        return 0
    return (s16(hl) * s16(de)) & 0xFFFFFFFF


def div32(n, bc):
    """$92D7: DE,HL = DE,HL / BC, signed, on the magnitudes, rounded up
    when the remainder is at least half the divisor (floored), as the
    original's restoring division does it, register by register.
    Returns (quotient, remainder): 32 bits and 16."""
    n &= 0xFFFFFFFF
    bc &= 0xFFFF
    if n == 0:
        return 0, 0
    sign = 1
    if n & 0x80000000:
        n = -n & 0xFFFFFFFF
        sign = -1
    if bc & 0x8000:
        bc = -bc & 0xFFFF
        sign = -sign
    rem = 0
    a = 0x20
    # Normalise: shift until the dividend's top 1 comes out.
    while True:
        carry = n >> 31
        n = (n << 1) & 0xFFFFFFFF
        if carry:
            break
        a -= 1
        if a == 0:
            return n, rem
    while True:
        # ADC HL,HL then SBC HL,BC: the carry out of the ADC is subtracted too.
        t = (rem << 1) | carry
        out = t >> 16
        t &= 0xFFFF
        d = t - bc - out
        if d >= 0:
            rem = d
            qbit = 1           # no borrow, and CCF
        else:
            # ADD HL,BC restores it, and CCF takes that addition's carry.
            r16 = (d & 0xFFFF) + bc
            rem = r16 & 0xFFFF
            qbit = 1 - (r16 >> 16)
        a -= 1
        if a == 0:
            break
        carry = n >> 31
        n = ((n << 1) | qbit) & 0xFFFFFFFF
    n = ((n << 1) | qbit) & 0xFFFFFFFF
    # SRA B : RR C, then the remainder's 16-bit difference's sign.
    half = (bc >> 1) | (bc & 0x8000)
    if not (rem - half) & 0x8000:
        n = (n + 1) & 0xFFFFFFFF
    if sign < 0:
        n = -n & 0xFFFFFFFF
    return n, rem


def mul_h_l(h, l):
    """$928C: HL = H * L, signed bytes."""
    if l & 0xFF == 0 or h & 0xFF == 0:
        return 0
    return (s8(h) * s8(l)) & 0xFFFF


def _check(snap, cases, seed=1):
    import random
    import sys
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    import zx
    from skoolkit.simutils import A, B, C, D, E, H, L
    rng = random.Random(seed)
    spec = zx.Spectrum(snap)
    spec.interrupts = 0
    r = spec.regs
    bad = 0

    def edge16():
        return rng.choice([0, 1, 0xFFFF, 0x8000, 0x7FFF, 64, 0xFFC0, rng.randrange(0x10000),
                           rng.randrange(-1100, 1100) & 0xFFFF, rng.randrange(-70, 70) & 0xFFFF])

    for i in range(cases):
        # $910E
        a, hl = rng.choice([0, 1, 0x80, 0x7F, 0xFF, rng.randrange(256)]), edge16()
        r[A], r[H], r[L] = a, hl >> 8, hl & 0xFF
        spec.call(0x910E)
        got = r[A] << 16 | r[H] << 8 | r[L]
        if got != mul_a_hl(a, hl):
            bad += 1
            print(f"$910E A={a:02X} HL={hl:04X}: original {got:06X}, transcription {mul_a_hl(a, hl):06X}")
        # $9179
        hl, de = edge16(), edge16()
        r[H], r[L], r[D], r[E] = hl >> 8, hl & 0xFF, de >> 8, de & 0xFF
        spec.call(0x9179)
        got = r[D] << 24 | r[E] << 16 | r[H] << 8 | r[L]
        if got != mul_hl_de(hl, de):
            bad += 1
            print(f"$9179 HL={hl:04X} DE={de:04X}: original {got:08X}, transcription {mul_hl_de(hl, de):08X}")
        # $92D7, mostly as the move uses it: a product over a delta
        if rng.random() < 0.7:
            n = mul_hl_de(rng.randrange(-64, 65) & 0xFFFF, rng.randrange(-1100, 1100) & 0xFFFF)
            bc = rng.randrange(-1100, 1100) & 0xFFFF
        else:
            n = rng.choice([rng.randrange(1 << 32), rng.randrange(1 << 16), 0x80000000, 1])
            bc = edge16()
        r[D], r[E], r[H], r[L] = n >> 24, (n >> 16) & 0xFF, (n >> 8) & 0xFF, n & 0xFF
        r[B], r[C] = bc >> 8, bc & 0xFF
        spec.call(0x92D7)
        got = (r[D] << 24 | r[E] << 16 | r[H] << 8 | r[L], r[B] << 8 | r[C])
        if got != div32(n, bc):
            bad += 1
            print(f"$92D7 DEHL={n:08X} BC={bc:04X}: original {got}, transcription {div32(n, bc)}")
        # $928C
        h, l_ = rng.randrange(256), rng.choice([0, 1, 2, 4, 0x80, rng.randrange(256)])
        r[H], r[L] = h, l_
        spec.call(0x928C)
        got = r[H] << 8 | r[L]
        if got != mul_h_l(h, l_):
            bad += 1
            print(f"$928C H={h:02X} L={l_:02X}: original {got:04X}, transcription {mul_h_l(h, l_):04X}")
    return bad


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--snap", default="build/zx/driller.z80")
    ap.add_argument("--cases", type=int, default=2000)
    args = ap.parse_args()
    bad = _check(args.snap, args.cases)
    print(f"arith: {args.cases} cases of each routine, {bad} differ")
    raise SystemExit(1 if bad else 0)
