"""
Clima completo de Manizales para el cuaderno 17 (fila clima_completo de patrones/datos/variables.csv).

    python calendarios/clima/clima_completo.py      escribe calendarios/clima_completo.csv.gz

Open-Meteo Archive (reanalisis ERA5, el mismo punto que clima_manizales.py: La Nubia) desde 2010, con las
variables que no tenia el clima unificado: horas de sol, nubosidad, punto de rocio, deficit de presion de
vapor, humedad minima y maxima. Encima se calculan las rachas, las transiciones y los extremos.

LA LLUVIA NO SALE DEL ERA5: en La Nubia da ~16.000 mm al ano (10 veces lo real) y correlacion -0,02 con el
pluviometro (medido el 2026-10-05, CLIMA.md). Sale de NASA POWER (PRECTOTCORR), que contra el pluviometro valido
da 0,30 por dia, 0,52 por semana y 0,80 por mes: por eso toda variable de lluvia usa ventanas de 7 dias o mas.
Temperatura, humedad y radiacion del ERA5 concuerdan con el clima unificado (0,5-0,77); horas de sol y nubosidad,
de forma moderada (0,54 y -0,43 contra la radiacion): se usan como anomalias, con cautela.

Es OBSERVACION (reanalisis, ~5 dias de retraso), no pronostico: sirve para explorar y entrenar. Para operar
hace falta el pronostico archivado (Previous Runs API, desde 2024), que va aparte.

Las anomalias se calculan contra la climatologia del mes de 2010-2024: 2025 y 2026 no entran en la referencia.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

LAT, LON = 5.0299, -75.4630
INICIO = "2010-01-01"
REF = ("2010-01-01", "2024-12-31")
SALIDA = Path(__file__).resolve().parents[1] / "clima_completo.csv.gz"
DIARIAS = ["temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
           "sunshine_duration", "daylight_duration", "cloud_cover_mean", "dew_point_2m_mean",
           "relative_humidity_2m_mean", "relative_humidity_2m_max", "relative_humidity_2m_min",
           "vapour_pressure_deficit_max", "shortwave_radiation_sum", "wind_speed_10m_max", "et0_fao_evapotranspiration"]


def bajar(fin):
    r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=300, params={
        "latitude": LAT, "longitude": LON, "start_date": INICIO, "end_date": fin, "daily": ",".join(DIARIAS),
        "timezone": "America/Bogota", "models": "era5"})
    r.raise_for_status(); d = r.json()["daily"]
    t = pd.DataFrame(d).rename(columns={"time": "fecha"}); t["fecha"] = pd.to_datetime(t.fecha)
    t["horas_sol"] = t.pop("sunshine_duration") / 3600; t["horas_luz"] = t.pop("daylight_duration") / 3600
    t = t.set_index("fecha")
    n = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point", timeout=300, params={
        "parameters": "PRECTOTCORR", "community": "AG", "latitude": LAT, "longitude": LON,
        "start": INICIO.replace("-", ""), "end": fin.replace("-", ""), "format": "JSON"}).json()
    p = pd.Series(n["properties"]["parameter"]["PRECTOTCORR"]); p.index = pd.to_datetime(p.index, format="%Y%m%d")
    t["lluvia_nasa"] = p.where(p >= 0).reindex(t.index)
    return t


def racha(cond):
    """Dias seguidos (hasta hoy inclusive) en que se cumple cond."""
    g = (~cond).cumsum()
    return cond.groupby(g).cumsum().astype(float)


def construir(t):
    ref = t.loc[REF[0]:REF[1]]; mes = t.index.month
    def anom(c, log=False):
        x = np.log1p(t[c]) if log else t[c]; r = np.log1p(ref[c]) if log else ref[c]
        clim = r.groupby(r.index.month).agg(["mean", "std"])
        return (x - clim["mean"].reindex(mes).values) / clim["std"].reindex(mes).values
    o = pd.DataFrame(index=t.index)
    # niveles en anomalia estandarizada contra el mes (media movil de 7 dias)
    for c, n, lg in [("temperature_2m_mean", "temp", False), ("temperature_2m_min", "tmin", False), ("temperature_2m_max", "tmax", False),
                     ("lluvia_nasa", "lluvia", True), ("horas_sol", "sol", False), ("cloud_cover_mean", "nubes", False),
                     ("dew_point_2m_mean", "rocio", False), ("relative_humidity_2m_mean", "humedad", False),
                     ("vapour_pressure_deficit_max", "vpd", False), ("shortwave_radiation_sum", "radiacion", False),
                     ("wind_speed_10m_max", "viento", False)]:
        a = anom(c, lg); o[f"{n}_7d"] = a.rolling(7, min_periods=5).mean(); o[f"{n}_28d"] = a.rolling(28, min_periods=20).mean()
        # transicion: ultima semana contra las 3 anteriores
        o[f"{n}_cambio"] = o[f"{n}_7d"] - a.shift(7).rolling(21, min_periods=15).mean()
    # rachas (la lluvia, en ventanas de 7 dias: NASA no acierta el dia exacto)
    llu = anom("lluvia_nasa", True); llu7 = llu.rolling(7, min_periods=5).mean()
    sol_med = ref.horas_sol.groupby(ref.index.month).median()
    o["dias_en_racha_seca"] = racha(llu7 < -0.5)
    o["dias_de_sol"] = racha(t.horas_sol > sol_med.reindex(mes).values)
    lluvia7 = t.lluvia_nasa.rolling(7, min_periods=5).sum(); ref7 = lluvia7.loc[REF[0]:REF[1]]
    p90 = ref7.groupby(ref7.index.month).quantile(.9)
    fuerte = lluvia7 > p90.reindex(mes).values
    ult = pd.Series(np.where(fuerte, np.arange(len(t)), np.nan), index=t.index).ffill()
    o["dias_desde_semana_muy_lluviosa"] = np.arange(len(t)) - ult
    # extremos de la ultima semana
    tmin_p10 = ref.temperature_2m_min.groupby(ref.index.month).quantile(.1)
    o["semana_muy_lluviosa"] = fuerte.astype(float)
    o["extremos_frio_7d"] = (t.temperature_2m_min < tmin_p10.reindex(mes).values).astype(float).rolling(7).sum()
    # transicion seco -> lluvioso (CLAUDE.md: importa la transicion, no el nivel)
    seco14 = llu.shift(7).rolling(14, min_periods=10).mean() < -0.5
    o["seco_a_lluvioso"] = (seco14 & (llu7 > 0.5)).astype(float)
    return t.join(o)


if __name__ == "__main__":
    fin = (pd.Timestamp.today() - pd.Timedelta(days=6)).date().isoformat()
    t = construir(bajar(fin))
    t.to_csv(SALIDA, compression="gzip")
    print(f"{SALIDA.name}: {len(t)} dias, {t.index[0].date()} a {t.index[-1].date()}, {t.shape[1]} columnas")
