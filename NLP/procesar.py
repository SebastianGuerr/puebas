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

import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from NLP import rutas
from NLP.depuracion import depuracion
from NLP.evaluacion import auditoria
from NLP.fase1_limpieza.limpieza import analizar, es_vacio, limpiar_conservando_original
from NLP.fase2_ortografia import ortografia, terminologia
from NLP.fase3_normalizacion import normalizacion
from NLP.nucleo import reglas
from NLP.reduccion import reduccion
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

LIMITE_REGISTROS = 30000    # None = toda la tabla
MUESTREO_ALEATORIO = True
LIMITE_LEXICO = 200000      # registros usados solo para contar frecuencias

N_HILOS = 4
GUARDAR_CADA = 2000
NORMALIZAR = True           # agrega la columna texto_normalizado (fase 3)

# Fase 4: saca del CSV las notas que no dicen nada del paciente. Las descartadas
# se escriben con su motivo en salidas/notas_descartadas.csv, de modo que
# ponerlo en False no informa de mas: da el mismo CSV sin filtrar.
DEPURAR = True

# Fase 5: agrega la columna texto_embedding, la nota reducida a su motivo de
# consulta. Es el texto que consume el modelo de embeddings; texto_normalizado
# sigue estando entero al lado para leer y auditar.
REDUCIR = True

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
    selección es aleatoria, para que la muestra no se concentre en un periodo.
    """
    print("Descargando registros...")
    top = f"TOP {LIMITE_REGISTROS}" if LIMITE_REGISTROS else ""
    orden = "ORDER BY NEWID()" if (LIMITE_REGISTROS and MUESTREO_ALEATORIO) else ""
    df = pd.read_sql(
        f"SELECT {top} {LLAVE}, {COLUMNA} FROM {TABLA} WHERE {filtro} {orden}", engine
    )
    print(f"  {len(df):,} registros")
    return df


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

            if n % 500 == 0:
                t = time.time() - inicio
                print(f"  [{n:,}/{total:,}] {t/60:.1f} min | faltan ~{t/n*(total-n)/60:.1f} min")

            if n % GUARDAR_CADA == 0:
                guardar_cache(resultados)

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
# MAIN
# ==========================================================

def main():
    """
    Ejecuta la corrida completa: carga diccionarios y léxicos, descarga los
    registros, aplica las tres fases, escribe el CSV y el reporte de cambios, y
    resume por pantalla lo que hay que revisar.
    """
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
    vistos = set()
    pendientes = []
    for clave, limpio, original in zip(df["clave"], df["texto_limpio"], df["texto_norm"]):
        if not limpio or clave in cache or clave in vistos:
            continue
        vistos.add(clave)
        pendientes.append((clave, limpio, original))

    print(f"Fase 2: correccion ortografica")
    print(f"  textos unicos por corregir: {len(pendientes):,} "
          f"(de {df['clave'].nunique():,} distintos)")

    cache.update(corregir_lote(pendientes))

    df["texto_corregido"] = [
        cache.get(c, l) for c, l in zip(df["clave"], df["texto_limpio"])
    ]
    df["texto_original"] = df[COLUMNA].astype(str)

    columnas = [LLAVE, "texto_original", "texto_corregido"]
    if NORMALIZAR and normalizacion.disponible():
        print("Fase 3: normalizacion de coloquialismos y siglas...")
        df["texto_normalizado"] = df["texto_corregido"].map(normalizacion.normalizar)
        columnas.append("texto_normalizado")

    # ------------------------------------------------------------------
    # Fase 4: depuracion
    #
    # Va DESPUES de la normalizacion y no antes, y ese orden es el modulo
    # entero. Preguntar 'esta nota tiene terminologia clinica' sobre el texto
    # sin normalizar mide el diccionario, no la nota: 'me cai' y 'tengo gripa'
    # dan cero terminos hasta que la fase 3 los traduce.
    # ------------------------------------------------------------------
    columna_juicio = "texto_normalizado" if "texto_normalizado" in df.columns else "texto_corregido"
    if DEPURAR:
        print("Fase 4: depuracion de notas sin contenido clinico...")
        print(f"  {depuracion.cargar():,} raices clinicas indexadas")
        veredictos = [depuracion.evaluar(t) for t in df[columna_juicio]]
        df["util"] = [u for u, _m in veredictos]
        df["motivo_descarte"] = [m for _u, m in veredictos]
    else:
        df["util"] = True
        df["motivo_descarte"] = ""

    descartadas = df[~df["util"]]
    if not descartadas.empty:
        # Nada se descarta en silencio: el archivo con el motivo de cada nota
        # es lo que permite distinguir el ruido real del hueco de diccionario.
        descartadas[[LLAVE, "texto_original", columna_juicio, "motivo_descarte"]].to_csv(
            DESCARTADAS_CSV, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL
        )

    conservadas = df[df["util"]].copy()

    # ------------------------------------------------------------------
    # Fase 5: reduccion al motivo de consulta
    #
    # SON DOS TEXTOS DISTINTOS Y HACEN FALTA LOS DOS.
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
    if REDUCIR:
        print("Fase 5: reduccion al motivo de consulta...")
        reduccion.cargar_lexico()
        conservadas["texto_embedding"] = conservadas[columna_juicio].map(reduccion.recortar)
        columnas = columnas + ["texto_embedding"]
        vacios = (conservadas["texto_embedding"] == "").sum()
        if vacios:
            print(f"  aviso: {vacios:,} notas quedaron sin texto de embedding")

    conservadas[columnas].to_csv(
        OUTPUT_CSV, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL
    )

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
