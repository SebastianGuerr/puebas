"""
Depuración: separar las notas que dicen algo de las que no.

QUÉ PROBLEMA RESUELVE
    No todas las notas de triage hablan del paciente. Una parte del corpus son
    plantillas contestadas en blanco, trámite puro o un fragmento suelto que no
    dice a qué vino nadie.

    Para el agrupamiento posterior eso no es solo peso muerto: son notas casi
    idénticas entre sí y ajenas a cualquier cuadro clínico, de modo que forman
    grupos propios que no significan nada y ensucian los que sí.

EL CRITERIO, Y POR QUÉ ESTA FASE VA LA ÚLTIMA
    Una nota se descarta cuando, después de corregir, normalizar y recortar, no
    queda en ella ni un solo término del léxico clínico curado.

    El orden no es un detalle de implementación: es la diferencia entre medir la
    nota y medir el diccionario. Aplicado antes de la normalización, este mismo
    criterio descartaba miles de notas que sí tenían contenido, como las que
    describen una caída en lenguaje corriente o las que usan una sigla que el
    diccionario ya sabe traducir. Ninguna de ellas estaba vacía: eran huecos de
    vocabulario, y descartarlas habría sido borrar la evidencia del problema en
    lugar de resolverlo.

    De ahí la regla: este módulo solo puede ejecutarse cuando ya se aplicó todo
    lo que el proyecto sabe traducir.

QUÉ SE DESCARTA Y QUÉ NO
    Ante la duda se conserva. Una nota descartada no vuelve, y el coste de
    arrastrar algo de ruido es mucho menor que el de perder un motivo de
    consulta real. Por eso el trámite solo descarta cuando además no hay nada
    clínico: una nota que solo dice cómo llegó el paciente se va, pero la que
    dice cómo llegó y por qué se conserva entera.

NADA SE DESCARTA EN SILENCIO
    evaluar() devuelve siempre el motivo, y el orquestador escribe todas las
    notas descartadas con su motivo. Revisar ese archivo es la forma de
    descubrir el siguiente hueco de diccionario: si ahí aparece una expresión
    clínica repetida, no es ruido, es una entrada que falta.
"""

import json
import re

from NLP import rutas
from NLP.nucleo import morfologia
from NLP.recursos import lexico

# ==========================================================
# QUE CUENTA COMO TERMINO CLINICO
# ==========================================================

# Solo las fuentes curadas del lexico. El vocabulario del modelo biomedico
# queda fuera a proposito: contiene el espanol corriente entero, y con el hasta
# un aviso administrativo pareceria lleno de terminologia clinica. Es la misma
# decision que toma embedding/recorte.py, y por la misma razon.
FUENTES_CURADAS = (lexico.DICCIONARIO, lexico.CATALOGO, lexico.EXTERNO)

RE_PALABRA = re.compile(r"[^\W\d_]+", re.UNICODE)

# Palabras que no son contenido. Solo deciden si lo que queda vale la pena;
# nunca se borran del texto.
VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "a", "al", "en", "con", "sin", "por", "para", "que", "se", "su",
    "sus", "lo", "le", "les", "es", "esta", "este", "esto", "muy", "mas",
    "ni", "pero", "ya", "aun", "aca", "alla", "ahi", "hoy", "ayer", "manana",
    "paciente", "usuario", "usuaria", "senor", "senora", "ahora", "momento",
    "cual", "quien", "ademas", "tipo", "toda", "todo", "ser", "han", "ha",
    "he", "hace", "desde", "hasta", "sobre", "entre", "cuando", "donde",
    "refiere", "manifiesta", "presenta", "indica", "comenta", "dice",
}

# Lo que queda de una plantilla contestada en blanco. Si al quitar los
# encabezados la nota solo tiene esto, es un formulario sin las preguntas.
RESPUESTAS_VACIAS = {
    "niega", "niegan", "ninguno", "ninguna", "nada", "nono", "no",
    "negativo", "negativa", "normal", "normales", "asintomatico",
    "asintomatica", "aplica", "sano", "sana", "bien", "estable",
}

# ==========================================================
# LAS DOS LISTAS QUE EL LEXICO NO PUEDE DAR
# ==========================================================
#
# Saber que una palabra es terminologia no basta, porque el CIE-10 no
# distingue el nombre de un sintoma del de una region anatomica ni del espanol
# corriente que arrastra en sus rubricas. Frases como 'consulta externa' o una
# parte del cuerpo suelta pasan el filtro con terminologia reconocida y son
# ruido, asi que esa distincion hay que ponerla aqui.
#
# Las dos listas son cortas y cerradas a proposito: enumeran los dos casos en
# que coincidir con el lexico no es evidencia de contenido clinico, y no
# pretenden cubrir el vocabulario administrativo del hospital.

# Palabras del recorrido por el sistema. No son motivo de consulta aunque el
# CIE-10 las contenga.
PALABRAS_TRAMITE = {
    "cita", "citada", "citado", "citaron", "citar", "prioritaria",
    "prioritario", "reconsulta", "remision", "remitieron", "remitida",
    "remitido", "remiten", "remite", "remitir", "derivada", "derivado",
    "derivaron", "derivan", "deriva", "enviada", "enviado", "enviaron",
    "envian", "envio", "mandaron", "mandan", "eps", "ips", "hospitalizar",
    "hospitalizacion", "urgencia", "urgencias", "consulta", "externa",
    "control", "valoracion", "orden", "ordenada", "ordenado", "autorizacion",
    "formula", "incapacidad", "certificado", "emi", "ger", "ambulancia",
    "camilla", "traslado", "trasladada", "trasladado", "vital", "vitales",
    "servicio", "atencion", "nivel", "afiliada", "afiliado", "venir",
    "viniera", "vengo", "vine", "dijeron", "acompanante", "trae", "traida",
    "traido", "reingreso", "reemitieron", "reemitidos", "devolvieron",
    "aceptada", "aceptado", "aceptados",
}

# Regiones anatomicas. Nombrar una parte del cuerpo no dice a que vino nadie:
# puede ser un golpe, una artrosis o una herida. Solo descartan cuando son lo
# UNICO clinico de la nota; acompanadas de un sintoma, la nota se conserva
# entera porque el contenido lo pone el sintoma.
PALABRAS_ANATOMIA = {
    "cabeza", "cara", "frente", "ojo", "ojos", "oido", "oidos", "oreja",
    "nariz", "boca", "diente", "dientes", "muela", "lengua", "garganta",
    "cuello", "nuca", "hombro", "hombros", "brazo", "brazos", "codo",
    "antebrazo", "muneca", "mano", "manos", "dedo", "dedos", "pecho",
    "torax", "espalda", "columna", "cintura", "abdomen", "barriga",
    "estomago", "ombligo", "cadera", "pelvis", "pierna", "piernas", "muslo",
    "rodilla", "rodillas", "pantorrilla", "tobillo", "pie", "pies", "talon",
    "gluteo", "gluteos", "costado", "costilla", "costillas", "axila",
    "ingle", "genitales", "seno", "senos", "piel", "cuerpo", "extremidad",
    "extremidades", "miembro", "miembros", "hueso", "huesos", "musculo",
}

# Palabras de tiempo. CUANDO ocurrio algo no es POR QUE vino el paciente, y el
# tiempo de evolucion ya viaja como dato estructurado.
#
# Es el tercer caso de lo mismo, y por eso hay tres listas y no una: el CIE-10
# contiene 'semana', 'pasada' y 'pasado' en sus rubricas, de modo que
#
#     'la semana pasada me hospitalizar y el viernes pasado sali'
#
# daba tres 'terminos clinicos' -- semana, pasada, pasado -- y salia del
# pipeline como si fuera un motivo de consulta. No dice ni un sintoma: cuenta un
# ingreso anterior.
PALABRAS_TIEMPO = {
    "dia", "dias", "semana", "semanas", "mes", "meses", "ano", "anos",
    "hora", "horas", "minuto", "minutos", "rato", "noche", "noches",
    "madrugada", "tarde", "manana", "anoche", "antier", "antenoche",
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
    "pasado", "pasada", "pasados", "pasadas", "reciente", "recientemente",
    "actual", "actualmente", "previo", "previa", "anterior", "ultimo",
    "ultima", "fin", "principios", "mediados", "finales", "hace", "desde",
    "aproximadamente", "aprox",
}

# Numero minimo de palabras con contenido para conservar una nota que no tiene
# terminologia reconocida. Es la valvula de escape del criterio: una nota larga
# escrita en lenguaje corriente puede no contener ni un termino del lexico y ser
# un motivo de consulta perfectamente legible. El corte esta alto a proposito,
# porque por debajo caen los fragmentos sueltos, que es lo que se descarta.
PALABRAS_PARA_SALVAR = 8


def _plegar(palabra):
    """Misma clave de comparación que usa el léxico: minúsculas y sin tildes."""
    return morfologia.sin_tildes(str(palabra).lower().strip())


# Encabezado del formulario, con la expansion que le pone la fase 3:
# 'ap:', 'mc (motivo de consulta):'. Se quita ANTES de juzgar la nota.
#
# POR QUE, CON EL NUMERO
#     La fase 3 expande el rotulo del apartado, y esa expansion es terminologia
#     clinica de pleno derecho: 'antecedentes', 'alergicos', 'patologicos'.
#     Medido, eso hacia que las 296 notas que dicen exactamente
#
#         'ap (antecedentes personales): niega; aa (antecedentes alergicos): niega'
#
#     contaran como notas con contenido clinico. Y son justo lo contrario: una
#     plantilla contestada en blanco, sin una sola palabra sobre el paciente.
#     El rotulo del formulario lo escribio el formulario, no quien atendio.
RE_ENCABEZADO = re.compile(
    r"\b[a-z]{2,6}\s*(?:\([^)]{3,60}\))?\s*:", re.IGNORECASE)


def sin_encabezados(texto):
    """La nota sin los rotulos del formulario ni su expansion."""
    return RE_ENCABEZADO.sub(" ", str(texto))


# ==========================================================
# LOS APARTADOS QUE NO SON MOTIVO DE CONSULTA
# ==========================================================
#
# Quitar el rotulo no basta: hay que quitar tambien lo que el rotulo contiene.
#
#     'ap (antecedentes personales): hta (hipertension arterial); aa: niega'
#
# Sin los rotulos queda 'hta (hipertension arterial); niega', que es
# terminologia clinica legitima, asi que la nota se conservaba. Y no dice a que
# vino el paciente: dice que es hipertenso. Son cosas distintas. La
# hipertension es un antecedente, y no se sabe ni por que consulto ni por que
# se genero. Para agrupar motivos de consulta, eso es ruido.
#
# La lista de apartados no la inventa este modulo: la declara nucleo/clinico.py,
# que ya la mantiene para cortar el alcance de la negacion. Se importa la tabla,
# no el pipeline, de modo que esto no carga spaCy ni medspaCy.

def _tabla_apartados():
    """
    Las formas escritas de cada apartado y si es o no motivo de consulta, segun
    la tabla de nucleo/clinico.py. Devuelve {forma plegada: es_no_clinico}.

    Se importa la tabla, no el pipeline: nucleo/clinico.py carga spaCy de forma
    perezosa, asi que leer SECCIONES no arrastra el modelo.
    """
    from NLP.nucleo import clinico

    tabla = {}
    for categoria, escrituras in clinico.SECCIONES.items():
        no_clinico = categoria in clinico.SECCIONES_NO_CLINICAS
        for escritura in escrituras:
            tabla[_plegar(escritura)] = no_clinico
    return tabla


_APARTADOS = None
_RE_APARTADO = None

# Longitud a partir de la cual un rotulo se reconoce SIN los dos puntos.
#
# EL FALLO QUE OBLIGA A DISTINGUIR, CON EL NUMERO
#     Un apartado termina donde empieza el siguiente, y el siguiente se
#     detectaba solo por los dos puntos. Pero el corpus escribe muchisimas veces
#
#         'ap: niega; aa: niega; motivo de consulta hace 10 dias me cai'
#
#     con el ultimo rotulo SIN dos puntos. Sin reconocerlo, el apartado de
#     alergicos se extiende hasta el final y se traga el motivo de consulta.
#     Medido: 287 notas con un motivo perfectamente legible se descartaban asi.
#
#     Lo contrario tampoco vale: aceptar cualquier rotulo sin dos puntos haria
#     que 'af' o 'ax' cortaran dentro de una palabra corriente. Por eso los
#     rotulos largos ('motivo de consulta') se reconocen sueltos y los cortos
#     ('ap', 'aa', 'mc') siguen exigiendo los dos puntos: un rotulo de tres
#     palabras no aparece por casualidad, uno de dos letras si.
LONGITUD_ROTULO_SIN_DOSPUNTOS = 8


def _re_apartado():
    """
    Patron que reconoce el arranque de cualquier apartado declarado. Se
    construye desde la tabla, ordenando de mas largo a mas corto para que gane
    la coincidencia mas especifica ('mc (motivo de consulta)' sobre 'mc').
    """
    global _APARTADOS, _RE_APARTADO
    if _RE_APARTADO is not None:
        return _RE_APARTADO

    _APARTADOS = _tabla_apartados()
    largos, cortos = [], []
    for forma in sorted(_APARTADOS, key=len, reverse=True):
        (largos if len(forma) >= LONGITUD_ROTULO_SIN_DOSPUNTOS else cortos).append(
            re.escape(forma))

    # el rotulo puede traer la expansion entre parentesis que le pone la fase 3
    expansion = r"\s*(?:\([^)]{3,60}\))?\s*"
    alternativas = []
    if largos:
        alternativas.append(r"(?P<largo>%s)%s:?" % ("|".join(largos), expansion))
    if cortos:
        alternativas.append(r"(?P<corto>%s)%s:" % ("|".join(cortos), expansion))

    _RE_APARTADO = re.compile(r"\b(?:%s)" % "|".join(alternativas), re.IGNORECASE)
    return _RE_APARTADO


def sin_apartados_no_clinicos(texto):
    """
    La nota sin los apartados que no son motivo de consulta: antecedentes
    personales, alergicos, familiares, quirurgicos y toxicos, medicamentos,
    ocupacion y fuente de la historia.

    Lo que va ANTES del primer rotulo se conserva siempre: en triage la nota
    tipica es texto corrido sin estructura, y ese tramo es el motivo de consulta.
    """
    patron = _re_apartado()
    texto = str(texto)

    marcas = []
    for m in patron.finditer(texto):
        rotulo = m.group("largo") or m.group("corto")
        marcas.append((m.start(), m.end(), _plegar(rotulo)))
    if not marcas:
        return texto

    partes = [texto[:marcas[0][0]]]
    for i, (_ini, fin, rotulo) in enumerate(marcas):
        siguiente = marcas[i + 1][0] if i + 1 < len(marcas) else len(texto)
        if not _APARTADOS.get(rotulo, False):
            partes.append(texto[fin:siguiente])
    return " ".join(partes)


def con_contenido(texto):
    """
    Palabras del texto que aportan significado, ya plegadas y sin las vacías ni
    las muy cortas. Es la base de todas las decisiones del módulo.
    """
    return [p for p in (_plegar(w) for w in RE_PALABRA.findall(sin_encabezados(texto)))
            if p not in VACIAS and len(p) >= 3]


# ==========================================================
# EL INDICE DE EVIDENCIA CLINICA
# ==========================================================
#
# POR QUE NO BASTA CON PREGUNTARLE AL LEXICO
#     El lexico clinico se construye para el corrector ortografico: guarda
#     formas base y descarta las palabras de menos de cuatro letras, porque a
#     dos ediciones de una palabra de tres letras hay medio diccionario. Es la
#     decision correcta ahi y la equivocada aqui. Medido, consultarlo por
#     igualdad exacta descartaba
#
#         136 notas que dicen 'tos'      que no entra por tener 3 letras
#          23 notas 'tengo colicos'      el lexico tiene 'colico', no el plural
#          17 notas 'convulsiono'        tiene 'convulsion', no la forma verbal
#           8 notas 'esta vomitando'     tiene 'vomito', no el gerundio
#
#     Las cuatro son motivos de consulta perfectamente claros. El problema no
#     es el lexico: preguntarle por igualdad responde 'esta escrita asi en el
#     CIE-10', y lo que hace falta saber aqui es 'habla de algo clinico'.
#
# COMO SE RESUELVE
#     Se indexa la RAIZ morfologica de cada termino curado, con el mismo
#     stemmer que ya usa embedding/extraccion.py para lo mismo. 'vomitando' y
#     'vomito' comparten la raiz 'vomit', y una sola entrada cubre la familia
#     entera sin enumerar conjugaciones.
#
#     El catalogo de sintomas se lee ademas por separado y sin minimo de
#     longitud, porque es la fuente que declara que 'tos' es un sintoma.
#
# EL RIESGO DE LA RAIZ, Y COMO SE ACOTA
#     Truncar aumenta las coincidencias, tambien las falsas: 'consulta' y
#     'consultar' comparten raiz, y 'consulta' esta en el CIE-10. Por eso las
#     raices de tramite y de anatomia se restan del indice al CONSTRUIRLO, no
#     al consultarlo: si una raiz es ambigua entre las dos poblaciones, no
#     cuenta como evidencia clinica.

LONGITUD_MINIMA_RAIZ = 3   # por debajo, truncar deja de discriminar

_RAICES = None       # raices de los terminos curados, ya restado lo ambiguo
_FRASES = None       # variantes del catalogo de varias palabras
_STEMMER = None


def _stem(palabra):
    """Raiz morfologica, o la palabra tal cual si nltk no esta instalado."""
    return _STEMMER.stem(palabra) if _STEMMER is not None else palabra


def _del_catalogo():
    """
    Variantes declaradas en el catalogo de sintomas: la fuente que dice que
    'tos' es un sintoma y que 'me falta el aire' es disnea. Se lee de aqui y no
    del lexico porque el lexico les aplica el minimo de cuatro letras.

    Devuelve la pareja (palabras sueltas, expresiones de varias palabras).
    """
    ruta = rutas.CATALOGO_SINTOMAS
    if not ruta.exists():
        return set(), set()

    catalogo = json.loads(ruta.read_text(encoding="utf-8"))
    sueltas, frases = set(), set()
    for concepto, datos in catalogo.get("sintomas", {}).items():
        variantes = datos.get("variantes", ()) if isinstance(datos, dict) else ()
        for forma in [concepto, *variantes]:
            plano = _plegar(forma)
            (frases if " " in plano else sueltas).add(plano)
    return sueltas, frases


def _lugares():
    """
    Municipios declarados en el grupo 'geografia' del diccionario de siglas.
    Se lee del mismo sitio que NLP/reduccion, para que ampliar una entrada
    arregle las dos cosas a la vez.
    """
    ruta = rutas.DICCIONARIO_SIGLAS
    if not ruta.exists():
        return set()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {_plegar(x) for x in datos.get("geografia", {})}


def cargar():
    """
    Construye el indice de evidencia clinica y devuelve cuantas raices quedaron.

    Es idempotente y perezoso: lo llama la primera consulta, de modo que
    importar el modulo no cuesta nada.
    """
    global _RAICES, _FRASES, _STEMMER
    if _RAICES is not None:
        return len(_RAICES)

    try:
        from nltk.stem import SnowballStemmer
        _STEMMER = SnowballStemmer("spanish")
    except ModuleNotFoundError:
        # sin nltk se compara por igualdad: peor cobertura, no incorrecto
        print("Aviso: nltk no instalado; la depuracion no cubrira formas verbales.")
        _STEMMER = None

    sueltas, _FRASES = _del_catalogo()

    # terminos del lexico curado: el CIE-10 y el diccionario del proyecto
    if lexico.disponible():
        for termino in lexico.terminos():
            if " " not in termino and lexico.fuente(termino) in FUENTES_CURADAS:
                sueltas.add(termino)

    # lo que no es evidencia clinica se resta ANTES de indexar
    # Los toponimos tampoco son evidencia clinica. Sin restarlos, 'remitido de
    # viterbo' se conservaba porque el municipio esta en el lexico como entrada
    # del diccionario, y luego la reduccion lo dejaba en texto vacio: la nota
    # sobrevivia sin decir nada. La lista es la misma que usa la reduccion.
    # Entre lo excluido van tambien las palabras de la fuente NO_CLINICO:
    # municipios, instituciones y vocabulario administrativo.
    #
    # No basta con filtrarlas por fuente al recorrer el lexico, porque este
    # indice va por RAIZ y una misma raiz la puede aportar otra palabra.
    # 'hospital' seguia dentro aunque su fuente ya fuera no_clinico, y con ella
    # 'remitida del hospital santa sofia' seguia contando como clinica.
    no_clinicas = set()
    if lexico.disponible():
        no_clinicas = {t for t in lexico.terminos()
                       if lexico.fuente(t) == lexico.NO_CLINICO}

    excluidas = {_stem(p) for p in
                 PALABRAS_TRAMITE | PALABRAS_ANATOMIA | PALABRAS_TIEMPO
                 | VACIAS | _lugares() | no_clinicas}
    _RAICES = {r for r in (_stem(p) for p in sueltas)
               if len(r) >= LONGITUD_MINIMA_RAIZ and r not in excluidas}
    return len(_RAICES)


def es_clinica(palabra):
    """
    True si la palabra es evidencia de contenido clinico.

    Se compara por raiz y no por igualdad, de modo que 'vomitando' cuenta
    gracias a 'vomito', que es la forma que declara el catalogo.
    """
    clave = _plegar(palabra)
    if (clave in PALABRAS_TRAMITE or clave in PALABRAS_ANATOMIA
            or clave in PALABRAS_TIEMPO):
        return False
    cargar()
    return _stem(clave) in _RAICES


def frases_clinicas(texto):
    """
    Expresiones del catalogo de varias palabras presentes en la nota, como
    'me falta el aire'. Se buscan enteras porque su contenido clinico no esta
    en ninguna de sus palabras por separado.
    """
    cargar()
    plano = " ".join(_plegar(w) for w in RE_PALABRA.findall(sin_encabezados(texto)))
    return [f for f in _FRASES if f in plano]


def terminos_clinicos(texto):
    """
    Palabras de la nota que son terminología clínica curada y además aportan
    contenido: ni trámite ni región anatómica suelta.

    Esa resta es la diferencia entre que una palabra figure en el léxico y que
    diga algo del paciente.
    """
    return [p for p in con_contenido(texto) if es_clinica(p)]


def solo_tramite(texto):
    """
    True si la nota no tiene mas que tramite y nombres propios.

    POR QUE NO BASTA CON EXIGIR QUE TODO SEA TRAMITE
        La version anterior pedia que TODAS las palabras estuvieran en la lista,
        y por eso dejaba pasar

            'remitido de assbsaluda san cayetano'

        que es una derivacion pura: 'remitido' es tramite, pero 'assbsaluda' y
        'cayetano' no estan en ninguna lista -- son el nombre de una IPS y de un
        municipio, y no hay lista que los cubra todos.

        La forma si generaliza: lo que sostiene una nota es la CLINICA. Una
        palabra que no es terminologia no aporta motivo de consulta, se llame
        como se llame, asi que basta con que haya tramite y no haya nada
        clinico.

    Se exige al menos una palabra de tramite: sin ella esto marcaria cualquier
    nota cuyo vocabulario el lexico todavia no cubra, que es justo el error que
    el proyecto lleva toda su historia evitando.
    """
    palabras = con_contenido(texto)
    if not palabras:
        return False
    if not any(p in PALABRAS_TRAMITE for p in palabras):
        return False
    return not any(es_clinica(p) for p in palabras)


# ==========================================================
# EL VEREDICTO
# ==========================================================

# Motivos de descarte, en el orden en que se comprueban.
VACIA = "vacia"
PLANTILLA = "plantilla en blanco"
ANTECEDENTES = "solo antecedentes"
TRAMITE = "tramite administrativo"
SIN_TERMINOLOGIA = "sin terminologia clinica"
UTIL = ""


def evaluar(texto, sintomas=None):
    """
    Decide si una nota aporta información clínica.

    Devuelve el par (útil, motivo), donde el motivo es cadena vacía cuando la
    nota se conserva y, si no, uno de los motivos declarados arriba. Las
    comprobaciones van de la más barata y concluyente a la más laxa, y terminan
    en una válvula de escape por longitud.

    `sintomas` es la lista de síntomas que la fase 4 haya reconocido, si se
    tiene a mano. Cuando se pasa, un síntoma reconocido basta para conservar la
    nota sin mirar nada más: el catálogo es mejor evidencia que la coincidencia
    palabra a palabra, porque reconoce expresiones de varias palabras. El
    parámetro es opcional para que el módulo siga sirviendo dentro de las fases
    1 a 3, donde todavía no se ha extraído nada.
    """
    if sintomas:
        return True, UTIL

    palabras = con_contenido(texto)
    if not palabras:
        return False, VACIA

    if all(p in RESPUESTAS_VACIAS for p in palabras):
        return False, PLANTILLA

    # A PARTIR DE AQUI SE JUZGA SOLO EL TRAMO QUE PUEDE SER MOTIVO DE CONSULTA.
    #
    # Los antecedentes son terminologia clinica de verdad y aun asi no dicen a
    # que vino nadie. 'ap: hta; aa: niega' informa de que el paciente es
    # hipertenso, no de por que consulto hoy ni de por que se descompenso. Para
    # agrupar motivos de consulta eso es ruido, y ademas ruido convincente: pasa
    # cualquier filtro que solo pregunte si hay terminologia.
    motivo = sin_apartados_no_clinicos(texto)
    palabras = con_contenido(motivo)
    if not palabras:
        return False, ANTECEDENTES
    if all(p in RESPUESTAS_VACIAS for p in palabras):
        return False, PLANTILLA

    # El tramite puro se comprueba ANTES que la terminologia, y ese orden
    # importa: hay frases administrativas cuyas palabras estan todas en el
    # lexico, de modo que preguntando primero por terminologia se conservarian.
    if solo_tramite(motivo):
        return False, TRAMITE

    # La frase entera se comprueba ademas de las palabras sueltas: 'me falta el
    # aire' es disnea y ninguna de sus tres palabras lo es por separado.
    if terminos_clinicos(motivo) or frases_clinicas(motivo):
        return True, UTIL

    # La nota no tiene terminologia con contenido, pero antes de descartarla se
    # le da una ultima oportunidad: si es larga se conserva, porque el lenguaje
    # de paciente que el lexico no cubre sigue siendo un motivo de consulta.
    if len(palabras) >= PALABRAS_PARA_SALVAR:
        return True, UTIL

    # corta, sin terminologia y encima mencionando tramite: se descarta con ese
    # motivo, que al auditar dice mas que 'sin terminologia'
    if any(p in PALABRAS_TRAMITE for p in palabras):
        return False, TRAMITE

    return False, SIN_TERMINOLOGIA


def util(texto, sintomas=None):
    """Atajo booleano de evaluar(), para filtrar sin desempaquetar el motivo."""
    return evaluar(texto, sintomas)[0]


def resumen(motivos):
    """
    Cuenta los motivos de descarte de una corrida y los devuelve ordenados de
    más a menos frecuente. Las notas conservadas, cuyo motivo es vacío, no se
    cuentan.
    """
    conteo = {}
    for motivo in motivos:
        if motivo:
            conteo[motivo] = conteo.get(motivo, 0) + 1
    return sorted(conteo.items(), key=lambda x: -x[1])


def diagnosticar(texto):
    """
    Por qué una nota concreta se conserva o se descarta: el veredicto, el
    motivo y las señales en las que se apoya. Herramienta de inspección manual.
    """
    util_, motivo = evaluar(texto)
    return {
        "texto": texto,
        "util": util_,
        "motivo": motivo or "se conserva",
        "palabras_con_contenido": con_contenido(texto),
        "motivo_de_consulta": sin_apartados_no_clinicos(texto),
        "terminos_clinicos": terminos_clinicos(texto),
        "frases_clinicas": frases_clinicas(texto),
        "menciona_tramite": any(p in PALABRAS_TRAMITE for p in con_contenido(texto)),
    }
