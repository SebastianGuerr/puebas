"""
Delitos y lesiones de Manizales por dia, desde datos.gov.co (Ministerio de Defensa).

    python calendarios/seguridad/mindefensa.py             incremental: solo cambian los ultimos 90 dias escritos
    python calendarios/seguridad/mindefensa.py --rehacer   acepta tambien las revisiones antiguas

Solo se piden SUMAS por dia (`$select=fecha_hecho, sum(cantidad) ... $group=fecha_hecho`):
la fuente ya viene agregada y sin datos de persona, y ademas nunca se baja una fila suelta.
El porque y los limites estan en calendarios/docs/INVENTARIO.md y FUENTES_EXTERNAS.md.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd
import requests

try:                                   # la red del hospital inspecciona TLS
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

MANIZALES = "17001"
DATASETS = {
    "lesiones_transito": "ntej-qq7v",
    "homicidio_transito": "uav5-b85g",
    "lesiones_personales": "jr6v-i33g",
    "homicidio": "m8fd-ahd9",
    "violencia_intrafamiliar": "gepp-dxcs",
}
SALIDA = Path(__file__).resolve().parents[1] / "seguridad_mindefensa.csv.gz"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from calendarios.actualizacion import escribir_si_cambia, fusionar, proteger, resumen  # noqa: E402
# La Policia completa los ultimos meses con denuncias tardias: se reabren 90 dias; lo anterior no cambia.
REABRIR_DIAS = 90


def por_dia(id_, desde="2015-01-01"):
    url = f"https://www.datos.gov.co/resource/{id_}.json"
    params = {"$select": "fecha_hecho, sum(cantidad) as n",
              "$where": f"cod_muni='{MANIZALES}' AND fecha_hecho >= '{desde}T00:00:00'",
              "$group": "fecha_hecho", "$order": "fecha_hecho", "$limit": 50000}
    r = requests.get(url, params=params, timeout=120)
    r.raise_for_status()
    d = pd.DataFrame(r.json())
    if d.empty:
        return pd.Series(dtype=float)
    d["fecha"] = pd.to_datetime(d["fecha_hecho"]).dt.normalize()
    return d.groupby("fecha")["n"].sum().astype(float)


def main(rehacer=False):
    columnas = {}
    for nombre, id_ in DATASETS.items():
        s = por_dia(id_)
        columnas[nombre] = s
        print(f"  {nombre:24s} {id_}  {len(s):5d} dias con casos, {int(s.sum()):6d} casos, "
              f"{s.index.min():%Y-%m-%d} a {s.index.max():%Y-%m-%d}")
    t = pd.DataFrame(columnas)
    t = t.reindex(pd.date_range(t.index.min(), t.index.max())).fillna(0)   # dia sin casos = 0
    t.index.name = "fecha"
    t = t.reset_index()
    viejo = pd.read_csv(SALIDA) if SALIDA.exists() else None
    proteger(viejo, t, "fecha", SALIDA.name)
    revisiones = 0
    if viejo is not None and not rehacer:
        t, revisiones = fusionar(viejo, t, "fecha", REABRIR_DIAS)
    t["fecha"] = pd.to_datetime(t["fecha"]).dt.date
    escrito = escribir_si_cambia(t, SALIDA, index=False, float_format="%.0f")
    resumen(SALIDA.name, viejo, t, "fecha", revisiones, escrito)
    t = t.set_index(pd.to_datetime(t["fecha"])).drop(columns="fecha")
    print(t.groupby(t.index.year).sum().astype(int).to_string())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Delitos y lesiones de Manizales por dia (MinDefensa)")
    ap.add_argument("--rehacer", action="store_true", help="acepta las revisiones de todo el pasado")
    main(ap.parse_args().rehacer)
