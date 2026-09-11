"""
El dibujo: una corrida convertida en una figura que se puede leer.

COMO SE LEE ESTE MAPA, QUE NO ES OBVIO
    Los COLORES son el TEMA, no el grupo. Las POSICIONES vienen de una
    reduccion a 2 dimensiones hecha solo para poder dibujar, distinta de la de
    5 sobre la que se agrupo (ver agrupar.py).

    Se colorea por tema y no por grupo por dos razones. La de fondo: el tema es
    el nivel con el que se va a trabajar, y el mapa tiene que mostrar lo que se
    va a usar. La practica: con 130 grupos y una paleta de 20 colores, cada
    color se repetia seis veces y el mapa no se podia leer -- dos manchas del
    mismo color no querian decir nada. Con 20 temas hay un color por tema y
    volver a mirar el mapa sirve para algo.

    La consecuencia practica es que dos puntos pegados con colores distintos NO
    son un fallo: son dos vecindarios que en 2 dimensiones no tenian donde
    separarse. Y la distancia entre dos manchas lejanas no significa nada,
    porque UMAP conserva la vecindad local y no las distancias globales. El
    mapa sirve para ver la FORMA del corpus y para leer los textos por encima;
    lo que manda siempre es el numero de tema.

POR QUE EL TAMANO DEL PUNTO Y NO SOLO SU POSICION
    Cada punto es un texto DISTINTO, no una nota, porque es asi como se agrupa
    (ver corpus.py). Dibujados todos iguales, 'dolor abdominal' -- que puede
    representar 40 notas -- se veria igual que una frase que aparecio una sola
    vez, y el mapa mentiria sobre donde esta el volumen del corpus. El area del
    punto crece con las notas que representa.

POR QUE MATPLOTLIB Y NO PLOTLY
    Lo del notebook era plotly, que necesita un navegador y una celda. Esto
    tiene que abrirse como una ventana del escritorio y quedarse ahi
    refrescandose mientras el pipeline avanza, y para eso matplotlib es lo
    directo. El precio es que el hover hay que escribirlo a mano, que es lo que
    hace _conectar_hover.

EL PANEL DE LA DERECHA NO ES DECORACION
    El mapa dice donde estan los temas y el panel dice cuales importan, medidos
    en NOTAS. Son preguntas distintas: un tema puede ocupar media pantalla con
    muchos textos raros y pesar menos que una mancha pequena de frases
    repetidas. Los colores son los mismos en los dos lados, que es lo que
    permite pasar del nombre a la mancha.

    El panel lista TEMAS porque es la respuesta a "de que viene la gente al
    hospital", que es la pregunta del proyecto. Los grupos que componen cada
    tema estan en salidas/clusters.csv y en el globo del hover.
"""

import textwrap

import numpy as np

from clustering import rutas

# Cuantos temas se listan en el panel. Mas de esto no cabe legible, y el resto
# sigue estando en salidas/temas.csv, que es donde se mira en serio.
TEMAS_EN_PANEL = 20

COLOR_RUIDO = "#d7d7d7"

# El area del punto: un texto que aparece una vez y otro que aparece cuarenta
# no pueden dibujarse igual. Se topa porque sin tope las frases mas repetidas
# tapan a sus vecinas.
AREA_BASE = 9
AREA_POR_NOTA = 5
AREA_MAXIMA = 190


def color_de(tema):
    """
    Color estable de un tema: el mismo numero da el mismo color entre corridas,
    que es lo que permite comparar dos mapas de un vistazo.

    tab20 tiene exactamente 20 colores y el valor por defecto de temas.py son
    20 temas, asi que normalmente hay uno por tema y ninguno se repite. Si se
    piden mas con --temas, vuelven a repetirse; por eso el numero va escrito
    sobre la mancha, para que el color agrupe a ojo y el numero identifique.
    """
    import matplotlib.pyplot as plt

    if tema == -1:
        return COLOR_RUIDO
    return plt.get_cmap("tab20")(int(tema) % 20)


def dibujar(figura, corrida):
    """
    Vacia la figura y dibuja el mapa mas el panel de temas.

    Recibe la figura en vez de crearla para que el visor pueda refrescar la
    ventana que ya esta abierta: crear una nueva en cada refresco haria
    parpadear el mapa y perderia el zoom que el usuario haya hecho.
    """
    figura.clear()
    rejilla = figura.add_gridspec(1, 2, width_ratios=[2.35, 1],
                                  left=0.04, right=0.985,
                                  top=0.90, bottom=0.085, wspace=0.22)
    eje_mapa = figura.add_subplot(rejilla[0, 0])
    eje_panel = figura.add_subplot(rejilla[0, 1])

    tabla = corrida.tabla_temas()
    _dibujar_mapa(eje_mapa, corrida)
    _dibujar_panel(eje_panel, corrida, tabla)
    _titular(figura, corrida)
    figura.canvas.draw_idle()


def _dibujar_mapa(eje, corrida):
    """El scatter, las etiquetas de cada grupo y el hover."""
    datos = corrida.textos
    es_ruido = datos["tema"].to_numpy() == -1
    areas = np.minimum(
        AREA_BASE + AREA_POR_NOTA * (datos["n_notas"].to_numpy() - 1),
        AREA_MAXIMA)

    # El ruido va primero y por debajo: son el 30% de los puntos y dibujado
    # encima taparia los grupos, que es justo lo que se quiere ver.
    capas = []
    if es_ruido.any():
        indices = np.where(es_ruido)[0]
        capas.append((eje.scatter(
            datos["x"].to_numpy()[indices], datos["y"].to_numpy()[indices],
            s=areas[indices] * 0.6, c=COLOR_RUIDO, linewidths=0,
            alpha=0.55, zorder=1, label="ruido"), indices))

    if (~es_ruido).any():
        indices = np.where(~es_ruido)[0]
        colores = [color_de(t) for t in datos["tema"].to_numpy()[indices]]
        capas.append((eje.scatter(
            datos["x"].to_numpy()[indices], datos["y"].to_numpy()[indices],
            s=areas[indices], c=colores, linewidths=0.3,
            edgecolors="white", alpha=0.9, zorder=2), indices))

    _numerar_temas(eje, corrida)

    eje.set_xticks([])
    eje.set_yticks([])
    for lado in eje.spines.values():
        lado.set_color("#dddddd")
    eje.set_xlabel(
        "posiciones: UMAP 2D solo para dibujar  |  colores: TEMA  |  "
        "area: notas que representa el texto",
        fontsize=8, color="#777777")

    _conectar_hover(eje, corrida, capas)


def _numerar_temas(eje, corrida):
    """
    Escribe el numero de cada TEMA sobre su mancha.

    Antes numeraba los grupos y con 130 el mapa quedaba tapado de cifras. Los
    temas son veinte y caben.

    La posicion es la MEDIANA de sus puntos y no la media: un tema con dos
    textos sueltos lejos del resto -- que pasa, porque el agrupamiento es sobre
    otro espacio -- arrastraria la media hasta un hueco vacio y la etiqueta
    quedaria flotando lejos de la mancha que nombra. Con temas pasa mas que con
    grupos, porque un tema funde grupos que no tienen por que caer juntos en la
    proyeccion de 2 dimensiones.
    """
    datos = corrida.textos
    for tema in sorted(t for t in datos["tema"].unique() if t != -1):
        bloque = datos[datos["tema"] == tema]
        eje.annotate(
            str(int(tema)),
            (bloque["x"].median(), bloque["y"].median()),
            fontsize=9, fontweight="bold", color="#1a1a1a",
            ha="center", va="center", zorder=5,
            path_effects=_halo())


def _halo():
    """
    Un borde blanco alrededor del texto. Sin esto los numeros se pierden encima
    de las manchas de color y el mapa deja de poder leerse.
    """
    from matplotlib import patheffects
    return [patheffects.withStroke(linewidth=2.6, foreground="white")]


def _dibujar_panel(eje, corrida, tabla):
    """Los temas mas grandes en notas, con el nombre que salio del TF-IDF."""
    visibles = tabla[tabla["tema"] != -1].head(TEMAS_EN_PANEL)
    if visibles.empty:
        eje.text(0.5, 0.5, "Todavia no hay ningun grupo:\ntodo cayo como ruido.",
                 ha="center", va="center", fontsize=10, color="#666666")
        eje.set_axis_off()
        return

    # invertido para que el mas grande quede arriba, que es donde se mira
    visibles = visibles.iloc[::-1]
    posiciones = np.arange(len(visibles))
    eje.barh(posiciones, visibles["notas"],
             color=[color_de(t) for t in visibles["tema"]],
             edgecolor="white", linewidth=0.5)

    eje.set_yticks(posiciones)
    eje.set_yticklabels(
        [f"{int(t)}. {n}" for t, n in zip(visibles["tema"], visibles["nombre"])],
        fontsize=8)
    eje.set_xlabel("notas que representa el tema", fontsize=8.5)
    eje.set_title(
        f"Temas mas grandes  ({len(tabla[tabla['tema'] != -1])} en total)",
        fontsize=10, fontweight="bold", loc="left")
    eje.grid(axis="x", alpha=0.25, linewidth=0.6)
    eje.set_axisbelow(True)
    eje.tick_params(axis="x", labelsize=8)
    for lado in ("top", "right"):
        eje.spines[lado].set_visible(False)

    # Espacio a la derecha para la cifra que va al final de cada barra: sin
    # esto la del grupo mas grande -- que es la que primero se mira -- queda
    # cortada contra el borde del panel.
    eje.set_xlim(0, visibles["notas"].max() * 1.22)

    # notas y cuantos grupos se fundieron: '412n / 7g' dice a la vez cuanto
    # pesa el tema y si es una fusion de verdad o un grupo que quedo solo.
    for y, (notas, grupos) in enumerate(zip(visibles["notas"],
                                            visibles["grupos"])):
        eje.text(notas, y, f" {int(notas):,}n / {int(grupos)}g",
                 va="center", fontsize=7, color="#555555")


def _titular(figura, corrida):
    """Las cifras de la corrida, arriba. Es el resumen que se lee primero."""
    m = corrida.metricas
    figura.suptitle(
        f"Motivos de triage agrupados  |  {m['textos']:,} textos distintos  |  "
        f"{m['notas']:,} notas  |  {m.get('temas', 0):,} temas  |  "
        f"{m['clusters']:,} grupos  |  "
        f"ruido {m['ruido_textos']:.0%} de los textos "
        f"({m['ruido_notas']:.0%} de las notas)",
        fontsize=12, fontweight="bold", y=0.975)
    figura.text(
        0.04, 0.935,
        "Pasa el cursor por un punto para leer el motivo. Cada punto es un "
        "texto distinto, no una nota. El ruido (gris) es lo que no se parece "
        "a nada: no es un fallo.",
        fontsize=8.5, color="#666666", ha="left")


# ==========================================================
# HOVER
# ==========================================================

def _conectar_hover(eje, corrida, capas):
    """
    Muestra el texto real del punto que esta debajo del cursor.

    Es la parte que hace util el mapa. Sin esto son manchas de color: la unica
    forma de juzgar si un cluster tiene sentido es leer las frases que cayeron
    dentro, y en un scatter de 2.000 puntos eso solo se puede hacer apuntando.

    LO PRIMERO QUE HACE ES DESCONECTAR EL HOVER ANTERIOR, y no es opcional.
    figura.clear() borra los ejes pero NO toca los callbacks del canvas, asi
    que el visor -- que redibuja cada vez que el pipeline agrega embeddings --
    iria acumulando un handler por refresco. Cada uno sigue apuntando a los
    ejes y al DataFrame de su corrida, que ya no estan dibujados: se filtra
    memoria, y cada movimiento del raton dispara N redibujados en vez de uno.
    """
    figura = eje.get_figure()
    datos = corrida.textos

    anterior = getattr(figura, "_clustering_hover", None)
    if anterior is not None:
        figura.canvas.mpl_disconnect(anterior)

    globo = eje.annotate(
        "", xy=(0, 0), xytext=(16, 16), textcoords="offset points",
        bbox=dict(boxstyle="round,pad=0.55", facecolor="#fffef0",
                  edgecolor="#9a9a9a", linewidth=0.8, alpha=0.98),
        fontsize=8.5, zorder=30, annotation_clip=False)
    globo.set_visible(False)

    def contenido(fila):
        """
        Los DOS niveles en el globo, el tema arriba y el grupo debajo.

        El color de la mancha es el tema, asi que apuntando solo se sabe eso;
        y la pregunta que sigue -- 'vale, pero por que esta ESTA frase en ESE
        tema' -- se responde con el grupo, que es el que la puso ahi. Sin los
        dos, auditar la fusion obliga a ir al CSV.
        """
        registro = datos.iloc[fila]
        cabecera = corrida.nombre_tema_de(int(registro["tema"]))
        grupo = corrida.nombre_de(int(registro["cluster"]))
        cuerpo = textwrap.fill(" ".join(str(registro["texto"]).split()), 74)
        pie = (f"{int(registro['n_notas'])} nota(s)"
               f"  |  confianza {registro['confianza']:.2f}")
        return (f"TEMA {cabecera}\n     grupo {grupo}\n"
                f"{'-' * 34}\n{cuerpo}\n{pie}")

    def mover(evento):
        if evento.inaxes is not eje:
            if globo.get_visible():
                globo.set_visible(False)
                figura.canvas.draw_idle()
            return

        for coleccion, indices in reversed(capas):
            encontrado, detalle = coleccion.contains(evento)
            if not encontrado:
                continue
            fila = int(indices[detalle["ind"][0]])
            globo.xy = (datos["x"].iloc[fila], datos["y"].iloc[fila])
            globo.set_text(contenido(fila))
            globo.set_visible(True)
            figura.canvas.draw_idle()
            return

        if globo.get_visible():
            globo.set_visible(False)
            figura.canvas.draw_idle()

    figura._clustering_hover = figura.canvas.mpl_connect(
        "motion_notify_event", mover)


def guardar(figura):
    """Escribe el mapa en salidas/mapa.png, para poder pegarlo en el informe."""
    figura.savefig(rutas.MAPA, dpi=140, facecolor="white")
    return rutas.MAPA
