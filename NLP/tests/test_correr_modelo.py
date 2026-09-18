from pathlib import Path

from NLP import correr_modelo


def test_carga_los_primeros_100_oid_del_triage_antiguo(tmp_path):
    fuente = tmp_path / "triage_limpio_antiguo.csv"
    fuente.write_text(
        "OID,texto_original,texto_embedding\n"
        "101,Nota original 1,motivo antiguo 1\n"
        "102,Nota original 2,motivo antiguo 2\n",
        encoding="utf-8",
    )

    notas = correr_modelo.cargar_muestra_antigua(fuente, limite=2)

    assert [nota["ID"] for nota in notas] == ["101", "102"]
    assert [nota["HCTMOTCON"] for nota in notas] == [
        "Nota original 1",
        "Nota original 2",
    ]
    assert [nota["salida_esperada"] for nota in notas] == [
        "motivo antiguo 1",
        "motivo antiguo 2",
    ]
