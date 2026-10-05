"""
El motor de la prediccion del cuaderno 15: los datos, las entradas por capas, los modelos y la
evaluacion. Protocolo en docs/CONTEXTO.md (2026-09-30, «Arranca el modelo de prediccion», y
2026-10-01, «Contexto completo, todos los anos y prueba sobre 2026»), fijado antes de mirar.

    python notebooks/pronostico.py                              fase A (E0), todos los modelos
    python notebooks/pronostico.py --exp e2 --modelos sarimax   un experimento y un modelo
    python notebooks/pronostico.py --exp e2 --anio --modelos sarimax   prueba 2: el ano a ciegas

Experimentos:
    e0  entrena desde 2022-03, sin contexto externo; evalua 2025-01 a 2026-09   salidas/pronostico/
    e1  entrena desde 2020-01 con la COVID marcada, sin contexto; evalua 2026  salidas/pronostico/e1/
    e2  e1 + todo el contexto externo (fila contexto_completo de variables.csv) salidas/pronostico/e2/

Cada modelo escribe su archivo (una fila por origen y horizonte, con los cuantiles y lo que de verdad
paso), para que una corrida cortada no pierda lo hecho.

Reglas que el codigo hace cumplir:
- toda entrada se calcula con datos <= origen, salvo lo que se conoce por adelantado (calendario,
  eventos programados);
- todos los modelos se reentrenan cada REENTRENO origenes; entre reentrenamientos solo usan los datos
  nuevos si su estructura lo permite (estado de SARIMAX, rezagos de GLM y LightGBM, contexto de Chronos);
- ningun parametro se elige mirando el periodo de evaluacion.
"""
import argparse, logging, os, re, sys, time, warnings
from pathlib import Path

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")
for _v in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):   # varias colas en paralelo: cada una
    os.environ.setdefault(_v, "2")                                         # con pocos hilos, o se estorban (02-10)
import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "salidas/pronostico"
INI, FIN = "2022-03-01", "2026-09-20"
PRIMER_ORIGEN, ULTIMO_ORIGEN = "2024-12-31", "2026-09-13"
H = 7
REENTRENO = 7
QL = np.array([.02, .05, .10, .25, .50, .75, .90, .95, .98])
QCOL = [f"q{int(round(q * 100)):02d}" for q in QL]
CAL = ["es_festivo", "es_puente", "es_vispera_festivo", "es_post_festivo", "es_quincena",
       "es_vacaciones_escolares", "es_semana_santa", "es_temporada_navidad", "es_temporada_fin_anio",
       "es_regreso_colegio"]
NIVELES = ["ext_red_nueva_peso", "ext_enso_oni"]      # contexto que es un nivel, no una anomalia: su 'tipico' no es 0
COVID = {"es_covid_fuerte": ("2020-03-15", "2020-08-31"), "es_covid_parcial": ("2020-09-01", "2022-02-28")}
CAPAS = {"calendario": "dow_|^es_", "estacion": "four_", "nivel": "^nivel$", "memoria": "^mem_",
         "salud": "^ext_sal_", "clima": "^ext_cli_", "social": "^ext_soc_", "red": "^ext_red_",
         "catastrofe": "^ext_cat_", "enso": "^ext_enso", "eventos": "^fut_"}
EXPERIMENTOS = {
    "e0": dict(ini=INI, contexto=False, origenes=(PRIMER_ORIGEN, ULTIMO_ORIGEN), carpeta=SALIDA),
    "e1": dict(ini="2020-01-01", contexto=False, origenes=("2025-12-31", ULTIMO_ORIGEN), carpeta=SALIDA / "e1"),
    "e2": dict(ini="2020-01-01", contexto=True, origenes=("2025-12-31", ULTIMO_ORIGEN), carpeta=SALIDA / "e2"),
    # e3: e1 + el contexto depurado (fila contexto_depurado de variables.csv: elegido con datos <= 2025-12-31)
    "e3": dict(ini="2020-01-01", contexto=True, origenes=("2025-12-31", ULTIMO_ORIGEN), carpeta=SALIDA / "e3",
               seleccion=["ext_sal_ira_total", "ext_sal_consultas_todas", "ext_cli_radiacion_cambio", "ext_cli_temp_28d",
                          "ext_soc_lesiones_personales", "ext_soc_violencia_intrafamiliar", "ext_red_nueva_peso",
                          "ext_red_nueva_cambio"]),
    # validacion_2025: la configuracion de e1 evaluada en 2025, para ver si lo de 2026 se repite en otro ano
    "e1_2025": dict(ini="2020-01-01", contexto=False, origenes=("2024-12-31", "2025-12-30"), carpeta=SALIDA / "e1_2025"),
    # jerarquico (fila jerarquico): Nueva EPS y el resto, cada una con las entradas de e1; el total = suma de cuantiles
    "j_ne": dict(ini="2020-01-01", contexto=False, origenes=("2025-12-31", ULTIMO_ORIGEN), carpeta=SALIDA / "j_ne", serie="nueva_eps"),
    "j_resto": dict(ini="2020-01-01", contexto=False, origenes=("2025-12-31", ULTIMO_ORIGEN), carpeta=SALIDA / "j_resto", serie="resto"),
}
# reentrenamiento holistico (fila reentrenamiento_holistico, cuaderno 22): H = 24 variables de notebooks/indices.py.
# C1 = 'h' (total con H); C2 = 'hb<banda>' (cada banda de edad con H). '_2025' = validacion; sin sufijo = prueba 2026.
BANDAS = {"04": "0-4", "514": "5-14", "1544": "15-44", "4564": "45-64", "65": "65-+"}
for _suf, _ors in [("_2025", ("2024-12-31", "2025-12-30")), ("", ("2025-12-31", ULTIMO_ORIGEN))]:
    EXPERIMENTOS[f"h{_suf}"] = dict(ini="2020-01-01", contexto="holistico", origenes=_ors, carpeta=SALIDA / f"h{_suf}")
    for _k, _b in BANDAS.items():
        EXPERIMENTOS[f"hb{_k}{_suf}"] = dict(ini="2020-01-01", contexto="holistico", origenes=_ors,
                                             carpeta=SALIDA / f"hb{_k}{_suf}", serie=f"edad:{_b}")
EXP = EXPERIMENTOS["e0"]                      # el experimento activo; lo cambia usar()
ANIO_ORIGEN = "2025-12-31"


def usar(nombre):
    """Activa un experimento para todo el modulo."""
    global EXP
    EXP = EXPERIMENTOS[nombre]
    return EXP


# ------------------------------------------------------------------ datos
def cargar():
    """Triage diario y calendario desde el inicio del experimento activo. La caida de registro de marzo de
    2024 va como nula. Si el entrenamiento toca la COVID, sus dos fases entran como fechas especiales."""
    dias = pd.date_range(EXP["ini"], FIN)
    t = pd.read_parquet(RAIZ / "salidas/triage_diario.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
    y = t.set_index("dia")["triages"].reindex(dias).astype(float)
    if str(EXP.get("serie", "")).startswith("edad:"):                # jerarquico por banda de edad (cuaderno 22)
        ed = pd.read_parquet(RAIZ / "salidas/triage_edad.parquet")
        ed = ed[ed.banda.eq(EXP["serie"].split(":", 1)[1])]
        y = ed.groupby(pd.to_datetime(ed.dia))["n"].sum().reindex(dias).fillna(0).astype(float)
    elif EXP.get("serie"):                                           # jerarquico: Nueva EPS o el resto
        te = pd.read_parquet(RAIZ / "salidas/triage_entidad.parquet", columns=["dia", "entidad", "n"])
        ent = te.entidad.fillna("")
        es_ne = ent.str.contains(r"NUEVA EMPRESA PROMOTORA|NUEVA EPS", regex=True) & ~ent.str.contains("COMPLEMENTARIOS")
        ne = te[es_ne].groupby(pd.to_datetime(te.dia[es_ne]))["n"].sum().reindex(dias).fillna(0)
        y = ne if EXP["serie"] == "nueva_eps" else y - ne
    y["2024-03-19":"2024-03-21"] = np.nan
    idx = pd.date_range(EXP["ini"], pd.Timestamp(FIN) + pd.Timedelta(days=H))
    cal = (pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
             .reindex(idx)[CAL].apply(pd.to_numeric, errors="coerce").fillna(0))
    if pd.Timestamp(EXP["ini"]) < pd.Timestamp(COVID["es_covid_parcial"][1]):
        for c, (a, b) in COVID.items():
            cal[c] = ((cal.index >= a) & (cal.index <= b)).astype(float)
    return y, cal


def calendario(idx, cal):
    """Capa 1 (dia de semana y fechas especiales) y capa 2 (estacion: Fourier anual, 3 armonicos)."""
    X = pd.get_dummies(pd.Index(idx.dayofweek), prefix="dow", drop_first=True).set_index(idx).astype(float)
    X = X.join(cal.reindex(idx).fillna(0))
    doy = 2 * np.pi * idx.dayofyear.values / 365.25
    for k in (1, 2, 3):
        X[f"four_s{k}"] = np.sin(k * doy); X[f"four_c{k}"] = np.cos(k * doy)
    return X


def _semanal_a_diario(w, todos):
    """Serie semanal (indice = domingo de inicio) -> el valor de la ultima semana completa ANTES de la del dia,
    como anomalia operativa: log contra la media de las 52 semanas previas (sin mirar el ano entero)."""
    lw = np.log1p(w.astype(float))
    an = lw - lw.shift(1).rolling(52, min_periods=26).mean()
    domingo = todos - pd.to_timedelta((todos.dayofweek + 1) % 7, unit="D")
    return pd.Series(an.reindex(domingo - pd.Timedelta(weeks=1)).values, index=todos)


def _sem(anio, semana):
    """Domingo de inicio de la semana epidemiologica (la SE1 es la que contiene el 4 de enero)."""
    e4 = pd.Timestamp(year=int(anio), month=1, day=4)
    return e4 - pd.Timedelta(days=(e4.dayofweek + 1) % 7) + pd.Timedelta(weeks=int(semana) - 1)


def contexto(dias):
    """Todo el contexto externo (fila contexto_completo de variables.csv). Devuelve dos tablas por dia:
    PAS, lo que se sabe ESE dia (se usa desplazado al origen); FUT, lo que se sabe por adelantado del dia."""
    todos = pd.date_range("2019-01-01", pd.Timestamp(FIN) + pd.Timedelta(days=H))
    PAS, FUT = pd.DataFrame(index=todos), pd.DataFrame(index=todos)
    pbi = RAIZ / "calendarios/vigilancia/powerbi/2026-09-28"

    # salud: tablero 995 de Power BI (2015-2026, sin 2020) empalmado con microdatos; eventos igual
    t = pd.read_csv(pbi / "ira_995_tablero.csv")
    t.index = [_sem(a, w) for a, w in zip(t.anio, t.semana)]; t = t.groupby(level=0).sum().sort_index()
    v = pd.read_csv(RAIZ / "calendarios/vigilancia_sivigila.csv.gz", parse_dates=["fecha_inicio_semana"])
    v = v[v.ambito.eq("manizales")]
    def micro(ev, var):
        return (v[v.evento.eq(ev) & v.variable.eq(var)].drop_duplicates("fecha_inicio_semana")
                  .set_index("fecha_inicio_semana")["valor"].astype(float).sort_index())
    def empalme(principal, respaldo):
        comun = principal.index.intersection(respaldo.index)
        k = (principal[comun] / respaldo[comun].replace(0, np.nan)).median() if len(comun) else 1.0
        return principal.combine_first(respaldo * k).sort_index()
    ira = {"ira_total": (t.grup_total, micro(995, "consultas_ira_total")),
           "ira_0_4": (t.grupo_1 + t.grupo_2 + t.grupo_3, micro(995, "consultas_ira_0_4")),
           "ira_60": (t.grupo_7, micro(995, "consultas_ira_60_mas")),
           "consultas_todas": (t.Tot_tot, micro(995, "consultas_todas_causas_total"))}
    for k, (p, r) in ira.items():
        PAS[f"ext_sal_{k}"] = _semanal_a_diario(empalme(p.astype(float), r), todos)
    e = pd.read_csv(RAIZ / "calendarios/vigilancia_sivigila_eventos.csv.gz", parse_dates=["fecha_inicio_semana"])
    e = e[e.ambito.eq("manizales") & e.variable.eq("casos_notificacion")]
    for ev in (300, 356, 831, 875):
        p = pd.read_csv(pbi / f"evento_{ev}.csv"); p.index = [_sem(a, w) for a, w in zip(p.anio, p.semana)]
        p = p.groupby(level=0)[["casos"]].sum()      # el tablero trae una SE53 parcial en anos de 52: va con la SE1
        r = e[e.evento.eq(ev)].drop_duplicates("fecha_inicio_semana").set_index("fecha_inicio_semana")["valor"].astype(float)
        PAS[f"ext_sal_ev{ev}"] = _semanal_a_diario(empalme(p.casos.astype(float).sort_index(), r.sort_index()), todos)
    ru = pd.read_csv(pbi / "rutinaria_manizales.csv")
    r26 = ru[ru.cod_eve.eq(365)].groupby("semana").casos.sum()
    sem26 = pd.Index([_sem(2026, w) for w in range(1, int(ru.semana.max()) + 1)])
    r26 = pd.Series(r26.reindex(range(1, int(ru.semana.max()) + 1)).fillna(0).values, index=sem26)
    r365 = e[e.evento.eq(365)].drop_duplicates("fecha_inicio_semana").set_index("fecha_inicio_semana")["valor"].astype(float)
    PAS["ext_sal_ev365"] = _semanal_a_diario(r365.combine_first(r26).sort_index(), todos)

    # clima: anomalias contra la climatologia del mes 2020-2024. El archivo acaba el 2026-08-28: se arrastra el
    # ultimo valor conocido hasta 30 dias (en operacion se tendria el dato del dia anterior)
    c = pd.read_csv(RAIZ / "calendarios/clima_unificado.csv.gz", parse_dates=["fecha"]).set_index("fecha").reindex(todos)
    c["amplitud"] = c.temp_max_consenso - c.temp_min_consenso
    c["lluvia7"] = np.log1p(c.precip_7d); c["lluvia30"] = np.log1p(c.precip_30d)
    def anom(col):
        x = c[col].astype(float); ref = x.loc["2020-01-01":"2024-12-31"]
        return x - ref.groupby(ref.index.month).mean().reindex(x.index.month).values
    m7 = lambda col: anom(col).rolling(7, min_periods=5).mean()
    m28 = lambda col: anom(col).rolling(28, min_periods=20).mean()
    PAS["ext_cli_temp_7d"] = m7("temp_media_consenso"); PAS["ext_cli_temp_28d"] = m28("temp_media_consenso")
    PAS["ext_cli_tmin_7d"] = m7("temp_min_consenso"); PAS["ext_cli_tmax_7d"] = m7("temp_max_consenso")
    PAS["ext_cli_amplitud_7d"] = m7("amplitud")
    PAS["ext_cli_humedad_7d"] = m7("humedad_consenso"); PAS["ext_cli_humedad_28d"] = m28("humedad_consenso")
    PAS["ext_cli_lluvia_7d"] = anom("lluvia7"); PAS["ext_cli_lluvia_30d"] = anom("lluvia30")
    PAS["ext_cli_radiacion_7d"] = m7("radiacion_consenso")
    PAS["ext_cli_radiacion_cambio"] = PAS.ext_cli_radiacion_7d - PAS.ext_cli_radiacion_7d.shift(7)
    PAS["ext_cli_viento_7d"] = m7("viento_consenso_ms")
    cli = [k for k in PAS if k.startswith("ext_cli_")]
    PAS[cli] = PAS[cli].ffill(limit=30)

    # social: MinDefensa, ultimos 7 dias contra la media de los 365 previos (log)
    sg = pd.read_csv(RAIZ / "calendarios/seguridad_mindefensa.csv.gz", parse_dates=["fecha"]).set_index("fecha").reindex(todos)
    for k in ["lesiones_transito", "lesiones_personales", "homicidio", "violencia_intrafamiliar"]:
        x = sg[k].astype(float)
        s7 = np.log1p(x.rolling(7).sum()) - np.log1p(x.shift(7).rolling(365, min_periods=200).mean() * 7)
        PAS[f"ext_soc_{k}"] = s7.ffill(limit=30)

    # red: Nueva EPS (cambio 28 contra 28 dias y peso en los ultimos 28)
    te = pd.read_parquet(RAIZ / "salidas/triage_entidad.parquet", columns=["dia", "entidad", "n"])
    te["dia"] = pd.to_datetime(te.dia)
    ent = te.entidad.fillna("")
    es_ne = ent.str.contains(r"NUEVA EMPRESA PROMOTORA|NUEVA EPS", regex=True) & ~ent.str.contains("COMPLEMENTARIOS")
    ne = te[es_ne].groupby("dia")["n"].sum().reindex(todos).fillna(0)
    tot = te.groupby("dia")["n"].sum().reindex(todos).fillna(0)
    s28, t28 = ne.rolling(28).sum(), tot.rolling(28).sum()
    PAS["ext_red_nueva_cambio"] = np.log1p(s28) - np.log1p(s28.shift(28))
    PAS["ext_red_nueva_peso"] = s28 / t28.replace(0, np.nan)
    red = ["ext_red_nueva_cambio", "ext_red_nueva_peso"]
    PAS.loc["2024-03-19":"2024-04-18", red] = np.nan                       # la caida de registro contamina la suma
    PAS.loc[pd.Timestamp(FIN) + pd.Timedelta(days=1):, red] = np.nan
    PAS[red] = PAS[red].ffill()

    # catastrofes: desastre activo (se sabe cuando ya empezo; incluye el terremoto del 2026-08-10)
    d = pd.read_csv(RAIZ / "calendarios/desastres_manizales_2020_2026.csv")
    cat = pd.Series(0.0, index=todos)
    for _, r in d.dropna(subset=["fecha_inicio"]).iterrows():
        a = pd.Timestamp(r.fecha_inicio); b = pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else a
        cat[a:b] = 1
    PAS["ext_cat_desastre"] = cat

    # ENSO: ONI de dos meses antes (se publica con retraso)
    en = pd.read_csv(RAIZ / "calendarios/enso_oni.csv", parse_dates=["fecha"])
    oni = en.set_index(en.fecha.dt.to_period("M"))["oni"]
    PAS["ext_enso_oni"] = oni.reindex((todos - pd.DateOffset(months=2)).to_period("M")).values
    PAS["ext_enso_oni"] = PAS.ext_enso_oni.ffill()

    # conocido por adelantado: eventos de Manizales, fiestas de Caldas, dias especiales
    def activo(df):
        s_ = pd.Series(0.0, index=todos)
        for _, r in df.dropna(subset=["fecha_inicio"]).iterrows():
            a = pd.Timestamp(r.fecha_inicio); b = pd.Timestamp(r.fecha_fin) if pd.notna(r.fecha_fin) else a
            s_[a:b] += 1
        return s_
    ev = pd.read_csv(RAIZ / "calendarios/eventos_manizales_2020_2026.csv").query("estado in ['realizado', 'programado']")
    for k, g in {"feria": ["feria", "taurino"], "religioso": ["religioso"], "civico": ["civico"],
                 "cultural": ["musical", "teatro", "literario", "academico", "universitario"], "deportivo": ["deportivo"]}.items():
        FUT[f"fut_ev_{k}"] = activo(ev[ev.categoria.isin(g)]).clip(upper=1)
    fi = pd.read_csv(RAIZ / "calendarios/fiestas_caldas_2020_2026.csv").query("estado in ['realizado', 'programado']")
    for k, (lo, hi) in {"cerca": (0, 50), "media": (51, 100), "lejos": (101, 999)}.items():
        FUT[f"fut_fiestas_{k}"] = activo(fi[fi.distancia_km_manizales.between(lo, hi)]).clip(upper=3)
    ct = pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha").reindex(todos)
    for k in ["es_dia_madre", "es_dia_padre", "es_amor_amistad", "es_dia_velitas", "es_halloween", "es_nochebuena",
              "es_navidad", "es_ano_viejo", "es_reyes_magos", "es_dia_ninez", "es_dia_mujer", "es_novena"]:
        FUT[f"fut_{k[3:]}"] = pd.to_numeric(ct[k], errors="coerce").fillna(0)
    return PAS.reindex(dias).fillna(0), FUT.reindex(dias).fillna(0)


def contexto_exp(dias):
    """El contexto del experimento activo: el completo, la seleccion depurada, o el holistico H (cuaderno 22)."""
    if EXP.get("contexto") == "holistico":
        import indices
        PAS = indices.contexto_holistico(dias)
        return PAS, pd.DataFrame(index=PAS.index)
    PAS, FUT = contexto(dias)
    sel = EXP.get("seleccion")
    if sel:
        PAS, FUT = PAS[[c for c in PAS if c in sel]], FUT[[c for c in FUT if c in sel]]
    return PAS, FUT


def rasgos(y, cal, h, ctx=None):
    """Entradas para predecir t desde el origen o = t - h. Lo que no es calendario ni conocido por adelantado
    sale de <= o. ctx = (PAS, FUT) de contexto(), o None."""
    ly = np.log(y)
    nivel = ly.rolling(28, min_periods=20).mean()                       # capa 3: nivel reciente
    dow = ly.index.dayofweek
    norma_dow = ly.groupby(dow).transform(lambda s: s.shift(1).rolling(4, min_periods=2).mean())
    X = calendario(y.index, cal)
    X["nivel"] = nivel.shift(h)
    X["mem_semana"] = (ly.rolling(7, min_periods=5).mean() - nivel).shift(h)   # capa 4: memoria
    X["mem_ultimo"] = (ly - norma_dow).shift(h)                               # desvio del ultimo dia frente a su dia de semana
    X["mem_mismo_dia"] = ly.shift(7) - nivel.shift(h)                         # t-7 <= o porque h <= 7
    if ctx is not None:
        PAS, FUT = ctx
        X = X.join(PAS.shift(h).reindex(X.index)).join(FUT.reindex(X.index))
    return X


def capas(cols):
    return {c: next((k for k, p in CAPAS.items() if re.search(p, c)), "otra") for c in cols}


# ------------------------------------------------------------------ modelos
class Modelo:
    nombre = ""
    def __init__(self, y, cal):
        self.y, self.cal = y, cal
        self.ctx = contexto_exp(cal.index) if EXP["contexto"] else None
    def ajustar(self, o): ...
    def predecir(self, o): ...          # -> array (H, len(QL)) de cuantiles del conteo


class _Directo(Modelo):
    """Un modelo por horizonte sobre las entradas de rasgos(): control, GLM y LightGBM."""
    columnas = None
    def __init__(self, y, cal):
        super().__init__(y, cal)
        ctx = None if self.ctx is None else tuple(c.reindex(y.index) for c in self.ctx)
        self.X = {h: rasgos(y, cal.reindex(y.index), h, ctx) for h in range(1, H + 1)}
        if self.columnas:
            self.X = {h: X[[c for c in X if any(c.startswith(p) for p in self.columnas)]] for h, X in self.X.items()}
    def datos(self, h, o):
        X = self.X[h].loc[:o]; yy = self.y.loc[:o]
        ok = X.notna().all(axis=1) & yy.notna()
        return X[ok], yy[ok]
    def ajustar(self, o):
        self.cols, self.m = {}, {}
        for h in range(1, H + 1):
            X, yy = self.datos(h, o)
            self.cols[h] = X.columns[X.std() > 0]                   # fuera lo que no varia en el entrenamiento
            self.m[h] = self.ajustar_h(X[self.cols[h]], yy)
    def fila(self, h, o):
        return self.X[h].loc[[o + pd.Timedelta(days=h)], self.cols[h]]
    def predecir(self, o):
        return np.vstack([self.predecir_h(self.m[h], self.fila(h, o)) for h in range(1, H + 1)])


class Control(_Directo):
    """Base 2: calendario + nivel reciente, en log, con cuantiles empiricos del residuo. Sin estacion ni memoria."""
    nombre = "control"
    columnas = ["dow_", "es_", "nivel"]
    def ajustar_h(self, X, yy):
        Z = np.c_[np.ones(len(X)), X.values]; b, *_ = np.linalg.lstsq(Z, np.log(yy.values), rcond=None)
        r = np.log(yy.values) - Z @ b
        return b, np.quantile(r, QL), r.std()
    def predecir_h(self, m, x):
        b, qr, _ = m
        return np.exp(np.r_[1, x.values[0]] @ b + qr)
    def centro_y_sd(self, o):
        """Para el umbral de pico: la mediana que anuncia el control y la desviacion de su residuo."""
        return [(float(self.predecir_h(self.m[h], self.fila(h, o))[4]), self.m[h][2]) for h in range(1, H + 1)]


class ControlRapido(Control):
    """Segunda vara (fila control_rapido): calendario + nivel de 28 dias + desvio de la ultima semana. Sigue los
    escalones de la red en pocos dias, asi que 'sube' contra este control mide anticipar el dia, no seguir el nivel."""
    nombre = "control_rapido"
    columnas = ["dow_", "es_", "nivel", "mem_semana"]


class Ingenuo(Modelo):
    """Base 1: el mismo dia de la semana anterior, con la dispersion historica de ese salto."""
    nombre = "ingenuo"
    def ajustar(self, o):
        r = np.log(self.y.loc[:o] / self.y.loc[:o].shift(7)).dropna()
        self.qr = np.quantile(r, QL)
    def predecir(self, o):
        return np.vstack([self.y[o + pd.Timedelta(days=h - 7)] * np.exp(self.qr) for h in range(1, H + 1)])


class GLMBinNeg(_Directo):
    """Regresion binomial negativa: cada factor multiplica. Es el modelo que da las razones."""
    nombre = "glm_binneg"
    def ajustar_h(self, X, yy):
        import statsmodels.api as sm
        Z = sm.add_constant(X.values, has_constant="add")
        r = sm.NegativeBinomial(yy.values, Z).fit(disp=0, maxiter=300)
        if not np.all(np.isfinite(r.params)):                       # con muchas columnas puede no converger
            r = sm.NegativeBinomial(yy.values, Z).fit(disp=0, maxiter=300, method="nm")
        return r
    def predecir_h(self, r, x):
        from scipy.stats import nbinom
        mu = float(r.predict(np.c_[np.ones(1), x.values])[0]); a = float(r.params[-1])
        n = 1 / a
        return nbinom.ppf(QL, n, n / (n + mu)).astype(float)


class LightGBM(_Directo):
    """Arboles con refuerzo (gradient boosting), un modelo por cuantil. Capta interacciones."""
    nombre = "lightgbm"
    PARAM = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=30,
                 subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1,
                 n_jobs=2)                                     # 2 hilos: con varias colas en paralelo, mas hilos se estorban
    def ajustar_h(self, X, yy):
        import lightgbm as lgb
        return [lgb.LGBMRegressor(objective="quantile", alpha=q, **self.PARAM).fit(X, np.log(yy)) for q in QL]
    def predecir_h(self, ms, x):
        return np.exp(np.sort([m.predict(x)[0] for m in ms]))


class _ConExogenas(Modelo):
    """Exogenas de los modelos de serie de tiempo: calendario, estacion y lo conocido por adelantado del dia; el
    contexto pasado, con un dia de rezago al entrenar y congelado en el valor del origen al predecir."""
    def __init__(self, y, cal):
        super().__init__(y, cal)
        E = calendario(self.cal.index, self.cal)
        self.E = E[[c for c in E if not c.startswith("dow_")]]
        if self.ctx is not None:
            PAS, FUT = self.ctx
            self.PAS = PAS
            self.E = self.E.join(FUT).join(PAS.shift(1).fillna(0))
    def columnas_activas(self, o):
        Ez = self.E.loc[:o]
        return Ez.columns[Ez.std() > 0]
    def exog_futuro(self, o, n, pasado_tipico=False):
        """Contexto pasado hacia adelante: congelado en el valor del origen. En el ano a ciegas ('pasado_tipico'),
        las anomalias van en 0 (ano tipico) y las variables de NIVEL (NIVELES) siguen congeladas en el origen."""
        F = self.E.loc[o + pd.Timedelta(days=1):o + pd.Timedelta(days=n)].copy()
        if self.ctx is not None:
            F[self.PAS.columns] = self.PAS.loc[o].values
            if pasado_tipico:
                F[[c for c in self.PAS.columns if c not in NIVELES]] = 0.0
        return F[self.cols]


class SARIMAX(_ConExogenas):
    """Serie de tiempo clasica: SARIMA(1,0,1)(0,1,1)7 sobre log, con calendario, estacion y contexto como exogenas."""
    nombre = "sarimax"
    def modelo(self, o):
        from statsmodels.tsa.statespace.sarimax import SARIMAX as S
        return S(np.log(self.y.loc[:o]), exog=self.E.loc[:o, self.cols], order=(1, 0, 1), seasonal_order=(0, 1, 1, 7))
    def ajustar(self, o):
        cols = self.columnas_activas(o)
        previo = getattr(self, "params", None) if list(cols) == list(getattr(self, "cols", [])) else None
        self.cols = cols                                            # arranque desde el ajuste anterior: converge antes
        self.params = self.modelo(o).fit(start_params=previo, disp=0, maxiter=100).params
    def predecir(self, o, n=H, pasado_tipico=False):
        from scipy.stats import norm
        f = self.modelo(o).filter(self.params).get_forecast(n, exog=self.exog_futuro(o, n, pasado_tipico))
        return np.exp(f.predicted_mean.values[:, None] + f.se_mean.values[:, None] * norm.ppf(QL)[None, :])


class Prophet(_ConExogenas):
    """Serie de tiempo por componentes: tendencia con cambios, semana, ano, calendario y contexto."""
    nombre = "prophet"
    def ajustar(self, o):
        from prophet import Prophet as P
        logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
        self.cols = [c for c in self.columnas_activas(o) if not c.startswith("four_")]   # Prophet trae su propio ano
        d = pd.DataFrame({"ds": self.y.loc[:o].index, "y": np.log(self.y.loc[:o].values)})
        d = d.join(self.E.loc[:o, self.cols].reset_index(drop=True))
        self.m = P(weekly_seasonality=True, yearly_seasonality=True, daily_seasonality=False,
                   changepoint_range=0.95, uncertainty_samples=300)
        for c in self.cols: self.m.add_regressor(c)
        self.m.fit(d)
    def predecir(self, o, n=H, pasado_tipico=False):
        F = self.exog_futuro(o, n, pasado_tipico)
        f = pd.DataFrame({"ds": F.index}).join(F.reset_index(drop=True))
        s_ = self.m.predictive_samples(f)["yhat"]
        return np.exp(np.quantile(s_, QL, axis=1).T)


class Chronos2(Modelo):
    """Modelo fundacional de series de tiempo (Amazon Chronos-2, 120 M), sin entrenar: lee la historia y predice."""
    nombre = "chronos2"
    covariables = False
    _pipe = None
    def ajustar(self, o):
        if Chronos2._pipe is None:
            from chronos import Chronos2Pipeline
            import torch; torch.set_num_threads(int(os.environ.get("OMP_NUM_THREADS", "2")))
            Chronos2._pipe = Chronos2Pipeline.from_pretrained("amazon/chronos-2", device_map="cpu")
    def lote(self, origenes, n=H, pasado_tipico=False):
        """Chronos no se entrena: se predicen todos los origenes en lotes. Con contexto, lo conocido por
        adelantado va como covariable futura y el resto como covariable solo pasada."""
        self.ajustar(None)
        futuro = self.cal if self.ctx is None else self.cal.join(self.ctx[1])
        hist, fut = [], []
        for o in origenes:
            d = pd.DataFrame({"id": str(o.date()), "timestamp": self.y.loc[:o].index, "target": self.y.loc[:o].values})
            f = pd.DataFrame({"id": str(o.date()), "timestamp": pd.date_range(o + pd.Timedelta(days=1), periods=n)})
            if self.covariables:
                d = d.join(futuro.reindex(d.timestamp).reset_index(drop=True))
                f = f.join(futuro.reindex(f.timestamp).reset_index(drop=True))
                if self.ctx is not None:
                    d = d.join(self.ctx[0].reindex(d.timestamp).reset_index(drop=True))
            hist.append(d); fut.append(f)
        kw = dict(prediction_length=n, quantile_levels=list(QL), id_column="id", timestamp_column="timestamp", target="target")
        if self.covariables: kw["future_df"] = pd.concat(fut)
        r = self._pipe.predict_df(pd.concat(hist), **kw)
        cols = [str(q) for q in QL] if str(QL[0]) in r.columns else [c for c in r.columns if c not in ("id", "timestamp", "target_name", "predictions")]
        return {pd.Timestamp(i): np.sort(g[cols].values.astype(float), axis=1) for i, g in r.groupby("id")}


class Chronos2Cal(Chronos2):
    nombre = "chronos2_cal"
    covariables = True


MODELOS = {m.nombre: m for m in [Ingenuo, Control, GLMBinNeg, LightGBM, SARIMAX, Prophet, Chronos2, Chronos2Cal]}
FASE_A = ["ingenuo", "control", "glm_binneg", "lightgbm", "sarimax", "prophet", "chronos2", "chronos2_cal"]
CON_CONTEXTO = ["glm_binneg", "lightgbm", "sarimax", "prophet", "chronos2_cal"]


# ------------------------------------------------------------------ evaluacion
def origenes():
    return pd.date_range(*EXP["origenes"])


def rodar(nombre, y, cal, avisar=print, cada=1):
    """Origen rodante. Devuelve una fila por (origen, h) con cuantiles y lo que de verdad paso. Con cada > 1 se
    usa un origen de cada 'cada' dias (para los modelos que no caben en tiempo con todos)."""
    M = MODELOS[nombre](y, cal)
    ors = origenes()[::cada]; filas = []; t0 = time.time()
    if isinstance(M, Chronos2):
        preds = {}
        for i in range(0, len(ors), 8):
            preds.update(M.lote(ors[i:i + 8])); avisar(f"  {nombre}: {min(i + 8, len(ors))}/{len(ors)} ({time.time() - t0:.0f} s)")
    for i, o in enumerate(ors):
        if not isinstance(M, Chronos2):
            if i % max(1, REENTRENO // cada) == 0:
                M.ajustar(o)
                if i % (REENTRENO * 5) == 0: avisar(f"  {nombre}: origen {i}/{len(ors)} ({time.time() - t0:.0f} s)")
            Q = M.predecir(o)
        else:
            Q = preds[o]
        for h in range(1, H + 1):
            t = o + pd.Timedelta(days=h)
            filas.append({"modelo": nombre, "origen": o, "h": h, "fecha": t, "real": y.get(t, np.nan), **dict(zip(QCOL, Q[h - 1]))})
    return pd.DataFrame(filas)


def umbrales(y, cal, clase=None):
    """Para cada (origen, h): lo que anuncia el control (mediana) y su desviacion. Define 'pico' en operacion."""
    C = (clase or Control)(y, cal); filas = []
    for i, o in enumerate(origenes()):
        if i % REENTRENO == 0: C.ajustar(o)
        for h, (c, sd) in enumerate(C.centro_y_sd(o), 1):
            filas.append({"origen": o, "h": h, "esperado_cal": c, "sd_cal": sd})
    return pd.DataFrame(filas)


def anio_a_ciegas(nombre, y, cal):
    """Prueba 2: desde ANIO_ORIGEN se predice de una vez hasta FIN. El contexto pasado va como 'ano tipico'
    (anomalia cero), porque en diciembre no se sabe como sera el clima o la IRA de julio."""
    o = pd.Timestamp(ANIO_ORIGEN); n = (pd.Timestamp(FIN) - o).days
    fechas = pd.date_range(o + pd.Timedelta(days=1), periods=n)
    if nombre == "anio_pasado":                                      # base: el mismo dia de la semana de hace 52 semanas
        salto = np.quantile(np.log(y / y.shift(364)).loc[:o].dropna(), QL)
        Q = np.vstack([y[t - pd.Timedelta(weeks=52)] * np.exp(salto) for t in fechas])
    elif nombre == "regresion_anual":                                # calendario + estacion + eventos + nivel del origen
        X = calendario(cal.index, cal)
        if EXP["contexto"]: X = X.join(contexto_exp(cal.index)[1])
        ly = np.log(y).reindex(X.index)
        X["nivel"] = ly.rolling(28, min_periods=20).mean().shift(1)
        Xtr = X.loc[:o]; ok = Xtr.notna().all(axis=1) & ly.loc[:o].notna()
        cols = Xtr.columns[Xtr[ok].std() > 0]
        Z = np.c_[np.ones(ok.sum()), Xtr.loc[ok, cols].values]
        b, *_ = np.linalg.lstsq(Z, ly.loc[:o][ok].values, rcond=None)
        r = ly.loc[:o][ok].values - Z @ b
        Xf = X.loc[fechas, cols].copy(); Xf["nivel"] = ly.loc[o - pd.Timedelta(days=27):o].mean()
        Q = np.exp((np.c_[np.ones(n), Xf.values] @ b)[:, None] + np.quantile(r, QL)[None, :])
    else:
        M = MODELOS[nombre](y, cal)
        if isinstance(M, Chronos2):
            Q = M.lote([o], n=n)[o]
        else:
            M.ajustar(o); Q = M.predecir(o, n=n, pasado_tipico=True)
    return pd.DataFrame({"modelo": nombre, "origen": o, "h": range(1, n + 1), "fecha": fechas,
                         "real": y.reindex(fechas).values, **{c: Q[:, j] for j, c in enumerate(QCOL)}})


def prob_sobre(Q, u):
    """P(y > u) a partir de los cuantiles, interpolando la funcion de distribucion entre ellos."""
    F = np.array([np.interp(ui, qi, QL, left=QL[0] / 2, right=1 - (1 - QL[-1]) / 2) for qi, ui in zip(Q, u)])
    return 1 - F


def metricas(P, U):
    """P: filas de rodar() de varios modelos. U: umbrales(). Devuelve (P con eventos y probabilidades, tabla).
    La tabla trae los criterios en el orden de la jerarquia (CONTEXTO.md, 2026-10-01)."""
    from sklearn.metrics import roc_auc_score
    P = P.merge(U, on=["origen", "h"]).dropna(subset=["real"])
    P["umbral_pico"] = P.esperado_cal * np.exp(P.sd_cal)
    P["pico"] = (P.real > P.umbral_pico).astype(int)
    P["sobre"] = (P.real > P.esperado_cal).astype(int)
    Q = P[QCOL].values
    P["p_pico"] = prob_sobre(Q, P.umbral_pico.values)
    P["p_sobre"] = prob_sobre(Q, P.esperado_cal.values)
    P["ape"] = (P.q50 - P.real).abs() / P.real
    P["pinball"] = np.mean([np.maximum(q * (P.real - P[c]), (q - 1) * (P.real - P[c])) for q, c in zip(QL, QCOL)], axis=0) / P.real
    P["d_real"] = np.log(P.real / P.esperado_cal); P["d_pred"] = np.log(P.q50 / P.esperado_cal)
    for n, lo, hi in [(50, "q25", "q75"), (80, "q10", "q90"), (90, "q05", "q95")]:
        P[f"cob{n}"] = P.real.between(P[lo], P[hi]).astype(int)
    bs, bp = P.sobre.mean(), P.pico.mean()
    def tabla(g):
        return pd.Series({
            "BSS sube %": 100 * (1 - ((g.p_sobre - g.sobre) ** 2).mean() / (bs * (1 - bs))),
            "BSS pico %": 100 * (1 - ((g.p_pico - g.pico) ** 2).mean() / (bp * (1 - bp))),
            "R2 desvio %": 100 * (1 - ((g.d_real - g.d_pred) ** 2).sum() / (g.d_real ** 2).sum()),
            "acierta sube/baja %": 100 * ((g.p_sobre > .5) == (g.sobre == 1)).mean(),
            "AUC pico": roc_auc_score(g.pico, g.p_pico) if g.pico.nunique() == 2 else np.nan,
            "cob80 %": 100 * g.cob80.mean(), "cob50 %": 100 * g.cob50.mean(), "cob90 %": 100 * g.cob90.mean(),
            "error <=10 %": 100 * (g.ape <= .10).mean(), "MAPE %": 100 * g.ape.mean(), "pinball %": 100 * g.pinball.mean(),
            "n": len(g)})
    return P, P.groupby("modelo").apply(tabla)


def leer(modelos=None, exp="e0", anio=False, vara="calendario"):
    """Predicciones de un experimento. Los umbrales de 'sube' y 'pico' son siempre los del control de E0,
    para que todos los experimentos se midan contra la misma vara."""
    car = EXPERIMENTOS[exp]["carpeta"] / ("anio" if anio else "")
    fs = sorted(car.glob("*.parquet"))
    fs = [f for f in fs if not f.stem.startswith("_") and (modelos is None or f.stem in modelos)]
    P = pd.concat([pd.read_parquet(f) for f in fs]).assign(exp=exp)
    return P, pd.read_parquet(SALIDA / ("_umbrales.parquet" if vara == "calendario" else "_umbrales_rapido.parquet"))


if __name__ == "__main__":
    warnings.filterwarnings("ignore")
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", default="e0", choices=list(EXPERIMENTOS))
    ap.add_argument("--modelos", nargs="*", default=FASE_A)
    ap.add_argument("--anio", action="store_true", help="prueba 2: el ano a ciegas")
    ap.add_argument("--cada", type=int, default=1, help="un origen de cada N dias; el archivo y el modelo llevan _cadaN")
    a = ap.parse_args()
    usar(a.exp); car = EXP["carpeta"] / ("anio" if a.anio else ""); car.mkdir(parents=True, exist_ok=True)
    y, cal = cargar()
    if a.exp == "e0" and not a.anio and not (SALIDA / "_umbrales.parquet").exists():
        umbrales(y, cal).to_parquet(SALIDA / "_umbrales.parquet")
    if a.exp == "e0" and not a.anio and not (SALIDA / "_umbrales_rapido.parquet").exists():
        umbrales(y, cal, ControlRapido).to_parquet(SALIDA / "_umbrales_rapido.parquet")
    for m in a.modelos:
        t = time.time(); print(f"{a.exp} {m}{' (ano a ciegas)' if a.anio else ''}...", flush=True)
        try:
            d = anio_a_ciegas(m, y, cal) if a.anio else rodar(m, y, cal, avisar=lambda s: print(s, flush=True), cada=a.cada)
            sufijo = f"_cada{a.cada}" if a.cada > 1 else ""
            d.assign(modelo=d.modelo + sufijo).to_parquet(car / f"{m}{sufijo}.parquet")
            print(f"{a.exp} {m} listo en {time.time() - t:.0f} s", flush=True)
        except Exception as e:
            import traceback; traceback.print_exc(); print(f"{a.exp} {m} FALLO: {e!r}", flush=True)
