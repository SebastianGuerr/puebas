"""
Sismos cerca de Manizales del catalogo del USGS (el FDSN del SGC da 404, CAPTURAS.md / FUENTES_EXTERNAS.md).

    python calendarios/fenomenos/sismos_usgs.py             incremental: solo cambian los ultimos 30 dias escritos
    python calendarios/fenomenos/sismos_usgs.py --rehacer   acepta tambien las revisiones antiguas del USGS

Magnitud >= 3,0 a menos de 150 km de Manizales, desde 2010. Solo datos publicos del catalogo.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

SALIDA = Path(__file__).resolve().parents[1] / "sismos_usgs.csv"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from calendarios.actualizacion import escribir_si_cambia, fusionar, proteger, resumen  # noqa: E402
# El USGS revisa magnitud y lugar en los dias siguientes al sismo (el 2026-10-15, el M4,5 del 29-sep paso a 4,4):
# se reabren los ultimos 30 dias del archivo; lo anterior no cambia.
REABRIR_DIAS = 30
q = {"format": "csv", "starttime": "2010-01-01", "minmagnitude": 3.0, "latitude": 5.0689, "longitude": -75.5174,
     "maxradiuskm": 150, "orderby": "time-asc"}
if __name__ == "__main__":
    import io
    ap = argparse.ArgumentParser(description="Sismos del USGS cerca de Manizales")
    ap.add_argument("--rehacer", action="store_true", help="acepta las revisiones de todo el pasado")
    rehacer = ap.parse_args().rehacer
    r = requests.get("https://earthquake.usgs.gov/fdsnws/event/1/query", params=q, timeout=120); r.raise_for_status()
    d = pd.read_csv(io.StringIO(r.text))[["time", "latitude", "longitude", "depth", "mag", "place"]]
    d["fecha"] = pd.to_datetime(d.time).dt.tz_convert("America/Bogota").dt.date
    d = d.drop(columns="time")
    viejo = pd.read_csv(SALIDA, float_precision="round_trip") if SALIDA.exists() else None
    proteger(viejo, d, "fecha", SALIDA.name)
    if viejo is not None and not rehacer:
        d, _ = fusionar(viejo, d, "fecha", REABRIR_DIAS, rellenar=False)
    d["fecha"] = pd.to_datetime(d["fecha"]).dt.date
    escrito = escribir_si_cambia(d, SALIDA, index=False)
    resumen(SALIDA.name, viejo, d, "fecha", escrito=escrito)
    print(f"{SALIDA.name}: {len(d)} sismos, {d.fecha.min()} a {d.fecha.max()}; M >= 4,5: {(d.mag >= 4.5).sum()}")
