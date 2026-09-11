"""
Ponerle nombre a cada cluster. Sin esto el resultado son numeros sin sentido.

EL PROBLEMA
    HDBSCAN devuelve 'cluster 7'. Para buscar patrones hace falta saber que el
    cluster 7 es el de los traumas por caida, y hace falta que ese nombre salga
    de los datos y no de que alguien se leyo cien notas y decidio.

POR QUE NO SIRVE CONTAR PALABRAS Y QUEDARSE CON LAS MAS FRECUENTES
    Porque lo mas frecuente dentro de un cluster suele ser lo mas frecuente en
    todos: 'dolor' encabezaria media docena de grupos y no distinguiria
    ninguno. La pregunta correcta no es que palabras aparecen mucho AQUI, es
    que palabras aparecen mucho aqui Y POCO EN EL RESTO.

    Eso es un TF-IDF, pero calculado tomando cada CLUSTER como documento en vez
    de cada nota. Con la nota como documento, el IDF mide en cuantas notas sale
    la palabra, que es una propiedad del corpus y no del grupo. Con el cluster
    como documento mide exactamente lo que se quiere: cuantos GRUPOS comparten
    la palabra. La que sale en uno solo lo nombra; la que sale en todos, no.

LAS NOTAS PESAN, LOS TEXTOS NO
    El agrupamiento trabaja con textos distintos (ver corpus.py), pero para
    nombrar se cuenta cada texto tantas veces como notas tiene. Un cluster
    donde 'contracciones' aparece en un texto que representa 62 notas y
    'tapon' en uno que representa 1 no se nombra igual con ambos.

EL NOMBRE NO BASTA, TAMBIEN VA UN EJEMPLO
    Tres palabras sueltas se pueden leer de varias formas. Junto al nombre va
    el texto REAL mas central del grupo, que es lo que permite ver de un
    vistazo si el cluster tiene sentido o si junto dos cosas distintas.

    Ese texto se elige en el espacio original de bge-m3 y no en la proyeccion
    de UMAP. UMAP conserva quien es vecino de quien, no las distancias: su
    centro geometrico no corresponde a ningun 'significado medio'. El de los
    1.024 numeros si.
"""

import re

import numpy as np

from NLP.nucleo import morfologia
from clustering import rutas

# Cuantas palabras forman el nombre. Tres es lo que cabe en una leyenda y en
# una columna de CSV sin dejar de decir algo.
PALABRAS_NOMBRE = 3

# Una palabra que aparece en mas de esta fraccion de los clusters no nombra
# nada, y se reporta como candidata a palabras_vacias.txt. No se filtra sola:
# la lista se edita a mano a proposito, para que quede constancia de que se
# quito y quien lo decidio.
REPARTO_SOSPECHOSO = 0.5

RE_PALABRA = re.compile(r"[a-zñ]{3,}")


def palabras_vacias():
    """
    La lista de datos/palabras_vacias.txt, plegada sin tildes para que coincida
    con como se parten los textos aqui.
    """
    ruta = rutas.DATOS / "palabras_vacias.txt"
    if not ruta.exists():
        return set()
    vacias = set()
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if linea and not linea.startswith("#"):
            vacias.add(morfologia.sin_tildes(linea.lower()))
    return vacias


def partir(texto, vacias):
    """
    De un texto a su lista de palabras utiles.

    Se pliegan las tildes porque el corpus escribe 'caida' y 'caída' para la
    misma cosa y contarlas aparte partiria en dos la evidencia del mismo
    cluster. Se descartan las de menos de tres letras porque a ese largo casi
    todo es preposicion o ruido de digitacion.

    Los glosados que deja la fase 3 -- 'dolor de cabeza (cefalea)' -- entran
    enteros, con la palabra coloquial y la clinica. Es deliberado: la clinica
    es la que nombra bien el cluster, y la coloquial es la que explica por que
    quedaron juntas frases que no comparten terminologia.
    """
    plano = morfologia.sin_tildes(str(texto).lower())
    return [p for p in RE_PALABRA.findall(plano) if p not in vacias]


def nombrar(textos, etiquetas, vectores, n_palabras=PALABRAS_NOMBRE):
    """
    Devuelve (nombres, representantes, difusas).

    nombres       {cluster: 'palabra palabra palabra'}
    representantes {cluster: el texto real mas central}
    difusas       [(palabra, fraccion de clusters en que sale)] -- las que
                  aparecen repartidas por todas partes y por tanto no nombran:
                  la lista de candidatas para palabras_vacias.txt.
    """
    etiquetas = np.asarray(etiquetas)
    grupos = sorted(c for c in set(etiquetas) if c != -1)
    if not grupos:
        return {}, {}, []

    vacias = palabras_vacias()
    n_notas = textos["n_notas"].to_numpy()
    columna = textos["texto"].to_numpy()

    # frecuencia de cada palabra dentro de cada cluster, pesada por notas
    conteo = {}
    for c in grupos:
        cuenta = {}
        for i in np.where(etiquetas == c)[0]:
            peso = int(n_notas[i])
            for palabra in set(partir(columna[i], vacias)):
                cuenta[palabra] = cuenta.get(palabra, 0) + peso
        conteo[c] = cuenta

    # en cuantos clusters aparece cada palabra: el IDF de clase
    clusters_por_palabra = {}
    for cuenta in conteo.values():
        for palabra in cuenta:
            clusters_por_palabra[palabra] = clusters_por_palabra.get(palabra, 0) + 1

    total_clusters = len(grupos)
    nombres = {}
    for c in grupos:
        cuenta = conteo[c]
        total = sum(cuenta.values()) or 1
        puntajes = {
            palabra: (veces / total) * np.log(
                1 + total_clusters / clusters_por_palabra[palabra])
            for palabra, veces in cuenta.items()
        }
        mejores = sorted(puntajes, key=lambda p: -puntajes[p])[:n_palabras]
        nombres[c] = " ".join(mejores) if mejores else f"cluster {c}"

    representantes = _representantes(textos, etiquetas, vectores, grupos)

    difusas = sorted(
        ((palabra, veces / total_clusters)
         for palabra, veces in clusters_por_palabra.items()
         if veces / total_clusters > REPARTO_SOSPECHOSO),
        key=lambda par: -par[1])

    return nombres, representantes, difusas


def _representantes(textos, etiquetas, vectores, grupos):
    """
    El texto real mas cercano al centro de cada cluster, en el espacio de
    bge-m3.

    El centro se calcula pesando por notas y se vuelve a normalizar. Sin
    renormalizar, la media de vectores unitarios cae DENTRO de la esfera y su
    norma depende de lo disperso que sea el cluster: los productos con ella
    dejarian de ser cosenos y un cluster disperso puntuaria mas bajo solo por
    serlo. Se compara con coseno porque es la metrica en la que bge-m3 se
    entreno; cualquier otra mide algo que el modelo no aprendio.
    """
    columna = textos["texto"].to_numpy()
    n_notas = textos["n_notas"].to_numpy().astype(np.float32)
    representantes = {}
    for c in grupos:
        filas = np.where(etiquetas == c)[0]
        bloque = vectores[filas]
        centro = np.average(bloque, axis=0, weights=n_notas[filas])
        norma = np.linalg.norm(centro)
        if norma:
            centro = centro / norma
        representantes[c] = str(columna[filas[np.argmax(bloque @ centro)]])
    return representantes
