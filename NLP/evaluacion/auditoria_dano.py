"""
Daño probable: sustituciones sospechosas de estropear la nota en vez de
arreglarla, sin necesidad de haberlas visto antes. Parte de
`evaluacion/auditoria.py` (E6.2, division de archivos grandes); la
explicacion de por que hace falta ademas de las regresiones y la
referencia anotada esta en docs/ARQUITECTURA.md #2.9.

QUÉ OFRECE
    motivo_dano()    por que una sustitucion concreta es sospechosa, o None
    dano_probable()  aplica motivo_dano() a las filas de un reporte
"""

# Mismo plegado que usa auditoria_medicion (aqui tambien incluye la eñe: ver
# su docstring). Se importa en vez de duplicarlo.
from NLP.evaluacion.auditoria_medicion import _sin_tildes

# Motivos, del más grave al más leve.
DANO_DIVISION = "palabra correcta partida en dos"
DANO_DECLARADA = "termino declarado en el diccionario"
DANO_CONOCIDA = "palabra que el espanol reconoce"
DANO_DISTANCIA = "el reemplazo no se parece al original"
DANO_FRECUENCIA = "el original es mucho mas frecuente que el reemplazo"

# Un reemplazo que comparte pocas letras con el original no es una corrección
# ortográfica: es otra palabra. El umbral es relativo a la longitud porque dos
# ediciones sobre una palabra de cuatro letras cambian el concepto y sobre una
# de quince no.
FRACCION_DISTANCIA_MAXIMA = 0.40

# Cuántas veces más frecuente tiene que ser el original para que sustituirlo
# resulte sospechoso. Una errata no es más común que su forma correcta.
FACTOR_FRECUENCIA = 10


def _distancia(a, b):
    """Distancia de edición sin dependencias externas."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1,
                              previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def motivo_dano(original, reemplazo, conocida=None, declarada=None, frecuencia=None):
    """
    Por qué una sustitución concreta es sospechosa, o None si no lo es.

    Las cuatro comprobaciones se aplican en orden de gravedad. Los tres últimos
    parámetros son funciones que se inyectan para poder llamar a esto sin cargar
    spaCy ni el corpus; cuando faltan, la comprobación que dependía de ellas
    simplemente no se hace.
    """
    original = str(original or "").strip()
    reemplazo = str(reemplazo or "").strip()
    if not original or not reemplazo or original == reemplazo:
        return None

    plano_o = _sin_tildes(original.lower())
    plano_r = _sin_tildes(reemplazo.lower())

    # Restaurar una tilde deja las mismas letras y no puede cambiar el
    # concepto: nunca es daño, y se descarta antes que nada.
    if plano_o == plano_r:
        return None

    if " " in reemplazo and conocida and conocida(original):
        return DANO_DIVISION

    if declarada and declarada(original):
        return DANO_DECLARADA

    # UNA EDICION O UNAS LETRAS BAILADAS ES UNA ERRATA, NO UN DESTROZO.
    #
    # Sin esta salida, la regla siguiente marcaba como sospechosas justo las
    # correcciones que mejor funcionan:
    #
    #     apra -> para      mcuho -> mucho     ahce -> hace
    #     tien -> tiene     door  -> dolor     fibre -> fiebre
    #
    # Todas son typos de teclado, y todas disparaban 'palabra que el espanol
    # reconoce' porque el vocabulario de spaCy es laxo y acepta 'apra' o 'tien'
    # como palabras. Medido sobre el informe real, eran 32 de las 76 alertas.
    #
    # Las dos formas de la errata de teclado se reconocen solas: o son las
    # mismas letras en otro orden, o falta o sobra una. Ninguna de las dos
    # puede convertir una palabra en otra que no se le parezca, que es lo que
    # esta funcion busca. Va DESPUES de las dos reglas anteriores a proposito:
    # 'dorada' -> 'morada' es una sola edicion y aun asi es daño, y lo salva
    # que el municipio este declarado en el diccionario.
    if sorted(plano_o) == sorted(plano_r) or _distancia(plano_o, plano_r) <= 1:
        return None

    if conocida and conocida(original):
        return DANO_CONOCIDA

    limite = max(1, int(len(plano_o) * FRACCION_DISTANCIA_MAXIMA))
    if _distancia(plano_o, plano_r.replace(" ", "")) > limite:
        return DANO_DISTANCIA

    if frecuencia:
        f_o, f_r = frecuencia(original), frecuencia(reemplazo)
        if f_o and f_o >= FACTOR_FRECUENCIA * max(f_r, 1):
            return DANO_FRECUENCIA

    return None


def dano_probable(filas, minimo=1):
    """
    Sustituciones sospechosas de haber estropeado la nota en vez de arreglarla.

    `filas` son las que devuelve escribir_reporte(): (fase, original, reemplazo,
    veces, oid). Devuelve la misma forma con el motivo añadido, ordenada por
    gravedad y luego por frecuencia, de modo que lo que más notas afecta salga
    primero.

    Solo mira la fase de ortografía: la limpieza no cambia palabras y la
    normalización sustituye a propósito.
    """
    try:
        from NLP.fase2_ortografia import pesos
        from NLP.nucleo import reglas
        conocida = lambda p: reglas.es_palabra_conocida(reglas.normalizar(p))
        declarada = lambda p: reglas.normalizar(p) in reglas.SIGLAS
        frecuencia = pesos.frecuencia
    except Exception:
        conocida = declarada = frecuencia = None

    orden = {DANO_DIVISION: 0, DANO_DECLARADA: 1, DANO_CONOCIDA: 2,
             DANO_DISTANCIA: 3, DANO_FRECUENCIA: 4}

    salida = []
    for fila in filas:
        fase, original, reemplazo, veces = fila[0], fila[1], fila[2], fila[3]
        oid = fila[4] if len(fila) > 4 else ""
        if fase != "ortografia" or veces < minimo:
            continue
        motivo = motivo_dano(original, reemplazo, conocida, declarada, frecuencia)
        if motivo:
            salida.append((motivo, original, reemplazo, veces, oid))

    salida.sort(key=lambda x: (orden.get(x[0], 9), -x[3]))
    return salida
