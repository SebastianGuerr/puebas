"""
Fase 5 por reglas: conserva el motivo de consulta y descarta lo que sobra
(bloque institucional, tramite, examen fisico, conducta, antecedentes,
acompanante, lugares, preambulo temporal, ficha demografica). No reescribe la
nota, solo recorta bloques; lo que sobrevive es texto original palabra por
palabra. Ver NLP/docs/FLUJO.md seccion 7 y NLP/docs/ARQUITECTURA.md 2.7.
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

# E5.8: una oracion con terminologia clinica de sobra no se descarta por
# mencionar una institucion. Ver bitacora/2026-09-16-E0.2.md y E5.8.
FRENO_CLINICO_INSTITUCIONAL = True
DENSIDAD_MINIMA = 0.40

# Bandera de E5.1 (docs/decisiones/2026-09-16-E5.1-glosas.md). Por defecto no
# cambia nada: la anotacion entre parentesis que agrego la fase 3 se conserva
# en texto_embedding (ver FLUJO.md seccion 7, "Que se conserva"). Con
# QUITAR_GLOSA=True, recortar() la quita tambien, para medir o usar la opcion
# (b) de la ficha sin tocar fase3_normalizacion.py. Si fase3 ya corrio con
# normalizacion.SEPARAR_CONCEPTO=True esta bandera no tiene nada que hacer,
# porque el texto que le llega ya no trae parentesis.
QUITAR_GLOSA = False

# Bandera de E5.5 (docs/decisiones/2026-09-16-E5.5.md). Por defecto no cambia
# nada: _quitar_clasificador() actua igual que antes. Con USAR_CLASIFICADOR=
# False, _quitar_clasificador() devuelve el texto sin tocarlo aunque haya un
# clasificador entrenado y disponible, para poder medir con y sin el freno
# de frases.py sobre las mismas notas.
USAR_CLASIFICADOR = True

# Bandera de E5.2 (docs/decisiones/2026-09-16-E5.2.md). Antepone NEG_ (nucleo/
# negacion.marcar()) al alcance de cada negacion, como ULTIMO paso de recortar(),
# sobre el texto ya recortado -- no antes: los patrones de esta fase (RE_EXAMEN,
# RE_TRAMITE, MARCADORES_INSTITUCIONALES...) buscan frases literales, y marcar
# antes les cambiaria el texto que buscan y los dejaria de reconocer. Apagada por
# defecto: cambia el contenido de texto_embedding (contrato PLAN.md §7), y el
# gate de esa seccion exige revectorizar y correr `python -m clustering
# --validar` antes de adoptarla en la corrida real -- ninguno de los dos esta al
# alcance de este item. La evidencia medida (contaminacion que corrige, costo en
# tokens) esta en la decision.
USAR_NEGACION = False


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
    # Fecha de inicio por mes o por epoca del mes (no depende de 'hace N
    # dias'): cuando ocurrio la cosa no es el motivo de consulta, y ademas
    # separa dos notas identicas escritas en meses distintos.
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

# Quien acompana al paciente y como llego al servicio: no dice por que
# consulto, y es identico en notas de cuadros opuestos (ruido para el
# agrupamiento). 'en silla de ruedas' se quita aunque describa al paciente: es
# una condicion previa, no el motivo de hoy, y el triage ya la registra aparte.
# Medicion y ejemplo: docs/decisiones/2026-09-16-reduccion-acompanante-llegada.md.
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
# En las notas largas del corpus, lo que sobra son tres bloques -- examen
# fisico, conducta, antecedentes en prosa -- y ninguno responde a por que vino
# el paciente. Medicion y ejemplos:
# docs/decisiones/2026-09-16-reduccion-bloques-nota-larga.md.
#
# Se quitan con patrones de FRASE y no de oracion porque
# _quitar_institucional() descarta oraciones enteras (separa por punto y
# punto y coma), y la nota larga de triage no usa ninguno de los dos: es una
# sola frase corrida separada por comas. Ahi el filtro por oracion es todo o
# nada -- o deja el bloque entero o se lleva la nota entera.

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
# No exige el 'con' delante (corre ANTES que RE_PLURIPATOLOGIA, que puede
# dejarlo sin la preposicion pegada). El tramo esta acotado a 400 caracteres
# porque sin limite, cuando el conector de cierre no aparece, el patron no
# encuentra donde terminar y recorta de menos.
RE_ANTECEDENTES = re.compile(
    r"\b(?:paciente\s+)?(?:con\s+)?antecedentes?\s+(?:de\s+|personales\s+)?"
    r"[^.;]{0,400}?(?=\bcon\s+cuadro\b|\bcuadro\s+cl[ií]nico\b|"
    r"\bquien\s+consulta\b|\bconsulta\s+por\b|\bingresa\b|"
    r"\brefiere\b|\bpresenta\b|\bmanifiesta\b|\bindica\b|[.;])",
    re.IGNORECASE)
#
# Sin '$' entre las alternativas a proposito: si no aparece ningun conector
# de cierre, no se quita nada del bloque. Es preferible arrastrar unos
# antecedentes que borrar el motivo de consulta.

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

    Pliega la palabra igual que se guardó la clave (minúsculas, sin tildes,
    eñe protegida) antes de comparar.
    """
    if _LEXICO is None:
        cargar_lexico()
    if not _LEXICO:
        return False
    import unicodedata
    # la eñe se protege con un caracter de control antes de descomponer los
    # acentos y se restaura despues; ese caracter va literal en la linea de
    # abajo y no se ve al leerlo, asi que conviene no tocarla a ciegas
    plano = "".join(c for c in unicodedata.normalize("NFD", palabra.replace("ñ", ""))
                    if not unicodedata.combining(c)).replace("", "ñ")
    return plano in _LEXICO


def _protegido_por_clinica(tramo):
    """
    True si el tramo habla lo bastante del paciente como para que no pueda ser
    trámite, diga lo que diga el clasificador. Mismo umbral y léxico que usa
    `_quitar_institucional()`, para que las dos defensas del módulo no se
    contradigan. Ver docs/decisiones/2026-09-15-clasificador-freno-clinico.md.
    """
    return densidad_clinica(tramo) >= DENSIDAD_MINIMA


def _quitar_clasificador(texto):
    """
    Quita los tramos que el clasificador de frases da por administrativos,
    ademas de los patrones (no en su lugar: ver
    docs/decisiones/2026-09-16-reduccion-clasificador-cobertura.md). Si lo
    marcado se lleva todos los tramos, devuelve el texto original -- la misma
    regla que `_quitar_institucional()` y por la misma razon.
    """
    from NLP.reduccion import frases

    if not USAR_CLASIFICADOR or not frases.disponible():
        return texto

    tramos = frases.segmentos(texto)
    if len(tramos) < 2:
        return texto

    marcados = frases.burocraticos(tramos)
    if not any(marcados):
        return texto

    # El clasificador propone, la terminologia clinica verifica (mismo
    # principio que extractor.py con el modelo de lenguaje): el clasificador
    # juzga el tramo entero por como EMPIEZA, y un tramo que abre pareciendo
    # tramite puede terminar siendo el motivo de consulta. El tramo se tira
    # entero y no vuelve, asi que su veredicto no basta por si solo. Medicion:
    # docs/decisiones/2026-09-15-clasificador-freno-clinico.md.
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
        # EL MARCADOR PROPONE; LA TERMINOLOGIA VERIFICA.
        #
        # Un marcador institucional tiraba la ORACION ENTERA, y buena parte del
        # corpus no lleva punto ni punto y coma: la "oracion" es toda la nota.
        # Asi, una nota que dice el motivo y ademas menciona la EPS perdia el
        # motivo. Medido sobre las 420 notas que perdian terminologia en la
        # reparacion del 16/09, este paso causaba 189 (34,2%), la mayor fuente
        # de perdida, incluidos 'dolor', 'vomito' y 'episodios'.
        #
        # El freno es el mismo que ya protege a _quitar_clasificador y el mismo
        # criterio que usa extractor.py: un tramo con terminologia clinica de
        # sobra no es tramite, lo mencione o no. Ver E5.8.
        if (any(m in o.lower() for m in MARCADORES_INSTITUCIONALES)
                and not (FRENO_CLINICO_INSTITUCIONAL and _protegido_por_clinica(o))):
            continue
        palabras = _con_contenido(o)
        if len(palabras) >= PALABRAS_ORACION_LARGA and densidad_clinica(o) < DENSIDAD_MINIMA:
            continue
        utiles.append(o)

    # Si no queda nada, se devuelve la nota entera: no es una cautela
    # generica. Las oraciones se separan por punto y punto y coma, y buena
    # parte del corpus no lleva ninguno de los dos (una sola frase corrida),
    # asi que este filtro por oracion es todo o nada. Medicion (229 de 8.000
    # notas quedaban vacias asi):
    # docs/decisiones/2026-09-16-reduccion-institucional-todo-o-nada.md.
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


def _marcar_negacion(texto):
    """
    Antepone NEG_ al alcance de cada negacion de `texto` (E5.2), si
    USAR_NEGACION esta activa. Import diferido: nucleo.negacion no debe
    cargarse si la bandera esta apagada, igual que frases.py con USAR_CLASIFICADOR.
    """
    if not USAR_NEGACION or not texto:
        return texto
    from NLP.nucleo import negacion
    return negacion.marcar(texto)


def recortar(texto, agresivo=True):
    """
    Devuelve la nota sin bloque institucional, sin trámite y sin encabezados,
    en dos pasadas (agresiva y suave, ver `_recortar()` y NLP/docs/FLUJO.md
    sección 7). Solo devuelve cadena vacía si la nota no dice nada del
    paciente; lo que sobrevive es texto original palabra por palabra, con el
    alcance de una negacion marcado si USAR_NEGACION esta activa (E5.2).
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
        return _marcar_negacion(agresiva)

    suave = _recortar(texto, agresivo=False)
    if suave and not crea_costura(texto, suave):
        return _marcar_negacion(suave)

    return _marcar_negacion(sin_reducir(texto, agresiva or suave))


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
    True si el recorte deja juntas dos palabras que no lo estaban en la nota
    (p.ej. 'paciente que consulta por dolor' -> 'paciente que dolor'). No
    enumera que patron corta mal: es una propiedad del resultado, asi que vale
    para los patrones de hoy y los que se añadan mañana. Medicion:
    docs/decisiones/2026-09-16-reduccion-costuras.md.
    """
    return bool(_pares_contiguos(recortado) - _pares_contiguos(original))


def sin_reducir(original, reducido):
    """
    Devuelve el recorte, o el texto original si el recorte no dejo nada.

    No se marca ni se descarta: que una nota no tenga terminologia
    RECONOCIDA no prueba que no diga nada, solo que el vocabulario no la
    cubre. Estas notas quedan identificables porque su texto de embedding
    coincide con el normalizado (comparando ambas columnas).
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
    if QUITAR_GLOSA:
        texto = RE_PARENTESIS.sub(" ", texto)
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

    # El tope se tiene que aplicar igual cuando no hay limite de oracion:
    # cortar en limite de oracion supone que hay limites de oracion, y la nota
    # larga de triage es una sola frase separada por comas (ver
    # docs/decisiones/2026-09-16-reduccion-bloques-nota-larga.md). La primera
    # oracion se acepta siempre porque cortarla dejaria la nota vacia; lo que
    # no puede es quedar sin limite, asi que se corta por palabras.
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
    # Este paso FALTABA y la funcion mentia: _recortar() empieza por el
    # clasificador de frases, asi que todo lo que el quitaba se le atribuia al
    # siguiente paso. Costo un diagnostico equivocado de E0.2: se culpo a
    # _quitar_institucional de 189 perdidas que no eran suyas.
    t = _quitar_clasificador(texto);      pasos.append(("sin clasificador", t))
    t = _quitar_institucional(t);         pasos.append(("sin institucional", t))
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
    if QUITAR_GLOSA:
        t = RE_PARENTESIS.sub(" ", t);    pasos.append(("sin glosa (E5.1)", t))
    pasos.append(("pulido", _pulir(t)))
    return pasos
