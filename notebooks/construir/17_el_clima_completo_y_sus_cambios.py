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

## Pregunta y alcance

El clima que se había usado hasta aquí era una temperatura y un indicador de si llovió. Ese resumen pierde lo que
más importa en el mecanismo propuesto: una exposición al frío y la humedad que se prolonga, o un giro brusco de
una racha seca a una lluviosa, y no el valor de un día cualquiera. Este cuaderno construye el clima completo de
Manizales (humedad, precipitación, sol, tiempo que lleva haciendo sol, cambios bruscos) y mide qué parte de él se
asocia con tres desenlaces: la infección respiratoria aguda (IRA) de la ciudad, los ingresos respiratorios del
hospital y el triage total. Después se baja a lo concreto: los episodios de transición de seco a lluvioso uno por
uno, el efecto por banda de edad y la dilución del efecto desde la IRA de la ciudad hasta el triage total.

## Datos y método

- **Datos:** `calendarios/clima/clima_completo.py`, en el mismo punto que el clima anterior (La Nubia), **desde 2010**.
  - Horas de sol, nubosidad, punto de rocío, déficit de presión de vapor, humedad, temperatura y radiación salen
    de Open-Meteo/ERA5; la lluvia sale de NASA POWER.
- **Variables**, definidas antes de mirar los resultados:
  - cada nivel como anomalía contra lo normal del mes, en 7 y 28 días;
  - cada **cambio** (la última semana frente a las tres anteriores);
  - las **rachas** (días en racha seca, días seguidos de sol, días desde la última semana muy lluviosa);
  - los **extremos** (noches frías);
  - la **transición de seco a lluvioso**.
- **Desenlaces**, explorados solo con 2010-2024:
  1. **la IRA de Manizales** (SIVIGILA 995, 2012-2024, sin el periodo de la COVID), donde el clima debería verse;
  2. **los ingresos respiratorios del hospital** (2021-2024);
  3. **el triage total** sin calendario ni escalones de la red (2022-2024).
- **Método:** rezagos de 0 a 6 semanas, con mes y año fijos (la estación no cuenta como efecto), errores HAC y
  corrección de Benjamini-Hochberg (BH) con q = 0,10 por desenlace.
- **2025 y 2026 no se miran aquí:** quedan reservados para elegir y probar el modelo.

Antes de usar los datos se validó cada fuente. La lluvia del ERA5 en Manizales da unos 16.000 mm al año, diez veces
lo real, con correlación −0,02 frente al pluviómetro, y **se descartó**. La de NASA da unos 2.060 mm al año y
correlaciona 0,30 por día, 0,52 por semana y 0,80 por mes con el pluviómetro válido; por eso **toda variable de
lluvia usa ventanas de 7 días o más**.
""")

code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from matplotlib import pyplot as plt
from desenlace import desenlace_semanal
import desenlace as de

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
# 1. Las variables nuevas a lo largo de los años

Horas de sol, nubosidad, rachas y la transición de seco a lluvioso, que antes no existían como variables.
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
mes = cc.loc[:FIN_EXPLORA].groupby(cc.loc[:FIN_EXPLORA].index.month)
print("Horas de sol por mes (media diaria):", mes.horas_sol.mean().round(1).to_dict())
print("Nubosidad por mes (%):", mes.cloud_cover_mean.mean().round(0).to_dict())
print("Racha seca más larga por año (días):", cc.dias_en_racha_seca.groupby(cc.index.year).max().loc[2010:2024].astype(int).to_dict())
print("Días de transición seco → lluvioso por año:", cc.seco_a_lluvioso.groupby(cc.index.year).sum().astype(int).loc[:2024].to_dict())
""")
lec("vista")

md(r"""
---
# 2. Los tres desenlaces
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
print(f"Media semanal en la ventana: IRA de Manizales {np.exp(ira).mean():,.0f} consultas; ingresos respiratorios {np.expm1(resp).mean():.1f}; triage total {tot.index.size and desenlace_semanal().triage.loc[:FIN_EXPLORA].mean():,.0f}")
""")

md(r"""
---
# 3. El barrido de cada variable de clima con rezago de 0 a 6 semanas

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
            filas.append({"variable": c, "familia": FAMILIA[c], "rezago": L, "efecto %": 100 * (np.exp(r.params["x"]) - 1), "ee %": 100 * r.bse["x"], "p": r.pvalues["x"], "n": len(D)})
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
lec("mapa")

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
# 4. Aporte de las variables nuevas

Se separan las que ya existían en el modelo (temperatura, humedad, lluvia, radiación y viento en nivel) de las
que se crearon para este cuaderno: horas de sol, nubosidad, punto de rocío, déficit de presión de vapor, los cambios
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
code(r"""
print("Pruebas con la transición de seco a lluvioso que sobreviven a BH:", {k: int(((T.variable == "seco_a_lluvioso") & (T.q < .10)).sum()) for k, T in RES.items()})
pd.DataFrame({k: T[T.q < .10].groupby("familia").size() for k, T in RES.items()}).reindex(["nivel 7 días", "nivel 28 días", "cambio brusco", "racha / extremo / transición"]).fillna(0).astype(int)
""")
lec("nuevas_familias")

md(r"""
---
# 5. Índices que resumen el clima en pocas cifras

Para no darle al modelo 40 variables sueltas, que en el cuaderno 15 sobreajustaron el modelo, se resumen en
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
# 6. Episodios concretos de transición de seco a lluvioso

Un promedio de 13 años puede diluir un efecto que ocurre solo en los giros bruscos. Por eso se miran las
transiciones una por una. El indicador marca un día cuando las dos semanas previas fueron secas y la lluvia de la
última semana supera lo normal; los días marcados a menos de 14 días uno de otro se agrupan en un **episodio**.
Para cada episodio se toma la semana en que empieza como semana 0 y se sigue el desenlace tres semanas antes y
seis después, siempre como desvío frente a lo esperado para ese mes y año. Como referencia, se repite el cálculo
2.000 veces con el mismo número de semanas escogidas al azar: la banda gris es el rango en que caería el promedio
de episodios si la fecha no importara.
""")
code(r"""
sl = cc.seco_a_lluvioso.loc[:FIN_EXPLORA]; EP = []
for d in sl.index[sl > 0]:
    if not EP or (d - EP[-1][-1]).days > 14: EP.append([d])
    else: EP[-1].append(d)
ini = pd.DatetimeIndex([e[0] for e in EP]); ini_sem = ini - pd.to_timedelta((ini.weekday + 1) % 7, unit="D")
def sin_estacion(y):
    y = y.dropna()
    X = pd.concat([pd.get_dummies(pd.Index(y.index.month), prefix="m", drop_first=True),
                   pd.get_dummies(pd.Index(y.index.year), prefix="a", drop_first=True)], axis=1).set_index(y.index).astype(float)
    return sm.OLS(y, sm.add_constant(X)).fit().resid
OFS = list(range(-3, 7)); rng = np.random.default_rng(17)
def camino(y):
    r = sin_estacion(y).reindex(pd.date_range(y.index.min(), y.index.max(), freq="W-SUN"))
    M = pd.DataFrame({k: r.shift(-k) for k in OFS})
    E = M.reindex(ini_sem).dropna(how="all"); E = E[E[0].notna()]
    valido = M[M[0].notna()].values
    sim = np.array([np.nanmean(valido[rng.choice(len(valido), len(E), replace=False)], axis=0) for _ in range(2000)])
    return E, sim
EPI = {k: camino(DES[k]) for k in ["IRA de Manizales", "triage total (sin calendario ni red)"]}
pc = lambda x: 100 * (np.exp(x) - 1)
fig, axes = plt.subplots(1, 2, figsize=(15, 5), sharex=True)
for ax, (k, (E, sim)) in zip(axes, EPI.items()):
    lo, hi = np.nanpercentile(sim, [2.5, 97.5], axis=0)
    ax.fill_between(OFS, pc(lo), pc(hi), color=MUDO, alpha=.25, lw=0, label="95 % de promedios de semanas al azar")
    for _, f in E.iterrows(): ax.plot(OFS, pc(f.values), color=AZUL, lw=.7, alpha=.3)
    ax.plot(OFS, pc(E.mean().values), color=NARANJA, lw=2.6, marker="o", label=f"promedio de {len(E)} episodios")
    ax.axhline(0, color=TINTA2, lw=.8); ax.axvline(0, color=ROJO, lw=1, ls="--")
    ax.set_xlabel("semanas desde el inicio del episodio"); ax.set_ylabel("desvío frente a lo esperado (%)")
    ax.set_title(k); ax.legend(loc="upper left", fontsize=8)
    if k.startswith("IRA"): ax.set_ylim(-70, 105)
fig.suptitle("Los desenlaces en torno a cada giro de seco a lluvioso", fontweight="bold"); plt.tight_layout(); plt.show()
filas = []
for k, (E, sim) in EPI.items():
    ventana = E[[1, 2, 3, 4]].mean(axis=1); sv = sim[:, [OFS.index(j) for j in (1, 2, 3, 4)]].mean(axis=1)
    rebote = E[[3, 4, 5, 6]].mean(axis=1) - E[[-1, 0, 1, 2]].mean(axis=1)
    sr = sim[:, [OFS.index(j) for j in (3, 4, 5, 6)]].mean(axis=1) - sim[:, [OFS.index(j) for j in (-1, 0, 1, 2)]].mean(axis=1)
    filas.append({"desenlace": k, "episodios": len(E), "desvío medio semanas 1-4 (%)": round(pc(ventana.mean()), 2),
                  "mediana semanas 1-4 (%)": round(pc(ventana.median()), 2), "episodios con desvío > 0": int((ventana > 0).sum()),
                  "percentil frente al azar": round(100 * (sv < ventana.mean()).mean(), 1),
                  "rebote semanas 3-6 menos -1-2 (puntos %)": round(100 * rebote.mean(), 2), "percentil del rebote": round(100 * (sr < rebote.mean()).mean(), 1),
                  "mediana del rebote (puntos %)": round(100 * rebote.median(), 2), "episodios con rebote > 0": int((rebote > 0).sum())})
print("Primer día de cada episodio:", ", ".join(d.strftime("%Y-%m-%d") for d in ini))
pd.DataFrame(filas).set_index("desenlace")
""")
lec("episodios")
code(r"""
E_ira = EPI["IRA de Manizales"][0]; E_tot = EPI["triage total (sin calendario ni red)"][0]
T = pd.DataFrame({"IRA, desvío semanas 1-4 (%)": pc(E_ira[[1, 2, 3, 4]].mean(axis=1)).round(1),
                  "días del episodio": pd.Series({s: len(e) for s, e in zip(ini_sem, EP)}),
                  "triage total, desvío semanas 1-4 (%)": pc(E_tot[[1, 2, 3, 4]].mean(axis=1)).round(1)})
T.index = T.index.strftime("%Y-%m-%d"); T.index.name = "semana de inicio"; T.dropna(subset=["IRA, desvío semanas 1-4 (%)"]).astype(object).fillna("sin dato")
""")
lec("episodios_tabla")

md(r"""
---
# 7. El clima por banda de edad

Si el efecto respiratorio del clima es grande en los niños y en los mayores y casi nulo en los adultos jóvenes, el
total lo promedia y lo apaga. Se repite el barrido con cada banda de edad del triage (0-4, 5-14, 15-44, 45-64 y
65 o más años) como desenlace, de 2022-03 a 2024-12. Cada banda se lleva a su residuo semanal sin calendario, sin
nivel del año y sin escalones de la red, conservando la estación. Las variables son los siete índices de clima,
las rachas, los extremos y la transición de seco a lluvioso, a rezagos de 0 a 4 semanas, con mes fijo, errores HAC
y BH por banda.
""")
code(r"""
dias = pd.date_range("2020-01-01", "2026-09-20")
ed = pd.read_parquet(RAIZ / "salidas/triage_edad.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
E = ed.pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").reindex(dias).fillna(0)
nv = pd.read_parquet(RAIZ / "salidas/triage_nivel.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
P = pd.DataFrame({"0-4": E["0-4"], "5-14": E["5-14"], "15-44": E["15-44"], "45-64": E["45-64"], "65+": E["65-+"],
                  "total": nv.groupby("dia").n.sum().reindex(dias).fillna(0)})
P.loc["2024-03-19":"2024-03-21"] = np.nan
cal = (pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
         .reindex(dias)[de.CAL].apply(pd.to_numeric, errors="coerce").fillna(0))
completas = de._semana(P["total"].notna().astype(int)) == 7
cal_w = de._semana(cal).loc[de.INICIO:"2024-12-29"]
RB = pd.DataFrame({c: de._residuo(de._semana(P[c]).where(completas).loc[de.INICIO:"2024-12-29"], cal_w) for c in P})
EXTRA = ["dias_en_racha_seca", "dias_de_sol", "dias_desde_semana_muy_lluviosa", "seco_a_lluvioso", "extremos_frio_7d"]
COL = list(IDX.columns) + EXTRA
XB = pd.concat([IDX, F[EXTRA]], axis=1)
def barrido_banda(y, rezagos=range(0, 5)):
    idx = y.dropna().index; filas = []
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    for c in COL:
        xs = (XB[c] - XB[c].loc[:FIN_EXPLORA].mean()) / XB[c].loc[:FIN_EXPLORA].std()
        for L in rezagos:
            D = pd.concat([y.rename("y"), xs.shift(L).rename("x"), mes], axis=1).loc[idx].dropna()
            if len(D) < 60 or D.x.std() == 0: continue
            r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
            filas.append({"variable": c, "rezago": L, "efecto %": 100 * (np.exp(r.params["x"]) - 1), "ee %": 100 * r.bse["x"],
                          "ic_bajo": 100 * (np.exp(r.params["x"] - 1.96 * r.bse["x"]) - 1), "ic_alto": 100 * (np.exp(r.params["x"] + 1.96 * r.bse["x"]) - 1),
                          "p": r.pvalues["x"]})
    T = pd.DataFrame(filas); T["q"] = multipletests(T.p, method="fdr_bh")[1]; return T
TB = {c: barrido_banda(RB[c]) for c in RB}
peso = (P.loc["2022":"2024"].mean() / P.loc["2022":"2024", "total"].mean() * 100).round(1)
res = pd.DataFrame({c: {"peso en el triage %": peso[c], "pruebas": len(T), "p < 0,05": int((T.p < .05).sum()), "sobreviven BH": int((T.q < .10).sum()),
                        "mayor efecto que sobrevive %": round(T.loc[T.q < .10, "efecto %"].abs().max(), 1) if (T.q < .10).any() else np.nan,
                        "ruido semanal del residuo %": round(100 * RB[c].std(), 1)} for c, T in TB.items()}).T
res
""")
lec("bandas")
code(r"""
cel = {c: T.loc[T.groupby("variable").p.idxmin()].set_index("variable") for c, T in TB.items()}
M = pd.DataFrame({c: cel[c]["efecto %"] for c in cel}).reindex(COL); Q = pd.DataFrame({c: cel[c]["q"] for c in cel}).reindex(COL)
fig, ax = plt.subplots(figsize=(10, 6.2)); lim = np.nanpercentile(np.abs(M.values), 98)
im = ax.imshow(M.values, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
for (i, j), q in np.ndenumerate(Q.values):
    ax.text(j, i, f"{M.values[i, j]:+.1f}" + ("●" if q < .10 else ""), ha="center", va="center", fontsize=7.5, color=TINTA)
ax.set_xticks(range(M.shape[1]), M.columns); ax.set_yticks(range(len(COL)), COL, fontsize=8); ax.grid(False)
plt.colorbar(im, ax=ax, label="% por desviación típica (al rezago de menor p)")
ax.set_title("Efecto del clima en cada banda de edad (● = sobrevive a BH, q < 0,10)"); plt.tight_layout(); plt.show()
""")
lec("bandas_mapa")
code(r"""
v = "dias_desde_semana_muy_lluviosa"
fig, axes = plt.subplots(1, 6, figsize=(17, 3.6), sharex=True)
for ax, (c, T) in zip(axes, TB.items()):
    t = T[T.variable == v].sort_values("rezago")
    ax.errorbar(t.rezago, t["efecto %"], yerr=[t["efecto %"] - t.ic_bajo, t.ic_alto - t["efecto %"]], color=AZUL, marker="o", capsize=2, lw=1.2)
    ax.axhline(0, color=TINTA2, lw=.8); ax.set_title(f"{c} ({peso[c]:.0f} % del triage)", fontsize=9); ax.set_xlabel("rezago (semanas)")
axes[0].set_ylabel("% por desv. típica")
fig.suptitle("Días desde la última semana muy lluviosa, por banda de edad (intervalo de 95 %)", fontweight="bold"); plt.tight_layout(); plt.show()
""")
lec("bandas_rezagos")

md(r"""
---
# 8. Dilución del efecto desde la IRA de la ciudad hasta el triage total

El efecto del clima en la IRA de Manizales es de 6-7 % por desviación típica, y en el triage total de 1,5-2,4 %.
Hay dos razones de que se achique, y se pueden poner en cifras. La primera es de composición: el total suma bandas
de edad con pesos muy distintos, y el efecto del total es el promedio de los efectos por banda ponderado por su
peso. La segunda es de ruido: un desenlace pequeño tiene un error estándar mayor, y solo deja ver efectos grandes.
""")
code(r"""
def spec_mejor(c):
    t = TB[c][TB[c].q < .10]; r = (t if len(t) else TB[c]).sort_values("p").iloc[0]; return r.variable, int(r.rezago)
bandas = ["0-4", "5-14", "15-44", "45-64", "65+"]
out = []
for ancla in ["65+", "total"]:
    v, L = spec_mejor(ancla)
    fila = {b: TB[b].query("variable == @v and rezago == @L")["efecto %"].iloc[0] for b in bandas + ["total"]}
    out.append({"se elige según": ancla, "variable": v, "rezago": L, **{f"efecto {b} %": round(fila[b], 2) for b in bandas},
                "suma ponderada %": round(sum(peso[b] / 100 * fila[b] for b in bandas), 2), "efecto medido en el total %": round(fila["total"], 2)})
print("Pesos de las bandas en el triage (%):", peso[bandas].to_dict(), "| suma:", round(peso[bandas].sum(), 1))
pd.DataFrame(out).set_index("se elige según").T
""")
lec("dilucion")
code(r"""
M2 = RES["IRA de Manizales"].merge(RES["triage total (sin calendario ni red)"], on=["variable", "rezago"], suffixes=("_ira", "_tot"))
M2["sobrevive en"] = np.select([(M2.q_ira < .10) & (M2.q_tot < .10), M2.q_ira < .10, M2.q_tot < .10], ["ambos", "solo la IRA", "solo el triage"], "ninguno")
mismo = np.sign(M2["efecto %_ira"]) == np.sign(M2["efecto %_tot"])
print(f"{len(M2)} pares variable-rezago. Correlación del efecto en la IRA con el efecto en el triage total: {M2['efecto %_ira'].corr(M2['efecto %_tot']):.2f}")
print(f"Mismo signo en {100 * mismo.mean():.0f} % de los pares; entre los {int((M2.q_ira < .10).sum())} que sobreviven en la IRA, en {100 * mismo[M2.q_ira < .10].mean():.0f} %.")
print(M2["sobrevive en"].value_counts().to_dict())
fig, ax = plt.subplots(figsize=(7.5, 6))
for g, col in [("ninguno", MUDO), ("solo la IRA", AZUL), ("solo el triage", NARANJA), ("ambos", ROJO)]:
    t = M2[M2["sobrevive en"] == g]; ax.scatter(t["efecto %_ira"], t["efecto %_tot"], s=18, color=col, alpha=.7, label=f"{g} ({len(t)})")
ax.axhline(0, color=TINTA2, lw=.8); ax.axvline(0, color=TINTA2, lw=.8)
ax.set_xlabel("efecto en la IRA de Manizales (% por desv. típica)"); ax.set_ylabel("efecto en el triage total (% por desv. típica)")
ax.set_title("Cada variable y rezago: efecto en la IRA frente al efecto en el triage total"); ax.legend(title="sobrevive a BH en", fontsize=8)
plt.tight_layout(); plt.show()
corto = barrido(DES["IRA de Manizales"].loc["2022-03-06":], F)
M3 = corto.merge(RES["triage total (sin calendario ni red)"], on=["variable", "rezago"], suffixes=("_ira", "_tot"))
print(f"Misma ventana (2022-03 a 2024-12, {int(corto.n.median())} semanas): la IRA tiene {int((corto.q < .10).sum())} pruebas que sobreviven; "
      f"correlación de efectos IRA-triage {M3['efecto %_ira'].corr(M3['efecto %_tot']):.2f}; mismo signo en {100 * (np.sign(M3['efecto %_ira']) == np.sign(M3['efecto %_tot'])).mean():.0f} % de los pares.")
ee = pd.DataFrame({k: {"error estándar mediano (% por desv. típica)": round(T["ee %"].median(), 2),
                       "efecto mínimo detectable (% , 2,8 × error)": round(2.8 * T["ee %"].median(), 1),
                       "semanas": int(T.n.median())} for k, T in RES.items()}).T
ee
""")
lec("dilucion_ruido")

md(r"""
---
# 9. Conclusiones y límites
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "17_el_clima_completo_y_sus_cambios.ipynb")
print("ok", len(C))
