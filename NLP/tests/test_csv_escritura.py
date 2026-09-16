"""
E0.4: procesar.py y reparacion/reparar.py deben escribir el mismo CSV byte a
byte para las mismas filas. reparar.escribir_csv()/escribir_reparado() usan
EscritorCSV (nucleo/salida.py); esta prueba comprueba que producen exactamente
lo que produce EscritorCSV usado directamente, que es como escribe procesar.py.
"""

import pandas as pd

from NLP.nucleo.salida import EscritorCSV
from NLP.reparacion import reparar

COLUMNAS = ["OID", "texto_original", "texto_corregido", "texto_normalizado",
            "texto_embedding"]

FILAS = pd.DataFrame([
    {"OID": 900001, "texto_original": "PACIENTE REFIERE DOLRO DE CABEZA",
     "texto_corregido": "paciente refiere dolor de cabeza",
     "texto_normalizado": "paciente refiere dolor de cabeza",
     "texto_embedding": "dolor de cabeza"},
    {"OID": 900002, "texto_original": "MC: DOLOR ABDOMINAL, NIEGA FIEBRE",
     "texto_corregido": "mc: dolor abdominal, niega fiebre",
     "texto_normalizado": "motivo de consulta: dolor abdominal, niega fiebre",
     "texto_embedding": "dolor abdominal"},
])


def test_escribir_csv_de_reparar_es_igual_al_de_procesar(tmp_path):
    ruta_procesar = tmp_path / "via_procesar.csv"
    ruta_reparar = tmp_path / "via_reparar.csv"

    # Como escribe procesar.py: EscritorCSV directo, de una sola vez.
    escritor = EscritorCSV(ruta_procesar, COLUMNAS)
    try:
        escritor.agregar(FILAS)
    finally:
        escritor.cerrar()

    # Como escribe reparacion/reparar.py.
    reparar.escribir_csv(FILAS, ruta_reparar, COLUMNAS)

    assert ruta_procesar.read_bytes() == ruta_reparar.read_bytes()


def test_escribir_reparado_usa_el_mismo_escritor(tmp_path):
    ruta_directa = tmp_path / "directo.csv"
    ruta_reparado = tmp_path / "reparado.csv"

    escritor = EscritorCSV(ruta_directa, list(FILAS.columns))
    try:
        escritor.agregar(FILAS)
    finally:
        escritor.cerrar()

    reparar.escribir_reparado(FILAS, ruta_reparado)

    assert ruta_directa.read_bytes() == ruta_reparado.read_bytes()
