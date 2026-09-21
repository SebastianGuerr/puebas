"""
Convierte nota_triage.frase_procesada en vectores de SapBERT-es.

    python -m embedding.vectorizar
    python -m embedding.vectorizar --limite 500     # prueba corta
    python -m embedding.vectorizar --rehacer        # tira los vectores y empieza
    python -m embedding.vectorizar --estado         # que hay guardado, sin tocar

    LEE      nota_triage, que este paquete jamas modifica
    ESCRIBE  la tabla `embedding` de salidas/triage.duckdb

ESTE PAQUETE NO LIMPIA NADA
    Ni corrige ortografia, ni expande siglas, ni recorta la nota. Todo eso ya
    paso en NLP/ y llega hecho en frase_procesada. Aca solo se convierte texto
    en numeros.

SE CALCULA POR FRASE DISTINTA Y SE GUARDA POR NOTA
    Es la unica sutileza del modulo. El mismo motivo de consulta se repite
    muchisimo, asi que al modelo se le pasa cada texto distinto UNA vez y el
    vector que devuelve se copia en todas las notas que comparten la frase.

    El vector queda repetido en la tabla -- 3 KB por fila, unos 290 MB para el
    corpus completo -- y a cambio la tabla tiene el OID como columna, el JOIN
    con la fecha es directo y no hace falta una tabla de enlace. Se paga disco,
    que sobra, para no pagar computo ni complejidad.

CORRER ESTO DOS VECES SEGUIDAS NO CUESTA NADA
    La segunda corrida encuentra todo al dia, no carga siquiera el modelo y
    sale. Cuando nota_triage crezca, se paga unicamente por lo nuevo.

QUE CUENTA COMO 'PENDIENTE'
    Una nota sin vector, y tambien una nota cuyo vector se calculo sobre otra
    frase. Lo segundo pasa cuando NLP/ reprocesa una nota y el modelo devuelve
    algo distinto; se detecta comparando la huella guardada con la de ahora.
    Sin esa comparacion el vector viejo seguiria pegado a la nota en silencio.

SI SE CORTA A LA MITAD
    Cada bloque entra en su propia transaccion. Un corte deja la tabla en el
    ultimo bloque completo, nunca a medias, y la corrida siguiente retoma por
    lo que falte. No hay que limpiar nada a mano.
"""

import argparse
import time

from embedding import almacen, fuente, modelo, rutas

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

# Cada cuantas frases distintas se confirma la transaccion. Es el punto de
# control: si la corrida se corta, se pierde como mucho un bloque.
BLOQUE = 2000


def correr(limite=None, rehacer=False, codificador=None, con=None):
    """
    Una pasada completa. Devuelve un resumen de lo que hizo.

    codificador y con se pueden pasar ya abiertos para que el centinela no
    vuelva a cargar el modelo ni a reabrir la base en cada vuelta.
    """
    if rehacer:
        borrado = almacen.vaciar()
        print(f"  --rehacer: {borrado['vectores']:,} vectores borrados "
              f"(nota_triage no se toca)")

    propia = con is None
    con = con or almacen.abrir()
    try:
        utiles, vacias = fuente.leer(con)
        if limite:
            utiles = utiles.head(limite)
        if len(vacias):
            print(f"  {len(vacias):,} notas sin {fuente.COLUMNA_TEXTO}: "
                  f"se omiten")
        if utiles.empty:
            print(f"\n  nota_triage todavia no tiene notas con "
                  f"{fuente.COLUMNA_TEXTO}.")
            return {"notas_escritas": 0, "frases_codificadas": 0}

        almacen.comprobar_identidad(con)

        faltan = almacen.pendientes(con, utiles)
        print(f"  {len(utiles):,} notas | {len(utiles) - len(faltan):,} al dia "
              f"| {len(faltan):,} por vectorizar")
        if faltan.empty:
            _informar(almacen.estadisticas(con))
            return {"notas_escritas": 0, "frases_codificadas": 0}

        unicos = fuente.distintos(faltan)
        ahorro = 100 * (1 - len(unicos) / len(faltan))
        print(f"  {len(unicos):,} frases distintas que codificar "
              f"({ahorro:.1f}% menos trabajo que ir nota a nota)")

        codificador = codificador or _cargar_modelo()
        escritas = _procesar_en_bloques(con, codificador, faltan, unicos)

        _informar(almacen.estadisticas(con))
        return {"notas_escritas": escritas, "frases_codificadas": len(unicos)}
    finally:
        if propia:
            con.close()


def _cargar_modelo():
    print(f"  cargando {modelo.MODELO} (CPU)...", flush=True)
    inicio = time.perf_counter()
    codificador = modelo.Codificador()
    print(f"  cargado en {time.perf_counter() - inicio:.0f} s")
    return codificador


def _procesar_en_bloques(con, codificador, faltan, unicos):
    """
    Codifica por frase distinta y escribe por nota.

    El reparto es el merge de abajo: cada nota pendiente recoge el vector de
    su huella. Ese paso es el que convierte 479 llamadas al modelo en 596
    filas escritas.
    """
    import numpy as np

    huellas = unicos["huella"].tolist()
    textos = unicos["texto"].tolist()
    inicio = time.perf_counter()
    escritas = 0

    for desde in range(0, len(textos), BLOQUE):
        lote_textos = textos[desde:desde + BLOQUE]
        lote_huellas = huellas[desde:desde + BLOQUE]

        def avance(n, base=desde, total=len(textos), t0=inicio):
            hecho = base + n
            ritmo = hecho / max(time.perf_counter() - t0, 1e-9)
            faltantes = (total - hecho) / max(ritmo, 1e-9)
            print(f"\r  {hecho:,}/{total:,} frases  {ritmo:.1f}/s  "
                  f"faltan ~{faltantes / 60:.1f} min   ", end="", flush=True)

        matriz, truncados = codificador.codificar(lote_textos, avance)
        tokens = [len(codificador.tokenizador.encode(t)) for t in lote_textos]

        # el reparto: de una fila por frase a una fila por nota
        posicion = {h: i for i, h in enumerate(lote_huellas)}
        notas = faltan[faltan["huella"].isin(posicion)]
        filas = np.array([posicion[h] for h in notas["huella"]])

        almacen.guardar(con,
                        notas["OID"].tolist(),
                        notas["huella"].tolist(),
                        matriz[filas],
                        [tokens[i] for i in filas])
        escritas += len(notas)
        if truncados:
            print(f"\n  aviso: {truncados} frase(s) pasaron de "
                  f"{modelo.LONGITUD_MAXIMA} tokens y se truncaron")

    print(f"\r  {len(textos):,} frases codificadas -> {escritas:,} notas "
          f"escritas en {time.perf_counter() - inicio:.0f} s" + " " * 20)
    return escritas


def _informar(datos):
    # La redaccion importa: 'N notas | M frases distintas' se leyo una vez como
    # si solo se hubieran guardado M vectores. Son N filas, una por nota, cada
    # una con su vector. M es cuantas veces hubo que llamar al modelo.
    print(f"\n  embedding: {datos['notas']:,} vectores guardados, uno por nota "
          f"| {datos['frases']:,} textos distintos que hubo que codificar "
          f"| {datos['megabytes']} MB")
    if datos["notas_sin_vector"]:
        print(f"  {datos['notas_sin_vector']:,} notas de nota_triage sin "
              f"vector (sin frase o sin procesar todavia)")
    if datos["notas_sin_fecha"]:
        print(f"  {datos['notas_sin_fecha']:,} notas sin fecha_triage: "
              f"corre 'python -m NLP.procesar --fechas'")
    if datos["truncados"]:
        print(f"  {datos['truncados']:,} notas truncadas "
              f"(max {datos['tokens_max']} tokens, ventana "
              f"{modelo.LONGITUD_MAXIMA})")


def main():
    parser = argparse.ArgumentParser(
        description="Vectoriza nota_triage.frase_procesada con SapBERT-es.")
    parser.add_argument("--limite", type=int, help="solo las primeras N notas")
    parser.add_argument("--rehacer", action="store_true",
                        help="borra los vectores y empieza de cero")
    parser.add_argument("--estado", action="store_true",
                        help="imprime lo que hay guardado y sale")
    args = parser.parse_args()

    if args.estado:
        datos = almacen.estadisticas()
        print(f"  {rutas.BASE_DATOS}")
        _informar(datos)
        print(f"  modelo: {datos['modelos']}")
        return

    correr(limite=args.limite, rehacer=args.rehacer)


if __name__ == "__main__":
    main()
