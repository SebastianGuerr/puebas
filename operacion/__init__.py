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
import red as rd                 # noqa: E402
import resiliencia as rs         # noqa: E402
import indices as ix             # noqa: E402

CARPETA = RAIZ / "salidas" / "operacion"
CORRIDAS = CARPETA / "corridas"
VALIDADO = 28                        # hasta aquí llega la validación (cuaderno 26): más lejos es orientativo
HORIZONTE_MAX = 120                  # tope: hasta el 31 de diciembre del año en curso, nunca más de 120 días


def horizonte(o):
    """Días a predecir desde el origen: hasta el 31 de diciembre, entre VALIDADO y HORIZONTE_MAX."""
    return int(min(HORIZONTE_MAX, max(VALIDADO, (pd.Timestamp(f"{o.year}-12-31") - o).days)))
# Principal y comparación (fila operacion_m3s_contexto_automatico, 2026-10-15). M3s = C0r + los mecanismos externos de
# notebooks/mecanismos.py, con el contexto que mantiene `python -m contexto`; C0r corre cada semana al lado como vara.
# Regla de vuelta atrás: si a los 84 días comunes (y cada 84 más) M3s tiene más error del día que C0r, MODELO = "C0r".
MODELO = "M3s"
COMPARACION = "C0r"
CRITERIO_ADELANTO = (15, 21)                 # el adelanto real de uso: la base se actualiza una vez por semana
REGLA_DIAS = 84                              # N = 12 semanas de días comunes (por qué: la fila del preregistro)
FRESCURA = RAIZ / "salidas" / "contexto" / "frescura.csv"     # la escribe `python -m contexto`
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
USAR_RED = True                              # ajuste por la red (fila red_de_urgencias_v2: pasó su regla el 2026-10-14; la v1 no)
RANGO_QUIEBRE = True                         # rango del total más ancho tras un quiebre (fila resiliencia, W: entró; R no)


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
    ix.FIN_RED = str(o.date())       # la red de M3s lee el triage hasta el origen y no más (antes: fija en el 20-09)
    rp.MALOS = rp.MALOS.union([o + pd.Timedelta(days=1)])          # el día a medias no entra a los perfiles


def _texto_episodio(e):
    fin = f" hasta el {e.fecha_fin.date()}" if pd.notna(e.fecha_fin) else ""
    return f"{e.prestador} · {e.eps} · {e.tipo.replace('_', ' ')} desde el {e.fecha_inicio.date()}{fin}"


def _dias(o, fechas, Q, tau, usar_red=None):
    """Lo de cada día predicho a partir de los cuantiles del total del modelo (Q, sin red): total corregido por la red
    con lo sabido en tau, horas, jornadas, aseguradoras por día, jornada y hora (fila red_de_urgencias)."""
    usar_red = USAR_RED if usar_red is None else usar_red
    pf = rp.Perfiles(rp.horas(), rp.festivos())
    dias_g, X_g = ag.conteos_grupo(); pa = ag.Proporciones(dias_g, X_g)
    R_red = rd.registro() if rd.REGISTRO.exists() else None
    ef = None
    if usar_red and R_red is not None:
        if rd.INGRESOS.exists(): ef = rd.EfectoV2(R_red, dias_g, X_g)
        else: print("Sin salidas/ingresos_entidad.parquet: el ajuste por la red no se aplica (python -m extraccion --ingresos).")
    rng = np.random.default_rng(0); filas = []
    for k, t in enumerate(fechas):
        p24, a24 = pf.perfil(PERFIL, o, t)
        pg, a_g = pa.dia(VENTANA_ASEG, o, t); Ph = rd.por_hora(dias_g, X_g, o, pa.jornada(VENTANA_ASEG, o, t))
        lf = ef.log_factor(o, t, tau, rng)[0] if ef else np.zeros(rd.NSIM)
        T, Xh, Gh = rd.cadena(Q[k], p24, a24, pg, a_g, Ph, lf, rng)
        f = rd.resumen_dia(T, Xh, Gh)
        if not np.any(lf): f |= {c: Q[k, j] for j, c in enumerate(pr.QCOL)}      # sin ajuste: los cuantiles del modelo
        f |= {"fecha": t, "festivo": t in pf.fest, "f_red": float(np.exp(np.median(lf))),
              **{f"{c}_sin_red": Q[k, j] for j, c in enumerate(pr.QCOL)}}
        if R_red is not None:
            f["red_eventos"] = " | ".join(_texto_episodio(e) for e in rd.en_curso(R_red, t, tau).itertuples())
        hq = np.quantile(Xh, [.1, .5, .9], axis=0)
        f |= {f"h{h:02d}_{c}": hq[i, h] for h in range(24) for i, c in enumerate(("q10", "q50", "q90"))}
        f |= {f"h{h:02d}_esperado": f["q50"] * p24[h] for h in range(24)}
        for b, inicios in rp.BLOQUES.items():
            esp = p24 * f["q50"]; s = max(inicios, key=lambda i: esp[i:i + 3].sum())
            f |= {f"pico_{b}": s, f"pico_{b}_por_hora": esp[s:s + 3].mean()}
        filas.append(f)
    D = pd.DataFrame(filas)
    quiebre = bool(RANGO_QUIEBRE and rs.Quiebre(dias_g, X_g).total(o))
    if quiebre:                                          # fila resiliencia, W: q' = q50 (q / q50)^1,5
        D["quiebre_total"] = True; D = rs.ensanchar(D)
    b = ef.estimar(o, tau)[0] if ef else np.zeros(len(rd.EfectoV2.coeficientes))
    info = {"usada": bool(ef), "version": "red_de_urgencias_v2", "episodios": 0 if R_red is None else len(R_red),
            "conocido_al": str(pd.Timestamp(tau).date()),
            "efectos": {v: round(float(x), 4) for v, x in zip(rd.EfectoV2.coeficientes, b)},
            "ses_atiende_nueva_eps": None if ef is None else ef.abierto(o), "quiebre_total": quiebre}
    return D, info


def carpeta_corrida(o, modelo):
    return CORRIDAS / f"{pd.Timestamp(o).date()}_{modelo}"


def existe(o, modelo):
    """¿Ya hay una corrida guardada con este origen y este modelo? Si la hay no se reentrena: no se rehace."""
    return (carpeta_corrida(o, modelo) / "resumen.json").exists()


def predecir(modelo=MODELO, avisar=print):
    """Reentrena con todo lo conocido y predice hasta diciembre (horizonte). Devuelve (días, semanas, resumen)."""
    warnings.filterwarnings("ignore")
    t0 = datetime.now()
    o = ultimo_dia_completo(); n = horizonte(o); _preparar(o, n)
    y, cal, F = sm.datos()
    y = y.loc[:o].reindex(pd.date_range(y.index[0], o + pd.Timedelta(days=n)))
    hs = list(range(1, n + 1)); fechas = pd.date_range(o + pd.Timedelta(days=1), periods=n)
    avisar(f"Reentrenando {modelo} con datos hasta el {o.date()}...")
    aj = sm.Ajuste(y, cal, sm.COMBOS[modelo]); aj.ajustar(o, hs)
    Q, normal = aj.predecir(o, hs, sm.COMBOS[modelo])
    hoy = pd.Timestamp(date.today())
    D, info = _dias(o, fechas, Q, hoy)
    D = _completar(D, y, o, normal)
    W = semanas(D, modelo)
    R = {"origen": str(o.date()), "modelo": modelo, "papel": "principal" if modelo == MODELO else "comparación",
         "horizonte": n, "validado_hasta": VALIDADO, "creado": datetime.now().isoformat(timespec="seconds"),
         "segundos": round((datetime.now() - t0).total_seconds()),
         "commit": _commit(), "perfil": PERFIL, "ventana_aseguradoras": VENTANA_ASEG,
         "ultimo_dato": str(o.date()), "antiguedad_dias": (hoy - o).days, "red": info}
    return D, W, R


def correr(modelos=None, avisar=print):
    """El principal y la comparación, uno detrás de otro (una sola cosa pesada a la vez). Una corrida que ya existe
    con el mismo origen no se reentrena. Devuelve [(modelo, carpeta, nueva)]."""
    hechas = []
    for m in modelos or (MODELO, COMPARACION):
        o = ultimo_dia_completo()
        if existe(o, m):
            avisar(f"{m}: ya existía la corrida con origen {o.date()} (no se rehace)")
            hechas.append((m, carpeta_corrida(o, m), False)); continue
        D, W, R = predecir(m, avisar)
        c, nueva = guardar(D, W, R)
        avisar(f"{m}: {'guardada' if nueva else 'ya existía (no se rehace)'} en {c} ({R['segundos']} s)")
        hechas.append((m, c, nueva))
    return hechas


def _completar(D, y, o, normal=None):
    """Adelanto, vara del día habitual y probabilidad de pasarla, con los cuantiles ya corregidos."""
    D = D.copy()
    D["adelanto"] = (D.fecha - o).dt.days; D["largo_plazo"] = D.adelanto > VALIDADO
    D["habitual"] = md.vara(y, [o] * len(D), D.fecha)
    D["p_sube"] = pr.prob_sobre(np.sort(D[pr.QCOL].values, 1), D.habitual.values)
    if normal is not None: D["control"] = normal[:, 0]
    return D


def ajustar(modelo=MODELO, avisar=print):
    """Reaplica el registro de la red de hoy a la última corrida, SIN reentrenar: el uso diario de la fila
    red_de_urgencias_v2. Guarda corridas/<corrida>/ajustes/<fecha_hora>.parquet; ninguno se rehace."""
    warnings.filterwarnings("ignore")
    u = ultima_corrida(modelo)
    if u is None: raise SystemExit("No hay corrida guardada: corra primero `python -m operacion`.")
    D0, _, R0 = u; o = pd.Timestamp(R0["origen"]); hoy = pd.Timestamp(date.today())
    sin_red = [f"{q}_sin_red" for q in pr.QCOL]
    if sin_red[0] not in D0: D0 = D0.assign(**{f"{q}_sin_red": D0[q] for q in pr.QCOL})   # corrida anterior: sin red
    c = CORRIDAS / f"{R0['origen']}_{R0['modelo']}" / "ajustes"; destino = c / f"{datetime.now():%Y-%m-%d_%H%M}.parquet"
    if destino.exists(): return destino, False
    D0 = D0[D0.fecha > hoy - pd.Timedelta(days=1)]
    Q = D0[sin_red].values
    _preparar(o, int(R0["horizonte"]))
    D, info = _dias(o, pd.DatetimeIndex(D0.fecha), Q, hoy)
    y = sm.datos()[0].loc[:o]
    D = _completar(D, y.reindex(pd.date_range(y.index[0], D.fecha.max())), o)
    c.mkdir(parents=True, exist_ok=True); D.to_parquet(destino, index=False)
    destino.with_suffix(".json").write_text(json.dumps(info, ensure_ascii=False, indent=1), encoding="utf-8")
    avisar(f"Ajuste por la red con el registro al {hoy.date()}: {info}")
    return destino, True


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


def comparacion(V=None):
    """Fila operacion_m3s_contexto_automatico: días comunes (principal y comparación desde el mismo origen, adelanto
    15-21, guardados antes de que empezara el día, con dato real) y la regla de vuelta atrás. Devuelve (C, resumen):
    C = un día por fila con q10/q50/q90 de cada modelo; resumen = n, error y rango de cada uno y las evaluaciones."""
    V = verificar() if V is None else V
    vacio = {"n": 0, "evaluaciones": [], "vuelve": False}
    if V is None or V.empty: return pd.DataFrame(), vacio
    a, b = CRITERIO_ADELANTO
    S = V[V.prospectiva & V.adelanto.between(a, b) & V.real.notna()]
    S = S.sort_values("adelanto").drop_duplicates(["fecha", "modelo"], keep="first")   # varias: la de menor adelanto
    k = ["fecha", "origen", "adelanto", "real", "q10", "q50", "q90"]
    P, Cm = S[S.modelo == MODELO][k], S[S.modelo == COMPARACION][k]
    C = P.merge(Cm.drop(columns=["adelanto", "real"]), on=["fecha", "origen"], suffixes=(f"_{MODELO}", f"_{COMPARACION}"))
    if C.empty: return C, vacio
    C = C.sort_values("fecha").reset_index(drop=True)
    for m in (MODELO, COMPARACION):
        C[f"error_{m}"] = 100 * (C[f"q50_{m}"] - C.real).abs() / C.real
        C[f"en_rango_{m}"] = C.real.between(C[f"q10_{m}"], C[f"q90_{m}"])
    mide = lambda G: {f"{q}_{m}": float(G[f"{q}_{m}"].mean() * (100 if q == "en_rango" else 1))
                      for m in (MODELO, COMPARACION) for q in ("error", "en_rango")}
    ev = []
    for corte in range(REGLA_DIAS, len(C) + 1, REGLA_DIAS):        # acumulado: 84, 168, ... días comunes
        G = C.iloc[:corte]; x = mide(G)
        ev.append({"dias": corte, "hasta": str(G.fecha.max().date()), **x,
                   "vuelve": x[f"error_{MODELO}"] > x[f"error_{COMPARACION}"]})
    return C, {"n": len(C), **mide(C), "evaluaciones": ev, "vuelve": bool(ev and ev[-1]["vuelve"])}


def _si(x):
    return str(x).strip().lower() in {"si", "sí", "true", "1", "yes", "verdadero"}


def contexto_externo(archivo=None):
    """Señal «Contexto externo»: la frescura de las fuentes que deja `python -m contexto` (salidas/contexto/frescura.csv,
    columnas fuente, archivo, ultimo_dato, ultima_corrida, resultado, dias_atraso, atraso_tolerado, nivel, usa_m3s,
    detalle). Rojo si alguna fuente que usa M3s está en rojo; amarillo si alguna está en amarillo o si una que M3s no
    usa está en rojo; gris sin el archivo."""
    f = Path(archivo) if archivo else FRESCURA
    s = {"que": "Contexto externo", "en_general": True}
    if not f.exists():
        return s | {"nivel": "gris", "detalle": "sin orquestador de contexto (no existe salidas/contexto/frescura.csv)"}
    try:
        F = pd.read_csv(f, dtype=str, encoding="utf-8").fillna("")
        F["nivel"] = F.nivel.str.strip().str.lower(); F["m3s"] = F.usa_m3s.map(_si)
    except Exception as e:                   # un archivo roto no tumba la operación: se dice
        return s | {"nivel": "amarillo", "detalle": f"no se pudo leer {f.name}: {e}"}
    rojo_m3s = F[F.m3s & (F.nivel == "rojo")]; amarillas = F[F.nivel == "amarillo"]; rojo_otras = F[~F.m3s & (F.nivel == "rojo")]
    nivel = "rojo" if len(rojo_m3s) else "amarillo" if len(amarillas) or len(rojo_otras) else "verde" if len(F) else "gris"
    def lista(G):
        return ", ".join(f"{r.fuente} ({r.dias_atraso} días de atraso)" if str(r.dias_atraso).strip() else str(r.fuente)
                         for r in G.itertuples())
    partes = []
    if len(rojo_m3s): partes.append(f"en rojo y las usa M3s: {lista(rojo_m3s)}")
    if len(rojo_otras): partes.append(f"en rojo, no las usa M3s: {lista(rojo_otras)}")
    if len(amarillas): partes.append(f"en amarillo: {lista(amarillas)}")
    ultima = F.ultima_corrida[F.ultima_corrida.str.strip() != ""].max() if "ultima_corrida" in F else ""
    detalle = "; ".join(partes) if partes else f"las {len(F)} fuentes al día"
    return s | {"nivel": nivel, "detalle": detalle + (f" (última actualización: {ultima})" if ultima else ""),
                "fuentes_con_problema": [str(x) for x in pd.concat([rojo_m3s, rojo_otras, amarillas]).fuente]}


def señal_comparacion(V):
    """Señal «Comparación»: principal frente a la vara en los días comunes. No entra en el estado general que ve
    urgencias (es para quien mantiene el sistema), ni siquiera en rojo, que es cuando la regla manda volver a C0r."""
    C, r = comparacion(V)
    s = {"que": "Comparación", "en_general": False}
    if r["n"] < MIN_VERIFICADOS:
        return s | {"nivel": "gris", "detalle": f"{r['n']} días comunes de {MODELO} y {COMPARACION} a {CRITERIO_ADELANTO[0]}-"
                                                f"{CRITERIO_ADELANTO[1]} días (hacen falta {MIN_VERIFICADOS})"}
    em, ec = r[f"error_{MODELO}"], r[f"error_{COMPARACION}"]
    rm, rc = r[f"en_rango_{MODELO}"], r[f"en_rango_{COMPARACION}"]
    txt = (f"{r['n']} días comunes: error del día {em:.1f} % ({MODELO}) frente a {ec:.1f} % ({COMPARACION}); "
           f"en rango {rm:.0f} % frente a {rc:.0f} %")
    if r["vuelve"]:
        e = r["evaluaciones"][-1]
        return s | {"nivel": "rojo",
                    "detalle": txt + f". La regla preregistrada, evaluada con {e['dias']} días, manda volver a "
                                     f"{COMPARACION}: poner MODELO = \"{COMPARACION}\" y COMPARACION = \"{MODELO}\" en "
                                     "operacion/__init__.py y anotarlo en docs/CONTEXTO.md"}
    falta = REGLA_DIAS - r["n"] % REGLA_DIAS
    nivel = "verde" if em <= ec else "amarillo"
    return s | {"nivel": nivel, "detalle": txt + f"; la regla se evalúa dentro de {falta} días comunes"}


def semaforo(V=None):
    """Verde, amarillo o rojo, con el motivo de cada cosa. Se guarda en salidas/operacion/estado.json. El error y el
    rango son los del modelo principal; la comparación y el contexto externo van como señales aparte."""
    o = ultimo_dia_completo(); edad = (pd.Timestamp(date.today()) - o).days
    señales = []
    nivel = "verde" if edad <= DATOS_VERDE else "amarillo" if edad <= DATOS_ROJO else "rojo"
    señales.append({"que": "Datos", "nivel": nivel, "detalle": f"último día completo: {o.date()} (hace {edad} días)"})
    Vp = None if V is None or V.empty else V[V.modelo == MODELO]
    if Vp is None or Vp.empty:
        señales.append({"que": "Acierto reciente", "nivel": "gris", "detalle": f"todavía no hay días predichos por {MODELO} con dato real"})
    else:
        u = Vp[Vp.prospectiva].sort_values("origen").drop_duplicates("fecha", keep="first")   # la más antigua de cada día
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
    señales.append(contexto_externo())
    señales.append(señal_comparacion(V))
    orden = {"gris": 0, "verde": 1, "amarillo": 2, "rojo": 3}
    general = max((s["nivel"] for s in señales if s.get("en_general", True)), key=orden.get)
    E = {"general": general, "principal": MODELO, "comparacion": COMPARACION, "señales": señales,
         "calculado": datetime.now().isoformat(timespec="seconds")}
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
    """Cómo ha predicho, día por día: lo que cada modelo habría dicho 15-21 días antes (el adelanto real de uso) frente
    a lo ocurrido, con jornadas y aseguradoras. Una fila por día y modelo (columna combo): el principal y la
    comparación. Hasta la primera corrida guardada de cada modelo sale de la validación semanal reconstruida (reajuste
    cada 4 domingos; notebooks/reparto.py y aseguradoras.py), si existe para ese modelo a adelanto 15; si no existe no
    se inventa: ese modelo solo tiene las corridas guardadas. Las columnas _red (la red v2 y el rango W,
    resiliencia/conteos_v2AW.parquet) solo existen para los modelos con los que se reconstruyó. Después, las corridas
    guardadas (la más antigua de cada día). Escribe salidas/operacion/historial.parquet."""
    llaves = ["fecha", "origen", "adelanto", "combo"]
    partes = []
    fr, fa = rp.CARPETA / "conteos.parquet", ag.CARPETA / "conteos.parquet"
    fe = rs.CARPETA / "conteos_v2AW.parquet"             # la misma predicción con la red (v2A) y el rango W
    if fr.exists() and fa.exists():
        R0 = pd.read_parquet(fr); A0 = pd.read_parquet(fa); E0 = pd.read_parquet(fe) if fe.exists() else None
        for combo in (MODELO, COMPARACION):
            R = R0[(R0.combo == combo) & (R0.adelanto == 15)]; A = A0[(A0.combo == combo) & (A0.adelanto == 15)]
            if R.empty: continue
            cr = [c for c in R.columns if c.split("_")[0] in rp.FRANJAS and c.endswith(("_q10", "_q50", "_q90", "_real"))]
            ca = [c for c in A.columns if c.startswith(tuple(f"{g}_" for g in ag.GRUPOS))]
            B = R[llaves + pr.QCOL + ["real"] + cr].merge(A[llaves + ca], on=llaves, how="left")
            B["fuente"] = "reconstruida"; B["h"] = (B.fecha - pd.to_datetime(B.origen)).dt.days
            if E0 is not None:
                E = E0[(E0.variante == "v2AW") & (E0.adelanto == 15) & (E0.combo == combo)]
                if len(E):
                    cols = (pr.QCOL + [f"{g}_{s}" for g in ag.GRUPOS for s in ("q10", "q50", "q90")]
                            + [f"{j}_{s}" for j in rp.FRANJAS for s in ("q10", "q50", "q90")] + ["log_f"])
                    B = B.merge(E[llaves + cols].rename(columns={c: f"{c}_red" for c in cols}), on=llaves, how="left")
            partes.append(B)
    V = verificar()
    if not V.empty:
        u = V.sort_values("origen").drop_duplicates(["fecha", "modelo"], keep="first").copy()
        u["fuente"] = np.where(u.prospectiva, "prospectiva", "corrida (sin ver esos días)")
        u["h"] = u.adelanto; u["combo"] = u.modelo
        fin = {p.combo.iloc[0]: p.fecha.max() for p in partes}
        u = u[u.fecha > u.combo.map(fin).fillna(pd.Timestamp.min)]
        partes.append(u)
    if not partes: return pd.DataFrame()
    Hs = pd.concat(partes, ignore_index=True, sort=False).sort_values(["fecha", "combo"]).copy()
    Hs["origen"] = pd.to_datetime(Hs.origen)
    Hs["papel"] = np.where(Hs.combo == MODELO, "principal", np.where(Hs.combo == COMPARACION, "comparación", "anterior"))
    Hs["en_rango"] = Hs.real.between(Hs.q10, Hs.q90); Hs["error_pct"] = 100 * (Hs.q50 - Hs.real).abs() / Hs.real
    if "q50_red" in Hs:
        Hs = Hs.copy()
        Hs["en_rango_red"] = Hs.real.between(Hs.q10_red, Hs.q90_red).where(Hs.q50_red.notna())
        Hs["error_pct_red"] = 100 * (Hs.q50_red - Hs.real).abs() / Hs.real
    Hs.drop(columns=[c for c in Hs.columns if c.startswith("h") and c[1:3].isdigit()], errors="ignore", inplace=True)
    Hs.to_parquet(CARPETA / "historial.parquet", index=False)
    return Hs
