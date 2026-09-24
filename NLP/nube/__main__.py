# -*- coding: utf-8 -*-
"""
    python -m NLP.nube --exportar --muestra 300           una muestra repartida por la tabla
    python -m NLP.nube --exportar --oids lista.txt        esos OID (uno por linea)
    python -m NLP.nube --exportar                         todas las que faltan
          [--prompt NLP/prompts/v1_7.py] [--modelo qwen3:8b] [--excluir-base] [--forzar]
    python -m NLP.nube --auditar                          revisa el paquete; si falla, lo borra
    python -m NLP.nube --importar RUTA [--mapa RUTA]      respuestas.jsonl -> resultados.parquet
    python -m NLP.nube --exportar --segunda-pasada --forzar   paquete con los descartes dudosos
    python -m NLP.nube --estado                           que hay en NLP/salidas/nube/
    python -m NLP.nube --fusionar                         resultados.parquet -> nota_triage (a mano)

Ninguno llama a un modelo. El que llama a Ollama es NLP/nube/correr_en_gpu.py, y
corre en la maquina remota. Guia: NLP/docs/NUBE.md.
"""

import argparse
import json
import sys

from NLP.nube import (AUDITORIA, CARPETA, LOTE, MAPA, PAQUETE, RESPUESTAS, RESULTADOS, REVISAR,
                      SEGUNDA)


def estado(carpeta=CARPETA):
    import pandas as pd

    print(f"{carpeta}")
    for nombre in (PAQUETE, MAPA, LOTE, AUDITORIA, RESPUESTAS, RESULTADOS, SEGUNDA, REVISAR):
        ruta = carpeta / nombre
        if not ruta.exists():
            print(f"  {nombre:<22} -")
            continue
        if nombre.endswith(".txt"):
            detalle = f"{sum(1 for l in ruta.read_text(encoding='utf-8').splitlines() if l.strip()):,} OIDs"
        elif nombre.endswith(".jsonl"):
            with open(ruta, encoding="utf-8") as archivo:
                detalle = f"{sum(1 for l in archivo if l.strip()):,} lineas"
        elif nombre.endswith(".parquet"):
            detalle = f"{len(pd.read_parquet(ruta, columns=['OID'])):,} filas"
        else:
            datos = json.loads(ruta.read_text(encoding="utf-8"))
            detalle = (f"certificado={datos.get('certificado')} fallos={sum(datos.get('fallos', {}).values())}"
                       if nombre == AUDITORIA else
                       f"{datos.get('notas', '?'):,} notas, prompt {datos.get('version_prompt')}, "
                       f"modelo {datos.get('modelo')}, {datos.get('creado')}")
        print(f"  {nombre:<22} {detalle}")
    return 0


def main(argv=None):
    from NLP.nube import exportar

    parser = argparse.ArgumentParser(prog="python -m NLP.nube")
    accion = parser.add_mutually_exclusive_group(required=True)
    accion.add_argument("--exportar", action="store_true")
    accion.add_argument("--auditar", action="store_true")
    accion.add_argument("--importar", metavar="RUTA")
    accion.add_argument("--estado", action="store_true")
    accion.add_argument("--fusionar", action="store_true")
    cual = parser.add_mutually_exclusive_group()
    cual.add_argument("--muestra", type=int, help="N notas repartidas por toda la tabla")
    cual.add_argument("--oids", metavar="ARCHIVO", help="un OID por linea")
    parser.add_argument("--prompt", default=str(exportar.PROMPT_POR_DEFECTO),
                        help="modulo .py con construir(nota) y VERSION")
    parser.add_argument("--modelo", default=exportar.MODELO)
    parser.add_argument("--excluir-base", action="store_true",
                        help="no mandar las notas que ya tienen frase en nota_triage")
    parser.add_argument("--forzar", action="store_true",
                        help="armar aunque haya un paquete anterior (su mapa se aparta, no se borra)")
    parser.add_argument("--mapa", default=None, help="otro mapa_local para --importar")
    parser.add_argument("--segunda-pasada", action="store_true",
                        help="con --exportar: solo las notas de segunda_pasada.txt (descartadas "
                             "con evidencia clinica), con el prompt que no admite abstenerse")
    args = parser.parse_args(argv)

    if args.exportar:
        return exportar.exportar(muestra=args.muestra, oids=args.oids, ruta_prompt=args.prompt,
                                 modelo=args.modelo, excluir_base=args.excluir_base,
                                 forzar=args.forzar, segunda=args.segunda_pasada)
    if args.auditar:
        from NLP.nube import auditar
        return auditar.auditar()
    if args.importar:
        from NLP.nube import importar
        resumen = importar.importar(args.importar, ruta_mapa=args.mapa)
        return 0 if isinstance(resumen, dict) else resumen
    if args.fusionar:
        from NLP.nube import importar
        importar.fusionar_en_base()
        return 0
    return estado()


if __name__ == "__main__":
    sys.exit(main())
