"""Descarga AGREGADA de la tabla 'Rutinaria 2026' del tablero publico INS '006 Vigilancia Rutinaria'.
Tabla ya agregada por el INS: evento x semana x municipio de procedencia -> conteo. Sin datos de persona.
Uso: python pbi_rutinaria.py [MUNICIPIO]   (filtra por nmun_proce; por defecto MANIZALES)"""
import sys, json, csv, requests
try:
    import truststore; truststore.inject_into_ssl()
except ImportError: pass
C = "https://wabi-south-central-us-api.analysis.windows.net"
KEY = "526982b9-fe09-4db3-adcc-92383aecbcef"
T = "Rutinaria 2026"
def col(p): return {"Column": {"Expression": {"SourceRef": {"Source": "t"}}, "Property": p}}
def consulta(select, where, n=30000):
    h = {"X-PowerBI-ResourceKey": KEY, "User-Agent": "Mozilla/5.0"}
    mae = requests.get(f"{C}/public/reports/{KEY}/modelsAndExploration?preferReadOnlySession=true", headers=h, timeout=60).json()
    m = mae["models"][0]
    q = {"Version": 2, "From": [{"Name": "t", "Entity": T, "Type": 0}], "Select": select, "Where": where}
    body = {"version": "1.0.0", "queries": [{"Query": {"Commands": [{"SemanticQueryDataShapeCommand": {"Query": q,
            "Binding": {"Primary": {"Groupings": [{"Projections": list(range(len(select)))}]},
                        "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": n}}}, "Version": 1}}}]},
            "QueryId": "", "ApplicationContext": {"DatasetId": m["dbName"], "Sources": [{"ReportId": mae["exploration"]["report"]["objectId"]}]}}],
            "cancelQueries": [], "modelId": m["id"]}
    r = requests.post(f"{C}/public/reports/querydata?synchronous=true", headers=h, json=body, timeout=180); r.raise_for_status()
    d = r.json()["results"][0]["result"]["data"]; ds = d["dsr"]["DS"][0]
    dicts = ds.get("ValueDicts", {}); nsel = len(select); prev = [None] * nsel; filas = []
    for fila in ds["PH"][0].get("DM0", []):
        vals = iter(fila.get("C", [])); R = fila.get("R", 0); Ø = fila.get("Ø", 0); out = []
        for i in range(nsel):
            if (R >> i) & 1: out.append(prev[i])
            elif (Ø >> i) & 1: out.append(None)
            else: out.append(next(vals, None))
        # resolver diccionarios de valores
        for i, s in enumerate(fila.get("S", []) if False else []): pass
        prev = out; filas.append(out)
    # los diccionarios: el primer registro trae "S" con DN por columna
    dn = {}
    s0 = ds["PH"][0]["DM0"][0].get("S", []) if ds["PH"][0].get("DM0") else []
    for i, s in enumerate(s0):
        if "DN" in s: dn[i] = dicts[s["DN"]]
    for f in filas:
        for i, D in dn.items():
            if isinstance(f[i], int): f[i] = D[f[i]]
    return m["LastRefreshTime"], filas
if __name__ == "__main__":
    mun = sys.argv[1] if len(sys.argv) > 1 else "MANIZALES"
    sel = [dict(col("año"), Name="anio"), dict(col("cod_eve"), Name="cod_eve"), dict(col("nom_eve"), Name="nom_eve"),
           dict(col("semana"), Name="semana"),
           {"Aggregation": {"Expression": col("conteo"), "Function": 0}, "Name": "casos"}]
    where = [{"Condition": {"In": {"Expressions": [col("nmun_proce")], "Values": [[{"Literal": {"Value": f"'{mun}'"}}]]}}}]
    ref, filas = consulta(sel, where)
    print("refresco", ref, "filas", len(filas))
    with open(f"rutinaria_2026_{mun.lower()}.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(["anio", "cod_eve", "nom_eve", "semana", "casos"]); w.writerows(filas)
