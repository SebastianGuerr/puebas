"""
Escaneo del corpus: qué problemas traen las notas y en qué proporción.

Este módulo no corrige nada. Clasifica cada nota según las señales objetivas
que presenta y cuenta cuántas hay de cada clase, con dos finalidades:

  1. documentar el estado real de la columna de texto antes de intervenirla;
  2. muestrear de forma estratificada. Tomar las primeras N notas devuelve sobre
     todo notas corrientes, y lo que hace falta para construir un conjunto de
     referencia son las difíciles. Para pedir las raras primero hay que saber
     medir la rareza, y eso es lo que hace la puntuación de este módulo.

QUÉ NO HACE
    No decide si una nota está bien o mal escrita: eso solo lo dice una persona
    al leerla. Aquí solo se detectan señales objetivas y contables, como la
    proporción de mayúsculas, la presencia de abreviaturas o los grupos de
    consonantes imposibles en español.

USO
    python -m NLP.evaluacion.escaneo                escanea el CSV ya limpio
    python -m NLP.evaluacion.escaneo --bd           escanea la tabla completa
    python -m NLP.evaluacion.escaneo --muestra 400  además escribe una muestra
                                                    estratificada para revisar
"""

import argparse
import csv
import re
from collections import Counter
from pathlib import Path

from NLP import rutas

csv.field_size_limit(10 ** 7)

RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


from NLP.nucleo.morfologia import sin_tildes  # la eñe se conserva; ver morfologia.py


# ==========================================================
# SEÑALES DETECTADAS
# ==========================================================

# Palabras frecuentes que suelen escribirse sin su tilde. No se corrigen aqui:
# solo se cuenta en cuantas notas aparecen sin acentuar.
PALABRAS_CON_TILDE = (
    "dias", "dia", "clinico", "clinica", "valoracion", "evolucion", "presion",
    "sintomas", "region", "colico", "cesarea", "toracico", "abdomen",
    "gestacion", "infeccion", "cirugia", "ecografia", "medico", "cronico",
)

# Abreviaturas de habla del servicio. Se listan para MEDIR cuantas notas las
# traen sin expandir; la expansion es tarea del diccionario coloquial.
ABREVIATURAS = (
    "gral", "pte", "pcte", "tto", "ant", "post", "izq", "der", "sup", "inf",
    "sem", "hrs", "hs", "mgs", "amp", "gts", "aprox", "aprx", "px", "qx",
    "cel", "acomp", "fam", "sec", "temp", "sat", "obs", "ref", "trat",
)

# Texto institucional: habla del sistema y no del paciente. Una nota compuesta
# sobre todo por estas frases no tiene contenido clinico aprovechable.
MARCAS_INSTITUCIONALES = (
    "entidad promotora", "red de atencion", "nivel de atencion", "afiliados",
    "disculpas", "molestias ocasionadas", "cierres de servicios",
    "urgencias vitales", "lamentamos", "deberan ser orientados",
)

MARCAS_OBSTETRICAS = (
    "gestante", "primigestante", "multigestante", "embarazo", "embarazada",
    "semanas de gestacion", "sms", "fum", "trabajo de parto", "contracciones",
    "sangrado vaginal", "movimientos fetales", "fcf", "cesarea",
)

RE_DOSIS = re.compile(r"\b\d+\s*(?:mg|gr|g|ml|mcg|ui|cc|mgs)\b", re.IGNORECASE)
RE_SIGNOS_VITALES = re.compile(
    r"\b(?:ta|fc|fr|sat|temp|t)\s*[:=]?\s*\d{2,3}", re.IGNORECASE)


def _clasificar(texto, siglas, vocabulario):
    """
    Analiza una nota y devuelve el par (etiquetas, número de tokens).

    Las etiquetas describen señales objetivas agrupadas en cuatro bloques:
    forma (mayúsculas, longitud, encabezados), ortografía (tildes ausentes,
    palabras partidas, grupos consonánticos imposibles), vocabulario (términos
    desconocidos, siglas, abreviaturas) y contenido (obstétrico, medicamentos,
    signos vitales, texto institucional).
    """
    crudo = str(texto)
    plano = sin_tildes(crudo.lower())
    tokens = RE_TOKEN.findall(crudo)
    minus = [t.lower() for t in tokens]
    etiquetas = set()

    if not tokens:
        etiquetas.add("vacia")
        return etiquetas, 0

    # --- forma ---
    letras = [c for c in crudo if c.isalpha()]
    if letras and sum(1 for c in letras if c.isupper()) / len(letras) > 0.9:
        etiquetas.add("mayusculas")

    if len(tokens) <= 4:
        etiquetas.add("muy_corta")
    elif len(tokens) >= 120:
        etiquetas.add("muy_larga")

    if "\n" in crudo or re.search(r"\b\w{2,4}\s*:", crudo):
        etiquetas.add("con_encabezados")

    # --- ortografia ---
    sin_tilde = sum(1 for p in PALABRAS_CON_TILDE
                    if re.search(rf"(?<![\w]){p}(?![\w])", plano))
    if sin_tilde:
        etiquetas.add("tildes_faltantes")

    # Una consonante suelta delante de una palabra larga casi siempre es una
    # palabra partida al teclear. La 'y' queda fuera de la clase de caracteres
    # aunque sea consonante, porque como conjuncion es una palabra legitima e
    # incluirla disparaba la senal en una de cada cinco notas.
    if re.search(r"(?<=\s)[bcdfghjklmnpqrstvwxz]\s+\w{3,}", plano):
        etiquetas.add("palabra_partida")

    # cuatro consonantes seguidas no existen en espanol: es un error de
    # digitacion severo, no una palabra rara
    if re.search(r"[bcdfgjklmnpqrstvwxz]{4,}", plano):
        etiquetas.add("typo_duro")

    # --- vocabulario ---
    desconocidas = [t for t in minus
                    if len(t) >= 5 and t not in vocabulario and t not in siglas]
    if len(desconocidas) >= 3:
        etiquetas.add("muchas_desconocidas")

    n_siglas = sum(1 for t in minus if t in siglas)
    if n_siglas >= 4:
        etiquetas.add("muchas_siglas")

    if any(re.search(rf"(?<![\w]){a}(?![\w])", plano) for a in ABREVIATURAS):
        etiquetas.add("abreviaturas_de_habla")

    # --- contenido ---
    if any(m in plano for m in MARCAS_OBSTETRICAS):
        etiquetas.add("obstetrica")

    if RE_DOSIS.search(crudo):
        etiquetas.add("con_medicamentos")

    if RE_SIGNOS_VITALES.search(crudo):
        etiquetas.add("con_signos_vitales")

    if any(m in plano for m in MARCAS_INSTITUCIONALES):
        etiquetas.add("texto_institucional")

    return etiquetas, len(tokens)


def rareza(etiquetas):
    """
    Puntuación de dificultad de una nota, como suma de los pesos de sus
    señales. Ordena el muestreo: una nota con errores severos, siglas y
    estructura pesa más que una de cuatro palabras, que puntúa en negativo.
    """
    PESOS = {
        "typo_duro": 3, "palabra_partida": 3, "muchas_desconocidas": 2,
        "muchas_siglas": 2, "abreviaturas_de_habla": 2, "obstetrica": 2,
        "con_medicamentos": 2, "con_encabezados": 1, "muy_larga": 1,
        "tildes_faltantes": 1, "con_signos_vitales": 1,
        "texto_institucional": 1, "mayusculas": 1, "muy_corta": -1,
    }
    return sum(PESOS.get(e, 0) for e in etiquetas)


# ==========================================================
# ESCANEO
# ==========================================================

def escanear(textos):
    """
    Clasifica todas las notas y devuelve el par (recuento, filas): un contador
    de señales sobre el corpus y una fila por nota con sus etiquetas, su número
    de tokens y su puntuación de dificultad.
    """
    from NLP.nucleo import linguistica
    from NLP.nucleo import reglas
    reglas.cargar()

    vocabulario = set()
    if linguistica.disponible():
        pass  # se consulta token a token mas abajo

    siglas = set(reglas.SIGLAS)

    class _Vocab:
        """
        Vista del vocabulario de spaCy que responde al operador `in` y guarda
        en caché cada consulta, porque las mismas palabras se preguntan una y
        otra vez a lo largo del corpus.
        """
        def __init__(self):
            self._cache = {}

        def __contains__(self, palabra):
            if palabra not in self._cache:
                self._cache[palabra] = linguistica.en_vocabulario(palabra)
            return self._cache[palabra]

    vocabulario = _Vocab()

    conteo = Counter()
    filas = []
    for indice, texto in enumerate(textos):
        etiquetas, n = _clasificar(texto, siglas, vocabulario)
        conteo.update(etiquetas)
        filas.append({"indice": indice, "etiquetas": sorted(etiquetas),
                      "tokens": n, "rareza": rareza(etiquetas)})
    return conteo, filas


def muestrear(filas, cuantas, por_estrato=None):
    """
    Selecciona `cuantas` notas cubriendo todas las clases de problema, en lugar
    de tomar las primeras, que serían sobre todo notas corrientes. Devuelve un
    diccionario {índice de nota: etiqueta por la que entró}.

    Las etiquetas se recorren de la menos a la más frecuente y de cada una se
    toman las notas más difíciles, de modo que las clases minoritarias queden
    representadas. Si con eso no se llena el cupo, se completa con las notas de
    mayor dificultad que aún no estén elegidas.
    """
    por_etiqueta = {}
    for f in filas:
        for e in f["etiquetas"]:
            por_etiqueta.setdefault(e, []).append(f)

    orden = sorted(por_etiqueta, key=lambda e: len(por_etiqueta[e]))
    cupo = por_estrato or max(cuantas // max(len(orden), 1), 1)

    elegidas = {}
    for etiqueta in orden:
        candidatas = sorted(por_etiqueta[etiqueta],
                            key=lambda f: -f["rareza"])
        tomadas = 0
        for f in candidatas:
            if f["indice"] in elegidas:
                continue
            elegidas[f["indice"]] = etiqueta
            tomadas += 1
            if tomadas >= cupo or len(elegidas) >= cuantas:
                break
        if len(elegidas) >= cuantas:
            break

    # si sobra cupo, se completa con las mas raras que falten
    if len(elegidas) < cuantas:
        for f in sorted(filas, key=lambda f: -f["rareza"]):
            if f["indice"] not in elegidas:
                elegidas[f["indice"]] = "relleno_por_rareza"
            if len(elegidas) >= cuantas:
                break

    return elegidas


def informe(conteo, filas, total):
    """
    Informe legible del escaneo: frecuencia de cada señal, distribución de la
    dificultad y cuántas notas no presentan ningún problema detectable.
    """
    lineas = ["ESCANEO DEL CORPUS", "=" * 62,
              f"Notas analizadas: {total:,}", "",
              "SENALES ENCONTRADAS"]
    for etiqueta, veces in conteo.most_common():
        lineas.append(f"  {etiqueta:24} {veces:>7,}  {100*veces/total:5.1f}%")

    dist = Counter(f["rareza"] for f in filas)
    lineas += ["", "DIFICULTAD (suma de senales por nota)"]
    for r in sorted(dist, reverse=True)[:12]:
        lineas.append(f"  rareza {r:>3}: {dist[r]:>7,}")

    limpias = sum(1 for f in filas if not f["etiquetas"])
    lineas += ["", f"Notas sin ninguna senal de problema: {limpias:,} "
                   f"({100*limpias/total:.1f}%)"]
    return "\n".join(lineas)


def main():
    """
    Escanea el corpus e imprime el informe. Con --muestra escribe además el CSV
    de revisión manual, cuyas dos últimas columnas van vacías a propósito: son
    las que rellena quien revisa.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=rutas.TRIAGE_LIMPIO)
    ap.add_argument("--bd", action="store_true",
                    help="lee la tabla completa en vez del CSV")
    ap.add_argument("--muestra", type=int, default=0,
                    help="escribe una muestra estratificada de N notas")
    ap.add_argument("--salida", type=Path,
                    default=rutas.MUESTRA_REVISION)
    args = ap.parse_args()

    if args.bd:
        import pandas as pd
        from NLP.nucleo.conexion_bd import obtener_engine
        df = pd.read_sql(
            "SELECT OID, HCTMOTCON FROM DIM_TRIAGE WHERE HCTMOTCON IS NOT NULL "
            "AND LTRIM(RTRIM(HCTMOTCON)) <> ''", obtener_engine())
        ids = df["OID"].tolist()
        textos = df["HCTMOTCON"].astype(str).tolist()
    else:
        with open(args.csv, encoding="utf-8-sig", newline="") as f:
            registros = list(csv.DictReader(f))
        ids = [r["OID"] for r in registros]
        textos = [r["texto_original"] for r in registros]

    print(f"Escaneando {len(textos):,} notas...")
    conteo, filas = escanear(textos)
    print()
    print(informe(conteo, filas, len(textos)))

    if args.muestra:
        elegidas = muestrear(filas, args.muestra)
        por_indice = {f["indice"]: f for f in filas}
        with open(args.salida, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(["OID", "estrato", "rareza", "etiquetas",
                        "texto_original", "texto_corregido_a_mano", "notas_revision"])
            for indice, estrato in sorted(elegidas.items(),
                                          key=lambda kv: -por_indice[kv[0]]["rareza"]):
                d = por_indice[indice]
                w.writerow([ids[indice], estrato, d["rareza"],
                            "|".join(d["etiquetas"]), textos[indice], "", ""])
        print(f"\nMuestra de {len(elegidas):,} notas: {args.salida}")
        print("Las columnas texto_corregido_a_mano y notas_revision van vacias:")
        print("son las que se llenan al revisar.")


if __name__ == "__main__":
    main()
