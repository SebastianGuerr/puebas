# Aplica los filtros de produccion (posprocesar de v1.7) a las salidas YA guardadas en modo
# solo. Deterministas: no llaman al modelo. La segunda pasada si lo necesita, asi que solo se
# CUENTA en cuantas notas se dispararia. Escribe comparacion/filtradas.csv (sin notas crudas).
import glob
import json
import os
import sys
from pathlib import Path
sys.path.insert(0, ".")
import pandas as pd
from NLP import banco, fidelidad, rutas
# Todo el material de la competencia (muestras, notas enmascaradas, salidas) vive en
# NLP/salidas/competencia/, que git ignora: lleva texto clinico. Se cambia con COMPETENCIA=<ruta>.
AQUI = Path(os.environ.get("COMPETENCIA", rutas.SALIDAS / "competencia"))
AQUI.mkdir(parents=True, exist_ok=True)
(AQUI / "comparacion").mkdir(exist_ok=True)
banco._cargar_prompt("NLP/prompts/v1_7.py")
pos = banco._MODULO.posprocesar
notas = pd.read_csv(AQUI / "muestra64.csv", encoding="utf-8-sig", dtype=str).fillna("").set_index("OID")["frase_original"]
filas = []
for p in sorted(glob.glob(str(AQUI / "comparacion" / "*.jsonl"))):
    nombre = Path(p).stem
    if nombre.startswith("descartado") or "_reps" in nombre:
        continue
    for linea in open(p, encoding="utf-8"):
        r = json.loads(linea)
        o = notas[r["OID"]]
        f = pos(o, r["salida"]) if r["salida"] else r["salida"]
        filas.append({"archivo": nombre, "modelo": r["modelo"], "OID": r["OID"], "tipo": r["tipo"],
                      "salida_solo": r["salida"], "salida_filtrada": f, "cambia": f != r["salida"],
                      "segunda_pasada": fidelidad.necesita_segunda_pasada(o, f)})
t = pd.DataFrame(filas)
t.to_csv(AQUI / "comparacion" / "filtradas.csv", index=False, encoding="utf-8-sig")
print(t.groupby("archivo").agg(notas=("OID", "size"), cambian=("cambia", "sum"),
                               segunda_pasada=("segunda_pasada", "sum")).to_string())
