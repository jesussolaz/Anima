# ÁNIMA — la espada de Alonso (carril ESPADA)
#
#   cd ~/Flipendo/game/anima && Flipendo --background --python gen_espada.py
# Salida: Espada.blend con UN objeto MESH "Espada" (sin Python, sin luces, sin
# cámaras: eso lo pone la escena del juego).
#
# Brief con las fuentes y los números: dev/noche/informes/anima-espada.md y
# conocimiento/16-espada.md. Resumen de las decisiones que fijan la forma:
#   - Es la espada de los BISABUELOS de un hidalgo de 1600 (Cervantes I, cap. I:
#     «tomadas de orín y llenas de moho»), o sea forjada hacia 1510-1530: hoja
#     ANCHA, guarnición de lazo temprano (arriaz + patillas + pitones + anillo
#     + guardamano) y pomo lenticular (Peláez Valle, Gladius XVI, 1983).
#   - La exageración icónica va a ANCHURA y bloque de guarda, no a largo (la
#     Kingdom Key mide 0,667 de la estatura de Sora; una ropera real era más
#     larga, 0,72 H). Largo 1,12 m = 0,667 × 1,68 m. A 7 m de cámara (m_dist
#     del motor) 1 px = 3,9 mm: una hoja real de 26 mm de canto no existe en
#     pantalla, por eso la hoja mide 60 mm de ancho y 16 de grueso.
#   - Sección en ROMBO: con dos bandas de cel la arista parte la hoja en cara
#     al sol y cara en sombra, que es la «línea de luz» de las hojas de anime.
#   - Orín y moho por COLOR DE VÉRTICE (capa "Col", multiplica la rampa), no por
#     textura (Xrd, GDC 2015: independiente de la resolución). Son texto de
#     Cervantes, no decoración.
#
# Ejes del objeto (los usa el carril RIG al emparentar a hand_r):
#   origen = centro geométrico del puño; +Y = hacia la punta; los FILOS en ±X
#   (el plano de la hoja es XY); los PLANOS de la hoja miran a ±Z.
#   Guardamano: en el plano XY, lado −X (el de los nudillos: el filo verdadero
#   queda abajo cuando se empuña con la punta al frente, y los nudillos van
#   por ahí). Anillo superior: paralelo al plano de la hoja, despegado 40 mm
#   hacia +Z (el dorso de la mano). El brief escribía «+Z = guardamano» y
#   «anillo en +X»: aquí se sigue la anatomía real de una espada de lazo
#   (Peláez, tipos D-G) porque el guardamano protege los nudillos y el anillo
#   el dorso, y las dos cosas están en planos perpendiculares. Si el RIG
#   necesita girarla 90° sobre Y, es una rotación al emparentar.
#
# Presupuesto: ≤ 3.000 tris (objetivo del brief 2.400). El contorno por casco
# invertido (Solidify) los dibuja dos veces en el motor.

import bpy
import math
import os
import sys
from mathutils import Vector, Matrix, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.modules.pop("anima_kit", None)
sys.modules.pop("anima_toon", None)
from anima_kit import (                                            # noqa: E402
    Build, clamp01, disc, falloff, ico, lathe, lerp, loft,
    rect_ring, smoothstep, sweep, tube, catmull)
from anima_toon import sombra_de, material_contorno, contorno     # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_BLEND = os.path.join(HERE, "Espada.blend")

# ------------------------------------------------------------------ medidas (m)
# Todas salen del brief (§3). El puño está centrado en el origen.
L_PUNO = 0.105            # puño útil: «rara vez pasa de 10-11 cm» (Vauthier §VII)
Y_PUNO0, Y_PUNO1 = -L_PUNO / 2, L_PUNO / 2
ARRIAZ_Y = 0.016          # sección del arriaz: 16 (a lo largo de Y) × 12 (Z)
ARRIAZ_Z = 0.012
Y_CRUZ = Y_PUNO1 + ARRIAZ_Y / 2          # centro del arriaz = 0,0605
L_HOJA = 0.940                           # cruz → punta
Y_PUNTA = Y_CRUZ + L_HOJA                # 1,0005
L_RECAZO = 0.110
W_RECAZO, T_RECAZO = 0.060, 0.016        # ancho / grueso en el recazo
FILO_BISEL = 0.005                       # bisel claro de cada filo (M_Filo)
CANAL_W, CANAL_D = 0.014, 0.002          # canal central 14 × 2 mm
CANAL_Y0, CANAL_Y1 = 0.110, 0.380        # medido desde la cruz
MELLA_Y, MELLA_D = 0.620, 0.004          # los dos golpes a la celada de cartón
L_ARRIAZ = 0.300                         # punta a punta
R_BOLA = 0.010                           # remates del arriaz Ø 20
POMO_R = 0.035                           # lenticular Ø 70 (brief 72: con 72 el
                                         # grupo pomo+puño se iba a 194 mm; con
                                         # 70 y cuello de 8 mm queda en 183 y
                                         # el largo total en 1,1235 m, +0,3 %)
POMO_T = 0.030                           # grueso del pomo (en Z)
CUELLO = 0.008
Y_POMO = Y_PUNO0 - CUELLO - POMO_R       # centro del disco: −0,0955
Y_FIN = Y_POMO - POMO_R                  # −0,1305 → largo total 1,131
ANILLO_Z = 0.040                         # despegue del anillo sobre el plano
ANILLO_R = 0.028                         # Ø exterior 70 con sección 14
PATILLA_X = 0.040                        # eje de las patillas: hoja 60 + holgura
PATILLA_L = 0.070

# ------------------------------------------------------------------ colores
# RGB LINEAL (como los toman los nodos). Tabla §3.7 del brief.
C_ACERO = (0.620, 0.640, 0.660)
C_FILO = (0.900, 0.920, 0.950)
C_HIERRO = (0.110, 0.105, 0.120)
C_LATON = (0.850, 0.620, 0.250)
C_CUERO = (0.160, 0.090, 0.050)
C_CINTA = (0.420, 0.080, 0.060)
# Orín: el rust puro #B7410E = (0,474, 0,053, 0,004) multiplicado por el acero
# y al 80 % salía SANGRE en el render (v2): rojo oscuro saturado. Se desplaza a
# naranja-pardo (más verde y azul) y se mezcla al 65 %: sigue siendo óxido, no
# herida.
T_ORIN = (0.520, 0.200, 0.070)
T_MOHO = (0.180, 0.220, 0.140)           # pátina verdosa, al 50 %, solo en el canal


def mezcla(a, b, t):
    return tuple(lerp(x, y, t) for x, y in zip(a, b))


BLANCO = (1.0, 1.0, 1.0)


# ------------------------------------------------------------------ materiales
def toon_metal(name, color, spec=0.0, umbral=0.70, rough=0.15, usa_col=True,
               calida=False):
    """Cel shader de metal: la copia de toon() de anima_toon.py con dos cambios
    que el pelo no necesita y por eso no están allí (anima_toon es del carril
    ROPA y no se toca):
      1. la rugosidad del Glossy es parámetro (0,15 en la hoja: el lóbulo de
         una superficie plana satura y a 0,22 la banda se comía media hoja);
      2. la banda especular se APAGA en el lado en sombra con la misma puerta
         que usa banda_z: un brillo en la cara oscura delata que es un truco.
    Es step(umbral, pow(N·H, n)) de los shaders anime hecho con nodos EEVEE."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = 'CONSTANT'
    som = sombra_de(color, calida, 0.62)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*som, 1.0)
    ramp.color_ramp.elements[-1].position = 0.52
    ramp.color_ramp.elements[-1].color = (*color, 1.0)
    nt.links.new(dif.outputs["BSDF"], s2r.inputs["Shader"])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    salida = ramp.outputs["Color"]

    if usa_col:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.layer_name = "Col"
        mul = nt.nodes.new("ShaderNodeMix")
        mul.data_type = 'RGBA'
        mul.blend_type = 'MULTIPLY'
        mul.inputs["Factor"].default_value = 1.0
        nt.links.new(salida, mul.inputs["A"])
        nt.links.new(vc.outputs["Color"], mul.inputs["B"])
        salida = mul.outputs["Result"]

    if spec > 0.0:
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = rough
        g2r = nt.nodes.new("ShaderNodeShaderToRGB")
        gramp = nt.nodes.new("ShaderNodeValToRGB")
        gramp.color_ramp.interpolation = 'CONSTANT'
        gramp.color_ramp.elements[0].position = 0.0
        gramp.color_ramp.elements[0].color = (0, 0, 0, 1)
        gramp.color_ramp.elements[1].position = umbral
        gramp.color_ramp.elements[1].color = (spec, spec, spec, 1.0)
        nt.links.new(gl.outputs["BSDF"], g2r.inputs["Shader"])
        nt.links.new(g2r.outputs["Color"], gramp.inputs["Fac"])
        # puerta: 1 en la cara iluminada, casi 0 en la sombra
        puerta = nt.nodes.new("ShaderNodeValToRGB")
        puerta.color_ramp.interpolation = 'CONSTANT'
        puerta.color_ramp.elements[0].position = 0.0
        puerta.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1)
        puerta.color_ramp.elements[1].position = 0.52
        puerta.color_ramp.elements[1].color = (1, 1, 1, 1)
        nt.links.new(s2r.outputs["Color"], puerta.inputs["Fac"])
        gate = nt.nodes.new("ShaderNodeMix")
        gate.data_type = 'RGBA'; gate.blend_type = 'MULTIPLY'
        gate.inputs["Factor"].default_value = 1.0
        nt.links.new(gramp.outputs["Color"], gate.inputs["A"])
        nt.links.new(puerta.outputs["Color"], gate.inputs["B"])
        add = nt.nodes.new("ShaderNodeMix")
        add.data_type = 'RGBA'; add.blend_type = 'ADD'
        add.inputs["Factor"].default_value = 1.0
        nt.links.new(salida, add.inputs["A"])
        nt.links.new(gate.outputs["Result"], add.inputs["B"])
        salida = add.outputs["Result"]

    emi = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(salida, emi.inputs["Color"])
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = (*color, 1.0)
    return m


def emision_plana(name, color):
    """Color fijo sin rampa: el filo claro es DISEÑO, como la banda del pelo.
    Brilla también en la parte en sombra, como en la ilustración."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emi = nt.nodes.new("ShaderNodeEmission")
    emi.inputs["Color"].default_value = (*color, 1.0)
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = (*color, 1.0)
    return m


# ------------------------------------------------------------------ desgaste
def mancha(co, escala, umbral, ancho=0.25):
    """Máscara 0..1 de motas de ruido de 8-20 mm (escala 60-90 /m)."""
    n = noise.noise(Vector((co.x * escala, co.y * escala, co.z * escala)))
    return smoothstep(umbral - ancho, umbral + ancho, n)


def cobertura_a_umbral(cov):
    """noise.noise se reparte más o menos simétrico en [-1, 1]; para cubrir la
    fracción `cov` de la superficie el umbral baja según cov (aproximación
    lineal, suficiente: se mira en el render, no se mide)."""
    return 1.0 - 2.0 * cov


def tint_hoja(co):
    """Orín 45 % en el recazo y decreciendo al 10 % en los 250 mm siguientes;
    moho verdoso solo en el fondo del canal."""
    dy = co.y - Y_CRUZ
    if dy < L_RECAZO:
        cov = 0.45
    elif dy < L_RECAZO + 0.250:
        cov = lerp(0.45, 0.10, (dy - L_RECAZO) / 0.250)
    else:
        cov = 0.10
    # escala 40 /m: motas de ~25 mm. Con 70 /m (v1) la malla de 20 anillos no
    # las resolvía y salían como veladuras rosas.
    m = mancha(co, 40.0, cobertura_a_umbral(cov), 0.20)
    c = mezcla(BLANCO, T_ORIN, 0.65 * m)
    # canal: vértices del fondo (x = 0) entre CANAL_Y0 y CANAL_Y1
    if abs(co.x) < 0.0005 and CANAL_Y0 + 0.01 < dy < CANAL_Y1 - 0.01:
        mm = mancha(co, 90.0, cobertura_a_umbral(0.50), 0.35)
        c = mezcla(c, T_MOHO, 0.50 * mm)
    return c


def tint_guarnicion(uniones, eje_interior=None):
    """Orín en las uniones (35 % dentro de 25 mm de cada unión) y Col = 0,6 en
    la cara interior de los lazos (sesgo de umbral, como en Xrd)."""
    def f(co):
        c = BLANCO
        for u in uniones:
            d = (co - u).length
            if d < 0.025:
                m = mancha(co, 80.0, cobertura_a_umbral(0.35)) * falloff(d, 0.025)
                c = mezcla(c, T_ORIN, 0.70 * m)
        if eje_interior is not None:
            centro, hacia = eje_interior
            # la cara que mira hacia el eje del puño se oscurece
            if (co - centro).dot(hacia) > 0.0:
                c = tuple(x * 0.6 for x in c)
        return c
    return f


# ------------------------------------------------------------------ hoja
def seccion_hoja(w, t, b, fd, tipo):
    """12 puntos (x, z) en orden cíclico, mismo orden para el recazo y el
    rombo para poder loftear entre ambos.
      0 filo +X · 1 hombro +X arriba · 2 borde del canal +X arriba
      3 fondo del canal arriba · 4 borde −X arriba · 5 hombro −X arriba
      6 filo −X · 7 hombro −X abajo · 8 borde −X abajo · 9 fondo abajo
      10 borde +X abajo · 11 hombro +X abajo
    tipo 'recazo': rectángulo achaflanado; 'rombo': arista central en ±Z."""
    hw, ht = w / 2.0, t / 2.0
    fw = CANAL_W / 2.0
    if tipo == 'recazo':
        c = 0.0025
        tb = ht - c
        hs = hw - c
        h_fw = ht
    else:
        # bisel del filo: el hombro está a `b` del filo y a tb de alto
        hs = hw - b
        tb = ht * (b / hw) * 1.6 if hw > 1e-6 else 0.0
        tb = min(tb, ht * 0.7)
        # altura de la cara del rombo en x = fw
        if hs > fw:
            h_fw = tb + (ht - tb) * (1.0 - fw / hs)
        else:
            h_fw = ht * 0.5
    fw_ = min(fw, hs * 0.6)
    return [(hw, 0.0), (hs, tb), (fw_, h_fw), (0.0, ht - fd), (-fw_, h_fw),
            (-hs, tb), (-hw, 0.0), (-hs, -tb), (-fw_, -h_fw), (0.0, -(ht - fd)),
            (fw_, -h_fw), (hs, -tb)]


def ancho_hoja(dy):
    """Ancho: 60 en el recazo, 60 → 52 hasta 420, 52 → 24 hasta 880, laurel."""
    if dy <= L_RECAZO:
        return W_RECAZO
    if dy <= 0.420:
        return lerp(0.060, 0.052, (dy - L_RECAZO) / (0.420 - L_RECAZO))
    if dy <= 0.880:
        return lerp(0.052, 0.024, (dy - 0.420) / (0.880 - 0.420))
    # punta en hoja de laurel corta: cae con curva, no con recta
    t = (dy - 0.880) / (L_HOJA - 0.880)
    return max(0.0006, 0.024 * (1.0 - t * t) ** 0.8 * (1.0 - 0.15 * t))


def grueso_hoja(dy):
    """16 en el recazo, 10 a 200 mm («tres veces más fuerte en los diez
    primeros cm del fuerte, luego lineal», Vauthier §VI.b), 4 a 900, 1 en la punta."""
    if dy <= L_RECAZO:
        return T_RECAZO
    if dy <= 0.200:
        return lerp(0.016, 0.010, (dy - L_RECAZO) / (0.200 - L_RECAZO))
    if dy <= 0.900:
        return lerp(0.010, 0.004, (dy - 0.200) / 0.700)
    return max(0.0008, lerp(0.004, 0.001, (dy - 0.900) / (L_HOJA - 0.900)))


def hoja(b):
    dys = [0.0, 0.025, 0.065, L_RECAZO, 0.130, 0.200, 0.270, 0.340, 0.380,
           0.420, 0.500, 0.580, MELLA_Y - 0.006, MELLA_Y, MELLA_Y + 0.006,
           0.700, 0.780, 0.860, 0.900, 0.925, L_HOJA]
    rings = []
    for dy in dys:
        w, t = ancho_hoja(dy), grueso_hoja(dy)
        tipo = 'recazo' if dy <= L_RECAZO else 'rombo'
        fd = CANAL_D if (CANAL_Y0 < dy < CANAL_Y1) else 0.0
        if tipo == 'rombo' and dy >= 0.90:
            fd = 0.0
        sec = seccion_hoja(w, t, FILO_BISEL if tipo == 'rombo' else 0.0, fd, tipo)
        if abs(dy - MELLA_Y) < 1e-6:
            # mella: el filo +X entra 4 mm (la celada de cartón, cap. I)
            sec[0] = (sec[0][0] - MELLA_D, 0.0)
            sec[1] = (sec[1][0] - MELLA_D * 0.6, sec[1][1])
            sec[11] = (sec[11][0] - MELLA_D * 0.6, sec[11][1])
        rings.append([(x, Y_CRUZ + dy, z) for (x, z) in sec])
    V, F = loft(rings, cap_start=True, cap_end=False)
    n = 12
    nf0 = len(b.bm.faces)
    b.add(V, F, mat=0, smooth=False, tint=tint_hoja)
    b.bm.faces.ensure_lookup_table()
    # caras del bisel del filo → M_Filo (índice 1), solo fuera del recazo
    for ri in range(len(rings) - 1):
        if dys[ri] < L_RECAZO:
            continue
        for i in (0, 11, 5, 6):
            b.bm.faces[nf0 + ri * n + i].material_index = 1
    return len(V)


# ------------------------------------------------------------------ guarnición
def sec_barra(a=ARRIAZ_Y, c=ARRIAZ_Z):
    """Sección octogonal de barra forjada: `a` a lo largo de v (Y en el arriaz),
    `c` a lo largo de u."""
    return rect_ring(c, a, 0.003)


def sec_hex(a, c):
    """Sección hexagonal 2D (u = c, v = a): a 7 m una barra de 12 mm son 3 px,
    el octógono no se distingue del hexágono y cuesta un 33 % más."""
    return [(c / 2 * math.cos(math.radians(30 + 60 * i)), a / 2 * math.sin(math.radians(30 + 60 * i)))
            for i in range(6)]


def sec_circulo(r, n=6):
    """Sección circular 2D para sweep (circle_ring del kit devuelve 3D)."""
    return [(math.cos(i / n * 2 * math.pi) * r, math.sin(i / n * 2 * math.pi) * r)
            for i in range(n)]


def esfera(r, segs=8):
    prof = [(r * math.cos(math.radians(p)), r * math.sin(math.radians(p)))
            for p in (-62.0, -22.0, 22.0, 62.0)]
    return lathe(prof, segs=segs, cap_bottom=True, cap_top=True)


def guarnicion(b, mat):
    uniones = []
    # --- arriaz: 300 mm punta a punta, ligeramente curvado hacia la hoja
    path = []
    for i in range(9):
        t = i / 8.0
        x = lerp(-L_ARRIAZ / 2 + R_BOLA, L_ARRIAZ / 2 - R_BOLA, t)
        # curva: los extremos se adelantan 10 mm hacia la punta (tipo B de Peláez)
        y = Y_CRUZ + 0.010 * (2.0 * abs(t - 0.5)) ** 2
        path.append((x, y, 0.0))
    V, F = sweep(path, sec_barra(), caps=True, up_hint=(0, 0, 1))
    uniones += [Vector((0.0, Y_CRUZ, 0.0))]
    b.add(V, F, mat=mat, smooth=True, tint=tint_guarnicion(uniones))
    for sx in (-1, 1):
        V, F = esfera(R_BOLA, 8)
        M = Matrix.Translation((sx * (L_ARRIAZ / 2 - R_BOLA), Y_CRUZ + 0.010, 0.0))
        b.add(V, F, mat=mat, mtx=M, smooth=True)
        uniones.append(Vector((sx * (L_ARRIAZ / 2 - R_BOLA), Y_CRUZ + 0.010, 0.0)))

    # --- patillas (pas d'âne): dos lazos en «D» junto a cada filo, plano YZ
    yf = Y_CRUZ + PATILLA_L + 0.008
    for sx in (-1, 1):
        x = sx * PATILLA_X
        pts = [(x, Y_CRUZ - 0.004, 0.012), (x, Y_CRUZ + 0.030, 0.015),
               (x, Y_CRUZ + 0.060, 0.012), (x, yf, 0.0),
               (x, Y_CRUZ + 0.060, -0.012), (x, Y_CRUZ + 0.030, -0.015),
               (x, Y_CRUZ - 0.004, -0.012)]
        P = catmull(pts, 9)
        V, F = sweep(P, sec_hex(0.010, 0.012), caps=True, up_hint=(1, 0, 0))
        uni = [Vector((x, Y_CRUZ, 0.012)), Vector((x, Y_CRUZ, -0.012)),
               Vector((x, yf, 0.0))]
        eje = (Vector((x, Y_CRUZ + 0.035, 0.0)), Vector((-sx, 0.0, 0.0)))
        b.add(V, F, mat=mat, smooth=True, tint=tint_guarnicion(uni, eje))
        uniones += uni
        # --- pitón: 22 mm en ángulo recto desde el frente de la patilla, bolita Ø 12
        V, F = sweep([(x, yf, 0.0), (x + sx * 0.022, yf, 0.0)],
                     sec_circulo(0.0035, 6), caps=True, up_hint=(0, 0, 1))
        b.add(V, F, mat=mat, smooth=True)
        V, F = ico(0)
        M = Matrix.Translation((x + sx * 0.024, yf, 0.0)) @ Matrix.Scale(0.006, 4)
        b.add(V, F, mat=mat, mtx=M, smooth=True)

    # --- anillo superior: Ø 70, paralelo al plano de la hoja, a 40 mm en +Z,
    # centrado sobre el arriaz (mitad sobre el puño, mitad sobre el recazo)
    cy = Y_CRUZ
    ring = []
    for i in range(13):
        a = i / 12.0 * 2 * math.pi
        ring.append((math.cos(a) * ANILLO_R, cy + math.sin(a) * ANILLO_R, ANILLO_Z))
    V, F = sweep(ring, sec_hex(0.010, 0.014), caps=False, up_hint=(0, 0, 1))
    eje = (Vector((0.0, cy, ANILLO_Z)), None)
    # cara interior del anillo = la que mira a su propio centro
    def tint_anillo(co, c0=Vector((0.0, cy, ANILLO_Z))):
        d = co - c0
        d.z = 0.0
        hacia_centro = -d.normalized() if d.length > 1e-6 else Vector((0, 0, 0))
        c = BLANCO
        if (co - (c0 + d.normalized() * ANILLO_R)).dot(hacia_centro) > 0.0:
            c = tuple(x * 0.6 for x in c)
        m = mancha(co, 80.0, cobertura_a_umbral(0.20))
        return mezcla(c, T_ORIN, 0.70 * m)
    b.add(V, F, mat=mat, smooth=True, tint=tint_anillo)
    # dos puentes que unen el anillo con el arriaz
    for sx in (-1, 1):
        V, F = sweep([(sx * (ANILLO_R - 0.002), cy, 0.0),
                      (sx * ANILLO_R, cy, ANILLO_Z)],
                     rect_ring(0.009, 0.012, 0.0025), caps=True, up_hint=(0, 1, 0))
        b.add(V, F, mat=mat, smooth=True)
        uniones.append(Vector((sx * ANILLO_R, cy, ANILLO_Z)))

    # --- guardamano: arco en el plano XY, lado −X, del arriaz al pomo
    # («se levanta hasta casi tocar el pomo»): acaba a ~6 mm del disco.
    pts = [(-0.055, Y_CRUZ - 0.002, 0.0), (-0.082, 0.030, 0.0),
           (-0.090, -0.010, 0.0), (-0.080, -0.048, 0.0),
           (-0.062, -0.072, 0.0), (-0.047, -0.081, 0.0)]
    P = catmull(pts, 10)
    V, F = sweep(P, rect_ring(0.012, 0.016, 0.003), caps=True, up_hint=(0, 0, 1))
    eje = (Vector((-0.070, -0.010, 0.0)), Vector((1.0, 0.0, 0.0)))
    uni = [Vector((-0.055, Y_CRUZ, 0.0))]
    b.add(V, F, mat=mat, smooth=True, tint=tint_guarnicion(uni, eje))
    uniones += uni
    return uniones


# ------------------------------------------------------------------ puño y pomo
def puno(b, mat_cuero, mat_hierro):
    # alma: óvalo 30 × 24 (lathe alrededor de Y, escalado en X)
    R = Matrix.Rotation(-math.pi / 2, 4, 'X')          # z del lathe → +Y
    S = Matrix.Diagonal((1.25, 1.0, 1.0, 1.0))
    V, F = lathe([(0.012, Y_PUNO0), (0.012, Y_PUNO1)], segs=10,
                 cap_bottom=True, cap_top=True)
    b.add(V, F, mat=mat_cuero, mtx=S @ R, smooth=True)
    # cordón de cuero en espiral: 11 vueltas de Ø 9 mm
    vueltas, ppv = 11, 6
    pts = []
    n = vueltas * ppv
    for i in range(n + 1):
        t = i / n
        a = t * vueltas * 2 * math.pi
        y = lerp(Y_PUNO0 + 0.006, Y_PUNO1 - 0.006, t)
        pts.append((math.cos(a) * 0.0135 * 1.25, y, math.sin(a) * 0.0135))
    V, F = tube(pts, 0.0045, segs=4)
    def tint_cuero(co):
        m = mancha(co, 120.0, cobertura_a_umbral(0.25), 0.4)
        return mezcla(BLANCO, (0.55, 0.50, 0.45), 0.5 * m)     # roce claro
    b.add(V, F, mat=mat_cuero, smooth=True, tint=tint_cuero)
    # nudos de cabeza de turco Ø 34 en los extremos (toro achatado)
    for y in (Y_PUNO0 + 0.006, Y_PUNO1 - 0.007):
        prof = [(0.011 + 0.006 * math.cos(math.radians(p)),
                 0.006 * math.sin(math.radians(p))) for p in (-90, -20, 45, 110, 180)]
        V, F = lathe(prof, segs=10)
        M = Matrix.Translation((0, y, 0)) @ S @ R
        b.add(V, F, mat=mat_cuero, mtx=M, smooth=True)
    # cuello de hierro entre puño y pomo
    V, F = lathe([(0.010, Y_PUNO0 - CUELLO - 0.004), (0.011, Y_PUNO0 + 0.002)],
                 segs=8, cap_bottom=True)
    b.add(V, F, mat=mat_hierro, mtx=R, smooth=True)


def pomo(b, mat_hierro, mat_laton):
    """Lenticular Ø 70 × 30 en el plano de la hoja (disco de rueda), con canto
    de 8 mm; en cada cara un disco de latón Ø 26 y el emblema de los Quijano:
    un anillo abierto con un trazo (la Q reducida a círculo)."""
    R, T = POMO_R, POMO_T / 2
    prof = [(0.017, T), (0.028, T - 0.003), (R - 0.002, 0.005), (R, 0.0),
            (R - 0.002, -0.005), (0.028, -(T - 0.003)), (0.017, -T)]
    V, F = lathe(prof, segs=16, cap_bottom=True, cap_top=True)
    M = Matrix.Translation((0.0, Y_POMO, 0.0))
    def tint_pomo(co):
        m = mancha(co, 80.0, cobertura_a_umbral(0.20))
        return mezcla(BLANCO, T_ORIN, 0.70 * m)
    b.add(V, F, mat=mat_hierro, mtx=M, smooth=True, tint=tint_pomo)
    for sz in (-1, 1):
        z = sz * (T + 0.0004)
        V, F = disc(0.013, segs=16, z=0.0)
        if sz < 0:
            F = [list(reversed(f)) for f in F]
        b.add(V, F, mat=mat_laton, mtx=Matrix.Translation((0.0, Y_POMO, z)), smooth=False)
        # la Q: arco de 300° de radio 9 mm y el rabo hacia −Y
        pts = []
        for i in range(11):
            a = math.radians(120 + 300 * i / 10.0)
            pts.append((math.cos(a) * 0.009, Y_POMO + math.sin(a) * 0.009, z + sz * 0.0012))
        V, F = tube(pts, 0.0016, segs=4)
        b.add(V, F, mat=mat_laton, smooth=True)
        V, F = tube([(0.004, Y_POMO - 0.006, z + sz * 0.0012),
                     (0.011, Y_POMO - 0.013, z + sz * 0.0012)], 0.0016, segs=4)
        b.add(V, F, mat=mat_laton, smooth=True)
    # botón del espigón, en el canto inferior del disco
    V, F = lathe([(0.004, 0.0), (0.006, 0.005), (0.004, 0.008)], segs=8,
                 cap_bottom=True, cap_top=True)
    Rb = Matrix.Rotation(math.pi / 2, 4, 'X')            # z del lathe → −Y
    b.add(V, F, mat=mat_hierro, mtx=Matrix.Translation((0.0, Y_FIN + 0.002, 0.0)) @ Rb,
          smooth=True)


# ------------------------------------------------------------------ marca T
def caja(sx, sy, sz):
    """Caja de 8 vértices centrada, sin chaflán: para detalles de milímetros."""
    hx, hy, hz = sx / 2, sy / 2, sz / 2
    V = [(-hx, -hy, -hz), (hx, -hy, -hz), (hx, hy, -hz), (-hx, hy, -hz),
         (-hx, -hy, hz), (hx, -hy, hz), (hx, hy, hz), (-hx, hy, hz)]
    F = [[0, 3, 2, 1], [4, 5, 6, 7], [0, 1, 5, 4], [1, 2, 6, 5], [2, 3, 7, 6], [3, 0, 4, 7]]
    return V, F


def marca_toledo(b, mat_laton, mat_hierro):
    """Punzón de Toledo en el recazo, cara +Z, a 40 mm de la cruz: escudete de
    latón 9 × 11 mm (relleno, como el perrillo de Julián del Rey «estampado y
    relleno de cobre») con la T en hierro encima."""
    y = Y_CRUZ + 0.040
    z = T_RECAZO / 2
    # cajas planas de 8 vértices (12 tris): un chaflán en 9 mm son 2 px a 7 m
    V, F = caja(0.009, 0.011, 0.0016)
    b.add(V, F, mat=mat_laton, mtx=Matrix.Translation((0.0, y, z + 0.0006)), smooth=False)
    V, F = caja(0.0065, 0.0016, 0.0008)
    b.add(V, F, mat=mat_hierro, mtx=Matrix.Translation((0.0, y + 0.0035, z + 0.0018)), smooth=False)
    V, F = caja(0.0016, 0.007, 0.0008)
    b.add(V, F, mat=mat_hierro, mtx=Matrix.Translation((0.0, y - 0.0005, z + 0.0018)), smooth=False)


# ------------------------------------------------------------------ cinta
def cinta(b, mat):
    """Tira de lana rojo teja 25 × 260 anudada al cuello del pomo; dos colas
    (260 y 180) que cuelgan hacia −Y con una onda. Es el único color cálido y
    el elemento que ondea; en silueta es un triángulo blando junto al pomo."""
    y0 = Y_PUNO0 - CUELLO / 2
    V, F = ico(1)
    M = Matrix.Translation((0.006, y0, 0.011)) @ Matrix.Diagonal((0.011, 0.008, 0.009, 1.0))
    b.add(V, F, mat=mat, mtx=M, smooth=True)
    # Las colas salen del nudo por el lado +X y RODEAN el disco del pomo (radio
    # 35 mm): en v2 cruzaban por delante de la cara del pomo y tapaban la Q.
    for (L, sz, fase) in ((0.260, 1.0, 0.0), (0.180, -0.8, 1.4)):
        pts = [(0.010, y0, 0.012), (0.036, y0 - 0.030, 0.012 * sz),
               (0.050, y0 - 0.075, 0.006 * sz), (0.048, y0 - 0.120, 0.0)]
        n = 4
        for i in range(1, n + 1):
            t = i / n
            pts.append((0.048 - 0.030 * t + 0.012 * math.sin(t * 3.0 + fase),
                        y0 - 0.120 - (L - 0.120) * t,
                        sz * (0.006 + 0.018 * math.sin(t * 2.6 + fase)) * t))
        P = catmull(pts, 9)
        # ancho en X (con up_hint (0,0,1) el ancho caía en Z y la cinta salía de
        # canto en la vista del plano, v1) y un giro de 70° a lo largo para que
        # se vea desde cualquier lado, que es lo que hace una cinta al colgar
        twist = [math.radians(70) * (i / (len(P) - 1)) * sz for i in range(len(P))]
        V, F = sweep(P, [(-0.0125, 0.0), (0.0, 0.0008), (0.0125, 0.0), (0.0, -0.0008)],
                     twist=twist, caps=True, up_hint=(1, 0, 0))
        b.add(V, F, mat=mat, smooth=True)


# ================================================================== construcción
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene
sc.render.fps = 30
sc.render.engine = 'BLENDER_EEVEE_NEXT'
sc.view_settings.view_transform = 'Standard'

# La hoja es de caras PLANAS: cada cara tiene una sola normal, así que la banda
# Glossy→rampa no es una banda, es un interruptor por cara. En v1 con umbral
# 0,70 y spec 0,9 toda la hoja salía blanca y tapaba el orín. A 0,85 solo
# salta cuando la cara está en el ángulo de reflexión: un DESTELLO al girar,
# que es lo que hace una hoja de anime; el resto del tiempo manda el rombo.
M_ACERO = toon_metal("M_Acero", C_ACERO, spec=0.7, umbral=0.85, rough=0.15)
M_FILO = emision_plana("M_Filo", C_FILO)
M_HIERRO = toon_metal("M_Hierro", C_HIERRO, spec=0.6, umbral=0.80, rough=0.30)
M_LATON = toon_metal("M_Laton", C_LATON, spec=0.7, umbral=0.75, rough=0.25,
                     usa_col=False, calida=True)
M_CUERO = toon_metal("M_Cuero", C_CUERO, spec=0.0, calida=True)
M_CINTA = toon_metal("M_Cinta", C_CINTA, spec=0.0, usa_col=False, calida=True)
MATS = [M_ACERO, M_FILO, M_HIERRO, M_LATON, M_CUERO, M_CINTA]
I_ACERO, I_FILO, I_HIERRO, I_LATON, I_CUERO, I_CINTA = range(6)

b = Build()
rangos = {}


def marca(nombre, v0):
    rangos[nombre] = (v0, len(b.bm.verts))


v0 = 0
hoja(b);                         marca("hoja", v0); v0 = len(b.bm.verts)
guarnicion(b, I_HIERRO);         marca("guarnicion", v0); v0 = len(b.bm.verts)
puno(b, I_CUERO, I_HIERRO);      marca("puno", v0); v0 = len(b.bm.verts)
pomo(b, I_HIERRO, I_LATON);      marca("pomo", v0); v0 = len(b.bm.verts)
marca_toledo(b, I_LATON, I_HIERRO); marca("marca", v0); v0 = len(b.bm.verts)
cinta(b, I_CINTA);               marca("cinta", v0); v0 = len(b.bm.verts)

ob = b.finish("Espada", MATS)
me = ob.data

# --- contorno: casco invertido 1,6 mm en metal, 0,8 mm en la cinta (grupo de
# vértices con factor 0,5 para los vértices de peso 0)
vg = ob.vertex_groups.new(name="Contorno")
c0, c1 = rangos["cinta"]
todos = [i for i in range(len(me.vertices)) if not (c0 <= i < c1)]
vg.add(todos, 1.0, 'REPLACE')
vg.add(list(range(c0, c1)), 0.0, 'REPLACE')
mod = contorno(ob, grosor=0.0016, material=material_contorno())
mod.vertex_group = vg.name
mod.thickness_vertex_group = 0.5

ob.visible_shadow = False          # como el cuerpo: que no manche
ob.game.physics_type = 'NO_COLLISION'

# --- propiedades de juego (datos puros; el motor las lee si le hace falta).
# Opcionales: el motor de hoy no las usa. Sirven al RIG e INTEGRACIÓN para
# saber a qué hueso va y qué es.
bpy.context.view_layer.objects.active = ob
ob.select_set(True)
for nombre, valor in (("fl_arma", "espada"), ("fl_arma_hueso", "hand_r")):
    bpy.ops.object.game_property_new(type='STRING', name=nombre)
    ob.game.properties[nombre].value = valor
ob.select_set(False)
# medidas como propiedades ID (para herramientas, no para el motor)
ob["ESPADA_LARGO"] = Y_PUNTA - Y_FIN
ob["ESPADA_HOJA"] = L_HOJA
ob["ESPADA_Y_CRUZ"] = Y_CRUZ
partes = {}
for k, (a, c) in rangos.items():
    P = [me.vertices[i].co for i in range(a, c)]
    partes[k] = [min(p.x for p in P), max(p.x for p in P), min(p.y for p in P),
                 max(p.y for p in P), min(p.z for p in P), max(p.z for p in P)]
ob["ESPADA_PARTES"] = partes

# --- resumen
tris = sum(len(p.vertices) - 2 for p in me.polygons)
xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
print(f"[ES] tris={tris} caras={len(me.polygons)} verts={len(me.vertices)}")
print(f"[ES] bbox X {min(xs)*1000:.1f}..{max(xs)*1000:.1f} mm  "
      f"Y {min(ys)*1000:.1f}..{max(ys)*1000:.1f} mm  Z {min(zs)*1000:.1f}..{max(zs)*1000:.1f} mm")
print(f"[ES] largo total {(Y_PUNTA - Y_FIN)*1000:.1f} mm; hoja {L_HOJA*1000:.0f}; "
      f"cruz en y={Y_CRUZ*1000:.1f}; pomo centro y={Y_POMO*1000:.1f}")
for k, (a, c) in rangos.items():
    n = sum(1 for p in me.polygons if a <= p.vertices[0] < c)
    t = sum(len(p.vertices) - 2 for p in me.polygons if a <= p.vertices[0] < c)
    print(f"[ES]   {k:12s} verts {c-a:5d}  caras {n:5d}  tris {t:5d}")

bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[ES] guardado: {OUT_BLEND}")
