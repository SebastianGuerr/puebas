"""
Fase 2. Corrección ortográfica de las notas de triage.

Este módulo orquesta la fase; la lógica vive en los módulos del paquete:

    recursos/lexico.py    el vocabulario clínico contra el que se decide
    pesos.py              cuánto hay que proteger cada palabra
    enmascarado.py        aparta lo clínico y lo corrige contra el léxico
    nucleo/reglas.py      qué no se toca: siglas, números, entidades, forma
    candidatos.py         cuál de las sugerencias se aplica
    vocabulario.py        SymSpell, para los errores que LanguageTool no ve
    sugerencias.py        candidatos declarados para la capa de contexto
    contexto.py           si la palabra cabe donde está
    terminologia.py       el veto clínico sobre cualquier cambio

LA CADENA, EN ORDEN
    correcciones directas declaradas
      -> enmascarado clínico     aparta la terminología y la corrige por léxico
      -> LanguageTool            solo sobre lo que quedó fuera del enmascarado
      -> SymSpell                solo sobre lo que LanguageTool marcó
      -> capa de contexto        solo sobre lo que nadie supo arreglar
      -> restauración de siglas  devuelve a mayúscula lo que es sigla

    Cada capa ve menos texto que la anterior, y la terminología clínica no llega
    a ninguna: se aparta en el primer paso.

POR QUÉ ESE ORDEN
    La versión anterior corregía primero y vetaba después, de modo que bastaba
    un hueco en un veto para que pasara un cambio dañino. Al apartar la
    terminología antes, un término no se corrompe porque el corrector nunca lo
    recibe, y no porque una regla lo rescate a tiempo.

    Además, al no depender de LanguageTool, los términos pueden corregirse
    contra un léxico médico, que es lo que un corrector de español no puede
    hacer: su diccionario no contiene la terminología clínica.

EL PRINCIPIO
    El coste del error no es simétrico. Dejar una palabra sin tilde apenas
    afecta a las fases siguientes; convertir un fármaco o un topónimo en otra
    palabra les inyecta un dato falso. Ante la duda, no se corrige.
"""

import atexit
import re
import subprocess
import threading

import language_tool_python

from NLP.fase2_ortografia import candidatos
from NLP.fase2_ortografia import contexto
from NLP.fase2_ortografia import enmascarado
from NLP.fase2_ortografia import pesos
from NLP.fase2_ortografia import sugerencias
from NLP.fase2_ortografia import vocabulario
from NLP.nucleo import lt_compat
from NLP.nucleo import reglas
from NLP.recursos import casing
from NLP.recursos import lexico

CATEGORIAS_PERMITIDAS = {"TYPOS"}
USAR_VOCABULARIO = True

# Ninguna correccion puede cambiar las CIFRAS de un token. pesos.py ya declara
# "nada con un digito se toca jamas" (PESOS["numero"] = 1.00), pero esa
# proteccion solo se consulta cuando el token ya venia en la lista de
# protegidos de la nota; la rama que aplica las sugerencias de LanguageTool no
# la mira. Medido sobre salidas/pares_correccion.csv el 2026-09-16: cinco pares
# dividen una cifra por diez, entre ellos '1000cc' -> '100cc' y
# '1000mg' -> '100mg'. En una nota clinica eso es una dosis cambiada.
# Ver decisiones/2026-09-16-cifras.md.
PROTEGER_CIFRAS = True

RE_CIFRAS = re.compile(r"\d+")


def mismas_cifras(original, reemplazo):
    """True si el reemplazo conserva exactamente las cifras del original."""
    return RE_CIFRAS.findall(str(original)) == RE_CIFRAS.findall(str(reemplazo))
RESTAURAR_MAYUSCULAS = True

# La capa de contexto. Es lo unico del pipeline que puede arreglar una palabra
# bien escrita pero equivocada ('ala' por 'a la'), y tambien lo mas caro.
USAR_CONTEXTO = True

# LA PALABRA ESTABLECIDA NO SE TOCA, SALVO QUE SEA UNA ABREVIATURA.
#
# La capa de contexto trabaja sobre palabras correctas -- para eso existe -- y
# por tanto no tiene la senal que usan las capas anteriores, que es que ningun
# diccionario reconozca el token. Sin ningun freno produjo, sobre palabras
# corrientes que el corpus repite:
#
#     sufre       -> 'sobre'        un verbo comun sustituido
#     instaurada  -> 'instalada'
#     los         -> 'lamentamos'
#
# El corte combina las dos cosas que hacen improbable la errata: que el espanol
# reconozca la palabra Y que el hospital la escriba muchas veces. Una errata
# repetida decenas de veces con la misma forma deja de ser una errata.
FRECUENCIA_PALABRA_ESTABLECIDA = 20

# La excepcion, y hace falta. El freno anterior era demasiado romo: bloqueaba
#
#     gral -> general
#
# que es exactamente el caso para el que existe esta capa. 'gral' aparece 20
# veces y spaCy la reconoce, asi que por frecuencia es indistinguible de una
# palabra correcta.
#
# Lo que la distingue no es la frecuencia sino la FORMA: expandir una
# abreviatura conserva todas sus letras y en el mismo orden ('g-r-a-l' esta
# dentro de 'g-e-n-e-r-a-l'), y no la alarga sin limite. Las tres corrupciones
# de arriba fallan la prueba -- 'sufre' no esta dentro de 'sobre', 'instaurada'
# no esta dentro de 'instalada' -- y 'los' si esta dentro de 'lamentamos' pero
# lo triplica en longitud, que es lo que descarta el tope.
RATIO_EXPANSION_MAXIMO = 2.0


def _es_expansion(original, candidato):
    """
    True si el candidato parece la forma larga de una abreviatura: contiene
    todas las letras del original en orden y no lo alarga mas de lo permitido.
    """
    o, c = original.lower(), candidato.lower().replace(" ", "")
    if len(c) <= len(o) or len(c) > RATIO_EXPANSION_MAXIMO * len(o):
        return False
    it = iter(c)
    return all(letra in it for letra in o)

_LT = None

# UN SOLO LanguageTool PARA CUATRO HILOS, Y POR ESO HACE FALTA EL CANDADO.
#
# language_tool_python guarda el proceso del servidor en self._server y lo
# REEMPLAZA cuando una peticion falla y hay que reiniciarlo. Con varios hilos
# llamando a check() sobre la misma instancia, dos pueden entrar a la vez a ese
# reinicio y pisarse: el communicate() de uno se traga la linea de arranque que
# el otro esta esperando con readline(), y los dos quedan bloqueados para
# siempre. Ninguno lanza excepcion, asi que el try/except de corregir() no se
# entera y la corrida se cuelga entera con la CPU al 100%.
#
# Paso de verdad: la corrida del 9 de septiembre se congelo al 52% con dos
# hilos trabados de esa forma, y solo se destrabo matando el java a mano.
#
# El candado no cuesta casi nada porque contexto.logprob ya serializa la parte
# lenta de esta fase con su propio candado.
_LT_LOCK = threading.Lock()
_CAMBIOS_CONTEXTO = []


# ==========================================================
# CARGA
# ==========================================================

def cargar_siglas(ruta=reglas.RUTA_SIGLAS):
    """Carga el diccionario de siglas del proyecto. Devuelve el conjunto."""
    return reglas.cargar(ruta)


def cargar_lexico_clinico():
    """
    Carga el léxico clínico, que es lo que determina qué palabras no llegan al
    corrector, y devuelve cuántas formas trae.

    Si el archivo no existe avisa y sigue: el peso clínico se calcula entonces
    solo con el diccionario escrito a mano y la morfología, con menos cobertura.
    """
    entradas = lexico.cargar()
    if entradas:
        print(f"  lexico clinico: {entradas:,} formas "
              f"(umbral de proteccion {pesos.UMBRAL_PROTECCION})")
    else:
        print("  AVISO: falta lexico_clinico.json. Corre antes: python -m NLP.recursos.lexico")
    return entradas


def construir_lexico(textos):
    """
    Prepara todo lo que depende del corpus: el recuento de frecuencias, que
    alimenta los desempates y la detección de jerga, y el diccionario de
    SymSpell. Debe llamarse una vez antes de corregir la primera nota.
    """
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
    """
    Crea la instancia de LanguageTool la primera vez y la reutiliza, informando
    de si sus atributos se leen bien en la versión instalada.
    """
    global _LT
    if _LT is None:
        _LT = language_tool_python.LanguageTool(idioma)
        print(f"  LanguageTool: {lt_compat.verificar(_LT)}")
    return _LT


# ==========================================================
# CORRECCIÓN
# ==========================================================

def _matar_arbol(proceso):
    """
    Mata el proceso del servidor Y TODOS SUS DESCENDIENTES, y espera a que
    mueran de verdad.

    POR QUE NO BASTA CON MATAR EL PROCESO QUE ARRANCO Popen
        Porque ese no es el servidor. 'java -cp ... HTTPServer' resulta ser un
        lanzador que arranca UN SEGUNDO java, y el segundo es el que abre el
        puerto. Medido el 11 de septiembre: Popen arranca el java 14180, ese
        arranca el java 1228, y el que aparece escuchando en 8083 es el 1228.

        Matar solo al lanzador deja vivo al servidor, y con el los extremos de
        escritura de stdout y stderr que heredo al nacer. El pipe no llega
        nunca a EOF, el hilo lector de la libreria se queda en readline() para
        siempre, y el proceso de Python NO SALE aunque el trabajo este hecho y
        escrito.

        Es ademas el origen de los servidores huerfanos que motivaron esta
        funcion: cada corrida dejaba un java escuchando su puerto y la
        siguiente arrancaba un puerto mas arriba. El 11 de septiembre habia
        tres a la vez, en 8081, 8082 y 8083.

    Los descendientes se enumeran ANTES de matar al padre: una vez muerto,
    Windows los reasigna y dejan de ser localizables desde este pid.
    """
    try:
        import psutil
    except ImportError:
        psutil = None

    if psutil is not None:
        try:
            padre = psutil.Process(proceso.pid)
            familia = padre.children(recursive=True) + [padre]
            for miembro in familia:
                try:
                    miembro.kill()
                except psutil.Error:
                    pass
            psutil.wait_procs(familia, timeout=10)
            return
        except psutil.Error:
            pass

    # Sin psutil (no esta en requirements, llega de arrastre) taskkill /T baja
    # el arbol igual. Si tampoco hay, queda el kill de siempre: se sabe que no
    # alcanza, pero es mejor que no intentar nada.
    try:
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proceso.pid)],
                       capture_output=True, timeout=15)
    except (OSError, subprocess.SubprocessError):
        try:
            proceso.kill()
        except OSError:
            pass


def cerrar_languagetool():
    """
    Apaga el servidor de LanguageTool al terminar el proceso.

    Sin esto, cada corrida deja vivo su java escuchando en un puerto. El 9 de
    septiembre habia OCHO servidores huerfanos de corridas anteriores ocupando
    1,75 GB, y como language_tool_python busca el siguiente puerto libre, cada
    corrida nueva arrancaba un puerto mas arriba en vez de reutilizar.

    POR QUE NO SE LLAMA A _LT.close() A SECAS
        Porque cuelga el proceso para siempre, y lo hace JUSTO AL FINAL, con el
        trabajo ya hecho y escrito. Paso el 10 y el 11 de septiembre: las notas
        completas en el CSV, el resumen impreso, y el prompt sin volver nunca.

        El close() de la libreria termina en _terminate_server(), que hace:

            self._server.terminate()
            self._server.communicate()[1]      # <-- sin timeout

        communicate() arranca un hilo lector por pipe y los espera con join()
        sin plazo, mientras el hilo '_consume' de la propia libreria lleva
        desde el arranque leyendo ese mismo stdout. Con el servidor de verdad
        todavia vivo (ver _matar_arbol) el pipe no cierra, ningun lector
        termina, y el join se queda ahi. El stack era siempre identico:

            cerrar_languagetool -> close -> _terminate_server
              -> communicate -> join -> _wait_for_tstate_lock

        Aqui se hace lo unico que hacia falta: bajar el arbol de procesos
        entero y cerrar los pipes SIN LEERLOS.
    """
    global _LT
    if _LT is None:
        return

    servidor = getattr(_LT, "_server", None)
    if servidor is not None:
        _matar_arbol(servidor)
        for flujo in (servidor.stdin, servidor.stdout, servidor.stderr):
            try:
                flujo.close()
            except OSError:
                pass
        # Con _server en None, _server_is_alive() da False y el close() de la
        # libreria se salta su propio _terminate_server: ya no hay nada que
        # apagar y solo queda que limpie lo suyo.
        _LT._server = None

    try:
        _LT.close()
    except Exception:
        pass
    _LT = None


atexit.register(cerrar_languagetool)


def aplicar_directas(texto):
    """
    Aplica las correcciones declaradas a mano en el diccionario. Son errores
    conocidos, así que se sustituyen sin más comprobaciones.
    """
    return reglas.RE_PALABRA.sub(
        lambda m: reglas.DIRECTAS.get(m.group(0), m.group(0)), texto
    )


DOMINANCIA_PARA_ESCRIBIR = 0.85


def es_sigla_real(token):
    """
    True si el token es una sigla de verdad y no un término clínico completo.

    Hace falta distinguirlos porque el diccionario del proyecto guarda ambas
    cosas en el mismo conjunto: abreviaturas como 'hta' o 'ekg' y términos como
    'vertigo' o 'sincope'. Una sigla no lleva tilde y un término sí, de modo que
    tratar todo el diccionario como siglas dejaba esos términos sin acentuar de
    forma permanente.

    La distinción se apoya en cómo escribe el hospital, según el léxico de
    capitalización. Sin ese léxico se recurre al criterio conservador anterior:
    se considera sigla toda entrada del diccionario.
    """
    token = reglas.normalizar(token)
    if not token:
        return False
    if casing.disponible():
        return casing.es_sigla(token)
    return token in reglas.SIGLAS


def restaurar_mayusculas(texto, texto_original=None):
    """
    Devuelve las siglas clínicas a mayúscula ('hta' pasa a 'HTA').

    Solo escribe siglas: un nombre propio queda protegido de la corrección, pero
    esta función no lo capitaliza.

    Usa tres fuentes de evidencia, en este orden:

      1. La nota misma. Si el token venía en mayúsculas en el original y la nota
         no está gritada, es el dato más fuerte que existe, porque lo escribió
         quien atendió a ese paciente. La evidencia se lee POR OCURRENCIA, no
         por palabra: si un token aparece dos veces con sentidos distintos, solo
         se capitaliza donde de verdad venía en mayúscula.
      2. El corpus. En una nota gritada la primera fuente no dice nada, así que
         se recurre a las siglas aprendidas, exigiendo que aparezcan casi
         siempre en mayúscula. Con un criterio más laxo, una palabra corriente
         que a veces es sigla se capitalizaría en todos sus usos.
      3. El diccionario del proyecto.

    Además de venir en mayúscula, el token tiene que ser una sigla conocida. Sin
    esa condición, el énfasis del que escribe (una lista de antecedentes en
    mayúsculas) se confundiría con siglas y quedaría gritado dentro de un texto
    ya normalizado.
    """
    # Del lexico aprendido solo cuentan las formas que NO son palabra del
    # espanol: como en las notas se escriben en mayuscula listas enteras de
    # antecedentes, el corpus aprende como siglas palabras que en realidad son
    # enfasis, y lo que separa una sigla de una palabra enfatizada es que la
    # sigla no existe como palabra. El diccionario escrito a mano entra
    # completo, porque cada entrada suya es una decision deliberada.
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
    Índices de los tokens del texto corregido que en la nota original venían en
    mayúscula y además son siglas conocidas.

    Los dos textos no coinciden token a token, porque la limpieza elimina
    símbolos y la corrección cambia palabras, así que se alinean sobre su
    versión en minúsculas y la decisión se copia solo donde hay
    correspondencia. Sobre una nota gritada devuelve un conjunto vacío: ahí las
    mayúsculas no distinguen nada.
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
    Última pasada: arregla las palabras que existen pero no caben donde están.

    Recorre el texto de derecha a izquierda para que las posiciones pendientes
    sigan siendo válidas tras cada sustitución, y se salta todo lo que el
    enmascarado apartó. Devuelve el texto ya corregido y acumula los cambios
    para el informe.

    Cada cambio pasa por los mismos filtros que la corrección por léxico: que la
    evidencia venga de un modelo de lenguaje no lo exime del criterio clínico.
    Las divisiones en dos palabras se saltan ese filtro porque no hay una única
    palabra que comparar.
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

        # una palabra corriente que el hospital repite no es una errata; la
        # excepcion son las abreviaturas, que ver _es_expansion()
        establecida = (pesos.frecuencia(palabra) >= FRECUENCIA_PALABRA_ESTABLECIDA
                       and reglas.es_palabra_conocida(reglas.normalizar(palabra)))

        posibles = sugerencias.generar(palabra)
        if establecida:
            posibles = [c for c in posibles if _es_expansion(palabra, c)]
        if not posibles:
            continue

        # si entre los candidatos esta la misma palabra acentuada, es la unica
        # que se considera: restaurar una tilde deja las mismas letras y no
        # puede cambiar el concepto, mientras que cualquier otro cambio si
        acentuadas = [c for c in posibles if reglas.es_restauracion_tilde(palabra, c)]
        if acentuadas:
            posibles = acentuadas

        decision = contexto.elegir(texto[:inicio], palabra, texto[fin:], posibles)
        if decision is None:
            continue

        elegido, ganancia = decision

        # mismos filtros que la correccion por lexico y por la misma razon; las
        # divisiones en dos palabras no pasan por aqui porque no hay una unica
        # palabra que comparar
        # LAS DIVISIONES EN DOS PALABRAS TAMBIEN SE VALIDAN.
        #
        # Antes se saltaban todos los filtros, con el argumento de que no hay
        # una unica palabra que comparar. La consecuencia era que la operacion
        # mas arriesgada de la capa mas arriesgada resultaba ser la unica sin
        # ningun control, y produjo
        #
        #     afiliados  ->  'afilia dos'    'afiliado s'
        #
        # sobre una palabra que el espanol reconoce, que el corpus escribe 92
        # veces y que LanguageTool no habia marcado. Partirla inventa dos
        # palabras donde habia una correcta.
        #
        # No hay una palabra que comparar, pero si hay una pregunta que se puede
        # responder: si la palabra de partida ya existe, no se parte.
        #
        # NO SE REVALIDAN LOS TROZOS, Y RETIRARLO FUE UNA CORRECCION.
        #     Esta guarda comprobaba ademas que cada mitad existiera, con
        #     reglas.es_palabra_conocida(). Esa funcion descarta los tokens muy
        #     cortos, de modo que 'a', 'la', 'su' y 'al' no cuentan como
        #     palabras y toda division legitima quedaba bloqueada:
        #
        #         ala -> 'a la'     asu -> 'a su'
        #
        #     que son justo los dos casos que justifican la existencia de esta
        #     capa. La comprobacion sobraba: sugerencias._divisiones() ya exige
        #     que las dos mitades sean palabras reales al generarlas, con un
        #     criterio que si admite las funcionales. Revalidar aqui con una
        #     regla mas estricta que la del generador solo podia restar.
        if " " in elegido:
            if reglas.es_palabra_conocida(reglas.normalizar(palabra)):
                continue
        elif not enmascarado.admisible(palabra, elegido):
            continue

        texto = texto[:inicio] + elegido + texto[fin:]
        cambios.append((palabra, elegido, round(ganancia, 2)))

    if cambios:
        _CAMBIOS_CONTEXTO.extend(cambios)
    return texto


def resumen_contexto(minimo=1):
    """
    Cambios aplicados por la capa de contexto, con su número de apariciones y la
    mayor ganancia observada. Se usa en el informe de auditoría de la corrida.
    """
    from collections import Counter
    conteo = Counter((o, r) for o, r, _g in _CAMBIOS_CONTEXTO)
    ganancias = {}
    for o, r, g in _CAMBIOS_CONTEXTO:
        ganancias[(o, r)] = max(ganancias.get((o, r), 0), g)
    return [(o, r, n, ganancias[(o, r)])
            for (o, r), n in conteo.most_common() if n >= minimo]


def corregir(texto, texto_original=None):
    """
    Corrige una nota y devuelve el texto resultante.

        texto            la nota ya limpia, en minúsculas
        texto_original   la nota sin limpiar. Aporta las mayúsculas, que son la
                         única pista de que un token es un nombre propio y no un
                         error de digitación.

    Recorre la cadena completa descrita en la cabecera del módulo. Ante
    cualquier fallo de LanguageTool sigue adelante sin sus propuestas, de modo
    que una nota nunca queda sin procesar por un error del corrector.
    """
    if not texto:
        return texto

    # La mayoria de las notas viene integramente en mayusculas, y ahi ni la
    # deteccion por contraste ni el reconocedor de entidades tienen nada que
    # leer. Restaurar la capitalizacion que el corpus indica devuelve el
    # contraste y con el las dos defensas. Sobre una nota que ya venia con
    # mayusculas y minusculas no se toca nada, asi que este paso no degrada
    # nunca el caso bueno.
    referencia = casing.restaurar(texto_original) if texto_original else texto_original

    protegidos = reglas.detectar_protegidos(referencia)
    protegidos = protegidos | reglas.entidades(texto, referencia)
    protegidos = protegidos | reglas.tokens_protegidos_por_contexto(texto)

    texto = aplicar_directas(texto)

    # Antes de que LanguageTool vea la nota, el enmascarado aparta la
    # terminologia clinica y arregla contra el lexico medico la que venia mal
    # escrita. Lo que sale de aqui trae ya esos terminos corregidos y los
    # rangos que el corrector no puede tocar.
    nota = enmascarado.enmascarar(texto)
    texto = nota.texto
    protegidos = protegidos | nota.palabras_protegidas()

    lt = iniciar_languagetool()
    try:
        with _LT_LOCK:
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

        # el tramo es terminologia clinica: lo unico que se admite es ponerle
        # una tilde, que es la unica operacion que deja las mismas letras y por
        # tanto no puede cambiar el concepto
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

        # las cifras no se tocan: 'dolro' -> 'dolor' si, '1000cc' -> '100cc' no
        if PROTEGER_CIFRAS and not mismas_cifras(original, reemplazo):
            continue

        texto = texto[:inicio] + reemplazo + texto[fin:]

    # a minusculas antes de SymSpell: LanguageTool capitaliza al abrir frase, y
    # sobre esa mayuscula el segundo corrector reprocesaba mal la palabra
    texto = texto.lower()

    if USAR_VOCABULARIO and vocabulario.disponible():
        texto = vocabulario.corregir_texto(
            texto,
            lambda p: not reglas.esta_protegido(p, protegidos)
                      and not reglas.es_palabra_conocida(p),
            senalados=senalados,
        )

    # Lo que llega a la capa de contexto ya paso por el diccionario, el lexico
    # clinico, LanguageTool y SymSpell. Lo que sobrevive a todos ellos y sigue
    # mal es, por definicion, una palabra que existe, y ningun corrector
    # ortografico la ve.
    #
    # Va al final a proposito: es la capa mas cara y la mas arriesgada, asi que
    # solo ve lo que nadie mas supo arreglar, y nunca la terminologia.
    if USAR_CONTEXTO and contexto.disponible():
        texto = aplicar_contexto(texto, nota)

    texto = re.sub(r"[ \t]+", " ", texto).strip()

    if RESTAURAR_MAYUSCULAS:
        texto = restaurar_mayusculas(texto, texto_original)

    return texto


# ==========================================================
# AUDITORÍA
# ==========================================================

def diagnosticar(texto, texto_original=None):
    """
    Una fila por aviso de LanguageTool sobre la nota, con la regla que lo
    produjo, sus candidatos, el motivo por el que se aplicó o se descartó, y lo
    que habría propuesto SymSpell. Herramienta de inspección manual.
    """
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
