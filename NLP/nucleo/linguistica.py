"""
Capa lingüística sobre spaCy: vocabulario del español y entidades nombradas.

Aporta dos señales que ni LanguageTool ni el diccionario del proyecto pueden
dar, y ambas se usan siempre para PROTEGER una palabra, nunca para corregirla:

  1. Vocabulario. El modelo conoce del orden de medio millón de formas del
     español, muchas más que LanguageTool, e incluye buena parte de la
     terminología clínica y de los principios activos habituales. Una palabra
     que spaCy reconoce se considera real y queda fuera del corrector, sin
     necesidad de enumerarla en el diccionario.

  2. Entidades nombradas. El reconocedor identifica personas, lugares e
     instituciones incluso en texto ya pasado a minúscula, que es justo donde la
     detección por mayúsculas se queda ciega. Sin esta señal, en una nota
     escrita toda en minúscula 'pereira' se corrige a 'perdida' y 'hakim'
     (de válvula de Hakim) a 'hacia'.

Limitación conocida: el vocabulario procede de texto web y contiene ruido, de
modo que alguna forma incorrecta figura como válida y queda protegida. Esos
casos se resuelven uno a uno en las correcciones directas del diccionario.

Requiere el modelo `es_core_news_md`:

    pip install spacy
    python -m spacy download es_core_news_md

Si spaCy o el modelo no están instalados, el módulo se desactiva por sí solo y
el resto del pipeline sigue funcionando con sus demás defensas.
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
    True si spaCy reconoce la palabra.

    Solo sirve para proteger: que una palabra falte del vocabulario no
    demuestra que esté mal escrita. Las palabras de menos de cuatro letras se
    descartan porque el vocabulario las acepta casi todas. El resultado se
    guarda en caché, ya que la misma forma se consulta muchas veces por nota.
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
    Palabras de la nota que forman parte de una persona, lugar u organización.

    Devuelve un conjunto en minúscula, listo para cruzar con los tokens del
    texto. Ante cualquier fallo del modelo devuelve un conjunto vacío: perder la
    señal degrada la protección, pero no debe interrumpir el procesamiento.
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
    Igual que entidades(), pero sobre una lista de notas y aprovechando el
    procesamiento por lotes de spaCy. Devuelve un conjunto por nota, en el mismo
    orden de entrada. Es la vía a usar cuando se procesan miles de registros.
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
