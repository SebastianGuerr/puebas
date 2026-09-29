# Inventario de variables externas candidatas

**Qué es.** El catálogo de todo lo que podría mover el **conteo total de triages** de
urgencias en Manizales. Hay una fila por variable o familia, con su fuente y su estado. Es el
insumo para formular hipótesis **después**: aquí no se concluye nada. Lo decidió el
propietario el 2026-09-28 (ver `docs/CONTEXTO.md`).

**Criterios de cada fila:**
- La fuente es **oficial o comprobable**, y lleva su URL.
- La cobertura se compara con la del desenlace: triage diario desde 2020-01-01.
- **Rezago de publicación**: una variable que se publica meses después sirve para explicar y
  entrenar, no para pronosticar.
- **Calidad** medida, no supuesta: huecos, escalones, cambios de esquema.

**Estados:**
- **integrada**: hay un script que la rehace y una salida auditada.
- **manual**: calendario escrito a mano, pendiente de reemplazo.
- **candidata**: fuente identificada, sin integrar.
- **descartada**: se miró y no sirve; se dice por qué.

---

## Salud pública (vigilancia epidemiológica)

| Variable | Fuente | Cobertura | Granularidad | Rezago | Estado | Notas |
|---|---|---|---|---|---|---|
| Consultas por IRA, todas las causas, hospitalización, UCI y muertes, por edad (evento 995) | Microdatos SIVIGILA, INS — portalsivigila.ins.gov.co/Microdatos | 2012-2025 (usable desde 2015) | semana epidemiológica × institución | ~7-8 meses | **integrada** | `vigilancia_sivigila.csv.gz`. El denominador tiene escalones (+60 % en 2021, +35 % en 2024) |
| Casos de EDA, total y por edad (evento 998) | Microdatos SIVIGILA | 2011-2025 | semana × institución | ~7-8 meses | **integrada** | Cae a la mitad desde 2020, sin explicación |
| Consultas totales por institución de Manizales | Microdatos SIVIGILA (995, `tot_exturg`) | 2012-2025 | semana × institución | ~7-8 meses | **integrada** | `vigilancia_sivigila_instituciones.csv.gz`. Mide movimientos de la red |
| Vigilancia de 2026 casi en tiempo real: evento × semana de Manizales, IRA 995 con denominador | Power BI del INS: tablero 006 «Vigilancia Rutinaria» (tabla `Rutinaria 2026`) y tablero 995 (tabla `IRA`) | 2026 (006); 2015-2019 y 2021-2026 (995) | semana × municipio | ~7 días; las 2-3 últimas semanas son provisionales | **integrada** | `calendarios/vigilancia/powerbi.py`, una descarga congelada por fecha en `calendarios/vigilancia/powerbi/AAAA-MM-DD/`. API no documentada. Empalme medido en `VIGILANCIA.md` |
| Ventanas estacionales IRA, EDA y dengue | `vigilancia_salud_manizales_caldas.csv` | 2019-2026 | fecha fija anual | — | manual → **a reemplazar** | El mes del año explica el 93-100 % de ellas |

### Salud pública: eventos individuales del SIVIGILA (microdatos + Power BI)

Censo del 2026-09-28 (`calendarios/vigilancia/eventos.py`). Criterio de entrada, fijado por
el propietario: **media de al menos 1 caso por semana en Manizales en 2023-2025**, contando
por municipio de ocurrencia. Salida: `calendarios/vigilancia_sivigila_eventos.csv.gz`; el
censo completo, con los casos de cada año, en `calendarios/vigilancia_sivigila_eventos_censo.csv`.

Para todos: fuente = microdatos SIVIGILA (portalsivigila.ins.gov.co/Microdatos), rezago
**~8 meses** (2025 se publicó en agosto de 2026); 2026 sale del tablero Power BI 006 con
**~7 días**. Granularidad: semana epidemiológica. **Aviso de fuga:** varios son pacientes
que consultan en urgencias (300, 875, 356, 365, 549): parte del propio desenlace, solo
entran con rezago o como desenlaces específicos.

| Código | Evento | Cobertura (microdatos) | Casos Manizales 2023 · 2024 · 2025 | Media/sem. | Estado | Notas |
|---|---|---|---|---|---|---|
| 300 | Agresiones por animales potencialmente transmisores de rabia | 2015-2025 | 1.364 · 1.345 · 1.555 | 27,2 | **integrada** | Caída en 2020 (984) |
| 875 | Violencias de género e intrafamiliar | 2015-2025 | 1.255 · 1.308 · 1.332 | 24,8 | **integrada** | Crece +51 % entre 2015 y 2025 |
| 356 | Intento de suicidio | 2016-2025 (no existe antes) | 703 · 596 · 566 | 11,9 | **integrada** | |
| 365 | Intoxicaciones (suma de 360, 370, 380, 390, 400, 410, 412 y 414) | 2015-2025 | 548 · 510 · 444 | 9,6 | **integrada** | Código de 2026. Escalón en 414 (psicoactivas): 565 → 41 entre 2016 y 2021 |
| 370 | Intoxicación por fármacos (componente de 365) | 2015-2025 | 419 · 375 · 325 | 7,1 | **integrada** | Pasa el umbral por sí sola |
| 549 | Morbilidad materna extrema | 2015-2025 | 247 · 251 · 253 | 4,8 | **integrada** | Escalón 2020: 89 → 183 → 266. Útil solo si el triage cubre obstetricia (12,6 %) |
| 831 | Varicela | 2015-2025 | 222 · 211 · 237 | 4,3 | **integrada** | 1.316 en 2015 → 110 en 2020 |
| 155 | Cáncer de mama y cuello uterino | 2016-2021, 2023-2025 (**2022 no publicado**) | 248 · 216 · 200 | 4,2 | **integrada** | Crónico: sin dinámica de urgencias esperable |
| 850 | VIH / sida | 2015-2025 | 207 · 173 · 170 | 3,5 | **integrada** | Crónico |
| 813 | Tuberculosis (suma de 810, 820 y 825) | 2015-2025 | 148 · 170 · 138 | 2,9 | **integrada** | Código de 2026. 820 (pulmonar) pasa el umbral por sí sola: 2,6/sem. |
| 346 | IRA por virus nuevo (COVID-19) | **solo 2024-2025** | — · 202 · 20 | 2,1 | **integrada** | Entra por el umbral, pero se apaga: 20 en 2025, 6 en 2026 |
| 113 | Desnutrición aguda en menores de 5 años | 2016-2025 | 105 · 81 · 49 | 1,5 | **integrada** | Salto 36 → 105 en 2023 |
| 620 | Parotiditis | 2015-2025 | 63 · 53 · 47 | 1,04 | **integrada** (en el límite) | Brote de 2018: 328 casos |
| 452 | Lesiones por pólvora y explosivos | 2015-2025 | 14 · 22 · 25 | 0,39 | **marcador** | Semanas con ≥ 1 caso; se concentran en diciembre-enero. 0 filas en el 006 de 2026 |
| 349 | Brotes de ETA (colectivo, un registro por brote) | 2015-2025 | 5 · 7 · 10 brotes | 0,14 | **marcador** | Ficha distinta; hasta 2017, la del antiguo 350 |
| 348 | IRAG inusitado | 2015-2025 | 164 · 5 · 17 | — | **marcador** | 363 casos en 2022 y 164 en 2023: la ficha absorbió COVID |
| 414 | Intoxicación por sustancias psicoactivas | 2015-2025 | 58 · 58 · 35 | 0,96 | volumen insuficiente (entra en 365) | En el límite |
| 735 | Anomalías congénitas | 2023-2025 | 31 · 60 · 59 | 0,96 | volumen insuficiente | En el límite. En 2026 se notifica como 215 (1,0/sem.) |
| 750 | Sífilis gestacional | 2023-2025 | 56 · 40 · 51 | 0,94 | volumen insuficiente | En el límite |
| 360 | Intoxicación por plaguicidas | 2015-2025 | 29 · 38 · 29 | 0,61 | volumen insuficiente (entra en 365) | |
| 210 | Dengue | 2023-2025 | 5 · 84 · 4 | 0,59 | volumen insuficiente | 2024 fue año epidémico en el país; Manizales, a 2.150 m, no tiene transmisión documentada ([I]) |
| 410 | Intoxicación por otras sustancias químicas | 2015-2025 | 31 · 32 · 20 | 0,53 | volumen insuficiente (entra en 365) | |
| 560 | Mortalidad perinatal y neonatal tardía | 2023-2025 | 26 · 28 · 20 | 0,47 | volumen insuficiente | |
| 340, 330, 341 | Hepatitis B, A y C | 2023-2025 | 14·17·13 · 3·30·8 · 5·19·8 | ≤ 0,28 | volumen insuficiente | |
| 412 | Intoxicación por monóxido de carbono | 2015-2025 | 4 · 7 · 30 | 0,26 | volumen insuficiente (entra en 365) | 2025: 14 casos en una semana |
| 810, 825 | Tuberculosis extrapulmonar y farmacorresistente | 2015-2025 | 13·14·9 · 4·1·4 | ≤ 0,23 | volumen insuficiente (entran en 813) | |
| 101, 459, 740, 800, 100, 520, 530, 456, 400, 420, 510, 343, 455 | Otros animales venenosos, cáncer infantil, sífilis congénita, tos ferina, ofidismo, meningitis, leucemia, solventes, leishmaniasis, hipotiroidismo congénito, leptospirosis | 2023-2025 | 0 a 19 al año cada uno | ≤ 0,19 | volumen insuficiente | Casos por año en el censo |
| 298, 345, 490, 550, 600, 880, 205, 320, 380, 450, 495, 590, 112, 217, 220, 305, 310, 390, 430, 440, 457, 460, 470, 500, 540, 580, 739, 760, 780, 895 | Resto del catálogo (vectores, malaria, mortalidades, meningococo, etc.) | 2023-2025 | 0 a 3 al año cada uno | ≤ 0,02 | volumen insuficiente | 345: Manizales no es sitio centinela |
| 110 | Bajo peso al nacer | 2012-2022 | 149 · 164 · 132 (2020-2022) | 2,8 | **sin publicar desde 2022** | Tendría volumen, pero no hay microdatos recientes |
| 228, 230, 458, 480, 610, 670, 710, 730, 770, 790 | Flúor, difteria, pólvora (código antiguo), malaria malariae, PFA, rabia humana, rubéola, sarampión, tétanos neonatal, tifus | terminan entre 2009 y 2022 | 0 a 1 al año (458: 0,38/sem.) | — | sin publicar | 458 es el antecesor del 452 |

## Clima

| Variable | Fuente | Cobertura | Granularidad | Rezago | Estado | Notas |
|---|---|---|---|---|---|---|
| Temperatura, lluvia, humedad, viento y radiación | IDEAM, METAR La Nubia, Open-Meteo, NASA POWER → `clima_unificado.csv.gz` | 2020-01 a 2026-08 | día | días | integrada, **pendiente de auditoría** | El propietario sospecha cálculos mal hechos. Solo el 42,9 % de los días tiene pluviómetro |
| Pronóstico de clima archivado | Open-Meteo Historical Forecast / Previous Runs | 2021-2024 → hoy | día | 0 | candidata | Lo que se tendría de verdad al pronosticar |
| Fase ENSO (El Niño / La Niña) | NOAA CPC, ONI → `calendarios/enso_oni.csv` (`calendarios/clima/enso.py`) | 1950-2026 | trimestre móvil | ~1 mes | **integrada** (2026-09-29) | Sustituye los periodos escritos a mano. El Niño 2026 marcado «en curso». ENSO → temperatura de Manizales r = +0,49 (cuaderno 09) |

## Calendario

| Variable | Fuente | Cobertura | Estado | Notas |
|---|---|---|---|---|
| Festivos, puentes, quincena, vacaciones escolares, Semana Santa, etc. | `calendario_Colombia.csv` (`calendario_colombia.py`) | 2020-2026 | integrada | Es el **control**, no el producto. **Sus vacaciones escolares son 122 fechas fijas cada año: no usarlas.** |
| **Recesos escolares oficiales de Manizales** (fin de año, Semana Santa, mitad de año, octubre) | Resoluciones de la Secretaría de Educación, con URL por fila → `calendarios/calendario_escolar_manizales.csv` | 2021-2026 | integrada (manual con fuente) | Receso → IRA ciudad −0,20 y varicela −0,18 en la misma semana (cuaderno 09) |

## Eventos sociales

| Variable | Fuente | Cobertura | Estado | Notas |
|---|---|---|---|---|
| Feria, teatro, Grita Fest, feria del libro, aniversario, etc. | `eventos_manizales_2020_2026.csv` | 2020-2026 | manual | 99 filas, casi todas recurrentes anuales |

| **Fiestas de los municipios de Caldas** | Alcaldías, Gobernación, Cultura de Caldas, viajaporcolombia y prensa, con una URL por fila → `calendarios/fiestas_caldas_2020_2026.csv` | 2020-2026, 26 municipios, 177 ediciones | integrada (manual con fuente) | 167 filas con URL; 119 fechas confirmadas y 58 estimadas; marca V/B/I. **Filtrar por `estado`**: en las canceladas o aplazadas, la fecha es la prevista. Detalle en `CONTEXTO_PICOS.md`, sección 1bis |

## Catástrofes y emergencias

| Variable | Fuente | Cobertura | Estado | Notas |
|---|---|---|---|---|
| Deslizamientos, sismos, vendavales, terremoto de 2026 | `desastres_manizales_2020_2026.csv` | 2020-2026 | manual | 17 filas, 4 sin verificar |
| Actividad del Nevado del Ruiz, caída de ceniza | Servicio Geológico Colombiano (en el CSV de vigilancia) | 2012-2026 | manual | Periodos escritos a mano |
| Pandemia de COVID-19 (cuarentenas, picos) | En el CSV de vigilancia | 2020-2022 | manual | |

## Sistema de salud

| Variable | Fuente | Cobertura | Estado | Notas |
|---|---|---|---|---|
| **Triage por entidad administradora** (Nueva EPS, Sura, otras EPS, SOAT, ARL, particulares, régimen especial…) | Base del hospital: `DIM_TRIAGE.GEENENTADM` → `DIM_ENTIDAD` (`python -m extraccion --entidad`) | 2020-2026 | **integrada** (`salidas/triage_entidad.parquet`) | Grupos en `extraccion/entidades.py`, borrador a revisar. **Nueva EPS = 58 % del triage** y la causa de los escalones de nivel (nov-2025, jul-2026). El SOAT mide los accidentes de tránsito que llegan al SES |
| Cierres de servicios a EPS, intervenciones de la Supersalud | Prensa + Alcaldía (ver `CONTEXTO.md`, 2026-09-28) | 2024-2026 | **no existe como calendario** | Hacen falta las fechas SES-Nueva EPS (decisión #11 del HANDOFF) |

## Seguridad y tránsito

| Variable | Fuente | Cobertura | Granularidad | Rezago | Estado | Notas |
|---|---|---|---|---|---|---|
| Lesiones y homicidios en accidente de tránsito, lesiones personales, homicidio, violencia intrafamiliar | MinDefensa en datos.gov.co (`ntej-qq7v`, `uav5-b85g`, `jr6v-i33g`, `m8fd-ahd9`, `gepp-dxcs`); `calendarios/seguridad/mindefensa.py` | 2015-2026-08 | día, Manizales | 2-6 semanas | **integrada** (`calendarios/seguridad_mindefensa.csv.gz`) | Solo sumas por día. Solo lo denunciado a la Policía. Escalón en el tránsito de 2019. **No correlaciona con el SOAT del SES (r = 0,01)**, salvo en la Feria |

---

*Se actualiza cada vez que una variable cambia de estado.*
