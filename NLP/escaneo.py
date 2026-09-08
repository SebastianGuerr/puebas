"""
Escaneo del corpus: que tipos de problema traen las notas y en que proporcion.

PARA QUE SIRVE
    Antes de corregir hace falta saber que hay. Este modulo no corrige nada:
    clasifica cada nota segun los problemas que presenta y cuenta cuantas hay
    de cada clase. Sirve para dos cosas:

      1. documentar el estado real de la columna HCTMOTCON;
      2. muestrear de forma estratificada. Tomar las primeras 10.000 notas da
         sobre todo notas corrientes; lo que hace falta para construir un
         conjunto de referencia son las raras, y para pedir las raras primero
         hay que saber medir la rareza.

COMO SE USA
    python escaneo.py                    escanea NLP/triage_limpio.csv
    python escaneo.py --bd               escanea la tabla completa (92.597)
    python escaneo.py --muestra 400      ademas escribe una muestra estratificada

QUE NO HACE
    No decide si una nota esta bien o mal escrita: eso solo lo dice una persona
    leyendola. Aca solo se detectan senales objetivas y contables.
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

csv.field_size_limit(10 ** 7)

RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


from morfologia import sin_tildes  # la eñe se conserva; ver morfologia.py


# ==========================================================
# SENALES
# ==========================================================

# Vocales acentuadas que faltan casi siempre. No se corrige aca: solo se cuenta
# cuantas notas escriben sin tilde una palabra que la lleva.
PALABRAS_CON_TILDE = (
    "dias", "dia", "clinico", "clinica", "valoracion", "evolucion", "presion",
    "sintomas", "region", "colico", "cesarea", "toracico", "abdomen",
    "gestacion", "infeccion", "cirugia", "ecografia", "medico", "cronico",
)

# Abreviaturas de habla del servicio. Se listan para MEDIR cuantas hay sin
# expandir, no para expandirlas: la expansion vive en diccionario_coloquial.
ABREVIATURAS = (
    "gral", "pte", "pcte", "tto", "ant", "post", "izq", "der", "sup", "inf",
    "sem", "hrs", "hs", "mgs", "amp", "gts", "aprox", "aprx", "px", "qx",
    "cel", "acomp", "fam", "sec", "temp", "sat", "obs", "ref", "trat",
)

# Bloque institucional: no describe al paciente. Si la nota es sobre todo esto,
# no tiene contenido clinico util.
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
    """Senales objetivas de una nota. Devuelve un conjunto de etiquetas."""
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

    # Token de una letra suelto antes de una palabra larga: casi siempre es una
    # palabra partida al teclear ('s eindia redireccionar', 'g estante').
    #
    # La 'y' queda fuera aunque sea consonante: es la conjuncion, y es palabra
    # legitima. Incluirla hacia que este detector marcara el 21% del corpus
    # cuando el fenomeno real afecta al 0,6%. De 8.600 coincidencias, 8.426
    # eran 'y'.
    if re.search(r"(?<=\s)[bcdfghjklmnpqrstvwxz]\s+\w{3,}", plano):
        etiquetas.add("palabra_partida")

    # tres consonantes seguidas poco frecuentes en espanol: marca de typo duro
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
    Cuanto cuesta corregir esta nota. Sirve para ordenar el muestreo: una nota
    con typos duros, siglas y estructura pesa mas que una de cuatro palabras.
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
    import linguistica
    import reglas
    reglas.cargar()

    vocabulario = set()
    if linguistica.disponible():
        pass  # se consulta token a token mas abajo

    siglas = set(reglas.SIGLAS)

    class _Vocab:
        """Vocabulario de spaCy con cache: se consulta muchas veces por nota."""
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
    Muestra estratificada: cubre todas las clases de problema en vez de tomar
    las primeras N, que serian sobre todo notas corrientes.

    Se recorren las etiquetas de la menos frecuente a la mas frecuente y se
    toman las notas mas raras de cada una. Asi las clases minoritarias
    (obstetricas complejas, notas con medicamentos) quedan representadas.
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=BASE_DIR / "triage_limpio.csv")
    ap.add_argument("--bd", action="store_true",
                    help="lee la tabla completa en vez del CSV")
    ap.add_argument("--muestra", type=int, default=0,
                    help="escribe una muestra estratificada de N notas")
    ap.add_argument("--salida", type=Path,
                    default=BASE_DIR / "muestra_revision.csv")
    args = ap.parse_args()

    if args.bd:
        import pandas as pd
        from conexion_bd import obtener_engine
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
