"""
Resiliencia del pronóstico (fila resiliencia de patrones/datos/variables.csv): por cuánto falla después de un golpe,
cuántas semanas tarda en recuperarse, y dos correcciones que no reentrenan: reanclar el nivel de cada aseguradora
cuando los últimos datos muestran un quiebre (R) y ensanchar el rango del total después del quiebre (W).

    python notebooks/resiliencia.py      evalúa sobre la validación semanal y escribe salidas/pronostico/resiliencia/

Va encima de la v2 de la red (notebooks/red.py), que es la que está en operación.
"""
import warnings

import numpy as np
import pandas as pd

import pronostico as pr
import reparto as rp
import aseguradoras as ag
import red as rd

CARPETA = pr.SALIDA / "resiliencia"
GOLPES = {"cierre SES nov-2025": "2025-11-21", "reapertura mar-2026": "2026-03-02", "cierre SES jul-2026": "2026-07-01",
          "sismo ago-2026": "2026-08-10", "reapertura ago-2026": "2026-08-24"}
CORTO, LARGO, SEMANAS, SIGMAS, K_RANGO, TOPE, UMBRAL = 7, 28, 52, 2., 1.5, 12, 1.5


class Quiebre:
    """S_g(o) = log(media de los últimos 7 días / de los últimos 28), por grupo y para el total, con los conteos
    ajustados por día de la semana (52 semanas <= o) y sin festivos no domingo. Quiebre si |S| > 2 sigma de S en las
    52 semanas que terminan 7 días antes de o."""
    def __init__(self, dias, X, desde="2023-06-01"):
        G = pd.DataFrame(X.sum(1), index=pd.DatetimeIndex(dias), columns=ag.GRUPOS)
        G["total"] = G.sum(1)
        self.G = G.reindex(pd.date_range(G.index.min(), G.index.max()))
        fest = rp.festivos()
        self.G.loc[self.G.index.isin(list(fest))] = np.nan                     # festivos no domingo fuera
        self.S = self._serie(pd.Timestamp(desde))

    def _serie(self, desde):
        filas = {}
        for d in self.G.index[self.G.index >= desde]:
            w = self.G.loc[d - pd.Timedelta(weeks=SEMANAS) + pd.Timedelta(days=1):d]
            perfil = w.groupby(w.index.dayofweek).mean() / w.mean()
            a = w / perfil.reindex(w.index.dayofweek).values
            c, l = a.iloc[-CORTO:].mean(), a.iloc[-LARGO:].mean()
            filas[d] = np.log(c / l)
        return pd.DataFrame(filas).T.replace([np.inf, -np.inf], np.nan)

    def _dispara(self, o, col):
        s = self.S.loc[o - pd.Timedelta(weeks=SEMANAS) - pd.Timedelta(days=CORTO):o - pd.Timedelta(days=CORTO), col]
        v = self.S.at[o, col] if o in self.S.index else np.nan
        sd = s.std()
        return (v if np.isfinite(v) and np.isfinite(sd) and abs(v) > SIGMAS * sd else 0.)

    def factores(self, o, ventana_ne=False):
        r = np.array([np.exp(self._dispara(o, g)) for g in ag.GRUPOS])
        if ventana_ne: r[ag.GRUPOS.index(rd.EPS)] = 1.                        # la v2 ya lo corrigió
        return r

    def total(self, o):
        return bool(self._dispara(o, "total") != 0)


def ensanchar(E, k=K_RANGO):
    """W: cuantiles del total ensanchados en los orígenes con quiebre del total: q' = q50 x (q / q50)^k."""
    E = E.copy(); m = E.quiebre_total.astype(bool)
    Q = E.loc[m, pr.QCOL].values; med = E.loc[m, "q50"].values[:, None]
    E.loc[m, pr.QCOL] = med * (np.maximum(Q, 1e-6) / med) ** k
    return E


def recuperacion(E, normal):
    """Por golpe: semanas hasta la primera de dos seguidas con error semanal <= 1,5 x normal, exceso y sesgo."""
    E = E.assign(err=(E.q50 - E.real).abs() / E.real, ses=(E.q50 - E.real) / E.real)
    W = E.groupby(E.fecha - pd.to_timedelta(E.fecha.dt.dayofweek, unit="D"))[["err", "ses"]].mean()
    filas = []
    for nombre, f in GOLPES.items():
        f = pd.Timestamp(f); lun = f - pd.Timedelta(days=f.dayofweek)
        w = W[W.index >= lun].head(TOPE + 1)
        ok = (w.err <= UMBRAL * normal).values
        semanas = next((i for i in range(len(ok) - 1) if ok[i] and ok[i + 1]), TOPE)
        tramo = w.iloc[:max(semanas, 1)]
        filas.append({"golpe": nombre, "semanas de recuperación": semanas,
                      "exceso de error (puntos-semana)": 100 * (tramo.err - normal).clip(lower=0).sum(),
                      "error semanal medio en la recuperación %": 100 * tramo.err.mean(),
                      "sesgo medio %": 100 * tramo.ses.mean()})
    return pd.DataFrame(filas)


def cobertura_en_recuperacion(E, R_tabla):
    """Cobertura del total en las semanas de recuperación de cada golpe (de la propia variante)."""
    dias = []
    for (_, r), f in zip(R_tabla.iterrows(), GOLPES.values()):
        f = pd.Timestamp(f); lun = f - pd.Timedelta(days=f.dayofweek)
        dias.append((lun, lun + pd.Timedelta(weeks=max(int(r["semanas de recuperación"]), 1))))
    m = np.zeros(len(E), bool)
    for a, b in dias: m |= ((E.fecha >= a) & (E.fecha < b)).values
    g = E[m]
    return 100 * g.real.between(g.q10, g.q90).mean(), int(m.sum())


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    CARPETA.mkdir(parents=True, exist_ok=True)
    dias, X = ag.conteos_grupo(); R = rd.registro()
    P = pd.read_parquet(rp.SEMANAL).dropna(subset=["real"])
    P = P[(P.combo == "C0r") & P.fecha.isin(dias) & P.fecha.isin(rp.horas().index)].copy()
    P["anio"] = np.where(P.origen < rp.CORTE_2026, 2025, 2026)
    print("Detector de quiebres...", flush=True)
    qb = Quiebre(dias, X)
    e2 = rd.EfectoV2(R, dias, X)
    print(f"Evaluando v2AR en {len(P)} días...", flush=True)
    E = rd.evaluar(P, dias, X, R, avisar=lambda s: print(s, flush=True), variantes={"v2AR": (e2, "dia_anterior", qb)})
    V = pd.read_parquet(rd.CARPETA / "conteos_v2.parquet")
    V = V[V.variante.isin(["base", "v2A"])]
    W_ = ensanchar(E).assign(variante="v2ARW")
    T_all = pd.concat([V, E, W_], ignore_index=True)
    T_all.to_parquet(CARPETA / "conteos.parquet")
    T = rd.resumir(T_all, ref="v2AR"); T.to_csv(CARPETA / "resumen.csv")
    b15 = V[(V.variante == "base") & (V.adelanto == 15)]
    normal = float(((b15.q50 - b15.real).abs() / b15.real).groupby(
        b15.fecha - pd.to_timedelta(b15.fecha.dt.dayofweek, unit="D")).mean().loc["2025-01-01":"2025-10-31"].median())
    rec, cob = {}, {}
    for v in ["base", "v2A", "v2AR", "v2ARW"]:
        g = T_all[(T_all.variante == v) & (T_all.adelanto == 15)]
        rec[v] = recuperacion(g, normal); cob[v] = cobertura_en_recuperacion(g, rec[v])
    Rt = pd.concat(rec, names=["variante"]).reset_index(level=0); Rt.to_csv(CARPETA / "recuperacion.csv", index=False)
    s = lambda v, a, c: T.loc[(v, 15, a, "todos"), c]
    suma = {v: int(rec[v]["semanas de recuperación"].sum()) for v in rec}
    entra_R = (s("v2AR", 2026, "puntaje cuantiles %") < s("v2A", 2026, "puntaje cuantiles %")
               and s("v2AR", 2025, "puntaje cuantiles %") <= 1.01 * s("v2A", 2025, "puntaje cuantiles %")
               and min(s("v2AR", 2025, "total en rango 80 %"), s("v2AR", 2026, "total en rango 80 %")) >= 70
               and suma["v2AR"] <= suma["v2A"])
    entra_W = (abs(cob["v2ARW"][0] - 80) < abs(cob["v2AR"][0] - 80)
               and all(s("v2ARW", a, "puntaje cuantiles %") <= 1.01 * s("v2AR", a, "puntaje cuantiles %") for a in (2025, 2026)))
    txt = (f"normal (mediana del error semanal, base, ene-oct 2025, adelanto 15): {100 * normal:.2f} %\n"
           f"suma de semanas de recuperación: {suma}\ncobertura del total en las semanas de recuperación: {cob}\n"
           f"R: {'ENTRA' if entra_R else 'NO ENTRA'}\nW: {'ENTRA' if entra_W else 'NO ENTRA'}\n")
    (CARPETA / "regla.txt").write_text(txt, encoding="utf-8")
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    c = ["n", "error del día %", "puntaje cuantiles %", "total en rango 80 %", "Nueva EPS: error %", "Nueva EPS: en rango 80 %",
         "Sura EPS: error %", "Sura EPS: en rango 80 %"]
    print(T[c].round(2).to_string()); print(Rt.round(1).to_string()); print(txt)
