"""
notebooks/05_validacion_sin_motivo.py -- se corre con: python notebooks/05_validacion_sin_motivo.py

Validacion: ¿se puede predecir el aumento del CONTEO de triage sin el motivo?

Solo usa agregados ya extraidos (salidas/*.parquet) y los calendarios. Ningun
texto, ningun identificador.

Definiciones fijadas ANTES de mirar resultados (escritas aqui, 2026-09-28):
  - Ventana de analisis: 2022-03-01 a 2026-09-20 (fuera COVID y omicron; el
    ultimo dia de la serie esta incompleto).
  - Semana = lunes a domingo.
  - Control de calendario: dia de semana, festivo, puente, vispera/post festivo,
    quincena, vacaciones escolares, semana santa, temporada navidad/fin de ano,
    regreso a colegio + efecto fijo de ano + escalon 2025-11-01 (la deriva
    administrativa medida el 2026-09-22). SIN mes del ano: la estacionalidad es
    parte de lo que se quiere explicar.
  - Anomalias de clima: contra la climatologia del mismo mes (2020-2026).
  - ruptura_seca_lluvia (semana): z de lluvia de la semana >= +0.5 y media de z
    de las 3 semanas previas <= -0.5.
  - enfriamiento (semana): z de temp de la semana - media z de las 3 previas <= -1.
  - Indicador pediatrico: residuo (log) de 0-14 anos de la semana anterior.
"""
import numpy as np, pandas as pd, warnings, sys
warnings.filterwarnings("ignore")
from pathlib import Path
R = str(Path(__file__).resolve().parents[1])
INI, FIN = "2022-03-01", "2026-09-20"
out = []
def p(*a):
    s = " ".join(str(x) for x in a); print(s); out.append(s)

# ---------------------------------------------------------------- datos
d = pd.read_parquet(f"{R}/salidas/triage_diario.parquet")
p("diario cols:", list(d.columns))
dcol = [c for c in d.columns if np.issubdtype(d[c].dtype, np.datetime64) or c in ("dia", "fecha")][0]
ncol = [c for c in d.columns if c != dcol and np.issubdtype(d[c].dtype, np.number)][0]
tot = d.set_index(pd.to_datetime(d[dcol]))[ncol].astype(float).rename("total")

e = pd.read_parquet(f"{R}/salidas/triage_edad.parquet")
e["dia"] = pd.to_datetime(e["dia"])
ed = e.pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").fillna(0)
p("bandas:", list(ed.columns))
ped = ed[[c for c in ed.columns if c.startswith("0-") or c.startswith("5-")]].sum(axis=1).rename("ped")
b04 = ed[[c for c in ed.columns if c.startswith("0-")]].sum(axis=1).rename("b04")

nv = pd.read_parquet(f"{R}/salidas/triage_nivel.parquet")
nv["dia"] = pd.to_datetime(nv["dia"])
obst = nv[nv["nivel"].astype(str).str.contains("G")].groupby("dia")["n"].sum().rename("obst")

D = pd.concat([tot, ped, b04, obst], axis=1).fillna(0)
D = D.asfreq("D")
D["adult"] = D["total"] - D["ped"]
D["adult_noobst"] = D["adult"] - D["obst"]

k = pd.read_csv(f"{R}/calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
CAL = ["es_festivo", "es_puente", "es_vispera_festivo", "es_post_festivo", "es_quincena",
       "es_vacaciones_escolares", "es_semana_santa", "es_temporada_navidad",
       "es_temporada_fin_anio", "es_regreso_colegio"]
k = k[CAL + ["dia_semana"]].apply(pd.to_numeric, errors="coerce").fillna(0)

c = pd.read_csv(f"{R}/calendarios/clima_unificado.csv.gz", parse_dates=["fecha"]).set_index("fecha")
c = c[["precip_consenso_mm", "temp_media_consenso", "humedad_consenso", "temp_min_consenso",
       "precip_con_estacion"]]

D = D.join(k).join(c)
D = D.loc["2020-01-01":FIN]

# ------------------------------------------------ calendarios externos, dia a dia
def banderas(df, filtro, nombre, ini="fecha_inicio", fin="fecha_fin"):
    s = pd.Series(0.0, index=D.index, name=nombre)
    for _, r in df[filtro].iterrows():
        a = pd.to_datetime(r[ini], errors="coerce"); b = pd.to_datetime(r[fin], errors="coerce")
        if pd.isna(a): continue
        if pd.isna(b): b = a
        s.loc[a:b] = 1
    return s

v = pd.read_csv(f"{R}/calendarios/vigilancia_salud_manizales_caldas.csv")
ev = pd.read_csv(f"{R}/calendarios/eventos_manizales_2020_2026.csv")
de = pd.read_csv(f"{R}/calendarios/desastres_manizales_2020_2026.csv")

p("\n=== 0. QUE TRAEN LOS CALENDARIOS")
p(f"vigilancia: {len(v)} filas; ventana_estacional (misma fecha cada ano): "
  f"{(v.estado=='ventana_estacional').sum()} ({(v.estado=='ventana_estacional').mean():.0%})")
p("  por ambito:", v.ambito_territorial.value_counts().to_dict())
p("  con numero de casos:", v.casos.notna().sum(), "| de Manizales con casos:",
  ((v.ambito_territorial=='manizales') & v.casos.notna()).sum())
p(f"eventos: {len(ev)} filas; categorias:", ev.categoria.value_counts().to_dict())
p(f"desastres: {len(de)} filas; calidad:", de.calidad_dato.value_counts().to_dict())

X = pd.DataFrame(index=D.index)
X["ira_ventana"] = banderas(v, (v.subcategoria=="temporada_IRA") & (v.estado=="ventana_estacional"), "x")
X["vsr_ventana"] = banderas(v, (v.subcategoria=="vsr"), "x")
X["flu_ventana"] = banderas(v, (v.subcategoria=="influenza") & (v.estado=="ventana_estacional"), "x")
X["dengue_ventana"] = banderas(v, (v.subcategoria=="dengue") & (v.estado=="ventana_estacional"), "x")
X["nino"] = banderas(v, v.subcategoria=="el_nino", "x")
X["nina"] = banderas(v, v.subcategoria=="la_nina", "x")
X["volcan_naranja"] = banderas(v, v.nombre_evento.str.contains("Naranja", case=False, na=False) |
                               v.descripcion.str.contains("alerta naranja", case=False, na=False) &
                               (v.subcategoria=="actividad_volcanica"), "x")
X["ceniza"] = banderas(v, v.subcategoria=="ceniza_volcanica", "x")
evm = ev[(ev.municipio=="Manizales") & ev.estado.isin(["realizado", "hibrido"])]
X["evento"] = banderas(evm, slice(None), "x")
X["feria"] = banderas(evm, evm.nombre_evento.str.contains("Feria de Manizales"), "x")
X["desastre"] = banderas(de, de.ambito.isin(["municipal", "institucional"]) &
                         (de.calidad_dato != "pendiente_verificacion") &
                         (pd.to_datetime(de.fecha_fin) - pd.to_datetime(de.fecha_inicio)).dt.days.le(7), "x")
X["terremoto"] = 0.0; X.loc["2026-08-10":"2026-08-23", "terremoto"] = 1
D = D.join(X)

# ¿las ventanas de vigilancia dicen algo que el mes no diga ya?
m = pd.get_dummies(D.index.month).astype(float).values
for col in ["ira_ventana", "vsr_ventana", "flu_ventana", "dengue_ventana"]:
    y = D[col].values
    beta, *_ = np.linalg.lstsq(m, y, rcond=None)
    r2 = 1 - ((y - m @ beta) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    p(f"  {col}: R2 explicado solo por el mes del ano = {r2:.3f}")

# ------------------------------------------------------------ control diario
W = D.loc[INI:FIN].copy()
W = W[W.total > 0]
def diseno_control(df, con_mes=False, con_tendencia=True):
    Z = pd.get_dummies(df["dia_semana"].astype(int), prefix="dow", drop_first=True).astype(float)
    Z = pd.concat([Z, df[CAL]], axis=1)
    if con_tendencia:
        Z = pd.concat([Z, pd.get_dummies(df.index.year, prefix="a", drop_first=True)
                       .set_index(df.index).astype(float)], axis=1)
        Z["escalon_2025_11"] = (df.index >= "2025-11-01").astype(float)
    if con_mes:
        doy = df.index.dayofyear.values
        for h in (1, 2, 3):
            Z[f"s{h}"] = np.sin(2*np.pi*h*doy/365.25); Z[f"c{h}"] = np.cos(2*np.pi*h*doy/365.25)
    Z.insert(0, "const", 1.0)
    return Z

def ols(y, Z):
    b, *_ = np.linalg.lstsq(Z.values, y, rcond=None)
    return b, y - Z.values @ b

p("\n=== 1. PRESUPUESTO DE RUIDO (log conteo, dias 2022-03 a 2026-09)")
for nombre in ["total", "adult", "ped"]:
    y = np.log(W[nombre].clip(lower=0.5)).values
    _, r0 = ols(y, diseno_control(W))
    _, r1 = ols(y, diseno_control(W, con_mes=True))
    vt = y.var()
    piso = np.mean(1 / W[nombre].clip(lower=1))   # varianza de Poisson en log ~ 1/mu
    p(f"  {nombre:6s} media {W[nombre].mean():6.1f}/dia | sd residuo control {r0.std():.3f} | "
      f"+estacionalidad {r1.std():.3f} | piso Poisson {np.sqrt(piso):.3f} | "
      f"explicable que queda {np.sqrt(max(r1.var()-piso,0)):.3f} "
      f"({max(r1.var()-piso,0)/r1.var():.0%} de la varianza residual) | AR1 resid {pd.Series(r1).autocorr():+.2f}")
    W[f"res_{nombre}"] = r0
    W[f"res1_{nombre}"] = r1

# ------------------------------------------------------------ semanal
agg = {"total": "sum", "adult": "sum", "ped": "sum", "b04": "sum", "adult_noobst": "sum",
       "precip_consenso_mm": "sum", "temp_media_consenso": "mean", "humedad_consenso": "mean",
       "temp_min_consenso": "mean"}
agg.update({col: "mean" for col in CAL})
agg.update({col: "max" for col in X.columns})
agg["evento"] = "sum"; agg["feria"] = "sum"
S = D.loc["2020-01-06":FIN].resample("W-SUN").agg(agg)
S["n_dias"] = D.loc["2020-01-06":FIN, "total"].resample("W-SUN").count()
S = S[S.n_dias == 7]
# climatologia del mes (sobre semanas)
mes = S.index.month
for col, nom in [("precip_consenso_mm", "zp"), ("temp_media_consenso", "zt"),
                 ("humedad_consenso", "zh"), ("temp_min_consenso", "ztmin")]:
    g = S[col].groupby(mes)
    S[nom] = (S[col] - g.transform("mean")) / g.transform("std")
S["zp_prev3"] = S["zp"].shift(1).rolling(3).mean()
S["zt_prev3"] = S["zt"].shift(1).rolling(3).mean()
S["ruptura"] = ((S.zp >= 0.5) & (S.zp_prev3 <= -0.5)).astype(float).where(S.zp.notna() & S.zp_prev3.notna())
S["enfriamiento"] = ((S.zt - S.zt_prev3) <= -1).astype(float).where(S.zt.notna() & S.zt_prev3.notna())

SW = S.loc[INI:FIN].copy()
def diseno_sem(df, con_mes=False):
    Z = df[CAL].copy()
    Z = pd.concat([Z, pd.get_dummies(df.index.year, prefix="a", drop_first=True).set_index(df.index).astype(float)], axis=1)
    Z["escalon_2025_11"] = (df.index >= "2025-11-01").astype(float)
    if con_mes:
        w = df.index.isocalendar().week.values.astype(float)
        for h in (1, 2, 3):
            Z[f"s{h}"] = np.sin(2*np.pi*h*w/52.18); Z[f"c{h}"] = np.cos(2*np.pi*h*w/52.18)
    Z.insert(0, "const", 1.0)
    return Z

p("\n=== 2. PRESUPUESTO DE RUIDO SEMANAL")
for nombre in ["total", "adult", "ped", "b04"]:
    y = np.log(SW[nombre].clip(lower=0.5)).values
    _, r0 = ols(y, diseno_sem(SW)); _, r1 = ols(y, diseno_sem(SW, True))
    piso = np.mean(1 / SW[nombre].clip(lower=1))
    SW[f"r0_{nombre}"] = r0; SW[f"r1_{nombre}"] = r1
    p(f"  {nombre:6s} media {SW[nombre].mean():7.1f}/sem | sd resid control {r0.std():.3f} | "
      f"+estacional {r1.std():.3f} | piso Poisson {np.sqrt(piso):.3f} | "
      f"explicable {max(r1.var()-piso,0)/r1.var():.0%} | AR1 {pd.Series(r1).autocorr():+.2f} | "
      f"var que se come la estacionalidad {1 - r1.var()/r0.var():.0%}")

# ------------------------------------------------------------ asociaciones
def hac_se(y, Z, lags=4):
    Zv = Z.values; n = len(y)
    b, *_ = np.linalg.lstsq(Zv, y, rcond=None); u = y - Zv @ b
    XtX_inv = np.linalg.pinv(Zv.T @ Zv)
    S0 = (Zv * u[:, None]).T @ (Zv * u[:, None])
    for L in range(1, lags + 1):
        w = 1 - L / (lags + 1)
        G = (Zv[L:] * u[L:, None]).T @ (Zv[:-L] * u[:-L, None])
        S0 += w * (G + G.T)
    V = XtX_inv @ S0 @ XtX_inv
    return b, np.sqrt(np.diag(V))

p("\n=== 3. ASOCIACIONES SEMANALES (efecto % sobre el conteo, control + estacionalidad; IC95 HAC)")
p("    variable [rezago en semanas] : total | adultos | 0-14 anos")
SW["r1_ped_l1"] = SW["r1_ped"].shift(1)
SW["r1_b04_l1"] = SW["r1_b04"].shift(1)
cands = [("zp", "lluvia z"), ("zt", "temp z"), ("zh", "humedad z"), ("ztmin", "temp min z"),
         ("ruptura", "ruptura seca->lluvia"), ("enfriamiento", "enfriamiento brusco"),
         ("nino", "El Nino"), ("nina", "La Nina"), ("volcan_naranja", "volcan naranja"),
         ("ceniza", "caida de ceniza"), ("evento", "dias de evento (por dia)"),
         ("feria", "dias de Feria (por dia)"), ("terremoto", "terremoto 2026-08"),
         ("ira_ventana", "ventana IRA INS"), ("dengue_ventana", "ventana dengue")]
resumen = []
for col, et in cands:
    for lag in ((0, 1, 2) if col in ("zp", "zt", "zh", "ztmin", "ruptura", "enfriamiento") else (0,)):
        fila = [f"  {et:28s}[{lag}]"]
        for yname in ["total", "adult", "ped"]:
            base = diseno_sem(SW, True)
            xv = SW[col].shift(lag)
            ok = xv.notna()
            Z = base[ok].copy(); Z["x"] = xv[ok].values
            if Z["x"].std() == 0: fila.append("   (constante)   "); continue
            y = np.log(SW.loc[ok, yname].clip(lower=0.5)).values
            b, se = hac_se(y, Z)
            bx, sx = b[-1], se[-1]
            ef = lambda z: (np.exp(z) - 1) * 100
            sig = "*" if abs(bx / sx) > 1.96 else " "
            fila.append(f"{ef(bx):+6.1f}% [{ef(bx-1.96*sx):+5.1f},{ef(bx+1.96*sx):+5.1f}]{sig}")
            resumen.append((et, lag, yname, ef(bx), abs(bx/sx)))
        p(" | ".join(fila))

p("\n  Indicador adelantado: residuo pediatrico de la semana anterior -> adultos esta semana")
for yname in ["adult", "adult_noobst", "total"]:
    Z = diseno_sem(SW, True); Z["ped_l1"] = SW["r1_ped_l1"]; Z["y_l1"] = SW[f"r1_{'adult' if yname!='total' else 'total'}"].shift(1)
    ok = Z.notna().all(axis=1)
    y = np.log(SW.loc[ok, yname].clip(lower=0.5)).values
    b, se = hac_se(y, Z[ok])
    p(f"    {yname:13s}: +10% en ped(t-1) -> {(np.exp(b[-2]*np.log(1.1))-1)*100:+.2f}% (t={b[-2]/se[-2]:+.2f}); "
      f"propio rezago t={b[-1]/se[-1]:+.2f}")
p("  Correlacion contemporanea de residuos semanales (tras control+estacionalidad):")
p(f"    ped vs adultos r = {SW['r1_ped'].corr(SW['r1_adult']):+.2f} | 0-4 vs adultos r = {SW['r1_b04'].corr(SW['r1_adult']):+.2f}")
p(f"  Residuos SIN estacionalidad (solo control): ped vs adultos r = {SW['r0_ped'].corr(SW['r0_adult']):+.2f}")

# ------------------------------------------------------------ pronostico
p("\n=== 4. PRONOSTICO SEMANAL, ORIGEN RODANTE (2024-01 a 2026-08, h = 1 semana)")
F = S.loc["2021-09-01":FIN].copy()
F["ly"] = np.log(F["total"])
F["nivel4"] = F["ly"].rolling(4).mean()          # conocido al cierre de la semana t
F["objetivo"] = F["ly"].shift(-1) - F["nivel4"]   # log(semana t+1) - nivel
F["sube"] = (F["total"].shift(-1) > F["total"]).astype(float)
# calendario de la semana que viene (se conoce por adelantado) menos el de las 4 ultimas
for col in CAL:
    F[f"dcal_{col}"] = F[col].shift(-1) - F[col].rolling(4).mean()
w = F.index.isocalendar().week.values.astype(float) + 1
for h in (1, 2, 3):
    F[f"s{h}"] = np.sin(2*np.pi*h*w/52.18); F[f"c{h}"] = np.cos(2*np.pi*h*w/52.18)
F["escalon"] = (F.index >= "2025-11-01").astype(float)
F["mom"] = F["ly"] - F["nivel4"]                   # ultima semana vs su nivel
F["pedsh"] = np.log(F["ped"] / F["total"])
F["pedsh_d"] = F["pedsh"] - F["pedsh"].rolling(8).mean().shift(1)
F["zp_l"] = F["zp"]; F["zp_l1"] = F["zp"].shift(1); F["zt_l"] = F["zt"]; F["zh_l"] = F["zh"]
F["rupt_l"] = F["ruptura"]; F["enfr_l"] = F["enfriamiento"]
F["evento_sig"] = F["evento"].shift(-1); F["feria_sig"] = F["feria"].shift(-1)
F["nino_l"] = F["nino"]; F["nina_l"] = F["nina"]
F["zp_sig"] = F["zp"].shift(-1); F["zt_sig"] = F["zt"].shift(-1); F["rupt_sig"] = F["ruptura"].shift(-1)

M = {
 "M0 nivel+calendario": [f"dcal_{c}" for c in CAL] + ["escalon"],
 "M1 +estacionalidad (proyeccion)": [f"dcal_{c}" for c in CAL] + ["escalon", "s1", "c1", "s2", "c2", "s3", "c3", "mom"],
 "M2 +externas conocidas en t": [f"dcal_{c}" for c in CAL] + ["escalon", "s1", "c1", "s2", "c2", "s3", "c3", "mom",
        "pedsh_d", "zp_l", "zp_l1", "zt_l", "zh_l", "rupt_l", "enfr_l", "evento_sig", "feria_sig", "nino_l", "nina_l"],
 "M2b solo externas (sin estacional.)": [f"dcal_{c}" for c in CAL] + ["escalon", "mom",
        "pedsh_d", "zp_l", "zp_l1", "zt_l", "zh_l", "rupt_l", "enfr_l", "evento_sig", "feria_sig", "nino_l", "nina_l"],
 "M3 oraculo: +clima observado t+1": [f"dcal_{c}" for c in CAL] + ["escalon", "s1", "c1", "s2", "c2", "s3", "c3", "mom",
        "pedsh_d", "zp_l", "zp_l1", "zt_l", "zh_l", "rupt_l", "enfr_l", "evento_sig", "feria_sig", "nino_l", "nina_l",
        "zp_sig", "zt_sig", "rupt_sig"],
}
from math import erf, sqrt
Phi = lambda z: 0.5 * (1 + np.vectorize(erf)(z / sqrt(2)))
def ridge(Xtr, ytr, lam=3.0):
    mu, sd = Xtr.mean(0), Xtr.std(0); sd[sd == 0] = 1
    Xs = (Xtr - mu) / sd
    A = Xs.T @ Xs + lam * np.eye(Xs.shape[1]); b = np.linalg.solve(A, Xs.T @ (ytr - ytr.mean()))
    return lambda Xn: ytr.mean() + ((Xn - mu) / sd) @ b

orig = F.loc["2024-01-01":"2026-08-16"].index
res = {k: [] for k in M}; res["naive (=semana actual)"] = []
for t in orig:
    tr = F.loc[:t].iloc[:-1]
    fila = F.loc[t]
    y_real = F["ly"].shift(-1).loc[t]
    if np.isnan(y_real): continue
    act = fila["ly"]
    res["naive (=semana actual)"].append((y_real, act, act, 0.5, fila["sube"]))
    for nombre, cols in M.items():
        trn = tr.dropna(subset=cols + ["objetivo"])
        if fila[cols].isna().any():
            res[nombre].append((y_real, np.nan, act, np.nan, fila["sube"])); continue
        f = ridge(trn[cols].values, trn["objetivo"].values)
        pred_obj = f(fila[cols].values.astype(float)[None, :])[0]
        sig = np.std(trn["objetivo"].values - f(trn[cols].values))
        yhat = fila["nivel4"] + pred_obj
        p_sube = float(Phi((yhat - act) / sig))
        res[nombre].append((y_real, yhat, act, p_sube, fila["sube"]))

p(f"  {'modelo':38s} MAPE   dir.acierto  Brier  (n)")
for nombre, r in res.items():
    a = np.array(r, dtype=float); a = a[~np.isnan(a[:, 1])]
    mape = np.mean(np.abs(np.exp(a[:, 0]) - np.exp(a[:, 1])) / np.exp(a[:, 0])) * 100
    if nombre.startswith("naive"):
        p(f"  {nombre:38s} {mape:5.2f}%     —         —   ({len(a)})"); continue
    acc = np.mean((a[:, 3] > 0.5) == (a[:, 4] == 1)) * 100
    brier = np.mean((a[:, 3] - a[:, 4]) ** 2)
    p(f"  {nombre:38s} {mape:5.2f}%   {acc:5.1f}%     {brier:.3f} ({len(a)})")
p(f"  base: fraccion de semanas que suben = {F.loc[orig, 'sube'].mean():.1%} (Brier de moneda = 0.250)")



# ============================== profundizacion ==============================
out2 = []
def q(*a):
    s = " ".join(str(x) for x in a); print(s); out2.append(s)

q("=== A. POTENCIA")
n = SW["r1_total"].notna().sum(); sd = SW["r1_total"].std()
for col in ["ruptura", "enfriamiento"]:
    k_ = SW[col].sum(); m_ = SW[col].notna().sum()
    q(f"  {col}: {int(k_)} semanas de {m_} ({k_/m_:.1%})")
for frac in (0.05, 0.10, 0.25):
    se = sd / np.sqrt(n * frac * (1 - frac))
    q(f"  MDE (80% potencia, alfa .05) de una bandera presente en {frac:.0%} de {n} semanas: "
      f"{(np.exp(2.8*se)-1)*100:.1f}% (sd resid semanal {sd:.3f}, sin corregir autocorrelacion)")
neff = n * (1 - 0.52) / (1 + 0.52)
q(f"  con AR1 +0.52 el n efectivo es ~{neff:.0f} semanas: MDE bandera 10% = "
  f"{(np.exp(2.8*sd/np.sqrt(neff*0.1*0.9))-1)*100:.1f}%")

q("\n=== B. LAS SEMANAS MAS ALTAS Y MAS BAJAS (residuo tras control + estacionalidad)")
r = SW["r1_total"].sort_values()
fmt = lambda i: f"  {i:%Y-%m-%d} (sem que termina)  {(np.exp(r[i])-1)*100:+6.1f}%  total={int(SW.loc[i,'total'])}  ped={int(SW.loc[i,'ped'])}  zp={SW.loc[i,'zp']:+.1f} zt={SW.loc[i,'zt']:+.1f}"
q(" -- 12 mas bajas"); [q(fmt(i)) for i in r.index[:12]]
q(" -- 12 mas altas"); [q(fmt(i)) for i in r.index[-12:][::-1]]

q("\n=== C. ¿CUANTO EXPLICAN LAS EXTERNAS JUNTAS? (R2 incremental sobre el residuo semanal)")
ext = ["zp", "zt", "zh", "ztmin", "ruptura", "enfriamiento", "nino", "nina", "ceniza", "evento", "feria"]
E = SW[ext].copy()
for c_ in ["zp", "zt", "zh", "ztmin"]:
    E[c_ + "_l1"] = SW[c_].shift(1); E[c_ + "_l2"] = SW[c_].shift(2)
for yname in ["total", "adult", "ped"]:
    y = SW[f"r1_{yname}"]
    ok = E.notna().all(axis=1) & y.notna()
    Z = np.column_stack([np.ones(ok.sum()), E[ok].values])
    b, *_ = np.linalg.lstsq(Z, y[ok].values, rcond=None)
    u = y[ok].values - Z @ b
    r2 = 1 - u.var() / y[ok].var()
    p_ = Z.shape[1] - 1; r2a = 1 - (1 - r2) * (ok.sum() - 1) / (ok.sum() - p_ - 1)
    # R2 con la etiqueta barajada en bloques de 8 semanas: cuanto R2 da el azar
    rng = np.random.default_rng(0); nul = []
    yy = y[ok].values
    for _ in range(300):
        bl = [yy[i:i+8] for i in range(0, len(yy), 8)]; rng.shuffle(bl); ys = np.concatenate(bl)
        bb, *_ = np.linalg.lstsq(Z, ys, rcond=None); nul.append(1 - (ys - Z @ bb).var() / ys.var())
    q(f"  {yname:6s}: R2 {r2:.3f} (ajustado {r2a:.3f}); azar en bloques p95 = {np.quantile(nul,.95):.3f}  (n={ok.sum()}, {p_} variables, sin terremoto)")

q("\n=== D. ¿EL CLIMA PREDICE LA SERIE PEDIATRICA? (origen rodante, h=1 semana, 2024-01 a 2026-08)")
G = S.loc["2021-09-01":FIN].copy()
G["ly"] = np.log(G["ped"].clip(lower=1)); G["nivel4"] = G["ly"].rolling(4).mean()
G["objetivo"] = G["ly"].shift(-1) - G["nivel4"]; G["sube"] = (G["ped"].shift(-1) > G["ped"]).astype(float)
for col in CAL: G[f"dcal_{col}"] = G[col].shift(-1) - G[col].rolling(4).mean()
w_ = G.index.isocalendar().week.values.astype(float) + 1
for h in (1, 2, 3): G[f"s{h}"] = np.sin(2*np.pi*h*w_/52.18); G[f"c{h}"] = np.cos(2*np.pi*h*w_/52.18)
G["escalon"] = (G.index >= "2025-11-01").astype(float); G["mom"] = G["ly"] - G["nivel4"]
for c_ in ["zt", "zh", "zp", "ztmin"]:
    G[c_ + "_0"] = G[c_]; G[c_ + "_1"] = G[c_].shift(1)
base = [f"dcal_{c}" for c in CAL] + ["escalon", "mom"]
Mp = {"P0 nivel+calendario": base,
      "P1 +estacionalidad": base + ["s1", "c1", "s2", "c2", "s3", "c3"],
      "P2 +clima (t, t-1)": base + ["s1", "c1", "s2", "c2", "s3", "c3", "zt_0", "zt_1", "zh_0", "zh_1", "zp_0", "zp_1", "ztmin_0", "ztmin_1"],
      "P2b clima sin estacionalidad": base + ["zt_0", "zt_1", "zh_0", "zh_1", "zp_0", "zp_1", "ztmin_0", "ztmin_1"]}
res = {k: [] for k in Mp}
for t in G.loc["2024-01-01":"2026-08-16"].index:
    tr = G.loc[:t].iloc[:-1]; fila = G.loc[t]; yr = G["ly"].shift(-1).loc[t]
    if np.isnan(yr): continue
    for nombre, cols in Mp.items():
        if fila[cols].isna().any(): continue
        trn = tr.dropna(subset=cols + ["objetivo"])
        f = ridge(trn[cols].values, trn["objetivo"].values)
        sig = np.std(trn["objetivo"].values - f(trn[cols].values))
        yh = fila["nivel4"] + f(fila[cols].values.astype(float)[None, :])[0]
        res[nombre].append((yr, yh, float(Phi((yh - fila["ly"]) / sig)), fila["sube"]))
for nombre, r_ in res.items():
    a = np.array(r_)
    q(f"  {nombre:30s} MAPE {np.mean(np.abs(np.exp(a[:,0])-np.exp(a[:,1]))/np.exp(a[:,0]))*100:5.1f}%  "
      f"dir {np.mean((a[:,2]>.5)==(a[:,3]==1))*100:5.1f}%  Brier {np.mean((a[:,2]-a[:,3])**2):.3f}  (n={len(a)})")

q("\n=== E. ESCALAS: de donde viene la variacion del conteo total (dias 2022-03 a 2026-09, log)")
y = np.log(W["total"]).values
def r2(Z): b, *_ = np.linalg.lstsq(Z.values, y, rcond=None); return 1 - (y - Z.values @ b).var() / y.var()
Zd = diseno_control(W, con_tendencia=False); r_cal = r2(Zd)
Zt = diseno_control(W); r_ct = r2(Zt)
Zs = diseno_control(W, con_mes=True); r_cts = r2(Zs)
q(f"  calendario (dia semana + festivos...)   {r_cal:.1%}")
q(f"  + nivel por ano y escalon 2025-11       +{r_ct - r_cal:.1%}")
q(f"  + estacionalidad anual                  +{r_cts - r_ct:.1%}")
q(f"  queda                                    {1 - r_cts:.1%}  (de lo cual ~{np.mean(1/W['total'])/np.log(W['total']).var():.1%} es piso de Poisson)")
ym = W["total"].resample("MS").mean()
q("  Media diaria por ano:", {int(k_): round(v_, 1) for k_, v_ in D["total"].groupby(D.index.year).mean().items()})

q("\n=== F. TERREMOTO: dia a dia (2026-08-03 a 2026-08-30)")
t_ = D.loc["2026-08-03":"2026-08-30", ["total", "ped"]].copy()
t_["dow"] = t_.index.day_name().str[:3]
q(t_.T.to_string())

