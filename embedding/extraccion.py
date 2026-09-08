"""
Fase 4. Extraccion estructurada de la nota clinica.

Convierte una nota ya limpia en un registro con sintomas, hallazgos negados,
valores numericos y categoria. No corrige ortografia ni normaliza siglas: eso
ya paso en la fase anterior.

    "Paciente gestante de 22 semanas que consulta por dolor pelvico intenso,
     niega perdidas vaginales, movimientos fetales activos."

    -> categoria_principal: obstetrico
       sintomas: ["dolor pelvico", "movimientos fetales"]
       signos_negados: ["sangrado vaginal"]
       embarazo: true
       edad_gestacional: 22

COMO SE DETECTAN LOS SINTOMAS
    Con FlashText sobre catalogo_sintomas.json, que mapea cada variante de
    escritura a un concepto canonico. 'dolor de cabeza', 'cefalea' y 'jaqueca'
    producen el mismo sintoma, que es lo que reduce la dispersion al agrupar.
    FlashText prefiere la coincidencia mas larga, asi que 'dolor abdominal'
    gana sobre 'dolor'.

    Antes de buscar, texto y catalogo se llevan a una misma forma de
    comparacion: minusculas y sin tildes. Y de cada variante se derivan
    automaticamente su plural y su singular. Esto es lo que evita tener que
    escribir a mano en el JSON 'colico', 'cólico', 'colicos' y 'cólicos' para
    un solo concepto: se declara uno y las cuatro formas quedan cubiertas.
    Es la diferencia entre ampliar cobertura por regla y ampliarla agregando
    cadenas sueltas cada vez que aparece un caso nuevo.

COMO SE DECIDE SI ESTA PRESENTE O NEGADO
    Cada sintoma detectado se consulta contra negacion.marcar(), que devuelve
    el estado de cada palabra. Un sintoma negado no va a 'sintomas': va a
    'signos_negados'. Sin esta separacion, 'niega fiebre' y 'fiebre' caen en
    el mismo grupo al agrupar, que es el error mas caro de esta fase.

COMO SE ELIGE LA CATEGORIA
    Por prioridad clinica declarada en el catalogo, no por conteo. Una
    gestante con tos es un caso obstetrico, y un politraumatizado con cefalea
    es un trauma: manda la condicion que decide la conducta, no la que mas
    palabras ocupa. 'general' va ultima en esa prioridad: agrupa los sintomas
    transversales (dolor sin localizar, malestar, fatiga) y solo decide cuando
    no hay nada de un aparato especifico, para que un registro con contenido
    clinico real nunca termine en 'inespecifico' con los campos vacios.
"""

import json
import sys
import re
import unicodedata
from collections import Counter, OrderedDict
from pathlib import Path

# la carpeta de este archivo va primero en sys.path para que los modulos
# vecinos (negacion, texto_embedding) se encuentren sin importar desde
# que directorio se ejecute el script
sys.path.insert(0, str(Path(__file__).resolve().parent))

import negacion
import texto_embedding

RUTA_CATALOGO = Path(__file__).resolve().parent / "catalogo_sintomas.json"

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

# palabras de negacion que forman parte de la propia expresion del sintoma:
# en 'no ve bien', 'no puede orinar' o 'sin fuerzas' la negacion esta
# lexicalizada dentro del concepto y no lo niega. Solo aplica cuando el
# disparador cae DENTRO del tramo detectado: en 'no hay fiebre' el 'no' queda
# afuera del span 'fiebre' y sigue negando normalmente
NEGACION_LEXICALIZADA = {"no", "sin"}
LONGITUD_MINIMA_RAIZ = 5   # palabras mas cortas no se buscan por raiz

RE_ESPACIOS = re.compile(r"\s+")
RE_PALABRA = re.compile(r"[\wáéíóúüñ]+")

# genericos -> fragmentos que identifican una variante mas especifica de la
# misma familia. 'dolor' y 'sangrado' solo aportan cuando no se pudo saber
# cual era: si el texto tambien produjo 'cefalea' o 'sangrado vaginal', el
# generico sobra y quitarlo evita perder especificidad al agrupar.
DOLOR_GENERICO = {"dolor inespecifico"}

GENERICOS = {
    "dolor inespecifico": ("dolor", "algia", "cefalea", "colico", "pirosis"),
    "sangrado inespecifico": ("sangrado", "rragia", "hematuria", "hematemesis",
                              "melenas", "epistaxis"),
}


# ==========================================================
# NORMALIZACION PARA COMPARAR
# ==========================================================

def normalizar(texto):
    """
    Minusculas y sin tildes, conservando la longitud del texto caracter por
    caracter. Eso ultimo importa: los spans que devuelve FlashText sobre el
    texto normalizado tienen que seguir apuntando a la misma posicion en el
    texto original.
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
    La variante mas su plural o su singular, derivados de la ultima palabra.
    Cubre la variacion morfologica regular del espanol sin enumerarla en el
    JSON: 'colico' cubre 'colicos', 'nauseas' cubre 'nausea'.
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
# CARGA
# ==========================================================

def cargar(ruta=RUTA_CATALOGO):
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
    Indice por raiz morfologica, para las formas que el catalogo no puede
    listar: los verbos. 'convulsiono' no es plural de 'convulsion' ni se
    deriva de ella por regla de numero, pero comparten raiz; lo mismo
    'sangre'/'sangro' con 'sangrado'. Un stemmer resuelve toda esa familia de
    una vez, en lugar de agregar cada conjugacion al JSON.

    Solo se indexan raices que apunten a un unico canonico: si dos conceptos
    distintos comparten raiz, la raiz es ambigua y se descarta entera, porque
    un acierto dudoso aca contamina la categoria del registro completo.
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
    """[(canonico, inicio, fin)] de todas las variantes encontradas."""
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
    Palabras sueltas que no quedaron cubiertas por una variante exacta pero
    cuya raiz apunta sin ambiguedad a un sintoma del catalogo.
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
    Zona del cuerpo mencionada justo despues de un dolor generico. Es lo que
    convierte 'dolor en pecho', 'me duele el pecho' y 'dolor abajo del seno'
    en el mismo canonico sin escribir las tres frases en el JSON: el catalogo
    guarda las zonas, no las combinaciones.
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
    # exige una palabra obstetrica pegada a la cifra. El patron anterior
    # aceptaba cualquier 'N semanas' suelto, y por eso '1 semana con dolor en
    # la rodilla' producia edad_gestacional=1: el problema no era el numero,
    # era que nunca se miraba el contexto
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
    try:
        return float(str(texto).replace(",", "."))
    except (TypeError, ValueError):
        return None


def extraer_valores(texto_norm):
    """Cifras clinicas presentes en la nota. Solo lo que aparece explicito."""
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

    # fuera de 4-42 semanas no hay gestacion posible: si el patron llego aca
    # con otra cifra, el contexto se malinterpreto y el valor se descarta
    eg = valores.get("edad_gestacional")
    if eg is not None and not (EG_MIN <= eg <= EG_MAX):
        valores.pop("edad_gestacional")

    m = RE_TENSION.search(texto_norm)
    if m:
        sistolica, diastolica = int(m.group(1)), int(m.group(2))
        # descarta rangos imposibles: '120/80' es tension, '12/10' es una fecha
        if 60 <= sistolica <= 260 and 30 <= diastolica <= 160:
            valores["tension_arterial"] = f"{sistolica}/{diastolica}"

    return valores


# ==========================================================
# SINTOMAS
# ==========================================================

def extraer_sintomas(texto_norm, spans=None):
    """
    (presentes, negados, inciertos, antecedentes), cada uno como lista de
    sintomas canonicos sin repetir y en orden de aparicion.
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
        # la variante trae su propia negacion adentro: se afirma tal cual
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
                # ser generico: 'dolor en pecho' es dolor toracico
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
    Siempre incluye la categoria principal: un registro con
    categoria_principal y categorias=[] es inconsistente consigo mismo.
    """
    categorias = {_SINTOMAS[s] for s in sintomas if s in _SINTOMAS}
    if principal:
        categorias.add(principal)
    return sorted(categorias)


def calcular_confianza(sintomas, categoria, valores):
    """
    Que tanto se puede confiar en la estructuracion de esta nota:
        1.0  sintoma reconocido en una categoria clinica especifica
        0.6  solo sintomas transversales (categoria general)
        0.3  nada reconocido, pero hay cifras clinicas
        0.1  nada
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
    """Registro estructurado de una nota. Es la funcion que usa estructurar.py."""
    texto = RE_ESPACIOS.sub(" ", str(texto or "")).strip()
    texto_norm = normalizar(texto)

    spans = _detectar(texto_norm)
    spans = spans + _detectar_por_raiz(texto_norm, spans)
    sintomas, negados, inciertos, antecedentes = extraer_sintomas(texto_norm, spans)
    valores = extraer_valores(texto_norm)
    categoria = elegir_categoria(sintomas, texto_norm)

    # embarazo solo si el texto lo dice. Derivarlo de la categoria era un
    # error: 'dolor pelvico' pertenece a la categoria obstetrica del catalogo,
    # y eso marcaba como gestante a cualquiera con dolor en bajo vientre
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
        # el texto CON tildes: el modo extractivo conserva la frase real y
        # texto_norm viene plegado para poder cruzar spans con el catalogo
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
    """Distribucion por categoria y sintomas mas frecuentes. Para auditar."""
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
