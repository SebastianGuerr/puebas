# El almacén: esquema, garantías y contrato con `clustering/`

Todo vive en un archivo: **`salidas/triage.duckdb`**, en la raíz del repositorio.

## Por qué está en la raíz y no dentro de un paquete

Desde el 2026-09-21 la base la comparten dos:

| paquete | escribe | lee |
|---|---|---|
| `NLP/` | `nota_triage` | — |
| `embedding/` | `embedding` | `nota_triage` |
| `clustering/` | — | todo, vía `almacen.cargar()` |

Cada paquete es dueño de **sus** tablas y ninguno escribe las del otro. Meter
la base dentro de cualquiera de los dos haría falsa la propiedad del otro.

Eso no rompe la autonomía de `embedding/`: compartir un archivo de datos no es
lo mismo que importar código. `embedding/` sigue sin importar `NLP/`, y lo
único común es la ruta, declarada como constante en los dos `rutas.py`.

**Cuidado al borrar.** `embedding` se regenera en minutos; `triage` son horas de
generación contra la base clínica y **no se puede rehacer** sin volver a
consultarla, cosa que solo puede hacer el propietario. Por eso
`embedding.almacen.vaciar()` borra filas y nunca el archivo.

---

## El problema que resuelve

El diseño anterior guardaba la matriz en `vectores.f32` — un binario plano sin
cabecera — y la correspondencia en tres archivos aparte (`vocabulario.parquet`,
`indice.parquet`, `manifiesto.json`). **La llave era la posición**: el vector
`n` empezaba en el byte `n × dimensión × 4`.

Eso funciona hasta que deja de funcionar, y falla en silencio:

> Nada dentro de `vectores.f32` dice a qué texto pertenece cada vector. Si el
> binario y el índice se desincronizan — una escritura cortada, un cambio de
> dimensión, una compactación — se siguen leyendo 4.096 bytes perfectamente
> válidos que son de **otra frase**. No hay forma de detectarlo.

Que el código tuviera que defenderse con un orden de escritura preciso y
`fsync`, y que `clustering/corpus.py` comparara tamaños y fechas de los cuatro
archivos antes y después de cada lectura, era la señal de que la garantía era
una convención documentada y no una propiedad del sistema.

**Aquí la llave es la huella del texto**, que se deriva del propio dato.

| Escenario | Antes (posición) | Ahora (huella + DuckDB) |
|---|---|---|
| Borrar filas | sobreviven, pero dejan vectores huérfanos invisibles | `DELETE`, y la FK avisa si algo queda colgando |
| Reordenar / compactar | hay que reconstruir el índice entero | irrelevante: no hay orden |
| Migrar a otra base | exportar la posición y confiar | `COPY`; la llave viaja con el dato |
| Corte a mitad de escritura | quedan vectores de sobra al final | transacción: o entró o no entró |
| **Desincronización** | **indetectable** | **imposible: el motor la rechaza** |

## La posición no desaparece, se degrada

`almacen.cargar()` sigue devolviendo una columna `fila`, porque el clustering
trabaja con matrices y necesita saber qué renglón es cada texto. La diferencia
es que **esa fila se calcula en cada lectura y no se guarda nunca**.

Una posición es una comodidad válida en memoria. Como llave de persistencia es
lo que causó el problema.

## El esquema: dos tablas, nueve columnas

```sql
-- la escribe NLP/procesar.py. Son los TRES datos que se bajan de la base
-- clinica, mas el resultado de procesar el tercero.
CREATE TABLE nota_triage (
    OID              BIGINT PRIMARY KEY,   -- DIM_TRIAGE.OID
    fecha_triage     TIMESTAMP,            -- DIM_TRIAGE.HCTFECTRI, la fecha real
    frase_original   VARCHAR,              -- DIM_TRIAGE.HCTMOTCON, sin tocar
    frase_procesada  VARCHAR               -- lo que devolvió el modelo
);

-- la escribe embedding/vectorizar.py. Una fila por nota.
CREATE TABLE embedding (
    OID     BIGINT PRIMARY KEY REFERENCES nota_triage(OID),
    huella  VARCHAR NOT NULL,   -- sha256[:16] de la frase que se vectorizó
    modelo  VARCHAR NOT NULL,   -- con qué modelo se calculó este vector
    tokens  INTEGER,            -- largo real, para vigilar el truncamiento
    vector  FLOAT[768] NOT NULL -- normalizado a norma 1
);
```

`DIM_TRIAGE` tiene trece columnas. Las otras diez son nombre, segundo nombre,
apellidos, documento, edad, médico y códigos administrativos: dato
identificable de pacientes reales que no tiene por qué salir de la base
clínica. **`nota_triage` es la copia mínima que necesita el análisis.**

### El OID es una columna; nunca entra al vector

Es la pregunta que el paquete existe para contestar bien. Al modelo se le pasa
la frase y nada más — meter el OID dentro sería ruido sin significado en un
espacio semántico. Pero la **fila** lleva el OID, así que la fecha se consigue
con un `JOIN` y no hace falta nada más:

```sql
SELECT n.fecha_triage, e.vector
FROM embedding e JOIN nota_triage n USING (OID);
```

### Qué hace `huella`, la única columna que no se explica sola

Guarda el `sha256` de **la frase con la que se calculó ese vector**. Hace dos
cosas, y ninguna de las dos se puede hacer sin ella:

**1 · Detectar un vector caduco.** Si `NLP/` reprocesa una nota y el modelo
devuelve otra frase, el vector guardado deja de corresponderle. Sin la huella
eso es invisible: la fila tiene su OID y su vector, y nada dice que el vector
es de un texto que ya no existe. Con ella es una comparación:

```sql
WHERE e.huella <> sha256(n.frase_procesada)
```

Verificado el 2026-09-21: se cambió a mano la `frase_procesada` de un OID, se
volvió a correr `vectorizar`, y la fila se recalculó sola con la huella nueva.

**2 · No vectorizar dos veces lo mismo.** El mismo motivo se repite mucho: 596
notas son 479 frases distintas. Antes de llamar al modelo se agrupan las notas
pendientes por huella, se codifica cada texto **una** vez y el vector se copia
en todas las filas que lo comparten. El vector queda repetido —3 KB por fila,
unos 290 MB para el corpus completo— y a cambio se calcula una sola vez.

### Lo que se quitó, y por qué estaba de más

| Se quitó | Por qué |
|---|---|
| tablas `frases` + `triage_frase` | existían para no repetir el vector. Ahorraban disco, que sobra, a cambio de una tabla y un `JOIN` de más en toda consulta |
| tabla `meta` | guardaba la identidad del modelo. Ahora está en la columna `modelo` de cada fila, que es donde pertenece, y `SELECT DISTINCT modelo` es la misma comprobación |
| `nota_triage.modelo` / `.prompt` | decían con qué versión se generó cada frase. En la práctica un cambio de prompt obliga a rehacerlo todo, así que eran dos columnas repetidas 94.000 veces para un caso que no se da |
| `nota_triage.creado` | se confundía con `fecha_triage`, que es la que significa algo. Dos fechas donde solo una importa es una trampa esperando a que alguien agrupe por la equivocada |

## Las garantías, verificadas

Comprobado el 2026-09-21 contra la base real:

| Intento | Resultado |
|---|---|
| `INSERT INTO embedding` con un OID que no está en `nota_triage` | `Constraint Error: Violates foreign key constraint` |
| `DELETE FROM nota_triage` de una nota que tiene vector | `Constraint Error: ... is still referenced` |
| Dos vectores para el mismo OID | `Constraint Error: Duplicate key ... violates primary key` |
| Vectorizar con otro modelo sobre la tabla llena | `SystemExit` con el diagnóstico de qué cambió |

La última no la da el motor sino `almacen.comprobar_identidad()`. Mezclar
vectores de dos modelos produce una matriz mitad y mitad: no da ningún error, y
el único síntoma es que el clustering sale mal sin que nada diga por qué. Es el
fallo más caro de encontrar, así que se bloquea explícitamente. Para empezar de
cero: `python -m embedding.vectorizar --rehacer`.

## Cómo se consume

```python
from embedding import almacen

textos, vectores, indice = almacen.cargar()
#  textos    fila, huella, texto, n_notas   (una fila por frase VIVA)
#  vectores  (n, 768) float32, alineada con textos, ya normalizada
#  indice    OID, huella, fila              (una fila por nota)
```

`clustering/corpus.py` no abre la base por su cuenta: llama a esto. Es la única
frontera entre los dos paquetes.

**`cargar()` agrupa por frase distinta aunque la tabla guarde una fila por
nota.** HDBSCAN agrupa por densidad, y dos notas con la misma frase producen dos
puntos en la misma coordenada: un pico de densidad infinita que no corresponde a
ninguna estructura del corpus sino a que esa frase se repite. El vector es
idéntico en todas las filas que comparten huella, así que el `any_value()` de la
consulta es exacto y no una aproximación.

**Las frases huérfanas no existen.** Reprocesar una nota *actualiza* su fila; si
nadie usa una frase, no hay ninguna fila con esa huella.

## El cruce con la fecha, que es para lo que existe todo esto

`fecha_triage` es `DIM_TRIAGE.HCTFECTRI`: hora local de Manizales (UTC-5), sin
zona horaria declarada. Ver `clustering/fechas.py`.

```sql
-- una nota con su fecha y su vector
SELECT n.fecha_triage, n.frase_procesada, e.vector
FROM nota_triage n JOIN embedding e USING (OID);

-- la serie diaria
SELECT date_trunc('day', fecha_triage) AS dia, count(*) AS triages
FROM nota_triage GROUP BY 1 ORDER BY 1;
```

**Las notas migradas del CSV viejo no traen fecha**, porque el CSV no la tenía.
Se completan sin volver a llamar al modelo —la fecha son dos columnas, no
necesita al LLM— con:

```bash
python -m NLP.procesar --fechas
```

## Por qué DuckDB y no otra cosa

Con ~94.000 notas × 768 dimensiones × 4 bytes son **290 MB**: cabe
entero en RAM y un producto de matrices contra todo el corpus son segundos.
**No hay un problema de búsqueda vectorial aproximada**, que es para lo que
existen las bases vectoriales. Hay un problema de *join*: frase → OID → fecha →
serie diaria.

| Opción | Por qué no |
|---|---|
| `.f32` + parquet | lo que se acaba de sustituir |
| LanceDB | bien diseñado, pero sus ventajas (versionado, escala, multimodal) son para un problema más grande |
| SQLite + sqlite-vec | válido, pero guarda los vectores como BLOB y para agregar por fecha DuckDB es mucho mejor |
| **MongoDB** | **descartado por privacidad antes que por técnica**: necesita servidor, y su búsqueda vectorial solo existe en Atlas, que es nube. Con notas clínicas reales eso es exactamente lo que prohíbe `CLAUDE.md` |

Si algún día hicieran falta índices ANN, DuckDB tiene la extensión VSS con HNSW
y no habría que cambiar de almacén.

## Límites conocidos

- **Un solo escritor.** DuckDB no admite dos procesos escribiendo. Si el
  centinela y `vectorizar` coinciden, el segundo salta la pasada y reintenta.
  No es un error.
- **`salidas/` está ignorado por git**, igual que antes. La base se regenera
  con `python -m embedding.vectorizar`.
- **El tipo `FLOAT[768]` está fijado al crear la tabla.** Cambiar de modelo a
  otro de distinta dimensión obliga a `--rehacer`. Es deliberado: ver arriba.
