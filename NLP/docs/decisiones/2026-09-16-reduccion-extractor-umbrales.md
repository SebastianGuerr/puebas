# Extractor (fase 5b): a qué notas se manda, qué criterio de terminología usa y qué devuelve si no hay motivo

Fecha: 2026-09-16. Ítem: E1.5 (migración de documentación de código a `docs/`,
a partir de comentarios existentes en `reduccion/extractor.py`). Módulo:
`reduccion/extractor.py`.

## Pregunta 1 — ¿a qué notas se manda el extractor?

Opciones: mandar solo las notas largas, donde el recorte por reglas falla
más, o mandar todas y usar también el dictamen del modelo en las notas
cortas.

### Medición

Cola larga del corpus: notas de más de 30 palabras, 1.959; de más de 15
palabras, ~6.000. Medido en la máquina de desarrollo (i7-8550U, 4 núcleos,
sin GPU): el modelo de 3B en Q4 tarda del orden de 3 s por nota. Pasar las
~28.000 notas del corpus completo tomaría ~27 horas; pasar solo las de más
de 15 palabras, entre 2 y 6 horas.

Con el umbral original en 15 palabras, las notas cortas —el 71 % del
corpus— no recibían dictamen del modelo: `extraer()` devolvía `None` por
"nota corta" y quien llama no podía distinguir "es corta y el recorte por
reglas ya basta" de "el modelo la vio y concluyó que no hay motivo de
consulta" (`ESTADO_SIN_CONTEXTO`). Subir el umbral a 1 (verlas todas)
multiplica el tiempo de esta fase por algo más de tres: de ~4 h a ~14 h por
cada 5.000 notas sobre CPU.

## Decisión y motivo

`LONGITUD_MINIMA = 1`: el modelo ve todas las notas. El extractor dejó de
usarse solo para recortar y pasó también a dictaminar si la nota tiene
motivo de consulta, y esa distinción hace falta en las notas cortas tanto
como en las largas. El precio en tiempo está medido y se acepta.

## Pregunta 2 — ¿basta con verificar que el fragmento esté en la nota?

`verificar()`/`localizar()` comprueban que cada fragmento devuelto por el
modelo exista literalmente en la nota, pero no comprueban que el modelo
haya devuelto TODO lo que debía. Un fragmento correcto pero incompleto pasa
la verificación sin problema: medido, el modelo devolvió `"sangre mucho"`
de una nota cuyo motivo real era una herida en la mano.

## Decisión y motivo

Se añade `FRACCION_CLINICA_MINIMA = 0.50`: la extracción tiene que
conservar al menos la mitad de la terminología clínica que el recorte por
reglas encontraba en el mismo tramo (`conserva_lo_clinico()`). Se compara
terminología y no longitud, porque quitar trámite acorta el texto sin
perder evidencia, que es justo lo que el modelo debe hacer. La referencia
se filtra primero con `depuracion.sin_apartados_no_clinicos()` para no
penalizar al modelo por quitar bien los antecedentes, que no son el motivo
de hoy.

## Pregunta 3 — ¿qué hacer cuando el modelo concluye que no hay motivo de consulta?

Una respuesta vacía del modelo (ningún fragmento sobrevive a la
verificación, y tampoco hay fragmentos inventados) es una conclusión, no un
fallo.

### Medición

Una versión anterior marcaba la nota (por ejemplo, con una anotación de
"sin información relevante") en vez de devolver `None`, y el efecto era
medible: el texto de embedding pasaba de 128 a 141 palabras de media,
porque marcar no reduce.

## Decisión y motivo

`extraer()` devuelve `None` (estado `ESTADO_SIN_CONTEXTO`) y deja que
`reduccion.sin_reducir()` conserve el texto tal cual, sin marca añadida.

## Qué la invalidaría

Un conjunto de evaluación (E0.6) que mida el acuerdo de `motivo_span`
permitiría ajustar `FRACCION_CLINICA_MINIMA` con una curva
precisión/cobertura en vez de un único ejemplo. Disponer de GPU cambiaría
el cálculo de costo de `LONGITUD_MINIMA`.
