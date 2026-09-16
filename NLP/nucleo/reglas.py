"""
Criterios de proteccion: que tokens no deben corregirse nunca. Guardian
ortografico compartido por LanguageTool, SymSpell y la fase de
normalizacion. Reexporta `morfologia.py` (forma) como `reglas.X`; lo que
depende del SIGNIFICADO clinico vive en `terminologia.py`. Ver
ARQUITECTURA.md §2.2 (`reglas.py`) para las capas de proteccion.
"""

import json
import re
from pathlib import Path

from rapidfuzz.distance import DamerauLevenshtein

from NLP import rutas
from NLP.nucleo import linguistica
from NLP.recursos import casing
from NLP.recursos import lexico
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
RUTA_SIGLAS_PROTEGIDAS = rutas.DATOS / "lexicos" / "siglas_protegidas.txt"

# E3.5/E3.6: listas curadas de farmacos, lugares y nombres propios, cada una
# con su propio archivo y su propia bandera (PLAN.md S3, principio 8). Mismo
# patron que SIGLAS_PROTEGIDAS_MANUAL (E3.2): archivo de una forma por
# linea, cargado aparte para poder auditar y medir cada lista por separado.
# Ver bitacora/2026-09-16-E3.5.md y bitacora/2026-09-16-E3.6.md.
RUTA_FARMACOS = rutas.DATOS / "lexicos" / "farmacos.txt"
RUTA_LUGARES = rutas.DATOS / "lexicos" / "lugares.txt"
RUTA_NOMBRES = rutas.DATOS / "lexicos" / "nombres.txt"

LONGITUD_MINIMA = 5          # tokens mas cortos solo via correcciones directas
DISTANCIA_MAXIMA = 2         # ediciones permitidas entre original y candidato
DIFERENCIA_LONGITUD = 1      # letras de diferencia permitidas

PROPORCION_MAYUSCULAS = 0.9
LARGO_MAXIMO_SIGLA = 6

USAR_SPACY = True
PROTEGER_POR_VOCABULARIO = True
PROTEGER_ENTIDADES = True

# E3.2: segunda via de proteccion para siglas de triage, independiente de
# diccionario_siglas.json (ver docs/decisiones y bitacora/2026-09-16-E3.2.md).
# Tras bandera para poder medir con y sin ella (PLAN.md §3, principio 8).
PROTEGER_SIGLAS_LISTA_MANUAL = True

# E3.5/E3.6: banderas independientes para cada lista curada nueva.
PROTEGER_FARMACOS = True
PROTEGER_LUGARES = True
PROTEGER_NOMBRES = True

# E3.4: segunda via de proteccion para la terminologia de DISTEMIST/SympTEMIST
# integrada en recursos/lexico.py (fuente lexico.GAZETTEER). pesos.peso() ya
# consulta lexico.fuente() para esa fuente; esta bandera cierra el mismo
# hueco que E3.2 documento para esta_protegido() (la via de LanguageTool y
# SymSpell, independiente de la via de pesos.py). Ver bitacora/2026-09-16-E3.4.md.
PROTEGER_GAZETTEER_LEXICO = True

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

# E3.2: lista independiente de siglas_protegidas.txt, cargada aparte del
# diccionario para que se pueda auditar y medir por separado.
SIGLAS_PROTEGIDAS_MANUAL = set()

# E3.5/E3.6: mismo patron, una lista por recurso. Se guardan ya plegadas
# (sin tildes) porque los nombres propios de estas fuentes (topónimos,
# nombres de persona) sí llevan tilde en el origen (DIVIPOLA, REPS) y la
# nota de triage casi siempre no; esta_protegido() pliega el token de
# entrada de la misma forma antes de comparar (ver más abajo).
FARMACOS_PROTEGIDOS = set()
LUGARES_PROTEGIDOS = set()
NOMBRES_PROTEGIDOS = set()

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
    Lee el diccionario de siglas y llena las estructuras del modulo (formato
    del archivo: ver ARQUITECTURA.md §2.2, `reglas.py`). Puede llamarse
    varias veces: cada llamada vacia antes de volver a llenar. Devuelve el
    conjunto de siglas.
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

    cargar_siglas_protegidas()
    cargar_farmacos()
    cargar_lugares()
    cargar_nombres()
    return SIGLAS


def cargar_siglas_protegidas(ruta=RUTA_SIGLAS_PROTEGIDAS):
    """
    Lee `datos/lexicos/siglas_protegidas.txt` (una forma por linea, `#`
    comenta) en `SIGLAS_PROTEGIDAS_MANUAL` y lo devuelve. Sin archivo, deja
    el conjunto vacio sin fallar.
    """
    SIGLAS_PROTEGIDAS_MANUAL.clear()
    ruta = Path(ruta)
    if not ruta.exists():
        return SIGLAS_PROTEGIDAS_MANUAL
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        SIGLAS_PROTEGIDAS_MANUAL.add(linea.lower())
    return SIGLAS_PROTEGIDAS_MANUAL


def _cargar_lista(ruta, destino):
    """Lee una lista de una forma por linea (`#` comenta) en `destino`."""
    destino.clear()
    ruta = Path(ruta)
    if not ruta.exists():
        return destino
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        destino.add(sin_tildes(linea.lower()))
    return destino


def cargar_farmacos(ruta=RUTA_FARMACOS):
    """Lee `datos/lexicos/farmacos.txt` (E3.5) en `FARMACOS_PROTEGIDOS`."""
    return _cargar_lista(ruta, FARMACOS_PROTEGIDOS)


def cargar_lugares(ruta=RUTA_LUGARES):
    """Lee `datos/lexicos/lugares.txt` (E3.6) en `LUGARES_PROTEGIDOS`."""
    return _cargar_lista(ruta, LUGARES_PROTEGIDOS)


def cargar_nombres(ruta=RUTA_NOMBRES):
    """Lee `datos/lexicos/nombres.txt` (E3.6) en `NOMBRES_PROTEGIDOS`."""
    return _cargar_lista(ruta, NOMBRES_PROTEGIDOS)


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
    Nombres propios y siglas leidos del texto tal como se escribio (mayuscula
    inicial no explicada por posicion, o palabra corta toda en mayuscula).
    En nota gritada devuelve vacio: la proteccion recae en el diccionario.
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
    Personas, lugares e instituciones presentes en la nota, confirmadas por
    una segunda via (spaCy solo se equivoca menos con ayuda). Ver
    ARQUITECTURA.md §2.2 (`reglas.py`) para el porque de cada fuente.
    """
    if not (USAR_SPACY and PROTEGER_ENTIDADES):
        return set()

    # se consultan las dos versiones del texto porque se complementan: en
    # minusculas el reconocedor identifica toponimos frecuentes, y sobre el
    # original conserva los eponimos que solo se distinguen por la mayuscula
    encontradas = linguistica.entidades(texto_limpio)
    if texto_original and not texto_gritado(texto_original):
        encontradas = encontradas | linguistica.entidades(texto_original)

    if not encontradas:
        return encontradas

    # el reconocedor tambien marca como nombre propio palabras mal escritas
    # en frases cortas o en minusculas, asi que una entidad solo protege si
    # se confirma por otra via

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
    if PROTEGER_SIGLAS_LISTA_MANUAL and token in SIGLAS_PROTEGIDAS_MANUAL:
        return True

    # E3.5/E3.6/E3.4: las listas curadas se guardan sin tildes (ver
    # cargar_farmacos/_lugares/_nombres); se pliega tambien el token de
    # entrada para no depender de que la nota lleve la tilde correcta.
    plegado = sin_tildes(token)
    if PROTEGER_FARMACOS and plegado in FARMACOS_PROTEGIDOS:
        return True
    if PROTEGER_LUGARES and plegado in LUGARES_PROTEGIDOS:
        return True
    if PROTEGER_NOMBRES and plegado in NOMBRES_PROTEGIDOS:
        return True
    if PROTEGER_GAZETTEER_LEXICO and lexico.fuente(token) == lexico.GAZETTEER:
        return True

    return any(p.search(token) for p in PATRONES)


def es_palabra_conocida(token):
    """
    True si spaCy reconoce el token (se protege). Evaluar solo sobre la
    palabra original, nunca sobre candidatos: aplicarlo a un candidato
    anularia el corrector, porque casi toda correccion ya esta en el vocabulario.
    """
    if not (USAR_SPACY and PROTEGER_POR_VOCABULARIO):
        return False
    return linguistica.en_vocabulario(normalizar(token))


def forma_aceptable(original, candidato):
    """
    True si el par supera el criterio ortografico: longitud minima, mismo
    numero de palabras, sin digitos, distancia de edicion dentro del maximo.
    No evalua el significado (ver `terminologia.py`).
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
