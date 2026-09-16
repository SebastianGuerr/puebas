# Costuras del recorte: por qué "no inventar vecindad" y no enumerar qué patrón corta mal

Fecha: 2026-09-16. Ítem: E1.5. Módulo: `reduccion/reduccion.py`
(`crea_costura()`).

## Pregunta

Quitar un tramo del medio de la frase puede dejar pegadas dos palabras que
no lo estaban ("paciente que consulta por dolor" → "paciente que dolor").
¿Cómo detectar este fallo sin enumerar qué patrón concreto lo produce?

## Medición

Sobre 189 notas, las costuras eran el 70 % de todos los fallos del
recorte, y 13 de las 17 costuras encontradas empezaban por "paciente": los
patrones de trámite y de verbo de reporte se llevan el verbo y dejan el
sujeto huérfano pegado a lo siguiente.

## Decisión y motivo

`crea_costura()` no enumera qué patrón corta mal: compara los pares de
palabras contiguas del texto original y del recortado (separando por
puntuación, no dentro de un tramo) y falla si el recorte inventó una
vecindad que no existía en la nota. Es una propiedad del resultado, así que
vale para los patrones de hoy y para los que se añadan mañana. `recortar()`
usa esta comprobación para decidir entre la pasada agresiva y la suave (ver
`NLP/docs/FLUJO.md`, sección 7).

## Qué la invalidaría

Nada por ahora. Ver la discrepancia abierta en `NLP/docs/FLUJO.md`, sección
10, punto 6: `_pulir()` solo limpia el arranque huérfano al principio del
texto completo, no al principio de cada tramo interno que quedó pegado tras
un recorte por el medio — `crea_costura()` detecta el caso, pero la
limpieza posterior no siempre lo repara.
