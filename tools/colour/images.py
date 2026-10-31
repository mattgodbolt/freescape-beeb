"""Read one file out of a fetched disc image, in memory.

The colour study reads Driller's executables straight out of the disc
images that tools/fetch.d/30-colour.sh downloads, so nothing extracted is
ever written next to them. The images are untrusted data: these readers
only index into the bytes, and every read is bounds-checked by Python's
slicing (a short slice is caught where it matters).

- fat12_read: a DOS or Atari ST floppy (FAT12, root directory only).
- adf_read: an Amiga floppy (OFS or FFS), by path.
- dsk_read: an Amstrad CPC disc (standard or extended DSK, AMSDOS data or
  system format).
"""

import struct


class ImageError(Exception):
    pass


# --- FAT12 (DOS, Atari ST) -------------------------------------------------

class _Fat12:
    def __init__(self, img):
        (self.bps, self.spc, reserved, nfats, self.nroot, _total, _media,
         spf) = struct.unpack_from("<HBHBHHBH", img, 11)
        if self.bps not in (512, 1024) or self.spc == 0 or nfats == 0:
            raise ImageError("not a FAT12 boot sector")
        self.img = img
        self.fat = img[reserved * self.bps:(reserved + spf) * self.bps]
        self.root = (reserved + nfats * spf) * self.bps
        self.data = self.root + (
            (self.nroot * 32 + self.bps - 1) // self.bps) * self.bps

    def chain(self, cluster):
        csize = self.bps * self.spc
        out = bytearray()
        seen = set()
        while 2 <= cluster < 0xFF0:
            if cluster in seen:
                raise ImageError("FAT loop")
            seen.add(cluster)
            off = self.data + (cluster - 2) * csize
            out += self.img[off:off + csize]
            j = cluster * 3 // 2
            v = self.fat[j] | (self.fat[j + 1] << 8)
            cluster = v >> 4 if cluster & 1 else v & 0xFFF
        return bytes(out)

    def entries(self, path):
        """(name, is_dir, first cluster, size) in the directory at path."""
        d = self.img[self.root:self.root + 32 * self.nroot]
        for part in [p for p in path.split("/") if p]:
            for name, is_dir, cluster, _size in self._parse(d):
                if is_dir and name.upper() == part.upper():
                    d = self.chain(cluster)
                    break
            else:
                raise ImageError(f"{part}: no such directory")
        return list(self._parse(d))

    @staticmethod
    def _parse(d):
        for i in range(len(d) // 32):
            e = d[32 * i:32 * i + 32]
            if e[0] == 0:
                break
            if e[0] == 0xE5 or e[11] & 0x08 or e[0] == ord("."):
                continue  # deleted, volume label, . and ..
            name = e[0:8].decode("latin-1").rstrip()
            ext = e[8:11].decode("latin-1").rstrip()
            cluster, size = struct.unpack_from("<HI", e, 26)
            yield (name + "." + ext if ext else name), bool(e[11] & 0x10), \
                cluster, size


def fat12_list(img, path=""):
    return [(n, "dir" if d else s)
            for n, d, _c, s in _Fat12(img).entries(path)]


def fat12_read(img, path):
    fs = _Fat12(img)
    *dirs, leaf = path.split("/")
    for name, is_dir, cluster, size in fs.entries("/".join(dirs)):
        if not is_dir and name.upper() == leaf.upper():
            out = fs.chain(cluster)
            if len(out) < size:
                raise ImageError(f"{path}: short chain")
            return out[:size]
    raise ImageError(f"{path}: not in the image")


# --- Amiga ADF (OFS, FFS) --------------------------------------------------

_ADF_BLOCK = 512


def _adf_block(img, n):
    b = img[n * _ADF_BLOCK:(n + 1) * _ADF_BLOCK]
    if len(b) != _ADF_BLOCK:
        raise ImageError(f"block {n} outside the image")
    return b


def _adf_long(b, i):
    """The i'th big-endian longword; negative i counts from the end."""
    if i < 0:
        i += _ADF_BLOCK // 4
    return struct.unpack_from(">I", b, 4 * i)[0]


def _adf_name(b):
    n = b[_ADF_BLOCK - 80]
    return b[_ADF_BLOCK - 79:_ADF_BLOCK - 79 + min(n, 30)].decode("latin-1")


def _adf_hash(name):
    h = len(name)
    for c in name.upper():
        h = (h * 13 + ord(c)) & 0x7FF
    return h % 72


def _adf_lookup(img, dirblock, name):
    b = _adf_block(img, dirblock)
    key = _adf_long(b, 6 + _adf_hash(name))
    while key:
        e = _adf_block(img, key)
        if _adf_name(e).upper() == name.upper():
            return key
        key = _adf_long(e, -4)  # hash chain
    raise ImageError(f"{name}: not found")


def adf_list(img, path=""):
    boot = img[0:4]
    if boot[:3] != b"DOS":
        raise ImageError("not an AmigaDOS disc")
    block = len(img) // _ADF_BLOCK // 2
    for part in [p for p in path.split("/") if p]:
        block = _adf_lookup(img, block, part)
    b = _adf_block(img, block)
    out = []
    for i in range(72):
        key = _adf_long(b, 6 + i)
        while key:
            e = _adf_block(img, key)
            kind = struct.unpack(">i", e[-4:])[0]
            out.append((_adf_name(e), "dir" if kind == 2 else _adf_long(e, -47)))
            key = _adf_long(e, -4)
    return out


def adf_read(img, path):
    if img[:3] != b"DOS":
        raise ImageError("not an AmigaDOS disc")
    ffs = img[3] & 1
    block = len(img) // _ADF_BLOCK // 2  # the root block
    for part in [p for p in path.split("/") if p]:
        block = _adf_lookup(img, block, part)
    header = _adf_block(img, block)
    size = _adf_long(header, -47)
    out = bytearray()
    # Data blocks are listed backwards from longword 77 of the header and of
    # each extension block.
    h = header
    seen = set()
    while len(out) < size:
        count = _adf_long(h, 2)
        for i in range(count):
            d = _adf_block(img, _adf_long(h, 77 - i))
            out += d if ffs else d[24:24 + _adf_long(d, 3)]
            if len(out) >= size:
                break
        ext = _adf_long(h, -2)
        if len(out) >= size or not ext:
            break
        if ext in seen:
            raise ImageError("extension loop")
        seen.add(ext)
        h = _adf_block(img, ext)
    if len(out) < size:
        raise ImageError(f"{path}: short file")
    return bytes(out[:size])


# --- Amstrad CPC DSK -------------------------------------------------------

def _dsk_sectors(img):
    """{(track, side, sector id): bytes} from a standard or extended DSK."""
    ext = img.startswith(b"EXTENDED")
    if not (ext or img.startswith(b"MV - CPC")):
        raise ImageError("not a CPC DSK")
    tracks, sides = img[0x30], img[0x31]
    sizes = list(img[0x34:0x34 + tracks * sides]) if ext else None
    fixed = struct.unpack_from("<H", img, 0x32)[0]
    pos = 0x100
    out = {}
    for t in range(tracks * sides):
        tsize = sizes[t] * 256 if ext else fixed
        if tsize == 0:
            continue
        ti = img[pos:pos + tsize]
        if not ti.startswith(b"Track-Info"):
            raise ImageError(f"bad track header at {pos:#x}")
        nsec = ti[0x15]
        p = 0x100
        for s in range(nsec):
            c, h, r, n, _st1, _st2, alen = struct.unpack_from(
                "<BBBBBBH", ti, 0x18 + 8 * s)
            length = alen if ext else 128 << n
            out[(c, h, r)] = ti[p:p + length]
            p += length
        pos += tsize
    return out


def dsk_read(img, wanted):
    """The file with its AMSDOS header, if it has one."""
    sec = _dsk_sectors(img)
    ids = {r for (_c, _h, r) in sec}
    if 0xC1 in ids:          # data format: no reserved tracks
        first, off = 0xC1, 0
    elif 0x41 in ids:        # system format: two reserved tracks
        first, off = 0x41, 2
    else:
        raise ImageError("unknown CPC disc format")

    def block(n):
        # 1K blocks of two 512-byte sectors, 9 sectors a track.
        data = b""
        for k in (2 * n, 2 * n + 1):
            t, s = divmod(k, 9)
            data += sec[(t + off, 0, first + s)]
        return data

    directory = block(0) + block(1)
    want = wanted.upper()
    extents = []
    for i in range(64):
        e = directory[32 * i:32 * i + 32]
        if e[0] == 0xE5:
            continue
        name = bytes(b & 0x7F for b in e[1:9]).decode("latin-1").rstrip()
        typ = bytes(b & 0x7F for b in e[9:12]).decode("latin-1").rstrip()
        if f"{name}.{typ}".upper() == want and e[0] == 0:
            extents.append((e[12], e[15], [b for b in e[16:32] if b]))
    if not extents:
        raise ImageError(f"{wanted}: not on the disc")
    out = bytearray()
    for _ex, records, blocks in sorted(extents):
        chunk = b"".join(block(b) for b in blocks)
        out += chunk[:records * 128]
    # An AMSDOS file starts with a 128-byte header whose checksum (the sum
    # of bytes 0-66) is at 67-68 and whose length is at 64-66. ScummVM's
    # DRILL.BIN keeps the header, so the file is cut to its length after it.
    if len(out) >= 128 and sum(out[:67]) == struct.unpack_from("<H", out, 67)[0]:
        length = out[64] | (out[65] << 8) | (out[66] << 16)
        return bytes(out[:128 + length])
    return bytes(out)
