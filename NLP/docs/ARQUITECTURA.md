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
  recursos/            constructores de léxicos y diccionarios
  evaluacion/          auditoría de corridas, escaneo del corpus, referencia anotada
  reparacion/          reprocesa un CSV existente y compara
  datos/               curado a mano, versionado
  salidas/             generado por scripts, ignorado por git
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

**`reglas.py`** (313) — Qué tokens no se corrigen nunca. `cargar` (lee
`diccionario_siglas.json` y llena `SIGLAS`, `EXPANDIBLES`, `DIRECTAS`, `PATRONES`),
`esta_protegido`, `detectar_protegidos` (mayúsculas informativas del original),
`entidades` (spaCy confirmado por corpus o vocabulario), `es_palabra_conocida`,
`forma_aceptable`, `texto_gritado`. Reexporta de `morfologia` (`sin_tildes`, `morfemas`,
`normalizar`…): esas importaciones no son inertes. Configuración: `LONGITUD_MINIMA = 5`,
`DISTANCIA_MAXIMA = 2`, `PROPORCION_MAYUSCULAS = 0.9`, `USAR_SPACY`,
`PROTEGER_ENTIDADES`.

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

**`pesos.py`** (204) — Peso clínico de cada palabra antes de que el corrector la vea.
`peso` → (peso, motivo), `protegida`, `pesar_texto`, `usar_conteo`, `frecuencia`.
Tabla `PESOS` (diccionario/catálogo/externo 0,95; fármaco 0,90; morfemas 0,70; sigla
del corpus 0,60; biomédico 0,45; jerga frecuente 0,40; número 1,00).
`UMBRAL_PROTECCION = 0.5`, `FRECUENCIA_JERGA = 8`.

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

**`normalizacion.py`** (342) — Traduce habla del paciente y siglas a terminología,
anotando entre paréntesis (`MODO = "anotar"`), con control de ambigüedad por entrada
(`recursos/ambiguedad.py`). `cargar`, `normalizar`, `expandir_encabezados`,
`disponible` (False hasta llamar a `cargar`), `desactivadas`, `con_contexto`. Lee
`diccionario_coloquial.json` y `diccionario_siglas.json`.

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

**`reduccion.py`** (864) `[G]` — Fase 5 por reglas: quita bloques que no son motivo de
consulta (institucional, trámite, examen físico, conducta, antecedentes, acompañante,
lugares, preámbulo temporal, demografía). `recortar(texto, agresivo)` (pasada agresiva
y suave; acepta la que no deja costuras), `cargar_lexico`, `cargar_lugares`,
`densidad_clinica`, `crea_costura`, `sin_reducir`, `diagnosticar` (no incluye el paso
del clasificador). `PALABRAS_ORACION_LARGA = 8`, `DENSIDAD_MINIMA = 0.40`,
`TOPE_PALABRAS = 60`, `FUENTES_CURADAS`. Mantiene su propio `_LEXICO` y `_es_clinica`
leyendo `lexico_clinico.json` directamente (duplica `recursos/lexico.py`; ver §5).
Freno por densidad al clasificador: `decisiones/2026-09-15-clasificador-freno-clinico.md`.

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
ambiguedad  -> nucleo.linguistica; dif.: nucleo.lt_compat
auditoria   -> rutas; dif.: fase2.pesos, nucleo.reglas
escaneo     -> rutas, nucleo.morfologia; dif.: nucleo.{linguistica, reglas, conexion_bd}
referencia  -> rutas, nucleo.morfologia
reparar     -> procesar, rutas, depuracion, ortografia, normalizacion,
               nucleo.{reglas, requisitos, progreso}, recursos.casing,
               reduccion.{extractor, reduccion}, reparacion.comparacion; dif.: conexion_bd
comparacion -> dif.: depuracion, reduccion
detectar_siglas -> rutas; dif.: ambiguedad, ortografia, vocabulario, candidatos, reglas,
                   conexion_bd, procesar
extraer_cie10   -> rutas
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
(frecuencias).

**`datos/`** (versionado): `Clasif_Inter_Enfer_CIE_10_rev_3_ed.diag.pdf` (7,2 MB),
`diccionario_coloquial.json`, `diccionario_siglas.json`, `frases_etiquetadas.csv`
(1,4 MB, curado a mano), `lexico_externo.txt`, `referencia_correcciones.json`.

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

Código sin llamadas (además de los `diagnosticar()` de inspección manual, que se
declaran como tales): `alarmas.reiniciar` (documentado como parte de la corrida; nunca
se invoca), `ortografia.resumen_contexto` (documentado como parte del informe; ausente),
`normalizacion.desactivadas` / `con_contexto` (nadie las imprime), `coherencia.sin_corregir`,
`pesos.protegida`, `linguistica.entidades_lote` / `iniciar`, `limpieza.normalizar_token`,
`terminologia.explicar`, `contexto.es_sospechosa` / `esperado`, `depuracion.util`,
`lexico.forma`, `casing.es_nombre_propio`, y todo `nucleo/clinico.py` salvo sus dos
tablas (256 líneas que cargan spaCy + medspaCy sin uso).

Rutas fuera de `rutas.py`: `triage_reparado.csv`, `informe_reparacion.csv`,
`triage_limpio.previo-<sello>.csv` (definidas en `reparar.py`).

Salidas declaradas y nunca generadas: `siglas_detectadas.csv`, `muestra_revision.csv`,
`referencia.csv`. La ausencia de la muestra hace fallar `evaluacion/referencia.py`.

Documentación desactualizada: `NLP/__init__.py` y `NLP/README.md` describen "fases 1 a
3" y "tres columnas"; el README dice que la fase 4 elimina notas (las señala); no
menciona `reparacion/` ni la fase 2b; `rutas.DOCS` no se usa.

## 6. Guía de estilo

Pendiente (E1.6). Provisionalmente rigen las convenciones observadas: nombres en
español; `rutas.py` como único origen de rutas; `datos/` a mano y versionado,
`salidas/` generado; un punto de entrada por fase con `python -m`; CSV en utf-8-sig
mediante `nucleo/salida.py`; docstrings breves (qué hace), explicaciones en `docs/`.


## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | previo al plan | Primera versión |
