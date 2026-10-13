"""
De qué aseguradora llegan: el total del día repartido por grupo de aseguradora, y para los grupos grandes por jornada
(fila reparto_por_aseguradora de patrones/datos/variables.csv).

    python notebooks/aseguradoras.py      evalúa sobre la validación semanal guardada y escribe salidas/pronostico/aseguradoras/

No reentrena el total del día ni consulta la base: usa salidas/triage_entidad.parquet y la clasificación de
salidas/entidades_clasificadas.csv.
"""
import warnings

import numpy as np
import pandas as pd

import pronostico as pr
import reparto as rp

CARPETA = pr.SALIDA / "aseguradoras"
GRUPOS = ["nueva_eps", "sura_eps", "otra_eps", "regimen_especial", "soat", "arl", "prepagada", "resto"]
NOMBRES = {"nueva_eps": "Nueva EPS", "sura_eps": "Sura EPS", "otra_eps": "Otras EPS", "regimen_especial": "Régimen especial",
           "soat": "SOAT (tránsito)", "arl": "ARL (laboral)", "prepagada": "Prepagada", "resto": "Otros"}
A_GRUPO = {"soat_aseguradora": "soat"} | {g: g for g in GRUPOS} | {
    g: "resto" for g in ("particular", "ente_territorial", "adres_fosyga", "ips_remitente", "sin_entidad", "otro",
                         "nueva_eps_complementario")}
CANDIDATOS = {"T4": ("todos", 4), "T8": ("todos", 8), "T13": ("todos", 13), "T26": ("todos", 26),
              "D8": ("dia", 8), "D26": ("dia", 26)}
GRANDES = ["nueva_eps", "sura_eps"]
CAMBIOS_NE = ["2025-11", "2026-03", "2026-07"]
NSIM = 4000


def conteos_grupo():
    """Cubo día x hora x grupo (horas sin fila = 0)."""
    e = pd.read_parquet(pr.RAIZ / "salidas/triage_entidad.parquet")
    k = pd.read_csv(pr.RAIZ / "salidas/entidades_clasificadas.csv")[["entidad_oid", "grupo"]]
    e = e.merge(k, on="entidad_oid", how="left")
    e["grupo"] = e.grupo.fillna("sin_entidad").map(A_GRUPO).fillna("resto")
    e["dia"] = pd.to_datetime(e.dia)
    c = e.groupby(["dia", "hora", "grupo"]).n.sum()
    dias = pd.date_range(e.dia.min(), e.dia.max())
    idx = pd.MultiIndex.from_product([dias, range(24), GRUPOS], names=["dia", "hora", "grupo"])
    X = c.reindex(idx, fill_value=0).values.reshape(len(dias), 24, len(GRUPOS)).astype(float)
    malos = np.isin(dias, rp.MALOS)
    return dias[~malos], X[~malos]


class Proporciones:
    """Proporción de cada grupo en el día y dentro de cada jornada, con solo días <= origen."""
    def __init__(self, dias, X):
        self.dias, self.X, self.cache = pd.DatetimeIndex(dias), X, {}

    def ventana(self, cand, o, fecha):
        modo, sem = CANDIDATOS[cand]
        m = (self.dias <= o) & (self.dias > o - pd.Timedelta(weeks=sem))
        if modo == "dia": m &= self.dias.dayofweek == fecha.dayofweek
        return m

    def dia(self, cand, o, fecha):
        clave = ("dia", cand, o, fecha.dayofweek if CANDIDATOS[cand][0] == "dia" else -1)
        if clave not in self.cache:
            m = self.ventana(cand, o, fecha); D = self.X[m].sum(1)               # días x grupos
            p = D.sum(0) / D.sum()
            m28 = m if m.sum() >= 28 else (self.dias <= o) & (self.dias > o - pd.Timedelta(days=28))
            self.cache[clave] = (p, rp.dispersion(pd.DataFrame(self.X[m28].sum(1))))
        return self.cache[clave]

    def jornada(self, cand, o, fecha):
        """Proporción de cada grupo dentro de cada jornada (jornadas x grupos), razón de sumas en la ventana."""
        clave = ("jornada", cand, o, fecha.dayofweek if CANDIDATOS[cand][0] == "dia" else -1)
        if clave not in self.cache:
            m = self.ventana(cand, o, fecha)
            J = np.stack([self.X[m][:, lo:hi + 1].sum((0, 1)) for lo, hi in rp.FRANJAS.values()])
            self.cache[clave] = J / J.sum(1, keepdims=True)
        return self.cache[clave]


def elegir(P, dias, X):
    pp = Proporciones(dias, X); pos = pd.Series(range(len(dias)), index=dias)
    G = P[(P.anio == 2025) & (P.adelanto == 15) & (P.combo == "M3s")]
    tv = {}
    for cand in CANDIDATOS:
        d = []
        for _, r in G.iterrows():
            real = X[pos[r.fecha]].sum(0); d.append(.5 * np.abs(pp.dia(cand, r.origen, r.fecha)[0] - real / real.sum()).sum())
        tv[cand] = 100 * np.mean(d)
    tv = pd.Series(tv); mejor = tv.min()
    orden = ["T4", "T8", "T13", "T26", "D8", "D26"]
    return next(c for c in orden if tv[c] - mejor < .1), tv


def simular(q, p_jornada, a_j, Pg, a_g, rng, n=NSIM):
    """Total del día -> jornadas (perfil P52) -> grupos dentro de cada jornada. Devuelve n x jornadas x grupos."""
    J = rp.simular(q, p_jornada, a_j, rng, n)                                        # n x 24 horas
    J = np.stack([J[:, lo:hi + 1].sum(1) for lo, hi in rp.FRANJAS.values()], 1)    # n x 4 jornadas
    out = np.zeros((n, len(rp.FRANJAS), len(GRUPOS)), dtype=int)
    for j in range(len(rp.FRANJAS)):
        p = rng.dirichlet(a_g * Pg[j] + 1e-6, size=n)
        out[:, j] = rng.multinomial(J[:, j], p)
    return out


def evaluar(P, dias, X, cand, avisar=print):
    pp = Proporciones(dias, X); pf = rp.Perfiles(rp.horas(), rp.festivos())
    pos = pd.Series(range(len(dias)), index=dias); rng = np.random.default_rng(0); filas = []
    for k, (i, r) in enumerate(P.iterrows()):
        p24, a24 = pf.perfil("P52", r.origen, r.fecha)
        pg, ag = pp.dia(cand, r.origen, r.fecha); Pg = pp.jornada(cand, r.origen, r.fecha)
        S = simular(r[pr.QCOL].values.astype(float), p24, a24, Pg, ag, rng)
        real = X[pos[r.fecha]]; Rj = np.stack([real[lo:hi + 1].sum(0) for lo, hi in rp.FRANJAS.values()])
        Rg = Rj.sum(0); T = Rg.sum(); piso = rng.poisson(np.maximum(Rg, .5), size=(NSIM // 4, len(GRUPOS)))
        fila = {"i": i}
        dia_g = S.sum(1)
        for g, nombre in enumerate(GRUPOS):
            q10, q50, q90 = np.quantile(dia_g[:, g], [.1, .5, .9])
            fila |= {f"{nombre}_q10": q10, f"{nombre}_q50": q50, f"{nombre}_q90": q90, f"{nombre}_real": Rg[g],
                     f"{nombre}_con_total_real": T * pg[g], f"{nombre}_piso": np.abs(piso[:, g] - Rg[g]).mean()}
        for g in GRANDES:
            gi = GRUPOS.index(g)
            for j, jn in enumerate(rp.FRANJAS):
                q10, q50, q90 = np.quantile(S[:, j, gi], [.1, .5, .9])
                fila |= {f"{g}_{jn}_q10": q10, f"{g}_{jn}_q50": q50, f"{g}_{jn}_q90": q90, f"{g}_{jn}_real": Rj[j, gi]}
        filas.append(fila)
        if k % 500 == 0: avisar(f"  {k}/{len(P)}")
    return P.join(pd.DataFrame(filas).set_index("i"))


def resumir(C):
    filas = []
    for (combo, lead, anio), G in C.groupby(["combo", "adelanto", "anio"]):
        for g in GRUPOS:
            real = G[f"{g}_real"]; den = real.clip(lower=1)
            dentro = (real >= G[f"{g}_q10"]) & (real <= G[f"{g}_q90"])
            cambio = G.fecha.dt.strftime("%Y-%m").isin(CAMBIOS_NE)
            filas.append({"combo": combo, "adelanto": lead, "año": anio, "grupo": g, "media real": real.mean(),
                          "error %": 100 * (np.abs(G[f"{g}_q50"] - real) / den).mean(),
                          "error absoluto": np.abs(G[f"{g}_q50"] - real).mean(),
                          "error con total real %": 100 * (np.abs(G[f"{g}_con_total_real"] - real) / den).mean(),
                          "piso de ruido %": 100 * (G[f"{g}_piso"] / den).mean(),
                          "en rango 80 %": 100 * dentro.mean(), "Kupiec p": rp.kupiec(dentro.values),
                          "en rango, meses de cambio NE %": 100 * dentro[cambio].mean() if cambio.any() else np.nan,
                          "error, meses de cambio NE %": 100 * (np.abs(G[f"{g}_q50"] - real) / den)[cambio].mean() if cambio.any() else np.nan})
            if g in GRANDES:
                for jn in rp.FRANJAS:
                    r_ = G[f"{g}_{jn}_real"]; d_ = (r_ >= G[f"{g}_{jn}_q10"]) & (r_ <= G[f"{g}_{jn}_q90"])
                    filas[-1] |= {f"{jn}: media": r_.mean(), f"{jn}: error %": 100 * (np.abs(G[f"{g}_{jn}_q50"] - r_) / r_.clip(lower=1)).mean(),
                                  f"{jn}: en rango 80 %": 100 * d_.mean()}
    return pd.DataFrame(filas).set_index(["combo", "adelanto", "año", "grupo"])


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    CARPETA.mkdir(parents=True, exist_ok=True)
    dias, X = conteos_grupo()
    P = pd.read_parquet(rp.SEMANAL).dropna(subset=["real"])
    P = P[P.fecha.isin(dias) & P.fecha.isin(rp.horas().index)].copy()
    P["anio"] = np.where(P.origen < rp.CORTE_2026, 2025, 2026)
    cand, tv = elegir(P, dias, X)
    print("Distancia media en 2025, adelanto 15, M3s (puntos del día mal repartidos entre aseguradoras):")
    print(tv.round(3).to_string()); print(f"Elegido: {cand}")
    (CARPETA / "eleccion.txt").write_text(f"{cand}\n" + tv.round(4).to_string(), encoding="utf-8")
    C = evaluar(P, dias, X, cand)
    C.to_parquet(CARPETA / "conteos.parquet")
    T = resumir(C); T.to_csv(CARPETA / "resumen.csv")
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
    print(T.xs("M3s", level="combo").round(1).to_string())
