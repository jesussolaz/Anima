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
    Build, catmull, clamp01, clump_section, fino_section, hair_lock, ico, lerp,
    loft, smoothstep, sweep)

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
# Centro del cráneo: desde aquí se mide la latitud de la banda de brillo.
CENTRO_CRANEO = (0.0, 0.0, EYE_Z + 0.34 * (CROWN_Z - EYE_Z))


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
         aniso=False, usa_col=False, umbral=0.62, spec_col=None,
         banda_z=None):
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

    if usa_col:
        # El atributo "Col" que escribe Build.add NO se leía: todos los tint=
        # se perdían en silencio, y por eso el iris solo tenía dos colores
        # (verde y el marrón de la ceja) en vez de anillo limbal, cuerpo,
        # realce y pupila. Va MULTIPLICANDO la rampa, no sustituyéndola, para
        # no perder las bandas del cel. Es opt-in porque un objeto sin la capa
        # devolvería negro, y la malla del cuerpo no la tiene.
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(salida, mul.inputs["A"])
        nt.links.new(vc.outputs["Color"], mul.inputs["B"])
        salida = mul.outputs["Result"]

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
        # El umbral decide el GROSOR de la banda. A 0,62 con el glossy ancho
        # del pelo la banda se comía media cabeza y, siendo un ADD gris sobre
        # castaño oscuro, salía blanco rosáceo: leía como calvas, no como brillo.
        gramp.color_ramp.elements[1].position = umbral
        # el brillo del pelo es el propio color aclarado, no gris: un ADD gris
        # desatura y rompe la gama
        sc_ = spec_col if spec_col is not None else (1.0, 1.0, 1.0)
        gramp.color_ramp.elements[1].color = (sc_[0] * spec, sc_[1] * spec,
                                              sc_[2] * spec, 1.0)
        add = nt.nodes.new("ShaderNodeMix")
        add.data_type = 'RGBA'
        add.blend_type = 'ADD'
        add.inputs["Factor"].default_value = 1.0
        nt.links.new(gl.outputs["BSDF"], g2r.inputs["Shader"])
        nt.links.new(g2r.outputs["Color"], gramp.inputs["Fac"])
        nt.links.new(salida, add.inputs["A"])
        nt.links.new(gramp.outputs["Color"], add.inputs["B"])
        salida = add.outputs["Result"]

    if banda_z is not None:
        # BRILLO DEL PELO. No es un reflejo: en anime es un elemento de DISEÑO,
        # una banda a una ALTURA FIJA de la cabeza que no se mueve con la luz.
        # Con un glossy salían tres manchas sueltas siguiendo los huecos entre
        # mechones —leían como calvas— y subir el umbral casi no las estrechó,
        # porque el lóbulo satura sobre una superficie tan ancha.
        # Va por LATITUD alrededor del centro del cráneo, no por altura: una
        # banda de Z plana corta la cabeza en línea recta y lee como una cinta.
        # Tomando la dirección desde el centro y midiendo su componente Z sale
        # un paralelo de esfera, que de frente arquea hacia abajo por los lados
        # —que es como se dibuja.
        centro, lat, grosor, bcol = banda_z
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        res = nt.nodes.new("ShaderNodeVectorMath"); res.operation = 'SUBTRACT'
        res.inputs[1].default_value = centro
        nt.links.new(geo.outputs["Position"], res.inputs[0])
        nor = nt.nodes.new("ShaderNodeVectorMath"); nor.operation = 'NORMALIZE'
        nt.links.new(res.outputs["Vector"], nor.inputs[0])
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(nor.outputs["Vector"], sep.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = lat - 0.50
        mr.inputs["From Max"].default_value = lat + 0.50
        nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
        br = nt.nodes.new("ShaderNodeValToRGB")
        br.color_ramp.interpolation = 'CONSTANT'
        br.color_ramp.elements[0].position = 0.0
        br.color_ramp.elements[0].color = (0, 0, 0, 1)
        br.color_ramp.elements[1].position = 0.5 - grosor
        br.color_ramp.elements[1].color = (*bcol, 1.0)
        e2 = br.color_ramp.elements.new(0.5 + grosor)
        e2.color = (0, 0, 0, 1)
        nt.links.new(mr.outputs["Result"], br.inputs["Fac"])
        # se apaga en la zona en sombra: una banda que brilla en el lado oscuro
        # delata que es un truco
        puerta = nt.nodes.new("ShaderNodeValToRGB")
        puerta.color_ramp.interpolation = 'CONSTANT'
        puerta.color_ramp.elements[0].position = 0.0
        puerta.color_ramp.elements[0].color = (0.12, 0.12, 0.12, 1)
        puerta.color_ramp.elements[1].position = 0.50
        puerta.color_ramp.elements[1].color = (1, 1, 1, 1)
        nt.links.new(s2r.outputs["Color"], puerta.inputs["Fac"])
        gate = nt.nodes.new("ShaderNodeMix")
        gate.data_type = 'RGBA'; gate.blend_type = 'MULTIPLY'
        gate.inputs["Factor"].default_value = 1.0
        nt.links.new(br.outputs["Color"], gate.inputs["A"])
        nt.links.new(puerta.outputs["Color"], gate.inputs["B"])
        sumb = nt.nodes.new("ShaderNodeMix")
        sumb.data_type = 'RGBA'; sumb.blend_type = 'ADD'
        sumb.inputs["Factor"].default_value = 1.0
        nt.links.new(salida, sumb.inputs["A"])
        nt.links.new(gate.outputs["Result"], sumb.inputs["B"])
        salida = sumb.outputs["Result"]

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
            spec=0.0,
            banda_z=(CENTRO_CRANEO, 0.60, 0.055, (0.30, 0.20, 0.12)))
ESCLERA = toon("M_Esclera", (0.97, 0.965, 0.975), bandas=2, fuerza=0.88,
               usa_col=True)
IRIS = toon("M_Iris", (0.150, 0.400, 0.320), bandas=2, fuerza=0.72, spec=0.9,
            usa_col=True)
PESTANA = toon("M_Pestana", (0.085, 0.050, 0.048), bandas=2, fuerza=0.85)
CEJA = toon("M_Ceja", (0.260, 0.130, 0.070), bandas=2, fuerza=0.80,
            usa_col=True)
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

    # El iris anime es MÁS GRANDE que el hueco del ojo y el párpado se lo come
    # por arriba: ocupa ~70 % del ojo visible y su borde superior se mete
    # debajo del párpado. Antes el iris medía 25 mm en un hueco de 35 y dejaba
    # blanco por los CUATRO lados: eso es la mirada de muñeco que prohíbe
    # conocimiento/02. No se podía agrandar porque nada lo recortaba, así que
    # el recorte se hace aquí, contra la elipse de la abertura.
    IR = 0.0190
    IZ = 0.0030                       # sube: comido arriba, filo de blanco abajo

    def recorta(x, z, k=1.0):
        """Empuja el punto al borde de la abertura si se sale de ella."""
        u, v = (x - ctr.x) / EW, (z - ctr.z) / EH
        r = math.hypot(u, v)
        if r <= k:
            return x, z
        return ctr.x + u / r * k * EW, ctr.z + v / r * k * EH

    # cada anillo se recorta un pelo más adentro que el anterior: si dos caen
    # justo en el mismo borde salen caras de área cero y el sombreado se pica
    for (s0, s1, mat, tint) in ((1.00, 0.88, 1, (0.16, 0.18, 0.22)),
                                (0.88, 0.52, 1, (1.00, 1.06, 1.00)),
                                (0.52, 0.42, 1, (1.85, 2.00, 1.80)),
                                (0.42, 0.08, 3, (0.10, 0.10, 0.12))):
        anillo = []
        for (s, k) in ((s0, 1.000), (s1, 0.994)):
            pts = ell(IR * s, IR * s * 1.04, 0.0050 + 0.0012 * (1 - s), 30)
            anillo.append([(lambda cx, cz: (cx, y, cz))(*recorta(x, z + IZ, k))
                           for (x, y, z) in pts])
        V, F = loft(anillo, cap_start=False, cap_end=True)
        EYES.add(V, F, mat, smooth=True, tint=tint)
    # los brillos crecen con el iris, o se pierden dentro de él
    for (hx, hz, hr, hi) in ((-0.0064, 0.0094, 0.0047, 14.0),
                             (0.0072, -0.0040, 0.0024, 4.0)):
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
# v10. MEDIDO sobre peinados CC0 (conocimiento/09: Quaternius SimpleParted y
# VRoid HairSample_Male, cabeza de 253 mm como la de Alonso) y sobre la silueta
# del v9 con herramientas/medir_silueta_pelo.py:
#
#  - El VOLUMEN va en los MECHONES, no en el casquete. El v9 inflaba el
#    casquete 23 mm de mediana por igual en todo el azimut (VRoid 13,5 mm,
#    Quaternius 7,3) y eso ES la "bolsa de plástico": una cáscara hinchada no
#    tiene cantos. Ahora el casquete queda a ~8 mm de la piel y son los
#    mechones los que se separan (VRoid: raíz 9,5 mm, cuerpo 26, cresta 51).
#  - El perfil de volumen tiene FORMA: coronilla 1,5x más que las sienes (Sora
#    KH3 como principio de estructura), ancho máximo a la altura del techo del
#    cráneo y cintura en las sienes. El v9 lo tenía invertido (arriba 19 mm,
#    sienes 40, ancho máximo en la fila de los ojos): seta/casco.
#  - JERARQUÍA: 9 principales + medianos (hijas) + finos + 4 sueltos, con
#    anchos 1 : 0,5 : 0,25 : 0,12. Los 25 mechones del v9 eran del mismo nivel
#    (el "cactus" de las guías de dibujo: muchos iguales = plano y cargado).
#  - Los laterales del v9 eran CUCHILLAS por causa mecánica: up_hint = nor x f
#    ponía el eje ancho de la cuña tangente al cráneo, así que el mechón que
#    baja por la oreja enseñaba el canto a la cámara frontal. Remedio: giro0
#    (la sección arranca girada), comba (arqueo lateral) y giro_punta (la S).
#
# Ronda 2 (jueces sobre v10r1i8): la coronilla vista de perfil era una cúpula
# lisa con 2-3 pinchos (capa 60-120 de 12 mm; criterio 32-40), la nuca una
# campana con dobladillo recto, los laterales altos un abanico casi horizontal
# (11 grados) y había dos ventanas de piel detrás de las orejas. Lo que se
# cambió y POR QUÉ está en cada bloque; la lección grande fue la de las
# ventanas: no faltaba pelo, el casquete estaba HUNDIDO (ver "cuerdas").

NA_H = 32                      # azimuts del casquete
N_SCALP = 8                    # filas pegadas al cráneo (coronilla -> línea del pelo)
# 8 y no 4: las filas se reparten por elevación desde HEAD_C, que está 180 mm
# POR DELANTE del occipucio, así que en la nuca dos filas consecutivas caían a
# (y 24, z 121) y (62, 31) mm y la cuerda entre ellas cortaba 7-9 mm por
# dentro del bulto: el cráneo asomaba en piel por la bóveda trasera (v10r1i3
# e i4, comprobado pintando la piel de verde). El v9 no lo veía porque inflaba
# el casquete 23 mm. Coste: +256 tris respecto a 4 filas.
N_FREE, N_NUCA = 3, 2          # filas de la lámina de flequillo y de la de nuca
A_RAYA = 0.12                  # raya descentrada 18 mm hacia +X (7 % del ancho de cara, Sora)
VIENTO = 0.20                  # viento común: la coronilla se inclina a +X (rad)
LADO_SALVAJE = +1              # +X: es el lado que ve la cámara Tres4 de rtoon.py

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


def esponja(a):
    """Reparto del (poco) grosor del casquete: algo más atrás que en la frente."""
    frente = clamp01(math.cos(a) * 0.5 + 0.5)
    return 1.0 - 0.45 * frente


def wrap(a):
    """Ángulo a (-pi, pi]."""
    return ((a + math.pi) % (2 * math.pi)) - math.pi


def girar(v, eje, ang):
    """Rota el vector v alrededor de eje (Rodrigues)."""
    v = Vector(v)
    k = Vector(eje).normalized()
    c, s = math.cos(ang), math.sin(ang)
    return v * c + k.cross(v) * s + k * (k.dot(v) * (1.0 - c))


def pseudo_normal(q):
    """Normal 'de globo' del casquete: radial desde el centro de la cabeza con la
    z achatada. No es la normal real de la malla, pero es continua y no tiene
    los pliegues de la piel de MakeHuman, que es lo que importa para lanzar
    mechones desde ella."""
    nn = (q - HEAD_C)
    nn.z *= 0.72
    nn.normalize()
    return nn


# --- anillos pegados al cráneo, ajustados con Shrinkwrap -----------------------
# El Shrinkwrap va SIN offset y todo el despegue se hace después por la normal
# real (normal_real). Con offset 3 mm los puntos de la nuca, que caen DENTRO
# de la cabeza en la esfera de 150 mm (el occipucio está a 178 mm de HEAD_C),
# se desplazaban hacia el lado de origen, o sea hacia dentro: la nuca quedaba
# a 4 mm de la piel y la cuerda entre filas cortaba el bulto (medido con
# distancia con signo al BVH limpio, v10r1i6: -2,5 mm en la arista 2-3 de
# a=pi). Subir la esfera a 250 mm lo arreglaba pero cambiaba dónde engancha
# cada fila y movía 20 mm la línea del pelo: todo el peinado afinado se iba.
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
sw.offset = 0.0
bpy.ops.object.select_all(action='DESELECT')
bpy.context.view_layer.objects.active = cap
cap.select_set(True)
bpy.ops.object.modifier_apply(modifier=sw.name)
scalp = [v.co.copy() for v in tm.vertices]
bpy.data.objects.remove(cap, do_unlink=True)


def normal_real(q):
    """Normal de la PIEL bajo q (BVH limpio, construido antes del Solidify del
    contorno: el objeto evaluado lleva una cáscara con normales invertidas y
    engaña a find_nearest). La pseudo-normal desde HEAD_C sirve para lanzar
    mechones, pero para despegar el casquete del cráneo no: en la nuca apunta
    casi horizontal y solo alejaba 3-5 mm de la piel en vez de 8."""
    loc, nor, _, _ = BVH.find_nearest(q)
    return nor.normalized() if nor is not None else pseudo_normal(q)


def dist_piel(q):
    """Distancia CON SIGNO de q a la piel (negativa = dentro de la cabeza)."""
    loc, nor, _, _ = BVH.find_nearest(q)
    if nor is None:
        return 1.0
    return (q - loc).dot(nor)

# --- casquete: la MASA, fina ---------------------------------------------------
# Tapa el cuero cabelludo y nada más. El v9 le sumaba 0,030·esponja·sin(...)
# y flotaba a 23 mm del cráneo (p95 30): tres veces más lejos que el corte
# profesional (Quaternius 7,3 mm, VRoid 13,5). Con 4 mm de Shrinkwrap más
# 4-8 mm aquí se queda en la banda de 8 ± 2 mm que pide el cap. 05.
HV, HF = [], []


def anade(V, F):
    base = len(HV)
    HV.extend(tuple(v) for v in V)
    HF.extend([[i + base for i in f] for f in F])


CAP = []
for j in range(N_SCALP):
    fila = []
    for i in range(NA_H):
        a = i / NA_H * 2 * math.pi
        q = scalp[j * NA_H + i]
        vol = 0.006 + 0.004 * esponja(a)      # 8-10 mm sobre la piel
        fila.append(q + normal_real(q) * vol)
    CAP.append(fila)

# --- cuerdas: ninguna arista del casquete pasa por dentro del cráneo ------------
# Los 32 azimuts se reparten desde HEAD_C, que está 128 mm por delante del
# centro del cráneo, así que en las esquinas traseras (a ≈ ±2,8) UN paso de
# azimut salta 76 mm en x y la cuerda entre dos columnas iba 10 mm por dentro
# del parietal: dos ventanas de piel de 55 x 135 mm detrás de las orejas
# vistas desde atrás (v10r1i8, render verde). Los jueces las leyeron como
# falta de lámina; un raycast desde esa cámara acertaba la cara 142 del
# casquete DETRÁS de la piel: el casquete estaba, hundido. Remuestrear los
# azimuts alrededor del centro real del cráneo lo arreglaba de raíz, pero
# movía la línea del pelo y el significado de `a` para los 40 mechones ya
# afinados. Se corrige a posteriori: el punto medio de cada arista (y el
# centro de cada quad) se mide contra la piel y, si queda a menos de 4 mm,
# sus vértices se empujan por la normal de la piel hasta que sale. Converge
# en 2-3 pasadas y solo toca las esquinas traseras.
CUERDAS_EMPUJADAS, CUERDAS_MAX = 0, 0.0
for _pasada in range(5):
    empuje = {}
    for j in range(N_SCALP):
        for i in range(NA_H):
            i2 = (i + 1) % NA_H
            grupos = [((j, i), (j, i2))]
            if j + 1 < N_SCALP:
                grupos.append(((j, i), (j + 1, i)))
                grupos.append(((j, i), (j, i2), (j + 1, i2), (j + 1, i)))
            for g in grupos:
                m = sum((CAP[jj][ii] for jj, ii in g), Vector()) / len(g)
                d = dist_piel(m)
                if d < 0.004:
                    for key in g:
                        empuje[key] = max(empuje.get(key, 0.0), 0.004 - d)
    if not empuje:
        break
    for (j, i), e in empuje.items():
        CAP[j][i] = CAP[j][i] + normal_real(CAP[j][i]) * e
        CUERDAS_EMPUJADAS += 1
        CUERDAS_MAX = max(CUERDAS_MAX, e)
print(f"[AL] pelo: cuerdas del casquete: {CUERDAS_EMPUJADAS} empujes "
      f"(máx {CUERDAS_MAX*1000:.1f} mm) para que ninguna arista corte el cráneo")

for fila in CAP:
    HV.extend(tuple(v) for v in fila)
for j in range(N_SCALP - 1):
    for i in range(NA_H):
        i2 = (i + 1) % NA_H
        HF.append([j * NA_H + i, j * NA_H + i2,
                   (j + 1) * NA_H + i2, (j + 1) * NA_H + i])
HF.append(list(range(NA_H))[::-1])                     # tapa de la coronilla
N_TRIS_CAP = sum(len(f) - 2 for f in HF)


def cap_pt(a, t):
    """Punto y normal sobre el casquete: de ahí arranca cada mechón.
    t=0 coronilla, t=1 línea del pelo."""
    fi = (a % (2 * math.pi)) / (2 * math.pi) * NA_H
    i0 = int(math.floor(fi)) % NA_H
    i1 = (i0 + 1) % NA_H
    fx = fi - math.floor(fi)
    fj = clamp01(t) * (N_SCALP - 1)
    j0 = min(int(fj), N_SCALP - 1)
    j1 = min(j0 + 1, N_SCALP - 1)
    fy = fj - j0
    q = (CAP[j0][i0].lerp(CAP[j0][i1], fx)).lerp(
        CAP[j1][i0].lerp(CAP[j1][i1], fx), fy)
    return q, pseudo_normal(q)


# --- láminas: flequillo delante y nuca detrás, NO alrededor ----------------------
# La lámina va DETRÁS de los mechones y hace dos cosas que ellos no pueden:
# tapa el cuero cabelludo y proyecta UNA sombra sólida sobre la frente. Pero en
# el v9 daba la vuelta entera y colgaba como una falda por sienes y nuca, y con
# 38 % de componente normal el frente salía 52 mm por delante de la nariz
# (Quaternius: 36 mm por DETRÁS). Ahora hay dos arcos: frente 149 grados y
# nuca 90; en las sienes el casquete va desnudo y lo tapan los laterales
# bajos, que es la "cintura" del perfil de volumen.
#
# El borde se muestrea al DOBLE de azimuts que el casquete (12 quads de cap no
# dibujan cinco puntas) y la fila de costura es de triángulos. Las puntas del
# borde se colocan en los azimuts de los mechones de flequillo (PUNTAS_LAMINA):
# si la lámina y los mechones acaban en sitios distintos, cada mechón tira su
# propia sombra y la frente sale rayada (7 lenguas en r5-cara del v9).
PUNTAS_LAMINA = []      # se rellena con los azimuts del flequillo (3 P + 2 M)


def lamina(centro, semi, n_filas, z_borde_fn, k_normal, bulto=0.10, puntas=(),
           amp=0.005, ancho_punta=0.11, d_max=None):
    """Lámina colgada del borde del casquete en el arco centro ± semi.
    z_borde_fn(a) da la z objetivo del borde (así el largo sale de la
    geometría real de la línea del pelo, no de un número a ciegas); `puntas`
    baja el borde `amp` en esos azimuts y lo sube `amp` entre ellos (dientes
    de ±5 mm en el flequillo, ±12 en la nuca: el dobladillo recto de la nuca
    del v10r1 era un corte 'bob' visto de espaldas). `d_max` pega la lámina al
    cráneo/cuello: ningún punto queda a más de esa distancia de la piel. Sin
    esto la lámina de nuca caía a plomo desde el occipucio y dejaba 50 mm de
    aire hasta el cuello (perfil v10r1i8: pared vertical de 89 mm)."""
    paso = 2 * math.pi / NA_H
    ks = [k for k in range(-2 * NA_H, 2 * NA_H + 1)
          if abs(k * paso * 0.5) <= semi + 1e-9]
    # los extremos del arco caen en azimuts del casquete (k par): si no, el
    # último medio quad queda colgando sin coser
    while ks and ks[0] % 2:
        ks.pop(0)
    while ks and ks[-1] % 2:
        ks.pop()
    base_c = {}            # k par: índice del vértice del casquete (fila última)
    fila0 = {}             # k: posición base sobre el borde del casquete

    def cap_idx(k):
        i = int(round((centro / paso) + k / 2)) % NA_H
        return (N_SCALP - 1) * NA_H + i

    for k in ks:
        if k % 2 == 0:
            base_c[k] = cap_idx(k)
            fila0[k] = Vector(HV[base_c[k]])
    for k in ks:
        if k % 2 != 0:
            p0 = Vector(HV[cap_idx(k - 1)])
            p1 = Vector(HV[cap_idx(k + 1)])
            fila0[k] = (p0 + p1) * 0.5
    filas = []
    for j in range(1, n_filas + 1):
        t = j / n_filas
        fila = {}
        for k in ks:
            a = wrap(centro + k * paso * 0.5)
            base = fila0[k]
            nn = pseudo_normal(base)
            caida = Vector((nn.x * k_normal, nn.y * k_normal, -1.0)).normalized()
            z_obj = z_borde_fn(a)
            if puntas:
                d = min(abs(wrap(a - p)) for p in puntas)
                z_obj += amp - 2.0 * amp * math.exp(-(d / ancho_punta) ** 2)
            largo = max(0.012, (base.z - z_obj) / -caida.z)
            q = (base + caida * (largo * t)
                 + nn * (largo * bulto * t * (1 - t)))
            if d_max is not None:
                loc, nor, _, _ = BVH.find_nearest(q)
                if nor is not None:
                    dd = (q - loc).dot(nor)
                    if dd > d_max:
                        q = q - nor * (dd - d_max)
                    elif dd < 0.006:
                        q = q + nor * (0.006 - dd)
            fila[k] = q
        filas.append(fila)
    # índices: fila j (1..n) -> nuevos vértices
    idx = [{k: base_c.get(k) for k in ks}]
    for fila in filas:
        d = {}
        for k in ks:
            d[k] = len(HV)
            HV.append(tuple(fila[k]))
        idx.append(d)
    # costura: triángulos entre la fila gruesa del casquete y la fila fina 1
    # (mismo sentido de giro que los quads del casquete: fila de arriba de
    # k a k+1 y vuelta por la de abajo; al revés, el Solidify del contorno
    # pintaba estos triángulos como manchas negras en nuca y flequillo)
    for k in ks[:-1]:
        if k % 2 == 0 and (k + 2) in idx[1]:
            c0, c1 = idx[0][k], idx[0][k + 2]
            f0, f1, f2 = idx[1][k], idx[1][k + 1], idx[1][k + 2]
            HF.append([c0, f1, f0])
            HF.append([c0, c1, f1])
            HF.append([c1, f2, f1])
    for j in range(1, n_filas):
        for k in ks[:-1]:
            HF.append([idx[j][k], idx[j][k + 1], idx[j + 1][k + 1], idx[j + 1][k]])
    return len(ks)


# --- mechones -------------------------------------------------------------------
# Segmentos por nivel: P 10, M 7, F 5, S 4. La espec daba 11/8/6/5 (3.778 tris
# con 39 piezas); los jueces pidieron 5 medianos y 2 finos más (cuerpo bajo
# los pinchos de coronilla, nuca dentada, detrás de las orejas) y con los
# segmentos de la espec la base se iba a 4.370. Un segmento menos por nivel
# (loft = (n_seg-1) x vértices x 2) deja 45 piezas en ~3.700. Coste por pieza:
# P 116, M 80, F 36, S 28.
NIVEL = {'P': (10, 'cuña'), 'M': (7, 'cuña'), 'F': (5, 'rombo'), 'S': (4, 'rombo')}


def mechon(a, t, largo, ancho, salida, flujo, twist=0.0, nivel='P', giro0=0.0,
           comba=0.0, clump=None, taper_ancho=4.0, taper_grosor=2.5,
           grosor=None, hundir=0.002, giro_punta=0.0, punta_fuera=0.20, **_):
    """Un mechón sobre el casquete. Devuelve (V, F, info).

    `salida`      cuánto se despega de la normal (VRoid: cuerpo a 26 mm).
    `giro0`       giro inicial de la sección: 0 = cara ancha hacia la normal.
    `comba`       arqueo lateral (x largo) en los puntos 2 y 3: quita la recta.
    `giro_punta`  la punta se dobla hacia -normal (la S de los laterales).
    `clump`       (punta_del_padre, k): el 4.o punto se acerca k a esa punta y
                  el desplazamiento se aplica con peso t^2 (convergencia
                  parabólica, como Clump/Shape del manual de Blender).
    `punta_fuera` cuánto de la salida conserva la PUNTA (0,20 = el mechón
                  vuelve hacia el cráneo y lee como arco; 0,55 = sigue
                  saliendo y lee como púa: en perfil las puntas de coronilla
                  quedaban por dentro de su propio ápice y no contaban).
    El afilado va SEPARADO por eje: ancho con t^4 (a t=0,8 queda el 60 %) y
    grosor con t^2,5 (el 44 %). Con taper 3,0 uniforme el v9 tenía la mitad del
    ancho a t=0,8 y cada mechón leía como triángulo desde la raíz."""
    n_seg, tipo = NIVEL[nivel]
    if grosor is None:
        grosor = 0.32 if tipo == 'cuña' else 0.50
    raiz0, nor = cap_pt(a, t)
    raiz = raiz0 - nor * hundir
    f = Vector(flujo).normalized()
    lado = nor.cross(f)
    if lado.length < 1e-6:
        lado = Vector((1.0, 0.0, 0.0))
    lado.normalize()
    gp = giro_punta
    f_mid = f * math.cos(gp * 0.5) - nor * math.sin(gp * 0.5)
    f_tip = f * math.cos(gp) - nor * math.sin(gp)
    C = [raiz,
         raiz + nor * (salida * largo * 0.55) + f * (largo * 0.18)
         + lado * (comba * largo * 0.55),
         raiz + nor * (salida * largo * 0.62) + f_mid * (largo * 0.60)
         + lado * (comba * largo),
         raiz + nor * (salida * largo * punta_fuera) + f_tip * largo
         + lado * (comba * largo * 0.35)]
    P = catmull(C, n_seg)
    if clump is not None:
        punta_padre, k = clump
        d = (Vector(punta_padre) - P[-1]) * k
        P = [p + d * ((i / (n_seg - 1)) ** 2) for i, p in enumerate(P)]
    sec = clump_section(1.0, grosor) if tipo == 'cuña' else fino_section(grosor)
    escalas, giros = [], []
    for i in range(n_seg):
        u = i / (n_seg - 1)
        escalas.append((ancho * lerp(1.0, 0.04, u ** taper_ancho),
                        ancho * lerp(1.0, 0.04, u ** taper_grosor)))
        giros.append(giro0 + twist * u)
    V, F = sweep(P, sec, escalas, giros, caps=True, up_hint=tuple(lado))
    # desviación del punto medio respecto a la cuerda raíz-punta (criterio: no
    # hay tiras rectas; >= 10 % del largo en P, >= 8 % en M)
    cuerda = P[-1] - P[0]
    m = P[len(P) // 2] - P[0]
    desv = (m - cuerda * (m.dot(cuerda) / max(1e-9, cuerda.length_squared))).length
    horiz = math.hypot(cuerda.x, cuerda.y)
    info = dict(raiz=P[0], punta=P[-1], desv=desv / largo, nor=nor, f=f,
                lado=lado, z_min=min(p.z for p in P),
                lejos=max((p - raiz0).length for p in P),
                elev=math.degrees(math.atan2(cuerda.z, horiz)),
                y_min=min(p.y for p in P))
    return V, F, info


# --- campo de flujo por zonas + largo por zona ----------------------------------
# Sora KH3 (principio, no dibujo): cada zona tiene una dirección dominante y
# todo el peinado comparte un "viento". Coronilla atrás-arriba, laterales
# altos fuera-arriba ~30 grados, laterales bajos fuera-abajo, nuca atrás-abajo
# y flequillo en dos abanicos desde la raya. El artículo de partículas lo llama
# "peinar por capas": dirección global + desviación propia de cada mechón.
# Tablas por |a| (x lleva el signo del lado, se aplica luego). Vectores ya
# normalizados aproximadamente; se normalizan al usarlos.
# Laterales altos (1,20): z 0,55 = 33 grados sobre la horizontal. Con el 0,24
# de la ronda 1 la cuerda de P6 subía 11 grados (criterio 25-40) y el viento
# (giro sobre Y hacia +X) lo tumbaba aún más mientras levantaba a P7: por eso
# ahora el viento solo actúa en la coronilla (|a| < 1,0) y los dos laterales
# altos comparten flujo; la asimetría va en largo y salida (criterio 16).
_LINEA = [(0.00, (0.00, -0.14, -0.85)), (0.95, (0.30, -0.14, -0.85)),
          (1.30, (0.30, 0.38, -0.87)), (1.90, (0.30, 0.40, -0.85)),
          (2.20, (0.10, 0.60, -0.78)), (3.15, (0.00, 0.60, -0.78))]
_BOVEDA = [(0.00, (0.00, 0.88, 0.34)), (0.95, (0.50, 0.82, 0.34)),
           (1.20, (0.72, 0.42, 0.55)), (1.60, (0.55, 0.60, 0.40)),
           (2.20, (0.10, 0.60, -0.50)), (3.15, (0.00, 0.60, -0.70))]
_LARGO = [(0.00, 0.064), (0.60, 0.076), (0.95, 0.088), (1.30, 0.096),
          (1.75, 0.092), (2.20, 0.100), (3.15, 0.090)]


def _tabla(tabla, aa):
    for i in range(len(tabla) - 1):
        a0, v0 = tabla[i]
        a1, v1 = tabla[i + 1]
        if aa <= a1:
            w = (aa - a0) / (a1 - a0)
            if isinstance(v0, tuple):
                return Vector([lerp(x, y, w) for x, y in zip(v0, v1)])
            return lerp(v0, v1, w)
    return Vector(tabla[-1][1]) if isinstance(tabla[-1][1], tuple) else tabla[-1][1]


def flujo_zona(a, t):
    """Dirección dominante en (a, t): mezcla de la tabla de la línea del pelo
    (t alto) y la de la bóveda (t bajo), con el signo del lado en x, el abanico
    del flequillo desde la raya y el viento común hacia +X en la coronilla."""
    a = wrap(a)
    aa, s = abs(a), (1.0 if a >= 0 else -1.0)
    linea = _tabla(_LINEA, aa)
    boveda = _tabla(_BOVEDA, aa)
    linea.x *= s
    boveda.x *= s
    if aa < 0.95:
        # flequillo: cae y se abre desde la raya (Sora: dos abanicos)
        linea.x = 0.25 * math.sin(1.7 * a) + 0.20 * (1.0 if a > A_RAYA else -1.0)
    # La mezcla empieza en t=0,70: con 0,55 los laterales altos (t 0,60-0,65)
    # heredaban el flujo descendente de la línea del pelo y salían planos.
    w = smoothstep(0.70, 0.90, t)
    v = boveda.lerp(linea, w)
    if aa < 1.0:
        # viento común: la coronilla se inclina hacia +X (cámara Tres4).
        # Rotación sobre Y; NO en los laterales altos (ver arriba).
        v = girar(v, (0.0, 1.0, 0.0), VIENTO * (1.0 - w))
    return v.normalized()


def largo_zona(a):
    return _tabla(_LARGO, abs(wrap(a)))


# --- racimos: principal + hijas + finos ------------------------------------------
# skyryedesign: los secundarios van "en el borde de los mayores (Δa), saliendo
# por debajo (Δt) o desprendiéndose en las puntas (clump)". CG Cookie: "los
# pequeños son copias reducidas de los medios". Metasequoia: los finos nacen de
# la mitad inferior del principal y mueren cerca de su punta.

def hijas(padre, deltas_a, k_largo=(0.75, 0.90), k_ancho=(0.58, 0.42),
          k_salida=1.2, giros=(0.20, -0.20), clump=0.5, extra=()):
    """Medianos a partir del dict del principal. `extra` permite sobreescribir
    campos de cada hija (los laterales bajos entran así, y con clump None:
    si se dejan converger hacia la punta del padre, que está 100 mm más
    arriba, salen hacia el cielo; costó una vuelta verlo).
    Los anchos alternan 0,58/0,42 (media 0,5 = shinrinmusic 0,51) para que
    dos hijas vecinas difieran >= 20 % en ancho aunque el largo se parezca.
    `k_salida` puede ser una tupla, una por hija: dos hijas con la misma
    salida y giros simétricos (±0,20) daban el 'ala de pájaro' del 3/4."""
    out = []
    for i, da in enumerate(deltas_a):
        ks = k_salida[i % len(k_salida)] if isinstance(k_salida, tuple) else k_salida
        h = dict(padre)
        h.update(nivel='M', grupo=padre['grupo'], padre=padre['nombre'],
                 nombre=f"{padre['nombre']}m{i + 1}",
                 a=padre['a'] + da, t=padre['t'] - 0.05,
                 largo=padre['largo'] * k_largo[i % len(k_largo)],
                 ancho=padre['ancho'] * k_ancho[i % len(k_ancho)],
                 salida=padre['salida'] * ks,
                 desv=padre.get('desv', 0.0) + giros[i % len(giros)],
                 twist=padre.get('twist', 0.0) + (0.15 if i % 2 == 0 else -0.15),
                 grosor=0.30, clump_k=clump, comba=padre.get('comba', 0.0) * 0.8)
        if i < len(extra) and extra[i]:
            h.update(extra[i])
        out.append(h)
    return out


def fino(padre, tipo, da=0.0, dt=0.0, k_largo=0.85, giro=0.35, **extra):
    """Fino (rombo de 4 vértices) colgado de un principal.
    'punta': bifurca la punta del padre (clump 0,8);  'borde': flyaway en el
    borde de la silueta;  'engranado': fila trasera, t - 0,10."""
    h = dict(padre)
    h.update(nivel='F', grupo=padre['grupo'], padre=padre['nombre'],
             nombre=f"{padre['nombre']}f_{tipo}", a=padre['a'] + da,
             t=padre['t'] + dt - (0.10 if tipo == 'engranado' else 0.0),
             largo=padre['largo'] * k_largo, ancho=padre['ancho'] * 0.25,
             salida=padre['salida'] * (1.2 if tipo == 'punta' else 1.4), twist=0.6,
             desv=padre.get('desv', 0.0) + giro, grosor=0.50,
             clump_k=(0.8 if tipo == 'punta' else None),
             comba=padre.get('comba', 0.0) * 0.5, giro0=padre.get('giro0', 0.0))
    if tipo == 'punta':
        h['a'] = padre['a'] + (0.05 if da == 0.0 else da)
        h['largo'] = padre['largo'] * 1.0
    h.update(extra)
    return h


def principal(nombre, grupo, a, t, largo, ancho, salida, **kw):
    d = dict(nombre=nombre, grupo=grupo, nivel='P', a=a, t=t, largo=largo,
             ancho=ancho, salida=salida, desv=0.0, twist=0.0, giro0=0.0,
             comba=0.0, grosor=0.32)
    d.update(kw)
    return d


# Coordenadas: a=0 es el frente (la cara mira a -Y), a=pi la nuca, a>0 el lado
# izquierdo del personaje (+X, el "salvaje": lo ve la cámara Tres4).
# Largos y anchos en metros (ancho = SEMIancho; ancho total = 2x).
# Rango de los principales: largo 52-145 mm, ancho total 34-64 mm (13-25 % del
# ancho de cara: raíz VRoid 19-40 mm por cuartiles, 65 máx). Los del flequillo
# van más cortos que los 64-88 mm de la primera espec porque la línea del pelo
# está a ~50 mm de los ojos y las puntas centrales tienen que quedar 5-20 mm
# POR ENCIMA de la línea de ojos (Quaternius: en la ceja).
S = LADO_SALVAJE
P = {}
# P1 y la hija exterior de P3 llevan flujo explícito: son las dos puntas que
# bajan por delante de la sien hasta el pómulo (30-45 mm bajo los ojos) y con
# el abanico de la zona (z -0,80) necesitarían 120-150 mm; más verticales
# llegan con 105-110. P1 con comba 0,16 y giro_punta 0,10 (S hacia el pómulo):
# con 0,09 era la tabla recta del lado izquierdo del render de cara (desv 7,9 %).
P['P1'] = principal('P1', 'flequillo', -0.75, 0.99, 0.105, 0.018, 0.08,
                    comba=0.16, desv=-0.12, twist=0.30, giro_punta=0.10,
                    flujo=(-0.42, -0.08, -0.90))
P['P2'] = principal('P2', 'flequillo', -0.10, 0.94, 0.070, 0.023, 0.09,
                    comba=0.13, desv=0.05, twist=-0.20)
P['P3'] = principal('P3', 'flequillo', 0.50, 0.97, 0.070, 0.029, 0.12,
                    comba=-0.11, desv=0.10, twist=0.30)
# Coronilla: nacen junto a la cima (t 0,18-0,28) y barren hacia atrás-arriba
# a ~25 grados abriéndose en abanico a ±X, de modo que el arco pasa sobre la
# cima y la punta llega sobre la bóveda trasera (plano de la oreja). Con
# t=0,45, 140 mm y 37 grados (primera espec) salía UN cuerno de 72 mm sobre
# el cráneo delante de la cima, con las cinco puntas juntas en x 0..+40 y la
# bóveda trasera desnuda (medido en v10r1i1/i2). Las hijas van POR DELANTE
# del padre (t mayor), escalonadas, para vestir la pendiente delantera.
# desv: girar sobre la normal (que aquí apunta arriba) con ángulo NEGATIVO
# lleva la punta hacia +X; se comprobó en la tabla (v10r1i3: P5 con -0,20
# acababa en x -15 en vez de abrirse a -X).
# Ronda 2: P4 es el DOMINANTE (145 mm, salida 0,38, punta_fuera 0,95) y P5 se
# queda en 95 mm con punta_fuera 0,60: en v10r1i8 los dos cuernos eran orejas
# de gato simétricas (puntas a z +190 y +193) y la mayor prominencia frontal
# caía en el ala P7 (-X), no en la coronilla del lado salvaje.
P['P4'] = principal('P4', 'coronilla', 0.55 * S, 0.22, 0.145, 0.030, 0.38,
                    comba=0.10, desv=-0.20 * S, twist=0.45, grosor=0.28,
                    punta_fuera=0.95)
P['P5'] = principal('P5', 'coronilla', -0.55 * S, 0.28, 0.095, 0.022, 0.30,
                    comba=-0.10, desv=0.25 * S, twist=-0.40, grosor=0.28,
                    punta_fuera=0.60)
# Laterales altos: t 0,72/0,68 (ronda 1: 0,65/0,60) para que el ancho máximo
# de la silueta caiga 70-120 mm sobre los ojos y no a 126; P6 más corto (100)
# y con más salida (0,40) para que la cuerda suba 25-40 grados en vez de 11 y
# el máximo 3D baje de 109 a <= 60 mm; P7 (lado tranquilo) 72 mm y salida 0,22
# para que su ala no mande sobre la coronilla (era la punta mayor, 54 mm).
P['P6'] = principal('P6', 'lat_alto', 1.20 * S, 0.72, 0.100, 0.024, 0.40,
                    giro0=0.70 * S, comba=0.12, desv=0.10, grosor=0.40)
P['P7'] = principal('P7', 'lat_alto', -1.20 * S, 0.68, 0.072, 0.018, 0.22,
                    giro0=-0.70 * S, comba=-0.12, desv=-0.10, grosor=0.40)
# Nuca: nacen a media bóveda trasera (t 0,36-0,50), no en la línea del pelo:
# con t 0,85-0,95 la bóveda trasera quedaba como cúpula lisa de casquete
# (v10r1i1, render 3/4) y el perfil daba 0 mm de capa en nuca alta. P8 con
# salida 0,28 y punta_fuera 0,80: punta propia de la bóveda trasera en perfil.
P['P8'] = principal('P8', 'nuca', math.pi - 0.40, 0.36, 0.130, 0.020, 0.28,
                    comba=0.07, desv=0.12, twist=-0.20, grosor=0.28,
                    punta_fuera=0.80)
P['P9'] = principal('P9', 'nuca', math.pi + 0.28, 0.50, 0.110, 0.015, 0.16,
                    comba=-0.09, desv=-0.10, twist=0.20, grosor=0.28)

# Laterales BAJOS: medianos y finos de P6/P7, no principales (Laovaan: lo del
# contorno exterior más fino que lo de delante). Van hacia fuera y abajo,
# pasan 10-20 mm POR DELANTE del borde anterior de la oreja (y = -72 mm) y
# acaban en la mandíbula (Sora: 85 % de ojo-mentón, nunca bajo el mentón;
# criterio: punta 105-125 mm bajo los ojos). giro0 los presenta de cara
# ancha; giro_punta dobla la punta hacia la mandíbula (S).
# La línea del pelo en a=±1,5 está 74 mm POR DELANTE de la oreja (la sien) y a
# z +10: por eso nacen a t 0,84 (z ≈ +35) y no en la línea del pelo, y van
# ATRÁS y abajo (y 0,28: con 0,38 la punta caía 24-29 mm delante de la oreja).
# Ronda 2: comba 0,12 y giro_punta 0,30 (con comba 0 y giro_punta 0,12 eran
# tablas rectas por construcción: desv 5-6 %, arista vertical de 51 mm en la
# silueta), y flujos DISTINTOS por lado para que no sean pares en espejo.
M_BAJO = dict(t=0.84, salida=0.20, grosor=0.40, giro_punta=0.30, twist=0.0,
              comba=0.12, clump_k=None)
LISTA = []
# NUCA. P8 (lado +X) y P9 (-X) con dos hijas cada uno: una a media nuca (t 0,6)
# que dibuja un diente del borde y otra detrás de la oreja (a = pi ∓ 0,78,
# t 0,80) que cuelga sobre el parietal y la parte trasera de la oreja (desde
# atrás se veía el cráneo entre el abanico lateral y la lámina). Δlargo >= 20 %
# entre vecinas.
LISTA += [P['P8'], P['P9']]
LISTA += hijas(P['P8'], (0.15, -0.38), k_largo=(0.66, 0.74), k_salida=(0.8, 0.45),
               giros=(0.20, -0.30),
               extra=(dict(t=0.60, twist=0.30, punta_fuera=0.30),
                      dict(t=0.80, twist=0.30, punta_fuera=0.25, giro0=0.5 * S,
                           flujo=(0.25 * S, 0.45, -0.86), clump_k=None)))
LISTA += hijas(P['P9'], (-0.18, 0.50), k_largo=(0.80, 0.92), k_salida=(0.9, 0.7),
               giros=(-0.25, 0.30),
               extra=(dict(t=0.62, twist=-0.30, punta_fuera=0.30),
                      dict(t=0.80, twist=-0.30, punta_fuera=0.25, giro0=-0.5 * S,
                           flujo=(-0.25 * S, 0.45, -0.86), clump_k=None)))
# Finos de nuca: cortos (k_largo 0,50/0,40) y hacia abajo (z -0,50): con 0,80 y
# flujo horizontal eran agujas de 77 mm que salían hacia atrás a la altura
# de la oreja y subían la capa 160-200 del perfil a 53 mm (criterio 30-38).
LISTA += [fino(P['P8'], 'punta'),
          fino(P['P8'], 'borde', da=0.32, dt=-0.16, k_largo=0.50, giro=0.30,
               flujo=(0.35, 0.72, -0.50), comba=0.08, twist=0.9),
          fino(P['P9'], 'engranado', da=-0.22, k_largo=0.40, giro=-0.35,
               flujo=(-0.30, 0.75, -0.50), comba=0.08, twist=0.9)]
# CORONILLA. P4 dominante con dos hijas de salida DISTINTA (x1,2 y x0,8) y
# giros asimétricos (0,35 / -0,45): dos hijas iguales con giros ±0,20 eran el
# abanico de 5 plumas del 3/4. P4m3 y P5m2 son las hijas "de bóveda": salen a
# a = ±1,35, t 0,30, tumbadas hacia atrás-arriba sobre la bóveda lateral, con
# la cara ancha hacia arriba. Son el CUERPO bajo los pinchos: de perfil la
# coronilla era una cúpula de casquete de 8 mm entre P4 y P5 (capa 60-120 de
# 12 mm; criterio 32-40).
LISTA += [P['P4'], P['P5']]
LISTA += hijas(P['P4'], (0.16 * S, -0.14 * S, 0.80 * S), k_largo=(0.65, 0.55, 0.62),
               k_ancho=(0.58, 0.42, 0.45), k_salida=(1.2, 0.8, 0.85),
               giros=(0.35, -0.45, 0.0),
               extra=(dict(t=0.34, punta_fuera=0.70),
                      dict(t=0.50, punta_fuera=0.55),
                      dict(t=0.30, punta_fuera=0.80, giro0=0.0, twist=0.20,
                           comba=0.10, clump_k=None,
                           flujo=(0.25 * S, 0.80, 0.50))))
LISTA += hijas(P['P5'], (-0.15 * S, -0.80 * S), k_largo=(0.50, 0.82),
               k_ancho=(0.45, 0.50), k_salida=(1.0, 1.0), giros=(0.35, 0.0),
               extra=(dict(t=0.40, punta_fuera=0.50, comba=0.12),
                      dict(t=0.30, punta_fuera=0.80, giro0=0.0, twist=-0.20,
                           comba=-0.10, clump_k=None,
                           flujo=(-0.25 * S, 0.80, 0.50))))
# Finos de coronilla: la punta bifurcada de P4, el flyaway entre P4 y P5 (a
# 0,05, alargado a 0,75: con 0,50 era la aguja de 116 grados que no sobresalía
# del valle) y dos flyaways nuevos en el borde a a = +0,95 y -1,10, t 0,15,
# con giro0 hacia -Y para que la cámara Cara los vea de cara ancha y no como
# astillas (cactus de cartón, v10r1i8-cara).
LISTA += [fino(P['P4'], 'punta'),
          fino(P['P4'], 'borde', da=-0.50 * S, dt=0.06, k_largo=0.75, giro=-0.30,
               salida=0.22, punta_fuera=0.4, giro0=0.5),
          fino(P['P4'], 'borde', da=0.40 * S, dt=-0.07, k_largo=0.45, giro=0.30,
               salida=0.45, punta_fuera=0.6, giro0=0.5, nombre='P4f_borde2'),
          fino(P['P5'], 'borde', da=-0.55 * S, dt=-0.13, k_largo=0.63, giro=-0.30,
               salida=0.45, punta_fuera=0.6, giro0=-0.5)]
# LATERALES ALTOS y BAJOS. P6m2 se aparta de P6 (da -0,25 en vez de -0,12) con
# salida x0,5: en v10r1i8 P6, P6m2 y P6f_borde formaban una masa continua de
# 54 mm sin muescas en el sector 20-60 de la silueta frontal.
LISTA += [P['P6'], P['P7']]
LISTA += hijas(P['P6'], (0.30 * S, -0.25 * S), k_largo=(1.42, 0.70), k_salida=(1.0, 0.5),
               extra=(dict(a=1.50 * S, largo=0.142, ancho=0.014, giro0=0.55 * S,
                           flujo=(0.30 * S, 0.28, -0.90), **dict(M_BAJO, salida=0.16)),
                      dict(t=0.60, punta_fuera=0.45)))
LISTA += hijas(P['P7'], (0.30 * S,),
               extra=(dict(a=-1.50 * S, largo=0.138, ancho=0.012, giro0=-0.30 * S,
                           flujo=(-0.22 * S, 0.40, -0.88), **dict(M_BAJO, giro_punta=0.35)),))
# Finos laterales: el 'bajo' de cada lado más ancho (0,009/0,007) y más hacia
# fuera (x 0,50) para que sobresalga >= 18 mm del valle y cuente como punta;
# giro0 1,0 para que no crucen la oreja como un palo de canto (3/4 v10r1i8).
LISTA += [fino(P['P6'], 'punta', da=0.15 * S, giro=0.5),
          fino(P['P6'], 'borde', da=-0.10 * S, dt=-0.12, k_largo=0.75, giro=0.40,
               salida=0.30),
          fino(P['P7'], 'borde', da=0.10 * S, dt=-0.12, k_largo=0.80, giro=-0.40,
               salida=0.30),
          fino(P['P6'], 'bajo', da=0.55 * S, dt=0.20, k_largo=1.20, giro=0.0,
               ancho=0.009, salida=0.20, grosor=0.5, giro0=1.0 * S, giro_punta=0.40,
               comba=0.08, flujo=(0.50 * S, 0.30, -0.80)),
          fino(P['P7'], 'bajo', da=-0.55 * S, dt=0.24, k_largo=1.64, giro=0.0,
               ancho=0.007, salida=0.20, grosor=0.5, giro0=-1.0 * S, giro_punta=0.40,
               comba=-0.08, flujo=(-0.45 * S, 0.38, -0.81))]
# FLEQUILLO. La hija exterior de P3 (P3m1) va a la sien (a +1,15, no +1,00) y
# más hacia fuera: en v10r1i8 tapaba el ojo cercano en la cámara Tres4 (punta
# en x +131, z -47). Ahora pasa por el pómulo exterior (|x| >= rabillo + 8).
LISTA += [P['P1'], P['P2'], P['P3']]
LISTA += hijas(P['P1'], (-0.10,), k_largo=(0.88,))
LISTA += hijas(P['P2'], (-0.13, 0.11), k_largo=(0.85, 0.93))
LISTA += hijas(P['P3'], (0.65, -0.14), k_largo=(1.0, 0.85), k_ancho=(0.47, 0.58),
               extra=(dict(t=0.99, largo=0.098, salida=0.16, desv=0.0, clump_k=None,
                           punta_fuera=0.35, flujo=(0.60, -0.12, -0.79)), None))
LISTA += [fino(P['P3'], 'punta'),
          fino(P['P1'], 'engranado', da=0.32, k_largo=0.80, giro=0.30)]
# Sueltos: una hebra cada uno (VRoid FAQ "stray hair", number of hairs = 1).
# Salida 0,35 y semiancho 5 (no 0,5 y 3,5): de canto eran astillas de 3 px.
for nombre, a, lg, an, g0 in (('S1', A_RAYA, 0.055, 0.0050, 0.5),
                              ('S2', 1.05 * S, 0.050, 0.0050, 0.5 * S),
                              ('S3', math.pi - 0.60, 0.045, 0.0040, 0.0),
                              ('S4', math.pi + 0.60, 0.045, 0.0035, 0.0)):
    LISTA.append(dict(nombre=nombre, grupo='suelto', nivel='S', a=a, t=0.99,
                      largo=lg, ancho=an, salida=0.35, desv=0.0, twist=0.4,
                      grosor=0.5, comba=0.04, giro0=g0))

# Puntas de la lámina de flequillo = azimuts de los 3 principales, la hija
# exterior de P3 y el fino engranado P1-P2 (5 puntas repartidas por el arco;
# las otras hijas están a 0,11-0,14 rad de su padre y se fundirían con él).
_POR_NOMBRE = {m['nombre']: m for m in LISTA}
PUNTAS_LAMINA = [_POR_NOMBRE[n]['a'] for n in
                 ('P1', 'P2', 'P3', 'P3m1', 'P1f_engranado')]
# Puntas de la lámina de nuca: los dos principales y sus hijas de media nuca
# (4 dientes de ±12 mm, ninguno a la misma altura que su vecino).
PUNTAS_NUCA = [_POR_NOMBRE[n]['a'] for n in ('P8', 'P9', 'P8m1', 'P9m1')]


def z_borde_frente(a):
    """z del borde de la lámina: 22 mm sobre los ojos en el centro y bajando
    hasta 35 mm por debajo en las sienes (a = ±1,30), donde ya es el pómulo."""
    w = smoothstep(0.55, 1.30, abs(a))
    return EYE_Z + lerp(0.022, -0.035, w)


def z_borde_nuca(a):
    """Borde de la lámina de nuca: 115 mm bajo los ojos en el centro (la nuca)
    subiendo hasta 50 mm bajo los ojos en los extremos (a = pi ± 0,80, el borde
    trasero de la oreja, que va de a 2,05 a 2,38), de modo que no cuelgue sobre
    la oreja: por encima y detrás de ella el casquete ya la cubre."""
    d = abs(wrap(a - math.pi)) / 0.80
    return EYE_Z - 0.115 + 0.065 * smoothstep(0.45, 1.0, d)


n_lam_f = lamina(0.0, 1.30, N_FREE, z_borde_frente, 0.15, bulto=0.10,
                 puntas=PUNTAS_LAMINA)
# Nuca: salida 0,08 y bulto 0,03 (ronda 1: 0,15 / 0,08, campana), dientes de
# ±12 mm en los azimuts de P8/P9 y sus hijas, y pegada al cuello (d_max 26 mm:
# VRoid nuca 17 % del cráneo = 37 mm de capa total con los mechones encima).
n_lam_n = lamina(math.pi, 0.80, N_NUCA, z_borde_nuca, 0.08, bulto=0.03,
                 puntas=PUNTAS_NUCA, amp=0.012, ancho_punta=0.16, d_max=0.026)
N_TRIS_MASA = sum(len(f) - 2 for f in HF)
print(f"[AL] pelo: masa = casquete {N_TRIS_CAP} tris + láminas "
      f"{N_TRIS_MASA - N_TRIS_CAP} tris ({n_lam_f} y {n_lam_n} azimuts finos)")

# --- expansión: el flujo de cada mechón = campo de zona girado su desviación ---
INFO = {}
TRIS = collections.Counter()
FILA_TABLA = []
for m in LISTA:
    if 'flujo' not in m:
        q, nor = cap_pt(m['a'], m['t'])
        m['flujo'] = tuple(girar(flujo_zona(m['a'], m['t']), nor, m.get('desv', 0.0)))
    clump = None
    if m.get('clump_k') and m.get('padre') in INFO:
        clump = (INFO[m['padre']]['punta'], m['clump_k'])
    V, F, info = mechon(clump=clump, **m)
    n0 = len(HF)
    anade(V, F)
    TRIS[m['nivel']] += sum(len(f) - 2 for f in HF[n0:])
    INFO[m['nombre']] = info
    FILA_TABLA.append((m, info))

# --- tabla y comprobaciones -------------------------------------------------------
print("[AL] pelo v10: tabla de mechones (mm; punta z respecto a la línea de ojos; "
      "elev = ángulo de la cuerda raíz-punta sobre la horizontal)")
print("      nombre        grupo     N   a(rad)   t    largo  semiancho salida  raíz_z  punta_z  punta_x  punta_y  desv%  elev")
for m, info in FILA_TABLA:
    pz = (info['punta'].z - EYE_Z) * 1000
    print(f"      {m['nombre']:13s} {m['grupo']:9s} {m['nivel']}  {wrap(m['a']):+6.2f}  {m['t']:4.2f}  "
          f"{m['largo']*1000:5.0f}  {m['ancho']*1000:6.1f}    {m['salida']:4.2f}   "
          f"{(info['raiz'].z - EYE_Z)*1000:+5.0f}   {pz:+6.0f}   "
          f"{info['punta'].x*1000:+6.0f}   {info['punta'].y*1000:+6.0f}   {info['desv']*100:4.1f}  {info['elev']:+4.0f}")
avisos = 0
# variación entre vecinos del mismo grupo y nivel (ordenados por azimut)
for grupo in ('flequillo', 'coronilla', 'lat_alto', 'nuca'):
    for nivel in ('P', 'M'):
        fila = sorted([m for m in LISTA if m['grupo'] == grupo and m['nivel'] == nivel
                       and 'giro_punta' not in m],
                      key=lambda m: wrap(m['a'] - (math.pi if grupo == 'nuca' else 0.0)))
        for u, v in zip(fila, fila[1:]):
            d_l = abs(u['largo'] - v['largo']) / max(u['largo'], v['largo'])
            d_a = abs(u['ancho'] - v['ancho']) / max(u['ancho'], v['ancho'])
            if d_l < 0.20 and d_a < 0.20:
                avisos += 1
                print(f"[AL]   AVISO variación: {u['nombre']} y {v['nombre']} "
                      f"(largo {d_l*100:.0f} %, ancho {d_a*100:.0f} %) < 20 %")
            if abs(u['t'] - v['t']) < 0.05 - 1e-9 and nivel == 'P':
                avisos += 1
                print(f"[AL]   AVISO t de raíz: {u['nombre']} y {v['nombre']} Δt < 0,05")
pares = collections.Counter((round(m['largo'], 4), round(m['ancho'], 4)) for m in LISTA)
for par, n in pares.items():
    if n > 1:
        avisos += 1
        print(f"[AL]   AVISO pareja (largo, ancho) repetida {n} veces: {par}")
for m, info in FILA_TABLA:
    umbral = 0.10 if m['nivel'] == 'P' else (0.08 if m['nivel'] == 'M' else 0.0)
    if info['desv'] < umbral:
        avisos += 1
        print(f"[AL]   AVISO tira recta: {m['nombre']} desviación {info['desv']*100:.1f} % < {umbral*100:.0f} %")
# laterales altos: cuerda 25-40 grados sobre la horizontal. Bajos: el criterio
# pedía 25-45 grados bajo la horizontal, pero con la punta 10-20 mm delante de
# la oreja (criterio 12: y -82..-92 desde una raíz en y -130) y 115 mm más
# abajo, la cuerda sale a 60-70 grados por geometría: los dos criterios son
# incompatibles y se prioriza la posición respecto a la oreja (banda -72..-50).
for n, lo, hi in (('P6', 25, 40), ('P7', 25, 40), ('P6m1', -72, -50), ('P7m1', -72, -50)):
    e = INFO[n]['elev']
    if not (lo <= e <= hi):
        avisos += 1
        print(f"[AL]   AVISO elevación: {n} cuerda a {e:+.0f} grados (criterio {lo}..{hi})")
# laterales bajos: punta 105-125 mm bajo los ojos, 10-20 mm delante de la oreja (y -72)
for n in ('P6m1', 'P7m1'):
    pz = (INFO[n]['punta'].z - EYE_Z) * 1000
    py = INFO[n]['punta'].y * 1000
    if not (-125 <= pz <= -105):
        avisos += 1
        print(f"[AL]   AVISO lateral bajo {n}: punta a {pz:+.0f} mm de los ojos (criterio -125..-105)")
    if not (-92 <= py <= -82):
        avisos += 1
        print(f"[AL]   AVISO lateral bajo {n}: punta en y {py:+.0f} (oreja en -72; criterio -92..-82)")
centro = [info for m, info in FILA_TABLA
          if m['grupo'] == 'flequillo' and m['nivel'] in ('P', 'M')
          and m['nombre'].startswith(('P2', 'P3')) and abs(info['punta'].x) < 0.091]
z_min_c = min(i['punta'].z for i in centro) - EYE_Z
z_max_c = max(i['punta'].z for i in centro) - EYE_Z
print(f"[AL] flequillo central: puntas entre {z_min_c*1000:+.0f} y {z_max_c*1000:+.0f} mm "
      f"de la línea de ojos (objetivo +5..+20)")
if not (0.005 <= z_min_c and z_max_c <= 0.020):
    avisos += 1
    print("[AL]   AVISO flequillo central fuera de +5..+20 mm")
# nada del pelo por delante de la punta de la nariz (medida 3D, sin paralaje)
NARIZ_Y = min((ob.matrix_world @ v.co).y for v in ob.data.vertices
              if (ob.matrix_world @ v.co).z > EYE_Z - 0.06)
y_pelo = min(i['y_min'] for i in INFO.values())
quien = min(INFO, key=lambda n: INFO[n]['y_min'])
print(f"[AL] pelo más adelantado: {quien} y {y_pelo*1000:+.0f} mm; nariz y {NARIZ_Y*1000:+.0f} mm "
      f"(margen {(y_pelo - NARIZ_Y)*1000:+.0f} mm, debe ser > 0)")
if y_pelo < NARIZ_Y:
    avisos += 1
    print("[AL]   AVISO pelo por delante de la nariz")
lejos = {n: i['lejos'] * 1000 for n, i in INFO.items()}
print("[AL] mechones más lejos del casquete (mm): " +
      ", ".join(f"{n} {lejos[n]:.0f}" for n in ('P4', 'P5', 'P6', 'P7', 'P8', 'P1')))
n_niv = collections.Counter(m['nivel'] for m in LISTA)
N_TRIS = N_TRIS_MASA + sum(TRIS.values())
print(f"[AL] pelo: {len(LISTA)} mechones (P {n_niv['P']}, M {n_niv['M']}, "
      f"F {n_niv['F']}, S {n_niv['S']}) + 1 masa; tris masa {N_TRIS_MASA}, "
      f"P {TRIS['P']}, M {TRIS['M']}, F {TRIS['F']}, S {TRIS['S']} = {N_TRIS} "
      f"(tope 3.900 de malla base)")
# Presupuesto: la regla 5 (<= 4.000 tris) se aplica a la MALLA BASE del pelo.
# El Solidify 'Contorno' duplica las caras de TODOS los objetos (cuerpo, ojos,
# pelo) para dibujar la tinta: es un coste de la técnica de tinta, se cuenta
# aparte y por igual para todo el personaje (conocimiento/11).
print(f"[AL] pelo: con la tinta (Solidify) se evalúan {2 * N_TRIS} tris; el "
      f"presupuesto de la regla 5 se aplica a la malla base")
print(f"[AL] pelo: {avisos} aviso(s) de variación/forma")
if N_TRIS > 3900:
    raise RuntimeError(f"pelo: {N_TRIS} tris de malla base > 3.900")

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
print(f"[AL] pelo: {len(hm.polygons)} caras, {_pz} pieza(s) conexas "
      f"(objetivo v10: 40 = 39 mechones + 1 masa)")

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
