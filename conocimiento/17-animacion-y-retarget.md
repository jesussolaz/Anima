# 17 — Animación del personaje: clips CC0 de Quaternius y retarget al rig de MPFB

Lo que hay que saber para que Alonso ande, corra y pegue con clips de terceros sin
que se le tuerzan los pies ni las palmas. Todo medido en Blender 4.5 (Flipendo) sobre
`referencias/quaternius-cc0/animaciones/UAL1_Standard.glb` y `UAL2_Standard.glb`.
Evidencia (tiras de frames, capturas del Player) en `dev/noche/informes/rig-animaciones/`;
herramienta: `anima/anima_retarget.py`.

## 1. La librería: qué hay y cuánto dura

Universal Animation Library 1 y 2 [Standard], Quaternius, **CC0 1.0**. Cada pack son
**43 clips a 30 fps** (muestreo LINEAR, tiempos en segundos en el glTF: 40 claves =
1,333 s) sobre el **mismo esqueleto de 65 huesos** con nombres de Unreal (`root`,
`pelvis`, `spine_01..03`, `neck_01`, `Head`, `clavicle/upperarm/lowerarm/hand_l|r`,
dedos `*_01..03` más un `*_04_leaf`, `thigh/calf/foot/ball_l|r` más `ball_leaf`). La
versión de pago (con .blend y 120+ clips) no hace falta. El fichero `_RM` lleva root
motion horneado; se usa el que NO lo lleva porque el `CharacterController` C++ mueve
al Player y el clip solo debe mover huesos.

Clips útiles para un action-RPG (frames = claves del glTF; el horneado empieza en 1):

| Uso | Clip | Pack | Frames | s | Notas medidas |
|---|---|---|---|---|---|
| Idle | `Idle_Loop` | 1 | 75 | 2,50 | bucle limpio: frame 76 = frame 1 (0,39° máx) |
| Idle en guardia | `Sword_Idle` | 1 | 50 | 1,67 | rodillas flexionadas, espada al frente |
| Andar | `Walk_Loop` | 1 | 40 | 1,33 | 20 frames por paso = 90 pasos/min (paseo) |
| Correr | `Jog_Fwd_Loop` | 1 | 28 | 0,93 | 129 pasos/min; **vuelo real 7 de 28 frames** |
| Esprintar | `Sprint_Loop` | 1 | 20 | 0,67 | 180 pasos/min |
| Salto | `Jump_Start` + `Jump_Loop` + `Jump_Land` | 1 | 40 / 75 / 38 | | agacharse f1-8 (pelvis baja a 0,49 m), luego piernas encogidas; sin subida (la pone la física) |
| Golpe recibido | `Hit_Chest`, `Hit_Head` | 1 | 10 / 13 | 0,33 / 0,43 | retroceso corto en el sitio |
| Derribo | `Hit_Knockback` | 2 | 25 | 0,83 | cae hasta pelvis z 0,04 m: es un derribo, no un golpe |
| Ataques espada | `Sword_Regular_A/B/C` | 2 | 13 / 16 / 60 | 0,43 / 0,53 / 2,00 | tajo ascendente / barrido en estocada / giro |
| Combo encadenado | `Sword_Regular_Combo` | 2 | 90 | 3,00 | A+B+C con transiciones; **es el que usamos** |
| Recuperaciones | `Sword_Regular_A_Rec`, `_B_Rec` | 2 | 29 / 31 | | vuelven a `Sword_Idle` |
| Bloqueo, esquiva | `Sword_Block`, `Roll` | 2 / 1 | 37 / 44 | | |
| Muerte | `Death01` | 1 | 72 | 2,40 | |

También hay: `Crouch_*`, `Swim_*`, `Sitting_*`, `Push_Loop`, `Pistol_*`, `Spell_*`,
`Punch_Jab/Cross`, `Dance_Loop`, `Interact`, `Farm_*`, `Climb`, `Slide_*`, `Zombie_*`.
Inventario completo: `informes/rig-animaciones/inventario_ual1_24fps.txt` (¡ese está a
24 fps: 32 frames en vez de 40!) y `inventario_ual2_30fps.txt`.

**Trampa 1.** El importador glTF muestrea los tiempos al fps de la escena. Con la escena
a 24 fps `Walk_Loop` sale con 32 frames; hay que poner `scene.render.fps = 30` ANTES de
importar. Convención de ÁNIMA: todo a 30 fps.

## 2. Los dos esqueletos no descansan igual

| | Quaternius (UAL) | MPFB2 `game_engine` en Alonso |
|---|---|---|
| Huesos | 65 (con hojas) | 53 |
| Pose de reposo | **T**: `upperarm_l` Y=(1,0,0), codo recto | **A**: `upperarm_l` Y=(0,67,0,−0,75) = 48° bajo la horizontal, codo doblado hacia delante (`lowerarm` Y=(0,51,−0,68,−0,52)), mano pronada |
| Altura | 1,68 m (Head 1,569 + 0,083) | 1,68 m |
| Cadera (`pelvis.head` z) | 0,917 | 0,855 (base MPFB: 0,874) |
| Muslo / pantorrilla / pie | 0,400 / 0,429 / 0,173 | 0,339 / 0,462 / 0,124 |
| Brazo / antebrazo / mano | 0,274 / 0,273 / 0,049 | 0,246 / 0,260 / 0,035 |
| Eje Y | a lo largo del hueso | a lo largo del hueso |
| Eje Z brazos y columna | hacia atrás (−Y mundo) | hacia atrás |
| Eje Z muslo | (0, 1, 0) hacia delante | (−0,44, 0,89, −0,12): **26° de giro** |
| Eje Z `ball` | (0, 0, 1) arriba | (0,09, −0,05, −0,99): **180° girado** |
| Dedos `index_01` | X=(0,1,0) Z=(0,0,−1) | X=(0,74,0,47,−0,48): otra convención |

Los nombres coinciden salvo `Head`→`head` y `root`→`Root`; las hojas `*_leaf_*` no
existen en MPFB y se ignoran.

## 3. Retarget: por qué «Copy Rotation en mundo» no basta y qué sí

Copiar la orientación de mundo de cada hueso (método **a**, lo que hace un constraint
Copy Rotation en espacio World) resuelve por sí solo la diferencia A/T: el hueso destino
va a donde apunta el fuente y el reposo deja de importar. Pero también copia el giro
sobre el eje del hueso, y ahí las convenciones difieren: el muslo queda **26° torcido**
hacia dentro, el `ball` da la vuelta (pie de lado en la tira de marcha, frame 8) y la
palma del T-pose sale medio vuelta con el pulgar arriba (`detalle_a.png`).

Método **b** (el bueno): con el fuente en reposo, Q = Rs⁻¹·Rt es la rotación entre el
reposo fuente y el destino en coordenadas locales del fuente. Se descompone en
swing·twist y se conserva **solo el twist sobre Y**: q_twist = normalizar(w, 0, y, 0).
En cada frame, la orientación mundo deseada del hueso destino es
`P_destino = P_fuente · twist`. El swing (la diferencia A/T) se descarta a propósito: ya
lo da la copia de orientación. Resultado medido:

- T-pose fuente → T-pose destino, palmas abajo, dedos abiertos (`detalle_b.png`).
- Marcha: punto más bajo de los pies entre **−1,4 y +1,4 cm** del suelo en los 40
  frames (`analisis_b.py`); rodillas hacia delante; brazos en contrafase.
- Carrera: 7 de 28 frames con los dos pies en el aire (máx 22,6 cm): fase de vuelo
  correcta, no un error.
- Idle: pies a −1,8 cm constante (la pelvis de `Idle_Loop` va 1 cm más baja que el
  reposo). Aceptable; si molesta, restar 0,018 a la Z de la pelvis en ese clip.

La pelvis es el único hueso con traslación: Δ = (pos_fuente − reposo_fuente) × (0,855 /
0,917). Sin ese factor los pies se hunden 6 cm en el suelo.

Se hornea por cuaterniones (`rotation_mode = 'QUATERNION'`, interpolación LINEAR) frame
a frame calculando `matrix_basis` por jerarquía sin pasar por constraints: 21 clips en
~40 s.

**Trampa 2.** Los bucles del glTF van de 0 a N con el frame N igual al 0. Horneados a
partir de 1 quedan 1..N+1 y para el motor se declara `Accion:1:N`; declarar N+1 mete un
frame duplicado (parón de 33 ms en cada vuelta).

**Trampa 3.** Alonso.blend no tiene los cubos `joint-*` (el paso estilo borró los
helpers) y `mpfb.add_standard_rig` divide por cero. Se ajusta el rig en `AlonsoBase.blend`
y se traslada remapeando cada cabeza/cola por sus 32 vértices más cercanos (los 13.380
vértices del cuerpo conservan índice; se han movido 2–8 cm). Pesos: los del json de
MPFB filtrados a índices < 13.380; 0 vértices sin hueso.

**Trampa 4.** `ob["fl_rig"] = "1"` es una propiedad ID y el motor NO la ve
(`BL_ConvertProperties.cpp` solo convierte `ob.game.properties`). Hay que crearla con
`bpy.ops.object.game_property_new(type='STRING')`.

## 4. Impacto, HitSpec y cortes del combo

`FL_ArpgCore.hpp` define golpe 1 = 0,10 + 0,12 + 0,30 s, golpe 2 = 0,08 + 0,12 + 0,30,
golpe 3 = 0,14 + 0,16 + 0,55 (startup + active + recovery). El C++ escala la velocidad
para que el clip dure el total, así que el **frame de impacto tiene que caer entre el
19 % y el 42 % del clip** (golpe 1), 16–40 % (golpe 2) y 16–35 % (golpe 3).

El impacto se localiza por el **pico de velocidad de `hand_r`** (m/s, a 30 fps):

| Clip | Pico | Frame del pico | Corte elegido | Impacto en el corte |
|---|---|---|---|---|
| `Sword_Regular_A` | 25,7 | 9 de 14 (64 %) | — | demasiado tarde sin cortar |
| `Sword_Regular_Combo` golpe 1 | 25,7 | 9 | **5..17** (13 fr) | 31 % → 0,16 s de 0,52 |
| `Sword_Regular_Combo` golpe 2 | 28,6 | 23 | **18..31** (14 fr) | 36 % → 0,18 s de 0,50 |
| `Sword_Regular_Combo` golpe 3 | 29,2 | 48 | **37..70** (34 fr) | 33 % → 0,28 s de 0,85 |

El combo (90 frames) se usa entero como una sola acción `AtaqueCombo` y cada golpe es
un tramo: así la transición entre golpes viene animada por Quaternius y no por el
blend del motor. Los frames 71–91 son la vuelta a la pose neutra (velocidades < 1 m/s).

Ritmo de un tajo en el clip A: anticipación 6 frames (2,2–3,2 m/s), golpe 3 frames
(12→26 m/s), asentamiento 5 frames; recuperación aparte, 29 frames.

## 5. La espada en la mano

Ejes del hueso `hand_r` de MPFB en reposo (mundo): X=(−0,13, −0,47, 0,87) = **dorso de
la mano**, Y=(−0,33, −0,81, −0,49) = hacia los dedos, Z=(0,94, −0,35, −0,05) = **lado
del pulgar** (`thumb_01_r` proyectado: Z 0,89, Y 0,46, X −0,01). Una espada agarrada
lleva la hoja por el pulgar, así que el objeto Espada (hoja hacia +Y propio, origen en
la empuñadura) se emparenta al hueso con `rotation_euler = (+90°, 0, 0)` y
`location = (−0,010, 0,025, 0)` en el espacio del hueso (que cuelga de la COLA): 2,5 cm
más allá de la cola hacia el centro de la palma y 1 cm hacia la palma (−X). Comprobado
con un cilindro (`espada_proxy2.png`): T-pose hoja hacia delante, `Sword_Idle` hoja
horizontal al frente, tajos coherentes. Con la hoja por X (primer intento) salía del
dorso de la mano.

## 6. Plan B: ciclo de marcha por fórmula (si un día no hay clip)

Cifras de referencia, a 30 fps:

- Un ciclo = 2 pasos. Paseo 90 pasos/min → 40 frames/ciclo (igual que `Walk_Loop`);
  marcha normal 110–120 pasos/min → 30–33 frames; carrera 170–180 pasos/min → 20 frames.
- Poses clave por paso (Williams): **contacto** (0 %), **bajo/recoil** (25 %, pelvis
  −2 a −3 cm), **paso** (50 %, pierna libre cruza), **alto** (75 %, pelvis +2 cm).
- Pelvis: rotación ±4° (transversal), oblicuidad ±5° (frontal), inclinación ±2°;
  desplazamiento vertical 4–5 cm pico a pico, lateral 4 cm (Perry & Burnfield).
- Rodilla: 15–20° al cargar, 60° máx en balanceo; cadera: +30° flexión / −10° extensión.
- Brazos en contrafase con la pierna del mismo lado: hombro +8° delante / −24° atrás
  (Perry), codo 20–45°.
- Tajo de espada: anticipación 4 frames, impacto 2, recuperación 8 (encargo); Quaternius
  usa 6 / 3 / 5+29.

## Fuentes

- Quaternius, [Universal Animation Library](https://quaternius.com/packs/universalanimationlibrary.html)
  y [UAL 2](https://quaternius.itch.io/universal-animation-library-2), CC0 1.0. Cifras
  medidas con `informes/rig-animaciones/inv_ual.py` y `analisis_b.py`.
- MPFB2 2.0.17, `data/rigs/standard/rig.game_engine.json` y `weights.game_engine.json`.
- Perry, J.; Burnfield, J. *Gait Analysis: Normal and Pathological Function* (pelvis,
  rodilla, hombro). Williams, R. *The Animator's Survival Kit* (poses del ciclo).
- Blender 4.5: `EditBone.align_roll`, `Object.parent_type = 'BONE'` (el hijo cuelga de la
  cola), `Quaternion` swing-twist; UPBGE `BL_ConvertProperties.cpp` (propiedades de juego).
