"""
El tablero: un renglon por bloque de tiempo y tema, con el clima al lado.

    python -m patrones --tablero                por semana (lo que hay)
    python -m patrones --tablero --bloque dia   por dia (lo que se quiere)

    Deja tablero.csv (largo, para la maquina) y tablero_ancho.csv (un tema por
    columna, que es el que se abre para leer).

ESTA ES LA TABLA. TODO LO DEMAS DEL PAQUETE SALE DE AQUI
    Tiene la forma que hay que tener para responder la pregunta del proyecto:

        bloque              frecuencia   frecuencia   precip   era
                            de fiebre    de trauma    media    festivo
        2026 semana 10         145           20        12,3      no
        2026 semana 11         190           15        31,7      si

    La columna de la izquierda es tiempo, las del medio son motivos de consulta
    agrupados y las de la derecha son el mundo exterior. Cruzarlas es la fase 8.

POR QUE EL BLOQUE POR DEFECTO ES LA SEMANA Y NO EL DIA
    Porque el dia, HOY, no tiene datos suficientes y hay que decirlo con el
    numero. Medido sobre clustering/salidas/serie_diaria.csv (6.751 notas, el
    7,2% del corpus disponible):

        por dia     el tema mas grande promedia 1,09 notas diarias
                    el ancla MEDIANA esta en cero el 88,5% de los dias
                    el total de todos los temas juntos es de 11,0 notas al dia

        por semana  el tema mas grande promedia 12,1 notas semanales
                    el ancla mediana esta en cero el 41% de las semanas
                    89 bloques, 5 anclas con 5 o mas notas por semana

        por mes     el tema mas grande promedia 51,1 notas mensuales
                    26 de 42 anclas con menos del 10% de meses en cero
                    21 bloques  <- y aqui esta el problema

    El mes arregla la escasez y rompe otra cosa: 21 observaciones para 24
    variables externas no es un modelo, es una interpolacion. La semana es el
    unico punto donde las dos cosas son tolerables a la vez, y aun asi solo
    para los cinco o seis temas mas grandes.

    ESTO CAMBIA CON EL CORPUS COMPLETO. Con las 93.991 notas disponibles serian
    unas 153 notas diarias en vez de 11, y entonces el bloque correcto vuelve a
    ser el dia: 615 observaciones, que es lo que hace falta para separar un
    efecto del clima de la estacionalidad anual. Por eso el bloque es un
    parametro y no una constante, y por eso el valor por defecto de este archivo
    tendra que cambiar a 'dia' el dia que se amplie la extraccion.

    Ver clustering/salidas/informe_fase8.txt: la densidad diaria es la condicion
    que hoy no pasa, y es la misma que manda aqui.

CADA VARIABLE SE AGREGA COMO CORRESPONDE Y NO TODAS IGUAL
    Un bloque de siete dias no se resume con una media para todo:

        precipitacion     SUMA. Lo que le cayo encima a la ciudad esa semana.
                          La media diaria de lluvia de una semana esconde que
                          llovio 60 mm en un dia y nada en los otros seis.
        temperatura       MEDIA. Es un nivel, no un acumulado.
        humedad, viento   MEDIA, por lo mismo.
        banderas (0/1)    DIAS. Cuantos dias de ese bloque la cumplieron. Una
                          media daria 0,43 y hay que pararse a pensar que es;
                          un conteo de dias se lee solo.
        conteos de notas  SUMA, obviamente.

    Y ademas se guarda 'dias_en_bloque', porque el primero y el ultimo bloque
    de la ventana casi nunca estan completos. Una semana de tres dias tiene
    menos lluvia y menos notas que una de siete sin que haya pasado nada, y
    compararlas sin esa columna es fabricar dos valores atipicos en los dos
    extremos de la serie.

LA COLUMNA QUE HAY QUE MODELAR SIGUE SIENDO 'parte', NO 'notas'
    Se arrastra el mismo problema que documenta clustering/fechas.py y no
    desaparece por agregar: la fraccion de triages a los que les escriben el
    motivo cae unos 9 puntos por ano. Un conteo semanal hereda esa caida igual
    que uno diario.

    Por eso el tablero lleva siempre los tres denominadores -- procesadas,
    notas_con_motivo y triages -- y la columna 'parte'. Quien mire 'notas' sin
    mirar al lado va a encontrar que casi todos los motivos de consulta
    'bajaron' entre 2025 y 2026, y no bajo ninguno.
"""

import numpy as np
import pandas as pd

from patrones import calendario, rutas

# Como se agrega cada variable al pasar de dia a bloque. Lo que no este aqui y
# sea numerico se promedia, que es lo correcto para un nivel y lo unico
# defendible por defecto.
SUMA = {"precip_consenso_mm"}

BLOQUES = {
    "dia": "D",
    "semana": "W-MON",
    "mes": "MS",
}

# La semana, por lo medido en el encabezado. Cambiar a 'dia' cuando la
# extraccion de NLP/ deje de ser una muestra.
BLOQUE = "semana"


# ==========================================================
# EL NIVEL FINO: UNA FILA POR NOTA, CON SU FECHA
# ==========================================================

def notas_fechadas(asignacion=None, engine=None, aviso=print):
    """
    OID, momento, fecha, tema y el clima de ese dia. Una fila por nota.

    ES LO QUE PIDE K-PROTOTYPES Y NO LO DA serie_diaria.csv
        serie_diaria.csv ya viene agregado por (fecha, tema), y agregar pierde
        justo lo que un agrupamiento mixto necesita: la nota individual con sus
        atributos numericos (la lluvia de ese dia, la hora) y categoricos (el
        tema, el dia de la semana, la temporada). Sobre una tabla agregada no se
        puede agrupar por nota porque ya no hay notas.

        Tambien permite volver a agregar por otro bloque sin repetir la consulta
        a la base, que tarda.

    LA HORA SE GUARDA Y NO SE USA TODAVIA
        'momento' trae el timestamp completo. No entra en ningun analisis de
        este paquete -- todo va por dia -- pero guardarlo cuesta una columna y
        recuperarlo despues cuesta otra consulta a DIM_TRIAGE.

        Cuando se use hay que leer antes la nota de clustering/fechas.py sobre
        el corte a las 00:00 locales: para un analisis por dia el desfase no
        importa y para uno por hora si.
    """
    from clustering import fechas

    if asignacion is None:
        if not rutas.ASIGNACION.exists():
            raise SystemExit(
                f"No existe {rutas.ASIGNACION}.\n"
                f"Este paquete se para sobre la fase 7: hay que agrupar antes.\n"
                f"  python -m clustering")
        asignacion = pd.read_parquet(rutas.ASIGNACION)

    if "ancla" not in asignacion.columns:
        raise SystemExit(
            "La asignacion no trae columna 'ancla'.\n"
            "Sin anclas los numeros de tema se renumeran en cada corrida y una "
            "serie construida sobre ellos no es comparable con ninguna otra.\n"
            "  python -m clustering            (rehace salidas/ con las anclas)\n"
            "Ver clustering/anclas.py.")

    aviso(f"  recuperando la fecha de {len(asignacion):,} notas contra "
          f"DIM_TRIAGE...")
    fecha = fechas.fechas_de(asignacion["OID"].unique(), engine=engine)

    tabla = asignacion.merge(fecha[["OID", "fecha", "momento"]], on="OID",
                             how="inner")
    perdidas = len(asignacion) - len(tabla)
    if perdidas:
        aviso(f"  aviso: {perdidas} notas quedaron sin fecha y salen de la "
              f"tabla. Deberian ser cero: revisar DIM_TRIAGE.")

    diario, _ = calendario.construir(tabla["fecha"].min(), tabla["fecha"].max(),
                                     aviso=lambda *_: None)
    tabla = tabla.merge(diario, on="fecha", how="left")
    tabla["hora"] = tabla["momento"].dt.hour
    return tabla


# ==========================================================
# EL TABLERO
# ==========================================================

def _etiqueta(fechas_bloque, bloque):
    """El nombre legible del bloque. '2026 semana 11', no un timestamp."""
    if bloque == "dia":
        return fechas_bloque.dt.strftime("%Y-%m-%d")
    if bloque == "semana":
        iso = fechas_bloque.dt.isocalendar()
        return (iso["year"].astype(str) + " semana "
                + iso["week"].astype(int).astype(str).str.zfill(2))
    return fechas_bloque.dt.strftime("%Y-%m")


def _agregar_calendario(diario, clave, variables):
    """
    Las variables externas resumidas por bloque, cada una como corresponde.

    Las banderas se cuentan en dias y no se promedian: 'dias_de_lluvia_fuerte'
    se lee solo y '0,4285' hay que pararse a pensarlo. La columna conserva el
    nombre original con el prefijo 'dias_' para que se note que cambio de
    unidad al agregar y nadie la compare contra la diaria sin darse cuenta.
    """
    filas = diario.assign(_clave=clave)
    salida = filas.groupby("_clave").agg(
        dias_en_bloque=("fecha", "size"),
        dias_con_clima=("tiene_clima", "sum"),
        fecha_inicio=("fecha", "min"),
        fecha_fin=("fecha", "max"),
    )

    # La temporada del bloque es la de la MAYORIA de sus dias, no la del primero
    # ni la del ultimo. Una semana a caballo entre dos temporadas tiene que caer
    # en la que ocupa mas dias, y en las de siete dias eso siempre desempata.
    if "temporada" in filas.columns and filas["temporada"].notna().any():
        salida["temporada"] = (filas.groupby("_clave")["temporada"]
                               .agg(lambda x: x.dropna().mode().iloc[0]
                                    if not x.dropna().empty else np.nan))

    for variable in variables:
        serie = filas[variable]
        es_bandera = serie.dropna().isin([0, 1]).all()
        if es_bandera:
            salida[f"dias_{variable}"] = filas.groupby("_clave")[variable].sum()
        elif variable in SUMA:
            salida[variable] = filas.groupby("_clave")[variable].sum(min_count=1)
        else:
            salida[variable] = filas.groupby("_clave")[variable].mean()

    return salida.reset_index().rename(columns={"_clave": "bloque"})


def construir(serie=None, diario=None, bloque=BLOQUE, aviso=print):
    """
    El tablero largo: un renglon por (bloque, tema). Devuelve la tabla.

    Se parte de clustering/salidas/serie_diaria.csv y no de las notas, porque
    esa tabla ya resolvio lo dificil: la rejilla completa con los dias de cero
    dentro y los denominadores al lado. Volver a agregarla por semana conserva
    las dos cosas; reconstruirla desde las notas las perderia.
    """
    if bloque not in BLOQUES:
        raise SystemExit(f"Bloque desconocido: {bloque}. "
                         f"Hay {', '.join(BLOQUES)}.")

    if serie is None:
        if not rutas.SERIE_DIARIA.exists():
            raise SystemExit(
                f"No existe {rutas.SERIE_DIARIA}.\n"
                f"  python -m clustering --serie")
        serie = pd.read_csv(rutas.SERIE_DIARIA, encoding="utf-8-sig",
                            parse_dates=["fecha"])

    if diario is None:
        diario, _ = calendario.construir(serie["fecha"].min(),
                                         serie["fecha"].max(), aviso=aviso)

    serie = serie.copy()
    serie["_inicio"] = serie["fecha"].dt.to_period(
        {"dia": "D", "semana": "W", "mes": "M"}[bloque]).dt.start_time
    serie["bloque"] = _etiqueta(serie["_inicio"], bloque)

    # Los denominadores son del DIA, no del par (dia, tema): estan repetidos en
    # las 42 filas de cada dia. Sumarlos directo los multiplicaria por 42. Hay
    # que colapsar a un dia primero y sumar eso.
    por_dia = (serie.groupby(["bloque", "fecha"])
               .agg(procesadas=("procesadas", "first"),
                    notas_con_motivo=("notas_con_motivo", "first"),
                    triages=("triages", "first"))
               .groupby("bloque").sum())

    tabla = (serie.groupby(["bloque", "ancla", "nombre"], as_index=False)
             .agg(notas=("notas", "sum")))
    tabla = tabla.merge(por_dia, on="bloque", how="left")

    diario_clave = _etiqueta(
        diario["fecha"].dt.to_period(
            {"dia": "D", "semana": "W", "mes": "M"}[bloque]).dt.start_time,
        bloque)

    # LOS CONFUSORES VAN EN LA TABLA AUNQUE NO SE PRUEBEN.
    #
    # calendario.variables_probables() saca el fin de semana y los festivos,
    # porque son el AJUSTE de los modelos y preguntarle a un modelo que ya los
    # descuenta si tienen efecto no significa nada. Eso vale para las PRUEBAS.
    #
    # Para la tabla es al reves: '¿cuantos festivos tuvo esa semana?' es una de
    # las primeras columnas que alguien quiere mirar, y quitarla de aqui seria
    # confundir 'no se prueba' con 'no se muestra'. Son dos cosas distintas y
    # este es el archivo que se lee, no el que se modela.
    variables = (calendario.variables_probables(diario)
                 + [c for c in calendario.CONFUSORES if c in diario.columns])
    externas = _agregar_calendario(diario, diario_clave, variables)

    tabla = tabla.merge(externas, on="bloque", how="left")

    # 'parte' se recalcula sobre los totales del bloque y NO se promedian las
    # partes diarias. Promediar proporciones da mas peso a un dia de 3 notas
    # que a uno de 30, que es al reves de lo que se quiere.
    tabla["parte"] = tabla["notas"] / tabla["procesadas"].replace(0, np.nan)

    orden = (["bloque", "fecha_inicio", "fecha_fin", "dias_en_bloque",
              "dias_con_clima", "ancla", "nombre", "notas", "parte",
              "procesadas", "notas_con_motivo", "triages"]
             + [c for c in tabla.columns if c not in {
                 "bloque", "fecha_inicio", "fecha_fin", "dias_en_bloque",
                 "dias_con_clima", "ancla", "nombre", "notas", "parte",
                 "procesadas", "notas_con_motivo", "triages"}])
    tabla = tabla[orden].sort_values(["fecha_inicio", "ancla"])
    return tabla.reset_index(drop=True)


def ancho(tabla, columna="notas"):
    """
    El mismo tablero con un tema por columna. El que se abre para leer.

    Es la forma del ejemplo del proyecto: una fila por bloque, una columna por
    motivo de consulta y el clima a la derecha. No aporta ningun dato nuevo --
    de ahi que se genere y no se calcule -- pero un humano encuentra un patron
    en esta forma y no en la larga, que es exactamente para lo que existe.
    """
    contexto = [c for c in tabla.columns
                if c not in {"ancla", "nombre", "notas", "parte"}]
    base = tabla.drop_duplicates("bloque")[contexto].set_index("bloque")

    pivote = tabla.pivot_table(index="bloque", columns="nombre", values=columna,
                               aggfunc="sum", fill_value=0)
    # El orden de las columnas es por tamano total y no alfabetico: lo primero
    # que se quiere ver es el motivo mas frecuente.
    pivote = pivote[pivote.sum().sort_values(ascending=False).index]
    pivote.columns = [f"{columna}_{c}" for c in pivote.columns]

    return base.join(pivote).sort_values("fecha_inicio").reset_index()


def guardar(tabla, tabla_ancha):
    """Escribe los dos tableros y devuelve sus rutas."""
    tabla.to_csv(rutas.TABLERO, index=False, encoding="utf-8-sig")
    tabla_ancha.to_csv(rutas.TABLERO_ANCHO, index=False, encoding="utf-8-sig")
    return rutas.TABLERO, rutas.TABLERO_ANCHO


# ==========================================================
# CUANTO AGUANTA EL TABLERO
# ==========================================================

def composicion_por_temporada(serie, etiquetas, minimo_dias=20, minimo_notas=200):
    """
    Que se consulta dentro de cada temporada climatica. Devuelve (tabla, prueba).

    ES LA PREGUNTA 'VER LOS CLUSTERS DENTRO DE LA TEMPORADA', EN NUMEROS
        El calendario de vistas.temporadas() la responde a ojo. Esta tabla la
        responde con cifras: una fila por tema, una columna por temporada, y en
        cada celda la fraccion de las notas de esa temporada que fueron de ese
        tema.

        La fraccion y no el conteo, por lo de siempre -- la temporada seca tiene
        350 dias y la lluviosa 106, asi que en conteos la seca gana en todos los
        temas sin que eso signifique nada.

    Y ADMITE UNA SOLA PRUEBA, QUE ES LO MEJOR QUE TIENE
        asociacion.py hace 768 pruebas y las tiene que corregir hasta que no
        sobrevive ninguna. Aqui la pregunta es una: '¿la composicion de motivos
        de consulta es la misma en todas las temporadas?'. Eso es exactamente
        una prueba de chi-cuadrado sobre la tabla de contingencia, sin corregir
        nada porque no hay nada que corregir.

        Con una sola prueba la potencia no se reparte, asi que es el analisis
        con mas posibilidades de detectar algo de todo el paquete. Si algo va a
        salir con este corpus, va a salir aqui.

        Los residuos estandarizados dicen DONDE esta la diferencia: por encima
        de 2 en valor absoluto, esa celda tiene mas o menos notas de las que le
        tocarian si la composicion fuera la misma en todas las temporadas.

    LO QUE LA PRUEBA NO CONTROLA, Y HAY QUE TENERLO PRESENTE
        Las temporadas son bloques de meses consecutivos, asi que 'temporada'
        va confundida con 'epoca del ano' y con cualquier cosa que cambie
        despacio -- incluida la deriva de la cobertura del motivo. Un
        chi-cuadrado significativo dice que la composicion cambio entre esos
        bloques de tiempo, NO que la causa sea el clima.

        Es la limitacion de 1,7 ciclos anuales otra vez, y no se arregla aqui.
        Para separarlo hace falta el diseno de modelos.py, que compara dentro
        del mismo mes; el precio es que ahi la temporada casi no varia y por
        eso esta prueba existe aparte.
    """
    from scipy import stats

    serie = serie.copy()
    etiquetas = etiquetas.rename("temporada")
    serie = serie.merge(etiquetas, left_on="fecha", right_index=True, how="left")
    serie = serie[serie["temporada"].notna() & (serie["ancla"] != -1)]

    # Las temporadas de pocos dias no entran: con 6 dias, una nota de mas mueve
    # la fraccion entera. Es la misma regla que calendario.MINIMO_DIAS_BANDERA.
    dias = serie.groupby("temporada")["fecha"].nunique()
    vivas = dias[dias >= minimo_dias].index
    # Y los temas de pocas notas tampoco: inflan la tabla con celdas de cero y
    # el chi-cuadrado deja de ser valido cuando muchos esperados bajan de 5.
    notas = serie.groupby("ancla")["notas"].sum()
    grandes = notas[notas >= minimo_notas].index

    fuera = {
        "temporadas_descartadas": dias[dias < minimo_dias].to_dict(),
        "temas_descartados": int((notas < minimo_notas).sum()),
    }
    serie = serie[serie["temporada"].isin(vivas) & serie["ancla"].isin(grandes)]
    if serie.empty:
        return pd.DataFrame(), {"error": "no queda nada que comparar", **fuera}

    conteo = serie.pivot_table(index="nombre", columns="temporada",
                               values="notas", aggfunc="sum", fill_value=0)
    fraccion = conteo / conteo.sum(axis=0)

    chi2, p, gl, esperado = stats.chi2_contingency(conteo.to_numpy())
    residuos = pd.DataFrame(
        (conteo.to_numpy() - esperado)
        / np.sqrt(esperado * (1 - conteo.sum(axis=0).to_numpy() / conteo.to_numpy().sum())
                  * (1 - conteo.sum(axis=1).to_numpy()[:, None] / conteo.to_numpy().sum())),
        index=conteo.index, columns=conteo.columns)

    prueba = {
        "chi2": float(chi2), "p": float(p), "gl": int(gl),
        "notas": int(conteo.to_numpy().sum()),
        "esperados_bajo_5": int((esperado < 5).sum()),
        "dias_por_temporada": dias.loc[vivas].to_dict(),
        **fuera,
    }
    return fraccion, {"conteo": conteo, "residuos": residuos, **prueba}


def replicacion_por_anio(serie, etiquetas, minimo_dias=20, minimo_notas=200):
    """
    ¿El mismo patron aparece en los dos anos por separado? LA COMPROBACION CLAVE.

    POR QUE ESTO NO ES UN EXTRA
        composicion_por_temporada() junta los veinte meses y compara temporadas.
        El problema es que las temporadas son BLOQUES DE MESES SEGUIDOS: la seca
        cae sobre todo en la segunda mitad de la ventana. Asi que cualquier cosa
        que cambie despacio con el tiempo -- la deriva de la cobertura del
        motivo, un cambio de plantilla en el triage, una tendencia real -- se
        presenta como una diferencia entre temporadas y la prueba no la puede
        distinguir.

        Partir por ano rompe justamente eso. 2025 tiene lluviosa (feb-jun) y
        seca (jul-dic); 2026 tiene seca (ene-jun) e intermedia/lluviosa
        (jul-ago). Si el patron es del clima, tiene que aparecer en los dos. Si
        es de la tendencia, aparece en el conjunto y no dentro de cada ano,
        porque dentro de un ano la tendencia tiene la mitad de recorrido.

        Es el mismo principio del diseno cruzado de modelos.py -- comparar
        dentro de bloques de tiempo en vez de entre ellos -- aplicado a la
        escala mas gruesa que estos datos aguantan.

    LO QUE DEVUELVE Y COMO SE LEE
        Por ano: su chi-cuadrado y su p. Y ademas la CORRELACION entre las dos
        tablas de residuos, que es la cifra que decide: si el patron es el mismo
        en los dos anos, las celdas que sobran en 2025 son las que sobran en
        2026 y la correlacion es alta y positiva. Cerca de cero significa que
        los dos anos no cuentan la misma historia; negativa, que se contradicen.

        Un ano no significativo por si solo NO prueba que no replique -- puede
        ser falta de notas. Por eso la correlacion de residuos pesa mas que las
        dos p juntas: usa la tabla entera y no depende del tamano de muestra
        para tener signo.
    """
    from scipy import stats

    etiquetas = etiquetas.rename("temporada")
    datos = serie.merge(etiquetas, left_on="fecha", right_index=True, how="left")
    datos = datos[datos["temporada"].notna() & (datos["ancla"] != -1)]

    dias = datos.groupby("temporada")["fecha"].nunique()
    notas = datos.groupby("ancla")["notas"].sum()
    datos = datos[datos["temporada"].isin(dias[dias >= minimo_dias].index)
                  & datos["ancla"].isin(notas[notas >= minimo_notas].index)]

    por_anio, residuos = {}, {}
    for anio, parcial in datos.groupby(datos["fecha"].dt.year):
        conteo = parcial.pivot_table(index="nombre", columns="temporada",
                                     values="notas", aggfunc="sum", fill_value=0)
        conteo = conteo.loc[:, conteo.sum() > 0]
        if conteo.shape[1] < 2 or conteo.to_numpy().sum() < 100:
            por_anio[int(anio)] = {"error": "no hay bastante para comparar"}
            continue
        chi2, p, gl, esperado = stats.chi2_contingency(conteo.to_numpy())
        por_anio[int(anio)] = {
            "chi2": float(chi2), "p": float(p), "gl": int(gl),
            "notas": int(conteo.to_numpy().sum()),
            "temporadas": list(conteo.columns),
        }
        residuos[int(anio)] = pd.DataFrame(
            (conteo.to_numpy() - esperado) / np.sqrt(esperado),
            index=conteo.index, columns=conteo.columns)

    concordancia = float("nan")
    anios = sorted(residuos)
    if len(anios) >= 2:
        a, b = residuos[anios[0]], residuos[anios[-1]]
        comunes_f = a.index.intersection(b.index)
        comunes_c = a.columns.intersection(b.columns)
        if len(comunes_f) and len(comunes_c):
            x = a.loc[comunes_f, comunes_c].to_numpy().ravel()
            y = b.loc[comunes_f, comunes_c].to_numpy().ravel()
            if np.std(x) > 0 and np.std(y) > 0:
                concordancia = float(np.corrcoef(x, y)[0, 1])

    return {"por_anio": por_anio, "residuos": residuos,
            "concordancia": concordancia}


def informe_temporadas(fraccion, prueba, replicacion=None):
    """El texto de la composicion por temporada."""
    if fraccion.empty:
        return ("COMPOSICION POR TEMPORADA CLIMATICA\n\n"
                f"  No se pudo calcular: {prueba.get('error')}\n")

    residuos = prueba["residuos"]
    lineas = [
        "COMPOSICION POR TEMPORADA CLIMATICA",
        "",
        "  ¿Se consulta por lo mismo en temporada seca que en lluviosa? Una",
        "  fila por tema, una columna por temporada, y en la celda la fraccion",
        "  de las notas de esa temporada que fueron de ese tema.",
        "",
        f"  {int(prueba['notas']):,} notas, {len(fraccion)} temas, "
        f"{len(fraccion.columns)} temporadas.",
    ]
    for nombre, dias in sorted(prueba["dias_por_temporada"].items(),
                               key=lambda x: -x[1]):
        lineas.append(f"    {nombre:<24} {dias} dias")
    if prueba["temporadas_descartadas"]:
        lineas.append(f"    descartadas por pocos dias: "
                      f"{prueba['temporadas_descartadas']}")

    ancho = max(len(c) for c in fraccion.columns) + 2
    lineas += ["", "=" * 70, "  " + "tema".ljust(26)
               + "".join(c[:ancho - 2].rjust(ancho) for c in fraccion.columns)]
    for tema, fila in fraccion.iterrows():
        lineas.append("  " + tema[:26].ljust(26)
                      + "".join(f"{v:>{ancho}.1%}" for v in fila))

    lineas += [
        "",
        f"  chi-cuadrado = {prueba['chi2']:.1f} con {prueba['gl']} grados de "
        f"libertad, p = {prueba['p']:.4f}",
    ]
    if prueba["esperados_bajo_5"]:
        lineas.append(f"  AVISO: {prueba['esperados_bajo_5']} celdas con valor "
                      f"esperado menor que 5. La prueba pierde validez.")

    lineas += ["", "=" * 70]
    if prueba["p"] < 0.05:
        lineas += [
            "  LA COMPOSICION SI CAMBIA ENTRE TEMPORADAS.",
            "",
            "  Las celdas que mas se apartan de lo esperado (residuo mayor a 2",
            "  en valor absoluto: positivo = mas notas de las que tocarian):",
            "",
        ]
        fuertes = residuos.stack()
        fuertes = fuertes[fuertes.abs() >= 2].sort_values(key=abs,
                                                          ascending=False)
        if fuertes.empty:
            lineas.append("    ninguna celda pasa de 2; la diferencia esta "
                          "repartida.")
        for (tema, estacion), valor in fuertes.head(12).items():
            lineas.append(f"    {tema[:26]:<26} en {estacion:<22} "
                          f"{valor:+.1f}")
    else:
        lineas += [
            "  NO HAY DIFERENCIA DETECTABLE en la composicion entre temporadas.",
            "",
            "  Es el analisis con mas potencia del paquete -- una sola prueba,",
            "  sin correccion por multiplicidad que reparta el presupuesto -- "
            "asi",
            "  que este resultado pesa mas que los negativos de asociacion.py.",
            "",
            "  Sigue sin ser prueba de que el clima no influya: mide la",
            "  composicion promedio de bloques de meses, y un efecto de dias",
            "  concretos se le escapa por construccion.",
        ]

    if replicacion is not None:
        lineas += _bloque_replicacion(replicacion, prueba["p"] < 0.05)
    return "\n".join(lineas) + "\n"


def _bloque_replicacion(replicacion, hubo_senal):
    """El texto de si el patron aparece en los dos anos por separado."""
    concordancia = replicacion["concordancia"]
    lineas = [
        "",
        "=" * 70,
        "¿REPLICA EL PATRON DENTRO DE CADA ANO? LA COMPROBACION QUE DECIDE",
        "",
        "  Las temporadas son bloques de meses seguidos, asi que la prueba de",
        "  arriba no distingue 'el clima cambia la composicion' de 'la",
        "  composicion cambio con el tiempo'. Partir por ano si: dentro de un",
        "  ano la tendencia tiene la mitad de recorrido, pero las temporadas",
        "  siguen estando las dos.",
        "",
    ]
    for anio, datos in sorted(replicacion["por_anio"].items()):
        if "error" in datos:
            lineas.append(f"  {anio}: {datos['error']}")
            continue
        veredicto = "SI hay diferencia" if datos["p"] < 0.05 else "no hay diferencia"
        lineas.append(f"  {anio}: chi2 = {datos['chi2']:5.1f}, gl = "
                      f"{datos['gl']}, p = {datos['p']:.4f}   -> {veredicto}"
                      f"   ({datos['notas']:,} notas)")

    lineas += [
        "",
        f"  Correlacion entre las tablas de residuos de los dos anos: "
        f"{concordancia:+.2f}",
        "",
        "  Es la cifra que manda. Si el patron fuera del clima, las celdas que",
        "  sobran un ano sobrarian el otro y esto estaria cerca de +1. Cerca de",
        "  cero, los dos anos no cuentan la misma historia. Negativa, se",
        "  contradicen.",
        "",
    ]

    if not np.isfinite(concordancia):
        lineas.append("  No se pudo calcular: falta un ano comparable.")
    elif concordancia >= 0.5 and hubo_senal:
        lineas += [
            "  REPLICA. El patron es el mismo en los dos anos, asi que no puede",
            "  ser solo la tendencia de la ventana. Sigue sin estar identificada",
            "  la causa -- clima, epoca del ano y calendario escolar van juntos",
            "  -- pero ya no es un artefacto del periodo.",
        ]
    elif hubo_senal:
        lineas += [
            "  NO REPLICA, Y ESO CAMBIA LA CONCLUSION DE ARRIBA.",
            "",
            "  El chi-cuadrado del conjunto sale significativo y sin embargo los",
            "  dos anos no coinciden en QUE celdas se apartan. La explicacion",
            "  mas economica es que lo que separa a las temporadas no sea el",
            "  clima sino el momento: la temporada seca cae sobre todo en la",
            "  segunda mitad de la ventana, y ahi tambien esta la caida de la",
            "  cobertura del motivo de consulta.",
            "",
            "  NO reportar el resultado agregado como un efecto del clima. Lo",
            "  correcto es dejarlo como hipotesis y volver a mirarlo cuando",
            "  haya un tercer ano o el corpus completo, que es lo que permitiria",
            "  distinguir las dos cosas.",
        ]
    else:
        lineas += [
            "  Sin senal en el agregado, esta cifra solo sirve de referencia",
            "  para la proxima corrida.",
        ]
    return lineas


def temas_utiles(tabla, minimo=5.0):
    """
    Los temas con suficientes notas por bloque para que valga probarlos.

    POR QUE ESTE FILTRO ES PARTE DEL ANALISIS Y NO UNA COMODIDAD
        Probar los 42 temas cuando 36 de ellos estan casi siempre en cero no
        agrega informacion: agrega 36 series de ruido al recuento de pruebas.
        Y ese recuento es el divisor de la correccion por multiplicidad, asi
        que las series vacias le quitan potencia a las que si tenian algo.

        El filtro se aplica ANTES de mirar ninguna correlacion y por un
        criterio que no depende de los resultados -- el tamano del tema -- que
        es la unica forma de que no sea seleccion.
    """
    resumen = (tabla.groupby(["ancla", "nombre"])
               .agg(notas=("notas", "sum"),
                    media_bloque=("notas", "mean"),
                    bloques_en_cero=("notas", lambda x: float((x == 0).mean())))
               .reset_index())
    resumen["util"] = resumen["media_bloque"] >= minimo
    return resumen.sort_values("notas", ascending=False)
