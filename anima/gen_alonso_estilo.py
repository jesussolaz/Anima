# ÁNIMA — Alonso: estilización (paso 2 de 3)
#
# Herramienta de EDITOR. Toma la base humana de MPFB2 y la lleva al estilo del
# juego: JRPG estilizado, chico de 15-16, ojos grandes y expresivos.
#   Flipendo --background --python gen_alonso_estilo.py
# Entrada: AlonsoBase.blend   Salida: AlonsoEstilo.blend
#
# Se trabaja SOBRE una base esculpida en vez de generar geometría: los rasgos
# (nariz, labios, párpados, orejas) ya están, y la topología va en anillos
# alrededor de ojos y boca — que es lo que luego permite parpadeo y sonrisa.
# Aquí solo se deforma.
#
# EL ORDEN IMPORTA, y costó dos vueltas averiguarlo:
#   1. fijar la mezcla de fenotipo    (las props MPFB_HUM_* NO la aplican solas)
#   2. hornear los shape keys         (mientras existan, tocar co no hace nada)
#   3. medir referencias              (sobre la geometría YA horneada, o van desfasadas)
#   4. podar geometría auxiliar
#   5. deformar
#   6. normalizar estatura

import bpy
import bmesh
import collections
import math
import os
import sys
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("anima_kit", None)
from anima_kit import clamp01, lerp, smoothstep                    # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
IN_BLEND = os.path.join(HERE, "AlonsoBase.blend")
OUT_BLEND = os.path.join(HERE, "AlonsoEstilo.blend")

# --- cuánto se estiliza -------------------------------------------------------
HEAD_SCALE = 1.340      # 6,5 cabezas = adolescente (conocimiento/04).
                        # A 8 cabezas lee ADULTO por mucha cara de niño
                        # que se le ponga, y esa contradicción es lo que
                        # hacía que el modelo no terminara de funcionar.
EYE_WIDE = 1.58         # el ojo se ensancha...
EYE_TALL = 2.85         # ...y sobre todo SE ABRE: eso es lo que lo hace JRPG
NOSE_SHRINK = 0.32      # nariz pequeña, casi insinuada
MOUTH_SHRINK = 0.78
HAND_GROW = 1.10        # manos y pies algo exagerados ayudan a la silueta
HEIGHT_TARGET = 1.680

# fenotipo de partida: joven caucásico masculino
# ($md = macrodetail, $ca = caucásico, $ma = masculino, $yn = joven)
MIX = {"$md-$ca-$ma-$yn": 1.0,
       "$md-universal-$ma-$yn-$av$mu-$av$wg": 1.0}

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
h = bpy.data.objects["Alonso_Base"]
me = h.data

# --- 1 y 2: fenotipo y horneado ----------------------------------------------
if me.shape_keys:
    kb = me.shape_keys.key_blocks
    for k in kb:
        if k.name != "Basis":
            k.value = MIX.get(k.name, 0.0)
    # No se evalúa con el depsgraph: MPFB deja un modificador Mask que oculta los
    # helpers, así que la malla evaluada tiene menos vértices y los índices no
    # casan. La mezcla relativa se calcula a mano, que además es exacta.
    basis = kb[0]
    baked = []
    for vi in range(len(me.vertices)):
        co = basis.data[vi].co.copy()
        for k in kb[1:]:
            if k.value:
                ref = k.relative_key or basis
                co += (k.data[vi].co - ref.data[vi].co) * k.value
        baked.append(co)
    h.shape_key_clear()
    for i, v in enumerate(me.vertices):
        v.co = baked[i]
    me.update()
    print(f"[EST] fenotipo horneado en {len(baked)} verts")

for mod in list(h.modifiers):
    print("[EST] modificador retirado:", mod.name, mod.type)
    h.modifiers.remove(mod)


# --- 3: referencias, medidas sobre la geometría ya horneada -------------------
def group_centroid(name):
    g = h.vertex_groups.get(name)
    if g is None:
        return None
    pts = [v.co for v in me.vertices
           if any(gr.group == g.index and gr.weight > 0.35 for gr in v.groups)]
    return (sum(pts, Vector()) / len(pts)) if pts else None


L_EYE = group_centroid("helper-l-eye") or group_centroid("joint-l-eye")
R_EYE = group_centroid("helper-r-eye") or group_centroid("joint-r-eye")
NECKJ = group_centroid("joint-neck")
JAWJ = group_centroid("joint-jaw")
MOUTHJ = group_centroid("joint-mouth")
assert L_EYE and R_EYE and NECKJ and JAWJ, "faltan referencias en la malla base"

# OJO: estas referencias hay que tomarlas AQUÍ, antes de podar. La poda borra la
# geometría de los grupos `joint-*`, y group_centroid devolvería None en silencio
# — el ensanche de hombros y el agrandado de manos llevaban tiempo sin hacer nada.
CLAV_L = group_centroid("joint-l-clavicle") or group_centroid("joint-l-shoulder")
WRIST_L = group_centroid("joint-l-wrist")
WRIST_R = group_centroid("joint-r-wrist")
print(f"[EST] hombro {tuple(round(c,3) for c in CLAV_L) if CLAV_L else None} | "
      f"muñeca {tuple(round(c,3) for c in WRIST_L) if WRIST_L else None}")

CROWN_Z = max(v.co.z for v in me.vertices)
EYE_Z0 = L_EYE.z
# punta de la nariz: el vértice más adelantado entre boca y ojos, en el eje
cand = [v.co for v in me.vertices
        if abs(v.co.x) < 0.018 and JAWJ.z + 0.030 < v.co.z < EYE_Z0]
# .copy() obligatorio: v.co es un proxy RNA, y al podar vértices la referencia
# queda colgando y Blender casca al leerla.
NOSE_TIP = (min(cand, key=lambda c: c.y).copy() if cand
            else Vector((0, -0.13, EYE_Z0 - 0.04)))
# labios: el vértice más adelantado por debajo de la nariz
cand = [v.co for v in me.vertices
        if abs(v.co.x) < 0.012 and JAWJ.z + 0.010 < v.co.z < NOSE_TIP.z - 0.012]
LIP = (min(cand, key=lambda c: c.y).copy() if cand
       else Vector((0, -0.10, NOSE_TIP.z - 0.030)))
CHIN_Z = JAWJ.z
print(f"[EST] ojos z {EYE_Z0:.4f} sep {(L_EYE - R_EYE).length:.4f} | nariz "
      f"{tuple(round(c, 3) for c in NOSE_TIP)} | labio {tuple(round(c, 3) for c in LIP)}"
      f" | barbilla {CHIN_Z:.3f} | coronilla {CROWN_Z:.3f}")

# --- 4: podar geometría auxiliar ---------------------------------------------
aux_idx = {g.index for g in h.vertex_groups
           if g.name in ("HelperGeometry", "JointCubes")
           or g.name.startswith(("helper-", "joint-"))}
bg = h.vertex_groups.get("body")
body_idx = bg.index if bg else None
kill = [v.index for v in me.vertices
        if ({gr.group for gr in v.groups} & aux_idx)
        and (body_idx is None or body_idx not in {gr.group for gr in v.groups})]
if kill:
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    bmesh.ops.delete(bm, geom=[bm.verts[i] for i in kill], context='VERTS')
    bm.to_mesh(me)
    bm.free()
print(f"[EST] auxiliares borrados: {len(kill)} -> {len(me.vertices)} verts")

# --- 5: deformación de estilo ------------------------------------------------
orig = [v.co.copy() for v in me.vertices]
delta = [Vector((0, 0, 0)) for _ in orig]


def ellip(d, rx, ry, rz):
    return Vector((d.x / rx, d.y / ry, d.z / rz)).length


def style_delta(p):
    delta_i = Vector((0, 0, 0))
    # cabeza algo mayor, escalada desde la base del cuello
    w = smoothstep(NECKJ.z - 0.055, CHIN_Z + 0.010, p.z)
    if w > 0.0:
        # en Z se escala menos: escalar uniforme desde el cuello alarga la cabeza
        # y sale un huevo en vez de una cabeza juvenil (ancha, no larga)
        d = p - NECKJ
        # el estilizado de referencia tiene la cabeza ANCHA: ancho/alto 0,95,
        # frente al 0,83 que tenía Alonso. Se ensancha en X más que en Z.
        delta_i += Vector((d.x * 1.78, d.y * 1.05, d.z * 0.92)) * ((HEAD_SCALE - 1.0) * w)

    # OJOS. Campo ceñido al ojo, y crece mucho más en vertical que en horizontal:
    # un ojo JRPG no es un ojo realista escalado, es un ojo ABIERTO, que se come
    # parte de pómulo y de ceja.
    for EC in (L_EYE, R_EYE):
        d = p - EC
        # Caída ANCHA a propósito: si el campo es estrecho, el borde se desplaza
        # mucho y el vecino nada, y sale un reborde tipo antifaz alrededor del ojo.
        w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.058, 0.068, 0.044)))
        if w > 0.002:
            inward = clamp01(-d.x / 0.026) if EC.x > 0 else clamp01(d.x / 0.026)
            delta_i += Vector((d.x * (EYE_WIDE - 1.0) * w * (1.0 - 0.50 * inward),
                                0.0, d.z * (EYE_TALL - 1.0) * w))
            delta_i.z -= 0.0060 * w                          # ojo algo más bajo
            delta_i.x += (0.0040 * w) * (1 if EC.x > 0 else -1)

        # ceja y pómulo más blandos: el relieve adulto envejece la cara
        d2 = p - Vector((EC.x, EC.y, EC.z + 0.028))
        delta_i.y += 0.0065 * smoothstep(1.0, 0.0, clamp01(ellip(d2, 0.050, 0.046, 0.021)))
        d2 = p - Vector((EC.x * 1.35, EC.y + 0.012, EC.z - 0.038))
        delta_i.y += 0.0045 * smoothstep(1.0, 0.0, clamp01(ellip(d2, 0.042, 0.046, 0.032)))

    # nariz pequeña, encogida hacia su raíz
    root = Vector((0.0, NOSE_TIP.y + 0.026, NOSE_TIP.z + 0.026))
    d = p - root
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.030, 0.042, 0.040)))
    if w > 0.002:
        delta_i += d * ((NOSE_SHRINK - 1.0) * w)

    # boca menor
    d = p - LIP
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.040, 0.038, 0.026)))
    if w > 0.002:
        delta_i += d * ((MOUTH_SHRINK - 1.0) * w)

    # mandíbula estrecha y barbilla corta: la cara adulta es larga por abajo
    d = p - Vector((0.0, JAWJ.y - 0.005, CHIN_Z + 0.014))
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.082, 0.082, 0.052)))
    if w > 0.002:
        delta_i.x -= p.x * 0.165 * w
        delta_i.z += 0.020 * w
        delta_i.y += 0.005 * w

    # Aplanado del plano facial. Los rasgos anime van sobre una cara PLANA:
    # el relieve de pómulo y ceja es lo que la hace leer como adulta realista.
    if p.y < -0.02 and p.z > CHIN_Z - 0.02:
        fw = smoothstep(1.0, 0.0, clamp01(ellip(p - Vector((0.0, -0.085, EYE_Z0 - 0.020)),
                                                0.085, 0.075, 0.090)))
        delta_i.y += (-0.128 - p.y) * 0.30 * fw

    # PLANOS LATERALES DE LA CABEZA (conocimiento/08). Un plano PLANO tallado en
    # la esfera, del temporal al pómulo. Sin él el cráneo es una esfera con
    # rasgos encima, que es exactamente lo que tenía Alonso.
    if p.z > CHIN_Z - 0.01:
        alto = clamp01((p.z - (CHIN_Z - 0.01)) / max(CROWN_Z - CHIN_Z, 1e-6))
        # el plano existe entre mandíbula y sien, no en la coronilla
        franja = smoothstep(0.04, 0.22, alto) * (1.0 - smoothstep(0.72, 0.95, alto))
        # y se aplana hacia atrás; la cara de delante se deja
        atras = smoothstep(-0.055, 0.015, p.y)
        w_lat = franja * atras
        if w_lat > 0.002 and abs(p.x) > 0.018:
            ancho_plano = 0.0815 * (1.0 - 0.11 * abs(alto - 0.42))
            objetivo = ancho_plano * (1 if p.x > 0 else -1)
            delta_i.x += (objetivo - p.x) * 0.78 * w_lat

    # NARIZ DE PICO (conocimiento/14). "Recuerda más al pico de un pájaro que a
    # una nariz." La cara anime en 3D es PUNTIAGUDA a propósito: el cel-shading
    # esconde la forma rara. Suavizarla para que resulte creíble es el error.
    # cresta estrecha y alta desde el puente hasta la punta
    d = p - Vector((0.0, NOSE_TIP.y + 0.016, NOSE_TIP.z + 0.016))
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.0090, 0.026, 0.034)))
    if w > 0.002:
        delta_i.y -= 0.0105 * w ** 1.3
        delta_i.x -= p.x * 0.55 * w
    # y la punta, que es lo que sobresale de verdad
    d = p - Vector((0.0, NOSE_TIP.y + 0.006, NOSE_TIP.z - 0.002))
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.0075, 0.016, 0.013)))
    delta_i.y -= 0.0090 * w ** 1.2

    # mentón también en punta, no redondo
    d = p - Vector((0.0, JAWJ.y - 0.010, CHIN_Z + 0.008))
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.030, 0.034, 0.026)))
    if w > 0.002:
        delta_i.y -= 0.0050 * w ** 1.5
        delta_i.x -= p.x * 0.22 * w

    # cráneo más lleno arriba y frente algo mayor
    d = p - Vector((0.0, -0.015, CROWN_Z - 0.055))
    w = smoothstep(1.0, 0.0, clamp01(ellip(d, 0.100, 0.110, 0.080)))
    if w > 0.002:
        delta_i += Vector((p.x, p.y + 0.015, 0.0)) * (0.016 * w)

    # Hombros. MEDIDO sobre el estilizado CC0 de Blender Studio: 2,72 cabezas de
    # ancho de hombro, frente a 3,48 del realista del mismo autor. Alonso estaba
    # en 3,66 — más ancho incluso que un realista. En este estilo la cabeza es
    # grande y el hombro comparativamente ESTRECHO; ensancharlo (lo que hice
    # antes) va justo en la dirección contraria.
    if CLAV_L is not None:
        wsh = smoothstep(1.0, 0.0, clamp01(abs(p.z - CLAV_L.z) / 0.105))
        delta_i.x -= p.x * 0.190 * wsh
        wci = smoothstep(1.0, 0.0, clamp01(abs(p.z - (CLAV_L.z - 0.235)) / 0.085))
        delta_i.x -= p.x * 0.045 * wci

    # manos algo mayores
    for WJ in (WRIST_L, WRIST_R):
        if WJ is None:
            continue
        d = p - WJ
        if d.length < 0.17:
            delta_i += d * ((HAND_GROW - 1.0)
                             * smoothstep(0.0, 1.0, clamp01((d.length - 0.005) / 0.080)))
    return delta_i


for i, p in enumerate(orig):
    delta[i] = style_delta(p)

for i, v in enumerate(me.vertices):
    v.co = orig[i] + delta[i]
me.update()

# Pase de relajación sobre lo que se ha movido: quita los pliegues que deja el
# desplazamiento por campos. Los bordes de los huecos (ojos, boca) se dejan
# fijos, o el suavizado cerraría la apertura que acabamos de abrir.
moved = [i for i, d in enumerate(delta) if d.length > 0.0012]
if moved:
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    frozen = {v.index for v in bm.verts if v.is_boundary}
    target = [bm.verts[i] for i in moved if i not in frozen]
    # La relajación es necesaria: sin ella los pliegues que deja el
    # desplazamiento por campos se ven como BULTOS. "Puntiagudo" debe salir de
    # un cambio de plano deliberado y fuerte, no de dejar de suavizar.
    for _ in range(3):
        bmesh.ops.smooth_vert(bm, verts=target, factor=0.50,
                              use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(me)
    bm.free()
    me.update()
    print(f"[EST] relajados {len(target)} verts ({len(frozen)} de borde intactos)")

# --- 5c: REMAPEO VERTICAL DE LA CABEZA ----------------------------------------
# La regla del estilo (conocimiento/01 y 06): la línea de ojos va al 40-46 % del
# alto de cabeza desde el mentón. Alonso estaba al 55 %, por encima incluso del
# 50 % realista. Consecuencia: bóveda craneal pequeña y cara que lee adulta por
# mucho que se agranden los ojos.
#
# Se comprime lo que hay bajo los ojos y se expande lo que hay encima, dejando
# mentón y coronilla donde estaban. Eso baja la línea de ojos Y comprime el
# tercio inferior, que son las dos correcciones de mayor impacto.
EYE_RATIO = 0.415


def medir_menton(verts, eye):
    """Mentón = donde el ANCHO DE CARA toca su mínimo por debajo de los ojos.

    Bajando desde los ojos la cara se estrecha hasta el mentón; a partir de ahí
    el cuello vuelve a ensanchar. Ese mínimo es el mentón, y es un detector
    estable. Se probaron tres heurísticas de perfil frontal ("primer salto hacia
    delante", "último", "lo que sobresale del cuello") y cada una daba un
    resultado distinto según dónde arrancara el escaneo. El grupo anatómico
    `joint-jaw` tampoco vale: está 2 cm por encima del mentón real.
    """
    mejor, mejor_z = None, None
    z = eye - 0.030
    while z > eye - 0.200:
        band = [v for v in verts if abs(v.z - z) < 0.0035]
        if band:
            ancho = max(v.x for v in band) - min(v.x for v in band)
            if mejor is None or ancho < mejor:
                mejor, mejor_z = ancho, z
        z -= 0.003
    return mejor_z if mejor_z is not None else eye - 0.11


EYE_RATIO = 0.415


# El mentón NO se adivina por geometría: la malla base ya trae el grupo de
# vértices anatómico `joint-jaw`, centrado en el eje y a la altura del mentón.
# Tres heurísticas de perfil dieron tres resultados distintos según dónde
# arrancara el escaneo; el grupo es exacto y no depende de nada.


_crown = max(v.co.z for v in me.vertices)
_eye = (L_EYE + style_delta(L_EYE)).z
_chin = medir_menton([v.co for v in me.vertices], _eye)
_hh = _crown - _chin
_ratio = (_eye - _chin) / _hh
_eye_new = _chin + _hh * EYE_RATIO
_k_low = (_eye_new - _chin) / (_eye - _chin)
_k_up = (_crown - _eye_new) / (_crown - _eye)
print(f"[EST] cabeza: menton {_chin:.4f} ojos {_eye:.4f} coronilla {_crown:.4f}")
print(f"[EST] linea de ojos {_ratio*100:.1f}% -> {EYE_RATIO*100:.0f}% "
      f"(abajo x{_k_low:.3f}, arriba x{_k_up:.3f})")


def remap_z(p):
    """Remapeo vertical, difuminado a través del cuello para no romperlo."""
    w = smoothstep(_chin - 0.115, _chin + 0.010, p.z)
    if w <= 0.0:
        return p
    if p.z < _eye:
        nz = _chin + (p.z - _chin) * _k_low
    else:
        nz = _eye_new + (p.z - _eye) * _k_up
    return Vector((p.x, p.y, lerp(p.z, nz, w)))


for v in me.vertices:
    v.co = remap_z(v.co)
me.update()

# --- 5b: ojos, del pack CC0 de MakeHuman ---------------------------------------
# Vienen ajustados a ESTA malla base, así que no hay que adivinar el encaje. Se
# les aplica la MISMA deformación y normalización que a la cabeza, y así siguen
# encajando después de estilizar. Unidades MakeHuman: Y arriba, factor 0.1.
EYE_OBJ = os.path.join(HERE, "assets", "eyes", "high-poly", "high-poly.obj")
eye_v, eye_f, eye_vt, eye_fuv = [], [], [], []
if os.path.exists(EYE_OBJ):
    for line in open(EYE_OBJ):
        if line.startswith("v "):
            a, b, c = (float(t) for t in line.split()[1:4])
            eye_v.append(Vector((a * 0.1, -c * 0.1, b * 0.1)))
        elif line.startswith("vt "):
            u, vv = (float(t) for t in line.split()[1:3])
            eye_vt.append((u, vv))
        elif line.startswith("f "):
            toks = line.split()[1:]
            eye_f.append([int(t.split("/")[0]) - 1 for t in toks])
            eye_fuv.append([int(t.split("/")[1]) - 1 if "/" in t and t.split("/")[1]
                            else 0 for t in toks])
    mid = sum((v.x for v in eye_v)) / len(eye_v)
    left = [v for v in eye_v if v.x > mid]
    right = [v for v in eye_v if v.x <= mid]
    cL = sum(left, Vector()) / len(left)
    cR = sum(right, Vector()) / len(right)
    print(f"[EST] ojos CC0: {len(eye_v)} verts, centro neutro {tuple(round(c,4) for c in cL)}")
    # El globo se TRASLADA y se escala UNIFORME. Pasarlo por style_delta entero
    # lo estiraría 2,15x en vertical junto con su iris (el campo de ojo es
    # anisótropo a propósito, para abrir el párpado), y el ojo salía negro.
    EYEBALL_SCALE = 1.0
    moved = []
    for v in eye_v:
        izq = v.x > mid
        base = cL if izq else cR
        tgt = L_EYE if izq else R_EYE
        ctr = remap_z(tgt + style_delta(tgt))      # dónde acaba el centro del ojo
        moved.append(ctr + (v - base) * EYEBALL_SCALE)
    eye_v = moved

# --- 6: estatura final y referencias para el resto del pipeline --------------
zs = [v.co.z for v in me.vertices]
zmin, zmax = min(zs), max(zs)
k = HEIGHT_TARGET / (zmax - zmin)
for v in me.vertices:
    v.co = Vector((v.co.x * k, v.co.y * k, (v.co.z - zmin) * k))
me.update()

# Las referencias de ojo se pasan por la MISMA deformación y la misma
# normalización que la malla: así el paso 3 sabe exactamente dónde acabaron.
def to_final(pt):
    q = remap_z(pt + style_delta(pt))          # mismo remapeo que la malla
    return Vector((q.x * k, q.y * k, (q.z - zmin) * k))


LE, RE = to_final(L_EYE), to_final(R_EYE)
if eye_v:
    em = bpy.data.meshes.new("Alonso_Ojos")
    em.from_pydata([( v.x * k, v.y * k, (v.z - zmin) * k) for v in eye_v], [], eye_f)
    em.update()
    for poly in em.polygons:
        poly.use_smooth = True
    if eye_vt:                       # las UV traen el iris pintado en la textura
        uvl = em.uv_layers.new(name="UVMap")
        li = 0
        for pi, poly in enumerate(em.polygons):
            for k in range(len(poly.vertices)):
                uvl.data[li].uv = eye_vt[eye_fuv[pi][k]]
                li += 1
    eo = bpy.data.objects.new("Alonso_Ojos", em)
    bpy.context.collection.objects.link(eo)
    eo.game.physics_type = 'NO_COLLISION'
    print(f"[EST] ojos colocados: {len(em.vertices)} verts, {len(em.polygons)} caras")

h["ALONSO_L_EYE"] = tuple(LE)
h["ALONSO_R_EYE"] = tuple(RE)
h["ALONSO_EYE_SEP"] = (LE - RE).length
EYE_Z = (LE.z + RE.z) * 0.5
print(f"[EST] ojos finales: L {tuple(round(c,4) for c in LE)} sep {(LE-RE).length:.4f}")
h["ALONSO_CHIN_Z"] = medir_menton([v.co for v in me.vertices], EYE_Z)
h["ALONSO_EYE_Z"] = EYE_Z
h["ALONSO_CROWN_Z"] = max(v.co.z for v in me.vertices)
h["ALONSO_HEIGHT"] = HEIGHT_TARGET
h.name = "Alonso"
h.data.name = "Alonso_Malla"
print(f"[EST] estatura {HEIGHT_TARGET:.3f} m | ojos z {EYE_Z:.4f} | "
      f"{HEIGHT_TARGET / (h['ALONSO_CROWN_Z'] - (CHIN_Z * k)):.2f} cabezas aprox")
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print("[EST] guardado:", OUT_BLEND)
print("[EST] OK")
