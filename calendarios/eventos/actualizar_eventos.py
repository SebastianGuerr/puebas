"""
Proyecta los eventos recurrentes de Manizales (calendarios/eventos_manizales_2020_2026.csv) a los anios que faltan.

    python calendarios/eventos/actualizar_eventos.py              agrega lo que falte y rehace la lista por confirmar
    python calendarios/eventos/actualizar_eventos.py --seco       muestra lo que agregaria, sin escribir nada
    python calendarios/eventos/actualizar_eventos.py --hoy 2026-10-15 --anios 2

Nunca modifica una fila existente: solo AGREGA al final, con estado=programado y calidad_fecha=estimada_auto. Es
idempotente (una serie con fila en un anio, de cualquier estado, no recibe otra). La regla de cada evento y su
acierto medido estan en calendarios/docs/ACTUALIZADORES.md. Sale con codigo 1 si algo falla.
"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import reglas as R  # noqa: E402

CSV = R.RAIZ / "calendarios/eventos_manizales_2020_2026.csv"
COLUMNAS = ["nombre_evento", "edicion", "anio", "fecha_inicio", "fecha_fin", "duracion_dias", "categoria", "municipio",
            "lugar", "descripcion", "estado", "calidad_fecha", "asistencia_impacto", "fuente_url"]

ALIAS = {"grita rock / grita fest": "grita fest"}           # 2020-2021 se llamaba asi y no tenia fecha
NUNCA = {"emergencia"}                                        # categorias que no son eventos programados
HASTA = {   # limites legales o anunciados: despues de esta fecha la serie no se proyecta
    "temporada taurina": (date(2027, 7, 21), "Ley 2385 de 2024: prohibidas las corridas de toros desde el 22-07-2027"),
}
CONSUME_EDICION = {"realizado", "programado", "virtual", "hibrido", "aplazado"}   # cancelado no gasta numero


def series(df: pd.DataFrame, hoy: date) -> list[R.Serie]:
    df = df.copy()
    df["_clave"] = df.nombre_evento.map(lambda n: ALIAS.get(R.clave_nombre(n), R.clave_nombre(n)))
    out = []
    for k, g in df.groupby("_clave", sort=False):
        g = g.sort_values("anio")
        man = g[g.calidad_fecha != R.CALIDAD_AUTO]               # lo escrito a mano manda; lo proyectado no
        man = man if len(man) else g
        ult = man.iloc[-1]
        n_anios = man.anio.nunique()
        per, motivo = "anual", ""
        viva, aviso = R.vigencia(g, hoy, False)
        if ult.categoria in NUNCA:
            per, motivo = None, f"categoria {ult.categoria}: no se proyecta"
        elif n_anios < 2:
            per, motivo = None, "un solo anio: evento no recurrente"
        elif not viva:
            per, motivo = None, aviso
        hasta, nota = HASTA.get(k, (None, ""))
        out.append(R.Serie(clave=(k,), nombre=R.nombre_base(ult.nombre_evento), municipio=ult.municipio, filas=g,
                           periodicidad=per, motivo_no=motivo, hasta=hasta, nota_hasta=nota,
                           aviso=aviso if per else ""))
    return out


def edicion(s: R.Serie, anio: int, fest) -> int | None:
    """La ultima edicion que gasto numero mas una por cada anio intermedio que se espera que ocurra."""
    g = s.filas[s.filas.edicion.notna() & s.filas.estado.isin(CONSUME_EDICION)]
    if g.empty:
        return None
    ult = g.sort_values("anio").iloc[-1]
    ed, desde = int(ult.edicion), int(ult.anio)
    for a in range(desde + 1, anio + 1):
        filas = s.filas[s.filas.anio == a]
        if len(filas):
            ed += int(filas.iloc[-1].estado in CONSUME_EDICION or R.vacio(filas.iloc[-1].estado))
        elif a in R.anios_que_tocan(s.periodicidad, a, a):
            ed += 1
    return ed


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
        ed = edicion(s, anio, fest)
        return {"nombre_evento": s.nombre, "edicion": ed, "anio": anio, "fecha_inicio": ini.isoformat(),
                "fecha_fin": fin.isoformat() if fin else "", "duracion_dias": ((fin - ini).days + 1) if fin else "",
                "categoria": ult.categoria, "municipio": ult.municipio, "lugar": ult.lugar,
                "descripcion": f"Proyeccion automatica {date.today().isoformat()}: regla «{txt}»; acierto {med.texto()}; "
                               f"dejando uno fuera {med.texto_loo()}. POR CONFIRMAR",
                "estado": "programado", "calidad_fecha": R.CALIDAD_AUTO, "asistencia_impacto": "",
                "fuente_url": s.fuente}

    nuevas, pend, resumen = R.planificar(series(df, hoy), fest, hoy, a.anios, "eventos", hacer_fila)
    R.informe(nuevas, pend, resumen, "nombre_evento")
    if a.seco:
        print("\n--seco: no se escribio nada")
        return 0
    R.anexar(CSV, COLUMNAS, nuevas)
    R.escribir_pendientes("eventos", pend, seco=False)
    print(f"\nEscrito: {len(nuevas)} filas en {CSV.relative_to(R.RAIZ)}; pendientes en "
          f"{R.POR_CONFIRMAR.relative_to(R.RAIZ)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:                                       # cualquier falla: codigo distinto de cero
        print(f"ERROR actualizar_eventos: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(1)
