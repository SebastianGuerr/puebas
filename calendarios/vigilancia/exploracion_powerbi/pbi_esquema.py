"""Imprime SOLO nombres de tablas y columnas (metadatos) de un tablero publico Power BI. No consulta datos."""
import sys, json, requests
try:
    import truststore; truststore.inject_into_ssl()
except ImportError: pass
C = "https://wabi-south-central-us-api.analysis.windows.net"
key = sys.argv[1]; h = {"X-PowerBI-ResourceKey": key, "User-Agent": "Mozilla/5.0"}
mae = requests.get(f"{C}/public/reports/{key}/modelsAndExploration?preferReadOnlySession=true", headers=h, timeout=60).json()
m = mae["models"][0]
cs = requests.post(f"{C}/public/reports/conceptualschema", headers=h, json={"modelIds": [m["id"]], "userPreferredLocale": "es-ES"}, timeout=60).json()
print(m["displayName"], "refresco", m["LastRefreshTime"], "paginas", [s["displayName"] for s in mae["exploration"]["sections"]])
for s in cs["schemas"]:
    for e in s["schema"]["Entities"]:
        if e.get("Hidden") or e["Name"].startswith(("LocalDateTable", "DateTableTemplate")): continue
        props = [p["Name"] for p in e.get("Properties", []) if not p.get("Hidden")]
        print(" ", e["Name"], len(props), props[:25])
