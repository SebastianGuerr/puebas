"""
Capa linguistica sobre spaCy. Complementa a ortografia.py.

Aporta dos senales que ni LanguageTool ni el diccionario pueden dar:

  1. VOCABULARIO. spaCy conoce ~500.000 palabras del espanol, muchas mas que
     LanguageTool. Medido sobre terminos de las notas de triage:

       en vocabulario   midazolam, topiramato, olanzapina, odinofagia, emesis,
                        epigastrio, disnea, cefalea, crepitantes, dietarias,
                        afebril, helicobacter, crohn, pereira, taquicardia
       fuera            pacinete, dolro, trngo, cbeza, conuslta, malestra,
                        vaginlaes, daignosticaron, trombolfebitis, desasturada

     Una palabra que spaCy reconoce es una palabra real y no se corrige. Esto
     protege farmacos y terminologia sin tener que enumerarlos en el JSON.

  2. ENTIDADES NOMBRADAS. El NER reconoce personas, lugares e instituciones
     incluso en texto ya pasado a minusculas, que es donde la deteccion por
     mayusculas de ortografia.py se queda ciega:

       'paciente remitido de pereira'   -> pereira        (PER/LOC)
       'esposa argelia alzate acompana' -> argelia alzate (LOC/PER)
       'valvula de hakim disfuncional'  -> hakim          (PER)

     Sin esto, 'pereira' se convertia en 'perdida' y 'hakim' en 'hacia' en
     cualquier nota escrita toda en minuscula.

EXCEPCION CONOCIDA
     'fibre' figura en el vocabulario de spaCy (ruido de corpus web) y por eso
     quedaria protegida. Esta cubierta en correcciones_directas del JSON.

INSTALACION
     pip install spacy
     python -m spacy download es_core_news_md

Si spaCy no esta instalado, el modulo se desactiva solo y ortografia.py sigue
funcionando con el resto de sus defensas.
"""

import re
import threading

MODELO = "es_core_news_md"

# etiquetas cuyo contenido no debe corregirse nunca
ETIQUETAS_PROTEGIDAS = {"PER", "LOC", "ORG", "MISC"}

LONGITUD_MINIMA_ENTIDAD = 3
MAX_CARACTERES_NER = 3000     # notas mas largas se truncan para el NER

_NLP = None
_DISPONIBLE = None
_CACHE_VOCAB = {}

# los pipelines de spaCy no son thread-safe y procesar.py usa varios hilos
_LOCK = threading.Lock()

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


# ==========================================================
# CARGA
# ==========================================================

def disponible():
    """True si spaCy y el modelo estan instalados. Se comprueba una sola vez."""
    global _DISPONIBLE
    if _DISPONIBLE is None:
        _DISPONIBLE = _cargar() is not None
    return _DISPONIBLE


def _cargar():
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        import spacy
    except ModuleNotFoundError:
        print("Aviso: spaCy no instalado; la capa linguistica queda desactivada.")
        return None
    try:
        # sin parser ni lematizador: solo se usan vocabulario y entidades
        _NLP = spacy.load(MODELO, disable=["parser", "lemmatizer", "attribute_ruler"])
    except OSError:
        print(f"Aviso: falta el modelo {MODELO}. Instalar con:")
        print(f"       python -m spacy download {MODELO}")
        return None
    return _NLP


def iniciar():
    return _cargar()


# ==========================================================
# VOCABULARIO
# ==========================================================

def en_vocabulario(palabra):
    """
    True si spaCy reconoce la palabra. Se usa para PROTEGER, nunca para
    corregir: que una palabra falte del vocabulario no prueba que este mal.
    """
    if not disponible():
        return False

    palabra = palabra.lower().strip()
    if len(palabra) < 4:
        return False

    if palabra in _CACHE_VOCAB:
        return _CACHE_VOCAB[palabra]

    lexema = _NLP.vocab[palabra]
    resultado = not lexema.is_oov
    _CACHE_VOCAB[palabra] = resultado
    return resultado


# ==========================================================
# ENTIDADES
# ==========================================================

def entidades(texto):
    """
    Tokens que forman parte de una persona, lugar u organizacion.
    Devuelve un set en minuscula, listo para cruzar con los tokens del texto.
    """
    if not disponible() or not texto:
        return set()

    try:
        with _LOCK:
            doc = _NLP(str(texto)[:MAX_CARACTERES_NER])
    except Exception:
        return set()

    encontrados = set()
    for ent in doc.ents:
        if ent.label_ not in ETIQUETAS_PROTEGIDAS:
            continue
        for palabra in RE_PALABRA.findall(ent.text.lower()):
            if len(palabra) >= LONGITUD_MINIMA_ENTIDAD:
                encontrados.add(palabra)
    return encontrados


def entidades_lote(textos, n_process=1, batch_size=200):
    """
    Version por lotes para procesar miles de notas. Mucho mas rapida que
    llamar a entidades() una por una.
    """
    if not disponible():
        return [set() for _ in textos]

    textos = [str(t)[:MAX_CARACTERES_NER] if t else "" for t in textos]
    salida = []

    for doc in _NLP.pipe(textos, batch_size=batch_size, n_process=n_process):
        encontrados = set()
        for ent in doc.ents:
            if ent.label_ not in ETIQUETAS_PROTEGIDAS:
                continue
            for palabra in RE_PALABRA.findall(ent.text.lower()):
                if len(palabra) >= LONGITUD_MINIMA_ENTIDAD:
                    encontrados.add(palabra)
        salida.append(encontrados)

    return salida


def diagnosticar(texto):
    """Que ve spaCy en una nota. Para revisar casos puntuales."""
    if not disponible():
        return {"disponible": False}

    doc = _NLP(str(texto)[:MAX_CARACTERES_NER])
    return {
        "disponible": True,
        "entidades": [(e.text, e.label_) for e in doc.ents],
        "fuera_de_vocabulario": [t.text for t in doc if t.is_alpha and t.is_oov],
    }
