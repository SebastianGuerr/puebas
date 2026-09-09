"""
Lectura de los resultados de LanguageTool con independencia de la versión.

La librería language_tool_python renombró los atributos de sus objetos `Match`
entre versiones: 'errorLength' y 'ruleId' en las antiguas, 'error_length' y
'rule_id' en las nuevas. Leer el nombre equivocado lanza AttributeError en cada
nota y, como el corrector captura la excepción y devuelve el texto sin tocar, la
fase ortográfica quedaría anulada sin ningún mensaje de error.

Este módulo concentra ese acceso: cada función devuelve un dato del `Match`
probando los nombres de ambas versiones, de modo que el resto del paquete nunca
accede a un atributo directamente.

    offset, largo, span   dónde empieza y termina el error en el texto
    regla, categoria      qué regla lo produjo y de qué tipo es
    reemplazos            las sugerencias de corrección
    verificar             diagnóstico de que la lectura funciona
"""


def _leer(match, *nombres):
    """Primer atributo no nulo del match entre los nombres dados, o None."""
    for nombre in nombres:
        try:
            valor = getattr(match, nombre)
        except AttributeError:
            continue
        if valor is not None:
            return valor
    return None


def offset(match):
    """Posición del carácter donde empieza el error. 0 si no se puede leer."""
    valor = _leer(match, "offset")
    return int(valor) if valor is not None else 0


def largo(match):
    """
    Longitud en caracteres del fragmento señalado. Si la versión no expone la
    longitud, se deduce del texto coincidente.
    """
    valor = _leer(match, "error_length", "errorLength")
    if valor is not None:
        return int(valor)
    texto = _leer(match, "matched_text", "matchedText")
    return len(texto) if texto else 0


def regla(match):
    """Identificador de la regla de LanguageTool que disparó el aviso."""
    return _leer(match, "rule_id", "ruleId") or ""


def categoria(match):
    """Categoría del aviso; si falta, el tipo de incidencia de la regla."""
    valor = _leer(match, "category")
    if valor:
        return valor
    return _leer(match, "rule_issue_type") or ""


def reemplazos(match):
    """Lista de sugerencias propuestas por LanguageTool, posiblemente vacía."""
    return _leer(match, "replacements") or []


def span(match):
    """Par (inicio, fin) del error dentro del texto analizado."""
    inicio = offset(match)
    return inicio, inicio + largo(match)


def verificar(lt):
    """
    Comprueba contra una frase de prueba que los atributos se leen bien en la
    versión instalada. Devuelve un texto de diagnóstico legible, nunca lanza.
    """
    try:
        matches = lt.check("tengo dolro de cabeza")
    except Exception as exc:
        return f"LanguageTool no responde: {exc}"

    if not matches:
        return "LanguageTool responde pero no detecto el error de prueba"

    m = matches[0]
    inicio, fin = span(m)
    if fin <= inicio:
        return "no se pudo leer la longitud del error en esta version"
    return f"ok (regla {regla(m)}, categoria {categoria(m)})"
