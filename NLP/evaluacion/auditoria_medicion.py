"""
Medicion de una corrida del pipeline: lectura del CSV y calculo de las
metricas comparables entre corridas. Parte de `evaluacion/auditoria.py`
(E6.2, division de archivos grandes); las constantes compartidas viven en
auditoria_constantes.py. Ver docs/ARQUITECTURA.md #2.9.

QUÉ OFRECE
    leer()                lista de diccionarios desde el CSV de una corrida
    sustituciones()        alineamiento antes/despues, agrupado por tipo
    medir()                diccionario de metricas comparables entre corridas
    regresiones()          casos concretos que ya fallaron una vez
    typos_no_corregidos()  errores de control que el corrector debe arreglar
"""

import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

from NLP.evaluacion.auditoria_constantes import (
    CSV_POR_DEFECTO, COL_ID, COL_ORIGINAL, COL_CORREGIDO, COL_NORMALIZADO,
    RE_TOKEN, RE_PALABRA, LIMITE, PUNTUACION_BORDE, BORRADO, INSERTADO,
    SIMBOLOS_CLINICOS, SIMBOLOS_CONVERTIDOS, PROPORCION_MAYUSCULAS,
    REGRESIONES, TYPOS_QUE_DEBEN_CORREGIRSE,
)

# ==========================================================
# LECTURA DEL CSV
# ==========================================================

def leer(ruta=CSV_POR_DEFECTO):
    """Lee el CSV de una corrida como lista de diccionarios."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre antes procesar.py.")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _sin_tildes(texto):
    """Pliega acentos para comparar. Aquí sí incluye la eñe: solo se usa para
    decidir si dos formas difieren únicamente en la tilde."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def _gritado(texto):
    """True si la nota está escrita casi toda en mayúsculas."""
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


def _columna(filas, nombre):
    """
    Extrae una columna del CSV. Si no está presente (porque esa fase no se
    ejecutó) devuelve la columna corregida, para que la medición no falle.
    """
    if filas and nombre in filas[0]:
        return [f[nombre] for f in filas]
    return [f.get(COL_CORREGIDO, "") for f in filas]


# ==========================================================
# MEDICIÓN
# ==========================================================

def _frecuencias(textos):
    """Recuento de palabras del corpus de entrada, para medir el riesgo."""
    conteo = Counter()
    for t in textos:
        conteo.update(RE_PALABRA.findall(t.lower()))
    return conteo


def sustituciones(originales, corregidos):
    """
    Compara dos versiones del corpus y devuelve qué cambió, agrupado por tipo.

    El resultado es un diccionario con:

        pares                reemplazos de una palabra por otra, con su
                             frecuencia. Es lo que se entiende por corrección.
        movimientos          tokens borrados e insertados. Sin este grupo, la
                             limpieza y la normalización quedarían invisibles:
                             la primera borra símbolos y la segunda inserta la
                             anotación entre paréntesis, y ninguna de las dos
                             produce un reemplazo uno a uno.
        ejemplos             una nota de muestra por cada cambio distinto
        estructurales        cuántas notas sufrieron borrados o inserciones

    El alineamiento se hace con SequenceMatcher y no emparejando por posición,
    porque la limpieza borra y fusiona tokens: al emparejar por posición, un
    token borrado desplaza todo lo que sigue e inventa sustituciones que nunca
    ocurrieron.

    Además se alinea sobre el núcleo de cada palabra, sin la puntuación que la
    rodea, porque un cambio de separador convertiría la misma palabra en un
    token distinto y aparecería como borrado.
    """
    from difflib import SequenceMatcher

    pares = Counter()
    ejemplos = {}
    movimientos = Counter()
    ejemplos_movimiento = {}
    estructurales = 0

    def _limpiar(token):
        return token.strip(PUNTUACION_BORDE)

    for antes, despues in zip(originales, corregidos):
        if antes == despues:
            continue
        # se compara el nucleo de cada palabra, sin su puntuacion (ver docstring)
        ta = [_limpiar(t) for t in RE_TOKEN.findall(antes.lower())]
        tb = [_limpiar(t) for t in RE_TOKEN.findall(despues.lower())]
        hubo_estructural = False

        for etiqueta, i1, i2, j1, j2 in SequenceMatcher(
                None, ta, tb, autojunk=False).get_opcodes():
            if etiqueta == "equal":
                continue

            if etiqueta == "replace" and (i2 - i1) == (j2 - j1):
                for x, y in zip(ta[i1:i2], tb[j1:j2]):
                    # nucleos identicos: solo cambio la puntuacion de alrededor,
                    # que es reacomodo de la fase 1 y no una correccion
                    if x == y:
                        continue
                    nx, ny = x, y
                    pares[(nx, ny)] += 1
                    ejemplos.setdefault((nx, ny), (antes, despues))
                continue

            hubo_estructural = True
            for x in ta[i1:i2]:
                clave = (x, BORRADO)
                if clave[0]:
                    movimientos[clave] += 1
                    ejemplos_movimiento.setdefault(clave, (antes, despues))
            for y in tb[j1:j2]:
                clave = (INSERTADO, y)
                if clave[1]:
                    movimientos[clave] += 1
                    ejemplos_movimiento.setdefault(clave, (antes, despues))

        if hubo_estructural:
            estructurales += 1

    return {
        "pares": pares,
        "ejemplos": ejemplos,
        "movimientos": movimientos,
        "ejemplos_movimiento": ejemplos_movimiento,
        "estructurales": estructurales,
    }


def medir(filas):
    """
    Calcula todas las métricas de una corrida y las devuelve en un diccionario
    apto para guardar en JSON y comparar con otra.

    Cubre cinco bloques: la forma del corpus de entrada, la supervivencia de los
    símbolos clínicos, el volumen de cambio por fase, las sustituciones y su
    riesgo, y los errores de control que quedaron sin corregir.
    """
    total = max(len(filas), 1)
    originales = _columna(filas, COL_ORIGINAL)
    corregidos = _columna(filas, COL_CORREGIDO)
    normalizados = _columna(filas, COL_NORMALIZADO)

    m = {"registros": len(filas)}

    # --- forma del corpus de entrada ---
    m["notas_gritadas"] = sum(1 for t in originales if _gritado(t))
    m["pct_gritadas"] = round(100 * m["notas_gritadas"] / total, 1)

    # --- simbolos clinicos que sobreviven a la fase 1 ---
    supervivencia = {}
    for simbolo, _descripcion in SIMBOLOS_CLINICOS.items():
        antes = sum(1 for t in originales if simbolo in t)
        despues = sum(1 for t in corregidos if simbolo in t)
        if antes:
            supervivencia[simbolo] = {
                "notas_origen": antes,
                "notas_destino": despues,
                "pct_conservado": round(100 * despues / antes, 1),
            }
    m["simbolos_clinicos"] = supervivencia
    m["simbolos_perdidos"] = sum(
        v["notas_origen"] - v["notas_destino"] for v in supervivencia.values())

    # los convertidos no deben sobrevivir; lo que se comprueba es que la
    # division que marcaban siga representada por su separador
    conversion = {}
    for simbolo, (descripcion, separador) in SIMBOLOS_CONVERTIDOS.items():
        origen = [t for t in originales if simbolo in t]
        if not origen:
            continue
        indices = [i for i, t in enumerate(originales) if simbolo in t]
        con_separador = sum(1 for i in indices if separador in corregidos[i])
        conversion[simbolo] = {
            "notas_origen": len(indices),
            "conservan_separador": con_separador,
            "pct": round(100 * con_separador / len(indices), 1),
            "separador": separador,
        }
    m["simbolos_convertidos"] = conversion

    # --- volumen de cambio por fase ---
    m["notas_modificadas_ortografia"] = sum(
        1 for a, b in zip(originales, corregidos) if a != b)
    m["notas_modificadas_normalizacion"] = sum(
        1 for a, b in zip(corregidos, normalizados) if a != b)
    m["tokens_anadidos_normalizacion"] = sum(
        max(0, len(RE_TOKEN.findall(b)) - len(RE_TOKEN.findall(a)))
        for a, b in zip(corregidos, normalizados))

    # --- sustituciones y su riesgo ---
    diff = sustituciones(originales, corregidos)
    conteo = diff["pares"]
    m["sustituciones_distintas"] = len(conteo)
    m["sustituciones_aplicadas"] = sum(conteo.values())
    m["notas_con_cambio_estructural"] = diff["estructurales"]
    m["tokens_borrados"] = sum(v for (o, c), v in diff["movimientos"].items()
                               if c == BORRADO)
    m["tokens_insertados"] = sum(v for (o, c), v in diff["movimientos"].items()
                                 if o == INSERTADO)

    solo_tilde = sum(v for (o, c), v in conteo.items() if _sin_tildes(o) == _sin_tildes(c))
    m["sustituciones_solo_tilde"] = solo_tilde
    m["sustituciones_cambio_real"] = m["sustituciones_aplicadas"] - solo_tilde

    # Riesgo clinico: un termino que el corpus repite muchas veces no es un
    # descuido de digitacion, asi que reescribirlo es el error mas caro del
    # pipeline. Las sustituciones de solo tilde no cuentan, porque no cambian el
    # concepto.
    freq = _frecuencias(originales)
    riesgo = []
    for (o, c), veces in conteo.items():
        if _sin_tildes(o) == _sin_tildes(c):
            continue
        fo = freq.get(o.strip(".,;:"), 0)
        if fo >= 10:
            riesgo.append((fo, veces, o, c))
    riesgo.sort(reverse=True)
    m["sustituciones_sobre_termino_frecuente"] = len(riesgo)
    m["muestra_riesgo"] = [
        {"original": o, "corregido": c, "freq_corpus": fo, "veces": v}
        for fo, v, o, c in riesgo[:15]
    ]

    # --- notas que quedaron sin contenido ---
    m["notas_vacias_tras_limpieza"] = sum(1 for t in corregidos if not t.strip())

    # --- errores de control que sobrevivieron a la correccion ---
    # No se exige cero, porque la linea base tampoco lo lograba. Lo que se
    # vigila es que la cifra no aumente: subir significa que alguna defensa
    # nueva esta bloqueando correcciones legitimas.
    pendientes = typos_no_corregidos(filas)
    m["typos_sin_corregir"] = sum(destino for _t, _c, _o, destino in pendientes)
    m["detalle_typos"] = [
        {"typo": t, "correccion": c, "en_origen": o, "sin_corregir": d}
        for t, c, o, d in pendientes
    ]

    return m


def typos_no_corregidos(filas):
    """
    Errores de control que sobrevivieron a la corrección.

    Devuelve una tupla por error presente en el corpus, con la forma
    (error, corrección esperada, notas donde aparecía, notas donde sigue). Una
    lista vacía significa que ninguno de los errores de control aparece siquiera
    en el corpus de entrada.
    """
    salida = []
    for typo, correccion in TYPOS_QUE_DEBEN_CORREGIRSE:
        patron = re.compile(LIMITE + re.escape(typo) + LIMITE,
                            re.IGNORECASE)
        en_origen = sum(1 for f in filas if patron.search(f[COL_ORIGINAL]))
        if not en_origen:
            continue
        en_destino = sum(1 for f in filas if patron.search(f[COL_CORREGIDO]))
        salida.append((typo, correccion, en_origen, en_destino))
    return salida


def regresiones(filas):
    """
    Comprueba los casos concretos que ya fallaron una vez.

    Devuelve una tupla por caso, con la forma
    (oid, token, sobrevive, caja, descripción), donde los dos indicadores miden
    cosas distintas y de distinta gravedad:

        sobrevive  el término sigue en el texto y no se convirtió en otra
                   palabra. Es lo único que de verdad importa: convertir un
                   término en otra palabra inventa un dato clínico, mientras que
                   pasarlo a minúscula no.
        caja       además conserva las mayúsculas del original. Es deseable pero
                   secundario, y en una nota gritada no siempre hay evidencia
                   para arriesgarla.

    Medirlos juntos escondía el avance, porque un término que dejaba de
    corromperse seguía contando como fallo por salir en minúscula.

    Los dos indicadores valen None cuando el caso no se puede evaluar: la nota
    no está en esta corrida, o el token ni siquiera aparece en el original.
    """
    por_oid = {str(f[COL_ID]): f for f in filas}

    def _tokens(texto, plegar):
        texto = _sin_tildes(texto) if plegar else texto
        return set(re.findall(r"[^\W\d_]+", texto, re.UNICODE))

    salida = []
    for oid, token, descripcion in REGRESIONES:
        fila = por_oid.get(str(oid))
        if fila is None:
            salida.append((oid, token, None, None, "OID ausente de esta corrida"))
            continue

        # se busca por token completo y no por subcadena: una sigla corta
        # aparece dentro de muchas palabras y la comprobacion daria OK siempre
        if token not in _tokens(fila[COL_ORIGINAL], True):
            salida.append((oid, token, None, None, "el token no esta en el original"))
            continue

        destino_plegado = _tokens(fila[COL_CORREGIDO], True)
        sobrevive = token in destino_plegado

        venia_mayuscula = token.upper() in _tokens(fila[COL_ORIGINAL], False)
        if not venia_mayuscula:
            caja = sobrevive
        else:
            caja = token.upper() in _tokens(fila[COL_CORREGIDO], False)

        salida.append((oid, token, sobrevive, caja, descripcion))
    return salida
