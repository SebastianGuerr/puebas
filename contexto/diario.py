"""
El contexto diario: una fila por día, desde 2020-01-01 hasta el último día que cubren los calendarios.

    python -m contexto.diario            escribe salidas/contexto/contexto_diario.csv
    python -m contexto.diario --hasta 2027-12-31

Todo se calcula con las funciones del modelo (notebooks/mecanismos.py y notebooks/indices.py); aquí no se define
ninguna variable. Es un archivo para auditar y para el futuro Power BI: el modelo sigue leyendo sus fuentes.

Columnas:
    fecha
    las de mecanismos.columnas(dias): FUT (fut_m_* y ext_g_m_cli_*), PAS (ext_m_*, ext_g_m_*) sin compuerta, y cada
        compuerta como gate_<nombre> (1 = encendida)
    festivo                  es_festivo de calendarios/calendario_Colombia.csv
    los regímenes de indices.regimenes_diarios (oni, el_nino, ..., crisis_red)

Más allá del último dato real de cada fuente, las funciones del modelo rellenan (fillna(0), ffill): esos valores
son lo que el modelo vería, no datos. Dónde acaba cada fuente lo dice frescura.csv.
"""
import argparse
import sys
import time
import warnings

import pandas as pd

from contexto import DIARIO, RAIZ, escribir_csv

INICIO = "2020-01-01"


def horizonte() -> pd.Timestamp:
    """El último día que cubren a la vez los calendarios que alimentan las columnas conocidas por adelantado: fin del
    último año proyectado de eventos y de fiestas (sus actualizadores proyectan años enteros) y fin de los festivos."""
    fest = pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", usecols=["fecha"], parse_dates=["fecha"]).fecha.max()
    anios = [pd.read_csv(RAIZ / f, usecols=["anio"]).anio.max() for f in
             ("calendarios/eventos_manizales_2020_2026.csv", "calendarios/fiestas_caldas_2020_2026.csv")]
    return min(fest, pd.Timestamp(f"{int(min(anios))}-12-31"))


def calcular(hasta=None) -> pd.DataFrame:
    sys.path.insert(0, str(RAIZ / "notebooks"))
    import indices
    import mecanismos
    # la red se lee hasta el último día completo de triage, no hasta el corte fijo de los cuadernos
    h = pd.read_parquet(RAIZ / "salidas/triage_horario.parquet", columns=["dia"])
    indices.FIN_RED = str((pd.to_datetime(h.dia).max() - pd.Timedelta(days=1)).date())
    dias = pd.date_range(INICIO, pd.Timestamp(hasta) if hasta else horizonte())
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", FutureWarning)
        FUT, PAS, G = mecanismos.columnas(dias)
        R = indices.regimenes_diarios(str(dias.max().date())).reindex(dias)
    cal = pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", usecols=["fecha", "es_festivo"],
                      parse_dates=["fecha"]).set_index("fecha").reindex(dias)
    D = pd.concat([FUT, PAS, G.astype(int).add_prefix("gate_"), cal.es_festivo.rename("festivo"), R], axis=1)
    repetidas = D.columns[D.columns.duplicated()].tolist()
    if repetidas:
        raise RuntimeError(f"columnas repetidas entre mecanismos y regímenes: {repetidas}")
    D.index.name = "fecha"
    return D.reset_index().assign(fecha=lambda d: d.fecha.dt.strftime("%Y-%m-%d"))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m contexto.diario")
    ap.add_argument("--hasta", help="último día (por defecto, el horizonte de los calendarios)")
    a = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    t0 = time.time()
    D = calcular(a.hasta)
    escribir_csv(D, DIARIO)
    print(f"contexto_diario.csv: {len(D)} días, {D.fecha.iloc[0]} a {D.fecha.iloc[-1]}, {D.shape[1] - 1} columnas "
          f"({time.time() - t0:.0f} s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
