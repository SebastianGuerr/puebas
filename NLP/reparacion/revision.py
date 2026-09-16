"""
Revision del informe de reparacion, termino a termino (item E0.2 del plan).

Ver docs/ARQUITECTURA.md, ficha `reparacion/revision.py` (S2.10). Uso:

    python -m NLP.reparacion.revision
    python -m NLP.reparacion.revision --termino cefalea
"""

import argparse
import re
import sys
from collections import Counter, defaultdict

import pandas as pd

from NLP import rutas
from NLP.reparacion import comparacion

INFORME = rutas.INFORME_REPARACION

# Caracteres de contexto a cada lado del término en los ejemplos.
CONTEXTO = 60


def cargar(ruta=INFORME):
    df = pd.read_csv(ruta, dtype=str, keep_default_na=False)
    esperadas = ["OID", "categoria", "detalle", "embedding_antes", "embedding_despues"]
    faltan = [c for c in esperadas if c not in df.columns]
    if faltan:
        raise SystemExit(f"{ruta} no trae las columnas {faltan}")
    return df


def terminos(detalle, prefijo):
    """Los términos de un detalle 'pierde: a, b' o 'recupera: a, b'."""
    if not detalle.startswith(prefijo):
        return []
    return [t.strip() for t in detalle[len(prefijo):].split(",") if t.strip()]


def por_termino(df, categoria, prefijo):
    """
    {termino: [OIDs]} para una categoria del informe. Se indexa por termino y
    no por nota: un termino basta para juzgar si la perdida importa.
    """
    indice = defaultdict(list)
    for _, fila in df[df["categoria"] == categoria].iterrows():
        for termino in terminos(fila["detalle"], prefijo):
            indice[termino].append(fila["OID"])
    return indice


def contexto(texto, termino):
    """El trozo del texto alrededor del término, para leer el uso real."""
    encaje = re.search(rf"\b{re.escape(termino)}\w*\b", texto, re.IGNORECASE)
    if not encaje:
        return texto[:CONTEXTO * 2]
    ini = max(0, encaje.start() - CONTEXTO)
    fin = min(len(texto), encaje.end() + CONTEXTO)
    return ("..." if ini else "") + texto[ini:fin] + ("..." if fin < len(texto) else "")


def resumen(df):
    total = len(df)
    print(f"INFORME DE REPARACION ({total:,} notas)\n")
    conteo = Counter(df["categoria"])
    for categoria in comparacion.ORDEN:
        veces = conteo.get(categoria, 0)
        print(f"  {veces:6,}  ({veces/total*100:5.1f}%)  {categoria}")

    perdidos = por_termino(df, comparacion.PERDIO, "pierde:")
    ganados = por_termino(df, comparacion.RECUPERO, "recupera:")

    print(f"\n  notas que pierden: {conteo.get(comparacion.PERDIO, 0):,} | "
          f"terminos distintos perdidos: {len(perdidos):,}")
    print(f"  notas que recuperan: {conteo.get(comparacion.RECUPERO, 0):,} | "
          f"terminos distintos recuperados: {len(ganados):,}")

    # CRITERIO DE E0.2: recupero_motivo > perdio_motivo y cero terminos con
    # veredicto real. Lo primero se decide aqui; lo segundo lo decide quien lee
    # la tabla de abajo, que por eso sale ENTERA y no truncada.
    veredicto = ("CUMPLE" if conteo.get(comparacion.RECUPERO, 0) >
                 conteo.get(comparacion.PERDIO, 0) else "NO CUMPLE")
    print(f"  recupero > perdio: {veredicto}")

    if perdidos:
        print(f"\nTODOS los terminos perdidos ({len(perdidos)}), por frecuencia:\n")
        print(f"  {'notas':>6}  {'termino':24}  tambien se recupera en")
        for termino, oids in sorted(perdidos.items(), key=lambda x: (-len(x[1]), x[0])):
            cruce = len(ganados.get(termino, []))
            print(f"  {len(oids):6}  {termino:24}  "
                  f"{cruce if cruce else '-':>6}")
    return perdidos


def detalle_termino(df, termino, limite=8):
    """Las notas donde se pierde un término, con su contexto antes y después."""
    filas = df[(df["categoria"] == comparacion.PERDIO)
               & df["detalle"].str.contains(rf"\b{re.escape(termino)}\b", regex=True)]
    print(f"\n'{termino}': {len(filas):,} notas\n")
    for _, fila in filas.head(limite).iterrows():
        print(f"  OID {fila['OID']}")
        print(f"    antes : {contexto(fila['embedding_antes'], termino)}")
        print(f"    ahora : {fila['embedding_despues'][:2 * CONTEXTO]}")
        print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--informe", default=str(INFORME))
    ap.add_argument("--termino", help="ver las notas donde se pierde este termino")
    ap.add_argument("--ejemplos", type=int, default=8)
    args = ap.parse_args()

    # Los terminos vienen de las notas y llevan tildes y eñes; la consola de
    # Windows es cp1252 y los destroza. El resto del repo lo evita escribiendo
    # solo ASCII, pero aqui el texto es el dato.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    df = cargar(args.informe)
    if args.termino:
        detalle_termino(df, args.termino, args.ejemplos)
        return
    resumen(df)


if __name__ == "__main__":
    main()
