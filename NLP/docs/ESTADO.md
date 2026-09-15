# Estado del plan

Última actualización: 2026-09-15 (sesión de planificación). Actualizar este archivo al
reclamar y al cerrar cada ítem.

## 1. Lectura obligatoria al abrir una sesión

1. `PLAN.md` §0, §2, §3 y §4 (cómo trabajar), §6 (qué no romper).
2. Este archivo completo.
3. `python -m NLP.nucleo.requisitos` — debe mostrar todo en OK.
4. `git status` — ver §2 antes de tocar nada.

## 2. Estado del repositorio al cierre de la sesión del 2026-09-15

**Cambios sin commit** (pendiente E0.1; el commit lo autoriza el propietario):

| Archivo | Cambio |
|---|---|
| `NLP/nucleo/requisitos.py` | nuevo: verificación de artefactos; detiene `procesar.py` si falta uno exigido |
| `NLP/fase2_ortografia/coherencia.py` | nuevo: fase 2b, deshace correcciones incoherentes con la nota |
| `NLP/reparacion/__init__.py`, `reparar.py`, `comparacion.py` | nuevo: reprocesa un CSV existente y clasifica cada nota |
| `NLP/docs/*` | nuevo: esta documentación |
| `NLP/procesar.py` | fase 2b integrada; `requisitos.exigir()` al inicio; `VERSION_CORRECTOR = "4-con-spacy-y-coherencia"`; resumen de reversiones |
| `NLP/reduccion/reduccion.py` | freno por densidad clínica en `_quitar_clasificador` |
| `NLP/README.md` | comandos de requisitos y spaCy; enlace a `docs/README.md`; advertencia sobre `frases.py` |
| `NLP/evaluacion/escaneo.py`, `referencia.py`, `NLP/recursos/casing.py`, `NLP/reduccion/extractor.py`, `clustering/validacion.py` | imports inertes eliminados |
| `planeacion.md` (raíz) | puntero a `NLP/docs/` |

**Artefactos generados hoy** (en `NLP/salidas/`, no versionados; se regeneran con el
comando indicado):

| Artefacto | Comando | Nota |
|---|---|---|
| `lexico_clinico.json` (32.315 formas) | `python -m NLP.recursos.lexico` | su ausencia hacía que la fase 5 descartara toda oración larga |
| `lexico_casing.json` (4.843 entradas) | `python -m NLP.recursos.casing` | requiere BD |
| `clasificador_frases.joblib` | `from NLP.reduccion import frases; frases.entrenar()` | **no** usar `python -m NLP.reduccion.frases`: regenera `datos/frases_etiquetadas.csv` (curado a mano) |
| `cache_correcciones.json` | se llena al procesar | la caché anterior (versión 3, sin spaCy) está apartada en `cache_correcciones.descartada.json`; puede borrarse |
| `triage_reparado.csv`, `informe_reparacion.csv` | `python -m NLP.reparacion.reparar` | los de las pruebas de 100 notas; la corrida completa los sobrescribirá |

**Instalado hoy**: modelo `es_core_news_md` de spaCy (su ausencia dejaba la fase 2 sin
vocabulario ni protección de nombres propios); `pyflakes`.

**Proceso en curso al cerrar la sesión**: `python -m NLP.reparacion.reparar` sobre las
9.311 notas de `triage_limpio.csv`, sin `--aplicar`. Escribe `salidas/triage_reparado.csv`
e `informe_reparacion.csv` al terminar. Si al abrir la sesión no existen con fecha
posterior al 2026-09-15 14:00, relanzar el comando (usa la caché; tarda ~2–3 h en frío).

## 3. Resultados medidos hoy (línea base informal)

- Corpus: 94.136 notas en `DIM_TRIAGE`; 9.311 en el CSV.
- Reparación sobre muestra de 100: 69 intactas, 24 recuperan motivo, 3 cambian
  ortografía, 4 alarmas de pérdida (las cuatro verificadas como texto administrativo).
- Fase 2b sobre 8.751 notas: toca el 0,4 %, 2,6 ms por nota, 32 reversiones distintas,
  todas defendibles (ver `decisiones/2026-09-15-coherencia.md`).
- Reconstrucción del léxico: contenido descartado por la fase 5 pasa de 0,195 a 0,121
  (media); notas que pierden > 50 %: 18,1 % → 8,7 %; 25,1 % de notas recuperan
  contenido.
- Ollama `qwen2.5:3b`: 5,5 tokens/s en esta CPU.

## 4. Tabla de estado por ítem

Estados: `pendiente`, `en curso`, `bloqueado`, `cerrado`. La evidencia enlaza a
`bitacora/`.

| Ítem | Título | Estado | Sesión | Evidencia |
|---|---|---|---|---|
| E0.1 | Consolidar el trabajo del 15/09 (commit) | pendiente (P) | | |
| E0.2 | Terminar y revisar la reparación completa | en curso | 2026-09-15 (job en segundo plano) | |
| E0.3 | Aplicar la reparación y revectorizar | pendiente | | |
| E0.4 | Homogeneizar la escritura de CSV | pendiente | | |
| E0.5 | Línea base de métricas | pendiente | | |
| E0.6 | Conjunto de evaluación v0 | pendiente (P) | | |
| E1.1 | Estructura de `docs/` | en curso | 2026-09-15 | README, PLAN (v2), ESTADO, INVESTIGACION (v2, citada y enlazada), REFERENCIAS (enlaces completos), ARQUITECTURA, 4 decisiones, 1 bitácora, `Historial` en cada documento; faltan FLUJO, OPERACION, anotacion.md |
| E1.2 | `ARQUITECTURA.md` | en curso | 2026-09-15 | versión inicial escrita (49 archivos, grafo, E/S, duplicaciones); falta `paridad_docs.py` |
| E1.3 | `FLUJO.md` | pendiente | | |
| E1.4 | `OPERACION.md` | pendiente | | |
| E1.5 | Migrar documentación del código | pendiente | | |
| E1.6 | Guía de estilo | pendiente | | |
| E2.1 | Pruebas de regresión | pendiente | | |
| E2.2 | Módulo de métricas | pendiente | | |
| E2.3 | Corpus autoinducido y conjunto limpio | pendiente | | |
| E2.4 | Auditoría por par distinto | pendiente | | |
| E3.1 | Descargador con manifiesto | pendiente | | |
| E3.2 | Siglas protegidas | pendiente | | |
| E3.3 | Léxico del corpus propio | pendiente | | |
| E3.4 | Gazetteers SympTEMIST y DISTEMIST | pendiente | | |
| E3.5 | Fármacos (CUM, AEMPS) | pendiente | | |
| E3.6 | Topónimos y nombres | pendiente | | |
| E3.7 | Negación (NegEx-MES) | pendiente | | |
| E3.8 | Abreviaturas propias | pendiente | | |
| E3.9 | MedLexSp | pendiente (P) | | |
| E3.10 | MeSpEn | pendiente | | |
| E4.1–E4.9 | Experimentos del corrector | pendiente | | |
| E5.1–E5.7 | Normalización y reducción | pendiente | | |
| E6.1–E6.5 | Arquitectura y refactor | pendiente | | |
| E7.1–E7.4 | Ciclo de vida y operación | pendiente | | |

## 5. Problemas conocidos (no resueltos)

- `reparacion/reparar.py` escribe con pandas (QUOTE_MINIMAL); `procesar.py` con
  `nucleo/salida.py` (QUOTE_ALL). Un `procesar.py` posterior añadiría filas con otro
  entrecomillado. → E0.4.
- La copia de seguridad `triage_limpio.previo-<sello>.csv` no la purga `salida.rotar()`
  (glob `{stem}_*`). → E0.4.
- `embedding/corpus.py` lee el CSV sin `encoding=`. Funciona por el manejo del BOM de
  pandas. → anotar en E7.2.
- `embedding/estructurar.py` lista `texto_limpio`, columna que no existe. → E6.
- La métrica `perdio_motivo` aún cuenta `dada`, `salud`, `toma`, `signos` como
  terminología (están en el léxico curado). Es ruido conocido; se revisa por término.
- 38,1 % de las notas llevan glosa entre paréntesis en `texto_normalizado`, y
  `clustering/etiquetas.py` depende de ellas. → E5.1.
- `requirements.txt` fija `scikit-learn==1.4.2`; el `.venv` tiene 1.9.1.
- Léxico curado sin cobertura de cola larga (`ginecobstetricia`, `tensionales`). → E3.
- `alarmas.reiniciar()` nunca se invoca: los contadores del resumen final acumulan
  dentro de la corrida. → E2.0.
- `evaluacion/referencia.py` falla con `FileNotFoundError`: `salidas/muestra_revision.csv`
  nunca se generó (`escaneo.py --muestra`). → E0.6.
- `nucleo/clinico.py` (256 líneas) carga spaCy + medspaCy y solo se usan sus dos
  tablas. → E6.3.
- Duplicaciones de lógica listadas en `ARQUITECTURA.md` §5. → E6.0.

## 6. Próximas tres acciones

(Al cerrar cualquiera de ellas: bitácora con la lista de documentación de `PLAN.md` §4.1.)

1. Cerrar E0.2 cuando termine el job: revisar el resumen por término del informe y
   escribir `bitacora/2026-09-15-E0.2.md`.
2. E0.1: presentar el commit al propietario.
3. E1.2: escribir `evaluacion/paridad_docs.py` y cerrar el ítem; después E1.3 (`FLUJO.md`).


## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | previo al plan | Primera versión |
