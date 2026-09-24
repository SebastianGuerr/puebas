# -*- coding: utf-8 -*-
"""
Arma lo que sale a la GPU: paquete.jsonl con {"id","prompt"} y nada mas.

    python -m NLP.nube --exportar --muestra 300
    python -m NLP.nube --exportar --oids lista.txt
    python -m NLP.nube --exportar                      todas las que faltan

QUE SE BAJA DE DIM_TRIAGE, Y DONDE SE QUEDA CADA COSA
    OID, HCTFECTRI, HCTMOTCON       -> mapa_local.parquet (local, ignorado por git)
    GPADOCUME, GPANOMBRE, GPASEGNOM,
    GPAAPELLI, GPASEGAPE            -> SOLO EN MEMORIA. Se usan para tapar el
                                       nombre del paciente dentro de su propia
                                       nota y se tiran. Nunca se escriben.

    Y una consulta agregada: cuantas veces aparece cada nombre y cada apellido
    en la tabla (GROUP BY). Tambien solo en memoria. Es la lista con la que se
    decide si la palabra que sigue a 'madre' o a 'acompanado de' es un nombre;
    sin ella, los terceros solo se detectarian tras 'sra' o 'doctor'.

LO QUE SALE, LINEA POR LINEA
    {"id": "9f2c...", "prompt": "<el prompt completo, con la nota enmascarada>"}

    - id: secrets.token_hex(8). Aleatorio de verdad, no un hash del OID: un
      hash se puede recalcular para cada OID candidato y deshacer el cruce.
    - prompt: armado AQUI con construir() del modulo de prompt elegido. La
      maquina remota no necesita ni una linea de codigo del proyecto, y el
      glosario del hospital que se inyecta sale de la nota ya enmascarada.
    - el orden se BARAJA: las notas salen de la base en orden de OID, que es
      casi orden cronologico. Sin barajar, la posicion de la linea diria la
      fecha aproximada de cada nota.

    Nada mas: ni fecha, ni OID, ni edad, ni nombre de columna, ni lote.
"""

import json
import os
import re
import secrets
import sys
import time
import warnings
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

from NLP import rutas
from NLP.nube import CARPETA, LOTE, MAPA, OPCIONES, PAQUETE, RESULTADOS, SEGUNDA
from NLP.nube import enmascarar as em

warnings.filterwarnings("ignore", message=".*Unrecognized server version.*")

TABLA = "DIM_TRIAGE"
LLAVE = "OID"
COLUMNA = "HCTMOTCON"
COLUMNA_FECHA = "HCTFECTRI"
IDENTIDAD = ["GPADOCUME", "GPANOMBRE", "GPASEGNOM", "GPAAPELLI", "GPASEGAPE"]
COLUMNAS_BD = [LLAVE, COLUMNA_FECHA, COLUMNA] + IDENTIDAD

PROMPT_POR_DEFECTO = rutas.PAQUETE / "prompts" / "v1_7.py"
MODELO = "qwen3:8b"

# Una ficha tiene que aparecer al menos estas veces en las columnas de nombre
# para contar como 'nombre conocido'. Filtra erratas de digitacion sueltas.
MINIMO_NOMBRE = 5

# Por encima de estas notas se arma en paralelo: el glosario de cada prompt
# cuesta ~0,1 s y 94.000 notas en un solo proceso son casi tres horas.
PARALELO_DESDE = 2000


# ==========================================================
# EL MODULO DE PROMPT
# ==========================================================

def cargar_prompt(ruta):
    """Un .py con construir(nota), VERSION y, opcional, posprocesar()."""
    import importlib.util

    ruta = Path(ruta)
    if not ruta.is_absolute():
        ruta = rutas.PROYECTO / ruta
    spec = importlib.util.spec_from_file_location("prompt_nube_" + ruta.stem, ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def ruta_relativa(ruta):
    """Como se guarda en el mapa: relativa a la raiz y con barras normales."""
    ruta = Path(ruta).resolve()
    try:
        return ruta.relative_to(rutas.PROYECTO).as_posix()
    except ValueError:
        return ruta.as_posix()


def ampliar_cache_regex():
    """
    El glosario busca ~3.300 expresiones por nota con re.search, y el modulo re
    solo guarda 512 compiladas: las recompila todas en cada nota (medido el
    2026-09-23: 90 % del tiempo de construir(), 0,62 s por prompt). Con la cache
    ampliada baja a ~0,1 s y el prompt sale identico byte a byte (comprobado).
    """
    if getattr(re, "_MAXCACHE", 0) < 20000:
        re._MAXCACHE = 20000


# ==========================================================
# BASE CLINICA
# ==========================================================

def _engine():
    from NLP.nucleo.conexion_bd import obtener_engine
    return obtener_engine()


def _con_reintento(engine, funcion):
    """
    Una consulta, con UN reintento si la conexion estaba muerta.

    El engine de NLP/nucleo/conexion_bd.py no comprueba la conexion antes de
    usarla, y tras una lectura larga el pool puede entregar una que el servidor
    ya cerro (visto el 2026-09-23: PendingRollbackError en la consulta siguiente
    a leer las 95.405 notas). Se tira el pool y se repite una vez.
    """
    from sqlalchemy.exc import DBAPIError, PendingRollbackError

    try:
        return funcion()
    except (DBAPIError, PendingRollbackError):
        engine.dispose()
        return funcion()


# Una ficha de nombre que aparece en al menos PALABRA_DF notas y en al menos la
# mitad de notas que personas se llaman asi, en las notas es una palabra.
#
# Una que llevan SUELTO_PERSONAS personas o mas y aparece en menos de 1 nota por
# cada 50 de ellas casi solo existe como nombre. Medido el 2026-09-23 (95.405
# notas): los nombres con 1.000+ personas tienen df mediana 2 y razon
# df/personas maxima 0,071 ('sofia', por el hospital); las palabras sospechosas
# de la calibracion, entre 3 y 57.
#
# El minimo de personas NO es opcional. Sin el, la primera version tapaba
# palabras raras que tambien son apellidos raros -un arete en el lobulo de la
# oreja, lo que alguien se echo en la piel antes de asolearse-: aparecen en 1 o
# 2 notas y su razon sale baja solo porque son raras.
PALABRA_DF, PALABRA_RAZON = 20, 0.5
SUELTO_PERSONAS, SUELTO_RAZON = 300, 0.02


def frecuencia_en_notas(engine):
    """En cuantas notas aparece cada palabra. Lee el texto de todas, en memoria,
    y se queda solo con la cuenta."""
    from NLP.nucleo import datos

    textos = _con_reintento(engine, lambda: pd.read_sql(
        f"SELECT {COLUMNA} FROM {TABLA} WHERE {datos.filtro_no_vacio(COLUMNA)}", engine))[COLUMNA]
    df = Counter()
    for texto in textos:
        df.update(set(em._fichas(texto)))
    return df, len(textos)


def cargar_nombres(engine, minimo=MINIMO_NOMBRE, df=None):
    """
    Fichas de nombre y de apellido de toda la tabla, con un GROUP BY. En memoria.

    La consulta devuelve valores de columnas sensibles (los nombres distintos y
    cuantas veces aparece cada uno), y por eso lo que sale de aqui no se
    imprime ni se guarda: solo se usa para reconocer un nombre en el texto.
    """
    def cuenta(columnas):
        partes = " UNION ALL ".join(
            f"SELECT {c} AS v, COUNT(*) AS n FROM {TABLA} WHERE {c} IS NOT NULL GROUP BY {c}"
            for c in columnas)
        tabla = _con_reintento(engine, lambda: pd.read_sql(
            f"SELECT v, SUM(n) AS n FROM ({partes}) t GROUP BY v", engine))
        total = Counter()
        for valor, n in zip(tabla["v"], tabla["n"]):
            for ficha in em._fichas(valor):
                total[ficha] += int(n)
        return total

    de_pila, apellidos = cuenta(["GPANOMBRE", "GPASEGNOM"]), cuenta(["GPAAPELLI", "GPASEGAPE"])
    if df is None:
        df, _ = frecuencia_en_notas(engine)
    return nombres_desde_cuentas(de_pila, apellidos, df, minimo)


def nombres_desde_cuentas(de_pila, apellidos, df, minimo=MINIMO_NOMBRE):
    """La parte sin base de datos de cargar_nombres (se prueba con cuentas sinteticas)."""
    personas = Counter(de_pila) + Counter(apellidos)

    def palabra(f):
        return df.get(f, 0) >= PALABRA_DF and df.get(f, 0) >= PALABRA_RAZON * personas[f]

    def valida(f, n):
        return (n >= minimo and len(f) >= 3 and f.isalpha() and not em.es_vacia(f)
                and not em.es_comun(f) and not palabra(f))

    pila = frozenset(f for f, n in de_pila.items() if valida(f, n))
    ape = frozenset(f for f, n in apellidos.items() if valida(f, n))
    sueltos = frozenset(f for f in pila | ape
                        if personas[f] >= SUELTO_PERSONAS
                        and df.get(f, 0) <= SUELTO_RAZON * personas[f])
    return em.Nombres(nombres=pila, apellidos=ape, sueltos=sueltos)


def _con_tabla_de_oids(conexion, nombre, oids):
    conexion.exec_driver_sql(f"DROP TABLE IF EXISTS {nombre}")
    conexion.exec_driver_sql(f"CREATE TABLE {nombre} ({LLAVE} bigint PRIMARY KEY)")
    claves = sorted({int(k) for k in oids})
    for inicio in range(0, len(claves), 1000):
        tuplas = ",".join(f"({k})" for k in claves[inicio:inicio + 1000])
        conexion.exec_driver_sql(f"INSERT INTO {nombre} ({LLAVE}) VALUES {tuplas}")


def traer_notas(engine, muestra=None, oids=None, excluir=None):
    """
    Las notas a exportar, con las columnas de identidad. En memoria.

    muestra  N notas repartidas por toda la tabla (HASHBYTES del OID: repetible)
    oids     exactamente esas notas
    ninguno  todas las que tienen texto, menos las de `excluir`
    """
    from NLP.nucleo import datos

    if oids is None:
        return _con_reintento(engine, lambda: datos.muestra(
            engine, TABLA, COLUMNAS_BD, datos.filtro_no_vacio(COLUMNA),
            limite=muestra, disperso=True, llave=LLAVE, excluir=excluir))
    campos = ", ".join(f"t.{c}" for c in COLUMNAS_BD)

    def consulta():
        with engine.begin() as conexion:
            _con_tabla_de_oids(conexion, "#pedidas", oids)
            return pd.read_sql(
                f"SELECT {campos} FROM {TABLA} AS t WHERE {datos.filtro_no_vacio('t.' + COLUMNA)} "
                f"AND EXISTS (SELECT 1 FROM #pedidas AS p WHERE p.{LLAVE} = t.{LLAVE})", conexion)
    return _con_reintento(engine, consulta)


def traer_identidades(engine, oids):
    """{OID: Identidad} para la auditoria. Solo las cinco columnas y el OID."""
    campos = ", ".join(f"t.{c}" for c in [LLAVE] + IDENTIDAD)

    def consulta():
        with engine.begin() as conexion:
            _con_tabla_de_oids(conexion, "#auditadas", oids)
            return pd.read_sql(
                f"SELECT {campos} FROM {TABLA} AS t "
                f"WHERE EXISTS (SELECT 1 FROM #auditadas AS a WHERE a.{LLAVE} = t.{LLAVE})", conexion)
    tabla = _con_reintento(engine, consulta)
    return {int(f[LLAVE]): em.Identidad.de_fila(f) for f in tabla.to_dict("records")}


def oids_ya_hechos(carpeta=CARPETA, incluir_base=False):
    """Lo que no hace falta volver a mandar: lo ya importado de una corrida en la
    nube y, si se pide, lo que ya tiene frase en nota_triage (la base local)."""
    hechos = set()
    resultados = Path(carpeta) / RESULTADOS
    if resultados.exists():
        tabla = pd.read_parquet(resultados, columns=["OID", "frase_procesada"])
        hechos |= set(tabla.loc[tabla["frase_procesada"].notna(), "OID"].astype(int))
    if incluir_base:
        import duckdb
        ruta = rutas.BASE_VISTA if rutas.BASE_VISTA.exists() else rutas.BASE_DATOS
        if ruta.exists():
            con = duckdb.connect(str(ruta), read_only=True)
            try:
                hechos |= {f[0] for f in con.execute(
                    "SELECT OID FROM nota_triage WHERE frase_procesada IS NOT NULL").fetchall()}
            finally:
                con.close()
    return hechos


# ==========================================================
# ARMAR (sin base de datos: se prueba con datos sinteticos)
# ==========================================================

_TRABAJO = {}


def _iniciar(ruta_prompt, nombres, segunda=False):
    """Inicializador de cada proceso: carga el prompt una vez, no por nota.

    Con segunda=True usa construir_segunda_pasada(): el prompt que no admite
    abstenerse, para las notas descartadas que traen evidencia clinica (ver
    NLP/cadena.py y NLP/docs/NUBE.md, 'La segunda pasada')."""
    ampliar_cache_regex()
    modulo = cargar_prompt(ruta_prompt)
    _TRABAJO["prompt"] = modulo
    _TRABAJO["nombres"] = nombres
    _TRABAJO["construir"] = modulo.construir_segunda_pasada if segunda else modulo.construir


def _preparar(entrada):
    """(texto, identidad) -> (enmascarado, conteo, prompt, terminos_antes, terminos_despues)."""
    from NLP import glosario

    texto, identidad = entrada
    enmascarado, conteo = em.enmascarar(texto, identidad, _TRABAJO["nombres"])
    prompt = _TRABAJO["construir"](enmascarado)
    antes = len(glosario.buscar_terminos_clinicos(texto))
    despues = len(glosario.buscar_terminos_clinicos(enmascarado))
    return enmascarado, conteo, prompt, antes, despues


def ids_aleatorios(n):
    """n ids de 16 hex, distintos, sin ninguna relacion con el OID."""
    vistos = set()
    while len(vistos) < n:
        vistos.add(secrets.token_hex(8))
    ids = list(vistos)
    secrets.SystemRandom().shuffle(ids)
    return ids


def opciones_ollama(modelo):
    from NLP import modelo as motor
    return {"modelo": modelo, "think": False, "options": dict(motor.OPCIONES)}


def armar(notas, nombres=None, ruta_prompt=PROMPT_POR_DEFECTO, modelo=MODELO,
          carpeta=CARPETA, procesos=None, informar=True, segunda=False):
    """
    notas: DataFrame con OID, HCTFECTRI, HCTMOTCON y las cinco de identidad.

    Escribe paquete.jsonl, opciones.json, mapa_local.parquet y lote.json en
    `carpeta`. Devuelve {id: Identidad} para que la auditoria se haga con la
    identidad todavia en memoria, sin volver a la base.
    """
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    modulo = cargar_prompt(ruta_prompt)
    version = getattr(modulo, "VERSION", "desconocida")
    if segunda and not hasattr(modulo, "construir_segunda_pasada"):
        raise SystemExit(f"{ruta_prompt} no define construir_segunda_pasada()")

    filas = notas.to_dict("records")
    ids = ids_aleatorios(len(filas))
    # BARAJAR ANTES de procesar: la salida se escribe en el orden de llegada, y
    # asi el orden del archivo ya es el barajado sin tener 700 MB de prompts en
    # memoria esperando.
    orden = list(range(len(filas)))
    secrets.SystemRandom().shuffle(orden)
    entradas = [(str(filas[i][COLUMNA]), em.Identidad.de_fila(filas[i])) for i in orden]

    procesos = procesos if procesos is not None else (
        max(1, (os.cpu_count() or 2) - 2) if len(filas) >= PARALELO_DESDE else 1)
    inicio = time.time()
    mapa, identidades = [], {}
    ruta_paquete = carpeta / PAQUETE
    temporal = ruta_paquete.with_suffix(".tmp")

    if procesos > 1:
        from multiprocessing import Pool
        pool = Pool(procesos, initializer=_iniciar, initargs=(str(ruta_prompt), nombres, segunda))
        resultados = pool.imap(_preparar, entradas, chunksize=64)
    else:
        _iniciar(str(ruta_prompt), nombres, segunda)
        pool, resultados = None, map(_preparar, entradas)

    try:
        with open(temporal, "w", encoding="utf-8", newline="\n") as salida:
            for posicion, (i, resultado) in enumerate(zip(orden, resultados), 1):
                enmascarado, conteo, prompt, antes, despues = resultado
                fila, id_ = filas[i], ids[posicion - 1]
                salida.write(json.dumps({"id": id_, "prompt": prompt}, ensure_ascii=False) + "\n")
                identidades[id_] = entradas[posicion - 1][1]
                mapa.append({"id": id_, "OID": int(fila[LLAVE]),
                             "fecha_triage": fila.get(COLUMNA_FECHA),
                             "frase_original": str(fila[COLUMNA]),
                             "texto_enmascarado": enmascarado,
                             "terminos_antes": antes, "terminos_despues": despues,
                             **{"n_" + t: conteo.get(t, 0) for t in em.TIPOS}})
                if informar and (posicion % 500 == 0 or posicion == len(filas)):
                    ritmo = posicion / max(time.time() - inicio, 1e-9)
                    print(f"\r  {posicion:,}/{len(filas):,} notas   {ritmo:5.1f} notas/s   "
                          f"faltan {(len(filas) - posicion) / ritmo / 60:5.1f} min",
                          end="", flush=True)
    finally:
        if pool is not None:
            pool.close()
            pool.join()
    if informar:
        print()
    temporal.replace(ruta_paquete)

    tabla = pd.DataFrame(mapa)
    tabla["version_prompt"] = version
    tabla["ruta_prompt"] = ruta_relativa(ruta_prompt)
    tabla["modelo"] = modelo
    tabla["pasada"] = 2 if segunda else 1
    tabla.to_parquet(carpeta / MAPA, index=False)

    with open(carpeta / OPCIONES, "w", encoding="utf-8") as archivo:
        json.dump(opciones_ollama(modelo), archivo, ensure_ascii=False, indent=2)

    with open(carpeta / LOTE, "w", encoding="utf-8") as archivo:
        json.dump({"creado": datetime.now().isoformat(timespec="seconds"),
                   "notas": len(tabla), "version_prompt": version,
                   "ruta_prompt": ruta_relativa(ruta_prompt), "modelo": modelo,
                   "pasada": 2 if segunda else 1,
                   "sha256_paquete": huella(ruta_paquete)}, archivo, indent=2)
    return identidades


def huella(ruta):
    import hashlib
    h = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for trozo in iter(lambda: archivo.read(1 << 20), b""):
            h.update(trozo)
    return h.hexdigest()


# ==========================================================
# EL COMANDO
# ==========================================================

def _apartar_mapa_anterior(carpeta):
    """
    Nunca se pisa un mapa: es la UNICA forma de emparejar respuestas por las que
    ya se pago GPU. Se renombra con la fecha y se deja al lado.
    """
    mapa = Path(carpeta) / MAPA
    if not mapa.exists():
        return None
    sello = datetime.fromtimestamp(mapa.stat().st_mtime).strftime("%Y%m%d_%H%M%S")
    destino = mapa.with_name(f"mapa_local_{sello}.parquet")
    mapa.replace(destino)
    lote = Path(carpeta) / LOTE
    if lote.exists():
        lote.replace(lote.with_name(f"lote_{sello}.json"))
    return destino


def exportar(muestra=None, oids=None, ruta_prompt=PROMPT_POR_DEFECTO, modelo=MODELO,
             excluir_base=False, carpeta=CARPETA, forzar=False, segunda=False):
    from NLP.nube import auditar

    carpeta = Path(carpeta)
    if segunda and not oids:
        # los OID que dejo --importar: descartados con evidencia clinica
        oids = carpeta / SEGUNDA
        if not oids.exists() or not oids.read_text(encoding="utf-8").split():
            print(f"No hay {SEGUNDA} con notas pendientes: la segunda pasada sale de "
                  f"'python -m NLP.nube --importar' sobre la primera.")
            return 1
    if (carpeta / MAPA).exists() and not forzar:
        print(f"Ya hay un paquete armado en {carpeta}.\n"
              f"Su mapa_local.parquet es lo unico que empareja las respuestas con los OID.\n"
              f"Si ya importaste sus respuestas (o nunca se mando), repite con --forzar:\n"
              f"el mapa anterior se aparta con su fecha, no se borra.")
        return 1
    apartado = _apartar_mapa_anterior(carpeta) if forzar else None
    if apartado:
        print(f"Mapa anterior apartado en {apartado.name}")

    modulo = cargar_prompt(ruta_prompt)
    print(f"Prompt {getattr(modulo, 'VERSION', '?')} ({ruta_relativa(ruta_prompt)})   modelo {modelo}")

    print("Conectando a la base clinica...")
    engine = _engine()
    inicio = time.time()
    nombres = cargar_nombres(engine)
    print(f"  nombres conocidos: {len(nombres.nombres):,} de pila, "
          f"{len(nombres.apellidos):,} apellidos, {len(nombres.sueltos):,} que se tapan "
          f"donde aparezcan (en memoria, no se guardan)")

    lista = None
    if oids:
        lista = [int(x) for x in Path(oids).read_text(encoding="utf-8").split() if x.strip()]
        print(f"  {len(lista):,} OID pedidos en {oids}")
    excluir = None if (lista or muestra) else oids_ya_hechos(carpeta, excluir_base)
    if excluir:
        print(f"  {len(excluir):,} notas ya procesadas no se vuelven a mandar")
    notas = traer_notas(engine, muestra=muestra, oids=lista, excluir=excluir)
    print(f"  {len(notas):,} notas bajadas en {time.time() - inicio:.0f} s")
    if notas.empty:
        print("No hay notas que exportar.")
        return 0

    print("Enmascarando y armando prompts...")
    identidades = armar(notas, nombres, ruta_prompt, modelo, carpeta, segunda=segunda)
    del notas
    print(f"  {carpeta / PAQUETE}")

    return auditar.auditar(carpeta, identidades=identidades)
