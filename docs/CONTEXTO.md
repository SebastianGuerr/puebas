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
