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

## Historial

| Fecha | Ítem | Cambio |
|---|---|---|
| 2026-09-16 | cierre | Primera versión: medición honesta antes/después, lo arreglado, lo roto, lo no resuelto y qué falló del método |
