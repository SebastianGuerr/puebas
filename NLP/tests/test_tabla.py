# -*- coding: utf-8 -*-
"""Pruebas de NLP/nube/tabla.py. Datos SINTETICOS: ni base clinica, ni Ollama.

La tabla es la version para analisis de lo que sale del equipo: una fila por
nota con id aleatorio, dia, nivel, banda de edad y la nota con lo identificable
BORRADO (no marcado). Las pruebas fijan que lo identificable desaparezca sin
dejar rastro, que lo clinico llegue intacto y que la auditoria falle cerrado.
"""
import gzip
import json
import re
from datetime import date, datetime

import pandas as pd
import pytest

from NLP.nube import enmascarar as em
from NLP.nube import tabla

NOMBRES = em.Nombres(
    nombres=frozenset({"maria", "juan", "carlos", "ana", "pedro", "luis", "jose"}),
    apellidos=frozenset({"gomez", "lopez", "perez", "ramirez", "garcia", "villa"}))


def borrar(texto, identidad=None, nombres=NOMBRES):
    return tabla.borrar(texto, identidad, nombres)[0]


# ==========================================================
# BORRAR, NO MARCAR
# ==========================================================

def test_borra_nombre_y_documento_del_paciente_sin_dejar_marcas():
    identidad = em.Identidad.de_valores("1053456789", ("CARLOS", "ANDRES"), ("RAMÍREZ", "OSORIO"))

    salida = borrar("Paciente Carlos Andres RAMIREZ Osorio, CC 1.053.456.789, refiere cefalea",
                    identidad)

    plano = em._plano_1a1(salida)
    for ficha in ("carlos", "andres", "ramirez", "osorio", "053", "456"):
        assert ficha not in plano
    assert "[" not in salida and "]" not in salida
    assert "refiere cefalea" in salida


@pytest.mark.parametrize("texto", [
    "acompanado de su madre maria lopez refiere fiebre",
    "tel 310 555 1234 consulta por tos",
    "escribir a Nora.Q@correo.com por dolor",
    "fum 25/12/2024 con sangrado",
    "valorado por dr perez por dolor",
    # Las tres formas que enmascarar() deja pasar a proposito -una fecha pegada a
    # un guion- y la auditoria no. Encontradas en la corrida completa del
    # 2026-09-24 (3 de 95.424 notas); estos textos son inventados con su forma.
    "cirugia (fx. -12/03/2025) a revision",
    "signos 12/120/80-16/10/98 sin cambios",
    "formula g 1-2-3-4-5-12, sin cambios",
])
def test_lo_borrado_pasa_la_revision_de_la_auditoria(texto):
    """Lo que sale de borrar() es exactamente lo que la auditoria acepta."""
    salida = borrar(texto)

    assert tabla.revisar_nota(salida, em.Identidad()) == []


def test_la_red_de_fechas_se_cuenta_aparte():
    """Lo que borra la segunda pasada queda a la vista en el conteo."""
    salida, conteo = tabla.borrar("cirugia (fx. -12/03/2025) a revision", None, NOMBRES)

    assert "12/03/2025" not in salida and "cirugia" in salida and "a revision" in salida
    assert conteo["fecha_red"] == 1


@pytest.mark.parametrize("texto", [
    "acompanado de su madre maria lopez , refiere fiebre",
    "valorado por dr perez ( ) por dolor",
    "fum 25/12/2024 , con sangrado",
])
def test_el_hueco_no_deja_espacios_dobles_ni_puntuacion_huerfana(texto):
    salida = borrar(texto)

    assert "  " not in salida
    assert " ," not in salida and ", ," not in salida
    assert "( )" not in salida and "()" not in salida
    assert salida == salida.strip(" ,;:-")


def test_borrar_no_junta_dos_numeros_que_estaban_separados():
    """Sustituir la marca por nada podria pegar '3' y '12' en '312'."""
    salida = borrar("hace 3 dias fum 25/12/2024 12 semanas")

    assert "3 dias" in salida and "12 semanas" in salida
    assert not re.search(r"\d{5,}", salida)


@pytest.mark.parametrize("texto", [
    "dolor abdominal desde hace 3 dias",
    "36 semanas de gestacion",
    "ta 120/80 fc 88 sat 95%",
    "plaquetas en 150.000",
    "hace 2-3 dias",
])
def test_lo_clinico_sale_intacto(texto):
    salida, conteo = tabla.borrar(texto, None, NOMBRES)

    assert salida == texto
    assert sum(conteo.values()) == 0


def test_saltos_de_linea_y_tabuladores_quedan_en_un_espacio():
    """Una nota con saltos de linea rompe el CSV para quien lo abra a mano."""
    assert borrar("tos\n\n  fiebre\tdesde ayer\r\n") == "tos fiebre desde ayer"


# ==========================================================
# REVISAR UNA NOTA (lo que usa la auditoria)
# ==========================================================

@pytest.mark.parametrize("nota, bandera", [
    ("consulta por tos cc 1053456789", "cifras_5_o_mas"),
    ("consulta por tos desde 25/12/2024", "fecha_completa"),
    ("escribir a nora@correo.com", "correo"),
    ("ver www.ejemplo.com/x", "url"),
    ("consulta por tos [NOMBRE]", "marca_sin_borrar"),
])
def test_revisar_nota_atrapa_cada_patron(nota, bandera):
    assert bandera in tabla.revisar_nota(nota, em.Identidad())


def test_revisar_nota_atrapa_el_nombre_del_propio_paciente():
    identidad = em.Identidad.de_valores("", ("JOSEFINA",), ("QUINTERO",))

    assert "resto_de_identidad" in tabla.revisar_nota("josefina con tos", identidad)
    assert tabla.revisar_nota("paciente con tos", identidad) == []


# ==========================================================
# ARMAR LA TABLA
# ==========================================================

def _notas(n, dias=3, con_hora=False):
    filas = []
    for i in range(n):
        dia = date(2025, 3, 1 + i % dias)
        raro = i % 7 == 0
        filas.append({
            "OID": 700000 + i,
            "fecha": datetime(dia.year, dia.month, dia.day, 14, 37) if con_hora else dia,
            "nivel": "M" if raro else "IV",
            "nivel_nombre": "MUERTO" if raro else "DIFERIDA/NO URGENTE",
            "edad_banda": ["0-4", "15-44", "65-+"][i % 3],
            "HCTMOTCON": f"Paciente Josefina Quintero con tos\nhace {i % 5 + 1} dias",
            "GPADOCUME": "1098765432", "GPANOMBRE": "JOSEFINA", "GPASEGNOM": None,
            "GPAAPELLI": "QUINTERO", "GPASEGAPE": "ARCILA"})
    return pd.DataFrame(filas)


def _armar(tmp_path, n=12, niveles_raros=frozenset({"M"}), **kw):
    carpeta = tmp_path / "tabla"
    identidades = tabla.armar(_notas(n, **kw), NOMBRES, carpeta,
                              niveles_raros=niveles_raros, informar=False)
    return carpeta, identidades


def _leer(carpeta):
    return pd.read_csv(carpeta / tabla.ARCHIVO, dtype=str, keep_default_na=False)


def test_el_csv_solo_lleva_las_seis_columnas(tmp_path):
    carpeta, _ = _armar(tmp_path)

    datos = _leer(carpeta)
    assert list(datos.columns) == ["id", "fecha", "nivel", "nivel_nombre", "edad_banda", "nota"]
    assert len(datos) == 12
    assert datos["id"].str.fullmatch(r"[0-9a-f]{16}").all() and datos["id"].is_unique
    crudo = gzip.open(carpeta / tabla.ARCHIVO, "rt", encoding="utf-8").read()
    assert "Josefina" not in crudo and "Quintero" not in crudo
    assert all(str(oid) not in crudo for oid in range(700000, 700012))


def test_la_fecha_sale_como_dia_sin_hora(tmp_path):
    carpeta, _ = _armar(tmp_path, con_hora=True)

    fechas = _leer(carpeta)["fecha"]
    assert fechas.str.fullmatch(r"\d{4}-\d{2}-\d{2}").all()
    assert "14:37" not in gzip.open(carpeta / tabla.ARCHIVO, "rt", encoding="utf-8").read()


def test_los_niveles_raros_salen_como_otro(tmp_path):
    carpeta, _ = _armar(tmp_path)

    datos = _leer(carpeta)
    assert "M" not in set(datos["nivel"]) and "MUERTO" not in set(datos["nivel_nombre"])
    assert (datos["nivel"] == "otro").sum() == 2          # i = 0 y 7
    assert set(datos.loc[datos["nivel"] == "otro", "nivel_nombre"]) == {"otro"}


def test_la_nota_sale_borrada_y_en_una_linea(tmp_path):
    carpeta, _ = _armar(tmp_path)

    notas = _leer(carpeta)["nota"]
    assert notas.str.startswith("Paciente con tos hace").all()
    assert not notas.str.contains(r"[\[\]\n]").any()


def test_el_mapa_se_queda_en_local_solo_con_id_y_oid(tmp_path):
    carpeta, _ = _armar(tmp_path)

    mapa = pd.read_parquet(carpeta / tabla.MAPA)
    assert set(mapa.columns) == {"id", "OID"}
    assert set(mapa["OID"]) == set(range(700000, 700012))
    assert set(mapa["id"]) == set(_leer(carpeta)["id"])


def test_filas_por_dia_y_al_azar_dentro_del_dia(tmp_path):
    """Ordenado por OID dentro del dia, la posicion diria la hora del triage."""
    carpeta, _ = _armar(tmp_path)

    datos = _leer(carpeta)
    assert list(zip(datos["fecha"], datos["id"])) == sorted(zip(datos["fecha"], datos["id"]))


# ==========================================================
# AUDITORIA: FALLA CERRADO
# ==========================================================

def _reescribir(carpeta, datos):
    """Cambia el CSV y re-sella la huella, para probar una sola comprobacion."""
    datos.to_csv(carpeta / tabla.ARCHIVO, index=False, compression="gzip")
    lote = json.loads((carpeta / tabla.LOTE).read_text(encoding="utf-8"))
    lote["sha256"] = tabla.huella(carpeta / tabla.ARCHIVO)
    (carpeta / tabla.LOTE).write_text(json.dumps(lote), encoding="utf-8")


def _informe(carpeta):
    return json.loads((carpeta / tabla.AUDITORIA).read_text(encoding="utf-8"))


def test_la_auditoria_aprueba_un_csv_limpio(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 0
    assert _informe(carpeta)["certificado"] is True
    assert (carpeta / tabla.ARCHIVO).exists()


def test_la_auditoria_borra_el_csv_si_el_borrado_fallo(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(em, "enmascarar", lambda texto, identidad=None, nombres=None: (texto, {}))
    carpeta, identidades = _armar(tmp_path)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2

    assert not (carpeta / tabla.ARCHIVO).exists()
    assert _informe(carpeta)["fallos"]["resto_de_identidad"] == 12
    crudo = (carpeta / tabla.AUDITORIA).read_text(encoding="utf-8") + capsys.readouterr().out
    assert "Josefina" not in crudo and "Quintero" not in crudo


def test_la_auditoria_falla_si_el_csv_cambio_despues_de_armarlo(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path)
    datos = _leer(carpeta)
    datos.loc[0, "nota"] = "consulta por tos"
    datos.to_csv(carpeta / tabla.ARCHIVO, index=False, compression="gzip")

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2
    assert _informe(carpeta)["fallos"]["archivo_modificado_despues_de_armarlo"] == 1


def test_la_auditoria_falla_si_aparece_otra_columna(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path)
    datos = _leer(carpeta)
    datos["OID"] = "1"
    _reescribir(carpeta, datos)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2
    assert _informe(carpeta)["fallos"]["columnas_distintas"] == 1


def test_la_auditoria_falla_si_la_fecha_trae_hora(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path)
    datos = _leer(carpeta)
    datos.loc[0, "fecha"] = "2025-03-01 14:37"
    _reescribir(carpeta, datos)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2
    assert _informe(carpeta)["fallos"]["fecha_no_es_un_dia"] == 1


def test_la_auditoria_falla_si_se_cuela_un_nivel_raro(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path)
    datos = _leer(carpeta)
    datos.loc[0, ["nivel", "nivel_nombre"]] = ["M", "MUERTO"]
    _reescribir(carpeta, datos)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2
    assert _informe(carpeta)["fallos"]["nivel_raro"] == 1


def test_la_auditoria_falla_si_la_edad_no_es_una_banda(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path)
    datos = _leer(carpeta)
    datos.loc[0, "edad_banda"] = "37"
    _reescribir(carpeta, datos)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2
    assert _informe(carpeta)["fallos"]["edad_fuera_de_banda"] == 1


def test_la_auditoria_falla_si_dentro_del_dia_el_orden_sigue_al_oid(tmp_path, capsys):
    carpeta, identidades = _armar(tmp_path, n=60)
    mapa = pd.read_parquet(carpeta / tabla.MAPA)
    datos = _leer(carpeta).merge(mapa, on="id").sort_values(["fecha", "OID"]).drop(columns="OID")
    _reescribir(carpeta, datos)

    assert tabla.auditar(carpeta, identidades=identidades, informar=False) == 2
    assert _informe(carpeta)["fallos"]["correlacion_dentro_del_dia_vs_oid"] == 1


def test_el_lote_cuenta_la_red_de_fechas(tmp_path):
    carpeta = tmp_path / "tabla"
    notas = _notas(3)
    notas.loc[0, "HCTMOTCON"] = "cirugia (fx. -12/03/2025) a revision"
    tabla.armar(notas, NOMBRES, carpeta, informar=False)

    lote = json.loads((carpeta / tabla.LOTE).read_text(encoding="utf-8"))
    assert lote["notas_con_algo_borrado"]["fecha_red"] == 1
