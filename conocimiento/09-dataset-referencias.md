# 09 — Dataset: medidas de personajes de referencia

Leer guías da reglas cualitativas ("los ojos más bajos"). **Medir personajes
cartoon bien hechos da números.** Esta ficha es el dataset, y crece cada vez que
se mide una referencia nueva.

Herramienta: `anima/herramientas/medir_personaje.py`

```
Flipendo --background <fichero.blend> --python medir_personaje.py -- <Objeto>
```

## Medidas

Referencias: bases humanas de **Blender Studio**, CC0, del mismo autor — así que
la diferencia entre las dos columnas es *exactamente* el efecto de estilizar,
sin ruido de autor.

| Métrica | Realista (CC0) | **Estilizado (CC0)** | Alonso |
|---|---|---|---|
| Cabezas de alto | 7,93 | **6,12** | 6,59 |
| Línea de ojos (% alto cabeza) | 47,9 % | **44,9 %** | 44,7 % |
| Cráneo (% alto cabeza) | 52,1 % | **55,1 %** | 55,3 % |
| **Ancho/alto de cabeza** | 0,853 | **0,932** | 0,932 |

### Qué enseña el dataset

1. **Estilizar es bajar de ~8 a ~6 cabezas.** Es el cambio de mayor peso.
2. **La línea de ojos baja unos 3 puntos** y el cráneo crece otros tantos.
3. **La cabeza estilizada es mucho MÁS ANCHA**: 0,93 frente a 0,85 de ancho
   partido por alto. Alonso llevaba tiempo con una cabeza de anchura realista
   (0,858) y era una de las razones de que no leyera cartoon. Es un dato que
   **ninguna guía de las consultadas mencionaba** — salió solo al medir.

## Trampa de medición: no comparar poses

El primer intento midió "ancho de hombros" como la anchura máxima del tronco.
**En pose A eso mide los BRAZOS, no los hombros**, y el resultado depende del
ángulo de la pose, no del diseño. Dio 2,72 cabezas para la referencia y 3,66
para Alonso, y llevó a estrechar hombros sin motivo.

Regla: **usar solo métricas independientes de la pose** — proporciones de
cabeza, cara y altura. Para comparar torsos habría que normalizar la pose antes.

## Cómo medir el mentón

Es más difícil de lo que parece; cuatro métodos dieron cuatro resultados. El
único estable: **el mínimo de ANCHURA de cara por debajo de los ojos**. Bajando
desde los ojos la cara se estrecha hasta el mentón, y a partir de ahí el cuello
vuelve a ensanchar.

No funcionan: umbral de altura (coge el cuello), saltos del perfil frontal
(dependen de dónde arranque el escaneo), ni el grupo anatómico `joint-jaw`
(está 2 cm por encima del mentón real).

## Pendiente de medir

Manos y pies respecto al alto de cabeza, largo de pierna, y un torso normalizado
de pose. Y más referencias: el dataset con dos entradas es un punto de partida,
no una ley.
