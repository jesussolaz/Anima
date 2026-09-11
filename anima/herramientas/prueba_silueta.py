# ÁNIMA — prueba de la silueta
#
#   Flipendo --background <fichero.blend> --python prueba_silueta.py -- <dir_salida>
#
# Renderiza al personaje completamente en NEGRO sobre blanco. Es la comprobación
# objetiva de la fase de bloqueo: si la mancha no se lee —si no se distingue la
# cabeza del pelo, o el pelo del cuerpo— no hay detalle que lo salve y hay que
# volver atrás. Los detalles no arreglan formas malas, solo las señalan.

import bpy
import sys
from mathutils import Vector

out = (sys.argv[sys.argv.index("--") + 1:] or ["/tmp"])[0]
sc = bpy.context.scene

negro = bpy.data.materials.new("Silueta")
negro.use_nodes = True
nt = negro.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
sal = nt.nodes.new("ShaderNodeOutputMaterial")
emi = nt.nodes.new("ShaderNodeEmission")
emi.inputs["Color"].default_value = (0, 0, 0, 1)
nt.links.new(emi.outputs["Emission"], sal.inputs["Surface"])

todo = []
for o in bpy.data.objects:
    if o.type == 'MESH':
        o.data.materials.clear()
        o.data.materials.append(negro)
        todo += [o.matrix_world @ v.co for v in o.data.vertices]
    elif o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)

zmin, zmax = min(v.z for v in todo), max(v.z for v in todo)
cz = (zmin + zmax) * 0.5
H = zmax - zmin

w = bpy.data.worlds.new("Blanco")
sc.world = w
w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)
w.node_tree.nodes["Background"].inputs["Strength"].default_value = 1.0


def cam(nombre, loc, tgt, lens):
    cd = bpy.data.cameras.new(nombre)
    cd.lens = lens
    o = bpy.data.objects.new(nombre, cd)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


d = H * 2.2
cam("SilFrente", (0, -d, cz), (0, 0, cz), 50)
cam("SilLado", (-d, 0, cz), (0, 0, cz), 50)
cam("SilCabeza", (0, -H * 0.55, zmax - H * 0.075), (0, 0, zmax - H * 0.075), 60)

sc.render.resolution_x, sc.render.resolution_y = 620, 900
sc.render.film_transparent = False
for e in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = e
        break
    except TypeError:
        continue
try:
    sc.view_settings.view_transform = 'Standard'
    sc.eevee.taa_render_samples = 16
except (AttributeError, TypeError):
    pass

for n, f in (("SilFrente", "frente"), ("SilLado", "lado"), ("SilCabeza", "cabeza")):
    sc.camera = bpy.data.objects[n]
    sc.render.filepath = f"{out}/silueta-{f}.png"
    bpy.ops.render.render(write_still=True)
    print("SILUETA", f)
