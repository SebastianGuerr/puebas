"""
Correccion por vocabulario del corpus, con SymSpell.

Cubre el hueco que dejan LanguageTool y spaCy: typos de terminologia medica que
LanguageTool no sabe corregir y spaCy no reconoce. Medido sobre las notas:

    cardioacular      -> cardiovascular       urgencuas   -> urgencias
    consutla          -> consulta             ugencias    -> urgencias
    deformimdad       -> deformidad           habala      -> habla
    neuorlogicament   -> neurologicamente     smena       -> suena
    hemodinamicamente -> hemodinámicamente    ginceologica-> ginecologica

COMO SE CONSTRUYE EL DICCIONARIO
    Del propio corpus, quedandose solo con las palabras que spaCy reconoce.
    Asi las formas correctas entran con su frecuencia real y los typos quedan
    fuera. El indice se guarda sin tildes, para que 'ginceologica' alcance a
    'ginecológica'; la forma con tilde se recupera al devolver el resultado.

CUANDO SE APLICA UNA SUGERENCIA
    distancia 0    misma palabra sin tildes: se aplica siempre, es restauracion
                   de acento (hemodinamicamente -> hemodinámicamente).
    original raro  hasta FRECUENCIA_TYPO apariciones. Ya NO se aplica sin mas:
                   en una nota clinica la rareza no distingue un typo de un
                   termino especializado, y esa suposicion produjo
                   'fazecas -> canecas' y 'stemi -> stent'. Se exige distancia
                   1, o distancia 2 con PREFIJO_COMUN_MINIMO letras iniciales
                   compartidas. Medido sobre 13 pares conocidos, esa condicion
                   separa las 10 correcciones buenas de las 3 corrupciones sin
                   una sola discrepancia.
    original comun se exige que la sugerencia sea RATIO_MINIMO veces mas
                   frecuente. Esto es lo que salva los terminos reales:

                     glucometria(218) -> glucosuria(1)     ratio 0.005  rechazado
                     desaturada(61)   -> saturada(169)     ratio 2.8    rechazado
                     taquicardica(26) -> taquicardia(149)  ratio 5.7    rechazado
                     consutla(28)     -> consulta(2489)    ratio 89     aceptado

                   'desaturada -> saturada' es el caso que justifica el umbral:
                   son terminos opuestos y la distancia de edicion es 2.

INSTALACION
    pip install symspellpy

Si symspellpy no esta instalado, el modulo se desactiva y ortografia.py sigue
funcionando con sus otras defensas.
"""

import re
import unicodedata
from collections import Counter

import linguistica
import reglas
import terminologia

# ==========================================================
# CONFIGURACION
# ==========================================================

DISTANCIA_MAXIMA = 3          # tope del indice; el lookup usa menos segun longitud
PREFIJO = 10

LONGITUD_MINIMA = 5           # tokens mas cortos no pasan por aqui
LONGITUD_DISTANCIA_3 = 10     # a partir de esta longitud se permite distancia 3
FRECUENCIA_TYPO = 2           # hasta aqui el original se considera error de digitacion
RATIO_MINIMO = 10             # si el original es comun, cuanto debe superarlo la sugerencia

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


def sin_tildes(palabra):
    return "".join(
        c for c in unicodedata.normalize("NFD", palabra) if not unicodedata.combining(c)
    )


# ==========================================================
# CONSTRUCCION
# ==========================================================

def disponible():
    return _DISPONIBLE is True


def construir(textos, validar_con_spacy=True):
    """
    Arma el diccionario a partir del corpus. Llamar una vez, antes de corregir.
    Devuelve el numero de entradas.
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
    return _CONTEO.get(palabra.lower(), 0)


# ==========================================================
# CORRECCION
# ==========================================================

def _prefijo_comun(a, b):
    """Cuantas letras iniciales comparten dos palabras."""
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


def sugerir(palabra):
    """
    Devuelve la correccion para una palabra, o None si no hay evidencia.
    No decide sobre siglas ni entidades: eso lo filtra ortografia.py antes.
    """
    if not disponible():
        return None

    from symspellpy import Verbosity

    palabra = palabra.lower()
    if len(palabra) < LONGITUD_MINIMA or not palabra.isalpha():
        return None

    plano = sin_tildes(palabra)
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

    # misma regla morfologica que en candidatos.py: un termino medico solo se
    # corrige hacia otro que conserve sus morfemas y su raiz. Sin esto SymSpell
    # producia presincope -> sincope y hemoperitoneo -> neumoperitoneo
    # mismos filtros de forma que en candidatos.py. Sin ellos SymSpell producia
    # electrofisiologo -> electrofisiologia y midriaticas -> midriasis, que
    # cambian la categoria de la palabra en lugar de arreglar la escritura
    if not reglas.forma_aceptable(palabra, forma):
        return None
    # misma puerta que usa LanguageTool: el guardian clinico decide
    if not terminologia.admite(palabra, forma):
        return None

    # distancia 0: la misma palabra, solo le faltaban las tildes
    if mejor.distance == 0:
        return forma

    freq_original = frecuencia(palabra)

    # Un original que casi no aparece en el corpus SUELE ser un error de
    # digitacion, pero no siempre: en una nota clinica la rareza es tambien la
    # firma de la terminologia especializada. Los epónimos, las escalas y los
    # farmacos poco usados aparecen una o dos veces en 30.000 notas, igual que
    # un typo. Aplicar la correccion sin mas condiciones es lo que produjo:
    #
    #     fazecas(1) -> canecas(1)     la escala de Fazekas
    #     stemi(1)   -> stent(25)      el infarto con elevacion del ST
    #     fomag(3)   -> toma(349)      el fondo del magisterio
    #
    # Lo que separa a esos tres de una correccion buena es la distancia,
    # medido sobre 13 pares conocidos: las 9 correcciones buenas estan a
    # distancia 1, salvo 'cardioacular' -> 'cardiovascular', que esta a 2 pero
    # comparte 6 letras iniciales. Las 3 corrupciones estan a distancia 2 y
    # comparten como mucho 3.
    if freq_original <= FRECUENCIA_TYPO:
        if mejor.distance <= 1:
            return forma
        if _prefijo_comun(plano, mejor.term) >= PREFIJO_COMUN_MINIMO:
            return forma
        terminologia.anotar_abstencion(
            palabra, f"termino raro a distancia {mejor.distance} de '{forma}'")
        return None

    # un original repetido es terminologia: la sugerencia tiene que aplastarlo
    if mejor.count >= freq_original * RATIO_MINIMO:
        return forma

    return None


def corregir_texto(texto, es_corregible, senalados=None):
    """
    Aplica sugerencias palabra por palabra.

    es_corregible(palabra) -> bool lo aporta ortografia.py, que sabe de siglas,
    entidades y patrones protegidos.

    senalados: conjunto de tokens que LanguageTool marco como error. Si se pasa,
    SymSpell solo actua sobre ellos. Es lo que impide que reprocese una palabra
    que LanguageTool ya corrigio bien: 'ofidico' -> 'ofídico' (LanguageTool)
    terminaba en 'físico' porque SymSpell la volvia a tocar despues.
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
        return sugerir(palabra) or palabra

    return RE_PALABRA.sub(_sub, texto)


def diagnosticar(palabra):
    """Que ve SymSpell para una palabra. Para revisar casos puntuales."""
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
