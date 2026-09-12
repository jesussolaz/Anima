# ÁNIMA — medir la silueta del PELO contra el cráneo (frontal y perfil)
#
#   Flipendo --background Alonso.blend --python herramientas/medir_silueta_pelo.py -- <dir_salida> [prom_min_%]
#
# Renderiza la cabeza en negro sobre blanco DOS veces (con pelo y sin pelo) con
# la misma cámara que prueba_silueta.py (SilCabeza) y una de perfil a la misma
# distancia, y compara las dos siluetas con un barrido polar desde el centro de
# los ojos: radio del pelo menos radio del cráneo por grado = capa de pelo en
# mm; máximos locales del radio del pelo = puntas, con su prominencia (cuánto
# sobresalen del valle vecino). Es el mismo método que se usó para medir los
# renders de Sora (scratchpad/sora/puntas.py), así que los números son
# comparables con las bandas de la referencia.
#
# Por qué dos renders y no la malla: la silueta es lo que se JUZGA en pantalla;
# medir vértices contra el BVH del cráneo (medir_pelo2.py) da distancias
# 3D que no se ven en el contorno. Aquí se mide lo que la prueba de silueta
# enseña, y sobre eso van los criterios de aceptación del cap. 05.
import bpy, sys, os, math
import numpy as np
from mathutils import Vector
from bpy_extras.object_utils import world_to_camera_view as w2c

args = sys.argv[sys.argv.index("--") + 1:]
out = args[0] if args else "/tmp"
PROM_MIN = float(args[1]) if len(args) > 1 else 7.0     # % del ancho de cara
os.makedirs(out, exist_ok=True)
sc = bpy.context.scene
ob = bpy.data.objects["Alonso"]
pelo = bpy.data.objects.get("Alonso_Pelo")
EYE_Z = ob["ALONSO_EYE_Z"]; CROWN_Z = ob["ALONSO_CROWN_Z"]
ANCHO_CARA = 0.2533          # medir_personaje.py (m)

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
for o in list(bpy.data.objects):
    if o.type == 'MESH':
        o.data.materials.clear(); o.data.materials.append(negro)
        todo += [o.matrix_world @ v.co for v in o.data.vertices]
    elif o.type in ('LIGHT', 'CAMERA'):
        bpy.data.objects.remove(o, do_unlink=True)
zmin, zmax = min(v.z for v in todo), max(v.z for v in todo)
H = zmax - zmin
w = bpy.data.worlds.new("Blanco"); sc.world = w; w.use_nodes = True
w.node_tree.nodes["Background"].inputs["Color"].default_value = (1, 1, 1, 1)


def cam(nombre, loc, tgt, lens):
    cd = bpy.data.cameras.new(nombre); cd.lens = lens
    o = bpy.data.objects.new(nombre, cd); bpy.context.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector(tgt) - Vector(loc)).to_track_quat('-Z', 'Y').to_euler()
    return o


tz = zmax - H * 0.075
CAMS = {"cabeza": cam("SilCabeza", (0, -H * 0.55, tz), (0, 0, tz), 60),
        "perfil": cam("SilPerfil", (-H * 0.55, 0, tz), (0, 0, tz), 60)}
W, Hh = 620, 900
sc.render.resolution_x, sc.render.resolution_y = W, Hh
sc.render.film_transparent = False
for e in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = e; break
    except TypeError:
        continue
try:
    sc.view_settings.view_transform = 'Standard'; sc.eevee.taa_render_samples = 16
except (AttributeError, TypeError):
    pass


def render_mask(nombre, con_pelo):
    if pelo:
        pelo.hide_render = not con_pelo
    ruta = f"{out}/sil-{nombre}-{'pelo' if con_pelo else 'craneo'}.png"
    sc.render.filepath = ruta
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(ruta)
    px = np.array(img.pixels[:], dtype=np.float32).reshape(Hh, W, 4)[::-1]
    return px[..., :3].mean(axis=2) < 0.5         # fila 0 arriba


def px_of(camob, p):
    v = w2c(sc, camob, Vector(p))
    return v.x * W, (1 - v.y) * Hh


def polar(mask, cx, cy, ymax):
    m = mask.copy(); m[int(ymax):, :] = False
    ys, xs = np.where(m)
    ang = np.degrees(np.arctan2(-(ys - cy), xs - cx)) % 360   # 0 derecha, 90 arriba
    rad = np.hypot(xs - cx, ys - cy)
    R = np.zeros(360)
    for k in range(360):
        s = (ang >= k) & (ang < k + 1)
        if s.any():
            R[k] = rad[s].max()
    return np.convolve(np.r_[R[-2:], R, R[:2]], np.ones(3) / 3, 'valid')


def picos(R, pmin):
    out_ = []
    for k in range(360):
        if R[k] > R[k - 1] and R[k] >= R[(k + 1) % 360]:
            l = k
            while R[(l - 1) % 360] <= R[l % 360] and (k - l) < 90: l -= 1
            r = k
            while R[(r + 1) % 360] <= R[r % 360] and (r - k) < 90: r += 1
            prom = R[k] - max(R[l % 360], R[r % 360])
            if prom >= pmin:
                out_.append((k, R[k], prom))
    return out_


# OJO: la matriz de una cámara recién creada no se actualiza hasta que se
# evalúa el depsgraph; sin esto la primera vista proyecta todo a la misma fila.
bpy.context.view_layer.update()
for vista, camob in CAMS.items():
    sc.camera = camob
    # escala px/mm y centro de ojos, proyectando puntos conocidos
    ex, ey = px_of(camob, (0, 0, EYE_Z))
    x1, _ = px_of(camob, (0.05, 0, EYE_Z)) if vista == "cabeza" else px_of(camob, (0, 0.05, EYE_Z))
    ppm = abs(x1 - ex) / 50.0                       # píxeles por mm
    _, crow = px_of(camob, (0, 0, CROWN_Z))
    chin_z = CROWN_Z - (CROWN_Z - EYE_Z) / 0.53
    _, chrow = px_of(camob, (0, 0, chin_z))
    con = render_mask(vista, True)
    sin = render_mask(vista, False)
    Rp = polar(con, ex, ey, chrow)
    Rc = polar(sin, ex, ey, chrow)
    capa = (Rp - Rc) / ppm                          # mm por grado
    cara_px = ANCHO_CARA * 1000 * ppm
    pk = picos(Rp, PROM_MIN / 100 * cara_px)
    print(f"\n=== SILUETA {vista}  ({ppm:.3f} px/mm, ojos en fila {ey:.0f}, "
          f"cráneo en fila {crow:.0f}, mentón en fila {chrow:.0f})")
    # cima del pelo y del cráneo (fila mínima con píxel negro)
    top_p = np.where(con.any(axis=1))[0].min(); top_c = np.where(sin.any(axis=1))[0].min()
    print(f"  cima del pelo sobre el cráneo: {(top_c - top_p) / ppm:.1f} mm "
          f"= {(top_c - top_p) / cara_px * 100:.0f} % del ancho de cara")
    zonas = (("arriba 60-120", 60, 120), ("lat. alto izq-esp 120-160", 120, 160),
             ("lat. alto der-esp 20-60", 20, 60), ("sienes 160-200", 160, 200),
             ("sienes 340-20", 340, 380), ("lat. bajo 200-250", 200, 250),
             ("lat. bajo 290-340", 290, 340)) if vista == "cabeza" else (
             ("coronilla 60-120", 60, 120), ("nuca alta 120-160", 120, 160),
             ("nuca 160-200", 160, 200), ("frente 20-60", 20, 60), ("cara 340-20", 340, 380))
    for nombre, a0, a1 in zonas:
        idx = [k % 360 for k in range(a0, a1)]
        c = capa[idx]
        print(f"  capa {nombre:26s}: mediana {np.median(c):5.1f} mm  máx {c.max():5.1f} mm "
              f"(mediana = {np.median(c) * ppm / cara_px * 100:.0f} % del ancho de cara)")
    filas = con.sum(axis=1)
    fmax = int(np.argmax(filas[:int(chrow)]))
    w_eye = filas[int(ey)] / ppm; w_max = filas[fmax] / ppm
    print(f"  ancho máx del pelo {w_max:.0f} mm = {w_max / (ANCHO_CARA*1000):.2f}x cara, en fila {fmax} "
          f"({(ey - fmax) / ppm:.0f} mm sobre los ojos); ancho en la línea de ojos {w_eye:.0f} mm "
          f"(cintura {100 * (1 - w_eye / w_max):.0f} %)")
    print(f"  puntas con prominencia >= {PROM_MIN:.0f} % del ancho de cara: {len(pk)}")
    for k, r, p in sorted(pk, key=lambda t: -t[2]):
        print(f"    ángulo {k:3d}  radio {r/ppm:5.0f} mm  prominencia {p/ppm:4.0f} mm = {p / cara_px * 100:4.0f} %")
    g = sum(1 for _, _, p in pk if p / cara_px >= 0.25)
    m = sum(1 for _, _, p in pk if 0.15 <= p / cara_px < 0.25)
    f = sum(1 for _, _, p in pk if p / cara_px < 0.15)
    print(f"  jerarquía grandes(>=25%)/medianas(15-25%)/finas(7-15%): {g}/{m}/{f}")
