import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("21_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 21 — El jerárquico por tipo de consulta: llevar cada contexto a la parte donde actúa

## Por qué

Los cuadernos 17, 19 y 20 repiten lo mismo. El clima, las enfermedades de la ciudad y El Niño **sí mueven
algo**: la IRA de la ciudad un 6-7 %, la diarrea un 16 %. Pero al **triage total** llegan diluidos, en un 1-3 %.
`CLAUDE.md` lo anticipaba: si lo respiratorio es el 10 % del total y sube un 30 %, el total sube un 3 %,
invisible bajo un ruido del 10-12 %.

**La salida es no mirar el total sino sus partes**, y darle a cada parte el contexto que le toca.

## Qué particiones existen (fila `jerarquico_tipo` de `variables.csv`)

| Partición | Cobertura | Fuente |
|---|---|---|
| **Bandas de edad** (0-4, 5-14, 15-44, 45-64, 65+) | 100 %, desde 2020 | `triage_edad.parquet` |
| **Obstétrico frente al resto** | 100 %, desde 2020 | `triage_nivel.parquet` (niveles -G) |
| Diagnósticos | **41 %** (son ingresos) | `perfil_dx_diario` |
| Motivo de consulta (NLP) | 2025-2026, sin procesar | `NLP/` |

**El cruce edad × obstétrico no existe todavía.** Haría falta una extracción agregada nueva, que solo puede
hacer el propietario.
""")
code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from matplotlib import pyplot as plt
import indices as ix
import desenlace as de
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
dias = pd.date_range("2020-01-01", "2026-09-20")
ed = pd.read_parquet(RAIZ / "salidas/triage_edad.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
E = ed.pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").reindex(dias).fillna(0)
nv = pd.read_parquet(RAIZ / "salidas/triage_nivel.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
obst = nv[nv.nivel.str.endswith("-G")].groupby("dia").n.sum().reindex(dias).fillna(0)
tot = nv.groupby("dia").n.sum().reindex(dias).fillna(0)
P = pd.DataFrame({"edad 0-4": E["0-4"], "edad 5-14": E["5-14"], "edad 15-44": E["15-44"], "edad 45-64": E["45-64"], "edad 65+": E["65-+"],
                  "obstétrico": obst, "no obstétrico": tot - obst, "TOTAL": tot})
P.loc["2024-03-19":"2024-03-21"] = np.nan
peso = (P.loc["2022":"2024"].mean() / P.loc["2022":"2024", "TOTAL"].mean() * 100).round(1)
print("Peso de cada parte en 2022-2024 (%):"); peso.drop("TOTAL")
""")

md(r"""
---
# 1. Cada parte tiene su propia estación
""")
code(r"""
x = np.log(P.loc["2022":"2025"].resample("MS").mean())
forma = (np.exp((x - x.groupby(x.index.year).transform("mean")).groupby(x.index.month).mean()) - 1) * 100
fig, ax = plt.subplots(figsize=(12, 4.2))
im = ax.imshow(forma.T.values, cmap="RdBu_r", vmin=-30, vmax=30, aspect="auto")
ax.set_xticks(range(12), MESES); ax.set_yticks(range(forma.shape[1]), forma.columns)
for (i, j), v in np.ndenumerate(forma.T.values): ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=8)
plt.colorbar(im, ax=ax, label="% frente a la media del año"); ax.set_title("La estación de cada parte del triage (2022-2025)")
plt.tight_layout(); plt.show()
amp = (forma.max() - forma.min()).round(1).rename("amplitud de la estación (puntos %)"); amp.to_frame()
""")
lec("estacion")

md(r"""
---
# 2. El contexto externo, parte por parte (2022-03 a 2024-12)

Cada parte se lleva a su residuo semanal: sin calendario, sin el nivel del año y sin los escalones de la red,
igual que `desenlace.py`, conservando la estación. Contra cada parte se barren:
- las 6 familias de enfermedad, con rezago de 0 a 2 semanas;
- los 7 índices de clima y 2 rachas, con rezago de 0 a 4;
- El Niño y La Niña.

En total son 77 pruebas por parte, con mes fijo, errores HAC y BH por parte.
""")
code(r"""
cal = (pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
         .reindex(dias)[de.CAL].apply(pd.to_numeric, errors="coerce").fillna(0))
completas = de._semana(P["TOTAL"].notna().astype(int)) == 7
cal_w = de._semana(cal).loc[de.INICIO:"2024-12-29"]
RESID = {}
for c in P:
    w = de._semana(P[c]).where(completas).loc[de.INICIO:"2024-12-29"]
    RESID[c] = de._residuo(w, cal_w)
RESID = pd.DataFrame(RESID)
FAM = ix.familias_enfermedad(); IC = ix.indices_clima()
REG = ix.regimenes_diarios()[["el_nino", "la_nina"]].resample("W-SAT").mean(); REG.index -= pd.Timedelta(days=6)
X = {}
for f in FAM:
    for L in range(3): X[f"{f} (−{L} sem)"] = FAM[f].shift(L)
for c in IC:
    for L in range(5): X[f"{c} (−{L} sem)"] = IC[c].shift(L)
for c in REG: X[c] = REG[c]
X = pd.DataFrame(X)
def barrido(y):
    idx = y.dropna().index; filas = []
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    for c in X:
        xs = (X[c] - X[c].loc[:"2024"].mean()) / X[c].loc[:"2024"].std()
        D = pd.concat([y.rename("y"), xs.rename("x"), mes], axis=1).loc[idx].dropna()
        if len(D) < 60 or D.x.std() == 0: continue
        r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        filas.append({"variable": c, "efecto %": 100 * (np.exp(r.params["x"]) - 1), "p": r.pvalues["x"]})
    T = pd.DataFrame(filas); T["q"] = multipletests(T.p, method="fdr_bh")[1]; return T
RB = {c: barrido(RESID[c]) for c in RESID}
res = pd.DataFrame({c: {"pruebas": len(T), "p < 0,05": int((T.p < .05).sum()), "sobreviven BH": int((T.q < .10).sum()),
                        "mayor efecto que sobrevive %": round(T.loc[T.q < .10, "efecto %"].abs().max(), 1) if (T.q < .10).any() else np.nan,
                        "ruido semanal (desv. del residuo) %": round(100 * RESID[c].std(), 1)} for c, T in RB.items()}).T
res
""")
lec("barrido")

code(r"""
filas = []
for c, T in RB.items():
    for _, r in T[T.q < .10].sort_values("p").head(6).iterrows():
        filas.append({"parte": c, "variable": r.variable, "efecto %": round(r["efecto %"], 2), "q": round(r.q, 3)})
pd.DataFrame(filas) if filas else "nada sobrevive"
""")
lec("top")

md(r"""
---
# 3. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "21_el_jerarquico_por_tipo.ipynb")
print("ok", len(C))
