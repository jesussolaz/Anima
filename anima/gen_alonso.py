# ÁNIMA — Alonso Quijano (protagonista)
#
# Herramienta de EDITOR (bpy). El .blend sale SIN Python.
#   Flipendo --background --factory-startup --python gen_alonso.py
# Salida: ~/Flipendo/game/anima/Alonso.blend
#
# ARPG estilizado tipo JRPG/Kingdom Hearts. 15-16 años, 1,68 m, 7,15 cabezas.
# El personaje mira hacia -Y (vista frontal de Blender).
#
# La cara no se saca de una esfera deformada: se loftea desde perfiles
# (frente, lateral, nuca) y luego se esculpe con campos de desplazamiento.
# Es la única forma de que el perfil lea como una cara y no como un huevo.

import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Matrix, Vector, Euler, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
for _m in ("anima_kit",):
    if _m in sys.modules:
        del sys.modules[_m]
from anima_kit import (                                            # noqa: E402
    Build, catmull, cam, clamp01, clear_scene, disc, falloff, flat, hair_lock,
    ico, lathe, leaf_section, lerp, loft, make_mat, mirror_x, rgb, smoothstep,
    sweep, transport_frames, tube)

random.seed(1605)

OUT_DIR = os.path.expanduser("~/Flipendo/game/anima")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_BLEND = os.path.join(OUT_DIR, "Alonso.blend")

# ----------------------------------------------------------------- proporciones
H_TOTAL = 1.680
Z_ANKLE, Z_KNEE, Z_CROTCH = 0.075, 0.435, 0.790
Z_WAIST, Z_CHEST, Z_SHOULDER = 1.020, 1.205, 1.360
Z_NECK, Z_CHIN, Z_CROWN = 1.408, 1.445, 1.680
HEAD_H = Z_CROWN - Z_CHIN                       # 0.235
SHOULDER_X = 0.158                              # articulación del hombro
EYE_Z = Z_CHIN + 0.100
EYE_X = 0.0305

M = dict(PIEL=0, PELO=1, OJO_BLANCO=2, OJO_IRIS=3, PESTANA=4, TELA_AZUL=5,
         TELA_CREMA=6, CUERO=7, METAL=8, PANUELO=9, LABIO=10, CEJA=11,
         TELA_ROJA=12, CUERO_OSC=13, ACERO=14, MADERA=15, BOCA=16)


def pbr(name, color, rough=0.6, metallic=0.0, spec=0.5, sss=0.0,
        sss_color=None, sss_radius=None, emit=None, emit_str=0.0,
        clearcoat=0.0, anisotropic=0.0, sheen=0.0, ior=1.45):
    """Principled PBR. Cada familia de material se diferencia por su
    respuesta especular, no solo por el color base."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metallic
    b.inputs["IOR"].default_value = ior

    def setif(sock, val):
        if sock in b.inputs:
            b.inputs[sock].default_value = val

    setif("Specular IOR Level", spec)
    if sss > 0.0:
        setif("Subsurface Weight", sss)
        if sss_radius:
            setif("Subsurface Radius", sss_radius)
        if sss_color:
            setif("Subsurface Color", (*sss_color, 1.0))
        setif("Subsurface Scale", 0.012)
    if clearcoat > 0.0:
        setif("Coat Weight", clearcoat)
        setif("Coat Roughness", 0.18)
    if anisotropic > 0.0:
        setif("Anisotropic", anisotropic)
        setif("Anisotropic Rotation", 0.25)
    if sheen > 0.0:
        setif("Sheen Weight", sheen)
        setif("Sheen Roughness", 0.4)
    if emit is not None:
        setif("Emission Color", (*emit, 1.0))
        setif("Emission Strength", emit_str)
    m.diffuse_color = (*color, 1.0)
    return m


def micro(mat, scale=340.0, amt=0.030, rough_lo=None, rough_hi=None):
    """Microrrelieve procedural por bump + variación de aspereza. Es lo que
    separa la tela del cuero cuando no hay texturas pintadas."""
    nt = mat.node_tree
    b = nt.nodes.get("Principled BSDF")
    tex = nt.nodes.new("ShaderNodeTexNoise")
    tex.inputs["Scale"].default_value = scale
    tex.inputs["Detail"].default_value = 8.0
    tex.inputs["Roughness"].default_value = 0.65
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = amt
    bump.inputs["Distance"].default_value = 0.0016
    nt.links.new(tex.outputs["Fac"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], b.inputs["Normal"])
    if rough_lo is not None:
        t2 = nt.nodes.new("ShaderNodeTexNoise")
        t2.inputs["Scale"].default_value = scale * 0.09
        t2.inputs["Detail"].default_value = 5.0
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = rough_lo
        rr.inputs["To Max"].default_value = rough_hi
        nt.links.new(t2.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], b.inputs["Roughness"])
    return mat


clear_scene()
sc = bpy.context.scene
sc.name = "Alonso"

SKIN = pbr("M_Piel", (0.855, 0.660, 0.545), rough=0.44, spec=0.42,
           sss=0.16, sss_color=(0.86, 0.42, 0.32),
           sss_radius=(0.030, 0.011, 0.0075))
micro(SKIN, scale=620.0, amt=0.020, rough_lo=0.36, rough_hi=0.55)

HAIR = pbr("M_Pelo", (0.135, 0.070, 0.042), rough=0.30, spec=0.55,
           anisotropic=0.72, clearcoat=0.42)
micro(HAIR, scale=90.0, amt=0.055)

MATS = [
    SKIN,
    HAIR,
    pbr("M_OjoBlanco", (0.90, 0.885, 0.885), rough=0.16, spec=0.6,
        sss=0.10, sss_color=(0.85, 0.55, 0.50)),
    pbr("M_OjoIris", (0.115, 0.245, 0.185), rough=0.08, spec=1.0, ior=1.38,
        clearcoat=0.9),
    pbr("M_Pestana", (0.045, 0.028, 0.024), rough=0.34, spec=0.4),
    micro(pbr("M_TelaAzul", (0.086, 0.132, 0.245), rough=0.74, spec=0.30,
              sheen=0.35), 420.0, 0.055, 0.66, 0.84),
    micro(pbr("M_TelaCrema", (0.72, 0.66, 0.545), rough=0.78, spec=0.28,
              sheen=0.45), 480.0, 0.060, 0.70, 0.88),
    micro(pbr("M_Cuero", (0.196, 0.115, 0.062), rough=0.50, spec=0.45,
              clearcoat=0.18), 300.0, 0.075, 0.40, 0.62),
    pbr("M_Metal", (0.735, 0.615, 0.335), rough=0.26, metallic=1.0),
    micro(pbr("M_Panuelo", (0.475, 0.105, 0.098), rough=0.66, spec=0.34,
              sheen=0.55), 520.0, 0.050, 0.58, 0.76),
    pbr("M_Labio", (0.735, 0.470, 0.435), rough=0.36, spec=0.5, sss=0.22,
        sss_color=(0.86, 0.40, 0.34), sss_radius=(0.032, 0.012, 0.008)),
    pbr("M_Ceja", (0.115, 0.062, 0.040), rough=0.42, spec=0.35),
    micro(pbr("M_TelaRoja", (0.352, 0.078, 0.070), rough=0.72, spec=0.30,
              sheen=0.40), 440.0, 0.055, 0.64, 0.82),
    micro(pbr("M_CueroOscuro", (0.095, 0.058, 0.038), rough=0.44, spec=0.5,
              clearcoat=0.22), 300.0, 0.080, 0.34, 0.56),
    pbr("M_Acero", (0.560, 0.575, 0.600), rough=0.19, metallic=1.0),
    micro(pbr("M_Madera", (0.255, 0.150, 0.078), rough=0.55, spec=0.4), 200.0, 0.05),
    pbr("M_Boca", (0.135, 0.062, 0.058), rough=0.45, spec=0.3),
]


# ================================================================= CABEZA
# Local de cabeza: origen en la base del mentón, -Y = frente, Z arriba.

def tab(table, z):
    if z <= table[0][0]:
        return table[0][1:]
    for i in range(len(table) - 1):
        z0, z1 = table[i][0], table[i + 1][0]
        if z <= z1:
            t = (z - z0) / (z1 - z0)
            return tuple(lerp(table[i][1 + k], table[i + 1][1 + k], t)
                         for k in range(len(table[0]) - 1))
    return table[-1][1:]


#      z      frente   lateral   nuca    semiancho
HEAD_TAB = [
    (0.000, -0.0330, -0.0210, 0.0130, 0.0210),   # base del mentón, ancho y blando
    (0.014, -0.0530, -0.0180, 0.0300, 0.0330),
    (0.028, -0.0605, -0.0130, 0.0430, 0.0430),   # mandíbula
    (0.044, -0.0648, -0.0075, 0.0570, 0.0525),
    (0.060, -0.0678, -0.0028, 0.0690, 0.0605),   # boca
    (0.076, -0.0700,  0.0012, 0.0782, 0.0665),   # base de la nariz
    (0.092, -0.0714,  0.0040, 0.0842, 0.0706),
    (0.105, -0.0718,  0.0054, 0.0872, 0.0722),   # eje de los ojos
    (0.120, -0.0716,  0.0060, 0.0892, 0.0730),
    (0.132, -0.0704,  0.0062, 0.0902, 0.0732),   # ceja
    (0.148, -0.0682,  0.0058, 0.0904, 0.0728),   # frente
    (0.166, -0.0644,  0.0050, 0.0892, 0.0712),
    (0.184, -0.0584,  0.0035, 0.0860, 0.0676),
    (0.200, -0.0498,  0.0012, 0.0808, 0.0620),
    (0.214, -0.0378, -0.0026, 0.0716, 0.0522),
    (0.226, -0.0222, -0.0072, 0.0570, 0.0372),
    (0.235,  0.0000, -0.0105, 0.0260, 0.0095),   # coronilla
]

NA, NZ = 72, 40
EYE_CZ = 0.1055                     # centro del ojo en local de cabeza
EYE_HW, EYE_HH = 0.0232, 0.0150     # semiejes del hueco


def eye_mask(x, z):
    """<1 dentro del hueco del ojo. Almendra con lagrimal bajo y rabillo alto."""
    ax = abs(x)
    u = (ax - EYE_X) / EYE_HW
    v = (z - EYE_CZ - 0.0022 * u) / EYE_HH
    # el párpado superior sube más en el centro; el inferior es más plano
    vv = v / (1.0 + 0.30 * clamp01(-v))
    return math.sqrt(u * u * (1.0 + 0.10 * max(vv, 0.0)) + vv * vv)


def head_base():
    rings = []
    for j in range(NZ):
        t = j / (NZ - 1)
        z = 0.235 * (t ** 0.94)
        fy, sy, by, w = tab(HEAD_TAB, z)
        ring = []
        for i in range(NA):
            a = i / NA * 2 * math.pi
            c, s = math.cos(a), math.sin(a)
            if c >= 0.0:
                y = lerp(fy, sy, (1.0 - c) ** 1.55)     # cara plana
            else:
                y = lerp(sy, by, (-c) ** 0.80)          # cráneo redondo
            ring.append([w * s, y, z])
        rings.append(ring)
    return rings


def sculpt_head(p):
    x, y, z = p
    ax = abs(x)
    sgn = 1.0 if x >= 0 else -1.0
    front = clamp01(-y / 0.052)
    out = Vector((x, y, z))

    # cuenca: hundido suave alrededor del hueco, para que el ojo se asiente
    m = falloff(eye_mask(x, z) / 1.55, 1.0) * front
    out.y += 0.0072 * m

    # párpado superior: reborde carnoso justo encima del hueco
    u = (ax - EYE_X) / 0.0300
    v = (z - (EYE_CZ + EYE_HH + 0.0042)) / 0.0075
    m = falloff(math.sqrt(u * u + v * v * 1.4), 1.0) * front
    out.y -= 0.0040 * m

    # arco superciliar
    u = (ax - 0.0300) / 0.0430
    v = (z - 0.1300) / 0.0140
    m = falloff(math.sqrt(u * u + v * v * 1.6), 1.0) * front
    out.y -= 0.0058 * m

    # pómulo alto y ancho: juventud
    u = (ax - 0.0510) / 0.0300
    v = (z - 0.0830) / 0.0250
    m = falloff(math.sqrt(u * u + v * v), 1.0)
    out.y -= 0.0042 * m
    out.x += 0.0050 * m * sgn

    # sien
    u = (ax - 0.0705) / 0.0215
    v = (z - 0.1380) / 0.0240
    out.x -= 0.0038 * falloff(math.sqrt(u * u + v * v), 1.0) * sgn

    # ángulo mandibular
    u = (ax - 0.0555) / 0.0260
    v = (z - 0.0370) / 0.0215
    m = falloff(math.sqrt(u * u + v * v), 1.0)
    out.x += 0.0034 * m * sgn
    out.y += 0.0020 * m

    # mentón redondeado, no en punta
    u = ax / 0.0230
    v = (z - 0.0165) / 0.0200
    out.y -= 0.0044 * falloff(math.sqrt(u * u + v * v), 1.0) * front

    # surco bajo el labio
    u = ax / 0.0180
    v = (z - 0.0435) / 0.0090
    out.y += 0.0026 * falloff(math.sqrt(u * u + v * v), 1.0) * front

    # filtro
    u = ax / 0.0062
    v = (z - 0.0672) / 0.0072
    out.y += 0.0014 * falloff(math.sqrt(u * u + v * v), 1.0) * front

    # aletas de la nariz
    u = (ax - 0.0128) / 0.0092
    v = (z - 0.0718) / 0.0080
    out.y -= 0.0026 * falloff(math.sqrt(u * u + v * v), 1.0) * front

    if y > 0.02 and z > 0.14:
        out.y += 0.0028 * falloff(abs(z - 0.180) / 0.058, 1.0)
    return tuple(out)


HEAD = Build()
_rings = [[sculpt_head(p) for p in r] for r in head_base()]

# Loft de la cabeza SALTÁNDOSE las caras del hueco de cada ojo. Sin agujero real
# el globo se queda enterrado: es la misma técnica que la boca del horno.
_hv = []
for r in _rings:
    _hv.extend(r)
_hf = []
for j in range(NZ - 1):
    for i in range(NA):
        i2 = (i + 1) % NA
        a, b = j * NA, (j + 1) * NA
        quad = [a + i, a + i2, b + i2, b + i]
        cx = sum(_hv[k][0] for k in quad) / 4.0
        cy = sum(_hv[k][1] for k in quad) / 4.0
        cz = sum(_hv[k][2] for k in quad) / 4.0
        _ = (cx, cy, cz)      # cabeza SIN agujero: el ojo va como parche
        _hf.append(quad)
_hf.append(list(range((NZ - 1) * NA, NZ * NA)))          # tapa de la coronilla
HEAD.add(_hv, _hf, M["PIEL"], Matrix.Translation((0, 0, Z_CHIN)), smooth=True)


def face_pt(x, z):
    """Superficie de la cara en (x, z). TIENE que usar la misma
    parametrización que el loft: la malla recorre el ángulo (x = w·sin a,
    mezcla (1-cos a)^1.55). Si aquí se usa |x|/w, este punto queda casi 2 cm
    por detrás de la malla real y todo lo que se apoye en él (ojos, pestañas,
    cejas) se entierra dentro de la cabeza."""
    fy, sy, by, w = tab(HEAD_TAB, z)
    a = math.asin(clamp01(abs(x) / max(w, 1e-6)))
    return Vector(sculpt_head((x, lerp(fy, sy, (1.0 - math.cos(a)) ** 1.55), z)))


def rim_point(phi, side=1):
    """Punto del borde del ojo (donde eye_mask==1) en la dirección phi."""
    cx = EYE_X * side
    lo, hi = 0.2, 2.2
    for _ in range(14):
        mid = (lo + hi) * 0.5
        if eye_mask(cx + math.cos(phi) * EYE_HW * mid * side,
                    EYE_CZ + math.sin(phi) * EYE_HH * mid) < 1.0:
            lo = mid
        else:
            hi = mid
    s = (lo + hi) * 0.5
    return (cx + math.cos(phi) * EYE_HW * s * side,
            EYE_CZ + math.sin(phi) * EYE_HH * s)


NRIM = 48

# ================================================================= OJOS
# El ojo NO es una esfera asomando por un agujero: recortar un hueco en una
# malla de rejilla deja el borde en escalera. Es un PARCHE almendrado que se
# apoya en la cara y abomba hacia fuera. El contorno lo define el parche, así
# que sale limpio, y encima va la pestaña, que es la firma del estilo.

EYES = Build()
OFF = Matrix.Translation((0, 0, Z_CHIN))


def build_eye(side):
    sx = 1.0 if side > 0 else -1.0
    cx, cz = EYE_X * sx, EYE_CZ
    rim = [rim_point(i / NRIM * 2 * math.pi, side) for i in range(NRIM)]

    def patch(scale_list, bulge_max, mat, tint=None, extra=0.0):
        rings = []
        for s in scale_list:
            ring = []
            for (px, pz) in rim:
                qx, qz = cx + (px - cx) * s, cz + (pz - cz) * s
                b = bulge_max * (1.0 - s * s) ** 0.62 + extra
                ring.append((qx, face_pt(qx, qz).y - 0.0006 - b, qz))
            rings.append(ring)
        V, F = loft(rings, cap_start=False, cap_end=True)
        EYES.add(V, F, mat, OFF, smooth=True, tint=tint)

    # esclerótica: el parche completo
    patch([1.0, 0.90, 0.76, 0.58, 0.38, 0.16], 0.0042, M["OJO_BLANCO"])

    # iris: disco abombado sobre el parche, ligeramente ovalado en vertical
    IR = 0.0122

    def patch_y(px, pz):
        """Superficie del parche del ojo: hay que seguir su curvatura o el
        iris se entierra por un lado y sale una lágrima en vez de un disco."""
        sm = min(eye_mask(px, pz), 1.0)
        return face_pt(px, pz).y - 0.0006 - 0.0042 * (1.0 - sm * sm) ** 0.62

    def iris_ring(s, lift):
        out = []
        for i in range(32):
            a = i / 32 * 2 * math.pi
            px = cx + math.cos(a) * IR * s
            pz = cz + math.sin(a) * IR * s * 1.06
            out.append((px, patch_y(px, pz) - lift, pz))
        return out

    for (ss, mat, tint) in (((1.00, 0.94), M["OJO_IRIS"], (0.20, 0.22, 0.24)),
                            ((0.94, 0.62), M["OJO_IRIS"], (1.00, 1.06, 1.00)),
                            ((0.62, 0.34), M["OJO_IRIS"], (1.70, 1.85, 1.65)),
                            ((0.34, 0.10), M["BOCA"], (0.16, 0.16, 0.16))):
        r0 = iris_ring(ss[0], 0.0008 + 0.0016 * (1 - ss[0]))
        r1 = iris_ring(ss[1], 0.0008 + 0.0016 * (1 - ss[1]))
        V, F = loft([r0, r1], cap_start=False, cap_end=True)
        EYES.add(V, F, mat, OFF, smooth=True, tint=rgb(tint))

    # brillos
    for (hx, hz, hr, hi) in ((-0.0052, 0.0068, 0.0040, 11.0),
                             (0.0062, -0.0056, 0.0020, 3.5)):
        hv, hf = ico(2)
        hcx, hcz = cx + hx * sx, cz + hz
        hcy = patch_y(hcx, hcz) - 0.0026
        hv = [(x * hr + hcx, y * hr * 0.5 + hcy, z * hr + hcz)
              for (x, y, z) in hv]
        EYES.add(hv, hf, M["OJO_BLANCO"], OFF, smooth=True, tint=rgb((hi, hi, hi)))

    # PESTAÑA superior: gruesa, remontando en el rabillo
    r0, r1 = [], []
    for k in range(NRIM + 1):
        t = k / NRIM
        phi = math.pi * t
        px, pz = rim_point(phi, side)
        outer = 1.0 - t if side > 0 else 1.0 - t
        w = (0.0012 + 0.0092 * (outer ** 2.2)
             + 0.0034 * math.sin(math.pi * t) ** 1.1)
        d = Vector((px - cx, 0.0, pz - cz))
        d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
        base = face_pt(px, pz)
        r0.append((px - d.x * 0.0018, base.y - 0.0034, pz - d.z * 0.0018))
        r1.append((px + d.x * w * 0.5, base.y - 0.0042, pz + d.z * w))
    V, F = loft([r0, r1], cap_start=False, cap_end=False)
    EYES.add(V, F, M["PESTANA"], OFF, smooth=True)

    # pestaña inferior, mucho más fina
    r0, r1 = [], []
    for k in range(NRIM + 1):
        phi = math.pi + math.pi * (k / NRIM)
        px, pz = rim_point(phi, side)
        d = Vector((px - cx, 0.0, pz - cz))
        d = d.normalized() if d.length > 1e-6 else Vector((0, 0, 1))
        base = face_pt(px, pz)
        fade = math.sin(math.pi * (k / NRIM)) ** 0.8      # se desvanece en las esquinas
        w = 0.0004 + 0.0011 * fade
        r0.append((px - d.x * 0.0004, base.y - 0.0026, pz - d.z * 0.0004))
        r1.append((px + d.x * w, base.y - 0.0029, pz + d.z * w))
    V, F = loft([r0, r1], cap_start=False, cap_end=False)
    EYES.add(V, F, M["PESTANA"], OFF, smooth=True, tint=rgb((0.55, 0.55, 0.55)))

    # ceja
    bctrl = [(0.0132, 0.1338), (0.0254, 0.1400), (0.0402, 0.1402),
             (0.0530, 0.1348), (0.0600, 0.1278)]
    bp = catmull([Vector((p[0] * sx, 0.0, p[1])) for p in bctrl], 18)
    b0, b1 = [], []
    for i, p in enumerate(bp):
        t = i / (len(bp) - 1)
        w = 0.0038 * (0.28 + 0.92 * math.sin(math.pi * clamp01(t * 1.04)) ** 0.5)
        base = face_pt(p.x, p.z)
        b0.append((p.x, base.y - 0.0014, p.z - w))
        b1.append((p.x, base.y - 0.0036, p.z + w * 0.78))
    V, F = loft([b0, b1], cap_start=False, cap_end=False)
    EYES.add(V, F, M["CEJA"], OFF, smooth=True)


build_eye(1)
build_eye(-1)

# --------------------------------------------------------------- nariz
_nb = face_pt(0.0, 0.0740)
nose_path = catmull([(0.0, _nb.y + 0.0038, 0.0895),
                     (0.0, _nb.y - 0.0026, 0.0832),
                     (0.0, _nb.y - 0.0070, 0.0770),
                     (0.0, _nb.y - 0.0084, 0.0724),
                     (0.0, _nb.y - 0.0044, 0.0678)], 10)
nsc = [(0.0036, 0.0048), (0.0050, 0.0062), (0.0070, 0.0074),
       (0.0088, 0.0074), (0.0092, 0.0054)]
_nv, _nf = sweep(nose_path, leaf_section(10, 1.0, 0.90),
                 scales=[nsc[min(int(i / 10 * 5), 4)] for i in range(10)],
                 caps=True, up_hint=(1, 0, 0))
HEAD.add(_nv, _nf, M["PIEL"], OFF, smooth=True)

# --------------------------------------------------------------- labios
_lp = face_pt(0.0, 0.0575)
lip_rings = []
for (zz, ww, dd, yy) in ((0.0620, 0.0100, 0.0012, 0.0016),
                         (0.0596, 0.0132, 0.0034, -0.0012),
                         (0.0572, 0.0138, 0.0024, -0.0009),
                         (0.0546, 0.0128, 0.0036, -0.0004),
                         (0.0516, 0.0094, 0.0016, 0.0020)):
    ring = []
    for i in range(22):
        a = i / 22 * 2 * math.pi
        c, s = math.cos(a), math.sin(a)
        ring.append((ww * s, _lp.y + yy - dd * max(c, 0.0) * (1.0 - 0.48 * abs(s) ** 1.5)
                     + 0.0012 * min(c, 0.0), zz))
    lip_rings.append(ring)
_lv, _lf = loft(lip_rings, cap_start=True, cap_end=True)
HEAD.add(_lv, _lf, M["LABIO"], OFF, smooth=True)

# --------------------------------------------------------------- orejas
EAR_PROF = [(-0.0195, 0.0032, 0.0050), (-0.0110, 0.0086, 0.0098),
            (-0.0015, 0.0104, 0.0120), (0.0085, 0.0092, 0.0110),
            (0.0165, 0.0058, 0.0074), (0.0215, 0.0020, 0.0034)]
ear_rings = []
for (dz, hy, hx) in EAR_PROF:
    ear_rings.append([(hx * (0.35 + 0.65 * max(math.cos(i / 14 * 2 * math.pi), -0.35)),
                       hy * math.cos(i / 14 * 2 * math.pi),
                       dz + hy * 0.85 * math.sin(i / 14 * 2 * math.pi))
                      for i in range(14)])
_ev, _ef = loft(ear_rings, cap_start=True, cap_end=True)
for s in (1, -1):
    vv, ff = (_ev, _ef) if s > 0 else mirror_x(_ev, _ef)
    HEAD.add(vv, ff, M["PIEL"],
             Matrix.Translation((0.0668 * s, 0.0150, Z_CHIN + 0.1010))
             @ Matrix.Rotation(math.radians(-13 * s), 4, 'Y')
             @ Matrix.Rotation(math.radians(9 * s), 4, 'Z'), smooth=True)


# ================================================================= PELO
# Dos reglas: el mechón sigue un FLUJO (no la normal del cráneo, o sale erizo)
# y mantiene su grosor hasta afilarse al final (taper alto, o salen agujas).

HAIR_B = Build()
HEAD_C = Vector((0.0, 0.012, 0.130))

#            |a|      z de nacimiento del pelo
HAIRLINE = [(0.00, 0.1790), (0.55, 0.1762), (0.95, 0.1690),
            (1.35, 0.1520), (1.85, 0.1280), (2.45, 0.1030), (3.15, 0.0910)]


def hairline_z(a):
    return tab(HAIRLINE, abs(((a + math.pi) % (2 * math.pi)) - math.pi))[0]


def skull(a, z, off=0.0):
    fy, sy, by, w = tab(HEAD_TAB, z)
    c, s = math.cos(a), math.sin(a)
    y = lerp(fy, sy, (1.0 - c) ** 1.55) if c >= 0 else lerp(sy, by, (-c) ** 0.80)
    p = Vector(sculpt_head((w * s, y, z)))
    n = p - HEAD_C
    n.z *= 0.70
    n.normalize()
    return p + n * off, n


def lock(a, z, dirv, L, bend=(0, 0, 0), w0=0.020, w1=0.0016, thick=0.68,
         off=0.006, twist=0.0, segs=8, root_out=0.10, taper=2.8):
    anchor, n = skull(a, z, off)
    d = Vector(dirv).normalized()
    pts = [anchor + n * (L * root_out * (1.0 - (1.0 - i / (segs - 1)) ** 2))
           + d * (L * (i / (segs - 1))) + Vector(bend) * ((i / (segs - 1)) ** 2)
           for i in range(segs)]
    V, F = hair_lock(pts, w0=w0, w1=w1, thick=thick, n=13, twist_amt=twist,
                     up_hint=(n.x, n.y, n.z), taper=taper)
    HAIR_B.add(V, F, M["PELO"], OFF, smooth=True)


# casquete pegado al cráneo, naciendo en la línea del pelo
cap_rings = []
for j in range(13):
    t = j / 12
    cap_rings.append([tuple(skull(i / 56 * 2 * math.pi,
                                 lerp(0.2345, hairline_z(i / 56 * 2 * math.pi), t ** 0.86),
                                 0.0060 + 0.0050 * math.sin(t * math.pi) ** 0.8)[0])
                      for i in range(56)])
cv, cf = loft(cap_rings, cap_start=False, cap_end=False)
HAIR_B.add(cv, cf, M["PELO"], OFF, smooth=True)

# FLEQUILLO: cuñas cortas sobre la frente, con raya y barrido a un lado.
# Muere por encima de las cejas: si las tapa, se pierde la mirada.
for k in range(11):
    t = (k - 5) / 5.0
    a = t * 0.92
    z = hairline_z(a) + 0.016
    L = 0.042 + 0.016 * (1.0 - abs(t)) + random.uniform(-0.003, 0.003)
    lock(a, z, (t * 0.26 + 0.30, -0.42, -0.86), L,
         bend=(t * 0.008 + 0.005, -0.006, -0.008),
         w0=0.0150 + 0.0050 * (1.0 - abs(t)), thick=0.58,
         twist=random.uniform(-0.2, 0.2), off=0.0075, root_out=0.10, taper=3.0)

# mechones que enmarcan la cara, por delante de las orejas
for side in (-1, 1):
    for k in range(2):
        a = side * (1.22 + k * 0.20)
        lock(a, hairline_z(a) + 0.010 - k * 0.008,
             (side * 0.30, -0.22, -0.93), 0.082 + k * 0.018,
             bend=(side * 0.006, -0.003, -0.012), w0=0.0116, thick=0.54,
             twist=side * 0.2, off=0.006, root_out=0.08, taper=3.2)

# PÚAS de la coronilla: arriba y atrás, no en abanico
SPIKES = [
    (0.00, 0.2320, (0.04, 0.62, 0.78), 0.072),
    (0.52, 0.2290, (0.30, 0.58, 0.76), 0.068),
    (-0.52, 0.2290, (-0.30, 0.58, 0.76), 0.068),
    (1.05, 0.2225, (0.48, 0.46, 0.74), 0.062),
    (-1.05, 0.2225, (-0.48, 0.46, 0.74), 0.062),
    (1.60, 0.2150, (0.58, 0.32, 0.75), 0.056),
    (-1.60, 0.2150, (-0.58, 0.32, 0.75), 0.056),
    (2.25, 0.2175, (0.38, 0.70, 0.60), 0.064),
    (-2.25, 0.2175, (-0.38, 0.70, 0.60), 0.064),
    (2.78, 0.2135, (0.16, 0.86, 0.48), 0.068),
    (-2.78, 0.2135, (-0.16, 0.86, 0.48), 0.068),
    (3.14, 0.2095, (0.00, 0.92, 0.38), 0.064),
]
for (a, z, d, L) in SPIKES:
    lock(a, z, d, L, bend=(d[0] * 0.014, 0.020, -0.014), w0=0.0210, thick=0.74,
         twist=random.uniform(-0.25, 0.25), off=0.009, root_out=0.14, taper=2.7)
    lock(a + 0.26, z - 0.012, (d[0] * 0.92, d[1] * 0.90, d[2] * 0.84), L * 0.72,
         bend=(d[0] * 0.010, 0.014, -0.012), w0=0.0146, thick=0.68,
         twist=random.uniform(-0.25, 0.25), off=0.008, root_out=0.12, taper=2.9)

# capa media, para que entre púa y púa haya pelo y no cuero cabelludo
for k in range(18):
    a = -math.pi + (k / 18) * 2 * math.pi + 0.11
    z = lerp(0.206, hairline_z(a) + 0.026, 0.34 + 0.20 * abs(math.sin(k * 1.3)))
    _, n = skull(a, z, 0.0)
    lock(a, z, (n.x * 0.38, n.y * 0.38 + 0.30, -0.62 if abs(a) < 1.4 else 0.18),
         0.040 + random.uniform(0.0, 0.014), bend=(n.x * 0.004, 0.008, -0.005),
         w0=0.0118, thick=0.62, twist=random.uniform(-0.3, 0.3),
         off=0.005, root_out=0.08, taper=3.0)

# NUCA
for k in range(11):
    t = (k - 5) / 5.0
    a = math.pi + t * 0.95
    lock(a, hairline_z(a) + 0.030, (t * 0.22, 0.30, -0.92),
         0.052 + 0.018 * (1.0 - abs(t)), bend=(t * 0.004, 0.008, -0.010),
         w0=0.0126, thick=0.62, twist=random.uniform(-0.2, 0.2),
         off=0.006, root_out=0.08, taper=3.0)


# ================================================================= ESCENA
# Cabeza, ojos y pelo como objetos separados (el pelo necesita su propio
# shader y sus propios huesos secundarios; los ojos, su propio rig).
CAB = HEAD.finish("Alonso_Cabeza", MATS)
OJO = EYES.finish("Alonso_Ojos", MATS)
PEL = HAIR_B.finish("Alonso_Pelo", MATS)
for ob in (CAB, OJO, PEL):
    ob.game.physics_type = 'NO_COLLISION'

world = bpy.data.worlds.new("W_Estudio")
sc.world = world
world.use_nodes = True
wn = world.node_tree.nodes["Background"]
wn.inputs["Color"].default_value = (0.30, 0.34, 0.42, 1.0)
wn.inputs["Strength"].default_value = 0.55


def area(name, loc, energy, color, size=0.5, target=(0, 0, EYE_Z)):
    d = bpy.data.lights.new(name, 'AREA')
    d.energy, d.color, d.size = energy, color, size
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    o.game.physics_type = 'NO_COLLISION'
    return o


area("Key", (-0.45, -0.70, 1.78), 22.0, (1.00, 0.92, 0.84), 0.55)
area("Fill", (0.55, -0.55, 1.55), 7.0, (0.72, 0.80, 1.00), 0.70)
area("Rim", (0.35, 0.62, 1.80), 16.0, (1.00, 0.80, 0.62), 0.40)

cam("CamRetrato", (0.0, -0.62, EYE_Z), (0, 0, EYE_Z - 0.005), lens=85, clip_end=50)
cam("Cam34", (-0.40, -0.47, EYE_Z + 0.03), (0, 0, EYE_Z - 0.01), lens=85, clip_end=50)
cam("CamPerfil", (-0.62, 0.02, EYE_Z), (0, 0, EYE_Z - 0.01), lens=85, clip_end=50)
sc.camera = bpy.data.objects["CamRetrato"]

sc.render.resolution_x, sc.render.resolution_y = 900, 1100
for _e in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = _e
        break
    except TypeError:
        continue
try:
    sc.view_settings.view_transform = 'AgX'
except TypeError:
    sc.view_settings.view_transform = 'Standard'
try:
    sc.eevee.taa_render_samples = 128
    sc.eevee.use_raytracing = True
    sc.eevee.ray_tracing_options.use_denoise = True
except AttributeError:
    pass
sc.game_settings.fps = 60

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("[ALONSO] guardado:", OUT_BLEND)
print("[ALONSO] caras:", sum(len(m.polygons) for m in bpy.data.meshes))
print("[ALONSO] OK")
