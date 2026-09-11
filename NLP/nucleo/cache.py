"""
Cache en disco de un resultado caro por texto.

QUE RESUELVE
    La correccion ortografica de una nota cuesta segundos: pasa por
    LanguageTool, por SymSpell y por un modelo de contexto. Repetir una corrida
    sin cache significa volver a pagarlo entero, y con decenas de miles de notas
    eso son horas para obtener exactamente los mismos textos.

    Como la correccion depende solo del texto, guardar {texto: resultado} hace
    que la segunda corrida cueste minutos.

LA VERSION ENTRA EN LA CLAVE, Y ES LA PARTE QUE MAS IMPORTA
    El riesgo de una cache asi no es que falle: es que acierte con una respuesta
    vieja. Si el corrector cambia y la cache sigue devolviendo lo que decidio la
    version anterior, el archivo resultante mezcla dos correctores y cualquier
    medicion sobre el es enganosa, sin ningun sintoma visible.

    Por eso la version del proceso forma parte de la clave. Al tocar el
    corrector se sube ese identificador y la cache anterior deja de aplicarse
    sola, sin depender de que alguien se acuerde de borrar el archivo.

POR QUE ESTA EN nucleo/ Y NO EN LA FASE ORTOGRAFICA
    No sabe nada de ortografia: es {texto -> texto} con una version. Sirve igual
    para cualquier paso caro y determinista sobre texto, como la extraccion del
    motivo de consulta con el modelo local, que hoy cachea en memoria y pierde
    todo al terminar el proceso.
"""

import json
from pathlib import Path

SEPARADOR = "\x00"


def clave(texto, version, protegidos=()):
    """
    Clave de cache de un texto.

    Incluye tres cosas y las tres son necesarias: el texto, la version del
    proceso y los tokens protegidos. Los protegidos entran porque un mismo texto
    puede tratarse de forma distinta segun que partes esten marcadas como
    intocables -- en el corrector, segun las mayusculas del original.
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

    La relectura no es paranoia: es lo que permite guardar por bloques sin
    perder lo de los bloques anteriores, y que dos corridas sobre muestras
    distintas sumen en vez de pisarse.
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
