import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("21_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(sin escribir: {k})*"))

md(r"""
# 21 — El triage por bandas de edad: qué contexto actúa en cada parte

## Pregunta y motivo

Los cuadernos 17, 19 y 20 muestran lo mismo desde tres ángulos: el clima, las enfermedades de la ciudad y El Niño
mueven algo medible, pero los efectos que se ven en el triage total son pequeños, en el orden del 1 al 3 %, bajo un ruido semanal
del 6 %, y no son una versión reducida de los de la ciudad (cuaderno 17). El argumento de la partición es de aritmética: si una parte del triage pesa el 10 % y sube un 30 %, el total sube un 3 %.
Este cuaderno pregunta si, al repartir el triage en sus partes, cada factor externo reaparece con su tamaño
real en la parte donde actúa, y qué firma deja en cada una: con qué rezago, en qué sentido y con qué estabilidad
entre 2022-2024 y 2025-2026.

Se recorren cinco familias de factores: el clima, la salud pública de la ciudad, los regímenes (El Niño y La Niña),
los episodios locales (Feria, deslizamientos, el terremoto de 2026) y la red de aseguradoras. Cada una tiene su
reloj: el clima y la enfermedad actúan con semanas de rezago; la Feria y el terremoto, en días; la red, en meses.

## Particiones disponibles

| Partición | Cobertura | Fuente |
|---|---|---|
| **Bandas de edad** (0-4, 5-14, 15-44, 45-64, 65+) | 100 %, desde 2020 | `triage_edad.parquet` |
| **Obstétrico frente al resto** | 100 %, desde 2020 | `triage_nivel.parquet` (niveles -G) |
| Diagnósticos | 41 % (solo los ingresos) | `perfil_dx_diario` |
| Motivo de consulta (NLP) | 2025-2026, corpus sin procesar completo | `NLP/` |

Los diagnósticos no sirven como partición porque solo cubren a los pacientes que ingresan. El cruce de edad por
condición obstétrica no existe en los datos agregados disponibles, de modo que el análisis usa las dos particiones
por separado.
""")
code(r"""
import sys, pathlib, warnings
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import re
import numpy as np, pandas as pd, statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from matplotlib import pyplot as plt
from IPython.display import display
import indices as ix
import desenlace as de
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
BANDAS = ["0-4", "5-14", "15-44", "45-64", "65+"]
COLB = [MAGENTA, AMARILLO, AZUL, AQUA, VIOLETA]
dias = pd.date_range("2020-01-01", "2026-09-20")
ed = pd.read_parquet(RAIZ / "salidas/triage_edad.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
E = ed.pivot_table(index="dia", columns="banda", values="n", aggfunc="sum").reindex(dias).fillna(0)
nv = pd.read_parquet(RAIZ / "salidas/triage_nivel.parquet").assign(dia=lambda d: pd.to_datetime(d.dia))
obst = nv[nv.nivel.str.endswith("-G")].groupby("dia").n.sum().reindex(dias).fillna(0)
tot = nv.groupby("dia").n.sum().reindex(dias).fillna(0)
P = pd.DataFrame({"edad 0-4": E["0-4"], "edad 5-14": E["5-14"], "edad 15-44": E["15-44"], "edad 45-64": E["45-64"], "edad 65+": E["65-+"],
                  "obstétrico": obst, "no obstétrico": tot - obst, "TOTAL": tot})
P.loc["2024-03-19":"2024-03-21"] = np.nan
peso = (P.loc["2022":"2024"].mean() / P.loc["2022":"2024", "TOTAL"].mean() * 100).round(1)
print("Peso de cada parte en 2022-2024 (%):"); peso.drop("TOTAL").to_frame("% del triage")
""")
code(r"""
# La suma de las cinco bandas frente al total y las filas sin edad
sin_edad = ed[ed.banda.eq("sin edad")].set_index("dia").n.reindex(dias).fillna(0)
suma5 = P[["edad 0-4", "edad 5-14", "edad 15-44", "edad 45-64", "edad 65+"]].sum(axis=1)
print("Triages sin banda de edad, 2022-2026:", int(sin_edad.loc["2022":].sum()), "de", int(tot.loc["2022":].sum()))
print("Suma de las 5 bandas menos el total (2022-2026, días válidos):", int((suma5 - P.TOTAL).loc["2022":].sum()))
""")

md(r"""
# 1. La estación de cada parte

Cada serie se lleva a promedio mensual de 2022 a 2025, se le resta el nivel de su año (en logaritmo) y se promedia
por mes del calendario. El resultado es la forma anual de la parte, en porcentaje frente a su propia media. La
amplitud es la distancia entre el mes más alto y el más bajo.
""")
code(r"""
x = np.log(P.loc["2022":"2025"].resample("MS").mean())
forma = (np.exp((x - x.groupby(x.index.year).transform("mean")).groupby(x.index.month).mean()) - 1) * 100
fig, ax = plt.subplots(figsize=(12, 4.2))
im = ax.imshow(forma.T.values, cmap="RdBu_r", vmin=-30, vmax=30, aspect="auto")
ax.set_xticks(range(12), MESES); ax.set_yticks(range(forma.shape[1]), forma.columns); ax.grid(False)
for (i, j), v in np.ndenumerate(forma.T.values): ax.text(j, i, f"{v:+.0f}", ha="center", va="center", fontsize=8)
plt.colorbar(im, ax=ax, label="% frente a la media del año"); ax.set_title("Las bandas pediátricas tienen una estación mucho más marcada que el total (2022-2025)")
plt.tight_layout(); plt.show()
amp = (forma.max() - forma.min()).round(1).rename("amplitud de la estación (puntos %)")
pk = forma.idxmax().map(lambda m: MESES[m - 1]).rename("mes más alto"); vl = forma.idxmin().map(lambda m: MESES[m - 1]).rename("mes más bajo")
pd.concat([amp, pk, vl], axis=1)
""")
lec("estacion")

md(r"""
# 2. La composición por edad y su cambio en el tiempo

Antes de buscar el efecto de un factor conviene saber si la composición del triage por edad es estable. Si lo fuera,
las bandas serían copias a escala del total y la partición no aportaría nada.
""")
code(r"""
Y = P.groupby(P.index.year).mean()
compo = (Y[[f"edad {b}" for b in BANDAS]].div(Y[[f"edad {b}" for b in BANDAS]].sum(axis=1), axis=0) * 100).round(1)
compo.columns = BANDAS
dia = Y[[f"edad {b}" for b in BANDAS] + ["TOTAL"]].round(1); dia.columns = BANDAS + ["TOTAL"]
cambio = ((dia.loc[2026] / dia.loc[2024] - 1) * 100).round(1).rename("2026 frente a 2024 (%)")
fig, ax = plt.subplots(1, 2, figsize=(12.5, 4))
for b, col in zip(BANDAS, COLB):
    ax[0].plot(dia.index[1:], (dia[b] / dia.loc[2024, b] * 100).loc[2021:], marker="o", color=col, label=b)
ax[0].axhline(100, color=MUDO, lw=.8); ax[0].set_ylabel("triages/día, índice 2024 = 100"); ax[0].legend(title="banda", ncol=2)
ax[0].set_title("Desde 2024 caen los adultos y los mayores; los menores de 5 años no")
compo.loc[2021:].plot(kind="bar", stacked=True, ax=ax[1], color=COLB, width=.75, legend=False)
ax[1].set_ylabel("% del triage con edad"); ax[1].set_xlabel(""); ax[1].tick_params(axis="x", rotation=0)
ax[1].set_title("El peso de los extremos de la vida crece"); ax[1].grid(False)
ax[1].legend(BANDAS, title="banda", ncol=5, loc="upper center", bbox_to_anchor=(.5, -.1))
plt.tight_layout(); plt.show()
print("Triages/día por año y banda (2026 hasta el 20-sep):"); display(dia)
print("Composición (%):"); display(compo); print(cambio.to_string())
""")
lec("composicion")

md(r"""
# 3. El contexto externo, parte por parte

## Diseño

Cada parte se lleva a su residuo semanal en logaritmo: sin calendario (festivo, puente, Semana Santa, Navidad, fin
de año), sin el nivel de cada año y sin los escalones de la red (abril de 2024, noviembre de 2025, marzo y julio de
2026), igual que en el desenlace común de los cuadernos 12 y 13. Se conserva la estación, porque el clima y la
enfermedad pueden explicarla. Semanas completas, de domingo a sábado.

Contra el residuo de cada parte se barren 65 pruebas (variable por rezago):

- 6 familias de enfermedad de la ciudad, con rezago de 0 a 2 semanas (18 pruebas);
- 4 índices de estado del clima, 3 de cambio brusco y 2 rachas (racha seca, días desde la última semana muy
  lluviosa), con rezago de 0 a 4 semanas (45 pruebas);
- El Niño y La Niña (2 pruebas).

El efecto se expresa por desviación típica de la variable, con mes del año fijo y errores HAC de 4 rezagos. La
corrección de Benjamini-Hochberg se aplica dentro de cada parte. **Se descubre con 2022-03 a 2024-12 y se
confirma con 2025-01 a 2026-09**, que no participan en la selección, con la misma estandarización. Las familias
de enfermedad se calculan con microdatos que llegan hasta diciembre de 2025, así que en la confirmación solo
cubren 2025.
""")
code(r"""
cal = (pd.read_csv(RAIZ / "calendarios/calendario_Colombia.csv", parse_dates=["fecha"]).set_index("fecha")
         .reindex(dias)[de.CAL].apply(pd.to_numeric, errors="coerce").fillna(0))
completas = de._semana(P["TOTAL"].notna().astype(int)) == 7
cal_w = de._semana(cal).loc[de.INICIO:de.FIN]
RESID_F = pd.DataFrame({c: de._residuo(de._semana(P[c]).where(completas).loc[de.INICIO:de.FIN], cal_w) for c in P})
# el residuo de descubrimiento se ajusta solo con 2022-03 a 2024-12, como en el desenlace original
cal_d = cal_w.loc[:"2024-12-29"]
RESID = pd.DataFrame({c: de._residuo(de._semana(P[c]).where(completas).loc[de.INICIO:"2024-12-29"], cal_d) for c in P})
FAM = ix.familias_enfermedad(); IC = ix.indices_clima()
REG = ix.regimenes_diarios()[["el_nino", "la_nina"]].resample("W-SAT").mean(); REG.index -= pd.Timedelta(days=6)
X = {}
for f in FAM:
    for L in range(3): X[f"{f} (−{L} sem)"] = FAM[f].shift(L)
for c in IC:
    for L in range(5): X[f"{c} (−{L} sem)"] = IC[c].shift(L)
for c in REG: X[c] = REG[c]
X = pd.DataFrame(X)
def barrido(y, minimo=60):
    idx = y.dropna().index; filas = []
    mes = pd.get_dummies(pd.Index(idx.month), prefix="m", drop_first=True).set_index(idx).astype(float)
    for c in X:
        xs = (X[c] - X[c].loc[:"2024"].mean()) / X[c].loc[:"2024"].std()
        D = pd.concat([y.rename("y"), xs.rename("x"), mes], axis=1).loc[idx].dropna()
        if len(D) < minimo or D.x.std() == 0: continue
        r = sm.OLS(D.y, sm.add_constant(D.drop(columns="y"))).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        filas.append({"variable": c, "efecto %": 100 * (np.exp(r.params["x"]) - 1), "p": r.pvalues["x"], "n": len(D)})
    T = pd.DataFrame(filas); T["q"] = multipletests(T.p, method="fdr_bh")[1]; return T
RB = {c: barrido(RESID[c]) for c in RESID}
RC = {c: barrido(RESID_F[c].loc["2025-01-05":], minimo=50) for c in RESID_F}
print("Semanas de descubrimiento:", RESID["TOTAL"].notna().sum(), "| de confirmación:", RESID_F["TOTAL"].loc["2025-01-05":].notna().sum(),
      "| pruebas por parte:", len(RB["TOTAL"]))
res = pd.DataFrame({c: {"pruebas": len(T), "p < 0,05": int((T.p < .05).sum()), "sobreviven BH": int((T.q < .10).sum()),
                        "mayor efecto que sobrevive %": round(T.loc[T.q < .10, "efecto %"].abs().max(), 1) if (T.q < .10).any() else np.nan,
                        "ruido semanal (desv. del residuo) %": round(100 * RESID[c].std(), 1)} for c, T in RB.items()}).T
res
""")
lec("barrido")

code(r"""
filas = []
for c, T in RB.items():
    Tc = RC[c].set_index("variable")
    for _, r in T[T.q < .10].sort_values("p").iterrows():
        cc_ = Tc.loc[r.variable] if r.variable in Tc.index else None
        filas.append({"parte": c, "variable": r.variable, "efecto 2022-24 %": round(r["efecto %"], 2), "q": round(r.q, 3),
                      "efecto 2025-26 %": round(cc_["efecto %"], 2) if cc_ is not None else np.nan,
                      "p 2025-26": round(cc_["p"], 3) if cc_ is not None else np.nan,
                      "mismo signo": bool(np.sign(cc_["efecto %"]) == np.sign(r["efecto %"])) if cc_ is not None else np.nan})
S = pd.DataFrame(filas)
S["confirma"] = S["mismo signo"].astype(bool) & (S["p 2025-26"] < .05)
S["se invierte"] = (~S["mismo signo"].astype(bool)) & (S["p 2025-26"] < .05)
resumen = S.groupby("parte").agg(sobreviven=("variable", "count"), mismo_signo=("mismo signo", "sum"),
                                 confirman=("confirma", "sum"), se_invierten_con_p_menor_005=("se invierte", "sum")).reindex(list(P))
print("Lo que sobrevive en 2022-24, mirado en 2025-26:"); display(resumen)
S.sort_values(["parte", "q"]).reset_index(drop=True)
""")
lec("top")

md(r"""
## Qué mide cada índice de clima

Los índices son componentes principales y su signo es arbitrario. Se verifica con la correlación semanal frente a
las variables climáticas de origen, para poder leer el signo de cada efecto.
""")
code(r"""
cc = ix.clima_diario()
sem = lambda s: ix.semana(s)
def corr_con(indice, vars_):
    return {v: round(IC[indice].corr(sem(cc[v])), 2) for v in vars_}
tabla = pd.DataFrame({i: corr_con(i, ["lluvia_7d", "sol_7d", "humedad_7d", "temp_7d", "viento_7d"]) for i in ["estado_1", "estado_2", "estado_3", "estado_4"]})
tabla2 = pd.DataFrame({i: corr_con(i, ["lluvia_cambio", "temp_cambio", "humedad_cambio", "sol_cambio", "viento_cambio"]) for i in ["cambio_1", "cambio_2", "cambio_3"]})
display(tabla); display(tabla2)
""")
lec("indices")

md(r"""
## La firma de cada factor por banda

Para cada variable de base (los rezagos se colapsan) se toma el rezago con menor p en 2022-2024. Esa elección
es del descubrimiento, así que el efecto de 2022-2024 está sobreestimado por construcción. El panel derecho
repite el mismo rezago en 2025-2026, que no participó, y es el que da la medida honesta. Un asterisco marca q < 0,10
en el descubrimiento y p < 0,05 con el mismo signo en la confirmación.
""")
code(r"""
BASE = lambda v: v.split(" (")[0]
LAGDE = lambda v: int(re.search(r"−(\d)", v).group(1)) if "sem)" in v else 0
orden = (list(IC.columns) + list(FAM.columns) + ["el_nino", "la_nina"])
partes = ["edad 0-4", "edad 5-14", "edad 15-44", "edad 45-64", "edad 65+", "TOTAL"]
D1 = pd.DataFrame(index=orden, columns=partes, dtype=float); Q1 = D1.copy(); D2 = D1.copy(); P2 = D1.copy(); LAG = D1.copy()
for c in partes:
    T = RB[c].assign(b=lambda d: d.variable.map(BASE)); Tc = RC[c].set_index("variable")
    for b, g in T.groupby("b"):
        r = g.sort_values("p").iloc[0]; D1.loc[b, c] = r["efecto %"]; Q1.loc[b, c] = r.q
        LAG.loc[b, c] = LAGDE(r.variable)
        if r.variable in Tc.index: D2.loc[b, c] = Tc.loc[r.variable, "efecto %"]; P2.loc[b, c] = Tc.loc[r.variable, "p"]
fig, ax = plt.subplots(1, 2, figsize=(14, 7.2), sharey=True)
for a, M, tit in [(ax[0], D1, "Descubrimiento 2022-03 a 2024-12 (mejor rezago)"), (ax[1], D2, "Confirmación 2025-01 a 2026-09 (mismo rezago)")]:
    im = a.imshow(M.values, cmap="RdBu_r", vmin=-8, vmax=8, aspect="auto"); a.grid(False)
    a.set_xticks(range(len(partes)), [p.replace("edad ", "") for p in partes]); a.set_title(tit, fontsize=10)
    for (i, j), v in np.ndenumerate(M.values):
        if np.isnan(v): continue
        sig = (Q1.values[i, j] < .10) if M is D1 else (Q1.values[i, j] < .10 and P2.values[i, j] < .05 and np.sign(v) == np.sign(D1.values[i, j]))
        a.text(j, i, f"{v:+.1f}" + ("*" if sig else ""), ha="center", va="center", fontsize=8, fontweight="bold" if sig else "normal")
ETQ = {"estado_1": "clima soleado y seco (estado_1)", "estado_2": "clima cálido (estado_2)", "estado_3": "clima ventoso (estado_3)",
       "estado_4": "sol con humedad (estado_4)", "cambio_1": "cambio hacia sol y sequedad (cambio_1)", "cambio_2": "calentamiento brusco (cambio_2)",
       "cambio_3": "cambio de viento (cambio_3)", "racha_seca": "racha seca", "dias_desde_semana_muy_lluviosa": "días desde semana muy lluviosa",
       "respiratoria": "IRA de la ciudad", "digestiva": "enfermedad diarreica", "violencias_y_agresiones": "violencias y agresiones",
       "salud_mental_e_intoxicaciones": "salud mental e intoxicaciones", "materno_perinatal": "materno-perinatal",
       "inmunoprevenibles": "inmunoprevenibles", "el_nino": "El Niño", "la_nina": "La Niña"}
ax[0].set_yticks(range(len(orden)), [ETQ[o] for o in orden], fontsize=8.5)
fig.colorbar(im, ax=ax, shrink=.6, label="efecto por desviación típica (%)")
fig.suptitle("La firma de cada factor cambia con la banda de edad, y casi nada se repite en 2025-2026", fontweight="bold", y=.995)
plt.show()
print("Rezago elegido en el descubrimiento (semanas):"); display(LAG.astype(int).rename(index=ETQ))
""")
lec("firma")

md(r"""
## Las familias de enfermedad en las bandas pediátricas, sin selección de rezago

La hipótesis respiratoria apunta a los niños. Para no depender de un rezago elegido, se muestran los tres rezagos
(0, 1 y 2 semanas) de la IRA y de la enfermedad diarreica de la ciudad en las dos bandas pediátricas, en cada periodo.
""")
code(r"""
filas = []
for c in ["edad 0-4", "edad 5-14"]:
    for fam in ["respiratoria", "digestiva"]:
        for L in range(3):
            v = f"{fam} (−{L} sem)"
            a = RB[c].set_index("variable").loc[v]; b = RC[c].set_index("variable").loc[v]
            filas.append({"banda": c, "familia": ETQ[fam], "rezago": L, "efecto 2022-24 %": a["efecto %"], "p": a.p,
                          "efecto 2025 %": b["efecto %"], "p 2025": b.p, "semanas 2025": int(b.n)})
display(pd.DataFrame(filas).round(3).set_index(["banda", "familia", "rezago"]))
""")
lec("pediatricas")

md(r"""
## Estabilidad año por año de las señales preseleccionadas

El mismo rezago elegido en el descubrimiento se mide en cada año por separado (sin mes fijo, con 40-52 semanas por
año; 2026 llega hasta septiembre). Una señal real debería conservar el signo.
""")
code(r"""
sel = [("edad 65+", "dias_desde_semana_muy_lluviosa"), ("edad 45-64", "dias_desde_semana_muy_lluviosa"), ("edad 15-44", "racha_seca"),
       ("edad 45-64", "racha_seca"), ("edad 65+", "racha_seca"), ("edad 15-44", "digestiva"), ("TOTAL", "racha_seca")]
filas = []
for c, b in sel:
    T = RB[c].assign(b=lambda d: d.variable.map(BASE)); v = T[T.b.eq(b)].sort_values("p").iloc[0].variable
    xs = (X[v] - X[v].loc[:"2024"].mean()) / X[v].loc[:"2024"].std()
    fila = {"parte": c, "variable": v}
    for a in range(2022, 2027):
        D = pd.concat([RESID_F[c].rename("y"), xs.rename("x")], axis=1).loc[str(a)].dropna()
        if len(D) < 25 or D.x.std() == 0: fila[str(a)] = np.nan; continue
        r = sm.OLS(D.y, sm.add_constant(D[["x"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        fila[str(a)] = round(100 * (np.exp(r.params["x"]) - 1), 1)
    filas.append(fila)
pd.DataFrame(filas).set_index(["parte", "variable"])
""")
lec("anual")

md(r"""
# 4. Episodios locales: Feria, deslizamientos y terremoto

Un promedio semanal diluye lo que dura días. Para los episodios con fecha se compara cada banda en la ventana del
episodio con ventanas vecinas del mismo largo (múltiplos de 7 días, para equilibrar los días de la semana). Se
mide la **participación de la banda en el triage del día** (el denominador es el total), que descuenta cualquier
cambio general de volumen, y el cambio del conteo medio.

Los episodios son pocos (6 Ferias, 3 deslizamientos con fecha precisa, 1 terremoto), de modo que se muestran uno
por uno, no como promedio con significancia.
""")
code(r"""
ev = pd.read_csv(RAIZ / "calendarios/eventos_manizales_2020_2026.csv")
fer = ev[ev.nombre_evento.eq("Feria de Manizales") & ev.estado.eq("realizado")][["anio", "fecha_inicio", "fecha_fin"]]
B = P[[f"edad {b}" for b in BANDAS]].copy(); B.columns = BANDAS; B["TOTAL"] = P.TOTAL
def ventana(ini, fin):
    w = B.loc[ini:fin]; return w.mean(), (w[BANDAS].sum() / w[BANDAS].sum().sum() * 100)
filas = []
for _, r in fer.iterrows():
    a, b = pd.Timestamp(r.fecha_inicio), pd.Timestamp(r.fecha_fin)
    m_f, s_f = ventana(a, b); m_p, s_p = ventana(b + pd.Timedelta(days=1), b + pd.Timedelta(days=14))
    for bd in BANDAS + ["TOTAL"]:
        filas.append({"Feria": int(r.anio), "banda": bd, "conteo": 100 * (m_f[bd] / m_p[bd] - 1),
                      "participación": (s_f[bd] - s_p[bd]) if bd != "TOTAL" else np.nan})
F = pd.DataFrame(filas)
M1 = F.pivot(index="banda", columns="Feria", values="conteo").reindex(BANDAS + ["TOTAL"]).round(1)
M2 = F.pivot(index="banda", columns="Feria", values="participación").reindex(BANDAS).round(2)
print("Cambio del conteo medio diario, días de Feria frente a los 14 días siguientes (%):"); display(M1)
print("Cambio de la participación de la banda entre los triages con edad (puntos porcentuales):"); display(M2)
fig, ax = plt.subplots(figsize=(9, 3.8))
for bd, col in zip(BANDAS, COLB):
    ax.plot(M2.columns.astype(str), M2.loc[bd], marker="o", color=col, label=bd)
ax.axhline(0, color=MUDO, lw=.8); ax.set_ylabel("puntos de participación"); ax.set_xlabel("edición de la Feria")
ax.set_title("La composición por edad en la Feria cambia de signo de una edición a otra"); ax.legend(title="banda", ncol=5, loc="lower center")
plt.tight_layout(); plt.show()
""")
lec("feria")

code(r"""
casos = [("Deslizamientos múltiples", "2022-10-20", 14, 14, 0), ("Deslizamientos múltiples", "2025-04-08", 14, 14, 0),
         ("Deslizamientos múltiples", "2026-04-18", 14, 14, 0), ("Terremoto M7,4, días 0-13", "2026-08-10", 28, 14, 0),
         ("Terremoto M7,4, días 14-27", "2026-08-10", 28, 14, 14)]
filas = []
for nombre, f, pre, post, off in casos:
    f = pd.Timestamp(f)
    m_pre, s_pre = ventana(f - pd.Timedelta(days=pre), f - pd.Timedelta(days=1))
    m_po, s_po = ventana(f + pd.Timedelta(days=off), f + pd.Timedelta(days=off + post - 1))
    filas.append({"episodio": f"{nombre} ({f.date()})", **{bd: round(100 * (m_po[bd] / m_pre[bd] - 1), 1) for bd in BANDAS + ["TOTAL"]}})
    filas.append({"episodio": "   participación (puntos)", **{bd: round(s_po[bd] - s_pre[bd], 2) for bd in BANDAS}})
# control: las mismas ventanas del calendario en 2022-2025 (sin terremoto)
ctrl = {"0-13": [], "14-27": []}
for a in range(2022, 2026):
    f = pd.Timestamp(f"{a}-08-10")
    m_pre, s_pre = ventana(f - pd.Timedelta(days=28), f - pd.Timedelta(days=1))
    for k, off in [("0-13", 0), ("14-27", 14)]:
        m_po, _ = ventana(f + pd.Timedelta(days=off), f + pd.Timedelta(days=off + 13))
        ctrl[k].append(100 * (m_po / m_pre - 1))
for k in ctrl:
    C_ = pd.concat(ctrl[k], axis=1)
    filas.append({"episodio": f"Control: mismas fechas 2022-2025, días {k} (promedio)", **{bd: round(C_.loc[bd].mean(), 1) for bd in BANDAS + ["TOTAL"]}})
    filas.append({"episodio": "   mínimo a máximo de los 4 años", **{bd: f"{C_.loc[bd].min():.0f} a {C_.loc[bd].max():.0f}" for bd in BANDAS + ["TOTAL"]}})
EP = pd.DataFrame(filas).set_index("episodio")
print("Cambio del conteo medio diario frente a la ventana previa (%):"); EP
""")
lec("episodios")

md(r"""
# 5. La red de aseguradoras y las bandas

La caída del volumen desde 2024 se explicó por Nueva EPS (cuadernos 07 y 18). Si es así, las bandas deberían
caer según cuánto de su demanda pasa por esa aseguradora. No existe el cruce de edad por aseguradora, así que se
estima de forma indirecta: la **elasticidad** de cada banda frente al cambio en 28 días de los triages de Nueva
EPS y del resto. Ambas variables son conteos que incluyen a los pacientes de la banda, por lo que la relación
es en parte contable; lo que se compara es su tamaño entre bandas, no su causalidad.
""")
code(r"""
red = ix.red_diaria()
R28 = lambda s: np.log1p(s.rolling(28, min_periods=20).sum()) - np.log1p(s.rolling(28, min_periods=20).sum().shift(28))
V = pd.DataFrame({b: R28(P[f"edad {b}"]) for b in BANDAS})
V["TOTAL"] = R28(P.TOTAL)
Z = V.join(red[["cambio_nueva_eps_28d", "cambio_resto_28d"]]).loc["2022-04-01":"2026-09-20"].iloc[::7].dropna()
filas = []
for b in BANDAS + ["TOTAL"]:
    r = sm.OLS(Z[b], sm.add_constant(Z[["cambio_nueva_eps_28d", "cambio_resto_28d"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 8})
    ci = r.conf_int()
    filas.append({"banda": b, "elasticidad a Nueva EPS": r.params["cambio_nueva_eps_28d"],
                  "IC95 inf": ci.loc["cambio_nueva_eps_28d", 0], "IC95 sup": ci.loc["cambio_nueva_eps_28d", 1],
                  "elasticidad al resto": r.params["cambio_resto_28d"], "R2": r.rsquared})
EL = pd.DataFrame(filas).set_index("banda")
print("Observaciones semanales:", len(Z)); display(EL.round(2))
fig, ax = plt.subplots(figsize=(8.5, 3.8))
y = np.arange(len(EL)); ax.barh(y, EL["elasticidad a Nueva EPS"], color=AZUL, height=.55)
ax.errorbar(EL["elasticidad a Nueva EPS"], y, xerr=[EL["elasticidad a Nueva EPS"] - EL["IC95 inf"], EL["IC95 sup"] - EL["elasticidad a Nueva EPS"]], fmt="none", ecolor=TINTA2, capsize=3)
ax.set_yticks(y, EL.index); ax.invert_yaxis(); ax.set_xlabel("cambio % de la banda por 1 % de cambio de Nueva EPS (28 días)")
ax.set_title("Cuánto sigue cada banda el movimiento de Nueva EPS"); plt.tight_layout(); plt.show()
""")
lec("red")

md(r"""
# 6. El pronóstico por banda

El modelo de contexto holístico (24 variables de clima, enfermedad, red y regímenes) se entrenó para cada banda y
se evaluó en 2025 con origen rodante, de 1 a 7 días. Se leen los resultados guardados. La banda de 5 a 14 años se
excluye: su corrida guardada es anterior a la corrección del logaritmo con ceros (log(y + 1)) y conserva valores
infinitos, así que no es utilizable.
""")
code(r"""
filas = []
for k, nom in [("04", "0-4"), ("1544", "15-44"), ("4564", "45-64"), ("65", "65+")]:
    d = pd.read_parquet(RAIZ / f"salidas/pronostico/hb{k}_2025/lightgbm.parquet")
    assert not np.isinf(d.select_dtypes("number")).any().any()
    real = d.drop_duplicates("fecha").set_index("fecha").real
    d = d.assign(ingenuo=d.fecha.map(lambda f: real.get(f - pd.Timedelta(days=7), np.nan)))
    d = d[(d.real > 0) & d.ingenuo.notna()]
    for h in (1, 7):
        g = d[d.h.eq(h)]
        filas.append({"banda": nom, "h (días)": h, "MAPE modelo %": 100 * ((g.q50 - g.real).abs() / g.real).mean(),
                      "MAPE «igual día semana pasada» %": 100 * ((g.ingenuo - g.real).abs() / g.real).mean(),
                      "cobertura del 80 % (q10-q90) %": 100 * ((g.real >= g.q10) & (g.real <= g.q90)).mean(), "días": len(g)})
PB = pd.DataFrame(filas).set_index(["banda", "h (días)"]).round(1)
PB
""")
lec("pronostico")

md(r"""
# 7. Conclusiones y límites
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "21_el_jerarquico_por_tipo.ipynb")
print("ok", len(C))
