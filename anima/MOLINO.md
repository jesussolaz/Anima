# ÁNIMA — El Molino de La Mancha (pieza héroe)

Primer asset construido con modelado real, no con primitivas. Sirve de listón de
calidad para todo lo que venga después.

- `Molino.blend` — la pieza y su cerro. **Sin Python**: cero text blocks, cero
  logic bricks, cero controladores. Doctrina C++ intacta.
- `gen_molino.py` — generador (herramienta de editor, determinista, semilla 1605).
  `Flipendo --background --factory-startup --python gen_molino.py`

**67.989 caras.** Se genera en ~6 s y arranca en el player sin errores.

## Qué lo separa de un cilindro con un cono encima

| Pieza | Cómo está hecha |
|---|---|
| Tejado | **661 tejas curvas colocadas una a una** en 19 hiladas, con solape del 45 %, alternancia de hilada, y desvío propio de ángulo y sombra en cada teja |
| Fuste | Perfil torneado con entasis (se estrecha al subir), desplazado con ruido 3D en dos frecuencias: el encalado a mano no es un cilindro |
| Zócalo | 120 sillares individuales en 3 hiladas, cada uno con tamaño, giro y deformación propios |
| Puerta | Jambas de sillería alternando soga y tizón, dintel, umbral gastado, 6 tablas con resalte distinto, 3 herrajes con 21 clavos, aldaba torneada |
| Ventanas | Alféizar volado, jambas, dintel, contraventana de tablas con travesaño y pernios; unas abiertas y otras cerradas |
| Aspas | Verga en punta + 11 travesaños decrecientes + largueros que cosen las puntas + lona con panza y arrugas + cabos. ×4 |
| Bocín | Tambor torneado, 2 zunchos de hierro, 16 pernos, eje que entra en la cubierta |
| Alero | Tabla de borde, 20 canes que asoman y 44 dentículos bajo la cornisa |
| Muro | 11 desconchones donde la cal se cayó y asoma la mampostería, 15 mechinales del andamio en hélice áurea, 3 llaves de tirante de hierro |
| Cerro | 340 piedras sueltas, 900 matas de hierba (5-8 briznas cada una, vencidas y de distinto tono), rodada de paso pelada |

Todas las aristas van achaflanadas: es lo que hace que una superficie atrape la
luz en vez de leerse como plástico.

## Desgaste

No hay texturas: el desgaste va **pintado en el atributo de color `Col`** por
vértice y cada material lo multiplica. Incluye humedad y barro en el arranque del
muro, regueros verticales bajo cada alféizar y bajo el dintel de la puerta,
moteado en dos escalas y aguas verticales de la cal.

## Objetos y gameplay

`Molino` y `Molino_Cubierta` (estáticos, colisión de malla), `Molino_Aspas`
(objeto aparte, pivote en el bocín y eje inclinado 10°: **listo para el
componente C++ rotador**), `Cerro`, `Piedras`, `Hierba`, `AnimaMotas`, `Cordal`.

Cámaras: `CamHeroe`, `CamPostal`, `CamPuerta`, `CamAspas`, `CamTejas`.

## Provisional — no es canon (biblia §34)

1. El molino es **solo un molino**. El momento molino/gigante es narrativa futura;
   aquí no se canoniza nada.
2. La rotación de las aspas todavía no existe: falta el componente C++.
3. Iluminación de atardecer y `AgX` con contraste medio-alto para el render; el
   motor de juego puede necesitar otro ajuste de vista.
4. Sin texturas de imagen: todo es color por vértice + ruido procedural. Si más
   adelante se pintan texturas, el desgaste ya está resuelto en `Col`.
