# Handoff — sesión del 2026-09-21

Qué se decidió, qué se hizo, qué quedó sin hacer y con qué hay que tener cuidado.
La sesión fue sobre `embedding/` y, en su segunda mitad, sobre la migración de
`NLP/` y `embedding/` a una base compartida.

---

## En una frase

`embedding/` estaba **caído** —no se podía ni importar— y apuntaba a una columna
retirada. Se rehízo entero: modelo elegido por medición, entrada nueva, y el
almacén pasado a DuckDB con llave por contenido en vez de por posición.

## El estado al empezar

Tres roturas, todas consecuencia de que `NLP/` se reorganizó y `embedding/` no
se enteró:

1. **El paquete no importaba.** `rutas.py` pedía `rutas_nlp.CATALOGO_SINTOMAS`,
   que dejó de existir. `AttributeError` en cualquier `import embedding.*`.
2. **Contrato de entrada roto.** `corpus.py` exigía `texto_embedding`; el CSV
   nuevo trae `texto_optimizado`.
3. **Artefactos huérfanos.** 37 MB de vectores del 16/09 atados a una columna
   que ya no se genera, y con contaminación medida: 98 de 9.142 frases eran
   literalmente antecedentes (`ap: niega; aa: niega`), 803 contenían «niega».

## Las cuatro decisiones

### 1 · El OID se une por llave, no por posición

Era la duda del propietario: cómo mantener el `OID` pegado a su vector sin
meterlo dentro del embedding. La respuesta corta es que ya se hacía con una
tabla aparte; la respuesta larga es que **el diseño que había era frágil por
otro motivo** y por eso se cambió.

La llave era la posición de la fila dentro de `vectores.f32`, un binario plano
sin cabecera. Nada en ese archivo dice a qué texto pertenece cada vector, así
que una desincronización con el índice era **indetectable**: se siguen leyendo
4.096 bytes válidos que son de otra frase.

Ahora la llave es `sha256(texto)[:16]`, derivada del propio dato, y una clave
foránea impide que exista una nota apuntando a una frase ausente. Verificado
contra la base real: los tres intentos de romper la integridad son rechazados
por el motor. Ver [ALMACEN.md](ALMACEN.md).

### 2 · El modelo pasa de `bge-m3` a `SapBERT-es`

Se midieron cuatro candidatos en un factorial 2×2 (clínico/generalista ×
español/multilingüe) sobre 787 frases.

| modelo | vec1 concepto | AUC resp | frases/s |
|---|---|---|---|
| **sapbert_es** | **0,877** | **0,827** | **24,8** |
| sapbert_xlmr | 0,787 | 0,786 | 19,7 |
| bge_m3 *(anterior)* | 0,733 | 0,744 | 6,5 |
| qwen3_06b | 0,656 | 0,674 | 4,4 |
| *piso léxico TF-IDF* | *0,627* | — | — |

Gana en calidad **y** en velocidad, con la cuarta parte de los parámetros del
que sustituye. El orden salió exactamente inverso al tamaño de los modelos.

**Lo que más vale de esta medición es la trampa que destapó.** Una métrica
(`knn5_real`) daba el orden invertido. Se investigó antes de decidir: sus
etiquetas se asignan por coincidencia de subcadena, así que premian el parecido
léxico. La prueba: TF-IDF sin semántica ninguna le ganaba a tres de los cuatro
modelos. Al excluir los vecinos que comparten literal, el orden se invierte y
`sapbert_es` pasa a primero. Detalle en [MODELO.md](MODELO.md).

### 3 · El paquete se reorganizó y es autónomo

Ya no importa `NLP/`. La frontera es de una sola dirección y lo único
compartido es la ruta de la base, una constante en cada `rutas.py`.

### 4 · El almacén es DuckDB

Un archivo, tres tablas, escritura transaccional. Se descartó MongoDB
explícitamente: su búsqueda vectorial solo existe en Atlas, que es nube, y con
notas clínicas reales eso viola la regla 1 de `CLAUDE.md`.

## Qué se hizo

**Nuevos:** `fuente.py` (era `corpus.py`), `comparar_modelos.py`, `docs/` con
`MODELO.md`, `ALMACEN.md`, `DECISIONES.md` y este archivo.

**Reescritos:** `rutas.py`, `modelo.py`, `almacen.py`, `vectorizar.py`,
`centinela.py`, `README.md`.

**Borrados** (siguen en git): `corpus.py`, `estructurar.py`, `extraccion.py`,
`negacion.py`, `texto_embedding.py`, y las salidas viejas.

**Tocado fuera del paquete:** `clustering/corpus.py` (ahora delega en
`almacen.cargar()`; se le quitó toda la maquinaria de leer cuatro archivos
consistentes, que dejó de tener sentido), `clustering/validacion.py` (dos
referencias y el validador de truncamiento), `CLAUDE.md`, `.gitignore`,
`requirements.txt` (`duckdb`, `protobuf`, `sentencepiece`).

## Comprobado, no supuesto

| Qué | Resultado |
|---|---|
| Migración `--importar-csv` | 600 notas, 0 OID repetidos, repetible |
| Cadena completa `python -m embedding.vectorizar` | 596 notas → 479 frases, 28 s |
| Segunda corrida seguida | 0 por vectorizar, no carga el modelo |
| Corrida incremental con notas nuevas | solo vectoriza las que faltan |
| `almacen.cargar()` | (479, 4) textos, (479, 768) vectores, norma 1,0 |
| Vecinos de una frase respiratoria | los 6 primeros son coherentes |
| Las **4** restricciones de integridad | las 4 rechazadas por el motor |
| Guardia de identidad de modelo | rechaza con diagnóstico |
| `python -m embedding.diagnostico` | **11/11** |
| `import` de los 13 módulos tocados | los 13 OK |
| El modelo elegido tras borrar los otros tres | sigue cargando y vectorizando |
| Las pruebas no tocan la base real | verificado: 600 notas y 479 frases intactas |
| `python -m pytest NLP/tests -q` | **29 en verde**, 2,7 s |

## Cuidado con esto

**1 · El banco de frases está congelado, y con razón.**
`embedding/salidas/banco_frases.csv` fija las frases con las que se comparan
modelos, porque el corpus crece mientras se mide. Si se vuelve a congelar (`--congelar`), **hay que volver
a correr los cuatro modelos** o la tabla deja de ser comparable.

**2 · La medición es sobre 787 frases, con 30 respiratorias.** Las diferencias
grandes aguantan; las pequeñas no. Hay que repetirla con el corpus completo.

**3 · Nada de esto mide acierto de pronóstico.** Mide calidad de
representación, que es un insumo. Que la serie respiratoria mejore el
pronóstico es otra medición, aguas abajo, y está **sin hacer**. Es la regla 7
de `CLAUDE.md` y aquí aplica directamente.

**4 · Se perdió un parche sin commitear de `texto_embedding.py`** (20 líneas)
al borrar el archivo. Su contenido útil se recuperó: era el manejo del
centinela `sin motivo clinico`, ahora en `fuente.py:SIN_MOTIVO`. Sin él se
habrían vectorizado 4 notas administrativas como si fueran un cuadro clínico.

**5 · Nunca borrar `salidas/triage.duckdb` a mano.** `frases` se regenera en
minutos; `triage` son horas de generación contra la base clínica y no se puede
rehacer sin volver a consultarla. Para limpiar:
`python -m embedding.vectorizar --rehacer`, que vacía los vectores y deja
`triage` en paz. `python -m NLP.procesar --rehacer` sí borra `triage`, y avisa.

**6 · Contar palabras no es contar tokens, y el repo ya falló en eso dos veces.**
La ventana de 128 se justificó primero con «máximo 60 palabras = 60 tokens»
(eran 120) y después con «máximo 24 palabras» medido sobre 257 filas (con 541 el
máximo real eran 113). Ahora el largo real se guarda en la columna `tokens` del
almacén y `vectorizar.py` avisa en cada corrida.

## Segunda tanda de la misma sesion — la migracion a la base

Con el modelo ya decidido, se cerro `NLP/` y `embedding/`:

**1 · `NLP/` deja de escribir un CSV.** `NLP/procesar.py` ahora llena la tabla
`triage` de `salidas/triage.duckdb` a traves de `NLP/nucleo/almacen.py`. La
reanudacion por OID sigue igual pero es una consulta sobre la clave primaria en
vez de releer el archivo entero. Se confirma cada 10 notas y se **suelta** la
base entre bloques, para que el centinela de `embedding/` pueda entrar mientras
la generacion corre: DuckDB admite un solo escritor.

Cada fila guarda ademas `modelo` y `prompt`. Una corrida larga puede abarcar un
cambio de prompt, y sin esas columnas no habria forma de saber que notas
salieron de que version.

**2 · La base es compartida y vive en la raiz.** `salidas/triage.duckdb`, no
dentro de ningun paquete: `NLP/` escribe `triage`, `embedding/` escribe
`frases` y `triage_frase`. Meterla dentro de uno de los dos haria falsa la
propiedad del otro. `embedding/` sigue sin importar `NLP/` — comparten un
archivo de datos, no codigo.

`triage_frase` gano una segunda clave foranea contra `triage`. Ahora un enlace
no puede existir si la nota no esta o si la frase no esta vectorizada. Las
cuatro violaciones posibles estan verificadas contra la base real.

**3 · Migracion hecha.** Las 600 notas del CSV entraron con
`python -m NLP.procesar --importar-csv`. El CSV se conserva en
`NLP/salidas/` pero **ya no se escribe**; existe solo como origen de esa
importacion, que es repetible.

**4 · Vectorizado el corpus entero disponible.** 596 notas con frase -> 479
frases distintas (19,6% de dedup), 28 s.

**5 · Control de calidad nuevo:** `embedding/diagnostico.py`, 7 pruebas.
Resultado **11/11**, detalle en [CALIDAD.md](CALIDAD.md). Lo importante:

| | SapBERT-es | bge-m3 |
|---|---|---|
| coseno medio entre pares al azar | **0,286** | 0,469 |
| desviacion | **0,151** | 0,087 |
| rango del 98% central | **0,70** | 0,41 |

El espacio dejo de ser el cono estrecho que describia
`clustering/agrupar.py`. El percentil 1 llega a cero: ahora si existen pares de
frases lejanas, que es lo que HDBSCAN necesita.

**6 · Se borraron los tres modelos descartados** de la cache de Hugging Face
(6,5 GB liberados). Los `resultado_*.json` y `docs/MODELO.md` conservan la
evidencia; repetir el bake-off los vuelve a descargar.

**7 · 29 pruebas en verde** (eran 18). Las 11 nuevas son de
`NLP/nucleo/almacen.py` y corren sobre una base temporal, nunca la real.

### Lo que hay que rehacer en `clustering/` y todavia no se hizo

`clustering/agrupar.py` tiene medidas y tablas calculadas **sobre bge-m3**:
el suelo de coherencia `sqrt((1+(n-1)*0,4636)/n)` usa la correlacion de fondo
del modelo viejo. Con 0,286 esos numeros son otros. **No usar esas tablas tal
cual.** La regla que sigue valiendo, y mas que nunca, es no decidir nada con un
umbral absoluto de similitud.

## Tercera pasada — el esquema se poda a dos tablas

El propietario reviso el diseno y objeto tres cosas. Tenia razon en las tres.

**Antes:** cuatro tablas (`triage`, `frases`, `triage_frase`, `meta`) con
`modelo`, `prompt` y `creado` en la tabla de notas.
**Ahora:** dos tablas, nueve columnas, y la fecha real del triage dentro.

```sql
nota_triage  OID (PK) | fecha_triage | frase_original | frase_procesada
embedding    OID (PK, FK) | huella | modelo | tokens | vector FLOAT[768]
```

- **`triage_frase` fuera.** Era una tabla de enlace para no repetir el vector
  de una frase compartida. Ahorraba disco, que sobra (290 MB para el corpus
  completo), a cambio de una tabla y un JOIN de mas en toda consulta. El
  ahorro que si importaba, el de COMPUTO, se conserva: se codifica por frase
  distinta (479 llamadas) y se copia el vector a cada nota (596 filas).
- **`meta` fuera.** La identidad del modelo esta en la columna `modelo` de
  cada fila, que es donde pertenece.
- **`modelo`/`prompt`/`creado` fuera de `nota_triage`.** Un cambio de prompt
  obliga a rehacerlo todo, asi que servian para un caso que no se da; y
  `creado` se confundia con `fecha_triage`, que es la que significa algo.
- **`fecha_triage` dentro.** Es lo que faltaba: `DIM_TRIAGE.HCTFECTRI`, la
  razon de ser del proyecto. `procesar.py` ahora baja TRES columnas de las
  trece de `DIM_TRIAGE`; las otras diez son dato identificable.
- **`huella` se queda**, y es la unica columna no obvia. Detecta un vector
  calculado sobre una frase que ya cambio. Comprobado: se cambio a mano la
  `frase_procesada` de un OID y `vectorizar` recalculo esa fila sola.

**Las 600 notas migradas no tienen fecha** porque el CSV viejo no la traia.
Se completan con `python -m NLP.procesar --fechas`, que baja OID+HCTFECTRI sin
volver a llamar al LLM. **Ese comando esta escrito pero NO ejecutado**: toca la
base clinica y solo lo puede correr el propietario (regla 1 de CLAUDE.md).

Comprobado en esta pasada: 33 pruebas en verde, diagnostico 11/11 sobre el
esquema nuevo, las 3 restricciones de integridad rechazadas por el motor,
segunda corrida sin trabajo pendiente, y deteccion de vector caduco funcionando.

## Cuarta pasada — el fallo de `--fechas`, y lo que aparecio al buscarlo

**El fallo no estaba en `--fechas`.** La extension de DuckDB de VS Code tenia
el archivo con bloqueo exclusivo (PID 27400): DuckDB admite un solo escritor, y
con el archivo tomado no se podia ni leer ni copiar. El comando era correcto.

Arreglado el diagnostico, que era el problema de verdad: `abrir()` reintentaba
8 veces cada 2 s y despues enterraba el error de DuckDB en una traza. Ahora
detecta `already open in`, corta al instante y dice quien la tiene y como
soltarla. En los dos paquetes.

### Lo que aparecio: el cuello de botella 1 estaba resuelto sin saberlo

Con permiso explicito del propietario se consulto `DIM_TRIAGE` (solo `OID` y
`HCTFECTRI`, ni texto ni dato identificable). El resultado cambia el proyecto:

| | |
|---|---|
| Filas en `DIM_TRIAGE` | **433.392** |
| Rango | **2020-01-01 a 2026-09-21** |
| Dias distintos | **2.454**, con 2 huecos |
| Fechas nulas | **0** |
| Media | 176,6 triages/dia |

`CLAUDE.md` decia que el desenlace tenia «solo veinte meses» de historia contra
seis anos de clima, y que conseguir los triages desde 2020 era «lo que mas
compra por lo que menos cuesta». **Ya estaban ahi.** Costo una consulta de 2,4 s.

La restriccion real es otra y mas estrecha: **`HCTMOTCON` solo tiene texto desde
2025** (95.036 de 433.392, todas en 2025-2026). Asi que el conteo TOTAL se puede
modelar desde 2020, pero la serie respiratoria solo desde 2025.

Extraidas y guardadas en `salidas/` (ignoradas por git, como el resto):

- `triage_diario.parquet` — 2.454 filas, dia y conteo
- `triage_horario.parquet` — 55.844 filas, dia x hora y conteo

**La granularidad hora confirma la hipotesis de `CLAUDE.md`:** el patron
intradiario es mucho mas fuerte que el semanal. Pico a las 10 h con 14,0
triages/hora, valle a las 4 h con 1,9 — **7,4x de oscilacion**, contra 1,57x del
dia de la semana (lunes 208,5, domingo 132,7).

### Lo que quedo sin hacer y por que

**Las 600 notas siguen sin `fecha_triage`.** La escritura necesita la base
libre y VS Code no la solto en toda la sesion. En cuanto se cierre esa
conexion, un comando lo resuelve:

```bash
python -m NLP.procesar --fechas
```

No hace falta ningun script temporal: ese comando ya hace exactamente eso
(baja OID+HCTFECTRI y rellena donde falte), y tarda segundos.

**Los dos parquet de series no tienen todavia un script que los regenere.**
Estan en `salidas/`, que por convencion es «lo que regenera un script», y ese
script no existe. Hay que decidir si viven como tablas de la base
(`triage_diario`, `triage_horario`) o como extraccion aparte, y escribirlo.

## Quinta pasada — convivir con el bloqueo de DuckDB

Las 600 fechas ya estan puestas (`sin_fecha: 0`, rango 2025-01-08 a 2025-01-11).
Lo que quedaba era poder trabajar sin desconectar VS Code a mano.

**Lo primero fue medir que permite DuckDB de verdad, entre procesos:**

| A tiene la base | B escritor | B lector |
|---|---|---|
| lectura-escritura | no | **no** |
| solo lectura | no | si |

Un escritor bloquea **tambien a los lectores**. No es configuracion. Con
cualquier visor adjunto al archivo de verdad, `NLP.procesar` no puede escribir.

**Dos piezas nuevas, y cada una resuelve una mitad:**

`NLP/monitor.py` — el seguimiento en vivo. Abre y CIERRA en cada vuelta en vez
de quedarse la conexion, asi que convive con el escritor; si coinciden, se
salta la vuelta. Da avance, ritmo, ETA y las ultimas frases generadas.
Probado corriendo a la vez que un escritor: choco una vez, se recupero solo y
siguio informando.

```bash
python -m NLP.monitor              # cada 15 s
python -m NLP.monitor --frases     # y las ultimas frases
python -m NLP.monitor --una-vez
```

`salidas/triage_vista.duckdb` — una copia que refresca el escritor cada 20 s.
Adjuntando VS Code a ESA y no a la de verdad, **la corrida ya no se cae nunca**.

**Lo que la vista NO da, y conviene saberlo:** mientras el visor la tiene
abierta, Windows no deja sustituir el archivo — medido, `PermissionError`
tanto con `copyfile` como con `replace`. La copia se congela en la foto que
habia al conectarse y avanza cuando el visor se desconecta y vuelve. No hay
forma de que un visor de archivo vea datos que cambian; para eso es el monitor.

**Un error introducido y corregido en la misma pasada:** el mensaje de fallo
rapido por bloqueo se disparaba tambien en el monitor y lo mataba, porque
`SystemExit` no es `Exception` y se le escapaba al `except`. `abrir()` tiene
ahora `diagnosticar=False` para quien sabe convivir con el bloqueo.

## Lo que sigue, por orden

1. **Procesar el corpus completo: `python -m NLP.procesar`.** Hay 600 notas de
   93.991. Es el cuello de botella de todo lo demás: con el corpus completo la
   serie respiratoria pasa de indetectable a ~6,8 notas/día. Mientras corre,
   `python -m embedding.centinela` mantiene los vectores al día sin recargar el
   modelo en cada vuelta.
2. **Volver a correr `python -m embedding.diagnostico`** con el corpus
   completo. La anisotropía y la hubness empeoran al crecer; 479 frases son
   pocas para dar el 11/11 por definitivo.
3. **Repetir el bake-off** (`--congelar` y los cuatro modelos, que hay que
   volver a descargar). Con ~40.000 frases y varios cientos de respiratorias
   los intervalos se estrechan mucho.
4. **La granularidad hora.** `fecha_triage` es un `TIMESTAMP`, así que la hora
   ya está en la base. Es probablemente la granularidad más útil en operación:
   el patrón intradiario suele ser más fuerte que el día de la semana.
5. **Rehacer las medidas de `clustering/agrupar.py`**, que son de bge-m3. Ver
   arriba.
6. **Perseguir la desalineación del generador.** La fila 0 del CSV era
   `OSOSPECHA DE ACEV` → `traumatismo por aplastamiento en dedo izquierdo`. No
   es la misma nota. No se investigó: está fuera de `embedding/`, pero si hay
   desalineación o alucinación sistemática, contamina todo lo de aguas abajo.
7. **Nombrar los clusters.** El lector de catálogo de `extraccion.py`, borrado
   en esta sesión, es la pieza que hace falta. Está en el historial de git.
