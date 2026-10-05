"""
Indices compartidos de los cuadernos 17-22: clima completo, familias de enfermedad y red de salud.
Una sola definicion para la exploracion (17-21) y para el reentrenamiento (22), para que el modelo use
exactamente lo que se exploro. Filas de patrones/datos/variables.csv: clima_completo, familias_enfermedad,
panel_eps.

    from indices import clima_semanal, indices_clima, familias_enfermedad, red_diaria

Todas las referencias (climatologias, medias, desviaciones, componentes principales) se ajustan con datos
hasta REF_FIN = 2024-12-31: 2025 se reserva para elegir y 2026 para probar.
"""
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
REF_FIN = "2024-12-31"
NIVELES = ["temp", "tmin", "tmax", "lluvia", "sol", "nubes", "rocio", "humedad", "vpd", "radiacion", "viento"]


def semana(s, como="mean"):
    """Agrega a semana epidemiologica (domingo a sabado), con el indice en el domingo de inicio."""
    r = getattr(s.resample("W-SAT"), como)(); r.index = r.index - pd.Timedelta(days=6)
    return r


# ---------------------------------------------------------------- clima (cuaderno 17)
def clima_diario():
    return pd.read_csv(RAIZ / "calendarios/clima_completo.csv.gz", index_col=0, parse_dates=True)


def clima_semanal():
    cc = clima_diario(); F = {}
    for n in NIVELES:
        for k in ("7d", "28d", "cambio"): F[f"{n}_{k}"] = semana(cc[f"{n}_{k}"])
    F["dias_en_racha_seca"] = semana(cc.dias_en_racha_seca, "max"); F["dias_de_sol"] = semana(cc.dias_de_sol, "max")
    F["dias_desde_semana_muy_lluviosa"] = semana(cc.dias_desde_semana_muy_lluviosa, "min")
    F["extremos_frio_7d"] = semana(cc.extremos_frio_7d, "max"); F["seco_a_lluvioso"] = semana(cc.seco_a_lluvioso, "max")
    return pd.DataFrame(F)


def _pca(X, k, nombre):
    from sklearn.decomposition import PCA
    Z = X.loc[:REF_FIN].dropna(); mu, sd = Z.mean(), Z.std()
    p = PCA(k, random_state=0).fit((Z - mu) / sd)
    ok = X.notna().all(axis=1)
    S = pd.DataFrame(p.transform(((X[ok] - mu) / sd)), index=X.index[ok], columns=[f"{nombre}_{i + 1}" for i in range(k)])
    return S.reindex(X.index), pd.DataFrame(p.components_.T, index=X.columns, columns=S.columns), p.explained_variance_ratio_


def indices_clima(diario=False):
    """4 indices de estado (niveles de 7 dias) y 3 de cambio brusco, ajustados con 2010-2024. Semanales, o
    diarios si diario=True (los mismos pesos aplicados a las variables diarias)."""
    cc = clima_diario()
    est = cc[[f"{n}_7d" for n in NIVELES]]; cam = cc[[f"{n}_cambio" for n in NIVELES]]
    if not diario:
        est = est.resample("W-SAT").mean(); est.index -= pd.Timedelta(days=6)
        cam = cam.resample("W-SAT").mean(); cam.index -= pd.Timedelta(days=6)
    S1, L1, v1 = _pca(est, 4, "estado"); S2, L2, v2 = _pca(cam, 3, "cambio")
    out = S1.join(S2)
    out["racha_seca"] = (cc.dias_en_racha_seca if diario else semana(cc.dias_en_racha_seca, "max")).reindex(out.index)
    out["dias_desde_semana_muy_lluviosa"] = (cc.dias_desde_semana_muy_lluviosa if diario else semana(cc.dias_desde_semana_muy_lluviosa, "min")).reindex(out.index)
    return out


# ---------------------------------------------------------------- familias de enfermedad (cuaderno 19)
FAMILIAS = {
    "respiratoria": [("995", "consultas_ira_total"), ("995", "consultas_ira_0_4"), ("995", "consultas_ira_60_mas"), ("995", "hospitalizaciones_irag_total")],
    "digestiva": [("998", "casos_eda_total"), ("998", "casos_eda_0_4")],
    "violencias_y_agresiones": [("875", None), ("300", None)],
    "salud_mental_e_intoxicaciones": [("356", None), ("365", None)],
    "materno_perinatal": [("549", None)],
    "inmunoprevenibles": [("831", None)],
}
EN_2026 = {"respiratoria": "sí (Power BI 995, ~1 semana)", "digestiva": "NO: solo microdatos (~8 meses)",
           "violencias_y_agresiones": "sí (Power BI 006)", "salud_mental_e_intoxicaciones": "sí (Power BI 006)",
           "materno_perinatal": "sí (Power BI 006)", "inmunoprevenibles": "sí (Power BI 006)"}


def series_sivigila():
    """Series semanales de Manizales de los microdatos (2012-2025), una columna por (evento, variable)."""
    v = pd.read_csv(RAIZ / "calendarios/vigilancia_sivigila.csv.gz", parse_dates=["fecha_inicio_semana"])
    v = v[v.ambito.eq("manizales")]
    e = pd.read_csv(RAIZ / "calendarios/vigilancia_sivigila_eventos.csv.gz", parse_dates=["fecha_inicio_semana"])
    e = e[e.ambito.eq("manizales") & e.variable.eq("casos_notificacion")]
    S = {}
    for fam, miembros in FAMILIAS.items():
        for ev, var in miembros:
            if var:
                s = v[v.evento.eq(int(ev)) & v.variable.eq(var)]
            else:
                s = e[e.evento.eq(int(ev))]
            s = s.drop_duplicates("fecha_inicio_semana").set_index("fecha_inicio_semana").valor.astype(float).sort_index()
            S[f"{ev}_{var or 'casos'}"] = s
    S = pd.DataFrame(S)
    S.loc[S.index == pd.Timestamp("2025-12-28"), [c for c in S if c.startswith("998")]] = np.nan   # SE53-2025 del 998: error de la fuente
    return S


def anomalia_operativa(s):
    """log contra la media de las 52 semanas previas: lo que se sabria esa semana, sin mirar el ano entero."""
    l = np.log1p(s); return l - l.shift(1).rolling(52, min_periods=26).mean()


def familias_enfermedad():
    """Indice semanal por familia = promedio de las anomalias operativas estandarizadas (desviacion de <= 2024)."""
    S = series_sivigila().apply(anomalia_operativa)
    Z = (S - S.loc[:REF_FIN].mean()) / S.loc[:REF_FIN].std()
    out = pd.DataFrame(index=Z.index)
    for fam, miembros in FAMILIAS.items():
        cols = [f"{ev}_{var or 'casos'}" for ev, var in miembros]
        out[fam] = Z[cols].mean(axis=1, skipna=True).where(Z[cols].notna().any(axis=1))
    return out


# ---------------------------------------------------------------- red de salud (cuaderno 18)
def grupo_asegurador(e):
    e = str(e).upper()
    reglas = [("Nueva EPS", r"NUEVA (EMPRESA PROMOTORA|EPS)(?!.*COMPLEMENT)"), ("SURA", r"^EPS SURA|EPS SURAMERICANA"),
              ("Salud Total", r"SALUD TOTAL"), ("Sanitas", r"^EPS SANITAS|SANITAS EPS"), ("Asmet", r"ASMET"),
              ("Magisterio (FOMAG)", r"FIDEICOMISOS|FIDUPREVISORA|MAGISTERIO"), ("Medimás", r"MEDIMAS"),
              ("SOAT y accidentes", r"SEGUROS|MUNDIAL|PREVISORA S\.A\. COMPA|SOAT|ARL|POSITIVA|LIBERTY|ALLIANZ|AXA"),
              ("Territorial (no asegurados)", r"TERRITORIAL|SECRETARIA|MUNICIPIO|DEPARTAMENTO"), ("Particulares", r"PARTICULAR"),
              ("Prepagadas", r"PREPAGADA|COLSANITAS|COLMEDICA|MEDISANITAS")]
    return next((g for g, p in reglas if re.search(p, e)), "Otras")


def resoluciones_nueva_eps():
    import glob
    f = sorted(glob.glob(str(RAIZ / "calendarios/capturas/medidas/*/CTFT21-Listado*EPS.csv")))[-1]
    m = pd.read_csv(f); col = next(c for c in m.columns if c.upper().startswith("RESOLU"))
    MES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
    r = m[m.ENTIDAD.astype(str).str.upper().str.contains("NUEVA")][col].astype(str).str.lower().sum()
    return sorted({pd.Timestamp(int(a), MES[mes], int(d)) for d, mes, a in re.findall(r"(\d{1,2}) de (\w+) del? (\d{4})", r) if mes in MES})


def red_diaria(fin="2026-09-20"):
    """Las 6 variables de red del cuaderno 18, por dia, conocidas ese dia (usan el triage hasta ese dia)."""
    te = pd.read_parquet(RAIZ / "salidas/triage_entidad.parquet", columns=["dia", "entidad", "n"]); te["dia"] = pd.to_datetime(te.dia)
    te["grupo"] = te.entidad.map({e: grupo_asegurador(e) for e in te.entidad.dropna().unique()}).fillna("Otras")
    D = te.pivot_table(index="dia", columns="grupo", values="n", aggfunc="sum").reindex(pd.date_range("2020-01-01", fin)).fillna(0)
    D.loc["2024-03-19":"2024-03-21"] = np.nan
    P = D.rolling(28, min_periods=20).sum(); tot = P.sum(axis=1); resto = P.drop(columns="Nueva EPS").sum(axis=1)
    V = pd.DataFrame({"peso_nueva_eps_28d": P["Nueva EPS"] / tot, "peso_sura_28d": P["SURA"] / tot,
                      "cambio_nueva_eps_28d": np.log1p(P["Nueva EPS"]) - np.log1p(P["Nueva EPS"].shift(28)),
                      "cambio_resto_28d": np.log1p(resto) - np.log1p(resto.shift(28)),
                      "herfindahl_28d": (P.div(tot, axis=0) ** 2).sum(axis=1)})
    res = pd.Series(0.0, index=V.index)
    for d in resoluciones_nueva_eps(): res[d:d + pd.Timedelta(days=30)] = 1
    V["resolucion_nueva_eps_30d"] = res
    return V.ffill()


# ---------------------------------------------------------------- regimenes y fenomenos (cuaderno 20)
def regimenes_diarios(fin="2026-09-30"):
    """Estados que duran y se repiten, por dia, todos conocidos al predecir (fila regimenes de variables.csv)."""
    dias = pd.date_range("2010-01-01", fin); R = pd.DataFrame(index=dias)
    en = pd.read_csv(RAIZ / "calendarios/enso_oni.csv", parse_dates=["fecha"])
    oni = en.set_index(en.fecha.dt.to_period("M"))["oni"]
    R["oni"] = pd.Series(oni.reindex((dias - pd.DateOffset(months=2)).to_period("M")).values, index=dias).ffill()
    R["el_nino"] = (R.oni >= .5).astype(float); R["la_nina"] = (R.oni <= -.5).astype(float)
    R["covid_fuerte"] = ((dias >= "2020-03-15") & (dias <= "2020-08-31")).astype(float)
    R["covid_parcial"] = ((dias >= "2020-09-01") & (dias <= "2022-02-28")).astype(float)
    R["paro_nacional_2021"] = ((dias >= "2021-04-28") & (dias <= "2021-06-15")).astype(float)
    s = pd.read_csv(RAIZ / "calendarios/sismos_usgs.csv", parse_dates=["fecha"]); fuertes = s[s.mag >= 4.5].fecha
    R["sismo_fuerte_7d"] = 0.0
    for d in fuertes: R.loc[d:d + pd.Timedelta(days=6), "sismo_fuerte_7d"] = 1.0
    de = pd.read_csv(RAIZ / "calendarios/desastres_manizales_2020_2026.csv"); R["desastre_activo"] = 0.0
    for _, r in de.dropna(subset=["fecha_inicio"]).iterrows():
        a = pd.Timestamp(r.fecha_inicio); b = pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else a
        R.loc[a:b, "desastre_activo"] = 1.0
    red = red_diaria(min(fin, "2026-09-20")).reindex(dias)
    p10 = red.peso_nueva_eps_28d.loc["2022-01-01":REF_FIN].quantile(.10)
    R["crisis_red"] = (red.peso_nueva_eps_28d < p10).astype(float).where(red.peso_nueva_eps_28d.notna(), 0.0)
    return R
