from NLP import glosario


def test_bloque_incluye_municipio_y_departamento_de_divipola():
    bloque = glosario.bloque("Paciente procedente de Medellín")

    assert "LUGARES DE COLOMBIA" in bloque
    assert "MEDELLÍN" in bloque
    assert "ANTIOQUIA" in bloque


def test_bloque_incluye_termino_canonico_del_catalogo_clinico():
    bloque = glosario.bloque("Paciente con sangrado nasal")

    assert "TERMINOLOGIA CLINICA" in bloque
    assert "epistaxis" in bloque
