"""
Detector de siglas y términos que el diccionario todavía no cubre.

EL CRITERIO
    Perseguir siglas de una en una no escala: el conjunto de siglas del
    castellano médico no está acotado y cada una que falta queda expuesta al
    corrector, que la convierte en la palabra corriente más parecida.

    Lo que sí está acotado es la señal. Una sigla o un término del hospital es
    un token que ningún diccionario del español reconoce y que, aun así, el
    personal repite. Un error de digitación cumple lo primero pero se distingue
    de una sigla porque tiene una corrección evidente y mucho más frecuente.

    Esa distinción final exige criterio médico, así que el módulo no la toma:
    detecta los candidatos, los ordena por frecuencia y entrega la lista para
    que la revise una persona. Cada entrada que se promueva al diccionario queda
    protegida de forma permanente.

USO
    python -m NLP.recursos.detectar_siglas

    Lee la columna de texto de la base y escribe en salidas/ un CSV con el
    token, su frecuencia, la corrección que propondría el corrector y un
    veredicto preliminar:

        typo_probable   tiene una corrección frecuente a distancia corta
        revisar         no tiene corrección clara: candidato a sigla o término

    Las filas marcadas como 'revisar' son las que hay que mirar; las que
    resulten siglas o términos clínicos se añaden al diccionario del proyecto.
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
    Tokens frecuentes que ningún diccionario reconoce, con su veredicto
    preliminar.

    Devuelve una lista de diccionarios, uno por candidato, ordenada de más a
    menos frecuente.

        textos       corpus de notas
        conocidas    claves ya presentes en el diccionario del proyecto
        es_palabra   función(token) -> bool que reconoce palabras del español
        sugerir      función(token) -> str | None con la corrección propuesta
        frecuencias  recuento del corpus completo, para comparar la frecuencia
                     del token con la de su corrección

    Un candidato se clasifica como error de digitación cuando su corrección es
    al menos RATIO_TYPO veces más frecuente que él. En cualquier otro caso queda
    para revisión manual.
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
    probables).

    Las filas a revisar van primero y ordenadas por frecuencia, porque son las
    que hay que mirar y conviene empezar por las que más aparecen.
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
