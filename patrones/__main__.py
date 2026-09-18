"""
Punto de entrada unico de la fase 8. Un comando, del agrupamiento a los patrones.

    python -m patrones

    Recupera la fecha de cada nota, arma la tabla de bloques con el clima y el
    calendario al lado, dice que efecto se podria detectar, busca asociaciones,
    ajusta los modelos, compara los agrupamientos de bloques y dibuja. En ese
    orden y sin preguntar nada.

    python -m patrones --bloque dia      por dia en vez de por semana
    python -m patrones --potencia        solo: ¿alcanza para algo?
    python -m patrones --tablero         solo la tabla
    python -m patrones --temporadas      que se consulta en cada temporada
    python -m patrones --asociar         solo la busqueda exploratoria
    python -m patrones --modelar         solo el analisis principal
    python -m patrones --comparar        solo los tres agrupamientos
    python -m patrones --vistas          solo las figuras
    python -m patrones --panorama        el historico entero en un eje
    python -m patrones --ventana         y ademas lo abre en pantalla
    python -m patrones --sin-base        no consulta DIM_TRIAGE

EL ORDEN NO ES ARBITRARIO Y ES LA IDEA CENTRAL DEL PAQUETE
    potencia va PRIMERO, antes de calcular un solo resultado. Decide que temas
    entran, y esa decision tiene que tomarse sin haber visto ninguna
    correlacion: elegir que analizar despues de ver cual dio bonito es como se
    fabrica un hallazgo falso sin darse cuenta.

    Despues va la composicion por temporada climatica, que es UNA sola prueba
    y por tanto la de mas potencia del paquete: si algo se puede detectar con
    este corpus, se detecta ahi y no en las 768 correlaciones que vienen luego.

    Despues la busqueda exploratoria, despues el analisis principal, y las
    figuras al final para mirar lo que salio.

    Lo unico que se puede hacer en cualquier momento es mirar los calendarios.
    Mirar no gasta una prueba.

QUE ESPERAR HOY, PARA NO PERDER LA TARDE INTERPRETANDO RUIDO
    El corpus es una muestra del 7% y eso manda sobre todo lo demas. Con el, el
    efecto mas pequeno que se podria detectar ronda el 15%, y los efectos de
    clima sobre urgencias que existen en la literatura estan entre el 2% y el
    10%.

    O sea que lo esperable es que no salga nada, y que si sale algo sea falso.
    El paquete lo dice antes de empezar en vez de dejarlo descubrir al final.

    Eso no lo vuelve inutil hoy: la tuberia queda construida y verificada
    contra datos reales, las figuras se pueden mirar a ojo, y potencia.py
    convierte 'falta corpus' en una cifra concreta de cuantas notas faltan.
    Cuando NLP/ termine la extraccion completa, esto es un solo comando.

SI ALGO FALLA
    Los dos fallos normales son que clustering/salidas/ todavia no existe --
    no se ha corrido 'python -m clustering' -- y que la base no responde, que
    es lo unico para lo que hace falta. Con --sin-base se salta la consulta y
    se trabaja sobre serie_diaria.csv, que ya trae las fechas resueltas.
"""

import argparse
import sys


def _argumentos(argv=None):
    from patrones import tablero

    parser = argparse.ArgumentParser(
        prog="python -m patrones",
        description="Cruza los temas de triage contra el clima y el "
                    "calendario: escribe patrones/salidas/ y dibuja.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Sin argumentos hace todo. Los pasos sueltos existen para "
               "repetir uno sin rehacer los anteriores.")

    parser.add_argument("--bloque", default=tablero.BLOQUE,
                        choices=sorted(tablero.BLOQUES),
                        help=f"unidad de tiempo del analisis "
                             f"(por defecto: {tablero.BLOQUE}; ver tablero.py "
                             f"para por que no es 'dia' todavia)")
    parser.add_argument("--ventana", action="store_true",
                        help="abrir el panorama en una ventana ademas de "
                             "escribirlo. Implica --panorama")
    parser.add_argument("--sin-base", action="store_true",
                        help="no consultar DIM_TRIAGE; usar solo lo que ya "
                             "dejo 'python -m clustering --serie'")

    pasos = parser.add_argument_group("hacer solo un paso")
    for nombre, ayuda in [
            ("calendario", "unificar calendarios/ en una tabla diaria"),
            ("tablero", "la tabla de bloques con el clima al lado"),
            ("potencia", "¿que efecto se podria detectar?"),
            ("temporadas", "que se consulta dentro de cada temporada climatica"),
            ("asociar", "busqueda exploratoria con rezagos"),
            ("modelar", "el analisis principal"),
            ("comparar", "los tres agrupamientos de bloques"),
            ("vistas", "solo las figuras"),
            ("panorama", "el historico entero en un eje de tiempo, con los "
                         "temas agrupados por como se mueven")]:
        pasos.add_argument(f"--{nombre}", action="store_true", help=ayuda)

    return parser.parse_args(argv)


def _pasos_pedidos(args):
    """Que pasos se piden. Si no se pide ninguno, todos."""
    nombres = ["calendario", "tablero", "potencia", "temporadas", "asociar",
               "modelar", "comparar", "vistas", "panorama"]
    pedidos = {n for n in nombres if getattr(args, n.replace("-", "_"), False)}
    if args.ventana:
        pedidos.add("panorama")
    return set(nombres) if not pedidos else pedidos


def main(argv=None):
    args = _argumentos(argv)
    pasos = _pasos_pedidos(args)

    import pandas as pd

    from patrones import (agrupamiento, asociacion, calendario, comparacion,
                          modelos, potencia, rutas, tablero, vistas)

    def titulo(texto):
        print()
        print("=" * 70)
        print(texto)
        print("=" * 70)

    partes = []

    # ------------------------------------------------------------------
    # La serie diaria de la fase 7. Es la entrada de todo.
    # ------------------------------------------------------------------
    if not rutas.SERIE_DIARIA.exists():
        raise SystemExit(
            f"No existe {rutas.SERIE_DIARIA}.\n"
            f"Este paquete se para sobre la fase 7:\n"
            f"  python -m clustering            (agrupa)\n"
            f"  python -m clustering --serie    (la serie diaria)\n")

    serie = pd.read_csv(rutas.SERIE_DIARIA, encoding="utf-8-sig",
                        parse_dates=["fecha"])
    desde, hasta = serie["fecha"].min(), serie["fecha"].max()
    print(f"serie de la fase 7: {len(serie):,} filas, "
          f"{serie['fecha'].nunique()} dias, "
          f"{serie['ancla'].nunique()} temas "
          f"({desde.date()} a {hasta.date()})")

    # ------------------------------------------------------------------
    titulo("1. EL CALENDARIO")
    diario, resumen = calendario.construir(desde, hasta)
    calendario.guardar(diario)
    variables, descartadas = calendario.variables_probables(diario, detalle=True)
    print(f"  {len(variables)} variables entran, {len(descartadas)} descartadas")
    for nombre, motivo in list(descartadas.items())[:6]:
        print(f"    - {nombre}: {motivo}")
    if len(descartadas) > 6:
        print(f"    ... y {len(descartadas) - 6} mas (ver calendario.py)")

    # ------------------------------------------------------------------
    titulo("2. EL TABLERO")
    tabla = tablero.construir(serie=serie, diario=diario, bloque=args.bloque,
                              aviso=lambda *_: None)
    ancha = tablero.ancho(tabla)
    rutas_tablero = tablero.guardar(tabla, ancha)
    print(f"  bloque: {args.bloque}. {tabla['bloque'].nunique()} bloques x "
          f"{tabla['ancla'].nunique()} temas = {len(tabla):,} filas")
    for ruta in rutas_tablero:
        print(f"  {ruta}")

    utiles = tablero.temas_utiles(tabla)
    print(f"  {int(utiles['util'].sum())} temas con 5 o mas notas por bloque")

    # Las notas fechadas: el nivel fino. Solo si se puede llegar a la base.
    if not args.sin_base:
        try:
            notas = tablero.notas_fechadas(aviso=lambda *_: None)
            notas.to_parquet(rutas.EVENTOS_FECHADOS, index=False)
            print(f"  {len(notas):,} notas con fecha, hora y clima -> "
                  f"{rutas.EVENTOS_FECHADOS}")
        except SystemExit as error:
            print(f"  sin notas fechadas: {error}")
        except Exception as error:
            print(f"  sin notas fechadas (la base no respondio): {error}")
            print("  El resto del analisis no la necesita: sigue.")

    # ------------------------------------------------------------------
    titulo("3. ¿ALCANZA PARA ALGO? (POTENCIA)")
    tabla_potencia = potencia.tabla(tabla, diario, variables, serie=serie)
    texto_potencia = potencia.informe(tabla_potencia)
    print(texto_potencia)
    partes.append(texto_potencia)

    temas = [(int(fila.ancla), fila.nombre)
             for fila in (tabla_potencia[tabla_potencia["suficiente"]]
                          .drop_duplicates("ancla").itertuples())]
    if not temas:
        print("Ningun tema tiene eventos suficientes. Se para aqui: lo que "
              "siguiera no significaria nada.")
        _escribir(partes, pasos, args.bloque)
        return 0

    # ------------------------------------------------------------------
    # Va antes que la busqueda exploratoria a proposito: es UNA sola prueba y
    # por tanto la de mas potencia del paquete. Si algo se puede detectar con
    # este corpus, se detecta aqui.
    if "temporadas" in pasos and "temporada" in diario.columns:
        titulo("4. QUE SE CONSULTA EN CADA TEMPORADA CLIMATICA")
        etiquetas = diario.set_index("fecha")["temporada"]
        fraccion, prueba = tablero.composicion_por_temporada(serie, etiquetas)
        if fraccion.empty:
            print(f"  no se pudo: {prueba.get('error')}")
        else:
            replicacion = tablero.replicacion_por_anio(serie, etiquetas)
            texto = tablero.informe_temporadas(fraccion, prueba, replicacion)
            print(texto)
            partes.append(texto)
            fraccion.to_csv(rutas.TEMPORADAS, encoding="utf-8-sig")
            print(f"  {rutas.TEMPORADAS}")

    # ------------------------------------------------------------------
    if "asociar" in pasos:
        titulo("5. BUSQUEDA EXPLORATORIA")
        encontrado = asociacion.probar(serie, diario, variables, temas)
        asociacion.guardar(encontrado)
        texto = asociacion.informe(encontrado)
        print(texto)
        partes.append(texto)
    else:
        encontrado = None

    # ------------------------------------------------------------------
    if "modelar" in pasos:
        titulo("6. ANALISIS PRINCIPAL")
        ajustados = modelos.correr(serie, diario, temas)
        modelos.guardar(ajustados)
        texto = modelos.informe(ajustados)
        print(texto)
        partes.append(texto)

    # ------------------------------------------------------------------
    if "comparar" in pasos:
        titulo("7. LOS TRES AGRUPAMIENTOS DE BLOQUES")
        try:
            numericas, categoricas = agrupamiento.matriz(tabla)
            print(f"  {numericas.shape[0]} bloques x "
                  f"{numericas.shape[1]} columnas numericas + "
                  f"{categoricas.shape[1]} categoricas")
            comparadas = comparacion.correr(numericas, categoricas)
            comparacion.guardar(comparadas)
            etiquetas, _ = agrupamiento.correr(numericas, categoricas,
                                               n_grupos=4)
            agrupamiento.guardar(numericas.index, etiquetas)
            texto = comparacion.informe(comparadas)
            print(texto)
            partes.append(texto)
        except SystemExit as error:
            print(f"  no se pudo agrupar bloques: {error}")

    # ------------------------------------------------------------------
    if "vistas" in pasos:
        titulo("8. LAS FIGURAS")
        hechas = _dibujar(serie, diario, temas, encontrado, variables)
        for ruta in hechas:
            print(f"  {ruta}")
        print()
        print("  Los calendarios se miran ANTES de creerle a ninguna cifra, y")
        print("  lo que se vea en ellos se anota como hipotesis para probar")
        print("  contra datos que no sean estos.")

    # ------------------------------------------------------------------
    # EL PANORAMA VA AL FINAL Y ES LO PRIMERO QUE SE MIRA
    #     Al final porque necesita el calendario ya unificado. Lo primero que
    #     se mira porque las cifras de arriba dicen si algo sobrevive a la
    #     correccion, y ninguna de ellas dice QUE mirar. Eso lo dice la figura.
    if "panorama" in pasos:
        titulo("9. EL PANORAMA")
        texto = _panorama(serie, diario, ventana=args.ventana)
        if texto:
            partes.append(texto)

    _escribir(partes, pasos, args.bloque)

    # El plt.show() va DESPUES de escribir el informe: bloquea hasta que se
    # cierre la ventana, y dejar el informe a medias mientras alguien mira una
    # figura durante veinte minutos es como se pierde una corrida.
    if args.ventana and _VENTANA_LISTA:
        from patrones import vistas
        print()
        print("Ventana abierta. Se cierra y el comando termina.")
        vistas.mostrar()

    return 0


_VENTANA_LISTA = False


def _panorama(serie, diario, ventana=False):
    """
    Las familias de motivos y las tres figuras del panorama. Devuelve el informe.

    EL CAMBIO DE BACKEND TIENE QUE PASAR AQUI Y NO DENTRO DE vistas
        vistas.py fija 'Agg' al importarse porque su trabajo normal es escribir
        PNG. matplotlib solo deja cambiar de backend mientras no exista ninguna
        figura, asi que el cambio va antes de dibujar la primera y no despues.
    """
    global _VENTANA_LISTA

    from patrones import panorama as panorama_modulo
    from patrones import rutas, vistas

    if ventana:
        _VENTANA_LISTA = vistas.abrir_ventana()

    try:
        agrupadas = panorama_modulo.familias(serie)
    except SystemExit as error:
        print(f"  no se pudo agrupar por forma: {error}")
        return None

    asignacion = agrupadas["asignacion"]
    proporcion, notas, _ = panorama_modulo.series_familias(serie, asignacion)
    print(f"  {len(asignacion)} temas -> {agrupadas['n_familias']} familias "
          f"sobre {len(proporcion)} semanas")

    try:
        perfil = panorama_modulo.rezagos(serie, diario, asignacion)
    except Exception as error:
        print(f"  sin perfil de rezagos: {error}")
        perfil = None

    for ruta in panorama_modulo.guardar(agrupadas, proporcion, perfil):
        print(f"  {ruta}")

    # El diario que necesita la figura lleva tres columnas mas que el del
    # analisis: cuantas notas se procesaron ese dia, cuantos triages hubo y
    # cuantos traian motivo escrito. Van DIBUJADAS, en su propio panel, porque
    # son las que pueden fabricar un patron que no existe -- si la cobertura
    # cae justo donde una familia sube, lo que se esta viendo es el
    # denominador. Se pasan en crudo y no ya divididas para que la figura pueda
    # agregarlas por semana como cociente de sumas.
    dibujo = diario.set_index("fecha").copy()
    por_dia = serie.drop_duplicates("fecha").set_index("fecha")
    for columna in ("procesadas", "notas_con_motivo", "triages"):
        dibujo[columna] = por_dia[columna].reindex(dibujo.index)

    estabilidad = agrupadas["estabilidad"]
    hechas = []
    hechas.append(vistas._guardar_sin_cerrar(
        vistas.panorama(proporcion, dibujo, asignacion, estabilidad),
        rutas.FIGURAS / "panorama.png"))
    hechas.append(vistas._guardar_sin_cerrar(
        vistas.mapa_familias(agrupadas["correlacion"], agrupadas["orden"],
                             asignacion, estabilidad),
        rutas.FIGURAS / "panorama_familias.png"))
    figura = vistas.perfil_familias(perfil, asignacion, estabilidad)
    if figura is not None:
        hechas.append(vistas._guardar_sin_cerrar(
            figura, rutas.FIGURAS / "panorama_rezagos.png"))

    for ruta in hechas:
        print(f"  {ruta}")

    texto = panorama_modulo.informe(agrupadas, proporcion, notas, perfil)
    print()
    print(texto)
    return texto


def _dibujar(serie, diario, temas, asociaciones, variables):
    """Las figuras: un calendario doble por tema y las matrices."""
    from patrones import rutas, vistas

    hechas = []
    diario_indexado = diario.set_index("fecha")

    # LOS CALENDARIOS POR TEMPORADA. Es la figura que se pidio: la misma de
    # exploracion.ipynb pero pudiendo ver los temas dentro de cada temporada.
    #
    # Primero el general, que situa las temporadas en el tiempo, y despues uno
    # por tema con la MISMA rejilla y los MISMOS colores. Al ponerlos uno detras
    # de otro se ve si un tema se oscurece dentro de un bloque de color y no en
    # los otros, que es justamente la pregunta.
    if "temporada" in diario.columns and diario["temporada"].notna().any():
        etiquetas = diario_indexado["temporada"]
        total = serie.drop_duplicates("fecha").set_index("fecha")["procesadas"]
        ruta = vistas.temporadas(
            total, etiquetas, "Todas las notas procesadas, por temporada climatica",
            "notas del dia", ruta=rutas.FIGURAS / "temporada_00_todas.png")
        if ruta is not None:
            hechas.append(ruta)

        for ancla, nombre in temas:
            parcial = (serie[serie["ancla"] == ancla]
                       .set_index("fecha")["notas"])
            limpio = "".join(c if c.isalnum() else "_" for c in nombre)[:40]
            ruta = vistas.temporadas(
                parcial, etiquetas, f"{nombre} -- por temporada climatica",
                "notas del tema ese dia",
                ruta=rutas.FIGURAS / f"temporada_{ancla:02d}_{limpio}.png")
            if ruta is not None:
                hechas.append(ruta)

    # El calendario doble de cada tema con potencia, contra la lluvia. Es la
    # figura que responde a ojo, asi que se hace para todos los temas que
    # pasaron y no solo para el mayor.
    for ancla, nombre in temas:
        parcial = serie[serie["ancla"] == ancla].set_index("fecha")["notas"]
        limpio = "".join(c if c.isalnum() else "_" for c in nombre)[:40]
        hechas.append(vistas.calendarios(
            parcial, diario_indexado["precip_consenso_mm"],
            nombre, "lluvia diaria (mm)",
            ruta=rutas.FIGURAS / f"calendario_{ancla:02d}_{limpio}.png"))

    if asociaciones is not None and not asociaciones.empty:
        mascara = asociaciones.pivot_table(index="nombre", columns="variable",
                                           values="sobrevive", aggfunc="max")
        hechas.append(vistas.matriz(
            asociaciones[asociaciones["ventana_dias"] == 7],
            "nombre", "variable", "correlacion",
            "Correlacion a 7 dias, tras pre-blanqueo",
            "correlacion parcial",
            ruta=rutas.FIGURAS / "matriz_asociacion.png",
            mascara=~mascara.astype(bool)))

        # El perfil dia a dia. Estas cifras NO llevan correccion por
        # multiplicidad y no son pruebas: son la forma de la relacion, que es
        # lo que distingue un efecto real -- sube, tiene un maximo y baja -- de
        # un pico suelto entre catorce rezagos planos.
        from patrones import asociacion

        perfiles = asociacion.explorar(serie, diario, variables, temas)
        for _, nombre in temas:
            limpio = "".join(c if c.isalnum() else "_" for c in nombre)[:40]
            ruta = vistas.perfil_rezagos(
                perfiles, nombre, ruta=rutas.FIGURAS / f"rezagos_{limpio}.png")
            if ruta is not None:
                hechas.append(ruta)

    return hechas


def _escribir(partes, pasos=None, bloque=None):
    """
    Junta los informes de cada paso en salidas/informe.txt.

    LLEVA UNA CABECERA QUE DICE QUE PASOS CORRIERON, Y HACE FALTA
        El archivo se reescribe entero en cada corrida, asi que una corrida
        parcial -- 'python -m patrones --tablero' -- deja un informe que solo
        tiene la parte de potencia. Sin cabecera eso se lee igual que un
        informe completo en el que no salio nada, que son dos cosas muy
        distintas y la segunda es una conclusion.
    """
    import datetime

    from patrones import rutas

    completo = pasos is None or len(pasos) >= 9
    cabecera = [
        "FASE 8 -- PATRONES ENTRE MOTIVOS DE TRIAGE Y CALENDARIO",
        f"generado {datetime.datetime.now():%Y-%m-%d %H:%M}",
        f"bloque de tiempo: {bloque}" if bloque else "",
        "",
        ("Corrida COMPLETA." if completo else
         f"Corrida PARCIAL: solo {', '.join(sorted(pasos))}. Lo que no esta "
         f"aqui es que no se calculo, no que no saliera nada."),
        "",
    ]
    separador = "\n\n" + "#" * 70 + "\n\n"
    rutas.INFORME.write_text(
        "\n".join(c for c in cabecera if c is not None)
        + separador + separador.join(partes), encoding="utf-8")
    print()
    print(f"Informe: {rutas.INFORME}")


if __name__ == "__main__":
    sys.exit(main())
