# Handoff — sesión del 15–16 de septiembre de 2026

Documento de entrega para quien retome el trabajo. Está escrito para ser leído entero
antes de tocar nada, y dice tanto lo que se consiguió como lo que no.

**Resumen en una frase**: se arreglaron fallos reales y graves del pipeline, se construyó
todo el instrumental para medir, y **la calidad del texto que llega al agrupamiento mejoró
poco: 1,45 puntos de retención de terminología.** El problema que el propietario planteó
desde el principio —quedarse solo con lo importante de la nota— **sigue sin resolverse**, y
esta sesión además introdujo dos regresiones que hay que deshacer.

---

## 1. La medición que importa, y cómo se hizo

Durante la sesión se reportaron mejoras grandes (retención de 0,861 a 0,9516). **Esa
comparación era engañosa** y conviene no repetirla: comparaba contra un CSV generado sin el
modelo de spaCy y sin el léxico clínico. Esa mejora vino de **instalar artefactos que
faltaban** (hecho el 15/09), no del código.

La comparación honesta es **mismas notas, mismos artefactos, solo cambia el código**. Se
hizo con un *worktree* de git en el commit `35ae86a` (anterior a todo este trabajo), con los
mismos léxicos copiados, sobre las mismas 300 notas:

| Métrica | Código anterior | Código actual | Diferencia |
|---|---|---|---|
| Retención media de terminología | 0,9629 | 0,9774 | **+1,45 pp** |
| Notas que conservan toda su terminología | 92,31 % | 94,67 % | +2,36 pp |
| Notas que pierden más de la mitad | 1,18 % | 0,59 % | la mitad |
| Notas que se quedan sin motivo | 2 | 1 | −1 |
| Intervención del corrector (sin tildes) | 2,01 % | 1,92 % | −0,10 pp |
| **Notas que superan la ventana del modelo** | **0** | **2** | **peor** |
| **Recorte medio del texto** | **8,69 %** | **2,85 %** | **recorta menos** |

Cómo reproducirla:

```
git worktree add <ruta> 35ae86a
# copiar salidas/lexico_clinico.json, lexico_casing.json, clasificador_frases.joblib
# y datos/lexicos/corpus_frecuencia.tsv al worktree
# correr el mismo lote de notas en los dos arboles y comparar con:
python -m NLP.evaluacion.calidad --csv <antes.csv> --comparar <ahora.csv>
```

## 2. Las cinco notas de control, antes y ahora

El propietario aportó cinco notas reales que son los casos difíciles. Están en
`datos/evaluacion/muestra_control.csv` y se pasan por el pipeline en cinco segundos con
`python -m NLP.evaluacion.control`. **Es la herramienta más útil que salió de la sesión.**

| Nota | Antes | Ahora | Veredicto |
|---|---|---|---|
| C-001 epistaxis + bloque de la EPS | quita el bloque | quita el bloque y marca `NEG_epistaxis` | mejora pequeña |
| C-002 nota mínima `sangre mucho` | sobrevive | idéntico | igual |
| C-003 `cordada` en mano derecha | `cortada (herida cortante)...` | idéntico | igual |
| C-004 sangrado + adenocarcinoma | limpio | **deja entrar `refiere hospitalización reciente`** | **peor** |
| C-005 diarrea, fiebre, vómito, tos | **pierde `diarrea`** | conserva `diarrea` y marca la negación, pero arrastra `menor de edad la cual desde el fin de semana con esta con` | mejor en lo clínico, peor en la limpieza |

**Balance: 2 idénticas, 1 mejora pequeña, 1 peor, 1 mixta.**

## 3. Lo que sí se arregló (fallos reales, no mejoras de calidad)

Son la parte defendible de la sesión. Ninguno se ve en las métricas agregadas, y todos eran
reales:

| Fallo | Evidencia | Dónde |
|---|---|---|
| **La fase 1 destruía cifras**: `1000mg` → `100mg`, `1000cc` → `100cc`, documentos que perdían un dígito | una regla para `holaaaaa` aplicaba también a los dígitos; 8 casos en 9.311 notas, dos de ellos dosis | `decisiones/2026-09-16-cifras.md` |
| **El corrector inventaba términos clínicos**: `paraclínicos` → `paralíticos` en 6 notas | `paralíticos` es una entrada real del léxico (CIE-10) con frecuencia **cero** en el corpus; el 86,3 % del léxico no aparece nunca en las notas | `decisiones/2026-09-16-E4.6.md` |
| **El clasificador de frases convertía todos los puntos en comas** | desactivaba el filtro institucional aguas abajo: la propaganda de la EPS llegaba entera al texto final | corregido en `reduccion/_quitar_clasificador` |
| **La reparación completa nunca había terminado** | abortaba al final, tras 90 minutos, por `OID` duplicados que el contrato declara posibles | `bitacora/2026-09-16-E0.2.md` |
| **`embedding/estructurar.py` estaba roto** | `AttributeError` al importarse; nunca arrancaba | corregido en `embedding/rutas.py` |
| **`requisitos.py` recomendaba el comando que destruye datos curados** | el verificador que se corre al abrir sesión aconsejaba `python -m NLP.reduccion.frases`, que regenera `frases_etiquetadas.csv` | corregido |
| **Dos modelos en uso con licencia mal registrada** | `es_core_news_md` es GPL-3.0 (no MIT) y `qwen2.5:3b` es **no comercial** (no Apache-2.0), verificado en el artefacto instalado | `decisiones/2026-09-16-licencias-modelos-en-uso.md` |
| **Datos de pacientes en la documentación** | una decisión citaba la historia clínica de un paciente identificable por su OID | anonimizado |

## 4. Lo que esta sesión ROMPIÓ y hay que deshacer

> **Corregido el 2026-09-17.** La causa no era la que esta tabla suponía, y la
> localización está medida en `decisiones/2026-09-17-freno-por-aporte-unico.md`: toda la
> regresión del recorte vive dentro de `reduccion._quitar_clasificador()`, en el freno por
> densidad clínica. Los otros tres frenos que esta tabla señala no tienen parte en ella.
> Ver §10.

| Regresión | Causa probable | Qué hacer |
|---|---|---|
| **El recorte pasó del 8,69 % al 2,85 %** | al proteger el texto para que el corrector no lo destruyera, el sistema quedó demasiado conservador y deja pasar relleno | revisar los frenos clínicos añadidos: `coherencia.RESPALDO_POR_CORPUS`, `ERRATA_SOLO_SIN_RESPALDO`, `REVERTIR_MISMO_LEMA` y el freno de `_quitar_clasificador` |
| **2 notas superan la ventana del modelo** (antes 0) | consecuencia de lo anterior, más los prefijos `NEG_` que alargan el texto | medir con `calidad.py`; si se mantiene la negación, acortar por otro lado |
| **C-004 deja entrar `refiere hospitalización reciente`** | `RE_REPORTE` no lo atrapa en esa posición | caso concreto y reproducible en la muestra de control |

**Recomendación: antes de añadir nada, medir cada bandera nueva con la muestra de control y
apagar la que no se gane su sitio.** Todas están tras bandera y documentadas.

## 5. Lo que NO se resolvió, que es el objetivo del proyecto

El propietario pidió un sistema que **corrija las notas y extraiga solo el contexto
importante del motivo de consulta**. Eso no se logró, ni antes ni ahora:

- **El sistema apenas extrae.** Recorte medio del 2,85 %: deja pasar el texto casi entero y
  lo llama motivo de consulta. Sobrevive relleno como «anoche paso muy mala noche» o
  «menor de edad la cual desde el fin de semana con esta con».
- **16,7 % de las notas se quedan con menos de 3 palabras.** No se ha investigado si es
  porque la nota no decía más o porque se recortó de más.
- **El corrector sigue tocando el 49,7 % de las notas.** El objetivo del plan era ≤ 0,1 %
  de intervención sobre texto correcto. La distancia sigue siendo de dos órdenes de
  magnitud.
- **68 apariciones de palabra real sustituida por otra palabra real** siguen vivas:
  `álgica → alérgica`, `urente → urgente`, `maluca → mala`, `cuncho → cinco`. La señal de
  frecuencia llegó a su techo; hace falta léxico propio y revisión humana.
- **La normalización conceptual (fase 6) cubre el 21 %** cuando el criterio era el 80 %.

## 6. Qué falló del método, para no repetirlo

1. **Se verificó sobre 9.311 notas cuando bastaban 300.** Varias corridas de una hora para
   descubrir cosas que la muestra de control dice en cinco segundos. La muestra pequeña
   llegó al final de la sesión; debió ser lo primero.
2. **Se midió contra una línea base corrupta.** Comparar contra un CSV mal generado hace que
   cualquier cambio parezca una mejora. La comparación válida es código contra código con
   los mismos artefactos.
3. **Se arreglaron fallos sin comprobar primero que el fallo fuera el que se creía.** El
   caso peor: se culpó a `_quitar_institucional` de 189 pérdidas usando una herramienta de
   diagnóstico (`reduccion.diagnosticar`) que **no ejecutaba el mismo orden de pasos que la
   corrida real**. El arreglo consiguiente resultó inútil y hubo que revertirlo.
4. **El plan orientó el esfuerzo a proteger el texto, no a extraerlo.** De sus 53 ítems, la
   mayoría van de no dañar. Casi ninguno ataca la pregunta de qué parte de la nota es el
   motivo de consulta.
5. **Demasiado paralelismo.** Se lanzaron hasta 11 agentes a la vez; dos oleadas murieron
   por límites de sesión con el trabajo a medias, y varios se pisaron editando los mismos
   archivos.

## 7. Lo que queda construido y sirve

| Herramienta | Para qué | Comando |
|---|---|---|
| **Muestra de control** | ver en 5 s qué hace el pipeline con los casos difíciles | `python -m NLP.evaluacion.control` |
| **Informe de calidad** | cifras agregadas de un CSV, y comparar dos versiones | `python -m NLP.evaluacion.calidad --csv A --comparar B` |
| **Tabla de pares** | qué está cambiando el corrector, palabra por palabra | `python -m NLP.evaluacion.pares` |
| **120 pares juzgados a mano** | conjunto de control para medir cualquier cambio del corrector | `datos/evaluacion/pares_juzgados.csv` |
| **38 pruebas de regresión** | incluye salida byte-idéntica de las fases 1–5 | `python -m pytest NLP/tests -q` |
| **Métricas del corrector** | F0.5, intervención, CER/WER, κ de Cohen | `python -m NLP.evaluacion.metricas` |
| **Corpus autoinducido** | 6.779 pares con su forma correcta conocida | `salidas/evaluacion/autoinducido.csv` |
| **Migrador de caché** | subir versión del corrector sin recalcular 20 horas | `python -m NLP.nucleo.migrar_cache` |
| **Paridad documental** | que ningún archivo quede sin documentar | `python -m NLP.evaluacion.paridad_docs --estricto` |
| **Descargador con manifiesto** | recursos externos con sha256 y licencia verificados | `python -m NLP.recursos.descargar` |

Más 33 bitácoras y 32 decisiones medidas en `bitacora/` y `decisiones/`, cada una con sus
comandos y su salida literal.

## 8. Por dónde empezar la próxima sesión

En este orden, y midiendo con la muestra de control después de cada paso:

1. **Deshacer las regresiones de §4.** Recuperar el nivel de recorte anterior sin volver a
   destruir texto. Es un problema de calibración de frenos, y todos están tras bandera.
2. **Atacar la extracción, que es el objetivo real.** Hoy nadie decide qué parte de la nota
   es el motivo: se quitan bloques enumerados y sobrevive el resto. Las dos vías que la
   sesión dejó preparadas y sin explotar son el nivel 2 de la fase 6
   (`carmen-symptemist`, CC-BY-4.0, encuentra mención clínica en el 91,3 % de las notas
   largas) y el conjunto de control para medir si extraer de verdad mejora o empeora.
3. **Ampliar la muestra de control** con cada caso nuevo que aparezca. Cinco notas ya
   destaparon un fallo que 9.311 no habían destapado.
4. **No añadir técnicas nuevas hasta que 1 y 2 estén resueltos.** El repositorio ya tiene
   más banderas de las que nadie ha medido juntas.

## 9. Estado del dato

- `salidas/triage_limpio.csv` (9.311 notas) está **reparado con el corrector v5** y aplicado
  el 16/09 a las 13:54. La versión anterior quedó en
  `salidas/triage_limpio_20260916-135449.csv`.
- **El código actual es la v6** (canal ruidoso) más la regla de mismo lema y la negación
  activada, **que no se han aplicado al CSV**. Es decir: el CSV en disco no corresponde
  exactamente al código en disco. Para alinearlos: `python -m NLP.reparacion.reparar` y
  luego `--aplicar` (`OPERACION.md` §3.10).
- `embedding/salidas/` se revectorizó el 16/09 a las 14:10 contra el CSV v5.
  `clustering/salidas/` **no se tocó**: sigue siendo del 15/09.

## 10. Sesión del 2026-09-17: comparación contra el CSV del 11/09

El propietario aportó `triage_limpio_antiguo.csv` (11/09, 6.501 notas) y pidió comparar,
nota a nota, cómo resolvía cada sistema. Es la comparación que esta sesión no había hecho:
**6.501 notas con el mismo `OID` y el mismo `texto_original` byte a byte**, mucho más
grande que las 300 de §1 y que las 5 de §2.

### Qué dijo la comparación

De las 6.501, **2.011 (30,9 %) dan un `texto_embedding` distinto**. Repartidas:

| | notas |
|---|---|
| el sistema nuevo rescata terminología que el antiguo perdía | 322 |
| el antiguo conserva terminología que el nuevo pierde | 37 |
| misma terminología en los dos, pero el **antiguo deja menos relleno** | 1.195 |
| misma terminología, el **nuevo** deja menos relleno | 344 |

Es decir: el nuevo gana en retención 9 a 1, y el antiguo gana en limpieza 3,5 a 1. Los dos
sistemas eran mejores que el otro en cosas distintas, que es exactamente lo que el
propietario veía.

### Los dos fallos que salieron, y su arreglo

1. **La regresión del recorte no estaba donde §4 decía.** Corriendo cada versión del
   recortador sobre la misma entrada, el `_quitar_clasificador` del 11/09 reproduce las
   cifras del 11/09 exactamente; todos los demás patrones de la fase 5 son idénticos entre
   las dos versiones. El responsable es el freno por densidad clínica, que salva un tramo
   administrativo entero en cuanto el 40 % de sus palabras está en el léxico — y el léxico
   da por clínicas `salud`, `nivel` o `atención`. Sustituido por un freno por **aporte
   único**: el tramo se tira salvo que traiga terminología que no esté en el resto de la
   nota. Resultado sobre las 6.501: retención 0,9806 (antiguo 0,9598, nuevo 0,9736) y
   recorte 0,1504 (antiguo 0,1555, nuevo 0,1249). Domina a los dos.
   → `decisiones/2026-09-17-freno-por-aporte-unico.md`.

2. **El guardián de cifras dejaba partir la cifra en dos.** `39+5` → `39+ 5`,
   `glasgow 15/15` → `glasgow 15/ 15`, `22/04/2025` → `22/ 04/ 2025`. 250 notas de 9.311 en
   el CSV nuevo contra 3 en el antiguo, y las 3 del antiguo ya venían así en el original.
   `mismas_cifras()` comparaba los grupos de dígitos, que el reemplazo conserva, y no veía
   el espacio. → `decisiones/2026-09-17-cifras-partidas.md`.

### Lo que sigue abierto

- **El CSV en disco no lleva ninguno de los dos arreglos.** Hay que decidir si se regenera.
  La fase 5 sola se puede rehacer desde `texto_normalizado` en segundos; el arreglo de
  cifras exige volver a pasar la fase 2. Los dos cambian `texto_embedding`, así que aplican
  el gate de `PLAN.md` §7: revectorizar y `python -m clustering --validar`.
- **3,1 puntos de recorte que no son de la fase 5.** El CSV del 11/09 recorta el 18,68 % y
  la fase 5 del 11/09, sobre la entrada de hoy, solo el 15,55 %. La diferencia viene de las
  fases 1–3 y no se ha investigado.
- Sigue en pie §5 entero: el sistema recorta, no extrae.

## 11. Sesión del 2026-09-17 (tarde): atacar la extracción con un modelo local

### Por qué se hizo

§5 lleva dos sesiones diciendo lo mismo: **el sistema recorta, no extrae.** Y §8 ponía la
extracción como segunda prioridad. El propietario decidió atacarla por la vía que §8 no
había considerado: un modelo de lenguaje local que **no recorte la nota, sino que la
entienda y la reescriba**.

El encargo tiene una exigencia que va más allá de extraer. Si la parte importante de la
nota dice `doolr gral`, quedarse con ese tramo no sirve de nada: el embedding y el
clustering necesitan texto entendible. Y un colombianismo como `fuego` no se agrupa nunca
con `herpes labial` porque no comparten ni una letra. Por eso el objetivo es
**interpretar y estandarizar**, no seleccionar.

Restricción heredada del `CLAUDE.md`: **no hay GPU**. La máquina es un i7-8550U de 4
núcleos con 16 GB de RAM, sin GPU utilizable. El techo práctico son modelos de 8B
cuantizados a Q4 (~5 GB). Todo corre con Ollama en localhost; **ninguna nota sale de la
máquina**.

### El banco de pruebas

`NLP/banco_triage_50.csv`. **50 notas reales del corpus**, elegidas por poder discriminante
y trazables por `OID`, con su `salida_esperada`, la trampa que tiende cada una y un campo
`confianza_clinica`. 13 estratos, de 6 a 1.434 caracteres.

La primera versión del banco la escribió Claude inventando frases; el propietario la
rechazó por demasiado limpia y sin colombianismos. **Las notas inventadas no valen: el
corpus ya contiene el habla real.** De las 50, 49 son reales (7 aportadas directamente por
el propietario) y **una sola es sintética**, a propósito: el corpus tiene tres apariciones
de `fuego` y las tres son `arma de fuego`, ninguna es el fuego labial. T-11 y T-12 son esa
pareja, y son la trampa central del banco: un modelo con la mano suelta para parafrasear
convierte a un herido de bala en un herpes.

### Los siete modelos, y por qué ganó uno

Se evaluaron con **prompt idéntico**, cambiando solo el modelo:

| Modelo | Tamaño | Resultado |
|---|---|---|
| `qwen3:8b` | 5,2 GB | **elegido** |
| `qwen3:4b`, `qwen3:1.7b` | 2,5 / 1,4 GB | por debajo de 8b |
| `medgemma1.5:4b` | 3,3 GB | descartado |
| BioMistral 7B (GGUF) | 4,4 GB | descartado |
| Apollo2 7B (GGUF) | 4,7 GB | descartado |
| `qwen2.5:3b-instruct` | 1,9 GB | línea base; **acierta 3 de 30** |

La línea base sirve de piso y dice cuánto aporta subir de tamaño: devolvió `sin motivo
clinico` en 16 de 30 notas, y solo 2 eran correctas. Las otras 14 —epistaxis, gestante de
38 semanas, rectorragia con adenocarcinoma, nota pediátrica, y `PACIENTE HERIDO POR ARMA DE
FUEGO`— habrían desaparecido de la serie diaria en silencio.

**Los modelos médicos perdieron contra el generalista multilingüe**, como se había
anticipado: están entrenados sobre literatura biomédica en inglés, y el problema difícil
aquí no es saber medicina, es saber que `chuzones` es dolor punzante. Eso es español de
Caldas.

### Lo que costó el prompt, y la lección que dejó

Se probaron seis versiones. La cronología importa porque **casi todas empeoraron**:

| | Qué se intentó | Qué pasó |
|---|---|---|
| **v1** | reglas numeradas y cuatro pares de ejemplo | la buena. Respuestas cortas y contenidas |
| v2 | quitar los ejemplos, explicar rol y propósito | ganó en el bloque institucional (`epistaxis`, no `sangrado nasal`) pero volvió locuaz al modelo: inventó `posible fractura de brazo izquierdo` sobre una nota que solo dice `ME CAI`, y `parto de pretérmino` en una gestante de 38 semanas |
| v3 | v2 con la brevedad de v1 y una revisión final | quitó las invenciones grandes, pero 5 de 7 alucinaciones eran la misma: rellenar una localización que la nota no daba |
| v4 | sección dedicada contra eso | **peor**: `ESTOY BROTADA` salió como `dolor abdominal` |
| — | **vuelta a v1 por decisión del propietario** | |
| v1.1 | v1 + 5 reglas contra los fallos medidos | |
| v1.2 / v1.3 | v1.1 + acceso a los diccionarios | actual |

> **La lección, que conviene no volver a aprender:** *cualquier palabra concreta escrita en
> el prompt acaba apareciendo en las respuestas, se ponga como ejemplo o como prohibición.*
> En v1 el modelo copió literalmente el ejemplo `trauma por aplastamiento en dedo` sobre
> una nota que hablaba de un balón. En v2 se pegó a la muletilla `sin especificar`. En v4
> escribí `dolor abdominal` como ejemplo de lo que **no** había que responder, y el modelo
> empezó a responder `dolor abdominal`. Por eso las reglas de v1.1 hablan de categorías
> —una parte del cuerpo, un lado, una causa— y **no nombran ni un solo término clínico**.

El segundo aprendizaje: **pedirle al modelo una revisión mental al final no funciona**. No
la ejecuta. Hay que convertirlo en restricción de construcción o en dato que se le entrega.

### Darle herramientas en vez de dejarlo solo

Es el cambio con más recorrido de la sesión. En vez de pedirle al modelo que adivine el
habla local, **se le entrega lo que el proyecto ya sabe**, vía `NLP/glosario.py`: antes de
cada nota se le inyectan **solo las entradas de `diccionario_siglas.json` y
`diccionario_coloquial.json` que aparecen en esa nota concreta**. Nunca el glosario entero,
por la lección de arriba.

Se respetan las políticas que los propios diccionarios declaran: solo se expanden los
`_grupos_expandibles`, se bloquean las `_siglas_ambiguas` y se honran las listas `contexto`.
Eso último funciona: **T-12 recibe `fuego = herpes labial` porque la nota habla del labio, y
T-11 (`ARMA DE FUEGO`) no recibe nada.**

Los diccionarios se ampliaron con **43 expresiones caldenses** que no estaban (`chuzones`,
`entumida`, `brotada`, `popo`, `pipi`, `dolor bajito`, `cordada`, `picadas`, `un colorado`,
`se me durmió`…) y **8 erratas verificadas** en `correcciones_directas` (`motrada`→morada,
`cdolor`→dolor, `vitla`→vital, `onculta`→consulta…), que también se inyectan. Con eso, **33
de las 50 notas** reciben ayuda, frente a 24 antes de ampliar.

`cordada` entró al diccionario coloquial, no a las erratas, y con respaldo del propio
repositorio: `datos/evaluacion/muestra_control.csv` ya lo documentaba como *«colombianismo
por herida cortante»* en el `que_se_espera` de C-003.

### Hallazgo que afecta al pipeline, no solo al modelo

Se comparó `texto_original` contra `texto_corregido` en las notas difíciles del banco para
ver si convenía pasarle al modelo el texto ya corregido. **No conviene, y el motivo es un
fallo del corrector:**

| Original | Corrector | |
|---|---|---|
| `TENGO ENTUMIDA LA MANO` | `tengo **entubada** la mano` | adormecimiento → intubado |
| `PICADAS EN EL PECHO` | `**picaduras** en el pecho` | dolor punzante → picadura de insecto |
| `TENGO CDOLOR E CABEZA Y DIARREA` | `**color** e cabeza y diarrea` | se come la cefalea |
| `SE PUSO MOTRADA` | `moderada` | era «morada» |
| `PACIENTE QUE ONCULTA` | `oculta` | era «consulta» |
| `URGENCIA VITLA DE CHINCHINA, PACIENTRE… MEINTRA` | `vital de chinchiná, paciente… mientras` | **acierta** |

Es §5 otra vez («68 apariciones de palabra real sustituida por otra palabra real»), pero
con casos nuevos y concretos. **Meter estas palabras en el diccionario lo arregla en los dos
sitios a la vez**, porque ese diccionario es además la lista de «nunca corregir» del
corrector.

### Estado y retos abiertos

Lo medido hasta ahora es cualitativo y lo audita el propietario nota a nota; **no hay aún
una puntuación formal del banco**. Retos vivos, por orden de gravedad:

1. **La consistencia no la arregla ningún prompt.** `DOLOR BAJITO` y `TENGO MUCHO DOLOR
   BAJITO` son dos llamadas independientes y el modelo no recuerda qué contestó antes; las
   redacta distinto y el clúster se parte en dos. `dolor bajito` aparece 73 veces en el
   corpus. La salida tiene que pasar por un vocabulario cerrado **después** de generarse. Los
   cuatro pares de consistencia del banco (T-31/T-32, T-01/T-33, T-02/T-30) están para
   medirlo.
2. **Las negaciones se pierden.** T-26 perdió `sin dificultad respiratoria` en las cuatro
   versiones del prompt, aunque dos reglas distintas lo piden. Para triage importa: una
   negación explícita es lo que baja la prioridad de un caso.
3. **La medición de cuatro notas es circular.** Las equivalencias `dolor bajito` →
   hipogastrio, `chuzones` → dolor punzante, `picadas` → dolor punzante y `un colorado` →
   lesión eritematosa las propuso Claude, y son **las mismas que están puestas como
   `salida_esperada` en el banco**. Mientras un clínico no las valide, esas cuatro notas no
   miden si el modelo entiende, sino si sabe copiar del glosario. No cuentan como aciertos.
4. **`daño de estómago` está declarado como `dispepsia` en el diccionario y como `diarrea`
   en el banco.** Uno de los dos está mal; hay que decidirlo antes de puntuar T-19.
5. **Licencia de `qwen3:8b` sin verificar.** §3 dejó constancia de que `qwen2.5:3b` es **no
   comercial**, contra lo que estaba registrado. El modelo elegido hoy no se ha comprobado,
   y es el que iría a producción.
6. **La regla 13 es una apuesta con riesgo.** Le dice al modelo que descartar de menos es
   peor que descartar de más, para frenar los falsos `sin motivo clinico`. Este modelo ya ha
   demostrado tres veces que se pega a lo último que se le enfatiza. Al auditar, mirar
   primero T-24, T-25 y T-49, que son trámites de verdad: si inventan motivo, la regla 13 se
   quita.
7. **Ubicación de los archivos.** `banco_triage_50.csv` y `resultado_*.csv` están en la raíz
   de `NLP/` por petición expresa del propietario. Los `resultado_*` son salidas
   regenerables y, por la regla 2 del `CLAUDE.md`, corresponderían a `salidas/`. Decisión
   pendiente.

### Cómo se ejecuta

```
python -m NLP.correr_qwen3_8b
```

Imprime cada nota según la procesa y escribe `NLP/resultado_qwen3_8b.csv` **fila a fila**,
cerrando el archivo en cada una: se puede abrir en Excel mientras corre, y una corrida
interrumpida se reanuda donde iba. Unos 40-50 minutos las 50 notas. Las corridas nuevas se
añaden **debajo** de las anteriores, etiquetadas con la `VERSION` del prompt, para poder
comparar versiones dentro del mismo archivo.

No toca la base de datos: lee el banco en CSV y habla con Ollama en localhost.

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-16 | cierre | Primera versión: medición honesta antes/después, lo arreglado, lo roto, lo no resuelto y qué falló del método |
| 2026-09-17 | §4, §10 | Comparación contra el CSV del 11/09 sobre 6.501 notas; se localiza la regresión del recorte y se corrige, más el guardián de cifras |
| 2026-09-17 | §11 | Fase 7: banco de 50 notas reales, comparación de 7 modelos locales, elección de `qwen3:8b`, seis versiones de prompt y conexión de los diccionarios del proyecto al modelo |
