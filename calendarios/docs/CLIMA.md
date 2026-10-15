# Clima unificado — por qué se construye así

`calendarios/clima/clima_unificado.py` une cuatro fuentes en una fila por día y escribe
`calendarios/clima_unificado.csv.gz` (comprimido desde el 2026-09-24; pandas lo lee igual). Este documento dice **por qué** está hecho así y con qué
evidencia. Cómo funciona está en el docstring del script.

Reescrito el 2026-09-23. La versión anterior producía resultados falsos por seis motivos
distintos, todos medidos.

---

## Las fuentes, y cuál es cuál

| Fuente | Qué es | Dónde | Cobertura |
|---|---|---|---|
| `clima_ideam.csv` | Estaciones IDEAM, empalmadas por cercanía | 3 estaciones, ver abajo | 1.776 días hasta el 2026-08-25; lo actualiza `clima_ideam.py` desde el 2026-10-15 |
| `raw_iem_skmz.csv` | METAR del aeropuerto La Nubia | En la ciudad, ~2.090 m | 2.432 días (temp. 83 %) |
| `raw_openmeteo.csv` | Reanálisis ERA5-Land (temp.) y ERA5 (lluvia) | Celda de 2.100 m | 2.431 días |
| `raw_nasapower.csv` | Reanálisis MERRA-2 / satélite | Celda de ~55 km | 2.431 días |

**La columna «IDEAM» no es una estación: son tres empalmadas.**

| Estación | Distancia | Periodo | Temp. media | Máx. contra La Nubia |
|---|---|---|---|---|
| Tesorito Finca | 7,7 km | 2020-01 → 2020-07 | 15,7 °C | r 0,58, −0,99 °C |
| **Planalto** | **12,8 km** | **2020-08 → 2023-09** | **21,0 °C** | **r 0,50, +7,39 °C** |
| Aeropuerto La Nubia | 5,0 km | 2022-03 → 2026-08 | 16,6 °C | **r 0,81, −0,29 °C** |

Planalto es de Cenicafé, en la zona de Chinchiná, unos 800 m más abajo. Los 4,5 °C de
diferencia en la media son exactamente lo que da la altitud (6,5 °C/km). **No es Manizales**
y se excluye.

La fila de La Nubia es la validación que fija la referencia: la estación IDEAM y el METAR
son **la misma pista con dos redes distintas**, y coinciden con r = 0,81 y 0,29 °C de sesgo.

---

## Los seis problemas de la versión anterior

| # | Problema | Efecto medido |
|---|---|---|
| 1 | Las cuatro rutas de entrada apuntaban a archivos inexistentes, y `cargar_csv` devolvía una tabla vacía con un aviso | **El archivo no se podía regenerar**, y si se intentaba, fallaba en silencio |
| 2 | La lluvia de Open-Meteo viene de ERA5 a ~28 km | **16.555 mm/año**, ciclo invertido, **r = −0,025** con la estación: ruido |
| 3 | Planalto empalmado como si fuera Manizales | Escalón falso de **+7,4 °C** en la máxima entre 2020-08 y 2023-09 |
| 4 | Open-Meteo votaba dos veces en temperatura (`_corr` y sin corregir) | Sesgo del consenso hacia una sola fuente |
| 5 | **Mediana de fuentes con sesgos distintos** | **Escalones falsos cada vez que una fuente falta** |
| 6 | Banderas con umbral fijo en una ciudad sin estaciones térmicas | `dia_frio` 0,0 %, `dia_calido` 1,4 %, `llovio` 98,8 %: constantes |

### El 5 es el que importa para este proyecto

El consenso era la mediana de las fuentes disponibles cada día. Con tres fuentes, la que
está fuera de escala queda fuera de la mediana. **Con dos, la mediana es el promedio**, y la
fuente rota entra a medias.

La estación IDEAM solo cubre el 72,6 % de los días. El resultado, medido **dentro del mismo
mes** para que la comparación sea justa:

| | Días sin pluviómetro − días con pluviómetro |
|---|---|
| **Antes** | **+20,05 mm/día** |
| **Después** | **−0,36 mm/día** |

Antes, cada vez que la estación dejaba de reportar aparecía una tormenta. **Este proyecto
busca exactamente eso** — el paso brusco de seco a lluvioso — así que la versión anterior
fabricaba el efecto que se quería medir.

---

## El método

1. **Una referencia por variable**, la que mejor mide esa variable en Manizales.
2. **Cada otra fuente se lleva a la escala de la referencia, mes calendario por mes**:
   sumando la diferencia media (temperatura, humedad, viento) o multiplicando por el
   cociente (lluvia). Es el escalado lineal, el método estándar para corregir reanálisis
   contra estación.
3. **Consenso = mediana de las fuentes ya corregidas.**

Con el paso 2, que falte una fuente ya no mueve el nivel: todas están en la misma escala.

### Las referencias, y por qué cada una

| Variable | Referencia | Por qué |
|---|---|---|
| Temp. máx. y mín. | METAR La Nubia (IDEAM La Nubia donde falte) | En la ciudad, a la altura correcta, 83 % de cobertura |
| **Temp. media** | **IDEAM La Nubia / Tesorito** | **Media real de 22 lecturas/día.** El (máx+mín)/2 del METAR sale **+1,09 °C** por encima: en montaña la curva diaria es asimétrica |
| **Lluvia** | **Pluviómetros IDEAM** | Ver abajo |
| Humedad | NASA POWER | La única con media diaria real y serie completa. (mín+máx)/2 del METAR la subestima: la noche pasa horas cerca del 100 % |
| Viento | METAR La Nubia | Medido en la ciudad |
| Radiación | ninguna (mediana simple) | No hay estación en tierra y las dos fuentes están siempre presentes: no hay escalón posible |

### La decisión de la lluvia, que no es obvia

Los dos pluviómetros válidos coinciden entre sí y NASA da casi el doble:

| | mm/año | Días con ≥ 1 mm |
|---|---|---|
| La Nubia | 1.083 | 34 % |
| Tesorito | 1.172 | 39 % |
| NASA POWER | 1.904 | **73 %** |

La cifra que decide no es el total, es la frecuencia. **NASA llueve casi tres de cada cuatro
días**: es la llovizna típica de los productos satelitales, que reparten la lluvia en muchos
días flojos en vez de pocos fuertes. Con NASA de referencia casi no habría días secos, y
sin días secos no hay transición de seco a lluvioso que detectar.

**La referencia es el pluviómetro.** El total anual resultante (1.035 mm) queda por debajo de
las cifras municipales publicadas (~2.000 mm), y eso **no se sabe resolver con estos datos**:
puede que La Nubia sea más seca que la media del municipio o que los pluviómetros
subcuenten. **Para este proyecto no cambia nada**, porque todo se mide en anomalías
relativas al propio mes, y un factor multiplicativo no mueve una anomalía relativa.

### El límite que hay que tener presente

**Solo el 42,9 % de los días tiene pluviómetro.** El resto usa NASA escalado, que acierta el
total del mes pero no el día exacto de la lluvia (r = 0,18 contra la estación, día a día).

La columna `precip_con_estacion` dice cuáles son. **Para buscar transiciones día a día,
restringir a esos días o trabajar con acumulados de 7 días**, que son robustos a esto.

> **Actualizado el 2026-09-29:** tras quitar la falla del pluviómetro (sección siguiente),
> los días con pluviómetro válido son el **34,7 %**, no el 42,9 %.

### La falla del pluviómetro de La Nubia (octubre de 2025 a julio de 2026)

**El problema.** Desde octubre de 2025 el pluviómetro reporta **0 mm días enteros** mientras NASA
registra lluvia normal. No falta el dato: el dato es falso, y el filtro de completitud no lo
detecta porque el registro está completo.

| Mes | Pluviómetro (mm, días con dato) | NASA (mm) |
|---|---|---|
| 2025-10 | 4,2 (31) | 202,6 |
| 2026-01 | 8,8 (30) | 240,3 |
| 2026-02 | 1,6 (28) | 200,4 |
| 2026-03 a 06 | **0,0 cada mes** | 103-159 |

**Por qué es grave para este proyecto.** El consenso toma el pluviómetro como referencia, así que
**fabricaba sequías**: marzo-junio de 2026 salían como los meses más secos de la serie. El
proyecto busca justamente el paso de seco a lluvioso, así que esas sequías falsas fabricaban
«rupturas». Además, `corregir()` calcula el factor con que se escala NASA **sobre el solape con
el pluviómetro**, de modo que los meses fallidos contaminaban también ese factor en toda la serie.

**La regla** (`pluviometro_fallido()` en el script):
- En 31 días centrados, un día se marca como falla si el pluviómetro suma **menos del 10 %** de lo
  que suma NASA **y** NASA supera **60 mm**.
- Se mira a escala de un mes y no de un día, porque un día seco aislado es real.
- **Por qué el 10 %:** en los 34 meses con ≥ 20 días de pluviómetro, la razón pluviómetro/NASA de
  los meses sanos va de **0,27 a 1,42** (mediana 0,54). En los fallidos es **< 0,04**. El umbral
  deja margen a los dos lados.
- **El orden importa:** la falla se quita **antes** de calcular los factores de escala.

**Resultado.**
- 199 días marcados: 20 en octubre de 2025, enero a junio de 2026 completos y 5 en julio.
- Van a la columna `pluviometro_fallido` y se tratan como día sin pluviómetro.
- La lluvia anual del consenso pasa de ~1.035 a **1.297 mm**.
- El nivel medio según el número de fuentes queda parejo: 3,47 mm con una, 3,71 con dos.

**Efecto en resultados ya publicados.** En el cuaderno 07, «seco → lluvioso» sobre los 0-4 años pasa
de +22,0 ± 17,8 % (13 episodios) a **+13,4 ± 15,0 % (17 episodios)**, que ya no se distingue de
cero. La madrugada con lluvia fuerte pasa de −7,8 % a −4,3 %, tampoco significativo.

**Lo que no se arregla:** 2021 no tiene **ninguna** medida de lluvia en tierra. Es reanálisis
puro y sale como el año más seco.

---

## Las banderas

| Bandera | Antes | Después | Definición nueva |
|---|---|---|---|
| `llovio` | 98,8 % | **58,5 %** | ≥ 1 mm (día de lluvia de la OMM) |
| `lluvia_fuerte` | 22,0 % | **5,1 %** | el 5 % más lluvioso **de ese mes** |
| `dia_frio` | 0,0 % | **10,1 %** | media ≤ percentil 10 **de ese mes** |
| `dia_calido` | 1,4 % | **10,2 %** | media ≥ percentil 90 **de ese mes** |

Frío y cálido son relativos al propio mes por una razón física: **en 2.432 días la máxima no
llegó a 26 °C ni una vez**, y el rango de la media cabe en cuatro grados. Un umbral fijo en
una ciudad sin estaciones térmicas es una constante.

`llovio` al 98,8 % era un artefacto del dato inflado. Llueve mucho en Manizales —el 58,5 % de
los días— pero no siempre.

Los acumulados (`precip_7d`, `precip_30d`, `temp_media_7d`, `humedad_7d`) exigen la
ventana completa: un hueco da nulo, no una suma más corta que parezca un periodo seco.

---

## Lo que queda anulado

Todo lo calculado sobre la versión anterior de `precip_consenso_mm`, `precip_7d`,
`precip_30d`, `llovio`, `lluvia_fuerte`, `dia_frio` y `dia_calido`. En particular:

- Las 8 y 24 rupturas seca→lluviosa y su efecto medido, en `CLAUDE.md`.
- Las cifras de clima de `patrones/calendario.py` y `clustering/fechas.py`.

## Límites conocidos, medidos el 2026-09-30 (cuaderno 12)

- **Las horas de lluvia de Open-Meteo no sirven.** La mediana es de 24 horas al día, y la
  correlación semanal con el pluviómetro es de 0,18. Quedan fuera de todo índice.
- **El consenso sobreestima los días con lluvia.** En los días con pluviómetro válido, el
  pluviómetro marca lluvia el 43,0 % de los días; el consenso, el 66,0 %. La mediana entre
  fuentes promedia el pluviómetro con la llovizna de NASA.
  - Las rachas secas que salen del consenso son más cortas de lo real y dependen de la fuente
    que tenga cada día: en 2025, el 32,6 % de los días con pluviómetro son secos, contra el
    14,9 % de los que no lo tienen.
  - Para rachas secas, usar solo los días con pluviómetro válido o los acumulados.
- **La radiación del consenso es exactamente la de NASA POWER.** Open-Meteo trae vacías la
  radiación, el viento y la evapotranspiración.

## Cómo comprobar que sigue bien

El script imprime una auditoría al final. Lo que hay que mirar:

- **Temperatura media ~16,5 °C.** Si sale ~17,7, la referencia volvió a ser (máx+mín)/2.
- **Ciclo de lluvia bimodal**: picos en marzo-junio y octubre-noviembre, valles en
  enero-febrero y septiembre.
- **«Nivel medio según cuántas fuentes hubo»**: los valores deben parecerse. Si divergen,
  hay una fuente fuera de escala colándose en la mediana.


## Clima completo para el cuaderno 17 (2026-10-05)

`calendarios/clima/clima_completo.py` escribe `calendarios/clima_completo.csv.gz`: datos de 2010 a hoy en La
Nubia, con horas de sol, nubosidad, punto de rocío, déficit de presión de vapor, humedad, rachas, extremos y la
transición de seco a lluvioso.

**La lluvia del ERA5 (Open-Meteo Archive) está rota en Manizales.**
- Da ~16.000 mm al año, 10 veces lo real.
- Su correlación diaria contra el pluviómetro válido es de −0,02.
- **No se usa.**

**La lluvia sale de NASA POWER (PRECTOTCORR):**
- da ~2.060 mm al año;
- contra el pluviómetro válido correlaciona 0,30 por día, 0,52 por semana y 0,80 por mes;
- por eso toda variable de lluvia del clima completo usa **ventanas de 7 días o más**.

**Las demás variables del ERA5, frente al clima unificado:**
- temperatura media, 0,75;
- humedad, 0,69;
- radiación, 0,69;
- temperatura mínima, 0,52;
- horas de sol frente a la radiación, 0,54;
- nubosidad frente a la radiación, −0,43.

## Actualización incremental (2026-10-15)

Los tres scripts de clima pasaron a ser **incrementales**: lo ya escrito no cambia salvo los últimos 10 días y las
celdas vacías; `--rehacer` vuelve al comportamiento anterior. Por qué, y la tabla de cuánto movía el pasado
rehacerlo todo, en `CAPTURAS.md`, «Actualización incremental». Lo que toca a este documento:

- **Las correcciones de arriba siguen intactas.** `pluviometro_fallido()`, la exclusión de Planalto, el escalado
  mes a mes y la lluvia del ERA5 fuera del consenso no se tocaron; solo cambió qué filas se escriben.
- **NASA POWER es provisional en sus últimos ~3 meses.** Al rehacer el 2026-10-15, los días 2026-05-31 a
  2026-08-27 cambiaron (precipitación hasta 14,8 mm en un día, humedad hasta 6,5 puntos). Con el modo incremental
  esos días quedan como se bajaron; el cambio se cuenta y no se aplica.
- **Open-Meteo cambió su máxima y mínima diarias en toda la serie** (+0,05 y −0,06 °C de media; la media diaria no
  cambió). Con el modo incremental no entra en el pasado.
- **El ERA5 de los últimos días trae valores imposibles** (mínimas de 3,0 y 5,9 °C el 24-25 de septiembre de 2026,
  corregidas después a ~15 °C). Por eso se reabren siempre los últimos 10 días.
- **Los factores y percentiles de `clima_unificado.py` dependen de toda la serie.** Solo añadir 49 días movía
  188-569 celdas del pasado por variable. El modo incremental conserva las filas viejas y calcula las nuevas con
  los factores del día; el desfase entre ambas es del orden de 0,01-0,02 °C de media.
- **Desde el 2026-08-25 no hay pluviómetro en el consenso**: `clima_ideam.csv` no tiene script que lo regenere.
  La lluvia posterior es NASA escalada (sirve para acumulados, no para el día exacto).
  **Resuelto el mismo día** con `clima_ideam.py`: ver «El pluviómetro IDEAM al día».

## El pluviómetro IDEAM al día (2026-10-15)

`calendarios/clima/clima_ideam.py` regenera `clima_ideam.csv`. El CSV llegó hecho en el commit 3d68117, sin el
script que lo produjo, y se había quedado en el 2026-08-25. Desde entonces la lluvia del consenso era solo NASA
escalada.

```
.venv\Scripts\python.exe calendarios/clima/clima_ideam.py             # diario, sin argumentos; después clima_unificado.py
.venv\Scripts\python.exe calendarios/clima/clima_ideam.py --rehacer   # rehace La Nubia entera (mueve el pasado)
```

### La fuente

API Socrata de datos.gov.co, sin token. Estación **AEROPUERTO LA NUBIA - AUT** (`0026155110`).

| Conjunto | Qué es | Sensor que se usa | Lecturas por día |
|---|---|---|---|
| `s54a-sgyg` | «Precipitación», mm | `0240` | 144 (cada 10 minutos) |
| `sbwg-7ju4` | «Temperatura Ambiente del Aire», °C | `0068` | 24 (horaria) |

- Columnas de la fuente: `codigoestacion`, `codigosensor`, `fechaobservacion` (hora local, sin zona),
  `valorobservado`, `nombreestacion`, `departamento`, `municipio`, `zonahidrografica`, `latitud`, `longitud`,
  `descripcionsensor` y `unidadmedida`. Se usan las cuatro primeras.
- **Desde el 2026-08-12 hay un segundo sensor GPRS de cada variable**, con una lectura cada 2 minutos: `0257` para
  la lluvia y `0071` para la temperatura. Miden lo mismo:
  - entre el 12-ago y el 14-oct la lluvia total es idéntica, 331,2 mm en los dos;
  - la temperatura media difiere 0,00 ± 0,06 °C por día.
  
  **No se usan**, para que la serie siga siendo la misma desde 2022.
- Retraso: consultado el 15-oct a mediodía, el día 14 ya estaba completo (144/144 y 24/24).

### La reconstrucción, y su acierto

No había script, ni en el repositorio ni en el historial de git. El método se reconstruyó a partir de los datos.

| Columna | Regla |
|---|---|
| `precipitacion_mm` | suma de las lecturas del día, a 2 decimales |
| `completitud_precip` | mín(1, lecturas / 144), a 3 decimales. **144 fijo para todas las estaciones** |
| `temp_media` | media decimal exacta de las lecturas, redondeada a 2 decimales con numpy |
| `temp_min`, `temp_max` | extremos de las lecturas |
| `n_registros_temp` | número de lecturas de temperatura |
| fila | hay fila si ese día hay lluvia o temperatura; lo que falte va vacío |

Antes de agregar se quitan las lecturas repetidas. La fuente publica **cada lectura dos veces** de octubre de 2024 a
febrero de 2025, y **diecinueve veces** el 2026-07-24. Si no se quitan, la lluvia de esos días sale doble.

**Acierto** sobre los 977 días de La Nubia del CSV (2022-03-21 a 2026-08-25), comparados con lo que publica hoy la
fuente:

| Columna | Días idénticos |
|---|---|
| `temp_media`, `temp_min`, `temp_max`, `n_registros_temp` | **977 de 977** |
| `completitud_precip` | 976 de 977 |
| `precipitacion_mm` | 973 de 977 |
| Días con fila | los mismos 977: en 50 días la fuente no rellenó ningún hueco |

- **El redondeo de la media importa.**
  - Con la media en coma flotante fallaban 2 días por 0,01 °C: 420,6 / 24 da 17,525000000000002 y sube a 17,53,
    mientras que el CSV dice 17,52.
  - Con redondeo al par sobre el decimal exacto fallaban 11.
  - Lo que da el CSV en los 977 días es la media decimal exacta seguida del redondeo de numpy. Es lo mismo que da
    el `avg()` de Socrata.
- **Los 5 días que no coinciden son un defecto del CSV anterior, no del método.**
  - El 16, 17, 22 y 23 de agosto de 2026 el CSV trae 14,0 / 62,97 / 1,67 / 7,0 mm. El pluviómetro marca
    8,4 / 37,8 / 1,0 / 4,2.
  - Es **×5/3** en los cuatro días: el CSV anterior mezcló el sensor de 10 minutos con el nuevo de 2 minutos.
  - Por la misma mezcla, el 13-ago trae una completitud de 1,0 en vez de 0,993.
  - No se logró reproducir la cifra exacta de la mezcla (62,97): la carga del sensor nuevo cambió desde entonces.
  - Ningún otro día del CSV es posterior al 12-ago, así que el defecto no llega más atrás.
- **Las estaciones cerradas también coinciden en sus valores.**
  - Tesorito Finca (`0026155170`): 163 de 163 días idénticos en lluvia, completitud, media, máxima y número de
    lecturas.
  - Planalto (`0026155503`): lluvia idéntica en 632 de 632 días.
  - La completitud de Planalto confirma el 144 fijo: con su frecuencia real (288 lecturas) solo coincidirían 429
    días.
- **Lo que no se reconstruye es qué filas eligió el empalme.**
  - La Nubia manda todos los días en que tiene dato. Pero hay 114 días de 2020 y 2022-2023 en que Planalto tiene
    lluvia publicada y el CSV no tiene fila.
  - Por eso las filas de Tesorito y Planalto **se conservan tal como están**, también con `--rehacer`, y el script
    solo baja La Nubia.
  - Planalto está excluido del consenso de todos modos.

### Cómo se actualiza

Igual que los demás actualizadores incrementales (`CAPTURAS.md`), con `calendarios/actualizacion.py`:

- **Cola de 10 días.** Lo medido no pide más:
  - el día anterior llega completo;
  - en 50 días la fuente no cambió ningún valor ni rellenó ningún hueco de los 977 días;
  - y 10 es lo que reabre `clima_unificado.py`, así que un día que el IDEAM complete tarde sigue dentro de la cola
    de los dos archivos.
- Se bajan 120 días para **contar**, sin aplicarlo, lo que la fuente cambiaría del pasado («revisiones del pasado
  no aplicadas»). Si antes de la cola trae días que el archivo no tiene, avisa y no los añade.
- Hoy no se baja, porque está a medias. Si se corre de madrugada, ayer puede estar incompleto; la cola lo completa
  al día siguiente.
- `proteger()` aborta sin escribir si la fuente acaba antes que el archivo o si trae menos del 98 % de los días de
  La Nubia del tramo bajado.
- `escribir_si_cambia()`: si no hay cambios, el archivo no se toca.
- Cualquier fallo de la API (tras tres intentos) o de `proteger` sale con **código 1**. Comprobado con la red
  cortada y con una fuente truncada al 30-sep: código 1 y el archivo intacto.
- Tarda de 20 s a 1 minuto según cómo responda datos.gov.co. Una segunda corrida dice «sin cambios, no se toca».
- `--rehacer` baja La Nubia entera por tramos de un mes: tardó 20 minutos el 2026-10-15 por la tarde, con el
  servidor lento (por la mañana la misma descarga tomó 3 minutos). Probado sobre una copia: solo cambia la
  completitud del 13-ago, la revisión que el modo incremental cuenta y no aplica.

### La primera corrida (2026-10-15)

- `clima_ideam.csv`: último dato **2026-08-25 → 2026-10-14**. Son 50 días nuevos, sin ningún faltante del 26-ago al
  14-oct. Lluvia de septiembre: 121,4 mm (30 días); del 1 al 14 de octubre: 158,0 mm.
- Los cuatro días inflados de agosto entraron en la cola, y por tanto se corrigieron. La completitud del 13-ago
  queda como estaba: es la «1 revisión no aplicada».
- **`pluviometro_fallido` no se dispara en ningún día nuevo.**
  - Del 26-ago al 14-oct el pluviómetro suma 279,8 mm y NASA 386,9.
  - Es una razón de 0,72, dentro del rango de los meses sanos (0,27 a 1,42).
  - La falla de 2025-2026 terminó.

**Lo que pasa en `clima_unificado.csv.gz` en modo incremental**, medido contra una copia previa:

| Días | `precipitacion_mm` (pluviómetro) | Entra al consenso (`precip_con_estacion`) |
|---|---|---|
| 26-ago a 04-oct (40) | rellenada | **no**: el consenso sigue siendo NASA escalada |
| 05-oct a 14-oct (10, la cola) | rellenada | **sí** |

- `fusionar()` rellena las celdas vacías del pasado (`precipitacion_mm`, `completitud_precip`, `temp_media`…) pero
  no recalcula las columnas derivadas.
  - En esos 40 días, la columna del pluviómetro y el consenso dicen cosas distintas.
  - El caso más claro es el 13-sep: el pluviómetro marca 41,4 mm y el consenso 4,1.
- **Para analizar, `precip_con_estacion` sigue siendo la llave correcta**, porque es coherente con el consenso.
- La corrección de los cuatro días de agosto tampoco llega al unificado: sus filas son anteriores a la cola.
- **Corregido el mismo día en `clima_unificado.py`** (ya no hace falta `--rehacer`). Ahora, si un dato llega tarde a
  un día ya escrito (una celda vacía que la fuente trae llena), ese día se **recalcula entero**, igual que la cola, y
  no solo se rellena la columna cruda (`fusionar(..., rellenar=False)`).
  - El alcance llega hasta `LLEGADA_TARDIA_MAX = 120` días atrás; más atrás no se toca nada.
  - Medido, partiendo de la copia anterior a la llegada del IDEAM: se recalcularon 51 días, y solo cambiaron filas
    del 25-ago al 04-oct.
  - Los 50 días del 26-ago al 14-oct entran al consenso con pluviómetro (`precip_con_estacion = True`), ninguno con
    `pluviometro_fallido` y **0 filas incoherentes**. El 13-sep pasa a un consenso de 22,9 mm.
  - Una segunda corrida: «sin cambios, no se toca».
- Lo que sigue pendiente del propietario: los cuatro días de agosto inflados ×5/3 (16, 17, 22 y 23) siguen así en el
  unificado. No son celdas vacías sino revisiones del pasado, y esas solo se aplican con `--rehacer`.
