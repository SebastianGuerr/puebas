"""Pruebas del cliente de Ollama. No levantan el servidor ni cargan el modelo."""

import pytest

from NLP import modelo


# ==========================================================
# limpiar(): lo que llega del modelo no es lo que va al CSV
# ==========================================================

def test_quita_el_bloque_de_razonamiento():
    crudo = "<think>el paciente dice que le duele</think>\ncefalea"

    assert modelo.limpiar(crudo) == "cefalea"


def test_quita_el_encabezado_que_algunos_modelos_repiten():
    assert modelo.limpiar("Motivo de consulta: dolor abdominal") == "dolor abdominal"


def test_si_el_encabezado_ocupa_la_primera_linea_toma_la_siguiente():
    assert modelo.limpiar("MOTIVO DE CONSULTA:\nfiebre") == "fiebre"


def test_se_queda_con_una_sola_linea():
    assert modelo.limpiar("tos seca\ny ademas otra cosa") == "tos seca"


def test_quita_comillas_y_asteriscos_del_borde():
    assert modelo.limpiar('**"epistaxis"**') == "epistaxis"


@pytest.mark.parametrize("crudo", ["", None, "   ", "<think>solo piensa</think>"])
def test_respuesta_sin_contenido_devuelve_cadena_vacia(crudo):
    assert modelo.limpiar(crudo) == ""


# ==========================================================
# verificar(): falla antes de empezar, no en la primera nota
# ==========================================================

def test_acepta_el_modelo_instalado(monkeypatch):
    monkeypatch.setattr(modelo, "instalados", lambda: (["qwen3:8b"], None))

    modelo.verificar("qwen3:8b")     # no debe lanzar


def test_acepta_el_modelo_aunque_ollama_lo_liste_con_latest(monkeypatch):
    monkeypatch.setattr(modelo, "instalados", lambda: (["qwen3:latest"], None))

    modelo.verificar("qwen3")


def test_si_el_modelo_no_esta_lo_dice_y_lista_los_que_hay(monkeypatch):
    monkeypatch.setattr(modelo, "instalados", lambda: (["qwen3:4b"], None))

    with pytest.raises(SystemExit) as fallo:
        modelo.verificar("qwen3:8b")

    assert "qwen3:8b" in str(fallo.value)
    assert "qwen3:4b" in str(fallo.value)      # muestra la alternativa instalada


def test_si_ollama_no_contesta_el_mensaje_trae_el_error_real(monkeypatch):
    """El fallo concreto tiene que salir en el mensaje.

    Antes se tragaba la excepcion y siempre aconsejaba 'ollama serve', que es el
    consejo equivocado cuando el servidor ya esta arrancado y lo que falla es
    otra cosa (un proxy, un timeout, un puerto ocupado).
    """
    monkeypatch.setattr(modelo, "instalados",
                        lambda: ([], "URLError: [Errno 111] Connection refused"))

    with pytest.raises(SystemExit) as fallo:
        modelo.verificar("qwen3:8b")

    assert "Connection refused" in str(fallo.value)
