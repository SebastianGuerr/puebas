"""
Migra la cache de correcciones de una version del corrector a la siguiente.

Evita recalcular las entradas que el cambio no puede afectar. Ver
NLP/docs/OPERACION.md (politica de version del corrector, E7.2) y la decision
que motive cada migracion. Uso:

    python -m NLP.nucleo.migrar_cache --desde 4-... --hasta 5-...
    python -m NLP.nucleo.migrar_cache --desde 4-... --hasta 5-... --aplicar
"""

import argparse
import json
import re
import shutil
import sys
from datetime import datetime

from NLP import rutas

SEPARADOR = "\x00"
RE_CIFRAS = re.compile(r"\d+")
RE_PALABRA = re.compile(r"[a-záéíóúñü]{3,}", re.IGNORECASE)


def cargar(ruta=None):
    ruta = ruta or rutas.CACHE_CORRECCIONES
    return json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}


def _formas_sin_respaldo():
    """
    Formas del lexico clinico que el corpus no escribe nunca.

    Son exactamente las que `sugerencias.RESPALDO_CANDIDATO_LEXICO` dejo de
    proponer: si la correccion guardada no contiene ninguna, el candidato
    elegido no estaba entre los bloqueados y el resultado no cambia.
    """
    from NLP.fase2_ortografia import candidatos
    from NLP.recursos import lexico

    if not candidatos.CONTEO:
        tsv = rutas.DATOS / "lexicos" / "corpus_frecuencia.tsv"
        if not tsv.exists():
            raise SystemExit(
                f"falta {tsv}. Regeneralo con `python -m NLP.recursos.corpus_lexico`: "
                "sin las frecuencias del corpus no se puede saber que formas del "
                "lexico no tienen respaldo, y migrar a ciegas arruinaria la cache.")
        for linea in tsv.read_text(encoding="utf-8").splitlines():
            if linea.startswith("#") or not linea.strip():
                continue
            partes = linea.split("\t")
            if len(partes) >= 2 and partes[1].isdigit():
                candidatos.CONTEO[partes[0]] = int(partes[1])

    if not lexico.disponible():
        lexico.cargar()
    formas = set()
    for clave in lexico.terminos():
        if candidatos.frecuencia(clave) == 0:
            formas.add(clave)
    return formas


def clasificar(cache, desde, hasta, sin_respaldo):
    """
    Devuelve (migrables, a_recalcular) para las entradas de la version `desde`.

    Una entrada se migra si su correccion NO contiene ninguna forma del lexico
    sin respaldo del corpus: esas son exactamente las que el filtro nuevo dejo
    de proponer, y quitar candidatos no cambia al ganador si el ganador no
    estaba entre los quitados.

    Un cambio en la fase 1 no necesita tratarse aqui: la clave de la cache ES
    el texto ya limpio, asi que una nota cuyo texto limpio cambia produce una
    clave nueva que no existe en la cache y se recalcula sola. La comprobacion
    se deja como red de seguridad y para que el informe lo diga.
    """
    from NLP.fase1_limpieza.limpieza import limpiar_conservando_original

    migrables, recalcular = {}, []
    for clave, valor in cache.items():
        version, _, texto = clave.partition(SEPARADOR)
        if version != desde:
            continue
        limpio, _ = limpiar_conservando_original(texto)
        if RE_CIFRAS.findall(limpio) != RE_CIFRAS.findall(texto):
            recalcular.append((texto, "la fase 1 cambia sus cifras"))
            continue
        palabras = {p.lower() for p in RE_PALABRA.findall(str(valor))}
        if palabras & sin_respaldo:
            recalcular.append((texto, "correccion con forma del lexico sin respaldo"))
            continue
        migrables[hasta + SEPARADOR + texto] = valor
    return migrables, recalcular


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--desde", required=True)
    ap.add_argument("--hasta", required=True)
    ap.add_argument("--aplicar", action="store_true")
    args = ap.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cache = cargar()
    print(f"entradas en la cache: {len(cache):,}")
    print("cargando el lexico para saber que formas no respalda el corpus...")
    sin_respaldo = _formas_sin_respaldo()
    print(f"  formas del lexico sin respaldo del corpus: {len(sin_respaldo):,}")

    migrables, recalcular = clasificar(cache, args.desde, args.hasta, sin_respaldo)
    total = len(migrables) + len(recalcular)
    print(f"\nentradas de la version {args.desde}: {total:,}")
    print(f"  se migran tal cual : {len(migrables):,}")
    print(f"  hay que recalcular : {len(recalcular):,}")
    motivos = {}
    for _texto, motivo in recalcular:
        motivos[motivo] = motivos.get(motivo, 0) + 1
    for motivo, veces in sorted(motivos.items(), key=lambda x: -x[1]):
        print(f"      {veces:6}  {motivo}")

    if not args.aplicar:
        print("\nNo se escribio nada. Repetir con --aplicar.")
        return

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    copia = rutas.CACHE_CORRECCIONES.with_name(
        f"cache_correcciones.previo-{sello}.json")
    shutil.copy2(rutas.CACHE_CORRECCIONES, copia)
    cache.update(migrables)
    rutas.CACHE_CORRECCIONES.write_text(
        json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"\nMigradas {len(migrables):,} entradas a {args.hasta}.")
    print(f"Copia previa en {copia.name}.")


if __name__ == "__main__":
    main()
