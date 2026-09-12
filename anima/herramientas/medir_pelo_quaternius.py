# Segunda pasada: solo la piel del cuerpo como referencia (sin Icosphere, cejas ni ojos),
# cráneo sin orejas, y desglose por isla de Hair_SimpleParted.
import bpy, bmesh, json
from mathutils import Vector
from mathutils.bvhtree import BVHTree
D = "/Users/jesussolaz/Flipendo/game/referencias/quaternius-cc0/"
bpy.ops.wm.read_factory_settings(use_empty=True)
def importar(f):
    antes = set(bpy.data.objects); bpy.ops.import_scene.gltf(filepath=D + f)
    return [o for o in bpy.data.objects if o not in antes]
cuerpo = importar("Superhero_Male_FullBody.gltf")
piel = next(o for o in cuerpo if o.name == "SuperHero_Male")
ojos = next(o for o in cuerpo if o.name == "Eyes")
M = piel.matrix_world
V = [M @ v.co for v in piel.data.vertices]
top = max(v.z for v in V); suelo = min(v.z for v in V)
Me = ojos.matrix_world; Vo = [Me @ v.co for v in ojos.data.vertices]
eye_z = (max(v.z for v in Vo) + min(v.z for v in Vo)) / 2
print(f"CUERPO altura {top-suelo:.4f} m; coronilla z={top:.4f}; linea de ojos (centro bbox de la malla Eyes) z={eye_z:.4f} -> {top-eye_z:.4f} bajo coronilla")
# orejas: en la línea de ojos, los vértices de |x| extremo; miro su y
b = [v for v in V if abs(v.z - eye_z) < 0.004]
ext = sorted(b, key=lambda v: -abs(v.x))[:6]
print("  vertices mas externos en la linea de ojos (x, y):", [(round(v.x,4), round(v.y,4)) for v in ext])
# ancho de cara (delante de las orejas: y < -0.03) y de cráneo (todo) en la línea de ojos
def ancho(sel): return (max(v.x for v in sel) - min(v.x for v in sel)) if sel else 0
cara = [v for v in b if v.y < -0.03]
print(f"  ancho total en linea de ojos (con orejas) {ancho(b):.4f}; ancho de cara delante de orejas (y<-0.03) {ancho(cara):.4f}")
# cráneo sin orejas: anchura máxima por encima de la línea de ojos + 3 cm (las orejas terminan ahí)
for dz in (0.03, 0.04, 0.05):
    sel = [v for v in V if v.z > eye_z + dz and v.z < top]
    print(f"  ancho max del craneo por encima de ojos+{dz*100:.0f}cm: {ancho(sel):.4f}; profundidad Y {max(v.y for v in sel)-min(v.y for v in sel):.4f}")
# menton: minimo de anchura bajo ojos (criterio medir_personaje.py)
mejor, chin = None, None; z = eye_z - 0.03
while z > eye_z - 0.2:
    a = ancho([v for v in V if abs(v.z - z) < 0.0035])
    if a > 0 and (mejor is None or a < mejor): mejor, chin = a, z
    z -= 0.003
print(f"  menton z={chin:.4f}; alto de cabeza {top-chin:.4f}; cabezas de alto {(top-suelo)/(top-chin):.2f}; ojos al {(eye_z-chin)/(top-chin)*100:.1f}% del alto de cabeza")
HH = top - chin
bm = bmesh.new(); bm.from_mesh(piel.data); bm.transform(M); bvh = BVHTree.FromBMesh(bm)
def sep(Vs):
    ds = []
    for v in Vs:
        loc, nrm, idx, dist = bvh.find_nearest(v)
        ds.append((1 if (v-loc).dot(nrm) >= 0 else -1) * dist)
    ds.sort(); n = len(ds)
    return ds, (lambda p: ds[min(n-1, int(p*n))])
for f in ["Hair_SimpleParted", "Hair_Buzzed"]:
    obs = importar(f + ".gltf"); o = next(x for x in obs if x.type == 'MESH')
    bmh = bmesh.new(); bmh.from_mesh(o.data); bmh.transform(o.matrix_world); bmh.verts.ensure_lookup_table()
    visto = set(); islas = []
    for v in bmh.verts:
        if v.index in visto: continue
        pila = [v]; visto.add(v.index); comp = []
        while pila:
            u = pila.pop(); comp.append(u)
            for e in u.link_edges:
                w = e.other_vert(u)
                if w.index not in visto: visto.add(w.index); pila.append(w)
        islas.append(comp)
    Vh = [v.co.copy() for v in bmh.verts]
    ds, pct = sep(Vh)
    print(f"PELO {f}: {len(bmh.verts)} verts, {len(bmh.faces)} tris (glTF llega triangulado), {len(islas)} islas")
    print(f"  separacion a la piel (mm): p05 {pct(.05)*1000:.1f} p25 {pct(.25)*1000:.1f} mediana {pct(.5)*1000:.1f} p75 {pct(.75)*1000:.1f} p95 {pct(.95)*1000:.1f} max {ds[-1]*1000:.1f}; dentro de la piel {sum(1 for d in ds if d<0)}/{len(ds)}")
    ztop = max(v.z for v in Vh)
    print(f"  coronilla del pelo sobre la del craneo: {(ztop-top)*1000:.1f} mm = {(ztop-top)/HH*100:.1f}% del alto de cabeza")
    wmax = ancho(Vh); print(f"  ancho max del pelo {wmax*1000:.1f} mm = {wmax/HH:.3f} del alto de cabeza; vs craneo sin orejas (ojos+4cm) ratio {wmax/ancho([v for v in V if v.z > eye_z+0.04]):.3f}; vs ancho con orejas {wmax/ancho(b):.3f}")
    prof = max(v.y for v in Vh) - min(v.y for v in Vh); print(f"  profundidad del pelo {prof*1000:.1f} mm; frente del pelo y={min(v.y for v in Vh):.4f} vs frente de la piel (nariz) y={min(v.y for v in V if v.z>chin):.4f}; nuca del pelo y={max(v.y for v in Vh):.4f} vs nuca de la piel y={max(v.y for v in V if v.z>eye_z):.4f}")
    for i, comp in enumerate(sorted(islas, key=len, reverse=True)):
        cs = [u.co for u in comp]
        caras = {fa.index for u in comp for fa in u.link_faces}
        mn = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs))); mx = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
        di, pi = sep(cs)
        print(f"  isla {i}: {len(comp)} verts, {len(caras)} tris; bbox x[{mn.x:.3f},{mx.x:.3f}] y[{mn.y:.3f},{mx.y:.3f}] z[{mn.z:.3f},{mx.z:.3f}]; dims {[round(c*1000) for c in (mx-mn)]} mm; sep mediana {pi(.5)*1000:.1f} p95 {pi(.95)*1000:.1f} mm; punto mas bajo {(eye_z-mn.z)*1000:+.1f} mm respecto a ojos")
    # flequillo: vértices frontales (y < -0.04) — largo desde la línea del pelo hasta la punta
    front = [v for v in Vh if v.y < -0.04]
    if front:
        print(f"  frente (y<-4cm): z max {max(v.z for v in front):.4f}, z min {min(v.z for v in front):.4f} -> punta del flequillo {(eye_z-min(v.z for v in front))*1000:+.1f} mm respecto a la linea de ojos; cejas z {1.6949:.4f}-{1.7255:.4f}")
    bmh.free()
    for x in obs: bpy.data.objects.remove(x)
