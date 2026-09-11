"""
El agrupamiento: de 1.024 dimensiones a un numero de cluster por texto.

POR QUE NO SE AGRUPA DIRECTO SOBRE LOS 1.024 NUMEROS DE bge-m3
    Porque en esa dimension la distancia deja de significar lo que uno cree.
    Medido sobre los vectores de este corpus, la similitud coseno entre pares
    de frases tomadas al azar es 0,469 de media con desviacion 0,087: el 98%
    de los pares cae entre 0,30 y 0,71. No hay frases 'lejanas'. Todo esta a
    una distancia parecida de todo, que es la forma que toma la maldicion de la
    dimension en un espacio de embeddings, agravada porque bge-m3 es
    anisotropico y concentra sus vectores en un cono estrecho.

    Un algoritmo de densidad necesita que haya zonas densas y zonas vacias.
    Sobre esa distribucion no las hay: la densidad es casi la misma en todas
    partes y HDBSCAN devolveria casi todo como ruido.

    De ahi la consecuencia practica, que vale para todo lo que se construya
    encima: NUNCA se decide nada con un umbral absoluto de similitud. 0,70 no
    significa 'parecidas' en este espacio; significa 'del 1% mas parecido'. Lo
    que se usa es vecindad RELATIVA -- quien esta entre mis k mas cercanos --
    que es lo que hacen UMAP y HDBSCAN.

QUE HACE UMAP Y QUE NO
    Construye el grafo de los k vecinos mas cercanos por coseno y busca una
    disposicion en pocas dimensiones que conserve ese grafo. Conserva la
    estructura LOCAL -- quien es vecino de quien -- y no las distancias
    globales: en el resultado, la distancia entre dos clusters lejanos no
    significa nada y no hay que interpretarla.

    Eso es exactamente lo que hace falta aqui. La pregunta del proyecto no es
    'cuanto dista la fiebre del trauma', es 'que frases hablan de lo mismo'.

DOS REDUCCIONES Y NO UNA
    Se agrupa sobre 5 dimensiones y se dibuja sobre 2, y son dos corridas
    distintas de UMAP.

    Agrupar sobre las 2 del dibujo seria mas barato y esta mal: aplastar 1.024
    dimensiones en 2 obliga a superponer grupos que no tienen nada que ver solo
    porque no caben, y el agrupamiento heredaria esos choques. Dibujar las 5 no
    se puede. Cada salida sirve para lo suyo, y por eso el mapa es para MIRAR y
    nunca para decidir: dos puntos pegados en el mapa pueden estar en clusters
    distintos y el que manda es el cluster.

EL RUIDO NO ES UN FALLO
    HDBSCAN marca como ruido (-1) lo que no cae en ninguna zona densa, y aqui
    va a marcar mucho: el 93% de los textos distintos aparece una sola vez. Un
    motivo de consulta que nadie mas escribio de forma parecida NO pertenece a
    ningun grupo, y forzarlo dentro del mas cercano seria inventarse el dato.

    Un k-means no tiene esa opcion: reparte los puntos entre k grupos, con lo
    cual toda la cola larga se reparte entre los grupos grandes y los ensucia.
    Por eso aqui es HDBSCAN y no k-means, y por eso una fraccion alta de ruido
    en el informe es informacion sobre el corpus, no un parametro mal puesto.

REPRODUCIBILIDAD
    UMAP con random_state fijo renuncia al paralelismo y corre en un hilo: es
    mas lento a proposito. Un agrupamiento que cambia entre corridas no se
    puede comparar con el de ayer ni depurar, y aqui la corrida siguiente tiene
    que poder atribuir la diferencia a los datos nuevos y no al azar.
"""

import numpy as np

# ==========================================================
# PARAMETROS -- lo unico que hay que tocar para explorar
# ==========================================================

# Vecinos que UMAP mira para construir su grafo. Es la perilla que decide la
# ESCALA de lo que se va a encontrar: bajo, encuentra muchos grupos pequenos y
# muy especificos; alto, pocos grupos grandes y genericos.
VECINOS = 15

# Dimensiones sobre las que se agrupa. Ver 'DOS REDUCCIONES Y NO UNA'.
DIMENSIONES = 5

# min_dist=0 deja que UMAP apile los puntos de un mismo vecindario tan juntos
# como quiera. Para MIRAR un mapa eso es feo y se sube; para que HDBSCAN
# encuentre densidad es justo lo que se quiere.
DISTANCIA_MINIMA = 0.0

# El grupo mas pequeno que cuenta como grupo. Es el parametro que mas cambia el
# resultado y el que hay que mover primero: subirlo da menos grupos, mas
# grandes y mas ruido; bajarlo, muchos grupos diminutos. El valor bueno se
# encuentra mirando el informe, no adivinando.
TAMANO_MINIMO = 15

# Cuan conservador es al declarar densidad. None lo iguala a TAMANO_MINIMO.
MUESTRAS_MINIMAS = None

SEMILLA = 42


def proyectar(vectores, dimensiones=DIMENSIONES, vecinos=VECINOS,
              distancia_minima=DISTANCIA_MINIMA, semilla=SEMILLA):
    """
    Reduce a `dimensiones` conservando la vecindad por coseno.

    La metrica es coseno y no euclidea aunque los vectores vengan normalizados
    -- caso en que ordenan igual -- porque decirlo explicito es lo que impide
    que esto se rompa en silencio el dia que alguien cambie
    embedding/modelo.py y deje de normalizar.
    """
    import umap

    n = len(vectores)
    if n <= dimensiones + 1:
        raise SystemExit(
            f"Solo hay {n} textos distintos: no alcanza para agrupar nada. "
            f"Deja avanzar el pipeline y vuelve a correr esto.")

    # UMAP no admite pedir mas vecinos que puntos hay. Pasa de verdad al correr
    # esto contra un pipeline que lleva pocos minutos.
    vecinos = min(vecinos, n - 1)

    reductor = umap.UMAP(
        n_neighbors=vecinos,
        n_components=dimensiones,
        min_dist=distancia_minima,
        metric="cosine",
        random_state=semilla,
    )
    return reductor.fit_transform(vectores)


def agrupar(proyeccion, tamano_minimo=TAMANO_MINIMO,
            muestras_minimas=MUESTRAS_MINIMAS):
    """
    Devuelve (etiquetas, confianza) con HDBSCAN sobre la proyeccion.

    La metrica aqui SI es euclidea, y no es una incoherencia con proyectar():
    el coseno se aplico donde vivian los 1.024 numeros de bge-m3. La salida de
    UMAP es un espacio nuevo, sin norma que interpretar, en el que lo unico que
    significa algo es la distancia ordinaria entre puntos.

    confianza es la fuerza con que cada texto pertenece a su cluster, de 0 a 1.
    Sirve para ordenar: los textos de confianza alta son los que describen el
    grupo, y por ahi es por donde se le pone nombre.
    """
    import hdbscan

    agrupador = hdbscan.HDBSCAN(
        min_cluster_size=int(tamano_minimo),
        min_samples=int(muestras_minimas) if muestras_minimas else None,
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=False,
    )
    etiquetas = agrupador.fit_predict(np.asarray(proyeccion, dtype=np.float64))
    return etiquetas, agrupador.probabilities_


def resumen(etiquetas, n_notas):
    """
    Las cuatro cifras con que se juzga una corrida, en notas y no en textos.

    Se cuenta en NOTAS a proposito. Un cluster de 20 textos distintos que
    representan 300 notas y otro de 20 textos que representan 21 no son el
    mismo hallazgo, y contando textos parecerian identicos.
    """
    etiquetas = np.asarray(etiquetas)
    n_notas = np.asarray(n_notas)
    es_ruido = etiquetas == -1
    return {
        "textos": int(len(etiquetas)),
        "notas": int(n_notas.sum()),
        "clusters": int(len(set(etiquetas[~es_ruido]))),
        "textos_en_ruido": int(es_ruido.sum()),
        "notas_en_ruido": int(n_notas[es_ruido].sum()),
        "ruido_textos": float(es_ruido.mean()) if len(etiquetas) else 0.0,
        "ruido_notas": (float(n_notas[es_ruido].sum() / n_notas.sum())
                        if n_notas.sum() else 0.0),
    }


# min_dist para el MAPA. Aqui si se sube: con 0.0 los puntos de un vecindario
# se apilan hasta quedar indistinguibles y el dibujo no se puede leer. Es el
# mismo valor de la exploracion en el notebook.
DISTANCIA_MAPA = 0.05

VECINOS_MAPA = 30


def proyectar_mapa(vectores, vecinos=VECINOS_MAPA,
                   distancia_minima=DISTANCIA_MAPA, semilla=SEMILLA):
    """
    La segunda reduccion, la de 2 dimensiones, la que se dibuja.

    Es una corrida de UMAP DISTINTA de la de proyectar(), por lo que explica
    'DOS REDUCCIONES Y NO UNA' arriba: las 5 dimensiones son para agrupar y
    estas 2 para mirar. No se sacan las 2 primeras columnas de la proyeccion de
    5: UMAP no ordena sus componentes por importancia como lo hace un PCA, asi
    que quedarse con dos de las cinco es tirar estructura al azar.

    De ahi la advertencia que hay que tener presente al leer el mapa: los
    colores vienen del espacio de 5 dimensiones y las posiciones de este otro.
    Dos puntos pegados con colores distintos no son un error del agrupamiento,
    son dos vecindarios que en 2 dimensiones no tenian donde separarse. El que
    manda es el color.
    """
    import umap

    n = len(vectores)
    if n <= 3:
        raise SystemExit(
            f"Solo hay {n} textos distintos: no hay nada que dibujar todavia.")

    reductor = umap.UMAP(
        n_neighbors=min(vecinos, n - 1),
        n_components=2,
        min_dist=distancia_minima,
        metric="cosine",
        random_state=semilla,
    )
    return reductor.fit_transform(vectores)
