"""
Control de ambiguedad de las entradas de diccionario que usa la fase 3: una
entrada no se aplica salvo que se demuestre inequivoca (o declare contexto).

Criterio completo, las dos clases de ambiguedad y ejemplos: docs/FLUJO.md
(fase 3, seccion 5).
"""

import re

from NLP.nucleo import linguistica

VENTANA_CONTEXTO = 6      # palabras a cada lado donde se busca la confirmacion
LONGITUD_MINIMA = 3       # por debajo de esto ninguna sigla se expande sola

_LT = None
_CACHE_PALABRA = {}

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


def usar_languagetool(lt):
    """Registra el LanguageTool de la fase ortografica; sin el, se usa solo
    el vocabulario de spaCy."""
    global _LT
    _LT = lt


# ==========================================================
# (a) AMBIGÜEDAD DETECTABLE AUTOMÁTICAMENTE
# ==========================================================

def es_palabra_corriente(forma):
    """True si la forma existe como palabra del espanol (LanguageTool +
    vocabulario de spaCy). Cachea el resultado por forma."""
    forma = forma.lower().strip()
    if not forma or not forma.isalpha():
        return False
    if forma in _CACHE_PALABRA:
        return _CACHE_PALABRA[forma]

    # LanguageTool cubre la flexion completa pero deja pasar siglas cortas;
    # spaCy cubre lo frecuente pero ignora palabras de menos de 4 letras.
    resultado = linguistica.en_vocabulario(forma)

    if not resultado and _LT is not None:
        from NLP.nucleo import lt_compat
        # se inserta la forma en una frase minima: LanguageTool necesita
        # contexto para decidir, y asi se comprueba si la marca como error
        frase = f"tiene {forma} aqui"
        try:
            marcada = any(
                lt_compat.categoria(m) == "TYPOS"
                and frase[slice(*lt_compat.span(m))].lower() == forma
                for m in _LT.check(frase)
            )
            resultado = not marcada
        except Exception:
            resultado = False

    _CACHE_PALABRA[forma] = resultado
    return resultado


# ==========================================================
# EVALUACIÓN DE UNA ENTRADA
# ==========================================================

def evaluar(clave, definicion, declaradas_seguras=(), declaradas_ambiguas=()):
    """
    Decide si una entrada del diccionario puede aplicarse: libre, con contexto,
    o inactiva. Devuelve (estado, contexto, motivo); criterio en docs/FLUJO.md.
    """
    clave = clave.lower().strip()
    contexto = ()

    if isinstance(definicion, dict):
        contexto = tuple(p.lower() for p in definicion.get("contexto", ()))

    palabras = clave.split()

    if len(palabras) > 1:
        return ("contexto" if contexto else "libre"), contexto, ""

    if clave in declaradas_ambiguas:
        return "inactiva", contexto, "declarada ambigua"

    if len(clave) < LONGITUD_MINIMA:
        return "inactiva", contexto, f"sigla de {len(clave)} letras"

    if clave in declaradas_seguras:
        return ("contexto" if contexto else "libre"), contexto, ""

    if es_palabra_corriente(clave):
        if contexto:
            return "contexto", contexto, ""
        return "inactiva", contexto, "coincide con una palabra del espanol"

    if contexto:
        return "contexto", contexto, ""

    return "inactiva", contexto, "sigla no declarada como inequivoca"


# ==========================================================
# APLICACIÓN CONDICIONADA AL CONTEXTO
# ==========================================================

def hay_contexto(texto, inicio, fin, palabras_contexto):
    """
    True si alguna palabra de contexto aparece en la ventana de
    VENTANA_CONTEXTO palabras a cada lado del tramo. Sin contexto declarado
    (palabras_contexto vacio), devuelve True.
    """
    if not palabras_contexto:
        return True

    antes = RE_PALABRA.findall(texto[:inicio].lower())[-VENTANA_CONTEXTO:]
    despues = RE_PALABRA.findall(texto[fin:].lower())[:VENTANA_CONTEXTO]
    vecinas = set(antes) | set(despues)

    return any(p in vecinas for p in palabras_contexto)
