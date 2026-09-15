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


# ==========================================================
# CONFIGURACION
# ==========================================================

SERVIDOR = "http://localhost:11434"
MODELO = "qwen2.5:3b-instruct"

# Longitud minima para consultar al modelo. En 1 significa que las ve TODAS.
#
# POR QUE YA NO SE FILTRA POR LONGITUD
#     El umbral estaba en 15 palabras porque por debajo el recorte por reglas
#     ya acierta y el modelo solo cuesta tiempo. Sigue siendo verdad para el
#     recorte, pero el modelo dejo de usarse solo para recortar: ahora tambien
#     DICTAMINA si la nota tiene un motivo de consulta o no, y ese dictamen es
#     lo que separa 'quedo igual porque es corta' de 'quedo igual porque no
#     habia nada que extraer'. Esa distincion hace falta en las cortas tanto
#     como en las largas.
#
#     El precio esta medido y no es pequeno: el 71% del corpus baja de 15
#     palabras, asi que mandarlas todas multiplica por algo mas de tres el
#     tiempo de esta fase (de ~4 h a ~14 h por cada 5.000 notas sobre CPU).
#     Subir este numero vuelve al comportamiento anterior y las notas por
#     debajo del umbral dejan de recibir dictamen.
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
# modelo tiene que conservar para darla por buena.
#
# POR QUE HACE FALTA UN SEGUNDO CRITERIO, DISTINTO DE LA VERIFICACION
#     La verificacion comprueba que lo devuelto ESTE en la nota. No comprueba
#     que este todo lo que deberia: un fragmento correcto pero incompleto la
#     pasa sin problema. Medido, el modelo devolvio 'sangre mucho' de una nota
#     cuyo motivo era una herida en la mano, y era texto legitimo de la nota.
#
#     Son dos preguntas distintas -- 'esto es de la nota?' y 'esto es todo?' --
#     y solo la primera se puede responder mirando el fragmento. La segunda
#     necesita algo con que comparar, y lo que hay es el recorte por reglas.
#
# LO QUE SE COMPARA ES TERMINOLOGIA, NO LONGITUD
#     Comparar por numero de palabras castigaria al modelo por hacer bien su
#     trabajo: quitar tramite ACORTA sin perder nada. Lo que no puede es perder
#     terminos clinicos, y eso se mide con el mismo lexico curado que usa la
#     depuracion.
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

    Devuelve SIEMPRE posiciones, nunca texto. Quien llama recorta de la nota,
    de modo que el modelo no puede alterar un solo caracter aunque su fragmento
    venga con otra capitalizacion, otra tilde o una palabra cambiada.

    DOS PASADAS, Y LA SEGUNDA ES LA QUE EVITA PERDER INFORMACION
        1. exacta   el fragmento aparece tal cual, en limite de palabra. El
                    limite hace falta porque sin el 'stenosis' se daba por
                    bueno dentro de 'estenosis', partiendo un termino clinico.

        2. tolerante  el fragmento no aparece igual, pero la mayoria de sus
                    palabras si estan en la nota, seguidas y en orden. Es lo que
                    ocurre cuando el modelo copia mal una palabra
                    ('estreñosis' por 'estenosis', 'e' por 'y'): el fragmento
                    apunta bien y solo la transcripcion falla. Se alinea con el
                    texto de la nota y se devuelve el tramo que abarca.

        Lo que no encaja en ninguna de las dos no esta en la nota, y eso si es
        una invencion.
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

    Se usa SequenceMatcher sobre listas de palabras y no distancia de edicion
    sobre caracteres porque lo que hay que medir es cuantas PALABRAS del
    fragmento estan de verdad en la nota. Una palabra mal copiada baja la
    fraccion en una unidad; un fragmento inventado no alinea casi nada.
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

    # EL TRAMO SE EXTIENDE HASTA CUBRIR TODO EL FRAGMENTO, NO SOLO LO ALINEADO.
    #
    # Tomar de la primera a la ultima palabra ALINEADA deja fuera precisamente
    # la palabra que el modelo copio mal, que suele ser la que importa: con
    # 'estreñosis de coledoco distal' se recuperaba 'de coledoco distal' y se
    # perdia 'estenosis', que es el termino clinico.
    #
    # La alineacion dice donde cae cada palabra del fragmento en la nota, asi
    # que la palabra i del fragmento corresponde a la palabra (a - b + i) de la
    # nota. Con eso se recupera el tramo entero que el fragmento señalaba,
    # incluidas sus palabras mal copiadas, y lo que se devuelve sigue siendo el
    # texto de la nota.
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

    POR QUE SE RECORTA DE LA NOTA Y NO SE USA LO QUE DEVOLVIO EL MODELO
        Porque el modelo no siempre copia. Medido sobre la muestra: devolvio
        'lleve aprox 10 dias' donde la nota decia 'lleva', y 'stenosis' donde
        decia 'estenosis'. Son cambios de una letra, y en una nota clinica una
        letra distingue dos farmacos o dos diagnosticos.

        El modelo señala DONDE esta lo importante; el texto lo pone la nota.
        Asi es imposible que altere un solo caracter, aunque quiera.
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
    True si `extraido` conserva bastante de la terminologia clinica que
    `referencia` traia Y QUE PODIA SER MOTIVO DE CONSULTA.

    LA REFERENCIA SE LIMPIA ANTES DE COMPARAR, Y ESO ES LO ESENCIAL
        La primera version comparaba contra el recorte por reglas tal cual, y
        castigaba al modelo por acertar. El recorte por reglas conserva los
        antecedentes -- 'trastorno de ansiedad generalizada', 'sertralina',
        'colecistectomia' --, que son terminologia clinica de pleno derecho y
        que NO son el motivo de hoy. El modelo los quitaba bien, la comparacion
        lo leia como perdida, y la nota volvia a salir con toda la historia
        clinica dentro.

        Los apartados que no son motivo de consulta ya los sabe recortar la
        depuracion, asi que la referencia se filtra con ella antes de contar.
        Lo que queda es lo unico que el modelo no tiene derecho a perder.

    Se mide en terminologia y no en palabras: quitar tramite acorta el texto sin
    perder evidencia, que es justo lo que el modelo debe hacer.
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

    # UNA LISTA VACIA ES UNA RESPUESTA, NO UN FALLO.
    #     Si el modelo leyo la nota y no encontro nada que sea motivo de
    #     consulta, eso ES la conclusion y hay que conservarla. Antes se
    #     confundia con no haber podido responder, y la nota caia al recorte por
    #     reglas como si el modelo no hubiera opinado.
    #
    #     Lo que si es un fallo es que devolviera algo y no sobreviviera nada:
    #     ahi no sabemos que penso, solo que lo que dijo no estaba en la nota.
    if not tramos:
        if inventados:
            info["estado"] = "todo inventado"
            return info if detalle else None
        # El modelo no vio nada. Se devuelve None para que el recorte por
        # reglas haga su trabajo, y es ese texto -- no la nota entera -- el que
        # dejara tal cual reduccion.sin_reducir() si tampoco redujo nada.
        #
        # Devolver aqui la nota marcada fue un error medido: el texto de
        # embedding pasaba de 128 palabras a 141, porque marcar no reduce.
        info["estado"] = ESTADO_SIN_CONTEXTO
        return info if detalle else None

    # el texto sale de la nota, no del modelo (ver _unir)
    motivo = _unir(nota, tramos)
    validos = [str(nota)[i:f].strip(" ,.;:-") for i, f in sorted(tramos)]

    if len(motivo.split()) > FRACCION_MAXIMA * len(nota.split()):
        info["estado"] = "devolvio casi toda la nota: no extrajo"
        return info if detalle else None

    # el modelo puede quitar todo lo que no sea clinico, pero no puede perder
    # lo que si lo es (ver FRACCION_CLINICA_MINIMA)
    # LA EXTRACCION NO PUEDE SALIR ENTERA DE UN APARTADO DE ANTECEDENTES.
    #
    #     'ap: hta; aa: niega; motivo de consulta me mandaron por la presion alta'
    #         -> 'hta (hipertension arterial), niega'
    #
    #     El modelo se quedo con los antecedentes y tiro el motivo. La
    #     comprobacion de terminologia no lo frena, porque el motivo de esa nota
    #     no tiene ni un termino reconocido: sin nada que comparar, aceptaba
    #     cualquier cosa.
    #
    #     Esta condicion no compara, comprueba una PROCEDENCIA: si lo extraido
    #     no toca ni una palabra del tramo que puede ser motivo de consulta,
    #     viene entero de donde no debia.
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
