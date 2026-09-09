"""
Elección del candidato de corrección.

LanguageTool propone varias sugerencias por error y no las ordena por
probabilidad clínica, así que la elección la toma este módulo. Está separado del
orquestador porque es la lógica más delicada de la fase y la que concentra los
ajustes de umbral.

ORDEN DE PRIORIDAD
  1. Restauración de tilde. Si un candidato es la misma palabra acentuada, es
     ese: 'palida' se corrige a 'pálida', nunca a 'salida'.
  2. Filtro de viabilidad. Un candidato debe superar las reglas de protección,
     el criterio de forma, un mínimo de apariciones en el corpus y el veto del
     guardián clínico.
  3. Menor distancia de edición, con la frecuencia en el corpus como desempate.

LOS UMBRALES, Y QUÉ EVITA CADA UNO
    FRECUENCIA_CANDIDATO   una corrección que nadie escribió nunca en el
                           hospital no es una corrección.
    UMBRAL_TERMINO y       un original que se repite y además tiene forma de
    FACTOR_TERMINO         término solo se corrige si el candidato lo supera con
                           holgura.
    FACTOR_RESPALDO        cuando el original figura en el vocabulario de spaCy,
                           el corpus tiene que respaldar el cambio.
    FRECUENCIA_DESEMPATE   y RATIO_DESEMPATE: ante varios candidatos igual de
                           cercanos, uno debe dominar claramente.

Cuando ningún candidato reúne evidencia suficiente, el módulo se abstiene y
deja constancia en el registro de abstenciones. Elegir sin evidencia no mejora
el texto: inventa información.
"""

from collections import Counter

from rapidfuzz.distance import DamerauLevenshtein

from NLP.fase2_ortografia import terminologia
from NLP.nucleo import reglas

MAX_CANDIDATOS = 10
LONGITUD_CANDIDATO_UNICO = 6  # a partir de aqui se acepta un candidato unico
FRECUENCIA_CANDIDATO = 3      # el candidato debe existir en las notas del hospital
FRECUENCIA_DESEMPATE = 10     # apariciones minimas para elegir entre varios
RATIO_DESEMPATE = 3           # el ganador debe superar al segundo por este factor
UMBRAL_TERMINO = 10           # a partir de aqui el original se considera termino real
FACTOR_TERMINO = 5            # y su correccion debe ser N veces mas frecuente

# Cuanto debe superar la correccion al original cuando este figura en el
# vocabulario de spaCy. Es mas bajo que FACTOR_TERMINO a proposito: llegado a
# este punto ya se sabe que el token no es terminologia clinica, porque el peso
# clinico lo habria apartado antes, y el unico riesgo que queda es cambiar una
# palabra corriente por otra.
FACTOR_RESPALDO = 2

CONTEO = Counter()


def construir_lexico(textos):
    """
    Cuenta las palabras del corpus y deja el recuento disponible para todo el
    módulo. Es la base de todos los desempates por frecuencia, así que debe
    llamarse antes de empezar a corregir.
    """
    CONTEO.clear()
    for t in textos:
        CONTEO.update(reglas.RE_PALABRA.findall(str(t).lower()))
    return CONTEO


def frecuencia(expresion):
    """
    Apariciones de una expresión en el corpus. Para expresiones de varias
    palabras devuelve la de la palabra menos frecuente, que es la que limita la
    credibilidad del conjunto.
    """
    partes = reglas.RE_PALABRA.findall(str(expresion).lower())
    if not partes:
        return 0
    return min(CONTEO.get(p, 0) for p in partes)


def elegir(original, sugerencias, protegidos=()):
    """
    Devuelve la corrección que debe aplicarse, o None si no hay evidencia
    suficiente para ninguna.

        original     palabra tal como aparece en la nota
        sugerencias  propuestas de LanguageTool, en su orden original
        protegidos   tokens que esta nota concreta declara intocables

    Toda salida None queda registrada como abstención, con el motivo.
    """
    original = reglas.normalizar(original)
    if not original or reglas.tiene_numero(original):
        return None

    # 1. tilde faltante: no es un error de digitacion
    for cand in sugerencias[:MAX_CANDIDATOS]:
        if reglas.es_restauracion_tilde(original, cand):
            return cand

    # 2. que spaCy reconozca el original ya no es un veto, sino una exigencia
    #    de respaldo. Su vocabulario procede de texto web y contiene faltas de
    #    ortografia frecuentes; tratarlo como veto absoluto las congelaba para
    #    siempre, aunque LanguageTool propusiera la forma correcta.
    #
    #    La proteccion de la terminologia clinica ya no depende de esto: la
    #    resuelve antes el peso clinico, y lo que pesa se aparta en el
    #    enmascarado y no llega hasta aqui.
    exige_respaldo = reglas.es_palabra_conocida(original)

    viables = []
    for cand in sugerencias[:MAX_CANDIDATOS]:
        norm = cand.lower().strip()
        if not norm or reglas.esta_protegido(norm, protegidos):
            continue
        if not reglas.forma_aceptable(original, norm):
            continue
        if frecuencia(norm) < FRECUENCIA_CANDIDATO:
            continue
        # el guardian clinico tiene la ultima palabra sobre el criterio ortografico
        if not terminologia.admite(original, norm):
            continue
        viables.append((DamerauLevenshtein.distance(original, norm),
                        -frecuencia(norm), cand))

    if not viables:
        terminologia.anotar_abstencion(original, "ningun candidato admisible")
        return None

    viables.sort()

    # 3. un original muy repetido se considera terminologia, pero se exige
    #    ademas que TENGA FORMA de termino. Sin esa segunda condicion, en un
    #    corpus donde todos cometen la misma falta, la falta se protege a si
    #    misma por frecuente.
    freq_original = frecuencia(original)
    if freq_original >= UMBRAL_TERMINO and terminologia.es_terminologia(original):
        if -viables[0][1] < freq_original * FACTOR_TERMINO:
            return None

    distancia_minima = viables[0][0]
    empatados = [v for v in viables if v[0] == distancia_minima]

    # 3bis. el original esta en el vocabulario de spaCy: puede ser una palabra
    #       legitima o una falta tan comun que entro al corpus con el que se
    #       entreno el modelo. Lo que las separa es como escribe el hospital,
    #       asi que se exige que la correccion supere al original en las notas.
    if exige_respaldo:
        mejor_freq = -empatados[0][1]
        if mejor_freq < max(freq_original * FACTOR_RESPALDO, FRECUENCIA_DESEMPATE):
            terminologia.anotar_abstencion(
                original, "palabra del vocabulario sin respaldo del corpus")
            return None

    # 4. un solo candidato a la distancia minima, en palabra larga
    if len(empatados) == 1 and len(original) >= LONGITUD_CANDIDATO_UNICO:
        return empatados[0][2]

    # 5. varios igual de cerca: decide el corpus, y por margen amplio
    mejor = -empatados[0][1]
    segunda = -empatados[1][1] if len(empatados) > 1 else 0
    if mejor >= FRECUENCIA_DESEMPATE and mejor >= max(segunda * RATIO_DESEMPATE, 1):
        return empatados[0][2]

    # varios candidatos igual de plausibles y ninguno domina: no hay manera de
    # saber cual se quiso escribir, y elegir uno inventaria informacion
    terminologia.anotar_abstencion(original, "varios candidatos sin uno dominante")
    return None
