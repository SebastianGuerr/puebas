"""
La ventana. Punto de entrada del paquete.

    python -m clustering.visor                 abre la ventana y la deja viva
    python -m clustering.visor --una-vez       calcula, dibuja y no refresca
    python -m clustering.visor --guardar       ademas escribe salidas/
    python -m clustering.visor --tamano-minimo 10

QUE ES 'EN VIVO'
    NLP/procesar.py y embedding/centinela.py estan corriendo: cada 15 minutos
    aparecen embeddings nuevos. La ventana comprueba el tamano y la fecha de
    los archivos de embedding/salidas/ y solo recalcula cuando cambiaron, asi
    que se puede dejar abierta y el mapa se va llenando solo.

    La comprobacion es barata (cuatro stat) y el recalculo caro (~1 minuto de
    UMAP). Por eso se comprueba seguido y se recalcula poco: al reves seria
    quemar CPU que ahora mismo necesita el pipeline.

ESTE PAQUETE NO ESCRIBE EN embedding/salidas/ NI EN NLP/salidas/
    Solo lee, y encima con reintentos (ver corpus.instantanea). Se puede abrir
    esta ventana con el pipeline a medias sin arriesgar nada de lo que lleva
    calculado, que es la razon de que exista.

POR QUE LA PRIMERA VEZ TARDA
    UMAP corre sobre numba y la primera llamada del proceso compila sus
    kernels: unos 40 segundos que no se repiten en los refrescos siguientes. No
    esta colgado. Va imprimiendo en que paso esta.
"""

import argparse
import time

from clustering import corpus, corrida as motor, mapa

# Segundos entre comprobaciones. No es cada cuanto se recalcula: es cada cuanto
# se mira si hace falta.
INTERVALO_DEFECTO = 60

# Repeticiones minimas para que un texto entre al mapa. UNO, es decir todos.
#
# Estaba en 15 y era un error grave: el 93% de los textos distintos aparece una
# sola vez, asi que con 15 el mapa se dibujaba con 5 de los 1.957 textos y
# parecia que no habia nada que agrupar. La cola larga no es sobra a limpiar,
# es el corpus (ver corpus.cargar).
MINIMO_DEFECTO = 1


def calcular(args, aviso=print):
    """Una corrida, contando por donde va. El aviso se puede silenciar."""
    aviso("Leyendo embeddings...")
    inicio = time.time()
    resultado = motor.ejecutar(
        minimo_notas=args.minimo_notas,
        vecinos=args.vecinos,
        tamano_minimo=args.tamano_minimo,
    )
    m = resultado.metricas
    aviso(f"  {m['textos']:,} textos distintos / {m['notas']:,} notas")
    aviso(f"  {m['clusters']} grupos, ruido {m['ruido_textos']:.0%} de los "
          f"textos ({m['ruido_notas']:.0%} de las notas)")
    aviso(f"  {time.time() - inicio:.0f}s")
    return resultado


def _mensaje(figura, texto):
    """Deja la ventana diciendo algo en vez de en blanco cuando algo falla."""
    figura.clear()
    eje = figura.add_subplot(111)
    eje.text(0.5, 0.5, texto, ha="center", va="center", fontsize=11,
             wrap=True, color="#444444")
    eje.set_axis_off()
    figura.canvas.draw_idle()


def _refrescar(figura, args, estado):
    """
    Recalcula y redibuja, pero solo si embedding/salidas/ cambio.

    Los errores no cierran la ventana: se escriben dentro. Un fallo tipico aqui
    es transitorio -- el pipeline reescribiendo el indice justo ahora, o
    todavia no hay puntos suficientes -- y matar la ventana por eso obligaria a
    relanzarla y a pagar otra vez el minuto de UMAP.
    """
    firma = corpus.firma()
    if firma is None:
        _mensaje(figura, "Todavia no hay embeddings en embedding/salidas/.\n"
                         "Esperando a que el pipeline cierre su primer bloque.")
        return
    if firma == estado.get("firma"):
        return

    estado["firma"] = firma
    try:
        resultado = calcular(args)
    except ImportError as error:
        _mensaje(figura, "Faltan dependencias: instala umap-learn y hdbscan.\n"
                         f"Detalle: {error}")
        return
    except (RuntimeError, ValueError, KeyError, OSError, SystemExit) as error:
        # Se olvida la firma para que la proxima comprobacion vuelva a
        # intentarlo. Dejandola puesta, un fallo transitorio -- que es el caso
        # normal aqui -- congelaria la ventana hasta que el pipeline escribiera
        # otra vez, o para siempre si ya termino.
        estado["firma"] = None
        _mensaje(figura, f"No se pudo agrupar todavia:\n\n{error}")
        return

    mapa.dibujar(figura, resultado)

    if args.guardar:
        motor.guardar(resultado)
        mapa.guardar(figura)
        print("  salidas escritas en clustering/salidas/")


def main():
    parser = argparse.ArgumentParser(
        description="Abre una ventana con el mapa de clusters de los motivos "
                    "de triage ya vectorizados. Solo lee embedding/salidas/.")
    parser.add_argument("--intervalo", type=float, default=INTERVALO_DEFECTO,
                        help="segundos entre comprobaciones (por defecto: 60)")
    parser.add_argument("--minimo-notas", type=int, default=MINIMO_DEFECTO,
                        help="repeticiones minimas por texto (por defecto: 1, "
                             "es decir todos)")
    parser.add_argument("--vecinos", type=int, default=None,
                        help="vecinos de UMAP: la escala de lo que se busca")
    parser.add_argument("--tamano-minimo", type=int, default=None,
                        help="grupo mas pequeno que cuenta como grupo")
    parser.add_argument("--una-vez", action="store_true",
                        help="calcula una sola vez y no refresca")
    parser.add_argument("--guardar", action="store_true",
                        help="escribe tambien clustering/salidas/")
    args = parser.parse_args()

    if args.intervalo <= 0 or args.minimo_notas < 1:
        parser.error("intervalo debe ser positivo y minimo-notas >= 1")

    # None significa 'el valor de agrupar.py', que es donde estan documentados.
    # Repetirlos aqui como default los duplicaria y se desincronizarian.
    from clustering import agrupar
    args.vecinos = args.vecinos or agrupar.VECINOS
    args.tamano_minimo = args.tamano_minimo or agrupar.TAMANO_MINIMO

    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    figura = plt.figure(figsize=(16.5, 9), facecolor="white")
    figura.canvas.manager.set_window_title("Clusters de motivos de triage")

    estado = {}
    _refrescar(figura, args, estado)

    if args.una_vez:
        plt.show()
        return

    print(f"\nVentana abierta. Comprueba cada {args.intervalo:.0f}s si el "
          f"pipeline agrego embeddings; recalcula solo si cambio.")
    animacion = FuncAnimation(
        figura,
        lambda _: _refrescar(figura, args, estado),
        interval=args.intervalo * 1000,
        cache_frame_data=False,
    )
    # FuncAnimation solo se mantiene viva mientras alguien la referencie; sin
    # esto el recolector se la lleva y la ventana deja de refrescarse.
    figura._animacion_visor = animacion
    plt.show()


if __name__ == "__main__":
    main()
