# Plantilla ARPG — gameplay NATIVO C++

El gameplay (PlayerController, ThirdPersonCamera, EnemyAI) ya **no es Python**.
Son componentes C++ nativos del motor (doctrina C++):
`source/gameengine/Flipendo/FL_ArpgComponents.cpp` + `FL_ArpgCore.hpp`.

Se atan a un objeto poniéndole una propiedad de juego **`fl_component`**
(string) con el nombre del componente. El motor los instancia y tickea solo
(FL_ComponentManager). Un nombre que el motor no conoce se dice por consola al
arrancar: `Flipendo: el objeto 'X' pide el componente 'Y' y no existe`.

## Componentes registrados

| `fl_component` | Fichero | Qué hace | Propiedades que lee |
|---|---|---|---|
| `PlayerController` | `FL_ArpgComponents.cpp` | WASD relativo a cámara (7 m/s), SHIFT izq. corre (×1,7), ESPACIO salta, J / click izq. combo de 3 golpes (`FL_ArpgCore.hpp`). Publica `combo` y `hp`. Si tiene un hijo con `fl_rig`, anima: Idle/Andar/Correr en bucle, Ataque1-3/Salto/Golpe de un tiro, a la velocidad que cuadra con el `HitSpec`. | en el hijo `fl_rig`: `fl_anim_idle`, `fl_anim_walk`, `fl_anim_run`, `fl_anim_attack1..3`, `fl_anim_jump`, `fl_anim_hit` = `"Accion:inicio:fin"` |
| `ThirdPersonCamera` | `FL_ArpgComponents.cpp` | Se hace cámara activa y sigue al objeto llamado **`Player`**. El ratón orbita (yaw libre, pitch -10°..60°), suavizado, sin invertir; con `FL_UI_EXIT` (el Player conducido por `jugar`) no toca el puntero. | `fl_cam_dist` (7), `fl_cam_altura` (2,6), `fl_cam_sens` (0,0025 rad/px) |
| `EnemyAI` | `FL_ArpgComponents.cpp` | Persigue al `Player` (4 m/s) si lo ve a menos de 18 m, golpea a 2,2 m cada 1,4 s (8 de daño), muere a los 40 hp. Se pone él solo `arpg_enemy`. | — |
| `Flotar` | `FL_AnimaComponents.cpp` | Sube y baja en Z alrededor de donde estaba; la fase sale de la posición (dos objetos no van a la vez). Giro lento opcional. | `fl_flotar_amp` (0,25 m), `fl_flotar_periodo` (3 s), `fl_flotar_giro` (0 °/s) |
| `Girar` | `FL_AnimaComponents.cpp` | Rota sobre un eje local a velocidad constante. | `fl_girar_eje` (`X`/`Y`/`Z`, defecto `Y`), `fl_girar_grados_s` (12) |
| `CctvMonitor` | `FL_RenderToTexture.cpp` | Render a textura (una cámara pintada en una malla). | ver el fichero |
| `TemplateHello`, `TemplateKeyInput`, `TemplateTimer`, `TemplateProperty`, `TemplateFollow` | `FL_TemplateComponents.cpp` | Plantillas mínimas para escribir un componente propio (sustituyen a las plantillas Python del editor). | `speed`, `interval`, `amplitude`, `frequency`, `distance` |

## Jerarquía del personaje (convención de ÁNIMA)

```
Player          EMPTY, física CHARACTER, fl_component = "PlayerController". Nombre EXACTO.
 └─ Alonso_Rig  ARMATURE, fl_rig = "1", fl_anim_* (ver arriba). NO_COLLISION.
     └─ Alonso  MESH con modificador Armature. NO_COLLISION.
GameCamera      CAMERA, fl_component = "ThirdPersonCamera", cámara de la escena.
```

Detalle, cifras de verificación y trampas medidas (el EMPTY sin bounding box, los
hijos que deben ser NO_COLLISION, el visor 3D que tiene que estar en vista de
cámara para que el Player pinte desde `GameCamera`): `politicas/ARPG-ANIMACION.md`
en el repositorio del motor.

## Verificación sin manos

```
FL_ARPG_AUTOPLAY="w:70-150;shift:100-150;j:170;j:200;j:230" \
  ~/Flipendo/dev/noche/jugar escena.blend captura.png 210 volcado.txt
```

`tecla:frame` es un toque; `tecla:desde-hasta`, mantenida (teclas `w a s d shift j
space`; el frame es el tic lógico). El volcado (`FL_GAME_DUMP` v2) lleva
`accion=<nombre>@<frame>` por objeto que anima y `combo=… hp=…` en el Player.

> `ArpgNative.blend` tiene el visor 3D guardado en perspectiva libre, no en vista de
> cámara: el Player pinta desde la vista del visor, no desde `GameCamera`. Al
> regenerarlo hay que poner `region_3d.view_perspective = 'CAMERA'` en los `VIEW_3D`.
