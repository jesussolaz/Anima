# ÁNIMA — Terreno 1: La Mancha

Primer mapa del proyecto ÁNIMA. Generado con Flipendo (modo `--background`).

- `T1_LaMancha.blend` — el mapa. **Sin Python**: cero text blocks, cero logic
  bricks, cero controladores. El gameplay se ata solo con la propiedad de juego
  `fl_component` (componentes nativos C++ del motor).
- `gen_t1_lamancha.py` — generador. Es herramienta de EDITOR (bpy), no entra en
  el juego. Regenerar: `Flipendo --background --factory-startup --python gen_t1_lamancha.py`
  (determinista, semilla 1605).

## Contenido del mapa

| Zona | Qué hay |
|---|---|
| Pueblo (oeste) | 6 casas (zócalo de piedra, vigas, contraventanas, ventanas encendidas, chimeneas) + venta en L con tapia y cartel, plaza empedrada con pozo de sillares y torno, faroles encendidos, era, almiares, carro, cajas y barriles |
| Camino | Tierra batida plaza→colina con piedras de borde, vallas de madera y poste indicador |
| Arroyo seco | Cruza el camino; puente de madera con tablas y barandillas, piedras en el lecho |
| Colina (noreste) | Molino principal detallado (base de piedra, dintel, ventanas, aspas de celosía con travesaños y lona) + 2 molinos lejanos en la cresta |
| Llanura | 300×300 m con franjas de cultivo (trigo/rastrojo/arada con surcos), viñedos, olivos retorcidos, cipreses, penachos de hierba, amapolas, roquedos, lomas al horizonte |
| Cielo | Atardecer por gradiente + disco solar incandescente + nubes estilizadas retroiluminadas + sol cálido y relleno frío |
| Ánima | 7 nubes de motas doradas emisivas (plaza, pozo, camino, molino, era, puente, venta) |

## Gameplay (datos puros)

- `Player` — maniquí provisional, físicas CHARACTER (cápsula), `fl_component=PlayerController`.
- `GameCamera` — `fl_component=ThirdPersonCamera`, cámara de escena.
- `Pesadilla00..02` — placeholders sobre el camino, `fl_component=EnemyAI`.
- `Terreno` — STATIC con colisión TRIANGLE_MESH. `CamVista` es solo para renders.

## Provisional — NO es canon (biblia §34)

1. **Pesadillas**: el diseño de los enemigos recurrentes está SIN decidir. Aquí
   son bultos oscuros mate, deliberadamente abstractos y sustituibles.
2. **Aspas del molino**: estáticas. La rotación vendrá como componente C++
   (doctrina C++; no se usaron logic bricks). El objeto `Molino_Aspas` ya está
   separado y centrado en su eje para rotarlo directamente.
3. **Maniquí del jugador**: placeholder hasta tener el modelo de Alonso.
4. **El molino es solo un molino**: el momento molino/gigante es narrativa
   futura; nada aquí lo canoniza.
5. **Límites del mapa**: sin muros; las lomas del borde disuaden pero no
   bloquean. Pendiente de decidir cómo se delimita.
6. Distribución del pueblo, trazado del camino y paleta: parámetros del
   generador, fáciles de sustituir.
