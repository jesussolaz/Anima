# ÁNIMA — Alonso vestido (carril ROPA)
#
#   cd ~/Flipendo/game/anima && Flipendo --background --python gen_alonso_ropa.py [-- <metricas.txt>]
# Entrada: Alonso.blend (tal como esté)   Salida: AlonsoVestido.blend
#
# Viste a Alonso según dev/noche/informes/anima-ropa-diseno.md (el brief con
# cotas) con la técnica probada en anima-ropa-tecnica.md: cada prenda se EXTRAE
# del propio cuerpo (conocimiento/12) seleccionando caras por los pesos del rig
# game_engine de MPFB2, se corta con planos en las aperturas, se empuja por la
# normal la holgura de la prenda, se decima, se le da grosor (Solidify solo
# canto), sombreado toon y contorno de casco invertido (anima_toon.py), y se
# APLICAN grosor y contorno como geometría porque el motor reevalúa toda la pila
# de modificadores en CPU cada frame (no hay BL_SkinDeformer en este UPBGE).
#
# Prendas (objetos MESH, cada uno Alonso_Ropa_<prenda>, sin padre: el carril RIG
# los cuelga de Alonso_Rig con un Armature; todos llevan los 53 grupos de hueso
# con los pesos exactos de MPFB2 heredados en la extracción):
#   Jubon       coleto sin mangas azul de pastel, tirilla, bajo bajo la pretina
#   Faldillas   8 haldetas trapezoidales de 70 mm colgando de la pretina
#   Camisa      dos mangas con vuelo (1,6x) + valona lisa de 70 mm
#   Panuelo     banda de 40 mm sobre la valona, nudo y dos colas (220/170 mm)
#   Pretina     correa de 50 mm en la cintura natural + hebilla de latón 60x50
#   Greguescos  valones ESTRECHOS de buriel, cintura -> 35 mm bajo la rodilla
#   Botas       medias botas datiladas, caña a z 0,30, pie x1,25, suela y correa
#   Guantes     manoplas de 70 mm; la mano es el propio cuerpo con M_Camuza
#   (medias)    sin geometría: M_Medias sobre la piel de z 0,26 a 0,475
#
# El cuerpo (objeto Alonso) conserva TODAS sus propiedades ALONSO_* y todos sus
# 13.380 vértices en el mismo orden (MPFB2 importa los pesos por índice): solo
# se borran las CARAS tapadas del todo por una prenda (delete FACES_ONLY), con
# margen en cada apertura. Se midió qué era mejor (ver §"piel tapada" abajo y el
# informe): borrarlas ahorra 11.000 tris de cuerpo y evita que la piel asome
# cuando la ropa decimada se deforma en el codo (-7,3 mm en la prueba posada).
#
# Determinista: sin random; Decimate/bisect/Solidify son deterministas para la
# misma entrada. Los números vienen del brief; cuando se apartan de él se dice
# el porqué en el sitio.

import bpy
import bmesh
import collections
import glob
import json
import math
import os
import sys
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("anima_toon", None)
from anima_toon import toon, material_contorno, contorno   # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
IN_BLEND = os.path.join(HERE, "Alonso.blend")
OUT_BLEND = os.path.join(HERE, "AlonsoVestido.blend")
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
METRICAS = ARGS[0] if ARGS else None

# Pesos del rig game_engine de MPFB2 (CC0). Los 13.380 vértices de Alonso son
# los índices 0..13379 del basemesh (verificado hueso a hueso en la
# investigación técnica). Sin este fichero no hay zonas: los 153 vertex groups
# de Alonso.blend no parten el cuerpo (136 están vacíos tras la poda).
def _pesos_mpfb():
    cands = [os.path.join(HERE, "referencias", "mpfb", "weights.game_engine.json")]
    cands += glob.glob(os.path.expanduser(
        "~/Library/Application Support/UPBGE/*/extensions/*/mpfb/data/rigs/standard/weights.game_engine.json"))
    cands += glob.glob(os.path.expanduser(
        "~/Library/Application Support/Blender/*/extensions/*/mpfb/data/rigs/standard/weights.game_engine.json"))
    for c in cands:
        if os.path.exists(c):
            return c
    raise SystemExit("[ROPA] no encuentro weights.game_engine.json de MPFB2")


W_JSON = _pesos_mpfb()

bpy.ops.wm.open_mainfile(filepath=IN_BLEND)
ob = bpy.data.objects["Alonso"]
me = ob.data
N = len(me.vertices)
HEIGHT = float(ob["ALONSO_HEIGHT"])
print(f"[ROPA] cuerpo: {N} verts, {len(me.polygons)} caras, altura {HEIGHT:.3f}; pesos {W_JSON}")

PESOS = json.load(open(W_JSON))["weights"]
peso = [dict() for _ in range(N)]
for h, lst in PESOS.items():
    for i, x in lst:
        if i < N:
            peso[i][h] = x
HUESOS = sorted(PESOS.keys())

# Grupos de hueso en el cuerpo ANTES de extraer: bmesh conserva la capa deform
# al borrar caras y Decimate/bisect la interpolan, así cada prenda nace con los
# pesos exactos sin transferir nada (vía A del informe técnico: 100 % de los
# vértices con suma > 0,98).
for h in HUESOS:
    if h in ob.vertex_groups:
        continue
    g = ob.vertex_groups.new(name=h)
    for i, x in PESOS[h]:
        if i < N:
            g.add([i], x, 'REPLACE')
GRUPOS_CUERPO = [g.name for g in ob.vertex_groups]

# BVH de la piel real (sin modificadores) para medir distancias prenda->piel
BVH_PIEL = BVHTree.FromPolygons([v.co for v in me.vertices], [list(p.vertices) for p in me.polygons])


def smoothstep(a, b, x):
    t = max(0.0, min(1.0, (x - a) / (b - a))) if b != a else (1.0 if x >= b else 0.0)
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def zona_w(i, huesos):
    return sum(peso[i].get(h, 0.0) for h in huesos)


def articulacion(a, b, lo=0.35, hi=0.65):
    """Centro de la articulación entre los huesos `a` y `b`: media de los
    vértices donde los dos pesan parecido. Los grupos joint-* de MPFB2 están
    vacíos en Alonso.blend; esto es lo que hay, y es estable."""
    P = [me.vertices[i].co for i in range(N) if lo <= zona_w(i, a) <= hi and lo <= zona_w(i, b) <= hi]
    return sum(P, Vector()) / len(P)


def activar(o):
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = o
    o.select_set(True)


def tris_de(o):
    return sum(len(p.vertices) - 2 for p in o.data.polygons)


def aplicar(o, mod):
    activar(o)
    bpy.ops.object.modifier_apply(modifier=mod.name)


def sgn(x):
    return 1.0 if x >= 0 else -1.0


# ------------------------------------------------------------- articulaciones
HOMBRO = {s: articulacion([f"upperarm_{s}"], [f"clavicle_{s}", "spine_03"]) for s in "lr"}
MUNECA = {s: articulacion([f"lowerarm_{s}"], [f"hand_{s}"]) for s in "lr"}
TOBILLO = {s: articulacion([f"calf_{s}"], [f"foot_{s}"]) for s in "lr"}
print("[ROPA] hombro", tuple(round(x, 3) for x in HOMBRO["l"]), "muñeca", tuple(round(x, 3) for x in MUNECA["l"]),
      "tobillo", tuple(round(x, 3) for x in TOBILLO["l"]))


def t_brazo(s):
    """Parámetro a lo largo del brazo: 0 en el hombro, 1 en la muñeca."""
    H, M = HOMBRO[s], MUNECA[s]
    eje = M - H
    L2 = eje.length_squared

    def f(co):
        return (co - H).dot(eje) / L2
    return f, H, eje.normalized()


# ------------------------------------------------------------------ paleta
# Colores LUZ en lineal (brief §4.2), tres bandas por material con sombra_de v2.
M_LIENZO = toon("M_Lienzo", (0.839, 0.776, 0.617), bandas=3, fuerza=0.66)
M_JUBON = toon("M_Jubon", (0.054, 0.138, 0.332), bandas=3, fuerza=0.62)
M_GREG = toon("M_Greguescos", (0.122, 0.065, 0.032), bandas=3, fuerza=0.60)
M_MEDIAS = toon("M_Medias", (0.745, 0.644, 0.445), bandas=3, fuerza=0.66)
# botas «enceradas» (Quijote II,18): un brillo estrecho de cera, no plástico
M_BOTA = toon("M_Bota", (0.181, 0.048, 0.019), bandas=3, fuerza=0.60, spec=0.16, umbral=0.80)
M_CUERO = toon("M_Cuero_oscuro", (0.032, 0.018, 0.012), bandas=3, fuerza=0.60)
M_LATON = toon("M_Laton", (0.434, 0.262, 0.051), bandas=3, fuerza=0.62, spec=0.30, umbral=0.72)
M_CAMUZA = toon("M_Camuza", (0.552, 0.352, 0.156), bandas=3, fuerza=0.64)
M_PANUELO = toon("M_Panuelo", (0.479, 0.027, 0.019), bandas=3, fuerza=0.62)
M_CONT = material_contorno()

G_ROPA, G_BOTA, G_FINO = 0.0013, 0.0016, 0.0009     # contorno (m): brief §4.2

INFO = collections.OrderedDict()


# ------------------------------------------------------------- extracción
def islas(bm):
    vistos = set()
    out = []
    for f in bm.faces:
        if f.index in vistos:
            continue
        isla, pila = [], [f]
        while pila:
            g = pila.pop()
            if g.index in vistos:
                continue
            vistos.add(g.index)
            isla.append(g)
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in vistos:
                        pila.append(h)
        out.append(isla)
    out.sort(key=len, reverse=True)
    return out


def lazos_borde(bm):
    """Lazos de aristas de borde (listas de BMEdge) de una malla."""
    be = [e for e in bm.edges if e.is_boundary]
    adj = {}
    for e in be:
        for v in e.verts:
            adj.setdefault(v.index, []).append(e)
    vistos, lazos = set(), []
    for e in be:
        if e.index in vistos:
            continue
        pila, lazo = [e], []
        while pila:
            g = pila.pop()
            if g.index in vistos:
                continue
            vistos.add(g.index)
            lazo.append(g)
            for v in g.verts:
                for h in adj[v.index]:
                    if h.index not in vistos:
                        pila.append(h)
        lazos.append(lazo)
    return lazos


def envolver_sobre_piel(o, offset, grupo=None):
    """Shrinkwrap ABOVE_SURFACE sobre la piel con los modificadores del cuerpo
    APAGADOS: el objetivo se evalúa con modificadores y el casco del contorno
    (normales invertidas, 1,3 mm fuera) es lo que encontraba; «encima» de él es
    DENTRO del cuerpo (informe técnico §4.2)."""
    vis = [(m, m.show_viewport) for m in ob.modifiers]
    for m, _ in vis:
        m.show_viewport = False
    sw = o.modifiers.new("Envolver", 'SHRINKWRAP')
    sw.target = ob
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.wrap_mode = 'ABOVE_SURFACE'
    sw.offset = offset
    if grupo:
        sw.vertex_group = grupo
    aplicar(o, sw)
    for m, vv in vis:
        m.show_viewport = vv


def cortar(bm, co, no, pred=None):
    """Corte plano; borra el lado hacia el que apunta `no`. Devuelve los
    vértices del corte (se dejan fijos al suavizar bordes). Con `pred(v)` el
    corte se limita a la geometría cuyos vértices lo cumplen: un plano
    inclinado (la sisa, perpendicular al eje del brazo) atraviesa también el
    tronco y sin el subconjunto se llevaba medio costado."""
    if pred is None:
        geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    else:
        lay = bm.verts.layers.int.get("orig")
        vs = [v for v in bm.verts if pred(v, v[lay] if lay else -1)]
        ok = set(v.index for v in vs)
        geom = vs + [e for e in bm.edges if all(v.index in ok for v in e.verts)] \
            + [f for f in bm.faces if all(v.index in ok for v in f.verts)]
    r = bmesh.ops.bisect_plane(bm, geom=geom,
                               plane_co=co, plane_no=no, clear_outer=True, clear_inner=False)
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    return {g.index for g in r['geom_cut'] if isinstance(g, bmesh.types.BMVert)}


def extraer(nombre, huesos, umbral=0.5, filtro=None, cortes=(), empuje=0.005, empuje_fn=None,
            suavizar_borde=2, decimar=None, isla_mayor=True, suavizar_zona=None, tapar_huecos=40,
            envolver=None, preproceso=None):
    """Duplica las caras del cuerpo cuyos vértices pesan >= umbral en `huesos`
    y pasan `filtro(co)`, las corta con planos, suaviza los bordes libres,
    empuja por la normal (de la prenda ya separada) y decima. Devuelve el
    objeto con los grupos de hueso heredados. Grosor, materiales y contorno
    los pone `acabar()`."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    orig = bm.verts.layers.int.new("orig")
    for v in bm.verts:
        v[orig] = v.index
    en = set(i for i in range(N) if zona_w(i, huesos) >= umbral and (filtro is None or filtro(me.vertices[i].co)))
    keep = set(f.index for f in bm.faces if all(v.index in en for v in f.verts))
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.index not in keep], context='FACES')
    bm.verts.ensure_lookup_table()
    bm.faces.ensure_lookup_table()
    if isla_mayor:
        isl = islas(bm)
        if len(isl) > 1:
            bmesh.ops.delete(bm, geom=[f for isla in isl[1:] for f in isla], context='FACES')
    fijos = set()
    for corte in cortes:
        fijos |= cortar(bm, *corte)
    if tapar_huecos:
        # Huecos de la selección por pesos (la valona tenía dos de 11 aristas
        # tras decimar —unas 20 antes— en la punta de los hombros y el jubón
        # asomaba azul por ellos): se tapa todo lazo de borde de <= tapar_huecos
        # aristas que NO sea un corte plano (esos son las aperturas de verdad).
        # Las prendas con aperturas libres (mangas: hombro y muñeca por pesos)
        # pasan un umbral bajo.
        tapados = 0
        for lazo in lazos_borde(bm):
            es_corte = all(v.index in fijos for e in lazo for v in e.verts)
            if len(lazo) <= tapar_huecos and not es_corte:
                r = bmesh.ops.holes_fill(bm, edges=lazo)
                bmesh.ops.triangulate(bm, faces=r['faces'])
                tapados += 1
        if tapados:
            print(f"[ROPA]   {nombre}: {tapados} huecos tapados")
    bm.verts.ensure_lookup_table()
    if preproceso:
        preproceso(bm)
    borde = [v for v in bm.verts if v.is_boundary and v.index not in fijos]
    for _ in range(suavizar_borde):
        bmesh.ops.smooth_vert(bm, verts=borde, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    if suavizar_zona:
        sel = [v for v in bm.verts if suavizar_zona[0](v.co)]
        for _ in range(suavizar_zona[1]):
            bmesh.ops.smooth_vert(bm, verts=sel, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.normal_update()
    emp = []
    for v in bm.verts:
        d = empuje_fn(v.co, v.normal) if empuje_fn else empuje
        emp.append(d)
        v.co = v.co + v.normal * d
    bm.verts.layers.int.remove(orig)
    nm = bpy.data.meshes.new(nombre)
    bm.to_mesh(nm)
    bm.free()
    o = bpy.data.objects.new(nombre, nm)
    bpy.context.collection.objects.link(o)
    for g in GRUPOS_CUERPO:          # mismo orden que el cuerpo: la capa deform lo exige
        o.vertex_groups.new(name=g)
    nm.shade_smooth()
    n0 = tris_de(o)
    if decimar:
        d = o.modifiers.new("Decimar", 'DECIMATE')
        d.ratio = decimar
        d.use_collapse_triangulate = False
        aplicar(o, d)
    if envolver:
        envolver_sobre_piel(o, envolver)
    INFO.setdefault(nombre, {})
    INFO[nombre].update(caras_extraidas=len(keep), tris_brutos=n0, tris_decimados=tris_de(o),
                        empuje_mm=(round(min(emp) * 1000, 1), round(max(emp) * 1000, 1)))
    print(f"[ROPA] {nombre}: {len(keep)} caras -> {n0} tris -> decimado {tris_de(o)} | empuje {min(emp)*1000:.1f}-{max(emp)*1000:.1f} mm")
    return o


def medir_piel(o):
    """Vértices de la prenda bajo la piel (distancia firmada a la piel real)."""
    bajo, dmin = 0, 1e9
    for v in o.data.vertices:
        loc, nor, idx, d = BVH_PIEL.find_nearest(v.co)
        s = (v.co - loc).dot(nor)
        dmin = min(dmin, s)
        if s < 0.0005:
            bajo += 1
    return bajo, dmin


def acabar(o, mat, grosor, contorno_g=G_ROPA, solo_canto=True, mats_extra=()):
    """Materiales, grosor (Solidify hacia dentro) y contorno, APLICADOS como
    geometría: en el juego solo queda el Armature (informe técnico §6)."""
    bajo, dmin = medir_piel(o)
    INFO.setdefault(o.name, {}).update(bajo_piel=bajo, dist_min_mm=round(dmin * 1000, 1), verts=len(o.data.vertices))
    o.data.materials.append(mat)
    for m in mats_extra:
        o.data.materials.append(m)
    if grosor > 0.0:
        s = o.modifiers.new("Grosor", 'SOLIDIFY')
        s.thickness = grosor
        s.offset = -1.0            # crece hacia la piel: la cara exterior no se mueve
        s.use_rim = True
        s.use_rim_only = solo_canto
        s.use_even_offset = True
        aplicar(o, s)
    t_sin = tris_de(o)
    c = contorno(o, contorno_g, material=M_CONT)
    aplicar(o, c)
    o.visible_shadow = False       # acné de sombra de EEVEE Next (informe técnico §4.6)
    o.game.physics_type = 'NO_COLLISION'
    INFO[o.name].update(tris_sin_contorno=t_sin, tris=tris_de(o))
    print(f"[ROPA] {o.name}: {t_sin} tris + contorno = {tris_de(o)} | bajo piel {bajo} (mín {dmin*1000:.1f} mm)")
    return o


def unir(nombre, partes):
    activar(partes[0])
    for p in partes[1:]:
        p.select_set(True)
    bpy.ops.object.join()
    o = bpy.context.view_layer.objects.active
    o.name = nombre
    o.data.name = nombre
    return o


def pesos_a(o, asign):
    """asign(v) -> [(hueso, peso)]. Limpia y asigna."""
    for g in list(o.vertex_groups):
        o.vertex_groups.remove(g)
    grupos = {}
    for v in o.data.vertices:
        for h, w in asign(v):
            if h not in grupos:
                grupos[h] = o.vertex_groups.new(name=h)
            grupos[h].add([v.index], w, 'REPLACE')


def limpiar_grupos(o):
    """Quita los grupos que no son huesos o están vacíos."""
    usados = collections.Counter()
    for v in o.data.vertices:
        for g in v.groups:
            if g.weight > 0.0:
                usados[g.group] += 1
    for g in list(o.vertex_groups):
        if g.name not in PESOS or usados[g.index] == 0:
            o.vertex_groups.remove(g)


def rayo_frente(x, z):
    """y de la piel en la cara delantera del cuerpo en (x, z)."""
    h = BVH_PIEL.ray_cast(Vector((x, -0.8, z)), Vector((0, 1, 0)), 1.6)
    return h[0].y if h[0] is not None else None


def malla_de(nombre, verts, caras, mat, mats_extra=()):
    nm = bpy.data.meshes.new(nombre)
    nm.from_pydata([tuple(v) for v in verts], [], caras)
    nm.update()
    o = bpy.data.objects.new(nombre, nm)
    bpy.context.collection.objects.link(o)
    nm.materials.append(mat)
    for m in mats_extra:
        nm.materials.append(m)
    nm.shade_smooth()
    return o


# ================================================================= JUBÓN
# Coleto sin mangas: tronco + clavículas + casquete del hombro + tirilla del
# cuello. Abajo se corta plano en z 1,03: el pico de 35 mm del brief (borde a
# 1,04 en los lados y 1,005 al frente) queda ENTERO bajo la pretina (z 0,995-
# 1,055), así que no se modela lo que no se ve. Arriba, tirilla hasta z 1,385
# (base del cuello). Holgura: 7 mm (ease +25 de perímetro = +4 de radio, más
# 3 de margen para que la piel no asome al decimar); en el casquete del hombro
# sube a 14 mm para quedar SOBRE la manga (8 mm + 2 de grosor) y su borde libre
# (la sisa) lleva 4 mm más: son las «aletas» de 25 mm del brief, leídas como un
# labio que remata la sisa.
Z_JUB_BAJO, Z_TIRILLA = 1.03, 1.385


def empuje_jubon(co, n):
    d = 0.007 + 0.007 * smoothstep(0.13, 0.19, abs(co.x)) * smoothstep(1.20, 1.27, co.z)
    return lerp(d, 0.006, smoothstep(1.34, 1.36, co.z))     # tirilla ceñida


# Sisa: el borde de la selección por pesos/filtro es dentado (se veía en
# exp1-exp9 y en la iteración 1). Se corta con un plano PERPENDICULAR AL EJE
# DEL BRAZO en t = 0,17 (z 1,235 en el eje), limitado a la geometría del brazo
# (upperarm >= 0,3 y por fuera de |x| 0,13): el plano inclinado cruza también
# el costado y sin ese límite se llevaba el pecho.
T_SISA = 0.17
_cortes_jubon = [((0, 0, Z_JUB_BAJO), (0, 0, -1)), ((0, 0, Z_TIRILLA), (0, 0, 1))]
_T_ARM = {s: t_brazo(s) for s in "lr"}
for s, sg in (("l", 1.0), ("r", -1.0)):
    t_de, H, eje = _T_ARM[s]
    P = H + eje * (T_SISA * (MUNECA[s] - HOMBRO[s]).length)
    _cortes_jubon.append((tuple(P), tuple(eje),
                          lambda v, oi, sg=sg, s=s: v.co.x * sg > 0.13 and oi >= 0 and peso[oi].get(f"upperarm_{s}", 0.0) >= 0.3))
jubon = extraer("Alonso_Ropa_Jubon",
                ["spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "pelvis", "neck_01",
                 "upperarm_l", "upperarm_r"], 0.5,
                filtro=lambda c: 1.00 <= c.z <= 1.40 and (abs(c.x) < 0.19 or
                                                          (_T_ARM["l" if c.x > 0 else "r"][0](c) < 0.24 and c.z > 1.15)),
                cortes=_cortes_jubon, empuje_fn=empuje_jubon, decimar=0.45)
# aletas: el borde libre de la sisa sale 4 mm más
bm = bmesh.new()
bm.from_mesh(jubon.data)
bm.normal_update()
for v in bm.verts:
    if v.is_boundary and Z_JUB_BAJO + 0.003 < v.co.z < Z_TIRILLA - 0.003:
        v.co += v.normal * 0.004
bm.to_mesh(jubon.data)
bm.free()
acabar(jubon, M_JUBON, 0.004)

# ------------------------------------------------------------- FALDILLAS
# 8 haldetas trapezoidales (Museo del Traje, jubón 1580-1620): 70 mm de alto,
# 84 mm arriba -> 96 abajo, grosor 5. Cuelgan del borde INFERIOR de la pretina
# (z 1,005 -> 0,935, con la fila de arriba metida 3 mm bajo la correa) y no
# de z 1,04 como decía el brief: colgadas de 1,04 la pretina de 50 mm tapaba
# 40 de los 70 mm y solo asomaban 30. El ancho 84->96 (x1,143) se consigue
# abriéndolas 16° hacia fuera, que es lo que hace un paño de 5 mm apoyado en el
# volumen de los greguescos (holgura 22 mm bajo la pretina). Cada haldeta tiene
# 2x2 cuadros para que los huesos faldilla_f/_b del carril RIG la doblen.
Z_FAL_ALTO, Z_FAL_BAJO = 1.005, 0.935
C_CINT = Vector((0.0, -0.0227, 0.0))     # centro de la rebanada z 1,025 (medido)
OFF_PRETINA = 0.013                       # empuje de la pretina (ver abajo)
V, F = [], []
for k in range(8):
    a0 = (k + 0.5) * (2 * math.pi / 8)     # centrada en cada octante: 2 delante, 2 detrás, 2 por lado
    span = (2 * math.pi / 8) * (84.0 / 93.0)
    for r_i in range(3):                    # 3 filas: 1,00 / 0,965 / 0,93
        u = r_i / 2.0
        z = lerp(Z_FAL_ALTO, Z_FAL_BAJO, u)
        for c_i in range(3):                # 3 columnas
            a = a0 + (c_i / 2.0 - 0.5) * span
            d = Vector((math.sin(a), -math.cos(a), 0.0))      # a=0 al frente (-Y)
            # radio de la piel en esa dirección a la altura de la pretina
            h = BVH_PIEL.ray_cast(Vector((C_CINT.x, C_CINT.y, 1.000)), d, 0.4)
            r_piel = (h[0] - Vector((C_CINT.x, C_CINT.y, 1.000))).length if h[0] is not None else 0.13
            r = r_piel + OFF_PRETINA - 0.003 + 0.023 * u        # nace 3 mm dentro de la pretina y abre 20 mm en 70: 16°
            V.append(Vector((C_CINT.x, C_CINT.y, z)) + d * r)
    b = k * 9
    for r_i in range(2):
        for c_i in range(2):
            i0 = b + r_i * 3 + c_i
            F.append((i0, i0 + 1, i0 + 4, i0 + 3))
faldillas = malla_de("Alonso_Ropa_Faldillas", V, F, M_JUBON)


def _w_fald(v):
    lado = "l" if v.co.x >= 0 else "r"
    u = (Z_FAL_ALTO - v.co.z) / (Z_FAL_ALTO - Z_FAL_BAJO)
    wt = 0.4 * u                       # abajo 0,6 pelvis / 0,4 muslo (brief §5.2)
    return [("pelvis", 1.0 - wt), (f"thigh_{lado}", wt)] if wt > 0 else [("pelvis", 1.0)]


pesos_a(faldillas, _w_fald)
INFO["Alonso_Ropa_Faldillas"] = dict(caras_extraidas=0, tris_brutos=tris_de(faldillas), tris_decimados=tris_de(faldillas), empuje_mm=(0, 0))
acabar(faldillas, M_JUBON, 0.005, solo_canto=False)

# ================================================================= CAMISA
# Mangas con vuelo 1,6x (brief §5.1): bíceps 240 -> 385 de perímetro = +23 mm
# de radio, antebrazo 180 -> 300 = +19. Perfil por t (0 hombro, 1 muñeca):
# 6 mm bajo el casquete del jubón (t < 0,25), sube a 18 mm en el antebrazo
# (t 0,45-0,60), y se frunce en un embudo largo a 9 mm en t 0,85 (donde empieza la manopla del
# guante, que va por ENCIMA con 8-14 mm y 3 de canto: con 5 mm quedaba un
# hueco de 5 mm en la boca de la manopla que se veía como una media luna
# gris) y a 3,6 mm en la muñeca. No se llega a
# los 23 del brief: con 18 la manga ya lee 120 mm de ancho y en la prueba
# posada del informe técnico la penetración del codo no crece con el empuje.
def empuje_manga(s):
    t_de, H, eje = t_brazo(s)

    def f(co, n):
        t = t_de(co)
        d = 0.006 + 0.012 * smoothstep(0.25, 0.45, t)
        d *= 1.0 - (1.0 - 9.0 / 18.0) * smoothstep(0.60, 0.85, t)
        d *= 1.0 - 0.60 * smoothstep(0.85, 0.97, t)
        return d
    return f


mangas = []
for s in "lr":
    m = extraer(f"tmp_manga_{s}", [f"upperarm_{s}", f"lowerarm_{s}"], 0.5,
                empuje_fn=empuje_manga(s), decimar=0.55, tapar_huecos=8)
    acabar(m, M_LIENZO, 0.0)          # sin canto: hombro bajo el jubón, puño dentro de la manopla
    mangas.append(m)

# Valona «a lo estudiantil, sin almidón y sin randas» (Quijote II,18): cuello
# vuelto liso de 70 mm que nace en el borde de la tirilla (z 1,385) y cae a
# z 1,315. Se extrae la banda del cuello y se RE-FORMA como cono: radio de la
# piel + 12 mm arriba (por fuera de la tirilla: 7 de holgura + 4 de grosor)
# abriendo 30 mm hacia abajo. Empujar por la normal no vale aquí: en la base
# del cuello las normales miran hacia arriba (trapecio) y el cuello subía en
# vez de abrirse.
C_CUELLO = Vector((0.0, -0.030, 0.0))
Z_VAL_ALTO, Z_VAL_BAJO = 1.385, 1.325
R_VALONA, FLARE_VALONA = 0.012, 0.024


def conificar(o, z_alto, z_bajo, r0, flare):
    for v in o.data.vertices:
        u = max(0.0, min(1.0, (z_alto - v.co.z) / (z_alto - z_bajo)))
        d = Vector((v.co.x - C_CUELLO.x, v.co.y - C_CUELLO.y, 0.0))
        rv = d.length
        d.normalize()
        r = rv + r0 + flare * u
        v.co = Vector((C_CUELLO.x, C_CUELLO.y, lerp(z_alto, z_bajo, u))) + d * r


valona = extraer("tmp_valona", ["neck_01", "spine_03", "clavicle_l", "clavicle_r", "upperarm_l", "upperarm_r"], 0.35,
                 filtro=lambda c: 1.29 <= c.z <= 1.41,
                 cortes=[((0, 0, Z_VAL_BAJO), (0, 0, -1)), ((0, 0, Z_VAL_ALTO), (0, 0, 1))],
                 empuje=0.0, suavizar_borde=0, decimar=0.5)
conificar(valona, Z_VAL_ALTO, Z_VAL_BAJO, R_VALONA, FLARE_VALONA)
valona.data.update()
acabar(valona, M_LIENZO, 0.0)      # lienzo de 2 mm: el canto no se ve, el contorno sí
camisa = unir("Alonso_Ropa_Camisa", [mangas[0], mangas[1], valona])
INFO["Alonso_Ropa_Camisa"] = dict(
    caras_extraidas=sum(INFO[k]["caras_extraidas"] for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona")),
    tris_brutos=sum(INFO[k]["tris_brutos"] for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona")),
    tris_decimados=sum(INFO[k]["tris_decimados"] for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona")),
    empuje_mm=INFO["tmp_manga_l"]["empuje_mm"], bajo_piel=sum(INFO[k]["bajo_piel"] for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona")),
    dist_min_mm=min(INFO[k]["dist_min_mm"] for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona")),
    verts=len(camisa.data.vertices), tris_sin_contorno=sum(INFO[k]["tris_sin_contorno"] for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona")),
    tris=tris_de(camisa))
for k in ("tmp_manga_l", "tmp_manga_r", "tmp_valona"):
    del INFO[k]

# ================================================================= PAÑUELO
# Banda de 36 mm CEÑIDA al cuello (15 mm de holgura), z 1,372-1,408: justo
# encima de la tirilla (que acaba en 1,385 a 10 mm) y bajo la mandíbula. En la
# iteración 1 la banda iba de 1,345 a 1,385 siguiendo el cono de la valona y
# salía como un flotador rojo sobre un cuello marinero; anudado alto, el
# pañuelo es pañuelo y la valona asoma debajo como cuello de camisa. Nudo a la
# izquierda del personaje (+X) al frente, y dos colas de 220 y 170 mm, de
# 60 -> 20 mm de ancho, que caen sobre el pecho por delante del hombro
# izquierdo, a 46 mm de la piel junto al borde de la valona y a 20 mm sobre el
# jubón. Pesos: la banda hereda los del cuello; las colas van de neck_01
# (arriba) a spine_03 (abajo) hasta que el carril RIG ponga los 6 huesos
# panuelo_l1..3 / r1..3.
Z_PAN_ALTO, Z_PAN_BAJO = 1.408, 1.372
banda = extraer("tmp_panuelo_banda", ["neck_01", "head", "spine_03"], 0.35,
                filtro=lambda c: 1.35 <= c.z <= 1.43 and abs(c.x) < 0.12,
                cortes=[((0, 0, Z_PAN_BAJO), (0, 0, -1)), ((0, 0, Z_PAN_ALTO), (0, 0, 1))],
                empuje=0.0, suavizar_borde=0, decimar=0.6)
conificar(banda, Z_PAN_ALTO, Z_PAN_BAJO, 0.015, 0.0)
banda.data.update()
acabar(banda, M_PANUELO, 0.0, contorno_g=G_FINO)

NUDO = Vector((0.055, 0.0, 1.372))
y_n = rayo_frente(NUDO.x, NUDO.z)
NUDO.y = y_n - 0.015 - 0.012
knot_verts, knot_faces = [], []
# nudo: icosfera pequeña (r 17 mm) achatada contra el cuerpo
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=1, radius=0.017)
for v in bm.verts:
    v.co = Vector((v.co.x * 1.15, v.co.y * 0.7, v.co.z * 0.9)) + NUDO
knot_verts = [v.co.copy() for v in bm.verts]
knot_faces = [[v.index for v in f.verts] for f in bm.faces]
bm.free()
nudo = malla_de("tmp_nudo", knot_verts, knot_faces, M_PANUELO)
pesos_a(nudo, lambda v: [("neck_01", 1.0)])
INFO["tmp_nudo"] = dict(caras_extraidas=0, tris_brutos=tris_de(nudo), tris_decimados=tris_de(nudo), empuje_mm=(0, 0))
acabar(nudo, M_PANUELO, 0.0, contorno_g=G_FINO)


def cola(nombre, largo, x0, dx, ancho0, ancho1, n=6):
    V, F = [], []
    for i in range(n + 1):
        u = i / n
        z = NUDO.z - 0.010 - largo * u
        x = x0 + dx * u
        w = lerp(ancho0, ancho1, u)
        off = lerp(0.020, 0.046, smoothstep(1.26, 1.32, z))
        for sx in (-0.5, 0.5):
            xx = x + sx * w
            y = rayo_frente(xx, z)
            if y is None:
                y = rayo_frente(x, z) or -0.12
            V.append(Vector((xx, y - off, z)))
    for i in range(n):
        F.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
    o = malla_de(nombre, V, F, M_PANUELO)

    def w(v):
        u = (NUDO.z - v.co.z) / largo
        u = max(0.0, min(1.0, u))
        return [("neck_01", 1.0 - u), ("spine_03", u)] if u > 0 else [("neck_01", 1.0)]
    pesos_a(o, w)
    INFO[nombre] = dict(caras_extraidas=0, tris_brutos=tris_de(o), tris_decimados=tris_de(o), empuje_mm=(0, 0))
    acabar(o, M_PANUELO, 0.002, contorno_g=G_FINO, solo_canto=False)
    return o


cola_a = cola("tmp_cola_a", 0.220, NUDO.x + 0.010, 0.030, 0.060, 0.020)
cola_b = cola("tmp_cola_b", 0.170, NUDO.x - 0.020, -0.010, 0.055, 0.020)
partes = [banda, nudo, cola_a, cola_b]
nombres = [p.name for p in partes]
INFO["Alonso_Ropa_Panuelo"] = dict(
    caras_extraidas=INFO["tmp_panuelo_banda"]["caras_extraidas"],
    tris_brutos=sum(INFO[k]["tris_brutos"] for k in nombres),
    tris_decimados=sum(INFO[k]["tris_decimados"] for k in nombres), empuje_mm=(0, 0),
    bajo_piel=sum(INFO[k]["bajo_piel"] for k in nombres), dist_min_mm=min(INFO[k]["dist_min_mm"] for k in nombres),
    tris_sin_contorno=sum(INFO[k]["tris_sin_contorno"] for k in nombres))
panuelo = unir("Alonso_Ropa_Panuelo", partes)
INFO["Alonso_Ropa_Panuelo"].update(verts=len(panuelo.data.vertices), tris=tris_de(panuelo))
for k in nombres:
    del INFO[k]

# ================================================================= PRETINA
# Correa de 50 mm (3,0 % de la altura; Sora 3,2 %) en la cintura natural,
# z 0,995-1,055, 13 mm por fuera de la piel (jubón 7 + grosor 4 + 2). Hebilla
# de latón 60 x 50 x 4 al frente, un poco a la izquierda del personaje. Los
# tiros de la espada quedan pendientes (dependen de la vaina del carril ESPADA
# y del hueso `tiros` del carril RIG).
Z_PRE_BAJO, Z_PRE_ALTO = 0.995, 1.055
pretina = extraer("Alonso_Ropa_Pretina", ["pelvis", "spine_01", "spine_02"], 0.5,
                  filtro=lambda c: 0.97 <= c.z <= 1.08 and abs(c.x) < 0.19,
                  cortes=[((0, 0, Z_PRE_BAJO), (0, 0, -1)), ((0, 0, Z_PRE_ALTO), (0, 0, 1))],
                  empuje=OFF_PRETINA, suavizar_borde=0, decimar=0.4)
HEB = Vector((0.030, 0.0, 1.025))
HEB.y = rayo_frente(HEB.x, HEB.z) - OFF_PRETINA - 0.002
hx, hz, hy = 0.030, 0.025, 0.002
V = [HEB + Vector((sx * hx, sy * hy, sz * hz)) for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
F = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (1, 5, 7, 3), (0, 2, 6, 4)]
hebilla = malla_de("tmp_hebilla", V, F, M_LATON)
hebilla.data.shade_flat()
# pesos de la hebilla: los del vértice de la pretina más cercano
_kd_src = pretina.data.vertices


def _w_heb(v):
    best = min(_kd_src, key=lambda p: (p.co - v.co).length_squared)
    return [(pretina.vertex_groups[g.group].name, g.weight) for g in best.groups if g.weight > 0]


pesos_a(hebilla, _w_heb)
INFO["tmp_hebilla"] = dict(caras_extraidas=0, tris_brutos=12, tris_decimados=12, empuje_mm=(0, 0))
acabar(hebilla, M_LATON, 0.0, contorno_g=G_FINO)
acabar(pretina, M_CUERO, 0.005)
INFO["Alonso_Ropa_Pretina"].update(
    tris_brutos=INFO["Alonso_Ropa_Pretina"]["tris_brutos"] + 12,
    tris_sin_contorno=INFO["Alonso_Ropa_Pretina"]["tris_sin_contorno"] + INFO["tmp_hebilla"]["tris_sin_contorno"])
pretina = unir("Alonso_Ropa_Pretina", [pretina, hebilla])
INFO["Alonso_Ropa_Pretina"].update(verts=len(pretina.data.vertices), tris=tris_de(pretina))
del INFO["tmp_hebilla"]

# ============================================================== GREGUESCOS
# Valones ESTRECHOS de buriel (Quijote II,31): de la cintura (bajo la pretina,
# z 1,02) a 35 mm bajo la rodilla (z 0,455). Holgura: 22 mm en el muslo
# (perímetro 471 -> 640 = +27 de radio en el brief; 22 porque la cara interna
# del muslo NO puede empujarse tanto: el hueco entre muslos es de 21 mm a
# z 0,78 y 38 a z 0,74), así que hacia dentro (normal mirando al otro muslo)
# el empuje se limita a 6 mm por encima de z 0,68. Se estrecha a 6 mm en la
# jareta de la rodilla (380 de perímetro sobre 340) y a 5 bajo la pretina,
# con el escalón de 17 mm justo debajo de ella: son los greguescos «atacados»
# al jubón.
Z_GREG_ALTO, Z_JARETA = 1.02, 0.455


def empuje_greg(co, n):
    d = 0.005 + 0.017 * smoothstep(0.995, 0.93, co.z)          # escalón bajo la pretina
    d = lerp(0.006, d, smoothstep(Z_JARETA, Z_JARETA + 0.075, co.z))   # jareta
    hacia_dentro = max(0.0, -n.x * sgn(co.x))
    tope = lerp(d, 0.006, smoothstep(0.62, 0.70, co.z))
    return lerp(d, min(d, tope), hacia_dentro)


# La raja glútea se PUENTEA antes de empujar: cada vértice de la raja
# (|x| < 35 mm, y > 0) sube en y hasta 2 mm por debajo del glúteo a su misma
# altura (la raja mide 4-27 mm de hondo entre z 0,72 y 0,92). Sin esto las dos
# caras de la raja se cruzaban al empujar (30 aristas a -170°, 39-68 pares de
# caras solapadas en las iteraciones 2 y 3) y alisarlas (Laplaciano, 8 pases)
# no bastaba. La entrepierna delantera se alisa 6 pases: el bulto genital del
# basemesh dejaba un triángulo de sombra en el cel (iteración 1). Como el
# alisado encoge, después se ENVUELVE a 4 mm sobre la piel.
_GLUTEO = [(v.co.z, v.co.y) for v in me.vertices if 0.04 < abs(v.co.x) < 0.09 and v.co.y > 0 and 0.68 < v.co.z < 0.98]


def puente_raja(bm):
    for v in bm.verts:
        c = v.co
        if abs(c.x) < 0.035 and c.y > 0.0 and 0.70 < c.z < 0.95:
            cerca = [y for (z, y) in _GLUTEO if abs(z - c.z) < 0.012]
            yb = max(cerca) if cerca else min(_GLUTEO, key=lambda zy: abs(zy[0] - c.z))[1]
            v.co.y = max(c.y, yb - 0.002)

greguescos = extraer("Alonso_Ropa_Greguescos", ["pelvis", "spine_01", "thigh_l", "thigh_r", "calf_l", "calf_r"], 0.5,
                     filtro=lambda c: 0.40 <= c.z <= 1.06,
                     cortes=[((0, 0, Z_JARETA), (0, 0, -1)), ((0, 0, Z_GREG_ALTO), (0, 0, 1))],
                     empuje_fn=empuje_greg, suavizar_borde=0, decimar=0.5,
                     preproceso=puente_raja,
                     suavizar_zona=(lambda c: abs(c.x) < 0.055 and 0.69 < c.z < 0.83 and c.y < 0.0, 6), envolver=0.004)
acabar(greguescos, M_GREG, 0.005)

# ================================================================== BOTAS
# Medias botas «datiladas» (Quijote II,18) de camino: caña hasta z 0,30 (bajo
# el máximo de la pantorrilla, que asoma con la media por encima), pie x1,25
# en planta (242 -> ~300 de largo, 90 -> ~118 de ancho) escalado desde el
# tobillo, suela de 22 mm y una correa de 25 mm bajo la caña en cuero oscuro.
# Los dedos no se visten (informe técnico §4.3): se cortan en y = -0,145 y se
# cierra con una puntera de 4 anillos elípticos (dy = R·sin φ, ancho cos φ,
# alto 0,35 + 0,65·cos φ desde la SUELA) cerrada en abanico: redondeada y
# con altura en la punta, que es lo que quedaba pendiente.
Z_CANA, Y_CORTE, R_PUNTERA = 0.30, -0.145, 0.075
Y_CORTE2 = Y_CORTE + 0.015     # segundo corte tras decimar: el borde decimado se mueve hasta ~10 mm
Z_SUELA = 0.022


def puntera(o):
    kx_prev = 1.0
    bm = bmesh.new()
    bm.from_mesh(o.data)
    # los dedos ya se cortaron en y = Y_CORTE antes de decimar (así el decimado
    # se gasta en la bota y no en los dedos); aquí se recorta 15 mm más atrás
    # para tener un anillo PLANO y ÚNICO: con 4 mm (iteración 3) el decimado
    # había metido vértices del borde viejo detrás del plano, el anillo salía
    # en trozos y la extrusión plegaba la puntera (aristas a -179°)
    r = bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                               plane_co=(0.0, Y_CORTE2, 0.0), plane_no=(0.0, -1.0, 0.0),
                               clear_outer=True, clear_inner=False)
    frente = [g for g in r['geom_cut'] if isinstance(g, bmesh.types.BMEdge)]
    n_lazos = len([l for l in lazos_borde(bm) if any(abs(v.co.y - Y_CORTE2) < 1e-4 for e in l for v in e.verts)])
    if n_lazos != 1:
        print(f"[ROPA]   AVISO {o.name}: el anillo de la puntera tiene {n_lazos} lazos")
    fv = list({v for e in frente for v in e.verts})
    c = sum((v.co for v in fv), Vector()) / len(fv)
    c.z = min(v.co.z for v in fv)
    kz_prev = 1.0
    for ang in (22.0, 44.0, 64.0, 80.0):
        a = math.radians(ang)
        kx, kz = math.cos(a), 0.35 + 0.65 * math.cos(a)     # la punta conserva el 35 % de la altura: bota, no zapatilla
        r = bmesh.ops.extrude_edge_only(bm, edges=frente)
        nv = set(g for g in r['geom'] if isinstance(g, bmesh.types.BMVert))
        # SOLO las aristas entre dos vértices nuevos: los peldaños (vértice
        # viejo -> nuevo) también son de borde y en exp8/iteración 2 se
        # extruían con el anillo, plegando la puntera (aristas a -170°, trazos
        # negros del casco en la punta)
        frente = [g for g in r['geom'] if isinstance(g, bmesh.types.BMEdge) and all(v in nv for v in g.verts)]
        for v in nv:
            # el extruido nace en la posición del anillo anterior; se deshace
            # la escala anterior y se aplica la de este ángulo
            x0 = c.x + (v.co.x - c.x) / kx_prev
            z0 = c.z + (v.co.z - c.z) / kz_prev
            v.co = Vector((c.x + (x0 - c.x) * kx, Y_CORTE2 - R_PUNTERA * math.sin(a),
                           c.z + (z0 - c.z) * kz))
        kx_prev, kz_prev = kx, kz
    # cierre en abanico a un vértice central (un n-gon no plano se plegaba)
    fv2 = list({v for e in frente for v in e.verts})
    cc = sum((v.co for v in fv2), Vector()) / len(fv2)
    cc.y -= 0.004
    vc = bm.verts.new(cc)
    for e in frente:
        bm.faces.new((e.verts[0], e.verts[1], vc))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(o.data)
    bm.free()


def bandas_bota(o):
    """Corte limpio para la suela (material por cara sin dientes). Las dos
    correas de 25 mm del brief se probaron en la iteración 1 (cortes a z 0,257
    y 0,282 con relieve de 3 mm): no se veían ni en el render de detalle
    (cuero L* 16 sobre bota L* 33 en sombra) y costaban ~240 tris por bota."""
    bm = bmesh.new()
    bm.from_mesh(o.data)
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:],
                           plane_co=(0.0, 0.0, Z_SUELA), plane_no=(0.0, 0.0, 1.0),
                           clear_outer=False, clear_inner=False)
    for f in bm.faces:
        zc = sum(v.co.z for v in f.verts) / len(f.verts)
        f.material_index = 1 if zc < Z_SUELA else 0
    bm.to_mesh(o.data)
    bm.free()


botas = []
for s in "lr":
    b = extraer(f"tmp_bota_{s}", [f"foot_{s}", f"ball_{s}", f"calf_{s}"], 0.35,
                filtro=lambda c: c.z <= Z_CANA + 0.05,
                cortes=[((0, 0, Z_CANA), (0, 0, 1)), ((0, Y_CORTE, 0), (0, -1, 0))],
                empuje_fn=lambda c, n: 0.006 + 0.006 * smoothstep(0.09, 0.24, c.z),
                suavizar_borde=3, decimar=0.42)
    puntera(b)
    # pie x1,25 en planta desde el tobillo (z <= 0,04 entero, 1,0 a z 0,12);
    # la suela se aplana en z = 0 (el empuje la había bajado 6 mm bajo el suelo)
    T = TOBILLO[s]
    for v in b.data.vertices:
        k = 1.0 + 0.25 * (1.0 - smoothstep(0.04, 0.12, v.co.z))
        v.co.x = T.x + (v.co.x - T.x) * k
        v.co.y = T.y + (v.co.y - T.y) * k
        v.co.z = max(v.co.z, 0.0)
    # Shrinkwrap ABOVE_SURFACE (9 mm) solo en la parte que sigue a la piel
    # (y > -0,13: detrás de la puntera), con los modificadores del cuerpo
    # apagados (informe técnico §4.2: el casco del contorno engañaba al
    # shrinkwrap y metía la bota entera dentro del pie).
    gsw = b.vertex_groups.new(name="tmp_sw")
    gsw.add([v.index for v in b.data.vertices if v.co.y > -0.13 and v.co.z > 0.005], 1.0, 'REPLACE')
    vis = [(m, m.show_viewport) for m in ob.modifiers]
    for m, _ in vis:
        m.show_viewport = False
    sw = b.modifiers.new("Envolver", 'SHRINKWRAP')
    sw.target = ob
    sw.wrap_method = 'NEAREST_SURFACEPOINT'
    sw.wrap_mode = 'ABOVE_SURFACE'
    sw.offset = 0.009
    sw.vertex_group = "tmp_sw"
    aplicar(b, sw)
    for m, vv in vis:
        m.show_viewport = vv
    b.vertex_groups.remove(b.vertex_groups["tmp_sw"])
    b.data.materials.append(M_BOTA)
    b.data.materials.append(M_CUERO)
    bandas_bota(b)
    b.data.materials.clear()
    acabar(b, M_BOTA, 0.004, contorno_g=G_BOTA, mats_extra=(M_CUERO,))
    botas.append(b)
INFO["Alonso_Ropa_Botas"] = dict(
    caras_extraidas=sum(INFO[f"tmp_bota_{s}"]["caras_extraidas"] for s in "lr"),
    tris_brutos=sum(INFO[f"tmp_bota_{s}"]["tris_brutos"] for s in "lr"),
    tris_decimados=sum(INFO[f"tmp_bota_{s}"]["tris_decimados"] for s in "lr"),
    empuje_mm=INFO["tmp_bota_l"]["empuje_mm"], bajo_piel=sum(INFO[f"tmp_bota_{s}"]["bajo_piel"] for s in "lr"),
    dist_min_mm=min(INFO[f"tmp_bota_{s}"]["dist_min_mm"] for s in "lr"),
    tris_sin_contorno=sum(INFO[f"tmp_bota_{s}"]["tris_sin_contorno"] for s in "lr"))
botas_o = unir("Alonso_Ropa_Botas", botas)
INFO["Alonso_Ropa_Botas"].update(verts=len(botas_o.data.vertices), tris=tris_de(botas_o))
for s in "lr":
    del INFO[f"tmp_bota_{s}"]

# ================================================================ GUANTES
# Guantes de camuza: la mano es el propio cuerpo con M_Camuza (un guante
# geométrico costaría 12.600 tris con contorno: el presupuesto entero), más
# una manopla de 70 mm desde la muñeca hacia el codo (perímetro 150 -> 200:
# 8 -> 14 mm de holgura) que tapa el borde dentado del material de la mano y
# el fruncido de la manga. Se corta con dos planos perpendiculares al eje del
# brazo. La mano x1,10 del brief no se hace: es geometría del cuerpo (carril
# PELO) y la mano ya lee grande (210 mm).
MANO = [h for h in HUESOS if h.endswith(("_l", "_r")) and h.startswith(("hand", "index", "middle", "ring", "pinky", "thumb"))]
L_BRAZO = (MUNECA["l"] - HOMBRO["l"]).length
T_MANOPLA = 1.0 - 0.070 / L_BRAZO
manoplas = []
for s in "lr":
    t_de, H, eje = t_brazo(s)
    p0 = H + eje * (T_MANOPLA * L_BRAZO)
    p1 = H + eje * (1.04 * L_BRAZO)
    g = extraer(f"tmp_manopla_{s}", [f"lowerarm_{s}", f"hand_{s}"], 0.5,
                filtro=lambda c, t_de=t_de: 0.78 <= t_de(c) <= 1.12,
                cortes=[(tuple(p0), tuple(-eje)), (tuple(p1), tuple(eje))],
                empuje_fn=lambda c, n, t_de=t_de: lerp(0.014, 0.008, smoothstep(T_MANOPLA, 1.04, t_de(c))),
                suavizar_borde=0, decimar=0.4)
    acabar(g, M_CAMUZA, 0.003)
    manoplas.append(g)
INFO["Alonso_Ropa_Guantes"] = dict(
    caras_extraidas=sum(INFO[f"tmp_manopla_{s}"]["caras_extraidas"] for s in "lr"),
    tris_brutos=sum(INFO[f"tmp_manopla_{s}"]["tris_brutos"] for s in "lr"),
    tris_decimados=sum(INFO[f"tmp_manopla_{s}"]["tris_decimados"] for s in "lr"),
    empuje_mm=INFO["tmp_manopla_l"]["empuje_mm"], bajo_piel=sum(INFO[f"tmp_manopla_{s}"]["bajo_piel"] for s in "lr"),
    dist_min_mm=min(INFO[f"tmp_manopla_{s}"]["dist_min_mm"] for s in "lr"),
    tris_sin_contorno=sum(INFO[f"tmp_manopla_{s}"]["tris_sin_contorno"] for s in "lr"))
guantes = unir("Alonso_Ropa_Guantes", manoplas)
INFO["Alonso_Ropa_Guantes"].update(verts=len(guantes.data.vertices), tris=tris_de(guantes))
for s in "lr":
    del INFO[f"tmp_manopla_{s}"]

# ------------------------------------------- materiales sobre el cuerpo
# M_Contorno tiene que ser el ÚLTIMO slot del cuerpo (ver anima_toon.contorno):
# se saca y se vuelve a meter después de los materiales nuevos.
idx_c = [m.name if m else None for m in me.materials].index("M_Contorno")
me.materials.pop(index=idx_c)
me.materials.append(M_CAMUZA)
me.materials.append(M_MEDIAS)
me.materials.append(M_CONT)
I_CAMUZA, I_MEDIAS = 1, 2
for m in ob.modifiers:
    if m.type == 'SOLIDIFY' and m.name == "Contorno":
        m.material_offset = 32767
        m.material_offset_rim = 32767
T_DE_L, _, _ = t_brazo("l")
T_DE_R, _, _ = t_brazo("r")
n_guante = n_media = 0
for p in me.polygons:
    vs = p.vertices
    c = p.center
    t = T_DE_L(c) if c.x >= 0 else T_DE_R(c)
    if all(zona_w(i, MANO) >= 0.5 for i in vs) or (t > 0.86 and all(zona_w(i, ["lowerarm_l", "lowerarm_r", "hand_l", "hand_r"]) >= 0.5 for i in vs)):
        p.material_index = I_CAMUZA
        n_guante += 1
    elif 0.26 <= c.z <= 0.475 and all(zona_w(i, ["thigh_l", "thigh_r", "calf_l", "calf_r"]) >= 0.5 for i in vs):
        p.material_index = I_MEDIAS
        n_media += 1
print(f"[ROPA] guantes por material: {n_guante} caras; medias por material: {n_media} caras")

# ------------------------------------------------- piel tapada: borrar caras
# Solo CARAS (FACES_ONLY): los 13.380 vértices siguen en su índice para que
# MPFB2 pueda importar los pesos del rig por índice (carril RIG). Márgenes:
# tirilla (se deja el cuello entero), muñeca (30 mm bajo la manopla), jareta
# (35 mm: la media asoma si el greguesco sube), caña (40 mm dentro de la bota).
tapado = set()
Z_JUB = ["spine_01", "spine_02", "spine_03", "clavicle_l", "clavicle_r", "pelvis"]
for i in range(N):
    c = me.vertices[i].co
    if zona_w(i, Z_JUB) >= 0.6 and 1.00 <= c.z <= 1.355 and abs(c.x) < 0.17:
        tapado.add(i)
    if zona_w(i, ["pelvis", "thigh_l", "thigh_r", "calf_l", "calf_r", "spine_01"]) >= 0.6 and 0.49 <= c.z <= 1.00:
        tapado.add(i)
    t = T_DE_L(c) if c.x >= 0 else T_DE_R(c)
    if zona_w(i, ["upperarm_l", "lowerarm_l", "upperarm_r", "lowerarm_r"]) >= 0.65 and t < 0.64:
        tapado.add(i)
    if zona_w(i, ["foot_l", "ball_l", "foot_r", "ball_r", "calf_l", "calf_r"]) >= 0.6 and c.z <= Z_CANA - 0.04:
        tapado.add(i)
caras_tapadas = [p.index for p in me.polygons if all(vi in tapado for vi in p.vertices)]
tris_tapados = sum(len(me.polygons[i].vertices) - 2 for i in caras_tapadas)
n_caras_antes = len(me.polygons)
bm = bmesh.new()
bm.from_mesh(me)
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[i] for i in caras_tapadas], context='FACES_ONLY')
bm.to_mesh(me)
bm.free()
assert len(me.vertices) == N, "los vértices del cuerpo deben conservarse"
print(f"[ROPA] piel tapada borrada: {len(caras_tapadas)} de {n_caras_antes} caras ({tris_tapados} tris); verts {len(me.vertices)} (sin cambio)")

# ------------------------------------------------------------- remate
for o in bpy.data.objects:
    if o.name.startswith("Alonso_Ropa_"):
        limpiar_grupos(o)
        o.data.update()
# Solidify deja aristas sueltas sin uso en el cuerpo tras borrar caras: no
# importa para el render ni para el motor; se dejan para no tocar vértices.

ROPA = [o for o in bpy.data.objects if o.name.startswith("Alonso_Ropa_")]
tot = sum(tris_de(o) for o in ROPA)
tot_sin = sum(INFO[o.name]["tris_sin_contorno"] for o in ROPA)
lineas = [f"# Alonso vestido: triángulos por prenda (malla final, contorno aplicado como geometría)",
          f"# entrada {os.path.basename(IN_BLEND)} ({N} verts); cuerpo {n_caras_antes} -> {len(me.polygons)} caras "
          f"({tris_tapados} tris de piel tapada borrados; vértices intactos)",
          f"{'prenda':24s} {'verts':>6s} {'tris':>6s} {'sin_cont':>8s} {'extraidas':>9s} {'brutos':>6s} {'decim':>6s} {'bajo_piel':>9s} {'dmin_mm':>7s} {'empuje_mm':>12s}"]
for o in ROPA:
    d = INFO[o.name]
    lineas.append(f"{o.name:24s} {d['verts']:6d} {d['tris']:6d} {d['tris_sin_contorno']:8d} {d['caras_extraidas']:9d} {d['tris_brutos']:6d} "
                  f"{d['tris_decimados']:6d} {d['bajo_piel']:9d} {d['dist_min_mm']:7.1f} {str(d['empuje_mm']):>12s}")
lineas.append(f"{'TOTAL ROPA':24s} {sum(len(o.data.vertices) for o in ROPA):6d} {tot:6d} {tot_sin:8d}   (presupuesto 15000 con contorno)")
lineas.append(f"{'Alonso (cuerpo)':24s} {N:6d} {tris_de(ob):6d}   caras {len(me.polygons)}; con casco de contorno x2 = {2*tris_de(ob)}")
for l in lineas:
    print("[ROPA] " + l)
if METRICAS:
    open(METRICAS, "w").write("\n".join(lineas) + "\n")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[ROPA] guardado: {OUT_BLEND}")
print(f"[ROPA] ropa: {tot} tris con contorno ({tot_sin} sin) — {'OK' if tot <= 15000 else 'FUERA DE PRESUPUESTO'}")
print("[ROPA] OK")
