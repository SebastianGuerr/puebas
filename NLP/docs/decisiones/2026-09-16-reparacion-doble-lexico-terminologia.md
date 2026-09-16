# Reparación: qué léxico usar para detectar pérdida de terminología clínica

Fecha: 2026-09-16. Ítem: E1.5 (trasladado del docstring de
`reparacion/comparacion.py`, función `_terminos_clinicos`). Módulo:
`reparacion/comparacion.py`.

## Pregunta

`comparacion.clasificar()` compara `texto_embedding` antes y después de reparar
una nota y marca `perdio_motivo` cuando el conjunto de terminología clínica
encontrada se reduce. `perdio_motivo` es la única categoría que detiene la
reparación (`reparar.py` no aplica el CSV si hay alguna), así que su valor
entero depende de no dar falsas alarmas: una alarma que salta por ruido obliga
a revisar a mano notas que estaban bien y, a la tercera vez, nadie la mira. Con
qué léxico se decide si una palabra es "terminología clínica" para este
propósito.

## Opciones consideradas

1. `depuracion.terminos_clinicos()` solo — indexa por raíz morfológica sobre
   10.402 entradas.
2. El léxico curado de `reduccion.py` (`reduccion._es_clinica`) solo — compara
   formas exactas.
3. Exigir que los dos coincidan (AND).

## Medición

Los dos léxicos fallan de formas distintas y no coincidentes:

- `depuracion.py`, por comparar raíces, da por clínicas `teniamos`,
  `recomendaciones`, `ingresa`, `cierres` y `observa` — todas por parecido de
  raíz, ninguna es terminología real.
- `reduccion.py`, por comparar formas exactas, no cae en eso, pero acepta
  `dada`, `salud` y `toma` como clínicas.

Exigir que ambos coincidan (opción 3) deja fuera esos falsos positivos y
conserva `desvanecimiento`, `isquemia`, `comisura`, `desviacion`, `gestante`,
`fetido`, `herida`, `cefalea`, `disnea` y `convulsiva` (diez términos reales).

Efecto sobre la muestra de 100 notas reparadas (la misma corrida que mide
`decisiones/2026-09-15-clasificador-freno-clinico.md`): siete alarmas de
`perdio_motivo`, las siete administrativas tras revisión manual (ninguna
pérdida real). **Nota de redacción (E1.5)**: el docstring original decía
"siete alarmas, de las que siete eran ruido" sin aclarar si ese conteo es el
resultado final con la opción 3 ya aplicada (que es como se interpreta aquí,
coincidiendo con la cifra de la decisión del freno del clasificador) o una
medición aparte; si se vuelve a medir, conviene fijar el comando y la muestra
exacta en este documento.

## Decisión y motivo

Opción 3 (AND de los dos léxicos). Vale más perderse una pérdida real que
gritar en falso: la opción 1 sola arrastra el ruido de la comparación por raíz
de `depuracion.py`, y la opción 2 sola acepta palabras administrativas
frecuentes (`dada`, `salud`, `toma`) que no son motivo de consulta.

## Qué la invalidaría

Que `depuracion.terminos_clinicos()` deje de comparar por raíz (ver
`ARQUITECTURA.md` §5, duplicación de léxico clínico entre `depuracion.py` y
`reduccion.py`) o que se unifiquen ambos criterios de "palabra clínica"; en ese
caso el AND dejaría de aportar nada sobre exigir un solo léxico.
