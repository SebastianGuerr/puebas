import pandas as pd
import re
from itertools import combinations
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

# =====================================================
# CONFIGURACION
# =====================================================

MAX_MUESTRA = 5000

MIN_DISTINTOS = 10

COLUMNAS_EXCLUIDAS = {

    # tecnicas
    "OID",
    "OPTIMISTICLOCKFIELD",
    "RN",
    "VECES",

    # dominios pequeños
    "SEXO",
    "MES",
    "DIA",

    "ANO",
    "AÑO",
    "ANNO",

    "ACTIVO",
    "ESACTIVO",
    "VIGENTE",

    "ESTADO",
    "ESTADOOID",

    "COLOR",

    "TRASLADO",
    "EGRESO",

    "TIPOINGRESO",
    "TIPORIESGO",

    # campos que suelen producir falsos positivos
    "EDAD",
    "EDADCALCULADA",

    "DIAS",
    "DIASESTANCIA",
    "DIASEGRESO",

    "USUARIO",
    "USUARIOREGISTRO",

    "SERVICIO",
    "NOMBRE",

    "MUNICIPIO",
    "DEPTO",
    "DEPARTAMENTO",

    "ENTIDAD",
    "ASEGURADOR",
    "ASEGURADORA"
}

# =====================================================
# CONEXION SQL SERVER
# =====================================================

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

print("Conectado")

# =====================================================
# OBTENER DICCIONARIO
# =====================================================

query = """
SELECT
    TABLE_NAME,
    COLUMN_NAME,
    DATA_TYPE
FROM INFORMATION_SCHEMA.COLUMNS
"""

df_cols = pd.read_sql(query, engine)

print(f"Columnas encontradas: {len(df_cols)}")

# =====================================================
# NORMALIZACION
# =====================================================

def normalizar(nombre):

    nombre = nombre.upper()

    nombre = re.sub(
        r'[^A-Z0-9]',
        '',
        nombre
    )

    nombre = re.sub(
        r'\d+$',
        '',
        nombre
    )

    return nombre


df_cols["NOMBRE_NORMALIZADO"] = (
    df_cols["COLUMN_NAME"]
    .astype(str)
    .apply(normalizar)
)

# =====================================================
# FILTRAR COLUMNAS TECNICAS
# =====================================================

# excluir columnas de la lista

df_cols = df_cols[
    ~df_cols["NOMBRE_NORMALIZADO"]
    .isin(COLUMNAS_EXCLUIDAS)
]

# excluir cualquier columna que contenga FECHA

df_cols = df_cols[
    ~df_cols["NOMBRE_NORMALIZADO"]
    .str.contains(
        "FECHA",
        na=False
    )
]

# =====================================================
# GENERAR CANDIDATOS
# =====================================================

candidatos = []

grupos = (
    df_cols.groupby(
        "NOMBRE_NORMALIZADO"
    )
)

for _, grupo in grupos:

    if len(grupo) < 2:
        continue

    registros = grupo.to_dict("records")

    for a, b in combinations(
        registros,
        2
    ):

        if a["TABLE_NAME"] == b["TABLE_NAME"]:
            continue

        candidatos.append(
            {
                "tabla1": a["TABLE_NAME"],
                "columna1": a["COLUMN_NAME"],
                "tipo1": a["DATA_TYPE"],
                "tabla2": b["TABLE_NAME"],
                "columna2": b["COLUMN_NAME"],
                "tipo2": b["DATA_TYPE"]
            }
        )

print(
    f"Candidatos generados: "
    f"{len(candidatos)}"
)

# =====================================================
# FUNCION MATCH
# =====================================================

def calcular_match(
    tabla1,
    columna1,
    tabla2,
    columna2
):

    try:

        sql1 = f"""
        SELECT DISTINCT TOP ({MAX_MUESTRA})
        [{columna1}] valor
        FROM [{tabla1}]
        WHERE [{columna1}] IS NOT NULL
        """

        sql2 = f"""
        SELECT DISTINCT TOP ({MAX_MUESTRA})
        [{columna2}] valor
        FROM [{tabla2}]
        WHERE [{columna2}] IS NOT NULL
        """

        df1 = pd.read_sql(
            sql1,
            engine
        )

        df2 = pd.read_sql(
            sql2,
            engine
        )

        if df1.empty or df2.empty:
            return None

        s1 = set(
            df1["valor"]
            .astype(str)
        )

        s2 = set(
            df2["valor"]
            .astype(str)
        )

        if len(s1) < MIN_DISTINTOS:
            return None

        if len(s2) < MIN_DISTINTOS:
            return None

        comunes = s1.intersection(s2)

        if len(s1) == 0:
            return None

        porcentaje_origen = (
            len(comunes)
            / len(s1)
        ) * 100

        porcentaje_destino = (
            len(comunes)
            / len(s2)
        ) * 100

        score = (
            porcentaje_origen
            +
            porcentaje_destino
        ) / 2

        return {
            "comunes": len(comunes),
            "origen": len(s1),
            "destino": len(s2),
            "match_origen":
                round(
                    porcentaje_origen,
                    2
                ),
            "match_destino":
                round(
                    porcentaje_destino,
                    2
                ),
            "score":
                round(
                    score,
                    2
                )
        }

    except Exception as ex:

        return {
            "error": str(ex)
        }

# =====================================================
# EVALUACION
# =====================================================

resultado = []

total = len(candidatos)

for n, cand in enumerate(
    candidatos,
    start=1
):

    print(
        f"[{n}/{total}] "
        f"{cand['tabla1']}.{cand['columna1']} "
        f"<-> "
        f"{cand['tabla2']}.{cand['columna2']}"
    )

    datos = calcular_match(
        cand["tabla1"],
        cand["columna1"],
        cand["tabla2"],
        cand["columna2"]
    )

    if datos is None:
        continue

    if "error" in datos:
        continue

    resultado.append({

        "TABLA_ORIGEN":
            cand["tabla1"],

        "COLUMNA_ORIGEN":
            cand["columna1"],

        "TIPO_ORIGEN":
            cand["tipo1"],

        "TABLA_DESTINO":
            cand["tabla2"],

        "COLUMNA_DESTINO":
            cand["columna2"],

        "TIPO_DESTINO":
            cand["tipo2"],

        "VALORES_COMUNES":
            datos["comunes"],

        "VALORES_ORIGEN":
            datos["origen"],

        "VALORES_DESTINO":
            datos["destino"],

        "MATCH_ORIGEN":
            datos["match_origen"],

        "MATCH_DESTINO":
            datos["match_destino"],

        "SCORE":
            datos["score"]
    })

# =====================================================
# EXPORTAR CSV
# =====================================================

df_rel = pd.DataFrame(resultado)

if not df_rel.empty:

    df_rel = df_rel.sort_values(
        "SCORE",
        ascending=False
    )

df_rel.to_csv(
    "relaciones_detectadas.csv",
    index=False,
    encoding="utf-8-sig"
)

print(
    "Archivo generado:"
)
print(
    "relaciones_detectadas.csv"
)

# =====================================================
# EXPORTAR TXT
# =====================================================

with open(
    "relaciones_detectadas.txt",
    "w",
    encoding="utf-8"
) as f:

    f.write(
        "RELACIONES DETECTADAS\n"
    )

    f.write(
        df_rel.to_string(index=False)
    )