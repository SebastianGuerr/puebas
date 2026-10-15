"""
Tableros Power BI publicos del INS -> conteos semanales AGREGADOS de Manizales, congelados por fecha.

    python calendarios/vigilancia/powerbi.py                  descarga y congela hoy
    python calendarios/vigilancia/powerbi.py --esquema 006    solo NOMBRES de tablas y columnas
    python calendarios/vigilancia/powerbi.py --empalme        compara 2025 contra los microdatos

Es la via para 2026: los microdatos salen con ~8 meses de rezago y los tableros
van ~7 dias por detras. El porque de cada decision esta en
calendarios/docs/VIGILANCIA.md, seccion "Power BI: la via de 2026".

Sale:   calendarios/vigilancia/powerbi/AAAA-MM-DD/   una carpeta por dia de descarga
            rutinaria_manizales.csv   006, tabla 'Rutinaria {ano}': evento x semana
            ira_995_rutinaria.csv     006, tabla 'salida_para_rutinaria_995 {ano}'
            ira_995_tablero.csv       tablero 995, tabla IRA: numerador y denominador
            evento_{cod}.csv          tableros por evento: medida Casos por ano y semana
            metadatos.json            clave, tabla, refresco del INS y consulta de cada archivo
        Las carpetas NO se sobrescriben entre dias: las 2-3 ultimas semanas se
        revisan con la notificacion tardia, y lo que se sabia en cada fecha vale.
        Una carpeta AAAA-MM-DD solo aparece si TODOS los archivos bajaron y ninguno
        trae menos filas que la descarga anterior. Si no, lo bajado va a
        powerbi/_parciales/AAAA-MM-DD/ y el proceso sale con codigo 1 (CAPTURAS.md).

API: la interna de 'Publish to web' (no documentada). Sin token: solo la clave
publica del tablero, que se lee en cada corrida de la lista SharePoint
'MenuReporteNivel2' del portal SIVIGILA (si el portal no responde, se usan las
claves de la ultima descarga, guardadas en su metadatos.json). El nombre de la
tabla lleva el ano y se descubre con conceptualschema.

PRIVACIDAD, NO NEGOCIABLE
    Los modelos de los tableros POR EVENTO exponen en su esquema columnas de
    persona (nombre, documento, direccion, telefono, coordenadas). Este modulo
    solo pide: la tabla ya agregada del 006 (SUM(conteo)), sumas de columnas de
    conteo, y la medida Calculos[Casos]. Toda consulta pasa por
    consulta_agregada(), que rechaza cualquier columna que no este en
    AGRUPABLES (ano, semana, codigo y nombre de evento) como agrupacion.
"""

import argparse
import base64
import json
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests

try:                                    # inspeccion TLS corporativa en esta red
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

AQUI = Path(__file__).resolve().parent
CARPETA = AQUI / "powerbi"
CLUSTER = "https://wabi-south-central-us-api.analysis.windows.net"
MENU = ("https://portalsivigila.ins.gov.co/_api/web/lists/getbytitle('MenuReporteNivel2')/items"
        "?$select=Title,Url&$top=500")
CAB = {"User-Agent": "Mozilla/5.0"}
MANIZALES = "17001"

# Las unicas columnas por las que se deja AGRUPAR una consulta. Todo lo demas
# solo puede aparecer sumado, o como filtro de municipio.
AGRUPABLES = {"año", "Año", "semana", "Semana", "cod_eve", "nom_eve"}


# ==========================================================
# CLIENTE
# ==========================================================

def tableros():
    """{titulo: clave} de la lista MenuReporteNivel2. La clave va en el parametro r (base64)."""
    r = requests.get(MENU, headers={"Accept": "application/json;odata=nometadata", **CAB}, timeout=60)
    r.raise_for_status()
    salida = {}
    for x in r.json()["value"]:
        url = (x.get("Url") or {}).get("Url") or ""
        m = re.search(r"app\.powerbi\.com/view\?r=([A-Za-z0-9+/=_-]+)", url)
        if not m:
            continue
        crudo = m.group(1)
        try:
            k = json.loads(base64.b64decode(crudo + "=" * (-len(crudo) % 4)))["k"]
        except Exception:
            continue
        salida[x["Title"].strip()] = k
    return salida


def tableros_guardados():
    """{titulo: clave} de la ultima descarga completa: plan B cuando la lista del portal no responde."""
    for carpeta in sorted(CARPETA.glob("????-??-??"), reverse=True):
        meta = carpeta / "metadatos.json"
        if meta.exists():
            m = json.loads(meta.read_text(encoding="utf-8"))
            tabs = {a["tablero"]: a["clave"] for a in m["archivos"].values() if "clave" in a and "tablero" in a}
            if tabs:
                return tabs
    raise FileNotFoundError(f"ninguna descarga en {CARPETA} trae claves en metadatos.json")


def clave(tabs, prefijo):
    """Clave del tablero cuyo titulo empieza por el prefijo ('006 ', '995 ', '356 ')."""
    c = [t for t in tabs if t.startswith(prefijo)]
    if len(c) != 1:
        raise KeyError(f"tableros que empiezan por {prefijo!r}: {c}")
    return c[0], tabs[c[0]]


def sesion(k):
    h = {"X-PowerBI-ResourceKey": k, **CAB}
    r = requests.get(f"{CLUSTER}/public/reports/{k}/modelsAndExploration?preferReadOnlySession=true",
                     headers=h, timeout=60)
    r.raise_for_status()
    mae = r.json()
    m = mae["models"][0]
    return {"clave": k, "modelo": m["id"], "dataset": m["dbName"],
            "reporte": mae["exploration"]["report"]["objectId"],
            "refresco_ins": m.get("LastRefreshTime"), "proximo_refresco_ins": m.get("NextRefreshTime")}


def esquema(s):
    """{tabla: {'columnas': [...], 'medidas': [...]}}. Solo NOMBRES: no toca un dato."""
    h = {"X-PowerBI-ResourceKey": s["clave"], **CAB}
    r = requests.post(f"{CLUSTER}/public/reports/conceptualschema", headers=h,
                      json={"modelIds": [s["modelo"]], "userPreferredLocale": "es-ES"}, timeout=60)
    r.raise_for_status()
    out = {}
    for sch in r.json()["schemas"]:
        for e in sch["schema"]["Entities"]:
            if e["Name"].startswith(("LocalDateTable", "DateTableTemplate")):
                continue
            props = e.get("Properties", [])
            out[e["Name"]] = {"columnas": [p["Name"] for p in props if "Measure" not in p],
                              "medidas": [p["Name"] for p in props if "Measure" in p]}
    return out


def _col(alias, prop):
    return {"Column": {"Expression": {"SourceRef": {"Source": alias}}, "Property": prop}}


def _filtro(alias, prop, valor):
    lit = f"'{valor}'" if isinstance(valor, str) else f"{valor}L"
    return {"Condition": {"In": {"Expressions": [_col(alias, prop)],
                                 "Values": [[{"Literal": {"Value": lit}}]]}}}


def consulta_agregada(s, desde, grupos, sumas=(), medidas=(), filtros=(), desde_anio=None, n=30000):
    """
    desde:   {alias: tabla}
    grupos:  [(alias, columna)]  SOLO columnas de AGRUPABLES
    sumas:   [(alias, columna)]  se piden como SUM
    medidas: [(alias, medida)]   medidas del modelo (p. ej. Calculos[Casos])
    filtros: [(alias, columna, valor)]  igualdad; el municipio va aqui
    desde_anio: (alias, columna, ano) -> columna >= ano. Algunas tablas de
             fechas del INS empiezan en el ano 987, y sin este corte la
             respuesta son mil anos de ceros.
    Devuelve (DataFrame, consulta enviada).
    """
    for _, c in grupos:
        if c not in AGRUPABLES:
            raise ValueError(f"'{c}' no se puede usar como agrupacion: solo {sorted(AGRUPABLES)}")
    sel, nombres = [], []
    for a, c in grupos:
        sel.append(dict(_col(a, c), Name=f"{a}.{c}"))
        nombres.append(c)
    for a, c in sumas:
        sel.append({"Aggregation": {"Expression": _col(a, c), "Function": 0}, "Name": f"sum({a}.{c})"})
        nombres.append(c)
    for a, c in medidas:
        sel.append({"Measure": {"Expression": {"SourceRef": {"Source": a}}, "Property": c},
                    "Name": f"{a}.{c}"})
        nombres.append(c)
    q = {"Version": 2, "From": [{"Name": a, "Entity": t, "Type": 0} for a, t in desde.items()],
         "Select": sel, "Where": [_filtro(*f) for f in filtros]}
    if desde_anio:
        a, c, v = desde_anio
        q["Where"].append({"Condition": {"Comparison": {"ComparisonKind": 2, "Left": _col(a, c),
                                                        "Right": {"Literal": {"Value": f"{v}L"}}}}})
    cuerpo = {"version": "1.0.0", "queries": [{"Query": {"Commands": [{"SemanticQueryDataShapeCommand": {
        "Query": q,
        "Binding": {"Primary": {"Groupings": [{"Projections": list(range(len(sel)))}]},
                    "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": n}}}, "Version": 1}}}]},
        "QueryId": "", "ApplicationContext": {"DatasetId": s["dataset"], "Sources": [{"ReportId": s["reporte"]}]}}],
        "cancelQueries": [], "modelId": s["modelo"]}
    h = {"X-PowerBI-ResourceKey": s["clave"], **CAB}
    r = requests.post(f"{CLUSTER}/public/reports/querydata?synchronous=true", headers=h, json=cuerpo, timeout=180)
    r.raise_for_status()
    res = r.json()["results"][0]["result"]
    dsr = res["data"]["dsr"]
    if "DataShapes" in dsr and any("odata.error" in x for x in dsr["DataShapes"]):
        raise RuntimeError(f"error del modelo: {json.dumps(dsr['DataShapes'])[:400]}")
    filas = _decodificar(dsr, len(sel))
    if len(filas) >= n:
        raise RuntimeError(f"se alcanzo el limite de {n} filas: la respuesta esta truncada")
    return pd.DataFrame(filas, columns=nombres), q


def _decodificar(dsr, nsel):
    """Formato DSR de Power BI: R = columnas repetidas de la fila anterior, Ø = nulas,
    y las columnas con DN guardan un indice a un diccionario de valores."""
    if "DS" not in dsr:
        raise RuntimeError(f"respuesta sin datos: {list(dsr)}")
    ds = dsr["DS"][0]
    if "PH" not in ds or not ds["PH"] or "DM0" not in ds["PH"][0]:
        return []
    dicts = ds.get("ValueDicts", {})
    filas, prev, dn = [], [None] * nsel, {}
    for k, fila in enumerate(ds["PH"][0]["DM0"]):
        if k == 0:
            for i, sch in enumerate(fila.get("S", [])):
                if "DN" in sch:
                    dn[i] = dicts[sch["DN"]]
        vals = iter(fila.get("C", []))
        rep, nul = fila.get("R", 0), fila.get("Ø", 0)
        out = []
        for i in range(nsel):
            if (rep >> i) & 1:
                out.append(prev[i])
            elif (nul >> i) & 1:
                out.append(None)
            else:
                v = next(vals, None)
                if i in dn and isinstance(v, int):
                    v = dn[i][v]
                out.append(v)
        prev = out
        filas.append(out)
    return filas


# ==========================================================
# DESCARGAS
# ==========================================================

def inicio_semana(anio, semana):
    """Domingo que abre la semana epidemiologica (la SE1 contiene el 4 de enero)."""
    cuatro = date(int(anio), 1, 4)
    return cuatro - timedelta(days=(cuatro.weekday() + 1) % 7) + timedelta(weeks=int(semana) - 1)


def tabla_con_anio(esq, patron):
    """El nombre de tabla lleva el ano ('Rutinaria 2026'): se toma la del ano mas alto."""
    c = [(int(m.group(1)), t) for t in esq if (m := re.fullmatch(patron, t))]
    if not c:
        raise KeyError(f"ninguna tabla cumple {patron!r}: {sorted(esq)}")
    return max(c)[1]


def rutinaria(tabs):
    """006: evento x semana de Manizales (municipio de procedencia), tabla ya agregada por el INS."""
    titulo, k = clave(tabs, "006 ")
    s = sesion(k)
    t = tabla_con_anio(esquema(s), r"Rutinaria (\d{4})")
    d, q = consulta_agregada(s, {"t": t}, [("t", "año"), ("t", "cod_eve"), ("t", "nom_eve"), ("t", "semana")],
                             sumas=[("t", "conteo")], filtros=[("t", "Cod_municipio", MANIZALES)])
    d.columns = ["anio", "cod_eve", "nom_eve", "semana", "casos"]
    return d, dict(s, tablero=titulo, tabla=t, filtro=f"Cod_municipio = {MANIZALES}", consulta=q)


def ira_rutinaria(tabs):
    """006: IRA 995 de 2026 por semana, municipio de notificacion (sin denominador por edad)."""
    titulo, k = clave(tabs, "006 ")
    s = sesion(k)
    t = tabla_con_anio(esquema(s), r"salida_para_rutinaria_995 (\d{4})")
    d, q = consulta_agregada(s, {"t": t}, [("t", "año"), ("t", "semana")],
                             sumas=[("t", c) for c in ("SumaDetot_iraext", "tot_exturg",
                                                       "SumaDetot_irag", "SumaDetot_irauci")],
                             filtros=[("t", "nmun_notif", "MANIZALES"), ("t", "ndep_notif", "CALDAS")])
    d.columns = ["anio", "semana", "consultas_ira", "consultas_todas_causas",
                 "hospitalizaciones_irag", "uci_irag"]
    return d, dict(s, tablero=titulo, tabla=t, filtro="nmun_notif = MANIZALES, ndep_notif = CALDAS",
                   consulta=q)


def ira_tablero(tabs):
    """Tablero 995, tabla IRA: numerador y denominador por edad, todos los anos que tenga."""
    titulo, k = clave(tabs, "995 ")
    s = sesion(k)
    sumas = [f"grupo_{i}" for i in range(1, 8)] + ["grup_total"] + [f"Tot_{i}" for i in range(1, 8)] + ["Tot_tot"]
    d, q = consulta_agregada(s, {"t": "IRA"}, [("t", "año"), ("t", "semana")],
                             sumas=[("t", c) for c in sumas], filtros=[("t", "cod_mun", MANIZALES)])
    d = d.rename(columns={"año": "anio"})
    return d, dict(s, tablero=titulo, tabla="IRA", filtro=f"cod_mun = {MANIZALES}", consulta=q)


def por_evento(tabs, evento):
    """Tablero de un evento: medida Calculos[Casos] por ano y semana, filtrada a Manizales."""
    titulo, k = clave(tabs, f"{evento} ")
    s = sesion(k)
    esq = esquema(s)
    cal = [t for t in ("Calendario", "Fechas") if t in esq and {"Año", "Semana"} <= set(esq[t]["columnas"])]
    mun = [t for t in ("Municipio", "2Municipio") if t in esq and "CodMun" in esq[t]["columnas"]]
    if not cal or not mun or "Casos" not in esq.get("Calculos", {}).get("medidas", []):
        raise KeyError(f"{titulo}: sin calendario, municipio (CodMun) o medida Casos")
    d, q = consulta_agregada(s, {"c": cal[0], "k": "Calculos", "m": mun[0]},
                             [("c", "Año"), ("c", "Semana")], medidas=[("k", "Casos")],
                             filtros=[("m", "CodMun", MANIZALES)], desde_anio=("c", "Año", 2007), n=5000)
    d.columns = ["anio", "semana", "casos"]
    # La tabla de fechas cubre anos enteros, tambien los que el tablero no
    # tiene y las semanas que aun no han pasado: la medida da 0 ahi. Se quitan
    # los anos sin ningun caso y las semanas que empiezan despues del refresco.
    d = d.dropna(subset=["anio", "semana"])
    d = d[d.groupby("anio")["casos"].transform("sum") > 0]
    tope = pd.Timestamp(s["refresco_ins"]).date()
    d = d[[inicio_semana(a, w) <= tope for a, w in zip(d["anio"], d["semana"])]]
    return d, dict(s, tablero=titulo, tabla=f"{cal[0]} x {mun[0]} -> Calculos[Casos]",
                   filtro=f"{mun[0]}[CodMun] = {MANIZALES}", consulta=q)


# Tableros por evento que se congelan: los que tienen Calendario/Fechas,
# Municipio[CodMun] y Calculos[Casos]. 365 no los tiene (su modelo es otro) y
# 549 filtra por municipio de RESIDENCIA (CodMunR): no empalman igual.
EVENTOS_TABLERO = [356, 300, 831, 875]


# Archivos de un solo ano (la tabla del 006 lleva el ano en el nombre): en enero vuelven a empezar y es normal
# que traigan menos filas que la descarga anterior. Los demas cubren todos los anos y no deben encoger.
DE_UN_ANO = {"rutinaria_manizales", "ira_995_rutinaria"}


def encogio(nombre, d, anterior):
    """Motivo si `d` trae menos filas que el mismo archivo de la descarga anterior; '' si no."""
    if anterior is None or not (anterior / f"{nombre}.csv").exists():
        return ""
    a = pd.read_csv(anterior / f"{nombre}.csv")
    if nombre in DE_UN_ANO and pd.to_numeric(d["anio"]).max() != a["anio"].max():
        return ""
    return f"{len(d)} filas contra {len(a)} de {anterior.name}" if len(d) < len(a) else ""


def congelar(rehacer=False):
    hoy = date.today().isoformat()
    destino = CARPETA / hoy
    if destino.exists() and not rehacer:
        sys.exit(f"{destino} ya existe: una descarga por dia (--rehacer para sustituirla).")
    anteriores = [c for c in sorted(CARPETA.glob("????-??-??")) if c.name < hoy]
    anterior = anteriores[-1] if anteriores else None
    try:
        tabs, origen = tableros(), "MenuReporteNivel2"
    except Exception as e:                         # el portal SIVIGILA se cae; el Power BI no
        print(f"  la lista de tableros del portal no responde ({e!r:.150}); se usan las claves guardadas")
        tabs, origen = tableros_guardados(), "claves de la ultima descarga"
    trabajos = [("rutinaria_manizales", lambda: rutinaria(tabs)),
                ("ira_995_rutinaria", lambda: ira_rutinaria(tabs)),
                ("ira_995_tablero", lambda: ira_tablero(tabs))]
    trabajos += [(f"evento_{e}", lambda e=e: por_evento(tabs, e)) for e in EVENTOS_TABLERO]
    tmp = CARPETA / f"_tmp_{hoy}"                  # se escribe aparte y solo se publica completo
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    meta = {"descargado": pd.Timestamp.now().isoformat(timespec="seconds"), "claves": origen, "archivos": {}}
    fallos = []
    for nombre, f in trabajos:
        try:
            d, m = f()
        except Exception as e:                     # un tablero caido no tumba los demas
            print(f"  {nombre}: FALLO {e!r}"[:300])
            meta["archivos"][f"{nombre}.csv"] = {"error": repr(e)[:500]}
            fallos.append(nombre)
            continue
        d = d.sort_values(list(d.columns[:2]) if nombre != "rutinaria_manizales" else ["cod_eve", "semana"])
        d.to_csv(tmp / f"{nombre}.csv", index=False)
        m.update(filas=len(d))
        meta["archivos"][f"{nombre}.csv"] = m
        anios = sorted(pd.to_numeric(d["anio"]).unique().tolist())
        print(f"  {nombre}: {len(d)} filas, anos {anios[0]}-{anios[-1]}, refresco del INS {m['refresco_ins']}")
        if motivo := encogio(nombre, d, anterior):
            print(f"  {nombre}: MENOS DATOS que la descarga anterior: {motivo}")
            meta["archivos"][f"{nombre}.csv"]["menos_datos"] = motivo
            fallos.append(nombre)
    (tmp / "metadatos.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    if fallos:
        parcial = CARPETA / "_parciales" / hoy
        shutil.rmtree(parcial, ignore_errors=True)
        parcial.parent.mkdir(parents=True, exist_ok=True)
        tmp.replace(parcial)
        sys.exit(f"descarga incompleta ({', '.join(fallos)}): guardada en {parcial}, no en {destino}")
    if destino.exists():                           # solo con --rehacer
        shutil.rmtree(destino)
    tmp.replace(destino)
    print(f"congelado en {destino}")
    return destino


def ultima():
    """Carpeta de la descarga mas reciente."""
    c = sorted(p for p in CARPETA.glob("????-??-??") if p.is_dir())
    if not c:
        raise FileNotFoundError(f"no hay descargas en {CARPETA}")
    return c[-1]


def rutinaria_largo(carpeta=None, eventos=None):
    """La tabla del 006 de una descarga -> el formato largo de vigilancia_sivigila_eventos.csv.gz.

    variable = casos_ocurrencia: por el empalme medido (VIGILANCIA.md), la semana
    del 006 se comporta como la columna SEMANA de los microdatos, no como la de
    notificacion. Se rellena con CERO cada semana sin casos hasta la ultima
    semana que trae la tabla, que es provisional (notificacion tardia).
    """
    carpeta = Path(carpeta) if carpeta else ultima()
    r = pd.read_csv(carpeta / "rutinaria_manizales.csv")
    ultima_semana = int(r["semana"].max())
    anio = int(r["anio"].max())
    eventos = sorted(eventos or r["cod_eve"].unique())
    idx = pd.MultiIndex.from_product([eventos, range(1, ultima_semana + 1)], names=["evento", "semana_epi"])
    w = (r[r["anio"] == anio].groupby(["cod_eve", "semana"])["casos"].sum()
         .rename_axis(["evento", "semana_epi"]).reindex(idx, fill_value=0).rename("valor").reset_index())
    w.insert(1, "anio", anio)
    w["fecha_inicio_semana"] = [inicio_semana(anio, s) for s in w["semana_epi"]]
    w["fecha_fin_semana"] = w["fecha_inicio_semana"] + timedelta(days=6)
    w["ambito"], w["variable"] = "manizales", "casos_ocurrencia"
    w["descarga"] = carpeta.name
    return w[["evento", "anio", "semana_epi", "fecha_inicio_semana", "fecha_fin_semana",
              "ambito", "variable", "valor", "descarga"]]


# ==========================================================
# PRINCIPAL
# ==========================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--esquema", metavar="PREFIJO", help="solo nombres de tablas y columnas de un tablero")
    ap.add_argument("--rehacer", action="store_true", help="sustituye la descarga de hoy")
    ap.add_argument("--empalme", action="store_true", help="2025 del tablero contra los microdatos")
    args = ap.parse_args()
    if args.empalme:
        import empalme
        empalme.main(ultima())
        return
    if args.esquema:
        tabs = tableros()
        titulo, k = clave(tabs, args.esquema)
        s = sesion(k)
        print(titulo, "| refresco del INS:", s["refresco_ins"])
        for t, d in esquema(s).items():
            print(f"  {t}: columnas {d['columnas']} | medidas {d['medidas']}")
        return
    congelar(args.rehacer)


if __name__ == "__main__":
    main()
