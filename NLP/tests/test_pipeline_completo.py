"""
Prueba de regresion de punta a punta (NLP/docs/PLAN.md E2.1): fases 1 a 5
sobre las 50 notas sinteticas deben producir el mismo CSV, byte a byte, que
tests/datos/triage_esperado.csv. Cualquier cambio de comportamiento en una
fase mueve este archivo: se regenera a proposito, nunca por accidente.

No mide correccion clinica (para eso estan test_correccion.py y las fichas de
E3-E5): mide que la salida de HOY es la salida de MANANA si nadie toco nada.
"""

from pathlib import Path

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

    assert RUTA_ESPERADO.exists(), (
        f"falta el CSV esperado en {RUTA_ESPERADO}; genera uno con "
        "prueba_pipeline (ver bitacora 2026-09-16-E2.1.md) y fijalo a mano "
        "tras revisarlo"
    )
    assert ruta_obtenida.read_bytes() == RUTA_ESPERADO.read_bytes()


def test_las_50_notas_sinteticas_se_conservan(pipeline_resultado, notas_sinteticas_df):
    conservadas, _senaladas = pipeline_resultado
    assert len(conservadas) == len(notas_sinteticas_df)
    assert set(conservadas["OID"]) == set(notas_sinteticas_df["OID"])
