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

Todo esto es del 2026-09-17, sobre `clustering/salidas/cobertura_diaria.csv` (615 días,
2025-01-08 a 2026-09-14, sin huecos):

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
| Rupturas seca→lluviosa dentro de la ventana con triage | **8** |
| Las mismas rupturas en todo el clima disponible (2020-2026) | **24** |
| Efecto de esas rupturas sobre el residuo, rezagos 0–14 | todos los IC 95 % cruzan cero, anchos de ±10 pp |
| Efectos de clima sobre urgencias publicados en la literatura | 2 % a 10 % |

Lectura: el instrumento actual es más grueso que el efecto que se busca. No es que la
hipótesis sea falsa; es que este diseño no puede distinguirla de nada.

## Los dos cuellos de botella, y los dos son extracciones del propietario

Ninguno se arregla con más modelo ni con más limpieza de texto. Los dos son consultas de
**conteo agregado**, sin texto clínico ni dato identificable:

1. **Triages por día y por hora desde 2020.** Hoy la exposición (clima) tiene seis años de
   historia y el desenlace (triage) solo veinte meses. Eso tira dos tercios de los eventos:
   8 rupturas en vez de 24. Es lo que más compra por lo que menos cuesta.
2. **`LIMITE_REGISTROS = None` en `NLP/procesar.py`.** Hoy hay 9.311 notas procesadas de
   93.991 (7,2 %). La serie respiratoria está en 0,49 notas/día con 61 % de días en cero:
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
  cobertura de `HCTMOTCON` cae ~9 puntos por año y eso mete una tendencia falsa. Ver
  `clustering/fechas.py`.

## Granularidades

| | Estado |
|---|---|
| **Día** | Listo. 615 días completos. Es donde está todo lo medido. |
| **Hora** | **No está en el repositorio.** `HCTFECTRI` la trae y `patrones/salidas/eventos_fechados.parquet` tiene columna `hora`, pero solo para las 6.751 notas muestreadas, no para los ~94.000 triages. Probablemente la granularidad más útil en operación: el patrón intradiario suele ser más fuerte que el día de la semana. |
| **Mes** | No alcanza. 21 meses son 1,7 ciclos anuales; una curva estacional ajustada sobre eso no está estimada, está inventada. |

## Cómo está repartido el trabajo

| Carpeta | Papel |
|---|---|
| `NLP/` | Fase 1. De `HCTMOTCON` de `DIM_TRIAGE` a un motivo limpio por nota en `NLP/salidas/triage_limpio.csv`. Tiene su propia documentación en `NLP/docs/` |
| `embedding/`, `clustering/` | Consumen ese CSV. `clustering/fechas.py` es el puente a la serie diaria por tema, **con denominadores**: contar notas por día da un resultado falso porque entre el paciente y la fila hay tres filtros que se mueven con el tiempo |
| `patrones/` | Fase 8. Poisson condicional por estratos, corrección Benjamini-Hochberg, K-Prototypes, potencia estadística. **No predice**: su `modelos.py` estima asociación ajustada, no acierto |
| `calendarios/` | Las variables externas que explican los picos: festivos de Colombia, clima, eventos y desastres de Manizales, vigilancia en salud de Caldas. **Es el «por qué» del proyecto** |
| `diccionario_bd/` | Exploración del esquema. **Solo el propietario lo ejecuta** |

## Reglas que no se negocian

1. **No conectarse a la base de datos.** Todo lo que hay en SQL Server (`mssql+pyodbc`,
   host `ls-cobra`) es información clínica sensible de pacientes reales. Ni MCP de base de
   datos, ni `pyodbc`, ni consultas exploratorias, ni siquiera de lectura. Si hace falta un
   dato de allí, lo extrae el propietario y lo deja como archivo en el repositorio. Por lo
   mismo, **no ejecutar** `python -m NLP.procesar` ni `python -m clustering --serie`: bajan
   de la base.
2. **`datos/` es lo escrito a mano; `salidas/` es lo que regenera un script.** Si un
   archivo nuevo no encaja en ninguna de las dos, está mal ubicado. Las excepciones
   deliberadas están comentadas una por una en `.gitignore`.
3. **`NLP/datos/frases_etiquetadas.csv` es curado a mano.** No ejecutar
   `python -m NLP.reduccion.frases`: lo regenera y destruye el trabajo humano. Para
   reentrenar: `from NLP.reduccion import frases; frases.entrenar()`.
4. **La documentación vive en `NLP/docs/`, no en los docstrings**, y se actualiza en el
   mismo ítem que cambia el código.
5. **No hay GPU.** Cualquier propuesta que la dé por supuesta está descartada de entrada.
6. **Evidencia antes que afirmación.** Una mejora solo existe si se midió con las mismas
   notas y los mismos artefactos, cambiando únicamente el código. El precedente está en
   `NLP/docs/HANDOFF.md` §1: se reportó una mejora grande que resultó venir de instalar
   artefactos que faltaban, no del trabajo hecho.
7. **Ninguna métrica cuenta como mejora si no se mide sobre la salida final de la cadena.**
   `verification-before-completion` impide afirmar en falso que un comando corrió; no impide
   afirmar en cierto una métrica irrelevante. Retención de terminología no es acierto de
   pronóstico.

## Al abrir sesión

1. **Este archivo entero.** Es el propósito; sin él las decisiones técnicas no se entienden.
2. `NLP/docs/HANDOFF.md` — qué se consiguió, qué se rompió, qué sigue sin resolverse.
3. `NLP/docs/ESTADO.md` completo — estado por ítem, artefactos y problemas conocidos.
4. `python -m NLP.nucleo.requisitos` — todo en OK.
5. `python -m pytest NLP/tests -q` — **38 en verde** en menos de 5 minutos (medido: 31 s).
6. `python -m NLP.evaluacion.paridad_docs --estricto` — 0 faltantes, 0 huérfanas.
7. `git status` antes de tocar nada.

Las habilidades instaladas para este proyecto y por qué están en `.claude/skills/README.md`
(esa carpeta está ignorada por `.gitignore:28` y no se versiona).
