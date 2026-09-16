"""
Fase 4. Genera el archivo estructurado a partir del CSV ya limpio.

    python -m embedding.estructurar
    python -m embedding.estructurar --csv "D:\\ruta\\a\\triage_limpio.csv"

Sin argumentos toma el CSV que dejan las fases 1 a 3. Con --csv usa la ruta
indicada solo para esa corrida, sin editar nada.

    LEE      el CSV de entrada, que no se modifica en ningún momento
    ESCRIBE  triage_estructurado.jsonl  un registro JSON por línea
             triage_estructurado.json   el mismo contenido como lista
             resumen_estructuracion.txt distribución por categoría y cobertura

POR QUÉ JSONL ADEMÁS DE JSON
    Un array con decenas de miles de objetos hay que cargarlo entero en memoria
    para leer uno solo. En JSONL cada línea es un registro independiente, de modo
    que se procesa en streaming y se lee por partes. El array completo se genera
    también, porque es más cómodo para inspeccionarlo a mano.

QUÉ COLUMNA SE USA
    La primera disponible de COLUMNAS_TEXTO, que están en orden de preferencia.
    El texto normalizado es el mejor punto de partida porque lleva las siglas
    expandidas y los coloquialismos anotados, que es lo que permite al catálogo
    reconocer una expresión popular como el síntoma que le corresponde.
"""

import argparse
import json
from pathlib import Path

import pandas as pd

from embedding import extraccion
from embedding import rutas

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

# Las rutas concretas viven en embedding/rutas.py.
CARPETA_PROYECTO = rutas.PROYECTO
CARPETA_SALIDA = rutas.SALIDAS
CSV_POR_DEFECTO = rutas.TRIAGE_LIMPIO

# texto_limpio no se escribe nunca en el CSV: es una columna intermedia de
# procesar.py. Figuraba aqui y hacia creer que el contrato la admitia (E6.4).
COLUMNAS_TEXTO = ["texto_normalizado", "texto_corregido", "texto_original"]
COLUMNA_ID = "OID"

FORMATO_JSON = True     # ademas del jsonl, escribe el array completo
INCLUIR_TEXTO = True    # conserva el texto de origen en cada registro
LIMITE = None           # None = todos los registros


def elegir_columna(df):
    """
    Primera columna de texto disponible, según el orden de preferencia de
    COLUMNAS_TEXTO. Lanza ValueError si el CSV no trae ninguna, indicando cuáles
    se buscaban y cuáles hay.
    """
    for columna in COLUMNAS_TEXTO:
        if columna in df.columns:
            return columna
    raise ValueError(
        f"El CSV no tiene ninguna columna de texto conocida: {COLUMNAS_TEXTO}\n"
        f"Columnas encontradas: {list(df.columns)}")


def barra(iterable, total, descripcion):
    """Envuelve el iterable en una barra de progreso, si tqdm está instalado."""
    try:
        from tqdm import tqdm
        return tqdm(iterable, total=total, desc=descripcion, unit="nota")
    except ModuleNotFoundError:
        return iterable


def escribir_resumen(registros, ruta):
    """
    Escribe el resumen de la corrida y devuelve su contenido para imprimirlo.

    La cobertura del catálogo es la métrica que importa: indica en qué
    proporción de las notas se reconoció al menos un síntoma. Si baja, el
    catálogo se ha quedado corto frente al vocabulario del corpus.
    """
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
    """
    Ejecuta la fase: lee el CSV, carga el catálogo, extrae un registro por nota
    y escribe las tres salidas. El CSV de entrada nunca se modifica.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=Path, default=None,
                    help="ruta completa al CSV de entrada")
    args = ap.parse_args()

    entrada_csv = args.csv or CSV_POR_DEFECTO
    entrada_csv = entrada_csv.resolve()
    carpeta_salida = CARPETA_SALIDA
    salida_jsonl = carpeta_salida / "triage_estructurado.jsonl"
    salida_json = carpeta_salida / "triage_estructurado.json"
    salida_resumen = carpeta_salida / "resumen_estructuracion.txt"

    print(f"Leyendo {entrada_csv}...")
    if not entrada_csv.exists():
        raise SystemExit(
            f"No existe {entrada_csv}\n"
            f"Corre antes 'python -m NLP.procesar', o pasa la ruta con --csv.")

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
