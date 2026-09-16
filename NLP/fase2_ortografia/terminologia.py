"""
Guardián de terminología clínica.

Todo cambio que el corrector quiera aplicar sobre una palabra pasa por aquí
antes de ejecutarse. No es una revisión posterior sobre texto ya alterado: es un
veto que se consulta dentro del ciclo de corrección, tanto desde el motor de
LanguageTool como desde el de SymSpell. Esa es la razón de que sea un módulo
aparte: una regla que solo se aplicara en uno de los dos motores dejaría pasar
el mismo error por el otro.

POR QUÉ EL CRITERIO CLÍNICO MANDA SOBRE EL ORTOGRÁFICO
    El objetivo del proyecto es conservar el motivo de consulta y la
    sintomatología reales. Una corrección que convierte 'monoparesia' en
    'menopausia' no empeora la redacción: inventa un diagnóstico distinto, y
    cualquier análisis posterior agrupará mal ese registro de forma permanente.

QUÉ SE VETA
    1. Antónimos morfológicos    hipo/hiper, bradi/taqui, pre/post. Invierten el
                                 significado con una sola edición.
    2. Truncamientos             quitar un prefijo cambia o niega el hallazgo.
    3. Cambio de morfemas o raíz distinta raíz, distinto órgano.
    4. Cambio de terminación     es concordancia de género o número, no
                                 ortografía.
    5. Nombres de fármaco        la forma rara es el dato; cualquier vecino
                                 ortográfico suyo es otro medicamento.
    6. Abreviaturas de habla     'neuro' o 'gastro' no son errores.
    7. Término contra término    si original y candidato son ambos terminología
                                 reconocida, no hay corrección posible: son dos
                                 conceptos distintos.

QUÉ NO SE VETA
    La restauración de tildes, que nunca cambia el concepto, y los errores de
    digitación que no afectan a terminología.

REPARTO DE RESPONSABILIDADES
    nucleo/morfologia.py  la forma de la palabra: morfemas, antónimos, familias
                          de sufijo, sufijos de fármaco.
    nucleo/reglas.py      el diccionario y las protecciones por contexto.
    alarmas.py            los contadores y sus informes.
    este módulo           la decisión: dado un original y un candidato, se
                          aplica o no.
"""

from NLP.fase2_ortografia import alarmas
from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.nucleo import reglas
from NLP.fase2_ortografia.alarmas import (  # reexportado: procesar.py los llama como terminologia.X
    anotar_abstencion,
    reiniciar_abstenciones,
    reiniciar_alarmas,
    resumen_abstenciones,
    resumen_alarmas,
)
from NLP.nucleo.morfologia import (
    cambia_familia,
    familia_sufijo,
    invierte_significado,
    parece_farmaco,
)

# ==========================================================
# RECONOCIMIENTO DE TERMINOLOGÍA
# ==========================================================

# Un fragmento como 'neuro' no es un error sino una abreviatura de habla
# ('el neuro', 'el gastro', 'el cardio'), y corregirlo borra un concepto
# clinico. Se reconoce porque es el inicio de varias palabras reales del corpus,
# cosa que un error de digitacion no cumple.
PREFIJO_DE_MINIMO = 2     # cuantas palabras del corpus debe iniciar
LONGITUD_ABREVIATURA = 8  # solo se consideran fragmentos mas cortos que esto

_CACHE_ABREVIATURA = {}

# Un token que no pertenece al espanol, no tiene morfemas medicos y no termina
# como un principio activo puede ser igualmente un nombre comercial o jerga del
# servicio. Para esos no hay ninguna forma que los delate, asi que la politica
# es la abstencion: si ninguna correccion reune evidencia clara, el token se
# deja intacto y queda registrado en alarmas.py.


def es_abreviatura(palabra, conteo=None):
    """
    True si la palabra parece un fragmento de otras más largas que el corpus
    usa. 'neuro' encabeza 'neurologo', 'neurologia' y 'neurologico', de modo que
    es una abreviatura; una palabra mal digitada no encabeza ninguna palabra
    real.

    Requiere el recuento de frecuencias del corpus, que toma del motor de
    candidatos si no se le pasa. Sin corpus cargado devuelve False. El resultado
    se guarda en caché porque la comprobación recorre todo el vocabulario.
    """
    palabra = morfologia.normalizar(palabra)
    if len(palabra) < 4 or len(palabra) >= LONGITUD_ABREVIATURA:
        return False

    if conteo is None:
        from NLP.fase2_ortografia import candidatos
        conteo = candidatos.CONTEO
    if not conteo:
        return False

    if palabra in _CACHE_ABREVIATURA:
        return _CACHE_ABREVIATURA[palabra]

    largas = sum(1 for p, n in conteo.items()
                 if n >= 3 and len(p) > len(palabra) + 2 and p.startswith(palabra))
    resultado = largas >= PREFIJO_DE_MINIMO
    _CACHE_ABREVIATURA[palabra] = resultado
    return resultado


def es_terminologia(palabra):
    """
    True si la palabra tiene forma de término clínico: está en el diccionario
    del proyecto, contiene morfemas médicos o termina como un principio activo.
    """
    palabra = morfologia.normalizar(palabra)
    if not palabra:
        return False
    if palabra in reglas.SIGLAS or morfologia.es_termino_medico(palabra):
        return True
    return parece_farmaco(palabra)


def es_terminologia_reconocida(palabra):
    """
    True si, además de tener forma de término, la palabra existe realmente:
    figura en el diccionario del proyecto o en el vocabulario de spaCy.

    La distinción con es_terminologia() es la que separa un término mal escrito
    de uno correcto. 'hipotiroidimo' tiene morfemas médicos pero es un error y
    debe corregirse; 'desaturada' también los tiene y es una palabra real que
    debe respetarse. Lo que las separa no son los morfemas, sino que alguna
    fuente reconozca la forma.
    """
    palabra = morfologia.normalizar(palabra)
    if not palabra:
        return False
    if palabra in reglas.SIGLAS:
        return True
    return linguistica.en_vocabulario(palabra)


# ==========================================================
# VETO
# ==========================================================

# Dos terminos clinicos reconocidos son dos conceptos distintos, no un error y
# su correccion. Se deja como interruptor porque es el veto mas amplio de todos
# y el primero que conviene revisar si alguna vez bloquea correcciones validas.
VETO_TERMINO_CONTRA_TERMINO = True

def validar(original, candidato):
    """
    Decide si una corrección es admisible desde el punto de vista clínico.

    Devuelve (True, "") si la acepta, o (False, motivo) si la veta, dejando
    constancia del veto en el registro de alarmas. Los criterios se evalúan del
    más barato al más costoso, y el primero que se cumple corta la evaluación.

    Es la única puerta: los dos motores de corrección pasan por aquí antes de
    aplicar cualquier cambio.
    """
    original = morfologia.normalizar(original)
    candidato = morfologia.normalizar(candidato)

    if not original or not candidato or original == candidato:
        return True, ""

    # la tilde nunca cambia el concepto
    if morfologia.es_restauracion_tilde(original, candidato):
        return True, ""

    if es_abreviatura(original):
        alarmas.anotar("abreviatura, no error", original, candidato)
        return False, "abreviatura, no error"

    # un nombre de farmaco no se corrige nunca: la forma rara ES el dato, y
    # cualquier vecino ortografico suyo es otro medicamento u otra cosa
    if parece_farmaco(original):
        alarmas.anotar("nombre de farmaco", original, candidato)
        return False, "nombre de farmaco"

    if invierte_significado(original, candidato):
        alarmas.anotar("invierte el significado", original, candidato)
        return False, "invierte el significado"

    if morfologia.es_truncamiento(original, candidato):
        alarmas.anotar("quita o agrega un prefijo", original, candidato)
        return False, "quita o agrega un prefijo"

    if cambia_familia(original, candidato):
        alarmas.anotar("cambia el tipo de hallazgo", original, candidato)
        return False, "cambia el tipo de hallazgo"

    # 'taquicardico' describe como esta el paciente y 'taquicardia' es el
    # diagnostico: el cambio convierte una descripcion en una entidad clinica
    if morfologia.cambia_categoria(original, candidato):
        alarmas.anotar("adjetivo contra sustantivo", original, candidato)
        return False, "adjetivo contra sustantivo"

    if not morfologia.conserva_morfemas(original, candidato):
        alarmas.anotar("no conserva morfemas ni raiz", original, candidato)
        return False, "no conserva morfemas ni raiz"

    if morfologia.es_termino_medico(original) and morfologia.solo_cambia_terminacion(original, candidato):
        alarmas.anotar("solo cambia genero o numero", original, candidato)
        return False, "solo cambia genero o numero"

    # dos terminos reconocidos son dos conceptos distintos: 'desaturada' y
    # 'saturada' no son un error y su correccion, sino dos hallazgos
    if (VETO_TERMINO_CONTRA_TERMINO
            and es_terminologia_reconocida(original)
            and es_terminologia(candidato)):
        alarmas.anotar("ambos son terminos clinicos", original, candidato)
        return False, "ambos son terminos clinicos"

    return True, ""


def admite(original, candidato):
    """Igual que validar(), pero devolviendo solo el veredicto."""
    return validar(original, candidato)[0]


# ==========================================================
# AUDITORÍA
# ==========================================================

def explicar(original, candidato):
    """
    Diagnóstico completo de un par (original, candidato): si se admite, por qué,
    y qué ve el guardián en cada una de las dos palabras. Herramienta de
    inspección manual.

    Advertencia: al llamar a validar(), un par vetado queda contabilizado en el
    registro de alarmas, igual que si lo hubiera producido una corrida.
    """
    ok, motivo = validar(original, candidato)
    return {
        "original": original,
        "candidato": candidato,
        "admitido": ok,
        "motivo": motivo or "sin objecion",
        "original_es_terminologia": es_terminologia(original),
        "original_reconocido": es_terminologia_reconocida(original),
        "candidato_es_terminologia": es_terminologia(candidato),
        "morfemas_original": sorted(morfologia.morfemas(original)),
        "morfemas_candidato": sorted(morfologia.morfemas(candidato)),
        "familia_original": familia_sufijo(original),
        "familia_candidato": familia_sufijo(candidato),
    }
