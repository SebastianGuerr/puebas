"""
Una corrida completa: de los embeddings guardados a temas con nombre.

QUE HACE ESTE MODULO Y POR QUE EXISTE APARTE
    Encadena los cinco pasos -- leer, reducir, agrupar, nombrar, fundir en
    temas -- y no hace nada mas. Ni dibuja ni imprime.

    Esta separado porque hay dos consumidores con necesidades distintas y el
    calculo es el mismo para ambos: el visor, que quiere una figura en una
    ventana y la va refrescando, y la escritura de salidas/, que quiere los
    archivos en disco para cruzarlos despues con las fechas de triage. Cuando
    el calculo vivia dentro del visor, la unica forma de obtener los archivos
    era abrir una ventana.

LO QUE CUESTA
    Las dos corridas de UMAP son casi todo el tiempo: sobre 1.957 textos son
    unos 50 segundos en total, mas unos 40 la primera vez del proceso porque
    numba tiene que compilar. HDBSCAN y el nombrado son despreciables al lado.

    Por eso ejecutar() devuelve la firma de la instantanea que uso: quien la
    llama no vuelve a calcular hasta que embedding/salidas/ cambie. El
    centinela escribe cada 15 minutos; recalcular mas seguido es quemar CPU
    para obtener el mismo resultado, y encima compitiendo con NLP/procesar.py,
    que esta corriendo.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from clustering import agrupar, anclas, corpus, etiquetas, rutas, temas


@dataclass
class Corrida:
    """
    El resultado completo, ya listo para dibujar o escribir.

    HAY DOS NIVELES Y LOS DOS VIAJAN JUNTOS
        El GRUPO es lo que encontro HDBSCAN: especifico, apretado, y son
        muchos. El TEMA junta los grupos que hablan de lo mismo (ver temas.py).
        Se llevan los dos en la misma tabla porque sirven para cosas distintas
        y ninguna de las dos es prescindible: el grupo para leer un caso y
        auditar el agrupamiento, el tema para contar por dia y cruzar contra el
        clima y el calendario, que es el objetivo del proyecto.

    textos    un renglon por texto distinto vivo, con todo pegado: fila, texto,
              n_notas, cluster, tema, confianza y las coordenadas x, y.
    nombres   {cluster: 'palabra palabra palabra'}
    representantes {cluster: el texto real mas central del grupo}
    temas     {cluster: tema} -- el mapa del nivel fino al general
    nombres_tema, representantes_tema  lo mismo, un nivel arriba
    detalle_anclas  a que ancla fue cada grupo y con cuanta similitud. Es el
              nivel que SI se puede comparar con la corrida de la semana
              pasada: el numero de tema se renumera y el de ancla no.
    informe_anclas  anclas gemelas, vacias y grupos huerfanos. Hay que leerlo
              antes de construir una serie: ver anclas.revisar().
    difusas   palabras repartidas por todos los clusters: las candidatas a
              datos/palabras_vacias.txt.
    metricas  las cifras con que se juzga la corrida (ver agrupar.resumen).
    firma     el estado de embedding/salidas/ con el que se calculo esto. Es lo
              que permite saber si la corrida sigue vigente.
    """

    textos: pd.DataFrame
    indice: pd.DataFrame
    nombres: dict
    representantes: dict
    difusas: list
    metricas: dict
    temas: dict = field(default_factory=dict)
    nombres_tema: dict = field(default_factory=dict)
    representantes_tema: dict = field(default_factory=dict)
    # El anclaje. Son None cuando todavia no se han creado las anclas, que es
    # un estado valido: el paquete funciona sin ellas y lo unico que no se
    # puede hacer es comparar esta corrida con la anterior.
    detalle_anclas: pd.DataFrame = None
    informe_anclas: dict = None
    firma: tuple = None
    parametros: dict = field(default_factory=dict)

    def nombre_de(self, cluster):
        """El nombre de un cluster, con el numero delante para poder citarlo."""
        if cluster == -1:
            return "ruido"
        return f"{cluster}. {self.nombres.get(cluster, 'sin nombre')}"

    def nombre_tema_de(self, tema):
        """Lo mismo un nivel arriba."""
        if tema == -1:
            return "sin tema"
        return f"{tema}. {self.nombres_tema.get(tema, 'sin nombre')}"

    def tabla(self):
        """
        Un renglon por cluster, ordenado por NOTAS y no por textos distintos.

        El orden importa: un cluster de 12 textos que representan 200 notas
        interesa mucho mas que uno de 40 textos que representan 41, y es el
        primero el que tiene que salir arriba en el CSV y en el panel.
        """
        agregado = (self.textos.groupby("cluster", dropna=False)
                    .agg(textos=("fila", "size"),
                         notas=("n_notas", "sum"),
                         confianza=("confianza", "mean"))
                    .reset_index())
        agregado["cluster"] = agregado["cluster"].astype(int)
        agregado["nombre"] = [
            self.nombres.get(c, "ruido" if c == -1 else "sin nombre")
            for c in agregado["cluster"]]
        agregado["representante"] = [
            self.representantes.get(c, "") for c in agregado["cluster"]]
        agregado["tema"] = [self.temas.get(c, -1) for c in agregado["cluster"]]
        agregado["tema_nombre"] = [
            self.nombres_tema.get(t, "sin tema" if t == -1 else "sin nombre")
            for t in agregado["tema"]]
        return (agregado.sort_values(["notas", "textos"], ascending=False)
                .reset_index(drop=True)
                [["cluster", "nombre", "tema", "tema_nombre", "textos",
                  "notas", "confianza", "representante"]])

    def tabla_temas(self):
        """
        Un renglon por TEMA. Es la tabla con la que se trabaja de aqui en
        adelante: la que se cruza por fecha contra clima, calendario y eventos.

        Lleva 'grupos' -- cuantos grupos de HDBSCAN se fundieron en el tema --
        porque es lo que permite ver de un vistazo si un tema es una fusion de
        verdad o un grupo que se quedo solo, y eso cambia como se lee su nombre.
        """
        datos = self.textos
        agregado = (datos.groupby("tema", dropna=False)
                    .agg(textos=("fila", "size"),
                         notas=("n_notas", "sum"))
                    .reset_index())
        agregado["tema"] = agregado["tema"].astype(int)

        grupos = {t: 0 for t in agregado["tema"]}
        for cluster, tema in self.temas.items():
            grupos[tema] = grupos.get(tema, 0) + 1

        agregado["grupos"] = [grupos.get(t, 0) for t in agregado["tema"]]
        agregado["nombre"] = [
            self.nombres_tema.get(t, "sin tema" if t == -1 else "sin nombre")
            for t in agregado["tema"]]
        agregado["representante"] = [
            self.representantes_tema.get(t, "") for t in agregado["tema"]]
        agregado["parte"] = agregado["notas"] / max(int(datos["n_notas"].sum()), 1)
        return (agregado.sort_values("notas", ascending=False)
                .reset_index(drop=True)
                [["tema", "nombre", "grupos", "textos", "notas", "parte",
                  "representante"]])

    def notas(self):
        """
        Un renglon por NOTA: OID, su tema, su cluster y el texto.

        Es la vista que responde "¿que notas agrupo exactamente aqui?", y por
        eso va ordenada como se lee y no como se calcula: por TEMA de mayor a
        menor, dentro de cada tema por grupo, y dentro de cada grupo las notas
        de mas confianza arriba. Las notas sin tema, al final de todo. Abierta
        en Excel, recorrerla de arriba a abajo es auditar los dos niveles de
        mayor a menor impacto, y ver seguidos los grupos que un tema fundio es
        la forma mas rapida de juzgar si la fusion tenia sentido.

        Deshace la deduplicacion: si 'dolor abdominal' es un solo texto que
        representa 17 notas, aqui salen los 17 OID. Es a proposito. clusters.csv
        cuenta grupos y este cuenta notas, que es la unidad con la que se cruza
        contra la fecha de triage.
        """
        columnas = ["cluster", "tema", "confianza", "texto"]
        if "ancla" in self.textos.columns:
            columnas = ["ancla"] + columnas
        mapa = self.textos.set_index("fila")[columnas]
        salida = self.indice.merge(mapa, left_on="fila", right_index=True,
                                   how="inner")
        salida["nombre"] = [
            self.nombres.get(c, "ruido" if c == -1 else "sin nombre")
            for c in salida["cluster"]]
        salida["tema_nombre"] = [
            self.nombres_tema.get(t, "sin tema" if t == -1 else "sin nombre")
            for t in salida["tema"]]

        # El orden de temas y grupos es el de tabla_temas() y tabla(): por
        # notas. Se traduce a un rango para poder ordenar por el sin repetir
        # los groupby.
        orden_tema = {int(t): i for i, t in
                      enumerate(self.tabla_temas()["tema"].to_numpy())}
        orden = {int(c): i for i, c in
                 enumerate(self.tabla()["cluster"].to_numpy())}
        salida["_tema"] = [orden_tema.get(int(t), len(orden_tema))
                           for t in salida["tema"]]
        salida["_orden"] = [orden.get(int(c), len(orden)) for c in salida["cluster"]]
        # lo que no tiene tema, al final, pase lo que pase con su tamano
        salida.loc[salida["tema"] == -1, "_tema"] = len(orden_tema) + 1

        # 'ancla' va PRIMERA de las tres etiquetas, aunque 'tema' sea la que se
        # viene leyendo desde siempre: es la unica de las tres cuyo numero
        # significa lo mismo en dos corridas distintas. Quien audite esta tabla
        # tiene que ver eso antes que nada.
        columnas = ["OID", "tema", "tema_nombre", "cluster", "nombre",
                    "confianza", "texto"]
        if "ancla" in salida.columns:
            columnas.insert(1, "ancla")

        return (salida.sort_values(["_tema", "_orden", "confianza"],
                                   ascending=[True, True, False])
                .reset_index(drop=True)[columnas])


def ejecutar(minimo_notas=1, vecinos=agrupar.VECINOS,
             dimensiones=agrupar.DIMENSIONES,
             tamano_minimo=agrupar.TAMANO_MINIMO,
             muestras_minimas=agrupar.MUESTRAS_MINIMAS,
             epsilon=agrupar.EPSILON, n_temas=temas.TEMAS,
             umbral=temas.UMBRAL):
    """
    Corre los cinco pasos y devuelve una Corrida.

    La firma se toma ANTES de calcular a proposito. Si el pipeline escribe
    mientras UMAP esta corriendo, esta corrida describe el estado anterior --
    que es correcto, porque los vectores que uso son los de ese estado -- y la
    firma vieja hace que la proxima comprobacion la vea desactualizada y la
    repita. Tomandola despues se marcaria como vigente un resultado que no
    incluye lo que acaba de llegar.
    """
    marca = corpus.firma()
    textos, vectores, indice = corpus.instantanea(minimo_notas=minimo_notas)

    proyeccion = agrupar.proyectar(vectores, dimensiones=dimensiones,
                                   vecinos=vecinos)
    grupos, confianza = agrupar.agrupar(proyeccion,
                                        tamano_minimo=tamano_minimo,
                                        muestras_minimas=muestras_minimas,
                                        epsilon=epsilon)
    plano = agrupar.proyectar_mapa(vectores)

    textos = textos.copy()
    textos["cluster"] = np.asarray(grupos, dtype=int)
    textos["confianza"] = np.asarray(confianza, dtype=float)
    textos["x"] = np.asarray(plano)[:, 0]
    textos["y"] = np.asarray(plano)[:, 1]

    nombres, representantes, difusas = etiquetas.nombrar(
        textos, textos["cluster"].to_numpy(), vectores)

    # El segundo nivel. Se calcula sobre los centroides de los grupos que
    # acaban de salir, asi que va despues por necesidad y no por orden.
    mapa_temas = temas.fundir(vectores, textos["cluster"].to_numpy(),
                              textos["n_notas"].to_numpy(),
                              n_temas=n_temas, umbral=umbral)
    textos["tema"] = temas.aplicar(textos, mapa_temas)

    # Los temas se nombran con la MISMA maquinaria que los grupos: el TF-IDF de
    # etiquetas.py toma como documento la etiqueta que se le pase, asi que
    # pasandole la columna de tema mide que palabras distinguen un tema de los
    # otros temas. Reusarlo no es ahorro de lineas: es lo que garantiza que un
    # nombre de tema y uno de grupo signifiquen lo mismo y se puedan leer
    # seguidos sin cambiar de vara.
    nombres_tema, representantes_tema, _ = etiquetas.nombrar(
        textos, textos["tema"].to_numpy(), vectores)

    # EL ANCLAJE. Va despues de los temas porque necesita sus centroides, y es
    # lo que convierte el resultado en algo comparable con la corrida anterior.
    # Si no hay anclas todavia, la corrida sigue igual y la columna queda en -1:
    # el paquete tiene que poder usarse antes de haberlas creado.
    detalle_anclas = None
    informe_anclas = None
    if anclas.existen():
        tabla_anclas, matriz_anclas = anclas.cargar()
        columna, detalle_anclas = anclas.aplicar(
            vectores, textos["cluster"].to_numpy(),
            textos["n_notas"].to_numpy(),
            tabla=tabla_anclas, matriz=matriz_anclas)
        textos["ancla"] = columna
        informe_anclas = anclas.revisar(detalle_anclas, tabla_anclas,
                                        matriz_anclas)
    else:
        textos["ancla"] = -1

    metricas = agrupar.resumen(textos["cluster"].to_numpy(),
                               textos["n_notas"].to_numpy())
    metricas["coherencia"] = agrupar.coherencia(
        vectores, textos["cluster"].to_numpy(), textos["n_notas"].to_numpy())
    metricas["temas"] = len(set(mapa_temas.values()))
    metricas["separacion"] = temas.separacion(
        vectores, textos["cluster"].to_numpy(),
        textos["n_notas"].to_numpy(), mapa_temas)

    return Corrida(
        textos=textos,
        indice=indice,
        nombres=nombres,
        representantes=representantes,
        difusas=difusas,
        metricas=metricas,
        temas=mapa_temas,
        nombres_tema=nombres_tema,
        representantes_tema=representantes_tema,
        detalle_anclas=detalle_anclas,
        informe_anclas=informe_anclas,
        firma=marca,
        parametros={
            "minimo_notas": minimo_notas,
            "vecinos": vecinos,
            "dimensiones": dimensiones,
            "tamano_minimo": tamano_minimo,
            "muestras_minimas": muestras_minimas or tamano_minimo,
            "epsilon": epsilon,
            "temas": n_temas or f"umbral {umbral}",
            "semilla": agrupar.SEMILLA,
        },
    )


# ==========================================================
# ESCRITURA -- solo dentro de clustering/salidas/
# ==========================================================

def guardar(corrida):
    """
    Deja en salidas/ los archivos de datos que describe rutas.py.

    El mapa.png no se escribe aqui porque para tenerlo hace falta una figura ya
    dibujada, y eso es asunto de mapa.py.

    asignacion.parquet es el que importa para lo que viene despues: devuelve el
    cluster a cada OID deshaciendo la deduplicacion, y es la tabla que se cruza
    por OID con la fecha de triage para buscar los patrones temporales, que es
    el objetivo del proyecto. Los otros son para mirar y para poder comparar
    dos corridas.

    notas.csv lleva los mismos renglones que asignacion.parquet y se escribe
    igual. No es redundancia por descuido: el parquet es tipado, comprimido y
    se lee con pandas, y este se abre en Excel con el nombre del grupo al lado
    y las notas ordenadas para leerlas. Auditar un agrupamiento es una tarea de
    ojo humano, y obligar a escribir un script para hacerla es lo que hace que
    no se haga.
    """
    # asignacion lleva las dos columnas, tema y cluster. La que se usa para el
    # cruce temporal es tema; cluster va al lado para poder bajar al detalle
    # sin volver a juntar tablas.
    asignacion = corpus.repartir(corrida.textos, corrida.indice)
    asignacion.to_parquet(rutas.ASIGNACION, index=False)

    tabla = corrida.tabla()
    # utf-8-sig y no utf-8: sin el BOM, Excel en Windows abre el CSV en cp1252 y
    # parte todas las tildes de los textos representantes.
    tabla.to_csv(rutas.CLUSTERS, index=False, encoding="utf-8-sig")
    corrida.tabla_temas().to_csv(rutas.TEMAS, index=False, encoding="utf-8-sig")
    corrida.notas().to_csv(rutas.NOTAS, index=False, encoding="utf-8-sig")

    corrida.textos[["fila", "texto", "n_notas", "cluster", "tema", "confianza",
                    "x", "y"]].to_parquet(rutas.PROYECCION, index=False)

    rutas.INFORME.write_text(informe(corrida), encoding="utf-8")
    return asignacion, tabla


def informe(corrida):
    """
    Las metricas y los parametros de la corrida, en texto plano.

    Va con los parametros dentro y no solo las cifras: un informe que dice '36
    clusters y 30% de ruido' sin decir con que tamano minimo salio no se puede
    comparar con el de la semana que viene, que es la unica razon de escribirlo.

    Es publica porque se escribe a salidas/informe.txt Y se imprime en consola
    al final de 'python -m clustering'. Son el mismo texto a proposito: lo que
    se lee en la terminal es exactamente lo que queda en disco.
    """
    m = corrida.metricas
    lineas = ["CORRIDA DE AGRUPAMIENTO", "", "PARAMETROS"]
    lineas += [f"  {clave:18} {valor}"
               for clave, valor in corrida.parametros.items()]
    lineas += [
        "",
        "RESULTADO",
        f"  textos distintos  {m['textos']:,}",
        f"  notas             {m['notas']:,}",
        f"  clusters          {m['clusters']:,}",
        f"  textos en ruido   {m['textos_en_ruido']:,} ({m['ruido_textos']:.1%})",
        f"  notas en ruido    {m['notas_en_ruido']:,} ({m['ruido_notas']:.1%})",
        f"  temas             {m.get('temas', 0):,}",
        f"  coherencia        {m.get('coherencia', 0):.3f}"
        f"   (coseno medio al centro del grupo, en el espacio de bge-m3)",
        "                     NO se lee contra 0,47. El suelo de esta metrica",
        "                     depende del tamano del grupo y ronda 0,72 para",
        "                     grupos de diez textos SIN ninguna estructura.",
        "                     Lo que se lee es la ganancia sobre ese suelo, y",
        "                     eso lo calcula 'python -m clustering --validar'.",
        f"  separacion        {m.get('separacion', float('nan')):.3f}"
        f"   (coseno medio entre grupos del mismo tema; dos",
        "                     centroides al azar dan 0,66, esa vara si es",
        "                     correcta -- no depende del tamano del tema. Lo",
        "                     que no hace es justificar el umbral: el enlace",
        "                     completo la obliga a subir con el. Ver --validar.)",
        "",
        "El ruido no es un fallo: un motivo de consulta que nadie mas escribio",
        "de forma parecida no pertenece a ningun grupo. Ver agrupar.py.",
        "",
        "Estas cifras describen la corrida, no la validan. Lo segundo es",
        "'python -m clustering --validar': modelo nulo, estabilidad y contraste",
        "contra el catalogo clinico. Leerlo antes de apoyar decisiones aqui.",
        "",
        "=" * 70,
        "TEMAS (por notas) -- ESTE ES EL NIVEL QUE SE CRUZA CONTRA CLIMA",
        "=" * 70,
    ]

    for fila in corrida.tabla_temas().itertuples(index=False):
        if fila.tema == -1:
            continue
        lineas.append(
            f"  {fila.tema:3d}  {fila.notas:5,} notas ({fila.parte:4.1%})  "
            f"{fila.grupos:3d} grupos  {fila.nombre}")
        lineas.append(f"       ejemplo: {_recortar(fila.representante, 105)}")

    lineas += [
        "",
        "=" * 70,
        "GRUPOS (por notas) -- el nivel fino, con el tema de cada uno",
        "=" * 70,
        "Sirve para auditar la fusion: si dos grupos del mismo tema no tienen",
        "nada que ver, o dos de temas distintos son lo mismo, se ve aqui.",
        "",
    ]

    for fila in corrida.tabla().itertuples(index=False):
        if fila.cluster == -1:
            continue
        lineas.append(
            f"  {fila.cluster:3d}  {fila.notas:5,} notas  "
            f"{fila.textos:4,} textos  conf {fila.confianza:.2f}  "
            f"[tema {fila.tema:2d}] {fila.nombre}")
        lineas.append(f"       ejemplo: {_recortar(fila.representante, 105)}")

    if corrida.informe_anclas:
        from clustering import anclas as _anclas
        lineas += ["", "=" * 70, ""]
        lineas.append(_anclas.texto(corrida.informe_anclas))
    else:
        lineas += [
            "",
            "=" * 70,
            "SIN ANCLAS: LOS NUMEROS DE TEMA DE ESTA CORRIDA NO SON COMPARABLES",
            "  con los de ninguna otra. Se renumeran por tamano, asi que el tema",
            "  12 de hoy no es el tema 12 de la semana que viene. Medido: sin",
            "  anclaje solo el 64-74% de las notas cae en el mismo tema al",
            "  repetir la corrida; con anclaje, el 95-97%.",
            "",
            "  Antes de construir cualquier serie temporal:",
            "      python -m clustering --anclar",
        ]

    if corrida.difusas:
        lineas += [
            "",
            "PALABRAS QUE NO NOMBRAN NADA",
            "  Salen en mas de la mitad de los clusters. Candidatas a",
            "  datos/palabras_vacias.txt; se agregan a mano a proposito.",
        ]
        lineas += [f"  {palabra:24} {reparto:.0%} de los clusters"
                   for palabra, reparto in corrida.difusas[:25]]

    return "\n".join(lineas) + "\n"


def _recortar(texto, largo):
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= largo else texto[:largo - 3] + "..."
