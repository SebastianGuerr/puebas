"""
Captura periodica de las fuentes que NO guardan su historia: lo que se sabia cada dia solo existe si se
guardo ese dia. La ejecuta una tarea programada de Windows (calendarios/capturas.cmd); tambien a mano.

    python calendarios/capturas.py              corre todas las fuentes que toque
    python calendarios/capturas.py --solo bdua  una sola fuente
    python calendarios/capturas.py --estado     ultimas capturas por fuente, sin descargar nada

Fuentes (calendarios/docs/CAPTURAS.md tiene el porque de cada una):
    powerbi      tableros del INS (SIVIGILA ~7 dias de rezago) via calendarios/vigilancia/powerbi.py; semanal
    bdua         afiliados por EPS x municipio x edad x estado de Caldas (datos.gov.co); foto SIN historico
    afiliacion   zips mensuales de cifras de afiliacion de MinSalud (EPS x municipio); se extrae Caldas
    medidas      Excel de la Supersalud: EPS en medida especial, intervencion, liquidacion
    oni          indice ENSO de la NOAA (y se rehace calendarios/enso_oni.csv)

Cada fuente se guarda solo si cambio respecto de la ultima captura (huella sha256), en
calendarios/capturas/<fuente>/. Todo queda en calendarios/capturas/registro.csv. Solo agregados: ninguna
fuente trae dato de persona.
"""
import argparse, hashlib, html, io, re, subprocess, sys, zipfile
from datetime import datetime, date
from pathlib import Path

import pandas as pd
import requests

try:                                                     # la red del hospital inspecciona TLS
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

RAIZ = Path(__file__).resolve().parents[1]
CAP = RAIZ / "calendarios/capturas"
CRUDO = CAP / "crudo"                                    # ignorado por git: archivos nacionales pesados
REGISTRO = CAP / "registro.csv"
H = {"User-Agent": "Mozilla/5.0 (proyecto academico triage SES Caldas)"}
HOY = date.today().isoformat()


def huella(b):
    return hashlib.sha256(b).hexdigest()


def anotar(fuente, accion, archivo="", filas="", sha="", detalle=""):
    REGISTRO.parent.mkdir(parents=True, exist_ok=True)
    fila = pd.DataFrame([{"fecha_hora": datetime.now().isoformat(timespec="seconds"), "fuente": fuente, "accion": accion,
                          "archivo": Path(archivo).resolve().relative_to(RAIZ).as_posix() if archivo else "", "filas": filas,
                          "sha256": sha[:16], "detalle": detalle}])
    fila.to_csv(REGISTRO, mode="a", header=not REGISTRO.exists(), index=False, encoding="utf-8")
    print(f"  {fuente}: {accion} {archivo if archivo else ''} {detalle}", flush=True)


def ya_visto(fuente, sha):
    if not REGISTRO.exists(): return False
    r = pd.read_csv(REGISTRO, dtype=str)
    return ((r.fuente == fuente) & (r.sha256 == sha[:16])).any()


# ---------------------------------------------------------------- fuentes
def powerbi():
    carpetas = sorted(p.name for p in (RAIZ / "calendarios/vigilancia/powerbi").iterdir() if p.is_dir())
    if carpetas and (date.today() - date.fromisoformat(carpetas[-1])).days < 6:
        return anotar("powerbi", "sin_cambios", detalle=f"ultima foto {carpetas[-1]} (< 6 dias)")
    r = subprocess.run([sys.executable, str(RAIZ / "calendarios/vigilancia/powerbi.py")], cwd=RAIZ,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    ok = r.returncode == 0
    anotar("powerbi", "nuevo" if ok else "error", f"calendarios/vigilancia/powerbi/{HOY}" if ok else "",
           detalle="" if ok else r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else f"codigo {r.returncode}")


def bdua():
    for regimen, ds in [("contributivo", "tq4m-hmg2"), ("subsidiado", "d7a5-cnra")]:
        meta = requests.get(f"https://www.datos.gov.co/api/views/{ds}.json", headers=H, timeout=120).json()
        corte = datetime.fromtimestamp(meta.get("rowsUpdatedAt", 0)).date().isoformat()
        q = {"$select": "ent_id,ent_nombre,mnc_nombre,tps_grp_etr_id,tps_gnr_nombre,tps_est_afl_nombre,tps_afl_nombre,sum(cantidad::number) as afiliados",
             "$where": "dpr_nombre='CALDAS'",
             "$group": "ent_id,ent_nombre,mnc_nombre,tps_grp_etr_id,tps_gnr_nombre,tps_est_afl_nombre,tps_afl_nombre",
             "$limit": 200000}
        r = requests.get(f"https://www.datos.gov.co/resource/{ds}.json", params=q, headers=H, timeout=300)
        if r.status_code != 200: anotar("bdua", "error", detalle=f"{regimen}: HTTP {r.status_code} {r.text[:120]}"); continue
        d = pd.DataFrame(r.json())
        if d.empty: anotar("bdua", "error", detalle=f"{regimen}: consulta vacia"); continue
        d["afiliados"] = pd.to_numeric(d.afiliados); d.insert(0, "regimen", regimen); d.insert(0, "corte_datos_gov", corte)
        d = d.sort_values(list(d.columns[:-1])).reset_index(drop=True)
        b = d.to_csv(index=False).encode("utf-8"); sha = huella(b)
        if ya_visto("bdua", sha): anotar("bdua", "sin_cambios", detalle=f"{regimen}, corte {corte}"); continue
        f = CAP / "bdua" / f"bdua_caldas_{regimen}_{corte}.csv.gz"; f.parent.mkdir(parents=True, exist_ok=True)
        d.to_csv(f, index=False, compression="gzip")
        anotar("bdua", "nuevo", f, len(d), sha, f"{regimen}, corte {corte}, {int(d.afiliados.sum())} afiliados en Caldas")


def enlaces(url, patron):
    t = requests.get(url, headers=H, timeout=120).text
    return sorted({html.unescape(l) for l in re.findall(r'href="([^"]+\.(?:' + patron + r'))"', t, re.I)})


def afiliacion():
    base = "https://www.minsalud.gov.co"
    for l in enlaces(base + "/Proteccion-Social/Paginas/cifras-aseguramiento-salud.aspx", "zip"):
        nombre = l.rsplit("/", 1)[-1]; destino = CRUDO / "afiliacion" / nombre
        caldas = CAP / "afiliacion" / (nombre.replace(".zip", "") + "_caldas.csv.gz")
        if caldas.exists(): continue
        try:
            if not destino.exists():
                destino.parent.mkdir(parents=True, exist_ok=True)
                destino.write_bytes(requests.get(l if l.startswith("http") else base + l, headers=H, timeout=600).content)
            filas = extraer_caldas(destino)
            if filas is None: anotar("afiliacion", "descargado_sin_extraer", destino, detalle="formato no reconocido; revisar a mano"); continue
            caldas.parent.mkdir(parents=True, exist_ok=True); filas.to_csv(caldas, index=False, compression="gzip")
            anotar("afiliacion", "nuevo", caldas, len(filas), huella(destino.read_bytes()), nombre)
        except Exception as e:
            anotar("afiliacion", "error", detalle=f"{nombre}: {e!r}"[:200])


def extraer_caldas(zip_path):
    """Hojas de MinSalud (encabezado en una o dos filas): filas de CALDAS en formato largo
    (hoja, fila, columna, valor), para que hojas con columnas distintas quepan en un solo archivo. None si nada."""
    sal = []
    with zipfile.ZipFile(zip_path) as z:
        for n in z.namelist():
            if n.startswith("__MACOSX") or n.rsplit("/", 1)[-1].startswith("._") or not n.lower().endswith((".xlsx", ".xls")):
                continue
            for hoja, t in pd.read_excel(io.BytesIO(z.read(n)), sheet_name=None, header=None, dtype=str).items():
                fila_enc = next((i for i in range(min(12, len(t))) if t.iloc[i].astype(str).str.strip().str.upper().eq("DEPARTAMENTO").any()), None)
                if fila_enc is None: continue
                arriba = t.iloc[fila_enc - 1].ffill() if fila_enc > 0 else pd.Series([""] * t.shape[1])
                cols = [(f"{a} | {b}" if isinstance(a, str) and a.strip() and a != "nan" else str(b)).strip() for a, b in zip(arriba, t.iloc[fila_enc])]
                d = t.iloc[fila_enc + 1:].copy(); d.columns = cols
                cdep = next((c for c in cols if c.upper().split("| ")[-1] == "DEPARTAMENTO"), None) or                        next(c for c in cols if c.upper().endswith("DEPARTAMENTO"))   # 2026 trae IdDepartamento antes
                d = d[d[cdep].astype(str).str.upper().str.contains("CALDAS", na=False)]
                if len(d):
                    largo = d.reset_index(drop=True).reset_index().melt(id_vars="index", var_name="columna", value_name="valor").dropna(subset=["valor"])
                    sal.append(largo.rename(columns={"index": "fila"}).assign(hoja=hoja))
    return pd.concat(sal)[["hoja", "fila", "columna", "valor"]] if sal else None


COLUMNAS_MEDIDAS = ["ENTIDAD", "NOMBRE DE ENTIDAD", "NIT", "CIUDAD", "DEPARTAMENTO", "CIUDAD/ DEPARTAMENTO", "CLASE DE MEDIDA",
                     "RESOLUCIÓN", "FECHA FINAL MEDIDA", "FECHA DE VENCIMIENTO", "ACTA DE POSESIÓN", "ACTA DE TOMA DE POSESIÓN"]


def limpiar_medidas(b):
    """Tabla de la Supersalud SIN las columnas de persona (interventor, documento, correo, telefono, direccion)."""
    x = pd.read_excel(io.BytesIO(b), header=None, dtype=str)
    h = next((i for i in range(min(25, len(x))) if x.iloc[i].astype(str).str.strip().str.upper()
              .isin(["ENTIDAD", "NOMBRE DE ENTIDAD"]).any()), None)
    if h is None: return None
    t = x.iloc[h + 1:].copy(); t.columns = [str(c).strip() for c in x.iloc[h]]
    cols = [c for c in t.columns if c in COLUMNAS_MEDIDAS]
    ent = next(c for c in cols if "ENTIDAD" in c)
    return t[cols].dropna(subset=[ent]).replace(r"\s+", " ", regex=True)


def medidas():
    """Los Excel originales traen datos de persona de los interventores: van a crudo/ (no se versionan) y se
    versiona solo la tabla limpia (entidad, NIT, ciudad, medida, resolucion, fechas)."""
    for l in enlaces("https://www.supersalud.gov.co/es-co/transparencia-y-acceso-a-la-informacion-publica/informacion-especifica-para-grupos-de-interes/entidades-en-medida-especial-liquidacion-y-traslados-de-eps", "xlsx?"):
        nombre = requests.utils.unquote(l.rsplit("/", 1)[-1])
        try:
            b = requests.get(l, headers=H, timeout=300).content; sha = huella(b)
            if ya_visto("medidas", sha): anotar("medidas", "sin_cambios", detalle=nombre[:80]); continue
            crudo = CRUDO / "medidas" / HOY / nombre; crudo.parent.mkdir(parents=True, exist_ok=True); crudo.write_bytes(b)
            t = limpiar_medidas(b)
            if t is None: anotar("medidas", "descargado_sin_limpiar", crudo, sha=sha, detalle=nombre[:80]); continue
            f = CAP / "medidas" / HOY / (Path(nombre).stem + ".csv"); f.parent.mkdir(parents=True, exist_ok=True)
            t.to_csv(f, index=False, encoding="utf-8")
            anotar("medidas", "nuevo", f, len(t), sha, nombre[:80])
        except Exception as e:
            anotar("medidas", "error", detalle=f"{nombre[:60]}: {e!r}"[:200])


def oni():
    b = requests.get("https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt", headers=H, timeout=120).content; sha = huella(b)
    if ya_visto("oni", sha): return anotar("oni", "sin_cambios")
    f = CAP / "oni" / f"oni_{HOY}.txt"; f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(b)
    r = subprocess.run([sys.executable, str(RAIZ / "calendarios/clima/enso.py")], cwd=RAIZ, capture_output=True, text=True)
    anotar("oni", "nuevo", f, sha=sha, detalle="enso_oni.csv rehecho" if r.returncode == 0 else "enso.py fallo")


FUENTES = {"powerbi": powerbi, "bdua": bdua, "afiliacion": afiliacion, "medidas": medidas, "oni": oni}

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--solo", nargs="*", choices=list(FUENTES)); ap.add_argument("--estado", action="store_true")
    a = ap.parse_args()
    if a.estado:
        r = pd.read_csv(REGISTRO) if REGISTRO.exists() else pd.DataFrame()
        print(r.sort_values("fecha_hora").groupby("fuente").tail(1).to_string(index=False) if len(r) else "sin capturas todavia"); sys.exit()
    print(f"capturas {datetime.now():%Y-%m-%d %H:%M}", flush=True)
    for nombre in a.solo or FUENTES:
        try: FUENTES[nombre]()
        except Exception as e: anotar(nombre, "error", detalle=repr(e)[:200])
