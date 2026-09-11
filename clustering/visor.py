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

    La comprobacion es barata (cuatro stat) y el recalculo caro -- sobre 6.001
    notas son unos 100 segundos, y crece con el corpus. Por eso se comprueba
    seguido y se recalcula poco: al reves seria quemar CPU que ahora mismo
    necesita el pipeline.

    Y por eso el recalculo va EN UN HILO APARTE (ver _lanzar). Durante esos
    cien segundos la ventana sigue viva: se le hace zoom, se pasa el cursor por
    los puntos y se lee el mapa de la corrida anterior, con un renglon abajo a
    la derecha que dice que hay otra en marcha y cuanto lleva.

ESTE PAQUETE NO ESCRIBE EN embedding/salidas/ NI EN NLP/salidas/
    Solo lee, y encima con reintentos (ver corpus.instantanea). Se puede abrir
    esta ventana con el pipeline a medias sin arriesgar nada de lo que lleva
    calculado, que es la razon de que exista.

POR QUE LA PRIMERA VEZ TARDA
    UMAP corre sobre numba y la primera llamada del proceso compila sus
    kernels: unos 40 segundos que no se repiten en los refrescos siguientes. No
    esta colgado. Va imprimiendo en que paso esta.
"""

import threading
import time

from clustering import corpus, corrida as motor, mapa


def calcular(args, aviso=print):
    """
    Una corrida, contando por donde va. El aviso se puede silenciar.

    Pasa TODOS los parametros de args, incluidos los del segundo nivel. No es
    un detalle: si aqui falta uno, la primera corrida -- la que hace
    __main__.py -- sale con lo que se pidio por linea de comandos y los
    refrescos siguientes salen con los valores por defecto, asi que la ventana
    cambiaria sola de criterio al cabo de un rato sin decir nada.
    """
    aviso("Leyendo embeddings...")
    inicio = time.time()
    resultado = motor.ejecutar(
        minimo_notas=args.minimo_notas,
        vecinos=args.vecinos,
        dimensiones=args.dimensiones,
        tamano_minimo=args.tamano_minimo,
        muestras_minimas=args.muestras_minimas,
        epsilon=args.epsilon,
        n_temas=args.temas,
        umbral=args.umbral,
    )
    m = resultado.metricas
    aviso(f"  {m['textos']:,} textos distintos / {m['notas']:,} notas")
    aviso(f"  {m.get('temas', 0)} temas sobre {m['clusters']} grupos, "
          f"ruido {m['ruido_notas']:.0%} de las notas")
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


def _aviso(figura, texto):
    """
    Un renglon de estado en la esquina, SIN borrar el mapa que ya esta.

    _mensaje() vacia la figura y sirve para cuando no hay ningun mapa que ensenar.
    Este es lo contrario: el mapa de la corrida anterior sigue ahi, se le puede
    hacer zoom y pasar el cursor por encima, y este renglon dice que hay otra
    corrida en marcha. Es lo que convierte la espera en algo que se puede usar.

    Se guarda el artista en la figura porque mapa.dibujar() llama a clear() y
    se lo lleva por delante; asi se vuelve a crear cuando hace falta en vez de
    acumular uno por refresco.
    """
    artista = getattr(figura, "_visor_aviso", None)
    if artista is None or artista.figure is not figura:
        artista = figura.text(0.995, 0.005, "", ha="right", va="bottom",
                              fontsize=8, color="#8a8a8a")
        figura._visor_aviso = artista
    artista.set_text(texto)
    figura.canvas.draw_idle()


def _lanzar(args, estado):
    """
    Arranca el calculo en un hilo aparte y vuelve enseguida.

    POR QUE UN HILO Y NO LLAMAR A calcular() Y YA
        Porque el callback que llama a esto corre en el hilo de la interfaz, y
        mientras no vuelva la ventana esta muerta: no repinta, no hace zoom, no
        responde al raton, y Windows la marca como 'no responde'. Sobre 6.001
        notas el recalculo son unos 100 segundos, y crece con el corpus; a
        30.000 notas seran varios minutos de ventana congelada cada vez que el
        centinela escriba. Una ventana que se anuncia 'en vivo' no puede pasar
        la mayor parte del tiempo bloqueada.

        Con el hilo, durante el recalculo se sigue viendo y usando el mapa
        anterior, que es informacion perfectamente valida -- solo le faltan las
        notas de los ultimos minutos.

    EL REPARTO DE TRABAJO ENTRE HILOS ES ESTRICTO
        El hilo solo CALCULA y deja el resultado en un buzon. Todo lo que toca
        matplotlib -- dibujar, guardar el png -- se queda en el hilo principal,
        en _recoger(). matplotlib no es seguro entre hilos y saltarse esto da
        fallos que no se reproducen dos veces igual.

    daemon=True para que cerrar la ventana no deje el proceso colgado
    esperando a que termine un UMAP que ya no le importa a nadie.
    """
    def trabajo():
        try:
            estado["buzon"] = ("ok", calcular(args))
        except BaseException as error:      # noqa: BLE001 -- se reenvia entero
            estado["buzon"] = ("error", error)

    estado["buzon"] = None
    estado["inicio"] = time.time()
    estado["hilo"] = threading.Thread(target=trabajo, daemon=True)
    estado["hilo"].start()


def _recoger(figura, args, estado):
    """
    Recoge lo que dejo el hilo y dibuja. Corre en el hilo principal.

    Los errores no cierran la ventana: se escriben dentro. Un fallo tipico aqui
    es transitorio -- el pipeline reescribiendo el indice justo ahora, o
    todavia no hay puntos suficientes -- y matar la ventana por eso obligaria a
    relanzarla y a pagar otra vez el minuto de UMAP.
    """
    clase, carga = estado.pop("buzon")
    estado["hilo"] = None

    if clase == "error":
        if isinstance(carga, ImportError):
            _mensaje(figura, "Faltan dependencias: instala umap-learn y "
                             f"hdbscan.\nDetalle: {carga}")
            return
        if not isinstance(carga, (RuntimeError, ValueError, KeyError,
                                  OSError, SystemExit)):
            raise carga
        # Se olvida la firma para que la proxima comprobacion vuelva a
        # intentarlo. Dejandola puesta, un fallo transitorio -- que es el caso
        # normal aqui -- congelaria la ventana hasta que el pipeline escribiera
        # otra vez, o para siempre si ya termino.
        estado["firma"] = None
        _aviso(figura, f"no se pudo agrupar: {carga}")
        return

    mapa.dibujar(figura, carga)

    if args.guardar:
        motor.guardar(carga)
        mapa.guardar(figura)
        print("  salidas escritas en clustering/salidas/")

    _aviso(figura, f"actualizado {time.strftime('%H:%M:%S')}  --  "
                   f"{carga.metricas['notas']:,} notas")


# Cada cuanto LATE la animacion, que no es cada cuanto se mira el disco.
#
# Son dos ritmos distintos y mezclarlos estropea uno de los dos. El latido
# tiene que ser corto para que el contador de 'recalculando... 34s' avance a la
# vista y para recoger el resultado del hilo apenas esta; --intervalo tiene que
# poder ser largo, porque es cada cuanto se mira si el pipeline escribio y esa
# es una pregunta que no hace falta hacerse cada dos segundos. Con un solo
# ritmo, o el contador va a saltos de un minuto o se mira el disco sin parar.
LATIDO = 2.0


def _refrescar(figura, args, estado):
    """
    Una vuelta del bucle. Decide entre esperar, recoger o lanzar.

    Se llama cada LATIDO segundos y casi siempre no hace nada. Mirar si
    embedding/salidas/ cambio son cuatro stat() y ni eso se hace en cada vuelta:
    solo cuando han pasado args.intervalo segundos desde la ultima vez.
    """
    if estado.get("buzon") is not None:
        _recoger(figura, args, estado)
        return

    if estado.get("hilo") is not None:
        _aviso(figura, f"recalculando... {time.time() - estado['inicio']:.0f}s "
                       f"(el mapa que se ve es el de la corrida anterior)")
        return

    ahora = time.time()
    if ahora - estado.get("mirado", 0.0) < args.intervalo:
        return
    estado["mirado"] = ahora

    firma = corpus.firma()
    if firma is None:
        _mensaje(figura, "Todavia no hay embeddings en embedding/salidas/.\n"
                         "Esperando a que el pipeline cierre su primer bloque.")
        return
    if firma == estado.get("firma"):
        return

    estado["firma"] = firma
    _lanzar(args, estado)
    _aviso(figura, "embeddings nuevos: recalculando...")


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
    print("El recalculo corre aparte: la ventana sigue usandose mientras tanto,"
          "\nmostrando el mapa anterior hasta que el nuevo este listo.")

    # 'mirado' arranca en ahora y no en cero para no mirar el disco en el primer
    # latido: __main__.py acaba de calcular y dibujar, y firma_inicial ya dice
    # con que estado. Mirar ahora solo puede dar lo mismo.
    estado = {"firma": firma_inicial, "mirado": time.time()}
    animacion = FuncAnimation(
        figura,
        lambda _: _refrescar(figura, args, estado),
        interval=LATIDO * 1000,
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
