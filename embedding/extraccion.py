"""
Fase 4. Extracción estructurada de la nota clínica.

Convierte una nota ya limpia en un registro con síntomas, hallazgos negados,
valores numéricos y categoría. No corrige ortografía ni normaliza siglas: eso
ocurrió en las fases anteriores.

    "Paciente gestante de 22 semanas que consulta por dolor pelvico intenso,
     niega perdidas vaginales, movimientos fetales activos."

    -> categoria_principal: obstetrico
       sintomas: ["dolor pelvico", "movimientos fetales"]
       signos_negados: ["sangrado vaginal"]
       embarazo: true
       edad_gestacional: 22

CÓMO SE DETECTAN LOS SÍNTOMAS
    Contra el catálogo de síntomas, que asocia cada variante de escritura a un
    concepto canónico, de modo que las distintas formas de decir lo mismo
    producen el mismo síntoma. Gana siempre la coincidencia más larga, para que
    un síntoma localizado no quede reducido a su forma genérica.

    La detección tiene tres niveles, y cada uno cubre lo que el anterior no
    puede:

      1. variante exacta del catálogo, más su plural o singular derivados
         automáticamente. Eso evita tener que escribir a mano cada forma en el
         catálogo: se declara una y quedan cubiertas las cuatro.
      2. raíz morfológica, para las formas verbales, que no se derivan por
         regla de número. Solo se aceptan las raíces que apuntan a un único
         concepto: si dos conceptos comparten raíz, se descarta entera.
      3. localización, para convertir un dolor genérico en el dolor de la zona
         que se menciona a continuación. Así el catálogo guarda las zonas del
         cuerpo y no todas las combinaciones posibles.

    Antes de buscar, texto y catálogo se llevan a una misma forma de
    comparación: minúsculas y sin tildes.

CÓMO SE DECIDE SI ESTÁ PRESENTE O NEGADO
    Cada síntoma detectado se consulta contra el marcado de negación, que
    devuelve el estado de cada palabra. Un síntoma negado no va a la lista de
    síntomas sino a la de signos negados. Sin esa separación, una nota que niega
    un hallazgo y otra que lo afirma acabarían en el mismo grupo, que es el
    error más caro de esta fase.

CÓMO SE ELIGE LA CATEGORÍA
    Por prioridad clínica declarada en el catálogo, no por recuento. Manda la
    condición que decide la conducta y no la que ocupa más palabras: una
    gestante con tos es un caso obstétrico. La categoría general va la última de
    la prioridad, porque agrupa los síntomas transversales y solo debe decidir
    cuando no hay nada de un aparato específico.
"""

import json
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

from embedding import negacion
from embedding import rutas
from embedding import texto_embedding

RUTA_CATALOGO = rutas.CATALOGO_SINTOMAS

CATEGORIA_POR_DEFECTO = "inespecifico"

_SINTOMAS = {}       # canonico -> categoria
_VARIANTES = {}      # variante normalizada -> canonico
_PRIORIDAD = []
_CATEGORIAS = {}
_TERMINOS = set()    # vocabulario para resolver la coma en las enumeraciones
_PROCESADOR = None
_LOCALIZACIONES = {}  # parte del cuerpo -> canonico de dolor de esa zona
_RAICES = {}          # raiz morfologica -> canonico (solo raices no ambiguas)
_STEMMER = None

VENTANA_LOCALIZACION = 4   # tokens que se miran tras un 'dolor' generico

# Palabras de negacion que forman parte de la propia expresion del sintoma: en
# 'no ve bien' o 'sin fuerzas' la negacion esta lexicalizada dentro del concepto
# y no lo niega. Solo aplica cuando la palabra cae DENTRO del tramo detectado;
# si queda fuera, sigue negando con normalidad.
NEGACION_LEXICALIZADA = {"no", "sin"}
LONGITUD_MINIMA_RAIZ = 5   # palabras mas cortas no se buscan por raiz

RE_ESPACIOS = re.compile(r"\s+")
RE_PALABRA = re.compile(r"[\wáéíóúüñ]+")

# Sintomas genericos y los fragmentos que identifican una variante mas
# especifica de su misma familia. Un generico solo aporta cuando no se pudo
# saber de cual se trataba: si el texto produjo tambien la forma especifica, el
# generico sobra y conservarlo hace perder precision al agrupar.
DOLOR_GENERICO = {"dolor inespecifico"}

GENERICOS = {
    "dolor inespecifico": ("dolor", "algia", "cefalea", "colico", "pirosis"),
    "sangrado inespecifico": ("sangrado", "rragia", "hematuria", "hematemesis",
                              "melenas", "epistaxis"),
}


# ==========================================================
# NORMALIZACIÓN PARA COMPARAR
# ==========================================================

def normalizar(texto):
    """
    Pasa el texto a minúsculas y le quita las tildes conservando su longitud
    carácter a carácter.

    Esa equivalencia de longitud es imprescindible: las posiciones que devuelve
    la búsqueda sobre el texto normalizado tienen que seguir apuntando al mismo
    lugar del texto original. Si algún carácter no se recompone uno a uno, se
    devuelve el texto sin plegar, que es la opción segura.
    """
    texto = str(texto or "").lower()
    descompuesto = unicodedata.normalize("NFD", texto)
    sin_tildes = "".join(c for c in descompuesto
                         if unicodedata.category(c) != "Mn")
    if len(sin_tildes) != len(texto):
        # algun caracter no se recompuso 1:1; se cae a la forma segura
        return texto
    return sin_tildes


def _formas(variante):
    """
    La variante más su plural o su singular, derivados de la última palabra.

    Cubre la variación morfológica regular del español sin tener que enumerarla
    en el catálogo: declarando una forma quedan cubiertas también las demás.
    """
    formas = {variante}
    palabras = variante.split()
    if not palabras:
        return formas

    ultima = palabras[-1]
    prefijo = " ".join(palabras[:-1])

    derivadas = []
    if len(ultima) > 3 and ultima.endswith("es"):
        derivadas.append(ultima[:-2])
    if len(ultima) > 3 and ultima.endswith("s"):
        derivadas.append(ultima[:-1])
    if len(ultima) > 2 and not ultima.endswith("s"):
        derivadas.append(ultima + "s")
        if ultima[-1] not in "aeiou":
            derivadas.append(ultima + "es")

    for d in derivadas:
        formas.add(f"{prefijo} {d}".strip())
    return formas


# ==========================================================
# CARGA DEL CATÁLOGO
# ==========================================================

def cargar(ruta=RUTA_CATALOGO):
    """
    Lee el catálogo y construye todos los índices de búsqueda. Devuelve el
    número de síntomas canónicos cargados.

    Se recorre dos veces a propósito: primero las variantes escritas a mano y
    después las derivadas por regla, porque lo declarado explícitamente debe
    prevalecer sobre lo generado automáticamente.
    """
    global _PROCESADOR

    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    _SINTOMAS.clear()
    _VARIANTES.clear()
    _TERMINOS.clear()

    declaradas = set()
    for canonico, info in datos["sintomas"].items():
        _SINTOMAS[canonico] = info["categoria"]
        for variante in info["variantes"]:
            v = normalizar(variante)
            _VARIANTES[v] = canonico
            declaradas.add(v)
            _TERMINOS.update(v.split())

    # las formas derivadas nunca pisan una variante escrita explicitamente en
    # el JSON: lo declarado a mano manda sobre lo generado por regla
    for canonico, info in datos["sintomas"].items():
        for variante in info["variantes"]:
            for forma in _formas(normalizar(variante)):
                if forma not in declaradas:
                    _VARIANTES.setdefault(forma, canonico)
                    _TERMINOS.update(forma.split())

    _PRIORIDAD.clear()
    _PRIORIDAD.extend(datos.get("_prioridad_categorias", []))
    _CATEGORIAS.clear()
    _CATEGORIAS.update(datos.get("_categorias", {}))

    _LOCALIZACIONES.clear()
    for zona, canonico in datos.get("_localizaciones_dolor", {}).items():
        _LOCALIZACIONES[normalizar(zona)] = canonico

    _PROCESADOR = _construir(_VARIANTES)
    _construir_raices()
    return len(_SINTOMAS)


def _construir_raices():
    """
    Construye el índice por raíz morfológica, que cubre las formas que el
    catálogo no puede enumerar: las verbales. Una conjugación no se deriva de un
    sustantivo por regla de número, pero comparte raíz con él, así que un
    lematizador resuelve toda la familia de una vez.

    Solo se indexan las raíces que apuntan a un único concepto. Si dos conceptos
    distintos comparten raíz, se descarta entera: un acierto dudoso aquí
    contamina la categoría del registro completo.

    Requiere nltk. Sin él, este nivel de detección queda desactivado y los otros
    dos siguen funcionando.
    """
    global _STEMMER
    _RAICES.clear()
    try:
        from nltk.stem import SnowballStemmer
    except ModuleNotFoundError:
        print("Aviso: nltk no instalado; no se buscaran formas verbales.")
        _STEMMER = None
        return

    _STEMMER = SnowballStemmer("spanish")
    candidatas = {}
    for variante, canonico in _VARIANTES.items():
        if " " in variante or len(variante) < LONGITUD_MINIMA_RAIZ:
            continue
        candidatas.setdefault(_STEMMER.stem(variante), set()).add(canonico)

    for raiz, canonicos in candidatas.items():
        if len(canonicos) == 1:
            _RAICES[raiz] = next(iter(canonicos))


def _construir(variantes):
    """
    Construye el autómata de búsqueda de variantes. Devuelve None si flashtext
    no está instalado, en cuyo caso se usa la búsqueda con expresiones
    regulares, más lenta pero equivalente.
    """
    try:
        from flashtext import KeywordProcessor
    except ModuleNotFoundError:
        print("Aviso: flashtext no instalado; la deteccion sera mas lenta.")
        return None

    kp = KeywordProcessor(case_sensitive=False)
    kp.non_word_boundaries |= set("áéíóúüñ")
    for variante, canonico in variantes.items():
        kp.add_keyword(variante, canonico)
    return kp


def _detectar(texto_norm):
    """
    Variantes del catálogo encontradas en el texto, como tuplas
    (canónico, inicio, fin) con las posiciones en caracteres.

    La rama de respaldo replica el comportamiento del autómata: ordena por
    posición prefiriendo la coincidencia más larga y descarta los solapamientos.
    """
    if _PROCESADOR is not None:
        return _PROCESADOR.extract_keywords(texto_norm, span_info=True)

    hallados = []
    for variante, canonico in sorted(_VARIANTES.items(), key=lambda x: -len(x[0])):
        for m in re.finditer(r"\b%s\b" % re.escape(variante), texto_norm):
            hallados.append((canonico, m.start(), m.end()))

    # replica la preferencia de flashtext por la coincidencia mas larga
    hallados.sort(key=lambda h: (h[1], -(h[2] - h[1])))
    limpio, fin_previo = [], -1
    for canonico, inicio, fin in hallados:
        if inicio < fin_previo:
            continue
        limpio.append((canonico, inicio, fin))
        fin_previo = fin
    return limpio


def _detectar_por_raiz(texto_norm, spans):
    """
    Síntomas detectados por raíz morfológica entre las palabras que no quedaron
    cubiertas por una variante exacta. Mismo formato que _detectar().
    """
    if _STEMMER is None or not _RAICES:
        return []

    cubierto = bytearray(len(texto_norm))
    for _canonico, inicio, fin in spans:
        for i in range(inicio, min(fin, len(texto_norm))):
            cubierto[i] = 1

    hallados = []
    for m in re.finditer(r"[a-z]+", texto_norm):
        palabra = m.group()
        if len(palabra) < LONGITUD_MINIMA_RAIZ:
            continue
        if any(cubierto[m.start():m.end()]):
            continue
        canonico = _RAICES.get(_STEMMER.stem(palabra))
        if canonico:
            hallados.append((canonico, m.start(), m.end()))
    return hallados


def _resolver_localizacion(tokens, indice_fin):
    """
    Síntoma canónico correspondiente a la zona del cuerpo mencionada justo
    después de un dolor genérico, o None si no hay ninguna en la ventana.

    Es lo que permite que varias formas de decir dónde duele produzcan el mismo
    concepto sin escribirlas todas en el catálogo, que guarda las zonas y no las
    combinaciones.
    """
    for token in tokens[indice_fin:indice_fin + VENTANA_LOCALIZACION]:
        canonico = _LOCALIZACIONES.get(token)
        if canonico:
            return canonico
    return None


# ==========================================================
# VALORES NUMERICOS
# ==========================================================

EG_MIN, EG_MAX = 4, 42

PATRONES_VALOR = OrderedDict([
    # exige una palabra obstetrica junto a la cifra: aceptar cualquier
    # 'N semanas' suelto convertia en edad gestacional el tiempo de evolucion
    # de cualquier dolencia
    ("edad_gestacional", re.compile(
        r"(?:gestante|embarazada|embarazo|gestacion|edad gestacional|"
        r"primigestante|multigestante|eg)\s*(?:de\s*)?(\d{1,2})(?:[.,+]\d)?\s*"
        r"(?:semanas?|sem\b|sems?\b|sms\b|sdg\b|s\.?g\.?)"
        r"|(\d{1,2})(?:[.,+]\d)?\s*(?:semanas?|sem\b|sems?\b|sms\b|sdg\b)\s*(?:de\s*)?"
        r"(?:gestacion|embarazo|gestacional|sdg|eg)\b")),
    ("temperatura", re.compile(r"(?:temp(?:eratura)?|fiebre de|t°|tº)\s*:?\s*(\d{2}(?:[.,]\d)?)")),
    ("saturacion", re.compile(r"(?:sat(?:uracion)?|spo2|sato2)\s*:?\s*(\d{2,3})\s*%?")),
    ("frecuencia_cardiaca", re.compile(r"(?:fc|frecuencia cardiaca)\s*:?\s*(\d{2,3})")),
    ("frecuencia_respiratoria", re.compile(r"(?:fr|frecuencia respiratoria)\s*:?\s*(\d{1,2})")),
    ("glicemia", re.compile(r"(?:glucometria|glicemia|hgt)\s*:?\s*(\d{2,3})")),
    ("edad", re.compile(r"(\d{1,3})\s*(?:anos|anos de edad)\b")),
    ("dias_evolucion", re.compile(r"(?:hace|desde hace|de)\s+(\d{1,3})\s*dias?")),
    ("horas_evolucion", re.compile(r"(?:hace|desde hace|de)\s+(\d{1,3})\s*horas?")),
])

RE_TENSION = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b")

RE_EMBARAZO = re.compile(
    r"\b(gestante|embarazada|embarazo|gestacion|primigestante|multigestante|"
    r"trabajo de parto|puerpera|prenatal|obstetric)")

RE_PEDIATRICO = re.compile(
    r"\b(neonato|recien nacido|lactante|menor de|nino|nina|bebe|pediatric|"
    r"escolar|adolescente)")


def _numero(texto):
    """Convierte a número admitiendo la coma decimal. None si no se puede."""
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def extraer_valores(texto_norm):
    """
    Cifras clínicas presentes en la nota, como diccionario. Solo se extrae lo
    que aparece de forma explícita; nada se deduce ni se completa.

    Los valores pasan por un control de rango, que es lo que distingue un dato
    clínico de una coincidencia numérica: una edad gestacional imposible
    significa que el contexto se malinterpretó, y una pareja de cifras separadas
    por barra puede ser una tensión arterial o una fecha.
    """
    valores = {}

    for nombre, patron in PATRONES_VALOR.items():
        m = patron.search(texto_norm)
        if not m:
            continue
        crudo = next((g for g in m.groups() if g), None)
        numero = _numero(crudo)
        if numero is None:
            continue
        valores[nombre] = int(numero) if numero == int(numero) else numero

    # fuera del rango posible de gestacion, el patron capturo otra cosa
    eg = valores.get("edad_gestacional")
    if eg is not None and not (EG_MIN <= eg <= EG_MAX):
        valores.pop("edad_gestacional")

    m = RE_TENSION.search(texto_norm)
    if m:
        sistolica, diastolica = int(m.group(1)), int(m.group(2))
        # descarta rangos imposibles, que casi siempre son fechas
        if 60 <= sistolica <= 260 and 30 <= diastolica <= 160:
            valores["tension_arterial"] = f"{sistolica}/{diastolica}"

    return valores


# ==========================================================
# SINTOMAS
# ==========================================================

def extraer_sintomas(texto_norm, spans=None):
    """
    Reparte los síntomas detectados según su estado y devuelve la tupla
    (presentes, negados, inciertos, antecedentes), cada una como lista de
    conceptos canónicos sin repetidos y en orden de aparición.

    Después del reparto se descartan los genéricos que ya están representados
    por una forma más específica, y se garantiza que un síntoma negado no figure
    además como presente.
    """
    marcado = negacion.marcar(texto_norm, _TERMINOS)
    tokens = [t for t, _ in marcado]
    estados = [e for _, e in marcado]

    grupos = {"afirmado": [], "negado": [], "incierto": [], "antecedente": []}

    for canonico, inicio, fin in (spans if spans is not None else _detectar(texto_norm)):
        palabras = RE_PALABRA.findall(texto_norm[inicio:fin])
        if not palabras:
            continue

        estado = "afirmado"
        # la variante trae su propia negacion dentro: se afirma tal cual
        negacion_propia = palabras[0] in NEGACION_LEXICALIZADA

        for i in range(len(tokens) - len(palabras) + 1):
            if tokens[i:i + len(palabras)] == palabras:
                tramo = estados[i:i + len(palabras)]
                if not negacion_propia:
                    for prioridad in ("negado", "incierto", "antecedente"):
                        if prioridad in tramo:
                            estado = prioridad
                            break
                # un dolor generico con una zona del cuerpo al lado deja de
                # ser generico y pasa a ser el dolor de esa zona
                if canonico in DOLOR_GENERICO:
                    localizado = _resolver_localizacion(tokens, i + len(palabras))
                    if localizado:
                        canonico = localizado
                break

        if canonico not in grupos[estado]:
            grupos[estado].append(canonico)

    _quitar_genericos_redundantes(grupos)

    # un sintoma negado no puede figurar ademas como presente
    for lista in ("negado", "incierto", "antecedente"):
        for s in grupos[lista]:
            if s in grupos["afirmado"]:
                grupos["afirmado"].remove(s)

    return (grupos["afirmado"], grupos["negado"],
            grupos["incierto"], grupos["antecedente"])


def _quitar_genericos_redundantes(grupos):
    """
    Elimina de todos los grupos los síntomas genéricos cuando el texto produjo
    además una forma específica de su misma familia. Modifica las listas en el
    sitio.
    """
    todos = [s for lista in grupos.values() for s in lista]
    for generico, familia in GENERICOS.items():
        if not any(s != generico and any(f in s for f in familia) for s in todos):
            continue
        for lista in grupos.values():
            if generico in lista:
                lista.remove(generico)


# ==========================================================
# CATEGORIA
# ==========================================================

def elegir_categoria(sintomas, texto_norm=""):
    """
    Categoría principal del registro, según la prioridad clínica declarada en el
    catálogo. Si el texto menciona un embarazo, la categoría obstétrica entra en
    juego aunque ningún síntoma la haya aportado. Sin categorías reconocidas
    devuelve la categoría por defecto.
    """
    categorias = {_SINTOMAS[s] for s in sintomas if s in _SINTOMAS}

    if RE_EMBARAZO.search(texto_norm):
        categorias.add("obstetrico")

    if not categorias:
        return CATEGORIA_POR_DEFECTO

    for categoria in _PRIORIDAD:
        if categoria in categorias:
            return categoria
    return sorted(categorias)[0]


def categorias_presentes(sintomas, principal=None):
    """
    Todas las categorías presentes en el registro, ordenadas.

    Siempre incluye la principal: un registro que declara una categoría
    principal y una lista de categorías vacía sería inconsistente consigo mismo.
    """
    categorias = {_SINTOMAS[s] for s in sintomas if s in _SINTOMAS}
    if principal:
        categorias.add(principal)
    return sorted(categorias)


def calcular_confianza(sintomas, categoria, valores):
    """
    Cuánto se puede confiar en la estructuración de esta nota:

        1.0  hay un síntoma reconocido en una categoría clínica específica
        0.6  solo hay síntomas transversales
        0.3  no se reconoció ningún síntoma, pero sí cifras clínicas
        0.1  no se reconoció nada

    Es el campo por el que se filtran los registros poco fiables aguas abajo.
    """
    if sintomas and categoria not in ("general", CATEGORIA_POR_DEFECTO):
        return 1.0
    if sintomas:
        return 0.6
    if valores:
        return 0.3
    return 0.1


# ==========================================================
# REGISTRO COMPLETO
# ==========================================================

def extraer(oid, texto):
    """
    Registro estructurado de una nota, como diccionario ordenado. Es la función
    que consume el orquestador de la fase.

    Los campos opcionales (hallazgos inciertos, antecedentes, edad gestacional,
    valores) solo aparecen cuando hay algo que poner, para que el archivo de
    salida no se llene de campos vacíos.
    """
    texto = RE_ESPACIOS.sub(" ", str(texto or "")).strip()
    texto_norm = normalizar(texto)

    spans = _detectar(texto_norm)
    spans = spans + _detectar_por_raiz(texto_norm, spans)
    sintomas, negados, inciertos, antecedentes = extraer_sintomas(texto_norm, spans)
    valores = extraer_valores(texto_norm)
    categoria = elegir_categoria(sintomas, texto_norm)

    # el embarazo se marca solo si el texto lo dice. Derivarlo de la categoria
    # es un error: hay sintomas de la categoria obstetrica que no implican
    # gestacion, y asi se marcaba como gestante a quien no lo estaba
    embarazo = bool(RE_EMBARAZO.search(texto_norm))
    pediatrico = bool(RE_PEDIATRICO.search(texto_norm))

    registro = OrderedDict()
    registro["oid"] = oid
    registro["categoria_principal"] = categoria
    registro["categorias"] = categorias_presentes(sintomas, categoria)
    registro["sintomas"] = sintomas
    registro["signos_negados"] = negados
    if inciertos:
        registro["hallazgos_inciertos"] = inciertos
    if antecedentes:
        registro["antecedentes"] = antecedentes
    registro["embarazo"] = embarazo
    if valores.get("edad_gestacional"):
        registro["edad_gestacional"] = valores["edad_gestacional"]
    registro["pediatrico"] = pediatrico
    if valores:
        registro["valores"] = valores
    registro["confianza"] = calcular_confianza(sintomas, categoria, valores)
    registro["texto"] = texto
    registro["embedding_texto"] = texto_embedding.construir(
        # el texto CON tildes: el modo extractivo conserva la frase real, y la
        # version plegada solo sirve para cruzar posiciones con el catalogo
        texto=texto,
        categoria=categoria,
        sintomas=sintomas,
        negados=negados,
        inciertos=inciertos,
        valores=valores,
        embarazo=embarazo,
        pediatrico=pediatrico,
        texto_norm=texto_norm,
        spans=spans,
    )

    return registro


def resumen(registros):
    """
    Estadísticas de una corrida: distribución por categoría, síntomas y negados
    más frecuentes, y cuántos registros quedaron sin síntoma reconocido o con
    confianza baja. Es la base del informe de la fase.
    """
    categorias = Counter(r["categoria_principal"] for r in registros)
    sintomas = Counter(s for r in registros for s in r["sintomas"])
    negados = Counter(s for r in registros for s in r["signos_negados"])
    sin_sintoma = sum(1 for r in registros if not r["sintomas"])
    confianza_baja = sum(1 for r in registros if r["confianza"] <= 0.3)

    return {
        "registros": len(registros),
        "sin_sintoma_reconocido": sin_sintoma,
        "confianza_baja": confianza_baja,
        "categorias": categorias.most_common(),
        "sintomas_frecuentes": sintomas.most_common(15),
        "negados_frecuentes": negados.most_common(10),
    }
