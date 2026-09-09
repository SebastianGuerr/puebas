"""
Léxico clínico: el vocabulario médico contra el que se decide qué NO se corrige.

QUÉ PROBLEMA RESUELVE
    Antes de existir este módulo el pipeline reconocía terminología con dos
    fuentes, y ambas fallaban por el mismo lado. El diccionario escrito a mano
    no escala, porque el conjunto de siglas y términos del castellano médico no
    está acotado y siempre falta la siguiente. El vocabulario de spaCy procede
    de texto web: desconoce buena parte de los principios activos y de los
    términos quirúrgicos y, en cambio, acepta faltas de ortografía frecuentes.
    Es decir, protege lo que habría que corregir y deja expuesto lo que habría
    que proteger.

    Al revisar las correcciones que el pipeline no supo hacer, en la mayoría de
    los casos la forma correcta no figuraba en ninguna de las dos fuentes, de
    modo que ningún ajuste de umbrales las habría resuelto.

LAS FUENTES, DE MÁS A MENOS FIABLE
    diccionario_siglas.json   escrito a mano; cada entrada es una decisión
                              deliberada del proyecto.
    catalogo_sintomas.json    variantes de los conceptos clínicos de la fase 4.
    lexico_externo.txt        vocabulario del CIE-10-ES y de cualquier otra
                              fuente externa; un término por línea.
    vocabulario biomédico     palabras enteras del tokenizador de un modelo
                              entrenado sobre historias clínicas en español;
                              es la fuente que aporta el volumen.

    El orden importa: cuando una palabra aparece en varias fuentes se conserva
    la más fiable, y el peso clínico que se le asigna después depende de cuál
    sea.

    El vocabulario biomédico, tomado como detector aislado de terminología,
    acierta casi siempre que dispara pero se le escapa cerca de la mitad de los
    términos reales. Por eso no decide por sí solo: entra como una evidencia más
    en el cálculo de peso clínico.

POR QUÉ SE CONGELA EN UN ARCHIVO
    Cargar el tokenizador del modelo biomédico cuesta segundos y exige tener
    instalados transformers y torch. Como el vocabulario no cambia entre
    corridas, se extrae una sola vez y se guarda en JSON; durante el proceso
    solo se lee ese archivo.

USO

    python -m NLP.recursos.lexico   construye el léxico (la primera vez
                                    necesita red, para descargar el tokenizador)

    cargar()             lo lee, sin modelo ni red
    contiene(palabra)    ¿es terminología?
    forma(palabra)       escritura canónica, con sus tildes
    cercano(palabra)     corrige un término mal escrito contra el léxico, sin
                         pasar por un corrector de español
    vecinos(palabra)     todos los candidatos a esa distancia
"""

import json
import re
from pathlib import Path

from NLP import rutas
from NLP.nucleo import morfologia

RUTA_LEXICO = rutas.LEXICO_CLINICO
RUTA_SIGLAS = rutas.DICCIONARIO_SIGLAS
RUTA_CATALOGO = rutas.CATALOGO_SINTOMAS
RUTA_EXTERNO = rutas.LEXICO_EXTERNO

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
    """Clave de comparación del léxico: minúsculas y sin tildes, con la eñe."""
    return morfologia.sin_tildes(str(palabra).lower().strip())


# ==========================================================
# CONSTRUCCIÓN DEL LÉXICO
# ==========================================================

def _del_diccionario():
    """
    Siglas y términos del diccionario del proyecto. Incorpora también las
    palabras del significado de cada sigla, que son terminología por derecho
    propio ('hipertensión arterial' detrás de 'hta').
    """
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
    """Variantes de síntoma y localizaciones del catálogo de la fase 4."""
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
    Términos de lexico_externo.txt, uno por línea, ignorando comentarios.

    Es la vía para incorporar vocabulario externo (CIE-10-ES, SNOMED o el
    nomenclátor del INVIMA) sin tocar el código. Las líneas con varias palabras
    se parten, porque aquí hace falta vocabulario y no descripciones.
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
    Palabras enteras del vocabulario del tokenizador biomédico.

    El vocabulario BPE mezcla palabras completas con fragmentos, y solo sirven
    las primeras: se reconocen porque el token arranca con el marcador de inicio
    de palabra de los tokenizadores tipo RoBERTa. Un fragmento como 'car' o
    'ectomia' se descarta, porque no es un término sino un trozo.

    Si falta transformers o el modelo no se puede descargar, avisa y devuelve un
    conjunto vacío: el léxico se construye con las demás fuentes.
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
    """
    Reúne el léxico a partir de las cuatro fuentes y lo deja en memoria.
    Devuelve el número de formas distintas.

    Las fuentes se recorren de menos a más fiable, de modo que la más fiable
    sobrescribe a la dudosa cuando ambas traen la misma palabra.
    """
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
    """
    Escribe en disco el léxico construido, junto con el nombre del modelo del
    que salió el vocabulario biomédico. Devuelve el número de formas guardadas.
    """
    datos = {
        "_descripcion": (
            "Lexico clinico. Lo genera lexico.construir() desde el diccionario "
            "del proyecto, el catalogo de sintomas, lexico_externo.txt y el "
            "vocabulario del modelo biomedico. No se edita a mano: para agregar "
            "terminos, escribelos en lexico_externo.txt y regenera con "
            "'python -m NLP.recursos.lexico'."),
        "_modelo_biomedico": MODELO_BIOMEDICO,
        "terminos": {clave: [forma, fuente]
                     for clave, (forma, fuente) in sorted(_TERMINOS.items())},
    }
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=0),
                          encoding="utf-8")
    return len(_TERMINOS)


def cargar(ruta=RUTA_LEXICO):
    """
    Lee el léxico ya construido y devuelve cuántas formas trae, o 0 si el
    archivo todavía no existe. No necesita transformers ni conexión a la red.
    """
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
    """True si hay un léxico cargado en memoria."""
    return bool(_TERMINOS)


def terminos():
    """
    Todas las formas plegadas del léxico. Es la vista de solo lectura que
    necesita quien tiene que recorrerlo entero en vez de consultarlo palabra a
    palabra, como la depuración cuando construye su índice por raíz.
    """
    return _TERMINOS.keys()


# ==========================================================
# CONSULTA DEL LÉXICO
# ==========================================================

def contiene(palabra):
    """True si la palabra figura en el léxico, con tildes o sin ellas."""
    return _plegar(palabra) in _TERMINOS


def fuente(palabra):
    """Fuente de la que procede la palabra, o None si no está en el léxico."""
    entrada = _TERMINOS.get(_plegar(palabra))
    return entrada[1] if entrada else None


def forma(palabra):
    """Escritura canónica del término, con sus tildes, o None si no está."""
    entrada = _TERMINOS.get(_plegar(palabra))
    return entrada[0] if entrada else None


def _indice():
    """
    Índice SymSpell sobre el léxico, para la búsqueda por distancia de edición.
    Se construye la primera vez que se necesita y se reutiliza después.
    """
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
    Forma del léxico más cercana a la palabra, o None si no hay una sola
    candidata clara. Corrige un término médico mal escrito sin recurrir a un
    corrector de español:

        abodominal   -> abdominal
        esplectomia  -> esplenectomia
        dilispidemia -> dislipidemia

    Ante un empate devuelve None: si dos términos clínicos distintos están a la
    misma distancia no hay manera de saber cuál se quiso escribir, y elegir uno
    equivale a inventar un diagnóstico.

    Los candidatos deben además compartir el arranque de la palabra, porque un
    término mal digitado conserva sus primeras letras.
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
    Todas las formas del léxico dentro de la distancia dada, ordenadas de más
    a menos cercana y limitadas a `maximo`.

    A diferencia de cercano(), aquí el empate no es un problema: la lista se
    entrega a la capa de contexto, que desempata leyendo la frase.
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
    """
    Qué sabe el léxico de una palabra: si la contiene, de qué fuente, su forma
    canónica y su vecino más cercano. Herramienta de inspección manual.
    """
    return {
        "palabra": palabra,
        "en_lexico": contiene(palabra),
        "fuente": fuente(palabra),
        "forma_canonica": forma(palabra),
        "cercano": cercano(palabra),
    }


# ==========================================================
# GENERACIÓN DEL ARCHIVO
# ==========================================================

def main():
    """Construye el léxico desde las cuatro fuentes y lo guarda en disco."""
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
