# Paquete `embedding`

Convierte la columna `frase_procesada` de la tabla `nota_triage` en vectores de
**SapBERT-es**, identificables por su `OID`. Eso es todo lo que hace.

No limpia, no corrige ortografía, no expande siglas y no recorta la nota: todo
eso ya pasó en `NLP/` y llega hecho en esa columna. Tampoco agrupa ni visualiza:
el clustering es la fase siguiente y vive fuera de aquí, para que probar un
parámetro de agrupamiento no obligue a volver a vectorizar.

```bash
# desde la raíz del repositorio
python -m embedding.vectorizar
python -m embedding.vectorizar --limite 500      # prueba corta
python -m embedding.vectorizar --estado          # qué hay guardado, sin tocar nada
python -m embedding.vectorizar --rehacer         # tira los vectores y empieza
python -m embedding.centinela                    # vectoriza según crece la tabla
python -m embedding.diagnostico                  # control de calidad antes de agrupar
```

| archivo | qué hace |
| --- | --- |
| `vectorizar.py` | orquesta la fase: lee la tabla, vectoriza lo que falta y escribe `embedding` |
| `fuente.py` | lee `nota_triage`, valida la columna, aparta las vacías y calcula huellas |
| `diagnostico.py` | las 7 pruebas de calidad de la matriz, antes de agrupar |
| `modelo.py` | el modelo y sus parámetros: cuál, qué ventana, qué pooling |
| `almacen.py` | la base DuckDB: guardar, saber qué falta y entregarlo al clustering |
| `centinela.py` | mantiene el almacén al día mientras `NLP/` sigue escribiendo |
| `comparar_modelos.py` | el banco de pruebas con el que se eligió el modelo |
| `rutas.py` | único sitio que sabe dónde vive cada archivo |

## La documentación está en `docs/`

| | |
| --- | --- |
| [`docs/MODELO.md`](docs/MODELO.md) | qué modelo, contra qué otros se midió, con qué números y qué **no** prueba esa medición |
| [`docs/ALMACEN.md`](docs/ALMACEN.md) | el esquema, las garantías de integridad y el contrato con `clustering/` |
| [`docs/CALIDAD.md`](docs/CALIDAD.md) | el control de calidad de los vectores y su último resultado |
| [`docs/DECISIONES.md`](docs/DECISIONES.md) | bitácora de lo descartado y por qué |
| [`docs/HANDOFF.md`](docs/HANDOFF.md) | qué se decidió en la última sesión y qué quedó pendiente |

## Este paquete es autónomo

No importa `NLP/`. Antes sí lo hacía, y el día que `NLP/` se reorganizó,
`embedding/` dejó de poder importarse siquiera. La frontera ahora es explícita
y de una sola dirección:

```
NLP/         escribe la tabla `nota_triage` en salidas/triage.duckdb
embedding/   lee esa tabla y escribe la tabla `embedding` en la misma base
clustering/  pide la matriz con embedding.almacen.cargar(), y nada más
```

Comparten el **archivo**, no el código: cada paquete es dueño de sus tablas y
ninguno escribe las del otro. Lo único común es la ruta, una constante en cada
`rutas.py`. Ver [`docs/ALMACEN.md`](docs/ALMACEN.md).

## El OID no entra en el vector, y aun así no se pierde

Es la pregunta que este paquete existe para contestar bien. El `OID` **nunca**
forma parte del texto que se vectoriza — metería ruido y no significa nada en
un espacio semántico. Vive en una tabla aparte y se une por llave:

```python
from embedding import almacen

textos, vectores, indice = almacen.cargar()
#  textos    fila, huella, texto, n_notas   (una fila por frase viva)
#  vectores  (n, 768) float32, ya normalizada
#  indice    OID, huella, fila              (una fila por nota)
```

La tabla tiene **una fila por nota**, con el `OID` como clave primaria. Y una
columna más, `huella`, que es el `sha256` de la frase con la que se calculó ese
vector. Hace dos cosas:

- **Detecta un vector caduco.** Si `NLP/` reprocesa una nota y devuelve otra
  frase, la huella deja de coincidir y se revectoriza sola. Sin ella el vector
  viejo seguiría pegado a la nota, en silencio.
- **Evita calcular dos veces lo mismo.** Al modelo se le pasa cada frase
  distinta una vez y el vector se copia a todas las notas que la comparten: 596
  notas son 479 llamadas. El vector queda repetido —disco sobra— y se calcula
  una sola vez, que es lo que cuesta.

La fecha vive en `nota_triage.fecha_triage` (`DIM_TRIAGE.HCTFECTRI`), así que
el cruce es directo:

```sql
SELECT n.fecha_triage, n.frase_procesada, e.vector
FROM nota_triage n JOIN embedding e USING (OID);
```

## Correr esto dos veces no cuesta nada

Es la propiedad que sostiene el diseño. La tabla `nota_triage` crece apendando
notas, y sin GPU (`torch` está instalado en su versión `+cpu`) revectorizar de cero cada
vez sería tirar tiempo para obtener los mismos números.

La segunda corrida sobre los mismos datos ni siquiera carga el modelo:
encuentra todo al día y sale.

## Qué hay en `salidas/`

Misma regla que en `NLP/`: `datos/` se edita a mano y se versiona, `salidas/` lo
escribe un script y está ignorado por git.

| archivo | contenido |
| --- | --- |
| `banco_frases.csv` | el set congelado con el que se comparan modelos |

El almacén no está aquí: vive en `salidas/triage.duckdb`, en la raíz, porque lo
comparte con `NLP/`.

## Si se corta a la mitad

Cada bloque entra en su propia transacción. Un corte deja el almacén en el
último bloque completo, nunca a medias, y la corrida siguiente retoma por las
huellas que falten. No hay que limpiar nada a mano.

Esto sustituye a toda la maquinaria que hacía falta con el diseño anterior:
orden de escritura con `fsync`, reintentos de parquets a medio escribir y
comparación de tamaños y fechas antes y después de cada lectura.

## Si cambias el modelo

Cada fila guarda con qué modelo se calculó, en la columna `modelo`. Si la
tabla ya tiene vectores de otro, `vectorizar.py` se niega a continuar en vez de
mezclar dos espacios y producir una matriz mitad y mitad — un fallo que no da
ningún error y solo se nota en que el clustering sale raro. Para ese caso está
`--rehacer`.

Y antes de cambiarlo, mídelo: `python -m embedding.comparar_modelos --tabla`
compara contra los cuatro que ya se probaron, sobre las mismas frases. Los
`resultado_*.json` de esa comparación siguen en la raíz del paquete; los pesos
de los tres modelos descartados se borraron de la caché el 2026-09-21 y
volver a correrlos los descarga de nuevo (unos 6,5 GB).
