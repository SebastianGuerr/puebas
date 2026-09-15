"""
Qué le pasó a cada nota al reprocesarla, y si eso fue una mejora o un destrozo.

POR QUE HACE FALTA ESTE MODULO Y NO BASTA CON MIRAR EL CSV NUEVO
    Reprocesar 9.311 notas produce 9.311 textos distintos, y mirarlos no dice
    nada: la pregunta no es cómo quedaron sino QUE CAMBIO respecto a lo que
    había, y sobre todo si algún cambio fue a peor. Un reproceso que arregla
    2.000 notas y estropea 50 es un mal negocio si nadie se entera de las 50.

    Por eso la reparación no se da por buena mirando el resultado, sino este
    informe: cada nota entra en una categoría, y una de ellas -- `perdio_motivo`
    -- es la que obliga a parar y revisar antes de aplicar nada.

LAS CATEGORIAS, Y POR QUE SON ESTAS
    Salen de los tres fallos que se midieron sobre la corrida vieja, que son
    los tres que hay que poder contar por separado:

        intacta            el reproceso no la toco. Es la mayoria y tiene que
                           serlo: si esta categoria fuera pequeña, el reproceso
                           estaria reescribiendo notas que ya estaban bien.
        ortografia         cambio el texto corregido. Es el caso de la nota que
                           no habia recibido correccion, o que la recibio mal.
        recupero_motivo    el texto de embedding GANO terminologia clinica que
                           antes se habia perdido. Es el arreglo del lexico
                           ausente, contado nota a nota.
        perdio_motivo      el texto de embedding PERDIO terminologia clinica.
                           Es el unico resultado inaceptable y por eso tiene
                           categoria propia: no se mezcla con nada.
        normalizacion      solo cambio la anotacion de la fase 3.

    Una nota cae en la primera categoria que le aplica, de la mas grave a la
    mas leve, para que `perdio_motivo` nunca quede tapada por otra cosa.
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
    Terminología clínica del texto, como conjunto.

    SE EXIGE QUE LOS DOS LEXICOS ESTEN DE ACUERDO, Y NO ES POR PRUDENCIA
        `perdio_motivo` es la categoría que detiene la reparación, así que su
        valor entero está en que no dé falsas alarmas: una que salte por ruido
        obliga a revisar a mano notas que estaban bien, y a la tercera vez
        nadie la mira. Vale más perderse una pérdida real que gritar en falso.

        Los dos léxicos fallan de formas distintas y no coincidentes.
        `depuracion.py` indexa RAICES, así que con sus 10.402 entradas
        cargadas da por clínicas 'teniamos', 'recomendaciones', 'ingresa',
        'cierres' y 'observa' -- todas por parecido de raíz, ninguna es
        terminología. El léxico curado de `reduccion.py` compara formas
        exactas y no cae en eso, pero acepta 'dada', 'salud' y 'toma'.

        Pedir las dos cosas deja fuera las diez y conserva 'desvanecimiento',
        'isquemia', 'comisura', 'desviacion', 'gestante', 'fetido', 'herida',
        'cefalea', 'disnea' y 'convulsiva'. Medido sobre la muestra de 100
        notas: siete alarmas, de las que siete eran ruido.
    """
    from NLP.depuracion import depuracion
    from NLP.reduccion import reduccion

    texto = str(texto or "")
    return {p for p in depuracion.terminos_clinicos(texto)
            if reduccion._es_clinica(p)}


def clasificar(vieja, nueva):
    """
    En qué categoría cae una nota. `vieja` y `nueva` son diccionarios con las
    columnas del CSV.

    Devuelve (categoria, detalle), donde el detalle explica el cambio en una
    línea para poder revisarlo sin abrir las dos versiones.
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
    Cuántas notas cayeron en cada categoría, en el orden en que hay que leerlas.

    Recibe categorías sueltas, no las tuplas del informe, porque quien llama
    tiene dos formas distintas de tupla y desempaquetar aquí una de las dos
    obliga a la otra a fingir que tiene la misma forma.

    Se devuelve una lista y no un diccionario porque el orden ES el mensaje: lo
    primero que tiene que ver quien lee el informe es cuántas notas empeoraron.
    """
    conteo = {c: 0 for c in ORDEN}
    for categoria in categorias:
        conteo[categoria] = conteo.get(categoria, 0) + 1
    return [(c, conteo[c]) for c in ORDEN]
