"""
Escritura de resultados: rotar la version anterior y llenar un CSV por
bloques a medida que la corrida avanza. No sabe de triage, notas ni base de
datos (rutas y columnas por parametro); lo usa cualquier proceso largo del
proyecto, no solo el pipeline de texto. Ver ARQUITECTURA.md §2.2
(`salida.py`).
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
    Aparta la version anterior de un archivo (con la fecha en el nombre)
    antes de escribir la nueva, y devuelve a donde se movio (None si no
    habia nada que apartar). Conserva las ultimas `conservar` versiones.
    """
    ruta = Path(ruta)
    if not ruta.exists():
        return None

    # La marca tiene resolucion de segundo, asi que dos rotaciones seguidas
    # chocan: en Windows renombrar sobre un archivo existente lanza
    # FileExistsError en vez de sobrescribir. El contador evita que la
    # segunda rotacion aborte la corrida.
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
    Dice si un CSV existente se puede seguir llenando con estas columnas. Se
    compara la cabecera, no solo la existencia del archivo, porque la lista
    de columnas depende de la configuracion de quien escribe.
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
    Las llaves que ya estan en los archivos indicados (para que relanzar
    continue en vez de repetir). Un archivo que no existe o no tiene la
    columna se ignora en silencio: es el caso normal de la primera corrida.
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
    Un CSV que se va llenando mientras la corrida avanza: pone la cabecera al
    abrir, luego solo anade filas y vacia el buffer tras cada bloque. Usa
    utf-8-sig y QUOTE_ALL (igual que df.to_csv con esas opciones).
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
