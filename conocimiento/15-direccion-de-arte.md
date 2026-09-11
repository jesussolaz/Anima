# 15 — Dirección de arte y control de producción

Cómo se dirige un reparto de personajes estilizados para que no se desmadre.
Material de producción real, no de tutorial.

## La decisión que se toma ANTES de todo: la pila de render

Se elige en preproducción y **es estructural**: cambiarla a mitad de proyecto
es rehacer.

| Pila | Qué es | Ejemplos |
|---|---|---|
| **NPR puro** | cel-shading, contornos, pictórico | Genshin, Honkai Star Rail |
| **PBR estilizado** | materiales PBR con dirección de arte apretada | Overwatch, Fortnite, Valorant |
| **Híbrido** | base PBR con post o materiales NPR encima | cada vez más común |

**ÁNIMA queda fijado en NPR puro.** Ya está implementado (ficha 11) y no se
cambia.

## Matriz de lenguaje de formas, antes del bloqueo

Para cada personaje, y **antes de tocar geometría**:

1. **Forma primaria** (esfera / cubo / cilindro / cono / pirámide).
2. **Forma secundaria** de acento.
3. **Una silueta prohibida**: la que rompería su identidad visual.

Ese tercer punto es el que nunca se escribe y el que evita la deriva.

## La silueta como PUERTA, no como consejo

Se prueba con el personaje **100 % negro sobre blanco**, y no es opinable:

- **A tres distancias**: 5 m (plano héroe), 15 m (distancia de juego),
  50-100 m (umbral de reconocimiento). Debe seguir identificándose a la máxima.
- **En cinco poses canónicas**: reposo, ataque, desplazamiento, reacción al
  golpe, victoria. La silueta tiene que aguantar en todas.

**Puerta de producción:** no se pasa de bloqueo a alta densidad sin superarla, y
no se pasa de alta densidad a retopología hasta que aguante en las cinco poses.
Saltársela obliga a rehacer más caro.

## Compresión de valor

- Comprimir el rango real a pasos deliberados: **tres valores** (sombra, medio,
  luz). Es exactamente lo que hace el Color Ramp del cel shader.
- **Prueba de tensión**: renderizar todo el reparto al **25 % de saturación**
  bajo tres luces (clave frontal, clave lateral, solo contraluz). Si las
  relaciones de valor se caen o los colores de bando dejan de distinguirse, la
  compresión no está bastante apretada.

## Anclaje al personaje héroe

Del personaje de referencia (en ÁNIMA, **Alonso**) se documenta:

- proporciones (cabeza/cuerpo, extremidad/torso, anchura de hombros)
- presupuesto de polígonos por nivel de silueta
- densidad de téxel objetivo
- pila de render
- **reglas de grosor de contorno**
- lista de características del shader

Y luego, **la comparativa héroe**: cada personaje del reparto se renderiza
**al lado del héroe, con la misma luz, en cada hito**. Detecta la deriva de
estilo mucho antes que revisar cada personaje por separado.

## Filosofía de diseño

De entrevistas con diseñadores de personaje de videojuego:

- Los diseños deben **encajar en el mundo y la atmósfera del juego**, no ser
  bonitos por su cuenta.
- **El género manda**: «en un RPG no hay límites reales de diseño, pero en un
  juego de acción hay que asegurarse de que **se vea bien en movimiento**».
- Se añaden deliberadamente **elementos que ondean** —telas, accesorios,
  colgantes— sabiendo que complican el modelado, porque dan vida en movimiento.
  (En ÁNIMA: el pañuelo de Alonso, el faldón, los mechones largos.)
- El **nombre** forma parte del diseño, no se pone al final.

## Aplicado a ÁNIMA

| Personaje | Forma primaria | Secundaria | Silueta prohibida |
|---|---|---|---|
| Alonso | círculo | triángulo (espada, faldón) | achaparrada o pesada |
| Wukong | triángulo | círculo (cabeza) | simétrica y quieta |
| Bajie | círculo grande | cuadrado (peso) | esbelta |
| Celestina | triángulo invertido | línea vertical | redonda y cercana |
| Pesadillas | triángulo | — | cualquier cosa redonda |

## Fuentes

- [Stylized 3D Characters Done Right — Nasty Rodent](https://nastyrodent.com/stylized-3d-characters-art-direction-principles/)
- [UE5 Character Pipeline: 7 Stages — Nasty Rodent](https://nastyrodent.com/3d-character-pipeline-unreal-engine-5/)
- [Entrevista Nomura × Shinkawa — shmuplations](https://shmuplations.com/nomurashinkawa/)
