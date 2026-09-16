"""Las cifras no se tocan en ninguna fase. Ver decisiones/2026-09-16-cifras.md."""

import pytest

from NLP.fase1_limpieza.limpieza import limpiar_conservando_original
from NLP.fase2_ortografia import ortografia


@pytest.mark.parametrize("texto", [
    "paciente con 1000cc de salida",
    "se aplican 1000mg de dipirona",
    "documento 30277767",
    "documento 26049320102222a",
    "hace 2000 metros",
    "saturacion 100 por ciento",
])
def test_fase1_conserva_las_cifras(texto):
    limpio, _ = limpiar_conservando_original(texto)
    assert _cifras(limpio) == _cifras(texto), (
        f"la fase 1 cambio las cifras: {texto!r} -> {limpio!r}")


@pytest.mark.parametrize("texto,esperado", [
    ("holaaaaa", "holaa"),
    ("doctorrrr", "doctorr"),
])
def test_fase1_sigue_colapsando_letras_alargadas(texto, esperado):
    limpio, _ = limpiar_conservando_original(texto)
    assert esperado in limpio


@pytest.mark.parametrize("original,reemplazo,permitido", [
    ("1000cc", "100cc", False),
    ("1000mg", "100mg", False),
    ("2000", "200", False),
    ("26049320102222a", "260493201022a", False),
    ("2tieene", "2tiene", True),
    ("dolro", "dolor", True),
])
def test_guardian_de_cifras(original, reemplazo, permitido):
    assert ortografia.mismas_cifras(original, reemplazo) is permitido


def _cifras(texto):
    import re
    return re.findall(r"\d+", texto)
