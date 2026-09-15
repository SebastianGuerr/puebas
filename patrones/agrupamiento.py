"""
Agrupar BLOQUES DE TIEMPO, no notas. Tres algoritmos sobre la misma tabla.

    python -m patrones --agrupar      ajusta los tres y escribe agrupamiento.csv

QUE SE AGRUPA AQUI Y POR QUE NO ES LO MISMO QUE HACE clustering/
    clustering/ agrupa NOTAS por lo que dicen: junta 'me duele la barriga' con
    'dolor abdominal'. Eso ya esta hecho y este paquete no lo repite.

    Aqui las filas son SEMANAS (o dias). Cada fila es un pedazo de tiempo
    descrito por dos cosas a la vez: de que consulto la gente esa semana -- la
    composicion de temas -- y como fue esa semana por fuera: cuanto llovio, si
    hubo festivo, en que mes cayo.

    Lo que sale es una tipologia de semanas. 'Semanas lluviosas de mitad de ano
    con mucha consulta gastrointestinal' seria un grupo. Es una forma distinta
    de buscar el patron que persigue el proyecto: en vez de preguntar si una
    variable mueve un tema, pregunta si hay TIPOS de semana que se repitan.

    Y es el nivel en el que los tres algoritmos que se querian comparar tienen
    sentido a la vez, que es la otra razon para ponerlos aqui.

POR QUE K-PROTOTYPES NO VA SOBRE LOS EMBEDDINGS, AUNQUE SE PUEDA
    Es la tentacion obvia -- ya hay una matriz de vectores en embedding/ -- y
    esta mal.

    K-Prototypes mezcla columnas numericas y categoricas ponderando las
    segundas con un escalar gamma. Con 384 dimensiones continuas y tres
    columnas categoricas, gamma tendria que compensar un desbalance de dos
    ordenes de magnitud, y el resultado depende enteramente de un numero que
    nadie sabe fijar. Cualquier valor que se elija se puede defender igual de
    mal.

    Sobre bloques de tiempo el reparto es razonable: una docena de columnas
    numericas contra tres o cuatro categoricas. Ahi gamma hace lo que dice.

    El camino correcto para lo otro -- texto y categorias juntos -- es el que
    el proyecto ya tomo: agrupar el texto por su cuenta en clustering/ y cruzar
    el resultado con las categoricas despues. Que es exactamente lo que hacen
    tablero.py y modelos.py.

LOS TRES, Y QUE PREGUNTA CONTESTA CADA UNO
    K-Prototypes      el unico que mete las categoricas EN la distancia. Pide
                      el numero de grupos por adelantado y supone grupos
                      redondos. Es la referencia con la que se comparan los
                      otros dos.

    HDBSCAN           por densidad. No pide el numero de grupos y, sobre todo,
                      declara RUIDO: las semanas que no se parecen a ninguna
                      otra se quedan sin grupo en vez de forzarse dentro del
                      mas cercano. Para buscar temporadas es la propiedad que
                      importa -- un brote de seis semanas es una region densa
                      con forma de lo que sea, y las otras 83 semanas no
                      tienen por que pertenecer a nada.

    Jerarquico        con enlace promedio. Da el arbol completo, asi que deja
                      ver la estructura a varias escalas en vez de un corte.

    Ninguno es 'el bueno'. Lo que decide cual se usa es comparacion.py, y el
    criterio principal no es una metrica de forma sino la ESTABILIDAD: si un
    grupo no reaparece al remuestrear, no existe.

WARD NO SE USA, Y NO ES UN DESCUIDO
    Ward es el enlace por defecto en casi todo ejemplo de clustering
    jerarquico, y es INVALIDO con cualquier distancia que no sea euclidea: su
    criterio -- minimizar el aumento de la suma de cuadrados dentro del grupo
    -- esta definido sobre geometria euclidea y nada mas. scikit-learn lo
    prohibe explicitamente y lanza error si se le pide Ward con coseno.

    Aqui las columnas van estandarizadas y la distancia es euclidea, asi que
    Ward SERIA legal. Se usa enlace promedio de todos modos porque Ward tiende
    a partir en grupos del mismo tamano, y no hay ninguna razon para creer que
    los tipos de semana vengan en porciones iguales: una temporada de brote es
    corta y la normalidad es larga.

LAS COLUMNAS SE ESTANDARIZAN SIEMPRE, Y ESO NO ES COSMETICA
    Sin estandarizar, precip_30d (desviacion 145) aplastaria a
    temp_media_consenso (desviacion 0,60) por un factor de 240, y el
    agrupamiento seria un agrupamiento por lluvia acumulada con adornos.

    En K-Prototypes es todavia mas grave: su gamma por defecto se calcula como
    la mitad del promedio de las desviaciones de las columnas numericas, asi
    que sin estandarizar el peso de TODAS las categoricas queda amarrado a la
    escala de la columna numerica mas grande. Es un efecto invisible que
    cambia el resultado entero.
"""

import numpy as np
import pandas as pd

from patrones import rutas

SEMILLA = 12345

# Cuantos grupos se le piden a los algoritmos que los exigen. No es un valor
# elegido a ojo: comparacion.py barre este rango y reporta la estabilidad de
# cada uno, que es lo que decide.
#
# El rango empieza en 3 y no en 2 porque partir en dos no es una tipologia, y
# termina en 6 porque con 89 semanas el septimo grupo ya promedia doce bloques
# y a esa altura la estabilidad se derrumba sola. Subirlo cuesta caro: cada
# valor mas son 100 remuestreos x 2 algoritmos, y el barrido pasa de minutos a
# la media hora sin agregar una fila que vaya a sobrevivir.
GRUPOS = (3, 4, 5, 6)

# Reinicios de K-Prototypes. Converge a optimos locales sensibles a la
# inicializacion, asi que uno solo no dice nada; 25 es lo que se recomienda
# como minimo para que la solucion sea reproducible.
REINICIOS = 25

# El grupo mas pequeno que HDBSCAN puede declarar. Con 89 semanas, pedir menos
# de 4 seria dejarle llamar 'temporada' a tres semanas sueltas.
TAMANO_MINIMO = 4


def matriz(tablero, columna="parte", minimo_notas=200):
    """
    Una fila por bloque: composicion de temas + clima + categoricas.

    Devuelve (numericas, categoricas, indice). Van separadas porque
    K-Prototypes las necesita asi y porque juntarlas obligaria a decidir aqui
    como se codifican, que es una decision de cada algoritmo.

    SE USA LA COMPOSICION Y NO EL CONTEO
        Igual que en todo el paquete: el conteo arrastra la deriva de la
        cobertura, asi que dos semanas identicas en composicion pero de anos
        distintos caerian en grupos distintos solo por eso. Con 'parte' no.
    """
    grandes = (tablero.groupby("ancla")["notas"].sum()
               .loc[lambda s: s >= minimo_notas].index)
    grandes = [a for a in grandes if a != -1]
    if not len(grandes):
        raise SystemExit(
            f"Ningun tema llega a {minimo_notas} notas, asi que no hay "
            f"composicion que agrupar.\n"
            f"Es la misma falta que reporta potencia.py: el corpus es una "
            f"muestra.")

    composicion = (tablero[tablero["ancla"].isin(grandes)]
                   .pivot_table(index="bloque", columns="nombre",
                                values=columna, aggfunc="sum", fill_value=0.0))
    composicion.columns = [f"parte_{c}" for c in composicion.columns]

    contexto = tablero.drop_duplicates("bloque").set_index("bloque")
    numericas_clima = [c for c in contexto.columns
                       if c.startswith(("precip_", "temp_", "humedad_",
                                        "viento_", "radiacion_"))]
    numericas = composicion.join(contexto[numericas_clima])

    # Las categoricas describen CUANDO fue el bloque, que es justo lo que una
    # columna numerica no puede decir: 'marzo' no es menor que 'abril'.
    categoricas = pd.DataFrame(index=numericas.index)
    categoricas["mes"] = contexto["fecha_inicio"].dt.month.astype(str)
    categoricas["trimestre"] = contexto["fecha_inicio"].dt.quarter.astype(str)

    # LA TEMPORADA CLIMATICA ES LA CATEGORICA QUE JUSTIFICA K-PROTOTYPES.
    #
    # 'Lluviosa-templada' no es mayor ni menor que 'Seca-templada', asi que
    # meterla como numero seria inventarle un orden. Codificada como tres
    # indicadoras tampoco es lo mismo: la distancia entre dos semanas de
    # temporadas distintas seria sqrt(2) para cualquier par, que da la
    # casualidad de que es lo que hace bien la distancia de Hamming de
    # K-Prototypes y lo que las otras dos tienen que aproximar.
    #
    # Es, en concreto, la razon por la que valia la pena tener los tres
    # algoritmos y no solo uno: sin una categorica de verdad, K-Prototypes no
    # aporta nada sobre un k-means.
    if "temporada" in contexto.columns:
        dominante = contexto["temporada"]
        if dominante.notna().any():
            categoricas["temporada"] = dominante.fillna("sin dato").astype(str)
    if "dias_es_festivo" in contexto.columns:
        categoricas["con_festivo"] = np.where(
            contexto["dias_es_festivo"] > 0, "si", "no")
    if "dias_lluvia_fuerte" in contexto.columns:
        categoricas["aguacero"] = np.where(
            contexto["dias_lluvia_fuerte"] > 0, "si", "no")

    # Los bloques incompletos -- la primera y la ultima semana -- se caen. Una
    # semana de tres dias tiene menos de todo sin que haya pasado nada, y
    # metida entre las completas seria siempre un valor atipico y casi siempre
    # su propio grupo.
    if "dias_en_bloque" in contexto.columns:
        completos = contexto["dias_en_bloque"] >= contexto["dias_en_bloque"].max()
        numericas = numericas[completos]
        categoricas = categoricas[completos]

    numericas = numericas.dropna()
    categoricas = categoricas.loc[numericas.index]
    return numericas, categoricas


def estandarizar(numericas):
    """Media cero y desviacion uno. Ver el encabezado: no es cosmetica."""
    valores = numericas.to_numpy(dtype=float)
    centro = valores.mean(axis=0)
    escala = valores.std(axis=0, ddof=0)
    escala[escala == 0] = 1.0
    return (valores - centro) / escala


# ==========================================================
# LOS TRES
# ==========================================================

def kprototypes(numericas, categoricas, n_grupos, semilla=SEMILLA,
                reinicios=REINICIOS, gamma=None):
    """
    K-Prototypes: el unico que mete las categoricas en la distancia.

    gamma por defecto lo calcula la libreria como la mitad del promedio de las
    desviaciones de las columnas numericas. Sobre columnas ya estandarizadas
    esa desviacion es 1, asi que gamma sale 0,5: cada desacuerdo categorico
    pesa medio punto de distancia numerica. Es un valor razonable Y es
    verificable, que es mas de lo que se puede decir del mismo calculo sobre
    columnas sin estandarizar.
    """
    from kmodes.kprototypes import KPrototypes

    x_num = estandarizar(numericas)
    x_cat = categoricas.astype(str).to_numpy()
    matriz_mixta = np.concatenate([x_num, x_cat], axis=1)
    indice_categoricas = list(range(x_num.shape[1], matriz_mixta.shape[1]))

    modelo = KPrototypes(n_clusters=n_grupos, init="Huang", n_init=reinicios,
                         gamma=gamma, random_state=semilla, verbose=0)
    etiquetas = modelo.fit_predict(matriz_mixta, categorical=indice_categoricas)
    return np.asarray(etiquetas), {"gamma": float(modelo.gamma),
                                   "costo": float(modelo.cost_)}


def hdbscan(numericas, categoricas, tamano_minimo=TAMANO_MINIMO):
    """
    HDBSCAN: por densidad, sin numero de grupos y CON ruido.

    Las categoricas entran como indicadoras 0/1 escaladas a la mitad, que es el
    mismo peso que les da gamma en K-Prototypes. No es una equivalencia exacta
    -- una distancia euclidea sobre indicadoras no es la distancia de Hamming
    -- pero pone a los dos algoritmos a mirar aproximadamente la misma
    geometria, que es la condicion para que compararlos signifique algo.

    Se usa el HDBSCAN de scikit-learn y no el paquete suelto. Los dos existen
    en el entorno y dan resultados distintos en algunos casos; se elige el de
    scikit-learn porque es el que no puede quedar sin mantenimiento. Lo que no
    se puede es mezclarlos entre corridas, asi que queda escrito aqui.
    """
    from sklearn.cluster import HDBSCAN

    x = np.concatenate([estandarizar(numericas),
                        0.5 * pd.get_dummies(categoricas.astype(str))
                        .to_numpy(dtype=float)], axis=1)
    modelo = HDBSCAN(min_cluster_size=tamano_minimo,
                     min_samples=max(2, tamano_minimo // 2))
    etiquetas = modelo.fit_predict(x)
    ruido = float((etiquetas == -1).mean())
    return etiquetas, {"ruido": ruido,
                       "grupos": int(len(set(etiquetas) - {-1}))}


def jerarquico(numericas, categoricas, n_grupos):
    """
    Aglomerativo con enlace promedio. Ver el encabezado sobre Ward.

    Enlace promedio y no completo porque el completo tiende a grupos compactos
    y de tamano parecido, y la cola larga de este problema -- temporadas cortas
    contra normalidad larga -- es justo lo que eso aplastaria.
    """
    from sklearn.cluster import AgglomerativeClustering

    x = np.concatenate([estandarizar(numericas),
                        0.5 * pd.get_dummies(categoricas.astype(str))
                        .to_numpy(dtype=float)], axis=1)
    modelo = AgglomerativeClustering(n_clusters=n_grupos, linkage="average")
    return modelo.fit_predict(x), {}


ALGORITMOS = {
    "kprototypes": kprototypes,
    "hdbscan": hdbscan,
    "jerarquico": jerarquico,
}

# Cuales necesitan que se les diga el numero de grupos.
PIDEN_K = {"kprototypes", "jerarquico"}


def correr(numericas, categoricas, n_grupos, aviso=print):
    """Los tres sobre la misma tabla. Devuelve etiquetas y detalles."""
    salida, detalles = {}, {}
    for nombre, funcion in ALGORITMOS.items():
        try:
            if nombre in PIDEN_K:
                etiquetas, detalle = funcion(numericas, categoricas, n_grupos)
            else:
                etiquetas, detalle = funcion(numericas, categoricas)
        except Exception as error:
            aviso(f"  {nombre}: no se pudo ajustar ({error})")
            continue
        salida[nombre] = np.asarray(etiquetas)
        detalles[nombre] = detalle
        encontrados = len(set(etiquetas) - {-1})
        aviso(f"  {nombre}: {encontrados} grupos"
              + (f", {detalle['ruido']:.0%} de ruido" if "ruido" in detalle else ""))
    return salida, detalles


def guardar(indice, etiquetas):
    """Una fila por bloque con la etiqueta de cada algoritmo."""
    tabla = pd.DataFrame({"bloque": indice})
    for nombre, valores in etiquetas.items():
        tabla[nombre] = valores
    tabla.to_csv(rutas.AGRUPAMIENTO, index=False, encoding="utf-8-sig")
    return rutas.AGRUPAMIENTO
