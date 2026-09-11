"""
Una corrida completa: de los embeddings guardados a clusters con nombre.

QUE HACE ESTE MODULO Y POR QUE EXISTE APARTE
    Encadena los cuatro pasos -- leer, reducir, agrupar, nombrar -- y no hace
    nada mas. Ni dibuja ni imprime.

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

from clustering import agrupar, corpus, etiquetas, rutas


@dataclass
class Corrida:
    """
    El resultado completo, ya listo para dibujar o escribir.

    textos    un renglon por texto distinto vivo, con todo pegado: fila, texto,
              n_notas, cluster, confianza y las coordenadas x, y del mapa.
    nombres   {cluster: 'palabra palabra palabra'}
    representantes {cluster: el texto real mas central del grupo}
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
    firma: tuple = None
    parametros: dict = field(default_factory=dict)

    def nombre_de(self, cluster):
        """El nombre de un cluster, con el numero delante para poder citarlo."""
        if cluster == -1:
            return "ruido"
        return f"{cluster}. {self.nombres.get(cluster, 'sin nombre')}"

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
        return (agregado.sort_values(["notas", "textos"], ascending=False)
                .reset_index(drop=True)
                [["cluster", "nombre", "textos", "notas", "confianza",
                  "representante"]])


def ejecutar(minimo_notas=1, vecinos=agrupar.VECINOS,
             dimensiones=agrupar.DIMENSIONES,
             tamano_minimo=agrupar.TAMANO_MINIMO,
             muestras_minimas=agrupar.MUESTRAS_MINIMAS):
    """
    Corre los cuatro pasos y devuelve una Corrida.

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
                                        muestras_minimas=muestras_minimas)
    plano = agrupar.proyectar_mapa(vectores)

    textos = textos.copy()
    textos["cluster"] = np.asarray(grupos, dtype=int)
    textos["confianza"] = np.asarray(confianza, dtype=float)
    textos["x"] = np.asarray(plano)[:, 0]
    textos["y"] = np.asarray(plano)[:, 1]

    nombres, representantes, difusas = etiquetas.nombrar(
        textos, textos["cluster"].to_numpy(), vectores)

    return Corrida(
        textos=textos,
        indice=indice,
        nombres=nombres,
        representantes=representantes,
        difusas=difusas,
        metricas=agrupar.resumen(textos["cluster"].to_numpy(),
                                 textos["n_notas"].to_numpy()),
        firma=marca,
        parametros={
            "minimo_notas": minimo_notas,
            "vecinos": vecinos,
            "dimensiones": dimensiones,
            "tamano_minimo": tamano_minimo,
            "muestras_minimas": muestras_minimas or tamano_minimo,
            "semilla": agrupar.SEMILLA,
        },
    )


# ==========================================================
# ESCRITURA -- solo dentro de clustering/salidas/
# ==========================================================

def guardar(corrida):
    """
    Deja en salidas/ los cuatro archivos de datos que describe rutas.py.

    El mapa.png no se escribe aqui porque para tenerlo hace falta una figura ya
    dibujada, y eso es asunto de mapa.py.

    asignacion.parquet es el que importa para lo que viene despues: devuelve el
    cluster a cada OID deshaciendo la deduplicacion, y es la tabla que se cruza
    por OID con la fecha de triage para buscar los patrones temporales, que es
    el objetivo del proyecto. Los otros tres son para mirar y para poder
    comparar dos corridas.
    """
    asignacion = corpus.repartir(corrida.textos, corrida.indice)
    asignacion.to_parquet(rutas.ASIGNACION, index=False)

    tabla = corrida.tabla()
    # utf-8-sig y no utf-8: sin el BOM, Excel en Windows abre el CSV en cp1252 y
    # parte todas las tildes de los textos representantes.
    tabla.to_csv(rutas.CLUSTERS, index=False, encoding="utf-8-sig")

    corrida.textos[["fila", "texto", "n_notas", "cluster", "confianza",
                    "x", "y"]].to_parquet(rutas.PROYECCION, index=False)

    rutas.INFORME.write_text(_informe(corrida), encoding="utf-8")
    return asignacion, tabla


def _informe(corrida):
    """
    Las metricas y los parametros de la corrida, en texto plano.

    Va con los parametros dentro y no solo las cifras: un informe que dice '36
    clusters y 30% de ruido' sin decir con que tamano minimo salio no se puede
    comparar con el de la semana que viene, que es la unica razon de escribirlo.
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
        "",
        "El ruido no es un fallo: un motivo de consulta que nadie mas escribio",
        "de forma parecida no pertenece a ningun grupo. Ver agrupar.py.",
        "",
        "CLUSTERS (por notas)",
    ]

    for fila in corrida.tabla().itertuples(index=False):
        if fila.cluster == -1:
            continue
        lineas.append(
            f"  {fila.cluster:3d}  {fila.notas:5,} notas  "
            f"{fila.textos:4,} textos  conf {fila.confianza:.2f}  "
            f"{fila.nombre}")
        lineas.append(f"       ejemplo: {_recortar(fila.representante, 110)}")

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
