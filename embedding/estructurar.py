"""
Fase 4. Genera el JSON estructurado a partir del CSV ya limpio.

    python estructurar.py
    python estructurar.py --csv "D:\\ruta\\a\\triage_limpio.csv"

Sin argumentos usa CARPETA_DATOS / NOMBRE_CSV de aca abajo. Con --csv usa esa
ruta para la corrida, sin editar nada.

LEE      el CSV de entrada          (no lo modifica en ningun momento)
ESCRIBE  triage_estructurado.jsonl  un registro JSON por linea
         triage_estructurado.json   el mismo contenido como lista, si se pide
         resumen_estructuracion.txt distribucion por categoria y cobertura

POR QUE JSONL Y NO UN UNICO JSON
    Un array de 30.000 objetos hay que cargarlo entero en memoria para leer
    uno solo. En JSONL cada linea es un registro independiente: se procesa en
    streaming y se lee con pandas.read_json(..., lines=True) sin cargar el
    resto. Si igual se quiere el array, FORMATO_JSON lo genera ademas.

QUE COLUMNA SE USA
    texto_normalizado si existe, y si no texto_corregido. El texto
    normalizado lleva las siglas expandidas y los coloquialismos anotados,
    que es lo que permite que el catalogo reconozca 'pita el oido' como
    tinnitus.
"""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

# la carpeta de este archivo va primero en sys.path para que los modulos
# vecinos (negacion, texto_embedding) se encuentren sin importar desde
# que directorio se ejecute el script
sys.path.insert(0, str(Path(__file__).resolve().parent))

import extraccion

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

# Rutas del proyecto. El CSV limpio vive en NLP y las salidas junto a este
# archivo, dentro de embedding.
CARPETA_PROYECTO = Path(__file__).resolve().parent.parent
CARPETA_DATOS = CARPETA_PROYECTO / "NLP"
CARPETA_SALIDA = Path(__file__).resolve().parent

NOMBRE_CSV = "triage_limpio.csv"

COLUMNAS_TEXTO = ["texto_normalizado", "texto_corregido", "texto_limpio", "texto_original"]
COLUMNA_ID = "OID"

FORMATO_JSON = True     # ademas del jsonl, escribe el array completo
INCLUIR_TEXTO = True    # conserva el texto de origen en cada registro
LIMITE = None           # None = todos los registros


def elegir_columna(df):
    for columna in COLUMNAS_TEXTO:
        if columna in df.columns:
            return columna
    raise ValueError(
        f"El CSV no tiene ninguna columna de texto conocida: {COLUMNAS_TEXTO}\n"
        f"Columnas encontradas: {list(df.columns)}")


def barra(iterable, total, descripcion):
    try:
        from tqdm import tqdm
        return tqdm(iterable, total=total, desc=descripcion, unit="nota")
    except ModuleNotFoundError:
        return iterable


def escribir_resumen(registros, ruta):
    datos = extraccion.resumen(registros)
    total = max(len(registros), 1)
    cobertura = 100 * (1 - datos["sin_sintoma_reconocido"] / total)

    lineas = [
        "RESUMEN DE ESTRUCTURACION",
        "=" * 60,
        f"Registros procesados      : {datos['registros']:,}",
        f"Sin sintoma reconocido    : {datos['sin_sintoma_reconocido']:,}",
        f"Confianza baja (<=0.3)    : {datos['confianza_baja']:,}",
        f"Cobertura del catalogo    : {cobertura:.1f}%",
        "",
        "DISTRIBUCION POR CATEGORIA",
    ]
    for categoria, veces in datos["categorias"]:
        pct = 100 * veces / total
        lineas.append(f"  {categoria:20} {veces:7,}  {pct:5.1f}%")

    lineas += ["", "SINTOMAS MAS FRECUENTES"]
    for sintoma, veces in datos["sintomas_frecuentes"]:
        lineas.append(f"  {sintoma:36} {veces:7,}")

    lineas += ["", "HALLAZGOS NEGADOS MAS FRECUENTES"]
    for sintoma, veces in datos["negados_frecuentes"]:
        lineas.append(f"  {sintoma:36} {veces:7,}")

    contenido = "\n".join(lineas)
    Path(ruta).write_text(contenido, encoding="utf-8")
    return contenido


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=None,
                    help="ruta completa al CSV de entrada")
    args = ap.parse_args()

    entrada_csv = args.csv or (CARPETA_DATOS / NOMBRE_CSV)
    entrada_csv = entrada_csv.resolve()
    carpeta_salida = CARPETA_SALIDA
    salida_jsonl = carpeta_salida / "triage_estructurado.jsonl"
    salida_json = carpeta_salida / "triage_estructurado.json"
    salida_resumen = carpeta_salida / "resumen_estructuracion.txt"

    print(f"Leyendo {entrada_csv}...")
    if not entrada_csv.exists():
        raise SystemExit(
            f"No existe {entrada_csv}\n"
            f"Corre antes procesar.py, o pasa la ruta con --csv, o edita "
            f"CARPETA_DATOS / NOMBRE_CSV al inicio de este archivo.")

    df = pd.read_csv(entrada_csv).fillna("")
    if LIMITE:
        df = df.head(LIMITE)

    columna = elegir_columna(df)
    print(f"  {len(df):,} registros | columna de texto: {columna}")

    print("Cargando catalogo de sintomas...")
    total = extraccion.cargar()
    print(f"  {total} sintomas canonicos")

    registros = []
    filas = list(zip(df[COLUMNA_ID], df[columna]))

    with open(salida_jsonl, "w", encoding="utf-8") as salida:
        for oid, texto in barra(filas, len(filas), "estructurando"):
            registro = extraccion.extraer(oid, texto)
            if not INCLUIR_TEXTO:
                registro.pop("texto", None)
            registros.append(registro)
            salida.write(json.dumps(registro, ensure_ascii=False) + "\n")

    if FORMATO_JSON:
        salida_json.write_text(
            json.dumps(registros, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n" + escribir_resumen(registros, salida_resumen))
    print(f"\nJSONL : {salida_jsonl}")
    if FORMATO_JSON:
        print(f"JSON  : {salida_json}")
    print(f"Resumen: {salida_resumen}")
    print("\nEl CSV de entrada no fue modificado.")


if __name__ == "__main__":
    main()
