"""
Empalme: lo que dicen los tableros Power BI del INS contra lo que dicen los microdatos.

    python calendarios/vigilancia/powerbi.py --empalme      (usa la descarga mas reciente)
    python calendarios/vigilancia/empalme.py [CARPETA]

Solo lee archivos ya agregados: la descarga congelada de powerbi/AAAA-MM-DD/ y
las salidas vigilancia_sivigila_eventos.csv.gz (eventos individuales) y
vigilancia_sivigila.csv.gz (995). No consulta la red. La lectura de los
numeros esta en calendarios/docs/VIGILANCIA.md.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

AQUI = Path(__file__).resolve().parent
EVENTOS = AQUI.parent / "vigilancia_sivigila_eventos.csv.gz"
COLECTIVOS = AQUI.parent / "vigilancia_sivigila.csv.gz"


def comparar_semanas(a, b):
    """Dos series semanales (indice = semana) -> metricas de acuerdo."""
    j = pd.concat([a.rename("pbi"), b.rename("micro")], axis=1).fillna(0)
    d = j["pbi"] - j["micro"]
    return {"semanas": len(j), "iguales": int((d == 0).sum()), "dif_abs_media": round(d.abs().mean(), 2),
            "dif_max": int(d.abs().max()), "r": round(j["pbi"].corr(j["micro"]), 3)}


def por_evento(carpeta):
    micro = pd.read_csv(EVENTOS)
    micro = micro[micro["ambito"] == "manizales"]
    filas, semanal = [], []
    for f in sorted(carpeta.glob("evento_*.csv")):
        e = int(f.stem.split("_")[1])
        pbi = pd.read_csv(f)
        m = micro[micro["evento"] == e]
        if m.empty:
            print(f"  {e}: sin microdatos integrados")
            continue
        for anio in sorted(set(pbi["anio"]) & set(m["anio"])):
            p = pbi[pbi["anio"] == anio].set_index("semana")["casos"]
            fila = {"evento": e, "anio": anio, "tablero": int(p.sum())}
            for var in ("casos_ocurrencia", "casos_residencia", "casos_notificacion"):
                fila[var.replace("casos_", "micro_")] = int(m[(m["anio"] == anio) & (m["variable"] == var)]["valor"].sum())
            fila["dif_%_ocurrencia"] = round(100 * (fila["tablero"] / fila["micro_ocurrencia"] - 1), 1)
            filas.append(fila)
            if anio == 2025:
                o = m[(m["anio"] == anio) & (m["variable"] == "casos_ocurrencia")].set_index("semana_epi")["valor"]
                semanal.append({"evento": e, **comparar_semanas(p, o)})
    print("\n=== Tableros por evento contra microdatos, Manizales, casos por ano ===")
    print(pd.DataFrame(filas).to_string(index=False))
    print("\n=== 2025, semana a semana (tablero contra microdatos por ocurrencia) ===")
    print(pd.DataFrame(semanal).to_string(index=False))


def ira(carpeta):
    t = pd.read_csv(carpeta / "ira_995_tablero.csv")
    c = pd.read_csv(COLECTIVOS)
    c = c[(c["evento"] == 995) & (c["ambito"] == "manizales")
          & c["variable"].isin(["consultas_ira_total", "consultas_todas_causas_total"])]
    m = c.pivot_table(index=["anio", "semana_epi"], columns="variable", values="valor")
    filas = []
    for anio in sorted(set(t["anio"]) & set(m.index.get_level_values(0))):
        tt, mm = t[t["anio"] == anio], m.loc[anio]
        filas.append({"anio": anio,
                      "ira_tablero": int(tt["grup_total"].sum()), "ira_micro": int(mm["consultas_ira_total"].sum()),
                      "todas_tablero": int(tt["Tot_tot"].sum()),
                      "todas_micro": int(mm["consultas_todas_causas_total"].sum())})
    f = pd.DataFrame(filas)
    f["dif_%_ira"] = (100 * (f["ira_tablero"] / f["ira_micro"] - 1)).round(1)
    f["dif_%_todas"] = (100 * (f["todas_tablero"] / f["todas_micro"] - 1)).round(1)
    print("\n=== 995: tablero IRA contra microdatos, Manizales ===")
    print(f.to_string(index=False))
    tt = t[t["anio"] == 2025].set_index("semana")
    mm = m.loc[2025]
    print("2025 semana a semana, IRA:", comparar_semanas(tt["grup_total"], mm["consultas_ira_total"]))
    print("2025 semana a semana, todas las causas:", comparar_semanas(tt["Tot_tot"], mm["consultas_todas_causas_total"]))
    # 2026: las dos vias del INS (tablero 995 y tabla del 006) entre si.
    r = pd.read_csv(carpeta / "ira_995_rutinaria.csv").set_index("semana")
    t26 = t[t["anio"] == 2026].set_index("semana")
    print("2026, tabla 995 del 006 contra tablero 995 -> IRA:",
          comparar_semanas(r["consultas_ira"], t26["grup_total"]),
          "| todas las causas:", comparar_semanas(r["consultas_todas_causas"], t26["Tot_tot"]))
    print(f"   totales 2026: 006 IRA {int(r['consultas_ira'].sum())}, tablero IRA {int(t26['grup_total'].sum())}; "
          f"006 todas {int(r['consultas_todas_causas'].sum())}, tablero todas {int(t26['Tot_tot'].sum())}")


def rutinaria(carpeta):
    r = pd.read_csv(carpeta / "rutinaria_manizales.csv")
    print("\n=== 006, 2026: eventos de Manizales ===")
    g = r.groupby(["cod_eve", "nom_eve"]).agg(semanas=("semana", "nunique"), ultima=("semana", "max"),
                                              casos=("casos", "sum")).reset_index()
    g["media_semanal"] = (g["casos"] / r["semana"].max()).round(2)
    g["nom_eve"] = g["nom_eve"].str[:50]
    print(g.sort_values("casos", ascending=False).to_string(index=False))
    print("\n=== 2026: tabla del 006 contra el tablero de cada evento ===")
    for f in sorted(carpeta.glob("evento_*.csv")):
        e = int(f.stem.split("_")[1])
        p = pd.read_csv(f)
        p = p[p["anio"] == 2026].set_index("semana")["casos"]
        a = r[r["cod_eve"] == e].set_index("semana")["casos"]
        print(f"  {e}: 006 {int(a.sum())} / tablero {int(p.sum())}, ultima semana 006 {a.index.max()} "
              f"tablero {p.index.max()}; {comparar_semanas(a, p)}")


def main(carpeta):
    carpeta = Path(carpeta)
    print(f"descarga: {carpeta}")
    pd.set_option("display.width", 200)
    por_evento(carpeta)
    ira(carpeta)
    rutinaria(carpeta)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        sys.path.insert(0, str(AQUI))
        import powerbi
        main(powerbi.ultima())
