"""
Análisis morfológico de terminología clínica.

Reúne todo lo que puede decidirse mirando únicamente la FORMA de una palabra:
sus prefijos y sufijos, si parece un principio activo, y si una corrección
propuesta conserva o altera su significado. No consulta diccionarios, corpus ni
modelos de lenguaje, y por eso no importa nada del resto del paquete: es la capa
más baja, sobre la que se apoyan `nucleo/reglas.py` (qué se protege) y
`fase2_ortografia/terminologia.py` (qué se veta).

El criterio de fondo es que en el vocabulario médico la forma codifica el
significado. 'hipo-' e 'hiper-' se separan por dos letras y son opuestos;
'-ectomía' e '-itis' distinguen un procedimiento de una inflamación. Un corrector
que solo mide distancia de edición no puede ver esa diferencia, y estas funciones
se la aportan.

Contenido del módulo:

    Utilidades de forma      normalizar, sin_tildes, tiene_numero,
                             es_restauracion_tilde
    Morfemas médicos         morfemas, es_termino_medico, prefijos
    Cambios de significado   invierte_significado, cambia_familia,
                             cambia_categoria, es_truncamiento,
                             solo_cambia_terminacion, conserva_morfemas
    Fármacos                 parece_farmaco
"""

import re
import unicodedata

from rapidfuzz.distance import DamerauLevenshtein

# Caracteres que se recortan de los bordes de un token antes de compararlo con
# un diccionario. Incluye + * < > porque la fase de limpieza los conserva como
# contenido clínico, pero pegados al borde siguen siendo puntuación: sin
# recortarlos, 'mejoria+' no coincide con ninguna entrada.
PUNTUACION = ".,;:/%°-\"'()[]{}¿?¡!+*<> "

RE_DIGITO = re.compile(r"\d")

LETRAS_RAIZ = 5   # inicio de palabra que un término médico debe conservar


# ==========================================================
# UTILIDADES DE FORMA
# ==========================================================

def normalizar(token):
    """Recorta la puntuación de los bordes y pasa a minúscula."""
    return str(token).strip(PUNTUACION).lower()


# La 'ñ' se descompone en NFD igual que una vocal acentuada ('n' + U+0303), de
# modo que plegar acentos a ciegas la elimina y fusiona palabras distintas:
# 'ano' y 'año', 'cana' y 'caña', 'pena' y 'peña'. La consecuencia no es solo
# perder un carácter: dos palabras que solo difieren en la eñe pasan a ser una
# restauración de tilde, que es la rama de mayor prioridad al elegir candidato y
# la única que no atraviesa los filtros posteriores. Se protege sustituyéndola
# por un centinela antes de descomponer y restaurándola al final.
_CENTINELA_ENE = "\x01"


def sin_tildes(palabra):
    """
    Pliega los acentos conservando la eñe, que en castellano es una letra
    distinta y no una vocal acentuada.

        'clavícula' -> 'clavicula'
        'año'       -> 'año'
    """
    texto = str(palabra).replace("ñ", _CENTINELA_ENE).replace("Ñ", _CENTINELA_ENE * 2)
    plano = "".join(c for c in unicodedata.normalize("NFD", texto)
                    if not unicodedata.combining(c))
    return plano.replace(_CENTINELA_ENE * 2, "Ñ").replace(_CENTINELA_ENE, "ñ")


def tiene_numero(token):
    """
    True si el token contiene algún dígito.

    Todo lo que lleva un número queda fuera del corrector: dosis, tensiones,
    vértebras, edades y fechas. Alterar '500 mcg' o 'l5' modifica un dato
    clínico, y ninguna mejora ortográfica compensa ese riesgo.
    """
    return bool(RE_DIGITO.search(str(token)))


def es_restauracion_tilde(original, candidato):
    """True si ambas palabras solo se diferencian en la tilde."""
    o, c = str(original).lower(), str(candidato).lower()
    return sin_tildes(o) == sin_tildes(c) and o != c


# ==========================================================
# MORFEMAS MÉDICOS
# ==========================================================

# Morfemas de origen griego y latino que identifican terminología médica. Una
# palabra que los contiene es un término, no un error de digitación, y solo
# admite corregirse hacia otra que comparta los mismos morfemas.
#
# La restricción no impide corregir el typo de un término: 'hipotiroidimo' ->
# 'hipotiroidismo' conserva el prefijo y el sufijo, así que se acepta. Lo que
# bloquea son los pares que cambian el concepto, como 'monoparesia' ->
# 'menopausia' o 'presincope' -> 'sincope'.
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
    """
    Conjunto de morfemas médicos presentes en la palabra, ya sin tildes.
    Devuelve un conjunto vacío si la palabra no es terminología.
    """
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
    """True si la palabra contiene al menos un morfema médico."""
    return bool(morfemas(palabra))


def prefijos(palabra):
    """Prefijos médicos con los que arranca la palabra."""
    palabra = sin_tildes(normalizar(palabra))
    return {p for p in PREFIJOS_MEDICOS
            if palabra.startswith(sin_tildes(p)) and len(palabra) > len(p) + 2}


# ==========================================================
# CAMBIOS QUE ALTERAN EL SIGNIFICADO
# ==========================================================

# Pares de prefijos opuestos. Intercambiar uno por su contrario cuesta una sola
# edición y convierte un hallazgo en el hallazgo inverso: es el error más barato
# de cometer y el más difícil de detectar aguas abajo.
ANTONIMOS = [
    {"hipo", "hiper"}, {"bradi", "taqui"}, {"hemo", "neumo"},
    {"hemo", "hidro"}, {"neumo", "hidro"}, {"sub", "supra"},
    {"pre", "post"}, {"ante", "post"}, {"endo", "exo"},
    {"intra", "extra"}, {"macro", "micro"}, {"poli", "oligo"},
    {"mono", "poli"}, {"mono", "bi"}, {"a", "hiper"},
    {"micro", "mega"}, {"hipo", "normo"}, {"hiper", "normo"},
    {"bradi", "normo"}, {"taqui", "normo"},
]

# Sufijos agrupados por el tipo de hallazgo que designan. Pasar de un grupo a
# otro altera la naturaleza del término: un procedimiento no es una enfermedad,
# y un déficit no es un dolor.
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
    """Nombre de la familia de sufijo a la que pertenece la palabra, o None."""
    palabra = sin_tildes(normalizar(palabra))
    for familia, sufijos in FAMILIAS_SUFIJO.items():
        if any(palabra.endswith(s) for s in sufijos):
            return familia
    return None


def invierte_significado(original, candidato):
    """True si la corrección intercambia un prefijo por su opuesto."""
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


# Terminaciones que en terminología médica marcan un adjetivo (una cualidad del
# paciente) frente a un sustantivo (un diagnóstico o un hallazgo).
# 'taquicárdico' describe cómo está el paciente; 'taquicardia' es la entidad
# clínica. Pasar de uno a otro no arregla la escritura: convierte una
# descripción en un diagnóstico.
#
# Se decide por terminación y no con el etiquetador de spaCy porque sobre
# palabras raras o mal escritas el etiquetador también adivina por la
# terminación, pero de forma opaca: en las pruebas marcaba 'taquicardia' como
# adjetivo y daba por cambio de categoría correcciones válidas. La lista
# explícita es equivalente en precisión y auditable.
SUFIJOS_ADJETIVO = (
    "ico", "ica", "icos", "icas", "oso", "osa", "osos", "osas",
    "al", "ales", "ar", "ares", "ivo", "iva", "ivos", "ivas",
    "il", "iles", "ento", "enta",
)


def es_adjetivo_por_forma(palabra):
    """True si la palabra termina en un sufijo característico de adjetivo."""
    palabra = sin_tildes(normalizar(palabra))
    return any(palabra.endswith(s) for s in SUFIJOS_ADJETIVO)


def cambia_categoria(original, candidato):
    """
    True si uno de los dos es adjetivo por su forma y el otro no.

    Solo se evalúa cuando alguna de las dos palabras es terminología médica. Sin
    ese filtro la regla vetaría correcciones corrientes: 'hospitl' -> 'hospital'
    se rechazaría solo porque el candidato termina en -al.
    """
    if not (es_termino_medico(original) or es_termino_medico(candidato)):
        return False
    return es_adjetivo_por_forma(original) != es_adjetivo_por_forma(candidato)


def es_truncamiento(original, candidato):
    """
    True si una palabra es la otra con un trozo añadido o quitado en un extremo.

    Quitar un prefijo no es una corrección ortográfica: altera o invierte el
    significado ('presincope' -> 'sincope', 'defocalizacion' ->
    'focalizacion'). Un error de digitación no produce este patrón, de modo que
    la regla no bloquea correcciones legítimas.
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
    True si la diferencia está únicamente en la última letra de una palabra
    larga. Es un cambio de género o número, no una corrección:
    'hipoactiva' -> 'hipoactivo' altera la concordancia sin arreglar nada.
    """
    o, c = sin_tildes(original.lower()), sin_tildes(candidato.lower())
    return len(o) >= 7 and len(o) == len(c) and o[:-1] == c[:-1] and o != c


def conserva_morfemas(original, candidato):
    """
    True si el candidato es una corrección admisible del original.

    Cuando el original no es terminología médica no hay restricción. Cuando lo
    es, se exigen dos condiciones:

      a) que el candidato conserve todos sus morfemas. La comparación es por
         inclusión y no por igualdad, para que un typo al que le falta un sufijo
         pueda corregirse: 'hipotiroidimo' {hipo} -> 'hipotiroidismo'
         {hipo, ismo} se acepta, mientras 'presincope' {pre, sincope} ->
         'sincope' {sincope} se rechaza.

      b) que conserve la raíz. 'onicectomia' y 'cistectomia' comparten el sufijo
         -ectomia y son procedimientos distintos; lo que los separa es el inicio
         de la palabra.
    """
    propios = morfemas(original)
    if not propios:
        return True
    if not propios <= morfemas(candidato):
        return False
    return _misma_raiz(sin_tildes(original), sin_tildes(candidato))


def _misma_raiz(original, candidato):
    """
    True si las raíces coinciden, admitiendo una transposición de letras.

    Exigir que los primeros LETRAS_RAIZ caracteres sean idénticos rechazaría el
    typo más frecuente de la terminología médica, que es el intercambio de dos
    letras contiguas dentro de la raíz ('dilispidemia' -> 'dislipidemia'). Se
    admite distancia de edición 1, que cubre la transposición y la letra
    sobrante sin dar paso a raíces distintas.
    """
    a, b = original[:LETRAS_RAIZ], candidato[:LETRAS_RAIZ]
    if a == b:
        return True
    # Al truncar la raíz una transposición se convierte en rotación y su
    # distancia sube a 2, así que se compara además el conjunto de letras. No
    # afloja el criterio: dos raíces realmente distintas no son anagramas.
    if sorted(a) == sorted(b):
        return True
    return DamerauLevenshtein.distance(a, b) <= 1


# ==========================================================
# FÁRMACOS
# ==========================================================

# Terminaciones de la Denominación Común Internacional de principios activos.
# No es un listado de fármacos, sino el conjunto de raíces que la OMS asigna por
# familia, de modo que cubre tanto los medicamentos existentes como los que se
# incorporen después sin tener que enumerarlos.
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
    internacional. Protege por forma y sin lista de nombres, de modo que
    cualquier -pril, -sartan, -azepam, -micina o -prazol queda cubierto.
    """
    palabra = sin_tildes(normalizar(palabra))
    if len(palabra) < LONGITUD_MINIMA_FARMACO:
        return False
    return any(palabra.endswith(sin_tildes(s)) for s in SUFIJOS_FARMACO)
