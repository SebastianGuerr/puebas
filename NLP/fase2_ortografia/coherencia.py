"""
Revisa la nota corregida CONTRA la original y deshace lo que la estropeó.

QUE PROBLEMA RESUELVE, Y POR QUE NO LO RESOLVIA terminologia.py
    `terminologia.admite()` es la puerta por la que pasa cada cambio, y decide
    mirando DOS PALABRAS: la original y la candidata. Con eso atrapa lo que se
    ve en la forma -- un prefijo invertido, un sufijo de otra familia, un
    truncamiento -- y lo hace bien.

    Lo que no puede ver es la nota. Una sustitución puede ser impecable como par
    de palabras y aun así estropear la frase, porque la evidencia de que está
    mal no está en la palabra sino alrededor:

        saliendo de villamaria  -> villamaría     toponimo, no lleva tilde
        sufre impacto en la via -> sobre impacto en la via

    Esta capa llega DESPUES de todas las demas y hace la pregunta que ninguna
    hizo: comparada con la nota que escribio quien atendio al paciente, esta
    correccion mejora el texto o lo cambia.

EL PRINCIPIO ES EL MISMO DEL RESTO DEL PROYECTO
    El coste del error no es simetrico. Dejar una palabra sin corregir cuesta
    poco; cambiarla por otra distinta le inyecta un dato falso al clustering,
    que no tiene forma de saber que es falso. Ante la duda, se deshace el
    cambio y se deja lo que habia escrito.

    Por eso esta capa solo QUITA correcciones. No propone ninguna, no reescribe
    nada y no puede introducir una palabra que no estuviera ya en la nota o en
    la correccion. Su peor resultado posible es dejar el texto como estaba.

DE DONDE SALEN LOS CRITERIOS
    No son nuevos. `evaluacion/auditoria.py` ya sabia reconocer una sustitucion
    dañina -- distancia excesiva, palabra que el español reconoce, original
    mucho mas frecuente que el reemplazo -- pero lo hacia DESPUES de la corrida
    y solo para escribir un informe. El daño ya estaba en el CSV.

    Aqui se aplican los mismos criterios ANTES de escribir, que es donde
    sirven. Los umbrales se conservan identicos para que el informe de
    auditoria siga siendo comparable con lo que esta capa decide.

LO QUE SE DEJA PASAR SIEMPRE, Y POR QUE
    Restaurar una tilde no cambia el concepto: son las mismas letras. Y una
    errata de teclado -- las mismas letras en otro orden, o una de mas o de
    menos -- no puede convertir una palabra en otra que no se le parezca.
    Medido sobre el informe real, 32 de 76 alertas eran de este tipo y todas
    eran correcciones buenas. Sin estas dos salidas, esta capa desharia justo
    lo que mejor funciona.
"""

import difflib
import re

from rapidfuzz.distance import DamerauLevenshtein

from NLP.fase2_ortografia import pesos
from NLP.fase2_ortografia.sugerencias import _es_subsecuencia
from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.nucleo import reglas
from NLP.recursos import casing

# ==========================================================
# CONFIGURACION
# ==========================================================

# Se conservan identicos a evaluacion/auditoria.py a proposito: son los mismos
# criterios medidos sobre el mismo corpus, aplicados antes en vez de despues.
FRACCION_DISTANCIA_MAXIMA = 0.40
FACTOR_FRECUENCIA = 10

# Por debajo de esto no se revisa nada. Las palabras cortas dan distancias
# relativas enormes por un solo caracter y el vocabulario las acepta casi
# todas, asi que ninguna de las dos señales significa nada.
LONGITUD_MINIMA = 4

MOTIVO_ENTIDAD = "nombre propio de la nota original"
MOTIVO_CLINICO = "termino clinico convertido en palabra corriente"
MOTIVO_INVENTADA = "la correccion no es una palabra de ningun diccionario"
MOTIVO_DISTANCIA = "el reemplazo no se parece al original"
MOTIVO_FRECUENCIA = "el original es mucho mas frecuente que el reemplazo"

RE_TOKEN = re.compile(r"\w+|[^\w\s]", re.UNICODE)
RE_PUNTUACION = re.compile(r"^[^\w\s]$", re.UNICODE)


def _tokenizar(texto):
    return RE_TOKEN.findall(str(texto or ""))


def _es_errata_de_teclado(original, candidato):
    """
    True si el par es una errata de digitación y no un cambio de palabra.

    Son las mismas letras en otro orden ('ahce' -> 'hace') o una sola edición
    ('door' -> 'dolor'). Ninguna de las dos puede llegar a una palabra que no se
    parezca al original, que es lo único que esta capa busca.
    """
    o = morfologia.sin_tildes(original.lower())
    c = morfologia.sin_tildes(candidato.lower())
    if sorted(o) == sorted(c):
        return True
    return DamerauLevenshtein.distance(o, c) <= 1


def _es_clinica(palabra):
    """
    True si la palabra es terminología clínica.

    Se preguntan las dos vías porque cubren cosas distintas y ninguna sola
    basta: el léxico curado conoce 'colico' y 'cefalea', que no tienen morfema
    médico reconocible, y la morfología reconoce 'losartan' y 'dutasteride',
    que son principios activos y no están en ningún catálogo de síntomas.
    """
    from NLP.depuracion import depuracion

    p = morfologia.normalizar(palabra)
    return (depuracion.es_clinica(p)
            or morfologia.es_termino_medico(p)
            or morfologia.parece_farmaco(p)
            or p in reglas.SIGLAS)


def _tiene_respaldo(palabra):
    """
    True si la palabra original era algo antes de que la corrigieran: una
    palabra del español, terminología clínica o un nombre declarado.

    Es la condición que separa proteger de estorbar. Revertir devuelve el
    original, así que solo tiene sentido cuando el original era mejor que la
    corrección; si tampoco era una palabra, la reversión no arregla nada.
    """
    return (linguistica.en_vocabulario(palabra)
            or reglas.es_palabra_conocida(palabra)
            or _es_clinica(palabra))


def nombres_del_corpus():
    """
    Nombres propios y siglas que el corpus conoce, en minúscula.

    ES LA FUENTE DE NOMBRES PROPIOS, Y NO EL RECONOCEDOR DE ENTIDADES
        La primera versión de esta capa vetaba cualquier corrección sobre una
        palabra que spaCy marcara como entidad, y deshacía correcciones buenas:
        sobre 'door de cabeza fibre alta' marcaba 'door' y 'fibre' como nombres
        propios y revertía las dos, que eran justo las erratas que había que
        arreglar.

        No es un fallo de spaCy sino de la pregunta: un reconocedor mira UNA
        nota corta, y estas notas van en mayúsculas y mal escritas, que es el
        peor terreno posible. `lexico_casing.json` sale de contar 94.136 notas,
        así que 'manizales' figura y 'door' no. Es la misma jerarquía que ya
        declara reglas.entidades(): lo que el corpus sabe pesa más que lo que
        el reconocedor opina de una nota suelta.
    """
    if not casing.disponible():
        casing.cargar()
    if not casing.disponible():
        return set()
    return casing.nombres_propios() | casing.siglas()


def juzgar(original, candidato, entidades=(), frecuencia=None):
    """
    Por qué esta sustitución concreta estropea la nota, o None si no lo hace.

    `entidades` son los nombres propios y siglas que el corpus conoce; se
    inyectan para no releer el léxico en cada palabra. `frecuencia` se inyecta
    para poder probar esta función sin cargar el corpus.
    """
    o = morfologia.normalizar(original)
    c = morfologia.normalizar(candidato)
    if not o or not c or o == c or len(o) < LONGITUD_MINIMA:
        return None

    # la tilde nunca cambia el concepto: son las mismas letras
    if morfologia.es_restauracion_tilde(o, c):
        return None

    # AÑADIR LETRAS NO DESTRUYE NADA, Y LO PARECIA
    #
    # Va antes que todo lo demas porque si no, las reglas de abajo lo tapan.
    # Medido: 'hipotirodismo' -> 'hipotiroidismo' salia como nombre propio
    # (el lexico de capitalizacion habia aprendido el typo), 'febrila' ->
    # 'febricula' y 'caidaen' -> 'caida en' salian como perdida de terminologia.
    # Las tres eran correcciones buenas.
    #
    # El criterio es el de sugerencias.py, que es quien las propone: una
    # abreviatura o un typo por letra omitida aparece completo y en orden
    # dentro de la forma larga. Si se revierte aqui lo que alli se propuso, las
    # dos capas se anulan y el corrector no arregla nada.
    if len(c) > len(o) and _es_subsecuencia(morfologia.sin_tildes(o),
                                            morfologia.sin_tildes(c)):
        return None

    # Un nombre propio declarado no se corrige jamas, y va ANTES de la salida
    # por errata de teclado a proposito: 'dorada' -> 'morada' es una sola
    # edicion y aun asi destruye un municipio. Lo que lo salva es que el corpus
    # tenga el nombre declarado, no que la distancia sea corta.
    if o in entidades:
        return MOTIVO_ENTIDAD

    # Perder terminologia clinica es el daño mas caro para el clustering, asi
    # que se mira ANTES que la errata de teclado. El orden importa: 'colico' ->
    # 'comico' es una sola edicion, pasaria como errata, y deja de ser clinico.
    if _es_clinica(o) and not _es_clinica(c):
        return MOTIVO_CLINICO

    if _es_errata_de_teclado(o, c):
        return None

    # SOLO SE REVIERTE LO QUE TENIA ALGO QUE PERDER
    #
    # Las dos reglas que quedan comparan la correccion con el original, y eso
    # solo significa algo si el original valia. Medido sobre el corpus, sin
    # esta condicion se revertian 'deposion' -> 'deposicion', 'luxo' ->
    # 'luxacion' y 'cervibraquial' -> 'cervicobraquial', que son correcciones
    # buenas: el original no es una palabra, asi que devolverlo no recupera
    # nada, solo cambia un error por otro y ademas pierde el arreglo.
    if not _tiene_respaldo(o):
        return None

    # una correccion que produce algo que no esta en ningun diccionario no ha
    # corregido nada: ha cambiado una palabra buena por un error
    if (len(c) >= LONGITUD_MINIMA
            and not linguistica.en_vocabulario(c)
            and not reglas.es_palabra_conocida(c)
            and not _es_clinica(c)):
        return MOTIVO_INVENTADA

    limite = max(1, int(len(o) * FRACCION_DISTANCIA_MAXIMA))
    if DamerauLevenshtein.distance(o, c.replace(" ", "")) > limite:
        return MOTIVO_DISTANCIA

    if frecuencia:
        f_o, f_c = frecuencia(o), frecuencia(c)
        if f_o and f_o >= FACTOR_FRECUENCIA * max(f_c, 1):
            return MOTIVO_FRECUENCIA

    return None


def revisar(limpio, corregido, original=None, frecuencia=None):
    """
    Deshace las correcciones que no se sostienen al comparar con la nota.

    Devuelve (texto, incidencias). `texto` es el corregido con las
    sustituciones dañinas revertidas a como estaban en `limpio`. `incidencias`
    es la lista de (original, reemplazo, motivo), para el informe.

    `original` se acepta por simetría con el resto de la fase, pero esta capa
    no lo necesita: los nombres propios salen del corpus, no de leer esta nota.
    Ver nombres_del_corpus() para por qué.
    """
    if not corregido or limpio == corregido:
        return corregido, []

    entidades = nombres_del_corpus()
    if frecuencia is None:
        frecuencia = pesos.frecuencia

    antes, despues = _tokenizar(limpio), _tokenizar(corregido)
    salida, incidencias = [], []

    cotejo = difflib.SequenceMatcher(a=[t.lower() for t in antes],
                                     b=[t.lower() for t in despues])
    for etiqueta, i1, i2, j1, j2 in cotejo.get_opcodes():
        if etiqueta in ("equal", "insert"):
            salida.extend(despues[j1:j2])
            continue
        if etiqueta == "delete":
            # el corrector quito tokens. No se restauran: quitar no inventa
            # ninguna palabra, que es lo unico que esta capa persigue
            continue

        # replace: el unico caso en que una palabra se convirtio en otra
        viejo, nuevo = antes[i1:i2], despues[j1:j2]
        if len(viejo) == 1:
            reemplazo = " ".join(nuevo)
            motivo = juzgar(viejo[0], reemplazo, entidades, frecuencia)
            if motivo:
                incidencias.append((viejo[0], reemplazo, motivo))
                salida.extend(viejo)
                continue
        salida.extend(nuevo)

    return _rearmar(salida), incidencias


def _rearmar(tokens):
    """
    Vuelve a unir los tokens dejando la puntuación pegada a la palabra anterior.

    Se rearma en vez de sustituir sobre el texto corregido porque los tramos
    revertidos vienen de dos cadenas distintas y no comparten posiciones.
    """
    partes = []
    for t in tokens:
        if partes and RE_PUNTUACION.match(t) and t not in "¿¡([{":
            partes[-1] += t
        else:
            partes.append(t)
    return " ".join(partes).strip()


def sin_corregir(corregido):
    """
    Palabras que quedaron igual y que no reconoce ningún diccionario.

    No se tocan -- que nadie conozca una palabra no demuestra que esté mal
    escrita -- pero son exactamente las candidatas a entrar en el diccionario, y
    son la otra mitad de la queja: no solo 'me cambió el sentido', también 'no
    me corrigió nada'.
    """
    quedaron, vistos = [], set()
    for t in _tokenizar(corregido):
        p = morfologia.normalizar(t)
        if len(p) < LONGITUD_MINIMA or p in vistos or morfologia.tiene_numero(p):
            continue
        vistos.add(p)
        if (not linguistica.en_vocabulario(p)
                and not reglas.es_palabra_conocida(p)
                and not _es_clinica(p)):
            quedaron.append(p)
    return quedaron
