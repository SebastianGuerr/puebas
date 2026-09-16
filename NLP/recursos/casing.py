"""
Recuperación de la capitalización, aprendida del propio corpus.

EL PROBLEMA
    La gran mayoría de las notas de triage está escrita íntegramente en
    mayúsculas. En ellas, la detección de nombres propios por contraste de
    capitalización no tiene nada que leer, de modo que la defensa principal
    contra corromper nombres, siglas y fármacos queda desactivada justo en el
    caso más frecuente.

    La respuesta anterior era un diccionario escrito a mano. No escala, y además
    obliga a dar una única respuesta global a un token cuyo sentido depende del
    contexto: 'ir' es sigla cuando significa insulinorrequiriente y verbo cuando
    no, y la lista negra solo permitía perder uno de los dos usos.

LA IDEA
    El hospital ya escribió la respuesta. Una parte del corpus está redactada
    con capitalización normal, y en ella se ve cómo se escribe realmente cada
    palabra. Contando esas apariciones se obtiene, por token, si se comporta
    como sigla, como nombre propio o como palabra común:

        ir          casi siempre en mayúsculas        -> sigla
        manizales   casi siempre con inicial          -> nombre propio
        dolor       casi siempre en minúsculas        -> palabra común

    Ese recuento es el léxico, se regenera cuando cambia el corpus y sustituye
    al mantenimiento manual en lugar de complementarlo.

QUÉ NO RESUELVE
    Un término que nunca apareció en una nota bien escrita no tiene evidencia, y
    entonces este módulo se abstiene. Esos casos quedan en manos del guardián
    clínico y de los umbrales del corrector.

USO
    construir(textos)   cuenta las formas sobre las notas con contraste
    guardar() / cargar()  persisten el léxico
    restaurar(nota)     devuelve una nota gritada con su capitalización
    clase(token)        qué aprendió el corpus sobre un token

El texto que se corrige sigue siendo el de la fase de limpieza, en minúsculas,
porque es la forma con la que mejor rinde el análisis gramatical. Lo que se
recupera aquí es la señal para proteger, que es la que de verdad se pierde al
pasar todo a minúsculas.
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
    Cuenta cómo se escribe cada palabra en las notas que sí tienen contraste
    de capitalización. Devuelve, por token en minúscula, un contador con las
    apariciones en mayúsculas, con inicial y en minúsculas.

    Solo cuenta la mayúscula que no se explica por la posición, porque de las
    tres razones por las que una palabra puede llevarla, dos no dicen nada sobre
    la palabra en sí:

        abrir oración     es la ortografía normal del español.
        etiquetar campo   'Ocupacion:', 'Alergicos:' encabezan un apartado de la
                          plantilla de la historia clínica.
        ser un nombre     esta es la única que aporta información.

    De ahí las dos exclusiones del bucle: el primer token de cada fragmento y
    todo token seguido de dos puntos. Sin la segunda, el léxico aprendía como
    nombres propios los rótulos de la plantilla.
    """
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
    Clasifica un token a partir de su contador de formas: SIGLA, NOMBRE o COMUN.

    Devuelve None cuando no hay evidencia suficiente, sea porque el token se vio
    pocas veces o porque se usa de varias formas sin que ninguna alcance la
    dominancia exigida. En ese caso no existe una respuesta global correcta y el
    módulo se abstiene.
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
    Construye el léxico a partir de un corpus y devuelve cuántas entradas
    quedaron.

    `textos` es un iterable de notas SIN limpiar: las mayúsculas del original
    son toda la materia prima de este módulo.
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
    Conjunto de siglas aprendidas del corpus. Complementa al diccionario de
    siglas escrito a mano.

    Con `dominancia` se exige además que superen esa fracción de apariciones en
    mayúscula. El parámetro existe porque las siglas se usan para dos cosas de
    exigencia distinta:

        proteger un token       basta la mayoría simple; proteger de más no
                                corrompe nada, solo deja una palabra sin
                                corregir.
        escribirlo en mayúscula hace falta más certeza, porque equivocarse sí
                                altera el texto: convertir en sigla todos los
                                usos de una palabra frecuente estropea la nota.
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
    Devuelve la nota con la capitalización que el corpus indica.

    Una nota que ya viene con mayúsculas y minúsculas se devuelve sin tocar: lo
    que escribió su autor es mejor evidencia que cualquier promedio. Solo se
    reescriben las notas gritadas.

    Los tokens sin evidencia pasan a minúscula, que es la opción segura: el
    análisis gramatical se degrada mucho menos en minúsculas que en mayúsculas.
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
    Tokens de una nota cuya mayúscula aporta información sobre la palabra.

    Aplica a una nota concreta el mismo criterio con el que se construye el
    léxico: se descartan las mayúsculas de inicio de oración y las de rótulo de
    campo, y queda solo la que no tiene otra explicación que ser un nombre
    propio o una sigla.

    Lo usa la protección por entidades para confirmar lo que propone el
    reconocedor. Aceptar cualquier mayúscula no sirve, porque sobre un texto ya
    recapitalizado toda oración abre en mayúscula y hasta una palabra mal
    escrita pasaría por nombre propio.
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
