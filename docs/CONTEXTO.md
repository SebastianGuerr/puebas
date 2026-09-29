# Contexto — la bitácora de decisiones

**Este archivo solo crece.** Nada se borra. Una decisión que se revierte se marca como
revertida y se añade la nueva entrada debajo, con el motivo del cambio. El historial de por
qué se cambió de idea vale tanto como la idea: es lo único que evita volver a discutir lo
mismo dentro de tres meses.

Regla 9 de `CLAUDE.md`. Cada entrada lleva **fecha, qué se decidió, por qué y con qué
evidencia**. El «por qué» es el campo que importa: lo que se puede reconstruir leyendo el
código no hace falta guardarlo aquí; lo que no, se pierde al cerrar la sesión.

Para saber **dónde está todo ahora mismo**, este archivo no sirve — es historia. Eso está en
`docs/HANDOFF.md`.

---

## 2026-09-29 — Exploración de la base para el perfil del hospital: primeros resultados

Se siguió el protocolo:
- esquema primero;
- **las columnas sensibles de 14 tablas añadidas a `extraccion/__init__.py` antes de consultar
  nada**;
- solo agregados por año. Las casillas con menos de 5 casos van a «otros».

**Ningún texto libre salió.** Los scripts de exploración están en el scratchpad
(`esquema_perfil.py`, `cobertura_perfil.py`, `repartos_perfil.py`) y todavía no se versionan.

**Cómo se enlaza:**
- triage → `DIM_INGRESO` (`ADNINGRESO`);
- ingreso → `DIM_FOLIO` → `CONTROL_DIAGNOSTICO` (`HCPDIAPRIN` = principal) → `DIM_DIAGNOSTICO` (CIE-10);
- ingreso → `AREA_SERVICIO` (con marca de urgencias).
- **Cobertura: el 98-99 % de los ingresos tiene diagnóstico principal CIE-10.** Es el diagnóstico
  estructurado que `GENDIAGNO1` no traía.

**1. Qué fracción del triage se atiende en el SES** (triage con ingreso):
- ~50 % en 2020-2023, **35 % en 2024, 30 % en 2025 y 34 % en 2026**.
- Por nivel: I 87 %, II 94 %, IIIU 93 %, III-G 64 %, **III 30 %, IV 14 %, V 0,1 %**. El nivel es,
  en la práctica, la decisión de tomar o redirigir.
- **Por edad: 65+ 55 %, 45-64 43 %, 15-44 39 %, 5-14 15 %, 0-4 13 %.** Confirma lo dicho por el
  superior: los niños se estabilizan y se remiten.

**2. Dónde se atiende:**
- Urgencias: 122.136 ingresos, 2020-2026.
- **Unidad obstétrica: 27.841, y creciendo** (2.349 en 2020, 5.554 en 2024, 4.851 en 2026 a
  septiembre).
- Recién nacidos: 596.

**3. Qué tienen** (diagnóstico principal del primer folio, primera letra CIE-10, 2020-2026):

| Grupo | Ingresos |
|---|---|
| R, síntomas (dolor abdominal R10: 15.171) | 25.459 |
| **S, traumatismos** | **22.128** |
| O, obstetricia | 21.840 |
| N, genitourinario | 13.157 |
| **J, respiratorio** (EPOC exacerbado J44, rinofaringitis J00) | **11.523** |
| M, osteomuscular | 11.037 |
| G, neurológico (cefalea, migraña) | 10.767 |
| I, circulatorio | 10.120 |
| K, digestivo | 8.713 |
| **A, infecciosas (diarrea A09: 4.944)** | 5.917 |
| U07, COVID | 4.601 |

- **Llega mucho trauma (S, el segundo grupo), pero no por SOAT.** Son contusiones de dedos,
  rodilla y cabeza: caídas y golpes, no accidentes de tránsito.
- **Aviso para la tesis.** Hay series con **mecanismo externo conocido**, codificadas desde 2020,
  **sin NLP**: respiratorio (J), diarrea (A09), trauma (S) y obstetricia (O). Son los «desenlaces
  específicos» que el `CLAUDE.md` pedía al NLP, **pero solo del subconjunto que se ingresa**.

**Advertencia:** los nombres de los códigos de 3 caracteres salieron de `MIN(DIANOMBRE)`, que es el
nombre de una subcategoría y no de la categoría. Por ejemplo, N39 salió como «incontinencia»
cuando N39.0 es infección urinaria, y R07 como «dolor de garganta» cuando R07 es sobre todo dolor
torácico. **Hay que rotularlos con la categoría CIE-10 oficial.**

**4. Causa de ingreso** (`AINCAUING`, códigos sin catálogo en la base). Descifrados en parte cruzando
con el asegurador:
- **código 6 = accidente de tránsito** (74 % SOAT);
- **código 10 = accidente laboral** (74 % ARL);
- **código 3 = enfermedad general** (casi todo);
- el **código 9** tiene 34.197 casos de todos los aseguradores y no se sabe qué es;
- 4, 2, 1 y 8 tampoco se saben.
- **Hace falta el diccionario de la base** (pregunta al superior).

**5. Remisiones** (`SEGUIMIENTO_REMISIONES_DW`, 2023-2026, ~1.200-1.600 por año). `MOTIVO` resultó
ser un catálogo de 6 valores (≤ 36 caracteres). `MotivoRemision` es texto libre de ~550 caracteres
y **no se consulta**.

| Motivo | Remisiones |
|---|---|
| **No disponibilidad de la especialidad** | 1.913 |
| **No convenio con la EPS** | 1.209 |
| No disponibilidad de camas | 453 |
| No habilitación (sube: 0 → 111) | 152 |
| Menor complejidad | 103 |
| No disponibilidad de equipos | 71 |

El 60 % de las remisiones sale de Urgencias (2.975). Coincide con el superior: se recibe todo y se
remite por especialidad y por convenio con la EPS.

**Pendiente de decidir con el propietario:**
- **qué granularidad se persiste**. Un diagnóstico por día con cifras pequeñas es información de
  salud: se propone capítulo CIE-10 por día, capítulo × banda de edad por semana y código de 3
  caracteres solo mensual con supresión < 5;
- **si se versiona**, porque el repositorio está en GitHub. La propuesta es **no** versionarlo
  mientras no lo autorice.

---

## 2026-09-29 — Qué hospital es el SES, según el superior del propietario; se abre la exploración de la base

**Contexto institucional** (el superior, vía el propietario). Responde la decisión #13 en su parte
cualitativa:
- **El SES recibe de todo.** Una urgencia se atiende por razones legales y morales. Otra cosa es
  que pueda **resolverla** allí.
- **Donde faltan especialistas, se recibe, se estabiliza y se remite.**
  - **Niños:** no hay especialistas pediátricos. La urgencia infantil se estabiliza y se envía al
    Hospital Infantil, que no tiene urgencias propias de puerta.
  - **Cardiovascular:** se remite a una clínica cardiovascular de Manizales. El propietario cree
    que es Avidanti, sin confirmar.
- **Accidentes de tránsito:** no hay un destino fijo; la ambulancia va al hospital más cercano.
  - Hipótesis del propietario: el SES está en una zona de avenidas bien señalizadas, con pocos
    accidentes cerca, y por eso le llegan pocos.
  - Sin SOAT, el paciente no llega por esa vía, sino por su EPS a donde haya convenio.
- **Remitir no es no atender**: «es mejor remitirlo que tratarlo con limitaciones».

**Cómo cambia la lectura de lo ya medido:**
- El **SOAT bajo** del SES (4 %) y su falta de relación con el tránsito de la ciudad (r = 0,01) son
  **geografía y logística de ambulancias**, no falta de demanda.
- La **estacionalidad pediátrica** del SES mide a los niños que **pasan por aquí para ser
  estabilizados**, no a toda la demanda infantil.
- El **51 % «no urgente»** (cuaderno 02) y el «60 % que se remite a la EPS» son la puerta de un
  hospital que **recibe todo y resuelve según su capacidad**.

**Decisión:** explorar la base para el perfil del hospital (cuaderno 10) **con el protocolo de la
regla 1, y con cautela reforzada por petición expresa del propietario**:
1. Solo esquema.
2. Clasificar cada columna nueva y añadir las sensibles a `extraccion/__init__.py` **antes** de
   consultar nada.
3. Solo conteos agregados de columnas codificadas.

**Ningún texto libre sale de la base**, ni siquiera como «valores más frecuentes». El precedente
del 28-09 fue que un agente imprimió valores de una columna con forma de cédula.

---

## 2026-09-29 — Cuaderno 09: el entorno conectado consigo mismo

Archivo: `notebooks/09_el_entorno.ipynb`, 21 celdas, sin errores. **Ningún dato del hospital.**
25 contextos por semana, y análisis conjunto en 2022-2025, unas 209 semanas.

**Datos nuevos integrados:**
- **ENSO:** `calendarios/clima/enso.py` → `calendarios/enso_oni.csv` (ONI de la NOAA, 1950-2026).
  Un episodio abierto al final de la serie se marca «en curso»: **El Niño de 2026, ONI +1,80 en
  junio-agosto**.
- **Recesos escolares oficiales:** `calendarios/calendario_escolar_manizales.csv`, 2021-2026, cada
  uno con su resolución y su URL. Sustituye las 122 fechas fijas del calendario.

**Hallazgos:**
1. **El calendario mueve la violencia de la ciudad** (Policía, Poisson, 2015-2026 sin cuarentenas).
   - Lesiones personales: domingo ×1,78, festivo ×1,32, **noche festiva ×1,96**.
   - Homicidios: domingo ×2,11 y noche festiva ×2,02.
   - **La violencia intrafamiliar tiene otro calendario:** quincena ×1,20 y receso escolar ×0,83.
   - El tránsito baja en festivo (×0,72).
2. **Cadenas con rezago** (anomalías sin estacionalidad):
   - **Temperatura media → IRA ciudad: r = −0,37 a 4 semanas.** Frío → más IRA.
   - Temperatura mínima: −0,31 a 1 semana.
   - Humedad: +0,31 a 5 semanas.
   - Lluvia: +0,23 a 5 semanas.
   - **Receso escolar → IRA −0,20 y varicela −0,18 en la misma semana.**
   - **ENSO → temperatura +0,49.** El Niño calienta Manizales.
   - Al revés de lo esperado: **lluvia → EDA −0,19**.
   - La ceniza no se puede medir: solo 4 episodios.
   - **Es la cadena clima → contagio → consulta que describía el propietario**, vista en la ciudad
     sin el hospital. Las barras en *k < 0* indican que parte es persistencia compartida: no es
     prueba de causa.
3. **Estados del entorno** (k-medias):
   - **Con calendario, 5 estados:** calma (45 % de las semanas; febrero-mayo y
     septiembre-noviembre), seco y cálido (julio-septiembre, El Niño), fiestas de los pueblos,
     temporada decembrina (100 % de diciembre) y Feria.
   - **Sin calendario, 3:** frío y húmedo (marzo-junio y octubre-diciembre), intermedio, y seco y
     cálido (julio-septiembre).
   - La IRA no define ningún estado. **El estado visible es el gatillo** (frío y húmedo), que
     precede a la IRA.
   - Siluetas bajas (0,13-0,17): son regiones de un continuo, no cajas.
4. **La «suma de factores» puesta en fechas:**
   - **marzo a mayo** junta colegios abiertos, frío y humedad, y lluvias. Es donde el cuaderno 08
     vio las semanas altas sostenidas;
   - **diciembre** junta receso, fiestas y violencia. Son los picos puntuales de noche.

**Trampas documentadas:**
- **La IRA como porcentaje sube en receso por el denominador** (cae la consulta programada). Para
  el contagio se usa el conteo.
- **La ceniza, la pólvora y el alumbrado parecen relacionados solo porque caen en el mismo
  diciembre** (2023).

**Sección 6 hecha el mismo día.** Revisión de literatura en `calendarios/docs/LITERATURA_ENTORNO.md`:
11 relaciones y 86 referencias verificadas, escrita **antes** de comparar.
- **Casi todo lo esperado aparece en la dirección publicada:** lluvia y humedad → IRA a ~1 mes,
  frío → IRA, cierre de colegios → menos transmisión, El Niño → calor, fin de semana y fiesta →
  violencia, pólvora en diciembre-enero. Eso da confianza en que las series externas miden lo que
  dicen.
- **No coincide:** la lluvia no sube los siniestros viales. La literatura avisa que el efecto es
  por hora y que el dato diario lo diluye.
- **Aportes posibles de la tesis, sin estudio publicado:**
  - quincena → violencia intrafamiliar ×1,20;
  - **la interacción frío × virus × población mayor.**
- **Vacíos de datos:** la ceniza (hace falta el PM10 del CDIAC, #10a), el tránsito por hora y la
  transición seco → lluvioso sobre la EDA.

**Decisión: el siguiente paso es enfrentar los estados y sus interacciones contra el hospital**,
preregistradas antes de mirar. La primera es la del propietario: frío anómalo × IRA circulando ×
mayores de 65.

---

## 2026-09-29 — Primero el entorno entre sí, después el hospital; el perfil del hospital espera

**Decisión del propietario.** Antes de volver a enfrentar nada contra el triage, se **conectan
los contextos externos entre sí**:
- clima, calendario (fines de semana, festivos, vacaciones);
- fiestas y eventos;
- vigilancia en salud;
- violencia y lesiones;
- volcán, ENSO y desastres.

**Qué se busca:**
- qué se mueve junto y con qué rezago;
- qué caracteriza la **«calma»** o flujo normal;
- qué **estados del entorno** se repiten, por ejemplo «temporada respiratoria activa»,
  «temporada festiva» o «calma».

Cada relación observada se **contrasta con la investigación publicada**. Ejemplo del
propietario: estudios de cómo la ceniza volcánica afecta la calidad del aire y la salud
respiratoria. **Solo después** se enfrentan esos estados, y sus **interacciones**, contra el
hospital.

**Por qué.** Enfrentar cada factor por separado contra el triage no ve **la suma de factores**. El
ejemplo del propietario: población frágil, más frío, más virus circulando da un riesgo mayor que
cada uno solo. Para medir esa interacción, primero hay que saber cuándo coinciden los factores
en el entorno.

**Diseño:**
1. **Revisión de literatura primero**, por un agente. Relaciones esperadas entre contextos, con
   dirección, tamaño y rezago publicados. Así lo esperado queda escrito antes de mirar lo
   observado, que es el espíritu del preregistro.
2. **Cuaderno 09, «El entorno».** Solo datos externos, ningún dato del hospital:
   - perfiles estacionales compartidos;
   - correlaciones cruzadas con rezago entre anomalías;
   - efecto del calendario sobre las otras series externas;
   - **estados del entorno** por agrupamiento de semanas;
   - comparación de lo observado con lo publicado.
3. **Datos que faltan y se integran para esto:** el índice ENSO (ONI de la NOAA) y el calendario
   oficial de vacaciones escolares, con las fechas de las resoluciones.

**El perfil del hospital (cuaderno 09 propuesto el mismo día) queda EN ESPERA.** El propietario
va a hablar con su superior para conseguir documentación e información de base antes de
construirlo desde cero. Pasa a ser el cuaderno 10. Ya se identificaron en el esquema, sin bajar
datos, tres tablas candidatas:
- `DIM_INGRESO`: causa de ingreso, servicio, cama;
- `CONTROL_DIAGNOSTICO` → `DIM_DIAGNOSTICO`: CIE-10;
- `SEGUIMIENTO_REMISIONES_DW`: remisiones. **Trae cédula, nombres y texto clínico: solo
  agregados.**

---

## 2026-09-29 — Cuaderno 08: los picos tienen tres relojes, y se corrige lo dicho sobre la mitad de año

Archivo: `notebooks/08_los_picos.ipynb`, 21 celdas, sin errores. Las pruebas son las
preregistradas el mismo día.

**1. Revierte el «matiz» de la entrada «Los cuadernos cuentan la historia completa»**, que decía
que el alto de mitad de año cae en mayo, antes de las vacaciones, y que junio-julio bajan.
**Era un artefacto del control.** Ese cálculo descontaba las «vacaciones escolares» del
calendario, que son 122 fechas fijas cada año.
- **Sin ese descuento** (control con día de la semana, festivo y año), **las semanas de
  vacaciones escolares oficiales están por encima del nivel del año los cinco años**: +3,5 a
  +9,3 %, media **+6,5 %**. Marzo-mayo está en +4,3 %.
- **El propietario tenía razón:** la mitad del año es la parte alta, de marzo a julio.
- Lección: un control que incluye la variable que se quiere estudiar la hace desaparecer.

**2. Las noches festivas**, frente a los demás domingos y festivos:
- **La ciudad es violenta esas noches.** Las lesiones personales de la Policía suben +161 % en
  velitas, +120 % el 8 de diciembre, +54 % el 25 y **+201 % el 1 de enero**.
- **En el SES el día completo baja**: −24 % en velitas, −35 % el 24, −40 % el 31.
- **Pero la madrugada sube**: +44 % la del 8 de diciembre, +31 % la del 31 y +35 % la del 1 de
  enero.
- **El 31 llegan +74 % de particulares.**
- La pólvora es el 80 % de sus casos anuales en diciembre-enero (SIVIGILA 452: 1,3 por semana),
  pero pesa poco en el conteo.

**3. El pico llega el día después.** En las 4 temporadas limpias: **3 de enero +14,0 %**, 2 de
enero y 26 de diciembre +6,7 %, 4 de enero +5,6 %.
- Del 2 al 4 de enero se juntan el día siguiente a Año Nuevo, el regreso de vacaciones, la Feria
  y el Carnaval de Riosucio.
- **Corrección dentro del mismo cuaderno:** la temporada 2021-22, dentro de la ventana COVID que
  el modelo no ajusta, fabricaba un pico de +11 a +17 % el 8-10 de diciembre. Sin ella, el 8 de
  diciembre queda en +2,7 %.

**4. Fiestas de los pueblos** (107 fiestas realizadas con fecha):
- Durante la fiesta y los 3 días siguientes, el total sube **+1,9 % [+0,5; +3,4] con las lejanas
  (≥ 60 km)** y +0,2 % con las cercanas. En 15-44 años, +2,1 % con las lejanas.
- **La huella del asegurador no acompaña:** particulares −7,5 %; IPS remitente −6 %, −10 % con
  las cercanas.
- Son 18 pruebas. El patrón «lejos > cerca» encaja con la hipótesis de remisión, pero el efecto
  es pequeño. **La prueba directa es la serie del CRUE** (#12).

**5. Para el modelo, decidido aquí:**
- **El indicador de festivo se parte en dos**: la noche de fiesta, que baja de día y sube de
  madrugada, y el día siguiente, que sube.
- **Las vacaciones escolares se toman con las fechas oficiales de cada año**, no con las fijas
  del calendario.
- **Las fiestas de los pueblos entran separadas por distancia**, con peso bajo.
- **Conviene un modelo por hora, o al menos día y madrugada por separado.**

---

## 2026-09-29 — El pluviómetro de La Nubia reporta cero cuando llueve: el clima vuelve a fabricar sequías

**Hallazgo**, del agente del cuaderno 03 y verificado aquí sobre `calendarios/clima_unificado.csv.gz`:

| Mes | Pluviómetro (mm, días con dato) | NASA POWER (mm) |
|---|---|---|
| 2025-02 | 1,2 (7) | 202,8 |
| 2025-10 | 4,2 (31) | 202,6 |
| 2026-01 | 8,8 (30) | 240,3 |
| 2026-02 | 1,6 (28) | 200,4 |
| **2026-03 a 2026-06** | **0,0 cada mes, con dato los 30-31 días** | 103-159 |

**El pluviómetro no está ausente: reporta cero todos los días.** Como `precip_con_estacion` lo da
por medido y el consenso toma el pluviómetro de referencia, **marzo-junio de 2026 aparecen como
los meses más secos de la serie**, cuando la fuente satelital dice que llovió lo normal. Es el
mismo tipo de defecto que el arreglo del 23-09 corrigió en otra dirección: allí la falta de dato
fabricaba tormentas; aquí un **dato falso** fabrica sequías. El propietario sospechaba que el clima
tenía cálculos mal hechos, y en esto tenía razón.

**Además:** en 2021 no hay ninguna medida de lluvia en tierra (0 días con pluviómetro). Todo ese
año es reanálisis, y sale como el más seco del consenso (664 mm).

**Qué queda en duda:**
- las variables de lluvia de octubre de 2025 a junio de 2026;
- **los episodios «seco → lluvioso» del cuaderno 07 de ese periodo**, porque un falso seco
  seguido de la vuelta del pluviómetro fabrica una «ruptura»;
- las variables de lluvia del periodo de prueba del cuaderno 05.

El +22 % de los 0-4 años tras un paso de seco a lluvioso **se vuelve a medir con el clima arreglado
antes de citarlo**.

**Decisión:** `clima_unificado.py` debe detectar la falla y tratarla como ausencia de pluviómetro.
El criterio es el cero sostenido de la estación mientras el satélite registra lluvia, a escala
de mes y no de día: un día seco aislado es real. La corrección y su evidencia van en
`calendarios/docs/CLIMA.md`.

**Hecho el mismo día.** `pluviometro_fallido()` usa 31 días centrados: pluviómetro < 10 % de NASA
y NASA ≥ 60 mm.
- **Por qué el 10 %:** en los 34 meses sanos la razón va de 0,27 a 1,42; en los fallidos es
  < 0,04.
- Marca 199 días y se aplica **antes** de calcular los factores de escala.
- La lluvia anual queda en 1.297 mm y los días con pluviómetro válido bajan al 34,7 %.

**Resultados que cambian:**
- **Seco → lluvioso, 0-4 años: de +22,0 ± 17,8 % (13 episodios) a +13,4 ± 15,0 % (17
  episodios).** La forma es la misma, pero **ya no se distingue de cero**.
- Lluvia fuerte y madrugada: de −7,8 % a −4,3 %, no significativo.
- En el cuaderno 06, la lluvia en quintiles pasa de −3,6 a −2,5 puntos.

**No cambian:** Feria, eventos sociales, Nueva EPS, enfriamiento y calentamiento, picos y el mapa
de correlaciones (las mismas 15 casillas marcadas).

**Cuadernos:**
- 06 y 07 re-ejecutados, con recuadros «clima corregido».
- 01, 02, 03 y 05 en manos de un agente.

**Lección, la segunda sobre el mismo archivo:** una fuente que **reporta** también puede estar
rota. La completitud no mide la verdad del dato. Toda referencia en tierra se contrasta con una
fuente independiente mes a mes antes de usarla.

---

## 2026-09-29 — Los cuadernos cuentan la historia completa, y los picos pasan al centro

**Decisión del propietario: los cuadernos 01 a 07 se corrigen para contar todo el camino.**
Cada uno debe mostrar:
- las premisas, los datos y las figuras;
- las fuentes de donde sale cada dato;
- la lectura y sus límites;
- **y lo que se supo después**.

**Cómo se corrige** (criterio fijado aquí): una afirmación que resultó falsa **no se borra en
silencio**. Queda visible con un recuadro «Corrección del 2026-09-29» que dice qué cambió y por
qué, igual que este archivo, que solo crece. El valor del recorrido está en poder ver por qué se
cambió de idea.

**Correcciones de fondo ya identificadas:**
1. **El 01 dice que la caída del 23,9 % es «en parte artefacto» del cambio de criterio de
   triage.** Es un error de razonamiento: reetiquetar un triage de IV a III **no cambia el
   conteo**. La caída del volumen es de **Nueva EPS** (cuaderno 07: 115,8 → 72,2 triages por día
   entre 2025 y 2026). La reclasificación es un fenómeno aparte, de la institución.
2. **El 01 dice «no hay huecos de registro».** El 19 y el 20 de marzo de 2024 no tienen filas,
   y el 21 tiene 40.
3. **El 01 y el 02 presentan la gripa y los niños como la hipótesis del proyecto.** Era un
   ejemplo (aclaración del 28-09).
4. **El 02 remite a un «cuaderno 03» de control de calendario que no existe.**
5. **El `05_validacion_sin_motivo.py` no es un cuaderno.** Se convierte, y su conclusión («las
   externas no mejoran el pronóstico») se matiza con el 07.

**Estructura nueva:**
- **03, nuevo**: las fuentes externas, con de dónde sale cada una, su cobertura y sus escalones.
  Hoy esa información solo está en `calendarios/docs/`.
- **08, nuevo**: los picos.
- **`notebooks/README.md`**: el hilo que une los cuadernos. El 04 (ciclo horario con Fourier)
  sigue pendiente.

**Los picos pasan al centro. Hipótesis del propietario**, que se preregistran antes de medir en
el 08:
- **Diciembre**: alcohol, riñas, fiesta, **pólvora**, quemados por velitas (7 de diciembre) y por
  el muñeco del 31. Es festivo y peligroso.
- **Año Nuevo y enero**: además de la Feria, **las fiestas de los pueblos cercanos**. Lo que el
  hospital del pueblo no puede atender termina en Manizales.
- **Mitad de año**: el propietario ve **más picos a mitad de año que a final**, lo que hay que
  medir.
- El contexto debe salir de **fuentes oficiales del gobierno de Caldas y de Manizales**.

**Lo que se deja:** accidentes de tránsito y lluvia como vía de los picos. Ya se midió que al SES
llega poco tránsito (r = 0,01 con la ciudad, salva la Feria) y que la lluvia no lo sube. El
propietario considera que seguir por ahí es sobrepensar.

**Medido el mismo día: hay dos tipos de pico** (descriptivo, residuo contra el calendario y el
nivel del año, 2022-03 a 2026-09; `scratchpad/picos_por_mes.py`, que pasará al cuaderno 08):
1. **Días puntuales**: más de 1,5 desviaciones sobre el nivel local.
   - **Enero 14,5 y diciembre 12,1 por cada 100 días**; el resto de meses, 1-6,5.
   - Ejemplos: 25 de diciembre de 2022; 1 y 8 de diciembre de 2024 (la noche de velitas); 26-27 de
     diciembre de 2025; 2-5 de enero de 2025; 3-4 de enero de 2026.
   - **El nivel medio de esos meses es bajo** (−2,6 % y −2,9 %). Son noches, no temporadas.
2. **Semanas altas sostenidas**: más de +8,4 % sobre el nivel del año.
   - **Mayo 45 %** de sus semanas, marzo-abril 23-25 %, **octubre-noviembre 0 %**.
   - Mayo tiene el nivel medio más alto del año (+8,1 %).

**Lectura.** El propietario ve más picos a mitad de año, y es cierto **si «pico» es una semana alta
sostenida**. Si es un día puntual, dominan diciembre y enero. Parecen dos mecanismos distintos:
lo festivo y rápido en diciembre-enero, y algo lento y sostenido en marzo-mayo.

**Matiz.** El alto de mitad de año cae en **mayo, antes de las vacaciones escolares**; junio y
julio, ya en vacaciones, bajan al 14 %. La variable preregistrada `mitad_de_anio` (semanas de
vacaciones) apunta a la ventana equivocada. **No se redefine**: se deja escrito y se añade como
exploratoria la ventana marzo-mayo, declarando que se miró después.

### Mismo día: el contexto oficial de los picos

Informe completo en `calendarios/docs/CONTEXTO_PICOS.md`.

**1. Calendario de fiestas municipales:** `calendarios/fiestas_caldas_2020_2026.csv`.
- **Primera versión incompleta**: 75 filas de 22 municipios, de las que 48 citan la fuente como
  texto y no como URL. Hay otro agente completándolo.
- Lo que ya se ve: **en enero solo está el Carnaval de Riosucio** (años impares).
- **El grueso de las fiestas cae entre finales de junio y comienzos de julio**, y en
  octubre-noviembre.
- Es decir, **no coinciden con los meses de más picos** (enero puntual, mayo sostenido). Hay que
  medirlo, no suponerlo.

**2. Pólvora (DTSC, Gobernación, Alcaldía).**
- En Caldas, de 24 a 47 quemados por temporada; en Manizales, de 8 a 16.
- **Son uno o dos triages por día pico, frente a ~177 de media.** La pólvora es parte de la
  noche festiva, pero no la explica sola.
- En la serie de MinDefensa, las **lesiones personales se multiplican por 2 a 5 el 1-ene y el
  25-dic**. Diciembre es el mes más alto (71,6 al mes) y junio el más bajo (48,0).

**3. Hechos de la red de salud que afectan al conteo.** Son causas de **oferta**, no de demanda.
- **28-feb-2024: el SES deja de atender en urgencias a Salud Total y Sanitas.** En los datos:
  172 y 194 triages en febrero y marzo de 2024, 120 en abril. Es un corte real, pero de solo
  4-6 triages por día.
- **Marzo de 2025: el SES al 200 %** («todos los pacientes del departamento llegan al SES»).
- **Julio de 2025: alerta hospitalaria en Manizales**, con urgencias al 200 % en días punta; en
  abril de 2026 seguía vigente por Nueva EPS.
- **La saturación puede recortar el conteo en los días de más demanda.** Si el servicio está
  lleno, se desvía o no se registra. **El conteo mide lo que el hospital recibe, no lo que la
  ciudad necesita.** Hay que tenerlo presente al interpretar cualquier pico.

**4. Remisiones.** La DTSC publica **119 informes mensuales del CRUE** («Referencia y
contrarreferencia Caldas», 2015-01 a 2026-08), pero cada descarga pide un reCAPTCHA. **Solo los
puede bajar el propietario a mano.** Además hay un derecho de petición propuesto en
`CONTEXTO_PICOS.md` §4.3.

**5. Vacaciones escolares de mitad de año**, por resolución de la Secretaría de Educación de
Manizales, 2021-2026. Ejemplo: 2025, del 16-jun al 6-jul.

**6. Calendario de fiestas completado**: `calendarios/fiestas_caldas_2020_2026.csv`.
- **177 ediciones de 26 municipios**, 167 con URL. Hay 119 fechas confirmadas y 58 estimadas;
  130 filas verificadas abriendo la página (V), 8 vistas solo en el buscador (B) y 39 inferidas
  (I).
- Valores de `estado` válidos: realizado, cancelado, virtual, programado y aplazado.
- **Las fiestas realizadas empiezan en octubre (39), junio (33) y agosto (20); en enero, 2.**
  Octubre y noviembre son justo los meses **sin** semanas altas de triage (0 %).
- No hay fiestas de San Pedro y San Pablo como fiesta principal. El puente de finales de junio lo
  ocupan otras fiestas (Colación, Ceiba, Samán y Horticultura).
- El terremoto del 10-ago-2026 canceló o aplazó varias.

### Mismo día: cuadernos 01 y 02 corregidos, y tres correcciones a `CLAUDE.md`

**Cuadernos.** El 01 tiene 38 celdas y el 02, 36; corren sin errores. Llevan 22 y 24 recuadros
«Corrección del 2026-09-29».
- **El markdown de los dos estaba roto**: sin saltos de línea y con las tablas en una sola línea.
  Se rehízo.

**Hallazgos nuevos:**
- **Caída del volumen de 2024 a 2026:** el total pierde 54,2 triages por día y Nueva EPS 53,4.
  **Pero de 2024 a 2025 la caída es sobre todo del resto** (−17,4; Sura baja de 69,6 a 53,9 tras
  su salto de abril de 2024). De 2025 a 2026 es de Nueva EPS (−43,6), mientras el resto sube 16,6.
- **La reclasificación del nivel y la cuota de Nueva EPS** van en sentido contrario de enero a
  octubre de 2025 (r = −0,80), así que la deriva de criterio es independiente. Desde noviembre
  de 2025 van juntas (r = +0,63). Queda como hipótesis; comprobarla exige un agregado nuevo día ×
  nivel × entidad.
- **Composición por edad de 2024 a 2026:** los 15-44 bajan de 122,1 a 88,1 por día y los 0-4 no
  suben (6,8 a 6,9). Los extremos ganan peso porque cae el centro, no porque vengan más niños.

**Cifras antiguas corregidas:**
- Emergencias: 1.591 casos, no 1.463.
- Obstétrico: 12,5 %.
- Triages por mes, octubre-diciembre de 2025: 6.434 → 5.165 → 4.581.
- Estancia, régimen 2: 324.046 registros.
- Clima del 02 (anterior al arreglo): temperatura media 16,6 °C; lluvia ~1.081 mm por año con
  máximo en marzo. **El «rezago de un mes» entre lluvia y pico pediátrico deja de sostenerse.**

**Corregido en `CLAUDE.md`, verificado aquí contra `triage_horario`, 2022-2026:**
1. **La segunda joroba del día es a las 14-15 h, no a las 18-19 h.** Pico a las 10 h (15,8
   triages por hora), valle a las 12-13 h (10,9), segundo pico a las 14-15 h (13,0); a las 18-19 h
   ya se baja a 8,6.
2. **Los «2 huecos» se nombran:** 19 y 20 de marzo de 2024, y el 21 con 40 triages.
3. **«Por qué cae no se sabe»** queda tachado y resuelto: es Nueva EPS.

**Hueco de reproducibilidad sin arreglar:** `python -m extraccion --series` **no** regenera
`triage_diario.parquet` ni `triage_horario.parquet`. Ningún script del repositorio los produce.
Sí se comprobó que el horario coincide casilla a casilla con `triage_nivel` sumado (0 diferencias
en 55.833 casillas).

---

## 2026-09-28 — Dos capas: el nivel lo mueve la red, los picos los mueven otras cosas

**Contexto que aporta el propietario**, con el respaldo de su superior y de las noticias:
- **Nueva EPS fue intervenida por corrupción y quedó al borde de la quiebra.** No puede pagar
  los tratamientos.
- **Sus afiliados dejaron de venir** porque saben que no los van a atender.
- Es lo que el cuaderno 07 vio en los datos del hospital: de 116 a 72 triages por día de Nueva EPS
  entre 2025 y 2026, con escalones en noviembre de 2025 y julio de 2026.

**Decisión de diseño.** El desenlace se separa en dos capas con causas distintas:
1. **El nivel**, lo que el hospital recibe «en una semana normal». Lo mueve la **red de salud**:
   la situación de la EPS dominante, los cierres y las intervenciones. Cambia en escalones y
   dura meses.
2. **Los picos**, lo que se sale del nivel reciente. Los mueven eventos sociales, cambios
   bruscos de clima, epidemias y catástrofes, cada uno con su reloj.

**Por qué importa.** Si los picos se miden contra la media del año, un desplome de nivel como el
de noviembre de 2025 fabrica «días bajos» y esconde «días altos» dentro de un año partido en dos.
**Los picos se definen desde ahora contra el nivel reciente**: los días previos, no la media del
año. Eso además coincide con la pregunta del proyecto, «¿va a incrementar?», que siempre es
respecto de lo que se venía viendo.

**Sobre el tránsito, según el propietario.** Los accidentados probablemente van a la Clínica La
Presentación o a Santa Sofía, y al SES solo llegan en momentos concretos, como la Feria. No lo
puede asegurar. El SIVIGILA no trae accidentes de tránsito como evento. La serie diaria de lesiones
de tránsito de MinDefensa en datos.gov.co (`FUENTES_EXTERNAS.md`) permite comparar la ciudad con el
SOAT del SES.

**Medido el mismo día** (`calendarios/seguridad/mindefensa.py` → `seguridad_mindefensa.csv.gz`,
solo sumas por día; cuaderno 07, sección 3.3):
- Correlación entre el **tránsito de la ciudad** (Policía, 3,1 casos por día) y el **SOAT del SES**
  (7,2 por día): **r = +0,01** por día y por semana. No se mueven juntos, como sostenía el
  propietario.
- En la Feria sí suben los dos: ciudad +63 % (±51) y SES +37 % (±6), frente a +26 % y +12 % de otros
  regresos.
- La lluvia fuerte no sube el tránsito ni en la ciudad (−8,5 % ±16) ni en el SES.

**Decisión derivada:** el tránsito de la ciudad **no** entra como predictor del triage del SES; la
Feria sí.

**Picos redefinidos contra el nivel local** (mediana de ±14 días, solo para describir): hay **30**,
frente a 22 contra la media del año. Los preceden la Feria (5,3 veces la tasa base) y los eventos
sociales (2,0 veces; 18 de 30). 18 caen en fin de semana, 9 en enero y 6 en diciembre. **Un nivel
que solo mira hacia atrás confunde la recuperación de Nueva EPS (mar-2026) con un pico.** Por
eso el pronóstico tendrá que llevar el estado de Nueva EPS como variable explícita.

---

## 2026-09-28 — Cambio de método: mecanismos con su propio reloj, no correlaciones globales

**Qué se decide.** El análisis de patrones deja de ser «correlacionar el residuo semanal con
todo». Pasa a buscar **mecanismos**. Cada familia de factores tiene:
- **su reloj**: los eventos sociales actúan en 0-5 días (trasnocho, trago, aglomeración,
  trauma, visitantes sin EPS a mano); lo infeccioso y lo climático, en 1-4 semanas
  (incubación, contagio);
- **su gatillo**: el cambio brusco, no el nivel;
- **su condición**: en día laboral la gente va a urgencias por la incapacidad, porque la cita de
  la EPS tarda una semana;
- **su subgrupo**: edad, hora, asegurador.

Y se ve en **picos puntuales**, no a lo largo del año.

**Por qué.** El propietario leyó el cuaderno 06 y vio en las gráficas lo contrario de lo que
decían sus lecturas. Tenía razón en lo esencial. Las lecturas concluían «no afecta» a partir de
un residuo al que **ya se le había quitado la estacionalidad**: eso borra precisamente los
efectos que se repiten cada año en las mismas fechas. Es un **sesgo de supervivencia**: se
concluyó sobre lo que sobrevivió al filtro. Además:
- una sola ventana semanal diluye los efectos de días;
- las variables de nivel no ven los cambios bruscos;
- el total entierra las firmas de subgrupo.

**Lo que ya estaba bien y se conserva:**
- Coincidir en el tiempo no identifica la causa. La Feria cae siempre al regreso de vacaciones,
  y el pico de mayo-junio coincide con lluvia, IRA y vacaciones escolares a la vez.
- Para eso sirven los años y fechas que **varían**, usados como experimentos naturales.

**Cómo se hace:**
1. Ventanas **preregistradas** en `patrones/datos/variables.csv` (filas del 2026-09-28), antes de
   mirar. Cada fila declara lo que ya se había visto.
2. Anatomía de los picos: composición y lo que pasó antes.
3. Efectos rápidos en días, con comparadores. Por ejemplo, la Feria contra otros regresos de
   vacaciones.
4. Efectos lentos por transiciones, separando día laboral de fin de semana.

**Dato nuevo que lo hace posible sin el motivo: la entidad administradora.**
`DIM_TRIAGE.GEENENTADM` → `DIM_ENTIDAD` cruza en el 100 % de 2020-2024 y el 99 % de 2025-2026.
Se extrae como `salidas/triage_entidad.parquet` (`python -m extraccion --entidad`; día × hora ×
entidad, 434.726 triages) y se agrupa con `extraccion/entidades.py`. Reparto:

| Grupo | % |
|---|---|
| Nueva EPS | **58,2** |
| EPS Sura | 22,2 |
| Otras EPS | 6,1 |
| **SOAT (accidente de tránsito)** | **4,0** |
| Régimen especial | 2,5 |
| Prepagada | 1,8 |
| **Particulares** | 1,3 |
| **ARL (accidente laboral)** | 1,0 |

La clasificación es un borrador que revisa el propietario (`salidas/entidades_clasificadas.csv`).
**El SOAT mide los accidentes de tránsito que llegan al SES**, que era la pregunta abierta del
propietario. La residencia del paciente **no** se usa, por decisión suya.

**Primer dato, aún sin analizar.** Nueva EPS pasa de 42.270 triages en 2025 a 19.532 en lo que va
de 2026 (~26 mil anualizados, −38 %). EPS Sura se mantiene (19.691 → 16.858, ~22 mil
anualizados).

### Mismo día: resultados del cuaderno 07 con el método nuevo

Archivo: `notebooks/07_mecanismos.ipynb`, 27 celdas, sin errores. Las pruebas son las
preregistradas en `variables.csv`.

1. **Red de salud (el efecto más grande).** Nueva EPS pasa de 115,8 a 72,2 triages por día entre
   2025 y 2026 (−38 %), mientras Sura sube; su cuota baja del 58 % al 42 %.
   - A mediados de **noviembre de 2025** se desploma de ~130 a ~55 por día. Empieza **antes** del
     cierre de Santa Sofía del 1-dic, así que apunta a algo entre el **SES y Nueva EPS**.
   - Se recupera en marzo de 2026 y vuelve a caer en **julio de 2026**.
   - Tras el cierre de Avidanti, Nueva EPS sube frente a Sura (+15,5 %).
   - **Estos escalones explican las semanas más bajas del cuaderno 06.**
2. **Feria contra 52 otros regresos de vacaciones**, media de los días 0-4:
   - **SOAT +36,9 ± 5,5 % contra +12,5 ± 8,5 %.** Sigue separado con t de 4 grados de libertad.
   - Particulares +61 contra +29 %, con intervalo ancho.
   - 15-44 +9 contra +4 %; total +7,3 contra +2,7 %, que se solapan.
   - Parte de la subida empieza el 1-2 de enero (Año Nuevo).
3. **Picos.** 22 días (más de +27 %), 13 de ellos en fin de semana y concentrados en enero y mayo.
   Su composición es casi la de un día normal. Los preceden la Feria (4,2 veces la tasa base) y
   los eventos sociales (1,8 veces). La mirada hacia atrás no sirve para lo lento: su ventana
   cubre al 65 % de los días.
4. **Transiciones de clima**, del cambio hacia adelante:
   - **Seco → lluvioso: 0-4 años +22,0 ± 17,8 % a los 7-13 días** (13 episodios), que se apaga a
     los 21-28.
   - Enfriamiento: + en mayores y en adultos en día laboral (+2 a +4 %). Calentamiento: −2 a −3 %.
     Los signos son coherentes, pero cada intervalo cruza el cero.
   - Son 36 comparaciones, así que el resultado de los niños hay que confirmarlo fuera de muestra.
5. **Lluvia fuerte:** −7,8 % de madrugada y ningún aumento del SOAT en el SES.
6. **Subidas de la IRA de la ciudad:** nada en el SES, ni en día laboral ni en fin de semana.

**Corrección del cuaderno 06.** Sus lecturas decían «no afecta». Ahora dicen qué no podía ver el
método (estacionalidad quitada, ventana semanal, nivel en vez de cambio, total en vez de
subgrupo) y remiten al 07.

**Lo que solo tiene el propietario:** las fechas de suspensión y reanudación de servicios entre
el SES y Nueva EPS. Con ellas, la variable de mayor efecto pasa a ser un predictor conocido **por
adelantado**.

---

## 2026-09-28 — Calendario de vigilancia cerrado: 14 eventos, marcadores y 2026 por Power BI

Detalle y evidencia en `calendarios/docs/VIGILANCIA.md`, sección final; estado por evento en
`calendarios/docs/INVENTARIO.md`.

**Decisiones de construcción** (las tomó el agente de integración; se asientan aquí):
1. **Archivo aparte para los eventos individuales**, `calendarios/vigilancia_sivigila_eventos.csv.gz`
   (`calendarios/vigilancia/eventos.py`). `sivigila.py` reescribe su archivo entero y dos
   escritores sobre el mismo se pisarían. Tiene la misma estructura larga. El censo de casos por
   año y evento está en `vigilancia_sivigila_eventos_censo.csv`.
2. **La semana principal es la de la columna `SEMANA`**, porque es la única que empalma con 2026
   (Power BI). **Contra ella:** no sigue la misma fecha todos los años. Por ejemplo, el 875 pasa
   a fecha de consulta en 2020 y el 549 en 2023. Por eso se conserva también
   `casos_ocurrencia_semana_consulta`, que es homogénea pero no existe para 2026. Según el
   evento, las dos correlacionan de ≥ 0,9 a 0,07-0,45.
3. **Las instantáneas de Power BI se versionan** (`calendarios/vigilancia/powerbi/AAAA-MM-DD/`).
   Son agregados sin persona y no se pueden rehacer: el tablero se sobrescribe cada semana. Hoy
   hay una sola, la del 28-09. **Falta una tarea que congele una cada semana.**

**Integrados** como serie semanal de Manizales (2015-2025, más 2026 por Power BI donde hay):
- 300 (agresiones por animales), 875 (violencias), 356 (intento de suicidio).
- 365 (intoxicaciones, suma de 360 a 414), 549 (morbilidad materna extrema), 831 (varicela).
- 155 (cáncer de mama y cuello), 850 (VIH), 813 (tuberculosis), 346 (COVID).
- 113 (desnutrición < 5 años), 620 (parotiditis).

Como **marcadores**: 452 (pólvora), 349 (brotes de ETA) y 348 (IRAG inusitado). En el límite
de volumen: 414, 735 y 750. Otros 53 eventos tienen volumen insuficiente, y 11 dejaron de
publicarse.

**Empalme de Power BI contra los microdatos:**
- Totales anuales de 2025 dentro del ±2 %.
- Excepción: el 300 de 2024, −8,3 %, sin explicar.
- El 995 del tablero va +3 a +8 % por encima, con r = 0,999: es un nivel, no un desfase.
- **Los tableros no usan una sola definición de semana**: 356 y 875 van por `SEMANA`; 300 y 831
  por la de notificación.

**Escalones** (antes de usar cualquiera, mirar su serie):
- 414 cae un 93 % entre 2016 y 2021 y arrastra al 365.
- 549 se triplica en 2020-2021.
- 831 cae de 1.316 a 110 entre 2015 y 2020.
- 348 absorbió COVID en 2022-2023.
- 113 salta ×2,9 en 2023.
- 155 no tiene 2022.

**Error encontrado y corregido.** `sivigila.fecha()` cortaba el texto a 10 caracteres y perdía
las fechas con día o mes de un dígito («5/1/2021 00:00:00»). En las fichas individuales perdía
8.718 de 29.557 filas del 831; `eventos.py` usa un lector propio. **Se midió que no afectaba al
995 ni al 998:**
- 995: 0 fechas nulas de 2015 a 2025.
- 998: 2016, 2020, 2021, 2023 y 2025 sin pérdidas; todo llega como fecha de Excel o como texto
  que se lee bien.

La función se arregló igual, cortando antes del espacio. Al rehacer `vigilancia_sivigila.csv.gz`
se obtienen 203.772 filas y **0 valores distintos**.

---

## 2026-09-28 — El hospital es el SES, el alcance se fija y empieza la búsqueda de patrones

**1. Identidad del hospital (resuelve la decisión #9).** El propietario confirma que es el
**SES Hospital Universitario de Caldas**, en Manizales. En el SIVIGILA 995 es la institución
**`170010010301` «SERVICIOS ESPECIALES DE SALUD»**, presente de 2019 a 2025. Lo medido:
- Sus consultas por todas las causas contra el triage semanal del proyecto dan **r = 0,758**
  en 313 semanas.
- **Reporta ~0 consultas por IRA**: 0 en 2022 y 2025, con 87 y 146 mil consultas. La
  correlación r = 0,703 entre la IRA de la ciudad y el triage 0-4 **no es mecánica**: el
  hospital no aporta a ese numerador.
- **Sí aporta al denominador** de la ciudad. Cuando se use «consultas de la ciudad» como
  variable externa, se **excluye el SES**.
- Dato sin interpretar: sus consultas del SIVIGILA suben de 2024 a 2025 (126 → 146 mil),
  mientras el triage baja (82 → 72 mil).

**2. Alcance, decidido por el propietario:**
- **Eventos sociales**: interesan los **grandes**, como la Feria de Manizales. Los partidos del
  Once Caldas quedan fuera por ahora.
- **Catástrofes**: de las bases abiertas colombianas (UNGRD en datos.gov.co).
- **Calidad del aire**: **descartada**. No hace falta.
- **Clima**: basta con `clima_unificado.csv.gz`.
- **Con esto hay datos suficientes para empezar a buscar patrones.** Se abre un cuaderno
  exploratorio de correlaciones y gráficas.

**3. Cómo se leen esos patrones.** Son **exploratorios**: sirven para generar hipótesis, no para
confirmarlas. Toda variable que se quiera contrastar después se preregistra en
`patrones/datos/variables.csv` antes de mirar su resultado confirmatorio.

### Mismo día: cuaderno 06, los primeros patrones

Archivo: `notebooks/06_patrones_exploratorios.ipynb`. Tiene 25 celdas y 7 figuras, cada una con
su lectura, y corre sin errores.

**Corrección de datos que vale para todo el proyecto.** Un día **sin filas** en el triage total
es una **caída del registro**, no cero pacientes. El 19 y el 20 de marzo de 2024 no tienen ni un
registro, y el 21 tiene 40. Rellenados con cero fabricaban una semana de −42 %. **Regla:** en el
total, un día sin filas es nulo, y un día con menos del 40 % de lo esperado fuera de COVID se
excluye como caída parcial. Rellenar con cero sigue siendo lo correcto para **subconjuntos**
(una banda de edad sí puede tener cero).

**Lo que se vio:**
- **Residuo semanal: 8,0 %, con autocorrelación de +0,62.** Lo que falta por explicar se mueve
  lento y en bloques.
- **Semanas extremas.** De las 10 más bajas, 7 caen entre noviembre de 2025 y febrero de 2026,
  y otra es la del terremoto. **Los calendarios actuales no tienen nada que decir de casi
  ninguna.**
- **Mapa de correlaciones:** 23 variables, rezagos de −1 a +4, 138 pruebas por panel.
  - Hay **15 celdas marcadas y el azar daría ~7**.
  - Solo es robusta la del propio SES en el SIVIGILA (+0,32 a +0,46), que es el control.
  - Ciudad sin el SES: +0,08 a +0,18.
  - Clima: ninguna de nivel pasa de ±0,15.
  - Feria y eventos: desaparecen al quitar la estacionalidad.
- **Consultas de la ciudad contra el hospital:** r = 0,17 en nivel y 0,00 con rezago. El total
  del SIVIGILA mezcla consulta externa (programada, que se hunde en festivos) con urgencias:
  **no mide demanda urgente**.
- **Feria:** +6,3 % de media, pero de −7,7 % a +27,3 % según el año. No se separa del regreso
  de vacaciones de enero.
- **Clima en quintiles:** la diferencia entre extremos queda dentro de ±3,6 puntos, sin
  pendiente.
- **Deslizamientos:** nada.
- **Terremoto:** −50 % el día del sismo, −26 % la primera semana, −7 % los días 8 a 21.

**Hipótesis que salen de aquí.** Sección 8 del cuaderno; ninguna probada.
- **H1:** la red de salud mueve el triage total más que cualquier otra familia.
- **H2:** la persistencia es la base contra la que se mide todo.
- **H3:** una catástrofe grande baja el triage registrado.
- **H4:** la lluvia de la semana lo baja un poco.
- **H5:** varicela y desnutrición comparten algo con el triage, quizá el calendario escolar.

**Siguiente paso propuesto:** el calendario del sistema de salud (H1).

---

## 2026-09-28 — Corrección del propietario: el ejemplo de la gripa no es el objetivo, y ahora toca recolectar

**Qué se corrige.** Las entradas anteriores del mismo día se estrecharon hacia lo respiratorio y
lo pediátrico: IRA 0-4, su correlación con el triage 0-4 y el pico de marzo a junio. **El
propietario aclara que la gripa era una ilustración del tipo de razonamiento, no la hipótesis
a perseguir.** El desenlace sigue siendo uno solo: **cuándo sube o no la tendencia del triage
total**. Y la etapa actual no es de conclusiones.

**Decisión.** Esta etapa es de **recolección e inventario**:
- Reunir el mayor número de variables externas candidatas, de fuentes oficiales y
  comprobables: clima, salud pública, sistema de salud, sociales, catástrofes, calendario.
- De cada una, documentar qué es, de dónde sale, qué cobertura tiene, con qué granularidad y
  rezago, y qué calidad.
- Las hipótesis y las correlaciones contra el triage total vienen **después**, con el
  inventario completo y preregistrando las variables en `patrones/datos/variables.csv`.

**Qué pasa con lo ya hecho.** Los hallazgos respiratorios y pediátricos de hoy (r = 0,703, el
pico de marzo a junio, etc.) **no se retiran, pero tampoco guían el trabajo**. Quedan como
auditoría de calidad de la fuente: demuestran que la serie SIVIGILA es coherente con el
hospital. No son un resultado del proyecto.

**Entregable central nuevo: `calendarios/docs/INVENTARIO.md`.** Es el catálogo de variables
candidatas, una fila por variable, con fuente, estado y limitaciones.

### Mismo día: inventario de fuentes fuera de vigilancia

Informe completo en `calendarios/docs/FUENTES_EXTERNAS.md`: 6 familias, cada fuente marcada como
verificada [V] o inferida [I].

**Lo más aprovechable.** Tienen historia desde 2020 o antes y se pueden automatizar:
- **Delitos de MinDefensa y la Policía** en datos.gov.co: lesiones, violencia intrafamiliar,
  homicidio, lesiones y muertes en tránsito. Por **día** y municipio, desde 2003, con 2-6
  semanas de rezago.
- **NOAA ONI**, el índice ENSO, 1950 →.
- **Pronóstico archivado de Open-Meteo**: temperatura desde 2021-03, lluvia desde 2024-01.
- **Partidos del Once Caldas** de local, con asistencia (API de ESPN, no documentada).
- **DANE**: población anual y desempleo por trimestre móvil.
- **UNGRD**: 80 emergencias en Manizales entre 2019 y 2025.
- **Sismos del USGS.**
- **Aerocivil** y la **terminal de buses**.
- **Aire del IDEAM**, hasta 2024-12.

**Escalones en fuentes externas.** Lesiones en tránsito sube de 279 a 1.013 entre 2019 y 2022;
lesiones personales cae un 62 % entre 2018 y 2025. Parecen cambios de registro, no de
realidad. Es la misma disciplina que con el triage: mirar la serie antes de usarla.

**Lo que no existe como serie y hay que pedirlo o construirlo:**
- Alertas hospitalarias.
- Cierres de servicios por fecha.
- Histórico de afiliados por EPS.
- Medidas de la Supersalud ya levantadas.

Lista de acciones del propietario en `HANDOFF.md`.

**Urgente por construcción.** La foto mensual de afiliados por EPS (BDUA) no guarda historia:
cada mes que no se descarga se pierde.

**Segundo incidente de privacidad del día.** Una consulta de prueba al REPS (`c36g-9fc2`)
imprimió en la terminal del agente una fila con nombre, cédula y correo de un profesional
independiente. No se guardó en ningún archivo. **Regla que sale de aquí:** en datos.gov.co,
la primera consulta a un dataset nuevo pide **solo el esquema** (`$select` con conteo, o los
metadatos), nunca `$limit=1` sobre todas las columnas.

---

## 2026-09-28 — Se aparta el NLP y se rehacen los calendarios externos con fuentes reales

**Decisión del propietario.** Las notas de triage quedan en pausa. El trabajo pasa a sustituir
los calendarios hechos a mano por **series obtenidas por API, descarga o raspado de fuentes
públicas**, con historia real, empezando por uno solo a la vez.

**Por qué.** La validación del mismo día (entrada siguiente) mostró que los calendarios
actuales no aportan señal fuera de muestra. El 67 % de la vigilancia son ventanas con fechas
fijas y los eventos son recurrentes anuales. El cuello de botella es la calidad de las
variables externas, no el modelo ni el texto.

**Orden** (fijado aquí; el propietario puede cambiarlo):
1. **Vigilancia en salud → microdatos SIVIGILA** (84 eventos, 2007-2025). Es la fuente con más
   valor y la única ya confirmada.
2. **Clima.** Auditoría de lo que el propietario sospecha mal calculado, más pronóstico
   archivado (Open-Meteo).
3. **Desastres y emergencias**, incluida la pandemia como periodo.
4. **Eventos sociales.**

**Arquitectura de vigilancia**:
- Código en `calendarios/vigilancia/`.
- Descarga cruda en `calendarios/vigilancia/crudo/`, **ignorada por git**. Los archivos del
  SIVIGILA traen nombre, teléfono y correo de quien notifica.
- Salida agregada a municipio × semana epidemiológica, **sin una sola columna de persona**,
  versionada como `calendarios/vigilancia_sivigila.csv.gz`.
- El porqué de la construcción va en `calendarios/docs/VIGILANCIA.md`.
- El CSV manual `vigilancia_salud_manizales_caldas.csv` **no se borra**: queda como registro de
  lo que había y de dónde salió cada fecha.

**Límite conocido desde el inicio.** Los microdatos se publican con ~8 meses de rezago (2025
salió el 25-ago-2026; 2026 no existe). Sirven para entrenar y medir. Para operar en tiempo
real hará falta otra vía (boletines semanales), que se investiga en paralelo.

### Mismo día, más tarde: la vía para 2026 y el orden de eventos

Fuente: `calendarios/docs/FUENTES_VIGILANCIA.md`.

**1. La vía para 2026 es Power BI, no los boletines.** El tablero público del INS «006
Vigilancia Rutinaria» da conteos por evento × semana × municipio, se actualiza cada semana y
va ~7 días por detrás.
- Se consulta por la API pública de Power BI, sin token. Su clave se lee cada vez de la lista
  SharePoint `MenuReporteNivel2`.
- Los tableros por evento traen historia y **cuadran con los microdatos**: 356 de 2016 da 368
  contra 368; 831 de 2024, 214 contra 211-214.
- Se descartaron:
  - El BES: solo baja a departamento.
  - La DTSC: reCAPTCHA en cada descarga.
  - datos.gov.co: congelado en 2022.
  - La Secretaría de Salud de Manizales: PDF mensual, casi todo gráficos.
- **Límites:** la API no está documentada y las 2 o 3 últimas semanas se revisan por
  notificación tardía. Cada descarga se guarda congelada con su fecha, para poder evaluar con
  lo que se habría sabido en su momento.

**2. Regla de privacidad nueva, y no negociable.** Los modelos públicos de los tableros por
evento **exponen en su esquema columnas identificables**: nombre, documento, dirección,
teléfono, coordenadas. Por eso:
- El proyecto solo pide **medidas agregadas** (`Casos`, `SUM(conteo)`) o la tabla ya agregada
  del 006.
- **Nunca pide una columna cruda de esos modelos.**
- Si se avisa o no al INS lo decide el propietario.

**3. Orden de integración después del 995:**
1. 998 (EDA), con el denominador del 995.
2. 356 (intento de suicidio).
3. 875 (violencia de género e intrafamiliar).
4. 300 (agresiones por animales).
5. 365 (intoxicaciones, suma de los códigos 360-414).
6. 831 (varicela) + 620 (parotiditis).
7. 549 (morbilidad materna extrema), solo si el triage cubre obstetricia; cubre el 12,6 %.

Los vectores quedan fuera: tienen 0-7 casos al año en Manizales. El 345 también: Manizales no
es sitio centinela. Pólvora (452), brotes de ETA (349) e IRAG inusitado (348) entran como
**marcadores de evento**, no como series.

**4. Aviso de fuga.** 356, 875, 300 y 365 son **parte del propio desenlace**: esas personas
consultan en urgencias, quizá en este mismo hospital. Solo pueden entrar al pronóstico con
rezago, o como desenlaces específicos. En la misma semana serían fuga de información.

**5. Calendario epidemiológico.** Semana de domingo a sábado; la SE1 es la que contiene el 4 de
enero. Tienen 53 semanas 2008, 2014, 2020 y 2025. **2021 no**, aunque algún calendario
interno del INS le asigne una.

### Mismo día: 995 y 998 integrados, y cuatro decisiones de construcción

Evidencia en `calendarios/docs/VIGILANCIA.md`. La corrida se repitió aquí desde el caché
(`--sin-descargar`, 16 s): 203.772 filas, **ninguna columna de persona** y el crudo ignorado
por git.

1. **La serie usable del 995 empieza en 2015.**
   - 2011 es otra ficha: trae casos, sin denominador.
   - 2012-2014 tienen semanas con 2 instituciones, duplicados y más IRA que consultas.
2. **La proporción IRA / todas las causas solo se compara dentro de cada año.** El
   denominador sube +60 % en 2021 y +35 % en 2024 por instituciones nuevas. La caída del
   16 % al 3,6 % es del denominador, no de la IRA. Para comparar entre años se usa el
   **conteo** de IRA, o una proporción sobre un **panel fijo de instituciones** (pendiente).
3. **El municipio se toma del código de la institución** (`cod_pre[:5]`), porque `cod_mun`
   cambia de formato entre años. Se midió: en Manizales es idéntico desde 2016, y en
   2012-2015 la correlación es ≥ 0,995.
4. **Semana epidemiológica asignada por regla, no por la columna.** Las 39 filas de «SE53 de
   2021» son la SE53 de 2020 y se descartan; ninguna es de Manizales.

**Hallazgos que cambian cosas.**
- **Correlación con el hospital: r = 0,703** entre la IRA 0-4 de Manizales y el triage 0-4,
  en 312 semanas de 2020-2025; 0,808 normalizando por año. El 0,685 de antes perdía los 124
  días con cero triages pediátricos, porque el `GROUP BY` no emite ceros. **Esa trampa vale
  para toda serie de conteo del proyecto.**
- **Límite:** en diferencias semanales la correlación baja a 0,18. Explica el nivel, no el
  cambio de una semana a la siguiente.
- **El segundo pico de lluvias (octubre-noviembre) no tiene pico de IRA en 0-4 años**, como ya
  pasaba en el hospital. Octubre es el mes más bajo.
- **Avidanti −39 % tras cerrar a Nueva EPS.** Pesa el 0,3 % del volumen de la ciudad y no se
  ve desplazamiento agregado.
- **La EDA de Manizales cae a la mitad desde 2020, sin explicación.** No se sabe si es real o
  de notificación.

**Sin verificar.**
- **Si el hospital del proyecto es una de las instituciones del 995.** Si lo es, parte de la
  correlación es mecánica: son las mismas consultas. El propietario lo sabe.
- El significado de los códigos de ajuste 4 y 6. Se asumió que 6 es descartado.

**Incidente de privacidad.** En la exploración inicial, el agente de integración imprimió en su
salida de sesión los 5 valores más frecuentes de `num_con`, que tienen forma de cédula. No
quedaron en ningún archivo del repositorio. A partir de ahí `num_con` va en la lista de
columnas descartadas al leer.

---

## 2026-09-28 — Validación: ¿se puede predecir el conteo sin el motivo de triage?

**Origen.** El superior del propietario sostiene que el motivo de la nota no hace falta para el
objetivo: las notas las escriben enfermeras, están sujetas a interpretación, y bastaría con
conteo + fecha enfrentados a factores externos (clima, salud, eventos, desastres). Se pidió
validarlo con los datos. **No es una decisión todavía: es la medición que la va a sostener.**
Script: `notebooks/05_validacion_sin_motivo.py` (solo parquet agregados y calendarios).
Ventana 2022-03-01 a 2026-09-20; control = día de semana, festivos, puentes, quincena,
vacaciones, Semana Santa, Navidad + nivel por año + escalón 2025-11. Las dos variables de
transición se definieron en el docstring **antes** de correr (no se preregistraron en
`variables.csv`: lo encontrado aquí es exploratorio).

**1. Los calendarios, tal como están, son en su mayoría calendario disfrazado.**
- `vigilancia_salud`: 216 de 321 filas (67 %) son «ventana_estacional», **las mismas fechas
  cada año**. El mes del año explica el **92,6 %** de la bandera IRA y el **100 %** de VSR e
  influenza. Usarlas es proyección, no predicción — exactamente lo que `CLAUDE.md` descarta.
  Solo 28 filas traen número de casos; de Manizales, 6.
- `eventos`: 99 filas, casi todas recurrentes anuales. **Efecto medido nulo**: días de evento
  +0,0 % [−0,4; +0,4]; días de Feria +0,2 % [−0,8; +1,1] por día.
- `desastres`: 17 filas, 4 pendientes de verificar.

**2. El presupuesto de ruido: sí hay algo que explicar, sobre todo a escala semanal.**

| | Diario | Semanal |
|---|---|---|
| sd del residuo tras control + estacionalidad | 11,8 % | 6,4 % |
| piso de Poisson (irreducible) | 7,3 % | 2,7 % |
| varianza residual potencialmente explicable | 62 % | 82 % |
| autocorrelación del residuo | +0,26 | +0,52 |

De la varianza diaria total: calendario 55,1 %, nivel por año +16,5 %, estacionalidad anual
**+2,5 %**, queda 25,9 % (≈10 puntos son Poisson).

**3. Las externas no explican el conteo TOTAL más allá del azar; sí explican el pediátrico.**
R² incremental de 19 variables externas sobre el residuo semanal: **total 0,112** (azar en
bloques de 8 semanas, p95 = 0,167: indistinguible) · adultos 0,112 (p95 0,175) · **0-14 años
0,260** (p95 0,197: por encima del azar).

Efectos por desviación típica (IC95 HAC, control + estacionalidad):

| | total | 0-14 años |
|---|---|---|
| temperatura, rezago 1-2 sem | −0,2 / −1,2 % | **−9,9 / −10,8 %** (frío → más niños) |
| humedad, rezago 1-2 sem | −0,5 / +0,3 % | **+6,2 / +7,4 %** |
| lluvia, misma semana | **−1,4 %** (llueve → menos consultas) | +1,1 % |
| enfriamiento brusco, misma semana | **−3,6 %** | −1,7 % |
| ruptura seca→lluvia | nulo, IC ±8 % | nulo, IC ±17 % |
| La Niña / El Niño | +1,8 % / −0,8 % | **+21,8 % / −27,2 %** (confundido con año) |
| terremoto 2026-08-10 (2 sem.) | **−21,5 %** | −29,5 % |

**El mecanismo respiratorio existe y se ve sin motivo, en la edad, con 6,7 años de historia.**
En el total se diluye: la correlación del residuo pediátrico con el de adultos es +0,08, y el
residuo pediátrico de la semana anterior no anticipa a los adultos (t = −1,75).

**4. Pronóstico semanal, origen rodante, 136 semanas (2024-01 a 2026-08), h = 1 semana.**

| Modelo | MAPE | acierto «¿sube?» | Brier |
|---|---|---|---|
| ingenuo (= semana actual) | 5,24 % | — | — |
| nivel + calendario | 6,07 % | 64,0 % | 0,240 |
| + estacionalidad (proyección) | **5,23 %** | 58,1 % | 0,237 |
| + externas conocidas en t | 5,64 % | 63,2 % | 0,252 |
| oráculo: + clima observado t+1 | 5,61 % | 55,9 % | 0,255 |

(Base: 47,1 % de semanas suben; Brier de una moneda 0,250.) **Ninguna variable externa mejora
el pronóstico del total, ni siquiera con el clima de la semana siguiente conocido.** Para la
serie pediátrica tampoco: el clima empeora de 15,0 % a 15,9 % de MAPE — la asociación existe,
pero no alcanza para predecir una semana adelante.

**5. Potencia.** Solo **7 semanas de ruptura seca→lluvia** en 237 (3 %). Efecto mínimo
detectable ~5,5 % sin corregir autocorrelación y ~7 % corrigiéndola, contra 2-10 % publicado.
La hipótesis de transición sobre el total **no se puede contrastar con este diseño, con o sin
motivo**.

**6. Lo que mueve de verdad el conteo es institucional.** Las semanas más extremas: 2025-11-02
y 11-09 (+21,7 %, +18,9 %) seguidas de 11-30 y 12-07 (−17,1 %, −13,2 %); la del terremoto
(−26,4 %); un bloque alto en marzo-abril de 2026. Ninguna coincide con una anomalía de clima.
Y el volumen anual (105,7 → 226,4 → 172,6) lo movieron COVID y la reclasificación.

**Lectura.**
1. **El superior tiene razón en que el motivo no hace falta para predecir** — `CLAUDE.md` ya lo
   decía: el motivo nunca podía ser entrada. Y para **probar el mecanismo**, la edad lo sustituye
   con más historia y sin interpretación de nadie.
2. **No tiene razón, con estos datos, en que las externas mejoren la predicción del total.** Los
   calendarios actuales no aportan señal fuera de muestra. No es que la idea sea falsa: es que
   las variables disponibles son calendario disfrazado, o demasiado raras para tener potencia.
3. El motivo solo añadiría lo que la edad no ve: la vía respiratoria **adulta** (la de la
   incapacidad). Es explicación, no pronóstico.

**Límites.** El periodo de prueba (2024-2026) es justo el de la deriva administrativa; ridge
con λ fijo sin ajustar; ENSO confundido con el año; solo horizonte semanal.

**Complemento del mismo día: lo que hay fuera** (investigación web; [V] = página leída por el
agente, no re-verificado en esta sesión).
- **La literatura coincide con el resultado.** Wargon et al. 2009, una revisión de 9 estudios
  [V]: *«adding meteorological data failed to improve model performance»*. Marcilio et al.
  2013 en São Paulo [V]: con temperatura el MAPE fue de 11,5 %, sin ella de 10,8 %. En
  Colombia el efecto grande aparece en lo **respiratorio o pediátrico** (Rodríguez-Villamizar
  2018; Medellín 2024; Bogotá 2015), no en el total.
- **La dilución es mayor de lo que suponía `CLAUDE.md`.** En los microdatos SIVIGILA 995 de
  2025, la IRA es ~5 % de las consultas de Manizales, no el 10 % supuesto.
- **Existe una serie de vigilancia real.** Son los microdatos SIVIGILA del evento 995 (IRA
  colectiva), en `portalsivigila.ins.gov.co/Microdatos`, **2011-2025**. Traen una fila por
  institución × semana con código de municipio, consultas por IRA en 7 grupos de edad y
  `tot_exturg`, que es el total de consultas de todas las causas. Tienen dos límites:
  - Publican con ~8 meses de rezago, así que sirven para entrenar, no para operar.
  - Traen nombre, teléfono y correo de quien notifica: esas columnas se descartan al cargar.
- **Hay eventos institucionales que coinciden con las semanas extremas** [V]:
  - Avidanti suspende todos los servicios a Nueva EPS el 21-ago-2025. Es ~30 % de la capacidad
    de la ciudad y ~1.600 triages al mes.
  - Santa Sofía cierra a Nueva EPS el 1-dic-2025.
  - Diagnostimed suspende en diciembre de 2025.
  - La Resolución 373 de 2026 obliga a reportar los tiempos de triage desde el 1-ene-2026.

  Esto es compatible con que el hospital recibiera primero la demanda desplazada (el pico de
  noviembre) y después cambiara su registro o se viera afectado por el cierre. **No está
  comprobado.** Se comprueba con `tot_exturg` por institución.

---

## 2026-09-24 — Se reabre la competencia de modelos EN CPU: Llama 3 y otros ligeros

**Decisión del propietario**: antes de dar por cerrado que el problema necesita GPU, medir
si **Llama 3 o alguna de sus variantes** —u otro modelo ligero— resuelve lo que qwen3:8b no
pudo, con menos recursos. No contradice el cierre de la fase de CPU: aquel era **no iterar
más el prompt**; esto es cambiar de **modelo** con el prompt fijo.

**Cómo se mide, y por qué así:**
- **La misma sonda de 32 notas** (17 fallos verificados + 15 guardas) y **el mismo prompt
  v1.7**, para que la única variable sea el modelo (regla 7).
- **Dos modos**: `solo` (sin filtros ni segunda pasada, como `NLP.duelo`: mide al modelo)
  y `cadena` (lo que iría a producción). Primero `solo` para todos; `cadena` para los
  mejores. Con filtros dos modelos salen parecidos porque se mide a los filtros.
- **qwen3:8b se vuelve a correr en la misma tanda**, no se compara solo contra sondas
  viejas: el 8B no es determinista cuando duda (entrada del duelo 8B-14B).
- **Las notas duras se repiten 3 veces** para medir la inestabilidad, que es el fallo que
  hoy no tiene arreglo (descartes falsos que salen o no según la corrida).
- **Se juzga leyendo, no contando**: la sonda cuenta mal (entrada «Conclusión: el 14B…»).
- **Una sola corrida contra Ollama a la vez**; los agentes solo investigan y leen.

Script de la comparación, fuera del repo (no cambia código del proyecto): el `comparar.py`
del scratchpad de la sesión, que usa `NLP.banco`, `NLP.cadena` y `NLP.fidelidad` sin tocarlos.

**Corrección del propietario, el mismo día: igualdad de condiciones.** Un modelo solo se
compara con qwen3:8b si es **de su mismo peso** (~8B, Q4_K_M, ~5 GB). `llama3.2:3b` se midió
primero por ser rápido, pero es un **piso**, no un rival: leído, 6/32 bien contra ~14/32 de
qwen3:8b sin filtros. No dice nada de la familia Llama. La comparación de familia es
`llama3.1:8b` contra `qwen3:8b`, más los **reentrenados de Llama 3.1 8B** por terceros
(Tulu 3.1, Hermes 3, SuperNova-Lite), que tienen el mismo tamaño. Llama 3.3 (solo 70B) y
Llama 4 (109B y 400B) no caben en 16 GB.

**Sesgo que queda a favor de qwen, y cómo se compensa**: el prompt v1.7 se afinó durante días
sobre qwen3:8b (ya le costó notas al 14B, que se abstenía de más). El mejor rival recibe
**una vuelta de ajuste del prompt**, como la tuvo el 14B (`v1_7_14b.py`), antes de decidir.

**Diseño final, fijado por el propietario y PREREGISTRADO antes de ver ningún resultado**
(escrito cuando solo se habían leído 2 salidas de llama3.1:8b):

- **Muestra de 63 notas** = la sonda (32) + una muestra **nueva** de los bancos que el prompt
  no vio al afinarse: 16 de `fallos.csv` (2 por cada bandera fuerte, empezando por la más
  rara) y 15 de `aciertos.csv` (2 por estrato; de `descarte_correcto` solo quedaba 1),
  semilla 11, sin OID de la sonda. La nueva existe porque la sonda favorece a qwen: v1.7 se
  afinó mirándola.
- **Contendientes, mismo prompt v1.7, modo solo, Q4, temperatura 0**: qwen3:8b ·
  llama3.1:8b · tulu3:8b (sin su mensaje de sistema) · Llama-3.1-Storm-8B · gemma3:12b ·
  gemma4:12b-it-qat. Los dos gemma son **un escalón más pesados** (~7 GB) y se reportan
  aparte de los 8B.
- **Veredicto por nota, leído** (bien / parcial / mal) contra una lista de lo que la
  respuesta correcta **debe** y **no debe** contener, escrita antes de juzgar a los modelos.
- **Puntaje — un daño pesa el doble que un arreglo** (la regla del propietario: no vale
  arreglar una nota y dañar otra que estaba bien):
  - nota de `fallo`: bien **+1**, parcial **+0,5**, mal **0**
  - nota de `acierto`: bien **0**, parcial **−1**, mal **−2**
  - el **descarte falso** se cuenta además aparte, en cualquier banco: es el peor error.
- **Dos lecturas**: la **estricta** (la línea que guardaría producción, `modelo.limpiar`),
  que es la que decide; y la de **comprensión** (la respuesta final del texto completo),
  que dice si un arreglo de formato cambiaría el orden. Motivo: llama3.1:8b razona en voz
  alta antes de responder y la primera línea sale inservible aunque la respuesta sea buena.
- **Sin repeticiones**: llama3.1:8b dio salidas idénticas en dos corridas; a temperatura 0
  es determinista, y el tiempo rinde más en notas y modelos.
- **La velocidad se mide aparte**, con la máquina quieta: esta tanda coincidió con descargas.

**Primer resultado medido (sonda, 32 notas, banco corregido: 18 fallos · 14 aciertos)**. El
revisor corrigió el banco de 13 de las 63 notas antes de juzgar: 9 «aciertos» de v1.6 estaban
mal por las reglas de v1.7 (duda, embarazo o negación perdidos) y 4 «fallos» eran falsos
positivos de un detector.

| Modo solo, prompt v1.7 | Fallos | Aciertos | Puntaje | Descartes falsos |
|---|---|---|---|---|
| qwen3:8b | +5,5 | −9 | **−3,5** | 2 |
| llama3.1:8b, lectura estricta | +5,0 | −16 | **−11** | 2 |
| llama3.1:8b, lectura de comprensión | +6,0 | −15 | **−9** | 5 |
| llama3.2:3b (piso) | | | −16 | 3 |

Lectura: **en arreglar fallos empatan; Llama daña el doble de aciertos.** Inventa el sufijo de
la regla 6 («en gestante de N semanas») en 6 notas, una de un varón; descarta «amarillo» y
«control prenatal»; en el 44 % de las notas su primera línea no es la respuesta (razona en voz
alta). Parte del daño lo induce la redacción de la regla 6, afinada para qwen, pero la lectura
de comprensión, que ignora el formato, lo deja igual de abajo.

**Estabilidad, medida por primera vez** (16 notas duras × 3 corridas): qwen3:8b cambia la
salida en 5/16 y el **veredicto en 1/16** (la hernia discal: descarte falso en 2 de 3);
llama3.1:8b cambia en 2/16 y 1/16. La inestabilidad de qwen es real pero estrecha: una nota,
no una familia.

**Resultado sobre las 63 notas: qwen3:8b le gana a llama3.1:8b** (medido y leído el mismo día).

| Modo solo, v1.7 | Sonda | Nueva | **Total 63** | Descartes falsos |
|---|---|---|---|---|
| qwen3:8b | −3,5 | **+10,5** | **+7** | 2 (0 en la nueva) |
| llama3.1:8b, comprensión | −9 | +7 | **−2** | 5 (0 en la nueva) |
| llama3.1:8b, estricta | −11 | −8,5 | **−19,5** | 2 |

Qué decide: **aun en su mejor lectura (la que ignora el formato), Llama queda 9 puntos
abajo**, así que la salida estructurada no lo rescataría y no se le corre esa segunda ronda.
En la muestra nueva qwen no daña ninguno de sus 11 aciertos; Llama inventa embarazos (3),
cambia síntomas («prurito» → «dolor mamario», «ardor al orinar» → «arritmia») y deja una
nota sin respuesta. **Llama gana solo en 3 trámites**, donde qwen copia el trámite en vez de
«sin motivo clinico» (parcial: no inventa). Los dos fallan igual en parte del cuerpo
inventada, «desde ayer» y negaciones: errores de la tarea, no de la familia.

**Muestra nueva contra sonda**: qwen pasa de −3,5 a +10,5. La sonda son sus peores notas a
propósito; la nueva se parece más al corpus. Las dos cifras se reportan siempre juntas.

**Velocidad**: la única medición limpia hasta ahora es qwen3:8b en la nueva, 16,4 s/nota de
mediana; llama3.1:8b es más lenta por construcción (razona en voz alta: ~100 tokens por
nota contra ~10).

**Tulu 3 8B (Llama 3.1 reentrenado por AllenAI, sin su mensaje de sistema)**: −8 solo (sonda
−13,5, nueva +5,5), 3 descartes falsos, **0 % de fallos de formato** y el más rápido de los
8B (15,5 s/nota de mediana, limpio). Resuelve cosas que qwen no: no descarta la hernia discal,
descarta los 3 trámites que qwen copia, no inventa lado ni «desde ayer». Su defecto dominante
es **inventar el sufijo de la regla 6 en 15 notas** (varón incluido): el reentrenamiento
arregla el formato de Llama y empeora la invención.

**Con los filtros de producción** (`posprocesar` de v1.7 aplicado a las salidas guardadas, sin
segunda pasada; deterministas, no llaman al modelo): **qwen3:8b +15,5 · tulu3:8b +2,5 ·
llama3.1:8b −9,5**. El orden no cambia. El filtro quita los 15 embarazos de Tulu, pero en 11
queda otro error debajo; 7 de los 10 puntos que gana Llama son del filtro de trámites
escribiendo «sin motivo clinico» sobre su relleno, no mérito del modelo.

**Defectos de los filtros de producción que salieron de aquí** (valen solos, pendientes):
1. `quitar_embarazo_inventado` **borra un embarazo real**: en una nota de «prueba positiva de
   embarazo» quita las semanas inventadas y con ellas el embarazo; la salida queda vacía.
2. El filtro de trámites deja restos: «derivada de la eps» → «la eps» (qwen, una nota de la
   muestra nueva).
3. `descarte_falso` → segunda pasada **se dispara en 2 trámites puros bien descartados** de la
   muestra: falsos positivos del disparador; si la segunda pasada inventa, un acierto se
   vuelve fallo. (Los OID de cada caso están en el material de la competencia, fuera del repo.)

**Los dos ~12B (un escalón más pesados: ~8 GB en RAM, cabe en esta máquina con ~2 GB de
margen, sin paginar).** Velocidad limpia, un solo modelo en memoria.

| Modo solo, v1.7 | Sonda | Nueva | **Total 63** | Con filtros | Desc. falsos | RAM | s/nota |
|---|---|---|---|---|---|---|---|
| **gemma4:12b-it-qat** | +7,5 | +17,5 | **+25** | **+26** | 5 | 8,49 GB | 23,8 |
| qwen3:8b | −3,5 | +10,5 | +7 | +15,5 | 2 | ~5,9 GB | 16,4 |
| gemma3:12b | −3,5 | +10 | +6,5 | +7,5 | **0** | 8,06 GB | 21,8 |

- **gemma4:12b resuelve casi todo lo que ningún 8B pudo**: oídos tapados e hipo completos;
  duda → certeza 4/4; negaciones 4/4; la agresión de la pareja; «antier»; no inventa lado,
  parte del cuerpo ni embarazo. En la muestra nueva no daña ningún acierto. **Su único error
  sistemático es el descarte falso (5, todos en la sonda)**: «congestionado», la hernia
  discal, la turbinoplastia, «amarillo», el control prenatal. Es el patrón del qwen3:14b con
  v1.7: el bloque de abstención, endurecido para el 8B, un modelo más capaz lo cumple de más.
  Si la segunda pasada los recuperara, el techo es +33.
- **gemma3:12b empata con qwen solo y pierde con filtros**, pero es **el único con cero
  descartes falsos**. Sus errores son omisiones y cambios de sentido, que ningún filtro ve;
  los de qwen son mecánicos (lado, parte, «antier», institución), que los filtros sí ven.
- **Ningún modelo resolvió «no me baja el azúcar»** (todos: «hipoglucemia»): es de glosario.

**Pendiente antes de tomarlo como decisión**: (1) verificación por un segundo juez **ciego**
de qwen3:8b contra gemma4:12b en las 43 notas donde difieren —el +25 lo juzgó un solo
revisor—; (2) la segunda pasada real de gemma4 sobre sus descartes; (3) la vuelta de ajuste
del prompt (abstención suavizada) que el diseño reserva al mejor rival.

**Verificación ciega: confirmada.** Un segundo agente, sin acceso a la clave ni a los archivos
de la competencia, juzgó las **43 notas donde qwen3:8b y gemma4:12b difieren**, con el orden
A/B barajado por fila. Destapada la clave: **gemma4 es mejor en 31, qwen en 3, empate en 9**;
veredictos gemma4 33 bien · 6 parcial · 4 mal, qwen 7 · 23 · 13. Descartes falsos: gemma4 3,
qwen 0 en esas 43 (los dos de qwen, «congestionado» y la hernia, **gemma4 también los hace
con la misma salida**, por eso no entraron). Dos jueces independientes, uno ciego, dan el
mismo orden. Lección de método: el juez resumió «A es mejor que B» como si A y B fueran
sistemas fijos, cuando el orden estaba barajado; **lo que vale del juez ciego son sus
veredictos fila a fila, no su resumen**.

**Preregistro de la vuelta de ajuste para gemma4** (escrito antes de correrla): se usa
`NLP/prompts/v1_7_14b.py` **tal como está** —escrito el 2026-09-24 para qwen3:14b, que tenía
el mismo problema—, sin ningún retoque mirando a gemma4. Solo cambia el bloque de abstención.
Mismas 63 notas, mismo juicio, mismo puntaje; se reporta **al lado** de v1.7, no en su lugar.
Criterio: si baja los descartes falsos **sin** dañar aciertos, es el prompt de gemma4.

**REVERTIDO el mismo día, antes de correrlo, por decisión del propietario** (entrada siguiente):
la vuelta con `v1_7_14b.py` se cancela y la reemplaza un prompt propio por modelo.

---

## 2026-09-24 — Cada modelo con su propio prompt: gana el primero que cruce la barrera

**Decisión del propietario.** Un prompt afinado para un modelo no es igualdad de condiciones.
Ya se conocen las fuerzas y debilidades de cada uno; ahora **cada modelo recibe su propio
prompt optimizado** y compiten por cruzar la barrera que qwen3:8b no cruzó. **El primero que
la cruce es el que se queda.**

**El riesgo que hay que cerrar, y cómo**: afinar prompts mirando las mismas 63 notas con que
se mide los hace **memorizar** esas notas («no me baja el azúcar = hiperglucemia» escrito en
el prompt) y el puntaje sube sin que el modelo mejore. Tres defensas:
1. **Conjunto de validación nuevo**, de las mismas familias difíciles, que ningún agente de
   prompt ve. Su lista de verificación se escribe antes de correr ningún modelo.
2. **Los prompts solo llevan reglas generales**, nunca frases, palabras raras o casos de
   notas concretas de la muestra. El revisor lo audita en cada ronda.
3. **Mismo presupuesto para todos**: máximo 3 rondas por modelo, todos parten de v1.7, mismos
   filtros (`posprocesar` de v1.7 sin cambios) y misma cadena con segunda pasada.

**PREREGISTRO — la barrera** (modo cadena, que es lo que iría a producción; juicio leído
contra la lista, banco real):
- **B1, lo que qwen no pudo**: de las 16 notas duras (`oids_duros.txt`), **≥ 12 bien**.
- **B2, no dañar**: en los aciertos del banco real, **0 mal**.
- **B3, no sacar pacientes de la cuenta**: **0 descartes falsos** sin marca; uno marcado
  `revisar` por la segunda pasada se tolera, porque lo ve una persona.
- **Confirmación**: quien cruce B1-B3 en las 63 se corre en la validación; ahí debe dar
  0 aciertos dañados, 0 descartes falsos sin marca y **puntaje por nota mayor que el de
  qwen3:8b con v1.7 y cadena** en esa misma validación.

**Quién se queda**: el primero que cruce la barrera y la confirmación, **contando por rondas**
(todos corren la ronda 1, luego la 2…). Si cruzan varios en la misma ronda: el de mejor
puntaje en validación; si empatan, el más ligero. Si nadie cruza en 3 rondas, **no hay
ganador por esta vía** y se le dice al propietario que el problema no se resuelve con
modelos ligeros en esta máquina.

**Participantes**: gemma4:12b-it-qat, qwen3:8b, gemma3:12b, tulu3:8b, llama3.1:8b (la familia
que el propietario pidió explorar). Storm 8B entra si en su corrida con v1.7 supera a Tulu.

**Storm 8B, medido: no entra.** −8 solo (igual que Tulu), +1,5 con filtros (Tulu +2,5) y **8
descartes falsos**, el peor número de la competencia; inventa el embarazo en 12 notas.

**Cuarto defecto de los filtros**: `quitar_parte_inventada` borró una parte del cuerpo **real**
de una respuesta fiel de Storm porque la nota la escribe con errata y el detector compara
letra por letra. Primer caso medido de un filtro que convierte un bien en mal.

**Aclaración del reglamento, a mitad de la ronda 1, para todos por igual**: dos agentes
encontraron por separado que la segunda pasada se dispara en trámites puros bien descartados,
y con un cierre que prohíbe abstenerse solo puede copiar el trámite o inventar: la barrera B2
quedaba imposible por diseño. Se permite que la segunda pasada se abstenga **solo** cuando lo
único que trae la nota es trámite (queda «sin motivo clinico» marcada `revisar`). Todos los
prompts se corren con la aclaración disponible; ninguno había corrido todavía.

**Segunda pasada real con v1.7 (cadena completa), medida el 2026-09-24:**
- **gemma4:12b recupera 3 de sus 5 descartes falsos** (la remisión con diagnóstico, el
  procedimiento, el control prenatal), los tres fieles; los otros 2 quedan «sin motivo clinico»
  **marcados `revisar`**. Los 2 trámites puros quedan bien. **Con la cadena, gemma4 no deja
  ningún descarte falso sin marca.**
- qwen3:8b recupera la remisión con diagnóstico **inventándole la localización** (otra vez, y
  ningún detector la ve); el otro descarte queda en `revisar`.
- **Cruzada** (primera qwen, segunda gemma3): la remisión sale fiel, sin la invención; pero con
  el cierre estricto de v1.7 **daña los 2 trámites puros** (copia el servicio que remite). Es
  el problema que resolvió la aclaración del reglamento.

**Hallazgo de velocidad: la segunda pasada rompe la caché de Ollama.** Ollama reaprovecha el
prefijo común de los prompts: medido con qwen3:8b, la primera llamada lee 2.218 tokens en 213 s;
la misma nota repetida, 0,4 s; **otra nota, ~10 s** (solo paga su tramo propio). Pero
`construir_segunda_pasada` pone su aviso **al principio**, así que cada vez que se dispara lee
el prompt entero otra vez: **288-419 s contra ~14 s**, y al volver a la primera pasada paga de
nuevo. Arreglo sin costo: mover el aviso al final, justo antes de la nota. Pendiente de
producción (`NLP/prompts/v1_7.py`, `_AVISO_SEGUNDA`).

**Línea base en cadena con v1.7** (filtros + segunda pasada real, 63 notas):

| Cadena v1.7 | Total | B1 (≥ 12/16) | B2 (0 aciertos mal) | B3 (0 DF sin marca) |
|---|---|---|---|---|
| **gemma4:12b** | **+30** | **14/16 ✓** | 1, marcado `revisar` | 0 ✓ |
| qwen3:8b | +15,5 | 5/16 ✗ | 2 ✗ | 0 ✓ |
| qwen3:8b + 2.ª pasada de gemma3 | +14,5 | 6/16 ✗ | 2 ✗ | 0 ✓ |
| gemma3:12b | +5,5 | 6/16 ✗ | 5 ✗ | 0 ✓ |

La cruzada no conviene: recupera limpia la remisión con diagnóstico (+1) pero convierte en
motivo los dos trámites puros (−2).

**Ambigüedad del preregistro, resuelta ANTES de ver la ronda 1**: B3 tolera un descarte falso
marcado, pero B2 no dice nada de marcas, y un acierto descartado y marcado cae en los dos. **Se
resuelve en sentido estricto: un acierto que termina descartado cuenta como dañado en B2 aunque
esté marcado.** Motivo: la regla del propietario es no dañar lo que estaba bien, y una nota que
pasa a necesitar revisión humana está dañada, aunque sea visible. La tolerancia de B3 queda
para los fallos. Consecuencia: gemma4 con v1.7 **no cruza por una nota**. Resolverla después
de ver R1 sería acomodar la regla al candidato.

**R1 qwen3:8b (2026-09-25; `FORMATO="razonado"`, copia literal a 5 casillas y después el
motivo)**: +12,5 en cadena (v1.7: +15,5). **No cruza**: B1 11/16 (v1.7: 5/16), B2 4 ✗, B3 1 ✗
(la segunda pasada dijo «ningún motivo clínico identificado», un descarte que esquiva la marca).
Auditoría: limpio. **La copia literal resuelve sentido y duda** —el coloquialismo de glucemia
invertido por primera vez en un 8B, los oídos, «creo que», quién causó la lesión—, pero **falla
el ensamblaje**: llena la casilla de negaciones y el motivo no la usa; se cuela «nada»; inventa
un tiempo y un «posible». Errores de armado, no de comprensión: van a la ronda 2.

**R1 tulu3:8b (instrucciones en inglés + recordatorios por nota armados con los detectores)**:
+8 en cadena (v1.7: +2,5). No cruza: B1 10/16, B2 5, B3 1. Auditoría: limpio. Arregla los
embarazos inventados (16 → 0) y recupera descartes; pero **el recordatorio desplaza a la queja**:
el modelo escribe solo lo que se le recordó («niega X» sin el síntoma principal) y comprime las
notas largas. Lección general: inyectar hechos de la nota en el prompt funciona solo si se dice
que se AÑADEN al motivo.

**R1 gemma4:12b (abstención por categorías)**: +28,5 en cadena, el mejor de la ronda pero bajo
su v1.7 (+30). No cruza: B1 11/16 (v1.7: 14), B2 1 (el mismo acierto de una palabra de aspecto,
marcado), B3 0 ✓. Auditoría: limpio. Arregla duraciones, edad pediátrica y el control de la
gestante; **pierde la duda en 2 notas que v1.7 hacía bien**: el énfasis nuevo en «escribe lo que
dice del paciente» se comió la regla de la duda. De sus 14 «sin motivo clinico», 12 son trámites
correctos: no se abstiene más que con v1.7.

**R1 llama3.1:8b (formato razonado con casillas)**: −6 en cadena (v1.7: −9,5 con filtros). No
cruza: B1 4/16, B2 9, B3 0 ✓. Auditoría: limpio. **El formato razonado arregla su problema de
formato** (63/63 JSON válidos) y los embarazos inventados (0), pero **las casillas hacen eco en el
motivo**: «posible» en 25/63 salidas sin duda en la nota, tiempos inventados en 6, diagnósticos
deducidos del nombre de un servicio. Lección general: una casilla vacía que el modelo debe
«llenar» invita a inventar.

**gemma3 R1 falló por memoria** (2026-09-25, 11:54-12:50): con los navegadores abiertos, 8,1 GB
de modelo paginaron a disco; 6 notas, la última a 473 s, y un timeout de 30 min. Se repite con
los navegadores cerrados. Salida apartada como `descartado_R1_gemma3_timeout`.

**La vara de la confirmación, medida (2026-09-25)**: qwen3:8b + v1.7 en cadena sobre las 56 notas
de validación: **−18 (−0,32 por nota)**; fallos 2 bien / 2 parcial / 12 mal; aciertos 24 / 11 / 5
mal; **0 descartes falsos**. En notas que el prompt nunca vio, v1.7 rinde mucho peor que en la
muestra con que se afinó: confirma que hacía falta la validación. El juicio nota a nota vive solo
en `validacion_privada/`.

**Prioridad de la cola, por decisión del propietario** (más potencial primero): gemma4 →
validación de qwen v1.7 (para poder confirmar a gemma4 enseguida) → qwen3 → gemma3 → tulu3 →
llama3.1. Resumen del método y los números: `NLP/docs/COMPETENCIA.md`.

---

## 2026-09-24 — Sincronización: se versionan los datos y se sube al repositorio actual

**Decisiones del propietario, tomadas sabiendo lo que implican:**

1. **Salen de `.gitignore`** `NLP/salidas/tabla/notas_triage.csv.gz`, su `auditoria.json` y
   las cinco series `salidas/triage_*.parquet`. Las reglas de carpeta pasaron a reglas de
   contenido (`NLP/salidas/*`, `/salidas/*`) porque git no re-incluye un archivo de una
   carpeta ignorada entera; el bloque «NUNCA» del final sigue ganando sobre mapas y DuckDB.
   La primera vez el sistema de permisos se lo bloqueó a Claude; con la petición explícita
   del propietario, pasó.
2. **Viajan las skills** (`.claude/skills/`, MIT y Apache), para trabajar igual en los dos
   equipos. `settings.local.json` no. El contexto entre equipos no vive en `.claude/`: vive
   en `CLAUDE.md`, este archivo y `HANDOFF.md`.
3. **Se sube al repositorio actual con el historial como está.** Se le ofrecieron tres
   caminos (repo nuevo limpio, recomendado; push al actual; `git filter-repo`) y eligió el
   push al actual. **La limpieza del historial queda pendiente**: hasta hacerla, un clon
   copia las notas crudas de los commits viejos (ver la entrada siguiente).

**Barrido antes del commit**, sobre los 201 archivos que entraban: correos y números de 6 a
10 cifras, y cada número cruzado contra los OID reales del mapa local (sin imprimirlos).
Aparecieron **2 OID reales en ejemplos de uso** de los docstrings de `NLP/banco.py` y
`NLP/duelo.py`: cambiados por `<OID>`. Uno de `figuras.py` era un color hexadecimal que
coincide por azar. Los cuadernos, limpios: los números estaban dentro de las imágenes. Lo
demás son datos inventados de las pruebas y ejemplos de la documentación de las skills.

**El `git push` también lo bloqueó el sistema de permisos** para Claude. Lo ejecuta el
propietario.

---

## 2026-09-24 — Trabajar desde un equipo propio con GPU: la tabla de notas sin identidad

**Qué quiere el propietario, en sus palabras resumidas.** Este equipo es lento (CPU, 15,9 GB).
En su casa tiene uno con **RTX 4060 de 8 GB**. La idea: clonar el repositorio allá, dejar
la GPU procesando de noche las ~95.000 notas, probar prompts y modelos, dejar a Claude
revisando y evaluando, y subir los resultados para que aquí solo haya que consumirlos y
analizarlos. Usar su equipo como servidor, sin pagar GPU y sin el techo de esta máquina.

**Decisión.** Las notas viajan como **`NLP/salidas/tabla/notas_triage.csv.gz`**, generada y
auditada por `NLP/nube/tabla.py`. Seis columnas: `id` aleatorio, `fecha` (día), `nivel`,
`nivel_nombre`, `edad_banda`, `nota`. El porqué de cada una está en `NLP/docs/TABLA.md`; lo
que no se puede reconstruir leyendo el código es esto:

1. **Sin OID, pero con id aleatorio.** El propietario no necesita saber de quién es cada
   nota: estudia tendencias, no personas. Pero dijo «de pronto más adelante». El id no
   revela nada y deja esa puerta abierta: `mapa_local.parquet` (`id → OID`) **se queda en
   este equipo** y nunca va al repositorio. Sin ninguna llave, sumar mañana otra variable
   a las mismas notas obligaría a reprocesarlas todas.
2. **Borrar, no marcar.** Decisión del propietario: `[NOMBRE]` o `[FECHA]` no aportan nada
   clínico y son ruido para el modelo. Se borra exactamente lo que tapa `enmascarar.py`.
3. **Día, no hora; edad en bandas, calculadas en SQL Server.** Con el día, cada nota queda
   entre ~150 del mismo día; con la hora exacta, apunta a una persona. Ni la hora ni la edad
   exacta llegan a la memoria del proceso.
4. **Niveles con menos de 100 notas → `otro`** (`I-G, IV-G, M, UA, V-G`: 209 notas).
   «Día + MUERTO + lo que pasó» se cruza con una noticia.
5. **La edad se incluye por el argumento, no por la persona.** Si una transición de clima
   pega más en 0-4 y 65+ que en 15-44, eso es el mecanismo y no una coincidencia.

**Evidencia.** Antes de decidir se midió cuánto identificable trae el texto: sobre las 3.087
notas locales, **2,6 %** tiene algo (cota inferior, sin la identidad del paciente). En la
corrida completa (95.424 notas, 2025-01-08 a 2026-09-24) se borró algo en el ~3 %: fecha
1.588, nombre de tercero 887, lugar 292, nombre del propio paciente 173. **Auditoría: 0
fallos**, identidad verificada contra la base, orden vs OID 0,0003 (límite 0,0129),
términos clínicos 2.203 → 2.207 en 2.000 notas al azar. 4,2 MB comprimido.

**La primera corrida completa falló la auditoría y el CSV se borró solo**: 3 notas con una
fecha pegada a un guion, que `enmascarar.py` deja pasar a propósito. Se añadió una segunda
pasada con los patrones de la auditoría (`fecha_red`, 3 notas) y la segunda corrida salió
limpia. **El caso de la fecha real es un fallo de `enmascarar.py` que también afecta al
paquete de la nube.**

**Descartado, y por qué:**
- *Subir OID + nota cruda.* El OID es la llave a nombre y cédula en la misma fila de
  `DIM_TRIAGE`, y el texto trae nombres, correos y direcciones escritos a mano.
- *Cifrar el OID.* Un OID cifrado o con hash se deshace recalculándolo; un id aleatorio con
  el mapa solo aquí, no.
- *Usar el paquete de `NLP/nube/`.* Lleva el prompt ya armado y congelado: en casa no se
  podrían probar otros prompts ni modelos.

**Lo que no resuelve el código:** la autorización institucional para procesar datos de
salud fuera del hospital (`NLP/docs/NUBE.md`). La capa técnica reduce la exposición; la
decisión es de la institución.

---

## 2026-09-24 — El historial de git ya tiene texto clínico real, y está en GitHub

**Hallazgo**, al preparar el repositorio para clonarlo en otro equipo. Revisado mirando solo
cabeceras de columnas y conteos, sin imprimir texto.

- **`triage_limpio_antiguo.csv`**: OID + nota cruda (`texto_original`) de **6.501 triages**,
  versionado desde el commit `d5266c6` (2026-09-18) y **subido a `origin/main`**. 67 notas con
  fecha completa y 7 con números de 5+ cifras.
- **`exploracion.ipynb`**: 8 salidas muestran columnas de notas y 217 líneas con números
  largos (probablemente OID).
- **En el historial, ya borrados del árbol**: `NLP/banco_triage_30.csv` y `_50.csv`,
  `NLP/resultado_*.csv` (7 modelos), `NLP/datos/evaluacion/banco_modelos.csv`,
  `gold_v0_plantilla.csv` (**OID + texto**), `muestra_control.csv` (**OID + `HCTMOTCON`**),
  `pares_juzgados.csv`, `NLP/datos/frases_etiquetadas.csv` (19.587 tramos),
  `NLP/datos/lexicos/corpus_frecuencia.tsv` (frecuencias de palabras de `HCTMOTCON`),
  `NLP/tests/datos/triage_esperado.csv`, `clustering/salidas/clusters.csv` (columna
  `representante`). Y `NLP/datos/lexicos/nombres.txt`, nombres de profesionales de la salud
  de origen no documentado.

**Hecho:** los dos que seguían en el árbol se retiraron del índice (`git rm --cached`; siguen
en el disco de este equipo) y `.gitignore` gana un bloque final **«NUNCA»** para
`mapa_local*.parquet`, `*.duckdb` y `NLP/salidas/nube/`. Va al final porque en `.gitignore`
gana la última regla que coincide.

**Por qué importa más que cualquier otra cosa de esta sesión:** la tabla anonimizada no
protege nada si el mismo repositorio trae miles de notas crudas con OID. **Clonar el
repositorio, hoy, copia ese texto** al equipo que lo clone.

**Pendiente, decisión del propietario** (reescribir un historial publicado es irreversible):
- **A (recomendada):** repositorio privado nuevo con un único commit del árbol limpio, y
  borrar el viejo de GitHub. Se pierde el historial de commits, pero el de decisiones vive
  aquí, que es para lo que existe este archivo.
- **B:** `git filter-repo` sobre esas rutas y `push --force`. Conserva el historial; GitHub
  puede seguir sirviendo los objetos viejos por su hash hasta que su soporte los purgue.

---

## 2026-09-24 — Qué más cambió para poder clonar y seguir en otro equipo

1. **`requirements.txt` rehecho contra los `import` reales** de todo el repositorio, con las
   versiones del `.venv` donde pasan las pruebas. Entran `hdbscan`, `umap-learn`, `pytest`,
   `ipykernel`, `nbformat`, `nbconvert` (se usaban sin estar). Salen 14 paquetes del pipeline
   de reglas retirado el 2026-09-21 (spaCy, medspaCy, SymSpell, LanguageTool…): nadie los
   importa. Anotado cómo instalar `torch` con CUDA para una GPU NVIDIA.
2. **`calendarios/clima_unificado.csv` → `.csv.gz`**, a pedido del propietario. Contenido
   idéntico (2.432 × 68, comprobado con `DataFrame.equals`), 1,31 → 0,46 MB. Cambian solo
   `SALIDA` en `calendarios/clima/clima_unificado.py` y `CLIMA` en `patrones/rutas.py`:
   pandas infiere la compresión por la extensión.
3. **Sacar el CSV de notas y las series agregadas de `.gitignore` quedó BLOQUEADO** por el
   sistema de permisos de Claude Code («Sensitive-Source Provenance»): versionar datos
   derivados de la base clínica es justo lo que ese control detiene. No se intentó por otra
   vía. Lo decide el propietario; las líneas exactas están en `docs/HANDOFF.md`.

---

## 2026-09-24 — Cómo quedó la red de seguridad, y cuatro decisiones de diseño

Construida en `NLP/cadena.py` y cableada en `banco.py` y en `NLP/nube/`. 283 pruebas en
verde, incluido el circuito completo de la nube con un modelo falso.

1. **El disparador es el detector que ya existía, `descarte_falso`**, envuelto como
   `fidelidad.necesita_segunda_pasada`. No se inventó un criterio nuevo: ese detector ya
   estaba validado leyendo lo que marca, y un trámite puro no lo dispara. Se le sumaron los
   sufijos quirúrgicos (`plastia`, `ectomía`, `otomía`, `oscopia`, «biopsia», «operación»)
   como evidencia clínica, porque «turbionoplastia» con errata se descartaba sin disparar.
2. **Si la segunda pasada inventa, gana el descarte.** La salida de la segunda pasada pasa por
   los mismos filtros y los mismos detectores fuertes; si tiene bandera, no se acepta. Por
   qué: un descarte marcado `revisar` lo puede mirar una persona; un motivo inventado sin
   marca se cuenta como verdadero en la serie. Entre los dos errores, el visible.
3. **En la nube son dos viajes, y la decisión de repetir se toma en local.** La máquina
   remota no recibe `fidelidad.py` ni código del proyecto (decisión del 2026-09-23), así que
   no puede decidir sola qué repetir. Al importar, los descartes con evidencia quedan
   `pendiente_segunda` y sus OID van a `segunda_pasada.txt`, que arma el segundo paquete.
   Pasa por el mismo enmascarado y la misma auditoría; ids nuevos y aleatorios.
4. **Un `pendiente_segunda` no se fusiona con `nota_triage`.** Es un paciente fuera de la
   cuenta que todavía se puede recuperar, y la base no tiene forma de decir «provisional».

**Hueco conocido**: `nota_triage` no tiene columna `pasada`. Al fusionar, un `revisar` se
vuelve indistinguible de un descarte normal; hasta decidir esas columnas (junto con
`version_prompt` y `modelo`), la única marca es `revisar.txt`.

---

## 2026-09-24 — Se cierra la fase de CPU

**Decisión del propietario**: dejar de iterar el prompt en la CPU local. Lo que la CPU podía
enseñar ya está medido (techo del 8B, ventaja del 14B, descartes inestables). Seguir ahí es
gastar días en lo que la GPU hace en una hora. Antes de alquilar se construyen:

1. **Una red de seguridad contra descartes falsos**: toda salida «sin motivo clinico» cuya
   nota trae evidencia clínica pasa por una **segunda pasada** con un prompt que no permite
   abstenerse. Si aun así se descarta, queda marcada para revisión humana. No es prompt: es
   un paso más de la cadena, y sirve igual en local y en la nube.
2. `restaurar_antier` también para «el día anterior»; la cirugía con errata
   («turbionoplastia») como evidencia clínica.

Siguen siendo del propietario las cuatro entradas de glosario: «no me baja el azúcar»,
«oídos tapados», «congestionado» e «hipo».

---

## 2026-09-24 — Un error de medición escondía la pérdida de «antier»

Al editar `fidelidad.perdido()` con un script pasado por la terminal, el `\b` de la
expresión regular se escribió como un **carácter invisible de retroceso** (0x08). La
condición nunca se cumplía, y la sonda no podía reportar un «antier» perdido: la guarda
«malestar general desde antier» → «desde el día anterior» salió como «revisar» en vez de
«PERDIÓ». Corregido y verificado (detecta la pérdida y no marca lo correcto). Revisados todos
los `.py` de `NLP/`, `calendarios/`, `clustering/` y `extraccion/`: era el único caso.

**Lección práctica**: las ediciones de código con barras invertidas se hacen con la
herramienta de edición, no con scripts por la terminal, que puede comerse la barra.

**Sonda del 14B, completa (32 notas)**: la sonda cuenta 14/17 fallos arreglados y 1
retroceso; leída, **11/17**, 1 guarda con retroceso y 1 guarda con «antier» perdido. Las
conclusiones de la entrada siguiente no cambian.

---

## 2026-09-24 — Conclusión: el 14B es mejor, pero solo es viable en GPU; el riesgo que queda son los descartes

**Evidencia**: sonda de 32 notas (29 leídas al concluir) con qwen3:14b, prompt suavizado
(`NLP/prompts/v1_7_14b.py`) y filtros, más el duelo de 13 notas sin filtros.

**Fallos arreglados, leídos uno por uno** (la sonda cuenta 14, pero cuenta mal tres):
**14B: 11 de 17. 8B con filtros: ~9-10 de 17.** El 14B gana donde el 8B tocó techo: el
sentido («no me baja el azúcar» → «no presenta disminución de glucemia», correcto), las
negaciones, la duda de la miastenia, «está congestionado», y conserva decimales de
gestación (30,2 semanas).

**Donde la sonda contó como arreglado lo que sigue mal** (lección repetida: leer, no contar):
- «hipo» → «hipotensión»: la bandera desapareció, pero traduce mal.
- «cefalea desde antier» → «desde el día anterior»: eso es ayer. `restaurar_antier` no lo
  ve porque la salida no dice «ayer».
- «me hicieron turbionoplastia en avidanti» → «sin motivo clinico»: **descarte falso** que
  ningún detector ve («turbiono…» con errata no casa con «turbin»).

**Lo que falla en los dos modelos**: «al parecer fractura» afirmado como hecho; «oídos
tapados» (el 14B dice «otorrea»); «hipo». Son de glosario o de revisión humana.

**El riesgo que queda es el descarte falso, y es inestable**: la nota de la hernia discal
salió bien en el duelo y descartada en la sonda, con el mismo modelo y prompt. Es la misma
inestabilidad de la teoría del contexto: en notas límite el modelo adivina. **No se arregla
con más prompt**: hace falta una red de seguridad (segunda pasada o revisión de todo
«sin motivo clinico» cuya nota traiga evidencia clínica).

**Velocidad**: el 14B no cabe en la RAM libre (9,3 GB contra ~7): tarda ~7-8 min en cargar y
20-120 s por nota. **En esta CPU procesar el corpus con el 14B llevaría meses; en GPU, horas.**

**Decisión propuesta** (pendiente del propietario): dejar de iterar en CPU. La corrida va en
GPU, con un modelo de clase 14B o superior (competencia 14B · gemma4 · qwen3:30b-a3b sobre la
sonda y el banco), prompt suavizado, filtros y red de seguridad para los descartes.

---

## 2026-09-24 — Duelo 8B contra 14B en 13 notas: el 14B gana en fidelidad y pierde por abstenerse de más

**Medido**: mismo prompt v1.7, **sin filtros**, 13 notas (fallos persistentes del 8B más
guardas), leídas una por una.

- **El 14B gana 5**: lado no inventado; «no me baja el azúcar» sin invertir el sentido (el 8B
  dijo «azúcar bajo»); la duda de la miastenia conservada (el 8B devolvió «miastronia
  reactiua», texto dañado); las dos negaciones de «presión alta, niega dolor de cabeza, niega
  dolor torácico» intactas (el 8B: «dolor hipertensivo»); «al parecer se fracturó» → «con
  posible fractura».
- **El 8B gana 2, y son del peor tipo para el 14B**: descartes falsos en «me golpeó mi novio»
  y en «remitida por… hernia discal».
- Empates: el trámite bien en los dos; «creo que tengo la presión alta» y «está congestionado»
  mal en los dos; «oídos tapados» y «hipo» mal en los dos (el 14B dijo «otorrea» e
  «hipotensión»).

**Hipótesis**: el bloque «ANTES DE TODO, decide si abstenerte» se endureció vuelta a vuelta
porque el 8B no obedecía. Un modelo que sigue mejor las instrucciones lo cumple **de más**.
El prompt está calibrado para el 8B, no para el 14B.

**Velocidad en esta CPU**: 8B 46,8 s/nota de media (la carga en frío, 311 s); 14B 79,9 s/nota
(carga 489 s). Sin contar la carga, el 14B va a ~1,5-2× el tiempo del 8B.

**El 8B no es determinista cuando duda**: en este duelo «remitido de anserma» salió bien y
«hernia discal» también, cuando en la sonda de la víspera, con el mismo prompt, habían salido
distinto. Confirma el hallazgo de la teoría del contexto: la inestabilidad es señal de
adivinanza.

---

## 2026-09-24 — El duelo de modelos: el 8B llegó a su techo, y el 14B da una primera señal

**Contexto.** El propietario pidió hacer lo posible con el 8B y, al llegar a su límite,
enfrentar un modelo más grande a las notas que el 8B hace mal.

**El techo del 8B, medido en la sonda ampliada** (32 notas: 17 fallos verificados leyendo, 15
guardas), con v1.7 más filtros: **12/17 arreglados, 1 retroceso, 1 pérdida**. Leyendo lo que
queda: un descarte falso que hace el propio modelo («remitida por… hernia discal»), la duda
que se vuelve certeza, y dos guardas dañadas (una negación perdida, una «sospecha de
fractura» perdida). Cada vuelta de prompt que arregla una familia tuerce otra.

**Tres filtros nuevos en `posprocesar()`**, con pruebas:
- `quitar_embarazo_inventado`: la regla 6 nueva («termina con: en gestante de N semanas»)
  arregló el embarazo perdido (3 de 3 notas), pero el modelo la pegó a una nota que no era de
  embarazada. El filtro quita ese sufijo si la nota no afirma embarazo.
- `restaurar_antier`: «antier» → «ayer» es sistemático en el 8B, incluso en una guarda que
  v1.6 hacía bien. **Es el único filtro que reemplaza**, y solo devuelve la palabra exacta de
  la nota. No actúa si la nota dice también «ayer».
- `quitar_identificadores` (privacidad, regla 4): instituciones concretas y «dr + nombre»
  cuando el nombre está en la nota.

**Qué dice la evidencia publicada sobre modelos** (investigación de un agente, con fuentes):
- Dentro de Qwen3, subir de tamaño casi no mejora el seguir instrucciones (IFEval sin
  thinking: 8B 83,0 · 14B 84,8). En el ranking de alucinación de Vectara el 14B sale **peor**
  que el 8B (5,4 % contra 4,8 %). Salvedad: Vectara mide resúmenes en inglés.
- La mejora probable está en **otra familia**: gemma4 (Apache 2.0; 12b cabe en esta CPU;
  26b y 31b para GPU).
- **El modo thinking empeora la abstención** (AbstentionBench, −24 % de media) y a
  temperatura 0 genera repeticiones. Se queda apagado.
- **Ningún benchmark mide lo que falla aquí** (abstenerse ante una nota de trámite): solo el
  banco del proyecto decide.

**Primera señal del 14B, contra la predicción de los benchmarks.** Mismo prompt v1.7 y **sin
filtros**, en 2 notas: resolvió solo el trámite («remitido de anserma» → «sin motivo
clinico») y el lado («me corté la mano con una teja» → «herida cortante en la mano»). El 8B
necesita los filtros para ambas. Dos notas no deciden nada; el duelo de 13 está en curso.

**Costo en esta máquina**: ~49 s/nota contra ~20 del 8B, y ~8 min de carga, porque 9,3 GB no
caben enteros en la RAM libre.

---

## 2026-09-23 — Capa de seguridad para procesar en una GPU de un tercero

**Decisión.** Se construye `NLP/nube/` (lo construyó un agente; lo auditó el orquestador por
separado). A la nube sale **solo** un `id` aleatorio y el prompt con la nota **enmascarada**.
El OID, la fecha, el mapa `id → OID` y el texto original se quedan en local, y el paquete va
**barajado** para no revelar la cronología. El prompt se construye en local, así que la
máquina remota no recibe código ni diccionarios. Los filtros se aplican al volver, contra la
nota original.

**El enmascarado usa las columnas del propio paciente** (documento, nombres y apellidos de ESA
fila, leídos solo en memoria) más patrones: números largos, fechas, correos, URLs, terceros
tras «sr», «dra» o «traído por», y residencia. Los nombres de pila que son palabras comunes
(«Dolores», «Luz») no se enmascaran solos, para no destruir «dolores musculares».

**Evidencia** (muestra real de 300 notas): auditoría del módulo y auditoría independiente.
Solo claves `id` y `prompt`; 0 restos de dígitos, fechas, correos, URLs u OID; orden contra
OID +0,049; ninguna columna sensible guardada, ni siquiera en local; términos clínicos
323 → 323.

**Límite declarado**: un nombre de tercero sin palabra que lo anuncie no se detecta. El
riesgo residual es bajo porque viaja sin OID, sin fecha, sin documento y en orden aleatorio,
pero **la autorización institucional no la da el código**.

---

## 2026-09-23 — Lección operativa: una sola cosa pesada a la vez en esta máquina

A pedido del propietario se lanzaron tres agentes en paralelo. Dos funcionaron bien:
detectores nuevos, 159 pruebas; investigación de modelos. Pero modelo cargado + agente
leyendo datos de la base agotaron los 15,9 GB de RAM: Ollama devolvió error 500 y **las dos
terminales dejaron de responder**. El agente de seguridad se detuvo a mitad de camino, aunque
su código quedó completo y con pruebas.

**Regla práctica**: en paralelo solo trabajo sin modelo y sin cargas grandes de datos. Las
llamadas al modelo, en serie y solas. Con el 14B, **nada más** corriendo.

---

## 2026-09-23 — La teoría del contexto acumulado: descartada, pero encontró un detector

**Hipótesis del propietario**: «entre más procesa, más contexto acumula, más tokens consume y
más alucina; convendría abrir una sesión nueva por nota».

**Por diseño ya es así**: `modelo.generar()` envía solo `model`, `prompt`, `stream` y
`options`. No hay campo `context` ni historial: cada nota empieza de cero, con el prompt más
la nota. Tokens por llamada medidos: 1.471 a 2.209, de una ventana de 4.096 (sin recorte).

**Medido, no supuesto:**

1. **Tasa de fallos según el orden de procesamiento**, en seis tramos: 7,4 % · 8,6 % · 9,3 % ·
   7,8 % · 8,6 % · 7,4 %. Plana: **no empeora con el uso**.
2. **La misma nota guardada (procesada tarde en una corrida), en frío (modelo recién cargado)
   y en caliente: 4 de 5 idénticas.** La quinta, una nota de trámite, dio **tres invenciones
   distintas**: «mordedura en dedo izquierdo», «molestia en hombro derecho por caída desde
   escalera» y «dolor abdominal intenso y persistente desde hace 24 horas».

**Lectura**: no hay acumulación. Pero a temperatura 0 la salida solo es estable cuando el
modelo tiene de dónde sacarla. Cuando adivina, las opciones están casi empatadas y cualquier
diferencia numérica mínima (caché, orden de los cálculos) cambia la palabra elegida. **La
inestabilidad es una señal de alucinación que no depende de ninguna lista de palabras** —
es la idea de los métodos de autoconsistencia—. Candidata a detector para la corrida en
GPU: procesar dos veces las notas sospechosas y marcar las que no coinciden.

**Lo que sí tiene de cierto la intuición**: cada llamada ya carga ~1.400 tokens de reglas
para una nota de diez palabras. Un prompt más corto podría ayudar a un modelo de 8B. Es
hipótesis, sin medir.

---

## 2026-09-23 — Barrido de errores que los detectores no miraban (3.087 notas, v1.6)

**Hallazgo, de solo lectura.** Diez categorías nuevas, sacadas de las propias reglas del
prompt. Los patrones del barrido también disparan en falso, así que cada categoría se
**leyó caso por caso** antes de darla por real.

| Familia real | Notas | Ejemplo | Por qué importa |
|---|---|---|---|
| **Embarazo perdido** (regla 6) | ~39 (1,3 %) | «secundigestante 13 semanas… sangrado vaginal» → «sangrado vaginal» | La población obstétrica es el 12,6 %: perderla mezcla un posible aborto con un sangrado ginecológico |
| **Duda convertida en certeza** (regla 7) | ~15 (0,5 %) | «creo que se me reactivó la miastenia» → «mialgia… relacionada con miastenia» | Además traduce mal: miastenia no es mialgia |
| **Negación perdida o deformada** | ~10 (0,3 %) | «niega traumas» → «**nieta** traumas»; «niega golpe en pie» → «dolor en pie… por trauma» | Invierte el hecho clínico |
| **Duración o lugar cambiados** | ~5 | «desde antier» → «desde ayer»; «detrás del ombligo» → «región lumbar» | Mueve el día de inicio: contamina el análisis de rezagos |
| **Nombres e instituciones en la salida** (regla 4) | ~3 | «…por neurocx dr carlos», «…en avidanti» | Dato identificable en la frase limpia |

**Descartadas tras leerlas**: signos vitales en la salida (casi todas eran «no refiere
otros síntomas»), texto administrativo (mayoría legítima), repetir la nota (notas cortas).
**Coloquialismo sin traducir** (3,1 %): real pero de bajo impacto —«dolor de cabeza» en vez
de «cefalea»—, porque SapBERT-es junta sinónimos (87,7 % como vecino 1).

**El glosario no es el problema**: «nacido» → furúnculo solo se inyecta con «salió» en la
nota, así que «recién nacido» no dispara nada. Está bien diseñado.

**Pendiente de decisión** antes de seguir ajustando: si se aumenta el modelo (el propietario
lo preguntó el 2026-09-23). Estas familias entran a la sonda como fallos nuevos cuando se
retome.

---

## 2026-09-23 — v1.7: el prompt solo no alcanza; dos filtros deterministas lo completan

**Resultado de la sonda (19 notas): 5 de 7 fallos arreglados, 0 retrocesos, 0 pérdidas de
detalle.**

**El balancín, medido.** Cada cambio del prompt que arreglaba una familia torcía otra:

| Vuelta | Cambio | Arregló | Rompió |
|---|---|---|---|
| 3 | Abstenerse va primero | trámite → «sin motivo» | «está muy amarillo» → descartado |
| 4 | Abstención acotada a «cómo está, se siente, se ve» | amarillo | — |
| 5 | Regla 10 repetida al final | nada | (revertida) |
| 6 | «Quitar un detalle es tan malo como agregarlo» | recuperó «mesogastrio», «11 kilos», «3 días» | trámite volvió a inventar |

**Decisión: lo que el modelo no cumple con reglas se aplica en código**, en
`posprocesar()` del candidato, con filtros que **solo quitan** y solo lo que el detector
confirma:

1. **`es_tramite_puro`** → «sin motivo clinico». Exige señal positiva de trámite (remisión,
   derivación, ambulancia…), ninguna evidencia clínica y salida sin base. **Las notas cortas
   quedan fuera a propósito**: «me arde», «está temblando», «está con mocos» son una o dos
   palabras y son motivos reales. Revisadas a mano las 44 notas que borraría del banco:
   **las 44 son trámite con queja inventada**. Proyectado al corpus: ~1.350.
2. **`quitar_lado_inventado` y `quitar_parte_inventada`**. Ninguna redacción de la regla 10
   (ni la de v3/v4 ni una nueva al final del prompt) consiguió que qwen3:8b dejara de
   completar «en ‹parte› ‹lado›». Respetan erratas («derehco»), siglas («IZQ», «MSD») y
   «lado derecho».

**Nueva medida: pérdida de detalle** (`fidelidad.perdido`). Empujar contra la invención
también empuja a recortar; sin medirlo, v1.7 había perdido cantidades y duraciones sin que
ninguna bandera lo viera. Límite: no ve sub-zonas (mesogastrio dentro de abdomen).

**Un modelo más grande no se pudo probar en local**: gemma4:26b pesa 18,6 GB y el equipo
tiene 15,9 GB de RAM. Queda como objetivo del piloto en GPU: comparar 8B con un modelo
grande sobre estas mismas familias.

**Pendientes, y los dos son del glosario, no del prompt:**
- F5: «los oídos se tapan» → «tapón nasal» (traducción equivocada).
- F6: «está congestionado» → «sin motivo clinico». Sin contexto es ambiguo (¿el paciente o
  el servicio?); lo resuelve una entrada del glosario, que es trabajo humano (regla 4).

**Pérdida menor sin medir**: «me mordió un gato callejero» → «mordedura» (pierde el animal).

---

## 2026-09-23 — Ajuste del prompt: el mecanismo de las alucinaciones, medido vuelta a vuelta

**Método, pedido por el propietario**: iterar sobre UNA nota por tipo de fallo, y en cada
cambio comprobar con una sonda fija que lo que ya salía bien no retrocede. El banco completo
se corre una sola vez al final. Herramientas: `NLP/banco.py` (`--oid`, `--sonda`) y
`NLP/fidelidad.py`. El candidato vive en `NLP/prompts/v1_7.py`; **el prompt de producción no se
toca** hasta que el candidato pase.

**Los detectores automáticos encuentran candidatos, no deciden qué es un fallo.** Se midió
tres veces el mismo día:

- Versión 1 de `queja_sin_sintoma` («no encuentro palabra de síntoma»): marcó **408** notas,
  casi todas correctas — «hemorroides», «sonda tapada», «ictericia neonatal», «no veo bien».
  El vocabulario clínico es abierto: no encontrar un síntoma no prueba que no lo haya. Se
  rehízo para exigir la señal POSITIVA de trámite: bajó a 62.
- Erratas de la nota («derehco», «abdoiminal», «iquierda») marcaban como inventado lo que la
  nota sí decía: se compara ahora por parecido (≥ 0,8).
- La sonda elegida automáticamente tenía **4 de 8 «fallos» que eran salidas correctas**
  («presión alta» → «cifras tensionales elevadas», «covid-19»). **Decisión: la sonda se arma a
  mano, con notas leídas**, y esas salidas correctas pasan a ser guardas de regresión.

**`lado_inventado` es el fallo más sistemático**: los 14 de una muestra eran reales. Cuando la
nota nombra una parte del cuerpo sin lado, el modelo le pone uno («me duele la mano» → «mano
derecha», «me duele un testículo» → «izquierdo»).

**El mecanismo de las notas de trámite, desarmado en tres vueltas** sobre «remitido de
anserma» (v1.6: «dolor en el pie derecho por caída desde altura»):

| Vuelta | Cambio | Salida |
|---|---|---|
| 1 | Reglas 8 y 13 reescritas (qué es trámite) | «trauma por mordedura en dedo izquierdo» |
| 2 | Fuera los ejemplos clínicos de las reglas 2, 3 y 5 | «dolor abdominal intenso y persistente desde hace 6 horas» |
| 3 | La decisión de abstenerse va PRIMERO, y el cierre del prompt ya no exige un motivo | **«sin motivo clinico»** |

Lecturas de cada vuelta:

1. **Los ejemplos del prompt se copian** cuando el modelo no tiene nada que decir: «mordedura»
   salía del ejemplo de la regla 3 y «dedo» del de la regla 2. Es la lección de v1 en
   `PROMPT.md`, que seguía viva en v1.6 con tres juegos de ejemplos. Dos de ellos ya estaban
   en el glosario (que los inyecta solo cuando la nota los trae), así que en el prompt sobraban.
2. **Sin ejemplos, el modelo cae en su propia frase comodín.** El problema de fondo era otro.
3. **La causa real: dos reglas que empujaban juntas.** La regla 4 manda borrar las remisiones
   —lo que deja «remitido de anserma» vacía— y el cierre «MOTIVO DE CONSULTA ESTANDARIZADO:»
   exigía un motivo. Nota vacía más motivo exigido es igual a motivo inventado.

**Tiempo por nota**: 19-168 s, contra ~12 s esperados. Ollama atiende una petición a la vez, y
las pruebas hacen fila detrás de la corrida de producción, que además sigue generando salidas
con v1.6 que habrá que rehacer.

---

## 2026-09-23 — Las pruebas pisaban la copia de lectura real

**Hallazgo y arreglo.** El fixture de `NLP/tests/test_almacen.py` reapuntaba `BASE_DATOS` a un
temporal pero no `BASE_VISTA`. Cada corrida de las pruebas —que `CLAUDE.md` pide al abrir toda
sesión— copiaba la base de prueba (2 filas, fecha nula) encima de
`salidas/triage_vista.duckdb`. No se perdió nada (la base principal no se tocaba y la copia se
regenera sola cuando corre NLP), pero cualquiera que leyera la copia después veía datos
falsos. Se detectó porque el armado de los bancos leyó 2 notas en vez de 2.856. Verificado:
tras el arreglo, la copia conserva sus 2.976 notas después de correr la suite.

---

## 2026-09-23 — El modelo inventa una queja cuando la nota no trae ninguna

**Hallazgo**, sobre las 2.856 notas procesadas con el prompt v1.6 y qwen3:8b.

La salida **«dolor abdominal intenso y persistente desde hace 24 horas»** aparece idéntica
**21 veces, desde 20 originales distintos**. Ninguno de los 21 originales menciona «24»,
horas, «intenso», «persistente» **ni el abdomen**. Son notas cortas (mediana 39 caracteres).

El caso ya estaba en el banco de evaluación del 2026-09-18, una sola fila y por eso
invisible: **«ME INDICAN CONSULTAR POR URGENCIAS» → «dolor abdominal intenso y persistente
desde hace 24 horas»**. Cuando la nota es solo un trámite de remisión, el modelo rellena con
una queja por defecto en vez de responder `sin motivo clinico`.

**Causa probable**: la regla 13 del prompt presiona con fuerza en contra de descartar una
nota («descartar una nota que sí traía una dolencia es el peor error que puedes cometer»),
y el único ejemplo de trámite que da la regla 8 («cambio de vendaje») no cubre «me indican
consultar».

**Tamaño**: 0,7 % de las notas. Sobre 93.991 serían ~690 casos de dolor abdominal
inventados, unos 1 por día: suficiente para torcer la serie de esa categoría. Y en el barrido
general, **31 de las 177 salidas que afirman una duración en números (18 %) usan un número
que no está en el original**: el 1,09 % de todas las notas lleva una duración inventada, que
contaminaría directamente el análisis de rezagos.

**Consecuencia**: el prompt v1.6 **no está listo** para procesar el corpus completo, y menos
para pagar por procesarlo. Hace falta una v1.7 que trate las remisiones sin síntoma, y una
comprobación automática de fidelidad que detecte salidas idénticas desde originales
distintos y números que no están en el original.

---

## 2026-09-23 — Antes de pagar GPU: lo único irreversible es la extracción

**Decisión de diseño (recomendación, pendiente de confirmar el propietario).**

El propietario va a contratar GPU para procesar las 93.991 notas y quiere no tener que
repetirlo. **La única etapa cara e irreversible es la extracción de `frase_procesada`.**
Todo lo que viene después —categorías, agrupamiento, series, calendarios, cruce con clima—
cuesta minutos de CPU y se puede cambiar cuantas veces haga falta.

**De ahí sale la regla de diseño: la categoría NO se le pide al modelo en el mismo prompt.**
El propio `NLP/prompt.py` documenta que cualquier palabra clínica escrita en el prompt acaba
apareciendo en las respuestas; meter una lista de categorías («respiratorio», «trauma»…)
contaminaría la frase limpia, que es el activo reutilizable. La categorización va en un paso
aparte, barato, que se puede rehacer sin volver a pagar.

**Lo que hay que congelar antes de pagar:**

1. Prompt v1.7 sin la alucinación de las remisiones, y comprobación de fidelidad automática.
2. `version_prompt` y `modelo` guardados en cada fila de `nota_triage`. Hoy no se guardan:
   una corrida local y una en GPU con otro motor producen filas indistinguibles.
3. Revisión a ciegas de ~150 notas repartidas por los 20 meses, con tasa de error.
4. Orden de la cola por hash del `OID`, para que una corrida cortada sea una muestra útil.
5. Piloto de ~1.000 notas en la GPU: velocidad real, costo, y si las salidas coinciden con
   las locales (la semilla fija no garantiza lo mismo entre motores distintos).
6. **Dónde corre la GPU.** `frase_original` es texto clínico con datos personales —el propio
   prompt enumera nombre, edad, ocupación y residencia entre lo que trae—. Mandarlo a una
   GPU de un tercero lo saca de la institución, y los datos de salud son datos sensibles
   (Ley 1581 de 2012). Hay que resolverlo antes: equipo con GPU dentro de la red del
   hospital, o aprobación institucional con contrato de tratamiento de datos.

---

## 2026-09-23 — El clima unificado se reescribe: seis errores, no uno

**Decisión.** `calendarios/clima/clima_unificado.py` se reescribe entero. **Revierte** la
entrada del 2026-09-22 que proponía como arreglo «quitar `om_precipitation_sum`»: ese era
uno de seis problemas, y arreglar solo ese dejaba los otros cinco.

**Los seis, medidos:**

1. **Rutas rotas.** Las cuatro entradas apuntaban a `calendarios/X.csv`; los archivos viven
   en `calendarios/clima/`. El script no se podía regenerar y fallaba en silencio.
2. **Lluvia de Open-Meteo**: 16.555 mm/año y **r = −0,025** con la estación. Ruido puro.
3. **Planalto empalmado como Manizales**: 12,8 km y ~800 m más abajo. Máxima **+7,39 °C**
   sobre La Nubia en los mismos días. Escalón falso de ago-2020 a sep-2023.
4. **Open-Meteo votaba dos veces** en temperatura.
5. **Mediana de fuentes con sesgos distintos → escalón cada vez que falta una.** Dentro del
   mismo mes, los días sin pluviómetro tenían **+20,05 mm/día** más que los días con él.
   Después del arreglo: **−0,36**. **La versión anterior fabricaba el efecto que el proyecto
   quiere medir**: una «tormenta» cada vez que la estación dejaba de reportar.
6. **Banderas constantes**: `llovio` 98,8 %, `dia_frio` 0,0 %, `dia_calido` 1,4 %.

**El método nuevo**: una referencia por variable, cada otra fuente llevada a su escala mes
por mes (escalado lineal), mediana de las ya corregidas. Detalle en `calendarios/docs/CLIMA.md`.

**Dos decisiones que no son obvias y quedan escritas:**

- **La temperatura media se ancla a la media real de IDEAM**, no a (máx+mín)/2 del METAR,
  que sale **+1,09 °C** por encima: en montaña la curva diaria es asimétrica. Se detectó
  porque la primera versión del arreglo daba 17,74 °C.
- **La lluvia se ancla al pluviómetro, no a NASA**, aunque NASA tenga la serie completa y un
  total anual más cercano al publicado. Lo que decide es la frecuencia: NASA llueve ≥ 1 mm
  el **73 %** de los días, los pluviómetros el **34-39 %**. Con NASA de referencia casi no
  habría días secos, y sin días secos no hay transición seco→lluvioso que detectar. El
  total queda en 1.035 mm/año contra ~2.000 publicados; **no se sabe resolver con estos
  datos y no afecta** porque todo se mide en anomalías relativas al mes.

**Resultado:** temperatura media 16,56 °C, humedad 86,9 %, lluvia bimodal. Banderas: `llovio`
58,5 %, `lluvia_fuerte` 5,1 % (el 5 % más lluvioso de cada mes), `dia_frio` 10,1 % y
`dia_calido` 10,2 % (percentiles del propio mes).

**Límite declarado:** solo el **42,9 %** de los días tiene pluviómetro. El resto usa NASA
escalado, que acierta el mes pero no el día (r = 0,18). Columna `precip_con_estacion`. Para
transiciones día a día, restringir a esos días o usar acumulados de 7 días.

**Corrige una afirmación extendida en el repositorio:** «en Manizales llueve casi siempre,
`llovio` es cierta el 98,8 %». Era un artefacto del dato inflado. Llueve el 58,5 % de los días.

---

## 2026-09-23 — La corrida de NLP va en orden cronológico, y eso es lo que estanca

**Hallazgo.** `NLP/procesar.py:223` llama a `datos.muestra(..., disperso=False)`, y aun con
`disperso=True` el `ORDER BY` por hash solo se aplica si hay `--limite` (`datos.py:38`). Sin
orden explícito, SQL Server devuelve las filas en el orden de la llave: **cronológico**.

Medido el 2026-09-23: **2.706 de 93.991 notas (2,9 %), todas de 15 días de enero de 2025.**
A ~1.300 notas/día, el corpus completo son ~70 días de corrida continua, y **durante semanas
solo habrá enero de 2025**: ningún calendario de motivos es posible hasta el final.

**Propuesta, pendiente de decisión del propietario:** ordenar la cola por hash del `OID`
siempre. El trabajo total es el mismo, pero después de N notas se tiene una muestra
uniforme de los 20 meses en vez de los primeros N días. Con ~6.000 notas (~5 días) ya habría
un calendario completo, fino pero usable.

---

## 2026-09-22 — El nivel de triage mide la decisión del hospital, no la gravedad del paciente

**Corrección de interpretación del propietario.** Es la más importante de la sesión porque
cambia qué se puede concluir de una variable que está al 100 %.

Al ver que el 51,4 % de los triages son «no urgente» o «consulta externa» se leyó que el
hospital recibe consultas que no lo ameritan. **Esa lectura es falsa.** El argumento, que los
datos no pueden dar:

> *«el hospital no está en la capacidad de recibir a cualquier persona e ingresarlo y
> tratarlo, directamente es inviable […] yo he venido con dolores muy fuertes pensando que me
> voy a morir y lo que me dicen es que no es tan grave y que me vaya para la EPS con cita
> prioritaria. Lo más seguro es que me marcan como no urgente o diferido y pasan al
> siguiente.»*

**Lo que el nivel NO dice:** si el paciente tenía razón en venir.
**Lo que el nivel SÍ dice:** si este servicio lo atiende aquí o lo remite.

**Tres consecuencias:**

1. **Todos los registros se tratan como verídicos.** No hay forma de separar quién exageró y
   tampoco hace falta: el conteo mide que alguien sintió la necesidad de consultar, que es
   justo lo que el proyecto quiere predecir.
2. **El nivel es variable de la INSTITUCIÓN, no de la población.** Depende del criterio del
   personal y de la capacidad del servicio. Caracteriza al hospital; no mide la gravedad de
   lo que pasa en la ciudad.
3. **El umbral se mueve con la presión del servicio**, y eso lo vuelve interesante por otra
   vía: un nivel que se endurece puede ser en sí mismo un indicador de saturación.

**De aquí sale la distinción que ahora organiza el análisis:**

| | Qué mide | Variables |
|---|---|---|
| **La población** | Cuánta gente enferma y de qué | conteo, edad, hora |
| **La institución** | Qué decide el hospital con ella | nivel, estancia |

El conteo y la edad son un termómetro de Manizales; el nivel y la estancia, del hospital.
**Para comparar años se usa conteo y edad, nunca nivel.**

---

## 2026-09-22 — La estacionalidad pediátrica: la primera evidencia real de la hipótesis

**Hallazgo**, sobre `salidas/triage_edad.parquet`, 100 % de cobertura desde 2020.

| Banda | Cuota | Amplitud estacional | Pico | Valle |
|---|---|---|---|---|
| 0-4 | 3,1 % | **72,5 %** | **Mayo** | Enero |
| 5-14 | 4,4 % | **43,5 %** | **Mayo** | Diciembre |
| 15-44 | **54,4 %** | 5,1 % | Diciembre | Junio |
| 45-64 | 18,5 % | 8,3 % | Enero | Agosto |
| 65+ | 19,5 % | 6,2 % | Enero | Mayo |

**Las bandas pediátricas tienen entre 7 y 14 veces más amplitud estacional que las adultas**,
y suben juntas de marzo a junio. Es la firma clásica de una temporada respiratoria: los niños
son el indicador adelantado de circulación viral.

**Encaja con la lluvia corregida, pero solo a medias**, y eso es lo interesante: el pico de
lluvia de abril precede en un mes al pico pediátrico de mayo (el rezago que predice el
mecanismo), pero el segundo pico de lluvia de octubre-noviembre **no** tiene pico pediátrico
detrás. Si encajaran los dos, la explicación simple sería estacionalidad compartida. Que
encaje uno obliga a buscar qué distingue abril de octubre.

**Decisión: la vía pediátrica se adelanta y pasa a ser el camino principal.** Prueba la
hipótesis respiratoria con 6,7 años de historia y **sin depender del NLP**.

**Límites declarados**: es el promedio de siete años y puede estar fabricado por el promedio;
la cuota no es el conteo; y el calendario escolar colombiano se solapa con la temporada de
lluvias, así que están confundidos.

**Además**: el 54,4 % de las consultas son de 15-44 años, población laboral — lo que encaja
con el mecanismo del soporte de incapacidad. Y los extremos de edad ganan peso (0-4 de 2,4 %
a 4,0 %; 65+ de 17,9 % a 21,8 %), coherente con que la población adulta de baja complejidad
se esté desviando.

---

## 2026-09-22 — `precip_consenso_mm` está roto: inflado 2,5× y con el ciclo invertido

**Hallazgo grave.** Invalida cifras ya publicadas en `CLAUDE.md` y en `patrones/`.

| Fuente | mm/año | Pico | Valle |
|---|---|---|---|
| Estación IDEAM | 1.403 | Abr | Feb |
| NASA POWER | 1.904 | Abr | Jul |
| **Open-Meteo** | **16.555** | **Jul** | **Ene** |
| **Consenso actual** | **4.393** | **Jun** | Ene |

Manizales recibe ~2.000 mm/año. Open-Meteo reporta **16.555** — más que el lugar más lluvioso
del planeta — y con el ciclo anual invertido.

**El mecanismo exacto:** `clima_unificado.py:197` toma la **mediana** de tres fuentes. Con
tres, Open-Meteo queda fuera de la mediana y no hace daño. Pero **la estación IDEAM solo cubre
el 72,6 % de los días**, y con dos fuentes la mediana es el promedio:

| Días con | Consenso |
|---|---|
| 3 fuentes (72,2 %) | 6,55 mm/día ✔ |
| **2 fuentes (27,6 %)** | **26,40 mm/día** ✘ |

**Causa raíz, escrita en el propio script** (`clima_manizales.py:68`): *«era5_land NO devuelve
precipitation_sum → la precipitación se pide aparte al modelo era5»*. Ese modelo tiene celdas
de ~28 km; en la Cordillera Central promedia el valle del Magdalena con la montaña.

**El arreglo**: quitar `om_precipitation_sum` de la lista `precipitaciones`. Resultado
**1.765 mm/año** y ciclo **bimodal** correcto — picos abril (6,99) y octubre-noviembre
(5,43 / 5,70), valles enero (3,36) y julio (3,52).

**Queda invalidado**: todo lo que dependa de `precip_consenso_mm`, `precip_7d`, `precip_30d`,
`llovio` y `lluvia_fuerte`. Incluida la afirmación de `CLAUDE.md` de que «llovió» es cierta el
98,8 % de los días — es cierta del dato inflado, no del clima de Manizales.

---

## 2026-09-22 — El clima de Manizales, medido

Sobre 2.432 días de `calendarios/clima_unificado.csv`:

| | |
|---|---|
| Temperatura media | 16,5 °C (sd 0,64) |
| Máxima media | 21,2 °C |
| **Días con máxima > 26 °C en 6,7 años** | **0** |
| Días con máxima > 25 °C | 5 (0,21 %) |
| Humedad media | 87,2 % |

**Confirma la observación del propietario: aquí no hace calor, nunca.** En 2.432 días la
máxima no llegó a 26 °C ni una vez. Manizales está a ~2.150 m en la Cordillera Central, junto
al Nevado del Ruiz, y el rango térmico anual completo cabe en cuatro grados.

**Consecuencia**: el mecanismo vectorial necesita calor sostenido y aquí no lo hay. La vía
local queda descartada; quedan los pacientes remitidos de municipios bajos de Caldas y las
epidemias que sí encajan con este clima — respiratorias, virales, fúngicas. Que es la
hipótesis original.

---

## 2026-09-22 — Aclaración: la regla no es «no tocar la base», es «no exponer dato personal»

**Decisión.** Se reescribe la regla 1. Explorar esquema, columnas y datos agregados de SQL
Server está permitido. Lo prohibido es que salga dato personal identificable.

**Por qué.** La regla anterior decía «no conectarse a la base de datos» y eso nunca fue la
intención del propietario. El coste de la mala lectura fue alto: varias sesiones asumieron
que toda la base estaba fuera de alcance y pidieron extracciones que se podían haber hecho
en el momento, o dieron por imposibles análisis que no lo eran.

**El protocolo, que ahora vive en `extraccion/__init__.py`:**

1. Mirar `INFORMATION_SCHEMA.COLUMNS` primero — no devuelve ni una fila de datos.
2. Clasificar las columnas. Lo que no esté en la lista blanca se trata como sensible.
3. Consultar **solo agregados** de columnas no sensibles. Nunca `SELECT *`, nunca una fila
   de paciente, nunca un identificador en la salida.

**Sensibles en `DIM_TRIAGE`**: `GPADOCUME`, `GPANOMBRE`, `GPASEGNOM`, `GPAAPELLI`,
`GPASEGAPE`, `GENMEDICO` y `HCTMOTCON` (texto libre: solo lo lee `NLP/` contra el modelo
local, nunca se imprime en crudo). En `DIM_HCNCONTRDT`: `GENUSUARIO`.

**`HCTEDAD` es el caso intermedio**: se baja, pero **solo agregada en bandas** (0-4, 5-14,
15-44, 45-64, 65+), que es como publica sus datos cualquier boletín epidemiológico.

---

## 2026-09-22 — El criterio de triage derivó desde enero de 2025

**Hallazgo, no decisión.** Y es el más importante de la sesión.

La caída del 23,9 % del volumen desde 2024 **no es toda de demanda**. Medido sobre los
433.620 registros:

| Grupo | 2024 → 2026 anualizado |
|---|---|
| Diferido (III) | **+101,5 %** |
| Urgente (I, II) | **+89,0 %** |
| No urgente (IV) | **−57,4 %** |
| Consulta externa (V) | −47,1 % |
| TOTAL | −23,3 % |

La cuota de «no urgente» pasó del 48,4 % (2024) al 26,9 % (2026); «diferido» subió del
14,3 % al 37,7 %. Las emergencias reales no se duplican en dos años: **cambió dónde se pone
la raya**, no quién llega.

**Cuándo**: deriva progresiva desde **enero de 2025**, con aceleración en
**noviembre-diciembre de 2025**, donde además el volumen cae de golpe (6.431 → 5.161 → 4.572
triages/mes). Un solo evento explicaría las dos cosas y no está en la base.

**Consecuencias:**

1. Un modelo entrenado sobre el total 2024-2026 modela un cambio administrativo.
2. El nivel de urgencia **no es comparable en el tiempo**. Sirve para caracterizar el
   hospital y para separar poblaciones dentro de un periodo corto, no entre periodos.
3. **La ventana con texto (2025-2026) es justo la ventana contaminada.** Cualquier serie
   por motivo hereda el problema.

---

## 2026-09-22 — La estancia tiene tres regímenes de medición

**Hallazgo.** `HCCFECSAL − HCCFECTUR` tiene 91,1 % de cobertura y es **estable en los siete
años** (85-94 %), a diferencia de `HCTMOTCON`. Pero el valor tiene dos saltos bruscos:

| Régimen | Periodo | Media | Mediana |
|---|---|---|---|
| 1 | 2020-01 → 2021-07 | 9,8 min | 3-10 min |
| 2 | 2021-08 → 2026-06 | 55,8 min | 28-60 min |
| 3 | 2026-07 → 2026-09 | 9,9 min | 5-6 min |

Entre julio y agosto de 2021 la mediana salta de 9 a 39 minutos, 4,3× en un mes. Entre junio
y julio de 2026 se desploma de 21 a 5. Un servicio de urgencias no hace eso: cambió qué se
graba en `HCCFECSAL`.

**Decisión:** la variable se usa **solo dentro del régimen 2** — agosto 2021 a junio 2026,
casi cinco años y ~300.000 registros.

**Y de aquí sale un método, no una anécdota:** dos derivas no documentadas encontradas el
mismo día en dos columnas centrales. **Antes de usar cualquier columna, mirar su serie
mensual buscando escalones.**

---

## 2026-09-22 — Qué tipo de hospital es, medido

**Hallazgo.** El nivel de urgencia está al **100 %** en los 433.620 registros desde 2020.

| Nivel | Qué es | Cuota |
|---|---|---|
| IV + V | No urgente + consulta externa | **51,4 %** |
| IIIU | Urgencia | 24,6 % |
| III + III-G | Diferida | 20,5 % |
| I + I-G | **Emergencia** | **0,4 %** (1.463 casos en 6,7 años) |

**Más de la mitad del servicio es no urgente y las emergencias son el 0,4 %.** Esto
**sostiene el mecanismo que el proyecto quiere medir**: la hipótesis de la incapacidad
—«van al hospital, o por lo menos a que les generen la incapacidad del día»— solo es
creíble en un servicio así. Si el 90 % fueran emergencias, habría que replantearla.

Hay además un **12,6 % obstétrico** (niveles con sufijo `-G`), población que no responde al
clima igual que el resto y que conviene poder separar.

---

## 2026-09-22 — `GENDIAGNO1` está vacío: no hay CIE-10 gratis

**Resultado negativo, escrito para que nadie lo persiga otra vez.**

`DIM_TRIAGE.GENDIAGNO1` apunta a `DIM_DIAGNOSTICO`, que tiene 12.427 filas con
`DIACODIGO nvarchar(10)` — es CIE-10. Si estuviera poblada, daría una clasificación clínica
estructurada de cada triage desde 2020 y haría innecesaria buena parte de la cadena
NLP + embedding + clustering.

**No lo está: 0,6 % de cobertura global, y cero en 2022, 2025 y 2026.**

**Cobertura del resto, medida el 2026-09-22:**

| Columna | Cobertura | Desde |
|---|---|---|
| `HCNCLAURGTR` (nivel) | **100 %** | 2020 |
| `HCTEDAD` (edad) | **100 %** | 2020 |
| estancia (`HCCFECSAL`) | **91,1 %** | 2020, estable |
| `HCTMOTCON` (texto) | 82,8 % (2025), 76,2 % (2026) | **solo 2025** |
| `GENDIAGNO1` | **0,6 %** | — |

---

## 2026-09-22 — Corrección de mecanismo: el calor favorece al vector, no el frío

**No es una decisión de código, es una corrección de la hipótesis** y queda escrita porque
cambia qué variable se busca.

*Aedes aegypti* —dengue, chikunguña, zika— necesita **calor**: acelera su ciclo y acorta la
incubación del virus dentro del insecto. La cadena «frío → más insectos» va con el signo
invertido. El ébola no es vectorial ni circula en América; la fiebre amarilla sí aplica pero
es selvática.

**Y Manizales tiene una particularidad que es casi un experimento natural.** A ~2.150 m está
por encima del umbral histórico de transmisión de *Aedes* (~1.800-2.200 m), y —observación
del propietario— la cercanía del nevado mantiene el clima fresco y húmedo aunque haya
temporada seca. **La temperatura aquí no es una variable continua, es un umbral.** Por eso
la vía vectorial local es improbable y lo que queda son dos canales: **pacientes remitidos
de municipios bajos de Caldas**, y las epidemias que sí encajan con el clima de Manizales
—respiratorias, virales, fúngicas—, que son la hipótesis original.

**Ventaja de diseño**: respiratorio y vectorial tienen **firmas opuestas** (frío vs calor;
rezago de días vs semanas; nivel bajo vs alto; edades 0-4/65+ vs 15-44). Si los dos
existen, son separables — y el nivel de urgencia y la edad son el instrumento que los
separa.

---

## 2026-09-22 — El agrupamiento no supervisado no sirve como desenlace

**Decisión.** `clustering/` se rediseña. HDBSCAN deja de ser «la fase 7» y pasa a ser un
candidato más, cuyo único papel declarado será auditar qué hay en el corpus que las
categorías no cubren.

**Por qué.** El agrupamiento devolvió una taxonomía de *redacción*, no de tipo de urgencia.
No se arregla con parámetros: es lo que hace un algoritmo de densidad sobre un espacio de
embeddings, donde la densidad refleja cómo se escribe.

**Evidencia**, sobre `clustering/salidas/temas.csv` (48 temas, corpus de 7.751 notas):

| Observación | Dato |
|---|---|
| Temas 0, 1, 2 y 4 son todos «dolor», separados por redacción | 1.969 notas, **25 % del corpus** |
| El tema 1 mezcla dolor abdominal con dolor torácico | clínicamente inconexos |
| Temas 8, 9 y 11 no son motivos de consulta, son logística y plantilla | 542 notas |
| Lo respiratorio queda partido entre el tema 5 y el 12, mezclado con fiebre e intoxicación | — |
| Estabilidad al quitar el 20 % del corpus | **ARI 0,27–0,30** |
| Ruido | 21,7 % de los textos |

El propio `clustering/temas.py` ya lo había escrito en su bloque «LO QUE ESTO NO ES»: *«si
hacen falta categorías fijas y estables entre corridas, esto no basta, y lo que hace falta es
definir los temas por términos semilla»*.

---

## 2026-09-22 — La elección de método se hace por medición, no a priori

**Decisión.** Se monta un banco de comparación con 7 candidatos, todos detrás de la misma
firma `clasificar(textos, vectores) -> Series[OID -> categoria]`.

**Por qué.** Una sola costura es lo que impide que una fase contamine a la siguiente en
silencio: si todos los métodos entran y salen igual, son intercambiables en un punto y solo
en uno. Y porque el precedente del repositorio dice que la intuición falla — en
`embedding/docs/MODELO.md`, el orden de los 4 modelos probados salió **exactamente inverso a
su tamaño**.

**Los candidatos.** Piso léxico (TF-IDF, el suelo) · HDBSCAN + fusión · K-medias · Aglomerativo ·
Centroides semilla · Logística supervisada · qwen3:8b directo.

**Las métricas.** F1 por categoría contra un banco etiquetado · cobertura · estabilidad (ARI
con submuestra del 80 %) · coste en CPU · y **la que decide: varianza de la serie diaria
resultante que NO explica el calendario**.

La última manda por la regla 8: un método puede clasificar con F1 de 0,9 y producir una serie
que sea una copia del volumen total. Ese método no sirve, y solo esa métrica lo delata.

**Bloqueado por**: no existe el banco de ~300-500 notas etiquetadas a mano. Es trabajo
clínico del propietario y es el cuello de botella real de todo el punto.

---

## 2026-09-22 — El conteo crudo por categoría no se dibuja nunca

**Decisión.** Toda figura por categoría se pinta en **índice de especialización** (lift), y
las casillas con frecuencia esperada < 5 se tapan en gris.

**Por qué.** El volumen total oscila 13,9× a lo largo de la rejilla hora × día. Todas las
categorías arrastran ese ciclo, así que ocho categorías en conteo crudo son ocho copias del
mismo dibujo. El lift convierte «trauma tiene pocos casos de madrugada» —cierto y trivial—
en «trauma es 4 veces más frecuente de lo normal el sábado a las 3», que es un hallazgo.

El gris no es un cero. Un cero es un color de la escala; el gris está fuera de la escala a
propósito, y dice «aquí no hay datos suficientes», que también es un resultado.

**Evidencia.** `clustering/visualizaciones/pruebas.py`, 5/5. La prueba que importa es
`probar_la_cobertura_se_cancela`: una caída del 40 % en la cobertura de `HCTMOTCON` mueve el
lift como mucho 0,0358.

**El supuesto que esto lleva dentro, y que no está medido**: la cobertura se cancela solo si
no depende de la categoría. Si los triages respiratorios tuvieran sistemáticamente más motivo
escrito que los de trauma, el lift de respiratorio saldría inflado y ninguna figura lo
delataría.

---

## 2026-09-22 — La fecha se queda en la base local, y el nivel de triage se le suma

**Decisión.** `nota_triage` conserva `fecha_triage` y **gana `nivel_triage`**. El NLP los
extrae a medida que procesa, igual que hace hoy con la fecha.

**Por qué.** Se evaluó quitarla por redundancia —la fecha está en `DIM_TRIAGE` y se puede
recuperar por `OID`— y se descartó. `nota_triage` no es una tabla transaccional sino un
extracto analítico, y en un extracto la desnormalización es el diseño, no un defecto. El
coste de quitarla era concreto: toda figura y toda serie pasarían a requerir ODBC contra la
base clínica, con lo cual **ningún jurado podría reproducir una sola figura** y la regla 1
dejaría fuera a cualquier sesión de asistente.

**Lo que aporta el nivel de triage**, más allá de completar el registro: es la vía para
contestar qué tipo de hospital es este —cuánto atiende urgencia real y cuánto resuelve cosas
rápidas—, y da un segundo desenlace contrastable **sin depender del texto**.

---

## 2026-09-22 — Primero exploración, y las predicciones no se tocan

**Decisión.** No se construye ningún modelo predictivo hasta haber terminado el exploratorio:
qué variables hay, qué patrones tienen, y qué relaciones reales existen entre tablas y
calendarios. Se avanza de a un hallazgo, no en paralelo.

**Por qué.** El ruido de fondo de la serie diaria es del 12,6 % y los efectos climáticos
publicados sobre urgencias van del 2 % al 10 %: el efecto que se busca es más pequeño que el
ruido contra el que se mide. Sin entender primero el ruido, no hay forma de saber si algo lo
movió.

**Corolario del propietario**, que amplía el diseño original: los calendarios no apuntan solo
al triage, también **se hablan entre sí**. Clima → vectores → epidemia → triages graves es
una cadena donde el triage es el último eslabón, no el único destino.

---

## 2026-09-22 — Las figuras viven en cuadernos, con su lectura escrita al lado

**Decisión.** Se abre `notebooks/`. Un cuaderno por pregunta, con la figura, su
interpretación y sus límites. Una figura suelta no es un resultado.

**Por qué.** Es corrección explícita de `exploracion.ipynb`: las figuras eran buenas y las
conclusiones se escribieron deprisa. La de la celda 14 —«un aumento progresivo a lo largo de
los años, siendo cada vez mayor»— resultó falsa al medirla sobre los seis años completos.

El criterio que queda: lo que no está escrito al lado de la figura se pierde, y lo que se
escribe sin medir se convierte en una conclusión que hay que retirar después.

---

## 2026-09-22 — Tres correcciones a `CLAUDE.md` que salieron de medir

**1. La serie no crece.** Subió hasta 2024 (226,4 triages/día) y lleva dos años cayendo:
199,6 en 2025 y 172,3 en 2026. **−23,9 % desde el pico.** Lo escrito en `exploracion.ipynb`
celda 14 decía lo contrario.

**2. La oscilación horaria es 13,9×, no 7,4×.** El 7,4 era el patrón horario *marginal*. La
casilla conjunta va de lunes 10 h (17,6 triages/hora) a jueves 3 h (1,3).

**3. La amplitud anual real es 19,7 %, no una campana con pico en junio-julio.** Esa forma
venía del cráter de COVID de 2020 (enero 164 → abril 59, −64 %), que hundía el mediodía del
año. Excluyendo 2020: pico junio 202, valle febrero 169.

**Y un hallazgo nuevo: hay interacción hora × día, y es interpretable.** El modelo aditivo en
logs explica el 97,30 % de la rejilla, pero el residuo máximo es 1,69× y no está repartido al
azar: la madrugada (00-05 h) es el **9,61 % del domingo** contra el **5,94 % del jueves**,
una razón de 1,62×. El fin de semana no solo tiene menos volumen, **tiene otra forma** — que
es la primera evidencia, sin haber clasificado una sola nota, de que la composición cambia
con el momento.

---

## 2026-09-21 — `NLP/` pasa de reglas a modelo generativo

*(Entrada retroactiva, reconstruida del historial de git y de `CLAUDE.md`.)*

**Decisión.** Se sustituyen las seis fases de reglas por una llamada a qwen3:8b local. La
carpeta pasa de 87 módulos a 14.

**Por qué.** El corrector ortográfico por palabra no veía el contexto clínico y estropeaba
justo las palabras que importan: convertía `entumida` en `entubada`. El modelo corrige con la
frase entera delante, dentro del mismo paso en que extrae el motivo.

## 2026-09-21 — `embedding/` cambia de modelo y de almacén

**Decisión.** `bge-m3` → **SapBERT-es**. Y el almacén pasa de cuatro archivos posicionales a
DuckDB llaveada por huella del texto.

**Por qué el modelo.** Medición sobre el banco congelado de 787 frases: 87,7 % de sinónimos
como vecino 1 contra 73,3 % de `bge-m3`, AUC respiratorio 0,827 contra 0,744, y 27 minutos de
CPU contra 103.

**Por qué el almacén.** No fue comodidad sino integridad: la llave era la posición de la fila
dentro de un binario sin cabecera, y una desincronización entre archivos era **indetectable**
—se leían bytes válidos de otra frase—. Una clave foránea la hace imposible.

**Consecuencia que sigue viva**: todas las tablas de coherencia calculadas contra el fondo de
`bge-m3` (0,4636) dejaron de valer. El fondo de SapBERT-es es 0,286 con desviación 0,151.
