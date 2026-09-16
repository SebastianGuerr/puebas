"""
Nivel 2 de la fase 6 (E5.7): NER de sintomas con `carmen-symptemist`
(BSC-NLP4BIA/bsc-bio-ehr-es-carmen-symptemist, CC-BY-4.0), solo sobre notas
largas (`LONGITUD_NOTA_LARGA`). No asigna codigo por si solo: extrae la
mencion (la tarjeta del modelo exige pre-tokenizar en palabras) y la entrega
a `nivel0.emparejar` / `nivel1.vecino_mas_cercano` para el codigo SNOMED,
igual que hace el resto del texto. Ver decisiones/2026-09-16-E5.7.md (coste
medido) y NLP/docs/FLUJO.md (fase 6).
"""

import re

from NLP.fase6_conceptos import nivel0, nivel1

MODELO = "BSC-NLP4BIA/bsc-bio-ehr-es-carmen-symptemist"
LONGITUD_NOTA_LARGA = 15   # palabras; por debajo, nivel 0/1 sobre el texto entero basta

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")

_TOK = None
_MOD = None
_ID2LABEL = None


def _cargar_modelo():
    """Carga tokenizador y modelo de token-classification una sola vez; sin trust_remote_code."""
    global _TOK, _MOD, _ID2LABEL
    if _MOD is not None:
        return _TOK, _MOD
    from transformers import AutoModelForTokenClassification, AutoTokenizer

    _TOK = AutoTokenizer.from_pretrained(MODELO)
    _MOD = AutoModelForTokenClassification.from_pretrained(MODELO)
    _MOD.eval()
    _ID2LABEL = _MOD.config.id2label
    return _TOK, _MOD


def es_nota_larga(texto):
    """True si el texto tiene al menos `LONGITUD_NOTA_LARGA` palabras."""
    return len(RE_PALABRA.findall(texto)) >= LONGITUD_NOTA_LARGA


def menciones(texto):
    """
    Lista de menciones (texto de la mención) que el NER etiqueta como
    sintoma/signo, con la palabra como unidad (la tarjeta del modelo exige
    tokenizar en palabras y alinear despues). Solo tiene sentido llamarla
    sobre notas largas; no filtra por longitud internamente.
    """
    import torch

    tok, mod = _cargar_modelo()
    palabras = RE_PALABRA.findall(texto)
    if not palabras:
        return []
    enc = tok(palabras, is_split_into_words=True, truncation=True, return_tensors="pt")
    with torch.no_grad():
        logits = mod(**enc).logits[0]
    etiquetas_id = logits.argmax(-1).tolist()
    ids_palabra = enc.word_ids()

    spans = []
    actual = []
    palabra_previa = None
    for etiqueta_id, idx_palabra in zip(etiquetas_id, ids_palabra):
        if idx_palabra is None:
            continue
        if idx_palabra == palabra_previa:
            continue  # subtoken de la misma palabra, ya contado
        palabra_previa = idx_palabra
        etiqueta = _ID2LABEL.get(etiqueta_id, "O")
        es_entidad = etiqueta != "O"
        if es_entidad:
            actual.append(palabras[idx_palabra])
        elif actual:
            spans.append(" ".join(actual))
            actual = []
    if actual:
        spans.append(" ".join(actual))
    return spans


def anotar(texto, indice_nivel1=None, umbral_nivel1=nivel1.UMBRAL_SIMILITUD):
    """
    `(concepto_snomed, concepto_termino)` para una nota larga: extrae
    menciones con el NER y las resuelve con nivel 0 y, si se pasa
    `indice_nivel1`, con nivel 1 para las que nivel 0 no reconoce. Cadenas
    vacias si la nota no es larga o no hay ninguna mencion resuelta.
    """
    if not es_nota_larga(texto):
        return "", ""
    codigos, terminos = [], []
    for mencion in menciones(texto):
        concepto = None
        matches = nivel0.emparejar(mencion)
        if matches:
            concepto = matches[0]
        elif indice_nivel1 is not None:
            resultado = nivel1.vecino_mas_cercano([mencion], indice_nivel1, umbral=umbral_nivel1)[0]
            if resultado:
                concepto = (resultado[0], resultado[1])
        if concepto and (not codigos or codigos[-1] != concepto[0]):
            codigos.append(concepto[0])
            terminos.append(concepto[1])
    return ";".join(codigos), ";".join(terminos)
