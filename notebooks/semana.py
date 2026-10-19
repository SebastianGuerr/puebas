"""
La respuesta semanal: «¿cómo se va a comportar urgencias esta semana?» (fila pronostico_semanal de
patrones/datos/variables.csv). Corre con los datos que haya en salidas/; no consulta la base.

    python notebooks/semana.py --semana 2026-10-05        predice la semana que empieza ese lunes y la GUARDA
    python notebooks/semana.py --verificar 2026-10-05     compara lo guardado con lo real (cuando haya datos)
    python notebooks/semana.py --validar                  la misma respuesta en los domingos de 2025 y 2026

Modelo: la combinacion (promedio de cuantiles) de SARIMAX y LightGBM sobre el desvio del nivel (C0r), entrenada desde 2020 con
calendario, estacion, nivel y memoria. 'Lo normal' es el control de calendario + nivel de 28 dias. El rango de la
semana sale de una copula gaussiana entre los 7 dias, con la correlacion medida en la validacion de 2025.

Una prediccion guardada no se rehace: es la prueba prospectiva, y su valor depende de haberse escrito antes.
"""
import argparse
import json
import subprocess
import time
import warnings
from datetime import datetime

import numpy as np
import pandas as pd
from scipy.stats import norm

import pronostico as pr
import reparto as rp

pr.H = 21                                      # hasta 3 semanas de adelanto: hoy los datos van 15 dias por detras
CARPETA = pr.SALIDA / "semanal"
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
FRANJAS = rp.FRANJAS                           # madrugada 0-5, mañana 6-11, tarde 12-17, noche 18-23 (fila reparto_del_dia)
PERFIL = "P52"                                 # elegido en reparto_del_dia: mismo día de la semana, 52 semanas
DESCRIPCION = {"C0r": "SARIMAX + LightGBM, solo calendario, estación, nivel y memoria",
               "Cg": "SARIMAX + LightGBM con el contexto de salud pública, que se enciende cuando hay ola, y las marcas de contexto",
               "M3s": "SARIMAX + LightGBM con los mecanismos medidos (Feria, noches festivas, fiestas lejanas, catástrofe, salud pública y red con compuerta), sin la fase fuerte de la COVID en el entrenamiento",
               "M3s-r": "M3s sin las variables de red calculadas con el propio triage (la red va solo en la corrección externa); la resolución de la Supersalud sobre Nueva EPS, sin compuerta",
               "M3s-rs": "M3s-r con la salud pública leída en la última semana epidemiológica completa (1 semana de rezago de notificación)",
               "M3s-cf": "M3s con la catástrofe contada desde el día predicho (días desde el terremoto sabido en el origen), no como estado congelado del origen"}
# 'modelo@exp': el modelo se construye con el contexto de ese experimento (Cg: salud publica en compuerta, fila
# contexto_con_compuerta_confirmacion); sin '@', con el de e1 (sin contexto)
COMBOS = {"C0": ["sarimax", "lightgbm"], "C0r": ["sarimax", "lightgbm_rel"], "Cg": ["sarimax", "lightgbm_rel@g"],
          "M3s": ["sarimax_mec@m3s", "lightgbm_rel_mec@m3s"],          # fila m3_semanal (notebooks/mecanismos.py)
          "M3cal": ["sarimax_mec@m3cal", "lightgbm_rel_mec@m3cal"],    # diagnostico (fila validacion_2026_operacion_semanal)
          # candidatas (fila m3s_correcciones_red_salud). Su SARIMAX es el de M3s: sarimax_mec no usa ni la red ni la salud
          "M3s-r": ["sarimax_mec@m3s", "lightgbm_rel_mec@m3s_r"],
          "M3s-rs": ["sarimax_mec@m3s", "lightgbm_rel_mec@m3s_rs"],
          # diagnostico aislado (fila m3s_catastrofe_por_fecha): la catastrofe entra en los dos modelos, asi que los
          # dos son propios
          "M3s-cf": ["sarimax_mec@m3s_cf", "lightgbm_rel_mec@m3s_cf"]}
DIAGNOSTICO = {"M3cal", "M3s-r", "M3s-rs", "M3s-cf"}   # fuera del valor por defecto de validar() (no cambia lo publicado)


def datos():
    pr.usar("e1")
    y, cal = pr.cargar()
    # dias futuros como faltantes: sin ellos los modelos directos no tienen fila para predecir despues del ultimo dato
    # (2026-10-06; el entrenamiento y la validacion no cambian: descartan faltantes y solo miran el pasado)
    y = y.reindex(pd.date_range(y.index[0], pd.Timestamp(pr.FIN) + pd.Timedelta(days=pr.H)))
    h = pd.read_parquet(pr.RAIZ / "salidas/triage_horario.parquet")
    h["dia"] = pd.to_datetime(h.dia)
    F = pd.DataFrame({f: h[h.hora.between(a, b)].groupby("dia").triages.sum() for f, (a, b) in FRANJAS.items()})
    F["dia_total"] = h.groupby("dia").triages.sum()
    return y, cal, F.fillna(0)


class Ajuste:
    """Los modelos de la combinacion y el control, ajustados en un origen, para los adelantos pedidos."""
    def __init__(self, y, cal, modelos):
        self.M = {m: self.construir(m, y, cal) for m in set(modelos) | {"control"}}
        self.modelos = modelos

    @staticmethod
    def construir(m, y, cal):
        nombre, _, exp = m.partition("@")
        if not exp: return pr.MODELOS[nombre](y, cal)
        if pr.EXPERIMENTOS[exp].get("contexto") == "mecanismos":      # M3s: mecanismos.py aplica su entrenamiento
            import mecanismos; return mecanismos.construir(nombre, exp, y, cal)
        previo = pr.EXP; pr.usar(exp)
        try: return pr.MODELOS[nombre](y, cal)
        finally: pr.EXP = previo

    def ajustar(self, o, hs):
        for nombre, M in self.M.items():
            if isinstance(M, pr._Directo):
                M.cols, M.m = {}, {}
                for h in hs:
                    X, yy = M.datos(h, o)
                    M.cols[h] = X.columns[X.std() > 0]
                    M.m[h] = M.ajustar_h(X[M.cols[h]], yy)
            else:
                M.ajustar(o)

    def predecir(self, o, hs, modelos=None):
        """Cuantiles por dia (filas = hs) de la combinacion de 'modelos', y lo normal (control) con su desviacion."""
        Q = {}
        for nombre in modelos or self.modelos:
            M = self.M[nombre]
            if isinstance(M, pr._Directo):
                Q[nombre] = np.vstack([M.predecir_h(M.m[h], M.fila(h, o)) for h in hs])
            else:
                Q[nombre] = M.predecir(o, n=max(hs))[[h - 1 for h in hs]]
        C = self.M["control"]
        normal = np.array([[float(C.predecir_h(C.m[h], C.fila(h, o))[4]), C.m[h][2]] for h in hs])
        return np.sort(np.mean(list(Q.values()), axis=0), axis=1), normal


def pit(Q, real):
    return np.array([np.interp(r, q, pr.QL, left=.01, right=.99) for q, r in zip(Q, real)])


def semana_agregada(Q, rho, n=4000, semilla=0):
    """Distribucion de la media diaria de la semana: copula gaussiana con correlacion rho^|i-j| entre dias."""
    k = len(Q); S = rho ** np.abs(np.subtract.outer(np.arange(k), np.arange(k)))
    u = norm.cdf(np.random.default_rng(semilla).multivariate_normal(np.zeros(k), S, size=n))
    sims = np.column_stack([np.interp(u[:, j], pr.QL, Q[j]) for j in range(k)])
    return sims.mean(axis=1)


_PERFILES = {}


def reparto(o, fechas, Q, semilla=0):
    """Franjas con su rango y horas de más demanda (fila reparto_del_dia): perfil P52 con solo días <= o, total del
    día de sus cuantiles, proporciones Dirichlet y conteo multinomial. Antes (hasta el 2026-10-13): la proporción
    media de 8 semanas, en 2 franjas y con el rango del día."""
    if "pf" not in _PERFILES: _PERFILES["pf"] = rp.Perfiles(rp.horas(), rp.festivos())
    pf, rng, filas = _PERFILES["pf"], np.random.default_rng(semilla), []
    for t, q in zip(fechas, Q):
        p, a = pf.perfil(PERFIL, o, t)
        X = rp.simular(q, p, a, rng); fila = {}
        for f, (lo, hi) in FRANJAS.items():
            x = X[:, lo:hi + 1].sum(1)
            fila |= {f"{f}_q10": np.quantile(x, .1), f"{f}_q50": np.quantile(x, .5), f"{f}_q90": np.quantile(x, .9)}
        esp = p * q[4]
        for f, inicios in rp.BLOQUES.items():
            b = max(inicios, key=lambda s: esp[s:s + 3].sum())
            fila |= {f"bloque_{f}": b, f"bloque_{f}_por_hora": esp[b:b + 3].mean()}
        filas.append(fila)
    return pd.DataFrame(filas)


def responder(y, cal, F, o, lunes, combo, rho, aj=None):
    """La respuesta para la semana que empieza en 'lunes', con lo conocido hasta 'o'."""
    h0 = (lunes - o).days; hs = list(range(h0, h0 + 7))
    if aj is None:
        aj = Ajuste(y, cal, COMBOS[combo]); aj.ajustar(o, hs)
    Q, normal = aj.predecir(o, hs, COMBOS[combo])
    fechas = pd.date_range(lunes, periods=7)
    esp, sd = normal[:, 0], normal[:, 1]
    D = pd.DataFrame({"fecha": fechas, "h": hs, **{c: Q[:, j] for j, c in enumerate(pr.QCOL)},
                      "normal": esp, "umbral_pico": esp * np.exp(sd),
                      "p_sube": pr.prob_sobre(Q, esp), "p_pico": pr.prob_sobre(Q, esp * np.exp(sd))})
    D = pd.concat([D, reparto(o, fechas, Q)], axis=1)
    m = semana_agregada(Q, rho)
    previo = float(y.loc[o - pd.Timedelta(days=27):o].mean())
    W = {"origen": str(o.date()), "lunes": str(lunes.date()), "adelanto_dias": h0, "combo": combo, "rho": rho,
         "media_q10": float(np.quantile(m, .1)), "media_q50": float(np.quantile(m, .5)), "media_q90": float(np.quantile(m, .9)),
         "normal_semana": float(esp.mean()), "p_semana_sobre_normal": float((m > esp.mean()).mean()),
         "media_4_semanas_previas": previo, "p_semana_sobre_previas": float((m > previo).mean())}
    return D, W


def texto(D, W, calib=None):
    lun = pd.Timestamp(W["lunes"]); dom = lun + pd.Timedelta(days=6); o = pd.Timestamp(W["origen"])
    f = lambda t: f"{DIAS[t.dayofweek]} {t.day} de {MESES[t.month]}"
    L = [f"# Semana del {f(lun)} al {f(dom)} de {dom.year}", "",
         f"Pronóstico hecho con datos hasta el {f(o)} ({W['adelanto_dias']} a {W['adelanto_dias'] + 6} días de adelanto). "
         f"Modelo: {W['combo']} ({DESCRIPCION.get(W['combo'], 'SARIMAX + LightGBM')}).", "",
         f"**En esta semana los triages tendrán una media de {W['media_q50']:.0f} por día** "
         f"(80 % de probabilidad entre {W['media_q10']:.0f} y {W['media_q90']:.0f}), unos {7 * W['media_q50']:.0f} en total.", "",
         f"- Probabilidad de que la semana quede **por encima de lo normal** para estas fechas ({W['normal_semana']:.0f}/día): "
         f"**{100 * W['p_semana_sobre_normal']:.0f} %**.",
         f"- Probabilidad de que **aumente frente a las últimas 4 semanas conocidas** ({W['media_4_semanas_previas']:.0f}/día): "
         f"**{100 * W['p_semana_sobre_previas']:.0f} %**.", ""]
    top = D.sort_values("p_sube", ascending=False).head(2)
    L += [f"Los días con más probabilidad de subir por encima de lo normal: " +
          " y ".join(f"**{f(t)} ({100 * p:.0f} %)**" for t, p in zip(top.fecha, top.p_sube)) + ".", "",
          "| Día | Esperado | Rango 80 % | Lo normal | P(sube) | P(pico) |", "|---|---|---|---|---|---|"]
    for _, r in D.iterrows():
        L.append(f"| {f(r.fecha)} | {r.q50:.0f} | {r.q10:.0f}-{r.q90:.0f} | {r.normal:.0f} | {100 * r.p_sube:.0f} % | "
                 f"{100 * r.p_pico:.0f} % |")
    L += ["", "**Cómo se reparte cada día** (pacientes esperados y rango del 80 %):", "",
          "| Día | Madrugada 0-6 h | Mañana 6-12 h | Tarde 12-18 h | Noche 18-24 h | Más demanda en la mañana | Más demanda en la tarde |",
          "|---|---|---|---|---|---|---|"]
    for _, r in D.iterrows():
        fr = " | ".join(f"{r[f'{k}_q50']:.0f} ({r[f'{k}_q10']:.0f}-{r[f'{k}_q90']:.0f})" for k in FRANJAS)
        bl = " | ".join(f"{int(r[f'bloque_{k}'])}-{int(r[f'bloque_{k}']) + 3} h, ~{r[f'bloque_{k}_por_hora']:.0f}/hora"
                        for k in rp.BLOQUES)
        L.append(f"| {f(r.fecha)} | {fr} | {bl} |")
    L += ["", "**Cómo leerlo.** «Sube» es quedar por encima de lo normal para ese día de la semana con el volumen "
          "reciente; «pico» es quedar más de una desviación por encima. El reparto es la forma del mismo día de la semana "
          "en el último año aplicada al total esperado; su rango suma la duda del total y la del reparto. La forma del día "
          "es muy estable: el error que queda en cada franja es casi todo el del total del día y el azar de las llegadas. "
          "Las horas de más demanda son un rasgo fijo del servicio (9-12 h y 14-17 h casi siempre), no un aviso de "
          "saturación de ese día en particular."]
    if calib:
        L += ["", "**Qué tan confiable es** (la misma respuesta, rehecha en las semanas pasadas con el mismo adelanto):"]
        L += [f"- {k}: {v}" for k, v in calib.items()]
    return "\n".join(L)


def guardar(D, W, txt, carpeta=None, nombre=None):
    carpeta = carpeta or CARPETA                          # otra carpeta y nombre: prueba ciega (--origen)
    carpeta.mkdir(parents=True, exist_ok=True); base = carpeta / (nombre or f"semana_{W['lunes']}_{W['combo']}")
    if base.with_suffix(".json").exists():
        raise SystemExit(f"Ya existe {base.name}: una prediccion guardada no se rehace (es la prueba prospectiva).")
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=pr.RAIZ).stdout.strip()
    W = {**W, "creado": datetime.now().isoformat(timespec="seconds"), "commit": commit}
    base.with_suffix(".json").write_text(json.dumps(W, ensure_ascii=False, indent=1), encoding="utf-8")
    D.to_csv(base.with_suffix(".csv"), index=False, float_format="%.3f")
    base.with_suffix(".md").write_text(txt, encoding="utf-8")
    return base


def verificar(lunes, combo):
    base = CARPETA / f"semana_{lunes.date()}_{combo}"
    W = json.loads(base.with_suffix(".json").read_text(encoding="utf-8"))
    D = pd.read_csv(base.with_suffix(".csv"), parse_dates=["fecha"])
    y, _, F = datos()
    D["real"] = y.reindex(D.fecha).values
    franjas = [f for f in FRANJAS if f"{f}_q50" in D]        # las guardadas antes del 13-10 solo traen mañana y tarde
    for f in franjas: D[f"{f}_real"] = F[f].reindex(D.fecha).values
    hay = D.real.notna()
    if not hay.any():
        return f"Todavía no hay datos reales de la semana del {W['lunes']} (los datos llegan hasta {y.last_valid_index().date()})."
    D = D[hay]; sube = D.real > D.normal
    L = [f"# Verificación de la semana del {W['lunes']} (pronóstico del {W['creado']}, datos hasta {W['origen']})", "",
         "| Día | Esperado | Rango 80 % | Real | ¿En el rango? | P(sube) | ¿Subió? | ¿Acertó? | "
         + " | ".join(f"{f.capitalize()} pred./real" for f in franjas) + " |", "|" + "---|" * (8 + len(franjas))]
    for (_, r), s in zip(D.iterrows(), sube):
        ok = (r.p_sube > .5) == s
        L.append(f"| {DIAS[r.fecha.dayofweek]} {r.fecha.day} | {r.q50:.0f} | {r.q10:.0f}-{r.q90:.0f} | {r.real:.0f} | "
                 f"{'sí' if r.q10 <= r.real <= r.q90 else 'no'} | {100 * r.p_sube:.0f} % | {'sí' if s else 'no'} | "
                 f"{'✔' if ok else '✘'} | " + " | ".join(f"{r[f'{f}_q50']:.0f}/{r[f'{f}_real']:.0f}" for f in franjas) + " |")
    L += ["", f"- Días con dato real: {len(D)} de 7.",
          f"- Acierto en sube/baja: {((D.p_sube > .5) == sube).sum()} de {len(D)}.",
          f"- Error medio del día: {100 * np.mean(np.abs(D.q50 - D.real) / D.real):.1f} %."]
    if len(D) == 7:
        m = D.real.mean()
        L += [f"- Media real de la semana: {m:.1f}/día; pronosticada {W['media_q50']:.0f} (rango {W['media_q10']:.0f}-{W['media_q90']:.0f}): "
              f"{'dentro' if W['media_q10'] <= m <= W['media_q90'] else 'fuera'} del rango, error {100 * abs(W['media_q50'] - m) / m:.1f} %.",
              f"- ¿Quedó sobre lo normal? {'sí' if m > W['normal_semana'] else 'no'} (el modelo daba {100 * W['p_semana_sobre_normal']:.0f} %). "
              f"¿Aumentó frente a las 4 semanas previas? {'sí' if m > W['media_4_semanas_previas'] else 'no'} (daba {100 * W['p_semana_sobre_previas']:.0f} %)."]
    txt = "\n".join(L); (base.parent / f"{base.name}_verificacion.md").write_text(txt, encoding="utf-8")
    return txt


def validar(avisar=print, refit=4, combos=None, adelantos=(1, 15), archivo=None):
    """La respuesta en cada domingo de 2025 y 2026, con dos adelantos (semana siguiente y a 15 dias). Se reajusta
    cada 'refit' domingos; entre ajustes, los modelos predicen con los datos al dia del origen. Otros 'adelantos' y
    otro 'archivo': la curva por adelanto del cuaderno 26 (fila madurez_de_la_prediccion; pr.H >= adelanto + 6)."""
    y, cal, F = datos(); fin = y.last_valid_index()
    doms = pd.date_range("2024-12-29", fin, freq="W-SUN")
    filas, sem = [], []; t0 = time.time()
    for lead in adelantos:
        hs = list(range(lead, lead + 7))
        ors = [o for o in doms if o + pd.Timedelta(days=lead + 6) <= fin]
        cs = combos or [c for c in COMBOS if c not in DIAGNOSTICO]
        a = Ajuste(y, cal, sorted({m for c in cs for m in COMBOS[c]}))   # un solo SARIMAX y control para todos
        for i, o in enumerate(ors):
            if i % refit == 0: a.ajustar(o, hs)
            for c in cs:
                D, W = responder(y, cal, F, o, o + pd.Timedelta(days=lead), c, rho=.0, aj=a)
                D["real"] = y.reindex(D.fecha).values
                for f in FRANJAS: D[f"{f}_real"] = F[f].reindex(D.fecha).values
                filas.append(D.assign(origen=o, adelanto=lead, combo=c))
            if i % 10 == 0: avisar(f"  adelanto {lead}: {i + 1}/{len(ors)} ({time.time() - t0:.0f} s)")
    P = pd.concat(filas, ignore_index=True)
    f = archivo or CARPETA / "validacion_semanal.parquet"
    if f.exists(): P = pd.concat([pd.read_parquet(f).query("combo not in @cs"), P], ignore_index=True)
    P.to_parquet(f)
    return P


def resumen_validacion(P, y):
    """Metricas de la respuesta semanal. rho de la copula: correlacion entre dias consecutivos del error (PIT en
    escala normal), medida solo en 2025, por adelanto y combinacion."""
    P = P.dropna(subset=["real"]).copy()
    P["z"] = norm.ppf(pit(P[pr.QCOL].values, P.real.values))
    P["anio"] = np.where(P.origen < "2025-12-28", 2025, 2026)          # la semana del 29-dic-2025 cuenta en 2026
    rhos = {}
    for (c, lead), G in P[P.anio == 2025].groupby(["combo", "adelanto"]):
        Z = G.pivot_table(index="origen", columns="h", values="z")
        rhos[(c, lead)] = float(np.nanmean([Z.iloc[:, j].corr(Z.iloc[:, j + 1]) for j in range(Z.shape[1] - 1)]))
    filas = []
    for (c, lead, a), G in P.groupby(["combo", "adelanto", "anio"]):
        ws = []
        for o, g in G.groupby("origen"):
            if len(g) < 7: continue
            m = semana_agregada(g[pr.QCOL].values, rhos[(c, lead)])
            prev = float(y.loc[o - pd.Timedelta(days=27):o].mean())
            ws.append({"real": g.real.mean(), "q10": np.quantile(m, .1), "q50": np.quantile(m, .5), "q90": np.quantile(m, .9),
                       "p_normal": (m > g.normal.mean()).mean(), "sube_normal": g.real.mean() > g.normal.mean(),
                       "p_prev": (m > prev).mean(), "sube_prev": g.real.mean() > prev})
        Wd = pd.DataFrame(ws); sube = G.real > G.normal
        fila = {"combo": c, "adelanto (días)": lead, "año": a, "semanas": len(Wd), "rho (2025)": round(rhos[(c, lead)], 2),
                "error media semanal %": 100 * np.mean(np.abs(Wd.q50 - Wd.real) / Wd.real),
                "semanas con error < 5 %": 100 * np.mean(np.abs(Wd.q50 - Wd.real) / Wd.real < .05),
                "semana en rango 80 %": 100 * np.mean((Wd.real >= Wd.q10) & (Wd.real <= Wd.q90)),
                "acierta semana sobre lo normal %": 100 * np.mean((Wd.p_normal > .5) == Wd.sube_normal),
                "acierta semana aumenta vs 4 previas %": 100 * np.mean((Wd.p_prev > .5) == Wd.sube_prev),
                "acierta día sube/baja %": 100 * np.mean((G.p_sube > .5) == sube),
                "día en rango 80 %": 100 * np.mean((G.real >= G.q10) & (G.real <= G.q90)),
                "error del día %": 100 * np.mean(np.abs(G.q50 - G.real) / G.real)}
        for lo, hi in [(.55, .65), (.65, .75), (.75, 1.01)]:
            s = G[(G.p_sube >= lo) & (G.p_sube < hi)]
            fila[f"dice {int(lo * 100)}-{min(int(hi * 100), 100)} %: subió %"] = 100 * (s.real > s.normal).mean() if len(s) else np.nan
            fila[f"días {int(lo * 100)}"] = len(s)
        for f in [f for f in FRANJAS if f"{f}_q50" in G]:      # la validacion guardada antes del 13-10 trae 2 franjas
            fila[f"error {f} %"] = 100 * np.mean(np.abs(G[f"{f}_q50"] - G[f"{f}_real"]) / G[f"{f}_real"].clip(lower=1))
        filas.append(fila)
    return pd.DataFrame(filas).set_index(["combo", "adelanto (días)", "año"]), rhos



if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--semana", help="lunes de la semana a predecir (AAAA-MM-DD)")
    ap.add_argument("--combo", default="C0r", choices=list(COMBOS))   # C0r: fila motor_objetivo_relativo
    ap.add_argument("--verificar", help="lunes de una semana ya guardada")
    ap.add_argument("--validar", action="store_true")
    ap.add_argument("--combos", nargs="*", help="con --validar: solo estas combinaciones (se suman a lo ya validado)")
    ap.add_argument("--hmax", type=int, default=21, help="adelanto maximo en dias (21 por defecto; fila m3_semanal)")
    ap.add_argument("--origen", help="prueba ciega: ultimo dia que el modelo puede ver (el triage posterior se borra); se guarda en salidas/pronostico/prueba_ciega/")
    a = ap.parse_args()
    pr.H = a.hmax
    if a.validar:
        P = validar(avisar=lambda s: print(s, flush=True), combos=a.combos)
        T, rhos = resumen_validacion(P, datos()[0])
        T.to_csv(CARPETA / "validacion_semanal_resumen.csv"); print(T.round(1).T.to_string())
    elif a.verificar:
        print(verificar(pd.Timestamp(a.verificar), a.combo))
    elif a.semana:
        y, cal, F = datos()
        o = y.last_valid_index(); lunes = pd.Timestamp(a.semana)
        if a.origen:                                                 # prueba ciega: nada posterior al origen
            o = pd.Timestamp(a.origen); y.loc[o + pd.Timedelta(days=1):] = np.nan; F.loc[o + pd.Timedelta(days=1):] = np.nan
        R = CARPETA / "validacion_semanal_resumen.csv"
        lead = 1 if (lunes - o).days <= 7 else 15
        rho, calib = .5, None
        if R.exists() and (CARPETA / "validacion_semanal.parquet").exists():
            T, rhos = resumen_validacion(pd.read_parquet(CARPETA / "validacion_semanal.parquet"), y)
            rho = rhos[(a.combo, lead)]; t = T.loc[(a.combo, lead)]
            calib = {f"en {an}": (f"error de la media semanal {r['error media semanal %']:.1f} %; semana dentro del rango "
                                  f"{r['semana en rango 80 %']:.0f} %; acierto por día en sube/baja {r['acierta día sube/baja %']:.0f} %; "
                                  f"cuando dice 55-65 % subió el {r['dice 55-65 %: subió %']:.0f} %, cuando dice 65-75 % el "
                                  f"{r['dice 65-75 %: subió %']:.0f} %, y cuando dice más de 75 % el {r['dice 75-100 %: subió %']:.0f} %")
                     for an, r in t.iterrows() if not a.origen or an < o.year}   # en la prueba ciega, solo anos anteriores
        D, W = responder(y, cal, F, o, lunes, a.combo, rho)
        txt = texto(D, W, calib)
        base = (guardar(D, W, txt, pr.SALIDA / "prueba_ciega", f"{lunes.date()}_origen_{o.date()}_{a.combo}") if a.origen
                else guardar(D, W, txt))
        print(txt); print(f"\nGuardado en {base}.json / .csv / .md")
