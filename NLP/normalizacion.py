"""
Fase 3. Normalizacion clinica: coloquialismos y siglas.

Convierte la forma en que habla el paciente a la forma en que se escribe en una
historia clinica, sin cambiar lo que dice:

    daño de estomago  -> dispepsia          pita el oido  -> tinnitus
    culebrilla        -> herpes zoster      nacido        -> furunculo
    hta               -> hipertension arterial

POR QUE FLASHTEXT Y NO REGEX
    El diccionario tiene cientos de expresiones y crecera a miles. Con regex el
    costo crece con el numero de patrones; FlashText construye un unico automata
    (Aho-Corasick) y recorre el texto una sola vez, asi que el costo es el mismo
    con 100 terminos que con 10.000. Ademas respeta los limites de palabra, que
    es lo que permite reconocer expresiones de varias palabras sin que 'nacido'
    coincida dentro de 'recien nacido'.

POR QUE ES UNA FASE APARTE
    Mezclar normalizacion con correccion ortografica arruina la auditoria: en
    reporte_cambios.csv dejarian de distinguirse un error de digitacion y una
    expansion intencional. Se aplica sobre la columna ya corregida, y se guardan
    las dos.

ORDEN INTERNO
    1. Expresiones de varias palabras primero ('boca del estomago' antes que
       'estomago'). FlashText ya prioriza la coincidencia mas larga.
    2. Siglas despues, desde diccionario_siglas.json.

INSTALACION
    pip install flashtext
Si no esta, el modulo cae a una implementacion con expresiones regulares, mas
lenta pero equivalente.
"""

import json
import re
from pathlib import Path

import ambiguedad
import reglas

RUTA_COLOQUIAL = Path(__file__).resolve().parent / "diccionario_coloquial.json"

# "anotar":     me pita el oido -> me pita el oido (tinnitus)
# "reemplazar": me pita el oido -> me tinnitus
#
# El reemplazo literal rompe la sintaxis en las expresiones verbales, y una nota
# agramatical le cuesta mas a un modelo que la expresion popular original. La
# anotacion conserva la frase del paciente y agrega el termino clinico, con lo
# que el texto sirve tanto para leerlo como para buscar el termino estandarizado.
MODO = "anotar"

EXPANDIR_SIGLAS = True
NORMALIZAR_COLOQUIALISMOS = True
EXPANDIR_ENCABEZADOS = True   # 'aa:' -> 'aa (antecedentes alergicos):' 

# Longitud minima de una sigla para expandirla.
# Las de dos letras son ambiguas y coinciden con palabras corrientes:
# 'pa' es 'para' en habla costumbrista, 'he' es el verbo haber, 'ar', 'pr',
# 'af' y 'am' aparecen dentro de nombres propios. Expandirlas produjo
# 'ar (artritis reumatoide)anzazu' y 'he (hoja de evolucion) tenido'.
LONGITUD_MINIMA_SIGLA = 3

# Ya no existe una lista negra de siglas ambiguas. La decision la toma
# ambiguedad.evaluar(): una entrada se aplica solo si es inequivoca, y lo que no
# se puede demostrar inequivoco queda inactivo y se reporta. Perseguir casos con
# listas negras no escalaba: IVA y DAD eran la version de esta semana de SMS y
# EDA. Estas dos listas viven ahora en el JSON, como declaraciones explicitas.
_DECLARADAS_SEGURAS = set()
_DECLARADAS_AMBIGUAS = set()
_CON_CONTEXTO = {}        # clave -> (significado, palabras de contexto)
_DESACTIVADAS = []        # (clave, motivo) para el informe

_COLOQUIAL = {}
_PROCESADOR = None
_RESPALDO = None


def _sin_tildes(texto):
    return reglas.sin_tildes(texto)


# ==========================================================
# CARGA
# ==========================================================

def cargar(ruta=RUTA_COLOQUIAL, lt=None):
    """
    Lee los diccionarios y decide entrada por entrada si puede aplicarse.
    lt: instancia de LanguageTool ya creada, para el test de ambiguedad.
    """
    global _PROCESADOR, _RESPALDO

    if lt is not None:
        ambiguedad.usar_languagetool(lt)

    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    _COLOQUIAL.clear()
    _CON_CONTEXTO.clear()
    _DESACTIVADAS.clear()
    _DECLARADAS_SEGURAS.clear()
    _DECLARADAS_AMBIGUAS.clear()

    # las declaraciones viven en diccionario_siglas.json, que lee reglas.py
    _DECLARADAS_SEGURAS.update(reglas.SIGLAS_INEQUIVOCAS)
    _DECLARADAS_SEGURAS.update(x.lower() for x in datos.get("_siglas_inequivocas", []))
    _DECLARADAS_SEGURAS.update(x.lower() for x in datos.get("_expresiones_inequivocas", []))
    _DECLARADAS_AMBIGUAS.update(reglas.SIGLAS_AMBIGUAS)
    _DECLARADAS_AMBIGUAS.update(x.lower() for x in datos.get("_siglas_ambiguas", []))

    candidatas = {}

    if NORMALIZAR_COLOQUIALISMOS:
        for grupo, valor in datos.items():
            if grupo.startswith("_") or not isinstance(valor, dict):
                continue
            for expresion, definicion in valor.items():
                candidatas[expresion.lower()] = definicion

    if EXPANDIR_SIGLAS:
        for sigla, significado in reglas.EXPANDIBLES.items():
            candidatas.setdefault(sigla, significado)

    tabla = {}
    for clave, definicion in candidatas.items():
        significado = definicion["significado"] if isinstance(definicion, dict) else definicion
        estado, contexto, motivo = ambiguedad.evaluar(
            clave, definicion, _DECLARADAS_SEGURAS, _DECLARADAS_AMBIGUAS
        )

        if estado == "inactiva":
            _DESACTIVADAS.append((clave, motivo))
            continue
        if estado == "contexto":
            _CON_CONTEXTO[clave] = (significado, contexto)
            continue

        tabla[clave] = significado
        _COLOQUIAL[clave] = significado

    _PROCESADOR = _construir_flashtext(tabla)
    if _PROCESADOR is None:
        _RESPALDO = _construir_regex(tabla)

    return len(tabla)


def desactivadas():
    """Entradas que no se aplican y por que. Es la lista de decisiones pendientes."""
    return sorted(_DESACTIVADAS)


def con_contexto():
    """Entradas que solo se aplican si su contexto aparece cerca."""
    return {k: v[1] for k, v in _CON_CONTEXTO.items()}


def _construir_flashtext(tabla):
    try:
        from flashtext import KeywordProcessor
    except ModuleNotFoundError:
        print("Aviso: flashtext no instalado; se usara la version con regex.")
        return None

    kp = KeywordProcessor(case_sensitive=False)
    # FlashText define los limites de palabra solo con ASCII, asi que una vocal
    # acentuada cuenta como separador: 'ar' coincidia dentro de 'Aranzazu' y
    # 'pa' dentro de 'panal'. Sin esta linea la expansion parte las palabras.
    kp.non_word_boundaries |= set("áéíóúüñÁÉÍÓÚÜÑ")

    for expresion, termino in tabla.items():
        # una expresion mapeada a si misma es un ancla: se deja intacta
        if termino.lower() == expresion.lower():
            kp.add_keyword(expresion, expresion)
            continue
        destino = termino if MODO == "reemplazar" else f"{expresion} ({termino})"
        kp.add_keyword(expresion, destino)
        # el texto viene sin tildes en muchas notas; se registran las dos formas
        plano = _sin_tildes(expresion)
        if plano != expresion:
            destino_plano = termino if MODO == "reemplazar" else f"{plano} ({termino})"
            kp.add_keyword(plano, destino_plano)
    return kp


def _construir_regex(tabla):
    if not tabla:
        return None
    claves = sorted(tabla, key=len, reverse=True)
    patron = re.compile(r"\b(%s)\b" % "|".join(re.escape(k) for k in claves),
                        re.IGNORECASE)
    return (patron, tabla)


def disponible():
    return _PROCESADOR is not None or _RESPALDO is not None


# ==========================================================
# NORMALIZACION
# ==========================================================

# un encabezado se reconoce porque va seguido de dos puntos
RE_ENCABEZADO = re.compile(r"\b([a-záéíóúüñ]{2,6})\s*:")


def expandir_encabezados(texto):
    """
    'aa: niega' -> 'aa (antecedentes alergicos): niega'

    Conserva la sigla original, que es la forma en que el personal escribe y
    busca, y agrega el significado para que el texto se entienda solo. Se aplica
    unicamente a las siglas seguidas de dos puntos: ahi la sigla es un rotulo de
    apartado y no hay ambiguedad posible sobre lo que significa.
    """
    def _sub(m):
        sigla = m.group(1).lower()
        significado = reglas.SIGNIFICADOS.get(sigla)
        if not significado or significado in ("medicamento", "termino clinico",
                                              "nombre propio", "apellido"):
            return m.group(0)
        if significado.lower() == sigla:
            return m.group(0)
        return f"{m.group(1)} ({significado}):"

    return RE_ENCABEZADO.sub(_sub, texto)


def _aplicar_con_contexto(texto):
    """
    Entradas que solo valen cuando su contexto aparece cerca:
    'le salio un nacido en la pierna' se normaliza, 'recien nacido de 6 dias' no.
    """
    for clave, (significado, palabras) in _CON_CONTEXTO.items():
        patron = re.compile(r"\b%s\b" % re.escape(clave), re.IGNORECASE)
        resultado, ultimo = [], 0
        for m in patron.finditer(texto):
            if not ambiguedad.hay_contexto(texto, m.start(), m.end(), palabras):
                continue
            encontrado = m.group(0)
            destino = (significado if MODO == "reemplazar"
                       else f"{encontrado} ({significado})")
            resultado.append(texto[ultimo:m.start()])
            resultado.append(destino)
            ultimo = m.end()
        if resultado:
            resultado.append(texto[ultimo:])
            texto = "".join(resultado)
    return texto


def normalizar(texto):
    """Aplica encabezados, coloquialismos y siglas sobre un texto ya corregido."""
    if not texto:
        return texto

    if EXPANDIR_ENCABEZADOS:
        texto = expandir_encabezados(texto)

    texto = _aplicar_con_contexto(texto)

    if not disponible():
        return texto

    if _PROCESADOR is not None:
        return _PROCESADOR.replace_keywords(str(texto))


    patron, tabla = _RESPALDO

    def _sub(m):
        encontrado = m.group(0)
        termino = tabla.get(encontrado.lower())
        if termino is None:
            return encontrado
        return termino if MODO == "reemplazar" else f"{encontrado} ({termino})"

    return patron.sub(_sub, str(texto))


def encontrados(texto):
    """Que expresiones se reconocieron, sin reemplazarlas. Para auditar."""
    if not texto or _PROCESADOR is None:
        return []
    return _PROCESADOR.extract_keywords(str(texto), span_info=True)


def diagnosticar(texto):
    return {
        "disponible": disponible(),
        "modo": MODO,
        "motor": "flashtext" if _PROCESADOR is not None else "regex",
        "activas": len(_COLOQUIAL),
        "con_contexto": len(_CON_CONTEXTO),
        "desactivadas": len(_DESACTIVADAS),
        "encontrados": encontrados(texto),
        "resultado": normalizar(texto),
    }
