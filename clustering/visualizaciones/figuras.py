"""
Las figuras. Cada funcion devuelve un Figure y no escribe nada en disco.

QUE HAY AQUI Y EN QUE ORDEN CONVIENE MIRARLO
    reloj_semanal   hora x dia de la semana. LA MAS INFORMATIVA de todas.
    calendario      el ano dia a dia, como el de exploracion.ipynb.
    dominante       un solo calendario con la categoria que mando cada dia.
    composicion     como cambia la MEZCLA a lo largo del tiempo.
    polar           el ciclo de 24 horas dibujado como lo que es: un circulo.
    perfiles        ocho categorias comparadas de un vistazo.
    mes_anio        la estacionalidad anual.

POR QUE EL RELOJ SEMANAL VA PRIMERO
    Porque ahi esta la senal mas grande que tiene esta serie, y esta medido:
    el ciclo intradiario oscila 7,4 veces entre el pico de las 10 y el valle de
    las 4, mientras que el semanal oscila 1,57 entre lunes y domingo. El ciclo
    de la hora es 4,7 veces mas fuerte que el del dia de la semana, y hasta hoy
    no habia ni una figura que lo mostrara.

POR QUE MATPLOTLIB Y NO calplot NI plotly
    calplot hace el calendario en una linea, y no esta instalado en el entorno.
    El calendario son cuarenta lineas de matplotlib -- las que hay en
    exploracion.ipynb celda 18 -- y no vale una dependencia mas que ademas
    obliga a pasar por su formato de entrada.

    plotly necesita un navegador vivo. Estas figuras van a un PNG que se mete
    en un documento.

LO QUE SE PINTA EN GRIS NO ES UN CERO
    Gris = no hay dato, o no hay dato suficiente para que el numero signifique
    algo (ver datos.lift). Un cero es un color de la escala; el gris esta fuera
    de la escala a proposito, para que no se pueda confundir uno con otro.
"""

import numpy as np
import pandas as pd
from matplotlib import pyplot as plt
from matplotlib.colors import BoundaryNorm, ListedColormap, Normalize, TwoSlopeNorm

from clustering.visualizaciones import datos

GRIS = "#e8e8e8"
CMAP_VOLUMEN = "YlOrRd"
CMAP_LIFT = "RdBu_r"


def _mapa(nombre):
    mapa = plt.get_cmap(nombre).copy()
    mapa.set_bad(GRIS)
    return mapa


def _norma_lift(matriz):
    """
    Escala divergente centrada en 1,0, que es el valor que significa 'nada'.

    Sin centrar, un lift de 1,05 sale con color fuerte solo porque es el maximo
    de la figura, y se lee como un hallazgo. Centrada en 1, el blanco es
    literalmente 'aqui no pasa nada' y el color mide distancia a esa nada.
    """
    valores = matriz.to_numpy(dtype=float)
    finitos = valores[np.isfinite(valores)]
    if finitos.size == 0:
        return Normalize(0, 2)
    borde = max(abs(finitos.max() - 1.0), abs(1.0 - finitos.min()), 0.05)
    return TwoSlopeNorm(vmin=1 - borde, vcenter=1.0, vmax=1 + borde)


# ==========================================================
# 1. RELOJ SEMANAL -- hora x dia de la semana
# ==========================================================

def reloj_semanal(tabla, categoria=None, valor="auto", titulo=None):
    """
    Mapa de calor 7 x 24. La figura que mas rinde de este modulo.

    valor='media'  triages medios por casilla. Es lo que se dibuja cuando no
                   hay categorias: describe el ritmo del hospital.
    valor='lift'   indice de especializacion de una categoria. Es lo que se
                   dibuja en cuanto hay categorias, y responde a 'a que hora y
                   que dia se dispara ESTE motivo'.
    valor='auto'   'media' si hay una sola categoria, 'lift' si hay varias.

    Con una sola categoria el lift vale 1,0 en todas las casillas por
    definicion -- la categoria es el total -- asi que 'auto' existe para que
    nadie dibuje por error una figura uniformemente blanca y crea que el
    hospital no tiene ritmo.
    """
    marco = datos.marco(tabla)
    unica = marco["categoria"].nunique() == 1
    if valor == "auto":
        valor = "media" if unica else "lift"
    if valor == "lift" and unica:
        raise ValueError("con una sola categoria el lift es 1,0 en todas las "
                         "casillas; usa valor='media'")

    if valor == "media":
        matriz = _media_casilla(marco, "dow", "hora", categoria)
        tapada = pd.DataFrame(False, index=matriz.index, columns=matriz.columns)
        mapa, norma = _mapa(CMAP_VOLUMEN), Normalize(0, np.nanmax(matriz.to_numpy()))
        etiqueta = "triages por hora (media)"
    else:
        objetivo = categoria if categoria is not None else marco["categoria"].iloc[0]
        matriz, tapada = datos.rejilla(marco, "dow", "hora", objetivo)
        mapa, norma = _mapa(CMAP_LIFT), _norma_lift(matriz)
        etiqueta = "indice de especializacion (1,0 = lo normal)"

    matriz = matriz.reindex(index=range(7), columns=range(24))
    tapada = tapada.reindex(index=range(7), columns=range(24)).fillna(True)
    valores = np.ma.masked_array(matriz.to_numpy(dtype=float),
                                 mask=tapada.to_numpy() | matriz.isna().to_numpy())

    fig, ax = plt.subplots(figsize=(14, 4.2))
    imagen = ax.imshow(valores, aspect="auto", cmap=mapa, norm=norma)

    ax.set_xticks(range(24))
    ax.set_xticklabels([f"{h:02d}" for h in range(24)], fontsize=8)
    ax.set_yticks(range(7))
    ax.set_yticklabels(datos.DIAS, fontsize=9)
    ax.set_xlabel("hora del dia")
    ax.set_xticks(np.arange(-0.5, 24, 1), minor=True)
    ax.set_yticks(np.arange(-0.5, 7, 1), minor=True)
    ax.grid(which="minor", color="white", linewidth=0.8)
    ax.tick_params(which="minor", length=0)

    if titulo is None:
        sufijo = categoria if categoria is not None else "todos los triages"
        titulo = f"Hora x dia de la semana -- {sufijo}"
    ax.set_title(titulo, fontsize=12, pad=10)
    fig.colorbar(imagen, ax=ax, label=etiqueta, pad=0.015)
    fig.tight_layout()
    return fig


def _media_casilla(marco, filas, columnas, categoria=None):
    """
    Conteo medio por casilla, dividiendo por los dias que REALMENTE hubo.

    triage_horario.parquet es disperso: una casilla dia x hora sin ningun
    triage no tiene fila. Dividir por el numero de filas inflaria las horas de
    la madrugada, que son justo las que mas casillas vacias tienen. El
    denominador correcto son los dias distintos de ese dia de la semana en todo
    el rango, hubiera o no consultas a esa hora.
    """
    if categoria is not None:
        marco = marco[marco["categoria"] == categoria]
    suma = marco.pivot_table(index=filas, columns=columnas, values="n",
                             aggfunc="sum", fill_value=0)
    dias_por_fila = (marco.drop_duplicates("dia")
                     .groupby(filas, observed=True)["dia"].nunique())
    return suma.div(dias_por_fila, axis=0)


# ==========================================================
# 2. CALENDARIO -- el ano dia a dia
# ==========================================================

def calendario(serie, titulo="", etiqueta="", cmap=CMAP_VOLUMEN, norma=None):
    """
    Un panel por ano, siete filas (lunes arriba) y una columna por semana.

    Reimplementa calplot en matplotlib. Los dias nulos salen en gris y los dias
    que no pertenecen al ano no se pintan.
    """
    serie = serie.sort_index()
    anios = sorted({fecha.year for fecha in serie.index})
    mapa = _mapa(cmap)
    if norma is None:
        finitos = serie.to_numpy(dtype=float)
        finitos = finitos[np.isfinite(finitos)]
        norma = Normalize(finitos.min(), finitos.max()) if finitos.size else Normalize(0, 1)

    fig, ejes = plt.subplots(len(anios), 1, figsize=(15, 1.7 * len(anios)),
                             squeeze=False)
    for ax, anio in zip(ejes[:, 0], anios):
        dias = pd.date_range(f"{anio}-01-01", f"{anio}-12-31", freq="D")
        valores = serie.reindex(dias)
        desplazamiento = dias[0].weekday()
        columna = (np.arange(len(dias)) + desplazamiento) // 7
        fila = (np.arange(len(dias)) + desplazamiento) % 7

        rejilla = np.full((7, columna.max() + 1), np.nan)
        rejilla[fila, columna] = valores.to_numpy(dtype=float)
        ax.imshow(np.ma.masked_invalid(rejilla), aspect="auto", cmap=mapa,
                  norm=norma, interpolation="nearest")

        primeros = [d for d in dias if d.day == 1]
        ax.set_xticks([(dias.get_loc(d) + desplazamiento) // 7 for d in primeros])
        ax.set_xticklabels(datos.MESES, fontsize=8)
        ax.set_yticks([0, 2, 4, 6])
        ax.set_yticklabels(["Lun", "Mie", "Vie", "Dom"], fontsize=8)
        ax.set_ylabel(anio, fontsize=13, color="#777777", rotation=0,
                      labelpad=28, va="center")
        ax.tick_params(length=0)
        for lado in ax.spines.values():
            lado.set_visible(False)

    fig.suptitle(titulo, fontsize=13, y=0.995)
    fig.colorbar(plt.cm.ScalarMappable(norm=norma, cmap=mapa),
                 ax=ejes[:, 0].tolist(), label=etiqueta, pad=0.012, fraction=0.02)
    return fig


def calendario_dominante(tabla, titulo="Categoria dominante por dia"):
    """
    UN calendario para todas las categorias, en vez de uno por categoria.

    Cada dia lleva el color de la categoria que mas se salio de su cuota
    habitual ese dia. Los dias sin ninguna categoria fiable quedan en gris.

    Es la figura que contesta 'que predomino cada dia' sin multiplicar paneles,
    y la unica de este modulo que necesita al menos dos categorias.
    """
    if tabla["categoria"].nunique() < 2:
        raise ValueError("el calendario dominante necesita al menos dos "
                         "categorias; con una sola no hay nada que comparar")

    ganador = datos.dominante(tabla)
    clases = sorted(ganador["categoria"].unique())
    indice = {clase: i for i, clase in enumerate(clases)}
    codigo = ganador["categoria"].map(indice).astype(float)

    colores = plt.get_cmap("tab20")(np.linspace(0, 1, max(len(clases), 2)))
    mapa = ListedColormap(colores[:len(clases)])
    norma = BoundaryNorm(np.arange(-0.5, len(clases), 1), mapa.N)

    fig = calendario(codigo, titulo=titulo, cmap=mapa, norma=norma)
    barra = fig.axes[-1]
    barra.set_yticks(range(len(clases)))
    barra.set_yticklabels(clases, fontsize=8)
    barra.set_ylabel("")
    return fig


# ==========================================================
# 3. COMPOSICION -- como cambia la mezcla
# ==========================================================

def composicion(tabla, frecuencia="W", titulo=None):
    """
    Area apilada al 100%: la cuota de cada categoria a lo largo del tiempo.

    No muestra el volumen, muestra la MEZCLA. Es donde se veria una temporada
    respiratoria: la banda se ensancha aunque el total no se mueva -- que es
    exactamente el efecto que el volumen total diluye.
    """
    if tabla["categoria"].nunique() < 2:
        raise ValueError("la composicion necesita al menos dos categorias")

    ancho = (tabla.groupby(["dia", "categoria"], observed=True)["n"].sum()
             .unstack("categoria").fillna(0.0).sort_index()
             .resample(frecuencia).sum())
    cuota = ancho.div(ancho.sum(axis=1), axis=0)

    fig, ax = plt.subplots(figsize=(15, 5))
    ax.stackplot(cuota.index, cuota.to_numpy().T, labels=cuota.columns,
                 colors=plt.get_cmap("tab20")(np.linspace(0, 1, cuota.shape[1])))
    ax.set_ylim(0, 1)
    ax.set_xlim(cuota.index.min(), cuota.index.max())
    ax.set_ylabel("cuota del periodo")
    ax.set_title(titulo or f"Composicion por {frecuencia}", fontsize=12)
    ax.legend(loc="upper left", bbox_to_anchor=(1.005, 1), fontsize=8,
              frameon=False)
    fig.tight_layout()
    return fig


# ==========================================================
# 4. POLAR -- el ciclo de 24 horas como circulo
# ==========================================================

def polar(tabla, categorias=None, titulo="Perfil de 24 horas"):
    """
    El dia como un reloj. La hora es CIRCULAR y un eje recto lo rompe: en un
    eje normal las 23 y las 0 quedan en extremos opuestos cuando en realidad
    son consecutivas, y el valle de la madrugada aparece partido en dos.

    Con una sola categoria dibuja el conteo medio; con varias, el lift.
    """
    marco = datos.marco(tabla)
    unica = marco["categoria"].nunique() == 1
    angulos = np.arange(24) * 2 * np.pi / 24

    fig, ax = plt.subplots(figsize=(7.5, 7.5), subplot_kw={"projection": "polar"})
    if unica:
        serie = _media_casilla(marco, "categoria", "hora").iloc[0]
        serie = serie.reindex(range(24)).fillna(0.0)
        ax.plot(np.append(angulos, angulos[0]),
                np.append(serie.to_numpy(), serie.to_numpy()[0]),
                linewidth=2.2, color="#c23b22")
        ax.fill(np.append(angulos, angulos[0]),
                np.append(serie.to_numpy(), serie.to_numpy()[0]),
                alpha=0.22, color="#c23b22")
        ax.set_title(f"{titulo}\ntriages por hora (media)", fontsize=12, pad=22)
    else:
        medido = datos.lift(marco, ["hora"])
        clases = categorias or sorted(marco["categoria"].unique())
        for color, clase in zip(plt.get_cmap("tab10").colors, clases):
            fila = (medido[medido["categoria"] == clase]
                    .set_index("hora")["lift"].reindex(range(24)))
            ax.plot(np.append(angulos, angulos[0]),
                    np.append(fila.to_numpy(), fila.to_numpy()[0]),
                    linewidth=1.8, label=clase, color=color)
        ax.axhline(1.0, color="#999999", linewidth=1, linestyle="--")
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.08), fontsize=8,
                  frameon=False)
        ax.set_title(f"{titulo}\nindice de especializacion", fontsize=12, pad=22)

    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_xticks(angulos)
    ax.set_xticklabels([f"{h}" for h in range(24)], fontsize=8)
    fig.tight_layout()
    return fig


# ==========================================================
# 5. PERFILES -- varias categorias de un vistazo
# ==========================================================

def perfiles(tabla, eje="hora", titulo=None):
    """
    Un mini-panel por categoria, todos con el MISMO eje vertical.

    El eje compartido es lo que hace la figura: con ejes libres cada panel se
    autoescala, los ocho parecen igual de marcados y la comparacion -- que es
    para lo que existe la figura -- deja de ser posible.
    """
    marco = datos.marco(tabla)
    if marco["categoria"].nunique() < 2:
        raise ValueError("los perfiles comparan categorias; con una sola usa polar()")

    medido = datos.lift(marco, [eje])
    clases = sorted(marco["categoria"].unique())
    orden = sorted(marco[eje].unique())
    tope = medido["lift"].replace([np.inf, -np.inf], np.nan).max()

    columnas = min(4, len(clases))
    filas = int(np.ceil(len(clases) / columnas))
    fig, ejes = plt.subplots(filas, columnas, figsize=(3.6 * columnas, 2.5 * filas),
                             sharex=True, sharey=True, squeeze=False)
    for ax, clase in zip(ejes.flat, clases):
        fila = (medido[medido["categoria"] == clase]
                .set_index(eje)["lift"].reindex(orden))
        ax.axhline(1.0, color="#bbbbbb", linewidth=1, linestyle="--")
        ax.plot(orden, fila.to_numpy(), linewidth=1.8, color="#2b6cb0")
        ax.fill_between(orden, 1.0, fila.to_numpy(), alpha=0.2, color="#2b6cb0")
        ax.set_title(clase, fontsize=9)
        ax.set_ylim(0, max(tope * 1.05, 2.0))
    for ax in ejes.flat[len(clases):]:
        ax.set_visible(False)

    if eje == "dow":
        ejes[-1, 0].set_xticks(range(7))
        ejes[-1, 0].set_xticklabels([d[:3] for d in datos.DIAS], fontsize=8)
    fig.suptitle(titulo or f"Indice de especializacion por {eje}", fontsize=12)
    fig.tight_layout()
    return fig


# ==========================================================
# 6. MES x ANO -- la estacionalidad anual
# ==========================================================

def mes_anio(serie, titulo="Media diaria por mes", etiqueta="triages/dia"):
    """
    Matriz ano x mes de la MEDIA DIARIA, no de la suma.

    La suma mezcla dos cosas: cuanta gente vino y cuantos dias tiene el mes.
    Febrero saldria bajo todos los anos por tener 28 dias, y un ano incompleto
    -- 2026 llega a septiembre -- saldria vacio en los ultimos meses aunque los
    datos esten bien.
    """
    matriz = (serie.groupby([serie.index.year, serie.index.month]).mean()
              .unstack().reindex(columns=range(1, 13)))

    fig, ax = plt.subplots(figsize=(11, 0.55 * len(matriz) + 2.0))
    imagen = ax.imshow(np.ma.masked_invalid(matriz.to_numpy(dtype=float)),
                       aspect="auto", cmap=_mapa(CMAP_VOLUMEN))
    ax.set_xticks(range(12))
    ax.set_xticklabels(datos.MESES)
    ax.set_yticks(range(len(matriz)))
    ax.set_yticklabels(matriz.index)
    for i in range(matriz.shape[0]):
        for j in range(matriz.shape[1]):
            valor = matriz.to_numpy()[i, j]
            if np.isfinite(valor):
                ax.text(j, i, f"{valor:.0f}", ha="center", va="center",
                        fontsize=8, color="#333333")
    ax.set_title(titulo, fontsize=12)
    fig.colorbar(imagen, ax=ax, label=etiqueta, pad=0.015)
    fig.tight_layout()
    return fig
