"""
Recorte de la nota: conservar el motivo de consulta y descartar lo demás.

QUÉ PROBLEMA RESUELVE
    El texto que se le entrega al modelo de embeddings se construía a partir de
    la estructura extraída, con frases del tipo 'categoria respiratorio. sintoma
    cefalea.'. Eso tenía dos consecuencias graves:

    Muchas notas distintas producían un texto idéntico, y un texto idéntico da
    un vector idéntico. Miles de registros se convertían así en un único punto,
    lo que degrada cualquier agrupamiento posterior.

    Y, sobre todo, canonizar contra un catálogo cerrado hace que el
    agrupamiento solo pueda redescubrir los conceptos ya declarados. La fase
    siguiente existe para encontrar los patrones que nadie declaró, y se le
    estaba entregando exactamente lo declarado.

LA INVERSIÓN
    Antes la estructura era el texto y la nota real quedaba como respaldo. Ahora
    la nota real es el texto y la estructura son campos aparte.

    Son dos cosas distintas que estaban mezcladas en un solo campo. La
    estructura sirve para filtrar, contar y cruzar con otras fuentes, y sigue en
    el archivo de salida. El texto sirve para que el modelo mida parecido
    semántico, y para eso necesita lenguaje, no etiquetas.

QUÉ SE QUITA
    Lo que sobra en una nota de triage no es variado: son unos pocos bloques
    estereotipados que se repiten casi iguales en miles de notas.

        bloque institucional  la política de la aseguradora, los niveles de
                              atención, las disculpas. No hablan del paciente y
                              se quitan siempre, en las dos pasadas.
        trámite               cómo llegó el paciente al servicio. Es idéntico en
                              notas de cuadros opuestos, así que agrupa por
                              recorrido administrativo y no por clínica.
        verbo de reporte      introduce el síntoma sin aportar nada.
        encabezados           etiquetas del formulario.
        preámbulo temporal    el tiempo de evolución ya viaja como dato aparte.
        ficha demográfica     la edad ya viaja como dato aparte.

    Todo lo demás se conserva TAL CUAL. Esa es la diferencia con el enfoque
    anterior: no se reescribe la nota, se le quitan los bloques que sobran, y lo
    que queda son las palabras que escribió quien atendió al paciente.

    Además de esa lista, una oración larga sin ninguna terminología clínica se
    descarta aunque nadie la haya enumerado. Es la red de seguridad para el
    texto administrativo que todavía no se conoce.

LO QUE NO SE TOCA
    La negación se queda dentro del texto. Un cuadro descrito como resuelto
    tiene que llegarle así al modelo, y quitar la negación lo convertiría en uno
    activo. La negación viaja dos veces a propósito, como campo estructurado y
    dentro de la frase, porque cada copia sirve para algo distinto.

    Tampoco se quita la anotación entre paréntesis que añade la fase 3: para el
    modelo no es una redundancia, sino la única pista de qué significa una sigla.
"""

import json
import re
from pathlib import Path

from NLP import rutas

RE_ESPACIOS = re.compile(r"\s+")

# El lexico clinico que construye NLP/recursos/lexico.py. Aqui se usa solo para
# medir de que habla cada oracion, nunca para corregir nada.
RUTA_LEXICO = rutas.LEXICO_CLINICO

_LEXICO = None

# Solo cuentan las fuentes curadas del lexico. El vocabulario del modelo
# biomedico queda fuera a proposito: contiene el espanol corriente entero, y con
# el la densidad clinica sale maxima incluso para un aviso administrativo.
FUENTES_CURADAS = ("diccionario", "catalogo", "externo")

# Umbral deliberadamente conservador. Al medir la densidad clinica de frases
# administrativas y de frases de paciente, las dos poblaciones se solapan: el
# CIE-10 contiene mucho espanol corriente, asi que un bloque burocratico puede
# puntuar alto y no hay un corte que las separe limpiamente.
#
# Por eso la densidad no es el criterio principal, sino una red de seguridad
# para los bloques que nadie enumero, con el umbral por debajo de la frase
# clinica mas pobre observada. Se prefiere dejar pasar texto administrativo
# antes que borrar una frase del paciente: es la asimetria de coste de todo el
# proyecto.
PALABRAS_ORACION_LARGA = 8
DENSIDAD_MINIMA = 0.40


# ==========================================================
# LUGARES
# ==========================================================
#
# El municipio del que viene el paciente no es su motivo de consulta, y para el
# agrupamiento es peor que neutro: hace parecidas dos notas que solo comparten
# el pueblo de origen, y separa dos que describen el mismo cuadro desde sitios
# distintos. Es exactamente el mismo problema que la ficha demografica.
#
# La lista no se escribe aqui: es el grupo 'geografia' de
# datos/diccionario_siglas.json, que ya existia para que el corrector NO
# corrija un toponimo. Se reutiliza en vez de duplicarla, porque dos listas de
# municipios acaban divergiendo, y porque asi ampliar una sola entrada arregla
# las dos cosas a la vez.
#
# LO QUE COSTO NO TENERLA COMPLETA
#     'la dorada' faltaba en ese grupo, y sin la declaracion el corrector la
#     tomo por un error de escritura:
#
#         'hospitalizacion reciente en la dorada'  ->  '... en la morada'
#
#     Un municipio convertido en otra palabra es un dato inventado, y ademas
#     silencioso: no aparece en ninguna alarma porque el corrector creyo estar
#     arreglando un typo.

_LUGARES = None
RE_LUGAR = None


def cargar_lugares(ruta=None):
    """
    Construye el patron de toponimos desde el grupo 'geografia' del diccionario
    de siglas. Devuelve cuantos se cargaron; 0 si el archivo no esta.

    Se quita tambien el articulo y la preposicion que los introducen ('de la
    dorada', 'en chinchina'), porque dejarlos sueltos parte la frase.
    """
    global _LUGARES, RE_LUGAR
    if _LUGARES is not None:
        return len(_LUGARES)

    ruta = Path(ruta or rutas.DICCIONARIO_SIGLAS)
    if not ruta.exists():
        _LUGARES, RE_LUGAR = set(), None
        return 0

    datos = json.loads(ruta.read_text(encoding="utf-8"))
    _LUGARES = set(datos.get("geografia", {}))
    if not _LUGARES:
        RE_LUGAR = None
        return 0

    # de mas largo a mas corto para que gane 'la dorada' sobre 'dorada'
    formas = "|".join(re.escape(x) for x in sorted(_LUGARES, key=len, reverse=True))
    RE_LUGAR = re.compile(
        r"(?:,\s*)?\b(?:de|desde|en|a|hacia|procedente\s+de|remitid[oa]\s+de)?"
        r"\s*(?:el|la|los|las)?\s*\b(?:%s)\b" % formas,
        re.IGNORECASE)
    return len(_LUGARES)


def cargar_lexico(ruta=RUTA_LEXICO):
    """
    Carga las formas curadas del léxico clínico y devuelve cuántas son. Si el
    archivo no existe devuelve 0, y entonces la densidad clínica queda
    desactivada y solo actúan los marcadores enumerados.
    """
    global _LEXICO
    ruta = Path(ruta)
    if not ruta.exists():
        _LEXICO = set()
        return 0
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    _LEXICO = {clave for clave, (_forma, fuente) in datos.get("terminos", {}).items()
               if fuente in FUENTES_CURADAS}
    return len(_LEXICO)

# ==========================================================
# LO QUE SE QUITA
# ==========================================================

# Frases del bloque institucional. Basta con encontrar una para descartar la
# oracion entera, porque ese bloque nunca trae contenido clinico mezclado.
MARCADORES_INSTITUCIONALES = (
    "entidad promotora", "red de atencion", "nivel de atencion", "afiliados",
    "priorizados", "disculpas", "molestias ocasionadas", "obligacion de realizar",
    "cierres de servicios", "urgencias vitales", "urgencia vital",
    "riesgo inmediato para la vida", "deberan ser orientados",
    "condicion represente", "lamentamos", "inconvenientes que esta situacion",
    "no constituye una urgencia", "sin criterios que constituyan",
    "asignada por su eps", "atencion asignada",
)

# Tramite: como llego el paciente al servicio. No es el motivo de consulta.
RE_TRAMITE = re.compile(
    r"\b(?:"
    r"ingresa(?:n)?\s+(?:paciente|usuari[oa])?|se\s+recibe\s+paciente|"
    r"paciente\s+que\s+ingresa|"
    r"es\s+(?:remitid[oa]|traslad[oa]d[oa]|derivad[oa])|"
    r"(?:remitid[oa]|traslad[oa]d[oa]|derivad[oa]|aceptad[oa])"
    r"(?:\s+(?:desde|de|por|a|en))?|"
    r"se\s+(?:remite|traslada|deriva|acepta)|"
    r"(?:lo|la|le|me|nos)\s+(?:remitieron|remiten|trasladaron|trasladan|"
    r"derivaron|derivan|enviaron|envian|mandaron|mandan|remitio|remite)|"
    r"(?:remitieron|trasladaron|derivaron|enviaron)|"
    r"(?:consulta|acude|asiste)\s+por|"
    r"paciente\s+(?:masculin[oa]|femenin[oa])|"
    r"quien\s+(?:consulta|ingresa|refiere|sufre|padece|presenta|manifiesta)|"
    r"servicio\s+de\s+urgencias|triage\s+de\s+enfermeria|"
    r"valorad[oa]\s+por\s+triage"
    r")\b",
    re.IGNORECASE)

# Verbos de reporte: introducen el sintoma sin aportar nada. Se quitan junto
# con el 'que' que los sigue, porque por si solos dejan la frase colgando.
RE_REPORTE = re.compile(
    r"\b(?:refiriendo|manifestando|indicando|comentando|informando)\s+que\s+"
    r"(?:esta|estaba|se\s+encuentra)?\s*|"
    r"\b(?:refiere|manifiesta|indica|comenta|informa)\s+que\s+",
    re.IGNORECASE)

# Encabezados del formulario: 'mc:', 'ap (antecedentes personales):'
RE_ENCABEZADO = re.compile(r"\b[a-z]{2,4}\s*(?:\([^)]{3,60}\))?\s*:", re.IGNORECASE)

# Anotacion entre parentesis que agrego la fase 3. NO se quita del texto, y es
# deliberado: para quien lee la nota la anotacion duplica lo que la sigla ya
# dice, pero el modelo de embeddings no sabe que hay detras de una sigla, asi
# que quitarla tira el trabajo de la fase anterior y deja notas sin un solo
# termino clinico reconocible.
#
# El unico parentesis que de verdad sobra es el del encabezado
# ('mc (motivo de consulta):'), y ese lo consume entero RE_ENCABEZADO, que
# incluye el parentesis opcional antes de los dos puntos.
#
# El patron se conserva por si hace falta el texto sin anotaciones.
RE_PARENTESIS = re.compile(r"\([^)]{5,80}\)")

MESES = (r"enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
         r"septiembre|setiembre|octubre|noviembre|diciembre")

RE_TEMPORAL = re.compile(
    r"(?:,\s*)?\b(?:desde\s+hace\s+\d{1,3}\s*(?:dias?|d[ií]as?|horas?|semanas?|meses?)|"
    r"hace\s+\d{1,3}\s*(?:dias?|d[ií]as?|horas?|semanas?|meses?)(?:\s+que)?|"
    r"desde\s+(?:el|la)\s+(?:lunes|martes|miercoles|mi[eé]rcoles|jueves|viernes|"
    r"sabado|s[aá]bado|domingo|manana|ma[nñ]ana|ayer|anoche|hoy)\w*|"
    r"desde\s+hace\s+(?:un|una|unos|unas)\s+\w+|"
    # Fecha de inicio por mes o por epoca del mes. Salio de la nota 815839, que
    # empieza 'desde principios de marzo' y no la cogia ninguna de las de
    # arriba, todas construidas sobre 'hace N dias'. Cuando ocurrio la cosa no
    # es el motivo de consulta, y ademas separa dos notas identicas escritas en
    # meses distintos, que es justo lo contrario de lo que hace falta.
    r"(?:desde\s+)?(?:a\s+)?(?:principios|mediados|finales|comienzos|fines)\s+"
    r"(?:de\s+|del\s+)?(?:%s|mes|semana|a[nñ]o)\w*|"
    r"desde\s+(?:el\s+)?(?:mes\s+de\s+)?(?:%s)\b|"
    r"en\s+(?:el\s+mes\s+de\s+)?(?:%s)\s+(?:pasado|de\s+\d{4})|"
    r"desde\s+hace\s+(?:varios|varias|muchos|muchas)\s+\w+)\b"
    % (MESES, MESES, MESES),
    re.IGNORECASE)

# Ficha demografica. La edad ya viaja como dato estructurado, y dentro del
# texto solo consigue que se parezcan dos notas que no tienen nada que ver.
RE_DEMOGRAFICO = re.compile(
    r"\b(?:de\s+)?\d{1,3}\s*(?:anos|años)(?:\s+de\s+edad)?\b", re.IGNORECASE)

# Quien acompana al paciente y como llego al servicio.
#
# Salieron de revisar tres notas a mano y luego contarlas en el corpus:
#
#     1.301 notas (4,6%)  'en compania de hija', 'con acompanante', 'traido por su esposa'
#     1.107 notas (3,9%)  'en silla de ruedas', 'caminando', 'en camilla'
#
# En la nota 803472 eran lo unico que sobrevivia al recorte: el texto de
# embedding empezaba con 'silla de ruedas con acompanante' antes de llegar a las
# epistaxis, que es de lo que habla la nota. Ninguna de las dos cosas dice por
# que consulto el paciente, y las dos son identicas en notas de cuadros
# opuestos, que es la definicion de ruido para el agrupamiento.
#
# 'en silla de ruedas' se quita aunque describa al paciente: es una condicion
# previa, no el motivo de hoy, y el triage ya la registra aparte.
RE_ACOMPANANTE = re.compile(
    r"(?:,\s*)?\b(?:"
    r"en\s+compa[nñ][ií]a\s+(?:de|del|de\s+la|de\s+su)?\s*\w*|"
    r"con\s+(?:su\s+)?acompa[nñ]ante|acompa[nñ]ad[oa]\s+(?:de|por)\s+\w+|"
    r"tra[ií]d[oa]\s+por\s+(?:su|la|el)\s+\w+|"
    r"por\s+(?:su\s+)?cuidador[a]?(?:\s+de\s+hogar)?|"
    r"cuidador[a]?\s+de\s+hogar"
    r")\b",
    re.IGNORECASE)

RE_LLEGADA = re.compile(
    r"(?:,\s*)?\b(?:"
    r"(?:llega|ingresa|viene|acude)?\s*en\s+silla\s+de\s+ruedas|"
    r"en\s+camilla(?:\s+de\s+ambulancia)?|"
    r"por\s+sus\s+propios\s+medios|"
    r"(?:llega|ingresa|viene|acude)\s+caminando|^caminando"
    r")\b",
    re.IGNORECASE)

RE_ORACION = re.compile(r"(?<=[.;])\s+")

# el mismo corte que usa reduccion/frases.py, para que los tramos coincidan
RE_TRAMO_CLASIF = re.compile(r"\s*[.;,]\s*")

# ==========================================================
# LOS TRES BLOQUES DE LA NOTA LARGA
# ==========================================================
#
# El 15,9% del corpus pasa de 30 palabras, y ahi es donde vive el ruido que
# sobrevivia a todo lo anterior. Medido sobre esas notas, lo que sobra son tres
# bloques, y ninguno responde a por que vino el paciente:
#
#   examen fisico   'paciente en el momento clinicamente estable, consciente
#                    orientado en sus tres esferas mentales, sin signos de
#                    deshidratacion, normotenso, normocardia, normal saturado'
#                   369 notas repiten la primera frase palabra por palabra.
#   conducta        'se realiza rastreo ecografico', 'se dan recomendaciones y
#                    signos de alarma', 'se decide derivar paciente'. Es lo que
#                   hizo el hospital, no lo que traia el paciente.
#   antecedentes    'paciente con antecedentes de artritis reumatoide, sindrome
#                    de sjogren, trombocitopenia autoinmune, osteoporosis...'
#                   En la nota 787265 son 60 de sus 153 palabras.
#
# POR QUE SE QUITAN POR FRASE Y NO POR ORACION
#     _quitar_institucional() descarta oraciones enteras, y para eso separa por
#     punto y por punto y coma. La nota larga de triage no usa ninguno de los
#     dos: es una sola frase corrida separada por comas. Ahi el filtro por
#     oracion es todo o nada -- o deja el bloque entero o se lleva la nota
#     entera -- y por eso estos tres se quitan con patrones de frase, que
#     recortan justo el tramo que sobra y dejan intacto lo que lo rodea.

# Hallazgos del examen fisico. Describen como esta el paciente ahora, que es
# justo lo que el triage ya registra como variable estructurada.
RE_EXAMEN = re.compile(
    r"(?:,\s*)?\b(?:"
    r"(?:paciente\s+)?(?:en\s+el\s+momento\s+)?cl[ií]nicamente?\s+(?:y\s+)?"
    r"(?:hemodinamicamente\s+)?estable|"
    r"hemodinamicamente\s+estable|"
    r"conscientes?\s+(?:y\s+)?orientad[oa]|"
    r"orientad[oa]\s+en\s+(?:sus\s+)?tres\s+esferas(?:\s+mentales)?|"
    r"en\s+sus\s+tres\s+esferas(?:\s+mentales)?|"
    r"sin\s+signos\s+de\s+(?:deshidrataci[oó]n|dificultad\s+respiratoria|"
    r"focalizaci[oó]n(?:\s+neurol[oó]gica)?|irritaci[oó]n\s+men[ií]ngea)|"
    r"no\s+signos\s+de\s+focalizaci[oó]n(?:\s+neurol[oó]gica)?|"
    r"no\s+d[eé]ficit\s+neurol[oó]gic[oa]|no\s+p[eé]rdida\s+de\s+fuerza|"
    r"fuerza\s+conservada|movilidad\s+completa\s+de\s+4\s+extremidades|"
    r"sin\s+desviaci[oó]n\s+de\s+la\s+comisura\s+labial|"
    r"normotens[oa]|normocardi[oa|co|ca]*|normal\s+saturad[oa]|"
    r"llenado\s+capilar\s+menor\s+de\s+\d+\s+segundos|"
    r"responde\s+[oó]rdenes|responde\s+ordenes|las\s+sigue|"
    r"pupilas?\s+normoreactivas?(?:\s+a\s+la\s+luz)?|"
    r"afebril\s+al\s+ingreso|"
    r"a\s+la\s+valoraci[oó]n(?:\s+paciente)?|al\s+momento\s+de\s+la\s+valoraci[oó]n|"
    r"al\s+examen\s+f[ií]sico|se\s+observa\s+paciente|observo\s+paciente"
    r")\b",
    re.IGNORECASE)

# Conducta: lo que hizo o decidio el servicio.
RE_CONDUCTA = re.compile(
    r"(?:,\s*)?\b(?:"
    r"se\s+(?:realiza|realizan|ordena|ordenan|solicita|solicitan|indica|"
    r"indican|administra|administran|canaliza|toma|tomaron|deja|dejan|"
    r"decide|decidio|decidió|informa|explica|educa)\b[^,.;]{0,60}|"
    r"se\s+dan\s+recomendaciones(?:\s+y\s+signos\s+de\s+alarma)?"
    r"(?:\s+de\s+reconsulta)?|"
    r"signos\s+de\s+alarma\s+de\s+reconsulta|"
    r"manejo\s+(?:con|ambulatorio|intrahospitalario)\b[^,.;]{0,40}|"
    r"pendiente\s+(?:valoraci[oó]n|resultados?)\b[^,.;]{0,40}|"
    r"queda\s+en\s+observaci[oó]n|pasa\s+a\s+observaci[oó]n|"
    r"traslado\s+por\s+sus\s+propios\s+medios[^,.;]{0,60}"
    r")",
    re.IGNORECASE)

# Antecedentes en prosa, sin rotulo. El apartado con rotulo lo resuelve
# NLP/depuracion, pero en la nota larga los antecedentes van introducidos por
# una frase y se extienden hasta el conector que abre el cuadro actual.
#
# DOS DETALLES QUE COSTARON UNA MEDICION
#   No se exige el 'con' delante. La nota 755179 dice 'paciente con
#   pluripatologia y polifarmacia, anciano fragil, antecedentes de SAHOS...',
#   y al quitar antes 'pluripatologia' el 'con' deja de estar pegado a
#   'antecedentes'. Por eso este patron corre ANTES que RE_PLURIPATOLOGIA y no
#   depende de la preposicion.
#
#   Y el tramo esta acotado a 400 caracteres. Con '.*?' sin limite, si el
#   conector que abre el cuadro actual no aparecia, el patron no encontraba
#   donde terminar y se quedaba corto: recortaba 'con ' y dejaba los 60
#   terminos de la historia pasada intactos.
RE_ANTECEDENTES = re.compile(
    r"\b(?:paciente\s+)?(?:con\s+)?antecedentes?\s+(?:de\s+|personales\s+)?"
    r"[^.;]{0,400}?(?=\bcon\s+cuadro\b|\bcuadro\s+cl[ií]nico\b|"
    r"\bquien\s+consulta\b|\bconsulta\s+por\b|\bingresa\b|"
    r"\brefiere\b|\bpresenta\b|\bmanifiesta\b|\bindica\b|[.;])",
    re.IGNORECASE)
#
# EL FINAL DE TEXTO NO CUENTA COMO FINAL DEL BLOQUE, Y ESO ES LO IMPORTANTE.
#     Con '$' entre las alternativas, una nota sin ningun conector ni punto no
#     tenia donde terminar el bloque y se lo llevaba entero:
#
#         'paciente con antecedente de infeccion urinaria, esta fiebre'  ->  ''
#
#     La fiebre de hoy desaparecia junto con el antecedente. Sin '$', cuando no
#     se ve donde acaba el bloque no se quita nada: es preferible arrastrar unos
#     antecedentes que borrar el motivo de consulta. Es la misma razon por la que
#     se retiro el patron de estudios previos, que fallaba igual.

RE_PLURIPATOLOGIA = re.compile(
    r"\b(?:pluripatolog[ií]a|polifarmacia|anciano\s+fr[aá]gil)\b(?:\s*y\s*)?",
    re.IGNORECASE)

# Conectores y preposiciones que quedan colgando al principio de la frase
# cuando se quita el tramo que los precedia.
#
# Dos detalles del patron que no son opcionales:
#   se ordena por longitud descendente, porque la alternancia de una expresion
#   regular toma la primera opcion que encaje y una preposicion corta se comeria
#   solo la primera letra de una mas larga;
#   lleva limite de palabra al final, porque sin el recorta dentro de la palabra
#   siguiente cuando esta empieza por la misma secuencia.
ARRANQUE_HUERFANO = (
    "de", "del", "con", "en", "por", "para", "a", "al", "y", "e", "o", "u",
    "que", "se", "su", "sus", "lo", "la", "el", "los", "las", "un", "una",
    "es", "ademas", "además", "tambien", "también",
)
RE_ARRANQUE_HUERFANO = re.compile(
    "^(?:%s)(?![^%sW%sd_])%ss*[,;]?%ss*" % (
        "|".join(sorted(ARRANQUE_HUERFANO, key=len, reverse=True)),
        chr(92), chr(92), chr(92), chr(92)),
    re.IGNORECASE)

# Palabras que por si solas no son contenido. Solo se usan para decidir si lo
# que quedo vale la pena; nunca se borran del texto, que tiene que seguir siendo
# una frase legible.
VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "a", "al", "en", "con", "sin", "por", "para", "que", "se", "su",
    "sus", "lo", "le", "es", "esta", "este", "muy", "mas", "ni", "pero",
    "paciente", "usuario", "usuaria", "ahora", "momento", "cual", "quien",
    "ademas", "tipo", "toda", "todo", "ser", "han", "ha", "he", "les",
}

# Palabras con contenido que debe dejar el recorte para dar la nota por util.
# Con una basta, porque el filtro de palabras vacias ya se aplico antes: si
# sobrevive una sola palabra, es una palabra que dice algo. Un umbral mas alto
# descartaba notas cortas perfectamente validas, que en triage son la norma.
LONGITUD_MINIMA = 1
TOPE_PALABRAS = 60       # una nota de 400 palabras no aporta mas que sus 60

# Lo que queda de una plantilla contestada en blanco: al quitarle los
# encabezados, una nota que solo tiene respuestas queda reducida a estas
# palabras, que tienen contenido pero no dicen nada del paciente.
RESPUESTAS_VACIAS = {
    "niega", "niegan", "ninguno", "ninguna", "ninguna", "nada", "nono",
    "negativo", "negativa", "normal", "normales", "refiere", "presenta",
    "manifiesta", "asintomatico", "asintomatica", "aplica",
}


# ==========================================================
# RECORTE
# ==========================================================

def densidad_clinica(oracion):
    """
    Fracción de las palabras con contenido de la oración que son terminología
    clínica, según el léxico curado. Devuelve 0.0 si la oración no tiene
    palabras con contenido.

    Es la alternativa que generaliza a la lista de marcadores. Enumerar frases
    funciona con un aviso institucional concreto, porque se repite literal, pero
    deja de funcionar en cuanto una sede cambia su redacción o aparece otro tipo
    de texto administrativo. La densidad no enumera nada: mide de qué habla la
    oración, y una oración que no menciona nada clínico no habla del paciente.
    """
    palabras = _con_contenido(oracion)
    if not palabras:
        return 0.0
    return sum(1 for p in palabras if _es_clinica(p)) / len(palabras)


def _es_clinica(palabra):
    """
    True si la palabra está en el léxico clínico.

    El léxico se guarda con la clave plegada (minúsculas, sin tildes y con la
    eñe conservada), así que aquí se pliega igual antes de comparar. La eñe se
    protege sustituyéndola por un carácter de control antes de descomponer los
    acentos y restaurándola después; ese carácter va literal en el código y no
    se ve al leerlo, así que conviene no tocar estas dos líneas a ciegas.
    """
    if _LEXICO is None:
        cargar_lexico()
    if not _LEXICO:
        return False
    import unicodedata
    plano = "".join(c for c in unicodedata.normalize("NFD", palabra.replace("ñ", ""))
                    if not unicodedata.combining(c)).replace("", "ñ")
    return plano in _LEXICO


def _protegido_por_clinica(tramo):
    """
    True si el tramo habla lo bastante del paciente como para que no pueda ser
    trámite, diga lo que diga el clasificador.

    SE MIDE CON LA MISMA DENSIDAD QUE USA EL FILTRO INSTITUCIONAL
        Es deliberado, y el umbral es el mismo. Con eso, las dos defensas de
        este módulo dicen lo mismo sobre un tramo: si `_quitar_institucional()`
        lo conservaría por hablar de clínica, el clasificador no puede tirarlo.
        Dos criterios distintos darían un tramo que una defensa salva y la otra
        descarta, y quien lea el resultado no sabría cuál mandó.

        La primera version de este freno pregunto a depuracion.py, que tiene un
        lexico mas estrecho a proposito (resta region anatomica suelta y
        tramite). Sobre 'olor fetido por herida quirurgica a nivel axilar
        izquierdo' encontraba UN termino, 'herida', y el tramo se perdia igual.
        El lexico curado de este modulo reconoce los siete.
    """
    return densidad_clinica(tramo) >= DENSIDAD_MINIMA


def _quitar_clasificador(texto):
    """
    Quita los tramos que el clasificador de frases da por administrativos.

    POR QUE ADEMAS DE LOS PATRONES, Y NO EN SU LUGAR
        Los patrones enumeran y por eso tienen buena precision y mala
        cobertura. Medido sobre 400 tramos que NINGUNA regla supo etiquetar, el
        clasificador reconocio 110 administrativos y 144 clinicos, dejando 146
        en zona gris. Los 110 no los cubria ningun patron y no se parecen entre
        si mas que en el tema:

            'derivan para manejo por hemodinamia'
            'remision del hospital san isidro'
            'paciente valorado con urgenciologo de turno'
            'tuve cita con especialista y el me derivo'

        Cada uno habria necesitado su propia expresion regular. Los patrones se
        quedan porque siguen siendo la defensa mas barata y la mas predecible;
        el clasificador cubre lo que ellos no ven.

    NUNCA VACIA LA NOTA
        Si lo marcado se lleva todos los tramos, se devuelve el texto original.
        Es la misma regla que en _quitar_institucional() y por la misma razon:
        perder el motivo de consulta cuesta mucho mas que arrastrar una frase
        administrativa.
    """
    from NLP.reduccion import frases

    if not frases.disponible():
        return texto

    tramos = frases.segmentos(texto)
    if len(tramos) < 2:
        return texto

    marcados = frases.burocraticos(tramos)
    if not any(marcados):
        return texto

    # EL CLASIFICADOR PROPONE; LA TERMINOLOGIA VERIFICA.
    #
    # El clasificador juzga el tramo entero y se deja llevar por como EMPIEZA.
    # Un tramo que abre con 'paciente ingresa refiriendo' o 'consulta por
    # cuadro clinico' se parece muchisimo a un tramite, y lo es -- hasta que
    # sigue. Medido al activarlo por primera vez sobre 100 notas reparadas,
    # se llevo por delante tres motivos de consulta enteros:
    #
    #     'consulta por cuadro clinico 8 dias de evolucion consistente en
    #      desviacion de la comisura labial lado izquierdo'      -> descartado
    #     'paciente ingresa refiriendo ... olor fetido por herida
    #      quirurgica a nivel axilar izquierdo'                  -> descartado
    #
    # Ninguno vuelve: el tramo se tira entero y las fases siguientes ya no lo
    # ven. Por eso el veredicto del clasificador no basta por si solo.
    #
    # El freno es el mismo criterio que usa extractor.py para aceptar lo que
    # devuelve el modelo de lenguaje: un tramo con terminologia clinica de
    # sobra no es tramite, diga lo que diga quien lo juzgo. Y es el mismo
    # principio del resto del proyecto -- el modelo propone, las reglas
    # verifican -- aplicado aqui, que es donde faltaba.
    sobran = {t for t, malo in zip(tramos, marcados)
              if malo and not _protegido_por_clinica(t)}
    if not sobran:
        return texto
    if not [t for t in tramos if t not in sobran]:
        return texto

    # se reconstruye quitando solo los tramos marcados, conservando el resto
    # tal cual: el objetivo es recortar, no reescribir
    partes = [t.strip() for t in RE_TRAMO_CLASIF.split(texto)
              if t.strip() and t.strip() not in sobran]
    return ", ".join(partes) if partes else texto


def _quitar_institucional(texto):
    """
    Descarta las oraciones que hablan del sistema y no del paciente.

    Aplica dos criterios: que la oración contenga un marcador institucional
    conocido, o que sea larga y su densidad clínica quede por debajo del umbral.

    El segundo es el que generaliza a los bloques que nadie enumeró. Se exige
    que la oración sea larga porque una frase corta sin terminología reconocida
    suele ser lenguaje del paciente, que sí hay que conservar: que el léxico no
    la reconozca no significa que sobre.
    """
    oraciones = RE_ORACION.split(texto)
    utiles = []
    for o in oraciones:
        if any(m in o.lower() for m in MARCADORES_INSTITUCIONALES):
            continue
        palabras = _con_contenido(o)
        if len(palabras) >= PALABRAS_ORACION_LARGA and densidad_clinica(o) < DENSIDAD_MINIMA:
            continue
        utiles.append(o)

    # SI NO QUEDA NADA, SE DEVUELVE LA NOTA ENTERA. NO ES UNA CAUTELA GENERICA.
    #
    # Las oraciones se separan por punto y por punto y coma, y buena parte del
    # corpus no lleva ni uno: la nota tipica de triage es una sola frase corrida.
    # En esas notas este filtro es todo o nada, y basta que el marcador aparezca
    # al final para que se lleve por delante el motivo de consulta:
    #
    #     'ingresa paciente refiriendo que lleva 8 dias con zumbido en oido
    #      derecho ... paciente estable sin criterio de urgencia vital'
    #
    #     una sola oracion -> 'urgencia vital' la descarta entera -> ''
    #
    # Medido sobre 8.000 notas, 229 quedaban vacias asi, y todas tenian un
    # cuadro clinico perfectamente legible. Devolver el original deja que
    # decidan los pasos siguientes, que trabajan sobre tramos y no sobre la
    # nota completa. Perder el bloque institucional de una nota es barato;
    # perder el motivo de consulta no lo es.
    if not utiles:
        return texto

    return " ".join(utiles)


def _pulir(texto):
    """
    Deja la frase legible después de haberle quitado tramos por el medio:
    normaliza la puntuación que queda suelta o duplicada y elimina los
    conectores que quedan colgando al principio.

    El barrido del arranque es iterativo y admite coma además de espacio, porque
    al quitar un tramo puede quedar más de un conector encadenado y una sola
    pasada no los limpia todos.
    """
    texto = re.sub(r"\s*,\s*(?=[,.;])", "", texto)
    texto = re.sub(r"(?:^|(?<=[.;]))\s*[,;]\s*", " ", texto)
    texto = re.sub(r"\s+([,.;])", r"\1", texto)
    texto = re.sub(r"([.;])\s*\1+", r"\1", texto)
    texto = RE_ESPACIOS.sub(" ", texto).strip(" ,.;:-")

    # conectores y preposiciones que quedan colgando al arranque, una y otra
    # vez hasta que no quede ninguna
    for _ in range(4):
        nuevo = RE_ARRANQUE_HUERFANO.sub("", texto, count=1).strip(" ,.;:-")
        if nuevo == texto:
            break
        texto = nuevo
    return texto


def _con_contenido(texto):
    """
    Palabras del texto que aportan significado, descartando las vacías y las
    muy cortas. Sirve para decidir si lo que quedó tras el recorte dice algo.
    """
    return [p for p in re.findall(r"[^\W\d_]+", texto.lower())
            if p not in VACIAS and len(p) >= 3]


def recortar(texto, agresivo=True):
    """
    Devuelve la nota sin bloque institucional, sin trámite y sin encabezados.
    Solo devuelve cadena vacía si la nota no dice nada del paciente.

    Se hace en dos pasadas. La agresiva quita además los verbos de reporte, la
    ficha demográfica y el preámbulo temporal; en una nota que es casi toda
    trámite, eso puede llevarse el contenido por delante. Cuando ocurre, se
    reintenta con la pasada suave, que conserva el trámite: es preferible una
    frase con algo de trámite que perder el motivo de consulta.

    Lo que sobrevive es texto del original palabra por palabra: aquí no se
    reescribe nada.
    """
    texto = str(texto or "").strip()
    if not texto:
        return ""

    # Se prueba la pasada agresiva, y se acepta solo si no dejo costuras. Si
    # las dejo, la suave corta menos y suele no tenerlas; y si tampoco vale, se
    # devuelve el mejor recorte disponible antes que nada. Una frase con algo de
    # tramite es mejor que una frase rota.
    agresiva = _recortar(texto, agresivo=True)
    if agresiva and not crea_costura(texto, agresiva):
        return agresiva

    suave = _recortar(texto, agresivo=False)
    if suave and not crea_costura(texto, suave):
        return suave

    return sin_reducir(texto, agresiva or suave)


def _pares_contiguos(texto):
    """
    Los pares de palabras contiguas del texto, tramo a tramo.

    Se corta en los signos de puntuacion porque un salto en una coma no es una
    costura: ahi la frase ya cambiaba de idea. Lo que interesa es la vecindad
    DENTRO de un tramo, que es la que la gramatica sostiene.
    """
    pares = set()
    for tramo in re.split(r"[.;,:]", str(texto).lower()):
        palabras = re.findall(r"[^\W\d_]+", tramo)
        pares |= set(zip(palabras, palabras[1:]))
    return pares


def crea_costura(original, recortado):
    """
    True si el recorte deja juntas dos palabras que no lo estaban en la nota.

    QUE MIDE, Y POR QUE ES UN CRITERIO Y NO UN SINTOMA
        Quitar un tramo por el medio deja pegado lo de antes con lo de despues.
        El resultado es una frase que nadie escribio:

            'paciente que consulta por dolor'  ->  'paciente que dolor'
            'paciente quien refiere cuadro'    ->  'paciente cuadro'

        Medido sobre 189 notas, esto era el 70% de todos los fallos del recorte,
        y 13 de las 17 costuras empezaban por 'paciente': los patrones de
        tramite y de verbo de reporte se llevan el verbo y dejan el sujeto
        huerfano pegado a lo siguiente.

        No hace falta enumerar que patron corta mal. Basta comprobar que el
        recorte no invento ninguna vecindad: si la invento, corto por un sitio
        por el que no se podia cortar. Es una propiedad del resultado, asi que
        vale para los patrones de hoy y para los que se añadan manana.
    """
    return bool(_pares_contiguos(recortado) - _pares_contiguos(original))


def sin_reducir(original, reducido):
    """
    Devuelve el recorte, o el texto original si el recorte no dejo nada.

    POR QUE NO SE MARCA NI SE DESCARTA
        Hubo una version que anadia '(sin informacion relevante)' y otra que
        tiraba la nota. Las dos obligan a decidir aqui algo que aqui no se puede
        decidir bien: que una nota no tenga terminologia RECONOCIDA no prueba
        que no diga nada, solo que el vocabulario no la cubre. Todo el historial
        de este proyecto es esa confusion -- 'me cai', 'tengo gripa', 'hta' --
        y cada vez el diccionario tenia el hueco, no la nota.

        Reducir cuando se puede y no tocar cuando no se puede deja esas notas
        reconocibles: son las unicas cuyo texto de embedding coincide con el
        normalizado. Se localizan comparando las dos columnas, sin que nadie
        haya tenido que apostar antes por ellas.
    """
    reducido = str(reducido or '').strip()
    return reducido if reducido else str(original or '').strip()


def _recortar(texto, agresivo=True):
    # El bloque institucional se quita SIEMPRE, tambien en la pasada suave, y
    # por eso va fuera del bloque 'agresivo': la pasada suave existe para
    # rescatar el motivo de consulta cuando la agresiva se lo llevo, y el
    # bloque institucional nunca es el motivo de consulta.
    texto = _quitar_clasificador(texto)
    texto = _quitar_institucional(texto)
    texto = RE_ENCABEZADO.sub(" ", texto)

    # Los tres bloques de la nota larga. Van en la pasada agresiva y tambien en
    # la suave: a diferencia del tramite, ninguno de ellos puede ser nunca el
    # motivo de consulta, asi que quitarlos no arriesga dejar la nota vacia.
    texto = RE_ANTECEDENTES.sub(" ", texto)
    texto = RE_PLURIPATOLOGIA.sub(" ", texto)
    texto = RE_EXAMEN.sub(" ", texto)
    texto = RE_CONDUCTA.sub(" ", texto)
    texto = RE_ACOMPANANTE.sub(" ", texto)
    texto = RE_LLEGADA.sub(" ", texto)
    if cargar_lugares() and RE_LUGAR is not None:
        texto = RE_LUGAR.sub(" ", texto)

    if agresivo:
        texto = RE_TRAMITE.sub(" ", texto)
        texto = RE_REPORTE.sub(" ", texto)
        texto = RE_TEMPORAL.sub(" ", texto)
        texto = RE_DEMOGRAFICO.sub(" ", texto)
    texto = _pulir(texto)

    palabras = _con_contenido(texto)
    if len(palabras) < LONGITUD_MINIMA:
        return ""

    # Plantilla contestada en blanco: al quitarle los encabezados, una nota
    # como 'AP: niega; AA: niega' queda reducida a las respuestas de un
    # formulario sin sus preguntas, que tienen contenido pero no dicen nada.
    if all(p in RESPUESTAS_VACIAS for p in palabras):
        return ""

    # tope por palabras, cortando en el limite de oracion mas cercano para no
    # dejar la frase partida a la mitad
    if len(texto.split()) > TOPE_PALABRAS:
        texto = _cortar(texto, TOPE_PALABRAS)

    return texto


def _cortar(texto, tope):
    """
    Recorta el texto al número de palabras indicado cortando en el límite de
    oración más cercano, para no dejar la frase partida por la mitad.
    """
    oraciones = RE_ORACION.split(texto)
    salida, total = [], 0
    for oracion in oraciones:
        n = len(oracion.split())
        if salida and total + n > tope:
            break
        salida.append(oracion)
        total += n
    if not salida:
        return " ".join(texto.split()[:tope])

    # EL TOPE TIENE QUE APLICARSE IGUAL, Y AQUI ESTABA EL AGUJERO.
    #
    # Cortar en limite de oracion supone que hay limites de oracion. La nota
    # larga de triage es una sola frase separada por comas, de modo que
    # RE_ORACION devolvia un unico tramo, el bucle lo aceptaba entero por ser el
    # primero, y TOPE_PALABRAS no se aplicaba nunca. Medido: con el tope en 60,
    # el texto mas largo del corpus tenia 153 palabras.
    #
    # La primera oracion se acepta siempre porque cortarla dejaria la nota
    # vacia; lo que no puede es quedar sin limite. Se corta por palabras, que es
    # peor estilisticamente y respeta el contrato.
    recortado = " ".join(salida)
    if len(recortado.split()) > tope:
        return " ".join(recortado.split()[:tope])
    return recortado


def diagnosticar(texto):
    """
    El texto tras cada paso del recorte, para ver qué quitó cada uno.
    Herramienta de inspección manual.

    Los pasos deben ser los mismos que aplica _recortar() y en el mismo orden.
    Si divergen, esta función deja de servir para depurar y puede ocultar que un
    paso no se está ejecutando en la corrida real.
    """
    pasos = [("original", texto)]
    t = _quitar_institucional(texto);     pasos.append(("sin institucional", t))
    t = RE_ENCABEZADO.sub(" ", t);        pasos.append(("sin encabezados", t))
    t = RE_ANTECEDENTES.sub(" ", t);      pasos.append(("sin antecedentes", t))
    t = RE_PLURIPATOLOGIA.sub(" ", t);    pasos.append(("sin pluripatologia", t))
    t = RE_EXAMEN.sub(" ", t);            pasos.append(("sin examen fisico", t))
    t = RE_CONDUCTA.sub(" ", t);          pasos.append(("sin conducta", t))
    t = RE_ACOMPANANTE.sub(" ", t);       pasos.append(("sin acompanante", t))
    t = RE_LLEGADA.sub(" ", t);           pasos.append(("sin modo de llegada", t))
    t = RE_TRAMITE.sub(" ", t);           pasos.append(("sin tramite", t))
    if cargar_lugares() and RE_LUGAR is not None:
        t = RE_LUGAR.sub(" ", t);         pasos.append(("sin lugares", t))
    t = RE_REPORTE.sub(" ", t);           pasos.append(("sin verbo de reporte", t))
    t = RE_TEMPORAL.sub(" ", t);          pasos.append(("sin preambulo temporal", t))
    t = RE_DEMOGRAFICO.sub(" ", t);       pasos.append(("sin ficha demografica", t))
    pasos.append(("pulido", _pulir(t)))
    return pasos
