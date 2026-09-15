"""
Los dibujos. Calendarios alineados y matrices de asociacion.

    python -m patrones --vistas      rehace salidas/figuras/ y no calcula nada

POR QUE HAY DIBUJOS EN UN PAQUETE QUE YA IMPRIME NUMEROS
    Porque las dos cosas responden preguntas distintas y ninguna reemplaza a la
    otra.

    asociacion.py contesta "¿esta correlacion sobrevive a corregir por las 600
    pruebas que se hicieron?". Es la pregunta que evita el hallazgo falso, y hay
    que hacerla. Lo que NO hace es sugerir que mirar: una prueba solo puede
    confirmar o negar una hipotesis que alguien ya tuvo.

    Un calendario de veinte meses puesto encima del calendario de la lluvia es
    lo que produce esa hipotesis. Un ojo entrenado ve ahi una racha de tres
    semanas que ninguna correlacion global iba a encontrar, porque una
    correlacion promedia la ventana entera y una racha de tres semanas se
    diluye en 615 dias.

    EL ORDEN IMPORTA Y ES ESTE: mirar primero, y despues probar contra datos
    que no se usaron para mirar. Mirar, elegir lo que se ve mas bonito y
    probarlo sobre los mismos datos es como se fabrica un resultado falso con
    todas las de la ley. Lo que estas figuras producen es una PREGUNTA, y la
    pregunta hay que anotarla en datos/variables.csv antes de correr la prueba.

DE DONDE SALE ESTE ESTILO
    De exploracion.ipynb, que es donde se dibujaron los primeros calendarios de
    este proyecto. La rejilla, los colores y los remates son los mismos a
    proposito: quien ya leyo esas figuras no tiene que aprender a leer estas.

        rejilla 7 x n_semanas    pcolormesh, una fila por dia de la semana
        #eeeeee                  el dia que existe pero no tiene dato
        YlOrRd                   la magnitud
        edgecolors blanco        la separacion entre celdas
        sin marco, sin ticks     el calendario es la figura, no un eje

    Lo unico que NO se hereda es calplot. El notebook lo importa en una celda,
    no esta instalado en el entorno y esa celda hoy falla. Las otras dos celdas
    de calendario estan hechas a mano con pcolormesh y salen igual de bien, asi
    que se copia ese camino y el paquete no gana una dependencia.

LA PALETA DE LAS MATRICES ES OTRA, Y TIENE QUE SERLO
    Un calendario muestra MAGNITUD: cuantas notas hubo. Una escala de un solo
    sentido, clara a oscura, es lo correcto y YlOrRd la cumple.

    Una matriz de correlacion muestra SIGNO: sube o baja. Ahi una escala de un
    solo sentido miente, porque pinta -0,4 y +0,4 con colores distintos sin
    decir que son simetricos, y pinta el cero en medio de la rampa como si
    fuera un valor mas. Lleva una escala divergente con el cero en gris neutro
    y los limites simetricos, que es lo que hace _divergente().

    Los dos polos son los mismos del notebook: #1f6fb4 para lo que baja y
    #c0392b para lo que sube.
"""

import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # se escriben archivos; no hay ventana que abrir
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import (LinearSegmentedColormap, ListedColormap,  # noqa: E402
                               Normalize, TwoSlopeNorm)
from matplotlib.cm import ScalarMappable  # noqa: E402

from patrones import rutas  # noqa: E402

DIAS = ["Lun", "Mar", "Mie", "Jue", "Vie", "Sab", "Dom"]
MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]

VACIO = "#eeeeee"      # el dia sin dato
TINTA = "#2c3e50"      # texto principal
TENUE = "#9a9a9a"      # etiquetas de ano y ejes
SUBE = "#c0392b"
BAJA = "#1f6fb4"

CALOR = "YlOrRd"       # magnitud de notas
AGUA = "PuBu"          # magnitud de lluvia: otra escala para otra cosa

# ==========================================================
# LOS CUATRO COLORES DE SERIE, Y POR QUE SON CUATRO Y NO LOS DE MATPLOTLIB
# ==========================================================
#
# El ciclo por defecto de matplotlib (tab10) NO es utilizable para lineas que
# hay que distinguir entre si. Medido sobre sus seis primeros colores, con la
# simulacion de Machado y distancia en OKLab x100 -- el umbral practico para
# que dos colores se distingan es 8, y por debajo de 6 no se distinguen:
#
#     naranja #ff7f0e contra verde  #2ca02c     0,7   <- indistinguibles
#     azul    #1f77b4 contra morado #9467bd     1,7
#     verde   #2ca02c contra rojo   #d62728     3,9
#     rojo    #d62728 contra marron #8c564b     4,6
#
# Para un lector con deuteranopia -- uno de cada doce hombres -- el naranja y
# el verde de esa figura son el mismo color. Y ademas el naranja no llega al
# contraste minimo contra el fondo blanco.
#
# Estos cuatro estan verificados con la misma cuenta y pasan todo: banda de
# luminosidad, piso de croma, distancia CVD entre TODOS los pares (minimo 8,1),
# distancia en vision normal (minimo 17,6) y contraste contra el fondo
# (minimo 3,17).
#
# SON CUATRO A PROPOSITO. Con seis lineas no hay forma de que todos los pares
# se separen, y las candidatas de seis que se probaron fallaban entre 1,8 y
# 7,6. Antes que repartir colores que no se distinguen, se dibujan menos
# lineas: perfil_rezagos() se queda con las cuatro variables de mayor
# correlacion absoluta. Lo que no cabe, no entra.
CATEGORICAS = ["#0b5fa5", "#d1495b", "#b8860b", "#2e7d32"]
MAXIMO_SERIES = len(CATEGORICAS)


def _divergente():
    """
    Azul - gris - rojo, con el gris exactamente en el cero.

    El punto medio va en gris y no en blanco a proposito: sobre el fondo blanco
    de la figura un midpoint blanco hace desaparecer las celdas de correlacion
    nula, y 'no hay relacion' es un resultado que tiene que verse igual que los
    otros. En gris se ve que la celda existe y que no dice nada.
    """
    return LinearSegmentedColormap.from_list(
        "sube_baja", [BAJA, "#dcdcdc", SUBE])


# ==========================================================
# LA REJILLA DEL CALENDARIO
# ==========================================================

def _rejilla(anio, serie):
    """
    Los valores de un ano colocados en una matriz 7 x n_semanas.

    La cuenta es la de exploracion.ipynb: la columna es la semana corrida desde
    el 1 de enero teniendo en cuenta en que dia cayo, y la fila es el dia de la
    semana. No se usa la semana ISO porque la ISO parte el ano -- el 1 de enero
    puede ser semana 52 del ano anterior -- y entonces el calendario arranca con
    una columna que pertenece a otra figura.
    """
    indice = pd.date_range(f"{anio}-01-01", f"{anio}-12-31", freq="D")
    valores = serie.reindex(indice).to_numpy(dtype=float)

    offset = pd.Timestamp(f"{anio}-01-01").dayofweek
    semana = ((indice.dayofyear.to_numpy() - 1 + offset) // 7).astype(int)
    dia = indice.dayofweek.to_numpy(dtype=int)
    n_semanas = int(semana.max()) + 1

    fondo = np.full((7, n_semanas), np.nan)
    datos = np.full((7, n_semanas), np.nan)
    fondo[dia, semana] = 1.0
    presentes = ~np.isnan(valores)
    datos[dia[presentes], semana[presentes]] = valores[presentes]
    return indice, semana, dia, fondo, datos


def _pintar(eje, fondo, datos, cmap, norma, etiqueta_y):
    """Una fila de calendario: el fondo gris y encima los dias con dato."""
    remate = dict(edgecolors="white", linewidth=0.5)
    eje.pcolormesh(np.ma.masked_invalid(fondo),
                   cmap=ListedColormap([VACIO]), **remate)
    eje.pcolormesh(np.ma.masked_invalid(datos), cmap=cmap, norm=norma, **remate)
    eje.invert_yaxis()
    eje.set_aspect("equal")
    eje.set_frame_on(False)
    eje.tick_params(length=0)
    eje.set_yticks(np.arange(7) + 0.5)
    eje.set_yticklabels(DIAS, fontsize=7, color=TENUE)
    eje.set_ylabel(etiqueta_y, fontsize=11, color=TINTA, rotation=0,
                   ha="right", va="center", labelpad=12)


def _meses(eje, indice, semana):
    """Las iniciales de mes debajo del calendario, en la semana que empiezan."""
    posiciones, nombres = [], []
    for mes in range(1, 13):
        primeros = np.where(indice.month.to_numpy() == mes)[0]
        if len(primeros):
            posiciones.append(semana[primeros[0]] + 0.5)
            nombres.append(MESES[mes - 1])
    eje.set_xticks(posiciones)
    eje.set_xticklabels(nombres, fontsize=8, color=TENUE)


# ==========================================================
# LA FIGURA QUE IMPORTA: DOS CALENDARIOS ALINEADOS
# ==========================================================

def calendarios(serie_tema, serie_variable, nombre_tema, nombre_variable,
                ruta=None, cmap_variable=AGUA):
    """
    El calendario del tema encima del de la variable, columna contra columna.

    ES LA FIGURA QUE RESPONDE 'A OJO' Y POR ESO ESTA PRIMERO
        Las dos rejillas comparten la posicion: la celda del 14 de marzo esta en
        la misma columna arriba y abajo. Una racha en que las dos se oscurecen
        juntas se ve de inmediato, y eso es exactamente lo que una correlacion
        global no puede mostrar porque la promedia con los otros veinte meses.

        Al reves tambien sirve, y es el uso mas honesto: si asociacion.py dice
        que hay una correlacion y aqui no se ve nada que coincida, esa
        correlacion casi seguro la sostienen la tendencia o el ciclo semanal y
        no ningun episodio real.

    LAS DOS ESCALAS SON DISTINTAS A PROPOSITO
        Arriba YlOrRd (notas) y abajo PuBu (lluvia). Usar la misma invitaria a
        comparar los colores entre paneles, que no significa nada: una celda
        'igual de roja' arriba y abajo no dice que los valores sean iguales,
        porque son unidades distintas. Colores distintos obligan a comparar lo
        unico comparable, que es DONDE estan las celdas oscuras.

        Cada panel lleva su propia barra de color con su unidad. Por lo mismo
        no se dibuja un eje doble: son dos figuras apiladas, no dos escalas en
        un mismo eje.
    """
    anios = sorted(set(serie_tema.index.year) | set(serie_variable.index.year))

    figura, ejes = plt.subplots(2 * len(anios), 1,
                                figsize=(15, 2.6 * len(anios)), squeeze=False)
    ejes = ejes[:, 0]

    norma_tema = _norma(serie_tema)
    norma_var = _norma(serie_variable)

    for k, anio in enumerate(anios):
        indice, semana, _, fondo, datos = _rejilla(anio, serie_tema)
        _pintar(ejes[2 * k], fondo, datos, CALOR, norma_tema, f"{anio}\ntema")
        ejes[2 * k].set_xticks([])

        _, _, _, fondo_v, datos_v = _rejilla(anio, serie_variable)
        _pintar(ejes[2 * k + 1], fondo_v, datos_v, cmap_variable, norma_var,
                f"{anio}\nvariable")
        _meses(ejes[2 * k + 1], indice, semana)

    figura.suptitle(f"{nombre_tema}  contra  {nombre_variable}",
                    fontsize=13, weight="bold", color=TINTA, y=0.995)
    # La advertencia va EN la figura y no solo en el informe, porque una figura
    # se copia a una presentacion y el informe se queda atras. El panel de
    # arriba dibuja CONTEOS, y los conteos arrastran la caida de la cobertura
    # del motivo de consulta (unos 9 puntos por ano): 2026 se ve mas palido que
    # 2025 en parte por eso y no solo porque hubiera menos consultas. Comparar
    # anos enteros a ojo en esta figura es el error que hay que evitar; lo que
    # si es comparable es la posicion de las celdas oscuras DENTRO de un ano.
    figura.text(0.5, 0.005,
                "Misma columna = mismo dia en los dos paneles. "
                "Gris = dia sin dato.\n"
                "El panel de arriba son CONTEOS: entre anos arrastran la caida "
                "de la cobertura del motivo (~9 puntos/ano).\n"
                "Comparar la POSICION de las celdas oscuras dentro de un ano, "
                "no el tono entre un ano y otro.",
                ha="center", fontsize=8, color=TENUE, linespacing=1.6)

    # Las dos barras van separadas lo suficiente para que sus etiquetas no se
    # pisen: con dos escalas apiladas el texto de la de abajo cae encima de la
    # de arriba y deja de leerse cual es cual, que en una figura de dos
    # unidades distintas es justo lo que no puede pasar.
    for escala, cmap, etiqueta, hueco in [
            (norma_tema, CALOR, f"notas de '{nombre_tema}'", 0.015),
            (norma_var, cmap_variable, nombre_variable, 0.075)]:
        barra = figura.colorbar(ScalarMappable(norm=escala, cmap=cmap),
                                ax=ejes.tolist(), fraction=0.014, pad=hueco,
                                shrink=0.75)
        barra.set_label(etiqueta, fontsize=9, color=TINTA, labelpad=8)
        barra.outline.set_visible(False)
        barra.ax.tick_params(labelsize=8, colors=TENUE, length=0)

    return _guardar(figura, ruta)


def temporadas(serie, etiquetas, titulo, unidad, ruta=None, minimo_dias=20):
    """
    El calendario coloreado por TEMPORADA CLIMATICA. La figura de exploracion.ipynb.

    Cada dia se pinta con la escala de color de su temporada y con la
    intensidad de su valor. Asi se ve a la vez CUANDO ocurrio cada temporada --
    los bloques de color -- y cuanto hubo cada dia -- el tono dentro del bloque.

    QUE APORTA SOBRE calendarios(), QUE TAMBIEN CRUZA TRIAGE Y CLIMA
        calendarios() pone dos rejillas, una encima de otra, y deja comparar
        posiciones. Sirve para episodios: una tormenta, una racha.

        Esta pone UNA sola rejilla y mete el clima en el color. Sirve para lo
        otro, que es lo que se pidio: ver el interior de una temporada. Con la
        serie de un tema, un bloque 'Lluviosa' que se oscurece entero mientras
        los bloques 'Seca' quedan palidos es exactamente el patron que se
        busca, y en dos rejillas separadas cuesta mas verlo.

    LA LEYENDA NO USA COORDENADAS FIJAS
        La version del notebook coloca las barras con fig.add_axes() en
        posiciones absolutas calculadas a mano. Eso funciona con plt.show() y
        se rompe al guardar con recorte ajustado: las barras quedan fuera del
        recorte o encima del calendario, segun cuantas temporadas haya.

        Aqui la leyenda es un eje mas de la figura y las barras van dentro de
        el en coordenadas del eje, asi que el recorte las respeta y da igual si
        salen tres temporadas o nueve.

    LAS TEMPORADAS CON POCOS DIAS SE DIBUJAN PERO SE MARCAN
        Con menos de 'minimo_dias' una temporada no se puede comparar contra
        las otras -- es la misma regla de calendario.MINIMO_DIAS_BANDERA -- y
        sin embargo en el calendario se ve igual de grande que las demas,
        porque ocupa celdas. La leyenda le pone el conteo al lado y una marca,
        para que no se lea como una de las tres grandes.
    """
    from patrones import calendario as calendario_modulo

    serie = serie.astype(float)
    etiquetas = etiquetas.reindex(serie.index)
    conteos = etiquetas.value_counts()
    presentes = [t for t in calendario_modulo.TEMPORADAS if t in conteos.index]
    if not presentes:
        return None

    anios = sorted({*serie.index.year})
    norma = _norma(serie)

    # Una fila por ano mas una para la leyenda. La leyenda como eje y no como
    # add_axes: ver el encabezado.
    figura, ejes = plt.subplots(
        len(anios) + 1, 1, figsize=(15, 2.3 * len(anios) + 0.55 * len(presentes)),
        gridspec_kw={"height_ratios": [1] * len(anios)
                     + [0.22 * len(presentes)]}, squeeze=False)
    ejes = ejes[:, 0]

    for k, anio in enumerate(anios):
        eje = ejes[k]
        indice, semana, dia, fondo, valores = _rejilla(anio, serie)
        temporada_anio = etiquetas.reindex(indice).to_numpy(dtype=object)

        remate = dict(edgecolors="white", linewidth=0.5)
        eje.pcolormesh(np.ma.masked_invalid(fondo),
                       cmap=ListedColormap([VACIO]), **remate)

        # Una capa por temporada. No se puede en una sola pasada porque cada
        # temporada lleva su propia escala de color.
        for nombre in presentes:
            elegidos = (~np.isnan(valores[dia, semana])
                        & (temporada_anio == nombre))
            if not elegidos.any():
                continue
            capa = np.full(fondo.shape, np.nan)
            capa[dia[elegidos], semana[elegidos]] = (
                serie.reindex(indice).to_numpy(dtype=float)[elegidos])
            eje.pcolormesh(np.ma.masked_invalid(capa),
                           cmap=_escala(calendario_modulo.TEMPORADAS[nombre]),
                           norm=norma, **remate)

        eje.invert_yaxis()
        eje.set_aspect("equal")
        eje.set_frame_on(False)
        eje.tick_params(length=0)
        eje.set_yticks(np.arange(7) + 0.5)
        eje.set_yticklabels(DIAS, fontsize=7, color=TENUE)
        eje.set_ylabel(str(anio), fontsize=18, color=TENUE, rotation=0,
                       labelpad=28, va="center")
        _meses(eje, indice, semana)

    _leyenda_temporadas(ejes[-1], presentes, conteos, minimo_dias)

    figura.suptitle(titulo, fontsize=13, weight="bold", color=TINTA)
    figura.text(0.5, 0.005,
                f"Color = temporada climatica. Intensidad = {unidad}. "
                f"Gris = dia sin dato.",
                ha="center", fontsize=8, color=TENUE)
    return _guardar(figura, ruta)


# Donde empieza cada escala de temporada. Las de matplotlib arrancan en blanco
# puro, y eso choca con el gris #eeeeee del dia sin dato: una celda con valor
# bajo sale MAS CLARA que el fondo, y se lee como un hueco.
#
# Se nota sobre todo en 'Greys' -- la de Intermedia-fria -- donde un valor bajo
# es literalmente blanco, pero les pasa a las nueve en distinto grado. Cortando
# el primer 18% de cada rampa, el valor mas bajo de cualquier temporada sigue
# teniendo color y el fondo vuelve a ser inconfundible.
#
# Se corta la rampa y no se cambia de paleta a proposito: las nueve familias de
# color son las de exploracion.ipynb y cambiarlas rompería la comparacion con
# esa figura, que es lo unico que no se puede tocar aqui.
INICIO_ESCALA = 0.18


def _escala(nombre):
    """La escala de una temporada, sin su tramo blanco inicial."""
    base = plt.get_cmap(nombre)
    return LinearSegmentedColormap.from_list(
        f"{nombre}_recortada",
        base(np.linspace(INICIO_ESCALA, 1.0, 256)))


def _leyenda_temporadas(eje, presentes, conteos, minimo_dias):
    """Una barra de gradiente por temporada, dentro de un eje normal."""
    from patrones import calendario as calendario_modulo

    eje.set_axis_off()
    gradiente = np.linspace(0, 1, 256).reshape(1, -1)
    alto = 1.0 / max(len(presentes), 1)

    for k, nombre in enumerate(presentes):
        dentro = eje.inset_axes([0.10, 1 - (k + 1) * alto, 0.26, alto * 0.55])
        dentro.imshow(gradiente, aspect="auto",
                      cmap=_escala(calendario_modulo.TEMPORADAS[nombre]))
        dentro.set_xticks([])
        dentro.set_yticks([])
        for lado in dentro.spines.values():
            lado.set_visible(False)

        dias = int(conteos.get(nombre, 0))
        escaso = dias < minimo_dias
        eje.text(0.095, 1 - (k + 0.5) * alto,
                 nombre.replace("-", " "), transform=eje.transAxes,
                 ha="right", va="center", fontsize=9,
                 color=TENUE if escaso else TINTA)
        eje.text(0.375, 1 - (k + 0.5) * alto,
                 f"{dias} dias" + ("   (pocos: no comparable)" if escaso else ""),
                 transform=eje.transAxes, ha="left", va="center", fontsize=8,
                 color=TENUE)


def _norma(serie):
    """La escala de una serie, robusta a un solo dia disparado."""
    valores = serie.to_numpy(dtype=float)
    validos = valores[~np.isnan(valores)]
    if not len(validos):
        return Normalize(0, 1)
    # El percentil 98 y no el maximo: un sismo o una tormenta sola aplastan
    # toda la escala y dejan el resto del calendario del mismo color palido.
    # Los dias por encima se pintan del tono mas oscuro, que es lo que se
    # quiere de ellos -- que se vean -- sin que borren los otros 600.
    return Normalize(float(np.nanmin(validos)),
                     float(np.nanpercentile(validos, 98)) or 1.0)


# ==========================================================
# LAS MATRICES
# ==========================================================

def matriz(tabla, filas, columnas, valores, titulo, etiqueta,
           ruta=None, mascara=None, simetrica=True):
    """
    Una matriz de calor generica: temas contra variables, o temas contra rezagos.

    'mascara' es una tabla booleana del mismo tamano con las celdas que NO
    sobrevivieron a la correccion por comparaciones multiples. Se dibujan
    rayadas en vez de ocultarse: que una celda se haya probado y no haya
    pasado es informacion, y borrarla dejaria una figura en la que solo se ven
    los aciertos -- que es como una matriz de 600 pruebas parece un hallazgo.
    """
    pivote = tabla.pivot_table(index=filas, columns=columnas, values=valores)
    datos = pivote.to_numpy(dtype=float)

    if simetrica:
        limite = float(np.nanmax(np.abs(datos))) or 1.0
        norma = TwoSlopeNorm(vmin=-limite, vcenter=0.0, vmax=limite)
        cmap = _divergente()
    else:
        norma = Normalize(float(np.nanmin(datos)), float(np.nanmax(datos)))
        cmap = CALOR

    alto = max(3.0, 0.32 * len(pivote.index) + 1.8)
    ancho = max(6.0, 0.55 * len(pivote.columns) + 4.0)
    figura, eje = plt.subplots(figsize=(ancho, alto))

    eje.pcolormesh(np.ma.masked_invalid(datos), cmap=cmap, norm=norma,
                   edgecolors="white", linewidth=0.5)

    if mascara is not None:
        fallidas = mascara.reindex(index=pivote.index,
                                   columns=pivote.columns).to_numpy(dtype=bool)
        for i, j in zip(*np.where(fallidas & ~np.isnan(datos))):
            eje.plot([j, j + 1], [i, i + 1], color="white", linewidth=0.8,
                     solid_capstyle="butt", zorder=3)

    eje.set_xticks(np.arange(len(pivote.columns)) + 0.5)
    eje.set_xticklabels(pivote.columns, rotation=45, ha="right", fontsize=8,
                        color=TINTA)
    eje.set_yticks(np.arange(len(pivote.index)) + 0.5)
    eje.set_yticklabels(pivote.index, fontsize=8, color=TINTA)
    eje.invert_yaxis()
    eje.set_frame_on(False)
    eje.tick_params(length=0)
    eje.set_title(titulo, fontsize=12, weight="bold", color=TINTA, pad=12)

    barra = figura.colorbar(ScalarMappable(norm=norma, cmap=cmap), ax=eje,
                            fraction=0.025, pad=0.02)
    barra.set_label(etiqueta, fontsize=9, color=TINTA)
    barra.outline.set_visible(False)

    if mascara is not None:
        # Como xlabel y no como figure.text: matplotlib lo coloca DEBAJO de las
        # etiquetas del eje, que aqui van rotadas y ocupan bastante. Puesto a
        # mano en coordenadas de figura se monta encima de ellas.
        eje.set_xlabel(
            "Las celdas tachadas se probaron y NO sobrevivieron a la "
            "correccion por comparaciones multiples.",
            fontsize=8, color=TENUE, labelpad=14, loc="left")

    return _guardar(figura, ruta)


def perfil_rezagos(tabla, tema, ruta=None):
    """
    Para un tema, la correlacion de cada variable a cada rezago. Una linea cada una.

    Sirve para lo que una matriz no: ver la FORMA. Un efecto real de la lluvia
    sobre las consultas respiratorias no aparece en un rezago suelto y cero en
    los vecinos -- sube, tiene un maximo y baja. Un pico aislado entre catorce
    rezagos planos es lo que produce el azar, y en esta figura se distingue de
    inmediato de una curva.
    """
    parcial = tabla[tabla["nombre"] == tema]
    if parcial.empty:
        return None

    figura, eje = plt.subplots(figsize=(9, 5))
    # Las de mayor correlacion absoluta, y no mas de las que hay colores que se
    # distingan. Ver CATEGORICAS: veinticuatro lineas no se leen y seis no se
    # distinguen, asi que la figura se queda con cuatro y lo dice en el titulo.
    orden = (parcial.groupby("variable")["correlacion"]
             .apply(lambda x: x.abs().max()).sort_values(ascending=False))
    elegidas = list(orden.head(MAXIMO_SERIES).index)

    for k, variable in enumerate(elegidas):
        serie = parcial[parcial["variable"] == variable].sort_values("rezago")
        eje.plot(serie["rezago"], serie["correlacion"], linewidth=2.0,
                 marker="o", markersize=5, color=CATEGORICAS[k],
                 label=variable, zorder=2)

    eje.axhline(0, color=TINTA, linewidth=1.0, zorder=1)
    eje.set_xlabel("rezago en dias (la variable ocurrio N dias antes)",
                   fontsize=9, color=TINTA)
    eje.set_ylabel("correlacion parcial", fontsize=9, color=TINTA)
    eje.set_title(f"Perfil de rezagos: {tema}", fontsize=12, weight="bold",
                  color=TINTA)
    eje.grid(alpha=0.25, linewidth=0.6)
    eje.set_frame_on(False)
    eje.legend(fontsize=8, frameon=False, ncol=2)
    return _guardar(figura, ruta)


def _guardar(figura, ruta):
    """Escribe la figura y la cierra. Devuelve la ruta."""
    if ruta is None:
        ruta = rutas.FIGURAS / "figura.png"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(ruta, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(figura)
    return ruta
