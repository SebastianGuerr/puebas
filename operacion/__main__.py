"""
    python -m operacion                 reentrena el principal (M3s) y la comparación (C0r), uno detrás de otro; predice
                                        hasta diciembre, guarda las dos corridas, verifica lo pasado y calcula el semáforo
    python -m operacion --extraer       lo mismo, pero antes baja los conteos de SQL Server (solo en el hospital)
    python -m operacion --estado        solo el semáforo, sin reentrenar
    python -m operacion --modelo C0r    solo ese modelo (sin --modelo: los dos; ver docs/OPERACION.md)
    python -m operacion --ajustar       reaplica el registro de la red de hoy a la última corrida de cada modelo, sin
                                        reentrenar

Después: streamlit run operacion/tablero.py
"""
import argparse
import sys

import operacion as op


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m operacion")
    ap.add_argument("--extraer", action="store_true", help="bajar los conteos de SQL Server antes de predecir")
    ap.add_argument("--estado", action="store_true", help="solo verificar y calcular el semáforo")
    ap.add_argument("--modelo", default=None, choices=["C0r", "M3s"],
                    help=f"forzar un solo modelo (por defecto los dos: {op.MODELO} principal y {op.COMPARACION} comparación)")
    ap.add_argument("--ajustar", action="store_true",
                    help="reaplicar datos/eventos_red.csv a la última corrida, sin reentrenar (uso diario)")
    a = ap.parse_args(argv)
    modelos = [a.modelo] if a.modelo else [op.MODELO, op.COMPARACION]
    if a.ajustar:
        for m in modelos:
            if op.ultima_corrida(m) is None:
                print(f"{m}: no hay corrida guardada; nada que ajustar"); continue
            d, nuevo = op.ajustar(m)
            print(f"{m}: {'guardado' if nuevo else 'ya existía el de esta hora (no se rehace)'}: {d}")
        return 0
    if a.extraer:
        print("Bajando conteos agregados de la base..."); op.extraer()
    if not a.estado:
        op.correr(modelos)
    V = op.verificar()
    Hs = op.historial()
    if not Hs.empty: print(f"Historial: {len(Hs)} filas día × modelo con predicción y dato real ({Hs.fecha.min().date()} a {Hs.fecha.max().date()})")
    E = op.semaforo(V)
    print(f"\nSemáforo ({op.MODELO}, comparado con {op.COMPARACION}): {E['general'].upper()}")
    for s in E["señales"]:
        print(f"  [{s['nivel']:>8}] {s['que']}: {s['detalle']}" + ("" if s.get("en_general", True) else "  (no entra en el general)"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
