"""
Conexión a la base de datos DWSES.

Único punto del paquete que construye el engine de SQLAlchemy. La autenticación
es integrada de Windows, de modo que no hay credenciales en el código ni en el
repositorio; si en algún momento se pasa a usuario y contraseña, deben leerse de
variables de entorno.

Ejecutado directamente comprueba que la conexión se establece:

    python -m NLP.nucleo.conexion_bd
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
