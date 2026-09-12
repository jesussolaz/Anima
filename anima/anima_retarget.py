# ÁNIMA — rig game_engine de MPFB2 sobre Alonso y retarget de clips CC0 de Quaternius
#
# Herramienta de EDITOR (bpy). La importa gen_alonso_rig.py; no va en el juego.
# Investigación y cifras: dev/noche/informes/anima-rig-animaciones.md y
# conocimiento/16-animacion-y-retarget.md.
#
# QUÉ RESUELVE
#  1. Alonso.blend ya no tiene los cubos `joint-*` de MakeHuman (el paso estilo los
#     borró junto con los helpers), así que `mpfb.add_standard_rig` divide por cero.
#     Se ajusta el rig en AlonsoBase.blend (que sí los tiene) y se traslada a Alonso
#     REMAPEANDO cada cabeza/cola de hueso por sus 32 vértices de cuerpo más cercanos:
#     los 13.380 vértices del cuerpo conservan índice entre ambos ficheros, pero se
#     han movido de 2 a 8 cm (cabeza ×1,34, hombros más anchos, altura renormalizada),
#     así que copiar el rig tal cual dejaba las rodillas y los hombros fuera de sitio.
#  2. El esqueleto de Quaternius está en T y el de MPFB en A con codos doblados, y
#     los ejes locales no coinciden (muslo: 26° de giro; `ball`: 180°). Copiar la
#     rotación en espacio mundo tal cual (método «a») deja los pies girados y la
#     palma medio vuelta; aquí se copia la orientación mundo y se le añade SOLO la
#     parte de giro sobre el eje Y (twist) de la diferencia de reposo (método «b»).
#     Con eso el T-pose sale en T con las palmas hacia abajo y el ciclo de marcha
#     deja los pies a ±1,4 cm del suelo.
#
# CONVENCIÓN DE FRAMES: cada acción horneada empieza en el frame 1. Un bucle de N
# frames del glTF (0..N) se hornea como 1..N+1 y el frame N+1 es igual al 1: para el
# motor se declara "Accion:1:N" y el salto de N a 1 es limpio.

import bpy
import math
from mathutils import Vector, Matrix, Quaternion, kdtree

NBODY = 13380          # vértices del cuerpo de la base MakeHuman (los helpers van después)
FPS = 30               # todos los clips de Quaternius están muestreados a 30 fps
K_VECINOS = 32         # vértices con que se remapea cada articulación

RUTA_BASE = bpy.path.abspath("//AlonsoBase.blend") if bpy.data.filepath else \
    "/Users/jesussolaz/Flipendo/game/anima/AlonsoBase.blend"


# --------------------------------------------------------------------- 1. rig en la base
def ajustar_rig_en_base(ruta_base=None, nombre_rig="game_engine"):
    """Trae Alonso_Base de AlonsoBase.blend, le ajusta el rig MPFB y devuelve un dict
    {"bones": {nombre: {parent, head, tail, matrix_local, roll}}, "weights": {hueso: [[idx, w]]}}
    en coordenadas de mundo. Borra lo que ha traído. Los pesos solo de vértices < NBODY."""
    ruta_base = ruta_base or RUTA_BASE
    with bpy.data.libraries.load(ruta_base, link=False) as (src, dst):
        dst.objects = ["Alonso_Base"]
    base = dst.objects[0]
    bpy.context.scene.collection.objects.link(base)
    from bl_ext.user_default.mpfb.services import HumanService
    arm = HumanService.add_builtin_rig(base, nombre_rig, import_weights=True)
    bpy.context.view_layer.update()
    datos = {}
    for b in arm.data.bones:
        datos[b.name] = {
            "parent": b.parent.name if b.parent else "",
            "head": list(arm.matrix_world @ b.head_local),
            "tail": list(arm.matrix_world @ b.tail_local),
            "matrix_local": [list(r) for r in (arm.matrix_world @ b.matrix_local)],
        }
    pesos = {b.name: [] for b in arm.data.bones}
    for v in base.data.vertices:
        if v.index >= NBODY:
            continue
        for ge in v.groups:
            g = base.vertex_groups[ge.group].name
            if g in pesos:
                pesos[g].append([v.index, ge.weight])
    for ob in (base, arm):
        me = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if isinstance(me, bpy.types.Mesh):
            bpy.data.meshes.remove(me)
        else:
            bpy.data.armatures.remove(me)
    return {"bones": datos, "weights": pesos}


# ------------------------------------------------------------- 2. rig remapeado en Alonso
def montar_rig_alonso(al, base, nombre="Alonso_Rig", ruta_base=None):
    """Crea la armadura `nombre` sobre la malla `al` (Alonso) a partir del ajuste en la
    base, remapeando articulaciones por vértices vecinos, y le pone pesos y modificador.
    Devuelve el objeto armadura. `base` es el dict de ajustar_rig_en_base()."""
    ruta_base = ruta_base or RUTA_BASE
    with bpy.data.libraries.load(ruta_base, link=False) as (src, dst):
        dst.objects = ["Alonso_Base"]
    bob = dst.objects[0]
    bco = [bob.data.vertices[i].co.copy() for i in range(NBODY)]
    aco = [al.data.vertices[i].co.copy() for i in range(NBODY)]
    me = bob.data
    bpy.data.objects.remove(bob, do_unlink=True)
    bpy.data.meshes.remove(me)

    kd = kdtree.KDTree(NBODY)
    for i, c in enumerate(bco):
        kd.insert(c, i)
    kd.balance()

    def remap(p):
        # posición = media de los mismos vértices en Alonso + el desplazamiento que
        # tenía respecto a su media en la base, escalado por la dispersión local
        p = Vector(p)
        idx = [i for _, i, _ in kd.find_n(p, K_VECINOS)]
        mb = sum((bco[i] for i in idx), Vector()) / K_VECINOS
        ma = sum((aco[i] for i in idx), Vector()) / K_VECINOS
        sb = sum((bco[i] - mb).length for i in idx) / K_VECINOS
        sa = sum((aco[i] - ma).length for i in idx) / K_VECINOS
        return ma + (p - mb) * (sa / sb if sb > 1e-9 else 1.0)

    armd = bpy.data.armatures.new(nombre)
    arm = bpy.data.objects.new(nombre, armd)
    bpy.context.scene.collection.objects.link(arm)
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode='EDIT')
    orden = orden_jerarquico(base["bones"])
    for n in orden:
        v = base["bones"][n]
        eb = armd.edit_bones.new(n)
        if n == "Root":
            eb.head, eb.tail, eb.roll = (0, 0, 0), (0, 0.15, 0), 0.0
        else:
            eb.head = remap(v["head"])
            eb.tail = remap(v["tail"])
            # el roll se conserva alineando el eje Z del hueso con el que tenía en la base
            M = v["matrix_local"]
            eb.align_roll(Vector((M[0][2], M[1][2], M[2][2])))
        if v["parent"]:
            eb.parent = armd.edit_bones[v["parent"]]
            eb.use_connect = False
    bpy.ops.object.mode_set(mode='OBJECT')

    for n, lst in base["weights"].items():
        if n not in armd.bones or not lst:
            continue
        vg = al.vertex_groups.get(n) or al.vertex_groups.new(name=n)
        for i, w in lst:
            vg.add([i], w, 'REPLACE')
    mod = al.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    # el Armature va el PRIMERO: el Solidify del contorno debe deformarse con la piel
    al.modifiers.move(len(al.modifiers) - 1, 0)
    al.parent = arm
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    return arm


def orden_jerarquico(bones, raiz="Root"):
    orden = []

    def rec(n):
        orden.append(n)
        for c, v in bones.items():
            if v["parent"] == n:
                rec(c)
    rec(raiz)
    return orden


def emparentar_a_hueso(ob, arm, hueso):
    """Emparenta `ob` al hueso conservando su transformación de mundo (pelo, ojos)."""
    b = arm.data.bones[hueso]
    mw = ob.matrix_world.copy()
    ob.parent = arm
    ob.parent_type = 'BONE'
    ob.parent_bone = hueso
    # un hijo de hueso cuelga de la COLA del hueso con los ejes locales del hueso
    ob.matrix_parent_inverse = (arm.matrix_world @ b.matrix_local @ Matrix.Translation((0, b.length, 0))).inverted()
    ob.matrix_world = mw


def emparentar_espada(esp, arm):
    """Espada con origen en la empuñadura y hoja hacia +Y del objeto, en hand_r.
    Ejes de hand_r en MPFB (medidos): X = dorso de la mano, Y = hacia los dedos,
    Z = lado del pulgar (pulgar·Z = 0,89). La hoja de una espada agarrada va por el
    pulgar, así que +Y del objeto -> +Z del hueso: giro de +90° sobre X local. La
    empuñadura se pone 2,5 cm más allá de la cola (centro de la palma; el hueso mide
    solo 3,5 cm desde la muñeca) y 1 cm hacia la palma (-X)."""
    esp.parent = arm
    esp.parent_type = 'BONE'
    esp.parent_bone = "hand_r"
    esp.matrix_parent_inverse = Matrix.Identity(4)
    esp.rotation_mode = 'XYZ'
    esp.rotation_euler = (math.pi / 2, 0.0, 0.0)
    esp.location = (-0.010, 0.025, 0.0)


# ---------------------------------------------------------------------- 3. retarget
MAPA_NOMBRES = {"Head": "head", "root": None}


def _nombre_destino(n, armd):
    if n in MAPA_NOMBRES:
        return MAPA_NOMBRES[n]
    if n.endswith("_leaf_l") or n.endswith("_leaf_r"):
        return None
    return n if n in armd.bones else None


def _twist_y(q):
    """Parte de giro sobre Y local de un cuaternión (descomposición swing-twist)."""
    t = Quaternion((q.w, 0.0, q.y, 0.0))
    return t.normalized() if t.magnitude > 1e-9 else Quaternion()


def importar_glb(ruta):
    """Importa un .glb de Quaternius. Devuelve (armadura, objetos_nuevos, {nombre: acción}).
    La escena debe estar a 30 fps ANTES de importar: el importador muestrea los tiempos
    en segundos del glTF al fps de la escena (a 24 fps un Walk de 40 frames sale de 32)."""
    assert bpy.context.scene.render.fps == FPS, "pon scene.render.fps = 30 antes de importar"
    antes = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=ruta)
    nuevos = [o for o in bpy.data.objects if o not in antes]
    src = [o for o in nuevos if o.type == 'ARMATURE'][0]
    pistas = [t.name for t in src.animation_data.nla_tracks]
    acts = {}
    for t in src.animation_data.nla_tracks:
        for s in t.strips:
            acts[t.name] = s.action
    for t in list(src.animation_data.nla_tracks):
        src.animation_data.nla_tracks.remove(t)
    return src, nuevos, acts


def retarget(src, act_src, arm, nombre, f0=None, f1=None, metodo="b"):
    """Hornea `act_src` (de la armadura fuente `src`) en una acción nueva `nombre` de
    `arm`, frames 1..N. metodo "b" = orientación mundo + twist de reposo (el bueno);
    "a" = orientación mundo tal cual (solo para comparar)."""
    sc = bpy.context.scene
    armd = arm.data
    fr = act_src.frame_range
    a = int(round(fr[0])) if f0 is None else f0
    b = int(round(fr[1])) if f1 is None else f1
    src.animation_data.action = act_src
    if not arm.animation_data:
        arm.animation_data_create()
    act = bpy.data.actions.new(nombre)
    arm.animation_data.action = act
    orden = orden_jerarquico({bn.name: {"parent": bn.parent.name if bn.parent else ""} for bn in armd.bones})

    pares = []
    for sb in src.data.bones:
        tn = _nombre_destino(sb.name, armd)
        if tn is None:
            continue
        Rs = (src.matrix_world @ sb.matrix_local).to_3x3()
        Rt = (arm.matrix_world @ armd.bones[tn].matrix_local).to_3x3()
        Q = (Rs.inverted() @ Rt).to_quaternion()
        off = _twist_y(Q) if metodo == "b" else Quaternion()
        pares.append((sb.name, tn, off.to_matrix()))

    # la pelvis se traslada escalando por la altura de cadera (Quaternius 0,917 m;
    # Alonso 0,855 m): así los pies pisan el suelo en vez de hundirse o flotar
    s_pelvis = src.data.bones["pelvis"]
    t_pelvis = armd.bones["pelvis"]
    ratio = (arm.matrix_world @ t_pelvis.head_local).z / (src.matrix_world @ s_pelvis.head_local).z
    s_rest_pelvis = src.matrix_world @ s_pelvis.head_local

    for f in range(a, b + 1):
        sc.frame_set(f)
        Ps = {sb.name: (src.matrix_world @ src.pose.bones[sb.name].matrix) for sb in src.data.bones}
        deseado = {tn: Ps[sn].to_3x3() @ off for sn, tn, off in pares}
        dp = (Ps["pelvis"].translation - s_rest_pelvis) * ratio
        pose = {}
        for tn in orden:
            pb = arm.pose.bones[tn]
            bn = armd.bones[tn]
            if bn.parent:
                Mpre = pose[bn.parent.name] @ bn.parent.matrix_local.inverted() @ bn.matrix_local
            else:
                Mpre = arm.matrix_world @ bn.matrix_local
            if tn in deseado:
                q = (Mpre.to_3x3().inverted() @ deseado[tn]).to_quaternion().normalized()
            else:
                q = Quaternion()
            loc = Vector((0, 0, 0))
            if tn == "pelvis":
                loc = Mpre.to_3x3().inverted() @ dp
            pose[tn] = Mpre @ Matrix.Translation(loc) @ q.to_matrix().to_4x4()
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f - a + 1)
            if tn == "pelvis":
                pb.location = loc
                pb.keyframe_insert("location", frame=f - a + 1)
    for fc in act.fcurves:
        for kp in fc.keyframe_points:
            kp.interpolation = 'LINEAR'
    act.use_fake_user = True
    return act


def retarget_glb(arm, ruta_glb, clips, metodo="b"):
    """clips = [(nombre_accion_destino, nombre_clip_quaternius), ...]. Importa, hornea
    y borra la fuente. Devuelve {nombre: n_frames}."""
    src, nuevos, acts = importar_glb(ruta_glb)
    hecho = {}
    for nombre, sname in clips:
        a = acts.get(sname)
        if a is None:
            print("[RETARGET] no existe el clip", sname)
            continue
        act = retarget(src, a, arm, nombre, metodo=metodo)
        hecho[nombre] = int(act.frame_range[1])
        print("[RETARGET] %-12s <- %-22s frames 1..%d (%.2f s)" % (nombre, sname, hecho[nombre], hecho[nombre] / FPS))
    for o in nuevos:
        bpy.data.objects.remove(o, do_unlink=True)
    for a in list(bpy.data.actions):
        if a.users == 0 and not a.use_fake_user:
            bpy.data.actions.remove(a)
    return hecho


def propiedad_de_juego(ob, nombre, valor):
    """Propiedad de JUEGO (ob.game.properties), que es lo que convierte
    BL_ConvertProperties.cpp y lee FL_PlayerController con GetProperty(). Una propiedad
    ID normal (ob["x"]) NO llega al motor: ese fue el primer error de esta herramienta."""
    if nombre not in ob.game.properties:
        bpy.context.view_layer.objects.active = ob
        bpy.ops.object.game_property_new(type='STRING', name=nombre)
    ob.game.properties[nombre].value = str(valor)


def aplicar_propiedades(arm):
    for k, v in PROPIEDADES.items():
        propiedad_de_juego(arm, k, v)


# ----------------------------------------------------- 4. clips elegidos y propiedades
# Rutas relativas a game/referencias/quaternius-cc0/animaciones/
GLB_UAL1 = "UAL1_Standard.glb"
GLB_UAL2 = "UAL2_Standard.glb"

CLIPS_UAL1 = [("Idle", "Idle_Loop"), ("IdleEspada", "Sword_Idle"), ("Andar", "Walk_Loop"),
              ("Correr", "Jog_Fwd_Loop"), ("Esprintar", "Sprint_Loop"), ("Salto", "Jump_Start"),
              ("SaltoAire", "Jump_Loop"), ("SaltoCaida", "Jump_Land"), ("Golpe", "Hit_Chest"),
              ("Muerte", "Death01"), ("Voltereta", "Roll")]
CLIPS_UAL2 = [("AtaqueCombo", "Sword_Regular_Combo"), ("Bloqueo", "Sword_Block"),
              ("GolpeAtras", "Hit_Knockback")]

# Lo que lee FL_PlayerController (Accion:inicio:fin). Ver el informe para el porqué de
# cada corte: el frame de impacto (pico de velocidad de hand_r) tiene que caer en la
# fase «active» del HitSpec de FL_ArpgCore.hpp una vez que el C++ escala la velocidad.
PROPIEDADES = {
    "fl_rig": "1",
    "fl_anim_idle": "Idle:1:75",             # Idle_Loop, bucle limpio (frame 76 = 1)
    "fl_anim_walk": "Andar:1:40",            # Walk_Loop 1,33 s
    "fl_anim_run": "Correr:1:28",            # Jog_Fwd_Loop 0,93 s, 7 frames de vuelo
    "fl_anim_attack1": "AtaqueCombo:5:17",   # impacto en el frame 9  -> 31 % -> 0,16 s de 0,52
    "fl_anim_attack2": "AtaqueCombo:18:31",  # impacto en el frame 23 -> 36 % -> 0,18 s de 0,50
    "fl_anim_attack3": "AtaqueCombo:37:70",  # impacto en el frame 48 -> 33 % -> 0,28 s de 0,85
    "fl_anim_jump": "Salto:1:41",            # Jump_Start: agacharse (f1-8) y encoger piernas
    "fl_anim_hit": "Golpe:1:11",             # Hit_Chest 0,37 s
}
