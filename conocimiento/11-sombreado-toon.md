# 11 — Sombreado toon

**Este capítulo faltaba entero, y es probablemente el mayor de los fallos del
proyecto.** Los personajes de ÁNIMA se han venido sombreando con PBR realista
—Principled BSDF con subsurface— y este estilo **no se sombrea así**. Por bien
modelada que esté una cara, con PBR va a parecer una figura de plástico
fotografiada, no un dibujo.

## 1. Gestión de color: lo PRIMERO que hay que cambiar

`Render Properties → Color Management → View Transform = **Standard**`

El valor por defecto de Blender es **AgX**, diseñado para fotorrealismo, y
**comprime justo los colores planos y saturados en los que se apoya el estilo**.
Con AgX todo sale lavado y pastel.

> Todos los renders de personaje de este proyecto se han hecho con AgX. Eso
> explica por sí solo buena parte del aspecto apagado.

## 2. El nodo clave: Shader to RGB

La cadena mínima de un cel shader en EEVEE:

```
Diffuse BSDF  →  Shader to RGB  →  Color Ramp (Constant)  →  Material Output
```

- **Diffuse BSDF**, no Principled. Se quiere la luz cruda, sin especular PBR.
- **Shader to RGB** convierte el resultado de iluminación en datos de color
  manipulables. Es la pieza que lo hace posible, y es **exclusiva de EEVEE**.
- **Color Ramp en interpolación `Constant`**, no `Linear`. Cada parada del
  degradado es una **banda dura** de sombreado.
  - **2 paradas** = dos tonos, el clásico anime.
  - **3 paradas** = con tono medio.
- El resultado del ramp se **multiplica** sobre el color base.

## 3. El color de la sombra NO es el color base oscurecido

Es el error de principiante. La sombra **desplaza el tono**:

| Zona | Desplazamiento |
|---|---|
| **Piel** | hacia el **rojo/cálido**, y se elige una variación más oscura de ese tono |
| **General / cine anime** | hacia el **púrpura/azul**, +0,05 a +0,12 de matiz |

## 4. Iluminación

**Un solo `Sun`** da el corte más limpio entre bandas. Muchas luces ensucian el
terminador y las bandas dejan de leerse. Al contrario que en PBR, aquí menos luz
es mejor.

## 5. Contorno: casco invertido (inverted hull)

1. Material `Contorno`, negro plano, con **Backface Culling activado**.
2. Modificador **Solidify** sobre el objeto:
   - **Thickness** pequeño y negativo (el casco crece hacia fuera).
   - **Normals → Flip** activado.
   - **Materials → Material Index = 1** (apunta al material de contorno).
3. Solo funciona en **EEVEE**.

**Trampa**: el grosor va en **unidades de mundo**, así que cambia con la escala
del objeto y con la distancia de cámara. Un personaje de 1,68 m necesita otro
número que un molino.

## 6. Pelo

El brillo del pelo anime **no es un punto especular: es una banda** que recorre
la cabeza. Se consigue con especular **anisótropo** (modelo Kajiya-Kay de
mechón). Puede llevar su propio ramp de sombra, aparte del de la piel.

## 7. Cara: normales esferizadas — el problema del "blob face"

**Lo más importante de este capítulo después del Shader to RGB.**

Las caras cartoon se ven mal iluminadas porque **no están esculpidas como se las
va a iluminar**: nariz, labios y cuencas proyectan sombras que delatan que es un
modelo 3D y no una ilustración. Es el llamado *blob face*.

La solución profesional (la de Arc System Works, entre otros) es **editar las
normales de vértice de la cara para que apunten como si fuese una esfera lisa**.
Así la cara sombrea como un volumen limpio y las sombras quedan en degradado de
ilustración, sin que la nariz manche.

Cómo se hace en Blender:
- **Data Transfer**: se copian las normales de una esfera colocada en la cabeza.
- O el complemento **Abnormal**, o la función "Sphereize Normals", moviendo la
  esfera hasta que las normales de la nariz apunten al frente.

## Fuentes

- [How to Get an Anime / Toon Look in Blender (2026) — StraySpark](https://www.strayspark.studio/blog/how-to-get-anime-toon-look-blender)
- [Toon Shading Effect in Blender — Yarsa DevBlog](https://blog.yarsalabs.com/basic-toon-shader-in-blender/)
- [CEL Shading in Blender — Artisticrender](https://artisticrender.com/cel-shading-in-blender/)
- [Inverse Hull Method — NPR Wiki](https://bnpr.gitbook.io/bnpr/outline/inverse-hull-method)
- [Normal Spherizing using Abnormal — NPR Wiki](https://bnpr.gitbook.io/bnpr/shaders/toon-shading-nbpr-abnormal-normal-sphering)
- [How to edit vertex normals for Anime / Toon shading — Polycount](https://polycount.com/discussion/207661/how-to-edit-vertex-normals-for-anime-toon-shading-in-blender-arc-system-works-inspired)
- [Anime skin shading — Clip Studio Tips](https://tips.clip-studio.com/en-us/articles/4413)
- [How to Make Anisotropic Hair — BlenderNation](https://www.blendernation.com/2020/04/09/how-to-make-anisotropic-hair/)
