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
#  3. (Implementación, gen_alonso_rig.py) El rig se monta con el OPERADOR OFICIAL de
#     MPFB sobre una malla temporal con los cubos `joint-*` reconstruidos por
#     transferencia de landmarks (montar_rig_mpfb): error máx. 6,1 mm y medio 0,45 mm
#     frente a la deformación analítica, contra 2-8 cm si se copiara el rig de la base
#     sin ajustar. montar_rig_alonso (remapeo por 32 vecinos) se conserva como
#     alternativa sin numpy.
#  4. Los dedos NO se retargetean (falanges de MPFB más cortas y otra convención de
#     ejes: salían como garras); se hornea un puño fijo en hand_r (agarre de la espada)
#     y un puño suave en hand_l en todas las acciones (`fijos` en retarget()).
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


def emparentar_espada(esp, arm, hueso="hand_r", offset=(-0.010, 0.025, 0.0), espejar=True):
    """Espada (origen en el centro del puño, hoja hacia +Y del objeto) agarrada en hand_r.
    Ejes de hand_r en MPFB (medidos): X = dorso de la mano, Y = hacia los dedos,
    Z = lado del pulgar (thumb_01_r·Z = 0,89). En un puño con la hoja saliendo por el
    pulgar, la hoja va a +Z del hueso, el GUARDAMANO (lado -X del objeto, el de los
    nudillos) a +Y del hueso y el ANILLO (+Z del objeto) al dorso, +X del hueso.
    Ese mapa (X_obj→-Y, Y_obj→Z, Z_obj→X) tiene determinante -1: Espada.blend está
    modelada con la quiralidad de la mano IZQUIERDA (probado en puno_m2/n2.png: sin
    espejo, o el anillo cae en la palma o el guardamano mira a la muñeca). Por eso se
    espeja la MALLA en Z (y se invierten las caras) y se usa Z_obj→-X, que ya es una
    rotación propia. La primera versión (rotation_euler +90° X, probada solo con un
    cilindro) dejaba el guardamano hacia la muñeca.
    `offset` en el espacio del hueso (que cuelga de la COLA): 2,5 cm más allá de la
    cola hacia el centro de la palma y 1 cm hacia la palma (-X); el puño de 105 mm
    queda dentro de los dedos cerrados (pose_puno)."""
    if espejar and not esp.get("ESPADA_ESPEJADA"):
        import bmesh
        bm = bmesh.new()
        bm.from_mesh(esp.data)
        for v in bm.verts:
            v.co.z = -v.co.z
        bmesh.ops.reverse_faces(bm, faces=bm.faces)
        bm.to_mesh(esp.data)
        bm.free()
        esp.data.update()
        esp["ESPADA_ESPEJADA"] = 1
    # columnas = imagen de X_obj, Y_obj, Z_obj en el espacio del hueso
    R = Matrix(((0.0, 0.0, -1.0),
                (-1.0, 0.0, 0.0),
                (0.0, 1.0, 0.0)))
    assert abs(R.determinant() - 1.0) < 1e-9
    esp.parent = arm
    esp.parent_type = 'BONE'
    esp.parent_bone = hueso
    esp.matrix_parent_inverse = Matrix.Identity(4)
    esp.matrix_basis = Matrix.Translation(Vector(offset)) @ R.to_4x4()
    esp.rotation_mode = 'QUATERNION'


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


def retarget(src, act_src, arm, nombre, f0=None, f1=None, metodo="b", fijos=None):
    """Hornea `act_src` (de la armadura fuente `src`) en una acción nueva `nombre` de
    `arm`, frames 1..N. metodo "b" = orientación mundo + twist de reposo (el bueno);
    "a" = orientación mundo tal cual (solo para comparar).
    `fijos` = {hueso: Quaternion} en espacio local del hueso (lo que va en
    rotation_quaternion): esos huesos no se retargetean, llevan esa rotación fija en
    todos los frames (puños)."""
    fijos = fijos or {}
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
        if tn is None or tn in fijos:
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
            if tn in fijos:
                q = fijos[tn].copy()
            elif tn in deseado:
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


def retarget_glb(arm, ruta_glb, clips, metodo="b", fijos=None):
    """clips = [(nombre_accion_destino, nombre_clip_quaternius), ...] o, para hornear
    solo un tramo del clip, (nombre, clip, f0, f1) con f0..f1 en frames del clip
    importado (1 = primera clave): el tramo sale como 1..(f1-f0+1). Importa, hornea
    y borra la fuente. Devuelve {nombre: n_frames}."""
    src, nuevos, acts = importar_glb(ruta_glb)
    hecho = {}
    for clip in clips:
        nombre, sname = clip[0], clip[1]
        a = acts.get(sname)
        if a is None:
            print("[RETARGET] no existe el clip", sname)
            continue
        if len(clip) >= 4:
            fr = a.frame_range
            f0 = int(round(fr[0])) + clip[2] - 1
            f1 = int(round(fr[0])) + clip[3] - 1
            act = retarget(src, a, arm, nombre, f0=f0, f1=f1, metodo=metodo, fijos=fijos)
        else:
            act = retarget(src, a, arm, nombre, metodo=metodo, fijos=fijos)
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


# ================================================================ 5. implementación
# (ronda 1 de gen_alonso_rig.py; cifras en dev/noche/informes/anima-rig.md)

def montar_rig_mpfb(al, ruta_base=None, nombre="Alonso_Rig", K=160, ridge=1e-4,
                    mix=None):
    """Rig game_engine de MPFB2 sobre `al` (Alonso) con el OPERADOR OFICIAL
    (bpy.ops.mpfb.add_standard_rig, import_weights) y sin tocar su malla.

    Por qué así: el operador coloca cada extremo de hueso en la media de un grupo de
    vértices `joint-*` (cubos auxiliares, índices >= NBODY de la basemesh de 19.158
    verts). En Alonso esos grupos existen vacíos (gen_alonso_estilo poda los helpers
    antes de deformar) y el operador muere (ZeroDivisionError en rig.py:938). Aquí se
    reconstruyen los helpers EN EL ESPACIO DEFORMADO llevando cada uno con la afín
    local ponderada (IDW) de sus K vértices de cuerpo más cercanos entre la base
    horneada con la misma mezcla de fenotipo y Alonso (misma topología 0..13.379).
    Medido contra la deformación analítica exacta: máx. 6,1 mm (hombros), media
    0,45 mm; K=24 daba 30 mm en joint-head y la Basis sin hornear 50 mm.
    Se monta una malla temporal de 19.158 verts (cuerpo de Alonso + helpers), se lanza
    el operador sobre ella y se traspasan armature, parentesco y pesos (índices < NBODY)
    a Alonso. Devuelve la armadura, con rotation_mode QUATERNION en todos los huesos."""
    import importlib
    import numpy as np
    ruta_base = ruta_base or RUTA_BASE
    # misma mezcla de fenotipo que gen_alonso_estilo.py (paso 1): sin ella no casan
    mix = mix or {"$md-$ca-$ma-$yn": 1.0, "$md-universal-$ma-$yn-$av$mu-$av$wg": 1.0}

    # --- 1. basemesh horneada (cuerpo + helpers): se appendea y se borra
    with bpy.data.libraries.load(ruta_base, link=False) as (src, dst):
        dst.objects = ["Alonso_Base"]
    hb = dst.objects[0]
    mb = hb.data
    kb = mb.shape_keys.key_blocks
    basis = kb[0]
    base = np.zeros((len(mb.vertices), 3))
    for vi in range(len(mb.vertices)):
        co = basis.data[vi].co.copy()
        for k in kb[1:]:
            val = mix.get(k.name, 0.0)
            if val:
                ref = k.relative_key or basis
                co += (k.data[vi].co - ref.data[vi].co) * val
        base[vi] = co[:]
    grupos = {}
    gi = {g.index: g.name for g in hb.vertex_groups
          if g.name.startswith(("joint-", "helper-")) or g.name in ("body", "JointCubes", "HelperGeometry")}
    for v in mb.vertices:
        for gr in v.groups:
            if gr.group in gi:
                grupos.setdefault(gi[gr.group], []).append((v.index, gr.weight))
    assert base.shape[0] == 19158 and max(i for i, _ in grupos["body"]) == NBODY - 1
    bpy.data.objects.remove(hb)
    bpy.data.meshes.remove(mb)

    # --- 2. transferencia de landmarks base -> Alonso
    me = al.data
    assert len(me.vertices) == NBODY, "Alonso ya no tiene la topología de la basemesh"
    alonso = np.array([v.co[:] for v in me.vertices])
    kd = kdtree.KDTree(NBODY)
    for i in range(NBODY):
        kd.insert(Vector(base[i]), i)
    kd.balance()

    def transferir(p):
        res = kd.find_n(Vector(p), K)
        nb = [i for (_, i, _) in res]
        dist = np.array([d for (_, _, d) in res])
        X, Y = base[nb], alonso[nb]
        w = 1.0 / (dist + dist.mean() * 0.5) ** 2
        w /= w.sum()
        c0 = (X * w[:, None]).sum(0)
        c1 = (Y * w[:, None]).sum(0)
        Xc, Yc = X - c0, Y - c1
        A = Xc.T @ (Xc * w[:, None])
        B = Xc.T @ (Yc * w[:, None])
        M = np.linalg.solve(A + ridge * np.trace(A) / 3.0 * np.eye(3), B)
        return c1 + (np.asarray(p) - c0) @ M

    full = np.vstack([alonso, np.array([transferir(base[j]) for j in range(NBODY, base.shape[0])])])
    control = None
    if "ALONSO_L_EYE" in al:
        idx = [i for i, w in grupos["helper-l-eye"] if w > 0.35]
        control = float(np.linalg.norm(full[idx].mean(0) - np.array(al["ALONSO_L_EYE"][:])) * 1000)
        print("[RIG] control ojo izquierdo: %.1f mm respecto a ALONSO_L_EYE" % control)

    # --- 3. malla temporal y operador oficial
    fm = bpy.data.meshes.new("AlonsoFit")
    fm.from_pydata([tuple(c) for c in full], [], [tuple(p.vertices) for p in me.polygons])
    fm.update()
    fit = bpy.data.objects.new("AlonsoFit", fm)
    bpy.context.scene.collection.objects.link(fit)
    for g, mem in grupos.items():
        vg = fit.vertex_groups.new(name=g)
        for i, w in mem:
            vg.add([i], w, 'REPLACE')
    fit.MPFB_GEN_object_type = "Basemesh"        # poll BASEMESH_ACTIVE del operador
    fit.MPFB_GEN_scale_factor = al.MPFB_GEN_scale_factor
    sc = bpy.context.scene
    sc.MPFB_ADR_standard_rig = "game_engine"     # SceneConfigSet, prefijo MPFB_ADR_
    sc.MPFB_ADR_import_weights = True
    for o in bpy.context.view_layer.objects:
        o.select_set(False)
    fit.select_set(True)
    bpy.context.view_layer.objects.active = fit
    # sin esto MpfbOperator se traga las excepciones y devuelve FINISHED sin armature
    importlib.import_module("bl_ext.user_default.mpfb.ui.mpfboperator")._RAISE_EXCEPTIONS = True
    r = bpy.ops.mpfb.add_standard_rig()
    arm = fit.parent
    assert r == {'FINISHED'} and arm and arm.type == 'ARMATURE' and len(arm.data.bones) == 53, (r, arm)
    arm.name = arm.data.name = nombre

    # --- 4. traspaso a Alonso: pesos (índices < NBODY), parentesco, modificador
    huesos = {b.name for b in arm.data.bones}
    for vg in fit.vertex_groups:
        if vg.name not in huesos:
            continue
        dst_g = al.vertex_groups.get(vg.name) or al.vertex_groups.new(name=vg.name)
        for v in fm.vertices:
            if v.index >= NBODY:
                break
            for gr in v.groups:
                if gr.group == vg.index and gr.weight > 0:
                    dst_g.add([v.index], gr.weight, 'REPLACE')
    al.parent = arm
    al.matrix_parent_inverse.identity()
    mod = al.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    al.modifiers.move(len(al.modifiers) - 1, 0)   # antes del Solidify del contorno
    bpy.data.objects.remove(fit)
    bpy.data.meshes.remove(fm)
    for pb in arm.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    arm["ALONSO_RIG_CONTROL_OJO_MM"] = control if control is not None else -1.0
    return arm


DEDOS = ("index", "middle", "ring", "pinky")


def pose_puno(arm, lado="r", curl=(60.0, 70.0, 40.0), pulgar=(35.0, 45.0)):
    """{hueso: Quaternion} de un puño para la mano `lado`, en el espacio local de cada
    hueso (lo que va en rotation_quaternion): cada falange gira `curl[i]` grados sobre
    el eje que lleva su Y (a lo largo del dedo) hacia la PALMA (-X del hueso hand);
    el pulgar se aduce `pulgar[0]` hacia la dirección de los dedos y sus falanges
    se flexionan `pulgar[1]` hacia la palma. Los ejes se calculan con las matrices
    de reposo, así que vale para cualquier ajuste del rig."""
    armd = arm.data

    def L(bn):
        return (arm.matrix_world @ armd.bones[bn].matrix_local).to_3x3()

    Lh = L("hand_" + lado)
    Xh, Yh, Zh = Lh.col[0], Lh.col[1], Lh.col[2]
    palma = -Xh

    def giro(bn, ang, hacia):
        Lb = L(bn)
        eje = Lb.col[1].cross(hacia).normalized()
        return Quaternion(Lb.inverted() @ eje, math.radians(ang))

    q = {}
    for dedo in DEDOS:
        for i, a in zip(("01", "02", "03"), curl):
            q[f"{dedo}_{i}_{lado}"] = giro(f"{dedo}_{i}_{lado}", a, palma)
    q[f"thumb_01_{lado}"] = giro(f"thumb_01_{lado}", pulgar[0], Yh)
    q[f"thumb_02_{lado}"] = giro(f"thumb_02_{lado}", pulgar[1], -Zh + palma * 0.5)
    q[f"thumb_03_{lado}"] = giro(f"thumb_03_{lado}", pulgar[1], -Zh + palma * 0.5)
    return q


def huesos_de(arm):
    return {b.name for b in arm.data.bones}


def vestir(prenda, cuerpo, arm):
    """Deja una prenda (Alonso_Ropa_*) deformándose con el rig: si ya trae grupos de
    hueso con suma ~1 (la extracción de la ropa hereda los pesos del cuerpo) se
    respetan; si no, se transfieren del cuerpo con Data Transfer POLYINTERP_NEAREST
    (exacto en torso y brazos; los únicos errores medidos están en los dedos). El
    modificador solo admite 'ALL' o UN grupo de origen, así que entran todos los grupos
    del cuerpo y luego se borran los que no son hueso. Modificador Armature el primero
    de la pila y parentesco a la armadura. Devuelve (n_verts, min_suma, n_sin_peso)."""
    huesos = huesos_de(arm)
    me = prenda.data
    nombres = {g.index: g.name for g in prenda.vertex_groups}

    def sumas():
        s = [0.0] * len(me.vertices)
        for v in me.vertices:
            for gr in v.groups:
                if nombres.get(gr.group) in huesos:
                    s[v.index] += gr.weight
        return s

    s = sumas() if prenda.vertex_groups else [0.0] * len(me.vertices)
    sin = sum(1 for x in s if x < 0.5)
    if sin > 0:
        for g in list(prenda.vertex_groups):
            prenda.vertex_groups.remove(g)
        for h in huesos:
            prenda.vertex_groups.new(name=h)
        ocultos = []
        for m in cuerpo.modifiers:             # el origen se evalúa CON modificadores:
            if m.show_viewport:                # que no vea el casco del contorno
                m.show_viewport = False
                ocultos.append(m)
        dt = prenda.modifiers.new("PesosDelCuerpo", 'DATA_TRANSFER')
        dt.object = cuerpo
        dt.use_vert_data = True
        dt.data_types_verts = {'VGROUP_WEIGHTS'}
        dt.vert_mapping = 'POLYINTERP_NEAREST'
        dt.layers_vgroup_select_src = 'ALL'
        dt.layers_vgroup_select_dst = 'NAME'
        bpy.context.view_layer.objects.active = prenda
        bpy.ops.object.modifier_apply(modifier=dt.name)
        for m in ocultos:
            m.show_viewport = True
        for g in list(prenda.vertex_groups):
            if g.name not in huesos:
                prenda.vertex_groups.remove(g)
        nombres = {g.index: g.name for g in prenda.vertex_groups}
        s = sumas()
    mod = prenda.modifiers.get("Armature") or prenda.modifiers.new("Armature", 'ARMATURE')
    mod.object = arm
    prenda.modifiers.move([m.name for m in prenda.modifiers].index(mod.name), 0)
    prenda.parent = arm
    prenda.matrix_parent_inverse.identity()
    return len(me.vertices), (min(s) if s else 0.0), sum(1 for x in s if x < 1e-6)


def crear_player(arm, radio=0.35, alto=1.75, step=0.4, nombre="Player"):
    """El Player del contrato: física CHARACTER con cápsula radio 0,35 y alto 1,75,
    step 0,4, propiedad de juego fl_component=PlayerController, y el rig colgando con
    los pies en la base de la cápsula. NO es un EMPTY: BKE_object_boundbox_get devuelve
    nullopt para OB_EMPTY y CcdPhysicsEnvironment.cpp (bloque «Get bounds information»)
    cae entonces a extents 1,0 → cápsula de radio 1 m y alto 0. La cápsula sale de la
    caja envolvente, así que el Player es una MALLA de 8 vértices sin caras (no se
    dibuja): radio = max(semiX, semiY), alto = 2·semiZ."""
    pm = bpy.data.meshes.new(nombre + "_Capsula")
    h = alto / 2.0
    pm.from_pydata([(x, y, z) for x in (-radio, radio) for y in (-radio, radio) for z in (-h, h)], [], [])
    pm.update()
    player = bpy.data.objects.new(nombre, pm)
    bpy.context.scene.collection.objects.link(player)
    player.location = (0.0, 0.0, h)
    g = player.game
    g.physics_type = 'CHARACTER'
    g.use_collision_bounds = True
    g.collision_bounds_type = 'CAPSULE'
    g.radius = radio
    g.step_height = step
    g.use_actor = True
    propiedad_de_juego(player, "fl_component", "PlayerController")
    arm.parent = player
    arm.matrix_parent_inverse.identity()
    arm.location = (0.0, 0.0, -h)
    return player
