"""
Corrección por vocabulario del corpus, con SymSpell.

Cubre el hueco que dejan LanguageTool y spaCy: los errores de digitación sobre
terminología médica, que LanguageTool no sabe corregir y spaCy no reconoce
('consutla' por 'consulta', 'cardioacular' por 'cardiovascular').

CÓMO SE CONSTRUYE EL DICCIONARIO
    A partir del propio corpus, conservando solo las palabras que spaCy
    reconoce. Así las formas correctas entran con su frecuencia real y los
    errores quedan fuera. El índice se guarda sin tildes, para que una palabra
    mal acentuada alcance a su forma correcta; la forma con tilde se recupera al
    devolver el resultado.

CUÁNDO SE APLICA UNA SUGERENCIA
    distancia 0     es la misma palabra sin tildes, de modo que se trata de una
                    restauración de acento y se aplica siempre.

    original raro   hasta FRECUENCIA_TYPO apariciones. No basta con que sea
                    raro: en una nota clínica la rareza es también la firma de
                    la terminología especializada, y los epónimos, las escalas y
                    los fármacos poco usados aparecen tan pocas veces como un
                    error. Se exige distancia 1, o distancia 2 compartiendo al
                    menos PREFIJO_COMUN_MINIMO letras iniciales.

    original común  se exige que la sugerencia sea RATIO_MINIMO veces más
                    frecuente que el original. Es lo que salva los términos
                    reales de convertirse en su vecino ortográfico: 'desaturada'
                    y 'saturada' están a distancia 2 y significan lo contrario.

Requiere symspellpy. Si no está instalado, el módulo se desactiva y la fase
ortográfica sigue funcionando con sus otras defensas.

`DISTANCIA_POR_TRAMOS` y `FRECUENCIA_MINIMA_CANDIDATO` (E4.2): banderas
apagadas por defecto; medición en docs/decisiones/2026-09-16-E4.2.md.
"""

import re
from collections import Counter

from NLP.fase2_ortografia import terminologia
from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.nucleo import reglas

# ==========================================================
# CONFIGURACION
# ==========================================================

DISTANCIA_MAXIMA = 3          # tope del indice; el lookup usa menos segun longitud
PREFIJO = 10

LONGITUD_MINIMA = 5           # tokens mas cortos no pasan por aqui
LONGITUD_DISTANCIA_3 = 10     # a partir de esta longitud se permite distancia 3
FRECUENCIA_TYPO = 2           # hasta aqui el original se considera error de digitacion
RATIO_MINIMO = 10             # si el original es comun, cuanto debe superarlo la sugerencia

# E4.2 (docs/decisiones/2026-09-16-E4.2.md): distancia maxima por tramos de
# longitud, alternativa a LONGITUD_DISTANCIA_3. Apagado por defecto: la
# medicion no encontro diferencia frente al tope fijo sobre los pares
# juzgados, asi que no se cambia el comportamiento por defecto (principio 8).
DISTANCIA_POR_TRAMOS = False
TRAMO_CORTO_MAXIMO = 5        # 4-5 letras
TRAMO_MEDIO_MAXIMO = 9        # 6-9 letras
DISTANCIA_TRAMO_CORTO = 1
DISTANCIA_TRAMO_MEDIO = 2
DISTANCIA_TRAMO_LARGO = 3

# E4.2: apariciones minimas que debe tener la forma propuesta en el corpus
# para aceptarla. En 0 (el valor de siempre) no hay piso: un candidato puede
# proponerse aunque no aparezca en ninguna nota. Ver la decision para la
# medicion que sostiene subirlo.
FRECUENCIA_MINIMA_CANDIDATO = 0

# Letras iniciales que un original raro debe compartir con su correccion para
# aceptar una distancia de 2. Un typo de digitacion conserva el arranque de la
# palabra; 'fazecas' y 'canecas' no comparten ni la primera letra.
PREFIJO_COMUN_MINIMO = 5
FRECUENCIA_ENTRADA = 1        # apariciones minimas para entrar al diccionario

_SYM = None
_DISPONIBLE = None
_CONTEO = Counter()
_FORMA = {}                   # sin tildes -> forma real mas frecuente

# captura la palabra junto con el guion que la une a otra: 'parieto-occipital'
# entra completa y no como 'parieto', que SymSpell convertia en 'aprieta'
RE_PALABRA = re.compile(r"[a-záéíóúüñ]+(?:-[a-záéíóúüñ]+)*")


# Se reutiliza la definicion de morfologia.py, que conserva la eñe: plegarla
# hacia 'n' juntaria 'año' y 'ano' en la misma entrada del indice.
sin_tildes = morfologia.sin_tildes


# ==========================================================
# CONSTRUCCIÓN DEL DICCIONARIO
# ==========================================================

def disponible():
    """True si el diccionario está construido y SymSpell disponible."""
    return _DISPONIBLE is True


def construir(textos, validar_con_spacy=True):
    """
    Construye el índice a partir del corpus y devuelve el número de entradas.
    Debe llamarse una sola vez, antes de empezar a corregir.

    Con `validar_con_spacy` activo solo entran las palabras que spaCy reconoce,
    que es lo que mantiene los errores de digitación fuera del diccionario. De
    cada forma plegada se recuerda además la variante acentuada más frecuente,
    que es la que se devuelve al corregir.
    """
    global _SYM, _DISPONIBLE

    try:
        from symspellpy import SymSpell
    except ModuleNotFoundError:
        print("Aviso: symspellpy no instalado; la correccion por vocabulario queda desactivada.")
        _DISPONIBLE = False
        return 0

    _CONTEO.clear()
    for t in textos:
        _CONTEO.update(RE_PALABRA.findall(str(t).lower()))

    _SYM = SymSpell(max_dictionary_edit_distance=DISTANCIA_MAXIMA, prefix_length=PREFIJO)
    _FORMA.clear()

    usar_spacy = validar_con_spacy and linguistica.disponible()
    entradas = 0

    for palabra, freq in _CONTEO.items():
        if len(palabra) < 3 or freq < FRECUENCIA_ENTRADA:
            continue
        # solo formas que spaCy reconoce: mantiene los typos fuera del diccionario
        if usar_spacy and not linguistica.en_vocabulario(palabra):
            continue

        plano = sin_tildes(palabra)
        _SYM.create_dictionary_entry(plano, freq)
        if plano not in _FORMA or freq > _CONTEO.get(_FORMA[plano], 0):
            _FORMA[plano] = palabra
        entradas += 1

    _DISPONIBLE = entradas > 0
    return entradas


def frecuencia(palabra):
    """Apariciones de la palabra en el corpus con el que se construyó el índice."""
    return _CONTEO.get(palabra.lower(), 0)


# ==========================================================
# CORRECCIÓN
# ==========================================================

def _prefijo_comun(a, b):
    """Número de letras iniciales que comparten dos palabras."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def sugerir(palabra):
    """
    Corrección para una palabra suelta, o None si no hay evidencia suficiente.

    No decide sobre siglas, entidades ni tokens protegidos: ese filtro lo aplica
    antes el orquestador de la fase. Toda salida None por falta de evidencia
    queda registrada como abstención.
    """
    if not disponible():
        return None

    from symspellpy import Verbosity

    palabra = palabra.lower()
    if len(palabra) < LONGITUD_MINIMA or not palabra.isalpha():
        return None

    plano = sin_tildes(palabra)
    if DISTANCIA_POR_TRAMOS:
        if len(palabra) <= TRAMO_CORTO_MAXIMO:
            distancia = DISTANCIA_TRAMO_CORTO
        elif len(palabra) <= TRAMO_MEDIO_MAXIMO:
            distancia = DISTANCIA_TRAMO_MEDIO
        else:
            distancia = DISTANCIA_TRAMO_LARGO
    else:
        distancia = 3 if len(palabra) >= LONGITUD_DISTANCIA_3 else 2

    try:
        sugerencias = _SYM.lookup(plano, Verbosity.CLOSEST, max_edit_distance=distancia)
    except Exception:
        return None

    if not sugerencias:
        return None

    # entre las sugerencias a la misma distancia, la que conserve la longitud
    # del original: 'ginceologica' se parece mas a 'ginecologico' que a
    # 'ginecologia', que ademas cambia de adjetivo a sustantivo
    distancia_minima = min(s.distance for s in sugerencias)
    empatadas = [s for s in sugerencias if s.distance == distancia_minima]
    empatadas.sort(key=lambda s: (abs(len(s.term) - len(plano)), -s.count))

    mejor = empatadas[0]
    forma = _FORMA.get(mejor.term, mejor.term)
    if forma == palabra:
        return None

    # mismos filtros de forma que en la eleccion de candidatos: sin ellos, este
    # motor cambia la categoria de la palabra en lugar de arreglar su escritura
    if not reglas.forma_aceptable(palabra, forma):
        return None
    # misma puerta que usa LanguageTool: el guardian clinico decide
    if not terminologia.admite(palabra, forma):
        return None

    # distancia 0: la misma palabra, solo le faltaban las tildes. No pasa por
    # el piso de frecuencia: restaurar un acento no depende de cuanto se
    # repita la forma acentuada, y exigirlo aqui volveria a dejar 'medico'
    # sin su tilde en el mismo hueco que describe FRECUENCIA_JERGA en pesos.py.
    if mejor.distance == 0:
        return forma

    if FRECUENCIA_MINIMA_CANDIDATO and frecuencia(forma) < FRECUENCIA_MINIMA_CANDIDATO:
        terminologia.anotar_abstencion(
            palabra, f"'{forma}' no alcanza la frecuencia minima del candidato")
        return None

    freq_original = frecuencia(palabra)

    # Un original que casi no aparece en el corpus suele ser un error de
    # digitacion, pero no siempre: la rareza es tambien la firma de la
    # terminologia especializada, y un eponimo o una escala aparecen tan pocas
    # veces como un typo. Lo que separa unos de otros es la distancia: las
    # correcciones validas estan a distancia 1, o a 2 conservando el arranque de
    # la palabra; las corrupciones estan a 2 y apenas comparten las primeras
    # letras.
    if freq_original <= FRECUENCIA_TYPO:
        # Empate a la distancia minima: dos o mas palabras estan igual de cerca
        # y el desempate por frecuencia elegiria la mas comun, que no tiene por
        # que ser la correcta. Como el original tambien es raro, no hay
        # evidencia por ningun lado y se prefiere no tocar la palabra.
        if len(empatadas) > 1:
            terminologia.anotar_abstencion(
                palabra,
                f"{len(empatadas)} candidatos a distancia {mejor.distance}, "
                f"ninguno decidible")
            return None
        if mejor.distance <= 1:
            return forma
        if _prefijo_comun(plano, mejor.term) >= PREFIJO_COMUN_MINIMO:
            return forma
        terminologia.anotar_abstencion(
            palabra, f"termino raro a distancia {mejor.distance} de '{forma}'")
        return None

    # un original repetido se comporta como terminologia: para sustituirlo, la
    # sugerencia tiene que superarlo por un margen amplio
    if mejor.count >= freq_original * RATIO_MINIMO:
        return forma

    return None


def vecinos(palabra, distancia=2, maximo=5):
    """
    Palabras del corpus dentro de la distancia dada, ordenadas de más a menos
    cercana y, a igual distancia, de más a menos frecuente.

    A diferencia de sugerir(), no decide ni filtra por frecuencia: devuelve la
    lista para que otro la use. La consume la generación de candidatos de la capa
    de contexto, donde el desempate lo hace la frase. Filtrar por frecuencia aquí
    dejaría fuera correcciones válidas, porque la palabra correcta puede ser tan
    rara como el error.
    """
    if not disponible() or len(palabra) < LONGITUD_MINIMA:
        return []

    from symspellpy import Verbosity

    plano = sin_tildes(palabra.lower())
    try:
        sugerencias = _SYM.lookup(plano, Verbosity.ALL, max_edit_distance=distancia)
    except Exception:
        return []

    salida = []
    for s in sorted(sugerencias, key=lambda s: (s.distance, -s.count)):
        forma = _FORMA.get(s.term, s.term)
        # no se descarta la coincidencia exacta con la clave: el indice esta
        # plegado, asi que una palabra y su forma acentuada la comparten, y
        # saltarla dejaria fuera la restauracion de tilde, que es la correccion
        # mas segura de todas
        if forma != palabra and forma not in salida:
            salida.append(forma)
        if len(salida) >= maximo:
            break
    return salida


# Ninguna sugerencia puede cambiar las CIFRAS de la palabra. Mismo criterio y
# mismo motivo que en ortografia.py: ver decisiones/2026-09-16-cifras.md.
PROTEGER_CIFRAS = True

RE_CIFRAS = re.compile(r"\d+")


def corregir_texto(texto, es_corregible, senalados=None):
    """
    Aplica las sugerencias palabra por palabra sobre el texto.

        es_corregible  función(palabra) -> bool que aporta el orquestador, que
                       es quien conoce las siglas, entidades y patrones
                       protegidos de esa nota.
        senalados      si se pasa, conjunto de tokens que LanguageTool marcó
                       como error; solo se actúa sobre ellos. Evita reprocesar
                       una palabra que LanguageTool ya corrigió bien, que era
                       una fuente de correcciones encadenadas erróneas.

    Las palabras con guion se dejan intactas: entran al índice completas y
    partirlas produce fragmentos que no son la palabra.
    """
    if not disponible() or not texto:
        return texto

    def _sub(m):
        palabra = m.group(0)
        if "-" in palabra:
            return palabra
        if senalados is not None and palabra not in senalados:
            return palabra
        if not es_corregible(palabra):
            return palabra
        propuesta = sugerir(palabra)
        if not propuesta:
            return palabra
        # las cifras no se tocan; ver decisiones/2026-09-16-cifras.md
        if PROTEGER_CIFRAS and RE_CIFRAS.findall(palabra) != RE_CIFRAS.findall(propuesta):
            return palabra
        return propuesta

    return RE_PALABRA.sub(_sub, texto)


def diagnosticar(palabra):
    """
    Qué ve SymSpell para una palabra: su frecuencia, las sugerencias más
    cercanas con su distancia y la decisión final. Herramienta de inspección
    manual.
    """
    if not disponible():
        return {"disponible": False}

    from symspellpy import Verbosity

    palabra = palabra.lower()
    distancia = 3 if len(palabra) >= LONGITUD_DISTANCIA_3 else 2
    sugerencias = _SYM.lookup(sin_tildes(palabra), Verbosity.CLOSEST,
                              max_edit_distance=distancia)
    return {
        "disponible": True,
        "frecuencia_original": frecuencia(palabra),
        "sugerencias": [(_FORMA.get(s.term, s.term), s.count, s.distance)
                        for s in sugerencias[:5]],
        "decision": sugerir(palabra),
    }
