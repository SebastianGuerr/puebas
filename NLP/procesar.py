"""
Orquestador de la fase 1.

Unico archivo que sabe de la base de datos. Conecta limpieza.py +
diccionario_siglas.json + ortografia.py y produce:

  triage_limpio.csv     OID, texto_original, texto_corregido
  reporte_cambios.csv   cada sustitucion distinta con su conteo

El reporte es la herramienta de auditoria: en vez de leer 30.000 notas, se
revisa la lista de sustituciones ordenada por frecuencia. Si en las primeras
50 filas aparece un farmaco, una sigla o un nombre propio, hay que agregarlo
a diccionario_siglas.json antes de dar la fase por buena.

Quien construye ese reporte y mide la corrida es auditoria.py. Se separo
porque la version que vivia aca solo comparaba texto_limpio contra
texto_corregido, y por eso no veia ni la limpieza ni la normalizacion: dos
fases enteras cambiaban el texto sin dejar rastro auditable.
"""

import csv
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

import auditoria
import casing
import normalizacion
import ortografia
import reglas
import terminologia
from limpieza import analizar, es_vacio, limpiar_conservando_original

# ==========================================================
# CONFIGURACION
# ==========================================================

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_CSV = BASE_DIR / "triage_limpio.csv"
REPORTE_CSV = BASE_DIR / "reporte_cambios.csv"
CACHE_JSON = BASE_DIR / "cache_correcciones.json"

TABLA = "DIM_TRIAGE"
COLUMNA = "HCTMOTCON"
LLAVE = "OID"

LIMITE_REGISTROS = 30000    # None = toda la tabla
MUESTREO_ALEATORIO = True
LIMITE_LEXICO = 200000      # registros usados solo para contar frecuencias

N_HILOS = 4
GUARDAR_CADA = 2000
USAR_CACHE = True           # False al cambiar umbrales: la cache guarda decisiones viejas
NORMALIZAR = True           # agrega la columna texto_normalizado (fase 3)



# ==========================================================
# CARGA
# ==========================================================

def cargar_corpus(engine, filtro):
    print("Construyendo lexico del corpus...")
    df = pd.read_sql(
        f"SELECT TOP {LIMITE_LEXICO} {COLUMNA} FROM {TABLA} WHERE {filtro}", engine
    )
    conteo = ortografia.construir_lexico(df[COLUMNA])
    print(f"  {len(conteo):,} palabras distintas sobre {len(df):,} notas")


def cargar_registros(engine, filtro):
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
    La misma nota limpia puede corregirse distinto segun las mayusculas del
    original: 'de pereira' se corrige si venia en minuscula y se respeta si
    venia 'de Pereira'. La clave tiene que incluir esa diferencia.
    """
    if not protegidos:
        return texto_limpio
    return texto_limpio + "\x00" + ",".join(sorted(protegidos))


def preparar(df):
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
    """pendientes: lista de (clave, texto_limpio, texto_original)."""
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
    print("Conectando BD...")
    from conexion_bd import obtener_engine
    engine = obtener_engine()

    filtro = f"{COLUMNA} IS NOT NULL AND LTRIM(RTRIM({COLUMNA})) <> ''"

    print("Cargando diccionarios...")
    ortografia.cargar_siglas()

    # El lexico de capitalizacion es lo que devuelve la proteccion a las notas
    # gritadas, que son el 87,7% del corpus. Sin el, detectar_protegidos() y el
    # NER siguen viendo un bloque de mayusculas sin contraste.
    aprendidas = casing.cargar()
    if aprendidas:
        print(f"  {aprendidas:,} tokens con capitalizacion aprendida "
              f"({len(casing.siglas()):,} siglas, "
              f"{len(casing.nombres_propios()):,} nombres propios)")
    else:
        print("  AVISO: falta lexico_casing.json. Corre antes: python casing.py")
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

    df[columnas].to_csv(
        OUTPUT_CSV, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_ALL
    )

    filas = auditoria.escribir_reporte(df, REPORTE_CSV, columnas)
    modificados = (df["texto_limpio"] != df["texto_corregido"]).sum()

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
    print(f"Notas modificadas: {modificados:,} de {len(df):,} "
          f"({modificados/len(df)*100:.1f}%)")
    print(f"Sustituciones distintas: {len(filas):,}")
    print(f"\nTop 15 (revisar que no haya terminos clinicos):")
    for fase, o, r, n, _oid in filas[:15]:
        print(f"  {n:5}  [{fase:13}] {o} -> {r}")

    print(f"\nEstadisticas de limpieza: {analizar(df[COLUMNA].head(2000))}")
    print(f"\nCSV: {OUTPUT_CSV}")
    print(f"Reporte: {REPORTE_CSV}")


if __name__ == "__main__":
    main()
