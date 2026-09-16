"""
Prueba de regresion de punta a punta (NLP/docs/PLAN.md E2.1): fases 1 a 5
sobre las 50 notas sinteticas deben producir el mismo CSV, byte a byte, que
tests/datos/triage_esperado.csv. Cualquier cambio de comportamiento en una
fase mueve este archivo: se regenera a proposito, nunca por accidente.

No mide correccion clinica (para eso estan test_correccion.py y las fichas de
E3-E5): mide que la salida de HOY es la salida de MANANA si nadie toco nada.
"""

import os
from pathlib import Path

import pytest

from NLP.nucleo.salida import EscritorCSV

RUTA_ESPERADO = Path(__file__).resolve().parent / "datos" / "triage_esperado.csv"

COLUMNAS = ["OID", "texto_original", "texto_corregido", "texto_normalizado",
            "texto_embedding"]


def test_fases_1_a_5_son_byte_identicas_al_csv_fijado(pipeline_resultado, tmp_path):
    conservadas, _senaladas = pipeline_resultado

    ruta_obtenida = tmp_path / "triage_obtenido.csv"
    escritor = EscritorCSV(ruta_obtenida, COLUMNAS)
    try:
        escritor.agregar(conservadas)
    finally:
        escritor.cerrar()

    # Regeneracion deliberada: REGENERAR_GOLDEN=1 python -m pytest NLP/tests -k byte
    # Se usa SOLO cuando una fase cambia de comportamiento de forma medida y
    # documentada en decisiones/. Sin la variable, la prueba solo compara.
    if os.environ.get("REGENERAR_GOLDEN") == "1":
        RUTA_ESPERADO.parent.mkdir(parents=True, exist_ok=True)
        RUTA_ESPERADO.write_bytes(ruta_obtenida.read_bytes())
        pytest.skip(f"golden regenerado a proposito en {RUTA_ESPERADO}")

    assert RUTA_ESPERADO.exists(), (
        f"falta el CSV esperado en {RUTA_ESPERADO}; regeneralo con "
        "REGENERAR_GOLDEN=1 y revisa el diff antes de fijarlo"
    )
    assert ruta_obtenida.read_bytes() == RUTA_ESPERADO.read_bytes(), (
        "la salida de las fases 1-5 cambio. Si el cambio es deliberado y esta "
        "medido, regenera con REGENERAR_GOLDEN=1 y anota la decision"
    )


def test_las_50_notas_sinteticas_se_conservan(pipeline_resultado, notas_sinteticas_df):
    conservadas, _senaladas = pipeline_resultado
    assert len(conservadas) == len(notas_sinteticas_df)
    assert set(conservadas["OID"]) == set(notas_sinteticas_df["OID"])
