"""
Registro de lo que el pipeline decidio NO hacer.

POR QUE EXISTE ESTE ARCHIVO
    terminologia.py mezclaba dos trabajos: decidir si una correccion es
    admisible, y llevar la cuenta de las que freno. El segundo no tiene nada
    que ver con criterio clinico, y ocupaba un tercio del archivo.

LAS DOS CUENTAS, Y POR QUE SON DISTINTAS
    ALARMAS      el guardian clinico veto un cambio concreto porque cambiaba
                 el significado: 'monoparesia' -> 'menopausia'. Hay una regla
                 que lo explica, y el par queda registrado con su motivo.
    ABSTENCIONES no hubo veto: simplemente ninguna correccion reunia evidencia
                 suficiente, asi que la palabra se dejo intacta. No es un
                 error, es la decision correcta ante la duda.

    La distincion importa al auditar. Una alarma dice que una regla funciono.
    Una abstencion dice que hay una palabra que el proyecto todavia no sabe
    interpretar: si aparece muchas veces, probablemente es una sigla, un
    farmaco o una jerga del servicio que merece entrar al diccionario.
"""

from collections import Counter

import morfologia

ALARMAS = Counter()
EJEMPLOS = {}

ABSTENCIONES = Counter()
EJEMPLOS_ABSTENCION = {}


# ==========================================================
# REGISTRO
# ==========================================================

def anotar(motivo, original, candidato):
    """Un veto del guardian clinico, con el par que lo provoco."""
    ALARMAS[motivo] += 1
    EJEMPLOS.setdefault(motivo, f"{original} -> {candidato}")


def anotar_abstencion(original, motivo="sin interpretacion clara"):
    """
    Registra que el sistema decidio no tocar una palabra por falta de evidencia.
    No es un error: es la decision correcta cuando no hay como saber que quiso
    decir el personal. La lista sirve para revisar si alguna merece entrar al
    diccionario.
    """
    palabra = morfologia.normalizar(original)
    ABSTENCIONES[palabra] += 1
    EJEMPLOS_ABSTENCION.setdefault(palabra, motivo)


# ==========================================================
# INFORMES
# ==========================================================

def resumen_alarmas():
    """Cuantas correcciones freno el guardian y por que motivo."""
    return [(motivo, veces, EJEMPLOS[motivo])
            for motivo, veces in ALARMAS.most_common()]


def resumen_abstenciones(minimo=2):
    """Palabras que se dejaron intactas por falta de evidencia, por frecuencia."""
    return [(palabra, veces, EJEMPLOS_ABSTENCION[palabra])
            for palabra, veces in ABSTENCIONES.most_common()
            if veces >= minimo]


def reiniciar_alarmas():
    ALARMAS.clear()
    EJEMPLOS.clear()


def reiniciar_abstenciones():
    ABSTENCIONES.clear()
    EJEMPLOS_ABSTENCION.clear()


def reiniciar():
    reiniciar_alarmas()
    reiniciar_abstenciones()
