# calendarios\clima_ideam.csv
# fecha,precipitacion_mm,completitud_precip,temp_media,temp_min,temp_max,n_registros_temp,estacion_clima,estacion_km
# 2020-01-01,11.1,1.0,14.66,12.8,18.2,24.0,TESORITO FINCA,7.7

# calendarios\clima_manizales_2020_hoy.csv
# fecha,om_temperature_2m_mean,om_temperature_2m_max,om_temperature_2m_min,om_relative_humidity_2m_mean,om_wind_speed_10m_max,om_shortwave_radiation_sum,om_et0_fao_evapotranspiration,om_precipitation_sum,om_precipitation_hours,om_elev_celda,om_temperature_2m_mean_corr,om_temperature_2m_max_corr,om_temperature_2m_min_corr,np_T2M,np_T2M_MAX,np_T2M_MIN,np_T2MDEW,np_RH2M,np_PRECTOTCORR,np_WS2M,np_ALLSKY_SFC_SW_DWN,iem_tmax_c,iem_tmin_c,iem_hr_min,iem_hr_max,iem_viento_ms,iem_dewp_max_c,temp_media_c,temp_max_c,temp_min_c,precip_mm,humedad_rel,viento_ms,radiacion_mj_m2
# 2020-01-01,16.6,19.5,14.3,93.0,,,,39.5,20.0,2100.0,16.840500000000002,19.7405,14.540500000000002,16.62,20.56,14.04,14.89,90.62,4.24,0.24,15.3,20.0,14.000000000000002,77.748055,100.0,1.5130705519216,16.0,16.840500000000002,20.0,14.000000000000002,4.24,93.0,1.5130705519216,15.3

# calendarios\raw_iem_skmz.csv
# station,date,max_tmpf,min_tmpf,precip,max_gust,snow,snowd,min_rh,max_rh,max_dwpf,min_dwpf,min_feel,avg_feel,max_feel,max_drct,precip_est,tmpf_est,max_gust_localts,temp_hour,avg_sknt,vector_avg_drct,min_rstage,max_rstage,id,name,fecha,iem_tmax_c,iem_tmin_c,iem_hr_min,iem_hr_max,iem_viento_ms,iem_dewp_max_c
# SKMZ,2020-01-01,68.0,57.2,,,,,77.748055,100.0,60.8,57.2,57.2,61.54117584228516,68.0,60.0,False,False,,,2.9411764,303.24744,,,SKMZ,Manizales,2020-01-01,20.0,14.000000000000002,77.748055,100.0,1.5130705519216,16.0

# calendarios\raw_nasapower.csv
# fecha,np_T2M,np_T2M_MAX,np_T2M_MIN,np_T2MDEW,np_RH2M,np_PRECTOTCORR,np_WS2M,np_ALLSKY_SFC_SW_DWN
# 2020-01-01,16.62,20.56,14.04,14.89,90.62,4.24,0.24,15.3

# calendarios\raw_openmeteo.csv
# fecha,om_temperature_2m_mean,om_temperature_2m_max,om_temperature_2m_min,om_relative_humidity_2m_mean,om_wind_speed_10m_max,om_shortwave_radiation_sum,om_et0_fao_evapotranspiration,om_precipitation_sum,om_precipitation_hours,om_elev_celda,om_temperature_2m_mean_corr,om_temperature_2m_max_corr,om_temperature_2m_min_corr
# 2020-01-01,16.6,19.5,14.3,93.0,,,,39.5,20.0,2100.0,16.840500000000002,19.7405,14.540500000000002

import pandas as pd
import numpy as np
from pathlib import Path


# ============================================================
# CONFIGURACIÓN
# ============================================================

ARCHIVO_IDEAM = "calendarios/clima_ideam.csv"
ARCHIVO_OPENMETEO = "calendarios/raw_openmeteo.csv"
ARCHIVO_NASA = "calendarios/raw_nasapower.csv"
ARCHIVO_IEM = "calendarios/raw_iem_skmz.csv"

SALIDA = "calendarios/clima_unificado.csv"


# ============================================================
# UTILIDADES
# ============================================================

def cargar_csv(path):
    if not Path(path).exists():
        print(f"[WARN] No existe: {path}")
        return pd.DataFrame()

    df = pd.read_csv(path)

    if "fecha" in df.columns:
        df["fecha"] = pd.to_datetime(df["fecha"])

    return df


def mediana_columnas(df, columnas):
    existentes = [c for c in columnas if c in df.columns]

    if not existentes:
        return np.nan

    return df[existentes].median(axis=1, skipna=True)


def std_columnas(df, columnas):
    existentes = [c for c in columnas if c in df.columns]

    if not existentes:
        return np.nan

    return df[existentes].std(axis=1, skipna=True)


# ============================================================
# CARGA DE DATOS
# ============================================================

print("Cargando archivos...")

ideam = cargar_csv(ARCHIVO_IDEAM)
openmeteo = cargar_csv(ARCHIVO_OPENMETEO)
nasa = cargar_csv(ARCHIVO_NASA)
iem = cargar_csv(ARCHIVO_IEM)


# ============================================================
# REDUCIR COLUMNAS DUPLICADAS DEL IEM
# ============================================================

columnas_iem = [
    "fecha",
    "iem_tmax_c",
    "iem_tmin_c",
    "iem_hr_min",
    "iem_hr_max",
    "iem_viento_ms",
    "iem_dewp_max_c"
]

iem = iem[[c for c in columnas_iem if c in iem.columns]]


# ============================================================
# MERGE
# ============================================================

clima = ideam.copy()

for fuente in [openmeteo, nasa, iem]:
    if not fuente.empty:
        clima = clima.merge(
            fuente,
            on="fecha",
            how="outer"
        )

print(f"Filas unificadas: {len(clima):,}")


# ============================================================
# CONSENSO DE TEMPERATURA MEDIA
# ============================================================

temperaturas_media = [
    "temp_media",
    "om_temperature_2m_mean_corr",
    "om_temperature_2m_mean",
    "np_T2M"
]

clima["temp_media_consenso"] = mediana_columnas(
    clima,
    temperaturas_media
)

clima["temp_media_dispersion"] = std_columnas(
    clima,
    temperaturas_media
)


# ============================================================
# CONSENSO DE TEMPERATURA MÁXIMA
# ============================================================

temperaturas_max = [
    "temp_max",
    "om_temperature_2m_max_corr",
    "om_temperature_2m_max",
    "np_T2M_MAX",
    "iem_tmax_c"
]

clima["temp_max_consenso"] = mediana_columnas(
    clima,
    temperaturas_max
)

clima["temp_max_dispersion"] = std_columnas(
    clima,
    temperaturas_max
)


# ============================================================
# CONSENSO DE TEMPERATURA MÍNIMA
# ============================================================

temperaturas_min = [
    "temp_min",
    "om_temperature_2m_min_corr",
    "om_temperature_2m_min",
    "np_T2M_MIN",
    "iem_tmin_c"
]

clima["temp_min_consenso"] = mediana_columnas(
    clima,
    temperaturas_min
)

clima["temp_min_dispersion"] = std_columnas(
    clima,
    temperaturas_min
)


# ============================================================
# CONSENSO DE PRECIPITACIÓN
# ============================================================

precipitaciones = [
    "precipitacion_mm",
    "om_precipitation_sum",
    "np_PRECTOTCORR"
]

clima["precip_consenso_mm"] = mediana_columnas(
    clima,
    precipitaciones
)

clima["precip_dispersion"] = std_columnas(
    clima,
    precipitaciones
)


# ============================================================
# CONSENSO DE HUMEDAD
# ============================================================

if "iem_hr_min" in clima.columns and "iem_hr_max" in clima.columns:
    clima["iem_hr_media"] = (
        clima["iem_hr_min"] +
        clima["iem_hr_max"]
    ) / 2

humedades = [
    "om_relative_humidity_2m_mean",
    "np_RH2M",
    "iem_hr_media"
]

clima["humedad_consenso"] = mediana_columnas(
    clima,
    humedades
)

clima["humedad_dispersion"] = std_columnas(
    clima,
    humedades
)


# ============================================================
# CONSENSO DE VIENTO
# ============================================================

vientos = [
    "iem_viento_ms",
    "np_WS2M"
]

clima["viento_consenso_ms"] = mediana_columnas(
    clima,
    vientos
)

clima["viento_dispersion"] = std_columnas(
    clima,
    vientos
)


# ============================================================
# CONSENSO DE RADIACIÓN
# ============================================================

radiacion = [
    "om_shortwave_radiation_sum",
    "np_ALLSKY_SFC_SW_DWN"
]

clima["radiacion_consenso"] = mediana_columnas(
    clima,
    radiacion
)


# ============================================================
# CANTIDAD DE FUENTES DISPONIBLES
# ============================================================

fuentes_base = [
    "temp_media",
    "om_temperature_2m_mean",
    "np_T2M"
]

clima["n_fuentes_temp"] = clima[
    [c for c in fuentes_base if c in clima.columns]
].notna().sum(axis=1)


# ============================================================
# CLASIFICACIÓN SIMPLE DEL DÍA
# ============================================================

clima["llovio"] = (
    clima["precip_consenso_mm"]
    .fillna(0)
    .gt(0)
    .astype(int)
)

clima["lluvia_fuerte"] = (
    clima["precip_consenso_mm"]
    .fillna(0)
    .ge(20)
    .astype(int)
)

clima["dia_calido"] = (
    clima["temp_media_consenso"]
    .fillna(-999)
    .ge(18)
    .astype(int)
)

clima["dia_frio"] = (
    clima["temp_media_consenso"]
    .fillna(999)
    .le(14)
    .astype(int)
)


# ============================================================
# ACUMULADOS
# ============================================================

clima = clima.sort_values("fecha")

clima["precip_7d"] = (
    clima["precip_consenso_mm"]
    .rolling(7, min_periods=1)
    .sum()
)

clima["precip_30d"] = (
    clima["precip_consenso_mm"]
    .rolling(30, min_periods=1)
    .sum()
)

clima["temp_media_7d"] = (
    clima["temp_media_consenso"]
    .rolling(7, min_periods=1)
    .mean()
)

clima["humedad_7d"] = (
    clima["humedad_consenso"]
    .rolling(7, min_periods=1)
    .mean()
)


# ============================================================
# EXPORTAR
# ============================================================

clima.to_csv(
    SALIDA,
    index=False,
    encoding="utf-8-sig"
)

print()
print(f"Archivo generado:")
print(SALIDA)
print()
print(f"Registros: {len(clima):,}")