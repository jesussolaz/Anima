# ÁNIMA — Interior del Molino: la casa del panadero
#
# Herramienta de EDITOR (bpy). El .blend sale SIN Python.
#   Flipendo --background --factory-startup --python gen_molino_interior.py
# Salida: ~/Flipendo/game/anima/MolinoInterior.blend
#
# La planta baja del molino, habitada. El horno de bóveda es la pieza héroe:
# está levantado ladrillo a ladrillo, igual que el tejado de fuera va teja a teja.
# La geometría del muro sale de anima_kit, así que interior y exterior encajan.

import bpy
import bmesh
import math
import os
import random
import sys
from mathutils import Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "anima_kit" in sys.modules:
    del sys.modules["anima_kit"]
from anima_kit import (                                            # noqa: E402
    CH, Build, aim, beam, blob, cam, cbox, circle_ring, clamp01, clear_scene,
    disc, flat, frame_matrix, ico, in_wall, inner_r, jitter, lathe, lathe_arc,
    lerp, loft, make_mat, on_wall, rect_ring, rgb, sack, sagging_grid, tower_r,
    tube, DOOR_ANG, DOOR_H, DOOR_W, WALL_T, WIN_BAJA, WIN_H, WIN_W, Z_PLINTH)

random.seed(1605)

OUT_DIR = os.path.expanduser("~/Flipendo/game/anima")
os.makedirs(OUT_DIR, exist_ok=True)
OUT_BLEND = os.path.join(OUT_DIR, "MolinoInterior.blend")

# ----------------------------------------------------------------- la sala
FLOOR = Z_PLINTH                    # 0.98
CEIL = 3.62                         # cara inferior de las vigas
BOARDS = CEIL + 0.20                # tarima del piso de arriba
R_FLOOR = inner_r(FLOOR)            # ~3.03
R_CEIL = inner_r(CEIL)              # ~2.88

OVEN_ANG = math.radians(112.0)      # el horno, enfrente y a la izquierda al entrar
STAIR_A0, STAIR_A1 = math.radians(-58.0), math.radians(22.0)
HATCH = Vector((1.95, 0.72))        # trampilla del piso de arriba
POST = Vector((0.10, 0.62))         # pie derecho central

MAT = dict(CAL=0, PIEDRA=1, LADRILLO=2, MAD=3, MADOSC=4, HIERRO=5, SACO=6,
           HARINA=7, PAN=8, MASA=9, BARRO=10, MIMBRE=11, BRASA=12, TELA=13,
           ANIMA=14, NEGRO=15, AJO=16, HIERBA=17, HOLLIN=18, LLAMA=19)

clear_scene()
sc = bpy.context.scene
sc.name = "MolinoInterior"

MATS = [
    make_mat("M_CalInt", (0.84, 0.78, 0.66), 0.92, mottle=0.13, mottle_scale=3.4),
    make_mat("M_Piedra", (0.50, 0.46, 0.40), 0.93, mottle=0.16, mottle_scale=7.0),
    make_mat("M_Ladrillo", (0.52, 0.26, 0.16), 0.90, mottle=0.22, mottle_scale=13.0),
    make_mat("M_Madera", (0.40, 0.26, 0.14), 0.82, mottle=0.14, mottle_scale=13.0),
    make_mat("M_MaderaOscura", (0.19, 0.12, 0.07), 0.84, mottle=0.13, mottle_scale=11.0),
    make_mat("M_Hierro", (0.075, 0.070, 0.075), 0.52, mottle=0.20, mottle_scale=16.0,
             metallic=0.85),
    make_mat("M_Saco", (0.66, 0.56, 0.38), 0.95, mottle=0.13, mottle_scale=18.0),
    make_mat("M_Harina", (0.93, 0.90, 0.82), 0.97, mottle=0.06, mottle_scale=22.0),
    make_mat("M_Pan", (0.62, 0.40, 0.19), 0.86, mottle=0.17, mottle_scale=20.0),
    make_mat("M_Masa", (0.86, 0.79, 0.63), 0.90, mottle=0.09, mottle_scale=16.0),
    make_mat("M_Barro", (0.48, 0.27, 0.17), 0.88, mottle=0.14, mottle_scale=8.0),
    make_mat("M_Mimbre", (0.60, 0.44, 0.22), 0.90, mottle=0.20, mottle_scale=26.0),
    make_mat("M_Brasa", (1.0, 0.32, 0.06), 0.70, emit=(1.0, 0.30, 0.045), emit_str=9.0),
    make_mat("M_Tela", (0.44, 0.36, 0.31), 0.94, mottle=0.11, mottle_scale=12.0),
    make_mat("M_Anima", (1.0, 0.72, 0.24), 0.40, emit=(1.0, 0.58, 0.14), emit_str=1.7),
    make_mat("M_Negro", (0.010, 0.009, 0.012), 0.96),
    make_mat("M_Ajo", (0.86, 0.82, 0.72), 0.88, mottle=0.10, mottle_scale=24.0),
    make_mat("M_Hierba", (0.34, 0.33, 0.17), 0.93, mottle=0.16, mottle_scale=18.0),
    make_mat("M_Hollin", (0.055, 0.048, 0.045), 0.95),
    make_mat("M_Llama", (1.0, 0.72, 0.32), 0.7, emit=(1.0, 0.62, 0.24), emit_str=2.6),
]

# ----------------------------------------------------------------- desgaste
OVEN_P = Vector((math.cos(OVEN_ANG) * (R_FLOOR - 0.7),
                 math.sin(OVEN_ANG) * (R_FLOOR - 0.7), FLOOR))


def interior(co):
    """Una panadería se ensucia de dos maneras: hollín subiendo desde el horno
    y harina posándose sobre todo lo demás."""
    x, y, z = co
    v = 1.0
    # hollín: mancha la pared sobre el horno y se extiende por el techo
    d = math.hypot(x - OVEN_P.x, y - OVEN_P.y)
    soot = clamp01(1.0 - d / 3.4) * clamp01((z - 1.5) / 1.6)
    v -= 0.52 * soot ** 1.3
    # zócalo sucio de rozar
    v -= 0.20 * clamp01(1.0 - (z - FLOOR) / 0.55) ** 1.5
    # moteado + aguas verticales de la cal
    v *= 0.90 + 0.13 * noise.noise(Vector((x * 0.9, y * 0.9, z * 0.9)))
    v *= 0.94 + 0.10 * noise.noise(Vector((x * 2.8, y * 2.8, z * 0.30)))
    # velo de harina en las superficies altas y en el suelo
    flour = 0.10 * clamp01(1.0 - abs(z - FLOOR) / 0.10)
    return (clamp01(v + flour), clamp01(v + flour * 0.96), clamp01(v + flour * 0.86))


def dusty(base, amt=0.5):
    """Tinte fijo con un velo de harina encima."""
    return lambda co: tuple(lerp(base[i], (0.93, 0.90, 0.82)[i], amt * 0.35)
                            for i in range(3))


# ----------------------------------------------------------------- MURO Y SUELO
print("[INT] muro, huecos y solería…")
W = Build()

# perfil cerrado del muro: cara interior, coronación, cara exterior, base
WPROF = [(R_FLOOR, FLOOR - 0.12), (R_CEIL - 0.06, BOARDS + 1.25),
         (tower_r(BOARDS + 1.25), BOARDS + 1.25), (tower_r(FLOOR - 0.12), FLOOR - 0.12),
         (R_FLOOR, FLOOR - 0.12)]

dgap = math.asin((DOOR_W / 2 + 0.16) / R_FLOOR)
wgap = math.asin((WIN_W / 2 + 0.14) / R_FLOOR)
WIN_ANG = WIN_BAJA[0]
# dos arcos de muro: del hueco de la puerta al de la ventana, y vuelta
W.add(*lathe_arc(WPROF, DOOR_ANG + dgap, WIN_ANG - wgap, segs=26, wobble=0.030),
      mat=MAT["CAL"], smooth=True, tint=interior)
W.add(*lathe_arc(WPROF, WIN_ANG + wgap, DOOR_ANG + 2 * math.pi - dgap, segs=54,
                 wobble=0.030), mat=MAT["CAL"], smooth=True, tint=interior)

# dinteles: cierran el muro por encima de cada hueco
for (ang, gap, htop) in ((DOOR_ANG, dgap, FLOOR + DOOR_H),
                         (WIN_ANG, wgap, WIN_BAJA[1] + WIN_H / 2)):
    HPROF = [(R_FLOOR, htop), (R_CEIL - 0.06, BOARDS + 1.25),
             (tower_r(BOARDS + 1.25), BOARDS + 1.25), (tower_r(htop), htop),
             (R_FLOOR, htop)]
    W.add(*lathe_arc(HPROF, ang - gap, ang + gap, segs=10, wobble=0.030),
          mat=MAT["CAL"], smooth=True, tint=interior)
# antepecho bajo la ventana
BPROF = [(R_FLOOR, FLOOR - 0.12), (R_FLOOR, WIN_BAJA[1] - WIN_H / 2),
         (tower_r(WIN_BAJA[1]), WIN_BAJA[1] - WIN_H / 2),
         (tower_r(FLOOR - 0.12), FLOOR - 0.12), (R_FLOOR, FLOOR - 0.12)]
W.add(*lathe_arc(BPROF, WIN_ANG - wgap, WIN_ANG + wgap, segs=10, wobble=0.030),
      mat=MAT["CAL"], smooth=True, tint=interior)

# solería: losas irregulares en anillos concéntricos, gastadas hacia la puerta
nrings = 6
for ri in range(nrings):
    r0 = R_FLOOR * (ri / nrings) ** 0.85
    r1 = R_FLOOR * ((ri + 1) / nrings) ** 0.85
    rm = (r0 + r1) / 2
    nsl = max(6, int(2 * math.pi * rm / 0.52))
    for i in range(nsl):
        a = (i + 0.42 * ri) / nsl * 2 * math.pi
        w = 2 * math.pi * rm / nsl * random.uniform(0.80, 0.94)
        d = (r1 - r0) * random.uniform(0.80, 0.94)
        V, F = cbox(w, d, 0.11, ch=0.016)
        V = jitter(V, 0.008)
        ca, sa = math.cos(a), math.sin(a)
        mtx = frame_matrix(Vector((ca * rm, sa * rm, FLOOR - 0.055 + random.uniform(-0.008, 0.006))),
                           Vector((-sa, ca, 0)), Vector((ca, sa, 0)), Vector((0, 0, 1)))
        wear = 1.0 - 0.13 * clamp01(1.0 - abs(a - DOOR_ANG) / 1.1)
        W.add(V, F, MAT["PIEDRA"], mtx,
              tint=rgb((wear * random.uniform(0.88, 1.10),) * 3))

muro = W.finish("Sala", MATS)

# ----------------------------------------------------------------- HORNO
print("[INT] horno de bóveda, ladrillo a ladrillo…")
H = Build()
_, OM = in_wall(OVEN_ANG, FLOOR)          # X ancho, Y hacia la sala, Z arriba

PLAT_W, PLAT_D, PLAT_H = 2.05, 1.58, 0.60
DOME_R, DOME_Y = 0.80, 0.72
MOUTH_W, MOUTH_H = 0.58, 0.30            # hueco recto + arco de medio punto encima

# poyo: mampostería en tres hiladas
for c, (cz, ch_) in enumerate(((0.0, 0.21), (0.21, 0.20), (0.41, 0.19))):
    nb = 9
    for i in range(nb):
        bw = PLAT_W / nb * random.uniform(0.84, 0.96)
        V, F = cbox(bw, PLAT_D, ch_ * 0.94, ch=0.016)
        V = jitter(V, 0.010)
        H.add(V, F, MAT["PIEDRA"],
              OM @ Matrix.Translation((-PLAT_W / 2 + (i + 0.5) * PLAT_W / nb
                                       + random.uniform(-0.01, 0.01),
                                       PLAT_D / 2, cz + ch_ / 2)),
              tint=rgb((random.uniform(0.86, 1.08),) * 3))
V, F = cbox(PLAT_W + 0.10, PLAT_D + 0.08, 0.09, ch=0.02)      # losa del poyo
H.add(V, F, MAT["PIEDRA"], OM @ Matrix.Translation((0, PLAT_D / 2, PLAT_H + 0.045)),
      tint=flat(0.98))

# bóveda: ladrillos por hiladas sobre la media esfera, saltándose la boca
DZ = PLAT_H + 0.09
ncourse = 15
nbrick = 0
for c in range(ncourse):
    phi = (math.pi / 2) * (1.0 - (c + 0.5) / ncourse)     # 90° = base
    rr = DOME_R * math.sin(phi)
    zz = DOME_R * math.cos(phi)
    n = max(5, int(2 * math.pi * rr / 0.205))
    for i in range(n):
        a = (i + 0.5 * (c % 2)) / n * 2 * math.pi + random.uniform(-0.012, 0.012)
        ca, sa = math.cos(a), math.sin(a)
        px, py, pz = rr * ca, rr * sa, zz
        # hueco de la boca: mira hacia la sala (+Y local)
        if py > 0.30 and abs(px) < MOUTH_W / 2 + 0.06 and pz < 0.50:
            continue
        nrm = Vector((px, py, pz)).normalized()
        tg = Vector((-sa, ca, 0.0))
        up = tg.cross(nrm)
        pos = Vector((px, py + DOME_Y, pz + DZ)) + nrm * 0.012
        bl = 2 * math.pi * rr / n
        V, F = cbox(bl * 0.93, 0.10, 0.062, ch=0.008)
        m = (OM @ frame_matrix(pos, tg, nrm, up)
             @ Matrix.Rotation(random.uniform(-0.05, 0.05), 4, 'Y'))
        H.add(V, F, MAT["LADRILLO"], m,
              tint=rgb((random.uniform(0.72, 1.12),) * 3))
        nbrick += 1
print(f"[INT]   {nbrick} ladrillos en la bóveda")

# cámara interior del horno: llega hasta el plano de la boca, para que por el
# hueco se vean las brasas y no el exterior
V, F = lathe([(0.0, 0.0), (0.785, 0.0), (0.750, 0.26), (0.600, 0.50),
              (0.360, 0.66), (0.0, 0.72)], segs=22, cap_bottom=True)
H.add(V, F, MAT["HOLLIN"], OM @ Matrix.Translation((0, DOME_Y, DZ + 0.005)),
      smooth=True, tint=flat(1.0))

MY = DOME_Y + 0.80                                            # plano de la boca
for side in (-1, 1):                                          # jambas de la boca
    V, F = cbox(0.17, 0.30, MOUTH_H + 0.10, ch=0.014)
    H.add(V, F, MAT["PIEDRA"],
          OM @ Matrix.Translation((side * (MOUTH_W / 2 + 0.085), MY - 0.06,
                                   DZ + (MOUTH_H + 0.10) / 2)),
          tint=flat(0.74))                                     # tiznadas de humo
for k in range(11):                                           # dovelas del arco
    a = math.pi * (k + 0.5) / 11
    ca, sa = math.cos(a), math.sin(a)
    rd = MOUTH_W / 2 + 0.085
    V, F = cbox(0.155, 0.30, 0.19, ch=0.012)
    m = (OM @ Matrix.Translation((ca * rd, MY - 0.06, DZ + MOUTH_H + 0.10 + sa * rd))
         @ Matrix.Rotation(-a + math.pi / 2, 4, 'Y'))
    H.add(V, F, MAT["PIEDRA"], m, tint=rgb((random.uniform(0.62, 0.80),) * 3))
V, F = cbox(MOUTH_W + 0.80, 0.46, 0.11, ch=0.02)              # losa de la boca
H.add(V, F, MAT["PIEDRA"], OM @ Matrix.Translation((0, MY + 0.16, DZ - 0.02)),
      tint=flat(0.90))

# brasas dentro
for i in range(34):
    r = random.uniform(0.0, 0.50)
    a = random.uniform(0, 2 * math.pi)
    V, F = blob(random.uniform(0.045, 0.095), lumps=0.45, seed=i * 2.1, subdiv=1)
    H.add(V, F, MAT["BRASA"],
          OM @ Matrix.Translation((math.cos(a) * r, DOME_Y + math.sin(a) * r + 0.14,
                                   DZ + 0.075)), smooth=True, tint=flat(1.0))
# ceniza
for i in range(30):
    r = random.uniform(0.0, 0.55)
    a = random.uniform(0, 2 * math.pi)
    V, F = blob(random.uniform(0.05, 0.13), lumps=0.5, seed=i * 3.3, subdiv=1,
                scale=(1, 1, 0.25))
    H.add(V, F, MAT["HOLLIN"],
          OM @ Matrix.Translation((math.cos(a) * r, DOME_Y + math.sin(a) * r, DZ + 0.02)),
          smooth=True, tint=rgb((random.uniform(0.8, 1.6),) * 3))

# humero: sale por detrás de la bóveda y se mete en el muro. Estrecho a propósito:
# la bóveda de ladrillo es la pieza, no se tapa.
V, F = loft([[(x, y, 0.0) for x, y in rect_ring(0.48, 0.42, 0.04)],
             [(x, y, 0.30) for x, y in rect_ring(0.40, 0.36, 0.035)],
             [(x, y, CEIL - FLOOR - (DZ + DOME_R * 0.86))
              for x, y in rect_ring(0.36, 0.32, 0.03)]],
            cap_start=False, cap_end=False)
H.add(V, F, MAT["CAL"], OM @ Matrix.Translation((0, DOME_Y - 0.30, DZ + DOME_R * 0.86)),
      tint=interior)

# puerta de hierro del horno, apoyada en el poyo
V, F = cbox(0.62, 0.05, 0.60, ch=0.012)
H.add(V, F, MAT["HIERRO"],
      OM @ Matrix.Translation((PLAT_W / 2 - 0.30, MY + 0.34, DZ + 0.28))
      @ Matrix.Rotation(math.radians(-14), 4, 'X'), tint=flat(1.0))
V, F = tube([(0, 0, 0), (0, -0.09, 0.06), (0, -0.09, 0.20), (0, 0, 0.26)], 0.020, segs=6)
H.add(V, F, MAT["HIERRO"],
      OM @ Matrix.Translation((PLAT_W / 2 - 0.30, MY + 0.30, DZ + 0.30))
      @ Matrix.Rotation(math.radians(-14), 4, 'X'), smooth=True, tint=flat(1.0))

horno = H.finish("Horno", MATS)

# ----------------------------------------------------------------- CARPINTERÍA
print("[INT] techo, pie derecho y escalera…")
C = Build()

# pie derecho con zapata
V, F = beam(0.30, 0.30, 0.26, 0.26, CEIL - FLOOR - 0.26, ch=0.020)
C.add(V, F, MAT["MAD"], Matrix.Translation((POST.x, POST.y, FLOOR)), tint=flat(0.92))
V, F = cbox(0.34, 0.34, 0.10, ch=0.02)                       # basa de piedra
C.add(V, F, MAT["PIEDRA"], Matrix.Translation((POST.x, POST.y, FLOOR + 0.05)),
      tint=flat(0.95))
V, F = beam(0.26, 0.98, 0.34, 0.62, 0.26, ch=0.020)          # zapata
C.add(V, F, MAT["MAD"], Matrix.Translation((POST.x, POST.y, CEIL - 0.26)),
      tint=flat(0.86))

# viga maestra sobre el pie derecho
L = 2 * math.sqrt(max(R_CEIL ** 2 - POST.x ** 2, 0.01))
V, F = beam(0.34, 0.30, 0.34, 0.30, L, ch=0.018)
C.add(V, F, MAT["MAD"],
      Matrix.Translation((-L / 2 + POST.x, POST.y, CEIL - 0.15))
      @ Matrix.Rotation(math.radians(90), 4, 'Y'), tint=flat(0.88))

# viguetas transversales
for k in range(-4, 5):
    yy = POST.y + k * 0.62
    if abs(yy) > R_CEIL - 0.30:
        continue
    half = math.sqrt(max(R_CEIL ** 2 - yy ** 2, 0.01))
    V, F = beam(0.17, 0.21, 0.15, 0.19, 2 * half, ch=0.014)
    V = jitter(V, 0.006)
    C.add(V, F, MAT["MADOSC"],
          Matrix.Translation((-half, yy, CEIL + 0.02))
          @ Matrix.Rotation(math.radians(90), 4, 'Y'), tint=flat(0.80))

# tarima del piso de arriba, con la trampilla abierta
hx0, hx1 = HATCH.x - 0.58, HATCH.x + 0.58
hy0, hy1 = HATCH.y - 0.58, HATCH.y + 0.58
x = -R_CEIL
while x < R_CEIL:
    w = 0.215
    half = math.sqrt(max(R_CEIL ** 2 - min(abs(x), R_CEIL) ** 2, 0.0))
    spans = [(-half, half)]
    if x + w > hx0 and x < hx1:
        spans = [(-half, hy0), (hy1, half)]
    for (y0, y1) in spans:
        if y1 - y0 < 0.12:
            continue
        V, F = cbox(w * 0.96, y1 - y0, 0.055, ch=0.008)
        C.add(V, F, MAT["MAD"],
              Matrix.Translation((x + w / 2, (y0 + y1) / 2, BOARDS)),
              tint=rgb((random.uniform(0.80, 1.0),) * 3))
    x += w

# escalera pegada al muro, hacia la trampilla
NSTEP = 12
for k in range(NSTEP):
    t = (k + 1) / NSTEP
    a = lerp(STAIR_A0, STAIR_A1, t)
    z = lerp(FLOOR, CEIL + 0.10, t)
    rr = lerp(R_FLOOR - 0.62, R_FLOOR - 0.85, t)
    ca, sa = math.cos(a), math.sin(a)
    V, F = cbox(1.02, 0.30, 0.075, ch=0.010)
    m = frame_matrix(Vector((ca * rr, sa * rr, z)),
                     Vector((-sa, ca, 0)), Vector((ca, sa, 0)), Vector((0, 0, 1)))
    C.add(V, F, MAT["MAD"], m, tint=rgb((random.uniform(0.82, 1.0),) * 3))
    # can empotrado que sostiene el peldaño
    V, F = beam(0.11, 0.11, 0.10, 0.10, 0.55, ch=0.010)
    C.add(V, F, MAT["MADOSC"],
          m @ Matrix.Translation((0.30, 0.24, -0.06))
          @ Matrix.Rotation(math.radians(-90), 4, 'X'), tint=flat(0.75))
# soga de mano sobre argollas
rope_pts = []
for k in range(NSTEP + 1):
    t = k / NSTEP
    a = lerp(STAIR_A0, STAIR_A1, t)
    z = lerp(FLOOR, CEIL + 0.10, t) + 0.92 + 0.05 * math.sin(k * 1.7)
    rr = lerp(R_FLOOR - 0.16, R_FLOOR - 0.30, t)
    rope_pts.append((math.cos(a) * rr, math.sin(a) * rr, z))
C.add(*tube(rope_pts, 0.022, segs=6), mat=MAT["MADOSC"], smooth=True, tint=flat(0.85))
for k in range(0, NSTEP + 1, 3):
    p = rope_pts[k]
    V, F = lathe([(0.045, 0.0), (0.062, 0.012), (0.062, 0.030), (0.045, 0.042)], segs=10)
    C.add(V, F, MAT["HIERRO"], Matrix.Translation(p), smooth=True, tint=flat(1.0))

carp = C.finish("Carpinteria", MATS)

# ----------------------------------------------------------------- OBRADOR
print("[INT] obrador: artesa, mesa, pan, sacos…")
O = Build()


def wood_table(mtx, w, d, h, top=0.075):
    V, F = cbox(w, d, top, ch=0.012)
    O.add(V, F, MAT["MAD"], mtx @ Matrix.Translation((0, 0, h - top / 2)),
          tint=flat(0.95))
    for sx in (-1, 1):
        for sy in (-1, 1):
            V, F = beam(0.085, 0.085, 0.075, 0.075, h - top, ch=0.010)
            O.add(V, F, MAT["MADOSC"],
                  mtx @ Matrix.Translation((sx * (w / 2 - 0.10), sy * (d / 2 - 0.10), 0)),
                  tint=flat(0.82))
    V, F = cbox(w - 0.16, 0.06, 0.06, ch=0.008)
    O.add(V, F, MAT["MADOSC"], mtx @ Matrix.Translation((0, 0, h * 0.34)), tint=flat(0.78))


def hogaza(mtx, r=0.15, scored=True, tint=None):
    """Hogaza redonda con la cruz marcada antes de meterla al horno."""
    V, F = blob(r, lumps=0.16, seed=random.random() * 9, subdiv=2,
                scale=(1.0, 1.0, 0.62))
    O.add(V, F, MAT["PAN"], mtx, smooth=True,
          tint=tint or rgb((random.uniform(0.80, 1.18),) * 3))
    if scored:
        for ang in (0.0, math.pi / 2):
            V, F = cbox(r * 1.15, 0.012, 0.008, ch=0.003)
            O.add(V, F, MAT["PAN"],
                  mtx @ Matrix.Rotation(ang, 4, 'Z')
                  @ Matrix.Translation((0, 0, r * 0.585)), tint=flat(0.42))


# artesa de amasar, junto al horno
_, AM = in_wall(math.radians(158), FLOOR)
AM = AM @ Matrix.Translation((0, 0.55, 0))
V, F = loft([[(x, y, 0.0) for x, y in rect_ring(1.30, 0.66, 0.03)],
             [(x, y, 0.34) for x, y in rect_ring(1.52, 0.80, 0.03)]],
            cap_start=True, cap_end=False)
O.add(V, F, MAT["MAD"], AM @ Matrix.Translation((0, 0, 0.62)), tint=flat(0.92))
V, F = loft([[(x, y, 0.0) for x, y in rect_ring(1.18, 0.54, 0.03)],
             [(x, y, 0.30) for x, y in rect_ring(1.38, 0.68, 0.03)]],
            cap_start=True, cap_end=False)
O.add(V, F, MAT["MADOSC"], AM @ Matrix.Translation((0, 0, 0.66)), tint=flat(0.55))
for sx in (-1, 1):                                    # patas en aspa
    for sy in (-1, 1):
        V, F = beam(0.09, 0.09, 0.08, 0.08, 0.66, ch=0.010)
        O.add(V, F, MAT["MADOSC"],
              AM @ Matrix.Translation((sx * 0.56, sy * 0.24, 0))
              @ Matrix.Rotation(math.radians(sx * 5), 4, 'Y'), tint=flat(0.80))
for i in range(5):                                    # masa reposando
    V, F = blob(random.uniform(0.13, 0.19), lumps=0.22, seed=i * 4.4, subdiv=2,
                scale=(1.0, 1.0, 0.58))
    O.add(V, F, MAT["MASA"],
          AM @ Matrix.Translation((-0.48 + i * 0.24, random.uniform(-0.09, 0.09), 0.80)),
          smooth=True, tint=rgb((random.uniform(0.90, 1.06),) * 3))
V, F = sagging_grid(0.76, 0.52, 8, 6, sag=0.05, ripple=0.018, seed=2.2)   # paño
O.add(V, F, MAT["TELA"], AM @ Matrix.Translation((0.34, 0.02, 0.86)), smooth=True,
      tint=flat(1.0))

# mesa de trabajo
MT = (Matrix.Translation((-1.30, -0.35, FLOOR)) @ Matrix.Rotation(math.radians(28), 4, 'Z'))
wood_table(MT, 1.60, 0.86, 0.86)
for i in range(4):                                    # hogazas listas
    hogaza(MT @ Matrix.Translation((-0.52 + i * 0.30, 0.18, 0.95)),
           r=random.uniform(0.13, 0.17))
V, F = lathe([(0.0, 0.0), (0.13, 0.0), (0.185, 0.075), (0.175, 0.125), (0.0, 0.125)],
             segs=18, cap_bottom=True)                # cuenco de barro
O.add(V, F, MAT["BARRO"], MT @ Matrix.Translation((0.50, -0.18, 0.90)), smooth=True,
      tint=flat(1.0))
V, F = blob(0.125, lumps=0.20, seed=7.1, subdiv=2, scale=(1, 1, 0.46))
O.add(V, F, MAT["MASA"], MT @ Matrix.Translation((0.50, -0.18, 0.975)), smooth=True,
      tint=flat(1.0))
V, F = lathe([(0.0, 0.0), (0.038, 0.0), (0.045, 0.06), (0.045, 0.46), (0.038, 0.52),
              (0.0, 0.52)], segs=12, cap_bottom=True)   # rodillo
O.add(V, F, MAT["MAD"], MT @ Matrix.Translation((-0.10, -0.26, 0.92))
      @ Matrix.Rotation(math.radians(90), 4, 'Y') @ Matrix.Translation((0, 0, -0.26)),
      smooth=True, tint=flat(1.05))
V, F = cbox(0.20, 0.035, 0.006, ch=0.002)               # cuchilla
O.add(V, F, MAT["HIERRO"], MT @ Matrix.Translation((0.10, -0.34, 0.90))
      @ Matrix.Rotation(math.radians(18), 4, 'Z'), tint=flat(1.0))
V, F = cbox(0.11, 0.030, 0.022, ch=0.005)
O.add(V, F, MAT["MADOSC"], MT @ Matrix.Translation((-0.05, -0.31, 0.90))
      @ Matrix.Rotation(math.radians(18), 4, 'Z'), tint=flat(1.0))
for i in range(90):                                     # harina derramada
    V, F = blob(random.uniform(0.006, 0.020), lumps=0.6, seed=i * 1.7, subdiv=1,
                scale=(1.7, 1.7, 0.14))
    O.add(V, F, MAT["HARINA"],
          MT @ Matrix.Translation((random.uniform(-0.74, 0.74),
                                   random.uniform(-0.38, 0.38), 0.90)),
          smooth=True, tint=flat(1.0))

# banqueta
BQ = Matrix.Translation((-1.95, -1.42, FLOOR)) @ Matrix.Rotation(math.radians(-40), 4, 'Z')
V, F = cbox(0.46, 0.30, 0.055, ch=0.010)
O.add(V, F, MAT["MAD"], BQ @ Matrix.Translation((0, 0, 0.44)), tint=flat(0.95))
for sx in (-1, 1):
    for sy in (-1, 1):
        V, F = beam(0.055, 0.055, 0.048, 0.048, 0.42, ch=0.008)
        O.add(V, F, MAT["MADOSC"],
              BQ @ Matrix.Translation((sx * 0.17, sy * 0.10, 0))
              @ Matrix.Rotation(math.radians(sx * 7), 4, 'Y'), tint=flat(0.85))

# palas de horno apoyadas en la pared
for k, (pa, ln) in enumerate(((math.radians(88), 2.35), (math.radians(96), 2.10))):
    _, PM = in_wall(pa, FLOOR)
    lean = PM @ Matrix.Translation((0.0, 0.42, 0)) @ Matrix.Rotation(
        math.radians(-13 - k * 3), 4, 'X')
    V, F = lathe([(0.0, 0.0), (0.028, 0.0), (0.033, 0.10), (0.030, ln), (0.0, ln)],
                 segs=10, cap_bottom=True)
    O.add(V, F, MAT["MAD"], lean, smooth=True, tint=flat(0.98))
    V, F = cbox(0.40, 0.020, 0.46, ch=0.010)
    O.add(V, F, MAT["MAD"], lean @ Matrix.Translation((0, 0, 0.24)), tint=flat(0.92))

# sacos de harina
SACKS = ((-2.30, 1.32, 0.0, 0.78, 0.34), (-1.86, 1.72, 0.35, 0.72, 0.31),
         (-2.55, 0.72, -0.5, 0.70, 0.30), (-1.55, 2.05, 1.1, 0.66, 0.29))
for i, (sx, sy, rz, sh, sr) in enumerate(SACKS):
    V, F = sack(h=sh, r=sr, seed=i * 5.5)
    O.add(V, F, MAT["SACO"], Matrix.Translation((sx, sy, FLOOR))
          @ Matrix.Rotation(rz, 4, 'Z'), smooth=True,
          tint=rgb((random.uniform(0.86, 1.10),) * 3))
    V, F = tube(circle_ring(sr * 0.30, 8, 0.0) + [circle_ring(sr * 0.30, 8, 0.0)[0]],
                0.014, segs=5)
    O.add(V, F, MAT["MADOSC"], Matrix.Translation((sx, sy, FLOOR + sh * 0.80)),
          smooth=True, tint=flat(0.9))
# uno tumbado, abierto, con la harina fuera
V, F = sack(h=0.74, r=0.32, seed=31.0)
O.add(V, F, MAT["SACO"], Matrix.Translation((-2.05, 0.30, FLOOR + 0.30))
      @ Matrix.Rotation(math.radians(86), 4, 'X')
      @ Matrix.Rotation(math.radians(20), 4, 'Z'), smooth=True, tint=flat(1.0))
for i in range(70):
    d = random.random() ** 0.6 * 0.62
    a = random.uniform(-1.1, 1.1) - 0.5
    V, F = blob(random.uniform(0.02, 0.07) * (1.1 - d), lumps=0.5, seed=i * 2.9,
                subdiv=1, scale=(1.6, 1.6, 0.18))
    O.add(V, F, MAT["HARINA"],
          Matrix.Translation((-2.05 + math.cos(a) * d - 0.35,
                              0.30 + math.sin(a) * d, FLOOR + 0.015)),
          smooth=True, tint=flat(1.0))

# tinajas
for (tx, ty, ts) in ((2.05, 1.72, 1.0), (2.48, 1.20, 0.78)):
    V, F = lathe([(0.0, 0.0), (0.22, 0.0), (0.34, 0.18), (0.40, 0.44), (0.34, 0.70),
                  (0.24, 0.86), (0.27, 0.92), (0.23, 0.96), (0.0, 0.96)],
                 segs=22, cap_bottom=True)
    V = [(x * ts, y * ts, z * ts) for (x, y, z) in V]
    O.add(V, F, MAT["BARRO"], Matrix.Translation((tx, ty, FLOOR)), smooth=True,
          tint=rgb((random.uniform(0.88, 1.06),) * 3))

# cestas de mimbre con pan
for (bx, by, br) in ((-0.55, -2.05, 0.34), (0.15, -2.30, 0.28)):
    prof = [(0.0, 0.0), (br * 0.8, 0.0)]
    for k in range(6):                                   # costillas del mimbre
        z0 = 0.04 + k * 0.055
        prof += [(br * (0.86 + 0.10 * (k / 5)), z0), (br * (0.92 + 0.10 * (k / 5)), z0 + 0.028)]
    prof += [(br * 1.02, 0.40), (br * 0.96, 0.42)]
    V, F = lathe(prof, segs=20, cap_bottom=True)
    O.add(V, F, MAT["MIMBRE"], Matrix.Translation((bx, by, FLOOR)), smooth=True,
          tint=rgb((random.uniform(0.88, 1.08),) * 3))
    for i in range(4):
        hogaza(Matrix.Translation((bx + random.uniform(-0.13, 0.13),
                                   by + random.uniform(-0.13, 0.13),
                                   FLOOR + 0.40 + i * 0.03)),
               r=random.uniform(0.11, 0.14))

# estante con hogazas
_, SH = in_wall(math.radians(196), FLOOR)
for k, sz in enumerate((1.30, 1.72)):
    V, F = cbox(1.70, 0.34, 0.055, ch=0.010)
    O.add(V, F, MAT["MAD"], SH @ Matrix.Translation((0, 0.19, sz)), tint=flat(0.92))
    for sx in (-0.70, 0.70):                             # jabalcones
        V, F = beam(0.055, 0.055, 0.048, 0.048, 0.40, ch=0.008)
        O.add(V, F, MAT["MADOSC"],
              SH @ Matrix.Translation((sx, 0.05, sz - 0.03))
              @ Matrix.Rotation(math.radians(128), 4, 'X'), tint=flat(0.8))
    for i in range(5):
        hogaza(SH @ Matrix.Translation((-0.66 + i * 0.33, 0.18, sz + 0.13)),
               r=random.uniform(0.115, 0.15))

obrador = O.finish("Obrador", MATS)

# ----------------------------------------------------------------- COLGADOS
print("[INT] colgados del techo…")
G = Build()
for k, (gx, gy) in enumerate(((-0.85, 1.55), (-0.45, 1.75), (1.15, -1.40))):
    top = CEIL - 0.05
    G.add(*tube([(gx, gy, top), (gx, gy, top - 0.22)], 0.012, segs=5),
          mat=MAT["MADOSC"], smooth=True, tint=flat(0.8))
    if k < 2:                                            # ristras de ajos
        for i in range(11):
            t = i / 10.0
            r = 0.085 * math.sin(t * math.pi) + 0.03
            a = i * 2.1
            V, F = blob(0.052, lumps=0.16, seed=i * 3.1, subdiv=1, scale=(1, 1, 1.25))
            G.add(V, F, MAT["AJO"],
                  Matrix.Translation((gx + math.cos(a) * r, gy + math.sin(a) * r,
                                      top - 0.30 - t * 0.46)), smooth=True,
                  tint=rgb((random.uniform(0.88, 1.06),) * 3))
    else:                                                # manojo de hierbas
        for i in range(16):
            a = random.uniform(0, 6.28)
            r = random.uniform(0.0, 0.075)
            V, F = beam(0.012, 0.012, 0.004, 0.004, random.uniform(0.30, 0.46), ch=0.003)
            G.add(V, F, MAT["HIERBA"],
                  Matrix.Translation((gx + math.cos(a) * r, gy + math.sin(a) * r,
                                      top - 0.22))
                  @ Matrix.Rotation(math.pi + random.uniform(-0.16, 0.16), 4, 'X'),
                  tint=rgb((random.uniform(0.8, 1.15),) * 3))

# farol colgado, encendido
FX, FY, FZ = 0.95, -0.95, CEIL - 0.60
G.add(*tube([(FX, FY, CEIL - 0.04), (FX, FY, FZ + 0.22)], 0.010, segs=5),
      mat=MAT["HIERRO"], smooth=True, tint=flat(1.0))
for sx in (-1, 1):
    for sy in (-1, 1):
        V, F = beam(0.016, 0.016, 0.016, 0.016, 0.30, ch=0.004)
        G.add(V, F, MAT["HIERRO"],
              Matrix.Translation((FX + sx * 0.085, FY + sy * 0.085, FZ - 0.15)),
              tint=flat(1.0))
V, F = cbox(0.21, 0.21, 0.035, ch=0.006)
G.add(V, F, MAT["HIERRO"], Matrix.Translation((FX, FY, FZ - 0.16)), tint=flat(1.0))
V, F = lathe([(0.145, 0.0), (0.155, 0.03), (0.02, 0.15)], segs=8, cap_top=True)
G.add(V, F, MAT["HIERRO"], Matrix.Translation((FX, FY, FZ + 0.15)), tint=flat(1.0))
V, F = lathe([(0.0, 0.0), (0.024, 0.0), (0.022, 0.075), (0.0, 0.095)], segs=10,
             cap_bottom=True)
G.add(V, F, MAT["LLAMA"], Matrix.Translation((FX, FY, FZ - 0.13)), smooth=True,
      tint=flat(1.0))

colgados = G.finish("Colgados", MATS)

# ----------------------------------------------------------------- POLVO
print("[INT] polvo de harina y motas de Ánima…")
P = Build()
SUN_FROM = Vector((0.344, -0.906, 0.242)).normalized()
# Poco y pequeño: el haz de luz lo dibuja la niebla, no las motas. Si se ven
# como copos, sobran.
for i in range(150):
    a = random.uniform(0, 2 * math.pi)
    d = random.random() ** 0.55 * (R_FLOOR - 0.25)
    x, y = math.cos(a) * d, math.sin(a) * d
    z = FLOOR + random.random() ** 0.8 * (CEIL - FLOOR - 0.1) + 0.05
    # el polvo se concentra donde entra la luz por la puerta
    shaft = clamp01(1.0 - abs(x - (y + 3.0) * (SUN_FROM.x / -SUN_FROM.y)) / 1.5)
    if random.random() > 0.16 + 0.70 * shaft:
        continue
    V, F = ico(1)
    r = random.uniform(0.0030, 0.0075)
    P.add(V, F, MAT["HARINA"],
          Matrix.Translation((x, y, z)) @ Matrix.Diagonal((r, r, r, 1.0)),
          smooth=True, tint=flat(1.0))
for i in range(45):
    a = random.uniform(0, 2 * math.pi)
    d = random.random() ** 0.6 * (R_FLOOR - 0.4)
    V, F = ico(1)
    r = random.uniform(0.006, 0.013)
    P.add(V, F, MAT["ANIMA"],
          Matrix.Translation((math.cos(a) * d, math.sin(a) * d,
                              FLOOR + random.uniform(0.3, 2.9)))
          @ Matrix.Diagonal((r, r, r, 1.0)), smooth=True, tint=flat(1.0))
polvo = P.finish("Polvo", MATS)

for ob in (muro, horno, carp, obrador):
    ob.game.physics_type = 'STATIC'
    ob.game.use_collision_bounds = True
    ob.game.collision_bounds_type = 'TRIANGLE_MESH'
for ob in (colgados, polvo):
    ob.game.physics_type = 'NO_COLLISION'

# ----------------------------------------------------------------- LUZ
print("[INT] luz…")
world = bpy.data.worlds.new("W_Interior")
sc.world = world
world.use_nodes = True
wnt = world.node_tree
bg = wnt.nodes.get("Background")
bg.inputs["Color"].default_value = (0.30, 0.20, 0.16, 1.0)
bg.inputs["Strength"].default_value = 0.42

sun_d = bpy.data.lights.new("SolPuerta", 'SUN')
sun_d.energy = 6.0
sun_d.color = (1.0, 0.60, 0.30)
sun_d.angle = math.radians(1.2)
sun = bpy.data.objects.new("SolPuerta", sun_d)
bpy.context.collection.objects.link(sun)
aim(sun, -SUN_FROM)
sun.game.physics_type = 'NO_COLLISION'


def point(name, loc, energy, color, radius=0.25):
    d = bpy.data.lights.new(name, 'POINT')
    d.energy = energy
    d.color = color
    d.shadow_soft_size = radius
    o = bpy.data.objects.new(name, d)
    bpy.context.collection.objects.link(o)
    o.location = loc
    o.game.physics_type = 'NO_COLLISION'
    return o


mouth = OM @ Vector((0.0, MY - 0.10, DZ + 0.22))
point("FuegoHorno", mouth, 420.0, (1.0, 0.42, 0.13), 0.30)
point("FuegoDentro", OM @ Vector((0.0, DOME_Y, DZ + 0.16)), 260.0, (1.0, 0.34, 0.08), 0.22)
point("Farol", (FX, FY, FZ - 0.12), 55.0, (1.0, 0.66, 0.30), 0.10)
point("Rebote", (0.0, -1.3, FLOOR + 0.9), 40.0, (1.0, 0.62, 0.38), 0.9)

# niebla de harina en suspensión: es lo que hace visible el haz de la puerta
vol = bpy.data.materials.new("M_PolvoAire")
vol.use_nodes = True
vnt = vol.node_tree
for n in list(vnt.nodes):
    vnt.nodes.remove(n)
vout = vnt.nodes.new("ShaderNodeOutputMaterial")
pv = vnt.nodes.new("ShaderNodeVolumePrincipled")
pv.inputs["Color"].default_value = (1.0, 0.86, 0.70, 1.0)
pv.inputs["Density"].default_value = 0.011
vnt.links.new(pv.outputs["Volume"], vout.inputs["Volume"])
VB = Build()
VB.add(*cbox(2 * R_FLOOR + 0.4, 2 * R_FLOOR + 0.4, CEIL - FLOOR + 0.3, ch=0.01))
niebla = VB.finish("PolvoAire", [vol])
niebla.location = (0, 0, (FLOOR + CEIL) / 2)
niebla.game.physics_type = 'NO_COLLISION'

# ----------------------------------------------------------------- cámaras
DOOR_P = Vector((math.cos(DOOR_ANG) * R_FLOOR, math.sin(DOOR_ANG) * R_FLOOR, FLOOR))
OV = OM @ Vector((0.0, MY, DZ + 0.30))          # boca del horno, en mundo
cam("CamSala", (0.92, DOOR_P.y + 0.30, FLOOR + 1.56),
    (OV.x - 0.30, OV.y - 0.15, FLOOR + 1.22), lens=21)
cam("CamHorno", (0.30, -1.60, FLOOR + 1.30), (-0.84, 1.95, FLOOR + 1.00), lens=34)
cam("CamMesa", (0.50, -1.80, FLOOR + 1.20), (-1.34, -0.34, FLOOR + 0.94), lens=38)
cam("CamTecho", (0.30, -1.70, FLOOR + 0.90), (1.75, 0.62, CEIL + 0.12), lens=20)
cam("CamEscalera", (-0.55, -1.55, FLOOR + 1.15), (2.30, 0.05, FLOOR + 1.55), lens=28)
sc.camera = bpy.data.objects["CamSala"]

# ----------------------------------------------------------------- ajustes
gs = sc.game_settings
gs.fps = 60
gs.physics_engine = 'BULLET'
gs.physics_gravity = 9.8
sc.render.resolution_x = 1600
sc.render.resolution_y = 900
for eng in ('BLENDER_EEVEE_NEXT', 'BLENDER_EEVEE'):
    try:
        sc.render.engine = eng
        break
    except TypeError:
        continue
try:
    sc.view_settings.view_transform = 'AgX'
except TypeError:
    sc.view_settings.view_transform = 'Standard'
for lk in ('AgX - Medium High Contrast', 'AgX - High Contrast', 'Medium High Contrast'):
    try:
        sc.view_settings.look = lk
        break
    except TypeError:
        continue
try:
    sc.eevee.taa_render_samples = 128
    sc.eevee.use_raytracing = True
    sc.eevee.ray_tracing_options.use_denoise = True
except AttributeError:
    pass

faces = sum(len(m.polygons) for m in bpy.data.meshes)
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[INT] guardado: {OUT_BLEND}")
print(f"[INT] objetos: {len(bpy.data.objects)}  caras: {faces}")
print("[INT] OK")
