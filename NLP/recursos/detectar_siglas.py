"""
Detector de siglas y terminos frecuentes que ningun diccionario reconoce, para
revision humana (no decide por si solo: exige criterio medico). Escribe un CSV
con el veredicto preliminar `typo_probable` / `revisar`.

Responsabilidad completa y criterio: docs/ARQUITECTURA.md, ficha
`recursos/detectar_siglas.py` (S2.8). Uso: `python -m NLP.recursos.detectar_siglas`.
"""

import csv
import re
from collections import Counter

from NLP import rutas

SALIDA = rutas.SIGLAS_DETECTADAS

FRECUENCIA_MINIMA = 5      # apariciones para considerar un token
LONGITUD_MAXIMA = 8        # las siglas y abreviaturas son cortas
RATIO_TYPO = 10            # si la correccion es N veces mas frecuente, es un typo

RE_TOKEN = re.compile(r"\b[a-záéíóúüñ]{2,%d}\b" % LONGITUD_MAXIMA)


def candidatos(textos, conocidas=(), es_palabra=None, sugerir=None, frecuencias=None):
    """
    Tokens frecuentes que ningun diccionario reconoce, con su veredicto
    preliminar (typo_probable | revisar). Ver criterio en docs/ARQUITECTURA.md,
    ficha `recursos/detectar_siglas.py` (S2.8). Lista ordenada de mas a menos
    frecuente.
    """
    conteo = Counter()
    for t in textos:
        conteo.update(RE_TOKEN.findall(str(t).lower()))

    frecuencias = frecuencias if frecuencias is not None else conteo
    conocidas = {c.lower() for c in conocidas}
    filas = []

    for token, veces in conteo.most_common():
        if veces < FRECUENCIA_MINIMA or token in conocidas:
            continue
        if es_palabra is not None and es_palabra(token):
            continue

        sugerencia = sugerir(token) if sugerir else None
        freq_sugerencia = frecuencias.get(sugerencia, 0) if sugerencia else 0

        if sugerencia and freq_sugerencia >= veces * RATIO_TYPO:
            veredicto = "typo_probable"
        else:
            veredicto = "revisar"

        filas.append({
            "token": token,
            "frecuencia": veces,
            "sugerencia": sugerencia or "",
            "frecuencia_sugerencia": freq_sugerencia,
            "veredicto": veredicto,
        })

    return filas


def escribir(filas, ruta=SALIDA):
    """
    Escribe el CSV de candidatos y devuelve el par (a revisar, typos
    probables). Las filas a revisar van primero, por frecuencia descendente.
    """
    revisar = [f for f in filas if f["veredicto"] == "revisar"]
    revisar.sort(key=lambda f: -f["frecuencia"])
    typos = [f for f in filas if f["veredicto"] == "typo_probable"]
    typos.sort(key=lambda f: -f["frecuencia"])

    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["token", "frecuencia", "sugerencia",
                                          "frecuencia_sugerencia", "veredicto"])
        w.writeheader()
        w.writerows(revisar + typos)

    return len(revisar), len(typos)


def main():
    """
    Ejecuta la detección sobre la tabla de triage: carga el diccionario, arma el
    léxico de frecuencias del corpus, busca los candidatos y escribe el CSV.
    """
    import language_tool_python
    import pandas as pd

    from NLP.recursos import ambiguedad
    from NLP.fase2_ortografia import ortografia
    from NLP.nucleo import reglas
    from NLP.fase2_ortografia import vocabulario
    from NLP.nucleo.conexion_bd import obtener_engine
    from NLP.procesar import COLUMNA, LIMITE_LEXICO, TABLA

    print("Conectando BD...")
    engine = obtener_engine()

    reglas.cargar()
    df = pd.read_sql(
        f"SELECT TOP {LIMITE_LEXICO} {COLUMNA} FROM {TABLA} "
        f"WHERE {COLUMNA} IS NOT NULL AND LTRIM(RTRIM({COLUMNA})) <> ''", engine
    )
    print(f"  {len(df):,} notas")

    ortografia.construir_lexico(df[COLUMNA])
    ambiguedad.usar_languagetool(language_tool_python.LanguageTool("es"))

    from NLP.fase2_ortografia import candidatos as mod_candidatos

    filas = candidatos(
        df[COLUMNA],
        conocidas=reglas.SIGLAS,
        es_palabra=ambiguedad.es_palabra_corriente,
        sugerir=vocabulario.sugerir,
        frecuencias=mod_candidatos.CONTEO,
    )
    revisar, typos = escribir(filas)

    print(f"\n  {revisar:,} tokens para revisar (candidatos a sigla o termino)")
    print(f"  {typos:,} clasificados como typo probable")
    print(f"\nArchivo: {SALIDA}")
    print("Revisa las filas 'revisar': las que sean siglas o terminos clinicos")
    print("van a diccionario_siglas.json y quedan protegidas.")


if __name__ == "__main__":
    main()
