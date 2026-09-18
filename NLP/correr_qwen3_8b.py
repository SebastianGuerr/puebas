# -*- coding: utf-8 -*-
"""Qwen3 8B — generalista multilingue, el mas grande que cabe en 16 GB de RAM.

Corre los primeros 100 registros de triage_limpio_antiguo.csv contra qwen3:8b y
escribe NLP/resultado_qwen3_8b.csv nota por nota.

    python -m NLP.correr_qwen3_8b

El prompt es el de NLP/prompt_normalizacion.py, identico para todos los modelos:
lo unico que cambia entre una corrida y otra es la linea MODELO de aqui abajo.
"""
from NLP.correr_modelo import correr
from NLP.rutas import PROYECTO

MODELO = "qwen3:8b"
ETIQUETA = "qwen3_8b"
FUENTE = PROYECTO / "triage_limpio_antiguo.csv"
LIMITE = 100

if __name__ == "__main__":
    correr(MODELO, ETIQUETA, fuente=FUENTE, limite=LIMITE)
