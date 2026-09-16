"""
Cache en disco de un resultado caro por texto: {clave: resultado}.

La clave combina texto, version del proceso y tokens protegidos, para que
cambiar de corrector invalide sola la cache anterior. Ver ARQUITECTURA.md
§2.2 (`cache.py`) para el porque de este diseno y de que vive en nucleo/.
"""

import json
from pathlib import Path

SEPARADOR = "\x00"


def clave(texto, version, protegidos=()):
    """
    Clave de cache: version + texto (+ protegidos, ordenados, si los hay).

    Los protegidos entran porque el mismo texto puede tratarse distinto segun
    que partes esten marcadas como intocables.
    """
    base = texto
    if protegidos:
        base = texto + SEPARADOR + ",".join(sorted(protegidos))
    return version + SEPARADOR + base


def leer(ruta, activa=True, silencioso=False):
    """
    Lee la cache de disco. Devuelve {} si esta desactivada, no existe o esta
    ilegible: ninguno de los tres casos es un error, solo significa que hay que
    calcularlo todo.
    """
    ruta = Path(ruta)
    if not activa or not ruta.exists():
        return {}
    try:
        cache = json.loads(ruta.read_text(encoding="utf-8"))
        if not silencioso:
            print(f"Cache previa: {len(cache):,} textos")
        return cache
    except Exception:
        if not silencioso:
            print("Cache ilegible, se ignora")
        return {}


def guardar(ruta, nuevos, activa=True):
    """
    Anade lo nuevo a la cache en disco, releyendo antes lo que ya hubiera.

    La relectura es lo que permite guardar por bloques sin perder lo de los
    bloques anteriores, y que dos corridas sobre muestras distintas sumen.
    """
    if not activa:
        return
    ruta = Path(ruta)
    cache = {}
    if ruta.exists():
        try:
            cache = json.loads(ruta.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    cache.update(nuevos)
    ruta.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
