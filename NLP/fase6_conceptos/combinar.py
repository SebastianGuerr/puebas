"""
Orquestador de la fase 6 (E5.7): aplica nivel 0, luego nivel 1 (si hay
indice guardado) y luego nivel 2 (solo notas largas) sobre una columna de
texto de un CSV de triage, y anade `concepto_snomed` / `concepto_termino`.
No se invoca desde `procesar.py`: es un paso aparte, tras bandera, tal como
exige PLAN.md §3 principio 8 y §7 (anadir columnas es transparente para
`embedding/`). Ver NLP/docs/FLUJO.md (fase 6) y
decisiones/2026-09-16-E5.7.md.
"""

import argparse
import sys
import time

import pandas as pd

from NLP import rutas
from NLP.fase6_conceptos import nivel0, nivel1, nivel2
from NLP.nucleo.salida import EscritorCSV

COLUMNA_TEXTO = "texto_embedding"
COLUMNAS_SALIDA = ["OID", COLUMNA_TEXTO, "concepto_snomed", "concepto_termino", "nivel"]


def _procesar_texto(texto, usar_nivel1, indice_nivel1, usar_nivel2):
    """(codigos, terminos, nivel) para un texto: intenta 0, luego 1, luego 2."""
    codigos, terminos = nivel0.anotar(texto)
    if codigos:
        return codigos, terminos, 0
    if usar_nivel1 and indice_nivel1 is not None:
        resultado = nivel1.vecino_mas_cercano([texto], indice_nivel1)[0]
        if resultado:
            return resultado[0], resultado[1], 1
    if usar_nivel2:
        codigos, terminos = nivel2.anotar(
            texto, indice_nivel1=indice_nivel1 if usar_nivel1 else None
        )
        if codigos:
            return codigos, terminos, 2
    return "", "", None


def procesar_csv(
    ruta_entrada,
    ruta_salida,
    limite=None,
    usar_nivel1=True,
    usar_nivel2=True,
    indice_ruta=None,
):
    """
    Lee `ruta_entrada` (solo lectura), anade las columnas de concepto sobre
    `COLUMNA_TEXTO` y escribe `ruta_salida` con `OID, texto_embedding,
    concepto_snomed, concepto_termino, nivel` (nivel: 0, 1, 2 o vacio si no
    hubo coincidencia). Devuelve el diccionario de cobertura por nivel.
    """
    df = pd.read_csv(ruta_entrada, encoding="utf-8-sig")
    if limite:
        df = df.head(limite).copy()

    indice_nivel1 = None
    if usar_nivel1:
        indice_nivel1 = nivel1.cargar_indice(indice_ruta)
        if indice_nivel1 is None:
            print("Aviso: no hay indice de nivel 1 guardado; se desactiva para esta corrida.")
            usar_nivel1 = False

    escritor = EscritorCSV(ruta_salida, COLUMNAS_SALIDA)
    cobertura = {0: 0, 1: 0, 2: 0, None: 0}
    t0 = time.time()
    filas = []
    for i, (oid, texto) in enumerate(zip(df["OID"], df[COLUMNA_TEXTO].astype(str)), 1):
        codigos, terminos, nivel = _procesar_texto(texto, usar_nivel1, indice_nivel1, usar_nivel2)
        cobertura[nivel] += 1
        filas.append({
            "OID": oid,
            COLUMNA_TEXTO: texto,
            "concepto_snomed": codigos,
            "concepto_termino": terminos,
            "nivel": "" if nivel is None else nivel,
        })
        if i % 200 == 0 or i == len(df):
            escritor.agregar(pd.DataFrame(filas))
            filas = []
            print(f"{i}/{len(df)} en {time.time() - t0:.1f} s")
    if filas:
        escritor.agregar(pd.DataFrame(filas))
    escritor.cerrar()

    total = len(df)
    duracion = time.time() - t0
    print(f"total: {total} notas en {duracion:.1f} s ({duracion / total * 1000:.2f} ms/nota)")
    for nivel, n in cobertura.items():
        print(f"nivel {nivel}: {n} ({n / total * 100:.2f} %)")
    print(f"cobertura 0+1: {(cobertura[0] + cobertura[1]) / total * 100:.2f} %")
    return cobertura


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=str(rutas.TRIAGE_LIMPIO))
    parser.add_argument("--salida", default=str(rutas.FASE6_SALIDAS / "conceptos.csv"))
    parser.add_argument("--limite", type=int, default=None)
    parser.add_argument("--sin-nivel1", action="store_true")
    parser.add_argument("--sin-nivel2", action="store_true")
    parser.add_argument("--indice", default=None)
    args = parser.parse_args()

    rutas.FASE6_SALIDAS.mkdir(exist_ok=True)
    procesar_csv(
        args.csv,
        args.salida,
        limite=args.limite,
        usar_nivel1=not args.sin_nivel1,
        usar_nivel2=not args.sin_nivel2,
        indice_ruta=args.indice,
    )


if __name__ == "__main__":
    main()
