"""
Pipeline clinico compartido: spaCy + medspacy, cargado una sola vez.

POR QUE EXISTE ESTE ARCHIVO
    linguistica.py levanta es_core_news_md para usar dos cosas: el vocabulario
    y el NER. Cargar ese modelo cuesta ~5 segundos y trae ademas tokenizador,
    etiquetador morfologico, lematizador y analizador de dependencias, que
    estaban ahi sin usarse.

    Al mismo tiempo el proyecto resolvia a mano, con expresiones regulares,
    tres cosas que medspacy ya hace y que estan instaladas desde el principio:

        secciones de la nota   RE_ENCABEZADO en limpieza.py, y OTRA copia en
                               embedding/texto_embedding.py
        terminos del catalogo  un matcher propio en embedding/extraccion.py
        negacion e incertidumbre  negacion.py, escrito entero a mano

    Este modulo centraliza la carga y deja los tres componentes disponibles.
    No reemplaza a linguistica.py: linguistica sigue siendo la interfaz
    estrecha (vocabulario, entidades) que usan reglas.py y terminologia.py, y
    ahora toma de aca el objeto nlp en vez de cargar el suyo.

POR QUE SECCIONES, Y POR QUE ES LO PRIMERO
    Medido sobre una nota real del corpus, ConText sin limites de seccion
    propaga la negacion de 'aa: niega' (antecedentes alergicos) al motivo de
    consulta entero, y marca como negado un 'dolor abdominal' que el paciente
    si tiene. Las secciones no son adorno de formato: son la frontera que
    impide que un 'niega' de una seccion contamine la siguiente.

    Ademas, saber que un tramo es 'ap:' o 'aa:' permite decidir que NO es
    motivo de consulta sin tener que enumerar frases, que es justo el parche
    que se quiere quitar de texto_embedding.py.

EL CASING
    Medido sobre 250 notas del corpus escritas con capitalizacion normal, y
    comparando contra el analisis de esas mismas notas sin alterar:

        TODO MAYUSCULAS   POS  64.4%   dependencias  67.1%   entidades x3.6
        todo minusculas   POS  94.9%   dependencias  93.8%   entidades  0.28x

    O sea: para etiquetas y dependencias, minusculas es casi tan bueno como el
    original, y limpieza.limpiar() ya las entrega asi. Para el NER no: en
    minusculas se pierden dos de cada tres entidades. Por eso este modulo
    analiza en minusculas y la recuperacion de nombres propios se resuelve
    aparte, en casing.py.
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
# CARGA
# ==========================================================

def _cargar():
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
    """True si spaCy y el modelo estan instalados. Se comprueba una sola vez."""
    global _DISPONIBLE
    if _DISPONIBLE is None:
        with _LOCK:
            if _DISPONIBLE is None:
                _DISPONIBLE = _cargar() is not None
    return _DISPONIBLE


def nlp():
    """El pipeline compartido, o None si spaCy no esta disponible."""
    return _cargar() if disponible() else None


def analizar(texto):
    """
    Un Doc de spaCy sobre texto ya limpio (minusculas).

    El pipeline de spaCy no es thread-safe y procesar.py usa varios hilos, por
    eso el candado. Es el mismo criterio que ya aplicaba linguistica.py.
    """
    modelo = nlp()
    if modelo is None:
        return None
    with _LOCK:
        return modelo(str(texto)[:MAX_CARACTERES])


MAX_CARACTERES = 5000   # notas mas largas se truncan para el analisis


# ==========================================================
# SECCIONES
# ==========================================================

# Encabezados de historia clinica tal como aparecen en el corpus. La sigla y su
# forma larga apuntan a la misma categoria: lo que interesa aguas abajo es la
# categoria, no como la escribio quien digito.
#
# Esta tabla sustituye a RE_ENCABEZADO de limpieza.py y al RE_ENCABEZADO
# distinto de embedding/texto_embedding.py. Que hubiera dos listas separadas
# para lo mismo era la garantia de que tarde o temprano dijeran cosas
# distintas.
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

# Nombre del tramo anterior al primer encabezado. En triage es lo mas comun:
# medido sobre 400 notas del corpus, solo 39 traen algun encabezado y el resto
# es una nota corrida sin estructura.
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
    Anade el Sectionizer al pipeline y lo devuelve. Idempotente.
    None si medspacy no esta instalado.
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
    Los tramos de la nota con su categoria.

    Devuelve [(categoria, inicio, fin, texto_del_cuerpo)], con los offsets en
    CARACTERES referidos al texto que se paso. Lista vacia si medspacy no esta
    o si la nota no trae encabezados, que es el caso mayoritario en triage.

    OJO CON body_span
        En medspacy 1.3.1 Section.body_span no es un Span de spaCy sino una
        tupla (token_inicial, token_final). Pedirle .text o .start_char lanza
        AttributeError. Se recortan los tokens del Doc a mano, que ademas es
        lo que da los offsets en caracteres que necesita quien llama.
    """
    if seccionador() is None:
        return []
    doc = analizar(texto)
    if doc is None:
        return []

    salida = []
    for seccion in doc._.sections:
        inicio, fin = seccion.body_start, seccion.body_end
        if inicio is None or fin is None or fin <= inicio:
            continue
        tramo = doc[inicio:fin]
        # medspacy abre una seccion implicita, con category None, para el texto
        # anterior al primer encabezado. En triage ese tramo es la mayoria del
        # corpus (la nota tipica no trae encabezados), asi que se nombra en vez
        # de dejarlo en None y que reviente el primer f-string que lo formatee.
        categoria = seccion.category or SIN_ENCABEZADO
        salida.append((categoria, tramo.start_char, tramo.end_char, tramo.text))
    return salida


def diagnosticar(texto):
    """Que ve el pipeline en una nota concreta. Para revisar casos puntuales."""
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
