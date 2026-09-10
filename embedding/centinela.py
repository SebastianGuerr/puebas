"""
Vigila triage_limpio.csv y vectoriza las notas nuevas segun van apareciendo.

    python -m embedding.centinela
    python -m embedding.centinela --intervalo 300     # mira cada 5 minutos
    python -m embedding.centinela --csv "D:\\otro.csv"

Se para con Ctrl+C. Deja el almacen consistente en cada vuelta, asi que cortarlo
en cualquier momento es seguro.

POR QUE UN CENTINELA Y NO UN BUCLE EN POWERSHELL
    Se puede hacer 'while ($true) { python -m embedding.vectorizar; sleep 1800 }'
    y funciona. Pero cada vuelta arranca un proceso nuevo, y eso significa traer
    bge-m3 a memoria otra vez: sobre CPU son un par de minutos de reloj por
    vuelta, para un trabajo que muchas veces son quince segundos de vectorizar
    doscientos textos.

    Este modulo carga el modelo UNA vez y lo deja vivo entre pasadas. Con eso
    mirar cada minuto sale casi gratis, y el embedding va pegado a lo que
    NLP/procesar.py escribe en vez de ir media hora por detras.

QUE NO HACE
    No toca triage_limpio.csv jamas: lo abre en modo lectura y nada mas. El
    unico que escribe ese archivo es NLP/procesar.py.

POR QUE RELEE EL ALMACEN EN CADA PASADA
    El deposito se vuelve a abrir de disco cada vuelta en vez de conservarse en
    memoria. Cuesta leer un parquet, que no es nada, y a cambio permite que el
    centinela conviva con un 'python -m embedding.vectorizar' lanzado a mano sin
    que ninguno de los dos trabaje sobre una foto vieja de lo ya vectorizado.
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

from embedding import almacen, corpus, modelo, rutas

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

CSV_POR_DEFECTO = rutas.TRIAGE_LIMPIO

# Cada cuanto se mira el archivo. Mirar es un stat(), asi que puede ser corto.
INTERVALO = 60

# Textos por punto de control dentro de una pasada.
BLOQUE = 2000


def firma(ruta):
    """
    Como saber si el CSV cambio sin leerlo entero.

    La pareja (fecha de modificacion, tamano) basta y cuesta un stat(). Como
    NLP/procesar.py solo apende, el tamano crece de forma monotona: si no se ha
    movido, no hay nada nuevo que mirar.
    """
    if not ruta.exists():
        return None
    est = ruta.stat()
    return (est.st_mtime_ns, est.st_size)


def ahora():
    return datetime.now().strftime("%H:%M:%S")


class Motor:
    """
    El modelo y el almacen. Guarda bge-m3 cargado entre pasadas, que es la razon
    de ser de este modulo.
    """

    def __init__(self):
        self.red = None
        self.dimension = None
        if rutas.MANIFIESTO.exists():
            guardado = json.loads(rutas.MANIFIESTO.read_text(encoding="utf-8"))
            self.dimension = guardado.get("dimension")

    def modelo_listo(self):
        """Carga bge-m3 la primera vez que de verdad hace falta."""
        if self.red is None:
            print(f"[{ahora()}] cargando modelo (una sola vez)...")
            self.red, dimension = modelo.cargar()
            if self.dimension is not None and dimension != self.dimension:
                raise SystemExit(
                    f"El modelo produce {dimension} dimensiones y el almacen "
                    f"tiene {self.dimension}. Corre 'vectorizar --rehacer'.")
            self.dimension = dimension
        return self.red

    def pasada(self, entrada):
        """
        Una vuelta completa: lee el CSV, vectoriza lo que falte y actualiza el
        indice. Devuelve (notas, nuevos, total) o None si no habia nada.
        """
        utiles, vacios, repetidos = corpus.leer(entrada)
        if utiles.empty:
            return None

        if self.dimension is None:
            self.modelo_listo()

        deposito = almacen.Almacen.abrir(self.dimension, modelo.identidad())
        faltan = corpus.pendientes(utiles, deposito)

        if faltan:
            red = self.modelo_listo()
            inicio = time.time()
            for arranque in range(0, len(faltan), BLOQUE):
                lote = faltan[arranque:arranque + BLOQUE]
                deposito.agregar(lote, modelo.codificar(red, lote))
            ritmo = len(faltan) / max(time.time() - inicio, 1e-9)
            print(f"[{ahora()}] +{len(faltan):,} textos nuevos "
                  f"({ritmo:.1f}/s) | almacen: {len(deposito):,}")

        if len(vacios):
            vacios.to_csv(rutas.SIN_TEXTO, index=False)

        indice = corpus.escribir_indice(utiles, deposito)
        deposito.guardar_manifiesto({
            "csv_origen": str(entrada),
            "columna": corpus.COLUMNA_TEXTO,
            "notas_indexadas": len(indice),
            "notas_sin_texto": len(vacios),
            "agregados_esta_corrida": deposito.agregados,
        })
        return len(utiles), len(faltan), len(deposito)


def main():
    ap = argparse.ArgumentParser(
        description="Vigila el CSV y vectoriza las notas nuevas segun aparecen.")
    ap.add_argument("--csv", type=Path, default=None,
                    help="ruta al CSV que se vigila")
    ap.add_argument("--intervalo", type=int, default=INTERVALO,
                    help=f"segundos entre comprobaciones (por defecto {INTERVALO})")
    args = ap.parse_args()

    entrada = (args.csv or CSV_POR_DEFECTO).resolve()
    motor = Motor()

    print(f"Vigilando {entrada}")
    print(f"Cada {args.intervalo}s. Ctrl+C para parar.")
    print("El CSV solo se lee; el unico que lo escribe es NLP/procesar.py.\n")

    ultima = None
    vueltas_quietas = 0
    try:
        while True:
            actual = firma(entrada)

            if actual is None:
                print(f"[{ahora()}] todavia no existe el CSV; esperando a "
                      f"NLP/procesar.py")
            elif actual == ultima:
                vueltas_quietas += 1
                # Sin novedad no se imprime cada vuelta: con intervalos cortos
                # eso llenaria la consola de lineas identicas y taparia lo unico
                # que interesa mirar, que es cuando SI entra trabajo.
                if vueltas_quietas % 10 == 1:
                    print(f"[{ahora()}] sin cambios "
                          f"({vueltas_quietas} comprobaciones seguidas)")
            else:
                vueltas_quietas = 0
                resultado = motor.pasada(entrada)
                if resultado is None:
                    print(f"[{ahora()}] el CSV existe pero aun no tiene notas")
                else:
                    notas, nuevos, total = resultado
                    if not nuevos:
                        print(f"[{ahora()}] {notas:,} notas | sin textos nuevos")
                    else:
                        print(f"[{ahora()}] {notas:,} notas indexadas | "
                              f"{total:,} vectores en el almacen")
                ultima = actual

            time.sleep(args.intervalo)

    except KeyboardInterrupt:
        print(f"\n[{ahora()}] centinela detenido. El almacen queda consistente.")


if __name__ == "__main__":
    main()
