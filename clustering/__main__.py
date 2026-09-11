"""
Punto de entrada unico de la fase 7. Un comando, de los embeddings a los grupos.

    python -m clustering

    Lee embedding/salidas/, reduce, agrupa, nombra cada grupo, funde los
    grupos en temas generales, escribe clustering/salidas/, imprime los temas
    con las notas que cayeron en cada uno, y abre la ventana del mapa. En ese
    orden y sin preguntar nada.

    python -m clustering --umbral 0.66         temas mas generales
    python -m clustering --sin-ventana         solo consola y archivos
    python -m clustering --notas 10            10 notas por tema en consola
    python -m clustering --vivo                deja la ventana refrescandose
    python -m clustering --barrido             prueba parametros y no agrupa

DOS NIVELES: GRUPO Y TEMA
    HDBSCAN encuentra grupos finos -- separa 'diarrea nauseas' de 'vomito
    diarrea fiebre' -- y para leer el corpus eso esta bien. Para contar cuantos
    triages de cada tipo llegan cada dia y cruzarlo contra el clima, no: un
    tema partido en tres son tres series flacas en vez de una con senal.

    Por eso hay un segundo nivel, que es el que manda de aqui en adelante. El
    grupo se queda al lado para poder bajar al detalle. Ver temas.py.

POR QUE ESTE ARCHIVO Y NO UNO QUE LO CONTENGA TODO
    Porque "un archivo con todo el proceso" y "un comando que haga todo el
    proceso" no son lo mismo, y lo que hace falta es lo segundo. Un modulo de
    mil lineas con la lectura, UMAP, HDBSCAN, el TF-IDF y matplotlib dentro
    daria el mismo comando y costaria dos cosas: no se podria tocar el
    agrupamiento sin arriesgar el dibujo, y el barrido -- que necesita agrupar
    cincuenta veces sin dibujar ni escribir una sola vez -- no tendria de donde
    colgarse.

    Asi que aqui no hay calculo. Este archivo decide QUE se hace y EN QUE
    ORDEN; cada paso sigue viviendo en su modulo:

        corpus.py    leer embedding/salidas/ sin tocarlo
        agrupar.py   UMAP + HDBSCAN
        etiquetas.py el nombre de cada grupo y de cada tema
        temas.py     fundir los grupos en temas generales
        corrida.py   encadena los cinco pasos y escribe salidas/
        mapa.py      el dibujo
        barrido.py   probar parametros y medirlos

LA VENTANA ES matplotlib Y NO plotly
    La exploracion del notebook era un px.scatter, que necesita un navegador y
    una celda viva. Esta ventana es del escritorio: se abre, se le hace zoom,
    se pasa el cursor por un punto y se lee el motivo de consulta que hay
    debajo. Con --vivo ademas se queda abierta y se va llenando sola mientras
    NLP/ y embedding/ siguen escribiendo, que en un navegador no se tiene.

SI ALGO FALLA
    Los dos fallos normales al principio son que embedding/salidas/ todavia no
    existe -- no se ha corrido 'python -m embedding.vectorizar' -- y que hay
    tan pocos textos que no hay densidad que encontrar. Los dos salen con un
    mensaje que dice que hacer, no con una traza.
"""

import argparse
import sys
import time


def _argumentos(argv=None):
    from clustering import agrupar, temas

    parser = argparse.ArgumentParser(
        prog="python -m clustering",
        description="Agrupa los motivos de triage ya vectorizados: escribe "
                    "clustering/salidas/, imprime los grupos y abre el mapa.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Los parametros de agrupamiento se eligen con --barrido, no a "
               "ojo. Sus valores por defecto estan documentados en agrupar.py.")

    grupo = parser.add_argument_group("parametros del agrupamiento")
    grupo.add_argument("--dimensiones", type=int, default=agrupar.DIMENSIONES,
                       help=f"dimensiones sobre las que se agrupa "
                            f"(por defecto: {agrupar.DIMENSIONES})")
    grupo.add_argument("--vecinos", type=int, default=agrupar.VECINOS,
                       help=f"vecinos de UMAP: la escala de lo que se busca "
                            f"(por defecto: {agrupar.VECINOS})")
    grupo.add_argument("--tamano-minimo", type=int, default=agrupar.TAMANO_MINIMO,
                       help=f"grupo mas pequeno que cuenta como grupo "
                            f"(por defecto: {agrupar.TAMANO_MINIMO})")
    grupo.add_argument("--muestras-minimas", type=int,
                       default=agrupar.MUESTRAS_MINIMAS,
                       help="cuanta evidencia exige para declarar densidad: "
                            "bajarlo rescata cola larga del ruido "
                            f"(por defecto: {agrupar.MUESTRAS_MINIMAS or 'igual al tamano minimo'})")
    grupo.add_argument("--epsilon", type=float, default=agrupar.EPSILON,
                       help=f"distancia bajo la cual dos micro-grupos son el "
                            f"mismo (por defecto: {agrupar.EPSILON})")
    grupo.add_argument("--umbral", type=float, default=temas.UMBRAL,
                       help="coseno minimo para que dos grupos sean el mismo "
                            "TEMA. Es el grano del analisis temporal "
                            f"(por defecto: {temas.UMBRAL})")
    grupo.add_argument("--temas", type=int, default=temas.TEMAS,
                       help="forzar exactamente N temas en vez de usar el "
                            "umbral. No deja grupos sueltos, pero tampoco "
                            "garantiza que los temas signifiquen algo")
    # 1 significa 'todos los textos entran', y es el unico valor sensato por
    # defecto. Estuvo en 15 y fue un error grave: el 93% de los textos
    # distintos aparece una sola vez, asi que con 15 se agrupaban 5 de los
    # 1.957 y parecia que el corpus no tenia estructura. La cola larga no es
    # sobra que limpiar, es el corpus (ver corpus.cargar). La opcion existe
    # para lo contrario -- mirar solo lo que se repite -- y no para 'limpiar'.
    grupo.add_argument("--minimo-notas", type=int, default=1,
                       help="repeticiones minimas para que un texto entre "
                            "(por defecto: 1, es decir todos)")

    salida = parser.add_argument_group("que se hace con el resultado")
    salida.add_argument("--notas", type=int, default=5, metavar="N",
                        help="cuantas notas de cada grupo se imprimen en "
                             "consola; 0 las omite (por defecto: 5)")
    salida.add_argument("--sin-ventana", action="store_true",
                        help="no abre el mapa: solo consola y archivos")
    salida.add_argument("--sin-guardar", action="store_true",
                        help="no escribe clustering/salidas/")
    salida.add_argument("--vivo", action="store_true",
                        help="deja la ventana abierta recalculando cuando el "
                             "pipeline agregue embeddings")
    salida.add_argument("--intervalo", type=float, default=60,
                        help="con --vivo, segundos entre comprobaciones "
                             "(por defecto: 60)")

    otros = parser.add_argument_group("otros modos")
    otros.add_argument("--barrido", action="store_true",
                       help="prueba combinaciones de parametros, escribe "
                            "salidas/barrido.csv y sale sin agrupar")

    args = parser.parse_args(argv)

    if args.minimo_notas < 1:
        parser.error("--minimo-notas tiene que ser 1 o mas")
    if args.notas < 0:
        parser.error("--notas no puede ser negativo")
    if args.dimensiones < 2:
        parser.error("--dimensiones tiene que ser 2 o mas")
    if args.tamano_minimo < 2:
        parser.error("--tamano-minimo tiene que ser 2 o mas")
    if args.temas is not None and args.temas < 2:
        parser.error("--temas tiene que ser 2 o mas")
    if not 0 < args.umbral < 1:
        parser.error("--umbral es un coseno: tiene que estar entre 0 y 1")
    if args.vivo and args.sin_ventana:
        parser.error("--vivo abre una ventana: no se puede con --sin-ventana")

    # --guardar es lo contrario de --sin-guardar. Se traduce aqui para que el
    # resto del modulo y el visor lean el mismo atributo.
    args.guardar = not args.sin_guardar
    return args


# ==========================================================
# LO QUE SE IMPRIME
# ==========================================================

def _notas_por_tema(corrida, cuantas):
    """
    Las notas de cada TEMA, con los grupos que lo componen listados encima.

    Es la parte que permite juzgar la fusion sin abrir un archivo. Un nombre de
    tres palabras se puede leer de varias formas; el nombre, la lista de grupos
    que se fundieron y cinco notas seguidas, ya no. Si un tema junto cosas que
    no tienen la misma causa -- que es lo unico que importa cuando esto se
    cruce contra el clima -- aqui se ve.

    Va por tema y no por grupo porque el tema es el nivel con el que se va a
    trabajar. El detalle por grupo esta en salidas/notas.csv, que viene
    ordenado igual que esto.

    Se imprimen NOTAS y no textos distintos a proposito, aunque eso signifique
    ver la misma frase repetida: esa repeticion es el peso real del tema, y
    esconderla haria parecer pequeno a un tema de 400 notas.
    """
    if not cuantas:
        return ""

    notas = corrida.notas()
    grupos = corrida.tabla()
    lineas = ["", "=" * 78,
              f"LAS NOTAS DE CADA TEMA  (las {cuantas} de mas confianza; "
              f"todas en salidas/notas.csv)", "=" * 78]

    for fila in corrida.tabla_temas().itertuples(index=False):
        if fila.tema == -1:
            continue
        dentro = grupos[grupos["tema"] == fila.tema]
        etiquetas = ", ".join(f"{int(g.cluster)}:{g.nombre}"
                              for g in dentro.itertuples(index=False))
        lineas += [
            "",
            f"[tema {fila.tema}] {fila.nombre}"
            f"   -- {fila.notas:,} notas ({fila.parte:.1%}), "
            f"{fila.grupos} grupo(s)",
            f"     funde: {_recortar(etiquetas, 150)}",
        ]
        bloque = notas[notas["tema"] == fila.tema].head(cuantas)
        for nota in bloque.itertuples(index=False):
            lineas.append(f"     {nota.confianza:.2f}  "
                          f"{_recortar(nota.texto, 98)}")

    sin_tema = notas[notas["tema"] == -1]
    if not sin_tema.empty:
        lineas += [
            "",
            f"[sin tema] {len(sin_tema):,} notas no entraron a ningun grupo,",
            "     asi que tampoco a ningun tema. No es un fallo: un motivo que",
            "     nadie mas escribio de forma parecida no pertenece a ninguna",
            "     parte. Siguen contando para el total de llegadas al hospital;",
            "     lo unico que no se les puede atribuir es un motivo.",
        ]
    return "\n".join(lineas)


def _recortar(texto, largo):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= largo else texto[:largo - 3] + "..."


def _donde_quedo():
    from clustering import rutas
    return "\n".join([
        "",
        "=" * 78,
        "ESCRITO EN clustering/salidas/",
        "=" * 78,
        "  temas.csv           un renglon por TEMA. Es el que se abre primero.",
        "  clusters.csv        un renglon por grupo, con el tema de cada uno.",
        "  notas.csv           un renglon por nota, ordenado por tema y grupo.",
        "  asignacion.parquet  OID -> tema y cluster. El del cruce temporal.",
        "  proyeccion.parquet  las coordenadas del mapa, ya calculadas.",
        "  informe.txt         esto mismo, para poder compararlo manana.",
        "",
        f"  {rutas.SALIDAS}",
    ])


# ==========================================================
# LOS MODOS
# ==========================================================

def _barrido(args):
    """Prueba parametros, escribe barrido.csv y no agrupa nada en firme."""
    from clustering import barrido

    print("Barrido de parametros. Una reduccion por cada (vecinos, dimensiones);")
    print("las combinaciones de HDBSCAN encima son casi gratis.\n")
    inicio = time.time()
    tabla = barrido.ejecutar(minimo_notas=args.minimo_notas)
    print(f"\n{len(tabla)} combinaciones en {time.time() - inicio:.0f}s\n")
    print(barrido.texto(tabla))
    print(f"Tabla completa en {barrido.guardar(tabla)}")
    return 0


def _corrida(args):
    """La corrida normal: calcular, escribir, imprimir y dibujar."""
    from clustering import corrida as motor, mapa

    print("Leyendo embedding/salidas/ ...")
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
    print(f"  {time.time() - inicio:.0f}s\n")

    print(motor.informe(resultado))
    print(_notas_por_tema(resultado, args.notas))

    if args.guardar:
        motor.guardar(resultado)
        print(_donde_quedo())

    if args.sin_ventana:
        return 0

    import matplotlib.pyplot as plt

    figura = plt.figure(figsize=(16.5, 9), facecolor="white")
    figura.canvas.manager.set_window_title("Clusters de motivos de triage")
    mapa.dibujar(figura, resultado)

    if args.guardar:
        print(f"\n  mapa escrito en {mapa.guardar(figura)}")

    if args.vivo:
        from clustering import visor
        visor.vivo(figura, args, firma_inicial=resultado.firma)
        return 0

    print("\nVentana abierta. Pasa el cursor por un punto para leer el motivo.")
    plt.show()
    return 0


def main(argv=None):
    args = _argumentos(argv)
    try:
        return _barrido(args) if args.barrido else _corrida(args)
    except ImportError as error:
        # Es el fallo de la primera vez en una maquina nueva y merece decir que
        # instalar, no una traza de veinte lineas.
        print(f"\nFalta una dependencia: {error}\n"
              f"  pip install umap-learn hdbscan matplotlib pyarrow",
              file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nCortado.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
