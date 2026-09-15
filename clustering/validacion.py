"""
Poner a prueba las decisiones del agrupamiento en vez de confiar en ellas.

    python -m clustering --validar              todo
    python -m clustering --validar --rapido     solo lo que no vuelve a reducir

QUE PREGUNTA ESTE MODULO Y QUE NO PREGUNTABA EL BARRIDO
    barrido.py compara configuraciones ENTRE SI: dice cual de dos es mejor.
    Este modulo pregunta lo otro, que es lo que faltaba: si lo que sale se
    distingue de lo que saldria sin ningun patron en los datos, y si sobrevive
    a repetir la corrida cambiando cosas que no deberian cambiar el resultado.

    Son preguntas distintas y la segunda es la que decide si se puede seguir
    construyendo encima. Una configuracion puede ganarle a todas las demas del
    barrido y aun asi estar describiendo ruido: ganar una comparacion entre
    malas opciones no convierte a ninguna en buena.

LO QUE SE ENCONTRO AL ESCRIBIR ESTO -- LEER ANTES DE INTERPRETAR NADA
    La coherencia NO tiene su suelo en 0,47. Ese numero es el coseno medio
    entre dos frases al azar, y la coherencia no compara dos frases: compara
    una frase con la MEDIA de su grupo. Promediar n vectores unitarios que
    correlacionan 0,47 entre si produce un centro al que todos se parecen
    mucho mas que entre ellos, sin que haya ninguna estructura de por medio.

    La cuenta es exacta y esta verificada contra el corpus:

        coherencia de un grupo ALEATORIO de n textos = sqrt((1 + (n-1)r) / n)
        con r = 0,4636, el coseno medio entre pares de este corpus.

            n            2      5     10     20     50    100    200
            medido    0,856  0,755  0,718  0,700  0,689  0,685  0,683
            formula   0,855  0,756  0,719  0,700  0,689  0,685  0,683

    Un grupo de dos textos SIN NADA EN COMUN da 0,86, por encima del 0,847 que
    el informe reporta como resultado de la corrida entera.

    Dos consecuencias, y ninguna es cosmetica:

    1. El suelo depende del TAMANO del grupo, asi que la coherencia baja sola
       cuando los grupos crecen. La tabla de agrupar.py que llevo a elegir
       TAMANO_MINIMO = 10 mide en parte ese efecto y no la calidad. Corregida
       contra el nulo, sobre la corrida de 5.020 textos:

           tam_min        8      10     15     20     30
           coherencia  0,856  0,851  0,838  0,824  0,806
           nulo        0,730  0,725  0,720  0,713  0,705
           GANANCIA    0,126  0,126  0,119  0,112  0,100

       La conclusion de fondo aguanta -- los grupos chicos son mas puros de
       verdad, no solo por aritmetica -- pero la mitad de la caida era el suelo
       moviendose. Entre 8 y 10 ya no hay diferencia medible.

    2. Nunca mas se lee una coherencia sola. Se lee contra su nulo, que es lo
       que calcula calibrar().

    'separacion', la del nivel de temas, NO tiene este problema: es un coseno
    medio entre PARES de centroides y su suelo -- 0,663 medido aqui -- no
    depende del tamano del tema. El 0,67 del docstring de temas.py es correcto.
    Lo que si tiene es otro problema distinto, que esta en codo_temas().

EL COSTO
    Casi todo es UMAP. La primera reduccion de la sesion paga la compilacion de
    numba y cuesta un par de minutos; las siguientes bajan a unos treinta
    segundos. La validacion completa hace diez reducciones -- el modelo nulo,
    tres semillas, tres dimensiones y tres submuestras -- asi que cuenta con
    unos siete u ocho minutos.

    --rapido se salta esas diez y deja lo que se calcula sobre la reduccion que
    ya esta en salidas/: la calibracion, las siluetas, el codo de temas y la
    validacion externa. Son segundos y responden la mitad de las preguntas.

    CUANDO EL CORPUS CREZCA ESTO DEJA DE COSTAR MINUTOS
        Hoy son 5.020 textos de los 94.000 que hay disponibles. UMAP con
        random_state fijo corre en un hilo a proposito (ver agrupar.py), y su
        costo crece algo mas que linealmente: sobre el corpus completo hay que
        contar con un cuarto de hora por reduccion, o sea unas tres horas la
        validacion entera.

        No es motivo para dejar de correrla -- se corre cuando el corpus da un
        salto de tamano, no todos los dias -- pero si para lanzarla sabiendo lo
        que va a tardar. Lo que se puede hacer mientras tanto es --rapido, que
        no depende del tamano de la misma forma.

QUE QUEDO PROBADO Y QUE NO, EN UNA PANTALLA
    Aguanta:
      - la estructura es real. Sobre datos sin estructura el mismo pipeline
        deja fuera el 43% de las notas y saca una ganancia de -0,001, o sea
        cero; sobre los datos reales deja fuera el 16% y saca +0,122. Ver
        modelo_nulo().
      - los grupos significan algo clinico: 0,78 de pureza contra el catalogo
        de sintomas, donde el azar da 0,23. Ver externa().
      - DIMENSIONES = 5 esta bien. Ver acuerdo_dimensiones().
      - no hace falta corregir la anisotropia de bge-m3. Ver centrado().
      - la ventana de 128 tokens se sostiene. Ver truncamiento().

    No aguanta:
      - leer la coherencia contra 0,47. Ver el bloque de aqui arriba.
      - el numero de grupos como resultado: el modelo nulo saca 121.
      - 'separacion' como justificacion del umbral de temas. Ver codo_temas().
      - tratar un grupo concreto como un hallazgo estable entre corridas.
        Quitando el 20% del corpus el ARI cae a 0,25-0,31. Ver estabilidad_datos(),
        que es lo que hay que leer antes de montar series temporales encima.
"""

import numpy as np

from clustering import agrupar, rutas, temas

# Semilla de las pruebas. No es la del agrupamiento (agrupar.SEMILLA = 42): son
# dos azares distintos y mezclarlos haria que una prueba comparta el sorteo con
# lo que esta probando.
SEMILLA = 12345

# Cuantas veces se baraja para estimar el nulo de la coherencia. La desviacion
# medida entre repeticiones es 0,002, asi que con 20 sobra: el tercer decimal ya
# no se mueve.
REPETICIONES = 20

# Semillas alternativas de UMAP. Tres bastan para distinguir 'estable' de 'el
# resultado es el sorteo'; no es una estimacion fina de nada.
SEMILLAS_ALTERNAS = (1, 7, 2024)

# Fraccion que se conserva en cada submuestra. 80% es lo habitual en las
# pruebas de estabilidad: quita bastante para que se note, no tanto como para
# que el corpus deje de ser el mismo.
SUBMUESTRA = 0.8
REPETICIONES_SUBMUESTRA = 3

# Dimensiones contra las que se compara la elegida. Las del barrido mas 50, que
# es lo que usaba el notebook exploratorio.
DIMENSIONES_PRUEBA = (10, 30, 50)

UMBRALES_TEMA = (0.60, 0.64, 0.66, 0.68, 0.70, 0.72, 0.75, 0.78, 0.80)


# ==========================================================
# 1. EL SUELO DE LA COHERENCIA
# ==========================================================

def calibrar(vectores, etiquetas, n_notas, repeticiones=REPETICIONES,
             semilla=SEMILLA):
    """
    La coherencia real contra la que daria el MISMO agrupamiento sin estructura.

    El nulo se estima barajando las etiquetas entre los textos: se conservan
    exactamente los tamanos de grupo y se destruye toda relacion entre el grupo
    y el contenido. Lo que queda es el suelo aritmetico que explica el docstring
    del modulo.

    Se baraja en vez de aplicar la formula sqrt((1+(n-1)r)/n) porque la formula
    supone que todos los pares correlacionan igual, y en un corpus real eso no
    es cierto -- hay frases mas centrales que otras. Barajar no supone nada.

    Devuelve real, nulo y ganancia. La ganancia es lo unico comparable entre
    corridas que tengan distinto tamano de grupo.
    """
    etiquetas = np.asarray(etiquetas)
    azar = np.random.default_rng(semilla)

    real = agrupar.coherencia(vectores, etiquetas, n_notas)
    nulos = [agrupar.coherencia(
        vectores, etiquetas[azar.permutation(len(etiquetas))], n_notas)
        for _ in range(repeticiones)]
    nulo = float(np.mean(nulos))
    return {"real": real, "nulo": nulo,
            "desviacion_nulo": float(np.std(nulos)),
            "ganancia": real - nulo}


# ==========================================================
# 2. LO QUE LA COHERENCIA NO MIDE: LA SEPARACION
# ==========================================================

# Textos por encima de los cuales la silueta se calcula sobre una muestra.
#
# LA SILUETA ES CUADRATICA Y ESO DEJA DE SER GRATIS MUY PRONTO
#     silhouette_samples compara cada texto con todos los demas: sobre los 5.020
#     de hoy son 25 millones de pares de 1.024 dimensiones, que tarda unos
#     segundos. Sobre las 94.000 notas que hay disponibles serian 8.800
#     millones de pares -- unas 350 veces mas -- y ademas la matriz de
#     distancias no cabe en memoria.
#
#     Es un fallo que no se ve venir: hoy funciona, y el dia que el corpus
#     crezca la validacion entera se cae despues de haber gastado media hora en
#     las reducciones. Por eso el limite esta puesto ahora y no cuando duela.
#
#     Con 20.000 textos muestreados el error de la silueta media esta muy por
#     debajo del tercer decimal, que es toda la precision con la que se lee.
MAXIMO_SILUETA = 20_000


def siluetas(vectores, proyeccion, etiquetas, maximo=MAXIMO_SILUETA,
             semilla=SEMILLA):
    """
    Silueta en el espacio de bge-m3 y DBCV en el de UMAP.

    POR QUE ESTO NO CONTRADICE A agrupar.py
        Ese modulo descarta la silueta con un argumento correcto: medida sobre
        la salida de UMAP, mide tambien la reduccion, y una a 5 dimensiones y
        otra a 30 no producen numeros del mismo orden.

        El argumento vale para la salida de UMAP. No vale para el espacio de
        los 1.024 numeros, que es el mismo en todas las corridas -- que es
        exactamente la razon por la que la coherencia si se mide ahi. La
        silueta ahi es igual de comparable que la coherencia, y mide lo que a
        la coherencia le falta.

        Y le falta lo importante: la coherencia solo mira hacia adentro del
        grupo. Un agrupamiento que parta un tema real en cinco pedazos
        apretados tendra coherencia altisima y estara mal. La silueta resta la
        distancia al grupo vecino mas cercano, asi que penaliza justo eso.

    DBCV se calcula sobre UMAP porque es la metrica disenada para densidad y la
    unica que juzga a HDBSCAN en sus propios terminos. No se compara entre
    dimensiones distintas, por lo que dice agrupar.py; sirve para comparar
    configuraciones a dimension fija.

    El ruido se excluye de las dos: no es un grupo y no tiene centro.
    """

    etiquetas = np.asarray(etiquetas)
    dentro = etiquetas != -1
    salida = {"silueta_bge": float("nan"), "dbcv": float("nan"),
              "muestreada": False}

    if dentro.sum() > 1 and len(set(etiquetas[dentro])) > 1:
        from sklearn.metrics import silhouette_samples

        bloque = np.asarray(vectores)[dentro]
        etiquetas_dentro = etiquetas[dentro]

        # El muestreo respeta los grupos: se toma una fraccion de CADA uno en
        # vez de una muestra global. Con una muestra global los grupos chicos
        # desaparecen y su silueta -- que es justo la que suele ser mala -- no
        # entraria en la media.
        if len(bloque) > maximo:
            azar = np.random.default_rng(semilla)
            fraccion = maximo / len(bloque)
            elegidos = []
            for grupo in np.unique(etiquetas_dentro):
                cuales = np.where(etiquetas_dentro == grupo)[0]
                cuantos = max(2, int(round(len(cuales) * fraccion)))
                elegidos.append(azar.choice(cuales, size=min(cuantos, len(cuales)),
                                            replace=False))
            elegidos = np.sort(np.concatenate(elegidos))
            bloque, etiquetas_dentro = bloque[elegidos], etiquetas_dentro[elegidos]
            salida["muestreada"] = True
            salida["textos_muestra"] = int(len(elegidos))

        por_texto = silhouette_samples(bloque, etiquetas_dentro, metric="cosine")

        # La media esconde lo que importa: un agrupamiento puede tener silueta
        # media baja porque todo esta regular, o porque la mayoria esta bien y
        # unos pocos grupos estan mal. Solo el segundo caso se arregla. Por eso
        # se guarda tambien la silueta por grupo y la fraccion de textos con
        # silueta negativa, que son los que estarian mejor en el grupo vecino.
        salida["silueta_bge"] = float(por_texto.mean())
        salida["negativos"] = float((por_texto < 0).mean())
        salida["por_grupo"] = sorted(
            float(por_texto[etiquetas_dentro == grupo].mean())
            for grupo in np.unique(etiquetas_dentro))

        # DBCV va sobre la proyeccion COMPLETA y no sobre la muestra: trabaja
        # con arboles de expansion minima sobre 5 dimensiones, que es mucho mas
        # barato que la matriz de distancias en 1.024. Si algun dia deja de
        # serlo, el error se captura aqui abajo y la validacion sigue.
        try:
            from hdbscan.validity import validity_index
            salida["dbcv"] = float(validity_index(
                np.asarray(proyeccion, dtype=np.float64)[dentro],
                etiquetas[dentro], metric="euclidean"))
        except Exception as error:
            salida["dbcv_error"] = str(error)

    return salida


# ==========================================================
# 3. LA PREGUNTA DE FONDO: HAY ESTRUCTURA O LA FABRICA EL METODO
# ==========================================================

def modelo_nulo(vectores, n_notas, semilla=SEMILLA, aviso=print, **config):
    """
    Corre el pipeline entero sobre datos sin estructura y compara.

    ES LA UNICA PRUEBA QUE PUEDE INVALIDAR TODO EL ENFOQUE
        UMAP + HDBSCAN encuentran grupos en cualquier cosa. UMAP construye el
        grafo de k vecinos incluso sobre ruido puro -- todo punto tiene quince
        vecinos mas cercanos que el resto -- y al proyectarlo produce las
        manchas caracteristicas que HDBSCAN despues llama clusters. Es un modo
        de fallo conocido del metodo, no una rareza.

        Asi que 155 grupos con coherencia 0,85 no significan nada hasta saber
        cuantos grupos y cuanta coherencia salen del mismo pipeline corriendo
        sobre datos donde por construccion no hay nada que encontrar.

    COMO SE CONSTRUYE EL NULO
        Permutando cada una de las 1.024 dimensiones por separado entre los
        textos. Eso conserva la distribucion de cada dimension y por tanto la
        anisotropia de bge-m3 -- el nulo sale con el mismo coseno medio entre
        pares, 0,463 contra 0,464 del real -- y destruye la unica cosa que hace
        a un texto un texto: que sus 1.024 numeros vayan juntos.

        Es el nulo correcto aqui. Uno de vectores gaussianos seria mas facil y
        no serviria: no tendria la anisotropia, y cualquier diferencia se
        podria atribuir a eso en vez de a la estructura.

    LO QUE DIO, Y COMO SE LEE
        Medido sobre los 5.020 textos:

                            grupos   ruido_n   coherencia   nulo   ganancia
            datos reales      155     15,9%       0,851    0,728    +0,122
            nulo permutado    139     43,2%       0,725    0,726    -0,001

        El nulo produce 139 grupos. Eso confirma que CONTAR GRUPOS NO ES
        EVIDENCIA DE NADA: el metodo los fabrica sobre datos vacios casi en la
        misma cantidad. Lo que separa a los dos es todo lo demas -- el nulo
        deja fuera el 43% de las notas y su coherencia queda EXACTAMENTE en su
        propio suelo: ganancia -0,001, o sea cero. Toda su coherencia de 0,725
        es el suelo aritmetico y nada mas.

        Conclusion: la estructura es real. Lo que no es evidencia es el numero
        de grupos, y ese era el numero que encabezaba el informe.
    """
    azar = np.random.default_rng(semilla)

    falsos = np.asarray(vectores, dtype=np.float64).copy()
    for columna in range(falsos.shape[1]):
        falsos[:, columna] = falsos[azar.permutation(len(falsos)), columna]
    falsos /= np.linalg.norm(falsos, axis=1, keepdims=True)
    falsos = falsos.astype(np.float32)

    aviso("    reduciendo el nulo ...")
    proyeccion = agrupar.proyectar(falsos, **_config_umap(config))
    etiquetas, _ = agrupar.agrupar(proyeccion, **_config_hdbscan(config))

    resumen = agrupar.resumen(etiquetas, n_notas)
    resumen.update(calibrar(falsos, etiquetas, n_notas, semilla=semilla))
    resumen["coseno_par"] = coseno_par(falsos, semilla)
    return resumen


def coseno_par(vectores, semilla=SEMILLA, muestras=100_000):
    """
    Coseno medio entre pares al azar. Es la vara con la que se lee todo lo
    demas, y se recalcula en cada corrida en vez de dejarla escrita: el 0,4636
    de hoy es una propiedad de ESTE corpus y se mueve cuando el corpus crece.
    """
    vectores = np.asarray(vectores, dtype=np.float64)
    azar = np.random.default_rng(semilla)
    pares = azar.integers(0, len(vectores), size=(muestras, 2))
    pares = pares[pares[:, 0] != pares[:, 1]]
    valores = np.einsum("ij,ij->i",
                        vectores[pares[:, 0]], vectores[pares[:, 1]])
    return float(valores.mean())


def centrado(vectores, textos, n_notas, semilla=agrupar.SEMILLA, aviso=print,
             **config):
    """
    Probar el remedio estandar de la anisotropia y ver si mejora algo. NO mejora.

    NO ENTRA EN ejecutar() A PROPOSITO
        Las demas pruebas de este modulo vigilan una corrida y hay que repetirlas
        cada vez que el corpus crece. Esta responde una pregunta de diseno que se
        contesta una vez -- 'habria que centrar los vectores' -- y cuesta cuatro
        reducciones. Se llama a mano cuando se dude de la decision o cuando se
        cambie el modelo de embeddings, que es cuando la respuesta podria ser
        otra.

    LA PREGUNTA
        bge-m3 concentra sus vectores en un cono estrecho -- anisotropia 0,68,
        coseno medio entre frases sin relacion 0,46 -- y agrupar.py trata eso
        como un hecho al que hay que adaptarse. La alternativa obvia es
        corregirlo: restar el centroide global y renormalizar deja la
        anisotropia en 0,013 y el coseno medio en 0,000, o sea un espacio donde
        'parecido' vuelve a significar lo que uno espera.

        Si eso mejorara el agrupamiento habria que hacerlo. Esta funcion lo mide
        en vez de suponerlo, en las dos unicas varas que sirven para comparar
        dos espacios distintos: la silueta y el catalogo clinico.

    LO QUE DIO, SOBRE LOS 5.020 TEXTOS

                          grupos  ruido_n  silueta  pureza-catalogo  ARI-semilla
        original            155    15,9%    0,115       0,779           0,477
        centrado            161    17,5%    0,124       0,773           0,420

        No mejora. La silueta sube nueve milesimas, la pureza contra el
        catalogo baja seis, y la estabilidad ante la semilla EMPEORA. Nada de
        eso es una diferencia: todo cae dentro del ruido que ya tiene el metodo.

    POR QUE NO MEJORA, QUE ES LO QUE VALIDA EL DISENO ACTUAL
        Porque la anisotropia desplaza TODOS los cosenos casi por igual, y lo
        unico que UMAP mira es el ORDEN de los vecinos, que un desplazamiento
        comun no cambia. Es exactamente el argumento que agrupar.py ya daba
        cuando decia que aqui nunca se decide nada con un umbral absoluto de
        similitud, sino con vecindad relativa. Esta medicion lo confirma: si el
        metodo fuera sensible a la anisotropia, corregirla tendria que haber
        hecho algo.

    UNA TRAMPA AL LEER ESTO
        La ganancia de coherencia sube de +0,122 a +0,391 con el centrado, y
        eso NO significa que el centrado sea mejor. El nulo tambien cambia --
        cae de 0,728 a 0,305 -- porque es otro espacio. La ganancia corrige el
        tamano de grupo, no el cambio de espacio, asi que solo se compara entre
        corridas sobre los MISMOS vectores. Para comparar espacios distintos
        quedan la silueta y la validacion externa, que es por lo que la tabla de
        arriba lleva esas dos columnas y no la ganancia.
    """
    from sklearn.metrics import adjusted_rand_score, silhouette_score

    originales = np.asarray(vectores, dtype=np.float64)
    centrados = originales - originales.mean(axis=0)
    centrados /= np.linalg.norm(centrados, axis=1, keepdims=True)

    filas = []
    for nombre, densos in (("original", originales), ("centrado", centrados)):
        aviso(f"    {nombre} ...")
        flotantes = densos.astype(np.float32)
        etiquetas, _ = agrupar.agrupar(
            agrupar.proyectar(flotantes, semilla=semilla, **_config_umap(config)),
            **_config_hdbscan(config))
        dentro = etiquetas != -1
        otras, _ = agrupar.agrupar(
            agrupar.proyectar(flotantes, semilla=semilla + 1,
                              **_config_umap(config)),
            **_config_hdbscan(config))
        filas.append({
            "espacio": nombre,
            "anisotropia": anisotropia(densos),
            "coseno_par": coseno_par(densos),
            **agrupar.resumen(etiquetas, n_notas),
            "silueta": float(silhouette_score(
                densos[dentro], etiquetas[dentro], metric="cosine")),
            "pureza": externa(textos, etiquetas).get("pureza", float("nan")),
            "ari_semilla": float(adjusted_rand_score(etiquetas, otras)),
        })
    return filas


def anisotropia(vectores):
    """
    Cuanto se aparta bge-m3 de repartir sus vectores por toda la esfera.

    Es la norma del centroide de TODO el corpus. Con 0 los vectores apuntan a
    todas partes y se cancelan; con 1 apuntan todos al mismo sitio. Aqui da
    0,68, que es mucho: los 1.024 numeros viven en un cono estrecho y esa es la
    causa de que el coseno medio entre frases sin relacion sea 0,46 en vez de 0.

    Esta medido porque es el origen de los dos problemas del modulo -- el suelo
    de la coherencia y la falta de zonas vacias que obliga a reducir antes de
    agrupar -- y conviene verlo moverse cuando cambie el corpus o el modelo.

    Corregirla se puede -- restar el centroide global la deja en 0,013 -- y no
    sirve de nada: ver centrado(), que lo mide. UMAP solo mira el orden de los
    vecinos, y un desplazamiento comun de todos los cosenos no lo cambia.
    """
    vectores = np.asarray(vectores, dtype=np.float64)
    return float(np.linalg.norm(vectores.mean(axis=0)))


# ==========================================================
# 4. ESTABILIDAD -- LO QUE AQUI HACE LAS VECES DE VALIDACION CRUZADA
# ==========================================================
#
# No hay validacion cruzada en el sentido supervisado: no hay etiqueta que
# predecir ni error que medir sobre datos que el modelo no vio. Pedirla es
# pedir algo que no existe para este problema.
#
# Lo que si existe y responde a la misma inquietud -- 'esto es del corpus o de
# esta corrida' -- es la estabilidad: repetir el agrupamiento cambiando algo
# que NO deberia cambiar el resultado, y medir cuanto cambio. Se mide con ARI,
# que compara dos particiones corrigiendo por el acuerdo que saldria del azar:
# 1,0 es la misma particion y 0,0 es el acuerdo del azar.
#
# Se cambian dos cosas y fallan por motivos distintos:
#
#   la semilla    si el resultado se mueve, lo que manda es el azar interno de
#                 UMAP y no los datos. random_state=42 no resuelve eso: fija el
#                 sorteo, no lo elimina, y lo esconde de la vista.
#   los datos     quitando el 20% de los textos, los grupos que describen algo
#                 real siguen ahi y los que eran casualidad no. Es la prueba
#                 mas dura de las dos y la que mas se parece a validar.
#
# ARI y AMI dicen cosas distintas y hay que mirar las dos. ARI cuenta pares de
# textos que siguen juntos; parte un grupo en dos y se desploma. AMI mide
# informacion compartida y tolera esa particion si es consistente. Un ARI bajo
# con AMI alto -- que es lo que da aqui -- significa que la ESTRUCTURA se
# conserva y las FRONTERAS finas no.
#
# Una salvedad al leer las dos: el ruido entra como si fuera un grupo mas. Las
# dos corridas marcan como -1 una porcion parecida del corpus, y ese acuerdo
# cuenta como acierto, asi que estas cifras tiran hacia arriba. Es decir: la
# estabilidad real es algo PEOR que la que sale aqui, no mejor. Se deja asi
# porque sacar el ruido obligaria a elegir entre comparar solo los textos que
# ninguna corrida descarto -- que son los faciles -- y no comparar nada.


def estabilidad_semilla(vectores, etiquetas, semillas=SEMILLAS_ALTERNAS,
                        aviso=print, **config):
    """
    ARI contra la corrida de referencia al cambiar solo random_state.

    Sobre los 5.020 textos da ARI entre 0,47 y 0,53 con AMI entre 0,79 y 0,81.
    Es el resultado mas incomodo de todo el modulo y hay que tenerlo presente
    al leer cualquier salida del paquete: cambiar un numero que no toca los
    datos reparte de otra forma la mitad de los pares de textos.

    No invalida el agrupamiento -- el AMI alto dice que los temas grandes son
    los mismos, y la validacion externa lo confirma -- pero si invalida dos
    usos concretos: comparar el cluster 37 de hoy con el cluster 37 de la
    semana pasada, y leer un grupo pequeno como si fuera un hallazgo firme.
    """
    from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

    etiquetas = np.asarray(etiquetas)
    filas = []
    for semilla in semillas:
        aviso(f"    semilla {semilla} ...")
        otras, _ = agrupar.agrupar(
            agrupar.proyectar(vectores, semilla=semilla, **_config_umap(config)),
            **_config_hdbscan(config))
        filas.append({
            "semilla": semilla,
            "ari": float(adjusted_rand_score(etiquetas, otras)),
            "ami": float(adjusted_mutual_info_score(etiquetas, otras)),
            "clusters": int(len(set(otras) - {-1})),
        })
    return filas


def estabilidad_datos(vectores, etiquetas, fraccion=SUBMUESTRA,
                      repeticiones=REPETICIONES_SUBMUESTRA, semilla=SEMILLA,
                      aviso=print, **config):
    """
    ARI sobre los textos compartidos al reagrupar submuestras del corpus.

    Se compara solo sobre los textos que estan en las dos corridas, que es lo
    unico comparable. Un ARI alto dice que los grupos no dependen de que
    estuviera ese 20% concreto; uno bajo dice que el agrupamiento se rehace
    entero cada vez que llegan datos nuevos, y entonces no se puede comparar la
    corrida de hoy con la de la semana pasada -- que es justo lo que el proyecto
    va a querer hacer cuando cruce esto contra el calendario.

    Hay que leerlo junto a estabilidad_semilla(): si el ARI de submuestra se
    parece al de semilla, quitar datos no hace mas dano que volver a tirar el
    dado, y entonces lo inestable es el metodo y no la sensibilidad al corpus.

    LO QUE DIO, Y ES EL RESULTADO MAS SERIO DE TODO EL MODULO
        Sobre los 5.020 textos, tres submuestras del 80%:

            ARI   0,313   0,315   0,246      (entre semillas: 0,47 a 0,53)
            AMI   0,694   0,713   0,667      (entre semillas: 0,79 a 0,81)
            grupos  128     124     129      (referencia: 155)

        Quitar el 20% del corpus hace CLARAMENTE mas dano que volver a tirar el
        dado: el ARI cae a la mitad. Y el numero de grupos cae un 18% quitando
        un 20% de los textos, que es casi proporcional -- senal de que buena
        parte de los 155 grupos existen porque estaban esos textos concretos, no
        porque haya 155 patrones en el corpus.

        Lo que NO significa: que el agrupamiento sea falso. El AMI sigue en
        0,69 y la validacion externa aguanta, asi que los temas grandes son
        reales y estables. Lo que se deshace es el grano fino.

        Lo que SI significa, y hay que tenerlo en cuenta antes del cruce
        temporal: el cluster 37 de hoy no es el cluster 37 de la semana que
        viene, y un grupo de 10 o 12 textos no es un hallazgo -- es lo que el
        metodo devolvio esta vez. Contar series por numero de grupo o de tema a
        lo largo de semanas va a producir saltos que parecen senal y son la
        renumeracion. Para eso hace falta anclar los temas, que es exactamente
        lo que temas.py ya anticipa cuando habla de definirlos por terminos
        semilla.
    """
    from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

    etiquetas = np.asarray(etiquetas)
    azar = np.random.default_rng(semilla)
    filas = []
    for repeticion in range(repeticiones):
        aviso(f"    submuestra {repeticion + 1}/{repeticiones} ...")
        muestra = np.sort(azar.choice(len(vectores),
                                      size=int(fraccion * len(vectores)),
                                      replace=False))
        otras, _ = agrupar.agrupar(
            agrupar.proyectar(vectores[muestra], **_config_umap(config)),
            **_config_hdbscan(config))
        filas.append({
            "repeticion": repeticion + 1,
            "ari": float(adjusted_rand_score(etiquetas[muestra], otras)),
            "ami": float(adjusted_mutual_info_score(etiquetas[muestra], otras)),
            "clusters": int(len(set(otras) - {-1})),
        })
    return filas


def acuerdo_dimensiones(vectores, etiquetas, n_notas,
                        candidatas=DIMENSIONES_PRUEBA, aviso=print, **config):
    # El parametro se llama 'candidatas' y no 'dimensiones' porque **config
    # trae la dimension de la corrida vigente con ese nombre, y chocaban: la
    # lista de dimensiones a probar quedaba sustituida por el entero 5.
    """
    Cuanto coinciden las particiones que salen de reducir a distinta dimension.

    POR QUE ESTO NO LO RESPONDIA EL BARRIDO
        El barrido comparo dimensiones por sus AGREGADOS -- cuantos grupos,
        cuanto ruido, cuanta coherencia -- y al ver que casi no se movian
        concluyo que la dimension no hace nada. El agregado no autoriza esa
        conclusion: dos particiones pueden tener el mismo numero de grupos, el
        mismo ruido y la misma coherencia y repartir el corpus de forma
        completamente distinta. Los agregados serian identicos y ningun texto
        estaria con los mismos companeros.

        Esto lo mide directo, con ARI.

    LO QUE DIO
        ARI de 0,54 contra dimensiones 10 y de 0,45 contra 30 -- es decir, el
        mismo orden que el ARI entre dos semillas de la MISMA configuracion,
        que va de 0,47 a 0,53.

        Esa coincidencia es la que cierra el asunto, y de una forma mas honesta
        que el barrido: cambiar la dimension no mueve la particion mas de lo
        que la mueve volver a tirar el dado. DIMENSIONES = 5 queda justificada.

        Lo que la coincidencia dice tambien, y hay que decirlo, es que la
        justificacion no es 'la dimension no importa' sino 'nada es preciso a
        ese nivel'. Es el mismo hecho leido desde el otro lado.
    """
    from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

    etiquetas = np.asarray(etiquetas)
    filas = []
    for dimension in candidatas:
        aviso(f"    dimensiones {dimension} ...")
        proyeccion = agrupar.proyectar(
            vectores, **{**_config_umap(config), "dimensiones": dimension})
        otras, _ = agrupar.agrupar(proyeccion, **_config_hdbscan(config))
        resumen = agrupar.resumen(otras, n_notas)
        filas.append({
            "dimensiones": dimension,
            "ari": float(adjusted_rand_score(etiquetas, otras)),
            "ami": float(adjusted_mutual_info_score(etiquetas, otras)),
            "clusters": resumen["clusters"],
            "ruido_notas": resumen["ruido_notas"],
            "ganancia": calibrar(vectores, otras, n_notas)["ganancia"],
        })
    return filas


def _config_umap(config):
    return {clave: valor for clave, valor in config.items()
            if clave in ("dimensiones", "vecinos", "distancia_minima")}


def _config_hdbscan(config):
    return {clave: valor for clave, valor in config.items()
            if clave in ("tamano_minimo", "muestras_minimas", "epsilon")}


# ==========================================================
# 5. EL CODO, QUE AQUI SOLO APLICA AL NIVEL DE TEMAS
# ==========================================================

def codo_temas(vectores, etiquetas, n_notas, umbrales=UMBRALES_TEMA):
    """
    Si existe un numero natural de temas, y si el umbral 0,70 cae cerca de el.

    POR QUE EL CODO NO SE PUEDE APLICAR AL NIVEL DE GRUPOS
        El grafico del codo es la inercia de k-means en funcion de k, y busca
        el k a partir del cual anadir grupos deja de pagar. Necesita dos cosas
        que aqui no hay: un k que se elija a mano y una inercia que baje de
        forma monotona con el. HDBSCAN no recibe un numero de grupos -- lo
        deduce de la densidad -- y no minimiza ninguna inercia. Dibujar un codo
        sobre el seria dibujar la curva de otro algoritmo.

        Donde SI aplica el razonamiento del codo es un nivel mas arriba, en la
        fusion en temas, porque ahi si hay una jerarquia con un numero de temas
        que se elige. El equivalente correcto no es la inercia sino la ALTURA
        DE FUSION del dendrograma: a que distancia se cierra cada union. Un
        salto grande significa que para seguir fundiendo hubo que juntar cosas
        bastante mas distintas, y ahi esta el codo.

    POR QUE ADEMAS HACIA FALTA MIRAR ESTO
        Porque la metrica con la que el informe justifica el umbral no puede
        justificarlo. 'separacion' es el coseno medio entre grupos del mismo
        tema, y el enlace completo GARANTIZA por construccion que ningun par
        dentro de un tema baje del umbral. Subir el umbral sube la separacion
        necesariamente, sin que eso diga nada sobre si los temas son mejores:

            umbral    0,60   0,64   0,68   0,70   0,75   0,80
            temas       16     24     35     41     60     91
            separac  0,754  0,781  0,794  0,801  0,829  0,858

        Esa columna no es evidencia, es el parametro escrito de otra forma. La
        silueta sobre los centroides, que si puede bajar, se queda plana entre
        0,12 y 0,15 en todo el rango.

    LO QUE DIO
        No hay codo cerca de 41 temas. Los saltos grandes del dendrograma estan
        en 7 temas y en 2, muy lejos. Entre 8 y 60 temas la curva sube lisa.

        La lectura no es que 0,70 este mal, es que el corpus NO TIENE un numero
        natural de temas y ninguna medida interna va a elegirlo. 0,70 es una
        decision de granularidad, legitima como tal, y hay que dejar de
        presentarla como si un numero la respaldara. Lo que si puede respaldar
        una eleccion aqui es la validacion externa -- externa() -- o el juicio
        clinico sobre la tabla de temas.
    """
    from scipy.cluster.hierarchy import linkage
    from scipy.spatial.distance import pdist
    from sklearn.metrics import silhouette_score

    grupos, puntos, pesos = temas.centroides(vectores, etiquetas, n_notas)
    if len(grupos) < 3:
        return {"grupos": len(grupos)}

    distancias = pdist(puntos, metric="cosine")
    jerarquia = linkage(distancias, method="complete")
    alturas = jerarquia[:, 2]

    # Una fila por 'si se cortara aqui': cuantos temas quedan y que salto hubo
    # que pagar para llegar a ese numero desde el siguiente.
    saltos = []
    for posicion in range(1, len(alturas)):
        saltos.append({
            "temas": int(len(alturas) - posicion),
            "distancia": float(alturas[posicion]),
            "similitud": float(1.0 - alturas[posicion]),
            "salto": float(alturas[posicion] - alturas[posicion - 1]),
        })

    filas = []
    for umbral in umbrales:
        mapa = temas.fundir(vectores, etiquetas, n_notas, umbral=umbral)
        asignado = np.array([mapa[c] for c in grupos])
        cuantos = len(set(asignado))
        peso_tema = {t: pesos[asignado == t].sum() for t in set(asignado)}
        filas.append({
            "umbral": umbral,
            "temas": cuantos,
            "solos": int(sum(1 for t in set(asignado)
                             if (asignado == t).sum() == 1)),
            "separacion": temas.separacion(vectores, etiquetas, n_notas, mapa),
            "silueta": (float(silhouette_score(puntos, asignado, metric="cosine"))
                        if 1 < cuantos < len(asignado) else float("nan")),
            "mayor": float(max(peso_tema.values()) / pesos.sum()),
        })

    return {
        "grupos": len(grupos),
        "coseno_entre_centroides": float((1.0 - distancias).mean()),
        "saltos": sorted(saltos, key=lambda f: f["temas"])[:15],
        "umbrales": filas,
    }


# ==========================================================
# 6. LA UNICA VALIDACION QUE MIRA AFUERA
# ==========================================================

def externa(textos, etiquetas, catalogo=None):
    """
    Contrastar los grupos contra una categorizacion clinica hecha por humanos.

    POR QUE ESTA ES LA MAS IMPORTANTE DE TODAS
        Todo lo demas de este modulo es interno: mide el agrupamiento con la
        misma geometria que lo produjo. Eso detecta que algo sea ruido, pero no
        puede decir si lo que encontro SIGNIFICA algo -- una particion puede ser
        perfectamente estable, perfectamente separada y no corresponder a
        ninguna distincion que le importe a nadie.

        Para responder eso hace falta una referencia de afuera, y el proyecto ya
        tiene una que no se estaba usando aqui: embedding/datos/
        catalogo_sintomas.json, donde 82 sintomas canonicos con sus 393
        variantes de escritura estan asignados a mano a 18 categorias clinicas.
        Nadie se la enseno a bge-m3 ni a UMAP ni a HDBSCAN.

    COMO SE USA
        A cada texto se le busca la variante mas larga que contenga y se le
        asigna la categoria de esa variante, resolviendo los empates con la
        prioridad que el propio catalogo trae. Eso etiqueta el 64% de los
        textos; el resto no menciona ningun sintoma del catalogo y no entra.

        Despues se comparan las dos particiones. La pureza es la fraccion de
        cada grupo que cae en su categoria mayoritaria.

    LO QUE DIO
        Sobre los 2.537 textos que tienen categoria y ademas cayeron en algun
        grupo:

            pureza media ponderada    0,779    (la categoria mas comun es 0,232)
            AMI                       0,407
            ARI                       0,104

        Casi cuatro de cada cinco textos de un grupo comparten categoria
        clinica, contra el 23% que daria adivinar siempre la mas frecuente. El
        agrupamiento recupera distinciones clinicas reales sin que nadie se las
        haya dado.

        El ARI bajo no contradice eso: hay 155 grupos para 18 categorias, asi
        que el agrupamiento parte cada categoria en muchos pedazos y ARI
        castiga eso duramente. La pareja 'pureza alta, ARI bajo' es la firma de
        un agrupamiento mas FINO que la referencia, no de uno equivocado.

    LO QUE NO PRUEBA
        El catalogo se construyo mirando este mismo corpus, asi que comparte su
        vocabulario y no es una referencia independiente del todo. Y cubre el
        64% de los textos: el 36% restante -- la cola larga, que es lo que mas
        interesa describir -- queda sin verificar por esta via.
    """
    import json

    from embedding import rutas as rutas_emb

    ruta = catalogo or (rutas_emb.DATOS / "catalogo_sintomas.json")
    if not ruta.exists():
        return {"error": f"no esta {ruta}"}

    contenido = json.loads(ruta.read_text(encoding="utf-8"))
    prioridad = {categoria: orden for orden, categoria
                 in enumerate(contenido.get("_prioridad_categorias", []))}

    # Las variantes se prueban de mas larga a mas corta: 'dolor abdominal' debe
    # ganarle a 'dolor', igual que hace FlashText en extraccion.py.
    variantes = sorted(
        ((texto.lower(), datos["categoria"])
         for datos in contenido["sintomas"].values()
         for texto in datos["variantes"]),
        key=lambda par: -len(par[0]))

    def categoria_de(texto):
        texto = str(texto).lower()
        encontradas = {cat for var, cat in variantes if var in texto}
        if not encontradas:
            return None
        return min(encontradas, key=lambda c: prioridad.get(c, 999))

    categorias = textos["texto"].map(categoria_de).to_numpy()
    etiquetas = np.asarray(etiquetas)

    comparables = np.array([c is not None for c in categorias]) & (etiquetas != -1)
    salida = {
        "textos_con_categoria": int(sum(c is not None for c in categorias)),
        "textos": int(len(categorias)),
        "comparables": int(comparables.sum()),
    }
    if comparables.sum() < 2:
        return salida

    from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

    referencia = categorias[comparables].astype(str)
    obtenidas = etiquetas[comparables]

    purezas, pesos = [], []
    for grupo in set(obtenidas):
        cuales = referencia[obtenidas == grupo]
        _, cuentas = np.unique(cuales, return_counts=True)
        purezas.append(cuentas.max() / len(cuales))
        pesos.append(len(cuales))

    _, frecuencias = np.unique(referencia, return_counts=True)

    salida.update({
        "ami": float(adjusted_mutual_info_score(referencia, obtenidas)),
        "ari": float(adjusted_rand_score(referencia, obtenidas)),
        "pureza": float(np.average(purezas, weights=pesos)),
        "pureza_azar": float(frecuencias.max() / frecuencias.sum()),
        "categorias": int(len(frecuencias)),
    })
    return salida


# ==========================================================
# 7. EL TRUNCAMIENTO, QUE ES UNA DECISION DE embedding/ Y NO DE AQUI
# ==========================================================

def truncamiento(limite=None):
    """
    Cuantos textos pierden contenido por la ventana de 128 tokens.

    Se valida aqui aunque la decision viva en embedding/modelo.py porque es la
    unica de esa fase que puede cambiar en silencio lo que ve el agrupamiento:
    un texto cortado se vectoriza a medias y cae en el grupo equivocado sin que
    nada avise.

    EL DOCSTRING DE embedding/modelo.py JUSTIFICA 128 CON UN NUMERO QUE NO ES
        Dice que la mediana es 6 palabras y el maximo 60, 'con 128 tokens entra
        el peor caso entero y sobra sitio'. El error esta en confundir palabras
        con tokens: sobre este corpus bge-m3 gasta 1,99 tokens por palabra -- el
        vocabulario espanol clinico se parte mucho -- asi que 60 palabras son
        unos 120 tokens y el margen que se creia tener no existe.

        Medido sobre el vocabulario real: mediana 13 tokens, percentil 99 en 95
        y maximo 170. Se truncan 10 textos de 5.020 (0,20%), que son 10 notas
        de 6.751 (0,15%), y el peor pierde 42 tokens.

    LA CONCLUSION IGUAL AGUANTA, PERO POR POCO Y HAY QUE VIGILARLA
        0,15% de las notas es despreciable y la decision de 128 se sostiene. Lo
        que no se sostiene es el razonamiento escrito, y por eso esto se mide en
        cada corrida en vez de confiar en el: los textos largos son las notas de
        ingreso con antecedentes, el tipo de nota que mas crece cuando se sumen
        servicios nuevos al corpus.
    """
    import pandas as pd

    from embedding import modelo, rutas as rutas_emb

    limite = limite or modelo.LONGITUD_MAXIMA
    if not rutas_emb.VOCABULARIO.exists():
        return {"error": "todavia no hay vocabulario"}

    try:
        from transformers import AutoTokenizer
        tokenizador = AutoTokenizer.from_pretrained(modelo.MODELO)
    except Exception as error:
        return {"error": f"no se pudo cargar el tokenizador: {error}"}

    vocabulario = pd.read_parquet(rutas_emb.VOCABULARIO)
    indice = pd.read_parquet(rutas_emb.INDICE)

    largos = np.asarray(tokenizador(
        vocabulario["texto"].tolist(),
        add_special_tokens=True, return_length=True)["length"])

    notas_por_fila = indice.groupby("fila").size()
    pesos = np.array([notas_por_fila.get(fila, 0)
                      for fila in range(len(vocabulario))])

    cortados = largos > limite
    return {
        "limite": int(limite),
        "mediana": int(np.median(largos)),
        "p99": int(np.percentile(largos, 99)),
        "maximo": int(largos.max()),
        "textos_cortados": int(cortados.sum()),
        "textos": int(len(largos)),
        "notas_cortadas": int(pesos[cortados].sum()),
        "notas": int(pesos.sum()),
        "tokens_por_palabra": float(np.mean(
            largos / vocabulario["texto"].str.split().str.len().to_numpy())),
    }


# ==========================================================
# 8. LA CORRIDA COMPLETA
# ==========================================================

def ejecutar(minimo_notas=1, rapido=False, aviso=print, **config):
    """
    Corre todas las pruebas sobre el corpus de hoy y devuelve el resultado.

    Con rapido=True se omiten las cuatro que vuelven a reducir -- el modelo
    nulo, las semillas, las dimensiones y las submuestras -- y queda lo que se
    calcula sobre la unica reduccion que de todos modos hay que hacer.

    Lo primero que hace es reducir y agrupar con la configuracion vigente, para
    que todo lo demas se mida contra ESA corrida y no contra una guardada que
    puede ser de otro dia y de otro corpus.
    """
    import time

    from clustering import corpus

    textos, vectores, indice = corpus.instantanea(minimo_notas=minimo_notas)
    n_notas = textos["n_notas"].to_numpy()
    densos = np.asarray(vectores, dtype=np.float64)
    aviso(f"{len(textos):,} textos distintos / {n_notas.sum():,} notas")

    aviso("  corrida de referencia ...")
    inicio = time.time()
    proyeccion = agrupar.proyectar(vectores, **_config_umap(config))
    etiquetas, _ = agrupar.agrupar(proyeccion, **_config_hdbscan(config))
    aviso(f"    {time.time() - inicio:.0f}s")

    resultado = {
        "config": {
            "vecinos": config.get("vecinos", agrupar.VECINOS),
            "dimensiones": config.get("dimensiones", agrupar.DIMENSIONES),
            "tamano_minimo": config.get("tamano_minimo", agrupar.TAMANO_MINIMO),
            "muestras_minimas": config.get("muestras_minimas",
                                           agrupar.MUESTRAS_MINIMAS),
            "epsilon": config.get("epsilon", agrupar.EPSILON),
            "minimo_notas": minimo_notas,
        },
        "resumen": agrupar.resumen(etiquetas, n_notas),
        "coseno_par": coseno_par(densos),
        "anisotropia": anisotropia(densos),
        "rapido": rapido,
    }

    aviso("  calibrando la coherencia contra su nulo ...")
    resultado["calibracion"] = calibrar(densos, etiquetas, n_notas)

    aviso("  siluetas ...")
    resultado["siluetas"] = siluetas(densos, proyeccion, etiquetas)

    aviso("  codo y umbral de temas ...")
    resultado["temas"] = codo_temas(densos, etiquetas, n_notas)

    aviso("  validacion externa contra el catalogo de sintomas ...")
    resultado["externa"] = externa(textos, etiquetas)

    aviso("  truncamiento de la ventana de embedding ...")
    resultado["truncamiento"] = truncamiento()

    if not rapido:
        aviso("  modelo nulo (esto tarda) ...")
        resultado["nulo"] = modelo_nulo(densos, n_notas, aviso=aviso, **config)

        aviso("  estabilidad ante la semilla ...")
        resultado["semillas"] = estabilidad_semilla(
            vectores, etiquetas, aviso=aviso, **config)

        aviso("  acuerdo entre dimensiones ...")
        resultado["dimensiones"] = acuerdo_dimensiones(
            vectores, etiquetas, n_notas, aviso=aviso, **config)

        aviso("  estabilidad ante los datos ...")
        resultado["submuestras"] = estabilidad_datos(
            vectores, etiquetas, aviso=aviso, **config)

    return resultado


# ==========================================================
# EL INFORME
# ==========================================================
#
# Cada bloque dice el numero, contra que se compara y que hacer si sale mal.
# Un informe de validacion que solo imprima cifras obliga a recordar como se
# leia cada una, y lo que se olvida es justamente el punto de comparacion --
# que es donde estaba el error que dio origen a este modulo.

def _bloque_coherencia(res):
    cal = res["calibracion"]
    sil = res["siluetas"]
    return [
        "1. LA COHERENCIA CONTRA SU SUELO",
        "",
        f"   coherencia         {cal['real']:.3f}",
        f"   suelo (nulo)       {cal['nulo']:.3f}   mismos tamanos de grupo, "
        f"etiquetas barajadas",
        f"   GANANCIA           {cal['ganancia']:+.3f}   <- esto es lo que hay "
        f"que mirar",
        "",
        "   El suelo NO es 0,47. Ese es el coseno entre dos frases al azar;",
        "   la coherencia compara una frase con la MEDIA de su grupo, y",
        "   promediar acerca. El suelo depende del tamano del grupo y por eso",
        "   se recalcula barajando en cada corrida.",
        "",
        f"   silueta (bge-m3)   {sil['silueta_bge']:.3f}   separacion entre "
        f"grupos; 0 = pegados, 1 = aislados"
        + (f"   [sobre {sil.get('textos_muestra', 0):,} textos: es cuadratica]"
           if sil.get("muestreada") else ""),
        f"   DBCV (UMAP)        {sil['dbcv']:.3f}   validez de densidad, en los "
        f"terminos de HDBSCAN",
        "",
        "   La silueta baja es esperable en embeddings de texto y no es una",
        "   alarma por si sola, pero es el unico numero del informe que puede",
        "   caer si el agrupamiento parte grupos reales en pedazos. La",
        "   coherencia no puede: partir un grupo la sube.",
    ]


def _bloque_nulo(res):
    if "nulo" not in res:
        return []
    nulo = res["nulo"]
    real = res["resumen"]
    cal = res["calibracion"]
    return [
        "",
        "2. HAY ESTRUCTURA, O LA FABRICA EL METODO",
        "",
        "   El mismo pipeline sobre vectores con cada dimension permutada por",
        "   separado: misma anisotropia, cero estructura conjunta.",
        "",
        f"   {'':<18}{'grupos':>8}{'ruido_n':>10}{'coherencia':>13}{'ganancia':>11}",
        f"   {'datos reales':<18}{real['clusters']:>8}"
        f"{real['ruido_notas']:>9.1%}{cal['real']:>13.3f}{cal['ganancia']:>+11.3f}",
        f"   {'nulo permutado':<18}{nulo['clusters']:>8}"
        f"{nulo['ruido_notas']:>9.1%}{nulo['real']:>13.3f}{nulo['ganancia']:>+11.3f}",
        "",
        "   El nulo tambien produce grupos: CONTAR GRUPOS NO ES EVIDENCIA DE",
        "   NADA. Lo que separa a los dos es el ruido y la ganancia. Si se",
        "   parecieran en esas dos columnas, todo lo construido encima seria",
        "   una alucinacion del metodo.",
    ]


def _bloque_estabilidad(res):
    if "semillas" not in res:
        return []
    lineas = [
        "",
        "3. ESTABILIDAD -- LO QUE AQUI HACE LAS VECES DE VALIDACION CRUZADA",
        "",
        "   No hay validacion cruzada supervisada: no hay etiqueta que predecir.",
        "   Lo equivalente es repetir cambiando algo que no deberia importar.",
        "   ARI 1,0 = la misma particion; 0,0 = el acuerdo del azar.",
        "   ARI cuenta pares que siguen juntos y castiga partir un grupo; AMI",
        "   mide informacion compartida y lo tolera. ARI bajo con AMI alto =",
        "   la estructura aguanta y las fronteras finas no.",
        "",
        f"   {'cambio':<26}{'ARI':>8}{'AMI':>8}{'grupos':>9}",
    ]
    for fila in res["semillas"]:
        lineas.append(f"   {'semilla ' + str(fila['semilla']):<26}"
                      f"{fila['ari']:>8.3f}{fila['ami']:>8.3f}"
                      f"{fila['clusters']:>9}")
    for fila in res.get("dimensiones", []):
        lineas.append(f"   {'dimensiones ' + str(fila['dimensiones']):<26}"
                      f"{fila['ari']:>8.3f}{fila['ami']:>8.3f}"
                      f"{fila['clusters']:>9}")
    for fila in res.get("submuestras", []):
        lineas.append(f"   {'submuestra 80% #' + str(fila['repeticion']):<26}"
                      f"{fila['ari']:>8.3f}{fila['ami']:>8.3f}"
                      f"{fila['clusters']:>9}")
    lineas += [
        "",
        "   COMO SE LEE, Y ES LA PARTE MAS IMPORTANTE DEL INFORME",
        "     Las filas de dimensiones hay que compararlas contra las de",
        "     semilla, no contra 1,0. Si cambiar la dimension mueve la",
        "     particion lo mismo que volver a tirar el dado, entonces la",
        "     dimension no importa y DIMENSIONES = 5 esta justificada.",
        "",
        "     Las de submuestra son la prueba dura. Si dan claramente por",
        "     debajo de las de semilla, el agrupamiento depende de que este",
        "     ese 20% concreto del corpus, y entonces NO se puede comparar la",
        "     corrida de hoy con la de la semana pasada por numero de grupo.",
        "     Para el cruce temporal hay que trabajar por TEMA y por nombre, o",
        "     fijar los temas con terminos semilla como avisa temas.py.",
    ]
    return lineas


def _bloque_temas(res):
    tem = res["temas"]
    if "umbrales" not in tem:
        return []
    lineas = [
        "",
        "4. EL CODO, Y POR QUE NO APLICA DONDE SE ESPERABA",
        "",
        "   El codo es la inercia de k-means en funcion de k. HDBSCAN no recibe",
        "   un k ni minimiza una inercia, asi que al nivel de GRUPOS no hay codo",
        "   que dibujar. Donde si aplica es en la fusion en TEMAS, que si es una",
        "   jerarquia con un numero de cortes que se elige, y ahi el equivalente",
        "   correcto es la altura a la que se cierra cada fusion.",
        "",
        f"   {'al cortar en':<16}{'similitud':>11}{'salto':>10}",
    ]
    for fila in tem["saltos"]:
        lineas.append(f"   {str(fila['temas']) + ' temas':<16}"
                      f"{fila['similitud']:>11.3f}{fila['salto']:>+10.4f}")
    lineas += [
        "",
        "   Un salto grande = para seguir fundiendo hubo que juntar cosas",
        "   bastante mas distintas. Ahi estaria el codo. Si los saltos grandes",
        "   caen lejos del numero de temas elegido, el corpus no tiene un numero",
        "   natural de temas y el umbral es una decision de granularidad, no un",
        "   hallazgo. Es una eleccion legitima; lo que no se puede es",
        "   presentarla como si un numero la respaldara.",
        "",
        f"   {'umbral':>7}{'temas':>7}{'solos':>7}{'separac':>9}{'silueta':>9}"
        f"{'mayor%':>9}",
    ]
    for fila in tem["umbrales"]:
        lineas.append(f"   {fila['umbral']:>7.2f}{fila['temas']:>7}"
                      f"{fila['solos']:>7}{fila['separacion']:>9.3f}"
                      f"{fila['silueta']:>9.3f}{fila['mayor']:>9.1%}")
    lineas += [
        "",
        "   CUIDADO CON LA COLUMNA 'separac'. Sube siempre con el umbral y eso",
        "   no dice nada: el enlace completo GARANTIZA que ningun par dentro de",
        "   un tema baje del umbral, asi que esa columna es el parametro escrito",
        "   de otra forma. No sirve para elegir el umbral. La silueta si podria",
        "   bajar -- si se queda plana, es que no hay un corte natural.",
        "",
        f"   coseno medio entre centroides: {tem['coseno_entre_centroides']:.3f}",
        "   Ese si es el suelo correcto de 'separacion' y no depende del tamano",
        "   del tema, a diferencia del suelo de la coherencia.",
    ]
    return lineas


def _bloque_externa(res):
    ext = res["externa"]
    if "pureza" not in ext:
        return ["", "5. VALIDACION EXTERNA", "",
                f"   no se pudo: {ext.get('error', 'sin datos comparables')}"]
    return [
        "",
        "5. VALIDACION EXTERNA -- LA UNICA QUE MIRA AFUERA",
        "",
        "   Contra las categorias clinicas de embedding/datos/",
        "   catalogo_sintomas.json, asignadas a mano y que nadie le enseno ni a",
        "   bge-m3 ni a UMAP ni a HDBSCAN.",
        "",
        f"   textos con categoria   {ext['textos_con_categoria']:,} de "
        f"{ext['textos']:,}",
        f"   comparables            {ext['comparables']:,}  (con categoria Y "
        f"dentro de un grupo)",
        f"   pureza ponderada       {ext['pureza']:.3f}   fraccion del grupo que "
        f"comparte categoria",
        f"   pureza del azar        {ext['pureza_azar']:.3f}   acertar siempre la "
        f"categoria mas comun",
        f"   AMI                    {ext['ami']:.3f}",
        f"   ARI                    {ext['ari']:.3f}",
        "",
        "   Esta es la prueba que dice si lo encontrado SIGNIFICA algo. Todo lo",
        "   demas mide el agrupamiento con la misma geometria que lo produjo.",
        "",
        "   'pureza alta con ARI bajo' es la firma de un agrupamiento mas FINO",
        "   que la referencia, no de uno equivocado: hay muchos mas grupos que",
        "   categorias, asi que cada categoria sale partida y ARI castiga eso.",
        "",
        "   Lo que no prueba: el catalogo se construyo mirando este corpus, y",
        "   solo cubre los textos que mencionan alguno de sus sintomas. La cola",
        "   larga -- lo que mas interesa describir -- queda sin verificar.",
    ]


def _bloque_entrada(res):
    tru = res["truncamiento"]
    lineas = [
        "",
        "6. LO QUE ENTRA: EL ESPACIO DE bge-m3 Y LA VENTANA",
        "",
        f"   coseno entre dos frases al azar   {res['coseno_par']:.3f}",
        f"   anisotropia (norma del centro)    {res['anisotropia']:.3f}",
        "",
        "   La anisotropia es la causa de todo lo raro de este espacio: con 0",
        "   los vectores apuntan a todas partes, y aqui apuntan casi todos al",
        "   mismo sitio. De ahi que dos frases sin relacion den 0,46 y no 0, y",
        "   de ahi el suelo de la coherencia del bloque 1.",
    ]
    if "error" in tru:
        return lineas + ["", f"   ventana: no se pudo medir ({tru['error']})"]
    return lineas + [
        "",
        f"   ventana                {tru['limite']} tokens",
        f"   tokens por texto       mediana {tru['mediana']}, p99 {tru['p99']}, "
        f"maximo {tru['maximo']}",
        f"   tokens por palabra     {tru['tokens_por_palabra']:.2f}",
        f"   textos truncados       {tru['textos_cortados']:,} de "
        f"{tru['textos']:,} ({tru['textos_cortados'] / max(tru['textos'], 1):.2%})",
        f"   notas afectadas        {tru['notas_cortadas']:,} de "
        f"{tru['notas']:,} ({tru['notas_cortadas'] / max(tru['notas'], 1):.2%})",
        "",
        "   embedding/modelo.py justifica los 128 tokens contando PALABRAS. A",
        "   dos tokens por palabra ese margen es la mitad de lo que parece, asi",
        "   que esto se mide en cada corrida: los textos largos son las notas de",
        "   ingreso con antecedentes, que es el tipo de nota que mas crece",
        "   cuando se suman servicios al corpus.",
    ]


def texto(res):
    """El informe completo de la validacion."""
    cfg = res["config"]
    lineas = [
        "VALIDACION DEL AGRUPAMIENTO",
        "",
        "Este informe no compara configuraciones entre si -- eso es --barrido.",
        "Pregunta si lo que sale se distingue de lo que saldria sin ningun",
        "patron, y si sobrevive a repetir la corrida cambiando lo que no",
        "deberia importar.",
        "",
        "PARAMETROS VALIDADOS",
        f"  vecinos {cfg['vecinos']}   dimensiones {cfg['dimensiones']}   "
        f"tamano_minimo {cfg['tamano_minimo']}   "
        f"muestras_minimas {cfg['muestras_minimas']}   "
        f"epsilon {cfg['epsilon']}",
        f"  textos {res['resumen']['textos']:,}   "
        f"notas {res['resumen']['notas']:,}   "
        f"grupos {res['resumen']['clusters']}   "
        f"ruido {res['resumen']['ruido_notas']:.1%}",
        "",
        "=" * 70,
    ]
    lineas += _bloque_coherencia(res)
    lineas += _bloque_nulo(res)
    lineas += _bloque_estabilidad(res)
    lineas += _bloque_temas(res)
    lineas += _bloque_externa(res)
    lineas += _bloque_entrada(res)

    if res.get("rapido"):
        lineas += [
            "",
            "=" * 70,
            "CORRIDA CON --rapido: faltan el modelo nulo y las tres pruebas de",
            "estabilidad, que son las que necesitan volver a reducir. Sin ellas",
            "no hay respuesta a 'la estructura es real' ni a 'el resultado se",
            "repite'. Corre 'python -m clustering --validar' sin --rapido antes",
            "de apoyar ninguna decision en esto.",
        ]
    return "\n".join(lineas) + "\n"


def guardar(res):
    """Escribe salidas/validacion.txt y devuelve la ruta."""
    rutas.VALIDACION.write_text(texto(res), encoding="utf-8")
    return rutas.VALIDACION


# ==========================================================
# LA FIGURA
# ==========================================================

def dibujar(res, umbral_actual=None):
    """
    Los cuatro paneles de la validacion, en una figura.

    POR QUE UNA FIGURA Y NO SOLO LA TABLA
        Tres de estos cuatro paneles son curvas o distribuciones, y de una
        curva lo que se lee es la FORMA: si el codo existe, si la silueta se
        hunde en unos pocos grupos o esta baja en todos, si las barras de
        estabilidad se separan o no. Eso en una tabla de numeros hay que
        reconstruirlo mentalmente fila por fila.

        La figura no reemplaza al informe: no lleva las advertencias sobre como
        se lee cada numero, que es donde estaba el error original. Se miran
        juntos.

    A  el codo, que es el panel que el nombre promete y el que dice que no hay
       codo. La linea vertical marca donde cae el umbral vigente.
    B  la silueta grupo por grupo, ordenada. Lo que importa es cuanto de la
       curva queda por debajo de cero: esos grupos estarian mejor fundidos con
       su vecino.
    C  coherencia contra su suelo. La barra que cuenta es la diferencia, no la
       altura.
    D  estabilidad. Compararlas entre si, no contra 1,0.
    """
    import matplotlib.pyplot as plt

    figura, ejes = plt.subplots(2, 2, figsize=(14, 9), facecolor="white")
    figura.suptitle("Validacion del agrupamiento -- "
                    f"{res['resumen']['textos']:,} textos, "
                    f"{res['resumen']['clusters']} grupos",
                    fontsize=13, fontweight="bold")

    _panel_codo(ejes[0][0], res, umbral_actual)
    _panel_silueta(ejes[0][1], res)
    _panel_coherencia(ejes[1][0], res)
    _panel_estabilidad(ejes[1][1], res)

    figura.tight_layout(rect=(0, 0, 1, 0.96))
    return figura


def _panel_codo(eje, res, umbral_actual):
    tem = res["temas"]
    eje.set_title("A. El codo, donde si aplica: la fusion en temas",
                  fontsize=10, fontweight="bold", loc="left")
    if "saltos" not in tem:
        eje.text(0.5, 0.5, "no hay grupos suficientes", ha="center")
        return

    saltos = sorted(tem["saltos"], key=lambda f: f["temas"])
    x = [f["temas"] for f in saltos]

    # El salto va en su propio eje y no reescalado sobre el primero. Multiplicar
    # por diez para que 'se vea' pone dos magnitudes distintas en la misma regla
    # y es justo el tipo de atajo que produjo el error que este modulo corrige.
    eje.plot(x, [f["similitud"] for f in saltos], marker="o", markersize=3,
             color="#1f77b4", label="similitud a la que se funde")
    if umbral_actual:
        eje.axhline(umbral_actual, color="#2ca02c", linestyle="--", linewidth=1,
                    label=f"umbral vigente {umbral_actual:.2f}")
    eje.set_xlabel("temas que quedarian al cortar aqui")
    eje.set_ylabel("similitud coseno", color="#1f77b4")
    eje.grid(alpha=0.25)

    otro = eje.twinx()
    otro.bar(x, [f["salto"] for f in saltos], color="#d62728", alpha=0.35,
             label="salto (el codo seria un pico)")
    otro.set_ylabel("salto de distancia en esa fusion", color="#d62728",
                    fontsize=8)
    otro.set_ylim(0, max(f["salto"] for f in saltos) * 3.2)

    lineas, nombres = eje.get_legend_handles_labels()
    l2, n2 = otro.get_legend_handles_labels()
    eje.legend(lineas + l2, nombres + n2, fontsize=7, loc="upper left")


def _panel_silueta(eje, res):
    eje.set_title("B. Silueta por grupo, en el espacio de bge-m3",
                  fontsize=10, fontweight="bold", loc="left")
    valores = res["siluetas"].get("por_grupo")
    if not valores:
        eje.text(0.5, 0.5, "sin siluetas", ha="center")
        return

    colores = ["#d62728" if v < 0 else "#1f77b4" for v in valores]
    eje.bar(range(len(valores)), valores, color=colores, width=1.0)
    eje.axhline(0, color="black", linewidth=0.8)
    eje.axhline(res["siluetas"]["silueta_bge"], color="#ff7f0e",
                linestyle="--", linewidth=1,
                label=f"media por texto {res['siluetas']['silueta_bge']:.3f}")
    eje.set_xlabel("grupos, ordenados por silueta")
    eje.set_ylabel("silueta media del grupo")
    eje.legend(fontsize=7, loc="upper left")
    eje.grid(alpha=0.25, axis="y")
    negativos = sum(1 for v in valores if v < 0)
    eje.text(0.98, 0.04,
             f"{negativos} de {len(valores)} grupos en rojo:\n"
             f"mas cerca del vecino que de si mismos",
             transform=eje.transAxes, ha="right", fontsize=7, color="#d62728")


def _panel_coherencia(eje, res):
    eje.set_title("C. La coherencia contra su suelo, no contra 0,47",
                  fontsize=10, fontweight="bold", loc="left")
    cal = res["calibracion"]
    barras = [("suelo\n(etiquetas\nbarajadas)", cal["nulo"], "#bbbbbb"),
              ("coherencia\nmedida", cal["real"], "#1f77b4")]
    if "nulo" in res:
        barras.insert(0, ("nulo permutado\n(datos sin\nestructura)",
                          res["nulo"]["real"], "#d62728"))

    eje.bar([b[0] for b in barras], [b[1] for b in barras],
            color=[b[2] for b in barras])
    for posicion, barra in enumerate(barras):
        eje.text(posicion, barra[1] + 0.005, f"{barra[1]:.3f}",
                 ha="center", fontsize=9)
    eje.axhline(res["coseno_par"], color="black", linestyle=":", linewidth=1,
                label=f"coseno entre frases al azar {res['coseno_par']:.3f}\n"
                      f"(NO es el suelo de esta metrica)")
    eje.set_ylim(0, 1.0)
    eje.set_ylabel("coseno medio al centro del grupo")
    eje.legend(fontsize=7, loc="lower right")
    eje.grid(alpha=0.25, axis="y")
    eje.text(0.02, 0.92, f"ganancia real  {cal['ganancia']:+.3f}",
             transform=eje.transAxes, fontsize=10, fontweight="bold")


def _panel_estabilidad(eje, res):
    eje.set_title("D. Estabilidad: comparar las barras entre si, no con 1,0",
                  fontsize=10, fontweight="bold", loc="left")
    if "semillas" not in res:
        eje.text(0.5, 0.5, "corrida con --rapido:\nno se midio estabilidad",
                 ha="center", va="center", fontsize=9)
        eje.set_axis_off()
        return

    nombres, aris, amis, colores = [], [], [], []
    for fila in res["semillas"]:
        nombres.append(f"semilla {fila['semilla']}")
        aris.append(fila["ari"]); amis.append(fila["ami"])
        colores.append("#1f77b4")
    for fila in res.get("dimensiones", []):
        nombres.append(f"dims {fila['dimensiones']}")
        aris.append(fila["ari"]); amis.append(fila["ami"])
        colores.append("#ff7f0e")
    for fila in res.get("submuestras", []):
        nombres.append(f"80% #{fila['repeticion']}")
        aris.append(fila["ari"]); amis.append(fila["ami"])
        colores.append("#d62728")

    posiciones = np.arange(len(nombres))
    eje.bar(posiciones - 0.2, aris, width=0.4, color=colores, label="ARI")
    eje.bar(posiciones + 0.2, amis, width=0.4, color=colores, alpha=0.4,
            label="AMI (mas claro)")
    eje.set_xticks(posiciones)
    eje.set_xticklabels(nombres, rotation=45, ha="right", fontsize=7)
    eje.set_ylim(0, 1.0)
    eje.set_ylabel("acuerdo con la corrida de referencia")
    eje.legend(fontsize=7, loc="upper right")
    eje.grid(alpha=0.25, axis="y")
    eje.text(0.02, 0.05,
             "azul = cambiar la semilla (no deberia importar)\n"
             "naranja = cambiar la dimension\n"
             "rojo = quitar el 20% del corpus",
             transform=eje.transAxes, fontsize=7)


def guardar_figura(figura):
    """Escribe salidas/validacion.png y devuelve la ruta."""
    figura.savefig(rutas.VALIDACION_FIGURA, dpi=130, facecolor="white")
    return rutas.VALIDACION_FIGURA
