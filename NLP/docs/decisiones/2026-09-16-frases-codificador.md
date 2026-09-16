# Codificador de frases: por qué roberta-clínico y no bge-m3, y por qué cachear por tramo

Fecha: 2026-09-16. Ítem: E1.5. Módulo: `reduccion/frases.py`.

## Pregunta

¿Qué codificador de frases usar para vectorizar los tramos de la nota antes
de clasificarlos, y hace falta cachear el resultado?

## Opciones consideradas (codificador)

1. `roberta-base-biomedical-clinical-es` (ya descargado para la capa de
   contexto de la fase 2).
2. `bge-m3` (reservado para la fase de embeddings, espacio multilingüe).

## Medición

Sobre CPU, en la máquina de desarrollo:

| Codificador | Velocidad | Tiempo para 40.602 tramos distintos |
|---|---|---|
| roberta-clínico | 76 frases/s | 8,9 min |
| bge-m3 | 15 frases/s | 46,0 min |

## Decisión y motivo (codificador)

roberta-clínico: cinco veces más rápido, ya está en disco, y está entrenado
sobre historias clínicas en español, que es exactamente este dominio.
bge-m3 se reserva para la fase de embeddings, donde hace falta un espacio
multilingüe.

## Medición (caché)

El corpus tiene 62.557 tramos pero solo 40.602 distintos: las frases
estereotipadas —justo las que interesa clasificar— se repiten cientos de
veces ("paciente en el momento clínicamente estable" aparece 367 veces).
Sin caché, `probabilidades()` vectorizaría cada una de esas 367 repeticiones
para obtener el mismo número.

## Decisión y motivo (caché)

`probabilidades()` cachea por tramo (`_PROBS`, en memoria de proceso).

## Qué la invalidaría

Un corpus con mucha menos repetición estereotipada (por ejemplo, notas de
otro servicio con redacción más variada) reduciría el beneficio de la
caché y podría justificar medir de nuevo la velocidad relativa de los
codificadores si cambia el volumen de tramos.
