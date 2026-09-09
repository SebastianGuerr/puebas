"""
Extractor por modelo de lenguaje: quedarse con el motivo de consulta.

QUÉ HACE, Y POR QUÉ NO LO HACÍA NADA ANTERIOR
    Las fases previas corrigen palabras. Esta decide QUÉ PARTE de la nota dice
    por qué vino el paciente, que es una pregunta de comprensión y no de
    ortografía. Los patrones de reduccion.py la responden enumerando lo que
    sobra, y el clasificador de frases.py la responde por tramos; ninguno de los
    dos entiende la frase.

    Aquí se le pasa la nota a un modelo local y se le pide que devuelva los
    fragmentos que son motivo de consulta.

EL RIESGO, Y POR QUÉ AQUÍ NO ES UN RIESGO
    Un modelo pequeño inventa. En una nota clínica eso sería inaceptable si el
    modelo escribiera el resultado, porque un dato falso es indistinguible de
    uno real.

    Por eso NO se le pide que reescriba: se le pide que COPIE. Cada fragmento
    que devuelve tiene que aparecer literalmente en la nota, y eso se comprueba:

        if fragmento not in nota:   # se lo invento
            se descarta

    Un modelo que alucina no mete un dato falso: falla de forma visible y esa
    nota cae al método anterior. La alucinación pasa de ser un riesgo silencioso
    a un error detectable, que es el mismo principio con el que funciona el
    resto del proyecto: el modelo propone, las reglas verifican.

DÓNDE SE APLICA, Y POR QUÉ NO A TODO
    La mediana de las notas del corpus son 6 palabras ('dolor abdominal',
    'tengo fiebre'). Ahí no hay nada que extraer y los patrones ya aciertan.
    El problema está en la cola larga:

        notas de mas de 30 palabras   1.959
        notas de mas de 15 palabras  ~6.000

    Medido en esta maquina (i7-8550U, 4 nucleos, sin GPU), un modelo de 3B en
    Q4 tarda del orden de 3 s por nota. Pasar las 28.000 serian ~27 horas;
    pasar solo las largas, entre 2 y 6. El umbral es LONGITUD_MINIMA y es la
    decision de diseño mas importante del modulo: el modelo se usa donde el
    metodo barato falla, no en todas partes.

SI ALGO FALLA, NO PASA NADA
    Sin servidor, sin modelo, con respuesta ilegible o con fragmentos
    inventados, extraer() devuelve None y quien llama se queda con el recorte
    anterior. Este modulo solo puede mejorar el resultado o dejarlo igual.
"""

import json
import re
import unicodedata
import urllib.error
import urllib.request

from NLP import rutas

# ==========================================================
# CONFIGURACION
# ==========================================================

SERVIDOR = "http://localhost:11434"
MODELO = "qwen2.5:3b-instruct"

# Solo se envian al modelo las notas por encima de esta longitud. Ver la
# cabecera: por debajo, el metodo barato ya acierta y el modelo solo cuesta.
LONGITUD_MINIMA = 15

TIMEOUT = 120           # segundos por nota
MAX_TOKENS = 300

# Temperatura cero: la misma nota tiene que dar siempre el mismo resultado. Sin
# esto, dos corridas del pipeline producen dos corpus distintos y ninguna
# medicion es comparable con la anterior.
TEMPERATURA = 0.0

# Fraccion maxima de la nota que puede sobrevivir. Una respuesta que devuelve
# casi todo no ha extraido nada, y suele significar que el modelo copio la nota
# entera en vez de elegir.
FRACCION_MAXIMA = 0.85


INSTRUCCIONES = """Eres un asistente que prepara notas de triage hospitalario para un analisis estadistico.

Tu tarea: de la nota que te doy, devolver SOLO los fragmentos que dicen POR QUE vino el paciente hoy.

CONSERVA:
- sintomas y molestias que refiere el paciente
- lesiones, traumatismos y su mecanismo
- hallazgos clinicos del episodio actual
- las negaciones de sintomas, COMPLETAS ("ahora sin sangrado", "niega fiebre").
  Una negacion dice que el cuadro se resolvio; quitarla lo convierte en activo.
- los hallazgos de estudios previos que explican el cuadro (un diagnostico
  encontrado en una biopsia, una fractura vista en radiografia)

DESCARTA:
- como llego al servicio, quien lo acompana, de que municipio viene
- avisos de la EPS, disculpas, niveles de atencion, criterios de urgencia
- hallazgos del examen fisico rutinario (estable, orientado, normotenso)
- lo que decidio o hizo el personal (se deriva, se dan recomendaciones)
- antecedentes y enfermedades previas que no son el motivo de hoy
- edad, sexo y cuanto tiempo lleva con el cuadro

REGLA ABSOLUTA: copia los fragmentos EXACTAMENTE como aparecen en la nota.
No corrijas la ortografia, no reescribas, no resumas, no traduzcas, no anadas
palabras. Otra fase ya se encargo de corregir el texto.
Si dudas de un fragmento, CONSERVALO: perder un sintoma cuesta mucho mas que
arrastrar una frase de mas.

EJEMPLOS

Nota: ingresa paciente en silla de ruedas con acompanante refiriendo que le han
dado varias epistaxis de dificil control ahora presento sangrado ahora paciente
sin epistaxis, normocardico. paciente en el momento clinicamente estable, ahora
sin criterios que constituyan ser una urgencia vital para ser atendida en un
tercer nivel de atencion.
Respuesta: {"fragmentos": ["le han dado varias epistaxis de dificil control", "ahora presento sangrado", "ahora paciente sin epistaxis"]}

Nota: desde principios de marzo, sangrado en el popo, paciente que ingresa en
compania de hija refiere hospitalizacion reciente en la dorada, donde realizan
examenes, colonoscopia, biopsia de recto donde encuentran adenocarcinoma
Respuesta: {"fragmentos": ["sangrado en el popo", "biopsia de recto donde encuentran adenocarcinoma"]}

Nota: ingresa menor de edad traida por la madre la cual refiere que desde el fin
de semana con esta con diarrea, fiebre, vomito y tos, anoche paso muy mala
noche, en el momento menor despierta, alerta, no signos de dificultad
respiratoria, tos seca, se dan recomendaciones y se deriva a su ips asignada
Respuesta: {"fragmentos": ["diarrea, fiebre, vomito y tos", "anoche paso muy mala noche", "tos seca"]}

Responde unicamente con un JSON con esa forma, sin nada mas."""


_DISPONIBLE = None
_CACHE = {}


# ==========================================================
# SERVIDOR
# ==========================================================

def disponible():
    """True si el servidor responde y el modelo esta instalado."""
    global _DISPONIBLE
    if _DISPONIBLE is not None:
        return _DISPONIBLE
    try:
        with urllib.request.urlopen(f"{SERVIDOR}/api/tags", timeout=5) as r:
            datos = json.loads(r.read())
        nombres = {m.get("name", "") for m in datos.get("models", [])}
        _DISPONIBLE = MODELO in nombres
        if not _DISPONIBLE:
            print(f"Aviso: {MODELO} no esta instalado. Instalados: {sorted(nombres)}")
    except Exception as exc:
        print(f"Aviso: Ollama no responde en {SERVIDOR} ({exc}); el extractor queda desactivado.")
        _DISPONIBLE = False
    return _DISPONIBLE


def _preguntar(nota):
    """Manda la nota al modelo y devuelve su respuesta cruda, o None."""
    cuerpo = json.dumps({
        "model": MODELO,
        "prompt": f"NOTA:\n{nota}",
        "system": INSTRUCCIONES,
        "stream": False,
        "format": "json",
        "options": {"temperature": TEMPERATURA, "num_predict": MAX_TOKENS},
    }).encode("utf-8")

    peticion = urllib.request.Request(
        f"{SERVIDOR}/api/generate", data=cuerpo,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(peticion, timeout=TIMEOUT) as r:
            return json.loads(r.read()).get("response", "")
    except Exception as exc:
        print(f"  aviso: fallo la peticion al modelo ({exc})")
        return None


# ==========================================================
# VERIFICACION
# ==========================================================

def _plegar(texto):
    """
    Forma de comparacion: minusculas, sin tildes y con los espacios colapsados.

    Se compara asi y no literalmente porque el modelo, aun pidiendole que copie,
    a veces devuelve el fragmento con otra capitalizacion o sin una tilde. Eso
    no es inventar: las letras son las mismas y el fragmento sigue estando en la
    nota. Lo que esta comprobacion tiene que atrapar es el texto que NO esta.
    """
    plano = unicodedata.normalize("NFD", str(texto).lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", plano).strip()


def verificar(nota, fragmentos):
    """
    Separa los fragmentos que estan de verdad en la nota de los inventados.

    Devuelve la pareja (validos, inventados). Es la unica defensa que hace
    aceptable un modelo de 3B sobre texto clinico, y por eso no tiene
    excepciones: un fragmento que no aparece en la nota se descarta siempre,
    por muy razonable que suene.
    """
    plano_nota = _plegar(nota)
    validos, inventados = [], []
    for f in fragmentos:
        f = str(f).strip(" ,.;:-")
        if len(f.split()) < 2:
            continue
        (validos if _plegar(f) in plano_nota else inventados).append(f)
    return validos, inventados


def _ordenar_como_la_nota(nota, fragmentos):
    """
    Devuelve los fragmentos en el orden en que aparecen en la nota, sin
    solaparse. El modelo los enumera en el orden que quiere, y una nota
    reordenada deja de leerse como la escribio quien atendio al paciente.
    """
    plano = _plegar(nota)
    posiciones = []
    for f in fragmentos:
        i = plano.find(_plegar(f))
        if i >= 0:
            posiciones.append((i, f))
    posiciones.sort()

    salida, ultimo = [], -1
    for i, f in posiciones:
        if i >= ultimo:
            salida.append(f)
            ultimo = i + len(_plegar(f))
    return salida


# ==========================================================
# EXTRACCION
# ==========================================================

def extraer(nota, detalle=False):
    """
    El motivo de consulta de la nota segun el modelo, o None si no se puede.

    Devuelve None -- y quien llama se queda con el recorte anterior -- cuando la
    nota es corta, el servidor no responde, la respuesta no es JSON legible, no
    sobrevive ningun fragmento a la verificacion, o lo que sobrevive es casi
    toda la nota (senal de que el modelo copio en vez de elegir).

    Con detalle=True devuelve un diccionario con lo que paso en cada paso, para
    revisar casos concretos.
    """
    nota = str(nota or "").strip()
    info = {"nota": nota, "motivo": None, "fragmentos": [], "inventados": [],
            "estado": None}

    if len(nota.split()) < LONGITUD_MINIMA:
        info["estado"] = "nota corta: no se envia al modelo"
        return info if detalle else None

    if not disponible():
        info["estado"] = "modelo no disponible"
        return info if detalle else None

    if nota in _CACHE:
        info.update(_CACHE[nota])
        return info if detalle else info["motivo"]

    cruda = _preguntar(nota)
    if not cruda:
        info["estado"] = "sin respuesta del modelo"
        return info if detalle else None

    try:
        fragmentos = json.loads(cruda).get("fragmentos", [])
    except Exception:
        info["estado"] = "respuesta no es JSON legible"
        return info if detalle else None

    validos, inventados = verificar(nota, fragmentos)
    info["inventados"] = inventados
    if not validos:
        info["estado"] = ("todo inventado" if inventados else "no devolvio nada")
        return info if detalle else None

    validos = _ordenar_como_la_nota(nota, validos)
    motivo = ", ".join(validos)

    if len(motivo.split()) > FRACCION_MAXIMA * len(nota.split()):
        info["estado"] = "devolvio casi toda la nota: no extrajo"
        return info if detalle else None

    info["motivo"] = motivo
    info["fragmentos"] = validos
    info["estado"] = "ok" + (f" ({len(inventados)} inventados descartados)" if inventados else "")
    _CACHE[nota] = {"motivo": motivo, "fragmentos": validos,
                    "inventados": inventados, "estado": info["estado"]}
    return info if detalle else motivo


def diagnosticar(nota):
    """Que hizo el modelo con una nota concreta, paso a paso."""
    return extraer(nota, detalle=True)
