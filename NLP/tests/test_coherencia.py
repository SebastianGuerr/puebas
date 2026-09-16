"""
Fase 2b (fase2_ortografia/coherencia.py): deshace correcciones que no se
sostienen contra la nota, y NO deshace las que si son correcciones validas.
Casos fijos de la sesion del 15/09 (ver NLP/docs/PLAN.md E2.1 y
decisiones/2026-09-15-coherencia.md).
"""

from NLP.fase2_ortografia import coherencia


def test_deposion_a_deposicion_no_se_revierte(recursos_reales):
    """
    'deposion' no es una palabra del espanol; 'deposicion' si lo es y
    conserva el respaldo del original (mismo criterio que
    _tiene_respaldo/_es_clinica). No debe marcarse como incidencia.
    """
    motivo = coherencia.juzgar("deposion", "deposicion")
    assert motivo is None


def test_ahogado_a_abogado_se_revierte(recursos_reales):
    """Caso historico real (E0.1): cambia el motivo de consulta por completo."""
    motivo = coherencia.juzgar("ahogado", "abogado")
    assert motivo is not None


def test_volcamiento_a_tocamiento_se_revierte(recursos_reales):
    motivo = coherencia.juzgar("volcamiento", "tocamiento")
    assert motivo is not None


def test_revisar_sobre_frase_completa_no_toca_deposion(recursos_reales):
    limpio = "paciente con deposion liquida en 6 ocasiones"
    corregido = "paciente con deposicion liquida en 6 ocasiones"
    texto, incidencias = coherencia.revisar(limpio, corregido)
    assert texto == corregido
    assert incidencias == []
