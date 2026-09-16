# Arquitectura del paquete NLP

Versión inicial, 2026-09-15, a partir del inventario de los 49 archivos `.py` (12.419
líneas). Se mantiene con el ítem E1.2 del plan; `evaluacion/paridad_docs.py` (pendiente)
comprobará que todo archivo del paquete tenga entrada aquí.

## 1. Mapa

```
NLP/
  procesar.py          orquestador: BD -> fases 1..5 por bloques -> salidas/
  rutas.py             único módulo que conoce la ubicación de cada archivo
  nucleo/              transversal: morfología, spaCy, reglas de protección, BD,
                       escritura de CSV, caché, progreso, requisitos
  fase1_limpieza/      forma del texto (mayúsculas, espacios, símbolos)
  fase2_ortografia/    palabras mal escritas; 2b: coherencia con la nota original
  fase3_normalizacion/ coloquialismos y siglas a terminología (anotación)
  depuracion/          fase 4: señala notas sin contenido clínico
  reduccion/           fase 5: recorte al motivo de consulta (reglas, clasificador,
                       extractor por modelo local)
  recursos/            constructores de léxicos y diccionarios; descargador con manifiesto
  evaluacion/          auditoría de corridas, escaneo del corpus, referencia anotada
  reparacion/          reprocesa un CSV existente, compara y revisa el informe
  tests/               pruebas de regresion (pytest); datos/ con las notas sinteticas
  datos/               curado a mano, versionado (incluye recursos_manifiesto.json)
  salidas/             generado por scripts, ignorado por git
  recursos_externos/   descargas verificadas de recursos_manifiesto.json, ignorado por git
  docs/                esta documentación
```

Flujo de una nota: `HCTMOTCON` → fase 1 (`texto_limpio`, `texto_norm` con mayúsculas)
→ fase 2 (`texto_corregido`) → fase 2b (reversión de correcciones incoherentes) → fase 3
(`texto_normalizado`) → fase 4 (marca `motivo_descarte`) → fase 5 (`texto_embedding`).

## 2. Archivos

Para cada archivo: función, fase, interfaz pública principal, configuración editable,
artefactos. `[G]` marca más de 400 líneas (candidato a división en E6). Toda la
documentación interna es hoy extensa y narrativa; E1.5 la reduce.

### 2.1 Raíz

**`rutas.py`** (54) — Constantes de ruta. Separa `datos/` de `salidas/`. Crea
`salidas/` al importarse. Define también `CATALOGO_SINTOMAS` apuntando a
`embedding/datos/catalogo_sintomas.json` (acoplamiento inverso; ver `PLAN.md` §6).
Importado por 15 módulos.

**`procesar.py`** (811) `[G]` — Orquestador. Único archivo que conoce la base de datos.
`cargar_corpus` (léxico de frecuencias sobre `LIMITE_LEXICO` notas), `cargar_registros`
(solo notas no procesadas), `preparar` (fase 1 + clave de caché), `corregir_lote`
(fase 2 en `N_HILOS` hilos, guardando caché cada `GUARDAR_CADA`), `procesar_bloque`
(fases 2–5 sobre `BLOQUE_ESCRITURA` notas), `main` (`--limite`, `--sin-llm`,
`--rehacer`). Configuración: `TABLA = DIM_TRIAGE`, `COLUMNA = HCTMOTCON`, `LLAVE = OID`,
`LIMITE_REGISTROS = 5000`, `LIMITE_LEXICO = 200000`, `N_HILOS = 4`, `BLOQUE_ESCRITURA =
250`, `NORMALIZAR`, `REVISAR_COHERENCIA`, `DEPURAR`, `REDUCIR`, `USAR_LLM`, `USAR_CACHE`,
`VERSION_CORRECTOR = "4-con-spacy-y-coherencia"`. Lee BD y `CACHE_CORRECCIONES`;
escribe `TRIAGE_LIMPIO`, `REPORTE_CAMBIOS`, `NOTAS_DESCARTADAS`, `CACHE_CORRECCIONES`.

### 2.2 `nucleo/`

**`morfologia.py`** (363) — Capa más baja: todo lo que se decide por la forma de la
palabra. `normalizar`, `sin_tildes` (conserva la ñ), `morfemas`, `es_termino_medico`,
`prefijos`, `invierte_significado`, `cambia_familia`, `cambia_categoria`,
`es_truncamiento`, `solo_cambia_terminacion`, `conserva_morfemas`, `parece_farmaco`,
`es_restauracion_tilde`, `tiene_numero`. Sin dependencias internas. Importado por 14
módulos y por `clustering/etiquetas.py`.

**`linguistica.py`** (197) — spaCy `es_core_news_md`: `en_vocabulario` (con caché;
ignora palabras de menos de 4 letras), `entidades` (PER/LOC/ORG/MISC), `disponible`,
`iniciar`. Siempre para proteger, nunca para corregir. Sin el modelo devuelve False y
conjunto vacío (por eso `requisitos.py` lo exige).

**`clinico.py`** (256) — spaCy + medspaCy compartidos y la tabla `SECCIONES` (15
categorías) / `SECCIONES_NO_CLINICAS` (8). Solo las tablas se usan (`depuracion.py`);
`analizar`, `secciones`, `seccionador`, `nlp`, `disponible` no tienen llamadas.

**`reglas.py`** (344) — Qué tokens no se corrigen nunca. `cargar` (lee
`diccionario_siglas.json` y llena `SIGLAS`, `EXPANDIBLES`, `DIRECTAS`, `PATRONES`, y
también `SIGLAS_PROTEGIDAS_MANUAL` vía `cargar_siglas_protegidas`),
`esta_protegido`, `detectar_protegidos` (mayúsculas informativas del original),
`entidades` (spaCy confirmado por corpus o vocabulario), `es_palabra_conocida`,
`forma_aceptable`, `texto_gritado`. Reexporta de `morfologia` (`sin_tildes`, `morfemas`,
`normalizar`…): esas importaciones no son inertes. Configuración: `LONGITUD_MINIMA = 5`,
`DISTANCIA_MAXIMA = 2`, `PROPORCION_MAYUSCULAS = 0.9`, `USAR_SPACY`,
`PROTEGER_ENTIDADES`, `PROTEGER_SIGLAS_LISTA_MANUAL = True` (E3.2: `esta_protegido`
también bloquea las formas de `datos/lexicos/siglas_protegidas.txt`, independientes del
diccionario). Decisión: `bitacora/2026-09-16-E3.2.md`.

**`requisitos.py`** (194) — Comprueba artefactos y modelo antes de arrancar. `exigir`
(detiene si falta un exigido), `revisar`, `main`. Tabla `ARTEFACTOS` con exigidos
(léxico clínico, léxico externo, catálogo de síntomas, diccionario de siglas, modelo
spaCy) y opcionales (casing, clasificador).

**`cache.py`** (89) — Caché `{clave: texto}` en disco; la clave incluye
`version\x00texto\x00protegidos`. `clave`, `leer`, `guardar` (relee antes de añadir).

**`datos.py`** (93) — Consultas a la BD parametrizadas: `muestra` (muestreo repetible
con `HASHBYTES`, exclusión por tabla temporal), `columna_suelta`.

**`conexion_bd.py`** (40) — `obtener_engine()`: `mssql+pyodbc`, host `ls-cobra`, base
`DWSES`, autenticación integrada. Importado también por `clustering/fechas.py`.

**`salida.py`** (197) — `rotar` (conserva 3 versiones con fecha), `cabecera_compatible`,
`llaves_escritas`, `contar_filas`, `EscritorCSV` (utf-8-sig, CRLF, QUOTE_ALL; en modo
reanudar abre en utf-8 sin BOM).

**`progreso.py`** (53) — `barra`, `fin_barra`.

**`lt_compat.py`** (92) — Acceso a los `Match` de LanguageTool independiente de la
versión: `offset`, `largo`, `span`, `regla`, `categoria`, `reemplazos`, `verificar`.

### 2.3 `fase1_limpieza/`

**`limpieza.py`** (254) — `limpiar` (minúsculas, espacios, símbolos; no cambia
palabras), `limpiar_conservando_original` (par limpio / original con mayúsculas),
`tokenizar`, `es_vacio`, `analizar`. Configuración: `SEPARADOR_LINEA`,
`MAX_REPETICIONES = 2`, `LARGO_MAXIMO = 20000`, `SIMBOLOS_CLINICOS = "+?()<>"`,
`ENCABEZADOS` (21 rótulos).

### 2.4 `fase2_ortografia/`

Cadena: correcciones directas → enmascarado clínico → LanguageTool (solo `TYPOS`) →
SymSpell → capa de contexto → restauración de siglas → (2b) coherencia. Cada capa ve
menos texto que la anterior; la terminología clínica no llega a ninguna.

**`ortografia.py`** (730) `[G]` — Orquestador de la fase. `corregir(texto, original)`,
`cargar_siglas`, `cargar_lexico_clinico`, `construir_lexico` (frecuencias + SymSpell),
`iniciar_languagetool` / `cerrar_languagetool` (mata el árbol de procesos Java),
`aplicar_directas`, `restaurar_mayusculas`, `aplicar_contexto`, `es_sigla_real`.
Configuración: `CATEGORIAS_PERMITIDAS = {"TYPOS"}`, `USAR_VOCABULARIO`,
`RESTAURAR_MAYUSCULAS`, `USAR_CONTEXTO`, `FRECUENCIA_PALABRA_ESTABLECIDA = 20`,
`RATIO_EXPANSION_MAXIMO = 2.0`, `DOMINANCIA_PARA_ESCRIBIR = 0.85`.

**`pesos.py`** (210) — Peso clínico de cada palabra antes de que el corrector la vea.
`peso` → (peso, motivo), `protegida`, `pesar_texto`, `usar_conteo`, `frecuencia`.
Tabla `PESOS` (diccionario/catálogo/externo 0,95; fármaco 0,90; morfemas 0,70; sigla
del corpus 0,60; biomédico 0,45; jerga frecuente 0,40; número 1,00).
`UMBRAL_PROTECCION = 0.5`, `FRECUENCIA_JERGA = 8`. E3.2: `peso()` también reconoce
`reglas.SIGLAS_PROTEGIDAS_MANUAL` (motivo `sigla_protegida_manual`, peso 0,95) tras la
bandera `reglas.PROTEGER_SIGLAS_LISTA_MANUAL`, para que la capa de contexto (que solo
consulta `peso()`, no `esta_protegido()`) respete la misma lista.

**`enmascarado.py`** (235) — Aparta la terminología en rangos intocables y la corrige
contra el léxico médico. `enmascarar(texto, corregir)` → `Nota`, `admisible`.
`LONGITUD_MINIMA_CORRECCION = 6`.

**`candidatos.py`** (169) — Elige entre las sugerencias de LanguageTool o se abstiene.
`elegir`, `construir_lexico`, `frecuencia`. `FRECUENCIA_CANDIDATO = 3`,
`FRECUENCIA_DESEMPATE = 10`, `RATIO_DESEMPATE = 3`, `UMBRAL_TERMINO = 10`.

**`vocabulario.py`** (326) — SymSpell sobre el vocabulario del corpus (solo formas que
spaCy reconoce). `construir`, `sugerir`, `corregir_texto`, `vecinos`, `disponible`.
`DISTANCIA_MAXIMA = 3`, `LONGITUD_MINIMA = 5`, `LONGITUD_DISTANCIA_3 = 10`,
`FRECUENCIA_TYPO = 2`, `RATIO_MINIMO = 10`.

**`sugerencias.py`** (234) — Candidatos para la capa de contexto desde cuatro fuentes
(léxico, corpus, divisiones, expansiones por subsecuencia). `generar`,
`_es_subsecuencia` (usado por `coherencia.py`). `DISTANCIA_MAXIMA = 2`,
`LONGITUD_MAXIMA_ABREVIATURA = 6`, `FRECUENCIA_EXPANSION = 30`.

**`contexto.py`** (605) `[G]` — Modelo enmascarado
(`PlanTL-GOB-ES/roberta-base-biomedical-clinical-es`) para decidir si una palabra cabe
en su hueco. `elegir`, `logprob`, `logprob_medio`, `iniciar`, `disponible`.
`UMBRAL_SOSPECHA = -6.0`, `UMBRAL_GANANCIA = 2.0`, `MAX_CANDIDATOS = 8`,
`DISTANCIA_RELATIVA_MAXIMA = 0.5`. Contiene su propia distancia Damerau (47 líneas).

**`terminologia.py`** (254) — Puerta única por la que pasa cada cambio: `validar`,
`admite`, `es_terminologia`, `es_abreviatura`. Reexporta la interfaz de `alarmas`
(`anotar_abstencion`, `resumen_alarmas`, `resumen_abstenciones`): esas importaciones
no son inertes. `VETO_TERMINO_CONTRA_TERMINO = True`.

**`alarmas.py`** (98) — Contadores de vetos y abstenciones: `anotar`,
`anotar_abstencion`, `resumen_alarmas`, `resumen_abstenciones`, `reiniciar`.
`reiniciar()` no se llama desde `procesar.py` (los contadores acumulan entre bloques
dentro de una misma corrida; ver §5).

**`coherencia.py`** (324) — Fase 2b. `revisar(limpio, corregido, original)` → (texto,
incidencias); `juzgar`; `nombres_del_corpus`; `sin_corregir` (sin llamadas aún).
`FRACCION_DISTANCIA_MAXIMA = 0.40`, `FACTOR_FRECUENCIA = 10`, `LONGITUD_MINIMA = 4`.
Decisión: `decisiones/2026-09-15-coherencia.md`.

### 2.5 `fase3_normalizacion/`

**`normalizacion.py`** (373) — Traduce habla del paciente y siglas a terminología,
anotando entre paréntesis (`MODO = "anotar"`), con control de ambigüedad por entrada
(`recursos/ambiguedad.py`). `cargar`, `normalizar`, `expandir_encabezados`,
`disponible` (False hasta llamar a `cargar`), `desactivadas`, `con_contexto`. Lee
`diccionario_coloquial.json` y `diccionario_siglas.json`. `SEPARAR_CONCEPTO = False`
(E5.1) — con `normalizar_separado(texto)` devuelve `(texto_sin_glosa,
concepto_normalizado)` en vez de anotar inline; apagada por defecto. Ver
`decisiones/2026-09-16-E5.1-glosas.md`.

### 2.6 `depuracion/`

**`depuracion.py`** (627) `[G]` — Fase 4: señala (no elimina) notas sin contenido
clínico, comparando por raíz contra el léxico curado. `evaluar` → (útil, motivo),
`cargar` (índice de raíces; 10.402 con el léxico completo), `es_clinica` (por raíz),
`terminos_clinicos`, `sin_apartados_no_clinicos`, `solo_tramite`, `resumen`. Motivos:
`VACIA`, `PLANTILLA`, `ANTECEDENTES`, `TRAMITE`, `SIN_TERMINOLOGIA`. Lee
`CATALOGO_SINTOMAS`, `DICCIONARIO_SIGLAS` (grupo `geografia`), léxico clínico vía
`recursos/lexico.py`. La comparación por raíz da por clínicas palabras como
`teniamos` o `recomendaciones` (ver `reparacion/comparacion.py`).

### 2.7 `reduccion/`

**`reduccion.py`** (877) `[G]` — Fase 5 por reglas: quita bloques que no son motivo de
consulta (institucional, trámite, examen físico, conducta, antecedentes, acompañante,
lugares, preámbulo temporal, demografía). `recortar(texto, agresivo)` (pasada agresiva
y suave; acepta la que no deja costuras), `cargar_lexico`, `cargar_lugares`,
`densidad_clinica`, `crea_costura`, `sin_reducir`, `diagnosticar` (no incluye el paso
del clasificador). `PALABRAS_ORACION_LARGA = 8`, `DENSIDAD_MINIMA = 0.40`,
`TOPE_PALABRAS = 60`, `FUENTES_CURADAS`. Mantiene su propio `_LEXICO` y `_es_clinica`
leyendo `lexico_clinico.json` directamente (duplica `recursos/lexico.py`; ver §5).
Freno por densidad al clasificador: `decisiones/2026-09-15-clasificador-freno-clinico.md`.
`QUITAR_GLOSA = False` (E5.1) — si `True`, `recortar()` quita también la anotación entre
paréntesis que dejó la fase 3 (`RE_PARENTESIS`); apagada por defecto, no interfiere con
`normalizacion.SEPARAR_CONCEPTO`. Ver `decisiones/2026-09-16-E5.1-glosas.md`.

**`extractor.py`** (593) `[G]` — Fase 5b: pide a Ollama (`qwen2.5:3b-instruct`) que
copie los fragmentos que son motivo y verifica que existan literalmente en la nota.
`extraer`, `disponible`, `localizar`, `verificar`, `conserva_lo_clinico`.
`LONGITUD_MINIMA = 1` (ve todas las notas), `TIMEOUT = 120`, `TEMPERATURA = 0.0`,
`FRACCION_MAXIMA = 0.85`, `FRACCION_CLINICA_MINIMA = 0.50`. Decisión sobre modelos
generativos: `decisiones/2026-09-15-modelo-generativo.md`.

**`frases.py`** (358) — Clasificador de tramos (RoBERTa clínico congelado + regresión
logística). `segmentos`, `burocraticos`, `probabilidades`, `etiquetar_debil`,
`construir_datos` (**regenera `datos/frases_etiquetadas.csv`, curado a mano**),
`entrenar` (usar este para reentrenar), `main` (construye y entrena: destruye la
curación). `MAX_LONGITUD = 64`, `UMBRAL_BUROCRATICO = 0.85`. Escribe
`CLASIFICADOR_FRASES`.

### 2.8 `recursos/`

**`lexico.py`** (458) `[G]` — Léxico clínico de cuatro fuentes (diccionario, catálogo,
externo CIE-10, modelo biomédico) más un grupo no clínico. `construir`, `guardar`,
`cargar`, `contiene`, `fuente`, `cercano`, `vecinos`. Escribe `LEXICO_CLINICO` (32.315
formas el 2026-09-15). La fuente biomédica no cuenta como curada en depuración ni
reducción.

**`casing.py`** (442) `[G]` — Aprende del corpus la capitalización de cada token (sigla,
nombre propio, común). `construir`, `guardar`, `cargar`, `restaurar`, `clase`,
`es_sigla`, `siglas`, `nombres_propios`, `mayusculas_informativas`, `disponible`.
`MINIMO_OBSERVACIONES = 3`, `DOMINANCIA = 0.6`. Lee la BD en `main`; escribe
`LEXICO_CASING` (4.843 entradas: 145 siglas, 164 nombres propios).

**`ambiguedad.py`** (180) — Una entrada de diccionario no se aplica salvo que sea
inequívoca o tenga su contexto cerca. `evaluar` → (libre | contexto | inactiva, contexto,
motivo), `hay_contexto`, `es_palabra_corriente`. `VENTANA_CONTEXTO = 6`.

**`detectar_siglas.py`** (169) — Script: tokens frecuentes que ningún diccionario
reconoce, para revisión humana. Escribe `SIGLAS_DETECTADAS` (no existe en disco hoy).

**`extraer_cie10.py`** (178) — Script: vocabulario del PDF del CIE-10 →
`LEXICO_EXTERNO`. `LONGITUD_MINIMA = 4`, `FRECUENCIA_MINIMA = 2`.

**`corpus_lexico.py`** (E3.3) — CLI `python -m NLP.recursos.corpus_lexico`: cuenta la
frecuencia de cada forma sobre `DIM_TRIAGE.HCTMOTCON` completa (94.226 notas el
2026-09-16) y, si la base no responde, sobre `texto_original` de `TRIAGE_LIMPIO` como
respaldo. `contar_bd`, `contar_csv`, `escribir` (TSV con cabecera de comentario que
declara la fuente), `cargar` (dict forma→frecuencia, sin tocar la BD). Escribe
`datos/lexicos/corpus_frecuencia.tsv`. Es la fuente de frecuencias que
`fase2_ortografia/pesos.usar_conteo()` puede recibir para calibrar
`coherencia.FRECUENCIA_RESPALDO_CORPUS` (E3.3; ver `bitacora/2026-09-16-E3.3.md`).

**`descargar.py`** (E3.1) — CLI `python -m NLP.recursos.descargar` que descarga,
verifica y extrae los recursos listados en `recursos_manifiesto.json` (PLAN.md §6 y
§4.5). `url_permitida` (https y dominio de `ALLOWED_DOMINIOS`, con prefijos de ruta
para los repositorios de organización autora en GitHub), `descargar_archivo` (stream a
`.parcial`, luego renombra), `sha256_de`, `extraer_seleccion` (lista el ZIP completo,
extrae solo `archivos_extraer` tras rechazar extensión ejecutable y zip slip),
`procesar_recurso` (aplica la regla de PLAN.md §6.6: hash que no coincide borra el
archivo y sale con código ≠ 0; hash `null` conserva el archivo e imprime el sha256 sin
escribirlo en el manifiesto), `main` (`--listar`, `--solo`, `--verificar`). Nunca
escribe en `recursos_manifiesto.json`: lo fija una persona (ver bitácora). Define
`RECURSOS_EXTERNOS` y `MANIFIESTO` en el propio módulo, no en `rutas.py` (pendiente de
mover; ver bitácora del ítem).

### 2.9 `evaluacion/`

**`auditoria.py`** (851) `[G]` — Mide una corrida y escribe `REPORTE_CAMBIOS`
(`fase, original, corregido, veces, oid_ejemplo`). `escribir_reporte`, `dano_probable`,
`motivo_dano` (los mismos umbrales que `coherencia.juzgar`, implementados aparte),
`medir`, `sustituciones`, `regresiones` (7 casos fijos), `typos_no_corregidos` (10
pares), `comparar`, `main` (`--guardar`, `--contra`). Contiene su propia distancia de
Levenshtein sin transposición.

**`escaneo.py`** (344) — Clasifica notas por señales objetivas y muestrea de forma
estratificada. `escanear`, `rareza`, `muestrear`, `main` (`--bd`, `--muestra`). Escribe
`MUESTRA_REVISION` (no existe en disco hoy).

**`referencia.py`** (338) — Conjunto de referencia anotado a mano y medición contra él.
`evaluar`, `construir_referencia`, `aplicar`, `cargar_anotaciones`. Lee
`REFERENCIA_CORRECCIONES` y `MUESTRA_REVISION`; **falla con `FileNotFoundError`
mientras no exista la muestra** (§5). Es la base natural de E0.6 y E2.2.

**`paridad_docs.py`** (175) — Comprueba que cada `.py` del paquete tenga ficha en
este documento y que cada ficha corresponda a un archivo; comprueba además que cada
`docs/*.md` tenga sección `## Historial`. `archivos_del_paquete`,
`fichas_del_documento`, `documentos_sin_historial`, `comparar`, `main` (`--estricto`,
`--doc`). Regla y lectura de la salida en §6.4. No escribe nada.

**`pares.py`** (E2.4) — Agrupa las correcciones de `triage_limpio.csv` por par
(original, correccion) distinto en vez de por nota. `pares_de_fila` (alineación 1 a 1
de tokens con `difflib`), `clave_fonetica` (clave fonética propia del módulo; E4.3
podrá sustituirla por `nucleo/fonetica.py`), `afecta_negacion_numero_lateralidad`
(reutiliza `morfologia.tiene_numero`; negación y lateralidad con listas propias del
módulo, ver bitácora), `clasificar` (cubo revertir/aceptar/revisar), `construir_tabla`,
`escribir` (vía `nucleo/salida.EscritorCSV`), `main` (`--csv`, `--salida`, `--top`).
`FREQ_ORIGINAL_RARA = 2`, `FREQ_CORRECCION_ESTABLECIDA = 50`,
`DISTANCIA_MAXIMA_ACEPTAR = 2`, `RIESGO_CUBO`. Escribe `PARES_CORRECCION` (constante
propia del módulo, pendiente de mover a `rutas.py`; ver §5). Lee `TRIAGE_LIMPIO`.

**`metricas.py`** (427) `[G]` — Métricas del corrector sobre un conjunto de gold (E2.2):
precisión y cobertura de detección y de corrección, F0.5, `tasa_intervencion`, CER/WER de
control, `acuerdo_motivo` (Jaccard de `motivo_span` contra `texto_embedding`) y kappa de
Cohen entre dos anotadores sobre `gravedad` (para E0.6). `mapa_cambios` (alineación por
`difflib.SequenceMatcher` entre `texto_original` y cada uno de `texto_correcto` /
`texto_corregido`; definición completa en la bitácora del ítem), `evaluar_nota`,
`evaluar_conjunto`, `cohen_kappa`, `version_corrector` (lee `procesar.py` con una
expresión regular en vez de importarlo: importar `NLP.procesar` tarda ~5,4 s por
spaCy/LanguageTool/sklearn). `main` (`--gold`, `--csv` con `TRIAGE_LIMPIO` por defecto,
`--guardar`, `--item`, `--comentario`, `--kappa-a`, `--kappa-b`). Lee `TRIAGE_LIMPIO`
(solo lectura) y el CSV de `--gold`; con `--guardar` escribe
`salidas/metricas/<fecha>-<item>.json` y una fila en `salidas/metricas/historico.csv`
(vía `nucleo/salida.EscritorCSV`).

### 2.10 `reparacion/`

**`reparar.py`** (329) — Reprocesa `triage_limpio.csv` usando `texto_original` como
entrada y las funciones de `procesar.py` (sin duplicar fases). `reparar`,
`cargar_recursos` (mismo orden de carga que una corrida normal), `cargar_frecuencias`
(BD; el CSV como respaldo), `comparar`, `escribir_informe`, `main` (`--limite`,
`--aplicar`, `--con-llm`, `--csv`). Escribe `triage_reparado.csv` e
`informe_reparacion.csv` (rutas definidas aquí, no en `rutas.py`; ver §5) y, con
`--aplicar`, una copia `triage_limpio.previo-<sello>.csv`.

**`comparacion.py`** (141) — `clasificar(vieja, nueva)` → categoría en orden de
gravedad (`perdio_motivo`, `recupero_motivo`, `ortografia`, `normalizacion`, `intacta`)
y detalle; `resumir`. La terminología se cuenta solo si los léxicos de `depuracion` y
`reduccion` coinciden.

**`revision.py`** (E0.2) — Lee `informe_reparacion.csv` y lo deja revisable: recuento
por categoría, comprobación de `recupero_motivo > perdio_motivo` y la lista **completa**
de términos perdidos con su frecuencia y cuántas veces se recuperan en otras notas
(`reparar.py` solo imprime los 25 más frecuentes, y el criterio de E0.2 exige juzgarlos
todos). `--termino <t>` muestra las notas donde se pierde ese término, con el contexto
antes y después. No escribe nada.

### 2.11 `tests/`

Pruebas de regresion (E2.1). Se ejecutan con `python -m pytest NLP/tests -q`
desde la raiz del repositorio; sin LanguageTool (sustituto en `conftest.py`),
sin base de datos ni Ollama, con los lexicos y modelos reales del repo
(`salidas/`, `datos/`), leidos y nunca escritos. `NLP/tests/datos/` guarda las
notas sinteticas y el CSV esperado; `__init__.py` solo tiene el docstring del
paquete y no exige ficha.

**`conftest.py`** (fixtures) — Sustituto de LanguageTool (`LanguageToolFalso`,
conoce solo las erratas de los casos fijos), carga de los lexicos reales una
vez por sesion (`recursos_reales`), lectura de las notas sinteticas
(`notas_sinteticas_df`) y una corrida real de las fases 1-5 sobre ellas
(`pipeline_resultado`, `nota`). Desactiva la capa de contexto (roberta) y
`procesar.USAR_CACHE`, para no tocar `salidas/cache_correcciones.json`.

**`test_requisitos.py`** — `nucleo/requisitos.exigir()` detiene la corrida si
falta un artefacto exigido (monkeypatch sobre `requisitos.ARTEFACTOS`).

**`test_alarmas.py`** (E2.0) — `alarmas.reiniciar()` vacia los contadores; dos
"corridas" en el mismo proceso no acumulan si se llama entre ellas; y
`procesar.main()` / `reparar.main()` la invocan al empezar (comprobado sobre
el codigo fuente con `inspect`, sin ejecutar `main()` completo).

**`test_csv_escritura.py`** (E0.4) — `reparacion/reparar.escribir_csv()` y
`escribir_reparado()` producen el mismo CSV, byte a byte, que escribir con
`nucleo/salida.EscritorCSV` directo (como hace `procesar.py`).

**`test_coherencia.py`** — Casos fijos de la fase 2b: `deposion` a
`deposicion` no se revierte; `ahogado` a `abogado` y `volcamiento` a
`tocamiento` si, sobre `coherencia.juzgar()` y `revisar()`.

**`test_correccion.py`** — Casos fijos de la fase 2 sobre las notas
sinteticas, via `pipeline_resultado`: `dolro` a `dolor`, `anuseas` a
`nauseas`, y `ahogado`/`volcamiento`/`mareado`/`tosiendo` intactos.

**`test_depuracion_reduccion.py`** — `comisura labial` conservada por la fase
5 (`reduccion.recortar`); tramite puro marcado por la fase 4
(`depuracion.evaluar`), aislado del ruido que el lexico curado real introduce
en las notas sinteticas de tramite (ver bitacora 2026-09-16-E2.1.md, hallazgo).

**`test_pipeline_completo.py`** — Fases 1-5 sobre las 50 notas sinteticas,
byte a byte contra `tests/datos/triage_esperado.csv` fijado a mano.

## 3. Grafo de dependencias

Importaciones internas (dif. = diferida dentro de una función; rompe un ciclo).

```
procesar    -> rutas, depuracion, evaluacion.auditoria, fase1.limpieza,
               fase2.{coherencia, ortografia, terminologia}, fase3.normalizacion,
               nucleo.{cache, datos, reglas, requisitos, progreso, salida},
               reduccion.{extractor, reduccion}, recursos.casing
               dif.: fase2.contexto, nucleo.conexion_bd
ortografia  -> fase1.limpieza, candidatos, contexto, enmascarado, pesos, sugerencias,
               terminologia, vocabulario, nucleo.{linguistica, lt_compat, reglas},
               recursos.{casing, lexico}
pesos       -> nucleo.{linguistica, morfologia, reglas}, recursos.{casing, lexico}
enmascarado -> pesos, terminologia, nucleo.{linguistica, morfologia, reglas}, recursos.lexico
candidatos  -> terminologia, nucleo.reglas
vocabulario -> terminologia, nucleo.{linguistica, morfologia, reglas}
sugerencias -> candidatos, vocabulario, nucleo.{linguistica, morfologia}, recursos.lexico
terminologia-> alarmas, nucleo.{linguistica, morfologia, reglas}; dif.: candidatos
alarmas     -> nucleo.morfologia
coherencia  -> pesos, sugerencias, nucleo.{linguistica, morfologia, reglas},
               recursos.casing; dif.: depuracion
contexto    -> dif.: nucleo.morfologia
normalizacion -> rutas, nucleo.reglas, recursos.ambiguedad
depuracion  -> rutas, nucleo.morfologia, recursos.lexico; dif.: nucleo.clinico (tablas)
reduccion   -> rutas; dif.: reduccion.frases
frases      -> rutas; dif.: depuracion, reduccion
extractor   -> dif.: depuracion
reglas      -> rutas, nucleo.{linguistica, morfologia}, recursos.casing
requisitos  -> rutas
lexico      -> rutas, nucleo.morfologia
casing      -> rutas, nucleo.morfologia; dif.: nucleo.conexion_bd
corpus_lexico -> rutas; dif.: nucleo.conexion_bd
ambiguedad  -> nucleo.linguistica; dif.: nucleo.lt_compat
auditoria   -> rutas; dif.: fase2.pesos, nucleo.reglas
escaneo     -> rutas, nucleo.morfologia; dif.: nucleo.{linguistica, reglas, conexion_bd}
referencia  -> rutas, nucleo.morfologia
paridad_docs -> rutas
pares       -> rutas, nucleo.{morfologia, reglas, salida}
metricas    -> rutas, nucleo.salida
reparar     -> procesar, rutas, depuracion, ortografia, normalizacion,
               nucleo.{reglas, requisitos, progreso}, recursos.casing,
               reduccion.{extractor, reduccion}, reparacion.comparacion; dif.: conexion_bd
comparacion -> dif.: depuracion, reduccion
revision    -> rutas, reparacion.comparacion
detectar_siglas -> rutas; dif.: ambiguedad, ortografia, vocabulario, candidatos, reglas,
                   conexion_bd, procesar
extraer_cie10   -> rutas
descargar       -> rutas
```

Módulos hoja: `rutas`, `morfologia`, `linguistica`, `clinico`, `cache`, `datos`,
`conexion_bd`, `salida`, `progreso`, `lt_compat`, `limpieza`.

Ciclos, todos rotos con importaciones diferidas: `terminologia ↔ candidatos`,
`reduccion ↔ frases`, `depuracion ↔ {coherencia, extractor, frases, comparacion}`,
`procesar ← {reparar, detectar_siglas}`.

## 4. Entradas y salidas

**Base de datos**: `DIM_TRIAGE.HCTMOTCON`, llave `OID`, filtro `IS NOT NULL AND
LTRIM(RTRIM(...)) <> ''`. Leen la tabla: `procesar.py`, `recursos/casing.py` (completa),
`evaluacion/escaneo.py --bd`, `recursos/detectar_siglas.py`, `reparacion/reparar.py`
(frecuencias), `recursos/corpus_lexico.py` (completa; E3.3, con respaldo en
`TRIAGE_LIMPIO` si la base no responde).

**`datos/`** (versionado): `Clasif_Inter_Enfer_CIE_10_rev_3_ed.diag.pdf` (7,2 MB),
`diccionario_coloquial.json`, `diccionario_siglas.json`, `frases_etiquetadas.csv`
(1,4 MB, curado a mano), `lexico_externo.txt`, `referencia_correcciones.json`,
`recursos_manifiesto.json` (14 recursos registrados el 2026-09-16: url, fuente_oficial,
licencia, sha256, tamaño, fechas, `archivos_extraer`, `estado`; ver `recursos/descargar.py`
y REFERENCIAS.md §2). `datos/lexicos/` (E3.2, E3.3): `siglas_protegidas.txt` (40 formas
a mano, cabecera con fuente y criterio; la lee `nucleo/reglas.cargar_siglas_protegidas`),
`corpus_frecuencia.tsv` (`forma\tfrecuencia`; la lee `recursos/corpus_lexico.py`).

**`recursos_externos/`** (generado por `recursos/descargar.py`, ignorado por git): un
subdirectorio por recurso del manifiesto; solo el archivo descargado (y, si el
manifiesto lo pide, lo extraído del ZIP). Se reobtiene con `python -m
NLP.recursos.descargar --solo <nombre>`.

**`salidas/`** (generado):

| Archivo | Escritor | Columnas |
|---|---|---|
| `triage_limpio.csv` | `procesar.py` | `OID, texto_original, texto_corregido, texto_normalizado, texto_embedding` |
| `notas_descartadas.csv` | `procesar.py` | `OID, texto_original, texto_normalizado, motivo_descarte` |
| `reporte_cambios.csv` | `evaluacion/auditoria.py` | `fase, original, corregido, veces, oid_ejemplo` |
| `cache_correcciones.json` | `nucleo/cache.py` | `{version\x00texto\x00protegidos: corregido}` |
| `lexico_clinico.json` | `recursos/lexico.py` | `terminos: {clave: [forma, fuente]}` |
| `lexico_casing.json` | `recursos/casing.py` | `lexico: {token: clase}`, `observaciones` |
| `clasificador_frases.joblib` | `reduccion/frases.py` | regresión logística |
| `triage_reparado.csv`, `informe_reparacion.csv` | `reparacion/reparar.py` | como `triage_limpio`; `OID, categoria, detalle, embedding_antes, embedding_despues` |
| `pares_correccion.csv` | `evaluacion/pares.py` | `original, correccion, ocurrencias, freq_original, freq_correccion, distancia, fonetica_igual, cubo, decision_humana` |
| `metricas/<fecha>-<item>.json`, `metricas/historico.csv` | `evaluacion/metricas.py` | JSON: doce claves de `PLAN.md` §4.5 más `cer`, `wer`; CSV: `fecha, item, version_corrector, F0.5, precision_deteccion, cobertura_deteccion, precision_correccion, cobertura_correccion, tasa_intervencion, acuerdo_motivo, notas, comentario` |
| `siglas_detectadas.csv`, `muestra_revision.csv`, `referencia.csv` | scripts de `recursos/` y `evaluacion/` | no existen en disco hoy |

Formato de escritura: `nucleo/salida.py` produce utf-8-sig, CRLF, QUOTE_ALL;
`reparar.py` usa pandas (QUOTE_MINIMAL) — se unifica en E0.4.

## 5. Observaciones para el refactor (E6)

Duplicaciones detectadas:

- `texto_gritado` / proporción de mayúsculas: cuatro implementaciones (`reglas`,
  `casing`, `auditoria._gritado`, `escaneo` en línea), umbral 0,9 declarado tres veces.
- `sin_tildes`: la canónica en `morfologia`, una copia en `auditoria._sin_tildes` (pliega
  también la ñ, a propósito) y otra en línea en `reduccion._es_clinica`.
- `_es_expansion`: `ortografia` (`len(c) > 2·len(o)`) y `contexto` (`>=`), criterios
  distintos en el borde.
- Léxico clínico: `reduccion.py` carga `lexico_clinico.json` por su cuenta en vez de usar
  `recursos/lexico.py` como `depuracion.py`; dos criterios de "palabra clínica" que no
  coinciden.
- `VACIAS` y `RESPUESTAS_VACIAS`: casi idénticas en `depuracion` y `reduccion`, con
  diferencias sutiles.
- Marcadores institucionales: `reduccion.MARCADORES_INSTITUCIONALES` (18) y
  `escaneo.MARCAS_INSTITUCIONALES` (10), solapados.
- `RE_ENCABEZADO`: cuatro variantes (`limpieza`, `normalizacion`, `depuracion`,
  `reduccion`) mientras `nucleo/clinico.SECCIONES` es la tabla canónica y solo la usa
  `depuracion`.
- Criterios de daño: `coherencia.juzgar` y `auditoria.motivo_dano` con los mismos
  umbrales, implementados por separado.
- Distancia de edición: `rapidfuzz` (reglas, morfologia, coherencia), Damerau propio en
  `contexto` (47 líneas), Levenshtein propio en `auditoria`; los dos últimos difieren.

Código sin llamadas — inventario reverificado por grep en E6.3
(`bitacora/2026-09-16-E6.3.md`, tabla completa con la evidencia archivo:línea):
eliminadas por confirmarse sin ninguna referencia y no ser `diagnosticar()` ni
reexportación: `linguistica.iniciar`, `limpieza.normalizar_token`,
`contexto.es_sospechosa`, `depuracion.util`, `casing.es_nombre_propio`. Dos entradas de
esta lista resultaron obsoletas: `alarmas.reiniciar` sí se invoca (`procesar.main()` y
`reparar.main()`, desde E2.0) y `lexico.forma` sí se usa (dentro de `lexico.diagnosticar()`);
se retiran del inventario. Reclasificadas como herramienta de inspección manual, igual
que un `diagnosticar()` (se conservan): `terminologia.explicar`, `contexto.esperado`.
Sin resolver, requieren decisión del propietario (E6.3 no las toca): `ortografia.resumen_contexto`
y `normalizacion.desactivadas` / `con_contexto` prometen en su docstring alimentar "el
informe de auditoría" pero nada las llama — o se conectan o se corrige el docstring;
`linguistica.entidades_lote` (posible optimización de lote sin conectar a `procesar.py`);
`coherencia.sin_corregir` y `pesos.protegida` (archivos fuera de alcance de E6.3, ver
briefing); todo `nucleo/clinico.py` salvo `SECCIONES` / `SECCIONES_NO_CLINICAS` y las
funciones de las que depende su propio `diagnosticar()` (256 líneas que cargan spaCy +
medspaCy; decisión pendiente: mantener como herramienta documentada o recortar en un
ítem dedicado, no en este).

Parámetro muerto: `reduccion.recortar(texto, agresivo=True)` — punto de contacto
protegido (`PLAN.md` §7) — nunca lee `agresivo` en su cuerpo; siempre intenta la pasada
agresiva y luego la suave sin mirar el argumento. No se toca la firma (contrato externo);
ver bitácora E6.3.

Docstring corregido en E6.3: `fase2_ortografia/sugerencias.py` afirmaba que "el sistema
se abstiene" cuando ninguna fuente aporta una forma correcta; la garantía es solo de ese
módulo (la capa de contexto). LanguageTool y SymSpell corrigen antes, por su cuenta, sin
pasar por `sugerencias.py`: 409 pares de `salidas/pares_correccion.csv` tienen
`freq_correccion = 0` (ninguna aparición en `texto_original`), de los cuales 120 tampoco
están en `lexico_clinico.json`. Detalle en `bitacora/2026-09-16-E6.3.md`.

Rutas fuera de `rutas.py`: `triage_reparado.csv`, `informe_reparacion.csv`,
`triage_limpio.previo-<sello>.csv` (definidas en `reparar.py`); `pares_correccion.csv`
(definida en `evaluacion/pares.py`, E2.4; debería pasar a `rutas.py`).

Salidas declaradas y nunca generadas: `siglas_detectadas.csv`, `muestra_revision.csv`,
`referencia.csv`. La ausencia de la muestra hace fallar `evaluacion/referencia.py`.

Documentación desactualizada: `NLP/__init__.py` y `NLP/README.md` describen "fases 1 a
3" y "tres columnas"; el README dice que la fase 4 elimina notas (las señala); no
menciona `reparacion/` ni la fase 2b; `rutas.DOCS` no se usa.

## 6. Guía de estilo

Rige para todo archivo nuevo o modificado de `NLP/`. E1.5 la aplica al código
existente; los gates de etapa (`PLAN.md` §4.2) la verifican con
`evaluacion/paridad_docs.py --estricto`.

### 6.1 Nombres, idioma y tamaño

| Regla | Detalle |
|---|---|
| Idioma | Código, nombres de módulos, funciones, variables, constantes, mensajes y documentación en español. |
| Tildes | Los comentarios y docstrings del código se escriben sin tildes (convención observada en todo el repositorio; evita fallos de consola en cp1252). La documentación de `docs/` sí las lleva. |
| Nombres | `snake_case` para módulos, funciones y variables; `MAYUSCULAS` para constantes de configuración; sin abreviaturas que el paquete no use ya. |
| Tamaño | Un archivo no supera las 400 líneas. Los marcados `[G]` en §2 se dividen en E6; ningún archivo nuevo nace por encima del límite. |
| Puntos de entrada | Un módulo ejecutable expone `main()` con `argparse`, se ejecuta con `python -m NLP.<paquete>.<modulo>` desde la raíz del repositorio y reconfigura `sys.stdout` a utf-8. |

### 6.2 Rutas, datos y salidas

| Regla | Detalle |
|---|---|
| Origen de rutas | `rutas.py` es el único módulo que sabe dónde vive cada archivo. Ningún otro construye rutas con `Path(__file__)` ni concatena `"datos"` o `"salidas"`. Una ruta nueva se declara allí, con el comentario del script que la escribe. |
| `datos/` | Se edita a mano y se versiona. Si se borra, se pierde trabajo humano. Ningún script lo escribe salvo que su ficha en §2 lo diga expresamente (`frases.construir_datos` es el caso conocido). |
| `salidas/` | Lo produce un script y está ignorado por git. Si se borra, se regenera. Los artefactos de un ítem van a `salidas/<subcarpeta-del-item>/`. |
| Escritura de CSV | Siempre con `nucleo/salida.py` (`EscritorCSV`: utf-8-sig, CRLF, QUOTE_ALL). No se escribe CSV con `pandas.to_csv` ni con `csv.writer` directo. |
| Otros formatos | Métricas, léxicos, manifiesto de recursos y conjunto de evaluación siguen `PLAN.md` §4.5. |

### 6.3 Documentación en el código

| Elemento | Regla |
|---|---|
| Docstring de módulo | ≤ 5 líneas: qué hace, ítem del plan si procede, y el documento de `docs/` donde está la explicación. |
| Docstring de función | ≤ 3 líneas: qué devuelve o qué efecto tiene. Sin ejemplos ni historia. |
| Comentarios | Aclaran un paso no evidente. Sin narrativa de incidentes, sin cifras medidas, sin fechas: eso va a `decisiones/` y `bitacora/`. |
| Banderas de configuración | Constantes en mayúsculas al inicio del módulo, tras las importaciones, una por técnica (`PLAN.md` §3, principio 8), enumeradas en la ficha del archivo en §2. |
| Ejemplos de notas | Anonimizados o sintéticos; nunca un OID ni texto identificable, ni en código, ni en pruebas, ni en documentación (principio 7). |
| Pruebas | En `NLP/tests/`, con `pytest`; una prueba por comportamiento observable, con datos sintéticos. |

### 6.4 Cómo documentar un archivo nuevo

1. Ficha en §2, dentro de la subsección `### 2.x \`carpeta/\`` que le corresponde (los
   de la raíz, en §2.1), con el formato `**\`archivo.py\`** (líneas) — función,
   interfaz pública, configuración, artefactos`. El nombre es el corto, sin carpeta.
2. Si la carpeta es nueva: subsección nueva en §2 y línea en el mapa de §1.
3. Línea en el grafo de §3 con sus importaciones internas.
4. Fila en §4 si lee la base de datos o escribe un artefacto.
5. Fila en `Historial`.
6. Ejecutar `python -m NLP.evaluacion.paridad_docs --estricto`.

`paridad_docs.py` lee las fichas de §2 con esa convención (subsección de carpeta +
nombre corto) y las compara con `NLP/**/*.py`. Reglas: excluye `__pycache__` y
entornos virtuales; un `__init__.py` que solo contiene el docstring del paquete no
exige ficha (hoy, los diez), y en cuanto tenga código la exige; una ficha escrita como
`carpeta/archivo.py` se acepta con la carpeta indicada. Informa **faltantes** (archivo
sin ficha), **huérfanas** (ficha sin archivo, o fuera de una subsección de carpeta),
fichas duplicadas y documentos de `docs/*.md` sin `## Historial`. Con `--estricto`
devuelve código de salida 1 si hay faltantes, huérfanas o documentos sin `Historial`;
`--doc <ruta>` comprueba otro documento (para pruebas). Forma parte del gate de todas
las etapas (`PLAN.md` §4.2).


## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | previo al plan | Primera versión |
| 2026-09-15 | E0.2 | Nuevo `reparacion/revision.py`: ficha en §2.10, entrada en §1 y §3 |
| 2026-09-15 | E1.2, E1.6 | Nuevo `evaluacion/paridad_docs.py`: ficha en §2.9 y línea en §3; §6 redactada (guía de estilo, sustituye el texto provisional) |
| 2026-09-16 | E2.4 | Nuevo `evaluacion/pares.py`: ficha en §2.9, línea en §3, fila en §4 (`pares_correccion.csv`) y nota en §5 (ruta fuera de `rutas.py`) |
| 2026-09-16 | E2.2 | Nuevo `evaluacion/metricas.py`: ficha en §2.9, línea en §3, fila en §4 (`metricas/<fecha>-<item>.json`, `metricas/historico.csv`); nuevas constantes `rutas.METRICAS` y `rutas.GOLD_V0` |
| 2026-09-16 | E3.1 | Nuevo `recursos/descargar.py` y `datos/recursos_manifiesto.json`: ficha en §2.8, línea en §3, entradas en §1 y §4 (`recursos_externos/`, ignorado por git). `RECURSOS_EXTERNOS` y `MANIFIESTO` quedan definidos en el propio módulo, no en `rutas.py` (pendiente, ver bitácora) |
| 2026-09-16 | E2.0, E2.1 | Nueva carpeta `tests/` (pytest): entrada en §1, subsección §2.11 con `conftest.py` y siete `test_*.py`. `procesar.main()` y `reparar.main()` llaman a `alarmas.reiniciar()` al empezar (E2.0); sin ficha propia, no cambian su interfaz |
| 2026-09-16 | E5.1 | `SEPARAR_CONCEPTO` nueva en `fase3_normalizacion/normalizacion.py` (§2.5) y `QUITAR_GLOSA` nueva en `reduccion/reduccion.py` (§2.7), las dos `False` por defecto; decisión en `decisiones/2026-09-16-E5.1-glosas.md` |
| 2026-09-16 | E3.2 | Nuevo `datos/lexicos/siglas_protegidas.txt` (40 formas); `nucleo/reglas.py` (§2.2): `cargar_siglas_protegidas`, `SIGLAS_PROTEGIDAS_MANUAL`, bandera `PROTEGER_SIGLAS_LISTA_MANUAL`; `fase2_ortografia/pesos.py` (§2.4): `peso()` reconoce la misma lista (motivo `sigla_protegida_manual`). Fila en §4 (`datos/lexicos/`). Bitácora `bitacora/2026-09-16-E3.2.md` |
| 2026-09-16 | E6.3 | §5 reverificada por grep (inventario de código sin llamadas corregido: dos entradas obsoletas retiradas, cinco funciones y sus imports huérfanos eliminados, dos reclasificadas como herramienta de inspección); nuevo hallazgo de parámetro muerto (`reduccion.recortar`) y de docstring corregido (`fase2_ortografia/sugerencias.py`). Bitácora `bitacora/2026-09-16-E6.3.md` |
| 2026-09-16 | E3.3 | Nuevo `recursos/corpus_lexico.py` (ficha en §2.8, línea en §3) y `datos/lexicos/corpus_frecuencia.tsv` (34.602 formas, contado sobre la BD completa; fila en §4). Umbral `coherencia.FRECUENCIA_RESPALDO_CORPUS` medido con las frecuencias del corpus completo; recomendación en `bitacora/2026-09-16-E3.3.md` (no se edita `coherencia.py` en este ítem) |
