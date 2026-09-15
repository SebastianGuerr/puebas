"""
Poner los tres algoritmos en la misma mesa. Que gane algo tiene que significar algo.

    python -m patrones --comparar     mide los tres y escribe comparacion.csv

EL CRITERIO PRINCIPAL ES LA ESTABILIDAD, NO LA FORMA
    Sin etiquetas verdaderas no se puede medir si un agrupamiento es CORRECTO.
    Lo que si se puede medir, y es lo que decide, es si es REAL: si los mismos
    grupos vuelven a aparecer cuando se remuestrean los datos.

    Un grupo que no reaparece al quitar el 20% de las semanas no es un grupo:
    es una particion del ruido que el algoritmo tenia que devolver porque se le
    pidio devolver algo. Y esa diferencia no se ve mirando el resultado --
    salen grupos, tienen nombre, se pueden dibujar.

    El procedimiento es el de Hennig: remuestrear, reagrupar, y para cada grupo
    original buscar su mejor pareja en la nueva particion midiendo Jaccard. La
    media sobre muchas repeticiones es la estabilidad del grupo.

    Y los umbrales estan publicados, que es lo que lo hace utilizable como
    criterio y no como opinion:

        >= 0,85   muy estable
        >= 0,75   grupo valido
        0,60-0,75 hay un patron, pero QUE semanas exactamente pertenecen es
                  muy dudoso
        <= 0,50   disuelto: no se recupero

    CONSECUENCIA OPERATIVA, Y ES LA RAZON DE SER DE ESTE MODULO: un grupo por
    debajo de 0,60 no entra en ningun analisis posterior. Un grupo inestable
    produce una serie cuyo significado cambia entre corridas, y cualquier cosa
    que se encuentre sobre ella es ruido de asignacion.

LA SILUETA NO SE USA PARA HDBSCAN, Y ESO NO ES UN DETALLE
    Silueta, Davies-Bouldin y Calinski-Harabasz miden lo mismo con distintas
    caras: si los grupos son compactos y esfericos segun una DISTANCIA.

    HDBSCAN no busca eso. Busca regiones densas de cualquier forma. Medirlo con
    silueta y compararlo contra K-Prototypes es una competencia amanada: el
    ganador esta decidido por la metrica antes de empezar, y siempre gana el
    que optimiza algo parecido a la metrica.

    Aqui se calculan igual -- para los dos que SI suponen grupos redondos -- y
    para HDBSCAN se dejan en blanco a proposito, con esta nota al lado. Es mas
    util una celda vacia que dice por que que un numero que no significa nada.

    Para densidad la metrica correcta es DBCV, que mide densidad en vez de
    distancia. No esta en el entorno y no se agrega una dependencia por una
    columna: lo que decide es la estabilidad, que sirve para los tres por igual.

COMPARAR ALGORITMOS QUE DEVUELVEN COSAS DISTINTAS
    HDBSCAN deja semanas fuera -- etiqueta -1 -- y los otros dos asignan todas.
    Compararlos con la misma metrica sin decirlo favorece a HDBSCAN: es facil
    tener grupos limpios si se pueden tirar los casos dificiles.

    Aqui se resuelve reportando la fraccion de ruido como una columna mas y
    calculando las metricas de forma solo sobre lo asignado. Las dos cifras hay
    que leerlas juntas: 'grupos muy estables cubriendo el 40% de las semanas' y
    'grupos regulares cubriendo el 100%' no son comparables sin las dos.

EL ACUERDO ENTRE SEMILLAS SE MIDE CON AMI Y NO SOLO CON ARI
    Las dos corrigen por azar, que es lo que hace falta: dos particiones al
    azar dan cerca de cero y no cerca de 0,3.

    Se reportan ambas porque se comportan distinto con grupos desbalanceados, y
    aqui los grupos van a ser desbalanceados -- una temporada corta contra la
    normalidad larga. En ese caso AMI es la mas informativa; ARI penaliza mas
    partir un grupo grande. Si las dos discrepan mucho, eso mismo es el dato.
"""

import numpy as np
import pandas as pd

from patrones import agrupamiento, rutas

# Repeticiones del remuestreo. 100 es lo habitual en la literatura y es lo que
# se usa.
REPETICIONES = 100

# Reinicios de K-Prototypes DENTRO del remuestreo.
#
# Fuera del remuestreo son 25, que es lo que hace falta para que la solucion de
# referencia sea reproducible. Repetir eso cien veces son 2.500 ajustes por
# cada numero de grupos, y la comparacion pasa de segundos a la media hora.
#
# Se bajan a 5 aqui, y el efecto de hacerlo tiene un signo conocido: un ajuste
# con menos reinicios cae mas a menudo en un optimo local, o sea que se parece
# MENOS a la solucion de referencia de lo que se pareceria con 25. La
# estabilidad que sale es entonces una COTA INFERIOR.
#
# Eso es tolerable y lo contrario no lo seria. Un metodo que subestima la
# estabilidad hace descartar grupos que quiza servian; uno que la sobreestima
# hace construir encima de grupos que no existen. Entre los dos errores, este
# es el que se elige a proposito.
REINICIOS_REMUESTREO = 5

# Fraccion que se conserva en cada remuestreo.
FRACCION = 0.80

# Semillas para el acuerdo entre corridas. Distintas de agrupamiento.SEMILLA a
# proposito: la pregunta es si el resultado depende de la semilla.
SEMILLAS = (1, 7, 2024, 31415)

ESTABLE = 0.75
DUDOSO = 0.60

# ==========================================================
# LA TRAMPA DE LA ESTABILIDAD, Y POR QUE HAY UN SEGUNDO FILTRO
# ==========================================================
#
# La estabilidad por remuestreo tiene un modo de fallo que no se ve en la
# tabla, y en esta corrida se disparo. Medido sobre 84 semanas:
#
#     jerarquico k=3   tamanos [78, 4, 2]     estabilidad media 0,79
#     jerarquico k=4   tamanos [78, 2, 2, 2]  estabilidad media 0,89  <- 'gana'
#     kprototypes k=3  tamanos [35, 29, 20]   estabilidad media 0,72
#
# El enlace promedio no encontro cuatro tipos de semana: encontro una semana
# normal y tres parejas de semanas raras. Y eso puntua altisimo, porque el
# grupo de 78 vuelve a aparecer SIEMPRE -- es casi todo el conjunto, su Jaccard
# contra si mismo ronda 1 pase lo que pase -- y una pareja de valores atipicos
# tambien vuelve siempre, porque esos dos bloques no se parecen a nada y se
# reencuentran solos.
#
# O sea que la particion mas degenerada posible es la que mejor puntua. La
# estabilidad sigue siendo el criterio correcto; lo que hace falta es leerla
# contra su nulo, igual que clustering/validacion.py hace con la coherencia.
#
# El nulo aqui es la dominancia: que fraccion del total se lleva el grupo mayor.
# Por encima de este umbral la particion no es una tipologia -- es 'casi todo'
# mas unas migajas -- y queda DESCALIFICADA del veredicto aunque su estabilidad
# sea la mas alta de la tabla. Se sigue reportando, con el motivo al lado.
DOMINANCIA_MAXIMA = 0.70

# Y el otro extremo: un grupo de uno o dos bloques no es un grupo, es un valor
# atipico con nombre. Se cuentan aparte para que la columna 'grupos hallados'
# no los infle.
TAMANO_MINIMO_GRUPO = 3


def _jaccard(a, b):
    """Interseccion sobre union de dos conjuntos de indices."""
    interseccion = len(a & b)
    union = len(a | b)
    return interseccion / union if union else 0.0


def estabilidad(numericas, categoricas, algoritmo, n_grupos,
                repeticiones=REPETICIONES, fraccion=FRACCION, semilla=0):
    """
    La estabilidad por grupo segun Hennig. Devuelve un Jaccard por grupo.

    Se remuestrea SIN reemplazo (submuestreo del 80%) y no con reemplazo. Con
    reemplazo aparecen filas duplicadas, y una fila duplicada es un par a
    distancia cero que los algoritmos por densidad tratan como un nucleo: se
    estaria midiendo la reaccion del algoritmo a los duplicados y no su
    estabilidad.
    """
    funcion = agrupamiento.ALGORITMOS[algoritmo]
    pide_k = algoritmo in agrupamiento.PIDEN_K

    def ajustar(num, cat, reinicios=None):
        if algoritmo == "kprototypes":
            etiquetas, _ = funcion(num, cat, n_grupos,
                                   reinicios=reinicios
                                   or agrupamiento.REINICIOS)
        elif pide_k:
            etiquetas, _ = funcion(num, cat, n_grupos)
        else:
            etiquetas, _ = funcion(num, cat)
        return np.asarray(etiquetas)

    base = ajustar(numericas, categoricas)
    grupos = sorted(set(base) - {-1})
    if not grupos:
        return {}

    posicion = {b: i for i, b in enumerate(numericas.index)}
    originales = {g: {numericas.index[i] for i in np.where(base == g)[0]}
                  for g in grupos}
    acumulado = {g: [] for g in grupos}

    generador = np.random.default_rng(semilla)
    n = len(numericas)
    tamano = max(int(n * fraccion), 10)

    for _ in range(repeticiones):
        elegidos = generador.choice(n, size=tamano, replace=False)
        sub_num = numericas.iloc[elegidos]
        sub_cat = categoricas.iloc[elegidos]
        try:
            nuevas = ajustar(sub_num, sub_cat, REINICIOS_REMUESTREO)
        except Exception:
            continue

        conjuntos = [{sub_num.index[i] for i in np.where(nuevas == g)[0]}
                     for g in sorted(set(nuevas) - {-1})]
        presentes = set(sub_num.index)
        for grupo, miembros in originales.items():
            # Se compara contra el grupo original RESTRINGIDO a las filas que
            # entraron al remuestreo. Sin esa restriccion, el Jaccard bajaria
            # solo porque faltan filas, que es una propiedad del remuestreo y
            # no de la estabilidad del grupo.
            visible = miembros & presentes
            if not visible:
                continue
            acumulado[grupo].append(
                max((_jaccard(visible, c) for c in conjuntos), default=0.0))

    return {g: float(np.mean(v)) if v else float("nan")
            for g, v in acumulado.items()}


def acuerdo(numericas, categoricas, algoritmo, n_grupos, semillas=SEMILLAS):
    """
    ARI y AMI entre corridas con distinta semilla. Cuanto depende del azar.

    Para los algoritmos deterministas -- jerarquico, HDBSCAN -- da 1,0 por
    construccion, y eso tambien es informacion: dice que su variabilidad esta
    en los datos y no en la inicializacion, asi que su estabilidad hay que
    juzgarla solo por el remuestreo.
    """
    from sklearn.metrics import adjusted_mutual_info_score, adjusted_rand_score

    funcion = agrupamiento.ALGORITMOS[algoritmo]
    pide_k = algoritmo in agrupamiento.PIDEN_K
    particiones = []
    for semilla in semillas:
        try:
            if algoritmo == "kprototypes":
                etiquetas, _ = funcion(numericas, categoricas, n_grupos,
                                       semilla=semilla)
            elif pide_k:
                etiquetas, _ = funcion(numericas, categoricas, n_grupos)
            else:
                etiquetas, _ = funcion(numericas, categoricas)
            particiones.append(np.asarray(etiquetas))
        except Exception:
            continue

    if len(particiones) < 2:
        return float("nan"), float("nan")

    aris, amis = [], []
    for i in range(len(particiones)):
        for j in range(i + 1, len(particiones)):
            aris.append(adjusted_rand_score(particiones[i], particiones[j]))
            amis.append(adjusted_mutual_info_score(particiones[i],
                                                   particiones[j]))
    return float(np.mean(aris)), float(np.mean(amis))


def forma(numericas, categoricas, etiquetas, algoritmo):
    """
    Silueta, Davies-Bouldin y Calinski-Harabasz. Vacias para HDBSCAN.

    Ver el encabezado: aplicarlas a un algoritmo por densidad no da un
    resultado malo, da una comparacion amanada.
    """
    if algoritmo == "hdbscan":
        return {"silueta": np.nan, "davies_bouldin": np.nan,
                "calinski_harabasz": np.nan}

    from sklearn.metrics import (calinski_harabasz_score, davies_bouldin_score,
                                 silhouette_score)

    x = np.concatenate([agrupamiento.estandarizar(numericas),
                        0.5 * pd.get_dummies(categoricas.astype(str))
                        .to_numpy(dtype=float)], axis=1)
    asignados = etiquetas != -1
    x, y = x[asignados], etiquetas[asignados]
    if len(set(y)) < 2:
        return {"silueta": np.nan, "davies_bouldin": np.nan,
                "calinski_harabasz": np.nan}
    return {
        "silueta": float(silhouette_score(x, y)),
        "davies_bouldin": float(davies_bouldin_score(x, y)),
        "calinski_harabasz": float(calinski_harabasz_score(x, y)),
    }


def correr(numericas, categoricas, grupos=agrupamiento.GRUPOS, aviso=print):
    """
    Cada algoritmo a cada numero de grupos, con todas las metricas.

    Devuelve una fila por (algoritmo, n_grupos). HDBSCAN aparece una sola vez
    porque no acepta que se le pida un numero.
    """
    filas = []
    for algoritmo in agrupamiento.ALGORITMOS:
        candidatos = grupos if algoritmo in agrupamiento.PIDEN_K else (0,)
        for k in candidatos:
            try:
                if algoritmo in agrupamiento.PIDEN_K:
                    etiquetas, detalle = agrupamiento.ALGORITMOS[algoritmo](
                        numericas, categoricas, k)
                else:
                    etiquetas, detalle = agrupamiento.ALGORITMOS[algoritmo](
                        numericas, categoricas)
                etiquetas = np.asarray(etiquetas)
            except Exception as error:
                aviso(f"  {algoritmo} k={k}: no ajusto ({error})")
                continue

            jaccard = estabilidad(numericas, categoricas, algoritmo, k)
            valores = [v for v in jaccard.values() if np.isfinite(v)]
            ari, ami = acuerdo(numericas, categoricas, algoritmo, k)

            asignadas = etiquetas[etiquetas != -1]
            tamanos = (pd.Series(asignadas).value_counts()
                       if len(asignadas) else pd.Series(dtype=int))
            dominancia = (float(tamanos.max() / len(etiquetas))
                          if len(tamanos) else np.nan)

            fila = {
                "algoritmo": algoritmo,
                "grupos_pedidos": k if k else np.nan,
                "grupos_hallados": int(len(set(etiquetas) - {-1})),
                "grupos_con_cuerpo": int((tamanos >= TAMANO_MINIMO_GRUPO).sum()),
                "tamano_mayor": int(tamanos.max()) if len(tamanos) else 0,
                "dominancia": dominancia,
                "degenerada": bool(np.isfinite(dominancia)
                                   and dominancia > DOMINANCIA_MAXIMA),
                "ruido": float((etiquetas == -1).mean()),
                "estabilidad_media": float(np.mean(valores)) if valores else np.nan,
                "estabilidad_minima": float(np.min(valores)) if valores else np.nan,
                "grupos_estables": int(sum(v >= ESTABLE for v in valores)),
                "grupos_disueltos": int(sum(v <= 0.50 for v in valores)),
                "ari_entre_semillas": ari,
                "ami_entre_semillas": ami,
            }
            fila.update(forma(numericas, categoricas, etiquetas, algoritmo))
            filas.append(fila)
            aviso(f"  {algoritmo:<12} k={k or '-':<2} "
                  f"estabilidad {fila['estabilidad_media']:.2f} "
                  f"({fila['grupos_estables']} estables de "
                  f"{fila['grupos_hallados']})"
                  + ("  DEGENERADA: el mayor se lleva "
                     f"{fila['dominancia']:.0%}" if fila["degenerada"] else ""))

    return pd.DataFrame(filas)


def guardar(tabla):
    """Escribe la comparacion y devuelve su ruta."""
    tabla.to_csv(rutas.COMPARACION, index=False, encoding="utf-8-sig")
    return rutas.COMPARACION


def informe(tabla):
    """Cual gana, si gana alguno, y con que reserva."""
    lineas = [
        "COMPARACION DE LOS TRES AGRUPAMIENTOS DE BLOQUES",
        "",
        "  El criterio que decide es la ESTABILIDAD por remuestreo (Jaccard de",
        "  Hennig): si un grupo no reaparece al quitar el 20% de los bloques,",
        f"  no es un grupo. Valido desde {ESTABLE:.2f}; dudoso bajo {DUDOSO:.2f}.",
        "",
        "  La silueta va vacia para HDBSCAN a proposito: mide compacidad segun",
        "  distancia y HDBSCAN busca densidad. Compararlos con ella seria una",
        "  competencia amanada.",
        "",
        "  Y una estabilidad alta no basta: se lee contra la DOMINANCIA, que es",
        "  que fraccion se lleva el grupo mayor. Una particion de 'casi todo'",
        f"  mas migajas puntua altisimo sin significar nada. Por encima de",
        f"  {DOMINANCIA_MAXIMA:.0%} queda descalificada, marcada con (D).",
        "",
        "=" * 78,
        f"  {'algoritmo':<13}{'k':>3}{'halla':>6}{'cuerpo':>7}{'domin':>7}"
        f"{'ruido':>7}{'estab':>7}{'ARI':>6}{'silueta':>9}",
    ]

    for _, fila in tabla.iterrows():
        k = int(fila["grupos_pedidos"]) if np.isfinite(fila["grupos_pedidos"]) else "-"
        silueta = (f"{fila['silueta']:.3f}" if np.isfinite(fila["silueta"])
                   else "  n/a")
        marca = "(D)" if fila["degenerada"] else "   "
        lineas.append(
            f"  {fila['algoritmo']:<13}{str(k):>3}{fila['grupos_hallados']:>6}"
            f"{fila['grupos_con_cuerpo']:>7}{fila['dominancia']:>7.0%}"
            f"{fila['ruido']:>7.0%}{fila['estabilidad_media']:>7.2f}"
            f"{fila['ari_entre_semillas']:>6.2f}{silueta:>9} {marca}")

    degeneradas = tabla[tabla["degenerada"] & tabla["estabilidad_media"].notna()]
    if not degeneradas.empty:
        lineas += [
            "",
            f"  (D) {len(degeneradas)} configuracion(es) descalificadas por "
            f"dominancia. La mejor de",
            "  ellas por estabilidad era "
            f"{degeneradas.loc[degeneradas['estabilidad_media'].idxmax(), 'algoritmo']} "
            f"con {degeneradas['estabilidad_media'].max():.2f}, que sin esta",
            "  columna habria ganado la tabla siendo un solo grupo grande mas",
            "  parejas de semanas atipicas.",
        ]

    validos = tabla[(tabla["estabilidad_media"] >= ESTABLE)
                    & ~tabla["degenerada"]]
    lineas += ["", "=" * 78, "VEREDICTO", ""]

    if validos.empty:
        limpias = tabla[~tabla["degenerada"]]
        mejor = (limpias.loc[limpias["estabilidad_media"].idxmax()]
                 if limpias["estabilidad_media"].notna().any() else None)
        lineas += [
            f"  NINGUNA configuracion no degenerada llega a una estabilidad "
            f"media de {ESTABLE:.2f}.",
            "",
            "  La lectura correcta no es 'hay que probar otro algoritmo'. Es",
            "  que en esta tabla de bloques no hay tipos de semana que se",
            "  repitan lo bastante como para encontrarlos: los tres algoritmos",
            "  devuelven grupos porque se les pidio devolverlos.",
            "",
            "  Con 89 semanas y cuatro temas con volumen, es lo esperable. El",
            "  numero de bloques sube esperando y el de temas con volumen sube",
            "  ampliando la extraccion; ninguna de las dos cosas se arregla",
            "  cambiando de algoritmo.",
        ]
        if mejor is not None:
            lineas += [
                "",
                f"  El menos malo fue {mejor['algoritmo']} "
                f"(estabilidad {mejor['estabilidad_media']:.2f}), y aun asi",
                "  sus grupos no se pueden usar como unidad de analisis.",
            ]
    else:
        mejor = validos.loc[validos["estabilidad_media"].idxmax()]
        lineas += [
            f"  Gana {mejor['algoritmo']} con "
            f"{int(mejor['grupos_hallados'])} grupos: estabilidad media "
            f"{mejor['estabilidad_media']:.2f},",
            f"  {int(mejor['grupos_estables'])} de ellos por encima de {ESTABLE:.2f}.",
            "",
            "  Usar SOLO los grupos estables. Los que quedaron por debajo de",
            f"  {DUDOSO:.2f} no entran en ningun analisis posterior: su composicion",
            "  cambia entre corridas y cualquier patron que muestren es ruido",
            "  de asignacion.",
        ]

    lineas += [
        "",
        "COMO LEER EL RUIDO DE HDBSCAN",
        "",
        "  No es un defecto: es la unica columna que dice cuantos bloques NO se",
        "  parecen a ningun otro. Un HDBSCAN con grupos muy estables cubriendo",
        "  el 40% de las semanas y un K-Prototypes regular cubriendo el 100% no",
        "  se comparan por la estabilidad sola: hay que leer las dos columnas.",
        "",
        "  Y hay una comprobacion pendiente que conviene hacer antes de",
        "  construir encima: si la fraccion de ruido varia con la epoca del",
        "  ano, entonces el ruido es el mismo una senal estacional, y los",
        "  grupos 'limpios' lo estan porque le pasaron el problema a la basura.",
    ]
    return "\n".join(lineas) + "\n"
