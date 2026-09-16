"""
Rutas del paquete embedding. Unico sitio que sabe donde vive cada archivo.

MISMA REGLA QUE EN NLP/
    datos/    se edita a mano y se versiona.
    salidas/  lo escribe un script y esta ignorado por git. Si se borra, se
              regenera corriendo vectorizar.py otra vez (aunque cueste horas).

QUE HAY EN salidas/
    vectores.f32       la matriz de embeddings en crudo, float32, sin cabecera.
                       Un archivo plano y no un .npy porque este paquete APENDE:
                       cada corrida agrega solo los textos nuevos al final, y a
                       un .npy no se le puede agregar una fila sin reescribirlo
                       entero. Con un binario plano es un open(..., "ab") y se
                       lee despues con np.memmap sin cargarlo en RAM.
    vocabulario.parquet  un renglon por texto distinto ya vectorizado, en el
                       mismo orden que las filas de vectores.f32. Es el indice
                       que dice que hay dentro de la matriz.
    indice.parquet     un renglon por fila del CSV: OID -> fila de la matriz.
                       Este SI se reescribe entero en cada corrida, porque es
                       barato de recalcular y es lo que consume la fase de
                       clustering para juntar cada OID con su vector.
    manifiesto.json    con que modelo y que parametros se lleno la matriz.
    sin_texto.csv      los OID que llegaron sin texto_embedding y quedaron
                       fuera. Se registran para que no desaparezcan en silencio.

POR QUE EL VOCABULARIO Y EL INDICE SON DOS ARCHIVOS
    El mismo motivo de consulta se repite muchisimo: sobre la corrida de 28.095
    notas habia 19.821 textos distintos. Vectorizar por texto distinto y no por
    fila ahorra cerca del 30% del trabajo, que sin GPU es la diferencia entre
    una tarde y una manana. El vocabulario guarda el vector una sola vez y el
    indice reparte esa fila entre todos los OID que comparten el texto.
"""

from pathlib import Path

from NLP import rutas as rutas_nlp

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"

# entrada: la deja NLP/procesar.py con la columna texto_embedding ya calculada
TRIAGE_LIMPIO = rutas_nlp.TRIAGE_LIMPIO

# El catalogo vive en embedding/datos/ pero lo declara NLP/rutas.py, que es el
# unico sitio que lo conoce; aqui se re-exporta igual que TRIAGE_LIMPIO. Sin
# esta linea, extraccion.py fallaba con AttributeError y estructurar.py no
# arrancaba. Mover el archivo a NLP/datos/ es E6.4.
CATALOGO_SINTOMAS = rutas_nlp.CATALOGO_SINTOMAS

# artefactos generados por vectorizar.py
VECTORES = SALIDAS / "vectores.f32"
VOCABULARIO = SALIDAS / "vocabulario.parquet"
INDICE = SALIDAS / "indice.parquet"
MANIFIESTO = SALIDAS / "manifiesto.json"
SIN_TEXTO = SALIDAS / "sin_texto.csv"

SALIDAS.mkdir(exist_ok=True)
