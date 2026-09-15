"""
La identidad estable de los temas entre corridas. Sin esto no hay fase 8.

EL PROBLEMA QUE RESUELVE, MEDIDO Y NO SUPUESTO
    validacion.py dejo esto claro: reagrupar el corpus quitandole el 20% de los
    textos da un ARI de 0,25 a 0,31 contra la corrida completa, y el numero de
    grupos pasa de 155 a ~125. Cambiar solo la semilla de UMAP ya mueve el ARI
    a 0,47.

    Traducido a lo que viene: el tema 12 de hoy NO es el tema 12 de la semana
    que viene. Los numeros los asigna temas._renumerar() por tamano, asi que
    basta con que un tema crezca un poco para que toda la numeracion se corra.

    Y lo que viene es contar cuantas notas de cada tema llegan cada dia y
    cruzarlo contra el clima y el calendario. Una serie construida sobre
    numeros que se renumeran no mide lo que dice medir: un salto en 'tema 12'
    entre dos corridas seria renumeracion, no un cambio en el hospital. Es la
    forma mas facil de publicar un hallazgo falso.

QUE ES UN ANCLA
    Un tema con nombre e identidad PERMANENTES, definido por un punto fijo en
    el espacio de bge-m3 -- el centroide del tema en la corrida que lo creo --
    y un id que no se reutiliza nunca.

    En cada corrida nueva no se renumera nada: cada grupo que sale de HDBSCAN
    se compara contra las anclas y se queda con la mas parecida. El tema de una
    nota deja de ser 'el hueco donde cayo esta vez' y pasa a ser 'a que ancla
    se parece', que es una pregunta cuya respuesta no depende de como quedo
    repartido el resto del corpus.

CUANTO ARREGLA, MEDIDO
    La prueba es directa: se reagrupa el corpus cambiando la semilla de UMAP y
    se mira que fraccion de las notas cae en el MISMO tema que en la corrida de
    referencia. No ARI -- que mide si la particion se parece -- sino coincidencia
    de la etiqueta, que es lo unico que sirve para contar una serie.

        semilla    ARI de temas    sin anclaje    con anclaje
             1          0,535          64,0%          96,6%
             7          0,642          73,6%          95,5%
          2024          0,515          64,2%          95,3%

    De dos de cada tres notas a diecinueve de cada veinte.

    Y la columna 'sin anclaje' esta siendo generosa: para calcularla hay que
    emparejar los temas de las dos corridas con el mejor emparejamiento posible
    (Hungaro), que es informacion que en la practica no se tiene -- si se
    tuviera, no haria falta anclar. Sin ese favor, los numeros de tema de dos
    corridas no se pueden comparar en absoluto.

POR QUE LOS CENTROIDES SE CONGELAN
    Lo natural seria recalcular cada ancla en cada corrida con los grupos que
    le tocaron, para que se mantenga al dia. Seria volver al problema: un ancla
    que se mueve un poco cada semana termina, al cabo de unos meses, en otro
    sitio, y la serie de enero y la de junio estarian contando cosas distintas
    con el mismo nombre. La deriva lenta es peor que el salto, porque no se ve.

    Asi que el ancla no se mueve. Cuando el corpus crezca lo bastante como para
    que las anclas de hoy se queden cortas -- y va a pasar, estan hechas sobre
    5.020 textos de los 94.000 disponibles -- se vuelven a crear a proposito
    con --anclar, queda registrado en el archivo, y desde ahi empieza una serie
    nueva. Lo que no se puede es que eso ocurra solo.

POR QUE VIVE EN datos/ Y NO EN salidas/
    Por la regla del proyecto: salidas/ lo reescribe un script y esta ignorado
    por git; datos/ se versiona y se edita a mano. Las anclas son lo segundo
    aunque nazcan de un calculo, y por dos motivos.

    El primero es que son la definicion de las unidades de analisis: si se
    borran, las series de meses anteriores dejan de ser comparables con las
    nuevas. Eso no puede vivir en una carpeta que cualquier corrida sobreescribe.

    El segundo es que hay que poder corregirlas a mano. El nombre que sale del
    TF-IDF es utilizable pero no siempre es el que un ojo clinico pondria, y
    'alta presion malestar' se lee mejor como 'hipertension'. anclas.csv se
    abre y se edita esa columna; el centroide no se toca, asi que renombrar no
    cambia ninguna serie.

DOS ARCHIVOS Y NO UNO
    datos/anclas.csv       id, nombre y de donde salio cada ancla. Es el que se
                           edita y el que se lee para entender.
    datos/anclas.npy       la matriz (n_anclas x 1024) de centroides, alineada
                           fila por fila con el CSV.

    Estan separados porque mil veinticuatro numeros por ancla dentro de un CSV
    lo vuelven ilegible y no se pueden editar a mano de todos modos. El CSV es
    para el ojo y el .npy para la maquina, igual que notas.csv y
    asignacion.parquet mas abajo en el pipeline.

    Van juntos o no valen: cargar() comprueba que tengan el mismo numero de
    filas y el mismo orden de ids, y se niega si no.

LO QUE ESTO NO ARREGLA
    No hace estable el agrupamiento; hace estable la LECTURA del agrupamiento.
    Los grupos de HDBSCAN van a seguir moviendose corrida a corrida, y un grupo
    concreto sigue sin ser un hallazgo. Lo que queda fijo es el tema al que se
    le asigna, que es el nivel con el que se va a trabajar de aqui en adelante.

    Tampoco inventa cobertura: una nota que HDBSCAN dejo en ruido sigue sin
    tema, porque no tiene grupo con el que compararse contra las anclas. Ese
    15,9% de notas sin tema es el mismo de antes y hay que contarlo aparte, no
    repartirlo.
"""

import json
from datetime import datetime

import numpy as np
import pandas as pd

from clustering import rutas, temas

# ==========================================================
# EL UMBRAL DE ASIGNACION
# ==========================================================
#
# Coseno minimo para que un grupo se considere de un ancla. Por debajo, el
# grupo no se parece a ninguna cosa conocida y se reporta como SIN ANCLA en vez
# de forzarlo dentro de la menos mala.
#
# CALIBRADO, NO ELEGIDO A OJO
#     Medido sobre la corrida de 5.020 textos, comparando los 155 grupos contra
#     las 41 anclas que salieron de ellos:
#
#         coseno de un grupo con SU ancla      min 0,832  mediana 0,910
#         coseno con la mejor ancla AJENA      mediana 0,834  p95 0,890
#         coseno entre dos anclas distintas    media 0,689
#
#     Los tres numeros estan altos porque el espacio de bge-m3 es anisotropico
#     y aqui todo se parece a todo (ver validacion.py). Lo que importa es que
#     0,80 queda por debajo del peor caso propio -- 0,832, asi que ningun grupo
#     legitimo se queda fuera -- y muy por encima del 0,689 de dos anclas al
#     azar, que es el suelo.
#
#     No se sube mas porque a 0,85 ya empiezan a quedarse fuera grupos que si
#     tenian ancla: tres de los 155 en la propia corrida que las creo, que es
#     el caso mas favorable posible.
UMBRAL = 0.80

# Parecido RESIDUAL por encima del cual dos anclas describen lo mismo. No se
# funden solas: cambiar el numero de anclas rompe las series, asi que es una
# decision y no un automatismo. revisar() las lista.
#
# POR QUE RESIDUAL Y NO EL COSENO DIRECTO -- AQUI HUBO UN ERROR Y SE CORRIGIO
#     La primera version comparaba el coseno crudo y avisaba por encima de 0,90.
#     Sobre las 41 anclas reales eso señalaba siete pares, cuatro de ellos con
#     el ancla 1 dentro. Al mirarlos, ninguno describia lo mismo.
#
#     La causa es la anisotropia de bge-m3 otra vez: un ancla que funde muchos
#     grupos acaba cerca del centro de todas las demas, y desde ahi se parece a
#     todo. Medido: la correlacion entre 'parecido al centro' y 'parecido a su
#     vecina mas proxima' es +0,906, y la de 'cuantos grupos fundio' con
#     'parecido al centro' es +0,655. Es decir, el aviso estaba detectando
#     anclas GENERICAS y llamandolas gemelas.
#
#     Fundir esos pares habria sido un error: no son dos temas repetidos, es un
#     tema que no dice nada de particular.
#
#     Lo que si separa una cosa de la otra es quitar a todas las anclas la
#     direccion que comparten y comparar lo que queda. Con esa correccion el
#     ancla generica desaparece de la lista y lo que sube son pares que si se
#     leen como lo mismo: 'dolor duele rodilla' con 'dolor bajito lumbar', o
#     'caida trauma cai' con 'transito moto accidente'.
#
#     El umbral 0,55 sale de esa medicion: el residual entre dos anclas
#     cualesquiera promedia -0,02 y su percentil 99 es 0,47, asi que 0,55 deja
#     fuera la cola normal y recoge los pares que de verdad se solapan.
UMBRAL_GEMELAS = 0.55

# Parecido al centro de todas las anclas por encima del cual un tema es tan
# generico que su serie no va a responder a nada: es una mezcla de todo. No es
# un error que haya uno -- suele ser el tema mas grande, el que absorbe lo
# inespecifico -- pero hay que saber cual es antes de interpretar su serie.
UMBRAL_GENERICA = 0.95


# ==========================================================
# CREAR
# ==========================================================

def administrativas(textos, indice):
    """
    Cuantas notas de cada texto senalo NLP/ como que no dicen nada del paciente.

    POR QUE ESTO LLEGA HASTA AQUI
        La fase 4 de NLP/ marca las notas que son tramite administrativo,
        plantilla en blanco o solo antecedentes, y a proposito NO las borra: las
        deja en el CSV y las vectoriza igual, porque un falso descarte es
        irrecuperable y un falso senalamiento no cuesta nada.

        La consecuencia es que esas notas llegan al agrupamiento, y como se
        parecen mucho entre si forman temas propios. Medido sobre la corrida de
        6.501 notas: 1.104 estan senaladas (17,0%), y CINCO de los 41 temas son
        mas de la mitad tramite -- uno de ellos es 100%.

        Un tema asi no mide salud. Su serie diaria sube y baja con como se
        llenan los formularios, no con quien llega enfermo, y cruzarla contra la
        lluvia es cruzar la lluvia contra el papeleo. Por eso se marca en el
        ancla y no se descubre despues mirando graficas raras.

    Devuelve un array alineado con textos: cuantas de las notas de ese texto
    estan senaladas. Si el CSV no existe, devuelve ceros y no rompe nada.
    """
    try:
        from NLP import rutas as rutas_nlp
    except ImportError:
        return np.zeros(len(textos))

    if not rutas_nlp.NOTAS_DESCARTADAS.exists():
        return np.zeros(len(textos))

    senaladas = pd.read_csv(rutas_nlp.NOTAS_DESCARTADAS,
                            encoding="utf-8-sig", usecols=["OID"])
    marcado = indice[indice["OID"].isin(set(senaladas["OID"]))]
    por_fila = marcado.groupby("fila").size()
    return textos["fila"].map(por_fila).fillna(0).to_numpy(dtype=float)


def crear(vectores, grupos, n_notas, mapa_temas, nombres_tema=None,
          notas_administrativas=None):
    """
    Construye las anclas a partir de una corrida y devuelve (tabla, matriz).

    Un ancla por TEMA, no por grupo. El centroide del ancla es la media de los
    centroides de sus grupos pesada por notas y renormalizada -- la misma
    cuenta que temas.centroides(), un nivel mas arriba -- porque es el punto que
    representa al tema entero y no a la forma concreta en que quedo partido.

    No escribe nada: guardar() lo hace aparte, para que se pueda mirar lo que
    saldria antes de comprometerse.
    """
    grupos = np.asarray(grupos)
    n_notas = np.asarray(n_notas, dtype=np.float64)
    nombres_tema = nombres_tema or {}

    # Se promedian los CENTROIDES DE GRUPO, no los textos sueltos. Parece lo
    # mismo y no lo es: el centroide de cada grupo esta renormalizado, asi que
    # cada grupo entra con el mismo peso por nota independientemente de lo
    # disperso que sea. Promediando textos, un grupo disperso aporta un vector
    # mas corto y pesa menos de lo que le toca.
    #
    # Ademas es la definicion con la que se midio que el anclaje recupera el
    # 95-97% de las notas entre corridas. Cambiarla invalidaria esa medicion.
    lista_grupos, centros_grupo, pesos_grupo = temas.centroides(
        vectores, grupos, n_notas)
    posicion_de = {int(c): i for i, c in enumerate(lista_grupos)}

    lista, filas = [], []
    for tema in sorted(set(mapa_temas.values())):
        cuales = [int(c) for c, t in mapa_temas.items()
                  if t == tema and int(c) in posicion_de]
        if not cuales:
            continue

        donde = [posicion_de[c] for c in cuales]
        bloque = centros_grupo[donde]
        peso = pesos_grupo[donde]
        centro = np.average(bloque, axis=0, weights=peso)
        norma = np.linalg.norm(centro)
        lista.append(centro / norma if norma else centro)

        dentro = np.isin(grupos, cuales)
        parte = 0.0
        if notas_administrativas is not None and n_notas[dentro].sum():
            parte = float(np.asarray(notas_administrativas)[dentro].sum()
                          / n_notas[dentro].sum())

        filas.append({
            # El id arranca en 1 y no en 0 para que no se confunda nunca con el
            # -1 del ruido ni con los numeros de tema de una corrida suelta.
            "id": len(filas) + 1,
            "nombre": str(nombres_tema.get(tema, f"ancla {len(filas) + 1}")),
            "notas_origen": int(peso.sum()),
            "grupos_origen": int(len(cuales)),
            "parte_administrativa": round(parte, 3),
            # clinica=False no excluye nada por si sola: la serie se calcula
            # igual. Lo que hace es dejar dicho, en el mismo archivo donde se
            # define el tema, que esa serie mide papeleo. Quien la use decide, y
            # no puede alegar que no estaba avisado.
            "clinica": parte < 0.5,
            "creada": datetime.now().strftime("%Y-%m-%d"),
            "activa": True,
        })

    return pd.DataFrame(filas), np.vstack(lista).astype(np.float32)


def guardar(tabla, matriz, procedencia=None):
    """
    Escribe datos/anclas.csv y datos/anclas.npy, y deja constancia de que los
    creo.

    Se niega a sobreescribir unas anclas que ya existan sin que se le pase
    procedencia con 'reemplazar': True. Rehacerlas es exactamente lo que rompe
    la comparabilidad con las series ya calculadas, asi que tiene que costar un
    gesto deliberado y no ser el efecto secundario de volver a correr algo.
    """
    rutas.DATOS.mkdir(exist_ok=True)
    procedencia = dict(procedencia or {})

    if rutas.ANCLAS.exists() and not procedencia.get("reemplazar"):
        raise SystemExit(
            f"Ya hay anclas en {rutas.ANCLAS} y rehacerlas rompe la "
            f"comparabilidad con toda serie ya calculada.\n"
            f"Si es lo que quieres: python -m clustering --anclar --rehacer")

    if len(tabla) != len(matriz):
        raise ValueError(
            f"tabla y matriz no cuadran: {len(tabla)} filas contra "
            f"{len(matriz)} centroides")

    tabla.to_csv(rutas.ANCLAS, index=False, encoding="utf-8-sig")
    np.save(rutas.ANCLAS_VECTORES, matriz)

    procedencia.update({
        "creado": datetime.now().isoformat(timespec="seconds"),
        "anclas": int(len(tabla)),
        "dimension": int(matriz.shape[1]),
    })
    rutas.ANCLAS_ORIGEN.write_text(
        json.dumps(procedencia, indent=2, ensure_ascii=False), encoding="utf-8")
    return rutas.ANCLAS


# ==========================================================
# CARGAR Y USAR
# ==========================================================

def existen():
    """Si hay anclas con que trabajar. Lo primero que pregunta la fase 8."""
    return rutas.ANCLAS.exists() and rutas.ANCLAS_VECTORES.exists()


def cargar():
    """
    Devuelve (tabla, matriz) comprobando que los dos archivos describan lo mismo.

    La comprobacion no es paranoia: el CSV se edita a mano y el .npy no, asi que
    borrar un renglon del CSV para quitar un ancla deja los dos archivos
    desalineados y, sin este control, cada ancla pasaria a llevar el centroide
    de la siguiente. Las series saldrian con nombres cambiados y nada avisaria.
    """
    if not existen():
        raise SystemExit(
            "No hay anclas todavia. Creaalas con:\n"
            "  python -m clustering --anclar\n"
            "Sin ellas los numeros de tema cambian entre corridas y no se puede "
            "construir ninguna serie temporal. Ver clustering/anclas.py.")

    tabla = pd.read_csv(rutas.ANCLAS, encoding="utf-8-sig")
    matriz = np.load(rutas.ANCLAS_VECTORES)

    if len(tabla) != len(matriz):
        raise SystemExit(
            f"anclas.csv tiene {len(tabla)} renglones y anclas.npy "
            f"{len(matriz)} centroides. Se editó uno sin el otro: cada ancla "
            f"estaria usando el centroide de otra.\n"
            f"Recupera anclas.csv de git, o vuelve a crear las anclas con "
            f"--anclar --rehacer asumiendo que empieza una serie nueva.")

    if tabla["id"].duplicated().any():
        raise SystemExit("Hay ids repetidos en anclas.csv: cada ancla tiene "
                         "que tener el suyo y no reutilizarse nunca.")

    return tabla, matriz


def asignar(centroides_grupos, matriz, umbral=UMBRAL):
    """
    Para cada grupo, el indice del ancla mas parecida, o -1 si ninguna llega.

    Devuelve (indices, similitudes). El indice es posicional sobre la matriz,
    no el id: quien llama lo traduce con la tabla. Se hace asi para que esta
    funcion no dependa de como este numerado el CSV.

    LO QUE HAY QUE ENTENDER DEL -1
        Un grupo sin ancla no es un fallo ni un dato que se pierda: es un
        motivo de consulta que no se parece a nada de lo que habia cuando se
        crearon las anclas. Puede ser una novedad real -- un brote, un tipo de
        trauma nuevo -- y es justo lo que interesa ver.

        Por eso se reporta aparte y no se reparte entre las anclas existentes.
        Si aparecen muchos y persisten, es la senal de que toca volver a anclar.
    """
    centroides_grupos = np.asarray(centroides_grupos, dtype=np.float64)
    matriz = np.asarray(matriz, dtype=np.float64)
    if centroides_grupos.size == 0 or matriz.size == 0:
        return np.array([], dtype=int), np.array([])

    similitud = centroides_grupos @ matriz.T
    mejor = similitud.argmax(axis=1)
    valor = similitud[np.arange(len(mejor)), mejor]
    return np.where(valor >= umbral, mejor, -1), valor


def aplicar(vectores, grupos, n_notas, tabla=None, matriz=None, umbral=UMBRAL):
    """
    El ancla de cada TEXTO, a partir del agrupamiento de una corrida.

    Devuelve (ancla_por_texto, detalle). ancla_por_texto lleva el id del ancla,
    o -1 para el ruido y para los grupos que no alcanzaron el umbral. detalle es
    un DataFrame por grupo con a que ancla fue y con cuanta similitud, que es lo
    que se audita cuando una serie hace algo raro.

    El ruido se queda en -1 y no se le busca ancla: no tiene grupo, asi que no
    hay centroide que comparar. Repartirlo por cercania al ancla mas proxima
    seria inventarse el dato, que es lo mismo que agrupar.py rechaza un nivel
    mas abajo.
    """
    if tabla is None or matriz is None:
        tabla, matriz = cargar()

    lista, centros, pesos = temas.centroides(vectores, grupos, n_notas)
    indices, similitudes = asignar(centros, matriz, umbral=umbral)

    ids = tabla["id"].to_numpy()
    nombres = tabla["nombre"].to_numpy()
    por_grupo = {}
    filas = []
    for posicion, grupo in enumerate(lista):
        indice = int(indices[posicion])
        por_grupo[int(grupo)] = int(ids[indice]) if indice >= 0 else -1
        filas.append({
            "cluster": int(grupo),
            "ancla": por_grupo[int(grupo)],
            "nombre_ancla": nombres[indice] if indice >= 0 else "(sin ancla)",
            "similitud": float(similitudes[posicion]),
            "notas": float(pesos[posicion]),
        })

    ancla_por_texto = np.array(
        [por_grupo.get(int(c), -1) for c in np.asarray(grupos)], dtype=int)
    return ancla_por_texto, pd.DataFrame(filas)


# ==========================================================
# REVISAR
# ==========================================================

def residuales(matriz):
    """
    Las anclas despues de quitarles la direccion que todas comparten.

    Devuelve (residual, generica): la matriz renormalizada sin su componente
    comun, y el coseno de cada ancla con el centro de todas, que es la medida de
    lo generica que es.

    Es la misma correccion de anisotropia que validacion.centrado() probo sobre
    el AGRUPAMIENTO y descarto por inutil: alli no cambiaba nada porque UMAP
    solo mira el orden de los vecinos. Aqui si hace falta, y no es una
    contradiccion -- aqui se comparan magnitudes absolutas de coseno entre
    cuarenta puntos, que es exactamente el caso en el que el componente comun
    domina.
    """
    matriz = np.asarray(matriz, dtype=np.float64)
    centro = matriz.mean(axis=0)
    centro = centro / (np.linalg.norm(centro) or 1.0)

    generica = matriz @ centro
    residual = matriz - np.outer(generica, centro)
    normas = np.linalg.norm(residual, axis=1, keepdims=True)
    residual = residual / np.where(normas == 0, 1.0, normas)
    return residual, generica


def revisar(detalle, tabla, matriz, umbral_gemelas=UMBRAL_GEMELAS,
            umbral_generica=UMBRAL_GENERICA):
    """
    Los cuatro problemas que vuelven inservible una serie, antes de construirla.

    1. ANCLAS GEMELAS. Dos anclas que describen lo mismo. En la serie se ve como
       dos temas que se roban notas entre si de una semana a la otra. Se miden
       sobre el residual y no sobre el coseno directo: ver UMBRAL_GEMELAS, que
       explica por que la version anterior de este aviso señalaba lo que no era.

    2. ANCLAS GENERICAS. Un tema tan cerca del centro de todos los demas que no
       describe nada en particular -- suele ser el mas grande, el que fundio
       mas grupos. Su serie es una mezcla y no va a responder limpiamente a
       ninguna variable.

    3. ANCLAS VACIAS. Un ancla a la que esta corrida no le mando ningun grupo.
       Su serie es una fila de ceros, y eso no significa que nadie consultara
       por eso: significa que el agrupamiento de hoy no formo un grupo
       parecido. Distinguir 'no paso' de 'no lo vi' es imprescindible antes de
       cruzar contra el clima.

    4. GRUPOS HUERFANOS. Grupos que no llegaron a ninguna ancla. Si son muchos
       o pesan mucho, las anclas se quedaron cortas y hay que rehacerlas.
    """
    residual, generica = residuales(matriz)
    similitud = residual @ residual.T
    arriba = np.triu_indices(len(matriz), 1)

    directa = np.asarray(matriz, dtype=np.float64) @ np.asarray(
        matriz, dtype=np.float64).T
    gemelas = [
        {"a": int(tabla["id"].iloc[i]), "nombre_a": tabla["nombre"].iloc[i],
         "b": int(tabla["id"].iloc[j]), "nombre_b": tabla["nombre"].iloc[j],
         "similitud": float(similitud[i, j]),
         "directa": float(directa[i, j])}
        for i, j in zip(*arriba) if similitud[i, j] >= umbral_gemelas
    ]

    genericas = sorted(
        ({"id": int(tabla["id"].iloc[i]), "nombre": tabla["nombre"].iloc[i],
          "generica": float(generica[i]),
          "grupos": int(tabla["grupos_origen"].iloc[i])
          if "grupos_origen" in tabla.columns else 0}
         for i in range(len(tabla)) if generica[i] >= umbral_generica),
        key=lambda a: -a["generica"])

    usadas = set(detalle.loc[detalle["ancla"] != -1, "ancla"])
    vacias = [{"id": int(r.id), "nombre": r.nombre}
              for r in tabla.itertuples(index=False) if int(r.id) not in usadas]

    huerfanos = detalle[detalle["ancla"] == -1]
    total = float(detalle["notas"].sum()) or 1.0

    return {
        "anclas": int(len(tabla)),
        "usadas": int(len(usadas)),
        "gemelas": sorted(gemelas, key=lambda g: -g["similitud"]),
        "genericas": genericas,
        "vacias": vacias,
        "huerfanos": int(len(huerfanos)),
        "notas_huerfanas": int(huerfanos["notas"].sum()),
        "parte_huerfana": float(huerfanos["notas"].sum() / total),
        "similitud_minima": (float(detalle.loc[detalle["ancla"] != -1,
                                               "similitud"].min())
                             if (detalle["ancla"] != -1).any() else float("nan")),
    }


def texto(informe, detalle=None):
    """El diagnostico del anclaje, para el informe de la corrida."""
    lineas = [
        "ANCLAJE DE TEMAS",
        f"  anclas definidas    {informe['anclas']}",
        f"  usadas esta corrida {informe['usadas']}",
        f"  grupos sin ancla    {informe['huerfanos']} "
        f"({informe['notas_huerfanas']:,} notas, {informe['parte_huerfana']:.1%})",
    ]
    if not np.isnan(informe["similitud_minima"]):
        lineas.append(f"  peor similitud      {informe['similitud_minima']:.3f}"
                      f"   (umbral {UMBRAL})")

    if informe["gemelas"]:
        lineas += ["", "  ANCLAS GEMELAS -- describen lo mismo y se roban notas",
                   "  entre corridas. Conviene fundirlas a mano en anclas.csv.",
                   "  La cifra es el parecido RESIDUAL, quitando lo que todas",
                   "  las anclas comparten; el coseno crudo va entre parentesis",
                   "  y no sirve para esto (ver UMBRAL_GEMELAS en anclas.py):"]
        for par in informe["gemelas"][:8]:
            lineas.append(f"    {par['similitud']:.3f} ({par['directa']:.3f})  "
                          f"[{par['a']}] {par['nombre_a']}  ~  "
                          f"[{par['b']}] {par['nombre_b']}")

    if informe.get("genericas"):
        lineas += ["", "  ANCLAS GENERICAS -- tan cerca del centro de todas las",
                   "  demas que no describen nada en particular. Su serie es una",
                   "  mezcla y no va a responder limpiamente a ninguna variable;",
                   "  no es un error, pero hay que saber cual es al leerla:"]
        for generica in informe["genericas"]:
            lineas.append(f"    {generica['generica']:.3f}  "
                          f"[{generica['id']}] {generica['nombre']}"
                          + (f"   ({generica['grupos']} grupos fundidos)"
                             if generica["grupos"] else ""))

    if informe["vacias"]:
        lineas += ["", f"  ANCLAS SIN GRUPO esta corrida ({len(informe['vacias'])}). "
                       f"Su serie va en CERO,",
                   "  y cero aqui significa 'el agrupamiento no formo un grupo",
                   "  parecido', NO 'nadie consulto por esto'. No se puede leer",
                   "  como ausencia sin mirar antes esta lista:"]
        for vacia in informe["vacias"][:10]:
            lineas.append(f"    [{vacia['id']}] {vacia['nombre']}")

    if informe["parte_huerfana"] > 0.15:
        lineas += ["", "  AVISO: mas del 15% de las notas agrupadas no encontro",
                   "  ancla. Las anclas se estan quedando cortas para el corpus",
                   "  actual. Mira si son motivos nuevos de verdad; si no lo son,",
                   "  toca 'python -m clustering --anclar --rehacer', sabiendo que",
                   "  eso empieza una serie nueva y no continua la anterior."]
    return "\n".join(lineas)
