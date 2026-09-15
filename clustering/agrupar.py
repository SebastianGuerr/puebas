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


def _umap():
    """
    Importa UMAP callando UN aviso concreto, y solo ese.

    'n_jobs value 1 overridden to 1 by setting random_state' no describe un
    problema: describe la decision de REPRODUCIBILIDAD que se tomo aqui a
    proposito y que esta explicada arriba. Sale dos veces por corrida -- una
    por reduccion -- y encabeza la salida del comando, justo donde lo primero
    que se lee tiene que ser el resultado.

    Se silencia por el texto del mensaje y no apagando los avisos de UMAP en
    bloque: cualquier otro que aparezca sigue saliendo, que es el unico motivo
    de que exista un sistema de avisos.
    """
    import warnings

    import umap

    warnings.filterwarnings(
        "ignore", message=r".*n_jobs value .* overridden.*")
    return umap


# ==========================================================
# PARAMETROS -- lo unico que hay que tocar para explorar
# ==========================================================

# Vecinos que UMAP mira para construir su grafo. Es la perilla que decide la
# ESCALA de lo que se va a encontrar: bajo, encuentra muchos grupos pequenos y
# muy especificos; alto, pocos grupos grandes y genericos.
VECINOS = 15

# Dimensiones sobre las que se agrupa. Ver 'DOS REDUCCIONES Y NO UNA'.
#
# SIGUE EN 5 Y ESO ES UN RESULTADO, NO UN DESCUIDO.
#     Es el parametro que mas invita a tocar -- el notebook exploratorio usaba
#     50 -- y el barrido dice que es el que menos hace. Con el resto fijo
#     (vecinos 15, tamano 10, muestras 3) sobre 1.957 textos:
#
#         dimensiones    5      10     15     30     50
#         grupos        71      68     68     62     66
#         ruido notas  14,4%  14,3%  16,3%  13,6%  16,1%
#         coherencia   0,834  0,832  0,834  0,826  0,833
#
#     No hay tendencia: la coherencia se mueve menos de 0,01 y el ruido sube y
#     baja sin direccion. Es ruido de medida. Y tiene sentido -- UMAP ya
#     resolvio el problema de la dimension al construir el grafo de vecinos;
#     darle 50 salidas en vez de 5 no le da mas informacion, solo mas sitio
#     donde ponerla.
#
#     Asi que se queda en 5, que es la mas barata de reducir y de agrupar. Lo
#     que si cambia el resultado son los dos parametros de HDBSCAN de aqui
#     abajo.
DIMENSIONES = 5

# min_dist=0 deja que UMAP apile los puntos de un mismo vecindario tan juntos
# como quiera. Para MIRAR un mapa eso es feo y se sube; para que HDBSCAN
# encuentre densidad es justo lo que se quiere.
DISTANCIA_MINIMA = 0.0

# El grupo mas pequeno que cuenta como grupo. Subirlo da menos grupos, mas
# grandes y mas ruido; bajarlo, muchos grupos diminutos. El valor bueno se
# encuentra con 'python -m clustering --barrido', no adivinando.
#
# Estaba en 15 y bajo a 10. Sobre 1.957 textos, con muestras_minimas en 3:
#
#     tamano_minimo   8      10     15     20     30
#     grupos         82      71     46     35     25
#     ruido notas  13,0%  14,4%  16,5%  21,6%  18,1%
#     coherencia   0,838  0,834  0,817  0,813  0,795
#
# 10 es donde deja de comprar cobertura y empieza a pagarla: bajar a 8 gana
# punto y medio de ruido a cambio de once grupos mas que leer, y subir a 15
# cuesta ruido y coherencia a la vez. Tendra que volver a mirarse cuando el
# corpus crezca: un grupo de 10 textos sobre 1.957 no es lo mismo que sobre
# 20.000, donde ese tamano ya es una rareza y no un patron.
#
# LA COLUMNA 'coherencia' DE ESA TABLA ESTA INFLADA POR EL TAMANO.
#     El suelo de la coherencia sube cuando los grupos son chicos (ver
#     coherencia() aqui abajo), asi que parte de la caida de 0,838 a 0,795 es el
#     suelo bajando y no calidad perdiendose. Corregido contra el nulo sobre
#     5.020 textos, la ganancia real va de 0,126 a 0,100 por el mismo rango.
#
#     La eleccion de 10 aguanta: la direccion es la misma. Lo que cambia es el
#     margen, que es la mitad del que parecia, y que entre 8 y 10 la ganancia es
#     identica -- los dos dan 0,126 -- asi que ahi ya no decide la metrica sino
#     cuantos grupos se quieren leer. La proxima vez que se toque esto, la
#     columna que hay que mirar es la ganancia de --validar y no esta.
TAMANO_MINIMO = 10

# LA PERILLA DE LA PRECISION, Y NO ES TAMANO_MINIMO.
#
# min_samples es lo conservador que es HDBSCAN al declarar que una zona es
# densa. Los dos parametros suenan parecido y hacen cosas distintas:
#
#   TAMANO_MINIMO    de que tamano para arriba algo cuenta como grupo.
#   MUESTRAS_MINIMAS cuanta evidencia exige para creerse que hay densidad.
#
# Igualandolos -- que es lo que hace None, y es el valor de fabrica de la
# libreria -- se pide lo mas estricto posible, y de ahi sale la montana de
# ruido. Bajandolo se rescata de la cola larga lo que si tenia vecinos: parte
# entra a los grupos que ya existian y parte forma grupos nuevos y pequenos,
# asi que bajan el ruido y sube la cuenta de grupos a la vez. Es la diferencia
# entre 'no se parece a nada' y 'no me atrevo a decir que se parece a algo'.
#
# Se paga en pureza: cuanto mas bajo, mas puntos dudosos entran a algun grupo.
# Por eso va acompanado de la coherencia en el informe, que es lo que mide si
# lo que entro pertenecia de verdad.
#
# ESTABA EN None Y ERA LO QUE PRODUCIA CASI TODO EL RUIDO.
#     Con tamano_minimo en 15, moverlo es lo unico que hizo falta para bajar el
#     ruido diez puntos sin perder nada:
#
#         muestras_minimas    1      3      5     10     15 (=None)
#         grupos             54     46     43     42     36
#         ruido notas      15,1%  16,5%  17,5%  23,2%  26,4%
#         coherencia       0,820  0,817  0,818  0,826  0,820
#
#     La coherencia no se mueve. Esos diez puntos de ruido no eran frases que
#     no pertenecian a ningun grupo: eran frases que SI pertenecian y que
#     HDBSCAN no se atrevia a colocar, porque None le pide la exigencia maxima.
#     Es el valor de fabrica de la libreria y no una eleccion.
#
#     Se deja en 3 y no en 1 por margen: con 1 basta un solo vecino para
#     sostener un punto, y sobre un corpus que va a crecer diez veces eso
#     empieza a pegar cosas por casualidad. 3 da casi la misma cobertura
#     pidiendo evidencia de verdad.
MUESTRAS_MINIMAS = 3

# Distancia por debajo de la cual dos micro-grupos se declaran el mismo. Con 0
# se apaga y manda solo la jerarquia. Subirlo pega los grupos que HDBSCAN parte
# por un valle de densidad estrecho -- tipico cuando la misma dolencia se
# escribe de dos formas -- sin tener que subir TAMANO_MINIMO, que ademas
# aumentaria el ruido.
EPSILON = 0.0

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
    umap = _umap()

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
            muestras_minimas=MUESTRAS_MINIMAS, epsilon=EPSILON):
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
        cluster_selection_epsilon=float(epsilon),
        metric="euclidean",
        cluster_selection_method="eom",
        prediction_data=False,
    )
    etiquetas = agrupador.fit_predict(np.asarray(proyeccion, dtype=np.float64))
    return etiquetas, agrupador.probabilities_


def coherencia(vectores, etiquetas, n_notas):
    """
    Que tan apretado es cada grupo EN EL ESPACIO DE bge-m3, de 0 a 1.

    Es la unica metrica de calidad que se puede comparar entre corridas con
    distinto numero de dimensiones. Todo lo que se mida sobre la salida de UMAP
    -- silueta, DBCV -- mide tambien la reduccion, y una reduccion a 5
    dimensiones y otra a 30 no producen numeros del mismo orden: se estaria
    comparando la vara y no lo medido. El espacio de los 1.024 numeros no
    cambia entre corridas, asi que ahi si.

    Se mide como la similitud coseno media de cada texto con el centro de su
    grupo, pesando por notas y promediando los grupos tambien por notas. El
    ruido no entra: no tiene centro al que parecerse.

    COMO SE LEE -- CORREGIDO, Y LA VERSION ANTERIOR ERA FALSA
        Aqui decia que el suelo era 0,47, el coseno medio entre dos frases al
        azar, y que por tanto un grupo con 0,75 estaba 'muy por encima del
        azar'. No es cierto y el error no es pequeno.

        La coherencia no compara dos frases: compara una frase con la MEDIA de
        su grupo, y promediar vectores que ya correlacionan 0,47 entre si
        produce un centro al que todos se parecen mucho mas. El suelo real de
        un grupo de n textos SIN NINGUNA ESTRUCTURA es sqrt((1+(n-1)*0,4636)/n),
        verificado contra el corpus:

            n            2      5     10     20     50    100
            azar puro  0,856  0,755  0,718  0,700  0,689  0,685

        Un grupo de dos textos sin nada en comun da 0,86. Los 0,847 que este
        paquete reportaba como resultado de la corrida entera estan por debajo
        de eso.

        Dos consecuencias:

        1. El suelo depende del TAMANO del grupo, asi que la coherencia baja
           sola cuando los grupos crecen. Las tablas de este mismo archivo que
           fijaron TAMANO_MINIMO miden en parte ese efecto y no calidad; la
           conclusion aguanta, pero por la mitad del margen que parecia.
        2. Una coherencia sola no se puede leer. Hay que leerla contra su nulo,
           que calcula validacion.calibrar() barajando las etiquetas entre los
           textos: conserva los tamanos de grupo y destruye toda relacion con el
           contenido.

        Sobre la corrida de 5.020 textos: coherencia 0,851, nulo 0,728,
        GANANCIA +0,122. Esa ganancia es lo unico comparable entre corridas, y
        para dimensionarla: el mismo pipeline sobre datos SIN estructura saca
        una coherencia de 0,725 con ganancia -0,001.

    LO QUE ESTA METRICA NO PUEDE VER
        Solo mira hacia adentro del grupo. Partir un tema real en cinco pedazos
        apretados la SUBE. Para lo otro -- que los grupos esten separados entre
        si -- hace falta la silueta, que validacion.siluetas() calcula en este
        mismo espacio y por tanto es igual de comparable entre corridas.
    """
    etiquetas = np.asarray(etiquetas)
    n_notas = np.asarray(n_notas, dtype=np.float64)
    valores, pesos = [], []
    for c in sorted(set(etiquetas) - {-1}):
        filas = np.where(etiquetas == c)[0]
        bloque = np.asarray(vectores[filas], dtype=np.float64)
        peso = n_notas[filas]
        centro = np.average(bloque, axis=0, weights=peso)
        norma = np.linalg.norm(centro)
        if norma:
            centro = centro / norma
        valores.append(float(np.average(bloque @ centro, weights=peso)))
        pesos.append(float(peso.sum()))
    if not valores:
        return 0.0
    return float(np.average(valores, weights=pesos))


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
    umap = _umap()

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
