import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("17_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 17 — El clima completo: sol, nubes, rachas y cambios bruscos

## Qué pidió el propietario

Que el modelo no se quede con «temperatura y si llovió». Quiere el **contexto completo**: humedad,
precipitación, sol, **cuánto tiempo lleva haciendo sol**, los **cambios bruscos**. Es lo que `CLAUDE.md` llama
«importa la transición, no el nivel», y que hasta hoy **no existía como variable**.

## Qué se hizo (fila `clima_completo` de `variables.csv`, fijada antes de mirar)

- **Datos nuevos:** `calendarios/clima/clima_completo.py`, en el mismo punto que el clima actual (La Nubia),
  **desde 2010**.
  - Horas de sol, nubosidad, punto de rocío, déficit de presión de vapor, humedad, temperatura y radiación
    salen de Open-Meteo/ERA5.
  - La lluvia sale de NASA POWER.
- **Variables:**
  - cada nivel como anomalía contra lo normal del mes, en 7 y 28 días;
  - cada **cambio** (la última semana contra las tres anteriores);
  - las **rachas** (días en racha seca, días seguidos de sol, días desde la última semana muy lluviosa);
  - los **extremos** (noches frías);
  - la **transición de seco a lluvioso**.
- **Exploración**, contra tres desenlaces y **solo con 2010-2024**:
  1. **la IRA de Manizales** (SIVIGILA 995, 2012-2024, sin la COVID): es donde el clima debería verse;
  2. **los ingresos respiratorios del hospital** (2021-2024);
  3. **el triage total** sin calendario ni escalones de la red (2022-2024).
- **Método:** rezagos de 0 a 6 semanas, con mes y año fijos (la estación no cuenta como efecto), errores HAC,
  y Benjamini-Hochberg con q = 0,10 por desenlace.
- **2025 y 2026 no se miran aquí:** están reservados para elegir y probar el modelo.

**Antes de usar los datos se validaron**, porque toda fuente puede estar rota:
- **la lluvia del ERA5 en Manizales da ~16.000 mm al año**, 10 veces lo real, con correlación −0,02 frente
  al pluviómetro. **Se descartó.**
- La lluvia de NASA da ~2.060 mm al año, y frente al pluviómetro correlaciona 0,30 por día, 0,52 por semana
  y 0,80 por mes. Por eso **toda variable de lluvia usa ventanas de 7 días o más**.
""")

code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from matplotlib import pyplot as plt
from desenlace import desenlace_semanal

AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
FIN_EXPLORA = "2024-12-31"
cc = pd.read_csv(RAIZ / "calendarios/clima_completo.csv.gz", index_col=0, parse_dates=True)
def semana(s, como="mean"):
    r = getattr(s.resample("W-SAT"), como)(); r.index = r.index - pd.Timedelta(days=6); return r
NIVELES = ["temp", "tmin", "tmax", "lluvia", "sol", "nubes", "rocio", "humedad", "vpd", "radiacion", "viento"]
F = {}
for n in NIVELES:
    F[f"{n}_7d"] = semana(cc[f"{n}_7d"]); F[f"{n}_28d"] = semana(cc[f"{n}_28d"]); F[f"{n}_cambio"] = semana(cc[f"{n}_cambio"])
F["dias_en_racha_seca"] = semana(cc.dias_en_racha_seca, "max"); F["dias_de_sol"] = semana(cc.dias_de_sol, "max")
F["dias_desde_semana_muy_lluviosa"] = semana(cc.dias_desde_semana_muy_lluviosa, "min")
F["extremos_frio_7d"] = semana(cc.extremos_frio_7d, "max"); F["seco_a_lluvioso"] = semana(cc.seco_a_lluvioso, "max")
F = pd.DataFrame(F)
FAMILIA = {c: ("nivel 7 días" if c.endswith("_7d") and c.split("_")[0] in NIVELES else "nivel 28 días" if c.endswith("_28d") else
               "cambio brusco" if c.endswith("_cambio") else "racha / extremo / transición") for c in F}
print(f"{F.shape[1]} variables semanales de clima, {F.index[0].date()} a {F.index[-1].date()}")
pd.Series(FAMILIA).value_counts()
""")

md(r"""
---
# 1. Cómo se ve el clima nuevo

Las variables que no existían: horas de sol, nubosidad, rachas y la transición de seco a lluvioso.
""")
code(r"""
v = cc.loc["2019-01-01":FIN_EXPLORA]
fig, axes = plt.subplots(4, 1, figsize=(15, 9), sharex=True)
axes[0].plot(v.index, v.horas_sol.rolling(14, center=True).mean(), color=AMARILLO, lw=1.4); axes[0].set_ylabel("horas de sol\n(media 14 d)")
axes[1].plot(v.index, v.cloud_cover_mean.rolling(14, center=True).mean(), color=MUDO, lw=1.4); axes[1].set_ylabel("nubosidad %\n(media 14 d)")
axes[2].fill_between(v.index, 0, v.dias_en_racha_seca, color=NARANJA, lw=0, alpha=.8, label="días en racha seca")
axes[2].fill_between(v.index, 0, -v.dias_de_sol.clip(upper=30), color=AMARILLO, lw=0, alpha=.6, label="días seguidos de sol (hacia abajo)")
axes[2].legend(loc="upper left", fontsize=8, ncol=2); axes[2].set_ylabel("días")
axes[3].plot(v.index, v.lluvia_7d, color=AZUL, lw=1); axes[3].axhline(0, color=MUDO, lw=.8)
for d in v.index[v.seco_a_lluvioso > 0]: axes[3].axvline(d, color=ROJO, lw=.6, alpha=.5)
axes[3].set_ylabel("lluvia 7 d\n(anomalía)"); axes[3].set_title("Lluvia de la semana frente a lo normal; en rojo, los días de transición de seco a lluvioso", fontsize=10)
plt.tight_layout(); plt.show()
print("Días de transición seco → lluvioso por año:", cc.seco_a_lluvioso.groupby(cc.index.year).sum().astype(int).loc[:2024].to_dict())
""")
lec("vista")

md(r"""
---
# 2. Los desenlaces
""")
code(r"""
v = pd.read_csv(RAIZ / "calendarios/vigilancia_sivigila.csv.gz", parse_dates=["fecha_inicio_semana"])
ira = (v[(v.ambito == "manizales") & (v.evento == 995) & (v.variable == "consultas_ira_total")]
         .drop_duplicates("fecha_inicio_semana").set_index("fecha_inicio_semana").valor.astype(float))
ira = np.log(ira.loc["2012-01-01":FIN_EXPLORA]); ira[(ira.index >= "2020-03-15") & (ira.index <= "2021-12-31")] = np.nan
dx = pd.read_parquet(RAIZ / "salidas/perfil_dx_diario.parquet"); dx["dia"] = pd.to_datetime(dx.dia)
resp = dx[dx.capitulo == "X Respiratorio"].set_index("dia").n.reindex(pd.date_range("2020-01-01", FIN_EXPLORA)).fillna(0)
resp = np.log1p(semana(resp, "sum")).loc["2021-01-01":FIN_EXPLORA]
tot = desenlace_semanal().y.loc[:FIN_EXPLORA]
DES = {"IRA de Manizales": ira, "ingresos respiratorios del hospital": resp, "triage total (sin calendario ni red)": tot}
for k, s in DES.items(): print(f"{k}: {s.notna().sum()} semanas, {s.dropna().index[0].date()} a {s.dropna().index[-1].date()}")
""")

md(r"""
---
# 3. El barrido: cada variable de clima, con rezago de 0 a 6 semanas

Por cada desenlace, variable y rezago: `desenlace(semana t) ~ clima(semana t − rezago) + mes + año`. El
efecto se lee como **% de cambio en el desenlace por cada desviación típica de la variable**, con errores HAC.
""")
code(r"""
def barrido(y, X, rezagos=range(0, 7)):
    filas = []
    idx = y.dropna().index
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    anio = pd.get_dummies(pd.Index(idx.year), prefix="a", drop_first=True).set_index(idx).astype(float)
    for c in X:
        xs = (X[c] - X[c].loc[:FIN_EXPLORA].mean()) / X[c].loc[:FIN_EXPLORA].std()
        for L in rezagos:
            D = pd.concat([y.rename("y"), xs.shift(L).rename("x"), mes, anio], axis=1).loc[idx].dropna()
            if len(D) < 60 or D.x.std() == 0: continue
            r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
            filas.append({"variable": c, "familia": FAMILIA[c], "rezago": L, "efecto %": 100 * (np.exp(r.params["x"]) - 1), "p": r.pvalues["x"], "n": len(D)})
    T = pd.DataFrame(filas); T["q"] = multipletests(T.p, method="fdr_bh")[1]
    return T
RES = {k: barrido(s, F) for k, s in DES.items()}
resumen = pd.DataFrame({k: {"pruebas": len(T), "p < 0,05": int((T.p < .05).sum()), "azar esperaría": round(.05 * len(T)),
                            "sobreviven BH (q < 0,10)": int((T.q < .10).sum())} for k, T in RES.items()}).T
resumen
""")
lec("barrido")

code(r"""
fig, axes = plt.subplots(1, 3, figsize=(16, 6.5), sharey=True)
orden = list(F.columns)
for ax, (k, T) in zip(axes, RES.items()):
    M = T.pivot_table(index="variable", columns="rezago", values="efecto %").reindex(orden)
    Q = T.pivot_table(index="variable", columns="rezago", values="q").reindex(orden)
    lim = np.nanpercentile(np.abs(M.values), 98)
    im = ax.imshow(M.values, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
    for (i, j), q in np.ndenumerate(Q.values):
        if q < .10: ax.text(j, i, "●", ha="center", va="center", fontsize=7, color=TINTA)
    ax.set_xticks(range(M.shape[1]), M.columns); ax.set_xlabel("rezago (semanas)"); ax.set_title(k, fontsize=10)
    plt.colorbar(im, ax=ax, fraction=.04, label="% por desv. típica")
axes[0].set_yticks(range(len(orden)), orden, fontsize=7)
fig.suptitle("Efecto de cada variable de clima, por rezago (● = sobrevive a BH con q < 0,10)", fontweight="bold"); plt.tight_layout(); plt.show()
""")

code(r"""
top = []
for k, T in RES.items():
    t = T[T.q < .10].copy(); t["desenlace"] = k; top.append(t)
TOP = pd.concat(top) if top else pd.DataFrame()
print("Lo que sobrevive a BH, ordenado por tamaño del efecto dentro de cada desenlace:")
(TOP.assign(abs_=TOP["efecto %"].abs()).sort_values(["desenlace", "abs_"], ascending=[True, False])
    .groupby("desenlace").head(12)[["desenlace", "variable", "familia", "rezago", "efecto %", "q", "n"]].round(3)) if len(TOP) else "nada sobrevive"
""")
lec("top")

md(r"""
---
# 4. ¿Aportan las variables NUEVAS?

Se separan las que ya existían en el modelo (temperatura, humedad, lluvia, radiación y viento en nivel) de las
que se crearon ahora: horas de sol, nubosidad, punto de rocío, déficit de presión de vapor, los cambios
bruscos, las rachas, los extremos y la transición.
""")
code(r"""
NUEVAS = lambda c: (c.split("_")[0] in ["sol", "nubes", "rocio", "vpd"]) or c.endswith("_cambio") or FAMILIA[c] == "racha / extremo / transición"
filas = []
for k, T in RES.items():
    for grupo, sel in [("ya existían (niveles)", ~T.variable.map(NUEVAS)), ("nuevas", T.variable.map(NUEVAS))]:
        t = T[sel]; filas.append({"desenlace": k, "grupo": grupo, "pruebas": len(t), "sobreviven BH": int((t.q < .10).sum()),
                                  "% que sobrevive": round(100 * (t.q < .10).mean(), 1), "mayor efecto %": round(t.loc[t.q < .10, "efecto %"].abs().max(), 1) if (t.q < .10).any() else np.nan})
pd.DataFrame(filas).set_index(["desenlace", "grupo"])
""")
lec("nuevas")

md(r"""
---
# 5. Índices: resumir el clima en pocas cifras

Para no darle al modelo 40 variables sueltas, que en el cuaderno 15 lo sobreajustaron, se resumen en
**componentes principales**, ajustados solo con 2010-2024:
- el **«estado del clima»**: los niveles de 7 días;
- el **«cambio brusco»**: los cambios.
""")
code(r"""
from sklearn.decomposition import PCA
def indices(cols, k, nombre):
    Z = F[cols].loc["2010-01-10":FIN_EXPLORA].dropna(); mu, sd = Z.mean(), Z.std()
    p = PCA(k).fit((Z - mu) / sd)
    S = pd.DataFrame(p.transform(((F[cols] - mu) / sd).dropna()), index=F[cols].dropna().index, columns=[f"{nombre}_{i + 1}" for i in range(k)])
    L = pd.DataFrame(p.components_.T, index=cols, columns=S.columns).round(2)
    return S, L, p.explained_variance_ratio_
S1, L1, v1 = indices([f"{n}_7d" for n in NIVELES], 4, "estado")
S2, L2, v2 = indices([f"{n}_cambio" for n in NIVELES], 3, "cambio")
print(f"Estado del clima: 4 componentes explican {v1.sum():.0%} ({np.round(v1, 2)}); cambio brusco: 3 explican {v2.sum():.0%} ({np.round(v2, 2)})")
display(pd.concat([L1, L2], axis=1).fillna(""))
IDX = S1.join(S2, how="outer")
FAMILIA.update({c: "índice" for c in IDX})
RI = {k: barrido(s, IDX) for k, s in DES.items()}
pd.concat({k: T[T.q < .10][["variable", "rezago", "efecto %", "q"]] for k, T in RI.items()}).round(3)
""")
lec("indices")

md(r"""
---
# 6. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "17_el_clima_completo_y_sus_cambios.ipynb")
print("ok", len(C))
