"""
La busqueda de asociaciones con rezago. EXPLORATORIA, y eso no es una salvedad.

    python -m patrones --asociar     escribe asociacion.csv y las figuras

QUE HACE Y QUE NO
    Recorre los pares (tema, variable) y mide si la variable de hoy tiene que
    ver con las consultas de dentro de N dias. Es la parte que GENERA
    hipotesis.

    Lo que sale de aqui NO es un resultado. Un resultado es lo que sobrevive a
    modelos.py, que ajusta por el calendario y por la estacionalidad. Esta
    separacion es deliberada y es lo unico que hace defendible mirar tantos
    pares: una correlacion aqui vale como 'mira esto', no como 'esto pasa'.

    La tentacion de saltarse ese segundo paso es enorme porque este modulo ya
    imprime valores p, y un valor p parece una conclusion. No lo es aqui: estan
    calculados sobre series filtradas y sin ajustar por confusores, asi que
    sirven para ORDENAR los pares, no para creerles.

LA CORRELACION CRUDA ENTRE DOS SERIES ES CASI SIEMPRE FALSA
    Es el error principal de este tipo de analisis y hay que entenderlo antes
    de leer una sola cifra de la salida.

    Dos series con tendencia correlacionan aunque no tengan nada que ver: las
    dos suben. Dos series con ciclo semanal correlacionan aunque no tengan nada
    que ver: las dos bajan el domingo. Y esta serie tiene las dos cosas -- la
    cobertura del motivo cae 9 puntos por ano y el ciclo semanal es su senal
    mas grande.

    El caso de referencia es lluvia contra malaria en Mpumalanga: la
    correlacion cruzada de las series crudas daba significativa en varios
    rezagos, y al repetirla sobre series pre-blanqueadas se vio que casi todo
    era artefacto.

    EL PRE-BLANQUEO es la correccion estandar y es lo que hace _blanquear():
    se ajusta un modelo autorregresivo a la serie de la EXPOSICION, se guardan
    sus residuos -- que ya son practicamente ruido -- y se aplica EL MISMO
    filtro a la serie del desenlace. Lo que quede correlacionado despues de eso
    no puede ser tendencia compartida ni ciclo compartido, porque el filtro se
    los llevo a los dos.

    El mismo filtro a las dos series y no uno propio para cada una: con filtros
    distintos, la correlacion resultante ya no estima la relacion entre las
    series originales.

QUINCE REZAGOS POR VARIABLE SON QUINCE PRUEBAS, Y NO HACEN FALTA
    Probar los rezagos 0 a 14 de cada variable multiplica por quince el numero
    de pruebas, y no aporta quince preguntas distintas: los rezagos vecinos son
    casi la misma prueba, porque la lluvia de ayer y la de anteayer estan
    correlacionadas entre si.

    Por eso lo que se PRUEBA son cuatro ventanas acumuladas:

        el mismo dia           efecto inmediato
        el promedio de 2 dias  efecto corto
        el promedio de 7 dias  la semana
        el promedio de 14 dias dos semanas

    Cuatro pruebas en vez de quince, con la misma cobertura de plazos. Es el
    mismo principio que un modelo de rezagos distribuidos: resumir la forma del
    efecto en pocos parametros en vez de estimar uno por dia.

    Los rezagos dia a dia SI se calculan, pero solo para dibujarlos en
    vistas.perfil_rezagos(). Mirar una curva no gasta una prueba; declararla
    significativa si.

LA CORRECCION POR COMPARACIONES MULTIPLES ES BENJAMINI-HOCHBERG, NO BONFERRONI
    Con 8 temas, 24 variables y 4 ventanas son 768 pruebas. A 0,05 sin corregir
    saldrian unos 38 falsos positivos, que es mas de lo que se espera encontrar
    de verdad.

    Bonferroni exigiria p < 0,000065. Con la potencia que tiene este corpus --
    ver potencia.py, el efecto mas pequeno detectable es del orden del 15% --
    no pasaria absolutamente nada, ni real ni falso, y el analisis no diria
    nada sobre nada.

    Benjamini-Hochberg controla la proporcion de falsos entre los que se
    declaran, no la probabilidad de un solo falso en todo el estudio. Es la
    correccion apropiada para una busqueda exploratoria con muchas pruebas y es
    la que se usa. Sigue siendo valida bajo dependencia positiva, que es lo que
    hay aqui: las variables de clima correlacionan entre si.

    La columna que hay que leer es 'sobrevive'. 'correlacion' sin ella no
    significa nada, y por eso las figuras tachan las celdas que no pasaron en
    vez de esconderlas.

SE MODELA 'parte' Y NO 'notas'
    Por lo mismo que documenta clustering/fechas.py: la fraccion de triages con
    motivo escrito cae con el tiempo, asi que un conteo arrastra una tendencia
    a la baja que no es del hospital. 'parte' -- las notas del tema sobre las
    procesadas de ese dia -- no la tiene.

    Es ademas lo que mide un sistema de vigilancia sindromica: no cuanta gente
    llego, sino que proporcion de la que llego venia por cada motivo.
"""

import numpy as np
import pandas as pd

from patrones import rutas

# Las ventanas que se prueban, en dias. 1 es el mismo dia.
VENTANAS = (1, 2, 7, 14)

# Los rezagos que se dibujan pero no se prueban.
REZAGOS = tuple(range(0, 15))

# Orden del autorregresivo del pre-blanqueo. 7 porque el ciclo de esta serie es
# semanal: un AR(7) absorbe el 'igual que hace una semana' que es la estructura
# dominante, y con el se va tambien la tendencia local.
ORDEN_AR = 7

# Proporcion de falsos descubrimientos que se acepta entre los declarados.
FDR = 0.05


def _blanquear(exposicion, desenlace, orden=ORDEN_AR):
    """
    Filtra las dos series con el AR ajustado a la EXPOSICION. Devuelve residuos.

    El filtro sale de la exposicion y no del desenlace porque la pregunta es si
    la exposicion anticipa al desenlace: se quiere quitar la estructura propia
    del que va delante y ver que le queda al otro por explicar.

    LIMITACION CONOCIDA: LOS DIAS QUE FALTAN SE PEGAN
        Las filas con nulo se quitan antes de filtrar, y el AR se aplica sobre
        lo que queda como si fueran dias consecutivos. Donde habia un hueco, el
        filtro cree que el dia 3 sigue al dia 1.

        Hoy no hace dano porque los nulos estan todos AL FINAL -- son los dias
        que clima_unificado.csv todavia no alcanza -- asi que quitarlos no parte
        la serie, solo la acorta. Deja de ser cierto en cuanto haya un hueco en
        medio, y entonces esto hay que cambiarlo por un filtro que respete las
        fechas. Queda escrito para que se note antes y no despues.
    """
    x = np.asarray(exposicion, dtype=float)
    y = np.asarray(desenlace, dtype=float)
    validos = ~(np.isnan(x) | np.isnan(y))
    if validos.sum() < orden * 6:
        return None, None

    x, y = x[validos], y[validos]
    if np.std(x) == 0 or np.std(y) == 0:
        return None, None

    # Los coeficientes del AR por minimos cuadrados sobre los propios rezagos.
    # Es un AutoReg a mano y a proposito: hace falta aplicar EXACTAMENTE el
    # mismo polinomio a la otra serie, y para eso hay que tener los
    # coeficientes en la mano.
    diseno = np.column_stack([np.ones(len(x) - orden)]
                             + [x[orden - k - 1:-k - 1] for k in range(orden)])
    objetivo = x[orden:]
    try:
        coef, *_ = np.linalg.lstsq(diseno, objetivo, rcond=None)
    except np.linalg.LinAlgError:
        return None, None

    def aplicar(serie):
        rezagos = np.column_stack([np.ones(len(serie) - orden)]
                                  + [serie[orden - k - 1:-k - 1]
                                     for k in range(orden)])
        return serie[orden:] - rezagos @ coef

    return aplicar(x), aplicar(y)


def _correlacion(x, y):
    """Pearson y su valor p a dos colas, sin traer scipy entero."""
    from scipy import stats

    if x is None or y is None or len(x) < 30:
        return float("nan"), float("nan"), 0
    if np.std(x) == 0 or np.std(y) == 0:
        return float("nan"), float("nan"), len(x)
    r, p = stats.pearsonr(x, y)
    return float(r), float(p), len(x)


def _serie_de(diario, variable, ventana):
    """La variable promediada sobre los ultimos 'ventana' dias."""
    serie = diario[variable].astype(float)
    if ventana <= 1:
        return serie.to_numpy()
    return serie.rolling(ventana, min_periods=max(2, ventana // 2)).mean().to_numpy()


# ==========================================================
# LO QUE SE PRUEBA
# ==========================================================

def probar(serie, diario, variables, temas, fdr=FDR, aviso=print):
    """
    Una fila por (tema, variable, ventana), con la correccion ya aplicada.

    'temas' son los que pasaron el filtro de potencia. Probar los demas no
    agrega informacion y si le quita potencia a estos: cada prueba de mas
    endurece el umbral de Benjamini-Hochberg para todas.
    """
    diario = diario.sort_values("fecha").reset_index(drop=True)
    resultados = []

    for ancla, nombre in temas:
        parcial = (serie[serie["ancla"] == ancla]
                   .sort_values("fecha")[["fecha", "parte"]])
        alineada = diario[["fecha"]].merge(parcial, on="fecha", how="left")
        y = alineada["parte"].to_numpy(dtype=float)

        for variable in variables:
            for ventana in VENTANAS:
                x = _serie_de(diario, variable, ventana)
                bx, by = _blanquear(x, y)
                r, p, n = _correlacion(bx, by)
                resultados.append({
                    "ancla": ancla, "nombre": nombre, "variable": variable,
                    "ventana_dias": ventana, "correlacion": r, "p": p, "n": n,
                })

    tabla = pd.DataFrame(resultados)
    validas = tabla["p"].notna()
    aviso(f"  {int(validas.sum())} pruebas calculadas "
          f"({len(tabla) - int(validas.sum())} sin datos suficientes)")

    tabla["p_corregido"] = np.nan
    tabla["sobrevive"] = False
    if validas.any():
        from statsmodels.stats.multitest import multipletests

        pasa, corregidos, *_ = multipletests(tabla.loc[validas, "p"],
                                             alpha=fdr, method="fdr_bh")
        tabla.loc[validas, "p_corregido"] = corregidos
        tabla.loc[validas, "sobrevive"] = pasa

    sobreviven = int(tabla["sobrevive"].sum())
    aviso(f"  {sobreviven} sobreviven a Benjamini-Hochberg al {fdr:.0%}"
          + ("" if sobreviven else "  <- lo esperable con esta potencia"))

    return tabla.sort_values("p_corregido", na_position="last").reset_index(
        drop=True)


# ==========================================================
# LO QUE SOLO SE MIRA
# ==========================================================

def explorar(serie, diario, variables, temas):
    """
    La correlacion a cada rezago dia a dia. PARA DIBUJAR, no para concluir.

    Estas cifras no llevan correccion por multiplicidad y no deben llevarla:
    no son pruebas. Son la forma de la relacion, que es lo que permite
    distinguir un efecto real -- que sube, tiene un maximo y baja -- de un pico
    aislado entre catorce rezagos planos, que es lo que produce el azar.
    """
    diario = diario.sort_values("fecha").reset_index(drop=True)
    resultados = []

    for ancla, nombre in temas:
        parcial = (serie[serie["ancla"] == ancla]
                   .sort_values("fecha")[["fecha", "parte"]])
        alineada = diario[["fecha"]].merge(parcial, on="fecha", how="left")
        y = alineada["parte"].to_numpy(dtype=float)

        for variable in variables:
            x_base = diario[variable].to_numpy(dtype=float)
            for rezago in REZAGOS:
                # La exposicion ocurrio 'rezago' dias antes que el desenlace.
                x = np.roll(x_base, rezago).astype(float)
                x[:rezago] = np.nan
                bx, by = _blanquear(x, y)
                r, _, _ = _correlacion(bx, by)
                resultados.append({"ancla": ancla, "nombre": nombre,
                                   "variable": variable, "rezago": rezago,
                                   "correlacion": r})
    return pd.DataFrame(resultados)


def guardar(tabla):
    """Escribe la tabla de asociaciones y devuelve su ruta."""
    tabla.to_csv(rutas.ASOCIACION, index=False, encoding="utf-8-sig")
    return rutas.ASOCIACION


# ==========================================================
# EL TEXTO
# ==========================================================

def informe(tabla, fdr=FDR):
    """Lo que dice la busqueda, con la advertencia pegada al resultado."""
    validas = int(tabla["p"].notna().sum())
    sobreviven = tabla[tabla["sobrevive"]]
    crudas = int((tabla["p"] < 0.05).sum())

    lineas = [
        "BUSQUEDA DE ASOCIACIONES (EXPLORATORIA)",
        "",
        f"  {validas} pruebas: temas con potencia suficiente x variables x "
        f"{len(VENTANAS)} ventanas.",
        f"  Series pre-blanqueadas con un AR({ORDEN_AR}) ajustado a la exposicion.",
        "",
        f"  a p < 0,05 sin corregir:           {crudas}",
        f"  esperadas por azar a ese umbral:   {0.05 * validas:.0f}",
        f"  sobreviven a Benjamini-Hochberg:   {len(sobreviven)}",
        "",
    ]

    if crudas and 0.05 * validas >= crudas * 0.8:
        lineas += [
            "  LEER ESTO: el numero de pruebas que pasan sin corregir es del",
            "  mismo orden que el que se esperaria por puro azar. Eso es lo que",
            "  se ve cuando NO hay senal, y es la lectura correcta aunque la",
            "  lista de abajo tenga filas.",
            "",
        ]

    if sobreviven.empty:
        lineas += [
            "=" * 70,
            "NO SOBREVIVE NINGUNA, Y ERA LO ESPERADO",
            "",
            "  No es un fallo del analisis ni un resultado negativo sobre el",
            "  clima. potencia.py ya lo habia anticipado: con este corpus el",
            "  efecto mas pequeno detectable es de un orden que no existe en",
            "  esta literatura, asi que lo unico que podia salir era nada, o",
            "  algo falso.",
            "",
            "  Lo que si vale de esta corrida:",
            "",
            "  - el tablero y los calendarios quedan construidos y verificados,",
            "    asi que el dia que el corpus crezca esto es una sola orden;",
            "  - las figuras de vistas.py se pueden mirar a ojo, que es un uso",
            "    legitimo y no depende de la potencia;",
            "  - los pares con correlacion mas alta quedan anotados como",
            "    hipotesis PARA PROBAR DESPUES, contra datos que no se usaron",
            "    para elegirlos.",
        ]
    else:
        lineas += ["=" * 70, "LAS QUE SOBREVIVEN", "",
                   f"  {'tema':<24} {'variable':<22} {'vent':>5} {'r':>7} "
                   f"{'p corr':>9}"]
        for _, fila in sobreviven.head(25).iterrows():
            lineas.append(
                f"  {fila['nombre'][:24]:<24} {fila['variable'][:22]:<22} "
                f"{int(fila['ventana_dias']):>4}d {fila['correlacion']:>7.3f} "
                f"{fila['p_corregido']:>9.4f}")
        lineas += [
            "",
            "  ANTES DE CREER NINGUNA DE ESTAS FILAS:",
            "",
            "  1. Estas correlaciones NO estan ajustadas por el calendario.",
            "     Pasan por modelos.py o no son un resultado.",
            "  2. Se eligieron mirando estos mismos datos. Confirmarlas exige",
            "     datos que no se hayan usado para encontrarlas.",
            "  3. Mirar el perfil de rezagos en salidas/figuras/. Un efecto",
            "     real tiene forma; un pico aislado es azar que sobrevivio.",
        ]

    lineas += [
        "",
        "=" * 70,
        "LOS PARES MAS FUERTES, SOBREVIVAN O NO (SON HIPOTESIS)",
        "",
        f"  {'tema':<24} {'variable':<22} {'vent':>5} {'r':>7} {'p':>8}",
    ]
    for _, fila in tabla.dropna(subset=["p"]).nsmallest(10, "p").iterrows():
        marca = "*" if fila["sobrevive"] else " "
        lineas.append(
            f" {marca}{fila['nombre'][:24]:<24} {fila['variable'][:22]:<22} "
            f"{int(fila['ventana_dias']):>4}d {fila['correlacion']:>7.3f} "
            f"{fila['p']:>8.4f}")

    lineas += [
        "",
        "  Anotar en patrones/datos/variables.csv la que se quiera probar en",
        "  serio ANTES de volver a correr esto. Escribir la hipotesis antes de",
        "  probarla es lo que separa una prediccion de una descripcion.",
    ]
    return "\n".join(lineas) + "\n"
