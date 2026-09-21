# Bitácora de decisiones de `embedding/`

Lo que se descartó y por qué. Existe para que nadie vuelva a proponer algo que
ya se probó y no funcionó, y para poder reabrir una decisión sabiendo sobre qué
evidencia se tomó.

---

## 2026-09-21 · El modelo pasa de `bge-m3` a `SapBERT-es`

**Decidido con:** medición de cuatro candidatos sobre 787 frases.
**Detalle completo:** [MODELO.md](MODELO.md).

En una línea: gana en calidad y es 3,8× más rápido con la cuarta parte de los
parámetros. El orden de los cuatro resultó exactamente inverso a su tamaño.

Descartados y por qué: `jina-embeddings-v3` (licencia CC-BY-NC, uso
hospitalario), `PlanTL-GOB-ES/roberta-base-biomedical-clinical-es` (es un MLM,
no un codificador de frases).

---

## 2026-09-21 · La entrada pasa de `texto_embedding` a `texto_optimizado`

`NLP/` se reorganizó y su salida cambió de columna. Pero el cambio no fue solo
de nombre, y conviene que conste: la columna vieja **no estaba haciendo su
trabajo**. Medido sobre el vocabulario que dejó (9.142 frases):

- 98 frases eran literalmente antecedentes: `ap (antecedentes personales):
  niega; aa (antecedentes alergicos): niega`
- 803 contenían «niega»
- mediana 9 palabras, máximo 148

Es decir, la burocracia compartida que `corpus.py` decía evitar estaba entrando
igual. `texto_optimizado` tiene mediana 5 palabras y es la frase canónica que
genera el modelo, no un recorte por reglas.

**Consecuencia:** los vectores anteriores no se migraron. Estaban atados a una
columna que ya no existe y con contaminación medida; migrarlos habría sido
migrar basura con mejor formato.

---

## 2026-09-21 · El almacén pasa de cuatro archivos a una base DuckDB

**Detalle completo:** [ALMACEN.md](ALMACEN.md).

El motivo no fue comodidad sino integridad: la llave era la posición de la fila
dentro de un binario sin cabecera, y una desincronización entre los cuatro
archivos era indetectable. Ahora la llave es la huella del texto y la clave
foránea hace que el estado inconsistente sea imposible, no improbable.

**Se descartó MongoDB explícitamente.** Su búsqueda vectorial solo existe en
Atlas, que es nube; con notas clínicas reales eso viola la regla 1 de
`CLAUDE.md`. La decisión es de privacidad antes que técnica.

---

## 2026-09-21 (tarde) · El esquema se simplifica a dos tablas

Revisión pedida por el propietario sobre el diseño de la mañana. Tenía razón en
las tres objeciones, y el resultado es más simple.

**Antes:** cuatro tablas (`triage`, `frases`, `triage_frase`, `meta`) con
`modelo`, `prompt` y `creado` en la tabla de notas.
**Ahora:** dos tablas, nueve columnas.

| Objeción | Resolución |
|---|---|
| *«no entiendo qué hace `triage_frase`»* | era una tabla de enlace para no repetir el vector de una frase compartida. Ahorraba disco —que sobra: 290 MB para el corpus completo— a cambio de una tabla y un `JOIN` de más en toda consulta. Se quitó. El ahorro que sí importaba, el de **cómputo**, se conserva: se codifica por frase distinta y se copia el vector a cada nota |
| *«el modelo con el que se generó no me parece importante»* | cierto: un cambio de prompt obliga a rehacerlo todo, así que la columna servía para un caso que no se da. Se quitó de `nota_triage`. **Sí se conservó `modelo` en `embedding`**, que es otra cosa: dos vectores de modelos distintos no son comparables, y esa columna es lo que permite detectarlo |
| *«`creado` se puede confundir con la fecha real del triage»* | exacto, y es la trampa peligrosa: dos fechas donde solo una significa algo acaban con alguien agrupando por la equivocada. Se quitó |

**Lo que se añadió:** `fecha_triage`, que es lo que faltaba. Viene de
`DIM_TRIAGE.HCTFECTRI` y es la razón de ser del proyecto — sin ella no hay
serie temporal que cruzar con el clima. `procesar.py` ahora baja tres columnas
de la base clínica en vez de dos.

**La única columna que sobrevivió a la poda sin ser obvia es `huella`**, y se
ganó el sitio: detecta un vector calculado sobre una frase que ya cambió, cosa
que sin ella es invisible. Verificado cambiando una frase a mano y viendo que
`vectorizar` la recalculaba sola. Ver [ALMACEN.md](ALMACEN.md).

---

## 2026-09-21 · Se retira la vía de estructuración

Se borraron `estructurar.py`, `extraccion.py`, `negacion.py` y
`texto_embedding.py`, junto con `triage_estructurado.json/jsonl` (8,7 MB) y
`resumen_estructuracion.txt`.

Sacaban síntomas, negación y una frase canónica a partir de
`datos/catalogo_sintomas.json`. La idea se había descartado ya en su momento —
el recorte se resolvió mejor dentro de `NLP/` — pero el código seguía en disco,
se reparó el 2026-09-16 (commit `567e09e`) y tenía salidas frescas del mismo
día. Esa ambigüedad era peor que borrarlo.

**Sigue en el historial de git.** Vale la pena recordarlo cuando llegue el
momento de **ponerle nombre a cada cluster**: el lector de catálogo de
`extraccion.py` es justo lo que hace falta para etiquetar un grupo por su
síntoma dominante.

**Se perdió un parche sin commitear** de `texto_embedding.py` (20 líneas) que
adaptaba ese módulo a `texto_optimizado`. Su contenido útil se recuperó: era el
manejo del centinela `sin motivo clinico`, que ahora vive en
`fuente.py:SIN_MOTIVO`. Sin él se habrían vectorizado 4 notas administrativas
como si fueran un cuadro clínico.

`datos/catalogo_sintomas.json` **se queda**: lo usan `comparar_modelos.py` para
evaluar y `clustering/validacion.py` para verificar. `NLP/` ya no lo lee — tiene
su propia copia en `NLP/recursos/terminologia_clinica.json`, que evoluciona por
su cuenta.

---

## 2026-09-21 · El paquete deja de importar `NLP/`

`rutas.py` re-exportaba `TRIAGE_LIMPIO` y `CATALOGO_SINTOMAS` desde
`NLP/rutas.py`. El día que `NLP/` se reorganizó, `embedding/` dejó de poder
importarse siquiera: `AttributeError: module 'NLP.rutas' has no attribute
'CATALOGO_SINTOMAS'`. El paquete entero estaba caído y nada lo señalaba.

La frontera ahora es explícita y de una sola dirección:

```
NLP/         escribe la tabla nota_triage en salidas/triage.duckdb
embedding/   lee esa tabla y escribe la tabla embedding en la misma base
```

Comparten el **archivo**, no el código: cada paquete es dueño de sus tablas y
ninguno escribe las del otro. Lo único común es la ruta, declarada como
constante en cada `rutas.py`.

---

## Sin decidir

- **Cuánto ahorra deduplicar a escala.** Con el corpus actual son 596 notas →
  479 frases distintas: 19,6 % menos llamadas al modelo. Debería subir con el
  corpus completo (las frases canónicas se repiten más cuanto más corpus hay),
  pero está sin medir.
- **Afinar el modelo.** El estudio de CodiESP obtiene F1 0,709 afinando un
  bi-encoder con negativos duros, muy por encima de cualquier modelo de estante.
  Es el camino si `SapBERT-es` se queda corto.
- **Nombrar los clusters.** Ver arriba: el código borrado tiene la pieza.
