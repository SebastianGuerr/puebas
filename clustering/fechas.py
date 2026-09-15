"""
El puente a la fase 8: de OID a una serie diaria por tema, con sus denominadores.

    python -m clustering --serie        construye la serie y la deja en salidas/
    python -m clustering --puente       solo diagnostica si se puede, sin calcular

POR QUE LA FECHA NO ESTA EN triage_limpio.csv Y ESTA BIEN QUE NO ESTE
    NLP/ baja de DIM_TRIAGE solo OID y HCTMOTCON, porque para limpiar texto la
    fecha no hace falta y arrastrarla por cinco fases seria cargar una columna
    que nadie usa. El OID es la llave y la fecha se recupera cuando se necesita,
    que es aqui. Verificado: los 6.501 OID de asignacion.parquet devuelven
    fecha, cero perdidas.

    La consecuencia es que este modulo es el UNICO de clustering/ que toca la
    base de datos. Lo hace de lectura y sobre una tabla temporal, igual que
    NLP/nucleo/datos.py, y no escribe nada alla.

LO QUE MIDE ESTE MODULO Y POR QUE NO ES 'CONTAR NOTAS POR DIA'
    Contar notas por dia y por tema es lo obvio y da un resultado falso. Entre
    la gente que llega al hospital y una fila de esta tabla hay tres filtros, y
    los tres se mueven con el tiempo:

        1. llegan al triage           DIM_TRIAGE, todo lo que entro
        2. les escriben el motivo     HCTMOTCON no vacio
        3. NLP/ los proceso           triage_limpio.csv, hoy una muestra
        4. cayeron en un grupo        el 84% de lo procesado; el resto es ruido

    El filtro 2 es el peligroso. Medido sobre 2025-2026: la cobertura de
    HCTMOTCON va del 85,7% en el primer semestre de 2025 al 75,1% desde marzo
    de 2026, una caida de unos 9 puntos por ano.

    Eso significa que una serie de conteos por tema tiene una TENDENCIA A LA
    BAJA incorporada que no tiene nada que ver con el hospital: es que cada vez
    escriben el motivo en menos triages. Cruzada contra cualquier variable que
    tambien tenga tendencia -- y el clima de 2025 a 2026 la tiene -- produce
    correlaciones que no existen.

    Por eso esta tabla lleva SIEMPRE los denominadores al lado y por eso la
    columna que hay que modelar es la proporcion, no el conteo. Ver
    cobertura().

EL FILTRO 3 ES HOY EL MAS GRANDE Y ES TEMPORAL
    NLP/procesar.py trabaja sobre una muestra: LIMITE_REGISTROS = 5000 con
    muestreo disperso por hash. De las 93.991 notas con motivo que hay en la
    ventana, hoy estan procesadas 6.751 (7,2%), o sea unas 10,6 notas por dia
    repartidas entre 41 temas.

    A esa densidad no hay serie diaria que valga: el tema mas grande tendria
    menos de una nota al dia y el resto, cero casi todos los dias. Cruzar eso
    contra la lluvia no da un resultado debil, da ruido.

    Con la extraccion completa serian unas 153 notas por dia (mediana 150, minimo
    37, maximo 296), y ahi el tema mas grande ronda las 12 diarias, que ya es
    una serie. Es la condicion que informe() comprueba antes de dejar seguir.

LO QUE YA DOMINA LA SERIE ANTES DE QUE LLEGUE EL CLIMA
    Medido sobre el volumen TOTAL de triage de la ventana, que no depende del
    agrupamiento ni de la muestra y por tanto ya se puede medir bien:

        lunes 219,8 triages/dia ... domingo 145,1     -34% de punta a punta
        fin de semana              -24,8%
        festivo                    -16,6%
        temporada de navidad       -21,6%
        autocorrelacion a 7 dias   +0,703

    El ciclo semanal es, con diferencia, la senal mas grande de la serie. Dos
    consecuencias para la fase 8, y las dos son de diseno del modelo y no de
    datos:

    1. El dia de la semana y los festivos VAN EN EL MODELO, siempre. Si no, una
       variable climatica que por azar se reparta distinto entre semana y fin de
       semana se lleva el credito de un efecto que es del calendario laboral.
       calendario_Colombia.csv ya trae es_finde, es_festivo, es_puente y el
       resto listos para eso.

    2. Con autocorrelacion a 7 dias de 0,70 los errores estandar de una
       regresion ordinaria estan mal y todo sale significativo. Hace falta algo
       que lo absorba -- terminos de dia de la semana mas errores robustos a
       autocorrelacion, o directamente un modelo de series temporales.

LAS VARIABLES DE CLIMA QUE SIRVEN Y LAS QUE NO
    Manizales no tiene estaciones termicas y eso se ve en los datos de la
    ventana:

        temp_media_consenso    media 16,5 C   sd 0,60    <- casi constante
        temp_max_consenso      media 21,0 C   sd 1,29
        humedad_consenso       media 87,2 %   sd 4,18
        precip_consenso_mm     media 8,1 mm   sd 10,37   <- aqui si hay rango
        precip_7d              media 57,1 mm  sd 48,63

    La temperatura casi no se mueve, asi que no va a explicar nada: seis grados
    de rango entre el dia mas frio y el mas caluroso de veinte meses.

    Y hay una trampa concreta: la columna 'llovio' de clima_unificado.csv es
    cierta el 98,8% de los dias. Como variable binaria no distingue nada --
    en Manizales llueve casi siempre -- y meterla en un modelo es meter una
    constante. Lo que si tiene rango es la CANTIDAD (precip_consenso_mm), el
    acumulado (precip_7d) y 'lluvia_fuerte', que es cierta el 11,4% de los dias.

    El clima va con 17 dias de atraso respecto a la base (ultimo dia disponible
    2026-08-28). Hay que volver a correr calendarios/clima/ antes del cruce.

EL DIA, Y POR QUE SE CORTA A LAS 00:00 LOCALES
    HCTFECTRI es hora local de Manizales (UTC-5) y sin zona horaria declarada.
    El clima diario de calendarios/ viene de fuentes que agregan por dia; el
    corte no tiene por que coincidir exactamente con el local en todas ellas.

    No se intenta corregir y se deja dicho: un desfase de horas mueve una
    fraccion de las consultas nocturnas de un dia al siguiente, lo cual afecta
    a un analisis de eventos de horas, no a uno de dias. Si en algun momento se
    quiere mirar el efecto de una tormenta concreta hora a hora, esto hay que
    revisarlo antes y no despues.
"""

import numpy as np
import pandas as pd

from clustering import rutas

TABLA = "DIM_TRIAGE"
COLUMNA_FECHA = "HCTFECTRI"
COLUMNA_MOTIVO = "HCTMOTCON"
LLAVE = "OID"

# Notas diarias por debajo de las cuales una serie por tema no puede sostener
# ningun cruce. No es un umbral estadistico fino: es el orden de magnitud por
# debajo del cual el tema mas grande no llega a una nota diaria.
MINIMO_NOTAS_DIA = 50

# Dias minimos de historia. Con menos de un ano no se puede separar un efecto
# del clima de la estacionalidad anual, porque no hay dos ciclos que comparar.
MINIMO_DIAS = 365


def _engine():
    """
    El engine de NLP/, que es el unico sitio del proyecto que sabe conectarse.

    Se importa aqui dentro y no arriba para que clustering/ siga corriendo
    entero sin base de datos: todo lo demas del paquete trabaja sobre
    embedding/salidas/ y no tiene por que fallar porque el servidor no
    responda.
    """
    try:
        from NLP.nucleo.conexion_bd import obtener_engine
    except ImportError as error:
        raise SystemExit(
            f"No se pudo importar la conexion de NLP/: {error}\n"
            f"Este modulo es el unico de clustering/ que necesita la base.")
    return obtener_engine()


def _en_lotes(conexion, oids, lote=1000):
    """
    Mete los OID en una tabla temporal para poder cruzarlos con un JOIN.

    Un IN (...) con decenas de miles de llaves es medio megabyte de SQL que el
    servidor analiza entero en cada corrida; es el mismo motivo por el que
    NLP/nucleo/datos.py hace esto mismo. SQL Server admite 1.000 tuplas por
    VALUES, de ahi el tamano del lote.
    """
    conexion.exec_driver_sql("DROP TABLE IF EXISTS #oids")
    conexion.exec_driver_sql(f"CREATE TABLE #oids ({LLAVE} bigint PRIMARY KEY)")
    claves = sorted({int(o) for o in oids})
    for inicio in range(0, len(claves), lote):
        valores = ",".join(f"({k})" for k in claves[inicio:inicio + lote])
        conexion.exec_driver_sql(
            f"INSERT INTO #oids ({LLAVE}) VALUES {valores}")
    return len(claves)


def fechas_de(oids, engine=None):
    """
    Devuelve un DataFrame OID -> fecha (dia) y momento (timestamp completo).

    Se traen las dos: la fecha para agrupar y el timestamp para poder revisar
    despues efectos de hora del dia sin volver a la base.

    Si algun OID no aparece, sube un aviso en vez de perderlo en silencio: que
    un OID del agrupamiento no exista en DIM_TRIAGE significaria que el CSV de
    NLP/ y la tabla se desincronizaron, y eso hay que verlo.
    """
    engine = engine or _engine()
    with engine.begin() as conexion:
        pedidos = _en_lotes(conexion, oids)
        tabla = pd.read_sql(
            f"SELECT t.{LLAVE}, t.{COLUMNA_FECHA} AS momento "
            f"FROM {TABLA} AS t JOIN #oids AS o ON o.{LLAVE} = t.{LLAVE}",
            conexion)

    if len(tabla) < pedidos:
        print(f"  aviso: {pedidos - len(tabla)} OID del agrupamiento no estan "
              f"en {TABLA}. El CSV de NLP/ y la tabla no describen lo mismo.")

    tabla["momento"] = pd.to_datetime(tabla["momento"])
    tabla["fecha"] = tabla["momento"].dt.normalize()
    return tabla


def cobertura(desde=None, hasta=None, engine=None):
    """
    Una fila por fecha con los denominadores. ES LA TABLA QUE EVITA EL ERROR.

    triages      cuantas personas pasaron por triage ese dia. El universo.
    con_motivo   a cuantas les escribieron el motivo de consulta.
    cobertura    la razon entre las dos.

    POR QUE ESTO NO ES UN EXTRA SINO EL NUCLEO
        Sin esta tabla, una serie de notas por tema y dia mezcla dos cosas que
        cambian a la vez: cuanta gente consulto por ese motivo, y que fraccion
        del triage quedo documentada. Lo segundo cayo unos 9 puntos porcentuales
        por ano en la ventana disponible, asi que TODA serie por conteo hereda
        una tendencia descendente que no es del hospital.

        Con ella hay dos salidas honestas, y las dos necesitan estas columnas:
        modelar la proporcion (notas del tema / notas con motivo ese dia), o
        modelar el conteo poniendo log(con_motivo) como desplazamiento en un
        modelo de Poisson. Cual de las dos es cosa de la fase 8; que haga falta
        una de ellas se decide aqui.
    """
    engine = engine or _engine()
    filtros = [f"{COLUMNA_FECHA} IS NOT NULL"]
    if desde is not None:
        filtros.append(f"{COLUMNA_FECHA} >= '{pd.Timestamp(desde).date()}'")
    if hasta is not None:
        filtros.append(
            f"{COLUMNA_FECHA} < '{(pd.Timestamp(hasta) + pd.Timedelta(days=1)).date()}'")

    consulta = f"""
        SELECT CAST({COLUMNA_FECHA} AS date) AS fecha,
               COUNT(*) AS triages,
               SUM(CASE WHEN {COLUMNA_MOTIVO} IS NOT NULL
                         AND LTRIM(RTRIM({COLUMNA_MOTIVO})) <> ''
                        THEN 1 ELSE 0 END) AS con_motivo
        FROM {TABLA}
        WHERE {' AND '.join(filtros)}
        GROUP BY CAST({COLUMNA_FECHA} AS date)
        ORDER BY 1"""

    tabla = pd.read_sql(consulta, engine)
    tabla["fecha"] = pd.to_datetime(tabla["fecha"])
    tabla["cobertura"] = tabla["con_motivo"] / tabla["triages"].replace(0, np.nan)
    return tabla


def ventana(engine=None):
    """
    Desde cuando hay motivo de consulta en la base. La historia utilizable.

    NO ES 2020 AUNQUE LA TABLA EMPIECE EN 2020
        DIM_TRIAGE tiene 432.098 filas desde 2020-01-01, y HCTMOTCON esta vacio
        en TODAS las anteriores a 2025-01-08. Medido por ano: 0% en 2020, 2021,
        2022, 2023 y 2024; 82,8% en 2025 y 76,1% en 2026.

        Es el limite duro del proyecto y conviene tenerlo escrito donde se
        consulta: los calendarios de calendarios/ cubren 2020-2026, asi que
        cuatro quintas partes de ese trabajo no se pueden cruzar contra nada.
        Lo que hay son unos 615 dias, poco mas de un ciclo anual y medio.
    """
    engine = engine or _engine()
    fila = pd.read_sql(
        f"SELECT MIN({COLUMNA_FECHA}) AS desde, MAX({COLUMNA_FECHA}) AS hasta, "
        f"COUNT(*) AS notas FROM {TABLA} "
        f"WHERE {COLUMNA_MOTIVO} IS NOT NULL "
        f"AND LTRIM(RTRIM({COLUMNA_MOTIVO})) <> ''", engine).iloc[0]
    return {
        "desde": pd.Timestamp(fila["desde"]).normalize(),
        "hasta": pd.Timestamp(fila["hasta"]).normalize(),
        "notas_disponibles": int(fila["notas"]),
        "dias": int((pd.Timestamp(fila["hasta"]).normalize()
                     - pd.Timestamp(fila["desde"]).normalize()).days) + 1,
    }


# ==========================================================
# LA SERIE
# ==========================================================

def serie(asignacion, fechas, cobertura_diaria, tabla_anclas=None):
    """
    Una fila por (fecha, ancla). La tabla que se cruza contra clima y calendario.

    REJILLA COMPLETA, CON LOS CEROS DENTRO
        Se emiten todas las combinaciones de fecha y ancla, incluidas las que
        tienen cero notas. Un groupby normal las omitiria, y una serie a la que
        le faltan los dias de cero no es una serie: al cruzarla contra la lluvia
        se estarian comparando solo los dias en que ese motivo aparecio, que es
        justamente el sesgo que se queria evitar.

        El cero es un dato. Lo que no se puede es confundir dos ceros distintos:
        'ese dia nadie consulto por esto' y 'ese dia el ancla no recibio ningun
        grupo'. Lo segundo lo detecta anclas.revisar() y por eso hay que leer su
        aviso antes de usar esta tabla.

    LAS COLUMNAS
        notas            el conteo crudo. NO se modela directo.
        notas_con_motivo cuantas notas con motivo hubo ese dia en TODA la base.
        triages          cuanta gente paso por triage ese dia.
        procesadas       cuantas notas de ese dia llegaron hasta el agrupamiento.
        parte            notas / procesadas. La fraccion del dia que fue de este
                         tema, que es lo unico comparable entre dias mientras la
                         cobertura se mueva.

        'parte' es la columna por defecto para el cruce y 'notas' la que se
        conserva para poder usar un Poisson con desplazamiento si se prefiere.
    """
    if "ancla" not in asignacion.columns:
        raise SystemExit(
            "La asignacion no trae columna 'ancla', asi que viene de una "
            "corrida anterior a las anclas.\n"
            "Los numeros de 'tema' de ese archivo NO son comparables con los "
            "de ninguna otra corrida -- se renumeran por tamano -- y construir "
            "una serie sobre ellos daria saltos que parecen senal.\n"
            "  python -m clustering            (rehace salidas/ con las anclas)\n"
            "Ver clustering/anclas.py.")

    asignacion = asignacion.merge(fechas[["OID", "fecha"]], on="OID", how="inner")

    procesadas = (asignacion.groupby("fecha").size()
                  .rename("procesadas").reset_index())
    conteo = (asignacion.groupby(["fecha", "ancla"]).size()
              .rename("notas").reset_index())

    # EL -1 ENTRA EN LA REJILLA COMO UNA FILA MAS, no como un caso aparte.
    #
    # Es tentador tratarlo al final: son las notas que HDBSCAN dejo en ruido y
    # no tienen tema. Pero entonces solo saldrian los dias en que hubo ruido, y
    # esa serie tendria huecos donde deberia tener ceros -- exactamente el
    # defecto que esta rejilla existe para evitar, colado por la puerta de atras.
    #
    # Y hay que llevarlo: son gente que llego al hospital. Sin esta fila las
    # partes sumarian 1 y se perderia cuanto del dia quedo sin explicar, que es
    # una de las cifras que hay que reportar junto a cualquier resultado.
    dias = cobertura_diaria["fecha"].sort_values().unique()
    if tabla_anclas is not None:
        identificadores = np.concatenate([[-1], tabla_anclas["id"].to_numpy()])
        nombres = dict(zip(tabla_anclas["id"], tabla_anclas["nombre"]))
    else:
        identificadores = np.sort(asignacion["ancla"].unique())
        nombres = {}
    nombres[-1] = "(sin tema)"

    rejilla = pd.MultiIndex.from_product(
        [dias, identificadores], names=["fecha", "ancla"]).to_frame(index=False)

    tabla = (rejilla
             .merge(conteo, on=["fecha", "ancla"], how="left")
             .merge(procesadas, on="fecha", how="left")
             .merge(cobertura_diaria[["fecha", "triages", "con_motivo"]],
                    on="fecha", how="left"))
    tabla["notas"] = tabla["notas"].fillna(0).astype(int)
    tabla["procesadas"] = tabla["procesadas"].fillna(0).astype(int)
    tabla = tabla.rename(columns={"con_motivo": "notas_con_motivo"})
    tabla["nombre"] = tabla["ancla"].map(nombres).fillna("")
    tabla["parte"] = tabla["notas"] / tabla["procesadas"].replace(0, np.nan)

    columnas = ["fecha", "ancla", "nombre", "notas", "procesadas",
                "notas_con_motivo", "triages", "parte"]
    return tabla[columnas].sort_values(["fecha", "ancla"]).reset_index(drop=True)


def guardar(tabla_serie, tabla_cobertura):
    """Escribe las dos tablas y devuelve sus rutas."""
    tabla_serie.to_csv(rutas.SERIE, index=False, encoding="utf-8-sig")
    tabla_cobertura.to_csv(rutas.COBERTURA, index=False, encoding="utf-8-sig")
    return rutas.SERIE, rutas.COBERTURA


# ==========================================================
# ¿SE PUEDE ARRANCAR LA FASE 8?
# ==========================================================
#
# Este bloque no calcula nada del analisis: comprueba las condiciones sin las
# cuales el analisis no significaria nada, y las dice antes de gastar el tiempo
# en hacerlo.
#
# Existe porque los tres problemas que encontro la revision no se ven al mirar
# el resultado. Una serie construida sobre 10 notas diarias se dibuja igual de
# bien que una construida sobre 150, y una construida sobre temas que se
# renumeran tambien: salen graficas, salen correlaciones, y nada avisa.


def diagnostico(asignacion=None, engine=None):
    """
    Las condiciones de la fase 8, comprobadas contra la base y contra salidas/.

    Devuelve un diccionario con una entrada por condicion, cada una con si pasa
    y con el numero que lo sostiene.
    """
    from clustering import anclas

    engine = engine or _engine()
    hueco = ventana(engine=engine)
    cob = cobertura(desde=hueco["desde"], hasta=hueco["hasta"], engine=engine)

    # La deriva de la cobertura: lo que convierte una serie de conteos en una
    # tendencia falsa. Se mide como pendiente en puntos porcentuales por ano.
    dias = (cob["fecha"] - cob["fecha"].min()).dt.days.to_numpy()
    valores = cob["cobertura"].to_numpy()
    validos = ~np.isnan(valores)
    pendiente = (np.polyfit(dias[validos], valores[validos], 1)[0] * 365 * 100
                 if validos.sum() > 2 else float("nan"))

    salida = {
        "ventana": hueco,
        "cobertura_global": float(cob["con_motivo"].sum() / cob["triages"].sum()),
        "deriva_cobertura": float(pendiente),
        "notas_disponibles": hueco["notas_disponibles"],
        "notas_dia_disponibles": float(cob["con_motivo"].mean()),
        "anclas": anclas.existen(),
    }

    if asignacion is not None and len(asignacion):
        fec = fechas_de(asignacion["OID"].unique(), engine=engine)
        salida["notas_procesadas"] = int(len(asignacion))
        salida["parte_procesada"] = float(len(asignacion)
                                          / max(hueco["notas_disponibles"], 1))
        salida["notas_dia_procesadas"] = float(
            len(fec) / max(fec["fecha"].nunique(), 1))
        if "ancla" in asignacion.columns:
            con = int((asignacion["ancla"] != -1).sum())
            salida["notas_con_tema"] = con
            salida["notas_dia_con_tema"] = salida["notas_dia_procesadas"] * (
                con / max(len(asignacion), 1))
    return salida


def _condiciones(diag):
    """Las cinco condiciones, cada una con su veredicto y su explicacion."""
    hueco = diag["ventana"]
    dia = diag.get("notas_dia_con_tema", diag.get("notas_dia_procesadas", 0.0))

    return [
        ("historia suficiente",
         hueco["dias"] >= MINIMO_DIAS,
         f"{hueco['dias']} dias con motivo de consulta "
         f"({hueco['desde'].date()} a {hueco['hasta'].date()})",
         "HCTMOTCON esta vacio en TODO lo anterior a 2025: 0% en 2020-2024. Los "
         "calendarios cubren 2020-2026, asi que cuatro quintas partes de ese "
         "trabajo no tienen con que cruzarse. Con menos de un ano no se puede "
         "separar un efecto del clima de la estacionalidad."),

        ("densidad diaria",
         dia >= MINIMO_NOTAS_DIA,
         f"{dia:.1f} notas con tema por dia",
         f"Por debajo de {MINIMO_NOTAS_DIA} el tema mas grande no llega a una "
         f"nota diaria y el resto son ceros. La extraccion completa daria unas "
         f"153 notas/dia; hoy NLP/procesar.py trae una muestra "
         f"(LIMITE_REGISTROS). Es la condicion que mas falta y la mas facil de "
         f"arreglar: es dejar correr la extraccion."),

        ("temas con identidad estable",
         bool(diag["anclas"]),
         "anclas definidas" if diag["anclas"] else "NO hay anclas",
         "Sin anclas los numeros de tema se renumeran en cada corrida y una "
         "serie sobre ellos no mide lo que dice. Medido: sin anclaje solo el "
         "64-74% de las notas cae en el mismo tema al repetir; con anclaje, el "
         "95-97%. Se crean con 'python -m clustering --anclar'."),

        ("cobertura estable",
         abs(diag["deriva_cobertura"]) < 3.0,
         f"cobertura {diag['cobertura_global']:.1%}, deriva "
         f"{diag['deriva_cobertura']:+.1f} puntos/ano",
         "La fraccion de triages con motivo escrito cae con el tiempo. Una "
         "serie de CONTEOS hereda esa caida como tendencia propia y se "
         "correlaciona con cualquier otra cosa que tenga tendencia. No se "
         "arregla con datos: se arregla modelando la proporcion, o el conteo "
         "con log(notas_con_motivo) como desplazamiento. La columna 'parte' de "
         "serie_diaria.csv ya viene calculada para eso."),

        ("muestra representativa del calendario",
         diag.get("parte_procesada", 0.0) >= 0.5,
         f"{diag.get('parte_procesada', 0.0):.1%} de las notas disponibles "
         f"procesadas",
         "El muestreo de NLP/ es disperso por hash del OID, asi que no sesga "
         "por fecha y una muestra pequena sigue siendo insesgada. Lo que no da "
         "es PRECISION: con el 7% de las notas, el intervalo de confianza de "
         "cada dia se traga cualquier efecto del clima."),
    ]


def informe(diag):
    """El texto de si se puede arrancar la fase 8 y que falta."""
    condiciones = _condiciones(diag)
    pasan = sum(1 for _, bien, _, _ in condiciones if bien)

    lineas = [
        "¿ESTA LISTO EL PROYECTO PARA CRUZAR CONTRA EL CALENDARIO?",
        "",
        f"  {pasan} de {len(condiciones)} condiciones cumplidas.",
        "",
        "Esto no juzga el agrupamiento -- eso es --validar -- sino si la tabla",
        "que sale de el puede sostener un analisis temporal. Las tres primeras",
        "condiciones son de bloqueo; las dos ultimas cambian COMO hay que",
        "modelar, no si se puede.",
        "",
        "=" * 70,
    ]

    for nombre, bien, cifra, porque in condiciones:
        lineas += [
            f"{'[ OK ]' if bien else '[FALTA]'}  {nombre.upper()}",
            f"         {cifra}",
        ]
        if not bien:
            lineas += ["", *[f"         {linea}"
                             for linea in _envolver(porque, 62)]]
        lineas.append("")

    lineas += [
        "=" * 70,
        "EL ORDEN EN QUE CONVIENE RESOLVERLO",
        "",
        "  El corpus es hoy el 7% de lo disponible, y ESO MANDA SOBRE TODO LO",
        "  DEMAS. Anclar primero seria fijar las unidades de analisis mirando",
        "  una catorceava parte de los datos: con el corpus completo van a",
        "  aparecer motivos que la muestra no tiene, habria que reanclar, y",
        "  reanclar empieza una serie nueva. Se haria el trabajo dos veces y la",
        "  primera serie se tiraria.",
        "",
        "  1. Ampliar la extraccion. NLP/procesar.py con LIMITE_REGISTROS en",
        "     None procesa las 93.991 notas con motivo. Convierte 10 notas",
        "     diarias en 153. Es la unica condicion que hoy bloquea de verdad y",
        "     todo lo demas depende de ella.",
        "",
        "  2. Volver a validar ('--validar'). Con catorce veces mas textos los",
        "     parametros del agrupamiento hay que revisarlos: agrupar.py ya",
        "     avisa que un grupo de 10 textos sobre 5.000 no es lo mismo que",
        "     sobre 94.000. Cuenta con unas tres horas a ese tamano.",
        "",
        "  3. Anclar entonces ('--anclar'), sobre un agrupamiento ya revisado.",
        "     Ahi es cuando las anclas valen la pena, porque es cuando dejan de",
        "     tener que rehacerse.",
        "",
        "  4. Serie ('--serie') y recien ahi el cruce contra el calendario.",
        "",
        "  Anclar AHORA sigue siendo util para una cosa: ver como quedan los",
        "  temas y corregirles el nombre a mano. Lo que no hay que hacer es",
        "  construir sobre esas anclas ninguna serie que se piense conservar.",
        "",
        "LO QUE YA NO ES UN PROBLEMA",
        "  - La fecha. Se recupera por OID contra DIM_TRIAGE sin perdidas.",
        "  - El calendario. calendario_Colombia.csv cubre la ventana completa y",
        "    clima_unificado.csv le falta solo el final (va unos dias atrasado);",
        "    en la ventana util sus columnas de consenso estan al 99,5%.",
    ]
    return "\n".join(lineas) + "\n"


def _envolver(texto, ancho):
    """Parte un parrafo en lineas sin cortar palabras."""
    palabras, linea, salida = texto.split(), "", []
    for palabra in palabras:
        if len(linea) + len(palabra) + 1 > ancho:
            salida.append(linea)
            linea = palabra
        else:
            linea = f"{linea} {palabra}".strip()
    if linea:
        salida.append(linea)
    return salida
