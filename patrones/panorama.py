"""
El panorama: todo el historico en un solo eje de tiempo, y los temas agrupados
por como se mueven.

    python -m patrones --panorama              escribe las tres figuras
    python -m patrones --panorama --ventana    ademas las abre para navegarlas

QUE CONTESTA ESTO QUE NO CONTESTABAN LAS FIGURAS QUE YA HABIA
    vistas.py dibuja un calendario por tema: ocho figuras separadas, cada una
    con su escala. Para ver si un motivo sube cuando llueve hay que recordar la
    figura anterior mientras se mira la siguiente, y el ojo no hace eso.

    Aqui todo va en UN eje de tiempo compartido -- la lluvia arriba, los
    motivos en medio, el volumen de triage abajo, y las temporadas climaticas
    pintadas de fondo atravesando los cuatro paneles. Una coincidencia aparece
    entonces como una columna vertical, que es la unica forma en que el ojo la
    detecta sin ayuda.

    Esto NO es una prueba y no gasta una. Es lo que produce la hipotesis que
    luego se escribe en datos/variables.csv y se prueba con --modelar. El orden
    sigue siendo mirar primero y probar despues.

POR QUE SE AGRUPAN LOS TEMAS ANTES DE DIBUJARLOS
    Porque por separado no se pueden ver. El tema mas grande son 672 notas en
    89 semanas: 7,5 por semana, y el resto menos. Una linea de 7 notas
    semanales es casi toda ruido de muestreo, y potencia.py ya puso cifra a
    eso: el efecto mas pequeno que hoy se distingue del azar es un riesgo
    relativo de 1,15, cuando los efectos de clima que se publican estan entre
    1,02 y 1,10.

    Juntar los temas que se mueven juntos es la unica palanca que sube la
    cuenta por serie sin esperar a la extraccion completa. Cuatro familias dan
    series de decenas de notas por semana, que ya tienen forma.

    La idea es el modo 'perfil (correlacion)' del Time Series Clustering de
    ArcGIS -- agrupar series que suben y bajan a la vez, sin importar su
    tamano -- pero aplicada a los TEMAS y no a lugares. Esa herramienta agrupa
    celdas de un mapa y aqui hay un solo lugar: el hospital. Lo que se
    aprovecha es el criterio, no el producto.

LAS TRES TRAMPAS DE AGRUPAR ESTAS SERIES, Y COMO SE ESQUIVA CADA UNA
    1. LA TENDENCIA DEL DENOMINADOR. La cobertura de HCTMOTCON cae unos 9
       puntos por ano (ver clustering/fechas.py). Sobre CONTEOS, los temas
       bajan todos a la vez y correlacionan todos con todos: saldria una sola
       familia gigante cuyo significado es 'el ano va pasando'. Por eso se
       agrupa sobre la PROPORCION respecto a las notas procesadas de esa misma
       semana, que es la columna que fechas.py dice que hay que modelar.

    2. LA COMPOSICION. Las proporciones de una misma semana suman uno, asi que
       un tema que sube obliga a los demas a bajar aunque no pase nada:
       aparecen correlaciones negativas fabricadas por la aritmetica. La
       correccion estandar es el log-ratio centrado (CLR) de Aitchison, que es
       lo que se aplica, con el resto de la composicion -- lo no agrupado y los
       temas chicos -- incluido como una parte mas para que la referencia del
       centrado este completa.

    3. EL CICLO SEMANAL. Es la senal mas grande de toda la serie (lunes 219,8
       triages contra domingo 145,1). Agrupando por SEMANA desaparece por
       construccion: cada bloque contiene exactamente un lunes y un domingo.
       Ese es el motivo de que el bloque sea la semana y no el dia.

EL CRITERIO QUE DECIDE SI LAS FAMILIAS VALEN NO ES LA SILUETA
    Es la estabilidad, igual que en comparacion.py: se remuestrea y se mira con
    Jaccard si cada familia reaparece (>=0,75 valida, <=0,50 disuelta). Una
    familia que no reaparece no es una familia, es una particion del ruido.

    Lo que se remuestrea aqui son las SEMANAS y no los temas. En comparacion.py
    las filas son bloques de tiempo y se submuestrean esas filas; aqui las
    filas son temas y lo escaso -- lo que hace fragil la correlacion -- son las
    89 semanas de las que se calcula. Submuestrear temas mediria otra cosa.

    Y conviene decirlo antes de mirar el numero: con 89 semanas y estas
    cuentas, lo esperable es que las familias salgan a medio camino. Si salen
    bajas, la lectura correcta es que el agrupamiento no es de fiar todavia, no
    que se busquen otros parametros hasta que suba.

LO QUE SE VE EN EL PANORAMA Y LO QUE NO SE PUEDE VER
    Se ve: rachas, coincidencias, el ciclo de la lluvia, los huecos.
    No se ve, y no hay figura que lo arregle: si el patron se repite de un ano
    al otro. La ventana son 615 dias, 1,7 ciclos anuales. La temporada seca de
    esta ventana cae casi entera en la segunda mitad, o sea en la misma mitad
    donde cae la caida de la cobertura. Cualquier patron estacional que se vea
    aqui esta confundido con el tiempo, y eso ya se midio: el chi-cuadrado por
    temporada sale p<0,0001 en el agregado y no replica entre 2025 y 2026
    (correlacion de residuos +0,31). Mirar esta figura es un buen punto de
    partida y un pesimo punto final.
"""

import numpy as np
import pandas as pd

from patrones import rutas

# El bloque. Semanas que empiezan en lunes, que es como esta construido el
# ciclo laboral que domina la serie.
FRECUENCIA = "W-MON"

# Cuantas familias. Cuatro porque cuatro son los colores que vistas.py tiene
# verificados para lineas distinguibles entre si, incluida vision con
# deuteranopia. Con seis lineas no hay paleta que separe, y antes que repartir
# colores que se confunden se dibujan menos lineas.
N_FAMILIAS = 4

# Dias con datos que tiene que tener una semana para que se dibuje y se
# cuente. La ventana empieza un miercoles y termina un lunes, asi que la
# primera y la ultima semana estan cortadas: la ultima tiene UN dia, y una
# proporcion calculada sobre un dia salta a donde quiera. Se ven en la figura
# como un latigazo final que no significa nada, asi que se quitan.
MINIMO_DIAS_SEMANA = 5

# Notas en toda la ventana para que un tema entre al agrupamiento. Por debajo
# de esto la serie semanal es cero casi siempre y su correlacion con cualquier
# cosa esta dominada por donde cayeron las cuatro semanas que no son cero.
MINIMO_NOTAS = 40

# La pseudocuenta del CLR. El log-ratio no admite ceros y aqui hay muchos: se
# suma medio caso a cada celda, que es la convencion para tablas de conteos.
PSEUDOCUENTA = 0.5

# El remuestreo de la estabilidad. Los mismos de comparacion.py.
REPETICIONES = 200
FRACCION = 0.80

# Los rezagos del perfil, en dias. Los mismos de asociacion.REZAGOS.
REZAGOS = tuple(range(0, 15))


# ==========================================================
# DE LA SERIE DIARIA A LA MATRIZ TEMA x SEMANA
# ==========================================================

def semanal(serie, minimo_notas=MINIMO_NOTAS):
    """
    Devuelve (notas, procesadas, nombres): la matriz semana x tema y su denominador.

    'procesadas' es la SUMA de la semana, no el promedio de los dias: la
    proporcion correcta es el cociente de las sumas y no la media de los
    cocientes diarios, que le daria el mismo peso a un domingo de tres notas
    que a un lunes de veinte.
    """
    serie = serie.copy()
    serie["fecha"] = pd.to_datetime(serie["fecha"])

    por_dia = serie.drop_duplicates("fecha").set_index("fecha")["procesadas"]
    agrupado = por_dia.resample(FRECUENCIA, label="left", closed="left")
    total = agrupado.sum()[agrupado.count() >= MINIMO_DIAS_SEMANA]

    reales = serie[serie["ancla"] != -1]
    grandes = (reales.groupby(["ancla", "nombre"])["notas"].sum()
               .sort_values(ascending=False))
    grandes = grandes[grandes >= minimo_notas]
    if grandes.empty:
        raise SystemExit(
            f"Ningun tema llega a {minimo_notas} notas en la ventana. "
            f"El agrupamiento por forma no tiene sobre que calcularse.")

    anclas = [int(a) for a, _ in grandes.index]
    nombres = {int(a): n for a, n in grandes.index}

    notas = (reales[reales["ancla"].isin(anclas)]
             .pivot_table(index="fecha", columns="ancla", values="notas",
                          aggfunc="sum", fill_value=0)
             .resample(FRECUENCIA, label="left", closed="left").sum()
             .reindex(columns=anclas, fill_value=0)
             .reindex(total.index, fill_value=0))

    return notas, total, nombres


def _clr(notas, procesadas):
    """
    Log-ratio centrado de la composicion semanal. Devuelve solo las columnas de tema.

    La composicion lleva una parte mas -- 'resto' -- con lo que la semana
    proceso y no cayo en ninguno de estos temas: el 17% sin tema mas los temas
    chicos que no entraron. Sin ella la referencia del centrado serian solo los
    temas grandes, y el CLR estaria midiendo cada tema contra sus hermanos en
    vez de contra el total, que es justo la confusion que viene a quitar.
    """
    resto = (procesadas - notas.sum(axis=1)).clip(lower=0)
    completa = notas.copy()
    completa["resto"] = resto

    partes = completa.to_numpy(dtype=float) + PSEUDOCUENTA
    partes = partes / partes.sum(axis=1, keepdims=True)
    log = np.log(partes)
    centrado = log - log.mean(axis=1, keepdims=True)

    return pd.DataFrame(centrado[:, :notas.shape[1]],
                        index=notas.index, columns=notas.columns)


def _distancia(matriz):
    """
    Uno menos la correlacion de Pearson entre temas. Devuelve (distancia, correlacion).

    Es la distancia de perfil: dos temas estan cerca si suben y bajan a la vez,
    sin importar cual de los dos es mas grande. Un tema de 40 notas y uno de
    670 pueden caer en la misma familia, y esa es la intencion.
    """
    correlacion = np.corrcoef(matriz.to_numpy().T)
    correlacion = np.nan_to_num(correlacion, nan=0.0)
    np.fill_diagonal(correlacion, 1.0)
    distancia = 1.0 - correlacion
    np.fill_diagonal(distancia, 0.0)
    return np.clip(distancia, 0.0, 2.0), correlacion


def _particion(distancia, n_familias):
    """Aglomerativo con enlace promedio sobre la distancia ya calculada."""
    from sklearn.cluster import AgglomerativeClustering

    # Enlace promedio y no Ward, por lo mismo que en comparacion.py: el
    # criterio de Ward esta definido sobre geometria euclidea -- scikit-learn
    # ni siquiera lo acepta con una distancia precalculada -- y ademas parte en
    # grupos de tamano parecido, y no hay razon para creer que los motivos de
    # consulta vengan repartidos en porciones iguales.
    modelo = AgglomerativeClustering(n_clusters=n_familias,
                                     metric="precomputed", linkage="average")
    return modelo.fit_predict(distancia)


def _estabilidad(clr, n_familias, repeticiones=REPETICIONES,
                 fraccion=FRACCION, semilla=0):
    """
    El Jaccard de Hennig por familia, remuestreando SEMANAS. Devuelve un dict.

    Para cada repeticion se recalculan las correlaciones con el 80% de las
    semanas y se vuelve a agrupar. Cada familia original se empareja con la
    familia nueva que mas se le parezca y se guarda ese Jaccard. La media de
    esos maximos es la estabilidad de la familia.
    """
    base = _particion(_distancia(clr)[0], n_familias)
    originales = {int(f): set(np.where(base == f)[0]) for f in sorted(set(base))}
    acumulado = {f: [] for f in originales}

    generador = np.random.default_rng(semilla)
    n_semanas = len(clr)
    tamano = max(int(round(n_semanas * fraccion)), 20)

    for _ in range(repeticiones):
        filas = generador.choice(n_semanas, size=tamano, replace=False)
        parcial = clr.iloc[np.sort(filas)]
        if float(parcial.std().min()) == 0.0:
            continue
        try:
            etiquetas = _particion(_distancia(parcial)[0], n_familias)
        except Exception:
            continue
        nuevas = [set(np.where(etiquetas == f)[0])
                  for f in sorted(set(etiquetas))]
        for familia, miembros in originales.items():
            acumulado[familia].append(
                max((len(miembros & otra) / len(miembros | otra)
                     for otra in nuevas if miembros | otra), default=0.0))

    return {f: float(np.mean(v)) if v else float("nan")
            for f, v in acumulado.items()}


def familias(serie, n_familias=N_FAMILIAS, minimo_notas=MINIMO_NOTAS,
             semilla=0):
    """
    Agrupa los temas por la forma de su serie semanal. Devuelve un dict con todo.

    Las claves son: asignacion (un renglon por tema), correlacion (la matriz
    tema x tema), orden (las posiciones de los temas ordenadas por familia,
    para dibujar la matriz en bloques), estabilidad (el Jaccard de cada
    familia), clr, notas, procesadas, nombres y n_familias.
    """
    notas, procesadas, nombres = semanal(serie, minimo_notas)
    clr = _clr(notas, procesadas)

    distancia, correlacion = _distancia(clr)
    etiquetas = _particion(distancia, n_familias)

    asignacion = pd.DataFrame({
        "ancla": [int(a) for a in notas.columns],
        "nombre": [nombres[int(a)] for a in notas.columns],
        "familia": etiquetas.astype(int),
        "notas": notas.sum(axis=0).to_numpy(),
    })

    # Las familias se renumeran por tamano, de mayor a menor, para que la
    # familia 1 sea siempre la mas grande y el color no cambie de significado
    # entre una corrida y la siguiente. El algoritmo las numera segun el orden
    # en que fusiona, que no significa nada.
    orden_familias = (asignacion.groupby("familia")["notas"].sum()
                      .sort_values(ascending=False).index)
    renumerar = {int(vieja): nueva for nueva, vieja in enumerate(orden_familias)}
    asignacion["familia"] = asignacion["familia"].map(renumerar)

    estable = _estabilidad(clr, n_familias, semilla=semilla)
    estabilidad = {renumerar[f]: v for f, v in estable.items()
                   if f in renumerar}

    asignacion = asignacion.sort_values(["familia", "notas"],
                                        ascending=[True, False])
    posicion = {int(a): i for i, a in enumerate(notas.columns)}
    orden = [posicion[int(a)] for a in asignacion["ancla"]]

    return {"asignacion": asignacion.reset_index(drop=True),
            "correlacion": correlacion, "orden": orden,
            "estabilidad": estabilidad, "clr": clr, "notas": notas,
            "procesadas": procesadas, "nombres": nombres,
            "n_familias": n_familias}


# ==========================================================
# LAS SERIES QUE SE DIBUJAN
# ==========================================================

def _completas(serie, frecuencia):
    """El indice de bloques con dias suficientes. Diario no filtra nada."""
    por_dia = serie.drop_duplicates("fecha").set_index("fecha")["procesadas"]
    agrupado = por_dia.resample(frecuencia, label="left", closed="left")
    suma = agrupado.sum()
    if frecuencia == "D":
        return suma
    return suma[agrupado.count() >= MINIMO_DIAS_SEMANA]


def series_familias(serie, asignacion, frecuencia=FRECUENCIA):
    """
    La proporcion de cada familia, en porcentaje. Devuelve (proporcion, notas, procesadas).

    Proporcion y no conteo, por la misma razon de siempre: el conteo arrastra
    la caida de la cobertura del motivo y bajaria aunque no cambiara nada.
    """
    serie = serie.copy()
    serie["fecha"] = pd.to_datetime(serie["fecha"])
    de_familia = dict(zip(asignacion["ancla"], asignacion["familia"]))

    reales = serie[serie["ancla"].isin(de_familia)].copy()
    reales["familia"] = reales["ancla"].map(de_familia)

    notas = (reales.pivot_table(index="fecha", columns="familia",
                                values="notas", aggfunc="sum", fill_value=0)
             .resample(frecuencia, label="left", closed="left").sum())
    procesadas = _completas(serie, frecuencia)
    notas = notas.reindex(procesadas.index, fill_value=0)

    proporcion = notas.div(procesadas.replace(0, np.nan), axis=0) * 100
    return proporcion, notas, procesadas


def diaria_familias(serie, asignacion):
    """La misma proporcion pero por dia. La necesita el perfil de rezagos."""
    return series_familias(serie, asignacion, frecuencia="D")


def rezagos(serie, diario, asignacion, variable="precip_consenso_mm",
            ventana=7, lista=REZAGOS):
    """
    Correlacion de cada familia con la variable a cada rezago, tras pre-blanqueo.

    Reutiliza asociacion._blanquear, que es el mismo filtro AR(7) que usa la
    busqueda exploratoria: sin el, dos series con tendencia correlacionan
    aunque no tengan nada que ver, y estas dos la tienen.

    ESTAS CIFRAS NO SON PRUEBAS Y NO LLEVAN CORRECCION POR MULTIPLICIDAD. Son
    la FORMA de la relacion, que es lo que distingue un efecto real -- sube,
    hace maximo y baja -- de un pico suelto entre catorce rezagos planos.
    """
    from patrones import asociacion

    proporcion, _, _ = diaria_familias(serie, asignacion)
    exposicion = (diario.set_index("fecha")[variable].astype(float)
                  .rolling(ventana, min_periods=max(2, ventana // 2)).mean())

    filas = []
    for familia in sorted(proporcion.columns):
        objetivo = proporcion[familia]
        comun = exposicion.index.intersection(objetivo.index)
        x_base = exposicion.reindex(comun)
        y_base = objetivo.reindex(comun)
        for rezago in lista:
            x = x_base.shift(rezago)
            blanca_x, blanca_y = asociacion._blanquear(x, y_base)
            r, p, n = asociacion._correlacion(blanca_x, blanca_y)
            filas.append({"familia": int(familia), "rezago_dias": rezago,
                          "correlacion": r, "p_crudo": p, "n": n})
    return pd.DataFrame(filas)


# ==========================================================
# GUARDAR Y CONTAR
# ==========================================================

def guardar(agrupadas, proporcion, perfil):
    """Escribe las tres tablas y devuelve sus rutas."""
    rutas.SALIDAS.mkdir(parents=True, exist_ok=True)
    agrupadas["asignacion"].to_csv(rutas.FAMILIAS, index=False,
                                   encoding="utf-8-sig")
    proporcion.to_csv(rutas.SERIES_FAMILIAS, encoding="utf-8-sig")
    escritas = [rutas.FAMILIAS, rutas.SERIES_FAMILIAS]
    if perfil is not None and not perfil.empty:
        perfil.to_csv(rutas.REZAGOS_FAMILIAS, index=False,
                      encoding="utf-8-sig")
        escritas.append(rutas.REZAGOS_FAMILIAS)
    return escritas


def informe(agrupadas, proporcion, notas, perfil=None):
    """El texto que hay que leer antes de mirar las figuras."""
    asignacion = agrupadas["asignacion"]
    estabilidad = agrupadas["estabilidad"]
    lineas = [
        "EL PANORAMA: FAMILIAS DE MOTIVOS SOBRE EL EJE DE TIEMPO",
        "",
        f"{len(asignacion)} temas con {MINIMO_NOTAS} notas o mas entraron al "
        f"agrupamiento por forma.",
        f"{len(proporcion)} semanas, de {proporcion.index.min():%Y-%m-%d} a "
        f"{proporcion.index.max():%Y-%m-%d}.",
        "",
        "LAS FAMILIAS",
    ]

    for familia in sorted(asignacion["familia"].unique()):
        miembros = asignacion[asignacion["familia"] == familia]
        jaccard = estabilidad.get(familia, float("nan"))
        veredicto = ("valida" if jaccard >= 0.75 else
                     "disuelta" if jaccard <= 0.50 else "dudosa")
        por_semana = float(notas[familia].mean()) if familia in notas else 0.0
        lineas.append(
            f"  familia {familia}: {len(miembros)} temas, "
            f"{int(miembros['notas'].sum()):,} notas "
            f"({por_semana:.1f}/semana). "
            f"estabilidad Jaccard {jaccard:.2f} -- {veredicto}")
        for fila in miembros.itertuples():
            lineas.append(f"      {fila.nombre} ({int(fila.notas)})")

    lineas += ["", "COMO SE LEE LA ESTABILIDAD"]
    validas = sum(1 for v in estabilidad.values() if v >= 0.75)
    disueltas = sum(1 for v in estabilidad.values() if v <= 0.50)
    lineas.append(
        f"  {validas} de {len(estabilidad)} familias reaparecen al remuestrear "
        f"el {int(FRACCION * 100)}% de las semanas; {disueltas} se disuelven.")
    lineas.append(
        "  Una familia disuelta NO es un hallazgo con poca fuerza: es una "
        "particion del")
    lineas.append(
        "  ruido que el algoritmo devolvio porque se le pidio devolver algo. "
        "No se")
    lineas.append("  interpreta su linea en el panorama.")

    if perfil is not None and not perfil.empty:
        lineas += ["", "EL PERFIL DE REZAGOS (FORMA, NO PRUEBA)"]
        for familia, parte in perfil.groupby("familia"):
            mejor = parte.loc[parte["correlacion"].abs().idxmax()]
            lineas.append(
                f"  familia {familia}: maximo |r| = "
                f"{mejor['correlacion']:+.3f} al rezago "
                f"{int(mejor['rezago_dias'])} dias (p crudo "
                f"{mejor['p_crudo']:.3f}, sin corregir)")
        lineas.append(
            "  Catorce rezagos por familia son 56 cifras: que la mayor ronde "
            "p=0,05 es lo")
        lineas.append(
            "  que pasa cuando no hay nada. Lo que se mira es la FORMA -- "
            "sube, hace maximo")
        lineas.append("  y baja -- no el valor mas alto.")

    lineas += [
        "",
        "Y ANTES DE INTERPRETAR NADA",
        "  El corpus es el 7,2% de las notas con motivo. El efecto minimo "
        "detectable ronda",
        "  un RR de 1,15 y los efectos de clima publicados estan entre 1,02 y "
        "1,10. Estas",
        "  figuras sirven para tener hipotesis y para verificar que la tuberia "
        "funciona.",
        "  No sirven para concluir. Ver potencia.py.",
    ]
    return "\n".join(lineas)
