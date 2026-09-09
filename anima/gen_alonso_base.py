# ÁNIMA — Alonso: base humana (paso 1 de 2)
#
# Herramienta de EDITOR. Genera la malla base sobre la que se construye Alonso.
#   Flipendo --background --python gen_alonso_base.py
# Salida: ~/Flipendo/game/anima/AlonsoBase.blend
#
# POR QUÉ UNA BASE EN VEZ DE GENERARLA:
# una cara atractiva no obedece reglas paramétricas. Depende de topología
# dispuesta en anillos que siguen ojos y boca (lo que permite un parpadeo y una
# sonrisa creíbles) y de miles de decisiones escultóricas. Generarla por código
# se quedaba a medio camino. MPFB2 da esa base ya resuelta.
#
# LICENCIA: MPFB2 es GPLv3 y lo que genera es CC0 — uso comercial permitido,
# incluso en juego cerrado. Nada de material protegido de terceros.

import bpy
import os

OUT = os.path.expanduser("~/Flipendo/game/anima/AlonsoBase.blend")

# Alonso: chico de 15-16 años, delgado, proporción idealizada de héroe juvenil.
# (en MPFB age 0 = bebé, 0.5 = 25 años, 1 = anciano)
MACRO = {
    "MPFB_HUM_gender": 0.82,        # masculino pero aún sin endurecer
    "MPFB_HUM_age": 0.42,           # ~16 años
    "MPFB_HUM_muscle": 0.44,
    "MPFB_HUM_weight": 0.42,        # delgado
    "MPFB_HUM_proportions": 0.78,   # idealizado, no anatómico medio
    "MPFB_HUM_height": 0.44,
    "MPFB_HUM_cupsize": 0.0,
    "MPFB_HUM_firmness": 0.5,
    "MPFB_HUM_caucasian": 1.0,
    "MPFB_HUM_asian": 0.0,
    "MPFB_HUM_african": 0.0,
}

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

sc = bpy.context.scene
sc.name = "AlonsoBase"
sc.MPFB_NH_add_breast = False
sc.MPFB_NH_auto_generate_rigify = False      # el rig se monta en el paso 2
sc.MPFB_NH_load_clothes = False

bpy.ops.mpfb.create_human()
h = bpy.data.objects.get("Human")
assert h is not None, "MPFB no ha creado la base"
h.name = "Alonso_Base"

for k, v in MACRO.items():
    h[k] = v

bpy.context.view_layer.objects.active = h
h.select_set(True)
try:
    bpy.ops.mpfb.refit_human()
    print("[BASE] refit aplicado")
except Exception as e:
    print("[BASE] refit no disponible:", e)

dims = h.dimensions
print(f"[BASE] verts: {len(h.data.vertices)}  alto: {dims.z:.3f} m")
bpy.ops.wm.save_as_mainfile(filepath=OUT)
print("[BASE] guardado:", OUT)
print("[BASE] OK")
