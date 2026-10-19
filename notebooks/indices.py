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
from contextlib import contextmanager
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


# Ultimo dia de triage que leen las variables de red. Los cuadernos quedan cortados en el 20-sep a proposito; la
# operacion y el orquestador de contexto lo mueven al ultimo dia completo (docs/CONTEXTO.md, 2026-10-15).
FIN_RED = "2026-09-20"


def red_diaria(fin=None):
    """Las 6 variables de red del cuaderno 18, por dia, conocidas ese dia (usan el triage hasta ese dia)."""
    fin = fin or FIN_RED
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


# ---------------------------------------------------------------- familias operativas (cuaderno 22)
FAMILIAS_OPERATIVAS = ["respiratoria", "violencias_y_agresiones", "salud_mental_e_intoxicaciones", "materno_perinatal", "inmunoprevenibles"]


def _sem_epi(anio, semana_):
    e4 = pd.Timestamp(year=int(anio), month=1, day=4)
    return e4 - pd.Timedelta(days=(e4.dayofweek + 1) % 7) + pd.Timedelta(weeks=int(semana_) - 1)


def familias_operativas(foto=None):
    """Las familias que existen AL PREDECIR en 2026 (fila reentrenamiento_holistico): microdatos hasta 2025 y la
    foto del Power BI del INS para 2026. Fuera la digestiva (sin 2026) y la IRAG hospitalizada (no empalma).
    Con SEMANA_COMPLETA (umbral; None por defecto) se aplica el arreglo de la semana a medias (_semana_completa)."""
    import glob
    foto = foto or sorted(glob.glob(str(RAIZ / "calendarios/vigilancia/powerbi/20*")))[-1]
    S = _series_operativas(foto)
    crudas = S.copy()
    S = S.apply(anomalia_operativa)
    Z = (S - S.loc[:REF_FIN].mean()) / S.loc[:REF_FIN].std()
    out = pd.DataFrame(index=Z.index)
    for fam in FAMILIAS_OPERATIVAS:
        cols = [f"{ev}_{var or 'casos'}" for ev, var in FAMILIAS[fam] if f"{ev}_{var or 'casos'}" in Z]
        out[fam] = Z[cols].mean(axis=1, skipna=True).where(Z[cols].notna().any(axis=1))
    if SEMANA_COMPLETA is not None:
        out = _semana_completa(out, crudas, SEMANA_COMPLETA, foto)
    return out


def _series_operativas(foto):
    """Los conteos crudos semanales de las familias operativas: microdatos hasta 2025 empalmados con la foto."""
    S = series_sivigila().drop(columns=[c for c in series_sivigila().columns if c.startswith("998") or "irag" in c])
    t = pd.read_csv(Path(foto) / "ira_995_tablero.csv"); t.index = [_sem_epi(a, w) for a, w in zip(t.anio, t.semana)]
    t = t.groupby(level=0).sum()
    S = S.reindex(S.index.union(pd.date_range(S.index.max(), t.index.max(), freq="7D")))   # sitio para 2026
    def empalme(col, nueva):
        comun = S[col].dropna().index.intersection(nueva.index)
        k = (S.loc[comun, col] / nueva[comun].replace(0, np.nan)).median() if len(comun) else 1.0
        S[col] = S[col].combine_first(nueva * k)
    empalme("995_consultas_ira_total", t.grup_total.astype(float))
    empalme("995_consultas_ira_0_4", (t.grupo_1 + t.grupo_2 + t.grupo_3).astype(float))
    empalme("995_consultas_ira_60_mas", t.grupo_7.astype(float))
    for ev in ("300", "356", "831", "875"):
        p = pd.read_csv(Path(foto) / f"evento_{ev}.csv"); p.index = [_sem_epi(a, w) for a, w in zip(p.anio, p.semana)]
        empalme(f"{ev}_casos", p.groupby(level=0).casos.sum().astype(float))
    ru = pd.read_csv(Path(foto) / "rutinaria_manizales.csv")
    for ev in ("365", "549"):
        r = ru[ru.cod_eve.eq(int(ev))].groupby("semana").casos.sum()
        r = pd.Series(r.reindex(range(1, int(ru.semana.max()) + 1)).fillna(0).values,
                      index=[_sem_epi(2026, w) for w in range(1, int(ru.semana.max()) + 1)]).astype(float)
        S[f"{ev}_casos"] = S[f"{ev}_casos"].combine_first(r)
    return S.sort_index()


# ---------------------------------------------------------------- semana epidemiologica a medias (fila salud_semana_completa)
# Umbral de completitud con que se juzga la ultima semana de la foto. None (por defecto) = sin arreglo, como siempre:
# los cuadernos y las validaciones no cambian. La operacion lo enciende con salud_semana_completa(UMBRAL_SEMANA).
SEMANA_COMPLETA = None
UMBRAL_SEMANA = .90
SEMANAS_ESPERADO = 4          # esperado = mediana de las 4 semanas anteriores (edad >= 1: completas, CONTEXTO (rezago))
ARRASTRE_MAX = 4              # semanas que se arrastra la ultima completa cuando la que toca no esta en la foto
COMPLETITUD = {}              # el ultimo diagnostico: {familia: {...}}, para la operacion, el semaforo y el tablero


@contextmanager
def salud_semana_completa(umbral=UMBRAL_SEMANA):
    """Mientras dure, familias_operativas (y lo que sale de ella) aplica el arreglo con ese umbral (None = sin)."""
    global SEMANA_COMPLETA
    previo, SEMANA_COMPLETA = SEMANA_COMPLETA, umbral
    try: yield
    finally: SEMANA_COMPLETA = previo


def semana_epi(fecha):
    """'SE40-2026' de la semana epidemiologica que empieza ese domingo (o que contiene ese dia)."""
    t = pd.Timestamp(fecha)
    for a in (t.year + 1, t.year, t.year - 1):
        s1 = _sem_epi(a, 1)
        if t >= s1: return f"SE{(t - s1).days // 7 + 1}-{a}"
    return str(t.date())


def _semana_completa(out, crudas, umbral, foto):
    """La ultima semana de cada familia se juzga contra la mediana de las SEMANAS_ESPERADO anteriores (suma de sus
    conteos crudos): por debajo de umbral x esperado no se usa y vale el indice de la ultima completa. Las semanas que
    faltan despues de la ultima completa se rellenan con ella, hasta ARRASTRE_MAX. Deja el diagnostico en COMPLETITUD."""
    out = out.copy(); sem = pd.Timedelta(weeks=1)
    out = out.reindex(out.index.union(pd.date_range(out.index.max() + sem, periods=ARRASTRE_MAX, freq="7D")))
    COMPLETITUD.clear()
    for fam in FAMILIAS_OPERATIVAS:
        cols = [f"{ev}_{var or 'casos'}" for ev, var in FAMILIAS[fam] if f"{ev}_{var or 'casos'}" in crudas]
        raw = crudas[cols].sum(axis=1, min_count=1)
        ult = raw.last_valid_index()
        if ult is None: continue
        prev = raw.reindex([ult - sem * i for i in range(1, SEMANAS_ESPERADO + 1)]).dropna()
        esperado = float(prev.median()) if len(prev) else np.nan
        valor = float(raw[ult])
        frac = valor / esperado if esperado and np.isfinite(esperado) and esperado > 0 else np.nan
        completa = not (np.isfinite(frac) and frac < umbral)
        buena = ult if completa else ult - sem
        tramo = (out.index > buena) & (out.index <= buena + sem * ARRASTRE_MAX)
        out.loc[tramo, fam] = out.at[buena, fam]
        COMPLETITUD[fam] = {"foto": Path(foto).name, "ultima": ult, "valor": valor, "esperado": esperado,
                            "fraccion": frac, "completa": completa, "ultima_completa": buena, "umbral": umbral}
    return out


def lectura_salud(origen, foto=None, umbral=UMBRAL_SEMANA):
    """Que semana de cada familia lee M3s en el origen, con y sin el arreglo: una fila por familia con la semana que
    toca, la que se usa y el porque. Calcula familias_operativas con el arreglo (umbral) y sin el."""
    o = pd.Timestamp(origen)
    toca = o - pd.Timedelta(days=(o.dayofweek + 1) % 7) - pd.Timedelta(weeks=1 + REZAGO_SALUD)
    sin = familias_operativas(foto)
    with salud_semana_completa(umbral):
        con = familias_operativas(foto); diag = {k: dict(v) for k, v in COMPLETITUD.items()}
    filas = []
    for fam in FAMILIAS_OPERATIVAS:
        d = diag.get(fam, {})
        ult, buena = d.get("ultima"), d.get("ultima_completa")
        if buena is None or toca <= buena:
            usada, motivo = toca, f"{semana_epi(toca)} completa" if buena is not None else "sin datos"
        else:
            usada = buena if toca <= buena + pd.Timedelta(weeks=ARRASTRE_MAX) else None
            if toca <= ult:
                motivo = f"la {semana_epi(ult)} llegó al {100 * d['fraccion']:.0f} % de lo esperado"
            else:
                motivo = f"la {semana_epi(toca)} no está en la foto del {d['foto']}"
                if not d["completa"]: motivo += f" y la {semana_epi(ult)} llegó al {100 * d['fraccion']:.0f} %"
        filas.append({"familia": fam, "semana_toca": toca, "se_toca": semana_epi(toca), "semana_usada": usada,
                      "se_usada": semana_epi(usada) if usada is not None else "ninguna (vale 0)",
                      "arrastre": usada is not None and usada != toca, "motivo": motivo,
                      "indice_sin": float(sin[fam].get(toca, np.nan)), "indice_con": float(con[fam].get(toca, np.nan)),
                      "fraccion_ultima": d.get("fraccion", np.nan), "se_ultima": semana_epi(ult) if ult is not None else "",
                      "foto": d.get("foto", "")})
    return pd.DataFrame(filas)


# Semanas de MAS con que se lee la salud publica. 0 (por defecto, lo publicado) = la semana epidemiologica que acabo
# el sabado anterior al dia, que en la foto del Power BI llega a medias. El experimento m3s_rs lo pone en 1 con
# salud_con_rezago() (fila m3s_correcciones_red_salud; rezago medido en docs/CONTEXTO.md, 2026-10-16 (rezago)).
REZAGO_SALUD = 0


@contextmanager
def salud_con_rezago(semanas):
    """Mientras dure, contexto_holistico (y lo que sale de el: marcas, compuertas) lee la salud 'semanas' mas tarde."""
    global REZAGO_SALUD
    previo, REZAGO_SALUD = REZAGO_SALUD, int(semanas)
    try: yield
    finally: REZAGO_SALUD = previo


def contexto_holistico(dias):
    """Las 24 variables de H por dia, lo que se sabe ESE dia (se usan desplazadas al origen en pronostico.py)."""
    dias = pd.DatetimeIndex(dias)
    H = indices_clima(diario=True).reindex(dias).ffill(limit=30)
    F = familias_operativas()
    domingo = dias - pd.to_timedelta((dias.dayofweek + 1) % 7, unit="D")
    for c in F: H[f"fam_{c}"] = F[c].reindex(domingo - pd.Timedelta(weeks=1 + REZAGO_SALUD)).values   # ultima semana completa
    H = H.join(red_diaria().reindex(dias).ffill(limit=30))
    R = regimenes_diarios(str(max(dias.max(), pd.Timestamp("2026-09-30")).date())).reindex(dias)
    H = H.join(R[["oni", "el_nino", "la_nina", "sismo_fuerte_7d"]])
    return H.add_prefix("ext_h_").fillna(0)


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
    red = red_diaria(min(fin, FIN_RED)).reindex(dias)
    p10 = red.peso_nueva_eps_28d.loc["2022-01-01":REF_FIN].quantile(.10)
    R["crisis_red"] = (red.peso_nueva_eps_28d < p10).astype(float).where(red.peso_nueva_eps_28d.notna(), 0.0)
    return R
