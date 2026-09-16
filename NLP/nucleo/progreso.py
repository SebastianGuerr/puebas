"""
Barra de progreso para corridas largas, sin depender de nada del proyecto
(solo `time`/`sys`), para que cualquier script largo la use sin tener que
importar procesar.py entero. Ver ARQUITECTURA.md §2.2 (`progreso.py`) para
un ejemplo de uso.
"""

import sys
import time

ANCHO_BARRA = 34


def barra(hechos, total, inicio, etiqueta=""):
    """
    Escribe/reescribe una barra de progreso en la misma linea (retorno de
    carro, no salto), con porcentaje, ritmo y tiempo restante. Quien llama
    la cierra con fin_barra() al terminar.
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
