"""
Alcance de la negacion clinica (E3.7, NLP/docs/PLAN.md §8). Disparadores en
NLP/datos/lexicos/negacion.txt; algoritmo y decisiones en
NLP/docs/bitacora/2026-09-16-E3.7.md. Ventana con terminadores, no medspaCy
(ver bitacora, seccion Decision). Prefijar con NEG_ antes de vectorizar es
tarea de E5.2; este modulo solo calcula el alcance.
"""

import re
from pathlib import Path

from NLP.nucleo import morfologia

RUTA_NEGACION = Path(__file__).resolve().parent.parent / "datos" / "lexicos" / "negacion.txt"

# Tokens de contenido que entran en la ventana de alcance. No cuenta la
# puntuacion: 'niega dolor,' no debe gastar ventana en la coma.
RE_TOKEN = re.compile(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+")

# Puntuacion que cierra el alcance (PLAN.md §8, ficha E3.7: "terminadores de
# alcance: pero, aunque, salvo, excepto, puntuacion"). La coma se incluye
# porque en la nota de triage separa clausulas de polaridad distinta
# ('niega dolor, refiere cefalea'): sin ella el alcance se comia la clausula
# siguiente. Los dos puntos se excluyen a proposito: en la nota de triage
# introducen un resultado o un rotulo ('prueba de embarazo: negativo',
# 'ta: 120/80'), no separan clausulas, y cortar ahi vaciaba el alcance hacia
# atras de un disparador 'post' (ver bitacora, casos de la evaluacion
# sintetica).
RE_FIN_ORACION = re.compile(r"[.,;!?\n]")

# Tokens de contenido que abarca el alcance a cada lado del disparador.
# INVESTIGACION.md §6.2 cita 3-4 (NegEx sobre informes de radiologia en
# ingles, un hallazgo por disparador). La nota de triage suele enumerar
# varios sintomas tras un 'niega' ('niega fiebre, escalofrios, sudoracion
# nocturna'): con 4 se truncaban listas reales del conjunto sintetico de la
# bitacora sin que hubiera terminador ni puntuacion de por medio. Se sube a 8
# como respaldo; el limite real en el texto corrido de triage lo pone casi
# siempre la coma o el punto, no la ventana (ver Decision en la bitacora).
VENTANA_TOKENS = 8

_CATEGORIAS = ("pre", "post", "pseudo", "terminador")
_RE_CATEGORIA = re.compile(r"^#\s*categoria:\s*(\w+)")

_LISTAS = {c: [] for c in _CATEGORIAS}
_PROCESADORES = {}   # categoria -> KeywordProcessor | None
_RESPALDOS = {}       # categoria -> (patron, categoria) | None
_CARGADO = False


def _variantes(forma):
    """La forma tal cual y, si difiere, su version sin tildes."""
    forma = forma.strip().lower()
    plano = morfologia.sin_tildes(forma)
    return {forma, plano} if plano != forma else {forma}


def cargar(ruta=RUTA_NEGACION):
    """
    Lee datos/lexicos/negacion.txt, clasifica cada forma por la seccion
    '# categoria: <nombre>' que la precede y construye un buscador por
    categoria. Devuelve el numero de formas cargadas por categoria.
    """
    global _CARGADO
    for c in _CATEGORIAS:
        _LISTAS[c].clear()

    categoria_actual = None
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        m = _RE_CATEGORIA.match(linea)
        if m:
            categoria_actual = m.group(1)
            continue
        if not linea.strip() or linea.lstrip().startswith("#"):
            continue
        if categoria_actual in _LISTAS:
            _LISTAS[categoria_actual].append(linea.strip().lower())

    for categoria in _CATEGORIAS:
        formas = _LISTAS[categoria]
        _PROCESADORES[categoria] = _construir_flashtext(formas)
        if _PROCESADORES[categoria] is None:
            _RESPALDOS[categoria] = _construir_regex(formas)

    _CARGADO = True
    return {c: len(_LISTAS[c]) for c in _CATEGORIAS}


def _asegurar_cargado():
    if not _CARGADO:
        cargar()


def _construir_flashtext(formas):
    try:
        from flashtext import KeywordProcessor
    except ModuleNotFoundError:
        return None
    if not formas:
        return None
    kp = KeywordProcessor(case_sensitive=False)
    # igual que fase3_normalizacion/normalizacion.py: sin esto una vocal
    # acentuada o la ene cuentan como limite de palabra y la busqueda se rompe
    kp.non_word_boundaries |= set("áéíóúüñÁÉÍÓÚÜÑ")
    for forma in formas:
        for variante in _variantes(forma):
            kp.add_keyword(variante, forma)
    return kp


def _construir_regex(formas):
    if not formas:
        return None
    claves = set()
    for forma in formas:
        claves |= _variantes(forma)
    claves = sorted(claves, key=len, reverse=True)
    patron = re.compile(r"\b(%s)\b" % "|".join(re.escape(c) for c in claves), re.IGNORECASE)
    return patron


def _coincidencias(texto, categoria):
    """Lista de (inicio, fin, forma_canonica) para una categoria, sin solapar."""
    _asegurar_cargado()
    procesador = _PROCESADORES.get(categoria)
    if procesador is not None:
        return [(i, f, forma) for forma, i, f in procesador.extract_keywords(texto, span_info=True)]
    patron = _RESPALDOS.get(categoria)
    if patron is None:
        return []
    return [(m.start(), m.end(), m.group(0).lower()) for m in patron.finditer(texto)]


def _se_solapan(a, b):
    return a[0] < b[1] and b[0] < a[1]


def _quitar_solapados_con_pseudo(disparadores, pseudos):
    """Descarta un disparador pre/post si su tramo cae dentro de un pseudo."""
    return [d for d in disparadores if not any(_se_solapan(d, p) for p in pseudos)]


# ==========================================================
# LIMITES DEL ALCANCE
# ==========================================================

def _tokens(texto):
    return list(RE_TOKEN.finditer(texto))


def _limite_adelante(texto, desde, terminadores, ventana):
    """Posicion donde termina el alcance que se abre en `desde` y avanza."""
    limite = len(texto)

    fin_oracion = RE_FIN_ORACION.search(texto, desde)
    if fin_oracion:
        limite = min(limite, fin_oracion.start())

    for ti, tf in terminadores:
        if ti >= desde:
            limite = min(limite, ti)
            break

    tokens = [t for t in _tokens(texto) if t.start() >= desde and t.start() < limite]
    if len(tokens) > ventana:
        limite = min(limite, tokens[ventana].start())

    return max(limite, desde)


def _limite_atras(texto, hasta, terminadores, ventana):
    """Posicion donde empieza el alcance que se cierra en `hasta` mirando atras."""
    limite = 0

    for m in re.finditer(RE_FIN_ORACION, texto[:hasta]):
        limite = max(limite, m.end())

    for ti, tf in terminadores:
        if tf <= hasta:
            limite = max(limite, tf)

    tokens = [t for t in _tokens(texto) if t.end() <= hasta and t.end() > limite]
    if len(tokens) > ventana:
        limite = max(limite, tokens[-ventana].start())

    return min(limite, hasta)


def alcance(texto, ventana=VENTANA_TOKENS):
    """
    Tramos (inicio, fin) de `texto` bajo el efecto de una negacion, fusionados
    y ordenados. Ver NLP/docs/bitacora/2026-09-16-E3.7.md para el algoritmo
    (ventana, terminadores, exclusion de 'pseudo').
    """
    if not texto:
        return []
    texto = str(texto)

    pseudos = [(i, f) for i, f, _ in _coincidencias(texto, "pseudo")]
    terminadores = sorted((i, f) for i, f, _ in _coincidencias(texto, "terminador"))

    pre = _quitar_solapados_con_pseudo(
        [(i, f) for i, f, _ in _coincidencias(texto, "pre")], pseudos)
    post = _quitar_solapados_con_pseudo(
        [(i, f) for i, f, _ in _coincidencias(texto, "post")], pseudos)

    tramos = []
    for _, fin_disparador in pre:
        fin = _limite_adelante(texto, fin_disparador, terminadores, ventana)
        if fin > fin_disparador:
            tramos.append((fin_disparador, fin))
    for inicio_disparador, _ in post:
        inicio = _limite_atras(texto, inicio_disparador, terminadores, ventana)
        if inicio < inicio_disparador:
            tramos.append((inicio, inicio_disparador))

    return _fusionar(sorted(tramos))


def _fusionar(tramos):
    """Une tramos (inicio, fin) ordenados que se tocan o se solapan."""
    fusionados = []
    for inicio, fin in tramos:
        if fusionados and inicio <= fusionados[-1][1]:
            fusionados[-1] = (fusionados[-1][0], max(fusionados[-1][1], fin))
        else:
            fusionados.append((inicio, fin))
    return fusionados


def negado(texto, inicio_token, fin_token):
    """True si el tramo [inicio_token, fin_token) del texto cae en algun alcance."""
    return any(_se_solapan((inicio_token, fin_token), t) for t in alcance(texto))


def marcar(texto, prefijo="NEG_"):
    """
    Texto con `prefijo` antepuesto a cada palabra dentro de un alcance de
    negacion. Para uso de E5.2 (prefijo antes de vectorizar); no se invoca
    todavia desde ninguna fase del pipeline.
    """
    if not texto:
        return texto
    texto = str(texto)
    tramos = alcance(texto)
    if not tramos:
        return texto

    partes, ultimo = [], 0
    for token in _tokens(texto):
        en_alcance = any(_se_solapan((token.start(), token.end()), t) for t in tramos)
        if en_alcance:
            partes.append(texto[ultimo:token.start()])
            partes.append(prefijo + token.group(0))
            ultimo = token.end()
    partes.append(texto[ultimo:])
    return "".join(partes)


def diagnosticar(texto):
    """Disparadores encontrados por categoria y el alcance resultante. Inspeccion manual."""
    _asegurar_cargado()
    return {
        "pre": _coincidencias(texto, "pre"),
        "post": _coincidencias(texto, "post"),
        "pseudo": _coincidencias(texto, "pseudo"),
        "terminador": _coincidencias(texto, "terminador"),
        "alcance": alcance(texto),
        "marcado": marcar(texto),
    }
