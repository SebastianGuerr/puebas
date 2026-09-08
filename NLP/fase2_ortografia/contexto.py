"""
Capa de contexto: decidir si una palabra tiene sentido donde esta.

EL PROBLEMA QUE NINGUNA CAPA ANTERIOR PUEDE RESOLVER
    Un corrector ortografico comprueba que la palabra EXISTA. Por eso todas
    estas sobreviven al pipeline entero:

        ala      se irradia ala cadera        'ala' existe (de un ave)
        cordada  sufre cordada en mano        'cordada' existe (de alpinistas)
        regio    en regio tenar               'regio' existe (regio, real)
        gral     malestar gral                spaCy la conoce

    Estan bien escritas. Son la palabra equivocada. Se llaman errores de
    palabra real, y no hay diccionario, distancia de edicion ni lexico que los
    detecte: el criterio no es si la palabra existe sino si CABE AHI.

QUE ES 'CABER AHI', OPERATIVAMENTE
    La probabilidad condicional de la palabra dados sus vecinos. Se tapa la
    palabra, se le pregunta al modelo que espera en ese hueco, y se compara.

    Medido sobre 'se irradia ___ cadera' con
    PlanTL-GOB-ES/roberta-base-biomedical-clinical-es:

        ala    log P = -9.91        a la   log P = -0.25

    Nueve unidades logaritmicas de diferencia. La senal no es sutil.

POR QUE ESTO NO ES 'METERLE UN LLM'
    Es un encoder de 126M parametros que corre en CPU, es determinista (misma
    entrada, misma salida, siempre) y no genera texto: solo puntua candidatos
    que le pasa otro modulo. Todo cambio que produce queda registrado con su
    ganancia numerica, asi que la auditoria del proyecto sigue funcionando.

EL ERROR DE DISENO QUE LA MEDICION ATRAPO, Y QUE DEFINE ESTE ARCHIVO
    La primera version dejaba que el modelo PROPUSIERA la correccion. Medido:

        epistaxis -> epistasis   +1.955   sangrado nasal -> interaccion genica
        midazolam -> midazolan   +6.005   corrompe un farmaco

    Exactamente el desastre que el proyecto entero existe para evitar. Un
    modelo de lenguaje propone lo que es frecuente, no lo que es correcto.

    Por eso aqui el modelo NO propone. Recibe una lista cerrada de candidatos
    -- del lexico clinico y del vocabulario del hospital -- y solo dice cual
    encaja mejor. Y ni siquiera llega a ver la terminologia: pesos.py la aparta
    antes. Sobre esos mismos cuatro casos, con el enmascarado delante:

        epistaxis  peso 0.95  apartada, el modelo nunca la ve
        midazolam  peso 0.95  apartada
        disnea     peso 0.95  apartada
        tenar      peso 0.95  apartada  (del CIE-10)

    Las dos corrupciones pasan de improbables a imposibles.

LAS DOS CONDICIONES, Y POR QUE HACEN FALTA LAS DOS
    Una probabilidad baja NO basta para corregir. La terminologia rara es
    improbable por definicion: 'fazekas', 'stemi' y 'midazolam' tienen
    probabilidad bajisima y son correctos. Corregir todo lo improbable seria
    el mismo error que corregir todo lo poco frecuente, que ya costo caro.

    Se exigen las dos cosas:
        1. lo escrito es improbable en ese hueco, Y
        2. existe un candidato ortograficamente cercano MUCHO mas probable.

    La segunda salva a 'midazolam' aunque no estuviera protegido: es
    improbable, pero ningun vecino suyo lo supera.

COSTE MEDIDO
    60 ms por evaluacion suelta, 32 ms por lotes de 16, en CPU con 4 hilos.
    Sobre las 92.597 notas, suponiendo que un 10% traiga sospechosos, son unos
    111.000 pases: cerca de una hora, una sola vez, y cacheable.

INSTALACION
    pip install transformers torch
    La primera ejecucion baja el modelo (~500 MB). Despues es local.

Si transformers no esta o el modelo no se puede cargar, el modulo se desactiva
solo y el pipeline sigue con el resto de sus defensas.
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

# Cuanto tiene que superar el candidato a lo escrito para aplicarse. Medido
# sobre los cuatro casos conocidos, todos ganan por mas de 2:
#     ala -> a la      +9.65        regio -> región   +4.73
#     gral -> general  +7.33        cordada -> cortada +2.50
# Subirlo pierde 'cordada'; bajarlo empieza a aceptar reescrituras de estilo.
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

RE_ESPACIOS = re.compile(r"\s+")


# ==========================================================
# CARGA
# ==========================================================

def _cargar():
    global _TOK, _MOD
    if _MOD is not None:
        return _MOD
    try:
        import torch
        from transformers import AutoModelForMaskedLM, AutoTokenizer
    except ModuleNotFoundError:
        print("Aviso: transformers/torch no instalados; la capa de contexto queda desactivada.")
        return None
    try:
        _TOK = AutoTokenizer.from_pretrained(MODELO)
        _MOD = AutoModelForMaskedLM.from_pretrained(MODELO)
        _MOD.eval()
        torch.set_num_threads(4)
    except Exception as exc:
        print(f"Aviso: no se pudo cargar {MODELO} ({exc}); capa de contexto desactivada.")
        return None
    return _MOD


def disponible():
    global _DISPONIBLE
    if _DISPONIBLE is None:
        _DISPONIBLE = ACTIVO and _cargar() is not None
    return _DISPONIBLE


def iniciar():
    """Carga el modelo por adelantado, para que no cueste en mitad del lote."""
    if disponible():
        print(f"  modelo de contexto: {MODELO.split('/')[-1]} "
              f"(umbral sospecha {UMBRAL_SOSPECHA}, ganancia {UMBRAL_GANANCIA})")
    return disponible()


# ==========================================================
# PROBABILIDAD EN EL HUECO
# ==========================================================

def _recortar(izquierda, derecha):
    """Ventana alrededor del hueco. Una nota de 400 palabras no aporta mas."""
    mitad = MAX_CARACTERES // 2
    return izquierda[-mitad:], derecha[:mitad]


def logprob(izquierda, palabra, derecha):
    """
    log P(palabra | contexto), promediado si la palabra son varios subtokens.

    Se evalua en la MISMA posicion para todos los candidatos, que es lo que los
    hace comparables. La primera version puntuaba la frase entera y eso
    introducia un sesgo de longitud: 'gral' ganaba a 'general' por ser un solo
    token, aunque al taparlo el modelo predecia 'general' con 96,8%.
    """
    if not disponible():
        return None

    import torch

    clave = (izquierda[-80:], palabra, derecha[:80])
    if clave in _CACHE:
        return _CACHE[clave]

    izq, der = _recortar(izquierda, derecha)
    sub = _TOK.encode(" " + palabra.strip(), add_special_tokens=False)
    if not sub:
        return None

    total = 0.0
    with _LOCK:
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

    resultado = total / len(sub)
    _CACHE[clave] = resultado
    return resultado


def es_sospechosa(izquierda, palabra, derecha):
    """True si lo escrito es improbable en ese hueco."""
    lp = logprob(izquierda, palabra, derecha)
    return lp is not None and lp < UMBRAL_SOSPECHA


# ==========================================================
# DECISION
# ==========================================================

def elegir(izquierda, escrita, derecha, candidatos):
    """
    Devuelve (candidato, ganancia) si alguno encaja claramente mejor que lo
    escrito, o None.

    candidatos los genera OTRO modulo: el lexico clinico y el vocabulario del
    hospital. Este archivo no inventa ninguno, y esa es la garantia de que no
    puede introducir una palabra que nadie declaro.
    """
    if not disponible() or not candidatos:
        return None
    if len(escrita) < LONGITUD_MINIMA:
        return None

    base = logprob(izquierda, escrita, derecha)
    if base is None or base >= UMBRAL_SOSPECHA:
        return None

    mejor, mejor_lp = None, base
    for candidato in list(candidatos)[:MAX_CANDIDATOS]:
        if not candidato or candidato == escrita:
            continue
        lp = logprob(izquierda, candidato, derecha)
        if lp is not None and lp > mejor_lp:
            mejor, mejor_lp = candidato, lp

    if mejor is None:
        return None

    ganancia = mejor_lp - base
    if ganancia < UMBRAL_GANANCIA:
        return None
    return mejor, ganancia


def diagnosticar(izquierda, escrita, derecha, candidatos):
    """Que ve el modelo en un hueco concreto. Para revisar casos puntuales."""
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
    """Que palabras espera el modelo en el hueco. Solo para inspeccionar."""
    if not disponible():
        return []
    import torch
    izq, der = _recortar(izquierda, derecha)
    texto = f"{izq}{_TOK.mask_token} {der.strip()}"
    ids = _TOK(texto, return_tensors="pt", truncation=True, max_length=256)
    posiciones = (ids["input_ids"][0] == _TOK.mask_token_id).nonzero()
    if len(posiciones) == 0:
        return []
    with _LOCK, torch.no_grad():
        salida = _MOD(**ids).logits[0, posiciones[0, 0]]
    prob = torch.softmax(salida, -1)
    top = torch.topk(prob, k)
    return [(_TOK.decode([i]).strip(), round(v.item(), 4))
            for v, i in zip(top.values, top.indices)]
