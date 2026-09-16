"""
Recuperacion de la capitalizacion (sigla, nombre propio, comun), aprendida
contando el contraste de mayusculas/minusculas en el propio corpus en vez de
mantener un diccionario a mano. Responsabilidad completa y ejemplo (`ir` como
sigla vs. verbo) en docs/ARQUITECTURA.md, ficha `recursos/casing.py` (S2.8).
"""

import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from NLP import rutas

RUTA_LEXICO = rutas.LEXICO_CASING

# Una nota con mas mayusculas que esto no aporta evidencia: esta gritada y
# todos sus tokens irian a MAYUS. Es el mismo umbral de reglas.texto_gritado.
PROPORCION_MAYUSCULAS = 0.9

# Cuantas veces hay que haber visto un token para creerle. Con menos de esto la
# clasificacion es ruido: un solo 'Dolor' al abrir un renglon no convierte a
# dolor en nombre propio.
MINIMO_OBSERVACIONES = 3

# Que fraccion de las apariciones debe tener la forma ganadora. Por debajo, el
# token se usa de las dos maneras y no hay una respuesta correcta global: es
# justo el caso de 'ir', que se resuelve por mayoria y no por lista negra.
DOMINANCIA = 0.6

LONGITUD_MINIMA = 2
LONGITUD_MAXIMA_SIGLA = 8

SIGLA = "sigla"
NOMBRE = "nombre"
COMUN = "comun"

RE_TOKEN = re.compile(r"[^\W\d_]+", re.UNICODE)
RE_ORACION = re.compile(r"(?<=[.;:!?\n])\s+")

# un token seguido de dos puntos es la etiqueta de un campo de la plantilla
# ('Ocupacion:', 'Alergicos:'), no un nombre propio
RE_ETIQUETA = re.compile(r"[ ]*:")

# Fin de oracion de verdad: el signo tiene que ir seguido de espacio o de nada.
# Sin esa condicion, el punto de '19.6SMS' contaba como fin de oracion y la
# palabra siguiente se capitalizaba, produciendo '19.6Sms'.
RE_FIN_ORACION = re.compile(r"[.;:!?](?=\s|$)|\n")

_LEXICO = {}          # token en minuscula -> SIGLA | NOMBRE | COMUN
_OBSERVACIONES = {}   # token -> {"MAYUS": n, "Inicial": n, "minus": n}


# delegada a morfologia.py: la eñe es una letra, no un acento
from NLP.nucleo.morfologia import sin_tildes  # noqa: E402


def texto_gritado(texto):
    """
    True si la nota está escrita casi toda en mayúsculas y, por tanto, no aporta
    evidencia sobre cómo se capitaliza cada palabra.
    """
    letras = [c for c in str(texto) if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


# ==========================================================
# CONSTRUCCIÓN DEL LÉXICO
# ==========================================================

def _contar(textos):
    """
    Cuenta como se escribe cada palabra en las notas con contraste de
    capitalizacion. Devuelve, por token en minuscula, un contador con las
    apariciones en mayusculas, con inicial y en minusculas.
    """
    # Solo cuenta la mayuscula que no se explica por la posicion: abrir
    # oracion y etiquetar un campo de plantilla ('Ocupacion:') no dicen nada
    # del token en si, a diferencia de ser un nombre propio. De ahi las dos
    # exclusiones de mas abajo (primer token del fragmento, y token con ':').
    formas = defaultdict(Counter)

    for texto in textos:
        texto = str(texto)
        if texto_gritado(texto):
            continue
        for fragmento in RE_ORACION.split(texto):
            for posicion, m in enumerate(RE_TOKEN.finditer(fragmento)):
                palabra = m.group(0)
                if posicion == 0 or len(palabra) < LONGITUD_MINIMA:
                    continue
                if RE_ETIQUETA.match(fragmento, m.end()):
                    continue
                if palabra.isupper():
                    formas[palabra.lower()]["MAYUS"] += 1
                elif palabra[0].isupper():
                    formas[palabra.lower()]["Inicial"] += 1
                else:
                    formas[palabra.lower()]["minus"] += 1

    return formas


def _clasificar(conteo):
    """
    Clasifica un token por su contador de formas: SIGLA, NOMBRE o COMUN, o
    None si se vio pocas veces o ninguna forma alcanza la dominancia exigida.
    """
    total = sum(conteo.values())
    if total < MINIMO_OBSERVACIONES:
        return None

    mayus = conteo.get("MAYUS", 0) / total
    inicial = conteo.get("Inicial", 0) / total

    if mayus >= DOMINANCIA:
        return SIGLA
    if inicial >= DOMINANCIA:
        return NOMBRE
    if mayus + inicial < 1 - DOMINANCIA:
        return COMUN
    # se usa de varias formas sin que ninguna domine: no hay respuesta global
    return None


def construir(textos):
    """
    Construye el léxico y devuelve cuántas entradas quedaron. `textos` es un
    iterable de notas SIN limpiar: las mayúsculas del original son la materia
    prima de este módulo.
    """
    _LEXICO.clear()
    _OBSERVACIONES.clear()

    formas = _contar(textos)
    for token, conteo in formas.items():
        clase = _clasificar(conteo)
        if clase is None:
            continue
        if clase == SIGLA and len(token) > LONGITUD_MAXIMA_SIGLA:
            # una palabra larga escrita en mayusculas suele ser enfasis
            # ('DOLOR INTENSO'), no una sigla
            continue
        _LEXICO[token] = clase
        _OBSERVACIONES[token] = dict(conteo)

    return len(_LEXICO)


def disponible():
    """True si hay un léxico de capitalización cargado en memoria."""
    return bool(_LEXICO)


def guardar(ruta=RUTA_LEXICO):
    """
    Escribe el léxico en disco junto con los parámetros con los que se construyó
    y el recuento de formas de cada token, que es lo que permite revisar después
    por qué un token quedó clasificado como quedó.
    """
    datos = {
        "_descripcion": (
            "Capitalizacion aprendida de las notas del hospital escritas con "
            "mayusculas y minusculas. Generado por casing.construir(); no se "
            "edita a mano. Para regenerarlo: python -m NLP.recursos.casing"),
        "_parametros": {
            "minimo_observaciones": MINIMO_OBSERVACIONES,
            "dominancia": DOMINANCIA,
            "proporcion_mayusculas": PROPORCION_MAYUSCULAS,
        },
        "lexico": _LEXICO,
        "observaciones": _OBSERVACIONES,
    }
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return len(_LEXICO)


def cargar(ruta=RUTA_LEXICO):
    """
    Lee el léxico ya construido y devuelve cuántas entradas trae, o 0 si el
    archivo todavía no existe.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return 0
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    _LEXICO.clear()
    _LEXICO.update(datos.get("lexico", {}))
    _OBSERVACIONES.clear()
    _OBSERVACIONES.update(datos.get("observaciones", {}))
    return len(_LEXICO)


# ==========================================================
# CONSULTA DEL LÉXICO
# ==========================================================

def clase(token):
    """SIGLA, NOMBRE, COMUN, o None si el corpus no tiene evidencia del token."""
    return _LEXICO.get(str(token).lower())


def es_sigla(token):
    """True si el corpus escribe el token habitualmente en mayúsculas."""
    return clase(token) == SIGLA


def siglas(dominancia=None):
    """
    Conjunto de siglas aprendidas del corpus (complementa al diccionario
    escrito a mano). Con `dominancia`, exige ademas superar esa fraccion de
    apariciones en mayuscula (para reescribir, no solo para proteger).
    """
    if dominancia is None:
        return {t for t, c in _LEXICO.items() if c == SIGLA}

    salida = set()
    for token, clase_token in _LEXICO.items():
        if clase_token != SIGLA:
            continue
        conteo = _OBSERVACIONES.get(token, {})
        total = sum(conteo.values())
        if total and conteo.get("MAYUS", 0) / total >= dominancia:
            salida.add(token)
    return salida


def nombres_propios():
    """Conjunto de tokens que el corpus escribe como nombre propio."""
    return {t for t, c in _LEXICO.items() if c == NOMBRE}


# ==========================================================
# RESTAURACIÓN DE LA CAPITALIZACIÓN
# ==========================================================

def restaurar(texto):
    """
    Devuelve la nota con la capitalizacion que el corpus indica. Una nota que
    ya viene con mayusculas y minusculas se devuelve sin tocar; solo se
    reescriben las notas gritadas, y los tokens sin evidencia pasan a minuscula.
    """
    texto = str(texto or "")
    if not texto or not texto_gritado(texto):
        return texto

    partes = []
    ultimo = 0
    inicio_oracion = True

    for m in RE_TOKEN.finditer(texto):
        entre = texto[ultimo:m.start()]
        if entre:
            partes.append(entre)
            if RE_FIN_ORACION.search(entre):
                inicio_oracion = True
        palabra = m.group(0)
        partes.append(_recapitalizar(palabra, inicio_oracion))
        inicio_oracion = False
        ultimo = m.end()

    partes.append(texto[ultimo:])
    return "".join(partes)


def _recapitalizar(palabra, inicio_oracion):
    """
    Escribe una palabra según su clase: en mayúsculas si es sigla, con inicial
    si es nombre propio o si abre oración, y en minúsculas en los demás casos.
    """
    clase_token = clase(palabra)

    if clase_token == SIGLA:
        return palabra.upper()
    if clase_token == NOMBRE:
        return palabra.capitalize()
    if inicio_oracion and len(palabra) >= LONGITUD_MINIMA:
        # mayuscula inicial de oracion: es la ortografia normal del espanol y
        # es lo que el modelo de spaCy vio durante su entrenamiento
        return palabra.capitalize()
    return palabra.lower()


def mayusculas_informativas(texto):
    """
    Tokens de una nota cuya mayúscula no se explica por abrir oración ni por
    rotular un campo: solo queda la que aporta información (nombre propio o
    sigla). La usa la protección por entidades para confirmar al reconocedor.
    """
    encontrados = set()
    for fragmento in RE_ORACION.split(str(texto or "")):
        for posicion, m in enumerate(RE_TOKEN.finditer(fragmento)):
            palabra = m.group(0)
            if posicion == 0 or len(palabra) < LONGITUD_MINIMA:
                continue
            if RE_ETIQUETA.match(fragmento, m.end()):
                continue
            if palabra[0].isupper():
                encontrados.add(palabra.lower())
    return encontrados


def diagnosticar(token):
    """
    Por qué un token quedó clasificado como quedó: su clase, el recuento de
    formas observadas y el porcentaje de cada una. Herramienta de inspección
    manual.
    """
    token = str(token).lower()
    conteo = _OBSERVACIONES.get(token)
    if conteo is None:
        return {"token": token, "clase": None,
                "motivo": "sin observaciones en notas bien escritas"}
    total = sum(conteo.values())
    return {
        "token": token,
        "clase": _LEXICO.get(token),
        "observaciones": conteo,
        "total": total,
        "pct_mayus": round(100 * conteo.get("MAYUS", 0) / total, 1),
        "pct_inicial": round(100 * conteo.get("Inicial", 0) / total, 1),
        "pct_minus": round(100 * conteo.get("minus", 0) / total, 1),
    }


# ==========================================================
# GENERACIÓN DEL ARCHIVO
# ==========================================================

def main():
    """
    Regenera el léxico de capitalización leyendo la tabla de triage completa e
    informa de qué parte del corpus resultó aprovechable.
    """
    import pandas as pd
    from NLP.nucleo.conexion_bd import obtener_engine

    print("Leyendo notas...")
    df = pd.read_sql(
        "SELECT HCTMOTCON FROM DIM_TRIAGE WHERE HCTMOTCON IS NOT NULL "
        "AND LTRIM(RTRIM(HCTMOTCON)) <> ''", obtener_engine())
    textos = df["HCTMOTCON"].astype(str).tolist()
    utiles = sum(1 for t in textos if not texto_gritado(t))
    print(f"  {len(textos):,} notas, {utiles:,} con capitalizacion aprovechable "
          f"({100*utiles/max(len(textos),1):.1f}%)")

    total = construir(textos)
    guardar()

    print(f"\nLexico: {total:,} entradas")
    print(f"  siglas        : {len(siglas()):,}")
    print(f"  nombres propios: {len(nombres_propios()):,}")
    print(f"  palabras comunes: {sum(1 for c in _LEXICO.values() if c == COMUN):,}")
    print(f"\nGuardado en {RUTA_LEXICO}")


if __name__ == "__main__":
    main()
