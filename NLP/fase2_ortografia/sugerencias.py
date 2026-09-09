"""
Generación de candidatos para la capa de contexto.

POR QUÉ ES UN MÓDULO APARTE
    La capa de contexto puntúa candidatos pero no genera ninguno, y eso es
    deliberado: un modelo de lenguaje que propone escribe lo que es frecuente,
    no lo que es correcto, y llega a proponer variantes inexistentes de un
    término o de un principio activo. La garantía de que no puede inventar una
    palabra es que la lista de candidatos proceda de fuentes declaradas.

    Aquí viven esas fuentes. Todo candidato que salga de este módulo existe en
    el léxico clínico o en el vocabulario que el propio hospital escribe.

LAS CUATRO FUENTES, Y QUÉ CASO RESUELVE CADA UNA
    léxico clínico    términos a distancia de edición corta. Es la misma
                      búsqueda del léxico, pero devolviendo varios candidatos en
                      lugar de uno: aquí no hace falta que el léxico decida,
                      porque decide el contexto.

    corpus            lo que el personal escribe realmente, con su frecuencia.
                      Cubre la jerga y las abreviaturas de servicio, que no
                      están en ningún diccionario médico porque no son
                      terminología sino taquigrafía.

    divisiones        dos palabras que se escribieron pegadas. Se prueba cada
                      corte posible y se conservan los que dejan dos palabras
                      reales, de modo que la regla genera los casos en lugar de
                      enumerarlos.

    expansiones       la forma larga de una abreviatura de habla ('gral' por
                      'general').

LO QUE NO SE GENERA
    Nada que no esté en alguna de esas fuentes. Si una palabra está mal escrita
    y su forma correcta no aparece ni en el léxico ni en las notas del hospital,
    el sistema se abstiene.
"""

import re

from NLP.fase2_ortografia import candidatos
from NLP.fase2_ortografia import vocabulario
from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.recursos import lexico

# ==========================================================
# CONFIGURACION
# ==========================================================

DISTANCIA_MAXIMA = 2
MAX_POR_FUENTE = 5

# Frecuencia minima en el corpus para que una mitad de una division cuente como
# palabra real. Cubre las palabras muy cortas ('a', 'la', 'de'), que el
# vocabulario de spaCy descarta por longitud pero el corpus escribe a millares.
FRECUENCIA_MITAD = 20

LONGITUD_MINIMA_DIVISION = 4   # por debajo, dividir no deja nada util
LONGITUD_MINIMA = 4

RE_ALFABETICA = re.compile(r"^[a-záéíóúüñ]+$")


# ==========================================================
# FUENTES DE CANDIDATOS
# ==========================================================

def _del_lexico(palabra):
    """Formas del léxico clínico dentro de la distancia de edición máxima."""
    return lexico.vecinos(palabra, DISTANCIA_MAXIMA, MAX_POR_FUENTE)


def _del_corpus(palabra):
    """
    Palabras del corpus dentro de la distancia de edición máxima.

    No se filtra por frecuencia: el error y su corrección pueden ser igual de
    raros, y exigir respaldo aquí dejaba fuera correcciones válidas. La
    frecuencia era un buen criterio cuando tenía que decidir por sí sola; ahora
    decide el contexto, y filtrar antes solo le oculta la respuesta.
    """
    return vocabulario.vecinos(palabra, DISTANCIA_MAXIMA, MAX_POR_FUENTE)


# ==========================================================
# ABREVIATURAS
# ==========================================================

LONGITUD_MAXIMA_ABREVIATURA = 6
FRECUENCIA_EXPANSION = 30        # la forma larga tiene que ser corriente
_CACHE_EXPANSION = {}


def _es_subsecuencia(corta, larga):
    """True si las letras de la primera aparecen en la segunda en ese orden."""
    it = iter(larga)
    return all(c in it for c in corta)


def _expansiones(palabra):
    """
    Formas largas de una abreviatura de habla, como 'general' para 'gral'.

    La distancia de edición no sirve para esto: una abreviatura no es un vecino
    ortográfico de su forma larga sino una contracción, y suele quedar fuera del
    alcance del corrector. Lo que sí comparten es la secuencia de letras, que
    aparece completa y en orden dentro de la palabra larga. Ese es el criterio, y
    generaliza a todas las abreviaturas sin enumerar ninguna.

    Se exige además que la inicial coincida y que la forma larga sea corriente en
    el corpus: cualquier token corto es subsecuencia de decenas de palabras
    raras, y sin ese filtro la lista se llenaría de ruido. El resultado se guarda
    en caché porque la búsqueda recorre todo el vocabulario.
    """
    if len(palabra) > LONGITUD_MAXIMA_ABREVIATURA or len(palabra) < 2:
        return []
    if palabra in _CACHE_EXPANSION:
        return _CACHE_EXPANSION[palabra]
    if not candidatos.CONTEO:
        return []

    plano = morfologia.sin_tildes(palabra)
    encontradas = []
    for otra, veces in candidatos.CONTEO.items():
        if veces < FRECUENCIA_EXPANSION or len(otra) <= len(palabra) + 1:
            continue
        llano = morfologia.sin_tildes(otra)
        # la inicial ancla la expansion: 'gral' expande 'general', no 'lateral'
        if llano[0] != plano[0]:
            continue
        if _es_subsecuencia(plano, llano):
            encontradas.append((veces, otra))

    encontradas.sort(reverse=True)
    salida = [o for _v, o in encontradas[:MAX_POR_FUENTE]]
    _CACHE_EXPANSION[palabra] = salida
    return salida


def _es_palabra(fragmento):
    """
    True si el fragmento es una palabra real, sea porque el corpus la escribe
    con frecuencia o porque spaCy la reconoce.
    """
    if not fragmento or not RE_ALFABETICA.match(fragmento):
        return False
    if candidatos.CONTEO.get(fragmento, 0) >= FRECUENCIA_MITAD:
        return True
    return linguistica.en_vocabulario(fragmento)


def _divisiones(palabra):
    """
    Divisiones de la palabra en dos que dejan dos palabras reales, como 'a la'
    para 'ala'.

    Se prueban todos los cortes posibles y los que producen un fragmento
    inexistente se descartan solos, de modo que la regla no necesita una lista de
    casos.
    """
    if len(palabra) < LONGITUD_MINIMA_DIVISION - 1:
        return []

    # UNA PALABRA QUE YA EXISTE NO SE PROPONE PARTIDA.
    #
    # Esta fuente existe para 'ala' -> 'a la', donde lo escrito es un pegado.
    # Pero probaba todos los cortes de CUALQUIER palabra, y como los fragmentos
    # cortos casi siempre existen, generaba divisiones de palabras correctas:
    #
    #     hablando   ->  'h ablando', 'ha blando', 'habl ando'
    #     dorada     ->  'd orada', 'dora da'
    #     afiliados  ->  'afilia dos', 'afiliado s'
    #
    # Esas propuestas son el origen de la particion de palabras: el modelo solo
    # puntua lo que se le pasa, y se le estaban pasando. Ademas ocupaban sitio
    # en la lista, que esta topada, y desplazaban al candidato bueno --
    # 'cortada' quedaba en sexta posicion detras de cuatro divisiones inutiles.
    #
    # 'ala' sigue funcionando porque el espanol no la reconoce como palabra
    # suelta en este corpus; lo que se corta es proponer divisiones de una
    # palabra que ya es correcta, que nunca puede ser una correccion.
    if linguistica.en_vocabulario(palabra):
        return []

    salida = []
    for i in range(1, len(palabra)):
        izquierda, derecha = palabra[:i], palabra[i:]
        if _es_palabra(izquierda) and _es_palabra(derecha):
            salida.append(f"{izquierda} {derecha}")
    return salida[:MAX_POR_FUENTE]


# ==========================================================
# GENERACIÓN
# ==========================================================

def generar(palabra):
    """
    Todos los candidatos para una palabra, sin repetidos y sin la palabra
    misma, en el orden en que los aportan las cuatro fuentes.

    Devuelve una lista vacía cuando ninguna fuente aporta nada, que es el caso
    mayoritario: la mayor parte de las palabras de una nota están bien escritas.
    """
    palabra = morfologia.normalizar(palabra)
    if len(palabra) < LONGITUD_MINIMA - 1 or morfologia.tiene_numero(palabra):
        return []

    vistos, salida = {palabra}, []
    for fuente in (_del_lexico, _del_corpus, _divisiones, _expansiones):
        for candidato in fuente(palabra):
            clave = candidato.lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            salida.append(candidato)
    return salida


def diagnosticar(palabra):
    """
    Qué aporta cada fuente para una palabra concreta, y la lista final.
    Herramienta de inspección manual.
    """
    palabra = morfologia.normalizar(palabra)
    return {
        "palabra": palabra,
        "lexico": _del_lexico(palabra),
        "corpus": _del_corpus(palabra),
        "divisiones": _divisiones(palabra),
        "expansiones": _expansiones(palabra),
        "todos": generar(palabra),
    }
