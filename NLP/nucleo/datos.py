"""
Descarga de notas desde la base de datos: consultas parametrizadas (tabla,
columna, limite), no atadas a ninguna tabla en particular. `nucleo/conexion_bd.py`
sabe COMO conectarse; este modulo solo sabe QUE pedir. Ver ARQUITECTURA.md
§2.2 (`datos.py`).
"""

import pandas as pd


def filtro_no_vacio(columna):
    """Condicion SQL estandar: la columna trae texto de verdad."""
    return f"{columna} IS NOT NULL AND LTRIM(RTRIM({columna})) <> ''"


def muestra(engine, tabla, columnas, filtro, limite=None, disperso=True,
            llave="OID", excluir=None):
    """
    Descarga hasta `limite` filas. Con disperso, la seleccion se reparte por
    toda la tabla (HASHBYTES sobre la llave: pseudoaleatorio pero repetible,
    no ORDER BY NEWID()) en vez de traer las primeras. Ver ARQUITECTURA.md
    §2.2 (`datos.py`) para el porque del orden repetible.
    """
    excluir = set(excluir or ())
    top = f"TOP {limite}" if limite else ""
    orden = (f"ORDER BY HASHBYTES('MD5', CAST({llave} AS varchar(20)))"
             if (limite and disperso) else "")
    campos = ", ".join(columnas)

    if not excluir:
        consulta = f"SELECT {top} {campos} FROM {tabla} WHERE {filtro} {orden}"
        return pd.read_sql(consulta, engine)

    # Las ya hechas se descartan aqui, en el WHERE, y no filtrando en pandas
    # despues de bajarlas: con un orden fijo, filtrar despues hace que
    # `limite` cuente filas leidas y no filas utiles (pedir 5.000 cuando ya
    # hay 5.000 hechas devolveria esas mismas, ni una nueva).
    #
    # La lista va a una tabla temporal y no a un IN (...): un IN de ese
    # tamano es costoso de analizar para el servidor en cada corrida.
    with engine.begin() as conexion:
        conexion.exec_driver_sql(f"DROP TABLE IF EXISTS #ya_procesadas")
        conexion.exec_driver_sql(
            f"CREATE TABLE #ya_procesadas ({llave} bigint PRIMARY KEY)")

        # SQL Server admite 1.000 tuplas por VALUES, asi que el lote es ese.
        claves = sorted(int(k) for k in excluir)
        for inicio in range(0, len(claves), 1000):
            tuplas = ",".join(f"({k})" for k in claves[inicio:inicio + 1000])
            conexion.exec_driver_sql(
                f"INSERT INTO #ya_procesadas ({llave}) VALUES {tuplas}")

        consulta = (
            f"SELECT {top} {campos} FROM {tabla} AS t "
            f"WHERE {filtro} "
            f"AND NOT EXISTS (SELECT 1 FROM #ya_procesadas AS y "
            f"WHERE y.{llave} = t.{llave}) {orden}"
        )
        return pd.read_sql(consulta, conexion)


def columna_suelta(engine, tabla, columna, filtro, limite):
    """
    Una sola columna, sin orden particular, para contar frecuencias. Se lee
    a proposito mas texto del que se va a procesar: para contar da igual que
    filas toquen, y un corpus mayor da mejores desempates.
    """
    consulta = f"SELECT TOP {limite} {columna} FROM {tabla} WHERE {filtro}"
    return pd.read_sql(consulta, engine)
