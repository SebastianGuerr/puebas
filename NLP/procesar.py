"""
Orquestador de las fases 1 a 3.

    python -m NLP.procesar

Es el único archivo del paquete que conoce la base de datos. Descarga las notas,
encadena la limpieza de formato, la corrección ortográfica y la normalización
clínica, y escribe en salidas/:

    triage_limpio.csv     una fila por nota, con el texto de cada fase
    reporte_cambios.csv   cada sustitución distinta, con su frecuencia

El reporte de cambios es la herramienta de revisión: en lugar de leer decenas de
miles de notas, se recorre la lista de sustituciones ordenada por frecuencia. Si
entre las primeras aparece un fármaco, una sigla o un nombre propio, hay que
llevarlo al diccionario antes de dar la corrida por buena. Quien construye ese
reporte y mide la corrida es `evaluacion/auditoria.py`.

QUÉ IMPRIME AL TERMINAR
    Además del resumen, dos listas que conviene revisar:

        correcciones frenadas por el guardián clínico, agrupadas por motivo, que
        indican qué reglas de protección están actuando;

        palabras dejadas intactas por falta de evidencia, ordenadas por
        frecuencia, que son las candidatas a entrar en el diccionario.

CONFIGURACIÓN
    Las constantes del bloque siguiente son los únicos parámetros que se tocan:
    qué tabla y columna se leen, cuántos registros se procesan, cuántos hilos se
    usan y si se ejecuta la fase 3.
"""

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from NLP import rutas
from NLP.depuracion import depuracion
from NLP.evaluacion import auditoria
from NLP.fase1_limpieza.limpieza import analizar, es_vacio, limpiar_conservando_original
from NLP.fase2_ortografia import coherencia, ortografia, terminologia
from NLP.fase3_normalizacion import normalizacion
from NLP.nucleo import cache as cache_disco
from NLP.nucleo import datos, reglas, requisitos
from NLP.nucleo.progreso import barra, fin_barra
from NLP.nucleo.salida import EscritorCSV, cabecera_compatible, llaves_escritas, rotar
from NLP.reduccion import extractor, reduccion
from NLP.recursos import casing

# ==========================================================
# CONFIGURACION
# ==========================================================

OUTPUT_CSV = rutas.TRIAGE_LIMPIO
REPORTE_CSV = rutas.REPORTE_CAMBIOS
DESCARTADAS_CSV = rutas.NOTAS_DESCARTADAS
CACHE_JSON = rutas.CACHE_CORRECCIONES

TABLA = "DIM_TRIAGE"
COLUMNA = "HCTMOTCON"
LLAVE = "OID"

# Cuantas notas procesa la corrida. Es EL sitio donde se decide, y admite
# desde 4 hasta la tabla entera con None. El argumento --limite de la linea de
# comandos solo lo pisa para una corrida concreta, sin tocar el archivo.
LIMITE_REGISTROS = 5000    # None = toda la tabla
MUESTREO_ALEATORIO = True
LIMITE_LEXICO = 200000      # registros usados solo para contar frecuencias

N_HILOS = 4
GUARDAR_CADA = 2000

# Cuantas notas se procesan de punta a punta antes de escribir en el CSV.
#
# POR QUE EL PIPELINE VA POR BLOQUES Y NO FASE POR FASE
#     Antes cada fase recorria las 5.000 notas y el CSV se escribia al final de
#     todo. Eso tenia dos problemas y los dos se pagaron el 9 de septiembre: una
#     corrida de horas que se cuelga no deja NADA en disco, y hasta que termina
#     no hay forma de mirar lo que va produciendo para decidir si vale la pena
#     esperarla o pararla y corregir.
#
#     Con bloques, cada uno pasa por las fases 2 a 5 completas y se escribe. El
#     CSV crece mientras corre: se puede abrir, revisar la calidad y empezar a
#     usarlo para el embedding sin esperar al final. Y si algo se cuelga, lo ya
#     escrito sigue ahi.
#
#     El costo es que las fases se preparan una vez pero se ejecutan por bloque.
#     Con 250 notas el arranque se diluye y el CSV se refresca a menudo.
BLOQUE_ESCRITURA = 250
NORMALIZAR = True           # agrega la columna texto_normalizado (fase 3)

# Fase 2b: compara lo corregido con la nota original y deshace lo que la
# estropeo. Cuesta 2,6 ms por nota y, medido sobre 8.751, toca el 0,4% de
# ellas: rescata cosas como 'ahogado' -> 'abogado', 'volcamiento' ->
# 'tocamiento' y 'tosiendo' -> 'comiendo', que son las que ensucian el
# clustering porque cambian el motivo sin dejar rastro.
#
# Solo puede DESHACER correcciones, nunca proponer una nueva, asi que
# apagarlo devuelve el comportamiento anterior exacto.
REVISAR_COHERENCIA = True

# Lo que la fase 2b deshizo, para el resumen del final. Es una lista y no un
# contador porque lo que interesa revisar son los pares concretos.
_INCIDENCIAS = []

# Fase 4: SENALA las notas que no parecen decir nada del paciente. No las saca
# del CSV: siguen ahi enteras y se vectorizan igual, y lo unico que cambia es
# que la fase 5 no les busca un motivo de consulta.
#
# POR QUE SENALAR Y NO ELIMINAR
#     Al revisar lo que tiraba aparecieron falsos descartes: junto al tramite
#     administrativo real caian motivos legitimos como 'tengo epigastralgia
#     desde hace 3 dias', porque ese termino solo vive en la fuente biomedica
#     del lexico, que la depuracion no cuenta como evidencia a proposito.
#
#     Los dos errores no cuestan lo mismo. Un falso descarte es irrecuperable:
#     la nota desaparece del CSV y con ella del embedding y del analisis. Un
#     falso senalamiento no cuesta nada: la nota sigue completa y solo se queda
#     sin recortar.
#
#     Que notas se senalaron se sabe cruzando por OID contra
#     salidas/notas_descartadas.csv, que es el archivo de control: sirve para
#     descubrir que terminos le faltan al diccionario sin perder ni un dato.
DEPURAR = True

# Fase 5: agrega la columna texto_embedding, la nota reducida a su motivo de
# consulta. Es el texto que consume el modelo de embeddings; texto_normalizado
# sigue estando entero al lado para leer y auditar.
REDUCIR = True

# Fase 5b: el modelo local de Ollama decide que parte de la nota es el motivo de
# consulta. Solo ve las notas largas y, si no esta disponible o se inventa algo,
# el recorte lo hacen las reglas. Ponerlo en False deja el pipeline funcionando
# sin el.
USAR_LLM = True

# La cache guarda la correccion de cada texto distinto, y es lo que hace que
# repetir una corrida cueste minutos en vez de horas. El riesgo es que conserva
# la decision del corrector vigente cuando se escribio: reutilizarla despues de
# cambiar el corrector produce un CSV que mezcla dos versiones, y cualquier
# medicion sobre el es enganosa.
#
# Por eso la version entra en la clave. Al modificar el corrector se sube este
# identificador y la cache anterior deja de aplicarse sola, sin depender de que
# alguien se acuerde de borrarla.
USAR_CACHE = True

# 4: la corrida del 15 de septiembre se hizo con es_core_news_md SIN INSTALAR,
# y eso cambia el corrector entero, no un detalle. Sin el modelo,
# linguistica.en_vocabulario() devuelve False para toda palabra y
# reglas.entidades() el conjunto vacio, asi que las cinco capas que consultan
# una u otra -- enmascarado, pesos, sugerencias, terminologia y vocabulario --
# decidian sin la señal que las gobierna: 'dipirona' o 'cefalea' figuraban como
# desconocidas y quedaban expuestas. Toda la cache anterior a esa instalacion
# guarda esas decisiones, y reutilizarla reproduce el daño intacto.
#
# Se suma la fase 2b (coherencia.py), que tambien cambia lo que sale.
VERSION_CORRECTOR = "4-con-spacy-y-coherencia"

# Como se llama en notas_descartadas.csv el veredicto del modelo. Se escribe
# tal cual en la columna motivo_descarte, al lado de los motivos que pone la
# depuracion, para poder separar unos de otros al revisar.
MOTIVO_SIN_CONTEXTO = "el modelo no encontro motivo de consulta"



# ==========================================================
# CARGA DE DATOS
# ==========================================================

def cargar_corpus(engine, filtro):
    """
    Construye el léxico de frecuencias con una muestra amplia de la tabla. Se
    lee más texto del que se va a corregir a propósito: los desempates por
    frecuencia son mejores cuanto mayor es el corpus observado.
    """
    print("Construyendo lexico del corpus...")
    df = datos.columna_suelta(engine, TABLA, COLUMNA, filtro, LIMITE_LEXICO)
    conteo = ortografia.construir_lexico(df[COLUMNA])
    print(f"  {len(conteo):,} palabras distintas sobre {len(df):,} notas")


def cargar_registros(engine, filtro, excluir=()):
    """
    Descarga las notas que TODAVIA no estan limpias, repartidas por toda la
    tabla y siempre en el mismo orden entre corridas. El porqué de ese orden
    repetible está en nucleo/datos.muestra().

    POR QUE LAS YA LIMPIAS SE EXCLUYEN EN LA CONSULTA Y NO AL LLEGAR
        Antes se bajaban LIMITE_REGISTROS notas y las ya hechas se filtraban en
        pandas. Como el orden es fijo a proposito, pedir 5.000 cuando ya habia
        5.000 limpias devolvia EXACTAMENTE esas 5.000 y dejaba cero por
        procesar: la corrida arrancaba, cargaba diccionarios, escribia sus
        salidas y terminaba sin tocar una sola nota nueva.

        Visto desde fuera no parecia un error, parecia que el pipeline no hacia
        nada. Paso el 11 de septiembre y costo una manana entenderlo.

        Ademas obligaba a subir --limite a mano cargando con el lastre: pedir
        20.000 para conseguir 15.000 nuevas, y al final de la tabla pedir
        90.000 para conseguir las ultimas.

        Con la exclusion en el WHERE, --limite significa lo que dice: cuantas
        notas NUEVAS procesa esta corrida. 2.000 son 2.000, se este por la
        primera o por la ultima.
    """
    print("Descargando registros...")
    df = datos.muestra(engine, TABLA, [LLAVE, COLUMNA], filtro,
                       limite=LIMITE_REGISTROS, disperso=MUESTREO_ALEATORIO,
                       llave=LLAVE, excluir=excluir)
    print(f"  {len(df):,} notas nuevas")
    return df


# ==========================================================
# PROCESAMIENTO
# ==========================================================

# Los tres envoltorios de abajo atan la caché genérica de nucleo/cache.py a la
# configuración de ESTE pipeline: su archivo, su versión y su interruptor. La
# lógica vive allí; aquí solo se decide con qué parámetros se usa.

def clave_cache(texto_limpio, protegidos):
    """Clave de caché de una nota. El porqué de cada parte, en nucleo/cache.py."""
    return cache_disco.clave(texto_limpio, VERSION_CORRECTOR, protegidos)


def preparar(df):
    """
    Aplica la fase 1 sobre el DataFrame y añade tres columnas de trabajo: el
    texto limpio, el original normalizado (que conserva las mayúsculas) y la
    clave de caché de cada nota.
    """
    print("Fase 1: limpieza de formato...")
    limpios, originales, claves = [], [], []

    for texto in df[COLUMNA]:
        limpio, original = limpiar_conservando_original(texto)
        protegidos = reglas.detectar_protegidos(original)
        limpios.append(limpio)
        originales.append(original)
        claves.append(clave_cache(limpio, protegidos))

    df["texto_limpio"] = limpios
    df["texto_norm"] = originales
    df["clave"] = claves
    return df


def corregir_lote(pendientes):
    """
    Corrige en paralelo los textos que no estaban en caché y devuelve
    {clave: texto corregido}.

    `pendientes` es una lista de ternas (clave, texto limpio, texto original).
    Si una nota falla, se avisa y se conserva su texto sin corregir: un error
    aislado no debe abortar una corrida de horas. El progreso se guarda cada
    GUARDAR_CADA notas, para no perder el trabajo si el proceso se interrumpe.
    """
    resultados = {}
    if not pendientes:
        return resultados

    ortografia.iniciar_languagetool()

    # Se cargan los modelos AQUI, en un solo hilo, antes de abrir el pool.
    # La carga perezosa desde cuatro hilos a la vez produce importaciones a
    # medias y pesos sin materializar, y las notas afectadas salen sin corregir.
    from NLP.fase2_ortografia import contexto
    contexto.iniciar()
    inicio = time.time()
    total = len(pendientes)

    def _tarea(item):
        _, limpio, original = item
        try:
            return ortografia.corregir(limpio, original)
        except Exception as exc:
            print(f"  aviso: fallo al corregir un texto ({exc})", file=sys.stderr)
            return limpio

    with ThreadPoolExecutor(max_workers=N_HILOS) as pool:
        for n, (item, corregido) in enumerate(zip(pendientes, pool.map(_tarea, pendientes)), 1):
            resultados[item[0]] = corregido

            if n % 25 == 0 or n == total:
                barra(n, total, inicio, "corrigiendo")

            if n % GUARDAR_CADA == 0:
                guardar_cache(resultados)

    barra(total, total, inicio, "corrigiendo")
    fin_barra()
    guardar_cache(resultados)
    print(f"  correccion terminada en {(time.time()-inicio)/60:.1f} min")
    return resultados


def leer_cache():
    """Correcciones guardadas por corridas anteriores."""
    return cache_disco.leer(CACHE_JSON, USAR_CACHE)


def guardar_cache(nuevos):
    """Añade las correcciones nuevas a la caché en disco."""
    cache_disco.guardar(CACHE_JSON, nuevos, USAR_CACHE)


def procesar_bloque(bloque, cache, columna_juicio, normalizar, usar_llm):
    """
    Pasa un bloque de notas por las fases 2 a 5 y devuelve (conservadas,
    descartadas).

    Es el cuerpo que antes vivia suelto en main() recorriendo el DataFrame
    entero. Los diccionarios y modelos NO se cargan aqui: eso pasa una sola vez
    antes del bucle, porque cargarlos por bloque multiplicaria el arranque.
    """
    # ---- fase 2: correccion ortografica -------------------------------
    vistos, pendientes = set(), []
    for clave, limpio, original in zip(bloque["clave"], bloque["texto_limpio"],
                                       bloque["texto_norm"]):
        if not limpio or clave in cache or clave in vistos:
            continue
        vistos.add(clave)
        pendientes.append((clave, limpio, original))

    if pendientes:
        cache.update(corregir_lote(pendientes))
    else:
        print("  fase 2: todo estaba en cache")

    bloque["texto_corregido"] = [
        cache.get(c, l) for c, l in zip(bloque["clave"], bloque["texto_limpio"])
    ]
    bloque["texto_original"] = bloque[COLUMNA].astype(str)

    # ---- fase 2b: coherencia contra la nota original ------------------
    #
    # Deshace las correcciones que no se sostienen al compararlas con lo que
    # habia escrito. terminologia.py ya veto lo que se ve mirando dos palabras;
    # esta capa ve la nota, que es donde esta la evidencia del resto.
    #
    # VA FUERA DE LA CACHE A PROPOSITO
    #     La cache guarda lo que devolvio el corrector, que es caro de calcular.
    #     Esto cuesta 2,6 ms por nota, asi que no compensa guardarlo, y ademas
    #     interesa que se vuelva a aplicar entero cuando cambien el lexico de
    #     capitalizacion o los diccionarios: una cache lo congelaria.
    if REVISAR_COHERENCIA:
        revisados, incidencias = [], []
        for limpio, corregido, original in zip(bloque["texto_limpio"],
                                               bloque["texto_corregido"],
                                               bloque["texto_original"]):
            texto, incid = coherencia.revisar(limpio, corregido, original)
            revisados.append(texto)
            incidencias.extend(incid)
        bloque["texto_corregido"] = revisados
        if incidencias:
            _INCIDENCIAS.extend(incidencias)

    # ---- fase 3: normalizacion ----------------------------------------
    if normalizar:
        bloque["texto_normalizado"] = bloque["texto_corregido"].map(
            normalizacion.normalizar)

    # ---- fase 4: senalar las notas sin contenido clinico ---------------
    #
    # SENALA, NO ELIMINA, Y ESA ES LA DECISION IMPORTANTE.
    #
    # Antes esta fase sacaba del CSV las notas que no parecian decir nada del
    # paciente. El problema aparecio al mirar lo que tiraba: junto al tramite
    # administrativo real caian motivos de consulta legitimos como 'tengo
    # epigastralgia desde hace 3 dias', porque ese termino solo vive en la
    # fuente biomedica del lexico y la depuracion no la cuenta como evidencia.
    #
    # Un falso descarte es irrecuperable: la nota desaparece del CSV y con ella
    # del embedding, de los clusters y del analisis. Un falso senalamiento no
    # cuesta nada: la nota sigue entera, se puede vectorizar, y la marca queda
    # en motivo_descarte para revisarla y corregir el diccionario.
    #
    # Lo unico que cambia para una nota senalada es que la fase 5 no le busca
    # un motivo de consulta. No es lo mismo tirar la nota que no inventarle un
    # contexto importante donde no lo hay.
    if DEPURAR:
        veredictos = [depuracion.evaluar(t) for t in bloque[columna_juicio]]
        bloque["util"] = [u for u, _m in veredictos]
        bloque["motivo_descarte"] = [m for _u, m in veredictos]
    else:
        bloque["util"] = True
        bloque["motivo_descarte"] = ""

    # El registro aparte se mantiene: es la lista corta que se revisa para
    # decidir que terminos le faltan al diccionario. Pero ya no es una lista de
    # bajas, sino un indice de lo senalado -- esas notas TAMBIEN van al CSV.
    senaladas = bloque[~bloque["util"]].copy()
    conservadas = bloque.copy()

    # ---- fase 5: reduccion al motivo de consulta ----------------------
    #
    # EL MODELO VE TODAS LAS NOTAS, Y DICTAMINA ADEMAS DE RECORTAR.
    #
    # Antes solo veia las largas y su unico trabajo era recortar. Ahora hace
    # dos cosas, y la segunda es la que obliga a ensenarselas todas: decir si
    # la nota TIENE un motivo de consulta.
    #
    # Ese dictamen es lo que separa dos casos que en el CSV se ven identicos.
    # Una nota puede acabar con texto_embedding igual al normalizado porque es
    # corta y no habia nada que recortar ('tiene fiebre'), o porque el modelo
    # la leyo entera y concluyo que no dice por que vino el paciente. La
    # primera es dato bueno; la segunda es la que hay que revisar. Sin
    # preguntarle a las cortas, las dos quedan mezcladas.
    if REDUCIR:
        textos, marcas, inicio, n = [], [], time.time(), 0
        total_llm = len(conservadas) if usar_llm else 0

        for texto in conservadas[columna_juicio]:
            texto = str(texto)
            reducido = reduccion.recortar(texto)
            marca = ""

            if usar_llm:
                n += 1
                info = extractor.extraer(texto, detalle=True, referencia=reducido)

                if info["estado"] == extractor.ESTADO_SIN_CONTEXTO:
                    # El modelo opino, y su respuesta fue que no hay nada que
                    # extraer. La nota se deja EXACTAMENTE como llego -- ni el
                    # recorte por reglas la toca -- y se anota en el control.
                    reducido = texto
                    marca = MOTIVO_SIN_CONTEXTO
                elif info["motivo"]:
                    reducido = info["motivo"]
                # Cualquier otro estado es un fallo del modelo (no respondio, se
                # invento el texto, devolvio la nota entera). Ahi manda el
                # recorte por reglas, que es lo que ya estaba en 'reducido'.

                if n % 5 == 0 or n == total_llm:
                    barra(n, total_llm, inicio, "extrayendo")

            # Nunca None ni vacio: un fallo del modelo no puede borrar una nota.
            textos.append(reducido or texto)
            marcas.append(marca)

        if usar_llm and total_llm:
            barra(total_llm, total_llm, inicio, "extrayendo")
            fin_barra()
        conservadas["texto_embedding"] = textos
        conservadas["motivo_llm"] = marcas
    else:
        conservadas["motivo_llm"] = ""

    # ---- el archivo de control -----------------------------------------
    #
    # Recoge las dos fuentes de senalamiento y CONSERVA cual fue cual, que es
    # justo lo que se quiere poder distinguir despues:
    #
    #     depuracion  la nota no tiene terminologia clinica reconocible
    #     modelo      el modelo la leyo y no encontro motivo de consulta
    #
    # Si coinciden, se guardan los dos motivos separados por '|'. Ninguna de
    # las dos saca la nota del CSV: todas se vectorizan igual.
    conservadas["motivo_descarte"] = [
        " | ".join(m for m in (depurada, llm) if m)
        for depurada, llm in zip(conservadas["motivo_descarte"], conservadas["motivo_llm"])
    ]
    senaladas = conservadas[conservadas["motivo_descarte"] != ""].copy()

    return conservadas, senaladas


# ==========================================================
# MAIN
# ==========================================================

def main():
    """
    Ejecuta la corrida completa: carga diccionarios y léxicos, descarga los
    registros, aplica las tres fases, escribe el CSV y el reporte de cambios, y
    resume por pantalla lo que hay que revisar.
    """
    terminologia.alarmas.reiniciar()  # E2.0: sin esto, dos corridas en el mismo proceso acumulan
    global LIMITE_REGISTROS, USAR_LLM

    ap = argparse.ArgumentParser(description="Fases 1-5 del pipeline de triage.")
    ap.add_argument("--limite", type=int, default=None,
                    help="cuantas notas procesar (por defecto, LIMITE_REGISTROS)")
    ap.add_argument("--sin-llm", action="store_true",
                    help="no usar el modelo de Ollama para el texto de embedding")
    ap.add_argument("--rehacer", action="store_true",
                    help="aparta el CSV anterior y procesa todo desde cero")
    args = ap.parse_args()
    if args.limite:
        LIMITE_REGISTROS = args.limite
    if args.sin_llm:
        USAR_LLM = False

    # ANTES DE NADA: QUE ESTEN LOS ARTEFACTOS QUE ESTO DA POR HECHOS.
    #
    # Va aqui, y no mas abajo, porque el dano que evita no se ve en ningun
    # sitio despues. Sin lexico_clinico.json la fase 5 descarta toda oracion
    # larga y el CSV sale entero, con todas sus filas y todas sus columnas
    # llenas: nada aguas abajo puede notar que le falta el motivo de consulta.
    # Ver NLP/nucleo/requisitos.py para la lista y lo que rompe cada uno.
    requisitos.exigir()

    print(f"Registros a procesar: {LIMITE_REGISTROS or 'todos'} | "
          f"LLM: {'si' if USAR_LLM else 'no'}")
    print("Conectando BD...")
    from NLP.nucleo.conexion_bd import obtener_engine
    engine = obtener_engine()

    filtro = f"{COLUMNA} IS NOT NULL AND LTRIM(RTRIM({COLUMNA})) <> ''"

    print("Cargando diccionarios...")
    ortografia.cargar_siglas()

    # el lexico clinico decide que palabras NO llegan al corrector; se genera
    # aparte porque extraerlo del modelo biomedico es lento y no cambia entre
    # corridas
    ortografia.cargar_lexico_clinico()

    # el lexico de capitalizacion devuelve la proteccion a las notas gritadas,
    # que son la mayoria del corpus: sin el, las defensas que dependen del
    # contraste de mayusculas quedan desactivadas
    aprendidas = casing.cargar()
    if aprendidas:
        print(f"  {aprendidas:,} tokens con capitalizacion aprendida "
              f"({len(casing.siglas()):,} siglas, "
              f"{len(casing.nombres_propios()):,} nombres propios)")
    else:
        print("  AVISO: falta lexico_casing.json. Corre antes: python -m NLP.recursos.casing")
    print(f"  {len(reglas.SIGLAS):,} siglas ({len(reglas.EXPANDIBLES):,} expandibles) | "
          f"{len(reglas.DIRECTAS):,} correcciones directas | "
          f"{len(reglas.PATRONES)} patrones")

    if NORMALIZAR:
        entradas = normalizacion.cargar()
        print(f"  {entradas:,} expresiones de normalizacion (modo {normalizacion.MODO})")

    # ------------------------------------------------------------------
    # QUE SE VA A ESCRIBIR Y QUE ESTA ESCRITO YA -- LAS DOS COSAS ANTES DE
    # BAJAR NADA.
    #
    # Esto se decidia mas abajo, DESPUES de la descarga, y ese orden era justo
    # lo que rompia --limite: no se le puede pedir "2.000 notas nuevas" a la
    # base de datos si todavia no se sabe cuales estan hechas. Aqui se resuelve
    # primero que columnas lleva el CSV (de eso depende si el archivo anterior
    # sirve o hay que rotarlo), luego si se continua o se empieza de cero, y
    # solo entonces se leen los OID ya escritos para pasarselos a la consulta.
    # ------------------------------------------------------------------
    normalizar = NORMALIZAR and normalizacion.disponible()
    columnas = [LLAVE, "texto_original", "texto_corregido"]
    if normalizar:
        columnas.append("texto_normalizado")
    if REDUCIR:
        columnas.append("texto_embedding")

    # Fase 4: el juicio se hace sobre el texto normalizado siempre que exista.
    # Preguntar 'esta nota tiene terminologia clinica' sobre el texto sin
    # normalizar mide el diccionario, no la nota: 'me cai' y 'tengo gripa' dan
    # cero terminos hasta que la fase 3 los traduce.
    columna_juicio = "texto_normalizado" if normalizar else "texto_corregido"
    columnas_descarte = [LLAVE, "texto_original", columna_juicio,
                         "motivo_descarte"]

    # ------------------------------------------------------------------
    # Relanzar CONTINUA el CSV; no lo rehace.
    #
    # Antes cada corrida rotaba el archivo y empezaba por el bloque 1, y con
    # una tabla que se procesa a razon de un bloque cada media hora eso
    # significaba que interrumpir para revisar algo costaba todo lo andado.
    # Ahora se leen los OID que ya estan escritos, la consulta los salta, y lo
    # nuevo se anade al final.
    #
    # Es lo mismo que ya hacia embedding/: la corrida barata es la que no
    # repite trabajo. Para empezar de cero a proposito esta --rehacer.
    # ------------------------------------------------------------------
    reanudar = not args.rehacer

    if args.rehacer:
        anterior = rotar(OUTPUT_CSV)
        rotar(DESCARTADAS_CSV)
        if anterior:
            print(f"  --rehacer: version anterior apartada en {anterior.name}")
    elif not cabecera_compatible(OUTPUT_CSV, columnas) and OUTPUT_CSV.exists():
        anterior = rotar(OUTPUT_CSV)
        rotar(DESCARTADAS_CSV)
        reanudar = False
        print(f"  el CSV anterior tenia otras columnas; apartado en {anterior.name}")

    # Solo el CSV principal: desde que la fase 4 senala en vez de eliminar,
    # TODAS las notas procesadas acaban ahi. notas_descartadas.csv es un indice
    # de lo senalado, no una lista de bajas, asi que sus OID estan tambien en el
    # CSV y mirarlo seria redundante.
    hechas = llaves_escritas(OUTPUT_CSV) if reanudar else set()
    if hechas:
        print(f"  ya limpias de corridas anteriores: {len(hechas):,} notas "
              f"(la consulta las salta)")

    cargar_corpus(engine, filtro)
    df = cargar_registros(engine, filtro, excluir=hechas)
    if df.empty:
        print("\nNo quedan notas nuevas: la tabla entera esta limpia. "
              "Para rehacerla desde cero usa --rehacer.")
        return

    df = preparar(df)

    vacios = df["texto_limpio"].map(es_vacio)
    if vacios.any():
        print(f"  {vacios.sum():,} notas sin contenido util (se conservan sin corregir)")

    cache = leer_cache()

    # ------------------------------------------------------------------
    # Preparativos de las fases 3 a 5.
    #
    # Van AQUI y no dentro del bucle: cargar los lexicos, indexar las raices
    # clinicas y comprobar el modelo cuesta lo mismo para 250 notas que para
    # 5.000, asi que hacerlo por bloque multiplicaria el arranque por el numero
    # de bloques.
    # ------------------------------------------------------------------
    # El CSV conserva sus columnas de siempre. Que notas senalo la fase 4 se
    # sabe cruzando por OID contra notas_descartadas.csv, que sigue siendo el
    # archivo de control.
    #
    # No sirve deducirlo comparando texto_normalizado con texto_embedding:
    # sobre las primeras 1.293 notas el 60% ya salian iguales por ser cortas y
    # no tener nada que recortar ('tiene fiebre', 'tengo dolor'). Esa igualdad
    # mezclaria 776 notas sanas con el centenar senalado; el cruce por OID da
    # la lista exacta.

    if DEPURAR:
        print(f"Fase 4: {depuracion.cargar():,} raices clinicas indexadas")

    # ------------------------------------------------------------------
    # Fase 5: SON DOS TEXTOS DISTINTOS Y HACEN FALTA LOS DOS.
    #
    #   texto_normalizado  la nota entera, corregida y con la terminologia
    #                      anotada. Conserva el contexto -- 'tengo fiebre hace
    #                      3 dias' -- y es lo que se lee cuando hay que
    #                      entender un caso o auditar una decision.
    #   texto_embedding    solo por que vino el paciente. Sin antecedentes, sin
    #                      examen fisico, sin conducta, sin tramite y sin
    #                      preambulo temporal.
    #
    # La diferencia no es de limpieza sino de proposito. El objetivo del
    # proyecto es cruzar motivos de consulta con factores externos, no
    # diagnosticar: para eso, 'hace 3 dias' es precision que no se usa y que
    # separa dos notas que describen lo mismo.
    # ------------------------------------------------------------------
    usar_llm = False
    if REDUCIR:
        print("Fase 5: reduccion al motivo de consulta")
        reduccion.cargar_lexico()
        reduccion.cargar_lugares()

        # EL MODELO SOLO VE LAS NOTAS LARGAS, Y ESA ES LA DECISION DE COSTE.
        #
        # La mediana del corpus son 6 palabras ('dolor abdominal'): ahi no hay
        # nada que extraer y las reglas aciertan en decimas de milisegundo. El
        # modelo tarda del orden de 8 s por nota en esta maquina, asi que
        # pasarle las 28.000 serian mas de 60 horas y pasarle solo las largas,
        # unas pocas. Si el modelo no esta disponible, recortan las reglas y el
        # resultado sigue siendo valido.
        usar_llm = USAR_LLM and extractor.disponible()
        if usar_llm:
            print(f"  extractor: {extractor.MODELO} (todas las notas)")

    # ------------------------------------------------------------------
    # El bucle de bloques. Cada vuelta deja notas TERMINADAS en el CSV, no a
    # medio procesar: un bloque pasa por las fases 2 a 5 completas antes de
    # escribirse. Por eso el archivo se puede leer mientras la corrida sigue.
    # ------------------------------------------------------------------
    escritor = EscritorCSV(OUTPUT_CSV, columnas, reanudar=reanudar)
    escritor_descartes = EscritorCSV(DESCARTADAS_CSV, columnas_descarte,
                                     reanudar=reanudar)

    bloques = [df.iloc[k:k + BLOQUE_ESCRITURA]
               for k in range(0, len(df), BLOQUE_ESCRITURA)]
    hechos_ok, hechos_no = [], []

    print(f"\n{len(df):,} notas en {len(bloques)} bloques de {BLOQUE_ESCRITURA}")
    print(f"Cada bloque se escribe al terminar: puedes abrir {OUTPUT_CSV.name} "
          f"mientras corre.\n")

    interrumpido = False
    try:
        for numero, trozo in enumerate(bloques, 1):
            desde = (numero - 1) * BLOQUE_ESCRITURA + 1
            print(f"--- bloque {numero}/{len(bloques)}  "
                  f"(notas {desde:,}-{desde + len(trozo) - 1:,}) ---")
            ok, no = procesar_bloque(trozo.copy(), cache, columna_juicio,
                                     normalizar, usar_llm)
            escritor.agregar(ok)
            escritor_descartes.agregar(no)
            hechos_ok.append(ok)
            hechos_no.append(no)
            print(f"  +{len(ok):,} notas -> {OUTPUT_CSV.name} "
                  f"(acumulado {escritor.filas:,})")
            if len(no):
                print(f"  {len(no):,} senaladas sin contenido clinico "
                      f"(van al CSV sin reducir)")
    except KeyboardInterrupt:
        # Cortar a mano es una forma legitima de parar una corrida larga: lo ya
        # escrito es valido y la cache conserva lo corregido, asi que relanzar
        # sigue por donde iba en vez de empezar de cero.
        interrumpido = True
        fin_barra()
        print("\n\nInterrumpido a mano. Lo escrito hasta aqui es valido.")
    finally:
        escritor.cerrar()
        escritor_descartes.cerrar()

    if not hechos_ok:
        print("No se proceso ninguna nota.")
        return

    conservadas = pd.concat(hechos_ok).sort_index()
    descartadas = pd.concat(hechos_no).sort_index()

    # El resumen habla de lo que SE PROCESO, que con una interrupcion no es
    # todo lo que se descargo de la base.
    #
    # Desde que la fase 4 senala en vez de eliminar, 'conservadas' YA son todas
    # las notas del bloque y 'descartadas' es un subconjunto suyo, no un grupo
    # aparte. Concatenarlas contaria dos veces cada nota senalada y falsearia
    # todos los porcentajes de aqui abajo.
    df = conservadas

    print(f"\n{escritor.agregadas:,} notas nuevas | {escritor.filas:,} en total "
          f"en {OUTPUT_CSV.name}")
    if interrumpido:
        print(f"Sin procesar: {len(bloques) * BLOQUE_ESCRITURA - len(df):,} notas aprox.")
        print("Relanza cuando quieras: la cache evita repetir lo ya corregido.")

    # La auditoria mide lo que se conservo, que es lo que sale del pipeline.
    filas = auditoria.escribir_reporte(conservadas, REPORTE_CSV, columnas)
    modificados = (conservadas["texto_limpio"] != conservadas["texto_corregido"]).sum()

    # Correcciones sospechosas de haber estropeado la nota. A diferencia de las
    # otras dos varas del proyecto, esta no necesita que nadie haya anotado el
    # caso antes: reconoce la FORMA del dano, no la palabra concreta. Es lo que
    # habria delatado 'afiliados' -> 'afilia dos' y 'dorada' -> 'morada' en la
    # misma corrida que los produjo, en vez de dos semanas despues.
    sospechosas = auditoria.dano_probable(filas)
    if sospechosas:
        print(f"\nCorrecciones sospechosas de estropear la nota: {len(sospechosas):,} "
              f"de {len(filas):,} sustituciones")
        print("  Revisa estas antes de dar la corrida por buena. Si alguna es")
        print("  legitima, lo que falta es una entrada en el diccionario.")
        for motivo, orig, reemp, veces, oid in sospechosas[:15]:
            print(f"  {veces:5}  [{motivo:34}] {orig} -> {reemp}  (OID {oid})")

    if _INCIDENCIAS:
        conteo = {}
        for orig, reemp, motivo in _INCIDENCIAS:
            conteo[(motivo, orig, reemp)] = conteo.get((motivo, orig, reemp), 0) + 1
        print(f"\nCorrecciones deshechas por incoherentes con la nota: "
              f"{len(_INCIDENCIAS):,} en {len(conteo):,} formas distintas")
        print("  Son cambios que ya habian pasado el guardian clinico y que al")
        print("  compararlos con la nota original no se sostienen.")
        for (motivo, orig, reemp), veces in sorted(conteo.items(),
                                                   key=lambda x: -x[1])[:15]:
            print(f"  {veces:5}  [{motivo:36}] {orig} -> {reemp}")

    alarmas = terminologia.resumen_alarmas()
    if alarmas:
        print("\nCorrecciones frenadas por el guardian clinico:")
        for motivo, veces, ejemplo in alarmas:
            print(f"  {veces:6}  {motivo:32} ej: {ejemplo}")

    abstenciones = terminologia.resumen_abstenciones(minimo=3)
    if abstenciones:
        print("\nPalabras dejadas intactas por falta de evidencia (top 20):")
        print("  Revisa si alguna es sigla, farmaco o termino y llevala al diccionario.")
        for palabra, veces, motivo in abstenciones[:20]:
            print(f"  {veces:6}  {palabra:24} {motivo}")

    print(f"\n{'='*60}")
    motivos = depuracion.resumen(df["motivo_descarte"])
    if motivos:
        n = len(descartadas)
        print(f"Notas senaladas sin contenido clinico: "
              f"{n:,} de {len(df):,} ({n/len(df)*100:.1f}%)")
        print(f"  Siguen en el CSV, sin reducir. El motivo de cada una esta "
              f"en {DESCARTADAS_CSV.name}.")
        for motivo, veces in motivos:
            print(f"  {veces:6}  {motivo}")
        print(f"  Revisa {DESCARTADAS_CSV.name}: una expresion clinica repetida ahi")
        print(f"  no es ruido, es una entrada que le falta al diccionario.\n")

    print(f"Notas modificadas: {modificados:,} de {len(conservadas):,} "
          f"({modificados/max(len(conservadas), 1)*100:.1f}%)")
    print(f"Sustituciones distintas: {len(filas):,}")
    print(f"\nTop 15 (revisar que no haya terminos clinicos):")
    for fase, o, r, n, _oid in filas[:15]:
        print(f"  {n:5}  [{fase:13}] {o} -> {r}")

    print(f"\nEstadisticas de limpieza: {analizar(df[COLUMNA].head(2000))}")
    print(f"\nCSV: {OUTPUT_CSV}  ({len(conservadas):,} notas)")
    print(f"Reporte: {REPORTE_CSV}")
    if not descartadas.empty:
        print(f"Senaladas: {DESCARTADAS_CSV}  ({len(descartadas):,} notas, "
              f"tambien presentes en el CSV)")


if __name__ == "__main__":
    main()
