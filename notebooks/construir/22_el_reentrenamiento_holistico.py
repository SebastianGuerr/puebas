import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("22_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 22 — El reentrenamiento holístico: elegir con 2025, probar una vez en 2026

## Qué cambia frente a los cuadernos 15 y 16

El propietario pidió entrenar con **todo el contexto**, no con una sola variable, y sin «darle las respuestas
de 2026». Los cuadernos 17 a 21 construyeron ese contexto, y este cuaderno lo pone a prueba con un protocolo
que no deja elegir mirando la prueba (fila `reentrenamiento_holistico` de `variables.csv`, fijada antes de
correr).

| Etapa | Periodo | Qué se hace |
|---|---|---|
| Entrenar | desde 2020 (COVID marcada) | cada modelo se reentrena cada 7 días con todo lo anterior |
| **Elegir** | **2025** | se comparan tres diseños con una regla escrita antes de mirar |
| **Probar** | **2026, una sola vez** | solo el elegido; no se cambia nada después |
| Prospectiva | octubre-diciembre de 2026 | la hipótesis de El Niño (fila `hipotesis_el_nino_2026`) |

## Los tres diseños

| | Qué es |
|---|---|
| **C0** | La combinación SARIMAX + LightGBM **sin contexto**: calendario, estación, nivel y memoria. Es la de los cuadernos 15 y 16 |
| **C1** | La misma combinación **con el contexto holístico H** |
| **C2** | **Jerárquico por bandas de edad**: LightGBM con H en cada banda (0-4, 5-14, 15-44, 45-64, 65+), y el total como suma por cópula |

## El contexto H: 24 variables, todas conocidas el día de la predicción

| Capa | Variables | De dónde |
|---|---|---|
| Clima | 4 índices de estado, 3 de cambio brusco, racha seca y días desde la última semana muy lluviosa | cuaderno 17 |
| Salud pública | 5 familias: respiratoria, violencias, salud mental, materno-perinatal, inmunoprevenibles (la última semana completa) | cuaderno 19 + Power BI para 2026 |
| Red de salud | peso de Nueva EPS y SURA, cambios de 28 días, Herfindahl, resolución de la Supersalud | cuaderno 18 |
| Regímenes | ONI, El Niño, La Niña, sismo fuerte | cuaderno 20 |

**Quedan fuera** la familia digestiva y la IRAG hospitalizada: no existen al predecir en 2026.
""")
code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from matplotlib import pyplot as plt
import pronostico as pr, combinar as cb
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
NOMBRE = {"C0": "C0 · combinación sin contexto", "C1": "C1 · combinación con H", "C2": "C2 · jerárquico por edad con H"}
def leer(exp, modelos): P, _ = pr.leer(modelos, exp=exp); return P
def disenos(suf):
    pr.usar("e1"); y_tot, _ = pr.cargar()
    c0 = cb.promedio([leer("e1" + ("_2025" if suf else ""), ["sarimax"]), leer("e1" + ("_2025" if suf else ""), ["lightgbm"])], "C0") if suf else None
    out = {}
    if suf:
        out["C0"] = c0
    else:
        P0 = leer("e1", ["sarimax", "lightgbm"]); out["C0"] = cb.promedio([P0[P0.modelo == "sarimax"], P0[P0.modelo == "lightgbm"]], "C0")
    try: out["C1"] = cb.promedio([leer(f"h{suf}", ["sarimax"]), leer(f"h{suf}", ["lightgbm"])], "C1")
    except Exception as e: print("C1 sin datos:", repr(e)[:80])
    try: out["C2"] = cb.jerarquico_bandas({b: leer(f"hb{k}{suf}", ["lightgbm"]) for k, b in pr.BANDAS.items()}, y_tot, "C2")
    except Exception as e: print("C2 sin datos:", repr(e)[:80])
    return out
""")

md(r"""
---
# 1. Elegir con 2025

Los tres diseños con origen rodante sobre 2025, que no se usó para nada antes. También se muestran los modelos
sueltos, como referencia.
""")
code(r"""
D25 = disenos("_2025")
sueltos = []
for exp, ms in [("e1_2025", ["sarimax", "lightgbm"]), ("h_2025", ["sarimax", "lightgbm"])]:
    try:
        P = leer(exp, ms); sueltos.append(P.assign(modelo=P.modelo + " · " + ("sin contexto" if exp.startswith("e1") else "con H")))
    except Exception: pass
T25 = cb.tabla(pd.concat(list(D25.values()) + sueltos))
ELEGIDO = cb.elegir(T25, ["C0", "C1", "C2"])
print(f"Diseño elegido con 2025 por la regla preregistrada: {ELEGIDO} — {NOMBRE[ELEGIDO]}")
T25.sort_values("criterio (promedio BSS)", ascending=False).round(1)
""")
lec("eleccion")

md(r"""
---
# 2. Probar en 2026, una sola vez

Solo el diseño elegido se corrió en 2026, y se compara con C0, la combinación sin contexto de los cuadernos 15
y 16. La diferencia se prueba con remuestreo por bloques de 7 orígenes.
""")
code(r"""
D26 = disenos("")
T26 = cb.tabla(pd.concat([D26[k] for k in D26 if k in ("C0", ELEGIDO)]))
display(T26.round(1))
if ELEGIDO != "C0" and ELEGIDO in D26:
    _, U = pr.leer(["control"], exp="e0")
    P2, _ = pr.metricas(pd.concat([D26["C0"], D26[ELEGIDO]]), U)
    P2["acierta"] = ((P2.p_sobre > .5) == (P2.sobre == 1)).astype(float) * 100
    P2["brier x1000"] = (P2.p_sobre - P2.sobre) ** 2 * 1000; P2["error %"] = P2.ape * 100
    rng = np.random.default_rng(0); filas = []
    for sub, D in [("todo 2026", P2), ("abril-junio", P2[P2.fecha.dt.month.isin([4, 5, 6])])]:
        for col, mayor in [("acierta", True), ("brier x1000", False), ("error %", False)]:
            w = D.pivot_table(index=["origen", "h"], columns="modelo", values=col).dropna()
            d = (w[ELEGIDO] - w["C0"]).groupby(level=0).mean(); g = np.arange(len(d)) // 7; G = [np.where(g == x)[0] for x in np.unique(g)]
            B = np.array([d.values[np.concatenate([G[j] for j in rng.integers(0, len(G), len(G))])].mean() for _ in range(2000)])
            lo, hi = np.percentile(B, [2.5, 97.5])
            filas.append({"periodo": sub, "criterio": col, f"{ELEGIDO} − C0": round(d.mean(), 2), "IC 95 %": f"[{lo:.2f}, {hi:.2f}]",
                          "resultado": "empate" if lo <= 0 <= hi else (f"gana {ELEGIDO}" if (d.mean() > 0) == mayor else "gana C0")})
    display(pd.DataFrame(filas))
""")
lec("prueba")

md(r"""
---
# 3. Qué usa el modelo: el peso de cada capa del contexto

LightGBM con H, entrenado hasta el 2025-12-30 (sin 2026), mediana a 1 día: qué parte de su capacidad de separar
días sale de cada capa.
""")
code(r"""
import lightgbm as lgb, re
pr.usar("h"); y, cal = pr.cargar(); o = pd.Timestamp("2025-12-30")
ctx = tuple(c.reindex(y.index) for c in pr.contexto_exp(cal.index))
X = pr.rasgos(y, cal.reindex(y.index), 1, ctx).loc[:o]; yy = y.loc[:o]
ok = X.notna().all(axis=1) & yy.notna(); X, yy = X[ok], yy[ok]; X = X.loc[:, X.std() > 0]
m = lgb.LGBMRegressor(objective="quantile", alpha=.5, **pr.LightGBM.PARAM).fit(X, np.log(yy))
g = pd.Series(m.booster_.feature_importance("gain"), index=X.columns)
def capa(c):
    if c.startswith("ext_h_fam_"): return "salud pública"
    if c.startswith(("ext_h_peso", "ext_h_cambio_nueva", "ext_h_cambio_resto", "ext_h_herf", "ext_h_resol")): return "red de salud"
    if c.startswith(("ext_h_estado", "ext_h_cambio", "ext_h_racha", "ext_h_dias")): return "clima"
    if c.startswith(("ext_h_oni", "ext_h_el_", "ext_h_la_", "ext_h_sismo")): return "regímenes"
    return pr.capas([c])[c]
cap = pd.Series({c: capa(c) for c in X.columns})
pesos = (100 * g.groupby(cap).sum() / g.sum()).sort_values(ascending=False).round(1)
display(pesos.to_frame("% de la ganancia"))
print("Las 10 variables externas más usadas:"); print((100 * g[[c for c in g.index if c.startswith("ext_h_")]] / g.sum()).sort_values(ascending=False).head(10).round(2).to_string())
""")
lec("capas")

md(r"""
---
# 4. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "22_el_reentrenamiento_holistico.ipynb")
print("ok", len(C))
