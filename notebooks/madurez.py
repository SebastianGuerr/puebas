"""
¿Está madura la predicción? Las cinco pruebas del cuaderno 26 (fila madurez_de_la_prediccion de
patrones/datos/variables.csv), sobre las predicciones ya guardadas en salidas/pronostico/; solo la curva por
adelanto exige correr modelos.

    python notebooks/madurez.py --curva       adelantos 8 y 22 de la respuesta semanal (C0r y M3s), unas 2-3 h
    python notebooks/madurez.py               las cinco pruebas; escribe salidas/pronostico/madurez/

No consulta la base ni reentrena nada para elegir.
"""
import argparse
import json
import time
import warnings

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm
from scipy.special import xlogy

import pronostico as pr

CARPETA = pr.SALIDA / "madurez"
CURVA = CARPETA / "curva_8_22.parquet"
SEMANAL = pr.SALIDA / "semanal" / "validacion_semanal.parquet"
QL, QCOL = pr.QL, pr.QCOL
ULTIMO = "2026-09-20"
CORTE_2026 = "2025-12-28"                     # como semana.resumen_validacion: la semana del 29-dic-2025 es de 2026


def correr_curva():
    """Los adelantos 8 (dias 8-14) y 22 (dias 22-28), con el mismo diseno que la validacion de m3_semanal."""
    import semana as sm                       # semana fija pr.H = 21 al importarse: H se sube despues
    pr.H = 28
    CARPETA.mkdir(parents=True, exist_ok=True)
    t = time.time()
    sm.validar(avisar=lambda s: print(s, flush=True), combos=["C0r", "M3s"], adelantos=(8, 22), archivo=CURVA)
    print(f"curva lista en {time.time() - t:.0f} s -> {CURVA}", flush=True)


# ------------------------------------------------------------------ datos y vara unica (prueba 1)
def serie():
    """Triage diario hasta el ultimo dia completo, con la caida de registro de marzo de 2024 como faltante."""
    s = pd.read_parquet(pr.RAIZ / "salidas/triage_diario.parquet"); s["dia"] = pd.to_datetime(s.dia)
    y = s.set_index("dia").triages.astype(float).loc[:ULTIMO].asfreq("D")
    y["2024-03-19":"2024-03-21"] = np.nan
    return y


def reportado():
    """Conteos de una fuente externa escritos a mano: solo para comparar, nunca para entrenar."""
    f = pr.RAIZ / "datos/triage_reportado.csv"
    if not f.exists(): return pd.Series(dtype=float)
    r = pd.read_csv(f, parse_dates=["fecha"]); return r.set_index("fecha").triages.astype(float)


def _semanas_atras(origen, fecha):
    o = pd.to_datetime(pd.Series(origen)).values; t = pd.to_datetime(pd.Series(fecha)).values
    h = ((t - o) / np.timedelta64(1, "D")).astype(int)
    return t, np.ceil(h / 7).astype(int)              # t - 7*k0 es el mismo dia de la semana, ya conocido en el origen


def vara(y, origen, fecha):
    """V: media del mismo dia de la semana en las 8 semanas que terminan en el origen (minimo 4 dias observados)."""
    t, k0 = _semanas_atras(origen, fecha)
    vals = np.column_stack([y.reindex(pd.DatetimeIndex(t - (7 * (k0 + k)).astype("timedelta64[D]"))).values
                            for k in range(8)])
    n = (~np.isnan(vals)).sum(axis=1)
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return np.where(n >= 4, np.nanmean(vals, axis=1), np.nan)


def ultima_semana(y, origen, fecha):
    """Base sin modelo: el mismo dia de la semana mas reciente que ya se conoce en el origen."""
    t, k0 = _semanas_atras(origen, fecha)
    return y.reindex(pd.DatetimeIndex(t - (7 * k0).astype("timedelta64[D]"))).values


def enriquecer(P, y):
    """Agrega a filas con cuantiles: V, sube, P(sube), puntaje de cuantiles relativo, error, Brier, cobertura y z."""
    P = P.dropna(subset=["real"]).copy()
    P["V"] = vara(y, P.origen, P.fecha)
    P = P.dropna(subset=["V"]).reset_index(drop=True)
    Q = np.sort(P[QCOL].values, axis=1)
    P[QCOL] = Q
    P["sube"] = (P.real > P.V).astype(int)
    P["p_sube"] = pr.prob_sobre(Q, P.V.values)
    P["pin"] = np.mean([np.maximum(q * (P.real - Q[:, j]), (q - 1) * (P.real - Q[:, j]))
                        for j, q in enumerate(QL)], axis=0) / P.real
    P["ape"] = (P.q50 - P.real).abs() / P.real
    P["brier"] = (P.p_sube - P.sube) ** 2
    P["acierta"] = ((P.p_sube > .5) == (P.sube == 1)).astype(int)
    P["cob80"] = P.real.between(P.q10, P.q90).astype(int)
    P["z"] = norm.ppf([np.interp(r, q, QL, left=.01, right=.99) for q, r in zip(Q, P.real.values)])
    return P


def resumir(g):
    b = g.sube.mean()
    return pd.Series({"dias": len(g), "puntaje cuantiles %": 100 * g.pin.mean(), "error del dia %": 100 * g.ape.mean(),
                      "acierto sube %": 100 * g.acierta.mean(), "tasa base %": 100 * max(b, 1 - b),
                      "BSS sube %": 100 * (1 - g.brier.mean() / (b * (1 - b))) if 0 < b < 1 else np.nan,
                      "cobertura 80 %": 100 * g.cob80.mean()})


def vara_comparada(y):
    """Prueba 1: que fraccion de dias 'sube' con cada vara usada hasta hoy, en los mismos dias (rodante, h 1-7)."""
    C = pd.read_parquet(pr.SALIDA / "control.parquet").dropna(subset=["real"])
    C = C.merge(pd.read_parquet(pr.SALIDA / "_umbrales.parquet"), on=["origen", "h"])
    C = C.merge(pd.read_parquet(pr.SALIDA / "_umbrales_rapido.parquet").rename(
        columns={"esperado_cal": "rapido"}).drop(columns="sd_cal"), on=["origen", "h"])
    C["V"] = vara(y, C.origen, C.fecha); C = C.dropna(subset=["V"])
    filas = []
    for a, g in C.groupby(C.fecha.dt.year):
        filas.append({"año": a, "días (origen x adelanto)": len(g),
                      "sube con el control de 28 días %": 100 * (g.real > g.esperado_cal).mean(),
                      "sube con el control rápido %": 100 * (g.real > g.rapido).mean(),
                      "sube con V %": 100 * (g.real > g.V).mean(),
                      "V y el control de 28 días discrepan %": 100 * ((g.real > g.V) != (g.real > g.esperado_cal)).mean()})
    return pd.DataFrame(filas).set_index("año")


# ------------------------------------------------------------------ prueba 2: curva por adelanto
def curva(y):
    """Filas por dia de la respuesta semanal en los adelantos 1, 8, 15 y 22 (C0r, M3s y el control)."""
    partes = [pd.read_parquet(SEMANAL)]
    if CURVA.exists(): partes.append(pd.read_parquet(CURVA))
    P = pd.concat(partes, ignore_index=True).rename(columns={"combo": "modelo"})
    P = P[P.modelo.isin(["C0r", "M3s"])]
    P = P[["modelo", "origen", "h", "fecha", "real", "adelanto", *QCOL, "normal", "umbral_pico"]]
    C = P[P.modelo == "C0r"].copy()                    # el control es el mismo para las dos combinaciones
    sd = np.log(C.umbral_pico / C.normal)              # cuantiles lognormales alrededor de su mediana
    for q, c in zip(QL, QCOL): C[c] = C.normal * np.exp(sd * norm.ppf(q))
    P = pd.concat([P, C.assign(modelo="control")], ignore_index=True).drop(columns=["normal", "umbral_pico"])
    P = enriquecer(P, y)
    P["anio"] = np.where(P.origen < CORTE_2026, 2025, 2026)
    B = P[P.modelo == "control"].copy()
    B["ape_V"] = (B.V - B.real).abs() / B.real
    B["ape_ult"] = np.abs(ultima_semana(y, B.origen, B.fecha) - B.real) / B.real
    return P, B


def tabla_curva(P, B):
    T = P.groupby(["modelo", "anio", "h"]).apply(resumir)
    bases = B.groupby(["anio", "h"])[["ape_V", "ape_ult"]].mean() * 100
    return T, bases.rename(columns={"ape_V": "error de V %", "ape_ult": "error de la última semana %"})


def utiles(T):
    """Regla: util si en 2025 y 2026 a la vez el acierto supera la tasa base y el puntaje es menor que el del control."""
    filas = []
    for m in ["C0r", "M3s"]:
        for h in sorted(T.index.get_level_values("h").unique()):
            if (m, 2025, h) not in T.index or (m, 2026, h) not in T.index: continue
            ok = {}
            for a in (2025, 2026):
                t, c = T.loc[(m, a, h)], T.loc[("control", a, h)]
                ok[a] = (t["acierto sube %"] > t["tasa base %"], t["puntaje cuantiles %"] < c["puntaje cuantiles %"])
            sn = lambda v: "sí" if v else "no"
            filas.append({"modelo": m, "h": h,
                          "supera la tasa base (2025, 2026)": f"{sn(ok[2025][0])}, {sn(ok[2026][0])}",
                          "puntaje menor que el control (2025, 2026)": f"{sn(ok[2025][1])}, {sn(ok[2026][1])}",
                          "útil": all(ok[2025]) and all(ok[2026])})
    return pd.DataFrame(filas)


def lejanos(y):
    """Puntos lejanos de la curva: el mes a ciegas (septiembres de 2023-2026) y la revision (marzo, julio, agosto)."""
    rep = reportado(); partes = []
    for a in (2023, 2024, 2025, 2026):
        d = pd.read_parquet(pr.SALIDA / f"mes_a_ciegas/{a}.parquet").assign(fuente=f"septiembre {a}")
        d["real"] = d.real.fillna(d.fecha.map(rep))           # del 21 al 27 de septiembre de 2026: conteo reportado
        partes.append(d)
    for mes, nom in [("2026-03", "marzo 2026"), ("2026-07", "julio 2026"), ("2026-08", "agosto 2026")]:
        partes.append(pd.read_parquet(pr.SALIDA / f"revision/{mes}_desde_2025-12-31.parquet").assign(fuente=nom))
    P = pd.concat(partes, ignore_index=True)
    P = P[P.modelo.isin(["M3s", "C0r", "normal"])].replace({"modelo": {"normal": "control"}})
    P = enriquecer(P, y.combine_first(rep))
    T = P.groupby(["fuente", "modelo"], sort=False).apply(resumir)
    T.insert(0, "adelanto (días)", P.groupby(["fuente", "modelo"], sort=False).h.agg(lambda h: f"{h.min()}-{h.max()}"))
    return P, T


# ------------------------------------------------------------------ prueba 3: SPA y MCS
E0 = ["chronos2", "chronos2_cal", "control", "glm_binneg", "ingenuo", "lightgbm", "prophet", "sarimax"]
DISENOS = {
    2025: {**{f"e0 {m}": f"{m}.parquet" for m in E0},
           "e1 sarimax": "e1_2025/sarimax.parquet", "e1 lightgbm": "e1_2025/lightgbm.parquet",
           "e1 lightgbm_rel": "e1_2025/lightgbm_rel.parquet", "Cg lightgbm_rel": "g_2025/lightgbm_rel.parquet",
           "C1 sarimax": "h_2025/sarimax.parquet", "C1 lightgbm": "h_2025/lightgbm.parquet",
           "M1 sarimax_mec": "m1_2025/sarimax_mec.parquet", "M1 lightgbm_rel_mec": "m1_2025/lightgbm_rel_mec.parquet",
           "M2 lightgbm_rel_mec": "m2_2025/lightgbm_rel_mec.parquet",
           "M3 sarimax_mec": "m3_2025/sarimax_mec.parquet", "M3 lightgbm_rel_mec": "m3_2025/lightgbm_rel_mec.parquet"},
    2026: {**{f"e0 {m}": f"{m}.parquet" for m in E0},
           **{f"e1 {m}": f"e1/{m}.parquet" for m in ["chronos2_cal", "comb_4_modelos", "comb_sarimax_lightgbm",
              "gbr_afinado", "glm_binneg", "lightgbm", "lightgbm_afinado", "lightgbm_rel", "prophet", "sarimax",
              "xgboost_afinado"]},
           **{f"e2 {m}": f"e2/{m}.parquet" for m in ["glm_binneg", "lightgbm", "prophet"]},
           **{f"e3 {m}": f"e3/{m}.parquet" for m in ["chronos2_cal", "glm_binneg", "lightgbm", "sarimax"]},
           "Cg lightgbm_rel": "g/lightgbm_rel.parquet",
           "M3 sarimax_mec": "m3/sarimax_mec.parquet", "M3 lightgbm_rel_mec": "m3/lightgbm_rel_mec.parquet"}}
COMBINADOS = {2025: {"C0": ["e1 sarimax", "e1 lightgbm"], "C1": ["C1 sarimax", "C1 lightgbm"],
                     "Cg": ["e1 sarimax", "Cg lightgbm_rel"]},
              2026: {"Cg": ["e1 sarimax", "Cg lightgbm_rel"]}}
ORIGENES = {2025: ("2024-12-31", "2025-12-24"), 2026: ("2025-12-31", "2026-09-13")}
PERDIDAS = {"pin": "puntaje de cuantiles", "brier": "Brier de sube", "ape": "error de la mediana"}


def disenos(anio, y):
    """Todas las predicciones del ano, por diseno, con las perdidas calculadas sobre la vara unica. Solo origenes
    completos (7 adelantos con dato) en todos los disenos."""
    D = {n: pd.read_parquet(pr.SALIDA / f) for n, f in DISENOS[anio].items()}
    for n, (a, b) in COMBINADOS[anio].items():             # promedio de cuantiles, como se definieron en su dia
        P = pd.concat([D[a], D[b]]); g = P.groupby(["origen", "h", "fecha"])
        c = g[QCOL].mean().reset_index(); c["real"] = g.real.first().values
        D[n] = c[g.size().values == 2]
    for m, g in pd.read_parquet(pr.SALIDA / f"mecanismos/_combos_{anio}.parquet").groupby("modelo"): D[m] = g
    o0, o1 = ORIGENES[anio]
    P = pd.concat([d[(d.origen >= o0) & (d.origen <= o1)][["origen", "h", "fecha", "real", *QCOL]].assign(diseno=n)
                   for n, d in D.items()], ignore_index=True)
    P = enriquecer(P, y)
    completos = P.groupby(["diseno", "origen"]).h.count().unstack(0)
    return P[P.origen.isin(completos.index[(completos == 7).all(axis=1)])]


def spa_mcs(anio, y, reps=5000, bloque=14):
    from arch.bootstrap import MCS, SPA
    P = disenos(anio, y); filas, incl = [], {}
    for perd in PERDIDAS:
        L = P.groupby(["origen", "diseno"])[perd].mean().unstack()
        for bench in ["e0 control", "C0r"]:
            otros = L.drop(columns=bench); mejor = otros.mean().idxmin()
            s = SPA(L[bench].values, otros.values, block_size=bloque, reps=reps, bootstrap="stationary", seed=0)
            s.compute()
            s1 = SPA(L[bench].values, L[["M3"]].values, block_size=bloque, reps=reps, bootstrap="stationary", seed=0)
            s1.compute()
            filas.append({"año": anio, "pérdida": PERDIDAS[perd], "comparador": bench, "diseños": otros.shape[1],
                          "orígenes": len(L), "mejor diseño": mejor,
                          "mejora del mejor %": 100 * (1 - otros[mejor].mean() / L[bench].mean()),
                          "p SPA, todos": float(s.pvalues["consistent"]),
                          "mejora de M3 %": 100 * (1 - L["M3"].mean() / L[bench].mean()),
                          "p SPA, solo M3": float(s1.pvalues["consistent"])})
        m = MCS(L, size=.10, reps=reps, block_size=bloque, method="R", bootstrap="stationary", seed=0)
        m.compute()
        incl[perd] = pd.DataFrame({"pérdida media": L.mean(), "p MCS": m.pvalues.iloc[:, 0].reindex(L.columns),
                                   "en el conjunto": L.columns.isin(m.included)}, index=L.columns).sort_values("pérdida media")
    return pd.DataFrame(filas), incl


# ------------------------------------------------------------------ prueba 4: cobertura
def _ll(x, n, p):
    return xlogy(n - x, 1 - p) + xlogy(x, p)


def kupiec_christoffersen(fallos, p=.2):
    """fallos: 1 si el real cayo fuera del rango del 80 %, en orden de fecha. Kupiec (1995) para la proporcion,
    Christoffersen (1998) para la independencia y la cobertura condicional."""
    f = np.asarray(fallos, dtype=int); n, x = len(f), int(f.sum())
    lr_pof = -2 * (_ll(x, n, p) - _ll(x, n, x / n))
    a, b = f[:-1], f[1:]
    n00, n01 = int(((a == 0) & (b == 0)).sum()), int(((a == 0) & (b == 1)).sum())
    n10, n11 = int(((a == 1) & (b == 0)).sum()), int(((a == 1) & (b == 1)).sum())
    p01, p11 = n01 / max(n00 + n01, 1), n11 / max(n10 + n11, 1)
    p1 = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)
    lr_ind = -2 * (_ll(n01 + n11, n00 + n01 + n10 + n11, p1) - _ll(n01, n00 + n01, p01) - _ll(n11, n10 + n11, p11))
    return {"n": n, "fuera del rango %": 100 * x / n, "P(fuera | ayer fuera) %": 100 * p11,
            "P(fuera | ayer dentro) %": 100 * p01, "p Kupiec": float(chi2.sf(lr_pof, 1)),
            "p independencia": float(chi2.sf(lr_ind, 1)), "p cobertura condicional": float(chi2.sf(lr_pof + lr_ind, 2))}


def coberturas(y, Pcurva, Plej):
    filas = []
    def agregar(serie_, modelo, anio, g):
        filas.append({"serie": serie_, "modelo": modelo, "año": anio,
                      **kupiec_christoffersen(1 - g.sort_values("fecha").cob80.values)})
    for anio in (2025, 2026):
        c = pd.read_parquet(pr.SALIDA / f"mecanismos/_combos_{anio}.parquet")
        c = enriquecer(c[(c.h == 1) & (c.fecha.dt.year == anio)], y)
        for m, g in c.groupby("modelo"): agregar("rodante diario, adelanto 1", m, anio, g)
    for (m, lead, a), g in Pcurva.groupby(["modelo", "adelanto", "anio"]):
        agregar(f"semanal, días {lead}-{lead + 6}", m, a, g)
    for (fu, m), g in Plej[Plej.fuente.str.startswith("septiembre")].groupby(["fuente", "modelo"]):
        agregar("mes a ciegas", m, int(fu[-4:]), g)
    return pd.DataFrame(filas)


def cobertura_semana(Pcurva):
    """La media de la semana con su rango (copula de semana.py, rho medida en 2025 por modelo y adelanto). Kupiec."""
    import semana as sm
    filas = []
    for (m, lead), G in Pcurva[Pcurva.modelo != "control"].groupby(["modelo", "adelanto"]):
        Z = G[G.anio == 2025].pivot_table(index="origen", columns="h", values="z")
        rho = float(np.nanmean([Z.iloc[:, j].corr(Z.iloc[:, j + 1]) for j in range(Z.shape[1] - 1)]))
        for a, Ga in G.groupby("anio"):
            dentro = []
            for o, g in Ga.groupby("origen"):
                if len(g) < 7: continue
                s = sm.semana_agregada(g.sort_values("h")[QCOL].values, rho)
                dentro.append(np.quantile(s, .1) <= g.real.mean() <= np.quantile(s, .9))
            d = np.array(dentro); n, x = len(d), int((~d).sum())
            filas.append({"modelo": m, "días": f"{lead}-{lead + 6}", "año": a, "rho (2025)": rho, "semanas": n,
                          "semana en el rango %": 100 * d.mean(),
                          "p Kupiec": float(chi2.sf(-2 * (_ll(x, n, .2) - _ll(x, n, x / n)), 1))})
    return pd.DataFrame(filas)


def pit_tabla(Pcurva):
    """Proporcion de dias por debajo de cada cuantil, frente a la nominal."""
    filas = []
    for (m, lead), g in Pcurva[Pcurva.modelo != "control"].groupby(["modelo", "adelanto"]):
        filas.append({"modelo": m, "días": f"{lead}-{lead + 6}", **{c: 100 * (g.real < g[c]).mean() for c in QCOL}})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ prueba 5: vigilancia
def cusum(z, k=.5, H=5.):
    """CUSUM tabular de dos lados sobre z ~ N(0, 1) si el modelo esta calibrado; se reinicia tras cada alarma.
    'arriba' = lo real queda por encima de lo anunciado (el modelo se queda corto)."""
    sp = sn = 0.; S, alarmas = [], []
    for i, v in enumerate(z):
        sp = max(0., sp + v - k); sn = max(0., sn - v - k)
        S.append((sp, sn))
        if sp > H or sn > H:
            alarmas.append((i, "arriba" if sp > H else "abajo")); sp = sn = 0.
    return np.array(S), alarmas


def vigilancia(Pcurva, modelo="M3s"):
    filas, series = [], {}
    for lead in sorted(Pcurva.adelanto.unique()):
        g = Pcurva[(Pcurva.modelo == modelo) & (Pcurva.adelanto == lead)].sort_values("fecha")
        S, al = cusum(g.z.values)
        series[lead] = g.assign(c_arriba=S[:, 0], c_abajo=S[:, 1]).reset_index(drop=True)
        filas += [{"días": f"{lead}-{lead + 6}", "fecha": g.fecha.iloc[i].date(), "lado": lado} for i, lado in al]
    return pd.DataFrame(filas, columns=["días", "fecha", "lado"]), series


def prospectivas(y):
    """Las predicciones guardadas antes de conocer lo real, con cuantos de sus dias ya tienen dato."""
    real = y.combine_first(reportado()); filas = []
    for f in sorted((pr.SALIDA / "semanal").glob("semana_*.json")) + sorted((pr.SALIDA / "prueba_ciega").glob("*.json")):
        W = json.loads(f.read_text(encoding="utf-8")); fechas = pd.date_range(W["lunes"], periods=7)
        filas.append({"predicción": f.stem, "datos hasta": W["origen"], "días": f"{W['lunes']} a {fechas[-1].date()}",
                      "adelanto": f"{W['adelanto_dias']}-{W['adelanto_dias'] + 6}", "guardada": W.get("creado", "")[:10],
                      "días con dato real": int(real.reindex(fechas).notna().sum()), "de": 7})
    for f in sorted((pr.SALIDA / "revision").glob("2026-10*.json")):
        W = json.loads(f.read_text(encoding="utf-8")); fechas = pd.date_range("2026-10-01", "2026-10-31")
        filas.append({"predicción": f.stem, "datos hasta": ULTIMO, "días": "2026-10-01 a 2026-10-31", "adelanto": "11-41",
                      "guardada": str(W.get("creado", ""))[:10], "días con dato real": int(real.reindex(fechas).notna().sum()),
                      "de": 31})
    fechas = pd.date_range("2026-09-01", "2026-09-30")
    filas.append({"predicción": "mes a ciegas, septiembre de 2026", "datos hasta": "2025-12-31",
                  "días": "2026-09-01 a 2026-09-30", "adelanto": "244-273", "guardada": "2026-10-07",
                  "días con dato real": int(real.reindex(fechas).notna().sum()), "de": 30})
    return pd.DataFrame(filas)


# ------------------------------------------------------------------ uso C: el dia dentro de un nivel estable
def meses_estables(y):
    m = y.resample("MS").mean(); cambio = (m / m.shift(1) - 1).abs()
    return cambio[cambio < .05].index.to_period("M")


def nivel_estable(Pcurva, y):
    G = Pcurva[Pcurva.fecha.dt.to_period("M").isin(meses_estables(y)) & Pcurva.adelanto.isin([1, 15])]
    return G.groupby(["adelanto", "anio", "modelo"]).apply(resumir)


# ------------------------------------------------------------------ todo
def calcular(avisar=print):
    CARPETA.mkdir(parents=True, exist_ok=True); y = serie()
    vara_comparada(y).to_csv(CARPETA / "vara.csv")
    P, B = curva(y); P.to_parquet(CARPETA / "curva_filas.parquet")
    T, bases = tabla_curva(P, B); T.to_csv(CARPETA / "curva.csv"); bases.to_csv(CARPETA / "curva_bases.csv")
    utiles(T).to_csv(CARPETA / "utiles.csv", index=False)
    Pl, Tl = lejanos(y); Tl.to_csv(CARPETA / "lejanos.csv"); Pl.to_parquet(CARPETA / "lejanos_filas.parquet")
    avisar("curva, vara y lejanos listos")
    coberturas(y, P, Pl).to_csv(CARPETA / "cobertura.csv", index=False)
    cobertura_semana(P).to_csv(CARPETA / "cobertura_semana.csv", index=False)
    pit_tabla(P).to_csv(CARPETA / "pit.csv", index=False)
    al, _ = vigilancia(P); al.to_csv(CARPETA / "cusum_alarmas.csv", index=False)
    prospectivas(y).to_csv(CARPETA / "prospectivas.csv", index=False)
    nivel_estable(P, y).to_csv(CARPETA / "nivel_estable.csv")
    avisar("cobertura, vigilancia y nivel estable listos")
    spa(y, avisar)


def spa(y=None, avisar=print, rehacer=False):
    """SPA y MCS no dependen de la curva: se calculan una vez (semilla fija) y no se repiten salvo con rehacer."""
    y = serie() if y is None else y
    for a in (2025, 2026):
        if (CARPETA / f"spa_{a}.csv").exists() and not rehacer: continue
        t, incl = spa_mcs(a, y)
        t.to_csv(CARPETA / f"spa_{a}.csv", index=False)
        for perd, d in incl.items(): d.to_csv(CARPETA / f"mcs_{a}_{perd}.csv")
        avisar(f"SPA y MCS de {a} listos")


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--curva", action="store_true")
    ap.add_argument("--spa", action="store_true", help="solo SPA y MCS (rehace lo que ya exista)")
    a = ap.parse_args()
    if a.curva:
        correr_curva()
    elif a.spa:
        spa(avisar=lambda s: print(s, flush=True), rehacer=True)
    else:
        calcular(avisar=lambda s: print(s, flush=True))
