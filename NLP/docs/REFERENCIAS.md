# Referencias, recursos y licencias

Bibliografía, recursos de datos, modelos y software considerados para la fase NLP del
proyecto de triage. Este documento cumple dos funciones: reconocer la autoría de las
ideas y recursos que se usan (obligación de atribución) y dejar constancia de lo que se
evaluó y se descartó, para que no se vuelva a evaluar.

Convenciones de este documento:

- **Estado** indica la relación del recurso con el proyecto: `en uso`, `pendiente`
  (previsto en el plan, no integrado), `evaluar` (candidato, decisión abierta),
  `descartado` (con motivo).
- **Verificación**: las citas fueron recopiladas por agentes de investigación el
  2026-09-15 a partir de las fuentes indicadas. Las marcadas `[descarga verificada]`
  se descargaron y comprobaron durante la investigación. Antes de cualquier
  publicación externa (artículo, informe institucional) deben re-verificarse DOI y
  URL una a una.
- Las obligaciones de licencia se resumen en la sección 5.

---

## 1. Artículos, tesis y actas

Formato: Autores (año). Título. Publicación. Identificador. — Idea que se toma.

### 1.1 Corrección ortográfica

- Wilcox-O'Hearn, L. A. (2014). *Detection is the central problem in real-word spelling
  correction*. https://arxiv.org/abs/1408.3153. — En errores de palabra real la detección domina el
  error total; el coste de corregir una palabra correcta es asimétricamente mayor que
  dejar un error. Fundamento de la política conservadora del corrector.
- Kernighan, M. D., Church, K. W., Gale, W. A. (1990). *A Spelling Correction Program
  Based on a Noisy Channel Model*. COLING 1990. https://doi.org/10.3115/997939.997975 — Modelo de
  canal ruidoso: maximizar P(c)·P(t|c).
- Brill, E., Moore, R. C. (2000). *An Improved Error Model for Noisy Channel Spelling
  Correction*. ACL 2000. https://doi.org/10.3115/1075218.1075255 — Modelo de error de cadena a
  cadena (relevante para dígrafos del español: ll/y, qu/k, cc/c).
- Golding, A. R., Roth, D. (1999). *A Winnow-Based Approach to Context-Sensitive Spelling
  Correction*. Machine Learning, 34. https://doi.org/10.1023/A:1007545901558
- Islam, A., Inkpen, D. (2012). *Context-sensitive Spelling Correction Using Google Web 1T
  5-Gram Information*. https://arxiv.org/abs/1204.5852. — Corrección por n-gramas.
- (2023). *Real-Word Error Correction with Trigrams*. https://arxiv.org/abs/2302.04096.
- Fivez, P., Šuster, S., Daelemans, W. (2017). *Unsupervised Context-Sensitive Spelling
  Correction of English and Dutch Clinical Free-Text with Word and Character N-Gram
  Embeddings*. CLIN Journal, 7. https://arxiv.org/abs/1710.07045. Código: github.com/clips/clinspell. —
  Ranking de candidatos por similitud coseno con el contexto usando embeddings de
  n-gramas de caracteres; parámetros afinados con corpus de errores autoinducidos, sin
  anotación humana. Diseñado para texto clínico telegráfico.
- Lee, J., Kim, ... (2021). *Similarity-Based Unsupervised Spelling Correction Using
  BioWordVec*. JMIR Medical Informatics, 9(2), e25530.
  https://medinform.jmir.org/2021/2/e25530 — Token que no mapea a la
  terminología = candidato a error; candidatos por embeddings de n-gramas de caracteres
  + distancia de edición; F1 97,48 % sobre 27.544 informes.
- Singh, A. (2026). *Spelling Correction in Healthcare Query-Answer Systems: Methods,
  Retrieval Impact, and Empirical Evaluation*. https://arxiv.org/abs/2603.19249. — Comparación
  cuantitativa: SymSpell produce 1,5 % de cambios innecesarios frente a 8,9–16 % de
  Levenshtein; recomienda distancia 1 y frecuencia mínima del candidato ≥ 5 en salud; el
  ranking con contexto no aportó sobre vocabulario pequeño; el diccionario se construye
  del propio corpus (≥ 2 ocurrencias).
- Bravo-Candel, D., et al. (2021). *Automatic Correction of Real-Word Errors in Spanish
  Clinical Texts*. Sensors, 21(9), 2893. https://doi.org/10.3390/s21092893 — Referencia en español
  clínico para errores de palabra real: los homófonos (b/v, ll/y, h) son la categoría que
  mejor se corrige; la concordancia gramatical, la peor. Parámetros: ventana 5, frecuencia
  mínima 10. Los embeddings preentrenados no mejoraron el resultado.
- López Hernández, R., Almela, Á. (2021). *Detección automática de errores lingüísticos en
  textos clínicos*. Panace@, 22(53). Versión revisada: *Analysis of Context-Dependent
  Errors in the Medical Domain in Spanish*. SAGE Open. https://doi.org/10.1177/21582440221148454 —
  Corpus de > 2 M de palabras de cuatro especialidades; urgencias es la especialidad con
  más errores dependientes del contexto y el error más frecuente es la omisión de tilde.
- Juan, ..., Kim, ... (2022). *Context-Sensitive Misspelling Correction of Clinical Text
  via Conditional Independence*. CHIL 2022. Código: github.com/dalgu90/cim-misspelling.
  — Entrenable sin pares anotados; requiere GPU. Plan B.
- Yarowsky, D. (1994). *Decision Lists for Lexical Ambiguity Resolution: Application to
  Accent Restoration in Spanish and French*. ACL 1994. https://arxiv.org/abs/cmp-lg/9406034 — La restitución
  de tildes es desambiguación léxica, no ortografía.
- (2021). *Diacritics Restoration using BERT*. https://arxiv.org/abs/2105.11408. (2022). *Dilated CNN for
  Lightweight Diacritics Restoration*. https://arxiv.org/abs/2201.06757.
- (2016). *Comparative Analysis of Phonetic Algorithms Applied to Spanish*. Universidad
  Autónoma de Guadalajara / UWP. — Soundex no sirve para español; clases de equivalencia
  fonéticas (b/v, s/z/c, y/ll, h, qu/k/c, g/j).
- *Phonetic Matching Toolkit with Meta-Soundex (English and Spanish)*. Sam Houston State
  University. — Meta-Soundex reduce falsos positivos frente a Soundex y Metaphone.
- Salazar, J., et al. (2020). *Masked Language Model Scoring*. ACL 2020.
  https://aclanthology.org/2020.acl-main.240/ — Pseudo-log-verosimilitud para puntuar candidatos
  de varios subtokens con un modelo enmascarado.
- (2022). *BEDSpell: Spelling Error Correction Using BERT-Based MLM and Edit Distance*.
  ICSOC 2022 Workshops. https://doi.org/10.1007/978-3-031-26507-5_1
- Pal, A., Mustafi, A. (2020). *Vartani Spellcheck*. https://arxiv.org/abs/2012.07652.
- Hu, Y., et al. (2021). *Misspelling Correction with Pre-trained Contextual Language
  Model*. https://arxiv.org/abs/2101.03204.
- (2024). *Contextual Spelling Correction with Language Model for Low-resource Setting*.
  https://arxiv.org/abs/2404.18072.
- (2024). *PERCORE: Persian Spelling Correction with Phonetic Analysis*. https://arxiv.org/abs/2407.14789.
  (2022). *DPCSpell*. https://arxiv.org/abs/2211.03730. — Métricas de evaluación de correctores.

### 1.2 Detección de correcciones dañinas y evaluación

- Bryant, C., Felice, M., Briscoe, T. (2017). *Automatic Annotation and Evaluation of
  Error Types for Grammatical Error Correction (ERRANT)*. ACL 2017. Código:
  github.com/chrisjbryant/errant. — Alineamiento token a token entre original y
  corregido; la unidad de análisis es la edición, no la nota. (2025). *Multilingual
  Grammatical Error Annotation*. https://arxiv.org/abs/2506.07719.
- WMT21 Quality Estimation Task, subtarea *Critical Error Detection*.
  statmt.org/wmt21/quality-estimation-task.html. — Taxonomía minor/major/critical.
  (2024). *Towards Precise Localization of Critical Errors in Machine Translation*. ACL
  Findings 2024. Rei, R., et al. (2022). *CometKiwi*. https://arxiv.org/abs/2209.06243. Amrhein, C., et
  al. (2022). *ACES: Translation Accuracy Challenge Sets*. https://arxiv.org/abs/2210.15615. — Se adopta
  la taxonomía, no los modelos (XLM-R large, sin GPU).
- (2025). *Semantic Drift and Reporting Stability in VAERS*. medRxiv.
  https://doi.org/10.1101/2025.11.10.25339934 — Deriva semántica por embeddings; no aplicable a notas
  de 6 palabras.
- (2026). *Illusions of the Gold Standard: Human Evaluation Protocols*. https://arxiv.org/abs/2606.07936.
  — Doble anotación en muestra de calibración (κ de Cohen).
- (2021). *TF-IDF vs Word Embeddings for Morbidity Identification in Clinical Notes*.
  https://arxiv.org/abs/2105.09632. — TF-IDF sobre n-gramas de caracteres como línea base fuerte.
- (2020). *Discrete Word Embedding for Logical Natural Language Understanding*.
  https://arxiv.org/abs/2008.11649. — Efecto de la repetición de conceptos sobre embeddings promediados
  (fundamento de la decisión sobre glosas).

### 1.3 Modelos de lenguaje clínicos en español

- (2023). *A Survey of Spanish Clinical Language Models*. https://arxiv.org/abs/2308.02199.
- García Subies, G., Barbero Jiménez, Á., Martínez Fernández, P. (2024). *A comparative
  analysis of Spanish clinical encoder-based models on NER and classification tasks*.
  JAMIA. https://doi.org/10.1093/jamia/ocae054 — > 3.000 modelos sobre 17 corpus: los modelos de
  propósito general no siempre pierden frente a los clínicos; medir, no asumir.
- Mayhew, S., et al. (2019). *NER and POS when nothing is capitalized*. EMNLP 2019.
  https://aclanthology.org/D19-1650/ Mayhew, S., et al. (2019). *Robust Named Entity
  Recognition with Truecasing Pretraining*. https://arxiv.org/abs/1912.07095. — Los modelos con
  mayúsculas informativas degradan sobre texto en mayúsculas; truecasear o minusculizar.
- Verma, ..., Bagherzadeh, ..., Bergler, S. (2022). *CLaCLab at SocialDisNER*.
  https://arxiv.org/abs/2209.03528. — F1 0,869 en tweets en español inyectando gazetteers como
  características explícitas.
- Sanh, V., et al. (2019). *DistilBERT*. https://arxiv.org/abs/1910.01108. Hugging Face (s. f.).
  *Scaling-up BERT Inference on CPU*. huggingface.co/blog/bert-cpu-scaling-part-1.
  (2026). *Efficient INT8 Inference of Small NLP Models on Server CPUs*.
  https://arxiv.org/abs/2608.18182. — Coste en CPU; la aceleración INT8 depende de AVX-512 VNNI, ausente
  en el equipo del proyecto.

### 1.4 Normalización de entidades y jerga de pacientes

- Gallego, F. J., López-García, G., Gasco, L., Krallinger, M., Veredas, F. J. (2024).
  *ClinLinker: Medical Entity Linking of Clinical Concept Mentions in Spanish*. ICCS
  2024. https://doi.org/10.1007/978-3-031-63775-9_19 https://arxiv.org/abs/2404.06367.
- Gallego, F. J., et al. (2025). *Enhancing cross-encoders using knowledge graph hierarchy
  for medical entity linking in zero- and few-shot scenarios*. Knowledge-Based Systems.
  https://doi.org/10.1016/j.knosys.2025.113141 — Representación de conceptos enriquecida con la
  jerarquía SNOMED; conceptos hermanos quedan cerca en el espacio vectorial.
- Gallego, F. J., Veredas, F. J. (2024). *Recognition and normalization of multilingual
  symptom entities using in-domain-adapted BERT models and classification layers*.
  Database (Oxford). https://doi.org/10.1093/database/baae087 Código: github.com/ICB-UMA/WNT-Softmax.
  — Inicialización con el embedding promedio de los sinónimos de cada concepto;
  trasplantable sin entrenamiento como centroides por concepto.
- Borchert, F., et al. (2024). *xMEN: a modular toolkit for cross-lingual medical entity
  normalization*. JAMIA Open, 8(1), ooae147. https://doi.org/10.1093/jamiaopen/ooae147 Código:
  github.com/hpi-dhc/xmen. — Ensemble TF-IDF de n-gramas de caracteres + SapBERT, k=64.
- (2024). *Entity normalization in a Spanish medical corpus using a UMLS-based lexicon*.
  Language Resources and Evaluation. https://doi.org/10.1007/s10579-024-09755-7
- Ibrahim, M., et al. (2021). Construcción de vocabulario de salud del consumidor a partir
  de embeddings. PeerJ Computer Science.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC8371999/ Jiang, ..., Yang, ... (2019). JMIR
  Medical Informatics. https://pmc.ncbi.nlm.nih.gov/articles/PMC6552449/ — Vecinos más cercanos de cada término técnico en
  embeddings entrenados sobre lenguaje lego; receta para construir el diccionario
  jerga → clínico que no existe para español.
- Lopez Osornio, A., Luna, D., et al. (2007). *Creation of a local interface terminology
  to SNOMED CT*. https://pubmed.ncbi.nlm.nih.gov/17911820/ — *Terminology Services*.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC6115242/ — Terminología de
  interfaz en español (Hospital Italiano de Buenos Aires): corrección ortográfica y
  matching semántico como componentes del mismo servicio.
- SMM4H 2023 Task 3, overview. https://pmc.ncbi.nlm.nih.gov/articles/PMC10659479/ — Síntomas en tweets en español
  latinoamericano.
- Lima, S., et al. (2020). *NUBes: A Corpus of Negation and Uncertainty in Spanish
  Clinical Texts*. LREC 2020. https://aclanthology.org/2020.lrec-1.708/ (2022). *Negation and
  uncertainty detection in Spanish clinical texts*. PeerJ Computer Science. https://doi.org/10.7717/peerj-cs.913
  (2023). NegEx + CNN. BMC Medical Informatics and Decision Making.
  https://doi.org/10.1186/s12911-023-02301-5
- Campillos-Llanos, L. (2022). *MedLexSp – a medical lexicon for Spanish medical natural
  language processing*. Journal of Biomedical Semantics. https://doi.org/10.1186/s13326-022-00281-5
- (2020). Inventario de sentidos de acrónimos por especialidad a partir de PubMed. https://pubmed.ncbi.nlm.nih.gov/32570393/. (2021). *Medical Abbreviation and Acronym Meta-Inventory*. Scientific Data.
  https://doi.org/10.1038/s41597-021-00929-4

### 1.5 Triage, motivos de consulta y agrupamiento

- Chang, D., Hong, W. S., Taylor, R. A. (2020). *Generating contextual embeddings for
  emergency department chief complaints*. JAMIA Open, 3(2), 160–166.
  https://doi.org/10.1093/jamiaopen/ooaa022 Código: github.com/dchang56/chief_complaints. — 1,8 M de
  motivos de consulta; BERT + mezcla gaussiana; 15 clusters por silueta; max_length 64. El
  trabajo más cercano al objetivo del proyecto.
- Cortes, ..., Genaro, ..., Maraboli, ..., Manríquez-Troncoso, ... (2025). *Automated
  Triage Classification in Emergency Services Using Spanish Clinical Notes*. NeurIPS 2025
  (WiML). https://openreview.net/forum?id=OJNHTTWMFA — Notas de triage chilenas; construyeron un
  diccionario de abreviaturas local como paso obligatorio.
- Báez, P., Villena, F., Rojas, M., Durán, M., Dunstan, J. (2020). *The Chilean Waiting
  List Corpus*. Clinical NLP Workshop, EMNLP 2020. https://aclanthology.org/2020.clinicalnlp-1.32/
  — Único corpus clínico público de español latinoamericano con texto breve.
- Nobles, M., Vilk, ..., Chen, ..., et al. (2019). MUSES. OJPHI. https://ojphi.jmir.org/2019/1/e62431 — (2022). *Presyndromic
  surveillance*. Science Advances. https://doi.org/10.1126/sciadv.abm4920 — Topic modeling no
  supervisado sobre motivos de consulta para descubrir síndromes no catalogados.
- Chapman, W. W., Christensen, L. M., Wagner, M. M., et al. (2005). *Classifying free-text
  triage chief complaints into syndromic categories with natural language processing*.
  https://pubmed.ncbi.nlm.nih.gov/15617980/
- (2019). *Extracting information from free text through unsupervised graph-based
  clustering: patient incident records*. https://arxiv.org/abs/1909.00183.
- (2025). *Weakly Supervised Medical Entity Extraction and Linking for Chief Complaints*.
  https://arxiv.org/abs/2509.01899.
- Grootendorst, M. (2022). *BERTopic: Neural topic modeling with a class-based TF-IDF
  procedure*. https://arxiv.org/abs/2203.05794. (2022). https://arxiv.org/abs/2212.08459. BERTopic_Teen, https://pmc.ncbi.nlm.nih.gov/articles/PMC12378273/. —
  c-TF-IDF para nombrar clusters.
- (2026). Evaluación de robustez multilingüe de modelos de embedding. https://arxiv.org/abs/2605.31142.
  (2025). *Towards Domain Specification of Embedding Models in Medicine*.
  https://arxiv.org/abs/2507.19407. *Clustering Clinical Notes in Spanish Based on Contextualized
  Embeddings*. https://doi.org/10.1007/978-3-032-13729-6_17
- Reimers, N., Gurevych, I. (2019). *Sentence-BERT*. https://arxiv.org/abs/1908.10084. (2024).
  *Scandinavian Embedding Benchmarks*. https://arxiv.org/abs/2406.02396.

---

## 2. Recursos de datos y léxicos

| Recurso | Fuente | Licencia | Contenido | Estado | Notas de integración |
|---|---|---|---|---|---|
| CIE-10, 3.ª ed. (PDF) | OPS/OMS | uso interno | vocabulario diagnóstico | en uso (`datos/lexico_externo.txt`) | ya extraído por `recursos/extraer_cie10.py` |
| SympTEMIST gazetteer | BSC, Zenodo doi:10.5281/zenodo.8223653 (registro 10635215) | CC-BY-4.0 | 164.817 alias en español de síntomas, signos y hallazgos SNOMED CT; TSV `code, language, term, semantic_tag, mainterm` | pendiente (prioridad 1) | ZIP de 452 MB; el TSV es pequeño. Diccionario de protección y anclas de clusters |
| DISTEMIST gazetteer | BSC, Zenodo 6458115 | CC-BY-4.0 | ~111 k códigos de enfermedades con sinónimos, 9,1 MB | pendiente (prioridad 1) | mismas columnas |
| MedProcNER gazetteer | BSC, Zenodo 7929830 | CC-BY-4.0 | procedimientos; mapeos a MeSH | pendiente (media) | |
| MedLexSp | github.com/lcampillos/MedLexSp | gratuito para investigación/educación previa firma; excluye términos con copyright (SNOMED, MedDRA) | 100.887 lemas, 302.543 formas flexionadas, CUIs UMLS; lematizador para spaCy | pendiente (requiere trámite humano) | único recurso español con formas flexionadas |
| MeSpEn_Glossaries | github.com/PlanTL-GOB-ES/MeSpEn_Glossaries, doi:10.5281/zenodo.2205690 | CC-BY-4.0 (SEAD 2018) | 46 glosarios bilingües; par inglés-español 125.645 entradas; TSV de 2 columnas | pendiente (baja: tercera capa) | terminología de traductor, no de nota de triage |
| AbreMES-DB | github.com/PlanTL-GOB-ES/AbreMES-DB, doi:10.5281/zenodo.2207130 | CC-BY-4.0 | abreviaturas y definiciones minadas de SciELO/IBECS/PubMed; 6 TSV | evaluar | el valor está en la técnica (minar `SIGLA (definición)` sobre las 94 k notas propias) |
| BARR2 / SPACCC | temu.bsc.es/BARR2 | consultar | 1.000 casos clínicos con pares abreviatura-definición anotados | evaluar (gold para el expansor) | |
| CUM – Código Único de Medicamentos (INVIMA) | datos.gov.co, dataset `i7cb-raxc` | Ley 1712 de 2014 (dato abierto) | 157.756 filas; usar campo `descripcionatc` (1.450 valores limpios); `producto` para nombres comerciales | pendiente (alta) `[descarga verificada]` | NO usar `principioactivo` (dosis embebidas) |
| Nomenclátor AEMPS (CIMA) | listadomedicamentos.aemps.gob.es/prescripcion.zip | aviso legal no verificado automáticamente | `DICCIONARIO_PRINCIPIOS_ACTIVOS.xml` → 2.718 tokens únicos | pendiente (complemento) `[descarga verificada]` | devuelve 403 sin User-Agent de navegador; ignorar `Prescripcion.xml` (193 MB) |
| DIVIPOLA municipios | geoportal.dane.gov.co/descargas/divipola/DIVIPOLA_Municipios.xlsx | Ley 1712 | 1.122 municipios | pendiente (alta) `[descarga verificada]` | |
| DIVIPOLA centros poblados | mismo origen, `DIVIPOLA_CentrosPoblados.xlsx` | Ley 1712 | 1 MB | pendiente (media) | |
| GeoNames Colombia | download.geonames.org/export/dump/CO.zip | CC-BY-4.0 | 82.093 registros | evaluar (media) `[descarga verificada]` | usar solo la columna 2 (nombre); `alternatenames` contiene palabras comunes; UTF-8 |
| REPS – Registro de Prestadores | datos.gov.co, dataset `c36g-9fc2` | Ley 1712 | 76.821 filas: 19.551 IPS; 54.657 profesionales (nombres de persona colombianos) | pendiente (alta) `[consulta verificada]` | filtro `claseprestador like 'Instituciones%'` |
| INE nombres y apellidos | ine.es/daco/daco42/nombyapel/ | INE (reutilización permitida) | XLS | pendiente (media) | complemento barato |
| EPS activas | sin dataset limpio (ADRES/MinSalud publican PDF) | — | ~30 entidades | pendiente: transcribir a mano | |
| Siglas administrativas y clínicas | elaboración propia | — | ~40 entradas (EPS, IPS, ARL, SOAT, DX, RX, TAC, EKG, HTA, DM, EPOC…) | pendiente (alta, coste nulo) | lista de protección, no diccionario de frecuencias |
| NegEx-MES | Zenodo 2542567 | MIT | disparadores de negación en español para NegEx | pendiente (alta si se usa medspaCy) | las reglas por defecto de medspaCy son inglesas |
| NUBes | ver 1.4 | consultar | 29.682 frases anotadas con negación e incertidumbre | evaluar | |
| CoWeSe | Zenodo 5510033 | CC-BY-4.0 | 750 M tokens de texto biomédico español | evaluar (media) | pesado; útil para frecuencias de dominio |
| FastText Spanish Medical Embeddings | Zenodo 2542721 | CC-BY-4.0 | 41,1 GB | descartado por tamaño | entrenar fastText propio sobre las 94 k notas |
| Chilean Waiting List Corpus | Zenodo (ver 1.5) | consultar | 9.000 derivaciones, 900 anotadas | evaluar (validación LatAm) | |
| CIAP-2 / ICPC-2 | agapap.org/datos/CIAP2.pdf; UMLS `ICPCSPA` | consultar | ~700 rúbricas de motivo de consulta | evaluar (taxonomía de referencia para clusters) | |
| SNOMED CT edición española | licencia de afiliado (Centro Nacional de Referencia) | licencia | — | descartado a corto plazo | los gazetteers del BSC cubren la necesidad sin trámite |
| UMLS Metathesaurus | uts.nlm.nih.gov | licencia UTS (categorías por fuente) | subconjunto español ~451 k conceptos | evaluar (solo si se reentrena) | |
| CIE-10 Colombia (SISPRO) | web.sispro.gov.co | público | tabla de referencia | en uso parcial | Colombia en transición a CIE-11 (Res. 1442/2024) |
| RANM – Diccionario de Términos Médicos | dtme.ranm.es | copyright, sin descarga | 52.000 términos | descartado programáticamente | su contenido está en MedLexSp |
| DeCS/MeSH español | decs.bvsalud.org | registro | indexación bibliográfica | descartado para triage | |
| Lista de palabras es_ES (gist victorhck) | gist.github.com/victorhck/9ed2f9b95e675e9e71be142816791afd | verificar | lista de palabras del español | evaluar (baja) | LanguageTool + SymSpell ya cubren; aporte marginal |
| Frecuencias generales del español | hermitdave/FrequencyWords | CC-BY-SA-3.0 | | evaluar | atención: SA (copyleft) |
| Cosnautas – Diccionario de siglas médicas | cosnautas.com | suscripción | | descartado | no integrable |
| ATC/DDD (OMS), RxNorm, DrugBank | — | pago / licencia | | descartado | el CUM da la descripción ATC en español gratis |

---

## 3. Modelos

| Modelo | Base | Licencia | Uso previsto | Estado | Notas |
|---|---|---|---|---|---|
| `es_core_news_md` (spaCy 3.7) | — | MIT | vocabulario y entidades en fase 2 | en uso | instalado 2026-09-15; su ausencia dejaba la fase 2 sin protección |
| `PlanTL-GOB-ES/roberta-base-biomedical-clinical-es` | RoBERTa | Apache-2.0 | modelo de contexto (fase 2) y características del clasificador de frases | en uso | |
| `BAAI/bge-m3` | XLM-R large | MIT | embeddings (paquete `embedding/`) | en uso | comparar; ver 1.5 |
| `qwen2.5:3b-instruct` (Ollama) | Qwen2.5 | Apache-2.0 | extractor de motivo (fase 5), solo copia literal verificada | en uso, restringir | 5,5 tok/s en CPU; un prompt de reescritura corrompe contenido clínico (medido) |
| `PlanTL-GOB-ES/bsc-bio-ehr-es` | RoBERTa, 1,1 B tokens clínicos | Apache-2.0 | verificador enmascarado de pares en zona gris | evaluar | minusculizar antes; PLL para varios subtokens |
| `BSC-NLP4BIA/bsc-bio-ehr-es-carmen-symptemist` | bsc-bio-ehr-es | CC-BY-4.0 | NER de síntomas en notas largas | evaluar | pre-tokenizar en palabras; F1 0,753 sobre EHR reales |
| `lcampillos/roberta-es-clinical-trials-ner` | bsc-bio-ehr-es | consultar | NER ANAT/CHEM/DISO/PROC; F1 0,865 | evaluar | registro formal (ensayos clínicos) |
| `medspaner/roberta-es-clinical-trials-neg-spec-ner`, `-temporal-ner` | bsc-bio-ehr-es | AGPL-3.0 (medspaner) | negación, especulación, temporalidad | evaluar | AGPL contagia si se distribuye |
| `ICB-UMA/ClinLinker-KB-GP` | roberta-base-biomedical-clinical-es | consultar | enlace de menciones a conceptos (zero-shot) | evaluar (prioridad) | top-25 0,871 DisTEMIST |
| `BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es` | RoBERTa | Apache-2.0 | embedding de menciones cortas (usar [CLS], max_length 25) | evaluar (prioridad) | |
| `intfloat/multilingual-e5-small` | — | MIT | alternativa ligera de embedding | evaluar | requiere prefijos `query:`/`passage:` |
| `IIC/RigoBERTa-Clinical` / RigoBERTa 2 | — | consultar | comparación | evaluar | mejor F1 medio en JAMIA 2024 |
| `HUMADEX/spanish_medical_ner` | **`bert-base-cased` (inglés)**, vocabulario 28.996 | Apache-2.0 | — | **descartado** | tokenizador inglés sobre español; entrenado con traducciones automáticas; F1 0,776 sobre su propio test |
| `ixa-ehu/ixambert-base-cased` | multilingüe Wikipedia | — | — | descartado | no clínico |

---

## 4. Software y bibliotecas

En uso (ver `requirements.txt`): spaCy, medspacy, language-tool-python (Java 21 +
LanguageTool 6.8), symspellpy, rapidfuzz, flashtext, sentence-transformers, torch (+cpu),
transformers, scikit-learn, statsmodels, kmodes, pandas, pyarrow, SQLAlchemy, pyodbc.

Candidatos (pendiente de evaluación y de la política de seguridad de `PLAN.md`):

| Paquete | Uso | Licencia | Nota |
|---|---|---|---|
| `fasttext` (o `gensim` FastText) | embeddings de n-gramas de caracteres sobre las 94 k notas | MIT / LGPL | receta clinspell y Lee 2021 |
| `kenlm` | modelo de n-gramas de dominio | LGPL | binarios en Windows requieren compilación; alternativa: conteos propios |
| `optimum[onnxruntime]` | exportar y cuantizar modelos para CPU (modo `avx2`) | Apache-2.0 | el equipo no tiene AVX-512 VNNI |
| `xmen` | normalización de entidades (TF-IDF char + SapBERT) | consultar | |
| `bertopic`, `umap-learn`, `hdbscan` | agrupamiento y nombres de clusters | BSD / BSD / BSD | paquete `clustering/` |
| `pytest` | pruebas de regresión | MIT | |
| `pyflakes` | análisis estático | MIT | instalado 2026-09-15 |
| SymSpell (referencia: github.com/wolfgarbe/SymSpell; comparación seekstorm.com/blog/symspell-vs-bk-tree) | ya en uso vía symspellpy | MIT | |

---

## 5. Obligaciones y riesgos de licencia

- **CC-BY-4.0** (gazetteers del BSC, MeSpEn, AbreMES, GeoNames, CoWeSe): uso libre con
  atribución. Este documento y `RECURSOS.md` (cuando exista) constituyen la atribución.
  Si se publica un derivado, citar el recurso y la licencia.
- **CC-BY-SA-3.0** (hermitdave/FrequencyWords): copyleft; un léxico derivado debería
  compartirse bajo la misma licencia. Preferir fuentes CC-BY o propias.
- **AGPL-3.0** (medspaner y sus modelos): si se incorpora y se distribuye el software,
  contagia la licencia. Solo uso interno o evaluación.
- **MedLexSp**: uso de investigación/educación previa firma; la versión libre excluye
  términos con copyright. Uso comercial o publicación de derivados requiere acuerdo con el
  autor.
- **Datos abiertos colombianos** (Ley 1712 de 2014): uso, redistribución y modificación
  libres.
- **AEMPS**: aviso legal no verificado automáticamente; leer `Aviso_Legal_Nomenclator.pdf`
  antes de publicar un derivado.
- **Modelos Hugging Face**: verificar la licencia en la tarjeta de cada modelo antes de
  ponerlo en producción; preferir pesos en formato `safetensors`; no usar
  `trust_remote_code=True`.
- **Datos de pacientes**: las notas de triage son datos personales sensibles. Ninguna
  nota, ni fragmento, ni ejemplo del CSV debe salir del entorno de la institución
  (incluidos prompts a servicios externos y este repositorio si se hace público). Los
  ejemplos que aparecen en la documentación deben anonimizarse o sustituirse por casos
  sintéticos antes de cualquier publicación.


## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-15 | previo al plan | Primera versión: 60 citas, 30 recursos, 14 modelos, software, licencias |
| 2026-09-15 | revisión v2 | Enlaces añadidos a todas las citas con identificador; sección Historial |
