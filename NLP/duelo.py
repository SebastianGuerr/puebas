# -*- coding: utf-8 -*-
"""Duelo de modelos: la misma nota, el mismo prompt, SIN filtros, dos o mas modelos.

    python -m NLP.duelo --modelos qwen3:8b qwen3:14b --oids <OID> <OID> ...
    python -m NLP.duelo --modelos qwen3:8b qwen3:14b --sonda

POR QUE SIN FILTROS
    posprocesar() arregla en codigo lo que el modelo no cumple. Con filtros, dos
    modelos saldrian parecidos porque se estaria midiendo a los filtros. Aqui se
    mide al modelo solo: que tanto inventa, se abstiene y conserva por si mismo.

POR QUE UN MODELO DETRAS DE OTRO Y NO INTERCALADOS
    En CPU con 16 GB de RAM no caben dos modelos a la vez. Se corre toda la lista
    con uno, se descarga de memoria, y se carga el siguiente.
"""
import argparse
import json
import sys
import time
import urllib.request

import pandas as pd

from NLP import banco, fidelidad
from NLP import modelo as motor


def _descargar(modelo):
    cuerpo = json.dumps({"model": modelo, "keep_alive": 0}).encode()
    peticion = urllib.request.Request(motor.OLLAMA + "/api/generate", cuerpo,
                                      {"Content-Type": "application/json"})
    urllib.request.urlopen(peticion, timeout=300).read()


def _notas(oids, usar_sonda):
    if usar_sonda:
        tabla = pd.read_csv(banco.SONDA, encoding="utf-8-sig", dtype=str).fillna("")
        return tabla[["OID", "frase_original", "salida_referencia", "tipo"]]
    base = banco._leer_notas().astype(str)
    base = base[base["OID"].isin([str(o) for o in oids])]
    return base.rename(columns={"frase_procesada": "salida_referencia"}).assign(tipo="")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="python -m NLP.duelo")
    parser.add_argument("--modelos", nargs="+", required=True)
    parser.add_argument("--oids", nargs="*", default=[])
    parser.add_argument("--sonda", action="store_true")
    parser.add_argument("--prompt", default="NLP/prompts/v1_7.py")
    args = parser.parse_args(argv)

    construir, version = banco._cargar_prompt(args.prompt)
    notas = _notas(args.oids, args.sonda)
    salidas = {}
    for modelo in args.modelos:
        motor.verificar(modelo)
        tiempos = []
        for _, fila in notas.iterrows():
            inicio = time.time()
            _, respuesta = motor.generar(modelo, construir(fila["frase_original"]), 3600)
            tiempos.append(time.time() - inicio)
            nueva = motor.limpiar(respuesta.get("response", ""))
            banderas = [b for b in fidelidad.revisar(fila["frase_original"], nueva)["banderas"]
                        if b in fidelidad.FUERTES]
            salidas[(modelo, fila["OID"])] = (nueva, banderas)
            print(f"  {modelo:<11} {fila['OID']}  {tiempos[-1]:6.1f} s", flush=True)
        print(f"{modelo}: {sum(tiempos) / len(tiempos):.1f} s por nota "
              f"(la primera incluye cargar el modelo: {tiempos[0]:.1f} s)\n", flush=True)
        _descargar(modelo)

    print(f"\nDUELO  prompt {version}, sin filtros\n")
    limpias = {m: 0 for m in args.modelos}
    for _, fila in notas.iterrows():
        print(f"OID {fila['OID']}  {fila.get('tipo', '')}")
        print(f"   nota    {banco.enmascarar(fila['frase_original'])[:110]}")
        for modelo in args.modelos:
            nueva, banderas = salidas[(modelo, fila["OID"])]
            limpias[modelo] += not banderas
            print(f"   {modelo:<9}{nueva[:90]}   {'[' + ','.join(banderas) + ']' if banderas else ''}")
        print()
    print("sin banderas fuertes: " + "   ".join(f"{m} {k}/{len(notas)}" for m, k in limpias.items()))
    print("(las banderas no ven todo: el sentido invertido o una duda perdida hay que LEERLAS)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
