# Competencia de modelos locales: cuál extrae mejor el motivo de consulta

`NLP/competencia/` y `NLP/prompts/candidatos/`. Existe desde el 2026-09-24. La bitácora de
cada decisión, con fecha, está en `docs/CONTEXTO.md` (entradas del 2026-09-24 «Se reabre la
competencia de modelos EN CPU» y «Cada modelo con su propio prompt»). Este documento es el
resumen del método y de lo medido.

## La pregunta

¿Hay un modelo local y ligero (CPU de 8 núcleos, 16 GB de RAM, sin GPU) que resuelva lo que
qwen3:8b con el prompt v1.7 no pudo —descartes falsos inestables, la duda que se vuelve
certeza, negaciones perdidas, coloquialismos mal traducidos— **sin dañar lo que qwen ya hacía
bien**?

## El método, y por qué así

| Decisión | Motivo |
|---|---|
| **Muestra de 63 notas**: la sonda (32: 17 fallos verificados + 15 guardas) + una muestra **nueva** de los bancos (31) | La sonda favorece a qwen: v1.7 se afinó mirándola. La nueva no la vio ningún prompt |
| **Banco corregido antes de juzgar**: 13 de las 63 notas cambiaron de banco al leerlas | 9 «aciertos» de v1.6 en realidad estaban mal por las reglas de v1.7; 4 «fallos» eran falsos positivos de un detector. Quedan 38 fallos y 25 aciertos |
| **Lista de verificación escrita antes de ver ningún modelo** (qué debe y qué no debe decir cada respuesta) | Que el juicio no dependa de quién compite |
| **Puntaje preregistrado**: fallo arreglado +1 (parcial +0,5); **acierto dañado −2** (parcial −1); descartes falsos aparte | Regla del propietario: no vale arreglar una nota y dañar otra que estaba bien. Un daño pesa el doble |
| **Juicio leído, no contado** | Los detectores no ven errores de sentido; en la competencia, 9 de las notas mal de un modelo no levantaban ninguna bandera |
| **Mismo peso para comparar familias** | Un 3B contra un 8B no dice nada de la familia. Los ~12B se reportan como un escalón más pesado |
| **Temperatura 0, Q4, un modelo a la vez** | Determinismo y la RAM de esta máquina (ver «Trampas») |
| **Dos modos**: `solo` (sin filtros ni segunda pasada) y `cadena` (lo de producción) | Con filtros se mide en parte a los filtros; sin ellos, al modelo |
| **Verificación por un juez ciego** | El primer resultado fuerte lo había juzgado un solo revisor |

## Fase 1: todos con el mismo prompt (v1.7), 63 notas

| Modelo | Peso | Solo | Con filtros | Descartes falsos | RAM | s/nota (mediana) |
|---|---|---|---|---|---|---|
| **gemma4:12b-it-qat** | ~12B | **+25** | **+26** | 5 | 8,49 GB | 23,8 |
| qwen3:8b (el actual) | 8B | +7 | +15,5 | 2 | ~5,9 GB | 16,4 |
| gemma3:12b | ~12B | +6,5 | +7,5 | **0** | 8,06 GB | 21,8 |
| tulu3:8b (Llama 3.1 reentrenado, AllenAI) | 8B | −8 | +2,5 | 3 | 5,58 GB | 15,5 |
| Llama-3.1-Storm-8B | 8B | −8 | +1,5 | 8 | 5,58 GB | 26,3 |
| llama3.1:8b (Meta) | 8B | −19,5 (−2 leyendo su respuesta final) | −9,5 | 2 (5) | 5,58 GB | lento: razona en voz alta |
| llama3.2:3b | 3B | piso: 6/32 bien en la sonda | — | 3 | 2,56 GB | — |

**Verificación ciega**: un segundo agente sin acceso a qué salida era de qué modelo juzgó las
43 notas donde qwen3:8b y gemma4:12b difieren. gemma4 fue mejor en 31, qwen en 3, empate en 9
(gemma4 33 bien / 6 parcial / 4 mal; qwen 7 / 23 / 13).

### Lo que se aprendió

1. **gemma4:12b resuelve casi todo lo que ningún 8B pudo**: expresiones coloquiales del oído y
   de un reflejo respiratorio, duda conservada 4/4, negaciones 4/4, la agresión por otra
   persona, «antier». No inventa lado, parte del cuerpo ni embarazo. **Su único error
   sistemático es el más caro: el descarte falso.** Es el mismo patrón que tuvo qwen3:14b: el
   bloque de abstención de v1.7 se endureció para que el 8B obedeciera, y un modelo más capaz
   lo cumple de más.
2. **Los errores de qwen son mecánicos** (lado, parte del cuerpo, «antier», institución) y los
   filtros de producción se escribieron para ellos: por eso con filtros sube de +7 a +15,5. **Los
   de gemma3 son omisiones y cambios de sentido**, que ningún filtro ve.
3. **La familia Llama inventa embarazos** copiando el molde de la regla 6 de v1.7 («en gestante
   de N semanas»): Tulu en 15 notas (un varón incluido), Storm en 12, llama3.1 en 9. Confirma
   la lección de `PROMPT.md`: toda palabra concreta del prompt acaba en las respuestas.
4. **llama3.1:8b razona en voz alta**: en el 54 % de las notas su primera línea no es la
   respuesta. Leyendo su respuesta final sube de −19,5 a −2, y aun así queda 9 puntos bajo qwen.
5. **Ningún modelo resolvió un coloquialismo de glucemia con el sentido invertido.** Es de
   glosario, no de modelo.
6. **La inestabilidad de qwen es real pero estrecha**: en 3 corridas de 16 notas duras cambia el
   veredicto de 1 (un descarte falso que sale o no). llama3.1:8b también cambia 1.

## Defectos de la cadena de producción que salieron de la competencia

Valen por sí solos, independientes del modelo que se elija. Pendientes de arreglar con prueba:

| Dónde | Defecto |
|---|---|
| `fidelidad.quitar_embarazo_inventado` | Borra un embarazo **real**: con «prueba positiva de embarazo», al quitar las semanas inventadas se lleva el embarazo y la salida queda vacía |
| `fidelidad.quitar_parte_inventada` | Borra una parte del cuerpo **real** cuando la nota la escribe con errata: convirtió una respuesta fiel en mala |
| Filtro de trámites | Deja restos sin sentido («derivada de la eps» → «la eps») |
| `necesita_segunda_pasada` | Se dispara en trámites puros bien descartados; con un cierre que prohíbe abstenerse, la segunda pasada solo puede copiar el trámite o inventar |
| `banco.enmascarar`, `fidelidad._TRATO`, `quitar_identificadores` | No reconocen la abreviatura «doc»: un «doc + nombre y apellido» pasa visible, y un modelo que lo copie no se filtra |
| `banco.enmascarar` | Tapa de más: ocultó palabras clínicas como si fueran nombres. Afecta a quien juzga, no al modelo |

## Fase 2: un prompt propio por modelo (en curso)

**Decisión del propietario**: un prompt afinado para un modelo no es igualdad de condiciones.
Cada modelo recibe su prompt, escrito por un agente que conoce sus errores, y **gana el primero
que cruce la barrera** (preregistrada, en modo cadena):

- **B1**: ≥ 12 de las 16 notas duras que qwen3:8b no resolvió, bien.
- **B2**: 0 aciertos dañados.
- **B3**: 0 descartes falsos sin marca (uno marcado `revisar` se tolera: lo ve una persona).
- **Confirmación** en una validación de 56 notas nuevas (7 por familia: duda, negación,
  duración, trámite, gestante, lado, coloquial, corta) que ningún agente de prompt ve.

Contra la memorización: los prompts solo llevan reglas generales (un revisor los audita), todos
parten de v1.7, máximo 3 rondas, mismos filtros. Reglamento completo: `NLP/competencia/REGLAMENTO.md`.

**Ronda 1** — cinco enfoques distintos, en `NLP/prompts/candidatos/`:

| Modelo | Enfoque |
|---|---|
| gemma4 | Abstención por categorías: qué dice del paciente (estado, aspecto, enfermedad por la que lo remiten, procedimiento, control) contra qué es trámite |
| gemma3 | El glosario inyectado es vocabulario, no la respuesta: gemma3 lo tomaba como respuesta entera y perdía localización y negaciones |
| qwen3 | `FORMATO="razonado"`: primero copia literal a cinco casillas (paciente, niega, duda, tiempo, embarazo o niño) y después redacta; abstenerse = casilla del paciente vacía |
| llama3.1 | Su razonamiento en voz alta pasa a un campo propio con casillas; se quita el molde del embarazo |
| tulu3 | Instrucciones en inglés; recordatorios armados en código con los detectores de `fidelidad` (la duda, cada «niega X», el tiempo), solo con lo que trae cada nota |

## Cómo se reproduce

Todo el material con texto clínico (muestras, notas enmascaradas, listas, salidas) vive en
`NLP/salidas/competencia/`, que git ignora. Desde la raíz del repo:

```
python NLP/competencia/verificar.py NLP/prompts/candidatos/<m>_r1.py          sin llamar al modelo
python NLP/competencia/comparar.py --modelo <tag> --modo cadena \
       --prompt NLP/prompts/candidatos/<m>_r1.py --muestra <muestra.csv> --salida <x>.jsonl
python NLP/competencia/filtrar.py          aplica los filtros a las salidas guardadas en modo solo
python NLP/competencia/segunda.py --primera <tag> --segunda <tag> --oids <lista>
bash   NLP/competencia/despachador.sh      corre pedidos.txt de uno en uno
```

## Trampas

- **Una sola corrida contra Ollama a la vez.** Dos modelos de 8B cargados dejaron 0,6 GB libres
  y cada nota pasó de ~80 s a ~3 min. En Windows, detener una tarea de fondo no mata a sus
  hijos: parar por PID y confirmar con `ollama ps`. El despachador existe por esto.
- **Los ~12B caben con ~2 GB de margen**; `gemma3:12b` desde la librería de Ollama pesa 8,1 GB
  porque incluye la visión (se usó el GGUF de solo texto de bartowski).
- **El orden A/B de un juez ciego va barajado por fila**: su resumen «A es mejor» no vale; valen
  sus veredictos fila a fila, destapados con la clave.
