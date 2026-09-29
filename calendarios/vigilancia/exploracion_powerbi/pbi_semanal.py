"""Consulta AGREGADA (casos por año y semana) a un tablero publico Power BI del INS.
Solo pide la medida 'Casos' agrupada por Año/Semana y filtrada por municipio. Nunca columnas de persona."""
import json, sys, requests
try:
    import truststore; truststore.inject_into_ssl()
except ImportError:
    pass
CLUSTER = "https://wabi-south-central-us-api.analysis.windows.net"
def semanal(key, cod_mun="17001", campo_mun="CodMun", anio=None):
    h = {"X-PowerBI-ResourceKey": key, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    mae = requests.get(f"{CLUSTER}/public/reports/{key}/modelsAndExploration?preferReadOnlySession=true", headers=h, timeout=60).json()
    model = mae["models"][0]; rep = mae["exploration"]["report"]["objectId"]
    where = [{"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "m"}}, "Property": campo_mun}}],
                                    "Values": [[{"Literal": {"Value": f"'{cod_mun}'"}}]]}}}]
    if anio:
        where.append({"Condition": {"In": {"Expressions": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "Año"}}],
                                            "Values": [[{"Literal": {"Value": f"{anio}L"}}]]}}})
    q = {"Version": 2,
         "From": [{"Name": "c", "Entity": "Calendario", "Type": 0}, {"Name": "k", "Entity": "Calculos", "Type": 0}, {"Name": "m", "Entity": "Municipio", "Type": 0}],
         "Select": [{"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "Año"}, "Name": "anio"},
                    {"Column": {"Expression": {"SourceRef": {"Source": "c"}}, "Property": "Semana"}, "Name": "semana"},
                    {"Measure": {"Expression": {"SourceRef": {"Source": "k"}}, "Property": "Casos"}, "Name": "casos"}],
         "Where": where}
    body = {"version": "1.0.0", "queries": [{"Query": {"Commands": [{"SemanticQueryDataShapeCommand": {"Query": q,
             "Binding": {"Primary": {"Groupings": [{"Projections": [0, 1, 2]}]}, "DataReduction": {"DataVolume": 4, "Primary": {"Window": {"Count": 2000}}}, "Version": 1}}}]},
             "QueryId": "", "ApplicationContext": {"DatasetId": model["dbName"], "Sources": [{"ReportId": rep}]}}],
            "cancelQueries": [], "modelId": model["id"]}
    r = requests.post(f"{CLUSTER}/public/reports/querydata?synchronous=true", headers=h, json=body, timeout=120)
    r.raise_for_status(); d = r.json()
    ds = d["results"][0]["result"]["data"]["dsr"]["DS"][0]
    filas = []; prev = [None, None, None]
    for fila in ds["PH"][0].get("DM0", []):
        vals = fila.get("C", []); R = fila.get("R", 0); out = []; it = iter(vals)
        for i in range(3):
            out.append(prev[i] if (R >> i) & 1 else next(it, None))
        prev = out; filas.append(tuple(out))
    return model["LastRefreshTime"], filas
if __name__ == "__main__":
    key = sys.argv[1]; cod = sys.argv[2] if len(sys.argv) > 2 else "17001"; campo = sys.argv[3] if len(sys.argv) > 3 else "CodMun"
    ref, filas = semanal(key, cod, campo)
    print("refresco:", ref, "filas:", len(filas))
    por_anio = {}
    for a, s, c in filas: por_anio.setdefault(a, []).append((s, c))
    for a in sorted(por_anio, key=lambda x: (x is None, x)):
        v = sorted(por_anio[a], key=lambda x: (x[0] is None, x[0]))
        print(a, "semanas:", len(v), "total:", sum(c or 0 for _, c in v), "primeras:", v[:4], "ultimas:", v[-3:])
