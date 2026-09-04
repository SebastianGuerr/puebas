"""
Criterios de proteccion: que tokens NO deben corregirse nunca.

Se separa de ortografia.py porque estas reglas las consumen tambien
vocabulario.py (SymSpell) y normalizacion.py, y porque son el punto que mas se
ajusta cuando aparece un fallo nuevo en la auditoria.

ORDEN DE LAS DEFENSAS
  1. Numeros y medidas ..... nada que contenga un digito se toca jamas.
  2. Diccionario ........... siglas, farmacos, eponimos, marcas, terminos.
  3. Patrones .............. vertebras (l5), dosis (5mg), tokens de una letra.
  4. Entidades ............. personas, lugares e instituciones del texto.
  5. Vocabulario spaCy ..... palabras reales que LanguageTool marca por error.
  6. Forma ................. longitud minima, distancia y diferencia de largo.

DE DONDE SALE LO QUE NO ESTA AQUI
    Todo lo que se decide mirando solo la forma de la palabra (morfemas
    medicos, truncamientos, sufijos de farmaco) vive en morfologia.py. Este
    archivo lo reexporta para que quien importaba 'reglas.morfemas' o
    'reglas.sin_tildes' siga funcionando sin cambios.
"""

import json
import re
from pathlib import Path

from rapidfuzz.distance import DamerauLevenshtein

import casing
import linguistica
import morfologia
from morfologia import (  # reexportado: el resto del paquete los usa como reglas.X
    LETRAS_RAIZ,
    PREFIJOS_MEDICOS,
    SUFIJOS_MEDICOS,
    conserva_morfemas,
    es_restauracion_tilde,
    es_termino_medico,
    es_truncamiento,
    morfemas,
    normalizar,
    sin_tildes,
    solo_cambia_terminacion,
    tiene_numero,
)

RUTA_SIGLAS = Path(__file__).resolve().parent / "diccionario_siglas.json"

LONGITUD_MINIMA = 5          # tokens mas cortos solo via correcciones directas
DISTANCIA_MAXIMA = 2         # ediciones permitidas entre original y candidato
DIFERENCIA_LONGITUD = 1      # letras de diferencia permitidas

PROPORCION_MAYUSCULAS = 0.9
LARGO_MAXIMO_SIGLA = 6

USAR_SPACY = True
PROTEGER_POR_VOCABULARIO = True
PROTEGER_ENTIDADES = True

SIGLAS = set()
SIGLAS_INEQUIVOCAS = set()   # lista blanca: las unicas que se expanden solas
SIGLAS_AMBIGUAS = set()      # bloqueadas aunque pasaran los tests automaticos
SIGNIFICADOS = {}
EXPANDIBLES = {}
NO_RESTAURAR = set()
DIRECTAS = {}
PATRONES = []

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")
RE_MAYUSCULA_INICIAL = re.compile(r"\b[A-ZÁÉÍÓÚÑ][a-záéíóúüñ]{2,}")
RE_TODO_MAYUSCULAS = re.compile(r"\b[A-ZÁÉÍÓÚÑ]{2,%d}\b" % LARGO_MAXIMO_SIGLA)


# Palabras que anuncian un nombre propio inmediatamente despues. Es la unica
# senal disponible en notas escritas todas en mayusculas, donde ni el NER ni la
# deteccion por capitalizacion tienen con que trabajar. Sin esto:
#     dr ceron -> dr cero        dr munar -> dr lunar
#     confamiliar pereira -> conciliar pereira
# Solo titulos y lugares. Se dejaron fuera a proposito los de parentesco
# ('paciente', 'hijo', 'esposa') y los verbos de remision ('remitido',
# 'traido'): van seguidos de sintomas mucho mas a menudo que de nombres, y
# protegerlos bloqueaba correcciones validas como 'paciente con dolro'.
DISPARADORES_NOMBRE = {
    "dr", "dra", "doctor", "doctora", "sr", "sra", "srta", "don", "dona", "doña",
    "senor", "señor", "senora", "señora", "clinica", "clínica", "hospital",
    "ips", "eps", "arl", "fundacion", "fundación", "barrio", "vereda",
    "corregimiento", "municipio", "finca", "urbanizacion", "urbanización",
}
VENTANA_NOMBRE = 2   # cuantos tokens despues del disparador se protegen


def tokens_protegidos_por_contexto(texto):
    """Tokens que siguen a un disparador de nombre propio."""
    protegidos = set()
    tokens = RE_PALABRA.findall(str(texto).lower())
    for i, token in enumerate(tokens):
        if token in DISPARADORES_NOMBRE:
            for siguiente in tokens[i + 1:i + 1 + VENTANA_NOMBRE]:
                if siguiente not in DISPARADORES_NOMBRE and len(siguiente) >= 4:
                    protegidos.add(siguiente)
    return protegidos


# ==========================================================
# CARGA DEL DICCIONARIO
# ==========================================================

def cargar(ruta=RUTA_SIGLAS):
    """Lee diccionario_siglas.json en formato {clave: significado} o lista."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))

    for coleccion in (SIGLAS, NO_RESTAURAR, SIGLAS_INEQUIVOCAS, SIGLAS_AMBIGUAS):
        coleccion.clear()

    SIGLAS_INEQUIVOCAS.update(x.lower() for x in datos.get("_siglas_inequivocas", []))
    SIGLAS_AMBIGUAS.update(x.lower() for x in datos.get("_siglas_ambiguas", []))
    for mapa in (SIGNIFICADOS, EXPANDIBLES, DIRECTAS):
        mapa.clear()
    PATRONES.clear()

    expandibles = set(datos.get("_grupos_expandibles", []))

    for clave, valor in datos.items():
        if clave.startswith("_"):
            continue
        if clave == "patrones_protegidos":
            PATRONES.extend(re.compile(x) for x in valor)
        elif clave == "no_restaurar_mayuscula":
            NO_RESTAURAR.update(x.lower() for x in valor)
        elif clave == "correcciones_directas":
            DIRECTAS.update({k.lower(): v for k, v in valor.items()
                             if not k.startswith("_")})
        elif isinstance(valor, dict):
            for sigla, significado in valor.items():
                sigla = sigla.lower()
                SIGLAS.add(sigla)
                SIGNIFICADOS[sigla] = significado
                if clave in expandibles:
                    EXPANDIBLES[sigla] = significado
        else:
            SIGLAS.update(x.lower() for x in valor)

    return SIGLAS


# ==========================================================
# UTILIDADES
# ==========================================================

def texto_gritado(texto):
    """True si la nota esta toda en mayusculas: no hay contraste que leer."""
    letras = [c for c in str(texto) if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


# ==========================================================
# PROTECCION
# ==========================================================

def detectar_protegidos(texto_original):
    """
    Nombres propios y siglas leidos del texto TAL COMO LO ESCRIBIERON.
    Solo funciona en notas mixtas; en una nota gritada devuelve vacio y el
    trabajo lo hacen el diccionario y el NER.
    """
    protegidos = set()
    texto_original = str(texto_original or "")

    if texto_gritado(texto_original):
        return protegidos

    for m in RE_MAYUSCULA_INICIAL.finditer(texto_original):
        anterior = texto_original[:m.start()].rstrip()
        if anterior and not anterior.endswith((".", ":", ";", "!", "?", "\n")):
            protegidos.add(m.group(0).lower())

    for m in RE_TODO_MAYUSCULAS.finditer(texto_original):
        protegidos.add(m.group(0).lower())

    return protegidos


def entidades(texto_limpio, texto_original=None):
    """
    Personas, lugares e instituciones. Las dos lecturas se complementan: en
    minusculas el NER reconoce 'pereira' pero no 'hakim'; con las mayusculas del
    original reconoce 'Hakim' pero se pierde en notas gritadas.

    El NER se equivoca en frases cortas y en minusculas: llego a marcar
    'consutla' y 'malestra' como nombres, y eso bloqueaba dos correcciones
    validas. Por eso una entidad solo protege si ademas es una palabra que
    spaCy conoce, o venia con mayuscula en la nota original.
    """
    if not (USAR_SPACY and PROTEGER_ENTIDADES):
        return set()

    encontradas = linguistica.entidades(texto_limpio)
    if texto_original and not texto_gritado(texto_original):
        encontradas = encontradas | linguistica.entidades(texto_original)

    if not encontradas:
        return encontradas

    # Solo cuenta la mayuscula que no se explica por la posicion. Tomar
    # cualquier mayuscula del texto vacia el filtro cuando el texto viene
    # recapitalizado por casing.py, porque ahi toda oracion abre en mayuscula
    # y hasta un typo como 'Pacinete' pasaria por nombre propio.
    con_mayuscula = casing.mayusculas_informativas(texto_original)

    # Lo que el corpus sabe del token pesa mas que lo que diga el NER sobre una
    # nota suelta: casing.py lo aprendio de miles de notas bien escritas.
    del_corpus = casing.nombres_propios() | casing.siglas() if casing.disponible() else set()

    return {e for e in encontradas
            if e in con_mayuscula or e in del_corpus or linguistica.en_vocabulario(e)}


def esta_protegido(token, protegidos=()):
    """Diccionario, patrones, numeros y entidades. Sin vocabulario de spaCy."""
    if tiene_numero(token):
        return True

    token = normalizar(token)
    if not token:
        return True
    if token in SIGLAS or token in protegidos:
        return True
    return any(p.search(token) for p in PATRONES)


def es_palabra_conocida(token):
    """
    spaCy reconoce farmacos y terminologia que LanguageTool marca como error.

    Se evalua SOLO sobre la palabra original, nunca sobre los candidatos: casi
    toda correccion correcta ('paciente', 'dolor') esta en el vocabulario, y
    filtrarla ahi bloquea el pipeline entero.
    """
    if not (USAR_SPACY and PROTEGER_POR_VOCABULARIO):
        return False
    return linguistica.en_vocabulario(normalizar(token))


def forma_aceptable(original, candidato):
    """
    Criterio puramente ortografico: longitud, distancia de edicion y numeros.

    Las verificaciones clinicas (morfemas, truncamiento, antonimos, familia de
    sufijo) NO estan aqui: viven en terminologia.py, que es el unico punto donde
    se decide sobre el significado y donde queda registrada cada alarma. Tener
    un solo guardian evita que una regla se aplique en un motor y no en el otro.
    """
    if len(original) < LONGITUD_MINIMA:
        return False
    if abs(len(original) - len(candidato)) > DIFERENCIA_LONGITUD:
        return False
    if len(candidato.split()) != len(original.split()):
        return False
    if tiene_numero(original) or tiene_numero(candidato):
        return False
    return DamerauLevenshtein.distance(original, candidato) <= DISTANCIA_MAXIMA

