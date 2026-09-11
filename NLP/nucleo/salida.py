"""
Escritura de resultados: rotar la version anterior y llenar un CSV a medida
que la corrida avanza.

POR QUE ESTA AQUI Y NO EN procesar.py
    Todo lo de este modulo lo necesita cualquier proceso largo del proyecto,
    no solo el pipeline de texto: la fase de embeddings y la de clustering
    escriben tablas grandes que tardan horas y que conviene poder mirar
    mientras se generan.

    Nada de aqui sabe de triage, de notas ni de la base de datos. Se le pasan
    rutas y columnas.

LAS TRES IDEAS QUE HAY DETRAS

    rotar()          un artefacto generado nunca se sobrescribe en silencio:
                     la version anterior se aparta con la fecha en el nombre.

    EscritorCSV      el archivo se llena por bloques y se vacia el buffer en
                     cada uno, de modo que otro proceso puede leer lo que va
                     saliendo sin esperar al final.

    llaves_escritas  relanzar continua en vez de repetir: se leen las llaves
                     que ya estan en el archivo y quien llama las salta.
"""

import csv
import time
from pathlib import Path

import pandas as pd


# ==========================================================
# ROTACION
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
# REANUDACION
# ==========================================================

def cabecera_compatible(ruta, columnas):
    """
    Dice si un CSV existente se puede seguir llenando con estas columnas.

    Se compara la cabecera y no solo la existencia del archivo porque la lista
    de columnas depende de la configuracion de quien escribe: en el pipeline de
    texto, apagar la reduccion quita texto_embedding y apagar la normalizacion
    quita texto_normalizado. Apendar filas de cinco campos a un archivo de
    cuatro produce un CSV que no puede leer nadie, asi que ante cualquier
    diferencia se prefiere rotar y empezar limpio.
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


def llaves_escritas(*rutas, llave="OID"):
    """
    Las llaves que ya estan en los archivos indicados.

    Es lo que permite que relanzar continue en vez de repetir: quien llama
    filtra su entrada con esto y solo procesa lo que falta. Un archivo que no
    existe o que no tiene la columna se ignora en silencio, porque la primera
    corrida es justo ese caso.
    """
    hechas = set()
    for ruta in rutas:
        ruta = Path(ruta)
        if not ruta.exists():
            continue
        try:
            columna = pd.read_csv(ruta, encoding="utf-8-sig", usecols=[llave])
        except (ValueError, OSError, pd.errors.EmptyDataError):
            continue
        hechas.update(columna[llave].dropna().astype("int64").tolist())
    return hechas


# ==========================================================
# ESCRITURA INCREMENTAL
# ==========================================================

class EscritorCSV:
    """
    Un CSV que se va llenando mientras la corrida avanza.

    Abre el archivo en la primera escritura, pone la cabecera y desde ahi solo
    anade filas, vaciando el buffer despues de cada bloque para que otro proceso
    pueda leer lo que va saliendo sin esperar a que la corrida termine.

    Usa utf-8-sig y comillas en todos los campos, que es lo mismo que produce
    df.to_csv(..., encoding="utf-8-sig", quoting=csv.QUOTE_ALL): el archivo sale
    byte a byte identico al que saldria escribiendolo de una sola vez.
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
            # varios minutos en la que el archivo sencillamente NO EXISTE, y una
            # corrida cortada ahi deja al paso siguiente sin nada que leer --
            # con un FileNotFoundError que no explica nada -- en vez de con un
            # archivo vacio pero valido.
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
