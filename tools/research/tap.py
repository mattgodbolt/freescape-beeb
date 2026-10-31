import sys, struct, hashlib
def tap_blocks(buf):
    p = 0; out = []
    while p + 2 <= len(buf):
        n = struct.unpack_from('<H', buf, p)[0]; p += 2
        blk = buf[p:p+n]; p += n
        out.append(blk)
    return out
def tzx_blocks(buf):
    assert buf[:7] == b'ZXTape!', buf[:8]
    p = 10; out = []
    while p < len(buf):
        bid = buf[p]; p += 1
        if bid == 0x10:
            n = struct.unpack_from('<H', buf, p+2)[0]; out.append((bid, buf[p+4:p+4+n])); p += 4+n
        elif bid == 0x11:
            n = buf[p+15] | (buf[p+16]<<8) | (buf[p+17]<<16); out.append((bid, buf[p+18:p+18+n])); p += 18+n
        elif bid == 0x14:
            n = buf[p+7] | (buf[p+8]<<8) | (buf[p+9]<<16); out.append((bid, buf[p+10:p+10+n])); p += 10+n
        elif bid == 0x12: p += 4
        elif bid == 0x13: p += 1 + 2*buf[p]
        elif bid == 0x20: p += 2
        elif bid == 0x21: p += 1 + buf[p]
        elif bid == 0x22: pass
        elif bid == 0x30: p += 1 + buf[p]
        elif bid == 0x32: p += 2 + struct.unpack_from('<H', buf, p)[0]
        elif bid == 0x35: p += 0x14 + struct.unpack_from('<I', buf, p+0x10)[0]
        elif bid == 0x15:
            n = buf[p+5] | (buf[p+6]<<8) | (buf[p+7]<<16); out.append((bid, buf[p+8:p+8+n])); p += 8+n
        elif bid == 0x24: p += 2
        elif bid == 0x25: pass
        elif bid == 0x2a: p += 4
        elif bid == 0x2b: p += 5
        elif bid == 0x31: p += 2 + buf[p+1]
        elif bid == 0x33: p += 1 + 3*buf[p]
        elif bid == 0x5a: p += 9
        else:
            print("unknown block id %02x at %x" % (bid, p-1)); break
    return out
if __name__ == '__main__':
    buf = open(sys.argv[1], 'rb').read()
    if buf[:7] == b'ZXTape!':
        bl = tzx_blocks(buf)
    else:
        bl = [(0x10, b) for b in tap_blocks(buf)]
    for i, (bid, b) in enumerate(bl):
        info = ''
        if bid in (0x10, 0x11, 0x14) and len(b) == 19 and b[0] == 0:
            typ = b[1]; name = b[2:12].decode('latin-1'); ln, p1, p2 = struct.unpack_from('<HHH', b, 12)
            info = 'HEADER type=%d name=%r len=%d param1=%d(0x%x) param2=%d' % (typ, name, ln, p1, p1, p2)
        print(i, 'id=%02x' % bid, 'len=%d' % len(b), 'flag=%02x' % (b[0] if b else -1), info, 'md5body=%s' % hashlib.md5(b[1:-1]).hexdigest() if len(b) > 2 else '')
