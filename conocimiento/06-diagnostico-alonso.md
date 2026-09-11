# 06 — Diagnóstico de Alonso

Medidas reales del modelo actual (`anima/Alonso.blend`) contra las reglas de las
fichas anteriores. Sin esto, "la cara no acaba de funcionar" es una opinión;
con esto es una lista de tareas.

## Cómo se mide

El mentón se localiza **escaneando el perfil frontal**: se baja en z tomando el
vértice más adelantado del eje, y el mentón es el último antes de que el perfil
**retroceda de golpe** (ahí empieza el cuello). Medirlo con un umbral de altura
da mal: coge el cuello o el pecho.

## Medidas ANTES de aplicar las correcciones

| Medida | Alonso hoy | Objetivo | Estado |
|---|---|---|---|
| Altura total | 1,680 m | 1,68 m (15-16 años) | correcto |
| Alto de cabeza | 0,255 m | — | — |
| **Cabezas de alto** | **6,59** | 6,5 (adolescente) | **correcto** |
| **Línea de ojos** (desde mentón) | **55,2 %** | 40-46 % | **mal: 10 puntos alta** |
| **Cráneo** (ojos → coronilla) | **44,8 %** | 54-60 % | **mal: cráneo pequeño** |
| Ancho de cara en los ojos | 0,188 m | — | — |
| Ancho de ojo | 0,055 m (**29 %** de la cara) | 33 % o más | mejorable |
| Separación interpupilar | 0,072 m (38 % de la cara) | ~un ojo en medio | aceptable |

## El hallazgo

**Los ojos están demasiado ALTOS, no demasiado bajos.** Al 55 % están incluso
por encima del punto realista (50 %), cuando el estilo pide 40-46 %.

Y la consecuencia es la que explica por qué la cara "lee adulta" pese a tener
ojos grandes: el cráneo por encima de los ojos se queda en el 44,8 % cuando
debería rondar el 55 %. **Falta bóveda craneal.** Sin ella no hay lectura de
juventud — y además no hay sitio donde montar el pelo, que en este estilo es
medio personaje.

Durante el desarrollo se asumió que los ojos estaban al 47 % y se derivaron de
ahí el centro de cabeza y otras medidas. **Esa suposición era falsa**, y arrastró
error a todo lo demás.

## Medidas DESPUÉS (2026-09-11)

| Medida | Antes | Ahora | Objetivo |
|---|---|---|---|
| Cabezas de alto | 7,8-8,2 | **6,59** | 6,5 |
| Línea de ojos | 55,2 % | **44,7 %** | 40-46 % |
| Cráneo | 44,8 % | **55,3 %** | 54-60 % |
| Ancho de ojo | 29 % | **34 %** | 33-35 % |

Los cuatro en rango. Cómo se hizo: un **remapeo vertical de la cabeza** que
comprime lo que hay bajo los ojos y expande lo que hay encima, dejando mentón y
coronilla fijos; más `HEAD_SCALE` a 1,34 para bajar de 8 a 6,6 cabezas.

### Medir el mentón: cuatro intentos hasta dar con uno estable

Es más difícil de lo que parece y dio números contradictorios durante todo el
proceso. Lo que **no** funciona:

1. **Umbral de altura** → coge el cuello o el pecho. Daba 5,08 cabezas.
2. **"Primer salto hacia delante" bajando desde la coronilla** → la curva del
   cráneo ya produce retrocesos. Daba un mentón por encima de los ojos.
3. **"Lo que sobresale respecto al cuello"** → el pecho también sobresale; el
   resultado dependía de dónde arrancara el escaneo.
4. **El grupo anatómico `joint-jaw`** → está 2 cm por encima del mentón real.

Lo que **sí** funciona: **el mínimo de ANCHURA de cara por debajo de los ojos**.
Bajando desde los ojos la cara se estrecha hasta el mentón y a partir de ahí el
cuello vuelve a ensanchar. Ese mínimo es estable y no depende del arranque.

### Un fallo silencioso que conviene recordar

`CLAV_L` y `WRIST_L` se leían **después** de podar la geometría auxiliar, y la
poda borra justo los grupos `joint-*`. `group_centroid` devolvía `None` sin
avisar, así que el ensanche de hombros y el agrandado de manos **llevaban tiempo
sin hacer nada**. Las referencias se toman ahora antes de podar.

---

## Lista de correcciones, por impacto

1. **Bajar la línea de ojos del 55 % al ~44 %** del alto de cabeza. Equivale a
   crecer la bóveda craneal por encima de los ojos, no a mover los ojos hacia el
   mentón (eso alargaría la frente al revés).
2. **Comprimir el tercio inferior** (nariz → mentón). Es lo que más edad quita.
3. **Ensanchar el ojo** del 29 % al 33-35 % del ancho de cara.
4. **Meter el iris bajo el párpado superior.** Hoy flota con blanco alrededor,
   que es la expresión de sorpresa o de muñeco, no la mirada en reposo.
5. **Rehacer el pelo empezando por la silueta**, no por los mechones.
6. Verificar entrepierna y muñecas en la mitad de la altura.

## Pendiente

- El cuerpo aún lee más joven de lo debido: con la cabeza ya a proporción de
  adolescente, el torso se queda estrecho. Se ensancharon hombros un 15 %, pero
  hace falta más volumen de pecho y espalda.
- `joint-l-wrist` no existe con ese nombre: las manos siguen sin agrandar.
- Pelo: sigue siendo conos, no mechones.

## Lo que ya está bien

- 6,59 cabezas: proporción de adolescente, correcta.
- Topología de la base respetada (anillos de ojo y boca intactos).
- Casquete de pelo ajustado con Shrinkwrap.
- Ojo como geometría plana con piezas separadas.
