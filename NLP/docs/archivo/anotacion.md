# Guía de anotación del conjunto de evaluación (gold v0)

Ítem del plan: E0.6 (`PLAN.md` §8). Formato del gold: `PLAN.md` §4.5. Taxonomía de
gravedad: `INVESTIGACION.md` §3.4. Contexto de qué falla hoy en el corrector y qué debe
distinguir quien anota: `decisiones/2026-09-16-E4.1-reversion-de-correcciones.md`.

Esta guía la sigue una persona con criterio clínico al rellenar
`NLP/salidas/evaluacion/muestra_gold_v0.csv` (400 notas reales, muestreadas de forma
estratificada; ver la bitácora del ítem para el método y la distribución). El resultado
final, con las siete columnas canónicas y sin las columnas de diagnóstico, se guarda como
`NLP/datos/evaluacion/gold_v0.csv` (ruta ya declarada en `NLP/rutas.py` como `GOLD_V0`).
La plantilla versionada con la cabecera y tres filas sintéticas de ejemplo está en
`NLP/datos/evaluacion/gold_v0_plantilla.csv`.

## 1. Qué archivo se llena y qué columnas toca el anotador

`muestra_gold_v0.csv` trae, por nota: `OID`, `estrato`, `doble` (`si`/`no`, si la nota
está marcada para doble anotación), `texto_original` (tal como está en el CSV del
pipeline), y las columnas a rellenar: `texto_correcto`, `motivo_span`, `gravedad`,
`anotador`, `comentario`. Al final trae cuatro columnas con prefijo `_` (por ejemplo
`_distancia_sustantiva`, `_ratio_frecuencia`): son diagnóstico de por qué la nota entró a
la muestra, **no se editan ni se copian al gold final**.

`texto_correcto` **se deja vacío en el archivo de partida**, no precargado con
`texto_corregido` del pipeline. Motivo: el propósito central de este conjunto es medir
si el corrector cambia notas correctas por otras equivocadas (`ahogado → abogado`,
`volcamiento → tocamiento`, `paraclínicos → paralíticos`; ver la decisión de E4.1).
Mostrar la salida del sistema antes de que la persona lea el original ancla el juicio
hacia aceptar esa salida — es el sesgo que en estimación de calidad de traducción se
llama *post-editing bias* — y precisamente diluiría la sensibilidad del gold a los daños
que se quiere detectar. El costo es más trabajo por nota (escribir en vez de revisar);
se acepta ese costo porque el principio 2 del plan es precisión antes que ahorro de
esfuerzo. Si en una sesión futura se decide precargar para ganar velocidad, la
mitigación mínima es: registrar la nota como "ya vista" solo después de que la persona
escriba su propio `texto_correcto`, y solo entonces mostrar la salida del sistema para
comparar y comentar la diferencia en `comentario`.

## 2. `texto_correcto`: qué es y qué no es

Es el texto **solo con la ortografía corregida**, palabra por palabra, sin tocar nada
más. No es una reescritura, no es un resumen, no es una versión "más clara".

- **Se corrige**: errores de digitación (`dolro` → `dolor`), palabras partidas o
  pegadas (`do lor` → `dolor`, `sub clinica` → `subclinica`), tildes ausentes en
  palabras que las llevan (`dias` → `días`), concordancia de género/número/persona
  cuando es un error evidente de quien escribió (ver el caso `llevo/lleva` en la
  sección 4).
- **No se corrige**: el estilo (mayúsculas, orden de las palabras, redundancias),
  la puntuación salvo que impida leer la frase, ni la gramática cuando la frase ya se
  entiende sin ambigüedad.
- **Abreviaturas**: se mantienen tal cual (`pte`, `tto`, `ap`, `aa`, `fc`, `ta`). No se
  expanden — expandirlas es tarea de `recursos/lexico.py` y de la fase 3, no de este
  conjunto. Solo se corrige una abreviatura si está mal escrita de forma evidente y
  sigue siendo la misma abreviatura (`pcte` con una letra de más o de menos, no un
  cambio de sentido).
- **Siglas**: igual que las abreviaturas, se dejan como están (`UCI`, `EPS`, `TA`,
  `FC`). No se corrige una sigla por su forma "más frecuente en el diccionario general"
  — es exactamente el error que hoy comete el corrector automático por no tener una
  lista de protección (E3.2).
- **Nombres propios** (personas, IPS, municipios, EPS): no se corrigen salvo un error
  de digitación evidente que no cambie a qué persona o lugar se refiere. Ante la duda,
  se dejan igual y se anota la duda en `comentario`.
- **Números**: nunca se inventan ni se ajustan por criterio clínico (no se "corrige" una
  dosis o una edad porque parezca clínicamente rara). Solo se corrige la forma —
  separar un número pegado a una palabra (`19.6SMS` → `19.6 SMS`) — nunca el valor.
- **Tildes**: se restituyen según el español estándar, con independencia de que el
  corrector automático hoy las restituya o de que E4.5 decida en el futuro no
  restituirlas. El gold representa la forma correcta, no una decisión de ingeniería del
  pipeline. Para la métrica esto es indiferente: `evaluacion/metricas.py` compara
  tokens en minúscula pero **no pliega tildes**, así que escribir `días` frente a
  `dias` sí puede producir una discrepancia; se documenta aquí para que quien lea los
  resultados de E4.5 sepa de dónde puede venir.
- **Colombianismos y jerga del servicio**: si la palabra es una forma reconocible del
  español hablado en Colombia (`antier`, `maluca`, `piquiña`, `cuncho`, `parrillera`,
  `machuque`, `paila`, `guayabo` en sentido de malestar, etc.), se deja igual. No se
  reemplaza por su equivalente de diccionario. Ver la sección 4, caso 1.

## 3. `motivo_span`: qué es y qué no es

Es el **fragmento literal** de `texto_correcto` (debe ser una subcadena exacta, no un
resumen ni una paráfrasis) que expresa el motivo de consulta: qué le pasa al paciente y
por qué acude hoy.

Reglas de inclusión:

- El síntoma o motivo principal, con su duración o inicio si está pegado a él
  (`dolor abdominal desde hace 3 días`).
- Las **negaciones pertinentes al cuadro actual** (`dolor torácico, niega disnea ni
  sudoración`): niegan síntomas asociados que un clínico preguntaría para caracterizar
  el motivo, así que son parte del motivo, no ruido.
- Si hay más de un motivo independiente en la misma nota, se anota el fragmento
  contiguo del motivo principal (el primero o el más desarrollado) y el motivo
  secundario se resume en `comentario`. `motivo_span` es una sola subcadena contigua,
  no una lista.

Reglas de exclusión:

- **Antecedentes** (`AP:`, `AF:`, `AQx:`) que no son la razón de la consulta de hoy. Si
  el antecedente y el motivo coinciden (`control de HTA, refiere cefalea`), solo entra
  la parte que motiva la consulta de hoy.
- **Trámite administrativo**: derivaciones, EPS, autorizaciones, horarios de atención,
  disculpas institucionales. Si la nota es puramente administrativa, `motivo_span`
  queda **vacío** (ver el ejemplo 6 de la sección 4) — vacío es una respuesta válida,
  no un olvido.
- **Examen físico y hallazgos de la valoración**, salvo que el hallazgo sea
  literalmente el motivo por el que consultó (p. ej. "consulta por hallazgo de masa en
  control"). Por defecto, "al examen: abdomen blando, no doloroso" no es motivo, es
  constatación.
- Notas de control prenatal, vacunación, psicología, odontología cuando son solo listas
  de checkeo sin un síntoma nuevo: no son motivo de consulta salvo que el texto lo diga
  explícitamente.

## 4. Taxonomía de `gravedad`

Cuatro categorías, adaptadas de la taxonomía minor/major/critical de estimación de
calidad en traducción (WMT21 Critical Error Detection, ACES; `INVESTIGACION.md` §3.4) al
problema de esta fase. Clasifica **qué tan grave sería un error del corrector en esta
nota**, no la gravedad clínica del paciente.

| Valor | Cuándo se usa |
|---|---|
| `sin_error` | `texto_original` ya está bien escrito; no hace falta ninguna corrección. |
| `leve` | Errores de digitación, tildes, mayúsculas o puntuación que no cambian el significado ni el motivo de consulta. Una corrección equivocada aquí es molesta pero no engañosa. |
| `grave` | El error afecta la legibilidad o cambia una palabra por otra sin alterar el hecho clínico central (una abreviatura ambigua, una concordancia verbal que cambia quién narra pero no qué pasó). |
| `critico` | Si el corrector lo resuelve mal, cambia el motivo de consulta, el síntoma, el mecanismo de lesión, la lateralidad, un número, o invierte/borra una negación. Corresponde a los cuatro fallos medidos en el diagnóstico de partida (`ahogado → abogado`, `volcamiento → tocamiento`, `mareado → marcado`, `tosiendo → comiendo`) y a los casos de la sección 4 de esta guía. |

## 5. Diez ejemplos sintéticos resueltos

Todos los ejemplos son **inventados**, verosímiles, sin datos de pacientes reales
(principio 7 del plan). Los tres primeros de la lista final son casos difíciles
observados en el corpus real, expresados como palabras sueltas y no como notas
completas, por la misma razón.

### Casos difíciles como palabras sueltas

| # | Palabra / par | Qué es | Regla para `texto_correcto` | `gravedad` si el corrector la altera mal |
|---|---|---|---|---|
| 1 | `antier`, `maluca`, `piquiña` | Colombianismos: "anteayer", "sentirse mal/indispuesta", "picazón/prurito" | Se dejan igual; no se sustituyen por su forma de diccionario general | `critico` — son justo el síntoma o el momento de inicio que el motivo de consulta necesita |
| 2 | `paraclínicos` → `paralíticos` | `paraclínicos` = exámenes de apoyo diagnóstico (laboratorio, imágenes) | `texto_correcto` mantiene `paraclínicos`; `paralíticos` (personas con parálisis) es un concepto clínico distinto, no una corrección | `critico` — cambia por completo de qué se está hablando |
| 3 | `llevo` / `lleva` | Concordancia verbal con el sujeto de la oración | Si el sujeto es "el/la paciente" (tercera persona), es un error y se corrige a `lleva`; si es una cita textual del paciente en primera persona ("refiere: llevo 3 días..."), se deja `llevo`. Ante la duda, se documenta en `comentario` | `grave` si se corrige en el sentido equivocado (cambia quién narra, no el hecho clínico); no es `critico` porque el síntoma y su duración no cambian |

### Notas sintéticas completas

Formato de cada fila: `texto_original` → `texto_correcto` — `motivo_span` — `gravedad`.

4. `PTE REFIERE DOLROR ABDOMINAL DESDE AYER, NIEGA FIEBRE`
   → `PTE REFIERE DOLOR ABDOMINAL DESDE AYER, NIEGA FIEBRE`
   — motivo_span: `DOLOR ABDOMINAL DESDE AYER, NIEGA FIEBRE`
   — gravedad: `leve` (un solo typo, no cambia el motivo; la negación queda dentro del
   span porque caracteriza el cuadro).

5. `PACIENTE CON DO LOR DE GARGANTA Y TOS SECA`
   → `PACIENTE CON DOLOR DE GARGANTA Y TOS SECA`
   — motivo_span: `DOLOR DE GARGANTA Y TOS SECA`
   — gravedad: `leve` (palabra partida al escribir).

6. `PTE CON TA 140/90 FC 98 SATO2 96`
   → `PTE CON TA 140/90 FC 98 SATO2 96` (sin cambios: siglas y cifras correctas)
   — motivo_span: `` (vacío: son signos vitales, no hay motivo de consulta expresado)
   — gravedad: `sin_error`.

7. `AP: HTA, DM2. CONSULTA HOY POR CEFALEA DE 2 DIAS DE EVOLUCION`
   → sin cambios
   — motivo_span: `CEFALEA DE 2 DIAS DE EVOLUCION`
   — gravedad: `sin_error` (el antecedente HTA/DM2 queda fuera del span: no es la razón
   de la consulta de hoy).

8. `PACIENTE ACUDE A RECLAMAR FORMULA MEDICA, EPS AUTORIZA ENTREGA`
   → sin cambios
   — motivo_span: `` (vacío: trámite administrativo puro, sin contenido clínico)
   — gravedad: `sin_error`.

9. `CONSULTA POR DOLOR ABDOMINAL. AL EXAMEN: ABDOMEN DEPRESIVLE NO DOLOROSO A LA PALPACION`
   → `CONSULTA POR DOLOR ABDOMINAL. AL EXAMEN: ABDOMEN DEPRESIBLE NO DOLOROSO A LA PALPACION`
   — motivo_span: `DOLOR ABDOMINAL` (el hallazgo del examen físico queda fuera, aunque
   se haya corregido su ortografía)
   — gravedad: `leve` (el error está en el examen físico, no en el motivo).

10. `NIÑO DE 3 AÑOS CON FIEBRE NO CUANTIFICADA, MADRE NIEGA CONVULSIONES`
    → sin cambios
    — motivo_span: `FIEBRE NO CUANTIFICADA, MADRE NIEGA CONVULSIONES`
    — gravedad: `sin_error`; se marca el ejemplo para mostrar que una negación bien
    escrita (`niega convulsiones`) debe seguir diciendo exactamente eso — invertirla
    (`madre refiere convulsiones`) sería el caso `critico` que esta guía busca detectar.

## 6. Doble anotación y kappa de Cohen

Las notas con `doble = si` en `muestra_gold_v0.csv` (200 de las 400) se anotan por
**dos personas de forma independiente**, sin que una vea el trabajo de la otra. Cada una
guarda su propio CSV completo (mismas columnas que `muestra_gold_v0.csv`, incluida al
menos `OID` y `gravedad`), por ejemplo:

```
NLP/salidas/evaluacion/gold_v0_doble_anotadorA.csv
NLP/salidas/evaluacion/gold_v0_doble_anotadorB.csv
```

El acuerdo se mide sobre la columna `gravedad` con el módulo ya existente
`NLP/evaluacion/metricas.py` (no se modifica: ya tiene `--kappa-a/--kappa-b`), desde la
raíz del repositorio:

```
C:\Users\ad6708\Documents\puebas\.venv\Scripts\python.exe -m NLP.evaluacion.metricas ^
  --kappa-a NLP/salidas/evaluacion/gold_v0_doble_anotadorA.csv ^
  --kappa-b NLP/salidas/evaluacion/gold_v0_doble_anotadorB.csv
```

Imprime los OID comunes a ambos archivos y el kappa de Cohen sobre `gravedad`. El
criterio de la ficha (`PLAN.md` §8, E0.6) es **kappa ≥ 0,7**; si queda por debajo, se
revisa esta guía (probablemente la frontera `grave`/`critico` o `leve`/`sin_error`, que
son las más subjetivas) y se re-anota la muestra de calibración, no se relaja el umbral.

## 7. Tiempo estimado por nota

La muestra de E0.6 **no** tiene la longitud típica del corpus (mediana de 6 palabras,
`INVESTIGACION.md` §1): está deliberadamente enriquecida con notas largas y difíciles.
Sobre las 400 notas de `muestra_gold_v0.csv`, la longitud en palabras de
`texto_original` tiene mediana 16, media 30,5, y percentil 90 en 76 palabras (máximo
295, notas con encabezados de control prenatal). Estimación por tramo, medida en minutos
de lectura + escritura de `texto_correcto` + decisión de `motivo_span` y `gravedad`:

| Tramo (palabras) | Notas en la muestra | Minutos por nota | Subtotal |
|---|---|---|---|
| ≤ 10 | 151 | 1,5 | 226,5 min |
| 11–40 | 142 | 4 | 568 min |
| > 40 | 107 | 9 | 963 min |

Total de una pasada completa (400 notas): ≈ 1.758 min ≈ **29,3 horas**. La doble
anotación repite el trabajo en 200 notas con una distribución de longitud similar (se
marcaron proporcionalmente por estrato): ≈ 14,7 horas adicionales. **Total ≈ 44 horas ≈
5,5 jornadas de 8 horas para una sola persona cubriendo las dos pasadas**, o ≈ 3
jornadas por persona si son dos anotadores que se reparten la pasada única y ambos cubren
las 200 de doble anotación.

Esta cifra es más alta que la estimación previa de la ficha ("persona 1–2 jornadas",
`PLAN.md` §8). La diferencia se explica por la composición de la muestra: al
sobremuestrear a propósito los estratos difíciles (terminología perdida, distancia alta,
riesgo clínico, longitud extrema), el 27 % de las notas supera las 40 palabras, con
notas de control prenatal de hasta 295 palabras y varias secciones, mucho más lentas de
anotar que la nota mediana del corpus. Se deja anotado como algo a ajustar en la ficha
del plan, no se improvisa una muestra más corta para que encaje en la estimación
original.

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-16 | E0.6 | Primera versión: reglas de `texto_correcto` y `motivo_span`, taxonomía de `gravedad`, diez ejemplos sintéticos, procedimiento de doble anotación con el comando de kappa, estimación de tiempo por tramo de longitud |
