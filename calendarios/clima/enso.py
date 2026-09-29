"""
Indice ENSO (ONI, Oceanic Nino Index) de la NOAA, por trimestre movil desde 1950.

    python calendarios/clima/enso.py      escribe calendarios/enso_oni.csv

ONI > +0,5 durante 5 trimestres seguidos = El Nino; < -0,5 = La Nina (definicion NOAA).
Se guarda tal cual (anomalia de la temperatura del mar en la region Nino 3.4) y con la
fase. Reemplaza los periodos escritos a mano en vigilancia_salud_manizales_caldas.csv.
Fuente: https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt
"""
from pathlib import Path

import pandas as pd
import requests

try:                                   # la red del hospital inspecciona TLS
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
SALIDA = Path(__file__).resolve().parents[1] / "enso_oni.csv"
# Mes central de cada trimestre movil: DJF -> enero, JFM -> febrero...
MES_CENTRAL = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
               "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}


def fase(oni):
    """El Nino / La Nina con la regla NOAA: 5 trimestres seguidos pasado el umbral."""
    nino = (oni >= 0.5).astype(int)
    nina = (oni <= -0.5).astype(int)
    racha = lambda s: s.groupby((s != s.shift()).cumsum()).transform("size") * s
    salida = pd.Series("neutral", index=oni.index).mask(racha(nino) >= 5, "el_nino").mask(racha(nina) >= 5, "la_nina")
    # Un episodio que sigue abierto al final de la serie todavia no puede tener 5 trimestres
    # (el El Nino de 2026 llevaba 3 en JJA). Se marca "en_curso" en vez de esconderlo como neutral.
    for s, nombre in ((nino, "el_nino"), (nina, "la_nina")):
        r = racha(s)
        if s.iloc[-1] == 1 and 3 <= r.iloc[-1] < 5:
            salida.iloc[-int(r.iloc[-1]):] = f"{nombre}_en_curso"
    return salida


def main():
    texto = requests.get(URL, timeout=60).text
    filas = [l.split() for l in texto.strip().splitlines()[1:] if l.strip()]
    t = pd.DataFrame(filas, columns=["trimestre", "anio", "total", "oni"])
    t["anio"] = t["anio"].astype(int)
    t["oni"] = t["oni"].astype(float)
    t["mes"] = t["trimestre"].map(MES_CENTRAL)
    t["fecha"] = pd.to_datetime(dict(year=t["anio"], month=t["mes"], day=15))
    t["fase"] = fase(t["oni"])
    t[["fecha", "trimestre", "anio", "oni", "fase"]].to_csv(SALIDA, index=False)
    ult = t.iloc[-1]
    print(f"{SALIDA.name}: {len(t)} trimestres, {t.fecha.min():%Y-%m} a {t.fecha.max():%Y-%m}; "
          f"ultimo {ult.trimestre} {ult.anio}: ONI {ult.oni:+.2f} ({ult.fase})")
    print(t[t.anio >= 2020].groupby("anio")["fase"].agg(lambda s: s.value_counts().to_dict()).to_string())


if __name__ == "__main__":
    main()
