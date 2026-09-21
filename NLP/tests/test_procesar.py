"""Pruebas del armado de filas. No tocan la base de datos ni Ollama."""

from datetime import datetime

from NLP import procesar


def test_construye_las_cuatro_columnas_de_nota_triage():
    nota = {procesar.LLAVE: 123,
            procesar.COLUMNA_FECHA: datetime(2026, 3, 14, 8, 30),
            procesar.COLUMNA: "ME DUELE LA CABEZA"}

    fila = procesar.fila_optimizada(nota, lambda texto: "cefalea")

    assert fila == {
        "OID": 123,
        "fecha_triage": datetime(2026, 3, 14, 8, 30),
        "frase_original": "ME DUELE LA CABEZA",
        "frase_procesada": "cefalea",
    }


def test_al_modelo_le_llega_la_nota_cruda_sin_tocar():
    """El prompt recibe el texto tal cual esta en la BD.

    Ya no hay fases previas de limpieza: si algo modificara la nota antes de
    llegar al modelo, frase_original dejaria de ser lo que dice la base y la
    tabla no seria auditable contra ella.
    """
    visto = []
    nota = {procesar.LLAVE: 1, procesar.COLUMNA_FECHA: None,
            procesar.COLUMNA: "  PCTE C/ TOS  "}

    procesar.fila_optimizada(nota, lambda texto: visto.append(texto) or "tos")

    assert visto == ["  PCTE C/ TOS  "]


def test_solo_se_bajan_tres_columnas_de_la_base_clinica():
    """
    DIM_TRIAGE tiene trece columnas: las otras diez son nombre, documento,
    edad, medico y codigos administrativos. Dato identificable que no tiene
    por que salir de la base clinica. Ver la regla 1 de CLAUDE.md.
    """
    assert procesar.COLUMNAS_BD == ["OID", "HCTFECTRI", "HCTMOTCON"]


def test_la_fecha_viaja_desde_la_consulta_hasta_la_fila():
    """
    fecha_triage es HCTFECTRI, la fecha REAL del triage, y es la razon de ser
    de todo el proyecto: sin ella no hay serie temporal que cruzar con el
    clima. No puede perderse por el camino.
    """
    cuando = datetime(2025, 12, 31, 23, 59)
    nota = {procesar.LLAVE: 9, procesar.COLUMNA_FECHA: cuando,
            procesar.COLUMNA: "TOS"}

    assert procesar.fila_optimizada(nota, lambda _: "tos")["fecha_triage"] == cuando
