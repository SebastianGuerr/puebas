"""
La entrada: leer triage_limpio.csv y dejarlo listo para vectorizar.

QUE COLUMNA SE USA Y POR QUE NO HAY ALTERNATIVA
    texto_embedding, la que deja la fase 5 de NLP/. Y si no esta, este modulo
    falla en vez de buscarse otra.

    Esa terquedad es deliberada. La prueba original en el notebook vectorizaba
    texto_normalizado, que es la nota entera: antecedentes, tramite
    administrativo y motivo de consulta todo junto. El embedding recogia ese
    ruido y los clusters salian agrupados por la burocracia compartida y no por
    lo que le pasaba al paciente. texto_embedding existe justamente para
    arreglar eso.

    Una columna de reserva volveria a ese comportamiento en silencio el dia que
    el CSV llegue sin la columna buena, y el sintoma seria un clustering
    mediocre sin ninguna senal de por que. Es preferible el error.

LOS OID REPETIDOS
    El CSV va a crecer apendando renglones, asi que un OID reprocesado puede
    aparecer dos veces. Gana el ultimo, que es la version mas reciente del
    texto, y se avisa cuantos habia.
"""

import pandas as pd

from embedding import almacen, rutas

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

COLUMNA_TEXTO = "texto_embedding"
COLUMNA_ID = "OID"


def leer(ruta_csv):
    """
    Carga el CSV y devuelve la terna (utiles, vacios, repetidos).

    utiles    DataFrame con OID, texto y huella, un renglon por nota
    vacios    DataFrame con los OID que llegaron sin texto
    repetidos cuantos OID venian mas de una vez
    """
    if not ruta_csv.exists():
        raise SystemExit(
            f"No existe {ruta_csv}\n"
            f"Corre antes 'python -m NLP.procesar', o pasa la ruta con --csv.")

    # on_bad_lines: este CSV se puede estar escribiendo AHORA MISMO.
    #
    # NLP/procesar.py lo va llenando bloque a bloque, y la idea es justamente
    # poder vectorizar lo que ya salio sin esperar a que termine. El precio es
    # que una lectura puede caer entre medias de una fila y encontrarse la
    # ultima cortada.
    #
    # No es un problema porque el almacen se reconstruye entero en cada corrida:
    # la fila que hoy se salta aparece completa en la siguiente pasada y se
    # vectoriza entonces. Lo que si seria un problema es que un renglon a medias
    # abortara la corrida entera, que es lo que hace pandas por defecto.
    filas_malas = []
    df = pd.read_csv(ruta_csv, on_bad_lines=lambda mala: filas_malas.append(mala),
                     engine="python")
    if filas_malas:
        print(f"  {len(filas_malas)} fila(s) incompletas al final del CSV: se "
              f"omiten, entran en la proxima corrida")

    for columna in (COLUMNA_ID, COLUMNA_TEXTO):
        if columna not in df.columns:
            raise SystemExit(
                f"El CSV no tiene la columna '{columna}'.\n"
                f"Columnas encontradas: {list(df.columns)}\n"
                f"La columna {COLUMNA_TEXTO} la agrega la fase 5 de NLP/: "
                f"revisa que REDUCIR siga en True en NLP/procesar.py.")

    repetidos = int(df[COLUMNA_ID].duplicated().sum())
    if repetidos:
        df = df.drop_duplicates(subset=COLUMNA_ID, keep="last")

    texto = df[COLUMNA_TEXTO].fillna("").astype(str).str.strip()
    hay_texto = texto.ne("")

    vacios = df.loc[~hay_texto, [COLUMNA_ID]].copy()

    utiles = pd.DataFrame({
        COLUMNA_ID: df.loc[hay_texto, COLUMNA_ID].to_numpy(),
        "texto": texto[hay_texto].to_numpy(),
    })
    utiles["huella"] = [almacen.huella(t) for t in utiles["texto"]]

    return utiles, vacios, repetidos


def pendientes(utiles, deposito):
    """
    Los textos distintos que todavia no estan en el almacen.

    Se recorre en el orden en que aparecen y no con un set, porque un set no
    tiene orden estable entre corridas y eso haria que dos corridas de los
    mismos datos escribieran las filas en distinto sitio de la matriz. Con esto
    la matriz crece siempre igual y una corrida es reproducible.
    """
    faltan, vistas = [], set()
    for texto, h in zip(utiles["texto"], utiles["huella"]):
        if h in deposito or h in vistas:
            continue
        vistas.add(h)
        faltan.append(texto)
    return faltan


def escribir_indice(utiles, deposito):
    """
    Reescribe indice.parquet: la tabla OID -> fila de la matriz, que es lo que
    consume la fase de clustering.

    Se rehace entero en cada corrida en vez de apendarse, porque calcularlo es
    solo mirar huellas en un diccionario y asi refleja siempre el CSV actual:
    si una nota cambio de texto, su OID apunta a la fila nueva sin que quede
    rastro de la vieja.
    """
    filas = [deposito.fila[h] for h in utiles["huella"]]
    indice = pd.DataFrame({
        COLUMNA_ID: utiles[COLUMNA_ID].to_numpy(),
        "huella": utiles["huella"].to_numpy(),
        "fila": filas,
    })
    indice.to_parquet(rutas.INDICE, index=False)
    return indice
