"""
Barrido de ~40 regresores con LazyPredict (docs/CONTEXTO.md, 2026-10-02, «LazyPredict: barrido...»).

    python notebooks/lazypredict_barrido.py            E1 y E3

Particion temporal: entrena hasta 2025-12-31 (desde 2020, COVID marcada), prueba 2026; el modelo queda
congelado el 31-12 (no se reentrena: desventaja declarada frente a los modelos de pronostico.py, que se
reentrenan cada 7 dias). Entradas de rasgos() a 1 dia; objetivo log(triage). Ademas de las metricas de
LazyPredict, el acierto en si sube o baja frente al control de E0, en 2026 y en abril-junio (meses sin
escalones de Nueva EPS).

Escribe salidas/pronostico/lazypredict_<exp>.csv.
"""
import sys, time, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).parent))
import numpy as np
import pandas as pd
import pronostico as pr

CORTE, FIN_PRUEBA = pd.Timestamp("2025-12-31"), pd.Timestamp(pr.FIN)
ESTABLES = [4, 5, 6]


def datos(exp):
    pr.usar(exp); y, cal = pr.cargar()
    ctx = tuple(c.reindex(y.index) for c in pr.contexto_exp(cal.index)) if pr.EXP["contexto"] else None
    X = pr.rasgos(y, cal.reindex(y.index), 1, ctx)
    ok = X.notna().all(axis=1) & y.notna()
    X, y = X[ok], y[ok]
    tr, te = X.index <= CORTE, (X.index > CORTE) & (X.index <= FIN_PRUEBA)
    cols = X.columns[X[tr].std() > 0]
    return X.loc[tr, cols], X.loc[te, cols], np.log(y[tr]), y[te]


def vara():
    """Lo que anunciaba el control de E0 la vispera (h = 1), para medir 'sube o baja'."""
    U = pd.read_parquet(pr.SALIDA / "_umbrales.parquet")
    U = U[U.h == 1].assign(fecha=lambda d: d.origen + pd.Timedelta(days=1))
    return U.set_index("fecha")["esperado_cal"]


def medir(pred, real, esp):
    d = pd.DataFrame({"pred": pred, "real": real, "esp": esp.reindex(real.index)}).dropna()
    ok = np.sign(d.pred - d.esp) == np.sign(d.real - d.esp)
    est = d.index.month.isin(ESTABLES)
    return {"acierta sube/baja %": 100 * ok.mean(), "acierta abr-jun %": 100 * ok[est].mean(),
            "MAPE %": 100 * ((d.pred - d.real).abs() / d.real).mean(),
            "MAPE abr-jun %": 100 * ((d.pred - d.real).abs() / d.real)[est].mean()}


if __name__ == "__main__":
    from lazypredict.Supervised import LazyRegressor
    esp = vara()
    for exp in ["e1", "e3"]:
        t0 = time.time()
        Xtr, Xte, ytr, yte = datos(exp)
        print(f"{exp}: entrena {len(Xtr)} dias ({Xtr.index[0].date()} a {Xtr.index[-1].date()}), prueba {len(Xte)}, {Xtr.shape[1]} entradas", flush=True)
        lr = LazyRegressor(verbose=0, ignore_warnings=True, predictions=True)
        modelos, preds = lr.fit(Xtr, Xte, ytr, np.log(yte))
        filas = []
        for nombre in preds.columns:
            p = pd.Series(np.exp(np.asarray(preds[nombre], dtype=float)), index=Xte.index)
            if not np.all(np.isfinite(p)): continue
            filas.append({"modelo": nombre, **medir(p, yte, esp)})
        T = modelos.join(pd.DataFrame(filas).set_index("modelo")).sort_values("acierta sube/baja %", ascending=False)
        T.to_csv(pr.SALIDA / f"lazypredict_{exp}.csv")
        print(f"{exp} listo en {time.time() - t0:.0f} s; {len(T)} modelos", flush=True)
