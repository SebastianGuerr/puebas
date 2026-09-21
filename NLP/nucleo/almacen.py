"""
El deposito: la tabla `nota_triage` de la base del proyecto.

QUE GUARDA Y POR QUE ESAS CUATRO COLUMNAS Y NO MAS
    nota_triage  OID (PK)         la nota en DIM_TRIAGE
                 fecha_triage     HCTFECTRI, la fecha REAL del triage
                 frase_original   HCTMOTCON tal cual esta en la base, sin tocar
                 frase_procesada  lo que devolvio el modelo

    Son los tres datos que se bajan de la base clinica (OID, fecha, frase) mas
    el resultado de procesarlos. No hay nada mas porque no hace falta nada mas:
    con eso se puede contar triages por dia, cruzarlos con el clima y auditar
    cada frase procesada contra la original.

    LO QUE SE QUITO EL 2026-09-21, EN LA SEGUNDA PASADA DEL DISENO
        `modelo` y `prompt`: decian con que version se genero cada fila. La
        idea era poder rehacer solo las notas viejas tras un cambio de prompt.
        Se quito porque en la practica un cambio de prompt obliga a rehacerlo
        todo, y dos columnas repetidas 94.000 veces para un caso que no se da
        son ruido. Si alguna vez hace falta, se anaden.

        `creado`: la marca de cuando se escribio la fila. Se quito porque se
        confunde con fecha_triage, que es la que importa, y tener dos fechas
        donde solo una significa algo es una trampa esperando a que alguien
        agrupe por la equivocada.

POR QUE ESTA TABLA Y NO SE LEE DIM_TRIAGE DIRECTAMENTE
    Porque a DIM_TRIAGE no se puede acceder desde el analisis: es informacion
    clinica sensible y la regla 1 de CLAUDE.md lo prohibe. Esta tabla es la
    copia MINIMA y no identificable que se necesita aguas abajo: tres campos de
    los trece que tiene el original, sin nombre, documento, edad ni medico.

DONDE VIVE Y POR QUE AHI
    salidas/triage.duckdb, en la RAIZ del repositorio y no dentro de NLP/.
    La base la comparten dos paquetes: NLP/ escribe `nota_triage` y embedding/
    escribe `embedding`. Meterla dentro de cualquiera de los dos haria falsa la
    propiedad del otro. Sigue siendo una salida, la regenera un script y esta
    ignorada por git.

UN SOLO ESCRITOR
    DuckDB no admite dos procesos escribiendo a la vez. Por eso el escritor de
    aqui abre la base, confirma un bloque y la CIERRA, en vez de quedarsela
    toda la corrida: entre bloque y bloque queda libre para que
    'python -m embedding.centinela' entre a vectorizar lo que ya salio.
"""

import time
from pathlib import Path

from NLP import rutas

REINTENTOS = 8
ESPERA = 2.0


# ==========================================================
# ABRIR
# ==========================================================

def abrir(solo_lectura=False, reintentos=REINTENTOS, diagnosticar=True):
    """
    Conexion con el esquema ya creado, reintentando si otro proceso escribe.

    El bloqueo es temporal por definicion -- el otro proceso esta confirmando
    un bloque -- asi que se espera en vez de abortar una corrida de horas.

    diagnosticar=False para quien sabe convivir con el bloqueo y prefiere el
    error crudo: deja pasar la excepcion original en vez de convertirla en un
    SystemExit con instrucciones. Lo usa NLP/monitor.py, que espera chocar de
    vez en cuando con el escritor y solo quiere saltarse esa vuelta. Sin esto
    el monitor se moria en el primer choque, porque SystemExit no es Exception
    y se le escapaba al except.
    """
    import duckdb

    rutas.BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)
    ultimo = None
    for intento in range(reintentos):
        try:
            con = duckdb.connect(str(rutas.BASE_DATOS), read_only=solo_lectura)
            if not solo_lectura:
                crear_esquema(con)
            return con
        except Exception as error:
            ultimo = error
            # Si quien la tiene es una APLICACION y no otro paso del pipeline
            # -- la extension de DuckDB en VS Code es el caso tipico -- no va a
            # soltarla en 16 segundos. Reintentar solo retrasa el diagnostico,
            # asi que se corta ya y se dice que hacer.
            if diagnosticar and "already open in" in str(error):
                culpable = next(
                    (linea.strip() for linea in str(error).splitlines()
                     if ".exe" in linea), "otra aplicacion")
                raise SystemExit(
                    f"{rutas.BASE_DATOS.name} la tiene tomada:\n"
                    f"    {culpable}\n\n"
                    f"DuckDB admite un solo escritor. Cierra esa conexion y "
                    f"vuelve a intentar.\n"
                    f"En VS Code: Ctrl+Shift+P -> 'DuckDB: Detach Database'.\n"
                    f"Para seguir la corrida sin desconectar nada: "
                    f"python -m NLP.monitor")
            if intento < reintentos - 1:
                time.sleep(ESPERA)
    if not diagnosticar:
        raise ultimo
    raise SystemExit(
        f"No se pudo abrir {rutas.BASE_DATOS.name} en {reintentos} intentos.\n"
        f"DuckDB admite un solo escritor: comprueba que no haya otro proceso "
        f"(embedding.centinela) con la base tomada.\n"
        f"Ultimo error: {ultimo}")


def crear_esquema(con):
    """
    Crea `nota_triage` si no esta. Es idempotente y la llama tambien
    embedding/, que necesita que exista para su clave foranea.
    """
    con.execute("""
        CREATE TABLE IF NOT EXISTS nota_triage (
            OID              BIGINT PRIMARY KEY,
            fecha_triage     TIMESTAMP,
            frase_original   VARCHAR,
            frase_procesada  VARCHAR
        );
    """)


# ==========================================================
# REANUDACION
# ==========================================================

def oids_hechos():
    """
    Los OID que ya tienen frase procesada, para que relanzar continue en vez de
    repetir. Es una consulta sobre la clave primaria, no releer un archivo.
    """
    if not rutas.BASE_DATOS.exists():
        return set()
    con = abrir(solo_lectura=True)
    try:
        return {fila[0] for fila in con.execute(
            "SELECT OID FROM nota_triage WHERE frase_procesada IS NOT NULL"
        ).fetchall()}
    except Exception:
        return set()          # la base existe pero aun no tiene la tabla
    finally:
        con.close()


def contar():
    if not rutas.BASE_DATOS.exists():
        return 0
    con = abrir(solo_lectura=True)
    try:
        return con.execute("SELECT count(*) FROM nota_triage").fetchone()[0]
    except Exception:
        return 0
    finally:
        con.close()


def sin_fecha():
    """Cuantas notas guardadas no tienen todavia su fecha de triage."""
    if not rutas.BASE_DATOS.exists():
        return 0
    con = abrir(solo_lectura=True)
    try:
        return con.execute(
            "SELECT count(*) FROM nota_triage WHERE fecha_triage IS NULL"
        ).fetchone()[0]
    except Exception:
        return 0
    finally:
        con.close()


# ==========================================================
# ESCRITURA INCREMENTAL
# ==========================================================

class Escritor:
    """
    Va llenando `nota_triage` mientras la corrida avanza, por bloques.

    Se acumula en memoria y se baja cada `bloque` notas. El bloque es pequeno a
    proposito: una corrida de horas que se cuelga no puede perder mas que eso,
    y cada confirmacion libera la base para el centinela.

    Se usa como contexto para que una interrupcion baje siempre lo pendiente:

        with Escritor() as escritor:
            for nota in notas:
                escritor.agregar(fila)
    """

    CAMPOS = ("OID", "fecha_triage", "frase_original", "frase_procesada")

    def __init__(self, bloque=10, refrescar=True):
        self.bloque = bloque
        self.pendientes = []
        self.escritas = 0
        # refrescar=False lo usan las pruebas y la importacion del CSV: no
        # tiene sentido mantener una vista de una base temporal.
        self.refrescar = refrescar

    def agregar(self, fila):
        self.pendientes.append(fila)
        if len(self.pendientes) >= self.bloque:
            self.bajar()

    def bajar(self):
        """Confirma lo pendiente y suelta la base."""
        if not self.pendientes:
            return 0
        con = abrir()
        try:
            con.execute("BEGIN TRANSACTION")
            # ON CONFLICT DO UPDATE y no DO NOTHING: si una nota se reprocesa
            # gana la version nueva. Con DO NOTHING la fila vieja se quedaria y
            # la corrida no serviria de nada sin que nada avisara.
            con.executemany("""
                INSERT INTO nota_triage
                    (OID, fecha_triage, frase_original, frase_procesada)
                VALUES (?, ?, ?, ?)
                ON CONFLICT (OID) DO UPDATE SET
                    fecha_triage    = coalesce(excluded.fecha_triage,
                                               nota_triage.fecha_triage),
                    frase_original  = excluded.frase_original,
                    frase_procesada = excluded.frase_procesada
            """, [(int(f["OID"]), f.get("fecha_triage"),
                   _texto(f.get("frase_original")),
                   _texto(f.get("frase_procesada")))
                  for f in self.pendientes])
            con.execute("COMMIT")
            # CHECKPOINT antes de cerrar: dobla el .wal dentro del archivo.
            # Sin esto la copia de refrescar_vista() podria salir sin las
            # ultimas filas, que es justo lo que se quiere ver en vivo.
            con.execute("CHECKPOINT")
        except Exception:
            con.execute("ROLLBACK")
            raise
        finally:
            con.close()
        bajadas = len(self.pendientes)
        self.escritas += bajadas
        self.pendientes = []
        # Con la conexion ya cerrada el archivo esta libre y se puede copiar.
        if self.refrescar:
            refrescar_vista()
        return bajadas

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.bajar()
        return False


def _texto(valor):
    return None if valor is None else str(valor)


# ==========================================================
# LA COPIA PARA MIRAR
# ==========================================================

_ULTIMO_REFRESCO = 0.0
SEGUNDOS_ENTRE_REFRESCOS = 20


def refrescar_vista(forzar=False, cada=SEGUNDOS_ENTRE_REFRESCOS):
    """
    Copia la base a rutas.BASE_VISTA para poder mirarla sin bloquear nada.

    EL PROBLEMA QUE RESUELVE
        Un escritor de DuckDB bloquea a todo el mundo, lectores incluidos
        (medido el 2026-09-21). Asi que con la extension de VS Code adjunta a
        la base de verdad, esto no puede escribir. Y desconectarla a mano cada
        vez no es forma de trabajar.

        Con el visor adjunto a la COPIA, la corrida ya no se cae. Ese es el
        objetivo y se cumple entero.

        Lo que no se consigue es que la copia avance mientras el visor la
        tiene: en Windows no se puede sustituir un archivo abierto por otro
        proceso (medido el 2026-09-21: PermissionError tanto con copyfile como
        con replace). La copia se congela en la foto que habia al conectarse y
        avanza cuando el visor se desconecta y vuelve. Para ver datos que
        cambian de verdad esta NLP/monitor.py, que abre y cierra cada vuelta.

    POR QUE SE LLAMA DESPUES DE CERRAR Y NO ANTES
        En Windows el bloqueo de DuckDB es sobre el archivo: con la conexion
        abierta ni siquiera se puede copiar. Por eso esto va detras del
        con.close() del escritor.

    Se limita a una copia cada `cada` segundos: en el corpus completo el
    archivo pasa de 300 MB y copiarlo tras cada bloque de diez notas seria mas
    caro que generarlas.
    """
    import shutil
    global _ULTIMO_REFRESCO

    ahora = time.time()
    if not forzar and ahora - _ULTIMO_REFRESCO < cada:
        return False
    if not rutas.BASE_DATOS.exists():
        return False

    # Se escribe a un temporal y se renombra: si el visor esta leyendo justo
    # en ese instante, ve la copia vieja entera o la nueva entera, nunca una a
    # medias. Con el visor conectado el renombrado falla, y eso es normal y
    # esperado -- devuelve False y la corrida sigue. Abortar horas de trabajo
    # porque no se pudo actualizar una copia de conveniencia seria absurdo.
    temporal = rutas.BASE_VISTA.with_suffix(".tmp")
    try:
        shutil.copy2(rutas.BASE_DATOS, temporal)
        temporal.replace(rutas.BASE_VISTA)
        _ULTIMO_REFRESCO = ahora
        return True
    except OSError:
        temporal.unlink(missing_ok=True)
        return False


# ==========================================================
# FECHAS
# ==========================================================

def guardar_fechas(pares):
    """
    Rellena fecha_triage de notas que ya estan. No toca las frases.

    Existe para las notas importadas del CSV viejo, que no traia la fecha. La
    fecha no necesita al modelo: es una consulta de dos columnas a la base
    clinica, y rehacer esas notas con el LLM solo para conseguirla seria tirar
    horas. Lo alimenta 'python -m NLP.procesar --fechas'.
    """
    if not pares:
        return 0
    con = abrir()
    try:
        con.execute("BEGIN TRANSACTION")
        con.executemany(
            "UPDATE nota_triage SET fecha_triage = ? WHERE OID = ?",
            [(fecha, int(oid)) for oid, fecha in pares])
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
    return len(pares)


# ==========================================================
# MIGRACION Y LIMPIEZA
# ==========================================================

def importar_csv(ruta_csv):
    """
    Mete un triage_limpio.csv anterior en la tabla. Se puede repetir.

    Existe para la migracion del 2026-09-21 y para recuperar un CSV viejo sin
    volver a consultar la base clinica, que es lo caro. El CSV no traia la
    fecha, asi que esas filas quedan con fecha_triage en NULL y se completan
    despues con --fechas.
    """
    import pandas as pd

    ruta_csv = Path(ruta_csv)
    if not ruta_csv.exists():
        raise SystemExit(f"No existe {ruta_csv}")

    df = pd.read_csv(ruta_csv, encoding="utf-8-sig")
    faltan = {"OID", "texto_original", "texto_optimizado"} - set(df.columns)
    if faltan:
        raise SystemExit(f"Al CSV le faltan columnas: {sorted(faltan)}")

    antes = len(df)
    df = df.dropna(subset=["OID"]).drop_duplicates(subset="OID", keep="last")
    repetidos = antes - len(df)

    escritor = Escritor(bloque=max(len(df), 1))
    for fila in df.to_dict("records"):
        escritor.agregar({"OID": fila["OID"],
                          "fecha_triage": None,
                          "frase_original": fila.get("texto_original") or "",
                          "frase_procesada": fila.get("texto_optimizado") or ""})
    escritor.bajar()
    return {"leidas": antes, "repetidos": repetidos,
            "escritas": escritor.escritas, "sin_fecha": sin_fecha()}


def vaciar():
    """
    Deja `nota_triage` vacia para que --rehacer empiece de verdad desde cero.

    TOCA LA TABLA DE embedding/, Y ESO ES DELIBERADO
        `embedding` tiene una clave foranea contra `nota_triage`, asi que no se
        puede vaciar esta sin vaciar aquella: el motor lo impide, que es
        exactamente para lo que esta la restriccion.

        Los vectores se recalculan con 'python -m embedding.vectorizar' en
        minutos; estas notas son horas contra la base clinica. Por eso este
        comando es el caro y hay que pensarlo antes de correrlo.
    """
    con = abrir()
    try:
        vectores = 0
        existe = con.execute("""
            SELECT count(*) FROM information_schema.tables
            WHERE table_name = 'embedding'
        """).fetchone()[0]
        if existe:
            vectores = con.execute(
                "SELECT count(*) FROM embedding").fetchone()[0]
            con.execute("DELETE FROM embedding")
        notas = con.execute("SELECT count(*) FROM nota_triage").fetchone()[0]
        con.execute("DELETE FROM nota_triage")
        return {"notas": notas, "vectores": vectores}
    finally:
        con.close()
