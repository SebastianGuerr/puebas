"""
Piezas comunes de los actualizadores de fuentes externas (calendarios/docs/CAPTURAS.md, «Actualización
incremental»). Tres garantías, las mismas en todas las fuentes:

    fusionar()            el pasado no se reescribe: solo se reabre la cola reciente y se rellenan huecos
    proteger()            si la fuente devuelve menos de lo que ya hay, se aborta antes de escribir
    escribir_si_cambia()  si el contenido no cambió, el archivo no se toca (un .gz reescrito cambia de bytes)

Un actualizador que falla lanza una excepción: el proceso sale con código distinto de cero.
"""
import gzip
import io
from pathlib import Path

import numpy as np
import pandas as pd


class MenosDatos(RuntimeError):
    """La fuente devolvió menos de lo que ya había: no se escribe nada."""


def proteger(viejo, nuevo, fecha, nombre, tolerancia=0.02):
    """Aborta si `nuevo` está vacío, acaba antes que `viejo`, o trae menos filas en el periodo que `viejo` cubría."""
    if viejo is None or len(viejo) == 0:
        if nuevo is None or len(nuevo) == 0:
            raise MenosDatos(f"{nombre}: la fuente no devolvió nada")
        return
    if nuevo is None or len(nuevo) == 0:
        raise MenosDatos(f"{nombre}: la fuente no devolvió nada; se conserva el archivo ({len(viejo)} filas)")
    fv, fn = pd.to_datetime(viejo[fecha]), pd.to_datetime(nuevo[fecha])
    if fn.max() < fv.max():
        raise MenosDatos(f"{nombre}: la fuente acaba el {fn.max():%Y-%m-%d} y el archivo el {fv.max():%Y-%m-%d}")
    cubierto = int((fn.between(fv.min(), fv.max())).sum())
    if cubierto < len(viejo) * (1 - tolerancia):
        raise MenosDatos(f"{nombre}: en {fv.min():%Y-%m-%d} a {fv.max():%Y-%m-%d} la fuente trae {cubierto} filas "
                         f"y el archivo {len(viejo)}")


def fusionar(viejo, nuevo, fecha, reabrir_dias, rellenar=True):
    """
    Lo que ya estaba escrito manda hasta `reabrir_dias` antes de su última fecha; desde ahí, manda la fuente.
    Con rellenar=True (tablas de una fila por día) las celdas vacías del pasado sí se completan con la fuente.
    Devuelve (tabla, revisiones): revisiones = celdas del pasado que la fuente cambió y NO se aplicaron.
    """
    if viejo is None or len(viejo) == 0:
        return nuevo.copy(), 0
    viejo, nuevo = viejo.copy(), nuevo.copy()
    viejo[fecha] = pd.to_datetime(viejo[fecha]); nuevo[fecha] = pd.to_datetime(nuevo[fecha])
    corte = viejo[fecha].max() - pd.Timedelta(days=reabrir_dias)
    fijo = viejo[viejo[fecha] < corte]
    revisiones = 0
    if rellenar:
        f = fijo.set_index(fecha)
        n = nuevo[nuevo[fecha] < corte].set_index(fecha).reindex(f.index)
        comunes = [c for c in f.columns if c in n.columns]
        a = f[comunes].apply(pd.to_numeric, errors="coerce").astype(float)
        b = n[comunes].apply(pd.to_numeric, errors="coerce").astype(float)
        revisiones = int(((a - b).abs() > 1e-9).sum().sum())
        fijo = f.combine_first(n)[f.columns.tolist() + [c for c in n.columns if c not in f.columns]].reset_index()
    tabla = pd.concat([fijo, nuevo[nuevo[fecha] >= corte]], ignore_index=True)
    orden = list(viejo.columns) + [c for c in tabla.columns if c not in viejo.columns]
    tabla = tabla[orden].sort_values(fecha, kind="stable").reset_index(drop=True)
    return tabla, revisiones


def _texto(ruta):
    b = Path(ruta).read_bytes()
    if str(ruta).endswith(".gz"):
        b = gzip.decompress(b)
    return b.replace(b"\r\n", b"\n")


def escribir_si_cambia(tabla, ruta, **to_csv):
    """Escribe `tabla` en `ruta` solo si el contenido cambia. Devuelve True si escribió."""
    ruta = Path(ruta)
    to_csv = dict(to_csv)
    compresion = to_csv.pop("compression", "gzip" if ruta.name.endswith(".gz") else None)
    buf = io.StringIO(); tabla.to_csv(buf, **to_csv)
    texto = buf.getvalue().encode(to_csv.get("encoding") or "utf-8").replace(b"\r\n", b"\n")
    if ruta.exists():
        viejo = _texto(ruta)
        if to_csv.get("encoding") == "utf-8-sig":
            viejo = viejo.removeprefix(b"\xef\xbb\xbf"); texto = texto.removeprefix(b"\xef\xbb\xbf")
        if viejo == texto:
            return False
    tmp = ruta.with_name(ruta.name + ".tmp")
    tabla.to_csv(tmp, compression=compresion, **to_csv)
    tmp.replace(ruta)                        # atómico: nunca queda un archivo a medias
    return True


def resumen(nombre, viejo, tabla, fecha, revisiones=0, escrito=True):
    """Una línea para el registro: filas nuevas, última fecha antes y después, revisiones no aplicadas."""
    va = pd.to_datetime(viejo[fecha]).max() if viejo is not None and len(viejo) else None
    vn = pd.to_datetime(tabla[fecha]).max()
    nuevas = len(tabla) - (len(viejo) if viejo is not None else 0)
    print(f"{nombre}: {len(tabla)} filas ({nuevas:+d}); ultimo dato {va:%Y-%m-%d} -> {vn:%Y-%m-%d}; "
          f"revisiones del pasado no aplicadas: {revisiones}; {'escrito' if escrito else 'sin cambios, no se toca'}"
          if va is not None else f"{nombre}: {len(tabla)} filas, hasta {vn:%Y-%m-%d}", flush=True)


def cambios_largo(previo, nuevo, llave, valor="valor", rtol=1e-5):
    """Tablas en formato largo: (filas del previo que desaparecen, valores del previo que cambian)."""
    if previo is None or len(previo) == 0:
        return 0, 0
    a = previo.set_index(llave)[valor]; b = nuevo.set_index(llave)[valor]
    a = a[~a.index.duplicated()]; b = b[~b.index.duplicated()]
    comun = a.index.intersection(b.index)
    x, y = pd.to_numeric(a[comun], errors="coerce"), pd.to_numeric(b[comun], errors="coerce")
    cambiadas = int((~np.isclose(x, y, rtol=rtol, equal_nan=True)).sum())
    return int(len(a.index.difference(b.index))), cambiadas
