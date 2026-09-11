# 05 — Pelo

En este estilo el pelo es **la mitad de la personalidad** del personaje. Y se
construye al revés de como yo lo estaba haciendo.

## El orden correcto

1. **Cráneo y línea del pelo primero.** Sin saber dónde nace, todo lo demás
   flota.
2. **Silueta completa antes que ningún mechón.** Se bloquea la forma global —
   la mancha que se vería a contraluz — y se juzga ESA. Si la silueta no
   funciona, ningún detalle la salva.
3. **Grandes mechones**, no cientos de pelos. El pelo se piensa como una forma
   3D que envuelve la cabeza.
4. **Subdividir** progresivamente para el detalle fino, ya con la silueta fijada.

> Empezar por los mechones sueltos y esperar que la silueta emerja **no
> funciona**. Es el error que se cometió aquí.

## Construcción en 3D

- **Casquete** que cubre el cuero cabelludo, para que no se vea piel entre
  mechones. Se ajusta con el modificador **Shrinkwrap** en modo *Nearest Surface
  Point*, no lanzando rayos: una cabeza **no es convexa** y un rayo desde el
  centro choca con el pómulo o la nariz antes que con el cráneo.
- **Mechones**: tiras de malla o curvas con *bevel* y perfil de *taper*.
- Un mechón **mantiene su grosor y se afila solo al final**. Un cono que se
  estrecha desde la raíz es una aguja, no un mechón.
- Bajo coste primero, detalle después.

## Errores cometidos, para no repetirlos

- Mechones como conos de revolución → agujas.
- Flequillo demasiado largo → tapa los ojos, que es lo que hay que ver.
- Casquete ajustado por raycast → lengüetas dentadas sobre la cara.
- Mechones siguiendo la normal del cráneo → erizo. Tienen que seguir un **flujo**
  (caen, o van hacia arriba y atrás); la normal solo despega la raíz.

## Fuentes

- [Make Stylized Anime 3D Hair In Blender — yelzkizi](https://yelzkizi.org/make-stylized-anime-hair-flow-in-blender/)
- [Hair Modeling – Anime Hair is Difficult — 3DCG暮らし](https://tohawork.com/en/hairmodeling)
- [Shrinkwrap Hair Curves — Manual de Blender](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/hair/deformation/shrinkwrap_hair_curves.html)
- [Anime Hair Drawing Techniques — skyryedesign](https://skyryedesign.com/art/drawing/body/anime-hair-drawing-techniques/)
