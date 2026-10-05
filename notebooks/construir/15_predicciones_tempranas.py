import nbformat as nbf, json
from pathlib import Path
LJ = Path(__file__).with_name("15_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 15 — Predicciones tempranas: los primeros resultados reales

## El objetivo

> Predecir **cuántas solicitudes de triage llegarán al SES Hospital Universitario de Caldas**, como
> una **distribución** (un valor central y un rango). De ahí sale la **probabilidad de que el triage
> suba** por encima de lo que anuncia su calendario. Cada predicción lleva sus **razones**: qué del
> contexto interno y externo la mueve.

Es un solo proyecto. Los cuadernos 01-14 sirvieron para saber **con qué entrenar** y **cómo comprobar
la fiabilidad**. Este cuaderno junta las primeras predicciones reales, buenas o malas, para ver **cómo se
comporta hoy y qué falta**. No se espera que funcione a la primera. Si lo hiciera, habría que
sospechar.

## Lo que se decidió (docs/CONTEXTO.md, 2026-09-30 y 2026-10-01)

| | Decisión |
|---|---|
| **Qué se predice** | El conteo diario de triage a 1-7 días, el año completo y la hora de saturación |
| **Qué entrega** | Una **distribución** (9 cuantiles). La regresión es complemento, no método principal |
| **Qué es «subir»** | Pasar lo que anuncia el calendario. **Pico** = pasarlo en más de una desviación (≈ +11 %) |
| **Con qué se entrena** | **Todos los años con registro (2020-2026)**, con la COVID marcada, y **todo el contexto**: salud, clima, social, red de salud, catástrofes, eventos, ENSO. **Solo lo que se sabe el día de la predicción** |
| **Contra qué se prueba** | **2026**, con datos que el modelo nunca vio |
| **Qué modelos** | Todos en competencia: series de tiempo (SARIMAX, Prophet), modelo fundacional de series (Chronos-2), árboles (LightGBM), regresión binomial negativa, bases y MedGemma |
| **Confiabilidad esperada** | **60-70 %**. Por encima de eso hay que revisar el sobreentrenamiento o una fuga de información |

## Las tres pruebas

| Prueba | Pregunta | Cómo |
|---|---|---|
| **1. Corto plazo** | ¿Qué pasará los próximos 7 días? | Cada día de 2026, el modelo predice los 7 siguientes con lo que sabía hasta ayer |
| **2. El año a ciegas** | Desde diciembre de 2025: ¿cómo será cada mes de 2026? | Una sola predicción hecha el 31-12-2025 hasta septiembre |
| **3. La hora** | ¿A qué hora se satura el día predicho? | La predicción del día repartida con el perfil horario |

## Los tres experimentos, para saber qué aporta cada cosa

| | Años de entrenamiento | Contexto externo |
|---|---|---|
| **E0** | 2022-2024 (fase A) | no |
| **E1** | 2020-2025, con la COVID marcada | no |
| **E2** | 2020-2025, con la COVID marcada | **todo** |

E1 contra E0 dice qué aportan **más años**. E2 contra E1 dice qué aporta **el contexto**.

El motor está en `notebooks/pronostico.py` y las corridas largas escriben en `salidas/pronostico/`.
""")

code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
import statsmodels.api as sm
from matplotlib import pyplot as plt
import pronostico as pr

AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
COLOR = {"ingenuo": MUDO, "control": TINTA2, "glm_binneg": AZUL, "lightgbm": VERDE, "sarimax": VIOLETA,
         "prophet": AMARILLO, "chronos2": MAGENTA, "chronos2_cal": ROJO, "llm": NARANJA,
         "anio_pasado": MUDO, "regresion_anual": AZUL}
NOMBRE = {"ingenuo": "Ingenuo (semana pasada)", "control": "Control (calendario + nivel)", "glm_binneg": "Regresión binomial negativa",
          "lightgbm": "LightGBM (árboles)", "sarimax": "SARIMAX (serie de tiempo)", "prophet": "Prophet (serie de tiempo)",
          "chronos2": "Chronos-2 solo", "chronos2_cal": "Chronos-2 (IA de series)", "anio_pasado": "Igual que el año pasado",
          "regresion_anual": "Regresión anual (calendario + nivel)"}
CRIT = ["BSS sube %", "BSS pico %", "R2 desvio %", "acierta sube/baja %", "AUC pico", "cob80 %", "error <=10 %", "MAPE %", "n"]
SEM = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
color = lambda m: COLOR.get(m.split("_cada")[0], COLOR["llm"] if m.startswith("llm") else MUDO)

def leer(exp, desde="2025-12-31", modelos=None):
    P, U = pr.leer(exp=exp)
    P = P[(P.origen >= desde) & ~P.modelo.str.startswith("llm") & ~P.modelo.str.contains("_cada")]
    if modelos: P = P[P.modelo.isin(modelos)]
    return P, U

pr.usar("e2"); y, cal = pr.cargar()
print(f"triage diario: {y.notna().sum()} días con dato, {y.index[0].date()} a {y.index[-1].date()}")
""")

md(r"""
---
# 1. Los datos: qué se sabe y cuándo

La regla que manda sobre todas: **una predicción hecha el día *o* solo puede usar lo que se sabía el
día *o***. Lo que se sabe por adelantado (calendario, eventos programados) entra con el día que se
predice. Lo demás, con su último valor conocido.
""")
code(r"""
disp = pd.DataFrame([
    ["Triage diario", "salidas/triage_diario.parquet", "hasta el día de la predicción", "nivel y memoria"],
    ["Calendario de Colombia", "calendario_Colombia.csv", "por adelantado", "calendario"],
    ["COVID (dos fases)", "fechas fijas", "por adelantado", "calendario"],
    ["Feria, eventos de Manizales, fiestas de Caldas, días especiales", "eventos_*, fiestas_*, calendario", "por adelantado (programados)", "eventos"],
    ["IRA de Manizales (total, 0-4, 60+), consultas por toda causa", "Power BI 995 + microdatos", "semana epidemiológica anterior", "salud"],
    ["Agresión animal, intento de suicidio, varicela, violencia de género, intoxicaciones", "Power BI + microdatos", "semana anterior", "salud"],
    ["Temperatura, humedad, lluvia, radiación, viento (anomalías de 7 y 28 días)", "clima_unificado.csv.gz", "hasta el día anterior", "clima"],
    ["Lesiones de tránsito, lesiones personales, homicidio, violencia intrafamiliar", "seguridad_mindefensa.csv.gz", "hasta el día anterior", "social"],
    ["Nueva EPS: cambio de 28 días y peso en el triage", "triage_entidad.parquet", "hasta el día de la predicción", "red"],
    ["Desastre activo (incluye el terremoto del 10-08-2026)", "desastres_manizales_2020_2026.csv", "cuando ya empezó", "catástrofe"],
    ["ENSO (El Niño / La Niña)", "enso_oni.csv", "con dos meses de retraso", "ENSO"],
    ["Clima o IRA de los días que vienen", "—", "NO se sabe (no hay archivo histórico de pronósticos)", "no se usa"],
], columns=["dato", "fuente", "¿cuándo se sabe?", "capa"])
display(disp)

fig, ax = plt.subplots(figsize=(15, 3.6))
ax.plot(y.index, y.values, color="#c9c8c4", lw=.5)
ax.plot(y.index, y.rolling(28, center=True, min_periods=14).mean(), color=TINTA, lw=1.6, label="media de 28 días")
ax.axvspan(pd.Timestamp("2020-03-15"), pd.Timestamp("2022-02-28"), color=AMARILLO, alpha=.10)
ax.axvspan(pd.Timestamp("2026-01-01"), y.index[-1], color=AZUL, alpha=.10)
ax.text(pd.Timestamp("2020-06-01"), 320, "COVID (marcada como variable)", color=TINTA2, fontsize=9)
ax.text(pd.Timestamp("2026-01-10"), 320, "prueba: 2026", color=AZUL, fontsize=9)
ax.text(pd.Timestamp("2022-09-01"), 320, "entrenamiento (crece con cada día de prueba)", color=TINTA2, fontsize=9)
for f in ["2024-04-01", "2025-11-15", "2026-03-01", "2026-07-01"]: ax.axvline(pd.Timestamp(f), color=MUDO, lw=.8, ls=":")
ax.set_ylim(0, 350); ax.set_ylabel("triages por día"); ax.legend(loc="lower right")
ax.set_title("La serie completa (líneas punteadas: escalones de la red de salud)"); plt.tight_layout(); plt.show()
""")
lec("datos")

md(r"""
---
# 2. Las entradas, por capas

Cada capa es una razón posible de que un día tenga más o menos triage. Es lo que permite decir **por
qué** se mueve la predicción.
""")
code(r"""
X2 = pr.rasgos(y, cal.reindex(y.index), 1, tuple(c.reindex(y.index) for c in pr.contexto(cal.index)))
capa = pd.Series(pr.capas(X2.columns))
resumen = capa.value_counts().rename("variables").to_frame()
resumen["ejemplos"] = [", ".join(capa[capa == k].index[:3]) for k in resumen.index]
print(f"{X2.shape[1]} entradas por día en E2")
resumen
""")
lec("entradas")

md(r"""
---
# 3. Los modelos

| Modelo | Técnica | Cómo da la distribución | Ventaja | Riesgo |
|---|---|---|---|---|
| **Ingenuo** | base | lo de hace 7 días × su dispersión | nada que ajustar | no ve nada más |
| **Control** | base | calendario + nivel, en log | es la vara del proyecto | no ve estación ni contexto |
| **Regresión binomial negativa** | regresión de conteo | cada factor multiplica | **da las razones** directo | supone efectos que solo se suman en log |
| **LightGBM** | árboles con refuerzo | un modelo por cuantil | capta interacciones | se sobreajusta con pocos datos |
| **SARIMAX** | serie de tiempo clásica | error gaussiano del log, que crece con el horizonte | **se actualiza cada día** con lo que acaba de pasar | lineal |
| **Prophet** | serie de tiempo por componentes | simulación | buena para estaciones largas | no tiene memoria de corto plazo |
| **Chronos-2** | modelo fundacional de series (IA preentrenada) | cuantiles directos | **no se entrena con estos datos** | caja negra y lento con muchas covariables |
| **MedGemma** | modelo de lenguaje médico | un solo número (no da distribución) | — | no está hecho para series |

**Detalles que cuentan:**
- Todos se reentrenan cada 7 días con todo lo anterior.
- Ningún parámetro se eligió mirando 2026.
""")

md(r"""
---
# 4. Cómo se mide, en simple

| Criterio | Qué pregunta contesta | Cómo se lee |
|---|---|---|
| **Acierta si sube o baja** | ¿El día quedó por encima o por debajo de lo que anunciaba el calendario, como dijo el modelo? | 50 % = adivinar. **La meta es 60-70 %** |
| **Mejora de la probabilidad (BSS)** | ¿Su «60 % de que suba» vale más que decir siempre la tasa normal? | Positivo: sirve. Negativo: peor que no tener modelo |
| **Desvío anticipado (R²)** | De lo que el calendario no explica, ¿cuánto vio venir? | 0 % = no sabe más que el calendario |
| **Cobertura del 80 %** | De cada 100 días, ¿cuántos cayeron dentro del rango que prometió con 80 % de seguridad? | **75-85 % = honesto.** Menos es exceso de confianza (sobreajuste) |
| Días con error ≤ 10 % y MAPE | ¿Qué tan cerca quedó el número? | Para comunicar; casi todo lo explica el calendario |

**Deciden la mejora de la probabilidad y la cobertura.** El MAPE solo comunica: un modelo puede
clavar los lunes y no anticipar nada.
""")

md(r"""
---
# 5. Prueba 1: corto plazo, cada día de 2026

## 5.1 Los tres experimentos, modelo por modelo
""")
code(r"""
tablas = []
for e in ["e0", "e1", "e2", "e3"]:
    P, U = leer(e)
    P2, T = pr.metricas(P, U)
    tablas.append(T.assign(exp=e).reset_index())
R = pd.concat(tablas)
R["modelo_"] = R.modelo.map(NOMBRE)
tab = R.pivot_table(index="modelo_", columns="exp", values=["acierta sube/baja %", "BSS sube %", "BSS pico %", "cob80 %", "MAPE %"])
tab = tab.reindex(tab[("BSS sube %", "e2")].fillna(tab[("BSS sube %", "e0")]).sort_values(ascending=False).index)
display(tab.round(1))

fig, axes = plt.subplots(1, 3, figsize=(16, 4.2), sharey=True)
mods = [m for m in ["sarimax", "glm_binneg", "chronos2_cal", "lightgbm", "prophet"] if m in set(R.modelo)]
for ax, (c, t) in zip(axes, [("acierta sube/baja %", "Acierta si sube o baja (%)"), ("BSS sube %", "Mejora de la probabilidad (BSS, %)"), ("cob80 %", "Cobertura del rango del 80 % (%)")]):
    for j, e in enumerate(["e0", "e1", "e2", "e3"]):
        v = R[R.exp == e].set_index("modelo").reindex(mods)[c]
        ax.barh(np.arange(len(mods)) + (j - 1.5) * .2, v.values, height=.19, color=[MUDO, AZUL, NARANJA, VERDE][j],
                label={"e0": "E0: 2022-24, sin contexto", "e1": "E1: 2020-25, sin contexto", "e2": "E2: + las 49 externas", "e3": "E3: + 8 externas elegidas"}[e])
    ax.set_title(t, fontsize=10)
    base = R[(R.exp == "e0") & (R.modelo == "control")][c].iloc[0]
    ax.axvline(base, color=TINTA, lw=1, ls="--")
axes[0].set_yticks(range(len(mods)), [NOMBRE[m] for m in mods]); axes[2].axvspan(75, 85, color=AQUA, alpha=.12)
axes[0].axvspan(60, 70, color=AQUA, alpha=.12)
axes[2].legend(fontsize=8, loc="lower right"); fig.suptitle("2026, a 1-7 días: qué aportan más años (E1) y el contexto (E2). Línea: el control", fontweight="bold")
plt.tight_layout(); plt.show()
""")
lec("p1_experimentos")

md(r"""
## 5.2 Chronos-2 con todo el contexto

Con 61 covariables, Chronos-2 en CPU tarda horas por cada origen diario. Se corrió con **un origen
cada 7 días** (37 orígenes de 2026). La información es la misma; solo hay menos predicciones.
Para compararlo de forma justa, **todos los modelos se miden en esos mismos 37 orígenes**.
""")
code(r"""
P7, U7 = pr.leer(exp="e2")
cada7 = sorted(P7[P7.modelo.str.endswith("_cada7")].origen.unique())
if cada7:
    partes = [P7[P7.modelo.str.endswith("_cada7")].assign(modelo=lambda d: d.modelo + " · e2")]
    for e in ["e0", "e1", "e2", "e3"]:
        P, _ = leer(e); partes.append(P[P.origen.isin(cada7)].assign(modelo=lambda d, e=e: d.modelo + " · " + e))
    _, T7 = pr.metricas(pd.concat(partes), U7)
    display(T7[CRIT].sort_values("BSS sube %", ascending=False).round(1))
else:
    print("Chronos-2 con contexto todavía no ha terminado.")
""")
lec("p1_chronos")

md(r"""
## 5.3 El jerárquico: Nueva EPS y el resto por separado

Nueva EPS (58 % del triage) salta a escalones que el resto no tiene. Se predice cada parte con el mismo
modelo y las entradas de E1, y se arma el total de dos formas, preregistradas (filas `jerarquico` y
`jerarquico_correlado` de `variables.csv`):
- **suma de cuantiles:** supone que las dos partes se mueven siempre juntas;
- **cópula:** usa la correlación real entre las dos, medida en enero de 2026 y congelada.
""")
code(r"""
from scipy.stats import spearmanr, norm
CORTE = pd.Timestamp("2026-01-28")
def jerarquico(modelo, metodo):
    a, _ = pr.leer([modelo], exp="j_ne"); b, _ = pr.leer([modelo], exp="j_resto")
    m = a.merge(b, on=["origen", "h", "fecha"], suffixes=("_ne", "_re"))
    c0 = m[(m.origen < CORTE) & (m.h == 1)].dropna(subset=["real_ne", "real_re"])
    rho = spearmanr(np.log(c0.real_ne / c0.q50_ne), np.log(c0.real_re / c0.q50_re))[0]
    out = m[["origen", "h", "fecha"]].copy(); out["modelo"] = f"{NOMBRE[modelo]} · jerárquico ({metodo})"
    if metodo == "suma":
        for c in pr.QCOL: out[c] = m[c + "_ne"] + m[c + "_re"]
    else:
        u = norm.cdf(np.random.default_rng(0).multivariate_normal([0, 0], [[1, rho], [rho, 1]], size=4000))
        Qa, Qb = m[[c + "_ne" for c in pr.QCOL]].values, m[[c + "_re" for c in pr.QCOL]].values
        tot = np.array([np.quantile(np.interp(u[:, 0], pr.QL, x) + np.interp(u[:, 1], pr.QL, z), pr.QL) for x, z in zip(Qa, Qb)])
        for j, c in enumerate(pr.QCOL): out[c] = tot[:, j]
    return out, rho
P1, U1 = leer("e1"); real = P1[["fecha", "real"]].drop_duplicates("fecha")
lista = []
for mod in ["sarimax", "glm_binneg"]:
    for metodo in ["suma", "cópula"]:
        o, rho = jerarquico(mod, metodo); lista.append(o.merge(real, on="fecha"))
    lista.append(P1[P1.modelo == mod].assign(modelo=NOMBRE[mod] + " · sobre el total"))
    print(f"{NOMBRE[mod]}: correlación de Spearman entre Nueva EPS y el resto, en enero = {rho:.2f}")
_, TJ = pr.metricas(pd.concat(lista), U1)
display(TJ[CRIT].sort_values("BSS sube %", ascending=False).round(1))
a, _ = pr.leer(["sarimax"], exp="j_ne"); a = a[a.h == 1]
print("Nueva EPS en 2026: media real por mes y predicción de SARIMAX a 1 día")
display(a.groupby(a.fecha.dt.month)[["real", "q50"]].mean().round(0).T)
""")
lec("p1_jerarquico")

md(r"""
## 5.4 ¿Se puede creer la probabilidad? Calibración del mejor de cada familia

Se agrupan los días por la probabilidad de «sube» que dio el modelo, y se mira cuántas veces subió
de verdad. Un modelo calibrado cae sobre la diagonal.
""")
code(r"""
P, U = leer("e1"); P2, T2 = pr.metricas(P, U)
fig, ax = plt.subplots(figsize=(6.5, 5.5)); ax.plot([0, 1], [0, 1], color=MUDO, ls="--", lw=1)
bins = np.linspace(0, 1, 11)
for m in T2.sort_values("BSS sube %", ascending=False).index[:4]:
    d = P2[P2.modelo == m]
    g = d.groupby(pd.cut(d.p_sobre, bins)).agg(p=("p_sobre", "mean"), f=("sobre", "mean"), n=("sobre", "size")).query("n >= 25")
    ax.plot(g.p, g.f, "-o", color=color(m), lw=1.8, ms=5, label=NOMBRE.get(m, m))
ax.set_xlabel("probabilidad de «sube» que dio el modelo"); ax.set_ylabel("frecuencia con que subió")
ax.set_title("Calibración en 2026 (E1: 2020-2025)", fontsize=10); ax.legend(fontsize=8); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
plt.tight_layout(); plt.show()
""")
lec("p1_calibracion")

md(r"""
## 5.5 Los picos de 2026: ¿se vieron venir la víspera?
""")
code(r"""
mejor = T2.sort_values("BSS sube %", ascending=False).index[0]
d = P2[(P2.modelo == mejor) & (P2.h == 1)].copy()
d["día"] = d.fecha.dt.dayofweek.map(dict(enumerate(SEM)))
print(f"Modelo: {NOMBRE.get(mejor, mejor)} (E1: 2020-2025), a 1 día")
top = d.nlargest(12, "d_real")[["fecha", "día", "real", "esperado_cal", "q50", "q10", "q90", "p_sobre", "p_pico", "pico"]]
display(top.rename(columns={"esperado_cal": "anunciaba el calendario", "q50": "predijo", "p_sobre": "P(sube)", "p_pico": "P(pico)"}).round(2))
avisos = pd.DataFrame([{"avisar si P(pico) ≥": f"{u:.0%}", "avisos": int((d.p_pico >= u).sum()),
                        "de esos, eran pico %": 100 * d.pico[d.p_pico >= u].mean() if (d.p_pico >= u).any() else np.nan,
                        "picos avisados %": 100 * d.pico[d.p_pico >= u].sum() / d.pico.sum()} for u in [.2, .3, .4]])
display(avisos.round(1))
""")
lec("p1_picos")

md(r"""
---
# 6. Prueba 2: el año a ciegas

El 31 de diciembre de 2025 se hace **una sola predicción** para todo 2026, como pediría quien planea el
año. El modelo no puede saber el clima ni la IRA de julio: en E2, ese contexto va como «año típico»
(anomalía cero), y las variables de nivel (peso de Nueva EPS, ENSO) se congelan en su valor de
diciembre. Lo programado (calendario, Feria, fiestas) sí entra.
""")
code(r"""
filas = []
for e in ["e1", "e2"]:
    PA, _ = pr.leer(exp=e, anio=True); PA = PA.dropna(subset=["real"])
    PA["mes"] = PA.fecha.dt.month; filas.append(PA.assign(exp=e))
A = pd.concat(filas)
M = A.groupby(["exp", "modelo", "mes"]).agg(pred=("q50", "mean"), lo=("q10", "mean"), hi=("q90", "mean"), real=("real", "mean")).reset_index()
M["error %"] = 100 * (M.pred - M.real) / M.real
display(M.pivot_table(index=["exp", "modelo"], columns="mes", values="error %").round(1))
resA = A.groupby(["exp", "modelo"]).apply(lambda g: pd.Series({
    "MAPE diario %": 100 * ((g.q50 - g.real).abs() / g.real).mean(),
    "error medio del mes %": 100 * (g.groupby("mes").q50.mean() / g.groupby("mes").real.mean() - 1).abs().mean(),
    "cob80 %": 100 * g.real.between(g.q10, g.q90).mean()}))
display(resA.round(1))

meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep"]
fig, axes = plt.subplots(1, 2, figsize=(15, 4.2), sharey=True)
for ax, e in zip(axes, ["e1", "e2"]):
    r = M[(M.exp == e)].groupby("mes").real.first()
    ax.plot(r.index, r.values, "o-", color=TINTA, lw=2.2, label="real")
    for m in ["sarimax", "regresion_anual", "chronos2_cal", "prophet", "anio_pasado"]:
        g = M[(M.exp == e) & (M.modelo == m)]
        if len(g): ax.plot(g.mes, g.pred, "-", color=color(m), lw=1.6, label=NOMBRE.get(m, m))
    ax.set_xticks(range(1, 10), meses); ax.set_title({"e1": "E1: más años, sin contexto", "e2": "E2: más años + contexto"}[e], fontsize=10)
axes[0].set_ylabel("triages por día (media del mes)"); axes[1].legend(fontsize=8)
for ax in axes:
    for f, t in [(3, "Nueva EPS"), (7, "Nueva EPS")]: ax.axvline(f, color=MUDO, ls=":", lw=.8)
fig.suptitle("2026 predicho entero el 31 de diciembre de 2025", fontweight="bold"); plt.tight_layout(); plt.show()
""")
lec("p2_anio")

md(r"""
---
# 7. Prueba 3: la hora de saturación

La predicción del día del mejor modelo se reparte en horas con el **perfil horario por día de la
semana de 2025**, que se conoce el 31-12-2025. Se mide si acierta las horas de más carga.
""")
code(r"""
hor = pd.read_parquet(RAIZ / "salidas/triage_horario.parquet"); hor["dia"] = pd.to_datetime(hor.dia)
Hh = hor.pivot_table(index="dia", columns="hora", values="triages", aggfunc="sum").reindex(columns=range(24)).fillna(0)
ref = Hh.loc["2025-01-01":"2025-12-31"]
perfil = (ref.div(ref.sum(axis=1), axis=0)).groupby(ref.index.dayofweek).mean()
d1 = P2[(P2.modelo == mejor) & (P2.h == 1)].set_index("fecha")
real_h = Hh.reindex(d1.index)
pred_h = pd.DataFrame(d1.q50.values[:, None] * perfil.loc[d1.index.dayofweek].values, index=d1.index, columns=range(24))
dia_h = (pred_h - real_h).abs() / real_h.replace(0, np.nan)
pico_real, pico_pred = real_h.idxmax(axis=1), pred_h.idxmax(axis=1)
top3 = np.mean([len(set(real_h.loc[t].nlargest(3).index) & set(pred_h.loc[t].nlargest(3).index)) / 3 for t in d1.index])
print(f"Modelo: {NOMBRE.get(mejor, mejor)}, a 1 día, {len(d1)} días de 2026")
print(f"Hora pico acertada exacta: {(pico_real == pico_pred).mean():.0%}; a ±1 hora: {((pico_real - pico_pred).abs() <= 1).mean():.0%}")
print(f"De las 3 horas de más carga, coinciden en promedio: {top3:.0%}")
print(f"Error por hora entre 8 y 20 h (MAPE): {100 * dia_h.loc[:, 8:20].stack().mean():.1f} %")
fig, axes = plt.subplots(1, 2, figsize=(15, 3.8))
axes[0].plot(range(24), real_h.mean().values, "o-", color=TINTA, label="real (media 2026)")
axes[0].plot(range(24), pred_h.mean().values, "-", color=color(mejor), lw=2, label="predicho (media)")
axes[0].set_xticks(range(0, 24, 2)); axes[0].set_xlabel("hora"); axes[0].set_ylabel("triages por hora"); axes[0].legend(); axes[0].set_title("El día promedio")
sem = d1.index[(d1.index >= "2026-05-04") & (d1.index <= "2026-05-10")]
axes[1].plot(np.arange(len(sem) * 24), real_h.loc[sem].values.ravel(), color=TINTA, lw=1.2, label="real")
axes[1].plot(np.arange(len(sem) * 24), pred_h.loc[sem].values.ravel(), color=color(mejor), lw=1.6, label="predicho la víspera")
axes[1].set_xticks(np.arange(len(sem)) * 24 + 12, [f"{SEM[t.dayofweek]} {t.day}" for t in sem]); axes[1].legend(fontsize=8)
axes[1].set_title("Una semana hora por hora (4-10 de mayo de 2026)"); plt.tight_layout(); plt.show()
""")
lec("p3_hora")

md(r"""
---
# 8. Las razones: qué contexto pesa

Se ajustan dos modelos en el último origen (2026-09-13) con todo el contexto:
- **LightGBM** (mediana a 1 día): cuánto de su capacidad de separar días usa cada capa (ganancia);
- **la regresión**: cuánto mueve cada capa la predicción cuando sus variables se corren una desviación
  típica.
""")
code(r"""
import lightgbm as lgb
pr.usar("e2")
o = pd.Timestamp(pr.ULTIMO_ORIGEN)
ctx = tuple(c.reindex(y.index) for c in pr.contexto(cal.index))
X = pr.rasgos(y, cal.reindex(y.index), 1, ctx).loc[:o]; yy = y.loc[:o]
ok = X.notna().all(axis=1) & yy.notna(); X, yy = X[ok], yy[ok]; X = X.loc[:, X.std() > 0]
m = lgb.LGBMRegressor(objective="quantile", alpha=.5, **pr.LightGBM.PARAM).fit(X, np.log(yy))
gan = pd.Series(m.booster_.feature_importance("gain"), index=X.columns)
capa = pd.Series(pr.capas(X.columns))
r = sm.NegativeBinomial(yy.values, sm.add_constant(X.values, has_constant="add")).fit(disp=0, maxiter=300)
b = pd.Series(r.params[1:-1], index=X.columns)
efecto = (b * X.std()).abs().groupby(capa).sum()
pesos = pd.DataFrame({"LightGBM: % de la ganancia": 100 * gan.groupby(capa).sum() / gan.sum(),
                      "Regresión: efecto de 1 desviación, % (suma de |efectos|)": 100 * (np.exp(efecto) - 1)}).sort_values("LightGBM: % de la ganancia", ascending=False)
display(pesos.round(1))
print("Las 12 variables externas más usadas por LightGBM (% de la ganancia):")
ext = gan[[c for c in gan.index if c.startswith(("ext_", "fut_"))]]
print((100 * ext / gan.sum()).sort_values(ascending=False).head(12).round(2).to_string())
""")
lec("razones")

md(r"""
---
# 9. MedGemma: ¿puede un modelo de lenguaje médico pronosticar?

A pedido del propietario: `medgemma:latest` (4,3 B) en el servidor de su superior, con 19 consultas, y
`medgemma1.5:4b` en local si se corrió. Reciben **la misma información que E2**, en texto: 8 semanas de
triage, el calendario y los eventos que vienen, y el contexto de la ciudad (IRA, clima, Nueva EPS,
lesiones). Dan un número por día, no una distribución, así que se comparan solo en el error del número
y en si aciertan la dirección (sube o baja), **en los mismos orígenes** que los demás.
""")
code(r"""
PL, UL = pr.leer(exp="e2")
llm = PL[PL.modelo.str.startswith("llm")]
if len(llm):
    ors_llm = llm.origen.unique()
    comp = []
    for e in ["e0", "e1", "e2", "e3"]:
        P, _ = leer(e); comp.append(P[P.origen.isin(ors_llm)].assign(modelo=lambda d, e=e: d.modelo + " · " + e))
    comp.append(llm)
    CP, TL = pr.metricas(pd.concat(comp), UL)
    TL["dirección (sube/baja) %"] = CP.assign(ok=lambda d: (np.sign(d.d_pred) == np.sign(d.d_real))).groupby("modelo").ok.mean() * 100
    display(TL[["dirección (sube/baja) %", "error <=10 %", "MAPE %", "n"]].sort_values("MAPE %").round(1))
    print("Respuestas de MedGemma del servidor (los 7 números de cada consulta):")
    print(llm[llm.modelo.str.contains("servidor")].groupby("origen").q50.apply(lambda s: list(s.astype(int))).head(8).to_string())
""")
lec("medgemma")

md(r"""
---
# 10. Depuración: qué se queda y qué sale
""")
lec("depuracion")

md(r"""
---
# 11. Resumen de lo descubierto
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "15_predicciones_tempranas.ipynb")
print("ok", len(C))
