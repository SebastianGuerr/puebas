"""
Mira la base mientras se llena, sin estorbar a quien la esta llenando.

    python -m NLP.monitor
    python -m NLP.monitor --intervalo 10
    python -m NLP.monitor --una-vez       # imprime y sale

POR QUE HACE FALTA UN MONITOR Y NO VALE DEJAR UN VISOR ABIERTO
    DuckDB admite un solo escritor, y un escritor bloquea tambien a los
    LECTORES. Medido el 2026-09-21 entre procesos:

        proceso A tiene la base      B escritor    B lector
        lectura-escritura            no            NO
        solo lectura                 no            si

    O sea: con la extension de VS Code adjunta a la base de verdad,
    'python -m NLP.procesar' no puede escribir. Y al reves, mientras procesar
    escribe, el visor no puede leer.

    Este modulo esquiva el empate abriendo y CERRANDO en cada vuelta, en vez
    de quedarse la conexion. Cada consulta dura milisegundos, y el escritor
    tambien suelta la base entre bloque y bloque, asi que los dos caben. Si
    justo coinciden, la vuelta se salta y se reintenta: no es un error.

    Para VS Code hay media solucion aparte: rutas.BASE_VISTA, una copia que
    el escritor refresca cada 20 s. Adjuntando VS Code a ESA copia, la corrida
    ya no se cae nunca -- que es el problema grave. Lo que no da es dato en
    vivo: mientras el visor la tiene abierta, Windows no deja sustituirla, asi
    que se congela hasta que el visor se desconecta y vuelve.

    Resumiendo, y sin adornos:
        seguir la corrida en vivo   -> este modulo
        explorar la tabla con SQL   -> VS Code sobre BASE_VISTA, reconectando
                                       cuando se quiera dato mas fresco

QUE ENSENA
    Lo que sirve para saber si la corrida va bien, no un volcado de la tabla:
    cuanto lleva, a que ritmo, cuanto falta, y las ultimas frases generadas
    para poder ver a ojo si el modelo esta diciendo cosas sensatas.
"""

import argparse
import time
from datetime import datetime

from NLP import rutas
from NLP.nucleo import almacen

INTERVALO = 15

# Cuantas notas tiene DIM_TRIAGE con HCTMOTCON no vacio. Medido el 2026-09-21
# contra la base clinica; es el denominador del avance. Si cambia, el ritmo se
# sigue calculando bien y solo el porcentaje queda desfasado.
TOTAL_ESPERADO = 95_036


def instantanea():
    """Una foto del estado. Abre y cierra: no se queda la base."""
    # reintentos=1 y diagnosticar=False: chocar con el escritor es lo normal
    # aqui, no una averia. Se quiere el error crudo para saltarse la vuelta,
    # no un SystemExit con instrucciones de desconectar VS Code.
    con = almacen.abrir(solo_lectura=True, reintentos=1, diagnosticar=False)
    try:
        notas, con_fecha, desde, hasta = con.execute("""
            SELECT count(*),
                   count(*) FILTER (WHERE fecha_triage IS NOT NULL),
                   min(fecha_triage), max(fecha_triage)
            FROM nota_triage
        """).fetchone()
        try:
            vectores = con.execute(
                "SELECT count(*) FROM embedding").fetchone()[0]
        except Exception:
            vectores = 0          # todavia no se ha vectorizado nada
        ultimas = con.execute("""
            SELECT OID, frase_procesada FROM nota_triage
            ORDER BY OID DESC LIMIT 5
        """).fetchall()
    finally:
        con.close()
    return {"notas": notas, "con_fecha": con_fecha, "desde": desde,
            "hasta": hasta, "vectores": vectores, "ultimas": ultimas}


def imprimir(foto, previa=None, segundos=None):
    ahora = datetime.now().strftime("%H:%M:%S")
    notas = foto["notas"]
    linea = (f"[{ahora}]  {notas:,} notas  "
             f"({100 * notas / TOTAL_ESPERADO:.1f}% de {TOTAL_ESPERADO:,})  |  "
             f"{foto['vectores']:,} vectorizadas")

    if previa and segundos:
        nuevas = notas - previa["notas"]
        ritmo = nuevas / segundos
        linea += f"  |  +{nuevas} ({ritmo * 60:.1f}/min)"
        if ritmo > 0:
            horas = (TOTAL_ESPERADO - notas) / ritmo / 3600
            linea += f"  |  faltan ~{horas:.1f} h"
    print(linea, flush=True)

    if foto["con_fecha"] != notas:
        print(f"           {notas - foto['con_fecha']:,} sin fecha_triage "
              f"-> python -m NLP.procesar --fechas", flush=True)


def main():
    parser = argparse.ArgumentParser(
        description="Mira la base mientras se llena, sin bloquearla.")
    parser.add_argument("--intervalo", type=int, default=INTERVALO,
                        help=f"segundos entre vistazos (por defecto {INTERVALO})")
    parser.add_argument("--una-vez", action="store_true",
                        help="imprime el estado y sale")
    parser.add_argument("--frases", action="store_true",
                        help="ensena tambien las ultimas frases generadas")
    args = parser.parse_args()

    if args.una_vez:
        foto = instantanea()
        imprimir(foto)
        for oid, frase in foto["ultimas"]:
            print(f"           {oid}  {frase}")
        return

    print(f"monitor sobre {rutas.BASE_DATOS}")
    print(f"  cada {args.intervalo} s | Ctrl+C para parar")
    print(f"  no bloquea: abre y cierra en cada vuelta\n")

    previa = None
    try:
        while True:
            try:
                foto = instantanea()
                imprimir(foto, previa, args.intervalo if previa else None)
                if args.frases:
                    for oid, frase in foto["ultimas"][:3]:
                        print(f"           {oid}  {str(frase)[:70]}")
                previa = foto
            except Exception as error:
                # Casi siempre: el escritor tiene la base en este instante.
                # Dura milisegundos, asi que la vuelta siguiente entra.
                print(f"[{datetime.now():%H:%M:%S}]  (ocupada, reintento) "
                      f"{str(error).splitlines()[0][:60]}", flush=True)
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\nmonitor detenido")


if __name__ == "__main__":
    main()
