"""Nucleo/requisitos.py: la corrida se detiene si falta un artefacto exigido."""

import pytest

from NLP.nucleo import requisitos


def test_exigir_detiene_la_corrida_sin_lexico_clinico(monkeypatch, tmp_path):
    """requisitos.exigir() lanza SystemExit si falta lexico_clinico (exigido)."""
    faltante = tmp_path / "lexico_clinico_no_existe.json"
    artefactos = [
        (clave, faltante if clave == "lexico_clinico" else ruta, receta, dano, exigido)
        for clave, ruta, receta, dano, exigido in requisitos.ARTEFACTOS
    ]
    monkeypatch.setattr(requisitos, "ARTEFACTOS", artefactos)

    with pytest.raises(SystemExit):
        requisitos.exigir()


def test_exigir_no_estricto_no_detiene(monkeypatch, tmp_path):
    """Con estricto=False, la ausencia del mismo artefacto solo avisa."""
    faltante = tmp_path / "lexico_clinico_no_existe.json"
    artefactos = [
        (clave, faltante if clave == "lexico_clinico" else ruta, receta, dano, exigido)
        for clave, ruta, receta, dano, exigido in requisitos.ARTEFACTOS
    ]
    monkeypatch.setattr(requisitos, "ARTEFACTOS", artefactos)

    assert requisitos.exigir(estricto=False) is False


def test_exigir_pasa_con_los_artefactos_reales():
    """Sobre el repo tal cual esta (E0.1 ya reconstruyo los artefactos), no para."""
    assert requisitos.exigir() is True
