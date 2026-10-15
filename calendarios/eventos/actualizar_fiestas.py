"""
Proyecta las fiestas recurrentes de los municipios de Caldas (calendarios/fiestas_caldas_2020_2026.csv) a los anios
que faltan.

    python calendarios/eventos/actualizar_fiestas.py              agrega lo que falte y rehace la lista por confirmar
    python calendarios/eventos/actualizar_fiestas.py --seco       muestra lo que agregaria, sin escribir nada
    python calendarios/eventos/actualizar_fiestas.py --hoy 2026-10-15 --anios 2

Nunca modifica una fila existente: solo AGREGA al final, con estado=programado, calidad_fecha=estimada_auto y
marca=I (inferido). Respeta la periodicidad declarada (anual, bienal en pares o impares) y no proyecta las series
irregulares, de periodicidad desconocida o unicas. Es idempotente. La regla de cada fiesta y su acierto medido estan
en calendarios/docs/ACTUALIZADORES.md. Sale con codigo 1 si algo falla.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reglas as R  # noqa: E402

CSV = R.RAIZ / "calendarios/fiestas_caldas_2020_2026.csv"
COLUMNAS = ["nombre", "municipio", "distancia_km_manizales", "anio", "fecha_inicio", "fecha_fin", "periodicidad",
            "mes_tipico", "estado", "calidad_fecha", "fuente_url", "marca"]

# La misma fiesta con nombres distintos segun el anio (clave_nombre ya quita parentesis, romanos y tildes)
ALIAS = {
    ("Palestina", "fiestas de cumpleanos"): "fiestas aniversarias / del recuerdo / del regreso",
    ("Palestina", "fiestas del recuerdo"): "fiestas aniversarias / del recuerdo / del regreso",
    ("Palestina", "aniversario 169 anos"): "fiestas aniversarias / del recuerdo / del regreso",
    ("San José", "fiestas mitos y leyendas del paisaje cultural cafetero"): "fiestas de mitos y leyendas",
    ("Pácora", "cumpleanos del municipio y festival de la cancion"): "cumpleanos del municipio",
    ("Pácora", "cumpleanos del municipio y pregon fiestas del agua"): "cumpleanos del municipio",
    ("Manzanares", "dia del manzanareno y encuentro regional de arrieros"): "dia del manzanareno",
    ("Manzanares", "dia del manzanareno y encuentro de arrieria"): "dia del manzanareno",
}
# Periodicidades que no se leen solas
PERIODICIDAD_ESPECIAL = {
    "años sin Cordialidad": "pares",          # la Cordialidad de Manzanares es bienal en impares
}
CONSUME_EDICION = {"realizado", "programado", "virtual", "aplazado"}   # cancelado no gasta numero


def leer_periodicidad(p) -> tuple[str | None, str]:
    """(anual | pares | impares | None, motivo si None) a partir del texto de la columna periodicidad."""
    if R.vacio(p):
        return None, "periodicidad vacia"
    p = str(p).strip()
    if p in PERIODICIDAD_ESPECIAL:
        return PERIODICIDAD_ESPECIAL[p], ""
    t = R.sin_tildes(p).lower()
    if any(x in t for x in ("irregular", "desconocida", "unica")):
        return None, f"periodicidad «{p}»: no se proyecta"
    if t.startswith("anual") or "anual desde" in t:          # «bienal (anual desde 2024)»: hoy es anual
        return "anual", ""
    if "impares" in t:
        return "impares", ""
    if "pares" in t:
        return "pares", ""
    return None, f"periodicidad «{p}» no reconocida"


def leer_regimen(mes_tipico) -> tuple[int | None, frozenset]:
    """Del texto de mes_tipico: desde que anio vale el regimen actual y que anios fueron atipicos.
    «junio-julio (hasta 2023); octubre (desde 2024)» -> (2024, {});  «agosto (2021-2022 en noviembre)» -> (None, {2021, 2022})."""
    if R.vacio(mes_tipico):
        return None, frozenset()
    t = str(mes_tipico)
    desde = re.findall(r"desde (\d{4})", t)
    excl = set()
    for a, b in re.findall(r"(\d{4})-(\d{4}) en", t):
        excl |= set(range(int(a), int(b) + 1))
    return (int(desde[-1]) if desde else None), frozenset(excl)


def edicion_de(nombre: str):
    """('romano'|'arabigo'|'anios', numero) de la edicion escrita entre parentesis, o None."""
    m = re.search(r"\(([^)]*)\)", str(nombre))
    if not m:
        return None
    tok = re.split(r"[;,]", m.group(1))[0].strip()
    if re.fullmatch(r"\d+ años", tok):
        return "anios", int(tok.split()[0])
    if re.fullmatch(r"\d+", tok):
        return "arabigo", int(tok)
    n = R.de_romano(tok)
    return ("romano", n) if n else None


def edicion(s: R.Serie, anio: int) -> str:
    """Texto de la edicion del anio proyectado, en el mismo estilo que la ultima edicion conocida, o ''."""
    for _, r in s.filas.sort_values("anio", ascending=False).iterrows():
        e = edicion_de(r.nombre)
        if e and (r.estado in CONSUME_EDICION or e[0] == "anios"):
            break
    else:
        return ""
    estilo, n = e
    ult = int(r.anio)
    if estilo == "anios":                                 # aniversario: cuenta anios, no ediciones
        return f"{n + anio - ult} años"
    for a in range(ult + 1, anio + 1):
        filas = s.filas[s.filas.anio == a]
        if len(filas):
            n += int(filas.iloc[-1].estado in CONSUME_EDICION or R.vacio(filas.iloc[-1].estado))
        elif a in R.anios_que_tocan(s.periodicidad, a, a):
            n += 1
    return R.a_romano(n) if estilo == "romano" else str(n)


def series(df: pd.DataFrame, hoy: date) -> list[R.Serie]:
    df = df.copy()
    df["_clave"] = [ALIAS.get((m, R.clave_nombre(n)), R.clave_nombre(n)) for m, n in zip(df.municipio, df.nombre)]
    out = []
    for (mun, k), g in df.groupby(["municipio", "_clave"], sort=False):
        g = g.sort_values("anio")
        man = g[g.calidad_fecha != R.CALIDAD_AUTO]               # lo escrito a mano manda; lo proyectado no
        man = man if len(man) else g
        ult = man.iloc[-1]
        per, motivo = leer_periodicidad(ult.periodicidad)
        bienal = per in ("pares", "impares")
        viva, aviso = R.vigencia(g, hoy, bienal)
        if per and not viva:
            per, motivo = None, aviso
        desde, excl = leer_regimen(ult.mes_tipico)
        fechados = sorted(set(man[man.fecha_inicio.notna()].anio.astype(int)))
        if per == "anual" and len(fechados) >= 2 and len({a % 2 for a in fechados}) == 1 and \
                all(b - a == 2 for a, b in zip(fechados, fechados[1:])):
            aviso = "; ".join(x for x in (aviso, "declarada anual, pero solo hay fechas cada dos anios: revisar si es "
                                                 "bienal") if x)
        if per and ult.estado == "cancelado":
            aviso = "; ".join(x for x in (aviso, f"la ultima edicion ({int(ult.anio)}) se cancelo") if x)
        out.append(R.Serie(clave=(mun, k), nombre=R.nombre_base(ult.nombre), municipio=mun, filas=g,
                           periodicidad=per, motivo_no=motivo, anio_minimo_ajuste=desde, anios_excluidos=excl, aviso=aviso if per else ""))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--seco", action="store_true", help="muestra lo que agregaria, sin escribir")
    ap.add_argument("--hoy", default=date.today().isoformat(), help="fecha de corte (por defecto, hoy)")
    ap.add_argument("--anios", type=int, default=2, help="anios despues del actual a proyectar (por defecto 2)")
    a = ap.parse_args(argv)
    R.imprimir_utf8()
    hoy = date.fromisoformat(a.hoy)
    fest = R.Festivos()
    df = pd.read_csv(CSV)
    if list(df.columns) != COLUMNAS:
        raise R.ErrorActualizador(f"columnas inesperadas en {CSV.name}: {list(df.columns)}")

    def hacer_fila(s: R.Serie, anio, ini, fin, med, txt):
        man = s.filas[s.filas.calidad_fecha != R.CALIDAD_AUTO]
        ult = (man if len(man) else s.filas).iloc[-1]
        ed = edicion(s, anio)
        fuente = f"estimada_auto {date.today().isoformat()}: {txt} (acierto {med.texto()}; dejando uno fuera " \
                 f"{med.texto_loo()})"
        if s.fuente:
            fuente += f" ; {s.fuente}"
        return {"nombre": s.nombre + (f" ({ed})" if ed else ""), "municipio": s.municipio,
                "distancia_km_manizales": int(ult.distancia_km_manizales), "anio": anio,
                "fecha_inicio": ini.isoformat(), "fecha_fin": fin.isoformat() if fin else "",
                "periodicidad": ult.periodicidad, "mes_tipico": ult.mes_tipico, "estado": "programado",
                "calidad_fecha": R.CALIDAD_AUTO, "fuente_url": fuente, "marca": "I"}

    nuevas, pend, resumen = R.planificar(series(df, hoy), fest, hoy, a.anios, "fiestas", hacer_fila)
    R.informe(nuevas, pend, resumen, "nombre")
    if a.seco:
        print("\n--seco: no se escribio nada")
        return 0
    R.anexar(CSV, COLUMNAS, nuevas)
    R.escribir_pendientes("fiestas", pend, seco=False)
    print(f"\nEscrito: {len(nuevas)} filas en {CSV.relative_to(R.RAIZ)}; pendientes en "
          f"{R.POR_CONFIRMAR.relative_to(R.RAIZ)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                                       # cualquier falla: codigo distinto de cero
        print(f"ERROR actualizar_fiestas: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
