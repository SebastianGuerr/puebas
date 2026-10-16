"""
La operación semanal rehecha sobre 2026 (fila validacion_2026_operacion_semanal de patrones/datos/variables.csv):
¿M3s, que reentrena cada semana con el contexto externo, mejora, se mantiene o empeora frente a C0r?

    python notebooks/validacion_2026.py --reproducir      M3s y C0r contra la corrida guardada del 2026-10-14
    python notebooks/validacion_2026.py --medir           tiempo de un origen (adelanto 1-7, todos los modelos)
    python notebooks/validacion_2026.py --correr          todos los orígenes; reanuda lo que falte
    python notebooks/validacion_2026.py --resumir         tablas, regla y Diebold-Mariano

Guarda un archivo por (bloque de adelanto, origen) en salidas/pronostico/validacion_2026/origenes/: una interrupción
no pierde lo hecho. El porqué de cada elección está en la fila del preregistro y en docs/CONTEXTO.md.
"""
import argparse
import json
import sys
import time
import warnings
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "notebooks")); sys.path.insert(0, str(RAIZ))

import pronostico as pr          # noqa: E402
import semana as sm              # noqa: E402
import indices as ix             # noqa: E402
import mecanismos as mc          # noqa: E402
import madurez as md             # noqa: E402
import red as rd                 # noqa: E402
import resiliencia as rs         # noqa: E402
import aseguradoras as ag        # noqa: E402

FIN = "2026-10-14"                                   # operacion.ultimo_dia_completo() al preregistrar
FOTO = RAIZ / "calendarios/vigilancia/powerbi/2026-10-15"     # la última foto del Power BI al preregistrar
PRIMER_ORIGEN = "2026-01-04"
CARPETA = pr.SALIDA / "validacion_2026"
ORIGENES = CARPETA / "origenes"
REGISTRO = CARPETA / "progreso.log"
COMBOS = ["C0r", "M3s", "M3cal"]
REFIT = {(1, "C0r"): 1, (1, "M3s"): 1, (1, "M3cal"): 1, (15, "C0r"): 4, (15, "M3s"): 4, (15, "M3cal"): 4}
VINT = True                                          # sensibilidad de vintage: M3s con la salud una semana más tarde
NSIM = 4000
VENTANA_ASEG = "T4"                                  # la de operacion
RHO = {("C0r", 1): .337, ("C0r", 15): .487, ("M3s", 1): .318, ("M3s", 15): .473}      # operacion.RHO
SISMO = pd.Timestamp("2026-08-10")

_FO = ix.familias_operativas


def _avisar(s):
    linea = f"{datetime.now():%Y-%m-%d %H:%M:%S} {s}"
    print(linea, flush=True)
    CARPETA.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as f: f.write(linea + "\n")


def preparar():
    """Fija el fin de los datos, la red puntual y la foto del Power BI (la tarea diaria no la cambia a mitad)."""
    warnings.filterwarnings("ignore")
    pr.FIN = FIN; pr.H = 21; ix.FIN_RED = FIN
    ix.familias_operativas = lambda foto=None: _FO(foto or FOTO)
    y, cal, F = sm.datos()
    return y, cal


@contextmanager
def salud_retrasada(semanas=1):
    """Vintage: cada día ve la semana epidemiológica completa anterior a la que vería el modelo (la publicada en el
    origen), en el entrenamiento y en la predicción."""
    previo = ix.familias_operativas
    def f(foto=None):
        S = _FO(foto or FOTO); S.index = S.index + pd.Timedelta(weeks=semanas); return S
    ix.familias_operativas = f
    try: yield
    finally: ix.familias_operativas = previo


def origenes(lead):
    fin = pd.Timestamp(FIN)
    return [o for o in pd.date_range(PRIMER_ORIGEN, fin, freq="W-SUN") if o + pd.Timedelta(days=lead + 6) <= fin]


def de_cero(aj):
    """Como la operación: cada reentreno arranca SARIMAX de cero, no del ajuste anterior."""
    for M in aj.M.values():
        if hasattr(M, "params"): del M.params


def predecir(aj, o, hs, nombres):
    """Cuantiles por día de la combinación (promedio de cuantiles, ordenados), como semana.Ajuste.predecir."""
    Q = []
    for n in nombres:
        M = aj[n] if isinstance(aj, dict) else aj.M[n]
        if isinstance(M, pr._Directo): Q.append(np.vstack([M.predecir_h(M.m[h], M.fila(h, o)) for h in hs]))
        else: Q.append(M.predecir(o, n=max(hs))[[h - 1 for h in hs]])
    return np.sort(np.mean(Q, axis=0), axis=1)


class Entrega:
    """Versión (b): la red v2 con lo conocido en el origen (tau = o) sobre el total y el rango W tras un quiebre, con
    la misma cadena que rd.cadena para el total (las horas y las aseguradoras no cambian el total)."""
    def __init__(self):
        dias_g, X_g = ag.conteos_grupo()
        self.pa = ag.Proporciones(dias_g, X_g)
        self.ef = rd.EfectoV2(rd.registro(), dias_g, X_g)
        self.qb = rs.Quiebre(dias_g, X_g)
        self.ne = ag.GRUPOS.index(rd.EPS)

    def aplicar(self, o, fechas, Q, semilla):
        rng = np.random.default_rng(semilla); out = Q.copy(); fr = []
        for k, t in enumerate(fechas):
            lf = self.ef.log_factor(o, t, o, rng)[0]
            if np.any(lf):
                pg = self.pa.dia(VENTANA_ASEG, o, t)[0]
                mult = 1 + pg[self.ne] * (np.exp(lf) - 1)
                T0 = np.interp(rng.uniform(pr.QL[0], pr.QL[-1], NSIM), pr.QL, Q[k])
                out[k] = np.quantile(np.round(T0 * mult).astype(int).clip(0), pr.QL)
            fr.append(float(np.exp(np.median(lf))))
        quiebre = bool(self.qb.total(o))
        if quiebre:                                          # resiliencia.ensanchar: q' = q50 (q / q50)^1,5
            med = out[:, [4]]; out = med * (np.maximum(out, 1e-6) / med) ** rs.K_RANGO
        return np.sort(out, axis=1), np.array(fr), quiebre


def filas(o, lead, combo, version, Q, y, normal, extra=None):
    hs = list(range(lead, lead + 7)); fechas = pd.date_range(o + pd.Timedelta(days=lead), periods=7)
    V = md.vara(y, [o] * 7, fechas)
    rho = RHO[("C0r" if combo == "C0r" else "M3s", lead)]
    m = sm.semana_agregada(Q, rho)
    D = pd.DataFrame({"origen": o, "bloque": lead, "combo": combo, "version": version, "fecha": fechas, "h": hs,
                      **{c: Q[:, j] for j, c in enumerate(pr.QCOL)}, "real": y.reindex(fechas).values, "vara": V,
                      "p_sube": pr.prob_sobre(Q, V), "control": normal[:, 0],
                      "sem_q10": np.quantile(m, .1), "sem_q50": np.quantile(m, .5), "sem_q90": np.quantile(m, .9)})
    for k, v in (extra or {}).items(): D[k] = v
    return D


def construir(y, cal, lead):
    """Los Ajustes del bloque: uno por frecuencia de reentreno, más el de vintage (solo 1-7)."""
    grupos = {}
    for c in COMBOS: grupos.setdefault(REFIT[(lead, c)], []).append(c)
    A = {r: (sm.Ajuste(y, cal, sorted({m for c in cs for m in sm.COMBOS[c]})), cs) for r, cs in grupos.items()}
    vint = None
    if VINT and lead == 1:
        with salud_retrasada(): vint = sm.Ajuste(y, cal, ["lightgbm_rel_mec@m3s"])
    return A, vint


def correr(solo=None, limite=None):
    y, cal = preparar(); ORIGENES.mkdir(parents=True, exist_ok=True)
    _avisar(f"Inicio. FIN={FIN}, foto={FOTO.name}, REFIT={REFIT}, VINT={VINT}")
    ent = Entrega()
    for lead in (solo or (1, 15)):
        ors = origenes(lead); hs = list(range(lead, lead + 7))
        pend = [o for o in ors if not (ORIGENES / f"{lead:02d}_{o.date()}.parquet").exists()]
        if not pend: _avisar(f"bloque {lead}: completo ({len(ors)} orígenes)"); continue
        t0 = time.time(); A, vint = construir(y, cal, lead)
        _avisar(f"bloque {lead}: {len(pend)} de {len(ors)} orígenes pendientes; modelos construidos en {time.time() - t0:.0f} s")
        ajustado = {r: None for r in A}; ajustado_v = None
        for n_hecho, o in enumerate(pend):
            if limite is not None and n_hecho >= limite: break
            t1 = time.time(); i = ors.index(o); partes = []
            for r, (aj, cs) in A.items():
                ro = ors[i - i % r]                              # el origen del último reentreno de este grupo
                if ajustado[r] != ro:
                    de_cero(aj); aj.ajustar(ro, hs); ajustado[r] = ro
                for c in cs:
                    Q = predecir(aj, o, hs, sm.COMBOS[c])
                    normal = np.array([[float(aj.M["control"].predecir_h(aj.M["control"].m[h], aj.M["control"].fila(h, o))[4]),
                                        aj.M["control"].m[h][2]] for h in hs])
                    semilla = int(o.strftime("%Y%m%d")) * 100 + lead
                    Qb, fr, qb = ent.aplicar(o, pd.date_range(o + pd.Timedelta(days=lead), periods=7), Q, semilla)
                    ex = {"f_red": fr, "quiebre": qb, "reentreno": ro}
                    partes += [filas(o, lead, c, "a", Q, y, normal, ex), filas(o, lead, c, "b", Qb, y, normal, ex)]
                    if c == "M3s" and vint is not None:
                        if ajustado_v != o:
                            de_cero(vint); vint.ajustar(o, hs); ajustado_v = o
                        Qv = predecir({"sarimax_mec@m3s": aj.M["sarimax_mec@m3s"], "lightgbm_rel_mec@m3s": vint.M["lightgbm_rel_mec@m3s"]},
                                      o, hs, ["sarimax_mec@m3s", "lightgbm_rel_mec@m3s"])
                        Qvb, frv, qbv = ent.aplicar(o, pd.date_range(o + pd.Timedelta(days=lead), periods=7), Qv, semilla)
                        exv = {"f_red": frv, "quiebre": qbv, "reentreno": o}
                        partes += [filas(o, lead, "M3s_vint", "a", Qv, y, normal, exv), filas(o, lead, "M3s_vint", "b", Qvb, y, normal, exv)]
            P = pd.concat(partes, ignore_index=True); P["segundos"] = time.time() - t1
            f = ORIGENES / f"{lead:02d}_{o.date()}.parquet"; P.to_parquet(f.with_suffix(".tmp"), index=False)
            f.with_suffix(".tmp").replace(f)
            _avisar(f"bloque {lead}: origen {o.date()} ({i + 1}/{len(ors)}) en {time.time() - t1:.0f} s")
    _avisar("FIN")


def reproducir():
    """M3s y C0r con el código de la validación, en el origen de la corrida guardada (2026-10-14), contra q*_sin_red."""
    y, cal = preparar(); o = pd.Timestamp("2026-10-14"); hs = list(range(1, 22))
    aj = sm.Ajuste(y, cal, sorted({m for c in COMBOS for m in sm.COMBOS[c]})); de_cero(aj); aj.ajustar(o, hs)
    out = {}
    for c in ("C0r", "M3s"):
        D = pd.read_parquet(RAIZ / f"salidas/operacion/corridas/2026-10-14_{c}/dias.parquet")
        G = D[D.adelanto.between(1, 21)].sort_values("adelanto")[[f"{q}_sin_red" for q in pr.QCOL]].values
        Q = predecir(aj, o, hs, sm.COMBOS[c])
        out[c] = {"dif_max": float(np.abs(Q - G).max()), "dif_rel_max": float(np.abs(Q / G - 1).max()), "dias": len(G)}
    return out


# ------------------------------------------------------------------ resumen
def leer():
    P = pd.concat([pd.read_parquet(f) for f in sorted(ORIGENES.glob("*.parquet"))], ignore_index=True)
    P = P.dropna(subset=["real"]).copy()
    P["ape"] = 100 * (P.q50 - P.real).abs() / P.real; P["ae"] = (P.q50 - P.real).abs()
    P["sesgo"] = 100 * (P.q50 - P.real) / P.real; P["en_rango"] = P.real.between(P.q10, P.q90)
    P["acierta"] = (P.p_sube > .5) == (P.real > P.vara)
    return P


def metricas(G):
    W = G.groupby("origen").agg(real=("real", "mean"), q10=("sem_q10", "first"), q50=("sem_q50", "first"),
                                q90=("sem_q90", "first"), n=("real", "size"))
    W = W[W.n == 7]
    return pd.Series({"días": len(G), "MAPE %": G.ape.mean(), "mediana APE %": G.ape.median(),
                      "en rango 80 %": 100 * G.en_rango.mean(), "sesgo %": G.sesgo.mean(),
                      "error media semanal %": 100 * ((W.q50 - W.real).abs() / W.real).mean(),
                      "semana en rango 80 %": 100 * W.real.between(W.q10, W.q90).mean(),
                      "acierto sube/baja %": 100 * G.acierta.mean(), "semanas": len(W)})


def dm(d, h):
    """Diebold-Mariano con la corrección de Harvey-Leybourne-Newbold. d: diferencias de pérdida ordenadas por fecha."""
    from scipy.stats import t as tdist
    d = np.asarray(d, float); n = len(d); m = d.mean(); e = d - m
    g = [e @ e / n] + [e[k:] @ e[:-k] / n for k in range(1, h)]
    v = g[0] + 2 * sum(g[1:])
    vb = g[0] + 2 * sum((1 - k / h) * g[k] for k in range(1, h))                 # Bartlett (robustez)
    if v <= 0: v = vb
    c = np.sqrt((n + 1 - 2 * h + h * (h - 1) / n) / n)
    s, sb = m / np.sqrt(v / n) * c, m / np.sqrt(vb / n) * c
    return float(m), float(s), float(2 * tdist.sf(abs(s), n - 1)), n, float(2 * tdist.sf(abs(sb), n - 1))


def estados(fechas_origen):
    """Estado del día (calendario en t; compuertas en el origen; sismo) para cada par (origen, fecha)."""
    dias = pd.date_range("2025-12-01", pd.Timestamp(FIN) + pd.Timedelta(days=21))
    FUT, PAS, G = mc.columnas(dias)
    cal = (FUT[["fut_m_feria_d0_4", "fut_m_fiesta_lejana", "fut_m_noche_festiva", "fut_m_dia_siguiente"]].fillna(0) > 0)
    o, t = fechas_origen.origen, fechas_origen.fecha
    E = pd.DataFrame({"calendario": cal.any(axis=1).reindex(t).values,
                      "fiesta_lejana": cal.fut_m_fiesta_lejana.reindex(t).values,
                      "feria_noches": cal[["fut_m_feria_d0_4", "fut_m_noche_festiva", "fut_m_dia_siguiente"]].any(axis=1).reindex(t).values,
                      "salud": G.salud.reindex(o).values.astype(bool), "red": G.red.reindex(o).values.astype(bool),
                      "social": G.social.reindex(o).values.astype(bool),
                      "sismo": ((t - SISMO).dt.days.between(0, 21)).values}, index=fechas_origen.index)
    exc = np.select([E.sismo, E.calendario, E.red, E.salud, E.social], ["sismo", "calendario", "red", "salud", "social"], "normal")
    E["exclusivo"] = exc
    return E


def resumir():
    y, cal = preparar(); P = leer()
    P["mes"] = P.fecha.dt.month
    T = P.groupby(["combo", "version", "bloque"]).apply(metricas)
    M = P[P.version == "b"].groupby(["bloque", "mes", "combo"]).apply(metricas)[["MAPE %", "en rango 80 %", "sesgo %", "acierto sube/baja %", "días"]]
    # regla
    def x(c, v, b, k): return T.loc[(c, v, b), k]
    regla = {}
    for b in sorted(P.bloque.unique()):
        b = int(b)
        dmape = x("M3s", "b", b, "MAPE %") - x("C0r", "b", b, "MAPE %")
        dcob = x("M3s", "b", b, "en rango 80 %") - x("C0r", "b", b, "en rango 80 %")
        v = ("empeora" if dmape > .5 or dcob < -5 else "mejora" if dmape < -.5 and dcob >= 0 else "se mantiene")
        regla[b] = {"dif MAPE": dmape, "dif cobertura": dcob, "veredicto": v}
    # Diebold-Mariano
    DM = []
    for b, h in ((1, 7), (15, 21)):
        for v in ("a", "b"):
            S = P[(P.bloque == b) & (P.version == v)]
            for a_, b_ in (("M3s", "C0r"), ("M3cal", "C0r"), ("M3s", "M3cal"), ("M3s_vint", "C0r"), ("M3s_vint", "M3s")):
                if not {a_, b_} <= set(S.combo): continue
                for perd in ("ape", "ae"):
                    W = S.pivot_table(index="fecha", columns="combo", values=perd)[[a_, b_]].dropna().sort_index()
                    m, s, p, n, pb = dm(W[a_] - W[b_], h)
                    DM.append({"bloque": b, "version": v, "par": f"{a_} - {b_}", "pérdida": perd, "dif media": m, "DM (HLN)": s, "p": p,
                               "p Bartlett": pb, "n": n})
    DM = pd.DataFrame(DM)
    # culpable
    B = P[(P.version == "b") & P.combo.isin(["M3s", "C0r", "M3cal"])].pivot_table(index=["bloque", "origen", "fecha"], columns="combo", values="ape").reset_index()
    E = estados(B[["origen", "fecha"]]); B = B.join(E)
    B["d"] = B.M3s - B.C0r; B["d_cal"] = B.M3cal - B.C0r
    filas_ = []
    for b, Gb in B.groupby("bloque"):
        N = len(Gb)
        for k in ["calendario", "fiesta_lejana", "feria_noches", "salud", "red", "social", "sismo"]:
            g = Gb[Gb[k]]
            filas_.append({"bloque": b, "estado": k, "tipo": "con solapes", "días": len(g), "MAPE M3s": g.M3s.mean(), "MAPE C0r": g.C0r.mean(),
                           "MAPE M3cal": g.M3cal.mean(), "dif M3s-C0r": g.d.mean(), "contribución (puntos)": g.d.sum() / N,
                           "contribución M3cal-C0r": g.d_cal.sum() / N})
        for k, g in Gb.groupby("exclusivo"):
            filas_.append({"bloque": b, "estado": k, "tipo": "exclusivo", "días": len(g), "MAPE M3s": g.M3s.mean(), "MAPE C0r": g.C0r.mean(),
                           "MAPE M3cal": g.M3cal.mean(), "dif M3s-C0r": g.d.mean(), "contribución (puntos)": g.d.sum() / N,
                           "contribución M3cal-C0r": g.d_cal.sum() / N})
        filas_.append({"bloque": b, "estado": "TOTAL", "tipo": "exclusivo", "días": N, "MAPE M3s": Gb.M3s.mean(), "MAPE C0r": Gb.C0r.mean(),
                       "MAPE M3cal": Gb.M3cal.mean(), "dif M3s-C0r": Gb.d.mean(), "contribución (puntos)": Gb.d.mean(),
                       "contribución M3cal-C0r": Gb.d_cal.mean()})
    C = pd.DataFrame(filas_)
    T.to_csv(CARPETA / "tabla_principal.csv"); M.to_csv(CARPETA / "por_mes.csv"); DM.to_csv(CARPETA / "diebold_mariano.csv", index=False)
    C.to_csv(CARPETA / "por_estado.csv", index=False); B.to_parquet(CARPETA / "dias_estado.parquet", index=False)
    (CARPETA / "regla.json").write_text(json.dumps(regla, ensure_ascii=False, indent=1), encoding="utf-8")
    return T, M, DM, C, regla


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproducir", action="store_true"); ap.add_argument("--medir", action="store_true")
    ap.add_argument("--correr", action="store_true"); ap.add_argument("--resumir", action="store_true")
    ap.add_argument("--bloque", type=int, nargs="*"); ap.add_argument("--limite", type=int)
    a = ap.parse_args()
    if a.reproducir:
        r = reproducir(); _avisar(f"reproducción 2026-10-14: {r}")
    if a.medir:
        correr(solo=(1,), limite=1)
    if a.correr:
        correr(solo=a.bloque)
    if a.resumir:
        pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40)
        T, M, DM, C, regla = resumir()
        for k, v in (("principal", T), ("mes", M), ("DM", DM), ("estado", C)): print(f"\n== {k}\n{v.round(2).to_string()}")
        print(regla)
