# ÁNIMA — evidencias de la espada (carril ESPADA)
#   Flipendo --background Espada.blend --python render_espada.py -- <dir_salida> <prefijo>
# Renders toon (EEVEE Next, un Sun, fondo neutro) desde tres ángulos, silueta
# en negro sobre blanco (plano y canto), y la prueba de píxeles a la distancia
# de la cámara del juego (7 m y 15 m, lente 50 mm, 1280×800: 3,9 / 8,4 mm/px).
# Escribe también <prefijo>-medidas.txt con tris, bbox y medidas.
import bpy, sys, math
from mathutils import Vector

args = sys.argv[sys.argv.index("--") + 1:]
out, pref = args[0], args[1]
sc = bpy.context.scene
ob = bpy.data.objects["Espada"]
me = ob.data

# ---- medidas
tris = sum(len(p.vertices) - 2 for p in me.polygons)
xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
lineas = []
lineas.append(f"objeto {ob.name}: verts {len(me.vertices)} caras {len(me.polygons)} tris {tris}")
lineas.append(f"bbox X {min(xs)*1000:.1f}..{max(xs)*1000:.1f} mm ({(max(xs)-min(xs))*1000:.1f})")
lineas.append(f"bbox Y {min(ys)*1000:.1f}..{max(ys)*1000:.1f} mm ({(max(ys)-min(ys))*1000:.1f}) = largo total con cinta")
lineas.append(f"bbox Z {min(zs)*1000:.1f}..{max(zs)*1000:.1f} mm ({(max(zs)-min(zs))*1000:.1f})")
for k in ("ESPADA_LARGO", "ESPADA_HOJA", "ESPADA_Y_CRUZ"):
    if k in ob:
        lineas.append(f"{k} = {ob[k]*1000:.1f} mm")
# anchura de la hoja por Y (rebanadas) sobre el material 0/1
ycruz = ob.get("ESPADA_Y_CRUZ", 0.0605)
for dy in (0.0, 0.05, 0.11, 0.2, 0.3, 0.42, 0.6, 0.8, 0.88, 0.92):
    y = ycruz + dy
    sel = [v.co for v in me.vertices if abs(v.co.y - y) < 0.02 and abs(v.co.x) < 0.0345 and abs(v.co.z) < 0.011]
    if sel:
        w = max(c.x for c in sel) - min(c.x for c in sel)
        t = max(c.z for c in sel) - min(c.z for c in sel)
        lineas.append(f"hoja a {dy*1000:4.0f} mm de la cruz: ancho {w*1000:5.1f} mm grueso {t*1000:4.1f} mm")
if "ESPADA_PARTES" in ob:
    for k, bb in ob["ESPADA_PARTES"].items():
        bb = [float(x) * 1000 for x in bb]
        lineas.append(f"parte {k:11s}: X {bb[0]:7.1f}..{bb[1]:7.1f}  Y {bb[2]:7.1f}..{bb[3]:7.1f}  Z {bb[4]:6.1f}..{bb[5]:6.1f} mm")
mats = [m.name for m in me.materials]
for i, mn in enumerate(mats):
    n = sum(1 for p in me.polygons if p.material_index == i)
    lineas.append(f"material {i} {mn}: {n} caras")
for m in ob.modifiers:
    lineas.append(f"modificador {m.name} {m.type} grosor {getattr(m, 'thickness', 0)*1000:.2f} mm factor {getattr(m, 'thickness_vertex_group', 1):.2f}")
lineas.append("propiedades de juego: " + ", ".join(f"{p.name}={p.value}" for p in ob.game.properties))
lineas.append(f"fps {sc.render.fps}; text blocks {len(bpy.data.texts)}")
with open(f"{out}/{pref}-medidas.txt", "w") as f:
    f.write("\n".join(lineas) + "\n")
print("\n".join(lineas))

# ---- luces y mundo
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)

def sun(loc, tgt, energia, color=(1, 1, 1)):
    ld = bpy.data.lights.new("Sol", 'SUN'); ld.energy = energia; ld.color = color
    o = bpy.data.objects.new("Sol", ld); bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

SOL = sun((-1.5, 0.2, 3.0), (0, 0.45, 0), 3.0, (1.0, 0.97, 0.92))
w = sc.world or bpy.data.worlds.new("World"); sc.world = w; w.use_nodes = True
bg = w.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.62, 0.66, 0.72, 1)
bg.inputs["Strength"].default_value = 0.35

def cam(nombre, loc, rot=None, tgt=None, lens=50):
    cd = bpy.data.cameras.new(nombre); cd.lens = lens; cd.clip_end = 200
    o = bpy.data.objects.new(nombre, cd); bpy.context.collection.objects.link(o)
    o.location = loc
    if rot is not None:
        o.rotation_euler = rot
    else:
        o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

CY = 0.44   # centro del largo (−0,13 .. 1,0)
cam("Plano", (0.0, CY, 2.0), rot=(0, 0, 0))                     # mira −Z: se ve el plano de la hoja
cam("Canto", (2.0, CY, 0.0), rot=(0, math.pi / 2, 0))           # mira −X: se ve el canto
cam("Tres4", (1.3, CY - 0.9, 1.5), tgt=(0, CY, 0))
cam("Guarda", (0.25, -0.02, 0.55), tgt=(0, 0.0, 0))             # detalle de la guarnición
cam("Juego7", (4.0, CY - 3.5, 4.5), tgt=(0, CY, 0))             # ~7 m de distancia
cam("Juego15", (8.6, CY - 7.5, 9.6), tgt=(0, CY, 0))            # ~15 m

sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.view_settings.view_transform = 'Standard'
sc.eevee.taa_render_samples = 24

def render(nombre, fichero, rx, ry):
    sc.camera = bpy.data.objects[nombre]
    sc.render.resolution_x, sc.render.resolution_y = rx, ry
    sc.render.filepath = f"{out}/{pref}-{fichero}.png"
    bpy.ops.render.render(write_still=True)
    print("RENDER", fichero)

render("Plano", "plano", 700, 1400)
render("Canto", "canto", 700, 1400)
render("Tres4", "34", 1000, 1200)
render("Guarda", "guarda", 1200, 900)
render("Juego7", "juego7m", 1280, 800)
render("Juego15", "juego15m", 1280, 800)

# ---- silueta: todo negro sobre blanco, sin contorno
negro = bpy.data.materials.new("Silueta"); negro.use_nodes = True
nt = negro.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
sal = nt.nodes.new("ShaderNodeOutputMaterial"); emi = nt.nodes.new("ShaderNodeEmission")
emi.inputs["Color"].default_value = (0, 0, 0, 1)
nt.links.new(emi.outputs["Emission"], sal.inputs["Surface"])
for m in ob.modifiers:
    if m.type == 'SOLIDIFY':
        m.show_render = False
me.materials.clear(); me.materials.append(negro)
bg.inputs["Color"].default_value = (1, 1, 1, 1); bg.inputs["Strength"].default_value = 1.0
render("Plano", "silueta-plano", 700, 1400)
render("Canto", "silueta-canto", 700, 1400)
render("Tres4", "silueta-34", 1000, 1200)
render("Juego7", "silueta-juego7m", 1280, 800)
render("Juego15", "silueta-juego15m", 1280, 800)
