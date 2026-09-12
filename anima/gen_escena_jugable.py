# gen_escena_jugable.py — INTEGRACIÓN: Alonso jugable dentro del charco.
#
# Entradas: Charco.blend (gen_charco.py) y AlonsoJugable.blend (gen_alonso_rig.py,
# que a su vez viene de gen_alonso_ropa.py <- gen_alonso.py). Salida: EscenaCharco.blend.
#
# Qué hace: quita el maniquí provisional (Player + Player_Capsula) del charco y appendea
# la jerarquía Player -> Alonso_Rig -> mallas/espada de AlonsoJugable.blend, junto con
# TODAS sus acciones. Las acciones hay que traerlas aparte: appendear un objeto solo
# arrastra lo que referencia, y un rig en reposo no referencia ninguna. Sin ellas el
# motor no encuentra "Idle:1:75" y Alonso se queda en T-pose.
#
# Cero Python en el .blend: aquí solo hay datos y propiedades de juego; el gameplay es
# C++ (fl_component). Determinista.
#
# Trampa medida por el carril ESCENA (informes/anima-escena-tecnica.md §0.2): el Player
# solo respeta scene.camera si el visor 3D se guardó EN VISTA DE CÁMARA; si no, fabrica
# __default__cam__ y la partida arranca desde otro sitio. Por eso se fuerzan los visores.
import os
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
CHARCO = os.path.join(HERE, "Charco.blend")
JUGABLE = os.path.join(HERE, "AlonsoJugable.blend")
OUT = os.path.join(HERE, "EscenaCharco.blend")

bpy.ops.wm.open_mainfile(filepath=CHARCO)
sc = bpy.context.scene

# --- 1. fuera el maniquí ----------------------------------------------------------
viejo = sc.objects.get("Player")
punto = tuple(viejo.location) if viejo else (0.0, -30.0, 0.92)
rot = tuple(viejo.rotation_euler) if viejo else (0.0, 0.0, 0.0)
for nombre in ("Player_Capsula", "Player"):
    o = bpy.data.objects.get(nombre)
    if o:
        bpy.data.objects.remove(o, do_unlink=True)
print(f"[INT] maniquí retirado; punto de partida {tuple(round(v, 2) for v in punto)}")

# --- 2. acciones primero (fake user para que sobrevivan al guardado) ----------------
with bpy.data.libraries.load(JUGABLE, link=False) as (src, dst):
    dst.actions = list(src.actions)
    nombres_obj = list(src.objects)
for a in bpy.data.actions:
    a.use_fake_user = True
print(f"[INT] acciones: {sorted(a.name for a in bpy.data.actions)}")

# --- 3. la jerarquía del jugador ----------------------------------------------------
quiero = [n for n in nombres_obj
          if n == "Player" or n.startswith("Alonso") or n == "Espada"]
with bpy.data.libraries.load(JUGABLE, link=False) as (src, dst):
    dst.objects = quiero
nuevos = [o for o in dst.objects if o is not None]
for o in nuevos:
    if o.name not in sc.collection.objects:
        sc.collection.objects.link(o)
player = bpy.data.objects.get("Player")
assert player is not None, "AlonsoJugable.blend no trae Player"
player.location = punto
player.rotation_euler = rot
print(f"[INT] jugador: {len(nuevos)} objetos; raíz {player.name} "
      f"({player.game.physics_type}, cápsula r={player.game.radius:.2f})")

rig = bpy.data.objects.get("Alonso_Rig")
assert rig is not None and rig.parent == player, "Alonso_Rig no cuelga de Player"
props = {p.name: p.value for p in rig.game.properties}
faltan = [k for k in ("fl_rig", "fl_anim_idle", "fl_anim_walk", "fl_anim_run",
                      "fl_anim_attack1", "fl_anim_attack2", "fl_anim_attack3")
          if k not in props]
assert not faltan, f"al rig le faltan propiedades: {faltan}"
for k, v in props.items():
    if k.startswith("fl_anim_"):
        accion = v.split(":")[0]
        assert accion in bpy.data.actions, f"{k} apunta a '{accion}', que no existe"
print(f"[INT] rig: {len(rig.data.bones)} huesos, {len([k for k in props if k.startswith('fl_anim_')])} animaciones enlazadas")

# --- 4. cámara y visores -------------------------------------------------------------
# En la escena jugable solo puede haber UNA cámara. Medido: con CamVision (la de los
# renders del editor) presente, el Player pintaba desde ella —fija, a nivel, en el punto
# de partida— y no desde GameCamera: Alonso salía diminuto y cortado por el borde
# inferior y el horizonte a media pantalla, aunque scene.camera fuera GameCamera y el
# ThirdPersonCamera se activara. Fuera todo lo que no sea GameCamera.
cam = bpy.data.objects.get("GameCamera")
assert cam is not None and cam.type == 'CAMERA'
for o in [o for o in sc.objects if o.type == 'CAMERA' and o is not cam]:
    print(f"[INT] cámara de render retirada: {o.name}")
    bpy.data.objects.remove(o, do_unlink=True)
sc.camera = cam
for scr in bpy.data.screens:
    for area in scr.areas:
        if area.type == 'VIEW_3D':
            for sp in area.spaces:
                if sp.type == 'VIEW_3D':
                    sp.camera = cam
                    sp.region_3d.view_perspective = 'CAMERA'
sc.render.fps = 30

# --- 5. comprobaciones de doctrina ----------------------------------------------------
assert len(bpy.data.texts) == 0, "hay bloques de texto: cero Python en el .blend"
for o in sc.objects:
    assert not o.game.controllers, f"{o.name} tiene controladores"
    assert not o.game.sensors, f"{o.name} tiene sensores"

bpy.ops.wm.save_as_mainfile(filepath=OUT, compress=True)
print(f"[INT] guardado {OUT}: {len(sc.objects)} objetos, {len(bpy.data.actions)} acciones")
print("[INT] OK")
