"""
Fase 5b: pide a un modelo de lenguaje local (Ollama) los fragmentos que son
motivo de consulta y verifica que existan literalmente en la nota; lo que no
se localiza se descarta (el modelo propone, las reglas verifican). Si algo
falla, extraer() devuelve None y reduccion.py conserva su propio recorte. Ver
NLP/docs/FLUJO.md seccion 7, NLP/docs/decisiones/2026-09-15-modelo-generativo.md
y NLP/docs/decisiones/2026-09-16-reduccion-extractor-umbrales.md.
"""

import json
import re
import unicodedata
import urllib.error
import urllib.request


# ==========================================================
# CONFIGURACION
# ==========================================================

SERVIDOR = "http://localhost:11434"
MODELO = "qwen2.5:3b-instruct"

# Longitud minima para consultar al modelo. En 1 significa que las ve TODAS,
# a proposito: el modelo tambien dictamina si hay motivo de consulta o no, y
# ese dictamen hace falta en las notas cortas tanto como en las largas. Ver
# docs/decisiones/2026-09-16-reduccion-extractor-umbrales.md (medicion y costo).
LONGITUD_MINIMA = 1

# El modelo leyo la nota y concluyo que no hay motivo de consulta. Es una
# RESPUESTA, no un fallo, y por eso tiene nombre propio: quien llama la
# distingue de un error del modelo y puede dejar la nota intacta a proposito.
ESTADO_SIN_CONTEXTO = "sin informacion relevante"

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

# Fraccion de la evidencia clinica del recorte por reglas que la extraccion del
# modelo tiene que conservar para darla por buena. La verificacion solo
# comprueba que el fragmento ESTE en la nota, no que este completo; este
# segundo criterio compara terminologia (no longitud) contra el recorte por
# reglas. Ver docs/decisiones/2026-09-16-reduccion-extractor-umbrales.md.
FRACCION_CLINICA_MINIMA = 0.50



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

Nota: ingresa paciente refiriendo que salio de trasnocho con dolor cabeza, dolor
en el cuerpo y diarrea, paciente con mucosas hidratadas, paciente en el momento
clinica y hemodinamicamente estable sin criterios que requieran manejo en tercer
nivel de complejidad, se dan recomendaciones y se deriva a su eps
Respuesta: {"fragmentos": ["dolor cabeza, dolor en el cuerpo y diarrea"]}


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

def _plegar_con_mapa(texto):
    """
    Devuelve la forma plegada del texto y un mapa de posiciones al original.

    `mapa[i]` es la posicion en el texto original del caracter i del plegado, y
    eso es lo que permite recuperar despues el texto TAL CUAL lo escribio quien
    atendio al paciente. El plegado baja a minusculas, quita tildes y colapsa
    los espacios; ninguna de las tres cosas se aplica al resultado final.
    """
    plano, mapa, espacio = [], [], False
    for i, c in enumerate(str(texto)):
        if c.isspace():
            if not espacio and plano:
                plano.append(" ")
                mapa.append(i)
                espacio = True
            continue
        espacio = False
        base = unicodedata.normalize("NFD", c.lower())
        base = "".join(x for x in base if not unicodedata.combining(x)) or c.lower()
        # una letra puede plegarse a varias; todas apuntan a la misma posicion
        for b in base:
            plano.append(b)
            mapa.append(i)
    return "".join(plano), mapa


def _plegar(texto):
    """Forma de comparacion: minusculas, sin tildes, espacios colapsados."""
    return _plegar_con_mapa(texto)[0].strip()


def _limite_palabra(plano, inicio, fin):
    """True si el tramo [inicio, fin) no parte una palabra por ninguno de sus dos lados."""
    antes = plano[inicio - 1] if inicio > 0 else " "
    despues = plano[fin] if fin < len(plano) else " "
    return not (antes.isalnum() or despues.isalnum())


# Fraccion de las palabras del fragmento que tienen que aparecer en la nota,
# en el mismo orden, para dar por bueno que el fragmento señala ese tramo.
#
# POR QUE HAY UNA TOLERANCIA Y NO UNA IGUALDAD EXACTA
#     'Apunta mal' y 'se lo inventa' son dos cosas distintas, y exigir igualdad
#     las trataba igual. Un fragmento que difiere en una palabra de un tramo de
#     la nota ESTA señalando ese tramo; uno que no se parece a nada no señala
#     nada. Rechazar los dos por igual tira informacion buena.
#
#     Y la tolerancia no abre ninguna puerta, porque lo que se devuelve siguen
#     siendo POSICIONES: el texto lo pone la nota. El modelo puede apuntar con
#     mala punteria, pero no puede escribir. Esa es la propiedad que hace
#     seguro relajar el resto.
FRACCION_PALABRAS_MINIMA = 0.70

# Un fragmento de una o dos palabras no admite tolerancia: con tan pocas
# palabras, 'la mayoria coincide' deja de ser evidencia de nada.
PALABRAS_PARA_TOLERAR = 4


def _palabras_con_posicion(texto):
    """Las palabras plegadas del texto, cada una con su posicion en el original."""
    plano, mapa = _plegar_con_mapa(texto)
    salida = []
    for m in re.finditer(r"[^\W_]+", plano, re.UNICODE):
        salida.append((m.group(0), mapa[m.start()], mapa[m.end() - 1] + 1))
    return salida


def localizar(nota, fragmento):
    """
    Donde empieza y acaba el fragmento dentro de la nota, o None si no esta.

    Devuelve SIEMPRE posiciones, nunca texto: el modelo no puede alterar un
    caracter aunque su fragmento venga con otra capitalizacion o una palabra
    cambiada. Dos pasadas: (1) coincidencia exacta en limite de palabra, (2)
    alineacion tolerante por palabras cuando el modelo copio mal una palabra.
    Lo que no encaja en ninguna de las dos no esta en la nota.
    """
    plano_nota, mapa = _plegar_con_mapa(nota)
    plano_frag = _plegar(fragmento)
    if not plano_frag:
        return None

    # 1. exacta
    desde = 0
    while True:
        i = plano_nota.find(plano_frag, desde)
        if i < 0:
            break
        if _limite_palabra(plano_nota, i, i + len(plano_frag)):
            return mapa[i], mapa[i + len(plano_frag) - 1] + 1
        desde = i + 1

    # 2. tolerante, alineando palabra a palabra
    return _localizar_alineando(nota, fragmento)


def _localizar_alineando(nota, fragmento):
    """
    Alinea las palabras del fragmento con las de la nota y devuelve el tramo que
    cubren, o None si coinciden demasiado pocas.

    Usa SequenceMatcher sobre listas de palabras (no distancia de edicion sobre
    caracteres) porque lo que hay que medir es cuantas PALABRAS del fragmento
    estan de verdad en la nota, en orden.
    """
    from difflib import SequenceMatcher

    palabras_nota = _palabras_con_posicion(nota)
    palabras_frag = [p for p, _i, _f in _palabras_con_posicion(fragmento)]
    if len(palabras_frag) < PALABRAS_PARA_TOLERAR or not palabras_nota:
        return None

    solo_nota = [p for p, _i, _f in palabras_nota]
    coincidencias = SequenceMatcher(
        None, solo_nota, palabras_frag, autojunk=False).get_matching_blocks()
    utiles = [b for b in coincidencias if b.size > 0]
    if not utiles:
        return None

    cubiertas = sum(b.size for b in utiles)
    if cubiertas / len(palabras_frag) < FRACCION_PALABRAS_MINIMA:
        return None

    # El tramo se extiende hasta cubrir TODO el fragmento, no solo lo alineado:
    # tomar solo de la primera a la ultima palabra alineada dejaria fuera
    # precisamente la palabra que el modelo copio mal, que suele ser la que
    # importa. La alineacion dice donde cae cada palabra del fragmento en la
    # nota (palabra i del fragmento -> palabra a-b+i de la nota), y con eso se
    # recupera el tramo entero, incluidas sus palabras mal copiadas.
    desplazamiento = utiles[0].a - utiles[0].b
    primera = max(0, desplazamiento)
    ultima = min(len(palabras_nota) - 1, desplazamiento + len(palabras_frag) - 1)
    if ultima < primera:
        return None
    return palabras_nota[primera][1], palabras_nota[ultima][2]


def verificar(nota, fragmentos):
    """
    Localiza cada fragmento en la nota y separa los que estan de los inventados.

    Devuelve (tramos, inventados), donde cada tramo es la pareja (inicio, fin)
    de posiciones EN LA NOTA. No se devuelve el texto que dio el modelo, y esa
    es toda la diferencia: lo que salga de aqui se recorta de la nota.

    Es la unica defensa que hace aceptable un modelo pequeno sobre texto
    clinico, asi que no tiene excepciones: lo que no se localiza se descarta,
    por muy razonable que suene.
    """
    tramos, inventados = [], []
    for f in fragmentos:
        f = str(f).strip(" ,.;:-")
        if len(f.split()) < 2:
            continue
        sitio = localizar(nota, f)
        if sitio:
            tramos.append(sitio)
        else:
            inventados.append(f)
    return tramos, inventados


def _unir(nota, tramos):
    """
    Recorta de la NOTA los tramos localizados, en orden y sin solaparse.

    Se recorta de la nota y no del texto que devolvio el modelo porque el
    modelo no siempre copia letra por letra. El modelo señala DONDE esta lo
    importante; el texto lo pone la nota, asi que no puede alterar un caracter.
    """
    tramos = sorted(tramos)
    salida, ultimo = [], -1
    for inicio, fin in tramos:
        if inicio >= ultimo:
            salida.append(str(nota)[inicio:fin].strip(" ,.;:-"))
            ultimo = fin
    return ", ".join(x for x in salida if x)


# ==========================================================
# EXTRACCION
# ==========================================================

def _toca_el_motivo(nota, extraido):
    """
    True si lo extraido comparte alguna palabra con el tramo de la nota que
    puede ser motivo de consulta.

    En una nota sin apartados ese tramo es la nota entera y la condicion se
    cumple sola: solo dice que no en las notas estructuradas donde la
    extraccion vino toda de los antecedentes.
    """
    from NLP.depuracion import depuracion

    motivo = depuracion.sin_apartados_no_clinicos(nota)
    palabras = set(depuracion.con_contenido(motivo))
    if not palabras:
        return True
    return bool(set(depuracion.con_contenido(extraido)) & palabras)


def conserva_lo_clinico(referencia, extraido):
    """
    True si `extraido` conserva bastante terminologia clinica de `referencia`
    que ademas podia ser motivo de consulta.

    La referencia se filtra primero con `depuracion.sin_apartados_no_clinicos`
    para no contar como perdida un antecedente que el modelo quito bien (no es
    el motivo de hoy). Se mide en terminologia y no en palabras: quitar
    tramite acorta el texto sin perder evidencia.
    """
    from NLP.depuracion import depuracion

    motivo = depuracion.sin_apartados_no_clinicos(referencia)
    esperados = set(depuracion.terminos_clinicos(motivo))
    if not esperados:
        return True
    conservados = esperados & set(depuracion.terminos_clinicos(extraido))
    return len(conservados) / len(esperados) >= FRACCION_CLINICA_MINIMA


def extraer(nota, detalle=False, referencia=None):
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

    tramos, inventados = verificar(nota, fragmentos)
    info["inventados"] = inventados

    # Una lista vacia es una RESPUESTA (el modelo no vio motivo de consulta),
    # no un fallo; se distingue de "devolvio algo y no sobrevivio nada", que
    # si es un fallo del modelo.
    if not tramos:
        if inventados:
            info["estado"] = "todo inventado"
            return info if detalle else None
        # None, no la nota marcada: reduccion.sin_reducir() conserva el texto
        # tal cual si tampoco redujo nada (ver decisiones/2026-09-16-
        # reduccion-extractor-umbrales.md).
        info["estado"] = ESTADO_SIN_CONTEXTO
        return info if detalle else None

    # el texto sale de la nota, no del modelo (ver _unir)
    motivo = _unir(nota, tramos)
    validos = [str(nota)[i:f].strip(" ,.;:-") for i, f in sorted(tramos)]

    if len(motivo.split()) > FRACCION_MAXIMA * len(nota.split()):
        info["estado"] = "devolvio casi toda la nota: no extrajo"
        return info if detalle else None

    # el modelo puede quitar todo lo que no sea clinico, pero no puede perder
    # lo que si lo es (ver FRACCION_CLINICA_MINIMA). Este otro chequeo no
    # compara terminologia, comprueba PROCEDENCIA: si lo extraido no toca ni
    # una palabra del tramo que puede ser motivo de consulta, salio entero de
    # un apartado que no lo es (p.ej. de los antecedentes).
    if not _toca_el_motivo(nota, motivo):
        info["estado"] = "salio entero de un apartado que no es motivo de consulta"
        return info if detalle else None

    if referencia is not None and not conserva_lo_clinico(referencia, motivo):
        info["estado"] = "perdio terminologia que el recorte por reglas conservaba"
        return info if detalle else None

    info["motivo"] = motivo
    info["fragmentos"] = validos
    info["estado"] = "ok" + (f" ({len(inventados)} inventados descartados)" if inventados else "")
    _CACHE[nota] = {"motivo": motivo, "fragmentos": validos,
                    "inventados": inventados, "estado": info["estado"]}
    return info if detalle else motivo


def diagnosticar(nota, referencia=None):
    """Que hizo el modelo con una nota concreta, paso a paso."""
    return extraer(nota, detalle=True, referencia=referencia)
