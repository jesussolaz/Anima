# ÁNIMA — El Charco: laguna manchega al atardecer, espejo del sol, casi mágica.
# Generador (herramienta de EDITOR, bpy). Determinista, semilla 1605.
#
#   cd ~/Flipendo/game/anima && Flipendo --background --factory-startup --python gen_charco.py
#
# Salida: ~/Flipendo/game/anima/Charco.blend. El .blend NO lleva Python: ni text blocks,
# ni logic bricks, ni controladores. El gameplay se ata con la propiedad de juego
# fl_component (componentes C++: PlayerController, ThirdPersonCamera, EnemyAI, Flotar,
# Girar). Doctrina C++ intacta.
#
# De dónde salen los números (informes de la noche del 12-09-2026):
#   dev/noche/informes/anima-escena-vision.md   — composición, sol, cielo, charco, orillas
#   dev/noche/informes/anima-escena-tecnica.md  — qué pinta el Blenderplayer (EEVEE Next/Metal)
# Solo se usa lo que la ficha técnica demostró que el Player pinta: SSR (use_raytracing,
# método SCREEN) sin sonda planar, Sun lamp + disco solar emisivo + halos aditivos
# (Add Shader Emission+Transparent, BLENDED), caja de niebla (el volumen del MUNDO sale
# negro en este build), Noise→Bump en el agua, cel/sombras normales. Nada de Nishita,
# nada de bloom, nada de mist_settings (en EEVEE Next la niebla del mundo es solo un pase).
#
# Marco: el camino de losas corre hacia +Y; el sol está 12° a la derecha (+X) de ese eje y
# a 5° sobre el horizonte. La cámara de juego queda detrás del jugador (−Y), así que al
# arrancar el reflejo del sol cae delante y a la derecha del personaje, sin taparlo, y al
# caminar hacia el sol el reflejo camina con él (d = h/tan 5° desde la cámara).

import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Vector, Matrix, Euler, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import anima_kit as K  # noqa: E402

random.seed(1605)

OUT_DIR = os.path.expanduser("~/Flipendo/game/anima")
OUT_BLEND = os.path.join(OUT_DIR, "Charco.blend")
MOLINO_BLEND = os.path.join(OUT_DIR, "Molino.blend")

# ----------------------------------------------------------------- cifras que mandan
MAP_HALF = 150.0            # terreno 300 × 300 m
GRID_N = 200                # celdas de 1,5 m
CORDAL_HALF = 660.0         # anillo lejano hasta 660 m (las lomas del horizonte)
CORDAL_CELL = 10.0

CHARCO_A = 65.0             # semieje X (130 m): lagunas manchegas someras (Manjavacas 231 ha)
CHARCO_B = 90.0             # semieje Y (180 m), eje mayor hacia el sol
Z_AGUA = 0.0                # lámina de agua
Z_LECHO = -0.02             # el terreno bajo el charco: 2 cm bajo el agua (Uyuni: 1-2 cm)

SOL_ELEV = math.radians(5.0)    # hora dorada; reflejo a 22,7 m delante del personaje
SOL_AZ = math.radians(12.0)     # 12° a la derecha del eje del camino (reflejo al 66 % del ancho)
S_DIR = Vector((math.sin(SOL_AZ) * math.cos(SOL_ELEV),
                math.cos(SOL_AZ) * math.cos(SOL_ELEV),
                math.sin(SOL_ELEV)))                 # hacia el sol
S_FLAT = Vector((math.sin(SOL_AZ), math.cos(SOL_AZ), 0.0))
DISCO_DIST = 420.0
DISCO_R = 16.0              # 16 m a 420 m = 4,4° (8× el real; 26 m tapaba el torso)

PLAYER_START = Vector((0.0, -30.0))     # en el camino, a 30 m del centro, mirando al sol
PLAYER_HALF_H = 0.875                   # cápsula 1,75 m; el origen del Player en el centro
CAM_LENS = 24.0             # ver README de la cámara más abajo
CAM_DIST = 7.0
CAM_ALTURA = 1.2

# molinos: 3 siluetas de Consuegra/Criptana a 290-316 m, 20-35° a la derecha del sol
MOLINOS = [(math.radians(32.0), 292.0), (math.radians(39.0), 300.0), (math.radians(47.0), 316.0)]
LOMA_AZ, LOMA_R = math.radians(40.0), 300.0
LOMA_C = Vector((LOMA_R * math.sin(LOMA_AZ), LOMA_R * math.cos(LOMA_AZ)))


# ----------------------------------------------------------------- utilidades
def ss(t):
    return K.smoothstep(0.0, 1.0, t)


def n3(x, y, s, z=7.7):
    return noise.noise(Vector((x * s, y * s, z)))


def wobble(theta):
    """Irregularidad de la orilla (±7 %): una laguna no es una elipse."""
    c, s = math.cos(theta), math.sin(theta)
    return (0.07 * noise.noise(Vector((c * 2.3, s * 2.3, 5.1)))
            + 0.03 * noise.noise(Vector((c * 6.0, s * 6.0, 9.2))))


def e_eff(x, y):
    """Coordenada elíptica: 1 en el borde nominal del charco."""
    u, v = x / CHARCO_A, y / CHARCO_B
    e = math.hypot(u, v)
    if e < 1e-6:
        return 0.0
    th = math.atan2(v, u)
    return e * (1.0 + wobble(th))


def h_terr(x, y):
    """Altura del suelo. Una sola función para el terreno y el cordal: coinciden en la costura."""
    e = e_eff(x, y)
    rel = 1.8 * n3(x, y, 0.012) + 0.5 * n3(x, y, 0.045) + 0.15 * n3(x, y, 0.12)
    rel = max(rel, -0.25)
    # lecho plano 2 cm bajo el agua; 8 cm en los primeros ~5 m (la línea de agua queda en
    # e ≈ 1,023); banda de barro que sube 30 cm en 20-25 m; el relieve entra después.
    h = (Z_LECHO + 0.08 * ss((e - 1.0) / 0.07) + 0.30 * ss((e - 1.03) / 0.30)
         + rel * ss((e - 1.05) / 0.35))
    r = math.hypot(x, y)
    rim = K.clamp01((r - 100.0) / 60.0) ** 1.7 * 7.0 * (0.6 + 0.4 * n3(x, y, 0.02))
    h += rim
    if r > 150.0:
        h += (r - 150.0) * 0.035
        h += 9.0 * (0.5 + 0.5 * n3(x, y, 0.006, 3.3)) * ss((r - 165.0) / 70.0)
        dl = (Vector((x, y)) - LOMA_C).length
        h += 10.0 * math.exp(-(dl * dl) / (2.0 * 55.0 * 55.0))     # la loma de los molinos
    return h


def new_obj(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def set_game(ob, physics='STATIC', bounds=None, ghost=False):
    g = ob.game
    g.physics_type = physics
    g.use_ghost = ghost
    if bounds:
        g.use_collision_bounds = True
        g.collision_bounds_type = bounds


def add_prop(ob, name, value):
    """Propiedad de juego. Los números van como FLOAT (el componente C++ los lee con
    GetNumber); los nombres de componente y ejes, como STRING."""
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    if isinstance(value, bool):
        t = 'BOOL'
    elif isinstance(value, int):
        t = 'INT'
    elif isinstance(value, float):
        t = 'FLOAT'
    else:
        t = 'STRING'
    bpy.ops.object.game_property_new(type=t, name=name)
    ob.game.properties[name].value = value
    ob.select_set(False)


def mat_pbr(name, color, rough=0.85, emit=None, emit_strength=0.0):
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (*color, 1.0)
    b.inputs["Roughness"].default_value = rough
    if emit is not None:
        b.inputs["Emission Color"].default_value = (*emit, 1.0)
        b.inputs["Emission Strength"].default_value = emit_strength
    m.diffuse_color = (*color, 1.0)
    return m


def mesh_obj(name, bm, mat, loc=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = new_obj(name, me)
    ob.location = loc
    if mat:
        me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def aim(ob, direction):
    ob.rotation_euler = Vector(direction).to_track_quat('-Z', 'Y').to_euler()


def ramp(cr, stops):
    """Rellena un ColorRamp con [(pos, (r,g,b)), ...]."""
    cr.elements[0].position = stops[0][0]
    cr.elements[0].color = (*stops[0][1], 1.0)
    cr.elements[-1].position = stops[-1][0]
    cr.elements[-1].color = (*stops[-1][1], 1.0)
    for pos, col in stops[1:-1]:
        e = cr.elements.new(pos)
        e.color = (*col, 1.0)


# ----------------------------------------------------------------- limpiar
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.lights, bpy.data.cameras,
             bpy.data.worlds, bpy.data.images):
    for x in list(coll):
        coll.remove(x)
sc = bpy.context.scene
sc.name = "Charco"

# ----------------------------------------------------------------- materiales sencillos
M_HEROE = mat_pbr("M_Heroe", (0.20, 0.30, 0.55), 0.7)
M_PIEL = mat_pbr("M_Piel", (0.85, 0.66, 0.50), 0.85)
M_PESADILLA = mat_pbr("M_Pesadilla", (0.05, 0.045, 0.08), 0.98)
M_PESADILLA_OJO = mat_pbr("M_PesadillaOjo", (0.75, 0.60, 0.95), 0.5,
                          emit=(0.70, 0.55, 0.95), emit_strength=3.0)
M_CORDAL = mat_pbr("M_Cordal", (0.50, 0.38, 0.30), 0.95, emit=(0.62, 0.42, 0.34),
                   emit_strength=0.20)   # la distancia se come el contraste: se tiñe del aire
# Materiales con el atributo "Col" (los construye Build): losas, rocas, juncos, motas.
M_LOSA = K.make_mat("M_Losa", (0.30, 0.29, 0.27), rough=0.45, mottle=0.12, mottle_scale=3.0)
M_ROCA = K.make_mat("M_Roca", (0.40, 0.37, 0.34), rough=0.9, mottle=0.15, mottle_scale=2.0)
M_JUNCO = K.make_mat("M_Junco", (0.46, 0.40, 0.22), rough=0.9)
M_PANICULA = K.make_mat("M_Panicula", (0.42, 0.34, 0.40), rough=0.9)
M_ANIMA = K.make_mat("M_Anima", (1.0, 0.78, 0.30), rough=0.4, emit=(1.0, 0.72, 0.22),
                     emit_str=1.0)   # fuerza 1,0 + halo aditivo: a 5 son puntos duros

# ----------------------------------------------------------------- terreno 300 × 300 m
print("[CHARCO] terreno…")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=GRID_N, y_segments=GRID_N, size=MAP_HALF)
for v in bm.verts:
    v.co.z = h_terr(v.co.x, v.co.y)
me_t = bpy.data.meshes.new("Terreno")
bm.to_mesh(me_t)
bm.free()
terreno = new_obj("Terreno", me_t)
for p in me_t.polygons:
    p.use_smooth = True

# máscaras por vértice: orilla de barro (0-25 m), banda húmeda (0-4 m), costra de sal (1-3 m
# más allá de la línea de agua, que cae en e ≈ 1,023)
a_orilla = me_t.color_attributes.new(name="Orilla", type='FLOAT_COLOR', domain='POINT')
a_humedo = me_t.color_attributes.new(name="Humedo", type='FLOAT_COLOR', domain='POINT')
a_sal = me_t.color_attributes.new(name="Sal", type='FLOAT_COLOR', domain='POINT')
for i, v in enumerate(me_t.vertices):
    e = e_eff(v.co.x, v.co.y)
    o = 1.0 - ss((e - 1.0) / 0.30)
    hm = 1.0 - ss((e - 1.0) / 0.05)
    sl = ss((e - 1.03) / 0.010) * (1.0 - ss((e - 1.06) / 0.015))
    a_orilla.data[i].color = (o, o, o, 1.0)
    a_humedo.data[i].color = (hm, hm, hm, 1.0)
    a_sal.data[i].color = (sl, sl, sl, 1.0)

# material: ocre manchego lejos; barro agrietado (Voronoi: polígonos 0,3-0,8 m, grietas
# 2-4 cm, bordes levantados por Bump) en la orilla; oscuro y liso donde está mojado; sal.
mt = bpy.data.materials.new("M_Terreno")
mt.use_nodes = True
nt = mt.node_tree
bsdf = nt.nodes["Principled BSDF"]
tc = nt.nodes.new("ShaderNodeTexCoord")
at_o = nt.nodes.new("ShaderNodeAttribute"); at_o.attribute_name = "Orilla"
at_h = nt.nodes.new("ShaderNodeAttribute"); at_h.attribute_name = "Humedo"
at_s = nt.nodes.new("ShaderNodeAttribute"); at_s.attribute_name = "Sal"

# lejos: ocre con moteado grande y manchas de rastrojo
far_rgb = nt.nodes.new("ShaderNodeRGB"); far_rgb.outputs[0].default_value = (0.58, 0.42, 0.23, 1.0)
nz1 = nt.nodes.new("ShaderNodeTexNoise"); nz1.inputs["Scale"].default_value = 0.04; nz1.inputs["Detail"].default_value = 4.0
mr1 = nt.nodes.new("ShaderNodeMapRange"); mr1.inputs["To Min"].default_value = 0.80; mr1.inputs["To Max"].default_value = 1.15
mfar = nt.nodes.new("ShaderNodeMix"); mfar.data_type = 'RGBA'; mfar.blend_type = 'MULTIPLY'; mfar.inputs["Factor"].default_value = 1.0
nt.links.new(tc.outputs["Object"], nz1.inputs["Vector"])
nt.links.new(nz1.outputs["Fac"], mr1.inputs["Value"])
nt.links.new(far_rgb.outputs[0], mfar.inputs["A"])
nt.links.new(mr1.outputs["Result"], mfar.inputs["B"])
nz2 = nt.nodes.new("ShaderNodeTexNoise"); nz2.inputs["Scale"].default_value = 0.012; nz2.inputs["Detail"].default_value = 3.0
mr2 = nt.nodes.new("ShaderNodeMapRange"); mr2.inputs["From Min"].default_value = 0.45; mr2.inputs["From Max"].default_value = 0.62; mr2.clamp = True
mras = nt.nodes.new("ShaderNodeMix"); mras.data_type = 'RGBA'; mras.inputs["B"].default_value = (0.50, 0.45, 0.22, 1.0)
nt.links.new(tc.outputs["Object"], nz2.inputs["Vector"])
nt.links.new(nz2.outputs["Fac"], mr2.inputs["Value"])
nt.links.new(mr2.outputs["Result"], mras.inputs["Factor"])
nt.links.new(mfar.outputs["Result"], mras.inputs["A"])

# barro agrietado
vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.voronoi_dimensions = '2D'; vor.feature = 'DISTANCE_TO_EDGE'
vor.inputs["Scale"].default_value = 1.8          # celdas ≈ 0,55 m
vor.inputs["Randomness"].default_value = 0.85
nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
crack = nt.nodes.new("ShaderNodeMapRange"); crack.inputs["From Min"].default_value = 0.012; crack.inputs["From Max"].default_value = 0.040
crack.inputs["To Min"].default_value = 1.0; crack.inputs["To Max"].default_value = 0.0; crack.clamp = True
nt.links.new(vor.outputs["Distance"], crack.inputs["Value"])
mud_rgb = nt.nodes.new("ShaderNodeRGB"); mud_rgb.outputs[0].default_value = (0.36, 0.26, 0.18, 1.0)
dark = nt.nodes.new("ShaderNodeMapRange"); dark.inputs["To Min"].default_value = 1.0; dark.inputs["To Max"].default_value = 0.35
nt.links.new(crack.outputs["Result"], dark.inputs["Value"])
mmud = nt.nodes.new("ShaderNodeMix"); mmud.data_type = 'RGBA'; mmud.blend_type = 'MULTIPLY'; mmud.inputs["Factor"].default_value = 1.0
nt.links.new(mud_rgb.outputs[0], mmud.inputs["A"])
nt.links.new(dark.outputs["Result"], mmud.inputs["B"])
# mezcla lejos/orilla, humedad, sal
mix_o = nt.nodes.new("ShaderNodeMix"); mix_o.data_type = 'RGBA'
nt.links.new(mras.outputs["Result"], mix_o.inputs["A"])
nt.links.new(mmud.outputs["Result"], mix_o.inputs["B"])
nt.links.new(at_o.outputs["Fac"], mix_o.inputs["Factor"])
wet = nt.nodes.new("ShaderNodeMapRange"); wet.inputs["To Min"].default_value = 1.0; wet.inputs["To Max"].default_value = 0.55
nt.links.new(at_h.outputs["Fac"], wet.inputs["Value"])
mix_w = nt.nodes.new("ShaderNodeMix"); mix_w.data_type = 'RGBA'; mix_w.blend_type = 'MULTIPLY'; mix_w.inputs["Factor"].default_value = 1.0
nt.links.new(mix_o.outputs["Result"], mix_w.inputs["A"])
nt.links.new(wet.outputs["Result"], mix_w.inputs["B"])
nz3 = nt.nodes.new("ShaderNodeTexNoise"); nz3.inputs["Scale"].default_value = 0.9; nz3.inputs["Detail"].default_value = 3.0
mr3 = nt.nodes.new("ShaderNodeMapRange"); mr3.inputs["From Min"].default_value = 0.40; mr3.inputs["From Max"].default_value = 0.60; mr3.clamp = True
salf = nt.nodes.new("ShaderNodeMath"); salf.operation = 'MULTIPLY'
nt.links.new(tc.outputs["Object"], nz3.inputs["Vector"])
nt.links.new(nz3.outputs["Fac"], mr3.inputs["Value"])
nt.links.new(at_s.outputs["Fac"], salf.inputs[0])
nt.links.new(mr3.outputs["Result"], salf.inputs[1])
mix_s = nt.nodes.new("ShaderNodeMix"); mix_s.data_type = 'RGBA'; mix_s.inputs["B"].default_value = (0.86, 0.83, 0.78, 1.0)
nt.links.new(mix_w.outputs["Result"], mix_s.inputs["A"])
nt.links.new(salf.outputs["Value"], mix_s.inputs["Factor"])
nt.links.new(mix_s.outputs["Result"], bsdf.inputs["Base Color"])
# aspereza: 0,95 seco, 0,35 mojado (el barro húmedo refleja el cielo por SSR)
rgh = nt.nodes.new("ShaderNodeMapRange"); rgh.inputs["To Min"].default_value = 0.95; rgh.inputs["To Max"].default_value = 0.35
nt.links.new(at_h.outputs["Fac"], rgh.inputs["Value"])
nt.links.new(rgh.outputs["Result"], bsdf.inputs["Roughness"])
# relieve de las grietas solo en la orilla
hgt = nt.nodes.new("ShaderNodeMapRange"); hgt.inputs["From Max"].default_value = 0.06; hgt.clamp = True
nt.links.new(vor.outputs["Distance"], hgt.inputs["Value"])
hmul = nt.nodes.new("ShaderNodeMath"); hmul.operation = 'MULTIPLY'
nt.links.new(hgt.outputs["Result"], hmul.inputs[0])
nt.links.new(at_o.outputs["Fac"], hmul.inputs[1])
bump = nt.nodes.new("ShaderNodeBump"); bump.inputs["Strength"].default_value = 0.5; bump.inputs["Distance"].default_value = 0.04
nt.links.new(hmul.outputs["Value"], bump.inputs["Height"])
nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
mt.diffuse_color = (0.50, 0.38, 0.22, 1.0)
me_t.materials.append(mt)
set_game(terreno, 'STATIC', bounds='TRIANGLE_MESH')

# ----------------------------------------------------------------- cordal (lomas del horizonte)
print("[CHARCO] cordal…")
bm = bmesh.new()
nseg = int(round(2 * CORDAL_HALF / CORDAL_CELL))
bmesh.ops.create_grid(bm, x_segments=nseg, y_segments=nseg, size=CORDAL_HALF)
inner = [f for f in bm.faces
         if all(abs(v.co.x) < MAP_HALF - 0.01 and abs(v.co.y) < MAP_HALF - 0.01 for v in f.verts)]
bmesh.ops.delete(bm, geom=inner, context='FACES')
for v in bm.verts:
    v.co.z = h_terr(v.co.x, v.co.y)
cordal = mesh_obj("Cordal", bm, M_CORDAL, smooth=True)
set_game(cordal, 'STATIC', bounds='TRIANGLE_MESH')

# ----------------------------------------------------------------- charco (espejo)
print("[CHARCO] agua…")
bm = bmesh.new()
segs = 192
ring = []
for i in range(segs):
    th = i / segs * 2 * math.pi
    rho = 1.10 / (1.0 + wobble(th))          # e_eff = 1,10: bajo tierra desde e ≈ 1,023
    ring.append(bm.verts.new((CHARCO_A * rho * math.cos(th), CHARCO_B * rho * math.sin(th), 0.0)))
bm.faces.new(ring)
bmesh.ops.triangulate(bm, faces=bm.faces[:])
agua = mesh_obj("Agua", bm, None, loc=(0, 0, Z_AGUA), smooth=True)
set_game(agua, 'NO_COLLISION')

# camino de losas: hacia +Y con 3 quiebros de ±15°, 90 m; el final es donde está la luz
PATH_LEGS = [(0.0, 24.0), (15.0, 30.0), (-10.0, 21.0), (8.0, 15.0)]
path_pts = [Vector((0.0, -40.0))]
for ang, L in PATH_LEGS:
    d = Vector((math.sin(math.radians(ang)), math.cos(math.radians(ang))))
    path_pts.append(path_pts[-1] + d * L)
LUZ = path_pts[-1] + Vector((2.0, 3.0))        # luz bajo el agua, al final del camino

# agua: Principled base oscura (0,012, 0,020, 0,030), roughness 0,03, IOR 1,333; el barro del
# fondo asoma a los pies (Fresnel bajo) y lejos manda el espejo; ondas sutiles por
# Noise→Bump (30 / 0,06 / 0,02: con 0,15 sale una columna de chispas, no un disco);
# la "luz bajo el agua" (Dive to the Heart) es emisión azul en el propio agua, porque el
# agua es opaca (sin transmisión: no cambiaba nada y costaba).
m_agua = bpy.data.materials.new("M_Agua")
m_agua.use_nodes = True
nt = m_agua.node_tree
b = nt.nodes["Principled BSDF"]
b.inputs["Roughness"].default_value = 0.03
b.inputs["Metallic"].default_value = 0.0
b.inputs["IOR"].default_value = 1.333
b.inputs["Specular IOR Level"].default_value = 1.0
b.inputs["Transmission Weight"].default_value = 0.0
tc = nt.nodes.new("ShaderNodeTexCoord")
vor = nt.nodes.new("ShaderNodeTexVoronoi"); vor.voronoi_dimensions = '2D'; vor.feature = 'DISTANCE_TO_EDGE'
vor.inputs["Scale"].default_value = 1.8; vor.inputs["Randomness"].default_value = 0.85
nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
crack = nt.nodes.new("ShaderNodeMapRange"); crack.inputs["From Min"].default_value = 0.012; crack.inputs["From Max"].default_value = 0.040
crack.inputs["To Min"].default_value = 0.45; crack.inputs["To Max"].default_value = 1.0; crack.clamp = True
nt.links.new(vor.outputs["Distance"], crack.inputs["Value"])
mud = nt.nodes.new("ShaderNodeRGB"); mud.outputs[0].default_value = (0.30, 0.22, 0.16, 1.0)
mmud = nt.nodes.new("ShaderNodeMix"); mmud.data_type = 'RGBA'; mmud.blend_type = 'MULTIPLY'; mmud.inputs["Factor"].default_value = 1.0
nt.links.new(mud.outputs[0], mmud.inputs["A"])
nt.links.new(crack.outputs["Result"], mmud.inputs["B"])
lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
fr = nt.nodes.new("ShaderNodeMapRange"); fr.inputs["From Min"].default_value = 0.15; fr.inputs["From Max"].default_value = 0.65; fr.clamp = True
nt.links.new(lw.outputs["Fresnel"], fr.inputs["Value"])
mix_f = nt.nodes.new("ShaderNodeMix"); mix_f.data_type = 'RGBA'; mix_f.inputs["B"].default_value = (0.012, 0.020, 0.030, 1.0)
nt.links.new(mmud.outputs["Result"], mix_f.inputs["A"])
nt.links.new(fr.outputs["Result"], mix_f.inputs["Factor"])
nt.links.new(mix_f.outputs["Result"], b.inputs["Base Color"])
nz = nt.nodes.new("ShaderNodeTexNoise")
nz.inputs["Scale"].default_value = 30.0; nz.inputs["Detail"].default_value = 5.0
nz.inputs["Roughness"].default_value = 0.55; nz.inputs["Distortion"].default_value = 0.4
bp = nt.nodes.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.06; bp.inputs["Distance"].default_value = 0.02
nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
nt.links.new(nz.outputs["Fac"], bp.inputs["Height"])
nt.links.new(bp.outputs["Normal"], b.inputs["Normal"])
# luz bajo el agua: disco r 6 m, (0,55, 0,80, 1,0) × 1,5, al final del camino
sub = nt.nodes.new("ShaderNodeVectorMath"); sub.operation = 'SUBTRACT'; sub.inputs[1].default_value = (LUZ.x, LUZ.y, 0.0)
ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = 'LENGTH'
fall = nt.nodes.new("ShaderNodeMapRange"); fall.inputs["From Max"].default_value = 6.0
fall.inputs["To Min"].default_value = 1.0; fall.inputs["To Max"].default_value = 0.0; fall.clamp = True
pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 2.0
lm = nt.nodes.new("ShaderNodeMath"); lm.operation = 'MULTIPLY'; lm.inputs[1].default_value = 1.5
nt.links.new(tc.outputs["Object"], sub.inputs[0])
nt.links.new(sub.outputs["Vector"], ln.inputs[0])
nt.links.new(ln.outputs["Value"], fall.inputs["Value"])
nt.links.new(fall.outputs["Result"], pw.inputs[0])
nt.links.new(pw.outputs["Value"], lm.inputs[0])
nt.links.new(lm.outputs["Value"], b.inputs["Emission Strength"])
b.inputs["Emission Color"].default_value = (0.55, 0.80, 1.0, 1.0)
m_agua.diffuse_color = (0.05, 0.07, 0.10, 1.0)
agua.data.materials.append(m_agua)

# ----------------------------------------------------------------- losas hundidas
print("[CHARCO] losas…")
L = K.Build()
losas_pts = []
for k in range(len(path_pts) - 1):
    a, bb = path_pts[k], path_pts[k + 1]
    seg_len = (bb - a).length
    n = int(seg_len / 1.6)
    for j in range(n):
        losas_pts.append(a + (bb - a) * (j / n))
for i, p in enumerate(losas_pts):
    sx = random.uniform(0.9, 1.3)
    sy = random.uniform(0.9, 1.3)
    top = random.uniform(0.03, 0.06)                 # sobresalen 3-6 cm del agua
    V, F = K.cbox(sx, sy, 0.24, ch=0.03)
    mtx = (Matrix.Translation((p.x + random.uniform(-0.15, 0.15), p.y + random.uniform(-0.15, 0.15), top - 0.12))
           @ Matrix.Rotation(random.uniform(0, math.pi), 4, 'Z')
           @ Matrix.Rotation(random.uniform(-0.035, 0.035), 4, 'X')
           @ Matrix.Rotation(random.uniform(-0.035, 0.035), 4, 'Y'))
    tono = random.uniform(0.85, 1.05)
    L.add(V, F, 0, mtx, tint=K.flat(tono))
losas = L.finish("Losas", [M_LOSA])
set_game(losas, 'STATIC', bounds='TRIANGLE_MESH')

# ----------------------------------------------------------------- rocas
print("[CHARCO] rocas…")
R = K.Build()


def shore_pt(phi, e=1.0):
    """Punto de la orilla en el acimut phi (0 = +Y, horario) a la coordenada elíptica e."""
    u, v = math.sin(phi), math.cos(phi)
    th = math.atan2(v, u)
    rho = e / (1.0 + wobble(th))
    return Vector((CHARCO_A * rho * u, CHARCO_B * rho * v))


roca_pts = [Vector((-6.0, -20.0)), Vector((4.0, -44.0)), Vector((-3.0, -52.0)), Vector((10.5, -36.0)),
            Vector((-14.0, -8.0))]
for phi_deg, e in ((150, 1.02), (170, 0.99), (215, 1.03), (240, 1.00), (265, 1.04), (300, 1.01),
                   (335, 1.02), (70, 1.03), (100, 1.00)):
    roca_pts.append(shore_pt(math.radians(phi_deg), e))
for i, p in enumerate(roca_pts):
    rr = random.uniform(0.45, 1.1)
    V, F = K.blob(rr, lumps=0.16, seed=i * 2.7, subdiv=2,
                  scale=(random.uniform(0.8, 1.3), random.uniform(0.8, 1.3), 0.55))
    z = h_terr(p.x, p.y) + rr * 0.20
    mtx = Matrix.Translation((p.x, p.y, z)) @ Matrix.Rotation(random.uniform(0, 6.28), 4, 'Z')
    tono = random.uniform(0.8, 1.05)
    R.add(V, F, 0, mtx, smooth=True, tint=K.flat(tono))
rocas = R.finish("Rocas", [M_ROCA])
set_game(rocas, 'STATIC', bounds='TRIANGLE_MESH')

# ----------------------------------------------------------------- juncos (carrizo)
# Phragmites: 2,2-2,8 m, panícula 25 cm gris-púrpura. Solo a sotavento (izquierda y
# detrás): NUNCA entre la cámara y el sol, que está delante a la derecha.
print("[CHARCO] juncos…")
junco_pts = [Vector((-12.0, -27.0)), Vector((-15.5, -36.0)), Vector((13.0, -46.0))]
for phi_deg, e in ((200, 1.0), (225, 0.98), (250, 1.01), (290, 0.99), (320, 1.0)):
    junco_pts.append(shore_pt(math.radians(phi_deg), e))
for gi, c in enumerate(junco_pts):
    J = K.Build()
    n = random.randint(12, 25)
    for k in range(n):
        a = random.uniform(0, 2 * math.pi)
        rad = random.uniform(0.0, 1.1) ** 0.5 * 1.1
        px, py = c.x + math.cos(a) * rad, c.y + math.sin(a) * rad
        z0 = min(h_terr(px, py), Z_AGUA - 0.01)
        h = random.uniform(2.2, 2.8)
        V, F = K.blade(h=h, w=0.022, lean=random.uniform(0.10, 0.30), segs=5)
        mtx = Matrix.Translation((px, py, z0)) @ Matrix.Rotation(random.uniform(0, 6.28), 4, 'Z')
        J.add(V, F, 0, mtx, tint=K.flat(random.uniform(0.75, 1.05)))
        # panícula: lenteja alargada en la punta, inclinada con el tallo
        tip = mtx @ Vector((0.0, 0.0, h))
        V, F = K.blob(0.06, lumps=0.25, seed=k * 1.3, subdiv=1, scale=(0.7, 0.7, 2.4))
        J.add(V, F, 1, Matrix.Translation(tip + Vector((0, 0, 0.10))), smooth=True,
              tint=K.flat(random.uniform(0.8, 1.0)))
    jun = J.finish(f"Juncos{gi + 1:02d}", [M_JUNCO, M_PANICULA])
    set_game(jun, 'NO_COLLISION')

# ----------------------------------------------------------------- motas de ánima
# Núcleo emisivo pequeño (fuerza 1,0) + halo aditivo esférico: Emission × (1−Facing)^1,6 +
# Transparent en Add Shader, BLENDED. Es el "bloom" a mano que el Player sí pinta y que
# no depende de la orientación (en gen_exp eran planos mirando a la cámara).
print("[CHARCO] motas…")
m_halo = bpy.data.materials.new("M_AnimaHalo")
m_halo.use_nodes = True
nt = m_halo.node_tree
for n_ in list(nt.nodes):
    nt.nodes.remove(n_)
out = nt.nodes.new("ShaderNodeOutputMaterial")
lw = nt.nodes.new("ShaderNodeLayerWeight"); lw.inputs["Blend"].default_value = 0.5
inv = nt.nodes.new("ShaderNodeMapRange"); inv.inputs["To Min"].default_value = 1.0; inv.inputs["To Max"].default_value = 0.0; inv.clamp = True
pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = 1.6
mul = nt.nodes.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = 2.5
em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (1.0, 0.70, 0.25, 1.0)
tr = nt.nodes.new("ShaderNodeBsdfTransparent")
add = nt.nodes.new("ShaderNodeAddShader")
nt.links.new(lw.outputs["Facing"], inv.inputs["Value"])
nt.links.new(inv.outputs["Result"], pw.inputs[0])
nt.links.new(pw.outputs["Value"], mul.inputs[0])
nt.links.new(mul.outputs["Value"], em.inputs["Strength"])
nt.links.new(em.outputs["Emission"], add.inputs[0])
nt.links.new(tr.outputs["BSDF"], add.inputs[1])
nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
m_halo.surface_render_method = 'BLENDED'
m_halo.blend_method = 'BLEND'
m_halo.use_backface_culling = True
m_halo.use_transparency_overlap = True
m_halo.use_transparent_shadow = False


def mota_cloud(name, cx, cy, rad, count, zmax, ring_r=None, amp=0.3, periodo=5.0, giro=3.0):
    B = K.Build()
    for _ in range(count):
        if ring_r is None:
            px, py = random.gauss(0, rad * 0.5), random.gauss(0, rad * 0.5)
        else:
            a = random.uniform(0, 2 * math.pi)
            rr = random.uniform(ring_r[0], ring_r[1])
            px, py = math.cos(a) * rr, math.sin(a) * rr
        pz = random.uniform(0.3, zmax)
        rc = random.uniform(0.026, 0.055)
        rh = random.uniform(0.16, 0.30)
        V, F = K.ico(0)
        B.add(V, F, 0, Matrix.Translation((px, py, pz)) @ Matrix.Scale(rc, 4), smooth=True, tint=K.flat(1.0))
        V, F = K.ico(1)
        B.add(V, F, 1, Matrix.Translation((px, py, pz)) @ Matrix.Scale(rh, 4), smooth=True, tint=K.flat(1.0))
    ob = B.finish(name, [M_ANIMA, m_halo])
    ob.location = (cx, cy, 0.0)
    ob.visible_shadow = False
    set_game(ob, 'NO_COLLISION', ghost=True)
    add_prop(ob, "fl_component", "Flotar")
    add_prop(ob, "fl_flotar_amp", float(amp))
    add_prop(ob, "fl_flotar_periodo", float(periodo))
    add_prop(ob, "fl_flotar_giro", float(giro))
    return ob


mota_cloud("AnimaMotas_Camino1", 3.0, -22.0, 9.0, 60, 3.5, amp=0.30, periodo=5.0, giro=3.0)
mota_cloud("AnimaMotas_Camino2", -6.0, -2.0, 10.0, 70, 4.0, amp=0.35, periodo=6.0, giro=2.5)
mota_cloud("AnimaMotas_Camino3", 8.0, 24.0, 12.0, 80, 4.0, amp=0.40, periodo=7.0, giro=2.0)
mota_cloud("AnimaMotas_Luz", LUZ.x, LUZ.y, 0.0, 40, 2.5, ring_r=(4.0, 7.0), amp=0.25, periodo=4.0, giro=5.0)
mota_cloud("AnimaMotas_Juncos", -13.0, -31.0, 5.0, 35, 3.0, amp=0.25, periodo=4.5, giro=4.0)
mota_cloud("AnimaMotas_Rocas", 25.0, -50.0, 7.0, 45, 3.0, amp=0.30, periodo=5.5, giro=3.5)
mota_cloud("AnimaMotas_Orilla1", -58.0, -42.0, 8.0, 50, 3.5, amp=0.35, periodo=6.5, giro=2.0)
mota_cloud("AnimaMotas_Orilla2", 40.0, -70.0, 8.0, 50, 3.5, amp=0.30, periodo=5.0, giro=3.0)
mota_cloud("AnimaMotas_Lejos", -30.0, 60.0, 12.0, 60, 4.5, amp=0.40, periodo=7.5, giro=2.0)

# ----------------------------------------------------------------- molinos (appendeados)
# Molino.blend no se modifica: se appendean Molino, Molino_Cubierta y Molino_Aspas una vez
# y los otros dos molinos son copias de objeto con la misma malla (30 k caras por molino).
print("[CHARCO] molinos…")
with bpy.data.libraries.load(MOLINO_BLEND, link=False) as (src, dst):
    dst.objects = [n for n in src.objects if n in ("Molino", "Molino_Cubierta", "Molino_Aspas")]
base = {}
for ob in dst.objects:
    if ob is not None:
        base[ob.name] = ob
assert set(base) == {"Molino", "Molino_Cubierta", "Molino_Aspas"}, base.keys()


def poner_molino(idx, az, dist):
    mx, my = dist * math.sin(az), dist * math.cos(az)
    mz = h_terr(mx, my) - 0.25
    if idx == 0:
        torre, cub, asp = base["Molino"], base["Molino_Cubierta"], base["Molino_Aspas"]
    else:
        torre, cub, asp = (base["Molino"].copy(), base["Molino_Cubierta"].copy(), base["Molino_Aspas"].copy())
    for ob in (torre, cub, asp):
        if ob.name not in bpy.context.collection.objects:
            bpy.context.collection.objects.link(ob)
        ob.animation_data_clear()
    torre.name = f"Molino{idx + 1:02d}"
    cub.name = f"Molino{idx + 1:02d}_Cubierta"
    asp.name = f"Molino{idx + 1:02d}_Aspas"
    torre.location = (mx, my, mz)
    torre.rotation_euler = (0.0, 0.0, -az)          # las aspas (cara −Y) miran al charco
    cub.parent = torre
    cub.matrix_parent_inverse = Matrix.Identity(4)
    cub.location = (0.0, 0.0, 0.0)
    cub.rotation_euler = (0.0, 0.0, 0.0)
    asp.parent = torre
    asp.matrix_parent_inverse = Matrix.Identity(4)
    asp.location = (0.0, -3.30, 9.72)                # el bocín, como en gen_molino
    asp.rotation_euler = (math.radians(80.0), 0.0, 0.0)
    set_game(torre, 'STATIC', bounds='TRIANGLE_MESH')
    set_game(cub, 'STATIC', bounds='TRIANGLE_MESH')
    set_game(asp, 'NO_COLLISION')
    add_prop(asp, "fl_component", "Girar")
    add_prop(asp, "fl_girar_eje", "Z")                # el eje del bocín es la Z local (gen_molino)
    add_prop(asp, "fl_girar_grados_s", 15.0)          # 2,5 rpm: lento, lejano, de ensueño
    return torre


for i, (az, dist) in enumerate(MOLINOS):
    poner_molino(i, az, dist)
# las cámaras/luces/otros de Molino.blend no se han traído; sus materiales sí (M_Cal…)

# ----------------------------------------------------------------- objetos de juego
print("[CHARCO] objetos de juego…")
# Player: malla SIN caras (no se dibuja) cuya caja da la cápsula r 0,35 × 1,75 (receta del
# carril RIG probada en el Player: un EMPTY no tiene bounds y el motor le pone extents
# 1,0 → esfera de 1 m, CcdPhysicsEnvironment.cpp:2987-3000). Origen en el centro.
pm = bpy.data.meshes.new("PlayerBounds")
pm.from_pydata([(x, y, z) for x in (-0.35, 0.35) for y in (-0.35, 0.35)
                for z in (-PLAYER_HALF_H, PLAYER_HALF_H)], [], [])
pm.update()
player = new_obj("Player", pm)
player.location = (PLAYER_START.x, PLAYER_START.y, Z_LECHO + PLAYER_HALF_H + 0.05)
g = player.game
g.physics_type = 'CHARACTER'
g.use_collision_bounds = True
g.collision_bounds_type = 'CAPSULE'
g.radius = 0.35
g.step_height = 0.4
g.jump_speed = 6.0
g.fall_speed = 55.0
add_prop(player, "fl_component", "PlayerController")

# cápsula visible provisional (hijo, sin colisión), con una "nariz" en +Y: el
# PlayerController alinea la Y local con la dirección de marcha
C = K.Build()
prof = [(0.0, -PLAYER_HALF_H), (0.20, -0.83), (0.30, -0.70), (0.35, -0.525), (0.35, 0.525),
        (0.30, 0.70), (0.20, 0.83), (0.0, PLAYER_HALF_H)]
V, F = K.lathe(prof, segs=24)
C.add(V, F, 0, smooth=True, tint=K.flat(1.0))
V, F = K.cbox(0.12, 0.16, 0.10, ch=0.02)
C.add(V, F, 1, Matrix.Translation((0.0, 0.38, 0.30)), tint=K.flat(1.0))
capsula = C.finish("Player_Capsula", [K.make_mat("M_HeroeCol", (0.20, 0.30, 0.55), rough=0.7),
                                      K.make_mat("M_PielCol", (0.85, 0.66, 0.50), rough=0.85)])
capsula.parent = player
capsula.matrix_parent_inverse = Matrix.Identity(4)
capsula.location = (0.0, 0.0, 0.0)
set_game(capsula, 'NO_COLLISION')

# GameCamera. Lente 24 mm (VFOV 50,2° a 16:10). La visión pedía 28 mm con la cámara a
# 7 m / 2,6 m / pitch −5°, pero el ThirdPersonCamera de hoy arranca con pitch +18° fijo
# (m_pitch = 0,31416) y mira 21-24° hacia abajo: con 28 mm el horizonte se sale por
# arriba del encuadre y no se ve el sol. Con 24 mm y fl_cam_altura 1,2 el horizonte queda
# al 9 % del alto, el reflejo del sol al 19 % y el personaje del 50 al 74 %; cuando CPP
# lea fl_cam_pitch (−5°), 24 mm da horizonte 40 % y personaje 54-81 %: a 3 puntos de la
# visión. La pose guardada es la que el componente C++ produce en el arranque.
cam_data = bpy.data.cameras.new("GameCamera")
cam_data.lens = CAM_LENS
cam_data.sensor_width = 36.0
cam_data.clip_start = 0.1
cam_data.clip_end = 800.0
cam = new_obj("GameCamera", cam_data)
p0 = Vector((PLAYER_START.x, PLAYER_START.y, Z_LECHO + PLAYER_HALF_H))
cpp_pitch = 0.31416
cam.location = p0 + Vector((0.0, -CAM_DIST * math.cos(cpp_pitch), CAM_ALTURA + CAM_DIST * math.sin(cpp_pitch)))
aim(cam, (p0 + Vector((0, 0, CAM_ALTURA * 0.7))) - cam.location)
set_game(cam, 'NO_COLLISION')
add_prop(cam, "fl_component", "ThirdPersonCamera")
add_prop(cam, "fl_cam_dist", CAM_DIST)
add_prop(cam, "fl_cam_altura", CAM_ALTURA)
add_prop(cam, "fl_cam_pitch", -5.0)     # aún no lo lee el motor: petición al carril CPP
sc.camera = cam

# cámara de la visión (no activa): 7 m detrás, 2,6 m, pitch −5°. Para renders de comprobación.
cv_data = bpy.data.cameras.new("CamVision")
cv_data.lens = CAM_LENS
cv_data.clip_end = 800.0
cv = new_obj("CamVision", cv_data)
cv.location = (PLAYER_START.x, PLAYER_START.y - 7.0, 2.6)
cv.rotation_euler = (math.radians(85.0), 0.0, 0.0)
set_game(cv, 'NO_COLLISION')

# Pesadillas provisionales (diseño de enemigos SIN decidir): 3 a 8-15 m, ojos en +Y
# porque el EnemyAI alinea la Y local hacia el jugador
for i, (px, py) in enumerate(((-3.0, -19.5), (5.5, -17.0), (-9.0, -25.5))):
    P = K.Build()
    V, F = K.blob(0.7, lumps=0.15, seed=11.0 + i, subdiv=2, scale=(1.0, 1.0, 1.3))
    P.add(V, F, 0, smooth=True, tint=K.flat(1.0))
    for k in (-1, 1):
        V, F = K.ico(1)
        P.add(V, F, 1, Matrix.Translation((0.18 * k, 0.60, 0.40)) @ Matrix.Scale(0.07, 4),
              smooth=True, tint=K.flat(1.0))
    pes = P.finish(f"Pesadilla{i + 1:02d}", [K.make_mat("M_PesadillaCol", (0.05, 0.045, 0.08), rough=0.98),
                                             K.make_mat("M_PesadillaOjoCol", (0.75, 0.60, 0.95), rough=0.5,
                                                        emit=(0.70, 0.55, 0.95), emit_str=3.0)])
    pes.location = (px, py, Z_AGUA + 0.9)
    set_game(pes, 'STATIC')
    add_prop(pes, "fl_component", "EnemyAI")
    d = (Vector((PLAYER_START.x, PLAYER_START.y)) - Vector((px, py)))
    pes.rotation_euler = (0.0, 0.0, math.atan2(-d.x, d.y))

# ----------------------------------------------------------------- cielo y luz
print("[CHARCO] cielo y luz…")
world = bpy.data.worlds.new("W_Charco")
sc.world = world
world.use_nodes = True
wnt = world.node_tree
for n_ in list(wnt.nodes):
    wnt.nodes.remove(n_)
wout = wnt.nodes.new("ShaderNodeOutputWorld")
bg = wnt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.0
tc = wnt.nodes.new("ShaderNodeTexCoord")
sep = wnt.nodes.new("ShaderNodeSeparateXYZ")
elev = wnt.nodes.new("ShaderNodeMapRange")
elev.inputs["From Min"].default_value = -0.15
elev.inputs["From Max"].default_value = 0.6
wnt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
wnt.links.new(sep.outputs["Z"], elev.inputs["Value"])
# lado del sol: la rampa de gen_t1 (naranja → dorado → magenta → azul-violeta)
r_sol = wnt.nodes.new("ShaderNodeValToRGB")
ramp(r_sol.color_ramp, [(0.0, (0.98, 0.42, 0.10)), (0.16, (0.98, 0.63, 0.22)),
                        (0.42, (0.72, 0.45, 0.42)), (1.0, (0.20, 0.23, 0.42))])
# lado antisolar: sombra de la Tierra gris-azul abajo, Cinturón de Venus rosa a 10-20°
r_anti = wnt.nodes.new("ShaderNodeValToRGB")
ramp(r_anti.color_ramp, [(0.0, (0.55, 0.50, 0.62)), (0.14, (0.80, 0.52, 0.60)),
                         (0.34, (0.60, 0.44, 0.55)), (1.0, (0.20, 0.23, 0.42))])
wnt.links.new(elev.outputs["Result"], r_sol.inputs["Fac"])
wnt.links.new(elev.outputs["Result"], r_anti.inputs["Fac"])
dot_h = wnt.nodes.new("ShaderNodeVectorMath"); dot_h.operation = 'DOT_PRODUCT'
dot_h.inputs[1].default_value = tuple(S_FLAT)
azf = wnt.nodes.new("ShaderNodeMapRange"); azf.inputs["From Min"].default_value = -0.7; azf.inputs["From Max"].default_value = 0.7; azf.clamp = True
mix_az = wnt.nodes.new("ShaderNodeMix"); mix_az.data_type = 'RGBA'
wnt.links.new(tc.outputs["Generated"], dot_h.inputs[0])
wnt.links.new(dot_h.outputs["Value"], azf.inputs["Value"])
wnt.links.new(r_anti.outputs["Color"], mix_az.inputs["A"])
wnt.links.new(r_sol.outputs["Color"], mix_az.inputs["B"])
wnt.links.new(azf.outputs["Result"], mix_az.inputs["Factor"])
# resplandor concentrado alrededor del sol, solo cerca del horizonte (gen_molino)
dot_s = wnt.nodes.new("ShaderNodeVectorMath"); dot_s.operation = 'DOT_PRODUCT'
dot_s.inputs[1].default_value = tuple(S_DIR)
gl = wnt.nodes.new("ShaderNodeMapRange"); gl.inputs["From Min"].default_value = 0.55; gl.inputs["From Max"].default_value = 0.995; gl.clamp = True
hz = wnt.nodes.new("ShaderNodeMapRange"); hz.inputs["From Min"].default_value = 0.34; hz.inputs["From Max"].default_value = 0.0; hz.clamp = True
gmul = wnt.nodes.new("ShaderNodeMath"); gmul.operation = 'MULTIPLY'
mix_g = wnt.nodes.new("ShaderNodeMix"); mix_g.data_type = 'RGBA'; mix_g.inputs["B"].default_value = (0.98, 0.72, 0.34, 1.0)
wnt.links.new(tc.outputs["Generated"], dot_s.inputs[0])
wnt.links.new(dot_s.outputs["Value"], gl.inputs["Value"])
wnt.links.new(sep.outputs["Z"], hz.inputs["Value"])
wnt.links.new(gl.outputs["Result"], gmul.inputs[0])
wnt.links.new(hz.outputs["Result"], gmul.inputs[1])
wnt.links.new(mix_az.outputs["Result"], mix_g.inputs["A"])
wnt.links.new(gmul.outputs["Value"], mix_g.inputs["Factor"])
wnt.links.new(mix_g.outputs["Result"], bg.inputs["Color"])
wnt.links.new(bg.outputs["Background"], wout.inputs["Surface"])
world.sun_threshold = 0.0

sun_d = bpy.data.lights.new("Sol", 'SUN')
sun_d.energy = 4.2
sun_d.color = (1.0, 0.70, 0.42)
sun_d.angle = math.radians(4.0)          # el brillo especular en el agua sale del tamaño del disco
sun_d.shadow_maximum_resolution = 0.001
sun_d.shadow_filter_radius = 1.0
sun_d.use_shadow_jitter = False           # el Player no acumula muestras: el jitter parpadearía
sol = new_obj("Sol", sun_d)
aim(sol, -S_DIR)
set_game(sol, 'NO_COLLISION')

fill_d = bpy.data.lights.new("Relleno", 'SUN')
fill_d.energy = 0.5
fill_d.color = (0.55, 0.62, 0.90)
fill_d.use_shadow = False
relleno = new_obj("Relleno", fill_d)
F_DIR = Vector((-S_DIR.x, -S_DIR.y, 0.9)).normalized()
aim(relleno, -F_DIR)
set_game(relleno, 'NO_COLLISION')

# disco solar (emisión 1,0: en pantalla ya es blanco y la captura del Player no lo envuelve)
M_SOLDISCO = mat_pbr("M_SolDisco", (0.0, 0.0, 0.0), 0.9, emit=(1.0, 0.93, 0.80), emit_strength=1.0)
bm = bmesh.new()
bmesh.ops.create_circle(bm, cap_ends=True, segments=40, radius=DISCO_R)
disco = mesh_obj("SolDisco", bm, M_SOLDISCO, loc=S_DIR * DISCO_DIST)
disco.rotation_euler = S_DIR.to_track_quat('Z', 'Y').to_euler()
disco.visible_shadow = False
set_game(disco, 'NO_COLLISION')


def mat_glow(name, color, fuerza, pot=2.0):
    """Plano aditivo con caída radial (coordenadas Object): el halo del sol."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n_ in list(nt.nodes):
        nt.nodes.remove(n_)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ln = nt.nodes.new("ShaderNodeVectorMath"); ln.operation = 'LENGTH'
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 1.0; mr.inputs["To Max"].default_value = 0.0; mr.clamp = True
    pw = nt.nodes.new("ShaderNodeMath"); pw.operation = 'POWER'; pw.inputs[1].default_value = pot
    mul = nt.nodes.new("ShaderNodeMath"); mul.operation = 'MULTIPLY'; mul.inputs[1].default_value = fuerza
    em = nt.nodes.new("ShaderNodeEmission"); em.inputs["Color"].default_value = (*color, 1.0)
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    add = nt.nodes.new("ShaderNodeAddShader")
    nt.links.new(tc.outputs["Object"], ln.inputs[0])
    nt.links.new(ln.outputs["Value"], mr.inputs["Value"])
    nt.links.new(mr.outputs["Result"], pw.inputs[0])
    nt.links.new(pw.outputs["Value"], mul.inputs[0])
    nt.links.new(mul.outputs["Value"], em.inputs["Strength"])
    nt.links.new(em.outputs["Emission"], add.inputs[0])
    nt.links.new(tr.outputs["BSDF"], add.inputs[1])
    nt.links.new(add.outputs["Shader"], out.inputs["Surface"])
    m.surface_render_method = 'BLENDED'
    m.blend_method = 'BLEND'
    m.use_backface_culling = False
    m.use_transparency_overlap = True
    m.use_transparent_shadow = False
    return m


def plano_glow(name, mat, pos, radio, hacia):
    bm = bmesh.new()
    bmesh.ops.create_circle(bm, cap_ends=True, segments=32, radius=1.0)
    ob = mesh_obj(name, bm, mat, loc=pos)
    ob.scale = (radio, radio, radio)
    ob.rotation_euler = Vector(hacia).to_track_quat('Z', 'Y').to_euler()
    ob.visible_shadow = False
    set_game(ob, 'NO_COLLISION', ghost=True)
    return ob


plano_glow("SolHalo1", mat_glow("M_SolHalo1", (1.0, 0.62, 0.30), 6.0, pot=2.5), S_DIR * (DISCO_DIST - 5.0), 40.0, -S_DIR)
plano_glow("SolHalo2", mat_glow("M_SolHalo2", (1.0, 0.50, 0.22), 1.6, pot=1.6), S_DIR * (DISCO_DIST - 10.0), 110.0, -S_DIR)

# caja de niebla: capa de calima de 0 a 23 m sobre todo el mapa (el volumen del MUNDO sale
# negro en este build; la caja sí se pinta en el Player). A 300 m (molinos) transmite
# exp(−0,0025·300) = 47 %: siluetas; el cénit apenas se vela.
m_n = bpy.data.materials.new("M_Niebla")
m_n.use_nodes = True
mtn = m_n.node_tree
for n_ in list(mtn.nodes):
    mtn.nodes.remove(n_)
o_ = mtn.nodes.new("ShaderNodeOutputMaterial")
p_ = mtn.nodes.new("ShaderNodeVolumePrincipled")
p_.inputs["Density"].default_value = 0.0025
p_.inputs["Anisotropy"].default_value = 0.3
p_.inputs["Color"].default_value = (0.95, 0.80, 0.66, 1.0)
mtn.links.new(p_.outputs["Volume"], o_.inputs["Volume"])
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
bmesh.ops.scale(bm, vec=(2 * CORDAL_HALF, 2 * CORDAL_HALF, 24.0), verts=bm.verts)
niebla = mesh_obj("Niebla", bm, m_n, loc=(0, 0, 11.0))
niebla.visible_shadow = False
set_game(niebla, 'NO_COLLISION', ghost=True)

# ----------------------------------------------------------------- ajustes de render y juego
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.render.resolution_x = 1280
sc.render.resolution_y = 800
sc.render.resolution_percentage = 100
sc.render.fps = 30                                   # convención de ÁNIMA (acciones a 30 fps)
sc.view_settings.view_transform = 'Standard'         # AgX lava los planos saturados (ficha 11)
sc.view_settings.look = 'None'
sc.render.dither_intensity = 0.0                     # sin dither: la captura del Player envuelve >1,0
sc.eevee.taa_samples = 16
sc.eevee.taa_render_samples = 32
sc.eevee.use_shadows = True
sc.eevee.shadow_pool_size = '512'
sc.eevee.use_fast_gi = True
sc.eevee.use_raytracing = True                       # SSR: el espejo. SIN sonda planar.
sc.eevee.ray_tracing_method = 'SCREEN'
ro = sc.eevee.ray_tracing_options
ro.resolution_scale = '2'
ro.screen_trace_quality = 0.25
ro.screen_trace_thickness = 0.2
ro.trace_max_roughness = 0.5
ro.use_denoise = True
sc.eevee.volumetric_start = 1.0
sc.eevee.volumetric_end = 500.0                      # la caja llega a 480 m desde el arranque
sc.eevee.volumetric_tile_size = '8'
sc.eevee.volumetric_samples = 64
sc.eevee.use_volumetric_shadows = False

gs = sc.game_settings
gs.resolution_x, gs.resolution_y = 1280, 800
gs.fps = 60
gs.physics_engine = 'BULLET'
gs.physics_gravity = 9.8
gs.samples = 'SAMPLES_0'
gs.samp_per_frame = 1
gs.vsync = 'ON'
gs.use_frame_rate = True

# El Player toma el sombreado del visor 3D guardado (SOLID → OB_RENDER con mundo y luces
# de la escena) y solo respeta scene.camera si el visor está EN VISTA DE CÁMARA
# (BL_DataConversion.cpp:1416, persp == RV3D_CAMOB). Aquí además la activa el componente.
n_vis = 0
for scr in bpy.data.screens:
    for a in scr.areas:
        if a.type == 'VIEW_3D':
            for s in a.spaces:
                if s.type == 'VIEW_3D':
                    s.shading.type = 'SOLID'
                    s.shading.use_scene_world_render = True
                    s.shading.use_scene_lights_render = True
                    s.camera = cam
                    s.region_3d.view_perspective = 'CAMERA'
                    n_vis += 1

# ----------------------------------------------------------------- guardar
assert len(bpy.data.texts) == 0, "el .blend no puede llevar Python"
for ob in bpy.data.objects:
    assert len(ob.game.sensors) == 0 and len(ob.game.controllers) == 0 and len(ob.game.actuators) == 0, ob.name
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
n_faces = sum(len(o.data.polygons) for o in bpy.data.objects if o.type == 'MESH')
print(f"[CHARCO] guardado: {OUT_BLEND}")
print(f"[CHARCO] objetos: {len(bpy.data.objects)}  caras: {n_faces}  visores en cámara: {n_vis}")
print(f"[CHARCO] sol: elev 5° az 12°  disco {DISCO_R} m a {DISCO_DIST} m  luz bajo el agua en "
      f"({LUZ.x:.1f}, {LUZ.y:.1f})  fin del camino ({path_pts[-1].x:.1f}, {path_pts[-1].y:.1f})")
print("[CHARCO] OK")
