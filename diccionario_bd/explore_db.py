import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

# ==========================================================
# CONEXION
# ==========================================================

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

engine = create_engine(connection_url)

print("Conectado correctamente")

# ==========================================================
# CONSULTA METADATOS
# ==========================================================

query = """
SELECT
    TABLE_SCHEMA,
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE,
    CHARACTER_MAXIMUM_LENGTH,
    NUMERIC_PRECISION,
    NUMERIC_SCALE,
    IS_NULLABLE,
    ORDINAL_POSITION
FROM INFORMATION_SCHEMA.COLUMNS
ORDER BY
    TABLE_SCHEMA,
    TABLE_NAME,
    ORDINAL_POSITION
"""

df = pd.read_sql(query, engine)

# ==========================================================
# FUNCION PARA FORMATEAR TIPOS DE DATOS
# ==========================================================

def obtener_tipo_dato(row):

    tipo = row["DATA_TYPE"]

    if pd.notna(row["CHARACTER_MAXIMUM_LENGTH"]):

        longitud = int(row["CHARACTER_MAXIMUM_LENGTH"])

        if longitud == -1:
            return f"{tipo}(MAX)"

        return f"{tipo}({longitud})"

    if pd.notna(row["NUMERIC_PRECISION"]):

        precision = int(row["NUMERIC_PRECISION"])

        if pd.notna(row["NUMERIC_SCALE"]):

            escala = int(row["NUMERIC_SCALE"])

            if escala > 0:
                return f"{tipo}({precision},{escala})"

    return tipo


df["TIPO_COMPLETO"] = df.apply(
    obtener_tipo_dato,
    axis=1
)

# ==========================================================
# ARCHIVO 1
# tablas_y_columnas.csv
# ==========================================================

resultado = []

for (schema, tabla), grupo in df.groupby(
    ["TABLE_SCHEMA", "TABLE_NAME"]
):

    grupo = grupo.sort_values(
        "ORDINAL_POSITION"
    )

    fila = {
        "TABLE_SCHEMA": schema,
        "TABLE_NAME": tabla
    }

    for i, (_, reg) in enumerate(
        grupo.iterrows(),
        start=1
    ):

        fila[f"Columna_{i}"] = reg["COLUMN_NAME"]
        fila[f"TipoDato_{i}"] = reg["TIPO_COMPLETO"]
        fila[f"Nullable_{i}"] = reg["IS_NULLABLE"]

    resultado.append(fila)

df_tablas = pd.DataFrame(resultado)

df_tablas.to_csv(
    "tablas_y_columnas.csv",
    index=False,
    encoding="utf-8-sig"
)

print("Generado: tablas_y_columnas.csv")

# ==========================================================
# ARCHIVO 2
# diccionario_columnas.csv
# ==========================================================

diccionario = df[
    [
        "TABLE_SCHEMA",
        "TABLE_NAME",
        "COLUMN_NAME",
        "TIPO_COMPLETO",
        "IS_NULLABLE",
        "ORDINAL_POSITION",
    ]
].copy()

diccionario.columns = [
    "ESQUEMA",
    "TABLA",
    "COLUMNA",
    "TIPO_DATO",
    "PERMITE_NULL",
    "POSICION"
]

diccionario = diccionario.sort_values(
    ["TABLA", "POSICION"]
)

diccionario.to_csv(
    "diccionario_columnas.csv",
    index=False,
    encoding="utf-8-sig"
)

print("Generado: diccionario_columnas.csv")

# ==========================================================
# RESUMEN
# ==========================================================

print("\n==============================")
print("PROCESO FINALIZADO")
print("==============================")
print(f"Tablas encontradas: {df['TABLE_NAME'].nunique()}")
print(f"Columnas encontradas: {len(df)}")
print("==============================")