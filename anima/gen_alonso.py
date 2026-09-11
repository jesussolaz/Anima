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
# bitacora/04-alonso.md. Con RASGOS = False   # ojos y cejas propios: aún en curso, este paso solo aplica materiales y
# deja un asset limpio; con True, monta la versión rota que sirve de diagnóstico.
RASGOS = False   # ojos y cejas propios: aún en curso

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
ob = bpy.data.objects["Alonso"]
me = ob.data
EYE_Z = ob["ALONSO_EYE_Z"]
CROWN_Z = ob["ALONSO_CROWN_Z"]
HEIGHT = ob["ALONSO_HEIGHT"]


def sombra_de(color, calida=False, fuerza=0.62):
    """El color de sombra DESPLAZA EL TONO, no solo oscurece (conocimiento/11).
    Piel hacia el rojo; el resto hacia el azul/púrpura.

    NO se hace sumando al matiz: sumarle a un marrón (matiz ~0,05) lo lleva al
    amarillo-verde, no al azul. Se MEZCLA hacia un tinte objetivo en RGB, que
    funciona sea cual sea el color de partida.
    """
    tinte = (0.62, 0.26, 0.20) if calida else (0.24, 0.26, 0.48)
    k = 0.30
    return tuple(max(0.0, min(1.0, c * fuerza * (1 - k) + t * k * fuerza))
                 for c, t in zip(color, tinte))


def toon(name, color, calida=False, bandas=2, fuerza=0.62, spec=0.0,
         aniso=False):
    """Cel shader de EEVEE: Diffuse BSDF -> Shader to RGB -> Color Ramp en
    CONSTANT. Sin esto los personajes salen como figuras de plástico
    fotografiadas: el PBR realista no sirve para este estilo."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")      # la pieza clave, solo EEVEE
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = 'CONSTANT'       # bandas duras, no degradado
    som = sombra_de(color, calida, fuerza)
    med = sombra_de(color, calida, (fuerza + 1.0) * 0.5)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*som, 1.0)
    if bandas >= 3:
        e = ramp.color_ramp.elements.new(0.36)
        e.color = (*med, 1.0)
    ramp.color_ramp.elements[-1].position = 0.52
    ramp.color_ramp.elements[-1].color = (*color, 1.0)
    emi = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(dif.outputs["BSDF"], s2r.inputs["Shader"])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    salida = ramp.outputs["Color"]

    if spec > 0.0:
        # brillo: en el pelo es una BANDA que recorre la cabeza, no un punto
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.22 if not aniso else 0.38
        if aniso and "Anisotropy" in gl.inputs:
            gl.inputs["Anisotropy"].default_value = 0.85
        g2r = nt.nodes.new("ShaderNodeShaderToRGB")
        gramp = nt.nodes.new("ShaderNodeValToRGB")
        gramp.color_ramp.interpolation = 'CONSTANT'
        gramp.color_ramp.elements[0].position = 0.0
        gramp.color_ramp.elements[0].color = (0, 0, 0, 1)
        gramp.color_ramp.elements[1].position = 0.62
        gramp.color_ramp.elements[1].color = (spec, spec, spec, 1.0)
        add = nt.nodes.new("ShaderNodeMix")
        add.data_type = 'RGBA'
        add.blend_type = 'ADD'
        add.inputs["Factor"].default_value = 1.0
        nt.links.new(gl.outputs["BSDF"], g2r.inputs["Shader"])
        nt.links.new(g2r.outputs["Color"], gramp.inputs["Fac"])
        nt.links.new(salida, add.inputs["A"])
        nt.links.new(gramp.outputs["Color"], add.inputs["B"])
        salida = add.outputs["Result"]

    nt.links.new(salida, emi.inputs["Color"])
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = (*color, 1.0)
    return m


def pbr(name, color, rough=0.6, metallic=0.0, sss=0.0, sss_col=None,
        sss_rad=None, aniso=0.0, coat=0.0, sheen=0.0, emit=None, emit_str=0.0):
    """Solo para lo que NO es personaje (ojo con textura)."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]

    def st(k, v):
        if k in b.inputs:
            b.inputs[k].default_value = v
    st("Base Color", (*color, 1.0))
    st("Roughness", rough)
    st("Metallic", metallic)
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


PIEL = toon("M_Piel", (0.925, 0.760, 0.650), calida=True, bandas=3, fuerza=0.70)
PELO = toon("M_Pelo", (0.300, 0.150, 0.080), bandas=2, fuerza=0.55,
            spec=0.42, aniso=True)
ESCLERA = toon("M_Esclera", (0.97, 0.965, 0.975), bandas=2, fuerza=0.88)
IRIS = toon("M_Iris", (0.150, 0.400, 0.320), bandas=2, fuerza=0.72, spec=0.9)
PESTANA = toon("M_Pestana", (0.085, 0.050, 0.048), bandas=2, fuerza=0.85)
CEJA = toon("M_Ceja", (0.260, 0.130, 0.070), bandas=2, fuerza=0.80)
BRILLO = pbr("M_Brillo", (1, 1, 1), rough=0.05, emit=(1, 1, 1), emit_str=6.0)

# Ojo con la textura del pack CC0: el iris viene pintado y mapeado a estas UV.
OJO_MAT = pbr("M_Ojo", (1, 1, 1), rough=0.09, coat=0.9,
              emit=(1, 1, 1), emit_str=0.28)   # el ojo va al fondo
                                                # de la cuenca y se apaga
_tex = os.path.join(HERE, "assets", "eyes", "materials", "bluegreen_eye.png")
if os.path.exists(_tex):
    nt = OJO_MAT.node_tree
    img = nt.nodes.new("ShaderNodeTexImage")
    img.image = bpy.data.images.load(_tex, check_existing=True)
    img.interpolation = 'Cubic'
    bsdf = nt.nodes["Principled BSDF"]
    nt.links.new(img.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(img.outputs["Color"], bsdf.inputs["Emission Color"])
    print("[AL] textura de iris:", os.path.basename(_tex))
_ojos = bpy.data.objects.get("Alonso_Ojos")
if _ojos:
    _ojos.data.materials.clear()
    _ojos.data.materials.append(OJO_MAT)
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
# Gramática del género: el ojo NO es un globo realista asomando, es geometría
# PLANA con esclerótica, iris grande, pupila y brillos como piezas separadas.
# Y la LÍNEA DE PESTAÑA gruesa alrededor del hueco es lo que da la mirada — y de
# paso tapa el borde del recorte, que en una malla de rejilla queda escalonado.

_viejo = bpy.data.objects.get("Alonso_Ojos")
if _viejo:                       # el globo esférico del pack ya no se usa
    bpy.data.objects.remove(_viejo, do_unlink=True)
    print("[AL] globo esférico retirado: el ojo pasa a ser plano")

L_EYE = Vector(ob["ALONSO_L_EYE"])
R_EYE = Vector(ob["ALONSO_R_EYE"])
EW, EH = 0.0277, 0.0177          # 34 % del ancho de cara (conocimiento/06)


def eye_mask(x, z, c):
    """<1 dentro del hueco. Lagrimal bajo y afilado, rabillo levemente alto."""
    u = (abs(x) - abs(c.x)) / EW
    v = (z - c.z - 0.0028 * u) / EH
    v = v / (1.0 + 0.26 * clamp01(-v))          # párpado inferior más plano
    return math.sqrt(u * u * (1.0 + 0.10 * max(v, 0.0)) + v * v)


# NO se recorta el párpado. Recortar en una malla de rejilla deja el borde
# escalonado, y taparlo con la pestaña resultó frágil. Como la cara ya está
# aplanada en la zona del ojo, el ojo va como CALCOMANÍA: geometría plana
# apoyada sobre la piel, un pelo por delante. El contorno lo define el ojo, así
# que sale limpio, y la pestaña lo remata.
EYES = Build()
EYE_MATS = [ESCLERA, IRIS, PESTANA, CEJA]


def build_eye(ctr, side):
    surf = face_at(ctr.x, ctr.z)
    fy = (surf.y if surf else ctr.y)

    def ell(rx, rz, depth, n=48):
        return [(ctr.x + math.cos(i / n * 2 * math.pi) * rx, fy - depth,
                 ctr.z + math.sin(i / n * 2 * math.pi) * rz) for i in range(n)]

    # esclerótica: elipse plana, apenas abombada
    rings = []
    for sc in (1.00, 0.82, 0.60, 0.34, 0.02):
        d = 0.0016 + 0.0030 * clamp01(1.0 - sc * sc) ** 0.6
        rings.append(ell(EW * sc, EH * sc, d))
    V, F = loft(rings, cap_start=False, cap_end=True)
    EYES.add(V, F, 0, smooth=True)

    # iris grande, anillo limbal, pupila y dos brillos
    # El iris toca el párpado superior y se mete debajo (conocimiento/02).
    # Flotando con blanco alrededor lee como sorpresa o como muñeco.
    IR = 0.0122
    IZ = 0.0026                       # se sube: tapado arriba, esclerótica abajo
    for (s0, s1, mat, tint) in ((1.00, 0.90, 1, (0.16, 0.18, 0.22)),
                                (0.90, 0.46, 1, (1.00, 1.06, 1.00)),
                                (0.46, 0.30, 1, (1.85, 2.00, 1.80)),
                                (0.30, 0.06, 3, (0.10, 0.10, 0.12))):
        r0 = [(x, y, z + IZ) for (x, y, z) in
              ell(IR * s0, IR * s0 * 1.04, 0.0050 + 0.0012 * (1 - s0), 30)]
        r1 = [(x, y, z + IZ) for (x, y, z) in
              ell(IR * s1, IR * s1 * 1.04, 0.0050 + 0.0012 * (1 - s1), 30)]
        V, F = loft([r0, r1], cap_start=False, cap_end=True)
        EYES.add(V, F, mat, smooth=True, tint=tint)
    for (hx, hz, hr, hi) in ((-0.0048, 0.0072, 0.0034, 14.0),
                             (0.0052, -0.0026, 0.0017, 4.0)):
        hv, hf = ico(2)
        EYES.add([(x * hr + ctr.x + hx * side, y * hr * 0.4 + fy - 0.0064,
                   z * hr + ctr.z + hz) for (x, y, z) in hv], hf, 0,
                 smooth=True, tint=(hi, hi, hi))

    # LÍNEA DE PESTAÑA: gruesa arriba, remontando en el rabillo. Da la mirada y
    # remata el contorno del ojo.
    inner, outer = [], []
    for i in range(65):
        a = i / 64 * 2 * math.pi
        ca, sa = math.cos(a), math.sin(a)
        upper = clamp01(sa)
        t = clamp01((ca * side + 1.0) * 0.5)
        # la pestaña tiene que ir claramente DELANTE de la esclerótica, o esta
        # la tapa: hay menos de un milímetro entre las dos
        w = 0.0018 + 0.0026 * upper + 0.0044 * (t ** 2.0) * upper
        inner.append((ctr.x + ca * EW * 0.965, fy - 0.0062, ctr.z + sa * EH * 0.965))
        outer.append((ctr.x + ca * (EW * 0.965 + w), fy - 0.0034,
                      ctr.z + sa * (EH * 0.965 + w)))
    V, F = loft([inner, outer], cap_start=False, cap_end=False)
    EYES.add(V, F, 2, smooth=True)

    # ceja
    b0, b1 = [], []
    for i in range(16):
        t = i / 15
        ang = math.pi * (0.92 - 0.84 * t)
        px = ctr.x + math.cos(ang) * EW * 1.34 * side
        pz = ctr.z + EH * 1.44 + math.sin(ang) * EH * 0.34
        sp = face_at(px, pz)
        byy = (sp.y if sp else fy) - 0.0014
        w = 0.0028 * (0.24 + 0.96 * math.sin(math.pi * clamp01(t * 1.05)) ** 0.55)
        b0.append((px, byy, pz - w))
        b1.append((px, byy - 0.0018, pz + w * 0.8))
    V, F = loft([b0, b1], cap_start=False, cap_end=False)
    EYES.add(V, F, 3, smooth=True)


build_eye(L_EYE, 1)
build_eye(R_EYE, -1)
OJOS = EYES.finish("Alonso_Ojos", EYE_MATS)
OJOS.game.physics_type = 'NO_COLLISION'
print(f"[AL] ojos planos (calcomanía): {len(OJOS.data.polygons)} caras")

# ----------------------------------------------------------------- PELO
# MEDIDO sobre peinados CC0 profesionales (conocimiento/09): un corte corto son
# 3 PIEZAS y ~1.300 triángulos. El pelo anterior de Alonso tenía 7.784 en 73
# trozos sueltos, y en silueta leía como un fleco de púas, no como una masa.
#
# Así que las púas NO son conos independientes: son parte de UNA superficie
# continua cuyo BORDE se modula para acabar en puntas. La silueta la define el
# contorno de esa superficie, que es exactamente lo que se juzga en la prueba.

NA_H = 40                      # azimuts
N_SCALP, N_FREE = 5, 6         # anillos pegados al cráneo + anillos libres
N_PICOS = 9                    # puntas alrededor de la silueta

HAIRLINE = [(0.00, math.radians(48)), (0.60, math.radians(43)),
            (1.05, math.radians(33)), (1.45, math.radians(16)),
            (2.10, math.radians(-2)), (3.15, math.radians(-16))]


def hairline_elev(a):
    aa = abs(((a + math.pi) % (2 * math.pi)) - math.pi)
    for i in range(len(HAIRLINE) - 1):
        a0, e0 = HAIRLINE[i]
        a1, e1 = HAIRLINE[i + 1]
        if aa <= a1:
            return lerp(e0, e1, (aa - a0) / (a1 - a0))
    return HAIRLINE[-1][1]


def pico(a):
    """Perfil de puntas: potencia alta = picos estrechos y valles anchos."""
    return (0.5 + 0.5 * math.cos(N_PICOS * a + 0.4)) ** 3.0


def esponja(a):
    """Volumen del pelo: más masa arriba y atrás, menos en la frente."""
    frente = clamp01(math.cos(a) * 0.5 + 0.5)
    return 1.0 - 0.45 * frente


# --- anillos pegados al cráneo, ajustados con Shrinkwrap -----------------------
tmp_v, tmp_f = [], []
for j in range(N_SCALP):
    t = j / (N_SCALP - 1)
    for i in range(NA_H):
        a = i / NA_H * 2 * math.pi
        e = lerp(math.radians(89.5), hairline_elev(a), t ** 0.80)
        tmp_v.append(HEAD_C + Vector((math.sin(a) * math.cos(e),
                                      -math.cos(a) * math.cos(e),
                                      math.sin(e))) * 0.150)
for j in range(N_SCALP - 1):
    for i in range(NA_H):
        i2 = (i + 1) % NA_H
        tmp_f.append([j * NA_H + i, j * NA_H + i2,
                      (j + 1) * NA_H + i2, (j + 1) * NA_H + i])
tm = bpy.data.meshes.new("tmp_cap")
tm.from_pydata([tuple(v) for v in tmp_v], [], tmp_f)
tm.update()
cap = bpy.data.objects.new("tmp_cap", tm)
bpy.context.collection.objects.link(cap)
sw = cap.modifiers.new("Ajuste", 'SHRINKWRAP')
sw.target = ob
sw.wrap_method = 'NEAREST_SURFACEPOINT'
sw.offset = 0.004
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = cap
cap.select_set(True)
bpy.ops.object.modifier_apply(modifier=sw.name)
scalp = [v.co.copy() for v in tm.vertices]
bpy.data.objects.remove(cap, do_unlink=True)

# --- una sola superficie: casquete + fleco de puntas ---------------------------
HV, HF = [], []
for j in range(N_SCALP):
    for i in range(NA_H):
        a = i / NA_H * 2 * math.pi
        p = scalp[j * NA_H + i]
        n = (p - HEAD_C)
        n.z *= 0.72
        n.normalize()
        t = j / (N_SCALP - 1)
        # volumen: crece del cuero cabelludo hacia el borde, con relieve de mechón
        vol = (0.006 + 0.042 * esponja(a) * math.sin(t * math.pi * 0.70) ** 0.7
               + 0.016 * pico(a) * t)
        HV.append(tuple(p + n * vol))

borde = [Vector(HV[(N_SCALP - 1) * NA_H + i]) for i in range(NA_H)]
for j in range(1, N_FREE + 1):
    t = j / N_FREE
    for i in range(NA_H):
        a = i / NA_H * 2 * math.pi
        base = borde[i]
        n = (base - HEAD_C)
        n.z *= 0.72
        n.normalize()
        # la punta baja, se despega y se afila; su largo lo marca `pico`
        frente = clamp01(math.cos(a) * 0.5 + 0.5)      # 1 justo en la frente
        largo = ((0.026 + 0.072 * pico(a)) * esponja(a)
                 + 0.024 * frente ** 1.9)                  # flequillo: muere SOBRE la ceja
        caida = Vector((n.x * 0.38, n.y * 0.38, -0.94)).normalized()
        p = base + caida * (largo * t) + n * (largo * 0.30 * t * (1 - t))
        HV.append(tuple(p))

filas = N_SCALP + N_FREE
for j in range(filas - 1):
    for i in range(NA_H):
        i2 = (i + 1) % NA_H
        HF.append([j * NA_H + i, j * NA_H + i2,
                   (j + 1) * NA_H + i2, (j + 1) * NA_H + i])
HF.append(list(range(NA_H))[::-1])                     # tapa de la coronilla

hm = bpy.data.meshes.new("Alonso_Pelo")
hm.from_pydata(HV, [], HF)
hm.update()
for poly in hm.polygons:
    poly.use_smooth = True
hm.materials.append(PELO)
PELO_OB = bpy.data.objects.new("Alonso_Pelo", hm)
bpy.context.collection.objects.link(PELO_OB)
PELO_OB.game.physics_type = 'NO_COLLISION'

import bmesh as _bm
_b = _bm.new()
_b.from_mesh(hm)
_vis, _pz = set(), 0
for v in _b.verts:
    if v.index in _vis:
        continue
    _pz += 1
    pila = [v]
    _vis.add(v.index)
    while pila:
        x = pila.pop()
        for e in x.link_edges:
            o2 = e.other_vert(x)
            if o2.index not in _vis:
                _vis.add(o2.index)
                pila.append(o2)
_b.free()
print(f"[AL] pelo: {len(hm.polygons)} caras, {_pz} pieza(s) "
      f"(objetivo medido: 3-5 piezas, ~1.500 tris)")

# --------------------------------------------------- NORMALES ESFERIZADAS
# El "blob face" (conocimiento/11): una cara cartoon no está esculpida como se
# la va a iluminar, así que nariz, cejas y cuencas tiran sombras rotas que
# delatan el 3D. La solución profesional es hacer que las normales de la cara
# apunten como si fuese una esfera lisa: la cara pasa a sombrear como un volumen
# limpio y la sombra queda de ilustración.
grupo = ob.vertex_groups.new(name="CaraNormales")
R_CAB = (CROWN_Z - CHIN_Z) * 0.5
centro = Vector((0.0, HEAD_C.y + R_CAB * 0.30, (CROWN_Z + CHIN_Z) * 0.5))
for v in ob.data.vertices:
    p_ = v.co
    if p_.z < CHIN_Z - 0.02 or p_.y > centro.y:
        continue
    # peso máximo en plena cara, desvaneciendo hacia sienes y mandíbula
    dz = abs(p_.z - EYE_Z) / (R_CAB * 1.35)
    dx = abs(p_.x) / (R_CAB * 1.15)
    w_ = clamp01(1.0 - math.sqrt(dx * dx + dz * dz))
    if w_ > 0.001:
        grupo.add([v.index], w_ ** 0.7, 'REPLACE')

esf = bpy.data.meshes.new("EsferaNormales")
_ev, _ef = ico(4)
esf.from_pydata([(x * R_CAB * 1.02 + centro.x, y * R_CAB * 1.02 + centro.y,
                  z * R_CAB * 1.02 + centro.z) for (x, y, z) in _ev], [], _ef)
esf.update()
for poly in esf.polygons:
    poly.use_smooth = True
esfera = bpy.data.objects.new("EsferaNormales", esf)
bpy.context.collection.objects.link(esfera)

dt = ob.modifiers.new("EsferizarNormales", 'DATA_TRANSFER')
dt.object = esfera
dt.use_loop_data = True
dt.data_types_loops = {'CUSTOM_NORMAL'}
dt.loop_mapping = 'POLYINTERP_NEAREST'
dt.vertex_group = "CaraNormales"
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
try:
    bpy.ops.object.modifier_apply(modifier=dt.name)
    print("[AL] normales de la cara esferizadas")
except Exception as e:
    print("[AL] no se pudo esferizar:", e)
bpy.data.objects.remove(esfera, do_unlink=True)

# El cuerpo NO proyecta sombra sobre sí mismo: en este estilo la nariz no
# mancha la mejilla. El pelo SÍ sigue proyectando sobre la cara, que es una
# sombra deseable y característica.
ob.visible_shadow = False

# --------------------------------------------------- CONTORNO (casco invertido)
# Material negro con Backface Culling + Solidify de grosor NEGATIVO y normales
# invertidas: el casco crece hacia fuera y solo se ven sus caras traseras, que
# aparecen como línea negra alrededor de la silueta (conocimiento/11).
# El grosor va en unidades de MUNDO, así que se calibra a la escala del
# personaje: 1,68 m -> ~1,2 mm.
CONTORNO = bpy.data.materials.new("M_Contorno")
CONTORNO.use_nodes = True
_nt = CONTORNO.node_tree
for _n in list(_nt.nodes):
    _nt.nodes.remove(_n)
_o = _nt.nodes.new("ShaderNodeOutputMaterial")
_e = _nt.nodes.new("ShaderNodeEmission")
_e.inputs["Color"].default_value = (0.02, 0.015, 0.02, 1.0)
_nt.links.new(_e.outputs["Emission"], _o.inputs["Surface"])
CONTORNO.use_backface_culling = True
CONTORNO.diffuse_color = (0, 0, 0, 1)

for _obj, _gr in ((ob, 0.0013), (PELO_OB, 0.0016), (OJOS, 0.0006)):
    if _obj is None:
        continue
    _obj.data.materials.append(CONTORNO)
    _idx = len(_obj.data.materials) - 1
    _m = _obj.modifiers.new("Contorno", 'SOLIDIFY')
    _m.thickness = -_gr
    _m.offset = 1.0
    _m.use_flip_normals = True
    _m.use_rim = False
    _m.material_offset = _idx
    _m.material_offset_rim = _idx
print("[AL] contorno de casco invertido aplicado")

ob.game.physics_type = 'NO_COLLISION'
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[AL] guardado: {OUT_BLEND}")
print(f"[AL] total caras: {sum(len(m.polygons) for m in bpy.data.meshes)}")
print("[AL] OK")
