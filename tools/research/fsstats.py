import sys, json, collections, statistics
db = json.load(open(sys.argv[1]))
GEO = lambda o: o['t'] not in (0, 2, 15)
alltypes = collections.Counter(); rows = []
facecount = collections.Counter()
def nfaces(o):
    # non-transparent faces (colour index != 0); planar objects: count sides with colour
    return sum(1 for c in o.get('colours', []) if c != 0)
for a in db['areas']:
    objs = a['objects']
    tc = collections.Counter(o['type'] for o in objs)
    alltypes.update(tc)
    geo = [o for o in objs if GEO(o)]
    ents = [o for o in objs if o['t'] == 0]
    ext = [0, 0, 0]
    for o in geo:
        for i in range(3): ext[i] = max(ext[i], o['pos'][i] + o['size'][i])
    faces = sum(nfaces(o) for o in geo)
    fcl_objs = sum(1 for o in objs if o.get('fcl', 0) > 0)
    inv = sum(1 for o in objs if o['flags'] & 0x80)
    rows.append((a['id'], a['name'].strip(), a['nobj'], len(geo), len(ents), faces, a['scale'], ext, fcl_objs, inv, dict(tc)))
for r in rows:
    print('area %3d %-13s nobj=%2d geo=%2d ent=%2d faces=%3d scale=%d extent=%s fclobjs=%2d initInvis=%2d %s' % r)
g = [r[3] for r in rows]; n = [r[2] for r in rows]; f = [r[5] for r in rows]
print('areas', len(rows))
print('records/area min %d median %s max %d mean %.1f total %d' % (min(n), statistics.median(n), max(n), statistics.mean(n), sum(n)))
print('geometric/area min %d median %s max %d mean %.1f total %d' % (min(g), statistics.median(g), max(g), statistics.mean(g), sum(g)))
print('coloured faces/area min %d median %s max %d' % (min(f), statistics.median(f), max(f)))
print('types', dict(alltypes))
print('scales', collections.Counter(r[6] for r in rows))
# coordinate ranges
mx = [0,0,0]
for a in db['areas']:
    for o in a['objects']:
        if o['pos'] is None: continue
        for i in range(3):
            if o['t'] != 0: mx[i] = max(mx[i], o['pos'][i] + o['size'][i])
print('max geometric extent over all areas (object units):', mx)
# size of objects distribution
sizes = [max(o['size']) for a in db['areas'] for o in a['objects'] if GEO(o)]
print('largest object dimension: median', statistics.median(sizes), 'max', max(sizes))
# flat objects (a zero size)
flat = sum(1 for a in db['areas'] for o in a['objects'] if GEO(o) and 0 in o['size'])
print('geometric objects with a zero dimension (planar):', flat, 'of', len(sizes))
print('db bytes', db['db_size'], 'area bytes total', sum(a['bytes'] for a in db['areas']))
