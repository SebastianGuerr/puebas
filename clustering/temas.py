"""
El segundo nivel: juntar los grupos que hablan de lo mismo en TEMAS.

POR QUE HACEN FALTA DOS NIVELES Y NO UNO MAS FLOJO
    HDBSCAN separa 'diarrea nauseas emesis' de 'vomito diarrea fiebre', y
    'transito accidente moto' de 'moto caida cai'. Como agrupamiento no esta
    mal: son formas distintas de escribir, y para LEER el corpus esa finura
    sirve. Para lo que se va a hacer despues, no.

    Lo que viene despues es contar cuantos triages de cada tipo llegan cada dia
    y cruzarlo contra el clima, el calendario y los eventos de la ciudad. Ahi
    un tema partido en tres son tres series temporales flacas en vez de una con
    senal, y ninguna de las tres alcanza a mostrar nada. La pregunta no es 'que
    escribio exactamente este paciente' sino 'que tipo de urgencia es', y a esa
    pregunta 132 respuestas son demasiadas.

POR QUE NO SE RESUELVE AFLOJANDO HDBSCAN
    Es lo primero que se intenta y no funciona. Medido sobre este corpus con
    cluster_selection_epsilon, que es la perilla nativa para fundir grupos:

        epsilon      0,0    0,1    0,2    0,3    0,5    0,8
        grupos       132    128     90     50     19     11
        ruido notas 17,6%  15,6%   8,5%   3,6%   0,2%   0,0%
        coherencia  0,848  0,846  0,820  0,779  0,721  0,711
        mayor grupo  2,9%   2,9%   6,3%  15,5%  80,3%  86,1%

    Para llegar a unos veinte grupos hay que irse a 0,5, y ahi UNO SOLO se
    traga el 80% del corpus. No es casualidad: epsilon funde por valles de
    densidad en el espacio de UMAP, y en cuanto el umbral supera el valle mas
    estrecho la fusion encadena -- A se pega con B, B con C -- hasta barrerlo
    todo. Se obtienen veinte grupos y diecinueve son migajas.

LO QUE SE HACE AQUI
    Se agrupan los CENTROIDES, no los textos. Cada grupo de HDBSCAN se reduce
    a un punto -- la media de sus vectores pesada por notas, renormalizada -- y
    esos ~132 puntos se agrupan jerarquicamente por coseno.

    Tres cosas salen gratis de hacerlo asi:

    1. Se decide en el espacio de bge-m3, que es donde el coseno significa algo
       porque es la metrica en la que el modelo se entreno. epsilon decide en
       el de UMAP, que es un espacio inventado para que HDBSCAN pueda medir
       densidad y en el que no hay semantica que leer.
    2. No se pierde el nivel fino. Cada nota conserva su grupo Y su tema: el
       grupo para leer y auditar, el tema para contar y cruzar.
    3. La fusion es auditable. salidas/temas.csv dice exactamente que grupos
       cayeron en cada tema, asi que revisarla es leer una tabla y no volver a
       correr nada.

ENLACE COMPLETO Y NO PROMEDIO, QUE ES LO QUE EVITA EL ENCADENAMIENTO
    Con enlace promedio, sobre 129 centroides y pidiendo 20 temas, uno de ellos
    salia con 1.667 notas y 44 grupos dentro, mezclando vomito con hemorroides
    y con gripa. Es el mismo encadenamiento de epsilon por otra via: el
    promedio deja que un tema crezca mientras su centro se mueva despacio.

    El enlace completo mide contra el miembro MAS LEJANO, asi que un tema solo
    admite un grupo nuevo si se parece a todos los que ya estan dentro. La
    lectura es directa y es la que se quiere: 'dentro de un tema, no hay dos
    grupos mas distintos que el umbral'.

LO QUE ESTO NO ES
    No es una taxonomia clinica. Nadie le dijo a esto que existan 'trauma' o
    'respiratorio': son los que salen de como se parecen las frases, y por eso
    hay temas que a un ojo clinico le sobran o le faltan. Si en algun momento
    hacen falta categorias fijas y estables entre corridas -- porque se van a
    comparar meses entre si durante un ano -- esto no basta, y lo que hace
    falta es definir los temas por terminos semilla y asignar cada grupo al mas
    cercano. Se veria parecido y seria otra cosa.

    Mientras tanto hay que tener presente que LOS NUMEROS DE TEMA NO SON
    ESTABLES entre corridas, igual que los de grupo: si el corpus crece y
    aparece un tema nuevo, la numeracion entera se puede correr. Para comparar
    dos corridas se usan los nombres, no los numeros.
"""

import numpy as np

# EL UMBRAL, QUE ES EL MODO POR DEFECTO Y NO UN NUMERO FIJO DE TEMAS.
#
# Dos grupos se juntan si su coseno llega a esto. Como el enlace es completo,
# la garantia vale para el tema entero: dentro de un tema, NINGUN par de grupos
# esta por debajo del umbral.
#
# PEDIR UN NUMERO FIJO DE TEMAS ES LO QUE PRODUCE LAS BOLSAS DE BASURA.
#     Se probo primero y hay que saber por que no quedo. Pidiendo exactamente
#     20 temas sobre 135 grupos, los que no se parecian a nada tenian que
#     entrar igual en alguno, y se encadenaban entre ellos: salia un tema de
#     563 notas que juntaba 'caida trauma altura' con 'fucsia sexual codigo',
#     'hta hipertension' y 'cerebrovascular acv'. No es un fallo del enlace, es
#     que se le pidio algo imposible -- meter 135 cosas en 20 cajas cuando no
#     hay 20 cajas naturales.
#
#     Es el mismo error que agrupar.py rechaza un nivel mas abajo, cuando
#     explica que forzar un texto raro dentro del cluster mas cercano seria
#     inventarse el dato. Aqui vale igual: un grupo que no se parece a ninguno
#     es su propio tema, y eso es informacion, no un hueco que tapar.
#
# QUE VALOR
#     0,70 sobre este corpus. Las referencias para leerlo: dos frases al azar
#     dan 0,47 y dos centroides al azar 0,67 -- promediar acerca todo, asi que
#     el suelo aqui es 0,67 y no 0,47. 0,70 esta justo encima de ese suelo, que
#     es lo que se quiere: junta lo que se parece de verdad y deja fuera lo que
#     solo se parece lo que se parece todo.
#
#     Subirlo parte temas y multiplica los grupos que quedan solos; bajarlo los
#     funde y vuelve a encadenar. Entre 0,68 y 0,75 el resultado es estable en
#     lo que importa -- los temas grandes son los mismos -- y lo que cambia es
#     la cola.
UMBRAL = 0.70

# Numero fijo de temas. None = usar UMBRAL, que es lo normal.
#
# Existe para el caso en que hagan falta exactamente N series y se acepte el
# precio: con N fijo no hay grupos sueltos, pero tampoco hay garantia de que
# los temas signifiquen algo. Util para mirar el corpus de lejos, no para
# fundamentar una decision.
TEMAS = None

# Minimo de grupos para que valga la pena fundir nada.
MINIMO_GRUPOS = 3


def centroides(vectores, etiquetas, n_notas):
    """
    Un punto por grupo: la media de sus vectores pesada por NOTAS.

    Pesada por notas y no por textos distintos por lo mismo que en
    etiquetas.py: dentro de un grupo, un texto que representa 62 notas describe
    el grupo mucho mejor que uno que aparecio una vez, y sin el peso los dos
    moverian el centro igual.

    Se renormaliza despues de promediar. Sin eso la media de vectores unitarios
    cae dentro de la esfera y su norma depende de lo disperso que sea el grupo:
    los productos dejarian de ser cosenos y un grupo disperso se mediria como
    lejano a todo solo por serlo.

    Devuelve (grupos, centroides, notas_por_grupo) con los grupos ordenados.
    """
    etiquetas = np.asarray(etiquetas)
    n_notas = np.asarray(n_notas, dtype=np.float64)
    grupos = sorted(int(c) for c in set(etiquetas) if c != -1)

    puntos, pesos = [], []
    for c in grupos:
        filas = np.where(etiquetas == c)[0]
        bloque = np.asarray(vectores[filas], dtype=np.float64)
        peso = n_notas[filas]
        centro = np.average(bloque, axis=0, weights=peso)
        norma = np.linalg.norm(centro)
        puntos.append(centro / norma if norma else centro)
        pesos.append(float(peso.sum()))

    return grupos, np.vstack(puntos) if puntos else np.empty((0, 0)), np.array(pesos)


def fundir(vectores, etiquetas, n_notas, n_temas=TEMAS, umbral=UMBRAL):
    """
    Devuelve {grupo: tema}, el mapa del nivel fino al general.

    Con n_temas en None manda el umbral y salen los temas que salgan, que es lo
    normal. Con un n_temas se pide ese numero exacto y el umbral se ignora.

    El ruido no entra y no recibe tema: se queda en -1 en los dos niveles. Es
    deliberado y hay que tenerlo presente al contar -- las notas sin tema son
    el 17% y siguen siendo llegadas al hospital, asi que para un total diario
    se cuentan igual; lo que no se puede es atribuirles un motivo.
    """
    from sklearn.cluster import AgglomerativeClustering

    grupos, puntos, _ = centroides(vectores, etiquetas, n_notas)
    if len(grupos) < MINIMO_GRUPOS:
        # Con dos grupos no hay nada que fundir: cada uno es su propio tema.
        return {c: i for i, c in enumerate(grupos)}

    if n_temas:
        # Pedir mas temas que grupos no significa nada y sklearn lo rechaza.
        ajuste = dict(n_clusters=max(1, min(int(n_temas), len(grupos))),
                      distance_threshold=None)
    else:
        # sklearn habla en distancia y aqui se razona en similitud, que es como
        # se lee todo lo demas del paquete. La conversion es la resta.
        ajuste = dict(n_clusters=None, distance_threshold=1.0 - float(umbral))

    modelo = AgglomerativeClustering(
        metric="cosine", linkage="complete", **ajuste)
    crudo = modelo.fit_predict(puntos)

    return _renumerar(grupos, crudo, vectores, etiquetas, n_notas)


def _renumerar(grupos, crudo, vectores, etiquetas, n_notas):
    """
    Renumera los temas de mayor a menor NOTAS, para que el tema 0 sea el mas
    grande.

    sklearn los numera por el orden en que los fue cerrando el algoritmo, que
    no significa nada. Numerarlos por tamano hace que el informe, el CSV y el
    panel del mapa se lean en el mismo orden sin tener que ordenar tres veces,
    y que 'tema 0' quiera decir algo al leerlo suelto.
    """
    etiquetas = np.asarray(etiquetas)
    n_notas = np.asarray(n_notas, dtype=np.float64)

    peso = {}
    for c, t in zip(grupos, crudo):
        peso[t] = peso.get(t, 0.0) + n_notas[etiquetas == c].sum()

    orden = {t: i for i, t in
             enumerate(sorted(peso, key=lambda t: -peso[t]))}
    return {c: orden[t] for c, t in zip(grupos, crudo)}


def aplicar(textos, mapa):
    """
    La columna 'tema' a partir de la columna 'cluster'. El ruido sigue en -1.
    """
    return np.array([mapa.get(int(c), -1) for c in textos["cluster"]], dtype=int)


def separacion(vectores, etiquetas, n_notas, mapa):
    """
    Cuanto se parecen entre si los grupos que quedaron en el mismo tema.

    Es la vara de si la fusion fue razonable, y se lee junto a la coherencia de
    los grupos: aquella dice si cada grupo es apretado, y esta si el tema que
    los junta tiene sentido o metio cosas distintas en la misma bolsa.

    Devuelve el coseno medio entre pares de grupos del mismo tema, pesado por
    notas. Referencias para leerlo: dos frases al azar de este corpus dan 0,47
    y dos centroides al azar rondan 0,67 -- los centroides ya estan mas cerca
    entre si que las frases sueltas, porque promediar borra lo particular. Asi
    que lo que dice que un tema es bueno no es pasar de 0,47 sino quedar
    claramente por encima de 0,67.
    """
    grupos, puntos, pesos = centroides(vectores, etiquetas, n_notas)
    indice = {c: i for i, c in enumerate(grupos)}

    valores, ponderaciones = [], []
    for tema in sorted(set(mapa.values())):
        miembros = [indice[c] for c in grupos if mapa.get(c) == tema]
        if len(miembros) < 2:
            continue
        bloque = puntos[miembros]
        similitudes = bloque @ bloque.T
        arriba = np.triu_indices(len(miembros), 1)
        valores.append(float(similitudes[arriba].mean()))
        ponderaciones.append(float(pesos[miembros].sum()))

    if not valores:
        return float("nan")
    return float(np.average(valores, weights=ponderaciones))
