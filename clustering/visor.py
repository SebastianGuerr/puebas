"""
La ventana que se refresca sola mientras el pipeline sigue escribiendo.

    python -m clustering --vivo

EL PUNTO DE ENTRADA ES __main__.py, NO ESTE ARCHIVO
    Aqui esta el bucle de refresco y nada mas. La linea de comandos, el orden
    de los pasos y la escritura de salidas/ viven en __main__.py, para que haya
    un solo sitio donde mirar que hace el comando. 'python -m clustering.visor'
    sigue funcionando y es un atajo de 'python -m clustering --vivo'.

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

import time

from clustering import corpus, corrida as motor, mapa


def calcular(args, aviso=print):
    """Una corrida, contando por donde va. El aviso se puede silenciar."""
    aviso("Leyendo embeddings...")
    inicio = time.time()
    resultado = motor.ejecutar(
        minimo_notas=args.minimo_notas,
        vecinos=args.vecinos,
        dimensiones=args.dimensiones,
        tamano_minimo=args.tamano_minimo,
        muestras_minimas=args.muestras_minimas,
        epsilon=args.epsilon,
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


def vivo(figura, args, firma_inicial=None):
    """
    Deja la ventana abierta, recalculando solo cuando embedding/salidas/ cambie.

    Recibe la figura YA DIBUJADA por __main__.py con la primera corrida, y
    firma_inicial es el estado de embedding/salidas/ con el que se calculo esa
    primera. Sin ese dato el bucle no sabria que ya esta dibujado lo ultimo y
    repetiria el minuto de UMAP nada mas abrir la ventana, para pintar
    exactamente lo mismo.

    No vuelve hasta que se cierra la ventana.
    """
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    print(f"\nVentana abierta. Comprueba cada {args.intervalo:.0f}s si el "
          f"pipeline agrego embeddings; recalcula solo si cambio.")

    estado = {"firma": firma_inicial}
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


def main():
    """
    Atajo historico: 'python -m clustering.visor' == 'python -m clustering --vivo'.

    Se delega en vez de tener otro argparse aqui. Dos analizadores de linea de
    comandos sobre los mismos parametros se desincronizan a la primera opcion
    que se agregue en uno y se olvide en el otro, y el sintoma es que la misma
    bandera hace cosas distintas segun como se invoque.
    """
    import sys

    from clustering.__main__ import main as principal
    return principal(sys.argv[1:] + ["--vivo"])


if __name__ == "__main__":
    import sys
    sys.exit(main())
