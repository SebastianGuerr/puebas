import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("20_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 20 — Regímenes y fenómenos: El Niño, La Niña, sismos, crisis de la red

## Qué pidió el propietario

«Marcaste la COVID, pero no las demás catástrofes y fenómenos: El Niño y La Niña, terremotos, epidemias…»

## Cómo se marcan sin sobreajustar (fila `regimenes` de `variables.csv`)

El cuaderno 16 mostró el límite: con 4 episodios de El Niño, un modelo no aprende el efecto; memoriza esos 4.
Por eso cada fenómeno entra como **estado que dura y se repite**, conocido el día de la predicción:

| Estado | Cómo se define | Fuente |
|---|---|---|
| **El Niño / La Niña** | ONI de dos meses antes ≥ +0,5 / ≤ −0,5 (la NOAA lo publica con retraso) | NOAA, capturado cada semana |
| **COVID** fuerte / parcial | 2020-03-15 a 2020-08-31 / hasta 2022-02-28 | fechas fijas |
| **Paro nacional 2021** | 2021-04-28 a 2021-06-15 | fechas fijas |
| **Sismo fuerte** | los 7 días siguientes a un sismo de M ≥ 4,5 a menos de 150 km | USGS (`calendarios/sismos_usgs.csv`) |
| **Desastre activo** | catálogo propio de Manizales | `desastres_manizales_2020_2026.csv` |
| **Crisis de la red** | peso de Nueva EPS en el triage de 28 días por debajo de su percentil 10 de 2022-2024 | triage del hospital |

**Exploración:** sobre las familias de enfermedad de la ciudad (2012-2024) y el triage total (2022-2024),
con mes fijo y **tendencia lineal en lugar de año fijo**: un El Niño dura un año, y el año fijo se lo comería.
""")
code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from matplotlib import pyplot as plt
import indices as ix
from desenlace import desenlace_semanal
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
R = ix.regimenes_diarios()
ESTADOS = ["el_nino", "la_nina", "covid_fuerte", "covid_parcial", "paro_nacional_2021", "sismo_fuerte_7d", "desastre_activo", "crisis_red"]
def episodios(s):
    s = s.fillna(0) > 0; return int((s & ~s.shift(fill_value=False)).sum())
tab = pd.DataFrame({e: {"episodios 2012-2024": episodios(R[e].loc["2012":"2024"]), "días 2012-2024": int(R[e].loc["2012":"2024"].sum()),
                        "episodios 2020-2024": episodios(R[e].loc["2020":"2024"]), "días 2025-2026": int(R[e].loc["2025":].sum())} for e in ESTADOS}).T
tab
""")
lec("conteo")

code(r"""
fig, axes = plt.subplots(3, 1, figsize=(15, 6.5), sharex=True, gridspec_kw={"height_ratios": [1.2, 1, 1.2]})
axes[0].fill_between(R.index, 0, R.oni, where=R.oni > 0, color=ROJO, alpha=.6, lw=0); axes[0].fill_between(R.index, 0, R.oni, where=R.oni < 0, color=AZUL, alpha=.6, lw=0)
axes[0].axhline(.5, color=MUDO, ls=":", lw=.8); axes[0].axhline(-.5, color=MUDO, ls=":", lw=.8); axes[0].set_ylabel("ONI (2 meses antes)"); axes[0].set_title("El Niño (rojo) y La Niña (azul)")
for i, (e, c) in enumerate([("covid_fuerte", MUDO), ("covid_parcial", "#c9c8c4"), ("paro_nacional_2021", NARANJA), ("sismo_fuerte_7d", VIOLETA), ("desastre_activo", AMARILLO), ("crisis_red", MAGENTA)]):
    axes[1].fill_between(R.index, i, i + R[e].fillna(0) * .8, color=c, lw=0, label=e.replace("_", " "))
axes[1].set_yticks([]); axes[1].legend(ncol=6, fontsize=8, loc="upper left"); axes[1].set_title("Estados puntuales")
t = pd.read_parquet(RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia)).set_index("dia").triages
axes[2].plot(t.index, t.rolling(28, center=True, min_periods=14).mean(), color=TINTA, lw=1.4); axes[2].set_ylabel("triage, media 28 d")
axes[2].set_xlim(pd.Timestamp("2012-01-01"), R.index[-1]); plt.tight_layout(); plt.show()
""")

md(r"""
---
# 1. ¿Mueven los regímenes a las enfermedades de la ciudad? (2012-2024)

Efecto de estar en el estado sobre el índice de cada familia, en desviaciones típicas del índice. ● = sobrevive
a BH (q < 0,10).
""")
code(r"""
FAM = ix.familias_enfermedad().loc["2012":ix.REF_FIN]
W = R[ESTADOS].resample("W-SAT").mean(); W.index -= pd.Timedelta(days=6)
def efecto(y, X):
    filas = []; idx = y.dropna().index
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    tend = pd.Series(np.arange(len(idx)) / 52, index=idx, name="tendencia")
    for c in X:
        D = pd.concat([y.rename("y"), X[c].rename("x"), mes, tend], axis=1).loc[idx].dropna()
        if D.x.std() == 0 or (D.x > 0).sum() < 4: continue
        r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
        filas.append({"estado": c, "efecto": r.params["x"], "p": r.pvalues["x"], "semanas en el estado": int((D.x > 0).sum())})
    T = pd.DataFrame(filas)
    if len(T): T["q"] = multipletests(T.p, method="fdr_bh")[1]
    return T
RF = {fam: efecto(FAM[fam], W.drop(columns=["crisis_red"])) for fam in FAM}
M = pd.DataFrame({fam: T.set_index("estado")["efecto"] for fam, T in RF.items()}).round(2)
Q = pd.DataFrame({fam: T.set_index("estado")["q"] for fam, T in RF.items()})
M.astype(str).where(Q >= .10, M.astype(str) + " ●")
""")
lec("ciudad")

md(r"""
---
# 2. ¿Y al triage del hospital? (2022-2024)

Desenlace: triage semanal sin calendario ni escalones de la red. El efecto se expresa en % del triage.
""")
code(r"""
y = desenlace_semanal().y.loc[:ix.REF_FIN]
TH = efecto(y, W)
TH.assign(**{"efecto %": lambda d: 100 * (np.exp(d["efecto"]) - 1)})[["estado", "efecto %", "p", "q", "semanas en el estado"]].round(3)
""")
lec("hospital")

md(r"""
---
# 3. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "20_regimenes_y_fenomenos.ipynb")
print("ok", len(C))
