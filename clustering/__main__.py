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
    python -m clustering --validar             pone a prueba las decisiones
    python -m clustering --anclar              fija la identidad de los temas
    python -m clustering --serie               la serie diaria para la fase 8
    python -m clustering --puente              ¿se puede cruzar con el calendario?

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
        validacion.py poner a prueba que el resultado valga algo
        anclas.py    la identidad permanente de los temas entre corridas
        fechas.py    el puente a la fase 8: OID -> fecha -> serie diaria

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
    # --barrido elige entre configuraciones; --validar pregunta si alguna vale.
    # Son las dos mitades de la misma duda y por eso viven juntas aqui.
    otros.add_argument("--validar", action="store_true",
                       help="pone a prueba las decisiones del agrupamiento "
                            "(modelo nulo, estabilidad, siluetas, codo de "
                            "temas, catalogo clinico) y sale sin agrupar")
    otros.add_argument("--rapido", action="store_true",
                       help="con --validar, omite las pruebas que vuelven a "
                            "reducir: segundos en vez de minutos, y sin "
                            "respuesta sobre estabilidad")

    # LOS TRES MODOS DE LA FASE 8. Van aqui y no en un paquete aparte porque
    # los tres se apoyan en una corrida del agrupamiento y en nada mas; el
    # analisis contra el clima si sera otro paquete.
    puente = parser.add_argument_group(
        "el puente a la fase 8 (cruce contra fechas y calendario)")
    puente.add_argument("--anclar", action="store_true",
                        help="fija la identidad permanente de los temas en "
                             "datos/anclas.csv. Sin esto los numeros de tema "
                             "cambian entre corridas y ninguna serie temporal "
                             "significa nada")
    puente.add_argument("--rehacer", action="store_true",
                        help="con --anclar, reemplaza unas anclas que ya "
                             "existan. EMPIEZA UNA SERIE NUEVA: lo calculado "
                             "antes deja de ser comparable")
    puente.add_argument("--serie", action="store_true",
                        help="construye salidas/serie_diaria.csv: notas por "
                             "tema y por dia con sus denominadores, lista para "
                             "cruzar contra clima y calendario")
    puente.add_argument("--puente", action="store_true",
                        help="dice si el proyecto esta en condiciones de "
                             "cruzar contra el calendario y que falta. No "
                             "calcula nada: solo comprueba")

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
    if args.rapido and not args.validar:
        parser.error("--rapido solo significa algo junto a --validar")
    if args.rehacer and not args.anclar:
        parser.error("--rehacer solo significa algo junto a --anclar")
    modos = (args.barrido, args.validar, args.anclar, args.serie, args.puente)
    if sum(bool(modo) for modo in modos) > 1:
        parser.error("--barrido, --validar, --anclar, --serie y --puente son "
                     "modos distintos: uno a la vez")

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


def _validar(args):
    """Pone a prueba las decisiones del agrupamiento y no agrupa en firme."""
    from clustering import validacion

    print("Validacion del agrupamiento. --barrido elige entre configuraciones;")
    print("esto pregunta si alguna vale.\n")
    inicio = time.time()
    resultado = validacion.ejecutar(
        minimo_notas=args.minimo_notas,
        rapido=args.rapido,
        vecinos=args.vecinos,
        dimensiones=args.dimensiones,
        tamano_minimo=args.tamano_minimo,
        muestras_minimas=args.muestras_minimas,
        epsilon=args.epsilon,
    )
    print(f"\n  {time.time() - inicio:.0f}s\n")
    print(validacion.texto(resultado))

    if args.guardar:
        print(f"Informe en {validacion.guardar(resultado)}")

    # La figura se dibuja siempre que se vaya a mostrar o a guardar algo. Es
    # barata -- todo lo que pinta ya esta calculado -- y es donde se ve la
    # FORMA de las curvas, que en la tabla hay que reconstruir fila por fila.
    if args.sin_ventana and not args.guardar:
        return 0

    import matplotlib
    if args.sin_ventana:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figura = validacion.dibujar(resultado, umbral_actual=args.umbral)
    if args.guardar:
        print(f"Figura en {validacion.guardar_figura(figura)}")
    if not args.sin_ventana:
        figura.canvas.manager.set_window_title("Validacion del agrupamiento")
        plt.show()
    return 0


# ==========================================================
# LOS TRES MODOS DE LA FASE 8
# ==========================================================

def _parametros(args):
    """Los parametros del agrupamiento que los tres modos comparten."""
    return dict(
        minimo_notas=args.minimo_notas,
        vecinos=args.vecinos,
        dimensiones=args.dimensiones,
        tamano_minimo=args.tamano_minimo,
        muestras_minimas=args.muestras_minimas,
        epsilon=args.epsilon,
        n_temas=args.temas,
        umbral=args.umbral,
    )


def _vectores_de(resultado):
    """
    Los vectores de bge-m3 alineados con resultado.textos.

    La Corrida no los lleva dentro -- son varias decenas de MB y ninguno de sus
    consumidores los necesitaba -- asi que se releen del almacen y se reordenan
    por numero de fila, que es barato y es la misma fuente de la que salieron.
    """
    import numpy as np

    from clustering import corpus

    textos, vectores, _ = corpus.instantanea()
    orden = {int(fila): posicion for posicion, fila in enumerate(textos["fila"])}
    filas = [orden[int(fila)] for fila in resultado.textos["fila"]]
    return np.asarray(vectores)[filas]


def _anclar(args):
    """
    Fija la identidad permanente de los temas. Se corre UNA vez, no por corrida.

    Hace una corrida completa a proposito en vez de leer salidas/: las anclas
    son la definicion de las unidades de analisis de aqui en adelante, y
    fabricarlas a partir de unos archivos que pueden ser de otro dia y de otros
    parametros es justo el tipo de cosa que despues nadie puede reconstruir.
    """
    from clustering import anclas, corrida as motor

    print("Creando las anclas: la identidad permanente de los temas.")
    print("Se corre UNA vez. Rehacerlas despues empieza una serie nueva.\n")

    inicio = time.time()
    resultado = motor.ejecutar(**_parametros(args))
    print(f"  corrida de referencia: {time.time() - inicio:.0f}s")

    tabla, matriz = anclas.crear(
        _vectores_de(resultado),
        resultado.textos["cluster"].to_numpy(),
        resultado.textos["n_notas"].to_numpy(),
        resultado.temas,
        resultado.nombres_tema,
        notas_administrativas=anclas.administrativas(resultado.textos,
                                                     resultado.indice))

    print(f"  {len(tabla)} anclas a partir de "
          f"{resultado.metricas['clusters']} grupos\n")
    print(tabla.to_string(index=False))

    papeleo = tabla[~tabla["clinica"]]
    if len(papeleo):
        print(f"\n  {len(papeleo)} ancla(s) son mas de la mitad tramite "
              f"administrativo y quedan marcadas con clinica=False:")
        for fila in papeleo.itertuples(index=False):
            print(f"    [{fila.id}] {fila.nombre}  "
                  f"({fila.parte_administrativa:.0%} administrativas)")
        print("  Su serie diaria mide como se llenan los formularios, no quien")
        print("  llega enfermo. Se calculan igual; excluirlas es decision de")
        print("  quien analice, y ahora esta escrito en el archivo.")

    if not args.guardar:
        print("\n--sin-guardar: no se escribio nada.")
        return 0

    ruta = anclas.guardar(tabla, matriz, procedencia={
        "reemplazar": bool(args.rehacer),
        "parametros": dict(resultado.parametros),
        "corpus": {"textos": int(resultado.metricas["textos"]),
                   "notas": int(resultado.metricas["notas"])},
    })
    print(f"\nAnclas escritas en {ruta}")
    print("  El nombre de cada una se puede corregir a mano en ese CSV: el")
    print("  centroide no se toca, asi que renombrar no cambia ninguna serie.")
    print("  VERSIONA LOS DOS ARCHIVOS. Si se pierden, las series calculadas")
    print("  antes dejan de ser comparables con las nuevas.")
    return 0


def _serie(args):
    """Construye la serie diaria por tema y la deja en salidas/."""
    from clustering import anclas, corpus, corrida as motor, fechas

    if not anclas.existen():
        raise SystemExit(
            "No hay anclas, asi que los temas no tienen identidad estable y la "
            "serie no seria comparable con ninguna otra.\n"
            "  python -m clustering --anclar\n"
            "Ver clustering/anclas.py para por que esto no es opcional.")

    print("Construyendo la serie diaria por tema.\n")
    resultado = motor.ejecutar(**_parametros(args))
    asignacion = corpus.repartir(resultado.textos, resultado.indice)

    if resultado.informe_anclas:
        print(anclas.texto(resultado.informe_anclas))
        print()

    engine = fechas._engine()
    hueco = fechas.ventana(engine=engine)
    print(f"  ventana con motivo de consulta: {hueco['desde'].date()} a "
          f"{hueco['hasta'].date()} ({hueco['dias']} dias)")

    fecha_por_oid = fechas.fechas_de(asignacion["OID"].unique(), engine=engine)
    cobertura = fechas.cobertura(desde=hueco["desde"], hasta=hueco["hasta"],
                                 engine=engine)
    tabla_anclas, _ = anclas.cargar()
    serie = fechas.serie(asignacion, fecha_por_oid, cobertura,
                         tabla_anclas=tabla_anclas)

    dias = max(fecha_por_oid["fecha"].nunique(), 1)
    print(f"  serie: {len(serie):,} filas "
          f"({serie['fecha'].nunique()} dias x {serie['ancla'].nunique()} temas)")
    print(f"  notas por dia en el corpus: {len(fecha_por_oid) / dias:.1f}")

    if args.guardar:
        ruta_serie, ruta_cobertura = fechas.guardar(serie, cobertura)
        print(f"\n  {ruta_serie}\n  {ruta_cobertura}")

    print("\nLA COLUMNA QUE SE MODELA ES 'parte', NO 'notas'.")
    print("  La cobertura de HCTMOTCON cae unos 9 puntos por ano, asi que una")
    print("  serie de conteos trae una tendencia a la baja que no es del")
    print("  hospital. Ver clustering/fechas.py.")
    return 0


def _puente(args):
    """Dice si se puede arrancar la fase 8 y que falta. No calcula la serie."""
    import pandas as pd

    from clustering import corpus, corrida as motor, fechas, rutas

    print("Comprobando si el proyecto puede cruzar contra el calendario.\n")

    if rutas.ASIGNACION.exists():
        asignacion = pd.read_parquet(rutas.ASIGNACION)
        print(f"  leyendo la ultima corrida: {len(asignacion):,} notas\n")
    else:
        print("  no hay asignacion.parquet todavia; corriendo el agrupamiento\n")
        resultado = motor.ejecutar(**_parametros(args))
        asignacion = corpus.repartir(resultado.textos, resultado.indice)

    texto = fechas.informe(fechas.diagnostico(asignacion))
    print(texto)
    if args.guardar:
        rutas.PUENTE.write_text(texto, encoding="utf-8")
        print(f"Informe en {rutas.PUENTE}")
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
        if args.barrido:
            return _barrido(args)
        if args.validar:
            return _validar(args)
        if args.anclar:
            return _anclar(args)
        if args.serie:
            return _serie(args)
        if args.puente:
            return _puente(args)
        return _corrida(args)
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
