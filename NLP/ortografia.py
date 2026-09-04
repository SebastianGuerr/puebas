"""
Fase 2. Correccion ortografica de notas de triage.

Este modulo solo orquesta. La logica vive en:
    reglas.py        que no se toca (siglas, numeros, entidades, forma)
    candidatos.py    cual de las sugerencias se aplica
    vocabulario.py   SymSpell, para los typos que LanguageTool no propone
    linguistica.py   spaCy, vocabulario amplio y entidades nombradas
    lt_compat.py     diferencias de API entre versiones de LanguageTool

CADENA
    correcciones directas -> LanguageTool (categoria TYPOS) -> SymSpell

PRINCIPIO
    La asimetria del error no es simetrica. Dejar 'dias' sin tilde le cuesta
    poco al modelo de la fase siguiente; convertir 'midazolam' en 'madapolan' o
    'Pereira' en 'perdida' le inyecta un dato falso. Ante la duda, no se corrige.
"""

import re

import language_tool_python

import candidatos
import casing
import linguistica
import lt_compat
import reglas
import vocabulario
from limpieza import tokenizar

CATEGORIAS_PERMITIDAS = {"TYPOS"}
USAR_VOCABULARIO = True
RESTAURAR_MAYUSCULAS = True

_LT = None


# ==========================================================
# CARGA
# ==========================================================

def cargar_siglas(ruta=reglas.RUTA_SIGLAS):
    return reglas.cargar(ruta)


def construir_lexico(textos):
    """Frecuencias del corpus y diccionario de SymSpell, del mismo material."""
    textos = list(textos)
    candidatos.construir_lexico(textos)

    if USAR_VOCABULARIO:
        entradas = vocabulario.construir(textos)
        if entradas:
            print(f"  diccionario SymSpell: {entradas:,} formas validas")

    return candidatos.CONTEO


def iniciar_languagetool(idioma="es"):
    global _LT
    if _LT is None:
        _LT = language_tool_python.LanguageTool(idioma)
        print(f"  LanguageTool: {lt_compat.verificar(_LT)}")
    return _LT


# ==========================================================
# CORRECCION
# ==========================================================

def aplicar_directas(texto):
    return reglas.RE_PALABRA.sub(
        lambda m: reglas.DIRECTAS.get(m.group(0), m.group(0)), texto
    )


DOMINANCIA_PARA_ESCRIBIR = 0.85


def restaurar_mayusculas(texto, texto_original=None):
    """
    Devuelve las siglas clinicas a mayuscula: hta -> HTA, ekg -> EKG.

    TRES FUENTES DE EVIDENCIA, EN ESTE ORDEN
      1. la nota misma. Si el token venia en mayusculas en el original y la
         nota no esta gritada, ese es el dato mas fuerte que existe: lo
         escribio quien atendio a ESE paciente. Es lo que faltaba para que
         'DM no IR' conservara la sigla, porque 'ir' esta en
         no_restaurar_mayuscula y el diccionario nunca la iba a devolver.
      2. el corpus. En notas gritadas la fuente 1 no dice nada, asi que se
         usan las siglas aprendidas por casing.py, y solo las que aparecen en
         mayuscula casi siempre: convertir todos los 'puede ir al bano' en
         'puede IR al bano' seria peor que no restaurar nada.
      3. el diccionario, como estaba.

    'pereira' se protege de la correccion pero no se convierte en 'PEREIRA':
    esta funcion solo escribe siglas.

    DOS ERRORES QUE ESTA FUNCION YA COMETIO
      aplicar la fuente 1 en bloque. Si el token venia en mayuscula en ALGUNA
          parte de la nota, se ponia en mayuscula en TODAS. Sobre 'hta dm ir
          higado graso; puede ir al bano' producia 'puede IR al bano'. Por eso
          la evidencia se lee por ocurrencia, alineando los dos textos.
      confundir enfasis con sigla. En 'HIGADO GRASO' las mayusculas son enfasis
          del que escribe, no una sigla, y la nota terminaba con 'HIGADO GRASO'
          en medio de un texto normalizado. Por eso ademas de venir en
          mayuscula, el token tiene que ser una sigla conocida: del diccionario
          o aprendida del corpus.
    """
    # Del lexico aprendido solo cuentan las que NO son palabra del espanol. En
    # las notas se escriben en mayuscula listas enteras de antecedentes
    # ('HIGADO GRASO'), asi que casing.py aprende 'higado' como sigla: es
    # enfasis del que escribe, no una abreviatura. Lo que separa a una sigla de
    # una palabra enfatizada es justamente que la sigla no existe como palabra.
    # El diccionario escrito a mano si entra completo: ahi cada entrada es una
    # decision deliberada.
    aprendidas = {t for t in casing.siglas()
                  if not reglas.es_palabra_conocida(t)} if casing.disponible() else set()
    conocidas = reglas.SIGLAS | aprendidas

    mayusculas_por_ocurrencia = _mayusculas_alineadas(texto, texto_original, conocidas)

    del_corpus = set()
    if texto_original and reglas.texto_gritado(texto_original) and casing.disponible():
        del_corpus = casing.siglas(DOMINANCIA_PARA_ESCRIBIR)

    posicion = [0]

    def _sub(m):
        palabra = m.group(0)
        indice = posicion[0]
        posicion[0] += 1

        if indice in mayusculas_por_ocurrencia:
            return palabra.upper()
        if palabra in del_corpus:
            return palabra.upper()
        if palabra in reglas.NO_RESTAURAR or palabra not in reglas.SIGLAS:
            return palabra
        return palabra.upper()

    return reglas.RE_PALABRA.sub(_sub, texto)


def _mayusculas_alineadas(texto, texto_original, conocidas):
    """
    Indices de los tokens de 'texto' que en la nota original venian en
    mayuscula Y son siglas conocidas.

    Los dos textos no son identicos (la correccion cambia palabras y la
    limpieza borra tokens), asi que se alinean con SequenceMatcher sobre la
    version en minusculas y se copia la decision solo donde hay correspondencia.
    """
    if not texto_original or reglas.texto_gritado(texto_original):
        return set()

    from difflib import SequenceMatcher

    destino = reglas.RE_PALABRA.findall(texto)
    crudos = re.findall(r"[^\W\d_]+", str(texto_original), re.UNICODE)
    origen = [p.lower() for p in crudos]

    salida = set()
    for etiqueta, i1, i2, j1, j2 in SequenceMatcher(
            None, origen, destino, autojunk=False).get_opcodes():
        if etiqueta not in ("equal", "replace"):
            continue
        for desplazamiento in range(min(i2 - i1, j2 - j1)):
            palabra_original = crudos[i1 + desplazamiento]
            if palabra_original.isupper() and origen[i1 + desplazamiento] in conocidas:
                salida.add(j1 + desplazamiento)
    return salida


def corregir(texto, texto_original=None):
    """
    texto: salida de limpieza.limpiar()
    texto_original: la nota sin limpiar. Aporta las mayusculas, unica pista de
                    que 'Pereira' o 'Hakim' no son errores de digitacion.
    """
    if not texto:
        return texto

    # En el 87,7% de las notas el original esta integramente en mayusculas, y
    # ahi detectar_protegidos() y el NER no tienen contraste que leer: devolvian
    # cero tokens protegidos. casing.restaurar() les devuelve la capitalizacion
    # que el propio corpus dice que corresponde, y con eso las dos defensas
    # vuelven a funcionar. Sobre una nota que ya venia con mayusculas y
    # minusculas no toca nada, asi que este paso nunca degrada el caso bueno.
    referencia = casing.restaurar(texto_original) if texto_original else texto_original

    protegidos = reglas.detectar_protegidos(referencia)
    protegidos = protegidos | reglas.entidades(texto, referencia)
    protegidos = protegidos | reglas.tokens_protegidos_por_contexto(texto)

    texto = aplicar_directas(texto)

    lt = iniciar_languagetool()
    try:
        matches = lt.check(texto)
    except Exception:
        matches = []

    # tokens que LanguageTool marco: son los unicos que SymSpell puede tocar
    senalados = set()

    # de derecha a izquierda: asi los offsets pendientes siguen siendo validos
    for m in sorted(matches, key=lt_compat.offset, reverse=True):
        if lt_compat.categoria(m) not in CATEGORIAS_PERMITIDAS:
            continue

        sugerencias = lt_compat.reemplazos(m)
        if not sugerencias:
            continue

        inicio, fin = lt_compat.span(m)
        if fin <= inicio:
            continue

        original = texto[inicio:fin]
        senalados.add(reglas.normalizar(original))

        # una tilde faltante se restaura aunque el token este protegido: un
        # termino del diccionario escrito sin acento ('vertigo', 'sincope')
        # debe recibirlo igual. Las siglas y los numeros quedan fuera.
        if reglas.esta_protegido(original, protegidos):
            norm = reglas.normalizar(original)
            if norm in reglas.SIGLAS or reglas.tiene_numero(original):
                continue
            acentuado = next(
                (c for c in sugerencias if reglas.es_restauracion_tilde(norm, c)), None
            )
            if acentuado is None:
                continue
            texto = texto[:inicio] + acentuado + texto[fin:]
            continue

        reemplazo = candidatos.elegir(original, sugerencias, protegidos)
        if reemplazo is None:
            continue

        texto = texto[:inicio] + reemplazo + texto[fin:]

    # a minusculas ANTES de SymSpell: LanguageTool devuelve 'Valoración' con
    # mayuscula al abrir frase, y SymSpell reprocesaba 'aloración' dejando
    # 'Vvaloración'
    texto = texto.lower()

    if USAR_VOCABULARIO and vocabulario.disponible():
        texto = vocabulario.corregir_texto(
            texto,
            lambda p: not reglas.esta_protegido(p, protegidos)
                      and not reglas.es_palabra_conocida(p),
            senalados=senalados,
        )

    texto = re.sub(r"[ \t]+", " ", texto).strip()

    if RESTAURAR_MAYUSCULAS:
        texto = restaurar_mayusculas(texto, texto_original)

    return texto


# ==========================================================
# AUDITORIA
# ==========================================================

def diagnosticar(texto, texto_original=None):
    """Por que se aplico o se descarto cada cambio."""
    referencia = casing.restaurar(texto_original) if texto_original else texto_original
    protegidos = reglas.detectar_protegidos(referencia)
    ents = reglas.entidades(texto, referencia)
    protegidos = protegidos | ents | reglas.tokens_protegidos_por_contexto(texto)

    lt = iniciar_languagetool()
    texto = aplicar_directas(texto)

    filas = []
    for m in sorted(lt.check(texto), key=lt_compat.offset):
        inicio, fin = lt_compat.span(m)
        original = texto[inicio:fin]
        norm = reglas.normalizar(original)
        categoria = lt_compat.categoria(m)

        if categoria not in CATEGORIAS_PERMITIDAS:
            motivo = f"categoria {categoria} desactivada"
        elif reglas.tiene_numero(original):
            motivo = "contiene numeros"
        elif norm in reglas.SIGLAS:
            motivo = "sigla del diccionario"
        elif norm in ents:
            motivo = "entidad nombrada (spaCy)"
        elif norm in protegidos:
            motivo = "nombre propio o sigla del texto original"
        elif reglas.es_palabra_conocida(norm):
            motivo = "palabra del vocabulario de spaCy"
        elif len(norm) < reglas.LONGITUD_MINIMA:
            motivo = f"token de {len(norm)} letras, minimo {reglas.LONGITUD_MINIMA}"
        else:
            elegido = candidatos.elegir(original, lt_compat.reemplazos(m), protegidos)
            motivo = f"-> {elegido}" if elegido else "sin evidencia suficiente"

        filas.append({
            "token": original,
            "regla": lt_compat.regla(m),
            "categoria": categoria,
            "candidatos": lt_compat.reemplazos(m)[:5],
            "decision": motivo,
            "symspell": vocabulario.diagnosticar(norm) if vocabulario.disponible() else None,
        })
    return filas
