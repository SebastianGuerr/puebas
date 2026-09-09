"""
Criterios de protección: qué tokens no deben corregirse nunca.

Es el guardián ortográfico del pipeline y lo consultan tanto el corrector de
LanguageTool como el de SymSpell y la fase de normalización. Está separado de
esos motores a propósito: una regla que solo se aplicara en uno de ellos dejaría
un hueco por el que pasaría el mismo error.

Capas de protección, en el orden en que actúan:

  1. Números y medidas    nada que contenga un dígito se toca.
  2. Diccionario          siglas, fármacos, epónimos, marcas y términos.
  3. Patrones             vértebras (l5), dosis (5mg), tokens de una letra.
  4. Entidades            personas, lugares e instituciones de la nota.
  5. Vocabulario          palabras reales que LanguageTool marca por error.
  6. Forma                longitud mínima, distancia de edición y diferencia
                          de longitud entre original y candidato.

Lo que se decide mirando únicamente la forma de la palabra (morfemas médicos,
truncamientos, sufijos de fármaco) vive en `morfologia.py`. Este módulo lo
reexporta para que el resto del paquete pueda seguir invocándolo como
`reglas.morfemas` o `reglas.sin_tildes`.

Las verificaciones que dependen del SIGNIFICADO clínico tampoco están aquí:
las concentra `fase2_ortografia/terminologia.py`, que es el único punto donde se
veta un cambio por motivo clínico y donde queda registrado.
"""

import json
import re
from pathlib import Path

from rapidfuzz.distance import DamerauLevenshtein

from NLP import rutas
from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.recursos import casing
from NLP.nucleo.morfologia import (  # reexportado: el resto del paquete los usa como reglas.X
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

RUTA_SIGLAS = rutas.DICCIONARIO_SIGLAS

LONGITUD_MINIMA = 5          # tokens mas cortos solo via correcciones directas
DISTANCIA_MAXIMA = 2         # ediciones permitidas entre original y candidato
DIFERENCIA_LONGITUD = 1      # letras de diferencia permitidas

PROPORCION_MAYUSCULAS = 0.9
LARGO_MAXIMO_SIGLA = 6

USAR_SPACY = True
PROTEGER_POR_VOCABULARIO = True
PROTEGER_ENTIDADES = True

# Contenido del diccionario, poblado por cargar(). Son estructuras de módulo
# porque se consultan desde varios motores dentro del bucle de corrección.
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


# ==========================================================
# NOMBRES PROPIOS POR CONTEXTO
# ==========================================================

# Palabras que anuncian un nombre propio inmediatamente despues. Es la unica
# senal disponible en notas escritas todas en mayusculas, donde ni el NER ni la
# deteccion por capitalizacion tienen con que trabajar. Sin esta regla, el
# corrector convierte 'dr ceron' en 'dr cero' o 'confamiliar pereira' en
# 'conciliar pereira'.
#
# La lista incluye solo titulos y lugares. Se dejaron fuera a proposito los
# terminos de parentesco ('paciente', 'hijo', 'esposa') y los verbos de remision
# ('remitido', 'traido'): van seguidos de sintomas mucho mas a menudo que de
# nombres, y protegerlos bloqueaba correcciones validas.
DISPARADORES_NOMBRE = {
    "dr", "dra", "doctor", "doctora", "sr", "sra", "srta", "don", "dona", "doña",
    "senor", "señor", "senora", "señora", "clinica", "clínica", "hospital",
    "ips", "eps", "arl", "fundacion", "fundación", "barrio", "vereda",
    "corregimiento", "municipio", "finca", "urbanizacion", "urbanización",
}
VENTANA_NOMBRE = 2   # cuantos tokens despues del disparador se protegen


def tokens_protegidos_por_contexto(texto):
    """
    Tokens que aparecen justo después de un disparador de nombre propio, dentro
    de una ventana de VENTANA_NOMBRE palabras. Devuelve un conjunto en
    minúscula.
    """
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
    """
    Lee el diccionario de siglas y llena las estructuras del módulo. Devuelve el
    conjunto de siglas cargadas.

    El archivo agrupa las entradas por tema (siglas, fármacos, epónimos...) y
    admite además cuatro claves de control:

        _siglas_inequivocas    las únicas que pueden expandirse sin contexto
        _siglas_ambiguas       bloqueadas aunque superen las comprobaciones
        _grupos_expandibles    qué grupos temáticos pueden expandirse
        patrones_protegidos    expresiones regulares que nunca se corrigen

    y dos claves de datos: `no_restaurar_mayuscula` y `correcciones_directas`.
    Puede llamarse varias veces: cada llamada vacía las estructuras antes de
    volver a llenarlas.
    """
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
            # grupo temático {sigla: significado}
            for sigla, significado in valor.items():
                sigla = sigla.lower()
                SIGLAS.add(sigla)
                SIGNIFICADOS[sigla] = significado
                if clave in expandibles:
                    EXPANDIBLES[sigla] = significado
        else:
            # grupo temático como lista simple de términos protegidos
            SIGLAS.update(x.lower() for x in valor)

    return SIGLAS


# ==========================================================
# UTILIDADES
# ==========================================================

def texto_gritado(texto):
    """
    True si la nota está escrita casi toda en mayúsculas. En ese caso no hay
    contraste de capitalización que leer, y las defensas que dependen de él
    quedan inutilizadas.
    """
    letras = [c for c in str(texto) if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


# ==========================================================
# PROTECCIÓN
# ==========================================================

def detectar_protegidos(texto_original):
    """
    Nombres propios y siglas leídos del texto tal como se escribió, antes de
    limpiarlo.

    Reconoce dos señales: mayúscula inicial que no se explica por el comienzo de
    una frase, y palabras cortas escritas enteras en mayúscula. Solo sirve en
    notas con capitalización mixta; en una nota gritada devuelve un conjunto
    vacío y la protección recae en el diccionario y el reconocedor de entidades.
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
    Personas, lugares e instituciones presentes en la nota.

    Se consultan las dos versiones del texto porque se complementan: sobre el
    texto en minúsculas el reconocedor identifica topónimos frecuentes, y sobre
    el original conserva los epónimos que solo se distinguen por la mayúscula.

    El reconocedor se equivoca en frases cortas y en minúsculas, llegando a
    marcar como nombre propio palabras mal escritas, lo que bloquearía su
    corrección. Por eso una entidad solo protege si además se confirma por otra
    vía: venía con mayúscula informativa en el original, el corpus la conoce como
    nombre propio o sigla, o spaCy la tiene en su vocabulario.
    """
    if not (USAR_SPACY and PROTEGER_ENTIDADES):
        return set()

    encontradas = linguistica.entidades(texto_limpio)
    if texto_original and not texto_gritado(texto_original):
        encontradas = encontradas | linguistica.entidades(texto_original)

    if not encontradas:
        return encontradas

    # Solo cuenta la mayuscula que no se explica por la posicion: si se
    # aceptara cualquier mayuscula, un texto ya recapitalizado (donde toda
    # oracion abre en mayuscula) dejaria pasar como nombre propio hasta un typo.
    con_mayuscula = casing.mayusculas_informativas(texto_original)

    # Lo que el corpus sabe del token pesa mas que lo que diga el reconocedor
    # sobre una nota suelta, porque se aprendio de miles de notas.
    del_corpus = casing.nombres_propios() | casing.siglas() if casing.disponible() else set()

    return {e for e in encontradas
            if e in con_mayuscula or e in del_corpus or linguistica.en_vocabulario(e)}


def esta_protegido(token, protegidos=()):
    """
    True si el token no puede corregirse por diccionario, patrón, número o por
    figurar en el conjunto `protegidos` que aporta quien llama. No consulta el
    vocabulario de spaCy: eso lo decide es_palabra_conocida().
    """
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
    True si spaCy reconoce el token, que entonces se considera una palabra real
    y queda protegido. Cubre fármacos y terminología que LanguageTool marca como
    error.

    Debe evaluarse solo sobre la palabra original y nunca sobre los candidatos:
    casi toda corrección correcta está en el vocabulario, de modo que aplicarlo
    a los candidatos anularía el corrector entero.
    """
    if not (USAR_SPACY and PROTEGER_POR_VOCABULARIO):
        return False
    return linguistica.en_vocabulario(normalizar(token))


def forma_aceptable(original, candidato):
    """
    True si el par (original, candidato) supera el criterio puramente
    ortográfico: longitud mínima, misma cantidad de palabras, ausencia de
    dígitos y distancia de edición dentro del máximo permitido.

    No evalúa el significado: de eso se ocupa `terminologia.py`.
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
