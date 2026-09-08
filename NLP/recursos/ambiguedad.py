"""
Control de ambiguedad de las entradas de diccionario.

EL PROBLEMA QUE RESUELVE

    El pipeline transformaba por defecto y protegia por excepcion: cada vez que
    aparecia un caso malo se agregaba una entrada a una lista negra. IVA y DAD
    eran la version de esta semana de SMS y EDA, y siempre iban a aparecer mas.
    Perseguir casos no escala porque el numero de siglas ambiguas del castellano
    medico no esta acotado.

    Aqui se invierte: una entrada de diccionario NO se aplica salvo que se
    demuestre que es inequivoca. La demostracion tiene dos vias, porque hay dos
    clases de ambiguedad y solo una es detectable a maquina.

    (a) La forma coincide con una palabra corriente del espanol.
        nacido, fuego, brote, morado, les, dad, cita, masa.
        Se detecta consultando el diccionario de LanguageTool y el vocabulario
        de spaCy: si alguno la reconoce como palabra, la entrada queda inactiva.

    (b) La sigla no es una palabra, pero significa cosas distintas segun el
        servicio: IVA (impuesto / segmento hepatico / infeccion de vias aereas),
        EDA (enfermedad diarreica aguda / escala de dolor / endoscopia),
        DAD (dextrosa en agua destilada / nombre propio).
        Esto NO es detectable: requiere saber medicina. Por eso el diccionario
        declara explicitamente que entradas son seguras, y lo que no esta
        declarado no se expande.

COMO SE DECLARA UNA EXCEPCION

    En el JSON, una entrada puede escribirse de dos formas:

        "hta": "hipertension arterial"

        "nacido": {"significado": "furunculo",
                   "contexto": ["salio", "grano", "piel", "pierna", "espalda"]}

    La segunda solo se aplica si alguna palabra de "contexto" aparece cerca. Asi
    'le salio un nacido en la pierna' se normaliza y 'recien nacido de 6 dias'
    no, sin necesidad de anclas ni listas negras.

QUE HACER CON EL INFORME

    cargar() deja en desactivadas() todo lo que quedo fuera y por que. Ese
    listado es la lista de decisiones pendientes: cada entrada ahi es una que
    hay que revisar y, si corresponde, declarar con su contexto. El sistema no
    adivina.
"""

import re

import linguistica

VENTANA_CONTEXTO = 6      # palabras a cada lado donde se busca la confirmacion
LONGITUD_MINIMA = 3       # por debajo de esto ninguna sigla se expande sola

_LT = None
_CACHE_PALABRA = {}

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


def usar_languagetool(lt):
    """Recibe la instancia ya creada por ortografia.py; no crea otra."""
    global _LT
    _LT = lt


# ==========================================================
# (a) AMBIGUEDAD DETECTABLE
# ==========================================================

def es_palabra_corriente(forma):
    """
    True si la forma existe como palabra del espanol. Dos fuentes, porque
    ninguna basta sola: LanguageTool cubre la flexion completa pero deja pasar
    siglas cortas, y el vocabulario de spaCy cubre lo frecuente pero ignora
    palabras de menos de cuatro letras.
    """
    forma = forma.lower().strip()
    if not forma or not forma.isalpha():
        return False
    if forma in _CACHE_PALABRA:
        return _CACHE_PALABRA[forma]

    resultado = linguistica.en_vocabulario(forma)

    if not resultado and _LT is not None:
        import lt_compat
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
# EVALUACION DE UNA ENTRADA
# ==========================================================

def evaluar(clave, definicion, declaradas_seguras=(), declaradas_ambiguas=()):
    """
    Decide si una entrada puede aplicarse y como.

    Devuelve (estado, contexto, motivo) donde estado es:
        "libre"     se aplica siempre
        "contexto"  se aplica solo si aparece una palabra de contexto cerca
        "inactiva"  no se aplica
    """
    clave = clave.lower().strip()
    contexto = ()

    if isinstance(definicion, dict):
        contexto = tuple(p.lower() for p in definicion.get("contexto", ()))

    palabras = clave.split()

    # una expresion de varias palabras es casi siempre inequivoca por si misma
    if len(palabras) > 1:
        return ("contexto" if contexto else "libre"), contexto, ""

    if clave in declaradas_ambiguas:
        return "inactiva", contexto, "declarada ambigua"

    if len(clave) < LONGITUD_MINIMA:
        return "inactiva", contexto, f"sigla de {len(clave)} letras"

    # la declaracion explicita va primero: hay palabras del espanol cuya
    # traduccion clinica es inequivoca ('acidez' siempre es pirosis), y eso no
    # se puede deducir de que la palabra exista. Lo decide quien mantiene el
    # diccionario, no el test automatico.
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
# APLICACION CON CONTEXTO
# ==========================================================

def hay_contexto(texto, inicio, fin, palabras_contexto):
    """True si alguna palabra de contexto aparece en la ventana alrededor."""
    if not palabras_contexto:
        return True

    antes = RE_PALABRA.findall(texto[:inicio].lower())[-VENTANA_CONTEXTO:]
    despues = RE_PALABRA.findall(texto[fin:].lower())[:VENTANA_CONTEXTO]
    vecinas = set(antes) | set(despues)

    return any(p in vecinas for p in palabras_contexto)
