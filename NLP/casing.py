"""
Recuperacion de la capitalizacion, aprendida del propio corpus.

EL PROBLEMA
    El 87,7% de las notas de triage esta escrito integramente en mayusculas.
    Para esas notas, reglas.detectar_protegidos() devuelve un conjunto vacio:
    su unica senal es el contraste entre mayusculas y minusculas, y en un
    bloque de mayusculas no hay contraste que leer. O sea que la defensa
    principal contra corromper nombres propios, siglas y farmacos esta apagada
    en nueve de cada diez notas.

    La respuesta anterior a esto fue diccionario_siglas.json: 483 entradas
    escritas a mano. No escala, y ademas obliga a dar UNA respuesta global a
    un token cuyo sentido depende del contexto. El caso que lo demuestra es
    'IR': como insulinorrequiriente debe ir en mayuscula, como verbo 'ir' no,
    asi que la unica salida era listarlo en no_restaurar_mayuscula y perder la
    sigla en todas las notas.

LA IDEA
    El hospital ya escribio la respuesta. Hay 11.415 notas con capitalizacion
    normal, y en ellas se ve como se escribe cada palabra realmente. Medido
    sobre el corpus completo:

        ir         56 MAYUS   0 Inicial   11 minus  -> sigla
        hta       274 MAYUS   0 Inicial   35 minus  -> sigla
        manizales   0 MAYUS 208 Inicial    7 minus  -> nombre propio
        dolor      24 MAYUS   6 Inicial 4276 minus  -> palabra comun

    Ese recuento es el diccionario, y se regenera solo cuando cambia el
    corpus. Reemplaza al mantenimiento manual, no lo complementa.

QUE NO RESUELVE, Y HAY QUE DECIRLO
    Un termino que nunca aparecio en una nota bien escrita no tiene evidencia
    y este modulo se abstiene. Medido: 'stemi' (1 observacion), 'timi' (1) y
    'fazekas' (0) quedan fuera de alcance, y 'dolex' aparece en minuscula
    porque asi lo escriben. Esos casos los tiene que frenar el guardian
    clinico y los umbrales del corrector, no el casing.

COMO SE USA
    casing.construir(textos)      cuenta las formas sobre notas bien escritas
    casing.guardar()              deja el lexico en lexico_casing.json
    casing.cargar()               lo lee sin recalcular
    casing.restaurar(nota)        devuelve la nota gritada con su capitalizacion

El texto que se corrige sigue siendo el de limpieza.limpiar(), en minusculas:
medido sobre 250 notas, en minusculas spaCy conserva el 94,9% de las etiquetas
gramaticales y el 93,8% de las dependencias, mientras que en mayusculas cae a
64,4% y 67,1%. Lo que se recupera aca es la senal para PROTEGER, que es lo que
de verdad se pierde al minusculizar: el NER pasa de 575 entidades a 163.
"""

import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

RUTA_LEXICO = Path(__file__).resolve().parent / "lexico_casing.json"

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


def sin_tildes(palabra):
    return "".join(c for c in unicodedata.normalize("NFD", str(palabra))
                   if not unicodedata.combining(c))


def texto_gritado(texto):
    letras = [c for c in str(texto) if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


# ==========================================================
# CONSTRUCCION DEL LEXICO
# ==========================================================

def _contar(textos):
    """
    Cuenta como se escribe cada palabra en las notas que si tienen contraste.

    SOLO CUENTA LA MAYUSCULA QUE NO SE EXPLICA POR LA POSICION
        Una mayuscula puede venir de tres sitios, y dos de ellos no dicen nada
        sobre la palabra:

          abrir oracion   'Paciente refiere...' No es un nombre propio, es la
                          ortografia normal del espanol.
          etiquetar campo 'Ocupacion:', 'Alergicos:', 'Toxicos:'. Van en
                          mayuscula porque encabezan un apartado de la
                          plantilla de la historia clinica.
          ser el nombre   'Manizales', 'Sjogren', 'Dr'. Esta es la unica que
                          aporta informacion.

        La primera version de este modulo solo descartaba la primera, y por eso
        aprendio como nombres propios a 'Ocupacion', 'Alergicos', 'Toxicos',
        'Quirurgicos', 'Farmacologicos' y 'Acompanante': todas las etiquetas de
        la plantilla. Se descartan tambien los tokens seguidos de dos puntos.
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
    """SIGLA, NOMBRE, COMUN o None si no hay evidencia suficiente."""
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
    Construye el lexico a partir de un corpus. Devuelve cuantas entradas quedaron.

    textos: iterable de notas SIN limpiar. Las mayusculas del original son toda
    la materia prima de este modulo, asi que recibe el texto crudo.
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
    return bool(_LEXICO)


def guardar(ruta=RUTA_LEXICO):
    datos = {
        "_descripcion": (
            "Capitalizacion aprendida de las notas del hospital escritas con "
            "mayusculas y minusculas. Generado por casing.construir(); no se "
            "edita a mano. Para regenerarlo: python casing.py"),
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
# CONSULTA
# ==========================================================

def clase(token):
    """SIGLA, NOMBRE, COMUN o None si el corpus no tiene evidencia del token."""
    return _LEXICO.get(str(token).lower())


def es_sigla(token):
    return clase(token) == SIGLA


def es_nombre_propio(token):
    return clase(token) == NOMBRE


def siglas(dominancia=None):
    """
    Las siglas aprendidas. Complementa a diccionario_siglas.json.

    dominancia: si se pasa, solo devuelve las que superan esa fraccion de
    apariciones en mayuscula. Sirve para separar dos usos distintos:

      proteger un token de la correccion    basta la mayoria simple: proteger
          de mas no corrompe nada, solo deja una palabra sin corregir;
      escribirlo en mayuscula en la salida   hace falta mas certeza, porque
          equivocarse SI cambia el texto. 'ir' aparece en mayuscula el 83,6%
          de las veces: suficiente para protegerlo, no para convertir en 'IR'
          todos los 'puede ir al bano' de una nota gritada.
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
    return {t for t, c in _LEXICO.items() if c == NOMBRE}


# ==========================================================
# RESTAURACION
# ==========================================================

def restaurar(texto):
    """
    Devuelve la nota con la capitalizacion que el corpus dice que corresponde.

    Sobre una nota que ya viene con mayusculas y minusculas no se toca nada: su
    autor ya dio la informacion y es mejor evidencia que cualquier promedio.

    Los tokens sin evidencia van a minuscula. Es la opcion segura medida: en
    minusculas spaCy conserva el 94,9% de las etiquetas gramaticales, mientras
    que dejarlos en mayuscula las hunde al 64,4% y multiplica por 3,6 las
    entidades falsas.
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
    Tokens del texto cuya mayuscula dice algo sobre la palabra.

    Es la misma regla con la que se construye el lexico, aplicada ahora a una
    nota concreta: una mayuscula que se explica por la posicion no es
    evidencia. Se descartan las de inicio de oracion y las de etiqueta de
    campo, y queda solo la que no tiene otra explicacion que ser un nombre
    propio o una sigla.

    POR QUE HACE FALTA
        reglas.entidades() protegia una entidad del NER solo si el token venia
        en mayuscula en el original, para descartar los falsos positivos que
        spaCy produce sobre palabras raras. Al pasarle el texto ya
        recapitalizado ese filtro quedo vacio: restaurar() pone mayuscula al
        abrir oracion, asi que 'Pacinete' la cumplia y el typo quedaba
        protegido. Medido: se dejaron de corregir 'pacinete' y
        'hipotirodismo', que la version anterior si arreglaba.
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
    """Por que un token quedo clasificado como quedo."""
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
# GENERACION
# ==========================================================

def main():
    """Regenera lexico_casing.json leyendo la tabla de triage completa."""
    import pandas as pd
    from conexion_bd import obtener_engine

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
