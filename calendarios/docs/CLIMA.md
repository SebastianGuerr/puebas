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
| `clima_ideam.csv` | Estaciones IDEAM, empalmadas por cercanía | 3 estaciones, ver abajo | 1.776 días |
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

## Cómo comprobar que sigue bien

El script imprime una auditoría al final. Lo que hay que mirar:

- **Temperatura media ~16,5 °C.** Si sale ~17,7, la referencia volvió a ser (máx+mín)/2.
- **Ciclo de lluvia bimodal**: picos en marzo-junio y octubre-noviembre, valles en
  enero-febrero y septiembre.
- **«Nivel medio según cuántas fuentes hubo»**: los valores deben parecerse. Si divergen,
  hay una fuente fuera de escala colándose en la mediana.
