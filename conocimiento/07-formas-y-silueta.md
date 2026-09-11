# 07 — Formas y silueta: el orden que nunca hay que saltarse

La regla que resume todo el oficio:

> **Los detalles no arreglan formas malas: solo las señalan.**

Si se corre al detalle antes de resolver silueta y proporción, se acaba puliendo
algo que estructuralmente no lee. Es exactamente el error que se ha cometido aquí
una y otra vez: pestañas y mechones antes de tener una silueta válida.

## Jerarquía obligatoria

| Fase | Qué se resuelve | Qué NO se toca |
|---|---|---|
| **1. Primarias (bloqueo)** | Silueta, volúmenes grandes, proporciones | absolutamente nada más |
| **2. Secundarias** | Grupos musculares, almohadillas de grasa, rasgos, puntos óseos | detalle fino |
| **3. Terciarias** | Arrugas, poros, pequeñas imperfecciones | — |

En la fase 1 **la silueta es el rey**. Si la silueta no lee vista completamente
en negro, no hay detalle que la salve.

## LA PRUEBA DE LA SILUETA (ejecutable)

Es una comprobación objetiva, no una opinión, y se puede automatizar:

1. Renderizar el personaje **totalmente en negro sobre fondo blanco**.
2. Mirar SOLO la mancha.
3. ¿Se reconoce quién es? ¿Se distingue la cabeza del pelo, el pelo del cuerpo?
4. Si la mancha es un borrón informe, **volver a la fase 1**. No seguir.

En ÁNIMA esto lo hace `anima/prueba_silueta.py`. Hay que pasarlo **antes** de
añadir un solo detalle.

## Lenguaje de formas

La geometría comunica antes que cualquier otra cosa:

| Forma | Lee como | Se usa en |
|---|---|---|
| **Círculo** | blando, cercano, inofensivo, infantil | héroes jóvenes, acompañantes, criaturas tiernas |
| **Cuadrado** | estable, fiable, fuerte, con peso | héroes sólidos, figuras de autoridad |
| **Triángulo** | afilado, peligroso, rápido, inestable | villanos, amenazas, velocidad |

Hay que **definir la forma dominante** del personaje: es la que fija la primera
impresión. Mezclar formas da personajes más ricos, pero una tiene que mandar.

Aplicado a ÁNIMA:
- **Alonso**: círculo dominante (juventud, nobleza, cercanía) con algo de
  triángulo en la silueta de la ropa y la espada (aventura, filo).
- **Wukong**: triángulo (velocidad, travesura, inestabilidad).
- **Bajie**: círculo puro y grande (comodidad, bonachón).
- **Celestina**: triángulo afilado sobre base estrecha.
- **Pesadillas**: triángulo, sin excepción.

## Fuentes

- [Sculpting Issue: Primary, Secondary and Tertiary Shapes — Polycount](https://polycount.com/discussion/233026/sculpting-issue-primary-secondary-and-tertiary-shapes)
- [Character Sculpting — Hitem3D](https://www.hitem3d.ai/blog/en-Character-Sculpting-How-to-Create-Expressive-3D-Characters-from-Scratch/)
- [Shape Language in Character Design — Pixune](https://pixune.com/blog/shape-language-technique/)
- [Shape Language in Video Games — ejaw](https://ejaw.net/shape-language-in-character-design/)
