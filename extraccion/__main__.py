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


MINIMO = 5   # toda casilla con menos casos se oculta (queda nula y marcada como suprimida)

# Causa de ingreso (DIM_INGRESO.AINCAUING): la base no trae catalogo y no existe
# diccionario (confirmado por el propietario el 2026-09-30). Solo se rotula lo que se
# descifro con evidencia, cruzando con el asegurador del triage (CONTEXTO, 2026-09-29).
CAUSAS = {3: "enfermedad general (probable)", 6: "accidente de transito (74 % SOAT)",
          10: "accidente laboral (74 % ARL)"}


def _suprimir(t, col="n"):
    """Oculta las casillas pequenas. Es lo que hace no identificable un conteo fino."""
    t = t.copy()
    t["suprimido"] = t[col] < MINIMO
    t.loc[t["suprimido"], col] = None
    return t


def perfil(eng, destino):
    """
    El perfil del hospital (cuaderno 10): que pasa con el triage y en que estado queda.
    SOLO AGREGADOS. Nada sale por paciente: los ingresos, folios y diagnosticos se unen
    DENTRO de la consulta y lo que sale son conteos por mes, semana o dia.

    Lo que se escribe, y si se versiona (ver .gitignore):
      perfil_ingreso_banda         mes x banda de edad x paso a ingreso           si
      perfil_ingreso_nivel         mes x nivel de triage x paso a ingreso         si
      perfil_area_mensual          mes x area de servicio (catalogo)             si
      perfil_causa_mensual         mes x causa de ingreso (codigo)               si
      perfil_dx_semanal            semana x capitulo CIE-10                      si
      perfil_dx_edad_anual         anio x capitulo CIE-10 x banda de edad        si
      perfil_dx_codigo_mensual     mes x codigo de 3 caracteres (solo >= 5)      si
      perfil_remisiones_motivo     mes x motivo (catalogo)                       si
      perfil_remisiones_servicio   anio x servicio que remite                    si
      perfil_dx_diario             dia x capitulo CIE-10, SIN suprimir           NO: local
    Todo con casillas < 5 ocultas, salvo el diario, que por eso no sale del equipo.
    Los cruces se eligen gruesos a proposito: con mes x motivo x servicio se ocultaba el
    81 % de las casillas, y con semana x capitulo x edad el 53 % (medido el 2026-09-30).
    """
    from extraccion.cie10 import capitulo
    destino.mkdir(parents=True, exist_ok=True)
    caso = _caso_edad()

    print("  paso a ingreso por mes x nivel x banda...", end=" ", flush=True)
    t = pd.read_sql(f"""
        SELECT DATEFROMPARTS(YEAR(t.HCTFECTRI), MONTH(t.HCTFECTRI), 1) AS mes, c.HCCODIGO AS nivel,
               {caso} AS banda,
               CASE WHEN t.ADNINGRESO IS NOT NULL AND t.ADNINGRESO <> 0 THEN 1 ELSE 0 END AS con_ingreso,
               COUNT(*) AS n
        FROM dbo.DIM_TRIAGE t JOIN dbo.DIM_HCNCLAURGTR c ON t.HCNCLAURGTR = c.OID
        WHERE t.HCTFECTRI IS NOT NULL
        GROUP BY DATEFROMPARTS(YEAR(t.HCTFECTRI), MONTH(t.HCTFECTRI), 1), c.HCCODIGO, {caso},
                 CASE WHEN t.ADNINGRESO IS NOT NULL AND t.ADNINGRESO <> 0 THEN 1 ELSE 0 END""", eng)
    for cruce, nombre in [("banda", "perfil_ingreso_banda"), ("nivel", "perfil_ingreso_nivel")]:
        g = t.groupby(["mes", cruce, "con_ingreso"], as_index=False)["n"].sum()
        _suprimir(g).to_parquet(destino / f"{nombre}.parquet", index=False)
    print(f"{len(t):,} filas")

    print("  area de servicio del ingreso por mes...", end=" ", flush=True)
    a = pd.read_sql("""
        SELECT DATEFROMPARTS(YEAR(t.HCTFECTRI), MONTH(t.HCTFECTRI), 1) AS mes,
               COALESCE(s.GASNOMBRE, '(sin area)') AS area, CAST(s.GASAREURG AS int) AS es_urgencias,
               COUNT(*) AS n
        FROM dbo.DIM_TRIAGE t JOIN dbo.DIM_INGRESO i ON t.ADNINGRESO = i.OID
        LEFT JOIN dbo.AREA_SERVICIO s ON i.GENARESER = s.OID
        WHERE t.HCTFECTRI IS NOT NULL
        GROUP BY DATEFROMPARTS(YEAR(t.HCTFECTRI), MONTH(t.HCTFECTRI), 1), s.GASNOMBRE, s.GASAREURG""", eng)
    _suprimir(a).to_parquet(destino / "perfil_area_mensual.parquet", index=False)
    print(f"{len(a):,} filas")

    print("  causa de ingreso por mes...", end=" ", flush=True)
    k = pd.read_sql("""
        SELECT DATEFROMPARTS(YEAR(t.HCTFECTRI), MONTH(t.HCTFECTRI), 1) AS mes, i.AINCAUING AS causa_codigo,
               COUNT(*) AS n
        FROM dbo.DIM_TRIAGE t JOIN dbo.DIM_INGRESO i ON t.ADNINGRESO = i.OID
        WHERE t.HCTFECTRI IS NOT NULL
        GROUP BY DATEFROMPARTS(YEAR(t.HCTFECTRI), MONTH(t.HCTFECTRI), 1), i.AINCAUING""", eng)
    k["causa"] = k["causa_codigo"].map(CAUSAS).fillna(k["causa_codigo"].map(lambda c: f"codigo {c} (sin catalogo)"))
    _suprimir(k).to_parquet(destino / "perfil_causa_mensual.parquet", index=False)
    print(f"{len(k):,} filas")

    # Diagnostico principal del primer folio de cada ingreso que viene de un triage. Se une
    # todo dentro de la consulta; sale dia x codigo de 3 caracteres x banda, ya contado.
    print("  diagnostico principal (CIE-10) por dia x codigo x banda...", end=" ", flush=True)
    dx = pd.read_sql(f"""
        WITH ing AS (SELECT t.ADNINGRESO AS ingreso, MIN(CAST(t.HCTFECTRI AS DATE)) AS dia, MIN({caso}) AS banda
                     FROM dbo.DIM_TRIAGE t WHERE t.HCTFECTRI IS NOT NULL AND t.ADNINGRESO <> 0
                     GROUP BY t.ADNINGRESO),
             dx AS (SELECT f.ADNINGRESO AS ingreso, g.DIACODIGO AS cod,
                           ROW_NUMBER() OVER (PARTITION BY f.ADNINGRESO ORDER BY f.HCFECFOL, c.OID) AS rn
                    FROM dbo.DIM_FOLIO f JOIN dbo.CONTROL_DIAGNOSTICO c ON c.HCNFOLIO = f.OID
                    JOIN dbo.DIM_DIAGNOSTICO g ON c.GENDIAGNO = g.OID WHERE c.HCPDIAPRIN = 1)
        SELECT ing.dia, LEFT(dx.cod, 3) AS cod3, ing.banda, COUNT(*) AS n
        FROM ing JOIN dx ON dx.ingreso = ing.ingreso AND dx.rn = 1
        GROUP BY ing.dia, LEFT(dx.cod, 3), ing.banda""", eng)
    dx["dia"] = pd.to_datetime(dx["dia"])
    dx["capitulo"] = dx["cod3"].map(capitulo)
    print(f"{int(dx.n.sum()):,} ingresos con diagnostico")

    diario = dx.groupby(["dia", "capitulo"], as_index=False)["n"].sum()
    diario.to_parquet(destino / "perfil_dx_diario.parquet", index=False)          # NO se versiona

    dx["semana"] = dx["dia"] - pd.to_timedelta((dx["dia"].dt.dayofweek + 1) % 7, unit="D")   # domingo
    sem = dx.groupby(["semana", "capitulo"], as_index=False)["n"].sum()
    _suprimir(sem).to_parquet(destino / "perfil_dx_semanal.parquet", index=False)
    dx["anio"] = dx["dia"].dt.year
    edad = dx.groupby(["anio", "capitulo", "banda"], as_index=False)["n"].sum()
    _suprimir(edad).to_parquet(destino / "perfil_dx_edad_anual.parquet", index=False)

    dx["mes"] = dx["dia"].values.astype("datetime64[M]")
    men = dx.groupby(["mes", "cod3"], as_index=False)["n"].sum()
    chicos = men["n"] < MINIMO
    otros = men[chicos].groupby("mes", as_index=False)["n"].sum().assign(cod3="(otros, casillas < 5)")
    men = pd.concat([men[~chicos], otros], ignore_index=True)
    # Nombre de cada codigo de 3: la subcategoria MAS USADA en el hospital dentro de el (el
    # catalogo de la base no trae nombre de categoria). Es un catalogo publico, no un dato.
    nombres = pd.read_sql("""
        SELECT LEFT(g.DIACODIGO, 3) AS cod3, g.DIACODIGO AS cod, MIN(g.DIANOMBRE) AS nombre, COUNT(*) AS usos
        FROM dbo.CONTROL_DIAGNOSTICO c JOIN dbo.DIM_DIAGNOSTICO g ON c.GENDIAGNO = g.OID
        WHERE c.HCPDIAPRIN = 1 GROUP BY LEFT(g.DIACODIGO, 3), g.DIACODIGO""", eng)
    top = nombres.sort_values("usos", ascending=False).drop_duplicates("cod3")
    men = men.merge(top[["cod3", "cod", "nombre"]].rename(columns={"cod": "subcodigo_mas_usado"}), on="cod3", how="left")
    men["capitulo"] = men["cod3"].map(capitulo)
    men.to_parquet(destino / "perfil_dx_codigo_mensual.parquet", index=False)

    print("  remisiones por mes x motivo x servicio...", end=" ", flush=True)
    chk = pd.read_sql("SELECT COUNT(DISTINCT MOTIVO) AS k, MAX(LEN(MOTIVO)) AS L FROM dbo.SEGUIMIENTO_REMISIONES_DW", eng).iloc[0]
    if chk.k > 10 or chk.L > 60:        # MOTIVO solo sale si es un catalogo cerrado y corto
        print(f"MOTIVO no es un catalogo ({chk.k} valores, largo {chk.L}): no se extrae")
        return
    r = pd.read_sql("""
        SELECT DATEFROMPARTS(YEAR(FECHAREMISION), MONTH(FECHAREMISION), 1) AS mes, MOTIVO AS motivo,
               ServicioSes AS servicio, COUNT(*) AS n
        FROM dbo.SEGUIMIENTO_REMISIONES_DW WHERE FECHAREMISION IS NOT NULL
        GROUP BY DATEFROMPARTS(YEAR(FECHAREMISION), MONTH(FECHAREMISION), 1), MOTIVO, ServicioSes""", eng)
    _suprimir(r.groupby(["mes", "motivo"], as_index=False)["n"].sum()).to_parquet(
        destino / "perfil_remisiones_motivo.parquet", index=False)
    r["anio"] = pd.to_datetime(r["mes"]).dt.year
    _suprimir(r.groupby(["anio", "servicio"], as_index=False)["n"].sum()).to_parquet(
        destino / "perfil_remisiones_servicio.parquet", index=False)
    print(f"{int(r.n.sum()):,} remisiones")


SQL_CONTEO_HORARIO = """
    SELECT CAST(t.HCTFECTRI AS DATE) AS dia,
           DATEPART(HOUR, t.HCTFECTRI) AS hora,
           COUNT(*) AS triages
    FROM dbo.DIM_TRIAGE t
    WHERE t.HCTFECTRI IS NOT NULL
    GROUP BY CAST(t.HCTFECTRI AS DATE), DATEPART(HOUR, t.HCTFECTRI)"""


def conteo_horario(eng):
    """
    Triages por dia x hora, leidos al momento y sin escribir nada. Es la forma de
    salidas/triage_horario.parquet; sumado por dia da triage_diario.parquet.

    Lo usa el cuaderno 24 para mostrar la serie al dia y verificar una semana
    predicha. Solo sale la fecha, la hora y el conteo: ni OID ni texto.
    """
    t = pd.read_sql(SQL_CONTEO_HORARIO, eng)
    t["dia"] = pd.to_datetime(t["dia"])
    return t.sort_values(["dia", "hora"]).reset_index(drop=True)


def main(argv=None):
    from pathlib import Path

    parser = argparse.ArgumentParser(prog="python -m extraccion")
    parser.add_argument("--esquema", action="store_true")
    parser.add_argument("--cobertura", action="store_true")
    parser.add_argument("--series", action="store_true")
    parser.add_argument("--entidad", action="store_true",
                        help="solo la serie por entidad administradora (EPS, SOAT, ARL)")
    parser.add_argument("--perfil", action="store_true",
                        help="perfil del hospital: ingreso, area, causa, CIE-10, remisiones (solo agregados)")
    args = parser.parse_args(argv)

    if not (args.esquema or args.cobertura or args.series or args.entidad or args.perfil):
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
    if args.perfil:
        perfil(eng, salidas)
    return 0


if __name__ == "__main__":
    sys.exit(main())
