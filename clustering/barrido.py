"""
Probar muchas combinaciones de parametros y medirlas. No agrupa para producir:
agrupa para decidir con que parametros agrupar.

    python -m clustering --barrido

POR QUE ESTO EXISTE
    TAMANO_MINIMO, DIMENSIONES y MUESTRAS_MINIMAS no tienen un valor correcto
    que se pueda razonar desde el escritorio: dependen de cuantos textos hay y
    de como se reparten, y las dos cosas cambian cada vez que NLP/ escribe. Lo
    que hoy da 36 grupos limpios sobre 1.957 textos no tiene por que darlos
    sobre 20.000. Este modulo se vuelve a correr en cada salto de tamano del
    corpus, y por eso es codigo y no una sesion de notebook que se perdio.

LO QUE HACE BARATO EL BARRIDO
    UMAP es casi todo el costo y HDBSCAN es casi nada. Asi que la reduccion se
    hace UNA vez por cada (vecinos, dimensiones) y encima se prueban todas las
    combinaciones de HDBSCAN sin volver a reducir. Un barrido de 6 reducciones
    y 96 agrupamientos cuesta lo que cuestan las 6 reducciones.

NO HAY UNA CONFIGURACION 'GANADORA' Y EL MODULO NO LA INVENTA
    Bajar el ruido y subir la coherencia son objetivos opuestos: todo lo que se
    rescata del ruido entra a algun grupo, y lo dudoso que entra lo afloja. No
    existe el numero que resuelva ese cambio por ti, porque depende de para que
    sea el resultado -- describir el corpus tolera mas ruido que alimentar un
    cruce temporal, que necesita cobertura.

    Por eso la salida no es un ganador sino LA FRONTERA: las configuraciones
    que nadie supera en las dos cosas a la vez. Todo lo que no esta en la
    frontera se puede descartar sin pensarlo, porque hay otra que le gana en
    ruido Y en coherencia. Entre las que quedan hay que elegir, y esa eleccion
    es del que mira, no del script.
"""

import time

import numpy as np
import pandas as pd

from clustering import agrupar, corpus, rutas

# ==========================================================
# LA REJILLA -- lo que se prueba
# ==========================================================
#
# Deliberadamente corta. Una rejilla grande no da mejor respuesta, da mas filas
# que leer: estos rangos ya cubren de 'muchos grupos especificos' a 'pocos y
# genericos', y lo que hay en medio no cambia la decision.

VECINOS = (15, 30)

# Tres valores y no mas, y el motivo es un resultado del propio barrido: sobre
# este corpus las dimensiones casi no mueven nada. A parametros de HDBSCAN
# fijos, pasar de 5 a 50 cambia la coherencia en menos de 0,01 y el ruido en
# unos pocos puntos sin direccion clara -- es ruido de medida, no una tendencia.
# Se siguen probando porque eso puede dejar de ser cierto cuando el corpus sea
# diez veces mas grande, pero no merecen una rejilla fina.
DIMENSIONES = (5, 10, 30)

TAMANO_MINIMO = (8, 10, 15, 20)

# None = igualarlo a tamano_minimo, que es lo mas estricto posible.
MUESTRAS_MINIMAS = (1, 3, 5, None)


def ejecutar(vecinos=VECINOS, dimensiones=DIMENSIONES,
             tamanos=TAMANO_MINIMO, muestras=MUESTRAS_MINIMAS,
             minimo_notas=1, aviso=print):
    """
    Devuelve un DataFrame con una fila por combinacion y sus metricas.

    ruido_n y coherencia son las dos columnas con las que se decide; las demas
    estan para entender por que salieron asi.
    """
    textos, vectores, indice = corpus.instantanea(minimo_notas=minimo_notas)
    n_notas = textos["n_notas"].to_numpy()
    aviso(f"{len(textos):,} textos distintos / {n_notas.sum():,} notas")

    total = len(vecinos) * len(dimensiones)
    filas = []
    hecho = 0

    for v in vecinos:
        for d in dimensiones:
            hecho += 1
            inicio = time.time()
            aviso(f"  [{hecho}/{total}] reduciendo  vecinos={v} dimensiones={d} ...")
            proyeccion = agrupar.proyectar(vectores, dimensiones=d, vecinos=v)
            aviso(f"        {time.time() - inicio:.0f}s")

            for tam in tamanos:
                for mue in muestras:
                    # Pedir mas evidencia que tamano no significa nada: HDBSCAN
                    # no puede declarar un grupo mas chico que su propia
                    # exigencia de densidad.
                    if mue is not None and mue > tam:
                        continue
                    etq, _ = agrupar.agrupar(proyeccion, tamano_minimo=tam,
                                             muestras_minimas=mue)
                    filas.append(_medir(etq, vectores, n_notas, v, d, tam, mue))

    tabla = pd.DataFrame([f for f in filas if f is not None])
    if tabla.empty:
        raise SystemExit(
            "Ninguna combinacion produjo un solo grupo. Con esta cantidad de "
            "textos no hay densidad que encontrar: deja avanzar el pipeline.")
    return tabla.sort_values(["coherencia", "ruido_n"],
                             ascending=[False, True]).reset_index(drop=True)


def _medir(etiquetas, vectores, n_notas, vecinos, dims, tam, mue):
    """Las cifras de una combinacion, o None si no encontro ningun grupo."""
    resumen = agrupar.resumen(etiquetas, n_notas)
    if not resumen["clusters"]:
        return None
    etiquetas = np.asarray(etiquetas)
    tamanos = [int((etiquetas == c).sum()) for c in set(etiquetas) - {-1}]
    return {
        "vecinos": vecinos,
        "dims": dims,
        "tam_min": tam,
        "muestras": mue if mue is not None else tam,
        "clusters": resumen["clusters"],
        "ruido_t": resumen["ruido_textos"],
        "ruido_n": resumen["ruido_notas"],
        "coherencia": agrupar.coherencia(vectores, etiquetas, n_notas),
        "grupo_mediano": int(np.median(tamanos)),
        "grupo_mayor": int(max(tamanos)),
        "absorbido": float(max(tamanos) / len(etiquetas)),
    }


# Fraccion del corpus que un solo grupo puede llegar a tener antes de que la
# configuracion deje de describir nada. Ver _degeneradas().
MAXIMO_ABSORBIDO = 0.5


def _degeneradas(tabla):
    """
    Marca las configuraciones en las que un solo grupo se traga el corpus.

    Hay que quitarlas ANTES de buscar la frontera o se la quedan entera, y no
    por un fallo del criterio sino porque lo cumplen de verdad: con
    tamano_minimo y muestras_minimas los dos en 30 sale una corrida de 3 grupos
    con 1,3% de ruido en la que uno de ellos tiene 1.835 de los 1.957 textos.
    Casi nada queda fuera, ninguna otra la supera en cobertura, asi que
    encabeza la lista -- y no dice absolutamente nada, porque 'casi todo el
    corpus' no es un grupo.

    Es el recordatorio de que el ruido bajo no es el objetivo: se baja metiendo
    lo dudoso en algun grupo, y llevado al extremo eso es un solo grupo con
    todo dentro. La coherencia lo delata -- esas corridas caen a 0,70, cerca
    del 0,47 del azar -- pero para cuando se mira ya se perdio el tiempo
    leyendolas.
    """
    return tabla["absorbido"] > MAXIMO_ABSORBIDO


def frontera(tabla):
    """
    Las configuraciones que nadie supera en ruido Y en coherencia a la vez.

    Es un frente de Pareto sobre las dos columnas que importan. Lo que queda
    fuera esta estrictamente peor que alguna otra y no hay nada que pensar con
    ello; lo que queda dentro es una eleccion real entre cobertura y pureza.

    Las degeneradas no entran: ver _degeneradas().
    """
    tabla = tabla[~_degeneradas(tabla)]
    if tabla.empty:
        return tabla
    filas = tabla.sort_values("ruido_n").reset_index(drop=True)
    mejor = -1.0
    elegidas = []
    for fila in filas.itertuples(index=False):
        if fila.coherencia > mejor:
            elegidas.append(fila)
            mejor = fila.coherencia
    return pd.DataFrame(elegidas)


# ==========================================================
# SALIDA
# ==========================================================

def _linea(fila):
    return (f"  {fila.vecinos:>4}  {fila.dims:>4}  {fila.tam_min:>5}  "
            f"{fila.muestras:>5}  {fila.clusters:>5}  "
            f"{fila.ruido_t:>7.1%}  {fila.ruido_n:>7.1%}  "
            f"{fila.coherencia:>7.3f}  {fila.grupo_mediano:>6}  "
            f"{fila.grupo_mayor:>6}")


def _titulos():
    return ("  vecs  dims  t.min  mues  grupos  ruido_t  ruido_n  coheren  "
            "med.gr  may.gr")


def texto(tabla):
    """El informe del barrido: la frontera primero y la tabla entera debajo."""
    lineas = [
        "BARRIDO DE PARAMETROS",
        "",
        "COMO SE LEE",
        "  ruido_n     fraccion de NOTAS que no entro a ningun grupo. Es la",
        "              cobertura: con 40% de ruido, el cruce contra calendarios",
        "              se hace con el 60% del corpus.",
        "  coherencia  coseno medio de cada texto con el centro de su grupo, en",
        "              el espacio de bge-m3. Dos frases al azar de este corpus",
        "              dan 0,47: esa es la linea del suelo, no el cero.",
        "  med.gr      tamano mediano de grupo, en textos distintos. Si es casi",
        "              igual a t.min, los grupos se estan formando en el minimo",
        "              y el parametro esta apretando, no describiendo.",
        "",
        "LA FRONTERA -- ninguna de estas es peor que otra en las dos columnas",
        _titulos(),
    ]
    lineas += [_linea(f) for f in frontera(tabla).itertuples(index=False)]
    lineas += [
        "",
        "TODAS, por coherencia",
        _titulos(),
    ]
    lineas += [_linea(f) for f in tabla.itertuples(index=False)]

    cuantas = int(_degeneradas(tabla).sum())
    if cuantas:
        lineas += [
            "",
            f"{cuantas} configuracion(es) quedaron fuera de la frontera por",
            f"degeneradas: un solo grupo con mas del {MAXIMO_ABSORBIDO:.0%} de",
            "los textos dentro. Salen con poco ruido porque no dejan casi nada",
            "fuera, y no describen nada. Siguen en barrido.csv, con su fraccion",
            "en la columna 'absorbido'.",
        ]

    lineas += [
        "",
        "Elegida una fila, se fija en agrupar.py o se pasa por linea de comandos:",
        "  python -m clustering --dimensiones D --tamano-minimo T --muestras-minimas M",
    ]
    return "\n".join(lineas) + "\n"


def guardar(tabla):
    """Escribe salidas/barrido.csv y devuelve la ruta."""
    tabla.to_csv(rutas.BARRIDO, index=False, encoding="utf-8-sig")
    return rutas.BARRIDO
