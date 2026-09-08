"""
Lexico clinico: el vocabulario medico contra el que se decide que NO se corrige.

POR QUE HACE FALTA UN LEXICO EXTERNO
    Hasta ahora el proyecto decidia que era terminologia mirando dos cosas: el
    diccionario escrito a mano (483 entradas) y el vocabulario de spaCy. Las
    dos fallan por el mismo lado, y esta medido sobre las omisiones del
    conjunto de referencia:

        el diccionario a mano   no escala. SMS y EDA fueron las siglas de una
                                semana, IVA y DAD las de la siguiente.
        el vocabulario de spaCy es_core_news_md se entreno con texto web. No
                                conoce 'empagliflozina' ni 'esplenectomia', y
                                en cambio SI conoce 'conciente', 'transplante'
                                y 'aprox', que son errores. Protege lo que hay
                                que corregir y deja expuesto lo que hay que
                                proteger.

    Medido sobre 16 correcciones que el pipeline no supo hacer: en 9 de ellas
    la forma correcta no estaba en NINGUNA de las dos fuentes, asi que ningun
    ajuste de umbrales las habria arreglado. Era un techo estructural.

LAS FUENTES, Y QUE APORTA CADA UNA

    diccionario_siglas.json   483 entradas. Escrito a mano, cada una es una
                              decision deliberada. Peso maximo.
    catalogo_sintomas.json    391 variantes de 82 conceptos clinicos.
    vocabulario biomedico     ~10.000 palabras enteras del tokenizador de
                              PlanTL-GOB-ES/roberta-base-biomedical-clinical-es,
                              que se entreno sobre historias clinicas en
                              espanol. Es la fuente que aporta el volumen.
    lexico_externo.txt        opcional, un termino por linea. Es la puerta para
                              meter CIE-10-ES, SNOMED o el nomenclator del
                              INVIMA sin tocar codigo.

MEDIDO SOBRE EL VOCABULARIO BIOMEDICO
    Como detector de 'esto es un termino medico', tomando la palabra entera:

        terminos reales reconocidos  : 19/35   (54%)
        typos falsamente reconocidos : 2/36    ( 6%)

    O sea: cuando dispara acierta el 94% de las veces, y se le escapa casi la
    mitad. Por eso NO se usa solo, sino como uno de los pesos de pesos.py: es
    evidencia fuerte a favor, no un veredicto.

    Los dos falsos positivos son 'transplante' y 'dolro'. El primero es una
    falta de ortografia tan comun que entro al vocabulario del modelo; el
    segundo es un artefacto de la segmentacion BPE. Ambos quedan cubiertos por
    correcciones_directas.

POR QUE SE CONGELA EN UN JSON
    Cargar el tokenizador de HuggingFace cuesta segundos y obliga a tener
    transformers y torch instalados en la maquina que procesa. El vocabulario
    no cambia entre corridas, asi que se extrae UNA vez y se guarda. El runtime
    lee el JSON y no necesita ni el modelo ni la libreria.

COMO SE USA
    python lexico.py            construye lexico_clinico.json (necesita internet
                                la primera vez, para bajar el tokenizador)
    lexico.cargar()             lo lee, sin modelo ni red
    lexico.contiene(palabra)    esta en el lexico?
    lexico.cercano(palabra)     la forma del lexico a distancia <= 2, o None.
                                Es lo que corrige 'abodominal' -> 'abdominal'
                                sin preguntarle a un corrector de espanol.
"""

import json
import re
from pathlib import Path

import morfologia

BASE_DIR = Path(__file__).resolve().parent
RUTA_LEXICO = BASE_DIR / "lexico_clinico.json"
RUTA_SIGLAS = BASE_DIR / "diccionario_siglas.json"
RUTA_CATALOGO = BASE_DIR.parent / "embedding" / "catalogo_sintomas.json"
RUTA_EXTERNO = BASE_DIR / "lexico_externo.txt"

MODELO_BIOMEDICO = "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es"

# Longitud minima para entrar. Por debajo de 4 letras el vocabulario BPE esta
# lleno de fragmentos ('car', 'ico', 'emia') que no son terminos.
LONGITUD_MINIMA = 4

# Distancia de edicion maxima para dar por buena una correccion contra el
# lexico. Con 2 se cubren la transposicion ('dilispidemia'), la letra de mas
# ('abodominal') y la de menos ('esplectomia'); con 3 empiezan a cruzarse
# terminos distintos entre si.
DISTANCIA_MAXIMA = 2

# Fuentes, de mas a menos fiable. El orden importa: fuente() devuelve la
# primera que reconozca la palabra, y pesos.py asigna el peso segun cual sea.
DICCIONARIO = "diccionario"     # escrito a mano
CATALOGO = "catalogo"           # catalogo de sintomas
EXTERNO = "externo"             # CIE-10, SNOMED, INVIMA
BIOMEDICO = "biomedico"         # vocabulario del modelo clinico

_TERMINOS = {}      # forma plegada -> (forma real, fuente)
_SYM = None
_CARGADO = False

RE_ALFABETICA = re.compile(r"^[a-záéíóúüñ]+$")


def _plegar(palabra):
    """Clave de comparacion: minusculas y sin tildes, conservando la eñe."""
    return morfologia.sin_tildes(str(palabra).lower().strip())


# ==========================================================
# CONSTRUCCION
# ==========================================================

def _del_diccionario():
    """Siglas y terminos de diccionario_siglas.json."""
    if not RUTA_SIGLAS.exists():
        return set()
    datos = json.loads(RUTA_SIGLAS.read_text(encoding="utf-8"))
    salida = set()
    for clave, valor in datos.items():
        if clave.startswith("_") or clave in ("patrones_protegidos",
                                              "no_restaurar_mayuscula",
                                              "correcciones_directas"):
            continue
        if isinstance(valor, dict):
            salida.update(valor)
            # el significado tambien es terminologia: 'hipertension arterial'
            for significado in valor.values():
                salida.update(str(significado).split())
        elif isinstance(valor, list):
            salida.update(valor)
    return salida


def _del_catalogo():
    """Variantes de sintoma de catalogo_sintomas.json."""
    if not RUTA_CATALOGO.exists():
        return set()
    datos = json.loads(RUTA_CATALOGO.read_text(encoding="utf-8"))
    salida = set()
    for info in datos.get("sintomas", {}).values():
        for variante in info.get("variantes", []):
            salida.update(str(variante).split())
    salida.update(str(z) for z in datos.get("_localizaciones_dolor", {}))
    return salida


def _del_externo():
    """
    lexico_externo.txt, un termino por linea. Es la puerta de entrada para
    CIE-10-ES, SNOMED o el nomenclator del INVIMA. Las lineas que traen varias
    palabras se parten: lo que hace falta aqui es vocabulario, no descripciones.
    """
    if not RUTA_EXTERNO.exists():
        return set()
    salida = set()
    for linea in RUTA_EXTERNO.read_text(encoding="utf-8").splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#"):
            continue
        salida.update(linea.split())
    return salida


def _del_modelo_biomedico(modelo=MODELO_BIOMEDICO):
    """
    Palabras enteras del vocabulario del tokenizador biomedico.

    El vocabulario BPE mezcla palabras completas con fragmentos. Solo sirven
    las primeras, y se reconocen porque el token arranca con el marcador de
    inicio de palabra ('Ġ' en los tokenizadores tipo RoBERTa). Un fragmento
    como 'car' o 'ectomia' se descarta: no es un termino, es un trozo.
    """
    try:
        from transformers import AutoTokenizer
    except ModuleNotFoundError:
        print("  aviso: transformers no instalado; se omite el vocabulario biomedico.")
        return set()

    try:
        tok = AutoTokenizer.from_pretrained(modelo)
    except Exception as exc:
        print(f"  aviso: no se pudo cargar {modelo} ({exc}); se omite.")
        return set()

    salida = set()
    for token in tok.get_vocab():
        if not token.startswith("Ġ"):
            continue
        palabra = token[1:].lower()
        if len(palabra) >= LONGITUD_MINIMA and RE_ALFABETICA.match(palabra):
            salida.add(palabra)
    return salida


def construir():
    """Arma el lexico desde todas las fuentes. Devuelve el numero de entradas."""
    _TERMINOS.clear()

    # de menos a mas fiable: la fuente buena pisa a la dudosa
    for fuente, palabras in ((BIOMEDICO, _del_modelo_biomedico()),
                             (EXTERNO, _del_externo()),
                             (CATALOGO, _del_catalogo()),
                             (DICCIONARIO, _del_diccionario())):
        agregadas = 0
        for palabra in palabras:
            palabra = str(palabra).lower().strip()
            if len(palabra) < LONGITUD_MINIMA or not RE_ALFABETICA.match(palabra):
                continue
            _TERMINOS[_plegar(palabra)] = (palabra, fuente)
            agregadas += 1
        print(f"  {fuente:12} {agregadas:>7,} formas")

    return len(_TERMINOS)


def guardar(ruta=RUTA_LEXICO):
    datos = {
        "_descripcion": (
            "Lexico clinico. Lo genera lexico.construir() desde el diccionario "
            "del proyecto, el catalogo de sintomas, lexico_externo.txt y el "
            "vocabulario del modelo biomedico. No se edita a mano: para agregar "
            "terminos, escribelos en lexico_externo.txt y regenera con "
            "'python lexico.py'."),
        "_modelo_biomedico": MODELO_BIOMEDICO,
        "terminos": {clave: [forma, fuente]
                     for clave, (forma, fuente) in sorted(_TERMINOS.items())},
    }
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=0),
                          encoding="utf-8")
    return len(_TERMINOS)


def cargar(ruta=RUTA_LEXICO):
    """Lee el lexico ya construido. No necesita transformers ni red."""
    global _CARGADO, _SYM
    ruta = Path(ruta)
    if not ruta.exists():
        return 0
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    _TERMINOS.clear()
    for clave, (forma, fuente) in datos.get("terminos", {}).items():
        _TERMINOS[clave] = (forma, fuente)
    _SYM = None
    _CARGADO = bool(_TERMINOS)
    return len(_TERMINOS)


def disponible():
    return bool(_TERMINOS)


# ==========================================================
# CONSULTA
# ==========================================================

def contiene(palabra):
    """True si la palabra es un termino del lexico clinico."""
    return _plegar(palabra) in _TERMINOS


def fuente(palabra):
    """De que fuente viene la palabra, o None si no esta."""
    entrada = _TERMINOS.get(_plegar(palabra))
    return entrada[1] if entrada else None


def forma(palabra):
    """La escritura canonica del termino (con sus tildes), o None."""
    entrada = _TERMINOS.get(_plegar(palabra))
    return entrada[0] if entrada else None


def _indice():
    """Indice SymSpell sobre el lexico, para la busqueda difusa. Perezoso."""
    global _SYM
    if _SYM is not None:
        return _SYM
    try:
        from symspellpy import SymSpell
    except ModuleNotFoundError:
        return None
    sym = SymSpell(max_dictionary_edit_distance=DISTANCIA_MAXIMA, prefix_length=10)
    for clave in _TERMINOS:
        sym.create_dictionary_entry(clave, 1)
    _SYM = sym
    return _SYM


def cercano(palabra, distancia=DISTANCIA_MAXIMA):
    """
    La forma del lexico mas cercana a la palabra, o None si no hay una sola
    clara. Es lo que corrige un termino medico mal escrito SIN pasar por un
    corrector de espanol:

        abodominal   -> abdominal
        esplectomia  -> esplenectomia
        dilispidemia -> dislipidemia

    Devuelve None ante el empate. Si dos terminos clinicos distintos estan a la
    misma distancia no hay forma de saber cual se quiso escribir, y elegir uno
    inventa un diagnostico. Es la misma politica de abstencion del resto del
    proyecto.
    """
    sym = _indice()
    if sym is None or len(palabra) < LONGITUD_MINIMA:
        return None

    from symspellpy import Verbosity

    clave = _plegar(palabra)
    if clave in _TERMINOS:
        return _TERMINOS[clave][0]

    try:
        sugerencias = sym.lookup(clave, Verbosity.CLOSEST, max_edit_distance=distancia)
    except Exception:
        return None
    if not sugerencias:
        return None

    minima = min(s.distance for s in sugerencias)
    empatadas = [s for s in sugerencias if s.distance == minima]

    # un termino medico conserva su arranque aunque se digite mal; si el
    # candidato no comparte las primeras letras es otra palabra, no un typo
    empatadas = [s for s in empatadas
                 if s.term[:2] == clave[:2] or morfologia.sin_tildes(s.term)[:3] == clave[:3]]
    if len(empatadas) != 1:
        return None

    return _TERMINOS[empatadas[0].term][0]


def vecinos(palabra, distancia=DISTANCIA_MAXIMA, maximo=5):
    """
    TODAS las formas del lexico a distancia <= n, no solo la mejor.

    cercano() se abstiene ante el empate porque tiene que decidir sola. Aqui no
    hace falta: la lista va a contexto.py, que elige mirando la frase. Un
    empate ortografico deja de ser un problema cuando hay un desempate mejor.
    """
    sym = _indice()
    if sym is None or len(palabra) < LONGITUD_MINIMA:
        return []

    from symspellpy import Verbosity

    clave = _plegar(palabra)
    try:
        sugerencias = sym.lookup(clave, Verbosity.CLOSEST, max_edit_distance=distancia)
    except Exception:
        return []

    salida = []
    for s in sorted(sugerencias, key=lambda s: s.distance):
        if s.term == clave:
            continue
        forma = _TERMINOS.get(s.term, (s.term, None))[0]
        if forma not in salida:
            salida.append(forma)
        if len(salida) >= maximo:
            break
    return salida


def diagnosticar(palabra):
    """Que sabe el lexico de una palabra. Para revisar casos puntuales."""
    return {
        "palabra": palabra,
        "en_lexico": contiene(palabra),
        "fuente": fuente(palabra),
        "forma_canonica": forma(palabra),
        "cercano": cercano(palabra),
    }


# ==========================================================
# GENERACION
# ==========================================================

def main():
    print(f"Construyendo lexico clinico...")
    total = construir()
    guardar()
    print(f"\nLexico: {total:,} formas distintas")
    print(f"Guardado en {RUTA_LEXICO}")
    if not RUTA_EXTERNO.exists():
        print(f"\nPara agregar CIE-10, SNOMED o el nomenclator del INVIMA:")
        print(f"  escribe un termino por linea en {RUTA_EXTERNO.name} y vuelve a correr.")


if __name__ == "__main__":
    main()
