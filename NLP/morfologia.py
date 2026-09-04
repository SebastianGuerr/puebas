"""
Morfologia clinica: que forma tiene una palabra y que significa esa forma.

POR QUE EXISTE ESTE ARCHIVO
    El conocimiento morfologico estaba repartido entre reglas.py (prefijos y
    sufijos medicos, truncamiento, conservacion de raiz) y terminologia.py
    (antonimos, familias de sufijo, sufijos de farmaco). Las dos mitades se
    llamaban entre si, asi que para seguir una decision habia que saltar de un
    archivo a otro, y ninguno de los dos se podia leer entero de una sentada.

    Aca vive todo lo que se puede decidir mirando UNICAMENTE la forma de la
    palabra, sin diccionario, sin corpus y sin spaCy. Por eso este modulo no
    importa nada del proyecto: es la base sobre la que se apoyan reglas.py
    (que decide que se protege) y terminologia.py (que decide que se veta).

EL PRINCIPIO
    La forma de un termino medico no es decorativa: codifica el significado.
    'hipo' y 'hiper' se diferencian en dos letras y son opuestos. '-ectomia' y
    '-itis' se diferencian en el sufijo y son un procedimiento y una
    inflamacion. Un corrector ortografico que solo mide distancia de edicion no
    puede ver eso; estas funciones se lo dicen.
"""

import re
import unicodedata

# Se incluyen + * < > desde que limpieza.py dejo de borrarlos: son contenido
# clinico dentro de la nota, pero pegados al borde de un token siguen siendo
# puntuacion, y sin quitarlos 'hvda?' y 'mejoria+' no coincidian con el
# diccionario ni con el lexico del corpus.
PUNTUACION = ".,;:/%°-\"'()[]{}¿?¡!+*<> "

RE_DIGITO = re.compile(r"\d")

LETRAS_RAIZ = 5   # inicio de palabra que un termino medico debe conservar


# ==========================================================
# UTILIDADES DE FORMA
# ==========================================================

def normalizar(token):
    """Quita la puntuacion de los bordes y pasa a minuscula."""
    return str(token).strip(PUNTUACION).lower()


def sin_tildes(palabra):
    return "".join(c for c in unicodedata.normalize("NFD", str(palabra))
                   if not unicodedata.combining(c))


def tiene_numero(token):
    """
    Cualquier token con un digito queda intacto: dosis, tensiones, vertebras,
    edades, fechas. Corregir '500 mcg' o 'l5' cambia un dato clinico, y ningun
    beneficio ortografico compensa ese riesgo.
    """
    return bool(RE_DIGITO.search(str(token)))


def es_restauracion_tilde(original, candidato):
    """True si la unica diferencia es la tilde. Nunca cambia el concepto."""
    o, c = str(original).lower(), str(candidato).lower()
    return sin_tildes(o) == sin_tildes(c) and o != c


# ==========================================================
# MORFEMAS MEDICOS
# ==========================================================

# Morfemas de origen griego y latino que marcan terminologia medica. Una palabra
# que los contiene es un termino, no un descuido de digitacion, y solo puede
# corregirse hacia otra palabra que comparta los MISMOS morfemas.
#
# Sin esta regla el corrector producia, sobre terminos raros del corpus:
#     monoparesia    -> menopausia        hemoperitoneo -> neumoperitoneo
#     onicectomia    -> cistectomia       presincope    -> sincope
#     subsegmentaria -> segmentaria
# Todos son cambios de significado clinico, no correcciones.
#
# La regla no bloquea el typo de un termino medico: 'hipotiroidimo' ->
# 'hipotiroidismo' comparte el prefijo 'hipo' y el sufijo 'ismo', asi que pasa.
PREFIJOS_MEDICOS = (
    "mono", "hemi", "hemo", "hema", "neumo", "pneumo", "onico", "oligo", "poli",
    "hiper", "hipo", "taqui", "bradi", "dis", "sub", "supra", "infra", "peri",
    "endo", "epi", "exo", "intra", "inter", "retro", "ante", "pre", "post",
    "para", "meta", "macro", "micro", "mega", "cardio", "gastro", "hepato",
    "nefro", "neuro", "osteo", "artro", "mio", "dermo", "oftalmo", "oto",
    "rino", "laringo", "broncho", "bronco", "colo", "procto", "uro", "cisto",
    "histero", "ooforo", "orquio", "angio", "flebo", "linfo", "adeno", "cito",
    "leuco", "eritro", "trombo", "quimio", "radio", "electro", "ecto", "auto",
)
SUFIJOS_MEDICOS = (
    "ectomia", "ectomía", "otomia", "otomía", "ostomia", "ostomía", "plastia",
    "pexia", "rafia", "scopia", "scopía", "grafia", "grafía", "grama", "metria",
    "metría", "paresia", "plejia", "plejía", "patia", "patía", "algia", "dinia",
    "itis", "osis", "iasis", "emia", "uria", "penia", "citosis", "megalia",
    "esclerosis", "estenosis", "trofia", "plasia", "genesis", "génesis",
    "pnea", "fagia", "fasia", "praxia", "gnosia", "estesia", "termia",
    "peritoneo", "torax", "tórax", "cardia", "sincope", "síncope", "ismo",
)


def morfemas(palabra):
    """Morfemas medicos presentes en una palabra. Vacio si no es terminologia."""
    palabra = sin_tildes(str(palabra).lower())
    encontrados = set()
    for prefijo in PREFIJOS_MEDICOS:
        if palabra.startswith(sin_tildes(prefijo)) and len(palabra) > len(prefijo) + 2:
            encontrados.add(sin_tildes(prefijo))
    for sufijo in SUFIJOS_MEDICOS:
        if palabra.endswith(sin_tildes(sufijo)) and len(palabra) > len(sufijo) + 2:
            encontrados.add(sin_tildes(sufijo))
    return encontrados


def es_termino_medico(palabra):
    return bool(morfemas(palabra))


def prefijos(palabra):
    """Prefijos medicos con los que arranca la palabra."""
    palabra = sin_tildes(normalizar(palabra))
    return {p for p in PREFIJOS_MEDICOS
            if palabra.startswith(sin_tildes(p)) and len(palabra) > len(p) + 2}


# ==========================================================
# CAMBIOS QUE ALTERAN EL SIGNIFICADO
# ==========================================================

# Intercambiar uno de estos prefijos por su opuesto cuesta una sola edicion y
# convierte un hallazgo en su contrario. Es el error mas barato de cometer y el
# mas caro de detectar aguas abajo.
ANTONIMOS = [
    {"hipo", "hiper"}, {"bradi", "taqui"}, {"hemo", "neumo"},
    {"hemo", "hidro"}, {"neumo", "hidro"}, {"sub", "supra"},
    {"pre", "post"}, {"ante", "post"}, {"endo", "exo"},
    {"intra", "extra"}, {"macro", "micro"}, {"poli", "oligo"},
    {"mono", "poli"}, {"mono", "bi"}, {"a", "hiper"},
    {"micro", "mega"}, {"hipo", "normo"}, {"hiper", "normo"},
    {"bradi", "normo"}, {"taqui", "normo"},
]

# Sufijos que designan cosas de distinta naturaleza. Cambiar entre ellos altera
# el tipo de hallazgo: un procedimiento no es una enfermedad.
FAMILIAS_SUFIJO = {
    "procedimiento": {"ectomia", "otomia", "ostomia", "plastia", "pexia",
                      "rafia", "scopia", "grafia", "grama", "metria"},
    "inflamacion": {"itis"},
    "degeneracion": {"osis", "patia", "esclerosis", "estenosis"},
    "dolor": {"algia", "dinia"},
    "deficit": {"paresia", "plejia", "penia", "fasia", "praxia", "gnosia"},
    "sangre_orina": {"emia", "uria"},
    "respiracion": {"pnea"},
    "tamano": {"megalia", "trofia", "plasia"},
}


def familia_sufijo(palabra):
    palabra = sin_tildes(normalizar(palabra))
    for familia, sufijos in FAMILIAS_SUFIJO.items():
        if any(palabra.endswith(s) for s in sufijos):
            return familia
    return None


def invierte_significado(original, candidato):
    """True si el cambio intercambia un prefijo por su opuesto."""
    po, pc = prefijos(original), prefijos(candidato)
    if po == pc:
        return False
    for par in ANTONIMOS:
        if (po & par) and (pc & par) and (po & par) != (pc & par):
            return True
    return False


def cambia_familia(original, candidato):
    """True si el sufijo pasa a designar otro tipo de hallazgo."""
    fo, fc = familia_sufijo(original), familia_sufijo(candidato)
    if fo is None or fc is None:
        return False
    return fo != fc


# Terminaciones que en terminologia medica marcan un adjetivo (una cualidad
# del paciente) frente a un sustantivo (un diagnostico o un hallazgo).
# 'taquicardico' describe COMO esta el paciente; 'taquicardia' es la entidad
# clinica. Cambiar de uno a otro no arregla la escritura, convierte una
# descripcion en un diagnostico.
#
# POR QUE NO SE USA EL ETIQUETADOR DE spaCy
#     Se probo. Sobre estos mismos pares, es_core_news_md etiqueta
#     'taquicardia' como ADJ (es sustantivo), 'cardioacular' como VERB, y
#     marcaria 'hipotiroidimo' -> 'hipotiroidismo' como cambio de categoria
#     cuando es una correccion buena. Sobre palabras raras o mal escritas el
#     etiquetador adivina por la terminacion, que es justo lo que se hace aca
#     de forma explicita y auditable.
SUFIJOS_ADJETIVO = (
    "ico", "ica", "icos", "icas", "oso", "osa", "osos", "osas",
    "al", "ales", "ar", "ares", "ivo", "iva", "ivos", "ivas",
    "il", "iles", "ento", "enta",
)


def es_adjetivo_por_forma(palabra):
    palabra = sin_tildes(normalizar(palabra))
    return any(palabra.endswith(s) for s in SUFIJOS_ADJETIVO)


def cambia_categoria(original, candidato):
    """
    True si uno de los dos es adjetivo por su forma y el otro no.

    Solo se aplica cuando alguna de las dos palabras es terminologia medica.
    Sin ese filtro la regla vetaria correcciones corrientes: un typo como
    'hospitl' -> 'hospital' pasaria por cambio de categoria solo porque el
    candidato termina en -al.
    """
    if not (es_termino_medico(original) or es_termino_medico(candidato)):
        return False
    return es_adjetivo_por_forma(original) != es_adjetivo_por_forma(candidato)


def es_truncamiento(original, candidato):
    """
    True si el candidato es el original al que se le quito (o agrego) un trozo
    al principio o al final.

    Quitar un prefijo nunca es una correccion ortografica: cambia o invierte el
    significado. Es la regla que faltaba para:
        defocalizacion -> focalizacion   (invierte un hallazgo neurologico)
        presincope     -> sincope
        subsegmentaria -> segmentaria
    Un typo de digitacion no produce este patron: 'deirva'->'deriva' o
    'pacinete'->'paciente' no son truncamientos.
    """
    o, c = sin_tildes(original.lower()), sin_tildes(candidato.lower())
    if o == c or not o or not c:
        return False
    largo, corto = (o, c) if len(o) > len(c) else (c, o)
    if len(largo) - len(corto) < 1:
        return False
    return largo.endswith(corto) or largo.startswith(corto)


def solo_cambia_terminacion(original, candidato):
    """
    True si la diferencia esta unicamente en la ultima letra de una palabra
    larga: es un cambio de genero o numero, no una correccion ortografica.
    'hipoactiva' -> 'hipoactivo' altera la concordancia sin arreglar nada.
    """
    o, c = sin_tildes(original.lower()), sin_tildes(candidato.lower())
    return len(o) >= 7 and len(o) == len(c) and o[:-1] == c[:-1] and o != c


def conserva_morfemas(original, candidato):
    """
    True si el candidato es una correccion admisible del original.

    Si el original no es terminologia medica, no hay restriccion. Si lo es, se
    exigen dos cosas:

      a) que el candidato conserve todos sus morfemas. Se compara por inclusion
         y no por igualdad, para que un typo al que le falta un sufijo se pueda
         corregir: hipotiroidimo{hipo} -> hipotiroidismo{hipo, ismo} pasa,
         mientras presincope{pre, sincope} -> sincope{sincope} no.

      b) que conserve el inicio de la palabra. 'onicectomia' y 'cistectomia'
         comparten el sufijo -ectomia y son procedimientos distintos; la raiz
         es lo que los separa.
    """
    propios = morfemas(original)
    if not propios:
        return True
    if not propios <= morfemas(candidato):
        return False
    return sin_tildes(original)[:LETRAS_RAIZ] == sin_tildes(candidato)[:LETRAS_RAIZ]


# ==========================================================
# FARMACOS
# ==========================================================

# Terminaciones de la nomenclatura internacional de principios activos (DCI).
# No son una lista de farmacos: son las raices que la OMS asigna por familia, y
# por eso cubren los que existen y los que salgan manana sin tener que
# enumerarlos. 'midazolam', 'topiramato', 'olanzapina', 'losartan', 'enalapril'
# y cualquier otro de su familia quedan protegidos por su forma.
SUFIJOS_FARMACO = (
    "pril", "sartan", "sartán", "olol", "azepam", "zepam", "azolam", "zolam",
    "barbital", "micina", "ciclina", "cilina", "penem", "oxacino",
    "floxacino", "azol", "conazol", "prazol", "tidina", "statina", "vastatina",
    "fibrato", "glitazona", "gliptina", "formina", "glinida", "mab", "nib",
    "tinib", "ximab", "zumab", "profeno", "fenaco", "coxib", "caina", "caína",
    "curonio", "tropina", "parina", "plina", "filina", "terol", "sterol",
    "cortisona", "solona", "metasona", "onida", "tadina", "rizina", "setron",
    "prida", "peridol", "piramato", "racetam", "gabina", "triptan", "triptán",
    "dipino", "diltiazem", "digoxina", "warfarina", "dopa", "morfina", "fentanilo",
    "codona", "tramadol", "naloxona", "flumazenil", "sulfato", "cloruro",
    "apina", "zapina", "tiazida", "amol", "utamol", "idona", "ridona",
    "irona", "azina", "acina", "arina", "asona", "olona",
    "cetamol", "cetaminofen", "oprolol", "azida", "emida", "actona",
)

LONGITUD_MINIMA_FARMACO = 6


def parece_farmaco(palabra):
    """
    True si la palabra termina como un principio activo de la nomenclatura
    internacional. Protege por forma, sin lista: cualquier -pril, -sartan,
    -azepam, -micina, -oxacino o -prazol que aparezca queda cubierto.
    """
    palabra = sin_tildes(normalizar(palabra))
    if len(palabra) < LONGITUD_MINIMA_FARMACO:
        return False
    return any(palabra.endswith(sin_tildes(s)) for s in SUFIJOS_FARMACO)
