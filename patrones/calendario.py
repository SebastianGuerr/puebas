"""
Las variables externas, unificadas en una fila por dia. El lado derecho del cruce.

    python -m patrones --calendario     construye la tabla y dice que quedo

QUE HACE ESTE MODULO
    calendarios/ tiene cinco archivos con cinco formas distintas: dos son
    tablas diarias y tres son listas de eventos con fecha de inicio y de fin.
    Aqui se convierten en UNA tabla diaria, que es la unica forma que se puede
    pegar a la serie de triage.

    No calcula ninguna asociacion. Decide que significa 'ese dia hubo feria' y
    lo deja escrito, que es un paso que conviene tener aparte: si manana se
    cambia el criterio, se cambia aqui y todo lo que cuelga se recalcula igual.

LAS TRES VARIABLES DE CLIMA QUE PARECEN UTILES Y NO LO SON
    clima_unificado.csv trae cuatro banderas binarias ya calculadas. Medidas
    sobre los 598 dias con clima de la ventana util (2025-01-08 a 2026-09-14):

        llovio          cierta el 98,8% de los dias
        dia_frio        cierta el  0,0% de los dias
        dia_calido      cierta el  1,7% de los dias
        lluvia_fuerte   cierta el 11,4% de los dias   <- la unica con reparto

    Las tres primeras son constantes en la practica. Meter una constante en un
    modelo no da un resultado debil: da un coeficiente indeterminado o, peor,
    uno enorme sostenido por los diez dias en que la bandera cambio. Por eso se
    EXCLUYEN aqui, con el numero medido al lado, en vez de dejarlas pasar para
    que alguien las pruebe mas adelante sin saber esto.

    En Manizales llueve casi todos los dias. La pregunta util no es si llovio
    sino CUANTO, y eso es precip_consenso_mm (media 8,1 mm, sd 10,4) y los
    acumulados precip_7d (media 57,1, sd 48,6) y precip_30d (media 244, sd 145).

LA TEMPERATURA TAMPOCO VA A EXPLICAR NADA, Y SE DEJA IGUAL
    temp_media_consenso tiene media 16,5 C y sd 0,60 en la ventana: menos de
    cuatro grados entre el dia mas frio y el mas caluroso de veinte meses.
    Manizales no tiene estaciones termicas.

    Se conserva de todos modos, por dos motivos. Uno, temp_max_consenso si se
    mueve algo mas (sd 1,29) y la maxima del dia es una variable distinta de la
    media. Dos, y mas importante: una variable que se prueba y no da nada es un
    resultado que hay que poder reportar. Excluirla de entrada convierte 'no
    encontramos efecto de la temperatura' en 'no lo buscamos'.

    La diferencia con las banderas de arriba es real y no de criterio: una
    constante no se puede probar, una variable de rango pequeno si -- solo que
    con poca potencia, que es otra cosa y se dice en el informe.

LOS DIAS SIN CLIMA DEL FINAL NO SE RELLENAN
    clima_unificado.csv llega hasta 2026-08-28 y el triage hasta 2026-09-14.
    Medido: 20 dias al final de la ventana sin ninguna variable climatica -- 17
    porque el archivo no llega y 3 mas porque sus ultimas filas vienen vacias
    salvo los acumulados moviles. Ese numero crece un dia por dia que pase sin
    volver a correr la descarga, asi que el que manda es el que imprime la
    corrida y no este.

    No se interpolan. Rellenar la lluvia de esos dias a partir del acumulado
    anterior inventaria precisamente la variable que se quiere medir. Quedan en
    nulo y la columna 'tiene_clima' dice cuales son, para que los modelos los
    descarten explicitamente y el informe pueda decir cuantos dias perdio.

    Se arregla corriendo otra vez calendarios/clima/clima_manizales.py y
    despues calendarios/clima/clima_unificado.py. Es la primera cosa que
    conviene hacer antes de darle peso a cualquier resultado sobre el final de
    la ventana.

LAS TRES TABLAS DE EVENTOS SE EXPANDEN A DIAS, Y ESO TIENE UN COSTO
    desastres, eventos y vigilancia vienen como (fecha_inicio, fecha_fin). Para
    pegarlas a una serie diaria hay que marcar cada dia del intervalo.

    El costo esta en vigilancia_salud: 20 de sus 321 filas duran 2.921 dias --
    son lineas base plurianuales, no brotes -- y expandidas marcarian la
    ventana entera. Una variable cierta todos los dias es otra constante. Por
    eso hay un tope: los intervalos de mas de MAXIMO_DIAS_EVENTO dias no se
    expanden como bandera diaria, se cuentan aparte y se avisa.

    Con eventos/ pasa algo parecido pero menor: la mediana dura 6 dias y el
    maximo 160.

LO QUE NO SE PUEDE ARREGLAR: LOS DESASTRES NO DAN PARA ESTADISTICA
    desastres_manizales_2020_2026.csv tiene 17 filas en siete anos, y en la
    ventana util caben muy pocas. Se cargan y se marcan porque para LEER una
    grafica valen mucho -- el sismo del 2026-08-10 explica solo cualquier pico
    de esos dias -- pero no entran como variable de un modelo: con tres o
    cuatro dias marcados no hay contraste que estimar.

    Es la diferencia entre una variable y una anotacion, y aqui se respeta:
    van a la tabla con el prefijo 'nota_' y asociacion.py no las prueba.
"""

import unicodedata

import numpy as np
import pandas as pd

from patrones import rutas

# Un evento mas largo que esto no describe un dia, describe una epoca. Se
# cuenta pero no se expande. 120 dias es un trimestre largo: por encima de eso
# ninguna de las ventanas de vigilancia_salud es un brote.
MAXIMO_DIAS_EVENTO = 120

# Dias minimos en cada estado para que una bandera binaria sea una VARIABLE.
#
# No es lo mismo que el filtro de constantes y hace falta igual. Medido sobre
# la ventana, la expansion de eventos deja banderas asi:
#
#     evento_emergencia                  1 dia marcado  (0,2%)
#     vigilancia_epidemias_emergencias   1 dia          (0,2%)
#     evento_deportivo                   3 dias         (0,5%)
#     vigilancia_clima                 599 dias         (97,4%)  <- por el otro lado
#
# Ninguna es constante, asi que el filtro de nunique no las ve, y las cuatro
# son igual de inservibles: el 'efecto' de evento_emergencia seria la diferencia
# entre un solo dia y los otros 614. Ese dia es el sismo del 2026-08-10, y que
# ese dia se salga de la serie no es un hallazgo estadistico, es el sismo.
#
# Y NO SE ARREGLA CON MAS NOTAS. Es la trampa de este umbral y por eso conviene
# tenerla escrita: es tentador pensar que con el corpus completo los 14 dias de
# la Feria pasan de 11 notas diarias a 150 y entonces ya se puede estimar. No.
# Los 14 dias de la Feria son CONSECUTIVOS, y la serie tiene autocorrelacion de
# 0,70 a 7 dias: como observaciones independientes esos 14 dias valen dos o
# tres, no catorce. Mas notas por dia achican el error de medicion de cada dia,
# pero no crean dias de feria que no existieron. Lo unico que mueve este limite
# es que pase mas tiempo y haya mas ediciones del evento en la ventana.
#
# 20 dias es la frontera entre una variable y una anecdota, no un umbral fino.
# Lo que queda fuera no desaparece: sigue en el tablero y en los calendarios de
# vistas.py, que es donde una temporada de 14 dias si se puede leer a ojo. Lo
# que no hace es gastar una prueba del presupuesto de la correccion por
# multiplicidad para devolver un intervalo que abarca cualquier cosa.
MINIMO_DIAS_BANDERA = 20

# Banderas de clima que en la ventana util son constantes. Se excluyen con el
# numero medido al lado; ver el encabezado del modulo.
BANDERAS_DEGENERADAS = {
    "llovio": "cierta el 98,8% de los dias",
    "dia_frio": "cierta el 0,0% de los dias",
    "dia_calido": "cierta el 1,7% de los dias",
}

# Las columnas de clima que si tienen rango. El orden es el del informe.
CLIMA_NUMERICO = [
    "precip_consenso_mm",
    "precip_7d",
    "precip_30d",
    "temp_media_consenso",
    "temp_max_consenso",
    "temp_min_consenso",
    "humedad_consenso",
    "viento_consenso_ms",
    "radiacion_consenso",
]
CLIMA_BINARIO = ["lluvia_fuerte"]

# Las del calendario laboral. Son las que HAY QUE llevar siempre: el ciclo
# semanal es la senal mas grande de la serie (lunes 219,8 triages/dia contra
# domingo 145,1, un -34%) y sin ellas cualquier variable climatica que se
# reparta distinto entre semana y fin de semana se lleva ese credito.
CALENDARIO_BINARIO = [
    "es_finde",
    "es_festivo",
    "es_puente",
    "es_vispera_festivo",
    "es_post_festivo",
    "es_quincena",
    "es_vacaciones_escolares",
    "es_temporada_navidad",
    "es_semana_santa",
]
CALENDARIO_CATEGORICO = ["nombre_dia", "nombre_mes"]

# ==========================================================
# CONFUSOR NO ES LO MISMO QUE EXPOSICION, Y CONFUNDIRLOS INVALIDA LA CUENTA
# ==========================================================
#
# Una variable entra al analisis en uno de dos papeles y nunca en los dos:
#
#   CONFUSOR    va SIEMPRE dentro del modelo, ajustando. No se prueba.
#               El dia de la semana y los festivos son esto: se sabe de
#               antemano que mueven el volumen -- lunes 219,8 triages contra
#               domingo 145,1 -- y lo que se quiere es descontarlos para que
#               no se lleven el credito de un efecto del clima.
#
#   EXPOSICION  es lo que se prueba. El clima, los eventos, las alertas.
#
# Poner una variable en los dos papeles a la vez no da un resultado malo: no
# da ninguno. Se ve en la cuenta de la potencia, que mide cuanta variacion le
# queda a la exposicion despues de ajustar por los confusores:
#
#     es_finde     R2 contra el calendario = 1,00   variacion utilizable = 0%
#     es_festivo   R2 contra el calendario = 1,00   variacion utilizable = 0%
#
# Claro: son el propio ajuste. Preguntarle a un modelo que ya descuenta el fin
# de semana si el fin de semana tiene efecto es preguntarle por algo que acaba
# de borrar. La respuesta es siempre 'no' y no significa nada.
#
# Si el efecto del festivo interesa por si mismo -- y en este proyecto
# interesa, exploracion.ipynb ya lo midio a mano -- es OTRO analisis, con el
# festivo como exposicion y sin el en el ajuste. No se mezclan en la misma
# corrida.
CONFUSORES = ["es_finde", "es_festivo"]


# ==========================================================
# LA TEMPORADA CLIMATICA
# ==========================================================
#
# Los parametros son los de exploracion.ipynb, celda 20, sin cambiarlos. Esa
# figura ya se leyo y se discutio en este proyecto: mover los cortes ahora
# haria que las dos no se puedan comparar, que es peor que cualquier mejora
# que se les pudiera hacer.
VENTANA_REGIMEN = 30      # dias de la media/suma movil que define el regimen
VENTANA_MODA = 21         # dias del suavizado por moda
UMBRAL_FRIO, UMBRAL_CALIDO = 16.0, 17.5
CUANTILES_LLUVIA = (0.33, 0.67)

# Los nueve nombres posibles y su escala de color. El orden es el de la leyenda.
TEMPORADAS = {
    "Lluviosa-fria": "PuBu",
    "Lluviosa-templada": "GnBu",
    "Lluviosa-calida": "BuGn",
    "Intermedia-fria": "Greys",
    "Intermedia-templada": "YlGn",
    "Intermedia-calida": "YlGnBu",
    "Seca-fria": "BuPu",
    "Seca-templada": "YlOrBr",
    "Seca-calida": "YlOrRd",
}


def _leer(ruta, columnas_fecha):
    """Un CSV de calendarios/ con sus fechas ya convertidas."""
    if not ruta.exists():
        raise SystemExit(
            f"No existe {ruta}.\n"
            f"calendarios/ es una ENTRADA de este paquete y no una salida: "
            f"tiene que estar en el repositorio antes de correr esto.")
    tabla = pd.read_csv(ruta, encoding="utf-8-sig", low_memory=False)
    for columna in columnas_fecha:
        if columna in tabla.columns:
            tabla[columna] = pd.to_datetime(tabla[columna], errors="coerce")
    return tabla


# ==========================================================
# LAS DOS TABLAS QUE YA SON DIARIAS
# ==========================================================

def clima(desde, hasta):
    """
    Una fila por dia con las variables climaticas que tienen rango.

    'tiene_clima' es falso en los dias que el archivo no alcanza. No se rellena
    -- ver el encabezado del modulo -- y es la columna con la que los modelos
    descartan esos dias sin que desaparezcan en silencio.
    """
    tabla = _leer(rutas.CLIMA, ["fecha"])
    presentes = [c for c in CLIMA_NUMERICO + CLIMA_BINARIO if c in tabla.columns]
    faltan = set(CLIMA_NUMERICO + CLIMA_BINARIO) - set(presentes)
    if faltan:
        print(f"  aviso: clima_unificado.csv no trae {sorted(faltan)}. "
              f"Se sigue sin ellas.")

    tabla = tabla.loc[:, ["fecha"] + presentes]
    rejilla = pd.DataFrame({"fecha": pd.date_range(desde, hasta, freq="D")})
    tabla = rejilla.merge(tabla, on="fecha", how="left")

    # Un dia cuenta como 'con clima' si trae la lluvia del dia, que es la
    # variable que manda. Los acumulados moviles siguen existiendo despues del
    # ultimo dia observado -- son sumas de lo anterior -- y usarlos para decidir
    # esto marcaria como completos dias que no tienen ninguna medicion propia.
    if "precip_consenso_mm" in tabla.columns:
        tabla["tiene_clima"] = tabla["precip_consenso_mm"].notna()
    else:
        tabla["tiene_clima"] = False
    return tabla


def temporada(desde=None, hasta=None, referencia="historica"):
    """
    La temporada climatica de cada dia. Devuelve (serie, detalle).

    Es la clasificacion de exploracion.ipynb: se cruza el regimen de lluvia
    (terciles del acumulado de 30 dias) con el termico (media movil de 30 dias
    contra dos umbrales) y se suaviza el resultado con una moda de 21 dias,
    para que un dia suelto no parta una temporada en dos.

    EL EJE TERMICO CASI NO SEPARA, Y HAY QUE SABERLO ANTES DE LEER LA FIGURA
        Medido sobre los 2.432 dias de clima disponibles, la media movil de 30
        dias cae asi contra los umbrales 16,0 y 17,5:

            fria      311 dias   (12,8%)
            templada 2090 dias   (85,9%)   <- casi todo
            calida     31 dias   ( 1,3%)

        O sea que de las nueve casillas del cruce, en la practica se usan tres:
        las 'templada'. Las otras seis aparecen en rachas cortas o no aparecen.

        No es un defecto de los umbrales, es Manizales: la temperatura se mueve
        menos de tres grados entre la media movil mas fria y la mas calurosa de
        seis anos. La figura sigue siendo util porque el eje que SI separa es
        el de lluvia; conviene leerla como tres temporadas de humedad y no
        como nueve.

    'referencia' DECIDE CONTRA QUE ES 'SECO', Y CAMBIA EL RESULTADO ENTERO
        Los terciles de lluvia hay que calcularlos sobre algun periodo, y no da
        lo mismo cual. Medido sobre la ventana con temas (2025-01-08 a
        2026-09-14):

            historica  terciles sobre los 2020-2026 disponibles
                       cortes: seco <= 217,6 mm / lluvioso >= 377,4 mm
                       -> Seca 347 dias, Intermedia 123, Lluviosa 106

            ventana    terciles sobre la propia ventana
                       cortes: seco <= 142,5 mm / lluvioso >= 256,4 mm
                       -> Seca 192, Intermedia 195, Lluviosa 192

        Las dos son correctas y responden preguntas distintas. La historica
        dice que 2025-2026 fue un periodo SECO para Manizales, que es un hecho
        y se pierde si se normaliza contra si mismo. La de ventana reparte los
        dias en tres tercios por construccion, lo que da grupos del mismo
        tamano y por tanto mas potencia para comparar temas entre temporadas.

        Por defecto va la historica, que es lo que hace el notebook y lo que
        conserva el significado de la palabra 'seca'. Si lo que se quiere es
        comparar composiciones de temas, conviene 'ventana' -- con 106 dias
        lluviosos contra 347 secos, el grupo chico manda sobre el error.

    NO SE RELLENAN LOS DIAS SIN CLIMA
        Quedan en nulo, igual que en clima(). La moda de 21 dias los ignora, de
        modo que un hueco corto se cubre con los vecinos; el hueco de 20 dias
        del final de la ventana no, y esos dias salen sin temporada.
    """
    tabla = _leer(rutas.CLIMA, ["fecha"])
    tabla = (tabla.dropna(subset=["fecha"]).drop_duplicates("fecha")
             .set_index("fecha").sort_index())

    media = tabla["temp_media_consenso"].rolling(
        VENTANA_REGIMEN, min_periods=10, center=True).mean()
    suma = tabla["precip_consenso_mm"].rolling(
        VENTANA_REGIMEN, min_periods=10, center=True).sum()

    if referencia == "ventana" and desde is not None and hasta is not None:
        base = suma.loc[pd.Timestamp(desde):pd.Timestamp(hasta)]
    elif referencia == "historica":
        base = suma
    else:
        raise SystemExit(f"referencia desconocida: {referencia}. "
                         f"Hay 'historica' y 'ventana'.")
    seco, lluvioso = base.quantile(list(CUANTILES_LLUVIA))

    humedad = pd.Series(np.select(
        [suma >= lluvioso, suma <= seco],
        ["Lluviosa", "Seca"], default="Intermedia"), index=suma.index)
    termico = pd.Series(np.select(
        [media < UMBRAL_FRIO, media > UMBRAL_CALIDO],
        ["fria", "calida"], default="templada"), index=media.index)

    cruda = (humedad + "-" + termico).where(media.notna() & suma.notna())
    suave = _moda_movil(cruda, VENTANA_MODA)

    if desde is not None and hasta is not None:
        rejilla = pd.date_range(desde, hasta, freq="D")
        suave = suave.reindex(rejilla)

    detalle = {
        "referencia": referencia,
        "corte_seco": float(seco),
        "corte_lluvioso": float(lluvioso),
        "dias": suave.value_counts().to_dict(),
        "sin_temporada": int(suave.isna().sum()),
    }
    return suave.rename("temporada"), detalle


def _moda_movil(serie, ventana):
    """
    El valor mas frecuente en una ventana centrada. Suaviza sin promediar.

    No se puede usar una media movil porque la temporada es una etiqueta y no
    un numero: la media de 'Seca' y 'Lluviosa' no existe. La moda es el
    equivalente para categorias y es lo que hace que una temporada sea un
    bloque continuo en vez de un mosaico de dias sueltos.
    """
    valores = serie.to_numpy(dtype=object)
    mitad = ventana // 2
    salida = np.full(len(valores), np.nan, dtype=object)
    for i in range(len(valores)):
        bloque = valores[max(0, i - mitad):min(len(valores), i + mitad + 1)]
        bloque = [v for v in bloque if isinstance(v, str)]
        if bloque:
            salida[i] = max(set(bloque), key=bloque.count)
    return pd.Series(salida, index=serie.index, dtype=object)


def festivos(desde, hasta):
    """
    Una fila por dia con el calendario laboral y cultural colombiano.

    calendario_Colombia.csv cubre 2020-01-01 a 2026-12-31 sin un solo hueco, de
    modo que aqui no hay nada que rellenar ni que avisar. Es la unica de las
    cinco entradas que no tiene ningun problema de cobertura.
    """
    tabla = _leer(rutas.FESTIVOS, ["fecha"])
    columnas = ["fecha"] + [c for c in CALENDARIO_BINARIO + CALENDARIO_CATEGORICO
                            if c in tabla.columns]
    tabla = tabla.loc[:, columnas]

    rejilla = pd.DataFrame({"fecha": pd.date_range(desde, hasta, freq="D")})
    tabla = rejilla.merge(tabla, on="fecha", how="left")

    perdidos = (int(tabla["es_festivo"].isna().sum())
                if "es_festivo" in tabla.columns else 0)
    if perdidos:
        print(f"  aviso: {perdidos} dias de la ventana no estan en "
              f"calendario_Colombia.csv. Hay que reextenderlo con "
              f"'python calendarios/calendario_colombia.py'.")

    for columna in CALENDARIO_BINARIO:
        if columna in tabla.columns:
            tabla[columna] = tabla[columna].fillna(0).astype(int)
    return tabla


# ==========================================================
# LAS TRES TABLAS DE EVENTOS
# ==========================================================

def _limpiar(texto):
    """Un nombre de columna a partir de una categoria escrita a mano."""
    plano = unicodedata.normalize("NFKD", str(texto))
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = plano.strip().lower().replace(" ", "_").replace("-", "_")
    return "".join(c for c in plano if c.isalnum() or c == "_")


def _expandir(tabla, desde, hasta, prefijo, columna_categoria=None,
              maximo=MAXIMO_DIAS_EVENTO):
    """
    Convierte filas (fecha_inicio, fecha_fin) en banderas diarias.

    Devuelve la tabla diaria y un resumen de lo que NO se pudo expandir, que es
    tan importante como lo que si: son las filas sin fecha y las ventanas
    demasiado largas para significar algo como bandera de un dia.

    La marca se hace con busqueda por posicion sobre la rejilla y no con un
    bucle por dia dentro de otro bucle por fila: son 321 filas por 615 dias y
    hacerlo mal se nota.
    """
    dias = pd.date_range(desde, hasta, freq="D")
    salida = pd.DataFrame({"fecha": dias})
    desde, hasta = pd.Timestamp(desde), pd.Timestamp(hasta)

    sin_fecha = int(tabla["fecha_inicio"].isna().sum())
    util = tabla.dropna(subset=["fecha_inicio"]).copy()
    # Un evento de un solo dia suele venir sin fecha_fin. Dura ese dia.
    util["fecha_fin"] = util["fecha_fin"].fillna(util["fecha_inicio"])
    util["dias"] = (util["fecha_fin"] - util["fecha_inicio"]).dt.days + 1

    muy_largos = int((util["dias"] > maximo).sum())
    util = util[util["dias"] <= maximo]

    def _marcar(filas):
        """Cuantos de esos intervalos cubre cada dia de la rejilla."""
        conteo = np.zeros(len(dias), dtype=int)
        for inicio, fin in zip(filas["fecha_inicio"], filas["fecha_fin"]):
            if fin < desde or inicio > hasta:
                continue
            i = dias.searchsorted(max(inicio, desde), side="left")
            j = dias.searchsorted(min(fin, hasta), side="right")
            conteo[i:j] += 1
        return conteo

    # Se cuenta cuantos eventos cubren cada dia, no solo si hay alguno: dos
    # ferias solapadas no son lo mismo que una, y el conteo deja decidirlo
    # despues sin volver a expandir.
    conteo = _marcar(util)
    salida[f"{prefijo}_n"] = conteo
    salida[prefijo] = (conteo > 0).astype(int)

    # Una columna por categoria, porque 'hubo un evento' mezcla una procesion
    # con un terremoto. El analisis se hace por categoria o no se hace.
    categorias = {}
    if columna_categoria and columna_categoria in util.columns:
        for categoria, grupo in util.groupby(columna_categoria):
            marca = (_marcar(grupo) > 0).astype(int)
            if marca.sum():
                nombre = f"{prefijo}_{_limpiar(categoria)}"
                salida[nombre] = marca
                categorias[nombre] = int(marca.sum())

    resumen = {
        "filas": len(tabla),
        "sin_fecha": sin_fecha,
        "muy_largos": muy_largos,
        "dias_marcados": int((conteo > 0).sum()),
        "categorias": categorias,
    }
    return salida, resumen


def eventos(desde, hasta):
    """Ferias, procesiones, conciertos: lo que junta gente en la ciudad."""
    tabla = _leer(rutas.EVENTOS, ["fecha_inicio", "fecha_fin"])
    return _expandir(tabla, desde, hasta, "evento", "categoria")


def desastres(desde, hasta):
    """
    Deslizamientos, sismos, vendavales. ANOTACION, NO VARIABLE.

    Son 17 filas en siete anos. En la ventana util quedan poquisimas y por eso
    el prefijo es 'nota_': sirven para entender un pico al mirar una grafica,
    no para estimar un coeficiente. asociacion.py las salta a proposito.
    """
    tabla = _leer(rutas.DESASTRES, ["fecha_inicio", "fecha_fin"])
    return _expandir(tabla, desde, hasta, "nota_desastre", "tipo_evento")


def vigilancia(desde, hasta):
    """
    Brotes y ventanas epidemiologicas declaradas: dengue, respiratorias, etc.

    Es la entrada mas heterogenea de las cinco: 88 de sus 321 filas son fechas
    conmemorativas ('Dia Mundial contra el VIH') y 20 son lineas base de 2.921
    dias. Las segundas las corta el tope de _expandir; las primeras se quitan
    aqui, porque no describen lo que pasa en la ciudad sino el almanaque de
    campanas de MinSalud, y marcarian dias sueltos sin ninguna relacion con
    cuanta gente consulta.

    Lo que si vale mucho es la categoria: 'vectores' marcando los meses de un
    brote de dengue es exactamente el tipo de variable externa que puede
    explicar un tema del agrupamiento, y es informacion que no esta en el clima.
    """
    tabla = _leer(rutas.VIGILANCIA, ["fecha_inicio", "fecha_fin"])
    if "categoria" in tabla.columns:
        tabla = tabla[tabla["categoria"] != "calendario_preventivo"]
    return _expandir(tabla, desde, hasta, "vigilancia", "categoria")


# ==========================================================
# LA TABLA UNICA
# ==========================================================

def construir(desde, hasta, aviso=print):
    """
    Une las cinco entradas en una fila por dia. Devuelve la tabla y el resumen.

    El resumen no es decorativo: dice cuantos dias quedaron sin clima y cuantos
    eventos no se pudieron expandir, que es lo que hay que saber ANTES de leer
    una correlacion calculada sobre esta tabla.
    """
    desde, hasta = pd.Timestamp(desde), pd.Timestamp(hasta)
    aviso(f"  ventana: {desde.date()} a {hasta.date()} "
          f"({(hasta - desde).days + 1} dias)")

    tabla = clima(desde, hasta)
    tabla = tabla.merge(festivos(desde, hasta), on="fecha", how="left")

    resumenes = {}
    for nombre, funcion in [("eventos", eventos), ("desastres", desastres),
                            ("vigilancia", vigilancia)]:
        parcial, resumen = funcion(desde, hasta)
        tabla = tabla.merge(parcial, on="fecha", how="left")
        resumenes[nombre] = resumen
        aviso(f"  {nombre}: {resumen['dias_marcados']} dias marcados desde "
              f"{resumen['filas']} filas"
              + (f", {resumen['sin_fecha']} sin fecha"
                 if resumen["sin_fecha"] else "")
              + (f", {resumen['muy_largos']} ventanas de mas de "
                 f"{MAXIMO_DIAS_EVENTO} dias sin expandir"
                 if resumen["muy_largos"] else ""))

    # La temporada climatica entra como columna de TEXTO, y por eso no la ve
    # variables_probables(): no es una variable que se pruebe una a una -- seria
    # tres banderas correlacionadas entre si -- sino la que contesta la pregunta
    # entera de una vez en tablero.composicion_por_temporada(). Ademas es la
    # categorica que agrupamiento.py necesita, que es justo lo que K-Prototypes
    # sabe usar y una columna numerica no puede dar.
    try:
        etiquetas, detalle_temporada = temporada(desde, hasta)
        tabla = tabla.merge(etiquetas.rename("temporada"),
                            left_on="fecha", right_index=True, how="left")
        resumenes["temporada"] = detalle_temporada
        reparto = ", ".join(f"{k} {v}" for k, v in
                            sorted(detalle_temporada["dias"].items(),
                                   key=lambda x: -x[1])[:4])
        aviso(f"  temporadas ({detalle_temporada['referencia']}): {reparto}")
    except SystemExit:
        raise
    except Exception as error:
        aviso(f"  aviso: no se pudo clasificar la temporada climatica "
              f"({error}). El resto sigue.")
        tabla["temporada"] = np.nan

    sin_clima = int((~tabla["tiene_clima"]).sum())
    if sin_clima:
        aviso(f"  AVISO: {sin_clima} dias sin clima al final de la ventana "
              f"(clima_unificado.csv va atrasado). No se rellenan.")

    resumenes["clima"] = {
        "dias_sin_clima": sin_clima,
        "excluidas": dict(BANDERAS_DEGENERADAS),
    }
    return tabla, resumenes


def variables_probables(tabla, minimo=MINIMO_DIAS_BANDERA, detalle=False):
    """
    Que columnas de la tabla son VARIABLES y cuales son anotaciones o llaves.

    Existe para que asociacion.py no tenga que adivinarlo con una heuristica
    sobre el nombre, y para que la lista de lo que se probo quede en un solo
    sitio. Las 'nota_' quedan fuera por construccion: ver desastres().

    TRES FILTROS, Y LOS TRES DESCARTAN ANTES DE MIRAR NINGUN RESULTADO
        Eso es lo que los hace validos. Decidir que variables entran despues de
        ver cuales dieron una correlacion bonita es el camino corto al hallazgo
        falso, y ademas rompe la correccion por multiplicidad: el numero de
        pruebas que hay que corregir es el de las que se PODIAN hacer.

        1. no es numerica          ni fecha ni nombre de mes
        2. no varia                un solo valor en la ventana
        3. no esta balanceada      menos de 'minimo' dias en alguno de los dos
                                   estados, si es binaria

    Con detalle=True devuelve tambien las descartadas y el motivo, que es lo
    que el informe imprime para que quede escrito que se dejo fuera y por que.
    """
    fuera = ({"fecha", "tiene_clima", "nombre_dia", "nombre_mes", "temporada"}
             | set(CONFUSORES))
    dentro, descartadas = [], {}

    for columna in tabla.columns:
        if columna in fuera or columna.startswith("nota_"):
            continue
        if not pd.api.types.is_numeric_dtype(tabla[columna]):
            continue

        valores = tabla[columna].dropna()
        if valores.nunique() <= 1:
            descartadas[columna] = "constante en la ventana"
            continue

        # El balance solo aplica a las binarias. Una numerica continua concentrada
        # en pocos valores no tiene este problema: su varianza esta repartida.
        if valores.isin([0, 1]).all():
            unos = int(valores.sum())
            ceros = int(len(valores) - unos)
            if min(unos, ceros) < minimo:
                descartadas[columna] = (
                    f"solo {min(unos, ceros)} dias en el estado minoritario "
                    f"(hacen falta {minimo})")
                continue

        dentro.append(columna)

    return (dentro, descartadas) if detalle else dentro


def guardar(tabla):
    """Escribe la tabla diaria y devuelve su ruta."""
    tabla.to_parquet(rutas.CALENDARIO_DIARIO, index=False)
    return rutas.CALENDARIO_DIARIO
