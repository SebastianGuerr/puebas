"""
Descarga de notas desde la base de datos.

POR QUE ESTA AQUI Y NO EN procesar.py
    Eran dos funciones con la tabla, la columna y el limite escritos dentro, asi
    que leer otra columna o probar sobre otra tabla obligaba a editar el
    orquestador. Aqui reciben todo por parametro y sirven para cualquier tabla
    del almacen.

    nucleo/conexion_bd.py sigue siendo quien sabe COMO conectarse; este modulo
    solo sabe QUE pedir.
"""

import pandas as pd


def filtro_no_vacio(columna):
    """Condicion SQL estandar: la columna trae texto de verdad."""
    return f"{columna} IS NOT NULL AND LTRIM(RTRIM({columna})) <> ''"


def muestra(engine, tabla, columnas, filtro, limite=None, disperso=True,
            llave="OID"):
    """
    Descarga hasta `limite` filas. Con disperso, la seleccion se reparte por
    toda la tabla en vez de traer las primeras.

    EL ORDEN ES PSEUDOALEATORIO PERO REPETIBLE, Y ESO IMPORTA MUCHO.
        Lo natural aqui es ORDER BY NEWID(), que sortea una muestra distinta en
        cada corrida. Suena inofensivo hasta que se cruza con una cache: la
        cache guarda el resultado de cada TEXTO, asi que si la corrida siguiente
        trae otras 5.000 filas, casi nada coincide y se vuelve a pagar el
        trabajo entero.

        Paso de verdad: una corrida dejo 4.234 textos corregidos tras horas de
        trabajo, y relanzarla habria reaprovechado una fraccion minima.

        HASHBYTES sobre la llave da el mismo reparto disperso pero SIEMPRE el
        mismo, asi que repetir una corrida es casi gratis y subir el limite
        conserva la muestra anterior y solo anade filas nuevas.
    """
    top = f"TOP {limite}" if limite else ""
    orden = (f"ORDER BY HASHBYTES('MD5', CAST({llave} AS varchar(20)))"
             if (limite and disperso) else "")
    campos = ", ".join(columnas)
    consulta = f"SELECT {top} {campos} FROM {tabla} WHERE {filtro} {orden}"
    return pd.read_sql(consulta, engine)


def columna_suelta(engine, tabla, columna, filtro, limite):
    """
    Una sola columna, sin orden particular, para contar frecuencias.

    Se lee mas texto del que se va a procesar a proposito: los desempates por
    frecuencia son mejores cuanto mayor es el corpus observado, y para contar da
    igual que filas toquen.
    """
    consulta = f"SELECT TOP {limite} {columna} FROM {tabla} WHERE {filtro}"
    return pd.read_sql(consulta, engine)
