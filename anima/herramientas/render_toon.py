# ÁNIMA — render toon de comprobación (3 cámaras: cara, 3/4, cuerpo)
#   Flipendo --background <fichero.blend> --python rtoon.py -- <dir_salida> <prefijo>
# Los .blend del personaje no llevan luces ni cámaras (las pone la escena del
# juego), así que este script las crea con una iluminación fija para que dos
# renders sean comparables entre sí.
import bpy, sys
from mathutils import Vector
args = sys.argv[sys.argv.index("--") + 1:]
out, pref = args[0], args[1]
sc = bpy.context.scene
for o in list(bpy.data.objects):
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)

def luz(nombre, tipo, loc, tgt, energia, color=(1, 1, 1)):
    ld = bpy.data.lights.new(nombre, tipo)
    ld.energy = energia
    ld.color = color
    o = bpy.data.objects.new(nombre, ld)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

# clave alta y a la izquierda del personaje (su derecha en pantalla), relleno frío
luz("Clave", 'SUN', (-2.0, -3.0, 4.0), (0, 0, 1.4), 3.0, (1.0, 0.97, 0.92))
luz("Relleno", 'SUN', (3.0, -2.0, 1.5), (0, 0, 1.4), 0.6, (0.85, 0.9, 1.0))

w = sc.world or bpy.data.worlds.new("World")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes.get("Background")
if bg:
    bg.inputs["Color"].default_value = (0.62, 0.66, 0.72, 1)
    bg.inputs["Strength"].default_value = 0.35

def cam(nombre, loc, tgt, lens):
    cd = bpy.data.cameras.new(nombre)
    cd.lens = lens
    o = bpy.data.objects.new(nombre, cd)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o

# la cara mira a -Y; la cabeza queda en z 1,39-1,70 (pelo) con los ojos en z 1,54
cam("Cara", (0.0, -0.80, 1.56), (0.0, -0.05, 1.55), 85)
cam("Tres4", (0.62, -0.62, 1.62), (0.0, -0.04, 1.55), 70)
cam("Cuerpo", (0.0, -3.6, 0.95), (0.0, 0.0, 0.86), 50)

sc.render.resolution_x, sc.render.resolution_y = 900, 1200
sc.render.resolution_percentage = 100
sc.render.film_transparent = False
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.view_settings.view_transform = 'Standard'
sc.eevee.taa_render_samples = 24
for n, f in (("Cara", "cara"), ("Tres4", "34"), ("Cuerpo", "cuerpo")):
    sc.camera = bpy.data.objects[n]
    sc.render.filepath = f"{out}/{pref}-{f}.png"
    bpy.ops.render.render(write_still=True)
    print("RTOON", f)
