# Fuentes de vigilancia — informe de investigación (2026-09-28)

> Copia del informe del agente de investigación. [V] = abierto, descargado o consultado; [I] = inferido. Los scripts de consulta a Power BI citados están en el scratchpad de la sesión del 28 y se integrarán al paquete en el paso de 2026. El porqué de la construcción de la serie está en `VIGILANCIA.md`.

# Fuentes de vigilancia en salud pública para el conteo semanal de triage en Manizales

Fecha: 2026-09-28. Autor: agente investigador (solo lectura sobre el repositorio y escritura únicamente en el scratchpad).
Convención: **[V]** = verificado (se abrió, se descargó o se consultó hoy); **[I]** = inferido o razonado, sin comprobación directa.
Nada de este informe contiene filas de casos ni valores de columnas identificables: solo nombres de columna y conteos agregados.

---

## 0. Hallazgo principal: la vía Power BI del INS da 2026 semanal por municipio, sin token

### 0.a Qué tablero y qué consulta

- **Tablero**: «006 Vigilancia Rutinaria» del INS, publicado con *Publish to web* de Power BI. **[V]**
  - URL pública: `https://app.powerbi.com/view?r=eyJrIjoiNTI2OTgyYjktZmUwOS00ZGIzLWFkY2MtOTIzODNhZWNiY2VmIiwidCI6ImE2MmQ2YzdiLTlmNTktNDQ2OS05MzU5LTM1MzcxNDc1OTRiYiIsImMiOjR9`
  - El parámetro `r` es un base64 de `{"k": "526982b9-fe09-4db3-adcc-92383aecbcef", "t": <tenant>, "c": 4}`. `k` es la *resource key* pública.
  - Dónde se encuentra la URL: la lista SharePoint `MenuReporteNivel2` del portal SIVIGILA, legible sin autenticación por REST.
    `https://portalsivigila.ins.gov.co/_api/web/lists/getbytitle('MenuReporteNivel2')/items?$top=200`, con la cabecera `Accept: application/json;odata=nometadata`.
    La lista trae unos 40 tableros más, uno por evento (100, 101, 113, 205, 210, 215, 300, 310, 320, 340, 346, 352, 356, 357, 365, 455, 465, 549, 591, 740, 750, 831, 875, 880, 995 y 998). Las claves decodificadas están en `powerbi_reports.json`. **[V]**
- **Endpoints** (API interna de Power BI *publish-to-web*, no documentada) sobre el clúster `https://wabi-south-central-us-api.analysis.windows.net`: **[V]**
  1. `GET /public/reports/{k}/modelsAndExploration?preferReadOnlySession=true`, con la cabecera `X-PowerBI-ResourceKey: {k}`. Devuelve `modelId`, `dbName` (DatasetId), `reportId`, `LastRefreshTime` y `NextRefreshTime`.
  2. `POST /public/reports/conceptualschema` con el cuerpo `{"modelIds":[modelId]}`. Devuelve tablas y columnas; sirve para descubrir el nombre de la tabla de cada año.
  3. `POST /public/reports/querydata?synchronous=true` con un `SemanticQueryDataShapeCommand`. Es la consulta de datos.
- **Consulta que produce `rutinaria_2026_manizales.csv`** (script `pbi_rutinaria.py`): sobre la tabla **`Rutinaria 2026`**, que tiene las columnas `cod_eve, nom_eve, semana, t_semana, año, npais_proce, Cod_pais, Cod_Departamento, ndep_proce, Cod_municipio, nmun_proce, conteo`. La tabla **ya viene agregada por el INS** (evento × semana × municipio de procedencia → conteo) y no tiene ninguna columna de persona. Se hace `SELECT año, cod_eve, nom_eve, semana, SUM(conteo) WHERE nmun_proce = 'MANIZALES'`. Salen 494 filas, 28 eventos y las semanas 1 a 38 de 2026. **[V]**
- **¿Necesita token?** No. Solo la *resource key* pública en la cabecera. No hay cookies, ni OAuth, ni captcha. **[V]**
  - En esta red, `requests` falla por la inspección TLS corporativa («self-signed certificate in chain»). Se resolvió con `truststore.inject_into_ssl()`, que usa el almacén de certificados de Windows. `curl` (schannel) funciona tal cual. **[V]**
- **¿Es estable?** A medias. **[I]**
  - Es una API **no documentada**: Microsoft puede cambiarla.
  - El INS puede **republicar** el tablero y la clave cambia. Mitigación: leer la clave de `MenuReporteNivel2` en cada corrida, no dejarla fija en el código.
  - El nombre de la tabla lleva el año (`Rutinaria 2026`, `salida_para_rutinaria_995 2026`). En 2027 cambiará. Mitigación: descubrirlo con `conceptualschema`.
  - Límite práctico: `Window.Count` hasta 30.000 filas por consulta. Para un municipio sobra.
  - Recomendación: congelar cada semana la respuesta cruda (CSV con fecha de descarga), porque **el tablero se reescribe y las semanas recientes cambian** con la notificación tardía.

> **Advertencia de privacidad, obligatoria**. Los modelos públicos de los tableros **por evento** exponen en su esquema columnas identificables: `pri_nom_`, `pri_ape_`, `num_ide_`, `dir_res_`, `telefono_`, `lat_dir`, `long_dir` y otras. Se vio en `356 Intento de suicidio`: tabla `expertos_356_2026` y otras. **[V]**
>
> Aquí solo se leyeron **nombres de columna** y se pidieron **medidas agregadas** (`Casos`, `SUM(conteo)`). Nunca se consultó una columna de persona. Para el proyecto (regla 1 de `CLAUDE.md`), la vía que debe usarse es la tabla **ya agregada** `Rutinaria 2026` del tablero 006. En los tableros por evento, solo la medida `Calculos[Casos]` agrupada por `Calendario[Año]` y `Calendario[Semana]`, con filtro de municipio. Conviene valorar si se avisa al INS de la exposición.

### 0.b Cobertura de años anteriores, y la IRA 995 con denominador

- **`Rutinaria 2026` (tablero 006): solo 2026.** La suma por año filtrada a Manizales devuelve solo `(2026, 3.747)`. **No sirve por sí sola para empalmar.** **[V]**
- **Los tableros por evento sí traen historia.** Consulta `Calculos[Casos]` por `Calendario[Año]` y `Calendario[Semana]`, filtrada a `Municipio[CodMun] = '17001'` (script `pbi_semanal.py`). **[V]**

  | Tablero | Años con datos para Manizales | Totales anuales (Manizales) |
  |---|---|---|
  | 356 Intento de suicidio | 2016–2026 | 2016: 368 · 2024: 601 · 2025: 575 · 2026 (hasta SE37): 469 |
  | 831 Varicela | 2007–2026 | 2024: 214 · 2025: 236 · 2026: 146 |
  | 300 Agresiones por animales | 2022–2026 | 2022: 1.149 · 2023: 1.362 · 2024: 1.233 · 2025: 1.538 · 2026: 1.108 |
  | 998 EDA (colectiva) | 2019–2026 | 2019: 28.631 · 2020: 13.278 · 2021: 13.077 · 2024: 22.815 · 2025: 19.204 · 2026 (hasta SE37): 16.875 |
  | 365, 875 y 210 | la consulta genérica falla | su modelo usa otras tablas; hay que mapear cada uno con `conceptualschema` |

- **Empalme validado contra los microdatos**: [V]
  - 356 de 2016: tablero **368**; microdatos por municipio de ocurrencia **368**. Es idéntico.
  - 356 de 2024: tablero 601; microdatos 596 por ocurrencia y 603 por residencia.
  - 831 de 2024: tablero 214; microdatos 211 por ocurrencia, 212 por residencia y 214 por ocurrencia o residencia.
  - Entre 2026 del tablero 006 y el tablero por evento: 300 da 1.102 contra 1.108, 356 da 472 contra 469 y 831 da 144 contra 146.
  - **Conclusión**: el filtro municipal de los tableros equivale al **municipio de ocurrencia o procedencia** (`COD_MUN_O`) de los microdatos, con diferencias del ±1 % por actualizaciones. **[V]** para los números; **[I]** para la interpretación.
- **IRA 995 con denominador: sí.** No se tocó la integración del 995, solo se describe la cobertura. **[V]**
  - En el tablero 006, la tabla `salida_para_rutinaria_995 2026` (y otra llamada `995`) tiene `semana, año, ndep_notif, nmun_notif, SumaDetot_iraext, SumaDetot_irauci, SumaDetot_irag, tot_exturg`. `tot_exturg` es el **total de atenciones de consulta externa y urgencias por todas las causas**: el denominador. Manizales 2026: IRA en consulta externa y urgencias = 40.596; total de atenciones = 1.621.992. Solo 2026, hasta SE37.
  - En el tablero «995 Morbilidad por IRA» (clave `574df00d-…`), la tabla `IRA` tiene `semana, año, cod_mun, nom_upgd, cod_pre, grupo_1…7, grup_total, Tot_1…7, Tot_tot`: numerador por grupo de edad y **denominador** por grupo, **por UPGD**. Manizales (`cod_mun = '17001'`): **2015–2019 y 2021–2026. Falta 2020.** Ejemplos: 2024, IRA 68.411 de 1.877.985 atenciones; 2026, 42.623 de 1.696.530. Útil para el agente del 995. El detalle por UPGD permitiría incluso aislar la institución propia **[I]**.
  - La 998 también tiene tablas propias en el 006: `998` y `Salida_para_rutinaria_998 2026`, con sexo, `PTE_HOS` y `PTE_AMB`. Mi filtro por `nmun_notif` devolvió vacío, así que hay que revisar el nombre del campo de municipio. **[V]** para el esquema; el filtro está pendiente.

### 0.c Rezago y última semana disponible hoy (lunes 2026-09-28)

- Actualización del tablero 006: `LastRefreshTime = 2026-09-26T22:04` (sábado). **[V]** Los tableros por evento se actualizaron entre el 25 y el 26 de septiembre; el de 356 anuncia la próxima para el `2026-09-30T08:30`. **[V]** Es una **cadencia semanal** **[I]**, a partir de las fechas observadas.
- **Última semana con datos: SE38 de 2026** (20 al 26 de septiembre). **Está incompleta**: se actualizó el mismo sábado en que cerraba (300 trae 8 casos en SE38 contra 29 de media). **Última semana completa: SE37** (13 al 19 de septiembre). **[V]**
- **Rezago efectivo: unos 7 días** hasta la primera cifra, más la **notificación tardía**. Las 2 o 3 últimas semanas suben después, y hay que modelarlas como provisionales o descartarlas. **[I]**, apoyado en el comportamiento estándar del SIVIGILA y en la SE38 parcial observada.
- Comparación con las otras fuentes: microdatos, unos 7 meses después del cierre del año (los archivos de 2025 tienen `Last-Modified` del 7 de agosto de 2026) **[V]**; BES, unos 6 días (el de SE37 salió el 25 de septiembre) **[V]**.

### Volumen 2026 de Manizales por evento (tablero 006, SE1 a SE38, `rutinaria_2026_manizales.csv`) [V]

| cod | evento | total 2026 | semanas con casos (de 38) | media semanal | máximo semanal |
|---|---|---|---|---|---|
| 300 | Agresiones por animales potencialmente transmisores de rabia | 1.102 | 38 | 29,0 | 42 |
| 875 | Violencia de género e intrafamiliar | 901 | 38 | 23,7 | 36 |
| 356 | Intento de suicidio | 472 | 38 | 12,4 | 22 |
| 365 | Intoxicaciones (agrupa 360-414) | 344 | 38 | 9,1 | 20 |
| 549 | Morbilidad materna extrema | 216 | 38 | 5,7 | 14 |
| 155 | Cáncer de mama y cuello uterino | 148 | 35 | 3,9 | 12 |
| 831 | Varicela | 144 | 34 | 3,8 | 11 |
| 850 | VIH | 102 | 37 | 2,7 | 8 |
| 813 | Tuberculosis | 80 | 33 | 2,1 | 7 |
| 620 | Parotiditis | 16 | 13 | 0,4 | 3 |
| 348 | IRAG inusitado | 12 | 9 | 0,3 | 3 |
| 346 | IRA por virus nuevo | 6 | 6 | 0,2 | 1 |
| 210 dengue, 220, 217 y 452 pólvora | — | 0 filas en 2026 | — | — | — |

A esto se suman la 998 EDA (~456 atenciones por semana en 2026, del tablero 998) y la 995 IRA (tablas con denominador), que son colectivas.

---

## 1. Catálogo de los 84 eventos de Microdatos

Fuente: `micro.json` (1.222 archivos, 84 eventos, 2007–2025). La tabla se regenera con `catalogo.py`. Los volúmenes marcados [V] se midieron hoy: en los microdatos, por ocurrencia (O) o residencia (R) en Manizales (`17`/`001`); en 2026, con el tablero 006. El resto de la columna «relevancia» es **[I]**, un juicio razonado.

Notas previas:
- **No existe un código 350 ni un 355 (ETA individual)** en Microdatos. Solo está el **349 «ETA colectivo»**, que es una fila por brote. **[V]**
- En 2026 el INS notifica con **códigos agrupados** que no están en Microdatos: 365 «Intoxicaciones» (junta los antiguos 360 a 414), 813 «Tuberculosis», 215 «Defectos congénitos» y 115 «Cáncer en menores de 18». **[V]**, visto en el tablero 006. Para empalmar hay que **sumar los códigos antiguos**.
- Marcadas **ALTA** con serie semanal no vacía: 995, 998, 356, 875, 300 y 370 (vía 365). **Media** con serie usable: 831 y 549. El resto es serie casi vacía en Manizales o solo marcador de evento.

| cód | evento | años en microdatos (n) | relevancia | ¿serie semanal no vacía en Manizales? | por qué |
|---|---|---|---|---|---|
| 100 | Accidente ofídico | 2007-2025 (19) | baja | no | Ofidismo rural; Manizales 5/año (2024 R) y 5 en 2026 [V]. |
| 101 | Accidente por otros animales venenosos | 2025 (1) | baja | no | Solo 2025 en microdatos; 20 casos Manizales en 2026, 0,5/sem [V]. |
| 110 | Bajo Peso Al Nacer | 2012-2022 (11) | baja | no | Desenlace perinatal, no demanda general de urgencias. |
| 112 | Mortalidad Por Desnutrición | 2013-2025 (13) | baja | no | Mortalidad; volumen mínimo. |
| 113 | Desnutrición Aguda En Menores De 5 Años | 2016-2025 (10) | baja | no | Desnutrición <5 años: 80/año Manizales 2024 (1,5/sem) [V]; no es consulta urgente típica. |
| 155 | Cáncer De La Mama Y Cuello Uterino | 2016-2021, 2023-2025 (9) | baja | no | Cáncer: crónico, sin dinámica semanal de urgencias. |
| 205 | Chagas | 2012-2025 (14) | baja | no | Chagas: sin transmisión en Manizales. |
| 210 | Dengue | 2007-2025 (19) | baja | no | Dengue: 7 residentes Manizales en 2018 [V], 0 filas en 2026 [V]; ciudad a 2.150 m. A lo sumo, marcador regional de remitidos. |
| 217 | Chikunguya | 2014-2025 (12) | baja | no | Chikungunya: sin transmisión local. |
| 220 | Dengue Grave | 2007-2025 (19) | baja | no | Dengue grave: 0 residentes Manizales 2024; 2 notificados en Manizales (remitidos) [V]. |
| 228 | Exposición A Flúor | 2012-2019 (8) | baja | no | Exposición a flúor (centinela). |
| 230 | Difteria | 2018, 2021 (2) | baja | no | Difteria: casi inexistente. |
| 298 | Evento Adverso Grave Posterior A La Vacunación | 2007-2024 (18) | baja | no | ESAVI: volumen mínimo. |
| 300 | Agresiones Por Animales Potencialmente Transmisores De Rabia | 2007-2025 (19) | ALTA | sí | Agresiones animales: ~29/sem 2026, 38/38 sem [V]; se atienden en urgencias (profilaxis antirrábica). Componente directo del triage, sensible a fines de semana y vacaciones. |
| 305 | Tracoma | 2017-2019, 2022, 2024-2025 (6) | baja | no | Tracoma: no aplica. |
| 310 | Fiebre Amarilla | 2007-2009, 2016, 2023-2025 (7) | baja | no | Fiebre amarilla: no aplica. |
| 320 | Fiebre Tifoidea Y Paratifoidea | 2007-2025 (19) | baja | no | Tifoidea: 0 Manizales 2024 [V]. |
| 330 | Hepatitis A | 2007-2025 (19) | baja | no | Hepatitis A: 39/año 2024 (0,75/sem, 24 sem) [V]; 2 en 2026. Solo para brotes. |
| 340 | Hepatitis B | 2007-2025 (19) | baja | no | Hepatitis B: crónica. |
| 341 | Hepatitis C | 2014-2025 (12) | baja | no | Hepatitis C: crónica. |
| 343 | Hipotiroidismo congénito | 2007-2025 (19) | baja | no | Tamizaje neonatal. |
| 345 | ESI - Irag (Vigilancia Centinela) | 2008-2025 (18) | baja | no | ESI-IRAG centinela: Manizales no es sitio centinela (0 residentes 2024; 3 en Caldas) [V]. Solo como señal NACIONAL de circulación viral. |
| 346 | IRA por Virus Nuevo | 2024-2025 (2) | media | no | IRA por virus nuevo (COVID): 6 casos 2026 [V]; clave en 2020-2022, pero para esos años la fuente es datos.gov.co gt2j-8ykr [V existe]. |
| 348 | Infección Respiratoria Aguda Grave Irag Inusitada | 2009-2025 (17) | media | no | IRAG inusitado: 8/año Manizales 2024 [V]; marcador de gravedad, serie casi vacía. |
| 349 | ETA Colectivo | 2010-2025 (16) | media | no | ETA colectivo (brotes): 7 brotes con 180 enfermos en Manizales 2024 [V]. Marcador de evento puntual, no serie. |
| 356 | Intento De Suicidio | 2016-2025 (10) | ALTA | sí | Intento de suicidio: 603/año 2024, 11,6/sem, 52/52 sem [V]; ingresa por urgencias. Crece (365 en 2016). |
| 360 | Intoxicación Por Plaguicidas | 2007-2025 (19) | media | parcial | Plaguicidas: 41/año 2024, 26 sem [V]. Mejor sumado en «365 Intoxicaciones». |
| 370 | Intoxicación Por Medicamentos | 2007-2025 (19) | ALTA | sí | Intoxicación por medicamentos: 374/año 2024, 7,2/sem, 52/52 sem [V]; urgencias. Sumar en 365. |
| 380 | Intoxicación Por Metanol | 2007-2025 (19) | baja | no | Metanol: brotes raros. |
| 390 | Intoxicación Por Metales Pesados | 2007-2025 (19) | baja | no | Metales pesados. |
| 400 | Intoxicación Por Solventes | 2007-2025 (19) | baja | no | Solventes. |
| 410 | Intoxicación Por Otras Sustancias químicas | 2012-2025 (14) | baja | no | Otras sustancias químicas; sumar en 365. |
| 412 | Intoxicación Por Gases | 2010-2025 (16) | baja | no | Gases (CO): 7/año 2024 [V]. |
| 414 | Intoxicación Por Sustancias Psicoactivas | 2010-2025 (16) | media | parcial | Sustancias psicoactivas: 60/año 2024, 34 sem [V]; ligada a fiestas (Feria de enero). Sumar en 365. |
| 420 | Leishmaniasis cutánea | 2007-2025 (19) | baja | no | Leishmaniasis cutánea: 3 residentes Manizales 2024 [V]; sin transmisión. |
| 430 | Leishmaniasis Mucosa | 2007-2025 (19) | baja | no | Leishmaniasis mucosa. |
| 440 | Leishmaniasis Visceral | 2007-2025 (19) | baja | no | Leishmaniasis visceral. |
| 450 | Lepra | 2007-2025 (19) | baja | no | Lepra. |
| 452 | Lesiones Por Artefactos Explosivos (pólvora Y Minas Antipersonal) | 2014-2025 (12) | media | no | Pólvora: 23/año 2024, concentrados en SE48-SE1 [V]. Marcador de diciembre (ya lo captura el calendario). |
| 455 | Leptospirosis | 2007-2025 (19) | baja | no | Leptospirosis: 4/año [V]; ligada a la lluvia pero sin volumen. |
| 456 | Leucemia Aguda Pediátrica Linfoide | 2008-2025 (18) | baja | no | Leucemia pediátrica. |
| 457 | Leucemia Aguda Pediátrica Mieloide | 2008-2025 (18) | baja | no | Leucemia pediátrica. |
| 458 | Lesiones Por pólvora Y Explosivos | 2007-2014 (8) | media | no | Pólvora, código antiguo (2007-2014); empalma con 452. |
| 459 | Cáncer Infantil | 2014-2025 (12) | baja | no | Cáncer infantil. |
| 460 | Malaria Asociada (Formas Mixtas) | 2007-2009, 2011-2025 (18) | baja | no | Malaria mixta: sin transmisión. |
| 470 | Malaria Falciparum | 2007-2025 (19) | baja | no | Malaria falciparum. |
| 480 | Malaria Malarie | 2007-2009, 2011-2014 (7) | baja | no | Malaria malariae. |
| 490 | Malaria Vivax | 2007-2025 (19) | baja | no | Malaria vivax. |
| 495 | Malaria Complicada | 2007-2025 (19) | baja | no | Malaria complicada. |
| 500 | Meningitis Meningocócica | 2007-2025 (19) | baja | no | Meningitis: grave pero muy rara. |
| 510 | Meningitis Por Haemophilus Influenzae | 2007-2025 (19) | baja | no | Meningitis por Hib. |
| 520 | Meningitis Por Neumococo | 2007-2025 (19) | baja | no | Meningitis por neumococo. |
| 530 | Meningitis Tuberculosa | 2007-2025 (19) | baja | no | Meningitis tuberculosa. |
| 540 | Mortalidad por Malaria | 2007-2025 (19) | baja | no | Mortalidad por malaria. |
| 549 | Morbilidad Materna Extrema | 2012-2025 (14) | media | sí | Morbilidad materna extrema: 5,7/sem 2026, 38/38 sem [V]. Relevante solo si el triage incluye obstetricia. |
| 550 | Mortalidad Materna | 2007-2025 (19) | baja | no | Mortalidad materna. |
| 560 | Mortalidad Perinatal Y Neonatal Tardía | 2007-2025 (19) | baja | no | Mortalidad perinatal. |
| 580 | Mortalidad Por Dengue | 2007-2025 (19) | baja | no | Mortalidad por dengue. |
| 590 | Mortalidad Por Eda 0-4 Años | 2007-2025 (19) | baja | no | Mortalidad por EDA en <5 años. |
| 600 | Mortalidad Por Ira | 2007-2025 (19) | baja | no | Mortalidad por IRA: rara; marcador de gravedad. |
| 610 | Parálisis flácida Aguda (Menores De 15 Años) | 2009 (1) | baja | no | PFA: solo 2009. |
| 620 | Parotiditis | 2007-2025 (19) | media | parcial | Parotiditis: 53/año 2024, 30 sem [V]; brotes en población universitaria. Serie dispersa. |
| 670 | Rabia Humana | 2007-2010 (4) | baja | no | Rabia humana. |
| 710 | Rubéola | 2007-2009 (3) | baja | no | Rubéola. |
| 730 | Sarampión | 2011, 2018-2019 (3) | baja | no | Sarampión: casi inexistente (alerta regional 2026 en el BES). |
| 735 | Anomalías congénitas | 2010-2025 (16) | baja | no | Anomalías congénitas. |
| 739 | Síndrome Inflamatorio Multisistémico En Niños Asociado A SARS-COV2 | 2023-2025 (3) | baja | no | MIS-C. |
| 740 | Sífilis congénita | 2007-2025 (19) | baja | no | Sífilis congénita. |
| 750 | Sífilis gestacional | 2007-2025 (19) | baja | no | Sífilis gestacional. |
| 760 | Tétanos Accidental | 2007-2025 (19) | baja | no | Tétanos accidental. |
| 770 | Tétanos Neonatal | 2007-2010, 2012, 2014-2022 (14) | baja | no | Tétanos neonatal. |
| 780 | Tifus Epidémico Transmitido Por Piojos | 2025 (1) | baja | no | Tifus epidémico (solo 2025). |
| 790 | Tifus Endémico Trasmitido Por Pulgas | 2013-2014 (2) | baja | no | Tifus endémico. |
| 800 | Tos Ferina | 2007-2025 (19) | baja | no | Tos ferina: 2/año Manizales 2024 [V]. |
| 810 | Tuberculosis Extra Pulmonar | 2007-2025 (19) | baja | no | TB extrapulmonar: crónica. |
| 820 | Tuberculosis Pulmonar | 2007-2025 (19) | baja | no | TB pulmonar: crónica. |
| 825 | Tuberculosis Farmacorresistente | 2011-2025 (15) | baja | no | TB farmacorresistente. |
| 831 | Varicela Individual | 2007-2025 (19) | media | sí | Varicela: 212/año 2024, 4,1/sem, 46/52 sem [V]; transmisión escolar; casi toda ambulatoria (209 de 212 sin hospitalización) [V]. |
| 850 | VIH / SIDA y la mortalidad por SIDA | 2008-2025 (18) | baja | no | VIH: crónico. |
| 875 | Vigilancia En Salud Pública De La Violencia De Género E Intrafamiliar | 2012-2025 (14) | ALTA | sí | Violencia de género e intrafamiliar: ~24/sem 2026, 38/38 sem [V] (514/año en 2013 [V]); atención urgente (violencia sexual); ligada a fines de semana, quincena y fiestas. |
| 880 | Viruela Símica (Mpox) | 2023-2025 (3) | baja | no | Mpox. |
| 895 | Zika | 2015-2025 (11) | baja | no | Zika: sin transmisión. |
| 995 | Morbilidad por IRA | 2011-2025 (15) | ALTA | sí | IRA colectiva, con denominador. La integra OTRO agente; no se tocó. |
| 998 | Morbilidad por EDA | 2009-2025 (17) | ALTA | sí | EDA colectiva: 31.606 en Manizales en 2012 (microdatos) [V]; ~456/sem en 2026 (tablero) [V]. Análogo gastrointestinal del 995. |

---

## 2. Formato de los archivos de casos individuales

### 2.1 Qué se descargó [V]

Todos los archivos pesan menos de 30 MB (se comprobó el tamaño antes con HEAD) y se bajaron de uno en uno a `xlsx/`. Se leyeron en streaming con `openpyxl` en modo `read_only` (`agregados.py`), sin cargar la hoja entera en memoria.

- Individuales:
  - 452: 2014, 2020, 2021, 2024 y 2025.
  - 356: 2016 y 2024.
  - 345, 831, 348, 620, 414, 412, 360, 330, 800, 220, 370, 420, 455, 320, 100 y 113: todos de 2024.
  - 210 de 2018 (27,6 MB). El de 2019 pesa 80 MB y se descartó.
  - 300 de 2010 (22 MB). **El de 2024 pesa 116 MB y se descartó.**
  - 875 de 2013 (26 MB). El de 2024 pesa 107 MB.
  - 458 de 2008.
- Colectivos:
  - 998 de 2012 (9 MB).
  - 349 de 2024.

Los archivos grandes (300, 875, 210 y 998 recientes) superan los 30 MB. Su volumen de 2022 a 2026 se obtuvo de los tableros (sección 0).

### 2.2 Esquema de los archivos individuales [V]

- **Una hoja `Datos` con 69 columnas, idénticas en nombre y orden en TODOS los archivos individuales revisados de 2008 a 2025** (8 comparados columna a columna y 4 más por número de columnas). **No hay cambios de esquema entre años.**
- **Trampa de formato**: todos los valores vienen como texto con aspecto de fórmula de Excel (`="452"`, `="01"`, `="1         "`). Hay que quitar `="`…`"` y los espacios antes de convertir.
- **Trampa de códigos**: `COD_DPTO_O`/`COD_MUN_O` y `_R` usan 2 y **3** dígitos (Manizales = `17` y `001`), pero **`COD_MUN_N` usa 5 dígitos** (`17001`). Verificado con `Municipio_notificacion = MANIZALES`.

| Concepto | Columna(s) |
|---|---|
| Semana epidemiológica | `SEMANA` (texto `01`..`53`; semana de **notificación**) |
| Año | `ANO` |
| Evento | `COD_EVE`, `Nombre_evento` |
| Ocurrencia/procedencia | `COD_PAIS_O`, `COD_DPTO_O`, `COD_MUN_O`, `Departamento_ocurrencia`, `Municipio_ocurrencia` |
| Residencia | `COD_PAIS_R`, `COD_DPTO_R`, `COD_MUN_R`, `Departamento_residencia`, `Municipio_residencia` |
| Notificación | `COD_DPTO_N`, `COD_MUN_N` (5 dígitos), `Departamento_Notificacion`, `Municipio_notificacion` |
| Edad | `EDAD` + `UNI_MED` (1 = años; 2 = meses; 3 = días; 4 = horas; 5 = minutos **[I]**, según la convención SIVIGILA; los valores observados son 1 a 5) |
| Tipo de caso | `TIP_CAS` (1 sospechoso, 2 probable, 3 confirmado por laboratorio, 4 confirmado por clínica, 5 confirmado por nexo **[I]**; observado: 356, 452 y 300 son todos 4; 210 es 2, 3 o 5; 345 es 1) |
| Otras de interés | `PAC_HOS` (1 sí, 2 no), `CON_FIN` (1 vivo, 2 muerto), `AJUSTE` (0, 3, 4, 5, 6, 7 y D; **excluir 6 = descartado y D = error** **[I]**, según el criterio de los informes de evento del INS), fechas `FEC_NOT`, `INI_SIN`, `FEC_CON`, `FEC_HOS`, `FEC_DEF` |

Lista completa de las 69, en orden: `CONSECUTIVE, COD_EVE, FEC_NOT, SEMANA, ANO, COD_PRE, COD_SUB, EDAD, UNI_MED, SEXO, COD_PAIS_O, COD_DPTO_O, COD_MUN_O, AREA, OCUPACION, TIP_SS, COD_ASE, PER_ETN, GRU_POB, nom_grupo, estrato, GP_DISCAPA, GP_DESPLAZ, GP_MIGRANT, GP_CARCELA, GP_GESTAN, sem_ges, GP_INDIGEN, GP_POBICFB, GP_MAD_COM, GP_DESMOVI, GP_PSIQUIA, GP_VIC_VIO, GP_OTROS, fuente, COD_PAIS_R, COD_DPTO_R, COD_MUN_R, COD_DPTO_N, COD_MUN_N, FEC_CON, INI_SIN, TIP_CAS, PAC_HOS, FEC_HOS, CON_FIN, FEC_DEF, AJUSTE, FECHA_NTO, CBMTE, FEC_ARC_XL, FEC_AJU, FM_FUERZA, FM_UNIDAD, FM_GRADO, confirmados, va_sispro, Estado_final_de_caso, nom_est_f_caso, Nombre_upgd, Pais_ocurrencia, Nombre_evento, Departamento_ocurrencia, Municipio_ocurrencia, Pais_residencia, Departamento_residencia, Municipio_residencia, Departamento_Notificacion, Municipio_notificacion`.

### 2.3 Clasificación sensible y no sensible

Los microdatos **no traen nombre ni documento**, pero sí cuasi-identificadores que, cruzados, reidentifican, sobre todo en eventos raros o estigmatizantes (356, 875, 850).

- **Sensibles (no bajar al repositorio; agregar al leer):**
  - `FECHA_NTO` (fecha de nacimiento: el más peligroso).
  - `EDAD` y `UNI_MED` fuera de bandas.
  - Las fechas exactas `FEC_NOT`, `INI_SIN`, `FEC_CON`, `FEC_HOS`, `FEC_DEF`, `FEC_AJU` y `FEC_ARC_XL`.
  - `SEXO` cruzado con edad y municipio.
  - `OCUPACION`, `PER_ETN`, `GRU_POB`, `nom_grupo` y `estrato`.
  - Todos los `GP_*`: discapacidad, desplazado, migrante, carcelario, gestante, indígena, psiquiátrico, víctima…
  - `sem_ges`, `COD_ASE` (EPS), `TIP_SS` y `AREA`.
  - `FM_FUERZA`, `FM_UNIDAD` y `FM_GRADO` (fuerza pública).
  - `CONSECUTIVE` (identificador de fila).
  - `COD_PRE`, `COD_SUB` y `Nombre_upgd`: identifican a la institución que notifica. No es dato personal, pero junto con evento, semana y edad acota mucho.
- **No sensibles (se pueden usar directamente, siempre en agregado):** `COD_EVE`, `Nombre_evento`, `SEMANA`, `ANO`, los códigos y nombres de país, departamento y municipio, `TIP_CAS`, `PAC_HOS`, `CON_FIN`, `AJUSTE`, `fuente`, `confirmados`, `va_sispro`, `Estado_final_de_caso`, `nom_est_f_caso` y `CBMTE`.
- **Regla práctica**: el lector debe producir de inmediato `(evento, año, semana, municipio, banda de edad 0-4/5-14/15-44/45-64/65+) → conteo` y descartar el resto, como hace `agregados.py`. No guardar el xlsx en el repositorio.

### 2.4 Casos de Manizales por archivo [V]

O = ocurrencia, R = residencia, N = notificado en Manizales. «Sem>0» = semanas del año con al menos un caso por residencia.

| Archivo | Filas nacionales | O | R | N | Sem>0 | Media/sem (R) | Máx/sem |
|---|---|---|---|---|---|---|---|
| 356 de 2024 (intento de suicidio) | 38.769 | 596 | 603 | 690 | 52 | 11,6 | 29 |
| 356 de 2016 | 18.562 | 368 | 365 | 391 | 50 | 7,0 | 16 |
| 370 de 2024 (intoxicación por medicamentos) | 23.078 | 375 | 374 | 432 | 52 | 7,2 | 16 |
| 300 de 2010 (agresiones por animales) | 35.634 | 759 | 765 | 800 | 52 | 14,7 | 24 |
| 875 de 2013 (violencia de género) | 42.808 | 508 | 514 | 535 | 52 | 9,9 | 18 |
| 831 de 2024 (varicela) | 24.919 | 211 | 212 | 236 | 46 | 4,1 | 14 |
| 113 de 2024 (desnutrición aguda) | 24.221 | 81 | 80 | 102 | 40 | 1,5 | 4 |
| 414 de 2024 (sustancias psicoactivas) | 8.447 | 58 | 60 | 62 | 34 | 1,2 | 5 |
| 620 de 2024 (parotiditis) | 5.293 | 53 | 53 | 58 | 30 | 1,0 | 5 |
| 360 de 2024 (plaguicidas) | 6.729 | 38 | 41 | 54 | 26 | 0,8 | 4 |
| 330 de 2024 (hepatitis A) | 4.392 | 30 | 39 | 52 | 24 | 0,75 | 4 |
| 452 de 2024 (pólvora) | 2.212 | 22 | 23 | 24 | 7 | 0,44 | 5 |
| 452 de 2020 | 1.505 | 13 | 13 | 14 | 7 | 0,25 | 3 |
| 452 de 2014 | 1.280 | 15 | 16 | 18 | 7 | 0,31 | 5 |
| 348 de 2024 (IRAG inusitado) | 1.083 | 8 | 8 | 21 | 7 | 0,15 | 2 |
| 412 de 2024 (gases) | 1.103 | 7 | 7 | 7 | 3 | 0,13 | 5 |
| 210 de 2018 (dengue) | 43.652 | 2 | 7 | 9 | 7 | 0,13 | 1 |
| 100, 420, 455, 800 y 220 de 2024 | — | 0 a 6 | 0 a 5 | 2 a 10 | ≤ 5 | ≤ 0,1 | 1 |
| 345 de 2024 (ESI-IRAG centinela) | 8.121 | 0 | 0 | 0 | 0 | 0 | 0 (3 residentes en Caldas) |
| 320 de 2024 (tifoidea) | 71 | 0 | 0 | 0 | 0 | 0 | 0 |
| 349 de 2024 (ETA, brotes) | 636 brotes | 7 brotes y 180 enfermos (procedencia Manizales) | | | 7 | | |

Lectura: solo 356, 370 (y su grupo 365), 300 y 875 dan **52 de 52 semanas no vacías** en casos individuales. 831 está cerca (46). El resto es disperso. **Notificado en Manizales (N) > residentes (R)**, porque Manizales atiende remitidos del departamento. Para el hospital, la N y la O son las que más se parecen a la demanda.

### 2.5 Formato de los colectivos [V]

- **998 de 2012**: dos hojas. `Hoja1` está vacía y `EDA_2012` tiene 163.709 filas con **10 columnas**: `SEMANA, Semana_, ANO, COD_EVE, EVENTO, COD_DPTO_N, COD_MUN_N, DPTO, MUN, CASOS`. Es **por municipio notificador**, sin edad ni servicio. Manizales 2012: **31.606 casos** en 51 semanas (entre 5 y 1.118 por semana). Los 998 recientes (37 a 40 MB) no se bajaron; el tablero 998 de 2026 trae sexo, `PTE_HOS` y `PTE_AMB`.
- **349 de 2024**: hoja `ETA349_2024`, **137 columnas**, una fila por brote. Trae enfermos y expuestos por grupo de edad (`g1..g7`), alimentos, síntomas, `total_enf`, `cod_mun` (4 o 5 dígitos: se pierde el 0 inicial) y `nom_upgd`/`nit_upgd`.
- El formato del 995 lo lleva el otro agente; no se abrió.

### 2.6 Cambios de esquema entre años [V]

Ninguno en los individuales entre 2008 y 2025 (69 columnas, mismo orden). Sí difieren **entre tipos de archivo**: individual (69), colectivo EDA (10) y ETA por brote (137). El número de semanas sí cambia: **2008, 2014, 2020 y 2025 traen `SEMANA = 53`**; 2015 y 2021 no.

---

## 3. Fuentes casi en tiempo real para 2026

| Fuente | URL | Formato | Granularidad | Cobertura | Rezago | Automatización | Estado |
|---|---|---|---|---|---|---|---|
| **Tableros Power BI del INS** (006 Vigilancia Rutinaria y uno por evento) | Ver la sección 0. La lista de tableros está en `portalsivigila.ins.gov.co/_api/web/lists/getbytitle('MenuReporteNivel2')/items` | JSON (API *publish-to-web*) | **Evento × semana × municipio**; 995 por UPGD con denominador | 006: solo 2026. Por evento: 2007/2016/2019/2022 a 2026, según el evento. 995: 2015-2026 sin 2020 | **~7 días**; SE38 parcial a 2026-09-26 | **Probado**: `pbi_rutinaria.py`, `pbi_semanal.py` y `pbi_cobertura.py`. Sin token | **[V] Mejor vía** |
| **BES del INS** (Boletín Epidemiológico Semanal) | `https://www.ins.gov.co/buscador-eventos/BoletinEpidemiologico/{AÑO}_Boletin_epidemiologico_semana_{N}.pdf` (sin cero a la izquierda) | PDF de ~10 MB | Nacional y **departamental** («Tabla de mando»: acumulado, esperado y observado por entidad territorial y evento; Caldas es una fila). La IRA lista solo municipios >100.000 habitantes **con comportamiento inusual** (Manizales no aparece en la SE37) | Semanal, años anteriores con el mismo patrón | **~6 días** (SE37, del 13 al 19 de septiembre, publicado el 25 de septiembre); SE38 da 404 hoy | Descarga directa **probada** (curl, SE37). Extraer tablas: pdfplumber o pdftotext. El texto sale desalineado en las tablas anexas, así que el raspado es frágil | [V] |
| **Informes de evento del INS** | `https://www.ins.gov.co/buscador-eventos/Informesdeevento/{EVENTO}%20PE%20{romano}%20{AÑO}.pdf` (p. ej. `INTENTO%20DE%20SUICIDIO%20PE%20VIII%202026.pdf`) | PDF | Por periodo epidemiológico (4 semanas), acumulado; tasas por municipio solo en el «top» (Manizales 85,1 en 356 PE VIII) | 2026: PE I a PE VIII | ~3 semanas (PE VIII publicado el 7 de septiembre) | Descarga directa probada con HEAD y GET. Nombres irregulares por evento | [V]. Sirve para validar, no para la serie |
| **datos.gov.co** | `4hyg-wa9d` «Datos de Vigilancia en Salud Pública de Colombia» (API Socrata `https://www.datos.gov.co/resource/4hyg-wa9d.json`) | JSON y CSV (SODA) | Evento × semana × municipio de ocurrencia → `conteo` | **2007-2022** | **Congelado**: última actualización 2024-10-17 | API trivial, pero **no aporta 2023-2026** | [V] |
| datos.gov.co, COVID | `gt2j-8ykr` «Casos positivos de COVID-19 en Colombia» | SODA | Caso con municipio y fechas | 2020-2023 | Congelado desde el 2024-01-18 | API | [V] metadatos. Útil para el cráter COVID de 2020 |
| **DTSC Caldas** | `https://saluddecaldas.gov.co/documentos/1027/boletines-ano-2026/` (y `/999/` para 2025) | PDF | «BOLETÍN EPIDEMIOLÓGICO SE n», semanal | 2026: SE1 a SE22 (faltan 13 y 18) | **≥16 semanas**: SE22 (hasta el 6 de junio) subida en bloque el 06/07/2026; nada después | **No automatizable**: cada descarga pasa por **reCAPTCHA v2** (`lFuncion=validar`). Además, curl necesita `--ssl-no-revoke` | [V] índice y captcha. **Contenido no verificado [I]** |
| **Secretaría de Salud de Manizales** | `https://salud.manizales.gov.co/blog/boletines-2025/`; los PDF se listan por la API de WordPress `https://salud.manizales.gov.co/wp-json/wp/v2/media?search=boletin` | PDF mensual (periodo epidemiológico) | Manizales: varicela, **IRA (995) por grupo de edad y servicio**, **EDA (998)**, canales endémicos, vectores. Casi todo en **gráficos**, no en tablas | Ene 2023 a **Oct 2025** (PE 11, subido el 26 de noviembre de 2025) | ~3-4 semanas cuando se publicaba | Descarga directa fácil, pero **no hay boletines en 2026**: ningún PDF subido desde diciembre de 2025 salvo trámites | [V] |
| Portal SIVIGILA «Incidencias» (canales endémicos, mapas) | `portalsivigila.ins.gov.co/sivigila/incidencias/pages/*_general_40.php` (enlazado en el menú) | — | — | — | — | **404** hoy; `sivigilareportes.ins.gov.co` no responde | [V] roto |

**Descarga automática probada**:
1. Power BI, tabla `Rutinaria 2026` (Manizales, 494 filas).
2. Power BI por evento: 356, 300, 831 y 998, con historia.
3. PDF del BES de la SE37.
4. PDF de un informe de evento.
5. PDF del boletín de Manizales de octubre de 2025.

---

## 4. Calendario de semanas epidemiológicas

- **Regla**: semanas de **domingo a sábado**. **[V]** Así lo muestran los calendarios oficiales del INS: `https://portalsivigila.ins.gov.co/Documentos%20compartidos/Calendario%202026.pdf` (y los de 2024 y 2025), con columnas D L M M J V S. Coincide con la nota de Presidencia del 12 de enero de 2026 (52 semanas domingo-sábado en 13 periodos de 4), vista solo en el extracto del buscador.
- **Definición de la SE1** (regla OPS, idéntica a la MMWR de los CDC): **la SE1 termina el primer sábado de enero que deja al menos cuatro días de enero antes de él**. Equivale a: la SE1 es la semana domingo-sábado que contiene el 4 de enero. **[I en cuanto a la cita]**: el texto de la OPS (`www3.paho.org/.../2016-cha-calendario-epidemiologico.pdf`) devolvió 502 hoy y solo se vio en el extracto del buscador. **[V] en cuanto a la aplicación**, porque la regla reproduce exactamente los calendarios del INS:
  - 2026: SE53 de 2025 = del 28 de diciembre de 2025 al 3 de enero de 2026; SE1 de 2026 = del 4 al 10 de enero; SE37 = del 13 al 19 de septiembre (igual que el BES).
  - 2025: SE1 = del 29 de diciembre de 2024 al 4 de enero de 2025.
  - Los microdatos traen `SEMANA = 53` justo en 2008, 2014, 2020 y 2025, y no en 2015 ni en 2021.
- **Años con 53 semanas entre 2007 y 2026: 2008, 2014, 2020 y 2025.** Todos los demás tienen 52. Se calcula con `semanas_epi.py`. El siguiente es 2031 **[I]**, por la misma regla.
- **Cuidado**: el `Calendario` interno de algunos tableros Power BI asigna una «semana 53» a 2021 (2 casos en el tablero 356). No es oficial. Para empalmar, **reasignar la semana con la regla anterior** a partir de la fecha, o usar el `SEMANA` que viene en los datos.

---

## 5. Recomendación

**Advertencia de diseño [I]**. 300, 356, 875 y 365 son **componentes** del propio desenlace: el paciente que llega por intento de suicidio *es* un triage. Usarlos en la misma semana es fuga de información, no predicción. Solo tienen dos usos legítimos:
- como **rezagos** (t−1, t−2, que se tienen gracias al rezago de ~7 días);
- como **desenlaces específicos**, análogos a la serie respiratoria del `NLP/`.

995 y 998 sí son señales de **circulación comunitaria**, más exógenas al hospital.

**Orden de integración después del 995:**

1. **998 EDA.** Microdatos colectivos de 2009 a 2025 por municipio notificador, más el tablero 998 (2019-2026) y la tabla 998 del 006 para 2026. Unos 450 por semana en Manizales. El denominador se puede tomar del `tot_exturg`/`Tot_tot` del 995, que viene de las mismas UPGD **[I]**. Es el análogo gastrointestinal de la hipótesis respiratoria.
2. **356 Intento de suicidio.** 52 de 52 semanas, ~12 por semana, esquema estable. El tablero empalma **exacto** con los microdatos (368 = 368 en 2016).
3. **875 Violencia de género e intrafamiliar.** ~24 por semana y ligada a fines de semana, quincenas y fiestas: puede explicar picos que el calendario no explica. Los microdatos recientes pesan más de 100 MB: leerlos en streaming cuando el otro proceso termine, o tomar 2022-2026 del tablero.
4. **300 Agresiones por animales.** ~29 por semana: es el mayor volumen individual. Microdatos grandes (116 MB en 2024); el tablero cubre 2022-2026.
5. **365 Intoxicaciones.** Suma de 360, 370, 380, 390, 400, 410, 412 y 414 en los microdatos, y el 365 en 2026. ~9 por semana. El 414 (psicoactivas) sirve para la Feria de enero.
6. **831 Varicela, junto con 620 Parotiditis.** Contagio escolar y universitario, ~4-5 por semana, casi siempre ambulatorio. Señal de brote.
7. *(Condicional)* **549 Morbilidad materna extrema**, solo si el triage del hospital incluye obstetricia.
8. **Como marcadores de evento, no como series**: 452 pólvora (diciembre-enero), 349 brotes de ETA (7 brotes al año) y 348 IRAG inusitado. Para el cráter de 2020: COVID de `gt2j-8ykr`.

Descartar para Manizales: 210, 220, 217, 895, 420 y la malaria (sin transmisión local; 0 a 7 casos por año), y 345 (Manizales no es sitio centinela).

**Vía para 2026 (y para el futuro operativo):**
- **Tablero Power BI «006 Vigilancia Rutinaria»**, tabla `Rutinaria 2026`, ya agregada y sin datos de persona. Una descarga semanal automática después del refresco (sábado o domingo).
- Congelar cada descarga con su fecha, porque las 2-3 últimas semanas son provisionales.
- Leer la *resource key* desde `MenuReporteNivel2` y el nombre de la tabla desde `conceptualschema` en cada corrida.
- Para 2016/2019/2022-2025, que faltan o pesan demasiado en los microdatos, usar los tableros por evento, **pidiendo solo la medida agregada `Casos`**.
- Respaldo y validación a nivel Caldas: el PDF del BES (descarga directa, ~6 días).
- DTSC y Secretaría de Manizales **no sirven** como vía automática: captcha en un caso y publicación detenida desde octubre de 2025 en el otro.

### Archivos en `investigacion_vigilancia/`

- `INFORME.md`: este informe.
- `catalogo.py` y `catalogo.md`: la tabla de los 84 eventos.
- `agregados.py`: lector streaming de xlsx que solo produce agregados.
- `cabeceras.py`.
- `semanas_epi.py`: la regla de la semana epidemiológica.
- `pbi_rutinaria.py`: la tabla 006 de 2026.
- `pbi_semanal.py`: medida `Casos` por año y semana de un tablero por evento.
- `pbi_esquema.py`: solo metadatos.
- `pbi_cobertura.py`.
- `powerbi_reports.json`: las claves de los ~40 tableros.
- `menu2.json`.
- `rutinaria_2026_manizales.csv`.
- `xlsx/*_agg.json`: agregados por archivo; los xlsx se pueden borrar.
- `web/`: PDF del BES, de un informe de evento, del boletín de Manizales, calendarios y respuestas del esquema de Power BI.

