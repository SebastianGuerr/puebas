"""
Llena la tabla `nota_triage`: base de datos clinica -> Qwen3 -> base del proyecto.

    python -m NLP.procesar
    python -m NLP.procesar --limite 500
    python -m NLP.procesar --fechas                # solo rellena fecha_triage
    python -m NLP.procesar --estado                # que hay guardado, sin tocar
    python -m NLP.procesar --importar-csv          # migra un triage_limpio.csv
    python -m NLP.procesar --rehacer               # vacia la tabla y empieza

Es el unico archivo del proyecto que conoce la base clinica. De DIM_TRIAGE baja
TRES columnas y nada mas:

    OID          el identificador de la nota
    HCTFECTRI    la fecha real del triage
    HCTMOTCON    lo que escribio el auxiliar

Le pasa la tercera al modelo con el prompt de NLP/prompt.py —que lleva
inyectados los diccionarios del hospital— y escribe las cuatro columnas de
`nota_triage`:

    OID, fecha_triage, frase_original, frase_procesada

SOLO TRES COLUMNAS DE LAS TRECE QUE TIENE DIM_TRIAGE
    Las otras diez son nombre, segundo nombre, apellidos, documento, edad,
    medico y codigos administrativos: dato identificable de pacientes reales
    que no tiene por que salir de la base clinica. Esta tabla es la copia
    minima que necesita el analisis. Ver la regla 1 de CLAUDE.md.

YA NO SE ESCRIBE UN CSV
    Hasta el 2026-09-21 la salida era salidas/triage_limpio.csv. El CSV cumplio
    mientras esto era el final del camino, y dejo de servir en cuanto hubo que
    cruzarlo: la frase de una nota tiene que juntarse con su vector y con su
    fecha. Eso es un JOIN. El CSV anterior no se pierde: --importar-csv lo mete
    en la tabla sin volver a consultar la base clinica, que es lo caro.

REANUDACION
    Por OID contra la tabla, igual que antes contra el CSV pero sin leerlo
    entero: es una consulta sobre la clave primaria. Una interrupcion conserva
    lo ya escrito y la siguiente ejecucion pide a la base clinica unicamente
    las notas que faltan.

    Se confirma cada BLOQUE notas y se SUELTA la base entre bloque y bloque.
    DuckDB admite un solo escritor, y asi 'python -m embedding.centinela' puede
    ir vectorizando lo que va saliendo en vez de esperar a que esto termine.

El flujo completo y el papel de cada archivo estan en NLP/docs/FLUJO.md.
"""

import argparse
import sys
import time

from NLP import modelo as motor
from NLP import rutas
from NLP.nucleo import almacen, datos
from NLP.prompt import VERSION, construir

# ==========================================================
# CONFIGURACION
# ==========================================================

TABLA = "DIM_TRIAGE"
COLUMNA = "HCTMOTCON"        # la frase cruda
COLUMNA_FECHA = "HCTFECTRI"  # la fecha real del triage
LLAVE = "OID"

COLUMNAS_BD = [LLAVE, COLUMNA_FECHA, COLUMNA]

# Modelo elegido tras comparar siete en Ollama. Se puede pisar con --modelo.
MODELO = "qwen3:8b"

# Timeout por nota. Alto a proposito: una nota larga en CPU puede tardar
# minutos y cortarla obliga a repetirla entera en la siguiente corrida.
TIMEOUT = 1800

# Cada cuantas notas se confirma y se suelta la base. Pequeno a proposito: es
# lo maximo que puede perder una interrupcion, y cada confirmacion abre una
# ventana para que el centinela de embedding/ entre a leer.
BLOQUE = 10


# ==========================================================
# GENERACION
# ==========================================================

def optimizar(nota, modelo=MODELO, timeout=TIMEOUT):
    """Motivo de consulta estandarizado de UNA nota, ya limpio de razonamiento."""
    _, respuesta = motor.generar(modelo, construir(str(nota[COLUMNA])), timeout)
    return motor.limpiar(respuesta.get("response", ""))


def fila_optimizada(nota, generar):
    """Convierte una nota de la consulta en las columnas de `nota_triage`."""
    texto = str(nota[COLUMNA])
    return {
        LLAVE: nota[LLAVE],
        "fecha_triage": nota.get(COLUMNA_FECHA),
        "frase_original": texto,
        "frase_procesada": generar(texto),
    }


# ==========================================================
# SUBCOMANDOS
# ==========================================================

def _estado():
    total = almacen.contar()
    print(f"  {rutas.BASE_DATOS}")
    print(f"  nota_triage: {total:,} notas")
    if not total:
        return
    con = almacen.abrir(solo_lectura=True)
    try:
        print(con.execute("""
            SELECT count(*) FILTER (WHERE frase_procesada IS NOT NULL) AS procesadas,
                   count(*) FILTER (WHERE fecha_triage IS NULL)        AS sin_fecha,
                   min(fecha_triage) AS desde, max(fecha_triage) AS hasta
            FROM nota_triage
        """).df().to_string(index=False))
    finally:
        con.close()


def _rellenar_fechas():
    """Baja OID+HCTFECTRI y completa las notas que no tienen fecha."""
    from NLP.nucleo.conexion_bd import obtener_engine

    faltan = almacen.sin_fecha()
    if not faltan:
        print("  todas las notas guardadas ya tienen fecha_triage")
        return
    print(f"  {faltan:,} notas sin fecha. Conectando BD...")

    engine = obtener_engine()
    tabla = datos.solo_columnas(engine, TABLA, [LLAVE, COLUMNA_FECHA])
    print(f"  {len(tabla):,} fechas bajadas de {TABLA}")

    con = almacen.abrir(solo_lectura=True)
    try:
        pendientes = {fila[0] for fila in con.execute(
            "SELECT OID FROM nota_triage WHERE fecha_triage IS NULL"
        ).fetchall()}
    finally:
        con.close()

    pares = [(fila[LLAVE], fila[COLUMNA_FECHA])
             for fila in tabla.to_dict("records")
             if fila[LLAVE] in pendientes]
    escritas = almacen.guardar_fechas(pares)
    print(f"  {escritas:,} fechas escritas | quedan sin fecha: "
          f"{almacen.sin_fecha():,}")


# ==========================================================
# MAIN
# ==========================================================

def main():
    parser = argparse.ArgumentParser(
        description="Llena nota_triage con Qwen3 y reanudacion por OID.")
    parser.add_argument("--limite", type=int, default=None,
                        help="limita la cantidad de notas de esta ejecucion")
    parser.add_argument("--modelo", default=MODELO,
                        help="modelo instalado en Ollama")
    parser.add_argument("--rehacer", action="store_true",
                        help="vacia nota_triage y empieza desde cero")
    parser.add_argument("--estado", action="store_true",
                        help="imprime que hay guardado y sale")
    parser.add_argument("--fechas", action="store_true",
                        help="solo rellena fecha_triage donde falte")
    parser.add_argument("--importar-csv", nargs="?", const=str(rutas.TRIAGE_LIMPIO),
                        default=None, metavar="RUTA",
                        help="mete un triage_limpio.csv anterior en la tabla")
    args = parser.parse_args()

    if args.estado:
        _estado()
        return

    if args.importar_csv:
        print(f"Importando {args.importar_csv}")
        resumen = almacen.importar_csv(args.importar_csv)
        print(f"  {resumen['leidas']:,} leidas | "
              f"{resumen['repetidos']:,} OID repetidos (gana el ultimo) | "
              f"{resumen['escritas']:,} escritas")
        if resumen["sin_fecha"]:
            print(f"  {resumen['sin_fecha']:,} sin fecha_triage: el CSV no la "
                  f"traia. Completala con 'python -m NLP.procesar --fechas'.")
        _estado()
        return

    if args.fechas:
        _rellenar_fechas()
        return

    if args.rehacer:
        borrado = almacen.vaciar()
        print(f"--rehacer: {borrado['notas']:,} notas borradas de nota_triage")
        if borrado["vectores"]:
            print(f"           {borrado['vectores']:,} vectores borrados "
                  f"tambien (la clave foranea lo exige). Se rehacen con "
                  f"'python -m embedding.vectorizar'.")
        hechas = set()
    else:
        hechas = almacen.oids_hechos()
        if hechas:
            print(f"OID ya procesados: {len(hechas):,}; se omitiran al "
                  f"consultar la BD")

    print(f"Modelo: {args.modelo} | Prompt: {VERSION}")
    print("Comprobando Ollama...")
    motor.verificar(args.modelo)

    from NLP.nucleo.conexion_bd import obtener_engine

    filtro = datos.filtro_no_vacio(COLUMNA)
    print("Conectando BD...")
    engine = obtener_engine()
    notas = datos.muestra(
        engine, TABLA, COLUMNAS_BD, filtro,
        limite=args.limite, disperso=False, llave=LLAVE, excluir=hechas,
    )
    print(f"Notas nuevas: {len(notas):,}")
    if notas.empty:
        print("No hay notas nuevas por procesar.")
        return

    procesadas = 0
    inicio = time.time()
    with almacen.Escritor(bloque=BLOQUE) as escritor:
        try:
            for _, nota in notas.iterrows():
                fila = fila_optimizada(
                    nota, lambda texto: optimizar(nota, args.modelo))
                escritor.agregar(fila)
                procesadas += 1
                print(f"[{procesadas}/{len(notas)}] OID {fila[LLAVE]} | "
                      f"{fila['frase_procesada'][:100]}")
                sys.stdout.flush()
        except KeyboardInterrupt:
            print("\nInterrumpido. Se baja el bloque pendiente y se conserva "
                  "todo lo anterior.")

    print(f"Listo: {procesadas:,} notas nuevas en {time.time() - inicio:.1f} s")
    print(f"Base: {rutas.BASE_DATOS}  "
          f"(nota_triage: {almacen.contar():,} notas)")


if __name__ == "__main__":
    main()
