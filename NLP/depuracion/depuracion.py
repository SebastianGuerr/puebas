"""
Depuracion: separa (no elimina) las notas sin contenido clinico del corpus,
comparando por raiz contra el lexico curado.

Documentacion: NLP/docs/FLUJO.md §6 y
NLP/docs/decisiones/2026-09-16-depuracion-indice-clinico.md.
"""

import json
import re

from NLP import rutas
from NLP.nucleo import morfologia
from NLP.recursos import lexico

# ==========================================================
# QUE CUENTA COMO TERMINO CLINICO
# ==========================================================

# Solo las fuentes curadas del lexico; el vocabulario del modelo biomedico
# queda fuera (contiene el espanol corriente entero). Misma decision que
# embedding/recorte.py.
FUENTES_CURADAS = (lexico.DICCIONARIO, lexico.CATALOGO, lexico.EXTERNO)

RE_PALABRA = re.compile(r"[^\W\d_]+", re.UNICODE)

# Palabras que no son contenido. Solo deciden si lo que queda vale la pena;
# nunca se borran del texto.
VACIAS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas", "y",
    "o", "a", "al", "en", "con", "sin", "por", "para", "que", "se", "su",
    "sus", "lo", "le", "les", "es", "esta", "este", "esto", "muy", "mas",
    "ni", "pero", "ya", "aun", "aca", "alla", "ahi", "hoy", "ayer", "manana",
    "paciente", "usuario", "usuaria", "senor", "senora", "ahora", "momento",
    "cual", "quien", "ademas", "tipo", "toda", "todo", "ser", "han", "ha",
    "he", "hace", "desde", "hasta", "sobre", "entre", "cuando", "donde",
    "refiere", "manifiesta", "presenta", "indica", "comenta", "dice",
}

# Lo que queda de una plantilla contestada en blanco. Si al quitar los
# encabezados la nota solo tiene esto, es un formulario sin las preguntas.
RESPUESTAS_VACIAS = {
    "niega", "niegan", "ninguno", "ninguna", "nada", "nono", "no",
    "negativo", "negativa", "normal", "normales", "asintomatico",
    "asintomatica", "aplica", "sano", "sana", "bien", "estable",
}

# ==========================================================
# LISTAS CERRADAS QUE EL LEXICO NO PUEDE DAR
# ==========================================================
# Coincidir con el lexico no basta como evidencia clinica: ver
# NLP/docs/FLUJO.md §6 ("por que hay listas cerradas ademas del lexico").

# Palabras del recorrido por el sistema. No son motivo de consulta aunque el
# CIE-10 las contenga.
PALABRAS_TRAMITE = {
    "cita", "citada", "citado", "citaron", "citar", "prioritaria",
    "prioritario", "reconsulta", "remision", "remitieron", "remitida",
    "remitido", "remiten", "remite", "remitir", "derivada", "derivado",
    "derivaron", "derivan", "deriva", "enviada", "enviado", "enviaron",
    "envian", "envio", "mandaron", "mandan", "eps", "ips", "hospitalizar",
    "hospitalizacion", "urgencia", "urgencias", "consulta", "externa",
    "control", "valoracion", "orden", "ordenada", "ordenado", "autorizacion",
    "formula", "incapacidad", "certificado", "emi", "ger", "ambulancia",
    "camilla", "traslado", "trasladada", "trasladado", "vital", "vitales",
    "servicio", "atencion", "nivel", "afiliada", "afiliado", "venir",
    "viniera", "vengo", "vine", "dijeron", "acompanante", "trae", "traida",
    "traido", "reingreso", "reemitieron", "reemitidos", "devolvieron",
    "aceptada", "aceptado", "aceptados",
}

# Regiones anatomicas. Nombrar una parte del cuerpo no dice a que vino nadie;
# solo descartan cuando son lo UNICO clinico de la nota.
PALABRAS_ANATOMIA = {
    "cabeza", "cara", "frente", "ojo", "ojos", "oido", "oidos", "oreja",
    "nariz", "boca", "diente", "dientes", "muela", "lengua", "garganta",
    "cuello", "nuca", "hombro", "hombros", "brazo", "brazos", "codo",
    "antebrazo", "muneca", "mano", "manos", "dedo", "dedos", "pecho",
    "torax", "espalda", "columna", "cintura", "abdomen", "barriga",
    "estomago", "ombligo", "cadera", "pelvis", "pierna", "piernas", "muslo",
    "rodilla", "rodillas", "pantorrilla", "tobillo", "pie", "pies", "talon",
    "gluteo", "gluteos", "costado", "costilla", "costillas", "axila",
    "ingle", "genitales", "seno", "senos", "piel", "cuerpo", "extremidad",
    "extremidades", "miembro", "miembros", "hueso", "huesos", "musculo",
}

# Palabras de tiempo. CUANDO ocurrio algo no es POR QUE vino el paciente, y el
# tiempo de evolucion ya viaja como dato estructurado. Ver FLUJO.md §6 para el
# ejemplo que motiva esta tercera lista.
PALABRAS_TIEMPO = {
    "dia", "dias", "semana", "semanas", "mes", "meses", "ano", "anos",
    "hora", "horas", "minuto", "minutos", "rato", "noche", "noches",
    "madrugada", "tarde", "manana", "anoche", "antier", "antenoche",
    "lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo",
    "enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
    "septiembre", "setiembre", "octubre", "noviembre", "diciembre",
    "pasado", "pasada", "pasados", "pasadas", "reciente", "recientemente",
    "actual", "actualmente", "previo", "previa", "anterior", "ultimo",
    "ultima", "fin", "principios", "mediados", "finales", "hace", "desde",
    "aproximadamente", "aprox",
}

# Numero minimo de palabras con contenido para conservar una nota que no tiene
# terminologia reconocida. Es la valvula de escape del criterio: una nota larga
# escrita en lenguaje corriente puede no contener ni un termino del lexico y ser
# un motivo de consulta perfectamente legible. El corte esta alto a proposito,
# porque por debajo caen los fragmentos sueltos, que es lo que se descarta.
PALABRAS_PARA_SALVAR = 8


def _plegar(palabra):
    """Misma clave de comparacion que usa el lexico: minusculas y sin tildes."""
    return morfologia.sin_tildes(str(palabra).lower().strip())


# Encabezado del formulario, con la expansion que le pone la fase 3:
# 'ap:', 'mc (motivo de consulta):'. Se quita ANTES de juzgar la nota: la
# expansion del rotulo ('antecedentes', 'alergicos'...) es terminologia
# clinica valida y falsearia el juicio si no se quitara antes. Medicion en
# decisiones/2026-09-16-depuracion-indice-clinico.md.
RE_ENCABEZADO = re.compile(
    r"\b[a-z]{2,6}\s*(?:\([^)]{3,60}\))?\s*:", re.IGNORECASE)


def sin_encabezados(texto):
    """La nota sin los rotulos del formulario ni su expansion."""
    return RE_ENCABEZADO.sub(" ", str(texto))


# ==========================================================
# LOS APARTADOS QUE NO SON MOTIVO DE CONSULTA
# ==========================================================
# Quitar el rotulo no basta: hay que quitar tambien lo que contiene (ver
# NLP/docs/FLUJO.md §6). La lista de apartados la declara nucleo/clinico.py
# (la misma que usa para acotar el alcance de la negacion).

def _tabla_apartados():
    """Formas escritas de cada apartado y si es o no motivo de consulta.
    Devuelve {forma plegada: es_no_clinico}."""
    # se importa la tabla, no el pipeline: no carga spaCy ni medspaCy
    from NLP.nucleo import clinico

    tabla = {}
    for categoria, escrituras in clinico.SECCIONES.items():
        no_clinico = categoria in clinico.SECCIONES_NO_CLINICAS
        for escritura in escrituras:
            tabla[_plegar(escritura)] = no_clinico
    return tabla


_APARTADOS = None
_RE_APARTADO = None

# Longitud a partir de la cual un rotulo se reconoce SIN los dos puntos (el
# ultimo apartado de una nota a veces no los lleva). Por debajo de esta
# longitud se exigen los dos puntos, para no cortar dentro de una palabra
# corriente. Medicion en decisiones/2026-09-16-depuracion-indice-clinico.md.
LONGITUD_ROTULO_SIN_DOSPUNTOS = 8


def _re_apartado():
    """Patron que reconoce el arranque de cualquier apartado declarado,
    ordenado de mas largo a mas corto para que gane la forma mas especifica."""
    global _APARTADOS, _RE_APARTADO
    if _RE_APARTADO is not None:
        return _RE_APARTADO

    _APARTADOS = _tabla_apartados()
    largos, cortos = [], []
    for forma in sorted(_APARTADOS, key=len, reverse=True):
        (largos if len(forma) >= LONGITUD_ROTULO_SIN_DOSPUNTOS else cortos).append(
            re.escape(forma))

    # el rotulo puede traer la expansion entre parentesis que le pone la fase 3
    expansion = r"\s*(?:\([^)]{3,60}\))?\s*"
    alternativas = []
    if largos:
        alternativas.append(r"(?P<largo>%s)%s:?" % ("|".join(largos), expansion))
    if cortos:
        alternativas.append(r"(?P<corto>%s)%s:" % ("|".join(cortos), expansion))

    _RE_APARTADO = re.compile(r"\b(?:%s)" % "|".join(alternativas), re.IGNORECASE)
    return _RE_APARTADO


def sin_apartados_no_clinicos(texto):
    """La nota sin los apartados no clinicos (antecedentes, alergicos,
    familiares, quirurgicos, toxicos, medicamentos, ocupacion, fuente).
    Lo anterior al primer rotulo se conserva siempre."""
    patron = _re_apartado()
    texto = str(texto)

    marcas = []
    for m in patron.finditer(texto):
        rotulo = m.group("largo") or m.group("corto")
        marcas.append((m.start(), m.end(), _plegar(rotulo)))
    if not marcas:
        return texto

    partes = [texto[:marcas[0][0]]]
    for i, (_ini, fin, rotulo) in enumerate(marcas):
        siguiente = marcas[i + 1][0] if i + 1 < len(marcas) else len(texto)
        if not _APARTADOS.get(rotulo, False):
            partes.append(texto[fin:siguiente])
    return " ".join(partes)


def con_contenido(texto):
    """Palabras del texto que aportan significado, ya plegadas y sin las
    vacias ni las muy cortas. Es la base de todas las decisiones del modulo."""
    return [p for p in (_plegar(w) for w in RE_PALABRA.findall(sin_encabezados(texto)))
            if p not in VACIAS and len(p) >= 3]


# ==========================================================
# EL INDICE DE EVIDENCIA CLINICA
# ==========================================================
# Se indexa la RAIZ morfologica de cada termino curado (mismo stemmer que
# embedding/extraccion.py), no la forma exacta: comparar por igualdad contra
# el lexico deja fuera formas verbales y plurales legitimos. Las raices de
# tramite y de anatomia se restan del indice al construirlo, no al
# consultarlo, porque una raiz truncada puede ser ambigua entre las dos
# poblaciones (p. ej. 'consulta'/'consultar'). Medicion y opciones
# consideradas en decisiones/2026-09-16-depuracion-indice-clinico.md.

LONGITUD_MINIMA_RAIZ = 3   # por debajo, truncar deja de discriminar

_RAICES = None       # raices de los terminos curados, ya restado lo ambiguo
_FRASES = None       # variantes del catalogo de varias palabras
_STEMMER = None


def _stem(palabra):
    """Raiz morfologica, o la palabra tal cual si nltk no esta instalado."""
    return _STEMMER.stem(palabra) if _STEMMER is not None else palabra


def _del_catalogo():
    """Variantes del catalogo de sintomas (sin el minimo de cuatro letras que
    aplica el lexico). Devuelve (palabras sueltas, expresiones de varias
    palabras)."""
    ruta = rutas.CATALOGO_SINTOMAS
    if not ruta.exists():
        return set(), set()

    catalogo = json.loads(ruta.read_text(encoding="utf-8"))
    sueltas, frases = set(), set()
    for concepto, datos in catalogo.get("sintomas", {}).items():
        variantes = datos.get("variantes", ()) if isinstance(datos, dict) else ()
        for forma in [concepto, *variantes]:
            plano = _plegar(forma)
            (frases if " " in plano else sueltas).add(plano)
    return sueltas, frases


def _lugares():
    """Municipios declarados en el grupo 'geografia' del diccionario de
    siglas; mismo sitio que lee NLP/reduccion, para ampliar una sola vez."""
    ruta = rutas.DICCIONARIO_SIGLAS
    if not ruta.exists():
        return set()
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    return {_plegar(x) for x in datos.get("geografia", {})}


def cargar():
    """Construye el indice de evidencia clinica y devuelve cuantas raices
    quedaron. Idempotente y perezoso (lo llama la primera consulta)."""
    global _RAICES, _FRASES, _STEMMER
    if _RAICES is not None:
        return len(_RAICES)

    try:
        from nltk.stem import SnowballStemmer
        _STEMMER = SnowballStemmer("spanish")
    except ModuleNotFoundError:
        # sin nltk se compara por igualdad: peor cobertura, no incorrecto
        print("Aviso: nltk no instalado; la depuracion no cubrira formas verbales.")
        _STEMMER = None

    sueltas, _FRASES = _del_catalogo()

    # terminos del lexico curado: el CIE-10 y el diccionario del proyecto
    if lexico.disponible():
        for termino in lexico.terminos():
            if " " not in termino and lexico.fuente(termino) in FUENTES_CURADAS:
                sueltas.add(termino)

    # lo que no es evidencia clinica se resta ANTES de indexar: toponimos
    # (misma lista que usa la reduccion) y palabras de la fuente NO_CLINICO
    # del lexico (municipios, instituciones, vocabulario administrativo). Se
    # restan por STEM y no filtrando por fuente al recorrer el lexico, porque
    # otra palabra clinica puede compartir la misma raiz no clinica.
    no_clinicas = set()
    if lexico.disponible():
        no_clinicas = {t for t in lexico.terminos()
                       if lexico.fuente(t) == lexico.NO_CLINICO}

    excluidas = {_stem(p) for p in
                 PALABRAS_TRAMITE | PALABRAS_ANATOMIA | PALABRAS_TIEMPO
                 | VACIAS | _lugares() | no_clinicas}
    _RAICES = {r for r in (_stem(p) for p in sueltas)
               if len(r) >= LONGITUD_MINIMA_RAIZ and r not in excluidas}
    return len(_RAICES)


def es_clinica(palabra):
    """True si la palabra es evidencia de contenido clinico (comparada por
    raiz, no por igualdad, contra el indice de `cargar()`)."""
    clave = _plegar(palabra)
    if (clave in PALABRAS_TRAMITE or clave in PALABRAS_ANATOMIA
            or clave in PALABRAS_TIEMPO):
        return False
    cargar()
    return _stem(clave) in _RAICES


def frases_clinicas(texto):
    """Expresiones del catalogo de varias palabras presentes en la nota,
    buscadas enteras (su contenido clinico no esta en cada palabra suelta)."""
    cargar()
    plano = " ".join(_plegar(w) for w in RE_PALABRA.findall(sin_encabezados(texto)))
    return [f for f in _FRASES if f in plano]


def terminos_clinicos(texto):
    """Palabras de la nota que son terminologia clinica curada y ademas
    aportan contenido: ni tramite ni region anatomica suelta."""
    return [p for p in con_contenido(texto) if es_clinica(p)]


def solo_tramite(texto):
    """True si la nota no tiene mas que tramite y nombres propios: hay al
    menos una palabra de tramite y ninguna palabra clinica reconocida."""
    palabras = con_contenido(texto)
    if not palabras:
        return False
    if not any(p in PALABRAS_TRAMITE for p in palabras):
        return False
    return not any(es_clinica(p) for p in palabras)


# ==========================================================
# EL VEREDICTO
# ==========================================================

# Motivos de descarte, en el orden en que se comprueban.
VACIA = "vacia"
PLANTILLA = "plantilla en blanco"
ANTECEDENTES = "solo antecedentes"
TRAMITE = "tramite administrativo"
SIN_TERMINOLOGIA = "sin terminologia clinica"
UTIL = ""


def evaluar(texto, sintomas=None):
    """Decide si una nota aporta informacion clinica. Devuelve (util, motivo),
    con motivo = "" si se conserva; si no, uno de los motivos declarados
    arriba. Ver NLP/docs/FLUJO.md §6 para el orden de las comprobaciones."""
    if sintomas:
        # un sintoma ya reconocido (fase 4/5) basta para conservar la nota
        # sin mirar nada mas; parametro opcional, no lo usan las fases 1-3
        return True, UTIL

    palabras = con_contenido(texto)
    if not palabras:
        return False, VACIA

    if all(p in RESPUESTAS_VACIAS for p in palabras):
        return False, PLANTILLA

    # A PARTIR DE AQUI SE JUZGA SOLO EL TRAMO QUE PUEDE SER MOTIVO DE CONSULTA.
    #
    # Los antecedentes son terminologia clinica de verdad y aun asi no dicen a
    # que vino nadie. 'ap: hta; aa: niega' informa de que el paciente es
    # hipertenso, no de por que consulto hoy ni de por que se descompenso. Para
    # agrupar motivos de consulta eso es ruido, y ademas ruido convincente: pasa
    # cualquier filtro que solo pregunte si hay terminologia.
    motivo = sin_apartados_no_clinicos(texto)
    palabras = con_contenido(motivo)
    if not palabras:
        return False, ANTECEDENTES
    if all(p in RESPUESTAS_VACIAS for p in palabras):
        return False, PLANTILLA

    # El tramite puro se comprueba ANTES que la terminologia, y ese orden
    # importa: hay frases administrativas cuyas palabras estan todas en el
    # lexico, de modo que preguntando primero por terminologia se conservarian.
    if solo_tramite(motivo):
        return False, TRAMITE

    # La frase entera se comprueba ademas de las palabras sueltas: 'me falta el
    # aire' es disnea y ninguna de sus tres palabras lo es por separado.
    if terminos_clinicos(motivo) or frases_clinicas(motivo):
        return True, UTIL

    # La nota no tiene terminologia con contenido, pero antes de descartarla se
    # le da una ultima oportunidad: si es larga se conserva, porque el lenguaje
    # de paciente que el lexico no cubre sigue siendo un motivo de consulta.
    if len(palabras) >= PALABRAS_PARA_SALVAR:
        return True, UTIL

    # corta, sin terminologia y encima mencionando tramite: se descarta con ese
    # motivo, que al auditar dice mas que 'sin terminologia'
    if any(p in PALABRAS_TRAMITE for p in palabras):
        return False, TRAMITE

    return False, SIN_TERMINOLOGIA


def resumen(motivos):
    """Cuenta los motivos de descarte de una corrida y los devuelve ordenados
    de mas a menos frecuente. Las notas conservadas (motivo vacio) no cuentan."""
    conteo = {}
    for motivo in motivos:
        if motivo:
            conteo[motivo] = conteo.get(motivo, 0) + 1
    return sorted(conteo.items(), key=lambda x: -x[1])


def diagnosticar(texto):
    """Por que una nota concreta se conserva o se descarta: el veredicto, el
    motivo y las senales en las que se apoya. Herramienta de inspeccion manual."""
    util_, motivo = evaluar(texto)
    return {
        "texto": texto,
        "util": util_,
        "motivo": motivo or "se conserva",
        "palabras_con_contenido": con_contenido(texto),
        "motivo_de_consulta": sin_apartados_no_clinicos(texto),
        "terminos_clinicos": terminos_clinicos(texto),
        "frases_clinicas": frases_clinicas(texto),
        "menciona_tramite": any(p in PALABRAS_TRAMITE for p in con_contenido(texto)),
    }
