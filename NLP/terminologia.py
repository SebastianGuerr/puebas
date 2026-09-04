"""
Guardian de terminologia clinica.

Todo cambio que el pipeline quiera hacer sobre una palabra pasa por aqui ANTES
de aplicarse. No es una etapa posterior que recibe texto ya alterado: es un veto
que se consulta dentro del ciclo de correccion, tanto desde candidatos.py
(LanguageTool) como desde vocabulario.py (SymSpell).

POR QUE ESTA SEPARADO
    El objetivo del proyecto es conservar el motivo de consulta y la
    sintomatologia reales, expresados en terminologia clinica. Una correccion
    ortografica que convierte 'monoparesia' en 'menopausia' no degrada el texto:
    inventa un diagnostico distinto, y cualquier clustering posterior agrupara
    mal ese registro para siempre. Por eso el criterio medico manda sobre el
    criterio ortografico, y no al reves.

QUE VETA
    1. Antonimos morfologicos ... hipo/hiper, bradi/taqui, hemo/neumo, pre/post.
                                  Invierten el significado con una sola edicion.
    2. Truncamientos ............ defocalizacion -> focalizacion. Quitar un
                                  prefijo cambia o niega el hallazgo.
    3. Cambio de morfemas ....... monoparesia -> menopausia, glosectomia ->
                                  lobectomia. Distinta raiz, distinto organo.
    4. Cambio de terminacion .... hipoactiva -> hipoactivo. Concordancia, no
                                  ortografia.
    5. Termino contra termino ... si original y candidato son ambos terminos
                                  clinicos reconocidos, no hay correccion
                                  posible: son dos conceptos distintos.

QUE NO VETA
    La restauracion de tildes, que nunca cambia el concepto, y los typos que no
    tocan terminologia ('pacinete' -> 'paciente').

REGISTRO
    Cada veto queda anotado en alarmas.py, que lleva las dos cuentas: los
    cambios frenados por una regla y las palabras dejadas intactas por falta de
    evidencia. resumen_alarmas() y resumen_abstenciones() se reexportan aca
    para que procesar.py las siga llamando como terminologia.X.

DONDE VIVE CADA COSA
    morfologia.py  la forma de la palabra: morfemas, antonimos, familias de
                   sufijo, sufijos de farmaco. No sabe de este proyecto.
    reglas.py      el diccionario y las protecciones por contexto.
    alarmas.py     los contadores y sus informes.
    este archivo   la decision: dado un original y un candidato, se aplica o no.
"""

import alarmas
import linguistica
import morfologia
import reglas
from alarmas import (  # reexportado: procesar.py los llama como terminologia.X
    anotar_abstencion,
    reiniciar_abstenciones,
    reiniciar_alarmas,
    resumen_abstenciones,
    resumen_alarmas,
)
from morfologia import (
    cambia_familia,
    familia_sufijo,
    invierte_significado,
    parece_farmaco,
    prefijos,
)

# ==========================================================
# RECONOCIMIENTO DE TERMINOLOGIA
# ==========================================================

# Un fragmento como 'neuro' no es un error: es una abreviatura de habla
# ('el neuro', 'el gastro', 'el cardio'). Corregirlo produce 'negro' y borra un
# concepto clinico. Se reconoce porque es el inicio de varias palabras reales
# del corpus, cosa que un typo no cumple.
PREFIJO_DE_MINIMO = 2     # cuantas palabras del corpus debe iniciar
LONGITUD_ABREVIATURA = 8  # solo se consideran fragmentos mas cortos que esto

_CACHE_ABREVIATURA = {}

# Un token que no pertenece al espanol, no tiene morfemas medicos y no termina
# como un principio activo puede ser igualmente un nombre comercial (Biogaia,
# Dolex, Noraver) o una jerga del servicio. Para esos no hay forma que los
# delate, asi que la politica es la abstencion: si ninguna correccion reune
# evidencia clara, el token se deja como esta y queda anotado en alarmas.py.


def es_abreviatura(palabra, conteo=None):
    """
    True si la palabra parece un fragmento de otra mas larga que el corpus usa.
    'neuro' inicia 'neurologo', 'neurologia', 'neurologico': es una abreviatura.
    'pacinete' no inicia ninguna palabra real: es un typo.
    """
    palabra = morfologia.normalizar(palabra)
    if len(palabra) < 4 or len(palabra) >= LONGITUD_ABREVIATURA:
        return False

    if conteo is None:
        import candidatos
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
    """True si la palabra tiene forma de termino clinico (morfemas o diccionario)."""
    palabra = morfologia.normalizar(palabra)
    if not palabra:
        return False
    if palabra in reglas.SIGLAS or morfologia.es_termino_medico(palabra):
        return True
    return parece_farmaco(palabra)


def es_terminologia_reconocida(palabra):
    """
    True si ademas de tener forma de termino, la palabra existe: esta en el
    diccionario del proyecto o en el vocabulario de spaCy.

    La distincion importa. 'hipotiroidimo' tiene morfemas medicos pero es un
    error de digitacion y debe corregirse; 'desaturada' tambien los tiene y es
    una palabra real que debe respetarse. Lo que las separa no son los morfemas
    sino el reconocimiento.
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

# Dos terminos clinicos reconocidos son dos conceptos, no un error y su
# correccion. Se deja como interruptor porque es el veto mas amplio de todos y
# el primero que hay que apagar si alguna vez bloquea correcciones legitimas.
VETO_TERMINO_CONTRA_TERMINO = True

def validar(original, candidato):
    """
    Decide si una correccion es admisible desde el punto de vista clinico.
    Devuelve (True, "") si pasa, o (False, motivo) si el guardian la veta.

    Es la unica puerta: candidatos.py y vocabulario.py llaman aqui antes de
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

    # 'taquicardico' (como esta el paciente) -> 'taquicardia' (el diagnostico).
    # Es el caso que se aplico 22 veces en la corrida de 30.000: convierte una
    # descripcion clinica en una entidad clinica distinta.
    if morfologia.cambia_categoria(original, candidato):
        alarmas.anotar("adjetivo contra sustantivo", original, candidato)
        return False, "adjetivo contra sustantivo"

    if not morfologia.conserva_morfemas(original, candidato):
        alarmas.anotar("no conserva morfemas ni raiz", original, candidato)
        return False, "no conserva morfemas ni raiz"

    if morfologia.es_termino_medico(original) and morfologia.solo_cambia_terminacion(original, candidato):
        alarmas.anotar("solo cambia genero o numero", original, candidato)
        return False, "solo cambia genero o numero"

    # dos terminos clinicos reconocidos son dos conceptos, no un error y su
    # correccion: 'desaturada' y 'saturada', 'presincope' y 'sincope'
    if (VETO_TERMINO_CONTRA_TERMINO
            and es_terminologia_reconocida(original)
            and es_terminologia(candidato)):
        alarmas.anotar("ambos son terminos clinicos", original, candidato)
        return False, "ambos son terminos clinicos"

    return True, ""


def admite(original, candidato):
    return validar(original, candidato)[0]


# ==========================================================
# AUDITORIA
# ==========================================================

def explicar(original, candidato):
    """Diagnostico de un par concreto. Para revisar casos puntuales."""
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
