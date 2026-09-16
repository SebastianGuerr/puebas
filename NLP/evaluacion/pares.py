"""
Auditoria por par distinto (E2.4): agrupa las correcciones de la fase 2 por
par (original -> correccion) para revisar pares en vez de notas. Metodo y
evidencia: `docs/bitacora/2026-09-16-E2.4.md`, `docs/INVESTIGACION.md` §3.2.

    python -m NLP.evaluacion.pares [--csv RUTA] [--salida RUTA] [--top N]
"""

import argparse
import re
import sys
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd
from rapidfuzz.distance import DamerauLevenshtein

from NLP import rutas
from NLP.nucleo import morfologia
from NLP.nucleo import reglas
from NLP.nucleo.salida import EscritorCSV

# Pendiente de mover a rutas.py (no se toca aqui: otro agente lo edita ahora).
PARES_CORRECCION = rutas.SALIDAS / "pares_correccion.csv"

COLUMNAS = [
    "original", "correccion", "ocurrencias", "freq_original", "freq_correccion",
    "distancia", "fonetica_igual", "cubo", "decision_humana",
]

RE_TOKEN = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ0-9]+")

# Umbrales del cubo 'aceptar' (INVESTIGACION.md §3.2; PLAN.md §8 E2.4).
FREQ_ORIGINAL_RARA = 2
FREQ_CORRECCION_ESTABLECIDA = 50
DISTANCIA_MAXIMA_ACEPTAR = 2

# Disparadores de negacion y de lateralidad para el criterio de daño de la
# ficha. No existe hoy una lista importable de uso general para estos dos
# criterios (E3.7 -negacion NegEx-MES- todavia no se ha ejecutado; las listas
# de VACIAS en depuracion.py y reduccion.py son para respuestas
# administrativas vacias, no disparadores de negacion): se definen aqui, a
# mano, y quedan documentadas en la bitacora del item.
NEGACION = {
    "no", "nunca", "niega", "niegan", "sin", "ausencia", "ausente",
    "negativo", "negativa",
}
LATERALIDAD = {
    "izquierdo", "izquierda", "derecho", "derecha", "bilateral", "ambos", "ambas",
}

# Peso del cubo en el orden de revision (ver clave_riesgo). 'revisar' no tiene
# ninguna senal automatica a favor ni en contra: es la maxima incertidumbre.
# 'revertir' ya tiene una senal fuerte, pero es la decision de mayor costo si
# se equivoca (deja pasar un error real). 'aceptar' ya supero un filtro
# estricto de cuatro condiciones: es lo que menos necesita revision humana.
RIESGO_CUBO = {"revisar": 3, "revertir": 2, "aceptar": 1}


# ==========================================================
# CLAVE FONETICA
# ==========================================================

def clave_fonetica(palabra):
    """
    Clave fonetica simple para español (seseo, betacismo, hache muda).
    Ver metodo en la bitacora del item; E4.3 podra sustituirla por
    `nucleo/fonetica.py`.
    """
    p = morfologia.sin_tildes(str(palabra)).lower()
    p = p.replace("qu", "k")
    p = p.replace("ll", "y")
    p = re.sub(r"c(?=[ei])", "s", p)
    p = p.replace("v", "b")
    p = p.replace("z", "s")
    p = p.replace("h", "")
    p = re.sub(r"(.)\1+", r"\1", p)
    return p


# ==========================================================
# LECTURA Y ALINEACION
# ==========================================================

def _tokenizar(texto):
    return RE_TOKEN.findall(str(texto or ""))


def _clave_alineacion(token):
    """Forma usada solo para casar tokens con difflib: minuscula, sin tilde."""
    return morfologia.sin_tildes(token.lower())


def pares_de_fila(texto_original, texto_corregido):
    """
    Pares (original, correccion) de una nota, por alineacion 1 a 1 de tokens.
    Insercion, borrado y cambios de solo tilde o mayuscula no producen par
    (motivo y metodo: bitacora del item).
    """
    originales = _tokenizar(texto_original)
    corregidos = _tokenizar(texto_corregido)
    alineado_o = [_clave_alineacion(t) for t in originales]
    alineado_c = [_clave_alineacion(t) for t in corregidos]

    pares = []
    cotejo = SequenceMatcher(a=alineado_o, b=alineado_c, autojunk=False)
    for etiqueta, i1, i2, j1, j2 in cotejo.get_opcodes():
        if etiqueta != "replace" or i2 - i1 != 1 or j2 - j1 != 1:
            continue
        pares.append((originales[i1].lower(), corregidos[j1].lower()))
    return pares


# ==========================================================
# CRITERIOS DE DAÑO Y CUBOS
# ==========================================================

def afecta_negacion_numero_lateralidad(original, correccion):
    """
    True si el par cambia la negacion, un numero o la lateralidad.
    Numero reutiliza `morfologia.tiene_numero`; negacion y lateralidad usan
    las listas de este modulo (motivo: bitacora del item).
    """
    if morfologia.tiene_numero(original) or morfologia.tiene_numero(correccion):
        return True
    o, c = morfologia.sin_tildes(original), morfologia.sin_tildes(correccion)
    if (o in NEGACION) != (c in NEGACION):
        return True
    if (o in LATERALIDAD) != (c in LATERALIDAD):
        return True
    if o in LATERALIDAD and c in LATERALIDAD and o != c:
        return True
    return False


def clasificar(original, correccion, freq_original, freq_correccion, distancia,
               fonetica_igual):
    """Cubo del par: 'revertir', 'aceptar' o 'revisar', por el orden de la ficha."""
    if (freq_original >= freq_correccion
            or reglas.esta_protegido(original)
            or afecta_negacion_numero_lateralidad(original, correccion)):
        return "revertir"
    if (freq_original <= FREQ_ORIGINAL_RARA
            and freq_correccion >= FREQ_CORRECCION_ESTABLECIDA
            and distancia <= DISTANCIA_MAXIMA_ACEPTAR
            and fonetica_igual):
        return "aceptar"
    return "revisar"


def clave_riesgo(cubo, ocurrencias):
    """Orden de revision: ocurrencias x riesgo del cubo (ver RIESGO_CUBO)."""
    return ocurrencias * RIESGO_CUBO[cubo]


# ==========================================================
# TABLA
# ==========================================================

def construir_tabla(ruta_triage=rutas.TRIAGE_LIMPIO):
    """
    Lista de dicts (columnas de COLUMNAS) con los pares distintos y su cubo,
    ordenada por ocurrencias x riesgo y con desempate estable para que dos
    corridas produzcan el mismo archivo.
    """
    reglas.cargar()

    columnas = ["texto_original", "texto_corregido"]
    filas = pd.read_csv(ruta_triage, encoding="utf-8-sig", usecols=columnas)

    frecuencias = Counter()
    for texto in filas["texto_original"]:
        frecuencias.update(t.lower() for t in _tokenizar(texto))

    ocurrencias = Counter()
    for original, corregido in zip(filas["texto_original"], filas["texto_corregido"]):
        for par in pares_de_fila(original, corregido):
            ocurrencias[par] += 1

    tabla = []
    for (original, correccion), veces in ocurrencias.items():
        freq_o = frecuencias.get(original, 0)
        freq_c = frecuencias.get(correccion, 0)
        distancia = DamerauLevenshtein.distance(
            morfologia.sin_tildes(original), morfologia.sin_tildes(correccion))
        fon_igual = clave_fonetica(original) == clave_fonetica(correccion)
        cubo = clasificar(original, correccion, freq_o, freq_c, distancia, fon_igual)
        tabla.append({
            "original": original,
            "correccion": correccion,
            "ocurrencias": veces,
            "freq_original": freq_o,
            "freq_correccion": freq_c,
            "distancia": distancia,
            "fonetica_igual": fon_igual,
            "cubo": cubo,
            "decision_humana": "",
        })

    tabla.sort(key=lambda f: (
        -clave_riesgo(f["cubo"], f["ocurrencias"]),
        -f["ocurrencias"],
        f["original"],
        f["correccion"],
    ))
    return tabla


def escribir(tabla, ruta=PARES_CORRECCION):
    """Escribe la tabla con EscritorCSV: utf-8-sig, CRLF, comillas en todos los campos."""
    ruta = Path(ruta)
    escritor = EscritorCSV(ruta, COLUMNAS)
    escritor.agregar(pd.DataFrame(tabla, columns=COLUMNAS))
    escritor.cerrar()
    return ruta


# ==========================================================
# CLI
# ==========================================================

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--csv", type=Path, default=rutas.TRIAGE_LIMPIO,
                    help="triage_limpio.csv de entrada (solo lectura)")
    ap.add_argument("--salida", type=Path, default=PARES_CORRECCION,
                    help="ruta de salida de pares_correccion.csv")
    ap.add_argument("--top", type=int, default=10,
                    help="cuantos pares de cada extremo imprimir en consola")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    tabla = construir_tabla(args.csv)
    ruta = escribir(tabla, args.salida)

    total_ocurrencias = sum(f["ocurrencias"] for f in tabla)
    cubos = Counter(f["cubo"] for f in tabla)
    cobertura_200 = sum(f["ocurrencias"] for f in tabla[:200])

    print(f"Fuente:  {args.csv}")
    print(f"Salida:  {ruta}")
    print(f"Pares distintos: {len(tabla)}")
    print(f"Ocurrencias totales: {total_ocurrencias}")
    if total_ocurrencias:
        print(f"Cobertura de los 200 primeros: {cobertura_200}/{total_ocurrencias} "
              f"({100 * cobertura_200 / total_ocurrencias:.1f} %)")
    print("Distribucion por cubo:")
    for cubo in ("revertir", "aceptar", "revisar"):
        print(f"  {cubo}: {cubos.get(cubo, 0)}")
    print(f"Primeros {args.top} pares por ocurrencias x riesgo:")
    for fila in tabla[:args.top]:
        print(f"  {fila['original']} -> {fila['correccion']}  "
              f"({fila['cubo']}, {fila['ocurrencias']} veces)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
