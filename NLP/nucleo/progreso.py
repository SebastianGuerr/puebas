"""
Barra de progreso para corridas largas.

POR QUE ESTA AQUI Y NO EN procesar.py
    Vivia dentro del orquestador, y cualquier otro script que tardara horas
    -- vectorizar el corpus, agrupar embeddings, reconstruir un lexico --
    tenia que elegir entre importar procesar.py entero (que abre la base de
    datos y carga media docena de modelos) o escribirse otra barra distinta.

    Aqui no depende de nada del proyecto: solo de time y sys.

    from NLP.nucleo.progreso import barra, fin_barra

    inicio = time.time()
    for n, cosa in enumerate(cosas, 1):
        ...
        if n % 25 == 0 or n == total:
            barra(n, total, inicio, "corrigiendo")
    fin_barra()
"""

import sys
import time

ANCHO_BARRA = 34


def barra(hechos, total, inicio, etiqueta=""):
    """
    Escribe una barra de progreso en la misma linea, con porcentaje, ritmo y
    tiempo restante estimado.

    Se reescribe la misma linea con un retorno de carro, en vez de saltar de
    linea, para no llenar la terminal de miles de lineas en una corrida larga.
    Al terminar, quien llama la cierra con fin_barra().
    """
    total = max(total, 1)
    fraccion = hechos / total
    lleno = int(ANCHO_BARRA * fraccion)
    transcurrido = time.time() - inicio
    ritmo = hechos / transcurrido if transcurrido > 0 else 0
    falta = (total - hechos) / ritmo if ritmo > 0 else 0
    sys.stdout.write(
        f"\r  [{'#' * lleno}{'.' * (ANCHO_BARRA - lleno)}] {fraccion * 100:5.1f}% "
        f"{hechos:,}/{total:,} | {transcurrido / 60:.1f} min | "
        f"faltan ~{falta / 60:.1f} min | {ritmo:.1f}/s {etiqueta}   ")
    sys.stdout.flush()


def fin_barra():
    """Cierra la linea de la barra."""
    sys.stdout.write("\n")
    sys.stdout.flush()
