# ÁNIMA — Alonso jugable: rig, animaciones, espada y Player (carril RIG)
#
#   cd ~/Flipendo/game/anima && Flipendo --background --python gen_alonso_rig.py [-- salida.blend]
#
# Entrada: AlonsoVestido.blend (carril ROPA) si existe y carga sin error; si no,
# Alonso.blend (carril PELO). Salida: AlonsoJugable.blend con la jerarquía del contrato
# (dev/noche/NOCHE-ANIMA.md, «Convención de jerarquía y animación»):
#
#   Player          MALLA de 8 vértices sin caras (no se dibuja), física CHARACTER,
#                   cápsula r 0,35 alto 1,75 step 0,4, fl_component=PlayerController.
#                   No es un EMPTY porque el motor saca la cápsula de la caja envolvente
#                   y un EMPTY no tiene (BKE_object_boundbox_get → nullopt → extents 1,0:
#                   cápsula de radio 1 m). Ver anima_retarget.crear_player().
#    └─ Alonso_Rig  ARMATURE game_engine de MPFB2 (53 huesos, nombres UE), con los pesos
#                   oficiales, fl_rig=1 y fl_anim_*=Accion:inicio:fin como PROPIEDADES DE
#                   JUEGO (ob.game.properties; una propiedad ID no llega al motor).
#        ├─ Alonso        modificador Armature (primero de la pila, antes del Solidify)
#        ├─ Alonso_Ropa_* Armature con pesos heredados o transferidos del cuerpo
#        ├─ Alonso_Pelo   bone parent a head
#        ├─ Alonso_Ojos   bone parent a head
#        └─ Espada        bone parent a hand_r, puño dentro de los dedos cerrados
#
# Acciones (30 fps, todas desde el frame 1; clips CC0 de Quaternius retargeteados con
# anima_retarget, método «b»): Idle, IdleEspada, Andar, Correr, Ataque1, Ataque2,
# Ataque3, Salto, SaltoAire, SaltoCaida, Golpe. Los tres ataques son los tres golpes de
# Sword_Regular_Combo cortados por el pico de velocidad de hand_r (frames 9, 23 y 48
# del combo) para que el impacto caiga en la fase «active» del HitSpec de
# FL_ArpgCore.hpp una vez que el C++ escala la velocidad al total de cada golpe.
#
# Cero Python en el .blend: ni textos, ni bricks. Cifras y evidencias:
# dev/noche/informes/anima-rig.md.

import bpy
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.modules.pop("anima_retarget", None)
import anima_retarget as R                                          # noqa: E402

REF = os.path.join(HERE, "..", "referencias", "quaternius-cc0", "animaciones")
ENTRADAS = ("AlonsoVestido.blend", "Alonso.blend")
ESPADA = os.path.join(HERE, "Espada.blend")
args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
OUT = args[0] if args else os.path.join(HERE, "AlonsoJugable.blend")

# Tramos del combo (frames del clip importado, 1 = primera clave) y propiedades.
# Impacto (pico de velocidad de hand_r): combo f9 → Ataque1 f5 de 13 (0,17 s de 0,52),
# f23 → Ataque2 f6 de 14 (0,19 s de 0,50), f48 → Ataque3 f12 de 34 (0,28 s de 0,85).
CLIPS_UAL1 = [("Idle", "Idle_Loop"), ("IdleEspada", "Sword_Idle"), ("Andar", "Walk_Loop"),
              ("Correr", "Jog_Fwd_Loop"), ("Salto", "Jump_Start"), ("SaltoAire", "Jump_Loop"),
              ("SaltoCaida", "Jump_Land"), ("Golpe", "Hit_Chest")]
CLIPS_UAL2 = [("Ataque1", "Sword_Regular_Combo", 5, 17),
              ("Ataque2", "Sword_Regular_Combo", 18, 31),
              ("Ataque3", "Sword_Regular_Combo", 37, 70)]
PROPIEDADES = {
    "fl_rig": "1",
    "fl_anim_idle": "Idle:1:75",        # bucle: el frame 76 es igual al 1
    "fl_anim_walk": "Andar:1:40",
    "fl_anim_run": "Correr:1:28",
    "fl_anim_attack1": "Ataque1:1:13",  # tajo 1 del combo (horizontal, de derecha a izquierda)
    "fl_anim_attack2": "Ataque2:1:14",  # tajo 2 (de vuelta, diagonal)
    "fl_anim_attack3": "Ataque3:1:34",  # tajo grande con giro
    "fl_anim_jump": "Salto:1:41",
    "fl_anim_hit": "Golpe:1:11",
}


def log(*a):
    print("[RIG]", *a)


# ------------------------------------------------------------------ 1. entrada
def abrir_entrada():
    for nombre in ENTRADAS:
        ruta = os.path.join(HERE, nombre)
        if not os.path.exists(ruta):
            continue
        try:
            bpy.ops.wm.open_mainfile(filepath=ruta)
            al = bpy.data.objects["Alonso"]
            assert al.type == 'MESH' and len(al.data.vertices) == R.NBODY, "Alonso sin la topología base"
            assert not bpy.data.texts, "la entrada trae textos Python"
            log("entrada:", nombre)
            return al, nombre
        except Exception as e:                                       # noqa: BLE001
            log("no vale", nombre, "->", repr(e))
    raise SystemExit("[RIG] sin entrada válida")


al, entrada = abrir_entrada()
sc = bpy.context.scene
sc.render.fps = 30                 # ANTES de importar los glb: el importador muestrea al fps de la escena
sc.render.fps_base = 1.0
for o in bpy.data.objects:
    if o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)

# ------------------------------------------------------------------ 2. rig
arm = R.montar_rig_mpfb(al)
huesos = R.huesos_de(arm)
log("rig", arm.name, len(arm.data.bones), "huesos; control ojo %.1f mm" % arm["ALONSO_RIG_CONTROL_OJO_MM"])

# ------------------------------------------------------------------ 3. ropa, pelo, ojos
ropa = [o for o in bpy.data.objects if o.type == 'MESH' and o.name.startswith("Alonso_Ropa_")]
for prenda in ropa:
    n, smin, sin = R.vestir(prenda, al, arm)
    log("ropa %-22s %5d verts, suma de pesos mín %.3f, sin peso %d" % (prenda.name, n, smin, sin))
for n in ("Alonso_Pelo", "Alonso_Ojos"):
    if n in bpy.data.objects:
        R.emparentar_a_hueso(bpy.data.objects[n], arm, "head")
        log(n, "-> hueso head")

# ------------------------------------------------------------------ 4. espada
esp = None
if os.path.exists(ESPADA):
    with bpy.data.libraries.load(ESPADA, link=False) as (src, dst):
        dst.objects = ["Espada"]
    esp = dst.objects[0]
    sc.collection.objects.link(esp)
    R.emparentar_espada(esp, arm)
    log("Espada -> hand_r (malla espejada: quiralidad de mano derecha)")
else:
    log("sin Espada.blend: el personaje va desarmado")

# ------------------------------------------------------------------ 5. acciones
# Puño de agarre en la derecha; puño suave en la izquierda. Los dedos no se retargetean.
fijos = {}
fijos.update(R.pose_puno(arm, "r", curl=(60.0, 70.0, 40.0), pulgar=(35.0, 45.0)))
fijos.update(R.pose_puno(arm, "l", curl=(25.0, 30.0, 20.0), pulgar=(15.0, 20.0)))
hecho = {}
hecho.update(R.retarget_glb(arm, os.path.join(REF, R.GLB_UAL1), CLIPS_UAL1, fijos=fijos))
hecho.update(R.retarget_glb(arm, os.path.join(REF, R.GLB_UAL2), CLIPS_UAL2, fijos=fijos))
for k, v in PROPIEDADES.items():
    R.propiedad_de_juego(arm, k, v)
    if k.startswith("fl_anim_"):
        nombre, a, b = v.split(":")
        assert nombre in hecho and int(b) <= hecho[nombre], (k, v, hecho.get(nombre))

# ------------------------------------------------------------------ 6. Player y escena
player = R.crear_player(arm)
arm.animation_data.action = bpy.data.actions["Idle"]
sc.frame_start, sc.frame_end = 1, 75
sc.frame_set(1)
bpy.data.orphans_purge(do_recursive=True)

# ------------------------------------------------------------------ 7. comprobaciones
assert len(bpy.data.texts) == 0, "hay textos en el blend"
for o in bpy.data.objects:
    assert not o.game.controllers and not o.game.sensors and not o.game.actuators, o.name
assert player.name == "Player" and player.game.physics_type == 'CHARACTER'
assert al.parent == arm and al.modifiers[0].type == 'ARMATURE'
assert all(o.parent == player for o in (arm,)) and all(o.parent == arm for o in ropa)
suma = [0.0] * R.NBODY
nombres = {g.index: g.name for g in al.vertex_groups}
for v in al.data.vertices:
    for gr in v.groups:
        if nombres[gr.group] in huesos:
            suma[v.index] += gr.weight
log("pesos del cuerpo: suma mín %.3f máx %.3f, sin peso %d" % (min(suma), max(suma), sum(1 for s in suma if s < 1e-6)))
log("acciones:", ", ".join("%s 1..%d" % (k, v) for k, v in sorted(hecho.items())))
log("propiedades de juego:", {p.name: p.value for p in arm.game.properties})
log("objetos:", [(o.name, o.type, o.parent.name if o.parent else None, o.parent_bone or "") for o in bpy.data.objects])

bpy.ops.wm.save_as_mainfile(filepath=OUT)
log("guardado", OUT, "desde", entrada)
