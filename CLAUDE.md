# Contexto del proyecto

## El objetivo, en una frase

Responder, para una ventana de tiempo dada (hora, día, semana o mes):

> **¿Va a incrementar la cantidad de solicitudes de triage?**

Con una probabilidad asociada y con las razones que la sostienen. Nada más.

**No** se predice el motivo por el que va a consultar el siguiente paciente. El desenlace
es siempre el **conteo** de solicitudes de triage en la ventana.

## Proyección no es predicción — esta distinción manda sobre todo lo demás

| | |
|---|---|
| **Proyección** — *no es esto* | «Los lunes históricamente hay más gente, luego el lunes habrá más gente.» Sale de una regresión sobre el histórico en un día de trabajo. |
| **Predicción** — *es esto* | «Teniendo en cuenta los factores X e Y, esta semana habrá un crecimiento en las solicitudes de triage con un N % de probabilidad.» |

La diferencia no está en la técnica, está en que la segunda contesta **«por qué»**. No todos
los lunes crecen igual, y entender por qué unos sí y otros no es el trabajo entero. Un modelo
que solo repite el patrón histórico no entendió ni el contexto ni los datos.

**Por eso existen `calendarios/clima/`, `eventos_manizales`, `desastres_manizales` y
`vigilancia_salud`.** No son contexto de relleno: son el «por qué». Una propuesta que los
ignore está contestando la pregunta equivocada, por buenas que sean sus métricas.

Esto es un trabajo de nivel tesis. No se acepta como entrega una regresión sobre el
histórico que diga «el lunes tiende a haber más gente».

## El mecanismo tipo que se quiere capturar

El ejemplo que fija el criterio, en palabras del propietario:

> Si venimos en temporada de sequía y el clima cambia de golpe —se pone más lluvioso, más
> húmedo o más frío—, a la gente le empieza a dar gripa, y las personas con gripa van al
> hospital, o por lo menos a que les generen la incapacidad del día por el triage.

Tres consecuencias de diseño que hay que respetar siempre:

1. **Importa la transición, no el nivel.** «Llueve mucho» no es la hipótesis; «empezó a
   llover después de una seca» sí lo es. Una variable de nivel promedia la transición y la
   borra. Medido el 2026-09-17: las 10 variables preregistradas de
   `patrones/datos/variables.csv` y las 48 columnas de `calendario_diario.parquet` son
   **todas** nivel o acumulado. La variable que codifica esta hipótesis **no existe todavía**.
2. **Hay rezago.** Entre el cambio de clima y la consulta median días de incubación y de
   decisión. El efecto se busca a rezagos de varios días, nunca solo a rezago cero.
3. **Hay un desenlace intermedio observable**: las consultas respiratorias. El mecanismo
   pasa por ahí, y ahí es donde el efecto es grande.

## El papel de cada pieza en esa pregunta

**El modelo de calendario es el CONTROL, no el producto.** Día de la semana, festivos,
puentes, quincena, vacaciones. Sirve para poder decir «este efecto no lo explicaba ya el
calendario», que es lo primero que va a preguntar un jurado. Un control débil infla el
efecto externo; un control sobreajustado se lo come. Calibrarlo bien es parte del argumento
causal, no un rodeo.

**El motivo limpio de `NLP/` es el DESENLACE ESPECÍFICO, no un predictor.** No puede ser
entrada del pronóstico: los motivos de mañana se conocen cuando el paciente ya llegó. Su
valor es otro y es grande: probar «cambio de clima → gripa → consulta» sobre el **volumen
total** es la peor elección estadística posible, por dilución. Si lo respiratorio es el 10 %
de las consultas y una ruptura climática lo sube un 30 %, el total sube un 3 % — invisible
bajo un ruido de fondo del 12,6 %. **La serie respiratoria sola subiría un 30 %.** Ese es el
argumento que justifica la clasificación por tema.

## Lo ya medido — no repetirlo

Todo esto es del 2026-09-17, sobre la serie diaria de 615 días (2025-01-08 a 2026-09-14,
sin huecos). Son propiedades del **conteo total**, no del agrupamiento: el archivo del que
salieron era de `clustering/` pero ningún número de aquí depende de cómo se agrupe nada.
Siguen siendo la vara contra la que se mide cualquier mejora:

| Hecho | Valor |
|---|---|
| Modelo **solo calendario**, origen rodante, 215 días fuera de muestra | MAPE **10,13 %** |
| Base «mismo día de la semana pasada» | MAPE 13,82 % |
| Base media móvil 7 días | MAPE 14,98 % |
| Varianza de `log(triages)` que explica el calendario | 67,8 % |
| Autocorrelación del residuo a 1 día | **+0,423** — lo que sobra no es ruido blanco |
| Desviación típica del residuo diario | **12,6 %** — el ruido contra el que se compite |
| «¿Mañana > media de los últimos 7 días?», acierto fuera de muestra | 77,2 % (base 50,7 %) |
| «¿Mañana entre el 20 % de días más altos?» | 83,3 % (base 76,3 %) — **los picos son lo difícil** |
| ~~Rupturas seca→lluviosa dentro de la ventana con triage~~ | ~~8~~ — **anulado, ver abajo** |
| ~~Las mismas rupturas en todo el clima disponible (2020-2026)~~ | ~~24~~ — **anulado** |
| ~~Efecto de esas rupturas sobre el residuo~~ | **anulado**: se calculó sobre una variable rota |
| Efectos de clima sobre urgencias publicados en la literatura | 2 % a 10 % |


> **El clima unificado se reescribió el 2026-09-23** porque producía resultados falsos por
> seis motivos, el peor de los cuales fabricaba tormentas: dentro del mismo mes, los días sin
> pluviómetro tenían +20,05 mm/día más que los días con él (ahora −0,36). **Queda anulado
> todo lo calculado sobre la versión anterior** — incluidas las filas tachadas de arriba y la
> idea de que `llovio` es cierta el 98,8 % de los días (es el 58,5 %). Solo el 42,9 % de los
> días tiene pluviómetro: para transiciones día a día, usar `precip_con_estacion` o
> acumulados de 7 días. Evidencia y método en `calendarios/docs/CLIMA.md`.


Y esto es del 2026-09-21, sobre las 787 frases del banco congelado de `embedding/`
(`salidas/banco_frases.csv`). Mide **calidad de representación, no acierto de pronóstico**:

| Hecho | Valor |
|---|---|
| Modelo elegido para vectorizar | **SapBERT-es** (126 M par., 768 dim, Apache-2.0) |
| Sinónimos del catálogo que caen como vecino 1 — SapBERT-es | **87,7 %** |
| Lo mismo con `bge-m3`, el modelo anterior | 73,3 % |
| Lo mismo con un piso léxico sin semántica (TF-IDF de n-gramas) | 62,7 % |
| Separación de lo respiratorio (AUC, centroide sin el propio punto) | 0,827 vs 0,744 de `bge-m3` |
| Coste en CPU: proyección a 40.000 frases distintas | **27 min** vs 103 de `bge-m3` |
| Frases truncadas por la ventana de 128 tokens | 1 de 452 (0,22 %) |

Lectura: el orden de los cuatro modelos probados salió **exactamente inverso a su tamaño**.
Aquí no manda la escala sino el ajuste a la tarea. El detalle, y las dos métricas que
resultaron contaminadas por fuga léxica, están en `embedding/docs/MODELO.md`.

Y el control de calidad de la matriz que quedó guardada (479 frases, 596 notas), que es la
compuerta antes de agrupar — `python -m embedding.diagnostico`, **11/11**:

| Hecho | SapBERT-es | bge-m3 (el anterior) |
|---|---|---|
| Coseno medio entre pares de frases al azar | **0,286** | 0,469 |
| Desviación | **0,151** | 0,087 |
| Rango del 98 % central | **0,70** | 0,41 |
| Brecha misma categoría vs distinta | +0,114 | — |
| Asimetría de hubness (problemática por encima de ~2) | 0,77 | — |
| Dimensión efectiva de 768 nominales | 37,3 | — |

Lectura: el espacio dejó de ser un cono estrecho. El percentil 1 llega a cero, o sea que
ahora **sí existen pares de frases lejanas**, que es justo lo que un algoritmo de densidad
necesita. Detalle en `embedding/docs/CALIDAD.md`.

Lectura: el instrumento actual es más grueso que el efecto que se busca. No es que la
hipótesis sea falsa; es que este diseño no puede distinguirla de nada.

## Los dos cuellos de botella, y los dos son extracciones del propietario

Ninguno se arregla con más modelo ni con más limpieza de texto. Los dos son consultas de
**conteo agregado**, sin texto clínico ni dato identificable:

1. ~~**Triages por día y por hora desde 2020.**~~ **RESUELTO el 2026-09-21.** Se midió
   contra `DIM_TRIAGE`: tiene **433.392 triages del 2020-01-01 al 2026-09-21**, 2.454 días
   con solo 2 huecos y **cero fechas nulas**. Las series ya están extraídas en
   `salidas/triage_diario.parquet` y `salidas/triage_horario.parquet`. El desenlace deja de
   tener veinte meses de historia y pasa a tener seis años y medio, igual que el clima.

   La restricción que queda es otra y más estrecha: **`HCTMOTCON` (el texto) solo existe
   desde 2025.** 95.036 notas con texto de las 433.392, todas en 2025–2026. Es decir, el
   conteo total se puede modelar desde 2020, pero la serie respiratoria solo desde 2025.
2. **Procesar el corpus completo: `python -m NLP.procesar` sin `--limite`.** El
   2026-09-21 la fase NLP se rehízo con un modelo generativo (ver abajo) y el CSV empezó de
   cero, así que hoy hay unos cientos de notas de 93.991. Medido sobre el corpus anterior de
   9.311 notas, la serie respiratoria estaba en 0,49 notas/día con 61 % de días en cero:
   indetectable. Con el corpus completo son ~6,8/día. Es densidad, no limpieza.

## Estándar de evidencia

- **Validación de origen rodante siempre.** Nunca validación cruzada aleatoria: en una serie
  temporal el corte aleatorio filtra el futuro y produce métricas falsamente buenas.
- **Toda métrica se reporta contra el control de calendario**, no contra cero y no contra
  una base tonta sola.
- **Las variables se preregistran en `patrones/datos/variables.csv` antes de mirar
  resultados.** Ese archivo se versiona precisamente porque su valor depende de haber sido
  escrito antes. Ajustar la definición de una variable hasta que salga algo es exactamente
  cómo se fabrica un falso positivo.
- **Para predecir de verdad hace falta el *pronóstico* del clima, no la observación.** Un
  modelo evaluado con clima observado mide algo que en operación no se va a tener.
- **La serie por motivo se modela como proporción con denominador, no como conteo.** La
  cobertura de `HCTMOTCON` cae ~9 puntos por año y eso mete una tendencia falsa. Lo mismo
  vale para las figuras: el conteo crudo de una categoría reproduce el ciclo del volumen
  total y no dice nada. Ver `clustering/visualizaciones/datos.py`.

## Granularidades

| | Estado |
|---|---|
| **Día** | **2.454 días, 2020-01-01 a 2026-09-21, 2 huecos** (`salidas/triage_diario.parquet`). Media 176,6 triages/día. El patrón semanal medido: lunes 208,5 → domingo 132,7. |
| **Hora** | **Extraída** (`salidas/triage_horario.parquet`, 55.844 filas día×hora). El patrón intradiario es **mucho** más fuerte que el semanal. Medido sobre la casilla conjunta el 2026-09-22: pico **lunes 10 h con 17,6 triages/hora**, valle **jueves 3 h con 1,3** — **13,9× de oscilación**, contra 1,57× del día de la semana. El día tiene **dos jorobas** (pico 10-11 h, valle 13-14 h, segundo pico 18-19 h): un solo armónico de 24 h no lo describe. |
| **Mes** | Ya alcanza para el conteo total: 6,7 ciclos anuales. Para la serie por motivo no, que sigue empezando en 2025. Excluyendo 2020, la amplitud anual es **19,7 %** (feb 169 → jun 202 triages/día). |

### La serie no crece: subió hasta 2024 y lleva dos años cayendo

Medido el 2026-09-22 sobre los 2.454 días. Es el hecho más grande que se conoce del
desenlace y condiciona todo lo que se modele encima:

| 2020 | 2021 | 2022 | 2023 | **2024** | 2025 | 2026 |
|---|---|---|---|---|---|---|
| 105,7 | 149,3 | 189,6 | 192,4 | **226,4** | 199,6 | 172,3 |

Triages/día. Desde el pico de 2024 la caída acumulada es del **23,9 %**.

Dos consecuencias que no son opcionales:

1. **2020 es un cráter de COVID, no un año flojo**: enero 164 → abril 59, un −64 %. Meterlo
   en el entrenamiento sin tratarlo aparte le enseña al modelo una forma anual que no es
   la del hospital.
2. **La tendencia va en el modelo antes que cualquier variable externa.** Un modelo
   entrenado en 2022-2024 sobre-predice 2026 de forma sistemática, y esa tendencia se lleva
   el crédito de cualquier variable que también tenga tendencia — que es casi cualquiera.

**Por qué cae no se sabe.** Es la pregunta abierta más importante del proyecto: si es
demanda real, es un hallazgo; si es un cambio en cómo se registra, contamina los seis años.

## Cómo está repartido el trabajo

| Carpeta | Papel |
|---|---|
| `NLP/` | Fase 1. De `HCTMOTCON` de `DIM_TRIAGE` a un motivo limpio por nota en la tabla `nota_triage` de `salidas/triage.duckdb`, junto con `HCTFECTRI` (la fecha real del triage). Baja **tres** columnas de las trece de `DIM_TRIAGE`; las otras diez son dato identificable. Lo hace **un modelo local de Ollama** (qwen3:8b) guiado por los 4 diccionarios de `NLP/recursos/`, no un pipeline de reglas. Detrás del modelo, `NLP/cadena.py`: filtros deterministas que quitan lo inventado (`NLP/fidelidad.py`) y una **segunda pasada** contra los descartes falsos. Cómo se mide que no alucina: `NLP/docs/EVALUACION.md`. Documentación en `NLP/README.md` y `NLP/docs/` |
| `embedding/` | Fase 6. Vectoriza `nota_triage.frase_procesada` con **SapBERT-es** y escribe la tabla `embedding` en la misma base, una fila por nota con el `OID` como columna. No agrupa: solo convierte texto en números y mantiene el `OID` unido a su vector sin meterlo dentro. Documentación propia en `embedding/docs/` |
| `clustering/` | **En rediseño desde el 2026-09-22.** El agrupamiento no supervisado por densidad devolvió una taxonomía de *redacción*, no de tipo de urgencia, y no sirve como desenlace. Lo que se decida vive en `docs/CONTEXTO.md`. Lo único nuevo y en pie es `clustering/visualizaciones/`: las figuras de tiempo, que funcionan con cualquier columna categórica y hoy corren sobre la serie total |
| `patrones/` | Fase 8. Poisson condicional por estratos, corrección Benjamini-Hochberg, K-Prototypes, potencia estadística. **No predice**: su `modelos.py` estima asociación ajustada, no acierto. Sus salidas están calculadas sobre los temas retirados y **no valen** |
| `notebooks/` | El trabajo de análisis: una figura sin su lectura escrita al lado no es un resultado. Un cuaderno por pregunta, con su conclusión y sus límites |
| `calendarios/` | Las variables externas que explican los picos: festivos de Colombia, clima, eventos y desastres de Manizales, vigilancia en salud de Caldas. **Es el «por qué» del proyecto** |
| `diccionario_bd/` | Exploración del esquema. **Solo el propietario lo ejecuta** |

**Cambio de arquitectura del 2026-09-21.** `NLP/` era un pipeline de reglas de seis fases
(limpieza, corrección ortográfica, normalización, depuración, reducción, conceptos). Se
sustituyó entero por una llamada a un modelo generativo local: la nota cruda entra tal como
está en la base y sale el motivo de consulta estandarizado. La carpeta pasó de 87 módulos a
14, y lo retirado —fases, `reduccion/`, `reparacion/`, `evaluacion/`, `depuracion/`, y toda
la documentación y las bitácoras de aquel diseño— se borró; sigue en el historial de git.

El motivo del cambio: el corrector por palabra no veía el contexto clínico y estropeaba
justo las palabras que importan (convertía `entumida` en `entubada`). El modelo corrige con
la frase entera delante, dentro del mismo paso en que extrae el motivo.

**Cambio de `embedding/` del 2026-09-21.** Aguas abajo de lo anterior, el paquete quedó
roto —importaba un nombre de `NLP/rutas.py` que dejó de existir— y apuntando a una columna
retirada. Se rehízo entero: modelo elegido por medición (`SapBERT-es` en vez de `bge-m3`),
entrada `texto_optimizado`, y el almacén pasó de cuatro archivos posicionales a una base
DuckDB llaveada por huella del texto. Se retiró la vía de estructuración
(`estructurar.py`, `extraccion.py`, `negacion.py`, `texto_embedding.py`), que el propio
README daba por descartada; sigue en el historial de git, y su lector de catálogo es lo que
hará falta el día de ponerle nombre a cada cluster.

El motivo del cambio de almacén no fue comodidad sino integridad: la llave era la posición
de la fila dentro de un binario sin cabecera, y una desincronización entre archivos era
**indetectable** —se leían bytes válidos de otra frase—. Ahora una clave foránea la hace
imposible. Detalle en `embedding/docs/ALMACEN.md`.

## Reglas que no se negocian

1. **No exponer dato personal. La base sí se puede explorar.** Reescrita el 2026-09-22:
   la versión anterior decía «no conectarse a la base de datos» y eso nunca fue la
   intención. El coste de la mala lectura fue alto — sesiones enteras dieron por imposibles
   análisis que se podían hacer en el momento.

   Lo que está prohibido es que salga **dato personal identificable**. Explorar esquema,
   columnas y agregados, no.

   **El protocolo, en tres pasos y en este orden:**

   1. Mirar el **esquema primero**. `INFORMATION_SCHEMA.COLUMNS` no devuelve ni una fila de
      datos, así que se consulta sin pensarlo.
   2. **Clasificar las columnas.** Lo que no esté en la lista blanca se trata como sensible
      mientras no se haya mirado.
   3. Consultar **solo agregados** de columnas no sensibles. Nunca `SELECT *`, nunca una
      fila de paciente, nunca un identificador en la salida.

   **Sensibles en `DIM_TRIAGE`**: `GPADOCUME` (documento), `GPANOMBRE`, `GPASEGNOM`,
   `GPAAPELLI`, `GPASEGAPE` (nombres), `GENMEDICO` (identifica al médico) y `HCTMOTCON`
   (texto libre: solo lo lee `NLP/` contra el modelo local y **nunca se imprime en crudo**).
   En `DIM_HCNCONTRDT`: `GENUSUARIO`.

   **`HCTEDAD` es el caso intermedio**: la edad no identifica, pero edad + fecha + servicio
   reduce mucho el conjunto de candidatos. Se baja **solo agregada en bandas** (0-4, 5-14,
   15-44, 45-64, 65+), que es como publica cualquier boletín epidemiológico.

   El protocolo vive en código en `extraccion/__init__.py`, que es el **único** módulo del
   repositorio que habla con SQL Server. Las consultas están en `extraccion/__main__.py` y
   todas llevan su `GROUP BY`.

   Sigue en pie **no ejecutar `python -m NLP.procesar`** sin decirlo: no por la conexión,
   sino porque son horas de generación contra el modelo local y bloquea la base DuckDB.
2. **`datos/` es lo escrito a mano; `salidas/` es lo que regenera un script.** Si un
   archivo nuevo no encaja en ninguna de las dos, está mal ubicado. Las excepciones
   deliberadas están comentadas una por una en `.gitignore`. En `NLP/` la carpeta escrita a
   mano se llama `recursos/`, no `datos/`.
3. **`salidas/triage.duckdb` no se borra a mano, aunque esté en `salidas/`.** Es la base
   compartida, y son dos tablas: `NLP/` escribe `nota_triage` (OID, fecha_triage,
   frase_original, frase_procesada) y `embedding/` escribe `embedding` (OID, huella,
   modelo, tokens, vector). Los vectores se rehacen en minutos, pero `nota_triage` son
   **horas de generación contra la base clínica** y no se puede regenerar sin volver a
   consultarla, cosa que solo puede hacer el propietario. Para limpiar:
   `python -m embedding.vectorizar --rehacer` vacía los vectores y deja las notas en paz.
4. **`NLP/recursos/` es trabajo humano y ningún script lo regenera.** Son los cuatro
   diccionarios que le dan contexto al modelo —`siglas.json`, `coloquialismos.json`,
   `lugares.csv`, `terminologia_clinica.json`— y sin ellos el modelo deja de entender el
   habla de Caldas y las abreviaturas del hospital. Cómo ampliarlos: `NLP/docs/RECURSOS.md`.
5. **La documentación vive en la carpeta `docs/` de cada paquete, no en los docstrings**,
   y se actualiza en el mismo ítem que cambia el código. Hoy son `NLP/docs/`,
   `embedding/docs/` y `calendarios/docs/`. Un docstring explica *cómo funciona este módulo*; un documento
   explica *por qué se decidió así y con qué evidencia*, que es lo que no se puede
   reconstruir leyendo el código.
6. **Este equipo no tiene GPU.** Cualquier propuesta que la dé por supuesta aquí está
   descartada de entrada (15,9 GB de RAM y sin tarjeta: una sola cosa pesada a la vez).
   Hay dos vías a una GPU, y en las dos el OID se queda en este equipo: el **equipo de casa
   del propietario** (RTX 4060, 8 GB), que recibe la tabla sin identidad
   (`NLP/docs/TABLA.md`), y una **GPU alquilada**, que recibe solo prompts enmascarados
   (`NLP/docs/NUBE.md`). En el equipo de casa esta regla no aplica. Las dos requieren la
   autorización institucional, que no la da el código.
7. **Evidencia antes que afirmación.** Una mejora solo existe si se midió con las mismas
   notas y los mismos artefactos, cambiando únicamente el código. El precedente: una vez se
   reportó una mejora grande que resultó venir de instalar artefactos que faltaban, no del
   trabajo hecho.
8. **Ninguna métrica cuenta como mejora si no se mide sobre la salida final de la cadena.**
   `verification-before-completion` impide afirmar en falso que un comando corrió; no impide
   afirmar en cierto una métrica irrelevante. Retención de terminología no es acierto de
   pronóstico.
9. **Toda decisión se escribe en `docs/CONTEXTO.md` en el momento en que se toma.** No al
   final, no «si da tiempo»: en el momento. Vale para cualquier sesión, no solo para la que
   abrió el archivo.

   Qué es una decisión: elegir entre dos caminos, descartar algo, fijar un parámetro, medir
   un número que va a sostener una conclusión, o cambiar de opinión sobre algo ya escrito.
   Cada entrada lleva **fecha, qué se decidió, por qué, y con qué evidencia**. El «por qué»
   es el campo que importa: lo que se puede reconstruir leyendo el código no hace falta
   guardarlo, y lo que no, se pierde en cuanto se cierra la sesión.

   **El archivo solo crece.** Una decisión que se revierte no se borra: se añade la nueva
   entrada diciendo que revierte a la anterior y por qué. El historial de por qué se cambió
   de idea vale tanto como la idea, y es lo único que evita volver a discutir lo mismo en
   tres meses.
10. **`docs/HANDOFF.md` se actualiza durante la sesión, no al cerrarla.** Es el estado vivo:
   qué es cierto ahora, qué está a medias, qué sigue, y qué está esperando una decisión del
   propietario. A diferencia de `CONTEXTO.md`, este **se reescribe**: describe el presente,
   no la historia.

   Se toca cada vez que algo cambia de estado, no en una pasada final. Una sesión que se
   corta a la mitad — y se cortan — tiene que dejar el archivo utilizable igual.

   La prueba de que está bien escrito: **una sesión nueva que lea solo `CLAUDE.md`,
   `CONTEXTO.md` y `HANDOFF.md` tiene que poder seguir sin preguntar nada de lo ya hablado.**
   Si hace falta explicarle algo que ya se discutió, es que falta en uno de los tres.

## Al abrir sesión

1. **Este archivo entero.** Es el propósito; sin él las decisiones técnicas no se entienden.
2. **`docs/HANDOFF.md` y `docs/CONTEXTO.md`, en ese orden.** El primero dice dónde se quedó
   todo y qué sigue; el segundo, por qué está así. Leerlos **antes** de proponer nada: casi
   todo lo que parece una buena idea nueva ya se discutió, y ahí está escrito por qué se
   tomó o se descartó. Ver las reglas 9 y 10.
3. `NLP/README.md` — mapa de la carpeta y cómo se ejecuta.
4. `NLP/docs/FLUJO.md` — cómo viaja una nota desde la base hasta el CSV, y por qué.
5. `embedding/docs/HANDOFF.md` — qué se decidió en la última sesión, qué se comprobó y
   qué quedó pendiente. Después, según haga falta: `MODELO.md` (qué modelo y con qué
   evidencia), `ALMACEN.md` (el esquema y sus garantías), `CALIDAD.md` (el estado de
   los vectores) y `DECISIONES.md` (la bitácora de lo descartado).
6. `python -m pytest NLP/tests -q` — **283 en verde** (medido el 2026-09-24: ~21 s).
7. `python -m NLP.procesar --estado` y `python -m embedding.vectorizar --estado` — qué
   hay en la base, sin tocar nada.

**DuckDB admite un solo escritor, y un escritor bloquea también a los lectores** (medido
entre procesos el 2026-09-21). Consecuencias prácticas, que no son opcionales:

- Para seguir una corrida en vivo: `python -m NLP.monitor`. Abre y cierra en cada vuelta,
  así que convive con `NLP.procesar`; si coinciden, se salta la vuelta y sigue.
- Para explorar con SQL desde VS Code: adjuntar `salidas/triage_vista.duckdb`, **nunca**
  `salidas/triage.duckdb`. La vista es una copia que refresca el escritor; con el visor
  encima, la corrida ya no se cae. A cambio la copia se congela mientras esté adjunta, y
  avanza al reconectar — Windows no deja sustituir un archivo abierto.
- Si algo falla con «la tiene tomada», el mensaje dice qué proceso es y cómo soltarlo.
8. `git status` antes de tocar nada.

Si hay que hablar con el modelo, comprobar primero que Ollama responde:
`curl http://127.0.0.1:11434/api/tags`. En Windows lo arranca sola la aplicación de la
bandeja, así que `ollama serve` fallará con «bind: solo se permite un uso de cada dirección
de socket» precisamente cuando ya está funcionando.

Las habilidades instaladas para este proyecto y por qué están en `.claude/skills/README.md`
(esa carpeta está ignorada por `.gitignore:28` y no se versiona).
