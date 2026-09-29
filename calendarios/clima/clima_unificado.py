"""
Une las cuatro fuentes de clima de Manizales en UNA fila por dia.

    python calendarios/clima/clima_unificado.py

Entra:  calendarios/clima/clima_ideam.csv, raw_openmeteo.csv, raw_nasapower.csv,
        raw_iem_skmz.csv
Sale:   calendarios/clima_unificado.csv.gz, con las mismas columnas de siempre
        (patrones/calendario.py las lee por nombre) mas las de trazabilidad.

EL METODO, EN TRES PASOS
    1. Cada variable tiene UNA fuente de referencia: la que mejor mide esa
       variable en Manizales. Temperatura y lluvia, las estaciones de la ciudad;
       humedad, NASA POWER (la unica con media diaria real y serie completa).
    2. Cada otra fuente se lleva a la escala de la referencia, mes calendario
       por mes calendario: sumando la diferencia media (temperatura, humedad,
       viento) o multiplicando por el cociente (lluvia). Es el metodo de
       escalado lineal, el estandar para corregir reanalisis contra estacion.
    3. El consenso es la mediana de las fuentes ya corregidas.

    El paso 2 es el que importa. Sin el, cada vez que una fuente falta un dia la
    mediana salta de nivel aunque el clima no haya cambiado -- y este proyecto
    busca justamente cambios bruscos de clima.

Por que se hizo asi y con que evidencia: calendarios/docs/CLIMA.md.
"""

from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
ARCHIVO_IDEAM = AQUI / "clima_ideam.csv"
ARCHIVO_OPENMETEO = AQUI / "raw_openmeteo.csv"
ARCHIVO_NASA = AQUI / "raw_nasapower.csv"
ARCHIVO_IEM = AQUI / "raw_iem_skmz.csv"
SALIDA = AQUI.parent / "clima_unificado.csv.gz"   # comprimido desde el 2026-09-24

# Planalto queda fuera: esta a 12,8 km y unos 800 m mas abajo. Su maxima sale
# 7,4 C por encima de La Nubia en los mismos dias. No es Manizales.
ESTACIONES_VALIDAS = {"AEROPUERTO LA NUBIA", "TESORITO FINCA"}

# Un dia de pluviometro con menos del 80% de sus registros subestima la lluvia
# de ese dia: se descarta en vez de contarse como poca lluvia.
COMPLETITUD_MINIMA = 0.8

# Dias de solape minimos en un mes calendario para estimar su correccion. Por
# debajo se usa la correccion de todos los meses juntos.
SOLAPE_MINIMO = 30

# Falla del pluviometro (2026-09-29): desde oct-2025 La Nubia reporta 0 mm dias
# enteros mientras NASA marca 100-240 mm/mes. No falta el dato: es falso. En los 34
# meses sanos la razon pluviometro/NASA va de 0,27 a 1,42 (mediana 0,54); en los
# fallidos, < 0,04. Se marca falla cuando, en 31 dias centrados, el pluviometro
# suma menos del 10% de NASA y NASA supera 60 mm. Ventana de un mes y no un dia:
# un dia seco aislado es real. Ver calendarios/docs/CLIMA.md.
FALLA_VENTANA_DIAS = 31
FALLA_RAZON_MAXIMA = 0.10
FALLA_NASA_MINIMA_MM = 60.0

LLUVIA_DIA_MM = 1.0       # 'dia de lluvia' de la OMM
# 'lluvia_fuerte' es el 5% mas lluvioso de cada mes. Con 20 mm fijos era cierta
# el 0,7% de los dias: 17 dias en seis anos, una bandera que no discrimina.


# ==========================================================
# CARGA
# ==========================================================

def cargar(ruta):
    """Lee un CSV de fuente. Si falta, se detiene: nunca sigue con una tabla vacia."""
    if not ruta.exists():
        raise FileNotFoundError(
            f"No existe {ruta}. Se genera con calendarios/clima/clima_manizales.py.")
    tabla = pd.read_csv(ruta)
    tabla["fecha"] = pd.to_datetime(tabla["fecha"])
    duplicadas = tabla["fecha"].duplicated().sum()
    if duplicadas:
        raise ValueError(f"{ruta.name} trae {duplicadas} fechas repetidas")
    return tabla


def preparar_ideam(ideam):
    """Solo las estaciones de la ciudad, y la lluvia solo en dias completos."""
    ideam = ideam.copy()
    fuera = ~ideam["estacion_clima"].isin(ESTACIONES_VALIDAS)
    columnas = ["temp_media", "temp_min", "temp_max", "precipitacion_mm"]
    ideam.loc[fuera, columnas] = np.nan
    incompleto = ideam["completitud_precip"] < COMPLETITUD_MINIMA
    ideam.loc[incompleto, "precipitacion_mm"] = np.nan
    ideam.loc[fuera, "estacion_clima"] = np.nan
    return ideam


def pluviometro_fallido(clima):
    """Dias en que el pluviometro reporta (casi) cero mientras NASA registra lluvia."""
    ambos = clima["precipitacion_mm"].notna() & clima["np_PRECTOTCORR"].notna()
    ventana = dict(window=FALLA_VENTANA_DIAS, center=True, min_periods=15)
    suma_pluv = clima["precipitacion_mm"].where(ambos).rolling(**ventana).sum()
    suma_nasa = clima["np_PRECTOTCORR"].where(ambos).rolling(**ventana).sum()
    fallo = ambos & (suma_nasa >= FALLA_NASA_MINIMA_MM) & (suma_pluv < FALLA_RAZON_MAXIMA * suma_nasa)
    return fallo.fillna(False)


# ==========================================================
# CORRECCION Y CONSENSO
# ==========================================================

def corregir(tabla, fuente, referencia, modo):
    """
    Lleva 'fuente' a la escala de 'referencia', mes calendario por mes.

    modo 'suma'      fuente + media(referencia - fuente)
    modo 'producto'  fuente * suma(referencia) / suma(fuente)
    """
    solape = tabla[[fuente, referencia]].dropna()
    mes_solape = solape.index.month

    def factor(parte):
        if modo == "suma":
            return (parte[referencia] - parte[fuente]).mean()
        total = parte[fuente].sum()
        return parte[referencia].sum() / total if total > 0 else 1.0

    general = factor(solape)
    por_mes = {}
    for mes in range(1, 13):
        parte = solape[mes_solape == mes]
        por_mes[mes] = factor(parte) if len(parte) >= SOLAPE_MINIMO else general

    ajuste = tabla.index.month.map(por_mes).to_numpy(dtype=float)
    if modo == "suma":
        return tabla[fuente] + ajuste
    return tabla[fuente] * ajuste


def consenso(tabla, nombre, referencia, otras, modo):
    """Mediana de la referencia y de las otras fuentes ya corregidas."""
    columnas = [tabla[referencia].rename(referencia)]
    for fuente in otras:
        columnas.append(corregir(tabla, fuente, referencia, modo).rename(fuente))
    juntas = pd.concat(columnas, axis=1)
    tabla[nombre] = juntas.median(axis=1, skipna=True)
    tabla[nombre.replace("_consenso", "") + "_dispersion"] = juntas.std(axis=1, skipna=True)
    tabla["n_fuentes_" + nombre.replace("_consenso", "").replace("_mm", "")] = (
        juntas.notna().sum(axis=1))


# ==========================================================
# UNION
# ==========================================================

def unir():
    ideam = preparar_ideam(cargar(ARCHIVO_IDEAM))
    openmeteo = cargar(ARCHIVO_OPENMETEO)
    nasa = cargar(ARCHIVO_NASA)
    iem = cargar(ARCHIVO_IEM)[["fecha", "iem_tmax_c", "iem_tmin_c", "iem_hr_min",
                               "iem_hr_max", "iem_viento_ms", "iem_dewp_max_c"]]

    inicio = min(t["fecha"].min() for t in (ideam, openmeteo, nasa, iem))
    fin = max(t["fecha"].max() for t in (ideam, openmeteo, nasa, iem))
    clima = pd.DataFrame({"fecha": pd.date_range(inicio, fin, freq="D")})
    for fuente in (ideam, openmeteo, nasa, iem):
        clima = clima.merge(fuente, on="fecha", how="left")
    clima = clima.set_index("fecha")

    # La falla se quita ANTES de todo: si no, tambien contamina los factores con que
    # se escala NASA mes a mes (corregir() los calcula sobre el solape).
    clima["pluviometro_fallido"] = pluviometro_fallido(clima)
    clima.loc[clima["pluviometro_fallido"], "precipitacion_mm"] = np.nan

    # Referencias en tierra. La estacion IDEAM de La Nubia y el METAR del mismo
    # aeropuerto coinciden (r = 0,81, sesgo -0,29 C); donde falta una, la otra.
    clima["iem_tmedia_c"] = (clima["iem_tmax_c"] + clima["iem_tmin_c"]) / 2
    clima["iem_hr_media"] = (clima["iem_hr_min"] + clima["iem_hr_max"]) / 2
    clima["ref_tmax"] = clima["iem_tmax_c"].fillna(clima["temp_max"])
    clima["ref_tmin"] = clima["iem_tmin_c"].fillna(clima["temp_min"])
    # La media NO usa (max+min)/2 como referencia: en montana la curva diaria es
    # asimetrica y ese punto medio sale 1,09 C por encima de la media real de
    # IDEAM (22 lecturas por dia). Entra como una fuente mas, corregida.

    # Open-Meteo vota una sola vez: la version corregida por altura. Su
    # precipitacion NO entra: es de ERA5 a ~28 km, da 16.555 mm/ano y no
    # correlaciona con la estacion (r = -0,03).
    consenso(clima, "temp_max_consenso", "ref_tmax",
             ["om_temperature_2m_max_corr", "np_T2M_MAX"], "suma")
    consenso(clima, "temp_min_consenso", "ref_tmin",
             ["om_temperature_2m_min_corr", "np_T2M_MIN"], "suma")
    consenso(clima, "temp_media_consenso", "temp_media",
             ["iem_tmedia_c", "om_temperature_2m_mean_corr", "np_T2M"], "suma")
    # Lluvia: la referencia es el pluviometro aunque NASA tenga la serie completa.
    # NASA llueve >= 1 mm el 73% de los dias y los pluviometros el 34-39%: es
    # llovizna de producto satelital. Con NASA de referencia casi no habria dias
    # secos, y el proyecto busca justamente el paso de seco a lluvioso.
    consenso(clima, "precip_consenso_mm", "precipitacion_mm",
             ["np_PRECTOTCORR"], "producto")
    clima["precip_con_estacion"] = clima["precipitacion_mm"].notna()
    # Humedad: (min+max)/2 del METAR subestima la media real (la noche pasa horas
    # cerca del 100%). La referencia es NASA, que si trae media diaria.
    consenso(clima, "humedad_consenso", "np_RH2M",
             ["om_relative_humidity_2m_mean", "iem_hr_media"], "suma")
    consenso(clima, "viento_consenso_ms", "iem_viento_ms", ["np_WS2M"], "suma")

    # Radiacion: sin estacion en tierra y con las dos fuentes siempre presentes,
    # no hay escalon que corregir.
    clima["radiacion_consenso"] = clima[
        ["om_shortwave_radiation_sum", "np_ALLSKY_SFC_SW_DWN"]].median(axis=1)

    # Banderas. Frio y calido son relativos al propio mes: un umbral fijo en una
    # ciudad sin estaciones termicas es una constante.
    mes = clima.index.month
    tmedia = clima["temp_media_consenso"]
    p10 = tmedia.groupby(mes).transform(lambda s: s.quantile(0.10))
    p90 = tmedia.groupby(mes).transform(lambda s: s.quantile(0.90))
    lluvia = clima["precip_consenso_mm"]
    clima["llovio"] = lluvia.ge(LLUVIA_DIA_MM).astype("Int64").where(lluvia.notna())
    p95 = lluvia.groupby(mes).transform(lambda s: s.quantile(0.95))
    clima["lluvia_fuerte"] = lluvia.ge(p95).astype("Int64").where(lluvia.notna())
    clima["dia_frio"] = tmedia.le(p10).astype("Int64").where(tmedia.notna())
    clima["dia_calido"] = tmedia.ge(p90).astype("Int64").where(tmedia.notna())

    # Acumulados con la ventana completa: un hueco da nulo, no una suma corta.
    clima["precip_7d"] = lluvia.rolling(7, min_periods=7).sum()
    clima["precip_30d"] = lluvia.rolling(30, min_periods=30).sum()
    clima["temp_media_7d"] = tmedia.rolling(7, min_periods=7).mean()
    clima["humedad_7d"] = clima["humedad_consenso"].rolling(7, min_periods=7).mean()

    return clima.reset_index()


# ==========================================================
# AUDITORIA -- lo que hay que mirar antes de confiar en el archivo
# ==========================================================

MESES = ["Ene", "Feb", "Mar", "Abr", "May", "Jun",
         "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]


def auditar(clima):
    c = clima.set_index("fecha")
    print(f"\n{len(c):,} dias, {c.index.min():%Y-%m-%d} a {c.index.max():%Y-%m-%d}")

    print("\nVARIABLE               media     sd    fuentes/dia (min-max)")
    for nombre, n in [("temp_media_consenso", "n_fuentes_temp_media"),
                      ("temp_max_consenso", "n_fuentes_temp_max"),
                      ("temp_min_consenso", "n_fuentes_temp_min"),
                      ("precip_consenso_mm", "n_fuentes_precip"),
                      ("humedad_consenso", "n_fuentes_humedad")]:
        s = c[nombre]
        print(f"  {nombre:<20}{s.mean():7.2f}{s.std():7.2f}"
              f"    {int(c[n].min())}-{int(c[n].max())}")

    lluvia = c["precip_consenso_mm"]
    print(f"\nLluvia anual: {lluvia.mean() * 365:,.0f} mm")
    ciclo = lluvia.groupby(lluvia.index.month).mean()
    print("Ciclo anual (mm/dia):")
    for m in range(1, 13):
        print(f"  {MESES[m - 1]} {ciclo[m]:5.2f}  " + "#" * int(ciclo[m] * 6))
    print(f"Dias con pluviometro: {c['precip_con_estacion'].mean():.1%}  (el resto "
          f"usa NASA escalado: sirve para acumulados, no para el dia exacto)")

    print("\nBanderas (fraccion de dias):")
    for bandera in ["llovio", "lluvia_fuerte", "dia_frio", "dia_calido"]:
        print(f"  {bandera:<14}{c[bandera].mean():6.1%}")

    # Escalones: el mayor salto de nivel entre dias con distinto numero de
    # fuentes. Si el metodo funciona, faltar una fuente no mueve el nivel.
    print("\nNivel medio segun cuantas fuentes hubo ese dia (debe ser parecido):")
    for nombre, n in [("temp_max_consenso", "n_fuentes_temp_max"),
                      ("precip_consenso_mm", "n_fuentes_precip")]:
        grupos = c.groupby(c[n])[nombre].mean()
        texto = "   ".join(f"{int(k)} fuentes: {v:5.2f}" for k, v in grupos.items() if k > 0)
        print(f"  {nombre:<20} {texto}")


if __name__ == "__main__":
    clima = unir()
    clima.to_csv(SALIDA, index=False, encoding="utf-8-sig")
    print(f"Escrito: {SALIDA}")
    auditar(clima)
