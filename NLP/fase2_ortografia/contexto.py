"""
Capa de contexto: decidir si una palabra tiene sentido donde está.

EL PROBLEMA QUE NINGUNA CAPA ANTERIOR RESUELVE
    Un corrector ortográfico comprueba que la palabra EXISTA, de modo que no ve
    los casos en que lo escrito está bien escrito pero es la palabra
    equivocada:

        'se irradia ala cadera'      'ala' existe, pero era 'a la'
        'sufre cordada en mano'      'cordada' existe, pero era 'cortada'
        'malestar gral'              spaCy conoce 'gral', pero era 'general'

    Son errores de palabra real, y no hay diccionario, distancia de edición ni
    léxico que los detecte: el criterio no es si la palabra existe, sino si cabe
    en ese hueco.

CÓMO SE MIDE
    Con la probabilidad condicional de la palabra dados sus vecinos. Se tapa la
    palabra, se pregunta al modelo qué espera en ese lugar y se compara lo
    escrito con cada candidato. Es un codificador de tamaño medio que corre en
    CPU y es determinista: la misma entrada produce siempre la misma salida.

EL MODELO NO PROPONE, SOLO PUNTÚA
    Una versión anterior dejaba que el modelo propusiera la corrección, y
    proponía variantes inexistentes de términos y de principios activos, que es
    exactamente lo que el proyecto entero existe para evitar. Un modelo de
    lenguaje escribe lo que es frecuente, no lo que es correcto.

    Aquí recibe una lista cerrada de candidatos, generada a partir del léxico
    clínico y del vocabulario del hospital, y solo indica cuál encaja mejor.
    Además, la terminología con peso clínico alto se aparta antes de llegar
    hasta aquí, de modo que el modelo ni siquiera la ve.

LAS DOS CONDICIONES, Y POR QUÉ HACEN FALTA LAS DOS
    Una probabilidad baja no basta para corregir: la terminología rara es
    improbable por definición, y corregir todo lo improbable sería el mismo
    error que corregir todo lo poco frecuente. Se exigen dos cosas a la vez:

        1. lo escrito es improbable en ese hueco, y
        2. hay un candidato ortográficamente cercano bastante más probable.

    La segunda condición es la que protege a un término correcto aunque sea
    raro: es improbable, pero ninguno de sus vecinos lo supera.

COSTE
    Del orden de decenas de milisegundos por evaluación en CPU, menos si se
    agrupa por lotes. Solo se evalúan las palabras marcadas como sospechosas, y
    el resultado se guarda en caché.

Requiere transformers y torch; la primera ejecución descarga el modelo. Si no
están disponibles, el módulo se desactiva y el pipeline sigue con sus otras
defensas.
"""

import re
import threading

MODELO = "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es"

# ==========================================================
# UMBRALES
# ==========================================================

# Por debajo de esta log-probabilidad la palabra se considera sospechosa y se
# le buscan candidatos. Es un filtro de coste, no una decision: lo que decide
# es la ganancia. Se puso holgado a proposito para no perder casos.
UMBRAL_SOSPECHA = -6.0

# Cuanto tiene que superar el candidato a lo escrito para que se aplique. El
# valor esta ajustado sobre los casos conocidos de error de palabra real:
# subirlo pierde los mas ajustados, y bajarlo empieza a aceptar reescrituras de
# estilo que no son correcciones.
UMBRAL_GANANCIA = 2.0

LONGITUD_MINIMA = 3      # tokens mas cortos no se evaluan
MAX_CANDIDATOS = 8       # tope por palabra, para acotar el coste
MAX_CARACTERES = 600     # ventana alrededor del hueco que se le pasa al modelo

ACTIVO = True

_LOCK = threading.Lock()
_TOK = None
_MOD = None
_DISPONIBLE = None
_CACHE = {}

# se pone a True si la carga fallo, para no reintentarla en cada nota
_FALLO_CARGA = False

RE_ESPACIOS = re.compile(r"\s+")


# ==========================================================
# CARGA
# ==========================================================

def _cargar():
    """
    Carga el tokenizador y el modelo la primera vez y los reutiliza. Devuelve
    None, con un aviso, si faltan las librerías o el modelo no se puede obtener.
    """
    global _TOK, _MOD, _FALLO_CARGA
    if _MOD is not None:
        return _MOD

    # LA CARGA VA BAJO CANDADO, Y NO ES UNA PRECAUCION TEORICA.
    #
    # El orquestador corrige con cuatro hilos, y los cuatro llegaban aqui a la
    # vez la primera vez. Sin candado, cada uno empezaba a cargar por su cuenta
    # y el resultado eran dos fallos distintos, los dos por la misma causa:
    #
    #     cannot import name 'AutoModelForMaskedLM' from 'transformers'
    #         un hilo importaba el modulo mientras otro lo estaba importando, y
    #         veia el espacio de nombres a medio construir
    #
    #     Tensor.item() cannot be called on meta tensors
    #         un hilo empezaba a usar los pesos que otro todavia estaba
    #         materializando
    #
    # Las notas afectadas se quedaban sin corregir, y el aviso no decia que la
    # causa era la concurrencia. Con el candado, el primero que llega carga y
    # los demas esperan y reutilizan.
    with _LOCK:
        if _MOD is not None:
            return _MOD
        if _FALLO_CARGA:
            return None
        try:
            import torch
            from transformers import AutoModelForMaskedLM, AutoTokenizer
        except ImportError:
            print("Aviso: transformers/torch no disponibles; la capa de contexto queda desactivada.")
            _FALLO_CARGA = True
            return None
        try:
            tok = AutoTokenizer.from_pretrained(MODELO)
            mod = AutoModelForMaskedLM.from_pretrained(MODELO)
            mod.eval()
            torch.set_num_threads(4)
        except Exception as exc:
            print(f"Aviso: no se pudo cargar {MODELO} ({exc}); capa de contexto desactivada.")
            _FALLO_CARGA = True
            return None
        # se publican al final y ya listos: hasta esta linea, _MOD sigue siendo
        # None para cualquier otro hilo, de modo que nadie ve un modelo a medias
        _TOK, _MOD = tok, mod
    return _MOD


def disponible():
    """True si la capa está activada y el modelo se pudo cargar."""
    global _DISPONIBLE
    if _DISPONIBLE is None:
        _DISPONIBLE = ACTIVO and _cargar() is not None
    return _DISPONIBLE


def iniciar():
    """
    Carga el modelo por adelantado e informa de los umbrales en uso, para que el
    coste no recaiga sobre la primera nota del lote.
    """
    if disponible():
        print(f"  modelo de contexto: {MODELO.split('/')[-1]} "
              f"(umbral sospecha {UMBRAL_SOSPECHA}, ganancia {UMBRAL_GANANCIA})")
    return disponible()


# ==========================================================
# PROBABILIDAD DE UNA PALABRA EN SU HUECO
# ==========================================================

def _recortar(izquierda, derecha):
    """
    Recorta el contexto a una ventana alrededor del hueco. El texto lejano no
    aporta información sobre la palabra y sí multiplica el coste.
    """
    mitad = MAX_CARACTERES // 2
    return izquierda[-mitad:], derecha[:mitad]


def logprob(izquierda, palabra, derecha):
    """
    Logaritmo de la probabilidad de la palabra dado su contexto: la SUMA sobre
    sus subtokens, que es log P(palabra | contexto).

    POR QUÉ LA SUMA Y NO EL PROMEDIO, CON LA MEDICIÓN QUE LO DEMUESTRA
        Esta función promediaba, dividiendo entre el número de subtokens, con el
        argumento de que sumar favorecería a las palabras cortas. El argumento
        está invertido: la probabilidad de una secuencia es el PRODUCTO de las
        de sus partes, así que en logaritmos es la suma. Promediar no corrige un
        sesgo, lo introduce, y en la dirección más dañina.

        La razón es que cada subtoken se puntúa con los anteriores de la MISMA
        palabra ya revelados como prefijo. Predecir 'ada' después de 'mor' es
        casi seguro, y esa probabilidad alta sube la media. Cuantas más piezas
        tiene un candidato, más fácil le resulta ganar, de modo que el
        procedimiento premiaba justo lo que nunca hay que hacer: partir una
        palabra en trozos.

        Medido sobre seis casos con respuesta conocida, tres que hay que
        corregir y tres que no:

            promedio   acierta 3 de 6
            suma       acierta 6 de 6

                                        promedio        suma
            afiliados -> 'afilia dos'    +0.92         -13.77   (no tocar)
            dorada    -> 'morada'        +8.32          -0.21   (no tocar)
            hablando  -> 'bailando'      +5.54          -2.24   (no tocar)
            ala       -> 'a la'          +8.55          +6.25   (corregir)
            cordada   -> 'cortada'       +2.48          +4.96   (corregir)
            gral      -> 'general'       +7.07         +14.18   (corregir)

        Las tres correcciones legítimas siguen aplicándose y las tres
        corrupciones desaparecen, sin tocar ningún umbral.

    Para saber si una palabra es RARA en su hueco hace falta la media, no la
    suma: una palabra larga acumula logaritmos negativos por ser larga. Esa
    medida es logprob_medio(), y es la que alimenta el filtro de sospecha.

    Devuelve None si la capa no está disponible o si el texto no se puede
    preparar. El resultado se guarda en caché por contexto y palabra.
    """
    if not disponible():
        return None

    import torch

    clave = (izquierda[-80:], palabra, derecha[:80])
    if clave in _CACHE:
        return _CACHE[clave][0]

    izq, der = _recortar(izquierda, derecha)

    # TODO EL USO DEL TOKENIZADOR VA DENTRO DEL CANDADO, NO SOLO EL DEL MODELO.
    #     El tokenizador rapido de HuggingFace esta implementado en Rust y
    #     tampoco admite dos hilos a la vez: usarlo en paralelo lanza
    #     RuntimeError('Already borrowed'). Esta llamada quedaba fuera, y con
    #     cuatro hilos corrigiendo era otra fuente de notas sin corregir --
    #     distinta de la carga, y con un mensaje que no decia de que iba.
    with _LOCK:
        sub = _TOK.encode(" " + palabra.strip(), add_special_tokens=False)
        if not sub:
            return None

        total = 0.0
        for k in range(len(sub)):
            prefijo = _TOK.decode(sub[:k]).strip()
            texto = f"{izq}{prefijo}{' ' if prefijo else ''}{_TOK.mask_token} {der.strip()}"
            ids = _TOK(texto, return_tensors="pt", truncation=True, max_length=256)
            posiciones = (ids["input_ids"][0] == _TOK.mask_token_id).nonzero()
            if len(posiciones) == 0:
                return None
            with torch.no_grad():
                salida = _MOD(**ids).logits[0, posiciones[0, 0]]
            total += torch.log_softmax(salida, -1)[sub[k]].item()

    _CACHE[clave] = (total, len(sub))
    return total


def logprob_medio(izquierda, palabra, derecha):
    """
    log P(palabra | contexto) dividido entre sus subtokens.

    Mide si la palabra es rara en ese hueco, que es una pregunta distinta de
    cual de dos candidatos es mas probable. Para lo primero hay que normalizar
    -- una palabra larga acumula logaritmos negativos por ser larga -- y para
    lo segundo NO, porque la probabilidad de la secuencia es el producto de las
    de sus partes.
    """
    total = logprob(izquierda, palabra, derecha)
    if total is None:
        return None
    n = _CACHE.get((izquierda[-80:], palabra, derecha[:80]), (None, 1))[1]
    return total / max(n, 1)


def _distancia(a, b):
    """
    Distancia de edicion entre dos formas, plegando tildes y espacios.

    Se pliega porque aqui la distancia mide cuantas TECLAS separan lo escrito
    del candidato, no cuanto difieren como cadenas: 'ala' -> 'a la' es una sola
    insercion desde el punto de vista de quien escribe, y contar el espacio
    aparte la alejaria sin motivo.
    """
    a = _sin_tildes(a.lower().replace(" ", ""))
    b = _sin_tildes(b.lower().replace(" ", ""))
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1, previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def _sin_tildes(texto):
    """Pliega los acentos conservando la enye, como el resto del paquete."""
    from NLP.nucleo import morfologia
    return morfologia.sin_tildes(texto)


def _es_expansion(escrita, candidato):
    """
    True si el candidato es la forma larga de una abreviatura: contiene todas
    las letras de lo escrito, en orden, sin alargarlo mas del doble.

    EXPANDIR NO ES CORREGIR UNA ERRATA, Y POR ESO VA EN SU PROPIA TANDA
        Ordenar por distancia de edicion arreglo 'cordada' -> 'cortada' y rompio
        'gral' -> 'general':

            gral -> oral      1 edicion    <- ganaba la tanda cercana
            gral -> general   3 ediciones

        'oral' esta mas cerca de 'gral' que 'general', pero quien escribio
        'gral' no se equivoco de tecla: abrevio. Una abreviatura conserva todas
        sus letras en orden, y esa forma la distingue de una errata sin depender
        de cuantas ediciones haya de por medio.
    """
    e = _sin_tildes(escrita.lower())
    c = _sin_tildes(candidato.lower().replace(" ", ""))
    if len(c) <= len(e) or len(c) > 2 * len(e):
        return False
    it = iter(c)
    return all(letra in it for letra in e)


def es_sospechosa(izquierda, palabra, derecha):
    """
    True si lo escrito resulta improbable en ese hueco. Es un filtro de coste,
    no una decisión: marca a qué palabras vale la pena buscarles candidatos.
    """
    lp = logprob_medio(izquierda, palabra, derecha)
    return lp is not None and lp < UMBRAL_SOSPECHA


# ==========================================================
# DECISIÓN
# ==========================================================

def elegir(izquierda, escrita, derecha, candidatos):
    """
    Devuelve el par (candidato, ganancia) si alguno encaja claramente mejor que
    lo escrito, o None.

    Se descarta de entrada si lo escrito no resulta sospechoso, y al final si
    ningún candidato supera la ganancia mínima. La lista de candidatos la genera
    otro módulo a partir de fuentes declaradas: aquí no se inventa ninguno, y esa
    es la garantía de que la capa no puede introducir una palabra que nadie
    declaró.
    """
    if not disponible() or not candidatos:
        return None
    if len(escrita) < LONGITUD_MINIMA:
        return None

    # La sospecha se mide con la media (¿es rara esta palabra aqui?) y la
    # comparacion con la suma (¿cual de las dos es mas probable?). Son dos
    # preguntas distintas y mezclarlas era el origen de las corrupciones.
    medio = logprob_medio(izquierda, escrita, derecha)
    if medio is None or medio >= UMBRAL_SOSPECHA:
        return None

    base = logprob(izquierda, escrita, derecha)
    if base is None:
        return None

    # LOS CANDIDATOS SE MIRAN POR TANDAS DE DISTANCIA DE EDICION, DE MENOR A
    # MAYOR, Y SE PARA EN LA PRIMERA QUE DE UN GANADOR.
    #
    # EL CASO QUE LO OBLIGA
    #     Esta funcion elegia por probabilidad y nada mas, ignorando cuanto se
    #     parecia el candidato a lo escrito. Sobre 'paciente sufre cordada en
    #     mano derecha':
    #
    #         cortada   1 edicion    ganancia  +5.41
    #         mordida   2 ediciones  ganancia +10.49   <- ganaba
    #
    #     Y gana con razon, si solo se mira el modelo: 'sufre mordida en mano'
    #     es mas frecuente en espanol que 'sufre cortada en mano'. Las dos son
    #     lesiones plausibles de una mano, asi que el contexto no las separa.
    #
    #     Lo que si las separa es la ortografia: quien escribio 'cordada'
    #     tecleo una letra de mas o de menos, y 'cortada' esta a una edicion
    #     mientras que 'mordida' esta a dos. Una errata de una letra es mucho
    #     mas probable que una de dos, y esa evidencia no estaba entrando en la
    #     decision.
    #
    # POR QUE POR TANDAS Y NO SUMANDO UNA PENALIZACION
    #     Penalizar la distancia obligaria a elegir cuantos puntos de
    #     log-probabilidad vale una edicion, que es un numero inventado y habria
    #     que recalibrarlo con cada cambio del modelo. Por tandas no hace falta:
    #     si algo a una edicion ya convence, no se mira mas lejos. Y cuando no
    #     hay nada cerca que convenza, las tandas siguientes se evaluan igual,
    #     de modo que 'gral' -> 'general' (3 ediciones) sigue funcionando.
    candidatos = [c for c in list(candidatos)[:MAX_CANDIDATOS]
                  if c and c != escrita]
    if not candidatos:
        return None

    # Las expansiones de abreviatura van en su propia tanda, la primera: son
    # otra operacion distinta de arreglar una errata (ver _es_expansion).
    por_distancia = {}
    for candidato in candidatos:
        tanda = -1 if _es_expansion(escrita, candidato) else _distancia(escrita, candidato)
        por_distancia.setdefault(tanda, []).append(candidato)

    for distancia in sorted(por_distancia):
        mejor, mejor_lp = None, base
        for candidato in por_distancia[distancia]:
            lp = logprob(izquierda, candidato, derecha)
            if lp is not None and lp > mejor_lp:
                mejor, mejor_lp = candidato, lp
        if mejor is not None and mejor_lp - base >= UMBRAL_GANANCIA:
            return mejor, mejor_lp - base

    return None


def diagnosticar(izquierda, escrita, derecha, candidatos):
    """
    Qué ve el modelo en un hueco concreto: la probabilidad de lo escrito, si lo
    considera sospechoso, la de cada candidato y la decisión final. Herramienta
    de inspección manual.
    """
    if not disponible():
        return {"disponible": False}
    base = logprob(izquierda, escrita, derecha)
    puntajes = {c: logprob(izquierda, c, derecha) for c in candidatos}
    decision = elegir(izquierda, escrita, derecha, candidatos)
    return {
        "disponible": True,
        "escrita": escrita,
        "logprob_escrita": base,
        "sospechosa": base is not None and base < UMBRAL_SOSPECHA,
        "candidatos": puntajes,
        "decision": decision,
    }


def esperado(izquierda, derecha, k=6):
    """
    Las k palabras que el modelo espera en el hueco, con su probabilidad. Solo
    sirve para inspeccionar: el pipeline nunca corrige con estas propuestas.
    """
    if not disponible():
        return []
    import torch
    izq, der = _recortar(izquierda, derecha)
    # mismo motivo que en logprob(): el tokenizador tampoco es seguro entre hilos
    with _LOCK, torch.no_grad():
        texto = f"{izq}{_TOK.mask_token} {der.strip()}"
        ids = _TOK(texto, return_tensors="pt", truncation=True, max_length=256)
        posiciones = (ids["input_ids"][0] == _TOK.mask_token_id).nonzero()
        if len(posiciones) == 0:
            return []
        salida = _MOD(**ids).logits[0, posiciones[0, 0]]
        prob = torch.softmax(salida, -1)
        top = torch.topk(prob, k)
        return [(_TOK.decode([i]).strip(), round(v.item(), 4))
                for v, i in zip(top.values, top.indices)]
