"""
Vigila la tabla `nota_triage` y vectoriza las notas nuevas segun van apareciendo.

    python -m embedding.centinela
    python -m embedding.centinela --intervalo 300     # mira cada 5 minutos

Se para con Ctrl+C. Cada vuelta deja el almacen consistente, asi que cortarlo
en cualquier momento es seguro.

POR QUE UN CENTINELA Y NO UN BUCLE EN POWERSHELL
    Se puede hacer 'while ($true) { python -m embedding.vectorizar; sleep 1800 }'
    y funciona. Pero cada vuelta arranca un proceso nuevo, y eso significa
    traer el modelo a memoria otra vez para un trabajo que muchas veces son
    quince segundos de vectorizar doscientas frases.

    Este modulo carga el modelo UNA vez y lo deja vivo entre pasadas. Con eso
    mirar cada minuto sale casi gratis, y el embedding va pegado a lo que
    NLP/procesar.py escribe en vez de ir media hora por detras.

QUE NO HACE
    No toca la tabla `nota_triage` jamas: solo la lee. El unico que la escribe es
    NLP/procesar.py.

CONVIVIR CON EL GENERADOR: EL PUNTO DELICADO
    DuckDB admite un solo escritor. NLP/procesar.py confirma cada 10 notas y
    SUELTA la base entre bloque y bloque, y eso es lo que deja entrar a este
    centinela. Aun asi las dos partes pueden coincidir: si al abrir la base
    esta tomada, esta vuelta se salta y se reintenta en la siguiente. No es un
    error, es el turno del otro.

    Por eso tambien se abre y se cierra la conexion en cada pasada en vez de
    conservarla: quedarsela bloquearia al generador, que es el que importa.
"""

import argparse
import time

from embedding import almacen, modelo, rutas, vectorizar

INTERVALO = 60


def _cuantas_notas():
    """Cuantas notas hay en `nota_triage`, o None si no se pudo mirar."""
    try:
        con = almacen.abrir(solo_lectura=True)
    except Exception:
        return None
    try:
        return con.execute("SELECT count(*) FROM nota_triage").fetchone()[0]
    except Exception:
        return None
    finally:
        con.close()


def main():
    parser = argparse.ArgumentParser(
        description="Vectoriza las notas nuevas segun aparecen.")
    parser.add_argument("--intervalo", type=int, default=INTERVALO,
                        help=f"segundos entre pasadas (por defecto {INTERVALO})")
    args = parser.parse_args()

    print(f"centinela sobre {rutas.BASE_DATOS}")
    print(f"  cada {args.intervalo} s | Ctrl+C para parar")

    codificador = None
    ultimas = None
    vuelta = 0

    try:
        while True:
            vuelta += 1
            # Si no hay notas nuevas desde la ultima pasada no hay nada que
            # hacer, y ni se abre la base para escribir. El caso comun es este.
            actuales = _cuantas_notas()
            if actuales is not None and actuales != ultimas:
                print(f"\n[{time.strftime('%H:%M:%S')}] vuelta {vuelta} | "
                      f"{actuales:,} notas en nota_triage")
                try:
                    if codificador is None:
                        codificador = modelo.Codificador()
                    con = almacen.abrir()
                    try:
                        vectorizar.correr(codificador=codificador, con=con)
                    finally:
                        con.close()
                    ultimas = actuales
                except Exception as error:
                    # Lo mas probable es que NLP/procesar.py tenga la base
                    # tomada. No se aborta: se reintenta en la vuelta siguiente
                    # y se deja 'ultimas' sin tocar para que lo vuelva a mirar.
                    print(f"  pasada saltada: {str(error)[:150]}")
            time.sleep(args.intervalo)
    except KeyboardInterrupt:
        print("\ncentinela detenido")


if __name__ == "__main__":
    main()
