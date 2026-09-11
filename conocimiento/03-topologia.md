# 03 — Topología

Por qué importa: la topología es lo que permite que una cara **se deforme**.
Sin anillos alrededor de ojos y boca no hay parpadeo ni sonrisa creíbles, por
mucho que la forma en reposo esté bien.

## Reglas

- **Cuadriláteros.** Evitar triángulos y n-gons: dan artefactos de sombreado y
  se deforman mal.
- **Anillos concéntricos alrededor del ojo**: 3-4 para animación; 2 como mínimo
  en modelos de bajo coste.
- **Anillos concéntricos alrededor de la boca**, extendiéndose hacia nariz y
  mejillas.
- **Polos** (vértices con más de 4 aristas) colocados a propósito, no por
  accidente. Las **comisuras de la boca son polos** naturales, donde convergen
  los flujos.
- El flujo de aristas **sigue la musculatura**: es lo que hace que la deformación
  parezca carne y no plástico.

## Consecuencia práctica para ÁNIMA

La malla base de MPFB2 (MakeHuman) **ya tiene esta topología resuelta**: anillos
alrededor de ojos y boca, cuadriláteros, polos en su sitio. Eso es exactamente lo
que no se consigue generando geometría por código.

Por tanto la regla del proyecto es: **deformar, no generar**. El trabajo es mover
vértices respetando los anillos que ya existen.

Y de ahí una segunda regla: **después de deformar por campos, relajar**. Un
desplazamiento con caída abrupta deja un pliegue (a un vértice se le mueve mucho
y a su vecino nada). Un pase de suavizado sobre la zona tocada, dejando fijos los
bordes, lo resuelve.

## Fuentes

- [Good Face Topology: Essential Loops — vsquad.art](https://vsquad.art/blog/modeling-guide-to-achieving-good-face-topology)
- [Topology for Low Poly Game Characters — Thundercloud Studio](https://thundercloud-studio.com/article/topology-for-low-poly-game-characters/)
- [Topology for Animated Characters — The Gnomon Workshop](https://www.thegnomonworkshop.com/workshops/topology-for-animated-characters)
