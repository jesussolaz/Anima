# ÁNIMA — kit de construcción de assets (herramienta de EDITOR, bpy)
#
# Geometría de bajo nivel compartida por los generadores. Nada de esto entra en
# los .blend: los .blend salen sin Python. Doctrina C++ intacta.
#
# Regla de oro del kit: todo lleva chaflán. Una arista viva se lee como plástico;
# una arista achaflanada atrapa la luz y se lee como un objeto.

import bmesh
import bpy
import math
import random
from mathutils import Matrix, Vector, noise

CH = 0.014          # chaflán por defecto


# ----------------------------------------------------------------- numérico

def clamp01(x):
    return max(0.0, min(1.0, x))


def lerp(a, b, t):
    return a + (b - a) * t


def flat(c):
    """Tinte constante para Build.add(tint=...)."""
    return lambda co: (c, c, c)


def rgb(c):
    return lambda co: c


# ----------------------------------------------------------------- perfiles

def rect_ring(w, d, ch):
    """Anillo rectangular con las 4 esquinas achaflanadas (octógono)."""
    ch = max(0.0, min(ch, w * 0.45, d * 0.45))
    hw, hd = w / 2.0, d / 2.0
    return [(hw, hd - ch), (hw - ch, hd), (-(hw - ch), hd), (-hw, hd - ch),
            (-hw, -(hd - ch)), (-(hw - ch), -hd), (hw - ch, -hd), (hw, -(hd - ch))]


def circle_ring(r, segs=12, z=0.0):
    return [(math.cos(i / segs * 2 * math.pi) * r,
             math.sin(i / segs * 2 * math.pi) * r, z) for i in range(segs)]


def loft(rings, cap_start=True, cap_end=True):
    """Une anillos consecutivos (mismo número de puntos) en un tubo cerrado."""
    V, F = [], []
    offs = []
    for r in rings:
        offs.append(len(V))
        V.extend(r)
    n = len(rings[0])
    for ri in range(len(rings) - 1):
        a, b = offs[ri], offs[ri + 1]
        for i in range(n):
            j = (i + 1) % n
            F.append([a + i, a + j, b + j, b + i])
    if cap_start:
        F.append(list(range(offs[0], offs[0] + n))[::-1])
    if cap_end:
        F.append(list(range(offs[-1], offs[-1] + n)))
    return V, F


# ----------------------------------------------------------------- primitivas

def beam(w0, d0, w1, d1, L, ch=CH):
    """Viga achaflanada en las 4 aristas largas y en los dos extremos.
    Crece de z=0 a z=L."""
    c0 = min(ch, w0 * 0.4, d0 * 0.4)
    c1 = min(ch, w1 * 0.4, d1 * 0.4)
    rings = [
        [(x, y, 0.0) for x, y in rect_ring(w0 - 2 * c0, d0 - 2 * c0, c0 * 0.5)],
        [(x, y, c0) for x, y in rect_ring(w0, d0, c0)],
        [(x, y, L - c1) for x, y in rect_ring(w1, d1, c1)],
        [(x, y, L) for x, y in rect_ring(w1 - 2 * c1, d1 - 2 * c1, c1 * 0.5)],
    ]
    return loft(rings)


def cbox(sx, sy, sz, ch=CH):
    """Caja achaflanada CENTRADA en el origen (sx,sy,sz = lados completos).
    `beam` crece de z=0 a z=L, así que hay que bajarla media altura."""
    V, F = beam(sx, sy, sx, sy, sz, ch)
    return [(x, y, z - sz / 2.0) for (x, y, z) in V], F


def lathe(profile, segs=48, wobble=0.0, seed=0.0, cap_bottom=False, cap_top=False):
    """Superficie de revolución. `profile` = [(radio, z), ...].
    `wobble` desplaza el radio con ruido 3D: lo hecho a mano no es un cilindro."""
    V, F = [], []
    n = len(profile)
    for si in range(segs):
        a = si / segs * 2.0 * math.pi
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in profile:
            rr = r
            if wobble:
                rr += wobble * noise.noise(Vector((ca * r * 0.55, sa * r * 0.55,
                                                   z * 0.5 + seed)))
                rr += wobble * 0.4 * noise.noise(Vector((ca * r * 2.1, sa * r * 2.1,
                                                         z * 1.9 + seed)))
            V.append((ca * rr, sa * rr, z))

    def vid(si, pi):
        return (si % segs) * n + pi

    for si in range(segs):
        for pi in range(n - 1):
            F.append([vid(si, pi), vid(si + 1, pi), vid(si + 1, pi + 1), vid(si, pi + 1)])
    if cap_bottom:
        F.append([vid(si, 0) for si in range(segs)][::-1])
    if cap_top:
        F.append([vid(si, n - 1) for si in range(segs)])
    return V, F


def lathe_arc(profile, a0, a1, segs=24, wobble=0.0, seed=0.0, caps=True):
    """Revolución PARCIAL de un perfil CERRADO (el último punto repite el primero).
    Sirve para levantar un muro dejando el hueco de una puerta: los extremos del
    arco se tapan y esas tapas son las mochetas del hueco."""
    V, F = [], []
    n = len(profile)
    for si in range(segs + 1):
        a = lerp(a0, a1, si / segs)
        ca, sa = math.cos(a), math.sin(a)
        for (r, z) in profile:
            rr = r
            if wobble:
                rr += wobble * noise.noise(Vector((ca * r * 0.55, sa * r * 0.55,
                                                   z * 0.5 + seed)))
            V.append((ca * rr, sa * rr, z))
    for si in range(segs):
        for pi in range(n - 1):
            a_, b_ = si * n, (si + 1) * n
            F.append([a_ + pi, b_ + pi, b_ + pi + 1, a_ + pi + 1])
    if caps:
        F.append(list(range(0, n - 1))[::-1])
        last = segs * n
        F.append(list(range(last, last + n - 1)))
    return V, F


_ICO = {}


def ico(subdiv=1):
    """Icosfera unitaria cacheada."""
    if subdiv in _ICO:
        return _ICO[subdiv]
    tb = bmesh.new()
    bmesh.ops.create_icosphere(tb, subdivisions=subdiv, radius=1.0)
    tb.verts.index_update()
    V = [tuple(v.co) for v in tb.verts]
    F = [[v.index for v in f.verts] for f in tb.faces]
    tb.free()
    _ICO[subdiv] = (V, F)
    return V, F


def blob(r=0.5, lumps=0.18, seed=0.0, subdiv=2, scale=(1, 1, 1)):
    """Icosfera abollada: hogazas, brasas, cebollas, montones."""
    V, F = ico(subdiv)
    out = []
    for (x, y, z) in V:
        n = 1.0 + lumps * noise.noise(Vector((x * 2.2 + seed, y * 2.2, z * 2.2)))
        out.append((x * r * n * scale[0], y * r * n * scale[1], z * r * n * scale[2]))
    return out, F


def disc(r, segs=48, z=0.0):
    V = [(0.0, 0.0, z)]
    for i in range(segs):
        a = i / segs * 2 * math.pi
        V.append((math.cos(a) * r, math.sin(a) * r, z))
    F = [[0, 1 + i, 1 + (i + 1) % segs] for i in range(segs)]
    return V, F


def sack(h=0.72, r=0.30, seed=0.0, segs=14):
    """Saco de harina: panza abajo, cuello estrangulado, bultos irregulares."""
    prof = ((0.00, 0.70), (0.07, 0.96), (0.26, 1.00), (0.48, 0.92),
            (0.66, 0.66), (0.76, 0.36), (0.84, 0.30), (0.92, 0.20))
    rings = []
    for (t, rr) in prof:
        ring = []
        for i in range(segs):
            a = i / segs * 2 * math.pi
            lump = 1.0 + 0.13 * noise.noise(Vector((math.cos(a) * 2.0,
                                                    math.sin(a) * 2.0, t * 4.0 + seed)))
            R = r * rr * lump
            ring.append((math.cos(a) * R, math.sin(a) * R, t * h))
        rings.append(ring)
    return loft(rings, cap_start=True, cap_end=True)


def tube(pts, r, segs=6):
    """Tubo de sección circular siguiendo una polilínea: sogas, ristras, cables."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, p in enumerate(pts):
        if i == 0:
            d = (pts[1] - pts[0])
        elif i == len(pts) - 1:
            d = (pts[-1] - pts[-2])
        else:
            d = (pts[i + 1] - pts[i - 1])
        d.normalize()
        up = Vector((0, 0, 1)) if abs(d.z) < 0.9 else Vector((1, 0, 0))
        ex = d.cross(up).normalized()
        ey = ex.cross(d).normalized()
        ring = []
        for k in range(segs):
            a = k / segs * 2 * math.pi
            ring.append(tuple(p + ex * (math.cos(a) * r) + ey * (math.sin(a) * r)))
        rings.append(ring)
    return loft(rings, cap_start=True, cap_end=True)


def sagging_grid(w, h, nx, ny, sag, ripple=0.0, seed=0.0):
    """Paño con vuelo (panza en el centro) y arrugas: lonas, mantas, sábanas."""
    V, F = [], []
    for j in range(ny + 1):
        for i in range(nx + 1):
            u, v = i / nx, j / ny
            z = math.sin(u * math.pi) * math.sin(v * math.pi) * sag
            if ripple:
                z += ripple * noise.noise(Vector((u * 5.0, v * 5.0, seed)))
            V.append(((u - 0.5) * w, (v - 0.5) * h, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            F.append([a, a + 1, a + nx + 2, a + nx + 1])
    return V, F


def blade(h=0.34, w=0.024, lean=0.15, segs=4):
    """Brizna de hierba: tira que se estrecha y se vence."""
    V, F = [], []
    for i in range(segs + 1):
        t = i / segs
        ww = w * (1.0 - t * 0.93) ** 0.75
        V.append((-ww, lean * t * t, h * t))
        V.append((ww, lean * t * t, h * t))
    for i in range(segs):
        F.append([2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2])
    return V, F


def tile(width=0.335, length=0.44, thick=0.022, arc=math.radians(118), segs=5,
         taper=0.87):
    """Teja curva. Abomba hacia +Z, corre hacia +Y, ancho en X.
    Los bordes del arco quedan en z=0 para apoyar en el faldón."""
    R = (width / 2.0) / math.sin(arc / 2.0)
    cz = -R * math.cos(arc / 2.0)
    V = []
    for (yy, sc) in ((0.0, 1.0), (length, taper)):
        for rr in (R - thick, R):
            for i in range(segs + 1):
                a = -arc / 2.0 + arc * i / segs
                V.append((math.sin(a) * rr * sc, yy, cz + math.cos(a) * rr))
    n = segs + 1

    def vid(j, k, i):
        return j * 2 * n + k * n + i

    F = []
    for i in range(segs):
        F.append([vid(0, 1, i), vid(0, 1, i + 1), vid(1, 1, i + 1), vid(1, 1, i)])
        F.append([vid(0, 0, i), vid(1, 0, i), vid(1, 0, i + 1), vid(0, 0, i + 1)])
        F.append([vid(0, 0, i), vid(0, 0, i + 1), vid(0, 1, i + 1), vid(0, 1, i)])
        F.append([vid(1, 0, i), vid(1, 1, i), vid(1, 1, i + 1), vid(1, 0, i + 1)])
    for i in (0, segs):
        F.append([vid(0, 0, i), vid(0, 1, i), vid(1, 1, i), vid(1, 0, i)])
    return V, F


def jitter(V, amt):
    return [(x + random.uniform(-amt, amt),
             y + random.uniform(-amt, amt),
             z + random.uniform(-amt, amt)) for (x, y, z) in V]


def frame_matrix(origin, ex, ey, ez):
    """Matriz cuyas columnas son los ejes dados."""
    return Matrix(((ex.x, ey.x, ez.x, origin.x),
                   (ex.y, ey.y, ez.y, origin.y),
                   (ex.z, ey.z, ez.z, origin.z),
                   (0.0, 0.0, 0.0, 1.0)))


# ----------------------------------------------------------------- constructor

class Build:
    """Acumula geometría en un bmesh con un atributo de color por vértice.
    El desgaste se pinta aquí, no en texturas."""

    def __init__(self):
        self.bm = bmesh.new()
        self.col = self.bm.loops.layers.color.new("Col")

    def add(self, V, F, mat=0, mtx=None, smooth=False, tint=None):
        bv = []
        for v in V:
            co = Vector(v)
            if mtx is not None:
                co = mtx @ co
            bv.append(self.bm.verts.new(co))
        for f in F:
            try:
                face = self.bm.faces.new([bv[i] for i in f])
            except ValueError:
                continue
            face.material_index = mat
            face.smooth = smooth
            for lp in face.loops:
                if tint is None:
                    c = (1.0, 1.0, 1.0)
                else:
                    c = tint(lp.vert.co) if callable(tint) else tint
                lp[self.col] = (c[0], c[1], c[2], 1.0)

    def finish(self, name, mats):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        me = bpy.data.meshes.new(name)
        self.bm.to_mesh(me)
        self.bm.free()
        ob = bpy.data.objects.new(name, me)
        bpy.context.collection.objects.link(ob)
        for m in mats:
            me.materials.append(m)
        return ob


def make_mat(name, color, rough=0.9, mottle=0.0, mottle_scale=6.0,
             emit=None, emit_str=0.0, metallic=0.0):
    """Principled con el atributo "Col" multiplicando la base y, opcionalmente,
    moteado procedural en color y aspereza."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metallic

    base = nt.nodes.new("ShaderNodeRGB")
    base.outputs[0].default_value = (*color, 1.0)
    attr = nt.nodes.new("ShaderNodeAttribute")
    attr.attribute_name = "Col"
    mix = nt.nodes.new("ShaderNodeMix")
    mix.data_type = 'RGBA'
    mix.blend_type = 'MULTIPLY'
    mix.inputs["Factor"].default_value = 1.0
    nt.links.new(base.outputs[0], mix.inputs["A"])
    nt.links.new(attr.outputs["Color"], mix.inputs["B"])
    out = mix.outputs["Result"]

    if mottle > 0.0:
        tex = nt.nodes.new("ShaderNodeTexNoise")
        tex.inputs["Scale"].default_value = mottle_scale
        tex.inputs["Detail"].default_value = 6.0
        rng = nt.nodes.new("ShaderNodeMapRange")
        rng.inputs["To Min"].default_value = 1.0 - mottle
        rng.inputs["To Max"].default_value = 1.0 + mottle
        mix2 = nt.nodes.new("ShaderNodeMix")
        mix2.data_type = 'RGBA'
        mix2.blend_type = 'MULTIPLY'
        mix2.inputs["Factor"].default_value = 1.0
        nt.links.new(out, mix2.inputs["A"])
        nt.links.new(tex.outputs["Fac"], rng.inputs["Value"])
        nt.links.new(rng.outputs["Result"], mix2.inputs["B"])
        out = mix2.outputs["Result"]
        rr = nt.nodes.new("ShaderNodeMapRange")
        rr.inputs["To Min"].default_value = max(0.05, rough - 0.18)
        rr.inputs["To Max"].default_value = min(1.0, rough + 0.10)
        nt.links.new(tex.outputs["Fac"], rr.inputs["Value"])
        nt.links.new(rr.outputs["Result"], bsdf.inputs["Roughness"])

    nt.links.new(out, bsdf.inputs["Base Color"])
    if emit is not None:
        bsdf.inputs["Emission Color"].default_value = (*emit, 1.0)
        bsdf.inputs["Emission Strength"].default_value = emit_str
    m.diffuse_color = (*color, 1.0)
    return m


def clear_scene():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob, do_unlink=True)


def aim(ob, direction):
    ob.rotation_euler = Vector(direction).to_track_quat('-Z', 'Y').to_euler()


def cam(name, loc, target, lens=50.0, clip_end=1200.0):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.clip_end = clip_end
    co = bpy.data.objects.new(name, cd)
    bpy.context.collection.objects.link(co)
    co.location = loc
    aim(co, Vector(target) - Vector(loc))
    co.game.physics_type = 'NO_COLLISION'
    return co


# ------------------------------------------------- geometría del molino (compartida)
# Exterior e interior TIENEN que coincidir, así que el perfil de la torre y la
# posición de los huecos viven aquí y no en cada generador.

Z_PLINTH = 0.98          # coronación del zócalo de piedra
Z_EAVE = 8.30            # arranque de la cornisa
WALL_T = 0.58            # grosor del muro
PROFILE = [(3.62, 0.86), (3.58, 1.60), (3.50, 3.00), (3.40, 4.60),
           (3.30, 6.20), (3.19, 7.50), (3.13, Z_EAVE)]

DOOR_ANG = -math.pi / 2.0                  # la puerta mira a -Y
DOOR_W, DOOR_H = 1.32, 2.16
WIN_BAJA = (-math.pi / 2 + 1.55, 2.35)     # ventana de la planta baja
WINDOWS = [WIN_BAJA,
           (-math.pi / 2 + 0.62, 4.15),
           (-math.pi / 2 + 2.05, 6.05),
           (-math.pi / 2 - 1.25, 5.10)]
WIN_W, WIN_H = 0.78, 0.86


def tower_r(z):
    if z <= PROFILE[0][1]:
        return PROFILE[0][0]
    for i in range(len(PROFILE) - 1):
        r0, z0 = PROFILE[i]
        r1, z1 = PROFILE[i + 1]
        if z <= z1:
            return lerp(r0, r1, (z - z0) / (z1 - z0))
    return PROFILE[-1][0]


def inner_r(z):
    return tower_r(z) - WALL_T


def on_wall(ang, z, out=0.0):
    """Punto sobre el muro y marco local diestro:
    X = a lo ancho, Y = hacia FUERA (profundidad), Z = arriba."""
    ca, sa = math.cos(ang), math.sin(ang)
    r = tower_r(z) + out
    p = Vector((ca * r, sa * r, z))
    return p, frame_matrix(p, Vector((sa, -ca, 0.0)), Vector((ca, sa, 0.0)),
                           Vector((0.0, 0.0, 1.0)))


def in_wall(ang, z, inn=0.0):
    """Igual pero en la cara INTERIOR: Y apunta hacia el centro de la sala."""
    ca, sa = math.cos(ang), math.sin(ang)
    r = inner_r(z) - inn
    p = Vector((ca * r, sa * r, z))
    return p, frame_matrix(p, Vector((-sa, ca, 0.0)), Vector((-ca, -sa, 0.0)),
                           Vector((0.0, 0.0, 1.0)))


# ------------------------------------------------- personajes
# Barridos a lo largo de un camino, mechones de pelo y espejado. Lo que hace
# falta para construir un personaje con secciones limpias en vez de esferas.

def catmull(pts, n):
    """Remuestrea una polilínea con Catmull-Rom: n puntos, curva suave."""
    pts = [Vector(p) for p in pts]
    if len(pts) < 2:
        return pts
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    out = []
    segs = len(pts) - 1
    for i in range(n):
        t = i / (n - 1) * segs
        k = min(int(t), segs - 1)
        f = t - k
        p0, p1, p2, p3 = ext[k], ext[k + 1], ext[k + 2], ext[k + 3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * f
                          + (2 * p0 - 5 * p1 + 4 * p2 - p3) * f * f
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * f * f * f))
    return out


def transport_frames(path, up_hint=(0.0, 0.0, 1.0)):
    """Marcos con transporte paralelo: el barrido no se retuerce solo."""
    P = [Vector(p) for p in path]
    T = []
    for i in range(len(P)):
        if i == 0:
            d = P[1] - P[0]
        elif i == len(P) - 1:
            d = P[-1] - P[-2]
        else:
            d = P[i + 1] - P[i - 1]
        T.append(d.normalized() if d.length > 1e-9 else Vector((0, 0, 1)))
    up = Vector(up_hint)
    n0 = (up - T[0] * up.dot(T[0]))
    if n0.length < 1e-6:
        n0 = (Vector((1, 0, 0)) - T[0] * T[0].x)
    n0.normalize()
    frames = [(T[0], n0, T[0].cross(n0))]
    for i in range(1, len(P)):
        prev_t, prev_n, _ = frames[-1]
        n = prev_n - T[i] * prev_n.dot(T[i])      # proyecta y renormaliza
        if n.length < 1e-6:
            n = prev_t.cross(T[i])
        n.normalize()
        frames.append((T[i], n, T[i].cross(n)))
    return P, frames


def sweep(path, section, scales=None, twist=None, caps=True, up_hint=(0, 0, 1)):
    """Barre una sección 2D [(u,v), ...] a lo largo de un camino.

    `scales[i]` puede ser un número (escala uniforme) o una tupla (su, sv):
    su escala el eje u de la sección (el ANCHO del mechón) y sv el eje v (su
    GROSOR). Se separan porque un mechón de pelo no se afila igual en los dos
    ejes: medido en VRoid, en el último quinto conserva el 80 % del ancho y
    solo el 62 % del grosor (se aplana antes de afilarse). Con una sola escala
    el mechón leía como triángulo desde la raíz (Alonso v9, taper 3,0)."""
    P, frames = transport_frames(path, up_hint)
    rings = []
    for i, (p, (t, n, b)) in enumerate(zip(P, frames)):
        s = scales[i] if scales else 1.0
        if isinstance(s, (int, float)):
            su = sv = s
        else:
            su, sv = s
        a = twist[i] if twist else 0.0
        ca, sa = math.cos(a), math.sin(a)
        ring = []
        for (u, v) in section:
            uu, vv = u * ca - v * sa, u * sa + v * ca
            ring.append(tuple(p + n * (uu * su) + b * (vv * sv)))
        rings.append(ring)
    return loft(rings, cap_start=caps, cap_end=caps)


def leaf_section(segs=8, w=1.0, h=0.32):
    """Sección de mechón: lenteja apuntada, no un cilindro."""
    pts = []
    for i in range(segs):
        a = i / segs * 2 * math.pi
        c, s = math.cos(a), math.sin(a)
        pts.append((c * w * (0.55 + 0.45 * abs(c) ** 0.7), s * h))
    return pts


def clump_section(w=1.0, h=0.42):
    """Sección de mechón anime: CUÑA DE ESQUINAS AFILADAS, no una lenteja.
    Es el punto en el que insisten los tutoriales de pelo pincho: con sección
    redonda el mechón lee como una manguera. Las aristas vivas —dos puntas
    laterales y una cresta— son las que dan la faceta de pelo y las que el
    cel-shading convierte en corte limpio entre luz y sombra."""
    return [(-1.00 * w, 0.00), (-0.52 * w, 0.86 * h), (0.0, 1.15 * h),
            (0.52 * w, 0.86 * h), (1.00 * w, 0.00), (0.0, -0.62 * h)]


def fino_section(h=0.5):
    """Sección de hebra fina: ROMBO de 4 vértices, ancho 2 y grosor h.
    Para mechones finos y pelos sueltos no hace falta la cuña de 6 vértices:
    la FAQ de VRoid mide que la sección abierta de pocos vértices divide el
    coste del pelo por 4,2, y CG Cookie lo dice con otras palabras: "para
    hebras muy finas basta un rectángulo". Con 4 vértices y 6 segmentos un
    fino cuesta 44 triángulos frente a los 128 de un principal."""
    return [(-1.0, 0.0), (0.0, 0.5 * h), (1.0, 0.0), (0.0, -0.5 * h)]


def hair_lock(path, w0=0.020, w1=0.002, thick=0.55, n=14, twist_amt=0.0,
              up_hint=(0, 1, 0), taper=2.6):
    """Mechón. `taper` alto = el mechón MANTIENE su grosor y solo se afila al
    final: eso es un mechón. `taper` bajo = cono desde la raíz: eso es una aguja."""
    P = catmull(path, n)
    sec = leaf_section(8, 1.0, thick)
    scales, twists = [], []
    for i in range(n):
        t = i / (n - 1)
        scales.append(lerp(w0, w1, t ** taper))
        twists.append(twist_amt * t)
    return sweep(P, sec, scales, twists, caps=True, up_hint=up_hint)


def mirror_x(V, F):
    """Copia especular en X, con las caras invertidas."""
    MV = [(-x, y, z) for (x, y, z) in V]
    MF = [list(reversed(f)) for f in F]
    return MV, MF


def smoothstep(a, b, x):
    t = clamp01((x - a) / (b - a)) if b != a else 0.0
    return t * t * (3.0 - 2.0 * t)


def falloff(d, r):
    """1 en el centro, 0 en el radio r, con curva suave."""
    return smoothstep(1.0, 0.0, clamp01(d / r))
