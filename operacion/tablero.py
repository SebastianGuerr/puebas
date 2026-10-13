"""
Tablero para urgencias: el calendario de lo que viene hasta diciembre (cuántos, en qué jornada, a qué hora se llena y
de qué aseguradora llegan) y el calendario de cómo ha predicho hasta hoy frente a lo ocurrido. Solo lee lo que dejó
`python -m operacion` en salidas/operacion/; no reentrena ni toca la base.

    streamlit run operacion/tablero.py
"""
import json
from datetime import date
from pathlib import Path

import altair as alt
import numpy as np
import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
CARPETA = RAIZ / "salidas" / "operacion"

JORNADAS = {"madrugada": "Madrugada (0-6 h)", "mañana": "Mañana (6-12 h)", "tarde": "Tarde (12-18 h)", "noche": "Noche (18-24 h)"}
GRUPOS = {"nueva_eps": "Nueva EPS", "sura_eps": "Sura EPS", "otra_eps": "Otras EPS", "regimen_especial": "Régimen especial",
          "soat": "SOAT (tránsito)", "arl": "ARL (laboral)", "prepagada": "Prepagada", "resto": "Otros"}
GRANDES = ["nueva_eps", "sura_eps"]          # los únicos con más de 10 por día: se informan también por jornada
DIAS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
MESES = ["", "ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGO = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
               "noviembre", "diciembre"]
DIAS_LARGO = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
ICONO = {"verde": "✅", "amarillo": "⚠️", "rojo": "⛔", "gris": "⚪"}
TEXTO_NIVEL = {"verde": "Confiable", "amarillo": "Con cuidado", "rojo": "No confiar por ahora", "gris": "Sin verificar"}
FUENTE = {"reconstruida": "reconstruida: el modelo solo vio datos de 15 a 21 días antes",
          "corrida (sin ver esos días)": "corrida guardada: el modelo no vio esos días",
          "prospectiva": "prospectiva: guardada antes de que ocurriera"}

st.set_page_config(page_title="Pronóstico de urgencias", page_icon="🏥", layout="wide")


def oscuro():
    try: return st.context.theme.type == "dark"
    except Exception: return False


def colores():
    """Divergente azul <-> rojo con gris en el centro (paleta de referencia de dataviz), y un tono para barras."""
    if oscuro():
        return dict(abajo=["#104281", "#1c5cab", "#3987e5"], medio="#383835", arriba=["#e66767", "#d03b3b", "#a82a2a"],
                    barra="#3987e5", barra_fuerte="#86b6ef", rango="#c3c2b7", real="#ffffff",
                    texto_fuerte="#ffffff", texto_suave="#ffffff")
    return dict(abajo=["#184f95", "#3987e5", "#9ec5f4"], medio="#f0efec", arriba=["#f2a3a2", "#e34948", "#a82a2a"],
                barra="#2a78d6", barra_fuerte="#104281", rango="#52514e", real="#0b0b0b",
                texto_fuerte="#ffffff", texto_suave="#0b0b0b")


@st.cache_data(ttl=600)
def cargar():
    cs = sorted((CARPETA / "corridas").glob("*/resumen.json"))
    if not cs: return None
    c = cs[-1].parent
    D = pd.read_parquet(c / "dias.parquet"); W = pd.read_parquet(c / "semanas.parquet")
    R = json.loads((c / "resumen.json").read_text(encoding="utf-8"))
    leer = lambda n: pd.read_parquet(CARPETA / n) if (CARPETA / n).exists() else pd.DataFrame()
    E = json.loads((CARPETA / "estado.json").read_text(encoding="utf-8")) if (CARPETA / "estado.json").exists() else None
    return D, W, R, E, leer("historial.parquet")


def fecha_larga(t):
    return f"{DIAS_LARGO[t.dayofweek]} {t.day} de {MESES_LARGO[t.month]}"


def ent(x):
    return f"{x:.0f}" if pd.notna(x) else "—"


# ------------------------------------------------------------------ cabecera
def cabecera(R, E):
    st.title("Pronóstico de urgencias: solicitudes de triage")
    o = pd.Timestamp(R["origen"])
    st.caption(f"Última predicción con datos hasta el {fecha_larga(o)} de {o.year} · modelo {R['modelo']} · reentrenado "
               f"el {R['creado'][:10]}. Las cifras son pacientes que piden triage. El rango es el del 80 %: 8 de cada 10 "
               "días el valor real cae dentro.")
    if E:
        nivel = E["general"]
        st.markdown(f"#### {ICONO[nivel]} Estado del pronóstico: **{TEXTO_NIVEL[nivel]}**")
        cols = st.columns(len(E["señales"]))
        for col, s in zip(cols, E["señales"]):
            col.markdown(f"{ICONO[s['nivel']]} **{s['que']}** · {TEXTO_NIVEL[s['nivel']].lower()}  \n"
                         f"<span style='font-size:0.85em'>{s['detalle']}</span>", unsafe_allow_html=True)


# ------------------------------------------------------------------ calendario genérico
def calendario(C, c, color_titulo, tooltip, clave_sel):
    """Cuadrícula semana x día. C trae: fecha, dif (color, -0,3 a 0,3), l1 (arriba), l2 (grande), l3 (abajo)."""
    C = C.copy()
    C["lunes"] = C.fecha - pd.to_timedelta(C.fecha.dt.dayofweek, unit="D")
    C["semana"] = C.lunes.map(lambda t: f"Semana del {t.day} {MESES[t.month]}")
    C["dia_sem"] = C.fecha.dt.dayofweek.map(dict(enumerate(DIAS)))
    C["clave"] = C.fecha.dt.strftime("%Y-%m-%d")
    C["fuerte"] = C.dif.abs() > .15
    orden_sem = list(dict.fromkeys(C.sort_values("fecha").semana))
    sel = alt.selection_point(fields=["clave"], name=clave_sel, on="click")
    base = alt.Chart(C).encode(
        x=alt.X("dia_sem:O", sort=DIAS, title=None, axis=alt.Axis(orient="top", labelAngle=0, ticks=False, domain=False)),
        y=alt.Y("semana:O", sort=orden_sem, title=None, axis=alt.Axis(ticks=False, domain=False)), tooltip=tooltip)
    escala = alt.Scale(domain=[-.3, -.15, -.05, 0, .05, .15, .3], range=c["abajo"] + [c["medio"]] + c["arriba"],
                       interpolate="lab")
    celdas = base.mark_rect(cornerRadius=4).encode(
        color=alt.Color("dif:Q", scale=escala, title=color_titulo,
                        legend=alt.Legend(format="+.0%", orient="bottom", gradientLength=320, titleLimit=420)),
        opacity=alt.condition(sel, alt.value(1), alt.value(.45))).add_params(sel)
    tc = alt.condition("datum.fuerte", alt.value(c["texto_fuerte"]), alt.value(c["texto_suave"]))
    capas = [celdas, base.mark_text(dy=-15, fontSize=11).encode(text="l1:N", color=tc),
             base.mark_text(dy=3, fontSize=19, fontWeight="bold").encode(text="l2:N", color=tc),
             base.mark_text(dy=21, fontSize=10).encode(text="l3:N", color=tc)]
    return alt.layer(*capas).properties(height=92 * len(orden_sem)).configure_view(stroke=None), C


def elegir_dia(ev, nombre, opciones, defecto):
    clave = None
    try:
        pts = ev.selection.get(nombre) if ev and ev.selection else None
        if pts: clave = pts[0]["clave"]
    except Exception:
        pass
    defecto = clave if clave in opciones else defecto
    return st.selectbox("Día", opciones, index=opciones.index(defecto), key=f"sel_{nombre}",
                        format_func=lambda k: fecha_larga(pd.Timestamp(k)).capitalize())


def elegir_mes(fechas, clave, defecto=None):
    meses = list(dict.fromkeys(fechas.dt.strftime("%Y-%m")))
    i = meses.index(defecto) if defecto in meses else 0
    return st.radio("Mes", meses, index=i, horizontal=True, key=clave,
                    format_func=lambda m: f"{MESES_LARGO[int(m[5:])].capitalize()} {m[:4]}")


# ------------------------------------------------------------------ próximos días
def proximos(D, W, R, c):
    st.markdown("**Color:** rojo = más pacientes que un día habitual de ese tipo; azul = menos; gris = lo de siempre. "
                "Cifra grande = pacientes esperados; abajo, el rango. Haga clic en un día para ver el detalle.")
    mes = elegir_mes(D.fecha, "mes_prox")
    M = D[D.fecha.dt.strftime("%Y-%m") == mes].copy()
    M["dif"] = (M.q50 / M.habitual - 1).clip(-.3, .3)
    M["l1"] = M.apply(lambda r: f"{r.fecha.day} {MESES[r.fecha.month]}" + (" · festivo" if r.festivo else ""), axis=1)
    M["l2"] = np.where(M.largo_plazo, "≈ ", "") + M.q50.map(ent); M["l3"] = M.q10.map(ent) + "-" + M.q90.map(ent)
    M["p"] = (100 * M.p_sube).round().astype(int).astype(str) + " %"
    tt = [alt.Tooltip("l1:N", title="Día"), alt.Tooltip("l2:N", title="Esperados"), alt.Tooltip("l3:N", title="Rango 80 %"),
          alt.Tooltip("habitual:Q", title="Día habitual", format=".0f"), alt.Tooltip("p:N", title="Prob. de más que lo habitual")]
    graf, C = calendario(M, c, "Frente a un día habitual", tt, "prox")
    ev = st.altair_chart(graf, width="stretch", on_select="rerun", key="cal_prox")
    if M.largo_plazo.any():
        st.caption(f"Los días con «≈» están a más de {R.get('validado_hasta', 28)} días de los datos. La "
                   "validación llega hasta 28 días: más lejos el nivel puede cambiar por cosas que nadie conoce de antemano "
                   "(por ejemplo, cambios en la atención de una aseguradora). Léalos como tendencia.")
    hoy = pd.Timestamp(date.today()); op_ = list(C.clave)
    elegido = elegir_dia(ev, "prox", op_, next((k for k in op_ if pd.Timestamp(k) >= hoy), op_[0]))
    detalle_futuro(D[D.fecha == pd.Timestamp(elegido)].iloc[0], c)
    st.divider(); semanas(W)


def detalle_futuro(r, c):
    t = r.fecha
    st.subheader(f"{fecha_larga(t).capitalize()} de {t.year}" + (" · festivo" if r.festivo else ""))
    if r.largo_plazo: st.warning("Día lejano (más de 28 días): léalo como tendencia, no como cifra exacta.")
    k = st.columns(4)
    k[0].metric("Pacientes esperados", ent(r.q50), help="La mitad de los días quedan por encima y la mitad por debajo")
    k[1].metric("Rango probable (80 %)", f"{ent(r.q10)} a {ent(r.q90)}")
    k[2].metric("Un día habitual", ent(r.habitual), f"{100 * (r.q50 / r.habitual - 1):+.0f} %", delta_color="off",
                help="Media del mismo día de la semana en las 8 semanas anteriores a los datos")
    k[3].metric("Probabilidad de más que lo habitual", f"{100 * r.p_sube:.0f} %")
    st.markdown("#### Cómo se reparte el día")
    filas = [{"Jornada": n, "Pacientes": ent(r[f"{j}_q50"]), "Rango 80 %": f"{ent(r[f'{j}_q10'])} a {ent(r[f'{j}_q90'])}",
              "Del día": f"{100 * r[f'{j}_q50'] / r.q50:.0f} %", "Por hora": f"~{r[f'{j}_q50'] / 6:.0f}"} for j, n in JORNADAS.items()]
    a, b = st.columns([5, 6])
    a.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    pm, pt = int(r.pico_mañana), int(r.pico_tarde)
    a.markdown(f"**Más saturado:** de **{pm} a {pm + 3} h** (~{r.pico_mañana_por_hora:.0f} por hora) y de "
               f"**{pt} a {pt + 3} h** (~{r.pico_tarde_por_hora:.0f} por hora).  \n"
               f"**Más tranquilo:** la madrugada, con ~{r.madrugada_q50:.0f} pacientes entre las 0 y las 6 h.")
    a.caption("Las horas de más demanda son un rasgo estable del servicio, no un aviso de algo especial ese día.")
    H = pd.DataFrame({"hora": range(24), "esperado": [r[f"h{h:02d}_esperado"] for h in range(24)],
                      "q10": [r[f"h{h:02d}_q10"] for h in range(24)], "q90": [r[f"h{h:02d}_q90"] for h in range(24)]})
    H["pico"] = H.hora.isin(list(range(pm, pm + 3)) + list(range(pt, pt + 3)))
    H["etiqueta"] = H.hora.map(lambda h: f"{h}:00 a {h + 1}:00")
    barras = alt.Chart(H).mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=14).encode(
        x=alt.X("hora:O", title="Hora del día"), y=alt.Y("esperado:Q", title="Pacientes por hora"),
        color=alt.condition("datum.pico", alt.value(c["barra_fuerte"]), alt.value(c["barra"])),
        tooltip=[alt.Tooltip("etiqueta:N", title="Hora"), alt.Tooltip("esperado:Q", title="Esperados", format=".1f"),
                 alt.Tooltip("q10:Q", title="Mínimo probable", format=".0f"), alt.Tooltip("q90:Q", title="Máximo probable", format=".0f")])
    rango = alt.Chart(H).mark_rule(strokeWidth=2, opacity=.6, color=c["rango"]).encode(x="hora:O", y="q10:Q", y2="q90:Q")
    b.altair_chart((barras + rango).properties(height=260, title="Llegadas por hora (barra = esperado, línea = rango 80 %; oscuro = horas pico)"),
                   width="stretch")
    st.markdown("#### De qué aseguradora llegan")
    a, b = st.columns([6, 5])
    a.altair_chart(barras_grupos(r, c), width="stretch")
    J = pd.DataFrame([{"Aseguradora": GRUPOS[g], **{JORNADAS[j].split(" ")[0]: ent(r[f"{g}_{j}_q50"]) for j in JORNADAS}}
                      for g in GRANDES])
    b.markdown("**Las dos grandes, por jornada** (pacientes esperados):")
    b.dataframe(J, hide_index=True, width="stretch")
    b.caption("Sura se predice bien. **Nueva EPS falla cuando cambia la atención de sus afiliados** (suspensiones o "
              "reanudaciones): si el estado muestra un cambio de Nueva EPS, tome sus cifras con cuidado. Las "
              "aseguradoras pequeñas traen pocos pacientes al día; se informan con su rango.")


def barras_grupos(r, c, real=False):
    G = pd.DataFrame([{"grupo": GRUPOS[g], "esperado": r[f"{g}_q50"], "q10": r[f"{g}_q10"], "q90": r[f"{g}_q90"],
                       "real": r.get(f"{g}_real", np.nan)} for g in GRUPOS])
    G["rango"] = G.q10.map(ent) + " a " + G.q90.map(ent)
    orden = list(G.sort_values("esperado", ascending=False).grupo)
    y = alt.Y("grupo:N", sort=orden, title=None)
    tt = [alt.Tooltip("grupo:N", title="Aseguradora"), alt.Tooltip("esperado:Q", title="Predichos", format=".0f"),
          alt.Tooltip("rango:N", title="Rango 80 %")] + ([alt.Tooltip("real:Q", title="Reales", format=".0f")] if real else [])
    capas = [alt.Chart(G).mark_bar(cornerRadiusTopRight=4, cornerRadiusBottomRight=4, size=16, color=c["barra"]).encode(
                 y=y, x=alt.X("esperado:Q", title="Pacientes en el día"), tooltip=tt),
             alt.Chart(G).mark_rule(strokeWidth=2, opacity=.6, color=c["rango"]).encode(y=y, x="q10:Q", x2="q90:Q")]
    if real:
        capas.append(alt.Chart(G).mark_point(shape="diamond", size=110, filled=True, color=c["real"]).encode(y=y, x="real:Q", tooltip=tt))
    else:
        capas.append(alt.Chart(G).mark_text(align="left", dx=6, fontSize=11).encode(y=y, x="q90:Q", text="rango:N"))
    return alt.layer(*capas).properties(height=290)


def semanas(W):
    if W.empty: return
    st.markdown("#### Semanas completas")
    fin = W.lunes + pd.Timedelta(days=6)
    S = pd.DataFrame({"Semana": [f"del {a.day} {MESES[a.month]} al {b.day} {MESES[b.month]}" for a, b in zip(W.lunes, fin)],
                      "Media por día": W.media_q50.round().astype(int),
                      "Rango 80 %": W.media_q10.map(ent) + " a " + W.media_q90.map(ent),
                      "Semana habitual": W.habitual.round().astype(int),
                      "Prob. de más que lo habitual": (100 * W.p_sobre_habitual).round().astype(int).astype(str) + " %"})
    st.dataframe(S, hide_index=True, width="stretch")


# ------------------------------------------------------------------ cómo ha predicho
def como_ha_predicho(Hs, c):
    if Hs.empty:
        st.info("Todavía no hay historial. Corra `python -m operacion`."); return
    st.markdown("Cada día muestra **lo que pasó** (cifra grande) y **lo que se predijo 15 a 21 días antes** (abajo), que es "
                "con cuánta anticipación se usa el pronóstico. **Color:** rojo = llegaron más de los predichos; azul = "
                "menos; gris = acertó. ✓ = el día cayó dentro del rango anunciado.")
    anios = sorted(Hs.fecha.dt.year.unique())
    anio = st.radio("Año", anios, index=len(anios) - 1, horizontal=True, key="anio_hist")
    A = Hs[Hs.fecha.dt.year == anio]
    resumen_anio(A, anio, c)
    mes = elegir_mes(A.fecha, "mes_hist", defecto=A.fecha.max().strftime("%Y-%m"))
    M = A[A.fecha.dt.strftime("%Y-%m") == mes].copy()
    M["dif"] = (M.real / M.q50 - 1).clip(-.3, .3)
    M["l1"] = M.fecha.map(lambda t: f"{t.day} {MESES[t.month]}") + np.where(M.en_rango, "  ✓", "  ✗")
    M["l2"] = M.real.map(ent); M["l3"] = "pred. " + M.q50.map(ent) + " (" + M.q10.map(ent) + "-" + M.q90.map(ent) + ")"
    M["err"] = M.error_pct.round(1).astype(str) + " %"; M["fte"] = M.fuente.map(FUENTE)
    tt = [alt.Tooltip("l1:N", title="Día"), alt.Tooltip("l2:N", title="Real"), alt.Tooltip("l3:N", title="Predicho"),
          alt.Tooltip("err:N", title="Error"), alt.Tooltip("fte:N", title="Predicción")]
    k = st.columns(3)
    k[0].metric(f"Error medio de {MESES_LARGO[int(mes[5:])]}", f"{M.error_pct.mean():.1f} %")
    k[1].metric("Días dentro del rango", f"{int(M.en_rango.sum())} de {len(M)}")
    k[2].metric("Media real por día / predicha", f"{M.real.mean():.0f} / {M.q50.mean():.0f}")
    graf, C = calendario(M, c, "Real frente a lo predicho", tt, "hist")
    ev = st.altair_chart(graf, width="stretch", on_select="rerun", key="cal_hist")
    op_ = list(C.clave)
    elegido = elegir_dia(ev, "hist", op_, op_[-1])
    detalle_pasado(M[M.fecha == pd.Timestamp(elegido)].iloc[0], c)


def resumen_anio(A, anio, c):
    m = A.groupby(A.fecha.dt.month).agg(error=("error_pct", "mean"), rango=("en_rango", "mean"), real=("real", "mean"), pred=("q50", "mean"))
    st.markdown(f"**{anio}:** error medio del día **{A.error_pct.mean():.1f} %**; **{100 * A.en_rango.mean():.0f} %** de los "
                f"días dentro del rango ({len(A)} días).")
    S = A.set_index("fecha")[["q10", "q50", "q90", "real"]].resample("W-MON", label="left").mean().reset_index()
    banda = alt.Chart(S).mark_area(opacity=.22, color=c["barra"]).encode(
        x=alt.X("fecha:T", title=None, axis=alt.Axis(format="%b")), y=alt.Y("q10:Q", title="Media por día de la semana"), y2="q90:Q")
    linea = alt.Chart(S).mark_line(strokeWidth=2, color=c["barra"]).encode(x="fecha:T", y="q50:Q")
    pts = alt.Chart(S).mark_point(filled=True, size=40, color=c["real"]).encode(
        x="fecha:T", y="real:Q", tooltip=[alt.Tooltip("fecha:T", title="Semana del", format="%d %b"),
                                         alt.Tooltip("q50:Q", title="Predicho", format=".0f"), alt.Tooltip("real:Q", title="Real", format=".0f")])
    st.altair_chart((banda + linea + pts).properties(height=200, title="Semana a semana: banda y línea = predicho 15-21 días antes; puntos = real"),
                    width="stretch")
    tabla = pd.DataFrame({"Mes": [MESES_LARGO[i].capitalize() for i in m.index], "Error medio": m.error.map(lambda v: f"{v:.1f} %"),
                          "Días dentro del rango": (100 * m.rango).map(lambda v: f"{v:.0f} %"),
                          "Media real": m.real.round().astype(int), "Media predicha": m.pred.round().astype(int)})
    with st.expander("Resumen por mes"):
        st.dataframe(tabla, hide_index=True, width="stretch")


def detalle_pasado(r, c):
    t = r.fecha
    st.subheader(f"{fecha_larga(t).capitalize()} de {t.year}")
    st.caption(f"Predicción {FUENTE.get(r.fuente, r.fuente)} (hecha {int(r.h)} días antes).")
    k = st.columns(3)
    k[0].metric("Llegaron", ent(r.real))
    k[1].metric("Se predijo", ent(r.q50), f"{r.real - r.q50:+.0f} pacientes", delta_color="off")
    k[2].metric("Rango anunciado (80 %)", f"{ent(r.q10)} a {ent(r.q90)}", "dentro" if r.en_rango else "fuera", delta_color="off")
    a, b = st.columns([5, 6])
    filas = []
    for j, n in JORNADAS.items():
        if f"{j}_q50" not in r or pd.isna(r[f"{j}_q50"]): continue
        filas.append({"Jornada": n, "Predicho": ent(r[f"{j}_q50"]), "Rango 80 %": f"{ent(r[f'{j}_q10'])} a {ent(r[f'{j}_q90'])}",
                      "Real": ent(r[f"{j}_real"]), "¿Dentro?": "sí" if r[f"{j}_q10"] <= r[f"{j}_real"] <= r[f"{j}_q90"] else "no"})
    a.markdown("**Por jornada**"); a.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    if "nueva_eps_q50" in r and pd.notna(r["nueva_eps_q50"]):
        b.markdown("**Por aseguradora** (barra = predicho, línea = rango, rombo = real)")
        b.altair_chart(barras_grupos(r, c, real=True), width="stretch")


# ------------------------------------------------------------------ confiabilidad
def confiabilidad(Hs):
    st.markdown("#### Qué tan cerca ha estado de la realidad")
    if Hs.empty: st.info("Sin historial todavía."); return
    def fila(G, nombre):
        out = {"Periodo": nombre, "Días": len(G), "Error del día": f"{G.error_pct.mean():.1f} %",
               "Día dentro del rango": f"{100 * G.en_rango.mean():.0f} %"}
        for j in ("mañana", "tarde", "noche"):
            e = (100 * (G[f"{j}_q50"] - G[f"{j}_real"]).abs() / G[f"{j}_real"].clip(lower=1)).mean()
            out[f"Error {j}"] = f"{e:.0f} %"
        for g in GRANDES:
            e = (100 * (G[f"{g}_q50"] - G[f"{g}_real"]).abs() / G[f"{g}_real"].clip(lower=1)).mean()
            out[f"Error {GRUPOS[g]}"] = f"{e:.0f} %"
        return out
    filas = [fila(Hs[(Hs.fuente == "reconstruida") & (Hs.fecha.dt.year == a)], f"{a}, reconstruido a 15-21 días")
             for a in sorted(Hs.fecha.dt.year.unique()) if ((Hs.fuente == "reconstruida") & (Hs.fecha.dt.year == a)).any()]
    nr = Hs[Hs.fuente != "reconstruida"]
    if len(nr): filas.append(fila(nr, f"{nr.fecha.min().day} {MESES[nr.fecha.min().month]} a {nr.fecha.max().day} "
                                      f"{MESES[nr.fecha.max().month]} {nr.fecha.max().year}, corridas guardadas"))
    st.dataframe(pd.DataFrame(filas), hide_index=True, width="stretch")
    st.markdown("""
**Cómo leerlo**
- **El total del día** se equivoca alrededor de un 10 % cuando se predice con 15 a 21 días de anticipación. Con
  175 pacientes, eso son unos 18 de más o de menos.
- **Por jornada** el error es mayor (14-17 %) porque cada jornada tiene menos pacientes y el azar de las llegadas pesa
  más. Ningún método puede repartir mejor el día: lo que queda es azar.
- **Sura** se predice bien. **Nueva EPS** falla en los meses en que cambia la atención de sus afiliados (noviembre de
  2025, marzo y julio de 2026): es la causa principal de los días fuera del rango.
- **Las horas de más demanda** (9-12 h y 14-17 h) aciertan el 86 % y el 71-80 % de los días.
- **Lo más lejano a 28 días** no está validado: se muestra como tendencia.
""")


def main():
    datos = cargar()
    if datos is None:
        st.error("No hay ninguna corrida guardada. Corra `python -m operacion` primero."); return
    D, W, R, E, Hs = datos
    c = colores()
    cabecera(R, E)
    st.divider()
    t1, t2, t3 = st.tabs(["Próximos días", "Cómo ha predicho", "Qué tan confiable es"])
    with t1: proximos(D, W, R, c)
    with t2: como_ha_predicho(Hs, c)
    with t3: confiabilidad(Hs)


main()
