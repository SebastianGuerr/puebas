"""
El almacen de vectores. Guarda lo ya calculado y sabe decir que falta.

EL PROBLEMA QUE RESUELVE
    triage_limpio.csv va a crecer agregando renglones, no rehaciendose entero.
    Sin GPU, volver a vectorizar de cero en cada corrida es tirar horas para
    obtener exactamente los mismos numeros. Este modulo es lo que hace que una
    segunda corrida solo pague por lo que llego nuevo.

LA LLAVE ES EL TEXTO, NO EL OID
    Podria guardarse un vector por OID, pero seria peor por dos motivos.

    El primero es el ahorro: el mismo motivo de consulta se repite muchisimo
    ('dolor abdominal', 'fiebre'), y sobre la corrida de 28.095 notas habia
    19.821 textos distintos. Guardando por texto se vectoriza un 30% menos.

    El segundo es la correccion. Si NLP/ mejora y una nota vieja pasa a tener
    otro texto_embedding, con llave por OID el vector guardado quedaria pegado
    a ese OID y seguiria usandose aunque ya no corresponda al texto. Con llave
    por texto, un texto distinto es una huella distinta y se vectoriza sola: es
    imposible que un vector quede desalineado de la frase que representa.

    La huella es sha1 y no el hash() de Python, que va salteado por proceso y
    daria un valor distinto en cada corrida.

QUE PASA SI SE CORTA A MEDIAS
    El orden de escritura es siempre el mismo: primero los vectores al final
    del binario, y solo despues el vocabulario que dice cuantos hay. Asi, un
    corte deja como mucho vectores de sobra al final del archivo, nunca un
    vocabulario que promete filas que no existen. abrir() detecta esa cola
    suelta y la recorta, y lo que se perdio se recalcula en la corrida
    siguiente porque su huella vuelve a faltar.
"""

import hashlib
import json
import os
from datetime import datetime

import numpy as np
import pandas as pd

from embedding import rutas


def huella(texto):
    """
    Identificador estable de un texto. Se recorta a 16 caracteres porque con
    ese largo la probabilidad de choque sobre unos cientos de miles de frases
    es despreciable, y el archivo pesa la mitad que con el sha1 completo.
    """
    return hashlib.sha1(texto.encode("utf-8")).hexdigest()[:16]


class Almacen:
    """
    Los tres archivos de salidas/ tratados como una sola cosa.

    Se usa asi:

        almacen = Almacen.abrir(dimension, modelo.identidad())
        faltan = [t for t in textos if almacen.huella_de(t) not in almacen]
        almacen.agregar(faltan, matriz)
    """

    def __init__(self, dimension, identidad, huellas, textos):
        self.dimension = dimension
        self.identidad = identidad
        self.huellas = huellas      # lista, en el orden de las filas
        self.textos = textos        # lista, alineada con huellas
        self.fila = {h: i for i, h in enumerate(huellas)}
        self.agregados = 0

    # ------------------------------------------------------
    # apertura y reparacion
    # ------------------------------------------------------

    @classmethod
    def abrir(cls, dimension, identidad, rehacer=False):
        """
        Levanta el almacen de disco, o crea uno vacio si no habia.

        Se niega a continuar si el manifiesto guardado dice que la matriz se
        lleno con otro modelo u otros parametros: esos vectores no viven en el
        mismo espacio que los que se van a calcular ahora, y apendarlos daria
        una matriz mitad y mitad que ningun clustering puede interpretar. Para
        ese caso esta --rehacer, que empieza de cero a proposito.
        """
        if rehacer or not rutas.MANIFIESTO.exists():
            return cls(dimension, identidad, [], [])

        manifiesto = json.loads(rutas.MANIFIESTO.read_text(encoding="utf-8"))
        guardada = manifiesto.get("identidad", {})
        if guardada != identidad:
            raise SystemExit(
                "El almacen existente se lleno con otros parametros.\n"
                f"  guardado : {guardada}\n"
                f"  actual   : {identidad}\n"
                "Los vectores no son comparables entre si. Corre con --rehacer "
                "para empezar de cero, o devuelve embedding/modelo.py a los "
                "valores anteriores.")

        if manifiesto.get("dimension") != dimension:
            raise SystemExit(
                f"El almacen tiene vectores de {manifiesto.get('dimension')} "
                f"dimensiones y el modelo produce {dimension}. Usa --rehacer.")

        # Manifiesto sin vocabulario: una corrida que registro su identidad pero
        # no llego a vectorizar nada. Pasa de verdad, y no es un error: si se
        # lanza esto contra un triage_limpio.csv que todavia no tiene notas
        # -- porque NLP/procesar.py aun no ha cerrado su primer bloque -- no hay
        # ni un texto que guardar. El almacen simplemente esta vacio.
        if not rutas.VOCABULARIO.exists():
            return cls(dimension, identidad, [], [])

        vocabulario = pd.read_parquet(rutas.VOCABULARIO)
        huellas = vocabulario["huella"].tolist()
        textos = vocabulario["texto"].tolist()

        # Cola suelta de una corrida cortada a la mitad: hay vectores escritos
        # que el vocabulario todavia no reclama.
        #
        # Recortarla es solo higiene, no correccion: quien lee pide siempre
        # len(huellas) filas y nunca mira mas alla, y quien apende escribe en la
        # posicion exacta que le toca y pisa la cola. Por eso el recorte es un
        # intento y no un requisito: en Windows falla si alguien tiene un memmap
        # abierto sobre el archivo, y en ese caso seguir es perfectamente sano.
        bytes_por_fila = dimension * np.dtype(np.float32).itemsize
        en_disco = (rutas.VECTORES.stat().st_size // bytes_por_fila
                    if rutas.VECTORES.exists() else 0)
        if en_disco > len(huellas):
            sobran = en_disco - len(huellas)
            try:
                with open(rutas.VECTORES, "r+b") as binario:
                    binario.truncate(len(huellas) * bytes_por_fila)
                print(f"  se recortaron {sobran:,} vectores de una corrida "
                      f"interrumpida; se recalculan si hacen falta")
            except PermissionError:
                print(f"  quedaron {sobran:,} vectores sueltos de una corrida "
                      f"interrumpida; se ignoran y se sobrescriben")
        elif en_disco < len(huellas):
            # No deberia ocurrir con el orden de escritura de agregar(), pero si
            # alguien borro el binario a mano el vocabulario miente. Se recorta
            # el vocabulario para que vuelvan a faltar esas huellas.
            print(f"  el vocabulario prometia {len(huellas):,} filas y el "
                  f"binario tiene {en_disco:,}; se ajusta al binario")
            huellas = huellas[:en_disco]
            textos = textos[:en_disco]

        return cls(dimension, identidad, huellas, textos)

    # ------------------------------------------------------
    # consulta
    # ------------------------------------------------------

    def __contains__(self, huella_texto):
        return huella_texto in self.fila

    def __len__(self):
        return len(self.huellas)

    def matriz(self):
        """
        La matriz completa como memmap de solo lectura: se pagina desde disco en
        vez de cargarse entera en RAM, que con la tabla completa serian cientos
        de megas para nada.
        """
        if not self.huellas:
            return np.empty((0, self.dimension), dtype=np.float32)
        return np.memmap(
            rutas.VECTORES, dtype=np.float32, mode="r",
            shape=(len(self.huellas), self.dimension))

    # ------------------------------------------------------
    # escritura
    # ------------------------------------------------------

    def agregar(self, textos_nuevos, matriz):
        """
        Apenda vectores al final y actualiza el vocabulario.

        El orden importa y es el que describe el docstring del modulo: primero
        el binario y con fsync, despues el vocabulario. Al reves, un corte entre
        las dos escrituras dejaria un vocabulario reclamando filas inexistentes.

        Se escribe buscando la posicion exacta y no en modo "ab", que agregaria
        DESPUES de una posible cola suelta y dejaria un hueco de basura en medio
        de la matriz. Con seek, la fila que toca cae donde el vocabulario dice
        que cae, haya o no cola, y de paso la pisa.
        """
        if len(textos_nuevos) != len(matriz):
            raise ValueError(
                f"{len(textos_nuevos)} textos contra {len(matriz)} vectores")
        if not len(matriz):
            return

        crudo = np.ascontiguousarray(matriz, dtype=np.float32).tobytes()
        inicio = len(self.huellas) * self.dimension * np.dtype(np.float32).itemsize

        if not rutas.VECTORES.exists():
            rutas.VECTORES.touch()
        with open(rutas.VECTORES, "r+b") as binario:
            binario.seek(inicio)
            binario.write(crudo)
            try:
                binario.truncate()   # se lleva la cola sobrante, si la habia
            except OSError:
                pass                 # higiene, no correccion; ver abrir()
            binario.flush()
            os.fsync(binario.fileno())

        for texto in textos_nuevos:
            h = huella(texto)
            self.fila[h] = len(self.huellas)
            self.huellas.append(h)
            self.textos.append(texto)

        self.agregados += len(textos_nuevos)
        self._guardar_vocabulario()

    def _guardar_vocabulario(self):
        pd.DataFrame({"huella": self.huellas, "texto": self.textos}).to_parquet(
            rutas.VOCABULARIO, index=False)

    def guardar_manifiesto(self, extra=None):
        """
        Deja constancia de con que se lleno la matriz. Sin esto no hay forma de
        saber si dos corridas son comparables, ni de detectar que alguien movio
        un parametro entre una y otra.
        """
        manifiesto = {
            "identidad": self.identidad,
            "dimension": self.dimension,
            "textos_distintos": len(self.huellas),
            "actualizado": datetime.now().isoformat(timespec="seconds"),
        }
        manifiesto.update(extra or {})
        rutas.MANIFIESTO.write_text(
            json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
        return manifiesto


def cargar(oids=None):
    """
    Punto de entrada para quien CONSUME los embeddings (la fase de clustering).

    Devuelve la pareja (indice, matriz), donde indice es un DataFrame con OID,
    huella y fila, y matriz es el memmap completo. Para tener un vector por OID,
    en el mismo orden del indice:

        indice, matriz = almacen.cargar()
        vectores = matriz[indice["fila"].to_numpy()]

    Ese paso es el que reparte la fila unica de un texto repetido entre todos
    los OID que lo comparten. Con oids se filtra a un subconjunto.
    """
    if not rutas.MANIFIESTO.exists():
        raise SystemExit(
            "No hay embeddings todavia. Corre antes 'python -m embedding.vectorizar'.")

    manifiesto = json.loads(rutas.MANIFIESTO.read_text(encoding="utf-8"))
    dimension = manifiesto["dimension"]
    total = manifiesto["textos_distintos"]

    indice = pd.read_parquet(rutas.INDICE)
    if oids is not None:
        indice = indice[indice["OID"].isin(set(oids))].reset_index(drop=True)

    # np.memmap no admite un archivo de cero filas, y encima puede que el
    # binario ni exista: es el estado normal de un almacen que registro su
    # identidad pero todavia no tiene ningun texto.
    if total == 0 or not rutas.VECTORES.exists():
        return indice, np.empty((0, dimension), dtype=np.float32)

    matriz = np.memmap(rutas.VECTORES, dtype=np.float32, mode="r",
                       shape=(total, dimension))
    return indice, matriz
