"""
Registro de lo que el corrector decidió NO hacer.

Lleva dos contadores que responden a preguntas distintas, y esa distinción es
justamente lo que hace útil el registro al auditar una corrida:

    ALARMAS       el guardián clínico vetó un cambio concreto porque alteraba el
                  significado. Hay una regla que lo explica, y el par queda
                  registrado junto con el motivo. Una alarma indica que una
                  regla de protección hizo su trabajo.

    ABSTENCIONES  no hubo veto: ninguna corrección reunía evidencia suficiente,
                  así que la palabra se dejó intacta. No es un error, sino la
                  decisión correcta ante la duda. Una abstención indica que hay
                  una palabra que el proyecto todavía no sabe interpretar, y si
                  se repite mucho probablemente sea una sigla, un fármaco o
                  jerga del servicio que merece entrar al diccionario.

El registro está separado de `terminologia.py`, que es quien decide, porque
contar no requiere criterio clínico y mezclarlo oscurecía las dos tareas.
"""

from collections import Counter

from NLP.nucleo import morfologia

ALARMAS = Counter()
EJEMPLOS = {}

ABSTENCIONES = Counter()
EJEMPLOS_ABSTENCION = {}


# ==========================================================
# REGISTRO
# ==========================================================

def anotar(motivo, original, candidato):
    """
    Registra un veto del guardián clínico. Del primer par que dispara cada
    motivo se conserva un ejemplo, que es lo que permite entender después qué
    estaba frenando esa regla.
    """
    ALARMAS[motivo] += 1
    EJEMPLOS.setdefault(motivo, f"{original} -> {candidato}")


def anotar_abstencion(original, motivo="sin interpretacion clara"):
    """
    Registra que el corrector dejó una palabra intacta por falta de evidencia.
    La palabra se normaliza antes de contarla, para que sus variantes con
    puntuación o mayúsculas no se cuenten por separado.
    """
    palabra = morfologia.normalizar(original)
    ABSTENCIONES[palabra] += 1
    EJEMPLOS_ABSTENCION.setdefault(palabra, motivo)


# ==========================================================
# INFORMES
# ==========================================================

def resumen_alarmas():
    """
    Vetos agrupados por motivo y ordenados de más a menos frecuente, como lista
    de tuplas (motivo, veces, ejemplo).
    """
    return [(motivo, veces, EJEMPLOS[motivo])
            for motivo, veces in ALARMAS.most_common()]


def resumen_abstenciones(minimo=2):
    """
    Palabras que se dejaron intactas por falta de evidencia, ordenadas por
    frecuencia y descartando las que aparecen menos de `minimo` veces, que
    suelen ser errores puntuales de digitación y no términos por incorporar.
    """
    return [(palabra, veces, EJEMPLOS_ABSTENCION[palabra])
            for palabra, veces in ABSTENCIONES.most_common()
            if veces >= minimo]


def reiniciar_alarmas():
    """Vacía el registro de vetos."""
    ALARMAS.clear()
    EJEMPLOS.clear()


def reiniciar_abstenciones():
    """Vacía el registro de abstenciones."""
    ABSTENCIONES.clear()
    EJEMPLOS_ABSTENCION.clear()


def reiniciar():
    """Vacía ambos registros. Se llama al empezar cada corrida."""
    reiniciar_alarmas()
    reiniciar_abstenciones()
