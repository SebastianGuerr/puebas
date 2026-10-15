"""
Motor comun de los dos actualizadores de calendarios hechos a mano (eventos de Manizales y fiestas de Caldas).

Para cada serie recurrente deduce del historico la REGLA DE FECHA de inicio, la mide contra los anios confirmados,
proyecta los anios que faltan y los AGREGA al final del CSV sin tocar ni una fila existente. El porque de cada
decision, las reglas elegidas y su acierto medido estan en calendarios/docs/ACTUALIZADORES.md.

Familias de regla (todas se evaluan; gana la que reproduce exactamente mas anios confirmados):
    fijo      el mismo dia del mismo mes cada anio                         (Dia de las Velitas: 7-dic)
    festivo   N dias antes o despues de un festivo de Colombia ya trasladado por la Ley Emiliani, o de la Pascua
    semana    el primer <dia de la semana> desde el dia D del mes M         (Feria: primer sabado de enero)
Cada una con o sin el ajuste «si cae en festivo, al dia siguiente». Desempates: menor desvio total, familia mas
simple (fijo < festivo < semana), sin ajuste antes que con ajuste, el festivo mas cercano.
"""
from __future__ import annotations

import csv
import io
import os
import re
import statistics
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
from dateutil.easter import easter

RAIZ = Path(__file__).resolve().parents[2]
CALENDARIO = RAIZ / "calendarios/calendario_Colombia.csv"
POR_CONFIRMAR = RAIZ / "salidas/contexto/por_confirmar_eventos.csv"

CALIDAD_AUTO = "estimada_auto"
CALIDADES_AJUSTE = {"confirmada", "recurrente_anual"}        # fechas que sirven para deducir la regla
ESTADOS_AJUSTE = {"realizado", "programado", "cancelado", "aplazado"}   # la fecha prevista sirve; virtual no:
#                                                             en 2020-2021 la edicion virtual movio la fecha
MESES = ["", "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]
DIAS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
ORDINAL = {1: "primer", 8: "segundo", 15: "tercer", 22: "cuarto"}
RANGO_FAMILIA = {"fijo": 0, "festivo": 1, "semana": 2}
DESFASE_MAX = 15                                              # un festivo a mas de 15 dias no es «su» puente
EXCLUIR_FESTIVOS = {"jueves santo", "viernes santo"}          # son la Pascua - 3 y - 2: con la Pascua basta


class ErrorActualizador(Exception):
    """Falla que debe terminar el proceso con codigo distinto de cero."""


# ----------------------------------------------------------------------------------------------- utilidades
def sin_tildes(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def clave_nombre(nombre: str) -> str:
    """Nombre sin parentesis, sin numeros romanos sueltos, sin tildes y en minuscula: la misma serie aunque cada anio
    lleve su edicion en el nombre («Noche del Fuego (XXIV)» = «Noche del Fuego»)."""
    s = re.sub(r"\([^)]*\)", " ", str(nombre))
    s = re.sub(r"\b[IVXLC]+\b", " ", s)
    return re.sub(r"\s+", " ", sin_tildes(s).lower()).strip()


def nombre_base(nombre: str) -> str:
    """El nombre legible sin el parentesis de la edicion ni las notas."""
    return re.sub(r"\s+", " ", re.sub(r"\([^)]*\)", " ", str(nombre))).strip()


def fecha(x) -> date | None:
    if x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() in ("", "nan", "NaT"):
        return None
    return pd.Timestamp(x).date()


def vacio(x) -> bool:
    return x is None or (isinstance(x, float) and pd.isna(x)) or str(x).strip() in ("", "nan")


# ------------------------------------------------------------------------------------------------- festivos
class Festivos:
    """Festivos de Colombia en su fecha observada (la que mueve la Ley Emiliani), de calendario_Colombia.csv."""

    def __init__(self, ruta: Path = CALENDARIO):
        if not ruta.exists():
            raise ErrorActualizador(f"no existe {ruta}")
        c = pd.read_csv(ruta, encoding="utf-8-sig", usecols=["fecha", "nombre_festivo", "es_festivo"])
        c = c[c.es_festivo == 1]
        self.dias: set[date] = set()
        self.por_clave: dict[tuple[str, int], date] = {}
        self.nombre: dict[str, str] = {}
        for f, n in zip(c.fecha, c.nombre_festivo):
            d = pd.Timestamp(f).date()
            self.dias.add(d)
            for parte in str(n).split(";"):
                legible = re.sub(r"\(observado\)", "", parte).strip()
                k = sin_tildes(legible).lower()
                if k in EXCLUIR_FESTIVOS:
                    continue
                self.por_clave[(k, d.year)] = d
                self.nombre[k] = legible
        self.anios = {d.year for d in self.dias}
        self.claves = sorted({k for k, _ in self.por_clave})

    def cubre(self, anio: int) -> bool:
        return anio in self.anios

    def ancla(self, clave: str, anio: int) -> date | None:
        if clave == "pascua":
            return easter(anio)
        return self.por_clave.get((clave, anio))


# --------------------------------------------------------------------------------------------------- reglas
@dataclass(frozen=True)
class Regla:
    familia: str                  # fijo | festivo | semana
    mes: int = 0
    dia: int = 0                  # fijo: dia del mes; semana: desde que dia se busca
    dia_semana: int = 0           # semana: 0 = lunes
    festivo: str = ""             # festivo: clave del festivo o «pascua»
    desfase: int = 0              # festivo: dias respecto del festivo
    evita_festivo: bool = False

    def fecha(self, anio: int, fest: Festivos) -> date | None:
        if self.familia == "fijo":
            try:
                d = date(anio, self.mes, self.dia)
            except ValueError:
                return None
        elif self.familia == "semana":
            d = date(anio, self.mes, self.dia)
            d += timedelta(days=(self.dia_semana - d.weekday()) % 7)
        else:
            a = fest.ancla(self.festivo, anio)
            if a is None:
                return None
            d = a + timedelta(days=self.desfase)
        if self.evita_festivo:
            while d in fest.dias:
                d += timedelta(days=1)
        return d

    def texto(self, fest: Festivos) -> str:
        if self.familia == "fijo":
            t = f"cada anio el {self.dia} de {MESES[self.mes]}"
        elif self.familia == "semana":
            if self.dia in ORDINAL:
                t = f"{ORDINAL[self.dia]} {DIAS[self.dia_semana]} de {MESES[self.mes]}"
            else:
                t = f"primer {DIAS[self.dia_semana]} desde el {self.dia} de {MESES[self.mes]}"
        else:
            n = "el Domingo de Pascua" if self.festivo == "pascua" else                 f"el festivo {fest.nombre.get(self.festivo, self.festivo)} (fecha trasladada)"
            if self.desfase == 0:
                t = f"el mismo dia que {n}"
            else:
                t = f"{abs(self.desfase)} dias {'antes' if self.desfase < 0 else 'despues'} d{n}"
        return t + ("; si cae en festivo, al dia siguiente" if self.evita_festivo else "")


@dataclass
class Medida:
    regla: Regla | None
    n: int = 0                                  # anios confirmados con fecha
    exactos: int = 0
    desvios: dict = field(default_factory=dict)   # anio -> dias (prediccion - real), solo los fallos
    loo_n: int = 0
    loo_exactos: int = 0
    loo_desvio_medio: float | None = None

    def texto(self) -> str:
        if self.regla is None or self.n == 0:
            return "sin medir"
        t = f"{self.exactos}/{self.n} anios exactos"
        if self.desvios:
            t += "; fallos: " + ", ".join(f"{a} {d:+d} d" for a, d in sorted(self.desvios.items()))
        return t

    def texto_loo(self) -> str:
        if self.loo_n < 2:
            return "sin medir (menos de 2 anios)"
        return f"{self.loo_exactos}/{self.loo_n} exactos; desvio medio {self.loo_desvio_medio:.1f} d"

    def confianza(self) -> str:
        if self.loo_n < 2:
            return "sin medir"
        if self.loo_n >= 3 and self.loo_exactos * 3 >= self.loo_n * 2:
            return "alta"
        if self.loo_desvio_medio is not None and self.loo_desvio_medio <= 3:
            return "media"
        return "baja"


def candidatas(obs: dict[int, date], fest: Festivos) -> list[Regla]:
    meses = sorted({d.month for d in obs.values()})
    c: list[Regla] = []
    for ev in (False, True):
        for md in sorted({(d.month, d.day) for d in obs.values()}):
            c.append(Regla("fijo", mes=md[0], dia=md[1], evita_festivo=ev))
        for m in meses:
            for w in range(7):
                for d in range(1, 29):
                    c.append(Regla("semana", mes=m, dia=d, dia_semana=w, evita_festivo=ev))
        for k in fest.claves + ["pascua"]:
            difs = []
            for a, d in obs.items():
                an = fest.ancla(k, a)
                if an is None:
                    break
                difs.append((d - an).days)
            else:
                cuenta = Counter(x for x in difs if abs(x) <= DESFASE_MAX)
                if cuenta:
                    mx = max(cuenta.values())
                    for desf in sorted((x for x, v in cuenta.items() if v == mx), key=abs)[:1]:
                        c.append(Regla("festivo", festivo=k, desfase=desf, evita_festivo=ev))
    return c


def _puntaje(r: Regla, obs: dict[int, date], fest: Festivos):
    exactos, total, desv = 0, 0, {}
    for a, d in obs.items():
        p = r.fecha(a, fest)
        if p is None:
            return None
        e = (p - d).days
        if e == 0:
            exactos += 1
        else:
            desv[a] = e
            total += abs(e)
    # desempate de «semana»: la ventana [dia, dia + 6] lo mas centrada posible en lo observado
    centro = 0
    if r.familia == "semana":
        dias_obs = [d.day for d in obs.values() if d.month == r.mes]
        if dias_obs:
            centro = abs((r.dia + 3) - statistics.median(dias_obs))
    clave = (-exactos, total, RANGO_FAMILIA[r.familia], r.evita_festivo, abs(r.desfase),
             0 if r.dia in ORDINAL else 1, centro, repr(r))
    return clave, exactos, desv


def ajustar(obs: dict[int, date], fest: Festivos) -> Medida:
    """La mejor regla para las fechas de inicio observadas, con su acierto dentro de muestra y dejando uno fuera."""
    if not obs:
        return Medida(None)
    mejor = None
    for r in candidatas(obs, fest):
        p = _puntaje(r, obs, fest)
        if p is not None and (mejor is None or p[0] < mejor[0]):
            mejor = (p[0], r, p[1], p[2])
    if mejor is None:
        return Medida(None, n=len(obs))
    m = Medida(mejor[1], n=len(obs), exactos=mejor[2], desvios=mejor[3])
    if len(obs) >= 2:                                       # dejando uno fuera: la medida honesta
        errores = []
        for a in obs:
            resto = {k: v for k, v in obs.items() if k != a}
            sub = ajustar_sin_loo(resto, fest)
            p = sub.fecha(a, fest) if sub else None
            if p is not None:
                errores.append((p - obs[a]).days)
        m.loo_n = len(errores)
        m.loo_exactos = sum(e == 0 for e in errores)
        m.loo_desvio_medio = (sum(abs(e) for e in errores) / len(errores)) if errores else None
    return m


def ajustar_sin_loo(obs: dict[int, date], fest: Festivos) -> Regla | None:
    mejor = None
    for r in candidatas(obs, fest):
        p = _puntaje(r, obs, fest)
        if p is not None and (mejor is None or p[0] < mejor[0]):
            mejor = (p[0], r)
    return mejor[1] if mejor else None


# ----------------------------------------------------------------------------------------- periodicidad
def anios_que_tocan(periodicidad: str | None, desde: int, hasta: int) -> list[int]:
    if periodicidad == "anual":
        return list(range(desde, hasta + 1))
    if periodicidad == "pares":
        return [a for a in range(desde, hasta + 1) if a % 2 == 0]
    if periodicidad == "impares":
        return [a for a in range(desde, hasta + 1) if a % 2 == 1]
    return []


# --------------------------------------------------------------------------------------------- ediciones
ROMANOS = [(100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def a_romano(n: int) -> str:
    s = ""
    for v, r in ROMANOS:
        while n >= v:
            s, n = s + r, n - v
    return s


def de_romano(s: str) -> int | None:
    if not re.fullmatch(r"[IVXLC]+", s):
        return None
    val = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    t = 0
    for i, ch in enumerate(s):
        v = val[ch]
        t += -v if i + 1 < len(s) and val[s[i + 1]] > v else v
    return t if a_romano(t) == s else None


# ------------------------------------------------------------------------------------------------ escritura
def anexar(ruta: Path, columnas: list[str], filas: list[dict]) -> None:
    """Agrega filas AL FINAL del CSV sin reescribir ni un byte de lo que ya habia. Respeta el fin de linea del archivo
    y comprueba despues de escribir que el contenido anterior quedo intacto como prefijo; si no, restaura y falla."""
    if not filas:
        return
    viejo = ruta.read_bytes()
    eol = "\r\n" if b"\r\n" in viejo[:4096] else "\n"
    cabecera = viejo.split(b"\n", 1)[0].rstrip(b"\r").decode("utf-8-sig").split(",")
    if cabecera != columnas:
        raise ErrorActualizador(f"la cabecera de {ruta.name} cambio: {cabecera}")
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator=eol)
    for f in filas:
        w.writerow(["" if vacio(f.get(c)) else f.get(c) for c in columnas])
    nuevo = viejo + (b"" if viejo.endswith(b"\n") else eol.encode()) + buf.getvalue().encode("utf-8")
    tmp = ruta.with_suffix(ruta.suffix + ".tmp")
    tmp.write_bytes(nuevo)
    os.replace(tmp, ruta)
    leido = ruta.read_bytes()
    if not leido.startswith(viejo):
        ruta.write_bytes(viejo)
        raise ErrorActualizador(f"{ruta.name}: el contenido anterior no quedo intacto; se restauro el original")
    pd.read_csv(ruta)                                        # que siga siendo un CSV legible


COLS_PENDIENTES = ["calendario", "evento", "municipio", "anio", "fecha_estimada", "fecha_fin_estimada", "tipo",
                   "regla", "acierto_historico", "acierto_dejando_uno_fuera", "confianza", "aviso", "fuente_confirmar"]


def escribir_pendientes(calendario: str, filas: list[dict], seco: bool) -> None:
    """Reescribe en por_confirmar_eventos.csv solo las filas de este calendario; conserva las del otro."""
    nuevo = pd.DataFrame(filas, columns=COLS_PENDIENTES)
    if POR_CONFIRMAR.exists():
        viejo = pd.read_csv(POR_CONFIRMAR, dtype=str)
        viejo = viejo[viejo.calendario != calendario]
        nuevo = pd.concat([viejo, nuevo.astype(str).replace("None", "")], ignore_index=True)
    nuevo = nuevo.sort_values(["calendario", "fecha_estimada", "evento"], na_position="last")
    if seco:
        return
    POR_CONFIRMAR.parent.mkdir(parents=True, exist_ok=True)
    nuevo.to_csv(POR_CONFIRMAR, index=False, encoding="utf-8")


def imprimir_utf8() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


# ------------------------------------------------------------------------------------------ planificacion
GRACIA = 3          # anios que una serie ya proyectada sigue viva sin una sola fila nueva escrita a mano


def vigencia(filas: pd.DataFrame, hoy: date, bienal: bool) -> tuple[bool, str]:
    """(sigue viva, aviso). Viva si tiene fila a mano del anio pasado (o del antepasado, si es bienal). Si ya se
    proyecto alguna vez, aguanta GRACIA anios sin confirmacion a mano, avisando; despues deja de proyectarse."""
    man = filas[filas.calidad_fecha != CALIDAD_AUTO]
    ult = int(man.anio.max()) if len(man) else int(filas.anio.max())
    if ult >= hoy.year - (2 if bienal else 1):
        return True, ""
    if (filas.calidad_fecha == CALIDAD_AUTO).any() and ult >= hoy.year - GRACIA:
        return True, f"sin fila escrita a mano desde {ult}: se sigue proyectando hasta {ult + GRACIA}"
    return False, f"sin filas escritas a mano desde {ult}: no se sabe si sigue"


@dataclass
class Serie:
    """Una fiesta o evento recurrente: todas sus filas del CSV, de cualquier anio y estado."""
    clave: tuple
    nombre: str                                 # legible, el de la ultima fila sin la edicion
    municipio: str
    filas: pd.DataFrame
    periodicidad: str | None                    # anual | pares | impares | None (no se proyecta)
    motivo_no: str = ""                         # por que no se proyecta, si periodicidad es None
    hasta: date | None = None                   # ultima fecha posible (p. ej. una prohibicion legal)
    nota_hasta: str = ""
    anio_minimo_ajuste: int | None = None       # cambio de regimen: solo se ajusta con anios >= este
    anios_excluidos: frozenset = frozenset()    # anios atipicos declarados en mes_tipico
    aviso: str = ""

    @property
    def fuente(self) -> str:
        urls = [u for u in self.filas.sort_values("anio").fuente_url.tolist() if not vacio(u) and "http" in str(u)]
        if not urls:
            return ""
        return str(urls[-1]).split(" ; ")[-1].strip()

    def observaciones(self) -> tuple[dict[int, date], int | None]:
        f = self.filas
        f = f[f.calidad_fecha.isin(CALIDADES_AJUSTE) & f.estado.isin(ESTADOS_AJUSTE) & f.fecha_inicio.notna()]
        if self.anio_minimo_ajuste:
            f = f[f.anio >= self.anio_minimo_ajuste]
        f = f[~f.anio.isin(self.anios_excluidos)]
        obs: dict[int, date] = {}
        for a, ini in zip(f.anio, f.fecha_inicio):
            obs.setdefault(int(a), fecha(ini))
        durs = [(fecha(b) - fecha(a)).days for a, b in zip(f.fecha_inicio, f.fecha_fin) if fecha(b) and fecha(a)]
        return obs, (int(statistics.median(durs)) if durs else None)


def planificar(series: list[Serie], fest: Festivos, hoy: date, anios: int, calendario: str, hacer_fila):
    """Devuelve (filas nuevas, pendientes, resumen de reglas). No escribe nada."""
    horizonte = list(range(hoy.year, hoy.year + anios + 1))
    for a in horizonte:
        if not fest.cubre(a):
            raise ErrorActualizador(f"calendario_Colombia.csv no cubre {a}: amplielo antes de proyectar")
    nuevas, pend, resumen = [], [], []

    def pendiente(s, anio, ini, fin, tipo, med, regla_txt, aviso=""):
        pend.append({"calendario": calendario, "evento": s.nombre, "municipio": s.municipio, "anio": anio,
                     "fecha_estimada": ini.isoformat() if ini else "", "fecha_fin_estimada": fin.isoformat() if fin else "",
                     "tipo": tipo, "regla": regla_txt, "acierto_historico": med.texto() if med else "",
                     "acierto_dejando_uno_fuera": med.texto_loo() if med else "",
                     "confianza": med.confianza() if med else "",
                     "aviso": "; ".join(x for x in (s.aviso, aviso) if x), "fuente_confirmar": s.fuente})

    for s in series:
        obs, dur = s.observaciones()
        anios_con_fila = set(s.filas.anio.astype(int))
        if s.periodicidad is None:
            if len(anios_con_fila) >= 2 or s.motivo_no.startswith("periodicidad"):   # los eventos unicos no
                pendiente(s, "", None, None, "no_proyectada", None, s.motivo_no)
            continue
        med = ajustar(obs, fest)
        resumen.append({"serie": s.nombre, "municipio": s.municipio, "periodicidad": s.periodicidad,
                        "anios": sorted(obs), "regla": med.regla.texto(fest) if med.regla else "",
                        "medida": med.texto(), "loo": med.texto_loo(), "confianza": med.confianza(),
                        "duracion": dur})
        if len(obs) < 2:
            sug_a = next((a for a in anios_que_tocan(s.periodicidad, horizonte[0], horizonte[-1])
                          if med.regla and med.regla.fecha(a, fest) and med.regla.fecha(a, fest) > hoy), None)
            sug = med.regla.fecha(sug_a, fest) if sug_a else None
            pendiente(s, sug_a or "", sug, None, "no_proyectada", med,
                      "un solo anio con fecha confirmada: regla sin medir, no se proyecta"
                      + (f" (sugerencia: {med.regla.texto(fest)})" if med.regla else ""))
            continue
        for a in anios_que_tocan(s.periodicidad, horizonte[0], horizonte[-1]):
            ini = med.regla.fecha(a, fest)
            fin = ini + timedelta(days=dur) if (ini and dur is not None) else None
            txt = med.regla.texto(fest)
            existentes = s.filas[s.filas.anio == a]
            if len(existentes):
                r = existentes.iloc[-1]
                if r.calidad_fecha == CALIDAD_AUTO:
                    av = "" if fecha(r.fecha_inicio) == ini else f"la regla actual da {ini}; la fila dice {r.fecha_inicio}"
                    pendiente(s, a, fecha(r.fecha_inicio), fecha(r.fecha_fin), "anadida_auto", med, txt, av)
                elif vacio(r.estado):
                    pendiente(s, a, ini, fin, "fila_existente_sin_estado", med, txt,
                              "la fila existe y no se toca: el modelo la ignora hasta que se le ponga estado"
                              + (f"; la fila dice {r.fecha_inicio}" if not vacio(r.fecha_inicio) else ""))
                elif r.estado in ("realizado", "programado", "aplazado") and vacio(r.fecha_inicio):
                    pendiente(s, a, ini, fin, "fila_existente_sin_fecha", med, txt,
                              f"estado {r.estado} sin fecha_inicio")
                continue
            if ini is None:
                pendiente(s, a, None, None, "no_proyectada", med, f"la regla no da fecha en {a}")
                continue
            if s.hasta and ini > s.hasta:
                pendiente(s, a, ini, fin, "no_proyectada", med, txt, s.nota_hasta)
                continue
            if ini <= hoy:
                pendiente(s, a, ini, fin, "falta_pasada", med, txt,
                          "no hay fila de este anio y la fecha estimada ya paso: se completa a mano, no se estima")
                continue
            nuevas.append(hacer_fila(s, a, ini, fin, med, txt))
            pendiente(s, a, ini, fin, "anadida_auto", med, txt)
    return nuevas, pend, resumen


def informe(nuevas: list[dict], pend: list[dict], resumen: list[dict], col_nombre: str) -> None:
    print(f"\nReglas deducidas ({len(resumen)} series):")
    for r in resumen:
        print(f"  - {r['serie']} [{r['municipio']}] {r['periodicidad']}: {r['regla'] or '-'} | {r['medida']} | "
              f"dejando uno fuera: {r['loo']} | confianza {r['confianza']}")
    print(f"\nFilas a agregar: {len(nuevas)}")
    for f in nuevas:
        print(f"  + {f['anio']} {f[col_nombre]}: {f['fecha_inicio']} -> {f.get('fecha_fin') or ''}")
    c = Counter(p["tipo"] for p in pend)
    print("\nPor confirmar: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
