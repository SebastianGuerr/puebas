# -*- coding: utf-8 -*-
"""La cadena por nota: filtros y segunda pasada, con un modelo falso (sin Ollama)."""
import types

import pytest

from NLP import cadena, fidelidad


def _modulo():
    """Un modulo de prompt minimo: el prompt es la nota misma, marcada."""
    return types.SimpleNamespace(
        construir=lambda nota: "PRIMERA|" + nota,
        construir_segunda_pasada=lambda nota: "SEGUNDA|" + nota,
        posprocesar=lambda original, salida: salida,
    )


def _modelo(primera, segunda=None):
    """Responde 'primera' al prompt normal y 'segunda' al de segunda pasada."""
    llamadas = []

    def generar(prompt):
        llamadas.append(prompt.split("|")[0])
        return primera if prompt.startswith("PRIMERA") else segunda
    generar.llamadas = llamadas
    return generar


def test_una_salida_buena_se_queda_en_la_primera_pasada():
    generar = _modelo("fiebre y tos")
    assert cadena.procesar_nota("TIENE FIEBRE Y TOS", _modulo(), generar) == ("fiebre y tos", "primera")
    assert generar.llamadas == ["PRIMERA"]


def test_un_descarte_falso_se_arregla_en_la_segunda_pasada():
    generar = _modelo("sin motivo clinico", "hernia discal")
    salida, pasada = cadena.procesar_nota("REMITIDA POR HERNIA DISCAL", _modulo(), generar)
    assert (salida, pasada) == ("hernia discal", "segunda")
    assert generar.llamadas == ["PRIMERA", "SEGUNDA"]


def test_si_la_segunda_tambien_descarta_queda_marcada_para_revision():
    generar = _modelo("sin motivo clinico", "sin motivo clinico")
    assert cadena.procesar_nota("ESTA CONGESTIONADO", _modulo(), generar) == (fidelidad.SIN_MOTIVO, "revisar")


def test_si_la_segunda_inventa_no_se_acepta():
    # nota con sintoma pero sin lado; la segunda pasada inventa el lado
    generar = _modelo("sin motivo clinico", "dolor en mano derecha")
    assert cadena.procesar_nota("ME DUELE LA MANO", _modulo(), generar) == (fidelidad.SIN_MOTIVO, "revisar")


def test_un_tramite_descartado_no_pasa_por_segunda():
    generar = _modelo("sin motivo clinico")
    assert cadena.procesar_nota("REMITIDO DE OTRO MUNICIPIO", _modulo(), generar) == (
        "sin motivo clinico", "primera")
    assert generar.llamadas == ["PRIMERA"]


def test_sin_construir_segunda_pasada_queda_para_revision():
    modulo = _modulo()
    del modulo.construir_segunda_pasada
    generar = _modelo("sin motivo clinico")
    assert cadena.procesar_nota("REMITIDA POR HERNIA DISCAL", modulo, generar) == (
        "sin motivo clinico", "revisar")


def test_sin_filtros_es_el_modelo_solo():
    generar = _modelo("sin motivo clinico", "no deberia llamarse")
    assert cadena.procesar_nota("REMITIDA POR HERNIA DISCAL", _modulo(), generar, filtros=False) == (
        "sin motivo clinico", "primera")
    assert generar.llamadas == ["PRIMERA"]


# ---------- los arreglos de fidelidad del cierre de la fase de CPU ----------

@pytest.mark.parametrize("original, salida, esperada", [
    ("MALESTAR GENERAL DESDE ANTIER", "malestar general desde el dia anterior", "malestar general desde antier"),
    ("CEFALEA DESDE ANTIER", "cefalea desde el día anterior", "cefalea desde antier"),
])
def test_restaurar_antier_tambien_para_el_dia_anterior(original, salida, esperada):
    assert fidelidad.restaurar_antier(original, salida) == esperada


def test_un_procedimiento_con_errata_es_evidencia_clinica():
    assert fidelidad.necesita_segunda_pasada("ME HICIERON TURBIONOPLASTIA EN LA CLINICA", "sin motivo clinico")
