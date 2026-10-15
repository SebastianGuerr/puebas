"""
Pluviometro y termometro IDEAM de La Nubia (AEROPUERTO LA NUBIA - AUT, 0026155110) a una fila por dia.

    python calendarios/clima/clima_ideam.py             incremental: solo cambian los ultimos 10 dias escritos
    python calendarios/clima/clima_ideam.py --rehacer   rehace La Nubia entera desde la fuente (mueve el pasado)

Sale:   calendarios/clima/clima_ideam.csv, con las columnas de siempre (las lee clima_unificado.py):
        fecha, precipitacion_mm, completitud_precip, temp_media, temp_min, temp_max, n_registros_temp,
        estacion_clima, estacion_km

LA FUENTE (datos.gov.co, API Socrata, sin token)
    s54a-sgyg  "Precipitacion"                   sensor 0240: lluvia de cada 10 minutos, 144 lecturas por dia
    sbwg-7ju4  "Temperatura Ambiente del Aire"   sensor 0068: temperatura horaria, 24 lecturas por dia
    Columnas que se usan: fechaobservacion (hora local, sin zona), valorobservado, codigosensor.

    Desde el 2026-08-12 la estacion publica ademas sensores GPRS cada 2 minutos (0257 lluvia, 0071
    temperatura). NO se mezclan: el CSV anterior los mezclaba y por eso sus cuatro dias con lluvia de
    2026-08-16 a 2026-08-23 salen multiplicados por ~5/3. Ver calendarios/docs/CLIMA.md.

LA AGREGACION (reconstruida contra el CSV anterior en los 977 dias de La Nubia, 2022-03-21 a 2026-08-25:
temperatura identica en los 977; lluvia en 973 y completitud en 976, y los que fallan son el defecto de arriba)
    1. Se quitan las lecturas repetidas (misma hora, mismo sensor). La fuente trae cada lectura dos veces
       de oct-2024 a feb-2025 y diecinueve veces el 2026-07-24.
    2. Dia = fecha local de fechaobservacion.
    3. precipitacion_mm   = suma de las lecturas del dia, redondeada a 2 decimales
       completitud_precip = min(1, lecturas / 144), a 3 decimales (clima_unificado descarta < 0,8)
       temp_media         = media decimal exacta de las lecturas, redondeada a 2 decimales con numpy
       temp_min / temp_max = extremos;  n_registros_temp = numero de lecturas de temperatura
    4. Hay fila si hay lluvia o temperatura ese dia; la variable que falte va vacia. No se rellena nada.

    Las filas de Tesorito Finca (2020-01 a 2020-07) y Planalto (2020-08 a 2023-09) se conservan tal como
    estan, tambien con --rehacer: son el empalme historico y no se vuelven a bajar. La Nubia manda en todo
    dia en que tiene dato.

Por que se hizo asi y con que evidencia: calendarios/docs/CLIMA.md, "El pluviometro IDEAM al dia".
"""
import argparse
import sys
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI.parents[1]))
from calendarios.actualizacion import MenosDatos, escribir_si_cambia, fusionar, proteger, resumen  # noqa: E402

SALIDA = AQUI / "clima_ideam.csv"
API = "https://www.datos.gov.co/resource/{}.json"
ESTACION = "0026155110"
NOMBRE = "AEROPUERTO LA NUBIA"
KM = 5.0
LLUVIA = ("s54a-sgyg", "0240")          # (conjunto, sensor de 10 minutos)
TEMPERATURA = ("sbwg-7ju4", "0068")     # (conjunto, sensor horario)
LECTURAS_LLUVIA_DIA = 144
INICIO_LA_NUBIA = "2022-03-01"          # primera lectura publicada: 2022-03-21

# Medido el 2026-10-15: el dia 14 ya estaba completo (144/144 y 24/24); en los 50 dias desde que se hizo el CSV
# anterior la fuente no cambio ningun valor de sus 977 dias ni relleno ningun hueco. La cola solo tiene que cubrir
# los ultimos dias a medias, y 10 es lo que reabre clima_unificado.py: un dia que el IDEAM complete tarde sigue
# dentro de la cola de los dos archivos.
REABRIR_DIAS = 10
# Se baja un trecho mas largo que la cola solo para CONTAR lo que la fuente cambiaria del pasado sin aplicarlo.
VERIFICAR_DIAS = 120
COLUMNAS = ["fecha", "precipitacion_mm", "completitud_precip", "temp_media", "temp_min", "temp_max",
            "n_registros_temp", "estacion_clima", "estacion_km"]


def bajar(conjunto, sensor, desde, hasta, pagina=50000, intentos=3):
    """Lecturas crudas de un sensor de La Nubia en [desde, hasta). Lanza excepcion si la API falla."""
    filas, offset = [], 0
    donde = (f"codigoestacion='{ESTACION}' AND codigosensor='{sensor}' "
             f"AND fechaobservacion >= '{desde}' AND fechaobservacion < '{hasta}'")
    while True:
        params = {"$select": "fechaobservacion, valorobservado", "$where": donde,
                  "$order": "fechaobservacion, :id", "$limit": pagina, "$offset": offset}
        for intento in range(intentos):
            try:
                r = requests.get(API.format(conjunto), params=params, timeout=300)
                r.raise_for_status()
                lote = r.json()
                break
            except (requests.RequestException, ValueError):
                if intento == intentos - 1:
                    raise
                time.sleep(10 * (intento + 1))
        filas += lote
        if len(lote) < pagina:
            break
        offset += pagina
    t = pd.DataFrame(filas, columns=["fechaobservacion", "valorobservado"])
    t["hora"] = pd.to_datetime(t["fechaobservacion"])
    t["valor"] = pd.to_numeric(t["valorobservado"], errors="coerce")
    t = t.dropna(subset=["hora", "valor"])
    t["texto"] = t["valorobservado"].astype(str)       # el decimal tal como lo publica la fuente
    return t[["hora", "valor", "texto"]]


def sin_repetidas(t, nombre):
    """Una lectura por hora. Si una hora trae valores distintos (no visto hasta hoy) se avisa y gana la primera."""
    conflictos = t.drop_duplicates(["hora", "valor"]).duplicated("hora").sum()
    if conflictos:
        print(f"AVISO {nombre}: {conflictos} horas con lecturas repetidas de valor distinto; se toma la primera")
    return t.drop_duplicates("hora")


def exacto(textos, operacion):
    """Suma o media EXACTA de los decimales publicados, pasada al float mas cercano (como el avg() de Socrata)."""
    total = sum(Decimal(x) for x in textos)
    return float(total / len(textos) if operacion == "media" else total)


def diario(lluvia, temperatura):
    lluvia = sin_repetidas(lluvia, "lluvia")
    temperatura = sin_repetidas(temperatura, "temperatura")
    p = lluvia.groupby(lluvia["hora"].dt.normalize())["texto"].agg(
        sum=lambda x: exacto(x, "suma"), size="size")
    t = temperatura.groupby(temperatura["hora"].dt.normalize()).agg(
        mean=("texto", lambda x: exacto(x, "media")), min=("valor", "min"), max=("valor", "max"),
        size=("valor", "size"))
    d = pd.DataFrame(index=p.index.union(t.index))
    d["precipitacion_mm"] = p["sum"].round(2)
    d["completitud_precip"] = (p["size"] / LECTURAS_LLUVIA_DIA).clip(upper=1).round(3)
    # Media decimal exacta y despues round(2) de numpy, que es lo que reproduce el CSV historico en los 977 dias.
    # Con la media en coma flotante (420,6 / 24 = 17,525000000000002 -> 17,53) fallaban 2 de 977 dias por 0,01;
    # con redondeo al par sobre el decimal exacto, 11.
    d["temp_media"] = t["mean"].round(2)
    d["temp_min"] = t["min"]
    d["temp_max"] = t["max"]
    d["n_registros_temp"] = t["size"].astype(float)
    d["estacion_clima"] = NOMBRE
    d["estacion_km"] = KM
    return d.rename_axis("fecha").reset_index()[COLUMNAS]


def main():
    ap = argparse.ArgumentParser(description="Pluviometro y temperatura IDEAM de La Nubia")
    ap.add_argument("--rehacer", action="store_true", help="rehace La Nubia entera y aplica las revisiones del pasado")
    rehacer = ap.parse_args().rehacer

    viejo = pd.read_csv(SALIDA, float_precision="round_trip") if SALIDA.exists() else None
    if viejo is not None:
        viejo["fecha"] = pd.to_datetime(viejo["fecha"])
    # Hoy (hora de Bogota) esta a medias: se baja hasta ayer incluido.
    hasta = datetime.now(ZoneInfo("America/Bogota")).date()
    if rehacer or viejo is None:
        desde = pd.Timestamp(INICIO_LA_NUBIA)
    else:
        desde = viejo["fecha"].max() - pd.Timedelta(days=VERIFICAR_DIAS)

    # Por tramos de un mes. El 2026-10-15 un tramo de un anyo bajo en segundos por la manana y por la tarde agoto
    # tres intentos de 300 s: el servidor de datos.gov.co es variable, y un tramo corto que falle se reintenta solo.
    tramos = pd.date_range(desde, hasta, freq="MS").union([desde, pd.Timestamp(hasta)])
    lluvia, temperatura = [], []
    for a, b in zip(tramos[:-1], tramos[1:]):
        lluvia.append(bajar(*LLUVIA, f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}"))
        temperatura.append(bajar(*TEMPERATURA, f"{a:%Y-%m-%d}", f"{b:%Y-%m-%d}"))
    nuevo = diario(pd.concat(lluvia), pd.concat(temperatura))
    if len(nuevo):
        print(f"Fuente: {len(nuevo)} dias de La Nubia, {nuevo.fecha.min():%Y-%m-%d} a {nuevo.fecha.max():%Y-%m-%d}")

    if viejo is None:
        proteger(None, nuevo, "fecha", SALIDA.name)
        tabla, revisiones = nuevo, 0
    else:
        nubia_vieja = viejo[(viejo["estacion_clima"] == NOMBRE) & (viejo["fecha"] >= desde)]
        proteger(nubia_vieja, nuevo, "fecha", SALIDA.name)
        if rehacer:
            # La Nubia sale entera de la fuente; Tesorito y Planalto se conservan donde La Nubia no tiene dato.
            otras = viejo[(viejo["estacion_clima"] != NOMBRE) & ~viejo["fecha"].isin(nuevo["fecha"])]
            tabla = pd.concat([otras, nuevo]).sort_values("fecha").reset_index(drop=True)
            revisiones = 0
        else:
            corte = viejo["fecha"].max() - pd.Timedelta(days=REABRIR_DIAS)
            tabla, revisiones = fusionar(viejo, nuevo, "fecha", REABRIR_DIAS)
            huecos = int((~nuevo.loc[nuevo["fecha"] < corte, "fecha"].isin(viejo["fecha"])).sum())
            if huecos:
                print(f"AVISO: la fuente trae {huecos} dias anteriores al {corte:%Y-%m-%d} que el archivo no tiene; "
                      f"no se anaden (--rehacer los anade)")
    tabla = tabla[COLUMNAS].copy()
    tabla["fecha"] = pd.to_datetime(tabla["fecha"]).dt.date
    if tabla["fecha"].duplicated().any():
        raise ValueError("fechas repetidas en la tabla final")
    escrito = escribir_si_cambia(tabla, SALIDA, index=False)
    resumen(SALIDA.name, viejo, tabla, "fecha", revisiones, escrito)


if __name__ == "__main__":
    try:
        main()
    except (MenosDatos, requests.RequestException, ValueError) as e:
        print(f"ERROR clima_ideam: {e}", file=sys.stderr)
        sys.exit(1)
