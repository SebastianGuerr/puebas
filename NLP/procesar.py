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
import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from NLP import rutas
from NLP.depuracion import depuracion
from NLP.evaluacion import auditoria
from NLP.fase1_limpieza.limpieza import analizar, es_vacio, limpiar_conservando_original
from NLP.fase2_ortografia import ortografia, terminologia
from NLP.fase3_normalizacion import normalizacion
from NLP.nucleo import reglas
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

# Fase 4: saca del CSV las notas que no dicen nada del paciente. Las descartadas
# se escriben con su motivo en salidas/notas_descartadas.csv, de modo que
# ponerlo en False no informa de mas: da el mismo CSV sin filtrar.
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
VERSION_CORRECTOR = "3-contexto-por-suma"



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
    df = pd.read_sql(
        f"SELECT TOP {LIMITE_LEXICO} {COLUMNA} FROM {TABLA} WHERE {filtro}", engine
    )
    conteo = ortografia.construir_lexico(df[COLUMNA])
    print(f"  {len(conteo):,} palabras distintas sobre {len(df):,} notas")


def cargar_registros(engine, filtro):
    """
    Descarga los registros que se van a procesar. Con LIMITE_REGISTROS activo la
    selección se reparte por toda la tabla, para que la muestra no se concentre
    en un periodo.

    EL ORDEN ES PSEUDOALEATORIO PERO REPETIBLE, Y ESO IMPORTA MUCHO.
        Antes esto era ORDER BY NEWID(), que sortea una muestra distinta en cada
        corrida. Suena inofensivo hasta que se cruza con la caché: la caché
        guarda la corrección de cada TEXTO, así que si la corrida siguiente trae
        otras 5.000 notas, casi nada coincide y se vuelve a pagar el trabajo
        entero.

        Pasó el 9 de septiembre: una corrida dejó 4.234 textos corregidos tras
        horas de trabajo, y relanzarla habría reaprovechado una fracción mínima.

        HASHBYTES sobre la llave da el mismo reparto disperso pero SIEMPRE el
        mismo, así que repetir una corrida es casi gratis y subir el límite
        conserva la muestra anterior y solo añade notas nuevas.
    """
    print("Descargando registros...")
    top = f"TOP {LIMITE_REGISTROS}" if LIMITE_REGISTROS else ""
    orden = (f"ORDER BY HASHBYTES('MD5', CAST({LLAVE} AS varchar(20)))"
             if (LIMITE_REGISTROS and MUESTREO_ALEATORIO) else "")
    df = pd.read_sql(
        f"SELECT {top} {LLAVE}, {COLUMNA} FROM {TABLA} WHERE {filtro} {orden}", engine
    )
    print(f"  {len(df):,} registros")
    return df


# ==========================================================
# PROGRESO
# ==========================================================

ANCHO_BARRA = 34


def barra(hechos, total, inicio, etiqueta=""):
    """
    Escribe una barra de progreso en la misma linea, con porcentaje, ritmo y
    tiempo restante estimado.

    Se reescribe la misma linea con un retorno de carro, en vez de saltar de
    linea, para no llenar la terminal de miles de lineas en una corrida larga.
    Al terminar, quien llama la cierra con fin_barra().
    """
    total = max(total, 1)
    fraccion = hechos / total
    lleno = int(ANCHO_BARRA * fraccion)
    transcurrido = time.time() - inicio
    ritmo = hechos / transcurrido if transcurrido > 0 else 0
    falta = (total - hechos) / ritmo if ritmo > 0 else 0
    sys.stdout.write(
        f"\r  [{'#' * lleno}{'.' * (ANCHO_BARRA - lleno)}] {fraccion * 100:5.1f}% "
        f"{hechos:,}/{total:,} | {transcurrido / 60:.1f} min | "
        f"faltan ~{falta / 60:.1f} min | {ritmo:.1f}/s {etiqueta}   ")
    sys.stdout.flush()


def fin_barra():
    """Cierra la linea de la barra."""
    sys.stdout.write("\n")
    sys.stdout.flush()


# ==========================================================
# SALIDA
# ==========================================================

def rotar(ruta, conservar=3):
    """
    Aparta la version anterior de un archivo antes de escribir la nueva, y
    devuelve a donde se movio (o None si no habia nada que apartar).

    POR QUE EXISTE
        Antes se sobrescribia. Una corrida nueva borraba la anterior sin dejar
        rastro, de modo que comparar dos versiones del pipeline obligaba a
        acordarse de copiar el CSV a mano ANTES de lanzar, y quien no se
        acordaba perdia la referencia.

        Y al reves: si alguien renombraba el archivo para guardarlo, cualquier
        script que lo diera por existente fallaba. Un artefacto generado no
        puede ser una precondicion; si no esta, se crea.

    Se guardan las ultimas `conservar` versiones con la fecha en el nombre y se
    borran las mas viejas, para que salidas/ no crezca sin limite.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return None

    # La marca tiene resolucion de segundo, asi que dos rotaciones seguidas
    # chocan. En Windows renombrar sobre un archivo existente lanza
    # FileExistsError en vez de sobrescribir, de modo que sin el contador la
    # segunda rotacion aborta la corrida entera. Lo destapo la prueba de la
    # propia funcion, no el corpus.
    marca = time.strftime("%Y%m%d-%H%M%S")
    destino = ruta.with_name(f"{ruta.stem}_{marca}{ruta.suffix}")
    n = 2
    while destino.exists():
        destino = ruta.with_name(f"{ruta.stem}_{marca}-{n}{ruta.suffix}")
        n += 1
    ruta.rename(destino)

    previas = sorted(ruta.parent.glob(f"{ruta.stem}_*{ruta.suffix}"), reverse=True)
    for vieja in previas[conservar:]:
        try:
            vieja.unlink()
        except OSError:
            pass
    return destino


# ==========================================================
# PROCESAMIENTO
# ==========================================================

def clave_cache(texto_limpio, protegidos):
    """
    Clave de caché de una nota.

    Incluye tres cosas, y las tres son necesarias: el texto ya limpio, los
    tokens protegidos y la versión del corrector. Los protegidos entran porque
    una misma nota limpia puede corregirse de forma distinta según las
    mayúsculas del original, y la versión porque una caché de un corrector
    anterior contaminaría la corrida.
    """
    base = texto_limpio
    if protegidos:
        base = texto_limpio + "\x00" + ",".join(sorted(protegidos))
    # la version entra en la clave: al cambiar el corrector, la cache vieja deja
    # de aplicar sola en vez de contaminar la corrida con decisiones anteriores
    return VERSION_CORRECTOR + "\x00" + base


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
    """Lee la caché de correcciones. Devuelve {} si está desactivada o ilegible."""
    if not USAR_CACHE or not CACHE_JSON.exists():
        return {}
    try:
        cache = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
        print(f"Cache previa: {len(cache):,} textos")
        return cache
    except Exception:
        print("Cache ilegible, se ignora")
        return {}


def guardar_cache(nuevos):
    """
    Añade las correcciones nuevas a la caché en disco, releyendo antes lo que ya
    hubiera para no perder lo guardado por una corrida anterior.
    """
    if not USAR_CACHE:
        return
    cache = {}
    if CACHE_JSON.exists():
        try:
            cache = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
        except Exception:
            cache = {}
    cache.update(nuevos)
    CACHE_JSON.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")


# ==========================================================
# ESCRITURA INCREMENTAL
# ==========================================================

def cabecera_compatible(ruta, columnas):
    """
    Dice si un CSV existente se puede seguir llenando con estas columnas.

    Se compara la cabecera y no solo la existencia del archivo porque la lista
    de columnas depende de la configuracion: apagar REDUCIR quita
    texto_embedding, y apagar NORMALIZAR quita texto_normalizado. Apendar filas
    de cinco campos a un archivo de cuatro produce un CSV que no puede leer
    nadie, asi que ante cualquier diferencia se prefiere rotar y empezar limpio.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return False
    try:
        with open(ruta, "r", newline="", encoding="utf-8-sig") as archivo:
            cabecera = next(csv.reader(archivo), None)
    except OSError:
        return False
    return cabecera == list(columnas)


def contar_filas(ruta):
    """Filas de datos de un CSV, sin contar la cabecera."""
    with open(ruta, "r", newline="", encoding="utf-8-sig") as archivo:
        return max(sum(1 for _ in csv.reader(archivo)) - 1, 0)


def llaves_escritas(*rutas):
    """
    Los OID que ya paso el pipeline en corridas anteriores.

    Mira tanto el CSV de salida como el de descartadas, y esa segunda parte es
    la que se olvida: una nota que se tiro por no tener contenido clinico ESTA
    procesada. Si solo se miraran las conservadas, cada relanzamiento volveria a
    corregir y a pasar por el modelo las mismas notas descartadas, que son
    justo las que menos valor tienen.
    """
    hechas = set()
    for ruta in rutas:
        ruta = Path(ruta)
        if not ruta.exists():
            continue
        try:
            columna = pd.read_csv(ruta, encoding="utf-8-sig", usecols=[LLAVE])
        except (ValueError, OSError, pd.errors.EmptyDataError):
            continue
        hechas.update(columna[LLAVE].dropna().astype("int64").tolist())
    return hechas


class EscritorCSV:
    """
    Un CSV que se va llenando mientras la corrida avanza.

    Abre el archivo en la primera escritura, pone la cabecera y desde ahi solo
    anade filas, vaciando el buffer despues de cada bloque para que otro proceso
    pueda leer lo que va saliendo sin esperar a que la corrida termine.

    Usa las mismas opciones que el to_csv de antes -- utf-8-sig y comillas en
    todos los campos -- para que el archivo sea identico al de siempre.
    """

    def __init__(self, ruta, columnas, reanudar=False):
        self.ruta = Path(ruta)
        self.columnas = list(columnas)
        self.previas = 0        # filas que ya estaban en el archivo
        self.agregadas = 0      # filas que ha escrito ESTA corrida

        if reanudar and cabecera_compatible(self.ruta, self.columnas):
            # Continuar el archivo que ya habia. Se abre en modo "a" y con
            # utf-8 A SECAS, no utf-8-sig: la marca BOM va una sola vez al
            # principio del archivo y ya esta puesta. Anadirla otra vez
            # intercalaria tres bytes basura en mitad de los datos.
            self.previas = contar_filas(self.ruta)
            self._archivo = open(self.ruta, "a", newline="", encoding="utf-8")
            self._escritor = csv.writer(self._archivo, quoting=csv.QUOTE_ALL)
        else:
            # El archivo se crea YA, con su cabecera, aunque todavia no haya
            # filas. Dejar la creacion para el primer bloque abre una ventana de
            # varios minutos en la que triage_limpio.csv sencillamente NO
            # EXISTE, y una corrida cortada ahi deja al paso siguiente sin
            # archivo que leer -- con un FileNotFoundError que no explica nada
            # -- en vez de con uno vacio pero valido.
            self._archivo = open(self.ruta, "w", newline="", encoding="utf-8-sig")
            self._escritor = csv.writer(self._archivo, quoting=csv.QUOTE_ALL)
            self._escritor.writerow(self.columnas)
            self._archivo.flush()

    @property
    def filas(self):
        """Total de filas en el archivo, contando las de corridas anteriores."""
        return self.previas + self.agregadas

    def agregar(self, df):
        """Anade las filas de un bloque y las baja a disco."""
        if df is None or df.empty:
            return
        # fillna: csv.writer escribiria 'nan' donde to_csv dejaba el campo vacio
        for fila in df[self.columnas].fillna("").itertuples(index=False, name=None):
            self._escritor.writerow(fila)
        self._archivo.flush()
        self.agregadas += len(df)

    def cerrar(self):
        if self._archivo is not None:
            self._archivo.close()
            self._archivo = None


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

    # ---- fase 3: normalizacion ----------------------------------------
    if normalizar:
        bloque["texto_normalizado"] = bloque["texto_corregido"].map(
            normalizacion.normalizar)

    # ---- fase 4: depuracion -------------------------------------------
    if DEPURAR:
        veredictos = [depuracion.evaluar(t) for t in bloque[columna_juicio]]
        bloque["util"] = [u for u, _m in veredictos]
        bloque["motivo_descarte"] = [m for _u, m in veredictos]
    else:
        bloque["util"] = True
        bloque["motivo_descarte"] = ""

    descartadas = bloque[~bloque["util"]].copy()
    conservadas = bloque[bloque["util"]].copy()

    # ---- fase 5: reduccion al motivo de consulta ----------------------
    if REDUCIR:
        textos, inicio, n = [], time.time(), 0
        largas = sum(1 for t in conservadas[columna_juicio]
                     if len(str(t).split()) >= extractor.LONGITUD_MINIMA) if usar_llm else 0

        for texto in conservadas[columna_juicio]:
            reducido = reduccion.recortar(texto)
            if usar_llm and len(str(texto).split()) >= extractor.LONGITUD_MINIMA:
                n += 1
                # si el modelo no encuentra nada o se inventa algo, se queda el
                # recorte por reglas; y si ese tampoco redujo, la nota tal cual.
                # Nunca None ni vacio: un fallo del modelo no puede borrar una nota
                reducido = extractor.extraer(texto, referencia=reducido) or reducido or str(texto)
                if n % 5 == 0 or n == largas:
                    barra(n, largas, inicio, "extrayendo")
            textos.append(reducido)
        if usar_llm and largas:
            barra(largas, largas, inicio, "extrayendo")
            fin_barra()
        conservadas["texto_embedding"] = textos

    return conservadas, descartadas


# ==========================================================
# MAIN
# ==========================================================

def main():
    """
    Ejecuta la corrida completa: carga diccionarios y léxicos, descarga los
    registros, aplica las tres fases, escribe el CSV y el reporte de cambios, y
    resume por pantalla lo que hay que revisar.
    """
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

    cargar_corpus(engine, filtro)
    df = cargar_registros(engine, filtro)
    if df.empty:
        print("No hay registros.")
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
    normalizar = NORMALIZAR and normalizacion.disponible()
    columnas = [LLAVE, "texto_original", "texto_corregido"]
    if normalizar:
        columnas.append("texto_normalizado")

    # Fase 4: el juicio se hace sobre el texto normalizado siempre que exista.
    # Preguntar 'esta nota tiene terminologia clinica' sobre el texto sin
    # normalizar mide el diccionario, no la nota: 'me cai' y 'tengo gripa' dan
    # cero terminos hasta que la fase 3 los traduce.
    columna_juicio = "texto_normalizado" if normalizar else "texto_corregido"
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
            print(f"  extractor: {extractor.MODELO} "
                  f"(solo notas de mas de {extractor.LONGITUD_MINIMA} palabras)")
        columnas.append("texto_embedding")

    # ------------------------------------------------------------------
    # El bucle de bloques. Cada vuelta deja notas TERMINADAS en el CSV, no a
    # medio procesar: un bloque pasa por las fases 2 a 5 completas antes de
    # escribirse. Por eso el archivo se puede leer mientras la corrida sigue.
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------
    # Relanzar CONTINUA el CSV; no lo rehace.
    #
    # Antes cada corrida rotaba el archivo y empezaba por el bloque 1, y con
    # una tabla que se procesa a razon de un bloque cada media hora eso
    # significaba que interrumpir para revisar algo costaba todo lo andado.
    # Ahora se leen los OID que ya estan escritos, se saltan, y las notas
    # nuevas se anaden al final.
    #
    # Es lo mismo que ya hacia embedding/: la corrida barata es la que no
    # repite trabajo. Para empezar de cero a proposito esta --rehacer.
    # ------------------------------------------------------------------
    columnas_descarte = [LLAVE, "texto_original", columna_juicio, "motivo_descarte"]
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

    if reanudar:
        hechas = llaves_escritas(OUTPUT_CSV, DESCARTADAS_CSV)
        if hechas:
            antes = len(df)
            df = df[~df[LLAVE].isin(hechas)]
            print(f"  ya procesadas en corridas anteriores: {antes - len(df):,} notas "
                  f"(se saltan)")
            if df.empty:
                print("\nNo hay notas nuevas que procesar. "
                      "Sube --limite o usa --rehacer.")
                return

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
                print(f"  {len(no):,} descartadas por no aportar informacion clinica")
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
    df = pd.concat([conservadas, descartadas]).sort_index()

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
        print(f"Notas descartadas por no aportar informacion clinica: "
              f"{n:,} de {len(df):,} ({n/len(df)*100:.1f}%)")
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
        print(f"Descartadas: {DESCARTADAS_CSV}  ({len(descartadas):,} notas)")


if __name__ == "__main__":
    main()
