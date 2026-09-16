"""
Fase 3. Normalización clínica: coloquialismos y siglas.

Traduce la forma en que habla el paciente a la forma en que se escribe en una
historia clínica, sin cambiar lo que dice:

    daño de estomago  -> dispepsia          pita el oido  -> tinnitus
    culebrilla        -> herpes zoster      hta           -> hipertension arterial

POR QUÉ ES UNA FASE APARTE
    Mezclar normalización y corrección ortográfica arruina la auditoría: en el
    informe de cambios dejarían de distinguirse un error de digitación y una
    expansión intencionada. Se aplica sobre la columna ya corregida y se
    conservan ambas.

QUÉ SE ANOTA Y QUÉ SE REEMPLAZA
    El modo por defecto es anotar: 'me pita el oido' pasa a 'me pita el oido
    (tinnitus)'. El reemplazo literal rompe la sintaxis en las expresiones
    verbales, y una nota agramatical le cuesta más a un modelo que la expresión
    popular original. Anotando se conserva la frase del paciente y se añade el
    término clínico, de modo que el texto sirve tanto para leerlo como para
    buscar el término estandarizado.

QUÉ ENTRADAS SE APLICAN
    No todas. Cada entrada del diccionario pasa por el control de ambigüedad,
    que decide si puede aplicarse siempre, solo cuando su contexto aparece
    cerca, o si queda inactiva. No hay listas negras: lo que no se puede
    demostrar inequívoco no se aplica y se reporta en desactivadas(), que es la
    lista de decisiones pendientes de revisar.

ORDEN INTERNO
    1. Encabezados de apartado, que son siglas sin ambigüedad posible.
    2. Entradas condicionadas al contexto.
    3. Expresiones de varias palabras y siglas, prefiriendo siempre la
       coincidencia más larga.

MOTOR
    Con flashtext se construye un único autómata que recorre el texto una sola
    vez, de modo que el coste no crece con el tamaño del diccionario, y respeta
    los límites de palabra. Si no está instalado se recurre a una
    implementación con expresiones regulares, más lenta pero equivalente.
"""

import json
import re
from pathlib import Path

from NLP import rutas
from NLP.nucleo import reglas
from NLP.recursos import ambiguedad

RUTA_COLOQUIAL = rutas.DICCIONARIO_COLOQUIAL

# "anotar":     me pita el oido -> me pita el oido (tinnitus)
# "reemplazar": me pita el oido -> me tinnitus
# Ver el criterio en la cabecera del modulo.
MODO = "anotar"

EXPANDIR_SIGLAS = True
NORMALIZAR_COLOQUIALISMOS = True
EXPANDIR_ENCABEZADOS = True   # 'aa:' -> 'aa (antecedentes alergicos):'

# Bandera de E5.1 (docs/decisiones/2026-09-16-E5.1-glosas.md). Por defecto no
# cambia nada: normalizar() sigue anotando inline. Con SEPARAR_CONCEPTO=True,
# normalizar_separado() devuelve el texto SIN la anotacion y el concepto en un
# valor aparte, para que fase 5 y clustering/etiquetas.py puedan usar una
# columna de concepto en vez de un parentesis dentro del texto de embedding.
SEPARAR_CONCEPTO = False

# Longitud minima de una sigla para expandirla. Las de dos letras coinciden
# con palabras corrientes del espanol y con fragmentos de nombres propios, de
# modo que expandirlas parte palabras y anota significados equivocados.
LONGITUD_MINIMA_SIGLA = 3

# Estado del diccionario tras evaluar la ambiguedad de cada entrada. Las
# declaraciones de que siglas son seguras y cuales ambiguas viven en los
# archivos de datos, no aqui: perseguir casos con listas negras en el codigo no
# escalaba.
_DECLARADAS_SEGURAS = set()
_DECLARADAS_AMBIGUAS = set()
_CON_CONTEXTO = {}        # clave -> (significado, palabras de contexto)
_DESACTIVADAS = []        # (clave, motivo) para el informe

_COLOQUIAL = {}
_PROCESADOR = None
_RESPALDO = None


def _sin_tildes(texto):
    """Atajo al plegado de acentos del paquete, que conserva la eñe."""
    return reglas.sin_tildes(texto)


# ==========================================================
# CARGA DEL DICCIONARIO
# ==========================================================

def cargar(ruta=RUTA_COLOQUIAL, lt=None):
    """
    Lee los dos diccionarios, decide entrada por entrada si puede aplicarse y
    construye el motor de búsqueda. Devuelve cuántas entradas quedaron activas
    sin condiciones.

    `lt` es una instancia de LanguageTool ya creada, que el control de
    ambigüedad usa para saber si una clave coincide con una palabra corriente
    del español. Sin ella la comprobación se apoya solo en el vocabulario de
    spaCy.

    Las entradas condicionadas quedan en con_contexto() y las descartadas en
    desactivadas(), con su motivo.
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

    # las declaraciones de seguridad y ambiguedad viven en los diccionarios; las
    # de siglas las cargo antes el modulo de reglas
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
    """
    Entradas que no se aplican, con su motivo, ordenadas. Es la lista de
    decisiones pendientes: cada una hay que revisarla y, si procede, declararla
    con su contexto en el diccionario.
    """
    return sorted(_DESACTIVADAS)


def con_contexto():
    """Entradas activas solo cuando alguna de sus palabras de contexto aparece cerca."""
    return {k: v[1] for k, v in _CON_CONTEXTO.items()}


def _construir_flashtext(tabla):
    """
    Construye el autómata de búsqueda a partir de la tabla de entradas activas.
    Devuelve None si flashtext no está instalado, para que se use el respaldo.
    """
    try:
        from flashtext import KeywordProcessor
    except ModuleNotFoundError:
        print("Aviso: flashtext no instalado; se usara la version con regex.")
        return None

    kp = KeywordProcessor(case_sensitive=False)
    # flashtext define los limites de palabra solo con ASCII, de modo que una
    # vocal acentuada o la eñe cuentan como separador y una sigla corta coincide
    # dentro de una palabra acentuada. Sin esta linea la expansion parte palabras.
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
    """
    Motor de respaldo: una expresión regular con todas las claves, ordenadas de
    más larga a más corta para que gane la coincidencia más específica.
    Devuelve el par (patrón, tabla), o None si no hay entradas.
    """
    if not tabla:
        return None
    claves = sorted(tabla, key=len, reverse=True)
    patron = re.compile(r"\b(%s)\b" % "|".join(re.escape(k) for k in claves),
                        re.IGNORECASE)
    return (patron, tabla)


def disponible():
    """True si hay un motor de búsqueda construido, sea el autómata o el respaldo."""
    return _PROCESADOR is not None or _RESPALDO is not None


# ==========================================================
# NORMALIZACIÓN
# ==========================================================

# un encabezado se reconoce porque va seguido de dos puntos
RE_ENCABEZADO = re.compile(r"\b([a-záéíóúüñ]{2,6})\s*:")


def expandir_encabezados(texto):
    """
    Anota el significado de las siglas que encabezan un apartado:
    'aa: niega' pasa a 'aa (antecedentes alergicos): niega'.

    Conserva la sigla original, que es la forma en que el personal escribe y
    busca, y añade el significado para que el texto se entienda por sí solo.

    Solo actúa sobre las siglas seguidas de dos puntos, porque ahí la sigla es
    un rótulo de apartado y no hay ambigüedad posible. Se saltan los
    significados genéricos, que no aportarían nada al lector.
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
    Aplica las entradas condicionadas, comprobando ocurrencia por ocurrencia que
    alguna de sus palabras de contexto aparezca cerca. Así 'le salio un nacido
    en la pierna' se normaliza y 'recien nacido de 6 dias' no.
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
    """
    Aplica sobre un texto ya corregido, y en este orden, la expansión de
    encabezados, las entradas condicionadas al contexto y el resto del
    diccionario. Devuelve el texto normalizado.
    """
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


# Anotacion inline que deja normalizar() en modo 'anotar': 'hta (hipertension
# arterial)'. Se reutiliza para separarla, no para detectarla en el original.
RE_GLOSA_INLINE = re.compile(r"\s*\(([^)]{3,80})\)")


def normalizar_separado(texto):
    """
    Como normalizar(), pero con la anotacion aparte del texto en vez de
    inline. Devuelve (texto_sin_glosa, concepto_normalizado).

    Si SEPARAR_CONCEPTO es False (por defecto) no separa nada y devuelve
    (normalizar(texto), ""), para no cambiar el comportamiento por defecto.
    Ver decisiones/2026-09-16-E5.1-glosas.md y PLAN.md §7 (clustering/etiquetas.py
    necesita esta segunda fuente si se le deja de dar el parentesis).
    """
    anotado = normalizar(texto)
    if not SEPARAR_CONCEPTO or not anotado:
        return anotado, ""
    conceptos = [c.strip() for c in RE_GLOSA_INLINE.findall(anotado)]
    sin_glosa = re.sub(r"\s+", " ", RE_GLOSA_INLINE.sub("", anotado)).strip()
    concepto_normalizado = " ".join(dict.fromkeys(conceptos))
    return sin_glosa, concepto_normalizado


def encontrados(texto):
    """
    Expresiones reconocidas en el texto, con su posición y sin sustituirlas.
    Solo disponible con el motor de flashtext.
    """
    if not texto or _PROCESADOR is None:
        return []
    return _PROCESADOR.extract_keywords(str(texto), span_info=True)


def diagnosticar(texto):
    """
    Estado del módulo y resultado sobre un texto concreto: motor en uso,
    entradas activas, condicionadas y descartadas, expresiones reconocidas y
    texto normalizado. Herramienta de inspección manual.
    """
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
