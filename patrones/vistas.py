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


# ==========================================================
# EL PANORAMA: TODO EL HISTORICO EN UN EJE DE TIEMPO COMPARTIDO
# ==========================================================
#
# Las figuras de arriba responden "¿como se reparte este tema en el calendario?".
# Esta responde otra: "¿que estaba pasando a la vez?". Son cuatro paneles
# apilados que comparten el eje x, de modo que una coincidencia se ve como una
# COLUMNA VERTICAL -- la lluvia sube, la familia sube, en la misma abscisa.
#
# Un calendario no puede mostrar eso porque cada figura tiene su propia rejilla
# y el ojo no sostiene dos rejillas a la vez. Una correlacion tampoco, porque
# promedia los veinte meses y una racha de tres semanas se diluye.
#
# POR QUE LA LINEA GRUESA ES UNA MEDIA MOVIL Y LA FINA ES EL DATO
#     La proporcion semanal de una familia de 30 notas tiene un error de
#     muestreo de varios puntos: dibujada sola, la linea tiembla tanto que
#     cualquier forma que se le vea es imaginada. Va el dato crudo en fino y
#     transparente -- para que se vea cuanto tiembla, que es informacion -- y
#     encima la media movil de tres semanas en grueso, que es lo que se lee.
#
#     La media movil NO se usa para calcular nada. Suavizar y despues
#     correlacionar infla las correlaciones porque mete autocorrelacion que no
#     estaba. Los numeros salen de panorama.rezagos(), sobre la serie sin
#     suavizar y pre-blanqueada.

VENTANA_SUAVE = 3          # semanas de la media movil que se dibuja en grueso
ALFA_FONDO = 0.22          # el tono de las bandas de temporada, y el de su leyenda
SIN_CLIMA = "#f2f2f2"      # el tramo final que clima_unificado.csv no alcanza


def _tramos(etiquetas):
    """Los tramos seguidos con la misma etiqueta: [(desde, hasta, etiqueta)]."""
    etiquetas = etiquetas.dropna()
    if etiquetas.empty:
        return []
    cambio = (etiquetas != etiquetas.shift()).cumsum()
    tramos = []
    for _, parte in etiquetas.groupby(cambio):
        tramos.append((parte.index[0], parte.index[-1], parte.iloc[0]))
    return tramos


def _fondo_temporadas(ejes, etiquetas):
    """Pinta las temporadas de fondo en todos los ejes. Devuelve las presentes."""
    presentes = []
    for desde, hasta, nombre in _tramos(etiquetas):
        from patrones import calendario as calendario_modulo
        escala = calendario_modulo.TEMPORADAS.get(nombre)
        if escala is None:
            continue
        color = _escala(escala)(0.28)
        for eje in ejes:
            eje.axvspan(desde, hasta, color=color, alpha=ALFA_FONDO,
                        lw=0, zorder=0)
        if nombre not in presentes:
            presentes.append(nombre)
    return presentes


def _hueco_sin_clima(ejes, diario, etiqueta=True):
    """Marca en gris el tramo final sin clima. No se interpola: se ensena."""
    con_clima = diario["precip_consenso_mm"].dropna()
    if con_clima.empty:
        return None
    ultimo = con_clima.index.max()
    fin = diario.index.max()
    if ultimo >= fin:
        return None
    for eje in ejes:
        eje.axvspan(ultimo, fin, color=SIN_CLIMA, zorder=0.5)
        eje.axvline(ultimo, color=TENUE, lw=0.8, ls=":", zorder=1)
    if etiqueta:
        ejes[0].text(ultimo, ejes[0].get_ylim()[1], " sin clima ",
                     fontsize=7, color=TENUE, va="top", ha="left")
    return ultimo


def _etiqueta_familia(familia, asignacion, estabilidad, maximo_temas=3):
    """El texto de la leyenda: los temas mayores y el aviso si no es estable."""
    miembros = asignacion[asignacion["familia"] == familia]
    nombres = list(miembros.sort_values("notas", ascending=False)["nombre"])
    corto = " · ".join(n.split()[0] for n in nombres[:maximo_temas])
    if len(nombres) > maximo_temas:
        corto += f" +{len(nombres) - maximo_temas}"
    jaccard = estabilidad.get(familia, float("nan"))
    aviso = ""
    if not np.isnan(jaccard):
        if jaccard <= 0.50:
            aviso = "  [INESTABLE]"
        elif jaccard < 0.75:
            aviso = "  [dudosa]"
    return f"F{familia} · {corto}{aviso}"


def panorama(proporcion, diario, asignacion, estabilidad, ruta=None,
             titulo="Motivos de triage y clima, 2025-2026"):
    """
    Los cuatro paneles alineados. Devuelve la figura (no la cierra).

    proporcion  semana x familia, en porcentaje de las notas procesadas
    diario      indexado por fecha, con el clima y la columna temporada
    """
    figura = plt.figure(figsize=(16, 10.5))
    rejilla = figura.add_gridspec(
        5, 1, height_ratios=[1.15, 0.85, 2.7, 1.0, 0.5], hspace=0.16)

    lluvia = figura.add_subplot(rejilla[0])
    aire = figura.add_subplot(rejilla[1], sharex=lluvia)
    motivos = figura.add_subplot(rejilla[2], sharex=lluvia)
    volumen = figura.add_subplot(rejilla[3], sharex=lluvia)
    pie = figura.add_subplot(rejilla[4])

    ejes = [lluvia, aire, motivos, volumen]

    # ---- el fondo: temporadas climaticas y el hueco sin clima --------------
    presentes = []
    if "temporada" in diario.columns:
        presentes = _fondo_temporadas(ejes, diario["temporada"])

    # ---- 1. la lluvia -----------------------------------------------------
    lluvia.bar(diario.index, diario["precip_consenso_mm"], width=1.0,
               color="#9dc3e0", lw=0, zorder=2, label="lluvia del dia (mm)")
    if "precip_7d" in diario.columns:
        lluvia.plot(diario.index, diario["precip_7d"] / 7.0, color=BAJA,
                    lw=1.6, zorder=3, label="media de 7 dias (mm/dia)")
    lluvia.set_ylabel("lluvia\n(mm/dia)", fontsize=9, color=TINTA)
    lluvia.legend(loc="upper left", fontsize=8, frameon=False, ncol=2)

    # ---- 2. humedad y temperatura ----------------------------------------
    # La temperatura va aqui aunque no explique nada, y va DIBUJADA para que se
    # vea por que no explica nada: seis grados de rango en veinte meses. Es mas
    # convincente verla plana que leer que lo esta.
    def _media_7d(columna):
        # calendario_diario.parquet trae 'precip_7d' ya calculada pero no las
        # de humedad y temperatura, asi que se calculan aqui. La ventana es la
        # misma -- 7 dias -- para que los tres paneles se lean con el mismo
        # grado de suavizado y una racha se vea igual de ancha en los tres.
        if columna not in diario.columns:
            return None
        return diario[columna].astype(float).rolling(7, min_periods=4).mean()

    humedad = _media_7d("humedad_consenso")
    if humedad is not None:
        aire.plot(diario.index, humedad, color="#2e7d32", lw=1.4, zorder=3)
        aire.set_ylabel("humedad\n(%, media 7d)", fontsize=9, color="#2e7d32")
    gemelo = aire.twinx()
    temperatura = _media_7d("temp_media_consenso")
    if temperatura is not None:
        gemelo.plot(diario.index, temperatura, color="#b8860b", lw=1.4,
                    zorder=3)
        gemelo.set_ylabel("temp (C,\nmedia 7d)", fontsize=9, color="#b8860b")
        gemelo.tick_params(axis="y", labelsize=8, colors="#b8860b")
        # La escala de la temperatura se abre a +-2,5 C a proposito. Dejada en
        # automatico, matplotlib estira un rango de dos grados hasta llenar el
        # panel y la linea parece una montana rusa. Con un rango fijo y ancho
        # se ve lo que de verdad hace: casi nada. Esa es la informacion, y es
        # la razon por la que la temperatura no va a explicar ningun pico.
        if float(temperatura.max() - temperatura.min()) < 4.0:
            centro = float(temperatura.mean())
            gemelo.set_ylim(centro - 2.5, centro + 2.5)
        for lado in ("top", "left", "bottom"):
            gemelo.spines[lado].set_visible(False)
    aire.tick_params(axis="y", labelsize=8, colors="#2e7d32")

    # ---- 3. las familias de motivos --------------------------------------
    suave = proporcion.rolling(VENTANA_SUAVE, min_periods=1, center=True).mean()
    for i, familia in enumerate(sorted(proporcion.columns)):
        color = CATEGORICAS[i % len(CATEGORICAS)]
        jaccard = estabilidad.get(familia, float("nan"))
        estilo = ":" if (not np.isnan(jaccard) and jaccard <= 0.50) else "-"
        motivos.plot(proporcion.index, proporcion[familia], color=color,
                     lw=0.8, alpha=0.30, zorder=2)
        motivos.plot(suave.index, suave[familia], color=color, lw=2.4,
                     ls=estilo, zorder=3,
                     label=_etiqueta_familia(familia, asignacion, estabilidad))
    # ESCALA LOGARITMICA, Y NO ES UN ADORNO
    #     F0 vale la mitad de todas las notas y F3 vale el 5%. En escala lineal
    #     la primera se lleva el panel entero y las otras tres quedan aplastadas
    #     contra el eje, donde un movimiento del 40% de su propio tamano no se
    #     ve. En logaritmica la MISMA distancia vertical significa el mismo
    #     cambio relativo en las cuatro, que es justo lo que se viene a
    #     comparar, y es ademas la escala coherente con el CLR con el que se
    #     agruparon.
    #
    #     Precio: una semana en cero no se puede dibujar. Con estas cuentas le
    #     pasa a las familias chicas, y esas semanas salen como un corte en la
    #     linea fina. Es visible y es correcto: cero notas no es 'casi cero'.
    motivos.set_yscale("log")
    motivos.set_yticks([1, 2, 5, 10, 20, 50])
    motivos.get_yaxis().set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}%"))
    motivos.set_ylabel("% de las notas procesadas de esa semana\n"
                       "(escala logaritmica)", fontsize=9, color=TINTA)
    motivos.legend(loc="lower left", fontsize=8.5, frameon=False, ncol=2)

    # ---- 4. el denominador, que es lo que puede fabricar el patron --------
    # Va en la figura y no en una nota al pie a proposito. Si la cobertura del
    # motivo cae justo donde una familia sube, lo que se esta viendo es el
    # denominador y no el hospital, y eso tiene que poder verse de un vistazo.
    # POR SEMANA Y NO POR DIA, AL REVES QUE LOS DOS PANELES DE ARRIBA
    #     Dia a dia esto son 615 barras y una linea que recorre el ciclo
    #     semanal entero cada siete pixeles: no se lee nada. Y el ciclo semanal
    #     no es lo que este panel viene a ensenar -- viene a ensenar la DERIVA,
    #     que es de meses. Agregando por semana el ciclo se va y la deriva queda
    #     a la vista, que es lo unico que se le pide.
    #     Y se cortan las semanas incompletas, igual que en panorama.semanal().
    #     La ventana termina un lunes, asi que la ultima semana tiene UN dia:
    #     dibujada, su barra es un munon y su cobertura salta a donde caiga ese
    #     dia -- en esta ventana, al 100%. Una deriva de nueve puntos por ano
    #     leida con un salto de veinte al final no se lee.
    semanalmente = dict(rule="W-MON", label="left", closed="left")

    def _por_semana(columna, minimo_dias=5):
        agrupado = diario[columna].resample(**semanalmente)
        return agrupado.sum()[agrupado.count() >= minimo_dias]

    if "procesadas" in diario.columns:
        semanas = _por_semana("procesadas")
        volumen.bar(semanas.index, semanas, width=6.0, color="#cfcfcf", lw=0,
                    zorder=2, label="notas procesadas por semana")
    if {"notas_con_motivo", "triages"} <= set(diario.columns):
        # La cobertura como cociente de las SUMAS de la semana. El promedio de
        # los cocientes diarios le daria el mismo peso a un domingo de veinte
        # triages que a un lunes de doscientos.
        con_motivo = _por_semana("notas_con_motivo")
        triages = _por_semana("triages").reindex(con_motivo.index)
        cobertura = volumen.twinx()
        cobertura.plot(con_motivo.index,
                       (con_motivo / triages.replace(0, np.nan)) * 100,
                       color=SUBE, lw=1.8, zorder=3,
                       label="triages con motivo escrito (%)")
        cobertura.set_ylabel("cobertura del\nmotivo (%)", fontsize=9,
                             color=SUBE)
        cobertura.tick_params(axis="y", labelsize=8, colors=SUBE)
        for lado in ("top", "left", "bottom"):
            cobertura.spines[lado].set_visible(False)
        cobertura.legend(loc="lower left", fontsize=8, frameon=False)
    volumen.set_ylabel("notas\nprocesadas", fontsize=9, color=TINTA)
    volumen.legend(loc="upper left", fontsize=8, frameon=False)

    _hueco_sin_clima(ejes, diario)

    for eje in ejes:
        eje.margins(x=0.005)
        eje.grid(axis="y", color="#f0f0f0", lw=0.8, zorder=0)
        for lado in ("top", "right", "left"):
            eje.spines[lado].set_visible(False)
        eje.tick_params(axis="y", labelsize=8)
    for eje in ejes[:-1]:
        eje.tick_params(axis="x", labelbottom=False, length=0)
    volumen.tick_params(axis="x", labelsize=9, colors=TINTA)
    volumen.set_xlim(diario.index.min(), diario.index.max())

    # ---- el pie: la leyenda de temporadas --------------------------------
    pie.set_axis_off()
    if presentes:
        from patrones import calendario as calendario_modulo
        ancho = 1.0 / max(len(presentes), 1)
        for i, nombre in enumerate(presentes):
            escala = calendario_modulo.TEMPORADAS.get(nombre, "Greys")
            pie.add_patch(plt.Rectangle((i * ancho + 0.01, 0.45),
                                        ancho * 0.25, 0.30,
                                        color=_escala(escala)(0.28),
                                        alpha=ALFA_FONDO,
                                        transform=pie.transAxes,
                                        clip_on=False))
            pie.text(i * ancho + 0.01 + ancho * 0.28, 0.60, nombre,
                     fontsize=8.5, color=TINTA, va="center",
                     transform=pie.transAxes)
        pie.text(0.01, 0.05,
                 "Fondo: temporada climatica (lluvia en terciles historicos x "
                 "temperatura). Gris al final: dias sin clima, no interpolados.",
                 fontsize=7.5, color=TENUE, transform=pie.transAxes)

    figura.suptitle(titulo, fontsize=14, color=TINTA, y=0.955)
    figura.text(0.5, 0.925,
                "Linea fina: la semana. Linea gruesa: media movil de "
                f"{VENTANA_SUAVE} semanas, solo para leer -- los numeros salen "
                "de la serie sin suavizar.",
                fontsize=8.5, color=TENUE, ha="center")

    if ruta is not None:
        _guardar_sin_cerrar(figura, ruta)
    return figura


def mapa_familias(correlacion, orden, asignacion, estabilidad, ruta=None):
    """
    La matriz tema x tema reordenada por familia, con los bloques marcados.

    Es la figura que justifica -- o no -- las lineas del panorama. Si los
    cuadrados de la diagonal no se ven mas rojos que el resto de la matriz, las
    familias no existen y las lineas del panorama son cuatro promedios
    arbitrarios. Se mira esta ANTES que el panorama, no despues.

    LA BARRA DE COLOR VA EN SU PROPIA COLUMNA DE LA REJILLA
        Pedida con ax=, matplotlib le roba sitio al eje de la matriz y la
        coloca encima de la columna de texto de la derecha. Con una columna
        propia -- estrecha, entre las dos -- cada cosa tiene su ancho y no hay
        nada que se solape.
    """
    matriz = correlacion[np.ix_(orden, orden)]
    nombres = list(asignacion["nombre"])
    familias_col = list(asignacion["familia"])
    n = len(nombres)

    figura = plt.figure(figsize=(14.5, 9.5))
    rejilla = figura.add_gridspec(1, 3, width_ratios=[3.0, 0.10, 1.5],
                                  wspace=0.06)
    eje = figura.add_subplot(rejilla[0])
    eje_barra = figura.add_subplot(rejilla[1])
    lado = figura.add_subplot(rejilla[2])

    # El limite de la escala sale del mayor valor FUERA de la diagonal. Con la
    # diagonal dentro, el maximo seria siempre 1,0 -- la correlacion de cada
    # tema consigo mismo -- y la matriz entera saldria de un gris uniforme.
    fuera = matriz - np.eye(n)
    limite = max(float(np.nanmax(np.abs(fuera))), 0.05)
    imagen = eje.imshow(matriz, cmap=_divergente(),
                        norm=TwoSlopeNorm(vmin=-limite, vcenter=0.0,
                                          vmax=limite))

    eje.set_xticks(range(n))
    eje.set_yticks(range(n))
    eje.set_xticklabels(nombres, rotation=90, fontsize=7, color=TINTA)
    eje.set_yticklabels(nombres, fontsize=7, color=TINTA)
    eje.tick_params(length=0)
    for lado_marco in ("top", "right", "bottom", "left"):
        eje.spines[lado_marco].set_visible(False)

    # El recuadro de cada familia sobre la diagonal.
    inicio_bloque = 0
    for i, familia in enumerate(sorted(set(familias_col))):
        cuantos = familias_col.count(familia)
        color = CATEGORICAS[i % len(CATEGORICAS)]
        eje.add_patch(plt.Rectangle((inicio_bloque - 0.5, inicio_bloque - 0.5),
                                    cuantos, cuantos, fill=False,
                                    edgecolor=color, lw=2.2))
        inicio_bloque += cuantos

    barra = figura.colorbar(imagen, cax=eje_barra)
    barra.ax.tick_params(labelsize=8)
    # Las cifras a la IZQUIERDA de la barra: a la derecha caen encima de los
    # titulos de familia de la columna de texto.
    barra.ax.yaxis.set_ticks_position("left")
    # El rotulo va como titulo de la barra y no como set_label: en una columna
    # estrecha, set_label lo escribe en vertical a la DERECHA, o sea encima de
    # la lista de temas.
    eje_barra.set_title("correlacion\nentre series\nsemanales\n(CLR)",
                        fontsize=7.5, color=TENUE, pad=8)

    eje.set_title("Que motivos se mueven juntos", fontsize=13, color=TINTA,
                  pad=12)

    # ---- el lado derecho: quien esta en cada familia y si es de fiar ------
    #
    # El paso vertical se calcula y no se fija: con 30 temas y cuatro familias
    # son mas de cuarenta renglones, y un paso constante los saca de la figura
    # por abajo, encima de la nota al pie. Se cuenta cuantos hay y se reparte
    # el alto entre ellos.
    lado.set_axis_off()
    familias_unicas = sorted(set(familias_col))
    renglones = len(familias_unicas) * 3 + n + 1
    paso = min(0.026, 0.80 / max(renglones, 1))

    y = 0.99
    lado.text(0.0, y, "LAS FAMILIAS", fontsize=10, color=TINTA, va="top",
              weight="bold")
    y -= paso * 2.0

    for i, familia in enumerate(familias_unicas):
        color = CATEGORICAS[i % len(CATEGORICAS)]
        miembros = asignacion[asignacion["familia"] == familia]
        jaccard = estabilidad.get(familia, float("nan"))
        veredicto = ("valida" if jaccard >= 0.75 else
                     "DISUELTA" if jaccard <= 0.50 else "dudosa")
        lado.text(0.0, y,
                  f"F{familia}  ·  {len(miembros)} temas  ·  "
                  f"{int(miembros['notas'].sum()):,} notas",
                  fontsize=9, color=color, va="top", weight="bold")
        y -= paso
        lado.text(0.0, y, f"estabilidad Jaccard {jaccard:.2f} — {veredicto}",
                  fontsize=8, color=TENUE, va="top")
        y -= paso
        for fila in miembros.sort_values("notas", ascending=False).itertuples():
            lado.text(0.03, y, f"{fila.nombre}  ({int(fila.notas)})",
                      fontsize=7.5, color=TINTA, va="top")
            y -= paso
        y -= paso * 0.6

    lado.text(0.0, 0.0,
              "Jaccard: se reagrupa con el 80% de las semanas, 200 veces.\n"
              ">=0,75 la familia reaparece; <=0,50 es una particion del ruido\n"
              "y su linea en el panorama no se interpreta.",
              fontsize=7.5, color=TENUE, va="bottom")

    if ruta is not None:
        _guardar_sin_cerrar(figura, ruta)
    return figura


def perfil_familias(perfil, asignacion, estabilidad, ruta=None,
                    variable="lluvia (media de 7 dias)"):
    """
    Correlacion de cada familia con la lluvia a cada rezago, tras pre-blanqueo.

    NO SON PRUEBAS. Catorce rezagos por cuatro familias son 56 cifras sin
    correccion por multiplicidad: que la mayor ronde p=0,05 es exactamente lo
    que pasa cuando no hay nada. Lo que se lee es la FORMA -- sube, hace maximo
    y baja -- porque un efecto real no aparece y desaparece de un dia al otro.
    """
    if perfil is None or perfil.empty:
        return None

    figura, eje = plt.subplots(figsize=(11, 5.6))
    for i, (familia, parte) in enumerate(perfil.groupby("familia")):
        color = CATEGORICAS[i % len(CATEGORICAS)]
        jaccard = estabilidad.get(familia, float("nan"))
        estilo = ":" if (not np.isnan(jaccard) and jaccard <= 0.50) else "-"
        parte = parte.sort_values("rezago_dias")
        eje.plot(parte["rezago_dias"], parte["correlacion"], color=color,
                 lw=2.0, ls=estilo, marker="o", ms=3.5,
                 label=_etiqueta_familia(familia, asignacion, estabilidad))

    eje.axhline(0, color=TENUE, lw=1.0)
    eje.set_xlabel(f"rezago en dias: la {variable} de hace N dias", fontsize=9,
                   color=TINTA)
    eje.set_ylabel("correlacion tras pre-blanqueo AR(7)", fontsize=9,
                   color=TINTA)
    eje.set_title("Forma de la relacion con la lluvia, por familia",
                  fontsize=12.5, color=TINTA, pad=10)
    eje.legend(fontsize=8.5, frameon=False, loc="best")
    eje.grid(axis="y", color="#f0f0f0", lw=0.8)
    for lado in ("top", "right"):
        eje.spines[lado].set_visible(False)

    figura.text(0.5, -0.02,
                "Sin correccion por multiplicidad: esto NO es una prueba. La "
                "prueba es 'python -m patrones --modelar', y lo que se pruebe "
                "se escribe antes en datos/variables.csv.",
                fontsize=7.5, color=TENUE, ha="center")

    if ruta is not None:
        _guardar_sin_cerrar(figura, ruta)
    return figura


def _guardar_sin_cerrar(figura, ruta):
    """
    Como _guardar pero deja la figura viva, porque puede haber que mostrarla.

    _guardar cierra a proposito: las corridas completas dibujan decenas de
    calendarios y dejarlos abiertos se come la memoria. Aqui son tres figuras y
    la siguiente linea puede ser un plt.show().
    """
    ruta.parent.mkdir(parents=True, exist_ok=True)
    figura.savefig(ruta, dpi=140, bbox_inches="tight", facecolor="white")
    return ruta


def abrir_ventana():
    """
    Cambia al backend interactivo. Hay que llamarla ANTES de crear las figuras.

    Este modulo fija 'Agg' al importarse porque su trabajo normal es escribir
    archivos y en un servidor no hay pantalla que abrir. Para mirar el panorama
    hace falta lo contrario, y matplotlib solo deja cambiar de backend mientras
    no haya figuras vivas -- de ahi el orden.

    Devuelve True si se consiguio. Si no hay tkinter -- un Python compilado sin
    el, o una sesion sin escritorio -- se queda en Agg y se dice, en vez de
    reventar despues de haber calculado todo.
    """
    try:
        matplotlib.use("TkAgg", force=True)
        return True
    except Exception as error:
        print(f"  no se pudo abrir ventana ({error}); quedan los PNG")
        return False


def mostrar():
    """Bloquea mostrando las figuras abiertas. Solo tras abrir_ventana()."""
    plt.show()
