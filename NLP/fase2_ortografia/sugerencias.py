"""
Generacion de candidatos para la capa de contexto.

POR QUE ESTE ARCHIVO EXISTE SEPARADO
    contexto.py puntua candidatos pero no genera ninguno, a proposito: un
    modelo de lenguaje que propone escribe lo que es frecuente, no lo que es
    correcto, y medido produjo 'epistaxis -> epistasis' y 'midazolam ->
    midazolan'. La garantia de que no puede inventar una palabra es que la
    lista de candidatos venga de fuentes declaradas.

    Aqui viven esas fuentes. Cada candidato que salga de este modulo existe en
    el lexico clinico (32.310 formas del CIE-10, el diccionario del proyecto y
    el catalogo) o en el vocabulario que el propio hospital escribe.

LAS TRES FUENTES, Y QUE CASO RESUELVE CADA UNA

    lexico clinico      'cordada' -> 'cortada', 'regio' -> 'región'
                        Terminos y palabras a distancia de edicion <= 2. Es la
                        misma busqueda de lexico.cercano(), pero devolviendo
                        VARIOS candidatos en vez de uno: aqui no hace falta que
                        el lexico decida, porque decide el contexto.

    vocabulario del     'gral' -> 'general'
    hospital            Lo que el personal escribe de verdad, con su
                        frecuencia. Cubre la jerga y las abreviaturas de
                        servicio, que no estan en ningun diccionario medico
                        porque no son terminologia sino taquigrafia.

    division en dos     'ala' -> 'a la'
                        Dos palabras pegadas al teclear. Se prueba cada corte
                        posible y se conservan los que dejan DOS palabras
                        reales. No hace falta enumerar los casos: la regla los
                        genera. 'ala' produce 'a la'; 'dolor' no produce nada
                        porque 'lor' no existe.

LO QUE NO SE GENERA
    Nada que no este en una de las tres fuentes. Si una palabra esta mal
    escrita y su forma correcta no aparece ni en el CIE-10, ni en el
    diccionario del proyecto, ni en las notas del hospital, el sistema se
    abstiene. Es la misma politica del resto del proyecto: ante la falta de
    evidencia, no se toca.
"""

import re

import candidatos
import lexico
import vocabulario
import linguistica
import morfologia

# ==========================================================
# CONFIGURACION
# ==========================================================

DISTANCIA_MAXIMA = 2
MAX_POR_FUENTE = 5

# Frecuencia minima en el corpus para que una mitad de una division cuente como
# palabra real. Cubre las palabras cortisimas ('a', 'la', 'de') que ningun
# vocabulario de spaCy reconoce por longitud, pero que el hospital escribe
# miles de veces.
FRECUENCIA_MITAD = 20

LONGITUD_MINIMA_DIVISION = 4   # por debajo, dividir no deja nada util
LONGITUD_MINIMA = 4

RE_ALFABETICA = re.compile(r"^[a-záéíóúüñ]+$")


# ==========================================================
# FUENTES
# ==========================================================

def _del_lexico(palabra):
    """Formas del lexico clinico a distancia <= 2."""
    return lexico.vecinos(palabra, DISTANCIA_MAXIMA, MAX_POR_FUENTE)


def _del_corpus(palabra):
    """
    Palabras que el hospital escribe, a distancia <= 2.

    NO se filtra por frecuencia, y esa decision costo un caso conocido. La
    primera version exigia que el candidato fuera al menos el doble de
    frecuente que el original, con la idea de no gastar evaluaciones en
    candidatos sin respaldo. Medido:

        cordada(1) -> cortada(1)    quedaba fuera, y es la correccion buena

    El error y su correccion pueden ser igual de raros. La frecuencia era buen
    criterio cuando ella misma tenia que decidir; ahora decide el contexto, y
    filtrar antes solo le esconde la respuesta.
    """
    return vocabulario.vecinos(palabra, DISTANCIA_MAXIMA, MAX_POR_FUENTE)


# ==========================================================
# ABREVIATURAS
# ==========================================================

LONGITUD_MAXIMA_ABREVIATURA = 6
FRECUENCIA_EXPANSION = 30        # la forma larga tiene que ser corriente
_CACHE_EXPANSION = {}


def _es_subsecuencia(corta, larga):
    """True si las letras de 'corta' aparecen en 'larga' en el mismo orden."""
    it = iter(larga)
    return all(c in it for c in corta)


def _expansiones(palabra):
    """
    'gral' -> ['general'].  La forma larga de una abreviatura de habla.

    POR QUE NO SIRVE LA DISTANCIA DE EDICION
        Una abreviatura no es un vecino ortografico de su forma larga: es una
        contraccion. Medido, 'gral' esta a distancia 3 de 'general', o sea
        fuera del alcance de SymSpell con DISTANCIA_MAXIMA=2. Lo mismo pasa con
        'qx'/'quirurgico', 'tto'/'tratamiento' o 'aprox'/'aproximadamente'.

        Lo que SI comparten es la secuencia de letras: g-r-a-l aparece dentro
        de g-e-n-e-r-a-l en ese orden. Esa es la prueba clasica de abreviatura,
        y generaliza a todas sin enumerar ninguna.

    Se exige ademas que la forma larga sea corriente en el corpus. Cualquier
    token corto es subsecuencia de decenas de palabras raras, y sin ese filtro
    la lista de candidatos se llenaria de ruido.
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
    """True si el fragmento es una palabra real del espanol o del hospital."""
    if not fragmento or not RE_ALFABETICA.match(fragmento):
        return False
    if candidatos.CONTEO.get(fragmento, 0) >= FRECUENCIA_MITAD:
        return True
    return linguistica.en_vocabulario(fragmento)


def _divisiones(palabra):
    """
    'ala' -> ['a la'].  Dos palabras que se escribieron pegadas.

    Se prueban todos los cortes y se conservan los que dejan dos palabras
    reales. Un corte que produce un fragmento inexistente se descarta solo, asi
    que la regla no necesita lista de casos: 'ala' funciona porque 'a' y 'la'
    existen, y 'dolor' no produce nada porque 'lor' no existe.
    """
    if len(palabra) < LONGITUD_MINIMA_DIVISION - 1:
        return []
    salida = []
    for i in range(1, len(palabra)):
        izquierda, derecha = palabra[:i], palabra[i:]
        if _es_palabra(izquierda) and _es_palabra(derecha):
            salida.append(f"{izquierda} {derecha}")
    return salida[:MAX_POR_FUENTE]


# ==========================================================
# GENERACION
# ==========================================================

def generar(palabra):
    """
    Todos los candidatos para una palabra, sin repetir y sin la propia palabra.
    Lista vacia si ninguna fuente aporta nada, que es el caso mayoritario.
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
    """De donde sale cada candidato. Para revisar casos puntuales."""
    palabra = morfologia.normalizar(palabra)
    return {
        "palabra": palabra,
        "lexico": _del_lexico(palabra),
        "corpus": _del_corpus(palabra),
        "divisiones": _divisiones(palabra),
        "expansiones": _expansiones(palabra),
        "todos": generar(palabra),
    }
