"""
Pruebas de la tabla `nota_triage`. No tocan la base clinica ni Ollama.

Cada prueba trabaja sobre una base temporal propia: rutas.BASE_DATOS se
reapunta con monkeypatch. Sin eso, correr los tests pisaria la base real, que
contiene horas de generacion imposibles de rehacer sin acceso a la clinica.
"""

from datetime import datetime

import pytest

from NLP import rutas
from NLP.nucleo import almacen


@pytest.fixture
def base(tmp_path, monkeypatch):
    monkeypatch.setattr(rutas, "BASE_DATOS", tmp_path / "prueba.duckdb")
    return rutas.BASE_DATOS


def _fila(oid, procesada="cefalea", original="ME DUELE LA CABEZA", fecha=None):
    return {"OID": oid, "fecha_triage": fecha,
            "frase_original": original, "frase_procesada": procesada}


def _leer(sql):
    con = almacen.abrir(solo_lectura=True)
    try:
        return con.execute(sql).fetchone()
    finally:
        con.close()


def test_escribe_y_cuenta(base):
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(1))
        escritor.agregar(_fila(2))
    assert almacen.contar() == 2


def test_guarda_las_cuatro_columnas(base):
    """Son los tres datos que se bajan de la clinica mas el procesado."""
    cuando = datetime(2026, 3, 14, 8, 30)
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(1, procesada="cefalea",
                               original="ME DUELE LA CABEZA", fecha=cuando))

    assert _leer("""SELECT OID, fecha_triage, frase_original, frase_procesada
                    FROM nota_triage""") == (
        1, cuando, "ME DUELE LA CABEZA", "cefalea")


def test_reanuda_por_oid(base):
    """Es lo que permite relanzar una corrida de horas sin repetir trabajo."""
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(10))
        escritor.agregar(_fila(11))
    assert almacen.oids_hechos() == {10, 11}


def test_sin_base_no_hay_nada_hecho(base):
    """La primera corrida no puede fallar por no encontrar el archivo."""
    assert almacen.oids_hechos() == set()
    assert almacen.contar() == 0


def test_reprocesar_una_nota_pisa_la_version_vieja(base):
    """
    Con DO NOTHING la fila vieja se quedaria y la corrida no serviria de nada
    sin que nada avisara. Gana siempre la generacion mas reciente.
    """
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(7, procesada="dolor de cabeza"))
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(7, procesada="cefalea"))

    assert almacen.contar() == 1
    assert _leer("SELECT frase_procesada FROM nota_triage")[0] == "cefalea"


def test_reprocesar_no_borra_la_fecha_que_ya_estaba(base):
    """
    La fecha viene de la clinica y puede llegar por --fechas, aparte de la
    generacion. Un reproceso que traiga fecha en NULL no puede tirarla: por eso
    el UPDATE usa coalesce y no excluded a secas.
    """
    cuando = datetime(2026, 3, 14, 8, 30)
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(5, fecha=cuando))
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(5, procesada="otra", fecha=None))

    fecha, frase = _leer(
        "SELECT fecha_triage, frase_procesada FROM nota_triage")
    assert fecha == cuando
    assert frase == "otra"


def test_rellenar_fechas_no_toca_las_frases(base):
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(1, procesada="cefalea"))
    assert almacen.sin_fecha() == 1

    cuando = datetime(2026, 1, 2, 7, 0)
    assert almacen.guardar_fechas([(1, cuando)]) == 1

    assert almacen.sin_fecha() == 0
    assert _leer("SELECT fecha_triage, frase_procesada FROM nota_triage") == (
        cuando, "cefalea")


def test_el_bloque_se_baja_solo_al_llegar_al_tamano(base):
    """Un corte no puede perder mas que un bloque."""
    escritor = almacen.Escritor(bloque=3)
    for oid in range(1, 4):
        escritor.agregar(_fila(oid))
    assert almacen.contar() == 3          # ya en disco, sin cerrar el escritor
    assert escritor.pendientes == []


def test_salir_del_contexto_baja_lo_pendiente(base):
    """Una interrupcion a mitad de bloque no puede tirar esas notas."""
    with almacen.Escritor(bloque=100) as escritor:
        escritor.agregar(_fila(1))
        assert almacen.contar() == 0      # todavia en memoria
    assert almacen.contar() == 1


def test_importar_csv_es_repetible(base, tmp_path):
    """La migracion se puede relanzar sin duplicar ni perder nada."""
    import pandas as pd

    csv = tmp_path / "triage_limpio.csv"
    pd.DataFrame([
        {"OID": 1, "texto_original": "A", "texto_optimizado": "cefalea"},
        {"OID": 2, "texto_original": "B", "texto_optimizado": "tos"},
    ]).to_csv(csv, index=False, encoding="utf-8-sig")

    primero = almacen.importar_csv(csv)
    segundo = almacen.importar_csv(csv)

    assert primero["escritas"] == 2
    assert segundo["escritas"] == 2
    assert almacen.contar() == 2


def test_importar_csv_deja_la_fecha_pendiente(base, tmp_path):
    """El CSV viejo no traia HCTFECTRI; hay que poder detectarlo y completarlo."""
    import pandas as pd

    csv = tmp_path / "triage_limpio.csv"
    pd.DataFrame([
        {"OID": 1, "texto_original": "A", "texto_optimizado": "cefalea"},
    ]).to_csv(csv, index=False, encoding="utf-8-sig")

    resumen = almacen.importar_csv(csv)

    assert resumen["sin_fecha"] == 1
    assert almacen.sin_fecha() == 1


def test_importar_csv_se_queda_con_el_ultimo_oid_repetido(base, tmp_path):
    import pandas as pd

    csv = tmp_path / "triage_limpio.csv"
    pd.DataFrame([
        {"OID": 1, "texto_original": "A", "texto_optimizado": "viejo"},
        {"OID": 1, "texto_original": "A", "texto_optimizado": "nuevo"},
    ]).to_csv(csv, index=False, encoding="utf-8-sig")

    resumen = almacen.importar_csv(csv)

    assert resumen["repetidos"] == 1
    assert _leer("SELECT frase_procesada FROM nota_triage")[0] == "nuevo"


def test_importar_csv_sin_las_columnas_falla_claro(base, tmp_path):
    import pandas as pd

    csv = tmp_path / "otro.csv"
    pd.DataFrame([{"OID": 1, "loquesea": "x"}]).to_csv(csv, index=False)

    with pytest.raises(SystemExit, match="faltan columnas"):
        almacen.importar_csv(csv)


def test_vaciar_deja_la_tabla_en_cero_pero_no_borra_el_archivo(base):
    with almacen.Escritor() as escritor:
        escritor.agregar(_fila(1))
    borrado = almacen.vaciar()
    assert borrado["notas"] == 1
    assert almacen.contar() == 0
    # borrar el archivo tiraria tambien la tabla del otro paquete
    assert base.exists()
