import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("19_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 19 — Las familias de enfermedad: no solo IRA

## Qué pidió el propietario

«No es como que a la gente de Manizales solo le den problemas respiratorios.» Un repertorio de, al menos, las
enfermedades más comunes, cruzado con el clima y las temporadas, para una predicción escalable.

## Qué se hizo (fila `familias_enfermedad` de `variables.csv`, fijada antes de mirar)

Seis familias, armadas con las series semanales de Manizales en el SIVIGILA:

| Familia | Series | ¿Hay dato de 2026 al predecir? |
|---|---|---|
| **Respiratoria** | IRA total, IRA 0-4, IRA 60+, hospitalizaciones por IRAG | sí (Power BI 995, ~1 semana) |
| **Digestiva** | EDA total, EDA 0-4 | **no**: solo microdatos, ~8 meses |
| **Violencias y agresiones** | violencia de género e intrafamiliar (875), agresiones por animales (300) | sí (Power BI 006) |
| **Salud mental e intoxicaciones** | intento de suicidio (356), intoxicaciones (365) | sí |
| **Materno-perinatal** | morbilidad materna extrema (549) | sí |
| **Inmunoprevenibles** | varicela (831) | sí |

- **Cada serie** es una anomalía *operativa*: el log contra la media de las 52 semanas previas, que es lo que
  se sabría esa semana.
- **Cada familia** es el promedio de sus series estandarizadas.
- **Todo con datos hasta 2024.** La definición vive en `notebooks/indices.py`, que usará también el
  reentrenamiento.
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
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
FIN = ix.REF_FIN
FAM = ix.familias_enfermedad().loc[:FIN]
FAM[(FAM.index >= "2020-03-15") & (FAM.index <= "2021-12-31")] = np.nan      # la COVID desordena la notificacion
S = ix.series_sivigila().loc["2012":FIN]
print("Casos o consultas totales 2012-2024 por serie:"); S.sum().astype(int).sort_values(ascending=False)
""")

md(r"""
---
# 1. Cuándo sube cada familia
""")
code(r"""
crudas = ix.series_sivigila().loc["2015":FIN]
crudas = crudas[(crudas.index < "2020-03-15") | (crudas.index > "2021-12-31")]
indice_mes = {}
for fam, miembros in ix.FAMILIAS.items():
    cols = [f"{ev}_{var or 'casos'}" for ev, var in miembros]
    x = np.log1p(crudas[cols]); x = x - x.groupby(x.index.year).transform("mean")      # forma del ano, sin el nivel de cada ano
    indice_mes[fam] = (np.exp(x.mean(axis=1).groupby(x.index.month).mean()) - 1) * 100
H = pd.DataFrame(indice_mes).T
fig, ax = plt.subplots(figsize=(12, 3.8))
im = ax.imshow(H.values, cmap="RdBu_r", vmin=-25, vmax=25, aspect="auto")
ax.set_xticks(range(12), MESES); ax.set_yticks(range(len(H)), [f.replace("_", " ") for f in H.index])
for (i, j), v in np.ndenumerate(H.values): ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=8, color=TINTA)
plt.colorbar(im, ax=ax, label="% frente a la media del año"); ax.set_title("La estación de cada familia (2015-2024, sin la COVID)")
plt.tight_layout(); plt.show()
""")
lec("estacion")

md(r"""
---
# 2. ¿Se mueven juntas? Correlación entre familias, semana a semana
""")
code(r"""
C_ = FAM.dropna().corr().round(2)
C_.index = C_.columns = [c.replace("_", " ") for c in C_.columns]; C_
""")
lec("juntas")

md(r"""
---
# 3. Cada familia contra el hospital

Desenlaces:
- el **triage total** sin calendario ni escalones de la red (2022-2024);
- los **ingresos por capítulo de diagnóstico** del hospital (2021-2024): respiratorio, infecciosas, digestivo,
  trauma, embarazo y mental.

Cada prueba es `desenlace(t) ~ familia(t − rezago) + mes + año`, con rezago de 0 a 4 semanas, errores HAC y
BH con q = 0,10 por desenlace.
""")
code(r"""
dx = pd.read_parquet(RAIZ / "salidas/perfil_dx_diario.parquet"); dx["dia"] = pd.to_datetime(dx.dia)
print("capítulos disponibles:", sorted(dx.capitulo.unique()))
CAP = {"respiratorio": "X Respiratorio", "infecciosas": "I Infecciosas y parasitarias", "digestivo": "XI Digestivo",
       "trauma": "XIX Traumatismos y envenenamientos", "embarazo": "XV Embarazo, parto y puerperio"}
ment = [c for c in dx.capitulo.unique() if c.startswith("V ")]
if ment: CAP["mental"] = ment[0]
dias = pd.date_range("2020-01-01", FIN)
DES = {"triage total": desenlace_semanal().y.loc[:FIN]}
for k, c in CAP.items():
    s = dx[dx.capitulo == c].set_index("dia").n.reindex(dias).fillna(0)
    DES[f"ingresos {k}"] = np.log1p(ix.semana(s, "sum")).loc["2021-01-01":FIN]
def barrido(y, X, rezagos=range(0, 5)):
    filas = []; idx = y.dropna().index
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    anio = pd.get_dummies(pd.Index(idx.year), prefix="a", drop_first=True).set_index(idx).astype(float)
    for c in X:
        xs = (X[c] - X[c].mean()) / X[c].std()
        for L in rezagos:
            D = pd.concat([y.rename("y"), xs.shift(L).rename("x"), mes, anio], axis=1).loc[idx].dropna()
            if len(D) < 50 or D.x.std() == 0: continue
            r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
            filas.append({"familia": c, "rezago": L, "efecto %": 100 * (np.exp(r.params["x"]) - 1), "p": r.pvalues["x"], "n": len(D)})
    T = pd.DataFrame(filas); T["q"] = multipletests(T.p, method="fdr_bh")[1]; return T
RES = {k: barrido(y, FAM) for k, y in DES.items()}
pd.DataFrame({k: {"pruebas": len(T), "p < 0,05": int((T.p < .05).sum()), "azar esperaría": round(.05 * len(T), 1),
                  "sobreviven BH": int((T.q < .10).sum())} for k, T in RES.items()}).T
""")
code(r"""
fig, ax = plt.subplots(figsize=(12, 4.6))
M = pd.DataFrame({k: T.loc[T.groupby("familia")["p"].idxmin()].set_index("familia")["efecto %"] for k, T in RES.items()})
Q = pd.DataFrame({k: T.loc[T.groupby("familia")["p"].idxmin()].set_index("familia")["q"] for k, T in RES.items()})
lim = np.nanmax(np.abs(M.values))
im = ax.imshow(M.values, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
for (i, j), v in np.ndenumerate(M.values): ax.text(j, i, f"{v:+.1f}{'●' if Q.values[i, j] < .10 else ''}", ha="center", va="center", fontsize=8)
ax.set_xticks(range(M.shape[1]), M.columns, rotation=30, ha="right", fontsize=8); ax.set_yticks(range(M.shape[0]), [f.replace("_", " ") for f in M.index])
plt.colorbar(im, ax=ax, label="% por desv. típica"); ax.set_title("El rezago más fuerte de cada familia contra cada desenlace del hospital (● = sobrevive a BH)")
plt.tight_layout(); plt.show()
pd.concat({k: T[T.q < .10].sort_values("p")[["familia", "rezago", "efecto %", "q", "n"]] for k, T in RES.items()}).round(3)
""")
lec("hospital")

md(r"""
---
# 4. Clima → familia de enfermedad

La cadena «factor externo → enfermedad en la ciudad → demanda» empieza aquí: ¿qué familias responden al
clima? Se usan los índices de clima del cuaderno 17 (2012-2024, rezagos de 0 a 6 semanas).
""")
code(r"""
IC = ix.indices_clima()
RC = {fam: barrido(FAM[fam].dropna(), IC, range(0, 7)) for fam in FAM}
rc = pd.DataFrame({fam: {"pruebas": len(T), "sobreviven BH": int((T.q < .10).sum()),
                         "más fuerte": (lambda t: f"{t.familia} a {t.rezago} sem: {t['efecto %']:+.1f} %")(T.loc[T.p.idxmin()])} for fam, T in RC.items()}).T
rc
""")
lec("clima")

md(r"""
---
# 5. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "19_las_familias_de_enfermedad.ipynb")
print("ok", len(C))
