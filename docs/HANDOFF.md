# Handoff — dónde está todo ahora

**Este archivo se reescribe.** Describe el presente, no la historia. La historia —qué se
decidió, cuándo y por qué— está en `docs/CONTEXTO.md` y esa solo crece.

Regla 10 de `CLAUDE.md`. Se actualiza **durante** la sesión, cada vez que algo cambia de
estado: una sesión que se corta a la mitad tiene que dejar esto utilizable igual.

**Última actualización: 2026-09-30.**

---

## EN CURSO (2026-09-30): barrido ancho de clima y vigilancia — cuadernos 12 y 13

**Cambio de enfoque del propietario:** el resumen anterior le pareció «relleno». Pide:
- aprovechar **todo** el clima y **todo** el SIVIGILA;
- quedarse con **variables generales de la ciudad**, no con casos puntuales como los colegios.

El método está fijado antes de mirar:
- decisión en `CONTEXTO.md`, entrada «Cambio de enfoque»;
- filas `barrido_clima`, `barrido_vigilancia`, `indices_generales` y `fin_de_sequia` de `variables.csv`.

Cómo se trabaja:
- **Desenlace común:** `notebooks/desenlace.py`. Es el triage semanal sin calendario ni escalones de la red, con estacionalidad, más las series respiratoria, infecciosa y de trauma.
- **Periodos:** descubrir de 2022-03 a 2024-12 y confirmar de 2025-01 a 2026-08 (el SIVIGILA solo hasta 2025-12).
- **Control:** BH con q = 0,10. **Solo cuenta lo que se confirma.**

**Estado: HECHOS, los dos, y ejecutados con 0 errores.** El resultado está en `CONTEXTO.md`, en
la entrada «Resultado de los barridos».

**Clima (cuaderno 12)**
- 693 pruebas, 34 sobreviven a BH y **se confirma 1**: el cambio de radiación a 2 semanas, a la
  misma semana.
- La sequía de 2026 termina en agosto. Los precedentes no anuncian ola.

**Vigilancia (cuaderno 13)**
- 531 pruebas y **0 predictores válidos del total**. La EDA hospitalizada se confirmaba, pero era
  estación compartida.
- La presión respiratoria de la ciudad da **+10,6 % en el respiratorio del hospital a 1 semana**,
  con p = 0,055. Es el mejor candidato.

**Regla de método nueva, desde el 2026-09-30:** antes de dar algo por confirmado, el efecto tiene
que sobrevivir sin estación y sin causalidad inversa (el triage no puede «predecir» la variable
hacia atrás).

**Lectura:** el entorno general actúa sobre la **fracción respiratoria** y se diluye en el total.

**Esperando al propietario:**
1. ¿Se corrige la SE53-2025 del 998 en `sivigila.py`? Hoy solo se anula en memoria.
2. ¿Se programa una instantánea semanal de Power BI?
3. **Cómo se predice:** si se pronostica el total directamente, o el total más la fracción
   respiratoria.

**Siguiente paso:** la discusión de predicción.

---

## En una frase

Se está en **exploración**, no en modelado. El objetivo de esta etapa es saber qué variables
existen, cómo se comportan y qué relaciones reales hay entre las tablas y los calendarios.
**Nada de predicción hasta terminarla.**

---

## EN CURSO (2026-09-28): calendarios externos con fuentes reales — 1/4: vigilancia

**El NLP está en pausa por decisión del propietario.** El orden y el porqué están en
`CONTEXTO.md` («Se aparta el NLP…»): **vigilancia → clima → desastres → eventos**, de uno en uno.

**Encuadre (propietario, 28-09):** esta etapa es de **recolección e inventario**. El desenlace
es el **triage total**; lo respiratorio era solo un ejemplo. El entregable central es
`calendarios/docs/INVENTARIO.md`. Alcance fijado:
- Eventos grandes (Feria) sí; partidos no.
- Catástrofes, de la UNGRD.
- **Sin** calidad del aire.
- El clima actual basta.

**Estado al cierre del 28-09:**
- **Calendario 1 (vigilancia) CERRADO.**
  - 995 y 998: `vigilancia_sivigila.csv.gz`.
  - 14 eventos individuales y 3 marcadores: `vigilancia_sivigila_eventos.csv.gz`, con el script
    `eventos.py`.
  - 2026 por Power BI (`powerbi.py`), con una instantánea en `powerbi/2026-09-28/`.
  - Decisiones y escalones: `CONTEXTO.md`, entrada «Calendario de vigilancia cerrado».
- **Cuaderno `notebooks/06_patrones_exploratorios.ipynb`**, con los primeros patrones contra el
  triage total. Lo más fuerte es institucional; clima, Feria y vigilancias no se distinguen del
  azar. Cinco hipótesis (H1-H5) en `CONTEXTO.md`.
- **Inventario de fuentes de las demás familias** en `calendarios/docs/FUENTES_EXTERNAS.md`.
  Las acciones del propietario están en la decisión #10.
- **Regla nueva:** en el total, un día sin filas es una caída del registro, no cero pacientes.

**HECHO (30-09): `notebooks/11_cruces_del_entorno.ipynb`**, con más cruces de la ciudad.
- **Principio de parsimonia** (propietario): no explorar de más, porque sobreajusta.
- Entra al repertorio: frío y humedad del último mes (+8-10 % de IRA por desviación típica), enero
  como periodo respiratorio, y calendario festivo y lluvia para la calle.
- El resto queda de contexto.
- **Siguiente:** resumen de todo y conversación sobre **cómo hacer las predicciones**.
- Las preguntas al superior (código 9, habilitación, obstetricia) quedan descartadas por ahora.

**HECHO (30-09): perfil del hospital, `notebooks/10_perfil_del_hospital.ipynb`**, con datos
enmascarados.
- Se genera con `python -m extraccion --perfil`: solo agregados y casillas < 5 ocultas. Se
  versionan 9 tablas; `perfil_dx_diario` se queda local.
- **El SES recibe todo y se queda con un tercio** (la mitad hasta 2023).
- Obstetricia crece.
- Hay **series de diagnóstico desde 2020 sin NLP**: respiratorio, diarrea, trauma y embarazo, cada
  una con su época del año.
- Remite por falta de especialidad o de convenio con la EPS.
- Preguntas abiertas en `CONTEXTO.md` (30-09): el código 9, la «no habilitación», la obstetricia.
- **Siguiente natural:** enfrentar los estados del entorno (cuaderno 09) y sus interacciones
  contra el triage total **y** contra las series por diagnóstico, preregistrando antes. La primera
  es frío × virus × mayores sobre respiratorio.

**HECHO (29-09, noche): el entorno conectado consigo mismo**, que es la decisión del propietario.
- `notebooks/09_el_entorno.ipynb` está hecho, sin errores y sin datos del hospital. Trae el
  calendario → violencia, las cadenas clima → IRA con rezago y los estados del entorno (calma,
  frío y húmedo, seco y cálido, decembrino, Feria).
- **Sección 6 hecha**: lo observado contra lo publicado, con la revisión en
  `calendarios/docs/LITERATURA_ENTORNO.md` (86 referencias). Casi todo coincide. Aportes propios:
  quincena → violencia intrafamiliar, y la interacción frío × virus × mayores.
- Datos nuevos: `enso_oni.csv` y `calendario_escolar_manizales.csv`.
- **Después:** enfrentar los estados y sus interacciones contra el hospital (cuaderno 10 o 11;
  el perfil del hospital espera, #13).

**HECHO (29-09, tarde): los cuadernos 01-08 cuentan la historia completa.**
- Índice y hilo en `notebooks/README.md`.
- 01, 02, 03 (nuevo), 05 (convertido), 06, 07 y 08 (nuevo) corren **sin errores**.
- Llevan recuadros de corrección, incluido el del clima.
- **El 08 (los picos)** dejó tres relojes: la noche festiva (baja de día, sube de madrugada, y el
  día siguiente sube), el arranque de año (3 de enero +14 %) y la temporada de mitad de año
  (vacaciones +6,5 %). Fiestas de pueblos lejanos: +2 %.
- **El clima está corregido otra vez** (pluviómetro roto, `pluviometro_fallido`).
- **Siguiente:** fijar las variables definitivas y probarlas fuera de muestra (origen rodante).
  Pendientes del propietario: #10, #11, #12 (CRUE).

**(histórico de la mañana) Los cuadernos cuentan la historia completa** (`CONTEXTO.md`, entrada del 29).
Tres agentes trabajan en paralelo, sin compartir archivos:
- **01 y 02: TERMINADOS**, 38 y 36 celdas, sin errores, con 22 y 24 recuadros de corrección.
  `CLAUDE.md` también corregido: la segunda joroba es a las 14-15 h, los huecos van nombrados y
  la caída se atribuye a Nueva EPS.
  - **Pendiente:** ningún script regenera `triage_diario` ni `triage_horario`. Hay que añadirlos
    a `extraccion --series`.
- **Calendario de fiestas:** un agente está integrando `scratchpad/picos_contexto/fiestas_A.csv`
  (93 filas con URL y los aplazamientos por el terremoto) en
  `calendarios/fiestas_caldas_2020_2026.csv`.
- **03 nuevo** (fuentes externas) y **05 convertido a cuaderno**, con el defecto de marzo de 2024
  arreglado.
- **Investigación de picos**: calendario de fiestas de los municipios de Caldas en
  `calendarios/fiestas_caldas_2020_2026.csv`, y contexto oficial de diciembre, enero y mitad de
  año en `<scratchpad>/picos_contexto/INFORME.md`.

**Después:** el cuaderno **08, los picos**, con las hipótesis ya preregistradas
(`diciembre_noches_festivas`, `fiestas_pueblos`, `mitad_de_anio`); `notebooks/README.md` con el
hilo; y ajustes al 06 y al 07. **Ya medido:** hay dos tipos de pico. Días puntuales en
diciembre-enero (12-15 por cada 100 días) y semanas altas sostenidas en marzo-mayo (mayo: 45 % de
sus semanas).

**NUEVO (28-09, noche): método por mecanismos** (`CONTEXTO.md`, «Cambio de método»).
- Ventanas preregistradas en `patrones/datos/variables.csv`.
- Serie nueva por asegurador: `salidas/triage_entidad.parquet` (`python -m extraccion
  --entidad`), agrupada con `extraccion/entidades.py`, que es un borrador a revisar.
- `notebooks/07_mecanismos.ipynb`: Nueva EPS explica los escalones de nov-2025 y jul-2026; la
  Feria tiene huella propia (SOAT +37 % contra +12 %); seco → lluvioso daba +22 % en 0-4 años (**+13 % ± 15, no significativo, tras corregir el
  pluviómetro el 29-09**) a
  1-2 semanas.
- Las lecturas del 06 están corregidas.
- **Pendiente del propietario (#11):** fechas de suspensión y reanudación de servicios entre el
  SES y Nueva EPS, y revisar la clasificación de entidades.

**Sigue, en orden** (el propietario elige):
1. **Calendario del sistema de salud (H1).** Es la señal más visible y no existe como dato.
   Se arma con la API de noticias de la Alcaldía (8.746 desde 2020) mientras llega el derecho de
   petición a la DTSC (#10c).
2. **Catástrofes de la UNGRD**, que sustituyen `desastres_manizales_2020_2026.csv`.
3. **Eventos sociales grandes**, que sustituyen el calendario manual: Feria con asistencia y
   número de eventos por año, que es lo único que la haría medible.
4. **Tarea semanal que congele el Power BI.** Hoy hay una sola instantánea.
5. **Preregistrar H1-H5** en `patrones/datos/variables.csv` antes de cualquier prueba fuera de
   muestra.

---

**Detalle del calendario 1 (vigilancia):**

| | |
|---|---|
| Código | `calendarios/vigilancia/sivigila.py` (`--sin-descargar` rehace todo desde el caché en ~16 s) |
| Salidas versionables | `calendarios/vigilancia_sivigila.csv.gz` (203.772 filas; Manizales, Caldas y Colombia) y `vigilancia_sivigila_instituciones.csv.gz` (130 instituciones) |
| Crudo | `calendarios/vigilancia/crudo/`, 1,6 GB, **ignorado**: trae datos de quien notifica |
| Porqué | `calendarios/docs/VIGILANCIA.md` |
| Fuentes | `calendarios/docs/FUENTES_VIGILANCIA.md` |
| Cobertura | 995 usable **2015-2025**; 998 de 2011 a 2025 |

**Lo que hay que saber para usarlo** (detalle en `CONTEXTO.md`):
- La proporción IRA / todas las causas **solo se compara dentro de cada año**: el denominador
  tiene escalones de +60 % y +35 %. Para comparar entre años, usar el conteo.
- La IRA 0-4 de la ciudad correlaciona **r = 0,703** con el triage 0-4 del hospital. En
  diferencias semanales baja a 0,18.
- **Trampa de conteo:** el `GROUP BY` de SQL no emite días con cero. Antes de correlacionar,
  rellenar con cero.

- Los eventos individuales (300, 356, 875, 365…) **solo entran al pronóstico con rezago**:
  son parte del desenlace.
- Pendiente: una proporción sobre un panel fijo de instituciones, para quitar los escalones
  del denominador.

Las copias del scratchpad con datos de quien notifica (`d995.xlsx`, `d995_2025.parquet`) se
borraron el 28. El único crudo que queda es el de `crudo/`, ignorado por git.

## Lo más nuevo, y lo que más cambia el plan

**0. (2026-09-28) Validación «sin motivo» medida — ver `CONTEXTO.md`, entrada del 28.**
`python notebooks/05_validacion_sin_motivo.py`. En corto: el motivo **no hace falta** para
predecir ni para probar el mecanismo (la edad lo prueba: frío/humedad → +6-11 % de consultas
0-14 años a 1-2 semanas). Pero **ninguna variable externa actual mejora el pronóstico del
total** fuera de muestra (semanal: estacionalidad 5,23 % de MAPE, con externas 5,64 %), porque
los calendarios son sobre todo calendario disfrazado (vigilancia: 67 % ventanas fijas; el mes
explica 93-100 % de ellas) y las rupturas seca→lluvia son solo 7 semanas. Lo que más mueve el
conteo es institucional (nov-2025, terremoto −21,5 %). **Espera decisión del propietario** (#7).
Fuera del repositorio hay dos cosas útiles:
- **Microdatos SIVIGILA 995** (IRA por institución × semana, Manizales, 2011-2025): es una serie
  de vigilancia real para reemplazar las ventanas fijas. Al cargarlos hay que descartar las
  columnas del notificador, que son dato personal.
- Los **cierres a Nueva EPS**: Avidanti el 21-ago-2025 y Santa Sofía el 1-dic-2025. Son el
  candidato a explicar noviembre-diciembre de 2025.

Detalle y enlaces en `CONTEXTO.md`.

**1. La vía pediátrica pasa a ser el camino principal.** Las bandas 0-4 y 5-14 tienen
**72,5 % y 43,5 % de amplitud estacional** contra 5-8 % de las adultas, con pico en mayo y
valle en enero. Es la firma de una temporada respiratoria, y prueba la hipótesis central
**con 6,7 años y sin depender del NLP**. `salidas/triage_edad.parquet`, 100 % de cobertura.

**2. El clima unificado está ARREGLADO (2026-09-23).** Tenía seis errores, no uno; el peor
fabricaba tormentas cada vez que el pluviómetro dejaba de reportar (+20,05 mm/día falsos,
ahora −0,36). Ya se puede cruzar contra clima. **Límite: solo el 42,9 % de los días tiene
pluviómetro** — para transiciones día a día, `precip_con_estacion` o acumulados de 7 días.
Ver `calendarios/docs/CLIMA.md`.

**3. El nivel de triage mide la decisión del hospital, no la gravedad del paciente.**
Corrección del propietario. Todos los registros son demanda real. De ahí la distinción que
ahora organiza todo: **conteo, edad y hora miden a la población; nivel y estancia miden a la
institución.** Para comparar años, solo los primeros.

**4. Aquí no hace calor, nunca.** 0 días con máxima > 26 °C en 2.432. Descarta la vía
vectorial local y deja la respiratoria, que es la hipótesis original.

---

## EN CURSO (2026-09-24): competencia de modelos ligeros en CPU — Llama 3 y otros

**Qué se busca**: si un modelo local y ligero (Llama 3.x u otro) resuelve lo que qwen3:8b no
pudo —descartes falsos inestables, duda → certeza, negaciones, «no me baja el azúcar»,
«oídos tapados»— con igual o menos recursos. Diseño y porqué: `docs/CONTEXTO.md`, entrada
del 2026-09-24 «Se reabre la competencia de modelos EN CPU».

**Estado (10:55)**: corriendo la competencia en **igualdad de condiciones**, diseño y puntaje
**preregistrados** en `CONTEXTO.md` (bloque «Diseño final»): 63 notas (sonda + muestra nueva
de los bancos), prompt v1.7, modo solo, un modelo a la vez. Orden: llama3.1:8b → qwen3:8b →
tulu3:8b → Llama-3.1-Storm-8B → gemma3:12b → gemma4:12b-it-qat. Un agente revisor escribe la
lista de verificación de las 63 notas antes de juzgar.

**Ya medido (15:40)** — puntaje preregistrado sobre 63 notas, modo solo / con filtros:
**gemma4:12b-it-qat +25 / +26** · qwen3:8b +7 / +15,5 · gemma3:12b +6,5 / +7,5 (0 descartes
falsos) · tulu3:8b −8 / +2,5 · llama3.1:8b −19,5 / −9,5 · llama3.2:3b piso. Detalle y lectura
en `CONTEXTO.md`. **gemma4:12b es el candidato**, con un defecto: 5 descartes falsos.

**Juez ciego: confirmado** (gemma4 mejor en 31 de 43 notas distintas, qwen en 3).

**NUEVA FASE (16:10), decisión del propietario: un prompt propio por modelo**, gana el primero
que cruce la barrera preregistrada (≥ 12/16 notas duras, 0 aciertos dañados, 0 descartes
falsos) y la confirme en una validación que ningún agente de prompt ve. Protocolo completo en
`CONTEXTO.md`, entrada «Cada modelo con su propio prompt». En curso:
- 5 agentes escribiendo la ronda 1 (gemma4, qwen3, gemma3, tulu3, llama3.1) en
  `scratchpad/prompts/<modelo>_r1.py`, con `prompts/REGLAMENTO.md` y `prompts/verificar.py`.
- Validación en construcción: `scratchpad/validacion_privada/` (~49 notas nuevas de 8
  familias, fuera de la muestra de 63).
- Storm 8B corriendo con v1.7; después `cola4.sh` (segunda pasada real y prueba de reuso).
- Cancelada la vuelta de gemma4 con `v1_7_14b.py` (la reemplaza su prompt propio).

**2026-09-25, 08:00 — se reanuda tras un reinicio de la máquina.** La ronda 1 no había guardado
nada (R1_gemma4 quedó vacío). Ollama se actualizó solo a **0.34.4** (ayer 0.34.3): las salidas
a temperatura 0 de ayer podrían no ser idénticas byte a byte. Solo había **5,6 GB libres** (VS
Code, Edge, Brave), así que la cola se reordenó para empezar por lo que cabe: R1_qwen3 →
validación de qwen v1.7 → R1_gemma4 → R1_gemma3 → R1_tulu3 → R1_llama31. **Los ~12B necesitan
~8,5 GB: cerrar navegadores antes de que les toque.**

**Para correr un prompt de ronda** (modo cadena, que es el que decide la barrera):
`python <scratchpad>/comparar.py --modelo <tag> --modo cadena --prompt <scratchpad>/prompts/<m>_r1.py --muestra <scratchpad>/muestra64.csv --salida <scratchpad>/comparacion/<m>_r1.jsonl`

**Herramientas y prompts, versionados** (2026-09-24): `NLP/competencia/` (comparar, segunda,
filtrar, verificar, despachador, REGLAMENTO) y `NLP/prompts/candidatos/<m>_r1.py`. Método y
números: `NLP/docs/COMPETENCIA.md`. **El material con texto clínico no se versiona**: en esta
sesión vive en su scratchpad (muestras, notas enmascaradas, listas de verificación, salidas,
`revision_modelos.md`, `validacion_privada/`); las herramientas del repo lo buscan en
`NLP/salidas/competencia/` (ignorado). Para seguir en otro equipo hay que regenerar la muestra
desde la base local, que solo existe aquí.

---

## EN CURSO: seguir el trabajo desde el equipo de casa (RTX 4060, 8 GB)

**Qué quiere el propietario:** clonar este repositorio en su equipo de casa y seguir desde
allí; que la GPU procese de noche las ~95.000 notas y pruebe prompts y modelos, y traer los
resultados de vuelta. El porqué y lo descartado: `docs/CONTEXTO.md`, 2026-09-24.

**Hecho y certificado (2026-09-24):**
- `NLP/salidas/tabla/notas_triage.csv.gz` — 95.424 notas, 2025-01-08 a 2026-09-24 (el último
  día incompleto: descartarlo al analizar). Seis columnas: `id, fecha, nivel, nivel_nombre,
  edad_banda, nota`. Lo identificable **borrado**. Auditoría: **0 fallos**. Su certificado
  (conteos y sha256 del CSV) es `auditoria.json`, al lado. Se rehace con
  `python -m NLP.nube.tabla --exportar --forzar` (solo aquí: necesita la base).
- `mapa_local.parquet` (`id → OID`) **se queda aquí**. Es lo único que devuelve una fila a su
  triage. Hay dos mapas apartados en la misma carpeta, de una muestra y de una corrida
  fallida: sus CSV nunca salieron, se pueden borrar.
- `requirements.txt` rehecho; `calendarios/clima_unificado.csv.gz` (antes `.csv`).
- Retirados del índice: `triage_limpio_antiguo.csv` y `exploracion.ipynb` (texto real).

**Versionado y en el commit `9c43633`** (2026-09-24): el CSV de notas, su certificado, las
cinco series `salidas/triage_*.parquet`, `clima_unificado.csv.gz` y `.claude/skills/`. El
mapa, las DuckDB y `NLP/salidas/nube/` siguen fuera (bloque «NUNCA» de `.gitignore`).
**El push lo hace el propietario** (a Claude se lo bloquea el sistema de permisos).

**El historial sigue sucio, por decisión del propietario** (se sube al repo actual): un clon
copia las notas crudas de los commits viejos. Decisión #6 abajo, pendiente.

**En el equipo de casa, para arrancar:**
```
git clone https://github.com/SebastianGuerr/puebas.git
cd puebas
python -m venv .venv && .venv\Scripts\activate
pip install torch==2.6.0 --index-url https://download.pytorch.org/whl/cu124
pip install -r requirements.txt
python -m pytest NLP/tests -q
```
y Ollama con `qwen3:8b` (y los candidatos que se quieran probar).

**Falta:**
1. **El código de casa no existe:** leer el CSV, armar el prompt con la versión que se elija
   de `NLP/prompts/`, llamar a Ollama en la GPU, guardar cada resultado con `id`,
   `version_prompt` y `modelo`. Y aquí, el camino de vuelta: resultado → `id` → mapa → OID.
2. **Pasar el arreglo de las fechas con guion a `enmascarar.py`** (hoy solo lo tiene la
   tabla, `_red_de_fechas`): el paquete de la nube tiene el mismo hueco.
3. En el equipo de casa la regla 6 («No hay GPU») no aplica: hay RTX 4060 de 8 GB.

---

## EN CURSO: fase de CPU cerrada; la red de seguridad está construida

**Decisión del propietario (2026-09-24): no se itera más el prompt en la CPU.** Lo que la CPU
podía enseñar ya está medido. Candidatos listos en `NLP/prompts/v1_7.py` (8B) y
`NLP/prompts/v1_7_14b.py` (14B, abstención suavizada); **producción (`NLP/prompt.py`, v1.6)
intacta**. La corrida de producción está **parada**.

**Qué se sabe del modelo** (detalle en `docs/CONTEXTO.md`, entradas del 2026-09-24):
- **El 8B llegó a su techo**: ~9-10/17 fallos de la sonda arreglados, leídos a mano.
- **El 14B es mejor en fidelidad** (duelo 5-2, sonda leída 11/17) pero **no es viable en
  CPU**: 9,3 GB, ~8 min de carga, 20-120 s/nota. En GPU sí.
- **El riesgo que queda son los descartes falsos**, y son **inestables** (la misma nota sale
  bien o descartada según la corrida). No se arreglan con prompt.
- **No hay acumulación de contexto**: cada llamada es independiente; la tasa de fallo es
  plana por orden de procesamiento. La inestabilidad en una nota es señal de que adivina.

**La red de seguridad, construida el 2026-09-24** (`NLP/cadena.py`): toda salida «sin motivo
clinico» cuya nota trae evidencia clínica se repite con `construir_segunda_pasada()`, un
prompt que no admite abstenerse. Si vuelve a descartar o inventa, queda «sin motivo clinico»
**marcada `revisar`**. Integrada en `banco.py` (la sonda marca `<segunda>` / `<revisar>`) y
en `NLP/nube/` como dos viajes (`--exportar --segunda-pasada`; los pendientes **no** se
fusionan con la base). Documentada en `NLP/docs/EVALUACION.md` y `NLP/docs/NUBE.md`.
283 pruebas en verde.

**Medición real de la red**: sonda de 32 notas con qwen3:8b + v1.7 + cadena completa,
**corriendo el 2026-09-24** (salida en el scratchpad de la sesión, `sonda_cadena_8b.txt`).
Si se perdió: `python -m NLP.banco --sonda --prompt NLP/prompts/v1_7.py`, **nada más en
paralelo**.

```
python -m NLP.banco --oid <OID> --prompt NLP/prompts/v1_7.py               una nota
python -m NLP.banco --sonda --prompt NLP/prompts/v1_7.py                   la sonda (32 notas)
python -m NLP.banco --sonda --prompt ... --sin-filtros                     el modelo solo
python -m NLP.duelo --modelos qwen3:8b qwen3:14b --oids ...                mismo prompt, sin filtros
```

**Filtros de `posprocesar()`**, en este orden, todos con pruebas: `es_tramite_puro` →
`quitar_lado_inventado` → `quitar_parte_inventada` → `quitar_embarazo_inventado` →
`restaurar_antier` (también «el día anterior») → `quitar_identificadores`. Solo quitan,
salvo `restaurar_antier`, que devuelve la palabra exacta de la nota.

**Límite duro de esta máquina**: 15,9 GB de RAM. Correr modelo + agentes en paralelo **colgó
la terminal** el 2026-09-23. Una sola cosa pesada a la vez.

---

## Antes de contratar GPU

Recomendada: **RTX PRO 6000 (96 GB) a ~2.088 COP/h** — 33 COP/h más que la 5090 con el triple
de memoria. Costo estimado de todo: decenas de miles de pesos; el piloto de 30 min da la cifra
real antes de comprometerse.

- [x] **Capa de seguridad `NLP/nube/`** (2026-09-23): sale solo `id` aleatorio + prompt con la
      nota enmascarada; OID, fechas y mapa quedan en local; paquete barajado; auditoría que
      falla cerrado. Auditada de forma independiente sobre 300 notas reales: 0 restos, orden
      vs OID +0,049, 323→323 términos clínicos. Ver `NLP/docs/NUBE.md`.
- [x] **Comprobación de fidelidad automática**: 13 detectores fuertes en `fidelidad.py`,
      cada uno validado leyendo lo que marca.
- [x] **Fase de CPU cerrada** (2026-09-24): el 8B llegó a su techo; el 14B es mejor pero
      solo en GPU. El modelo final se decide en la GPU, con la sonda.
- [x] **Red de seguridad contra descartes falsos** (`NLP/cadena.py`), local y nube.
- [ ] **Cuatro entradas de glosario** que son trabajo del propietario: «no me baja el azúcar»,
      «oídos tapados», «congestionado», «hipo».
- [ ] **Banco completo** con el candidato final (~420 llamadas).
- [ ] **Promover a producción**: `NLP/prompt.py` + `procesar.py` llamando a
      `cadena.procesar_nota` + columnas `version_prompt`, `modelo` y `pasada` en
      `nota_triage`. **Sin la columna `pasada`, al fusionar un `revisar` se vuelve un
      descarte normal**: hoy la única marca es `NLP/salidas/nube/revisar.txt`.
- [ ] **Probar que el enmascarado no cambia la salida**: mismas notas enmascaradas y sin
      enmascarar, mismo modelo.
- [ ] **Decisión institucional** sobre procesar datos de salud en infraestructura de un
      tercero. La capa técnica reduce el riesgo; la autorización no la da el código.
- [ ] En la GPU: competencia de 2-3 modelos (el agente de investigación recomienda
      `gemma4:26b` o `gemma4:31b`, `qwen3:32b` como control, y el 8B de referencia) con la
      sonda y el banco, antes de la corrida completa.

---

## Lo que cambió hoy y hay que saber antes de nada

**La regla 1 estaba mal escrita.** No es «no tocar la base», es «no exponer dato personal».
La base **sí** se explora: esquema primero, clasificar columnas, y solo agregados de las no
sensibles. El protocolo está en `extraccion/__init__.py`. Eso desbloqueó todo lo de abajo en
una sola sesión.

**Se encontraron dos derivas de medición no documentadas**, y eso convierte la auditoría en
un paso obligatorio:

1. **El criterio de triage derivó desde enero de 2025.** La caída del 23,9 % del volumen es
   en buena parte reclasificación: «no urgente» −57,4 %, «diferido» +101,5 %.
2. **La estancia tiene tres regímenes de registro** (saltos en 2021-08 y 2026-07). Solo vale
   el régimen 2: agosto 2021 a junio 2026.

**Antes de usar cualquier columna nueva: mirar su serie mensual buscando escalones.**

---

## Qué está corriendo

**La corrida de producción (`NLP.procesar`) está parada** desde el 2026-09-23. Quedó en
~3.087 notas, todas de enero de 2025, **procesadas con v1.6**: habrá que rehacerlas con la
versión final. Al relanzar, hacerlo con la cola **por hash del OID** (hoy procesa en orden
cronológico, `procesar.py:223`, `disperso=False`).

---

## Qué existe y se puede usar hoy

| Archivo | Qué es | Cobertura |
|---|---|---|
| `salidas/triage_diario.parquet` | 2.454 días | 2020-2026 |
| `salidas/triage_horario.parquet` | 55.844 casillas día×hora | 2020-2026 |
| `salidas/triage_nivel.parquet` | 177.864 filas día×hora×nivel | **100 %** desde 2020 |
| `salidas/triage_edad.parquet` | 12.339 filas día×banda | **100 %** desde 2020 |
| `salidas/triage_estancia.parquet` | 2.455 días | 91,1 %, **solo vale régimen 2** |
| `salidas/triage.duckdb` | `nota_triage` + `embedding` | 1,5 % del corpus |
| `NLP/salidas/tabla/notas_triage.csv.gz` | 95.424 notas sin identidad, auditadas | 2025-01-08 a 2026-09-24 |
| `calendarios/clima_unificado.csv.gz` | clima diario unificado (antes `.csv`) | 2020-01-01 a 2026-08-28 |

Los cuatro parquet se regeneran con `python -m extraccion --series`. **Los cuadernos leen de
ahí y no de SQL Server**, que es lo que permite que otra persona reproduzca las figuras.

---

## Lo construido, y cómo se corre

```
python -m extraccion --esquema            columnas y su clasificación. No baja datos
python -m extraccion --cobertura          qué está lleno y desde cuándo
python -m extraccion --series             escribe salidas/*.parquet

python -m clustering.visualizaciones      7 figuras sobre la serie total
python -m clustering.visualizaciones.pruebas    5/5

notebooks/01_la_serie_de_triage.ipynb     25 celdas, 6 figuras, 0 errores
notebooks/02_el_hospital.ipynb            20 celdas, 2 figuras, 0 errores
```

**`clustering/visualizaciones/`** — 994 líneas en 6 archivos, 3 con cálculo. La regla que
lleva dentro: nunca se dibuja el conteo crudo de una categoría, siempre el índice de
especialización, y las casillas con esperado < 5 se tapan en gris.

**`extraccion/`** — 2 archivos. El único módulo que habla con SQL Server. Todas las
consultas llevan `GROUP BY`.

**`notebooks/01_la_serie_de_triage.ipynb`** — ejecutado, 0 errores. Cubre: el volumen y su
caída, el ritmo horario, qué tipo de hospital es, la reclasificación y los regímenes de la
estancia. Cada figura con su lectura y sus límites.

---

## Hallazgos que condicionan lo que venga

1. **La serie no crece: −23,9 % desde el pico de 2024** — y buena parte es reclasificación.
2. **2020 es un cráter de COVID** (−64 % enero→abril). No entra en entrenamiento sin tratarlo aparte.
3. **La hora manda: 13,9× contra 1,57 ×** del día de la semana.
4. **El día tiene dos jorobas** → harán falta 2-3 armónicos de 24 h, no uno.
5. **Hay interacción hora × día**: la madrugada pesa 1,62× más el domingo que el jueves.
6. **51,4 % del hospital es no urgente; las emergencias son el 0,4 %.** Sostiene el
   mecanismo de la incapacidad que el proyecto quiere medir.
7. **12,6 % es obstétrico** (niveles `-G`). Población aparte, conviene separarla.
8. **`GENDIAGNO1` está vacío (0,6 %)**: no hay CIE-10 gratis. No volver a buscarlo.
9. **La ventana con texto (2025-2026) es justo la ventana contaminada** por la deriva.

---

## Esperando decisión del propietario

| # | Qué | Por qué importa |
|---|---|---|
| 1 | **¿Qué pasó en enero y en noviembre de 2025?** ¿Directriz, contrato, auditoría? | Es la única explicación de la deriva que no está en la base |
| 2 | **¿Qué significa `HCCFECSAL`** en cada régimen? | Sin eso la estancia no se interpreta ni dentro del régimen 2 |
| 3 | **La lista de 6-8 categorías clínicas** | Bloquea el banco etiquetado, y el banco bloquea la comparación de métodos |
| 4 | **Reordenar la cola del NLP por hash del OID** (parar y relanzar la corrida) | Muestra uniforme de 20 meses en ~5 días en vez de 70 días en orden cronológico |
| 6 | **Limpiar el historial de git**: repo nuevo con un commit limpio (recomendado) o `git filter-repo` + `push --force`. El 2026-09-24 el propietario eligió subir al repo actual y dejarlo para después | Hoy un clon copia 6.501 notas crudas con OID y otros bancos de notas. Irreversible: lo decide el propietario |
| 7 | **¿Se congela el NLP y se sigue sin motivo?** (2026-09-28, conversación con el superior). La medición apoya congelarlo *para el pronóstico*; lo que se pierde es solo la vía respiratoria adulta. Si se sigue sin motivo, lo que falta no es modelo sino **mejores externas**: series semanales reales de vigilancia (no ventanas fijas), pronóstico de clima, y un calendario **institucional** (EPS, cierres de la red, directrices) | Decide en qué se gasta la GPU y el tiempo de las próximas semanas |
| 14 | ~~Perfil del hospital, decisiones abiertas~~ **RESUELTA el 30-09**: no existe diccionario, se enmascara con supresión < 5 y cruces gruesos, y se versionan las tablas suprimidas (no la diaria). Cuaderno 10 hecho. **Queda preguntar**: el código 9 de causa de ingreso, la «no habilitación» de 2025-2026 y el alza de obstetricia | — |
| 13 | ~~Perfil del hospital: en espera~~ **RESUELTA el 30-09**: el superior dio el contexto y se hizo el cuaderno 10. Texto original: (2026-09-29). El propietario habla con su superior para conseguir documentación de base (servicios, qué se reporta, qué se atiende) antes de construirlo. Tablas candidatas ya vistas en el esquema: `DIM_INGRESO` (causa de ingreso, servicio, cama), `CONTROL_DIAGNOSTICO` (CIE-10) y `SEGUIMIENTO_REMISIONES_DW` (con datos personales: solo agregados) | Define qué factores deberían importarle al SES y qué es el 40 % que sí se atiende |
| 12 | **Informes del CRUE (remisiones), a mano** (2026-09-29): 119 informes mensuales en `saluddecaldas.gov.co/documentos/338/referencia-y-contrarreferencia-caldas/`, con reCAPTCHA en cada descarga. Empezar por diciembre, enero, junio y julio. Derecho de petición propuesto en `calendarios/docs/CONTEXTO_PICOS.md` §4.3 | Es la única vía para medir la hipótesis «lo que el pueblo no atiende termina en Manizales» |
| 11 | **Fechas de la relación SES-Nueva EPS** (2026-09-28): ¿qué pasó a mediados de noviembre de 2025, en marzo de 2026 y en julio de 2026 (suspensión, reanudación, cambio de contrato)? Y revisar `salidas/entidades_clasificadas.csv` | Es la variable de mayor efecto (±40-55 % del triage de Nueva EPS) y se conoce por adelantado |
| 10 | **Acciones de fuentes que solo puede hacer el propietario** (2026-09-28; detalle en `calendarios/docs/FUENTES_EXTERNAS.md`): (a) calidad del aire del CDIAC: la red institucional lo bloquea como «Malicious Websites»; pedir a TI que lo reclasifique, bajarlo desde casa o pedírselo a Corpocaldas; (b) registro en ACLED para la API de protestas; (c) derecho de petición a la DTSC con alertas hospitalarias, novedades REPS de urgencias, hospitalización y UCI, y ocupación, 2020-2026; (d) serie histórica de afiliados por EPS de MinSalud; (e) histórico de medidas de la Supersalud; (f) aceptar o no las API no documentadas (ESPN, SGC); (g) autorizar que se empiece a guardar la foto mensual de la BDUA | Sin (c) no hay calendario del sistema de salud, que es la familia que coincide con las semanas más extremas. (g) pierde historia cada mes |
| 9 | ~~¿El hospital aparece en el SIVIGILA 995?~~ **RESUELTA el 28-09**: es el SES Hospital Universitario de Caldas, `170010010301` «SERVICIOS ESPECIALES DE SALUD». Reporta ~0 IRA; se excluye de las consultas de la ciudad | Si aparece, parte de la correlación r = 0,703 es mecánica (son las mismas consultas) y hay que excluirlo de la serie de la ciudad para usarla como variable externa |
| 8 | **¿Se avisa al INS de que los modelos públicos de sus tableros Power BI por evento exponen columnas identificables?** (2026-09-28) | El proyecto no las usa, pero están expuestas a cualquiera. Es una decisión ética e institucional, no técnica |
| 5 | **Permitir una primera pasada léxica en SQL** sobre `HCTMOTCON`: `CASE WHEN ... LIKE` + `GROUP BY` día; el texto nunca sale del servidor | Calendario de motivos de los 20 meses **hoy**, y es además el «piso léxico» del banco de comparación |

---

## Pendiente de hacer, en orden

1. ~~Arreglar el clima unificado~~ — **hecho el 2026-09-23.**
2. **Cuaderno 03: la estacionalidad pediátrica año a año.** ¿Se repite, o la fabrica el
   promedio de siete años? Y separar lluvia de calendario escolar, que hoy están confundidos.
3. **Cuaderno 04: el ciclo horario con Fourier.** Periodograma y cuántos armónicos hacen falta.
4. **Añadir `nivel_triage` a `nota_triage`** y que `NLP/` lo extraiga, como hace con la
   fecha. **No tocar mientras la corrida esté viva.**
5. **Auditar `HCAREA`** de `HCNCONCOTRI_DW` — posible categoría estructural gratis desde 2020.
   Mirar su serie mensual buscando escalones antes de usarla.
6. **Reescribir `clustering/`** contra la base: retirar `fechas.py`, las anclas posicionales
   y las salidas sueltas.
7. **Borrar los archivos muertos** — lista aprobada, ejecución pendiente. Todos están en git.

---

## Trampas conocidas

- **Cuatro defectos de los filtros de producción** (2026-09-24, tabla en
  `NLP/docs/COMPETENCIA.md`): `quitar_embarazo_inventado` borra un embarazo real;
  `quitar_parte_inventada` borra una parte del cuerpo real si la nota la escribe con errata; el
  filtro de trámites deja «la eps»; la segunda pasada se dispara en trámites puros bien
  descartados. Arreglar con prueba antes de promover ningún prompt.
- **`banco.enmascarar` tapa de más**: ocultó «desaturaciones» y «como urgencia» como si
  fueran nombres. No afecta al modelo (recibe la nota entera) pero sí a quien juzga.

- **En Windows, detener una tarea de fondo NO mata a sus hijos** (2026-09-24). Se detuvo una
  cola `bash cola.sh` y siguieron vivos el bash y su `python`: tres corridas pidieron modelos a
  la vez, Ollama cargó qwen3:8b y llama3.1:8b juntos, la RAM libre bajó a 0,6 GB y cada nota
  pasó de ~80 s a ~3 min. **Para parar una corrida: buscar los PID con
  `Get-CimInstance Win32_Process` y `Stop-Process` a cada uno, y confirmar con `ollama ps`
  que queda un solo modelo.** `cola3.sh` descarga todo modelo cargado antes de empezar otro.

- **Hueco de privacidad, encontrado el 2026-09-24 y SIN arreglar**: la abreviatura **«doc»**
  (doctor) no está en `NLP/banco.py:316` (`enmascarar`), ni en `NLP/fidelidad.py:717`
  (`_TRATO`) ni en `:834` (`quitar_identificadores`). Una nota con «doc + nombre y apellido»
  sale con el nombre visible, y un modelo que lo copie no pasa por el filtro. Caso real en la
  muestra de la competencia. Arreglo: sumar `doc` a las tres, con prueba.

- **DuckDB admite un solo escritor y bloquea a los lectores.** Leer de `triage_vista.duckdb`.
- **`calplot` no está instalado**; el calendario está reimplementado en `figuras.py`.
- **Las salidas de `clustering/salidas/` y `patrones/salidas/` están muertas** (bge-m3,
  corpus de 9.256 notas que ya no existe). No citar esos números.
- **El supuesto del lift no está medido**: se asume que la cobertura de `HCTMOTCON` no
  depende de la categoría.
- **`ipykernel`, `nbformat` y `nbconvert`** ya están en `requirements.txt` (2026-09-24), con
  `hdbscan`, `umap-learn` y `pytest`, que también se usaban sin estar.
- **`ollama pull` puede fallar por DNS** contra `r2.cloudflarestorage.com` en la red local; al
  reintentar funcionó. Alternativa: `ollama pull hf.co/usuario/repo:Q4_K_M` (Hugging Face).
- **`CLAUDE.md` todavía dice «No hay GPU» (regla 6) y «33 pruebas en verde»**: los dos quedaron
  viejos (hoy son 283 pruebas). Se actualizan al cerrar la sesión.
- **La segunda pasada en la nube va a otro archivo de respuestas** (`correr_en_gpu.py
  --salida respuestas_segunda.jsonl`): el mapa del 2º paquete reemplaza al del 1º.
