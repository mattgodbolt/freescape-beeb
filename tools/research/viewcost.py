# Estimate per-view work for a Freescape area: objects inside the view frustum and
# front-facing, non-transparent faces, from each entrance. No occlusion (the original
# painter's renderer draws every surviving face). Parameters are assumptions (see report).
import sys, json, math, statistics
db = json.load(open(sys.argv[1]))
HFOV = float(sys.argv[2]) if len(sys.argv) > 2 else 75.0
ASPECT = float(sys.argv[3]) if len(sys.argv) > 3 else 2.0   # view width/height in pixels (Driller ZX 208x104)
EYE = 1.5  # eye height above feet in object units at scale 1 (ScummVM changePlayerHeight index 1)
th = math.tan(math.radians(HFOV / 2)); tv = th / ASPECT
def frustum_planes(cam, yaw_deg):
    # yaw 0 looks along +Z, yaw 90 along +X (Freescape convention inferred from CM2 movement code)
    y = math.radians(yaw_deg)
    f = (math.sin(y), 0.0, math.cos(y)); r = (math.cos(y), 0.0, -math.sin(y)); u = (0.0, 1.0, 0.0)
    def plane(n):
        return (n, -sum(n[i]*cam[i] for i in range(3)))
    P = [plane(f)]
    P.append(plane(tuple(f[i]*th + r[i] for i in range(3))))
    P.append(plane(tuple(f[i]*th - r[i] for i in range(3))))
    P.append(plane(tuple(f[i]*tv + u[i] for i in range(3))))
    P.append(plane(tuple(f[i]*tv - u[i] for i in range(3))))
    return P
def aabb_in(P, mn, mx):
    for n, d in P:
        # positive vertex
        p = [mx[i] if n[i] >= 0 else mn[i] for i in range(3)]
        if sum(n[i]*p[i] for i in range(3)) + d < 0: return False
    return True
def faces_facing(o, cam):
    mn = o['pos']; mx = [o['pos'][i] + o['size'][i] for i in range(3)]
    t = o['t']; cols = o.get('colours', [])
    if t == 1 or 4 <= t <= 9:
        n = 0; nv = 0
        # colour order: -X, +X, -Y, +Y, -Z, +Z (ScummVM renderCube)
        for axis in range(3):
            if cam[axis] < mn[axis] and cols[2*axis] != 0: n += 1
            if cam[axis] > mx[axis] and cols[2*axis+1] != 0: n += 1
        return n, 4 * n
    if t == 3 or 10 <= t <= 14:
        if not any(cols): return 0, 0
        nverts = 4 if t == 3 else (t - 8)
        if t == 10: return 1, 2
        return 1, nverts
    return 0, 0
rows = []
for a in db['areas']:
    sc = a['scale']
    ents = [o for o in a['objects'] if o['t'] == 0]
    geo = [o for o in a['objects'] if o['t'] not in (0, 2, 15) and not (o['flags'] & 0x80)]
    for e in ents:
        cam = [e["pos"][0] + 0.5, e["pos"][1] + (2 * sc - 0.5), e["pos"][2] + 0.5]
        yaw = 5 * e['rot5'][1]
        P = frustum_planes(cam, yaw)
        inview = []; faces = 0; verts = 0
        for o in geo:
            mn = o['pos']; mx = [o['pos'][i] + o['size'][i] for i in range(3)]
            # give planar objects a tiny thickness for the test
            mx = [mx[i] if mx[i] > mn[i] else mn[i] + 0.01 for i in range(3)]
            if aabb_in(P, mn, mx):
                f, v = faces_facing(o, cam)
                if f:
                    inview.append(o['id']); faces += f; verts += v
        rows.append((a['id'], a['name'].strip(), e['id'], yaw, len(geo), len(inview), faces, verts))
for r in rows:
    print('area %3d %-13s entrance %3d yaw %3d: visible-candidate geo %2d, in frustum & drawn %2d objects, %2d faces, ~%3d polygon vertices' % r)
o = [r[5] for r in rows]; f = [r[6] for r in rows]; v = [r[7] for r in rows]
print('entrance views:', len(rows))
print('objects drawn: min %d median %s max %d mean %.1f' % (min(o), statistics.median(o), max(o), statistics.mean(o)))
print('faces drawn:   min %d median %s max %d mean %.1f' % (min(f), statistics.median(f), max(f), statistics.mean(f)))
print('vertices:      min %d median %s max %d mean %.1f' % (min(v), statistics.median(v), max(v), statistics.mean(v)))
