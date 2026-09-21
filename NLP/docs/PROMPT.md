# El prompt: por qué dice lo que dice

Vive en [`NLP/prompt.py`](../prompt.py), versión **v1.6**. Cada regla salió de un
fallo observado, no de una intuición. Este archivo guarda ese razonamiento para
que nadie lo deshaga sin saber lo que costó.

## La lección que gobierna todo

> **Cualquier palabra clínica concreta que aparezca en el prompt acaba saliendo
> en las respuestas, se ponga como ejemplo o como prohibición.**

Se aprendió probando cuatro redacciones completas del prompt:

| Versión | Qué se intentó | Qué pasó |
|---|---|---|
| **v1** | Reglas numeradas + 4 pares «entrada → salida» | Respuestas cortas y contenidas. Pero el modelo **copiaba los ejemplos**: una nota sobre un balón salió con el texto literal de un ejemplo de aplastamiento de dedo. |
| **v2** | Se quitan todos los ejemplos y se explica el rol y el contexto | Ganó donde se esperaba (dejó de copiar, conservó términos clínicos reales), pero **volvió locuaz al modelo**, y al alargarse inventó: «posible fractura de brazo izquierdo» en una nota que solo decía ME CAI. |
| **v3** | v2 + la brevedad de v1 + una revisión final explícita | Quitó las invenciones grandes, pero **5 de 7 alucinaciones eran rellenar una localización anatómica** que la nota no daba. La revisión final que pedía el prompt simplemente no se ejecutaba. |
| **v4** | Sección destacada: «no inventes una localización» | **Salió peor.** El modelo empezó a responder justamente el término anatómico que el prompt nombraba como ejemplo de lo que NO había que responder. |

De ahí las dos decisiones de diseño que no se negocian:

1. **El glosario se inyecta por nota, nunca entero** ([RECURSOS.md](RECURSOS.md)).
   Meterle los 455 coloquialismos contaminaría todas las respuestas.
2. **Las reglas 10-14 hablan de categorías, no de términos.** Dicen «una parte
   del cuerpo», «un lado», «una causa» — nunca nombran una parte del cuerpo
   concreta.

## Qué hace cada regla

| # | Regla | De dónde salió |
|---|---|---|
| 1 | Devuelve únicamente el motivo de consulta | el objetivo del proyecto |
| 2 | Traduce el coloquialismo hasta dejarlo en término clínico | el modelo dejaba crudo el colombianismo |
| 3 | Corrige la ortografía con el contexto de la frase | sustituye al corrector por palabra, que estropeaba `entumida` → `entubada` |
| 4 | Elimina EPS, lugares, acompañantes, filiación y signos normales | es ruido, y una parte es dato identificable |
| 5 | No diagnostiques ni supongas causa ni duración | «tengo la presión alta» no es «crisis hipertensiva» |
| 6 | Conserva lo que cambia la prioridad del triage | lateralidad, embarazo, edad pediátrica, negaciones explícitas |
| 7 | Si el paciente duda, conserva la duda | convertir duda en certeza es inventar |
| 8 | Trámite puro → `sin motivo clinico` | necesita una salida explícita para no forzar un motivo |
| 9 | Una sola línea, minúsculas, sin razonar en voz alta | el CSV es una línea por nota |
| 10 | No agregues lo que la nota no nombra | v3: 5 de 7 alucinaciones eran localización inventada |
| 11 | Si no descifras una sigla, déjala fuera | sustituía lo ilegible por algo que «sonara médico» |
| 12 | Fíjate en quién le hizo qué a quién | un paciente se cae **desde** un triturador y salió «trauma por trituración» |
| 13 | `sin motivo clinico` solo para trámites | dos notas con dolencia real salieron descartadas |
| 14 | Repasa tu frase contra la nota y quita lo que no esté | la revisión final de v3, ahora al final del todo |
| 15 | El glosario del hospital manda sobre tu interpretación | sin esto el modelo ignoraba las equivalencias inyectadas |

La regla 13 merece énfasis: **el falso descarte es el peor error posible**. Una
nota descartada por error borra a ese paciente del conteo diario, que es
exactamente el desenlace que el proyecto quiere medir. Una nota mal recortada se
corrige después; una nota que no está, no.

## Parámetros de generación

En [`modelo.py`](../modelo.py):

```python
{"temperature": 0, "top_p": 1, "seed": 7, "num_predict": 200, "num_ctx": 4096}
```

`temperature: 0` y `seed` fijo son requisito, no preferencia: sin ellos la misma
nota da respuestas distintas en dos corridas y el CSV deja de ser reproducible.

`think: False` se intenta primero y se reintenta sin esa opción si el modelo
devuelve 400. Lo que el modelo razone en voz alta lo quita `modelo.limpiar()`,
pero pedir que no razone ahorra tiempo de generación.

## Al retocar el prompt

1. Subir `VERSION` en `prompt.py`. Se imprime al arrancar y queda en el registro
   de la corrida.
2. No escribir ningún término clínico concreto como ejemplo ni como prohibición.
3. No medir la mejora contra respuestas esperadas que salieron del propio
   glosario (ver el aviso al final de [RECURSOS.md](RECURSOS.md)).
4. Una redacción nueva se compara **sobre las mismas notas**, no sobre una
   muestra nueva.
