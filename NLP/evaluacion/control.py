"""
Pasa la muestra de control por las fases 1-5 y muestra que hace cada una.

Es el bucle rapido de verificacion: segundos en vez de una hora. La muestra
vive en datos/evaluacion/muestra_control.csv, con una columna que dice que se
espera de cada nota. Ver NLP/docs/OPERACION.md 3.12.

    python -m NLP.evaluacion.control
    python -m NLP.evaluacion.control --csv <otra muestra> --fases
"""

import argparse
import sys

import pandas as pd

from NLP import procesar, rutas

RUTA_CONTROL = rutas.DATOS / "evaluacion" / "muestra_control.csv"


def cargar_recursos():
    """Carga lo mismo que una corrida normal, sin base de datos."""
    from NLP.depuracion import depuracion
    from NLP.fase2_ortografia import ortografia
    from NLP.fase3_normalizacion import normalizacion
    from NLP.recursos import casing
    from NLP.reduccion import reduccion

    ortografia.cargar_siglas()
    ortografia.cargar_lexico_clinico()
    casing.cargar()
    normalizacion.cargar()
    depuracion.cargar()
    reduccion.cargar_lexico()
    reduccion.cargar_lugares()

    # Frecuencias del corpus: sin ellas el corrector no distingue una errata de
    # una palabra rara, y la muestra mediria otro sistema distinto del real.
    from NLP.fase2_ortografia import candidatos, pesos

    tsv = rutas.DATOS / "lexicos" / "corpus_frecuencia.tsv"
    if tsv.exists():
        for linea in tsv.read_text(encoding="utf-8").splitlines():
            if linea.startswith("#") or not linea.strip():
                continue
            partes = linea.split("\t")
            if len(partes) >= 2 and partes[1].isdigit():
                candidatos.CONTEO[partes[0]] = int(partes[1])
        pesos.usar_conteo(candidatos.CONTEO)
        print(f"  frecuencias del corpus: {len(candidatos.CONTEO):,} formas")
    else:
        print("  AVISO: sin corpus_frecuencia.tsv; el corrector medira distinto "
              "que en una corrida real")


def procesar_muestra(df):
    """Corre las fases sobre la muestra y devuelve el DataFrame resultante."""
    trabajo = df[["OID", "HCTMOTCON"]].copy()
    trabajo = procesar.preparar(trabajo)
    conservadas, _senaladas = procesar.procesar_bloque(
        trabajo, cache={}, columna_juicio="texto_normalizado",
        normalizar=True, usar_llm=False)
    return conservadas


def imprimir(df, esperado, mostrar_fases=False):
    for _, fila in df.iterrows():
        oid = fila["OID"]
        print("=" * 78)
        print(f"{oid}   ESPERADO: {esperado.get(oid, '')}")
        print("-" * 78)
        print(f"  original    : {fila['texto_original'][:300]}")
        if mostrar_fases:
            print(f"  corregido   : {str(fila.get('texto_corregido', ''))[:300]}")
            print(f"  normalizado : {str(fila.get('texto_normalizado', ''))[:300]}")
        print(f"  EMBEDDING   : {str(fila.get('texto_embedding', ''))[:300]}")
        descarte = str(fila.get("motivo_descarte", ""))
        if descarte:
            print(f"  descarte    : {descarte}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--csv", default=str(RUTA_CONTROL))
    ap.add_argument("--fases", action="store_true",
                    help="mostrar tambien el texto corregido y el normalizado")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
    esperado = dict(zip(df["OID"], df.get("que_se_espera", [""] * len(df))))
    print(f"Muestra de control: {len(df)} notas de {args.csv}\n")
    cargar_recursos()
    print()
    imprimir(procesar_muestra(df), esperado, args.fases)


if __name__ == "__main__":
    main()
