"""
Sismos cerca de Manizales del catalogo del USGS (el FDSN del SGC da 404, CAPTURAS.md / FUENTES_EXTERNAS.md).

    python calendarios/fenomenos/sismos_usgs.py      escribe calendarios/sismos_usgs.csv

Magnitud >= 3,0 a menos de 150 km de Manizales, desde 2010. Solo datos publicos del catalogo.
"""
from pathlib import Path

import pandas as pd
import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

SALIDA = Path(__file__).resolve().parents[1] / "sismos_usgs.csv"
q = {"format": "csv", "starttime": "2010-01-01", "minmagnitude": 3.0, "latitude": 5.0689, "longitude": -75.5174,
     "maxradiuskm": 150, "orderby": "time-asc"}
if __name__ == "__main__":
    import io
    r = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params=q, timeout=120); r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))[["time", "latitude", "longitude", "depth", "mag", "place"]]
    d["fecha"] = pd.to_datetime(d.time).dt.tz_convert("America/Bogota").dt.date
    d.drop(columns="time").to_csv(SALIDA, index=False)
    print(f"{SALIDA.name}: {len(d)} sismos, {d.fecha.min()} a {d.fecha.max()}; M >= 4,5: {(d.mag >= 4.5).sum()}")
