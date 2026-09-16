"""
Clasifica que le paso a cada nota al reprocesarla (intacta, ortografia,
recupero_motivo, perdio_motivo, normalizacion), de mas a menos grave, para que
`perdio_motivo` nunca quede tapada por otro cambio. Detalle y motivo de cada
categoria: docs/ARQUITECTURA.md, ficha `reparacion/comparacion.py` (S2.10).
"""

import re

RE_PALABRA = re.compile(r"[a-záéíóúñü]+", re.IGNORECASE)

INTACTA = "intacta"
ORTOGRAFIA = "ortografia"
RECUPERO = "recupero_motivo"
PERDIO = "perdio_motivo"
NORMALIZACION = "normalizacion"

# El orden en que se pregunta. `perdio_motivo` va primero a proposito: es la
# unica categoria que obliga a parar, y si se preguntara despues de
# `ortografia` una nota que arregla una tilde Y pierde el motivo saldria
# contada como arreglo.
ORDEN = (PERDIO, RECUPERO, ORTOGRAFIA, NORMALIZACION, INTACTA)


def _terminos_clinicos(texto):
    """
    Terminología clínica del texto: solo cuenta si `depuracion.py` (raíces) y
    `reduccion.py` (formas exactas) coinciden. Motivo y medición:
    docs/decisiones/2026-09-16-reparacion-doble-lexico-terminologia.md.
    """
    from NLP.depuracion import depuracion
    from NLP.reduccion import reduccion

    texto = str(texto or "")
    return {p for p in depuracion.terminos_clinicos(texto)
            if reduccion._es_clinica(p)}


def clasificar(vieja, nueva):
    """
    En qué categoría cae una nota (`vieja`/`nueva`: dict con columnas del CSV).
    Devuelve (categoria, detalle); el detalle resume el cambio en una línea.
    """
    emb_v, emb_n = str(vieja.get("texto_embedding", "")), str(nueva.get("texto_embedding", ""))
    cor_v, cor_n = str(vieja.get("texto_corregido", "")), str(nueva.get("texto_corregido", ""))
    nor_v, nor_n = str(vieja.get("texto_normalizado", "")), str(nueva.get("texto_normalizado", ""))

    clin_v, clin_n = _terminos_clinicos(emb_v), _terminos_clinicos(emb_n)
    perdidos = clin_v - clin_n
    ganados = clin_n - clin_v

    if perdidos:
        return PERDIO, f"pierde: {', '.join(sorted(perdidos))}"
    if ganados:
        return RECUPERO, f"recupera: {', '.join(sorted(ganados))}"
    if cor_v != cor_n:
        return ORTOGRAFIA, _diferencia(cor_v, cor_n)
    if nor_v != nor_n:
        return NORMALIZACION, _diferencia(nor_v, nor_n)
    return INTACTA, ""


def _diferencia(antes, despues):
    """
    Las palabras que cambiaron, en forma 'vieja -> nueva', para leer el cambio
    sin comparar dos frases enteras a ojo.
    """
    import difflib

    a, b = RE_PALABRA.findall(antes.lower()), RE_PALABRA.findall(despues.lower())
    cambios = []
    for etiqueta, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b).get_opcodes():
        if etiqueta == "equal":
            continue
        viejo = " ".join(a[i1:i2]) or "-"
        nuevo = " ".join(b[j1:j2]) or "-"
        cambios.append(f"{viejo} -> {nuevo}")
    return "; ".join(cambios[:6])


def resumir(categorias):
    """
    Cuántas notas cayeron en cada categoría, como lista ordenada (no dict:
    el orden es el mensaje, `perdio_motivo` primero). Recibe categorías
    sueltas, no las tuplas del informe.
    """
    conteo = {c: 0 for c in ORDEN}
    for categoria in categorias:
        conteo[categoria] = conteo.get(categoria, 0) + 1
    return [(c, conteo[c]) for c in ORDEN]
