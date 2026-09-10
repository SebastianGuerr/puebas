"""
Fase 6. Convierte la columna texto_embedding en vectores de bge-m3.

    python -m embedding.vectorizar
    python -m embedding.vectorizar --csv "D:\\ruta\\a\\triage_limpio.csv"
    python -m embedding.vectorizar --limite 500     # prueba corta
    python -m embedding.vectorizar --rehacer        # tira lo guardado y empieza

    LEE      triage_limpio.csv, que no se modifica en ningun momento
    ESCRIBE  vectores.f32        la matriz, un vector por texto distinto
             vocabulario.parquet que texto es cada fila de la matriz
             indice.parquet      OID -> fila, para juntar cada nota con su vector
             manifiesto.json     con que modelo y parametros se lleno
             sin_texto.csv       los OID que quedaron fuera por venir vacios

ESTE PAQUETE NO LIMPIA NADA
    Ni corrige ortografia, ni expande siglas, ni recorta la nota. Todo eso ya
    paso en NLP/ y llega hecho en la columna texto_embedding. Aca solo se
    convierte texto en numeros.

CORRER ESTO DOS VECES SEGUIDAS NO CUESTA NADA
    La segunda corrida encuentra todas las huellas en el almacen, no carga
    siquiera el modelo y solo rehace el indice. Cuando triage_limpio.csv crezca
    con notas nuevas, se paga unicamente por los textos que no se habian visto.
    Sin GPU eso es la diferencia entre minutos y horas.
"""

import argparse
import json
import time
from pathlib import Path

from embedding import almacen, corpus, modelo, rutas

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

CSV_POR_DEFECTO = rutas.TRIAGE_LIMPIO

# Cada cuantos textos distintos se baja lo hecho a disco. Es el punto de
# control: si la corrida se corta, se pierde como mucho un bloque. Mas chico
# protege mas y escribe mas seguido; 2000 es el mismo valor que usa
# NLP/procesar.py y sobre CPU son unos pocos minutos de trabajo.
BLOQUE = 2000


def abrir_almacen(dimension_conocida, rehacer):
    """
    Abre el almacen sin cargar el modelo cuando se puede.

    La dimension solo la sabe el modelo, y cargarlo son 2 GB y bastante espera.
    Pero si ya hay un manifiesto, la dimension esta escrita ahi, y eso permite
    averiguar si falta trabajo ANTES de decidir si vale la pena cargarlo. En la
    corrida que no tiene nada nuevo que hacer, el modelo no se toca.
    """
    if rehacer or not rutas.MANIFIESTO.exists():
        return None
    guardado = json.loads(rutas.MANIFIESTO.read_text(encoding="utf-8"))
    return guardado.get("dimension")


def limpiar_almacen():
    """Borra los artefactos para que --rehacer empiece de verdad desde cero."""
    for ruta in (rutas.VECTORES, rutas.VOCABULARIO, rutas.INDICE, rutas.MANIFIESTO):
        if ruta.exists():
            ruta.unlink()


def main():
    ap = argparse.ArgumentParser(
        description="Vectoriza la columna texto_embedding con bge-m3.")
    ap.add_argument("--csv", type=Path, default=None,
                    help="ruta completa al CSV de entrada")
    ap.add_argument("--limite", type=int, default=None,
                    help="usa solo las primeras N notas, para probar")
    ap.add_argument("--bloque", type=int, default=BLOQUE,
                    help=f"textos por punto de control (por defecto {BLOQUE})")
    ap.add_argument("--rehacer", action="store_true",
                    help="descarta los vectores guardados y vuelve a empezar")
    args = ap.parse_args()

    entrada = (args.csv or CSV_POR_DEFECTO).resolve()

    # ------------------------------------------------------
    # entrada
    # ------------------------------------------------------
    print(f"Leyendo {entrada}...")
    utiles, vacios, repetidos = corpus.leer(entrada)
    if args.limite:
        utiles = utiles.head(args.limite)

    distintos = utiles["huella"].nunique()
    print(f"  {len(utiles):,} notas con texto | {distintos:,} textos distintos "
          f"({100 * (1 - distintos / max(len(utiles), 1)):.0f}% se repite)")
    if repetidos:
        print(f"  {repetidos:,} OID venian repetidos; se conservo el ultimo")
    if len(vacios):
        vacios.to_csv(rutas.SIN_TEXTO, index=False)
        print(f"  {len(vacios):,} notas sin texto_embedding -> {rutas.SIN_TEXTO.name}")

    # Salir ANTES de cargar el modelo si no hay nada que vectorizar.
    #
    # El caso normal es lanzar esto mientras NLP/procesar.py todavia no ha
    # cerrado su primer bloque: el CSV existe con su cabecera y ni una nota.
    # Traer bge-m3 a memoria para descubrirlo son un par de minutos tirados, y
    # ademas dejaba un manifiesto sin vectores que confundia a la corrida
    # siguiente.
    if utiles.empty:
        print("\nEl CSV todavia no tiene notas con texto_embedding.")
        print("Espera a que NLP/procesar.py cierre su primer bloque y vuelve a correr esto.")
        return

    # ------------------------------------------------------
    # almacen y trabajo pendiente
    # ------------------------------------------------------
    if args.rehacer:
        limpiar_almacen()
        print("  --rehacer: se descarto lo guardado")

    identidad = modelo.identidad()
    dimension = abrir_almacen(None, args.rehacer)
    red = None

    if dimension is not None:
        deposito = almacen.Almacen.abrir(dimension, identidad)
        faltan = corpus.pendientes(utiles, deposito)
        print(f"  almacen: {len(deposito):,} textos ya vectorizados")
        if faltan:
            print("Cargando modelo...")
            red, dimension_real = modelo.cargar()
            if dimension_real != dimension:
                raise SystemExit(
                    f"El modelo produce {dimension_real} dimensiones y el "
                    f"almacen tiene {dimension}. Usa --rehacer.")
    else:
        print("Cargando modelo...")
        red, dimension = modelo.cargar()
        deposito = almacen.Almacen.abrir(dimension, identidad, rehacer=True)
        faltan = corpus.pendientes(utiles, deposito)

    # ------------------------------------------------------
    # vectorizacion por bloques
    # ------------------------------------------------------
    if faltan:
        print(f"\nVectorizando {len(faltan):,} textos nuevos "
              f"(punto de control cada {args.bloque:,})...")
        inicio = time.time()
        hechos = 0
        for arranque in range(0, len(faltan), args.bloque):
            lote = faltan[arranque:arranque + args.bloque]
            deposito.agregar(lote, modelo.codificar(red, lote, progreso=True))
            hechos += len(lote)
            ritmo = hechos / max(time.time() - inicio, 1e-9)
            restan = (len(faltan) - hechos) / max(ritmo, 1e-9)
            print(f"  {hechos:,}/{len(faltan):,}  "
                  f"{ritmo:.1f} textos/s  faltan ~{restan / 60:.0f} min")
        print(f"  listo en {(time.time() - inicio) / 60:.1f} min")
    else:
        print("\nNo hay textos nuevos: todo estaba vectorizado.")

    # ------------------------------------------------------
    # indice y manifiesto
    # ------------------------------------------------------
    indice = corpus.escribir_indice(utiles, deposito)
    manifiesto = deposito.guardar_manifiesto({
        "csv_origen": str(entrada),
        "columna": corpus.COLUMNA_TEXTO,
        "notas_indexadas": len(indice),
        "notas_sin_texto": len(vacios),
        "agregados_esta_corrida": deposito.agregados,
    })

    peso = (rutas.VECTORES.stat().st_size / 1e6
            if rutas.VECTORES.exists() else 0.0)
    print(f"\nMatriz  : {len(deposito):,} x {deposito.dimension}  ({peso:.0f} MB)")
    print(f"Indice  : {len(indice):,} notas -> {rutas.INDICE.name}")
    print(f"Nuevos  : {deposito.agregados:,} textos vectorizados esta corrida")
    print(f"Manifiesto: {rutas.MANIFIESTO}")
    print(f"\nActualizado: {manifiesto['actualizado']}")
    print("El CSV de entrada no fue modificado.")


if __name__ == "__main__":
    main()
