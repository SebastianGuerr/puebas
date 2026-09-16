"""
Fase 1. Limpieza de formato.

Normaliza la forma del texto y nada más: no corrige palabras, no separa
términos y no interpreta contenido. Lo que entra sale con las mismas palabras y
en el mismo orden; solo cambian mayúsculas, espacios, saltos de línea y
símbolos.

Interfaz del módulo:

    limpiar(texto)                      texto normalizado en minúsculas
    limpiar_conservando_original(texto) además, el original con sus mayúsculas
    tokenizar                           utilidad de token
    es_vacio, analizar                  control de calidad del lote

CRITERIOS QUE NO SON EVIDENTES

  Se conserva la puntuación de frase (. , ; :)
      LanguageTool segmenta por oraciones; sin puntuación pierde el contexto
      que necesita para decidir una corrección.

  Se conservan la barra, el porcentaje, el grado y los decimales
      '120/80', '39.5' y '95%' son datos clínicos. Al eliminar la barra,
      '120/80' pasa a '120 80' y la tensión arterial deja de ser un dato.

  Se conserva la separación entre apartados
      'AP: HTA' y 'AA: NIEGA' fundidos en una sola línea pierden la frontera
      entre antecedentes patológicos y alérgicos, que las fases siguientes
      necesitan para acotar el alcance de la negación.

  Se devuelve aparte el original con sus mayúsculas
      Son la única señal de que un término es un nombre propio y no un error de
      digitación. Como limpiar() las destruye, quien las necesite debe usar
      limpiar_conservando_original().
"""

import re
import unicodedata

# ==========================================================
# CONFIGURACION
# ==========================================================

# El salto de linea separa ideas pero es invasivo: rompe la segmentacion por
# oraciones de LanguageTool, obliga a comillas en el CSV y no aporta nada que un
# signo de puntuacion no aporte. Se sustituye por punto y coma, que marca la
# separacion sin partir el texto: el punto y coma une oraciones relacionadas,
# que es exactamente lo que son los apartados de una nota clinica.
PRESERVAR_ESTRUCTURA = True
SEPARADOR_LINEA = "; "
MAX_REPETICIONES = 2          # holaaaaa -> holaa
LARGO_MAXIMO = 20000          # corta notas absurdamente largas

PUNTUACION = ".,;:"

# Simbolos que en una nota clinica son contenido y no adorno:
#
#   +   suma hallazgos. 'cefalea sin mejoria + dolor en rodilla' son DOS
#       sintomas; sin el signo quedan fusionados en uno.
#   ?   marca sospecha. 'hvda ?' es una hipotesis diagnostica, y al perder el
#       signo pasa a leerse como un diagnostico afirmado.
#   ()  aclara una sigla o un dato: 'dm (insulinorrequiriente)'.
#   <>  comparan una medida: 'sat < 90'.
#
# El asterisco queda fuera a proposito: en el corpus es vinneta de lista, no
# contenido, y se convierte en separador mas abajo para conservar lo unico que
# aporta, que es la division entre items.
SIMBOLOS_CLINICOS = r"+?()<>"
CONSERVADOS = r"\w\s.,;:/%°\-+?()<>áéíóúüñÁÉÍÓÚÜÑ"

RE_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
RE_INVISIBLES = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff\u00a0\u2028\u2029]")
RE_COMILLAS = re.compile(r"[\u2018\u2019\u201a\u201b\u201c\u201d\u201e\u201f\u00ab\u00bb]")
RE_GUIONES = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015]")
RE_SALTOS = re.compile(r"[\r\n]+")
RE_TABS = re.compile(r"[\t\v\f]+")
RE_SIMBOLOS = re.compile(r"[^%s]" % CONSERVADOS)
RE_REPETIDOS = re.compile(r"(.)\1{%d,}" % MAX_REPETICIONES)
RE_ESPACIO_PUNT = re.compile(r"[ ]*(?<!\d)([.,;:])[ ]*|[ ]*([.,;:])[ ]*(?!\d)")
RE_PUNT_REPETIDA = re.compile(r"([.,;:])[.,;: ]*\1+")
# El guion suelto de las listas clinicas separa items, no une palabras:
# 'hta - dm - artrosis' son tres antecedentes distintos, y borrarlo los funde en
# una sola cadena. Se convierte en coma para conservar la division.
RE_GUION_SUELTO = re.compile(r"(?<![\w])-+(?![\w])|(?<=\s)-+(?=\s)")

# El asterisco tiene dos usos en el corpus y solo uno importa. El mayoritario es
# una marca al final de la nota, que no separa nada y se descarta por no figurar
# en CONSERVADOS. El minoritario es vinneta de lista ('* cefalea  * emesis'),
# donde si marca division entre items: este patron exige texto a ambos lados,
# con lo que reconoce la vinneta y no la marca final.
RE_VINNETA = re.compile(r"(?<=\S)\s+\*+(?=\s*\w)|(?<=^)\*+(?=\s*\w)")

# Parentesis pegados a la palabra: 'dm(ir)' -> 'dm (ir)'. Sin separarlos, el
# token que ve LanguageTool es 'dm(ir)' y no lo reconoce ni como sigla ni como
# palabra.
RE_PARENTESIS_PEGADO = re.compile(r"(?<=[\w])\(|\)(?=[\w])")

# Un signo de interrogacion suelto pierde su referente al normalizar espacios.
# Se pega a la palabra anterior para que viaje con ella: 'hvda ?' -> 'hvda?'
RE_INTERROGACION_SUELTA = re.compile(r"(?<=[\w])\s+\?")
RE_ESPACIOS = re.compile(r"[ ]{2,}")
RE_LINEAS_VACIAS = re.compile(r"\n[ ]*\n+")
RE_TOKEN = re.compile(r"[a-záéíóúüñ]+")

# encabezados de nota clinica: siempre deben abrir linea
ENCABEZADOS = ["mc", "ea", "ap", "aa", "af", "ax", "ef", "sv", "rs", "dx", "px",
               "hc", "ap patologicos", "antecedentes", "motivo de consulta",
               "enfermedad actual", "revision por sistemas", "examen fisico",
               "analisis", "plan", "impresion diagnostica"]
RE_ENCABEZADO = re.compile(
    r"(?<!^)(?<![\n])\s*\b(%s)\s*:" % "|".join(sorted(ENCABEZADOS, key=len, reverse=True)),
    re.IGNORECASE,
)


# ==========================================================
# LIMPIEZA
# ==========================================================

def _normalizar_unicode(texto):
    """
    Unifica la representación de los acentos y sustituye los caracteres que no
    se ven: controles, espacios de ancho cero, comillas tipográficas y guiones
    largos.
    """
    texto = unicodedata.normalize("NFC", texto)
    texto = RE_CONTROL.sub(" ", texto)
    texto = RE_INVISIBLES.sub(" ", texto)
    texto = RE_COMILLAS.sub(" ", texto)
    texto = RE_GUIONES.sub("-", texto)
    return texto


def _normalizar_estructura(texto):
    """
    Deja un solo salto de línea por separación lógica y fuerza que cada
    encabezado de historia clínica abra línea, esté donde esté en el original.
    """
    texto = RE_TABS.sub(" ", texto)
    texto = RE_SALTOS.sub("\n", texto)
    texto = RE_ENCABEZADO.sub(lambda m: "\n" + m.group(1) + ":", texto)
    texto = RE_LINEAS_VACIAS.sub("\n", texto)
    return texto


def limpiar(texto):
    """
    Devuelve el texto normalizado en minúsculas, con las mismas palabras del
    original y en el mismo orden.

        'MC: DOLOR!!!\\n\\nAP: HTA'  ->  'mc: dolor; ap: hta'

    Acepta None y valores vacíos, para los que devuelve cadena vacía. Las notas
    que superan LARGO_MAXIMO se truncan.
    """
    if texto is None:
        return ""

    texto = str(texto)
    if not texto.strip():
        return ""

    if len(texto) > LARGO_MAXIMO:
        texto = texto[:LARGO_MAXIMO]

    texto = _normalizar_unicode(texto)
    texto = _normalizar_estructura(texto)
    texto = texto.lower()

    # la vinneta se convierte ANTES de descartar simbolos: el asterisco no esta
    # en CONSERVADOS, asi que al reves se borraria antes de poder separar nada
    texto = RE_VINNETA.sub("; ", texto)
    texto = RE_SIMBOLOS.sub(" ", texto)
    texto = RE_REPETIDOS.sub(lambda m: m.group(1) * MAX_REPETICIONES, texto)
    texto = RE_GUION_SUELTO.sub(", ", texto)
    texto = RE_PARENTESIS_PEGADO.sub(lambda m: " (" if m.group(0) == "(" else ") ", texto)
    texto = RE_INTERROGACION_SUELTA.sub("?", texto)
    texto = RE_ESPACIO_PUNT.sub(lambda m: (m.group(1) or m.group(2)) + " ", texto)
    texto = RE_PUNT_REPETIDA.sub(r"\1", texto)
    texto = RE_ESPACIOS.sub(" ", texto)

    lineas = [l.strip(" " + PUNTUACION) for l in texto.split("\n")]
    lineas = [l for l in (RE_ESPACIOS.sub(" ", l) for l in lineas) if l]

    if not PRESERVAR_ESTRUCTURA:
        return " ".join(lineas).strip()

    unido = SEPARADOR_LINEA.join(lineas).strip()
    # el separador no debe duplicar un signo que ya cerraba la linea
    unido = re.sub(r"[.,;:]\s*;\s*", "; ", unido)
    return RE_ESPACIOS.sub(" ", unido).strip(" ;")


def limpiar_conservando_original(texto):
    """
    Devuelve el par (texto_limpio, texto_original_normalizado).

    El segundo mantiene las mayúsculas del original y solo se le aplican las
    normalizaciones de Unicode y estructura. Es lo que permite reconocer
    nombres propios y siglas más adelante.
    """
    if texto is None:
        return "", ""

    original = _normalizar_estructura(_normalizar_unicode(str(texto)))
    return limpiar(texto), original.strip()


# ==========================================================
# UTILIDADES
# ==========================================================

def tokenizar(texto):
    """Palabras en minúscula, sin números ni puntuación. Para contar frecuencias."""
    return RE_TOKEN.findall(str(texto).lower())


def es_vacio(texto):
    """
    True si la nota no aporta contenido: está vacía, solo trae puntuación o se
    reduce a una negación administrativa del tipo 'n/a' o 'ninguno'.
    """
    limpio = limpiar(texto)
    if not limpio:
        return True
    if not RE_TOKEN.search(limpio):
        return True
    return limpio.replace(" ", "") in {"na", "n/a", "no", "nada", "ninguno", "ninguna"}


def analizar(textos):
    """
    Estadísticas de un lote ya limpio: registros, notas vacías, notas con
    estructura multilínea y densidad de palabras. Sirve para comprobar que la
    limpieza no destruyó contenido antes de seguir con las fases siguientes.
    """
    total = len(textos)
    vacios = sum(1 for t in textos if es_vacio(t))
    limpios = [limpiar(t) for t in textos]
    con_lineas = sum(1 for l in limpios if "\n" in l)
    palabras = sum(len(tokenizar(l)) for l in limpios)

    return {
        "registros": total,
        "vacios": vacios,
        "con_estructura_multilinea": con_lineas,
        "palabras_totales": palabras,
        "palabras_por_nota": round(palabras / max(total - vacios, 1), 1),
    }
