# Investigación: fuentes, hallazgos y aplicación al proyecto

Revisión de literatura y de recursos realizada el 2026-09-15 para la fase NLP del
proyecto de triage. Este documento registra, fuente por fuente, **por qué se consideró,
qué problema concreto del proyecto resuelve, qué idea se toma, cómo se usaría aquí y qué
veredicto recibe**. La bibliografía en formato de cita formal, con licencias, está en
`REFERENCIAS.md`; aquí las citas van abreviadas (autor, año) con su enlace.

## 0. Método y alcance

- Dos agentes de investigación en paralelo con acceso a internet: uno sobre técnicas
  (corrección ortográfica, detección de daño, evaluación, normalización para
  agrupamiento) y otro sobre recursos (léxicos, modelos, corpus, licencias). Unas
  sesenta fuentes en total.
- Criterio de prioridad: aplicabilidad a **notas de mediana 6 palabras, en mayúsculas,
  con erratas, en español colombiano, procesadas en CPU sin GPU**, con el objetivo final
  de agrupar motivos de consulta. Lo que no encaja en ese perfil se marca como
  descartado, con el motivo.
- Verificación: los recursos marcados *[descarga verificada]* se descargaron y
  comprobaron durante la investigación. Las citas de artículos se tomaron de las
  fuentes indicadas; los DOI y URL deben re-verificarse antes de cualquier publicación
  externa (ítem E7.4 del plan).
- Veredictos: **adoptar** (evidencia suficiente para incorporar), **probar** (candidato
  con experimento asignado en el plan), **descartar** (con motivo), **referencia**
  (se cita como fundamento, no como técnica a implementar).

## 1. El diagnóstico que orienta la búsqueda

Antes de buscar se midió el CSV existente (8.751 notas). Los datos que condicionan qué
literatura sirve:

| Medición | Valor | Consecuencia |
|---|---|---|
| Longitud de nota | mediana 31 caracteres (~6 palabras), media 99 | Una nota es casi una única mención: la literatura de *chief complaints* y de enlace de menciones cortas aplica más que la de historias clínicas largas |
| Notas en mayúsculas | mayoría del corpus | Los modelos preentrenados con capitalización natural degradan; hay que minusculizar o truecasear |
| Contenido descartado por la fase 5 | media 19,5 %; 18,1 % de notas pierden > 50 % | Causa: léxico clínico ausente. Tras reconstruirlo: 12,1 % y 8,7 % |
| Notas con glosa entre paréntesis | 38,1 % | Afecta al embedding (sección 6.1) |
| Correcciones que cambian el sentido | `ahogado → abogado`, `volcamiento → tocamiento`, `mareado → marcado`, `tosiendo → comiendo` | Las cuatro palabras originales son correctas: son fallos de **detección**, no de elección de candidato |
| Velocidad de un modelo generativo de 3 B en esta CPU | 5,5 tokens/s | Nada generativo sobre el corpus completo (94.136 notas) |

El último punto reencuadra la pregunta: no hace falta "un modelo mejor" sino un corrector
que no toque palabras correctas, un léxico de dominio y una evaluación que mida
precisión.

## 2. Corrección ortográfica

### 2.1 La detección es el problema central

**Wilcox-O'Hearn (2014).** *Detection is the central problem in real-word spelling
correction.* https://arxiv.org/abs/1408.3153
- Por qué se consideró: los cuatro fallos del corpus son de palabra real (la palabra
  existe, pero se cambió por otra).
- Qué sostiene: en corrección de palabras reales, la detección domina el error total;
  corregir una palabra correcta cuesta más que dejar un error; recomienda umbrales
  conservadores y priorizar precisión sobre cobertura.
- Aplicación: fundamento del principio 2 del plan (precisión antes que cobertura),
  de la métrica F0.5 y de la tasa de intervención sobre texto limpio (E2.2).
- Veredicto: **referencia** (fundamento).

### 2.2 El léxico se construye desde el propio corpus

**Singh (2026).** *Spelling Correction in Healthcare Query-Answer Systems: Methods,
Retrieval Impact, and Empirical Evaluation.* https://arxiv.org/abs/2603.19249
- Por qué: es el único trabajo encontrado que compara SymSpell contra distancia de
  edición con números en dominio salud.
- Qué sostiene (vocabulario de 8.201 términos extraído del propio corpus con ≥ 2
  ocurrencias):

  | Método | Correcciones correctas | Cambios innecesarios |
  |---|---|---|
  | Distancia 1 exacta + frecuencia del candidato ≥ 5 | 18,9 % | 8,9 % |
  | Levenshtein estándar (d = 1 o 2) | 12,0 % | 16,0 % |
  | Ranking con contexto (ventana ±2) | 12,0 % | 16,0 % |
  | SymSpell | 12,1 % | **1,5 %** |

  Conclusiones: recomiendan d = 1 y frecuencia mínima ≥ 5 en salud; SymSpell es el más
  conservador (lo que interesa cuando una corrección errónea contamina un cluster); el
  ranking con contexto no aportó sobre vocabulario pequeño; el diccionario del propio
  corpus da la jerga local gratis.
- Aplicación: E3.3 (léxico del corpus con umbrales ≥ 2 y ≥ 5), E4.2 (candidatos
  conservadores), y la decisión de no invertir en ranking contextual hasta medir
  (E4.6–E4.7 solo sobre la zona gris).
- Veredicto: **adoptar** (léxico y umbrales), **probar** (ranking contextual).

**Lee, Kim et al. (2021).** *Similarity-Based Unsupervised Spelling Correction Using
BioWordVec.* JMIR Medical Informatics 9(2):e25530.
https://medinform.jmir.org/2021/2/e25530
- Por qué: receta casi idéntica al problema: detección por no pertenencia a la
  terminología.
- Qué sostiene: cada token se mapea contra SNOMED; lo que no mapea es candidato a
  error; candidatos por similitud de embeddings de n-gramas de caracteres + distancia
  de edición; matriz ordenada por frecuencia; F1 97,48 % sobre 27.544 informes.
- Aplicación: E3.4 (gazetteers como terminología de referencia) y E4.7 (fastText propio
  en lugar de BioWordVec). El detector "no está en la terminología → sospechoso" es de
  coste nulo y precisión alta.
- Veredicto: **probar** (E4.7), **adoptar** el detector por no pertenencia (E3).

### 2.3 Modelo de canal ruidoso

**Kernighan, Church y Gale (1990).** *A Spelling Correction Program Based on a Noisy
Channel Model.* COLING. https://doi.org/10.3115/997939.997975
**Brill y Moore (2000).** *An Improved Error Model for Noisy Channel Spelling
Correction.* ACL. https://doi.org/10.3115/1075218.1075255
- Por qué: es el marco formal (maximizar P(c)·P(t|c)) que explica el fallo
  `ahogado → abogado`: el prior P(c) venía de un corpus general donde `abogado` es más
  frecuente.
- Qué sostiene: Brill y Moore generalizan el modelo de error a sustituciones de cadena a
  cadena, lo que importa en español (dígrafos `ll/y`, `qu/k`, `cc/c`). El modelo de
  error se estima con matrices de confusión y adyacencia de teclado, y puede refinarse
  con pares (error, corrección) autoinducidos del propio corpus.
- Aplicación: E4.4. Prior de dominio = unigramas y bigramas de las 94.136 notas. Coste:
  conteos y sumas de logaritmos, milisegundos por nota.
- Veredicto: **probar** (E4.4).

### 2.4 N-gramas de dominio

**Islam e Inkpen (2012).** *Context-sensitive Spelling Correction Using Google Web 1T
5-Gram Information.* https://arxiv.org/abs/1204.5852
**(2023).** *Real-Word Error Correction with Trigrams.* https://arxiv.org/abs/2302.04096
**Golding y Roth (1999).** *A Winnow-Based Approach to Context-Sensitive Spelling
Correction.* Machine Learning 34. https://doi.org/10.1023/A:1007545901558
**KenLM.** https://kheafield.com/code/kenlm/
- Por qué: con contexto de seis palabras, un trigrama entrenado en el dominio captura
  colocaciones reales (`caída de moto`, `dolor de pecho`) mejor que un modelo
  generalista, y es trazable (se puede explicar una elección mirando el conteo).
- Limitación: dispersión; con notas cortas los 4-gramas son casi todos únicos. Quedarse
  en bigramas/trigramas con suavizado Kneser-Ney y aceptar que el unigrama de dominio
  hace la mayor parte del trabajo.
- Aplicación: dentro de E4.4. KenLM en Windows requiere compilación; alternativa: conteos
  propios con suavizado simple.
- Veredicto: **probar** como parte de E4.4.

### 2.5 Generación de candidatos

**SymSpell (Garbe).** https://github.com/wolfgarbe/SymSpell — comparación con BK-tree:
https://seekstorm.com/blog/symspell-vs-bk-tree/
- Qué sostiene: precomputa eliminaciones hasta distancia d; búsqueda en O(1) práctico;
  ~1.870 veces más rápido que un BK-tree con d = 3. El BK-tree solo compensa con
  diccionarios enormes o métricas arbitrarias; el autómata de Levenshtein, cuando ya
  se tiene un FST.
- Regla práctica: distancia máxima proporcional a la longitud (1 para ≤ 4 caracteres,
  2 para 5–9, 3 para ≥ 10). Aplicar d = 2 fijo a palabras de 4 letras genera falsos
  positivos.
- Aplicación: el proyecto ya usa `symspellpy`; E4.2 fija la distancia por longitud.
- Veredicto: **adoptar** (mantener SymSpell; distancia por longitud). BK-tree:
  **descartar**.

### 2.6 Fonética del español

**(2016).** *Comparative Analysis of Phonetic Algorithms Applied to Spanish.*
https://aimimages.uwp.edu/aimimages/quevedo/intellcont/paper_JUQT_UAG_2016_07881516-1.pdf
**Meta-Soundex.** *Phonetic Matching Toolkit with Meta-Soundex (English and Spanish).*
https://shsu-ir.tdl.org/bitstreams/c412e040-12c0-4f6e-94eb-423a26146808/download
- Por qué: las erratas de digitación en español son mayoritariamente fonéticas, y
  Bravo-Candel (2.9) confirma que los homófonos son la categoría que mejor se corrige.
- Qué sostiene: Soundex no sirve para español (diseñado para apellidos ingleses);
  Meta-Soundex reduce falsos positivos al codificar vocales. Clases de equivalencia
  útiles: `b≡v`, `s≡z≡c(e,i)`, `y≡ll`, `h→∅`, `qu≡k≡c(a,o,u)`, `g(e,i)≡j`, `x≡ks`,
  consonantes y vocales dobles a simples.
- Aplicación: E4.3, como criterio de aceptación (mismo código fonético = candidato
  fuerte aunque la distancia sea 2–3) y como generador.
- Veredicto: **probar** (E4.3).

### 2.7 Modelo enmascarado como verificador

**Salazar et al. (2020).** *Masked Language Model Scoring.* ACL.
https://aclanthology.org/2020.acl-main.240/
**BEDSpell (2022).** ICSOC Workshops. https://doi.org/10.1007/978-3-031-26507-5_1
**Pal y Mustafi (2020).** *Vartani Spellcheck.* https://arxiv.org/abs/2012.07652
**Hu et al. (2021).** *Misspelling Correction with Pre-trained Contextual Language
Model.* https://arxiv.org/abs/2101.03204
**(2024).** *Contextual Spelling Correction with Language Model for Low-resource
Setting.* https://arxiv.org/abs/2404.18072
**PlanTL-GOB-ES/bsc-bio-ehr-es.** https://huggingface.co/PlanTL-GOB-ES/bsc-bio-ehr-es
(repositorio: https://github.com/PlanTL-GOB-ES/lm-biomedical-clinical-es)
- Por qué: el proyecto ya tiene una capa de contexto con RoBERTa clínico
  (`fase2_ortografia/contexto.py`); la literatura dice cómo usarla bien y cuándo no.
- Qué sostiene: una sola pasada por posición enmascarada puntúa todos los candidatos;
  solo hay que enmascarar tokens sospechosos (10–15 %). Tres trampas: (1) un solo
  `[MASK]` solo puntúa candidatos de un token y sesga hacia palabras cortas y frecuentes
  (`abogado`, `marcado`, `comiendo`): usar pseudo-log-verosimilitud sobre subtokens
  (Salazar 2020); (2) los modelos españoles están entrenados con capitalización natural:
  minusculizar antes; (3) con seis palabras de contexto la ganancia sobre un modelo de
  frecuencia de dominio es pequeña.
- Aplicación: E4.6, solo como verificador de pares en la zona gris (`P(orig|ctx)` frente
  a `P(corr|ctx)`), nunca como decisor sobre todas las notas. `bsc-bio-ehr-es` (1,1 B
  tokens clínicos, 278 k documentos reales) es el candidato natural.
- Veredicto: **probar** (E4.6). Como generador principal: **descartar**.

### 2.8 Corrección no supervisada para texto clínico telegráfico

**Fivez, Šuster y Daelemans (2017).** *Unsupervised Context-Sensitive Spelling Correction
of English and Dutch Clinical Free-Text with Word and Character N-Gram Embeddings.*
CLIN Journal 7. https://arxiv.org/abs/1710.07045 — código:
https://github.com/clips/clinspell
- Por qué: es el trabajo más cercano al problema: texto clínico corto y ruidoso, sin
  datos anotados, en un idioma con menos recursos que el inglés.
- Qué sostiene: (a) detección por OOV respecto a un lexicón; (b) candidatos por
  distancia de edición y variantes fonéticas; (c) ranking por coseno ponderado entre el
  vector del candidato y el vector del contexto, con embeddings de n-gramas de caracteres
  (fastText) para que un candidato raro también tenga vector. Parámetros afinados con
  errores autoinducidos, sin anotación humana. Portado de inglés (MIMIC-III) a neerlandés
  superando correctores comerciales.
- Aplicación: E4.7 (fastText sobre las 94 k notas; usar la nota entera como contexto) y
  E2.3 (corpus de errores autoinducidos).
- Veredicto: **probar** (E4.7), **adoptar** la técnica de evaluación autoinducida (E2.3).

### 2.9 Español clínico

**Bravo-Candel et al. (2021).** *Automatic Correction of Real-Word Errors in Spanish
Clinical Texts.* Sensors 21(9):2893. https://doi.org/10.3390/s21092893
- Por qué: referencia en español clínico para errores de palabra real.
- Qué sostiene: seq2seq transformer sobre errores sintéticos (Wikicorpus + CodiEsp +
  MEDDOCAN + SPACCC). F0.5 global 64,98 %; número 82,8 %, género-número 81,6 %, homófonos
  81,7 %; concordancia sujeto-verbo, la peor. Parámetros: ventana 5, longitud máxima 40,
  frecuencia mínima 10, umbral Levenshtein 3–6 según tipo. Los embeddings preentrenados
  (GloVe/Word2Vec) no mejoraron el resultado.
- Aplicación: E4.8 (desactivar concordancia gramatical: peor categoría y la gramática no
  es normativa en triage); umbrales de referencia; no invertir en embeddings
  preentrenados. La arquitectura seq2seq se descarta (GPU; con 65 % de F0.5 introduciría
  más daño del que repara sobre 94 k notas).
- Veredicto: **adoptar** los parámetros y la taxonomía; **descartar** la arquitectura.

**López Hernández y Almela (2021).** *Detección automática de errores lingüísticos en
textos clínicos.* Panace@ 22(53). Versión revisada: *Analysis of Context-Dependent Errors
in the Medical Domain in Spanish.* SAGE Open. https://doi.org/10.1177/21582440221148454
- Por qué: corpus real de > 2 millones de palabras de cuatro especialidades, incluida
  **urgencias**.
- Qué sostiene: urgencias es la especialidad con más errores dependientes del contexto;
  el error más frecuente es la omisión de tilde.
- Aplicación: valida trabajar sin tildes (E4.5) en lugar de restituirlas.
- Veredicto: **referencia**.

**Juan, Kim et al. (2022).** *Context-Sensitive Misspelling Correction of Clinical Text
via Conditional Independence.* CHIL. https://github.com/dalgu90/cim-misspelling
- Entrenable sin pares anotados, pero requiere modelo de lenguaje y GPU.
- Veredicto: **descartar** por hardware; plan B si aparece GPU.

### 2.10 Tildes

**Yarowsky (1994).** *Decision Lists for Lexical Ambiguity Resolution: Application to
Accent Restoration in Spanish and French.* ACL. https://arxiv.org/abs/cmp-lg/9406034
**(2021).** *Diacritics Restoration using BERT.* https://arxiv.org/abs/2105.11408
**(2022).** *Dilated CNN for Lightweight Diacritics Restoration.*
https://arxiv.org/abs/2201.06757
- Qué sostienen: restituir tildes es desambiguación léxica (`esta/está`,
  `medico/médico/medicó`), no ortografía; los métodos modernos requieren modelos.
- Aplicación: el pipeline hoy restituye tildes (`dias → días`). La recomendación es
  no restituirlas y trabajar sin tildes de extremo a extremo: no aporta al agrupamiento
  y es otra vía de cambio de significado. Al quitar diacríticos hay que proteger la ñ
  (`ano/año`). Como cambia todos los textos, E4.5 lo mide junto con el efecto en el
  agrupamiento (E7.3).
- Veredicto: **probar** (E4.5).

### 2.11 Texto en mayúsculas

**Mayhew et al. (2019).** *NER and POS when nothing is capitalized.* EMNLP.
https://aclanthology.org/D19-1650/ — y *Robust Named Entity Recognition with Truecasing
Pretraining.* https://arxiv.org/abs/1912.07095
- Qué sostienen: los modelos con mayúsculas informativas degradan sobre texto todo en
  mayúsculas; entrenar o evaluar con mezcla cased/uncased da el mejor resultado; el
  truecasing aporta información complementaria.
- Aplicación: respalda `recursos/casing.py`; obliga a minusculizar o truecasear antes de
  cualquier modelo preentrenado (E4.6, E5.7).
- Veredicto: **referencia**.

## 3. Detección de correcciones dañinas y evaluación

### 3.1 La unidad de análisis es la edición

**Bryant, Felice y Briscoe (2017).** *ERRANT: Automatic Annotation and Evaluation of
Error Types.* ACL. https://github.com/chrisjbryant/errant — **(2025).** *Multilingual
Grammatical Error Annotation.* https://arxiv.org/abs/2506.07719
- Qué sostiene: alineamiento Damerau-Levenshtein enriquecido entre original y
  corregido; extrae ediciones `(posición, token_original, token_corregido)` y las
  tipifica.
- Aplicación: ERRANT completo es excesivo (tipología para redacciones en inglés), pero
  la arquitectura sí: `difflib.SequenceMatcher` sobre tokens. Ya implementado en
  `fase2_ortografia/coherencia.py`. Habilita la auditoría por par distinto (E2.4).
- Veredicto: **adoptar** (ya en uso).

### 3.2 Auditar por par distinto, no por nota

- Observación aritmética: 9.311 notas × ~6 palabras ≈ 56.000 tokens; los pares distintos
  `(original → corrección)` serán del orden de 1.000–3.000, con cola larga donde los 200
  primeros cubren la mayoría de ocurrencias. Un humano revisa unos 300 pares por hora.
- Regla de no degradación: si `freq(original) ≥ freq(corrección)` en el corpus propio,
  revertir. Una corrección legítima va de una forma rara a una frecuente. Cubre los
  cuatro fallos observados. Coste: un contador.
- Aplicación: E2.4 (tabla de pares con cubos revertir / aceptar / revisar) y E4.1
  (comparar la regla estricta con la actual de factor 10 en `coherencia.py`).
- Veredicto: **adoptar** (E2.4), **probar** (E4.1).

### 3.3 Deriva semántica por embeddings

**(2025).** *Semantic Drift and Reporting Stability in VAERS.* medRxiv.
https://doi.org/10.1101/2025.11.10.25339934
- Por qué: es lo primero que se propone para detectar correcciones dañinas.
- Por qué no aquí: con seis palabras, cambiar un token mueve el vector mucho esté bien
  o mal la corrección; los embeddings subpalabra dan similitud **alta** a
  `ahogado/abogado` (comparten n-gramas), al revés de lo que se busca; y el original ya
  contiene erratas. Solo serviría a nivel de par de palabras con vectores entrenados en
  el propio corpus, y aun así es más débil que la regla de frecuencia.
- Veredicto: **descartar** a nivel de nota.

### 3.4 Errores críticos (estimación de calidad en traducción)

**WMT21 Quality Estimation, Critical Error Detection.**
https://www.statmt.org/wmt21/quality-estimation-task.html — **(2024).** *Towards Precise
Localization of Critical Errors in Machine Translation.* ACL Findings.
https://aclanthology.org/2024.findings-acl.177/ — **Rei et al. (2022).** *CometKiwi.*
https://arxiv.org/abs/2209.06243 — **Amrhein et al. (2022).** *ACES.*
https://arxiv.org/abs/2210.15615
- Qué se toma: la taxonomía minor / major / critical y las categorías de error crítico
  (negación invertida, entidad sustituida, número alterado), traducidas a triage:
  cambio de parte del cuerpo, de mecanismo de lesión, de síntoma, inserción o borrado de
  negación, alteración de número o lateralidad.
- Qué no se toma: los modelos (XLM-R large, supervisión masiva, GPU).
- Aplicación: etiquetas de gravedad en la guía de anotación (E0.6) y en el informe de
  reparación.
- Veredicto: **adoptar** la taxonomía; **descartar** los modelos.

### 3.5 Conjunto de evaluación con poco esfuerzo humano

**(2026).** *Illusions of the Gold Standard: Human Evaluation Protocols.*
https://arxiv.org/abs/2606.07936
- Técnicas, por relación valor/esfuerzo:
  1. Errores autoinducidos sobre notas limpias (coste humano cero): mide cobertura
     (Fivez 2017; Bravo-Candel 2021 con seis tipos de regla).
  2. Notas ya correctas pasadas por el corrector: mide precisión. **Es la evaluación
     que habría detectado los cuatro fallos** y la que falta en el pipeline.
  3. Muestreo estratificado por señal de riesgo (distancia, ratio de frecuencia,
     longitud), sobremuestreando estratos de alto riesgo. `evaluacion/escaneo.py` ya
     muestrea por rareza.
  4. Doble anotación en ~200 ítems para κ de Cohen; el resto con un anotador. Solo el 6 %
     de los trabajos publicados aplica filtrado de calidad.
- Aplicación: E2.3 y E0.6.
- Veredicto: **adoptar**.

### 3.6 Métricas

**(2024).** *PERCORE.* https://arxiv.org/abs/2407.14789 — **(2022).** *DPCSpell.*
https://arxiv.org/abs/2211.03730
- Separar detección (precisión y cobertura) de corrección (precisión y cobertura);
  F0.5 como métrica global (estándar en CoNLL-2014 y BEA-19 porque penaliza corregir de
  más); CER/WER solo como control agregado: `volcamiento → tocamiento` tiene un CER
  mínimo y es un error crítico.
- Métrica propia no estándar: `tasa_intervencion_texto_limpio` = proporción de tokens
  del léxico de alta frecuencia que el corrector modifica; objetivo < 0,1 %.
- Aplicación: E2.2.
- Veredicto: **adoptar**.

## 4. Recursos léxicos y de datos

Para cada recurso: qué es, enlace, licencia, por qué, cómo se integra, prioridad.

### 4.1 Gazetteers SNOMED del BSC — prioridad 1

**SympTEMIST gazetteer.** https://doi.org/10.5281/zenodo.8223653 (registro vigente:
https://zenodo.org/records/10635215). CC-BY-4.0.
- 164.817 alias en español de síntomas, signos y hallazgos SNOMED CT; TSV con `code,
  language, term, semantic_tag, mainterm`. El ZIP completo pesa 452 MB; el TSV es
  pequeño.
- Por qué: es la categoría semántica exacta de un motivo de consulta, en español, sin
  trámite de licencia SNOMED.
- Uso: fuente curada del léxico clínico (E3.4); detector de errores por no pertenencia;
  anclas para nombrar clusters; el corpus gold de 1.000 casos sirve para medir la
  normalización.

**DISTEMIST gazetteer.** https://zenodo.org/records/6458115. CC-BY-4.0. ~111 k códigos
de enfermedades con sinónimos, 9,1 MB, mismas columnas. Uso: E3.4.

**MedProcNER gazetteer.** https://zenodo.org/records/7929830. CC-BY-4.0. Procedimientos,
con mapeos a MeSH. Prioridad media.

### 4.2 MedLexSp — prioridad 1 (requiere trámite)

**Campillos-Llanos (2022).** *MedLexSp – a medical lexicon for Spanish medical natural
language processing.* J Biomed Semantics. https://doi.org/10.1186/s13326-022-00281-5 —
https://github.com/lcampillos/MedLexSp — licencia:
https://www.lllf.uam.es/ESP/nlpdata/wp1/MedLexSp_License.pdf
- 100.887 lemas, **302.543 formas flexionadas**, 42.958 CUIs de UMLS. Fusiona
  MedlinePlus, el Diccionario de Términos Médicos de la RANM, MeSH, SNOMED-CT, MedDRA,
  CIE-10, ATC, NCI, OMIM, OrphaData. Incluye un lematizador para spaCy y Stanza.
- Licencia: gratuito para investigación/educación previa firma; la versión libre
  excluye términos con copyright (SNOMED, MedDRA). Uso comercial: acordar con el autor.
- Por qué: es el único recurso español con formas flexionadas; las notas están en
  mayúsculas y sin lematizar, y un diccionario de lemas no sirve como referencia del
  corrector.
- Uso: E3.9. Herramienta derivada: **medspaner** (https://github.com/lcampillos/medspaner),
  anotador híbrido con negación, especulación, temporalidad y experienciador; **AGPL-3.0**
  (contagia licencia si se distribuye).

### 4.3 MeSpEn_Glossaries — prioridad baja

https://github.com/PlanTL-GOB-ES/MeSpEn_Glossaries — https://doi.org/10.5281/zenodo.2205690.
CC-BY-4.0 (SEAD 2018).
- 46 glosarios bilingües; el par inglés-español tiene 125.645 entradas; TSV de dos
  columnas (`pd.read_csv(f, sep="\t", header=None)`).
- Veredicto honesto: son glosarios de traducción, sesgados a terminología culta, no a
  cómo escribe un auxiliar de triage. Tercera capa detrás de SympTEMIST/DISTEMIST y
  MedLexSp (E3.10); no invertir en el mapeo inglés-español.

### 4.4 Abreviaturas

**AbreMES-DB.** https://github.com/PlanTL-GOB-ES/AbreMES-DB —
https://doi.org/10.5281/zenodo.2207130. CC-BY-4.0. Seis TSV (`abbreviations`,
`definitions`, `pairs`, `CoAbbreviations`, `publications`, `preprocessed`) minados de
SciELO, IBECS y PubMed detectando `SIGLA (definición)` en la misma frase.
- Limitación: literatura científica, no notas de enfermería colombianas.
- Lo accionable es la **técnica**: un script de ~30 líneas sobre las 94 k notas propias
  mina las abreviaturas institucionales (E3.8).

**BARR2 / SPACCC.** https://temu.bsc.es/BARR2/ — 1.000 casos clínicos con pares
abreviatura-definición anotados por expertos. Uso: gold para evaluar el expansor.

**Cosnautas, Diccionario de siglas médicas.** Suscripción; no integrable. Descartado.

**(2020).** Inventario de sentidos de acrónimos por especialidad.
https://pubmed.ncbi.nlm.nih.gov/32570393/ — **(2021).** *Medical Abbreviation and
Acronym Meta-Inventory.* Sci Data. https://doi.org/10.1038/s41597-021-00929-4 — las
abreviaturas son el 30–50 % de las palabras en texto clínico frente a < 1 % en texto
general; en triage, el extremo alto. Expandir solo las no ambiguas (E5.3).

### 4.5 Fármacos *[descargas verificadas]*

**CUM – Código Único de Medicamentos (INVIMA).** datos.gov.co, dataset `i7cb-raxc`.
CSV: https://www.datos.gov.co/api/views/i7cb-raxc/rows.csv?accessType=DOWNLOAD — API:
https://www.datos.gov.co/resource/i7cb-raxc.json. Ley 1712 de 2014.
- 157.756 filas × 29 columnas. Usar el campo **`descripcionatc`** (1.450 valores
  limpios: `ACETAZOLAMIDA`, `ABACAVIR/ZIDOVUDINA/LAMIVUDINA`). **No usar
  `principioactivo`** (dosis embebidas). `producto` (9.471 valores) da nombres
  comerciales, filtrando tokens con dígitos. La fuente trae erratas (`AACIDO`).
- Por qué: colombiano, ya en mayúsculas, con los nombres comerciales que circulan aquí.
- Uso: E3.5, lista de protección.

**Nomenclátor AEMPS (CIMA).** https://listadomedicamentos.aemps.gob.es/prescripcion.zip
(15,4 MB). Devuelve **403 sin User-Agent de navegador**. Usar
`DICCIONARIO_PRINCIPIOS_ACTIVOS.xml` (729 KB) → 3.375 entradas, 2.718 tokens únicos;
ignorar `Prescripcion.xml` (193 MB). Licencia: leer `Aviso_Legal_Nomenclator.pdf`
antes de publicar derivados. Uso: E3.5, complemento.

ATC/DDD de la OMS (200 EUR), RxNorm (inglés, licencia UMLS), DrugBank (licencia
comercial): **descartados**; el CUM da la descripción ATC en español gratis.

### 4.6 Topónimos y nombres propios *[descargas verificadas]*

**DANE DIVIPOLA.** Municipios:
https://geoportal.dane.gov.co/descargas/divipola/DIVIPOLA_Municipios.xlsx (1.122).
Centros poblados: `DIVIPOLA_CentrosPoblados.xlsx` (1 MB). Ley 1712. Uso: E3.6.

**GeoNames Colombia.** https://download.geonames.org/export/dump/CO.zip (2,1 MB;
82.093 registros; 35.945 de clase P, 1.519 de clase A). CC-BY-4.0. Dos trampas: **no
tokenizar la columna `alternatenames`** (contiene `CANCIONES`, `SIETE`, `EXTERIOR`);
usar solo la columna 2. Parsear en Python con `encoding="utf-8"`. Filtrar por códigos
`ADM1|ADM2|PPLA|PPLA2|PPLC` da 1.155 entradas ≈ DIVIPOLA. Prioridad media.

**REPS – Registro Especial de Prestadores.** datos.gov.co, dataset `c36g-9fc2`. CSV:
https://www.datos.gov.co/api/views/c36g-9fc2/rows.csv?accessType=DOWNLOAD. Ley 1712.
- 76.821 filas: 19.551 IPS, 54.657 profesionales independientes. La columna
  `nombreprestador` de los profesionales es una lista de nombres reales colombianos, y
  exactamente la población cuyos nombres aparecen en notas de triage. Medido sobre 5.000
  filas: 1.951 tokens únicos (`MARIA, JUAN, CARLOS, RESTREPO, GOMEZ, GARCIA, RAMIREZ,
  ARANGO, GIRALDO, VELEZ, MEJIA…`). El filtro exacto es
  `claseprestador like 'Instituciones%'` (no `'Instituciones - IPS'`).
- Uso: E3.6, listas de nombres e IPS.

**INE (España).** https://www.ine.es/daco/daco42/nombyapel/nombres_mas_frecuentes.xls y
`apellidos_mas_frecuentes.xls`. Complemento barato. Prioridad media.

**EPS.** Sin dataset limpio (ADRES y MinSalud publican PDF). ~30 entidades: transcribir a
mano (E3.6).

**Siglas administrativas y clínicas.** ~40 entradas a mano (`EPS IPS ARL POS PBS SISBEN
ESE UCI UCIN URG TRIAGE SOAT ADRES MIPRES RIPS CUM CIE DX RX TAC EKG ECG TA FC FR SATO
SPO2 HTA DM EPOC IRA EDA AINE VO IV IM SC SL PRN AM PM`). Probablemente el mayor impacto
por token de toda la lista: son siglas de 2–4 letras, las que SymSpell destroza con
distancia 1–2 (E3.2).

Advertencia de diseño para todas las listas: van a una **lista de protección** (bypass
antes del corrector), no al diccionario de frecuencias, porque nombres y fármacos suelen
estar a distancia 1 de palabras comunes (`SUAREZ/SUAVE`). Y hay que excluir los tokens que
ya son palabras comunes (`CORREA`, `LEON`, `ROSA`, `PALMA`, `CRESPO`) o bloquearán
correcciones legítimas.

### 4.7 Negación

**Lima et al. (2020).** *NUBes: A Corpus of Negation and Uncertainty in Spanish Clinical
Texts.* LREC. https://aclanthology.org/2020.lrec-1.708/ — 29.682 frases anotadas con
claves, alcances y eventos; incluye secciones de motivo de consulta.
**(2022).** *Negation and uncertainty detection in Spanish clinical texts.* PeerJ CS.
https://doi.org/10.7717/peerj-cs.913 — BiLSTM sobre NUBes, F1 90 % en alcance.
**(2023).** NegEx + CNN. BMC MIDM. https://doi.org/10.1186/s12911-023-02301-5
**NegEx-MES.** https://zenodo.org/record/2542567. **MIT**, 69 KB. Disparadores en
español para NegEx.
- Por qué: en embeddings promediados, `no refiere dolor torácico` y `refiere dolor
  torácico` quedan casi idénticos y caen en el mismo cluster. Las reglas por defecto de
  medspaCy son inglesas.
- Uso: E3.7 (disparadores) y E5.2 (prefijo `NEG_` en el alcance antes de vectorizar).

### 4.8 Corpus y terminologías de referencia

**CoWeSe.** https://zenodo.org/records/5510033. CC-BY-4.0. 750 M tokens de texto
biomédico español. Útil para frecuencias de dominio; pesado. Prioridad media.

**FastText Spanish Medical Embeddings.** https://zenodo.org/record/2542721. CC-BY-4.0,
**41,1 GB**. Descartado por tamaño: entrenar fastText propio sobre las 94 k notas.

**Báez, Villena, Rojas, Durán, Dunstan et al. (2020).** *The Chilean Waiting List
Corpus.* Clinical NLP @ EMNLP. https://aclanthology.org/2020.clinicalnlp-1.32/ — 9.000
derivaciones chilenas, 900 anotadas (9.029 entidades, 32 % anidadas). Único corpus
clínico público de español latinoamericano con texto breve. Uso: validar que el pipeline
no está sobreajustado al español peninsular (E7.3).

**CIAP-2 / ICPC-2.** http://www.agapap.org/datos/CIAP2.pdf (también en UMLS como
`ICPCSPA`). Clasificación diseñada para la razón de consulta en atención primaria (~700
rúbricas por aparato). Uso: taxonomía de referencia para nombrar y validar clusters, no
como etiquetas de entrenamiento (E7.3).

**SNOMED CT edición española.** Licencia de afiliado vía Centro Nacional de Referencia;
trámite de semanas; estado de licenciamiento en Colombia sin confirmar. Descartado a
corto plazo: los gazetteers del BSC cubren la necesidad.

**UMLS Metathesaurus.** https://uts.nlm.nih.gov — cuenta gratuita; subconjunto español
~451 k conceptos (fuentes `SCTSPA`, `MSHSPA`, `MDRSPA`, `ICPCSPA`, `MEDLINEPLUS_SPA`).
Solo si se reentrena un modelo de enlace.

**CIE-10 Colombia (SISPRO).**
https://web.sispro.gov.co/WebPublico/Consultas/ConsultarDetalleReferenciaBasica.aspx?Code=cie10
— Colombia en transición a CIE-11 (Resolución 1442 de 2024). Ya en uso parcial
(`datos/lexico_externo.txt`); vocabulario de diagnóstico, no de motivo.

**RANM, Diccionario de Términos Médicos.** https://dtme.ranm.es — 52.000 términos,
consulta web libre, sin API ni descarga, copyright reservado. Su contenido está dentro de
MedLexSp. Descartado programáticamente.

**DeCS/MeSH español.** https://decs.bvsalud.org — vocabulario de indexación
bibliográfica. Descartado para triage.

**Lista de palabras del español (gist de victorhck).**
https://gist.github.com/victorhck/9ed2f9b95e675e9e71be142816791afd — LanguageTool 6.8
y SymSpell ya cubren el diccionario general; aporte marginal. Evaluar solo si E3.3
muestra huecos de vocabulario general.

**hermitdave/FrequencyWords.** https://github.com/hermitdave/FrequencyWords — CC-BY-SA
3.0 (copyleft). Preferir fuentes propias.

## 5. Modelos

### 5.1 HUMADEX/spanish_medical_ner — descartado con evidencia

https://huggingface.co/HUMADEX/spanish_medical_ner
- Verificado en su `config.json`: `"_name_or_path": "bert-base-cased"`,
  `"vocab_size": 28996`. **El modelo base es BERT en inglés**, con vocabulario WordPiece
  inglés y cased. Sobre español, `cefalea` o `disnea` se fragmentan en subtokens sin
  sentido y las tildes están mal cubiertas.
- Entrenado con conjuntos anotados y **traducciones automáticas** de texto médico
  inglés; etiquetado débil. P 0,771 / R 0,781 / F1 0,776 sobre su propio test (no
  comparable con evaluaciones sobre EHR reales). 13 clases BIOES (PROBLEM / TEST /
  TREATMENT). Apache-2.0.
- Veredicto: **descartar**. Sobre español colombiano en mayúsculas y mal escrito, un
  tokenizador inglés es el peor escenario posible.

### 5.2 Alternativas para reconocimiento de entidades

Todas RoBERTa-base (~125 M parámetros, mismo coste en CPU), con tokenizador español y
preentrenamiento sobre 1,1 B tokens biomédico-clínicos en español.

**BSC-NLP4BIA/bsc-bio-ehr-es-carmen-symptemist.**
https://huggingface.co/BSC-NLP4BIA/bsc-bio-ehr-es-carmen-symptemist — CC-BY-4.0. NER
de síntomas y signos; entrenado sobre CARMEN-I (EHR reales) y SympTEMIST. P 0,743 / R
0,764 / F1 0,753 sobre EHR reales. **Requiere pre-tokenizar en palabras** antes de pasar
el texto. Prioridad alta para notas largas (E5.7 nivel 2).

**lcampillos/roberta-es-clinical-trials-ner.**
https://huggingface.co/lcampillos/roberta-es-clinical-trials-ner — ANAT / CHEM / DISO /
PROC; P 0,850 / R 0,881 / **F1 0,865**. Registro formal (ensayos clínicos). Variantes en
`medspaner/` (7 grupos; negación y especulación; temporalidad), AGPL-3.0.

**PlanTL-GOB-ES pharmaconer / cantemist.** Fármacos y morfología tumoral. Fuera de
dominio. Baja.

**ixa-ehu/ixambert-base-cased.** Multilingüe de Wikipedia, no clínico. Descartado.

**IIC/RigoBERTa-Clinical y RigoBERTa 2.** **García Subies, Barbero Jiménez y Martínez
Fernández (2024).** JAMIA. https://doi.org/10.1093/jamia/ocae054 — el comparativo más
grande (> 3.000 modelos, 17 corpus): "los mejores modelos no son los clínicos sino los de
propósito general" y "los más grandes no siempre son los mejores"; RigoBERTa 2 F1 medio
0,880. Lección: **medir, no asumir** que el modelo clínico gana; con texto tan degradado,
la robustez del preentrenamiento general puede pesar más. Incluir en la comparación de
E7.3.

### 5.3 ¿Hace falta NER? Enlace de menciones cortas

Con mediana de seis palabras, una nota es prácticamente una única mención; lo útil no es
segmentar sino enlazar la mención a un concepto.

**Verma, Bagherzadeh y Bergler (2022).** *CLaCLab at SocialDisNER.*
https://arxiv.org/abs/2209.03528 — F1 estricto 0,869 (media de la competición 0,675) en
NER de enfermedades sobre **tweets en español** inyectando gazetteers UMLS y DISTEMIST
como características explícitas. Idea: el gazetteer no es un respaldo, es una
característica de primera clase.

**Gallego, López-García, Gasco, Krallinger y Veredas (2024).** *ClinLinker.* ICCS.
https://doi.org/10.1007/978-3-031-63775-9_19 — https://arxiv.org/abs/2404.06367 —
bi-encoder + cross-encoder sobre `roberta-base-biomedical-clinical-es`, entrenamiento
contrastivo con multi-similarity loss y negativos difíciles, > 1 M de conceptos UMLS en
español. Top-25: DisTEMIST 0,871 (0,763 en códigos no vistos), MedProcNER 0,894.

**Gallego et al. (2025).** *Enhancing cross-encoders using knowledge graph hierarchy for
medical entity linking in zero- and few-shot scenarios.* Knowledge-Based Systems.
https://doi.org/10.1016/j.knosys.2025.113141 — modelo:
https://huggingface.co/ICB-UMA/ClinLinker-KB-GP — enriquece cada concepto con sus padres
y abuelos de la jerarquía SNOMED; los conceptos hermanos quedan cerca en el espacio
vectorial. Mejora de +40 puntos sobre benchmarks previos en zero-shot. Para agrupar
motivos de consulta ofrece granularidad controlable sin taxonomía manual.

**BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es.**
https://huggingface.co/BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es —
Apache-2.0; entrenado sobre entradas españolas de UMLS 2023AA incluyendo nombres
comerciales de fármacos. **Usar el token [CLS]** como embedding, `max_length = 25`:
diseñado para menciones cortas. Más ligero que `bge-m3` (XLM-R large).

**Gallego y Veredas (2024).** *Recognition and normalization of multilingual symptom
entities using in-domain-adapted BERT models and classification layers.* Database.
https://doi.org/10.1093/database/baae087 — https://github.com/ICB-UMA/WNT-Softmax —
capa WNT-softmax inicializada con el embedding promedio de todos los términos de cada
concepto (+5,5 % top-1). **Idea trasplantable sin entrenar nada**: centroide por
concepto SNOMED promediando los sinónimos del gazetteer; asignar cada nota al centroide
más cercano. Agrupamiento semisupervisado con etiquetas interpretables desde el primer
día, en CPU.

**Borchert et al. (2024).** *xMEN.* JAMIA Open 8(1):ooae147.
https://doi.org/10.1093/jamiaopen/ooae147 — https://github.com/hpi-dhc/xmen — candidatos
por ensemble de TF-IDF sobre n-gramas de caracteres + SapBERT, k = 64; reranking con
regularización de rango (λ = 1,0). DisTEMIST F1@1: 0,426 sin supervisión, 0,654
supervisado. El ensemble sin supervisión es viable en CPU y tolerante a erratas (el
TF-IDF de caracteres absorbe erratas; SapBERT absorbe jerga).

**(2024).** *Entity normalization in a Spanish medical corpus using a UMLS-based
lexicon.* LRE. https://doi.org/10.1007/s10579-024-09755-7 — sustituir por forma
canónica en lugar de añadir glosa.

**Lopez Osornio, Luna et al. (2007).** *Creation of a local interface terminology to
SNOMED CT.* https://pubmed.ncbi.nlm.nih.gov/17911820/ — y *Terminology Services*
https://pmc.ncbi.nlm.nih.gov/articles/PMC6115242/ — Hospital Italiano de Buenos Aires:
> 2 M de términos en español mapeados a SNOMED CT durante años de producción. Su lista
de servicios terminológicos (normalización, autocompletado, **corrección ortográfica**,
matching léxico, localidad semántica, composición) es una arquitectura de referencia;
corrección y matching aparecen como componentes del mismo servicio.

Estrategia por niveles que resulta (E5.7): nivel 0, `PhraseMatcher` contra
SympTEMIST + DISTEMIST (milisegundos); nivel 1, embedding de la mención + vecino más
cercano contra el gazetteer con SapBERT-es o ClinLinker-KB-GP; nivel 2, NER transformer
solo para notas largas con varios síntomas.

### 5.4 Jerga de pacientes → terminología

**Ibrahim et al. (2021).** PeerJ Computer Science.
https://pmc.ncbi.nlm.nih.gov/articles/PMC8371999/ — **Jiang y Yang (2019).** JMIR Medical
Informatics. https://pmc.ncbi.nlm.nih.gov/articles/PMC6552449/
- Hallazgo negativo: **no existe un Consumer Health Vocabulary consolidado para
  español** ni un recurso de jerga médica colombiana (verificado). El Open Access CHV es
  solo inglés.
- Receta: entrenar embeddings sobre el corpus lego; para cada término técnico, sus
  vecinos más cercanos; un léxico auxiliar filtra falsos positivos. Trasplante: fastText
  sobre las 94 k notas; para cada término del gazetteer, los vecinos que no están en
  ninguna terminología son, con alta probabilidad, jerga local y abreviaturas
  institucionales (E3.8 / E5.7).

**SocialDisNER (SMM4H 2022)** y **SMM4H 2023 Task 3**
(https://pmc.ncbi.nlm.nih.gov/articles/PMC10659479/): menciones de enfermedades y
síntomas en tweets en español, el segundo con español **latinoamericano**. Lo más
cercano a jerga de pacientes hispanoamericanos con anotación pública. Prioridad media.

### 5.5 Coste en CPU

**Sanh et al. (2019).** *DistilBERT.* https://arxiv.org/abs/1910.01108 — **Hugging Face.**
*Scaling-up BERT Inference on CPU.* https://huggingface.co/blog/bert-cpu-scaling-part-1 —
**(2026).** *Efficient INT8 Inference of Small NLP Models on Server CPUs.*
https://arxiv.org/abs/2608.18182
- El i7-8550U (Kaby Lake R) tiene AVX2 pero **no AVX-512 VNNI**; los 2,9× de aceleración
  INT8 publicados se miden en Xeon con VNNI. Aquí esperar 1,5–2×. Exportar con
  `optimum[onnxruntime]` en modo `avx2`.
- Estimación para 94 k notas con `max_length = 32`: 20–45 min en FP32; 10–25 min con ONNX
  INT8; el matching de gazetteer, segundos. El NER es viable como trabajo de una tanda;
  lo inviable es iterar sobre el corpus completo: calibrar con 5.000 notas.

## 6. Normalización y agrupamiento

### 6.1 Glosas duplicadas

**(2020).** *Discrete Word Embedding for Logical Natural Language Understanding.*
https://arxiv.org/abs/2008.11649
- Mecanismo: en embeddings por promedio, repetir un concepto empuja el vector hacia el
  concepto repetido; en TF-IDF duplica el peso.
- Efecto real, peor de lo que parece: en una nota de 6 palabras una glosa de 1–2 tokens
  cambia el 20–30 % del contenido, y como **solo algunas notas reciben glosa** (las que
  el pipeline supo mapear), la presencia de glosa es una variable oculta correlacionada
  con el éxito del mapeo, no con la clínica. El clustering puede separar "glosadas" de
  "no glosadas". Es un fallo silencioso: los clusters se ven razonables.
- Mitigación, por orden: (1) no inyectar la glosa; concepto en columna aparte
  (`concepto_normalizado`); (2) sustituir en vez de añadir; (3) deduplicar por concepto
  antes de vectorizar. Verificación en diez minutos: entrenar el clustering con y sin
  glosas y comprobar si la variable binaria "tiene glosa" predice el cluster.
- Restricción del proyecto: `clustering/etiquetas.py` usa las glosas para nombrar
  clusters (`PLAN.md` §6); E5.1 se coordina con ese módulo.

### 6.2 Negación con alcance

Ver 4.7. Recomendación concreta y barata: disparadores (`no`, `niega`, `sin`,
`descarta`, `ausencia de`, `nunca`) con ventana de 3–4 tokens y prefijo `NEG_` en los
tokens dentro del alcance antes de vectorizar (E5.2). Coste: microsegundos; efecto en la
calidad del agrupamiento, grande.

### 6.3 Abreviaturas

Ver 4.4. **Cortes, Genaro, Maraboli y Manríquez-Troncoso (2025).** *Automated Triage
Classification in Emergency Services Using Spanish Clinical Notes.* NeurIPS WiML.
https://openreview.net/forum?id=OJNHTTWMFA — notas de triage chilenas clasificadas
C1–C5; **construyeron un diccionario de abreviaturas específico del dominio como paso
obligatorio**; SentencePiece con 31.000 tokens; híbrido notas + estructurado AUROC 0,96.
Otro equipo con el mismo problema llegó a la misma conclusión. Expandir solo las no
ambiguas (E5.3).

### 6.4 Lematización

Snowball es despreciable en coste; spaCy `sm` sobre 94 k notas, minutos; Stanza, 10×
más lento sin ganancia. Pero el stemming español es agresivo y colapsa distinciones
clínicas (`sangra / sangrado / sangrante`), y en una nota de 6 palabras cada token es
~17 % de la señal. Recomendación: no lematizar, o solo sustantivos y adjetivos; medir
ambas (E5.4). Los embeddings subpalabra ya capturan la relación morfológica.

### 6.5 Motivos de consulta y agrupamiento

**Chang, Hong y Taylor (2020).** *Generating contextual embeddings for emergency
department chief complaints.* JAMIA Open 3(2):160–166.
https://doi.org/10.1093/jamiaopen/ooaa022 — https://github.com/dchang56/chief_complaints
- El trabajo más parecido al objetivo: 1,8 M de motivos de consulta de 7 servicios de
  urgencias. Clinical BERT, 3 épocas, lr 1e-4, **max_seq_length 64**, mean pooling;
  t-SNE + mezcla gaussiana; **silueta óptima en 15 clusters**; con 434 etiquetas top-1
  0,65 / top-5 0,92.
- Dos observaciones que se adoptan como criterio: los embeddings se distribuyen de forma
  clínicamente coherente (valida embeddings + clustering sobre chief complaints); muchos
  "errores" eran predicciones razonables (sinónimos, hiperónimos) — **no evaluar el
  clustering contra una taxonomía rígida**; medir coherencia semántica y revisar a mano.
- Referencia de calibración para E7.3: si el número de clusters difiere en órdenes de
  magnitud, revisar hiperparámetros antes que el modelo.

**Chapman, Christensen, Wagner et al. (2005).** *Classifying free-text triage chief
complaints into syndromic categories with NLP.* https://pubmed.ncbi.nlm.nih.gov/15617980/
— clásico; método superado; su taxonomía sindrómica sirve como etiquetado grueso de
clusters.

**Nobles, Vilk, Chen et al. (2019, 2022).** MUSES / *Presyndromic surveillance.* OJPHI
https://ojphi.jmir.org/2019/1/e62431 — Science Advances
https://doi.org/10.1126/sciadv.abm4920 — topic modeling no supervisado sobre chief
complaints para descubrir síndromes no catalogados. Justifica no partir de una taxonomía
cerrada.

**(2019).** *Extracting information from free text through unsupervised graph-based
clustering.* https://arxiv.org/abs/1909.00183 — paragraph vectors + detección de
comunidades; útil si se quiere jerarquía. **(2025).** *Weakly Supervised Medical Entity
Extraction and Linking for Chief Complaints.* https://arxiv.org/abs/2509.01899 — 1,2 M de
motivos con supervisión débil.

**Grootendorst (2022).** *BERTopic.* https://arxiv.org/abs/2203.05794 —
https://arxiv.org/abs/2212.08459 — BERTopic_Teen
https://pmc.ncbi.nlm.nih.gov/articles/PMC12378273/ — embeddings → UMAP → HDBSCAN →
c-TF-IDF; supera a LDA/NMF en texto corto; **c-TF-IDF da nombres interpretables de
cluster** a partir de las propias notas. Con mediana de 6 palabras: `n_neighbors` bajo y
`min_cluster_size` calibrado.

**(2021).** *TF-IDF vs Word Embeddings for Morbidity Identification in Clinical Notes.*
https://arxiv.org/abs/2105.09632 — TF-IDF resulta competitivo o superior en varias
métricas. Con notas de 6 palabras y vocabulario cerrado, **TF-IDF sobre n-gramas de
caracteres (3–5) es la línea base obligatoria** antes de invertir en nada neuronal (E7.3).

**Sobre `bge-m3`.** **(2026).** Evaluación de robustez multilingüe.
https://arxiv.org/abs/2605.31142 — obtiene el mejor ranking para español, con
variabilidad. **(2025).** *Towards Domain Specification of Embedding Models in Medicine.*
https://arxiv.org/abs/2507.19407 — los generalistas pierden en tareas médicas.
*Clustering Clinical Notes in Spanish Based on Contextualized Embeddings.*
https://doi.org/10.1007/978-3-032-13729-6_17 — para separaciones gruesas XLM-RoBERTa y
roberta-biomedical-clinical-es empatan (ARI = 1); la ventaja del modelo de dominio aparece
en granularidad fina, que es el caso. **Reimers y Gurevych (2019).** *Sentence-BERT.*
https://arxiv.org/abs/1908.10084 — **(2024).** *Scandinavian Embedding Benchmarks.*
https://arxiv.org/abs/2406.02396 (fastText: máximo throughput y robusto a erratas por
construcción).
- Comparativa recomendada (E7.3, una tarde): `bge-m3` (XLM-R large) frente a
  `ClinLinker-KB-GP`, `SapBERT-es` y `intfloat/multilingual-e5-small` (118 M; recordar
  los prefijos `query:` / `passage:`, omitirlos degrada en silencio). Métricas: ARI y
  silueta sobre 300–500 notas anotadas.

## 7. Hardware y coste

- i7-8550U (4 núcleos / 8 hilos, AVX2, sin AVX-512 VNNI), 16 GB (5,9 GB libres en la
  medición), UHD 620 sin CUDA, 241 GB libres. `torch 2.6.0+cpu`.
- Ollama `qwen2.5:3b-instruct`: 5,5 tokens/s (48 tokens en 8,7 s; carga 8,3 s).
  `gemma4:26b` (18 GB) no cabe en RAM. Con un prompt de reescritura sobre una nota real:
  `máscara de no reinhalación → vía nasal` (cambia el dispositivo), `chupeteo → uso de
  chupete` (destruye un signo), `crisis convulsiva → convulsión epiléptica` (inventa
  etiología). Decisión: `decisiones/2026-09-15-modelo-generativo.md`.
- Regla operativa: calibrar con muestras de 5.000 notas; correr el corpus completo una
  vez por versión del corrector.

## 8. Matriz de decisiones

| Fuente / recurso | Ítem del plan | Veredicto |
|---|---|---|
| Wilcox-O'Hearn 2014 | principios, E2.2 | referencia |
| Singh 2026 | E3.3, E4.2 | adoptar |
| Lee 2021 | E3.4, E4.7 | adoptar / probar |
| Kernighan 1990; Brill y Moore 2000 | E4.4 | probar |
| Islam e Inkpen 2012; trigramas 2023; KenLM | E4.4 | probar |
| SymSpell | E4.2 | adoptar (ya en uso) |
| Fonética española 2016; Meta-Soundex | E4.3 | probar |
| Salazar 2020; BEDSpell; Vartani; Hu 2021; bsc-bio-ehr-es | E4.6 | probar (solo zona gris) |
| Fivez 2017 (clinspell) | E4.7, E2.3 | probar / adoptar |
| Bravo-Candel 2021 | E4.8 | adoptar parámetros; descartar seq2seq |
| López Hernández y Almela 2021 | E4.5 | referencia |
| Yarowsky 1994; diacríticos BERT/CNN | E4.5 | probar (no restituir) |
| Mayhew 2019 | E4.6, E5.7 | referencia |
| ERRANT | E2.4 | adoptar (ya en uso) |
| WMT CED / ACES | E0.6 | adoptar taxonomía |
| Deriva por embeddings (VAERS) | — | descartar |
| Gold standard (Illusions 2026) | E0.6, E2.3 | adoptar |
| PERCORE / DPCSpell / F0.5 | E2.2 | adoptar |
| SympTEMIST, DISTEMIST, MedProcNER | E3.4 | adoptar |
| MedLexSp | E3.9 | adoptar (trámite) |
| MeSpEn | E3.10 | probar (baja) |
| AbreMES (técnica), BARR2 | E3.8 | adoptar técnica |
| CUM, AEMPS | E3.5 | adoptar |
| DIVIPOLA, REPS, INE, GeoNames | E3.6 | adoptar / evaluar |
| Siglas a mano | E3.2 | adoptar |
| NegEx-MES, NUBes | E3.7, E5.2 | adoptar |
| CoWeSe | E3.3 | evaluar |
| FastText médico (41 GB) | — | descartar |
| Corpus chileno | E7.3 | evaluar |
| CIAP-2 | E7.3 | evaluar |
| SNOMED, UMLS, RANM, DeCS | — | descartar a corto plazo |
| HUMADEX | — | descartar |
| carmen-symptemist; lcampillos NER | E5.7 | probar |
| JAMIA 2024 (RigoBERTa) | E7.3 | probar |
| ClinLinker(-KB-GP); SapBERT-es; WNT-softmax; xMEN | E5.7, E7.3 | probar (prioridad) |
| Ibrahim 2021; Jiang 2019 | E3.8, E5.7 | adoptar receta |
| Glosas (Discrete embedding 2020) | E5.1 | probar |
| Cortes 2025 | E5.3 | referencia |
| Chang 2020; Chapman 2005; MUSES; BERTopic; TF-IDF char | E7.3 | adoptar línea base / probar |
| INT8 en CPU | E5.7 | referencia |

## 9. Huecos en la literatura

1. No existe corrección ortográfica contextual publicada para español clínico
   latinoamericano de registro breve.
2. No existe un vocabulario de salud del consumidor en español ni un recurso de jerga
   médica colombiana.

Ambos son construibles con las recetas de 2.2/2.8 y 5.4 sobre los datos propios, y
constituirían contribución original.

## 10. Limitaciones de esta revisión

- Se hizo en una sesión, con dos agentes; puede haber trabajos relevantes no
  encontrados. Cada etapa del plan que toque un tema debe completar esta sección con lo
  que descubra (política de mantenimiento, `PLAN.md` §3.5).
- Las cifras de rendimiento de los modelos son las reportadas por sus autores sobre sus
  propios conjuntos; no son comparables entre sí ni con este corpus hasta medirlas aquí.
- Las licencias se registraron en la fecha de consulta; se re-verifican al descargar
  (E3.1).


## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | previo al plan | Primera versión |
| 2026-09-15 | revisión v2 | Reescrito fuente por fuente con enlace, motivo, aplicación y veredicto; matriz de decisiones |
