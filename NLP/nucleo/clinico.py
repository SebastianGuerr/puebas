"""
Pipeline clinico compartido: spaCy + medspaCy (tokenizador y seccionador),
cargado una sola vez. `analizar(texto)` da el Doc; `secciones(texto)` da los
tramos con su categoria. No sustituye a `linguistica.py` (vocabulario y
entidades). Ver ARQUITECTURA.md §2.2 (`clinico.py`) para el porque de las
secciones y del analisis en minusculas.
"""

import threading

MODELO = "es_core_news_md"

# El tokenizador de medspacy separa mejor lo que aparece pegado en notas
# clinicas ('39.5C', '10/10', 'dolor,nauseas') sin romper decimales ni fechas.
USAR_TOKENIZADOR_CLINICO = True

_NLP = None
_DISPONIBLE = None
_LOCK = threading.Lock()

# Componentes que se anaden bajo demanda. Ninguno se activa solo: cada uno
# necesita reglas, y las reglas las pone quien lo usa.
_SECCIONADOR = None


# ==========================================================
# CARGA DEL MODELO
# ==========================================================

def _cargar():
    """
    Carga el modelo la primera vez y lo conserva. Devuelve None si falta spaCy
    o el modelo. Si medspaCy no está disponible se mantiene el tokenizador de
    spaCy: separa peor los tokens pegados, pero no produce resultados erróneos.
    """
    global _NLP
    if _NLP is not None:
        return _NLP
    try:
        import spacy
    except ModuleNotFoundError:
        return None
    try:
        nlp = spacy.load(MODELO)
    except OSError:
        return None

    if USAR_TOKENIZADOR_CLINICO:
        try:
            from medspacy.custom_tokenizer import create_medspacy_tokenizer
            nlp.tokenizer = create_medspacy_tokenizer(nlp)
        except Exception:
            # sin medspacy el pipeline sigue funcionando con el tokenizador
            # de spaCy: es peor separando, no incorrecto
            pass

    _NLP = nlp
    return _NLP


def disponible():
    """
    True si spaCy y el modelo están instalados. Se comprueba una sola vez, con
    candado porque varios hilos pueden preguntarlo a la vez.
    """
    global _DISPONIBLE
    if _DISPONIBLE is None:
        with _LOCK:
            if _DISPONIBLE is None:
                _DISPONIBLE = _cargar() is not None
    return _DISPONIBLE


def nlp():
    """El pipeline compartido, o None si spaCy no está disponible."""
    return _cargar() if disponible() else None


def analizar(texto):
    """
    Devuelve el Doc de spaCy correspondiente al texto, ya limpio y en
    minúsculas, o None si el modelo no está disponible.

    Las notas se truncan a MAX_CARACTERES. El pipeline de spaCy no es seguro
    entre hilos y el orquestador usa varios, de ahí el candado.
    """
    modelo = nlp()
    if modelo is None:
        return None
    with _LOCK:
        return modelo(str(texto)[:MAX_CARACTERES])


MAX_CARACTERES = 5000   # notas mas largas se truncan para el analisis


# ==========================================================
# SECCIONES DE LA NOTA
# ==========================================================

# Encabezados de historia clinica tal como aparecen en el corpus. La sigla y su
# forma larga apuntan a la misma categoria: lo que interesa aguas abajo es la
# categoria, no como la escribio quien digito. Es la unica tabla de encabezados
# del proyecto; mantener dos listas para lo mismo garantiza que acaben
# divergiendo.
SECCIONES = {
    "motivo_consulta": ["mc", "motivo de consulta", "mc (motivo de consulta)"],
    "enfermedad_actual": ["ea", "enfermedad actual"],
    "antecedentes_patologicos": ["ap", "antecedentes personales", "antecedentes",
                                 "patologicos", "patológicos", "ap patologicos"],
    "antecedentes_alergicos": ["aa", "alergicos", "alérgicos", "alergias",
                               "antecedentes alergicos"],
    "antecedentes_familiares": ["af", "antecedentes familiares", "familiares"],
    "antecedentes_quirurgicos": ["quirurgicos", "quirúrgicos", "ax"],
    "antecedentes_toxicos": ["toxicos", "tóxicos"],
    "medicamentos": ["medicamentos", "farmacologicos", "farmacológicos"],
    "examen_fisico": ["ef", "examen fisico", "examen físico"],
    "signos_vitales": ["sv", "signos vitales"],
    "revision_sistemas": ["rs", "revision por sistemas", "revisión por sistemas"],
    "diagnostico": ["dx", "diagnostico", "diagnóstico", "diagnosticos",
                    "impresion diagnostica", "impresión diagnóstica"],
    "plan": ["plan", "px", "conducta", "analisis", "análisis"],
    "ocupacion": ["ocupacion", "ocupación"],
    "fuente": ["fuente de la historia", "fuente"],
}

# Nombre del tramo anterior al primer encabezado. En triage es el caso
# mayoritario: la nota tipica es un texto corrido, sin estructura.
SIN_ENCABEZADO = "sin_encabezado"

# Secciones que NO describen el motivo por el que el paciente consulto hoy.
# Sirven para dos cosas distintas y ambas importan:
#   1. cortar el alcance de la negacion, para que el 'niega' de los
#      antecedentes alergicos no niegue los sintomas del motivo de consulta;
#   2. decidir que tramos sobran en el texto para el embedding, sin tener que
#      enumerar frases administrativas una por una.
SECCIONES_NO_CLINICAS = {
    "antecedentes_patologicos", "antecedentes_alergicos",
    "antecedentes_familiares", "antecedentes_quirurgicos",
    "antecedentes_toxicos", "medicamentos", "ocupacion", "fuente",
}


def _reglas_seccion():
    """Traduce la tabla SECCIONES a reglas de medspaCy, una por forma escrita."""
    from medspacy.section_detection import SectionRule

    reglas = []
    for categoria, formas in SECCIONES.items():
        for forma in formas:
            # el encabezado se reconoce con y sin los dos puntos: en el corpus
            # aparece 'ap:' pero tambien 'ap -' y 'ap ' al abrir linea
            reglas.append(SectionRule(literal=f"{forma}:", category=categoria))
    return reglas


def seccionador():
    """
    Añade el Sectionizer al pipeline y lo devuelve. Es idempotente: si ya está
    registrado, devuelve el existente. None si medspaCy no está instalado.
    """
    global _SECCIONADOR
    if _SECCIONADOR is not None:
        return _SECCIONADOR

    modelo = nlp()
    if modelo is None:
        return None

    try:
        from medspacy.section_detection import Sectionizer
    except ModuleNotFoundError:
        return None

    with _LOCK:
        if "medspacy_sectionizer" in modelo.pipe_names:
            _SECCIONADOR = modelo.get_pipe("medspacy_sectionizer")
        else:
            _SECCIONADOR = modelo.add_pipe(
                "medspacy_sectionizer", config={"rules": None})
            _SECCIONADOR.add(_reglas_seccion())
    return _SECCIONADOR


def secciones(texto):
    """
    Tramos de la nota con su categoria: lista de (categoria, inicio, fin,
    texto), desplazamientos en caracteres. Lista vacia si medspaCy no esta
    instalado; el tramo antes del primer encabezado va como SIN_ENCABEZADO.
    """
    if seccionador() is None:
        return []
    doc = analizar(texto)
    if doc is None:
        return []

    salida = []
    for seccion in doc._.sections:
        # en la version de medspaCy usada, body_start/body_end son indices de
        # token (no un Span de spaCy); se recorta el Doc a mano con ellos
        inicio, fin = seccion.body_start, seccion.body_end
        if inicio is None or fin is None or fin <= inicio:
            continue
        tramo = doc[inicio:fin]
        categoria = seccion.category or SIN_ENCABEZADO
        salida.append((categoria, tramo.start_char, tramo.end_char, tramo.text))
    return salida


def diagnosticar(texto):
    """
    Qué ve el pipeline en una nota concreta: componentes activos, tokens,
    oraciones, entidades y secciones. Herramienta de inspección manual.
    """
    doc = analizar(texto)
    if doc is None:
        return {"disponible": False}
    return {
        "disponible": True,
        "modelo": MODELO,
        "componentes": nlp().pipe_names,
        "tokens": len(doc),
        "oraciones": [s.text for s in doc.sents],
        "entidades": [(e.text, e.label_) for e in doc.ents],
        "secciones": secciones(texto),
    }
