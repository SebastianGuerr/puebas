"""
Conexion a la base de datos DWSES: unico punto del paquete que construye el
engine de SQLAlchemy (autenticacion integrada de Windows). Ejecutado
directamente (`python -m NLP.nucleo.conexion_bd`) comprueba la conexion. Ver
ARQUITECTURA.md §2.2 (`conexion_bd.py`).
"""

from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def obtener_engine():
    """
    Devuelve un Engine de SQLAlchemy conectado a DWSES mediante el driver ODBC
    18 de SQL Server con autenticación integrada.
    """

    connection_url = URL.create(
        "mssql+pyodbc",
        host="ls-cobra",
        database="DWSES",
        query={
            "driver": "ODBC Driver 18 for SQL Server",
            "Trusted_Connection": "yes",
            "TrustServerCertificate": "yes",
        },
    )

    return create_engine(connection_url)


if __name__ == "__main__":
    engine = obtener_engine()
    print("Conectado correctamente")
