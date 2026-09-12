# Referencias para estudio

Modelos de terceros que se **miden y estudian**, no se copian ni entran en el
juego. Sirven para extraer números reales de personajes cartoon bien hechos.

| Carpeta | Origen | Licencia |
|---|---|---|
| `quaternius-cc0/` | [Universal Base Characters](https://quaternius.itch.io/universal-base-characters) de Quaternius | **CC0 1.0** |
| `vroid-cc0/` | [Modelos de VRoid Studio liberados por VRoid Project](https://opengameart.org/content/vroid-studio-cc0-models) (`HairSample_Male.vrm`, `Base_Male.vrm`; VRM 0.x = glTF 2.0) | **CC0 1.0** |
| `opengameart-cc0/` | [Side parting hairstyle for male model](https://opengameart.org/content/side-parting-hairstyle-for-male-model) de Micket, 201 triángulos | **CC0 1.0** |
| `quaternius-cc0/animaciones/` | [Universal Animation Library 1](https://quaternius.itch.io/universal-animation-library) y [2](https://quaternius.itch.io/universal-animation-library-2) de Quaternius: `UAL1_Standard.glb`, `UAL2_Standard.glb` (86 clips a 30 fps, esqueleto UE de 65 huesos en T). **Sí entran en el juego**: son la fuente de las acciones de Alonso (`anima/anima_retarget.py`) | **CC0 1.0** |

Los `.vrm` no los abre el importador glTF de Blender 4.5 (KeyError en un nodo sin malla): se leen a mano como GLB (cabecera + chunk JSON + chunk BIN) y se reconstruyen con `from_pydata`; la línea de ojos sale de los huesos `J_Adj_L/R_FaceEye`.

Las medidas extraídas están en [`conocimiento/09-dataset-referencias.md`](../conocimiento/09-dataset-referencias.md).

Aquí solo se guarda una muestra mínima para poder repetir las mediciones. Los
packs completos se descargan de origen; no se redistribuyen desde este repo.
