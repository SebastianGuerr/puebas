import json, nbformat as nbf
from pathlib import Path
LJ = Path(__file__).with_name("18_lecturas.json")
LECT = json.loads(LJ.read_text(encoding="utf-8")) if LJ.exists() else {}
C = []
md = lambda s: C.append(nbf.v4.new_markdown_cell(s.strip()))
code = lambda s: C.append(nbf.v4.new_code_cell(s.strip()))
lec = lambda k: md(LECT.get(k, f"**Lectura.** *(pendiente: {k})*"))

md(r"""
# 18 — El panel de todas las EPS

## Qué pidió el propietario

«No tenemos una variable que mida el estado de **todas** las EPS; es como si supusiera que la Nueva EPS es la
única que existe.» Este cuaderno arma ese panel con dos miradas:
- **desde dentro**, con el triage del propio hospital por asegurador (2020-2026);
- **desde fuera**, con la afiliación mensual de MinSalud por EPS en Manizales y las medidas de la
  Supersalud, que desde el 2026-10-05 se capturan solas cada semana (`calendarios/docs/CAPTURAS.md`).

Método en la fila `panel_eps` de `variables.csv`, fijado antes de mirar. Este cuaderno es **descriptivo**: mira
2025-2026 porque ahí ocurren los escalones de la red. **No elige ni prueba ningún modelo**; eso queda para el
cuaderno 22.
""")

code(r"""
import sys, pathlib, warnings, re, glob
RAIZ = next(p for p in [pathlib.Path.cwd(), *pathlib.Path.cwd().parents] if (p / "CLAUDE.md").exists())
sys.path.insert(0, str(RAIZ / "notebooks")); warnings.filterwarnings("ignore")
import numpy as np, pandas as pd
from matplotlib import pyplot as plt
AZUL, NARANJA, AQUA, AMARILLO, MAGENTA, VERDE, VIOLETA, ROJO = (
    "#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948")
TINTA, TINTA2, MUDO, SUP = "#0b0b0b", "#52514e", "#898781", "#fcfcfb"
plt.rcParams.update({"figure.facecolor": SUP, "axes.facecolor": SUP, "axes.spines.top": False,
    "axes.spines.right": False, "axes.edgecolor": MUDO, "axes.grid": True, "grid.color": "#e6e5e1",
    "grid.linewidth": .6, "axes.labelcolor": TINTA2, "xtick.color": TINTA2, "ytick.color": TINTA2,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA, "font.size": 10,
    "legend.frameon": False})
ESCALONES = ["2024-04-01", "2025-11-15", "2026-03-01", "2026-07-01"]

def grupo(e):
    e = str(e).upper()
    reglas = [("Nueva EPS", r"NUEVA (EMPRESA PROMOTORA|EPS)(?!.*COMPLEMENT)"), ("SURA", r"^EPS SURA|EPS SURAMERICANA"),
              ("Salud Total", r"SALUD TOTAL"), ("Sanitas", r"^EPS SANITAS|SANITAS EPS"), ("Asmet", r"ASMET"),
              ("Magisterio (FOMAG)", r"FIDEICOMISOS|FIDUPREVISORA|MAGISTERIO"), ("Medimás", r"MEDIMAS"),
              ("SOAT y accidentes", r"SEGUROS|MUNDIAL|PREVISORA S\.A\. COMPA|SOAT|ARL|POSITIVA|LIBERTY|ALLIANZ|AXA"),
              ("Territorial (no asegurados)", r"TERRITORIAL|SECRETARIA|MUNICIPIO|DEPARTAMENTO"), ("Particulares", r"PARTICULAR"),
              ("Prepagadas", r"PREPAGADA|COLSANITAS|COLMEDICA|MEDISANITAS")]
    return next((g for g, p in reglas if re.search(p, e)), "Otras")
te = pd.read_parquet(RAIZ / "salidas/triage_entidad.parquet", columns=["dia", "entidad", "n"]); te["dia"] = pd.to_datetime(te.dia)
te["grupo"] = te.entidad.map({e: grupo(e) for e in te.entidad.dropna().unique()}).fillna("Otras")
D = te.pivot_table(index="dia", columns="grupo", values="n", aggfunc="sum").reindex(pd.date_range("2020-01-01", "2026-09-20")).fillna(0)
D.loc["2024-03-19":"2024-03-21"] = np.nan
print("Grupos y triages totales 2020-2026:"); D.sum().sort_values(ascending=False).astype(int)
""")

md(r"""
---
# 1. Quién llega al hospital, mes a mes
""")
code(r"""
M = D.resample("MS").mean()
orden = ["Nueva EPS", "SURA", "Salud Total", "Sanitas", "Asmet", "Magisterio (FOMAG)", "SOAT y accidentes", "Territorial (no asegurados)", "Particulares", "Prepagadas", "Medimás", "Otras"]
cols = [AZUL, ROJO, VERDE, VIOLETA, AMARILLO, MAGENTA, NARANJA, AQUA, MUDO, "#9b9a95", "#c9c8c4", "#e0dfdb"]
fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
axes[0].stackplot(M.index, [M[g] for g in orden], labels=orden, colors=cols, lw=0)
axes[0].set_ylabel("triages por día (media del mes)"); axes[0].legend(ncol=6, fontsize=8, loc="upper left"); axes[0].set_title("El triage por asegurador")
W = M.div(M.sum(axis=1), axis=0) * 100
for g, c in zip(orden[:6], cols[:6]): axes[1].plot(W.index, W[g], color=c, lw=2, label=g)
for f in ESCALONES: [ax.axvline(pd.Timestamp(f), color=TINTA, lw=.8, ls=":") for ax in axes]
axes[1].set_ylabel("% del triage del mes"); axes[1].legend(ncol=6, fontsize=8); axes[1].set_title("El peso de cada uno (líneas punteadas: escalones de la red)")
plt.tight_layout(); plt.show()
anual = D.groupby(D.index.year).mean()[orden].round(1); anual["total"] = anual.sum(axis=1); anual
""")
lec("quien")

md(r"""
---
# 2. Sustitución: cuando Nueva EPS cae, ¿quién compensa?

Para cada escalón: el triage diario medio de Nueva EPS y del resto en los 60 días antes y los 60 días después,
dejando fuera la semana del escalón.
""")
code(r"""
filas = []
for f in ESCALONES:
    f = pd.Timestamp(f); a = D.loc[f - pd.Timedelta(days=67):f - pd.Timedelta(days=8)]; d = D.loc[f + pd.Timedelta(days=7):f + pd.Timedelta(days=66)]
    ne_a, ne_d = a["Nueva EPS"].mean(), d["Nueva EPS"].mean(); re_a, re_d = a.drop(columns="Nueva EPS").sum(axis=1).mean(), d.drop(columns="Nueva EPS").sum(axis=1).mean()
    su_a, su_d = a["SURA"].mean(), d["SURA"].mean()
    filas.append({"escalón": f.date(), "Nueva EPS antes": ne_a, "Nueva EPS después": ne_d, "cambio Nueva EPS": ne_d - ne_a,
                  "resto antes": re_a, "resto después": re_d, "cambio resto": re_d - re_a, "de eso, SURA": su_d - su_a,
                  "compensa el resto %": 100 * (re_d - re_a) / -(ne_d - ne_a) if ne_d != ne_a else np.nan,
                  "cambio del total %": 100 * ((ne_d + re_d) / (ne_a + re_a) - 1)})
pd.DataFrame(filas).set_index("escalón").round(1)
""")
lec("sustitucion")

md(r"""
---
# 3. Afiliados contra uso: ¿se van los afiliados o no logran entrar?

Afiliación mensual por EPS en **Manizales** (MinSalud, julio de 2025 a agosto de 2026, capturada el
2026-10-05) frente al triage del hospital de cada EPS.
""")
code(r"""
MESES = {"ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12}
filas = []
for f in glob.glob(str(RAIZ / "calendarios/capturas/afiliacion/*_caldas.csv.gz")):
    m = re.search(r"(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic)[a-z]*[-_]?(\d{4})", f.lower()); fecha = pd.Timestamp(int(m.group(2)), MESES[m.group(1)], 1)
    d = pd.read_csv(f); e = d[d.hoja == "EPSMunicipio"].pivot(index="fila", columns="columna", values="valor")
    mun = next(c for c in e.columns if c.split("| ")[-1].upper() == "MUNICIPIO"); eps = next(c for c in e.columns if c.split("| ")[-1].upper() == "EPS")
    e = e[e[mun].astype(str).str.upper().str.contains("MANIZALES")]
    af = [c for c in e.columns if c.split("| ")[-1].strip().upper().startswith("AFILIADOS")]
    for _, r in e.iterrows():
        filas.append({"mes": fecha, "eps": r[eps], "afiliados": pd.to_numeric(r[af], errors="coerce").fillna(0).sum()})
A = pd.DataFrame(filas).pivot_table(index="mes", columns="eps", values="afiliados", aggfunc="sum").sort_index()
mapa = {"NUEVA EPS": "Nueva EPS", "EPS SURA": "SURA", "SALUD TOTAL EPS": "Salud Total", "EPS SANITAS": "Sanitas"}
A = A[list(mapa)].rename(columns=mapa)
uso = M.loc[A.index, list(mapa.values())]
por_mil = uso * 30 / A * 1000           # triages al mes por cada 1.000 afiliados de Manizales
fig, axes = plt.subplots(1, 2, figsize=(15, 4))
for g, c in zip(mapa.values(), [AZUL, ROJO, VERDE, VIOLETA]):
    axes[0].plot(A.index, A[g] / 1000, "-o", color=c, ms=4, lw=2, label=g); axes[1].plot(por_mil.index, por_mil[g], "-o", color=c, ms=4, lw=2, label=g)
axes[0].set_ylabel("miles de afiliados en Manizales"); axes[0].set_title("Afiliados por EPS (MinSalud)"); axes[0].legend(fontsize=8)
axes[1].set_ylabel("triages al mes por 1.000 afiliados"); axes[1].set_title("Uso del hospital por afiliado")
plt.tight_layout(); plt.show()
cambio = pd.DataFrame({"afiliados jul-2025": A.iloc[0], "afiliados ago-2026": A.iloc[-1], "cambio afiliados %": 100 * (A.iloc[-1] / A.iloc[0] - 1),
                       "triage/día jul-2025": uso.iloc[0], "triage/día ago-2026": uso.iloc[-1], "cambio triage %": 100 * (uso.iloc[-1] / uso.iloc[0] - 1),
                       "uso por afiliado, cambio %": 100 * (por_mil.iloc[-1] / por_mil.iloc[0] - 1)})
cambio.round(1)
""")
lec("afiliados")

md(r"""
---
# 4. Las medidas de la Supersalud: fechas de cada actuación

La tabla limpia de la Supersalud (sin datos de los interventores) trae, para cada EPS intervenida, **todas
sus resoluciones con fecha**: la toma de posesión, las prórrogas y los cambios de interventor.
""")
code(r"""
f = glob.glob(str(RAIZ / "calendarios/capturas/medidas/*/CTFT21-Listado*EPS.csv"))[-1]
m = pd.read_csv(f); col = next(c for c in m.columns if c.upper().startswith("RESOLU"))
MES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7, "agosto": 8, "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12}
ev = []
for _, r in m.iterrows():
    for d, mes, a in re.findall(r"(\d{1,2}) de (\w+) del? (\d{4})", str(r[col]).lower()):
        if mes in MES: ev.append({"eps": r["ENTIDAD"].split("\n")[0].strip(), "fecha": pd.Timestamp(int(a), MES[mes], int(d))})
EV = pd.DataFrame(ev).drop_duplicates().sort_values(["eps", "fecha"])
print(EV.groupby("eps").fecha.agg(["min", "max", "count"]).rename(columns={"min": "primera resolución", "max": "última", "count": "resoluciones"}).to_string())
ne = EV[EV.eps.str.upper().str.contains("NUEVA")].fecha
fig, ax = plt.subplots(figsize=(15, 3.6))
ax.plot(D.index, D["Nueva EPS"].rolling(28, center=True, min_periods=14).mean(), color=AZUL, lw=1.8, label="triage de Nueva EPS (media 28 días)")
for d in ne: ax.axvline(d, color=ROJO, lw=1, alpha=.7)
for fsc in ESCALONES: ax.axvline(pd.Timestamp(fsc), color=TINTA, lw=1, ls=":")
ax.set_xlim(pd.Timestamp("2023-06-01"), D.index[-1]); ax.legend(loc="upper right"); ax.set_ylabel("triages por día")
ax.set_title("Nueva EPS: resoluciones de la Supersalud (rojo) y escalones del triage (punteado)"); plt.tight_layout(); plt.show()
print("Resoluciones sobre Nueva EPS:", [d.date().isoformat() for d in ne])
""")
lec("medidas")

md(r"""
---
# 5. Las variables candidatas para el modelo
""")
code(r"""
P28 = D.rolling(28, min_periods=20).sum(); tot28 = P28.sum(axis=1)
V = pd.DataFrame({"peso_nueva_eps_28d": P28["Nueva EPS"] / tot28, "peso_sura_28d": P28["SURA"] / tot28,
                  "cambio_nueva_eps_28d": np.log1p(P28["Nueva EPS"]) - np.log1p(P28["Nueva EPS"].shift(28)),
                  "cambio_resto_28d": np.log1p(P28.drop(columns="Nueva EPS").sum(axis=1)) - np.log1p(P28.drop(columns="Nueva EPS").sum(axis=1).shift(28)),
                  "herfindahl_28d": ((P28.div(tot28, axis=0)) ** 2).sum(axis=1)})
res = pd.Series(0.0, index=D.index)
for d in ne: res[d:d + pd.Timedelta(days=30)] = 1
V["resolucion_nueva_eps_30d"] = res
fig, axes = plt.subplots(len(V.columns), 1, figsize=(15, 10), sharex=True)
for ax, c in zip(axes, V.columns):
    ax.plot(V.index, V[c], color=TINTA2, lw=1); ax.set_ylabel(c, fontsize=8, rotation=0, ha="right")
    for fsc in ESCALONES: ax.axvline(pd.Timestamp(fsc), color=ROJO, lw=.8, ls=":")
plt.tight_layout(); plt.show()
disp = pd.DataFrame({"desde": [V[c].first_valid_index().date() for c in V], "¿se conoce al predecir?": ["sí"] * len(V.columns),
                     "fuente": ["triage del hospital"] * 5 + ["Supersalud (fecha pública)"]}, index=V.columns)
disp
""")
lec("candidatas")

md(r"""
---
# 6. Lo que deja este cuaderno
""")
lec("resumen")

nb = nbf.v4.new_notebook(); nb.cells = C
nb.metadata["kernelspec"] = {"name": "python3", "display_name": "Python 3", "language": "python"}
nbf.write(nb, Path(__file__).resolve().parents[1] / "18_el_panel_de_las_eps.ipynb")
print("ok", len(C))
