# Lee un VRM 0.x (GLB) a mano: el importador glTF de Blender 4.5 falla con sus nodos
# (KeyError en create_object). Solo se necesitan posiciones, indices y la jerarquia de nodos.
import bpy, bmesh, sys, struct, json, statistics
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree
f = sys.argv[sys.argv.index("--")+1]
data = open(f,'rb').read()
magic, ver, length = struct.unpack_from('<III', data, 0)
off = 12; js = None; bin_ = None
while off < length:
    clen, ctype = struct.unpack_from('<II', data, off); off += 8
    chunk = data[off:off+clen]; off += clen
    if ctype == 0x4E4F534A: js = json.loads(chunk.decode('utf-8'))
    elif ctype == 0x004E4942: bin_ = chunk
CT = {5120:np.int8,5121:np.uint8,5122:np.int16,5123:np.uint16,5125:np.uint32,5126:np.float32}
NC = {'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}
def acc(i):
    a = js['accessors'][i]; bv = js['bufferViews'][a['bufferView']]
    dt = CT[a['componentType']]; n = NC[a['type']]
    start = bv.get('byteOffset',0) + a.get('byteOffset',0)
    stride = bv.get('byteStride', 0)
    if stride and stride != n*np.dtype(dt).itemsize:
        raw = np.frombuffer(bin_, dtype=np.uint8, count=stride*a['count'], offset=start)
        return np.lib.stride_tricks.as_strided(raw, (a['count'], n*np.dtype(dt).itemsize), (stride,1)).copy().view(dt).reshape(a['count'], n)
    return np.frombuffer(bin_, dtype=dt, count=a['count']*n, offset=start).reshape(a['count'], n)
nodes = js['nodes']; parent = {}
for i,n in enumerate(nodes):
    for c in n.get('children',[]): parent[c]=i
def world_t(i):
    t = np.array(nodes[i].get('translation',[0,0,0]), dtype=np.float64)
    if i in parent: t = t + world_t(parent[i])
    return t
gltf2bl = lambda p: (p[0], -p[2], p[1])   # Y-up -> Z-up
ojos = [(n['name'], gltf2bl(world_t(i))) for i,n in enumerate(nodes) if 'FaceEye' in n.get('name','')]
print("HUESOS ojo:", [(n, tuple(round(c,4) for c in p)) for n,p in ojos])
print("MESHES:", [(m.get('name'), len(m['primitives'])) for m in js['meshes']])
mallas = {}
bpy.ops.wm.read_factory_settings(use_empty=True)
for i,n in enumerate(nodes):
    if 'mesh' not in n: continue
    m = js['meshes'][n['mesh']]; name = n.get('name') or m.get('name')
    t = world_t(i)
    for k,p in enumerate(m['primitives']):
        P = acc(p['attributes']['POSITION']).astype(np.float64) + t
        I = acc(p['indices']).reshape(-1) if 'indices' in p else np.arange(len(P))
        F = I.reshape(-1,3)
        # solo se muestrean vertices usados
        me = bpy.data.meshes.new(f"{name}.{k}")
        me.from_pydata([gltf2bl(v) for v in P], [], [tuple(int(x) for x in tri) for tri in F])
        ob = bpy.data.objects.new(f"{name}.{k}", me); bpy.context.collection.objects.link(ob)
        mat = js['materials'][p['material']].get('name') if 'material' in p else None
        mallas.setdefault(name, []).append((ob, mat))
for name, lst in mallas.items():
    print("NODO", name, [(o.name, len(o.data.vertices), len(o.data.polygons), mat) for o,mat in lst])
def V_of(o): return [v.co.copy() for v in o.data.vertices if v.co.length > 0 or True]
def islas_de(o):
    bm=bmesh.new(); bm.from_mesh(o.data); bm.verts.ensure_lookup_table(); visto=set(); res=[]
    for v in bm.verts:
        if v.index in visto or not v.link_edges: continue
        pila=[v]; visto.add(v.index); comp=[]; caras=set()
        while pila:
            u=pila.pop(); comp.append(u.co.copy()); caras.update(fa.index for fa in u.link_faces)
            for e in u.link_edges:
                w=e.other_vert(u)
                if w.index not in visto: visto.add(w.index); pila.append(w)
        res.append((comp,len(caras)))
    bm.free(); return res
pelo = [o for n,l in mallas.items() if 'hair' in n.lower() for o,m in l]
piel = [o for n,l in mallas.items() if n.lower().startswith(('face','body','head')) and 'hair' not in n.lower() for o,m in l]
print("PELO obs:", [o.name for o in pelo]); print("PIEL obs:", [o.name for o in piel])
Vp=[v for o in piel for v in V_of(o)]
bm=bmesh.new()
for o in piel: bm.from_mesh(o.data)
bvh=BVHTree.FromBMesh(bm)
top=max(v.z for v in Vp); suelo=min(v.z for v in Vp)
eye_z = statistics.mean(p[2] for n,p in ojos) if ojos else None
# hacia donde mira la cara: en la franja de los ojos, el vertice mas lejano del eje x=0 en Y
cab=[v for v in Vp if v.z>eye_z-0.05]; C=sum(cab,Vector())/len(cab)
franja=[v for v in Vp if abs(v.x)<0.01 and eye_z-0.06<v.z<eye_z]
nariz_y = max(franja, key=lambda v: abs(v.y-C.y)).y
print(f"orientacion: centro y {C.y:.4f}, nariz y {nariz_y:.4f} -> la cara mira a {'-Y' if nariz_y<C.y else '+Y'}")
sg = 1 if nariz_y < C.y else -1   # sg=+1: y negativo = delante
b=[v for v in Vp if abs(v.z-eye_z)<0.004]; w_ojos=max(v.x for v in b)-min(v.x for v in b)
cara=[v for v in b if sg*(v.y-C.y)<-0.03]; w_cara=(max(v.x for v in cara)-min(v.x for v in cara)) if cara else 0
sk=[v for v in Vp if v.z>eye_z+0.04]; w_sk=max(v.x for v in sk)-min(v.x for v in sk)
mejor,chin=None,None; z=eye_z-0.03
while z>eye_z-0.2:
    bb=[v for v in Vp if abs(v.z-z)<0.0035]
    if bb:
        a=max(v.x for v in bb)-min(v.x for v in bb)
        if mejor is None or a<mejor: mejor,chin=a,z
    z-=0.003
HH=top-chin
print(f"PIEL: altura {top-suelo:.4f} m; coronilla {top:.4f}; ojos (hueso) {eye_z:.4f} = {(top-eye_z)*1000:.0f} mm bajo coronilla; menton {chin:.4f}; alto cabeza {HH*1000:.1f} mm; cabezas de alto {(top-suelo)/HH:.2f}; ojos al {(eye_z-chin)/HH*100:.1f}% del alto de cabeza")
print(f"PIEL: ancho en ojos (con orejas) {w_ojos*1000:.1f} mm; cara delante de orejas {w_cara*1000:.1f}; craneo sobre ojos+4cm {w_sk*1000:.1f}; ancho/alto {w_ojos/HH:.3f}; profundidad cabeza {(max(v.y for v in cab)-min(v.y for v in cab))*1000:.1f} mm")
def sep(Vs):
    ds=[]
    for v in Vs:
        loc,n,i,d=bvh.find_nearest(v); ds.append((1 if (v-loc).dot(loc-C)>=0 else -1)*d)
    ds.sort(); k=len(ds); return ds,(lambda q: ds[min(k-1,int(q*k))]*1000)
Vh=[]; nt=0; isl_all=[]
for o in pelo:
    isl=islas_de(o); isl_all+=isl; nt+=len(o.data.polygons); Vh+=[c for comp,t in isl for c in comp]
tam=sorted([(len(c),t) for c,t in isl_all], reverse=True)
print(f"PELO total: {len(Vh)} verts usados, {nt} tris, {len(isl_all)} islas; mayores (verts,tris) {tam[:10]}; mediana tris/isla {statistics.median(t for c,t in isl_all)}")
ds,p=sep(Vh)
print(f"PELO sep a piel mm: p05 {p(.05):.1f} p25 {p(.25):.1f} mediana {p(.5):.1f} p75 {p(.75):.1f} p95 {p(.95):.1f} max {ds[-1]*1000:.1f}; dentro {sum(1 for d in ds if d<0)}/{len(ds)}")
bov=[v for v in Vh if v.z>eye_z+0.06]; ds,p=sep(bov)
print(f"PELO boveda (z>ojos+6cm, {len(bov)} verts): p05 {p(.05):.1f} mediana {p(.5):.1f} p95 {p(.95):.1f} max {ds[-1]*1000:.1f}")
ztop=max(v.z for v in Vh); wmax=max(v.x for v in Vh)-min(v.x for v in Vh); prof=max(v.y for v in Vh)-min(v.y for v in Vh)
print(f"PELO coronilla sobre craneo {(ztop-top)*1000:.1f} mm = {(ztop-top)/HH*100:.1f}% alto cabeza; ancho max {wmax*1000:.1f} mm = {wmax/HH:.3f} alto cabeza; pelo/cabeza-en-ojos {wmax/w_ojos:.3f}; pelo/craneo {wmax/w_sk:.3f}; profundidad {prof*1000:.1f} mm")
fr=[v for v in Vh if sg*(v.y-C.y)<-0.04]
frente_pelo = min(sg*v.y for v in Vh); frente_piel = min(sg*v.y for v in Vp if v.z>chin)
print(f"PELO flequillo: punta {(eye_z-min(v.z for v in fr))*1000:+.1f} mm respecto a ojos (+ = por debajo); cejas no medibles (textura); frente del pelo sobresale {(frente_piel-frente_pelo)*1000:+.1f} mm respecto a la nariz; nuca del pelo sobresale {(max(sg*v.y for v in Vh)-max(sg*v.y for v in Vp if v.z>eye_z))*1000:+.1f} mm respecto a la nuca; punto mas bajo del pelo {(eye_z-min(v.z for v in Vh))*1000:+.1f} mm bajo ojos")
anchos=[]
for c,t in isl_all:
    if len(c)<4: continue
    dx=max(v.x for v in c)-min(v.x for v in c); dy=max(v.y for v in c)-min(v.y for v in c); dz=max(v.z for v in c)-min(v.z for v in c)
    anchos.append((round(min(dx,dy)*1000), round(max(dx,dy)*1000), round(dz*1000), len(c), t))
anchos.sort(key=lambda a:-a[3])
print("PELO islas mayores (ancho_min_xy, ancho_max_xy, alto mm, verts, tris):", anchos[:12])
print(f"PELO islas: mediana ancho_min {statistics.median(a[0] for a in anchos)} mm, ancho_max {statistics.median(a[1] for a in anchos)} mm, alto {statistics.median(a[2] for a in anchos)} mm")
# grosor de mechon: media de la separacion cara-a-cara dentro de una isla no se mide; en VRoid son laminas sin grosor (comprobar: islas con caras dobles?)
