# ÁNIMA — Alonso: rasgos y materiales (paso 3 de 3)
#
#   Flipendo --background --python gen_alonso.py
# Entrada: AlonsoEstilo.blend   Salida: Alonso.blend
#
# Ojos (globo, iris, pestañas, cejas), pelo por mechones y materiales PBR.
# El pelo NO supone la forma del cráneo: la muestrea con un BVH lanzando rayos
# desde el centro de la cabeza, así se pega a la malla real aunque cambie.

import bpy
import bmesh
import collections
import math
import os
import random
import sys
from mathutils import Vector, Matrix
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("anima_kit", None)
from anima_kit import (                                            # noqa: E402
    Build, catmull, clamp01, hair_lock, ico, lerp, loft, smoothstep)

random.seed(1605)
HERE = os.path.dirname(os.path.abspath(__file__))
IN_BLEND = os.path.join(HERE, "AlonsoEstilo.blend")
OUT_BLEND = os.path.join(HERE, "Alonso.blend")

# EN CURSO. Los rasgos (ojos y pelo) todavía no salen bien: ver más abajo y
# bitacora/04-alonso.md. Con RASGOS = False, este paso solo aplica materiales y
# deja un asset limpio; con True, monta la versión rota que sirve de diagnóstico.
RASGOS = False

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
ob = bpy.data.objects["Alonso"]
me = ob.data
EYE_Z = ob["ALONSO_EYE_Z"]
CROWN_Z = ob["ALONSO_CROWN_Z"]
HEIGHT = ob["ALONSO_HEIGHT"]


def pbr(name, color, rough=0.6, metallic=0.0, sss=0.0, sss_col=None,
        sss_rad=None, aniso=0.0, coat=0.0, sheen=0.0, emit=None, emit_str=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]

    def st(k, v):
        if k in b.inputs:
            b.inputs[k].default_value = v
    st("Base Color", (*color, 1.0))
    st("Roughness", rough)
    st("Metallic", metallic)
    if sss:
        st("Subsurface Weight", sss)
        st("Subsurface Scale", 0.010)
        if sss_col:
            st("Subsurface Color", (*sss_col, 1.0))
        if sss_rad:
            st("Subsurface Radius", sss_rad)
    if aniso:
        st("Anisotropic", aniso)
    if coat:
        st("Coat Weight", coat)
        st("Coat Roughness", 0.16)
    if sheen:
        st("Sheen Weight", sheen)
    if emit:
        st("Emission Color", (*emit, 1.0))
        st("Emission Strength", emit_str)
    m.diffuse_color = (*color, 1.0)
    return m


def micro(mat, scale=520.0, amt=0.022):
    nt = mat.node_tree
    b = nt.nodes["Principled BSDF"]
    t = nt.nodes.new("ShaderNodeTexNoise")
    t.inputs["Scale"].default_value = scale
    t.inputs["Detail"].default_value = 8.0
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = amt
    bump.inputs["Distance"].default_value = 0.0012
    nt.links.new(t.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    return mat


PIEL = micro(pbr("M_Piel", (0.855, 0.660, 0.545), rough=0.44, sss=0.17,
                 sss_col=(0.86, 0.42, 0.32), sss_rad=(0.030, 0.011, 0.0075)))
PELO = pbr("M_Pelo", (0.105, 0.055, 0.033), rough=0.28, aniso=0.75, coat=0.40)
ESCLERA = pbr("M_Esclera", (0.90, 0.885, 0.885), rough=0.13, sss=0.10,
              sss_col=(0.85, 0.55, 0.50))
IRIS = pbr("M_Iris", (0.115, 0.245, 0.185), rough=0.07, coat=0.9)
PESTANA = pbr("M_Pestana", (0.040, 0.025, 0.022), rough=0.32)
CEJA = pbr("M_Ceja", (0.105, 0.058, 0.038), rough=0.40)
BRILLO = pbr("M_Brillo", (1, 1, 1), rough=0.05, emit=(1, 1, 1), emit_str=6.0)
me.materials.clear()
me.materials.append(PIEL)

# ----------------------------------------------------------------- muestreo
# La base de MakeHuman NO tiene huecos de ojo: el párpado es piel cerrada. Así
# que el ojo no es una esfera asomando por un agujero, sino un PARCHE almendrado
# apoyado en la cara. La superficie se muestrea con un BVH: nada se supone.
dg = bpy.context.evaluated_depsgraph_get()
BVH = BVHTree.FromObject(ob, dg)

L_EYE = Vector(ob["ALONSO_L_EYE"])
R_EYE = Vector(ob["ALONSO_R_EYE"])
head_pts = [v.co for v in me.vertices if v.co.z > EYE_Z - 0.115]
HEAD_C = sum(head_pts, Vector()) / len(head_pts)
HEAD_H = (CROWN_Z - EYE_Z) / 0.53
CHIN_Z = CROWN_Z - HEAD_H
print(f"[AL] centro de cabeza {tuple(round(c,3) for c in HEAD_C)} alto {HEAD_H:.3f}"
      f" barbilla {CHIN_Z:.3f}")


def face_at(x, z):
    """Superficie de la cara en (x, z). El rayo sale desde MUY cerca del ojo:
    si sale de lejos choca antes con la nariz o el pómulo y el parche se rompe."""
    for y0 in (L_EYE.y - 0.035, L_EYE.y - 0.070, L_EYE.y - 0.120):
        hit = BVH.ray_cast(Vector((x, y0, z)), Vector((0, 1, 0)), 0.30)
        if hit[0]:
            return hit[0]
    return None


def skull_at(direction):
    """Punto y normal del cráneo en una dirección desde el centro de la cabeza."""
    d = Vector(direction).normalized()
    loc, nor, idx, dist = BVH.ray_cast(HEAD_C, d)
    return (loc, nor) if loc else (None, None)


# ----------------------------------------------------------------- OJOS
EW, EH = 0.0205, 0.0142          # semiejes del ojo (grande: lectura JRPG)
EYES = Build()


def rim_xz(side, t):
    """Contorno almendrado: lagrimal bajo y afilado, rabillo alto."""
    a = t * 2 * math.pi
    c, sn = math.cos(a), math.sin(a)
    cx, cz = (L_EYE.x if side > 0 else R_EYE.x), L_EYE.z
    hz = EH * (1.0 if sn >= 0 else 0.80)          # párpado inferior más plano
    x = cx + c * EW * side
    z = cz + (abs(sn) ** 1.18) * (1 if sn >= 0 else -1) * hz
    z += 0.0022 * c * side * (1 if side > 0 else 1)   # el rabillo remonta
    return x, z


def build_eye(side):
    cx = L_EYE.x if side > 0 else R_EYE.x
    cz = L_EYE.z
    N = 44
    rim = [rim_xz(side, i / N) for i in range(N)]

    def patch(scales, bulge, mat, tint=None, lift=0.0):
        rings = []
        for sc in scales:
            ring = []
            for (px, pz) in rim:
                qx, qz = cx + (px - cx) * sc, cz + (pz - cz) * sc
                surf = face_at(qx, qz)
                base_y = surf.y if surf else L_EYE.y
                b = bulge * (1.0 - sc * sc) ** 0.60 + lift
                ring.append((qx, base_y - 0.0004 - b, qz))
            rings.append(ring)
        V, F = loft(rings, cap_start=False, cap_end=True)
        EYES.add(V, F, mat_index(mat), smooth=True, tint=tint)

    patch([1.0, 0.90, 0.76, 0.58, 0.38, 0.16], 0.0040, ESCLERA)

    surf = face_at(cx, cz)
    ey = (surf.y if surf else L_EYE.y) - 0.0004 - 0.0040
    IR = 0.0104

    def iris_ring(sc, lift):
        out = []
        for i in range(30):
            a = i / 30 * 2 * math.pi
            px = cx + math.cos(a) * IR * sc
            pz = cz + math.sin(a) * IR * sc * 1.06
            sp = face_at(px, pz)
            byy = (sp.y if sp else L_EYE.y) - 0.0004
            m = min(math.hypot((px - cx) / EW, (pz - cz) / EH), 1.0)
            out.append((px, byy - 0.0040 * (1 - m * m) ** 0.60 - lift, pz))
        return out

    for (s0, s1, mat, tint) in ((1.00, 0.94, IRIS, (0.20, 0.22, 0.24)),
                                (0.94, 0.60, IRIS, (1.00, 1.06, 1.00)),
                                (0.60, 0.32, IRIS, (1.75, 1.90, 1.70)),
                                (0.32, 0.09, IRIS, (0.14, 0.14, 0.14))):
        V, F = loft([iris_ring(s0, 0.0009), iris_ring(s1, 0.0016)],
                    cap_start=False, cap_end=True)
        EYES.add(V, F, mat_index(mat), smooth=True, tint=(tint if tint else None))

    for (hx, hz, hr) in ((-0.0046, 0.0058, 0.0034), (0.0054, -0.0048, 0.0017)):
        hv, hf = ico(2)
        px, pz = cx + hx * side, cz + hz
        sp = face_at(px, pz)
        py = (sp.y if sp else L_EYE.y) - 0.0060
        EYES.add([(x * hr + px, y * hr * 0.45 + py, z * hr + pz) for (x, y, z) in hv],
                 hf, mat_index(BRILLO), smooth=True)

    # PESTAÑA superior: gruesa y remontada en el rabillo. Es lo que da la mirada.
    r0, r1 = [], []
    for k in range(N // 2 + 1):
        t = k / (N // 2) * 0.5
        px, pz = rim_xz(side, t)
        surf = face_at(px, pz)
        byy = (surf.y if surf else L_EYE.y)
        outer = 1.0 - abs(t - 0.0) / 0.5
        w = 0.0022 + 0.0060 * ((1.0 - t / 0.5) ** 2.0) + 0.0024 * math.sin(math.pi * t / 0.5)
        d = Vector((px - cx, 0.0, pz - cz))
        d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
        r0.append((px - d.x * 0.0014, byy - 0.0026, pz - d.z * 0.0014))
        r1.append((px + d.x * w * 0.5, byy - 0.0034, pz + d.z * w))
    V, F = loft([r0, r1], cap_start=False, cap_end=False)
    EYES.add(V, F, mat_index(PESTANA), smooth=True)

    # ceja
    b0, b1 = [], []
    bc = [(0.42, 0.0295), (0.78, 0.0350), (1.20, 0.0352), (1.62, 0.0300),
          (1.88, 0.0232)]
    pts = catmull([Vector((cx * f, 0.0, cz + dz)) for (f, dz) in bc], 16)
    for i, q in enumerate(pts):
        t = i / (len(pts) - 1)
        w = 0.0034 * (0.26 + 0.94 * math.sin(math.pi * clamp01(t * 1.04)) ** 0.5)
        surf = face_at(q.x, q.z)
        byy = (surf.y if surf else L_EYE.y)
        b0.append((q.x, byy - 0.0012, q.z - w))
        b1.append((q.x, byy - 0.0032, q.z + w * 0.78))
    V, F = loft([b0, b1], cap_start=False, cap_end=False)
    EYES.add(V, F, mat_index(CEJA), smooth=True)


EYE_MATS = [ESCLERA, IRIS, PESTANA, CEJA, BRILLO]


def mat_index(m):
    return EYE_MATS.index(m)


if RASGOS:
    build_eye(1)
    build_eye(-1)
if RASGOS:
    OJOS = EYES.finish("Alonso_Ojos", EYE_MATS)
    OJOS.game.physics_type = 'NO_COLLISION'
    print(f"[AL] ojos: {len(OJOS.data.polygons)} caras")

# ----------------------------------------------------------------- PELO
# Cada mechón nace en el cráneo REAL (rayo desde el centro de la cabeza) y luego
# sigue un FLUJO. Si siguiera la normal, saldría un erizo.
HAIR = Build()


def skull_dir(a, elev, off=0.0):
    d = Vector((math.sin(a) * math.cos(elev), -math.cos(a) * math.cos(elev),
                math.sin(elev)))
    loc, nor = skull_at(d)
    if loc is None:
        return None, None
    n = (loc - HEAD_C)
    n.z *= 0.72
    n.normalize()
    return loc + n * off, n


#            |a|     elevación mínima donde empieza el pelo (radianes)
HAIRLINE = [(0.00, math.radians(58)), (0.60, math.radians(52)),
            (1.05, math.radians(40)), (1.45, math.radians(22)),
            (2.10, math.radians(2)), (3.15, math.radians(-12))]


def hairline_elev(a):
    aa = abs(((a + math.pi) % (2 * math.pi)) - math.pi)
    for i in range(len(HAIRLINE) - 1):
        a0, e0 = HAIRLINE[i]
        a1, e1 = HAIRLINE[i + 1]
        if aa <= a1:
            return lerp(e0, e1, (aa - a0) / (a1 - a0))
    return HAIRLINE[-1][1]


def lock(a, elev, flow, L, bend=(0, 0, 0), w0=0.013, thick=0.66, off=0.004,
         twist=0.0, root_out=0.10, taper=2.9, segs=8):
    anchor, n = skull_dir(a, elev, off)
    if anchor is None:
        return
    d = Vector(flow).normalized()
    pts = [anchor + n * (L * root_out * (1.0 - (1.0 - i / (segs - 1)) ** 2))
           + d * (L * (i / (segs - 1))) + Vector(bend) * ((i / (segs - 1)) ** 2)
           for i in range(segs)]
    V, F = hair_lock(pts, w0=w0, w1=0.0013, thick=thick, n=13, twist_amt=twist,
                     up_hint=(n.x, n.y, n.z), taper=taper)
    HAIR.add(V, F, 0, smooth=True)


if RASGOS:
    # casquete: nace en la línea del pelo, sin canto duro en la frente
    rings = []
    for j in range(13):
        t = j / 12
        ring = []
        for i in range(52):
            a = i / 52 * 2 * math.pi
            e = lerp(math.radians(89), hairline_elev(a), t ** 0.86)
            pt, _ = skull_dir(a, e, 0.0050 + 0.0040 * math.sin(t * math.pi) ** 0.8)
            ring.append(tuple(pt) if pt else (0, 0, CROWN_Z))
        rings.append(ring)
    V, F = loft(rings, cap_start=False, cap_end=False)
    HAIR.add(V, F, 0, smooth=True)

    # FLEQUILLO: cuñas cortas sobre la frente, con raya y barrido a un lado
    for k in range(13):
        t = (k - 6) / 6.0
        a = t * 0.98
        e = hairline_elev(a) - math.radians(4)
        L = 0.028 + 0.010 * (1.0 - abs(t)) + random.uniform(-0.002, 0.002)
        lock(a, e, (t * 0.30 + 0.22, -0.46, -0.82), L,
             bend=(t * 0.005 + 0.003, -0.004, -0.004),
             w0=0.0125 + 0.0042 * (1.0 - abs(t)), thick=0.58,
             twist=random.uniform(-0.2, 0.2), off=0.0060, root_out=0.10, taper=3.0)

    # mechones que enmarcan la cara
    for side in (-1, 1):
        for k in range(2):
            a = side * (1.16 + k * 0.18)
            lock(a, hairline_elev(a) - math.radians(2 + k * 3),
                 (side * 0.30, -0.18, -0.93), 0.044 + k * 0.012,
                 bend=(side * 0.005, -0.003, -0.010), w0=0.0108, thick=0.54,
                 twist=side * 0.2, off=0.0050, root_out=0.08, taper=3.2)

    # PÚAS de coronilla: arriba y atrás
    SPIKES = [(0.00, 80, (0.04, 0.60, 0.80), 0.062), (0.55, 76, (0.28, 0.58, 0.77), 0.058),
              (-0.55, 76, (-0.28, 0.58, 0.77), 0.058), (1.10, 68, (0.46, 0.46, 0.76), 0.054),
              (-1.10, 68, (-0.46, 0.46, 0.76), 0.054), (1.65, 58, (0.56, 0.32, 0.76), 0.050),
              (-1.65, 58, (-0.56, 0.32, 0.76), 0.050), (2.30, 62, (0.34, 0.70, 0.63), 0.056),
              (-2.30, 62, (-0.34, 0.70, 0.63), 0.056), (2.80, 55, (0.14, 0.86, 0.49), 0.058),
              (-2.80, 55, (-0.14, 0.86, 0.49), 0.058), (3.14, 50, (0.00, 0.92, 0.39), 0.056)]
    for (a, ed, d, L) in SPIKES:
        e = math.radians(ed)
        lock(a, e, d, L, bend=(d[0] * 0.012, 0.016, -0.012), w0=0.0180, thick=0.74,
             twist=random.uniform(-0.25, 0.25), off=0.0075, root_out=0.15, taper=2.7)
        lock(a + 0.26, e - math.radians(7), (d[0] * 0.92, d[1] * 0.90, d[2] * 0.84),
             L * 0.72, bend=(d[0] * 0.008, 0.012, -0.010), w0=0.0126, thick=0.68,
             twist=random.uniform(-0.25, 0.25), off=0.0068, root_out=0.12, taper=2.9)

    # capa media y nuca
    for k in range(20):
        a = -math.pi + (k / 20) * 2 * math.pi + 0.11
        e = lerp(math.radians(48), hairline_elev(a) + math.radians(8), 0.35)
        _, n = skull_dir(a, e)
        if n is None:
            continue
        lock(a, e, (n.x * 0.36, n.y * 0.36 + 0.28, -0.62 if abs(a) < 1.4 else 0.16),
             0.034 + random.uniform(0.0, 0.012), bend=(n.x * 0.003, 0.006, -0.004),
             w0=0.0102, thick=0.62, twist=random.uniform(-0.3, 0.3),
             off=0.0045, root_out=0.08, taper=3.0)
    for k in range(11):
        t = (k - 5) / 5.0
        a = math.pi + t * 0.95
        lock(a, hairline_elev(a) + math.radians(10), (t * 0.20, 0.28, -0.94),
             0.046 + 0.016 * (1.0 - abs(t)), bend=(t * 0.003, 0.006, -0.008),
             w0=0.0112, thick=0.62, twist=random.uniform(-0.2, 0.2),
             off=0.0050, root_out=0.08, taper=3.0)

    PELO_OB = HAIR.finish("Alonso_Pelo", [PELO])
    PELO_OB.game.physics_type = 'NO_COLLISION'
    print(f"[AL] pelo: {len(PELO_OB.data.polygons)} caras")
else:
    print("[AL] rasgos desactivados: solo cuerpo estilizado + materiales")

ob.game.physics_type = 'NO_COLLISION'
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[AL] guardado: {OUT_BLEND}")
print(f"[AL] total caras: {sum(len(m.polygons) for m in bpy.data.meshes)}")
print("[AL] OK")
