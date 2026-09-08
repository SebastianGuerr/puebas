"""
Peso clinico de cada palabra: cuanto hay que protegerla del corrector.

EL CAMBIO DE POLITICA QUE INTRODUCE ESTE ARCHIVO
    Hasta ahora el pipeline funcionaba asi: LanguageTool proponia un cambio y
    ocho guardias intentaban vetarlo (numeros, diccionario, patrones, entidades,
    vocabulario, forma, morfemas, terminologia). Es proteger por veto, y tiene
    un fallo de diseno: basta que UN guardia tenga un agujero para que el cambio
    pase. El caso que lo demostro:

        AÑOÑ -> anón

    'añoñ' y 'anón' pliegan al mismo 'anon' porque sin_tildes() trataba la eñe
    como un acento. Eso hacia True a es_restauracion_tilde(), que es la PRIMERA
    rama de candidatos.elegir() y retorna sin consultar a ninguno de los ocho
    guardias. Un veto que se puede rodear, tarde o temprano se rodea.

    Aca se invierte: cada palabra recibe un peso clinico ANTES de que el
    corrector la vea, y la que pesa lo suficiente no llega al corrector. No hay
    veto que pueda fallar porque no hay nada que vetar.

    Es la misma inversion que ya se hizo en ambiguedad.py con las siglas: en vez
    de transformar por defecto y proteger por excepcion, no se toca salvo que se
    demuestre que se puede.

LA ESCALA
    El peso es evidencia acumulada, no una clasificacion. Ninguna fuente sola
    decide, porque ninguna sola es fiable:

      1.00  correccion directa declarada      es un error conocido: NO se protege
      0.95  diccionario del proyecto          escrito a mano, decision deliberada
      0.95  catalogo de sintomas
      0.90  sufijo de principio activo (DCI)  -pril, -sartan, -azepam, -micina
      0.85  vocabulario biomedico             medido: 94% de precision
      0.70  morfemas medicos                  hipo-, -ectomia, -itis
      0.60  sigla aprendida del corpus        casing.py sobre notas bien escritas
      0.40  frecuente y desconocida           el hospital la repite y ningun
                                              diccionario del espanol la conoce
      0.00  nada

    Por encima de UMBRAL_PROTECCION la palabra no pasa al corrector general.

POR QUE EL VOCABULARIO DE spaCy YA NO ES UN VETO
    Era la proteccion mas amplia del pipeline y estaba mal usada.
    es_core_news_md se entreno con texto web y reconoce 'conciente',
    'transplante', 'aprox' y 'fibre'. Como reglas.es_palabra_conocida() los
    declaraba intocables, esas palabras no se corrigieron NUNCA: medido, 106 de
    106 notas con 'conciente' quedaron sin tocar.

    Aca spaCy pasa a ser lo que siempre debio ser: una senal debil que suma
    poco. Que una palabra este en un corpus web no prueba que sea terminologia
    clinica, y desde luego no prueba que este bien escrita.
"""

import casing
import lexico
import linguistica
import morfologia
import reglas

# ==========================================================
# CONFIGURACION
# ==========================================================

# Por encima de este peso la palabra no llega al corrector general. Se fijo en
# 0.5 porque es lo que separa las fuentes con evidencia clinica (diccionario,
# catalogo, farmaco, biomedico, morfemas) de las que solo dicen 'esta palabra
# existe en alguna parte'.
UMBRAL_PROTECCION = 0.5

# Peso a partir del cual se intenta arreglar la palabra contra el lexico
# clinico en vez de dejarla intacta. Es lo que convierte 'abodominal' en
# 'abdominal' sin preguntarle a un corrector de espanol.
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

    # El vocabulario del modelo biomedico NO protege por si solo, y esto se
    # midio despues de intentarlo:
    #
    #   La primera version le daba 0.85 y con eso protegia 'disculpas', 'ahora',
    #   'vida' y 'cuya'. El motivo es obvio en retrospectiva: el tokenizador se
    #   entreno sobre historias clinicas escritas EN ESPANOL, asi que su
    #   vocabulario BPE contiene el espanol corriente entero, no solo la
    #   terminologia. Protegerlo todo era inofensivo para las palabras bien
    #   escritas, pero congelaba las mal escritas que tambien estaban en el
    #   vocabulario: 'dificil' quedaba protegido y no recibia su tilde.
    #
    #   Se probo restarle el vocabulario de spaCy para quedarse solo con lo
    #   distintivamente clinico. Peor: spaCy conoce 21 de 22 terminos de prueba
    #   ('disnea', 'cefalea', 'taquicardia'), asi que la resta dejaba 1.
    #
    # Donde SI aporta es como DESTINO de correccion, no como escudo: es la unica
    # fuente que tenia 'venlafaxina', 'valsalva', 'craneoencefálico' y
    # 'levofloxacino' para que lexico.cercano() pudiera llegar a ellos. Por eso
    # se queda por debajo del umbral de proteccion: pesa, pero no basta.
    "biomedico": 0.45,
    "morfemas": 0.70,
    "sigla_corpus": 0.60,
    "jerga_frecuente": 0.40,
    "numero": 1.00,                # nada con un digito se toca jamas
    "ninguna": 0.0,
}

_CONTEO = None      # frecuencias del corpus, las inyecta ortografia.py


def usar_conteo(conteo):
    """Recibe el Counter del corpus que ya construye candidatos.py."""
    global _CONTEO
    _CONTEO = conteo


def frecuencia(palabra):
    """Veces que el hospital escribio esa palabra. 0 si no hay corpus cargado."""
    return _CONTEO.get(str(palabra).lower(), 0) if _CONTEO else 0


_frecuencia = frecuencia


# ==========================================================
# PESO
# ==========================================================

def peso(palabra):
    """
    Devuelve (peso, motivo) para una palabra suelta.

    El motivo no es decorativo: es lo que se escribe en el reporte de auditoria
    para poder explicar despues por que una palabra quedo como quedo.
    """
    token = morfologia.normalizar(palabra)
    if not token:
        return PESOS["ninguna"], "ninguna"

    if morfologia.tiene_numero(token):
        return PESOS["numero"], "numero"

    # Un error declarado a mano manda sobre cualquier evidencia. Hace falta
    # porque el vocabulario biomedico contiene faltas de ortografia tan comunes
    # que el modelo las aprendio: 'transplante' esta ahi y sin esta linea
    # quedaria protegido, que es peor que como estaba antes.
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

    # el hospital la repite y ningun diccionario del espanol la conoce: es
    # jerga del servicio, un nombre comercial o una sigla que falta
    if (_frecuencia(token) >= FRECUENCIA_JERGA
            and not linguistica.en_vocabulario(token)):
        return PESOS["jerga_frecuente"], "jerga_frecuente"

    return PESOS["ninguna"], "ninguna"


def protegida(palabra):
    """True si la palabra no debe llegar al corrector general."""
    return peso(palabra)[0] >= UMBRAL_PROTECCION


def pesar_texto(texto):
    """
    [(palabra, inicio, fin, peso, motivo)] para cada palabra del texto.
    Es la vista que consume enmascarado.py.
    """
    salida = []
    for m in reglas.RE_PALABRA.finditer(str(texto).lower()):
        p, motivo = peso(m.group(0))
        salida.append((m.group(0), m.start(), m.end(), p, motivo))
    return salida


def diagnosticar(texto):
    """Peso de cada palabra de una nota. Para revisar casos puntuales."""
    return [
        {"palabra": palabra, "peso": p, "motivo": motivo,
         "protegida": p >= UMBRAL_PROTECCION,
         "frecuencia_corpus": _frecuencia(palabra)}
        for palabra, _i, _f, p, motivo in pesar_texto(texto)
    ]
