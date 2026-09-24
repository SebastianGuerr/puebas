"""
La tabla larga que alimenta todas las figuras, y el indice de especializacion.

QUE HACE ESTE MODULO Y POR QUE ES EL UNICO CON CALCULO DENTRO
    Todas las figuras de figuras.py reciben la MISMA tabla: una fila por
    (dia, hora, categoria) con un conteo. Nada mas. Lo que cambia entre una
    figura y otra es por que eje se agrega, no de donde salen los datos.

    Esa decision es la que evita el fallo que se quiere evitar: si cada figura
    se construyera su propia tabla, dos figuras podrian discrepar entre si y
    nadie lo notaria. Aqui hay un solo sitio donde el conteo puede estar mal.

EL CONTEO CRUDO POR CATEGORIA NO SE DIBUJA NUNCA. SE DIBUJA EL LIFT.
    Es la trampa central de este analisis y hay que entenderla antes de mirar
    ninguna figura.

    El volumen total de triage cae un 36% de lunes a domingo y oscila 7,4 veces
    entre las 10 de la manana y las 4 de la madrugada. TODAS las categorias
    siguen ese patron, porque es el patron de cuanta gente hay en el hospital.
    Si se pinta el conteo crudo de ocho categorias, salen ocho figuras casi
    identicas: se esta mirando el volumen total ocho veces.

    Lo que informa es si una categoria esta SOBRE-representada en una casilla:

        lift(c, t) = [ n(c,t) / n(.,t) ]  /  [ n(c,.) / n(.,.) ]

    lift 1,0  esa categoria es ahi tan comun como siempre. No dice nada.
    lift 3,0  es el triple de comun de lo normal. Ahi si hay algo.

    Con eso 'trauma tiene pocos casos de madrugada' -- cierto y trivial, todo
    tiene pocos casos de madrugada -- se convierte en 'trauma es cuatro veces
    mas frecuente de lo normal el sabado a las 3'. Lo segundo es un hallazgo.

EL DENOMINADOR DEL LIFT ES EL CORPUS ANALIZADO, NO EL TRIAGE TOTAL, Y ESO
SUPONE ALGO QUE HAY QUE DEJAR DICHO
    n(.,t) se calcula sumando las categorias de esa misma casilla, no contra
    DIM_TRIAGE entero. Es lo correcto para una pregunta de COMPOSICION -- 'de
    las notas que leimos ese dia, que fraccion era respiratoria' -- y hace que
    la cobertura se cancele: si un dia se escribio el motivo en el 85% de los
    triages y otro dia en el 75%, el lift no se entera.

    Se cancela SI Y SOLO SI la cobertura no depende de la categoria. Si los
    triages respiratorios tuvieran sistematicamente mas motivo escrito que los
    de trauma, el lift de respiratorio saldria inflado y esta figura no lo
    delataria. No esta medido todavia. Queda dicho aqui porque es exactamente
    el tipo de error que no se ve en la grafica.

LAS CASILLAS CON POCOS CASOS MIENTEN, Y POR ESO SE TAPAN
    Un lift es un cociente. Con dos casos esperados y cuatro observados da 2,0
    y no significa nada: es ruido de Poisson. Cuanto mas fina la rejilla --
    7x24 son 168 casillas -- mas casillas con conteos minusculos, y siempre va
    a haber alguna con lift alto por azar.

    'esperado' es el conteo que tendria la casilla si la categoria se repartiera
    igual que el total. Es la frecuencia esperada de una prueba de chi-cuadrado,
    y por debajo de 5 esa prueba deja de valer. Debajo de ese umbral la columna
    'fiable' queda en falso y las figuras pintan la casilla en gris.

    Tapar no es esconder: una casilla gris dice 'aqui no hay datos suficientes',
    que es un resultado. Pintarla de color diria 'aqui pasa algo', que seria
    falso.
"""

import pandas as pd

from clustering.visualizaciones import rutas

MINIMO_ESPERADO = 5.0
TOTAL = "TOTAL"

DIAS = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def total():
    """
    La serie completa de triage por dia y hora, sin categorias.

    Sale de salidas/triage_horario.parquet: 55.844 casillas dia x hora entre
    2020-01-01 y 2026-09-21. No depende del NLP ni del agrupamiento, asi que es
    lo unico que hoy se puede dibujar de verdad -- y es tambien el denominador
    contra el que se lee cualquier categoria.
    """
    tabla = pd.read_parquet(rutas.HORARIO)
    tabla = tabla.rename(columns={"triages": "n"})
    tabla["dia"] = pd.to_datetime(tabla["dia"])
    tabla["categoria"] = TOTAL
    return tabla[["dia", "hora", "categoria", "n"]]


def por_categoria(columna="categoria", base=None):
    """
    Una fila por (dia, hora, categoria) a partir de las notas ya clasificadas.

    'columna' es el nombre de la columna de nota_triage que lleva la categoria.
    Hoy no existe ninguna: este es el camino que queda listo para cuando la
    clasificacion se decida, y por eso falla con un mensaje y no con una traza.

    No se inventa un valor por defecto. Una figura 'por categoria' que en
    realidad no tuviera categorias dibujaria una sola banda y pareceria
    correcta, que es el peor de los fallos posibles.
    """
    import duckdb

    ruta = base if base is not None else rutas.base_lectura()
    con = duckdb.connect(str(ruta), read_only=True)
    try:
        existe = con.execute(
            "select count(*) from information_schema.columns "
            "where table_name = 'nota_triage' and column_name = ?",
            [columna]).fetchone()[0]
        if not existe:
            raise RuntimeError(
                f"nota_triage no tiene la columna {columna!r}. La clasificacion "
                f"por categoria todavia no esta decidida; mientras tanto la "
                f"serie total se dibuja con 'python -m clustering.visualizaciones'.")
        tabla = con.execute(
            f"select cast(fecha_triage as date) as dia, "
            f"       cast(extract(hour from fecha_triage) as integer) as hora, "
            f"       {columna} as categoria, cast(count(*) as bigint) as n "
            f"from nota_triage "
            f"where fecha_triage is not null and {columna} is not null "
            f"group by 1, 2, 3").fetchdf()
    finally:
        con.close()

    tabla["dia"] = pd.to_datetime(tabla["dia"])
    return tabla[["dia", "hora", "categoria", "n"]]


def marco(tabla):
    """
    Anade las columnas de tiempo derivadas.

    Todas salen de 'dia' y ninguna se guarda en disco: son baratas de
    recalcular, y guardarlas seria una copia mas que se podria desincronizar.
    """
    salida = tabla.copy()
    dia = salida["dia"]
    salida["dow"] = dia.dt.dayofweek          # 0 = lunes
    salida["mes"] = dia.dt.month
    salida["anio"] = dia.dt.year
    salida["semana"] = dia.dt.isocalendar().week.astype(int)
    return salida


def lift(tabla, ejes, minimo_esperado=MINIMO_ESPERADO):
    """
    El indice de especializacion por casilla. Ver la cabecera del modulo.

    ejes   lista de columnas que definen la casilla, p.ej. ['dow', 'hora'].

    Devuelve una fila por (casilla, categoria) con n, esperado, lift y fiable.
    'esperado' es n(.,t) * n(c,.) / n(.,.): el conteo que tendria la casilla si
    la categoria no dependiera de ella. Es la frecuencia esperada de una prueba
    de chi-cuadrado, y el umbral de 5 es el suyo.
    """
    faltan = [c for c in ejes if c not in tabla.columns]
    if faltan:
        raise KeyError(f"la tabla no tiene las columnas {faltan}; "
                       f"pasala antes por datos.marco()")

    total_global = tabla["n"].sum()
    if total_global == 0:
        raise ValueError("la tabla esta vacia")

    observado = (tabla.groupby(ejes + ["categoria"], observed=True)["n"]
                 .sum().reset_index())
    por_casilla = tabla.groupby(ejes, observed=True)["n"].sum().rename("n_casilla")
    por_clase = tabla.groupby("categoria", observed=True)["n"].sum().rename("n_categoria")

    salida = (observado.merge(por_casilla, on=ejes, how="left")
                       .merge(por_clase, on="categoria", how="left"))
    salida["esperado"] = salida["n_casilla"] * salida["n_categoria"] / total_global
    salida["lift"] = salida["n"] / salida["esperado"]
    salida["fiable"] = salida["esperado"] >= minimo_esperado
    return salida


def rejilla(tabla, filas, columnas, categoria=None, valor="lift",
            minimo_esperado=MINIMO_ESPERADO):
    """
    El lift de UNA categoria como matriz filas x columnas, lista para imshow.

    Devuelve (matriz, tapada). 'tapada' es True donde el valor no es fiable, y
    es lo que las figuras pintan en gris.
    """
    medido = lift(tabla, [filas, columnas], minimo_esperado=minimo_esperado)
    if categoria is not None:
        medido = medido[medido["categoria"] == categoria]
    if medido.empty:
        raise ValueError(f"no hay datos para la categoria {categoria!r}")

    matriz = medido.pivot_table(index=filas, columns=columnas, values=valor)
    fiable = medido.pivot_table(index=filas, columns=columnas, values="fiable",
                                aggfunc="max")
    fiable = fiable.reindex(index=matriz.index, columns=matriz.columns)
    return matriz, ~fiable.fillna(False).astype(bool)


def serie_diaria(tabla, categoria=None):
    """
    Conteo por dia, con todos los dias del rango presentes.

    Los dias sin ningun registro quedan en NULO y no en cero: en un calendario
    un cero se pinta del color mas bajo de la escala y se lee como 'ese dia casi
    no vino nadie', que es una afirmacion distinta de 'ese dia no hay dato'.
    """
    if categoria is not None:
        tabla = tabla[tabla["categoria"] == categoria]
    serie = tabla.groupby("dia", observed=True)["n"].sum().sort_index()
    if serie.empty:
        raise ValueError(f"no hay datos para la categoria {categoria!r}")
    completo = pd.date_range(serie.index.min(), serie.index.max(), freq="D")
    return serie.reindex(completo)


def cuota_diaria(tabla, categoria):
    """
    La fraccion del dia que se llevo una categoria, como serie diaria.

    Es lo que se pinta en un calendario por categoria. El conteo crudo ahi
    reproduce el calendario del volumen total -- ver la cabecera del modulo.
    """
    por_dia = tabla.groupby(["dia", "categoria"], observed=True)["n"].sum()
    ancho = por_dia.unstack("categoria").sort_index()
    if categoria not in ancho.columns:
        raise ValueError(f"no hay datos para la categoria {categoria!r}")
    cuota = ancho[categoria] / ancho.sum(axis=1)
    completo = pd.date_range(ancho.index.min(), ancho.index.max(), freq="D")
    return cuota.reindex(completo)


def dominante(tabla, minimo_esperado=MINIMO_ESPERADO):
    """
    Que categoria estuvo mas sobre-representada cada dia.

    Es lo que colorea el calendario unico: en vez de una figura por categoria,
    una sola en la que cada dia lleva el color de la categoria que mas se salio
    de lo suyo. Los dias sin ninguna casilla fiable quedan en nulo.
    """
    medido = lift(tabla, ["dia"], minimo_esperado=minimo_esperado)
    medido = medido[medido["fiable"]]
    if medido.empty:
        raise ValueError("ningun dia alcanza el minimo esperado; el corpus "
                         "todavia es demasiado pequeno para esta figura")
    ganador = medido.loc[medido.groupby("dia")["lift"].idxmax()]
    return ganador.set_index("dia")[["categoria", "lift"]].sort_index()
