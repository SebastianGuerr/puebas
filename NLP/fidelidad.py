# -*- coding: utf-8 -*-
"""Detectores de alucinacion: comparan la salida del modelo con la nota original.

Cada detector mira UNA forma concreta de inventar, y todos son deterministas:
la misma nota con la misma salida da siempre las mismas banderas. Por que estos
y no otros, y con que evidencia: NLP/docs/EVALUACION.md.

    fuertes  (una sola basta para llamar fallo a una salida)
        queja_sin_sintoma    nota de tramite sin ningun sintoma, salida con queja
        copia_de_ejemplo     la salida repite un ejemplo del prompt sin respaldo
        numero_inventado     un numero en la salida que no esta en la nota
        lado_inventado       derecha/izquierda sin que la nota diga el lado
        cuerpo_inventado     una parte del cuerpo que la nota no nombra
        descarte_falso       'sin motivo clinico' en una nota con sintomas
        frase_comodin        la misma salida desde notas distintas, sin base
        formato              salida vacia o demasiado larga
        embarazo_perdido     la nota dice gestante y la salida lo pierde (regla 6)
        duda_a_certeza       'creo que', 'sospecha de' -> afirmado como hecho (regla 7)
        negacion_perdida     'niega X' -> X afirmado, o 'niega' deformado (regla 6)
        duracion_cambiada    'antier' -> 'ayer', '3 dias' -> '2 dias' (regla 6)
        identificador_en_salida  nombre tras dr/sra o institucion de salud (regla 4)

    suave
        poca_base            la mayoria de las palabras de la salida no estan
                             en la nota ni en el glosario. Solo 'sospechosa':
                             traducir coloquialismos es justo lo que se le pide
"""
import re
import unicodedata
from collections import defaultdict
from difflib import SequenceMatcher

from functools import lru_cache

from NLP import glosario as _glosario


class glosario:
    """El glosario con memoria. Cada nota se consulta tres veces (base, evidencia
    clinica, estrato) y cada consulta recorre cientos de expresiones: sin esto,
    armar los bancos tardaba ~15 minutos."""
    buscar = staticmethod(lru_cache(maxsize=None)(_glosario.buscar))
    buscar_terminos_clinicos = staticmethod(lru_cache(maxsize=None)(_glosario.buscar_terminos_clinicos))

SIN_MOTIVO = "sin motivo clinico"
LARGO_MAXIMO = 200
FUERTES = ["queja_sin_sintoma", "copia_de_ejemplo", "numero_inventado", "lado_inventado",
           "cuerpo_inventado", "descarte_falso", "frase_comodin", "formato",
           # 2026-09-23, barrido de 3.087 notas: cada una se dio por fuerte despues
           # de LEER todo lo que marcaba (precision leida en EVALUACION.md)
           "embarazo_perdido", "duda_a_certeza", "negacion_perdida", "duracion_cambiada",
           "identificador_en_salida"]

# Las notas vienen con erratas ('derehco', 'abdoiminal', 'iquierda'). El modelo
# las corrige bien, y compararlas al pie de la letra marcaba como inventado justo
# lo que la nota si decia. Dos palabras de 5+ letras con este parecido cuentan
# como la misma.
PARECIDO_ERRATA = 0.8


def _parecida(palabra, objetivo):
    return SequenceMatcher(None, palabra, objetivo).ratio() >= PARECIDO_ERRATA


def plano(texto):
    """Minusculas y sin tildes."""
    texto = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def palabras(texto):
    return re.findall(r"[a-z0-9]+", plano(texto))


# ==========================================================
# LO QUE LA NOTA AUTORIZA A DECIR
# ==========================================================

def base(original):
    """
    Las palabras que la salida puede usar sin inventar: las de la nota mas los
    significados que el glosario del hospital le asigna a ESA nota. Sin el
    glosario, cada coloquialismo bien traducido saldria como alucinacion.
    """
    trozos = [original]
    halladas, _, erratas = glosario.buscar(original)
    trozos += [significado for _, significado in halladas]
    trozos += [correcta for _, correcta in erratas]
    trozos += glosario.buscar_terminos_clinicos(original)
    return set(palabras(" ".join(str(t) for t in trozos)))


def _esta(raiz, vocabulario, errata=False):
    """Raiz larga: prefijo. Raiz corta (pie, ojo, dedo): palabra exacta, porque
    'pie' como prefijo encontraria 'piel' y 'pierna'.

    Con errata=True, una raiz larga tambien se da por presente si alguna palabra
    empieza parecido ('abdoi' por 'abdom'). Se usa del lado de la NOTA, que es la
    que trae erratas; la salida del modelo sale bien escrita."""
    if len(raiz) <= 4:
        return raiz in vocabulario or raiz + "s" in vocabulario
    if any(p.startswith(raiz) for p in vocabulario):
        return True
    return errata and any(len(p) >= len(raiz) and _parecida(p[:len(raiz) + 1], raiz)
                          for p in vocabulario)


# ==========================================================
# DETECTORES
# ==========================================================

_NUMEROS_ESCRITOS = {
    "un": "1", "uno": "1", "una": "1", "dos": "2", "tres": "3", "cuatro": "4",
    "cinco": "5", "seis": "6", "siete": "7", "ocho": "8", "nueve": "9",
    "diez": "10", "doce": "12", "quince": "15", "veinte": "20", "treinta": "30",
    "ayer": "1", "anoche": "1", "antier": "2", "anteayer": "2",
}


def numero_inventado(original, salida):
    # Un numero pegado a una palabra es parte de un nombre, no una duracion:
    # 'covid-19', 'sars-cov-2', 'vih1'. Falso positivo real de la sonda.
    sin_nombres = re.sub(r"\b[a-z]+-?\d+\b", " ", plano(salida))
    numeros = set(re.findall(r"\d+", sin_nombres))
    if not numeros:
        return False
    en_nota = set(re.findall(r"\d+", plano(original)))
    en_nota |= {v for k, v in _NUMEROS_ESCRITOS.items() if k in palabras(original)}
    # 'ayer' autoriza tambien las 24 horas
    if "1" in en_nota:
        en_nota.add("24")
    return not numeros <= en_nota


_LADO_SALIDA = re.compile(r"derech|izquierd")
# Siglas del hospital que llevan el lado dentro: miembro superior/inferior
# derecho/izquierdo, ojo, hemitorax, fosa iliaca, hemicuerpo.
_LADO_NOTA = re.compile(r"derech|izquierd|\bder\b|\bizq|\bdcho|\bdcha|\bizdo|\bizda|diestr|zurd|"
                        r"\bms[di]\b|\bmi[di]\b|\bo[di]\b|\bh[di]\b|\bhc[di]\b|\bfi[di]\b|\bhtd\b|\bhti\b")
_LADOS = ("derecho", "derecha", "izquierdo", "izquierda")


def lado_inventado(original, salida):
    if not _LADO_SALIDA.search(plano(salida)):
        return False
    nota = plano(original)
    if _LADO_NOTA.search(nota):
        return False
    return not any(_parecida(p, lado) for p in palabras(nota) if len(p) >= 5 for lado in _LADOS)


# Grupos de partes del cuerpo. Dos palabras del mismo grupo cuentan como la
# misma parte: 'cefalea' esta autorizada por 'dolor de cabeza', 'toracico' por
# 'pecho'. Lo que se detecta es la parte del cuerpo que aparece de la nada.
PARTES = {
    "abdomen": ["abdom", "barriga", "estomag", "panza", "vientre", "epigastr",
                "hipogastr", "mesogastr", "periumbilic", "ombligo", "flanco",
                "hipocondri", "iliaca", "gastr", "colico"],
    "cabeza": ["cabeza", "cefal", "craneo", "craneal", "frente", "occipit", "migran"],
    "torax": ["torax", "torac", "pecho", "precordi", "costal", "costill", "esternon"],
    "espalda": ["espalda", "lumbar", "lumbalg", "dorsal", "columna"],
    "cuello": ["cuello"],
    "cara": ["cara", "mejilla", "facial", "rostro", "menton", "mandibul", "pomulo"],
    "ojo": ["ojo", "ocular", "oftalm", "parpado", "conjuntiv", "vista", "vision"],
    "oido": ["oido", "otalg", "oreja", "otitis"],
    "garganta": ["garganta", "faring", "odinofag", "amigdal"],
    "nariz": ["nariz", "nasal", "epistax"],
    "boca": ["boca", "dental", "diente", "muela", "encia", "labio", "lengua", "odontalg"],
    # 'una' (uña sin tilde) no entra: choca con el articulo y marcaria cualquier
    # 'una herida' como una mano inventada.
    "mano": ["mano", "manos", "dedo", "dedos", "muneca", "palma", "falange", "pulgar", "ungueal"],
    "brazo": ["brazo", "antebrazo", "codo", "hombro", "humero"],
    "pierna": ["pierna", "rodilla", "muslo", "tobillo", "pie", "pies", "pantorrilla",
               "femur", "tibia", "cadera", "talon", "gemelo"],
    "genital": ["vagin", "pene", "testic", "escroto", "vulva", "genital"],
}


# Palabras de la nota que implican una parte del cuerpo sin nombrarla. Salieron
# de revisar a mano las salidas marcadas: 'congestionado' -> 'congestion nasal' o
# 'dolor en el corazon' -> 'dolor en el pecho' son traducciones, no invenciones.
_IMPLICA = {
    "corazon": "torax", "congest": "nariz", "gripa": "nariz", "reflujo": "abdomen",
    "gastrit": "abdomen", "inguin": "abdomen", "hernia": "abdomen", "colitis": "abdomen",
    "vomit": "abdomen", "emesis": "abdomen", "diarre": "abdomen", "estrenim": "abdomen",
}


def cuerpo_inventado(original, salida, vocabulario=None):
    """Devuelve la lista de partes que la salida nombra y la nota no."""
    vocabulario = vocabulario if vocabulario is not None else base(original)
    implicadas = {parte for raiz, parte in _IMPLICA.items() if _esta(raiz, vocabulario, errata=True)}
    en_salida = set(palabras(salida))
    inventadas = []
    for parte, raices in PARTES.items():
        if parte in implicadas:
            continue
        if (any(_esta(r, en_salida) for r in raices)
                and not any(_esta(r, vocabulario, errata=True) for r in raices)):
            inventadas.append(parte)
    return inventadas


_SINTOMA = re.compile(
    r"dolor|duel|dolid|fiebre|febril|termic|\btos\b|vomit|emesis|diarre|sangr|hemorrag|"
    r"mare[oa]|cefal|trauma|golpe|golpi|caid|\bcai\b|\bcayo\b|herid|cort[aeoó]|quem|"
    r"fractur|fisur|ahog|disnea|respir|convuls|desmay|pic[oóa]|picad|mord|intoxic|"
    r"hinch|inflam|brote|ardor|nause|palpitac|adormec|debilid|malestar|gripa|congest|"
    r"machuc|aplast|torc|esguinc|luxac|absces|edema|rasquiñ|rasquin|prurit|picazon|"
    r"alerg|ronch|gastro|infecc|colic|calcul|presion|tension|azucar|glucos|sincop|"
    r"desalient|nauseas|estreñ|estren|orina|embaraz|contracc|sangrad|flujo|"
    r"ansied|depres|suicid|agitad|convulsi|accident|atropell|choque|mordi|"
    r"dolencia|molest|enferm|\bmal\b|maluc|sintom|zarpull|sarpull|erupc|lesion|mancha|"
    r"granit|ampoll|verrug|herpes|hongo|picor|irritac|"
    # 'remitida por el dr X por hernia discal' salio descartada en la sonda
    # ampliada (2026-09-23) sin que nada lo marcara: no conocia la palabra
    r"hernia|discal|ciatic|tumor|cancer|\bca\b|oncolog|quimio|dialisis|fistula|cateter|"
    r"sonda|protesis|turbin|amigdal|apendic|vesicul|hemorroid|migran|epileps|diabet|"
    # procedimientos por su sufijo: 'turbionoplastia' (con errata) salio descartada
    # en la sonda del 14B sin que nada lo marcara
    r"plastia|ectomi|otomi|oscopi|biopsi|quirurg|operac|"
    # embarazo: 'primigestante que consulta por control' tiene motivo aunque no
    # nombre un sintoma (falso positivo real de la sonda, 2026-09-23)
    r"gestac|gestant|primigest|secundigest|trigest|multigest|prenatal|parto|puerper|"
    r"\bfum\b|\bg/?o\b|obstetr|ginecol|"
    # falsos positivos reales del filtro de tramite (2026-09-23): tienen motivo
    r"amarill|borrach|ebri|alcohol|licor|embriag|aborto|operar|operaron|operad|cirug|"
    r"\bcx\b|postop|pop\b|puntos|sutur|curacion|drenaje|"
    r"inchad|\barde\b|mocos|tembl|asfix|asifix|ahoga|\bno mejora\b")

# Erratas de los sintomas mas comunes ('amreo' por 'mareo'). Si una palabra de la
# nota se parece a alguno, la nota tiene algo clinico.
_SINTOMAS_COMUNES = ["mareo", "dolor", "fiebre", "vomito", "diarrea", "cefalea", "sangrado",
                     "gripa", "tos", "herida", "golpe", "caida", "nauseas", "desmayo"]


def _sintoma_con_errata(nota):
    return any(_parecida(p, s) for p in palabras(nota) if len(p) >= 4
               for s in _SINTOMAS_COMUNES if abs(len(p) - len(s)) <= 2)

# Nombres de servicios que llevan una palabra de sintoma dentro y no lo son.
_SERVICIOS = re.compile(r"medicina del dolor|clinica del dolor|clinica de heridas|"
                        r"programa de heridas|unidad de dolor")


def evidencia_clinica(original):
    """Si la nota trae ALGO clinico: un sintoma, una lesion, o un termino del
    catalogo. Una nota que solo documenta una remision no lo trae."""
    # El glosario se consulta con la nota YA sin nombres de servicio: si no,
    # 'medicina del dolor' le devuelve el termino 'dolor'.
    nota = _SERVICIOS.sub(" ", plano(original))
    if _SINTOMA.search(nota) or _sintoma_con_errata(nota):
        return True
    if glosario.buscar_terminos_clinicos(nota):
        return True
    vocabulario = set(palabras(nota))
    return any(_esta(r, vocabulario, errata=True) for raices in PARTES.values() for r in raices)


def descarte_falso(original, salida):
    return plano(salida).strip() == SIN_MOTIVO and evidencia_clinica(original)


_TRAMITE = re.compile(r"remit|remision|deriv|traslad|acept|referencia|contrarrefer|ambulancia|"
                      r"\bcita\b|consulta externa|enviad|mandad|\bpor orden\b|autoriz|"
                      r"\bcama\b|hospitaliz|valoracion por|interconsulta")


def necesita_segunda_pasada(original, salida):
    """
    La red de seguridad contra el peor error: un descarte ('sin motivo clinico')
    en una nota que si trae algo clinico. Ese paciente saldria de la cuenta.

    Medido el 2026-09-24: los descartes falsos son INESTABLES -- la misma nota
    salio bien en una corrida y descartada en otra, con el mismo modelo y prompt.
    No se arreglan con mas prompt: se repite la nota con un prompt que no permite
    abstenerse (construir_segunda_pasada del modulo de prompt), y si aun asi se
    descarta, queda marcada para revision humana. Ver NLP/cadena.py.
    """
    return descarte_falso(original, salida)


def queja_sin_sintoma(original, salida, base_salida=None):
    """La familia de alucinacion mas grande medida el 2026-09-23: una nota de
    tramite ('remitido de otro municipio', 'traida en ambulancia') o cortada
    ('tengo') recibe una queja clinica completa que no esta en ninguna parte.

    Exige las TRES condiciones. La primera version exigia solo la segunda
    -- 'no encuentro ninguna palabra de sintoma' -- y marco 408 notas, casi todas
    correctas ('hemorroides', 'sonda tapada', 'ictericia neonatal'): el vocabulario
    clinico es abierto y ninguna lista lo cubre. No encontrar un sintoma no
    prueba que no lo haya; por eso se busca la senal POSITIVA de tramite."""
    s = plano(salida).strip()
    if not s or s == SIN_MOTIVO:
        return False
    nota = plano(original)
    contenido = [p for p in palabras(nota) if p not in _VACIAS and len(p) > 2]
    tramite_o_cortada = bool(_TRAMITE.search(nota)) or len(contenido) <= 1
    if not tramite_o_cortada or evidencia_clinica(original):
        return False
    base_salida = base_salida if base_salida is not None else base_de_salida(original, salida)
    return base_salida < 0.5


def es_tramite_puro(original, salida):
    """
    Mas estricto que queja_sin_sintoma, porque este lo usa un FILTRO que borra.

    Exige la senal positiva de tramite (remision, derivacion, ambulancia...). Las
    notas cortas quedan fuera a proposito: medido el 2026-09-23, 'me arde',
    'esta temblando' o 'esta con mocos' son una o dos palabras y son motivos
    reales. Borrar uno de esos saca al paciente de la cuenta, que es el peor error.
    """
    s = plano(salida).strip()
    if not s or s == SIN_MOTIVO:
        return False
    if not _TRAMITE.search(plano(original)) or evidencia_clinica(original):
        return False
    return base_de_salida(original, salida) < 0.5


# Los ejemplos del prompt v1.6 que el modelo copia cuando no tiene de donde sacar
# nada. Cada uno con lo que la nota tendria que decir para que fuera legitimo.
_EJEMPLOS_DEL_PROMPT = [
    # 'machuque' se escribe con q: machucar -> machuque
    (re.compile(r"aplastamiento|machu[cq]"),
     re.compile(r"machu[cq]|aplast|prens|apret|\bcolo\b|atrap|majad")),
    (re.compile(r"cifras tensionales elevadas"), re.compile(r"presion|tension|\bta\b|hipertens")),
    (re.compile(r"mordedura"), re.compile(r"mord")),
    (re.compile(r"cortad|herida cortante|corte"), re.compile(r"cort|herid|vidrio|cuchill|machete")),
    (re.compile(r"morad"), re.compile(r"morad|moret|equimo|hematom")),
]
_PRESION_BAJA = re.compile(r"(baj[oó]|bajit|baja)\w*\s+(la\s+)?(presion|tension)|(presion|tension)\s+baj|hipotens")


def copia_de_ejemplo(original, salida):
    s, nota = plano(salida), plano(original)
    for en_salida, respaldo in _EJEMPLOS_DEL_PROMPT:
        if en_salida.search(s) and not respaldo.search(nota):
            return True
    # 'se le bajo la presion' -> 'cifras tensionales elevadas': el ejemplo copiado
    # y ademas invertido
    return "elevad" in s and bool(_PRESION_BAJA.search(nota))


def formato(salida):
    texto = str(salida or "").strip()
    return not texto or len(texto) > LARGO_MAXIMO


_VACIAS = set("""de del la el las los en por con y a al un una unos unas sin desde hace se
que para o u su sus lo le les es no mas muy tambien pero como ya este esta ese esa
motivo consulta paciente refiere presenta cuadro inespecifico general""".split())


def base_de_salida(original, salida, vocabulario=None):
    """Fraccion de las palabras con contenido de la salida que tienen base."""
    vocabulario = vocabulario if vocabulario is not None else base(original)
    contenido = [p for p in palabras(salida) if p not in _VACIAS and not p.isdigit() and len(p) > 2]
    if not contenido:
        return 1.0
    raiz = lambda p: p[:5]
    con_base = sum(any(v.startswith(raiz(p)) or p.startswith(v[:5]) for v in vocabulario if len(v) > 2)
                   for p in contenido)
    return con_base / len(contenido)


# ==========================================================
# LO QUE CAMBIA LA PRIORIDAD: embarazo, duda, negacion, duracion
# ==========================================================
#
# Los detectores de arriba miran lo que la salida AGREGA. Estos miran lo que la
# salida pierde o tuerce de lo que la nota si dice, y que el prompt manda
# conservar (reglas 6 y 7). Salieron de un barrido de solo lectura sobre 3.087
# notas el 2026-09-23; cada uno se ajusto leyendo TODO lo que marcaba, porque la
# primera version de un detector siempre dispara de mas.

# ---------- embarazo_perdido (regla 6) ----------

_GESTANTE = re.compile(r"embarazad[ao]s?\b|\bembarazo\b|emabraz|gestant|primigest|secundigest|"
                       r"segundigest|trigest|multigest")
# 'semanas de gestacion' y '37 sms' las lleva tambien un recien nacido: 'recien
# nacido del 25/12 de 37.4 semanas de gestacion' no es una gestante (falso
# positivo real del barrido). Solo cuentan si la nota no habla de un recien
# nacido. 'gestacional' tampoco: 'antecedentes: hta gestacional' es historia.
_EDAD_GESTACIONAL = re.compile(r"gesta(?:cion|icon|sion)\b|\d\s*(?:sms|sdg)\b")
_RECIEN_NACIDO = re.compile(r"recien nacid|\brn\b|neonat|\bnacid[oa]\b|lactante")
# 'no se si estoy embarazada', 'se sospecha embarazo', 'prueba de embarazo' no
# afirman el embarazo (casos reales); 'prueba de embarazo positiva' si.
_EMBARAZO_EN_DUDA = re.compile(r"(?:no se si|sospech\w*|posible|probable|descart\w*|niega|\bno\b|"
                               r"prueba\w* (?:\w+ )?de|test de)\s+(?:\w+\s+){0,3}$")
# Lo que en la salida conserva el embarazo sin decir la palabra. 'movimientos
# fetales activos', 'contracciones' o 'liquido amniotico' en una gestante no
# dejan duda: la primera version los marcaba y eran ~50 notas correctas.
_EMBARAZO_EN_SALIDA = re.compile(
    r"embaraz|gestac|gestant|primigest|secundigest|segundigest|multigest|trigest|fetal|\bfeto|"
    r"fetocard|amniot|\bparto|aborto|contracc|tapon mucoso|membranas|placent|eclamp|obstetr|"
    r"prenatal|cesarea|embrion|\bive\b|trimestre|ectopic")


def es_gestante(original):
    """La nota AFIRMA un embarazo en curso."""
    nota = plano(original)
    for m in _GESTANTE.finditer(nota):
        antes = nota[max(0, m.start() - 40):m.start()]
        despues = nota[m.end():m.end() + 30]
        if _EMBARAZO_EN_DUDA.search(antes) and "positiv" not in despues:
            continue
        return True
    return bool(_EDAD_GESTACIONAL.search(nota)) and not _RECIEN_NACIDO.search(nota)


def embarazo_perdido(original, salida):
    """
    Fallo real: 'secundigestante de 30 semanas ... dolor de cabeza y zumbido en
    los oidos' -> 'cefalea y zumbido en oidos'. Es justo lo que sube la prioridad
    del triage (una cefalea en una gestante de 30 semanas es otra cosa), y lo que
    la regla 6 manda conservar. 21 marcadas en el barrido, 21 fallos al leerlas.
    """
    s = plano(salida).strip()
    if not s or s == SIN_MOTIVO:
        return False   # eso es descarte_falso
    return es_gestante(original) and not _EMBARAZO_EN_SALIDA.search(s)


# ---------- duda_a_certeza (regla 7) ----------

_DUDA = re.compile(
    r"\bcreo\b(?:\s+que)?|\bparece(?:\s+que)?|\bpareciera\b|al parecer|\bposibles?\b|posiblemente|"
    r"\bprobables?\b|probablemente|sospech\w*|no se si|tal ?vez|quizas?|supuesta\w*|presunt\w*|"
    r"descartar\b|no se descarta")
# 'no fue posible extraerlo', 'lo antes posible': 'posible' sin ninguna duda
# clinica detras (caso real: un cuerpo extrano que no pudieron sacar).
# 'como que' no entra en _DUDA: 'siento como que me ahogo' describe, no duda.
_NO_ES_DUDA = re.compile(r"(?:no fue|no es|no ha sido|no sea|no era|lo mas|lo antes|si es)\s*$")
_FIN_DUDA = re.compile(r"[,.;:\n(\"]|\bpero\b|\bporque\b|\bpor lo (?:que|cual)\b|\bsin embargo\b|"
                       r"\bentonces\b")
_DUDA_EN_SALIDA = re.compile(
    r"posib|probab|sospech|al parecer|parece|\bcreo\b|duda|presunt|aparente|descart|no confirmad|"
    r"a estudio|\?|\bvs\b|a definir|por confirmar|no se si|tal ?vez|quizas?|supuest")
_VACIAS_DUDA = set("""tengo tiene tienen tenia estoy esta estan estaba soy fue fui era sea hay
algo como mucho mucha poco poca otra otro otras otros volvi volvio tener hacer hizo hice quien
donde cuando cual este esto eso ese esa unos unas pues porque aunque""".split())
# La palabra dudada que el modelo nunca copia literal: 'creo que tengo la presion
# alta' sale como 'cifras tensionales elevadas' (caso real, sin 'presion').
_DUDA_TRADUCIDA = {"presion": r"tension|hipertens", "tension": r"tension|hipertens",
                   "infecc": r"infecc|\bitu\b"}
_LADOS_Y_PARTES = [r for raices in PARTES.values() for r in raices if len(r) > 3] + list(_LADOS)


def _tramos_en_duda(nota):
    """(inicio, fin) de cada frase que la nota pone en duda, hasta la coma."""
    tramos = []
    for m in _DUDA.finditer(nota):
        if _NO_ES_DUDA.search(nota[max(0, m.start() - 12):m.start()]):
            continue
        fin = _FIN_DUDA.search(nota, m.end())
        tramos.append((m.start(), m.end(), min(fin.start() if fin else len(nota), m.end() + 80)))
    return tramos


def duda_a_certeza(original, salida):
    """
    Fallo real: 'creo que se me reactivo la miastenia' -> 'mialgia muscular
    relacionada con miastenia'; 'al parecer tiene fractura' -> 'fractura
    confirmada por radiografia'. La salida afirma lo que la nota dudaba.

    Solo cuenta la palabra dudada que la salida repite SIN ninguna marca de duda.
    Las partes del cuerpo y los lados no cuentan como lo dudado: 'creo que me
    fracture la mano' -> 'dolor en mano' es correcto, la duda era la fractura.
    Si la nota afirma la misma palabra fuera de la duda ('sospecha de neumonia,
    rx confirma neumonia'), tampoco.
    """
    s = plano(salida)
    if not s.strip() or _DUDA_EN_SALIDA.search(s):
        return False
    nota = plano(original)
    tramos = _tramos_en_duda(nota)
    if not tramos:
        return False
    fuera = nota
    for i, _, j in sorted(tramos, reverse=True):
        fuera = fuera[:i] + " " + fuera[j:]
    afirmado = set(palabras(fuera))
    en_salida = set(palabras(s))
    for _, desde, hasta in tramos:
        for p in palabras(nota[desde:hasta]):
            if len(p) < 4 or p in _VACIAS_DUDA or p.isdigit():
                continue
            if any(p.startswith(r) or r.startswith(p[:5]) for r in _LADOS_Y_PARTES):
                continue
            raiz = p[:5]
            if any(v.startswith(raiz) for v in afirmado):
                continue
            traducida = next((t for k, t in _DUDA_TRADUCIDA.items() if p.startswith(k)), None)
            if any(w.startswith(raiz) for w in en_salida) or (traducida and re.search(traducida, s)):
                return True
    return False


# ---------- negacion_perdida (regla 6) ----------

_NIEGA = re.compile(r"\b(?:niega|niegan|neiga|niege|niegea|nieg)\b")
_FIN_NIEGA = re.compile(r"[,.;:\n(\"*\-]|\b(?:refiere|refiriendo|presenta|con|pero|ademas|asociad\w*|"
                        r"tiene|niega|niegan|se|paciente|en el momento|ahora|hoy|a la)\b")
# Lo que sigue a 'niega' y no es un sintoma: 'niega sintomatologia adicional',
# 'alergias: niega' (antecedentes). Sin esto cada nota con antecedentes marcaba.
_NEGADO_GENERICO = set("""sintomas sintoma sintomatologia otros otras otro otra adicional adicionales
adicioal adicionaol relacionados relacionadas asociados asociadas antecedentes antecedente cuadro
cuadros alteracion alteraciones signos tipo segun interrogatorio nada ninguna ningun alergias
quirurgicos toxicos farmacologicos patologicos transfusionales desde hace para nivel zona
region""".split())
# 'niega dolor en el pecho' se contradice con 'dolor toracico', no con cualquier
# dolor: con estas cabezas hace falta que tambien coincida lo que las acompana.
_CABEZA_GENERICA = {"dolor", "perdida", "perdidas", "salida", "sensacion", "episodio", "episodios"}
_NIEGA_VALIDA = {"niega", "niegan", "niego", "niegas", "niegue", "negar", "negarse", "negando",
                 "negado", "negada", "negados", "negadas", "negativo", "negativa", "negativos",
                 "negativas",
                 # palabras reales que se le parecen: 'diarrea negra' no es una
                 # negacion deformada (sale en 3 notas del barrido)
                 "negra", "negras", "negro", "negros", "siega"}
_NEGADOR = re.compile(r"\b(?:niega\w*|neiga|niege|niegea|sin|no|ni|ausencia de|descart\w*)\b")
_FIN_NEGADOR = re.compile(r"[,.;:(]|\b(?:con|pero|refiere|presenta|asociad\w*|mas|ademas)\b")


def _negados(nota):
    """[(cabeza, acompanantes)] de cada 'niega X' de la nota, y la nota sin ellos."""
    items, tramos = [], []
    for m in _NIEGA.finditer(nota):
        fin = _FIN_NIEGA.search(nota, m.end())
        hasta = min(fin.start() if fin else len(nota), m.end() + 70)
        tramos.append((m.start(), hasta))
        # 'y', 'o', 'y/o', 'ni' siguen la negacion: 'niega diarrea y/o emesis'.
        # La coma no: en 'niega diarrea, perdida de apetito, nauseas' no se sabe
        # si lo demas tambien se niega (caso real ambiguo).
        for trozo in re.split(r"\by/o\b|\by\b|\bo\b|\be\b|\bni\b", nota[m.end():hasta]):
            ps = [p for p in palabras(trozo) if len(p) >= 4 and p not in _NEGADO_GENERICO]
            if ps:
                items.append((ps[0], ps[1:]))
    fuera = nota
    for i, j in sorted(tramos, reverse=True):
        fuera = fuera[:i] + " " + fuera[j:]
    # las otras negaciones tampoco afirman nada: 'no dolor a la digitopresion'
    fuera = re.sub(r"\b(?:no|sin|ni)\s+\w+", " ", fuera)
    return items, fuera


def _afirmada(raiz, salida):
    """La raiz sale en la salida fuera de toda negacion. Una negacion alcanza
    hasta la coma ('niega cuadro de vomito y diarrea': las dos negadas), y
    'diarrea y emesis negadas' tambien niega."""
    tramos = []
    for m in _NEGADOR.finditer(salida):
        fin = _FIN_NEGADOR.search(salida, m.end())
        tramos.append((m.start(), fin.start() if fin else len(salida)))
    for m in re.finditer(r"\b" + re.escape(raiz) + r"\w*", salida):
        if any(i <= m.start() < j for i, j in tramos):
            continue
        if any(w.startswith("negad") for w in salida[m.end():].split()[:3]):
            continue
        return True
    return False


def _parte_de(palabra):
    return next((parte for parte, raices in PARTES.items() if any(_esta(r, {palabra}) for r in raices)),
                None)


def negacion_perdida(original, salida):
    """
    Dos fallos reales:
      'niega traumas'                  -> 'nieta traumas'   la negacion deformada
      'hipo ... niega dolor en el pecho' -> 'dolor toracico inespecifico'

    'diarrea negada', 'sin disnea' y 'niega emesis' en la salida son negaciones
    validas. Solo mira 'niega' en la nota: extenderlo a 'sin X' y 'no X' marco 15
    notas mas en el barrido y ninguna era un fallo de negacion.
    """
    nota, s = plano(original), plano(salida)
    if not _NIEGA.search(nota):
        return False
    en_nota = set(palabras(nota))
    for w in palabras(s):
        if len(w) >= 4 and w not in _NIEGA_VALIDA and w not in en_nota and _parecida(w, "niega"):
            return True
    items, fuera = _negados(nota)
    afirmado = set(palabras(fuera))
    en_salida = set(palabras(s))
    for cabeza, acompanantes in items:
        raiz = cabeza[:5]
        if not _afirmada(raiz, s):
            continue
        if cabeza not in _CABEZA_GENERICA:
            if not any(v.startswith(raiz) for v in afirmado):
                return True
            continue
        for otra in acompanantes:
            parte = _parte_de(otra)
            if parte:
                en_la_salida = any(_esta(r, en_salida) for r in PARTES[parte])
                en_la_nota = any(_esta(r, afirmado) for r in PARTES[parte])
            else:
                en_la_salida = any(w.startswith(otra[:5]) for w in en_salida)
                en_la_nota = any(v.startswith(otra[:5]) for v in afirmado)
            if en_la_salida and not en_la_nota:
                return True
    return False


# ---------- duracion_cambiada (regla 6) ----------

_EN_HORAS = {"h": 1, "d": 24, "s": 168, "m": 720, "a": 8760}
_UNIDAD = {"hora": "h", "horas": "h", "hrs": "h", "hr": "h", "h": "h", "dia": "d", "dias": "d",
           "d": "d", "semana": "s", "semanas": "s", "sem": "s", "sms": "s", "mes": "m",
           "meses": "m", "ano": "a", "anos": "a"}
# Del lado de la nota, las erratas de la unidad: '30.2 semasn de gestaicon',
# '11 ias de evolucion'. Sin esto la nota 'no tenia' la duracion que la salida
# copio bien corregida.
_UNIDAD_CON_ERRATA = {"horas": "h", "dias": "d", "semanas": "s", "meses": "m"}
_CANTIDAD = {k: float(v) for k, v in _NUMEROS_ESCRITOS.items()
             if k not in ("ayer", "anoche", "antier", "anteayer")}
_CANTIDAD.update({"once": 11.0, "catorce": 14.0, "cuarenta": 40.0, "medio": 0.5, "media": 0.5})
_HOY = re.compile(r"\bhoy\b|esta manana|esta tarde|esta noche|\bmadrugada\b|hace un rato")


def _unidad(palabra, errata):
    if palabra in _UNIDAD:
        return _UNIDAD[palabra]
    if errata and len(palabra) >= 3:
        return next((u for correcta, u in _UNIDAD_CON_ERRATA.items()
                     if SequenceMatcher(None, palabra, correcta).ratio() >= 0.75), None)
    return None


def duraciones(texto, errata=False):
    """[(cantidad, unidad)] de un texto. 'ayer' es (1, 'd') y 'antier' (2, 'd');
    'hoy' y 'anoche' van como ('hoy', None) y ('anoche', None) porque son rangos."""
    t = plano(texto)
    # '6+3 semanas' es 6 semanas y 3 dias: se queda el primer numero
    t = re.sub(r"(\d+)\s*\+\s*\d+", r"\1", t)
    fichas = re.findall(r"\d+(?:[.,]\d+)?|[a-z]+", t)
    items = []
    for i in range(1, len(fichas)):
        unidad = _unidad(fichas[i], errata)
        # 'desde las 16 horas' es una hora del reloj, no una duracion (falso
        # positivo real: 'epistaxis desde las 16' contra 'retirar en 12 horas')
        if not unidad or (i >= 2 and fichas[i - 2] in ("las", "la")):
            continue
        previa = fichas[i - 1]
        cantidad = float(previa.replace(",", ".")) if previa[0].isdigit() else _CANTIDAD.get(previa)
        if cantidad is None:
            continue
        items.append((cantidad, unidad))
        # 'de 2 a 3 dias': el primer numero lleva la misma unidad
        if i >= 3 and fichas[i - 2] in ("a", "o", "y") and fichas[i - 3][0].isdigit():
            items.append((float(fichas[i - 3].replace(",", ".")), unidad))
    sueltas = set(re.findall(r"[a-z]+", t))
    if sueltas & {"antier", "anteayer", "antenoche"} or "antes de ayer" in t:
        items.append((2.0, "d"))
    if "ayer" in sueltas and "antes de ayer" not in t:
        items.append((1.0, "d"))
    if "anoche" in sueltas:
        items.append(("anoche", None))
    if _HOY.search(t):
        items.append(("hoy", None))
    return items


def _misma_duracion(a, b):
    if a[1] is None and b[1] is None:
        return a[0] == b[0] or {a[0], b[0]} == {"hoy", "anoche"}
    if a[1] is None or b[1] is None:
        # 'hoy' y 'anoche' abarcan hasta un dia: '24 horas', 'ayer'
        exacta = a if a[1] else b
        return exacta[0] * _EN_HORAS[exacta[1]] <= 24
    if a[1] == b[1]:
        # misma unidad, mismo numero: '38.6 semanas' -> '38 semanas' vale,
        # '3 dias' -> '2 dias' no
        return int(a[0]) == int(b[0])
    # otra unidad: la conversion que hace cualquiera. '8 dias' es 'una semana' en
    # Colombia (12 % de diferencia); '2 dias' no son '72 horas'.
    ha, hb = a[0] * _EN_HORAS[a[1]], b[0] * _EN_HORAS[b[1]]
    return abs(ha - hb) <= 0.15 * max(ha, hb)


def duracion_cambiada(original, salida):
    """
    Fallos reales: 'cefalea desde antier' -> 'cefalea desde ayer'; 'desde
    antenoche' -> 'desde ayer noche'. Cada duracion de la salida tiene que estar
    en la nota, con su numero o con su equivalente.

    Solo compara cuando la nota trae alguna duracion: una duracion que sale de la
    nada es numero_inventado. 'hoy' en la salida no se compara: suele ser una
    fecha ('induccion para hoy') y la nota lo escribe con erratas que no se
    pueden seguir ('para el dia de hopy', falso positivo real).
    """
    en_salida = [d for d in duraciones(salida) if d[0] != "hoy"]
    if not en_salida:
        return False
    en_nota = duraciones(original, errata=True)
    return bool(en_nota) and any(not any(_misma_duracion(d, n) for n in en_nota) for d in en_salida)


# ==========================================================
# PRIVACIDAD (regla 4)
# ==========================================================

# Instituciones de salud concretas. 'su eps', 'la ips', 'hospital local' no
# identifican a nadie y no entran; 'clinica' sola tampoco ('clinica estable').
_INSTITUCION = re.compile(
    r"\bavidanti\b|santa ?sofia|san ?marcel|clinica (?:san|santa|versalles|la presentacion)\b|"
    r"hospital (?:san|santa|de caldas|infantil)\b|mater filius|\bhuc\b|\bses\b|\bemi\b|\bimi\b|"
    r"assbasalud|\bassba\b|\bconfa\b|confamiliar|comfamiliar|\bsura\b|nueva eps|salud total|"
    r"sanitas|coomeva|asmet|medimas|famisanar|eps compensar|colsubsidio|emssanar|savia salud|"
    r"cafesalud|salud ?vida|aliansalud|\bpijaos\b|arl positiva|positiva arl")
_TRATO = re.compile(r"\b(?:dr|dra|doctor|doctora|sr|sra|senor|senora|don|dona)\.?\s+([a-z]{3,})")
_NO_ES_NOMBRE = set("""del los las que con por para sus una turno tratante general particular
medico especialista familia familiar paciente urgencias""".split())


def identificador_en_salida(original, salida):
    """
    Fallos reales: 'hernia discal por neurocx dr <apellido>', 'turbinoplastia en
    avidanti', 'derivado del hospital santa sofia'. La regla 4 manda quitarlos y
    la salida es lo que se guarda y se comparte.

    El nombre tras un trato solo cuenta si esta en la nota: asi se sabe que es el
    nombre copiado y no una palabra comun ('dr de turno').
    """
    s = plano(salida)
    if _INSTITUCION.search(s):
        return True
    en_nota = set(palabras(original))
    return any(m.group(1) not in _NO_ES_NOMBRE and m.group(1) in en_nota for m in _TRATO.finditer(s))


# ==========================================================
# FILTROS: lo que el prompt no consigue, aplicado en codigo
# ==========================================================
#
# El 2026-09-23 se midio que ninguna redaccion de la regla 10 ('no agregues una
# parte del cuerpo ni un lado') consigue que qwen3:8b deje de completar
# 'en <parte> <lado>': ni la de v3/v4 ni una instruccion al final del prompt. A
# temperatura 0 esa tendencia es mas fuerte que cualquier regla escrita. Estos
# filtros aplican la regla 10 en codigo, que el modelo no puede desobedecer.
#
# Solo QUITAN, nunca agregan, y solo lo que el detector correspondiente
# confirma que no esta en la nota (con erratas y siglas incluidas).

_FRASE_LADO = re.compile(r"\s*\b(?:del|en el|al)?\s*lado\s+(?:derech|izquierd)\w*|\s*\b(?:derech|izquierd)[oa]s?\b")


def quitar_lado_inventado(original, salida):
    if not lado_inventado(original, salida):
        return salida
    return re.sub(r"\s{2,}", " ", _FRASE_LADO.sub("", salida)).strip(" ,")


def quitar_parte_inventada(original, salida):
    """Quita 'en el abdomen', 'en la mano' cuando esa parte no esta en la nota.

    Solo frases con preposicion: un sustantivo suelto como 'cefalea' puede ser
    todo el motivo, y quitarlo dejaria la salida vacia. Esos los sigue marcando
    el detector."""
    partes = cuerpo_inventado(original, salida)
    for parte in partes:
        raices = "|".join(re.escape(r) for r in PARTES[parte])
        patron = re.compile(r"\s*\b(?:en|de|del|a|al)\s+(?:el|la|los|las|su|sus)?\s*"
                            r"(?:" + raices + r")\w*", re.I)
        salida = patron.sub("", salida)
    return re.sub(r"\s{2,}", " ", salida).strip(" ,")


_SUFIJO_GESTANTE = re.compile(r"\s*,?\s*\ben (?:paciente )?(?:gestante|embarazada)"
                              r"(?: de [\d.,]+ semanas(?: de gestacion)?)?", re.I)


def quitar_embarazo_inventado(original, salida):
    """
    La regla 6 de v1.7 pide terminar con 'en gestante de N semanas' cuando la nota
    lo dice. Medido en la sonda ampliada: el modelo tambien lo pega a notas que no
    son de embarazada ('creo que se me reactivo la miastenia' -> 'miastenia grave
    en gestante'). Solo se quita ESE sufijo, y solo si la nota no afirma embarazo.
    """
    if es_gestante(original):
        return salida
    return re.sub(r"\s{2,}", " ", _SUFIJO_GESTANTE.sub("", salida)).strip(" ,")


_ANTIER_NOTA = re.compile(r"\bantier\b|\banteayer\b|\bantes de ayer\b")
_ANTENOCHE_NOTA = re.compile(r"\bantenoche\b|\banteanoche\b|\bantier en la noche\b")


def restaurar_antier(original, salida):
    """
    'antier' -> 'ayer' es sistematico en qwen3:8b: medido en fallos y en una
    guarda que v1.6 hacia bien. Mueve el inicio del cuadro un dia, que es justo lo
    que mira el analisis de rezagos contra el clima.

    Es el unico filtro que REEMPLAZA en vez de quitar, y solo para devolver la
    palabra exacta de la nota. No actua si la nota dice tambien 'ayer' (entonces
    'ayer' en la salida puede ser correcto).
    """
    nota, s = plano(original), plano(salida)
    sin_ante = _ANTIER_NOTA.sub(" ", _ANTENOCHE_NOTA.sub(" ", nota))
    if re.search(r"\bayer\b|\banoche\b", sin_ante):
        return salida
    if _ANTENOCHE_NOTA.search(nota) and re.search(r"\bayer (?:en la )?noche\b|\banoche\b", s):
        return re.sub(r"\bayer (?:en la )?noche\b|\banoche\b", "antenoche", salida, flags=re.I)
    # 'el dia anterior' es la otra forma de decir ayer: el 8B y el 14B la usaron
    # para 'antier' (sonda del 2026-09-24)
    ayer_en_salida = r"\b(?:el dia de )?ayer\b|\bel d[ií]a anterior\b"
    if _ANTIER_NOTA.search(nota) and re.search(ayer_en_salida, s) and not _ANTIER_NOTA.search(s):
        return re.sub(ayer_en_salida, "antier", salida, flags=re.I)
    return salida


def quitar_identificadores(original, salida):
    """
    Privacidad (regla 4): la frase limpia es lo que se guarda, se agrupa y se
    muestra. Quita instituciones concretas y 'dr/sra + nombre' cuando ese nombre
    esta en la nota. Casos reales: 'hernia discal por neurocx dr <apellido>',
    'turbinoplastia en avidanti'.
    """
    s = salida
    s = re.sub(r"\s*\b(?:en|de|del|desde|por|a)?\s*(?:la |el )?(?:" + _INSTITUCION.pattern + r")",
               "", s, flags=re.I)
    en_nota = set(palabras(original))

    def _trato(m):
        return "" if m.group(1).lower() in en_nota and m.group(1).lower() not in _NO_ES_NOMBRE else m.group(0)

    s = re.sub(r"\s*\b(?:dr|dra|doctor|doctora|sr|sra|senor|senora|don|dona)\.?\s+([A-Za-z]{3,})",
               _trato, s, flags=re.I)
    s = re.sub(r"\s+\b(?:por|en|de|del|a)\s*$", "", s.strip())
    # 'remitida por dr X por hernia' -> quitado el nombre queda 'por por'
    s = re.sub(r"\b(por|de|del|en|a)\s+\1\b", r"\1", s, flags=re.I)
    # la regla 4 manda quitar la remision; si la salida EMPIEZA por ella y sigue
    # un motivo, se quita el tramite y queda el motivo
    s = re.sub(r"^(?:paciente\s+)?(?:remitid|derivad|enviad|referid)[oa]s?\s+(?:por|de|desde)\s+",
               "", s.strip(), flags=re.I)
    return re.sub(r"\s{2,}", " ", s).strip(" ,")


# ==========================================================
# PERDIDA: lo contrario de inventar
# ==========================================================

def perdido(original, referencia, nueva):
    """
    Lo que la salida de referencia decia, la nota respalda, y la nueva ya no dice:
    numeros, partes del cuerpo y negaciones.

    Existe porque empujar al modelo contra la invencion tambien lo empuja a
    recortar. Medido el 2026-09-23: la primera version de v1.7 dejo de decir
    'en mesogastrio', '11 kilos' y '3 dias', que la nota si traia.
    """
    nota, ref, nue = plano(original), plano(referencia), plano(nueva)
    vocabulario_nota = set(palabras(nota))
    perdidas = []
    for numero in set(re.findall(r"\b\d+\b", ref)):
        if numero in nota and not re.search(r"\b" + numero + r"\b", nue):
            perdidas.append(numero)
    en_nueva = set(palabras(nue))
    for parte, raices in PARTES.items():
        estaba = any(_esta(r, set(palabras(ref))) for r in raices)
        respaldada = any(_esta(r, vocabulario_nota, errata=True) for r in raices)
        sigue = any(_esta(r, en_nueva) for r in raices)
        if estaba and respaldada and not sigue:
            perdidas.append(parte)
    if "niega" in ref and "niega" in nota and "niega" not in nue:
        perdidas.append("negacion")
    # la duda y el 'antier' que la salida anterior conservaba (sonda ampliada:
    # 'con sospecha de fractura' desaparecio sin que nada lo marcara)
    duda = r"sospecha|posible|probable|al parecer|aparente"
    if re.search(duda, ref) and not re.search(duda, nue) and re.search(duda + r"|creo|parece", nota):
        perdidas.append("duda")
    if re.search(r"\bantier\b|anteayer|antenoche", ref) and not re.search(r"\bantier\b|anteayer|antenoche", nue):
        perdidas.append("antier")
    return perdidas


# ==========================================================
# TODO JUNTO
# ==========================================================

_PERDIDAS_Y_PRIVACIDAD = [("embarazo_perdido", embarazo_perdido), ("duda_a_certeza", duda_a_certeza),
                          ("negacion_perdida", negacion_perdida),
                          ("duracion_cambiada", duracion_cambiada),
                          ("identificador_en_salida", identificador_en_salida)]

def revisar(original, salida):
    """Banderas de UNA nota. La de frase_comodin necesita el corpus: ver revisar_corpus."""
    vocabulario = base(original)
    banderas = []
    if formato(salida):
        banderas.append("formato")
    if queja_sin_sintoma(original, salida, base_de_salida(original, salida, vocabulario)):
        banderas.append("queja_sin_sintoma")
    if copia_de_ejemplo(original, salida):
        banderas.append("copia_de_ejemplo")
    if numero_inventado(original, salida):
        banderas.append("numero_inventado")
    if lado_inventado(original, salida):
        banderas.append("lado_inventado")
    partes = cuerpo_inventado(original, salida, vocabulario)
    if partes:
        banderas.append("cuerpo_inventado")
    if descarte_falso(original, salida):
        banderas.append("descarte_falso")
    for nombre, detector in _PERDIDAS_Y_PRIVACIDAD:
        if detector(original, salida):
            banderas.append(nombre)
    cobertura = base_de_salida(original, salida, vocabulario)
    if cobertura < 0.5 and plano(salida).strip() != SIN_MOTIVO:
        banderas.append("poca_base")
    return {"banderas": banderas, "partes_inventadas": partes, "base": round(cobertura, 2)}


def revisar_corpus(filas, minimo_originales=3):
    """
    filas: iterable de (oid, original, salida). Devuelve {oid: revision}.

    Agrega 'frase_comodin' a las salidas que se repiten desde al menos
    `minimo_originales` notas distintas y que, en esa nota concreta, no tienen
    base. Una salida repetida no es sospechosa por si misma ('tos' se repite
    cientos de veces con razon); lo es cuando se repite Y no sale de la nota.
    """
    filas = list(filas)
    origenes = defaultdict(set)
    for _, original, salida in filas:
        origenes[plano(salida).strip()].add(plano(original).strip())

    resultado = {}
    for oid, original, salida in filas:
        revision = revisar(original, salida)
        repetida = len(origenes[plano(salida).strip()]) >= minimo_originales
        sin_base = "poca_base" in revision["banderas"] or revision["partes_inventadas"]
        if repetida and sin_base and plano(salida).strip() != SIN_MOTIVO:
            revision["banderas"].append("frase_comodin")
        resultado[oid] = revision
    return resultado


def es_fallo(revision):
    return any(b in FUERTES for b in revision["banderas"])
