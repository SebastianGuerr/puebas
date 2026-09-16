"""
Frecuencia de cada forma en el corpus propio (E3.3).

Cuenta `DIM_TRIAGE.HCTMOTCON`; si la BD no responde, cuenta `texto_original`
de `salidas/triage_limpio.csv`. Escribe `datos/lexicos/corpus_frecuencia.tsv`.
Uso: `python -m NLP.recursos.corpus_lexico`. Ver `docs/bitacora/2026-09-16-E3.3.md`.
"""

import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

import pandas as pd

from NLP import rutas

RUTA_SALIDA = rutas.DATOS / "lexicos" / "corpus_frecuencia.tsv"

TABLA = "DIM_TRIAGE"
COLUMNA = "HCTMOTCON"  # misma columna que procesar.COLUMNA

RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")


def _contar(textos):
    """Cuenta las formas en minúscula de un iterable de textos."""
    conteo = Counter()
    for t in textos:
        conteo.update(RE_PALABRA.findall(str(t).lower()))
    return conteo


def contar_bd():
    """
    Cuenta frecuencias sobre `DIM_TRIAGE.HCTMOTCON` completa. Devuelve
    (conteo, numero_de_notas) o levanta la excepcion de conexion si la base
    no responde: quien llama decide el respaldo.
    """
    from sqlalchemy import text

    from NLP.nucleo import conexion_bd

    engine = conexion_bd.obtener_engine()
    consulta = text(
        f"SELECT {COLUMNA} FROM {TABLA} "
        f"WHERE {COLUMNA} IS NOT NULL AND LTRIM(RTRIM({COLUMNA})) <> ''"
    )
    with engine.connect() as conexion:
        filas = [r[0] for r in conexion.execute(consulta)]
    return _contar(filas), len(filas)


def contar_csv(ruta=rutas.TRIAGE_LIMPIO):
    """Respaldo: cuenta frecuencias sobre `texto_original` del CSV vigente."""
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    return _contar(df["texto_original"]), len(df)


def escribir(conteo, fuente, notas, ruta=RUTA_SALIDA):
    """
    Escribe el TSV `forma<TAB>frecuencia`, ordenado por frecuencia
    descendente, con una cabecera de comentario (`#`) que declara la fuente,
    la fecha y el numero de notas contadas.
    """
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        f"# fuente: {fuente}",
        f"# fecha: {date.today().isoformat()}",
        f"# notas contadas: {notas:,}",
        f"# formas distintas: {len(conteo):,}",
        "# columnas: forma<TAB>frecuencia",
    ]
    for forma, frecuencia in sorted(conteo.items(), key=lambda kv: (-kv[1], kv[0])):
        lineas.append(f"{forma}\t{frecuencia}")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return len(conteo)


def cargar(ruta=RUTA_SALIDA):
    """
    Lee un `corpus_frecuencia.tsv` ya generado y lo devuelve como dict
    forma -> frecuencia. Ignora las lineas de cabecera (`#`).
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return {}
    conteo = {}
    for linea in ruta.read_text(encoding="utf-8").splitlines():
        if not linea or linea.startswith("#"):
            continue
        forma, frecuencia = linea.split("\t")
        conteo[forma] = int(frecuencia)
    return conteo


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        conteo, notas = contar_bd()
        fuente = f"base de datos {TABLA}.{COLUMNA} (DWSES, ls-cobra)"
        print(f"contado sobre la base de datos: {notas:,} notas")
    except Exception as exc:
        print(f"aviso: la base de datos no respondio ({exc}); "
              f"se cuenta sobre {rutas.TRIAGE_LIMPIO.name}")
        conteo, notas = contar_csv()
        fuente = f"{rutas.TRIAGE_LIMPIO.name} (columna texto_original, respaldo sin BD)"
        print(f"contado sobre el CSV: {notas:,} notas")

    formas = escribir(conteo, fuente, notas)
    print(f"{formas:,} formas distintas escritas en {RUTA_SALIDA}")


if __name__ == "__main__":
    main()
