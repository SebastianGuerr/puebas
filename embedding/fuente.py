"""
La entrada: leer la tabla `nota_triage` y dejarla lista para vectorizar.

DE DONDE SALE
    De la tabla `nota_triage` de la base compartida, que llena NLP/procesar.py.
    Hasta el 2026-09-21 se leia de NLP/salidas/triage_limpio.csv; ese CSV ya no
    se escribe. Ver NLP/nucleo/almacen.py para el porque del cambio.

    Este modulo solo LEE esa tabla. Nunca la escribe: el unico que puede es
    NLP/procesar.py, que es el unico con acceso a la base clinica.

QUE COLUMNA SE USA Y POR QUE NO HAY ALTERNATIVA
    frase_procesada, la frase canonica que genera el modelo de NLP/. Y si no
    esta, este modulo falla en vez de buscarse otra.

    Esa terquedad es deliberada y tiene historia. La prueba original
    vectorizaba la nota entera -- antecedentes, tramite administrativo y motivo
    de consulta todo junto -- y los clusters salian agrupados por la burocracia
    compartida y no por lo que le pasaba al paciente. Medido el 2026-09-21
    sobre el vocabulario que dejo la columna anterior (texto_embedding): 98 de
    9.142 frases eran literalmente antecedentes ("ap: niega; aa: niega") y 803
    contenian "niega". El problema no era teorico, estaba ocurriendo.

    La alternativa obvia -- frase_original, que esta justo al lado -- es
    exactamente la nota entera. Caer en ella en silencio el dia que falte la
    columna buena daria un clustering mediocre sin ninguna senal de por que.
    Es preferible el error.

QUE LE PASA AL TEXTO AQUI
    Se recorta y se pasa a minusculas, nada mas. No se limpia, no se corrige
    ortografia y no se expanden siglas: eso ya paso en NLP/. Minusculas porque
    la huella se calcula sobre el texto final, y "Cefalea" y "cefalea" tienen
    que ser la misma frase y gastar un solo vector.

    La unica excepcion es el centinela SIN_MOTIVO, que se trata como nota
    vacia. Ver la constante mas abajo.

LOS OID REPETIDOS YA NO EXISTEN
    En el CSV un OID reprocesado aparecia dos veces y habia que quedarse con el
    ultimo. En la tabla el OID es clave primaria, asi que el problema esta
    resuelto aguas arriba: reprocesar una nota actualiza su fila.
"""

import pandas as pd

from embedding import almacen

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

COLUMNA_TEXTO = "frase_procesada"
COLUMNA_ID = "OID"

# El centinela que emite el modelo de NLP/ cuando la nota solo documenta un
# tramite y no hay cuadro clinico ninguno (regla 13 de NLP/prompt.py). NO es
# una frase que haya que vectorizar: seria un punto en el espacio semantico
# que no corresponde a ningun sintoma, y arrastraria a su cluster a todas las
# notas administrativas -- exactamente el fallo que este paquete existe para
# evitar. Cuenta como nota sin texto.
SIN_MOTIVO = "sin motivo clinico"


def leer(con=None):
    """
    Carga la tabla y devuelve (utiles, vacias).

    utiles  DataFrame con OID, texto y huella, un renglon por nota
    vacias  los OID que no tienen frase que vectorizar
    """
    propia = con is None
    con = con or almacen.abrir(solo_lectura=True)
    try:
        try:
            df = con.execute(
                f"SELECT {COLUMNA_ID}, {COLUMNA_TEXTO} FROM nota_triage").df()
        except Exception as error:
            raise SystemExit(
                f"No se pudo leer nota_triage.{COLUMNA_TEXTO}: {error}\n"
                f"'{COLUMNA_TEXTO}' es la frase canonica que produce el modelo "
                f"de NLP/. Corre antes 'python -m NLP.procesar'.")
    finally:
        if propia:
            con.close()

    if df.empty:
        return (pd.DataFrame(columns=["OID", "texto", "huella"]),
                pd.DataFrame(columns=["OID"]))

    texto = (df[COLUMNA_TEXTO].fillna("").astype(str)
             .str.strip().str.lower())
    vacio = (texto == "") | (texto == SIN_MOTIVO)

    vacias = df.loc[vacio, [COLUMNA_ID]].copy()
    utiles = pd.DataFrame({
        "OID": df.loc[~vacio, COLUMNA_ID].astype("int64").to_numpy(),
        "texto": texto[~vacio].to_numpy(),
    })
    utiles["huella"] = [almacen.huella(t) for t in utiles["texto"]]
    return utiles, vacias


def distintos(utiles):
    """
    Una fila por texto distinto. Es la unidad de trabajo del MODELO.

    Ojo con la diferencia: la tabla `embedding` guarda una fila por NOTA,
    pero al modelo se le pasa cada texto distinto una sola vez y el vector que
    devuelve se copia en todas las notas que comparten la frase. El vector se
    guarda repetido -- disco sobra -- y se CALCULA una vez, que es lo que
    cuesta. Sobre 596 notas son 479 llamadas en vez de 596.

    vectorizar.py imprime el ahorro real en cada corrida.
    """
    return utiles.drop_duplicates(subset="huella")[["huella", "texto"]]
