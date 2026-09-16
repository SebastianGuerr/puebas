"""
Fase 4 (depuracion) y fase 5 (reduccion): casos fijos de la sesion del 15/09
(NLP/docs/PLAN.md E2.1).
"""

from NLP.depuracion import depuracion
from NLP.recursos import lexico
from NLP.reduccion import reduccion


def test_comisura_labial_se_conserva_en_texto_embedding(nota):
    """
    La nota 900008 describe 'desviacion de la comisura labial', el propio
    motivo de consulta. La fase 5 no debe recortarla (freno por densidad
    clinica, decisiones/2026-09-15-clasificador-freno-clinico.md).
    """
    texto = nota(900008)["texto_embedding"]
    assert "comisura labial" in texto


def test_recortar_conserva_comisura_labial_directo(recursos_reales):
    texto = ("consulta por cuadro clinico de 8 dias de evolucion consistente "
             "en desviacion de la comisura labial lado izquierdo, sin perdida "
             "de fuerza")
    reducido = reduccion.recortar(texto)
    assert "comisura labial" in reducido


def test_tramite_puro_se_descarta(monkeypatch):
    """
    Nota sin ningun termino clinico, solo tramite ('remitido de <IPS>').
    depuracion.evaluar() debe marcarla TRAMITE.

    HALLAZGO (ver bitacora 2026-09-16-E2.1.md): con el lexico_clinico.json real
    cargado, 'remitido de ips la esperanza' y 'solicita certificado de
    incapacidad' (las dos notas de tramite puro de tests/datos/) NO se marcan
    TRAMITE: 'salud' y 'esperanza' entran como terminos curados (diccionario y
    CIE-10) y 'solicita' comparte raiz con un rotulo administrativo del CIE-10,
    asi que depuracion.terminos_clinicos() encuentra 'evidencia clinica' donde
    no la hay. Por eso esta prueba aisla la funcion del ruido del lexico real
    (monkeypatch a lexico vacio, que dispensa solo el catalogo de sintomas) en
    lugar de usar las notas sinteticas: verifica la LOGICA de solo_tramite(),
    no el lexico curado, que es donde esta el defecto real.
    """
    monkeypatch.setattr(lexico, "_TERMINOS", {})
    monkeypatch.setattr(depuracion, "_RAICES", None)
    monkeypatch.setattr(depuracion, "_FRASES", None)
    monkeypatch.setattr(depuracion, "_STEMMER", None)

    depuracion.cargar()
    util, motivo = depuracion.evaluar("remitido de ips la esperanza")

    assert util is False
    assert motivo == depuracion.TRAMITE


def test_solo_tramite_exige_al_menos_una_palabra_de_tramite(monkeypatch):
    """Sin ninguna palabra de la lista de tramite, no se marca solo_tramite."""
    monkeypatch.setattr(lexico, "_TERMINOS", {})
    monkeypatch.setattr(depuracion, "_RAICES", None)
    monkeypatch.setattr(depuracion, "_FRASES", None)
    monkeypatch.setattr(depuracion, "_STEMMER", None)
    depuracion.cargar()

    assert depuracion.solo_tramite("assbsaluda san cayetano") is False
