"""
El desenlace comun de los barridos (cuadernos 12 y 13): el triage total por semana
epidemiologica, en log, SIN calendario y SIN los cortes de nivel de la red de salud, pero
CON la estacionalidad (el clima y la vigilancia pueden explicarla).

    from desenlace import desenlace_semanal
    y = desenlace_semanal()          # DataFrame indexado por el domingo de cada semana

Por que asi (docs/CONTEXTO.md, 2026-09-30, «Cambio de enfoque»):
- el calendario es el CONTROL: festivos, puentes, Semana Santa, Navidad y fin de ano;
- el nivel lo mueve la red (Nueva EPS): efecto por ano + escalones en 2024-04, 2025-11-15,
  2026-03 y 2026-07 (cuaderno 07, seccion 5);
- la caida de registro de marzo de 2024 va como nula (cuaderno 01);
- 2020-2021 (COVID) queda fuera del ajuste.
Desenlaces secundarios: las series de diagnostico del cuaderno 10, si existe el archivo local
salidas/perfil_dx_diario.parquet (no se versiona).
"""
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CAL = ["es_festivo", "es_puente", "es_semana_santa", "es_temporada_navidad", "es_temporada_fin_anio"]
ESCALONES_RED = ["2024-04-01", "2025-11-15", "2026-03-01", "2026-07-01"]
INICIO, FIN = "2022-03-06", "2026-09-13"
DESCUBRIR = ("2022-03-06", "2024-12-29")
CONFIRMAR = ("2025-01-05", "2026-09-13")


def _semana(s, como="sum"):
    r = getattr(s.resample("W-SAT"), como)()
    r.index = r.index - pd.Timedelta(days=6)
    return r


def _residuo(y, cal_w):
    """log(y) sin calendario, sin nivel del ano y sin escalones de la red. Conserva la estacion."""
    idx = y.index
    Z = pd.concat([cal_w.reindex(idx).fillna(0),
                   pd.get_dummies(pd.Index(idx.year), prefix="a", drop_first=True).set_index(idx).astype(float)], axis=1)
    for i, f in enumerate(ESCALONES_RED):
        Z[f"red_{i}"] = (idx >= f).astype(float)
    Z.insert(0, "c", 1.0)
    ly = np.log(y.clip(lower=1))
    ok = ly.notna()
    b, *_ = np.linalg.lstsq(Z[ok].values, ly[ok].values, rcond=None)
    return (ly - Z.values @ b).where(ok)


def desenlace_semanal():
    dias = pd.date_range("2020-01-01", "2026-09-19")
    t = pd.read_parquet(RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
    tri = t.set_index("dia")["triages"].reindex(dias).astype(float)
    tri["2024-03-19":"2024-03-21"] = np.nan                     # caida del registro
    cal = (pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
             .reindex(dias)[CAL].apply(pd.to_numeric, errors="coerce").fillna(0))
    tw = _semana(tri)
    completas = _semana(tri.notna().astype(int)) == 7
    tw = tw.where(completas).loc[INICIO:FIN]
    cal_w = _semana(cal).loc[INICIO:FIN]
    out = pd.DataFrame({"triage": tw, "y": _residuo(tw, cal_w)})
    dx = RAIZ / "salidas/perfil_dx_diario.parquet"
    if dx.exists():
        d = pd.read_parquet(dx)
        d["dia"] = pd.to_datetime(d["dia"])
        for cap, nom in [("X Respiratorio", "y_respiratorio"), ("I Infecciosas y parasitarias", "y_infecciosas"),
                         ("XIX Traumatismos y envenenamientos", "y_trauma")]:
            s = d[d.capitulo.eq(cap)].set_index("dia")["n"].reindex(dias).fillna(0)
            s[tri.isna()] = np.nan
            sw = _semana(s).where(completas).loc[INICIO:FIN]
            out[nom] = _residuo(sw, cal_w)
    out["periodo"] = np.where(out.index <= DESCUBRIR[1], "descubrir", "confirmar")
    return out


if __name__ == "__main__":
    y = desenlace_semanal()
    print(y.groupby("periodo").agg(semanas=("y", "count"), sd=("y", "std")).round(3))
    print(y.drop(columns="periodo").corr().round(2))
