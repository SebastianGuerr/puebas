# Flujo del pipeline de triage

Ítem E1.3 del plan (`PLAN.md` §8). Describe qué le pasa a una nota, fase por fase,
en el orden real en que `NLP/procesar.py` las aplica (función `procesar_bloque`,
`procesar.py:313-471`). No sustituye la lectura del código: cuando una cifra falta,
se anota "sin medición" a propósito, porque es información que el propietario del
proyecto pidió ver.

**Aviso sobre los ejemplos de este documento.** Los tres ejemplos son notas
**sintéticas** (inventadas para este documento, no proceden de ningún paciente ni
de la base de datos), ejecutadas de verdad con
`C:\Users\ad6708\Documents\puebas\.venv\Scripts\python.exe` el 2026-09-16. La fase 2
completa exige un servidor de LanguageTool (Java) y frecuencias contadas sobre la
base de datos; para no levantar ese servidor junto al job de reparación que corría
en segundo plano durante la redacción de este documento, los ejemplos de la fase 2
usan solo la capa de **enmascarado clínico** (`fase2_ortografia/enmascarado.py`),
que no requiere ni LanguageTool ni la base de datos. Se indica en cada caso qué
capas no se ejecutaron. El script de la demostración es
`evaluacion/../scratchpad/flujo_demo.py` (fuera del paquete, no se versiona); su
salida se pega literal más abajo.

## 1. Recorrido de una nota

Columnas que nacen en cada fase, en el orden de `procesar_bloque`:

| Orden | Fase | Función | Columna que nace | Se sobreescribe después |
|---|---|---|---|---|
| 1 | 1. Limpieza | `preparar()` (`procesar.py:232-251`) | `texto_limpio`, `texto_norm`, `clave` | `texto_norm` no; es la base fija de comparación |
| 2 | 2. Ortografía | `procesar_bloque()`, bloque fase 2 | `texto_corregido`, `texto_original` (copia de `HCTMOTCON`) | sí, por la fase 2b |
| 3 | 2b. Coherencia | `procesar_bloque()`, bloque fase 2b | `texto_corregido` (revisado) | no |
| 4 | 3. Normalización | `procesar_bloque()`, bloque fase 3 | `texto_normalizado` | no |
| 5 | 4. Depuración | `procesar_bloque()`, bloque fase 4 | `util` (interno), `motivo_descarte` | sí, la fase 5 le añade el motivo del modelo con `\|` |
| 6 | 5. Reducción | `procesar_bloque()`, bloque fase 5 | `texto_embedding`, `motivo_llm` | no |

Columnas finales escritas en `salidas/triage_limpio.csv`: `OID, texto_original,
texto_corregido, texto_normalizado, texto_embedding` (`rutas.py`, tabla en
`ARQUITECTURA.md` §4). `texto_limpio`, `texto_norm`, `clave`, `util` y
`motivo_llm` son columnas de trabajo que no llegan al CSV; `motivo_descarte` solo
se escribe en `salidas/notas_descartadas.csv`, indexado por `OID` contra el CSV
principal (todas las notas señaladas siguen también en `triage_limpio.csv`).

## 2. Fase 1 — Limpieza de formato

**Entrada**: `HCTMOTCON` tal cual llega de la base de datos (o `texto_original` en
una reparación). **Salida**: `texto_limpio` (minúsculas, forma normalizada) y
`texto_norm` (mismo texto con las mayúsculas del original conservadas, usado más
adelante como fuente de nombres propios). No corrige ninguna palabra ni cambia el
orden del texto: solo forma.

**Artefactos que consume**: ninguno. No depende de ningún archivo de `datos/` ni
`salidas/`.

**Módulo**: `fase1_limpieza/limpieza.py` (254 líneas). Funciones:
`limpiar_conservando_original(texto)` → `(texto_limpio, texto_norm)`; `limpiar()`
hace solo la primera mitad; `es_vacio()` y `analizar()` son de control de calidad.

| Constante | Valor | Archivo:línea | Efecto |
|---|---|---|---|
| `SEPARADOR_LINEA` | `"; "` | `limpieza.py:50` | sustituye el salto de línea, para no romper la segmentación por oraciones de LanguageTool |
| `MAX_REPETICIONES` | `2` | `limpieza.py:51` | `"holaaaaa"` → `"holaa"` |
| `LARGO_MAXIMO` | `20000` | `limpieza.py:52` | trunca notas absurdamente largas |
| `SIMBOLOS_CLINICOS` | `"+?()<>"` | `limpieza.py:68` | se conservan por ser contenido clínico (suma de hallazgos, sospecha, aclaración, comparación) |
| `ENCABEZADOS` | 21 rótulos | `limpieza.py:106-109` | fuerza que cada uno abra línea, esté donde esté en el original |

**Decisiones enlazadas**: ninguna en `decisiones/`; la fase no ha sido objeto de un
experimento medido. **Sin medición** — hallazgo: no hay cifra de línea base
específica de esta fase (la más cercana, `analizar()` sobre el lote, se imprime en
cada corrida pero no se guarda en `decisiones/` ni en `salidas/metricas/`, que
tampoco existe todavía).

**Ejemplo (nota A)**, salida real del script de demostración:

```
original           : PTE FEMENINA 34 A CON DOLOR ABDOMINAL DESDE HACE 2 DIAS, NIEGA FIEBRE. AP: HTA. SE REMITE A CASA DE SALUD PARA CONTROL.
fase1 texto_limpio  : pte femenina 34 a con dolor abdominal desde hace 2 dias, niega fiebre; ap: hta. se remite a casa de salud para control
```

El punto tras `"DIAS,"` se conserva como `;` (separador de apartado) y el resto de
puntuación de frase se conserva tal cual; nótese que `"AP:"` no se separa en línea
propia en este ejemplo por no venir precedido de salto de línea en el original
(regla `RE_ENCABEZADO`, `limpieza.py:110-113`, exige que el rótulo no esté ya al
inicio de línea; aquí lo fuerza igual porque el patrón no exige inicio de línea,
solo lo antepone con `\n` — en una nota de una sola línea el efecto visible es
solo la conservación del `:`).

**Por qué se conserva cada símbolo** (trasladado del docstring de `limpieza.py`,
E1.5):

- Puntuación de frase (`. , ; :`): LanguageTool segmenta por oraciones; sin
  puntuación pierde el contexto que necesita para decidir una corrección.
- Barra, porcentaje, grado y decimales (`/ % ° .`): `'120/80'`, `'39.5'` y
  `'95%'` son datos clínicos; al eliminar la barra, `'120/80'` pasa a
  `'120 80'` y deja de leerse como tensión arterial.
- Separación entre apartados: `'AP: HTA'` y `'AA: NIEGA'` fundidos en una sola
  línea pierden la frontera entre antecedentes patológicos y alérgicos, que
  las fases siguientes necesitan para acotar el alcance de la negación.
- `texto_norm` (segundo valor de `limpiar_conservando_original`) conserva las
  mayúsculas del original porque son la única señal de que un término es un
  nombre propio y no un error de digitación.

## 3. Fase 2 — Corrección ortográfica

**Entrada**: `texto_limpio` (con `texto_norm` como fuente auxiliar de mayúsculas).
**Salida**: `texto_corregido`. Orquestador: `fase2_ortografia/ortografia.py`,
función `corregir(texto, texto_original)` (`ortografia.py:550-676`).

**Artefactos que consume**:

| Artefacto | Comando que lo regenera | Qué decide |
|---|---|---|
| `datos/diccionario_siglas.json` | se edita a mano | `SIGLAS`, `DIRECTAS`, `PATRONES`, `EXPANDIBLES` (`nucleo/reglas.py:cargar`) |
| `salidas/lexico_clinico.json` | `python -m NLP.recursos.lexico` | qué palabras no llegan al corrector general (peso clínico) |
| `salidas/lexico_casing.json` | `python -m NLP.recursos.casing` | restauración de mayúsculas en siglas; nombres propios del corpus |
| modelo spaCy `es_core_news_md` | `python -m spacy download es_core_news_md` | vocabulario amplio del español y entidades nombradas |
| frecuencias del corpus | se calculan en cada corrida, `procesar.cargar_corpus()` (lee la BD) | desempate entre candidatos, detección de jerga |
| LanguageTool (servicio Java, no archivo) | se descarga solo la primera vez que se instancia `language_tool_python.LanguageTool("es")` | propone candidatos de corrección, categoría `TYPOS` únicamente |
| `PlanTL-GOB-ES/roberta-base-biomedical-clinical-es` (modelo, se cachea en disco tras la primera descarga) | automático al llamar `contexto.iniciar()` | capa de contexto (palabra real mal empleada) |

**Constantes**:

| Constante | Valor | Archivo | Efecto |
|---|---|---|---|
| `CATEGORIAS_PERMITIDAS` | `{"TYPOS"}` | `ortografia.py:64` | LanguageTool solo interviene por ortografía, nunca por concordancia o estilo |
| `USAR_CONTEXTO` | `True` | `ortografia.py:70` | activa/desactiva la capa más cara y más arriesgada |
| `FRECUENCIA_PALABRA_ESTABLECIDA` | `20` | `ortografia.py:86` | una palabra que el corpus repite ≥ 20 veces y spaCy reconoce no se toca en la capa de contexto, salvo que sea abreviatura |
| `RATIO_EXPANSION_MAXIMO` | `2.0` | `ortografia.py:102` | tope de cuánto puede alargar una abreviatura al expandirse |
| `DOMINANCIA_PARA_ESCRIBIR` | `0.85` | `ortografia.py:325` | proporción mínima de mayúscula para restaurar una sigla en nota gritada |
| `UMBRAL_PROTECCION` | `0.5` | `fase2_ortografia/pesos.py:55` | por encima, la palabra no llega al corrector general |
| `FRECUENCIA_JERGA` | `8` | `pesos.py:65` | apariciones mínimas para que una palabra desconocida cuente como jerga del servicio y no como typo |
| `LONGITUD_MINIMA_CORRECCION` | `6` | `fase2_ortografia/enmascarado.py:63` | por debajo, la distancia de edición deja de discriminar |
| `FRECUENCIA_CANDIDATO` | `3` | `fase2_ortografia/candidatos.py:42` | el candidato debe existir en las notas del hospital |
| `FRECUENCIA_DESEMPATE` / `RATIO_DESEMPATE` | `10` / `3` | `candidatos.py:43-44` | entre varios candidatos igual de cerca, uno debe dominar por este margen |
| `UMBRAL_TERMINO` / `FACTOR_TERMINO` | `10` / `5` | `candidatos.py:45-46` | un original repetido y con forma de término exige que la corrección lo supere 5 veces |
| `DISTANCIA_MAXIMA` (SymSpell) | `3` | `fase2_ortografia/vocabulario.py:47` | tope del índice; el `lookup` usa menos según longitud |
| `RATIO_MINIMO` (SymSpell) | `10` | `vocabulario.py:53` | si el original es común, la sugerencia debe superarlo por este factor |
| `UMBRAL_SOSPECHA` / `UMBRAL_GANANCIA` | `-6.0` / `2.0` | `fase2_ortografia/contexto.py:67,73` | umbral de log-probabilidad para marcar sospecha; ganancia mínima del candidato sobre lo escrito |
| `LONGITUD_MINIMA` / `DISTANCIA_MAXIMA` (protección) | `5` / `2` | `nucleo/reglas.py:56-57` | tokens más cortos solo se tocan por corrección directa; ediciones permitidas |

Ninguna de estas constantes de fase 2 (salvo las citadas explícitamente en
`decisiones/`) tiene un registro de medición en `decisiones/`. **Sin medición** —
es el hallazgo más extenso de este documento: la fase con más parámetros del
pipeline (14 constantes solo en la tabla de arriba) es también la que menos
respaldo medido tiene por escrito. El plan lo prevé como trabajo futuro (E4.1-E4.9).

**Subpasos internos, en el orden real de `corregir()`** (`ortografia.py:550-676`):

1. **Protección previa** (`nucleo/reglas.py`): `detectar_protegidos()` (mayúscula
   inicial no explicada por posición, o palabra corta toda en mayúscula, sobre el
   texto original) + `entidades()` (spaCy, confirmado por el corpus o el
   vocabulario) + `tokens_protegidos_por_contexto()` (palabra siguiente a un
   disparador de nombre como "dr", "hospital", "barrio"). Decide qué tokens no
   entrarán en ninguna capa posterior.
2. **Correcciones directas** (`aplicar_directas`): sustituye lo declarado a mano
   en `DIRECTAS`, sin más comprobación. Errores conocidos.
3. **Enmascarado clínico** (`enmascarado.enmascarar`, que internamente llama a
   **pesos** `pesos.peso()` palabra por palabra): aparta del corrector general la
   terminología que ya está en el léxico y, si una palabra pesa como clínica pero
   no está en ningún léxico (mal escrita), busca la forma más cercana en el
   léxico médico y la corrige *ahí mismo*, antes de que LanguageTool la vea. Es
   la capa que decide "esto es terminología, no me lo toques" o "esto es
   terminología mal escrita, la arreglo yo con mi propio diccionario".
4. **LanguageTool**: revisa el texto que salió del enmascarado (con los rangos
   protegidos ya excluidos de facto porque `corregir()` descarta cualquier
   coincidencia dentro de un rango protegido, salvo restauración de tilde).
   Decide candidatos de corrección ortográfica pura.
5. **Guardián clínico + candidatos** (`terminologia.validar/admite`, consultado
   desde `candidatos.elegir`): de las sugerencias de LanguageTool, filtra las que
   violan el criterio clínico (antónimo morfológico, truncamiento, cambio de
   familia o de categoría, fármaco, término contra término) y de las que quedan
   elige por menor distancia y frecuencia en el corpus, o se abstiene.
6. **SymSpell** (`vocabulario.corregir_texto`): solo sobre los tokens que
   LanguageTool marcó y no se corrigieron, para los errores de digitación sobre
   terminología que LanguageTool no reconoce.
7. **Capa de contexto** (`contexto.elegir`, vía `aplicar_contexto`): la más cara;
   ve solo lo que ninguna capa anterior arregló. También pasa por el guardián
   clínico y por `enmascarado.admisible()` para las palabras que forma (no para
   las divisiones en dos palabras).
8. **Restauración de mayúsculas** (`restaurar_mayusculas`): devuelve a mayúscula
   las siglas clínicas, con tres fuentes de evidencia en orden (la nota misma,
   el corpus, el diccionario).
9. **Caché** (`nucleo/cache.py`, invocada desde `procesar.py`, no desde
   `ortografia.py`): envuelve la fase 2 completa, **antes** de que se ejecute
   nada de lo anterior. La clave es `version\x00texto\x00protegidos`
   (`procesar.py:227-229`); si la clave está en `cache_correcciones.json`, la
   fase 2 entera se salta para esa nota. `VERSION_CORRECTOR` (hoy
   `"4-con-spacy-y-coherencia"`, `procesar.py:162`) es lo único que invalida la
   caché entre corridas.

**Ejemplo (nota B)**, salida real — demuestra el límite de esta demostración:

```
original            : nino de 5 anos con cefalea y bomito hace 3 horas, madre refiere que tambien tiene disnea leve
fase2 enmascarado    : nino de 5 anos con cefalea y bomito hace 3 horas, madre refiere que tambien tiene disnea leve
       terminos apartados : ['cefalea', 'disnea', 'hace', 'horas', 'leve', 'madre', 'refiere', 'tambien']
```

`"bomito"` (errata de `"vomito"`) **no se corrige** en esta demostración: el
enmascarado por sí solo no lo arregla (no está en el léxico clínico exacto y la
condición de `admisible()` no se satisface aquí con los datos disponibles sin
corpus de frecuencias cargado). En una corrida real, LanguageTool y/o SymSpell
—que este documento no ejecuta, ver el aviso del encabezado— son las capas que
deberían resolverlo. Queda anotado como limitación de esta demostración, no como
comportamiento verificado de la cadena completa.

## 4. Fase 2b — Coherencia contra la nota original

**Entrada**: `texto_limpio`, `texto_corregido` (salida de la fase 2), `texto_norm`.
**Salida**: `texto_corregido`, reescrito solo donde deshace un cambio. Módulo:
`fase2_ortografia/coherencia.py` (324 líneas), función `revisar()`
(`coherencia.py:242-286`).

**Artefactos que consume**: `salidas/lexico_casing.json` (vía
`nombres_del_corpus()`, `coherencia.py:137-159`, fuente de nombres propios y
siglas) y, de forma diferida, `salidas/lexico_clinico.json` (a través de
`NLP.depuracion.depuracion.es_clinica`, importado dentro de `_es_clinica()`,
`coherencia.py:105-120`, para no crear un ciclo de importación al cargar el
módulo).

| Constante | Valor | Archivo:línea |
|---|---|---|
| `FRACCION_DISTANCIA_MAXIMA` | `0.40` | `coherencia.py:68` |
| `FACTOR_FRECUENCIA` | `10` | `coherencia.py:69` |
| `LONGITUD_MINIMA` | `4` | `coherencia.py:74` |

**Subpasos**, en el orden de `juzgar()` (`coherencia.py:162-239`), tal como fija
`decisiones/2026-09-15-coherencia.md`: (1) restauración de tilde → dejar; (2) el
corregido es expansión por subsecuencia del original → dejar; (3) el original es
nombre propio o sigla del corpus → revertir; (4) el original es clínico y el
corregido no → revertir; (5) errata de teclado (anagrama o distancia ≤ 1) →
dejar; (6) el original no tiene respaldo en ningún diccionario → dejar; (7) el
corregido no está en ningún diccionario → revertir; (8) distancia > 40 % de la
longitud → revertir; (9) frecuencia del original ≥ 10× la del reemplazo →
revertir.

**Decisión enlazada**: `decisiones/2026-09-15-coherencia.md`. **Medición**:
muestra de 8.751 notas de `triage_limpio.csv`, 2026-09-15 — toca el 0,4 % de las
notas (39), 32 reversiones distintas, 2,6 ms por nota, cero falsos positivos en
revisión manual de las 32.

**Ejemplo**: en las tres notas sintéticas de este documento, `coherencia.revisar()`
no revirtió nada (`fase2b coherencia` idéntico a `fase2 enmascarado` en los tres
casos), porque la entrada de esta demostración es la salida del enmascarado, no de
la cadena completa de LanguageTool + SymSpell + contexto — no hubo, en esta
ejecución, ninguna sustitución que juzgar. Ver el ejemplo de reversiones reales
(`ahogado → abogado`, etc.) en `decisiones/2026-09-15-coherencia.md`.

**Veto del guardián clínico** (`terminologia.validar`, capa consultada tanto en
fase 2 como en fase 2b indirectamente vía `_es_clinica`), ejecutado de verdad en
esta demostración:

```
=== Ejemplo de veto clinico (terminologia.validar) ===
  ahogado -> abogado: admitido=True motivo=''
  volcamiento -> tocamiento: admitido=True motivo=''
  hipotension -> hipertension: admitido=False motivo='invierte el significado'
```

Nótese que `terminologia.validar()` **admite** `ahogado → abogado` y
`volcamiento → tocamiento` (ninguna de las reglas morfológicas del guardián los
detecta: no son antónimos, truncamientos ni cambios de familia reconocidos por
`morfologia.py`). Es exactamente la fase 2b, no el guardián clínico de fase 2,
la que revierte estos dos casos en una corrida real, comparando con la nota
completa y no solo con el par de palabras — así lo documenta
`decisiones/2026-09-15-coherencia.md` en su sección "Pregunta". `hipotension →
hipertension` sí lo detiene el guardián de fase 2 por sí solo (antónimo
morfológico, `morfologia.invierte_significado`).

## 5. Fase 3 — Normalización clínica

**Entrada**: `texto_corregido` (tras la fase 2b). **Salida**: `texto_normalizado`.
Módulo: `fase3_normalizacion/normalizacion.py` (342 líneas), función
`normalizar(texto)` (`normalizacion.py:284-314`); debe llamarse antes `cargar()`.

**Artefactos que consume**: `datos/diccionario_coloquial.json` (curado a mano, no
tiene comando de regeneración) y, vía `nucleo/reglas.EXPANDIBLES`,
`datos/diccionario_siglas.json`.

| Constante | Valor | Archivo:línea |
|---|---|---|
| `MODO` | `"anotar"` | `normalizacion.py:57` — añade `(significado)`, no sustituye |
| `EXPANDIR_SIGLAS` | `True` | `normalizacion.py:59` |
| `NORMALIZAR_COLOQUIALISMOS` | `True` | `normalizacion.py:60` |
| `EXPANDIR_ENCABEZADOS` | `True` | `normalizacion.py:61` |
| `LONGITUD_MINIMA_SIGLA` | `3` | `normalizacion.py:66` — siglas de 2 letras no se expanden, coinciden con palabras corrientes |
| `SEPARAR_CONCEPTO` | `False` (E5.1) | `normalizacion.py` | apagada: `normalizar()` sigue anotando inline igual que hoy. Encendida, `normalizar_separado(texto)` devuelve `(texto_sin_glosa, concepto_normalizado)` en vez de un solo texto con el paréntesis dentro |
| `EXPANDIR_ABREVIATURAS_PROPUESTAS` | `False` (E5.3) | `normalizacion.py` | apagada: expandiría además los candidatos no ambiguos de `salidas/e3_7_8/abreviaturas_candidatas.csv` (E3.8), tratándolos como declarados seguros solo para esta prueba. Medido sobre 9.311 notas: toca 67 (0,72 %), y 61 de esas 67 sufren daño real (falso positivo de sigla sobre una palabra corriente, o colisión de la glosa nueva con un patrón de recorte de fase 5). Ver `decisiones/2026-09-16-E5.3.md` |

**Subpasos**, en el orden de `normalizar()`: (1) `expandir_encabezados` — anota el
significado del rótulo de apartado (`"ap:"` → `"ap (antecedentes personales):"`);
conserva la sigla original (forma en que el personal escribe y busca) y omite
significados genéricos (`"medicamento"`, `"termino clinico"`, `"nombre propio"`,
`"apellido"`), que no aportarían nada al lector; (2) `_aplicar_con_contexto` —
entradas del diccionario que solo se activan si alguna palabra de contexto
aparece cerca (`recursos/ambiguedad.py`); (3) el resto del diccionario, con el
autómata de `flashtext` o, si no está instalado, una expresión regular de
respaldo.

**Decisión enlazada**: ninguna en `decisiones/` sobre el control de ambigüedad.
**Sin medición** — `recursos/ambiguedad.py`, que decide si una entrada se aplica
libre, con contexto o queda inactiva, no tiene una cifra de acierto/error
registrada. Sí hay decisión sobre la glosa que esta fase añade:
`decisiones/2026-09-16-E5.1-glosas.md` mide cuánto pesa en `texto_embedding` y su
asociación con la asignación de cluster, y dice por qué la bandera
`SEPARAR_CONCEPTO` está apagada por defecto pendiente de revectorizar y de
adaptar `clustering/etiquetas.py`.

**Por qué es una fase aparte** (trasladado del docstring de `normalizacion.py`,
E1.5): mezclar normalización y corrección ortográfica arruina la auditoría — en
el informe de cambios dejarían de distinguirse un error de digitación de una
expansión intencionada. Por eso corre sobre la columna ya corregida y conserva
ambas.

**Por qué se anota y no se reemplaza**: el reemplazo literal rompe la sintaxis en
expresiones verbales (`"me pita el oido"` → `"me tinnitus"`), y una nota
agramatical le cuesta más a un modelo que la expresión popular original.
Anotando se conserva la frase del paciente y se añade el término clínico.

**Qué entradas se aplican**: no todas. Cada entrada del diccionario pasa por el
control de ambigüedad (`recursos/ambiguedad.py`), que decide si se aplica
siempre, solo con contexto cercano, o queda inactiva. No hay listas negras: lo
que no se puede demostrar inequívoco no se aplica y queda en `desactivadas()`
como lista de decisiones pendientes de revisar. Ejemplo de entrada condicionada
al contexto: `"le salio un nacido en la pierna"` se normaliza (contexto de
erupción) y `"recien nacido de 6 dias"` no (contexto de edad).

**Las dos clases de ambigüedad que distingue `recursos/ambiguedad.py`**
(trasladado de su docstring, E1.5): (a) la forma coincide con una palabra
corriente del español (`"nacido"`, `"fuego"`, `"brote"`, `"masa"`), detectable
consultando el diccionario de LanguageTool y el vocabulario de spaCy — si
alguno la reconoce, la entrada queda inactiva salvo que declare contexto; (b)
una sigla que significa cosas distintas según el servicio (`"iva"` puede ser
un impuesto, un segmento hepático o una infección de vías aéreas), no
detectable por máquina — exige que el diccionario declare de forma explícita
qué entradas son seguras o ambiguas; lo no declarado no se expande. Formato de
una entrada condicionada a contexto: `{"significado": "furunculo", "contexto":
["salio", "grano", "piel", "pierna", "espalda"]}`.

**Ejemplo (nota A)**, salida real:

```
fase2b coherencia   : pte femenina 34 a con dolor abdominal desde hace 2 dias, niega fiebre; ap: hta. se remite a casa de salud para control
fase3 normalizado   : pte femenina 34 a con dolor abdominal desde hace 2 dias, niega fiebre; ap (antecedentes personales): hta (hipertensión arterial). se remite a casa de salud para control
```

`"ap:"` se anota como `"ap (antecedentes personales):"` (paso 1) y `"hta"` como
`"hta (hipertensión arterial)"` (paso 3, entrada del diccionario de siglas
expandibles). El resto de la nota, sin siglas ni coloquialismos del diccionario,
no cambia.

## 6. Fase 4 — Depuración (señalar, no eliminar)

**Entrada**: `texto_normalizado` si la fase 3 corrió, si no `texto_corregido`
(`columna_juicio`, decidido en `procesar.py:564`). **Salida**: `util` (interno) y
`motivo_descarte`. No modifica el texto de ninguna columna. Módulo:
`depuracion/depuracion.py` (435 líneas), función `evaluar(texto)`
(`depuracion.py:356-408`).

**Artefactos que consume**: `salidas/lexico_clinico.json` (solo fuentes curadas:
diccionario, catálogo, externo — el vocabulario biomédico queda fuera a propósito,
`depuracion.py:20-23`), `embedding/datos/catalogo_sintomas.json` (vía
`rutas.CATALOGO_SINTOMAS`) y `datos/diccionario_siglas.json` (grupo `geografia`,
para restar topónimos del índice de evidencia clínica).

| Constante | Valor | Archivo:línea |
|---|---|---|
| `PALABRAS_PARA_SALVAR` | `8` | `depuracion.py:108` — válvula de escape: una nota larga sin terminología reconocida se conserva igual |
| `LONGITUD_MINIMA_RAIZ` | `3` | `depuracion.py:226` — por debajo, truncar deja de discriminar |
| `LONGITUD_ROTULO_SIN_DOSPUNTOS` | `8` | `depuracion.py:158` — a partir de esta longitud, un rótulo de apartado se reconoce sin los dos puntos |

**Subpasos**, en el orden de `evaluar()`: (1) nota vacía → `VACIA`; (2) todas las
palabras son "respuesta vacía" (`"niega"`, `"normal"`...) → `PLANTILLA`; (3) quitar
apartados no clínicos (antecedentes, alérgicos...) y repetir (1)-(2) sobre lo que
queda → `ANTECEDENTES` o `PLANTILLA`; (4) trámite puro (todas las palabras son
trámite o no clínicas, con al menos una de trámite) → `TRAMITE`; (5) hay término o
frase clínica reconocida (por raíz morfológica, vía `nltk.SnowballStemmer` si está
instalado) → conservar; (6) la nota es larga (≥ 8 palabras con contenido) →
conservar igual, por la válvula de escape; (7) menciona trámite → `TRAMITE`; en
otro caso → `SIN_TERMINOLOGIA`.

**Por qué esta fase existe y por qué corre última** (trasladado del docstring de
`depuracion.py`, E1.5): no todas las notas de triage hablan del paciente — una
parte del corpus son plantillas contestadas en blanco, trámite puro o un
fragmento suelto que no dice a qué vino nadie. Para el agrupamiento posterior eso
no es solo peso muerto: son notas casi idénticas entre sí y ajenas a cualquier
cuadro clínico, que forman grupos propios sin significado y ensucian los que sí
lo tienen. El criterio — no queda en la nota ni un término del léxico clínico
curado — se aplica **después** de corregir, normalizar y recortar a propósito:
aplicado antes de la normalización, este mismo criterio descartaba miles de
notas que sí tenían contenido (una caída descrita en lenguaje corriente, una
sigla que el diccionario ya sabe traducir). Ninguna de ellas estaba vacía: eran
huecos de vocabulario, y descartarlas habría borrado la evidencia del problema
en vez de resolverlo. De ahí la regla: este módulo solo se ejecuta cuando ya se
aplicó todo lo que el proyecto sabe traducir.

**Qué se descarta y qué no**: ante la duda se conserva. Una nota descartada no
vuelve, y el coste de arrastrar algo de ruido es mucho menor que el de perder un
motivo de consulta real. Por eso el trámite solo descarta cuando además no hay
nada clínico: una nota que solo dice cómo llegó el paciente se va, pero la que
dice cómo llegó y por qué se conserva entera. Nada se descarta en silencio:
`evaluar()` devuelve siempre el motivo, y el orquestador escribe todas las notas
descartadas con su motivo en `notas_descartadas.csv`; una expresión clínica
repetida ahí no es ruido, es una entrada que falta en el léxico.

**Por qué hay listas cerradas además del léxico** (`PALABRAS_TRAMITE`,
`PALABRAS_ANATOMIA`, `PALABRAS_TIEMPO`): coincidir con el léxico no basta como
evidencia clínica, porque el CIE-10 no distingue el nombre de un síntoma del de
una región anatómica ni del español corriente que arrastra en sus rúbricas.
Frases como "consulta externa" o una parte del cuerpo suelta pasan el filtro con
terminología reconocida y son ruido. Las tres listas son cortas y cerradas a
propósito: enumeran los tres casos en que coincidir con el léxico no es
evidencia de contenido clínico, y no pretenden cubrir el vocabulario
administrativo del hospital. Nombrar una parte del cuerpo (`PALABRAS_ANATOMIA`)
solo descarta cuando es lo único clínico de la nota; acompañada de un síntoma,
la nota se conserva entera. `PALABRAS_TIEMPO` existe porque el CIE-10 contiene
"semana", "pasada" y "pasado" en sus rúbricas: sin la lista,
`'la semana pasada me hospitalizar y el viernes pasado sali'` daba tres
"términos clínicos" — semana, pasada, pasado — y salía del pipeline como si
fuera un motivo de consulta, cuando no dice ni un síntoma: cuenta un ingreso
anterior.

**Por qué no basta con quitar el rótulo del apartado**: hay que quitar también
lo que contiene. `'ap (antecedentes personales): hta (hipertension arterial); aa: niega'`
sin los rótulos queda `'hta (hipertension arterial); niega'`, que es
terminología clínica legítima, así que la nota se conservaba — y no dice a qué
vino el paciente, dice que es hipertenso. Los antecedentes son terminología
clínica de verdad y aun así no dicen a qué vino nadie; para agrupar motivos de
consulta eso es ruido, y ruido convincente porque pasa cualquier filtro que solo
pregunte si hay terminología.

**Decisión enlazada**: `decisiones/2026-09-16-depuracion-indice-clinico.md` (por
qué comparar por raíz y no por igualdad exacta contra el léxico; por qué
reconocer un rótulo sin los dos puntos a partir de cierta longitud; por qué
quitar la expansión del rótulo antes de juzgar la nota).

**Ejemplo (notas A y C)**, salida real:

```
fase4 depuracion    : util=True motivo='(ninguno)'      # nota A
fase4 depuracion    : util=True motivo='(ninguno)'      # nota C
```

La nota C es, por diseño, una nota puramente administrativa (orden de remisión,
"entidad promotora de salud", "urgencia vital"), y aun así `evaluar()` la marca
`util=True`. La causa es un problema **conocido y documentado en `ESTADO.md` §5**:
`"salud"` está en el léxico curado (aparece en el diccionario del proyecto) y
`terminos_clinicos()` la cuenta como término clínico, aunque en esta frase no dice
nada del paciente. Es exactamente el ruido que `ESTADO.md` §5 describe: *"La
métrica `perdio_motivo` aún cuenta `dada`, `salud`, `toma`, `signos` como
terminología (están en el léxico curado)"*. Este ejemplo lo reproduce de forma
sintética y verificable.

## 7. Fase 5 — Reducción al motivo de consulta

**Entrada**: `columna_juicio` (igual que la fase 4). **Salida**: `texto_embedding`
y `motivo_llm`; combina su señal de descarte con la de la fase 4 en
`motivo_descarte` (`procesar.py:465-469`, unidas con `" | "`). Módulos:
`reduccion/reduccion.py` (697 líneas, reglas), `reduccion/frases.py` (303 líneas,
clasificador de tramos) y `reduccion/extractor.py` (474 líneas, modelo de
lenguaje local, fase 5b).

**Artefactos que consume**:

| Artefacto | Comando | Rol |
|---|---|---|
| `salidas/lexico_clinico.json` | `python -m NLP.recursos.lexico` | densidad clínica de cada tramo (`reduccion._es_clinica`, **copia propia**, no reutiliza `recursos/lexico.py`; ver "Discrepancias") |
| `datos/diccionario_siglas.json` (grupo `geografia`) | se edita a mano | patrón de topónimos que se recortan |
| `salidas/clasificador_frases.joblib` (opcional) | `from NLP.reduccion import frases; frases.entrenar()` — **nunca** `python -m NLP.reduccion.frases` | cubre trámite no enumerado por los patrones |
| Ollama `qwen2.5:3b-instruct` (servicio, opcional) | `ollama pull qwen2.5:3b-instruct` | fase 5b: decide el motivo de consulta y si la nota tiene uno |

| Constante | Valor | Archivo:línea |
|---|---|---|
| `PALABRAS_ORACION_LARGA` | `8` | `reduccion.py:38` |
| `DENSIDAD_MINIMA` | `0.40` | `reduccion.py:39` |
| `TOPE_PALABRAS` | `60` | `reduccion.py:371` |
| `LONGITUD_MINIMA` | `1` | `reduccion.py:370` |
| `MAX_LONGITUD` / `UMBRAL_BUROCRATICO` | `64` / `0.85` | `frases.py` (ficha en `ARQUITECTURA.md` §2.7) |
| `LONGITUD_MINIMA` (extractor) | `1` | `extractor.py:28` — ve todas las notas, no solo las largas |
| `FRACCION_MAXIMA` / `FRACCION_CLINICA_MINIMA` | `0.85` / `0.50` | `extractor.py:46,53` |
| `QUITAR_GLOSA` | `False` (E5.1) | `reduccion.py` — si `True`, `recortar()` quita también `(...)` de la fase 3; sin efecto si el texto ya llega sin ella (`normalizacion.SEPARAR_CONCEPTO=True`) |
| `USAR_NEGACION` | `False` (E5.2) | `reduccion.py` — si `True`, `recortar()` antepone `NEG_` (`nucleo/negacion.marcar()`) al alcance de cada negación, como último paso, sobre el texto ya recortado. Apagada por defecto: cambia `texto_embedding` (contrato §7 de `PLAN.md`) y exige revectorizar y `clustering --validar`; ver `decisiones/2026-09-16-E5.2.md` |

**Subpasos**, en el orden de `_recortar()` (`reduccion.py:636-682`), llamada por
`recortar()`: pasada **agresiva** — `_quitar_clasificador` (tramos que `frases.py`
marca administrativos, salvo que su densidad clínica los proteja) →
`_quitar_institucional` (oraciones con marcador institucional, u oraciones largas
de baja densidad clínica) → quitar encabezados → quitar antecedentes en prosa,
pluripatología, examen físico, conducta, acompañante, modo de llegada, lugares →
(solo agresivo) trámite, verbo de reporte, preámbulo temporal, ficha demográfica →
pulir. Si el resultado crea una "costura" (`crea_costura()`, junta dos palabras que
no estaban juntas), se reintenta con la pasada **suave** (sin trámite/reporte/
temporal/demográfico); si tampoco sirve, se devuelve el texto original
(`sin_reducir()`). Si `USAR_LLM`, el extractor (fase 5b) sustituye el recorte por
su propia extracción, verificada literalmente contra la nota, o marca
`MOTIVO_SIN_CONTEXTO` si concluye que no hay motivo de consulta; cualquier otro
resultado del modelo deja mandar al recorte por reglas. Si `USAR_NEGACION` (E5.2),
el texto que sale de cualquiera de las tres ramas de `recortar()` (agresiva, suave
o sin reducir) pasa por `negacion.marcar()` como último paso, después de `_pulir()`
y no antes: los patrones de arriba buscan frases literales, y marcar antes los
dejaría de reconocer.

**Qué se conserva**: la negación viaja dentro del texto (un cuadro descrito como
resuelto tiene que llegarle así al modelo; viaja también aparte, como campo
estructurado — cada copia sirve para algo distinto) y la anotación entre paréntesis
que añadió la fase 3 tampoco se quita por defecto (`QUITAR_GLOSA = False`): para
quien lee la nota duplica lo que la sigla ya dice, pero es la única pista de qué
significa una sigla para el modelo de embeddings.

**Decisiones enlazadas**:
- `decisiones/2026-09-15-artefactos-y-version-corrector.md` — sin
  `lexico_clinico.json`, `densidad_clinica()` es 0,0 para toda oración: 25,1 % de
  las notas perdían contenido clínico, 18,1 % perdían más de la mitad (muestra
  8.751 notas, 2026-09-15).
- `decisiones/2026-09-15-clasificador-freno-clinico.md` — el freno de densidad
  clínica sobre el clasificador; notas que recuperan motivo 16 → 24, alarmas de
  pérdida 11 → 7 (muestra de 100 notas reparadas, 2026-09-15).
- `decisiones/2026-09-15-modelo-generativo.md` — por qué el extractor solo copia
  texto literal verificado y nunca reescribe (5,5 tokens/s medidos en esta CPU).
- `decisiones/2026-09-16-reduccion-extractor-umbrales.md` — por qué
  `LONGITUD_MINIMA` (extractor) pasó a ver todas las notas y qué mide
  `FRACCION_CLINICA_MINIMA`.
- `decisiones/2026-09-16-reduccion-clasificador-cobertura.md` — por qué el
  clasificador se usa además de los patrones (400 tramos sin regla: 110
  administrativos, 144 clínicos, 146 en zona gris).
- `decisiones/2026-09-16-reduccion-acompanante-llegada.md` — por qué se quita el
  acompañante y el modo de llegada (1.301 y 1.107 notas).
- `decisiones/2026-09-16-reduccion-bloques-nota-larga.md` — examen físico,
  conducta y antecedentes en prosa (15,9 % del corpus pasa de 30 palabras).
- `decisiones/2026-09-16-reduccion-costuras.md` — `crea_costura()` (189 notas,
  70 % de los fallos del recorte).
- `decisiones/2026-09-16-reduccion-institucional-todo-o-nada.md` — devolver la
  nota entera cuando no queda ninguna oración útil (229 de 8.000 notas).
- `decisiones/2026-09-16-frases-codificador.md` — roberta-clínico frente a
  bge-m3 y por qué `probabilidades()` cachea por tramo.

**Ejemplo (nota A)**, salida real — muestra una costura no resuelta:

```
fase3 normalizado    : pte femenina 34 a con dolor abdominal desde hace 2 dias, niega fiebre; ap (antecedentes personales): hta (hipertensión arterial). se remite a casa de salud para control
fase5 texto_embedding: pte femenina 34 a con dolor abdominal, niega fiebre; hta (hipertensión arterial). a casa de salud para control
```

`RE_TRAMITE` quita `"se remite"` (verbo de trámite) y deja `"a casa de salud para
control"` colgando tras el punto. `_pulir()` no lo limpia porque
`RE_ARRANQUE_HUERFANO` solo actúa al **inicio de todo el texto**, no al inicio de
cada tramo interno (ver "Discrepancias" más abajo).

**Ejemplo (nota C)**, salida real — muestra el caso "sin puntos, todo o nada" que
el propio código documenta:

```
fase3 normalizado    : trae orden de remision desde el hospital san jose por consulta prioritaria, entidad promotora de salud responde por los niveles de atencion, sin criterios que constituyan urgencia vital
fase5 texto_embedding: entidad promotora de salud responde por los niveles de atencion, sin criterios que constituyan urgencia vital
```

La nota entera es una sola frase separada por comas (sin `.` ni `;`), así que
`_quitar_institucional()` la trata como una única "oración": contiene marcadores
institucionales (`"entidad promotora"`, `"urgencia vital"`) y no tiene periodos
donde cortar solo esa parte, así que por la regla documentada en
`reduccion.py:460-491` ("si no queda nada, se devuelve la nota entera";
medición en `decisiones/2026-09-16-reduccion-institucional-todo-o-nada.md`) el
bloque institucional sobrevive completo. Solo la pasada agresiva (`RE_TRAMITE`) alcanza a
quitar el tramo `"trae orden de remision... prioritaria,"` porque ese sí es un
patrón de tramo, no de oración.

## 8. Fase 6 — Conceptos (prevista, E5.7)

No existe todavía. Prevista en `PLAN.md` §8, ítem **E5.7 Normalización conceptual
(fase 6, nueva)**: `PhraseMatcher` contra SympTEMIST + DISTEMIST (nivel 0),
SapBERT-es o ClinLinker-KB-GP con vecino más cercano (nivel 1), NER
(`carmen-symptemist`) solo en notas largas (nivel 2); columnas previstas
`concepto_snomed` y `concepto_termino`. Ver `PLAN.md` §8 para el criterio de
aceptación y la dependencia de E4-E5.

## 9. Lo que el flujo no hace todavía

- No hay fase 6: ningún texto llega codificado a un concepto SNOMED ni a un
  vocabulario controlado de síntomas más allá del catálogo de reglas (E5.7).
- La negación se queda dentro de la frase (`"niega fiebre"`) pero no viaja como
  campo estructurado ni como alcance marcado (`NEG_`) en `texto_embedding`
  (E5.2).
- Las glosas entre paréntesis que añade la fase 3 (`"hta (hipertensión
  arterial)"`) siguen en `texto_embedding` por defecto; `clustering/etiquetas.py`
  depende hoy de ellas para nombrar clusters (38,06 % de las notas por
  `texto_normalizado`, 28,84 % por `texto_embedding`, 9.311 notas,
  2026-09-16). E5.1 midió el efecto y dejó las banderas `SEPARAR_CONCEPTO`
  (fase 3) y `QUITAR_GLOSA` (fase 5) implementadas y apagadas: ver
  `decisiones/2026-09-16-E5.1-glosas.md`. Encenderlas sin adaptar
  `clustering/etiquetas.py` para que lea la nueva fuente de nombres sigue
  siendo lo que advierte `PLAN.md` §7: degrada los nombres sin fallo visible.
- No hay lematización selectiva (E5.4).
- No hay pruebas automatizadas que fijen el comportamiento de ninguna fase:
  `NLP/tests/` solo tiene una carpeta `datos/` vacía; `python -m pytest NLP/tests
  -q` ejecutado el 2026-09-16 devuelve `no tests ran in 0.07s` (E2.1).
- No existe `NLP/evaluacion/metricas.py`: no hay F0.5 ni tasa de intervención
  calculadas para ninguna versión del corrector, solo las cifras puntuales de
  `decisiones/` (E2.2).
- La fase 2 (14 constantes documentadas en la tabla de la sección 3) no tiene
  ninguna medición formal en `decisiones/` de sus propios umbrales; las únicas
  cifras medidas de la fase 2 son las de la fase 2b y la de los artefactos
  ausentes (E4.1-E4.9 las cubrirá).
- Esta demostración no verificó la cadena completa de la fase 2 (LanguageTool +
  SymSpell + capa de contexto) por no requerir un servicio Java ni la base de
  datos mientras corría el job de reparación en segundo plano; el caso
  `"bomito" → "vomito"` de la nota B queda sin resolver en este documento.

## 10. Discrepancias entre documentación y código

1. **`embedding/estructurar.py` no arranca.** `embedding/extraccion.py:61,64`
   hace `from embedding import rutas` y luego `rutas.CATALOGO_SINTOMAS`, pero
   `embedding/rutas.py` (54 líneas) no define ese atributo — solo lo define
   `NLP/rutas.py:54`. Ejecutado el 2026-09-16:
   `python -m embedding.estructurar --help` falla con
   `AttributeError: module 'embedding.rutas' has no attribute
   'CATALOGO_SINTOMAS'` antes de imprimir la ayuda. `PLAN.md` §7 documenta el
   acoplamiento inverso como si pasara por `NLP.rutas` ("Acoplamiento inverso:
   `NLP/rutas.py` apunta a `embedding/datos/catalogo_sintomas.json`; lo leen...
   `embedding/extraccion.py`"), pero el import real usa `embedding.rutas`. Esto
   no afecta a `python -m embedding.vectorizar`, que no importa `extraccion.py`
   y funciona (`--help` verificado el mismo día).
2. **`nucleo/requisitos.py` recomienda el comando peligroso.** La receta del
   artefacto `clasificador_frases` en `requisitos.py:74-78` es
   `"python -m NLP.reduccion.frases"`, el mismo comando que `PLAN.md`,
   `NLP/README.md` y esta misma bitácora prohíben expresamente porque regenera
   `datos/frases_etiquetadas.csv` (curado a mano) y destruye la curación. Un
   operador que siga al pie de la letra el aviso de `requisitos.py` (o de
   `python -m NLP.nucleo.requisitos`, que imprime esa receta literal) borraría
   trabajo humano. Ver el aviso en `OPERACION.md`.
3. **Cifras medidas en comentarios de código, no en `decisiones/`.** La guía de
   estilo (`ARQUITECTURA.md` §6.3) exige que las cifras medidas vayan a
   `decisiones/` y no a los comentarios. Ejemplos con cifra propia sin
   correspondencia en `decisiones/`: `reduccion.py:258-268` (1.301 y 1.107
   notas), `reduccion.py:300-321` (15,9 % del corpus, 369 notas, 60 de 153
   palabras en un caso), `reduccion.py:715-736` (189 notas, 70 % de los fallos,
   13 de 17 costuras). Las cifras que tenía `depuracion.py` (296 y 287 notas, y
   los conteos 136/23/17/8 del índice por raíz) se trasladaron en E1.5 a
   `decisiones/2026-09-16-depuracion-indice-clinico.md`.
4. **`evaluacion/perturbar.py` no tiene ficha en `ARQUITECTURA.md`.** Confirmado
   con `python -m NLP.evaluacion.paridad_docs` el 2026-09-16: `"Faltantes
   (archivo sin ficha): 1 — evaluacion/perturbar.py"`. El archivo ya existe en
   disco (E2.3 en marcha) pero la ficha de E1.2 no se ha actualizado.
5. **`NLP/docs/README.md` no tenía sección `## Historial`.** Confirmado con la
   misma corrida de `paridad_docs.py`: `"Documentos de docs/ sin sección
   '## Historial': 1 — README.md"`. Corregido en el mismo ítem que este
   documento (E1.3/E1.4).
6. **La costura de la fase 5 (sección 7, ejemplo de la nota A).**
   `_pulir()` (`reduccion.py:632-655`) limpia los conectores huérfanos solo al
   principio del texto completo (`RE_ARRANQUE_HUERFANO`, anclado con `^`,
   `reduccion.py:411-420`), no al principio de cada tramo interno que quedó
   pegado tras quitar un patrón por el medio. El propio módulo documenta el
   problema general de las costuras (`crea_costura()`,
   `reduccion.py:715-737`) pero la limpieza del arranque huérfano no cubre este
   caso, que si es real (no se pudo confirmar sobre datos reales, solo sobre la
   nota sintética A de este documento).

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-16 | E1.3 | Primera versión: recorrido de la nota, una sección por fase 1-6, ejemplos sintéticos ejecutados, discrepancias encontradas |
| 2026-09-16 | E5.1 | Constantes `SEPARAR_CONCEPTO` (fase 3) y `QUITAR_GLOSA` (fase 5) en las tablas de §5 y §7; bullet de glosas en §9 actualizado con la medición y el enlace a `decisiones/2026-09-16-E5.1-glosas.md` |
| 2026-09-16 | E5.2, E5.3 | Constante `USAR_NEGACION` (fase 5, §7) y nota sobre el marcado de negación como último paso de `recortar()`; constante `EXPANDIR_ABREVIATURAS_PROPUESTAS` (fase 3, §5). Enlaces a `decisiones/2026-09-16-E5.2.md` y `decisiones/2026-09-16-E5.3.md` |
