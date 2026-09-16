"""
Nivel 1 de la fase 6 (E5.7): vecino mas cercano contra el gazetteer DISTEMIST
con SapBERT-es (Apache-2.0, BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-
clinical-es, tarjeta del modelo: usar [CLS], max_length 25 para menciones
cortas). Construye un indice de embeddings normalizados de los terminos
preferidos del gazetteer y asigna cada texto al concepto de mayor producto
punto, si supera un umbral. Coste medido en esta maquina (CPU, sin GPU) y por
que el indice no se construyo completo en una sola sesion:
NLP/docs/decisiones/2026-09-16-E5.7.md.
"""

import csv
import time
from pathlib import Path

import numpy as np

from NLP import rutas

MODELO = "BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es"
LONGITUD_MAXIMA = 25          # recomendado por la tarjeta del modelo
LOTE = 32
UMBRAL_SIMILITUD = 0.80       # producto punto minimo; sin gold, no calibrado (ver decision)

_TOK = None
_MOD = None


def _cargar_modelo():
    """Carga tokenizador y modelo una sola vez por proceso; sin trust_remote_code."""
    global _TOK, _MOD
    if _MOD is not None:
        return _TOK, _MOD
    from transformers import AutoModel, AutoTokenizer
    _TOK = AutoTokenizer.from_pretrained(MODELO)
    _MOD = AutoModel.from_pretrained(MODELO)
    _MOD.eval()
    return _TOK, _MOD


def _embeber(textos, lote=LOTE):
    """Embeddings [CLS] normalizados (norma 1) de una lista de textos cortos."""
    import torch

    tok, mod = _cargar_modelo()
    vectores = []
    with torch.no_grad():
        for i in range(0, len(textos), lote):
            trozo = textos[i:i + lote]
            enc = tok(trozo, padding=True, truncation=True, max_length=LONGITUD_MAXIMA, return_tensors="pt")
            salida = mod(**enc)
            vectores.append(salida.last_hidden_state[:, 0, :].numpy())
    matriz = np.concatenate(vectores, axis=0)
    normas = np.linalg.norm(matriz, axis=1, keepdims=True)
    normas[normas == 0] = 1.0
    return matriz / normas


def _leer_conceptos(limite=None):
    """
    (codigos, terminos) de las filas `mainterm=1` del gazetteer (un termino
    preferido por concepto). Con `limite`, una muestra tomada a paso fijo
    sobre la lista completa (no las primeras N filas), para no sesgar hacia
    un tramo del vocabulario.
    """
    filas = []
    with open(rutas.GAZETTEER_DISTEMIST_TSV, encoding="utf-8", newline="") as f:
        lector = csv.DictReader(f, delimiter="\t")
        for fila in lector:
            if fila.get("mainterm") == "1":
                filas.append((fila["code"], fila["term"].strip().lower()))
    if limite and limite < len(filas):
        paso = len(filas) / limite
        filas = [filas[int(i * paso)] for i in range(limite)]
    return [c for c, _ in filas], [t for _, t in filas]


def construir_indice(limite=None, guardar=True):
    """
    Embebe los terminos preferidos del gazetteer (o una muestra de tamano
    `limite`, tomada a paso fijo) y devuelve (codigos, terminos, matriz
    normalizada). Con `guardar=True` escribe un `.npz` en
    `rutas.FASE6_SALIDAS`; el nombre lleva el tamano de la muestra si no es
    el gazetteer completo.
    """
    codigos, terminos = _leer_conceptos(limite)
    t0 = time.time()
    matriz = _embeber(terminos)
    duracion = time.time() - t0
    print(
        f"indice nivel 1: {len(codigos)} conceptos, {duracion:.1f} s "
        f"({duracion / len(codigos) * 1000:.2f} ms/concepto)"
    )
    if guardar:
        rutas.FASE6_SALIDAS.mkdir(exist_ok=True)
        destino = rutas.INDICE_CONCEPTOS_NIVEL1
        if limite:
            destino = destino.with_name(destino.stem + f"_muestra{limite}" + destino.suffix)
        np.savez_compressed(destino, codigos=np.array(codigos), terminos=np.array(terminos), matriz=matriz)
        print(f"guardado: {destino}")
    return codigos, terminos, matriz


def cargar_indice(ruta=None):
    """Indice guardado por `construir_indice`, o None si el archivo no existe."""
    ruta = Path(ruta) if ruta else rutas.INDICE_CONCEPTOS_NIVEL1
    if not ruta.exists():
        return None
    datos = np.load(ruta, allow_pickle=False)
    return list(datos["codigos"]), list(datos["terminos"]), datos["matriz"]


def vecino_mas_cercano(textos, indice, umbral=UMBRAL_SIMILITUD):
    """
    Para cada texto: `(concepto_snomed, concepto_termino, similitud)` del
    vecino de mayor producto punto en `indice`, o None si no alcanza
    `umbral`. `indice` es la tupla `(codigos, terminos, matriz)`.
    """
    codigos, terminos, matriz = indice
    vectores = _embeber(list(textos))
    similitudes = vectores @ matriz.T
    resultados = []
    for fila in similitudes:
        j = int(np.argmax(fila))
        sim = float(fila[j])
        resultados.append((codigos[j], terminos[j], sim) if sim >= umbral else None)
    return resultados


def main():
    """CLI: `python -m NLP.fase6_conceptos.nivel1 --limite-gazetteer N` construye y guarda el indice."""
    import argparse
    import sys

    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument("--limite-gazetteer", type=int, default=None)
    args = parser.parse_args()
    construir_indice(limite=args.limite_gazetteer)


if __name__ == "__main__":
    main()
