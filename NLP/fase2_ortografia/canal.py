"""
Canal ruidoso con prior de dominio (Kernighan 1990; Brill y Moore 2000):
puntúa candidatos por P(candidato | escrito) = P(escrito | candidato) *
P(candidato), en vez de decidir solo por frecuencia.

    P(escrito | candidato)   EL CANAL. Cuántas ediciones separan las dos
                              formas y de qué tipo (sustitución, inserción,
                              borrado, transposición), con un coste por tipo
                              aprendido sobre salidas/pares_correccion.csv
                              (entrenar_desde_pares_correccion()).
    P(candidato)              EL PRIOR DE DOMINIO. Unigramas de
                              datos/lexicos/corpus_frecuencia.tsv (34.602
                              formas, contadas sobre las 94.226 notas de la
                              base de datos) y bigramas contados aquí mismo
                              sobre triage_limpio.csv, interpolados.

Módulo aparte y tras bandera (E4.4): no sustituye por defecto el desempate
por frecuencia que ya usan `candidatos.py` y `vocabulario.py`; se mide contra
él sobre `salidas/evaluacion/autoinducido.csv`. Medición y decisión:
docs/decisiones/2026-09-16-E4.4.md.

NO SE ENTRENA CON `autoinducido.csv`: ese archivo es el conjunto de medición
de este ítem (perturbaciones sintéticas con su forma correcta conocida); usar
sus pares para entrenar el canal contaminaría la evaluación. La única fuente
de erratas reales sin ese problema es `salidas/pares_correccion.csv` (E2.4),
correcciones que el propio corrector ya aplicó.
"""

import csv
import math
import re
from collections import Counter

from NLP import rutas

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")

# ==========================================================
# EL CANAL: TIPO DE EDICION QUE SEPARA DOS FORMAS
# ==========================================================

# Coste de partida (= Levenshtein/Damerau con pesos iguales) si nunca se
# entrena. entrenar_canal() lo reemplaza por -log(P(operacion)), aprendida
# sobre pares reales.
_COSTE_OP = {
    "sustitucion": 1.0,
    "insercion": 1.0,
    "borrado": 1.0,
    "transposicion": 1.0,
}
_ENTRENADO = False


def _alinear(a, b):
    """
    Lista de operaciones (sin 'igual') que transforman `a` en `b`, con
    Damerau-Levenshtein restringido (la transposición no se solapa consigo
    misma; misma restricción que `contexto._distancia`).

    A diferencia de esa función, aquí hace falta RECONSTRUIR el camino: el
    canal no pregunta cuántas ediciones hay, sino de qué tipo, porque cada
    tipo pesa distinto.
    """
    n, m = len(a), len(b)
    d = [[0] * (m + 1) for _ in range(n + 1)]
    op = [[None] * (m + 1) for _ in range(n + 1)]
    for i in range(n + 1):
        d[i][0], op[i][0] = i, "borrado"
    for j in range(m + 1):
        d[0][j], op[0][j] = j, "insercion"
    op[0][0] = None

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            coste_sub = 0 if a[i - 1] == b[j - 1] else 1
            opciones = [
                (d[i - 1][j] + 1, "borrado"),
                (d[i][j - 1] + 1, "insercion"),
                (d[i - 1][j - 1] + coste_sub,
                 "igual" if coste_sub == 0 else "sustitucion"),
            ]
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                opciones.append((d[i - 2][j - 2] + 1, "transposicion"))
            d[i][j], op[i][j] = min(opciones, key=lambda x: x[0])

    ops, i, j = [], n, m
    while i > 0 or j > 0:
        tipo = op[i][j]
        if tipo == "transposicion":
            ops.append(tipo)
            i, j = i - 2, j - 2
        elif tipo == "borrado":
            ops.append(tipo)
            i -= 1
        elif tipo == "insercion":
            ops.append(tipo)
            j -= 1
        else:
            if tipo == "sustitucion":
                ops.append(tipo)
            i, j = i - 1, j - 1
    return ops


def entrenar_canal(pares):
    """
    Estima -log(P(operacion)) contando los tipos de edición sobre
    `pares` = [(correccion, error, peso), ...], con suavizado de Laplace.
    `peso` deja pesar cada par por sus ocurrencias reales en el corpus.
    """
    global _ENTRENADO
    conteo = Counter()
    for correccion, error, peso in pares:
        correccion, error = str(correccion).lower(), str(error).lower()
        if correccion == error:
            continue
        for tipo in _alinear(correccion, error):
            conteo[tipo] += peso

    total = sum(conteo.values())
    if total == 0:
        return dict(_COSTE_OP)

    v = len(_COSTE_OP)
    for tipo in _COSTE_OP:
        prob = (conteo.get(tipo, 0) + 1) / (total + v)
        _COSTE_OP[tipo] = -math.log(prob)
    _ENTRENADO = True
    return dict(_COSTE_OP)


def entrenado():
    """True si el canal usa costes aprendidos y no el valor de partida."""
    return _ENTRENADO


def entrenar_desde_pares_correccion(ruta=None):
    """
    Entrena el canal sobre `salidas/pares_correccion.csv` (E2.4): pares
    (original, corrección) que el corrector ya aplicó de verdad sobre este
    corpus, ponderados por `ocurrencias`. Es la única fuente de erratas
    reales que no es el conjunto de medición de este ítem.
    """
    ruta = ruta or (rutas.SALIDAS / "pares_correccion.csv")
    pares = []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        for fila in csv.DictReader(f):
            try:
                peso = max(int(fila.get("ocurrencias", 1)), 1)
            except (TypeError, ValueError):
                peso = 1
            pares.append((fila["correccion"], fila["original"], peso))
    return entrenar_canal(pares)


def log_canal(candidato, escrita):
    """
    log P(escrita | candidato): más alta cuanto más barata (según los costes
    aprendidos) es la edición que convierte el candidato en lo escrito.
    """
    ops = _alinear(str(candidato).lower(), str(escrita).lower())
    return -sum(_COSTE_OP[tipo] for tipo in ops)


# ==========================================================
# EL PRIOR DE DOMINIO: UNIGRAMAS Y BIGRAMAS DEL CORPUS
# ==========================================================

# Interpolacion lineal simple entre bigrama y unigrama (Jelinek-Mercer). No
# hay datos de desarrollo para ajustar el peso con mas cuidado; 0.6 favorece
# levemente el contexto inmediato sobre la frecuencia aislada, y se deja
# como constante medible, no una eleccion definitiva.
PESO_BIGRAMA = 0.6

_UNIGRAMAS = Counter()
_BIGRAMAS = Counter()
_TOTAL_UNIGRAMAS = 0
_V = 0
_PRIOR_CARGADO = False


def cargar_prior(ruta_unigramas=None, textos_bigramas=None):
    """
    Carga el prior de dominio.

        ruta_unigramas    datos/lexicos/corpus_frecuencia.tsv por defecto:
                          34.602 formas contadas sobre las 94.226 notas de la
                          base de datos (no sobre este CSV).
        textos_bigramas   iterable de textos sobre los que CONTAR bigramas
                          aquí mismo (normalmente `texto_original` de
                          triage_limpio.csv). Sin este argumento, log_prior()
                          usa solo el unigrama.

    Debe llamarse antes de puntuar ningún candidato.
    """
    global _TOTAL_UNIGRAMAS, _V, _PRIOR_CARGADO
    ruta = ruta_unigramas or (rutas.DATOS / "lexicos" / "corpus_frecuencia.tsv")
    _UNIGRAMAS.clear()
    if ruta.exists():
        for linea in ruta.read_text(encoding="utf-8").splitlines():
            if linea.startswith("#") or not linea.strip():
                continue
            partes = linea.split("\t")
            if len(partes) >= 2 and partes[1].isdigit():
                _UNIGRAMAS[partes[0]] = int(partes[1])

    _BIGRAMAS.clear()
    if textos_bigramas:
        for texto in textos_bigramas:
            palabras = RE_PALABRA.findall(str(texto).lower())
            for a, b in zip(palabras, palabras[1:]):
                _BIGRAMAS[(a, b)] += 1

    _TOTAL_UNIGRAMAS = sum(_UNIGRAMAS.values())
    _V = max(len(_UNIGRAMAS), 1)
    _PRIOR_CARGADO = True
    return len(_UNIGRAMAS), len(_BIGRAMAS)


def disponible():
    """True si hay prior de dominio cargado."""
    return _PRIOR_CARGADO and _TOTAL_UNIGRAMAS > 0


def log_prior(candidato, anterior=None):
    """
    log P(candidato), interpolando bigrama (si se cargaron bigramas y se
    conoce la palabra anterior) con el unigrama, suavizado con Laplace.
    """
    candidato = str(candidato).lower()
    p_uni = (_UNIGRAMAS.get(candidato, 0) + 1) / (_TOTAL_UNIGRAMAS + _V)
    if anterior and _BIGRAMAS:
        anterior = str(anterior).lower()
        num = _BIGRAMAS.get((anterior, candidato), 0) + 1
        den = _UNIGRAMAS.get(anterior, 0) + _V
        p_bi = num / den
        p = PESO_BIGRAMA * p_bi + (1 - PESO_BIGRAMA) * p_uni
    else:
        p = p_uni
    return math.log(p)


# ==========================================================
# DECISION
# ==========================================================

PESO_PRIOR = 1.0       # cuanto pesa el prior de dominio frente al canal
MARGEN_MINIMO = 1.0    # el primero debe superar al segundo por esto en log-prob


def puntuar(escrita, candidato, anterior=None):
    """log P(escrita | candidato) + PESO_PRIOR * log P(candidato)."""
    return log_canal(candidato, escrita) + PESO_PRIOR * log_prior(candidato, anterior)


def elegir(escrita, candidatos, anterior=None):
    """
    Devuelve el candidato con mayor P(candidato | escrita) según el canal y
    el prior, o None si no hay ninguno viable o el primero no domina al
    segundo por MARGEN_MINIMO. No genera candidatos: los recibe ya de otro
    módulo (`sugerencias.generar()`, `vocabulario.vecinos()`), igual que
    `contexto.elegir()`.

    SE PROBÓ Y SE DESCARTÓ exigir además que el ganador supere a QUEDARSE CON
    LO ESCRITO (`puntuar(escrita, escrita, anterior)`), por el mismo motivo
    que `UMBRAL_GANANCIA` en `contexto.py`. Medido sobre autoinducido.csv
    (docs/decisiones/2026-09-16-E4.4.md): con esa comparación adicional la
    exactitud baja de 0,8515 a 0,8179 (más abstenciones: 102 en vez de 55) y
    la intervención sobre texto limpio no mejora de forma apreciable (0 en
    vez de 2, sobre 1.069 tokens). La razón es que un original que también
    tiene frecuencia baja —el caso típico del error genuino— ya casi no
    compite con un candidato frecuente, así que la comparación no añade nada
    ahí y sí penaliza los casos donde el candidato gana por poco.
    """
    vistos = [c for c in dict.fromkeys(candidatos) if str(c).lower() != str(escrita).lower()]
    if not vistos:
        return None
    puntuados = sorted(((puntuar(escrita, c, anterior), c) for c in vistos),
                        key=lambda x: x[0], reverse=True)
    mejor_p, mejor_c = puntuados[0]
    if len(puntuados) > 1 and mejor_p - puntuados[1][0] < MARGEN_MINIMO:
        return None
    return mejor_c


def diagnosticar(escrita, candidatos, anterior=None):
    """Puntuación de cada candidato y la decisión final. Inspección manual."""
    return {
        "escrita": escrita,
        "anterior": anterior,
        "entrenado": _ENTRENADO,
        "prior_disponible": disponible(),
        "puntuaciones": {c: puntuar(escrita, c, anterior) for c in candidatos},
        "decision": elegir(escrita, candidatos, anterior),
    }
