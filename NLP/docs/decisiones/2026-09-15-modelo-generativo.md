# Uso de modelos generativos en el pipeline

Fecha: 2026-09-15. Ítem: previo al plan (petición P2). Afecta a
`reduccion/extractor.py` y a cualquier propuesta de "mejorar el modelo".

## Pregunta

Si conviene sustituir o complementar el corrector por un modelo de lenguaje local que
reescriba la nota corrigiendo ortografía y extrayendo el contexto (propuesta: Llama
pequeño u otro modelo).

## Opciones consideradas

1. Modelo generativo que reescribe la nota completa.
2. Modelo generativo que solo copia fragmentos literales, verificados contra la nota
   (diseño actual de `extractor.py`).
3. Sin modelo generativo: reglas, léxicos y modelos discriminativos.

## Medición

Equipo: i7-8550U, 4 núcleos, 16 GB, sin GPU. Ollama con `qwen2.5:3b-instruct`.

- Velocidad: 5,5 tokens/s (48 tokens en 8,7 s; carga 8,3 s). Para 9.311 notas con ~50
  tokens de salida: ~22 h. Para 94.136 notas: ~10 días. `gemma4:26b` (18 GB) no cabe en
  16 GB de RAM.
- Calidad con un prompt de reescritura sobre una nota real (anonimizada): `crisis
  convulsiva` → `convulsión epiléptica` (inventa etiología); `O2 bajo máscara de no
  reinhalación` → `O2 por vía nasal` (cambia el dispositivo: alto flujo por bajo flujo);
  `chupeteo` (automatismo de la crisis) → `uso de chupete` (destruye un signo).

## Decisión y motivo

Opción 2 se mantiene, restringida por coste a las notas donde las reglas fallan (E5.6
fijará el umbral de longitud con evidencia). La opción 1 se descarta: introduce
exactamente el tipo de error que el proyecto intenta eliminar, y su coste en esta máquina
es inviable para el corpus. Ningún modelo generativo reescribe texto clínico en este
proyecto (principio 3 del plan).

## Qué la invalidaría

Disponer de GPU y de un conjunto de evaluación (E0.6) en el que un modelo generativo con
verificación literal supere a las reglas en acuerdo de `motivo_span` sin pérdidas reales.
