import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("20_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(sin texto: {k})*"))

md(r"""
# 20 — Regímenes y fenómenos: El Niño, La Niña, sismos, paro, desastres y COVID

Hasta aquí la COVID era la única catástrofe marcada en los modelos. Quedaban sin tratar los fenómenos que duran
semanas o meses (El Niño y La Niña), los eventos que interrumpen la vida de la ciudad (el terremoto de 2026, el
paro nacional de 2021, los deslizamientos y la alerta volcánica) y los cambios de régimen de la red de salud. Este
cuaderno pregunta si alguno de ellos deja una huella medible en el triage del hospital o en la salud de la ciudad, y
lo hace de dos maneras: como **estados** que duran y se repiten, que un modelo puede recibir como entrada, y como
**episodios concretos**, que se miran uno por uno, con su firma por día, por hora y por edad.

La distinción importa por el tamaño de la muestra. Un fenómeno que ocurrió una vez no se puede aprender; se puede
marcar para que no contamine lo demás, o describir como episodio. Uno que se repitió decenas de veces, como los
sismos, sí permite una conclusión estadística.

## Cómo se marcan los estados sin sobreajustar

El cuaderno 16 mostró el límite: con 4 episodios de El Niño un modelo no aprende el efecto, memoriza esos 4. Por eso
cada fenómeno entra como un estado diario conocido el día de la predicción:

| Estado | Cómo se define | Fuente |
|---|---|---|
| **El Niño / La Niña** | ONI de dos meses antes ≥ +0,5 / ≤ −0,5 (la NOAA lo publica con retraso) | NOAA, capturado cada semana |
| **COVID** fuerte / parcial | 2020-03-15 a 2020-08-31 / hasta 2022-02-28 | fechas fijas |
| **Paro nacional 2021** | 2021-04-28 a 2021-06-15 | fechas fijas |
| **Sismo fuerte** | los 7 días siguientes a un sismo de M ≥ 4,5 a menos de 150 km | USGS (`calendarios/sismos_usgs.csv`) |
| **Desastre activo** | catálogo propio de Manizales | `desastres_manizales_2020_2026.csv` |
| **Crisis de la red** | peso de Nueva EPS en el triage de 28 días por debajo de su percentil 10 de 2022-2024 | triage del hospital |
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
axes[0].axhline(.5, color=MUDO, ls=":", lw=.8); axes[0].axhline(-.5, color=MUDO, ls=":", lw=.8); axes[0].set_ylabel("ONI (2 meses antes)"); axes[0].set_title("El Niño (rojo) y La Niña (azul) desde 2012")
for i, (e, c) in enumerate([("covid_fuerte", MUDO), ("covid_parcial", "#c9c8c4"), ("paro_nacional_2021", NARANJA), ("sismo_fuerte_7d", VIOLETA), ("desastre_activo", AMARILLO), ("crisis_red", MAGENTA)]):
    axes[1].fill_between(R.index, i, i + R[e].fillna(0) * .8, color=c, lw=0, label=e.replace("_", " "))
axes[1].set_yticks([]); axes[1].legend(ncol=6, fontsize=8, loc="upper left"); axes[1].set_title("Estados puntuales: COVID, paro, sismos, desastres y crisis de la red")
t = pd.read_parquet(RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia)).set_index("dia").triages
axes[2].plot(t.index, t.rolling(28, center=True, min_periods=14).mean(), color=TINTA, lw=1.4); axes[2].set_ylabel("triage/día, media 28 d")
axes[2].set_title("Triage del hospital, 2020-2026")
axes[2].set_xlim(pd.Timestamp("2012-01-01"), R.index[-1]); plt.tight_layout(); plt.show()
""")
lec("linea")

md(r"""
---
# 1. La COVID como régimen del triage

Es el único episodio de los estados anteriores que domina el entrenamiento, y se mide con el mismo rigor que los demás.
""")
code(r"""
t = t.asfreq("D"); t.loc["2024-03-19":"2024-03-21"] = np.nan            # caída del registro: nulo, no cero
cv = (R.covid_fuerte + R.covid_parcial).reindex(t.index) > 0
fase = pd.Series("después", index=t.index); fase[R.covid_parcial.reindex(t.index) > 0] = "parcial"; fase[R.covid_fuerte.reindex(t.index) > 0] = "fuerte"
fase[t.index < "2020-03-15"] = "antes"
ref = t.loc["2022":].mean()
resumen = pd.DataFrame({"días": fase.value_counts(), "triage/día": t.groupby(fase).mean().round(1)}).loc[["antes", "fuerte", "parcial", "después"]]
resumen["% del nivel desde 2022"] = (100 * resumen["triage/día"] / ref).round(1)
peso = pd.DataFrame({o: {"días de entrenamiento": len(t.loc[:o].dropna()), "días COVID": int(cv.loc[:o].sum())} for o in ["2024-12-31", "2025-12-31", "2026-09-13"]}).T
peso["% del entrenamiento"] = (100 * peso["días COVID"] / peso["días de entrenamiento"]).round(1)
display(resumen); display(peso)
fig, ax = plt.subplots(figsize=(14, 3.8))
m28 = t.loc[:"2023"].rolling(28, center=True, min_periods=14).mean()
ax.plot(t.loc[:"2023"].index, t.loc[:"2023"], color="#c9c8c4", lw=.6, label="triage diario")
ax.plot(m28.index, m28, color=TINTA, lw=1.6, label="media de 28 días")
ax.axvspan(pd.Timestamp("2020-03-15"), pd.Timestamp("2020-08-31"), color=ROJO, alpha=.15, lw=0); ax.axvspan(pd.Timestamp("2020-09-01"), pd.Timestamp("2022-02-28"), color=AMARILLO, alpha=.12, lw=0)
ax.axhline(ref, color=AZUL, ls="--", lw=1); ax.text(pd.Timestamp("2020-01-10"), ref + 4, f"media desde 2022: {ref:.0f}", color=AZUL, fontsize=9)
ax.text(pd.Timestamp("2020-05-01"), 232, "fase fuerte", ha="center", color=ROJO); ax.text(pd.Timestamp("2021-06-01"), 232, "fase parcial", ha="center", color="#a87600")
ax.set_ylabel("triages por día"); ax.set_title("La COVID es un nivel distinto, no un año flojo"); ax.legend(loc="lower right"); plt.tight_layout(); plt.show()
""")
lec("covid")

md(r"""
---
# 2. Regímenes y enfermedades de la ciudad (2012-2024)

Con las familias de enfermedad de la vigilancia de Manizales se estimó el efecto de estar en cada estado, con mes fijo y
**tendencia lineal en lugar de año fijo** (un El Niño dura un año y el año fijo se lo comería). El efecto se
expresa en desviaciones típicas del índice de la familia; el punto marca los que sobreviven a la corrección
Benjamini-Hochberg (q < 0,10).
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
        lo, hi = r.conf_int().loc["x"]
        filas.append({"estado": c, "efecto": r.params["x"], "lo": lo, "hi": hi, "p": r.pvalues["x"], "semanas en el estado": int((D.x > 0).sum())})
    T = pd.DataFrame(filas)
    if len(T): T["q"] = multipletests(T.p, method="fdr_bh")[1]
    return T
RF = {fam: efecto(FAM[fam], W.drop(columns=["crisis_red"])) for fam in FAM}
M = pd.DataFrame({fam: T.set_index("estado")["efecto"] for fam, T in RF.items()})
Q = pd.DataFrame({fam: T.set_index("estado")["q"] for fam, T in RF.items()})
fig, ax = plt.subplots(figsize=(12, 4.2))
v = np.nanmax(np.abs(M.values)); im = ax.imshow(M.values, cmap="RdBu_r", vmin=-v, vmax=v, aspect="auto")
ax.set_xticks(range(M.shape[1])); ax.set_xticklabels([c.replace("_", " ") for c in M.columns], rotation=30, ha="right")
ax.set_yticks(range(M.shape[0])); ax.set_yticklabels([i.replace("_", " ") for i in M.index]); ax.grid(False)
for i in range(M.shape[0]):
    for j in range(M.shape[1]):
        x = M.values[i, j]
        if not np.isnan(x): ax.text(j, i, f"{x:+.2f}" + (" ●" if Q.values[i, j] < .10 else ""), ha="center", va="center", fontsize=8.5, color="white" if abs(x) > v * .6 else TINTA)
plt.colorbar(im, ax=ax, label="efecto (desviaciones típicas del índice)"); ax.set_title("Qué familias de enfermedad mueve cada estado, 2012-2024 (● q < 0,10)"); plt.tight_layout(); plt.show()
""")
lec("ciudad")

md(r"""
---
# 3. Regímenes y triage del hospital (2022-2024)

El desenlace es el triage semanal sin calendario ni escalones de la red, y el efecto se expresa en porcentaje del
triage con su intervalo de confianza al 95 %.
""")
code(r"""
y = desenlace_semanal().y.loc[:ix.REF_FIN]
TH = efecto(y, W)
for c in ["efecto", "lo", "hi"]: TH[c + " %"] = 100 * (np.exp(TH[c]) - 1)
fig, ax = plt.subplots(figsize=(10, 3.8)); TT = TH.iloc[::-1].reset_index(drop=True)
col = [ROJO if q < .10 else MUDO for q in TT.q]
ax.hlines(TT.index, TT["lo %"], TT["hi %"], color=col, lw=2.2); ax.scatter(TT["efecto %"], TT.index, color=col, zorder=3, s=36)
ax.axvline(0, color=TINTA, lw=.8); ax.set_yticks(TT.index); ax.set_yticklabels([f"{e.replace('_', ' ')}  ({n} sem.)" for e, n in zip(TT.estado, TT["semanas en el estado"])])
ax.set_xlabel("efecto sobre el triage semanal (%), IC 95 % HAC"); ax.set_title("Solo El Niño se separa de cero en el triage del hospital (rojo: q < 0,10)"); plt.tight_layout(); plt.show()
TH[["estado", "efecto %", "lo %", "hi %", "p", "q", "semanas en el estado"]].round(3)
""")
lec("hospital")

md(r"""
---
# 4. El terremoto del 10 de agosto de 2026 como episodio

Un evento único no tiene muestra para un coeficiente, pero sí se puede medir con un diseño de episodio: cada día posterior
al sismo se compara con la **mediana del mismo día de la semana en las 8 semanas anteriores**, sin festivos, vísperas,
puentes ni temporadas atípicas. Así el calendario queda controlado sin ajustar ningún modelo. Para saber si lo observado
es grande o es ruido, el mismo procedimiento se aplica a cada día de 2022-03 a 2026-07 como si fuera un sismo
(1.460 pseudoepisodios): esa distribución es la vara del azar. El sismo tuvo magnitud 7,4, epicentro en el Chocó y
profundidad intermedia; el catálogo de desastres registra para Manizales alerta roja y daños menores sin afectación
estructural en el hospital, que atendió heridos con áreas de expansión y canceló la consulta programada.
""")
code(r"""
cal = pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
atip = ((cal.es_festivo == 1) | (cal.es_vispera_festivo == 1) | (cal.es_post_festivo == 1) | (cal.es_puente == 1) | (cal.es_semana_santa == 1) | (cal.es_temporada_navidad == 1))
def _normal(idx): return ~atip.reindex(idx).fillna(False).values
def base(X, ev, semanas=8):
    # mediana por día de la semana de las `semanas` previas al evento, solo días normales (X: Series o DataFrame)
    pre = X.loc[ev - pd.Timedelta(days=7 * semanas):ev - pd.Timedelta(days=1)]; pre = pre[_normal(pre.index)]
    return pre.groupby(pre.index.dayofweek).median()
def rel(X, ev, ks, semanas=8):
    # cociente día/base - 1 para los días ev+k (X: Series); NaN en días atípicos o sin dato
    b = base(X, ev, semanas); out = {}
    for k in ks:
        d = ev + pd.Timedelta(days=k)
        ok = d in X.index and not atip.get(d, False) and d.dayofweek in b.index
        out[k] = (X.loc[d] / b.loc[d.dayofweek] - 1) if ok else np.nan
    return pd.Series(out)
def ventana(X, ev, a, b, semanas=8):
    # suma observada / suma esperada - 1 en los días normales de ev+a..ev+b (por columna si X es DataFrame)
    bs = base(X, ev, semanas); obs = esp = None
    for k in range(a, b + 1):
        d = ev + pd.Timedelta(days=k)
        if d not in X.index or atip.get(d, False) or d.dayofweek not in bs.index or np.all(pd.isna(X.loc[d])): continue
        o, e = X.loc[d], bs.loc[d.dayofweek]
        obs = o if obs is None else obs + o; esp = e if esp is None else esp + e
    return np.nan if obs is None else obs / esp - 1
EV = pd.Timestamp("2026-08-10")
PSEUDO = [d for d in pd.date_range("2022-03-01", "2026-07-15") if d.dayofweek < 7]
r_ev = rel(t, EV, range(-14, 36))
pl_dia = pd.Series({d: rel(t, d, [0])[0] for d in PSEUDO}).dropna()
lo5, hi95 = pl_dia.quantile(.05), pl_dia.quantile(.95)
fig, ax = plt.subplots(figsize=(14, 4.2))
ax.axhspan(100 * lo5, 100 * hi95, color="#e6e5e1", zorder=0, label="rango del 90 % de un día cualquiera (azar)")
cols = [NARANJA if k >= 0 else MUDO for k in r_ev.index]
ax.bar(r_ev.index, 100 * r_ev.values, color=cols, width=.8); ax.axhline(0, color=TINTA, lw=.8); ax.axvline(-.5, color=ROJO, ls=":", lw=1)
ax.set_xlabel("días desde el sismo (0 = 2026-08-10; vacíos: festivos y vísperas)"); ax.set_ylabel("triage vs. esperado (%)")
ax.set_title("El día del sismo el triage cayó a la mitad y la caída se fue absorbiendo en dos semanas"); ax.legend(loc="lower right"); plt.tight_layout(); plt.show()
resumen_ev = pd.Series({"día 0": r_ev[0], "días 1-7": ventana(t, EV, 1, 7), "días 8-21": ventana(t, EV, 8, 21), "días 0-13": ventana(t, EV, 0, 13)}) * 100
sens = pd.DataFrame({f"base de {w} semanas": {"día 0": 100 * rel(t, EV, [0], w)[0], "días 1-7": 100 * ventana(t, EV, 1, 7, w), "días 8-21": 100 * ventana(t, EV, 8, 21, w)} for w in (4, 6, 8, 10)})
pl_sem = pd.Series({d: ventana(t, d, 1, 7) for d in PSEUDO}).dropna()
print(f"Percentil del sismo entre {len(pl_sem)} pseudoepisodios, días 1-7: {100 * (pl_sem <= resumen_ev['días 1-7'] / 100).mean():.2f} %  (media del azar {100 * pl_sem.mean():+.1f} %, desv. {100 * pl_sem.std():.1f} puntos)")
print(f"Peor día de los {len(pl_dia)} pseudoepisodios (día 0): {100 * pl_dia.min():.1f} %;  percentil 5 de un día cualquiera: {100 * lo5:.1f} %")
display(resumen_ev.round(1).to_frame("%").T); display(sens.round(1))
""")
lec("ev_dias")

code(r"""
h = pd.read_parquet(RAIZ / "salidas/triage_horario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
H = h.pivot_table(index="dia", columns="hora", values="triages", aggfunc="sum").reindex(t.index).fillna(0); H[t.isna()] = np.nan
BLQ = {f"{a:02d}-{a + 2:02d} h": list(range(a, a + 3)) for a in range(0, 24, 3)}
HB = pd.DataFrame({k: H[v].sum(axis=1) for k, v in BLQ.items()})
b0 = base(H, EV).loc[EV.dayofweek]
fig, axes = plt.subplots(1, 2, figsize=(14, 4), gridspec_kw={"width_ratios": [1.1, 1]})
ax = axes[0]; ax.plot(range(24), b0.values, color=MUDO, lw=2, marker="o", ms=4, label="esperado (mediana de 8 lunes normales)")
ax.plot(range(24), H.loc[EV].values, color=NARANJA, lw=2, marker="o", ms=4, label="2026-08-10"); ax.fill_between(range(24), b0.values, H.loc[EV].values, where=H.loc[EV].values < b0.values, color=NARANJA, alpha=.15)
ax.set_xlabel("hora del día"); ax.set_ylabel("triages por hora"); ax.set_xticks(range(0, 24, 3)); ax.set_title("El día del sismo se vació la mañana"); ax.legend()
rb = pd.DataFrame({"día 0": ventana(HB, EV, 0, 0), "días 1-5": ventana(HB, EV, 1, 5)}) * 100
ax = axes[1]; x = np.arange(len(rb)); ax.bar(x - .2, rb["día 0"], .4, color=NARANJA, label="día 0"); ax.bar(x + .2, rb["días 1-5"], .4, color=AQUA, label="días 1-5 (normales)")
ax.set_xticks(x); ax.set_xticklabels(rb.index, rotation=45, ha="right"); ax.axhline(0, color=TINTA, lw=.8); ax.set_ylabel("vs. esperado (%)"); ax.set_title("Déficit por franja horaria"); ax.legend(); plt.tight_layout(); plt.show()
cnt = pd.DataFrame({"esperado": b0.groupby(np.arange(24) // 3).sum().values, "observado": H.loc[EV].groupby(np.arange(24) // 3).sum().values}, index=rb.index).round(1).T
cnt
""")
lec("ev_hora")

code(r"""
E = pd.read_parquet(RAIZ / "salidas/triage_edad.parquet").assign(dia=lambda d: pd.to_datetime(d.dia)).pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").reindex(t.index).fillna(0)
E[t.isna()] = np.nan; E = E[["0-4", "5-14", "15-44", "45-64", "65-+"]]; E["0-14"] = E["0-4"] + E["5-14"]
BANDAS = ["0-14", "15-44", "45-64", "65-+"]; VENT = [("día 0", 0, 0), ("días 1-7", 1, 7), ("días 8-21", 8, 21)]
pse_e = {nm: pd.DataFrame({d: ventana(E[BANDAS], d, a, b) for d in PSEUDO[::2]}).T.dropna() for nm, a, b in VENT}
fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)
for ax, (nm, a, b) in zip(axes, VENT):
    obs = 100 * ventana(E[BANDAS], EV, a, b); q5 = 100 * pse_e[nm].quantile(.05); q95 = 100 * pse_e[nm].quantile(.95)
    for i, bd in enumerate(BANDAS): ax.vlines(i, q5[bd], q95[bd], color="#c9c8c4", lw=12, zorder=0)
    ax.bar(range(len(BANDAS)), obs.values, width=.45, color=[NARANJA if o < q5[bd] else MUDO for o, bd in zip(obs.values, BANDAS)], zorder=2)
    ax.axhline(0, color=TINTA, lw=.8); ax.set_xticks(range(len(BANDAS))); ax.set_xticklabels(BANDAS); ax.set_title(nm); ax.set_xlabel("banda de edad (años)")
axes[0].set_ylabel("triage vs. esperado (%)"); fig.suptitle("Firma por edad del terremoto (barra) frente al rango del 90 % del azar (franja gris)", fontsize=11, fontweight="bold", color=TINTA); plt.tight_layout(); plt.show()
n_ed = pd.DataFrame({nm: ventana(E[BANDAS], EV, a, b) * 100 for nm, a, b in VENT}).round(1)
vol = pd.DataFrame({"triages/día normal (8 sem. previas)": [base(E[bd], EV).mean() for bd in BANDAS]}, index=BANDAS).round(1)
display(n_ed.join(vol)); print("Dos semanas (días 0-13), 0-14 años:", round(100 * ventana(E[["0-14"]], EV, 0, 13)["0-14"], 1), " %;  total:", round(100 * ventana(t, EV, 0, 13), 1), " %")
""")
lec("ev_edad")

md(r"""
---
# 5. Los sismos fuertes como clase de eventos (2020-2026)

El terremoto es excepcional. Lo que sí se repite son los sismos de M ≥ 4,5 a menos de 150 km, y con ellos hay muestra
suficiente. Cada uno se trata como un episodio con el mismo diseño de la sección anterior y se promedian las curvas.
""")
code(r"""
sis = pd.read_csv(RAIZ / "calendarios/sismos_usgs.csv", parse_dates=["fecha"])
sis = sis[(sis.mag >= 4.5) & (sis.fecha >= "2020-04-15") & (sis.fecha != "2026-08-10") & (sis.fecha <= "2026-08-09")]
fechas = sorted(sis.fecha.unique()); KS = range(-7, 15)
MS = pd.DataFrame({pd.Timestamp(d): rel(t, pd.Timestamp(d), KS) for d in fechas}).T
mu = MS.mean(); se = MS.std() / np.sqrt(MS.count()); n = MS.count()
fig, ax = plt.subplots(figsize=(14, 4.2))
for _, f in MS.iterrows(): ax.plot(MS.columns, 100 * f.values, color="#c9c8c4", lw=.7, alpha=.8)
ax.fill_between(MS.columns, 100 * (mu - 1.96 * se), 100 * (mu + 1.96 * se), color=VIOLETA, alpha=.2, lw=0, label="IC 95 % de la media")
ax.plot(MS.columns, 100 * mu, color=VIOLETA, lw=2.2, marker="o", ms=4, label=f"media de {len(MS)} sismos"); ax.axhline(0, color=TINTA, lw=.8); ax.axvline(-.5, color=ROJO, ls=":", lw=1)
ax.set_ylim(-45, 45); ax.set_xlabel("días desde el sismo"); ax.set_ylabel("triage vs. esperado (%)"); ax.set_title("Tras un sismo fuerte cercano el triage promedio no se mueve de cero"); ax.legend(loc="upper right"); plt.tight_layout(); plt.show()
sem1 = pd.Series({pd.Timestamp(d): ventana(t, pd.Timestamp(d), 1, 7) for d in fechas}).dropna(); dia0 = MS[0].dropna()
mag = sis.set_index("fecha").mag
print(f"{len(MS)} sismos; día 0: media {100 * dia0.mean():+.1f} % (IC95 {100 * (dia0.mean() - 1.96 * dia0.std() / np.sqrt(len(dia0))):+.1f} a {100 * (dia0.mean() + 1.96 * dia0.std() / np.sqrt(len(dia0))):+.1f}); "
      f"días 1-7: media {100 * sem1.mean():+.1f} % (IC95 {100 * (sem1.mean() - 1.96 * sem1.std() / np.sqrt(len(sem1))):+.1f} a {100 * (sem1.mean() + 1.96 * sem1.std() / np.sqrt(len(sem1))):+.1f}), mediana {100 * sem1.median():+.1f} %")
fuertes = sis.sort_values("mag", ascending=False).head(5).assign(dia0=lambda d: [100 * rel(t, pd.Timestamp(f), [0])[0] for f in d.fecha], d1_7=lambda d: [100 * ventana(t, pd.Timestamp(f), 1, 7) for f in d.fecha])
fuertes[["fecha", "mag", "place", "dia0", "d1_7"]].assign(place=lambda d: d.place.str.replace("�", "")).round(1).rename(columns={"dia0": "día 0 (%)", "d1_7": "días 1-7 (%)"})
""")
lec("sismos")

md(r"""
---
# 6. El paro nacional de 2021 y los desastres de la ciudad

Mismo diseño de episodio. El paro se mide desde su inicio (2021-04-28) con ventana larga, porque duró siete semanas y
ocurrió dentro de la fase parcial de la COVID. Los desastres con fecha exacta se miran uno por uno; el
deslizamiento del barrio Centenario (febrero de 2022, tres fallecidos) no tiene día exacto en el catálogo y por eso no
se puede medir como episodio.
""")
code(r"""
PARO = pd.Timestamp("2021-04-28")
rp = rel(t, PARO, range(-28, 77)); sem = pd.Series({k: ventana(t, PARO, 7 * k, 7 * k + 6) for k in range(-4, 11)})
pl_par = pd.Series({d: ventana(t, d, 0, 13) for d in pd.date_range("2020-10-01", "2022-01-01")}).dropna()
fig, axes = plt.subplots(1, 2, figsize=(14, 4), gridspec_kw={"width_ratios": [1.5, 1]})
ax = axes[0]; ax.axvspan(0, 48, color=NARANJA, alpha=.1, lw=0); ax.bar(rp.index, 100 * rp.values, color=[NARANJA if k >= 0 else MUDO for k in rp.index], width=.85); ax.axhline(0, color=TINTA, lw=.8)
ax.set_xlabel("días desde el inicio del paro (2021-04-28); franja: duración del paro (hasta el 15 de junio)"); ax.set_ylabel("triage vs. esperado (%)"); ax.set_title("Paro nacional: caída al inicio y repunte posterior")
ax = axes[1]; ax.bar(sem.index, 100 * sem.values, color=[NARANJA if 0 <= k <= 6 else MUDO for k in sem.index]); ax.axhline(0, color=TINTA, lw=.8); ax.set_xlabel("semanas desde el inicio"); ax.set_ylabel("vs. esperado (%)"); ax.set_title("Por semana"); plt.tight_layout(); plt.show()
print(f"Paro, semana 0: {100 * sem[0]:+.1f} %; semanas 1-2: {100 * ventana(t, PARO, 7, 20):+.1f} %; semanas 4-6: {100 * ventana(t, PARO, 28, 48):+.1f} %.  Azar en la COVID (ventanas de 14 días, oct-2020 a ene-2022): media {100 * pl_par.mean():+.1f} %, 5-95 %: {100 * pl_par.quantile(.05):+.1f} a {100 * pl_par.quantile(.95):+.1f} %")
""")
lec("paro")

code(r"""
DES = {"Alerta máxima por deslizamientos (2022-10-20)": "2022-10-20", "Alerta naranja del Nevado del Ruiz (2023-03-30)": "2023-03-30",
       "Movimientos en masa en vías (2025-04-08)": "2025-04-08", "Movimientos en masa y evacuación (2026-04-18)": "2026-04-18"}
fig, axes = plt.subplots(1, 4, figsize=(15, 3.6), sharey=True)
for ax, (nm, d) in zip(axes, DES.items()):
    d = pd.Timestamp(d); r = rel(t, d, range(-7, 22)); ax.bar(r.index, 100 * r.values, color=[AMARILLO if k >= 0 else MUDO for k in r.index], width=.85)
    ax.axhspan(100 * lo5, 100 * hi95, color="#e6e5e1", zorder=0); ax.axhline(0, color=TINTA, lw=.8); ax.set_title(nm, fontsize=8.5); ax.set_xlabel("días desde el evento")
axes[0].set_ylabel("triage vs. esperado (%)"); fig.suptitle("Desastres de la ciudad con fecha exacta: ninguno sale del rango del azar (franja gris)", fontsize=11, fontweight="bold", color=TINTA); plt.tight_layout(); plt.show()
filas = {nm: {"día 0": 100 * rel(t, pd.Timestamp(d), [0])[0], "días 1-7": 100 * ventana(t, pd.Timestamp(d), 1, 7), "días 8-21": 100 * ventana(t, pd.Timestamp(d), 8, 21)} for nm, d in DES.items()}
pd.DataFrame(filas).T.round(1)
""")
lec("desastres")

md(r"""
---
# 7. El Niño como hipótesis prospectiva

El Niño es el único estado que se separa de cero en el triage del hospital, y su evidencia es un solo episodio. La
sección 3 lo mostró; aquí se pone el episodio en contexto: el índice, su coincidencia con el pico de volumen y lo que
hoy está en curso.
""")
code(r"""
sem_t = t.resample("W-SAT").mean().loc["2022-03":"2026-09"]
fig, axes = plt.subplots(2, 1, figsize=(14, 5.2), sharex=True, gridspec_kw={"height_ratios": [1, 1.2]})
o = R.oni.loc["2022-03":"2026-09"]; axes[0].fill_between(o.index, 0, o, where=o > 0, color=ROJO, alpha=.6, lw=0); axes[0].fill_between(o.index, 0, o, where=o < 0, color=AZUL, alpha=.6, lw=0)
axes[0].axhline(.5, color=MUDO, ls=":", lw=.8); axes[0].set_ylabel("ONI (2 meses antes)"); axes[0].set_title("El Niño 2023-24 y el que está en curso")
axes[1].plot(sem_t.index, sem_t, color=TINTA, lw=1.4); axes[1].set_ylabel("triage/día, media semanal"); axes[1].set_title("Triage del hospital")
for ax in axes: ax.axvspan(pd.Timestamp("2023-08-01"), pd.Timestamp("2024-06-30"), color=ROJO, alpha=.06, lw=0)
plt.tight_layout(); plt.show()
anual = t.groupby([t.index.year, R.el_nino.reindex(t.index).map({1.0: "El Niño", 0.0: "sin El Niño"})]).mean().unstack().round(1).loc[2022:]
display(anual)
pd.read_csv(RAIZ / "calendarios/enso_oni.csv").tail(3)
""")
lec("nino")

md(r"""
---
# 8. Conclusiones y límites
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "20_regimenes_y_fenomenos.ipynb")
print("ok", len(C))
