"""
Que efecto se podria detectar. La pregunta que va ANTES de buscar ninguno.

    python -m patrones --potencia      no analiza nada, dice si vale la pena

POR QUE ESTE MODULO EXISTE Y POR QUE CORRE PRIMERO
    Un analisis sin potencia no devuelve 'no hay efecto'. Devuelve ruido, y el
    ruido a veces sale significativo. Las dos formas de equivocarse son
    simetricas y las dos ocurren:

        se busca un efecto del 5% con datos que solo detectan el 25%
          -> no sale nada, y se concluye que la lluvia no influye
        se prueban 40 temas flacos
          -> salen dos o tres por azar, y se concluye lo contrario

    Las dos conclusiones son falsas y ninguna se ve al mirar el resultado. Se
    ven aqui, antes, con una cuenta que no necesita los datos del desenlace.

LA CUENTA, Y DE DONDE SALE
    Armstrong, Gasparrini, Tobias y Sera (BMC Med Res Methodol 2020;20:15)
    derivan que en una regresion de serie temporal con conteos la precision
    depende de solo dos cosas:

        SE(beta) = sqrt(phi) / sqrt(suma de eventos) * 1 / SD(x | z)

        phi        sobredispersion. 1 si el conteo fuera Poisson puro;
                   en la practica 1,5 a 3 en series de urgencias.
        suma Y     el TOTAL de eventos del periodo. No importa en cuantos
                   dias esten repartidos -- 3.000 notas en 615 dias dan la
                   misma precision que en 200.
        SD(x | z)  la variacion UTILIZABLE de la exposicion: la que queda
                   despues de quitarle lo que ya explican el calendario y la
                   estacionalidad. Es el termino que casi nunca se mira, y el
                   que hay que medir en vez de suponer: ver mas abajo.

    Y el efecto minimo detectable, con alfa 0,05 y potencia 0,80:

        beta minimo = 2,8 * SE(beta)        RR = exp(beta minimo)

    Los autores verifican la aproximacion contra analisis completos de 51
    ciudades: queda en promedio dentro del 20% del error estandar real.

EL TERMINO QUE SE SUPONE Y HAY QUE MEDIR
    SD(x|z) no es la desviacion de la lluvia: es la que sobra despues de que el
    modelo ya se quedo con la estacionalidad.

        SD(x | z) = SD(x) * sqrt(1 - R2)

    con R2 el de regresar la variable climatica contra los terminos de
    calendario. Lo que el calendario ya explica no se le puede atribuir a la
    variable, asi que ese R2 se descuenta de la potencia.

    LA EXPECTATIVA ERA QUE ESTO HUNDIERA A LA LLUVIA, Y NO PASO
        El razonamiento previo era razonable: la precipitacion en los Andes
        colombianos es BIMODAL -- dos temporadas de lluvia al ano -- de modo
        que buena parte de su varianza deberia ser estacional e irse en el
        ajuste. Medido sobre la ventana, no:

            precip_consenso_mm    R2 contra calendario 0,03   utilizable  98%
            precip_7d             R2 0,07                     utilizable  97%
            precip_30d            R2 0,10                     utilizable  95%
            humedad_consenso      R2 0,18                     utilizable  91%
            vigilancia_gastro...  R2 0,80                     utilizable  44%

        La lluvia DIARIA de Manizales es casi toda variacion de corto plazo:
        la temporada dice cuantos dias llueve, no cuanto cae cada dia. Lo que
        si esta casi todo explicado por el calendario son las ventanas de
        vigilancia epidemiologica, que es de esperar -- son temporadas.

        Conviene leer ese 0,03 con cuidado y no como buena noticia entera: con
        1,7 ciclos anuales y dos pares de Fourier, la estacionalidad se ajusta
        poco, asi que parte de lo que aqui queda como 'utilizable' es
        estacionalidad que el modelo no alcanzo a capturar. El numero es
        correcto para lo que mide -- cuanta variacion le queda a la variable
        frente a ESTE modelo -- y no es una garantia de que esa variacion sea
        de corto plazo.

    El punto de fondo es el mismo en los dos casos: este modulo lo MIDE en vez
    de suponerlo, que es la diferencia entre 'no encontramos efecto de la
    lluvia' y 'no teniamos con que encontrarlo'.

LO QUE ESTA TABLA NO PUEDE ARREGLAR
    Ni una nota mas. La potencia sube con eventos totales, y los eventos
    totales suben ampliando la extraccion de NLP/ -- que es lo mismo que pide
    clustering/salidas/informe_fase8.txt por otro camino.

    Lo que NO sube con mas notas es la ventana: 615 dias son 1,7 ciclos
    anuales. Con menos de dos ciclos no hay forma de separar 'la lluvia causa
    consultas respiratorias' de 'en marzo y abril hay mas consultas
    respiratorias por el calendario escolar', porque cada mes se ha visto una
    o dos veces. Eso no es falta de potencia, es falta de contraste, y se
    arregla esperando o no se arregla.

    Es el argumento mas fuerte para que el analisis principal sea el diseno
    cruzado por estratos de modelos.py, que compara dias DENTRO del mismo mes
    y el mismo dia de la semana y por tanto no necesita estimar la
    estacionalidad en absoluto.
"""

import numpy as np
import pandas as pd

# alfa 0,05 a dos colas y potencia 0,80: 1,96 + 0,84.
Z = 2.8

# Eventos totales por debajo de los cuales un tema no se modela solo. Sale de
# la regla de eventos por variable: el modelo base -- dia de la semana,
# festivos, dos pares de Fourier, tendencia -- ya gasta unos 20 parametros
# antes de tocar el clima, y a 10 eventos por parametro eso son 200 eventos
# solo para llegar a cero.
MINIMO_EVENTOS = 200

# Y por debajo de este otro, ni agregado en supertemas vale la pena mirarlo
# como serie propia.
EVENTOS_COMODOS = 500

# Sobredispersion supuesta cuando no se puede estimar. Se usa 2,0 y no 1,0 a
# proposito: suponer Poisson puro es el supuesto OPTIMISTA, y una tabla de
# potencia optimista es peor que ninguna. Pasar de phi 1 a phi 2 cuesta lo
# mismo que perder la mitad de los datos.
PHI_SUPUESTO = 2.0

# Cuanto crece el corpus cuando NLP/ deje de trabajar sobre una muestra.
# No es una estimacion: son las 93.991 notas con motivo que hay en DIM_TRIAGE
# divididas por las 6.751 que llevan procesadas. Ver clustering/fechas.py.
FACTOR_CORPUS_COMPLETO = 93991 / 6751


def dispersion(conteos, esperados=None):
    """
    La sobredispersion, estimada como chi-cuadrado de Pearson sobre los grados
    de libertad.

    Si no se pasan valores esperados se usa la media, que es el nulo sin
    covariables, y entonces el numero SOBREESTIMA phi: se le atribuye a la
    dispersion todo lo que en realidad explican el dia de la semana y la
    estacion. Sirve para comparar contra dispersion_ajustada() y ver cuanto
    de la 'sobredispersion' era en realidad estructura, que es lo que imprime
    la corrida. Para la cuenta de la potencia se usa la otra.
    """
    conteos = np.asarray(conteos, dtype=float)
    conteos = conteos[~np.isnan(conteos)]
    if len(conteos) < 3:
        return float("nan")
    if esperados is None:
        esperados = np.full(len(conteos), conteos.mean())
    esperados = np.asarray(esperados, dtype=float)
    positivos = esperados > 0
    if positivos.sum() < 3:
        return float("nan")
    residuo = (conteos[positivos] - esperados[positivos]) ** 2 / esperados[positivos]
    return float(residuo.sum() / (positivos.sum() - 1))


def eventos_necesarios(rr, phi=PHI_SUPUESTO, fraccion_util=1.0):
    """
    Cuantos eventos harian falta para detectar un riesgo relativo dado.

    Es la misma formula despejada, y es la que convierte 'no alcanza' en un
    objetivo: si para ver un efecto del 5% hacen falta 15.000 notas de un tema
    y hoy hay 672, eso dice exactamente cuanto falta y por que ampliar la
    extraccion de NLP/ no es un detalle de ingenieria sino la condicion del
    analisis.
    """
    beta = abs(np.log(rr))
    if beta <= 0:
        return float("inf")
    return float((Z * np.sqrt(phi) / (beta * max(fraccion_util, 1e-9))) ** 2)


def dispersion_ajustada(conteos, diario, aviso=print):
    """
    La sobredispersion estimada CONTRA EL MODELO BASE, no contra la media.

    POR QUE NO SIRVE LA VARIANZA SOBRE LA MEDIA
        Estimar phi comparando el conteo contra su media global le atribuye a
        la sobredispersion toda la estructura que el modelo si va a explicar:
        el ciclo semanal, los festivos, la estacionalidad. Medido en esta
        serie, esa cuenta da phi = 4,8 mientras que contra el modelo base da
        bastante menos.

        La diferencia importa porque phi entra en la potencia bajo raiz: pasar
        de 4,8 a 2,4 mejora el efecto detectable en un 30%. Sobrestimar phi
        hace que el informe declare imposible un analisis que si se podia
        hacer, que es el mismo error que este modulo existe para evitar, solo
        que por el otro lado.
    """
    import statsmodels.api as sm

    dia = (diario["fecha"] - diario["fecha"].min()).dt.days.to_numpy(dtype=float)
    diseno = [np.ones(len(diario)), dia / 365.25]
    for k in (1, 2):
        diseno += [np.sin(2 * np.pi * k * dia / 365.25),
                   np.cos(2 * np.pi * k * dia / 365.25)]
    for columna in ("es_finde", "es_festivo"):
        if columna in diario.columns:
            diseno.append(diario[columna].fillna(0).to_numpy(dtype=float))
    matriz = np.column_stack(diseno)

    y = pd.Series(conteos).reindex(range(len(diario))).to_numpy(dtype=float)
    validos = ~np.isnan(y)
    if validos.sum() < 60:
        return float("nan")

    try:
        modelo = sm.GLM(y[validos], matriz[validos],
                        family=sm.families.Poisson()).fit()
    except Exception as error:  # el ajuste puede no converger con conteos raros
        aviso(f"  aviso: no se pudo ajustar el modelo base para phi ({error}). "
              f"Se usa el supuesto {PHI_SUPUESTO}.")
        return float("nan")

    return float(modelo.pearson_chi2 / modelo.df_resid)


def varianza_util(diario, variables, calendario_columnas=None):
    """
    Cuanta variacion le queda a cada variable externa despues del calendario.

    Devuelve una fila por variable con SD(x), el R2 contra los terminos de
    calendario y SD(x|z), que es la que entra en la cuenta de la potencia.

    LOS TERMINOS DE CALENDARIO SON LOS DEL MODELO, NI MAS NI MENOS
        Si aqui se ajustara por menos cosas de las que ajusta modelos.py, esta
        tabla diria que hay mas variacion utilizable de la que va a haber, y
        seria una promesa que el analisis no puede cumplir. Por eso son los
        mismos: dia de la semana, festivo, y dos pares de Fourier anuales para
        la estacionalidad.

        Dos pares y no siete grados de libertad por ano porque la ventana es de
        1,7 anos: siete por ano serian doce parametros gastados en estimar una
        estacionalidad que solo se ha observado una vez y media.
    """
    tabla = diario.copy()
    dia = (tabla["fecha"] - tabla["fecha"].min()).dt.days.to_numpy(dtype=float)

    diseno = [np.ones(len(tabla))]
    nombres = ["const"]

    # Fourier anual: dos pares. El primero es el ciclo de un ano y el segundo
    # el semestral, que en un regimen de lluvia bimodal es el que manda.
    for k in (1, 2):
        diseno += [np.sin(2 * np.pi * k * dia / 365.25),
                   np.cos(2 * np.pi * k * dia / 365.25)]
        nombres += [f"sin{k}", f"cos{k}"]

    if calendario_columnas is None:
        calendario_columnas = [c for c in ("es_finde", "es_festivo")
                               if c in tabla.columns]
    for columna in calendario_columnas:
        diseno.append(tabla[columna].fillna(0).to_numpy(dtype=float))
        nombres.append(columna)

    matriz = np.column_stack(diseno)

    filas = []
    for variable in variables:
        y = tabla[variable].to_numpy(dtype=float)
        validos = ~np.isnan(y)
        if validos.sum() < 30 or np.nanstd(y) == 0:
            continue
        x, yv = matriz[validos], y[validos]
        coef, *_ = np.linalg.lstsq(x, yv, rcond=None)
        residuo = yv - x @ coef
        sd_total = float(np.std(yv, ddof=1))
        sd_util = float(np.std(residuo, ddof=1))
        r2 = 1.0 - (sd_util ** 2) / (sd_total ** 2) if sd_total > 0 else 0.0
        filas.append({
            "variable": variable,
            "sd": sd_total,
            "r2_calendario": max(r2, 0.0),
            "sd_util": sd_util,
            "fraccion_util": sd_util / sd_total if sd_total else float("nan"),
            "dias": int(validos.sum()),
        })
    return pd.DataFrame(filas)


def detectable(eventos, phi=PHI_SUPUESTO, fraccion_util=1.0):
    """
    El riesgo relativo mas pequeno detectable por 1 SD de la variable.

    'fraccion_util' es SD(x|z)/SD(x): lo que sobrevive al calendario. Con 1,0
    la cuenta es por 1 SD de variacion utilizable, que es lo que reporta la
    tabla del articulo; con la fraccion medida, el numero pasa a estar en
    unidades de 1 SD de la variable TAL COMO SE MIDE, que es lo que un lector
    entiende por 'una desviacion de lluvia' y por tanto lo que hay que
    reportar.
    """
    eventos = np.asarray(eventos, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        error = np.sqrt(phi / eventos) / np.maximum(fraccion_util, 1e-9)
        return np.exp(Z * error)


def _procesadas_por_dia(diario, serie=None):
    """
    Las notas que llegaron al agrupamiento cada DIA, alineadas con el calendario.

    La sobredispersion se estima por dia y no por bloque a proposito: el bloque
    por defecto es la semana y 89 semanas no alcanzan para estimar bien un
    parametro de dispersion, mientras que 615 dias si. Es el unico sitio del
    paquete que vuelve al grano diario despues de agregar, y por eso lo hace
    explicito en vez de reusar el tablero.
    """
    from patrones import rutas

    if serie is None:
        serie = pd.read_csv(rutas.SERIE_DIARIA, encoding="utf-8-sig",
                            parse_dates=["fecha"])
    por_dia = (serie.drop_duplicates("fecha")[["fecha", "procesadas"]])
    return (diario[["fecha"]].merge(por_dia, on="fecha", how="left")
            ["procesadas"])


def tabla(tablero, diario, variables, phi=None, serie=None, aviso=print):
    """
    Una fila por (tema, variable): cuantos eventos hay y que efecto se veria.

    Es la tabla que decide que se analiza. Se lee de izquierda a derecha y se
    para en la primera columna que no pase.
    """
    por_tema = (tablero.groupby(["ancla", "nombre"], as_index=False)
                .agg(eventos=("notas", "sum")))
    por_tema = por_tema[por_tema["ancla"] != -1]

    util = varianza_util(diario, variables)
    if util.empty:
        raise SystemExit("Ninguna variable externa tiene variacion utilizable. "
                         "Revisar calendario.py.")

    if phi is None:
        # Se estima sobre el total procesado por dia, que es la unica serie con
        # suficientes conteos para que la estimacion valga algo. Usarla para
        # todos los temas supone que la dispersion es parecida entre ellos, lo
        # cual es una suposicion y se dice.
        #
        # Y se estima contra el modelo base y no contra la media: ver
        # dispersion_ajustada(). La diferencia entre las dos cuentas es grande
        # y decide si el informe declara posible un analisis o imposible.
        totales = _procesadas_por_dia(diario, serie)
        phi = dispersion_ajustada(totales, diario, aviso=aviso)
        cruda = dispersion(totales.dropna())
        if not np.isfinite(phi) or phi < 1:
            phi = PHI_SUPUESTO
            aviso(f"  sobredispersion: no estimable, se usa phi = {phi:.2f}")
        else:
            aviso(f"  sobredispersion contra el modelo base: phi = {phi:.2f} "
                  f"(contra la media sola habria dado {cruda:.2f})")

    cruce = por_tema.merge(util, how="cross")
    cruce["rr_detectable"] = detectable(cruce["eventos"], phi,
                                        cruce["fraccion_util"])
    cruce["phi"] = phi
    cruce["suficiente"] = cruce["eventos"] >= MINIMO_EVENTOS

    columnas = ["ancla", "nombre", "eventos", "variable", "sd",
                "r2_calendario", "fraccion_util", "phi", "rr_detectable",
                "suficiente"]
    return cruce[columnas].sort_values(["eventos", "rr_detectable"],
                                       ascending=[False, True])


# ==========================================================
# EL TEXTO
# ==========================================================

def informe(tabla_potencia, util=None):
    """Lo que hay que leer antes de correr ningun analisis."""
    temas = (tabla_potencia.drop_duplicates(["ancla", "nombre"])
             [["ancla", "nombre", "eventos"]]
             .sort_values("eventos", ascending=False))
    phi = float(tabla_potencia["phi"].iloc[0])

    lineas = [
        "¿QUE EFECTO SE PODRIA DETECTAR CON LO QUE HAY?",
        "",
        "Esto no busca ningun efecto: calcula, antes de buscarlo, cual es el",
        "mas pequeno que estos datos podrian distinguir del azar. Un analisis",
        "que no pasa por aqui no puede interpretar un resultado negativo.",
        "",
        f"Formula de Armstrong et al. 2020, con sobredispersion phi = {phi:.2f},",
        "alfa 0,05 y potencia 0,80. El numero es el RIESGO RELATIVO por una",
        "desviacion estandar de la variable tal como se mide.",
        "",
        "=" * 70,
        "POR TEMA",
        "",
        f"  {'tema':<32} {'eventos':>8}   veredicto",
    ]

    for _, fila in temas.iterrows():
        if fila["eventos"] >= EVENTOS_COMODOS:
            veredicto = "se puede modelar solo"
        elif fila["eventos"] >= MINIMO_EVENTOS:
            veredicto = "solo modelo minimo"
        else:
            veredicto = "NO: agregar en supertema"
        lineas.append(f"  {fila['nombre'][:32]:<32} {int(fila['eventos']):>8}   "
                      f"{veredicto}")

    suficientes = int((temas["eventos"] >= MINIMO_EVENTOS).sum())
    lineas += [
        "",
        f"  {suficientes} de {len(temas)} temas llegan a {MINIMO_EVENTOS} eventos.",
        "",
        "  El modelo base -- dia de la semana, festivos, dos pares de Fourier y",
        f"  tendencia -- ya gasta unos 20 parametros. A diez eventos por",
        f"  parametro eso son {MINIMO_EVENTOS} eventos para llegar a cero, antes de",
        "  meter una sola variable de clima. Un tema por debajo de esa linea no",
        "  da un resultado debil: da un coeficiente que no significa nada.",
        "",
        "=" * 70,
        "POR VARIABLE: CUANTA VARIACION LE QUEDA DESPUES DEL CALENDARIO",
        "",
        "  Es el termino que decide la potencia y el que casi nunca se mira.",
        "  'utilizable' es la fraccion de la desviacion de la variable que NO",
        "  explican ya la estacionalidad ni el calendario laboral. Lo que el",
        "  calendario explica no puede atribuirse a la variable.",
        "",
        f"  {'variable':<26} {'SD':>8} {'R2 cal':>8} {'utilizable':>11}",
    ]

    porvar = tabla_potencia.drop_duplicates("variable")
    for _, fila in porvar.sort_values("fraccion_util").iterrows():
        lineas.append(f"  {fila['variable'][:26]:<26} {fila['sd']:>8.2f} "
                      f"{fila['r2_calendario']:>8.2f} "
                      f"{fila['fraccion_util']:>10.0%}")

    lineas += [
        "",
        "=" * 70,
        "LOS PARES QUE SI SE PUEDEN PROBAR",
        "",
        "  Ordenados por el efecto mas pequeno que detectarian. Un RR de 1,05",
        "  es un efecto del 5%, que es el orden de los que se publican en esta",
        "  literatura; un RR de 1,30 es un efecto enorme que casi seguro no",
        "  existe, y una fila asi significa que ese par no se puede estudiar.",
        "",
        f"  {'tema':<26} {'variable':<24} {'RR minimo':>10}",
    ]

    posibles = tabla_potencia[tabla_potencia["suficiente"]].nsmallest(
        15, "rr_detectable")
    if posibles.empty:
        lineas += ["", "  NINGUNO. No hay un solo par (tema, variable) con",
                   "  eventos suficientes. Ampliar la extraccion de NLP/ es la",
                   "  unica via: ver clustering/salidas/informe_fase8.txt."]
    else:
        for _, fila in posibles.iterrows():
            lineas.append(f"  {fila['nombre'][:26]:<26} "
                          f"{fila['variable'][:24]:<24} "
                          f"{fila['rr_detectable']:>9.3f}")

    # EL VEREDICTO. Es lo unico de este informe que hay que leer si solo se va
    # a leer una cosa.
    mejor = float(tabla_potencia[tabla_potencia["suficiente"]]
                  ["rr_detectable"].min()) if suficientes else float("nan")
    lineas += ["", "=" * 70, "EL VEREDICTO", ""]

    if not np.isfinite(mejor):
        lineas += ["  Ningun tema llega al minimo de eventos. No hay analisis",
                   "  que hacer todavia."]
    else:
        lineas += [
            f"  El efecto mas pequeno que este corpus puede detectar, en el",
            f"  mejor par (tema, variable) que hay, es un RR de {mejor:.2f}.",
            "",
            f"  Es un efecto del {100 * (mejor - 1):.0f}%. Los efectos de clima sobre",
            "  urgencias que se publican en esta literatura estan entre el 2% y",
            "  el 10%. Un efecto del tamano que aqui se podria ver casi con",
            "  seguridad no existe.",
            "",
            "  LEIDO AL DERECHO: si este analisis no encuentra nada, eso NO es",
            "  evidencia de que el clima no influya. Es lo que tenia que pasar.",
            "  Y si encuentra algo, hay que desconfiar: con esta potencia, un",
            "  resultado significativo es mas probable que sea azar a que sea",
            "  un efecto real de tamano plausible.",
            "",
            "  CUANTO FALTA, EN NOTAS",
            "",
            f"  {'para detectar':<18} {'eventos del tema':>18} {'veces lo de hoy':>17}",
        ]
        mayor = float(temas["eventos"].max()) if len(temas) else 1.0
        for objetivo in (1.05, 1.10, 1.20):
            necesarios = eventos_necesarios(objetivo, phi, 1.0)
            lineas.append(f"  RR {objetivo:<15.2f} {necesarios:>18,.0f} "
                          f"{necesarios / max(mayor, 1):>16.0f}x")
        # Que pasaria con el corpus completo. El factor no se supone: es el
        # cociente entre las notas con motivo que hay en la base y las que
        # NLP/ lleva procesadas, que es lo que informa la fase anterior.
        proyectado = mayor * FACTOR_CORPUS_COMPLETO
        alcanzable = np.exp(Z * np.sqrt(phi / proyectado))
        lineas += [
            "",
            f"  El tema mas grande tiene hoy {int(mayor):,} notas. La extraccion",
            f"  completa de NLP/ multiplica el corpus por {FACTOR_CORPUS_COMPLETO:.0f} "
            f"(93.991 notas con",
            f"  motivo contra las 6.751 procesadas), o sea unas "
            f"{int(proyectado):,} notas en ese",
            f"  tema. Con eso el efecto detectable baja a un RR de "
            f"{alcanzable:.3f}, que ya",
            "  esta dentro del rango de lo que se publica.",
            "",
            "  Esa sola cifra es el argumento para ampliar la extraccion antes",
            "  que cualquier otra cosa de esta fase: no mejora el analisis, lo",
            "  hace posible.",
        ]

    lineas += [
        "",
        "=" * 70,
        "LO QUE NO ARREGLA NINGUNA CANTIDAD DE NOTAS",
        "",
        "  La ventana son 615 dias, o sea 1,7 ciclos anuales. Cada mes se ha",
        "  visto una o dos veces. Con eso no se puede separar un efecto de la",
        "  lluvia de cualquier otra cosa que pase todos los anos en la misma",
        "  epoca -- el calendario escolar, la temporada de virus respiratorios --",
        "  porque en los datos son la misma columna.",
        "",
        "  Eso no es falta de potencia y no se arregla procesando mas notas. Se",
        "  arregla esperando, o se declara como limitacion y se responde otra",
        "  pregunta: la de corto plazo, que es la que si tiene contraste.",
        "",
        "  Por eso el analisis principal de modelos.py es el diseno cruzado por",
        "  estratos y no una regresion de serie: compara cada dia contra los",
        "  otros dias del MISMO mes y el MISMO dia de la semana, y asi la",
        "  estacionalidad no hay que estimarla porque no entra.",
    ]
    return "\n".join(lineas) + "\n"
