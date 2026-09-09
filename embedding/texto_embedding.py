"""
Construcción del texto que se le entrega al modelo de embeddings.

DOS MODOS, Y POR QUÉ MANDA EL EXTRACTIVO
    extractivo  la nota tal como la escribió quien atendió al paciente, sin los
                bloques que sobran. Es el modo activo: conserva el lenguaje, que
                es lo que el modelo sabe leer, y con él la intensidad, la
                evolución y los matices que la estructura no captura.

    canonico    una frase construida a partir de la estructura extraída. Se
                conserva solo para poder comparar los dos enfoques sobre el
                mismo corpus.

    El modo canónico partía de una idea razonable: que dos notas que dicen lo
    mismo de distinta forma produjeran el mismo texto. El problema es que
    canonizar contra un catálogo cerrado hace que miles de notas distintas
    generen una cadena idéntica, y un texto idéntico da un vector idéntico, lo
    que colapsa cualquier agrupamiento posterior.

    La estructura no se pierde por eso: sigue en el registro como categoría,
    síntomas, negados y valores. Son dos cosas distintas —una para filtrar y
    contar, otra para medir parecido— y estaban mezcladas en un solo campo.

EL RESPALDO DEL MODO CANÓNICO
    Cuando el catálogo no reconoce nada, la frase canónica queda vacía y el
    registro pierde todo su contenido clínico. Para ese caso, y solo para ese,
    se añade el texto real de la nota, sin ruido y sin los tramos que ya viajan
    como canónicos.

QUÉ SE LE QUITA AL TEXTO
    El bloque institucional, las frases de trámite que describen el recorrido
    por el sistema, los encabezados del formulario y los preámbulos temporales,
    porque el tiempo de evolución ya viaja como dato estructurado. Todo eso es
    idéntico en miles de notas de cuadros distintos, y dejarlo hace que el
    modelo agrupe por trámite en lugar de por clínica.

    En el modo extractivo el recorte lo hace `recorte.py`; los patrones de este
    módulo se aplican al respaldo del modo canónico.
"""

import re

from NLP.reduccion import reduccion as recorte

# Modo de construccion del texto: "extractivo" o "canonico". Ver la cabecera.
MODO_TEXTO = "extractivo"

# Marca de nota sin contenido clinico. No es una frase: es una etiqueta, para
# que se pueda filtrar en vez de confundirse con un cuadro real.
SIN_CONTENIDO = "sin contenido clinico"

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

# Encabezados del formulario: son etiquetas identicas en miles de notas y lo
# unico que aportan es hacer parecidas dos notas que no tienen nada que ver.
RE_ENCABEZADO = re.compile(
    r"\b[a-z]{2,4}\s*(?:\([^)]{3,60}\))?\s*:", re.IGNORECASE)

# la expansion entre parentesis de una sigla ya expandida en el texto
RE_PARENTESIS = re.compile(r"\([^)]{5,80}\)")

# Frases del bloque institucional que algunas notas traen pegado. No describen
# al paciente y son identicas en cientos de notas: si se dejan, el modelo acaba
# agrupando por ese bloque.
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

# Sintomas demasiado genericos: si son lo unico que se detecto, el respaldo con
# el texto real aporta mas que la frase canonica.
GENERICOS_POBRES = {"dolor inespecifico", "sangrado inespecifico",
                    "malestar general"}

# Palabras que por si solas no son contenido clinico. Si el residuo se queda
# solo con estas, no hay nada que respaldar.
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

# Tope mas estrecho cuando la parte estructurada ya representa el cuadro: si en
# ese caso el residuo es largo, casi siempre es relleno documental y no sintoma.
TOPE_RESIDUO_CON_SINTOMA = 12


def _quitar_tramos(texto, spans):
    """
    Sustituye por espacios los tramos que ya viajan como síntoma canónico, para
    que el respaldo no repita en texto libre lo que ya va estructurado. Se
    reemplaza en lugar de borrar para no descolocar las posiciones restantes.
    """
    if not spans:
        return texto
    caracteres = list(texto)
    for _canonico, inicio, fin in spans:
        for i in range(inicio, min(fin, len(caracteres))):
            caracteres[i] = " "
    return "".join(caracteres)


def _tiene_contenido(texto):
    """True si queda alguna palabra con significado y de longitud suficiente."""
    palabras = [p for p in re.findall(r"[\w]+", texto) if p not in VACIAS]
    return any(len(p) >= 4 for p in palabras)


def quitar_institucional(texto):
    """
    Descarta las oraciones que solo hablan de la política del servicio.

    Se evalúa oración por oración y no frase suelta: el bloque es largo, cambia
    de redacción entre notas, y lo que lo identifica no es una frase exacta sino
    que la oración completa hable del sistema y no del paciente.
    """
    oraciones = re.split(r"(?<=[.;])\s+", texto)
    utiles = [o for o in oraciones
              if not any(m in o for m in MARCADORES_INSTITUCIONALES)]
    return " ".join(utiles) if utiles else ""


def limpiar(texto):
    """
    Devuelve el texto sin bloque institucional, encabezados, anotaciones entre
    paréntesis, frases de trámite ni preámbulos temporales, y con los espacios
    y la puntuación sobrante ya normalizados.
    """
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
    """
    Fracción de las palabras con contenido de la nota que quedaron capturadas
    por el catálogo. Devuelve 1.0 cuando la nota no tiene palabras con
    contenido, para que una nota vacía no se considere mal cubierta.
    """
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
    True si la parte estructurada no alcanza a representar la nota y hace falta
    añadir texto real.

    Ocurre en tres situaciones, que son la misma idea vista de tres formas:

      1. no hay ningún síntoma afirmado, de modo que el registro no dice por qué
         consultó el paciente;
      2. lo único afirmado es un genérico que no describe el cuadro;
      3. el catálogo capturó menos de la mitad de las palabras con contenido, así
         que lo que quedó fuera pesa más que lo que entró.

    La tercera condición es la que evita descartar el texto completo por haber
    reconocido un solo síntoma, perdiendo todo lo demás que decía la nota.
    """
    if not sintomas:
        return True
    if set(sintomas).issubset(GENERICOS_POBRES):
        return True
    return _cobertura(texto_norm, spans) < COBERTURA_MINIMA


def construir(categoria, sintomas, negados, inciertos, valores,
              embarazo, pediatrico, texto_norm, spans=(), texto=None):
    """
    Devuelve el texto que se le entregará al modelo de embeddings, según el
    modo configurado (ver la cabecera del módulo).

    En modo extractivo recorta la nota y la devuelve; si el recorte se lleva
    todo, devuelve la marca SIN_CONTENIDO en lugar de caer a la frase canónica.
    Esa decisión es deliberada: una nota sin contenido tiene que quedar marcada
    como tal y poder filtrarse, no disfrazada de un cuadro clínico que en
    realidad comparte con cientos de notas ajenas.

    En modo canónico construye la frase a partir de la estructura y le añade el
    texto de respaldo cuando hace falta.
    """
    if MODO_TEXTO == "extractivo":
        # se recorta sobre el texto CON tildes: la version plegada existe para
        # cruzar posiciones con el catalogo, no para entregarsela al modelo
        recortado = recorte.recortar(texto if texto is not None else texto_norm)
        if recortado:
            return recortado
        # el recorte se llevo todo: la nota queda marcada como sin contenido,
        # para que se pueda filtrar (ver el docstring)
        return SIN_CONTENIDO

    return _canonico(categoria, sintomas, negados, inciertos, valores,
                     embarazo, pediatrico, texto_norm, spans)


def _canonico(categoria, sintomas, negados, inciertos, valores,
              embarazo, pediatrico, texto_norm, spans=()):
    """
    Construye la frase canónica a partir de la estructura extraída, en un orden
    fijo: categoría, condición del paciente, síntomas afirmados, negados e
    inciertos, y valores medidos. Añade el texto de respaldo cuando la
    estructura no basta, y devuelve una marca genérica si no hay nada que decir.
    """
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
    # tramos ya detectados se borran antes de limpiar, de modo que no se repite
    # en texto libre lo que ya viaja estructurado.
    if _necesita_respaldo(sintomas, negados, inciertos, texto_norm, spans):
        if spans:
            # al borrar los tramos capturados la gramatica queda rota, asi que
            # se conservan las palabras con contenido y no una frase mutilada
            residuo = limpiar(_quitar_tramos(texto_norm, spans))
            residuo = " ".join(p for p in re.findall(r"[\w]+", residuo)
                               if p not in VACIAS and len(p) >= 4)
        else:
            # nada se capturo: la nota entera sigue siendo una frase valida y se
            # aprovecha completa, que es lo que el modelo sabe leer
            residuo = limpiar(texto_norm)
        # las cifras ya viajan como valores; en el residuo solo dejan tokens
        # rotos cuando un patron consumio parte del numero
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
