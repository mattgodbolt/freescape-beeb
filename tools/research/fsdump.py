# Dump a Freescape 8-bit (Driller-era) database, following ScummVM's load8bitBinary/load8bitArea/load8bitObject.
import sys, json, struct, collections, statistics
TYPES = {0:'entrance',1:'cube',2:'sensor',3:'rect',4:'pyrE',5:'pyrW',6:'pyrU',7:'pyrD',8:'pyrN',9:'pyrS',
         10:'line',11:'tri',12:'quad',13:'pent',14:'hex',15:'group'}
def ncolours(t):
    if t in (0, 2, 15): return 0
    if t == 1 or 4 <= t <= 9: return 6
    return 2
def nords(t):
    if 4 <= t <= 9: return 4
    if 10 <= t <= 14: return 3 * (2 + t - 10)
    return 0
def parse_object(d, p, typemask=0x1f):
    raw = d[p]; t = raw & typemask
    o = {'raw': raw, 'type': TYPES.get(t, 't%d' % t), 't': t, 'flags': raw & 0xe0}
    if t == 15:
        ids = list(d[p+1:p+4]); oid = d[p+7]; ln = d[p+8]
        o.update(id=oid, len=ln, group_ids=ids, pos=None, size=None)
        return o, p + ln
    o['pos'] = list(d[p+1:p+4]); o['size'] = list(d[p+4:p+7]); o['id'] = d[p+7]; ln = d[p+8]; o['len'] = ln
    q = p + 9; end = p + ln
    if t == 0:
        o['rot5'] = o['size']; o['fcl'] = end - q
    elif t == 2:
        o['sensor'] = {'colour': d[q] & 0xf, 'interval': d[q+1], 'range': d[q+2] | (d[q+3] << 8), 'axis': d[q+4]}
        o['fcl'] = end - (q + 5)
    else:
        cols = []
        for i in range(ncolours(t) // 2):
            b = d[q]; q += 1; cols += [b & 0xf, b >> 4]
        o['colours'] = cols
        k = nords(t); o['ords'] = list(d[q:q+k]); q += k
        o['fcl'] = end - q
    return o, end
def parse_area(d, p, typemask=0x1f, variant='driller'):
    base = p
    a = {'flags': d[p], 'nobj': d[p+1], 'id': d[p+2], 'cptr': d[p+3] | (d[p+4] << 8), 'scale': d[p+5],
         'palette': list(d[p+6:p+10])}
    q = p + 10
    if variant == 'driller':
        a['gas'] = list(d[q:q+3]); q += 3
    else:
        a['name3'] = d[q:q+3].decode('latin-1'); q += 3
    a['name'] = d[q:q+12].decode('latin-1'); q += 12
    objs = []
    for i in range(a['nobj']):
        o, q = parse_object(d, q, typemask); objs.append(o)
    a['objects'] = objs
    a['objects_end_ok'] = (q == base + a['cptr'])
    r = base + a['cptr']; nc = d[r]; r += 1; conds = []
    for i in range(nc):
        ln = d[r]; conds.append(ln); r += 1 + ln
    a['area_conditions'] = conds
    a['bytes'] = r - base
    return a
def parse_db(d, off, typemask=0x1f, variant='driller'):
    db = {'n_areas': d[off], 'db_size': d[off+1] | (d[off+2] << 8), 'start_area': d[off+3], 'start_entrance': d[off+4]}
    db['shades'] = [list(d[off+0xa+4*i: off+0xe+4*i]) for i in range(15)]
    gbct = d[off+0x48] | (d[off+0x49] << 8)
    g = off + gbct; ng = d[g]; g += 1; gl = []
    for i in range(ng):
        ln = d[g]; gl.append(ln); g += 1 + ln
    db['global_conditions'] = gl
    db['timer'] = d[off+0xb4:off+0xbc].decode('latin-1')
    db['init_step_index'] = d[off+0xc2]; db['init_angle_index'] = d[off+0xc3]
    offs = [d[off+0xc8+2*i] | (d[off+0xc9+2*i] << 8) for i in range(db['n_areas'])]
    db['areas'] = [parse_area(d, off + o, typemask, variant) for o in offs]
    return db
if __name__ == '__main__':
    d = open(sys.argv[1], 'rb').read()
    off = int(sys.argv[2], 16)
    db = parse_db(d, off)
    gofs = int(sys.argv[3], 16) if len(sys.argv) > 3 else None
    if gofs is not None:
        q = gofs; gobj = []
        for i in range(int(sys.argv[4])):
            o, q = parse_object(d, q); gobj.append(o)
        db['global_objects'] = gobj
    json.dump(db, open(sys.argv[5] if len(sys.argv) > 5 else '/dev/stdout', 'w'), indent=None)
