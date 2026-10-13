"""
El reparto del día: de los triages que se esperan en un día, cuántos llegan en cada franja (madrugada, mañana,
tarde y noche) y en cada hora, con su rango, y en qué horas se concentra la demanda (fila reparto_del_dia y su
enmienda en patrones/datos/variables.csv).

    python notebooks/reparto.py          evalúa los perfiles sobre la validación semanal guardada y escribe
                                         salidas/pronostico/reparto/

No reentrena el total del día: lo toma de salidas/pronostico/semanal/validacion_semanal.parquet. No consulta la base.
"""
import argparse
import warnings

import numpy as np
import pandas as pd
from scipy.stats import chi2, norm

import pronostico as pr

CARPETA = pr.SALIDA / "reparto"
SEMANAL = pr.SALIDA / "semanal" / "validacion_semanal.parquet"
FRANJAS = {"madrugada": (0, 5), "mañana": (6, 11), "tarde": (12, 17), "noche": (18, 23)}
CANDIDATOS = {"P8": ("media", 8), "P26": ("media", 26), "P52": ("media", 52), "S26": ("suma", 26)}
BLOQUES = {"mañana": range(6, 12), "tarde": range(13, 19)}     # inicio de bloques de 3 horas (enmienda)
# caida de registro de marzo de 2024. El 2026-09-21 estuvo aqui (incompleto) hasta la extraccion del 2026-10-13,
# que lo trajo completo; el ultimo dia a medias de cada extraccion lo quita la operacion (operacion._preparar)
MALOS = pd.to_datetime(["2024-03-19", "2024-03-20", "2024-03-21"])
CORTE_2026 = "2025-12-28"
NSIM = 4000


def horas():
    """Matriz día x 24 horas de triages (hora sin fila = 0); los días de caída de registro quedan fuera."""
    h = pd.read_parquet(pr.RAIZ / "salidas/triage_horario.parquet")
    H = h.pivot_table(index=pd.to_datetime(h.dia), columns="hora", values="triages", aggfunc="sum")
    H = H.reindex(columns=range(24)).fillna(0)
    H = H.reindex(pd.date_range(H.index.min(), H.index.max())).fillna(0)
    return H.drop(MALOS, errors="ignore")


def festivos():
    cal = pd.read_csv(pr.RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
    f = pd.to_numeric(cal["es_festivo"], errors="coerce").fillna(0) > 0
    return set(f.index[f & (f.index.dayofweek != 6)])


def dispersion(C):
    """a de la Dirichlet-multinomial por momentos, sin contar dos veces el ruido de conteo (enmienda)."""
    n = C.sum(1); S = C.div(n, axis=0); p = S.mean().values; v = S.var(ddof=1).values; nm = n.mean()
    ok = p > .01
    r = v[ok] * nm / (p[ok] * (1 - p[ok]))
    a = np.where(r <= 1, 5000, (nm - r) / np.where(r <= 1, 2, r - 1))
    return float(np.median(np.clip(a, 20, 5000)))


class Perfiles:
    """Perfil horario (proporción del día por hora) y su dispersión, con solo días <= origen."""
    def __init__(self, H, fest):
        self.H, self.fest, self.cache = H, fest, {}

    def perfil(self, cand, o, fecha, F=False):
        clave = (cand, o, fecha.dayofweek, F and fecha in self.fest)
        if clave in self.cache: return self.cache[clave]
        H = self.H.loc[:o]
        if clave[3]:                                     # festivo no domingo: los festivos de las 104 semanas
            d = H[(H.index > o - pd.Timedelta(weeks=104)) & H.index.isin(self.fest)]
            if len(d) >= 5:
                r = self.cache[clave] = (d.sum().values / d.values.sum(), dispersion(d))
                return r
            fecha = fecha + pd.Timedelta(days=6 - fecha.dayofweek)    # sin festivos suficientes: perfil de domingo
        modo, sem = CANDIDATOS[cand]
        mismo = H[H.index.dayofweek == fecha.dayofweek]
        d = mismo.tail(sem)
        p = d.sum().values / d.values.sum() if modo == "suma" else d.div(d.sum(1), axis=0).mean().values
        a = dispersion(mismo[mismo.index > o - pd.Timedelta(weeks=52)])
        self.cache[clave] = (p, a)
        return p, a


def simular(q, p, a, rng, n=NSIM):
    """Conteos por hora (n x 24): total del día de sus cuantiles, proporciones Dirichlet, conteo multinomial."""
    T = np.round(np.interp(rng.uniform(pr.QL[0], pr.QL[-1], n), pr.QL, q)).astype(int).clip(0)
    P = rng.dirichlet(a * p + 1e-6, size=n)
    return rng.multinomial(T, P)


def _cuantil(q, u):
    """Cuantil u de la distribucion dada por q en pr.QL: interpolacion del log en la escala normal, y fuera de
    [0,02; 0,98] extrapolacion lineal con la pendiente de los dos cuantiles extremos (fila rango_recalibrado)."""
    s, lq, z = norm.ppf(pr.QL), np.log(np.maximum(q, 1)), norm.ppf(u)
    v = np.interp(z, s, lq)
    v = np.where(z < s[0], lq[0] + (z - s[0]) * (lq[1] - lq[0]) / (s[1] - s[0]), v)
    v = np.where(z > s[-1], lq[-1] + (z - s[-1]) * (lq[-1] - lq[-2]) / (s[-1] - s[-2]), v)
    return np.exp(v)


def recalibrar(P, metodo, ventana=56, minimo=14):
    """R1: escala k = desviacion de z en los resultados ya conocidos en el origen (56 dias); R2: ademas desplaza mu."""
    P = P.copy(); Q = np.sort(P[pr.QCOL].values, axis=1); P[pr.QCOL] = Q
    if metodo == "R0": return P
    P["z"] = norm.ppf([np.interp(r, q, pr.QL, left=.01, right=.99) for q, r in zip(Q, P.real.values)])
    s = norm.ppf(pr.QL)
    for (combo, lead), G in P.groupby(["combo", "adelanto"]):
        for o in G.origen.unique():
            w = G[(G.fecha <= o) & (G.fecha > o - pd.Timedelta(days=ventana))].z
            if len(w) < minimo: continue
            k = float(np.clip(w.std(ddof=1), .8, 3)); mu = float(np.clip(w.mean(), -2, 2)) if metodo == "R2" else 0.
            i = G.index[G.origen == o]
            P.loc[i, pr.QCOL] = np.vstack([_cuantil(q, norm.cdf(mu + k * s)) for q in Q[P.index.get_indexer(i)]])
    return P.drop(columns="z")


def evaluar_rango(P, y):
    """Puntaje, error, cobertura (Kupiec y Christoffersen) y sube con la vara de 8 semanas, por combo, adelanto y ano."""
    import madurez as md
    E = md.enriquecer(P, y); E["anio"] = np.where(E.origen < CORTE_2026, 2025, 2026)
    filas = []
    for (combo, lead, anio), g in E.groupby(["combo", "adelanto", "anio"]):
        kc = md.kupiec_christoffersen(1 - g.sort_values("fecha").cob80.values)
        filas.append({"combo": combo, "adelanto": lead, "año": anio, **md.resumir(g).to_dict(),
                      "p Kupiec": kc["p Kupiec"], "p cobertura condicional": kc["p cobertura condicional"],
                      "P(fuera | ayer fuera) %": kc["P(fuera | ayer fuera) %"]})
    return pd.DataFrame(filas).set_index(["combo", "adelanto", "año"])


def kupiec(dentro, nominal=.8):
    n, x = len(dentro), int((~dentro).sum()); pf = 1 - nominal
    if x in (0, n): return np.nan
    lr = -2 * ((n - x) * np.log(1 - pf) + x * np.log(pf) - (n - x) * np.log(1 - x / n) - x * np.log(x / n))
    return float(chi2.sf(lr, 1))


def evaluar(P, H, fest, avisar=print):
    """Distancia de reparto por candidato (la elección) y, para todos, conteos por franja y hora con rango."""
    pf = Perfiles(H, fest); rng = np.random.default_rng(0)
    P = P[P.fecha.isin(H.index)].copy()
    P["anio"] = np.where(P.origen < CORTE_2026, 2025, 2026)
    reales = H.loc[P.fecha].values; tot = reales.sum(1)
    filas = []
    for k, (i, r) in enumerate(P.iterrows()):
        real = reales[k]
        for cand in CANDIDATOS:
            for F in (False, True):
                p, a = pf.perfil(cand, r.origen, r.fecha, F)
                fila = {"i": i, "candidato": cand + ("F" if F else ""), "tv": .5 * np.abs(p - real / tot[k]).sum()}
                filas.append(fila)
        if k % 500 == 0: avisar(f"  distancias {k}/{len(P)}")
    D = pd.DataFrame(filas).merge(P[["fecha", "origen", "adelanto", "combo", "anio"]], left_on="i", right_index=True)
    return P, D


def elegir(D):
    """Menor distancia media en 2025 a adelanto 15; con menos de 0,1 puntos de diferencia, el más simple."""
    orden = [c for c in CANDIDATOS] + [c + "F" for c in CANDIDATOS]
    m = D[(D.anio == 2025) & (D.adelanto == 15) & (D.combo == "M3s")].groupby("candidato").tv.mean() * 100
    mejor = m.min()
    return next(c for c in orden if m[c] - mejor < .1), m


def conteos(P, H, fest, cand, avisar=print):
    """Por cada día predicho: mediana y rango 80 % por franja y hora, con el total predicho y con el real."""
    pf = Perfiles(H, fest); rng = np.random.default_rng(0)
    base, F = cand.rstrip("F"), cand.endswith("F")
    reales = H.loc[P.fecha].values; filas = []
    for k, (i, r) in enumerate(P.iterrows()):
        p, a = pf.perfil(base, r.origen, r.fecha, F)
        X = simular(r[pr.QCOL].values.astype(float), p, a, rng)
        real = reales[k]; T = real.sum()
        piso = rng.poisson(np.maximum(real, .5), size=(NSIM // 4, 24))
        out = {"i": i}
        for f, (lo, hi) in FRANJAS.items():
            x = X[:, lo:hi + 1].sum(1); rf = real[lo:hi + 1].sum()
            out |= {f"{f}_q10": np.quantile(x, .1), f"{f}_q50": np.quantile(x, .5), f"{f}_q90": np.quantile(x, .9),
                    f"{f}_real": rf, f"{f}_con_total_real": T * p[lo:hi + 1].sum(),
                    f"{f}_piso": np.mean(np.abs(piso[:, lo:hi + 1].sum(1) - rf)) / max(rf, 1)}
        q10, q50, q90 = np.quantile(X, [.1, .5, .9], axis=0)
        out |= {"hora_ae": np.abs(q50 - real).mean(), "hora_ae_total_real": np.abs(T * p - real).mean(),
                "hora_en_rango": ((real >= q10) & (real <= q90)).mean(),
                "hora_piso": np.abs(piso - real).mean()}
        esp = p                                          # bloques de demanda: solo dependen del perfil
        for f, inicios in BLOQUES.items():
            b = max(inicios, key=lambda s: esp[s:s + 3].sum())
            tramo = range(inicios[0], inicios[-1] + 3); mx = max(real[h] for h in tramo)
            out |= {f"bloque_{f}": b, f"bloque_{f}_acierta": any(real[h] == mx for h in range(b, b + 3))}
        filas.append(out)
        if k % 500 == 0: avisar(f"  conteos {k}/{len(P)}")
    viejas = {c: f"antes_{c}" for c in P.columns if c.startswith(("mañana_", "tarde_"))}   # semana.py: 8 semanas, sin rango propio
    return P.rename(columns=viejas).join(pd.DataFrame(filas).set_index("i"))


def bloque_base(H):
    """El bloque fijo más frecuente de 2024 (con datos de 2024), igual para todos."""
    R = {}
    for f, inicios in BLOQUES.items():
        mejor = H.loc["2024"].apply(lambda d: max(inicios, key=lambda s: d.values[s:s + 3].sum()), axis=1)
        R[f] = int(mejor.mode()[0])
    return R


def resumir(C, base):
    filas = []
    for (combo, lead, anio), G in C.groupby(["combo", "adelanto", "anio"]):
        fila = {"combo": combo, "adelanto": lead, "año": anio, "días": len(G),
                "error del día %": 100 * np.mean(np.abs(G.q50 - G.real) / G.real)}
        for f in FRANJAS:
            e = np.abs(G[f"{f}_q50"] - G[f"{f}_real"]) / G[f"{f}_real"].clip(lower=1)
            dentro = (G[f"{f}_real"] >= G[f"{f}_q10"]) & (G[f"{f}_real"] <= G[f"{f}_q90"])
            fila |= {f"{f}: media real": G[f"{f}_real"].mean(), f"{f}: error %": 100 * e.mean(),
                     f"{f}: error con total real %": 100 * np.mean(np.abs(G[f"{f}_con_total_real"] - G[f"{f}_real"]) / G[f"{f}_real"].clip(lower=1)),
                     f"{f}: piso de ruido %": 100 * G[f"{f}_piso"].mean(),
                     f"{f}: en rango 80 %": 100 * dentro.mean(), f"{f}: Kupiec p": kupiec(dentro.values)}
        for f in ("mañana", "tarde"):
            dentro = (G[f"antes_{f}_real"] >= G[f"antes_{f}_q10"]) & (G[f"antes_{f}_real"] <= G[f"antes_{f}_q90"])
            fila |= {f"{f} con semana.py: error %": 100 * np.mean(np.abs(G[f"antes_{f}_q50"] - G[f"antes_{f}_real"]) / G[f"antes_{f}_real"].clip(lower=1)),
                     f"{f} con semana.py: en rango 80 %": 100 * dentro.mean()}
        fila |= {"hora: error medio (pacientes)": G.hora_ae.mean(), "hora: con total real": G.hora_ae_total_real.mean(),
                 "hora: piso de ruido": G.hora_piso.mean(), "hora: en rango 80 %": 100 * G.hora_en_rango.mean()}
        for f in BLOQUES:
            b = base[f]
            fila |= {f"bloque {f}: acierta %": 100 * G[f"bloque_{f}_acierta"].mean(),
                     f"bloque {f}: más elegido": f"{int(G[f'bloque_{f}'].mode()[0])}-{int(G[f'bloque_{f}'].mode()[0]) + 3} h"}
        filas.append(fila)
    return pd.DataFrame(filas).set_index(["combo", "adelanto", "año"])


def acierto_base(C, H, base):
    """Acierto del bloque fijo de 2024 en los mismos días."""
    R = []
    for (combo, lead, anio), G in C.groupby(["combo", "adelanto", "anio"]):
        fila = {"combo": combo, "adelanto": lead, "año": anio}
        for f, inicios in BLOQUES.items():
            b = base[f]; tramo = range(inicios[0], inicios[-1] + 3); X = H.loc[G.fecha].values
            fila[f"bloque fijo {f} {b}-{b + 3} h: acierta %"] = 100 * np.mean(
                [any(x[h] == max(x[t] for t in tramo) for h in range(b, b + 3)) for x in X])
        R.append(fila)
    return pd.DataFrame(R).set_index(["combo", "adelanto", "año"])


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--solo-eleccion", action="store_true", help="solo las distancias en 2025 y el perfil elegido")
    ap.add_argument("--rango", action="store_true", help="recalibrado del rango del dia (fila rango_recalibrado)")
    a = ap.parse_args()
    pd.set_option("display.width", 250)
    if a.rango:
        import madurez as md
        CARPETA.mkdir(parents=True, exist_ok=True)
        y = md.serie(); P = pd.read_parquet(SEMANAL).dropna(subset=["real"]).reset_index(drop=True)
        R = {m: recalibrar(P, m) for m in ("R0", "R1", "R2")}
        T = pd.concat({m: evaluar_rango(R[m], y) for m in R}, names=["método"])
        T.to_csv(CARPETA / "rango_recalibrado.csv")
        pin = T.xs(("M3s", 15, 2025), level=["combo", "adelanto", "año"])["puntaje cuantiles %"]
        mejor = "R0"
        if (pin["R0"] - pin[["R1", "R2"]].min()) / pin["R0"] >= .01:
            mejor = "R1" if (pin["R1"] - pin["R2"]) / pin["R1"] < .01 else "R2"
        print(pin.round(3).to_string()); print(f"Elegido: {mejor}")
        R[mejor].to_parquet(CARPETA / "validacion_recalibrada.parquet")
        (CARPETA / "rango_eleccion.txt").write_text(f"{mejor}\n" + pin.round(4).to_string(), encoding="utf-8")
        print(T.round(2).to_string())
        raise SystemExit
    CARPETA.mkdir(parents=True, exist_ok=True)
    H, fest = horas(), festivos()
    P = pd.read_parquet(SEMANAL).dropna(subset=["real"])
    P, D = evaluar(P, H, fest)
    D.to_parquet(CARPETA / "distancias.parquet")
    cand, m = elegir(D)
    print("Distancia media en 2025, adelanto 15, M3s (puntos del día mal repartidos):")
    print(m.round(3).to_string()); print(f"Elegido: {cand}")
    (CARPETA / "eleccion.txt").write_text(f"{cand}\n" + m.round(4).to_string(), encoding="utf-8")
    if not a.solo_eleccion:
        C = conteos(P, H, fest, cand)
        C.to_parquet(CARPETA / "conteos.parquet")
        base = bloque_base(H)
        T = resumir(C, base).join(acierto_base(C, H, base))
        T.to_csv(CARPETA / "resumen.csv")
        tv = D.groupby(["candidato", "adelanto", "anio"]).tv.mean().unstack([1, 2]) * 100
        tv.to_csv(CARPETA / "distancias_resumen.csv")
        pd.set_option("display.width", 250)
        print(tv.round(2).to_string()); print(T.round(1).T.to_string())
