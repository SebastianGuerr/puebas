# -*- coding: utf-8 -*-
"""Segunda pasada sobre las notas que la disparan, con el MISMO modelo o con OTRO.

    python segunda.py --primera qwen3:8b --segunda qwen3:8b --oids oids_segunda_qwen.txt
    python segunda.py --primera qwen3:8b --segunda <gemma3:12b> --oids oids_segunda_qwen.txt

La primera pasada NO se vuelve a correr: se toma la salida ya guardada en modo solo y se le
aplica posprocesar (igual que cadena.procesar_nota). La segunda replica la logica de
NLP/cadena.py linea por linea: si sigue descartada o tiene bandera fuerte -> 'revisar'.
Escribe comparacion/segunda_<primera>__<segunda>.jsonl. Sin notas crudas en la salida.
"""
import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
import pandas as pd

from NLP import banco, fidelidad
from NLP import modelo as motor

from NLP import rutas
# Todo el material de la competencia (muestras, notas enmascaradas, salidas) vive en
# NLP/salidas/competencia/, que git ignora: lleva texto clinico. Se cambia con COMPETENCIA=<ruta>.
AQUI = Path(os.environ.get("COMPETENCIA", rutas.SALIDAS / "competencia"))
AQUI.mkdir(parents=True, exist_ok=True)
(AQUI / "comparacion").mkdir(exist_ok=True)
ARCHIVOS = {"qwen3:8b": ["qwen3-8b_solo.jsonl", "qwen3-8b_nueva.jsonl"],
            "hf.co/bartowski/google_gemma-3-12b-it-GGUF:Q4_K_M": ["bartowski-google_gemma-3-12b-it-GGUF-Q4_K_M_m64.jsonl"],
            "gemma4:12b-it-qat": ["gemma4-12b-it-qat_m64.jsonl"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--primera", required=True)
    p.add_argument("--segunda", required=True)
    p.add_argument("--oids", required=True)
    a = p.parse_args()
    banco._cargar_prompt("NLP/prompts/v1_7.py")
    m = banco._MODULO
    notas = pd.read_csv(AQUI / "muestra64.csv", encoding="utf-8-sig", dtype=str).fillna("").set_index("OID")
    oids = [l.strip() for l in open(AQUI / a.oids, encoding="utf-8") if l.strip()]
    primeras = {}
    for nombre in ARCHIVOS[a.primera]:
        for linea in open(AQUI / "comparacion" / nombre, encoding="utf-8"):
            r = json.loads(linea)
            primeras[r["OID"]] = r["salida"]
    motor.verificar(a.segunda)
    corto = lambda s: s.replace("hf.co/bartowski/", "").split(":")[0].replace("/", "-")
    salida = AQUI / "comparacion" / f"segunda_{corto(a.primera)}__{corto(a.segunda)}.jsonl"
    with open(salida, "w", encoding="utf-8") as f:
        for oid in oids:
            texto = notas.at[oid, "frase_original"]
            primera = m.posprocesar(texto, primeras[oid]) if primeras[oid] else primeras[oid]
            assert fidelidad.necesita_segunda_pasada(texto, primera), oid
            segundos, r = motor.generar(a.segunda, m.construir_segunda_pasada(texto), banco.TIMEOUT)
            cruda = motor.limpiar(r.get("response", ""))
            segunda = m.posprocesar(texto, cruda) if cruda else cruda
            sigue = fidelidad.plano(segunda).strip() in ("", fidelidad.SIN_MOTIVO)
            fuertes = [b for b in fidelidad.revisar(texto, segunda)["banderas"] if b in fidelidad.FUERTES]
            final, pasada = (fidelidad.SIN_MOTIVO, "revisar") if sigue or fuertes else (segunda, "segunda")
            reg = {"primera": a.primera, "segunda_modelo": a.segunda, "OID": oid,
                   "tipo": notas.at[oid, "tipo"], "salida_primera": primera,
                   "salida_segunda": segunda, "fuertes_segunda": fuertes,
                   "final": final, "pasada": pasada, "segundos": round(segundos, 1)}
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
            print(f"  {oid} {notas.at[oid, 'tipo'][:22]:<23} {segundos:6.1f}s  {pasada:<8} {final[:60]}  {fuertes or ''}", flush=True)
    cuerpo = json.dumps({"model": a.segunda, "keep_alive": 0}).encode()
    import urllib.request
    urllib.request.urlopen(urllib.request.Request(motor.OLLAMA + "/api/generate", cuerpo,
                                                  {"Content-Type": "application/json"}), timeout=300).read()


if __name__ == "__main__":
    main()
