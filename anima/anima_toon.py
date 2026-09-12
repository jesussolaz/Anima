# ÁNIMA — materiales toon y contorno compartidos (carril ROPA)
#
# Copia literal de toon()/sombra_de() y del contorno de casco invertido de
# gen_alonso.py, en módulo aparte para que la ropa (gen_alonso_ropa.py) use
# EXACTAMENTE el mismo sombreado que el cuerpo sin tocar gen_alonso.py mientras
# el carril PELO lo tiene abierto. Al integrar se unifica: gen_alonso.py debe
# importar de aquí y borrar sus copias. Mientras haya dos copias, cualquier
# cambio de sombreado se hace en las dos o el cuerpo y la ropa dejarán de casar.
#
# Uso:
#   sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
#   from anima_toon import toon, sombra_de, material_contorno, contorno
#
# Reglas de conocimiento/11: Diffuse -> Shader to RGB -> ColorRamp CONSTANT;
# la sombra desplaza el tono (piel al rojo, resto al azul); contorno = Solidify
# de grosor negativo con normales invertidas y material negro con backface
# culling; grosor en unidades de mundo, calibrado a 1,68 m: 1,3 mm cuerpo,
# 1,6 mm pelo, 0,6 mm ojos. Para la ropa ver GROSOR_CONTORNO_ROPA abajo.

import bpy

# Grosor de contorno por prenda, en metros (misma escala que el cuerpo: 1,3 mm).
# Las prendas grandes llevan el grosor del cuerpo; las pequeñas (guantes,
# pañuelo) algo menos para que la línea no se coma la forma.
GROSOR_CONTORNO_ROPA = {
    "cuerpo": 0.0013,
    "prenda": 0.0013,
    "pequeña": 0.0009,
}


def sombra_de(color, calida=False, fuerza=0.62):
    """El color de sombra DESPLAZA EL TONO, no solo oscurece (conocimiento/11).
    Piel hacia el rojo; el resto hacia el azul/púrpura.

    NO se hace sumando al matiz: sumarle a un marrón (matiz ~0,05) lo lleva al
    amarillo-verde, no al azul. Se MEZCLA hacia un tinte objetivo en RGB, que
    funciona sea cual sea el color de partida.
    """
    tinte = (0.62, 0.26, 0.20) if calida else (0.24, 0.26, 0.48)
    k = 0.30
    return tuple(max(0.0, min(1.0, c * fuerza * (1 - k) + t * k * fuerza))
                 for c, t in zip(color, tinte))


def toon(name, color, calida=False, bandas=2, fuerza=0.62, spec=0.0,
         aniso=False, usa_col=False, umbral=0.62, spec_col=None,
         banda_z=None):
    """Cel shader de EEVEE: Diffuse BSDF -> Shader to RGB -> Color Ramp en
    CONSTANT. Sin esto los personajes salen como figuras de plástico
    fotografiadas: el PBR realista no sirve para este estilo."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    dif = nt.nodes.new("ShaderNodeBsdfDiffuse")
    dif.inputs["Color"].default_value = (1, 1, 1, 1)
    s2r = nt.nodes.new("ShaderNodeShaderToRGB")      # la pieza clave, solo EEVEE
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = 'CONSTANT'       # bandas duras, no degradado
    som = sombra_de(color, calida, fuerza)
    med = sombra_de(color, calida, (fuerza + 1.0) * 0.5)
    ramp.color_ramp.elements[0].position = 0.0
    ramp.color_ramp.elements[0].color = (*som, 1.0)
    if bandas >= 3:
        e = ramp.color_ramp.elements.new(0.36)
        e.color = (*med, 1.0)
    ramp.color_ramp.elements[-1].position = 0.52
    ramp.color_ramp.elements[-1].color = (*color, 1.0)
    emi = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(dif.outputs["BSDF"], s2r.inputs["Shader"])
    nt.links.new(s2r.outputs["Color"], ramp.inputs["Fac"])
    salida = ramp.outputs["Color"]

    if usa_col:
        # El atributo "Col" que escribe Build.add NO se leía: todos los tint=
        # se perdían en silencio, y por eso el iris solo tenía dos colores
        # (verde y el marrón de la ceja) en vez de anillo limbal, cuerpo,
        # realce y pupila. Va MULTIPLICANDO la rampa, no sustituyéndola, para
        # no perder las bandas del cel. Es opt-in porque un objeto sin la capa
        # devolvería negro, y la malla del cuerpo no la tiene.
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
        # brillo: en el pelo es una BANDA que recorre la cabeza, no un punto
        gl = nt.nodes.new("ShaderNodeBsdfGlossy")
        gl.inputs["Roughness"].default_value = 0.22 if not aniso else 0.38
        if aniso and "Anisotropy" in gl.inputs:
            gl.inputs["Anisotropy"].default_value = 0.85
        g2r = nt.nodes.new("ShaderNodeShaderToRGB")
        gramp = nt.nodes.new("ShaderNodeValToRGB")
        gramp.color_ramp.interpolation = 'CONSTANT'
        gramp.color_ramp.elements[0].position = 0.0
        gramp.color_ramp.elements[0].color = (0, 0, 0, 1)
        # El umbral decide el GROSOR de la banda. A 0,62 con el glossy ancho
        # del pelo la banda se comía media cabeza y, siendo un ADD gris sobre
        # castaño oscuro, salía blanco rosáceo: leía como calvas, no como brillo.
        gramp.color_ramp.elements[1].position = umbral
        # el brillo del pelo es el propio color aclarado, no gris: un ADD gris
        # desatura y rompe la gama
        sc_ = spec_col if spec_col is not None else (1.0, 1.0, 1.0)
        gramp.color_ramp.elements[1].color = (sc_[0] * spec, sc_[1] * spec,
                                              sc_[2] * spec, 1.0)
        add = nt.nodes.new("ShaderNodeMix")
        add.data_type = 'RGBA'
        add.blend_type = 'ADD'
        add.inputs["Factor"].default_value = 1.0
        nt.links.new(gl.outputs["BSDF"], g2r.inputs["Shader"])
        nt.links.new(g2r.outputs["Color"], gramp.inputs["Fac"])
        nt.links.new(salida, add.inputs["A"])
        nt.links.new(gramp.outputs["Color"], add.inputs["B"])
        salida = add.outputs["Result"]

    if banda_z is not None:
        # BRILLO DEL PELO. No es un reflejo: en anime es un elemento de DISEÑO,
        # una banda a una ALTURA FIJA de la cabeza que no se mueve con la luz.
        # Con un glossy salían tres manchas sueltas siguiendo los huecos entre
        # mechones —leían como calvas— y subir el umbral casi no las estrechó,
        # porque el lóbulo satura sobre una superficie tan ancha.
        # Va por LATITUD alrededor del centro del cráneo, no por altura: una
        # banda de Z plana corta la cabeza en línea recta y lee como una cinta.
        # Tomando la dirección desde el centro y midiendo su componente Z sale
        # un paralelo de esfera, que de frente arquea hacia abajo por los lados
        # —que es como se dibuja.
        centro, lat, grosor, bcol = banda_z
        geo = nt.nodes.new("ShaderNodeNewGeometry")
        res = nt.nodes.new("ShaderNodeVectorMath"); res.operation = 'SUBTRACT'
        res.inputs[1].default_value = centro
        nt.links.new(geo.outputs["Position"], res.inputs[0])
        nor = nt.nodes.new("ShaderNodeVectorMath"); nor.operation = 'NORMALIZE'
        nt.links.new(res.outputs["Vector"], nor.inputs[0])
        sep = nt.nodes.new("ShaderNodeSeparateXYZ")
        nt.links.new(nor.outputs["Vector"], sep.inputs["Vector"])
        mr = nt.nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = lat - 0.50
        mr.inputs["From Max"].default_value = lat + 0.50
        nt.links.new(sep.outputs["Z"], mr.inputs["Value"])
        br = nt.nodes.new("ShaderNodeValToRGB")
        br.color_ramp.interpolation = 'CONSTANT'
        br.color_ramp.elements[0].position = 0.0
        br.color_ramp.elements[0].color = (0, 0, 0, 1)
        br.color_ramp.elements[1].position = 0.5 - grosor
        br.color_ramp.elements[1].color = (*bcol, 1.0)
        e2 = br.color_ramp.elements.new(0.5 + grosor)
        e2.color = (0, 0, 0, 1)
        nt.links.new(mr.outputs["Result"], br.inputs["Fac"])
        # se apaga en la zona en sombra: una banda que brilla en el lado oscuro
        # delata que es un truco
        puerta = nt.nodes.new("ShaderNodeValToRGB")
        puerta.color_ramp.interpolation = 'CONSTANT'
        puerta.color_ramp.elements[0].position = 0.0
        puerta.color_ramp.elements[0].color = (0.12, 0.12, 0.12, 1)
        puerta.color_ramp.elements[1].position = 0.50
        puerta.color_ramp.elements[1].color = (1, 1, 1, 1)
        nt.links.new(s2r.outputs["Color"], puerta.inputs["Fac"])
        gate = nt.nodes.new("ShaderNodeMix")
        gate.data_type = 'RGBA'; gate.blend_type = 'MULTIPLY'
        gate.inputs["Factor"].default_value = 1.0
        nt.links.new(br.outputs["Color"], gate.inputs["A"])
        nt.links.new(puerta.outputs["Color"], gate.inputs["B"])
        sumb = nt.nodes.new("ShaderNodeMix")
        sumb.data_type = 'RGBA'; sumb.blend_type = 'ADD'
        sumb.inputs["Factor"].default_value = 1.0
        nt.links.new(salida, sumb.inputs["A"])
        nt.links.new(gate.outputs["Result"], sumb.inputs["B"])
        salida = sumb.outputs["Result"]

    nt.links.new(salida, emi.inputs["Color"])
    nt.links.new(emi.outputs["Emission"], out.inputs["Surface"])
    m.diffuse_color = (*color, 1.0)
    return m


def material_contorno(nombre="M_Contorno"):
    """Material del casco invertido: emisión casi negra con Backface Culling.
    Si ya existe uno con ese nombre en el fichero (el del cuerpo, creado por
    gen_alonso.py) se REUTILIZA: dos materiales de contorno distintos en el
    mismo personaje son dos negros que un día dejarán de ser iguales."""
    m = bpy.data.materials.get(nombre)
    if m is not None and m.use_nodes and m.use_backface_culling:
        return m
    m = bpy.data.materials.new(nombre)
    m.use_nodes = True
    nt = m.node_tree
    for n in list(nt.nodes):
        nt.nodes.remove(n)
    o = nt.nodes.new("ShaderNodeOutputMaterial")
    e = nt.nodes.new("ShaderNodeEmission")
    e.inputs["Color"].default_value = (0.02, 0.015, 0.02, 1.0)
    nt.links.new(e.outputs["Emission"], o.inputs["Surface"])
    m.use_backface_culling = True
    m.diffuse_color = (0, 0, 0, 1)
    return m


def contorno(obj, grosor=0.0013, nombre="Contorno", material=None):
    """Casco invertido IGUAL que el del cuerpo en gen_alonso.py: Solidify de
    grosor negativo, offset 1, normales invertidas, sin borde (rim), material
    del casco en la última ranura. Grosor en metros de mundo."""
    mat = material or material_contorno()
    if mat.name not in [m.name for m in obj.data.materials if m]:
        obj.data.materials.append(mat)
    idx = [m.name if m else None for m in obj.data.materials].index(mat.name)
    m = obj.modifiers.new(nombre, 'SOLIDIFY')
    m.thickness = -grosor
    m.offset = 1.0
    m.use_flip_normals = True
    m.use_rim = False
    m.material_offset = idx
    m.material_offset_rim = idx
    return m
