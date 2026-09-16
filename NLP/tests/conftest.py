"""
Fixtures comunes de NLP/tests/. Ver NLP/docs/PLAN.md E2.1 y la bitacora
2026-09-16-E2.1.md para el porque de cada mock (LanguageTool, BD, Ollama).

Los lexicos reales (salidas/lexico_clinico.json, lexico_casing.json,
datos/diccionario_siglas.json, embedding/datos/catalogo_sintomas.json) se leen
tal cual estan en el repo, en modo solo lectura, una vez por sesion.
"""

import re
from pathlib import Path

import pandas as pd
import pytest

RAIZ_TESTS = Path(__file__).resolve().parent
CSV_SINTETICAS = RAIZ_TESTS / "datos" / "notas_sinteticas.csv"


# ==========================================================
# SUSTITUTO DE LanguageTool
# ==========================================================
#
# El servidor real es un proceso Java que tarda segundos en arrancar y que la
# ficha de E2.1 prohibe en las pruebas. Este sustituto no evalua gramatica: solo
# conoce las erratas que las notas sinteticas necesitan para los casos fijos del
# plan ('dolro' -> 'dolor', 'anuseas' -> 'nauseas'), con la misma forma de
# Match que espera nucleo/lt_compat.py. Todo lo demas del corrector -- el
# guardian clinico, el desempate por frecuencia, la capa de coherencia -- sigue
# siendo el codigo real.

class _MatchFalso:
    def __init__(self, offset, largo, reemplazos):
        self.offset = offset
        self.error_length = largo
        self.rule_id = "FAKE_SPELLER"
        self.category = "TYPOS"
        self.replacements = reemplazos


class LanguageToolFalso:
    """Sustituto minimo de language_tool_python.LanguageTool para pruebas."""

    ERRATAS = {"dolro": ["dolor"], "anuseas": ["nauseas"]}
    RE_PALABRA = re.compile(r"[a-záéíóúüñA-ZÁÉÍÓÚÜÑ]+")

    def check(self, texto):
        salida = []
        for m in self.RE_PALABRA.finditer(texto):
            candidatas = self.ERRATAS.get(m.group(0).lower())
            if candidatas:
                salida.append(_MatchFalso(m.start(), len(m.group(0)), list(candidatas)))
        return salida

    def close(self):
        pass


# ==========================================================
# CARGA DE RECURSOS REALES (una vez por sesion)
# ==========================================================

def cargar_recursos_reales():
    """
    Carga los artefactos reales del pipeline (sin BD, sin LanguageTool, sin
    Ollama) y desactiva la capa de contexto, que cargaria un modelo roberta
    pesado. Idempotente: cada cargar() del proyecto ya lo es.
    """
    from NLP.depuracion import depuracion
    from NLP.fase2_ortografia import contexto, ortografia
    from NLP.fase3_normalizacion import normalizacion
    from NLP.recursos import casing
    from NLP.reduccion import reduccion

    # Nunca cargar el modelo roberta biomedico en pruebas: ademas de pesado,
    # descarga de Hugging Face en la primera ejecucion. Se apaga por las dos
    # vias con las que el resto del paquete lo consulta.
    contexto.disponible = lambda: False
    contexto.iniciar = lambda: False
    ortografia.USAR_CONTEXTO = False

    ortografia.cargar_siglas()
    ortografia.cargar_lexico_clinico()
    casing.cargar()
    normalizacion.cargar()
    depuracion.cargar()
    reduccion.cargar_lexico()
    reduccion.cargar_lugares()


def leer_notas_sinteticas():
    """Las 50 notas sinteticas de tests/datos/, con las columnas de la BD real."""
    return pd.read_csv(CSV_SINTETICAS, encoding="utf-8-sig")


def correr_pipeline(df):
    """
    Fases 1 a 5 sobre un DataFrame con columnas OID/HCTMOTCON, usando las
    funciones reales de procesar.py (las mismas que procesar.main() y
    reparar.py), con LanguageTool sustituido y sin LLM.

    Devuelve (conservadas, senaladas), igual que procesar.procesar_bloque().
    """
    from NLP import procesar
    from NLP.fase2_ortografia import ortografia

    ortografia.iniciar_languagetool = lambda idioma="es": LanguageToolFalso()

    # USAR_CACHE en False por las dos puntas: procesar.corregir_lote() no solo
    # LEE salidas/cache_correcciones.json con este flag, tambien ESCRIBE en el
    # cada GUARDAR_CADA notas. Sin apagarlo, una corrida de pruebas mezcla sus
    # 50 notas sinteticas con la cache real que esta llenando el proceso de
    # reparacion en curso (NLP/docs/PLAN.md, briefing E2.1).
    procesar.USAR_CACHE = False

    df = df.copy()
    ortografia.construir_lexico(df[procesar.COLUMNA])
    df = procesar.preparar(df)

    pendientes = [
        (clave, limpio, original)
        for clave, limpio, original in zip(
            df["clave"], df["texto_limpio"], df["texto_norm"])
    ]
    cache = procesar.corregir_lote(pendientes)

    conservadas, senaladas = procesar.procesar_bloque(
        df.copy(), cache, "texto_normalizado", True, False)
    return (conservadas.reset_index(drop=True), senaladas.reset_index(drop=True))


# ==========================================================
# FIXTURES DE SESION
# ==========================================================

@pytest.fixture(scope="session")
def recursos_reales():
    """Carga los lexicos y modelos reales una sola vez por sesion de pytest."""
    cargar_recursos_reales()
    return True


@pytest.fixture(scope="session")
def notas_sinteticas_df():
    return leer_notas_sinteticas()


@pytest.fixture(scope="session")
def pipeline_resultado(recursos_reales, notas_sinteticas_df):
    """
    (conservadas, senaladas) de correr las fases 1-5 reales sobre las 50 notas
    sinteticas. Se calcula una sola vez: varias pruebas lo reutilizan.
    """
    return correr_pipeline(notas_sinteticas_df)


@pytest.fixture
def nota(pipeline_resultado):
    """Devuelve una funcion fila(oid) -> Series de 'conservadas' por OID."""
    conservadas, _senaladas = pipeline_resultado

    def _buscar(oid):
        filas = conservadas.loc[conservadas["OID"] == oid]
        assert len(filas) == 1, f"OID {oid} no esta en las notas sinteticas"
        return filas.iloc[0]

    return _buscar
