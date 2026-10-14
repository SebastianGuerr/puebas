"""
La red de urgencias de Manizales como contexto del pronóstico (fila red_de_urgencias de patrones/datos/variables.csv):
si un hospital cierra o reabre la atención a una aseguradora, el día o la semana cambian, el año no.

    python notebooks/red.py          evalúa el ajuste sobre la validación semanal guardada y escribe salidas/pronostico/red/

Lee el registro escrito a mano datos/eventos_red.csv. No reentrena el total del día: corrige lo ya predicho con lo
que se sabía en cada momento. El porqué está en docs/CONTEXTO.md (entrada del 2026-10-14).
"""
import warnings

import numpy as np
import pandas as pd

import pronostico as pr
import reparto as rp
import aseguradoras as ag

CARPETA = pr.SALIDA / "red"
REGISTRO = pr.RAIZ / "datos" / "eventos_red.csv"
VARIABLES = ["ses_vitales", "ses_restriccion", "externos"]
NOMBRES = {"ses_vitales": "SES solo urgencias vitales", "ses_restriccion": "SES restringe lo no urgente",
           "externos": "otros hospitales cerrados"}
VITALES = {"solo_urgencias_vitales", "cierre_total", "cierre_urgencias"}
EPS = "nueva_eps"                  # la única con episodios y con un grupo de control limpio (Sura)
CONTROL = "sura_eps"
INICIO = pd.Timestamp("2024-01-01")
VENTANA = 28                       # la de T4 y la del nivel de C0r
MIN_SEMANAS = 2
SUAVE = 20                         # aseguradora por hora: peso de la proporción de su jornada
NSIM = 4000
FECHAS = ["fecha_inicio", "fecha_anuncio", "fecha_fin", "fecha_anuncio_fin"]


def registro(archivo=REGISTRO):
    """Los episodios. Sin fecha de anuncio cuenta la de inicio; sin anuncio del fin, la del fin."""
    R = pd.read_csv(archivo, dtype=str, encoding="utf-8").fillna("")
    for c in FECHAS: R[c] = pd.to_datetime(R[c].str.strip().replace("", None), errors="coerce")
    R["fecha_anuncio"] = R.fecha_anuncio.fillna(R.fecha_inicio)
    R["fecha_anuncio_fin"] = R.fecha_anuncio_fin.fillna(R.fecha_fin)
    return R[R.fecha_inicio.notna()].reset_index(drop=True)


def activos(R, dias, tau):
    """Matriz días x episodios: True si el episodio está en curso ese día con lo que se sabía en tau (fecha única o
    una por día). Un fin que todavía no se había anunciado no cuenta: se supone que el episodio sigue."""
    d = pd.DatetimeIndex(dias).values[:, None]
    t = np.broadcast_to(np.asarray(pd.to_datetime(tau), dtype="datetime64[ns]").reshape(-1, 1), d.shape)
    ini, anu = R.fecha_inicio.values[None], R.fecha_anuncio.values[None]
    fin, anf = R.fecha_fin.values[None], R.fecha_anuncio_fin.values[None]
    empezo = (anu <= t) & (ini <= d)
    termino = ~np.isnat(fin) & (fin <= d) & (anf <= t)
    return empezo & ~termino


def estados(R, dias, tau, eps=EPS):
    """Las variables de la fila red_de_urgencias por día (DataFrame días x VARIABLES)."""
    e = R[R.eps == eps].reset_index(drop=True)
    A = activos(e, dias, tau)
    ses = (e.prestador == "SES").values
    out = pd.DataFrame(0., index=pd.DatetimeIndex(dias), columns=VARIABLES)
    out["ses_vitales"] = (A[:, ses & e.tipo.isin(VITALES).values]).any(1).astype(float)
    out["ses_restriccion"] = (A[:, ses & (e.tipo == "restriccion_no_urgente").values]).any(1).astype(float)
    ext = ~ses & (e.alcance_urgencias == "si").values & e.tipo.isin(VITALES).values & (e.prestador != "Municipio").values
    if ext.any():
        P = pd.DataFrame(A[:, ext], columns=e.prestador[ext].values)
        out["externos"] = P.T.groupby(level=0).any().sum().values.astype(float)   # prestadores distintos
    return out


def en_curso(R, dia, tau):
    """Episodios en curso ese día (cualquier aseguradora y tipo), con lo que se sabía en tau: para informar."""
    return R[activos(R, [dia], tau)[0]]


class Efecto:
    """b de la fila red_de_urgencias: primeras diferencias semanales de log(Nueva EPS / Sura), sin intercepto."""
    nombres = coeficientes = VARIABLES

    def __init__(self, R, dias, X):
        self.R, self.cache = R, {}
        G = pd.DataFrame(X.sum(1), index=pd.DatetimeIndex(dias), columns=ag.GRUPOS)
        G = G.reindex(pd.date_range(G.index.min(), G.index.max()))
        lunes = G.index - pd.to_timedelta(G.index.dayofweek, unit="D")
        S = G.groupby(lunes).agg(["sum", "count"])
        completa = (S[(EPS, "count")] == 7) & (S[(CONTROL, "count")] == 7)
        S = S[completa & (S.index >= INICIO)]
        self.y = np.log(S[(EPS, "sum")] / S[(CONTROL, "sum")])

    def estimar(self, o, tau):
        clave = (pd.Timestamp(o), pd.Timestamp(tau))
        if clave in self.cache: return self.cache[clave]
        y = self.y[self.y.index + pd.Timedelta(days=6) <= o]
        b, V = np.zeros(len(VARIABLES)), np.zeros((len(VARIABLES), len(VARIABLES)))
        if len(y) > 10:
            dias = pd.date_range(y.index.min(), y.index.max() + pd.Timedelta(days=6))
            E = estados(self.R, dias, tau)
            Xm = E.groupby(E.index - pd.to_timedelta(E.index.dayofweek, unit="D")).mean().reindex(y.index)
            seguidas = np.r_[False, np.diff(y.index.values).astype("timedelta64[D]").astype(int) == 7]
            dy, dX = y.diff()[seguidas], Xm.diff()[seguidas]
            usa = [k for k, v in enumerate(VARIABLES) if (dX[v].abs() > 1e-9).sum() >= MIN_SEMANAS]
            if usa:
                Z = dX.iloc[:, usa].values; coef, *_ = np.linalg.lstsq(Z, dy.values, rcond=None)
                res = dy.values - Z @ coef; s2 = res @ res / max(len(dy) - len(usa), 1)
                b[usa] = coef; V[np.ix_(usa, usa)] = s2 * np.linalg.pinv(Z.T @ Z)
        self.cache[clave] = (b, V)
        return b, V

    def log_factor(self, o, t, tau, rng=None, n=NSIM):
        """log f del día t para Nueva EPS; con rng, n simulaciones con b ~ Normal(b, V). Devuelve (logf, dx)."""
        b, V = self.estimar(o, tau)
        dias = list(pd.date_range(o - pd.Timedelta(days=VENTANA - 1), o)) + [t]
        E = estados(self.R, dias, tau).values
        dx = E[-1] - E[:-1].mean(0)
        if rng is None: return float(dx @ b), dx
        B = rng.multivariate_normal(b, V, size=n, method="eigh") if V.any() else np.tile(b, (n, 1))
        return B @ dx, dx


INGRESOS = pr.RAIZ / "salidas" / "ingresos_entidad.parquet"
SUAVE_A, ESTADO, MIN_DIAS, ABIERTO, SEMANAS_MAX, PREVIO = 10, .7, 7, 1.5, 26, 21     # fila red_de_urgencias_v2


def acceso(archivo=INGRESOS):
    """Ingresos diarios de Nueva EPS y Sura que no vienen de triage (los no urgentes), desde 2024."""
    d = pd.read_parquet(archivo)
    k = pd.read_csv(pr.RAIZ / "salidas/entidades_clasificadas.csv")[["entidad_oid", "grupo"]]
    d = d[d.por_triage == 0].merge(k, on="entidad_oid", how="left")
    p = d[d.grupo.isin([EPS, CONTROL])].pivot_table(index="dia", columns="grupo", values="n", aggfunc="sum")
    p = p.reindex(pd.date_range("2024-01-01", d.dia.max())).fillna(0)
    return p[EPS], p[CONTROL]


class EfectoV2:
    """Fila red_de_urgencias_v2: el estado del convenio SES-Nueva EPS se MIDE con los ingresos no urgentes; el
    registro solo aporta lo anunciado que todavía no se ve en los datos, y los otros hospitales solo cuentan si el SES
    atiende a Nueva EPS. log f = log f_ventana + bA (A(t) - A7(o)) + bE (E(t) - E(o))."""
    nombres = ["acceso", "externos", "ventana"]
    coeficientes = ["acceso", "externos"]

    def __init__(self, R, dias, X, solo_ventana=False):
        self.R, self.solo, self.cache = R, solo_ventana, {}
        ne, su = acceso()
        self.A7 = np.log((ne.rolling(7).sum() + SUAVE_A) / (su.rolling(7).sum() + SUAVE_A))
        lun = ne.index - pd.to_timedelta(ne.index.dayofweek, unit="D")
        n_ = ne.groupby(lun).agg(["sum", "count"]); s_ = su.groupby(lun).sum()
        self.Aw = np.log((n_["sum"] + SUAVE_A) / (s_ + SUAVE_A))[n_["count"] == 7]
        self.abierto_w = self.Aw >= self.Aw.rolling(SEMANAS_MAX, min_periods=1).max() - ABIERTO
        G = pd.DataFrame(X.sum(1), index=pd.DatetimeIndex(dias), columns=ag.GRUPOS)
        self.tri_ne, self.tri_tot = G[EPS], G.sum(1)
        self.y = Efecto(R, dias, X).y                                 # log(Nueva EPS / Sura) del triage, semanal
        self.ses = R[(R.eps == EPS) & (R.prestador == "SES") & R.tipo.isin(VITALES)]

    def abierto(self, o):
        aw = self.Aw[self.Aw.index + pd.Timedelta(days=6) <= o].tail(SEMANAS_MAX)
        return bool(len(aw) == 0 or self.A7.get(o, np.nan) >= aw.max() - ABIERTO)

    def ventana(self, o):
        dias = pd.date_range(o - pd.Timedelta(days=VENTANA - 1), o)
        a = self.A7.reindex(dias); cur = (a - self.A7.get(o, np.nan)).abs() < ESTADO
        tn, tt = self.tri_ne.reindex(dias), self.tri_tot.reindex(dias)
        if cur.sum() < MIN_DIAS or tt.sum() == 0: return 0.
        return float(np.log((tn[cur].sum() / tt[cur].sum()) / (tn.sum() / tt.sum())))

    def _salto(self, o, columna):
        """Dc (columna fecha_inicio) o Dr (fecha_fin): cambio medio de A en los episodios del SES ya ocurridos."""
        out = []
        for f in self.ses[columna].dropna():
            if f > o - pd.Timedelta(days=PREVIO): continue
            lun = f - pd.Timedelta(days=f.dayofweek)
            antes = self.Aw.reindex([lun - pd.Timedelta(weeks=2), lun - pd.Timedelta(weeks=1)])
            despues = self.Aw.reindex([lun + pd.Timedelta(weeks=1), lun + pd.Timedelta(weeks=2)])
            if antes.notna().all() and despues.notna().all(): out.append(despues.mean() - antes.mean())
        return float(np.mean(out)) if out else 0.

    def _externos(self, dias, tau, abiertos):
        return estados(self.R, dias, tau)["externos"].values * np.asarray(abiertos, dtype=float)

    def estimar(self, o, tau):
        clave = (pd.Timestamp(o), pd.Timestamp(tau))
        if clave in self.cache: return self.cache[clave]
        y = self.y[(self.y.index + pd.Timedelta(days=6) <= o) & (self.y.index >= pd.Timestamp("2024-01-08"))]
        y = y[y.index.isin(self.Aw.index)]
        b, V = np.zeros(2), np.zeros((2, 2))
        if len(y) > 10:
            dias = pd.date_range(y.index.min(), y.index.max() + pd.Timedelta(days=6))
            ab = self.abierto_w.reindex(dias - pd.to_timedelta(dias.dayofweek, unit="D")).fillna(True).values
            E = pd.Series(self._externos(dias, tau, ab), index=dias)
            Ew = E.groupby(E.index - pd.to_timedelta(E.index.dayofweek, unit="D")).mean().reindex(y.index)
            Z = pd.DataFrame({"acceso": self.Aw.reindex(y.index), "externos": Ew})
            seguidas = np.r_[False, np.diff(y.index.values).astype("timedelta64[D]").astype(int) == 7]
            dy, dZ = y.diff()[seguidas], Z.diff()[seguidas]
            usa = [0] + ([1] if (dZ.externos.abs() > 1e-9).sum() >= MIN_SEMANAS else [])
            M = dZ.iloc[:, usa].values; coef, *_ = np.linalg.lstsq(M, dy.values, rcond=None)
            res = dy.values - M @ coef; s2 = res @ res / max(len(dy) - len(usa), 1)
            b[usa] = coef; V[np.ix_(usa, usa)] = s2 * np.linalg.pinv(M.T @ M)
        self.cache[clave] = (b, V)
        return b, V

    def log_factor(self, o, t, tau, rng=None, n=NSIM):
        lv = self.ventana(o)
        if self.solo:
            return (np.full(n, lv) if rng is not None else lv), np.array([0., 0., lv])
        A_o = self.A7.get(o, np.nan); ab = self.abierto(o); A_t, ab_t = A_o, ab
        conocidos = self.ses[self.ses.fecha_anuncio <= tau]
        cierre = conocidos[(conocidos.fecha_inicio > o) & (conocidos.fecha_inicio <= t)]
        fin = conocidos[conocidos.fecha_fin.notna() & (conocidos.fecha_anuncio_fin <= tau) & (conocidos.fecha_fin > o)
                        & (conocidos.fecha_fin <= t)]
        ultimo_cierre = cierre.fecha_inicio.max() if len(cierre) else pd.NaT
        ultimo_fin = fin.fecha_fin.max() if len(fin) else pd.NaT
        if ab and pd.notna(ultimo_cierre) and (pd.isna(ultimo_fin) or ultimo_cierre > ultimo_fin):
            A_t, ab_t = A_o + self._salto(o, "fecha_inicio"), False
        elif not ab and pd.notna(ultimo_fin):
            A_t, ab_t = A_o + self._salto(o, "fecha_fin"), True
        e_o, e_t = self._externos([o, t], tau, [ab, ab_t])
        dx = np.array([0. if np.isnan(A_o) else A_t - A_o, e_t - e_o, lv])
        b, V = self.estimar(o, tau)
        if rng is None: return float(lv + dx[:2] @ b), dx
        B = rng.multivariate_normal(b, V, size=n, method="eigh") if V.any() else np.tile(b, (n, 1))
        return lv + B @ dx[:2], dx


def por_hora(dias, X, o, Pj):
    """Proporción de cada grupo dentro de cada hora (24 x grupos), ventana T4, suavizada hacia su jornada."""
    m = (pd.DatetimeIndex(dias) <= o) & (pd.DatetimeIndex(dias) > o - pd.Timedelta(weeks=4))
    C = X[m].sum(0)                                                               # 24 x grupos
    J = np.zeros_like(C)
    for j, (lo, hi) in enumerate(rp.FRANJAS.values()): J[lo:hi + 1] = Pj[j]
    return (C + SUAVE * J) / (C.sum(1, keepdims=True) + SUAVE)


def cadena(q, p24, a24, pg, a_g, Ph, logf, rng, n=NSIM):
    """Total del día -> 24 horas -> grupos por hora, con el factor de red de Nueva EPS por simulación.
    Devuelve (total n, horas n x 24, grupos n x 24 x G)."""
    ne = ag.GRUPOS.index(EPS)
    f = np.exp(np.broadcast_to(logf, (n,)))
    mult = 1 + pg[ne] * (f - 1)
    T0 = np.interp(rng.uniform(pr.QL[0], pr.QL[-1], n), pr.QL, q)
    T = np.round(T0 * mult).astype(int).clip(0)
    Xh = rng.multinomial(T, rng.dirichlet(a24 * p24 + 1e-6, size=n))
    M = rng.dirichlet(a_g * pg + 1e-6, size=n) / np.maximum(pg, 1e-9)              # variación del día por grupo
    M[:, ne] *= f
    W = Ph[None] * M[:, None, :]; W /= W.sum(2, keepdims=True)
    return T, Xh, rng.multinomial(Xh, W)


def resumen_dia(T, Xh, Gh):
    """Cuantiles del total (pr.QL), de cada grupo en el día y en cada jornada, y de cada grupo por hora."""
    f = {c: v for c, v in zip(pr.QCOL, np.quantile(T, pr.QL))}
    Gd = Gh.sum(1)
    for g, gn in enumerate(ag.GRUPOS):
        q10, q50, q90 = np.quantile(Gd[:, g], [.1, .5, .9])
        f |= {f"{gn}_q10": q10, f"{gn}_q50": q50, f"{gn}_q90": q90}
        for jn, (lo, hi) in rp.FRANJAS.items():
            f[f"{gn}_{jn}_q50"] = np.quantile(Gh[:, lo:hi + 1, g].sum(1), .5)
        esp = Gh[:, :, g].mean(0); q10h, q90h = np.quantile(Gh[:, :, g], [.1, .9], axis=0)
        f |= {f"{gn}_h{h:02d}_esp": esp[h] for h in range(24)}
        if gn in ag.GRANDES:
            f |= {f"{gn}_h{h:02d}_q10": q10h[h] for h in range(24)} | {f"{gn}_h{h:02d}_q90": q90h[h] for h in range(24)}
    for jn, (lo, hi) in rp.FRANJAS.items():
        x = Xh[:, lo:hi + 1].sum(1)
        f |= {f"{jn}_q10": np.quantile(x, .1), f"{jn}_q50": np.quantile(x, .5), f"{jn}_q90": np.quantile(x, .9)}
    return f


VARIANTES = {"base": None, "A": "dia_anterior", "B": "origen"}


def evaluar(P, dias, X, R, avisar=print, variantes=None):
    """La validación semanal guardada, sin ajuste y con cada variante (nombre -> None o (efecto, modo de tau)),
    con la misma semilla. Por defecto, la v1: base, A (tau = t - 1) y B (tau = o)."""
    pos = pd.Series(range(len(dias)), index=dias)
    pa, pf = ag.Proporciones(dias, X), rp.Perfiles(rp.horas(), rp.festivos())
    if variantes is None:
        ef = Efecto(R, dias, X); variantes = {v: None if m is None else (ef, m) for v, m in VARIANTES.items()}
    filas = []
    for k, (i, r) in enumerate(P.iterrows()):
        o, t = r.origen, r.fecha
        p24, a24 = pf.perfil("P52", o, t); pg, a_g = pa.dia("T4", o, t); Ph = por_hora(dias, X, o, pa.jornada("T4", o, t))
        real = X[pos[t]]; q = r[pr.QCOL].values.astype(float)
        for v, spec in variantes.items():
            rng = np.random.default_rng(k)                       # misma semilla para todas las variantes
            if spec is None: lf, extra = np.zeros(NSIM), {}
            else:
                ef, modo = spec
                tau = t - pd.Timedelta(days=1) if modo == "dia_anterior" else o
                lf, dx = ef.log_factor(o, t, tau, rng); b = ef.estimar(o, tau)[0]
                extra = {**{f"dx_{n}": x for n, x in zip(ef.nombres, dx)}, **{f"b_{n}": x for n, x in zip(ef.coeficientes, b)}}
            T, Xh, Gh = cadena(q, p24, a24, pg, a_g, Ph, lf, rng)
            fila = {"i": i, "variante": v, "log_f": float(np.median(lf)), **extra, **resumen_dia(T, Xh, Gh)}
            for g, gn in enumerate(ag.GRUPOS): fila[f"{gn}_real"] = real[:, g].sum()
            for gn in ag.GRANDES:
                g = ag.GRUPOS.index(gn); rh = real[:, g]
                lo_, hi_ = np.quantile(Gh[:, :, g], [.1, .9], axis=0)
                fila |= {f"{gn}_hora_ae": np.abs(np.median(Gh[:, :, g], 0) - rh).mean(),
                         f"{gn}_hora_en_rango": ((rh >= lo_) & (rh <= hi_)).mean(),
                         f"{gn}_hora_piso": np.abs(rng.poisson(np.maximum(rh, .5), size=(NSIM // 4, 24)) - rh).mean()}
            filas.append(fila)
        if k % 200 == 0: avisar(f"  {k}/{len(P)}")
    E = pd.DataFrame(filas)
    return E.merge(P[["fecha", "origen", "adelanto", "combo", "anio", "real"]], left_on="i", right_index=True)


def pinball(Q, real):
    return np.mean([np.maximum(tq * (real - Q[:, j]), (tq - 1) * (real - Q[:, j])) for j, tq in enumerate(pr.QL)], 0) / real


def resumir(E, ref="A"):
    filas = []
    for (v, lead, anio), G in E.groupby(["variante", "adelanto", "anio"]):
        for solo, g in (("todos", G), ("con ajuste", G[G.i.isin(E[(E.variante == ref) & (E.log_f.abs() > 1e-6)].i)])):
            if g.empty: continue
            Q = np.sort(g[pr.QCOL].values, 1); dentro = g.real.between(g.q10, g.q90)
            fila = {"variante": v, "adelanto": lead, "año": anio, "días": solo, "n": len(g),
                    "error del día %": 100 * np.mean(np.abs(g.q50 - g.real) / g.real),
                    "puntaje cuantiles %": 100 * pinball(Q, g.real.values).mean(),
                    "total en rango 80 %": 100 * dentro.mean(), "Kupiec p": rp.kupiec(dentro.values)}
            for gn in ag.GRANDES:
                r_ = g[f"{gn}_real"]
                fila |= {f"{ag.NOMBRES[gn]}: error %": 100 * np.mean(np.abs(g[f"{gn}_q50"] - r_) / r_.clip(lower=1)),
                         f"{ag.NOMBRES[gn]}: en rango 80 %": 100 * r_.between(g[f"{gn}_q10"], g[f"{gn}_q90"]).mean(),
                         f"{ag.NOMBRES[gn]}: hora, error medio": g[f"{gn}_hora_ae"].mean(),
                         f"{ag.NOMBRES[gn]}: hora, piso": g[f"{gn}_hora_piso"].mean(),
                         f"{ag.NOMBRES[gn]}: hora en rango 80 %": 100 * g[f"{gn}_hora_en_rango"].mean()}
            filas.append(fila)
    return pd.DataFrame(filas).set_index(["variante", "adelanto", "año", "días"])


def regla(T, v="A"):
    """Filas red_de_urgencias y _v2: la variante v, adelanto 15, puntaje del total mejora en 2026, no empeora más de 1 %
    en 2025 y cobertura del total >= 70 % en los dos años."""
    s = lambda v_, a, c: T.loc[(v_, 15, a, "todos"), c]
    mejora26 = s(v, 2026, "puntaje cuantiles %") < s("base", 2026, "puntaje cuantiles %")
    ok25 = s(v, 2025, "puntaje cuantiles %") <= 1.01 * s("base", 2025, "puntaje cuantiles %")
    cob = min(s(v, 2025, "total en rango 80 %"), s(v, 2026, "total en rango 80 %")) >= 70
    return bool(mejora26 and ok25 and cob), {"mejora en 2026": mejora26, "no empeora 2025": ok25, "cobertura >= 70": cob}


if __name__ == "__main__":
    import argparse
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser(); ap.add_argument("--v2", action="store_true", help="fila red_de_urgencias_v2")
    a = ap.parse_args()
    CARPETA.mkdir(parents=True, exist_ok=True)
    dias, X = ag.conteos_grupo(); R = registro()
    P = pd.read_parquet(rp.SEMANAL).dropna(subset=["real"])
    P = P[(P.combo == "C0r") & P.fecha.isin(dias) & P.fecha.isin(rp.horas().index)].copy()
    P["anio"] = np.where(P.origen < rp.CORTE_2026, 2025, 2026)
    print(f"{len(R)} episodios en el registro; {len(P)} días predichos (C0r, adelantos {sorted(P.adelanto.unique())})")
    pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
    if a.v2:
        e2, eD = EfectoV2(R, dias, X), EfectoV2(R, dias, X, solo_ventana=True)
        E = evaluar(P, dias, X, R, variantes={"base": None, "v2A": (e2, "dia_anterior"), "v2B": (e2, "origen"),
                                               "v2D": (eD, "origen")})
        E.to_parquet(CARPETA / "conteos_v2.parquet")
        T = resumir(E, ref="v2A"); T.to_csv(CARPETA / "resumen_v2.csv")
        r = {v: regla(T, v) for v in ("v2A", "v2B", "v2D")}
        (CARPETA / "regla_v2.txt").write_text("\n".join(f"{v}: {'ENTRA' if e else 'NO ENTRA'} {m}" for v, (e, m) in r.items()),
                                              encoding="utf-8")
        print(T.round(2).T.to_string())
        for v, (e, m) in r.items(): print(f"Regla {v}: {'ENTRA' if e else 'NO ENTRA'} {m}")
        raise SystemExit
    E = evaluar(P, dias, X, R)
    E.to_parquet(CARPETA / "conteos.parquet")
    T = resumir(E); T.to_csv(CARPETA / "resumen.csv")
    entra, motivos = regla(T)
    (CARPETA / "regla.txt").write_text(f"{'ENTRA' if entra else 'NO ENTRA'}\n{motivos}\n", encoding="utf-8")
    print(T.round(2).T.to_string()); print(f"\nRegla: {'ENTRA' if entra else 'NO ENTRA'} {motivos}")
