"""
Fase 4. Detección de negación, incertidumbre y antecedente en español clínico.

POR QUÉ HACE FALTA
    'niega fiebre' y 'fiebre' contienen la misma palabra y significan lo
    contrario. Para un análisis que agrupe por síntomas, un hallazgo negado
    contado como presente es un dato falso, y en este corpus la negación no es
    marginal: los disparadores más comunes aparecen en miles de notas.

POR QUÉ NO SE USA medspaCy DIRECTAMENTE
    Su motor ConText es sólido, pero los disparadores que trae son ingleses y no
    reaccionan al español. Lo aprovechable de ConText es el método —disparador,
    dirección, alcance y terminador— y es el que se implementa aquí, con los
    disparadores del español clínico observados en el corpus.

LOS CUATRO ESTADOS
    afirmado      el hallazgo está presente
    negado        se afirma que no está
    incierto      se plantea como sospecha, no como hecho
    antecedente   ocurrió en el pasado; no es el motivo de consulta actual

LAS TRAMPAS QUE RESUELVE
    Locuciones que empiezan como una negación sin serlo, y que sin excluirlas
    dejarían negado todo lo que viene detrás.

    Expresiones puente del tipo 'sin signos de', donde lo negado no es la
    palabra siguiente sino lo que va después del 'de'.

    La coma, que es ambigua: puede continuar una enumeración negada o cerrarla y
    empezar una afirmación. Se resuelve con el vocabulario de síntomas conocidos
    y con los adjetivos que afirman explícitamente un hallazgo.
"""

import re

# ==========================================================
# DISPARADORES
# ==========================================================

# niegan lo que viene DESPUES
NEGACION_ADELANTE = [
    "niega", "niegan", "no refiere", "no refieren", "no presenta", "no presentan",
    "no manifiesta", "no manifiestan", "no asocia", "no asocian", "no evidencia",
    "no se evidencia", "no impresiona", "no hay", "no se observa", "no observa",
    "no tiene", "no ha tenido", "no ha presentado", "no reporta", "sin",
    "ausencia de", "ausente", "descarta", "se descarta", "descartado",
    "libre de", "exento de", "no",
]

# niegan lo que viene ANTES
# 'no' se deja fuera a proposito: hacia atras es demasiado ambiguo y llegaba a
# negar el diagnostico de la frase anterior.
NEGACION_ATRAS = ["negativo", "negativa", "negativos", "negativas",
                  "ausente", "ausentes", "descartado", "descartada"]

# marcan duda, no ausencia: el hallazgo no es seguro pero tampoco esta negado
INCERTIDUMBRE = [
    "posible", "probable", "sospecha de", "sospecha", "a descartar", "descartar",
    "impresiona", "sugestivo de", "compatible con", "versus", "vs", "duda",
    "aparente", "al parecer", "refiere que posiblemente",
]

# situan el hallazgo en el pasado: es antecedente, no motivo de consulta actual
ANTECEDENTE = [
    "antecedente de", "antecedentes de", "historia de", "hace anos", "hace años",
    "previo", "previa", "en el pasado", "anteriormente", "conocido",
    "en manejo por", "en tratamiento por", "diagnosticado con", "diagnosticada con",
]

# cierran el alcance de un disparador
TERMINADORES = [
    ".", ";", ":", "pero", "aunque", "sin embargo", "no obstante", "refiere",
    "presenta", "manifiesta", "asociado a", "asociada a", "con", "mas",
    "ademas", "y presenta", "actualmente", "consulta por", "por lo que",
    "se evidencia", "se observa", "si", "positivo para",
]

# Adjetivos que afirman el hallazgo al que acompanan. Si aparecen cerca, la
# enumeracion negada ya termino: en 'niega perdidas vaginales, movimientos
# fetales activos' lo negado son las perdidas, no los movimientos.
AFIRMADORES = [
    "activos", "activo", "activas", "activa", "presentes", "presente",
    "positivo", "positiva", "positivos", "positivas", "conservados",
    "conservado", "conservada", "normales", "normal", "adecuados", "adecuado",
    "adecuada", "buenos", "buena", "bueno", "si", "sí", "refiere",
]

VENTANA_AFIRMADOR = 3   # tokens que se miran hacia adelante tras una coma

# locuciones que empiezan como negacion pero no lo son
EXCEPCIONES = ["sin embargo", "sin numero", "sin dato", "sin especificar"]

# tras estas palabras la negacion apunta al complemento, no al sustantivo:
# 'sin signos de dificultad respiratoria' niega la dificultad, no los signos
PUENTES = ["signos de", "signo de", "criterios de", "criterio de", "datos de",
           "evidencia de", "hallazgos de", "sintomas de", "síntomas de",
           "clinica de", "clínica de", "presencia de"]

ALCANCE_MAXIMO = 6   # tokens que abarca un disparador si no aparece terminador

RE_TOKEN = re.compile(r"[\wáéíóúüñ]+|[.;:,]")


def _frases(lista):
    """
    Ordena los disparadores de más a menos palabras, para que al buscar gane
    siempre la locución más larga y específica.
    """
    return sorted(lista, key=lambda x: len(x.split()), reverse=True)


NEGACION_ADELANTE = _frases(NEGACION_ADELANTE)
INCERTIDUMBRE = _frases(INCERTIDUMBRE)
ANTECEDENTE = _frases(ANTECEDENTE)
TERMINADORES = _frases(TERMINADORES)


# ==========================================================
# ANALISIS
# ==========================================================

def _tokenizar(texto):
    """Palabras y signos de puntuación relevantes, en minúscula."""
    return RE_TOKEN.findall(str(texto).lower())


def _coincide(tokens, i, frase):
    """True si la frase aparece en los tokens a partir de la posición i."""
    partes = frase.split()
    return tokens[i:i + len(partes)] == partes


def _es_excepcion(tokens, i):
    """True si en esa posición empieza una locución que solo parece negación."""
    return any(_coincide(tokens, i, e) for e in EXCEPCIONES)


def _saltar_puente(tokens, j):
    """
    Adelanta el inicio del alcance cuando hay una expresión puente, para que la
    negación caiga sobre el hallazgo y no sobre el sustantivo intermedio.
    """
    for puente in PUENTES:
        partes = puente.split()
        if tokens[j:j + len(partes)] == partes:
            return j + len(partes)
    return j


def _es_terminador(tokens, i):
    """True si en esa posición hay algo que cierra el alcance del disparador."""
    return any(_coincide(tokens, i, t) for t in TERMINADORES)


def _afirmacion_cercana(tokens, i, ventana=VENTANA_AFIRMADOR):
    """True si dentro de la ventana hay un adjetivo que afirma el hallazgo."""
    return any(t in AFIRMADORES for t in tokens[i:i + ventana + 1])


def marcar(texto, terminos_clinicos=None):
    """
    Marca cada token del texto con su estado y devuelve la lista de pares
    (token, estado).

    El recorrido busca un disparador, calcula dónde empieza su alcance —saltando
    la expresión puente si la hay— y marca hacia adelante hasta encontrar un
    terminador o agotar ALCANCE_MAXIMO tokens. Después se aplican los
    disparadores que niegan hacia atrás.

    `terminos_clinicos` es el vocabulario de síntomas conocidos y sirve para
    resolver la coma: la enumeración negada continúa mientras lo que sigue sea un
    síntoma del catálogo y no venga afirmado de forma explícita. Sin ese
    vocabulario, la coma cierra siempre.
    """
    terminos_clinicos = terminos_clinicos or set()
    tokens = _tokenizar(texto)
    estados = ["afirmado"] * len(tokens)

    i = 0
    while i < len(tokens):
        if _es_excepcion(tokens, i):
            i += 1
            continue

        disparador, etiqueta = None, None
        for frase in NEGACION_ADELANTE:
            if _coincide(tokens, i, frase):
                disparador, etiqueta = frase, "negado"
                break
        if disparador is None:
            for frase in INCERTIDUMBRE:
                if _coincide(tokens, i, frase):
                    disparador, etiqueta = frase, "incierto"
                    break
        if disparador is None:
            for frase in ANTECEDENTE:
                if _coincide(tokens, i, frase):
                    disparador, etiqueta = frase, "antecedente"
                    break

        if disparador is None:
            i += 1
            continue

        inicio = i + len(disparador.split())
        inicio = _saltar_puente(tokens, inicio)

        j, alcanzados = inicio, 0
        while j < len(tokens) and alcanzados < ALCANCE_MAXIMO:
            if _es_terminador(tokens, j):
                break
            if tokens[j] == ",":
                siguiente = tokens[j + 1] if j + 1 < len(tokens) else ""
                # la enumeracion negada continua solo si lo que sigue es un
                # sintoma conocido o un nexo; si no, la coma cierra el alcance
                sigue_enumeracion = (siguiente in terminos_clinicos
                                     or siguiente in ("ni", "y", "o"))
                # ...salvo que lo que viene este afirmado explicitamente
                if sigue_enumeracion and not _afirmacion_cercana(tokens, j + 1):
                    j += 1
                    continue
                break
            estados[j] = etiqueta
            j += 1
            alcanzados += 1

        i = inicio

    # disparadores que niegan hacia atras
    for i, token in enumerate(tokens):
        if token in NEGACION_ATRAS and i > 0:
            for j in range(max(0, i - 3), i):
                if _es_terminador(tokens, j):
                    continue
                estados[j] = "negado"

    return list(zip(tokens, estados))


def estado_de(texto, expresion, terminos_clinicos=None):
    """
    Estado de una expresión concreta dentro del texto: para 'fiebre' en
    'niega fiebre' devuelve 'negado'.

    Si la expresión abarca varios tokens con estados distintos, gana el más
    restrictivo, en el orden negado, incierto, antecedente. Una expresión que no
    aparece en el texto se considera afirmada.
    """
    marcado = marcar(texto, terminos_clinicos)
    partes = _tokenizar(expresion)
    if not partes:
        return "afirmado"

    tokens = [t for t, _ in marcado]
    for i in range(len(tokens) - len(partes) + 1):
        if tokens[i:i + len(partes)] == partes:
            estados = [e for _, e in marcado[i:i + len(partes)]]
            for prioridad in ("negado", "incierto", "antecedente"):
                if prioridad in estados:
                    return prioridad
            return "afirmado"
    return "afirmado"


def diagnosticar(texto, terminos_clinicos=None):
    """
    Tokens del texto que quedaron marcados con algún estado distinto de
    afirmado. Herramienta de inspección manual.
    """
    return [(t, e) for t, e in marcar(texto, terminos_clinicos) if e != "afirmado"]
