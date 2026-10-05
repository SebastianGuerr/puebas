"""
Arboles afinados (fila arboles_afinados de variables.csv; docs/CONTEXTO.md, 2026-10-02 noche).

    python notebooks/arboles.py --exp e1 --familias xgboost gbr lightgbm
    python notebooks/arboles.py --exp e3 --familias lightgbm

Tres etapas que no se mezclan:
  1. AFINAR con 2024: 13 pliegues de origen rodante (reentreno cada 28 dias desde 2024-01-01, se predicen los
     28 dias siguientes a 1 dia); criterio = error absoluto medio del log. Rejillas fijadas en variables.csv.
  2. CALIBRAR con 2025: origen rodante con la configuracion elegida (reentreno cada 7 dias, h = 1 a 7); por
     horizonte, los 9 cuantiles empiricos del error fuera de muestra (log real - log predicho).
  3. PROBAR en 2026: origen rodante como en pronostico.py; distribucion = prediccion x exp(cuantiles de 2025).
Nada de 2026 se mira antes de la etapa 3.

Escribe en salidas/pronostico/<exp>/: <familia>_afinado.parquet (formato de pronostico.py) y
_afinado_<familia>.json (rejilla, configuracion elegida y cuantiles del error).
"""
import argparse, itertools, json, sys, time, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
import pronostico as pr

REJILLAS = {
    "xgboost": {"max_depth": [2, 3, 4], "n_estimators": [200, 500], "learning_rate": [0.03, 0.1]},
    "gbr": {"max_depth": [2, 3], "n_estimators": [200, 500], "learning_rate": [0.03, 0.1]},
    "lightgbm": {"num_leaves": [7, 15, 31], "min_child_samples": [20, 50], "n_estimators": [300, 600]},
}
AFINAR = pd.date_range("2024-01-01", periods=13, freq="28D")
CALIBRAR = ("2024-12-31", "2025-12-24")


def modelo(familia, **p):
    """Arbol de la mediana del log (perdida absoluta), con los fijos de variables.csv."""
    if familia == "xgboost":
        from xgboost import XGBRegressor
        return XGBRegressor(objective="reg:absoluteerror", min_child_weight=10, subsample=.8, colsample_bytree=.8,
                            tree_method="hist", n_jobs=2, random_state=0, **p)
    if familia == "gbr":
        from sklearn.ensemble import GradientBoostingRegressor
        return GradientBoostingRegressor(loss="absolute_error", subsample=.8, random_state=0, **p)
    import lightgbm as lgb
    return lgb.LGBMRegressor(objective="l1", learning_rate=.03, subsample=.8, subsample_freq=1, colsample_bytree=.8,
                             n_jobs=2, verbose=-1, random_state=0, **p)


class Datos:
    def __init__(self, exp):
        pr.usar(exp); self.y, cal = pr.cargar()
        ctx = tuple(c.reindex(self.y.index) for c in pr.contexto_exp(cal.index)) if pr.EXP["contexto"] else None
        self.X = {h: pr.rasgos(self.y, cal.reindex(self.y.index), h, ctx) for h in range(1, pr.H + 1)}
        self.ly = np.log(self.y)

    def entrenar(self, familia, cfg, h, o):
        X = self.X[h].loc[:o]; ok = X.notna().all(axis=1) & self.ly.loc[:o].notna()
        cols = X.columns[X[ok].std() > 0]
        return modelo(familia, **cfg).fit(X.loc[ok, cols], self.ly.loc[:o][ok]), cols

    def predecir(self, m, cols, h, fechas):
        return pd.Series(m.predict(self.X[h].loc[fechas, cols]), index=fechas)


def afinar(D, familia, avisar):
    filas = []
    claves, valores = zip(*REJILLAS[familia].items())
    for combo in itertools.product(*valores):
        cfg = dict(zip(claves, combo)); err = []
        for o in AFINAR:
            m, cols = D.entrenar(familia, cfg, 1, o)
            f = pd.date_range(o + pd.Timedelta(days=1), periods=28)
            f = f[D.X[1].loc[f].notna().all(axis=1).values & D.ly.reindex(f).notna().values]
            err.append((D.predecir(m, cols, 1, f) - D.ly.loc[f]).abs())
        filas.append({**cfg, "mae_log": float(pd.concat(err).mean())}); avisar(f"    {cfg} -> {filas[-1]['mae_log']:.4f}")
    R = pd.DataFrame(filas).sort_values("mae_log")
    return R, {k: (int(v) if float(v).is_integer() else float(v)) for k, v in R.iloc[0][list(claves)].items()}


def rodar(D, familia, cfg, desde, hasta):
    """Origen rodante, reentreno cada REENTRENO dias. Devuelve la prediccion del log por (origen, h, fecha)."""
    filas = []
    for i, o in enumerate(pd.date_range(desde, hasta)):
        if i % pr.REENTRENO == 0:
            M = {h: D.entrenar(familia, cfg, h, o) for h in range(1, pr.H + 1)}
        for h in range(1, pr.H + 1):
            t = o + pd.Timedelta(days=h); m, cols = M[h]
            if D.X[h].loc[t, cols].notna().all():
                filas.append({"origen": o, "h": h, "fecha": t, "pred": float(m.predict(D.X[h].loc[[t], cols])[0])})
    return pd.DataFrame(filas)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="e1"); ap.add_argument("--familias", nargs="+", default=["xgboost", "gbr", "lightgbm"])
    a = ap.parse_args()
    D = Datos(a.exp); car = pr.EXP["carpeta"]; car.mkdir(parents=True, exist_ok=True)
    avisar = lambda s: print(s, flush=True)
    for fam in a.familias:
        t0 = time.time()
        etapa = car / f"_afinado_{fam}_etapas.json"                 # cada etapa se guarda: un corte no repite lo hecho
        E = json.loads(etapa.read_text(encoding="utf-8")) if etapa.exists() else {}
        if "elegida" not in E:
            avisar(f"{a.exp} {fam}: 1) afinar con 2024")
            R, cfg = afinar(D, fam, avisar)
            E.update(rejilla=R.to_dict("records"), elegida=cfg); etapa.write_text(json.dumps(E, indent=1), encoding="utf-8")
        cfg = E["elegida"]; R = pd.DataFrame(E["rejilla"])
        avisar(f"{a.exp} {fam}: elegida {cfg} ({time.time() - t0:.0f} s). 2) calibrar con 2025")
        if "cuantiles_error" not in E:
            C = rodar(D, fam, cfg, *CALIBRAR)
            C["err"] = D.ly.reindex(C.fecha).values - C.pred
            E["cuantiles_error"] = {str(int(h)): list(np.quantile(g.err.dropna(), pr.QL)) for h, g in C.groupby("h")}
            etapa.write_text(json.dumps(E, indent=1), encoding="utf-8")
        QR = {int(h): v for h, v in E["cuantiles_error"].items()}
        avisar(f"{a.exp} {fam}: cuantiles del error a 1 dia {np.round(QR[1], 3)} ({time.time() - t0:.0f} s). 3) probar en 2026")
        T = rodar(D, fam, cfg, *pr.EXPERIMENTOS[a.exp]["origenes"])
        Q = np.exp(T.pred.values[:, None] + np.array([QR[h] for h in T.h])[:, :])
        out = pd.DataFrame({"modelo": f"{fam}_afinado", "origen": T.origen, "h": T.h, "fecha": T.fecha,
                            "real": D.y.reindex(T.fecha).values, **{c: Q[:, j] for j, c in enumerate(pr.QCOL)}})
        out.to_parquet(car / f"{fam}_afinado.parquet")
        (car / f"_afinado_{fam}.json").write_text(json.dumps({"rejilla": R.to_dict("records"), "elegida": cfg,
                                                              "cuantiles_error": QR}, indent=1), encoding="utf-8")
        avisar(f"{a.exp} {fam}_afinado listo en {time.time() - t0:.0f} s")
