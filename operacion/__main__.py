"""
    python -m operacion                 reentrena, predice 28 días, guarda, verifica lo pasado y calcula el semáforo
    python -m operacion --extraer       lo mismo, pero antes baja los conteos de SQL Server (solo en el hospital)
    python -m operacion --estado        solo el semáforo, sin reentrenar
    python -m operacion --modelo M3s    otra receta (por defecto C0r; ver docs/OPERACION.md)

Después: streamlit run operacion/tablero.py
"""
import argparse
import sys

import operacion as op


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m operacion")
    ap.add_argument("--extraer", action="store_true", help="bajar los conteos de SQL Server antes de predecir")
    ap.add_argument("--estado", action="store_true", help="solo verificar y calcular el semáforo")
    ap.add_argument("--modelo", default=op.MODELO, choices=["C0r", "M3s"])
    a = ap.parse_args(argv)
    if a.extraer:
        print("Bajando conteos agregados de la base..."); op.extraer()
    if not a.estado:
        D, W, R = op.predecir(a.modelo)
        c, nueva = op.guardar(D, W, R)
        print(f"{'Guardada' if nueva else 'Ya existía (no se rehace)'}: {c}")
    V = op.verificar()
    Hs = op.historial()
    if not Hs.empty: print(f"Historial: {len(Hs)} días con predicción y dato real ({Hs.fecha.min().date()} a {Hs.fecha.max().date()})")
    E = op.semaforo(V)
    print(f"\nSemáforo: {E['general'].upper()}")
    for s in E["señales"]: print(f"  [{s['nivel']:>8}] {s['que']}: {s['detalle']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
