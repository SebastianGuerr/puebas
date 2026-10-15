"""
Detector automatico de terremotos con probable afectacion en Manizales, a partir del catalogo del USGS.

    python calendarios/fenomenos/actualizar_desastres.py          descarga, mide y escribe
    python calendarios/fenomenos/actualizar_desastres.py --seco   descarga y mide; no escribe nada

El criterio esta preregistrado en patrones/datos/variables.csv (fila desastre_terremoto_automatico, 2026-10-15) y
no se ajusta aqui: cambiarlo exige una fila nueva. El porque, el acierto medido y los limites estan en
calendarios/docs/ACTUALIZADORES.md.

Que escribe:
- calendarios/desastres_manizales_2020_2026.csv: SOLO anade filas al final, y solo si el criterio separo limpio en
  el historico (todas las filas reales detectadas y 0-1 falsos positivos) y la deteccion es posterior al corte del
  catalogo hecho a mano (CORTE_CATALOGO). Nunca modifica una fila existente.
- salidas/contexto/por_confirmar_desastres.csv: todas las detecciones, las reales no detectadas y los casi-umbral,
  con su estado, para que una persona las revise.

Idempotente: una deteccion a +-1 dia de una fila 'terremoto*' de Manizales ya existente no se vuelve a anadir.
Sale con codigo 1 si la descarga o la comprobacion fallan.
"""
import argparse
import csv
import io
import math
import sys
import unicodedata
from pathlib import Path

import pandas as pd
import requests

try:
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

RAIZ = Path(__file__).resolve().parents[2]
DESASTRES = RAIZ / "calendarios" / "desastres_manizales_2020_2026.csv"
POR_CONFIRMAR = RAIZ / "salidas" / "contexto" / "por_confirmar_desastres.csv"
USGS = "https://earthquake.usgs.gov/fdsnws/event/1/query"

# --- criterio preregistrado (variables.csv, desastre_terremoto_automatico) ---
LAT, LON = 5.07, -75.52            # Manizales
INICIO = "2020-01-01"
M_MIN = 4.5                         # universo
RADIO_KM = 300
I_MIN = 5.0                         # condicion 1: intensidad estimada en Manizales (Bakun y Wentworth 1997)
ALERTAS = {"yellow", "orange", "red"}  # condicion 2: compuerta de impacto del USGS
MMI_MIN = 6.0
FELT_MIN = 100
TOLERANCIA_DIAS = 1
MAX_FALSOS = 1
# Hasta esta fecha el catalogo de desastres lo revisa una persona: una deteccion anterior sin fila real es un falso
# positivo del criterio, no un terremoto olvidado. Solo lo posterior puede entrar solo.
CORTE_CATALOGO = pd.Timestamp("2026-10-15")
CASI_UMBRAL = 4.0                   # solo para el archivo de revision, no decide nada


def intensidad(m, d_epi_km, prof_km):
    """Bakun y Wentworth (1997): I = 3,67 + 1,17 M - 3,19 log10(R), R hipocentral en km."""
    r = math.hypot(d_epi_km, max(prof_km, 0.0))
    return 3.67 + 1.17 * m - 3.19 * math.log10(max(r, 1.0))


def distancia_km(lat, lon):
    p1, p2 = math.radians(LAT), math.radians(lat)
    dp, dl = p2 - p1, math.radians(lon - LON)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(a))


def descargar(hasta=None):
    q = {"format": "geojson", "starttime": INICIO, "minmagnitude": M_MIN, "latitude": LAT, "longitude": LON,
         "maxradiuskm": RADIO_KM, "orderby": "time-asc"}
    if hasta:
        q["endtime"] = hasta
    r = requests.get(USGS, params=q, timeout=120)
    r.raise_for_status()
    filas = []
    for f in r.json()["features"]:
        p, (lon, lat, prof) = f["properties"], f["geometry"]["coordinates"]
        filas.append({"usgs_id": f["id"], "hora_utc": pd.to_datetime(p["time"], unit="ms", utc=True),
                      "lat": lat, "lon": lon, "profundidad_km": prof, "magnitud": p["mag"], "lugar": p["place"],
                      "alerta": p.get("alert"), "mmi": p.get("mmi"), "felt": p.get("felt"), "url": p.get("url")})
    d = pd.DataFrame(filas)
    if d.empty:
        raise RuntimeError("el USGS no devolvio eventos: se esperaba al menos uno desde 2020")
    d["fecha"] = d.hora_utc.dt.tz_convert("America/Bogota").dt.tz_localize(None).dt.normalize()
    d["distancia_km"] = [distancia_km(a, b) for a, b in zip(d.lat, d.lon)]
    d["intensidad_manizales"] = [intensidad(m, x, z) for m, x, z in zip(d.magnitud, d.distancia_km, d.profundidad_km)]
    return d


def evaluar(d):
    """Aplica las dos condiciones preregistradas."""
    c1 = d.intensidad_manizales >= I_MIN
    hay = d.alerta.notna() | d.mmi.notna() | d.felt.notna()
    impacto = d.alerta.isin(ALERTAS) | (d.mmi.fillna(0) >= MMI_MIN) | (d.felt.fillna(0) >= FELT_MIN)
    d = d.copy()
    d["cond_intensidad"] = c1
    d["cond_impacto"] = impacto | ~hay
    d["detectado"] = c1 & d.cond_impacto
    return d


def filas_terremoto(cat):
    return cat[cat.subtipo.astype(str).str.startswith("terremoto") & cat.municipio.eq("Manizales")]


def cerca(fecha, fechas):
    return any(abs((fecha - f).days) <= TOLERANCIA_DIAS for f in fechas)


def medir(d, cat):
    """Acierto contra las filas reales (hechas a mano) hasta el corte del catalogo."""
    reales = filas_terremoto(cat)
    reales = reales[reales.calidad_dato.astype(str).ne("automatico_usgs")]
    f_reales = [pd.Timestamp(x) for x in reales.fecha_inicio]
    f_reales = [f for f in f_reales if pd.Timestamp(INICIO) <= f <= CORTE_CATALOGO]
    det = d[d.detectado & (d.fecha <= CORTE_CATALOGO)]
    aciertos = [f for f in f_reales if cerca(f, list(det.fecha))]
    falsos = det[det.fecha.map(lambda f: not cerca(f, f_reales)).astype(bool)]
    limpio = len(aciertos) == len(f_reales) and len(f_reales) > 0 and len(falsos) <= MAX_FALSOS
    return {"reales": f_reales, "aciertos": aciertos, "falsos": falsos, "limpio": limpio}


def descripcion(e):
    alerta = e.alerta if isinstance(e.alerta, str) else "sin dato"
    mmi = f"{e.mmi:.1f}" if pd.notna(e.mmi) else "sin dato"
    felt = f"{int(e.felt)}" if pd.notna(e.felt) else "sin dato"
    return (f"Deteccion automatica del USGS ({e.usgs_id}): M{e.magnitud:.1f} a {e.profundidad_km:.0f} km de profundidad, "
            f"epicentro a {e.distancia_km:.0f} km de Manizales ({e.lugar}). Intensidad estimada en Manizales "
            f"{e.intensidad_manizales:.2f} (Bakun y Wentworth 1997); PAGER {alerta}; MMI maxima {mmi}; felt {felt}. "
            f"SIN CIFRAS DE DANO: confirmar con la UGR de Manizales y completar la fila")


def ascii_(texto):
    """El catalogo esta escrito sin tildes; se mantiene asi."""
    return unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()


def fila_nueva(e, columnas):
    f = e.fecha.strftime("%Y-%m-%d")
    v = {c: "" for c in columnas}
    v.update({"fecha_inicio": f, "fecha_fin": f, "anio": str(e.fecha.year), "tipo_evento": "sismo",
              "subtipo": "terremoto_auto", "municipio": "Manizales", "descripcion": ascii_(descripcion(e)),
              "ambito": "municipal", "calidad_dato": "automatico_usgs", "fuente_url": e.url or ""})
    return [v[c] for c in columnas]


def anadir_filas(filas, columnas):
    """Anade al final sin tocar un byte de lo que ya hay (el archivo usa CRLF)."""
    original = DESASTRES.read_bytes()
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\r\n")
    for f in filas:
        w.writerow(f)
    sep = b"" if original.endswith(b"\n") else b"\r\n"
    DESASTRES.write_bytes(original + sep + buf.getvalue().encode("utf-8"))
    if not DESASTRES.read_bytes().startswith(original):
        raise RuntimeError("las filas existentes cambiaron al escribir")


def revision(d, med, nuevas_ids, anadidas):
    filas = []
    f_reales = med["reales"]
    for _, e in d[d.detectado | (d.intensidad_manizales >= CASI_UMBRAL)].iterrows():
        if not e.detectado:
            estado = "casi_umbral_no_detectado"
        elif e.fecha <= CORTE_CATALOGO:
            estado = "coincide_con_fila_real" if cerca(e.fecha, f_reales) else "falso_positivo_historico"
        elif e.usgs_id in nuevas_ids:
            estado = "nueva_anadida" if anadidas else "nueva_candidata_sin_entrar_al_modelo"
        else:
            estado = "ya_registrada"
        filas.append({"estado": estado, "fecha": e.fecha.date(), "usgs_id": e.usgs_id, "magnitud": e.magnitud,
                      "profundidad_km": round(e.profundidad_km, 1), "distancia_km": round(e.distancia_km, 1),
                      "intensidad_manizales": round(e.intensidad_manizales, 2), "alerta_pager": e.alerta,
                      "mmi_max": e.mmi, "felt": e.felt, "cond_intensidad": e.cond_intensidad,
                      "cond_impacto": e.cond_impacto, "lugar": e.lugar, "url": e.url})
    det = list(d[d.detectado].fecha)
    for f in f_reales:
        if not cerca(f, det):
            filas.append({"estado": "fila_real_no_detectada", "fecha": f.date()})
    return pd.DataFrame(filas).sort_values("fecha")


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seco", action="store_true", help="no escribe nada; solo informa")
    ap.add_argument("--hasta", help="fecha final de la consulta (por defecto, hoy)")
    a = ap.parse_args(argv)

    cat = pd.read_csv(DESASTRES)
    columnas = list(cat.columns)
    d = evaluar(descargar(a.hasta))
    med = medir(d, cat)
    print(f"USGS: {len(d)} eventos M>={M_MIN} a <={RADIO_KM} km desde {INICIO}; detectados {int(d.detectado.sum())}")
    print(f"historico hasta {CORTE_CATALOGO.date()}: filas reales {len(med['reales'])}, detectadas "
          f"{len(med['aciertos'])}, falsos positivos {len(med['falsos'])} -> "
          f"{'SEPARA LIMPIO: las nuevas entran como terremoto_auto' if med['limpio'] else 'NO SEPARA: las nuevas quedan como candidatas'}")
    for _, e in d[d.detectado].iterrows():
        print(f"  {e.fecha.date()} M{e.magnitud:.1f} prof {e.profundidad_km:.0f} km, {e.distancia_km:.0f} km, "
              f"I={e.intensidad_manizales:.2f}, PAGER {e.alerta}, MMI {e.mmi}, felt {e.felt} - {e.lugar}")

    existentes = [pd.Timestamp(x) for x in filas_terremoto(cat).fecha_inicio]
    nuevas = d[d.detectado & (d.fecha > CORTE_CATALOGO)]
    nuevas = nuevas[nuevas.fecha.map(lambda f: not cerca(f, existentes)).astype(bool)]
    anadir = med["limpio"] and not nuevas.empty
    print(f"detecciones nuevas posteriores al {CORTE_CATALOGO.date()}: {len(nuevas)}"
          + ("" if nuevas.empty else (" -> se anaden" if anadir else " -> solo candidatas")))

    rev = revision(d, med, set(nuevas.usgs_id), anadir)
    if a.seco:
        print("--seco: no se escribio nada")
        return 0
    if anadir:
        anadir_filas([fila_nueva(e, columnas) for _, e in nuevas.iterrows()], columnas)
        print(f"{DESASTRES.name}: +{len(nuevas)} filas terremoto_auto")
    POR_CONFIRMAR.parent.mkdir(parents=True, exist_ok=True)
    rev.to_csv(POR_CONFIRMAR, index=False)
    print(f"{POR_CONFIRMAR.relative_to(RAIZ)}: {len(rev)} filas")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # la tarea programada necesita un codigo distinto de cero
        print(f"ERROR actualizar_desastres: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
