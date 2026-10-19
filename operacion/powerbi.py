"""
Lo mismo que muestra el tablero (operacion/tablero.py), en tablas largas para Power BI: una fila por día, por día ×
jornada, día × hora, día × aseguradora... Solo lee salidas/operacion/; no reentrena ni toca la base. Escribe CSV en
salidas/powerbi/, que es la carpeta que lee prediccion.pbip (parámetro CarpetaDatos).

    python -m operacion.powerbi

Por qué y con qué límites: operacion/docs/POWERBI.md.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "salidas" / "operacion"
DESTINO = RAIZ / "salidas" / "powerbi"

JORNADAS = {"madrugada": ("Madrugada (0-6 h)", 1), "mañana": ("Mañana (6-12 h)", 2),
            "tarde": ("Tarde (12-18 h)", 3), "noche": ("Noche (18-24 h)", 4)}
GRUPOS = {"nueva_eps": "Nueva EPS", "sura_eps": "Sura EPS", "otra_eps": "Otras EPS", "regimen_especial": "Régimen especial",
          "soat": "SOAT (tránsito)", "arl": "ARL (laboral)", "prepagada": "Prepagada", "resto": "Otros"}
GRANDES = ["nueva_eps", "sura_eps"]
TEXTO_NIVEL = {"verde": "Confiable", "amarillo": "Con cuidado", "rojo": "No confiar por ahora", "gris": "Sin verificar"}
ORDEN_NIVEL = {"verde": 1, "amarillo": 2, "rojo": 3, "gris": 4}


def corrida(modelo):
    """La última corrida de ese modelo con el último ajuste por la red encima: lo mismo que tablero._corrida."""
    cs = sorted((CARPETA / "corridas").glob(f"*_{modelo}/resumen.json"))
    if not cs: return None
    c = cs[-1].parent
    D = pd.read_parquet(c / "dias.parquet"); W = pd.read_parquet(c / "semanas.parquet")
    R = json.loads((c / "resumen.json").read_text(encoding="utf-8"))
    aj = sorted((c / "ajustes").glob("*.parquet")) if (c / "ajustes").exists() else []
    if aj:
        A = pd.read_parquet(aj[-1]); D = pd.concat([D[D.fecha < A.fecha.min()], A], ignore_index=True)
        R = {**R, "ajuste_red": aj[-1].stem}
    return D, W, R


def _col(D, c):
    return D[c] if c in D else np.nan


def dias(D, R, papel):
    T = pd.DataFrame({"fecha": D.fecha, "modelo": R["modelo"], "papel": papel,
                      "q10": D.q10, "q25": D.q25, "q50": D.q50, "q75": D.q75, "q90": D.q90,
                      "habitual": D.habitual, "p_sube": D.p_sube, "festivo": D.festivo.astype(bool),
                      "largo_plazo": D.largo_plazo.astype(bool), "adelanto": D.adelanto,
                      "pico_manana": _col(D, "pico_mañana"), "pico_manana_por_hora": _col(D, "pico_mañana_por_hora"),
                      "pico_tarde": _col(D, "pico_tarde"), "pico_tarde_por_hora": _col(D, "pico_tarde_por_hora"),
                      "f_red": _col(D, "f_red"), "q50_sin_red": _col(D, "q50_sin_red")})
    T["dif_habitual"] = T.q50 / T.habitual - 1
    return T


def jornadas(D, R):
    return pd.concat([pd.DataFrame({"fecha": D.fecha, "modelo": R["modelo"], "jornada": nombre, "orden": orden,
                                    "q10": D[f"{j}_q10"], "q50": D[f"{j}_q50"], "q90": D[f"{j}_q90"]})
                      for j, (nombre, orden) in JORNADAS.items()], ignore_index=True)


def horas(D, R):
    return pd.concat([pd.DataFrame({"fecha": D.fecha, "modelo": R["modelo"], "hora": h,
                                    "q10": D[f"h{h:02d}_q10"], "q50": D[f"h{h:02d}_q50"], "q90": D[f"h{h:02d}_q90"],
                                    "esperado": D[f"h{h:02d}_esperado"]}) for h in range(24)], ignore_index=True)


def aseguradoras(D, R):
    filas = []
    for g, nombre in GRUPOS.items():
        T = pd.DataFrame({"fecha": D.fecha, "modelo": R["modelo"], "aseguradora": nombre,
                          "q10": D[f"{g}_q10"], "q50": D[f"{g}_q50"], "q90": D[f"{g}_q90"]})
        for j in JORNADAS: T[f"{j.replace('ñ', 'n')}_q50"] = _col(D, f"{g}_{j}_q50")
        filas.append(T)
    return pd.concat(filas, ignore_index=True)


def aseguradoras_hora(D, R):
    """Llegadas esperadas por hora y aseguradora; con menos de 1 por hora se informa la probabilidad de al menos una
    (Poisson), como en el tablero. Rango del 80 % solo para las dos grandes."""
    filas = []
    for g, nombre in GRUPOS.items():
        for h in range(24):
            esp = D[f"{g}_h{h:02d}_esp"]
            filas.append(pd.DataFrame({"fecha": D.fecha, "modelo": R["modelo"], "aseguradora": nombre, "hora": h,
                                       "esperado": esp, "prob_al_menos_uno": 1 - np.exp(-esp),
                                       "q10": _col(D, f"{g}_h{h:02d}_q10"), "q90": _col(D, f"{g}_h{h:02d}_q90")}))
    return pd.concat(filas, ignore_index=True)


def red(D):
    """Un episodio de la red de urgencias por fila y día (el tablero los separa por « | »)."""
    if "red_eventos" not in D: return pd.DataFrame(columns=["fecha", "lugar", "aseguradora", "episodio"])
    filas = []
    for t, s in zip(D.fecha, D.red_eventos.fillna("")):
        for e in (x for x in str(s).split(" | ") if x):
            p = [x.strip() for x in e.split(" · ")]
            filas.append({"fecha": t, "lugar": p[0], "aseguradora": p[1] if len(p) > 1 else "",
                          "episodio": " · ".join(p[2:]) if len(p) > 2 else e})
    return pd.DataFrame(filas)


def semanas(W, R):
    return pd.DataFrame({"lunes": W.lunes, "modelo": R["modelo"], "media_q10": W.media_q10, "media_q50": W.media_q50,
                         "media_q90": W.media_q90, "habitual": W.habitual, "p_sobre_habitual": W.p_sobre_habitual})


def historial(H):
    """Cómo ha predicho: una fila por día y modelo, la predicción de 15-21 días antes frente a lo real. Las columnas
    _red son la misma predicción corregida por la red de urgencias, donde existe."""
    if H.empty: return H, H
    if "combo" not in H: H = H.assign(combo="C0r")
    base = ["fecha", "combo", "fuente", "origen", "adelanto", "q10", "q50", "q90", "real", "en_rango", "error_pct",
            "subio", "acierta_sube", "q10_red", "q50_red", "q90_red", "en_rango_red", "error_pct_red", "habitual"]
    T = H[[c for c in base if c in H]].rename(columns={"combo": "modelo"})
    for c in ("en_rango", "subio", "acierta_sube", "en_rango_red"):
        if c in T: T[c] = T[c].astype("boolean")
    filas = []                                         # jornadas y aseguradoras grandes, para el error por pieza
    for j, (nombre, orden) in JORNADAS.items():
        filas.append(pd.DataFrame({"fecha": H.fecha, "modelo": H.combo, "fuente": H.fuente, "tipo": "Jornada",
                                   "pieza": nombre, "orden": orden, "q50": H[f"{j}_q50"], "real": H[f"{j}_real"]}))
    for i, g in enumerate(GRANDES):
        filas.append(pd.DataFrame({"fecha": H.fecha, "modelo": H.combo, "fuente": H.fuente, "tipo": "Aseguradora",
                                   "pieza": GRUPOS[g], "orden": 10 + i, "q50": H[f"{g}_q50"], "real": H[f"{g}_real"]}))
    P = pd.concat(filas, ignore_index=True)
    P["error_pct"] = 100 * (P.q50 - P.real).abs() / P.real.clip(lower=1)
    return T, P


def historial_aseguradoras(H):
    """Rango y real de cada aseguradora en el historial (15-21 días antes): con esto el tablero dice con qué
    frecuencia acierta el rango de cada una, medido y no supuesto."""
    if H.empty: return pd.DataFrame(columns=["fecha", "modelo", "aseguradora", "q10", "q50", "q90", "real"])
    if "combo" not in H: H = H.assign(combo="C0r")
    return pd.concat([pd.DataFrame({"fecha": H.fecha, "modelo": H.combo, "aseguradora": nombre, "q10": H[f"{g}_q10"],
                                    "q50": H[f"{g}_q50"], "q90": H[f"{g}_q90"], "real": H[f"{g}_real"]})
                      for g, nombre in GRUPOS.items() if f"{g}_q10" in H], ignore_index=True).dropna(subset=["real"])


def verificacion_horas():
    """Rango por hora de los días ya verificados frente a las llegadas reales por hora (salidas/triage_horario.parquet).
    Una hora sin filas en el horario es una hora sin llegadas: cuenta como 0."""
    V = pd.read_parquet(CARPETA / "verificacion.parquet") if (CARPETA / "verificacion.parquet").exists() else pd.DataFrame()
    f = RAIZ / "salidas" / "triage_horario.parquet"
    if V.empty or not f.exists() or "h00_q10" not in V:
        return pd.DataFrame(columns=["fecha", "modelo", "hora", "q10", "q90", "real"])
    T = pd.read_parquet(f).rename(columns={"dia": "fecha", "triages": "real"})
    L = pd.concat([pd.DataFrame({"fecha": V.fecha, "modelo": V.modelo, "hora": h, "q10": V[f"h{h:02d}_q10"],
                                 "q90": V[f"h{h:02d}_q90"]}) for h in range(24)], ignore_index=True)
    L = L.merge(T[["fecha", "hora", "real"]], on=["fecha", "hora"], how="left")
    L["real"] = L.real.fillna(0)
    return L


def estado(E, R, Rc):
    if not E: return pd.DataFrame(columns=["orden", "senal", "nivel", "estado", "en_general", "detalle"]), pd.DataFrame()
    S = pd.DataFrame([{"orden": i, "senal": s["que"], "nivel": s["nivel"], "estado": TEXTO_NIVEL[s["nivel"]],
                       "orden_nivel": ORDEN_NIVEL[s["nivel"]], "en_general": bool(s.get("en_general", True)),
                       "detalle": s["detalle"]} for i, s in enumerate(E["señales"])])
    C = pd.DataFrame([{"principal": R["modelo"], "comparacion": Rc["modelo"] if Rc else "",
                       "origen": R["origen"], "creado": R["creado"][:19], "ajuste_red": R.get("ajuste_red", ""),
                       "validado_hasta": R.get("validado_hasta", 28), "estado_general": TEXTO_NIVEL[E["general"]],
                       "nivel_general": E["general"], "semaforo_calculado": E.get("calculado", ""),
                       "exportado": pd.Timestamp.now().strftime("%Y-%m-%dT%H:%M:%S")}])
    return S, C


def escribir(T, nombre):
    """CSV con punto decimal y fechas ISO: la carga de Power BI fija la cultura en-US y no depende del equipo."""
    T.to_csv(DESTINO / f"{nombre}.csv", index=False, encoding="utf-8", date_format="%Y-%m-%d", float_format="%.4f")
    return f"{nombre}: {len(T)} filas"


def main():
    E = json.loads((CARPETA / "estado.json").read_text(encoding="utf-8")) if (CARPETA / "estado.json").exists() else None
    principal = (E or {}).get("principal", "M3s"); comp = (E or {}).get("comparacion", "C0r")
    P = corrida(principal)
    if P is None:
        print("No hay corrida guardada: corra python -m operacion primero."); return 1
    D, W, R = P
    Cp = corrida(comp) if comp != R["modelo"] else None
    if Cp is not None and Cp[2]["origen"] != R["origen"]: Cp = None    # el tablero solo compara corridas del mismo origen
    DESTINO.mkdir(parents=True, exist_ok=True)
    pares = [(D, R, "principal")] + ([(Cp[0], Cp[2], "comparación")] if Cp else [])
    H = pd.read_parquet(CARPETA / "historial.parquet") if (CARPETA / "historial.parquet").exists() else pd.DataFrame()
    Hd, Hp = historial(H)
    S, C = estado(E, R, Cp[2] if Cp else None)
    hechos = [
        escribir(pd.concat([dias(d, r, p) for d, r, p in pares], ignore_index=True), "pronostico_dia"),
        escribir(pd.concat([jornadas(d, r) for d, r, _ in pares], ignore_index=True), "pronostico_jornada"),
        escribir(pd.concat([horas(d, r) for d, r, _ in pares], ignore_index=True), "pronostico_hora"),
        escribir(pd.concat([aseguradoras(d, r) for d, r, _ in pares], ignore_index=True), "pronostico_aseguradora"),
        escribir(aseguradoras_hora(D, R), "pronostico_aseguradora_hora"),
        escribir(red(D), "red_urgencias"),
        escribir(pd.concat([semanas(w, r) for (_, r, _), w in zip(pares, [W] + ([Cp[1]] if Cp else []))],
                           ignore_index=True), "pronostico_semana"),
        escribir(Hd, "historial"), escribir(Hp, "historial_piezas"),
        escribir(historial_aseguradoras(H), "historial_aseguradora"), escribir(verificacion_horas(), "verificacion_hora"),
        escribir(S, "semaforo"), escribir(C, "corrida"),
    ]
    print(f"Power BI: {R['modelo']} con datos hasta {R['origen']}" + (f", comparación {Cp[2]['modelo']}" if Cp else "")
          + f" → {DESTINO}")
    for h in hechos: print("  " + h)
    return 0


if __name__ == "__main__":
    sys.exit(main())
