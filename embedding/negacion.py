"""
Fase 4. Deteccion de negacion, incertidumbre y antecedente en espanol.

POR QUE HACE FALTA
    'niega fiebre' y 'fiebre' contienen la misma palabra y significan lo
    contrario. Para un clustering que agrupe por sintomas, un hallazgo negado
    contado como presente es un dato falso, y en este corpus la negacion no es
    marginal: 'niega' aparece 3.418 veces y 'sin' 3.684 sobre 30.000 notas.

POR QUE NO SE USA medspaCy TAL CUAL
    Su motor ConText es solido, pero los disparadores que trae son ingleses
    ('denies', 'no evidence of', 'ruled out') y no reaccionan a 'niega'. Lo que
    sirve de ConText es el metodo: disparador, direccion, alcance y terminador.
    Ese metodo esta implementado aqui con los disparadores del espanol clinico
    colombiano medidos sobre el corpus.

LO QUE SE MIDIO
    niega .............. 3.418     sin .............. 3.684
    no hay ..............  223     descarta .........    65
    negativo ............   48     no refiere .......    45
    ausencia de .........   27     no presenta ......    21

    Dos trampas que aparecieron al mirar los datos:

    'sin embargo' (181 veces) es un conector, no una negacion. Sin excluirlo,
    todo lo que sigue a esa locucion quedaria marcado como negado.

    'sin signos de' y 'sin criterios de' (1.692 veces) no niegan la palabra
    siguiente sino lo que va despues del 'de': en 'sin signos de dificultad
    respiratoria' lo negado es la dificultad respiratoria, no los signos.
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
# 'no' se deja fuera a proposito: hacia atras es demasiado ambiguo y en
# 'posible neumonia, no hay fiebre' retro-negaba la neumonia.
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

# adjetivos que afirman el hallazgo al que acompanan. Si aparecen cerca, la
# enumeracion negada ya termino: en 'niega perdidas vaginales, movimientos
# fetales activos' lo negado son las perdidas, y los movimientos estan presentes.
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
    """Ordena por longitud para que la locucion mas larga gane."""
    return sorted(lista, key=lambda x: len(x.split()), reverse=True)


NEGACION_ADELANTE = _frases(NEGACION_ADELANTE)
INCERTIDUMBRE = _frases(INCERTIDUMBRE)
ANTECEDENTE = _frases(ANTECEDENTE)
TERMINADORES = _frases(TERMINADORES)


# ==========================================================
# ANALISIS
# ==========================================================

def _tokenizar(texto):
    return RE_TOKEN.findall(str(texto).lower())


def _coincide(tokens, i, frase):
    partes = frase.split()
    return tokens[i:i + len(partes)] == partes


def _es_excepcion(tokens, i):
    return any(_coincide(tokens, i, e) for e in EXCEPCIONES)


def _saltar_puente(tokens, j):
    """Avanza el inicio del alcance si hay un puente ('signos de', 'criterios de')."""
    for puente in PUENTES:
        partes = puente.split()
        if tokens[j:j + len(partes)] == partes:
            return j + len(partes)
    return j


def _es_terminador(tokens, i):
    return any(_coincide(tokens, i, t) for t in TERMINADORES)


def _afirmacion_cercana(tokens, i, ventana=VENTANA_AFIRMADOR):
    """True si en los proximos tokens hay un adjetivo que afirma el hallazgo."""
    return any(t in AFIRMADORES for t in tokens[i:i + ventana + 1])


def marcar(texto, terminos_clinicos=None):
    """
    Devuelve una lista de (token, estado) donde estado es uno de:
        'afirmado', 'negado', 'incierto', 'antecedente'

    terminos_clinicos: vocabulario de sintomas conocidos. Resuelve la coma, que
    es ambigua: en 'niega fiebre, tos y disnea' continua una enumeracion negada,
    pero en 'niega perdidas vaginales, movimientos fetales activos' cierra la
    negacion y empieza una afirmacion. Sin el catalogo no hay como distinguirlas;
    con el, la enumeracion sigue mientras el elemento siguiente sea un sintoma
    conocido.
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
                # sintoma del catalogo; en caso contrario la coma cierra
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
    Estado de una expresion concreta dentro del texto.
    'niega fiebre', 'fiebre' -> 'negado'
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
    """Como quedo marcada cada palabra. Para revisar casos puntuales."""
    return [(t, e) for t, e in marcar(texto, terminos_clinicos) if e != "afirmado"]
