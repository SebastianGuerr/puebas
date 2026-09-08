"""
Fase 2. Correccion ortografica de notas de triage.

Este modulo solo orquesta. La logica vive en:
    lexico.py        el vocabulario clinico: 23.767 formas de cuatro fuentes
    pesos.py         cuanto pesa cada palabra, o sea cuanto hay que protegerla
    enmascarado.py   aparta lo clinico y lo arregla contra el lexico
    reglas.py        que no se toca (siglas, numeros, entidades, forma)
    candidatos.py    cual de las sugerencias se aplica
    vocabulario.py   SymSpell, para los typos que LanguageTool no propone
    linguistica.py   spaCy, vocabulario amplio y entidades nombradas
    lt_compat.py     diferencias de API entre versiones de LanguageTool

CADENA
    correcciones directas
      -> ENMASCARADO CLINICO      aparta la terminologia y la corrige por lexico
      -> LanguageTool (TYPOS)     solo sobre lo que quedo fuera
      -> SymSpell                 solo sobre lo que LanguageTool marco

EL ORDEN CAMBIO, Y ESA ES LA CORRECCION DE FONDO
    La version anterior corregia primero y vetaba despues: LanguageTool proponia
    y ocho guardias intentaban frenar los cambios peligrosos. Bastaba que un
    guardia tuviera un agujero para que pasara un cambio malo, y lo tenia:

        AÑOÑ -> anón      'añoñ' y 'anón' plegaban al mismo 'anon' porque
                          sin_tildes() trataba la eñe como acento. Eso hacia
                          verdadera a es_restauracion_tilde(), que es la primera
                          rama de candidatos.elegir() y retorna antes de
                          consultar a ninguno de los ocho guardias.

    Ahora la terminologia se aparta ANTES. 'epistaxis' no se corrompe porque el
    corrector nunca la recibe, no porque un guardia la rescate a tiempo.

    Y como los terminos ya no dependen de LanguageTool, se pueden arreglar
    contra un lexico medico, que es lo que el corrector de espanol nunca pudo
    hacer: su diccionario no contiene 'abdominal' como termino clinico ni
    'dislipidemia' ni 'valsalva'.

PRINCIPIO
    La asimetria del error no es simetrica. Dejar 'dias' sin tilde le cuesta
    poco al modelo de la fase siguiente; convertir 'midazolam' en 'madapolan' o
    'Pereira' en 'perdida' le inyecta un dato falso. Ante la duda, no se corrige.
"""

import re

import language_tool_python

import candidatos
import casing
import contexto
import enmascarado
import lexico
import linguistica
import lt_compat
import pesos
import reglas
import sugerencias
import terminologia
import vocabulario
from limpieza import tokenizar

CATEGORIAS_PERMITIDAS = {"TYPOS"}
USAR_VOCABULARIO = True
RESTAURAR_MAYUSCULAS = True

# La capa de contexto. Es lo unico del pipeline que puede arreglar una palabra
# bien escrita pero equivocada ('ala' por 'a la'), y tambien lo mas caro.
USAR_CONTEXTO = True

_LT = None
_CAMBIOS_CONTEXTO = []


# ==========================================================
# CARGA
# ==========================================================

def cargar_siglas(ruta=reglas.RUTA_SIGLAS):
    return reglas.cargar(ruta)


def cargar_lexico_clinico():
    """
    Lee lexico_clinico.json, que es lo que decide que palabras no llegan al
    corrector. Sin el, pesos.py se queda solo con el diccionario a mano y la
    morfologia, que es como estaba antes de este cambio.
    """
    entradas = lexico.cargar()
    if entradas:
        print(f"  lexico clinico: {entradas:,} formas "
              f"(umbral de proteccion {pesos.UMBRAL_PROTECCION})")
    else:
        print("  AVISO: falta lexico_clinico.json. Corre antes: python lexico.py")
    return entradas


def construir_lexico(textos):
    """Frecuencias del corpus y diccionario de SymSpell, del mismo material."""
    textos = list(textos)
    candidatos.construir_lexico(textos)

    # pesos.py usa la frecuencia para reconocer la jerga del servicio: una
    # palabra que el hospital repite y ningun diccionario conoce
    pesos.usar_conteo(candidatos.CONTEO)

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


def es_sigla_real(token):
    """
    True si el token es una sigla de verdad, y no un termino clinico que el
    diccionario guarda en la misma bolsa.

    POR QUE HACE FALTA DISTINGUIRLOS
        diccionario_siglas.json mezcla dos cosas en SIGLAS: abreviaturas
        (HTA, EKG, EPOC) y terminos clinicos completos (palpacion,
        auscultacion, hemodinamicamente, vertigo, sincope). La restauracion de
        tilde se saltaba para todo lo que estuviera en SIGLAS, asi que esos
        terminos quedaban congelados sin acento para siempre. Medido contra el
        conjunto de referencia, era una de las tres causas de omision.

        Una sigla no lleva tilde; un termino si. Lo que los separa con
        evidencia es como los escribe el hospital: casing.py aprendio de las
        11.415 notas bien escritas que 'hta', 'ekg' y 'epoc' van en mayuscula,
        y que 'palpacion' y 'vertigo' no.

    Sin lexico de capitalizacion se cae al criterio anterior, que es
    conservador: se saltan todas las entradas del diccionario.
    """
    token = reglas.normalizar(token)
    if not token:
        return False
    if casing.disponible():
        return casing.es_sigla(token)
    return token in reglas.SIGLAS


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


def aplicar_contexto(texto, nota):
    """
    Ultima pasada: arregla las palabras que existen pero no caben donde estan.

    Recorre de derecha a izquierda para que los offsets pendientes sigan siendo
    validos, y se salta todo lo que el enmascarado aparto. Cada cambio pasa
    ademas por el guardian clinico, igual que los de LanguageTool y SymSpell:
    que la evidencia venga de un modelo de lenguaje no lo exime del criterio
    medico.
    """
    cambios = []
    for m in reversed(list(reglas.RE_PALABRA.finditer(texto))):
        palabra = m.group(0)
        inicio, fin = m.start(), m.end()

        # terminologia clinica: no se toca, y ni siquiera se evalua
        if nota.protegido(inicio, fin):
            continue
        if pesos.peso(palabra)[0] >= pesos.UMBRAL_PROTECCION:
            continue

        posibles = sugerencias.generar(palabra)
        if not posibles:
            continue

        # Si entre los candidatos esta la misma palabra acentuada, esa es la
        # unica que se considera. Restaurar una tilde no puede cambiar el
        # concepto -- deja las mismas letras -- mientras que cualquier otro
        # cambio si. Medido: sin esta regla 'Psicologa' se convirtio en
        # 'psicologia' teniendo 'psicóloga' en la lista.
        acentuadas = [c for c in posibles if reglas.es_restauracion_tilde(palabra, c)]
        if acentuadas:
            posibles = acentuadas

        decision = contexto.elegir(texto[:inicio], palabra, texto[fin:], posibles)
        if decision is None:
            continue

        elegido, ganancia = decision

        # MISMOS guardias que la correccion por lexico, y por la misma razon.
        # Medido contra el conjunto de referencia, sin ellos la capa de
        # contexto bajo la precision de 97,8% a 95,6% con tres danos:
        #
        #   canadnan       -> canadian        ingles del vocabulario biomedico
        #   LEVOFLOXACIBNA -> levofloxacino   farmaco, y en el genero contrario
        #   Psicologa      -> psicologia      cuando la correccion era la tilde
        #
        # Que la evidencia venga de un modelo de lenguaje no exime del criterio
        # clinico. Las divisiones en dos palabras ('a la') se saltan el
        # guardian porque no son una palabra que comparar.
        if " " not in elegido and not enmascarado.admisible(palabra, elegido):
            continue

        texto = texto[:inicio] + elegido + texto[fin:]
        cambios.append((palabra, elegido, round(ganancia, 2)))

    if cambios:
        _CAMBIOS_CONTEXTO.extend(cambios)
    return texto


def resumen_contexto(minimo=1):
    """Que cambio la capa de contexto y con cuanta ganancia. Para auditar."""
    from collections import Counter
    conteo = Counter((o, r) for o, r, _g in _CAMBIOS_CONTEXTO)
    ganancias = {}
    for o, r, g in _CAMBIOS_CONTEXTO:
        ganancias[(o, r)] = max(ganancias.get((o, r), 0), g)
    return [(o, r, n, ganancias[(o, r)])
            for (o, r), n in conteo.most_common() if n >= minimo]


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

    # PASO NUEVO, Y EL MAS IMPORTANTE DEL MODULO.
    # Antes de que LanguageTool vea la nota, enmascarado.py aparta la
    # terminologia clinica y arregla la que venia mal escrita usando el lexico
    # medico. Lo que sale de aqui ya trae 'abodominal' convertido en
    # 'abdominal', y trae marcados los rangos que el corrector no puede tocar.
    #
    # Es la inversion de politica: antes se corregia y ocho guardias intentaban
    # vetar; ahora lo clinico no llega al corrector, asi que no hay veto que
    # pueda fallar.
    nota = enmascarado.enmascarar(texto)
    texto = nota.texto
    protegidos = protegidos | nota.palabras_protegidas()

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

        # El tramo es terminologia clinica: solo se admite ponerle una tilde.
        #
        # Es la unica operacion que no puede cambiar el concepto, porque por
        # construccion deja las mismas letras. Y ahora es de verdad segura: la
        # eñe dejo de plegarse como acento, asi que 'añoñ'/'anón' ya no cuenta
        # como restauracion de tilde y no puede colarse por esta puerta.
        if nota.protegido(inicio, fin):
            norm = reglas.normalizar(texto[inicio:fin])
            if es_sigla_real(norm):
                continue
            acentuado = next(
                (c for c in sugerencias if reglas.es_restauracion_tilde(norm, c)), None)
            if acentuado is None:
                continue
            texto = texto[:inicio] + acentuado + texto[fin:]
            continue

        original = texto[inicio:fin]
        senalados.add(reglas.normalizar(original))

        # una tilde faltante se restaura aunque el token este protegido: un
        # termino del diccionario escrito sin acento ('vertigo', 'sincope')
        # debe recibirlo igual. Las siglas y los numeros quedan fuera.
        if reglas.esta_protegido(original, protegidos):
            norm = reglas.normalizar(original)
            if es_sigla_real(norm) or reglas.tiene_numero(original):
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

    # PASO NUEVO: la capa de contexto.
    #
    # Lo que llega aqui ya paso por el diccionario, el lexico clinico,
    # LanguageTool y SymSpell. Lo que sobrevive a todos ellos y sigue estando
    # mal es, por definicion, una palabra que EXISTE: 'ala' por 'a la',
    # 'cordada' por 'cortada', 'gral' por 'general'. Ningun corrector
    # ortografico las ve, porque su criterio es si la palabra existe y existe.
    #
    # Va al final a proposito. Es la capa mas cara (un pase del modelo por
    # candidato) y la mas arriesgada, asi que solo ve lo que nadie mas supo
    # arreglar, y nunca ve la terminologia: los rangos protegidos se saltan.
    if USAR_CONTEXTO and contexto.disponible():
        texto = aplicar_contexto(texto, nota)

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
