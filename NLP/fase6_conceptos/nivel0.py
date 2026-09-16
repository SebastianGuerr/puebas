"""
Nivel 0 de la fase 6 (E5.7): PhraseMatcher de spaCy contra el TSV crudo de
DISTEMIST (code/language/term/semantic_tag/mainterm, CC-BY-4.0). Busca la
mencion mas larga de cada nota que coincide literalmente con un termino del
gazetteer. Ver NLP/docs/FLUJO.md (fase 6) y decisiones/2026-09-16-E5.7.md.
"""

import csv

from NLP import rutas
from NLP.nucleo.morfologia import sin_tildes

_NLP = None
_MATCHER = None
_PATRON_A_CONCEPTO = {}   # texto normalizado del patron -> (concepto_snomed, concepto_termino)


def _leer_gazetteer():
    """Agrupa el TSV por codigo: {code: [(term, es_mainterm), ...]}."""
    por_codigo = {}
    with open(rutas.GAZETTEER_DISTEMIST_TSV, encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f, delimiter="\t")
        for fila in lector:
            termino = (fila.get("term") or "").strip().lower()
            codigo = (fila.get("code") or "").strip()
            if not termino or not codigo:
                continue
            por_codigo.setdefault(codigo, []).append((termino, fila.get("mainterm") == "1"))
    return por_codigo


def _termino_preferido(formas):
    """La forma marcada mainterm=1; si ninguna lo esta, la primera leida."""
    for termino, es_principal in formas:
        if es_principal:
            return termino
    return formas[0][0]


def construir():
    """
    Construye el PhraseMatcher una sola vez (tokenizador vacio de spaCy, sin
    modelo entrenado: nivel 0 solo necesita segmentar en palabras). Cada
    patron entra con su forma original y su forma sin tildes, para no perder
    coincidencias por una tilde ausente en la nota.
    """
    global _NLP, _MATCHER, _PATRON_A_CONCEPTO
    if _MATCHER is not None:
        return _MATCHER
    import spacy
    from spacy.matcher import PhraseMatcher

    _NLP = spacy.blank("es")
    _MATCHER = PhraseMatcher(_NLP.vocab, attr="LOWER")

    _PATRON_A_CONCEPTO = {}
    for codigo, formas in _leer_gazetteer().items():
        preferido = _termino_preferido(formas)
        for termino, _ in formas:
            for forma in {termino, sin_tildes(termino)}:
                if forma and forma not in _PATRON_A_CONCEPTO:
                    _PATRON_A_CONCEPTO[forma] = (codigo, preferido)

    docs = list(_NLP.tokenizer.pipe(_PATRON_A_CONCEPTO.keys()))
    _MATCHER.add("DISTEMIST", docs)
    return _MATCHER


def emparejar(texto):
    """
    Concepto SNOMED de la mencion mas larga y sin solapes que reconoce el
    gazetteer en `texto`, como lista de (concepto_snomed, concepto_termino)
    en el orden en que aparecen. Lista vacia si no hay ninguna.
    """
    from spacy.util import filter_spans

    matcher = construir()
    doc = _NLP.tokenizer(texto)
    coincidencias = matcher(doc)
    if not coincidencias:
        return []
    spans = filter_spans([doc[inicio:fin] for _, inicio, fin in coincidencias])
    spans.sort(key=lambda s: s.start)

    conceptos = []
    for span in spans:
        clave = span.text.lower()
        concepto = _PATRON_A_CONCEPTO.get(clave) or _PATRON_A_CONCEPTO.get(sin_tildes(clave))
        if concepto and (not conceptos or conceptos[-1] != concepto):
            conceptos.append(concepto)
    return conceptos


def anotar(texto):
    """
    `(concepto_snomed, concepto_termino)` para una nota: las columnas que
    pide la ficha, con varios conceptos unidos por ';' en el orden hallado.
    Cadenas vacias si no hubo ninguna coincidencia.
    """
    conceptos = emparejar(texto)
    if not conceptos:
        return "", ""
    codigos = ";".join(c for c, _ in conceptos)
    terminos = ";".join(t for _, t in conceptos)
    return codigos, terminos


def diagnosticar(muestra=None):
    """Imprime tamano del indice y, si se pasa una lista de textos, sus coincidencias."""
    construir()
    print(f"patrones cargados: {len(_PATRON_A_CONCEPTO)}")
    if muestra:
        for texto in muestra:
            print(repr(texto), "->", anotar(texto))
