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
            "T5": dict(rel=True, covid=.1, vida=1.5, raro=2., bolsas=10),
            # entrenamiento curado (fila entrenamiento_curado; marcas en marcas.py): S1 equilibra los tipos de contexto
            # por peso; S2 escoge las fechas: todas las marcadas, COVID una de cada 3 y estables una de cada 2
            "S0": dict(rel=True), "S1": dict(rel=True, curado="equilibrado"), "S2": dict(rel=True, curado="seleccion"),
            # contexto con compuerta (fila contexto_con_compuerta): cada capa solo cuando su gatillo esta activo
            "G1": dict(rel=True, compuerta=True), "G2": dict(rel=True, curado="equilibrado", compuerta=True)}
GATILLOS = {"clima": ["transición de clima", "clima extremo"], "salud": ["ola de salud pública"], "red": ["red de salud"],
            "regímenes": ["El Niño / La Niña fuerte", "sismo"]}


def compuerta(X, D):
    """H en compuerta: cada capa es NaN cuando su gatillo no esta activo. Marcas externas con 1 dia de rezago."""
    import marcas
    M = D["marcas"][marcas.TIPOS].astype(float)
    M = M.shift(1).assign(**{"calendario especial": M["calendario especial"]}).reindex(X.index).fillna(0) > 0
    X = X.copy()
    for capa_, tipos in GATILLOS.items():
        cols = [c for c in X.columns if D["capa"].get(c) == capa_]
        if cols: X.loc[~M[tipos].any(axis=1), cols] = np.nan
    for t in marcas.TIPOS: X[f"marca_{t}"] = M[t].astype(float)
    return X


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
    import marcas
    return dict(X=X, ly=ly, capa=pd.Series({c: capa(c) for c in X.columns}), raro=raro, covid=covid,
                marcas=marcas.marcar(X.index))


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
    if t.get("curado"):
        import marcas
        M = D["marcas"].reindex(idx)[marcas.TIPOS + ["estable"]]
        if t["curado"] == "equilibrado":                  # cada tipo pesa lo mismo: mediana(N_tipo) / N_tipo
            n = M.sum(); f = (n[n > 0].median() / n.replace(0, np.nan)).fillna(0)
            v = (M * f).sum(axis=1) / M.sum(axis=1).clip(lower=1)
            w *= np.minimum(v.values / v.mean(), 3)
        else:                                             # seleccion sistematica por orden de fecha
            covid, estable = M["COVID"].values, M["estable"].values
            w[covid & (np.cumsum(covid) % 3 != 1)] = 0
            w[estable & ~covid & (np.cumsum(estable & ~covid) % 2 != 1)] = 0
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
        L = una(np.flatnonzero(w > 0))                    # peso 0 = fecha no escogida (S2)
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
                if t.get("compuerta") and j != "base":
                    XX = compuerta(X[cols], D); Q = cuantiles(XX.loc[Xa.index], ya, XX.loc[Xb.index], w, t)
                else:
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


def evaluar_curado(P, ref=("S0", "base")):
    """Entrenamiento curado y compuerta (filas entrenamiento_curado y contexto_con_compuerta): BSS de sube en los
    dias marcados, en los estables y en todos, por ano; el veredicto de la regla y el BSS por tipo de contexto."""
    import marcas
    M = marcas.marcar(pd.date_range("2020-01-01", P.fecha.max()))
    P = P.join(M, on="fecha"); P["marcado"] = ~P.estable & ~P["COVID"]
    def bss(g):
        bs = g.sube.mean(); return 100 * (1 - np.mean((g.p - g.sube) ** 2) / (bs * (1 - bs))) if 0 < bs < 1 else np.nan
    T = P.groupby(["tecnica", "juego", "año"]).apply(lambda g: pd.Series({
        "BSS marcados": bss(g[g.marcado]), "BSS estables": bss(g[g.estable]), "BSS todos": bss(g),
        "acierta todos %": 100 * np.mean((g.p > .5) == (g.sube == 1)), "cob80 %": 100 * np.mean((g.real >= g.q10) & (g.real <= g.q90))}))
    r = T.loc[ref]; filas = []
    for (t, j), G in T.groupby(level=[0, 1]):
        if (t, j) == ref: continue
        G = G.droplevel([0, 1]); dm = G["BSS marcados"] - r["BSS marcados"]; de = G["BSS estables"] - r["BSS estables"]
        filas.append({"diseño": t, "juego": j, "años que mejora en marcados": int((dm > 0).sum()),
                      "mejora media en marcados": round(dm.mean(), 1), "cambio medio en estables": round(de.mean(), 1),
                      "¿sirve?": "SÍ" if (dm > 0).sum() >= 3 and de.mean() >= -2 else "no"})
    tipos = {tp: {f"{t} · {j}": bss(P[(P.tecnica == t) & (P.juego == j) & P[tp]]) for t, j in T.index.droplevel(2).unique()}
             for tp in marcas.TIPOS if tp != "COVID"}
    return T, pd.DataFrame(filas).set_index(["diseño", "juego"]), pd.DataFrame(tipos).T
