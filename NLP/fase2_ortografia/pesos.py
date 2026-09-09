"""
Peso clínico de cada palabra: cuánta protección merece frente al corrector.

EL CRITERIO QUE INTRODUCE ESTE MÓDULO
    El diseño anterior protegía por veto: el corrector proponía un cambio y una
    serie de guardias intentaban bloquearlo. Basta con que uno de ellos tenga un
    hueco para que el cambio pase, y un veto que se puede rodear termina
    rodeándose.

    Aquí se invierte: cada palabra recibe un peso clínico ANTES de que el
    corrector la vea, y la que pesa lo suficiente no llega a él. No hay veto que
    pueda fallar porque no hay nada que vetar. Es la misma inversión que se
    aplica a las siglas en `recursos/ambiguedad.py`: no se toca nada salvo que
    se demuestre que se puede.

LA ESCALA
    El peso es evidencia acumulada, no una clasificación. Ninguna fuente decide
    por sí sola, porque ninguna es fiable por sí sola:

        1.00  contiene un dígito                 nunca se toca
        0.95  diccionario, catálogo o léxico externo
        0.90  termina como un principio activo
        0.70  contiene morfemas médicos
        0.60  sigla aprendida del corpus
        0.45  vocabulario del modelo biomédico
        0.40  frecuente en el hospital y desconocida para el español
        0.00  ninguna evidencia
        0.00  corrección directa declarada       es un error conocido: se
                                                 corrige siempre

    Por encima de UMBRAL_PROTECCION la palabra no pasa al corrector general.

POR QUÉ EL VOCABULARIO DE spaCy NO ES UN VETO
    Era la protección más amplia del pipeline y estaba mal empleada. El modelo
    se entrenó con texto web y reconoce faltas de ortografía frecuentes, de modo
    que declararlas intocables impedía corregirlas para siempre. Aquí pasa a ser
    lo que debe ser: una señal débil, que suma poco. Que una palabra aparezca en
    un corpus web no prueba que sea terminología clínica ni que esté bien
    escrita.
"""

from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.nucleo import reglas
from NLP.recursos import casing
from NLP.recursos import lexico

# ==========================================================
# CONFIGURACION
# ==========================================================

# Por encima de este peso la palabra no llega al corrector general. El valor
# separa las fuentes con evidencia clinica (diccionario, catalogo, farmaco,
# morfemas) de las que solo indican que la palabra existe en alguna parte.
UMBRAL_PROTECCION = 0.5

# Peso a partir del cual se intenta arreglar la palabra contra el lexico
# clinico en lugar de dejarla intacta. Es lo que convierte 'abodominal' en
# 'abdominal' sin pasar por un corrector de espanol.
UMBRAL_CORRECCION_MEDICA = 0.4

# Apariciones en el corpus a partir de las cuales una palabra desconocida deja
# de parecer un typo. Un error de digitacion se repite unas pocas veces; una
# sigla o una jerga del servicio se repite muchas.
FRECUENCIA_JERGA = 8

PESOS = {
    "correccion_directa": 0.0,     # declarado como error: se corrige si o si
    "diccionario": 0.95,
    "catalogo": 0.95,
    "externo": 0.95,
    "farmaco": 0.90,

    # El vocabulario del modelo biomedico queda deliberadamente por debajo del
    # umbral de proteccion. El tokenizador se entreno sobre historias clinicas
    # escritas en espanol, de modo que su vocabulario contiene el idioma
    # corriente entero y no solo la terminologia: con un peso alto protegia
    # palabras comunes y, peor, congelaba las mal escritas que tambien figuran
    # en el, que asi no recibian su tilde.
    #
    # Donde si aporta es como DESTINO de correccion y no como escudo: es la
    # unica fuente que contiene muchos principios activos y epinimos, y sin ella
    # el lexico no podria corregir hacia ellos. Por eso pesa, pero no basta.
    "biomedico": 0.45,
    "morfemas": 0.70,
    "sigla_corpus": 0.60,
    "jerga_frecuente": 0.40,
    "numero": 1.00,                # nada con un digito se toca jamas
    "ninguna": 0.0,
}

_CONTEO = None      # frecuencias del corpus, las inyecta ortografia.py


def usar_conteo(conteo):
    """
    Registra el recuento de frecuencias del corpus, que construye el módulo de
    candidatos. Sin él, la señal de jerga frecuente queda desactivada.
    """
    global _CONTEO
    _CONTEO = conteo


def frecuencia(palabra):
    """Veces que la palabra aparece en el corpus. 0 si no hay corpus cargado."""
    return _CONTEO.get(str(palabra).lower(), 0) if _CONTEO else 0


_frecuencia = frecuencia


# ==========================================================
# CÁLCULO DEL PESO
# ==========================================================

def peso(palabra):
    """
    Devuelve el par (peso, motivo) de una palabra suelta.

    Las fuentes se consultan de mayor a menor autoridad y la primera que
    reconoce la palabra fija el peso. El motivo acompaña siempre al valor porque
    es lo que se vuelca en el informe de auditoría: sin él no se puede explicar
    después por qué una palabra quedó como quedó.
    """
    token = morfologia.normalizar(palabra)
    if not token:
        return PESOS["ninguna"], "ninguna"

    if morfologia.tiene_numero(token):
        return PESOS["numero"], "numero"

    # Un error declarado a mano manda sobre cualquier otra evidencia. Hace
    # falta porque el vocabulario biomedico incorporo faltas de ortografia tan
    # frecuentes que el modelo las aprendio, y sin esta comprobacion quedarian
    # protegidas.
    if token in reglas.DIRECTAS:
        return PESOS["correccion_directa"], "correccion_directa"

    if lexico.disponible():
        origen = lexico.fuente(token)
        if origen == lexico.DICCIONARIO:
            return PESOS["diccionario"], "diccionario"
        if origen == lexico.CATALOGO:
            return PESOS["catalogo"], "catalogo"
        if origen == lexico.EXTERNO:
            return PESOS["externo"], "externo"
        if origen == lexico.BIOMEDICO:
            return PESOS["biomedico"], "biomedico"

    if token in reglas.SIGLAS:
        return PESOS["diccionario"], "diccionario"

    if morfologia.parece_farmaco(token):
        return PESOS["farmaco"], "farmaco"

    if morfologia.es_termino_medico(token):
        return PESOS["morfemas"], "morfemas"

    if casing.disponible() and casing.es_sigla(token):
        return PESOS["sigla_corpus"], "sigla_corpus"

    # el corpus la repite y ningun diccionario del espanol la reconoce: es jerga
    # del servicio, un nombre comercial o una sigla que falta en el diccionario
    if (_frecuencia(token) >= FRECUENCIA_JERGA
            and not linguistica.en_vocabulario(token)):
        return PESOS["jerga_frecuente"], "jerga_frecuente"

    return PESOS["ninguna"], "ninguna"


def protegida(palabra):
    """True si el peso de la palabra alcanza el umbral de protección."""
    return peso(palabra)[0] >= UMBRAL_PROTECCION


def pesar_texto(texto):
    """
    Pesa todas las palabras del texto y devuelve una tupla
    (palabra, inicio, fin, peso, motivo) por cada una, con las posiciones en
    caracteres. Es la vista que consume el enmascarado clínico.
    """
    salida = []
    for m in reglas.RE_PALABRA.finditer(str(texto).lower()):
        p, motivo = peso(m.group(0))
        salida.append((m.group(0), m.start(), m.end(), p, motivo))
    return salida


def diagnosticar(texto):
    """
    Peso de cada palabra de una nota, con su motivo, si queda protegida y su
    frecuencia en el corpus. Herramienta de inspección manual.
    """
    return [
        {"palabra": palabra, "peso": p, "motivo": motivo,
         "protegida": p >= UMBRAL_PROTECCION,
         "frecuencia_corpus": _frecuencia(palabra)}
        for palabra, _i, _f, p, motivo in pesar_texto(texto)
    ]
