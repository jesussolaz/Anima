# ÁNIMA — banco de medición de personajes
#
#   Flipendo --background <fichero.blend> --python medir_personaje.py -- <objeto>
#
# Mide cualquier humanoide contra el juego de métricas de la biblioteca de
# conocimiento. Sirve para dos cosas: auditar los personajes propios y
# EXTRAER LOS NÚMEROS de personajes de referencia bien hechos, que es la única
# forma de saber a qué se parece "bien" en vez de suponerlo.

import bpy
import sys
from mathutils import Vector


def banda(V, z, tol=0.004):
    return [v for v in V if abs(v.z - z) < tol]


def ancho(V, z, tol=0.004):
    b = banda(V, z, tol)
    return (max(v.x for v in b) - min(v.x for v in b)) if b else 0.0


def medir_menton(V, eye_z):
    """Mentón = mínimo de ANCHURA de cara por debajo de los ojos. Bajando desde
    los ojos la cara se estrecha hasta el mentón; luego el cuello ensancha."""
    mejor, mejor_z, z = None, None, eye_z - 0.030
    while z > eye_z - 0.200:
        a = ancho(V, z, 0.0035)
        if a > 0 and (mejor is None or a < mejor):
            mejor, mejor_z = a, z
        z -= 0.003
    return mejor_z


def medir_ojos(V, top, bottom):
    """Sin marcador de ojo, se estima: la cara es MÁS ANCHA a la altura de los
    pómulos, que va justo bajo la línea de ojos."""
    mejor, mejor_z = 0.0, None
    z = top
    while z > top - (top - bottom) * 0.55:
        a = ancho(V, z, 0.0035)
        if a > mejor:
            mejor, mejor_z = a, z
        z -= 0.003
    return mejor_z, mejor


def medir(ob, nombre):
    M = ob.matrix_world
    V = [M @ v.co for v in ob.data.vertices]
    zmin = min(v.z for v in V)
    V = [Vector((v.x, v.y, v.z - zmin)) for v in V]
    H = max(v.z for v in V)
    eye_z = ob.get("ALONSO_EYE_Z")
    if eye_z is not None:
        eye_z -= zmin
    else:
        eye_z, _ = medir_ojos(V, H, H * 0.80)
    chin = medir_menton(V, eye_z) or (eye_z - H * 0.06)
    HH = H - chin

    # NO se mide "ancho de hombros" por anchura máxima: en pose A eso mide los
    # BRAZOS, no los hombros, y depende del ángulo de la pose. Comparar dos
    # personajes así es comparar poses, no diseños. Se usan métricas que no
    # dependen de la pose.
    head_w = max(ancho(V, chin + (H - chin) * f, 0.004) for f in (0.35, 0.5, 0.65))
    head_d = 0.0
    for v in V:
        if v.z > chin:
            head_d = max(head_d, abs(v.y))
    head_d *= 2
    # entrepierna: el punto más alto donde el eje deja de tener malla continua
    crotch = None
    z = H * 0.60
    while z > H * 0.35:
        if not [v for v in V if abs(v.x) < H * 0.012 and abs(v.z - z) < 0.006]:
            crotch = z
            break
        z -= 0.004

    print(f"=== {nombre}")
    print(f"  altura              {H:.4f} m")
    print(f"  alto de cabeza      {HH:.4f} m")
    print(f"  CABEZAS DE ALTO     {H / HH:.2f}")
    print(f"  LINEA DE OJOS       {(eye_z - chin) / HH * 100:.1f}% del alto de cabeza")
    print(f"  CRANEO              {(H - eye_z) / HH * 100:.1f}%")
    print(f"  ancho de cara       {ancho(V, eye_z):.4f} m")
    print(f"  ancho de cabeza     {head_w:.4f} m")
    print(f"  ANCHO/ALTO CABEZA   {head_w / HH:.3f}   (estilizado ~0.95, realista ~0.86)")
    print(f"  PROFUNDIDAD/ALTO    {head_d / HH:.3f}")
    if crotch:
        print(f"  ENTREPIERNA         {crotch / H * 100:.1f}% de la altura (ideal 50%)")
    print(f"  verts               {len(V)}")


argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
objetivos = argv if argv else [o.name for o in bpy.data.objects if o.type == 'MESH']
for n in objetivos:
    ob = bpy.data.objects.get(n)
    if ob and ob.type == 'MESH' and len(ob.data.vertices) > 500:
        try:
            medir(ob, n)
        except Exception as e:
            print(f"=== {n}: no medible ({e})")
