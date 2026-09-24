# -*- coding: utf-8 -*-
"""Corre UN modelo sobre la sonda y guarda cada llamada en JSONL, para comparar modelos.

Se ejecuta desde la raiz del repo:
    python NLP/competencia/comparar.py --modelo llama3.1:8b --modo solo --salida X.jsonl
    python NLP/competencia/comparar.py --modelo llama3.1:8b --modo solo --reps 3 --oids-duros oids.txt ...

modo solo    el modelo solo: sin posprocesar ni segunda pasada (como NLP.duelo)
modo cadena  la cadena de produccion: filtros + segunda pasada (como NLP.banco --sonda)

No toca el repo: usa NLP.banco, NLP.cadena, NLP.fidelidad y NLP.modelo tal como estan.
Las notas solo se escriben ENMASCARADAS (notas_enmascaradas.csv); el crudo no sale.
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))

import pandas as pd

from NLP import banco, cadena, fidelidad
from NLP import modelo as motor

from NLP import rutas
# Todo el material de la competencia (muestras, notas enmascaradas, salidas) vive en
# NLP/salidas/competencia/, que git ignora: lleva texto clinico. Se cambia con COMPETENCIA=<ruta>.
AQUI = Path(os.environ.get("COMPETENCIA", rutas.SALIDAS / "competencia"))
AQUI.mkdir(parents=True, exist_ok=True)
(AQUI / "comparacion").mkdir(exist_ok=True)


def _ps():
    try:
        datos = json.loads(urllib.request.urlopen(motor.OLLAMA + "/api/ps", timeout=30).read())
        return [{"name": m["name"], "size_gb": round(m.get("size", 0) / 1e9, 2),
                 "vram_gb": round(m.get("size_vram", 0) / 1e9, 2)} for m in datos.get("models", [])]
    except Exception as e:
        return str(e)


def _descargar(modelo):
    cuerpo = json.dumps({"model": modelo, "keep_alive": 0}).encode()
    peticion = urllib.request.Request(motor.OLLAMA + "/api/generate", cuerpo,
                                      {"Content-Type": "application/json"})
    urllib.request.urlopen(peticion, timeout=300).read()


# Segunda ronda: salida estructurada. Ollama obliga a responder con este esquema,
# asi que el formato deja de depender de que el modelo obedezca "una linea".
#   motivo   solo {"motivo"}: arreglo de formato puro
#   razonado {"razonamiento", "motivo"}: deja razonar primero a TODOS los modelos
ESQUEMAS = {
    "motivo": {"type": "object", "properties": {"motivo": {"type": "string"}},
               "required": ["motivo"]},
    "razonado": {"type": "object",
                 "properties": {"razonamiento": {"type": "string"}, "motivo": {"type": "string"}},
                 "required": ["razonamiento", "motivo"]},
}


def _generar_json(modelo, prompt, esquema, num_predict, opciones=None):
    cuerpo = {"model": modelo, "prompt": prompt, "stream": False, "format": ESQUEMAS[esquema],
              "options": {**motor.OPCIONES, **(opciones or {}), "num_predict": num_predict}}
    for intento in ({**cuerpo, "think": False}, cuerpo):
        try:
            peticion = urllib.request.Request(motor.OLLAMA + "/api/generate",
                                              json.dumps(intento).encode("utf-8"),
                                              {"Content-Type": "application/json"})
            inicio = time.time()
            r = json.loads(urllib.request.urlopen(peticion, timeout=banco.TIMEOUT).read())
            return time.time() - inicio, r
        except urllib.error.HTTPError as error:
            if error.code == 400 and "think" in intento:
                continue
            raise


def _motivo_de_json(texto):
    try:
        return str(json.loads(texto).get("motivo", "")).strip()
    except Exception:
        return ""   # JSON cortado o invalido: cuenta como salida vacia (bandera formato)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--modelo", required=True)
    p.add_argument("--modo", choices=["solo", "cadena"], default="solo")
    p.add_argument("--prompt", default="NLP/prompts/v1_7.py")
    p.add_argument("--reps", type=int, default=1, help="repeticiones de las notas duras")
    p.add_argument("--oids-duros", default=None, help="archivo con un OID por linea")
    p.add_argument("--solo-duros", action="store_true", help="corre solo las notas duras")
    p.add_argument("--salida", required=True)
    p.add_argument("--muestra", default=None, help="CSV con las columnas de sonda.csv; por defecto la sonda")
    p.add_argument("--formato", choices=sorted(ESQUEMAS), default=None,
                   help="salida estructurada (segunda ronda); por defecto, texto libre")
    args = p.parse_args()

    construir, version = banco._cargar_prompt(args.prompt)
    modulo = banco._MODULO
    # Un prompt por modelo puede declarar FORMATO ("motivo"/"razonado") y OPCIONES de Ollama.
    # La temperatura se fuerza a 0 para todos: es condicion de la competencia.
    formato = args.formato or getattr(modulo, "FORMATO", None)
    opciones = {**getattr(modulo, "OPCIONES", {}), "temperature": 0}
    tabla = pd.read_csv(args.muestra or banco.SONDA, encoding="utf-8-sig", dtype=str).fillna("")

    enmascaradas = AQUI / "notas_enmascaradas.csv"
    if not enmascaradas.exists():
        pd.DataFrame({
            "OID": tabla["OID"], "banco": tabla["banco"], "tipo": tabla["tipo"],
            "nota_enmascarada": tabla["frase_original"].map(banco.enmascarar),
            "salida_referencia_v16": tabla["salida_referencia"],
        }).to_csv(enmascaradas, index=False, encoding="utf-8-sig")

    duros = set()
    if args.oids_duros and Path(args.oids_duros).exists():
        duros = {l.strip() for l in Path(args.oids_duros).read_text(encoding="utf-8").split()
                 if l.strip()}
    if args.solo_duros:
        tabla = tabla[tabla["OID"].isin(duros)]

    motor.verificar(args.modelo)
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    print(f"{args.modelo}  modo {args.modo}  prompt {version}  {len(tabla)} notas", flush=True)

    ps_hecho = False
    t0 = time.time()
    with salida.open("a", encoding="utf-8") as f:
        for _, fila in tabla.iterrows():
            reps = args.reps if fila["OID"] in duros else 1
            for rep in range(reps):
                metas = []

                def generar(prompt):
                    if formato:
                        segundos, r = _generar_json(args.modelo, prompt, formato,
                                                    opciones.get("num_predict", 200 if formato == "motivo" else 500),
                                                    opciones)
                        cruda = r.get("response") or ""
                        metas.append({k: r.get(k) for k in ("eval_count", "eval_duration",
                                      "prompt_eval_count", "prompt_eval_duration", "load_duration")}
                                     | {"segundos": round(segundos, 2), "cruda": cruda[:1500]})
                        return _motivo_de_json(cruda)
                    segundos, r = motor.generar(args.modelo, prompt, banco.TIMEOUT, opciones)
                    # 'cruda' es la respuesta entera: un modelo que conversa antes de
                    # responder pierde la linea buena en limpiar(), y para juzgar si
                    # entendio la nota hay que verla completa.
                    metas.append({k: r.get(k) for k in ("eval_count", "eval_duration",
                                  "prompt_eval_count", "prompt_eval_duration", "load_duration")}
                                 | {"segundos": round(segundos, 2),
                                    "cruda": (r.get("response") or "")[:1500],
                                    "thinking": (r.get("thinking") or "")[:300]})
                    return r.get("response", "")

                inicio = time.time()
                nueva, pasada = cadena.procesar_nota(fila["frase_original"], modulo, generar,
                                                     filtros=(args.modo == "cadena"))
                revision = fidelidad.revisar(fila["frase_original"], nueva)
                registro = {
                    "modelo": args.modelo, "modo": args.modo, "prompt": version, "formato": formato,
                    "OID": fila["OID"], "banco": fila["banco"], "tipo": fila["tipo"],
                    "rep": rep, "salida": nueva, "pasada": pasada,
                    "fuertes": [b for b in revision["banderas"] if b in fidelidad.FUERTES],
                    "suaves": [b for b in revision["banderas"] if b not in fidelidad.FUERTES],
                    "fallo": fidelidad.es_fallo(revision),
                    "segundos": round(time.time() - inicio, 2), "llamadas": metas,
                }
                if not ps_hecho:
                    registro["ps"] = _ps()
                    ps_hecho = True
                f.write(json.dumps(registro, ensure_ascii=False) + "\n")
                f.flush()
                print(f"  {fila['tipo'][:24]:<25} r{rep} {registro['segundos']:6.1f}s  "
                      f"{nueva[:70]}{'' if pasada == 'primera' else ' <' + pasada + '>'}"
                      f"  {registro['fuertes'] or ''}", flush=True)
    print(f"total {time.time() - t0:.0f} s", flush=True)
    _descargar(args.modelo)


if __name__ == "__main__":
    main()
