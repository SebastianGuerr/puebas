"""
Detector de siglas y terminos que el diccionario todavia no cubre.

EL CONCEPTO

    Perseguir siglas una por una no escala. SMS y EDA fueron las de una semana,
    IVA y DAD las de la siguiente, y SAHOS, VMNI, CPAP, RTS y FCF son las de
    esta. El conjunto de siglas del castellano medico no esta acotado, y cada
    una que falta queda expuesta al corrector: 'sahos' terminaba en 'manos'.

    Lo que si esta acotado es la senal: una sigla o un termino del hospital es
    un token que NINGUN diccionario del espanol reconoce y que aun asi el
    personal repite. Un typo tambien cumple lo primero, pero se distingue porque
    tiene una correccion obvia y mucho mas frecuente; una sigla no la tiene.

    Esa distincion final requiere criterio medico, asi que el sistema no la
    toma: detecta los candidatos, los ordena por frecuencia y te entrega la
    lista para que decidas. Cada entrada que promuevas al diccionario queda
    protegida para siempre.

USO

    python detectar_siglas.py

    Lee la columna de texto de la base y escribe siglas_detectadas.csv con:
        token, frecuencia, sugerencia_del_corrector, veredicto

    'veredicto' es una primera clasificacion automatica:
        typo_probable   tiene correccion frecuente a distancia corta
        revisar         no tiene correccion clara: candidato a sigla o termino

    Las marcadas 'revisar' son las que hay que mirar. Las que resulten siglas o
    terminos van a diccionario_siglas.json; el resto se ignora.
"""

import csv
import re
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
SALIDA = BASE_DIR / "siglas_detectadas.csv"

FRECUENCIA_MINIMA = 5      # apariciones para considerar un token
LONGITUD_MAXIMA = 8        # las siglas y abreviaturas son cortas
RATIO_TYPO = 10            # si la correccion es N veces mas frecuente, es un typo

RE_TOKEN = re.compile(r"\b[a-záéíóúüñ]{2,%d}\b" % LONGITUD_MAXIMA)


def candidatos(textos, conocidas=(), es_palabra=None, sugerir=None, frecuencias=None):
    """
    textos:      corpus de notas
    conocidas:   claves ya presentes en el diccionario
    es_palabra:  funcion(token) -> bool, reconocimiento por LanguageTool/spaCy
    sugerir:     funcion(token) -> str|None, la correccion que propondria SymSpell
    frecuencias: Counter del corpus completo, para medir el ratio del typo
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
    import language_tool_python
    import pandas as pd

    import ambiguedad
    import ortografia
    import reglas
    import vocabulario
    from conexion_bd import obtener_engine
    from procesar import COLUMNA, LIMITE_LEXICO, TABLA

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

    import candidatos as mod_candidatos

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
