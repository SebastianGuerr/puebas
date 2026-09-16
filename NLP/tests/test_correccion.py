"""
Casos fijos de correccion ortografica de la sesion del 15/09 (NLP/docs/PLAN.md
E2.1), sobre las notas sinteticas de tests/datos/notas_sinteticas.csv. Corren
la cadena real de fase2_ortografia con LanguageTool sustituido (conftest.py) y
sin capa de contexto (roberta), que no hace falta para estos casos.
"""


def test_dolro_se_corrige_a_dolor(nota):
    texto = nota(900001)["texto_corregido"]
    assert "dolor" in texto
    assert "dolro" not in texto


def test_anuseas_se_corrige_a_nauseas(nota):
    texto = nota(900001)["texto_corregido"]
    assert "nauseas" in texto
    assert "anuseas" not in texto


def test_ahogado_queda_intacto(nota):
    """La nota 900003 respalda 'ahogado': el corrector no debe tocarlo."""
    texto = nota(900003)["texto_corregido"]
    assert "ahogado" in texto
    assert "abogado" not in texto


def test_volcamiento_queda_intacto(nota):
    """La nota 900004 respalda 'volcamiento' (accidente de vehiculo)."""
    texto = nota(900004)["texto_corregido"]
    assert "volcamiento" in texto
    assert "tocamiento" not in texto


def test_mareado_queda_intacto(nota):
    texto = nota(900005)["texto_corregido"]
    assert "mareado" in texto
    assert "marcado" not in texto


def test_tosiendo_queda_intacto(nota):
    texto = nota(900006)["texto_corregido"]
    assert "tosiendo" in texto
    assert "comiendo" not in texto
