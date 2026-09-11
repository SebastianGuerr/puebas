"""
La entrada: leer los embeddings ya calculados y dejarlos listos para agrupar.

SE AGRUPAN LOS TEXTOS DISTINTOS, NO LAS NOTAS. ES LA DECISION CENTRAL.
    embedding/ guarda un vector por TEXTO distinto y un indice que reparte esa
    fila entre todos los OID que comparten el texto. Lo comodo seria deshacer
    ese reparto (una fila por nota) y agrupar eso. Seria un error, y no solo
    por coste.

    HDBSCAN agrupa por densidad: mide a que distancia esta cada punto de sus
    vecinos y llama cluster a las zonas donde esa distancia es corta. Dos notas
    con el mismo texto producen DOS PUNTOS EN LA MISMA COORDENADA, a distancia
    cero una de otra. 'dolor abdominal' aparece 17 veces en las primeras 1.000
    notas: son 17 puntos superpuestos, un pico de densidad infinita que no
    corresponde a ninguna estructura del corpus sino a que esa frase se repite.

    El efecto es que las frases MUY frecuentes se vuelven nucleos artificiales
    y las frases raras -- que son el 93% de los textos distintos -- caen como
    ruido a su alrededor. Se estaria agrupando por frecuencia y no por
    significado.

    Agrupando los textos distintos cada frase pesa una vez, la densidad mide
    vecindad semantica de verdad, y la frecuencia se recupera despues: cada
    cluster se reporta con su numero de notas, que es lo que interesa para
    buscar patrones. De paso cuesta un 30% menos sobre el corpus completo.

LAS FILAS HUERFANAS
    La matriz de embedding/ APENDE y nunca borra: si NLP/ mejora y una nota
    cambia de texto, se vectoriza el texto nuevo y el viejo se queda en la
    matriz sin que ningun OID lo reclame. Sobre la corrida parcial medida habia
    1.179 filas en la matriz para 852 textos vivos: un 27,7% de la matriz eran
    fantasmas de versiones anteriores del CSV.

    Agruparlos meteria en los clusters frases que ya no existen en el corpus.
    Por eso aqui NUNCA se lee la matriz entera: se parte del indice, que es la
    unica fuente que dice que hay hoy, y se toman solo las filas que el indice
    reclama.

SE PUEDE LEER MIENTRAS EL PIPELINE ESCRIBE
    embedding/vectorizar.py reescribe indice.parquet entero en cada corrida, y
    una lectura puede caer justo en medio. Es un fallo transitorio y no un dato
    corrupto, asi que se reintenta en vez de abortar: la alternativa seria
    obligar a esperar a que termine una corrida de horas.
"""

import time

import numpy as np
import pandas as pd

from embedding import rutas as rutas_emb


def _leer_parquet(ruta, intentos=5, espera=1.5):
    """
    Lee un parquet que puede estarse reescribiendo en este instante.

    No distingue el fallo transitorio del archivo genuinamente roto, y no hace
    falta: si tras varios intentos sigue fallando, deja de ser transitorio y el
    error sube con su mensaje original.
    """
    for intento in range(intentos):
        try:
            return pd.read_parquet(ruta)
        except Exception:
            if intento == intentos - 1:
                raise
            time.sleep(espera)


def cargar(minimo_notas=1):
    """
    Devuelve la terna (textos, vectores, indice).

    textos    DataFrame con un renglon por texto distinto VIVO: fila (la de la
              matriz), texto y n_notas (cuantos OID lo comparten).
    vectores  matriz float32 alineada con textos, ya normalizada por bge-m3.
    indice    el OID -> fila original, para devolver el cluster a cada nota.

    Con minimo_notas se descartan los textos que aparecen menos de esa cantidad
    de veces. Por defecto no descarta nada: el 93% de los textos distintos son
    unicos y ahi es donde vive la cola larga del corpus, que es justo lo que
    interesa describir. La opcion existe para el caso contrario -- mirar solo lo
    que se repite -- y no para 'limpiar', que aqui seria tirar el corpus.
    """
    if not rutas_emb.MANIFIESTO.exists():
        raise SystemExit(
            "No hay embeddings todavia. Corre antes 'python -m embedding.vectorizar'.")

    indice = _leer_parquet(rutas_emb.INDICE)
    vocabulario = _leer_parquet(rutas_emb.VOCABULARIO)

    if indice.empty:
        raise SystemExit(
            "El indice de embedding/ esta vacio: todavia no hay ninguna nota "
            "vectorizada. Espera a que avance 'python -m embedding.vectorizar'.")

    # cuantas notas comparten cada fila de la matriz: es el peso del texto
    conteo = (indice.groupby("fila").size()
              .rename("n_notas").reset_index())

    textos = conteo.merge(
        vocabulario.reset_index().rename(columns={"index": "fila"})[["fila", "texto"]],
        on="fila", how="left")

    # Un texto sin entrada en el vocabulario significa que el indice apunta a
    # una fila que el vocabulario no tiene. No deberia pasar nunca -- el orden
    # de escritura de embedding/almacen.py lo impide -- pero si pasa hay que
    # verlo, no heredarlo callando.
    perdidos = int(textos["texto"].isna().sum())
    if perdidos:
        print(f"  aviso: {perdidos} fila(s) del indice no estan en el "
              f"vocabulario; se omiten")
        textos = textos.dropna(subset=["texto"])

    if minimo_notas > 1:
        textos = textos[textos["n_notas"] >= minimo_notas]

    textos = textos.sort_values("fila").reset_index(drop=True)

    matriz = np.memmap(
        rutas_emb.VECTORES, dtype=np.float32, mode="r",
        shape=(len(vocabulario), _dimension()))
    vectores = np.asarray(matriz[textos["fila"].to_numpy()], dtype=np.float32)

    return textos, vectores, indice


def _dimension():
    import json
    return json.loads(
        rutas_emb.MANIFIESTO.read_text(encoding="utf-8"))["dimension"]


def repartir(textos, indice):
    """
    Devuelve el cluster de cada NOTA, deshaciendo la deduplicacion.

    Es la operacion inversa a la del docstring del modulo: se agrupo por texto
    distinto y aqui ese resultado vuelve a cada OID que comparte el texto. Es lo
    que hace que la salida se pueda cruzar por OID con la fecha de triage.

    Van las dos columnas del resultado, tema y cluster. El cruce contra clima y
    calendario se hace por TEMA -- el cluster es demasiado fino para que una
    serie diaria tenga senal -- pero el cluster viaja al lado porque es lo que
    permite bajar al detalle de un tema sin rehacer la corrida.
    """
    columnas = ["cluster", "texto"]
    if "tema" in textos.columns:
        columnas = ["tema"] + columnas
    mapa = textos.set_index("fila")[columnas]
    salida = indice.merge(mapa, left_on="fila", right_index=True, how="inner")
    return salida[["OID"] + columnas].reset_index(drop=True)


# ==========================================================
# LEER MIENTRAS EL PIPELINE ESCRIBE
# ==========================================================
#
# _leer_parquet() de arriba resuelve el caso de UN archivo a medio escribir.
# Falta el otro, que es peor: los cuatro archivos de embedding/salidas/ tienen
# que describir el MISMO instante. vectorizar.py escribe primero los vectores,
# despues el vocabulario y al final el indice, asi que una lectura que caiga en
# medio puede juntar un indice viejo con un vocabulario nuevo y agrupar una
# mezcla de dos corridas.
#
# La defensa es mirar el tamano y la fecha de los cuatro archivos ANTES y
# DESPUES de leer: si cambiaron, la instantanea salio partida y se descarta. No
# hay bloqueo de archivos y no hace falta -- este paquete no escribe nada ahi,
# y el centinela corre cada 15 minutos, asi que reintentar cuesta segundos.

REINTENTOS = 6
ESPERA = 1.5

_ENTRADAS = (rutas_emb.MANIFIESTO, rutas_emb.VOCABULARIO,
             rutas_emb.INDICE, rutas_emb.VECTORES)


def firma():
    """
    Huella barata del estado de embedding/salidas/, o None si aun no estan los
    cuatro archivos.

    Sirve para dos cosas: detectar una lectura partida (aqui abajo) y saber si
    vale la pena recalcular el agrupamiento (el visor). Es tamano + mtime y no
    un hash del contenido porque leer 8 MB para decidir si hay que leer 8 MB no
    tiene sentido.
    """
    try:
        estados = [ruta.stat() for ruta in _ENTRADAS]
    except OSError:
        return None
    return tuple((e.st_size, e.st_mtime_ns) for e in estados)


def instantanea(minimo_notas=1):
    """
    Como cargar(), pero garantizando que los cuatro archivos vienen del mismo
    instante.

    Devuelve la misma terna (textos, vectores, indice). Si tras varios intentos
    sigue partiendose, el error sube: a esa altura ya no es una carrera con el
    pipeline sino algo roto que hay que ver.
    """
    ultimo = None
    for _ in range(REINTENTOS):
        antes = firma()
        if antes is None:
            ultimo = RuntimeError(
                "Todavia no estan los cuatro archivos de embedding/salidas/. "
                "Espera a que 'python -m embedding.vectorizar' cierre su primer "
                "bloque.")
            time.sleep(ESPERA)
            continue
        try:
            terna = cargar(minimo_notas=minimo_notas)
        except (OSError, ValueError, KeyError) as error:
            ultimo = error
            time.sleep(ESPERA)
            continue
        if firma() == antes:
            return terna
        ultimo = RuntimeError("Las salidas cambiaron durante la lectura")
        time.sleep(ESPERA)

    raise RuntimeError(
        f"No se obtuvo una instantanea consistente en {REINTENTOS} intentos: "
        f"{ultimo}")
