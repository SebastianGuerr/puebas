"""
Compatibilidad entre versiones de language_tool_python.

La API cambio de nombre entre versiones: 'errorLength'/'ruleId' en las antiguas,
'error_length'/'rule_id' en las nuevas. Acceder al nombre equivocado lanza
AttributeError en cada nota, y como corregir() atrapa la excepcion y devuelve el
texto sin tocar, el pipeline entero queda anulado en silencio.

Este modulo lee el atributo con cualquiera de los dos nombres.
"""


def _leer(match, *nombres):
    for nombre in nombres:
        try:
            valor = getattr(match, nombre)
        except AttributeError:
            continue
        if valor is not None:
            return valor
    return None


def offset(match):
    valor = _leer(match, "offset")
    return int(valor) if valor is not None else 0


def largo(match):
    valor = _leer(match, "error_length", "errorLength")
    if valor is not None:
        return int(valor)
    texto = _leer(match, "matched_text", "matchedText")
    return len(texto) if texto else 0


def regla(match):
    return _leer(match, "rule_id", "ruleId") or ""


def categoria(match):
    valor = _leer(match, "category")
    if valor:
        return valor
    return _leer(match, "rule_issue_type") or ""


def reemplazos(match):
    return _leer(match, "replacements") or []


def span(match):
    """(inicio, fin) del error dentro del texto."""
    inicio = offset(match)
    return inicio, inicio + largo(match)


def verificar(lt):
    """Comprueba que los atributos se leen bien. Devuelve un texto de diagnostico."""
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
