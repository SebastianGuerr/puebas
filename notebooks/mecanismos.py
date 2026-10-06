"""
Mecanismos en la forma en que se midieron (filas mecanismos_* de patrones/datos/variables.csv, escritas antes de
calcular). Cada hallazgo entra con su subgrupo de dias, su ventana, su rezago y su gatillo, no como indicador de
volumen siempre encendido. El por que de cada definicion y la linea donde se midio su efecto estan en las filas.

    python notebooks/mecanismos.py --humo                          matrices, fugas, cobertura y episodios
    python notebooks/mecanismos.py --exp m1_2025 --modelos sarimax_mec lightgbm_rel_mec
    python notebooks/mecanismos.py --exp m2_2025 --modelos lightgbm_rel_mec      (SARIMAX de m2 = el de m1)

Experimentos (en pronostico.EXPERIMENTOS; se corren SOLO desde aqui, porque m2 y m3 cambian el entrenamiento):
    m1  e1 + variables de mecanismo                                   salidas/pronostico/m1[_2025]/
    m2  m1 + repertorio: dentro de cada ano, los dias en calma y los marcados pesan lo mismo (solo LightGBM)
    m3  m1 sin la fase fuerte de la COVID (2020-03-15 a 2020-08-31); la parcial sigue con su indicador

Tres familias de columnas, por lo que se sabe al predecir t = o + h (h <= 7):
    fut_m_*      conocidas por adelantado (calendario de eventos) o con rezago >= 7 dias respecto de t
    ext_m_*      lo que se sabe en el dia; pronostico.rasgos las desplaza al origen
    ext_g_m_*    igual, pero con compuerta: faltante (NaN) cuando su gatillo no esta activo
Las de rezago >= 7 dias respecto de t van sin desplazar: exigen H <= 7 (se comprueba).

Modelos:
    sarimax_mec       SARIMAX de e1 + solo los mecanismos episodicos (lineales): Feria, noches, fiestas, catastrofe
    lightgbm_rel_mec  LightGBM sobre log(y) - nivel con todas las columnas; los episodios raros (menos de 30 dias,
                      el min_child_samples del motor) entran ademas como desplazamiento lineal estimado en el
                      entrenamiento con el calendario descontado, porque un arbol no puede aislarlos
"""
import argparse
import time
import warnings

import numpy as np
import pandas as pd

import pronostico as pr

ACTIVO = False                     # main() lo enciende: m2 y m3 no son validos por la linea de comandos de pronostico.py

FERIA_DIAS = (0, 4)                # dias 0-4 desde el inicio de la Feria
FIESTA_KM, FIESTA_COLA = 60, 3     # fiestas a >= 60 km, durante la fiesta y 3 dias despues
NOCHES = [(12, 7), (12, 24), (12, 31)]                    # velitas, nochebuena, fin de ano: el dia completo baja
DIAS_SIGUIENTES = [(12, 26), (1, 2), (1, 3), (1, 4)]     # el pico llega el dia despues
PUBLICACION_MINDEFENSA = 42        # dias: la fuente publica con 2-6 semanas de rezago; se toma el peor caso
RAROS = ["fut_m_feria_d0_4", "fut_m_noche_festiva", "fut_m_dia_siguiente",
         "ext_m_catastrofe_sem1", "ext_m_catastrofe_sem2_3", "ext_m_paro_2021"]
SARIMAX_COLS = RAROS + ["fut_m_fiesta_lejana"]
COVID_FUERTE = pr.COVID["es_covid_fuerte"]
MIN_HOJA = pr.LightGBM.PARAM["min_child_samples"]


# ------------------------------------------------------------------ fuentes
def _intervalos(df, todos, cola=0):
    s = pd.Series(0.0, index=todos)
    for _, r in df.dropna(subset=["fecha_inicio"]).iterrows():
        a = pd.Timestamp(r.fecha_inicio); b = pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else a
        s[a:b + pd.Timedelta(days=cola)] = 1
    return s


def _fechas(todos, md):
    return pd.Series([float((d.month, d.day) in md) for d in todos], index=todos)


def catastrofes():
    """Fecha de cada terremoto con danos en Manizales (desastres_manizales). Los deslizamientos, la alerta volcanica
    y los sismos M>=4,5 no entran: su efecto medido en el hospital es nulo."""
    d = pd.read_csv(pr.RAIZ / "calendarios/desastres_manizales_2020_2026.csv")
    d = d[d.subtipo.astype(str).str.startswith("terremoto") & d.municipio.eq("Manizales")]
    return sorted({pd.Timestamp(x) for x in d.fecha_inicio})


def columnas(dias):
    """Todas las columnas de mecanismo por dia (sin compuerta todavia, con la compuerta aparte). Devuelve
    (FUT, PAS, compuertas), cada una indexada por dia."""
    import indices as ix
    import marcas
    dias = pd.DatetimeIndex(dias)
    todos = pd.date_range("2015-01-01", dias.max())
    FUT, PAS = pd.DataFrame(index=todos), pd.DataFrame(index=todos)

    # calendario de eventos (conocido por adelantado)
    ev = pd.read_csv(pr.RAIZ / "calendarios/eventos_manizales_2020_2026.csv").query("estado in ['realizado', 'programado']")
    fer = pd.Series(0.0, index=todos)
    for f in ev[ev.nombre_evento.eq("Feria de Manizales")].fecha_inicio.dropna():
        a = pd.Timestamp(f); fer[a + pd.Timedelta(days=FERIA_DIAS[0]):a + pd.Timedelta(days=FERIA_DIAS[1])] = 1
    FUT["fut_m_feria_d0_4"] = fer
    fi = pd.read_csv(pr.RAIZ / "calendarios/fiestas_caldas_2020_2026.csv").query("estado in ['realizado', 'programado']")
    FUT["fut_m_fiesta_lejana"] = _intervalos(fi[fi.distancia_km_manizales >= FIESTA_KM], todos, FIESTA_COLA)
    FUT["fut_m_noche_festiva"] = _fechas(todos, NOCHES)
    FUT["fut_m_dia_siguiente"] = _fechas(todos, DIAS_SIGUIENTES)

    # clima: transiciones con su rezago (todas usan datos <= t - 7)
    cc = ix.clima_diario().reindex(todos)
    sl = cc.seco_a_lluvioso.fillna(0); inicio = ((sl > 0) & (sl.shift(1, fill_value=0) == 0)).astype(float)
    FUT["fut_m_cli_seco_lluvioso_7_13"] = inicio.rolling(7, min_periods=1).max().shift(7)
    FUT["fut_m_cli_seco_lluvioso_14_20"] = inicio.rolling(7, min_periods=1).max().shift(14)
    FUT["fut_m_cli_muy_lluviosa_7_13"] = cc.semana_muy_lluviosa.fillna(0).rolling(7, min_periods=1).max().shift(7)
    racha = cc.dias_en_racha_seca.shift(21)
    H = ix.contexto_holistico(todos[todos >= "2019-01-01"]).reindex(todos)
    M = marcas.marcar(todos[todos >= "2019-01-01"]).reindex(todos).fillna(False).astype(bool)
    cambios = {f"ext_g_m_cli_cambio_{k}_s1_5": H[f"ext_h_cambio_{k}"].rolling(29, min_periods=20).mean().shift(7) for k in (1, 2, 3)}
    for c, v in cambios.items(): FUT[c] = v
    FUT["ext_g_m_cli_racha_seca_21"] = racha

    # catastrofe y paro: se saben cuando ya empezaron (se desplazan al origen)
    cat = pd.Series(np.nan, index=todos)
    for c in catastrofes():
        dd = (todos - c).days.values; cat[(dd >= 0) & (dd <= 30)] = dd[(dd >= 0) & (dd <= 30)]
    PAS["ext_m_catastrofe_sem1"] = cat.between(0, 6).astype(float)
    PAS["ext_m_catastrofe_sem2_3"] = cat.between(7, 20).astype(float)
    R = ix.regimenes_diarios(str(max(dias.max(), pd.Timestamp("2026-09-30")).date())).reindex(todos).fillna(0)
    PAS["ext_m_paro_2021"] = R.paro_nacional_2021

    # salud publica (5 familias, la respiratoria es la IRA de la ciudad) y red: H con su compuerta
    import anual
    for c in H:
        if anual.capa(c) == "salud": PAS["ext_g_m_sal_" + c[len("ext_h_fam_"):]] = H[c]
        if anual.capa(c) == "red": PAS["ext_g_m_red_" + c[len("ext_h_"):]] = H[c]

    # social (MinDefensa): anomalia de 7 dias contra los 365 previos, con el rezago de publicacion
    sg = pd.read_csv(pr.RAIZ / "calendarios/seguridad_mindefensa.csv.gz", parse_dates=["fecha"]).set_index("fecha").reindex(todos)
    for k in ["lesiones_personales", "violencia_intrafamiliar"]:
        x = sg[k].astype(float)
        s7 = np.log1p(x.rolling(7).sum()) - np.log1p(x.shift(7).rolling(365, min_periods=200).mean() * 7)
        PAS[f"ext_g_m_soc_{k}"] = s7.shift(PUBLICACION_MINDEFENSA)

    # compuertas (True = encendida)
    G = pd.DataFrame(index=todos)
    for c, v in cambios.items():                     # cambio sostenido en [t-35, t-7]: |media| > p90 de 2020-2024
        G[c] = v.abs() > v.abs().loc["2020-01-01":"2024-12-31"].quantile(.9)
    G["clima_cambio"] = G[list(cambios)].any(axis=1)
    G["clima_racha"] = racha >= 15                                            # racha seca > 14 dias, 3 semanas antes
    G["salud"] = M["ola de salud pública"]
    G["red"] = M["red de salud"]
    G["social"] = H["ext_h_fam_violencias_y_agresiones"] > 1.5                 # el umbral de marcas.py para violencias
    return FUT.reindex(dias), PAS.reindex(dias), G.reindex(dias).fillna(False)


GATILLO_DE = {**{f"ext_g_m_cli_cambio_{k}": f"ext_g_m_cli_cambio_{k}_s1_5" for k in (1, 2, 3)}, "ext_g_m_cli_racha": "clima_racha", "ext_g_m_sal_": "salud",
              "ext_g_m_red_": "red", "ext_g_m_soc_": "social"}


def gatillo(c):
    return next((g for p, g in GATILLO_DE.items() if c.startswith(p)), None)


def con_compuerta(T, G):
    T = T.copy()
    for c in T:
        g = gatillo(c)
        if g: T[c] = T[c].where(G[g])
    return T


def contexto(dias, exp, H=None):
    """La rama 'mecanismos' de pronostico.contexto_exp: (PAS, FUT) con la compuerta aplicada."""
    if not ACTIVO:
        raise RuntimeError("los experimentos m* se corren con notebooks/mecanismos.py (m2 y m3 cambian el entrenamiento)")
    if (H or pr.H) > 7:
        raise RuntimeError("las variables con rezago de 7 dias respecto del dia predicho exigen H <= 7")
    FUT, PAS, G = columnas(dias)
    FUT, PAS = con_compuerta(FUT, G), con_compuerta(PAS, G)
    sin_g = [c for c in FUT if not c.startswith("ext_g_")]
    FUT[sin_g] = FUT[sin_g].fillna(0)
    sin_g = [c for c in PAS if not c.startswith("ext_g_")]
    PAS[sin_g] = PAS[sin_g].fillna(0)
    return PAS, FUT


# ------------------------------------------------------------------ tipos de dia (para pesos, desglose y episodios)
TIPOS_MEC = {"Feria (días 0-4)": "fut_m_feria_d0_4", "noche festiva": "fut_m_noche_festiva",
             "día siguiente a noche festiva": "fut_m_dia_siguiente", "fiesta lejana (≥ 60 km, +3 días)": "fut_m_fiesta_lejana",
             "catástrofe (semanas 1-3)": None, "paro nacional 2021": "ext_m_paro_2021",
             "seco → lluvioso (7-20 días antes)": None}


def tipos_de_dia(dias):
    """Una columna booleana por tipo de dia: las 8 marcas de marcas.py y los mecanismos. 'calma' = ninguno.
    'estable (marcas.py)' es la calma de antes (solo las 8 marcas), para comparar con el cuaderno 23."""
    import marcas
    dias = pd.DatetimeIndex(dias)
    Mk = marcas.marcar(dias); M = Mk[marcas.TIPOS]
    FUT, PAS, G = columnas(dias)
    T = M.copy()
    for t, c in TIPOS_MEC.items():
        if c: T[t] = (FUT[c] if c in FUT else PAS[c]).fillna(0) > 0
    T["catástrofe (semanas 1-3)"] = (PAS.ext_m_catastrofe_sem1 + PAS.ext_m_catastrofe_sem2_3) > 0
    T["seco → lluvioso (7-20 días antes)"] = (FUT.fut_m_cli_seco_lluvioso_7_13 + FUT.fut_m_cli_seco_lluvioso_14_20).fillna(0) > 0
    for g in ["clima_cambio", "clima_racha"]:                 # salud, red y social ya son marcas de marcas.py
        T[f"compuerta {g}"] = G[g].astype(bool)
    T = T.fillna(False).astype(bool)
    T["calma"] = ~T.any(axis=1)
    T["estable (marcas.py)"] = Mk["estable"].astype(bool)
    return T


def pesos_repertorio(idx, T):
    """Repertorio (m2): dentro de cada ano del entrenamiento, los dias en calma ('calma') y los marcados pesan lo
    mismo en total; los dias COVID quedan con peso 1 (su tratamiento es el brazo m3). Tope [1/3, 3]."""
    T = T.reindex(idx); w = pd.Series(1.0, index=idx)
    covid = T["COVID"].values; calma = T["calma"].values
    for a in np.unique(idx.year):
        en = (idx.year == a) & ~covid
        n_c, n_m = (en & calma).sum(), (en & ~calma).sum()
        if n_c == 0 or n_m == 0: continue
        n = n_c + n_m
        w[en & calma] = (n / 2) / n_c; w[en & ~calma] = (n / 2) / n_m
    return w.clip(1 / 3, 3).values


# ------------------------------------------------------------------ modelos
class SarimaxMec(pr.SARIMAX):
    """SARIMAX de e1 + los mecanismos episodicos lineales (SARIMAX no admite faltantes: sin las columnas con compuerta)."""
    nombre = "sarimax_mec"
    def __init__(self, y, cal):
        super().__init__(y, cal)
        self.E = self.E[[c for c in self.E if not c.startswith(("ext_", "fut_")) or c in SARIMAX_COLS]]
        self.PAS = self.PAS[[c for c in self.PAS if c in SARIMAX_COLS]]


class LightGBMRelMec(pr.LightGBMRel):
    """lightgbm_rel con los episodios raros como desplazamiento lineal y, en m2, con los pesos del repertorio."""
    nombre = "lightgbm_rel_mec"
    tipos = None                       # DataFrame de tipos_de_dia() cuando el experimento pide pesos
    def ajustar_h(self, X, yy):
        import lightgbm as lgb
        Z = X.drop(columns="nivel"); r = np.log(yy) - X.nivel
        rar = [c for c in RAROS if c in Z]
        b = np.zeros(len(rar))
        if rar:                        # efecto de cada episodio con el calendario descontado, como se midio
            ctrl = [c for c in Z if c.startswith(("dow_", "es_"))]
            A = np.c_[np.ones(len(Z)), Z[ctrl].values, Z[rar].values]
            b = np.linalg.lstsq(A, r.values, rcond=None)[0][-len(rar):]
        off = Z[rar].values @ b if rar else 0.0
        w = None if self.tipos is None else pesos_repertorio(X.index, self.tipos)
        ms = [lgb.LGBMRegressor(objective="quantile", alpha=q, **self.PARAM).fit(Z, r - off, sample_weight=w) for q in pr.QL]
        return ms, rar, b
    def predecir_h(self, m, x):
        ms, rar, b = m; z = x.drop(columns="nivel")
        off = float(z[rar].values[0] @ b) if rar else 0.0
        return np.exp(np.sort([mm.predict(z)[0] for mm in ms]) + x.nivel.values[0] + off)


MODELOS = {m.nombre: m for m in [SarimaxMec, LightGBMRelMec]}


def preparar(exp):
    """Activa el experimento y devuelve (y, cal) con el entrenamiento que pide: m3 quita la fase fuerte de la COVID
    (el triage de esos dias pasa a faltante y su indicador sale); m2 activa los pesos del repertorio."""
    global ACTIVO
    ACTIVO = True
    pr.usar(exp); pr.MODELOS.update(MODELOS)
    y, cal = pr.cargar()
    for a, b in pr.EXP.get("excluir", []):
        y.loc[a:b] = np.nan
        if (a, b) == COVID_FUERTE: cal["es_covid_fuerte"] = 0.0
    LightGBMRelMec.tipos = tipos_de_dia(cal.index) if pr.EXP.get("pesos") == "repertorio" else None
    return y, cal


# ------------------------------------------------------------------ evaluacion por tipo de dia
def desglose(P, varas=("calendario", "rapido")):
    """BSS de 'sube' por tipo de dia y modelo, con las dos varas. P: filas de rodar() o de combinar.promedio()."""
    T = tipos_de_dia(pd.date_range("2020-01-01", pd.Timestamp(pr.FIN) + pd.Timedelta(days=pr.H)))
    out = {}
    for vara in varas:
        _, U = pr.leer(["control"], exp="e0", vara=vara)
        Q, _ = pr.metricas(P, U)
        Q = Q.join(T, on="fecha")
        def bss(g):                    # contra la tasa base del propio grupo, como en anual.evaluar_curado
            bs = g.sobre.mean(); return 100 * (1 - ((g.p_sobre - g.sobre) ** 2).mean() / (bs * (1 - bs))) if 0 < bs < 1 else np.nan
        filas = {}
        for t in ["todos"] + list(T.columns):
            G = Q if t == "todos" else Q[Q[t]]
            filas[t] = G.groupby("modelo").apply(bss).to_dict() | {"días": G.fecha.nunique()}
        out[vara] = pd.DataFrame(filas).T
    return out


def brier_bloques(P, base, brazo, vara="calendario", bloque=28, n=2000, semilla=0):
    """Diferencia de Brier de 'sube' (brazo - base) con remuestreo por bloques de 28 dias de fecha: media e IC 95 %."""
    _, U = pr.leer(["control"], exp="e0", vara=vara)
    Q, _ = pr.metricas(P[P.modelo.isin([base, brazo])], U)
    Q["b"] = (Q.p_sobre - Q.sobre) ** 2
    d = Q.pivot_table(index=["origen", "h"], columns="modelo", values="b").dropna()
    f = d.index.get_level_values("origen"); blq = ((f - f.min()).days // bloque).values
    dif = (d[brazo] - d[base]).groupby(blq).agg(["sum", "count"])
    rng = np.random.default_rng(semilla); k = len(dif)
    bt = [(lambda s: s["sum"].sum() / s["count"].sum())(dif.iloc[rng.integers(0, k, k)]) for _ in range(n)]
    return dif["sum"].sum() / dif["count"].sum(), np.quantile(bt, [.025, .975])


# ------------------------------------------------------------------ humo, cobertura y episodios
def episodios(T, desde="2020-01-01", hasta=None):
    """Episodios (rachas contiguas) y dias activos de cada tipo, por ano."""
    T = T.loc[desde:hasta]; filas = []
    for t in T.columns:
        s = T[t].astype(int); ini = (s.diff().fillna(s.iloc[0]) == 1)
        for a in sorted(set(T.index.year)):
            m = T.index.year == a
            filas.append({"tipo": t, "año": a, "episodios": int(ini[m].sum()), "días": int(s[m].sum())})
    F = pd.DataFrame(filas)
    return F.pivot(index="tipo", columns="año", values="episodios"), F.pivot(index="tipo", columns="año", values="días")


def humo():
    """Construye las matrices de m1, m2 y m3 (2025 y 2026), comprueba que no haya infinitos ni fugas y cuenta la
    cobertura de cada variable y los episodios de cada tipo por ano. No ajusta ningun modelo."""
    warnings.filterwarnings("ignore")
    r = {}
    for exp in ["m1_2025", "m3_2025", "m2_2025"]:
        y, cal = preparar(exp)
        PAS, FUT = pr.contexto_exp(cal.index)
        X = pr.rasgos(y, cal, 1, (PAS.reindex(y.index), FUT.reindex(y.index)))
        num = X.select_dtypes("number")
        r[exp] = {"filas": len(X), "columnas": X.shape[1], "infinitos": int(np.isinf(num.values).sum()),
                  "faltantes fuera de compuerta": int(X[[c for c in X if not c.startswith("ext_g_")]].loc["2020-02-01":].isna().any(axis=1).sum()),
                  "dias de entrenamiento utiles (h=1)": int((X[[c for c in X if not c.startswith("ext_g_")]].notna().all(axis=1) & y.notna()).sum())}
        if exp == "m1_2025":
            # fuga: con h = 1..7, ninguna columna puede cambiar si se borra el triage y el clima posteriores al origen
            o = pd.Timestamp("2025-06-15")
            base = {h: pr.rasgos(y, cal, h, (PAS.reindex(y.index), FUT.reindex(y.index))).loc[o + pd.Timedelta(days=h)] for h in range(1, 8)}
            y2 = y.copy(); y2[o + pd.Timedelta(days=1):] = np.nan
            cambia = {h: [c for c in base[h].index if not np.allclose(
                pr.rasgos(y2, cal, h, (PAS.reindex(y.index), FUT.reindex(y.index))).loc[o + pd.Timedelta(days=h), c], base[h][c], equal_nan=True)]
                for h in range(1, 8)}
            r[exp]["columnas que dependen del triage posterior al origen"] = sum(len(v) for v in cambia.values())
            fug_cli = fuga_clima(o)
            r[exp]["columnas de clima que dependen de datos posteriores a t - 7"] = fug_cli
            cov = pd.DataFrame({a: X.loc[str(a)].drop(columns=[c for c in X if not c.startswith(("ext_m", "ext_g_m", "fut_m"))])
                                .pipe(lambda d: (d.notna() & (d != 0)).sum()) for a in range(2020, 2027)})
            r["cobertura"] = cov
    T = tipos_de_dia(pd.date_range("2020-01-01", pr.FIN))
    r["episodios"], r["dias"] = episodios(T)
    return r


def fuga_clima(o):
    """Recalcula las columnas de clima con el archivo de clima cortado en o: las de los dias o+1..o+7 no pueden
    cambiar (usan datos <= t - 7 <= o)."""
    import indices as ix
    dias = pd.date_range("2024-01-01", o + pd.Timedelta(days=7))
    F1, _, G1 = columnas(dias)
    orig = ix.clima_diario
    try:
        cc = orig(); ix.clima_diario = lambda: cc.loc[:o]          # tambien alimenta los indices de cambio (PCA de H)
        F2, _, G2 = columnas(dias)
    finally:
        ix.clima_diario = orig
    F1, F2 = F1.join(G1.astype(float), rsuffix="_g"), F2.join(G2.astype(float), rsuffix="_g")
    cols = [c for c in F1 if "_cli_" in c or c.startswith("clima")]
    t = pd.date_range(o + pd.Timedelta(days=1), o + pd.Timedelta(days=7))
    return int(sum(not np.allclose(F1.loc[t, c].values, F2.loc[t, c].values, equal_nan=True) for c in cols))


def main():
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", choices=[e for e in pr.EXPERIMENTOS if e[:2] in ("m1", "m2", "m3")])
    ap.add_argument("--modelos", nargs="*", default=["sarimax_mec", "lightgbm_rel_mec"])
    ap.add_argument("--humo", action="store_true")
    a = ap.parse_args()
    if a.humo:
        r = humo(); pd.set_option("display.width", 250); pd.set_option("display.max_columns", 30)
        for k, v in r.items(): print(f"\n== {k}\n{v}")
        car = pr.SALIDA / "mecanismos"; car.mkdir(parents=True, exist_ok=True)
        r["cobertura"].to_csv(car / "_cobertura.csv"); r["episodios"].to_csv(car / "_episodios.csv"); r["dias"].to_csv(car / "_dias.csv")
        return
    y, cal = preparar(a.exp); car = pr.EXP["carpeta"]; car.mkdir(parents=True, exist_ok=True)
    for m in a.modelos:
        t = time.time(); print(f"{a.exp} {m}...", flush=True)
        d = pr.rodar(m, y, cal, avisar=lambda s: print(s, flush=True))
        d.to_parquet(car / f"{m}.parquet"); print(f"{a.exp} {m} listo en {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    import mecanismos                  # una sola instancia del modulo: la que importa pronostico.contexto_exp
    mecanismos.main()
