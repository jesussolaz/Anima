# 13 — Rig y expresiones

## Shape keys, no huesos, para la cara

En personajes de este estilo la cara se anima con **shape keys** (blendshapes),
no con huesos: labios, comisuras, mejillas, aletas de la nariz y cejas se
construyen **solo con shape keys**. Los huesos quedan para mandíbula y ojos.

El rig se monta así: shape keys + **huesos de control** conectados por
**drivers**, de modo que mover un hueso dispara una o varias claves a la vez.
Un rig típico ronda las **24 claves faciales**.

## Juego estándar de expresiones (VRM)

Conviene ceñirse al estándar VRM: es lo que esperan los motores y las
herramientas, y evita inventarse una nomenclatura propia.

**Emociones:** `Angry`, `Blink`, `Fun`, `Joy`, `Sorrow`, `Surprised`
**Visemas (labial):** `A`, `E`, `I`, `O`, `U`
**Extra:** la expresión anime de ojos `> <`

Más `Blink_L` y `Blink_R` por separado, que hacen falta para guiños.

## Huesos secundarios

Para lo que se mueve por inercia y no por músculo:

- pañuelo del cuello
- faldón del jubón
- mechones largos del pelo
- correas y accesorios colgantes

Cadenas cortas de 2-3 huesos bastan; se animan por física o por retardo.

## Orden

El rig va **al final**, después de que la malla esté cerrada. Rehacer topología
con pesos ya pintados es tirar trabajo.

## Fuentes

- [Advanced Facial Rigging — Blender Studio](https://studio.blender.org/training/facial-rigging/)
- [Proposal: Facial Rigging with shape keys — Blender Studio](https://studio.blender.org/blog/proposal-facial-rigging-with-shape-keys/)
- [Example Expressions from Blendshapes — Extra Ordinary](https://extra-ordinary.tv/2021/01/15/example-expressions-from-blendshapes-with-vroid-studio-hana_tool-and-unity/)
