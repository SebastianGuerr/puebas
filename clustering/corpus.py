"""
La entrada: leer los embeddings ya calculados y dejarlos listos para agrupar.

DE DONDE SALEN
    De salidas/triage.duckdb, y solo a traves de embedding.almacen.cargar().
    Este modulo ya no abre archivos de ese paquete por su cuenta: antes leia
    los cuatro (manifiesto, vocabulario, indice y la matriz cruda con memmap),
    y eso obligaba a replicar aqui reglas que son de alla. Ahora la frontera
    es una funcion.

SE AGRUPAN LOS TEXTOS DISTINTOS, NO LAS NOTAS. ES LA DECISION CENTRAL.
    La tabla `embedding` guarda una fila por NOTA, pero almacen.cargar()
    devuelve una fila por FRASE DISTINTA. Lo comodo seria agrupar las notas
    tal cual vienen de la tabla. Seria un error, y no por coste.

    HDBSCAN agrupa por densidad: mide a que distancia esta cada punto de sus
    vecinos y llama cluster a las zonas donde esa distancia es corta. Dos notas
    con el mismo texto producen DOS PUNTOS EN LA MISMA COORDENADA, a distancia
    cero una de otra. Son puntos superpuestos, un pico de densidad infinita que
    no corresponde a ninguna estructura del corpus sino a que esa frase se
    repite.

    El efecto es que las frases MUY frecuentes se vuelven nucleos artificiales
    y las frases raras -- que son la mayoria de los textos distintos -- caen
    como ruido a su alrededor. Se estaria agrupando por frecuencia y no por
    significado.

    Agrupando los textos distintos cada frase pesa una vez, la densidad mide
    vecindad semantica de verdad, y la frecuencia se recupera despues: cada
    cluster se reporta con su numero de notas (columna n_notas), que es lo que
    interesa para buscar patrones.

LAS FRASES HUERFANAS YA NO EXISTEN
    Antes el almacen apendaba y nunca borraba: si NLP/ mejoraba y una nota
    cambiaba de frase, el vector viejo se quedaba en la matriz sin que ningun
    OID lo reclamara, y habia que evitar agruparlo a mano.

    Con una fila por nota eso no puede pasar: reprocesar una nota ACTUALIZA su
    fila. Si nadie usa una frase, no hay fila con esa huella y no sale de la
    consulta.

LEER MIENTRAS EL PIPELINE ESCRIBE
    Esto era la parte mas delicada del modulo y ha desaparecido casi entera.
    Con cuatro archivos habia que garantizar que los cuatro describieran el
    MISMO instante: se comparaban tamanos y fechas antes y despues de leer, y
    se reintentaban los parquets a medio escribir. Una lectura partida podia
    juntar un indice viejo con un vocabulario nuevo y agrupar una mezcla de dos
    corridas.

    Con una base transaccional, una lectura o ve la corrida entera o no la ve.
    Lo unico que queda es el reintento por si el escritor tiene la base tomada
    en ese momento, que es una espera, no una inconsistencia.
"""

import time

from embedding import almacen, rutas as rutas_emb

REINTENTOS = 6
ESPERA = 1.5


def cargar(minimo_notas=1):
    """
    Devuelve la terna (textos, vectores, indice).

    textos    un renglon por frase distinta VIVA: fila, huella, texto, n_notas.
    vectores  matriz float32 alineada con textos, ya normalizada.
    indice    OID -> huella -> fila, para devolverle su grupo a cada nota.

    'fila' la genera el almacen en cada lectura y no esta guardada en ninguna
    parte: es el renglon de la matriz que se acaba de construir. La llave
    persistente es la huella. Ver embedding/docs/ALMACEN.md.

    Con minimo_notas se descartan las frases que aparecen menos de esa cantidad
    de veces. Por defecto no descarta nada: la cola larga es justo lo que
    interesa describir.
    """
    return almacen.cargar(minimo_notas=minimo_notas)


def firma():
    """
    Huella barata del estado del almacen, o None si todavia no existe.

    Sirve para saber si vale la pena recalcular el agrupamiento (lo usa el
    visor). Es tamano + mtime y no un hash del contenido porque leer la base
    entera para decidir si hay que leerla no tiene sentido.
    """
    try:
        estado = rutas_emb.BASE_DATOS.stat()
    except OSError:
        return None
    return (estado.st_size, estado.st_mtime_ns)


def instantanea(minimo_notas=1):
    """
    Como cargar(), reintentando si el escritor tiene la base tomada.

    Se conserva el nombre porque lo llaman barrido.py y corrida.py, pero ya no
    hace lo que hacia: la consistencia de la lectura la garantiza la
    transaccion, no este bucle. Lo unico que se reintenta aqui es el bloqueo,
    que es temporal por definicion -- DuckDB admite un solo escritor.
    """
    ultimo = None
    for _ in range(REINTENTOS):
        if firma() is None:
            ultimo = RuntimeError(
                "Todavia no existe salidas/triage.duckdb. "
                "Corre 'python -m NLP.procesar' y "
                "'python -m embedding.vectorizar'.")
            time.sleep(ESPERA)
            continue
        try:
            return cargar(minimo_notas=minimo_notas)
        except Exception as error:
            ultimo = error
            time.sleep(ESPERA)

    raise RuntimeError(
        f"No se pudo leer el almacen en {REINTENTOS} intentos: {ultimo}")


def repartir(textos, indice):
    """
    Devuelve el cluster de cada NOTA, deshaciendo la deduplicacion.

    Es la operacion inversa a la del docstring del modulo: se agrupo por texto
    distinto y aqui ese resultado vuelve a cada OID que comparte el texto. Es
    lo que hace que la salida se pueda cruzar por OID con la fecha de triage.

    El orden de columnas importa: 'ancla' primero porque es la columna con la
    que se construye la serie temporal. tema y cluster viajan al lado para
    poder bajar al detalle, pero el numero de tema NO es comparable entre
    corridas y el de ancla si. Ver anclas.py.
    """
    columnas = ["cluster", "texto"]
    if "tema" in textos.columns:
        columnas = ["tema"] + columnas
    if "ancla" in textos.columns:
        columnas = ["ancla"] + columnas
    mapa = textos.set_index("fila")[columnas]
    salida = indice.merge(mapa, left_on="fila", right_index=True, how="inner")
    return salida[["OID"] + columnas].reset_index(drop=True)
