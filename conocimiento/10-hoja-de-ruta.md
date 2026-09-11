# 10 — Hoja de ruta: cómo hacer un personaje cartoon

El procedimiento, en orden. **El orden no es negociable**: casi todos los
fracasos de este proyecto han sido saltarse un paso, no ejecutarlo mal.

---

## Fase 0 — Decidir antes de tocar geometría

0. **Pila de render** (ficha 15). En ÁNIMA está fijada: **NPR puro**. Es una
   decisión estructural; no se cambia a mitad.
1. **Matriz de formas** (fichas 07 y 15): forma primaria, secundaria y **una
   silueta prohibida**. Esa tercera es la que evita la deriva.
2. **Edad → cabezas de alto** (ficha 04): 4-5 niño, **6-6,5 adolescente**,
   7-8 adulto. Este número condiciona todo lo demás.
3. **Silueta en papel**: qué mancha quiero. Sin esto no se empieza.

## Fase 1 — Primarias: bloqueo

4. Partir de una **base con topología resuelta** (anillos en ojos y boca), no
   generar geometría. Ficha 03.
5. Fijar el **fenotipo** y hornearlo. Si la base usa shape keys, **hornear antes
   de tocar vértices**: mientras existan, escribir en `co` no hace nada.
6. Ajustar a las **proporciones objetivo** medidas (ficha 09):
   cabezas de alto, línea de ojos, cráneo y **ancho/alto de cabeza**.
7. Tallar los **planos de la cabeza** (ficha 08): plano lateral del temporal al
   pómulo. Sin él, es una esfera con rasgos.
8. **PRUEBA DE LA SILUETA como PUERTA** (fichas 07 y 15): a 5 m, 15 m y 50 m,
   y en las cinco poses canónicas. Si no pasa, volver al paso 6.
   **No continuar** — saltarse esta puerta sale más caro después.

## Fase 2 — Secundarias: rasgos

9. **Ojos**: geometría plana, piezas separadas, iris tocando el párpado
   superior, pestaña gruesa hacia el rabillo y **delante de todo**. Ficha 02.
10. Nariz y boca, **pequeñas**, al final.
11. **Relajar** las zonas deformadas por campos o quedan pliegues.
12. Silueta otra vez.

## Fase 3 — Pelo

13. **Silueta del pelo primero**, como masa. Ficha 05.
14. Casquete ajustado con **Shrinkwrap**, nunca raycast.
15. Mechones en **tres capas**: mayores (silueta), medianos (los que se ven),
    menores **solo para puentear huecos**. Demasiados solapados = borrón gris.
16. Silueta otra vez, ahora con pelo. Es la prueba que más veces falla.

## Fase 4 — Ropa

17. **Extraer la ropa del cuerpo** (duplicar caras, separar, empujar, Solidify).
    No modelarla aparte. Ficha 12.
18. Silueta otra vez, vestido. La ropa cambia la silueta más que la cara.

## Fase 5 — Sombreado

19. **`View Transform = Standard`.** Con AgX el estilo sale lavado. Ficha 11.
20. **Cel shader**: `Diffuse BSDF → Shader to RGB → Color Ramp (Constant)`.
    La sombra **desplaza el tono**, no solo oscurece.
21. **Normales esferizadas en la cara** (Data Transfer desde esfera), o la nariz
    y las cuencas tiran sombras que delatan el 3D — el *blob face*.
22. **Contorno** por casco invertido: Solidify negativo + Flip + material negro
    con Backface Culling.
23. **Un solo Sun.** Varias luces ensucian el corte entre bandas.

## Fase 6 — Producción

24. Rig con shape keys y estándar VRM de expresiones, huesos secundarios, LODs.
    Ficha 13.

---

## Comprobaciones automáticas

| Herramienta | Qué hace | Cuándo |
|---|---|---|
| `herramientas/medir_personaje.py` | proporciones contra el dataset | pasos 6 y 12 |
| `herramientas/prueba_silueta.py` | renderiza la mancha en negro | pasos 8, 12, 16 |

## Errores ya cometidos, para no repetirlos

- Detalle antes que silueta. **Los detalles no arreglan formas malas.**
- Medir con métricas que dependen de la pose.
- Suponer una medida en vez de medirla (la línea de ojos "al 47 %" era 55 %).
- Leer referencias de la malla **después** de podar los grupos que las contienen:
  devuelve `None` en silencio y la corrección no se aplica.
- Ajustar por raycast desde el centro de la cabeza: **no es convexa**.
- Exponente fraccionario sobre base negativa → número complejo → Blender casca.
