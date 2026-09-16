# _quitar_institucional(): por qué se devuelve la nota entera cuando no queda ninguna oración útil

Fecha: 2026-09-16. Ítem: E1.5. Módulo: `reduccion/reduccion.py`
(`_quitar_institucional()`).

## Pregunta

Las oraciones se separan por punto y punto y coma, y buena parte del
corpus no lleva ninguno de los dos: la nota típica de triage es una frase
corrida. En esas notas el filtro institucional es todo o nada — basta que
el marcador aparezca al final para que se lleve por delante el motivo de
consulta. ¿Qué hacer cuando el filtro se queda sin ninguna oración útil que
devolver?

## Medición

Ejemplo real de una sola oración (sin puntos ni punto y coma):
"ingresa paciente refiriendo que lleva 8 dias con zumbido en oido derecho
... paciente estable sin criterio de urgencia vital" — el marcador "urgencia
vital" la descarta entera y el resultado sería cadena vacía.

Medido sobre 8.000 notas: 229 quedaban vacías así, y todas tenían un cuadro
clínico perfectamente legible.

## Decisión y motivo

Si no queda ninguna oración útil, `_quitar_institucional()` devuelve el
texto original en vez de la cadena vacía. Deja que decidan los pasos
siguientes, que trabajan sobre tramos y no sobre la nota completa
(`_quitar_clasificador()` primero, y los patrones de frase de
examen/conducta/antecedentes). Perder el bloque institucional de una nota
es barato; perder el motivo de consulta no lo es (ver `NLP/docs/FLUJO.md`,
sección 7, ejemplo "nota C").

## Qué la invalidaría

Separar también por coma en este filtro (como ya hace `frases.py` para sus
tramos) eliminaría buena parte de estos 229 casos, pero cambiaría el filtro
de "por oración" a "por tramo" y haría falta remedir el efecto sobre notas
cortas.
