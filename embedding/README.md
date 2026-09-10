# Paquete embedding — fase 6

Convierte la columna `texto_embedding` de `NLP/salidas/triage_limpio.csv` en
vectores de `bge-m3`, identificables por su `OID`. Eso es todo lo que hace.

No limpia, no corrige ortografia, no expande siglas y no recorta la nota: todo
eso ya paso en `NLP/` y llega hecho en esa columna. Tampoco agrupa ni visualiza:
el clustering es la fase siguiente y vive fuera de aqui, para que probar un
parametro de agrupamiento no obligue a volver a vectorizar.

```bash
# desde la raiz del repositorio
python -m embedding.vectorizar
python -m embedding.vectorizar --limite 500      # prueba corta
python -m embedding.vectorizar --csv "D:\ruta\a\otro_triage_limpio.csv"
python -m embedding.vectorizar --rehacer         # tira lo guardado y empieza
```

| archivo | que hace |
| --- | --- |
| `vectorizar.py` | orquesta la fase: lee el CSV, vectoriza lo que falta y escribe las salidas |
| `corpus.py` | lee el CSV, valida la columna, aparta los vacios y decide que falta |
| `modelo.py` | el modelo y sus parametros: cual, que ventana, que precision |
| `almacen.py` | guarda lo ya calculado y sabe decir que es nuevo |
| `rutas.py` | unico sitio que sabe donde vive cada archivo |

## Correr esto dos veces no cuesta nada

Es la propiedad que sostiene todo el diseno. `triage_limpio.csv` va a crecer
apendando notas, y sin GPU (`torch` esta instalado en su version `+cpu`)
revectorizar de cero cada vez seria tirar horas para obtener los mismos numeros.

La llave del almacen es **el texto**, no el `OID`. Eso da dos cosas a la vez:

- **Ahorro.** El mismo motivo de consulta se repite muchisimo. Sobre la corrida
  de 28.095 notas habia 19.821 textos distintos: un 30% menos de trabajo.
- **Correccion.** Si `NLP/` mejora y una nota vieja cambia de texto, cambia su
  huella, y se vectoriza sola. Con llave por `OID` el vector viejo seguiria
  pegado a esa nota aunque ya no le corresponda.

La segunda corrida sobre los mismos datos ni siquiera carga el modelo: encuentra
todas las huellas y solo rehace el indice.

## Que hay en `salidas/`

Misma regla que en `NLP/`: `datos/` se edita a mano y se versiona, `salidas/` lo
escribe un script y esta ignorado por git.

| archivo | contenido |
| --- | --- |
| `vectores.f32` | la matriz en crudo, `float32`, un vector por texto distinto |
| `vocabulario.parquet` | que texto es cada fila de la matriz |
| `indice.parquet` | `OID` → fila, un renglon por nota del CSV |
| `manifiesto.json` | con que modelo y parametros se lleno la matriz |
| `sin_texto.csv` | los `OID` que quedaron fuera por venir sin texto |

`vectores.f32` es un binario plano y no un `.npy` porque este paquete **apende**:
cada corrida agrega solo lo nuevo al final, y a un `.npy` no se le puede agregar
una fila sin reescribirlo entero. Se lee con `np.memmap`, sin cargarlo en RAM.

## Como se consume

```python
from embedding import almacen

indice, matriz = almacen.cargar()          # o cargar(oids=[...])
vectores = matriz[indice["fila"].to_numpy()]   # un vector por nota, en orden
```

Ese paso es el que reparte la fila unica de un texto repetido entre todos los
`OID` que lo comparten. La fecha (`HCTFECTRI`) no vive aca a proposito: se junta
por `OID` cuando haga falta, en la fase de clustering.

## Si se corta a la mitad

El orden de escritura es siempre el mismo: primero los vectores al final del
binario con `fsync`, y solo despues el vocabulario que dice cuantos hay. Un corte
deja como mucho vectores de sobra al final, nunca un vocabulario prometiendo
filas que no existen. La corrida siguiente los ignora o los pisa, y lo que se
perdio se recalcula porque su huella vuelve a faltar. El punto de control es cada
`BLOQUE` textos (2.000 por defecto, el mismo valor que usa `NLP/procesar.py`).

## Si cambias el modelo

`modelo.identidad()` — cual, que ventana, normalizado y precision — entra en el
manifiesto. Si no coincide con lo guardado, `vectorizar.py` se niega a continuar
en vez de apendar vectores que viven en otro espacio y producirian una matriz
mitad y mitad. Para ese caso esta `--rehacer`.

El ajuste que mas tiempo ahorra es `LONGITUD_MAXIMA = 128`: `bge-m3` trae 8192
de fabrica y el costo crece con el cuadrado de la longitud. La columna
`texto_embedding` tiene mediana de 6 palabras y maximo de 60, asi que con 128
tokens entra el peor caso y sobra. Ese margen existe gracias a la fase 5 de
`NLP/`; sobre `texto_normalizado`, que llega a 405 palabras, habria que subirlo.

## Historia

Este paquete fue antes la "fase 4" de estructuracion: `estructurar.py`,
`extraccion.py`, `negacion.py` y `texto_embedding.py` sacaban sintomas, negacion
y una frase canonica desde `datos/catalogo_sintomas.json`. Esa idea se descarto
cuando el recorte de la nota se resolvio mejor dentro de `NLP/` (fase 5, columna
`texto_embedding`), y la carpeta se reoriento a lo que hace hoy.

Ese codigo sigue en el historial de git. Vale la pena recordarlo cuando llegue el
momento de **ponerle nombre a cada cluster**: el lector de catalogo de
`extraccion.py` es justo lo que hace falta para etiquetar un grupo por su sintoma
dominante.

`datos/catalogo_sintomas.json` no era parte de esa idea descartada y se queda: lo
leen `NLP/recursos/lexico.py` y `NLP/depuracion/depuracion.py`. Como sus unicos
consumidores estan en `NLP/`, su sitio natural es `NLP/datos/`, y moverlo alli
eliminaria lo unico que hoy hace que `NLP/` dependa de esta carpeta.
