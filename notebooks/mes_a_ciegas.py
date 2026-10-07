"""
La prueba del mes a ciegas (fila mes_a_ciegas de patrones/datos/variables.csv): el modelo se entrena con el triage
hasta el 31 de diciembre y predice de una vez cada dia de septiembre del ano siguiente, sin reentrenar ni ver nada
posterior. Septiembre de 2023, 2024 y 2025 validan el diseno; septiembre de 2026 es la prueba.

    python notebooks/mes_a_ciegas.py                  los cuatro septiembres que falten
    python notebooks/mes_a_ciegas.py --anios 2026     solo uno (rehace el archivo si ya existe)
    python notebooks/mes_a_ciegas.py --revision       cuaderno 25: marzo, julio y agosto desde el 2025-12-31 y
                                                      octubre desde el 2026-09-20 (prospectivo: no se rehace)

Escribe salidas/pronostico/mes_a_ciegas/<ano>.parquet: una fila por (modelo, fecha) con los cuantiles y lo real.
Modelos: las piezas (sarimax_mec, lightgbm_rel_mec, sarimax, lightgbm_rel), sus combinaciones (M3s, C0r), lo normal
(la regresion anual de calendario) y el mismo dia de hace 52 semanas.
"""
import argparse
import time
import warnings

import numpy as np
import pandas as pd

import pronostico as pr
import mecanismos as mc

CARPETA = pr.SALIDA / "mes_a_ciegas"
ULTIMO_DATO = "2026-09-20"          # el 21-sep-2026 esta incompleto y lo posterior no esta en salidas/
ANIOS = [2023, 2024, 2025, 2026]
COMBOS = {"M3s": ("m3s_ciego", "sarimax_mec", "lightgbm_rel_mec"), "C0r": ("e1", "sarimax", "lightgbm_rel")}


def ventana(anio):
    """Origen (31 de diciembre anterior) y los dias de septiembre."""
    return pd.Timestamp(f"{anio - 1}-12-31"), pd.date_range(f"{anio}-09-01", f"{anio}-09-30")


def datos(exp, fin):
    """(y, cal) del experimento con el calendario hasta 'fin'. El triage posterior a ULTIMO_DATO va como faltante:
    los modelos directos necesitan la fila del dia a predecir, pero nunca su valor."""
    pr.FIN, pr.H = str(fin.date()), 1
    if exp in pr.EXPERIMENTOS and pr.EXPERIMENTOS[exp].get("contexto") == "mecanismos":
        y, cal = mc.preparar(exp)                 # quita la fase fuerte de la COVID y activa los mecanismos
    else:
        pr.usar(exp); y, cal = pr.cargar()
    y = y.copy(); y[y.index > ULTIMO_DATO] = np.nan
    return y, cal


def sarimax(nombre, y, cal, o, n):
    """Pronostico de n pasos desde o. Lo que no se sabe en el origen va como ano tipico (pasado_tipico)."""
    M = pr.MODELOS[nombre](y, cal)
    M.ajustar(o)
    return M.predecir(o, n=n, pasado_tipico=True)


def directo(nombre, y, cal, o, hs):
    """LightGBM directo: un modelo por adelanto h, entrenado con las entradas de pronostico.rasgos desplazadas h dias
    (todo lo que no es calendario ni programado sale de <= t - h)."""
    pr.H = 1
    M = pr.MODELOS[nombre](y, cal)
    ctx = None if M.ctx is None else tuple(c.reindex(y.index) for c in M.ctx)
    Q = []
    for h in hs:
        M.X = {h: pr.rasgos(y, cal.reindex(y.index), h, ctx)}
        X, yy = M.datos(h, o)
        cols = X.columns[X.std() > 0]
        Q.append(M.predecir_h(M.ajustar_h(X[cols], yy), M.X[h].loc[[o + pd.Timedelta(days=h)], cols]))
    return np.vstack(Q)


def predecir(o, fechas, avisar=print):
    """Las predicciones de todos los modelos para 'fechas', con lo conocido hasta el origen o y sin reentrenar.
    Una fila por (modelo, fecha) con los cuantiles y lo real de salidas/ (faltante despues de ULTIMO_DATO)."""
    fin = fechas[-1]
    hs = [(t - o).days for t in fechas]; n = max(hs)
    filas, t0 = {}, time.time()
    for combo, (exp, s, l) in COMBOS.items():
        y, cal = datos(exp, fin)
        filas[s] = sarimax(s, y, cal, o, n)[[h - 1 for h in hs]]
        avisar(f"  {fechas[0].date()} {s}: {time.time() - t0:.0f} s")
        filas[l] = directo(l, y, cal, o, hs)
        avisar(f"  {fechas[0].date()} {l}: {time.time() - t0:.0f} s")
        filas[combo] = np.sort((filas[s] + filas[l]) / 2, axis=1)       # promedio de cuantiles, como semana.py
    y, cal = datos("e1", fin)
    pr.ANIO_ORIGEN = str(o.date())
    for nombre, base in [("normal", "regresion_anual"), ("anio_pasado", "anio_pasado")]:
        d = pr.anio_a_ciegas(base, y, cal).set_index("fecha").loc[fechas]
        filas[nombre] = d[pr.QCOL].values
    real = pd.read_parquet(pr.RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
    real = real.set_index("dia").triages.astype(float).reindex(fechas)
    real[real.index > ULTIMO_DATO] = np.nan
    return pd.concat([pd.DataFrame({"modelo": m, "origen": o, "fecha": fechas, "h": hs, "real": real.values,
                                    **{c: Q[:, j] for j, c in enumerate(pr.QCOL)}}) for m, Q in filas.items()],
                     ignore_index=True)


def correr(anio, avisar=print):
    o, fechas = ventana(anio)
    P = predecir(o, fechas, avisar).assign(anio=anio)
    CARPETA.mkdir(parents=True, exist_ok=True)
    P.to_parquet(CARPETA / f"{anio}.parquet")
    return P


# ------------------------------------------------------------------ revision de predicciones (cuaderno 25)
REVISION = pr.SALIDA / "revision"
MESES_REVISION = {"2026-03": "2025-12-31", "2026-07": "2025-12-31", "2026-08": "2025-12-31", "2026-10": ULTIMO_DATO}
BANDA = .05


def archivo(mes, origen):
    return REVISION / f"{mes}_desde_{pd.Timestamp(origen).date()}"


def revisar(meses, avisar=print, rehacer=False):
    """Predice los meses pedidos (fila revision_de_predicciones). Un mes cuyo dato aun no existe es una prediccion
    prospectiva: se guarda con fecha y commit y no se rehace nunca. Los meses con el mismo origen se ajustan juntos."""
    import json, subprocess
    from datetime import datetime
    REVISION.mkdir(parents=True, exist_ok=True)
    por_origen = {}
    for m in meses:
        base = archivo(m, MESES_REVISION[m])
        prospectiva = pd.Timestamp(f"{m}-01") > pd.Timestamp(ULTIMO_DATO)
        if base.with_suffix(".parquet").exists() and (prospectiva or not rehacer):
            avisar(f"  {m}: ya existe {base.name}" + (" (prospectiva: no se rehace)" if prospectiva else "")); continue
        por_origen.setdefault(MESES_REVISION[m], []).append(m)
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=pr.RAIZ).stdout.strip()
    for o, ms in por_origen.items():
        fechas = pd.DatetimeIndex(sorted(t for m in ms for t in pd.date_range(f"{m}-01", pd.Period(m).end_time.normalize())))
        P = predecir(pd.Timestamp(o), fechas, avisar)
        for m in ms:
            base = archivo(m, o)
            P[P.fecha.dt.strftime("%Y-%m") == m].reset_index(drop=True).to_parquet(base.with_suffix(".parquet"))
            base.with_suffix(".json").write_text(json.dumps({"mes": m, "origen": o, "creado": datetime.now().isoformat(timespec="seconds"),
                "commit": commit, "fila": "revision_de_predicciones"}, ensure_ascii=False, indent=1), encoding="utf-8")
            avisar(f"  {m}: guardado {base.name}")


def vara(mes, origen):
    """'Lo normal' de sube/normal/baja: la media de cada dia de la semana en las 8 semanas anteriores al mes (o al
    origen, si el mes empieza despues de lo ultimo conocido). Indice: dia de la semana (0 = lunes)."""
    d = pd.read_parquet(pr.RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda x: pd.to_datetime(x.dia))
    d = d.set_index("dia").triages.astype(float).loc[:ULTIMO_DATO]
    d["2024-03-19":"2024-03-21"] = np.nan
    fin = min(pd.Timestamp(f"{mes}-01") - pd.Timedelta(days=1), pd.Timestamp(ULTIMO_DATO))
    v = d[fin - pd.Timedelta(days=55):fin]
    return v.groupby(v.index.dayofweek).mean()


def reportado():
    """Conteos escritos a mano en datos/triage_reportado.csv (fuente externa). Solo para comparar: nunca entrenan."""
    f = pr.RAIZ / "datos/triage_reportado.csv"
    if not f.exists(): return pd.Series(dtype=float)
    r = pd.read_csv(f, parse_dates=["fecha"]).dropna(subset=["triages"])
    return r.set_index("fecha").triages.astype(float)


def leer():
    return pd.concat([pd.read_parquet(f) for f in sorted(CARPETA.glob("*.parquet"))], ignore_index=True)


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--anios", nargs="*", type=int, help="por defecto, los que falten de 2023-2026")
    ap.add_argument("--revision", nargs="*", help="cuaderno 25: meses AAAA-MM (sin valor: los cuatro de MESES_REVISION)")
    ap.add_argument("--rehacer", action="store_true", help="con --revision: rehace los meses pasados (nunca los prospectivos)")
    a = ap.parse_args()
    if a.revision is not None:
        revisar(a.revision or list(MESES_REVISION), avisar=lambda s: print(s, flush=True), rehacer=a.rehacer)
        raise SystemExit
    for anio in a.anios or [x for x in ANIOS if not (CARPETA / f"{x}.parquet").exists()]:
        P = correr(anio, avisar=lambda s: print(s, flush=True))
        g = P[P.modelo.isin(["M3s", "C0r", "normal"])].dropna(subset=["real"])
        print(g.groupby("modelo").apply(lambda d: 100 * np.mean(np.abs(d.q50 - d.real) / d.real)).round(1).to_string(), flush=True)
