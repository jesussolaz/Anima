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

## El método de mechones (2026-09-12)

Sacado de transcribir un tutorial de pelo pincho y de un resumen de modelado de
pelo anime. Es el método que faltaba, y corrige una lección que habíamos sacado
mal.

**Un mechón es un BARRIDO sobre una curva**, no un cono ni un trozo de chapa:

1. Una **curva de camino** marca el recorrido del mechón.
2. Una **sección cerrada** se barre a lo largo de ella. La sección **NO es un
   círculo**: se le sacan **esquinas afiladas** (cuña con dos puntas laterales y
   una cresta). Con sección redonda el mechón lee como manguera; son las aristas
   vivas las que dan la faceta de pelo, y las que el cel-shading convierte en
   corte limpio.
3. **Raíz gruesa, punta afilada**: se estrecha solo al final. Estrechar desde la
   raíz da una aguja.
4. **Torsión** a lo largo del camino para los que se rizan.
5. El peinado se monta **duplicando y colocando a mano**, no con partículas,
   porque así se controla. Y la frase clave del tutorial: *"lo único que hay es
   variación de tamaño y escala"*. **Grandes, medianos y finos, superpuestos.**
   Una fila de mechones iguales delata que son piezas repetidas.

### La lección que teníamos mal

Después de que 73 conos sueltos fallaran, la conclusión escrita fue *"las púas
no son conos independientes: son UNA superficie continua"*. **Era la conclusión
equivocada.** Lo que falló fue la **forma** de los conos (agujas) y que **no
había masa debajo** — no el hecho de usar mechones. El recuento de piezas era
una correlación, no la causa.

La estructura buena tiene **las dos cosas**:

- **Casquete + lámina de flequillo continua**: tapa el cuero cabelludo y
  proyecta **una** sombra sólida en la frente. Sin ella, la luz se cuela entre
  los mechones y raya la cara a franjas.
- **Mechones encima**: dan el volumen y la silueta. Una cáscara pegada al cráneo
  no tiene volumen propio por mucho que se le module el borde — lee como una
  bolsa de plástico estirada.

### Números que costaron varias vueltas

- `salida` (cuánto se despega el mechón de la normal del cráneo) es el parámetro
  delicado: **en la coronilla la normal apunta ARRIBA**. A 1,0 salen astas de
  ciervo; a 0,06 no facetan nada y vuelve la cúpula lisa. **0,17 es el término
  medio**: se ve el canto de cada lámina sin que rompa la línea del cráneo.
- Los mechones de coronilla que **cruzan el perfil superior** asoman como
  nudillos. Van hacia **atrás**, no hacia arriba, y con la raíz **escalonada**.
- Grosor de sección: flequillo 0,32, coronilla 0,27, laterales 0,24. Más de
  0,35 y son tubos.

## Fuentes

- [Make Stylized Anime 3D Hair In Blender — yelzkizi](https://yelzkizi.org/make-stylized-anime-hair-flow-in-blender/)
- [Hair Modeling – Anime Hair is Difficult — 3DCG暮らし](https://tohawork.com/en/hairmodeling)
- [Shrinkwrap Hair Curves — Manual de Blender](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/hair/deformation/shrinkwrap_hair_curves.html)
- [Anime Hair Drawing Techniques — skyryedesign](https://skyryedesign.com/art/drawing/body/anime-hair-drawing-techniques/)
- [Blender Tutorial – How to Make Anime Hair (Tomorrow Films)](https://www.youtube.com/watch?v=8AdaAj6Ac5k) — transcrito; de aquí sale el método de barrido y la frase de la variación de tamaño
