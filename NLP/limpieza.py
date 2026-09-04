"""
Fase 1. Limpieza de formato.

Unico proposito: normalizar la forma del texto. No corrige palabras, no separa,
no interpreta. Lo que entra sale con las mismas palabras: solo cambian
mayusculas, espacios, saltos de linea y simbolos.

DECISIONES QUE NO SON OBVIAS

  Se conserva la puntuacion de frase (. , ; :)
      LanguageTool segmenta por oraciones. Sin puntuacion pierde el contexto
      que necesita para decidir una correccion.

  Se conservan / % ° y los decimales
      '120/80', '39.5', '95%' son datos clinicos. Eliminando la barra,
      '120/80' se volvia '120 80' y la tension arterial dejaba de ser un dato.

  Se conserva la estructura de lineas
      'AP: HTA \\n AA: NIEGA' colapsado en una sola linea pierde la separacion
      entre antecedentes patologicos y alergicos. Para leerlo da igual; para
      extraer entidades despues, no.

  Se preservan las mayusculas del original en un campo aparte
      ortografia.py las necesita: son la unica senal de que 'Pereira' o
      'Hakim' no son errores de digitacion. limpiar() no puede destruirlas
      sin avisar, por eso existe limpiar_conservando_original().
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

# Simbolos que en una nota clinica son contenido y no adorno. Medido sobre las
# 30.000 notas, la version anterior de CONSERVADOS los borraba todos:
#
#   +   suma hallazgos. 'cefalea sin mejoria + dolor en rodilla' son DOS
#       sintomas; sin el signo quedaban fusionados en uno. 349 notas.
#   ?   marca sospecha. 'HVDA ?' es una hipotesis diagnostica, y al perder el
#       signo pasaba a leerse como un diagnostico afirmado. 100 notas.
#   ()  aclara una sigla o un dato: 'DM (insulinorrequiriente)'. 439 notas.
#   <>  comparan una medida: 'sat < 90'. 7 notas.
#
# El asterisco NO esta aca a proposito: en el corpus es vinneta de lista, no
# contenido, y se convierte en separador mas abajo para conservar lo unico que
# aporta, que es la separacion entre items.
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
# 'HTA - DM - Artrosis' son tres antecedentes distintos. Borrarlo dejaba
# 'hta dm artrosis', una sola cadena donde antes habia tres hallazgos, que es
# el mismo dano que borrar el '+'. Se convierte en coma para conservar la
# division.
RE_GUION_SUELTO = re.compile(r"(?<![\w])-+(?![\w])|(?<=\s)-+(?=\s)")

# El asterisco tiene dos usos en el corpus, y solo uno importa.
#
# El mayoritario, medido sobre las 1.017 notas que lo traen, es una marca al
# final de la nota ('TENGO DOLOR EN LA CABEZA*'). No separa nada y se descarta
# sin mas: para eso basta con que no este en CONSERVADOS.
#
# El minoritario es vinneta de lista ('* cefalea  * emesis'), donde el simbolo
# si marca division entre items. Solo en ese caso se convierte en separador,
# que es lo que hace este patron: exige que el asterisco tenga texto a ambos
# lados, con lo que la marca final no coincide.
RE_VINNETA = re.compile(r"(?<=\S)\s+\*+(?=\s*\w)|(?<=^)\*+(?=\s*\w)")

# Parentesis pegados a la palabra: 'dm(ir)' -> 'dm (ir)'. Sin esto el token
# que ve LanguageTool es 'dm(ir)' y no lo reconoce ni como sigla ni como
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
    """Unifica la representacion de acentos y quita caracteres invisibles."""
    texto = unicodedata.normalize("NFC", texto)
    texto = RE_CONTROL.sub(" ", texto)
    texto = RE_INVISIBLES.sub(" ", texto)
    texto = RE_COMILLAS.sub(" ", texto)
    texto = RE_GUIONES.sub("-", texto)
    return texto


def _normalizar_estructura(texto):
    """Un salto de linea por separador logico; encabezados clinicos abren linea."""
    texto = RE_TABS.sub(" ", texto)
    texto = RE_SALTOS.sub("\n", texto)
    texto = RE_ENCABEZADO.sub(lambda m: "\n" + m.group(1) + ":", texto)
    texto = RE_LINEAS_VACIAS.sub("\n", texto)
    return texto


def limpiar(texto):
    """
    'MC: DOLOR!!!\\n\\nAP: HTA' -> 'mc: dolor\\nap: hta'

    Devuelve el texto normalizado en minusculas. Las mismas palabras del
    original, en el mismo orden.
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

    # la vinneta se convierte ANTES de descartar simbolos: RE_SIMBOLOS no la
    # conserva, y hacerlo al reves borraba el asterisco y dejaba a RE_VINNETA
    # sin nada que separar
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
    Devuelve (texto_limpio, texto_original_normalizado).

    El segundo conserva las mayusculas: ortografia.detectar_protegidos() las
    usa para reconocer nombres propios y siglas. Sin el, 'Pereira' termina
    convertido en 'perdida'.
    """
    if texto is None:
        return "", ""

    original = _normalizar_estructura(_normalizar_unicode(str(texto)))
    return limpiar(texto), original.strip()


# ==========================================================
# UTILIDADES
# ==========================================================

def tokenizar(texto):
    """Palabras en minuscula, sin numeros ni puntuacion. Para contar frecuencias."""
    return RE_TOKEN.findall(str(texto).lower())


def normalizar_token(token):
    """Quita puntuacion de los bordes de un token, conservando el interior."""
    return token.strip(PUNTUACION + " /%°-").lower()


def es_vacio(texto):
    """True si la nota no aporta contenido (vacia, guiones, 'n/a', puntuacion)."""
    limpio = limpiar(texto)
    if not limpio:
        return True
    if not RE_TOKEN.search(limpio):
        return True
    return limpio.replace(" ", "") in {"na", "n/a", "no", "nada", "ninguno", "ninguna"}


def analizar(textos):
    """Estadisticas de un lote. Para verificar que la limpieza no rompio nada."""
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
