# ÁNIMA — Sueños más allá de los mundos

Action-RPG de aventura y fantasía para PC. Un chico de La Mancha cruza mundos
hechos de literatura, mitología y folclore para encontrar a Dulcinea.

Se hace con **[Flipendo](https://github.com/jesussolaz/Flipendo)**, un fork propio
de UPBGE/Blender mantenido para el equipo. Este repositorio es **el juego**:
escenarios, personajes y las herramientas que los generan.

## La cosmología, en tres palabras

**Ánima** es el potencial de cualquier cosa para llegar a ser más de lo que es.
Una piedra puede seguir siendo una piedra un millón de años, o acabar formando
parte de una pirámide. **Sueños** es lo que todavía no existe pero podría existir.
**Pesadillas** no son el Mal: son miedo, pérdida e incertidumbre — y de ahí
también nacen los sueños más brillantes.

> Alonso no sueña con gigantes. Los gigantes son reales.
> Alonso sueña con un mundo sin ellos.

## Estado

Vertical slice en construcción. Nada de esto es definitivo.
La evolución de cada pieza, con imágenes, está en la **[bitácora](bitacora/)**.

![El molino al atardecer](bitacora/img/molino-heroe.jpg)

| Pieza | Estado |
|---|---|
| Terreno 1 — La Mancha | mapa jugable: pueblo, camino, arroyo, molinos |
| El Molino | pieza héroe: 661 tejas colocadas una a una, aspas de celosía |
| Interior del Molino | la casa del panadero: horno de bóveda de 213 ladrillos |
| Alonso Quijano | **en curso** — [base procedural descartada](bitacora/04-alonso.md) |

## Cómo está construido

Los `.blend` **no contienen Python**: ni text blocks, ni logic bricks, ni
controladores. El gameplay se ata con una propiedad de juego `fl_component`
que el motor resuelve a componentes nativos en C++. Es la doctrina del proyecto.

Los `gen_*.py` son **herramientas de editor**, no van en el juego. Son
deterministas: mismo script, mismo `.blend`. Para regenerar cualquier escena:

```
Flipendo --background --factory-startup --python gen_molino.py
```

`anima_kit.py` es el kit de geometría compartido (chaflanes, torneados,
barridos, desgaste por color de vértice). Vive en un solo sitio a propósito:
tener dos copias de un helper es cómo un bug se arregla en una y sobrevive en
la otra.

## Sobre las referencias

Kingdom Hearts y *La brújula dorada* son referencia de **sensación y alcance**,
nunca de contenido. Los personajes salen de **dominio público** (Cervantes,
*Viaje al Oeste*, *Libro de buen amor*). En este repositorio no entra material
protegido de terceros, ni modelos extraídos de otros juegos.

## Licencia

Pendiente de decidir. El código de Flipendo es GPL por herencia de Blender; el
contenido de este repositorio todavía no tiene licencia asignada.
