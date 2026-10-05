import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("23_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 23 — El catálogo de variables y su validación en varios años

## Para qué es este cuaderno

Los cuadernos 17 a 21 revisaron, probaron y validaron variables y fuentes nuevas. El propietario pidió dos cosas:
- **un resumen de todas las variables que quedan, y por qué**;
- **validarlas en diferentes tiempos y contextos de la historia**, no solo en 2026, con probabilidades
  razonables: «no es Dios»; 60-70 % es creíble, 80-90 % no.

**Partes del cuaderno:**
1. El **catálogo**: cada variable, su fuente, si se conoce al predecir, su evidencia y la decisión.
2. **Qué contextos ve el modelo** en su entrenamiento: El Niño, La Niña, crisis de la red, COVID…
3. **Por qué no se mezclan días al azar** entre entrenamiento y prueba: se demuestra con datos.
4. **Lo que dice la investigación** sobre cómo entrenar y validar bien este tipo de pronóstico.
5. **Un error de método** del motor que la validación en varios años sacó a la luz, y su corrección.
6. **La validación de cada capa en cuatro años** (2023, 2024, 2025, 2026), cada uno entrenado solo con lo
   anterior (fila `validacion_por_capas_multianual`, fijada antes de calcular).
7. **Las técnicas de entrenamiento** que propone la literatura, probadas una por una (fila
   `tecnicas_de_entrenamiento`).
8. **Qué tan seguras son las probabilidades** que emite el modelo, y si se cumplen.
""")
code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd, lightgbm as lgb
from matplotlib import pyplot as plt
import pronostico as pr, indices as ix
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
""")

md(r"""
---
# 1. El catálogo: las variables que quedan y por qué
""")
code(r"""
CAT = pd.DataFrame([
 # capa, variable, que mide, fuente, al predecir, desde, evidencia, decision
 ["Calendario", "día de la semana, festivo, puente, víspera, día después, quincena, vacaciones, Semana Santa, Navidad, fin de año, regreso a clases", "el ritmo social", "calendario de Colombia", "por adelantado", "2020", "72 % de la variación diaria (cuaderno 14)", "ENTRA: es el control"],
 ["Calendario", "COVID fuerte y parcial, paro nacional 2021", "episodios únicos", "fechas fijas", "por adelantado", "2020", "hunden la notificación de todo (cuaderno 20)", "ENTRA como marca, no como predictor"],
 ["Estación", "3 armónicos del año", "la época del año", "la fecha", "por adelantado", "—", "mayo concentra picos (cuaderno 14)", "ENTRA"],
 ["Nivel", "media de 28 días", "el nivel de la red", "triage del hospital", "hasta ayer", "2020", "sigue los escalones (cuaderno 15)", "ENTRA"],
 ["Memoria", "desvío de la última semana, del último día y del mismo día de la semana pasada", "la inercia de corto plazo", "triage del hospital", "hasta ayer", "2020", "autocorrelación de +0,26 a 1 día (cuaderno 14)", "ENTRA"],
 ["Clima", "4 índices de estado (soleado y seco frente a nublado y húmedo; cálido; viento; sol con humedad)", "cómo está el tiempo", "ERA5 + NASA POWER", "hasta ayer (observado)", "2010", "IRA de la ciudad +6-7 %; triage +1-2 % (cuaderno 17)", "ENTRA"],
 ["Clima", "3 índices de cambio brusco", "si el tiempo cambió de golpe", "ERA5 + NASA POWER", "hasta ayer", "2010", "81 % de los cambios (cuaderno 17)", "ENTRA"],
 ["Clima", "racha seca; días desde la última semana muy lluviosa", "sequía y lluvia reciente", "NASA POWER", "hasta ayer", "2010", "mayores +4,6 % tras lluvia; adultos +2,8 % tras racha seca (cuaderno 21)", "ENTRA"],
 ["Clima", "lluvia del ERA5", "—", "Open-Meteo Archive", "—", "—", "10 veces lo real, correlación −0,02 (cuaderno 17)", "FUERA: está rota"],
 ["Salud pública", "familia respiratoria (IRA total, 0-4, 60+)", "la ola respiratoria de la ciudad", "SIVIGILA + Power BI", "semana anterior", "2012", "mueve el respiratorio del hospital +10-14 % (cuaderno 13)", "ENTRA"],
 ["Salud pública", "violencias y agresiones; salud mental e intoxicaciones; materno-perinatal; inmunoprevenibles", "las otras urgencias de la ciudad", "SIVIGILA + Power BI", "semana anterior", "2015", "familias casi independientes, r ≤ 0,19 (cuaderno 19)", "ENTRA"],
 ["Salud pública", "familia digestiva (EDA)", "diarrea de la ciudad", "solo microdatos", "NO: ~8 meses tarde", "2012", "+15,7 % con sequía (cuaderno 19)", "FUERA hasta tener fuente a tiempo"],
 ["Salud pública", "IRAG hospitalizada", "gravedad respiratoria", "microdatos / rutinaria", "no empalma en 2026", "2012", "—", "FUERA"],
 ["Red de salud", "peso de Nueva EPS y de SURA (28 días)", "el estado de la red", "triage por asegurador", "hasta ayer", "2020", "dos aseguradoras son el 80-90 % (cuaderno 18)", "ENTRA"],
 ["Red de salud", "cambio de 28 días de Nueva EPS y del resto; Herfindahl", "si la red se mueve", "triage por asegurador", "hasta ayer", "2020", "la caída de Nueva EPS es de acceso (cuaderno 18)", "ENTRA"],
 ["Red de salud", "resolución de la Supersalud sobre Nueva EPS (30 días)", "intervenciones y cambios", "Supersalud (capturado)", "fecha pública", "2024", "coincide con el escalón de noviembre de 2025 (cuaderno 18)", "ENTRA"],
 ["Red de salud", "afiliados por EPS en Manizales; uso por afiliado", "tamaño y acceso de cada EPS", "MinSalud (capturado)", "1 mes", "2025-07", "−20 % afiliados y −60 % triage en Nueva EPS (cuaderno 18)", "PENDIENTE: 14 meses de historia"],
 ["Red de salud", "quejas por EPS (PQRD), giros de ADRES", "barreras y pagos", "Supersalud, ADRES", "1-2 meses", "2017 / 2020", "—", "PENDIENTE: sin captura automática"],
 ["Regímenes", "ONI, El Niño, La Niña", "el clima de fondo del año", "NOAA (capturado)", "2 meses de retraso", "1950", "La Niña sube violencias y salud mental; El Niño +3,6 % (cuaderno 20)", "ENTRA; El Niño se prueba prospectivamente"],
 ["Regímenes", "sismo fuerte (7 días)", "sismos M ≥ 4,5 a menos de 150 km", "USGS", "minutos", "2010", "sin efecto, con 40 episodios (cuaderno 20)", "ENTRA (pesa poco)"],
 ["Eventos", "Feria, eventos de Manizales, fiestas de Caldas, días especiales", "aglomeraciones", "calendarios propios", "por adelantado", "2020", "0,5 % de la ganancia (cuaderno 15)", "FUERA del total; la Feria ya se refleja en el calendario"],
 ["Motivo", "motivo de consulta limpio (NLP)", "el desenlace específico", "NLP/", "—", "2025", "es desenlace, no predictor (CLAUDE.md)", "PENDIENTE: corpus sin procesar"],
], columns=["capa", "variable", "qué mide", "fuente", "¿se sabe al predecir?", "desde", "evidencia", "decisión"])
pd.set_option("display.max_colwidth", 120)
CAT
""")
lec("catalogo")

md(r"""
---
# 2. Qué contextos ve el modelo cuando aprende

Para cada año de prueba: cuántos días de cada contexto tenía el entrenamiento (todo lo anterior, desde 2020) y
cuántos trae el año que se predice.
""")
code(r"""
pr.usar("h"); y, cal = pr.cargar()
PAS = ix.contexto_holistico(cal.index).reindex(y.index)
R = ix.regimenes_diarios().reindex(y.index)
ctx = pd.DataFrame({"El Niño": R.el_nino, "La Niña": R.la_nina, "COVID": R.covid_fuerte + R.covid_parcial, "crisis de la red": R.crisis_red,
                    "ola respiratoria (> +1 desv.)": (PAS.ext_h_fam_respiratoria > 1).astype(float), "racha seca > 14 días": (PAS.ext_h_racha_seca > 14).astype(float),
                    "temporada de Navidad": cal.reindex(y.index).es_temporada_navidad, "vacaciones escolares": cal.reindex(y.index).es_vacaciones_escolares})
filas = []
for a in [2023, 2024, 2025, 2026]:
    tr, te = ctx.loc[:f"{a - 1}-12-31"], ctx.loc[f"{a}-01-01":f"{a}-12-31"]
    filas.append(pd.Series({**{f"{c} · entrena": int(tr[c].sum()) for c in ctx}, **{f"{c} · prueba": int(te[c].sum()) for c in ctx}}, name=a))
cob = pd.DataFrame(filas)
cob.T.rename(columns=str)
""")
lec("contextos")

md(r"""
---
# 3. Por qué no se mezclan días al azar

La propuesta del propietario era «datos escogidos y aleatorios». Se prueban las dos formas con el mismo modelo
(LightGBM, mediana a 1 día) y dos juegos de entradas (la base, y la base con todo el contexto H):
- **aleatoria:** el 80 % de los días hasta el año de prueba para entrenar y el 20 % restante, mezclado, para probar;
- **temporal:** entrenar con todo lo anterior y probar el año entero, como pasaría en la realidad.

Se hace hasta 2025 y hasta 2026, y con los dos objetivos del árbol (el conteo, y el desvío frente al nivel: ver
sección 5). «Acierta» es acertar si el día queda por encima o por debajo de lo que espera el calendario.
""")
code(r"""
import anual
D = anual.preparar(); X, ly = D["X"], D["ly"]
def prueba(cols, ia, ib, rel):
    off_a = X.nivel.values[ia] if rel else 0; off_b = X.nivel.values[ib] if rel else 0
    C = [c for c in cols if not (rel and c == "nivel")]
    m = lgb.LGBMRegressor(objective="l1", **pr.LightGBM.PARAM).fit(X[C].values[ia], ly.values[ia] - off_a)
    p = np.exp(m.predict(X[C].values[ib]) + off_b); r = np.exp(ly.values[ib])
    Z = lambda i: np.c_[np.ones(len(i)), X[anual.CTRL(X)].values[i]]
    b, *_ = np.linalg.lstsq(Z(ia), ly.values[ia], rcond=None); esp = np.exp(Z(ib) @ b)
    return 100 * np.mean(np.abs(p - r) / r), 100 * np.mean((p > esp) == (r > esp))
fil = []
for fin in ["2025", "2026"]:
    n_ini = X.index.get_loc(X.loc[f"{fin}-01-01":].index[0]); n_fin = len(X.loc[:f"{fin}-12-31"])
    idx = np.random.default_rng(0).permutation(n_fin); k = int(.8 * n_fin)
    parts = {"aleatoria 80/20": (np.sort(idx[:k]), np.sort(idx[k:])), "temporal (la real)": (np.arange(n_ini), np.arange(n_ini, n_fin))}
    for juego in ["base", "base + todo H"]:
        cols = [c for c in X.columns if D["capa"][c] in anual.JUEGOS[juego]]
        for nom, (ia, ib) in parts.items():
            for rel in [False, True]:
                mp, ac = prueba(cols, ia, ib, rel)
                fil.append({"prueba hasta": fin, "objetivo del árbol": "desvío del nivel" if rel else "conteo", "partición": nom, "juego": juego, "MAPE %": mp, "acierta %": ac})
pd.DataFrame(fil).pivot_table(index=["prueba hasta", "objetivo del árbol", "partición"], columns="juego", values=["acierta %", "MAPE %"]).round(1)
""")
lec("aleatorio")

md(r"""
---
# 4. Lo que dice la investigación: cómo entrenar bien este tipo de pronóstico

El propietario pidió basar el entrenamiento en investigación, no en intuición. Se revisó la literatura de dos
frentes: **cómo validar y muestrear series de tiempo sin filtrar el futuro**, y **cómo se pronostican las urgencias
con variables externas y cómo se calibran sus probabilidades**. Lo que sigue es lo que se aplica aquí; las
referencias completas están en `docs/CONTEXTO.md` (entrada del 2026-10-05).

| Técnica | Qué es, en simple | Fuente | ¿Se aplica aquí? |
|---|---|---|---|
| **Origen rodante / año a ciegas** | Entrenar con el pasado y predecir hacia adelante; nunca al revés | Tashman 2000; Cerqueira, Torgo y Mozetič 2020 | **Sí, es la prueba final.** Con series que cambian de nivel, es la única estimación honesta |
| Partición aleatoria (k-fold) | Mezclar días de entrenamiento y prueba | Bergmeir, Hyndman y Koo 2018 | **No.** Solo vale si el residuo no tiene memoria, la serie es estable y no hay variables externas; aquí falla en las tres (memoria +0,42) |
| k-fold por bloques con purga y embargo | Bloques de meses, con 35 días de colchón alrededor de la prueba | López de Prado 2018; Racine 2000 | Solo para **afinar** dentro del entrenamiento, nunca para reportar |
| **Objetivo relativo al nivel** | Que el árbol aprenda «cuánto se aparta del nivel» y no el conteo | Hewamalage, Ackermann y Bergmeir 2023 | **Sí: corrige un error del motor** (sección 5) |
| Peso bajo al periodo COVID | Que la interrupción no enseñe una forma anual falsa | Hyndman y Rostami-Tabar 2025 | Se prueba (T1) |
| Peso a lo reciente | Con rupturas, el pasado lejano vale menos | Pesaran, Pick y Pranovich 2013 | Se prueba (T2) |
| **Peso a contextos raros** | El equivalente legítimo de «datos escogidos»: los días raros pesan más, sin mirar el futuro | Sugiyama, Krauledat y Müller 2007 (ponderación) | Se prueba (T3) |
| **Remuestreo por bloques (bagging)** | El «aleatorio» legítimo: se rehace el entrenamiento con bloques de 28 días al azar y se promedia | Bergmeir, Hyndman y Benítez 2016 | Se prueba (T4) |
| Calibración de Platt | Corrige probabilidades exageradas con el año anterior | Niculescu-Mizil y Caruana 2005; Kull et al. 2017 | Se prueba; la isotónica no, con pocos días sobreajusta |
| Combinar por promedio de cuantiles | El promedio simple es difícil de batir | Wang, Hyndman et al. 2023; Lichtendahl et al. 2013 | **Ya en uso** (cuaderno 22) |
| Modelo global por bandas o aseguradores | Un solo modelo para todas las series, con más ejemplos de lo raro | Montero-Manso y Hyndman 2021 | Pendiente: siguiente paso |
| Diebold-Mariano, Giacomini-White, conjunto de confianza de modelos | Decidir si una diferencia es real | Diebold y Mariano 1995; Giacomini y White 2006; Hansen, Lunde y Nason 2011 | Remuestreo por bloques ya en uso; Giacomini-White pendiente |

**Lo que dice la literatura de urgencias, que hay que tener presente al leer los resultados:**
- El calendario explica entre 31 y 75 % de la variación y deja errores de 4 a 14 % (Wargon et al. 2009, 9 estudios).
  Nuestro 72 % y 10 % están en ese rango: **el control no es débil**.
- **Añadir el clima casi nunca mejora el error del total**: São Paulo (Marcilio et al. 2013: 10,8 % sin temperatura,
  11,5 % con ella), Porto Alegre (Calegari et al. 2016), Londres (Vollmer et al. 2021), Tampere (Tuominen et al.
  2022). El clima se ve en la serie respiratoria y en grupos de edad, no en el total.
- Lo que **sí** ayuda de forma consistente es el **estado del sistema**: avisos de ambulancia (−6 puntos de error,
  Asheim et al. 2019), camas de la red (Tuominen et al. 2022), epidemia de influenza (Murtas et al. 2022).
- Solo 5 de 30 estudios dan intervalos de predicción (Petravić et al. 2025). Dar distribuciones, como aquí, ya es
  más de lo habitual.
""")

md(r"""
---
# 5. Un error de método que destapó la validación en varios años

La primera corrida de la validación anual (la regla preregistrada, tal cual) dio una base con **BSS de −105 % en
2024** y una cobertura del 80 % de solo 33 %. La causa: el LightGBM del motor aprende el **conteo** (su
logaritmo) y recibe el nivel como una entrada más. **Un árbol no puede predecir un valor que nunca vio**: cuando el
nivel de 2024 superó todo lo anterior (226 triages por día), el modelo se quedó pegado al techo de 2023. Con el
reentrenamiento semanal de los cuadernos 15-22 el problema casi no se nota, porque el árbol se pone al día cada
semana; congelado un año, aparece entero.

La corrección (T0) es que el árbol aprenda **el desvío frente al nivel**, log(y) − nivel, y que el nivel se sume
después. Se registró como desviación antes de seguir (fila `tecnicas_de_entrenamiento`).
""")
code(r"""
import anual
P = pd.concat([pd.read_parquet(RAIZ / "salidas/pronostico/anual_tecnicas.parquet"), pd.read_parquet(RAIZ / "salidas/pronostico/anual_capas.parquet")])
M = anual.metricas(P[P["año"] >= 2023])
ver = ["acierta sube/baja %", "BSS sube %", "cob80 %", "MAPE %"]
M.loc[(["original", "T0"], ["base", "base + todo H"]), ver].unstack("año").round(1)
""")
lec("metodo")

md(r"""
---
# 6. La validación de cada capa en cuatro años (con el método corregido)

Para cada año de prueba se entrena con todo lo anterior. **Una capa «aporta» si mejora la probabilidad de «sube»
frente a la base en al menos 3 de los 4 años** (regla preregistrada).
""")
code(r"""
B = M.loc["T0", "BSS sube %"].unstack("año").reindex(list(anual.JUEGOS))
mejora = B.sub(B.loc["base"], axis=1)
veredicto = pd.DataFrame({"años en que mejora a la base": (mejora > 0).sum(axis=1), "mejora media del BSS (puntos)": mejora.mean(axis=1).round(1),
                          "¿aporta? (≥ 3 de 4 años)": np.where((mejora > 0).sum(axis=1) >= 3, "SÍ", "no")}).drop("base")
fig, ax = plt.subplots(figsize=(10, 4))
for juego, c in zip(anual.JUEGOS, [MUDO, AZUL, ROJO, VERDE, AMARILLO, VIOLETA]):
    ax.plot(B.columns, B.loc[juego], "-o", color=c, lw=2.4 if juego in ("base", "base + todo H") else 1.4, label=juego)
ax.axhline(0, color=TINTA2, lw=.8); ax.set_xticks(B.columns); ax.set_ylabel("BSS de «sube» (%)"); ax.legend(fontsize=8, ncol=2)
ax.set_title("La calidad de la probabilidad, año por año, con cada capa"); plt.tight_layout(); plt.show()
display(veredicto)
M.loc["T0", ["acierta sube/baja %", "BSS sube %", "BSS pico %", "cob80 %", "MAPE %"]].unstack("año").reindex(list(anual.JUEGOS)).round(1)
""")
lec("capas")

md(r"""
---
# 7. Las técnicas de entrenamiento de la investigación, una por una

| | Técnica |
|---|---|
| T0 | Objetivo relativo al nivel (el método corregido) |
| T1 | T0 + peso 0,1 a los días COVID |
| T2 | T0 + más peso a lo reciente (vida media de 1,5 años) |
| T3 | T0 + peso doble a los contextos raros (crisis de la red, ola respiratoria, racha seca) |
| T4 | T0 + remuestreo de bloques de 28 días, 10 veces, y promedio |
| T5 | Todo junto |

Regla preregistrada: una técnica se adopta si mejora el BSS de «sube» frente a T0 en al menos 3 de los 4 años con
todo el contexto H, sin sacar la cobertura del 80 % de 70-88 %.
""")
code(r"""
TEC = ["T0", "T1", "T2", "T3", "T4", "T5"]
filas = []
for j in ["base", "base + salud pública", "base + todo H"]:
    b = M.loc[(TEC, j), "BSS sube %"].unstack("año").droplevel(1)
    d = b.sub(b.loc["T0"], axis=1)
    cob = M.loc[(TEC, j), "cob80 %"].groupby(level=0).mean()
    for t in TEC[1:]:
        filas.append({"juego": j, "técnica": t, **{a: round(b.loc[t, a], 1) for a in b.columns}, "años que mejora a T0": int((d.loc[t] > 0).sum()),
                      "mejora media (puntos)": round(d.loc[t].mean(), 1), "cob80 media %": round(cob[t], 1),
                      "¿se adopta?": "SÍ" if (d.loc[t] > 0).sum() >= 3 and 70 <= cob[t] <= 88 else "no"})
TT = pd.DataFrame(filas).set_index(["juego", "técnica"])
display(M.loc[("T0", ["base", "base + salud pública", "base + todo H"]), "BSS sube %"].unstack("año").round(1))
TT
""")
lec("tecnicas")

md(r"""
---
# 8. ¿Qué tan seguras son las probabilidades, y se cumplen?

El propietario lo dijo claro: un modelo que asegura 80-90 % no es creíble. Aquí se ve qué probabilidades emite el
modelo, si se cumplen (calibración) y qué pasa si se recalibran con el año anterior (Platt).
""")
code(r"""
PC = anual.platt(P)
MC = anual.metricas(PC, "p_cal")
cmp_ = pd.DataFrame({"Brier sin calibrar": M["Brier sube"], "Brier con Platt": MC["Brier sube"]}).dropna()
cmp_["mejora"] = cmp_["Brier sin calibrar"] > cmp_["Brier con Platt"]
cal_v = cmp_.groupby(level=[0, 1]).agg(**{"años que mejora": ("mejora", "sum")})
cal_v["¿se adopta?"] = np.where(cal_v["años que mejora"] >= 3, "SÍ", "no")
display(cal_v)
fig, axes = plt.subplots(1, 3, figsize=(16, 4.2))
D_ = PC[(PC.tecnica == "T0") & (PC.juego == "base + todo H")]
for col, c, et in [("p", MUDO, "sin calibrar"), ("p_cal", VIOLETA, "con Platt")]:
    axes[0].hist(D_[col], bins=np.linspace(0, 1, 21), color=c, alpha=.55, label=et)
    g = D_.groupby(pd.cut(D_[col], np.linspace(0, 1, 11))).agg(p=(col, "mean"), f=("sube", "mean"), n=("sube", "size")).query("n >= 20")
    axes[1].plot(g.p, g.f, "-o", color=c, lw=2, label=et)
for x in (.3, .7): axes[0].axvline(x, color=ROJO, ls=":")
axes[0].set_xlabel("probabilidad de «sube»"); axes[0].set_ylabel("días"); axes[0].legend(); axes[0].set_title("Qué tan seguro dice estar (T0, todo H, 2023-2026)")
axes[1].plot([0, 1], [0, 1], color=MUDO, ls="--"); axes[1].set_xlabel("probabilidad emitida"); axes[1].set_ylabel("frecuencia con que subió"); axes[1].legend()
axes[1].set_title("¿Se cumple lo que dice?")
seg = np.abs(D_.p_cal - .5) + .5
ac = pd.DataFrame({"ok": ((D_.p_cal > .5) == (D_.sube == 1)).values}).groupby(pd.cut(seg.values, [.5, .6, .7, .8, 1.])).ok.agg(["mean", "size"])
axes[2].bar(range(len(ac)), 100 * ac["mean"], color=AZUL); axes[2].set_xticks(range(len(ac))); axes[2].set_xticklabels(["50-60 %", "60-70 %", "70-80 %", "> 80 %"])
for i, (a, n) in enumerate(zip(ac["mean"], ac["size"])): axes[2].text(i, 100 * a + 1, f"{100 * a:.0f} %\n{n} días", ha="center", fontsize=8)
axes[2].set_xlabel("seguridad del modelo (con Platt)"); axes[2].set_ylabel("acierto real %"); axes[2].set_title("Cuando dice estar X seguro, ¿acierta X?")
plt.tight_layout(); plt.show()
MC.loc[("T0", ["base", "base + todo H"]), ["acierta sube/baja %", "BSS sube %", "P > 0,70 %", "P < 0,30 %"]].unstack("año").round(1)
""")
lec("probabilidades")

md(r"""
---
# 9. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "23_catalogo_y_validacion_multianual.ipynb")
print("ok", len(C))
