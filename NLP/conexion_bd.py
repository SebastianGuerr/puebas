# conexion_bd.py

from sqlalchemy import create_engine
from sqlalchemy.engine import URL


def obtener_engine():
    """
    Retorna una instancia de SQLAlchemy Engine
    para conectarse a DWSES.
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