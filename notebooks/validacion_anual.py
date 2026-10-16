"""
Las correcciones de M3s (fila m3s_correcciones_red_salud de patrones/datos/variables.csv), elegidas con 2025 y
confirmadas con 2026:
    M3s-r   M3s sin las variables de red calculadas con el triage del SES; la resolucion de la Supersalud, sin compuerta
    M3s-rs  M3s-r con la salud publica leida 1 semana mas tarde (la ultima semana epidemiologica completa)

Reutiliza la maquinaria de validacion_2026.py (mismo FIN, misma foto del Power BI, SARIMAX desde cero en cada reentreno,
versiones a = el modelo solo y b = con la red v2 y el rango W) con un parametro de anio. En 2026 solo calcula las
variantes: C0r y M3s se leen tal cual de salidas/pronostico/validacion_2026/origenes/.

    python notebooks/validacion_anual.py --reproducir                    M3s y C0r contra las corridas 2026-10-14_*
    python notebooks/validacion_anual.py --medir --anio 2025             tiempo de un origen (adelanto 1-7)
    python notebooks/validacion_anual.py --correr --anio 2025 2026       todos los origenes; reanuda lo que falte
    python notebooks/validacion_anual.py --resumir                       tablas, regla, Diebold-Mariano, mes y estado

Guarda un archivo por (anio, bloque de adelanto, origen) en salidas/pronostico/correcciones_red_salud/origenes/: una
interrupcion no pierde lo hecho. El porque de cada eleccion esta en la fila del preregistro y en docs/CONTEXTO.md.
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
from validacion_2026 import pr, sm, mc   # noqa: E402

CARPETA = pr.SALIDA / "correcciones_red_salud"
ORIGENES = CARPETA / "origenes"
REGISTRO = CARPETA / "progreso.log"
NUEVOS = ["M3s-r", "M3s-rs"]
COMBOS = {2025: ["C0r", "M3s"] + NUEVOS, 2026: NUEVOS}          # 2026: C0r y M3s se reutilizan de validacion_2026
REFIT = {1: 1, 15: 4}                                         # se puede bajar 15 a 8 con --refit15 (preregistrado)
PERIODO_2025 = ("2024-12-29", "2025-12-21")                   # 52 domingos: la convencion de semana.resumen_validacion
MEJORA_MAPE, MEJORA_COB = -.1, -2.                            # eleccion con 2025 frente a M3s
EMPEORA_MAPE, EMPEORA_COB = .5, -5.                           # confirmacion con 2026 frente a C0r y a M3s
PARES = [("M3s-r", "M3s"), ("M3s-rs", "M3s"), ("M3s-r", "C0r"), ("M3s-rs", "C0r"), ("M3s-rs", "M3s-r"), ("M3s", "C0r")]


def _avisar(s):
    linea = f"{pd.Timestamp.now():%Y-%m-%d %H:%M:%S} {s}"
    print(linea, flush=True)
    CARPETA.mkdir(parents=True, exist_ok=True)
    with open(REGISTRO, "a", encoding="utf-8") as f: f.write(linea + "\n")


def origenes(anio, lead):
    if anio == 2026: return v.origenes(lead)                  # los mismos de validacion_2026 (y los mismos reentrenos)
    return list(pd.date_range(*PERIODO_2025, freq="W-SUN"))


def archivo(anio, lead, o):
    return ORIGENES / f"{anio}_{lead:02d}_{o.date()}.parquet"


def correr(anio, solo=None, limite=None, refit=None):
    refit = refit or REFIT
    y, cal = v.preparar(); ORIGENES.mkdir(parents=True, exist_ok=True)
    ent = v.Entrega()
    _avisar(f"Inicio {anio}. FIN={v.FIN}, foto={v.FOTO.name}, combos={COMBOS[anio]}, REFIT={refit}")
    for lead in (solo or (1, 15)):
        ors = origenes(anio, lead); hs = list(range(lead, lead + 7)); r = refit[lead]
        pend = [o for o in ors if not archivo(anio, lead, o).exists()]
        if not pend: _avisar(f"{anio} bloque {lead}: completo ({len(ors)} orígenes)"); continue
        t0 = time.time(); cs = COMBOS[anio]
        aj = sm.Ajuste(y, cal, sorted({m for c in cs for m in sm.COMBOS[c]}))
        _avisar(f"{anio} bloque {lead}: {len(pend)} de {len(ors)} orígenes pendientes; modelos {sorted(aj.M)} construidos en {time.time() - t0:.0f} s")
        ajustado = None
        for n_hecho, o in enumerate(pend):
            if limite is not None and n_hecho >= limite: break
            t1 = time.time(); i = ors.index(o); ro = ors[i - i % r]; partes = []
            if ajustado != ro:
                v.de_cero(aj); aj.ajustar(ro, hs); ajustado = ro
            C = aj.M["control"]
            normal = np.array([[float(C.predecir_h(C.m[h], C.fila(h, o))[4]), C.m[h][2]] for h in hs])
            fechas = pd.date_range(o + pd.Timedelta(days=lead), periods=7)
            semilla = int(o.strftime("%Y%m%d")) * 100 + lead
            for c in cs:
                Q = v.predecir(aj, o, hs, sm.COMBOS[c])
                Qb, fr, qb = ent.aplicar(o, fechas, Q, semilla)
                ex = {"f_red": fr, "quiebre": qb, "reentreno": ro, "anio": anio}
                partes += [v.filas(o, lead, c, "a", Q, y, normal, ex), v.filas(o, lead, c, "b", Qb, y, normal, ex)]
            P = pd.concat(partes, ignore_index=True); P["segundos"] = time.time() - t1
            f = archivo(anio, lead, o); P.to_parquet(f.with_suffix(".tmp"), index=False); f.with_suffix(".tmp").replace(f)
            _avisar(f"{anio} bloque {lead}: origen {o.date()} ({i + 1}/{len(ors)}, reentreno {ro.date()}) en {time.time() - t1:.0f} s")
    _avisar(f"FIN {anio}")


def reproducir():
    """M3s y C0r con el codigo de validacion_2026 tras los cambios de esta fila, contra las corridas guardadas."""
    return v.reproducir()


# ------------------------------------------------------------------ resumen
def leer():
    P = pd.concat([pd.read_parquet(f) for f in sorted(ORIGENES.glob("*.parquet"))], ignore_index=True)
    R = pd.concat([pd.read_parquet(f) for f in sorted(v.ORIGENES.glob("*.parquet"))], ignore_index=True)
    R = R[R.combo.isin(["C0r", "M3s"])].assign(anio=2026)
    P = pd.concat([P, R], ignore_index=True).dropna(subset=["real"]).copy()
    P["ape"] = 100 * (P.q50 - P.real).abs() / P.real; P["ae"] = (P.q50 - P.real).abs()
    P["sesgo"] = 100 * (P.q50 - P.real) / P.real; P["en_rango"] = P.real.between(P.q10, P.q90)
    P["acierta"] = (P.p_sube > .5) == (P.real > P.vara)
    return P


def estados(F):
    """Estado del dia como en validacion_2026.estados (calendario en t; compuertas de M3s en el origen; sismo), para
    cualquier anio."""
    dias = pd.date_range("2024-12-01", pd.Timestamp(v.FIN) + pd.Timedelta(days=21))
    FUT, PAS, G = mc.columnas(dias)
    cal = (FUT[["fut_m_feria_d0_4", "fut_m_fiesta_lejana", "fut_m_noche_festiva", "fut_m_dia_siguiente"]].fillna(0) > 0)
    o, t = F.origen, F.fecha
    E = pd.DataFrame({"calendario": cal.any(axis=1).reindex(t).values,
                      "salud": G.salud.reindex(o).values.astype(bool), "red": G.red.reindex(o).values.astype(bool),
                      "social": G.social.reindex(o).values.astype(bool),
                      "sismo": ((t - v.SISMO).dt.days.between(0, 21)).values}, index=F.index)
    E["exclusivo"] = np.select([E.sismo, E.calendario, E.red, E.salud, E.social], ["sismo", "calendario", "red", "salud", "social"], "normal")
    return E


def regla(T):
    x = lambda a, c, k: T.loc[(a, c, "b", 1), k]
    R = {"2025": {}, "2026": {}}
    for c in NUEVOS:
        dm_, dc = x(2025, c, "MAPE %") - x(2025, "M3s", "MAPE %"), x(2025, c, "en rango 80 %") - x(2025, "M3s", "en rango 80 %")
        R["2025"][c] = {"dif MAPE vs M3s": dm_, "dif cobertura vs M3s": dc, "mejora": bool(dm_ < MEJORA_MAPE and dc >= MEJORA_COB)}
    mejoran = [c for c in NUEVOS if R["2025"][c]["mejora"]]
    elegida = min(mejoran, key=lambda c: x(2025, c, "MAPE %")) if mejoran else None
    for c in NUEVOS:
        R["2026"][c] = {}
        for ref in ("C0r", "M3s"):
            dm_, dc = x(2026, c, "MAPE %") - x(2026, ref, "MAPE %"), x(2026, c, "en rango 80 %") - x(2026, ref, "en rango 80 %")
            R["2026"][c][ref] = {"dif MAPE": dm_, "dif cobertura": dc, "empeora": bool(dm_ > EMPEORA_MAPE or dc < EMPEORA_COB)}
    pasa = bool(elegida) and not any(R["2026"][elegida][r]["empeora"] for r in ("C0r", "M3s"))
    R["elegida con 2025"] = elegida; R["pasa"] = pasa
    return R


def resumir():
    y, cal = v.preparar(); P = leer(); P["mes"] = P.fecha.dt.month
    T = P.groupby(["anio", "combo", "version", "bloque"]).apply(v.metricas)
    M = (P[P.version == "b"].groupby(["anio", "bloque", "mes", "combo"]).apply(v.metricas)
         [["MAPE %", "en rango 80 %", "sesgo %", "acierto sube/baja %", "días"]])
    R = regla(T)
    DM = []
    for (a, b, ver), S in P.groupby(["anio", "bloque", "version"]):
        h = 7 if b == 1 else 21
        for a_, b_ in PARES:
            if not {a_, b_} <= set(S.combo): continue
            for perd in ("ape", "ae"):
                W = S.pivot_table(index="fecha", columns="combo", values=perd)[[a_, b_]].dropna().sort_index()
                m, s, p, n, pb = v.dm(W[a_] - W[b_], h)
                DM.append({"anio": a, "bloque": b, "version": ver, "par": f"{a_} - {b_}", "pérdida": perd, "dif media": m,
                           "DM (HLN)": s, "p": p, "p Bartlett": pb, "n": n})
    DM = pd.DataFrame(DM)
    B = P[P.version == "b"].pivot_table(index=["anio", "bloque", "origen", "fecha"], columns="combo", values="ape").reset_index()
    B = B.join(estados(B[["origen", "fecha"]]))
    filas_ = []
    for (a, b), Gb in B.groupby(["anio", "bloque"]):
        N = len(Gb)
        grupos = [(k, Gb[Gb[k]], "con solapes") for k in ["calendario", "salud", "red", "social", "sismo"]]
        grupos += [(k, g, "exclusivo") for k, g in Gb.groupby("exclusivo")] + [("TOTAL", Gb, "exclusivo")]
        for k, g, tipo in grupos:
            f = {"anio": a, "bloque": b, "estado": k, "tipo": tipo, "días": len(g)}
            for c in ["C0r", "M3s"] + NUEVOS: f[f"MAPE {c}"] = g[c].mean()
            for c in NUEVOS:
                for ref in ("M3s", "C0r"):
                    f[f"{c} - {ref}"] = (g[c] - g[ref]).mean()
                    f[f"contribución {c} - {ref}"] = (g[c] - g[ref]).sum() / N
            filas_.append(f)
    C = pd.DataFrame(filas_)
    # rho de la copula medido en 2025 con semana.resumen_validacion, para la operacion (version a: el modelo solo, como
    # se midio operacion.RHO; y version b, informativa)
    rhos = {}
    for ver in ("a", "b"):
        Q = P[(P.anio == 2025) & (P.version == ver)].rename(columns={"bloque": "adelanto", "control": "normal"})
        _, r = sm.resumen_validacion(Q, y); rhos[ver] = {f"{c}|{l}": round(x_, 3) for (c, l), x_ in r.items()}
    CARPETA.mkdir(parents=True, exist_ok=True)
    T.to_csv(CARPETA / "tabla_principal.csv"); M.to_csv(CARPETA / "por_mes.csv"); DM.to_csv(CARPETA / "diebold_mariano.csv", index=False)
    C.to_csv(CARPETA / "por_estado.csv", index=False); B.to_parquet(CARPETA / "dias_estado.parquet", index=False)
    (CARPETA / "regla.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    (CARPETA / "rho_2025.json").write_text(json.dumps(rhos, ensure_ascii=False, indent=1), encoding="utf-8")
    return T, M, DM, C, R, rhos


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--reproducir", action="store_true"); ap.add_argument("--medir", action="store_true")
    ap.add_argument("--correr", action="store_true"); ap.add_argument("--resumir", action="store_true")
    ap.add_argument("--anio", type=int, nargs="*", default=[2025, 2026]); ap.add_argument("--bloque", type=int, nargs="*")
    ap.add_argument("--limite", type=int); ap.add_argument("--refit15", type=int, default=4)
    a = ap.parse_args()
    if a.reproducir:
        r = reproducir(); _avisar(f"reproducción 2026-10-14 tras los cambios: {r}")
    if a.medir:
        for an in a.anio: correr(an, solo=(1,), limite=1)
    if a.correr:
        for an in a.anio: correr(an, solo=a.bloque, refit={1: 1, 15: a.refit15})
    if a.resumir:
        pd.set_option("display.width", 250); pd.set_option("display.max_columns", 40); pd.set_option("display.max_rows", 500)
        T, M, DM, C, R, rhos = resumir()
        for k, x_ in (("principal", T), ("mes", M), ("DM", DM), ("estado", C)): print(f"\n== {k}\n{x_.round(3).to_string()}")
        print(json.dumps(R, ensure_ascii=False, indent=1)); print(rhos)
