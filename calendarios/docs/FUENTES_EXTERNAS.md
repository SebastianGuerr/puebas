# Fuentes externas candidatas (fuera de vigilancia) — informe de investigación (2026-09-28)

> Copia del informe del agente de exploración. [V] = abierto o consultado; [I] = inferido. Es inventario, **no** conclusiones sobre el efecto en el triage. Los datos de prueba (aire IDEAM, movilidad Google, afiliación, GEIH, población DANE) quedaron en el scratchpad de la sesión del 28 y se re-descargan al integrar cada familia. El resumen por variable está en `INVENTARIO.md`.

# Inventario de fuentes externas candidatas — informe de investigación

Fecha: 2026-09-28. Etapa: **inventario, sin conclusiones**. SIVIGILA excluido (lo integra otro agente).

Convenciones: **[V]** = abierto/descargado/consultado en esta sesión (con la cifra obtenida);
**[I]** = inferido de documentación o de búsqueda, no abierto. Código DANE de Manizales: `17001`.
Scripts de prueba: `h.py` (cliente HTTP), `cat.py` (buscador del catálogo de datos.gov.co), en esta misma carpeta.

Nota técnica: en esta red `requests` funcionó **sin** `truststore` (no está instalado en el `.venv`) contra
datos.gov.co.

---

## 3. Seguridad y violencia

### 3.1 MinDefensa — delitos por municipio y día (datos.gov.co) [V]

Seis datasets con el mismo esquema: `fecha_hecho` (día), `cod_depto`, `departamento`, `cod_muni`,
`municipio`, (a veces `zona`, `sexo`, `arma_medio`), `cantidad`. Agregados, **sin datos personales**.
Entidad: Ministerio de Defensa Nacional. Cobertura 2003-01-01 → 2026-08-31 (consultado 2026-09-28;
actualización 2026-09-16 → **rezago ~2-6 semanas**, publicación mensual).
API Socrata: `https://www.datos.gov.co/resource/<id>.json?$where=cod_muni='17001'`.

| id | Delito | Filas Manizales | Suma `cantidad` 2003-2026 | Por año (2018→2026 parcial) |
|---|---|---|---|---|
| `jr6v-i33g` | Lesiones personales | 11.503 | 25.791 | 1319, 1288, 890, 870, 690, 711, 549, 501, 369 |
| `m8fd-ahd9` | Homicidio | 2.420 | 2.422 | 77, 55, 48, 49, 33, 36, 27, 37, 29 |
| `gepp-dxcs` | Violencia intrafamiliar | 6.632 | 10.251 | 395, 688, 570, 551, 505, 683, 760, 475, 463 |
| `4rxi-8m8d` | Hurto a personas | 7.821 | 34.296 | 1741, 1802, 1062, 1085, 1023, 978, 911, 673, 445 |
| `ntej-qq7v` | Lesiones en accidente de tránsito | 14.684 | 19.966 | 563, 279, 550, 862, 1013, 1168, 1118, 1206, 803 |
| `uav5-b85g` | Homicidio en accidente de tránsito | 915 | 915 | 43, 32, 25, 31, 45, 33, 36, 31, 10 (hasta 2026-07) |

Calidad observada (sin interpretar): `ntej-qq7v` tiene un escalón (279 en 2019 → 1.013 en 2022), que
huele a cambio de registro; `jr6v-i33g` cae ~62 % entre 2018 y 2025. Días con al menos un caso de
lesiones personales: 257-349 por año — la serie diaria es rala para Manizales; semana es más estable.

### 3.2 Policía Nacional — "Reporte ..." (datos.gov.co) [V: esquema]

`72sg-cybi` (lesiones personales y en accidente de tránsito), `vuyt-mqpw` (violencia intrafamiliar),
`ha6j-pa2r` (homicidios en accidente de tránsito), `fpe5-yrmw` (delitos sexuales). Mismo contenido que
3.1 pero con `armas_medios`, `genero`, `grupo_etario`, `descripci_n_conducta`, y `fecha_hecho` como
**texto**. Actualizado 2026-09-01. Agregado, sin datos personales. Es probablemente la fuente primaria
de 3.1; 3.1 es más cómodo (fecha tipada).

### 3.3 Medicina Legal (INMLCF) — lesiones de causa externa [V: esquema]

- `79dd-d24f` Lesiones no fatales de causa externa, **preliminar ene-2025 → jul-2026** (actualizado 2026-09-21).
- `2kpj-cktv` Lesiones fatales, preliminar ene-2025 → jul-2026.
- `6cjn-eevd` Lesiones accidentales 2015-2024 definitivas; `ezhf-hscf` Lesiones por transporte
  2015-2024; `ers2-kerr` Violencia intrafamiliar 2015-2024; `e3xi-4zq5` Violencia interpersonal
  2015-2024; `vtub-3de2` Presuntos homicidios 2015-2024.
- Granularidad: **una fila por víctima**, con `a_o_del_hecho`, `mes_del_hecho`, `dia_del_hecho`
  (ver abajo), rango de 3 horas, municipio. **Sin nombres ni documento**, pero con cuasi-identificadores
  (edad, sexo, etnia, orientación sexual, escolaridad, municipio). Usar solo agregado; no guardar filas.
- Rezago: definitivas ~9 meses tras cierre de año; preliminares ~2 meses.

- [V] `dia_del_hecho` es **día de la semana** (lunes…domingo), no del mes; con `mes_del_hecho` y año, la
  granularidad temporal efectiva es **mes** (+ día de la semana). Mayúsculas inconsistentes
  ("domingo"/"Domingo") entre años.
- [V] Filas de Manizales (`codigo_dane_municipio='17001'`): no fatales preliminar `79dd-d24f` 2025: 1.643,
  2026 (ene-jul): 884. Violencia interpersonal `e3xi-4zq5`: 2015-2024 = 1228, 1260, 1027, 950, 933,
  **248 (2020)**, 456, 762, 838, 694. Lesiones por transporte `ezhf-hscf`: 828, 803, 685, 645, 679, 168,
  444, 658, 677, 578. Lesiones accidentales `6cjn-eevd`: 8-56 por año.

---

## 2. Catástrofes y emergencias

### 2.1 UNGRD — Consolidado de emergencias (datos.gov.co) [V]

Tres datasets por tramos, mismo contenido (fecha, municipio, evento, afectados, ayudas). Agregados por
evento, sin datos personales.

| id | Nombre | Cobertura | Filas totales | Filas Manizales | Eventos Manizales |
|---|---|---|---|---|---|
| `wwkg-r6te` | "Emergencias UNGRD." (atribuido a Alcaldía de Saravena, pero es nacional) | 2019-01-01 → 2022-12-31 | 25.857 | 67 (2019: 39, 2020: 6, 2021: 7, 2022: 15) | movimiento en masa 24, incendio estructural 23, colapso estructural 7, accidente terrestre 3, vendaval 2 … |
| `rgre-6ak4` | Emergencias UNGRD 2023-2024 | 2023-01-01 → 2024-12-31 | 16.036 | 9 | incendio estructural 4, incendio forestal 2, sismo 1, tormenta eléctrica 1, movimiento en masa 1 |
| `2343-nuqp` | Emergencias UNGRD V2 | 2025-01-01 → 2025-12-31 | 13.012 | 4 | movimiento en masa 2, incendio estructural 2 |

Lectura de calidad: 80 eventos en 2019-2025 para Manizales, muy desigual por año (39 en 2019, 4 en 2025).
Es un registro de **eventos reportados a la UNGRD para solicitar apoyo**, no un censo de emergencias
locales. 2026 no está publicado aún en datos.gov.co (rezago ≥ 9 meses).

### 2.2 Sismos

- **SGC, catálogo operativo** — https://sismo.sgc.gov.co/ [V parcial]. Formulario Django (desde 2018-01-01,
  límite del campo de fecha). Detrás hay un endpoint **no documentado** `POST /ajax/query` (JSON con
  `starttime`, `endtime`, `min_mag`, `departament`, `bounds`…, más token CSRF) que devuelve JSON con
  `time_UTC`, `time_local`, `latitude`, `longitude`, `depth`, `mag`, `type_mag`, `description`, `status`.
  Probado 2026-09-28: responde, pero **los filtros no se comportan como se espera** (con
  `departament=Caldas` devolvió 24 sismos de todo el país, M ≥ 3,7, ene-mar 2025; con rectángulo devolvió
  "sin registros"; con municipio, error). Automatizable solo como raspado frágil.
- **SGC, catálogo histórico CATS** — https://catalogosismico.sgc.gov.co/visor/ , REST
  `https://catalogosismico.sgc.gov.co/rest_cats/parametrosCapaRR` [V]: 16.290 eventos, M 3,5-8,45,
  **fecha máxima 2020-12-30**. No cubre 2021-2026. Descartable para este fin.
- **SGC FDSN** `http://sismo.sgc.gov.co:8080/fdsnws/event/1/` [V]: responde "Service Version 1.2.1" pero
  **404 en todas las consultas de eventos** (no expone el servicio `event`).
- **USGS FDSN** (alternativa) — `https://earthquake.usgs.gov/fdsnws/event/1/query` [V]. Radio 150 km de
  Manizales, M ≥ 2,5, 2020-01-01 → 2026-09-28: **67 eventos**. API estable (CSV/GeoJSON), rezago de
  minutos, sin datos personales. Menos sensible que la red nacional. Es el camino automatizable más limpio
  para "sismo potencialmente sentido".

### 2.3 Volcán Nevado del Ruiz (SGC)

- Boletines semanales en PDF, con fecha en el nombre, p. ej.
  `https://www2.sgc.gov.co/Noticias/boletinesDocumentos/Boletin_semanal_de_actividad_del_volcan_Nevado_del_Ruiz_del_14_de_abril_al_20_de_abril_de_2026.pdf`
  [I: visto en buscador]. Índice:
  https://www2.sgc.gov.co/sgc/volcanes/VolcanNevadoRuiz/Paginas/boletines-volcan-nevado-del-ruiz.aspx [I].
- **No se encontró un histórico descargable de niveles de alerta** (tabla fecha → nivel). Los cambios son
  pocos y están en comunicados: amarillo→naranja 2023-03-30, naranja→amarillo 2023-06-27 (89 días) [I:
  comunicados SGC/UNGRD en buscador]. Propuesta: calendario manual de cambios de nivel, cada fila con la URL
  del comunicado; si se quiere intensidad semanal, raspar los PDF (el formato cambia con los años).

---

## 5. Ambiente

### 5.1 Pronóstico archivado — Open-Meteo [V]

Coordenadas 5,07 N, −75,51 O (elevación de la celda devuelta: 2.087 m).

- **Historical Forecast API** `https://historical-forecast-api.open-meteo.com/v1/forecast` [V]: datos
  diarios desde **2017-01-01** (2016 vacío). Es la concatenación del primer tramo de cada corrida
  (≈ pronóstico a 0-1 días), no pronóstico a varios días. Admite modelo: `ecmwf_ifs025`, `gfs_seamless`,
  `icon_seamless` dan lluvias distintas para 2024-06-01 (12,3 / 4,6 / 0,6 mm).
- **Previous Runs API** `https://previous-runs-api.open-meteo.com/v1/forecast` [V] — la variable
  pronosticada con 1, 2, 3… días de antelación (`*_previous_dayN`). Cobertura medida mes a mes (horaria):
  - `temperature_2m_previous_day1`: desde **~2021-03-23** (GFS); hueco en dic-2023/ene-2024.
  - `precipitation_previous_day1..3`: **solo desde ~2024-01-19**.
  - ECMWF e ICON: solo desde 2024.
  O sea: lluvia pronosticada con antelación real solo ~2,7 años. Gratis sin clave (uso no comercial),
  rezago 0, sin datos personales.

### 5.2 ENSO — NOAA ONI [V]

`https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt` — trimestres móviles 1950 → **JJA 2026**
(anomalía +1,80). Texto plano, descarga directa. Rezago ~1 mes. Alternativa matriz año × mes:
`https://psl.noaa.gov/data/correlation/oni.data` [V]. Sin datos personales.

### 5.3 Calidad del aire — IDEAM / SISAIRE en datos.gov.co `g4t8-zkc3` [V]

Columnas: estación, contaminante (`msfl_code`), concentración, fecha inicio/fin, duración (min), municipio.
Actualizado 2026-02-20. Las agregaciones con `$group` superan el tiempo de espera de la API; se bajaron
las filas de Manizales paginando (99.464 filas, 5,2 MB → `aire_manizales_ideam.csv`). Resultado:

| Estación | Contaminante | Resolución | Desde | Hasta | Registros/año |
|---|---|---|---|---|---|
| GOBERNACIÓN | PM10 | diaria | 2020-01-02 | 2024-10-30 | 80-117 |
| GOBERNACIÓN | PM2.5 | diaria | 2020-01-29 | 2023-11-19 | 79-120 |
| GOBERNACIÓN | PM2.5 | horaria | 2024-01-11 | 2024-11-22 | 5.267 h |
| GOBERNACIÓN | CO, O3, SO2 | horaria | 2021-03-01 | 2024-11-22 | 4.800-8.000 h |
| LICEO ISABEL LA CATÓLICA | PM10 diaria / PM2.5 horaria | | 2020 / 2023 | 2024-12-23 | ~100 / ~6.000 h |
| MILÁN, LA NUBIA, PALOGRANDE, CATÓLICA (UCM) | PM10 | diaria | 2020-2021 | 2024-12 | 67-110 |

Lectura de calidad: PM10 diario tiene ~100 días/año por estación, patrón de muestreador manual de
**1 día de cada 3**; no es serie diaria continua. **Nada publicado después de dic-2024** (rezago ≥ 21
meses a hoy). Sin datos personales.

- `kekd-7v7h` promedio anual (no sirve para día). `yspz-pxxn` Chinchiná PM10/PM2.5 [I: solo catálogo].
- **CDIAC (U. Nacional sede Manizales + Corpocaldas)** — https://cdiac.manizales.unal.edu.co/ ; consulta
  `.../indicadores/public/searchAirMenu` [I]. Red SVCA de Manizales con registros cada 5 min → horarios
  para PM10, PM2.5, O3, SO2, CO; boletines PDF semestrales/anuales 2019-2025 (p. ej.
  `.../publicaciones/Boletin_CA_Manizales_2025_vFinal.pdf`). **Bloqueado por el filtro FortiGuard de esta
  red** ("Malicious Websites", HTTP 403): no se pudo verificar desde aquí. Es la fuente más completa para
  Manizales (el IDEAM no tiene nada después de 2024). Probar desde otra red o pedir los datos.

---

## 1. Sistema de salud

### 1.1 BDUA — afiliados por EPS y municipio (ADRES, datos.gov.co) [V]

- `tq4m-hmg2` contributivo (631.009 filas), `d7a5-cnra` subsidiado (1.333.445 filas). Columnas: sexo,
  grupo de edad, EPS, régimen, tipo de afiliado, estado, zona, departamento, municipio, nivel Sisbén,
  `cantidad`. Agregado, sin datos personales.
- **Es una foto del mes vigente, no una serie**: no hay columna de periodo. Actualizado 2026-09-07.
  Manizales hoy, contributivo: SURA 136.456; Salud Total 90.493; Sanitas 47.418; Nueva EPS 45.984
  (+4.803 "-CM"); Famisanar 1.414. Subsidiado: Salud Total 33.224; Nueva EPS 29.395 (+10.295 "-CM");
  SURA-CM 23.353; Sanitas 11.554; Famisanar-CM 3.663.
- Serie histórica: guardar la foto cada mes desde ahora, o buscar otra fuente (ver 1.3).
- `hn4i-593p` "Número de afiliados por departamento, municipio y régimen" (MinSalud, actualizado 2022-06) [I].

### 1.2 REPS — prestadores y sedes (MinSalud) [V]

- datos.gov.co `c36g-9fc2`: 76.821 sedes, **foto con corte 2026-03-12**, sin fecha de alta/baja y **sin
  servicios** (solo sedes). Manizales: 221 sedes de IPS, 922 de profesionales independientes, 4 de
  transporte especial, 21 de objeto social diferente.
- **Trae datos personales** en las filas de profesionales independientes (nombre, cédula, teléfono,
  correo, dirección). No se guardaron.
- Portal REPS https://prestadores.minsalud.gov.co/habilitacion/ [I]: consulta pública por prestador con
  sus servicios; tiene módulo de **novedades** (apertura/cierre de servicios). La norma (Res. 3100/2019 y
  anteriores) obliga a avisar el cierre de urgencias, UCI, hospitalización, pediatría o gineco-obstetricia a
  la entidad departamental con 15 días de antelación [I: buscador]. **No se encontró descarga pública del
  histórico de novedades con fecha.** Ver "acciones del propietario".

### 1.3 MinSalud — "Cifras de afiliación en salud" (mensual, EPS × municipio) [V]

- Página: https://www.minsalud.gov.co/Proteccion-Social/Paginas/cifras-aseguramiento-salud.aspx
- Zips mensuales enlazados (jul-2025 → **ago-2026**), p. ej.
  `https://www.minsalud.gov.co/sites/rid/Lists/BibliotecaDigital/RIDE/VP/RBC/cifras-afiliacion-salud-agosto2026.zip`
  (1,3 MB). Descargado y abierto: hojas `CoberturaDepartamento`, `CoberturaMunicipio`, **`EPSMunicipio`**
  (EPS × municipio × régimen), `EPS`, `Caracterización01-05` (edad, sexo, estado, por departamento).
  Manizales ago-2026: 451.100 afiliados (contributivo 327.857, subsidiado 111.773, excepción 11.470),
  población DANE 476.260, cobertura 94,7 %. SURA en Manizales: 136.623 contributivo + 23.401 subsidiado.
- Histórico: la página enlaza un "Histórico de Cifras" y un tablero Tableau público
  (`https://public.tableau.com/app/profile/minsaludcol/viz/CifrasAseguramientoenSalud_16166927767750/Aseguramiento`)
  que según el manual cubre **desde dic-2016** [I: no abierto]. Los zips anteriores a jul-2025 no están
  enlazados en la página actual.
- Rezago: ~1 mes. Agregado, sin datos personales. Automatizable: descarga del zip mensual (nombres de archivo
  irregulares: `agosto2026`, `abr-2026`, `cifra-...-enero-2026`), hay que raspar la página para los enlaces.

### 1.4 Supersalud — entidades en medida especial [V]

Página: https://www.supersalud.gov.co/es-co/transparencia-y-acceso-a-la-informacion-publica/informacion-especifica-para-grupos-de-interes/entidades-en-medida-especial-liquidacion-y-traslados-de-eps

Excel descargados (actualización 31-ago-2026):
- `CTFT21-Listado-...-para-administrar-EPS.xlsx`: 7 EPS con toma de posesión / intervención (Asmet,
  Capresoca, Coosalud, Emssanar, Famisanar, **Nueva EPS** — Res. 2024160000003012-6 del 3-abr-2024, vence
  10-abr-2027 —, S.O.S.). Columnas: entidad, ciudad, NIT, clase de medida, **resolución (con fecha en
  texto)**, fecha final de la medida.
- `CTFT21-programa-de-recuperacion.xlsx`: 2 en vigilancia especial.
- `M4-FT-16-...-IPS.xlsx`: 25 IPS intervenidas; **ninguna de Caldas**.
- `M4-FT-18 entidades-en-intervencion.xlsx`: liquidación; incluye nombre del liquidador (funcionario).
- **Solo medidas vigentes, no histórico**: Sanitas (intervenida 2-abr-2024 por Res.
  2024160000003002-6, según prensa) ya no aparece. El histórico hay que reconstruirlo de las resoluciones
  en `https://docs.supersalud.gov.co/PortalWeb/Juridica/Resoluciones/` [I] y de comunicados.
- Hitos con fecha encontrados en prensa/comunicados [I]: Sanitas intervenida 2024-04-02 (prórroga
  2025-04-02); Nueva EPS 2024-04-03 (prórroga Res. 2026100000003814-6 del 2026-04-10).

### 1.5 Alertas hospitalarias (DTSC / Alcaldía) — solo prensa [I]

No se encontró un registro estructurado. Hay comunicados fechados en:
- DTSC: https://saluddecaldas.gov.co/ (p. ej. "Caldas en alerta amarilla hospitalaria ante fenómeno de
  frente frío", `/publicaciones/5378/...`).
- Gobernación: https://caldas.gov.co/index.php/prensa/noticias (p. ej. `3472-la-territorial-de-salud-mantiene-la-alerta-verde-hospitalaria-en-manizales-y-en-villamaria`, `5541-...alerta-verde-hospitalaria...ceniza-volcanica`).
- Alcaldía: https://centrodeinformacion.manizales.gov.co/ (p. ej. "Sigue alerta hospitalaria ante crisis
  del sistema de salud … deudas de la Nueva EPS", 2026).
- Prensa: alerta roja en Manizales en ene-2022 por ocupación UCI de 87 % y cierre de 30 camas del
  Hospital Santa Sofía (RCN Radio / Noticias RCN).

Propuesta de construcción: raspar los listados de noticias de esos tres sitios (título + fecha + URL),
filtrar por "alerta" y "hospitalaria", y escribir a mano la tabla `inicio, fin, color, alcance, motivo,
url`. El nivel se declara por acto administrativo (marco: Decreto 0642/2019 citado por la Alcaldía [I]),
así que una **solicitud formal a la DTSC** daría la lista completa.

Ocupación UCI: el tablero nacional de ocupación UCI de la pandemia (MinSalud/INS) no se localizó como
serie descargable en esta sesión [I]. La DTSC lo reportaba en boletines 2020-2022.

---

## 0. Herramienta transversal: archivo de noticias de la Alcaldía por API (WordPress) [V]

`https://centrodeinformacion.manizales.gov.co/wp-json/wp/v2/posts?search=<texto>&per_page=100&_fields=date,link,title`
— **8.746 publicaciones desde 2020-01-01** hasta hoy, con fecha y URL, sin clave. También
`https://manizales.gov.co/wp-json/wp/v2/posts` (3.426 desde 2024-01-01). Coincidencias medidas:
"alerta hospitalaria" 23 (2021-12-23 → 2026-08-06), "cierre de servicios" 99, "Nueva EPS" 114, "ley seca" 9
(2023-11 → 2026-06), "deslizamiento" 145, "ceniza" 29, "ocupación hospitalaria" 6, "manifestación" 76.
Ejemplos de títulos con fecha: 2025-07-25 "Secretaría de Salud de Manizales advierte sobre alta ocupación
hospitalaria…"; 2025-08-22 "Cierre de servicios en la clínica Avidanti pone en riesgo la salud de 110.000
usuarios de Nueva EPS…"; 2026-03-26 "Alerta por cierre de servicios a usuarios de Nueva EPS…";
2026-04-15 "Sigue alerta hospitalaria…".
La búsqueda es de texto completo (ruidosa: "paro" casa 645 por subcadena). Sirve para **construir
calendarios de eventos con fecha y fuente** (alertas, cierres, ley seca, emergencias, eventos masivos),
no como serie en sí. La Patria no expone la API (404). Sin datos personales en título/fecha (el cuerpo
puede nombrar funcionarios).

---

## 4. Eventos sociales y masivos

### 4.1 Once Caldas — partidos (ESPN, API pública no documentada) [V]

`https://site.api.espn.com/apis/site/v2/sports/soccer/col.1/teams/2919/schedule?season=AAAA`
Partidos de liga con fecha-hora (UTC), local/visitante, estadio y **asistencia** (`attendance`, p. ej.
25.000, 26.732, 12.000 en 2024). Partidos de local en Palogrande por temporada: 2019: 20, 2020: 12,
2021: 19, 2023: 20, 2025: 23, 2026 (a la fecha): 16. Copa Colombia (`col.copa`, 6 en 2025) y Sudamericana
(`conmebol.sudamericana`, 13 en 2025) por el mismo esquema. Rezago: horas. Sin datos personales.
Cuidado: la hora está en UTC (un partido a las 20:00 de Colombia cae al día siguiente en UTC). Al ser API
no documentada puede cambiar; alternativas [I]: BeSoccer, ceroacero, worldfootball (raspado).

### 4.2 Paros y manifestaciones — ACLED vía HDX [V]

`https://data.humdata.org/dataset/colombia-acled-conflict-data` (API CKAN `package_show`), recurso
"colombia_HRP_demonstration_events_by_month-year" (XLSX 4,9 MB): **eventos de protesta por municipio y
mes**, 2018-01 → 2026-09 (actualizado 2026-09-25). Manizales (`CO17001`) por año: 2018: 11, 2019: 11,
2020: 24, 2021: 38 (mayo 16, junio 8 — Paro Nacional), 2022: 23, 2023: 24, 2024: 33, 2025: 23, 2026: 18.
Agregado, sin datos personales. **Por día y con descripción del evento** solo con cuenta ACLED (ver
acciones del propietario).

### 4.3 Elecciones y ley seca [I]

Fechas de jornada (Registraduría, https://www.registraduria.gov.co/): 2022-03-13 (Congreso y consultas),
2022-05-29 y 2022-06-19 (Presidencia), 2023-10-29 (autoridades locales), 2026-03-08 (Congreso),
2026-05-31 y 2026-06-21 (Presidencia) [I: de memoria, verificar contra la Registraduría]. La ley seca se
decreta por jornada (normalmente desde las 18:00 del sábado hasta las 06:00 del lunes) [I]; la Alcaldía
publica cada decreto (9 publicaciones "ley seca" en el archivo, sección 0) [V]. También hay ley seca local
en fechas no electorales (p. ej. partidos, 7 de agosto: "Autoridades de Manizales decretan medidas de
seguridad para el 7 de agosto", 2026-08-06) [V]. Calendario manual de pocas filas.

### 4.4 Calendario escolar oficial (Secretaría de Educación de Manizales) [V: existen los PDF]

Resoluciones anuales en PDF: 2025 `https://manizales.gov.co/wp-content/uploads/2025/01/RESOLUCION-No.-0065-DEL-28-DE-ENERO-DE-2025-1-1-1.pdf` (2,3 MB) y 2026
`https://manizales.gov.co/wp-content/uploads/2025/10/2025.10.29_Res_No_0992_Establece_Calendario_Academico_2026-1.pdf` (1,7 MB). Calendario A: 40
semanas lectivas, 12 de receso estudiantil [I: nota de prensa]. Años 2020-2024: buscar en el archivo de
noticias (sección 0) [I]. Manual: ~6 fechas por año. El repo ya tiene "vacaciones escolares" en
`calendario_Colombia.csv`; comparar contra estas resoluciones.

### 4.5 Calendarios universitarios [I]

- U. de Caldas: https://viceacademica.ucaldas.edu.co/calendario-academico-pregrado/ (acuerdo PDF por año,
  p. ej. `.../wp-content/uploads/2025/02/Calendario-Academico-Pregrado-2025.pdf`; 2025: clases desde
  27-ene y 11-ago).
- U. Nacional sede Manizales: https://registroymatricula.manizales.unal.edu.co/ ; los semestres se han
  corrido por paros (2024-2 terminó en mar-2025; 2025-2 va hasta 2026, según La Patria).
- U. de Manizales: https://umanizales.edu.co/calendario-academico/calendario-academico-para-pregrados-2025
- Autónoma y Católica: no buscadas.
Todo PDF/HTML, manual; ~4 fechas por universidad y semestre. Los paros universitarios mueven las fechas y
no quedan en el calendario original: hace falta la modificación posterior.

### 4.6 Agenda cultural y eventos masivos [I]

Instituto de Cultura y Turismo y Promotora de Eventos publican en
`https://manizales.gov.co/category/instituto-de-cultura-y-turismo-manizales/` y
`.../category/promotora-de-eventos-y-turismo/` (WordPress: consultable por API por categoría). Feria de
Manizales 2025: 3-12 ene (68.ª edición) [I: prensa]. No hay registro con aforo. El repo ya tiene
`eventos_manizales_2020_2026.csv` (99 filas manuales).

---

## 6. Movilidad, economía y población

### 6.1 Google COVID-19 Community Mobility Reports [V]

Zip de 98 MB (`https://www.gstatic.com/covid19/mobility/Region_Mobility_Report_CSVs.zip`, congelado
2022-10-18). **No se bajó entero**: se leyeron por rango HTTP solo los tres CSV de Colombia (2,4 MB
transferidos; `rangezip.py`). Manizales (`sub_region_2`): **974 días, 2020-02-15 → 2022-10-15**, seis
categorías completas salvo 8 días en transporte. Guardado `google_mobility_caldas.csv` (municipios de
Caldas + total departamental). Agregado. Serie cerrada.

### 6.2 Aerocivil — tráfico origen-destino (datos.gov.co `gb6w-ynu4`) [V]

Mensual por empresa, origen, destino; `pasajeros`, `carga_correo_kg`. Cobertura 2020 → **2026-06**
(actualizado 2026-08-06 → rezago ~2 meses). Pasajeros con origen o destino Manizales: 2020: 67.912
(10 meses con dato), 2021: 117.274, 2022: 144.465, 2023: 103.895, 2024: 77.103, 2025: 66.674,
2026 (6 meses): 27.275. Sin datos personales.

### 6.3 Supertransporte — pasajeros desde terminales (datos.gov.co `eh75-8ah6`) [V]

Diario (con hora de despacho) por terminal, origen y destino. "T.T. DE MANIZALES": 2021: 1.772.547
pasajeros (365 días), 2022: 2.504.220 (365), 2023: 2.627.261 (365), **2024: 1 día**, 2025: 2.375.370 (343
días), 2026 hasta 2026-04-06. 2020: 1 día. Hay fechas corruptas (máximo "6202-04-13"). Rezago ~5 meses.
Sin datos personales.

### 6.4 Población — DANE, proyecciones municipales post-COVID [V]

`https://www.dane.gov.co/files/censo2018/proyecciones-de-poblacion/Municipal/PPED-AreaMun-2018-2042_VP.xlsx`
(3,9 MB, modificado 2025-08-08; hoja `PobMunicipalxÁrea`, año × área). Manizales total: 2018: 434.403,
2019: 440.570, 2020: 447.015, 2021: 453.659, 2022: 458.752, 2023: 462.721, 2024: 467.681,
2025: 472.087, **2026: 475.690**. Anual; hay versión por sexo y edad simple en el mismo sitio [I].
Versión anterior: `DCD-area-proypoblacion-Mun-2020-2035-ActPostCOVID-19.xlsx` (2023) [V: existe].
Rezago: proyección (se conoce de antemano; se revisa tras cada censo/actualización). Sin datos personales.
Nota: la cobertura de afiliación de MinSalud (1.3) usa 476.260 para 2026: otra versión de proyección.

### 6.5 Desempleo — DANE GEIH, Manizales A.M. [V]

`https://www.dane.gov.co/files/operaciones/GEIH/anex-GEIH-jul2026.xlsx` (3,7 MB), hoja
`Total 23 ciudades A.M. Trim`, bloque "Manizales A.M.": **trimestre móvil desde ene-mar 2007 hasta
may-jul 2026** (233 trimestres): TGP, TO, TD, subocupación, población. Tasa de desocupación: 15,98 %
(ene-mar 2007) … 8,23 / 8,08 / 8,33 % (últimos tres trimestres móviles). Rezago ~1 mes tras el cierre del
trimestre. El nombre del archivo cambia cada mes (`anex-GEIH-<mes><año>.xlsx`), se raspa de
https://www.dane.gov.co/index.php/estadisticas-por-tema/mercado-laboral/empleo-y-desempleo. Agregado.

### 6.6 IPC por ciudad — DANE [V]

`https://www.dane.gov.co/files/operaciones/IPC/ago2026/anex-IPC-CiudadesMensuales-ago2026.xlsx` (59 KB):
variación mensual del IPC por ciudad, con bloques por año; Manizales presente (10 filas/años). También
`anex-IPC-Indices-…`, `anex-IPC-CiudadesAnuales-…`. Mensual, rezago ~1 semana tras el mes. Enlaces en
https://www.dane.gov.co/index.php/estadisticas-por-tema/precios-y-costos/indice-de-precios-al-consumidor-ipc/ipc-informacion-tecnica .

### 6.7 Combustibles [I]

Precio de referencia de gasolina y ACPM por ciudad: CREG,
https://creg.gov.co/publicaciones/15565/precios-de-combustibles-liquidos/ (la página no expone archivos en
el HTML; publicación mensual, desde 2023 los cambios son mensuales). Precio por estación: SICOM
(MinEnergía) [I]. En datos.gov.co solo aparece GNV (`he3q-86dn`). Prensa: Manizales ene-2026 gasolina
$16.466/galón, ACPM $11.349 [I]. Variable nacional con diferencias fijas entre ciudades: serie manual
mensual de ~80 filas.

### 6.8 Turismo [I]

Sin fuente diaria. Proxies ya verificados: pasajeros aéreos mensuales (6.2) y terminal de buses diaria
(6.3). MinCIT/CITUR publica ocupación hotelera por departamento (mensual) [I: no abierto].

---

## 7. Orden recomendado de integración

Criterio: calidad medida, historia desde ≤ 2020, facilidad (API estable) y rezago. **No** se opina
sobre el efecto en el triage.

1. **Delitos MinDefensa por día y municipio** (`jr6v-i33g`, `gepp-dxcs`, `4rxi-8m8d`, `m8fd-ahd9`,
   `ntej-qq7v`, `uav5-b85g`): API Socrata, diario, 2003 → hace 4 semanas. Revisar escalones antes de usar.
2. **NOAA ONI**: un archivo de texto; reemplaza el ENSO manual.
3. **Open-Meteo Previous Runs / Historical Forecast**: API, sin clave. Temperatura pronosticada desde
   2021-03, lluvia pronosticada solo desde 2024-01.
4. **Once Caldas (ESPN API)**: fechas, hora y asistencia 2019-2026; volumen pequeño.
5. **Población DANE (anual) y GEIH Manizales A.M. (trimestre móvil)**: dos Excel; controles lentos de
   tendencia.
6. **Cifras de afiliación MinSalud** (EPS × municipio, mensual) + **Supersalud medidas especiales**:
   serie mensual desde jul-2025 enlazada; el histórico previo depende del "Histórico de cifras"/Tableau.
7. **Calendario de eventos de sistema de salud** (alertas hospitalarias, cierres de servicios, intervención
   de EPS) construido con la API WordPress de la Alcaldía (2020 →) + resoluciones Supersalud.
8. **UNGRD** (3 datasets, 80 eventos Manizales 2019-2025) y **USGS sismos**: calendario de pocos eventos.
9. **ACLED protestas** (mensual, HDX) y **Supertransporte terminal** (diario 2021-2023 y 2025; 2024 vacío).
10. **IDEAM calidad del aire** (1 de cada 3 días, termina 2024-12): baja prioridad salvo que CDIAC
    complete.
11. **Google Mobility** (cerrado 2020-02 → 2022-10) y **Aerocivil** (mensual): contexto COVID / tendencia.
12. **Medicina Legal**: solo mes + día de la semana, y rezago de 9 meses en definitivas.
13. Manuales de pocas filas: ley seca/elecciones, calendario escolar oficial, calendarios universitarios,
    niveles del Ruiz, IPC y combustibles.

## 8. Requiere acción del propietario

1. **CDIAC (U. Nacional Manizales / Corpocaldas)**: el filtro FortiGuard de la red institucional bloquea
   `cdiac.manizales.unal.edu.co` como "Malicious Websites". Opciones: (a) pedir a TI la reclasificación
   del sitio; (b) descargar desde otra red (equipo de casa); (c) solicitud por correo al GTAIHA / Corpocaldas
   de las series horarias de PM10 y PM2.5 2020-2026 de las estaciones de Manizales.
2. **ACLED**: registrarse en https://acleddata.com (cuenta institucional, uso académico) para obtener
   clave de API y bajar los eventos de protesta **por día** con descripción. Sin cuenta solo hay el
   agregado mensual de HDX.
3. **DTSC — derecho de petición** (Ley 1755 de 2015) a la Dirección Territorial de Salud de Caldas
   pidiendo: (a) la lista de actos administrativos de declaratoria y levantamiento de alertas hospitalarias
   (verde/amarilla/naranja/roja) para Manizales y Caldas 2020-2026, con fecha de inicio, fin, color y motivo;
   (b) el registro de novedades REPS de **cierre, apertura o reducción de servicios de urgencias,
   hospitalización y UCI** de prestadores de Manizales 2020-2026, con fecha; (c) si existe, la serie de
   ocupación de camas UCI/hospitalización de Manizales. Todo agregado por institución, sin pacientes.
4. **MinSalud — "Histórico de cifras de afiliación"**: los zips anteriores a jul-2025 no están enlazados;
   si el tablero Tableau no permite exportar, solicitar a MinSalud (Oficina de Aseguramiento) la serie
   mensual EPS × municipio para Manizales dic-2016 → jun-2025.
5. **Supersalud**: el listado solo tiene medidas vigentes. Para el histórico (medidas levantadas, p. ej.
   Sanitas 2024-2026), petición a la Superintendencia o reconstrucción manual desde resoluciones.
6. **Decidir** si se acepta usar APIs no documentadas (ESPN, SGC `ajax/query`) congelando cada descarga en
   `salidas/`, o si se prefiere solo fuentes oficiales documentadas.
7. **Guardar desde ya la foto mensual de BDUA** (`tq4m-hmg2`, `d7a5-cnra`): no hay histórico en
   datos.gov.co y cada mes que pasa se pierde.
8. Para 2020-2024 del calendario escolar y de ley seca: aceptar que son calendarios **manuales** con
   URL por fila (no hay fuente estructurada).

## 9. Archivos en esta carpeta

`h.py`, `cat.py`, `aire.py`, `rangezip.py` (scripts de prueba); `aire_manizales_ideam.csv` (99.464 filas,
agregado por estación); `google_mobility_caldas.csv`; `cifras_afiliacion_ago2026.zip`;
`anex-GEIH-jul2026.xlsx`; `PPED-AreaMun-2018-2042_VP.xlsx`. Ninguno contiene datos personales.

