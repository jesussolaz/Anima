# ÁNIMA — El Molino de La Mancha (pieza héroe)
#
# Herramienta de EDITOR (bpy). El .blend resultante NO contiene Python:
# ni text blocks, ni logic bricks, ni controladores. Doctrina C++ intacta.
#
#   Flipendo --background --factory-startup --python gen_molino.py
#
# Salida: ~/Flipendo/game/anima/Molino.blend
#
# Todo se construye con geometría real: perfiles torneados con irregularidad,
# sillares individuales, ~600 tejas colocadas una a una, celosía de aspas con
# travesaños y lona con vuelo, herrajes con clavos. El desgaste va pintado en
# el atributo de color "Col" y lo multiplica cada material.

import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix, noise

random.seed(1605)

OUT_DIR = os.path.expanduser("~/Flipendo/game/anima")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_BLEND = os.path.join(OUT_DIR, "Molino.blend")

CH = 0.014  # chaflán por defecto: lo que hace que una arista atrape la luz

# índices de material (el orden importa: se asignan por face.material_index)
MAT_CAL, MAT_TEJA, MAT_MAD, MAT_MADOSC, MAT_PIEDRA, MAT_LONA, MAT_HIERRO, \
    MAT_TIERRA, MAT_HIERBA, MAT_ANIMA, MAT_NEGRO = range(11)


def clamp01(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, t):
    return a + (b - a) * t


# ----------------------------------------------------------------- geometría


def rect_ring(w, d, ch):
    """Anillo rectangular con las 4 esquinas achaflanadas (octógono)."""
    ch = max(0.0, min(ch, w * 0.45, d * 0.45))
    hw, hd = w / 2.0, d / 2.0
    return [(hw, hd - ch), (hw - ch, hd), (-(hw - ch), hd), (-hw, hd - ch),
            (-hw, -(hd - ch)), (-(hw - ch), -hd), (hw - ch, -hd), (hw, -(hd - ch))]


def loft(rings, cap_start=True, cap_end=True):
    """Une anillos consecutivos (mismo número de puntos) en un tubo."""
    V, F = [], []
    offs = []
    for r in rings:
        offs.append(len(V))
        V.extend(r)
    n = len(rings[0])
    for ri in range(len(rings) - 1):
        a, b = offs[ri], offs[ri + 1]
        for i in range(n):
            j = (i + 1) % n
            F.append([a + i, a + j, b + j, b + i])
    if cap_start:
        F.append(list(range(offs[0], offs[0] + n))[::-1])
    if cap_end:
        F.append(list(range(offs[-1], offs[-1] + n)))
    return V, F


def beam(w0, d0, w1, d1, L, ch=CH):
    """Viga achaflanada en las 4 aristas largas y en los dos extremos."""
    c0 = min(ch, w0 * 0.4, d0 * 0.4)
    c1 = min(ch, w1 * 0.4, d1 * 0.4)
    rings = [
        [(x, y, 0.0) for x, y in rect_ring(w0 - 2 * c0, d0 - 2 * c0, c0 * 0.5)],
        [(x, y, c0) for x, y in rect_ring(w0, d0, c0)],
        [(x, y, L - c1) for x, y in rect_ring(w1, d1, c1)],
        [(x, y, L) for x, y in rect_ring(w1 - 2 * c1, d1 - 2 * c1, c1 * 0.5)],
    ]
    return loft(rings)


def cbox(sx, sy, sz, ch=CH):
    """Caja achaflanada CENTRADA en el origen (sx,sy,sz = lados completos).
    `beam` crece de z=0 a z=L, así que hay que bajarla media altura."""
    V, F = beam(sx, sy, sx, sy, sz, ch)
    return [(x, y, z - sz / 2.0) for (x, y, z) in V], F


def lathe(profile, segs=48, wobble=0.0, seed=0.0, cap_bottom=False, cap_top=False):
    """Superficie de revolución. `profile` = [(radio, z), ...] de abajo arriba.
    `wobble` desplaza el radio con ruido 3D: el encalado a mano nunca es un cilindro."""
    V, F = [], []
    n = len(profile)
    for si in range(segs):
        a = si / segs * 2.0 * math.pi
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in profile:
            rr = r
            if wobble:
                rr += wobble * noise.noise(Vector((ca * r * 0.55, sa * r * 0.55,
                                                   z * 0.5 + seed)))
                rr += wobble * 0.4 * noise.noise(Vector((ca * r * 2.1, sa * r * 2.1,
                                                         z * 1.9 + seed)))
            V.append((ca * rr, sa * rr, z))

    def vid(si, pi):
        return (si % segs) * n + pi

    for si in range(segs):
        for pi in range(n - 1):
            F.append([vid(si, pi), vid(si + 1, pi), vid(si + 1, pi + 1), vid(si, pi + 1)])
    if cap_bottom:
        F.append([vid(si, 0) for si in range(segs)][::-1])
    if cap_top:
        F.append([vid(si, n - 1) for si in range(segs)])
    return V, F


_ICO = {}


def ico(subdiv=1):
    if subdiv in _ICO:
        return _ICO[subdiv]
    tb = bmesh.new()
    bmesh.ops.create_icosphere(tb, subdivisions=subdiv, radius=1.0)
    tb.verts.index_update()
    V = [tuple(v.co) for v in tb.verts]
    F = [[v.index for v in f.verts] for f in tb.faces]
    tb.free()
    _ICO[subdiv] = (V, F)
    return V, F


def tile(width=0.335, length=0.44, thick=0.022, arc=math.radians(118), segs=5,
         taper=0.87):
    """Teja curva. Abomba hacia +Z, corre hacia +Y, ancho en X.
    Los bordes del arco quedan en z=0 para apoyar en el faldón."""
    R = (width / 2.0) / math.sin(arc / 2.0)
    cz = -R * math.cos(arc / 2.0)
    V = []
    for (yy, sc) in ((0.0, 1.0), (length, taper)):
        for rr in (R - thick, R):
            for i in range(segs + 1):
                a = -arc / 2.0 + arc * i / segs
                V.append((math.sin(a) * rr * sc, yy, cz + math.cos(a) * rr))
    n = segs + 1

    def vid(j, k, i):
        return j * 2 * n + k * n + i

    F = []
    for i in range(segs):
        F.append([vid(0, 1, i), vid(0, 1, i + 1), vid(1, 1, i + 1), vid(1, 1, i)])
        F.append([vid(0, 0, i), vid(1, 0, i), vid(1, 0, i + 1), vid(0, 0, i + 1)])
        F.append([vid(0, 0, i), vid(0, 0, i + 1), vid(0, 1, i + 1), vid(0, 1, i)])
        F.append([vid(1, 0, i), vid(1, 1, i), vid(1, 1, i + 1), vid(1, 0, i + 1)])
    for i in (0, segs):
        F.append([vid(0, 0, i), vid(0, 1, i), vid(1, 1, i), vid(1, 0, i)])
    return V, F


def blade(h=0.34, w=0.024, lean=0.15, segs=4):
    """Brizna de hierba: tira que se estrecha y se vence."""
    V, F = [], []
    for i in range(segs + 1):
        t = i / segs
        ww = w * (1.0 - t * 0.93) ** 0.75
        V.append((-ww, lean * t * t, h * t))
        V.append((ww, lean * t * t, h * t))
    for i in range(segs):
        F.append([2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2])
    return V, F


def sagging_grid(w, h, nx, ny, sag, ripple=0.0, seed=0.0):
    """Paño de lona: rejilla con vuelo (más panza en el centro) y arrugas."""
    V, F = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            x = (u - 0.5) * w
            y = (v - 0.5) * h
            z = math.sin(u * math.pi) * math.sin(v * math.pi) * sag
            if ripple:
                z += ripple * noise.noise(Vector((u * 5.0, v * 5.0, seed)))
            V.append((x, y, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            F.append([a, a + 1, a + nx + 2, a + nx + 1])
    return V, F


def jitter(V, amt, seed=0.0):
    out = []
    for (x, y, z) in V:
        out.append((x + random.uniform(-amt, amt),
                    y + random.uniform(-amt, amt),
                    z + random.uniform(-amt, amt)))
    return out


def frame_matrix(origin, ex, ey, ez):
    """Matriz cuyas columnas son los ejes dados."""
    m = Matrix(((ex.x, ey.x, ez.x, origin.x),
                (ex.y, ey.y, ez.y, origin.y),
                (ex.z, ey.z, ez.z, origin.z),
                (0.0, 0.0, 0.0, 1.0)))
    return m


# ----------------------------------------------------------------- desgaste

STAINS = []   # (x, y, z_alféizar, ancho) — reguero de suciedad bajo cada hueco


def weather(co):
    """Multiplicador de color por vértice: humedad en la base, regueros bajo los
    huecos, moteado del encalado. Es lo que separa un objeto de un plástico."""
    x, y, z = co
    v = 1.0
    # humedad y salpicadura de barro en el arranque del muro
    v -= 0.42 * clamp01(1.0 - (z - 0.95) / 1.9) ** 1.6
    # moteado grande + poro fino
    v *= 0.90 + 0.14 * noise.noise(Vector((x * 0.7, y * 0.7, z * 0.7)))
    v *= 0.95 + 0.09 * noise.noise(Vector((x * 3.1, y * 3.1, z * 3.1)))
    # aguas verticales: la cal escurre, no mancha en manchas redondas
    v *= 0.93 + 0.11 * noise.noise(Vector((x * 2.6, y * 2.6, z * 0.28)))
    # regueros verticales bajo alféizares
    for (sx, sy, sz, sw) in STAINS:
        if z < sz:
            d = math.hypot(x - sx, y - sy)
            if d < sw:
                fall = clamp01(1.0 - (sz - z) / 2.6)
                side = clamp01(1.0 - d / sw)
                streak = 0.55 + 0.45 * math.sin((x * 9.0 + y * 9.0))
                v -= 0.30 * fall * side * streak
    return (clamp01(v),) * 3


def flat(c):
    return lambda co: (c, c, c)


# ----------------------------------------------------------------- constructor


class Build:
    def __init__(self):
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.color.new("Col")

    def add(self, V, F, mat=0, mtx=None, smooth=False, tint=weather):
        bv = []
        for v in V:
            co = Vector(v)
            if mtx is not None:
                co = mtx @ co
            bv.append(self.bm.verts.new(co))
        for f in F:
            try:
                face = self.bm.faces.new([bv[i] for i in f])
            except ValueError:
                continue
            face.material_index = mat
            face.smooth = smooth
            for lp in face.loops:
                c = tint(lp.vert.co) if callable(tint) else tint
                lp[self.col] = (c[0], c[1], c[2], 1.0)

    def finish(self, name, mats):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(ob)
        for m in mats:
            me.materials.append(m)
        return ob


# ----------------------------------------------------------------- materiales


def make_mat(name, color, rough=0.9, mottle=0.0, mottle_scale=6.0,
             emit=None, emit_str=0.0, metallic=0.0):
    """Principled con el atributo de color "Col" multiplicando la base
    y, opcionalmente, moteado procedural en color y aspereza."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic

    base = nt.nodes.new("ShaderNodeRGB")
    base.outputs[0].default_value = (*color, 1.0)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(base.outputs[0], mix.inputs["A"])
    nt.links.new(attr.outputs["Color"], mix.inputs["B"])
    out = mix.outputs["Result"]

    if mottle > 0.0:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = mottle_scale
        tex.inputs["Detail"].default_value = 6.0
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.inputs["To Min"].default_value = 1.0 - mottle
        rng.inputs["To Max"].default_value = 1.0 + mottle
        mix2 = nt.nodes.new("ShaderNodeMix")
        mix2.data_type = 'RGBA'
        mix2.blend_type = 'MULTIPLY'
        mix2.inputs["Factor"].default_value = 1.0
        nt.links.new(out, mix2.inputs["A"])
        nt.links.new(tex.outputs["Fac"], rng.inputs["Value"])
        nt.links.new(rng.outputs["Result"], mix2.inputs["B"])
        out = mix2.outputs["Result"]
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = max(0.05, rough - 0.18)
        rr.inputs["To Max"].default_value = min(1.0, rough + 0.10)
        nt.links.new(tex.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])

    nt.links.new(out, bsdf.inputs["Base Color"])
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_str
    m.diffuse_color = (*color, 1.0)
    return m


# ----------------------------------------------------------------- escena
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
sc = bpy.context.scene
sc.name = "Molino"

MATS = [
    make_mat("M_Cal", (0.86, 0.80, 0.68), 0.90, mottle=0.13, mottle_scale=3.2),
    make_mat("M_Teja", (0.55, 0.24, 0.13), 0.86, mottle=0.16, mottle_scale=9.0),
    make_mat("M_Madera", (0.40, 0.26, 0.14), 0.82, mottle=0.13, mottle_scale=14.0),
    make_mat("M_MaderaOscura", (0.17, 0.11, 0.065), 0.84, mottle=0.12, mottle_scale=12.0),
    make_mat("M_Piedra", (0.50, 0.46, 0.40), 0.93, mottle=0.15, mottle_scale=7.0),
    make_mat("M_Lona", (0.80, 0.70, 0.52), 0.82, mottle=0.10, mottle_scale=9.0),
    make_mat("M_Hierro", (0.075, 0.070, 0.075), 0.52, mottle=0.20, mottle_scale=16.0,
             metallic=0.85),
    make_mat("M_Tierra", (0.62, 0.50, 0.33), 0.95, mottle=0.10, mottle_scale=3.0),
    make_mat("M_Hierba", (0.44, 0.40, 0.17), 0.92, mottle=0.14, mottle_scale=5.0),
    make_mat("M_Anima", (1.0, 0.72, 0.24), 0.4, emit=(1.0, 0.58, 0.14), emit_str=1.7),
    make_mat("M_Negro", (0.012, 0.010, 0.014), 0.95),
]

# ----------------------------------------------------------------- perfil torre
Z_PLINTH = 0.98          # coronación del zócalo de piedra
Z_EAVE = 8.30            # arranque de la cornisa
PROFILE = [(3.62, 0.86), (3.58, 1.60), (3.50, 3.00), (3.40, 4.60),
           (3.30, 6.20), (3.19, 7.50), (3.13, Z_EAVE)]


def tower_r(z):
    if z <= PROFILE[0][1]:
        return PROFILE[0][0]
    for i in range(len(PROFILE) - 1):
        r0, z0 = PROFILE[i]
        r1, z1 = PROFILE[i + 1]
        if z <= z1:
            return lerp(r0, r1, (z - z0) / (z1 - z0))
    return PROFILE[-1][0]


def on_wall(ang, z, out=0.0):
    """Punto sobre el muro y marco local diestro:
    X = a lo ancho del muro, Y = hacia fuera (profundidad), Z = arriba (altura)."""
    ca, sa = math.cos(ang), math.sin(ang)
    r = tower_r(z) + out
    p = Vector((ca * r, sa * r, z))
    ex = Vector((sa, -ca, 0.0))       # tangente
    ey = Vector((ca, sa, 0.0))        # normal saliente
    ez = Vector((0.0, 0.0, 1.0))      # arriba
    return p, frame_matrix(p, ex, ey, ez)


# huecos: (ángulo, altura del centro) — siguen la escalera interior
DOOR_ANG = -math.pi / 2.0                       # la puerta mira a -Y
WINDOWS = [(-math.pi / 2 + 0.62, 4.15), (-math.pi / 2 + 2.05, 6.05),
           (-math.pi / 2 - 1.25, 5.10)]
for (wa, wz) in WINDOWS:
    p, _ = on_wall(wa, wz - 0.52)
    STAINS.append((p.x, p.y, p.z, 0.62))
p, _ = on_wall(DOOR_ANG, 3.05)
STAINS.append((p.x, p.y, p.z, 0.95))

# ----------------------------------------------------------------- TORRE
print("[MOLINO] torre, zócalo, huecos…")
T = Build()

# — zócalo: dos hiladas de sillares irregulares, no un cilindro
for course, (cz, ch_h, nblk, rad) in enumerate((
        (0.02, 0.34, 42, 3.78), (0.36, 0.32, 40, 3.74), (0.68, 0.30, 38, 3.70))):
    for i in range(nblk):
        a = (i + 0.5 * course) / nblk * 2 * math.pi + random.uniform(-0.012, 0.012)
        w = 2 * math.pi * rad / nblk * random.uniform(0.82, 0.96)
        h = ch_h * random.uniform(0.86, 1.0)
        d = random.uniform(0.42, 0.62)
        V, F = cbox(w, d, h, ch=0.018)
        V = jitter(V, 0.012)
        ca, sa = math.cos(a), math.sin(a)
        rr = rad + random.uniform(-0.04, 0.02)
        mtx = frame_matrix(Vector((ca * rr, sa * rr, cz + h / 2)),
                           Vector((sa, -ca, 0)), Vector((ca, sa, 0)), Vector((0, 0, 1)))
        T.add(V, F, MAT_PIEDRA, mtx)

# — fuste encalado, torneado con irregularidad de mano
V, F = lathe(PROFILE, segs=72, wobble=0.048, seed=3.1)
T.add(V, F, MAT_CAL, smooth=True)

# — cornisa volada con dentículos
V, F = lathe([(3.13, Z_EAVE), (3.30, Z_EAVE + 0.10), (3.34, Z_EAVE + 0.22),
              (3.20, Z_EAVE + 0.30)], segs=64, cap_top=False)
T.add(V, F, MAT_CAL, smooth=True)
for i in range(44):
    a = i / 44 * 2 * math.pi
    ca, sa = math.cos(a), math.sin(a)
    V, F = cbox(0.20, 0.26, 0.13, ch=0.012)
    mtx = frame_matrix(Vector((ca * 3.31, sa * 3.31, Z_EAVE - 0.02)),
                       Vector((-sa, ca, 0)), Vector((ca, sa, 0)), Vector((0, 0, 1)))
    T.add(V, F, MAT_PIEDRA, mtx)

# — desconchones: la cal se ha caído a placas y asoma la mampostería, casi a haces
for i in range(11):
    a = random.uniform(0, 2 * math.pi)
    z = random.uniform(1.5, 7.2)
    _, mtx = on_wall(a, z, out=-0.075)
    for _ in range(random.randint(7, 13)):
        V, F = cbox(random.uniform(0.26, 0.54), 0.15, random.uniform(0.15, 0.26),
                    ch=0.020)
        V = jitter(V, 0.016)
        off = Matrix.Translation((random.uniform(-0.52, 0.52), 0.0,
                                  random.uniform(-0.44, 0.44)))
        T.add(V, F, MAT_PIEDRA, mtx @ off,
              tint=lambda co: tuple(c * random.uniform(0.86, 1.06)
                                    for c in weather(co)))

# — mechinales: los huecos que dejó el andamio, en hélice alrededor del fuste
for i in range(15):
    a = i * 2.39996                                    # ángulo áureo: hélice natural
    z = 1.9 + i * 0.37
    _, mtx = on_wall(a, z, out=-0.10)
    V, F = cbox(0.19, 0.16, 0.15, ch=0.012)
    T.add(V, F, MAT_NEGRO, mtx, tint=flat(1.0))

# — llaves de tirante: las placas de hierro que cosen el muro
for (ta, tz) in ((-math.pi / 2 + 1.15, 3.30), (-math.pi / 2 - 2.0, 4.70),
                 (-math.pi / 2 + 2.6, 2.55)):
    _, mtx = on_wall(ta, tz, out=0.02)
    V, F = cbox(0.62, 0.07, 0.13, ch=0.010)
    T.add(V, F, MAT_HIERRO, mtx, tint=flat(1.0))
    V, F = cbox(0.13, 0.07, 0.52, ch=0.010)
    T.add(V, F, MAT_HIERRO, mtx, tint=flat(1.0))
    VS, FS = ico(1)
    T.add(VS, FS, MAT_HIERRO, mtx @ Matrix.Translation((0, 0.05, 0))
          @ Matrix.Diagonal((0.070, 0.070, 0.070, 1.0)), smooth=True, tint=flat(1.0))

# — PUERTA: jambas de sillería, dintel, tablas, herrajes, clavos, aldaba
# Marco local: X a lo ancho, Y hacia fuera, Z hacia arriba. Muro en y=0.
DOOR_H, DOOR_W = 2.16, 1.32
_, dmtx = on_wall(DOOR_ANG, Z_PLINTH + DOOR_H / 2.0 - 0.04)
V, F = cbox(DOOR_W, 0.10, DOOR_H + 0.06, ch=0.01)          # el interior en sombra
T.add(V, F, MAT_NEGRO, dmtx @ Matrix.Translation((0, -0.11, 0)), tint=flat(1.0))
for side in (-1, 1):                                       # jambas: soga y tizón
    for k in range(5):
        h = 0.46 if k % 2 == 0 else 0.40
        w = 0.34 if k % 2 == 0 else 0.44
        V, F = cbox(w, 0.30, h, ch=0.022)
        V = jitter(V, 0.012)
        T.add(V, F, MAT_PIEDRA,
              dmtx @ Matrix.Translation((side * (DOOR_W / 2 + w / 2 - 0.02), 0.10,
                                         -DOOR_H / 2 + 0.08 + k * 0.44 + h / 2)))
V, F = cbox(DOOR_W + 1.00, 0.34, 0.34, ch=0.025)           # dintel
V = jitter(V, 0.010)
T.add(V, F, MAT_PIEDRA, dmtx @ Matrix.Translation((0, 0.10, DOOR_H / 2 + 0.17)))
V, F = cbox(DOOR_W + 0.80, 0.66, 0.18, ch=0.03)            # umbral gastado
V = jitter(V, 0.012)
T.add(V, F, MAT_PIEDRA, dmtx @ Matrix.Translation((0, 0.24, -DOOR_H / 2 - 0.09)))
for k in range(6):                                         # 6 tablas, cada una a su aire
    V, F = cbox(0.208, 0.075 + random.uniform(-0.010, 0.010), DOOR_H, ch=0.009)
    T.add(V, F, MAT_MAD, dmtx @ Matrix.Translation((-0.55 + k * 0.22, 0.015, 0)))
for bz in (-0.78, 0.02, 0.82):                             # herrajes con clavos
    V, F = cbox(1.24, 0.030, 0.115, ch=0.008)
    T.add(V, F, MAT_HIERRO, dmtx @ Matrix.Translation((0, 0.068, bz)), tint=flat(1.0))
    for n in range(7):
        VS, FS = ico(1)
        T.add(VS, FS, MAT_HIERRO,
              dmtx @ Matrix.Translation((-0.54 + n * 0.18, 0.084, bz))
              @ Matrix.Diagonal((0.032, 0.032, 0.032, 1.0)), smooth=True, tint=flat(1.0))
VS, FS = lathe([(0.085, 0.0), (0.115, 0.018), (0.115, 0.046), (0.085, 0.064)], segs=14)
T.add(VS, FS, MAT_HIERRO, dmtx @ Matrix.Translation((0.44, 0.055, 0.26))
      @ Matrix.Rotation(math.radians(-90), 4, 'X'), smooth=True, tint=flat(1.0))

# — VENTANAS: alféizar volado, jambas, contraventana de tablas con pernios
for wi, (wa, wz) in enumerate(WINDOWS):
    _, wm = on_wall(wa, wz)
    V, F = cbox(0.78, 0.10, 0.86, ch=0.01)                 # hueco en sombra
    T.add(V, F, MAT_NEGRO, wm @ Matrix.Translation((0, -0.09, 0)), tint=flat(1.0))
    for side in (-1, 1):                                   # jambas
        V, F = cbox(0.26, 0.28, 1.02, ch=0.02)
        V = jitter(V, 0.010)
        T.add(V, F, MAT_PIEDRA, wm @ Matrix.Translation((side * 0.52, 0.09, 0)))
    V, F = cbox(1.36, 0.30, 0.22, ch=0.02)                 # dintel
    V = jitter(V, 0.008)
    T.add(V, F, MAT_PIEDRA, wm @ Matrix.Translation((0, 0.09, 0.62)))
    V, F = cbox(1.44, 0.48, 0.16, ch=0.03)                 # alféizar volado
    V = jitter(V, 0.008)
    T.add(V, F, MAT_PIEDRA, wm @ Matrix.Translation((0, 0.16, -0.60)))
    swing = math.radians((0, 0, 58, -44)[wi % 4])          # alguna abierta
    hinge = wm @ Matrix.Translation((-0.36, 0.14, 0)) @ Matrix.Rotation(swing, 4, 'Z')
    for k in range(3):                                     # tablas de la hoja
        V, F = cbox(0.23, 0.045, 0.84, ch=0.008)
        T.add(V, F, MAT_MADOSC, hinge @ Matrix.Translation((0.14 + k * 0.24, 0.03, 0)))
    V, F = cbox(0.76, 0.030, 0.09, ch=0.006)               # travesaño
    T.add(V, F, MAT_MADOSC, hinge @ Matrix.Translation((0.40, 0.062, -0.24)))
    for hz in (-0.30, 0.30):                               # pernios
        V, F = cbox(0.22, 0.026, 0.07, ch=0.005)
        T.add(V, F, MAT_HIERRO, hinge @ Matrix.Translation((0.09, 0.062, hz)),
              tint=flat(1.0))

torre = T.finish("Molino", MATS)

# ----------------------------------------------------------------- CUBIERTA
print("[MOLINO] cubierta: tejas una a una…")
R0, ZR0 = 3.42, Z_EAVE + 0.28
R1, ZR1 = 0.10, 11.62
SL = math.hypot(R0 - R1, ZR1 - ZR0)
s_r, s_z = (R1 - R0) / SL, (ZR1 - ZR0) / SL     # dirección de subida del faldón

C = Build()
# faldón oscuro bajo las tejas: que no se vea el cielo por las juntas
V, F = lathe([(R0 * 1.005, ZR0 - 0.06), (R1, ZR1 - 0.05)], segs=56, cap_top=True)
C.add(V, F, MAT_MADOSC, smooth=True, tint=flat(0.55))

# alero: tabla de borde + canes que asoman
V, F = lathe([(R0 + 0.06, ZR0 - 0.20), (R0 + 0.10, ZR0 - 0.06),
              (R0 + 0.06, ZR0 + 0.02)], segs=56)
C.add(V, F, MAT_MAD, smooth=True, tint=flat(0.78))
for i in range(20):
    a = i / 20 * 2 * math.pi
    ca, sa = math.cos(a), math.sin(a)
    V, F = beam(0.13, 0.11, 0.11, 0.09, 0.46, ch=0.012)
    mtx = frame_matrix(Vector((ca * (R0 - 0.10), sa * (R0 - 0.10), ZR0 - 0.16)),
                       Vector((-sa, ca, 0)), Vector((0, 0, 1)), Vector((ca, sa, 0)))
    C.add(V, F, MAT_MAD, mtx, tint=flat(0.72))

# tejas: cursos ascendentes, solape del 45 %, cada una con su desvío
EXPO, TW, TL = 0.232, 0.335, 0.44
ncourse = int(SL / EXPO)
ntiles = 0
for c in range(ncourse):
    t = (c * EXPO) / SL
    r = lerp(R0, R1, t)
    z = lerp(ZR0, ZR1, t)
    if r < 0.24:
        break
    n = max(6, int(2 * math.pi * r / TW))
    for i in range(n):
        a = (i + (0.5 if c % 2 else 0.0)) / n * 2 * math.pi
        ca, sa = math.cos(a), math.sin(a)
        U = Vector((s_r * ca, s_r * sa, s_z))          # hacia la cumbrera
        N = Vector((s_z * ca, s_z * sa, -s_r))         # normal saliente
        Tg = Vector((-sa, ca, 0.0))
        p = Vector((ca * r, sa * r, z)) + N * 0.012
        mtx = frame_matrix(p, Tg, U, N)
        mtx = mtx @ Matrix.Rotation(random.uniform(-0.035, 0.035), 4, 'Z')
        mtx = mtx @ Matrix.Translation((random.uniform(-0.008, 0.008), 0.0,
                                        random.uniform(-0.004, 0.006)))
        sc_w = 2 * math.pi * r / n / TW
        V, F = tile(width=TW * sc_w, length=TL, taper=0.87)
        shade = 0.80 + 0.20 * random.random()
        C.add(V, F, MAT_TEJA, mtx, smooth=True,
              tint=lambda co, s=shade: (s * weather(co)[0],) * 3)
        ntiles += 1
print(f"[MOLINO]   {ntiles} tejas en {ncourse} hiladas")

# caballete y remate de hierro
V, F = lathe([(0.30, ZR1 - 0.22), (0.34, ZR1 - 0.10), (0.20, ZR1 + 0.04)], segs=20,
             cap_top=True)
C.add(V, F, MAT_TEJA, smooth=True, tint=flat(0.85))
V, F = beam(0.075, 0.075, 0.045, 0.045, 1.05, ch=0.008)
C.add(V, F, MAT_HIERRO, Matrix.Translation((0, 0, ZR1)), tint=flat(1.0))
V, F = cbox(0.46, 0.045, 0.045, ch=0.006)
C.add(V, F, MAT_HIERRO, Matrix.Translation((0, 0, ZR1 + 0.72)), tint=flat(1.0))
cubierta = C.finish("Molino_Cubierta", MATS)

# ----------------------------------------------------------------- ASPAS
print("[MOLINO] aspas: celosía y lona…")
A = Build()
HUB = Vector((0.0, -3.30, 9.72))

# bocín: tambor con zunchos y pernos, más el eje que entra en la cubierta
V, F = lathe([(0.30, -1.70), (0.34, -1.55), (0.36, -0.30), (0.44, -0.18),
              (0.46, 0.10), (0.40, 0.26), (0.22, 0.34)], segs=22, cap_top=True)
A.add(V, F, MAT_MADOSC, smooth=True, tint=flat(0.85))
for bz in (-0.10, 0.16):
    V, F = lathe([(0.475, bz), (0.495, bz + 0.02), (0.495, bz + 0.075),
                  (0.475, bz + 0.095)], segs=22)
    A.add(V, F, MAT_HIERRO, smooth=True, tint=flat(1.0))
    for k in range(8):
        a = k / 8 * 2 * math.pi
        VS, FS = ico(1)
        m = (Matrix.Translation((math.cos(a) * 0.50, math.sin(a) * 0.50, bz + 0.048))
             @ Matrix.Diagonal((0.040, 0.040, 0.040, 1.0)))
        A.add(VS, FS, MAT_HIERRO, m, smooth=True, tint=flat(1.0))

SPAR_L, NBARS = 6.35, 11
for arm in range(4):
    rot = Matrix.Rotation(math.radians(45 + arm * 90 + 4.0), 4, 'Z')
    # verga principal, en punta (crece hacia +X, igual que su celosía)
    V, F = beam(0.19, 0.155, 0.085, 0.075, SPAR_L, ch=0.014)
    m = rot @ Matrix.Rotation(math.radians(90), 4, 'Y')
    A.add(V, F, MAT_MAD, m, tint=flat(0.92))
    # travesaños: más cortos según se aleja del bocín, centrados en la verga
    for k in range(NBARS):
        t = 0.13 + 0.855 * k / (NBARS - 1)
        d = t * SPAR_L
        half = lerp(0.86, 0.46, t)
        V, F = beam(0.062, 0.048, 0.052, 0.042, half * 2, ch=0.008)
        m = (rot @ Matrix.Translation((d, -half, 0.045))
             @ Matrix.Rotation(math.radians(-90), 4, 'X'))
        A.add(V, F, MAT_MAD, m, tint=flat(0.86))
    # largueros que cosen las puntas de los travesaños
    for side in (-1, 1):
        for seg in range(NBARS - 1):
            t0 = 0.13 + 0.855 * seg / (NBARS - 1)
            t1 = 0.13 + 0.855 * (seg + 1) / (NBARS - 1)
            p0 = Vector((t0 * SPAR_L, side * lerp(0.86, 0.46, t0), 0.045))
            p1 = Vector((t1 * SPAR_L, side * lerp(0.86, 0.46, t1), 0.045))
            L = (p1 - p0).length
            V, F = beam(0.034, 0.030, 0.034, 0.030, L, ch=0.006)
            zang = math.atan2(p1.y - p0.y, p1.x - p0.x)
            m = (rot @ Matrix.Translation(p0) @ Matrix.Rotation(zang, 4, 'Z')
                 @ Matrix.Rotation(math.radians(90), 4, 'Y'))
            A.add(V, F, MAT_MAD, m, tint=flat(0.80))
    # lona tendida sobre la mitad exterior: va EN el plano del aspa, con panza
    CW, CD = 2.55, 1.16
    V, F = sagging_grid(CW, CD, 16, 9, sag=0.30, ripple=0.055, seed=arm * 3.7)
    m = rot @ Matrix.Translation((SPAR_L * 0.685, 0.0, 0.125))
    A.add(V, F, MAT_LONA, m, smooth=True, tint=flat(1.0))
    # cabos que amarran la lona a los largueros
    for side in (-1, 1):
        V, F = beam(0.020, 0.020, 0.020, 0.020, CW, ch=0.004)
        m = (rot @ Matrix.Translation((SPAR_L * 0.685 - CW / 2, side * CD / 2, 0.135))
             @ Matrix.Rotation(math.radians(90), 4, 'Y'))
        A.add(V, F, MAT_MADOSC, m, tint=flat(0.9))

aspas = A.finish("Molino_Aspas", MATS)
aspas.location = HUB
aspas.rotation_euler = (math.radians(80.0), 0.0, 0.0)   # eje inclinado; gira en Z local

# ----------------------------------------------------------------- SUELO
print("[MOLINO] cerro, piedras y hierba…")
G = Build()
RINGS, SEGS, GR = 34, 72, 27.0


def ground_z(x, y):
    d = math.hypot(x, y)
    z = -(d * d) / 190.0
    z += 0.30 * noise.noise(Vector((x * 0.09, y * 0.09, 1.3)))
    z += 0.10 * noise.noise(Vector((x * 0.31, y * 0.31, 4.1)))
    z -= 0.16 * clamp01(1.0 - abs(d - 5.6) / 2.4)          # rodada de paso
    return z


gv = []
for ri in range(RINGS + 1):
    rr = GR * (ri / RINGS) ** 1.6
    for si in range(SEGS):
        a = si / SEGS * 2 * math.pi
        x, y = math.cos(a) * rr, math.sin(a) * rr
        gv.append((x, y, ground_z(x, y)))
gf = []
for ri in range(RINGS):
    for si in range(SEGS):
        a = ri * SEGS + si
        b = ri * SEGS + (si + 1) % SEGS
        c = (ri + 1) * SEGS + (si + 1) % SEGS
        d = (ri + 1) * SEGS + si
        gf.append([a, b, c, d])


def ground_tint(co):
    d = math.hypot(co.x, co.y)
    worn = clamp01(1.0 - (d - 4.2) / 3.4)                   # tierra pisada
    worn = max(worn, clamp01(1.0 - abs(d - 5.6) / 2.0) * 0.85)
    g = 0.92 + 0.16 * noise.noise(Vector((co.x * 0.5, co.y * 0.5, 2.0)))
    dry = (0.72 * g, 0.68 * g, 0.48 * g)                    # rastrojo seco
    dirt = (0.92 * g, 0.83 * g, 0.68 * g)                   # tierra batida
    return tuple(lerp(dry[i], dirt[i], worn) for i in range(3))


G.add(gv, gf, MAT_TIERRA, smooth=True, tint=ground_tint)
suelo = G.finish("Cerro", MATS)

# piedras sueltas
S = Build()
for i in range(340):
    a = random.uniform(0, 2 * math.pi)
    d = 4.0 + random.random() ** 0.6 * 21.0
    x, y = math.cos(a) * d, math.sin(a) * d
    z = ground_z(x, y)
    s = random.uniform(0.07, 0.30)
    V, F = cbox(s * random.uniform(1.0, 2.0), s * random.uniform(1.0, 1.8), s,
                ch=s * 0.22)
    V = jitter(V, s * 0.16)
    m = (Matrix.Translation((x, y, z + s * 0.35))
         @ Matrix.Rotation(random.uniform(0, 6.28), 4, 'Z')
         @ Matrix.Rotation(random.uniform(-0.25, 0.25), 4, 'X'))
    S.add(V, F, MAT_PIEDRA, m, tint=lambda co: (random.uniform(0.85, 1.1),) * 3)
piedras = S.finish("Piedras", MATS)

# matas de hierba seca
H = Build()
for i in range(900):
    a = random.uniform(0, 2 * math.pi)
    d = 4.6 + random.random() ** 0.5 * 22.0
    x, y = math.cos(a) * d, math.sin(a) * d
    if abs(d - 5.6) < 1.6 and random.random() < 0.8:
        continue                                   # el paso está pelado
    z = ground_z(x, y)
    base = Matrix.Translation((x, y, z))
    for b in range(random.randint(5, 8)):
        h = random.uniform(0.20, 0.44)
        V, F = blade(h=h, w=random.uniform(0.016, 0.026),
                     lean=random.uniform(0.05, 0.22))
        m = (base @ Matrix.Translation((random.uniform(-0.09, 0.09),
                                        random.uniform(-0.09, 0.09), 0))
             @ Matrix.Rotation(random.uniform(0, 6.28), 4, 'Z'))
        sh = random.uniform(0.70, 1.20)
        warm = random.uniform(0.88, 1.22)         # unas matas más secas que otras
        col = (sh * warm, sh * (0.92 + 0.08 * warm), sh * 0.78)
        H.add(V, F, MAT_HIERBA, m, smooth=True, tint=lambda co, c=col: c)
hierba = H.finish("Hierba", MATS)

# motas de Ánima
P = Build()
for i in range(170):
    a = random.uniform(0, 2 * math.pi)
    d = 2.0 + random.random() ** 0.7 * 13.0
    x, y = math.cos(a) * d, math.sin(a) * d
    z = ground_z(x, y) + random.uniform(0.4, 10.0) * random.random() ** 0.7 + 0.25
    VS, FS = ico(1)
    r = random.uniform(0.011, 0.030)
    P.add(VS, FS, MAT_ANIMA,
          Matrix.Translation((x, y, z)) @ Matrix.Diagonal((r, r, r, 1.0)),
          smooth=True, tint=flat(1.0))
motas = P.finish("AnimaMotas", MATS)

# cordal lejano: dos siluetas para que el horizonte no sea una línea
D = Build()
for k, (dist, hgt, col) in enumerate(((165.0, 15.0, 0.80), (240.0, 26.0, 1.25))):
    ring0, ring1 = [], []
    for si in range(96):
        a = si / 96 * 2 * math.pi
        h = hgt * (0.45 + 0.55 * abs(noise.noise(Vector((math.cos(a) * 2.2,
                                                         math.sin(a) * 2.2, k * 5.0)))))
        ring0.append((math.cos(a) * dist, math.sin(a) * dist, -14.0))
        ring1.append((math.cos(a) * dist, math.sin(a) * dist, h - 14.0))
    V, F = loft([ring0, ring1], cap_start=False, cap_end=False)
    D.add(V, F, MAT_TIERRA, smooth=True, tint=flat(col))
cordal = D.finish("Cordal", MATS)
# la distancia se come el contraste: el cordal se tiñe del aire, no de la tierra
haze = make_mat("M_Cordal", (0.42, 0.33, 0.36), 0.95, emit=(0.62, 0.42, 0.34),
                emit_str=0.30)
cordal.data.materials.clear()
cordal.data.materials.append(haze)

for ob in (torre, cubierta, suelo, cordal):
    ob.game.physics_type = 'STATIC'
    ob.game.use_collision_bounds = True
    ob.game.collision_bounds_type = 'TRIANGLE_MESH'
for ob in (aspas, piedras, hierba, motas):
    ob.game.physics_type = 'NO_COLLISION'

# ----------------------------------------------------------------- cielo y luz
print("[MOLINO] cielo y luz…")
SUN_FROM = Vector((0.344, -0.906, 0.242)).normalized()   # de dónde viene el sol

world = bpy.data.worlds.new("W_Atardecer")
sc.world = world
world.use_nodes = True
wnt = world.node_tree
for n in list(wnt.nodes):
    wnt.nodes.remove(n)
wout = wnt.nodes.new("ShaderNodeOutputWorld")
wbg = wnt.nodes.new("ShaderNodeBackground")
wbg.inputs["Strength"].default_value = 1.0
geo = wnt.nodes.new("ShaderNodeNewGeometry")
# "Incoming" apunta del cielo HACIA la cámara: hay que darle la vuelta para
# que +Z sea el cénit y no el suelo.
look = wnt.nodes.new("ShaderNodeVectorMath")
look.operation = 'SCALE'
look.inputs["Scale"].default_value = -1.0
wnt.links.new(geo.outputs["Incoming"], look.inputs[0])
sep = wnt.nodes.new("ShaderNodeSeparateXYZ")
elev = wnt.nodes.new("ShaderNodeMapRange")
elev.inputs["From Min"].default_value = -0.12
elev.inputs["From Max"].default_value = 0.62
band = wnt.nodes.new("ShaderNodeValToRGB")
cr = band.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (1.00, 0.44, 0.13, 1.0)
e = cr.elements.new(0.13); e.color = (1.00, 0.60, 0.22, 1.0)
e = cr.elements.new(0.32); e.color = (0.93, 0.55, 0.36, 1.0)
e = cr.elements.new(0.58); e.color = (0.52, 0.42, 0.52, 1.0)
cr.elements[-1].position = 1.0
cr.elements[-1].color = (0.13, 0.17, 0.36, 1.0)
wnt.links.new(look.outputs["Vector"], sep.inputs["Vector"])
wnt.links.new(sep.outputs["Z"], elev.inputs["Value"])
wnt.links.new(elev.outputs["Result"], band.inputs["Fac"])
# resplandor concentrado en el acimut del sol
dot = wnt.nodes.new("ShaderNodeVectorMath")
dot.operation = 'DOT_PRODUCT'
dot.inputs[1].default_value = tuple(SUN_FROM)
gl = wnt.nodes.new("ShaderNodeMapRange")
gl.inputs["From Min"].default_value = 0.55
gl.inputs["From Max"].default_value = 0.995
hz = wnt.nodes.new("ShaderNodeMapRange")
hz.inputs["From Min"].default_value = 0.34
hz.inputs["From Max"].default_value = 0.0
mul = wnt.nodes.new("ShaderNodeMath")
mul.operation = 'MULTIPLY'
glow = wnt.nodes.new("ShaderNodeMix")
glow.data_type = 'RGBA'
glow.inputs["B"].default_value = (1.0, 0.72, 0.34, 1.0)
wnt.links.new(look.outputs["Vector"], dot.inputs[0])
wnt.links.new(dot.outputs["Value"], gl.inputs["Value"])
wnt.links.new(sep.outputs["Z"], hz.inputs["Value"])
wnt.links.new(gl.outputs["Result"], mul.inputs[0])
wnt.links.new(hz.outputs["Result"], mul.inputs[1])
wnt.links.new(band.outputs["Color"], glow.inputs["A"])
wnt.links.new(mul.outputs["Value"], glow.inputs["Factor"])
wnt.links.new(glow.outputs["Result"], wbg.inputs["Color"])
wnt.links.new(wbg.outputs["Background"], wout.inputs["Surface"])


def add_sun(name, from_dir, energy, color, angle_deg):
    d = bpy.data.lights.new(name, 'SUN')
    d.energy = energy
    d.color = color
    d.angle = math.radians(angle_deg)
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    o.rotation_euler = (-Vector(from_dir)).to_track_quat('-Z', 'Y').to_euler()
    o.game.physics_type = 'NO_COLLISION'
    return o


add_sun("Sol", SUN_FROM, 5.4, (1.0, 0.63, 0.33), 1.1)
add_sun("Contra", Vector((-0.62, 0.68, 0.20)).normalized(), 2.1, (1.0, 0.52, 0.30), 3.0)
add_sun("Relleno", Vector((-0.35, -0.30, 0.88)).normalized(), 0.55,
        (0.46, 0.58, 0.95), 12.0)

# disco solar en el horizonte
V, F = lathe([(0.0, 0.0), (13.0, 0.0)], segs=40)
Sg = Build()
Sg.add(V, F, MAT_ANIMA, tint=flat(1.0))
sol = Sg.finish("SolDisco", MATS)
sol.location = SUN_FROM * 430.0
sol.rotation_euler = (-SUN_FROM).to_track_quat('-Z', 'Y').to_euler()
sol.game.physics_type = 'NO_COLLISION'
solmat = make_mat("M_SolDisco", (1.0, 0.55, 0.20), 0.9, emit=(1.0, 0.50, 0.16),
                  emit_str=14.0)
sol.data.materials.clear()
sol.data.materials.append(solmat)

# ----------------------------------------------------------------- cámaras


def cam(name, loc, target, lens=50.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = 1200.0
    co = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(co)
    co.location = loc
    co.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    co.game.physics_type = 'NO_COLLISION'
    return co


hero = cam("CamHeroe", (-20.5, -26.5, 3.40), (0.0, -1.0, 7.30), lens=40)
cam("CamPostal", (-31.0, -40.0, 9.00), (0.0, 0.0, 6.60), lens=58)
cam("CamPuerta", (0.7, -11.6, 2.70), (0.0, -3.5, 2.05), lens=55)
cam("CamAspas", (-6.4, -13.6, 8.00), (0.0, -3.3, 9.50), lens=65)
cam("CamTejas", (6.6, -8.6, 11.00), (1.0, -2.2, 9.60), lens=80)
sc.camera = hero

# ----------------------------------------------------------------- ajustes
gs = sc.game_settings
gs.fps = 60
gs.physics_engine = 'BULLET'
gs.physics_gravity = 9.8

sc.render.resolution_x = 1600
sc.render.resolution_y = 900
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        continue
try:
    sc.view_settings.view_transform = 'AgX'
except TypeError:
    sc.view_settings.view_transform = 'Standard'
for look in ('AgX - Medium High Contrast', 'AgX - High Contrast', 'Medium High Contrast',
             'High Contrast'):
    try:
        sc.view_settings.look = look
        break
    except TypeError:
        continue
print("[MOLINO] view:", sc.view_settings.view_transform, "| look:", sc.view_settings.look)
try:
    sc.eevee.taa_render_samples = 96
    sc.eevee.use_raytracing = True
    sc.eevee.ray_tracing_options.use_denoise = True
except AttributeError:
    pass

tris = sum(len(m.polygons) for m in bpy.data.meshes)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[MOLINO] guardado: {OUT_BLEND}")
print(f"[MOLINO] objetos: {len(bpy.data.objects)}  caras: {tris}")
print("[MOLINO] OK")
