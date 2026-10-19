"""
La catastrofe por fecha del evento (fila m3s_catastrofe_por_fecha de patrones/datos/variables.csv): prueba AISLADA,
no toca la operacion.
    M3s-cf  M3s con las dos columnas de catastrofe contadas desde el dia predicho (dias desde el terremoto, sabido en
            el origen), no como estado congelado del origen

Mismo diseno que validacion_anual.py (FIN, foto del Power BI, SARIMAX desde cero en cada reentreno, versiones a y b,
mismos origenes y reentrenos). Solo calcula M3s-cf: C0r y M3s se leen tal cual, 2025 de
salidas/pronostico/correcciones_red_salud/origenes/ y 2026 de salidas/pronostico/validacion_2026/origenes/.

    python notebooks/validacion_catastrofe.py --reproducir            M3s y C0r contra las corridas 2026-10-14_*
    python notebooks/validacion_catastrofe.py --inyeccion             terremoto ficticio con los modelos ya entrenados
    python notebooks/validacion_catastrofe.py --correr --anio 2026 2025   todos los origenes; reanuda lo que falte
    python notebooks/validacion_catastrofe.py --resumir               identidad, tablas, regla, tramo del sismo, DM

Guarda un archivo por (anio, bloque, origen) en salidas/pronostico/catastrofe_por_fecha/origenes/. El porque esta en
la fila del preregistro y en docs/CONTEXTO.md, entrada «2026-10-16 (catástrofe)».
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "notebooks")); sys.path.insert(0, str(RAIZ))

import validacion_2026 as v      # noqa: E402
import validacion_anual as va    # noqa: E402
from validacion_2026 import pr, sm, mc   # noqa: E402

CARPETA = pr.SALIDA / "catastrofe_por_fecha"
ORIGENES = CARPETA / "origenes"
REGISTRO = CARPETA / "progreso.log"
NUEVO = "M3s-cf"
REFIT = {1: 1, 15: 4}
TRAMO = ("2026-08-10", "2026-09-20")          # origenes del tramo del sismo (preregistrado)
MEJORA_MAPE, MEJORA_COB = va.MEJORA_MAPE, va.MEJORA_COB
EMPEORA_MAPE, EMPEORA_COB = va.EMPEORA_MAPE, va.EMPEORA_COB
QS = list(pr.QCOL)


def _avisar(s):
    linea = f"{pd.Timestamp.now():%Y-%m-%d %H:%M:%S} {s}"
    print(linea, flush=True)
    CARPETA.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as f: f.write(linea + "\n")


def archivo(anio, lead, o):
    return ORIGENES / f"{anio}_{lead:02d}_{o.date()}.parquet"


def correr(anio, solo=None, limite=None):
    y, cal = v.preparar(); ORIGENES.mkdir(parents=True, exist_ok=True)
    ent = v.Entrega()
    _avisar(f"Inicio {anio}. FIN={v.FIN}, foto={v.FOTO.name}, combo={NUEVO}, REFIT={REFIT}")
    for lead in (solo or (1, 15)):
        ors = va.origenes(anio, lead); hs = list(range(lead, lead + 7)); r = REFIT[lead]
        pend = [o for o in ors if not archivo(anio, lead, o).exists()]
        if not pend: _avisar(f"{anio} bloque {lead}: completo ({len(ors)} orígenes)"); continue
        t0 = time.time()
        aj = sm.Ajuste(y, cal, sm.COMBOS[NUEVO])
        _avisar(f"{anio} bloque {lead}: {len(pend)} de {len(ors)} orígenes pendientes; modelos {sorted(aj.M)} construidos en {time.time() - t0:.0f} s")
        ajustado = None
        for n_hecho, o in enumerate(pend):
            if limite is not None and n_hecho >= limite: break
            t1 = time.time(); i = ors.index(o); ro = ors[i - i % r]
            if ajustado != ro:
                v.de_cero(aj); aj.ajustar(ro, hs); ajustado = ro
            C = aj.M["control"]
            normal = np.array([[float(C.predecir_h(C.m[h], C.fila(h, o))[4]), C.m[h][2]] for h in hs])
            fechas = pd.date_range(o + pd.Timedelta(days=lead), periods=7)
            semilla = int(o.strftime("%Y%m%d")) * 100 + lead
            Q = v.predecir(aj, o, hs, sm.COMBOS[NUEVO])
            Qb, fr, qb = ent.aplicar(o, fechas, Q, semilla)
            ex = {"f_red": fr, "quiebre": qb, "reentreno": ro, "anio": anio}
            P = pd.concat([v.filas(o, lead, NUEVO, "a", Q, y, normal, ex), v.filas(o, lead, NUEVO, "b", Qb, y, normal, ex)],
                          ignore_index=True)
            P["segundos"] = time.time() - t1
            f = archivo(anio, lead, o); P.to_parquet(f.with_suffix(".tmp"), index=False); f.with_suffix(".tmp").replace(f)
            _avisar(f"{anio} bloque {lead}: origen {o.date()} ({i + 1}/{len(ors)}, reentreno {ro.date()}) en {time.time() - t1:.0f} s")
    _avisar(f"FIN {anio}")


# ------------------------------------------------------------------ comprobaciones antes de lanzar
def inyeccion():
    """Modelos entrenados una vez en el origen 2026-10-14; despues se anade un terremoto ficticio y se rehacen solo las
    entradas de la prediccion (la historia y los parametros no cambian). M3s-cf solo puede mover los dias con t - c
    en 0-20; M3s congela el estado del origen. Delta % del q50 frente a la base, por adelanto 1-21."""
    y, cal = v.preparar(); o = pd.Timestamp("2026-10-14"); hs = list(range(1, 22))
    nombres = sorted({m for c in ("M3s", NUEVO) for m in sm.COMBOS[c]})
    aj = sm.Ajuste(y, cal, nombres); v.de_cero(aj); aj.ajustar(o, hs)
    base = {c: v.predecir(aj, o, hs, sm.COMBOS[c]) for c in ("M3s", NUEVO)}
    cs = list(mc.CATASTROFE_VENTANAS)
    original = mc.catastrofes
    guard = {n: ({h: X.copy() for h, X in M.X.items()} if isinstance(M, pr._Directo) else M.PAS.copy()) for n, M in aj.M.items() if "@" in n}
    out = {}
    for esc, falso in (("control sin cambio", None), ("terremoto la víspera (c = o - 1)", o - pd.Timedelta(days=1)),
                       ("terremoto 5 días antes (c = o - 5)", o - pd.Timedelta(days=5))):
        mc.catastrofes = (lambda f=falso: sorted(set(original()) | ({f} if f is not None else set())))
        try:
            for n, M in aj.M.items():
                if "@" not in n: continue
                if isinstance(M, pr._Directo):
                    M.X = {h: X.copy() for h, X in guard[n].items()}
                    for h in hs:
                        t = o + pd.Timedelta(days=h)
                        if n.endswith("@m3s_cf"): val = mc.catastrofe_por_fecha([t], [o])
                        else: val = mc.catastrofe_por_fecha([o], [o])      # M3s: el estado del origen, desplazado
                        M.X[h].loc[t, cs] = val[cs].values[0]
                else:
                    M.PAS = guard[n].copy()
                    if not n.endswith("@m3s_cf"):                          # M3s: congelado en el origen
                        M.PAS.loc[o, [c for c in cs if c in M.PAS]] = mc.catastrofe_por_fecha([o], [o])[[c for c in cs if c in M.PAS]].values[0]
            for c in ("M3s", NUEVO):
                Q = v.predecir(aj, o, hs, sm.COMBOS[c])
                d = 100 * (Q[:, 4] / base[c][:, 4] - 1)
                dd = None if falso is None else [(o + pd.Timedelta(days=h) - falso).days for h in hs]
                out[f"{esc} | {c}"] = {"delta_q50_%": [round(float(x), 3) for x in d], "dias_desde_evento": dd,
                                       "max_abs_desde_dia_21": (None if falso is None else
                                                                float(np.abs(Q - base[c])[[k for k, x in enumerate(dd) if x >= 21]].max()) if any(x >= 21 for x in dd) else None),
                                       "max_abs_total": float(np.abs(Q - base[c]).max())}
        finally:
            mc.catastrofes = original
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / "inyeccion.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


# ------------------------------------------------------------------ resumen
def _medidas(P):
    P = P.dropna(subset=["real"]).copy()
    P["ape"] = 100 * (P.q50 - P.real).abs() / P.real; P["ae"] = (P.q50 - P.real).abs()
    P["sesgo"] = 100 * (P.q50 - P.real) / P.real; P["en_rango"] = P.real.between(P.q10, P.q90)
    P["acierta"] = (P.p_sube > .5) == (P.real > P.vara)
    return P


def leer(con_nan=False):
    N = pd.concat([pd.read_parquet(f) for f in sorted(ORIGENES.glob("*.parquet"))], ignore_index=True)
    A = pd.concat([pd.read_parquet(f) for f in sorted(va.ORIGENES.glob("2025_*.parquet"))], ignore_index=True)
    A = A[A.combo.isin(["C0r", "M3s"])]
    B = pd.concat([pd.read_parquet(f) for f in sorted(v.ORIGENES.glob("*.parquet"))], ignore_index=True)
    B = B[B.combo.isin(["C0r", "M3s"])].assign(anio=2026)
    P = pd.concat([N, A, B], ignore_index=True)
    return P if con_nan else _medidas(P)


def identidad(P):
    """M3s-cf frente a M3s, mismo (anio, bloque, version, origen, fecha): diferencia maxima de los cuantiles."""
    k = ["anio", "bloque", "version", "origen", "fecha"]
    X = P[P.combo == NUEVO].set_index(k)[QS]; Y = P[P.combo == "M3s"].set_index(k)[QS]
    j = X.index.intersection(Y.index)
    D = (X.loc[j] - Y.loc[j]).abs().max(axis=1).rename("dif").reset_index()
    D["antes_del_sismo"] = D.origen < v.SISMO
    R = D.groupby(["anio", "bloque", "version", "antes_del_sismo"]).agg(filas=("dif", "size"), dif_max=("dif", "max"),
                                                                       origenes_con_dif=("origen", lambda s: s[D.loc[s.index, "dif"] > 0].nunique()))
    return R, D


def resumir():
    y, cal = v.preparar()
    Pn = leer(con_nan=True); I, Dident = identidad(Pn)
    P = _medidas(Pn)
    T = P.groupby(["anio", "combo", "version", "bloque"]).apply(v.metricas)
    tramo = P[(P.anio == 2026) & P.origen.between(*TRAMO)]
    Tt = tramo.groupby(["combo", "version", "bloque"]).apply(v.metricas)
    Po = (tramo[tramo.version == "b"].groupby(["bloque", "origen", "combo"]).ape.mean().unstack("combo"))
    x = lambda a, c, k: T.loc[(a, c, "b", 1), k]
    R = {"(1) identidad 2025 y antes del sismo": {}, "regla 2025 (eleccion)": {}, "(2) 2026 frente a": {}, "(3) tramo del sismo, 1-7, b": {}}
    for (a, b, ver, ant), f in I.iterrows():
        if a == 2025 or ant:
            R["(1) identidad 2025 y antes del sismo"][f"{a}|{b}|{ver}|{'antes' if ant else 'después'}"] = float(f.dif_max)
    ident_ok = all(val == 0 for val in R["(1) identidad 2025 y antes del sismo"].values())
    dm_, dc = x(2025, NUEVO, "MAPE %") - x(2025, "M3s", "MAPE %"), x(2025, NUEVO, "en rango 80 %") - x(2025, "M3s", "en rango 80 %")
    mejora = bool(dm_ < MEJORA_MAPE and dc >= MEJORA_COB)
    R["regla 2025 (eleccion)"] = {"dif MAPE vs M3s": dm_, "dif cobertura vs M3s": dc, "mejora": mejora}
    emp = False
    for ref in ("C0r", "M3s"):
        dm2, dc2 = x(2026, NUEVO, "MAPE %") - x(2026, ref, "MAPE %"), x(2026, NUEVO, "en rango 80 %") - x(2026, ref, "en rango 80 %")
        e = bool(dm2 > EMPEORA_MAPE or dc2 < EMPEORA_COB); emp = emp or e
        R["(2) 2026 frente a"][ref] = {"dif MAPE": dm2, "dif cobertura": dc2, "empeora": e}
    mt = Tt.loc[(NUEVO, "b", 1), "MAPE %"] - Tt.loc[("M3s", "b", 1), "MAPE %"]
    R["(3) tramo del sismo, 1-7, b"] = {"MAPE M3s-cf": Tt.loc[(NUEVO, "b", 1), "MAPE %"], "MAPE M3s": Tt.loc[("M3s", "b", 1), "MAPE %"],
                                        "MAPE C0r": Tt.loc[("C0r", "b", 1), "MAPE %"], "dif": mt, "gana": bool(mt < 0),
                                        "días": int(Tt.loc[(NUEVO, "b", 1), "días"])}
    iny = json.loads((CARPETA / "inyeccion.json").read_text(encoding="utf-8")) if (CARPETA / "inyeccion.json").exists() else {}
    k_iny = f"terremoto la víspera (c = o - 1) | {NUEVO}"
    iny_ok = bool(iny) and iny.get(f"control sin cambio | {NUEVO}", {}).get("max_abs_total") == 0 and iny.get(k_iny, {}).get("max_abs_desde_dia_21") == 0
    R["(4) inyeccion"] = iny_ok
    R["pasa por la regla de m3s_correcciones_red_salud"] = bool(mejora and not emp)
    R["favorable (diagnostico)"] = bool(ident_ok and not emp and mt < 0 and iny_ok)
    DM = []
    conj = {"2026 completo": P[P.anio == 2026], "tramo del sismo": tramo, "2025": P[P.anio == 2025]}
    for nom, S0 in conj.items():
        for (b, ver), S in S0.groupby(["bloque", "version"]):
            h = 7 if b == 1 else 21
            for a_, b_ in ((NUEVO, "M3s"), (NUEVO, "C0r"), ("M3s", "C0r")):
                for perd in ("ape", "ae"):
                    W = S.pivot_table(index="fecha", columns="combo", values=perd)[[a_, b_]].dropna().sort_index()
                    d = W[a_] - W[b_]
                    if len(d) < 3 or np.allclose(d, 0): m, s, p, n, pb = float(d.mean()), np.nan, np.nan, len(d), np.nan
                    else: m, s, p, n, pb = v.dm(d, min(h, len(d) - 1))
                    DM.append({"conjunto": nom, "bloque": b, "version": ver, "par": f"{a_} - {b_}", "pérdida": perd,
                               "dif media": m, "DM (HLN)": s, "p": p, "p Bartlett": pb, "n": n})
    DM = pd.DataFrame(DM)
    Bq = P[(P.version == "b") & (P.anio == 2026)].pivot_table(index=["bloque", "origen", "fecha"], columns="combo", values="ape").reset_index()
    Bq = Bq.join(va.estados(Bq[["origen", "fecha"]]))
    E = []
    for b, Gb in Bq.groupby("bloque"):
        N = len(Gb)
        for k, g in list(Gb.groupby("exclusivo")) + [("TOTAL", Gb)]:
            f = {"bloque": b, "estado": k, "días": len(g)}
            for c in ["C0r", "M3s", NUEVO]: f[f"MAPE {c}"] = g[c].mean()
            f[f"{NUEVO} - M3s"] = (g[NUEVO] - g["M3s"]).mean(); f[f"contribución {NUEVO} - M3s"] = (g[NUEVO] - g["M3s"]).sum() / N
            E.append(f)
    E = pd.DataFrame(E)
    CARPETA.mkdir(parents=True, exist_ok=True)
    T.to_csv(CARPETA / "tabla_principal.csv"); Tt.to_csv(CARPETA / "tramo_sismo.csv"); Po.to_csv(CARPETA / "tramo_por_origen.csv")
    DM.to_csv(CARPETA / "diebold_mariano.csv", index=False); E.to_csv(CARPETA / "por_estado_2026.csv", index=False)
    I.to_csv(CARPETA / "identidad.csv")
    (CARPETA / "regla.json").write_text(json.dumps(R, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    return T, Tt, Po, DM, E, I, R


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproducir", action="store_true"); ap.add_argument("--inyeccion", action="store_true")
    ap.add_argument("--correr", action="store_true"); ap.add_argument("--resumir", action="store_true")
    ap.add_argument("--anio", type=int, nargs="*", default=[2026, 2025]); ap.add_argument("--bloque", type=int, nargs="*")
    ap.add_argument("--limite", type=int)
    a = ap.parse_args()
    if a.reproducir:
        r = v.reproducir(); _avisar(f"reproducción 2026-10-14 con el código de la variante: {r}")
    if a.inyeccion:
        r = inyeccion(); _avisar("inyección: " + json.dumps(r, ensure_ascii=False))
    if a.correr:
        for an in a.anio: correr(an, solo=a.bloque, limite=a.limite)
    if a.resumir:
        pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 500)
        T, Tt, Po, DM, E, I, R = resumir()
        for k, x_ in (("principal", T), ("tramo", Tt), ("tramo por origen", Po), ("DM", DM), ("estado 2026", E), ("identidad", I)):
            print(f"\n== {k}\n{x_.round(3).to_string()}")
        print(json.dumps(R, ensure_ascii=False, indent=1, default=float))
