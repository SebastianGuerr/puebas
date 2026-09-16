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
| SympTEMIST gazetteer | BSC, Zenodo doi:10.5281/zenodo.8223653 (registro 10635215) | CC-BY-4.0 | 164.817 alias en español de síntomas, signos y hallazgos SNOMED CT; TSV `code, language, term, semantic_tag, mainterm` | pendiente: zenodo.org devolvió HTTP 504 en 8 intentos el 2026-09-16 (E3.4) | ZIP de 452 MB; el TSV es pequeño. Diccionario de protección y anclas de clusters |
| DISTEMIST gazetteer | BSC, Zenodo 6458115 | CC-BY-4.0 | ~111 k códigos de enfermedades con sinónimos, 9,1 MB | **en uso** (E3.4, `recursos/lexico.py` fuente `GAZETTEER`, `datos/lexicos/gazetteer_distemist.txt`, 27.255 formas) | mismas columnas; ver bitácora/2026-09-16-E3.4.md |
| MedProcNER gazetteer | BSC, Zenodo 7929830 | CC-BY-4.0 | procedimientos; mapeos a MeSH | pendiente: zenodo.org devolvió HTTP 504 en 8 intentos el 2026-09-16 (E3.4) | |
| MedLexSp | github.com/lcampillos/MedLexSp | gratuito para investigación/educación previa firma; excluye términos con copyright (SNOMED, MedDRA) | 100.887 lemas, 302.543 formas flexionadas, CUIs UMLS; lematizador para spaCy | pendiente (requiere trámite humano) | único recurso español con formas flexionadas |
| MeSpEn_Glossaries | Zenodo doi:10.5281/zenodo.2205690 (el repositorio de GitHub solo tiene LICENSE y README; el dato vive en Zenodo, comprobado 2026-09-16) | CC-BY-4.0 (SEAD 2018) | 46 glosarios bilingües; par inglés-español 125.645 entradas; TSV de 2 columnas | pendiente: URL del manifiesto corregida a Zenodo el 2026-09-16 (E3.10); zenodo.org devolvió HTTP 504 el mismo día | terminología de traductor, no de nota de triage; no se integró (sin poder descargar no hay medición que la respalde) |
| AbreMES-DB | github.com/PlanTL-GOB-ES/AbreMES-DB, doi:10.5281/zenodo.2207130 | CC-BY-4.0 | abreviaturas y definiciones minadas de SciELO/IBECS/PubMed; 6 TSV | evaluar | el valor está en la técnica (minar `SIGLA (definición)` sobre las 94 k notas propias) |
| BARR2 / SPACCC | temu.bsc.es/BARR2 | consultar | 1.000 casos clínicos con pares abreviatura-definición anotados | evaluar (gold para el expansor) | |
| CUM – Código Único de Medicamentos (INVIMA) | datos.gov.co, dataset `i7cb-raxc` | Ley 1712 de 2014 (dato abierto) | 157.756 filas; usar campo `descripcionatc` (1.450 valores limpios); `producto` para nombres comerciales | **en uso** (E3.5, `datos/lexicos/farmacos.txt`) | NO usar `principioactivo` (dosis embebidas); `descripcionatc` usa INN español ('dutasterida'), no siempre coincide con la forma inglesa ('dutasteride') |
| Nomenclátor AEMPS (CIMA) | listadomedicamentos.aemps.gob.es/prescripcion.zip | aviso legal no verificado automáticamente | `DICCIONARIO_PRINCIPIOS_ACTIVOS.xml` → 2.718 tokens únicos | **en uso** (E3.5, mezclado en `datos/lexicos/farmacos.txt`) | devuelve 403 sin User-Agent de navegador; ignorar `Prescripcion.xml` (193 MB); leer `Aviso_Legal_Nomenclator.pdf` antes de publicar un derivado |
| DIVIPOLA municipios | geoportal.dane.gov.co/descargas/divipola/DIVIPOLA_Municipios.xlsx | Ley 1712 | 1.122 municipios | **en uso** (E3.6, `datos/lexicos/lugares.txt`) | |
| DIVIPOLA centros poblados | mismo origen, `DIVIPOLA_CentrosPoblados.xlsx` | Ley 1712 | 1 MB | pendiente (media); descargado por una sesión anterior pero no usado en E3.6 | |
| GeoNames Colombia | download.geonames.org/export/dump/CO.zip | CC-BY-4.0 | 82.093 registros | rechazado: dominio fuera de `ALLOWED_DOMINIOS` (PLAN.md §6.1) | usar solo la columna 2 (nombre); `alternatenames` contiene palabras comunes; UTF-8 |
| REPS – Registro de Prestadores | datos.gov.co, dataset `c36g-9fc2` | Ley 1712 | 76.821 filas: 19.551 IPS; 54.657 profesionales (nombres de persona colombianos) | **en uso parcial** (E3.6, solo profesionales independientes → `datos/lexicos/nombres.txt`; las IPS no se integraron) | filtro `claseprestador` = 'Profesional Independiente' para personas, 'Instituciones...' para IPS |
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
| `es_core_news_md` (spaCy 3.7.0) | AnCora v2.8 + WikiNER | **GPL-3.0** | vocabulario y entidades en fase 2 | en uso, con obligación | instalado 2026-09-15. La licencia del **modelo** es GPL-3.0 (la del paquete `spacy` es MIT); verificado el 2026-09-16 en `meta.json` del paquete instalado: `"license": "GNU GPL 3.0"`, heredada de AnCora. Ver §5 |
| `PlanTL-GOB-ES/roberta-base-biomedical-clinical-es` | RoBERTa | Apache-2.0 | modelo de contexto (fase 2) y características del clasificador de frases | en uso | |
| `BAAI/bge-m3` | XLM-R large | MIT | embeddings (paquete `embedding/`) | en uso | comparar; ver 1.5 |
| `qwen2.5:3b-instruct` (Ollama) | Qwen2.5 | **Qwen Research License** (no comercial) | extractor de motivo (fase 5), solo copia literal verificada | en uso, **decisión pendiente** | 5,5 tok/s en CPU; un prompt de reescritura corrompe contenido clínico (medido). NO es Apache-2.0: verificado el 2026-09-16 con `ollama show qwen2.5:3b-instruct --license` → «Qwen RESEARCH LICENSE AGREEMENT», uso no comercial. Ver §5 |
| `PlanTL-GOB-ES/bsc-bio-ehr-es` | RoBERTa; corpus biomédico+clínico > 1 B tokens, del que la parte clínica real (EHR) son ~91–95 M tokens en 278 K documentos | Apache-2.0 | verificador enmascarado de pares en zona gris | evaluar | minusculizar antes; PLL para varios subtokens. Corregido el 2026-09-16: «1,1 B tokens clínicos» era el total del corpus, no el clínico |
| `BSC-NLP4BIA/bsc-bio-ehr-es-carmen-symptemist` | bsc-bio-ehr-es | CC-BY-4.0 | NER de síntomas en notas largas | evaluar | pre-tokenizar en palabras; F1 0,753 sobre EHR reales |
| `lcampillos/roberta-es-clinical-trials-ner` | bsc-bio-ehr-es | **CC-BY-NC-4.0** | NER ANAT/CHEM/DISO/PROC; F1 0,8647 (P 0,8495 / R 0,8806) | evaluar, **no comercial** | registro formal (ensayos clínicos). Licencia verificada en la tarjeta el 2026-09-16 |
| `medspaner/roberta-es-clinical-trials-neg-spec-ner`, `-temporal-ner` | bsc-bio-ehr-es | **CC-BY-NC-4.0** (los pesos) | negación, especulación, temporalidad | evaluar, **no comercial** | Corregido el 2026-09-16: la AGPL-3.0 es la del **código** del repositorio `lcampillos/medspaner`, no la de los pesos, que son CC-BY-NC-4.0 en ambas tarjetas. F1 0,859 (neg-spec) y 0,900 (temporal) |
| `ICB-UMA/ClinLinker-KB-GP` | roberta-base-biomedical-clinical-es | Apache-2.0 | enlace de menciones a conceptos (zero-shot) | evaluar (prioridad) | top-25 según la tarjeta: DisTEMIST **0,864**, MedProcNER 0,901, SympTEMIST 0,922 (el 0,871 anterior no figura en la tarjeta). Pooling CLS. Sin `safetensors`: solo `pytorch_model.bin` |
| `BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es` | RoBERTa | Apache-2.0 | embedding de menciones cortas (usar [CLS], max_length 25) | evaluar (prioridad) | UMLS 2023AA. Sin `safetensors`: solo `pytorch_model.bin` (pickle) → §6.4 del plan exige dejar constancia al cargarlo |
| `intfloat/multilingual-e5-small` | — | MIT | alternativa ligera de embedding | evaluar | requiere prefijos `query:`/`passage:` |
| `IIC/RigoBERTa-Clinical` / `IIC/RigoBERTa-2.0` | XLM-R large | **licencia propia no comercial** (`rigoclinical-nc` / `rigoberta-nc`) | comparación | evaluar, **no comercial** | mejor F1 medio en JAMIA 2024. El identificador `IIC/RigoBERTa-2` no existe; el correcto es `IIC/RigoBERTa-2.0`. La licencia prohíbe uso en producción y ofrecerlo a terceros por API |
| `HUMADEX/spanish_medical_ner` | **`bert-base-cased` (inglés)**, vocabulario 28.996 | Apache-2.0 | — | **descartado** | tokenizador inglés sobre español; entrenado con traducciones automáticas; F1 0,776 sobre su propio test |
| `ixa-ehu/ixambert-base-cased` | multilingüe Wikipedia | — | — | descartado | no clínico |

---

## 4. Software y bibliotecas

En uso (ver `requirements.txt`): spaCy (MIT; **el modelo `es_core_news_md` es GPL-3.0**,
ver §3 y §5), medspacy (MIT), **`language-tool-python` (GPL-3.0-only)** con LanguageTool
6.8 (núcleo LGPL-2.1+; requiere **Java 17**, soportado hasta Java 21), symspellpy (MIT),
rapidfuzz (MIT), flashtext (MIT; última versión de 2018), sentence-transformers, torch
(+cpu), transformers, scikit-learn, statsmodels, kmodes, pandas, pyarrow, SQLAlchemy,
pyodbc.

Candidatos (pendiente de evaluación y de la política de seguridad de `PLAN.md`):

| Paquete | Uso | Licencia | Nota |
|---|---|---|---|
| `fasttext` (o `gensim` FastText) | embeddings de n-gramas de caracteres sobre las 94 k notas | MIT / LGPL-2.1 | receta clinspell y Lee 2021. **El repositorio `facebookresearch/fastText` está archivado desde 2024-03-19** y PyPI no publica rueda para Windows: preferir `gensim` |
| `kenlm` | modelo de n-gramas de dominio | LGPL-2.1 (PyPI no declara licencia) | PyPI publica **solo el código fuente**, sin ruedas para ninguna plataforma; el README oficial no soporta Windows nativo. Alternativa recomendada: conteos propios |
| `optimum[onnxruntime]` | exportar y cuantizar modelos para CPU (modo `avx2`) | Apache-2.0 | el equipo no tiene AVX-512 VNNI |
| `xmen` | normalización de entidades (TF-IDF char + SapBERT) | Apache-2.0 | v1.0.8 (hpi-dhc) |
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
- **GPL-3.0** (modelo `es_core_news_md` de spaCy, **hoy en uso**): el modelo se distribuye
  bajo GPL-3.0 por su corpus AnCora. Usarlo dentro del proceso no obliga a nada mientras no
  se distribuya el producto; distribuir un derivado que lo incluya sí. Verificado el
  2026-09-16 en el `meta.json` del paquete instalado.
- **Qwen Research License** (`qwen2.5:3b-instruct`, **hoy disponible para la fase 5**): uso
  exclusivamente no comercial; el uso comercial exige licencia de Alibaba. Verificado el
  2026-09-16 con `ollama show --license`. Requiere decisión del propietario (§6.9 del plan)
  antes de que la fase 5 lo use en producción.
- **CC-BY-NC-4.0** (modelos de `medspaner` y `lcampillos`, `IIC/RigoBERTa-*` con licencia
  propia no comercial): evaluación e investigación sí; producción no, sin acuerdo con el
  autor. La AGPL-3.0 de `medspaner` corresponde al **código** del repositorio, no a los
  pesos.
- **GPL-3.0-only** (`language-tool-python`, **hoy en uso**): es la envoltura de Python; el
  núcleo de LanguageTool es LGPL-2.1+. Mismo criterio que arriba: afecta a la
  distribución, no al uso interno.
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
| 2026-09-16 | E3.1 (verificación) | §3, §4 y §5 corregidos tras verificar las fuentes una a una: `es_core_news_md` es GPL-3.0 (no MIT) y `qwen2.5:3b` es Qwen Research License no comercial (no Apache-2.0), ambos comprobados en el artefacto instalado; `medspaner` y `lcampillos` son CC-BY-NC-4.0 (la AGPL es del código); `ClinLinker-KB-GP` es Apache-2.0 y su top-25 DisTEMIST es 0,864; corpus EHR de `bsc-bio-ehr-es` ~91–95 M tokens; `language-tool-python` es GPL-3.0-only; `fasttext` archivado y `kenlm` sin ruedas. Ver `decisiones/2026-09-16-licencias-modelos-en-uso.md` |
| 2026-09-16 | E3.4/E3.5/E3.6/E3.10 | DISTEMIST gazetteer integrado (CC-BY-4.0, en uso); SympTEMIST y MedProcNER siguen pendientes (zenodo.org con HTTP 504 persistente el 2026-09-16, 8 intentos); CUM, AEMPS y DIVIPOLA municipios en uso (E3.5/E3.6); REPS en uso parcial (solo profesionales independientes); GeoNames confirmado rechazado por política de dominio; MeSpEn_Glossaries con la URL del manifiesto corregida a Zenodo (el repositorio de GitHub no trae los datos) pero sin poder verificarse hoy por la misma caída de Zenodo, no integrado. Ver bitácora/2026-09-16-E3.4.md, E3.5.md, E3.6.md, E3.10.md |
