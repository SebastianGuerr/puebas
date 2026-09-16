# Estado del plan

Última actualización: 2026-09-16 (sesión de ejecución con agentes en paralelo). Actualizar
este archivo al reclamar y al cerrar cada ítem.

## 1. Lectura obligatoria al abrir una sesión

1. `PLAN.md` §0, §2, §3 y §4 (cómo trabajar), §6 (qué no romper).
2. Este archivo completo.
3. `python -m NLP.nucleo.requisitos` — debe mostrar todo en OK.
4. `python -m pytest NLP/tests -q` — debe dar 24 en verde en menos de 5 minutos.
5. `python -m NLP.evaluacion.paridad_docs --estricto` — debe dar 0 faltantes y 0 huérfanas.
6. `git status` — ver §2 antes de tocar nada.

## 2. Estado del repositorio

Commits de la sesión del 2026-09-16, en orden:

| Commit | Contenido |
|---|---|
| `ba63bfc` | consolidación del trabajo del 15/09 (E0.1) |
| `e530af4` | bitácora de cierre de E0.1 |
| `9cbbc03` | licencias verificadas y `evaluacion/calidad.py` |
| `fb3ab07` | E4.1/E3.3: la exención por errata de teclado tapaba el daño |
| `a7219f9` | E0.4, E0.6, E1.2–E1.4, E2.0–E2.4, E3.1: infraestructura de evaluación |
| `567e09e` | E6.4 parcial: `embedding/estructurar.py` estaba roto |

`main` va por delante de `origin/main` y **no se ha publicado**: el `push` lo decide el
propietario. Antes de publicar hay que revisar qué archivos de `datos/` contienen texto de
notas reales (principio 7).

**Artefactos** (en `NLP/salidas/`, no versionados; se regeneran con el comando indicado):

| Artefacto | Comando | Nota |
|---|---|---|
| `lexico_clinico.json` (32.315 formas) | `python -m NLP.recursos.lexico` | su ausencia hacía que la fase 5 descartara toda oración larga |
| `lexico_casing.json` (4.845 entradas) | `python -m NLP.recursos.casing` | requiere BD |
| `clasificador_frases.joblib` | `from NLP.reduccion import frases; frases.entrenar()` | **no** usar `python -m NLP.reduccion.frases`: regenera `datos/frases_etiquetadas.csv`, que es curado a mano |
| `cache_correcciones.json` | se llena al procesar | ver §5: 46 entradas sintéticas inertes |
| `pares_correccion.csv` (2.193 pares) | `python -m NLP.evaluacion.pares` | tabla de auditoría de E2.4 |
| `evaluacion/autoinducido.csv` (6.779), `evaluacion/limpio.csv` (3.645) | `python -m NLP.evaluacion.perturbar` | conjuntos de E2.3, deterministas |
| `evaluacion/muestra_gold_v0.csv` (400 notas) | script de E0.6 (en la bitácora) | contiene notas reales; no versionar |
| `metricas/<fecha>-<item>.json`, `metricas/historico.csv` | `python -m NLP.evaluacion.metricas --guardar` / `calidad.py --guardar` | dos formatos conviven a propósito: ver §3 |
| `triage_reparado.csv`, `informe_reparacion.csv` | `python -m NLP.reparacion.reparar` | ver §2.1 |
| `recursos_externos/DIVIPOLA_municipios/` | `python -m NLP.recursos.descargar --solo DIVIPOLA_municipios` | sha256 verificado |

**Instalado**: `es_core_news_md` de spaCy (GPL-3.0, ver `REFERENCIAS.md` §5), `pyflakes`,
`pytest`.

### 2.1 Proceso en curso

`python -m NLP.reparacion.reparar` sin `--aplicar` sobre las 9.311 notas, relanzado el
16/09 a las 07:54 (el del 15/09 murió al 67 % y el de la noche anterior no llegó a
terminar). Escribe `triage_reparado.csv` e `informe_reparacion.csv` al acabar. **Los dos
archivos que hay en disco siguen siendo los de la prueba de 100 notas del 15/09 a las
13:42**: mientras su fecha no sea posterior al 16/09 08:00, la reparación completa no ha
terminado y E0.2 no puede cerrarse. Si se interrumpe, relanzar el mismo comando; la caché
conserva lo ya corregido.

## 3. Resultados medidos

### 3.1 Línea base de calidad del CSV (2026-09-16, 9.311 notas, corrector v4, antes de aplicar la reparación)

`python -m NLP.evaluacion.calidad --guardar --item linea-base-antes-de-reparar`

| Métrica | Valor |
|---|---|
| Notas con terminología clínica en el original | 5.221 |
| Retención media de terminología en `texto_embedding` | 0,9185 |
| Notas que conservan toda su terminología | 86,86 % de 5.221 |
| Notas que pierden más de la mitad | 5,23 % de 5.221 = 273 |
| Notas que se quedan sin terminología | 3,91 % de 5.221 = 204 (2,19 % del corpus) |
| Notas con menos de tres palabras | 1.405 (15,1 % del corpus) |
| Notas con glosa entre paréntesis | 38,06 % |
| Notas que superan la ventana de `bge-m3` | 10 |
| Tokens que cambia el corrector | 7,82 % |
| …sin contar los cambios de sola tilde | **2,56 %** |
| Proporción de los cambios que es solo tilde | 67,3 % |

**Cuidado con el denominador**: todas las filas de retención van sobre las 5.221 notas que
tenían terminología en el original, no sobre las 9.311. El informe lo imprime al pie.

### 3.2 Calidad del corrector (2026-09-16)

Sobre `datos/evaluacion/pares_juzgados.csv` (141 pares juzgados a mano, 120 cruzan con la
tabla de E2.4: 34 dañinos y 86 buenos):

| Configuración de la fase 2b | Daño deshecho | Correcciones buenas perdidas |
|---|---|---|
| v4 (la del 15/09) | 1/34 — 2,9 % | 0/83 |
| **la adoptada el 16/09** | **8/34 — 23,5 %** | **0/83** |
| más agresiva (descartada) | 11/34 — 32,4 % | 1/83 |

Ver `decisiones/2026-09-16-E4.1-reversion-de-correcciones.md`. Daño confirmado contra el
CSV: `paraclínicos → paralíticos` en 6 notas (la forma «paralític\*» aparece 0 veces en los
originales y 6 en el texto corregido); 409 pares (15,8 % de las sustituciones) sustituyen
por una forma que no aparece **ni una vez** en el corpus.

### 3.3 Cifras anteriores que siguen vigentes

- Corpus: 94.136 notas en `DIM_TRIAGE` (94.226 al 16/09); 9.311 en el CSV.
- Fase 2b sobre 8.751 notas: toca el 0,4 %, 2,6 ms por nota (medido con la configuración
  v4; con la nueva hay que volver a medirlo).
- Reconstrucción del léxico: contenido descartado por la fase 5 de 0,195 a 0,121 de media.
- Ollama `qwen2.5:3b`: 5,5 tokens/s en esta CPU.

## 4. Tabla de estado por ítem

Estados: `pendiente`, `en curso`, `propuesto` (con evidencia, a falta de verificación del
orquestador), `bloqueado`, `cerrado`.

| Ítem | Título | Estado | Evidencia |
|---|---|---|---|
| E0.1 | Consolidar el trabajo del 15/09 | cerrado | `bitacora/2026-09-15-E0.1.md`, commit `ba63bfc` |
| E0.2 | Terminar y revisar la reparación completa | en curso | job corriendo; ver §2.1 |
| E0.3 | Aplicar la reparación y revectorizar | pendiente | depende de E0.2 |
| E0.4 | Homogeneizar la escritura de CSV | propuesto | `bitacora/2026-09-16-E0.4.md` |
| E0.5 | Línea base de métricas | cerrado parcialmente | `bitacora/2026-09-16-E0.5-calidad.md`; falta la parte que necesita el gold |
| E0.6 | Conjunto de evaluación v0 | **bloqueado en anotación humana** | `bitacora/2026-09-16-E0.6.md`; muestra de 400 y `docs/anotacion.md` listos |
| E1.1 | Estructura de `docs/` | cerrado | todos los documentos con `Historial`; `paridad_docs` lo comprueba |
| E1.2 | `ARQUITECTURA.md` y paridad automática | propuesto | `bitacora/2026-09-15-E1.2.md` |
| E1.3 | `FLUJO.md` | propuesto | `bitacora/2026-09-16-E1.3-E1.4.md` |
| E1.4 | `OPERACION.md` | propuesto | idem; falta la prueba por un agente sin contexto |
| E1.5 | Migrar documentación del código | pendiente | necesita acceso exclusivo a los `.py` |
| E1.6 | Guía de estilo | propuesto | `ARQUITECTURA.md` §6 |
| E2.0 | Contadores de alarmas | propuesto | dentro de `bitacora/2026-09-16-E2.1.md` |
| E2.1 | Pruebas de regresión | **verificado por el orquestador** | 24 pruebas en verde en 99,77 s |
| E2.2 | Módulo de métricas | **verificado por el orquestador** | reproduce su cálculo a mano de 5 notas |
| E2.3 | Corpus autoinducido y conjunto limpio | propuesto | 6.779 pares y 3.645 notas limpias |
| E2.4 | Auditoría por par distinto | **verificado por el orquestador** | 2.193 pares; base de las decisiones de E4.1 |
| E3.1 | Descargador con manifiesto | **verificado por el orquestador** | rechazo por hash reproducido: borra el archivo y sale con código 1 |
| E3.2 | Siglas protegidas | en curso | |
| E3.3 | Léxico del corpus propio | en curso | umbral provisional 20 en `coherencia.py` |
| E3.4 | Gazetteers SympTEMIST y DISTEMIST | **bloqueado** | Zenodo no respondía el 16/09 |
| E3.5 | Fármacos (CUM, AEMPS) | pendiente | en el manifiesto |
| E3.6 | Topónimos y nombres | pendiente | DIVIPOLA descargado y verificado |
| E3.7 | Negación (NegEx-MES) | en curso | |
| E3.8 | Abreviaturas propias | en curso | |
| E3.9 | MedLexSp | **bloqueado** | requiere solicitud firmada por una persona |
| E3.10 | MeSpEn | pendiente | en el manifiesto, CC-BY-4.0 confirmada |
| E4.1 | Regla estricta de frecuencia | **cerrado** | `decisiones/2026-09-16-E4.1-reversion-de-correcciones.md` |
| E4.2 | Distancia por longitud y frecuencia del candidato | en curso | |
| E4.3–E4.8 | Fonética, canal ruidoso, tildes, verificador enmascarado, fastText, LanguageTool | pendiente | |
| E4.9 | Composición del corrector v2 | pendiente | |
| E5.1 | Glosas | en curso | |
| E5.2 | Negación con alcance | pendiente | depende de E3.7 |
| E5.3–E5.4 | Abreviaturas, lematización | pendiente | |
| E5.5 | Clasificador de frases | pendiente | |
| E5.6 | Extractor por modelo de lenguaje | **bloqueado por licencia** | ver `decisiones/2026-09-16-licencias-modelos-en-uso.md` |
| E5.7 | Normalización conceptual (fase 6) | pendiente | depende de E3.4 |
| E6.0 | Eliminar duplicaciones | en curso (inventario) | |
| E6.1 | Diseño del refactor | pendiente | |
| E6.2 | Dividir archivos grandes | pendiente | `metricas.py` ya nace con 427 líneas |
| E6.3 | Eliminar código muerto | en curso | |
| E6.4 | Mover `catalogo_sintomas.json` | parcial | el fallo de `estructurar.py` ya está arreglado (`567e09e`) |
| E6.5 | Salida idéntica | pendiente | la prueba ya existe en `NLP/tests/` |
| E7.1–E7.4 | Ciclo de vida y operación | pendiente | E7.2 documentado en `OPERACION.md`, no ejecutado |

## 5. Problemas conocidos (no resueltos)

- **`qwen2.5:3b-instruct` tiene licencia no comercial** y la fase 5 lo usa cuando Ollama
  responde. Requiere decisión del propietario antes de producción (§6.9 del plan).
- **`es_core_news_md` es GPL-3.0**, no MIT. Sin efecto mientras no se distribuya el
  producto; registrado en `REFERENCIAS.md` §5.
- `cache_correcciones.json` tiene **46 entradas sintéticas** que dejó una corrida de
  pruebas con la caché activada. Verificado: ninguna coincide con una nota real, así que
  son inertes. Limpiar cuando el job en curso termine (script en el scratchpad de la
  sesión); `NLP/tests/conftest.py` ya fuerza `USAR_CACHE = False`.
- `pesos.py`: la señal `jerga_frecuente` vale 0,40 y el umbral de protección es 0,50, de
  modo que **una palabra que el corpus repite nunca queda protegida por esa vía**. No se
  toca sin medir: subirla protegería también las erratas repetidas (`pacinete` aparece 43
  veces). → E4.2.
- `evaluacion/referencia.py` corre, pero da cero en todo: las 27 anotaciones de
  `datos/referencia_correcciones.json` no comparten ningún OID con `muestra_revision.csv`.
- El léxico curado da por clínicas palabras como `salud`, `esperanza` o `solicita`, lo que
  impide marcar como trámite algunas notas que lo son. → abrir ítem en E3.
- 38,06 % de las notas llevan glosa entre paréntesis y `clustering/etiquetas.py` depende de
  ellas. → E5.1.
- `requirements.txt` fija `scikit-learn==1.4.2`; el `.venv` tiene 1.9.1.
- `embedding/corpus.py` lee el CSV sin `encoding=`. → E7.2.
- `nucleo/clinico.py` (256 líneas) carga spaCy + medspaCy y solo se usan sus dos tablas.
  → E6.3.
- `nucleo/requisitos.py` recomienda `python -m NLP.reduccion.frases` para regenerar el
  clasificador: es precisamente el comando prohibido. → corregir en E6.3.
- `sugerencias.py` afirma en su documentación que nunca propone una forma que el corpus no
  escriba, y 409 pares demuestran lo contrario. → E4.2 y E6.3.

## 6. Próximas acciones

1. **E0.2**: cuando termine el job, `python -m NLP.reparacion.revision` sobre el informe,
   veredicto término a término y bitácora. Criterio: `recupero_motivo > perdio_motivo` y
   cero términos con veredicto real.
2. **E0.3**: `reparar --aplicar`, revectorizar, `python -m clustering --validar`, y volver
   a medir con `calidad.py --comparar` para cuantificar la mejora.
3. **Volver a medir la fase 2b** con la configuración adoptada el 16/09 y con las
   frecuencias del corpus completo, no las del CSV (la decisión E4.1 dice por qué la
   cobertura real debería ser mayor que el 23,5 % medido).
4. Verificar los ítems en estado `propuesto` y pasarlos a `cerrado`.
5. Decisión del propietario sobre el `push`, sobre la licencia de Qwen y sobre la
   anotación del gold v0 (E0.6), que bloquea E0.5 completo y toda la evaluación de E4.

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | previo al plan | Primera versión |
| 2026-09-15 | E0.1 | §2 reescrita (commit `ba63bfc`, árbol limpio); E0.1 a `cerrado` |
| 2026-09-16 | oleada de ejecución | §2 con los seis commits; §3 con la línea base de calidad y la medición del corrector; §4 reescrita con los estados de E0–E7; §5 con licencias, caché, `jerga_frecuente` y documentación falsa; §6 reordenada |
