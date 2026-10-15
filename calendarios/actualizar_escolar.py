"""
Recesos escolares estimados de Manizales (calendario A) para los anos que todavia no tienen resolucion.

    python calendarios/actualizar_escolar.py              mide las reglas y anade los anos que falten
    python calendarios/actualizar_escolar.py --seco       mide y muestra; no escribe nada
    python calendarios/actualizar_escolar.py --hasta 2029 anos lectivos a cubrir (por defecto, el actual + 2)

Las reglas no se escriben a mano: cada una se DEDUCE del historico de calendario_escolar_manizales.csv (filas con
resolucion) dentro de una familia pequena y fija, y su acierto se mide con origen rodante (para cada ano, la regla
deducida solo de los anos anteriores). El porque y el acierto medido: calendarios/docs/ACTUALIZADORES.md.

Que escribe:
- calendarios/calendario_escolar_manizales.csv: SOLO anade filas al final, con resolucion = 'estimada_auto' y la
  regla en 'nota'. Nunca modifica una fila existente; si ya hay una fila para ese ano, tipo y tramo, no anade nada.
- salidas/contexto/por_confirmar_escolar.csv: las filas estimadas que siguen en el calendario, y los choques con
  resoluciones que ya se hayan escrito a mano (la estimada sobra y se borra a mano).

Sale con codigo 1 si algo falla.
"""
import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
ESCOLAR = RAIZ / "calendarios" / "calendario_escolar_manizales.csv"
POR_CONFIRMAR = RAIZ / "salidas" / "contexto" / "por_confirmar_escolar.csv"
ESTIMADA = "estimada_auto"
LUNES, DOMINGO = 0, 6
SEMANAS_DE_CLASE = 40      # Decreto 1075 de 2015, art. 2.4.3.4.1: 40 semanas de trabajo academico con estudiantes
MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def pascua(anio):
    """Domingo de Pascua (computo gregoriano anonimo, Meeus/Jones/Butcher)."""
    a, b, c = anio % 19, anio // 100, anio % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = (h + l_ - 7 * m + 114) % 31 + 1
    return date(anio, mes, dia)


def primer(dia_semana, desde):
    return desde + timedelta(days=(dia_semana - desde.weekday()) % 7)


class Ancla:
    """Regla 'el primer <dia_semana> desde el <dia> de <mes>'. Se deduce de fechas observadas: el conjunto de dias de
    ancla compatible con cada ano es un intervalo de 7 dias; se toma la interseccion de todos los anos (y su
    mediana), o, si esta vacia, el dia que acierta mas anos."""

    def __init__(self, mes, dia_semana, nombre):
        self.mes, self.dia_semana, self.nombre = mes, dia_semana, nombre
        self.k = None
        self.intervalo = None

    def _fecha(self, anio, k):
        return date(anio, self.mes, 1) + timedelta(days=k)

    def ajustar(self, observadas):
        """observadas: {anio: fecha}."""
        rango = range(-20, 50)
        aciertos = {k: sum(primer(self.dia_semana, self._fecha(a, k)) == f for a, f in observadas.items()) for k in rango}
        mejor = max(aciertos.values())
        ks = [k for k in rango if aciertos[k] == mejor]
        self.k = ks[len(ks) // 2]
        self.intervalo = (ks[0], ks[-1])
        self.ajuste = (mejor, len(observadas))
        return self

    def __call__(self, anio):
        return primer(self.dia_semana, self._fecha(anio, self.k))

    def texto(self, anio=2027):
        f = self._fecha(anio, self.k)
        dias = {LUNES: "lunes", DOMINGO: "domingo"}[self.dia_semana]
        a, b = self._fecha(anio, self.intervalo[0]), self._fecha(anio, self.intervalo[1])
        rango = "" if a == b else f" (cualquier ancla del {a.day}-{MESES[a.month - 1]} al {b.day}-{MESES[b.month - 1]} da lo mismo en el historico)"
        return f"primer {dias} desde el {f.day}-{MESES[f.month - 1]}{rango}"


# ------------------------------------------------------------------------- historico
def leer():
    d = pd.read_csv(ESCOLAR, dtype=str, keep_default_na=False)
    for c in ("fecha_inicio", "fecha_fin"):
        d[c] = pd.to_datetime(d[c]).dt.date
    d["anio_lectivo"] = d.anio_lectivo.astype(int)
    return d


def tramo(fila):
    """fin_de_anio aparece dos veces por ano lectivo: el arranque (empieza en diciembre del ano anterior) y el
    cierre (empieza en el propio ano). La llave de una fila es (anio_lectivo, tipo, tramo)."""
    if fila["tipo"] != "fin_de_anio":
        return ""
    return "arranque" if fila["fecha_inicio"].year < fila["anio_lectivo"] else "cierre"


def observaciones(d):
    """Por ano lectivo, las fronteras que fija cada resolucion (solo filas oficiales)."""
    of = d[d.resolucion.ne(ESTIMADA)].copy()
    of["tramo"] = [tramo(r) for _, r in of.iterrows()]
    o = {}
    for _, r in of.iterrows():
        o.setdefault(r.anio_lectivo, {})[(r.tipo, r.tramo)] = (r.fecha_inicio, r.fecha_fin)
    return o


def fronteras(o):
    """Las series observadas que necesita cada regla."""
    s = {"inicio_clases": {}, "mitad": {}, "mitad_semanas": {}, "octubre": {}, "cierre": {}, "corte_dic": {},
         "semana_santa": {}}
    for a, t in o.items():
        if ("fin_de_anio", "arranque") in t:
            s["inicio_clases"][a] = t[("fin_de_anio", "arranque")][1] + timedelta(days=1)
        if ("mitad_de_anio", "") in t:
            i, f = t[("mitad_de_anio", "")]
            s["mitad"][a] = i
            s["mitad_semanas"][a] = ((f - i).days + 1) // 7
        if ("octubre", "") in t:
            s["octubre"][a] = t[("octubre", "")][0]
        if ("fin_de_anio", "cierre") in t:
            s["cierre"][a], s["corte_dic"][a] = t[("fin_de_anio", "cierre")]
        if ("semana_santa", "") in t:
            s["semana_santa"][a] = t[("semana_santa", "")]
    return s


# ------------------------------------------------------------------------- reglas
def deducir(s):
    """Ajusta todas las reglas con las fronteras dadas. Devuelve un objeto con un metodo por receso."""
    r = {
        "inicio_clases": Ancla(1, LUNES, "inicio de clases").ajustar(s["inicio_clases"]),
        "mitad": Ancla(6, LUNES, "inicio del receso de mitad de ano").ajustar(s["mitad"]),
        "octubre": Ancla(10, LUNES, "receso de octubre").ajustar(s["octubre"]),
        "corte_dic": Ancla(12, DOMINGO, "fin del tramo de cierre").ajustar(s["corte_dic"]),
        "cierre_ancla": Ancla(11, LUNES, "inicio del receso de fin de ano").ajustar(s["cierre"]),
    }
    sem = pd.Series(s["mitad_semanas"])
    r["mitad_semanas"] = int(sem.mode().max()) if len(sem) else 3
    return r


def cierre_40(r, anio, ss=True):
    """Inicio del receso de fin de ano = inicio de clases + 40 semanas de clase + las semanas de receso intermedias
    (Semana Santa, mitad de ano, octubre)."""
    semanas = SEMANAS_DE_CLASE + (1 if ss else 0) + r["mitad_semanas"] + 1
    return r["inicio_clases"](anio) + timedelta(weeks=semanas)


def calendario(r, anio, arranque_desde=None, regla_cierre="40_semanas"):
    """Las cinco filas estimadas de un ano lectivo: {(tipo, tramo): (inicio, fin, regla)}."""
    ini = r["inicio_clases"](anio)
    if arranque_desde is None:
        arranque_desde = r["corte_dic"](anio - 1) + timedelta(days=1)
    p = pascua(anio)
    m = r["mitad"](anio)
    oc = r["octubre"](anio)
    ci = cierre_40(r, anio) if regla_cierre == "40_semanas" else r["cierre_ancla"](anio)
    cd = r["corte_dic"](anio)
    return {
        ("fin_de_anio", "arranque"): (arranque_desde, ini - timedelta(days=1),
                                      f"desde el dia siguiente al cierre del ano anterior hasta la vispera del inicio "
                                      f"de clases; inicio de clases = {r['inicio_clases'].texto(anio)}"),
        ("semana_santa", ""): (p - timedelta(days=6), p, "lunes santo a domingo de Pascua (computo de Pascua)"),
        ("mitad_de_anio", ""): (m, m + timedelta(days=7 * r["mitad_semanas"] - 1),
                                f"{r['mitad'].texto(anio)}, {r['mitad_semanas']} semanas (la duracion mas frecuente)"),
        ("octubre", ""): (oc, oc + timedelta(days=6),
                          f"{r['octubre'].texto(anio)}: la semana anterior al festivo del 12 de octubre"),
        ("fin_de_anio", "cierre"): (ci, cd,
                                    (f"inicio = inicio de clases + {SEMANAS_DE_CLASE} semanas de clase + las semanas de "
                                     f"receso intermedias (Decreto 1075 de 2015)" if regla_cierre == "40_semanas"
                                     else f"inicio = {r['cierre_ancla'].texto(anio)}")
                                    + f"; fin = {r['corte_dic'].texto(anio)}"),
    }


# ------------------------------------------------------------------------- medicion
def medir(o):
    """Acierto exacto (inicio y fin) por receso: (a) ajuste en todo el historico, (b) origen rodante: cada ano con la
    regla deducida solo de los anos anteriores (hacen falta 2 anos previos)."""
    anios = sorted(o)
    s_todo = fronteras(o)
    filas = []
    for regla_cierre in ("40_semanas", "ancla"):
        for modo in ("historico", "origen_rodante"):
            for a in anios:
                previos = {x: o[x] for x in anios if x < a}
                if modo == "origen_rodante" and len(previos) < 2:
                    continue
                r = deducir(s_todo if modo == "historico" else fronteras(previos))
                arr = o[a].get(("fin_de_anio", "arranque"))
                cal = calendario(r, a, arranque_desde=arr[0] if arr else None, regla_cierre=regla_cierre)
                for clave, (i, f, _) in cal.items():
                    if clave not in o[a]:
                        continue
                    ri, rf = o[a][clave]
                    filas.append({"regla_cierre": regla_cierre, "modo": modo, "anio": a, "tipo": clave[0],
                                  "tramo": clave[1], "acierto": (i, f) == (ri, rf),
                                  "error_inicio_dias": (i - ri).days, "error_fin_dias": (f - rf).days})
    return pd.DataFrame(filas)


def resumen(m):
    g = m.groupby(["regla_cierre", "modo", "tipo", "tramo"]).acierto.agg(["sum", "count"]).reset_index()
    g["acierto"] = g["sum"].astype(int).astype(str) + "/" + g["count"].astype(str)
    return g.pivot_table(index=["tipo", "tramo"], columns=["regla_cierre", "modo"], values="acierto", aggfunc="first")


def semanas_de_clase(o):
    """Semanas entre el inicio de clases y el receso de fin de ano, menos las semanas de receso intermedias reales."""
    s, r = fronteras(o), {}
    for a, t in o.items():
        if a in s["inicio_clases"] and a in s["cierre"]:
            rec = sum(((f - i).days + 1) / 7 for (tipo, _), (i, f) in t.items()
                      if tipo in ("semana_santa", "mitad_de_anio", "octubre"))
            r[a] = round((s["cierre"][a] - s["inicio_clases"][a]).days / 7 - rec, 2)
    return r


def contiguidad(o):
    """El arranque de cada ano empieza el dia siguiente al fin del cierre del ano anterior?"""
    r = {}
    for a, t in o.items():
        if a - 1 in o and ("fin_de_anio", "cierre") in o[a - 1] and ("fin_de_anio", "arranque") in t:
            r[a] = o[a - 1][("fin_de_anio", "cierre")][1] + timedelta(days=1) == t[("fin_de_anio", "arranque")][0]
    return r


# ------------------------------------------------------------------------- escritura
def nuevas_filas(d, o, hasta, regla_cierre):
    r = deducir(fronteras(o))
    # sensibilidad: las mismas reglas sin el primer ano observado (2021, alternancia por COVID), que es el que fija
    # varias anclas en el borde de su intervalo
    r_alt = deducir(fronteras({k: v for k, v in o.items() if k != min(o)}))
    existentes = {(x.anio_lectivo, x.tipo, tramo(x)) for _, x in d.iterrows()}
    ultimo = max(o)
    filas, arranque = [], None
    for a in range(ultimo + 1, hasta + 1):
        # el arranque empieza el dia siguiente al ultimo cierre que ya este en el calendario (oficial o estimado)
        previo = d[(d.anio_lectivo == a - 1) & (d.tipo == "fin_de_anio")]
        previo = previo[[tramo(x) == "cierre" for _, x in previo.iterrows()]]
        if len(previo):
            arranque = previo.fecha_fin.max() + timedelta(days=1)
        cal = calendario(r, a, arranque_desde=arranque, regla_cierre=regla_cierre)
        alt = calendario(r_alt, a, arranque_desde=arranque, regla_cierre=regla_cierre)
        arranque = cal[("fin_de_anio", "cierre")][1] + timedelta(days=1)
        for (tipo, tr), (i, f, regla) in cal.items():
            if (a, tipo, tr) in existentes:
                continue
            nota = f"regla: {regla}"
            ai, af, _ = alt[(tipo, tr)]
            if (ai, af) != (i, f):
                nota += f"; sin el ano {min(o)} la regla daria {ai.isoformat()} a {af.isoformat()}"
            filas.append({"anio_lectivo": a, "tipo": tipo, "fecha_inicio": i.isoformat(), "fecha_fin": f.isoformat(),
                          "resolucion": ESTIMADA, "fuente_url": "", "nota": nota})
    return filas


def anadir(filas, columnas):
    original = ESCOLAR.read_bytes()
    txt = pd.DataFrame(filas)[columnas].to_csv(index=False, header=False, lineterminator="\n")
    sep = b"" if original.endswith(b"\n") else b"\n"
    ESCOLAR.write_bytes(original + sep + txt.encode("ascii", "replace"))
    if not ESCOLAR.read_bytes().startswith(original):
        raise RuntimeError("las filas existentes cambiaron al escribir")


def por_confirmar(d):
    d = d.copy()
    d["tramo"] = [tramo(x) for _, x in d.iterrows()]
    est = d[d.resolucion.eq(ESTIMADA)]
    of = {(x.anio_lectivo, x.tipo, x.tramo) for _, x in d[d.resolucion.ne(ESTIMADA)].iterrows()}
    est = est.assign(
        estado=["choca_con_resolucion_oficial: borrar la estimada a mano" if (x.anio_lectivo, x.tipo, x.tramo) in of
                else "estimada: confirmar con la resolucion de la Secretaria de Educacion (sale hacia octubre-noviembre del ano anterior)"
                for _, x in est.iterrows()])
    return est[["estado", "anio_lectivo", "tipo", "tramo", "fecha_inicio", "fecha_fin", "nota"]]


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seco", action="store_true", help="no escribe nada; solo informa")
    ap.add_argument("--hasta", type=int, default=date.today().year + 2, help="ultimo ano lectivo a cubrir")
    a = ap.parse_args(argv)

    d = leer()
    columnas = list(pd.read_csv(ESCOLAR, nrows=0).columns)
    o = observaciones(d)
    m = medir(o)
    pd.set_option("display.width", 200)
    print("arranque contiguo al cierre del ano anterior:", contiguidad(o))
    print("acierto exacto (inicio y fin) por receso:")
    print(resumen(m).to_string())

    # Inicio del receso de fin de ano. Si la ley de las 40 semanas se cumple en TODOS los anos observados (con los
    # recesos reales), manda ella: la regla de ancla fija daria para 2027-2028 un ano de 39 semanas, que la norma no
    # permite. Si algun ano la incumple, se elige por acierto con origen rodante (empate -> 40 semanas).
    # (Criterio fijado el 2026-10-15 DESPUES de ver el origen rodante; ver ACTUALIZADORES.md.)
    ley = semanas_de_clase(o)
    print("semanas de clase por ano (con los recesos reales):", ley)
    ro = m[m.modo.eq("origen_rodante") & m.tipo.eq("fin_de_anio") & m.tramo.eq("cierre")]
    tasa = ro.groupby("regla_cierre").acierto.mean()
    if ley and all(v == SEMANAS_DE_CLASE for v in ley.values()):
        regla_cierre = "40_semanas"
    else:
        regla_cierre = "40_semanas" if tasa.get("40_semanas", 0) >= tasa.get("ancla", 0) else "ancla"
    print(f"regla para el inicio del receso de fin de ano: {regla_cierre} "
          f"(origen rodante: 40 semanas {tasa.get('40_semanas', 0):.0%}, ancla fija {tasa.get('ancla', 0):.0%})")

    filas = nuevas_filas(d, o, a.hasta, regla_cierre)
    for f in filas:
        print(f"  + {f['anio_lectivo']} {f['tipo']:<14} {f['fecha_inicio']} a {f['fecha_fin']}")
    print(f"filas nuevas: {len(filas)}")
    if a.seco:
        print("--seco: no se escribio nada")
        return 0
    if filas:
        anadir(filas, columnas)
    pc = por_confirmar(leer())
    POR_CONFIRMAR.parent.mkdir(parents=True, exist_ok=True)
    pc.to_csv(POR_CONFIRMAR, index=False)
    print(f"{ESCOLAR.name}: +{len(filas)} filas; {POR_CONFIRMAR.relative_to(RAIZ)}: {len(pc)} filas")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:  # la tarea programada necesita un codigo distinto de cero
        print(f"ERROR actualizar_escolar: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
