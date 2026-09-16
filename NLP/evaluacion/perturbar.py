"""
Corpus de errores autoinducidos y conjunto limpio para medir el corrector sin
anotar a mano (PLAN.md E2.3; fundamento en INVESTIGACION.md 3.5).
Escribe salidas/evaluacion/autoinducido.csv y limpio.csv de forma determinista.
Reglas, columnas y criterios: docs/ARQUITECTURA.md 2.9 y bitacora/2026-09-15-E2.3.md.
"""

import argparse
import math
import random
import re
import sys
from collections import Counter

import pandas as pd

from NLP import rutas
from NLP.nucleo import reglas
from NLP.nucleo.salida import EscritorCSV, rotar
from NLP.recursos import casing

# Rutas de este item. Deberian pasar a rutas.py (E0.4 / E6); se definen aqui
# para no tocar ese modulo mientras otros items lo editan.
CARPETA = rutas.SALIDAS / "evaluacion"
AUTOINDUCIDO = CARPETA / "autoinducido.csv"
LIMPIO = CARPETA / "limpio.csv"

SEMILLA = 20260915
UMBRAL_FRECUENCIA = 20     # forma "de alta frecuencia": apariciones en el corpus
MINIMO_PARES = 5000
LONGITUD_MINIMA = 4        # letras que debe tener un token para perturbarse

COLUMNAS_AUTOINDUCIDO = ["OID", "texto_limpio_ref", "texto_perturbado",
                         "token_original", "token_perturbado", "regla", "posicion"]
COLUMNAS_LIMPIO = ["OID", "texto"]

# Token alfabetico con su posicion en el texto original (conserva mayusculas).
RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")

VOCALES = "aeiou"
CON_TILDE = {"a": "á", "e": "é", "i": "í", "o": "ó", "u": "ú"}
SIN_TILDE = {v: k for k, v in CON_TILDE.items()}

# Teclado QWERTY espanol: vecinos en la misma fila y en las filas contiguas.
_FILAS = ("qwertyuiop", "asdfghjklñ", "zxcvbnm")


def _vecinos_teclado():
    vecinos = {}
    for f, fila in enumerate(_FILAS):
        for i, letra in enumerate(fila):
            lista = []
            if i > 0:
                lista.append(fila[i - 1])
            if i + 1 < len(fila):
                lista.append(fila[i + 1])
            if f > 0:
                arriba = _FILAS[f - 1]
                lista += [arriba[j] for j in (i, i + 1) if 0 <= j < len(arriba)]
            if f + 1 < len(_FILAS):
                abajo = _FILAS[f + 1]
                lista += [abajo[j] for j in (i - 1, i) if 0 <= j < len(abajo)]
            vecinos[letra] = lista
    return vecinos


TECLADO = _vecinos_teclado()


# ==========================================================
# REGLAS DE PERTURBACION (sobre la forma en minuscula)
# ==========================================================

def _transposicion(p):
    return [p[:i] + p[i + 1] + p[i] + p[i + 2:]
            for i in range(len(p) - 1) if p[i] != p[i + 1]]


def _omision(p):
    return [p[:i] + p[i + 1:] for i in range(len(p))]


def _duplicacion(p):
    return [p[:i] + p[i] + p[i:] for i in range(len(p))]


def _sustituir_en(p, i, largo, nuevo):
    return p[:i] + nuevo + p[i + largo:]


def _homofono_bv(p):
    return [_sustituir_en(p, i, 1, "v" if c == "b" else "b")
            for i, c in enumerate(p) if c in "bv"]


def _homofono_lly(p):
    salida = [_sustituir_en(p, m.start(), 2, "y") for m in re.finditer("ll", p)]
    salida += [_sustituir_en(p, i, 1, "ll") for i, c in enumerate(p) if c == "y"]
    return salida


def _homofono_h(p):
    salida = [_sustituir_en(p, i, 1, "") for i, c in enumerate(p) if c == "h"]
    if p[0] in VOCALES or p[0] in SIN_TILDE:
        salida.append("h" + p)
    return salida


def _digrafo_qu_k(p):
    salida = [_sustituir_en(p, m.start(), 2, "k") for m in re.finditer("qu", p)]
    salida += [_sustituir_en(p, i, 1, "qu") for i, c in enumerate(p) if c == "k"]
    return salida


def _digrafo_cc_c(p):
    salida = [_sustituir_en(p, m.start(), 2, "c") for m in re.finditer("cc", p)]
    salida += [_sustituir_en(p, i, 1, "cc") for i, c in enumerate(p)
               if c == "c" and i + 1 < len(p) and p[i + 1] in "eéií"
               and (i == 0 or p[i - 1] != "c")]
    return salida


def _tilde(p):
    if any(c in SIN_TILDE for c in p):
        return [_sustituir_en(p, i, 1, SIN_TILDE[c]) for i, c in enumerate(p) if c in SIN_TILDE]
    return [_sustituir_en(p, i, 1, CON_TILDE[c]) for i, c in enumerate(p) if c in CON_TILDE]


def _teclado(p):
    return [_sustituir_en(p, i, 1, v) for i, c in enumerate(p)
            for v in TECLADO.get(c, ())]


REGLAS = {
    "transposicion": _transposicion,
    "omision": _omision,
    "duplicacion": _duplicacion,
    "homofono_bv": _homofono_bv,
    "homofono_lly": _homofono_lly,
    "homofono_h": _homofono_h,
    "digrafo_qu_k": _digrafo_qu_k,
    "digrafo_cc_c": _digrafo_cc_c,
    "tilde": _tilde,
    "teclado": _teclado,
}


def variantes(token, regla):
    """Formas distintas que produce una regla sobre un token, en orden estable."""
    base = token.lower()
    vistas, salida = set(), []
    for v in REGLAS[regla](base):
        if v and v != base and v not in vistas:
            vistas.add(v)
            salida.append(v)
    return salida


def _con_caso(original, nuevo):
    """Devuelve la forma perturbada con la capitalizacion del token original."""
    if original.isupper():
        return nuevo.upper()
    if original[0].isupper():
        return nuevo[0].upper() + nuevo[1:]
    return nuevo


# ==========================================================
# SELECCION DE NOTAS Y TOKENS
# ==========================================================

def contar_formas(textos):
    """Frecuencia de cada forma en minuscula, como candidatos.construir_lexico."""
    conteo = Counter()
    for t in textos:
        conteo.update(reglas.RE_PALABRA.findall(str(t).lower()))
    return conteo


def cumple_lexico(texto, lexico):
    """True si todas las formas de la nota estan en el lexico de alta frecuencia."""
    formas = reglas.RE_PALABRA.findall(str(texto).lower())
    return bool(formas) and all(f in lexico for f in formas)


def tokens_elegibles(texto, siglas):
    """Tokens alfabeticos de la nota que admiten perturbacion: (inicio, token)."""
    gritado = reglas.texto_gritado(texto)
    salida = []
    for m in RE_TOKEN.finditer(texto):
        tok = m.group()
        if len(tok) < LONGITUD_MINIMA:
            continue
        antes = texto[m.start() - 1] if m.start() > 0 else ""
        despues = texto[m.end()] if m.end() < len(texto) else ""
        if antes.isdigit() or despues.isdigit():
            continue
        if tok.isupper() and (not gritado or tok.lower() in siglas):
            continue
        salida.append((m.start(), tok))
    return salida


def perturbar_nota(texto, elegibles, lexico, rng, cuantos):
    """Hasta `cuantos` perturbaciones de la nota, cada una sobre un token distinto."""
    pares = []
    disponibles = list(elegibles)
    while disponibles and len(pares) < cuantos:
        inicio, tok = disponibles.pop(rng.randrange(len(disponibles)))
        for regla in rng.sample(list(REGLAS), len(REGLAS)):
            opciones = [v for v in variantes(tok, regla) if v not in lexico]
            if not opciones:
                continue
            nuevo = _con_caso(tok, rng.choice(opciones))
            perturbado = texto[:inicio] + nuevo + texto[inicio + len(tok):]
            pares.append((perturbado, tok, nuevo, regla, inicio))
            break
    return pares


# ==========================================================
# CONSTRUCCION DEL CORPUS
# ==========================================================

def construir(df, semilla=SEMILLA, umbral=UMBRAL_FRECUENCIA, minimo=MINIMO_PARES,
              por_nota=None):
    """Devuelve (df_autoinducido, df_limpio, resumen) a partir de OID y texto_original."""
    textos = df["texto_original"].fillna("").astype(str)
    conteo = contar_formas(textos)
    lexico = {f for f, n in conteo.items() if n >= umbral}

    reglas.cargar()
    casing.cargar()
    siglas = set(reglas.SIGLAS) | set(casing.siglas())

    candidatas = []
    cumplen = 0
    for oid, texto in zip(df["OID"], textos):
        if not cumple_lexico(texto, lexico):
            continue
        cumplen += 1
        elegibles = tokens_elegibles(texto, siglas)
        if elegibles:
            candidatas.append((int(oid), texto, elegibles))

    if por_nota is None:
        por_nota = max(1, math.ceil(minimo / len(candidatas))) if candidatas else 1

    rng = random.Random(semilla)
    filas_auto, filas_limpio = [], []
    for oid, texto, elegibles in candidatas:
        filas_limpio.append((oid, texto))
        for perturbado, tok, nuevo, regla, inicio in perturbar_nota(
                texto, elegibles, lexico, rng, por_nota):
            filas_auto.append((oid, texto, perturbado, tok, nuevo, regla, inicio))

    auto = pd.DataFrame(filas_auto, columns=COLUMNAS_AUTOINDUCIDO)
    limpio = pd.DataFrame(filas_limpio, columns=COLUMNAS_LIMPIO)
    resumen = {
        "notas": len(df), "formas_distintas": len(conteo), "formas_lexico": len(lexico),
        "umbral": umbral, "notas_cumplen_lexico": cumplen,
        "notas_con_token_elegible": len(candidatas), "por_nota": por_nota,
        "pares": len(auto), "por_regla": Counter(auto["regla"]).most_common(),
    }
    return auto, limpio, resumen


def escribir(auto, limpio):
    """Escribe ambos CSV con nucleo/salida.py (utf-8-sig, CRLF, QUOTE_ALL), rotando los previos."""
    CARPETA.mkdir(exist_ok=True)
    rotadas = []
    for ruta, df, columnas in ((AUTOINDUCIDO, auto, COLUMNAS_AUTOINDUCIDO),
                               (LIMPIO, limpio, COLUMNAS_LIMPIO)):
        rotadas.append(rotar(ruta))
        escritor = EscritorCSV(ruta, columnas)
        escritor.agregar(df)
        escritor.cerrar()
    return rotadas


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(
        description="Genera el corpus de errores autoinducidos y el conjunto limpio.")
    ap.add_argument("--csv", default=str(rutas.TRIAGE_LIMPIO),
                    help="CSV de entrada con OID y texto_original")
    ap.add_argument("--semilla", type=int, default=SEMILLA)
    ap.add_argument("--umbral", type=int, default=UMBRAL_FRECUENCIA,
                    help="frecuencia minima de una forma para ser de alta frecuencia")
    ap.add_argument("--minimo", type=int, default=MINIMO_PARES,
                    help="pares que se quieren obtener como minimo")
    ap.add_argument("--por-nota", type=int, default=None,
                    help="perturbaciones por nota (por defecto, las justas para --minimo)")
    args = ap.parse_args()

    df = pd.read_csv(args.csv, encoding="utf-8-sig", usecols=["OID", "texto_original"])
    auto, limpio, r = construir(df, args.semilla, args.umbral, args.minimo, args.por_nota)

    print(f"Notas leidas: {r['notas']:,} de {args.csv}")
    print(f"  formas distintas: {r['formas_distintas']:,}; "
          f"con frecuencia >= {r['umbral']}: {r['formas_lexico']:,}")
    print(f"  notas con todas sus formas en el lexico: {r['notas_cumplen_lexico']:,}")
    print(f"  de ellas con algun token perturbable: {r['notas_con_token_elegible']:,}")
    print(f"  perturbaciones por nota: {r['por_nota']}  (semilla {args.semilla})")
    print(f"  pares generados: {r['pares']:,}"
          + ("" if r["pares"] >= args.minimo else f"  AVISO: menos de {args.minimo:,}"))
    print("  por regla:")
    for regla, n in r["por_regla"]:
        print(f"    {n:6,}  {regla}")

    rotadas = escribir(auto, limpio)
    for previa in rotadas:
        if previa:
            print(f"  version anterior apartada en {previa.name}")
    print(f"  {AUTOINDUCIDO}  ({len(auto):,} filas)")
    print(f"  {LIMPIO}  ({len(limpio):,} filas)")


if __name__ == "__main__":
    main()
