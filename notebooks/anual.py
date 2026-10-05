"""
Validacion anual de capas y tecnicas de entrenamiento (cuaderno 23; filas validacion_por_capas_multianual y
tecnicas_de_entrenamiento de patrones/datos/variables.csv).

    import anual
    D = anual.preparar()
    V, P = anual.correr(D, juegos=["base", "base + todo H"], tecnicas=["T0"])

Para cada ano de prueba se entrena un LightGBM por cuantiles con todo lo anterior (modelo congelado ese ano) y se
predice el ano a 1 dia. La vara es el control de calendario + nivel, ajustado con los mismos anos. El porque de
cada tecnica y su fuente estan en notebooks/23_catalogo_y_validacion_multianual.ipynb.
"""
import numpy as np
import pandas as pd
import lightgbm as lgb

import pronostico as pr
import indices as ix

JUEGOS = {"base": ["base"], "base + clima": ["base", "clima"], "base + salud pública": ["base", "salud"],
          "base + red": ["base", "red"], "base + regímenes": ["base", "regímenes"],
          "base + todo H": ["base", "clima", "salud", "red", "regímenes"]}

# rel: objetivo log(y) - nivel; covid: peso de los dias COVID; vida: vida media del decaimiento (anos);
# raro: peso extra de los dias de contexto raro (crisis de la red, ola respiratoria, racha seca; El Nino y La Nina
# no: juntos cubren el 67 % de los dias de 2020-2026); bolsas: remuestreos de bloques de 28 dias
TECNICAS = {"original": dict(rel=False), "T0": dict(rel=True), "T1": dict(rel=True, covid=.1),
            "T2": dict(rel=True, vida=1.5), "T3": dict(rel=True, raro=2.), "T4": dict(rel=True, bolsas=10),
            "T5": dict(rel=True, covid=.1, vida=1.5, raro=2., bolsas=10)}


def capa(c):
    if not c.startswith("ext_h_"): return "base"
    if c.startswith("ext_h_fam_"): return "salud"
    if c.startswith(("ext_h_peso", "ext_h_cambio_nueva", "ext_h_cambio_resto", "ext_h_herf", "ext_h_resol")): return "red"
    if c.startswith(("ext_h_oni", "ext_h_el_", "ext_h_la_", "ext_h_sismo")): return "regímenes"
    return "clima"


def preparar():
    """Entradas a 1 dia con el contexto H, el log del triage y las marcas de COVID y de contexto raro."""
    pr.usar("h"); y, cal = pr.cargar(); cal = cal.reindex(y.index)
    PAS = ix.contexto_holistico(cal.index).reindex(y.index)
    X = pr.rasgos(y, cal, 1, (PAS, pd.DataFrame(index=y.index)))
    ok = X.notna().all(axis=1) & y.notna(); X, ly = X[ok], np.log(y[ok])
    R = ix.regimenes_diarios().reindex(X.index).fillna(0)
    raro = (R.crisis_red + (PAS.ext_h_fam_respiratoria > 1) + (PAS.ext_h_racha_seca > 14)).reindex(X.index) > 0
    covid = (R.covid_fuerte + R.covid_parcial) > 0
    return dict(X=X, ly=ly, capa=pd.Series({c: capa(c) for c in X.columns}), raro=raro, covid=covid)


CTRL = lambda X: [c for c in X.columns if c.startswith(("dow_", "es_")) or c == "nivel"]


def control(Xa, ya, Xb):
    """Calendario + nivel en log por minimos cuadrados: la esperanza del dia y la desviacion de su residuo."""
    c = CTRL(Xa); Z = np.c_[np.ones(len(Xa)), Xa[c].values]; b, *_ = np.linalg.lstsq(Z, ya.values, rcond=None)
    return np.exp(np.c_[np.ones(len(Xb)), Xb[c].values] @ b), np.std(ya.values - Z @ b)


def pesos(idx, D, t):
    w = np.ones(len(idx))
    if t.get("covid") is not None: w[D["covid"].reindex(idx).values] = t["covid"]
    if t.get("vida"): w *= 0.5 ** ((idx.max() - idx).days.values / (365.25 * t["vida"]))
    if t.get("raro"): w[D["raro"].reindex(idx).values] *= t["raro"]
    return w


def cuantiles(Xa, ya, Xb, w, t, semilla=0):
    """Los 9 cuantiles del conteo para Xb. Con bolsas, promedio de cuantiles (Vincentizacion) sobre remuestreos
    de bloques de 28 dias del entrenamiento."""
    off_a = Xa.nivel.values if t.get("rel") else 0.
    off_b = Xb.nivel.values if t.get("rel") else np.zeros(len(Xb))
    Xa_, Xb_ = (Xa.drop(columns="nivel"), Xb.drop(columns="nivel")) if t.get("rel") else (Xa, Xb)
    obj = ya.values - off_a
    def una(ii):
        return np.column_stack([lgb.LGBMRegressor(objective="quantile", alpha=q, **pr.LightGBM.PARAM)
                                .fit(Xa_.iloc[ii], obj[ii], sample_weight=w[ii]).predict(Xb_) for q in pr.QL])
    n = len(Xa_)
    if not t.get("bolsas"):
        L = una(np.arange(n))
    else:
        rng = np.random.default_rng(semilla); ini = np.arange(0, n - 27)
        L = np.mean([una(np.concatenate([np.arange(s, s + 28) for s in rng.choice(ini, n // 28)])) for _ in range(t["bolsas"])], axis=0)
    return np.sort(np.exp(L + np.asarray(off_b)[:, None]), axis=1)


def correr(D, juegos, tecnicas, anios=(2022, 2023, 2024, 2025, 2026), avisar=print):
    """Probabilidades diarias por ano, juego y tecnica. 2022 sirve solo para calibrar 2023."""
    X, ly = D["X"], D["ly"]; filas = []
    for a in anios:
        Xa, ya = X.loc[:f"{a - 1}-12-31"], ly.loc[:f"{a - 1}-12-31"]
        Xb, yb = X.loc[f"{a}-01-01":f"{a}-12-31"], ly.loc[f"{a}-01-01":f"{a}-12-31"]
        esp, sd = control(Xa, ya, Xb); real = np.exp(yb.values)
        for nt in tecnicas:
            t = TECNICAS[nt]; w = pesos(Xa.index, D, t)
            for j in juegos:
                cols = [c for c in X.columns if D["capa"][c] in JUEGOS[j]]
                Q = cuantiles(Xa[cols], ya, Xb[cols], w, t)
                filas.append(pd.DataFrame({"año": a, "tecnica": nt, "juego": j, "fecha": Xb.index, "real": real, "esp": esp,
                                           "sube": (real > esp).astype(int), "pico": (real > esp * np.exp(sd)).astype(int),
                                           "p": pr.prob_sobre(Q, esp), "p_pico": pr.prob_sobre(Q, esp * np.exp(sd)),
                                           "q10": Q[:, 2], "q50": Q[:, 4], "q90": Q[:, 6]}))
            avisar(f"{a} {nt} listo")
    return pd.concat(filas, ignore_index=True)


def platt(P):
    """Calibracion de Platt de p con el ano anterior (misma tecnica y juego): logistica sobre logit(p)."""
    from sklearn.linear_model import LogisticRegression
    lg = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))[:, None]
    out = []
    for (nt, j), G in P.groupby(["tecnica", "juego"]):
        for a, A in G.groupby("año"):
            prev = G[G["año"] == a - 1]
            if prev.empty: continue
            m = LogisticRegression(C=1e6).fit(lg(prev.p.values), prev.sube.values)
            out.append(A.assign(p_cal=m.predict_proba(lg(A.p.values))[:, 1]))
    return pd.concat(out, ignore_index=True)


def metricas(P, col="p"):
    def m(g):
        bs = g.sube.mean(); bp = g.pico.mean()
        return pd.Series({"acierta sube/baja %": 100 * ((g[col] > .5) == (g.sube == 1)).mean(),
                          "BSS sube %": 100 * (1 - np.mean((g[col] - g.sube) ** 2) / (bs * (1 - bs))),
                          "BSS pico %": 100 * (1 - np.mean((g.p_pico - g.pico) ** 2) / (bp * (1 - bp))),
                          "Brier sube": np.mean((g[col] - g.sube) ** 2),
                          "cob80 %": 100 * np.mean((g.real >= g.q10) & (g.real <= g.q90)),
                          "MAPE %": 100 * np.mean(np.abs(g.q50 - g.real) / g.real),
                          "P > 0,70 %": 100 * np.mean(g[col] > .7), "P < 0,30 %": 100 * np.mean(g[col] < .3), "días": len(g)})
    return P.groupby(["tecnica", "juego", "año"]).apply(m)


if __name__ == "__main__":
    import time
    t0 = time.time(); D = preparar(); dir_ = pr.RAIZ / "salidas/pronostico"
    tres = ["base", "base + salud pública", "base + todo H"]
    correr(D, tres, list(TECNICAS), avisar=lambda s: print(s, round(time.time() - t0), "s", flush=True)).to_parquet(dir_ / "anual_tecnicas.parquet")
    correr(D, [j for j in JUEGOS if j not in tres], ["original", "T0"], avisar=print).to_parquet(dir_ / "anual_capas.parquet")
