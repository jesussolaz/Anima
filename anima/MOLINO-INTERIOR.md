# ÁNIMA — Interior del Molino: la casa del panadero

La planta baja del molino, habitada. Mismo listón de calidad que el exterior:
si el tejado de fuera va teja a teja, el horno de dentro va ladrillo a ladrillo.

- `MolinoInterior.blend` — la sala. **Sin Python**: cero text blocks, cero logic
  bricks, cero controladores. Doctrina C++ intacta.
- `gen_molino_interior.py` — generador (editor, determinista, semilla 1605).
  `Flipendo --background --factory-startup --python gen_molino_interior.py`
- `anima_kit.py` — kit de geometría **compartido** con el exterior.

**25.779 caras.** Arranca en el player sin errores.

## Por qué hay un kit compartido

El perfil de la torre, el grosor del muro y la posición de la puerta y las
ventanas viven en `anima_kit.py`, no en cada generador. Interior y exterior
**tienen** que encajar, y además ya se coló una vez un bug de centrado en `cbox`:
con dos copias del helper, el bug se arregla en una y sobrevive en la otra.

## La sala

Redonda, 6 m de diámetro, 2,6 m hasta las vigas. El muro se levanta como una
revolución parcial con hueco para la puerta y para la ventana baja, así que las
mochetas de los huecos son geometría real, no un recorte pintado.

| Pieza | Cómo está hecha |
|---|---|
| **Horno de bóveda** | **213 ladrillos** colocados uno a uno por hiladas sobre la media esfera, saltándose los que caen en la boca. Poyo de mampostería en 3 hiladas, boca con jambas y **11 dovelas** de arco de medio punto, cámara ennegrecida, 34 brasas encendidas, ceniza, humero y puerta de hierro apoyada |
| Solería | Losas irregulares en 6 anillos concéntricos, más gastadas hacia la puerta |
| Techo | Viga maestra sobre pie derecho con zapata y basa de piedra, 9 viguetas, tarima de tablas una a una y **trampilla abierta** al piso de arriba |
| Escalera | 12 peldaños empotrados en el muro sobre canes, subiendo hacia la trampilla, con soga de mano sobre argollas de hierro |
| Obrador | Artesa de amasar con masa reposando y paño, mesa con hogazas, cuenco de barro, rodillo y cuchilla, banqueta, dos palas de horno apoyadas |
| Despensa | 5 sacos de harina (uno tumbado y abierto, con la harina derramada), 2 tinajas, 2 cestas de mimbre con pan, estante de dos baldas con 10 hogazas |
| Colgados | 2 ristras de ajos, un manojo de hierbas y un farol encendido |

Las hogazas llevan la cruz marcada antes de entrar al horno.

## Desgaste

Como fuera, va **pintado en el atributo `Col`** por vértice, no en texturas.
Aquí hay dos suciedades distintas y opuestas: **hollín**, que sube desde el
horno y tizna la pared y el techo en un radio de 3,4 m, y **harina**, que se
posa en el suelo y en las superficies altas. Más el zócalo sucio de roce y las
aguas verticales de la cal.

## Luz

Sol de atardecer entrando por la puerta (misma dirección que en el exterior),
dos focos de fuego en el horno, el farol, y un rebote cálido. El haz de la
puerta lo dibuja una **niebla volumétrica** de harina en suspensión — las motas
sueltas son solo el remate, deliberadamente pocas y pequeñas.

## Objetos y gameplay

`Sala`, `Horno`, `Carpinteria`, `Obrador` (estáticos, colisión de malla);
`Colgados`, `Polvo`, `PolvoAire` (sin colisión).
Cámaras: `CamSala`, `CamHorno`, `CamMesa`, `CamTecho`, `CamEscalera`.

## Provisional — no es canon (biblia §34)

1. Que el molino sea la casa del panadero es **decisión de escenario**, no de
   guion: no hay nada aquí que fije quién es el panadero ni qué papel tiene.
2. No hay puerta modelada en el hueco: entra la luz directamente. Cuando se
   decida si la puerta se abre en juego, se modela.
3. El piso de arriba (la molienda: piedras, tolva, palahierro) **no existe
   todavía**. La trampilla ya está abierta y esperándolo.
4. Sin personaje ni maniquí: la escala está medida para un jugador de ~1,8 m.
5. Sin texturas de imagen: color por vértice + ruido procedural.
