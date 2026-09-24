# Evaluación del prompt: arreglar lo que falla sin dañar lo que sale bien

`NLP/banco.py` y `NLP/fidelidad.py`. Existen desde el 2026-09-23.

## El problema que resuelven

Al ajustar el prompt a mano pasaba siempre lo mismo: **se arreglaban unas notas y se dañaban
otras que antes salían bien**. Está documentado en [PROMPT.md](PROMPT.md): v4 salió peor que
v3. Sin una forma de medir las dos cosas a la vez, cada retoque era una apuesta, y por eso
el prompt se quedó en v1.6.

La solución es la estándar en cualquier cambio de software: **un banco de regresión**. Dos
conjuntos fijos de notas, y cada versión nueva del prompt se corre sobre los dos:

| Banco | Qué contiene | Qué se le exige a una versión nueva |
|---|---|---|
| `fallos.csv` | Salidas con al menos una alucinación clara | Que las corrija |
| `aciertos.csv` | Muestra de salidas sin ninguna bandera | **Que no las dañe** |

**Una versión solo es mejor si corrige fallos sin dañar aciertos.** Las dos cifras se miran
juntas; ninguna vale sola.

## Por qué hacía falta, con evidencia

El 2026-09-23 se encontró que, cuando la nota es solo un trámite de remisión, el modelo
inventa una queja entera:

> «ME INDICAN CONSULTAR POR URGENCIAS» → «dolor abdominal intenso y persistente desde hace 24 horas»

21 notas distintas dieron esa misma salida, y ninguna mencionaba el abdomen, las horas ni el
dolor. Sobre el corpus completo serían ~690 dolores abdominales inventados. Ese es el
tamaño de error que justifica no procesar las 93.991 notas hasta arreglarlo.

## Los detectores (`fidelidad.py`)

Comparan la salida con la nota original. Todos son deterministas.

| Bandera | Qué detecta | Fuerza |
|---|---|---|
| `numero_inventado` | Un número en la salida que no está en la nota («ayer» autoriza 1 y 24) | fuerte |
| `lado_inventado` | Derecha/izquierda sin que la nota diga el lado | fuerte |
| `cuerpo_inventado` | Una parte del cuerpo que la nota no nombra | fuerte |
| `descarte_falso` | `sin motivo clinico` en una nota con síntomas | fuerte |
| `frase_comodin` | La misma salida desde ≥ 3 notas distintas, **y** sin base en esta | fuerte |
| `formato` | Salida vacía o de más de 200 caracteres | fuerte |
| `queja_sin_sintoma` | Nota de trámite (remisión, derivación, ambulancia…) o cortada, sin nada clínico, y salida con una queja sin base | fuerte |
| `copia_de_ejemplo` | La salida repite un ejemplo del prompt v1.6 sin respaldo en la nota | fuerte |
| `embarazo_perdido` | La nota dice gestante o semanas de gestación y la salida lo pierde (regla 6) | fuerte · 21/21 leídas |
| `duda_a_certeza` | «creo que», «al parecer» → afirmado como hecho (regla 7) | fuerte · 13/14 leídas |
| `negacion_perdida` | «niega X» → X afirmado, o «niega» deformado («nieta») | fuerte · 4/4 leídas |
| `duracion_cambiada` | «antier» → «ayer»; número de la duración cambiado | fuerte · 3/3 leídas |
| `identificador_en_salida` | Nombre tras dr/sra, o institución de salud, en la salida (regla 4) | fuerte · 5/5 leídas |
| `poca_base` | Menos de la mitad de las palabras de la salida están en la nota o en el glosario | suave |

**Cómo se dio por fuerte cada detector**: leyendo **todo** lo que marcaba sobre las 3.087 notas,
enmascarado. Con 4 y 3 casos, la precisión de `negacion_perdida` y `duracion_cambiada`
todavía no está demostrada.

### La lección de los detectores: su primera versión siempre dispara de más

| Detector | Primera versión | Tras leer lo marcado |
|---|---|---|
| `queja_sin_sintoma` | 408 notas, casi todas correctas («hemorroides», «sonda tapada») | 62: exige la señal POSITIVA de trámite |
| `embarazo_perdido` | ~75 | 21: «movimientos fetales», «contracciones», «aborto» cuentan como embarazo conservado |
| Sonda elegida automáticamente | 4 de 8 «fallos» eran salidas correctas | Sonda armada a mano |

**Los detectores encuentran candidatos; no deciden qué es un fallo.**

### Pérdida de detalle (`perdido`)

Lo contrario de inventar: números, partes del cuerpo y negaciones que la salida anterior
decía, que la nota respalda, y que la nueva ya no dice. Existe porque empujar al modelo contra
la invención también lo empuja a recortar: una versión de v1.7 dejó de decir «en mesogastrio»,
«11 kilos» y «3 días» sin que ninguna bandera lo viera. Límite: no ve sub-zonas.

## Los filtros: lo que el modelo no cumple, aplicado en código

`posprocesar()` del prompt candidato aplica, después del modelo, filtros que **solo quitan** y
solo lo que el detector confirma:

| Filtro | Qué hace | Por qué en código |
|---|---|---|
| `es_tramite_puro` | Salida → `sin motivo clinico` | Por prompt, cada arreglo del trámite dañaba otras notas (balancín medido en 6 vueltas). Exige señal positiva de trámite; **las notas cortas quedan fuera** («me arde», «está temblando» son motivos reales). Leídas las 44 que borraría: las 44 eran invenciones |
| `quitar_lado_inventado` | Borra derecha/izquierda sin respaldo | Ninguna redacción de la regla 10 lo consiguió con qwen3:8b |
| `quitar_parte_inventada` | Borra «en ‹parte›» sin respaldo | Ídem. Solo frases con preposición: un sustantivo suelto puede ser todo el motivo |
| `quitar_embarazo_inventado` | Borra el sufijo «en gestante de N semanas» si la nota no afirma embarazo | La regla 6 de v1.7 lo pide cuando la nota lo dice, y el modelo lo pegó también a notas que no («miastenia grave en gestante») |
| `restaurar_antier` | Devuelve «antier» donde el modelo puso «ayer» o «el día anterior» | Sistemático en qwen3:8b. Corre el inicio del cuadro un día, que es justo lo que mira el análisis de rezagos. **El único filtro que reemplaza**, y solo por la palabra exacta de la nota |
| `quitar_identificadores` | Borra instituciones y «dr/sra + nombre» copiados de la nota | Privacidad: la frase limpia se guarda, se agrupa y se muestra. Casos reales con el apellido del especialista y el nombre de la clínica |

Respetan erratas («derehco»), siglas («IZQ», «MSD») y «lado derecho».

## La cadena: filtros y segunda pasada (`NLP/cadena.py`)

Desde el 2026-09-24 todo lo que procesa una nota —`banco.py` hoy, y `procesar.py` y la
importación de la nube cuando se promueva el candidato— pasa por
`cadena.procesar_nota(texto, modulo_prompt, generar)`, que devuelve la salida y **cómo se
llegó a ella**:

| `pasada` | Qué pasó |
|---|---|
| `primera` | la primera respuesta, filtrada, es la que queda |
| `segunda` | la primera fue un descarte con evidencia clínica y la segunda pasada dio un motivo fiel |
| `revisar` | descartada dos veces, o la segunda inventó: queda «sin motivo clinico» y marcada para una persona |

**Por qué un paso más y no más prompt.** El descarte falso es el peor error del proyecto: el
paciente sale de la cuenta, que es el desenlace. Y es **inestable**: la misma nota («remitida
por… hernia discal») salió bien en una corrida y descartada en otra, con el mismo modelo y
prompt. Cada vuelta del prompt que empujaba contra el descarte hacía inventar en otras notas.
Repetir solo las notas sospechosas con un prompt que no admite abstenerse
(`construir_segunda_pasada()`) cuesta una llamada más **solo en esas**.

**Cuándo se dispara**: `fidelidad.necesita_segunda_pasada`, que hoy es el detector
`descarte_falso` —salida «sin motivo clinico» en una nota con evidencia clínica—. No se
dispara en un trámite puro («remitido de otro municipio»): ahí el descarte es correcto.

**Si la segunda inventa, gana el descarte.** Un descarte marcado se revisa; un motivo
inventado sin marca se cuenta como verdadero.

En la sonda, las notas que no se quedan en la primera pasada llevan `<segunda>` o
`<revisar>` al final de la línea. `--sin-filtros` apaga la cadena entera y mide al modelo
solo. En la nube la segunda pasada son dos viajes: `NLP/docs/NUBE.md`.

### Dos decisiones que evitan falsos positivos

**Lo que la nota autoriza a decir incluye el glosario.** Si la nota dice «me duele la
barriga», la salida «dolor abdominal» es una traducción correcta, no una invención. Por eso
la base de cada nota es: sus palabras, **más** los significados que el glosario del hospital
le asigna a esa nota concreta.

**Las partes del cuerpo van por grupos.** «Cefalea» está autorizada por «dolor de cabeza» y
«torácico» por «pecho». Lo que se detecta es la parte del cuerpo que aparece de la nada,
que es el patrón de alucinación documentado en v3 (5 de 7 alucinaciones eran eso).

**`poca_base` es solo sospecha.** Traducir coloquialismos es exactamente lo que se le pide
al modelo, así que una salida con pocas palabras de la nota puede estar perfecta. Va a
`sospechosas.csv` para mirarla, pero no cuenta como fallo.

### Lo que los detectores NO ven

Una salida que suena bien y está mal sin inventar nada detectable: invertir quién le hizo
qué a quién, perder una negación, elegir mal entre dos síntomas de la nota. **Por eso tu
revisión de los bancos manda sobre las banderas**: la columna `veredicto` de un revisor
humano pisa lo que digan los detectores.

## La sonda: iterar en minutos

El banco completo son ~420 llamadas. Para iterar se usa la **sonda**
(`NLP/salidas/banco/sonda.csv`): una nota verificada **a mano** por familia de fallo, más
guardas de regresión (notas que salen bien y que un cambio podría romper). Cada cambio del
prompt: primero la nota del fallo que se ataca (`--oid`), después la sonda entera
(`--sonda`). El banco completo, una sola vez al final.

La sonda informa por nota: `ARREGLADA` / `pendiente` (fallos), `igual` / `revisar` /
`PERDIO` / `RETROCESO` (guardas). **`revisar` hay que leerlo**: la sonda sabe que cambió, no
si está bien. Ejemplo real: «no me baja el azúcar» → «azúcar bajo» salió como `ARREGLADA`
porque ya no copiaba el ejemplo, pero dice lo contrario de la nota.

## Cómo se usa

```
python -m NLP.banco --armar          # arma los bancos desde lo ya procesado
python -m NLP.banco --linea-base     # cuántas notas llevas revisadas
python -m NLP.banco --evaluar        # el prompt actual contra los bancos
python -m NLP.banco --evaluar --rapido                       # 20 + 40 notas, para iterar
python -m NLP.banco --evaluar --prompt NLP/prompts/v1_7.py   # un candidato
python -m NLP.banco --evaluar --opcion repeat_penalty=1.0    # un parámetro
python -m NLP.banco --evaluar --modelo qwen3:14b             # otro modelo
```

**Los bancos se congelan una vez revisados.** `--armar` se niega a pisarlos: tu revisión es
trabajo humano. Para rehacerlos hay que pedirlo con `--rehacer`, y eso borra la revisión.

**Tu veredicto reordena los bancos.** Una nota de `aciertos.csv` que marques `mal` o `parcial`
pasa a contarse como fallo; una de `fallos.csv` que marques `bien` pasa a aciertos (era un
falso positivo del detector). Si escribes `salida_esperada`, esa es la referencia contra la
que se compara.

## Cómo se lee el resultado

```
FALLOS    corregidas   18/40   siguen mal   22
ACIERTOS  iguales     130/150  cambiadas    17   DANADAS   3
```

- **Corregidas**: la salida nueva ya no tiene banderas fuertes.
- **Iguales**: misma salida que antes. Lo ideal para la mayoría de los aciertos.
- **Cambiadas**: distinta pero limpia y parecida (≥ 40 % de palabras en común). Puede ser
  mejor o peor: mirarlas.
- **DAÑADAS**: la salida nueva tiene banderas que antes no tenía, o se parece muy poco a la
  anterior. **Esta es la cifra que hay que mantener en cero.**

## Qué palancas mueven de verdad las alucinaciones

| Palanca | ¿Sirve aquí? |
|---|---|
| `temperature` | **No.** Ya está en 0, que es lo correcto para extraer. Subirla solo añade azar |
| `top_p`, `top_k`, `seed` | **No hacen nada con temperatura 0**: el modelo ya elige siempre el token más probable |
| `repeat_penalty` | Puede: Ollama la aplica aunque la temperatura sea 0, y penaliza repetir palabras de la nota |
| `num_ctx` | Solo si alguna nota más el prompt pasa de 4.096 tokens: Ollama recorta **el principio**, que es donde están las reglas |
| **El texto del prompt** | **Sí**, es la palanca principal. Con cuidado por la lección de PROMPT.md |
| **Separar reglas (`system`) y nota** | Probablemente: los modelos respetan más lo que va en el mensaje de sistema |
| **Salida estructurada con evidencia** | **Sí, y es la más robusta**: pedir `{motivo, evidencia}` donde `evidencia` es un trozo copiado literal de la nota, y comprobar en código que ese trozo existe. Una queja inventada no tiene de dónde copiar |
| **Modelo más grande** (qwen3:14b) | Sí, los grandes inventan menos. Con GPU deja de ser caro |

## Límite conocido del banco actual

Las notas procesadas son de **15 días de enero de 2025**. Si la forma de escribir las notas
cambió durante los 20 meses —y el criterio de triage cambió en enero y noviembre de 2025—,
el banco no lo representa. Antes de la corrida completa conviene sumar al banco unas 100
notas repartidas por todo el periodo.
