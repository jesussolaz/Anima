# 16 — La espada: ropera castellana, Llave Espada y metal toon

Lo que hay que saber para diseñar un arma blanca de personaje en ÁNIMA. Sale de
medir piezas de museo, un render de la Kingdom Key y a Alonso, no de suponer.
Brief con las medidas finales de la espada de Alonso: `dev/noche/informes/anima-espada.md`.

## 1. La ropera real, en números (1570-1630, n = 111 piezas de museo)

Calculado sobre las tablas del anexo de Vauthier (Wallace, Met, Dresde, Viena,
Écouen, Jarville, subastas):

| Parámetro | Mediana | Rango | Nota |
|---|---|---|---|
| Hoja (cruz→punta, con recazo) | **108,0 cm** | 99,6-126,4 | 84 % entre 100 y 115 |
| Largo total | 123,2 cm | 115,6-142,9 | |
| **Empuñadura + pomo** (total − hoja) | **15,8 cm** | 13,0-22,3 | puño útil ≤ 10-11 cm |
| Ancho de hoja en el fuerte | **2,6 cm** | 1,5-3,3 | |
| Peso | **1,28 kg** | 0,79-1,86 | 82 % entre 1,0 y 1,5 |
| Punto de balance | ⅛-⅒ de la hoja desde la cruz | | Peláez: «a una media cuarta de la guarnición» (⅛ vara = 10,4 cm) |
| Grosor | recazo ~10 mm → punta ~2 mm | | el ahusado es 3× más fuerte en los 10 primeros cm del fuerte, luego lineal |

Piezas sueltas: Met 25058, española ca. 1620: total 144,1, hoja 126,5,
**guarnición 25,2 × 14,0 cm**, 1.616 g. Met 25641: 123,3 / 107,3 / 23,3 × 8,9 /
1.191 g.

**La medida legal**: pragmática de Felipe II (1558, repetida 1564 y 1590):
«ninguna persona… traya espadas, verdugos, ni estoques de más de **cinco cuartas
de vara** de cuchillo en largo». Vara de Burgos = 0,835905 m → **hoja ≤ 104,5 cm**.
Los maestros españoles (Narváez, Ettenhard) la ligan al cuerpo: la hoja llega
**del suelo al ombligo = ⅝ de la estatura**; los italianos (Capo Ferro) quieren
el total hasta la axila, ≈ ⅔ de la estatura de hoja.

## 2. Cronología que decide el tipo (Peláez Valle, Gladius XVI, 1983)

| Época | Hoja | Guarnición | Pomo |
|---|---|---|---|
| ~1450-1500 | ancha, de corte | cruz de arriaz; nace la 2.ª patilla (pas d'âne) en España | cilíndrico, grande |
| **1500-1530** | **ancha** («a principios del XVI las hojas de ropera son anchas») | patillas + **pitones** con bolita (invento español), **anillo superior** sobre el arriaz, **guardamano** que «se levanta hasta casi tocar el pomo» | lenticular, venera |
| 1530-1570 | se estrecha y alarga | anillo inferior, puentes, lazos acestados | periforme, esférico, prismático |
| 1570-1620 | larga y fina, >1,1 m | lazo simplificado y elegante | troncocónico estriado; **esférico achatado** |
| 1620-1700 | 85-95 cm, vuelve la ancha | **taza** (rompepuntas, guardapolvo) | esférico achatado |

Detalles de oficio: el puño es madera forrada con **hilo de hierro o cobre**
(«en los ejemplares de alta calidad de oro o plata y excepcionalmente de seda»),
a veces en torzales alternados; o madera exótica tallada en gajos. Las marcas van
**siempre en el recazo**; el nombre del espadero, en el canal del tercio fuerte;
la **T** (con variantes) es punzón de origen de Toledo, no del espadero; el
«perrillo» de Julián del Rey iba estampado y relleno de cobre; los pomos podían
llevar el **escudo del dueño** (G.29 de la Real Armería, el Gran Capitán). Precio
1680: hoja de Toledo 30 reales, de Alemania 18, de Génova 10.

**Cervantes** (I, cap. I): las armas de los bisabuelos estaban «tomadas de orín y
llenas de moho, luengos siglos había… olvidadas en un rincón». Tres generaciones
desde 1600 → forjada hacia 1510-1530: **hoja ancha, lazo temprano, pomo
lenticular**. La taza y el estoque largo son de otra generación.

## 3. Lo que enseña la Llave Espada: no es más larga, es más ANCHA

Medido sobre el render de la Kingdom Key de KHWiki (564×600 px, por color de
píxel; vástago plateado, guarda dorada) y con 3,5 ft = 106,7 cm y Sora = 160 cm:

| Relación | Ropera real | Kingdom Key | Factor |
|---|---|---|---|
| Largo / estatura | ⅝ H de hoja + 16 cm ≈ **0,72 H** | 106,7/160 = **0,667 H** | **1,0 o menos** |
| Ancho de hoja / largo | 2,6/123 = 0,021 | 30/552 px = 0,054 | **×2,6** |
| Ancho de guarda / largo | 25,2/144 = 0,175 | 173/552 = 0,313 | **×1,8** |
| Grupo empuñadura / largo | ≈ 0,13-0,16 | 0,286 | ×1,9 |
| Nº de masas legibles | 4 | 5 (vástago, dientes, guarda, puño, llavero) | ≤ 6 |

**La regla**: la exageración de un arma icónica va a **anchura, grosor y bloque
de guarda**, no a longitud. Una ropera real ya es más larga respecto al cuerpo
que la Llave. Y es cuestión de píxeles: con lente de 50 mm y 1280 px de ancho, a
7 m (distancia de la cámara del motor, `m_dist = 7`) un píxel son **3,9 mm**: una
hoja real de 26 mm son 6-7 px y **de canto 0-2 px**; un gavilán de 7 mm, < 2 px.
A 15 m (8,4 mm/px) la ropera real de canto no existe. Se exagera para que en la
captura de juego haya píxeles, y en escorzo, no solo de perfil.

## 4. Metal en NPR: cinco reglas

1. **Dos tonos, no degradado** (Motomura, GDC 2015: «In Cel-shading, the surface
   is either lit, or not, and no value in between»). La tercera banda de una hoja
   sale de la **geometría**: sección en rombo → una cara al sol, otra en sombra,
   partidas por la arista. Es la «línea de luz» de las hojas de anime.
2. **Banda especular dura**: `step(umbral, pow(N·H, tamaño))` (Godot Anime Metal:
   tamaño 8, umbral 0,5). En EEVEE: `Glossy → Shader to RGB → Ramp CONSTANT` y ADD,
   apagada en el lado en sombra. En superficie plana el lóbulo satura: umbral
   más alto que en el pelo (0,70 frente a 0,62).
3. **Filo claro como diseño, no como reflejo**: material aparte, sin rampa.
   Igual que la banda del pelo (ficha 11): elementos fijos, intencionales.
4. **Desgaste por color de vértice, no por textura** (Xrd: «vertex properties
   are linearly interpolated between vertices, which is completely resolution
   independent»; el kit del molino ya pinta el desgaste así). El canal también
   sirve para **sesgar el umbral** en zonas ocluidas (caras interiores de la
   guarda).
5. **Colores con referencia física pero desplazados**: F0 hierro (0,531, 0,512,
   0,496) y latón (0,910, 0,778, 0,423) (physicallybased.info); óxido = rust
   #B7410E = lineal (0,474, 0,053, 0,004). El acero de hoja se pone más frío y
   más oscuro que el F0 para que la banda blanca tenga sitio; la sombra desplaza
   al azul (ficha 11).

Genshin usa **matcap + especular** para el metal (Ayers); en EEVEE sin nodo
matcap el Glossy→ramp cumple el mismo papel con el `toon()` del repo.

## 5. Trampas encontradas
- El texto de Vauthier pierde todos los dígitos al extraerlo (fuente con
  ligaduras); las **tablas del anexo** sí salen, y las estadísticas de la
  sección 1 están recalculadas desde ellas, no copiadas del texto.
- Medir la Llave por píxel confunde el **llavero** con el vástago (misma plata):
  hay que cortar por el eje mayor en el arranque de la guarda (−213 px) y no
  contar la cadena (200 px).
- Los renders «life-size» de réplicas (85-91 cm) no son canon; el 3,5 ft de la
  wiki y los 160 cm de Nomura son lo único citable.

## Fuentes
- Peláez Valle, J. M., «La espada ropera española en los siglos XVI y XVII», *Gladius* XVI (1983) — https://gladius.revistas.csic.es/index.php/gladius/article/download/127/127/128
- Vauthier, G., *Study of various historical rapiers* — https://subcaelo.net/ensis/vauthier-rapier/Rapieres_articleVE.pdf
- Met Museum obj. 25058 y 25641 — https://www.metmuseum.org/art/collection/search/25058
- Wikipedia EN «Rapier» — https://en.wikipedia.org/wiki/Rapier ; ES «Espada ropera» — https://es.wikipedia.org/wiki/Espada_ropera ; «Vara» — https://es.wikipedia.org/wiki/Vara ; «Rust (color)» — https://en.wikipedia.org/wiki/Rust_(color)
- Pragmática de Felipe II, AEEA — http://www.esgrimaantigua.com/forum/viewtopic.php?t=5744
- Cervantes, *Don Quijote*, Gutenberg #2000 — https://www.gutenberg.org/cache/epub/2000/pg2000.txt
- KHWiki «Kingdom Key» — https://www.khwiki.com/Kingdom_Key ; KHInsider (Sora 160 cm) — https://x.com/khinsider/status/1082803323340709889
- Motomura, J., *GuiltyGear Xrd*, GDC 2015 — https://www.ggxrd.com/Motomura_Junya_GuiltyGearXrd.pdf
- Godot Shaders, «Anime Style Metal» — https://godotshaders.com/shader/anime-style-metal-metallic-toon/
- Ayers, B., *Recreating the Genshin Impact shader in Blender* — https://bjayers.com/blog/9oOD/blender-npr-recreating-the-genshin-impact-shader
- physicallybased.info ; Innovecs, *Weapon concept art for games* — https://www.innovecsgames.com/blog/weapon-concept-art/ ; Darkwood Armory (puños de alambre con nudos) — https://rapiers.darkwoodarmory.com/product/wire-wrap-handle-with-knots/
