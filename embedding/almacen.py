"""
El almacen: la tabla `embedding` de la base compartida.

EL ESQUEMA ENTERO SON DOS TABLAS
    nota_triage   OID (PK)         la escribe NLP/, aqui solo se lee
                  fecha_triage     HCTFECTRI, la fecha real del triage
                  frase_original   HCTMOTCON sin tocar
                  frase_procesada  lo que devolvio el modelo generador

    embedding     OID (PK, FK)     -> nota_triage.OID
                  huella           sha256[:16] de la frase que se vectorizo
                  modelo           con que modelo se calculo este vector
                  tokens           cuantos tokens gasto la frase
                  vector           FLOAT[768], normalizado a norma 1

EL OID ES UNA COLUMNA, NO ENTRA AL VECTOR
    Esa es la pregunta que este paquete existe para contestar bien. El texto
    que se le da al modelo es la frase y nada mas: meter el OID dentro seria
    ruido sin significado en un espacio semantico. Pero la FILA si lleva el
    OID, asi que cada vector se identifica con una columna y la fecha se
    consigue con un JOIN:

        SELECT n.fecha_triage, e.vector
        FROM embedding e JOIN nota_triage n USING (OID)

QUE HACE 'huella' Y POR QUE NO SOBRA
    Es la unica columna que no se explica sola, asi que aqui va entera.

    Guarda el sha256 de la frase CON LA QUE SE CALCULO ese vector. Sirve para
    dos cosas, y las dos son cosas que sin ella no se pueden hacer:

    1. DETECTAR UN VECTOR CADUCO. Si NLP/ reprocesa una nota y el modelo
       devuelve otra frase, el vector guardado deja de corresponderle. Sin la
       huella eso es invisible: la fila tiene su OID, tiene su vector, y nada
       dice que el vector es de un texto que ya no existe. Con ella es una
       comparacion:

           WHERE e.huella <> sha256(n.frase_procesada)

    2. NO VECTORIZAR DOS VECES LO MISMO. El mismo motivo de consulta se repite
       muchisimo: sobre 596 notas hay 479 frases distintas. Antes de llamar al
       modelo se agrupan las notas pendientes por huella, se codifica cada
       texto distinto UNA vez y el mismo vector se escribe en todas las filas
       que lo comparten. El vector se guarda repetido -- 768 float32 son 3 KB
       por fila, y el corpus completo ocupa unos 290 MB -- pero se CALCULA una
       sola vez, que es lo que cuesta.

    Antes esto eran dos tablas (`frases` + `triage_frase`) para no repetir el
    vector. Se quitaron: ahorraban disco, que sobra, a cambio de una tabla y un
    JOIN de mas en todas las consultas.

POR QUE LA POSICION YA NO ES LA LLAVE DE NADA
    El diseno de antes del 2026-09-21 guardaba la matriz en un binario plano
    sin cabecera y la correspondencia en archivos aparte. La llave era la
    POSICION: el vector n empezaba en el byte n * dimension * 4. Nada dentro
    del binario decia a que texto pertenecia cada vector, asi que una
    desincronizacion era INDETECTABLE: se leian 4.096 bytes perfectamente
    validos que eran de otra frase.

    cargar() sigue devolviendo una columna 'fila' porque el clustering trabaja
    con matrices, pero se calcula en cada lectura y no se guarda nunca. Una
    posicion es una comodidad valida en memoria; como llave de persistencia es
    lo que causo el problema.
"""

import hashlib

import numpy as np

from embedding import modelo, rutas


def huella(texto):
    """
    La llave de contenido de una frase: sha256 de su texto, 16 hex.

    Se trunca porque 64 bits sobran: con 40.000 frases la probabilidad de
    colision es del orden de 1e-11.

    Es sha256 y no el hash() de Python, que va salteado por proceso y daria una
    llave distinta en cada ejecucion.
    """
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()[:16]


# ==========================================================
# ABRIR
# ==========================================================

def abrir(solo_lectura=False):
    """Devuelve una conexion con el esquema ya creado."""
    import duckdb

    if solo_lectura and not rutas.BASE_DATOS.exists():
        raise SystemExit(
            f"No existe {rutas.BASE_DATOS}.\n"
            f"La crea 'python -m NLP.procesar'; los vectores los anade "
            f"'python -m embedding.vectorizar'.")

    try:
        con = duckdb.connect(str(rutas.BASE_DATOS), read_only=solo_lectura)
    except Exception as error:
        # El caso tipico: la extension de DuckDB en VS Code tiene el archivo.
        # Sin este mensaje el error de DuckDB queda enterrado en una traza y
        # parece un fallo del pipeline, que es lo que paso el 2026-09-21.
        if "already open in" in str(error):
            culpable = next((linea.strip() for linea in str(error).splitlines()
                             if ".exe" in linea), "otra aplicacion")
            raise SystemExit(
                f"{rutas.BASE_DATOS.name} la tiene tomada:\n"
                f"    {culpable}\n\n"
                f"DuckDB admite un solo escritor. Cierra esa conexion y vuelve "
                f"a intentar.\n"
                f"En VS Code: Ctrl+Shift+P -> 'DuckDB: Detach Database'.")
        raise
    if not solo_lectura:
        _crear_esquema(con)
    return con


def _crear_esquema(con):
    # nota_triage la crea NLP/, pero embedding/ no importa NLP/ y la necesita
    # para su clave foranea. CREATE IF NOT EXISTS es idempotente y deja la
    # misma definicion; si NLP/ ya corrio, esto no hace nada.
    con.execute("""
        CREATE TABLE IF NOT EXISTS nota_triage (
            OID              BIGINT PRIMARY KEY,
            fecha_triage     TIMESTAMP,
            frase_original   VARCHAR,
            frase_procesada  VARCHAR
        );
    """)
    con.execute(f"""
        CREATE TABLE IF NOT EXISTS embedding (
            OID     BIGINT PRIMARY KEY REFERENCES nota_triage(OID),
            huella  VARCHAR NOT NULL,
            modelo  VARCHAR NOT NULL,
            tokens  INTEGER,
            vector  FLOAT[{modelo.DIMENSION}] NOT NULL
        );
    """)


# ==========================================================
# IDENTIDAD DEL MODELO
# ==========================================================

def comprobar_identidad(con):
    """
    Se niega a continuar si la tabla ya tiene vectores de otro modelo.

    Mezclar vectores de dos modelos produce una matriz mitad y mitad: no da
    ningun error, y el unico sintoma es que el clustering sale mal sin que nada
    diga por que. Es el fallo que mas cuesta encontrar, asi que se bloquea.

    La comprobacion no necesita una tabla de metadatos aparte: la identidad
    esta en la columna `modelo` de cada fila, que es donde pertenece.
    """
    guardados = [fila[0] for fila in con.execute(
        "SELECT DISTINCT modelo FROM embedding").fetchall()]
    ajenos = [m for m in guardados if m != modelo.MODELO]
    if ajenos:
        raise SystemExit(
            f"La tabla `embedding` ya tiene vectores de otro modelo:\n"
            f"    guardado(s): {ajenos}\n"
            f"    actual:      {modelo.MODELO}\n\n"
            f"Mezclarlos daria vectores de dos espacios distintos en la misma "
            f"tabla.\nPara empezar de cero: "
            f"python -m embedding.vectorizar --rehacer")


# ==========================================================
# ESCRIBIR
# ==========================================================

def pendientes(con, utiles):
    """
    Las notas que hay que vectorizar: las que no tienen vector, y las que lo
    tienen calculado sobre una frase que ya no es la suya.

    `utiles` trae OID, texto y huella. Se compara la huella de ahora contra la
    guardada; ese es el trabajo de esa columna.
    """
    import pyarrow as pa

    tabla = pa.table({"OID": pa.array([int(o) for o in utiles["OID"]],
                                      type=pa.int64()),
                      "huella": pa.array(utiles["huella"].tolist(),
                                         type=pa.string())})
    con.execute("CREATE OR REPLACE TEMP TABLE quiero AS SELECT * FROM tabla")
    filas = con.execute("""
        SELECT q.OID FROM quiero q
        LEFT JOIN embedding e USING (OID)
        WHERE e.OID IS NULL OR e.huella <> q.huella
    """).fetchall()
    faltan = {fila[0] for fila in filas}
    return utiles[utiles["OID"].isin(faltan)]


def guardar(con, oids, huellas, matriz, tokens=None):
    """
    Mete o actualiza vectores en una sola transaccion.

    O entran todos o no entra ninguno: no existe el estado a medias que el
    diseno anterior tenia que prevenir con un orden de escritura y fsync.
    """
    import pyarrow as pa

    if len(oids) == 0:
        return 0
    if not (len(oids) == len(huellas) == len(matriz)):
        raise ValueError("oids, huellas y matriz tienen que ir alineados")

    matriz = np.ascontiguousarray(matriz, dtype=np.float32)
    vectores = pa.FixedSizeListArray.from_arrays(
        pa.array(matriz.reshape(-1), type=pa.float32()), modelo.DIMENSION)
    nuevas = pa.table({
        "OID": pa.array([int(o) for o in oids], type=pa.int64()),
        "huella": pa.array(list(huellas), type=pa.string()),
        "modelo": pa.array([modelo.MODELO] * len(oids), type=pa.string()),
        "tokens": pa.array(list(tokens) if tokens is not None
                           else [None] * len(oids), type=pa.int32()),
        "vector": vectores,
    })

    con.execute("BEGIN TRANSACTION")
    try:
        # DO UPDATE y no DO NOTHING: si la nota cambio de frase, el vector
        # viejo tiene que irse. Con DO NOTHING se quedaria pegado a un texto
        # que ya no existe, en silencio.
        con.execute("""
            INSERT INTO embedding (OID, huella, modelo, tokens, vector)
            SELECT OID, huella, modelo, tokens, vector FROM nuevas
            ON CONFLICT (OID) DO UPDATE SET
                huella = excluded.huella,
                modelo = excluded.modelo,
                tokens = excluded.tokens,
                vector = excluded.vector
        """)
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    return len(oids)


def limpiar_huerfanos(con):
    """
    Borra vectores de notas que ya no estan en nota_triage.

    No deberia pasar -- la clave foranea lo impide al borrar -- pero si alguna
    vez se limpia la tabla de notas por otra via, esto lo deja consistente.
    """
    return con.execute("""
        DELETE FROM embedding
        WHERE OID NOT IN (SELECT OID FROM nota_triage)
    """).fetchall()


# ==========================================================
# LEER
# ==========================================================

def cargar(minimo_notas=1, con=None):
    """
    Devuelve la terna (textos, vectores, indice) que consume el clustering.

    textos    un renglon por FRASE DISTINTA: fila, huella, texto, n_notas.
    vectores  matriz float32 alineada con textos, ya normalizada.
    indice    OID -> huella -> fila, para devolverle su grupo a cada nota.

    SE AGRUPA POR FRASE DISTINTA AUNQUE LA TABLA GUARDE UNA FILA POR NOTA
        HDBSCAN agrupa por densidad. Dos notas con la misma frase producen dos
        puntos en la MISMA coordenada, a distancia cero: un pico de densidad
        infinita que no corresponde a ninguna estructura del corpus sino a que
        esa frase se repite. Las frases muy frecuentes se volverian nucleos
        artificiales y las raras caerian como ruido a su alrededor.

        Por eso se agrupa por huella aqui, en la LECTURA. El vector es
        identico en todas las filas que comparten huella, asi que any_value()
        es exacto y no una aproximacion.

    'fila' se genera aqui y no se guarda en ninguna parte: es el renglon de la
    matriz que se acaba de construir, valido solo para esta lectura.
    """
    import pyarrow as pa

    propia = con is None
    if propia:
        con = abrir(solo_lectura=True)
    try:
        arrow = con.execute("""
            SELECT e.huella,
                   any_value(n.frase_procesada) AS texto,
                   count(*)                     AS n_notas,
                   any_value(e.vector)          AS vector
            FROM embedding e
            JOIN nota_triage n USING (OID)
            GROUP BY e.huella
            HAVING count(*) >= ?
            ORDER BY e.huella
        """, [minimo_notas]).arrow()
        if isinstance(arrow, pa.RecordBatchReader):
            arrow = arrow.read_all()

        if arrow.num_rows == 0:
            raise SystemExit(
                "La tabla `embedding` esta vacia.\n"
                "Corre 'python -m embedding.vectorizar'.")

        textos = arrow.select(["huella", "texto", "n_notas"]).to_pandas()
        textos.insert(0, "fila", np.arange(len(textos), dtype=np.int64))

        plano = arrow.column("vector").combine_chunks().flatten().to_numpy(
            zero_copy_only=False)
        vectores = np.ascontiguousarray(
            plano.reshape(len(textos), -1), dtype=np.float32)

        indice = con.execute("SELECT OID, huella FROM embedding").df()
        indice = indice.merge(textos[["huella", "fila"]], on="huella",
                              how="inner")
        return textos, vectores, indice
    finally:
        if propia:
            con.close()


def estadisticas(con=None):
    propia = con is None
    if propia:
        con = abrir(solo_lectura=True)
    try:
        notas, frases, truncados, tokens_max, modelos = con.execute("""
            SELECT count(*), count(DISTINCT huella),
                   count(*) FILTER (WHERE tokens > ?), max(tokens),
                   list(DISTINCT modelo)
            FROM embedding
        """, [modelo.LONGITUD_MAXIMA]).fetchone()
        sin_vector, sin_fecha = con.execute("""
            SELECT (SELECT count(*) FROM nota_triage n
                    LEFT JOIN embedding e USING (OID) WHERE e.OID IS NULL),
                   (SELECT count(*) FROM nota_triage WHERE fecha_triage IS NULL)
        """).fetchone()
        return {
            "notas": notas, "frases": frases,
            "truncados": truncados, "tokens_max": tokens_max,
            "modelos": modelos, "notas_sin_vector": sin_vector,
            "notas_sin_fecha": sin_fecha,
            "megabytes": round(rutas.BASE_DATOS.stat().st_size / 1e6, 1)
            if rutas.BASE_DATOS.exists() else 0.0,
        }
    finally:
        if propia:
            con.close()


def vaciar():
    """
    Deja `embedding` vacia para que --rehacer empiece de cero.

    NO borra el archivo. La base la comparte con NLP/, que guarda ahi
    `nota_triage`: el resultado de horas de generacion contra la base clinica,
    que no se puede rehacer sin volver a consultarla. Borrar el archivo entero
    por comodidad tiraria eso.
    """
    if not rutas.BASE_DATOS.exists():
        return {"vectores": 0}
    con = abrir()
    try:
        vectores = con.execute("SELECT count(*) FROM embedding").fetchone()[0]
        con.execute("DELETE FROM embedding")
        return {"vectores": vectores}
    finally:
        con.close()
