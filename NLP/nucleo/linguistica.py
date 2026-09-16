"""
Capa linguistica sobre spaCy: vocabulario del espanol y entidades nombradas,
siempre para PROTEGER una palabra, nunca para corregirla. Requiere el modelo
`es_core_news_md` (`python -m spacy download es_core_news_md`); sin el, el
modulo se desactiva solo y el resto del pipeline sigue. Ver ARQUITECTURA.md
§2.2 (`linguistica.py`) para el porque de cada senal y sus limitaciones.
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

# los pipelines de spaCy no son thread-safe y el orquestador usa varios hilos
_LOCK = threading.Lock()

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


# ==========================================================
# CARGA DEL MODELO
# ==========================================================

def disponible():
    """
    True si spaCy y el modelo están instalados. La comprobación se hace una
    sola vez y se recuerda durante toda la ejecución.
    """
    global _DISPONIBLE
    if _DISPONIBLE is None:
        _DISPONIBLE = _cargar() is not None
    return _DISPONIBLE


def _cargar():
    """
    Carga el modelo la primera vez que se necesita y lo reutiliza después.
    Devuelve None, con un aviso por consola, si falta spaCy o el modelo.
    """
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


# ==========================================================
# VOCABULARIO
# ==========================================================

def en_vocabulario(palabra):
    """
    True si spaCy reconoce la palabra (solo protege: que falte del
    vocabulario no prueba que este mal escrita). Descarta menores de 4
    letras (el vocabulario las acepta casi todas). Cachea el resultado.
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
# ENTIDADES NOMBRADAS
# ==========================================================

def entidades(texto):
    """
    Palabras de la nota que forman parte de una persona, lugar u organizacion,
    en minuscula. Ante cualquier fallo del modelo devuelve un conjunto vacio
    (perder la senal no debe interrumpir el procesamiento).
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
    Igual que entidades(), sobre una lista de notas, aprovechando el
    procesamiento por lotes de spaCy. Un conjunto por nota, mismo orden.
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
    """
    Qué ve spaCy en una nota concreta: entidades detectadas y palabras fuera de
    vocabulario. Herramienta de inspección manual, no la usa el pipeline.
    """
    if not disponible():
        return {"disponible": False}

    doc = _NLP(str(texto)[:MAX_CARACTERES_NER])
    return {
        "disponible": True,
        "entidades": [(e.text, e.label_) for e in doc.ents],
        "fuera_de_vocabulario": [t.text for t in doc if t.is_alpha and t.is_oov],
    }
