"""
Combinaciones de pronosticos del cuaderno 22 (fila reentrenamiento_holistico de patrones/datos/variables.csv).

    from combinar import promedio, jerarquico_bandas, elegir

promedio            combinacion de modelos por promedio de cuantiles (Vincentizacion), pesos iguales.
jerarquico_bandas   suma de las 5 bandas de edad por copula gaussiana; la correlacion sale de los residuos diarios
                    de las bandas (log, sin dia de semana x mes x ano) de 2022-2024: nada de 2025-2026.
elegir              la regla preregistrada: promedio del BSS de 'sube' con las dos varas, cobertura del 80 %
                    entre 75 y 88 %; desempate, MAPE.
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

import pronostico as pr


def promedio(partes, nombre):
    """partes: DataFrames con las columnas de rodar(). Devuelve la combinacion por promedio de cuantiles."""
    P = pd.concat(partes); g = P.groupby(["origen", "h", "fecha"])
    c = g[pr.QCOL].mean().reset_index(); c["real"] = g.real.first().values
    c = c[g.size().values == len(partes)]; c["modelo"] = nombre
    return c


def correlacion_bandas():
    ed = pd.read_parquet(pr.RAIZ / "salidas/triage_edad.parquet"); ed["dia"] = pd.to_datetime(ed.dia)
    E = ed[ed.banda != "sin edad"].pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").loc["2022-01-01":"2024-12-31"]
    E = E.drop(pd.date_range("2024-03-19", "2024-03-21"), errors="ignore")
    L = np.log1p(E); clave = [L.index.dayofweek, L.index.month, L.index.year]
    R = L - L.groupby(clave).transform("mean")
    return R.corr(method="spearman")


def jerarquico_bandas(partes_por_banda, real_total, nombre="jerarquico_edad", n=4000, semilla=0):
    """partes_por_banda: {banda: DataFrame de rodar()}. real_total: Serie del triage total por fecha."""
    rho = correlacion_bandas().loc[list(partes_por_banda), list(partes_por_banda)].values
    u = norm.cdf(np.random.default_rng(semilla).multivariate_normal(np.zeros(len(rho)), rho, size=n))
    M = None
    for b, P in partes_por_banda.items():
        t = P.set_index(["origen", "h", "fecha"])[pr.QCOL].add_suffix(f"|{b}")
        M = t if M is None else M.join(t, how="inner")
    bandas = list(partes_por_banda)
    Q = [M[[f"{c}|{b}" for c in pr.QCOL]].values for b in bandas]
    tot = np.empty((len(M), len(pr.QL)))
    for i in range(len(M)):
        s = sum(np.interp(u[:, j], pr.QL, Q[j][i]) for j in range(len(bandas)))
        tot[i] = np.quantile(s, pr.QL)
    out = M.index.to_frame(index=False)
    for j, c in enumerate(pr.QCOL): out[c] = tot[:, j]
    out["real"] = real_total.reindex(out.fecha).values; out["modelo"] = nombre
    return out


def tabla(P):
    """Las metricas de la regla de eleccion, con las dos varas."""
    fil = {}
    for vara in ["calendario", "rapido"]:
        _, U = pr.leer(["control"], exp="e0", vara=vara)
        _, T = pr.metricas(P, U)
        fil[vara] = T
    T = pd.DataFrame({"BSS sube (28 dias) %": fil["calendario"]["BSS sube %"], "BSS sube (rapida) %": fil["rapido"]["BSS sube %"],
                      "acierta (28 dias) %": fil["calendario"]["acierta sube/baja %"], "acierta (rapida) %": fil["rapido"]["acierta sube/baja %"],
                      "BSS pico (28 dias) %": fil["calendario"]["BSS pico %"], "cob80 %": fil["calendario"]["cob80 %"],
                      "MAPE %": fil["calendario"]["MAPE %"], "n": fil["calendario"]["n"]})
    T["criterio (promedio BSS)"] = (T["BSS sube (28 dias) %"] + T["BSS sube (rapida) %"]) / 2
    T["cobertura valida"] = T["cob80 %"].between(75, 88)
    return T


def elegir(T, candidatos):
    t = T.loc[[c for c in candidatos if c in T.index]]
    v = t[t["cobertura valida"]]
    v = v if len(v) else t
    return v.sort_values(["criterio (promedio BSS)", "MAPE %"], ascending=[False, True]).index[0]
