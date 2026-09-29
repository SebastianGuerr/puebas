"""
Las consultas. Todas agregadas, todas sobre columnas no sensibles.

    python -m extraccion --esquema      lista columnas y las clasifica
    python -m extraccion --cobertura    que esta lleno y desde cuando
    python -m extraccion --series       escribe salidas/*.parquet

CADA CONSULTA VA CON SU GROUP BY. NO HAY NINGUNA QUE DEVUELVA FILAS DE PACIENTE.
    Es lo que hace que esto se pueda correr sin revisar nada: el agregado mas fino
    que se baja es dia x hora x nivel x banda de edad, y la casilla mas pequena
    tiene decenas de personas dentro.
"""

import argparse
import sys
import warnings

import pandas as pd

from extraccion import BANDAS_EDAD, SENSIBLES, motor

warnings.filterwarnings("ignore", message=".*Unrecognized server version.*")

TABLAS = ["DIM_TRIAGE", "DIM_HCNCONTRDT", "DIM_HCNCLAURGTR", "HCNCONCOTRI_DW"]


def esquema(eng):
    """Las columnas y su clasificacion. No baja ni una fila de datos."""
    marcas = ",".join(f"'{t}'" for t in TABLAS)
    tabla = pd.read_sql(
        f"SELECT TABLE_NAME, COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS "
        f"WHERE TABLE_NAME IN ({marcas}) ORDER BY TABLE_NAME, ORDINAL_POSITION", eng)
    for nombre, grupo in tabla.groupby("TABLE_NAME"):
        print(f"\n=== {nombre}")
        for _, fila in grupo.iterrows():
            motivo = SENSIBLES.get(nombre, {}).get(fila.COLUMN_NAME)
            marca = f"  <-- SENSIBLE: {motivo}" if motivo else ""
            print(f"   {fila.COLUMN_NAME:<22} {fila.DATA_TYPE}{marca}")


def cobertura(eng):
    """Que fraccion de cada ano tiene cada columna. Solo cuenta, no lee valores."""
    tabla = pd.read_sql("""
        SELECT YEAR(t.HCTFECTRI) AS anio, COUNT(*) AS triages,
          SUM(CASE WHEN t.GENDIAGNO1 IS NOT NULL AND t.GENDIAGNO1 <> 0 THEN 1 ELSE 0 END) AS diagnostico,
          SUM(CASE WHEN t.HCTMOTCON IS NOT NULL AND LEN(LTRIM(RTRIM(t.HCTMOTCON))) > 0 THEN 1 ELSE 0 END) AS texto,
          SUM(CASE WHEN t.HCNCLAURGTR IS NOT NULL AND t.HCNCLAURGTR <> 0 THEN 1 ELSE 0 END) AS nivel,
          SUM(CASE WHEN t.HCTEDAD IS NOT NULL THEN 1 ELSE 0 END) AS edad,
          SUM(CASE WHEN d.HCCFECSAL IS NOT NULL AND d.HCCFECSAL >= d.HCCFECTUR THEN 1 ELSE 0 END) AS estancia
        FROM dbo.DIM_TRIAGE t LEFT JOIN dbo.DIM_HCNCONTRDT d ON t.HCNCONTRDT = d.OID
        WHERE t.HCTFECTRI IS NOT NULL GROUP BY YEAR(t.HCTFECTRI) ORDER BY anio""", eng)

    columnas = ["diagnostico", "texto", "nivel", "edad", "estancia"]
    print(f"\n{'anio':>6}{'triages':>10}" + "".join(f"{c:>13}" for c in columnas))
    for _, fila in tabla.iterrows():
        porcentajes = "".join(f"{100 * fila[c] / fila.triages:12.1f}%" for c in columnas)
        print(f"{int(fila.anio):6d}{int(fila.triages):10,}{porcentajes}")
    print("\nGENDIAGNO1 esta practicamente vacio: no hay CIE-10 gratis. "
          "El nivel y la edad estan al 100% desde 2020.")


def _caso_edad():
    """El CASE que reparte HCTEDAD en bandas. La edad nunca sale fila a fila."""
    ramas = " ".join(
        f"WHEN t.HCTEDAD BETWEEN {desde} AND {hasta} THEN '{desde}-{hasta if hasta < 200 else '+'}'"
        for desde, hasta in BANDAS_EDAD)
    return f"CASE {ramas} ELSE 'sin edad' END"


def series(eng, destino):
    """
    Las tres tablas agregadas que alimentan los cuadernos.

    Se escriben a parquet para que un cuaderno no necesite la base para correr.
    Es lo que hace que estas figuras las pueda reproducir alguien que no tenga
    acceso a la historia clinica -- un jurado, por ejemplo.
    """
    destino.mkdir(parents=True, exist_ok=True)

    print("  nivel de urgencia por dia x hora...", end=" ", flush=True)
    nivel = pd.read_sql("""
        SELECT CAST(t.HCTFECTRI AS DATE) AS dia,
               DATEPART(HOUR, t.HCTFECTRI) AS hora,
               c.HCCODIGO AS nivel, c.HCDESCRIP AS nivel_nombre,
               COUNT(*) AS n
        FROM dbo.DIM_TRIAGE t JOIN dbo.DIM_HCNCLAURGTR c ON t.HCNCLAURGTR = c.OID
        WHERE t.HCTFECTRI IS NOT NULL
        GROUP BY CAST(t.HCTFECTRI AS DATE), DATEPART(HOUR, t.HCTFECTRI),
                 c.HCCODIGO, c.HCDESCRIP""", eng)
    nivel["dia"] = pd.to_datetime(nivel["dia"])
    nivel.to_parquet(destino / "triage_nivel.parquet", index=False)
    print(f"{len(nivel):,} filas")

    print("  edad en bandas por dia...", end=" ", flush=True)
    edad = pd.read_sql(f"""
        SELECT CAST(t.HCTFECTRI AS DATE) AS dia,
               {_caso_edad()} AS banda, COUNT(*) AS n
        FROM dbo.DIM_TRIAGE t WHERE t.HCTFECTRI IS NOT NULL
        GROUP BY CAST(t.HCTFECTRI AS DATE), {_caso_edad()}""", eng)
    edad["dia"] = pd.to_datetime(edad["dia"])
    edad.to_parquet(destino / "triage_edad.parquet", index=False)
    print(f"{len(edad):,} filas")

    print("  estancia por dia...", end=" ", flush=True)
    estancia = pd.read_sql("""
        SELECT CAST(t.HCTFECTRI AS DATE) AS dia, COUNT(*) AS n,
               AVG(CAST(DATEDIFF(MINUTE, d.HCCFECTUR, d.HCCFECSAL) AS float)) AS media_min,
               MAX(DATEDIFF(MINUTE, d.HCCFECTUR, d.HCCFECSAL)) AS max_min
        FROM dbo.DIM_TRIAGE t JOIN dbo.DIM_HCNCONTRDT d ON t.HCNCONTRDT = d.OID
        WHERE t.HCTFECTRI IS NOT NULL AND d.HCCFECSAL >= d.HCCFECTUR
          AND DATEDIFF(MINUTE, d.HCCFECTUR, d.HCCFECSAL) <= 1440
        GROUP BY CAST(t.HCTFECTRI AS DATE)""", eng)
    estancia["dia"] = pd.to_datetime(estancia["dia"])
    estancia.to_parquet(destino / "triage_estancia.parquet", index=False)
    print(f"{len(estancia):,} filas")


def entidad(eng, destino):
    """
    Triages por dia x hora x entidad administradora (la EPS, la aseguradora SOAT, la ARL...).

    DIM_TRIAGE.GEENENTADM -> DIM_ENTIDAD.OID cruza en el 100% de 2020-2024 y el 99% de
    2025-2026 (medido el 2026-09-28). El nombre es el de una ORGANIZACION, no de una
    persona. Sirve para dos cosas que ninguna otra columna da: separar la demanda por
    asegurador (los cierres de servicios a una EPS) y ver mecanismos sin leer el
    motivo -- el SOAT es accidente de transito, la ARL accidente laboral.
    """
    destino.mkdir(parents=True, exist_ok=True)
    print("  entidad administradora por dia x hora...", end=" ", flush=True)
    tabla = pd.read_sql("""
        SELECT CAST(t.HCTFECTRI AS DATE) AS dia, DATEPART(HOUR, t.HCTFECTRI) AS hora,
               n.OID AS entidad_oid, n.ENTNOMBRE AS entidad, n.ENTTIPENT AS tipo_entidad,
               COUNT(*) AS n
        FROM dbo.DIM_TRIAGE t LEFT JOIN dbo.DIM_ENTIDAD n ON t.GEENENTADM = n.OID
        WHERE t.HCTFECTRI IS NOT NULL
        GROUP BY CAST(t.HCTFECTRI AS DATE), DATEPART(HOUR, t.HCTFECTRI),
                 n.OID, n.ENTNOMBRE, n.ENTTIPENT""", eng)
    tabla["dia"] = pd.to_datetime(tabla["dia"])
    tabla.to_parquet(destino / "triage_entidad.parquet", index=False)
    print(f"{len(tabla):,} filas")


def main(argv=None):
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="python -m extraccion")
    parser.add_argument("--esquema", action="store_true")
    parser.add_argument("--cobertura", action="store_true")
    parser.add_argument("--series", action="store_true")
    parser.add_argument("--entidad", action="store_true",
                        help="solo la serie por entidad administradora (EPS, SOAT, ARL)")
    args = parser.parse_args(argv)

    if not (args.esquema or args.cobertura or args.series or args.entidad):
        parser.print_help()
        return 1

    eng = motor()
    salidas = Path(__file__).resolve().parents[1] / "salidas"
    if args.esquema:
        esquema(eng)
    if args.cobertura:
        cobertura(eng)
    if args.series:
        series(eng, salidas)
    if args.series or args.entidad:
        entidad(eng, salidas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
