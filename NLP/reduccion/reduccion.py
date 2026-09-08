"""
Recorte de la nota: dejar el motivo de consulta y tirar todo lo demas.

QUE PROBLEMA RESUELVE, CON EL NUMERO QUE LO DEMUESTRA
    texto_embedding.py construia una frase canonica desde la estructura
    extraida: 'categoria respiratorio. sintoma epistaxis.'. Medido sobre las
    30.000 notas del corpus, eso produjo

        embedding_texto distintos : 15.829 de 30.000
        notas con texto duplicado : 15.582  (51,9%)
        palabras por texto        : mediana 5, media 7,0

        999 notas dicen exactamente 'categoria gastrointestinal. sintoma dolor abdominal.'
        927 notas dicen exactamente 'categoria neurologico. sintoma cefalea.'
      1.096 notas dicen exactamente 'sin informacion clinica.'

    Texto identico -> vector identico -> distancia coseno 0. Para HDBSCAN esas
    999 notas son un unico punto de masa, y de ahi salen el cluster de 676
    registros y el 20,4% de ruido.

    Y hay un problema peor que la perdida de contexto: canonizar contra un
    catalogo de 82 conceptos hace que el clustering solo pueda redescubrir esos
    82 conceptos. La fase 5 existe para encontrar los patrones que NO se
    declararon, y se le estaba entregando exactamente lo que si se declaro.

LA INVERSION
    Antes:   la estructura ES el texto, y la nota real es el respaldo.
    Ahora:   la nota real es el texto, y la estructura son campos aparte.

    Son dos cosas distintas y estaban mezcladas en un solo campo. La estructura
    (categoria, sintomas, negados, valores) sirve para filtrar, contar y cruzar
    con el calendario; sigue en el JSON, intacta. El texto sirve para que
    bge-m3 mida parecido semantico, y para eso necesita lenguaje, no etiquetas.

QUE SE QUITA, Y POR QUE ESO SI SE PUEDE ENUMERAR
    Lo que sobra en una nota de triage no es variado: es un puñado de bloques
    estereotipados que se repiten en miles de notas casi igual.

      bloque institucional  la politica de la EPS, los niveles de atencion, las
                            disculpas. En la nota 803472 son 75% del texto y no
                            hablan del paciente.
      tramite               'ingresa paciente', 'se recibe', 'es remitido de',
                            'consulta por'. Describen el recorrido por el
                            sistema, y son identicas en notas de categorias
                            opuestas: es lo que forma clusters de puro tramite.
      verbo de reporte      'refiriendo que', 'quien manifiesta que'. Introducen
                            el sintoma sin aportar nada.
      encabezados           'mc:', 'ap (antecedentes personales):'. Etiquetas
                            del formulario.
      preambulo temporal    'desde hace 3 dias que'. El tiempo de evolucion ya
                            viaja como dato estructurado.

    Todo lo demas se conserva TAL CUAL. Esa es la diferencia con la version
    anterior: no se reescribe la nota, se le quitan los bloques que sobran y lo
    que queda es la frase que escribio quien atendio al paciente.

LO QUE NO SE TOCA
    La negacion se queda dentro del texto. 'ahora sin epistaxis' tiene que
    llegarle al modelo: bge-m3 la entiende, y quitarla convertiria un cuadro
    resuelto en uno activo. La negacion viaja dos veces a proposito, como campo
    estructurado y dentro de la frase, porque sirven para cosas distintas.
"""

import json
import re
from pathlib import Path

RE_ESPACIOS = re.compile(r"\s+")

# El lexico clinico que construye NLP/lexico.py: 32.310 formas del CIE-10-ES,
# el diccionario del proyecto y el catalogo de sintomas. Se usa para medir de
# que habla cada oracion, no para corregir nada.
RUTA_LEXICO = Path(__file__).resolve().parent.parent / "NLP" / "lexico_clinico.json"

_LEXICO = None

# Solo cuentan las fuentes CURADAS del lexico. El vocabulario del modelo
# biomedico queda fuera a proposito: se entreno sobre historias clinicas
# escritas en espanol, asi que contiene el espanol corriente entero y con el
# la densidad da 1.00 hasta para 'ofrecemos disculpas por los inconvenientes'.
FUENTES_CURADAS = ("diccionario", "catalogo", "externo")

# Umbral conservador, y lo es por una razon medida. Sobre frases de prueba:
#
#     0.33  'ofrecemos disculpas por los inconvenientes...'   institucional
#     0.38  'los demas usuarios deberan ser orientados...'    institucional
#     0.50  'me siento muy mal'                               paciente
#     0.62  'unicamente seran priorizados los pacientes...'   institucional
#     0.71  'le han dado varias epistaxis de dificil...'      clinico
#     0.86  'dolor en ambos costados que se irradia...'       clinico
#
# Las dos poblaciones SE SOLAPAN: el CIE-10 contiene mucho espanol corriente
# ('usuarios', 'hacia', 'riesgo', 'condicion'), asi que un bloque burocratico
# puede puntuar 0.62. No hay un corte que separe las dos limpiamente.
#
# Por eso la densidad NO es el criterio principal: es una red de seguridad para
# los bloques que nadie enumero, con el umbral puesto por debajo de la frase
# clinica mas pobre que se midio (0.50). El caso de 0.62 lo atrapan igual los
# marcadores. Preferimos dejar pasar texto administrativo antes que borrar una
# frase del paciente: es la misma asimetria de coste de todo el proyecto.
PALABRAS_ORACION_LARGA = 8
DENSIDAD_MINIMA = 0.40


def cargar_lexico(ruta=RUTA_LEXICO):
    """Lee el lexico clinico. Sin el, la densidad no se aplica y solo actuan
    los marcadores enumerados, que es como estaba antes."""
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

# Frases del bloque institucional. Basta una para descartar la oracion entera:
# el bloque nunca trae contenido clinico mezclado.
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

# Verbos de reporte: introducen el sintoma y no aportan nada. Se quitan junto
# con el 'que' que los sigue, porque solos dejan la frase colgando.
RE_REPORTE = re.compile(
    r"\b(?:refiriendo|manifestando|indicando|comentando|informando)\s+que\s+"
    r"(?:esta|estaba|se\s+encuentra)?\s*|"
    r"\b(?:refiere|manifiesta|indica|comenta|informa)\s+que\s+",
    re.IGNORECASE)

# Encabezados del formulario: 'mc:', 'ap (antecedentes personales):'
RE_ENCABEZADO = re.compile(r"\b[a-z]{2,4}\s*(?:\([^)]{3,60}\))?\s*:", re.IGNORECASE)

# Expansion entre parentesis que agrego la fase 3. En el texto para el modelo
# solo duplica lo que la sigla ya dice.
RE_PARENTESIS = re.compile(r"\([^)]{5,80}\)")

RE_TEMPORAL = re.compile(
    r"\b(?:desde\s+hace\s+\d{1,3}\s*(?:dias?|horas?|semanas?|meses?)|"
    r"hace\s+\d{1,3}\s*(?:dias?|horas?|semanas?|meses?)(?:\s+que)?|"
    r"desde\s+(?:el|la)\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|"
    r"domingo|manana|ayer|anoche|hoy)\w*|"
    r"desde\s+hace\s+(?:un|una|unos|unas)\s+\w+)\b",
    re.IGNORECASE)

# Ficha demografica: 'paciente masculino de 67 anos de edad'. La edad ya viaja
# como valores['edad'], y en el texto solo hace parecidas dos notas que no
# tienen nada que ver entre si. Se quita entera, con el 'de' que la introduce.
RE_DEMOGRAFICO = re.compile(
    r"\b(?:de\s+)?\d{1,3}\s*(?:anos|años)(?:\s+de\s+edad)?\b", re.IGNORECASE)

RE_ORACION = re.compile(r"(?<=[.;])\s+")

# Conectores y preposiciones que quedan sueltos al arranque cuando se quita el
# tramo que los precedia: 'al, cuadro clinico' es lo que sobra de 'paciente que
# ingresa al servicio de urgencias, cuadro clinico'.
#
# DOS DETALLES QUE COSTARON UNA MEDICION
#   El patron se construye ordenando por longitud DESCENDENTE. La alternancia
#   de una expresion regular toma la primera que encaje, asi que con 'a' antes
#   que 'al' sobre 'al, cuadro' se comia solo la 'a' y dejaba 'l, cuadro'.
#
#   Y lleva limite de palabra al final. Sin el, 'de' recortaba dentro de
#   'derivada por la eps' y producia 'rivada por la eps'.
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

# Palabras que por si solas no son contenido. Solo se usan para DECIDIR si lo
# que quedo vale la pena, nunca para borrarlas del texto: la frase tiene que
# seguir siendo legible.
VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "a", "al", "en", "con", "sin", "por", "para", "que", "se", "su",
    "sus", "lo", "le", "es", "esta", "este", "muy", "mas", "ni", "pero",
    "paciente", "usuario", "usuaria", "ahora", "momento", "cual", "quien",
    "ademas", "tipo", "toda", "todo", "ser", "han", "ha", "he", "les",
}

# Palabras con contenido que debe dejar el recorte para dar la nota por util.
#
# Estuvo en 3 y era demasiado: una nota entera que dice 'DOLOR ABDOMINAL' tiene
# dos, asi que se descartaba y caia a la frase canonica. Medido, el 23,2% del
# corpus caia por este umbral, y casi todas eran notas cortas pero perfectamente
# validas: en triage la nota tipica son cuatro palabras.
#
# Con 1 basta: _con_contenido() ya descarta las palabras vacias, asi que una
# sola palabra que sobreviva es una palabra que dice algo.
LONGITUD_MINIMA = 1
TOPE_PALABRAS = 60       # una nota de 400 palabras no aporta mas que sus 60

# Lo que queda de una plantilla contestada en blanco. Si el recorte solo deja
# esto, la nota no dice nada del paciente.
RESPUESTAS_VACIAS = {
    "niega", "niegan", "ninguno", "ninguna", "ninguna", "nada", "nono",
    "negativo", "negativa", "normal", "normales", "refiere", "presenta",
    "manifiesta", "asintomatico", "asintomatica", "aplica",
}       # una nota de 400 palabras no aporta mas que sus 60


# ==========================================================
# RECORTE
# ==========================================================

def densidad_clinica(oracion):
    """
    Fraccion de las palabras con contenido de la oracion que son terminologia
    clinica, segun el lexico de 32.310 formas.

    POR QUE NO BASTA LA LISTA DE MARCADORES
        MARCADORES_INSTITUCIONALES enumera frases: 'red de atencion',
        'lamentamos', 'molestias ocasionadas'. Funciona con el bloque de la EPS
        porque ese bloque es literal y se repite igual, pero no generaliza: en
        cuanto una sede cambie la redaccion de su aviso, o aparezca otro tipo
        de texto administrativo, hay que agregar frases a mano. Es el mismo
        problema que las listas negras de siglas, y no escala.

        La densidad no enumera nada. Mide de que habla la oracion:

          'ofrecemos disculpas por los inconvenientes que esta situacion...'
              0 de 6 palabras con contenido son clinicas   ->  0.00
          'dolor en ambos costados que se irradia a la cadera y presion en pelvis'
              5 de 8                                       ->  0.62

        Es tambien la respuesta a 'como se sabe que sobra sin listarlo': una
        oracion que no menciona nada clinico no habla del paciente.
    """
    palabras = _con_contenido(oracion)
    if not palabras:
        return 0.0
    return sum(1 for p in palabras if _es_clinica(p)) / len(palabras)


def _es_clinica(palabra):
    """El lexico se guarda con la clave plegada (minusculas, sin tildes, con
    la eñe conservada), asi que se compara igual."""
    if _LEXICO is None:
        cargar_lexico()
    if not _LEXICO:
        return False
    import unicodedata
    plano = "".join(c for c in unicodedata.normalize("NFD", palabra.replace("ñ", ""))
                    if not unicodedata.combining(c)).replace("", "ñ")
    return plano in _LEXICO


def _quitar_institucional(texto):
    """
    Descarta las oraciones que hablan del sistema y no del paciente.

    Dos criterios, y el segundo es el que generaliza:

      1. la oracion contiene un marcador institucional conocido;
      2. la oracion es larga y su densidad clinica es nula.

    El segundo captura los bloques administrativos que nadie enumero. Se exige
    que sea LARGA porque una nota corta sin terminologia reconocida suele ser
    lenguaje de paciente ('me siento mal', 'me duele mucho'), que si hay que
    conservar: que el catalogo no lo reconozca no significa que sobre.
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
    return " ".join(utiles)


def _pulir(texto):
    """
    Deja la frase legible despues de haberle quitado tramos por el medio.

    El barrido del arranque es iterativo y admite coma, no solo espacio. Al
    quitar el tramite de 'paciente que ingresa al servicio de urgencias, cuadro
    clinico de 3 dias...' queda 'al, cuadro clinico...', y una sola pasada que
    exigiera espacio detras no lo limpiaba.
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
    """Palabras que aportan algo. Sirve para decidir si la nota quedo vacia."""
    return [p for p in re.findall(r"[^\W\d_]+", texto.lower())
            if p not in VACIAS and len(p) >= 3]


def recortar(texto, agresivo=True):
    """
    Devuelve la nota sin bloque institucional, sin tramite y sin encabezados.
    Cadena vacia solo si la nota no dice NADA del paciente.

    DOS PASADAS, Y LA SEGUNDA ES LA QUE SALVA LA CALIDAD
        La pasada agresiva quita tramite, verbos de reporte, ficha demografica
        y preambulo temporal. En una nota que es casi toda tramite eso puede
        llevarse el contenido de paso.

        Cuando eso ocurre se reintenta quitando SOLO el bloque institucional y
        los encabezados. Es preferible una frase con algo de tramite a perder
        el motivo de consulta: el objetivo de este campo es que el modelo vea
        el cuadro clinico, y una nota vacia no lo enseña.

    Lo que sobrevive es texto del original, palabra por palabra: no se
    reescribe nada.
    """
    texto = str(texto or "").strip()
    if not texto:
        return ""

    salida = _recortar(texto, agresivo=True)
    if salida:
        return salida
    return _recortar(texto, agresivo=False)


def _recortar(texto, agresivo=True):
    texto = RE_ENCABEZADO.sub(" ", texto)
    if agresivo:
        texto = RE_PARENTESIS.sub(" ", texto)
        texto = RE_TRAMITE.sub(" ", texto)
        texto = RE_REPORTE.sub(" ", texto)
        texto = RE_TEMPORAL.sub(" ", texto)
        texto = RE_DEMOGRAFICO.sub(" ", texto)
    texto = _pulir(texto)

    palabras = _con_contenido(texto)
    if len(palabras) < LONGITUD_MINIMA:
        return ""

    # Plantilla contestada en blanco. Al quitarle los encabezados, una nota como
    #     'AP: niega; AA: niega; AF: niega'
    # queda en 'niega; niega; niega', que tiene palabras con contenido pero no
    # dice nada: son las respuestas de un formulario sin la pregunta. Medido,
    # 298 notas producian exactamente 'niega; niega'.
    if all(p in RESPUESTAS_VACIAS for p in palabras):
        return ""

    # tope por palabras, cortando en el limite de oracion mas cercano para no
    # dejar la frase partida a la mitad
    if len(texto.split()) > TOPE_PALABRAS:
        texto = _cortar(texto, TOPE_PALABRAS)

    return texto


def _cortar(texto, tope):
    """Recorta a 'tope' palabras sin partir una oracion por la mitad."""
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
    return " ".join(salida)


def diagnosticar(texto):
    """Que se quito en cada paso. Para revisar casos puntuales."""
    pasos = [("original", texto)]
    t = _quitar_institucional(texto);     pasos.append(("sin institucional", t))
    t = RE_ENCABEZADO.sub(" ", t);        pasos.append(("sin encabezados", t))
    t = RE_PARENTESIS.sub(" ", t);        pasos.append(("sin parentesis", t))
    t = RE_TRAMITE.sub(" ", t);           pasos.append(("sin tramite", t))
    t = RE_REPORTE.sub(" ", t);           pasos.append(("sin verbo de reporte", t))
    t = RE_TEMPORAL.sub(" ", t);          pasos.append(("sin preambulo temporal", t))
    t = RE_DEMOGRAFICO.sub(" ", t);       pasos.append(("sin ficha demografica", t))
    pasos.append(("pulido", _pulir(t)))
    return pasos
