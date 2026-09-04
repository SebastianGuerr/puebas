#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extrae clima histórico de Manizales (Caldas) del 2020-01-01 a la fecha actual
y lo guarda en CSV.

Fuentes (todas sin API key):
  1. Open-Meteo Archive  -> ERA5-Land (temp/HR/viento/radiación) + ERA5 (precipitación)
  2. NASA POWER          -> diario agroclimático + radiación
  3. Iowa Mesonet (IEM)  -> METAR observado del Aeropuerto La Nubia (SKMZ)
  4. IDEAM / datos.gov.co (opcional, IDEAM_ON=True) -> estaciones PLANALTO y CENICAFE

Salidas:
  raw_openmeteo.csv, raw_nasapower.csv, raw_iem_skmz.csv, raw_ideam.csv
  clima_manizales_2020_hoy.csv   <- consolidado diario

pip install requests pandas numpy
"""

import io
import time
import logging
from datetime import date

import numpy as np
import pandas as pd
import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("clima")

# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
INICIO = "2020-01-01"
FIN = date.today().isoformat()

LAT, LON = 5.0299, -75.4630          # Aeropuerto La Nubia (SKMZ)
ELEV_OBJETIVO = 2063.0               # m sobre el nivel del mar

IEM_NETWORK, IEM_STATION = "CO__ASOS", "SKMZ"

IDEAM_ON = False                     # True = intenta bajar IDEAM (lento e incompleto)
IDEAM_APP_TOKEN = None               # token gratis de dev.socrata.com evita throttling
IDEAM_ESTACIONES = ["0026155503", "0026155502"]   # PLANALTO - AUT, CENICAFE - AUT
IDEAM_DS = {"temperatura": "sbwg-7ju4", "precipitacion": "s54a-sgyg"}

REINTENTOS, ESPERA, TIMEOUT = 4, 3.0, 120


def get(url, params=None, headers=None, timeout=TIMEOUT):
    err = None
    for i in range(REINTENTOS):
        try:
            r = requests.get(url, params=params, headers=headers, timeout=timeout)
            r.raise_for_status()
            return r
        except Exception as e:
            err = e
            t = ESPERA * (2 ** i)
            log.warning(f"fallo {i+1}/{REINTENTOS} {url} -> {e}; reintento en {t:.0f}s")
            time.sleep(t)
    raise RuntimeError(f"agotados reintentos: {url} :: {err}")


# --------------------------------------------------------------------------
# 1. OPEN-METEO
#    OJO: era5_land NO devuelve precipitation_sum (llega null) -> la precipitación
#    se pide aparte al modelo era5.
# --------------------------------------------------------------------------
def bajar_openmeteo():
    url = "https://archive-api.open-meteo.com/v1/archive"
    base = {"latitude": LAT, "longitude": LON, "start_date": INICIO,
            "end_date": FIN, "timezone": "America/Bogota"}

    p1 = dict(base, models="era5_land", daily=",".join([
        "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
        "relative_humidity_2m_mean", "wind_speed_10m_max",
        "shortwave_radiation_sum", "et0_fao_evapotranspiration"]))
    j1 = get(url, params=p1).json()
    df = pd.DataFrame(j1["daily"]).rename(columns={"time": "fecha"})
    elev_celda = j1.get("elevation", np.nan)

    p2 = dict(base, models="era5", daily="precipitation_sum,precipitation_hours")
    j2 = get(url, params=p2).json()
    dp = pd.DataFrame(j2["daily"]).rename(columns={"time": "fecha"})
    df = df.merge(dp, on="fecha", how="left")

    df = df.add_prefix("om_").rename(columns={"om_fecha": "fecha"})
    df["fecha"] = pd.to_datetime(df["fecha"]).dt.date
    df["om_elev_celda"] = elev_celda

    # corrección por altitud (lapse rate 6.5 °C/km)
    delta = (elev_celda - ELEV_OBJETIVO) / 1000.0 * 6.5
    for c in ["om_temperature_2m_mean", "om_temperature_2m_max", "om_temperature_2m_min"]:
        df[c + "_corr"] = df[c] + delta

    df.to_csv("raw_openmeteo.csv", index=False)
    log.info(f"Open-Meteo: {len(df)} días (elev celda {elev_celda} m, ajuste {delta:+.2f} °C)")
    return df


# --------------------------------------------------------------------------
# 2. NASA POWER
# --------------------------------------------------------------------------
def bajar_nasapower():
    url = "https://power.larc.nasa.gov/api/temporal/daily/point"
    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,T2MDEW,RH2M,PRECTOTCORR,WS2M,ALLSKY_SFC_SW_DWN",
        "community": "AG", "latitude": LAT, "longitude": LON,
        "start": INICIO.replace("-", ""), "end": FIN.replace("-", ""), "format": "JSON",
    }
    j = get(url, params=params).json()
    df = pd.DataFrame(j["properties"]["parameter"])
    df.index = pd.to_datetime(df.index, format="%Y%m%d").date
    df.index.name = "fecha"
    df = df.reset_index().replace(-999.0, np.nan)
    df = df.rename(columns={c: "np_" + c for c in df.columns if c != "fecha"})
    df.to_csv("raw_nasapower.csv", index=False)
    log.info(f"NASA POWER: {len(df)} días")
    return df


# --------------------------------------------------------------------------
# 3. IOWA MESONET - METAR SKMZ (La Nubia). Temperaturas en °F, viento en nudos.
#    La precipitación del METAR viene vacía casi siempre: no se usa.
# --------------------------------------------------------------------------
def bajar_iem():
    url = "https://mesonet.agron.iastate.edu/api/1/daily.txt"
    partes, hoy = [], date.today()
    y, m = 2020, 1
    while (y, m) <= (hoy.year, hoy.month):
        try:
            r = get(url, params={"network": IEM_NETWORK, "station": IEM_STATION,
                                 "year": y, "month": m}, timeout=60)
            if r.text.strip():
                partes.append(pd.read_csv(io.StringIO(r.text)))
        except Exception as e:
            log.warning(f"IEM {y}-{m:02d}: {e}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
        time.sleep(0.25)

    if not partes:
        return pd.DataFrame(columns=["fecha"])

    df = pd.concat(partes, ignore_index=True)
    df["fecha"] = pd.to_datetime(df["date"], errors="coerce").dt.date
    df = df.dropna(subset=["fecha"]).drop_duplicates("fecha")
    df["iem_tmax_c"] = (pd.to_numeric(df["max_tmpf"], errors="coerce") - 32) * 5 / 9
    df["iem_tmin_c"] = (pd.to_numeric(df["min_tmpf"], errors="coerce") - 32) * 5 / 9
    # descarta valores no plausibles para Manizales (2.100 m): outliers del METAR
    df.loc[~df["iem_tmax_c"].between(8, 35), "iem_tmax_c"] = np.nan
    df.loc[~df["iem_tmin_c"].between(2, 25), "iem_tmin_c"] = np.nan
    df["iem_hr_min"] = pd.to_numeric(df["min_rh"], errors="coerce")
    df["iem_hr_max"] = pd.to_numeric(df["max_rh"], errors="coerce")
    df["iem_viento_ms"] = pd.to_numeric(df["avg_sknt"], errors="coerce") * 0.514444
    df["iem_dewp_max_c"] = (pd.to_numeric(df["max_dwpf"], errors="coerce") - 32) * 5 / 9
    df.to_csv("raw_iem_skmz.csv", index=False)
    cols = ["fecha", "iem_tmax_c", "iem_tmin_c", "iem_hr_min", "iem_hr_max",
            "iem_viento_ms", "iem_dewp_max_c"]
    log.info(f"IEM SKMZ: {len(df)} días")
    return df[cols]


# --------------------------------------------------------------------------
# 4. IDEAM (opcional). Cobertura incompleta: hay 2020, 2022-2023; faltan 2021 y 2024+.
# --------------------------------------------------------------------------
def bajar_ideam():
    headers = {"X-App-Token": IDEAM_APP_TOKEN} if IDEAM_APP_TOKEN else {}
    salida = []
    for var, ds in IDEAM_DS.items():
        for est in IDEAM_ESTACIONES:
            url = f"https://www.datos.gov.co/resource/{ds}.json"
            params = {
                "$select": "codigoestacion,nombreestacion,fechaobservacion,valorobservado",
                "$where": (f"codigoestacion='{est}' AND fechaobservacion "
                           f"between '{INICIO}T00:00:00' and '{FIN}T23:59:59'"),
                "$order": "fechaobservacion", "$limit": 400000,
            }
            try:
                d = get(url, params=params, headers=headers, timeout=300).json()
            except Exception as e:
                log.warning(f"IDEAM {var} {est}: {e}")
                continue
            if not d:
                continue
            t = pd.DataFrame(d)
            t["variable"] = var
            t["fecha"] = pd.to_datetime(t["fechaobservacion"]).dt.date
            t["valorobservado"] = pd.to_numeric(t["valorobservado"], errors="coerce")
            salida.append(t)
            log.info(f"IDEAM {var} {est}: {len(t)} obs")

    if not salida:
        return pd.DataFrame(columns=["fecha"])

    crudo = pd.concat(salida, ignore_index=True)
    crudo.to_csv("raw_ideam.csv", index=False)

    tmp = (crudo[crudo.variable == "temperatura"]
           .groupby("fecha")["valorobservado"].mean().rename("ideam_tmedia"))
    pre = (crudo[crudo.variable == "precipitacion"]
           .groupby("fecha")["valorobservado"].sum().rename("ideam_precip_mm"))
    return pd.concat([tmp, pre], axis=1).reset_index()


# --------------------------------------------------------------------------
# CONSOLIDADO
# --------------------------------------------------------------------------
def main():
    cal = pd.DataFrame({"fecha": pd.date_range(INICIO, FIN, freq="D").date})

    cal = cal.merge(bajar_openmeteo(), on="fecha", how="left")
    cal = cal.merge(bajar_nasapower(), on="fecha", how="left")

    iem = bajar_iem()
    if not iem.empty:
        cal = cal.merge(iem, on="fecha", how="left")

    if IDEAM_ON:
        ide = bajar_ideam()
        if not ide.empty:
            cal = cal.merge(ide, on="fecha", how="left")

    def coalesce(*cols):
        s = pd.Series(np.nan, index=cal.index)
        for c in cols:
            if c in cal.columns:
                s = s.fillna(pd.to_numeric(cal[c], errors="coerce"))
        return s

    cal["temp_media_c"] = coalesce("ideam_tmedia", "om_temperature_2m_mean_corr", "np_T2M")
    cal["temp_max_c"] = coalesce("iem_tmax_c", "om_temperature_2m_max_corr", "np_T2M_MAX")
    cal["temp_min_c"] = coalesce("iem_tmin_c", "om_temperature_2m_min_corr", "np_T2M_MIN")
    # Precipitación: NASA POWER va primero. ERA5/IFS de Open-Meteo sobreestima la
    # lluvia ~4-8x en la vertiente andina (da 7.000-17.000 mm/año vs ~2.000 mm reales),
    # así que queda solo como columna de referencia, no como fuente del consolidado.
    cal["precip_mm"] = coalesce("ideam_precip_mm", "np_PRECTOTCORR")
    cal["humedad_rel"] = coalesce("om_relative_humidity_2m_mean", "np_RH2M")
    cal["viento_ms"] = coalesce("iem_viento_ms", "np_WS2M")
    cal["radiacion_mj_m2"] = coalesce("om_shortwave_radiation_sum", "np_ALLSKY_SFC_SW_DWN")

    cal = cal.sort_values("fecha").reset_index(drop=True)
    cal.to_csv("clima_manizales_2020_hoy.csv", index=False)
    log.info(f"CSV final: {len(cal)} días, {cal.fecha.min()} -> {cal.fecha.max()}")
    return cal


if __name__ == "__main__":
    df = main()
    print(df[["fecha", "temp_media_c", "temp_max_c", "temp_min_c",
              "precip_mm", "humedad_rel", "viento_ms", "radiacion_mj_m2"]].tail(10))
