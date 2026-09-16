"""
Minero de abreviaturas, tecnica AbreMES (E3.8, NLP/docs/PLAN.md §8; detalle y
decisiones en NLP/docs/bitacora/2026-09-16-E3.8.md). Busca en el corpus
'SIGLA (definicion)' y 'definicion (SIGLA)' y agrega candidatos con
frecuencia. No escribe en diccionario_siglas.json. Uso:
python -m NLP.recursos.abreviaturas
"""

import re
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from NLP import rutas
from NLP.nucleo.salida import EscritorCSV

SALIDA_DIR = rutas.SALIDAS / "e3_7_8"
SALIDA = SALIDA_DIR / "abreviaturas_candidatas.csv"

LONGITUD_SIGLA_MIN = 2
LONGITUD_SIGLA_MAX = 8
PALABRAS_DEFINICION_MAX = 6   # ventana hacia atras para 'definicion (SIGLA)'

# Con >=2 sobreviven 16 candidatos y 0 nuevos no ambiguos (medido 2026-09-16,
# 94.238 notas): en esta nota tan corta, un patron 'SIGLA (definicion)' casi
# nunca se repite igual dos veces, y exigir repeticion tira candidatos reales
# de una sola aparicion ('hvda -> hemorragia via digestiva alta', 'g2a1v0'
# como notacion obstetrica). Se deja en 1 -es la persona quien filtra el
# ruido de una sola coincidencia, no el umbral- y se documenta en la
# bitacora del item.
FRECUENCIA_MINIMA = 1

_LETRA_O_DIGITO = "A-Za-z0-9ÁÉÍÓÚÑáéíóúñ"
RE_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")
RE_CORTE = re.compile(r"[.,;:!?\n]")

# El (?<!..) y (?!..) exigen que la sigla sea una palabra completa: sin ellos
# 'URGENCIAS (REGIMEN SUBSIDIADO)' entrega 'RGENCIAS' como sigla (el motor
# probaba empezar en cualquier posicion dentro de la racha de mayusculas).
RE_SIGLA_DEFINICION = re.compile(
    r"(?<![%s])([A-ZÁÉÍÓÚÑ0-9]{%d,%d})(?![%s])\s*\(\s*([^()]{3,80}?)\s*\)"
    % (_LETRA_O_DIGITO, LONGITUD_SIGLA_MIN, LONGITUD_SIGLA_MAX, _LETRA_O_DIGITO)
)
RE_DEFINICION_SIGLA = re.compile(
    r"(?<![%s])\(([A-ZÁÉÍÓÚÑ0-9]{%d,%d})\)(?![%s])"
    % (_LETRA_O_DIGITO, LONGITUD_SIGLA_MIN, LONGITUD_SIGLA_MAX, _LETRA_O_DIGITO)
)


def _sigla_valida(token):
    """Descarta valores puramente numericos (dosis, tensiones, fechas entre parentesis)."""
    return any(c.isalpha() for c in token) and not token.isdigit()


def candidatos_sigla_definicion(texto):
    """Coincidencias 'SIGLA (definicion)': lista de (sigla, definicion) en minuscula."""
    salida = []
    for m in RE_SIGLA_DEFINICION.finditer(texto):
        sigla, contenido = m.group(1), m.group(2)
        if not _sigla_valida(sigla):
            continue
        palabras = RE_PALABRA.findall(contenido)
        if not palabras:
            continue
        salida.append((sigla.lower(), " ".join(w.lower() for w in palabras)))
    return salida


def candidatos_definicion_sigla(texto):
    """
    Coincidencias 'definicion (SIGLA)': toma hasta PALABRAS_DEFINICION_MAX
    palabras inmediatamente anteriores al parentesis, sin cruzar puntuacion.
    """
    salida = []
    for m in RE_DEFINICION_SIGLA.finditer(texto):
        sigla = m.group(1)
        if not _sigla_valida(sigla):
            continue
        tramo = RE_CORTE.split(texto[:m.start()])[-1]
        palabras = RE_PALABRA.findall(tramo)[-PALABRAS_DEFINICION_MAX:]
        if not palabras:
            continue
        salida.append((sigla.lower(), " ".join(w.lower() for w in palabras)))
    return salida


def minar(textos):
    """
    Recorre el corpus con las dos variantes del patron y agrega ocurrencias
    por (sigla, definicion). Devuelve sigla -> Counter(definicion -> veces).
    """
    agregados = defaultdict(Counter)
    for texto in textos:
        if not texto:
            continue
        texto = str(texto)
        for sigla, definicion in candidatos_sigla_definicion(texto):
            agregados[sigla][definicion] += 1
        for sigla, definicion in candidatos_definicion_sigla(texto):
            agregados[sigla][definicion] += 1
    return agregados


def siglas_conocidas(ruta=rutas.DICCIONARIO_SIGLAS):
    """
    Claves ya presentes en diccionario_siglas.json, en minuscula, de todos los
    grupos sigla->significado (deja fuera correcciones_directas, que no son
    siglas sino pares typo->correccion).
    """
    import json

    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    conocidas = set()
    for clave, valor in datos.items():
        if clave.startswith("_") or clave == "correcciones_directas":
            continue
        if isinstance(valor, dict):
            conocidas.update(k.lower() for k in valor)
    return conocidas


def candidatos(agregados, conocidas, es_palabra=None):
    """
    Una fila por sigla: definicion mas frecuente, si tiene mas de un sentido
    (ambigua) y si ya esta protegida. `es_palabra` descarta palabras
    corrientes (ver NLP/docs/bitacora/2026-09-16-E3.8.md, seccion Decision).
    """
    filas = []
    for sigla, definiciones in agregados.items():
        total = sum(definiciones.values())
        if total < FRECUENCIA_MINIMA:
            continue
        if es_palabra is not None and es_palabra(sigla):
            continue
        definicion_principal, ocurrencias_principal = definiciones.most_common(1)[0]
        alternativas = "; ".join(
            f"{d} ({n})" for d, n in definiciones.most_common() if d != definicion_principal
        )
        filas.append({
            "sigla": sigla,
            "definicion": definicion_principal,
            "ocurrencias": ocurrencias_principal,
            "ocurrencias_totales": total,
            "ambigua": len(definiciones) > 1,
            "ya_en_diccionario": sigla in conocidas,
            "definiciones_alternativas": alternativas,
        })
    # segunda llave alfabetica: con FRECUENCIA_MINIMA=1 muchos candidatos
    # empatan en una sola ocurrencia y el orden debe ser reproducible
    filas.sort(key=lambda f: (-f["ocurrencias_totales"], f["sigla"]))
    return filas


CAMPOS = ["sigla", "definicion", "ocurrencias", "ocurrencias_totales", "ambigua",
          "ya_en_diccionario", "definiciones_alternativas"]


def escribir(filas, ruta=SALIDA):
    """Escribe el CSV de candidatos con NLP/nucleo/salida.py (PLAN.md §4.5). Devuelve el total de filas."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    escritor = EscritorCSV(ruta, CAMPOS)
    escritor.agregar(pd.DataFrame(filas, columns=CAMPOS))
    escritor.cerrar()
    return len(filas)


def _cargar_corpus():
    """
    Notas del corpus para minar: la base de datos si responde, o si no
    triage_limpio.csv (columna texto_original, solo lectura). Devuelve
    (serie de textos, descripcion de la fuente).
    """
    try:
        from NLP.nucleo.conexion_bd import obtener_engine
        try:
            from NLP.procesar import COLUMNA, TABLA
        except ImportError:
            COLUMNA, TABLA = "HCTMOTCON", "DIM_TRIAGE"

        engine = obtener_engine()
        consulta = (
            f"SELECT {COLUMNA} FROM {TABLA} "
            f"WHERE {COLUMNA} IS NOT NULL AND LTRIM(RTRIM({COLUMNA})) <> ''"
        )
        df = pd.read_sql(consulta, engine)
        return df[COLUMNA], f"base de datos {TABLA}.{COLUMNA} ({len(df):,} notas)"
    except Exception as exc:
        df = pd.read_csv(rutas.TRIAGE_LIMPIO, encoding="utf-8-sig")
        return (
            df["texto_original"],
            f"{rutas.TRIAGE_LIMPIO} columna texto_original "
            f"({len(df):,} notas) -- BD no disponible: {exc}",
        )


def main():
    import sys

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

    textos, fuente = _cargar_corpus()
    print(f"Fuente: {fuente}")

    from NLP.nucleo import linguistica

    agregados = minar(textos)
    conocidas = siglas_conocidas()
    filas = candidatos(agregados, conocidas, es_palabra=linguistica.en_vocabulario)
    total = escribir(filas)

    ambiguas = sum(1 for f in filas if f["ambigua"])
    ya_en_dic = sum(1 for f in filas if f["ya_en_diccionario"])
    nuevas_no_ambiguas = sum(
        1 for f in filas if not f["ambigua"] and not f["ya_en_diccionario"]
    )

    print(f"\n  {total:,} candidatos (sigla, definicion mas frecuente)")
    print(f"  {ambiguas:,} ambiguos (mas de un sentido observado)")
    print(f"  {ya_en_dic:,} ya presentes en diccionario_siglas.json")
    print(f"  {nuevas_no_ambiguas:,} nuevos y no ambiguos")
    print(f"\nArchivo: {SALIDA}")


if __name__ == "__main__":
    main()
