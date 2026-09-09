"""
Control de ambigüedad de las entradas de diccionario.

QUÉ PROBLEMA RESUELVE
    El criterio anterior era transformar por defecto y proteger por excepción:
    cada vez que aparecía un caso indebido se añadía una entrada a una lista
    negra. Eso no escala, porque el conjunto de siglas ambiguas del castellano
    médico no está acotado y siempre aparece la siguiente.

    Aquí se invierte la carga de la prueba: una entrada de diccionario no se
    aplica salvo que se demuestre que es inequívoca. La demostración tiene dos
    vías, porque hay dos clases de ambigüedad y solo una es detectable por
    máquina.

    (a) La forma coincide con una palabra corriente del español ('nacido',
        'fuego', 'brote', 'masa'). Se detecta consultando el diccionario de
        LanguageTool y el vocabulario de spaCy: si alguno la reconoce como
        palabra, la entrada queda inactiva.

    (b) La sigla no es una palabra, pero significa cosas distintas según el
        servicio: 'IVA' puede ser un impuesto, un segmento hepático o una
        infección de vías aéreas. Esto no es detectable automáticamente, porque
        exige criterio clínico. Por eso el diccionario declara de forma
        explícita qué entradas son seguras, y lo que no está declarado no se
        expande.

CÓMO SE DECLARA UNA EXCEPCIÓN
    En el diccionario, una entrada puede escribirse de dos formas:

        "hta": "hipertension arterial"

        "nacido": {"significado": "furunculo",
                   "contexto": ["salio", "grano", "piel", "pierna", "espalda"]}

    La segunda solo se aplica si alguna de las palabras de "contexto" aparece
    cerca. Así 'le salio un nacido en la pierna' se normaliza y 'recien nacido
    de 6 dias' no, sin necesidad de listas negras.

QUÉ HACER CON EL INFORME
    Al cargar el diccionario queda registrado todo lo que se desactivó y por
    qué. Ese listado es la lista de decisiones pendientes: cada entrada que
    aparece ahí hay que revisarla y, si corresponde, declararla con su contexto.
    El módulo no adivina.
"""

import re

from NLP.nucleo import linguistica

VENTANA_CONTEXTO = 6      # palabras a cada lado donde se busca la confirmacion
LONGITUD_MINIMA = 3       # por debajo de esto ninguna sigla se expande sola

_LT = None
_CACHE_PALABRA = {}

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


def usar_languagetool(lt):
    """
    Registra la instancia de LanguageTool que ya creó la fase ortográfica, para
    reutilizarla en la detección de palabras corrientes. Sin ella el módulo
    funciona igual, apoyado solo en el vocabulario de spaCy.
    """
    global _LT
    _LT = lt


# ==========================================================
# (a) AMBIGÜEDAD DETECTABLE AUTOMÁTICAMENTE
# ==========================================================

def es_palabra_corriente(forma):
    """
    True si la forma existe como palabra del español.

    Se consultan dos fuentes porque ninguna basta por sí sola: LanguageTool
    cubre la flexión completa pero deja pasar siglas cortas, y el vocabulario de
    spaCy cubre lo frecuente pero ignora las palabras de menos de cuatro letras.
    El resultado se guarda en caché, ya que la misma forma se consulta una vez
    por nota.
    """
    forma = forma.lower().strip()
    if not forma or not forma.isalpha():
        return False
    if forma in _CACHE_PALABRA:
        return _CACHE_PALABRA[forma]

    resultado = linguistica.en_vocabulario(forma)

    if not resultado and _LT is not None:
        from NLP.nucleo import lt_compat
        # se inserta la forma en una frase mínima: LanguageTool necesita
        # contexto para decidir, y así se comprueba si la marca como error
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
    Decide si una entrada del diccionario puede aplicarse y en qué condiciones.

    Devuelve la terna (estado, contexto, motivo), donde el estado es uno de:

        "libre"     se aplica siempre
        "contexto"  se aplica solo si una palabra de contexto aparece cerca
        "inactiva"  no se aplica, y el motivo explica por qué

    Las expresiones de varias palabras se consideran inequívocas por sí mismas.
    Para las de una sola palabra, la declaración explícita del diccionario tiene
    prioridad sobre la detección automática: hay palabras del español cuya
    traducción clínica es inequívoca, y eso no puede deducirse del hecho de que
    la palabra exista. Esa decisión corresponde a quien mantiene el diccionario.
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
    True si alguna de las palabras de contexto aparece en la ventana de
    VENTANA_CONTEXTO palabras a cada lado del tramo (inicio, fin).

    Si la entrada no declara contexto, devuelve True: no hay condición que
    comprobar.
    """
    if not palabras_contexto:
        return True

    antes = RE_PALABRA.findall(texto[:inicio].lower())[-VENTANA_CONTEXTO:]
    despues = RE_PALABRA.findall(texto[fin:].lower())[:VENTANA_CONTEXTO]
    vecinas = set(antes) | set(despues)

    return any(p in vecinas for p in palabras_contexto)
