# Skills instaladas en este repositorio

Cada carpeta con un `SKILL.md` es una habilidad que Claude Code carga sola cuando la
tarea encaja con su `description`. No hay que invocarlas a mano ni instalar nada más:
los scripts que traen solo usan `requests`, `pandas`, `numpy`, `matplotlib`, `seaborn`
y `scipy`, todas ya presentes en `.venv`.

Instaladas el 2026-09-17.

## Método de trabajo — origen: [obra/superpowers](https://github.com/obra/superpowers) (MIT)

| Skill | Para qué |
|---|---|
| `verification-before-completion` | Prohíbe decir «funciona» o «está cerrado» sin haber corrido el comando de verificación en ese mismo mensaje. Es la regla que habría evitado el reporte engañoso de 0,861 → 0,9516 descrito en `NLP/docs/HANDOFF.md` §1 |
| `systematic-debugging` | Prohíbe proponer arreglos antes de encontrar la causa raíz. Incluye `root-cause-tracing`, `condition-based-waiting` y `defense-in-depth` |
| `brainstorming` | Convierte una idea en diseño antes de tocar código, con una compuerta de aprobación explícita del propietario |
| `writing-plans` | Planes por ítems pequeños, cada uno con qué archivos toca y cómo se prueba |

## Análisis de datos — origen: [DenDen047/claude-scientific-skills](https://github.com/DenDen047/claude-scientific-skills) (MIT, autor K-Dense Inc.)

| Skill | Para qué |
|---|---|
| `statistical-analysis` | Elegir la prueba correcta, comprobar sus supuestos, calcular potencia y reportar en formato APA. Cubre el terreno de `patrones/` (Poisson condicional, corrección Benjamini-Hochberg) |
| `scientific-critical-thinking` | Calidad de la evidencia: sesgos, confusores, diseño experimental, falacias y *trampas estadísticas*. Es la contraparte teórica de la regla «mismas notas, mismos artefactos, solo cambia el código» |

## Investigación — mismo origen (MIT)

| Skill | Para qué |
|---|---|
| `paper-lookup` | Busca en 10 bases por API REST: PubMed, PMC, arXiv, bioRxiv, medRxiv, OpenAlex, Crossref, Semantic Scholar, CORE, Unpaywall. Por DOI, PMID, autor o tema; devuelve metadatos, resumen y si hay acceso abierto |
| `literature-review` | Revisión sistemática: estrategia de búsqueda, síntesis, verificación de cada cita y salida en Markdown o PDF, con estilo APA, Nature o Vancouver |
| `citation-management` | DOI → BibTeX, validación de referencias y detección de metadatos inventados |

## Disponibilidad de las fuentes, medida el 2026-09-17 desde esta máquina

| Fuente | Estado |
|---|---|
| OpenAlex, Crossref, PubMed (E-utilities), Europe PMC, arXiv, bioRxiv/medRxiv, DataCite, Unpaywall | responden 200 |
| Semantic Scholar | 429 sin clave de API: sirve, pero con límite de velocidad |
| CORE | exige clave de API gratuita |
| Google Scholar | **no responde** (bloqueado en esta red). `citation-management/scripts/search_google_scholar.py` no funcionará aquí; usar la vía de PubMed y DOI del mismo skill |

Prueba real de cierre: búsqueda en OpenAlex de *spanish clinical text triage chief
complaint* desde 2023 → 168 trabajos, los tres primeros con DOI y acceso abierto.

## Cambios hechos sobre el original

`writing-plans` y `systematic-debugging` referenciaban skills de superpowers que aquí no
están instaladas. Esas referencias se reescribieron a las convenciones del repo: las
pruebas van a `NLP/tests/` con pytest, el plan vigente es `NLP/docs/PLAN.md`, los planes
cerrados van a `NLP/docs/archivo/` y cada ítem cierra con su bitácora en
`NLP/docs/bitacora/`.

## Lo que NO se instaló, y por qué

| Descartado | Motivo |
|---|---|
| `generate-image`, `scientific-schematics`, `infographics` | Exigen clave de OpenRouter o Gemini. Para diagramas basta SVG escrito a mano; para figuras de artículos, la skill `pdf` ya incluida en Claude Code |
| `research-lookup`, `perplexity-search`, `bgpt-paper-search` | Exigen `PARALLEL_API_KEY` u `OPENROUTER_API_KEY` |
| `scientific-writing` | 260 KB y depende de `research-lookup`, que necesita clave |
| `test-driven-development` (superpowers) | «Ninguna línea sin una prueba que falle antes» encaja mal con trabajo exploratorio de NLP. La disciplina que sí importa aquí la impone `verification-before-completion` |
| [nimrodfisher/data-analytics-skills](https://github.com/nimrodfisher/data-analytics-skills) | Orientado a analítica de negocio (embudos, cohortes, A/B, interlocutores) y **sin licencia declarada** |
| Cualquier MCP de SQL Server | Los datos de la base son clínicos y sensibles. Ver abajo |

## Primera entrega: pronosticar los picos de triage — mismo origen (MIT/BSD/Apache)

Instaladas el 2026-09-17, segunda tanda. El objetivo está en `CLAUDE.md` en la raíz:
anticipar cuándo sube el número de solicitudes de triage.

| Skill | Para qué | Licencia |
|---|---|---|
| `statsmodels` | ARIMA, GLM, modelos mixtos, diagnósticos y residuos. Es la herramienta del recuento por día: Poisson y binomial negativa con denominador como *offset*, estacionalidad semanal, festivos como regresores | BSD-3 |
| `aeon` | Aprendizaje automático sobre series temporales con API tipo scikit-learn: pronóstico, detección de anomalías, segmentación y búsqueda por similitud | BSD-3 |
| `hypothesis-generation` | Convierte una observación en una hipótesis falsable con su predicción y el experimento que la pone a prueba. Evita el vicio de encontrar el patrón después de mirar los datos | MIT |
| `exploratory-data-analysis` | Perfilado de un archivo de datos: estructura, calidad, nulos, duplicados, valores sospechosos, y qué análisis admite después. Reconoce CSV entre más de 200 formatos | MIT |
| `transformers` | Modelos preentrenados y **técnicas de ajuste fino**. Ver la advertencia de abajo | Apache-2.0 |
| `test-driven-development` | Prueba primero, verla fallar, código mínimo. Incluye `writing-good-tests.md` | MIT |
| `markdown-mermaid-writing` | Documentación en Markdown con diagramas Mermaid como estándar: 24 tipos de diagrama y 9 plantillas de documento | Apache-2.0 |

### Advertencias medidas

- **`transformers` pide un token de Hugging Face** para algunas funciones, y este proyecto
  **no tiene GPU**. Sirve como referencia de técnicas de ajuste fino, no como plan de
  entrenamiento. Para el pronóstico de recuentos diarios, un modelo de conteo bien
  especificado con sus variables de calendario va a ganarle a cualquier cosa basada en un
  LLM, y se puede defender ante un comité clínico.
- **CSV**: la skill `xlsx` que llega sincronizada de la cuenta ya lee, limpia y arregla
  `.csv` y `.tsv`. `exploratory-data-analysis` no la reemplaza: una revisa y perfila, la
  otra edita.
- **`polars` se descartó**: su propia descripción la sitúa en conjuntos de 1 a 100 GB. Aquí
  el CSV grande tiene 9.311 filas. `pandas` sobra.
- **Las skills de Nixtla** ([plugins-nixtla](https://github.com/jeremylongshore/plugins-nixtla),
  `statsforecast` y `nixtla-cross-validator`) se descartaron por ahora: el repositorio no
  declara licencia en la raíz, mezcla 30 habilidades de mercados de predicción con las de
  series, y parte exige `NIXTLA_TIMEGPT_API_KEY`. La biblioteca `statsforecast` sí es buena
  candidata si un día hace falta `AutoARIMA`; instalarla no requiere la skill.
- **`timesfm-forecasting`** (modelo fundacional de Google, 200 M de parámetros, ~1,5 GB de
  RAM en CPU) se descartó como punto de partida. Puede servir de referencia de tiro cero
  más adelante, pero primero hay que tener la línea base tonta —media móvil y día de la
  semana— que todo pronóstico tiene que superar para justificar su existencia.

## Qué skills ve una sesión abierta en este repositorio

`.claude/settings.local.json` contiene `"syncClaudeAiPlugins": false`. Eso apaga, **solo
para las sesiones de este directorio**, los seis paquetes del marketplace
`knowledge-work-plugins` que cuelgan de la cuenta de claude.ai (`small-business`, `legal`,
`human-resources`, `design`, `data` y `cowork-plugin-management`): unas sesenta habilidades
de trabajo de oficina que no tocan este proyecto y que competían por activarse solas. No se
borra nada y otros proyectos siguen viéndolas; el ajuste está puesto en el archivo *local*
precisamente porque los de proyecto (`settings.json`) no leen esta clave.

Las **skills** sincronizadas de la cuenta se dejaron encendidas a propósito: `pdf`, `xlsx`,
`docx`, `pptx`, `docs`, `skill-creator`, `import-memory` y `morning`. Las cuatro primeras
hacen falta para leer artículos y hojas de cálculo, que es justo lo que se hace aquí.

Queda entonces: las 16 de esta carpeta, las 8 sincronizadas de la cuenta y las que trae
Claude Code de fábrica.

## Restricción permanente sobre los datos

No se accede a la base de datos SQL Server desde Claude: ni MCP, ni `pyodbc`, ni consultas
exploratorias. El material de trabajo son las tablas que el propietario ya tiene
conectadas y los archivos que viven en el repo. Si hace falta un dato de la base, lo
extrae el propietario y lo deja como archivo.
