# 14 — Modelar la cara: orden de operaciones

Sacado de estudiar a un modelador construyendo una cara anime de principio a fin.
Es el **orden concreto** que faltaba: hasta ahora se deformaba una base sin saber
cómo se construye una cara desde cero.

## EL HALLAZGO: la cara anime en 3D es PUNTIAGUDA

> «Las narices de personaje anime recuerdan más al **pico de un pájaro** que a
> una nariz real; de hecho **la cara en general es bastante puntiaguda** cuando
> se hace en 3D. Es necesario para que el modelo mantenga la ilusión del dibujo a
> mano desde varios ángulos, **mientras el cel-shading esconde su forma
> extraña**.»

Esto lo cambia todo. La geometría de una cara anime **no es anatómicamente
plausible a propósito**: es rara, angulosa y apuntada, y el sombreado plano la
disimula. Todo el trabajo previo del proyecto iba en la dirección contraria —
suavizar la cara para que resultara creíble— y por eso no leía.

## Orden de construcción

1. **Espejo activado** y arrancar con **un solo plano en la punta de la nariz**.
2. **Rasgos principales primero**: nariz → ojo → oreja.
3. Después **líneas guía** (la mandíbula) que sirven para rellenar el volumen.
4. Rellenar el resto de la cara.
5. Labios.
6. Cejas.
7. Lo último y lo menos agradecido: **cráneo, parte de atrás y unión al cuello**.

### Nariz
Bucles: uno que secciona la punta; un arco superior que ordena el flujo; un
bucle gemelo del primero para rellenar entre ambos; y una línea desde la
transición nariz–labio superior hasta el nacimiento de la ceja, que define el
contorno. Rellenar y cortar bucles.

### Ojo
Bucle de **16 caras** — «con la mitad bastaría» de cara a subdividir después.
Desde el ojo se puentea a nariz y ceja.

### Oreja
Se extruye desde el ojo. **Genshin y Honkai Star Rail resuelven la oreja como un
plano liso con la textura pintada.** Es una opción legítima y mucho más barata.

### Mandíbula
Un bucle desde la oreja a lo largo de la mandíbula que **NO llega a la punta del
mentón: muere por debajo, en punta**.

### Labios
Contorno general, con **cuadriláteros en las comisuras** para poder extruir
hacia dentro. Y **el interior del labio hay que extruirlo**: sin bucle interior,
al abrir la boca la geometría colapsa. Lo difícil es que los bordes superior e
inferior no se solapen.

### Coronilla
**Un solo vértice y una tapa triangulada.** La geometría del cráneo da igual:
la tapa el pelo o se enmascara entera. Así está hecha la cabeza de Katalina en
*Granblue Fantasy Versus*.

## Topología: la regla de "todo cuadriláteros" tiene excepción

Alrededor de la boca se pueden **triangular** unas cuantas caras. Es práctica
válida en personajes cel-shaded —la usan estudios como Arc System Works— porque
**esa zona se deforma mucho con las expresiones y, con demasiada geometría,
aparecen artefactos de sombreado**.

**Con shaders difusos normales esto sería mala práctica.** Es específico del
sombreado plano.

Regla general que se deduce: **en cel-shading, menos geometría en las zonas que
más se deforman.** Al revés de lo que pide el PBR realista.

## Subdivisión y presupuesto

- Se modela con densidad moderada, se **disuelven** las aristas que no definen
  forma, y luego se aplica **Subdivision**.
- Los **creases** (pliegues de arista) le dicen a la subdivisión dónde apretar.
- La subdivisión **cuadruplica** la geometría. Para juego, hay que optimizar
  después: disolver todo lo que no defina silueta.

## Fuentes

- [How to Model Anime Faces in Blender 3D](https://www.youtube.com/watch?v=sc4BBQJ0QEQ) (transcripción estudiada)
- [Face Topology Guide — VSQUAD](https://vsquad.art/blog/modeling-guide-to-achieving-good-face-topology)
- [Anime face topology: bucles conectados o separados — Blender Artists](https://blenderartists.org/t/which-topology-works-better-for-an-anime-face-connected-eye-and-mouth-loops-or-separated/1552599)
