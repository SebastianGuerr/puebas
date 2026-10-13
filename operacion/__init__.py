"""
La operación semanal: actualizar, reentrenar con receta fija, predecir, verificar lo ya predicho y avisar si algo
anda mal. Pensada para que corra sola en el hospital cuando ya no esté quien la construyó.

El porqué de cada pieza está en operacion/docs/OPERACION.md. Aquí solo el cómo.
"""
import json
import subprocess
import sys
import warnings
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "notebooks"))

import pronostico as pr          # noqa: E402
import semana as sm              # noqa: E402
import reparto as rp             # noqa: E402
import aseguradoras as ag        # noqa: E402
import madurez as md             # noqa: E402

CARPETA = RAIZ / "salidas" / "operacion"
CORRIDAS = CARPETA / "corridas"
VALIDADO = 28                        # hasta aquí llega la validación (cuaderno 26): más lejos es orientativo
HORIZONTE_MAX = 120                  # tope: hasta el 31 de diciembre del año en curso, nunca más de 120 días


def horizonte(o):
    """Días a predecir desde el origen: hasta el 31 de diciembre, entre VALIDADO y HORIZONTE_MAX."""
    return int(min(HORIZONTE_MAX, max(VALIDADO, (pd.Timestamp(f"{o.year}-12-31") - o).days)))
MODELO = "C0r"                       # receta fija: calendario, estación, nivel y memoria. Por qué: OPERACION.md
VENTANA_ASEG = "T4"                  # elegido en reparto_por_aseguradora
PERFIL = "P52"                       # elegido en reparto_del_dia
# Correlación entre días consecutivos del error, medida en la validación semanal de 2025 (semana.resumen_validacion,
# 2026-10-13). Sirve para el rango de la media de la semana. Adelanto 1 para la primera semana, 15 para las demás.
RHO = {("C0r", 1): .337, ("C0r", 15): .487, ("M3s", 1): .318, ("M3s", 15): .473}
# Semáforo (fijado el 2026-10-13 con la validación de 2025-2026: error del día 8-12 %, rango del 80 % entre 71 y 84 %)
DATOS_VERDE, DATOS_ROJO = 8, 21              # días de antigüedad del último dato
ERROR_VERDE, ERROR_ROJO = 12., 18.           # error medio del día, %, en los últimos 28 días verificados
RANGO_VERDE, RANGO_ROJO = 65., 50.           # % de días dentro del rango del 80 %, mismos días
NE_CAMBIO = .20                              # Nueva EPS: cambio de las 2 últimas semanas frente a las 8 anteriores
MIN_VERIFICADOS = 14


def _commit():
    r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=RAIZ)
    return r.stdout.strip() or "sin git"


def ultimo_dia_completo():
    """El día anterior al último con datos: la extracción corre de día y el último siempre queda a medias."""
    h = pd.read_parquet(RAIZ / "salidas/triage_horario.parquet", columns=["dia"])
    return pd.Timestamp(pd.to_datetime(h.dia).max()) - pd.Timedelta(days=1)


def extraer():
    """Baja los conteos agregados de SQL Server (solo en el equipo del hospital; protocolo en extraccion/)."""
    from extraccion.__main__ import main
    return main(["--series"])


def _preparar(o, n):
    pr.FIN = str(o.date()); pr.H = n
    rp.MALOS = rp.MALOS.union([o + pd.Timedelta(days=1)])          # el día a medias no entra a los perfiles


def _cadena(q, p24, a24, Pg, a_g, rng, n=4000):
    """Total del día -> 24 horas (perfil horario) -> jornadas -> aseguradoras dentro de cada jornada."""
    X = rp.simular(q, p24, a24, rng, n)
    J = np.stack([X[:, lo:hi + 1].sum(1) for lo, hi in rp.FRANJAS.values()], 1)
    G = np.zeros((n, len(rp.FRANJAS), len(ag.GRUPOS)), dtype=int)
    for j in range(len(rp.FRANJAS)):
        G[:, j] = rng.multinomial(J[:, j], rng.dirichlet(a_g * Pg[j] + 1e-6, size=n))
    return X, J, G


def predecir(modelo=MODELO, avisar=print):
    """Reentrena con todo lo conocido y predice hasta diciembre (horizonte). Devuelve (días, semanas, resumen)."""
    warnings.filterwarnings("ignore")
    o = ultimo_dia_completo(); n = horizonte(o); _preparar(o, n)
    y, cal, F = sm.datos()
    y = y.loc[:o].reindex(pd.date_range(y.index[0], o + pd.Timedelta(days=n)))
    hs = list(range(1, n + 1)); fechas = pd.date_range(o + pd.Timedelta(days=1), periods=n)
    avisar(f"Reentrenando {modelo} con datos hasta el {o.date()}...")
    aj = sm.Ajuste(y, cal, sm.COMBOS[modelo]); aj.ajustar(o, hs)
    Q, normal = aj.predecir(o, hs, sm.COMBOS[modelo])
    V = md.vara(y, [o] * len(fechas), fechas)
    pf = rp.Perfiles(rp.horas(), rp.festivos())
    dias_g, X_g = ag.conteos_grupo(); pa = ag.Proporciones(dias_g, X_g)
    rng = np.random.default_rng(0); filas = []
    for k, t in enumerate(fechas):
        p24, a24 = pf.perfil(PERFIL, o, t)
        pg, a_g = pa.dia(VENTANA_ASEG, o, t); Pg = pa.jornada(VENTANA_ASEG, o, t)
        X, J, G = _cadena(Q[k], p24, a24, Pg, a_g, rng)
        f = {"fecha": t, "adelanto": k + 1, "largo_plazo": k + 1 > VALIDADO, **{c: Q[k, j] for j, c in enumerate(pr.QCOL)},
             "habitual": V[k], "p_sube": float(pr.prob_sobre(Q[[k]], V[[k]])[0]),
             "control": normal[k, 0], "festivo": t in pf.fest}
        for j, jn in enumerate(rp.FRANJAS):
            f |= {f"{jn}_q10": np.quantile(J[:, j], .1), f"{jn}_q50": np.quantile(J[:, j], .5),
                  f"{jn}_q90": np.quantile(J[:, j], .9)}
        hq = np.quantile(X, [.1, .5, .9], axis=0)
        f |= {f"h{h:02d}_{c}": hq[i, h] for h in range(24) for i, c in enumerate(("q10", "q50", "q90"))}
        f |= {f"h{h:02d}_esperado": Q[k, 4] * p24[h] for h in range(24)}
        for b, inicios in rp.BLOQUES.items():
            esp = p24 * Q[k, 4]; s = max(inicios, key=lambda i: esp[i:i + 3].sum())
            f |= {f"pico_{b}": s, f"pico_{b}_por_hora": esp[s:s + 3].mean()}
        Gd = G.sum(1)
        for g, gn in enumerate(ag.GRUPOS):
            f |= {f"{gn}_q10": np.quantile(Gd[:, g], .1), f"{gn}_q50": np.quantile(Gd[:, g], .5),
                  f"{gn}_q90": np.quantile(Gd[:, g], .9)}
            for j, jn in enumerate(rp.FRANJAS):
                f[f"{gn}_{jn}_q50"] = np.quantile(G[:, j, g], .5)
        filas.append(f)
    D = pd.DataFrame(filas)
    W = semanas(D, modelo)
    R = {"origen": str(o.date()), "modelo": modelo, "horizonte": n, "validado_hasta": VALIDADO, "creado": datetime.now().isoformat(timespec="seconds"),
         "commit": _commit(), "perfil": PERFIL, "ventana_aseguradoras": VENTANA_ASEG,
         "ultimo_dato": str(o.date()), "antiguedad_dias": (pd.Timestamp(date.today()) - o).days}
    return D, W, R


def semanas(D, modelo):
    """Media diaria de cada semana (lunes a domingo) completa dentro del horizonte, con su rango (cópula de semana.py)."""
    filas = []
    for lunes in D.fecha[D.fecha.dt.dayofweek == 0]:
        g = D[(D.fecha >= lunes) & (D.fecha < lunes + pd.Timedelta(days=7))]
        if len(g) < 7: continue
        rho = RHO[(modelo, 1 if g.adelanto.min() <= 7 else 15)]
        m = sm.semana_agregada(np.sort(g[pr.QCOL].values, axis=1), rho)
        filas.append({"lunes": lunes, "media_q10": np.quantile(m, .1), "media_q50": np.quantile(m, .5),
                      "media_q90": np.quantile(m, .9), "habitual": g.habitual.mean(),
                      "p_sobre_habitual": float((m > g.habitual.mean()).mean())})
    return pd.DataFrame(filas)


def guardar(D, W, R):
    """Una corrida guardada no se rehace: es la prueba prospectiva."""
    c = CORRIDAS / f"{R['origen']}_{R['modelo']}"
    if (c / "resumen.json").exists():
        return c, False
    c.mkdir(parents=True, exist_ok=True)
    D.to_parquet(c / "dias.parquet", index=False); W.to_parquet(c / "semanas.parquet", index=False)
    (c / "resumen.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    return c, True


def reales():
    """Lo ocurrido, de los archivos de salidas/: total, jornadas y aseguradoras por día (sin el último día a medias)."""
    fin = ultimo_dia_completo()
    H = rp.horas().loc[:fin]
    R = pd.DataFrame({"real": H.sum(1)})
    for jn, (lo, hi) in rp.FRANJAS.items(): R[f"{jn}_real"] = H.loc[:, lo:hi].sum(1)
    dias_g, X_g = ag.conteos_grupo(); G = pd.DataFrame(X_g.sum(1), index=dias_g, columns=[f"{g}_real" for g in ag.GRUPOS])
    return R.join(G.loc[:fin])


def verificar():
    """Une cada corrida guardada con lo real, cuando ya existe. Escribe salidas/operacion/verificacion.parquet."""
    R = reales(); filas = []
    for c in sorted(CORRIDAS.glob("*/resumen.json")):
        meta = json.loads(c.read_text(encoding="utf-8")); D = pd.read_parquet(c.parent / "dias.parquet")
        D = D.merge(R, left_on="fecha", right_index=True, how="inner")
        if D.empty: continue
        creado = pd.Timestamp(meta["creado"]).normalize()
        # prospectiva: el día aún no había empezado al guardar. Los anteriores son ciegos (el modelo no los vio),
        # pero no prueban nada sobre el futuro: no cuentan en el semáforo.
        filas.append(D.assign(origen=meta["origen"], modelo=meta["modelo"], creado=meta["creado"],
                              prospectiva=D.fecha > creado))
    if not filas: return pd.DataFrame()
    V = pd.concat(filas, ignore_index=True)
    V["en_rango"] = V.real.between(V.q10, V.q90); V["error_pct"] = 100 * (V.q50 - V.real).abs() / V.real
    V["subio"] = V.real > V.habitual; V["acierta_sube"] = (V.p_sube > .5) == V.subio
    CARPETA.mkdir(parents=True, exist_ok=True); V.to_parquet(CARPETA / "verificacion.parquet", index=False)
    return V


def alerta_nueva_eps():
    """Cambio de nivel de Nueva EPS: media de las 2 últimas semanas conocidas frente a las 8 anteriores."""
    dias_g, X_g = ag.conteos_grupo(); fin = ultimo_dia_completo()
    ne = pd.Series(X_g.sum(1)[:, ag.GRUPOS.index("nueva_eps")], index=dias_g).loc[:fin]
    rec = ne.loc[fin - pd.Timedelta(days=13):].mean(); ant = ne.loc[fin - pd.Timedelta(days=69):fin - pd.Timedelta(days=14)].mean()
    return float(rec), float(ant), float(rec / ant - 1) if ant else np.nan


def semaforo(V=None):
    """Verde, amarillo o rojo, con el motivo de cada cosa. Se guarda en salidas/operacion/estado.json."""
    o = ultimo_dia_completo(); edad = (pd.Timestamp(date.today()) - o).days
    señales = []
    nivel = "verde" if edad <= DATOS_VERDE else "amarillo" if edad <= DATOS_ROJO else "rojo"
    señales.append({"que": "Datos", "nivel": nivel, "detalle": f"último día completo: {o.date()} (hace {edad} días)"})
    if V is None or V.empty:
        señales.append({"que": "Acierto reciente", "nivel": "gris", "detalle": "todavía no hay días predichos con dato real"})
    else:
        u = V[V.prospectiva].sort_values("origen").drop_duplicates("fecha", keep="first")   # la más antigua de cada día
        u = u[u.fecha > u.fecha.max() - pd.Timedelta(days=28)]
        if len(u) < MIN_VERIFICADOS:
            señales.append({"que": "Acierto reciente", "nivel": "gris", "detalle": f"solo {len(u)} días verificados"})
        else:
            e, r = u.error_pct.mean(), 100 * u.en_rango.mean()
            ne = "verde" if e <= ERROR_VERDE else "amarillo" if e <= ERROR_ROJO else "rojo"
            nr = "verde" if r >= RANGO_VERDE else "amarillo" if r >= RANGO_ROJO else "rojo"
            señales.append({"que": "Error del día", "nivel": ne, "detalle": f"{e:.1f} % en los últimos {len(u)} días verificados"})
            señales.append({"que": "Rango del 80 %", "nivel": nr, "detalle": f"{r:.0f} % de los días dentro del rango"})
    rec, ant, cambio = alerta_nueva_eps()
    nn = "amarillo" if abs(cambio) >= NE_CAMBIO else "verde"
    señales.append({"que": "Nueva EPS", "nivel": nn,
                    "detalle": f"{rec:.0f} por día en las 2 últimas semanas frente a {ant:.0f} en las 8 anteriores ({100 * cambio:+.0f} %)"
                               + ("; cambió de nivel: el total y el reparto por aseguradora pueden fallar" if nn != "verde" else "")})
    orden = {"gris": 0, "verde": 1, "amarillo": 2, "rojo": 3}
    general = max((s["nivel"] for s in señales), key=orden.get)
    E = {"general": general, "señales": señales, "calculado": datetime.now().isoformat(timespec="seconds")}
    CARPETA.mkdir(parents=True, exist_ok=True)
    (CARPETA / "estado.json").write_text(json.dumps(E, ensure_ascii=False, indent=1), encoding="utf-8")
    return E


def ultima_corrida(modelo=MODELO):
    cs = sorted(CORRIDAS.glob(f"*_{modelo}/resumen.json"))
    if not cs: return None
    c = cs[-1].parent
    return (pd.read_parquet(c / "dias.parquet"), pd.read_parquet(c / "semanas.parquet"),
            json.loads((c / "resumen.json").read_text(encoding="utf-8")))


def historial():
    """Cómo ha predicho, día por día: lo que el modelo habría dicho 15-21 días antes (el adelanto real de uso) frente a
    lo ocurrido, con jornadas y aseguradoras. Hasta la primera corrida sale de la validación semanal reconstruida
    (C0r, reajuste cada 4 domingos; notebooks/reparto.py y aseguradoras.py); después, de las corridas guardadas
    (la más antigua de cada día). Escribe salidas/operacion/historial.parquet."""
    llaves = ["fecha", "origen", "adelanto", "combo"]
    partes = []
    fr, fa = rp.CARPETA / "conteos.parquet", ag.CARPETA / "conteos.parquet"
    if fr.exists() and fa.exists():
        R = pd.read_parquet(fr); A = pd.read_parquet(fa)
        R = R[(R.combo == MODELO) & (R.adelanto == 15)]; A = A[(A.combo == MODELO) & (A.adelanto == 15)]
        cr = [c for c in R.columns if c.split("_")[0] in rp.FRANJAS and c.endswith(("_q10", "_q50", "_q90", "_real"))]
        ca = [c for c in A.columns if c.startswith(tuple(f"{g}_" for g in ag.GRUPOS))]
        B = R[llaves + pr.QCOL + ["real"] + cr].merge(A[llaves + ca], on=llaves, how="left")
        B["fuente"] = "reconstruida"; B["h"] = (B.fecha - pd.to_datetime(B.origen)).dt.days
        partes.append(B)
    V = verificar()
    if not V.empty:
        u = V.sort_values("origen").drop_duplicates("fecha", keep="first").copy()
        u["fuente"] = np.where(u.prospectiva, "prospectiva", "corrida (sin ver esos días)")
        u["h"] = u.adelanto; u["combo"] = u.modelo
        if partes: u = u[u.fecha > partes[0].fecha.max()]
        partes.append(u)
    if not partes: return pd.DataFrame()
    Hs = pd.concat(partes, ignore_index=True, sort=False).sort_values("fecha")
    Hs["origen"] = pd.to_datetime(Hs.origen)
    Hs["en_rango"] = Hs.real.between(Hs.q10, Hs.q90); Hs["error_pct"] = 100 * (Hs.q50 - Hs.real).abs() / Hs.real
    Hs.drop(columns=[c for c in Hs.columns if c.startswith("h") and c[1:3].isdigit()], errors="ignore", inplace=True)
    Hs.to_parquet(CARPETA / "historial.parquet", index=False)
    return Hs
