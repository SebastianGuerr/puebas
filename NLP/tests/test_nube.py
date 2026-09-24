# -*- coding: utf-8 -*-
"""Pruebas de NLP/nube/. Datos SINTETICOS: ni base clinica, ni Ollama.

Los nombres de aqui son inventados. Las pruebas de enmascarado fijan las dos
cosas que no pueden fallar a la vez: que lo identificable se tape y que lo
clinico -duraciones, cifras, sintomas- llegue intacto al modelo.
"""
import ast
import http.server
import json
import threading
from datetime import datetime

import pandas as pd
import pytest

from NLP.nube import AUDITORIA, LOTE, MAPA, OPCIONES, PAQUETE, RESULTADOS, REVISAR, SEGUNDA
from NLP.nube import auditar, correr_en_gpu, exportar, importar
from NLP.nube import enmascarar as em

NOMBRES = em.Nombres(
    nombres=frozenset({"maria", "juan", "carlos", "ana", "pedro", "luis", "jose"}),
    apellidos=frozenset({"gomez", "lopez", "perez", "ramirez", "garcia", "villa"}))


def tapar(texto, identidad=None, nombres=NOMBRES):
    return em.enmascarar(texto, identidad, nombres)[0]


# ==========================================================
# IDENTIDAD DEL PROPIO PACIENTE
# ==========================================================

def test_tapa_nombre_apellidos_y_documento_del_propio_paciente():
    identidad = em.Identidad.de_valores("1053456789", ("CARLOS", "ANDRES"), ("RAMÍREZ", "OSORIO"))

    salida, conteo = em.enmascarar(
        "Paciente Carlos Andres RAMIREZ Osorio, CC 1.053.456.789, refiere cefalea",
        identidad, NOMBRES)

    plano = em._plano_1a1(salida)
    for ficha in ("carlos", "andres", "ramirez", "osorio", "053", "456"):
        assert ficha not in plano
    assert "[NOMBRE]" in salida and "[DOC]" in salida
    assert "cefalea" in salida
    assert conteo["nombre_paciente"] == 1 and conteo["doc"] == 1


def test_errata_leve_en_el_apellido_tambien_se_tapa():
    identidad = em.Identidad.de_valores("", ("NORA",), ("GONZALEZ",))

    assert tapar("paciente gonzales refiere dolor", identidad) == "paciente [NOMBRE] refiere dolor"


def test_la_errata_no_se_come_una_palabra_corriente():
    """'medica' esta a una letra de 'medina'."""
    identidad = em.Identidad.de_valores("", ("ROSA",), ("MEDINA",))

    assert tapar("requiere valoracion medica", identidad) == "requiere valoracion medica"


def test_columnas_vacias_o_nan_no_producen_fichas():
    identidad = em.Identidad.de_fila({"GPADOCUME": None, "GPANOMBRE": float("nan"),
                                      "GPASEGNOM": "", "GPAAPELLI": "NO REFIERE",
                                      "GPASEGAPE": None})

    assert identidad.fuertes == frozenset()
    assert tapar("paciente no refiere alergias", identidad) == "paciente no refiere alergias"


# ==========================================================
# LA REGLA DE LA LISTA DE BLOQUEO
# ==========================================================

def test_dolores_musculares_queda_intacto_aunque_la_paciente_se_llame_dolores():
    identidad = em.Identidad.de_valores("", ("DOLORES",), ("GARCIA", "VELEZ"))

    assert tapar("refiere dolores musculares", identidad) == "refiere dolores musculares"


def test_el_nombre_bloqueado_se_tapa_si_va_pegado_al_apellido():
    identidad = em.Identidad.de_valores("", ("DOLORES",), ("GARCIA", "VELEZ"))

    salida = tapar("paciente Dolores Garcia con dolores musculares", identidad)

    assert salida == "paciente [NOMBRE] con dolores musculares"


def test_luz_de_la_fotofobia_no_se_toca():
    identidad = em.Identidad.de_valores("", ("LUZ", "MARINA"), ("QUINTERO",))

    assert tapar("le molesta la luz", identidad) == "le molesta la luz"


@pytest.mark.parametrize("apellido, frase", [
    ("CORTES", "herida por cortes en antebrazo"),
    ("PUERTA", "golpe con la puerta en mano derecha"),
    ("ROJAS", "lesiones rojas en piernas"),
    ("PIEDRAHITA", "dolor en pie izquierdo"),
])
def test_apellidos_que_son_palabras_clinicas_no_borran_la_palabra(apellido, frase):
    identidad = em.Identidad.de_valores("", ("NORA",), (apellido,))

    assert tapar(frase, identidad) == frase


# ==========================================================
# LO CLINICO NO SE TOCA
# ==========================================================

@pytest.mark.parametrize("texto", [
    "dolor abdominal desde hace 3 dias",
    "36 semanas de gestacion",
    "gestacion de 37.4 semanas",
    "fiebre desde las 16",
    "bebe de 11 kilos",
    "eva 8/10",
    "ta 120/80 fc 88 sat 95%",
    "fuerza 5/5 en miembros",
    "glasgow 14/15",
    "plaquetas en 150.000",
    "toma 1/2 tableta",
    "hace 2-3 dias",
])
def test_duraciones_y_cifras_clinicas_intactas(texto):
    salida, conteo = em.enmascarar(texto, None, NOMBRES)

    assert salida == texto
    assert sum(conteo.values()) == 0


def test_el_conteo_trae_siempre_todos_los_tipos():
    _, conteo = em.enmascarar("tos", None, None)

    assert set(conteo) == set(em.TIPOS)


# ==========================================================
# PATRONES
# ==========================================================

@pytest.mark.parametrize("texto", [
    "cc 1053456789 consulta por tos",
    "tel 310 555 1234 consulta por tos",
    "telefono 8 87 65 43 consulta por tos",
    "documento 1.053.456.789 consulta por tos",
])
def test_numeros_largos_y_telefonos(texto):
    salida = tapar(texto)

    assert "[NUM]" in salida and "consulta por tos" in salida
    assert not any(c.isdigit() for c in salida)


@pytest.mark.parametrize("texto", [
    "fum 25/12/2024 con sangrado",
    "cirugia el 25-12-24 con sangrado",
    "cirugia el 25 de diciembre de 2024 con sangrado",
    "control 2024-12-25 con sangrado",
    "operado en diciembre de 2024 con sangrado",
    "cita hoy 23/09 con sangrado",
])
def test_fechas_completas(texto):
    salida = tapar(texto)

    assert "[FECHA]" in salida and "con sangrado" in salida
    assert "2024" not in salida and "25" not in salida and "23" not in salida


def test_correo_y_url():
    salida = tapar("escribir a Nora.Q@correo.com o ver www.ejemplo.com/x")

    assert "[CORREO]" in salida and "[URL]" in salida and "@" not in salida


# ==========================================================
# TERCEROS
# ==========================================================

@pytest.mark.parametrize("texto, esperado", [
    ("acompanado de su madre maria lopez refiere fiebre",
     "acompanado de su madre [NOMBRE] refiere fiebre"),
    ("valorado por dr perez por dolor", "valorado por dr [NOMBRE] por dolor"),
    ("sra Josefina refiere cefalea", "sra [NOMBRE] refiere cefalea"),
    ("el docrore ramirez indica consultar", "el docrore [NOMBRE] indica consultar"),
    ("citada por eld juan para control", "citada por eld [NOMBRE] para control"),
    ("hijo de la senora ana perez con fiebre", "hijo de la senora [NOMBRE] con fiebre"),
    ("juan gomez trae a su hijo con fiebre", "[NOMBRE] trae a su hijo con fiebre"),
    ("remitido por dr. carlos franco por dolor", "remitido por dr. [NOMBRE] por dolor"),
])
def test_terceros_por_contexto(texto, esperado):
    assert tapar(texto) == esperado


@pytest.mark.parametrize("texto", [
    "madre refiere que presenta tos",
    "remitido por medico general",
    "traido por policia a urgencias",
    "ojo dr enrojecido y mano dra con herida",
    "hijo de 3 anos con fiebre",
    "acompanada por su esposo quien refiere dolor",
])
def test_contexto_sin_nombre_no_tapa_nada(texto):
    assert tapar(texto) == texto


def test_tras_un_punto_empieza_otra_frase_y_no_un_nombre():
    """Falso positivo real de la calibracion (2026-09-23): la mayuscula de
    'Previamente' es la de principio de frase."""
    texto = "Paciente de 21 anos, en compania de madre y esposo. Previamente sana, sin antecedentes"

    assert tapar(texto) == texto


def test_un_apellido_comun_que_es_termino_clinico_no_se_tapa_suelto():
    """'largo' lo llevan 1.051 personas y aparece en 9 notas: por frecuencia
    parece un apellido, pero en un tacto vaginal es la longitud del cuello."""
    nombres = em.Nombres(apellidos=frozenset({"largo"}), sueltos=frozenset({"largo"}))
    texto = "tacto vaginal: cervix posterior, largo, cerrado"

    assert tapar(texto, nombres=nombres) == texto


def test_nombre_de_pila_bloqueado_pegado_a_un_nombre_tapado_se_tapa():
    """Resto real de la calibracion: 'ACEPTADA POR LUZ [NOMBRE]'."""
    nombres = em.Nombres(apellidos=frozenset({"ramirez"}), sueltos=frozenset({"ramirez"}))

    assert tapar("remision aceptada por luz ramirez", nombres=nombres) == "remision aceptada por [NOMBRE]"
    assert tapar("dolores [NOMBRE] y ramirez", nombres=nombres) == "dolores [NOMBRE] y [NOMBRE]"


def test_nombre_suelto_solo_si_es_casi_solo_nombre():
    nombres = em.Nombres(nombres=frozenset({"maria", "jose"}), apellidos=frozenset(),
                         sueltos=frozenset({"maria", "jose"}))

    assert tapar("firma maria", nombres=nombres) == "firma [NOMBRE]"
    # un santo es una institucion, no una persona
    assert tapar("remitido del hospital san jose", nombres=nombres) == "remitido del hospital san jose"


# ==========================================================
# RESIDENCIA Y DIRECCION
# ==========================================================

@pytest.mark.parametrize("texto, esperado", [
    ("residente en el barrio la enea, consulta por dolor abdominal",
     "residente en el [LUGAR], consulta por dolor abdominal"),
    ("vive en chinchina quien consulta por tos de 3 dias",
     "vive en [LUGAR] quien consulta por tos de 3 dias"),
    ("recide en neira, con dolor", "recide en [LUGAR], con dolor"),
])
def test_residencia_hasta_la_coma_o_el_conector(texto, esperado):
    assert tapar(texto) == esperado


def test_direccion():
    salida = tapar("direccion: cra 23 # 12-40 casa 3, se cayo de la escalera")

    assert "[LUGAR]" in salida and "se cayo de la escalera" in salida
    assert not any(c.isdigit() for c in salida)


# ==========================================================
# NOMBRES CONOCIDOS DESDE CUENTAS
# ==========================================================

def test_nombres_desde_cuentas_separa_palabras_de_nombres():
    de_pila = {"maria": 60000, "servio": 6}
    apellidos = {"garcia": 10000, "blando": 14, "topo": 8}
    df = {"maria": 300, "garcia": 30, "blando": 624, "topo": 2, "servio": 2}

    nombres = exportar.nombres_desde_cuentas(de_pila, apellidos, df)

    assert "blando" not in nombres.apellidos              # en las notas es palabra
    assert {"garcia", "topo"} <= nombres.apellidos
    assert nombres.sueltos == frozenset({"maria", "garcia"})   # 'topo': muy pocas personas


# ==========================================================
# ARMAR, AUDITAR, IMPORTAR (con un prompt de juguete)
# ==========================================================

PROMPT_DE_PRUEBA = '''
VERSION = "prueba-1"

def construir(nota):
    return "Estandariza el motivo.\\nNOTA:\\n" + nota.strip() + "\\nRESPUESTA:"

def posprocesar(original, salida):
    # marca si recibio la nota ORIGINAL (con el nombre) y no la enmascarada
    return salida + (" (vio original)" if "Josefina" in original else "")
'''


@pytest.fixture
def prompt(tmp_path):
    ruta = tmp_path / "prompt_prueba.py"
    ruta.write_text(PROMPT_DE_PRUEBA, encoding="utf-8")
    return ruta


def _notas(n, doc_en_texto=False):
    filas = []
    for i in range(n):
        texto = f"Paciente Josefina Quintero con tos hace {i % 5 + 1} dias"
        if doc_en_texto and i == 0:
            texto += " cc 1098765432"
        filas.append({"OID": 700000 + i, "HCTFECTRI": datetime(2025, 1, 1 + i % 28, 8),
                      "HCTMOTCON": texto, "GPADOCUME": "1098765432",
                      "GPANOMBRE": "JOSEFINA", "GPASEGNOM": None,
                      "GPAAPELLI": "QUINTERO", "GPASEGAPE": "ARCILA"})
    return pd.DataFrame(filas)


def _armar(tmp_path, prompt, n=12, **kw):
    carpeta = tmp_path / "nube"
    identidades = exportar.armar(_notas(n, **kw), NOMBRES, prompt, "qwen3:8b", carpeta,
                                 procesos=1, informar=False)
    return carpeta, identidades


def test_el_paquete_solo_lleva_id_y_prompt(tmp_path, prompt):
    carpeta, _ = _armar(tmp_path, prompt)

    lineas = [json.loads(l) for l in (carpeta / PAQUETE).read_text(encoding="utf-8").splitlines()]
    assert len(lineas) == 12
    assert all(set(l) == {"id", "prompt"} for l in lineas)
    assert len({l["id"] for l in lineas}) == 12
    assert all(len(l["id"]) == 16 and int(l["id"], 16) >= 0 for l in lineas)
    texto = (carpeta / PAQUETE).read_text(encoding="utf-8")
    assert "Josefina" not in texto and "Quintero" not in texto
    assert all(str(oid) not in texto for oid in range(700000, 700012))


def test_el_mapa_y_las_opciones_se_quedan_en_local(tmp_path, prompt):
    carpeta, _ = _armar(tmp_path, prompt)

    mapa = pd.read_parquet(carpeta / MAPA)
    assert set(mapa["OID"]) == set(range(700000, 700012))
    assert {"id", "frase_original", "texto_enmascarado", "version_prompt", "modelo"} <= set(mapa)
    opciones = json.loads((carpeta / OPCIONES).read_text(encoding="utf-8"))
    assert opciones["modelo"] == "qwen3:8b" and opciones["think"] is False
    assert opciones["options"] == {"temperature": 0, "top_p": 1, "seed": 7,
                                   "num_predict": 200, "num_ctx": 4096}
    assert "sha256_paquete" in json.loads((carpeta / LOTE).read_text(encoding="utf-8"))


def test_la_auditoria_aprueba_un_paquete_limpio(tmp_path, prompt, capsys):
    carpeta, identidades = _armar(tmp_path, prompt)

    assert auditar.auditar(carpeta, identidades=identidades) == 0
    informe = json.loads((carpeta / AUDITORIA).read_text(encoding="utf-8"))
    assert informe["certificado"] is True and informe["fallos"] == {}
    assert (carpeta / PAQUETE).exists()


def test_la_auditoria_falla_cerrado_ante_un_resto_de_documento(tmp_path, prompt, monkeypatch, capsys):
    """Si el enmascarado falla, la auditoria lo atrapa y BORRA el paquete."""
    monkeypatch.setattr(em, "enmascarar", lambda texto, identidad=None, nombres=None: (texto, {}))
    carpeta, identidades = _armar(tmp_path, prompt, doc_en_texto=True)

    assert auditar.auditar(carpeta, identidades=identidades) == 2

    assert not (carpeta / PAQUETE).exists()
    informe = json.loads((carpeta / AUDITORIA).read_text(encoding="utf-8"))
    assert informe["fallos"]["resto_de_identidad"] == 12
    assert informe["fallos"]["cifras_5_o_mas"] == 1
    # el informe son conteos: ni el nombre ni el documento
    crudo = (carpeta / AUDITORIA).read_text(encoding="utf-8") + capsys.readouterr().out
    assert "Josefina" not in crudo and "1098765432" not in crudo


def test_la_auditoria_falla_si_una_linea_trae_otra_clave(tmp_path, prompt, capsys):
    carpeta, identidades = _armar(tmp_path, prompt)
    lineas = (carpeta / PAQUETE).read_text(encoding="utf-8").splitlines()
    registro = json.loads(lineas[0])
    registro["oid"] = 1
    lineas[0] = json.dumps(registro)
    (carpeta / PAQUETE).write_text("\n".join(lineas) + "\n", encoding="utf-8")

    assert auditar.auditar(carpeta, identidades=identidades) == 2
    informe = json.loads((carpeta / AUDITORIA).read_text(encoding="utf-8"))
    assert informe["fallos"]["claves_distintas_de_id_prompt"] == 1
    assert informe["fallos"]["paquete_modificado_despues_de_armarlo"] == 1


def test_la_auditoria_falla_si_el_orden_sigue_al_oid(tmp_path, prompt, capsys):
    """Un paquete sin barajar dice la fecha de cada nota por su posicion."""
    carpeta, identidades = _armar(tmp_path, prompt, n=60)
    mapa = pd.read_parquet(carpeta / MAPA).sort_values("OID")
    por_id = {json.loads(l)["id"]: l for l in (carpeta / PAQUETE).read_text(encoding="utf-8").splitlines()}
    (carpeta / PAQUETE).write_text("\n".join(por_id[i] for i in mapa["id"]) + "\n", encoding="utf-8")
    (carpeta / LOTE).unlink()

    assert auditar.auditar(carpeta, identidades=identidades) == 2
    informe = json.loads((carpeta / AUDITORIA).read_text(encoding="utf-8"))
    assert informe["fallos"]["correlacion_posicion_vs_oid"] == 1


def test_importar_empareja_en_local_y_posprocesa_contra_la_original(tmp_path, prompt, capsys):
    carpeta, _ = _armar(tmp_path, prompt, n=3)
    mapa = pd.read_parquet(carpeta / MAPA)
    respuestas = tmp_path / "respuestas.jsonl"
    with open(respuestas, "w", encoding="utf-8") as archivo:
        for i, id_ in enumerate(mapa["id"]):
            texto = "<think>x</think>tos [NOMBRE]" if i == 0 else "tos"
            archivo.write(json.dumps({"id": id_, "respuesta": texto, "segundos": 1.0}) + "\n")
        archivo.write(json.dumps({"id": "ffffffffffffffff", "respuesta": "x"}) + "\n")
        archivo.write('{"id": "cortad')        # ultima linea a medias

    resumen = importar.importar(respuestas, carpeta=carpeta)

    assert resumen["emparejadas"] == 3 and resumen["sin_mapa"] == 1
    assert resumen["lineas_ilegibles"] == 1 and resumen["con_marcas_quitadas"] == 1
    resultados = pd.read_parquet(carpeta / RESULTADOS)
    assert list(resultados.columns) == importar.COLUMNAS
    assert set(resultados["frase_procesada"]) == {"tos (vio original)"}
    assert set(resultados["version_prompt"]) == {"prueba-1"}


PROMPT_CON_SEGUNDA = PROMPT_DE_PRUEBA.replace("prueba-1", "prueba-2") + '''
def construir_segunda_pasada(nota):
    return "SEGUNDA PASADA.\\n" + construir(nota)
'''


def _responder(carpeta, ruta, respuesta_por_nota):
    mapa = pd.read_parquet(carpeta / MAPA)
    with open(ruta, "w", encoding="utf-8") as archivo:
        for fila in mapa.itertuples():
            archivo.write(json.dumps({"id": fila.id, "respuesta": respuesta_por_nota(fila)}) + "\n")


def test_la_segunda_pasada_viaja_en_dos_paquetes_y_solo_se_fusiona_al_final(tmp_path, capsys):
    """Un descarte con evidencia clinica NO entra como resultado final: queda
    pendiente, sale en un segundo paquete con el prompt que no admite abstenerse,
    y solo si esa respuesta es fiel reemplaza al descarte."""
    ruta_prompt = tmp_path / "prompt_segunda.py"
    ruta_prompt.write_text(PROMPT_CON_SEGUNDA, encoding="utf-8")
    carpeta = tmp_path / "nube"
    notas = pd.DataFrame([
        {"OID": 800001, "HCTFECTRI": datetime(2025, 3, 1, 8), "HCTMOTCON": "REMITIDA POR HERNIA DISCAL"},
        {"OID": 800002, "HCTFECTRI": datetime(2025, 3, 1, 9), "HCTMOTCON": "ESTA CONGESTIONADO"},
        {"OID": 800003, "HCTFECTRI": datetime(2025, 3, 1, 10), "HCTMOTCON": "REMITIDO DE OTRO MUNICIPIO"},
        {"OID": 800004, "HCTFECTRI": datetime(2025, 3, 1, 11), "HCTMOTCON": "TIENE FIEBRE Y TOS"},
    ])
    for columna in ("GPADOCUME", "GPANOMBRE", "GPASEGNOM", "GPAAPELLI", "GPASEGAPE"):
        notas[columna] = None

    # primera pasada: el modelo descarta todo menos la fiebre
    exportar.armar(notas, NOMBRES, ruta_prompt, "qwen3:8b", carpeta, procesos=1, informar=False)
    _responder(carpeta, tmp_path / "r1.jsonl",
               lambda f: "fiebre y tos" if f.OID == 800004 else "sin motivo clinico")
    importar.importar(tmp_path / "r1.jsonl", carpeta=carpeta, informar=False)

    pasadas = pd.read_parquet(carpeta / RESULTADOS).set_index("OID")["pasada"]
    assert pasadas.to_dict() == {800001: "pendiente_segunda", 800002: "pendiente_segunda",
                                 800003: "primera", 800004: "primera"}
    assert (carpeta / SEGUNDA).read_text(encoding="utf-8").split() == ["800001", "800002"]

    # segunda pasada: solo las dos pendientes, con el otro prompt; la hernia se
    # recupera y la congestion se vuelve a descartar
    exportar.armar(notas[notas["OID"].isin([800001, 800002])], NOMBRES, ruta_prompt, "qwen3:8b",
                   carpeta, procesos=1, informar=False, segunda=True)
    paquete = (carpeta / PAQUETE).read_text(encoding="utf-8")
    assert paquete.count("SEGUNDA PASADA") == 2 and "800001" not in paquete
    _responder(carpeta, tmp_path / "r2.jsonl",
               lambda f: "hernia discal" if f.OID == 800001 else "sin motivo clinico")
    importar.importar(tmp_path / "r2.jsonl", carpeta=carpeta, informar=False)

    final = pd.read_parquet(carpeta / RESULTADOS).set_index("OID")
    assert final["pasada"].to_dict() == {800001: "segunda", 800002: "revisar",
                                         800003: "primera", 800004: "primera"}
    assert final.loc[800001, "frase_procesada"] == "hernia discal"
    assert (carpeta / SEGUNDA).read_text(encoding="utf-8").strip() == ""
    assert (carpeta / REVISAR).read_text(encoding="utf-8").split() == ["800002"]


def test_fusionar_no_mete_los_descartes_que_esperan_segunda_pasada(tmp_path, monkeypatch, capsys):
    import sys
    import types

    escritas = []

    class Escritor:
        def __init__(self, bloque):
            self.escritas = 0

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def agregar(self, fila):
            escritas.append(fila["OID"])
            self.escritas += 1

    monkeypatch.setitem(sys.modules, "NLP.nucleo.almacen", types.SimpleNamespace(Escritor=Escritor))
    import NLP.nucleo
    monkeypatch.setattr(NLP.nucleo, "almacen", sys.modules["NLP.nucleo.almacen"], raising=False)
    ruta = tmp_path / "resultados.parquet"
    pd.DataFrame([
        {"OID": 1, "fecha_triage": datetime(2025, 1, 1), "frase_original": "a", "frase_procesada": "tos",
         "version_prompt": "v", "modelo": "m", "pasada": "primera"},
        {"OID": 2, "fecha_triage": datetime(2025, 1, 1), "frase_original": "b",
         "frase_procesada": "sin motivo clinico", "version_prompt": "v", "modelo": "m",
         "pasada": "pendiente_segunda"},
        {"OID": 3, "fecha_triage": datetime(2025, 1, 1), "frase_original": "c",
         "frase_procesada": "sin motivo clinico", "version_prompt": "v", "modelo": "m", "pasada": "revisar"},
    ]).to_parquet(ruta, index=False)

    assert importar.fusionar_en_base(ruta) == 2
    assert escritas == [1, 3]
    assert "1 notas esperan su segunda pasada" in capsys.readouterr().out


def test_quitar_marcas():
    assert importar.quitar_marcas("tos, [NOMBRE] refiere fiebre [FECHA]") == ("tos, refiere fiebre", True)
    assert importar.quitar_marcas("tos") == ("tos", False)


# ==========================================================
# correr_en_gpu.py CONTRA UN OLLAMA FALSO
# ==========================================================

def test_correr_en_gpu_solo_usa_la_biblioteca_estandar():
    """Se copia a una maquina de un tercero: no puede arrastrar codigo del proyecto."""
    import sys
    arbol = ast.parse(open(correr_en_gpu.__file__, encoding="utf-8").read())
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos |= {a.name.split(".")[0] for a in nodo.names}
        elif isinstance(nodo, ast.ImportFrom):
            modulos.add((nodo.module or "").split(".")[0])
    assert modulos <= set(sys.stdlib_module_names)


class _OllamaFalso(http.server.BaseHTTPRequestHandler):
    llamadas = []
    rechazar_think = False

    def log_message(self, *args):
        pass

    def _responder(self, codigo, cuerpo):
        datos = json.dumps(cuerpo).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(datos)))
        self.end_headers()
        self.wfile.write(datos)

    def do_GET(self):
        self._responder(200, {"models": [{"name": "qwen3:8b"}]})

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.rechazar_think and "think" in cuerpo:
            return self._responder(400, {"error": "think no soportado"})
        type(self).llamadas.append(cuerpo)
        self._responder(200, {"response": "motivo " + cuerpo["prompt"][-2:], "prompt_eval_count": 7})


@pytest.fixture
def ollama():
    _OllamaFalso.llamadas = []
    _OllamaFalso.rechazar_think = False
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _OllamaFalso)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_address[1]}"
    servidor.shutdown()
    servidor.server_close()


def _paquete(tmp_path, n=10):
    paquete = tmp_path / "paquete.jsonl"
    paquete.write_text("".join(json.dumps({"id": f"{i:016x}", "prompt": f"nota {i:02d}"}) + "\n"
                               for i in range(n)), encoding="utf-8")
    opciones = {"modelo": "qwen3:8b", "think": False, "options": {"temperature": 0}}
    return paquete, opciones, tmp_path / "respuestas.jsonl"


def _silencio(*args, **kwargs):
    pass


def test_correr_en_gpu_escribe_y_se_reanuda_sin_repetir(tmp_path, ollama):
    paquete, opciones, salida = _paquete(tmp_path)

    primera = correr_en_gpu.correr(str(paquete), opciones, str(salida), hilos=3, host=ollama,
                                   limite=4, imprimir=_silencio)
    assert primera["nuevas"] == 4 and len(_OllamaFalso.llamadas) == 4

    # una corrida anterior que murio a mitad de linea
    with open(salida, "a", encoding="utf-8") as archivo:
        archivo.write('{"id": "000000000000')

    segunda = correr_en_gpu.correr(str(paquete), opciones, str(salida), hilos=3, host=ollama,
                                   imprimir=_silencio)

    assert segunda["ya_hechas"] == 4 and segunda["nuevas"] == 6
    assert len(_OllamaFalso.llamadas) == 10                     # ninguna repetida
    registros = [json.loads(l) for l in salida.read_text(encoding="utf-8").splitlines()
                 if l.strip().endswith("}")]
    assert {r["id"] for r in registros} == {f"{i:016x}" for i in range(10)}
    assert all({"id", "respuesta", "segundos"} <= set(r) for r in registros)
    assert all(r["respuesta"] == "motivo " + r["id"][-2:] for r in registros)


def test_correr_en_gpu_quita_think_si_el_modelo_no_lo_admite(tmp_path, ollama):
    _OllamaFalso.rechazar_think = True
    paquete, opciones, salida = _paquete(tmp_path, n=3)

    resumen = correr_en_gpu.correr(str(paquete), opciones, str(salida), hilos=1, host=ollama,
                                   imprimir=_silencio)

    assert resumen["nuevas"] == 3 and resumen["fallidas"] == 0
    assert all("think" not in c for c in _OllamaFalso.llamadas)


def test_correr_en_gpu_anota_los_fallos_sin_el_prompt(tmp_path):
    paquete, opciones, salida = _paquete(tmp_path, n=2)

    resumen = correr_en_gpu.correr(str(paquete), opciones, str(salida), hilos=1,
                                   host="http://127.0.0.1:9", timeout=1, reintentos=1,
                                   espera=0, imprimir=_silencio)

    assert resumen["fallidas"] == 2
    errores = (tmp_path / "errores.jsonl").read_text(encoding="utf-8")
    assert "nota" not in errores                                 # solo id y tipo de error
