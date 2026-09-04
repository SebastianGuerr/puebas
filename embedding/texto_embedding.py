"""
Construccion del texto que se le manda a bge-m3.

EL PRINCIPIO QUE MANDA ACA
    El valor de este campo es que dos notas que dicen lo mismo de distinta
    forma produzcan el MISMO texto. 'me duele mucho la cabeza' y 'refiere
    cefalea intensa desde ayer' tienen que colapsar a la misma frase
    canonica; si cada una conserva su redaccion original, el modelo tambien
    conserva esa diferencia y los clusters se dispersan por forma de escribir
    en vez de agrupar por cuadro clinico. Por eso la base es SIEMPRE la
    estructura extraida, no el texto crudo.

EL RESPALDO, Y POR QUE NO REEMPLAZA A LA BASE
    Cuando el catalogo no reconoce nada, la frase canonica queda vacia y el
    registro pierde todo su contenido clinico. Para eso -- y solo para eso --
    se agrega el texto real de la nota, limpio de ruido y sin los tramos que
    ya viajan como canonicos. Es un respaldo para el caso sin cobertura, no
    la base del campo: se usa cuando no hay sintomas afirmados, o cuando lo
    unico afirmado es un generico que por si solo no describe el cuadro.

QUE SE LE QUITA AL RESPALDO
    Frases de tramite ('ingresa paciente', 'remitido desde', 'aceptado en
    urgencias'): describen el recorrido por el sistema, no el motivo de
    consulta, y son identicas en miles de notas de categorias distintas.
    Dejarlas es lo que forma clusters de puro tramite.
    Preambulos temporales ('desde el lunes', 'hace 3 dias que'): el tiempo de
    evolucion ya viaja como dato estructurado, y en el texto solo aporta
    variacion de redaccion.
"""

import re

RE_ESPACIOS = re.compile(r"\s+")

RE_ADMIN = re.compile(
    r"\b(?:ingresa(?:n)?\s+(?:paciente|usuario)?|se\s+recibe\s+paciente|"
    r"paciente\s+que\s+ingresa|"
    r"es\s+(?:remitido|remitida|trasladado|trasladada|derivado|derivada)|"
    r"(?:remitido|remitida|trasladado|trasladada|derivado|derivada|aceptado|"
    r"aceptada)(?:\s+(?:desde|de|por|a|en))?|"
    r"se\s+(?:remite|traslada|deriva|acepta)|"
    r"(?:lo|la|le|me|nos)\s+(?:remitieron|remiten|trasladaron|trasladan|"
    r"derivaron|derivan|enviaron|envian|mandaron|mandan|remitio|remite)|"
    r"(?:remitieron|trasladaron|derivaron|enviaron)|"
    r"(?:consulta|acude|asiste)\s+por|"
    r"paciente\s+(?:masculino|femenino)|"
    r"quien\s+(?:consulta|ingresa|refiere)|"
    r"servicio\s+de\s+urgencias|triage\s+de\s+enfermeria)\b",
    re.IGNORECASE)

# encabezados de historia clinica: 'mc (motivo de consulta):', 'ap
# (antecedentes personales):'. Son etiquetas del formulario, identicas en
# miles de notas, y lo unico que aportan al embedding es hacer parecidas dos
# notas que no tienen nada que ver
RE_ENCABEZADO = re.compile(
    r"\b[a-z]{2,4}\s*(?:\([^)]{3,60}\))?\s*:", re.IGNORECASE)

# la expansion entre parentesis de una sigla ya expandida en el texto
RE_PARENTESIS = re.compile(r"\([^)]{5,80}\)")

# frases del bloque institucional que algunas notas traen pegado (politica de
# la EPS, niveles de atencion, disculpas). No describen al paciente y son
# identicas en cientos de notas: si se dejan, el modelo agrupa por ese bloque
MARCADORES_INSTITUCIONALES = (
    "eps", "entidad promotora", "red de atencion", "nivel de atencion",
    "afiliados", "priorizados", "disculpas", "molestias ocasionadas",
    "obligacion de realizar", "cierres de servicios", "urgencias vitales",
    "riesgo inmediato para la vida", "deberan ser orientados",
    "condicion represente", "lamentamos",
)

RE_TEMPORAL = re.compile(
    r"\b(?:desde\s+hace\s+\d{1,3}\s*(?:dias?|horas?|semanas?|meses?)|"
    r"hace\s+\d{1,3}\s*(?:dias?|horas?|semanas?|meses?)(?:\s+que)?|"
    r"desde\s+(?:el|la)\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|"
    r"domingo|manana|ayer|anoche|hoy)\w*|"
    r"desde\s+hace\s+(?:un|una|unos|unas)\s+\w+)\b",
    re.IGNORECASE)

# generico que por si solo no describe el cuadro: si es lo unico que se
# detecto, el respaldo con el texto real aporta mas que la frase canonica
GENERICOS_POBRES = {"dolor inespecifico", "sangrado inespecifico",
                    "malestar general"}

# palabras que por si solas no son contenido clinico: si el residuo se queda
# solo con estas, no hay nada que respaldar
VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "a", "al", "en", "con", "sin", "por", "para", "que", "se", "su",
    "sus", "lo", "le", "es", "esta", "este", "muy", "mas", "tengo", "tiene",
    "presenta", "refiere", "niega", "paciente", "usuario", "mucho", "mucha",
    "poco", "desde", "hace", "dias", "dia", "horas", "hora", "semanas",
    "cuadro", "clinico", "actualmente", "manifiesta", "no", "ni", "pero",
    "cual", "quien", "ademas", "tipo", "propia", "su", "me", "siento",
    "llevo", "vengo", "viene", "tengo", "estoy", "dice", "sufre", "hicieron",
    "mes", "meses", "ano", "anos", "año", "años", "esta", "este", "toda",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "octubre", "noviembre", "diciembre", "madrugada", "manana",
    "tarde", "noche", "anoche", "ayer", "hoy", "principios", "finales",
}

# tope mas estrecho cuando la parte estructurada ya representa el cuadro: si
# ahi el residuo es largo, casi siempre es relleno documental y no sintoma
TOPE_RESIDUO_CON_SINTOMA = 12


def _quitar_tramos(texto, spans):
    """Borra del texto los tramos que ya viajan como sintoma canonico."""
    if not spans:
        return texto
    caracteres = list(texto)
    for _canonico, inicio, fin in spans:
        for i in range(inicio, min(fin, len(caracteres))):
            caracteres[i] = " "
    return "".join(caracteres)


def _tiene_contenido(texto):
    palabras = [p for p in re.findall(r"[\w]+", texto) if p not in VACIAS]
    return any(len(p) >= 4 for p in palabras)


def quitar_institucional(texto):
    """
    Descarta las oraciones que solo hablan de la politica del servicio. Se
    evalua oracion por oracion en vez de por frase suelta: el bloque es
    largo, cambia de redaccion entre notas, y lo que lo identifica no es una
    frase exacta sino que la oracion completa habla del sistema y no del
    paciente.
    """
    oraciones = re.split(r"(?<=[.;])\s+", texto)
    utiles = [o for o in oraciones
              if not any(m in o for m in MARCADORES_INSTITUCIONALES)]
    return " ".join(utiles) if utiles else ""


def limpiar(texto):
    """Texto sin ruido de tramite, encabezados ni preambulo temporal."""
    limpio = quitar_institucional(texto)
    limpio = RE_ENCABEZADO.sub(" ", limpio)
    limpio = RE_PARENTESIS.sub(" ", limpio)
    limpio = RE_ADMIN.sub(" ", limpio)
    limpio = RE_TEMPORAL.sub(" ", limpio)
    limpio = re.sub(r"\s*,\s*(?=,)", "", limpio)
    limpio = RE_ESPACIOS.sub(" ", limpio)
    return limpio.strip(" ,.;:-")


COBERTURA_MINIMA = 0.5   # fraccion de palabras con contenido que el catalogo
                          # debe haber capturado para confiar solo en el canonico
TOPE_RESIDUO = 25        # palabras: evita que una nota larga sin cobertura
                          # inunde el embedding y tape la parte estructurada


def _cobertura(texto_norm, spans):
    """Fraccion de las palabras con contenido que quedaron capturadas."""
    con_contenido = [m for m in re.finditer(r"[\w]+", texto_norm)
                     if m.group() not in VACIAS and len(m.group()) >= 4]
    if not con_contenido:
        return 1.0

    cubierto = bytearray(len(texto_norm))
    for _canonico, inicio, fin in spans:
        for i in range(inicio, min(fin, len(texto_norm))):
            cubierto[i] = 1

    capturadas = sum(1 for m in con_contenido if any(cubierto[m.start():m.end()]))
    return capturadas / len(con_contenido)


def _necesita_respaldo(sintomas, negados, inciertos, texto_norm, spans):
    """
    El respaldo entra en tres situaciones, y las tres son la misma idea: que
    la parte estructurada no alcance a representar la nota.

      1. no hay ningun sintoma afirmado -- un registro cuyo unico contenido es
         'niega fiebre' no dice por que consulto el paciente;
      2. lo unico afirmado es un generico que no describe el cuadro;
      3. el catalogo capturo menos de la mitad de las palabras con contenido,
         asi que lo que quedo afuera pesa mas que lo que entro.

    La tercera es la que evita el error de la version anterior, que descartaba
    el texto completo apenas hubiera UN sintoma: 'esta con flema y no lo deja
    respirar' se quedaba solo en 'expectoracion' y perdia el resto.
    """
    if not sintomas:
        return True
    if set(sintomas).issubset(GENERICOS_POBRES):
        return True
    return _cobertura(texto_norm, spans) < COBERTURA_MINIMA


def construir(categoria, sintomas, negados, inciertos, valores,
              embarazo, pediatrico, texto_norm, spans=()):
    partes = []

    if categoria != "inespecifico":
        partes.append(f"categoria {categoria}")

    if embarazo:
        if valores.get("edad_gestacional"):
            partes.append(f"gestante {valores['edad_gestacional']} semanas")
        else:
            partes.append("gestante")
    if pediatrico:
        partes.append("paciente pediatrico")

    if sintomas:
        partes.append("sintoma " + ", ".join(sintomas))
    if negados:
        partes.append("niega " + ", ".join(negados))
    if inciertos:
        partes.append("posible " + ", ".join(inciertos))

    if valores.get("temperatura"):
        partes.append(f"temperatura {valores['temperatura']}")
    if valores.get("saturacion"):
        partes.append(f"saturacion {valores['saturacion']}")
    if valores.get("dias_evolucion"):
        partes.append(f"evolucion {valores['dias_evolucion']} dias")
    elif valores.get("horas_evolucion"):
        partes.append(f"evolucion {valores['horas_evolucion']} horas")

    # El respaldo lleva solo lo que NO se pudo convertir en canonico: los
    # tramos ya detectados se borran antes de limpiar. Asi 'niega fiebre, tos
    # y disnea' no repite en texto libre lo que ya viaja estructurado, y
    # 'posible neumonia, no hay fiebre' si conserva la neumonia, que es lo
    # unico que el catalogo no supo representar.
    if _necesita_respaldo(sintomas, negados, inciertos, texto_norm, spans):
        if spans:
            # al borrar los tramos ya capturados la gramatica queda rota
            # ('sin signos de dificultad respiratoria' -> 'sin signos de'), asi
            # que se conservan solo las palabras con contenido en vez de una
            # frase mutilada
            residuo = limpiar(_quitar_tramos(texto_norm, spans))
            residuo = " ".join(p for p in re.findall(r"[\w]+", residuo)
                               if p not in VACIAS and len(p) >= 4)
        else:
            # nada se capturo: la nota entera sigue siendo una frase valida y
            # se aprovecha completa, que es justo lo que bge-m3 sabe leer
            residuo = limpiar(texto_norm)
        # las cifras ya viajan en 'valores'; en el residuo solo dejan tokens
        # rotos como '6sms' cuando el patron consumio parte del numero
        palabras_residuo = [p for p in residuo.split()
                            if not any(c.isdigit() for c in p)]
        tope = TOPE_RESIDUO_CON_SINTOMA if sintomas else TOPE_RESIDUO
        if len(palabras_residuo) > tope:
            palabras_residuo = [] if sintomas else palabras_residuo[:tope]
        residuo = " ".join(palabras_residuo)
        if residuo and _tiene_contenido(residuo):
            partes.append(residuo)

    if not partes:
        return "sin informacion clinica."
    return ". ".join(partes) + "."
