# ÁNIMA — Terreno 1: La Mancha (v2, detalle estilo KH)
# Generador del mapa (herramienta de construcción; se ejecuta en el EDITOR de
# Flipendo con --background). El .blend resultante NO contiene Python:
# ni text blocks, ni logic bricks, ni controladores. El gameplay se ata con
# la propiedad de juego fl_component (componentes nativos C++).
#
# Uso:
#   Flipendo --background --factory-startup --python gen_t1_lamancha.py
#
# Salida: ~/Flipendo/game/anima/T1_LaMancha.blend

import bpy
import bmesh
import math
import os
import random
from mathutils import Vector, Matrix, Euler, noise

random.seed(1605)  # deterministo (1605: año del Quijote)

OUT_DIR = os.path.expanduser("~/Flipendo/game/anima")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_BLEND = os.path.join(OUT_DIR, "T1_LaMancha.blend")

# ----------------------------------------------------------------- constantes
MAP_SIZE = 300.0
GRID_N = 200
VILLAGE = Vector((-65.0, -45.0))
PLAZA = Vector((-65.0, -45.0))
HILL = Vector((80.0, 58.0))
HILL_H = 9.0
HILL_SIGMA = 26.0

PATH_PTS = [Vector((-65.0, -45.0)), Vector((-46.0, -40.0)), Vector((-24.0, -44.0)),
            Vector((8.0, -30.0)), Vector((34.0, -4.0)), Vector((52.0, 24.0)),
            Vector((72.0, 46.0))]
PATH_W = 4.5

# arroyo seco (segmento A0-A1), cruza el camino entre el pueblo y la colina
A0 = Vector((-30.0, 45.0))
A1 = Vector((75.0, -75.0))

FIELD_ANG = math.radians(25.0)   # orientación de las franjas de cultivo
FIELD_W = 20.0

# ----------------------------------------------------------------- utilidades


def clamp(v, a, b):
    return max(a, min(b, v))


def smoothstep(t):
    t = clamp(t, 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def frac_hash(i):
    return (math.sin(i * 12.9898) * 43758.5453) % 1.0


def n2(x, y, s):
    return noise.noise(Vector((x * s, y * s, 7.7)))


def path_samples(n=180):
    pts = []
    total = len(PATH_PTS) - 1
    for i in range(n + 1):
        t = i / n * total
        k = min(int(t), total - 1)
        f = t - k
        p0 = PATH_PTS[max(k - 1, 0)]
        p1 = PATH_PTS[k]
        p2 = PATH_PTS[min(k + 1, total)]
        p3 = PATH_PTS[min(k + 2, total)]
        a = p1 * 2.0
        b = p2 - p0
        c = p0 * 2.0 - p1 * 5.0 + p2 * 4.0 - p3
        d = -p0 + p1 * 3.0 - p2 * 3.0 + p3
        pts.append((a + b * f + c * f * f + d * f * f * f) * 0.5)
    return pts


PATH = path_samples()


def path_dist(x, y):
    p = Vector((x, y))
    best = 1e9
    for q in PATH:
        d = (p - q).length_squared
        if d < best:
            best = d
    return math.sqrt(best)


def seg_dist(p, a, b):
    ab = b - a
    t = clamp((p - a).dot(ab) / ab.length_squared, 0.0, 1.0)
    return (p - (a + ab * t)).length


def arroyo_dist(x, y):
    return seg_dist(Vector((x, y)), A0, A1)


def field_tone(x, y):
    v = -x * math.sin(FIELD_ANG) + y * math.cos(FIELD_ANG)
    return frac_hash(math.floor(v / FIELD_W)), v


def terrain_h(x, y):
    h = 2.2 * n2(x, y, 0.012) + 0.7 * n2(x, y, 0.045) + 0.25 * n2(x, y, 0.12)
    dh = (Vector((x, y)) - HILL).length
    h += HILL_H * math.exp(-(dh * dh) / (2.0 * HILL_SIGMA * HILL_SIGMA))
    dv = (Vector((x, y)) - VILLAGE).length
    fv = math.exp(-(dv * dv) / (2.0 * 35.0 * 35.0))
    h *= (1.0 - 0.85 * fv)
    # plaza muy plana
    pm = smoothstep(1.0 - dv / 18.0)
    h = h * (1.0 - pm) + 0.15 * pm
    # lomas del horizonte
    r = math.hypot(x, y)
    rim = clamp((r - 115.0) / 45.0, 0.0, 1.0) ** 1.6
    h += 8.0 * rim * (0.6 + 0.4 * n2(x, y, 0.02))
    # camino: suavizar rugosidad
    pd = path_dist(x, y)
    pmask = smoothstep(1.0 - pd / (PATH_W * 1.6))
    h -= (0.7 * n2(x, y, 0.045) + 0.25 * n2(x, y, 0.12)) * 0.8 * pmask
    # arroyo seco
    ad = arroyo_dist(x, y)
    h -= 1.5 * smoothstep(1.0 - ad / 5.5)
    # surcos de arada en franjas de cultivo
    tone, v = field_tone(x, y)
    if tone > 0.66:
        w = 1.0
        w *= 1.0 - fv
        w *= 1.0 - smoothstep(1.0 - pd / (PATH_W * 2.0))
        w *= 1.0 - smoothstep(1.0 - ad / 8.0)
        w *= 1.0 - rim
        h += 0.055 * w * math.sin(v * 4.5)
    return h


def new_obj(name, me):
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def mat_simple(name, color, rough=0.85, emit=None, emit_strength=0.0):
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_strength
    m.diffuse_color = (*color, 1.0)
    return m


def set_game(ob, physics='STATIC', bounds=None, ghost=False, radius=1.0):
    g = ob.game
    g.physics_type = physics
    g.use_ghost = ghost
    g.radius = radius
    if bounds:
        g.use_collision_bounds = True
        g.collision_bounds_type = bounds


def add_prop(ob, name, value):
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.game_property_new(type='STRING', name=name)
    ob.game.properties[name].value = value
    ob.select_set(False)


def box(name, size, loc, mat, rot=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=size, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = new_obj(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    me.materials.append(mat)
    return ob


def cyl(name, r, h, loc, mat, segs=16, r2=None, rot=(0, 0, 0), smooth=False):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs,
                          radius1=r, radius2=(r2 if r2 is not None else r), depth=h)
    bm.to_mesh(me)
    bm.free()
    ob = new_obj(name, me)
    ob.location = loc
    ob.rotation_euler = rot
    me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def cone(name, r, h, loc, mat, segs=16, rot=(0, 0, 0)):
    return cyl(name, r, h, loc, mat, segs=segs, r2=0.02, rot=rot)


def ico(name, r, loc, mat, subdiv=1, scale=(1, 1, 1), smooth=True):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_icosphere(bm, subdivisions=subdiv, radius=r)
    bmesh.ops.scale(bm, vec=scale, verts=bm.verts)
    bm.to_mesh(me)
    bm.free()
    ob = new_obj(name, me)
    ob.location = loc
    me.materials.append(mat)
    if smooth:
        for p in me.polygons:
            p.use_smooth = True
    return ob


def prism(name, w, d, h, loc, mat, rot_z=0.0, overhang=0.25):
    """Tejado a dos aguas: caballete a lo largo del eje X local."""
    me = bpy.data.meshes.new(name)
    hw, hd = w / 2 + overhang, d / 2 + overhang
    verts = [(-hw, -hd, 0), (hw, -hd, 0), (hw, hd, 0), (-hw, hd, 0),
             (-hw, 0, h), (hw, 0, h)]
    faces = [(0, 1, 5, 4), (2, 3, 4, 5), (0, 4, 3), (1, 2, 5), (0, 3, 2, 1)]
    me.from_pydata(verts, [], faces)
    ob = new_obj(name, me)
    ob.location = loc
    ob.rotation_euler = (0, 0, rot_z)
    me.materials.append(mat)
    return ob


def join(parts, name):
    bpy.ops.object.select_all(action='DESELECT')
    for o in parts:
        o.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    parts[0].name = name
    return parts[0]


# ----------------------------------------------------------------- limpiar
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

sc = bpy.context.scene
sc.name = "T1_LaMancha"

# ----------------------------------------------------------------- materiales
M_CAL = mat_simple("M_Cal", (0.93, 0.90, 0.82), 0.9)
M_TEJA = mat_simple("M_Teja", (0.60, 0.28, 0.15), 0.9)
M_TECHO = mat_simple("M_TechoPizarra", (0.16, 0.19, 0.30), 0.85)
M_MADERA = mat_simple("M_Madera", (0.30, 0.19, 0.10), 0.85)
M_MADERA_OSC = mat_simple("M_MaderaOscura", (0.15, 0.10, 0.06), 0.85)
M_VIGA = mat_simple("M_Viga", (0.22, 0.14, 0.08), 0.85)
M_LONA = mat_simple("M_Lona", (0.90, 0.85, 0.72), 0.8)
M_PIEDRA = mat_simple("M_Piedra", (0.54, 0.50, 0.44), 0.95)
M_PIEDRA_OSC = mat_simple("M_PiedraOscura", (0.38, 0.35, 0.31), 0.95)
M_HIERRO = mat_simple("M_Hierro", (0.10, 0.10, 0.12), 0.6)
M_OLIVO_T = mat_simple("M_OlivoTronco", (0.32, 0.25, 0.16), 0.9)
M_OLIVO_C = mat_simple("M_OlivoCopa", (0.36, 0.44, 0.24), 0.9)
M_CIPRES = mat_simple("M_Cipres", (0.14, 0.24, 0.15), 0.9)
M_VID = mat_simple("M_Vid", (0.30, 0.42, 0.18), 0.9)
M_MATORRAL = mat_simple("M_Matorral", (0.42, 0.40, 0.20), 0.95)
M_HIERBA = mat_simple("M_Hierba", (0.50, 0.45, 0.19), 0.95)
M_AMAPOLA = mat_simple("M_Amapola", (0.75, 0.10, 0.08), 0.8)
M_PAJA = mat_simple("M_Paja", (0.80, 0.63, 0.28), 0.95)
M_NUBE = mat_simple("M_Nube", (0.96, 0.90, 0.86), 0.9,
                    emit=(1.0, 0.82, 0.70), emit_strength=1.2)
M_SOLGLOW = mat_simple("M_SolGlow", (1.0, 0.6, 0.25), 0.9,
                       emit=(1.0, 0.55, 0.20), emit_strength=7.0)
M_FAROL = mat_simple("M_FarolLuz", (1.0, 0.75, 0.35), 0.5,
                     emit=(1.0, 0.66, 0.25), emit_strength=9.0)
M_VENTANA_LUZ = mat_simple("M_VentanaLuz", (1.0, 0.72, 0.32), 0.5,
                           emit=(1.0, 0.60, 0.22), emit_strength=2.2)
M_ANIMA = mat_simple("M_Anima", (1.0, 0.78, 0.30), 0.4,
                     emit=(1.0, 0.72, 0.22), emit_strength=2.8)
M_PESADILLA = mat_simple("M_Pesadilla", (0.05, 0.045, 0.08), 0.98)
M_PESADILLA_OJO = mat_simple("M_PesadillaOjo", (0.75, 0.60, 0.95), 0.5,
                             emit=(0.70, 0.55, 0.95), emit_strength=3.0)
M_HEROE = mat_simple("M_Heroe", (0.20, 0.30, 0.55), 0.8)
M_PIEL = mat_simple("M_Piel", (0.85, 0.66, 0.50), 0.85)

# ----------------------------------------------------------------- terreno
print("[T1] terreno…")
me = bpy.data.meshes.new("Terreno")
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=GRID_N, y_segments=GRID_N, size=MAP_SIZE / 2.0)
bm.to_mesh(me)
bm.free()
terreno = new_obj("Terreno", me)

a_path = me.color_attributes.new(name="PathMask", type='FLOAT_COLOR', domain='POINT')
a_plaza = me.color_attributes.new(name="PlazaMask", type='FLOAT_COLOR', domain='POINT')
a_field = me.color_attributes.new(name="FieldTone", type='FLOAT_COLOR', domain='POINT')
for i, v in enumerate(me.vertices):
    x, y = v.co.x, v.co.y
    v.co.z = terrain_h(x, y)
    pd = path_dist(x, y)
    pm = smoothstep(1.0 - pd / PATH_W) * (0.75 + 0.25 * n2(x, y, 0.3))
    a_path.data[i].color = (pm, pm, pm, 1.0)
    dv = (Vector((x, y)) - VILLAGE).length
    zm = smoothstep(1.0 - dv / 16.0)
    a_plaza.data[i].color = (zm, zm, zm, 1.0)
    # tono de franja de cultivo, desvanecido en pueblo/colina/borde/arroyo
    tone, _ = field_tone(x, y)
    w = 1.0
    w *= 1.0 - math.exp(-(dv * dv) / (2.0 * 45.0 * 45.0))
    dh_ = (Vector((x, y)) - HILL).length
    w *= 1.0 - math.exp(-(dh_ * dh_) / (2.0 * 30.0 * 30.0))
    w *= 1.0 - clamp((math.hypot(x, y) - 115.0) / 45.0, 0.0, 1.0)
    w *= 1.0 - smoothstep(1.0 - arroyo_dist(x, y) / 8.0)
    ft = 0.5 + (tone - 0.5) * w
    a_field.data[i].color = (ft, ft, ft, 1.0)
for p in me.polygons:
    p.use_smooth = True

# material del terreno: franjas trigo/rastrojo/arada + camino + empedrado
mt = bpy.data.materials.new("M_Terreno")
mt.use_nodes = True
nt = mt.node_tree
bsdf = nt.nodes.get("Principled BSDF")
bsdf.inputs["Roughness"].default_value = 0.95

af = nt.nodes.new("ShaderNodeAttribute")
af.attribute_name = "FieldTone"
framp = nt.nodes.new("ShaderNodeValToRGB")
framp.color_ramp.elements[0].position = 0.15
framp.color_ramp.elements[0].color = (0.78, 0.56, 0.20, 1.0)   # trigo
fm = framp.color_ramp.elements.new(0.5)
fm.color = (0.55, 0.46, 0.18, 1.0)                             # rastrojo
framp.color_ramp.elements[-1].position = 0.85
framp.color_ramp.elements[-1].color = (0.46, 0.30, 0.17, 1.0)  # arada

tex = nt.nodes.new("ShaderNodeTexNoise")
tex.inputs["Scale"].default_value = 0.05
tex.inputs["Detail"].default_value = 5.0
vr = nt.nodes.new("ShaderNodeMapRange")
vr.inputs["From Min"].default_value = 0.0
vr.inputs["From Max"].default_value = 1.0
vr.inputs["To Min"].default_value = 0.85
vr.inputs["To Max"].default_value = 1.12
mvar = nt.nodes.new("ShaderNodeMix")
mvar.data_type = 'RGBA'
mvar.blend_type = 'MULTIPLY'
mvar.inputs["Factor"].default_value = 1.0

ap = nt.nodes.new("ShaderNodeAttribute")
ap.attribute_name = "PathMask"
mixp = nt.nodes.new("ShaderNodeMix")
mixp.data_type = 'RGBA'
mixp.inputs["B"].default_value = (0.46, 0.31, 0.18, 1.0)       # tierra

az = nt.nodes.new("ShaderNodeAttribute")
az.attribute_name = "PlazaMask"
vor = nt.nodes.new("ShaderNodeTexVoronoi")
vor.inputs["Scale"].default_value = 220.0
cramp = nt.nodes.new("ShaderNodeValToRGB")
cramp.color_ramp.elements[0].position = 0.15
cramp.color_ramp.elements[0].color = (0.60, 0.55, 0.48, 1.0)   # sillar claro
cramp.color_ramp.elements[1].position = 0.85
cramp.color_ramp.elements[1].color = (0.44, 0.40, 0.35, 1.0)   # sillar oscuro
mixz = nt.nodes.new("ShaderNodeMix")
mixz.data_type = 'RGBA'

nt.links.new(af.outputs["Fac"], framp.inputs["Fac"])
nt.links.new(tex.outputs["Fac"], vr.inputs["Value"])
nt.links.new(framp.outputs["Color"], mvar.inputs["A"])
nt.links.new(vr.outputs["Result"], mvar.inputs["B"])
nt.links.new(mvar.outputs["Result"], mixp.inputs["A"])
nt.links.new(ap.outputs["Fac"], mixp.inputs["Factor"])
nt.links.new(vor.outputs["Distance"], cramp.inputs["Fac"])
nt.links.new(mixp.outputs["Result"], mixz.inputs["A"])
nt.links.new(cramp.outputs["Color"], mixz.inputs["B"])
nt.links.new(az.outputs["Fac"], mixz.inputs["Factor"])
nt.links.new(mixz.outputs["Result"], bsdf.inputs["Base Color"])
me.materials.append(mt)

set_game(terreno, 'STATIC', bounds='TRIANGLE_MESH')

# ----------------------------------------------------------------- molinos


def make_molino(name, mx, my, scale=1.0, detail=True):
    mz = terrain_h(mx, my)
    s = scale
    parts = []
    parts.append(cyl(f"{name}_base", 3.6 * s, 1.2 * s, (mx, my, mz + 0.6 * s),
                     M_PIEDRA, segs=18))
    parts.append(cyl(f"{name}_torre", 3.3 * s, 8.0 * s, (mx, my, mz + 1.2 * s + 4.0 * s),
                     M_CAL, segs=20, r2=2.7 * s))
    parts.append(cone(f"{name}_techo", 3.1 * s, 2.9 * s, (mx, my, mz + 9.2 * s + 1.2 * s),
                      M_TECHO, segs=20))
    if detail:
        parts.append(box(f"{name}_lintel", (1.5 * s, 0.5 * s, 0.3 * s),
                         (mx, my - 3.15 * s, mz + 2.35 * s), M_PIEDRA_OSC))
        parts.append(box(f"{name}_puerta", (1.1 * s, 0.3 * s, 2.1 * s),
                         (mx, my - 3.05 * s, mz + 1.25 * s), M_MADERA))
        parts.append(box(f"{name}_vent1", (0.6 * s, 0.3 * s, 0.8 * s),
                         (mx, my - 2.85 * s, mz + 5.4 * s), M_MADERA_OSC))
        parts.append(box(f"{name}_vent2", (0.6 * s, 0.3 * s, 0.8 * s),
                         (mx + 2.85 * s, my, mz + 6.8 * s), M_MADERA_OSC,
                         rot=(0, 0, math.radians(90))))
    m = join(parts, name)
    set_game(m, 'STATIC', bounds='TRIANGLE_MESH')

    # aspas de celosía
    aparts = [ico(f"{name}_hub", 0.5 * s, (0, 0, 0), M_MADERA_OSC, subdiv=2)]
    aparts.append(cyl(f"{name}_eje", 0.22 * s, 1.3 * s, (0, 0.5 * s, 0),
                      M_MADERA_OSC, segs=10, rot=(math.radians(90), 0, 0)))
    for k in range(4):
        ang = k * math.pi / 2.0
        sa, ca = math.sin(ang), math.cos(ang)
        spar = box(f"{name}_spar{k}", (0.16 * s, 0.16 * s, 6.4 * s), (0, 0, 0),
                   M_MADERA, rot=(0, ang, 0))
        spar.location = (sa * 3.2 * s, 0, ca * 3.2 * s)
        aparts.append(spar)
        if detail:
            for j in range(5):
                t = (1.6 + j * 1.15) * s
                bar = box(f"{name}_bar{k}_{j}", (1.7 * s, 0.07 * s, 0.10 * s),
                          (0, 0, 0), M_MADERA, rot=(0, ang, 0))
                bar.location = (sa * t + ca * 0.35 * s, 0, ca * t - sa * 0.35 * s)
                aparts.append(bar)
        canvas = box(f"{name}_lona{k}", (1.5 * s, 0.05 * s, 3.6 * s), (0, 0, 0),
                     M_LONA, rot=(0, ang, 0))
        canvas.location = (sa * 4.0 * s + ca * 0.85 * s, 0.12 * s,
                           ca * 4.0 * s - sa * 0.85 * s)
        aparts.append(canvas)
    aspas = join(aparts, f"{name}_Aspas")
    aspas.location = (mx, my - 3.6 * s, mz + 8.6 * s)
    aspas.rotation_euler = (math.radians(-12.0), math.radians(45.0), 0)
    set_game(aspas, 'NO_COLLISION')
    return m


print("[T1] molinos…")
make_molino("Molino", HILL.x, HILL.y, 1.0, detail=True)
make_molino("MolinoLejano1", 120.0, 85.0, 0.8, detail=False)
make_molino("MolinoLejano2", 25.0, 130.0, 0.7, detail=False)

# ----------------------------------------------------------------- pueblo
print("[T1] pueblo…")


def make_house(name, cx, cy, w, d, h, rot, chimney=False, lit=True):
    z = terrain_h(cx, cy)
    R = Matrix.Rotation(rot, 2)
    parts = []
    parts.append(box(f"{name}_zocalo", (w + 0.3, d + 0.3, 0.6), (cx, cy, z + 0.3),
                     M_PIEDRA_OSC, rot=(0, 0, rot)))
    parts.append(box(f"{name}_muros", (w, d, h), (cx, cy, z + 0.5 + h / 2.0),
                     M_CAL, rot=(0, 0, rot)))
    # vigas de esquina y dintel corrido
    for sx_, sy_ in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        off = R @ Vector((sx_ * w / 2, sy_ * d / 2))
        parts.append(box(f"{name}_viga", (0.16, 0.16, h),
                         (cx + off.x, cy + off.y, z + 0.5 + h / 2.0),
                         M_VIGA, rot=(0, 0, rot)))
    parts.append(box(f"{name}_dintel", (w + 0.2, d + 0.2, 0.14),
                     (cx, cy, z + 0.5 + h), M_VIGA, rot=(0, 0, rot)))
    roof = prism(f"{name}_tejado", w, d, h * 0.5, (cx, cy, z + 0.5 + h), M_TEJA, rot)
    parts.append(roof)
    ridge = box(f"{name}_caballete", (w + 0.6, 0.28, 0.14), (0, 0, 0), M_MADERA_OSC,
                rot=(0, 0, rot))
    roff = R @ Vector((0, 0))
    ridge.location = (cx + roff.x, cy + roff.y, z + 0.5 + h + h * 0.5)
    parts.append(ridge)
    # puerta con marco (fachada -Y local)
    doff = R @ Vector((0, -(d / 2)))
    dpos = Vector((cx + doff.x, cy + doff.y, 0))
    parts.append(box(f"{name}_marco", (1.15, 0.18, 2.05), (dpos.x, dpos.y, z + 1.55),
                     M_VIGA, rot=(0, 0, rot)))
    parts.append(box(f"{name}_puerta", (0.9, 0.22, 1.8), (dpos.x, dpos.y, z + 1.45),
                     M_MADERA, rot=(0, 0, rot)))
    # ventanas con contraventanas; alguna encendida
    for wi, u in enumerate((-w * 0.28, w * 0.28)):
        woff = R @ Vector((u, -(d / 2)))
        wx_, wy_ = cx + woff.x, cy + woff.y
        parts.append(box(f"{name}_vmarco{wi}", (0.75, 0.14, 0.75),
                         (wx_, wy_, z + 1.9), M_VIGA, rot=(0, 0, rot)))
        pane_mat = M_VENTANA_LUZ if (lit and wi == 0) else M_MADERA_OSC
        parts.append(box(f"{name}_vpane{wi}", (0.55, 0.18, 0.55),
                         (wx_, wy_, z + 1.9), pane_mat, rot=(0, 0, rot)))
        for sside in (-1, 1):
            soff = R @ Vector((u + sside * 0.55, -(d / 2)))
            parts.append(box(f"{name}_contra{wi}{sside}", (0.28, 0.10, 0.72),
                             (cx + soff.x, cy + soff.y, z + 1.9),
                             M_TECHO, rot=(0, 0, rot)))
    if chimney:
        choff = R @ Vector((w * 0.3, d * 0.2))
        parts.append(box(f"{name}_chimenea", (0.5, 0.5, 1.3),
                         (cx + choff.x, cy + choff.y, z + 0.5 + h + h * 0.4),
                         M_CAL, rot=(0, 0, rot)))
        parts.append(box(f"{name}_chtapa", (0.7, 0.7, 0.12),
                         (cx + choff.x, cy + choff.y, z + 0.5 + h + h * 0.4 + 0.7),
                         M_TEJA, rot=(0, 0, rot)))
    ho = join(parts, name)
    set_game(ho, 'STATIC', bounds='BOX')
    return ho


houses = [
    ("Casa01", VILLAGE.x + 12, VILLAGE.y + 10, 6, 5, 3.2, 0.1, True, True),
    ("Casa02", VILLAGE.x - 2, VILLAGE.y + 14, 5, 4.5, 3.0, -0.25, False, True),
    ("Casa03", VILLAGE.x - 14, VILLAGE.y + 4, 7, 5, 3.4, 1.65, True, False),
    ("Casa04", VILLAGE.x - 12, VILLAGE.y - 12, 5.5, 4.5, 3.0, 0.35, False, True),
    ("Casa05", VILLAGE.x + 2, VILLAGE.y - 16, 6, 5, 3.2, -1.35, True, True),
    ("Casa06", VILLAGE.x + 16, VILLAGE.y - 6, 5, 4, 2.8, 1.45, False, False),
]
for hspec in houses:
    make_house(*hspec)

# la venta: cuerpo en L + corral con tapia + cartel colgante
vx, vy = VILLAGE.x + 26, VILLAGE.y + 5
make_house("Venta", vx, vy, 10, 7, 4.2, 0.2, True, True)
make_house("Venta_ala", vx + 5.5, vy - 6.5, 6, 5, 3.2, 1.75, False, False)
vz = terrain_h(vx, vy - 9)
tap = []
for i in range(5):
    tap.append(box(f"tapia{i}", (2.4, 0.4, 1.1),
                   (vx - 5.5 + i * 2.5, vy - 10.5, vz + 0.55), M_CAL))
for i in range(4):
    tap.append(box(f"tapiaL{i}", (0.4, 2.4, 1.1),
                   (vx - 6.7, vy - 9.2 + i * -0.0 - i * 0 + i * 2.0 - 3.0, vz + 0.55), M_CAL))
tapia = join(tap, "Venta_Tapia")
set_game(tapia, 'STATIC', bounds='BOX')
sz = terrain_h(vx - 2, vy - 4.2)
sign = join([
    cyl("cartel_poste", 0.09, 3.0, (vx - 2, vy - 4.2, sz + 1.5), M_MADERA_OSC, segs=8),
    box("cartel_brazo", (1.2, 0.08, 0.08), (vx - 1.5, vy - 4.2, sz + 2.9), M_MADERA_OSC),
    box("cartel_tabla", (0.9, 0.06, 0.6), (vx - 1.1, vy - 4.2, sz + 2.45), M_MADERA),
], "Venta_Cartel")
set_game(sign, 'STATIC')

# pozo de sillares con torno
wx, wy = PLAZA.x - 5.0, PLAZA.y + 7.0
pzw = terrain_h(wx, wy)
wparts = []
for i in range(9):
    a = i / 9.0 * 2 * math.pi
    wparts.append(box(f"pozo_s{i}", (0.75, 0.45, 0.9),
                      (wx + math.cos(a) * 1.05, wy + math.sin(a) * 1.05, pzw + 0.45),
                      M_PIEDRA, rot=(0, 0, a)))
wparts.append(box("pozo_p1", (0.14, 0.14, 2.0), (wx - 1.1, wy, pzw + 1.7), M_MADERA))
wparts.append(box("pozo_p2", (0.14, 0.14, 2.0), (wx + 1.1, wy, pzw + 1.7), M_MADERA))
wparts.append(cyl("pozo_torno", 0.14, 2.0, (wx, wy, pzw + 2.35), M_MADERA,
                  segs=10, rot=(0, math.radians(90), 0)))
wparts.append(prism("pozo_tejadillo", 2.6, 1.2, 0.55, (wx, wy, pzw + 2.7), M_TEJA))
wparts.append(cyl("pozo_cubo", 0.18, 0.3, (wx, wy, pzw + 1.1), M_MADERA_OSC, segs=10))
pozo = join(wparts, "Pozo")
set_game(pozo, 'STATIC', bounds='TRIANGLE_MESH')

# faroles encendidos (plaza y arranque del camino)
farol_pos = [(PLAZA.x + 8, PLAZA.y + 8), (PLAZA.x - 8, PLAZA.y - 8),
             (PLAZA.x + 8, PLAZA.y - 8), (PLAZA.x - 9, PLAZA.y + 6),
             (PLAZA.x + 15, PLAZA.y + 1), (-40.0, -38.5)]
for i, (fx, fy) in enumerate(farol_pos):
    fz = terrain_h(fx, fy)
    f = join([
        cyl(f"farol{i}_poste", 0.07, 2.7, (fx, fy, fz + 1.35), M_HIERRO, segs=8),
        box(f"farol{i}_caja", (0.30, 0.30, 0.42), (fx, fy, fz + 2.85), M_HIERRO),
        box(f"farol{i}_luz", (0.34, 0.34, 0.28), (fx, fy, fz + 2.85), M_FAROL),
        cone(f"farol{i}_tapa", 0.26, 0.22, (fx, fy, fz + 3.15), M_HIERRO, segs=8),
    ], f"Farol{i:02d}")
    set_game(f, 'STATIC')

# era de trillar + almiares + carro
ex, ey = VILLAGE.x + 30, VILLAGE.y - 18
ez = terrain_h(ex, ey)
era = cyl("Era", 6.0, 0.12, (ex, ey, ez + 0.05), M_PIEDRA, segs=24)
set_game(era, 'NO_COLLISION')
for i, (ax, ay) in enumerate([(ex + 4, ey - 6), (ex - 3, ey - 7)]):
    az = terrain_h(ax, ay)
    alm = cone(f"Almiar{i}", 1.7, 2.6, (ax, ay, az + 1.3), M_PAJA, segs=12)
    set_game(alm, 'STATIC', bounds='BOX')
cz = terrain_h(ex + 6, ey + 2)
carro = join([
    cyl("carro_r1", 0.85, 0.14, (ex + 6, ey + 1.1, cz + 0.85), M_MADERA_OSC,
        segs=14, rot=(math.radians(90), 0, 0)),
    cyl("carro_r2", 0.85, 0.14, (ex + 6, ey + 2.9, cz + 0.85), M_MADERA_OSC,
        segs=14, rot=(math.radians(90), 0, 0)),
    box("carro_caja", (2.6, 1.5, 0.5), (ex + 6, ey + 2, cz + 1.15), M_MADERA,
        rot=(0, math.radians(-7), 0)),
    box("carro_vara", (2.4, 0.12, 0.12), (ex + 8.1, ey + 1.7, cz + 0.75), M_MADERA,
        rot=(0, math.radians(12), 0)),
    box("carro_vara2", (2.4, 0.12, 0.12), (ex + 8.1, ey + 2.3, cz + 0.75), M_MADERA,
        rot=(0, math.radians(12), 0)),
], "Carro")
set_game(carro, 'STATIC', bounds='BOX')

# cajas y barriles junto a la venta
bparts = []
bx0, by0 = vx - 4.5, vy - 2.0
bz0 = terrain_h(bx0, by0)
for i in range(3):
    bparts.append(box(f"caja{i}", (0.8, 0.8, 0.8),
                      (bx0 + (i % 2) * 1.0, by0 + (i // 2) * 1.0,
                       bz0 + 0.4 + (i // 2) * 0.0), M_MADERA,
                      rot=(0, 0, random.uniform(0, 0.6))))
for i in range(2):
    bparts.append(cyl(f"barril{i}", 0.42, 0.9, (bx0 - 1.2 - i * 1.0, by0 + 0.3,
                                                bz0 + 0.45), M_MADERA_OSC, segs=12))
    bparts.append(cyl(f"barrilaro{i}", 0.45, 0.12, (bx0 - 1.2 - i * 1.0, by0 + 0.3,
                                                    bz0 + 0.65), M_HIERRO, segs=12))
cajas = join(bparts, "Cajas")
set_game(cajas, 'STATIC', bounds='BOX')

# ----------------------------------------------------------------- camino
print("[T1] camino, vallas, puente…")

# piedras de borde del camino
edge_parts_bm = bmesh.new()
for i in range(4, len(PATH) - 4, 4):
    p = PATH[i]
    t = (PATH[i + 1] - PATH[i - 1]).normalized()
    n = Vector((-t.y, t.x))
    for sside in (-1, 1):
        if random.random() < 0.35:
            continue
        q = Vector((p.x, p.y)) + n * sside * (PATH_W * 0.62 + random.uniform(0, 0.5))
        qz = terrain_h(q.x, q.y)
        rr = random.uniform(0.14, 0.30)
        mtx = Matrix.Translation((q.x, q.y, qz + rr * 0.4))
        bmesh.ops.create_icosphere(edge_parts_bm, subdivisions=1, radius=rr, matrix=mtx)
me_e = bpy.data.meshes.new("CaminoBordes")
edge_parts_bm.to_mesh(me_e)
edge_parts_bm.free()
bordes = new_obj("CaminoBordes", me_e)
me_e.materials.append(M_PIEDRA_OSC)
set_game(bordes, 'NO_COLLISION')

# vallas de madera a la salida del pueblo
for sside, nm in ((-1, "VallaSur"), (1, "VallaNorte")):
    vparts = []
    for i in range(8, 26, 3):
        p = PATH[i]
        t = (PATH[i + 1] - PATH[i - 1]).normalized()
        n = Vector((-t.y, t.x))
        q = Vector((p.x, p.y)) + n * sside * (PATH_W * 0.9)
        qz = terrain_h(q.x, q.y)
        vparts.append(cyl(f"{nm}_p{i}", 0.09, 1.1, (q.x, q.y, qz + 0.55),
                          M_MADERA, segs=8))
        if i > 8:
            prev = vparts[-3 if len(vparts) >= 3 else -2]
    # raíles entre postes
    posts = [o for o in vparts]
    rparts = []
    for j in range(len(posts) - 1):
        a = Vector(posts[j].location)
        b = Vector(posts[j + 1].location)
        mid = (a + b) / 2
        L = (b - a).length
        yaw = math.atan2(b.y - a.y, b.x - a.x)
        for zz in (0.45, 0.85):
            rparts.append(box(f"{nm}_r{j}{zz}", (L, 0.07, 0.07),
                              (mid.x, mid.y, (a.z + b.z) / 2 + zz - 0.55),
                              M_MADERA, rot=(0, 0, yaw)))
    valla = join(vparts + rparts, nm)
    set_game(valla, 'STATIC', bounds='BOX')

# puente de madera sobre el arroyo
cross_i = min(range(len(PATH)), key=lambda i: seg_dist(PATH[i], A0, A1))
cp = PATH[cross_i]
ct = (PATH[min(cross_i + 2, len(PATH) - 1)] - PATH[max(cross_i - 2, 0)]).normalized()
yaw = math.atan2(ct.y, ct.x)
end_a = Vector((cp.x, cp.y)) - ct * 4.5
end_b = Vector((cp.x, cp.y)) + ct * 4.5
deck_z = max(terrain_h(end_a.x, end_a.y), terrain_h(end_b.x, end_b.y)) + 0.25
bparts = []
for sside in (-1, 1):
    nn = Vector((-ct.y, ct.x)) * sside * 1.15
    bparts.append(box(f"puente_viga{sside}", (9.4, 0.22, 0.34),
                      (cp.x + nn.x, cp.y + nn.y, deck_z - 0.2), M_MADERA_OSC,
                      rot=(0, 0, yaw)))
    for px in (-3.4, 0.0, 3.4):
        pp = Vector((cp.x, cp.y)) + ct * px + Vector((-ct.y, ct.x)) * sside * 1.15
        bparts.append(cyl(f"puente_poste{sside}{px}", 0.09, 1.0,
                          (pp.x, pp.y, deck_z + 0.5), M_MADERA, segs=8))
    rr = Vector((cp.x, cp.y)) + Vector((-ct.y, ct.x)) * sside * 1.15
    bparts.append(box(f"puente_rail{sside}", (8.6, 0.09, 0.09),
                      (rr.x, rr.y, deck_z + 0.95), M_MADERA, rot=(0, 0, yaw)))
for j in range(11):
    px = -4.5 + j * 0.9
    pp = Vector((cp.x, cp.y)) + ct * px
    bparts.append(box(f"puente_tabla{j}", (0.7, 2.5, 0.09),
                      (pp.x, pp.y, deck_z), M_MADERA, rot=(0, 0, yaw)))
puente = join(bparts, "Puente")
set_game(puente, 'STATIC', bounds='TRIANGLE_MESH')

# piedras del lecho del arroyo
bed_bm = bmesh.new()
for _ in range(46):
    t = random.random()
    q = A0.lerp(A1, t)
    n = Vector((-(A1 - A0).y, (A1 - A0).x)).normalized()
    q = q + n * random.uniform(-2.6, 2.6)
    if (Vector((cp.x, cp.y)) - q).length < 4.0:
        continue
    qz = terrain_h(q.x, q.y)
    rr = random.uniform(0.15, 0.45)
    mtx = Matrix.Translation((q.x, q.y, qz + rr * 0.35)) @ Matrix.Scale(
        random.uniform(0.7, 1.3), 4, (1, 0, 0))
    bed_bm2 = bmesh.ops.create_icosphere(bed_bm, subdivisions=1, radius=rr, matrix=mtx)
me_b = bpy.data.meshes.new("ArroyoPiedras")
bed_bm.to_mesh(me_b)
bed_bm.free()
apiedras = new_obj("ArroyoPiedras", me_b)
me_b.materials.append(M_PIEDRA)
set_game(apiedras, 'NO_COLLISION')

# poste indicador en el desvío
sx_, sy_ = 8.0, -30.0
sz_ = terrain_h(sx_ + 3, sy_ - 3)
signp = join([
    cyl("indicador_poste", 0.09, 2.6, (sx_ + 3, sy_ - 3, sz_ + 1.3), M_MADERA_OSC, segs=8),
    box("indicador_t1", (1.1, 0.07, 0.32), (sx_ + 3.4, sy_ - 3, sz_ + 2.3), M_MADERA,
        rot=(0, 0, math.radians(35))),
    box("indicador_t2", (1.1, 0.07, 0.32), (sx_ + 2.6, sy_ - 3, sz_ + 1.9), M_MADERA,
        rot=(0, 0, math.radians(-140))),
], "Indicador")
set_game(signp, 'STATIC')

# ----------------------------------------------------------------- vegetación
print("[T1] vegetación y rocas…")
house_pts = [Vector((h[1], h[2])) for h in houses] + [Vector((vx, vy)), Vector((vx + 5.5, vy - 6.5))]


def spot_free(x, y, margin=7.0):
    if path_dist(x, y) < margin:
        return False
    if (Vector((x, y)) - VILLAGE).length < 42.0:
        return False
    if (Vector((x, y)) - HILL).length < 15.0:
        return False
    if arroyo_dist(x, y) < 8.0:
        return False
    return True


def scatter(n, fn, margin=7.0):
    placed = 0
    tries = 0
    while placed < n and tries < n * 40:
        tries += 1
        x = random.uniform(-MAP_SIZE / 2 * 0.9, MAP_SIZE / 2 * 0.9)
        y = random.uniform(-MAP_SIZE / 2 * 0.9, MAP_SIZE / 2 * 0.9)
        if not spot_free(x, y, margin):
            continue
        fn(placed, x, y)
        placed += 1


def make_olivo(i, x, y):
    z = terrain_h(x, y)
    parts = []
    lean = random.uniform(-0.15, 0.15)
    px_, py_, pz_ = x, y, z
    r0 = 0.30
    for s_ in range(3):
        h_ = random.uniform(0.5, 0.8)
        seg = cyl(f"Olivo{i:02d}_t{s_}", r0, h_, (px_, py_, pz_ + h_ / 2), M_OLIVO_T,
                  segs=8, r2=r0 * 0.75, rot=(lean, random.uniform(-0.1, 0.1), 0))
        parts.append(seg)
        px_ += math.sin(lean) * h_ + random.uniform(-0.1, 0.1)
        py_ += random.uniform(-0.12, 0.12)
        pz_ += h_ * 0.92
        r0 *= 0.75
    for j in range(4):
        cx = px_ + random.uniform(-0.9, 0.9)
        cy = py_ + random.uniform(-0.9, 0.9)
        cz = pz_ + 0.5 + random.uniform(-0.2, 0.6)
        parts.append(ico(f"Olivo{i:02d}_c{j}", random.uniform(0.8, 1.3),
                         (cx, cy, cz), M_OLIVO_C, subdiv=1,
                         scale=(1, 1, random.uniform(0.65, 0.85))))
    o = join(parts, f"Olivo{i:02d}")
    set_game(o, 'STATIC', bounds='BOX')


def make_matorral_batch(bi, pts):
    parts = []
    for j, (x, y) in enumerate(pts):
        z = terrain_h(x, y)
        parts.append(ico(f"mat{bi}_{j}", random.uniform(0.5, 1.1), (x, y, z + 0.25),
                         M_MATORRAL, subdiv=1, scale=(1.2, 1.2, 0.5)))
    b = join(parts, f"Matorrales{bi:02d}")
    set_game(b, 'NO_COLLISION')


def make_roca(i, x, y):
    z = terrain_h(x, y)
    parts = []
    for j in range(random.randint(1, 3)):
        rr = random.uniform(0.5, 1.6)
        parts.append(ico(f"Roca{i:02d}_{j}", rr,
                         (x + random.uniform(-1, 1), y + random.uniform(-1, 1), z + rr * 0.35),
                         M_PIEDRA, subdiv=1,
                         scale=(random.uniform(0.7, 1.5), random.uniform(0.7, 1.5),
                                random.uniform(0.5, 0.9)), smooth=False))
    r = join(parts, f"Roca{i:02d}")
    r.rotation_euler = (0, 0, random.uniform(0, 6.28))
    set_game(r, 'STATIC', bounds='BOX')


scatter(16, make_olivo)

mat_pts = []
scatter(48, lambda i, x, y: mat_pts.append((x, y)))
for bi in range(0, len(mat_pts), 12):
    make_matorral_batch(bi // 12, mat_pts[bi:bi + 12])

scatter(11, make_roca)

# hierba seca: matas de planos cruzados, por lotes
grass_pts = []
scatter(200, lambda i, x, y: grass_pts.append((x, y)), margin=5.5)
for bi in range(0, len(grass_pts), 25):
    gbm = bmesh.new()
    for (x, y) in grass_pts[bi:bi + 25]:
        z = terrain_h(x, y)
        mtx = (Matrix.Translation((x, y, z + 0.22)) @
               Matrix.Rotation(random.uniform(0, 0.3), 4, 'X') @
               Matrix.Diagonal((1, 1, random.uniform(0.8, 1.3), 1)))
        bmesh.ops.create_cone(gbm, cap_ends=False, segments=6,
                              radius1=0.22, radius2=0.03, depth=0.5, matrix=mtx)
    gme = bpy.data.meshes.new(f"Hierba{bi:03d}")
    gbm.to_mesh(gme)
    gbm.free()
    gob = new_obj(f"Hierba{bi:03d}", gme)
    gme.materials.append(M_HIERBA)
    set_game(gob, 'NO_COLLISION')

# amapolas: parches de puntos rojos
pop_centers = []
scatter(6, lambda i, x, y: pop_centers.append((x, y)), margin=6.0)
for pi, (cx, cy) in enumerate(pop_centers):
    pbm = bmesh.new()
    for _ in range(26):
        x = cx + random.gauss(0, 2.2)
        y = cy + random.gauss(0, 2.2)
        z = terrain_h(x, y)
        mtx = Matrix.Translation((x, y, z + 0.28))
        bmesh.ops.create_icosphere(pbm, subdivisions=1, radius=random.uniform(0.05, 0.09),
                                   matrix=mtx)
    pme = bpy.data.meshes.new(f"Amapolas{pi}")
    pbm.to_mesh(pme)
    pbm.free()
    pob = new_obj(f"Amapolas{pi}", pme)
    pme.materials.append(M_AMAPOLA)
    set_game(pob, 'NO_COLLISION')

# viñedo: dos parcelas en filas
for vi, (vcx, vcy) in enumerate([(VILLAGE.x - 18, VILLAGE.y - 30), (VILLAGE.x + 8, VILLAGE.y - 34)]):
    vbm = bmesh.new()
    ca, sa = math.cos(FIELD_ANG), math.sin(FIELD_ANG)
    for row in range(4):
        for col in range(7):
            lx = (col - 3) * 2.2
            ly = (row - 1.5) * 2.6
            x = vcx + lx * ca - ly * sa
            y = vcy + lx * sa + ly * ca
            z = terrain_h(x, y)
            mtx = (Matrix.Translation((x, y, z + 0.35)) @
                   Matrix.Diagonal((1.1, 1.1, 0.65, 1)))
            bmesh.ops.create_icosphere(vbm, subdivisions=1, radius=0.42, matrix=mtx)
    vme = bpy.data.meshes.new(f"Vinnedo{vi}")
    vbm.to_mesh(vme)
    vbm.free()
    vob = new_obj(f"Vinnedo{vi}", vme)
    vme.materials.append(M_VID)
    for p in vme.polygons:
        p.use_smooth = True
    set_game(vob, 'NO_COLLISION')

# cipreses junto al camino de entrada y la era
for ci, (cx, cy) in enumerate([(VILLAGE.x + 21, VILLAGE.y + 13), (VILLAGE.x + 23, VILLAGE.y + 16),
                               (ex - 7, ey + 4), (ex - 9, ey + 1)]):
    z = terrain_h(cx, cy)
    c = join([
        cyl(f"cip{ci}_t", 0.14, 0.8, (cx, cy, z + 0.4), M_OLIVO_T, segs=8),
        cone(f"cip{ci}_c", 0.85, 5.5, (cx, cy, z + 3.4), M_CIPRES, segs=10),
    ], f"Cipres{ci:02d}")
    set_game(c, 'STATIC', bounds='BOX')

# ----------------------------------------------------------------- motas de Ánima
print("[T1] motas de Ánima…")


def mota_cloud(name, cx, cy, cz, rad, count, zspread):
    me_m = bpy.data.meshes.new(name)
    bm_m = bmesh.new()
    for _ in range(count):
        px = random.gauss(0, rad * 0.5)
        py = random.gauss(0, rad * 0.5)
        pz = random.uniform(0.3, zspread)
        rr = random.uniform(0.026, 0.055)
        bmesh.ops.create_icosphere(bm_m, subdivisions=1, radius=rr,
                                   matrix=Matrix.Translation((px, py, pz)))
    bm_m.to_mesh(me_m)
    bm_m.free()
    ob = new_obj(name, me_m)
    ob.location = (cx, cy, cz)
    me_m.materials.append(M_ANIMA)
    set_game(ob, 'NO_COLLISION', ghost=True)
    return ob


mota_cloud("AnimaMotas_Plaza", PLAZA.x, PLAZA.y, terrain_h(PLAZA.x, PLAZA.y), 7.0, 80, 4.5)
mota_cloud("AnimaMotas_Pozo", wx, wy, pzw, 3.0, 45, 3.0)
mid = PATH[len(PATH) // 2]
mota_cloud("AnimaMotas_Camino", mid.x, mid.y, terrain_h(mid.x, mid.y), 6.0, 55, 4.0)
mota_cloud("AnimaMotas_Molino", HILL.x, HILL.y, terrain_h(HILL.x, HILL.y) + 1.0, 8.0, 90, 7.0)
mota_cloud("AnimaMotas_Era", ex, ey, ez, 5.0, 40, 3.5)
mota_cloud("AnimaMotas_Puente", cp.x, cp.y, deck_z, 4.0, 40, 3.0)
mota_cloud("AnimaMotas_Venta", vx, vy - 4, terrain_h(vx, vy - 4), 4.0, 35, 3.5)

# ----------------------------------------------------------------- gameplay (datos puros)
print("[T1] objetos de juego…")
pzz = terrain_h(PLAZA.x, PLAZA.y)

cuerpo = ico("Player_cuerpo", 0.5, (0, 0, 0.75), M_HEROE, subdiv=2, scale=(0.75, 0.75, 1.5))
cabeza = ico("Player_cabeza", 0.32, (0, 0, 1.75), M_PIEL, subdiv=2)
player = join([cuerpo, cabeza], "Player")
player.location = (PLAZA.x, PLAZA.y, pzz + 1.0)
g = player.game
g.physics_type = 'CHARACTER'
g.use_collision_bounds = True
g.collision_bounds_type = 'CAPSULE'
g.radius = 0.5
g.step_height = 0.6
add_prop(player, "fl_component", "PlayerController")

cam_data = bpy.data.cameras.new("GameCamera")
cam = bpy.data.objects.new("GameCamera", cam_data)
bpy.context.collection.objects.link(cam)
cam.location = (PLAZA.x, PLAZA.y - 7.0, pzz + 3.2)
cam.rotation_euler = (math.radians(75), 0, 0)
cam_data.clip_end = 800.0
set_game(cam, 'NO_COLLISION')
add_prop(cam, "fl_component", "ThirdPersonCamera")
sc.camera = cam

# pesadillas provisionales (diseño de enemigos SIN decidir — placeholder modular)
for i, t in enumerate([0.35, 0.55, 0.75]):
    p = PATH[int(t * (len(PATH) - 1))]
    z = terrain_h(p.x, p.y)
    body = ico(f"pes{i}_cuerpo", 0.7, (0, 0, 0), M_PESADILLA, subdiv=2,
               scale=(1.0, 1.0, 1.3))
    for v in body.data.vertices:
        v.co += Vector((random.uniform(-0.08, 0.08),
                        random.uniform(-0.08, 0.08),
                        random.uniform(-0.05, 0.12)))
    eyes = [ico(f"pes{i}_ojo{k}", 0.07, (0.18 * (1 if k else -1), -0.55, 0.45),
                M_PESADILLA_OJO, subdiv=1) for k in (0, 1)]
    e = join([body] + eyes, f"Pesadilla{i:02d}")
    e.location = (p.x + random.uniform(-3, 3), p.y + random.uniform(-3, 3), z + 0.9)
    set_game(e, 'STATIC')
    add_prop(e, "fl_component", "EnemyAI")

# ----------------------------------------------------------------- cielo y luz
print("[T1] cielo y luz…")
world = bpy.data.worlds.new("W_LaMancha")
sc.world = world
world.use_nodes = True
wnt = world.node_tree
for n in list(wnt.nodes):
    wnt.nodes.remove(n)
out = wnt.nodes.new("ShaderNodeOutputWorld")
bg = wnt.nodes.new("ShaderNodeBackground")
bg.inputs["Strength"].default_value = 1.15
tc = wnt.nodes.new("ShaderNodeTexCoord")
sep = wnt.nodes.new("ShaderNodeSeparateXYZ")
mr = wnt.nodes.new("ShaderNodeMapRange")
mr.inputs["From Min"].default_value = -0.15
mr.inputs["From Max"].default_value = 0.6
wramp = wnt.nodes.new("ShaderNodeValToRGB")
cr = wramp.color_ramp
cr.elements[0].position = 0.0
cr.elements[0].color = (1.0, 0.42, 0.10, 1.0)
e1 = cr.elements.new(0.16)
e1.color = (1.0, 0.63, 0.22, 1.0)
e2 = cr.elements.new(0.42)
e2.color = (0.72, 0.45, 0.42, 1.0)
cr.elements[-1].position = 1.0
cr.elements[-1].color = (0.20, 0.23, 0.42, 1.0)
wnt.links.new(tc.outputs["Generated"], sep.inputs["Vector"])
wnt.links.new(sep.outputs["Z"], mr.inputs["Value"])
wnt.links.new(mr.outputs["Result"], wramp.inputs["Fac"])
wnt.links.new(wramp.outputs["Color"], bg.inputs["Color"])
wnt.links.new(bg.outputs["Background"], out.inputs["Surface"])

sun_d = bpy.data.lights.new("Sol", 'SUN')
sun_d.energy = 4.2
sun_d.color = (1.0, 0.70, 0.42)
sun_d.angle = math.radians(1.5)
sun = bpy.data.objects.new("Sol", sun_d)
bpy.context.collection.objects.link(sun)
sun.rotation_euler = (math.radians(76), 0, math.radians(-125))
set_game(sun, 'NO_COLLISION')

fill_d = bpy.data.lights.new("Relleno", 'SUN')
fill_d.energy = 0.5
fill_d.color = (0.55, 0.62, 0.90)
fill = bpy.data.objects.new("Relleno", fill_d)
bpy.context.collection.objects.link(fill)
fill.rotation_euler = (math.radians(55), 0, math.radians(55))
set_game(fill, 'NO_COLLISION')

# disco solar incandescente en el horizonte (en la dirección de la luz)
sdir = Euler(sun.rotation_euler).to_matrix() @ Vector((0, 0, 1))
spos = sdir * 420.0
spos.z = max(spos.z, 26.0)
glow = cyl("SolGlow", 26.0, 0.3, spos, M_SOLGLOW, segs=24)
glow.rotation_euler = (Vector((0, 0, 0)) - spos).to_track_quat('-Z', 'Y').to_euler()
set_game(glow, 'NO_COLLISION')

# nubes estilizadas: bandas retroiluminadas hacia el sol + sueltas
for ci in range(9):
    if ci < 5:
        base_ang = math.atan2(sdir.y, sdir.x) + random.uniform(-0.7, 0.7)
        dist = random.uniform(190, 290)
        cz = random.uniform(38, 70)
    else:
        base_ang = random.uniform(0, 2 * math.pi)
        dist = random.uniform(180, 260)
        cz = random.uniform(55, 95)
    cx = math.cos(base_ang) * dist
    cy = math.sin(base_ang) * dist
    cbm = bmesh.new()
    for _ in range(random.randint(4, 7)):
        mtx = (Matrix.Translation((random.uniform(-14, 14), random.uniform(-5, 5),
                                   random.uniform(-2, 2))) @
               Matrix.Diagonal((random.uniform(2.5, 5.0), random.uniform(1.4, 2.4),
                                random.uniform(0.5, 0.9), 1)))
        bmesh.ops.create_icosphere(cbm, subdivisions=2, radius=3.0, matrix=mtx)
    cme = bpy.data.meshes.new(f"Nube{ci:02d}")
    cbm.to_mesh(cme)
    cbm.free()
    nob = new_obj(f"Nube{ci:02d}", cme)
    nob.location = (cx, cy, cz)
    cme.materials.append(M_NUBE)
    for p in cme.polygons:
        p.use_smooth = True
    set_game(nob, 'NO_COLLISION')

# ----------------------------------------------------------------- ajustes
gs = sc.game_settings
gs.fps = 60
gs.physics_engine = 'BULLET'
gs.physics_gravity = 9.8

sc.render.resolution_x = 1280
sc.render.resolution_y = 720
sc.view_settings.view_transform = 'Standard'
try:
    sc.eevee.taa_render_samples = 24
except AttributeError:
    pass


def vista_cam(name, loc, target):
    cd = bpy.data.cameras.new(name)
    cd.clip_end = 900.0
    co = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(co)
    co.location = loc
    dirv = Vector(target) - Vector(loc)
    co.rotation_euler = dirv.to_track_quat('-Z', 'Y').to_euler()
    set_game(co, 'NO_COLLISION')
    return co


hz = terrain_h(HILL.x, HILL.y)
vista_cam("CamVista", (-14.0, -72.0, terrain_h(-14.0, -72.0) + 11.0),
          (HILL.x, HILL.y, hz + 6.0))
vista_cam("CamPlaza", (PLAZA.x + 13, PLAZA.y - 11, pzz + 4.0),
          (PLAZA.x - 3, PLAZA.y + 4, pzz + 2.0))
vista_cam("CamMolino", (HILL.x - 14, HILL.y - 26, hz + 3.0),
          (HILL.x, HILL.y, hz + 8.0))
vista_cam("CamPuente", (cp.x - 12, cp.y - 9, deck_z + 4.0),
          (cp.x + 6, cp.y + 6, deck_z + 1.0))

# ----------------------------------------------------------------- guardar
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[T1] guardado: {OUT_BLEND}")
print(f"[T1] objetos: {len(bpy.data.objects)}  verts terreno: {len(terreno.data.vertices)}")
print("[T1] OK")
