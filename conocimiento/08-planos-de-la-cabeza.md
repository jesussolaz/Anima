# 08 — Los planos de la cabeza

**Este es el fallo estructural de todas las cabezas hechas hasta ahora en el
proyecto.** Una cabeza no es una esfera con rasgos pegados: es una caja
redondeada con **planos planos** bien definidos.

> Un plano plano tallado en la esfera, en el lateral de la cabeza, que va del
> temporal al pómulo. **El plano lateral es lo que da dirección a la cabeza: sin
> él el cráneo parece una esfera con rasgos encima.**

Eso es literalmente lo que tiene Alonso ahora mismo.

## Construcción Loomis: bola y plano

1. **Esfera** para la bóveda craneal.
2. **Cortar un plano plano a cada lado** — del temporal al pómulo. Es lo que
   convierte la esfera en cabeza.
3. **Bloque de mandíbula** cónico colgando por delante y abajo.

Con eso hay cabeza en minutos. Los rasgos vienen después.

## Los seis planos que cargan con el peso visual

1. **Frontal** — encima de la ceja
2. **Temporal** — el lateral de la frente (plano, no curvo)
3. **Pómulo** — encima del cigomático
4. **Mandibular** — el lateral de la cara baja
5. **Laterales de la nariz** — a cada lado del puente
6. **Mentón** — el frente de la masa de la barbilla

## La regla del triángulo invertido

Los planos frontales de la cara forman un **triángulo invertido** que se
estrecha hacia el mentón, mientras que **la parte trasera de la mandíbula es
mucho más ancha**. Esa contradicción —frente ancha por delante, mandíbula ancha
por detrás— es lo que da estructura. Una cara que se estrecha uniformemente
hacia abajo parece un huevo.

## Cómo se aplica en código

No se sacan de una esfera con ruido. Se **tallan** con campos planos:

- Campo lateral: a partir de cierta |x|, **aplanar** empujando hacia el plano
  `x = ±W`, con caída suave hacia delante y hacia atrás.
- Campo temporal: mismo tratamiento más arriba, algo más metido.
- Campo mandibular: plano lateral bajo, más estrecho por delante que por detrás.

La clave es que sean **planos**, no curvas suaves. La transición entre planos
—el "cambio de plano"— es lo que atrapa la luz y da lectura de volumen.

## Fuentes

- [Asaro head: planes of the face — Grid Maker Pro](https://gridmakerpro.com/learn/asaro-head/)
- [Loomis head method: ball-and-plane — Grid Maker Pro](https://gridmakerpro.com/grids/artist-guides/loomis-head/)
- [Planes and Forms of the Head — Proko](https://www.proko.com/course-lesson/planes-and-forms-of-the-head)
- [The Human Head part 1 — canmom](https://canmom.art/animation/the-human-head-1)
