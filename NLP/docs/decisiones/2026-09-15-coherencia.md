# Fase 2b: reversión de correcciones incoherentes con la nota

Fecha: 2026-09-15. Ítem: previo al plan (petición P4). Módulo:
`fase2_ortografia/coherencia.py`.

## Pregunta

Cómo deshacer, antes de escribir el CSV, las correcciones que pasan el veto morfológico
palabra a palabra (`terminologia.admite`) pero estropean la nota (`ahogado → abogado`,
`volcamiento → tocamiento`, `mareado → marcado`, `tosiendo → comiendo`), sin deshacer
las correcciones buenas.

## Opciones consideradas

1. Reconocedor de entidades de spaCy sobre la nota para proteger nombres propios.
2. Nombres propios y siglas aprendidos del corpus (`lexico_casing.json`, 94.136 notas).
3. Criterios de daño de `evaluacion/auditoria.py` (distancia > 40 % de la longitud,
   original mucho más frecuente que el reemplazo, palabra conocida) aplicados en línea.
4. Deriva semántica por embeddings entre original y corregido.

## Medición

Muestra: 8.751 notas de `triage_limpio.csv` (texto original en minúsculas frente a
`texto_corregido`). Tres iteraciones:

| Versión | Notas tocadas | Reversiones distintas | Falsos positivos observados |
|---|---|---|---|
| 1: entidades por NER | 1,5 % (127) | 45 | `door → dolor`, `fibre → fiebre` revertidas como "nombre propio" (NER sobre texto en mayúsculas) |
| 2: nombres del corpus; original debe tener respaldo | 0,5 % (46) | 39 | `hipotirodismo → hipotiroidismo`, `febrila → febricula`, `caidaen → caida en` revertidas por orden de reglas |
| 3: expansión por subsecuencia antes de todo | **0,4 % (39)** | **32** | ninguno detectado en revisión manual de las 32 |

Coste: 2,6 ms por nota. Reversiones correctas de la versión 3 (selección):
`laceraciones → alteraciones`, `focalizaciones → localizaciones`, `mareado → marcado`,
`tosiendo → comiendo`, `ahogado → abogado`, `volcamiento → tocamiento`, `orozco →
tronco`, `montoya → motora`, `dutasteride → dutasterida`.

## Decisión y motivo

Se adopta la versión 3 con este orden de reglas: (1) restauración de tilde → dejar;
(2) el corregido es una expansión por subsecuencia del original (reutiliza
`sugerencias._es_subsecuencia`) → dejar; (3) el original es nombre propio o sigla del
corpus → revertir; (4) el original es clínico (léxico curado + morfología + siglas) y el
corregido no → revertir; (5) errata de teclado (anagrama o distancia ≤ 1) → dejar;
(6) si el original no tiene respaldo en ningún diccionario → dejar (revertir no
recupera nada); (7) el corregido no está en ningún diccionario → revertir; (8) distancia
> 40 % de la longitud → revertir; (9) frecuencia del original ≥ 10 veces la del
reemplazo → revertir.

La NER de spaCy se descarta como fuente de nombres propios: sobre una nota corta en
mayúsculas marca erratas como entidades; el corpus de 94.136 notas es la fuente fiable.
La deriva por embeddings no se prueba: la literatura la desaconseja para textos de seis
palabras (ver `INVESTIGACION.md` §3).

Los umbrales (40 %, factor 10) se copian de `auditoria.py` para que el informe posterior
siga siendo comparable. La regla de no degradación estricta (factor 1) queda como
experimento E4.1.

## Qué la invalidaría

Una tasa de reversión sobre texto limpio (E2.3) superior a 0,1 %, o pérdidas reales de
correcciones buenas en el gold (E0.6).
