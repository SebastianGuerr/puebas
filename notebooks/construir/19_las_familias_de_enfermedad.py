import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("19_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(sin escribir: {k})*"))

md(r"""
# 19 — Las familias de enfermedad: no solo IRA

## La pregunta y por qué importa

A Manizales no le dan solo problemas respiratorios. Una ciudad de ladera, con lluvia fuerte, sismos, violencia y
una red de salud que cambia de asegurador dominante, tiene varias enfermedades con calendarios y gatillos propios.
Si el modelo de triage solo conoce la IRA, tiene una sola señal para explicar picos que vienen de causas distintas.

Este cuaderno arma un repertorio de **seis familias de enfermedad** de la ciudad y responde cuatro preguntas:
cuándo sube cada una, si el clima las mueve, si el hospital las ve en su triage y, dentro de los episodios
concretos (epidemias, el paro nacional de 2021, los desastres), si hay efectos que un promedio de años diluye.

## Las seis familias

Se arman con las series semanales de Manizales del sistema de vigilancia en salud pública (SIVIGILA).

| Familia | Series | ¿Hay dato de 2026 al predecir? |
|---|---|---|
| **Respiratoria** | IRA total, IRA 0-4, IRA 60+, hospitalizaciones por IRAG | sí (tablero del INS, ~1 semana) |
| **Digestiva** | EDA total, EDA 0-4 | **no**: solo microdatos, con ~8 meses de retraso |
| **Violencias y agresiones** | violencia de género e intrafamiliar (875), agresiones por animales (300) | sí (tablero del INS) |
| **Salud mental e intoxicaciones** | intento de suicidio (356), intoxicaciones (365) | sí |
| **Materno-perinatal** | morbilidad materna extrema (549) | sí |
| **Inmunoprevenibles** | varicela (831) | sí |

Cada serie se convierte en una anomalía *operativa*: el logaritmo contra la media de las 52 semanas previas, que
es lo único que se sabría esa semana. Cada familia es el promedio de sus series estandarizadas, con la
estandarización ajustada solo con datos hasta 2024. La definición vive en el módulo compartido de índices, que usa
también el reentrenamiento, de modo que el modelo recibe exactamente lo que aquí se exploró.

**Límite de partida.** La familia digestiva no tiene datos de 2026: el INS publica los microdatos de la EDA con
unos ocho meses de retraso y el tablero semanal no la incluye. Sirve para explicar y medir, pero no para operar, y
todo este cuaderno se limita a 2012-2024.
""")

code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, statsmodels.api as sm
from scipy.stats import poisson
from statsmodels.stats.multitest import multipletests
warnings.filterwarnings("ignore")
from matplotlib import pyplot as plt
import indices as ix
import desenlace as dz
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
FAM_C = ix.familias_enfermedad().loc["2012":FIN]                 # con la COVID, para los episodios
FAM = ix.familias_enfermedad().loc[:FIN]
FAM[(FAM.index >= "2020-03-15") & (FAM.index <= "2021-12-31")] = np.nan      # la COVID desordena la notificacion
S = ix.series_sivigila().loc["2012":FIN]
print("Casos o consultas totales 2012-2024 por serie:"); S.sum().astype(int).sort_values(ascending=False)
""")

md(r"""
---
# 1. La estación de cada familia

Para cada serie se resta la media de su propio año (la forma del año, sin el nivel de cada año) y se promedia por
mes sobre 2015-2024, sin las semanas de la COVID (2020-03-15 a 2021-12-31), que desordenaron la notificación.
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
plt.colorbar(im, ax=ax, label="% frente a la media del año"); ax.set_title("Cada familia tiene su estación: el mes en que sube y el mes en que baja (2015-2024, sin la COVID)")
plt.tight_layout(); plt.show()
pd.DataFrame({"mes más alto": [MESES[int(np.argmax(r))] for r in H.values], "% en ese mes": H.max(axis=1).round(0).values,
              "mes más bajo": [MESES[int(np.argmin(r))] for r in H.values], "% en ese mes ": H.min(axis=1).round(0).values}, index=H.index)
""")
lec("estacion")

md(r"""
---
# 2. Correlación entre familias, semana a semana

Si las familias se movieran juntas, seis índices serían uno solo repetido. Se mide la correlación de las
anomalías semanales (2012-2024, sin la COVID).
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

Cada prueba es `desenlace(t) ~ familia(t − rezago) + mes + año`, con rezago de 0 a 4 semanas, errores robustos a
la autocorrelación (HAC) y corrección de Benjamini-Hochberg con q = 0,10 dentro de cada desenlace.
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
            D = D.loc[:, (D != 0).any()]                                     # un ano sin semanas validas deja una columna de ceros
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
plt.colorbar(im, ax=ax, label="% por desv. típica de la familia"); ax.set_title("Contra el hospital, el efecto de cada familia es pequeño y pocos efectos sobreviven (● = pasa BH)")
plt.tight_layout(); plt.show()
pd.concat({k: T[T.q < .10].sort_values("p")[["familia", "rezago", "efecto %", "q", "n"]] for k, T in RES.items()}).round(3)
""")
code(r"""
# lo que dice la familia respiratoria de la ciudad sobre el respiratorio del hospital, rezago por rezago
T = RES["ingresos respiratorio"]; T[T.familia == "respiratoria"].round(3)
""")
lec("hospital")

md(r"""
---
# 4. Clima y familia: el primer eslabón de la cadena

La cadena «factor externo → enfermedad en la ciudad → demanda del hospital» empieza aquí: ¿qué familias responden
al clima? Se usan los índices de clima del cuaderno 17 (cuatro de estado, tres de cambio brusco, la racha seca y
los días desde la última semana muy lluviosa), 2012-2024, con rezagos de 0 a 6 semanas.
""")
code(r"""
IC = ix.indices_clima()
RC = {fam: barrido(FAM[fam].dropna(), IC, range(0, 7)) for fam in FAM}
rc = pd.DataFrame({fam: {"pruebas": len(T), "sobreviven BH": int((T.q < .10).sum()),
                         "más fuerte": (lambda t: f"{t.familia} a {t.rezago} sem: {t['efecto %']:+.1f} %")(T.loc[T.p.idxmin()])} for fam, T in RC.items()}).T
rc
""")
code(r"""
fig, axes = plt.subplots(1, 2, figsize=(13, 4), sharey=False)
for ax, (fam, col, ind, tit) in zip(axes, [("digestiva", ROJO, "dias_desde_semana_muy_lluviosa", "Digestiva: más diarrea cuanto más tiempo sin una semana muy lluviosa"),
                                          ("respiratoria", AZUL, "racha_seca", "Respiratoria: menos IRA tras una racha seca")]):
    T = RC[fam]; T = T[T.familia == ind].sort_values("rezago")
    ax.bar(T.rezago, T["efecto %"], color=col, alpha=.85)
    ax.set_xticks(T.rezago, [f"{r}\n●" if q < .10 else f"{r}" for r, q in zip(T.rezago, T.q)])
    ax.axhline(0, color=MUDO, lw=.8); ax.set_xlabel("rezago (semanas); ● = pasa BH"); ax.set_ylabel("% por desviación típica"); ax.set_title(tit, fontsize=10)
plt.suptitle("Efecto del clima sobre el índice de la familia, por rezago (● = pasa BH)", y=1.02, fontsize=11, fontweight="bold"); plt.tight_layout(); plt.show()
""")
code(r"""
# las pruebas del clima que sobreviven a BH (q < 0,10), rezago por rezago, para cada familia
sob = pd.concat({fam: T[T.q < .10].sort_values(["familia", "rezago"])[["familia", "rezago", "efecto %", "p", "q"]].rename(columns={"familia": "índice de clima"}) for fam, T in RC.items()})
sob.round(3)
""")
lec("clima")

md(r"""
---
# 5. El efecto por banda de edad

Un efecto que afecta a los niños pequeños pesa poco sobre el total, porque los niños de 0 a 4 años son una
fracción pequeña del triage del hospital. Con los datos agregados por banda de edad (0-4, 5-14, 15-44, 45-64 y
65 o más) se pueden hacer dos comprobaciones.

**5.1** En la ciudad, la IRA y la EDA vienen separadas por grupo de edad: se mide si el clima las mueve igual.

**5.2** En el hospital, se repite la prueba de la familia contra el triage, pero con el desenlace de cada banda de
edad (sin calendario ni escalones de la red, 2022-2024, la misma construcción del triage total).
""")
code(r"""
def anom_est(s):
    z = ix.anomalia_operativa(s); z = (z - z.loc[:FIN].mean()) / z.loc[:FIN].std()
    z[(z.index >= "2020-03-15") & (z.index <= "2021-12-31")] = np.nan; return z.loc[:FIN]
EDAD = pd.DataFrame({"IRA 0-4": anom_est(S["995_consultas_ira_0_4"]), "IRA 60+": anom_est(S["995_consultas_ira_60_mas"]),
                     "IRA total": anom_est(S["995_consultas_ira_total"]), "EDA 0-4": anom_est(S["998_casos_eda_0_4"]),
                     "EDA total": anom_est(S["998_casos_eda_total"])})
print("Correlación semanal entre las series por edad:"); display(EDAD.corr().round(2))
RE = {c: barrido(EDAD[c].dropna(), IC, range(0, 7)) for c in EDAD}
pd.DataFrame({c: {"pruebas": len(T), "sobreviven BH": int((T.q < .10).sum()),
                  "más fuerte": (lambda t: f"{t.familia} a {t.rezago} sem: {t['efecto %']:+.1f} % (q = {t.q:.3f})")(T.loc[T.p.idxmin()])} for c, T in RE.items()}).T
""")
code(r"""
# el efecto de la racha seca, rezago por rezago, en la IRA de niños y de mayores
det = pd.concat({c: RE[c][RE[c].familia == "racha_seca"].set_index("rezago")[["efecto %", "q"]].round(3) for c in ["IRA 0-4", "IRA 60+", "IRA total"]}, axis=1)
det
""")
lec("edad_ciudad")

code(r"""
# triage por banda de edad: misma construcción que el triage total (sin calendario, sin escalones de la red, mismas semanas)
te = pd.read_parquet(RAIZ / "salidas/triage_edad.parquet"); te["dia"] = pd.to_datetime(te.dia)
dd = pd.date_range("2020-01-01", "2026-09-19")
tri = pd.read_parquet(RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia)).set_index("dia").triages.reindex(dd).astype(float)
tri["2024-03-19":"2024-03-21"] = np.nan                                  # caida del registro
cal = (pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha").reindex(dd)[dz.CAL]
         .apply(pd.to_numeric, errors="coerce").fillna(0))
completas = dz._semana(tri.notna().astype(int)) == 7
cal_w = dz._semana(cal).loc[dz.INICIO:dz.FIN]
BANDAS = ["0-4", "5-14", "15-44", "45-64", "65-+"]
Bd = {}
for b in BANDAS:
    s = te[te.banda.eq(b)].groupby("dia").n.sum().reindex(dd).fillna(0).astype(float); s[tri.isna()] = np.nan
    Bd[b] = dz._residuo(dz._semana(s).where(completas).loc[dz.INICIO:dz.FIN], cal_w).loc[:FIN]
Bd = pd.DataFrame(Bd)
peso = (te[te.banda.isin(BANDAS)].groupby("banda").n.sum() / te[te.banda.isin(BANDAS)].n.sum() * 100).reindex(BANDAS).round(1)
RB = {b: barrido(Bd[b], FAM) for b in BANDAS}
print("Peso de cada banda en el triage 2020-2026 (%):"); display(peso.to_frame("% del triage").T)
pd.DataFrame({b: {"semanas": int(Bd[b].notna().sum()), "pruebas": len(T), "p < 0,05": int((T.p < .05).sum()),
                  "azar esperaría": round(.05 * len(T), 1), "sobreviven BH": int((T.q < .10).sum())} for b, T in RB.items()}).T
""")
code(r"""
fig, ax = plt.subplots(figsize=(10, 4.2))
M2 = pd.DataFrame({b: T.loc[T.groupby("familia")["p"].idxmin()].set_index("familia")["efecto %"] for b, T in RB.items()})
Q2 = pd.DataFrame({b: T.loc[T.groupby("familia")["p"].idxmin()].set_index("familia")["q"] for b, T in RB.items()})
lim = np.nanmax(np.abs(M2.values))
im = ax.imshow(M2.values, cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
for (i, j), v in np.ndenumerate(M2.values): ax.text(j, i, f"{v:+.1f}{'●' if Q2.values[i, j] < .10 else ''}", ha="center", va="center", fontsize=8)
ax.set_xticks(range(M2.shape[1]), [f"{b}\n({peso[b]} %)" for b in M2.columns]); ax.set_yticks(range(M2.shape[0]), [f.replace("_", " ") for f in M2.index])
plt.colorbar(im, ax=ax, label="% por desv. típica de la familia"); ax.set_xlabel("banda de edad del triage (peso en el triage total)")
ax.set_title("Por edad, la respiratoria pesa en los niños de 0 a 4 y la digestiva en los adultos (● = pasa BH)")
plt.tight_layout(); plt.show()
pd.concat({b: T[T.q < .10].sort_values("p")[["familia", "rezago", "efecto %", "q", "n"]] for b, T in RB.items()}).round(3)
""")
lec("edad_hospital")

code(r"""
# la serie por edad que corresponde a cada banda (0-4 con IRA 0-4; 65+ con IRA 60+): una sola prueba por banda, a rezagos 0-4
pares = {"0-4": "IRA 0-4", "65-+": "IRA 60+"}
filas = []
for b, c in pares.items():
    T = barrido(Bd[b], EDAD[[c]].dropna())
    for _, r in T.iterrows(): filas.append({"banda": b, "serie": c, "rezago": int(r.rezago), "efecto %": round(r["efecto %"], 2), "p": round(r.p, 3)})
PAR = pd.DataFrame(filas); PAR["q (10 pruebas)"] = multipletests(PAR.p, method="fdr_bh")[1].round(3)
PAR
""")
lec("edad_pares")

md(r"""
---
# 6. Episodios: epidemias y otras enfermedades de Manizales

El promedio de trece años de datos mezcla meses sin nada con semanas en que ocurre algo. Un efecto que dura siete
semanas y ocurre una vez desaparece en una regresión de todo el periodo. Aquí se toman episodios concretos y se
trata cada uno con la pregunta del mecanismo: qué reloj tiene, qué lo dispara, bajo qué condición y en quién.

## 6.1 Varicela durante el paro nacional de 2021

En el cuaderno 20 el paro nacional (2021-04-28 a 2021-06-15) aparecía asociado a más varicela (+0,67 desviaciones
típicas). Un efecto grande, sobre una sola ventana. Se revisa de tres maneras: se reproduce, se compara con los
conteos crudos y se pregunta cuánto efecto producirían ventanas del mismo tamaño puestas al azar en la serie.
""")
code(r"""
R = ix.regimenes_diarios()
W = R.resample("W-SAT").mean(); W.index -= pd.Timedelta(days=6)
def ajuste(y, x, maxlags=8):
    # efecto del estado x sobre el índice y, con mes fijo y tendencia lineal (un estado largo no cabe con año fijo)
    idx = y.dropna().index
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    tend = pd.Series(np.arange(len(idx)) / 52, index=idx, name="tendencia")
    D = pd.concat([y.rename("y"), x.rename("x"), mes, tend], axis=1).loc[idx].dropna()
    r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    return r.params["x"], r.pvalues["x"], int((D.x > 0).sum())
def permutar(y, x, margen=26):
    # desplaza circularmente el estado por toda la serie: conserva su duración y su forma, rompe su fecha
    idx = y.dropna().index; v = x.reindex(idx).fillna(0).values
    return np.array([ajuste(y, pd.Series(np.roll(v, k), index=idx))[0] for k in range(margen, len(idx) - margen)])
yv = FAM_C["inmunoprevenibles"]
b_paro, p_paro, n_paro = ajuste(yv, W.paro_nacional_2021)
perm_paro = permutar(yv, W.paro_nacional_2021)
v = S["831_casos"]; en_paro = pd.Series((v.index >= "2021-04-25") & (v.index <= "2021-06-13"), index=v.index)
cont = {"semanas del paro 2021": v[en_paro].mean(), "resto de 2021": v["2021"][~en_paro["2021"]].mean()}
for a in (2019, 2020, 2021, 2022): cont[f"promedio de todo {a}"] = v[str(a)].mean()
cont["ene-jun de 2021"] = v["2021-01":"2021-06"].mean(); cont["jul-dic de 2021"] = v["2021-07":"2021-12"].mean()
for a in (2022, 2023, 2024):
    m = v[str(a)]; p = (m.index >= f"{a}-04-25") & (m.index <= f"{a}-06-13")
    cont[f"mismas semanas de {a}"] = m[p].mean(); cont[f"resto de {a}"] = m[~p].mean()
print(f"Efecto reproducido del paro sobre el índice de inmunoprevenibles: {b_paro:+.2f} desv. típicas (p = {p_paro:.3f}), {n_paro} semanas con paro")
print(f"Con la misma ventana desplazada por toda la serie: efecto ≥ al observado en el {100*(perm_paro >= b_paro).mean():.1f} % de las posiciones (de {len(perm_paro)}); desv. típica del efecto al azar = {perm_paro.std():.2f}")
print(f"Efecto en valor absoluto ≥ al observado: {100*(np.abs(perm_paro) >= abs(b_paro)).mean():.1f} %")
pd.Series(cont, name="casos de varicela por semana").round(2).to_frame()
""")
code(r"""
fig, axes = plt.subplots(1, 2, figsize=(14, 4), gridspec_kw={"width_ratios": [1.6, 1]})
ax = axes[0]; vv = S["831_casos"].loc["2017":"2024"]
ax.plot(vv.index, vv.values, color=VIOLETA, lw=1.1); ax.axvspan(pd.Timestamp("2021-04-28"), pd.Timestamp("2021-06-15"), color=NARANJA, alpha=.3, label="paro nacional")
ax.set_ylabel("casos de varicela por semana"); ax.set_title("La varicela cayó a 2-3 casos por semana en 2020-2021 y el paro cae sobre ese piso"); ax.legend(loc="upper right")
ax = axes[1]; ax.hist(perm_paro, bins=40, color=MUDO, alpha=.8); ax.axvline(b_paro, color=NARANJA, lw=2, label=f"paro observado ({b_paro:+.2f})")
ax.set_xlabel("efecto de una ventana de 8 semanas puesta al azar (desv. típicas)"); ax.set_ylabel("posiciones"); ax.set_title("Con ventanas al azar sale lo mismo"); ax.legend()
plt.tight_layout(); plt.show()
""")
lec("varicela")

md(r"""
## 6.2 Salud mental con los desastres

El mismo cuaderno 20 asoció los desastres catalogados con más salud mental (+0,36). Antes de tomarlo como
hallazgo hay que separar qué es cada episodio, porque el catálogo mezcla eventos de un día confirmados, alertas
regionales de meses y temporadas de lluvias cuya fecha y cifras todavía no están verificadas.
""")
code(r"""
de = pd.read_csv(RAIZ / "calendarios/desastres_manizales_2020_2026.csv")
de = de[pd.to_datetime(de.fecha_inicio) < "2025-01-01"]
dd_ = pd.date_range("2010-01-01", "2026-09-30")
def ventana(df):
    s = pd.Series(0.0, index=dd_)
    for _, r in df.iterrows():
        a = pd.Timestamp(r.fecha_inicio); b = pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else a; s[a:b] = 1
    w = s.resample("W-SAT").mean(); w.index -= pd.Timedelta(days=6); return w
conf = de[de.calidad_dato.eq("confirmado")]; sin = de[~de.calidad_dato.eq("confirmado")]
Wc, Ws = ventana(conf), ventana(sin)
ym = FAM_C["salud_mental_e_intoxicaciones"]
filas = []
for nom, x in [("todos los desastres catalogados", W.desastre_activo), (f"solo confirmados ({len(conf)} registros)", Wc), (f"fecha aproximada o por verificar ({len(sin)} registros)", Ws)]:
    b, p, n = ajuste(ym, x.reindex(ym.index).fillna(0)); filas.append({"estado": nom, "efecto (desv. típicas)": round(b, 2), "p": round(p, 3), "semanas": n})
for ev, nom in [("356_casos", "intento de suicidio"), ("365_casos", "intoxicaciones")]:
    z = ix.anomalia_operativa(S[ev]); z = ((z - z.loc[:FIN].mean()) / z.loc[:FIN].std()).loc["2012":FIN]
    b, p, n = ajuste(z, W.desastre_activo); filas.append({"estado": f"todos los desastres, solo {nom}", "efecto (desv. típicas)": round(b, 2), "p": round(p, 3), "semanas": n})
perm_des = permutar(ym, W.desastre_activo); b_des = ajuste(ym, W.desastre_activo)[0]
print(f"Desplazando el estado por toda la serie: efecto ≥ al observado ({b_des:+.2f}) en el {100*(perm_des >= b_des).mean():.1f} % de las posiciones; en valor absoluto, {100*(np.abs(perm_des) >= abs(b_des)).mean():.1f} %")
print("Registros confirmados hasta 2024:"); display(conf[["fecha_inicio", "fecha_fin", "tipo_evento", "subtipo", "ambito"]])
pd.DataFrame(filas)
""")
code(r"""
# estudio de eventos: el indice de salud mental de 4 semanas antes a 8 despues del inicio de cada episodio confirmado
EP = {"2022-10-20 movimientos en masa": "2022-10-20", "2023-03-24 alerta del volcán": "2023-03-24", "2024-07-05 movimiento en masa": "2024-07-05"}
fig, axes = plt.subplots(1, 2, figsize=(14, 4), gridspec_kw={"width_ratios": [1.6, 1]})
ax = axes[0]; sub = ym.loc["2019":"2024"]
ax.plot(sub.index, sub.rolling(4, min_periods=2).mean(), color=VIOLETA, lw=1.2)
for _, r in sin.iterrows(): ax.axvspan(pd.Timestamp(r.fecha_inicio), pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else pd.Timestamp(r.fecha_inicio) + pd.Timedelta(days=7), color=AMARILLO, alpha=.25)
for _, r in conf.iterrows(): ax.axvspan(pd.Timestamp(r.fecha_inicio), (pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else pd.Timestamp(r.fecha_inicio)) + pd.Timedelta(days=7), color=ROJO, alpha=.35)
ax.axhline(0, color=MUDO, lw=.8); ax.set_ylabel("índice de salud mental (media de 4 semanas)")
ax.set_title("Salud mental con los desastres: rojo confirmados, amarillo sin verificar")
ax = axes[1]; tabla = {}
for (nom, f), col in zip(EP.items(), [AZUL, AQUA, NARANJA]):
    a = pd.Timestamp(f); a = a - pd.Timedelta(days=(a.dayofweek + 1) % 7)
    ws = pd.date_range(a - pd.Timedelta(weeks=4), periods=13, freq="7D"); vals = ym.reindex(ws).values; tabla[nom] = vals
    ax.plot(range(-4, 9), vals, color=col, lw=1, alpha=.7, label=nom)
mm = np.nanmean(np.array(list(tabla.values())), axis=0); ax.plot(range(-4, 9), mm, color=TINTA, lw=2.4, label="media de los 3")
ax.axvline(0, color=MUDO, ls=":"); ax.set_xlabel("semanas desde el inicio del episodio"); ax.set_ylabel("índice (desv. típicas)"); ax.legend(fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)
ax.set_title("Cada episodio por separado"); plt.tight_layout(); plt.show()
print(f"Media del índice, 4 semanas antes: {np.nanmean(mm[:4]):+.2f}; semanas 0 a 8 después: {np.nanmean(mm[4:]):+.2f}")
for nom, vals in tabla.items(): print(f"{nom}: antes {np.nanmean(vals[:4]):+.2f}, después {np.nanmean(vals[4:]):+.2f}")
""")
lec("mental")

md(r"""
## 6.3 Epidemias: qué brotes tuvo Manizales y qué hizo el hospital

Para encontrar epidemias sin escogerlas a ojo, se aplica una regla fija a cada evento de notificación individual
con al menos 150 casos en la serie de Manizales: una semana es de exceso si su conteo tiene probabilidad de
Poisson menor de 0,001 frente a la media de las 52 semanas previas y supera a esa media en al menos 3 casos. Las
semanas de exceso separadas por tres semanas o menos forman un episodio. Se listan los de tres semanas o más.
""")
code(r"""
ev_ = pd.read_csv(RAIZ / "calendarios/vigilancia_sivigila_eventos.csv.gz", parse_dates=["fecha_inicio_semana"])
ev_ = ev_[ev_.ambito.eq("manizales") & ev_.variable.eq("casos_notificacion")]
P = ev_.drop_duplicates(["evento", "fecha_inicio_semana"]).pivot(index="fecha_inicio_semana", columns="evento", values="valor").sort_index()
NOM = {113: "desnutrición aguda <5", 155: "cáncer de mama y cuello uterino", 300: "agresiones por animales", 348: "IRAG inusitada", 356: "intento de suicidio",
       360: "intoxicación por plaguicidas", 365: "intoxicaciones", 370: "intoxicación por fármacos", 400: "intoxicación por solventes",
       410: "intoxicación por otras sustancias", 412: "intoxicación por monóxido", 414: "intoxicación por psicoactivas", 452: "lesiones por pólvora",
       549: "morbilidad materna extrema", 620: "parotiditis", 813: "tuberculosis", 820: "tuberculosis pulmonar", 831: "varicela",
       850: "VIH/SIDA", 875: "violencia de género e intrafamiliar", 346: "IRA por virus nuevo", 810: "tuberculosis extrapulmonar"}
filas = []; BASE = {}
for e_ in P:
    s = P[e_].dropna()
    if s.sum() < 150: continue
    base = s.shift(1).rolling(52, min_periods=40).mean(); BASE[e_] = base
    pv = 1 - poisson.cdf(s - 1, base.clip(lower=.2)); flag = (pv < 1e-3) & (s - base >= 3); f = flag[flag]
    if f.empty: continue
    grp = (f.index.to_series().diff() > pd.Timedelta(weeks=3)).cumsum()
    for _, g in f.groupby(grp.values):
        a, b = g.index[0], g.index[-1]; nsem = int((b - a).days // 7 + 1)
        filas.append({"evento": NOM.get(e_, str(e_)), "código": e_, "inicio": a.date(), "fin": b.date(), "semanas de exceso": len(g),
                      "casos": int(s[a:b].sum()), "esperados": round(float(base[a:b].mean() * nsem), 1)})
EPI = pd.DataFrame(filas); EPI["veces lo esperado"] = (EPI.casos / EPI.esperados).round(1)
print(f"Episodios de exceso detectados en total: {len(EPI)}; de 3 semanas o más: {(EPI['semanas de exceso'] >= 3).sum()}")
EPI[EPI["semanas de exceso"] >= 3].sort_values("inicio").reset_index(drop=True)
""")
code(r"""
fig, axes = plt.subplots(1, 3, figsize=(15, 4.2), gridspec_kw={"width_ratios": [1.2, .8, 1.3]})
ax = axes[0]; x1 = P[348].loc["2022-03":"2022-12"]; ax.bar(x1.index, x1.values, width=6, color=ROJO, alpha=.85)
ax.set_ylabel("casos notificados por semana"); ax.set_title("IRAG inusitada, 2022: diez semanas de brote", fontsize=10)
ax = axes[1]; x2 = P[346].loc["2023-12":"2024-04"]; ax.bar(x2.index, x2.values, width=6, color=AZUL, alpha=.85)
ax.set_title("IRA por virus nuevo, 2024: seis semanas", fontsize=10)
for a_ in axes[:2]: a_.tick_params(axis="x", rotation=30)
ax = axes[2]; EP3 = EPI[EPI["semanas de exceso"] >= 3].sort_values("inicio")
for i, (_, r) in enumerate(EP3.iterrows()):
    ax.plot([pd.Timestamp(r.inicio), pd.Timestamp(r.fin) + pd.Timedelta(days=6)], [i, i], lw=7, color=VIOLETA, solid_capstyle="butt")
    ax.text(pd.Timestamp(r.fin) + pd.Timedelta(days=80), i, f"{r.evento}  ({r['veces lo esperado']}x)", va="center", fontsize=8)
ax.set_yticks([]); ax.set_xlim(pd.Timestamp("2015-01-01"), pd.Timestamp("2027-06-01")); ax.invert_yaxis(); ax.set_title("Episodios de 3 semanas o más (x = veces lo esperado)", fontsize=10)
plt.tight_layout(); plt.show()
""")
lec("epidemias")

code(r"""
x1 = P[348].loc["2022-05":"2022-09"]; x2 = P[346].loc["2023-12":"2024-02"]
print(f"IRAG inusitada, mayo-septiembre de 2022: {int(x1.sum())} casos, máximo semanal {int(x1.max())} ({x1.idxmax().date()})")
print(f"IRA por virus nuevo, 2023-12-31 a 2024-02-11: {int(x2.loc[:'2024-02-11'].sum())} casos, máximo semanal {int(x2.max())} ({x2.idxmax().date()})")
# lo que ve el hospital: proporción de ingresos del capítulo respiratorio sobre todos los capítulos, por semana del año
dxs = dx.groupby("dia").n.sum().reindex(pd.date_range("2020-01-01", FIN)).fillna(0)
rs = dx[dx.capitulo == "X Respiratorio"].set_index("dia").n.reindex(dxs.index).fillna(0)
tot_s = ix.semana(dxs, "sum"); prop = (ix.semana(rs, "sum") / tot_s * 100)[tot_s > 0]
wk = pd.Series((prop.index.dayofyear - 1) // 7 + 1, index=prop.index); yr = prop.index.year       # semana de 7 dias contada desde el 1 de enero
fig, ax = plt.subplots(figsize=(12, 4))
for a, col in [(2022, ROJO), (2023, MUDO), (2024, AZUL)]:
    sel = (yr == a) & (wk <= 52); ax.plot(wk[sel].values, prop[sel].values, color=col, lw=1.6 if a != 2023 else 1.2, label=str(a))
ax.axvspan(23, 31, color=ROJO, alpha=.12, label="brote de IRAG de 2022"); ax.axvspan(1, 6, color=AZUL, alpha=.12, label="brote de 2024")
ax.set_xlabel("semana del año (bloques de 7 días desde el 1 de enero)"); ax.set_ylabel("% de los ingresos que son respiratorios"); ax.legend(ncol=5, fontsize=8)
ax.set_title("La proporción respiratoria del hospital sube a mitad de año en 2022 y 2023, y en enero de 2024")
plt.tight_layout(); plt.show()
def media_ep(a, s_ini, s_fin):
    sel = (yr == a) & (wk >= s_ini) & (wk <= s_fin); return prop[sel].mean()
pd.DataFrame({"semanas 23-31 (jun-jul)": [media_ep(a, 23, 31) for a in (2022, 2023, 2024)],
              "semanas 1-6 (ene-feb)": [media_ep(a, 1, 6) for a in (2022, 2023, 2024)],
              "resto del año": [prop[(yr == a) & ~wk.isin(list(range(1, 7)) + list(range(23, 32)))].mean() for a in (2022, 2023, 2024)]},
             index=[2022, 2023, 2024]).round(2)
""")
lec("epidemias_hospital")

md(r"""
---
# 7. Conclusiones y límites
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "19_las_familias_de_enfermedad.ipynb")
print("ok", len(C))
