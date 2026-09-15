"""
Vuelve a procesar un triage_limpio.csv viejo y dice, nota a nota, qué cambió.

    python -m NLP.reparacion.reparar --limite 200    # prueba, no toca nada
    python -m NLP.reparacion.reparar                 # todas, no toca nada
    python -m NLP.reparacion.reparar --aplicar       # sustituye el CSV

QUE PROBLEMA RESUELVE
    El CSV que hay en salidas/ se produjo con cuatro artefactos ausentes, y por
    eso arrastra tres defectos mezclados: notas a las que la fase 5 les quitó el
    motivo de consulta, notas cuya corrección ortográfica les cambió una palabra
    y con ella el sentido, y notas que no recibieron corrección ninguna porque
    el corrector trabajaba sin vocabulario.

    Volver a bajarlo todo de la base de datos costaría días y tiraría las notas
    que SÍ están bien. Este módulo aprovecha que la columna `texto_original` del
    propio CSV es la nota tal como la escribieron: es la misma materia prima que
    daría la base de datos, ya descargada.

NO SE VUELVE A IMPLEMENTAR NINGUNA FASE, Y ESO ES DELIBERADO
    Las notas se le pasan a `procesar.py` por la misma puerta por la que entran
    las de la base de datos: se renombra `texto_original` a la columna que ese
    módulo espera y se llaman sus propias funciones. Reescribir aquí las fases
    daría dos pipelines que se irían separando, y entonces reparar el CSV
    produciría un archivo que la corrida normal ya no sabría continuar.

    La consecuencia buena es que lo reparado y lo que se procese mañana salen
    del mismo código, que es justo lo que hace falta para poder seguir
    acumulando notas sobre lo ya limpio.

NO PISA NADA HASTA QUE SE LE DICE
    Por defecto escribe a `triage_reparado.csv` y a un informe, y deja el
    original intacto. `--aplicar` es el único modo que sustituye, y antes
    guarda una copia con fecha. El informe existe para mirarlo ANTES de aplicar:
    si trae notas en la categoría `perdio_motivo`, la reparación no está lista.
"""

import argparse
import shutil
import time
from datetime import datetime

import pandas as pd

from NLP import procesar, rutas
from NLP.depuracion import depuracion
from NLP.fase2_ortografia import ortografia
from NLP.fase3_normalizacion import normalizacion
from NLP.nucleo import reglas, requisitos
from NLP.nucleo.progreso import barra, fin_barra
from NLP.recursos import casing
from NLP.reduccion import extractor, reduccion
from NLP.reparacion import comparacion

CSV_ENTRADA = rutas.TRIAGE_LIMPIO
CSV_SALIDA = rutas.SALIDAS / "triage_reparado.csv"
INFORME = rutas.SALIDAS / "informe_reparacion.csv"

# Notas por bloque. Igual que en procesar.py y por lo mismo: un bloque entero
# pasa por todas las fases antes de contarse, asi que si esto se interrumpe lo
# ya medido sigue siendo valido.
BLOQUE = 250


def cargar_frecuencias(textos):
    """
    Construye el léxico de frecuencias del corpus, que es lo que desempata
    entre candidatos de corrección.

    SIN ESTO EL CORRECTOR DEJA DE CORREGIR, Y NO LO DICE
        `pesos.frecuencia()` devuelve 0 para toda palabra mientras nadie haya
        contado el corpus, y entonces ningun candidato gana por ser el
        frecuente. Medido sobre 100 notas reparadas sin este paso: 'DOLRO' se
        quedaba en 'dolro' y 'ANUSEAS' en 'anuseas', dos erratas que la corrida
        anterior SI habia arreglado. El CSV salia completo y con dos notas
        peores que antes.

    SE PREFIERE LA BASE DE DATOS AUNQUE EL CSV BASTARIA
        `procesar.py` cuenta sobre una muestra mucho mayor que la que va a
        corregir, a proposito: cuanto mas grande es el corpus observado, mejor
        distingue una palabra rara de una errata. Reparar contando solo las
        9.311 notas del CSV daria frecuencias distintas y, por tanto,
        correcciones distintas a las que dara la proxima corrida normal.

        Si la base de datos no responde se cuenta sobre el propio CSV y se
        avisa: es peor, pero sigue siendo mucho mejor que no contar nada.
    """
    try:
        from NLP.nucleo.conexion_bd import obtener_engine

        engine = obtener_engine()
        filtro = (f"{procesar.COLUMNA} IS NOT NULL AND "
                  f"LTRIM(RTRIM({procesar.COLUMNA})) <> ''")
        print("Construyendo lexico del corpus (base de datos)...")
        procesar.cargar_corpus(engine, filtro)
        return
    except Exception as exc:
        print(f"  AVISO: no se pudo leer la base de datos ({exc})")

    print("  se cuentan las frecuencias sobre el propio CSV")
    conteo = ortografia.construir_lexico(textos)
    print(f"  {len(conteo):,} palabras distintas sobre {len(textos):,} notas")


def cargar_recursos(reducir, textos):
    """
    Carga los mismos diccionarios y léxicos que carga una corrida normal, y
    devuelve si la fase 3 quedó operativa.

    EL ORDEN IMPORTA Y SE PAGO POR APRENDERLO
        `normalizacion.disponible()` responde que NO hasta que se llama a
        `normalizacion.cargar()`. La primera version de este modulo preguntaba
        antes de cargar, se quedaba con normalizar=False, y el CSV reparado
        salia sin la columna texto_normalizado y sin las anotaciones de la
        fase 3 -- pero con todas sus filas, asi que no fallaba nada.

        El informe lo delato: 4 notas figuraban perdiendo terminologia clinica
        y lo que habian perdido era la anotacion que la fase 3 no llego a
        poner. Por eso cargar y preguntar viven ahora en la misma funcion, en
        el orden correcto, y quien llama recibe la respuesta ya calculada.

    Es la parte de `procesar.main()` que no depende de la base de datos. Llama
    a las mismas funciones y en el mismo orden: si una corrida normal y una
    reparacion cargaran cosas distintas, producirian textos distintos a partir
    de la misma nota.
    """
    print("Cargando diccionarios...")
    ortografia.cargar_siglas()
    ortografia.cargar_lexico_clinico()

    cargar_frecuencias(textos)

    aprendidas = casing.cargar()
    print(f"  {aprendidas:,} tokens con capitalizacion aprendida "
          f"({len(casing.siglas()):,} siglas, "
          f"{len(casing.nombres_propios()):,} nombres propios)")
    print(f"  {len(reglas.SIGLAS):,} siglas | "
          f"{len(reglas.DIRECTAS):,} correcciones directas")

    if procesar.NORMALIZAR:
        print(f"  {normalizacion.cargar():,} expresiones de normalizacion")
    normalizar = procesar.NORMALIZAR and normalizacion.disponible()
    if procesar.NORMALIZAR and not normalizar:
        print("  AVISO: la fase 3 no quedo operativa")

    print(f"  {depuracion.cargar():,} raices clinicas indexadas")

    if reducir:
        reduccion.cargar_lexico()
        reduccion.cargar_lugares()

    return normalizar


def reparar(df_viejo, normalizar=True, reducir=True, usar_llm=False):
    """
    Reprocesa las notas y devuelve (df_nuevo, clasificaciones).

    `df_viejo` tiene que traer OID y texto_original. El resto de columnas se usa
    solo para comparar.
    """
    # La columna se renombra para entrar por la misma puerta que usan las notas
    # que vienen de la base de datos. Ver el docstring del modulo.
    trabajo = df_viejo[[procesar.LLAVE, "texto_original"]].copy()
    trabajo = trabajo.rename(columns={"texto_original": procesar.COLUMNA})

    trabajo = procesar.preparar(trabajo)
    cache = procesar.leer_cache()
    columna_juicio = "texto_normalizado" if normalizar else "texto_corregido"

    partes, inicio = [], time.time()
    total = len(trabajo)
    for arranque in range(0, total, BLOQUE):
        trozo = trabajo.iloc[arranque:arranque + BLOQUE].copy()
        conservadas, _ = procesar.procesar_bloque(
            trozo, cache, columna_juicio, normalizar, usar_llm)
        partes.append(conservadas)
        barra(min(arranque + BLOQUE, total), total, inicio, "reparando")
    fin_barra()

    nuevo = pd.concat(partes, ignore_index=True)

    columnas = [procesar.LLAVE, "texto_original", "texto_corregido"]
    if normalizar:
        columnas.append("texto_normalizado")
    if reducir:
        columnas.append("texto_embedding")
    nuevo = nuevo[[c for c in columnas if c in nuevo.columns]]

    return nuevo, comparar(df_viejo, nuevo)


def comparar(df_viejo, df_nuevo):
    """
    Clasifica cada nota cruzando las dos versiones por OID.

    Devuelve una lista de (oid, categoria, detalle, texto_viejo, texto_nuevo).
    """
    viejo = df_viejo.set_index(procesar.LLAVE).to_dict("index")
    salida = []
    for _, fila in df_nuevo.iterrows():
        oid = fila[procesar.LLAVE]
        antes = viejo.get(oid)
        if antes is None:
            continue
        categoria, detalle = comparacion.clasificar(antes, fila.to_dict())
        salida.append((oid, categoria, detalle,
                       str(antes.get("texto_embedding", "")),
                       str(fila.get("texto_embedding", ""))))
    return salida


def escribir_informe(clasificaciones, ruta=INFORME):
    """Guarda el detalle nota a nota, ordenado por gravedad."""
    orden = {c: i for i, c in enumerate(comparacion.ORDEN)}
    filas = sorted(clasificaciones, key=lambda x: orden.get(x[1], 9))
    pd.DataFrame(filas, columns=["OID", "categoria", "detalle",
                                 "embedding_antes", "embedding_despues"]
                 ).to_csv(ruta, index=False, encoding="utf-8-sig")
    return ruta


def informar(clasificaciones):
    """Resume por pantalla y devuelve cuántas notas empeoraron."""
    print(f"\n{'='*64}")
    total = len(clasificaciones)
    print(f"RESULTADO DE LA REPARACION ({total:,} notas)\n")
    for categoria, veces in comparacion.resumir(c[1] for c in clasificaciones):
        if veces:
            print(f"  {veces:6,}  ({veces/total*100:5.1f}%)  {categoria}")

    peores = [c for c in clasificaciones if c[1] == comparacion.PERDIO]
    if peores:
        print(f"\n  ATENCION: {len(peores):,} notas PIERDEN terminologia clinica.")

        # SE RESUME POR TERMINO, NO POR NOTA, Y ESO ES LO QUE HACE REVISABLE
        # UNA CORRIDA GRANDE.
        #
        # Sobre 9.311 notas, un 4% son ~370 avisos: leerlos de uno en uno no
        # lo hace nadie. Pero los terminos distintos que se pierden son unas
        # pocas decenas, y un termino basta para juzgar si la perdida importa:
        # 'signos' viene siempre de 'signos de alarma' y 'dada' de 'dada
        # estabilidad', que son texto administrativo en todas las notas donde
        # aparecen. Mirar la lista de terminos cuesta un minuto y decide.
        conteo = {}
        for _, _, detalle, _, _ in peores:
            for termino in detalle.replace("pierde:", "").split(","):
                termino = termino.strip()
                if termino:
                    conteo[termino] = conteo.get(termino, 0) + 1
        print(f"  Terminos distintos que se pierden ({len(conteo)}), por frecuencia:")
        for termino, veces in sorted(conteo.items(), key=lambda x: -x[1])[:25]:
            print(f"      {veces:5}  {termino}")

        print("\n  Ejemplos:")
        for oid, _, detalle, antes, despues in peores[:6]:
            print(f"\n    OID {oid}  {detalle}")
            print(f"      antes : {antes[:150]}")
            print(f"      ahora : {despues[:150]}")
    else:
        print("\n  Ninguna nota pierde terminologia clinica.")

    mejores = [c for c in clasificaciones if c[1] == comparacion.RECUPERO]
    if mejores:
        print(f"\n  Ejemplos de motivo recuperado ({len(mejores):,} notas):")
        for oid, _, detalle, antes, despues in mejores[:8]:
            print(f"\n    OID {oid}  {detalle}")
            print(f"      antes : {antes[:150]}")
            print(f"      ahora : {despues[:150]}")

    return len(peores)


def main():
    ap = argparse.ArgumentParser(
        description="Reprocesa triage_limpio.csv y compara con lo que habia.")
    ap.add_argument("--limite", type=int, default=None,
                    help="reparar solo las primeras N notas (para probar)")
    ap.add_argument("--aplicar", action="store_true",
                    help="sustituir triage_limpio.csv (guarda copia antes)")
    ap.add_argument("--con-llm", action="store_true",
                    help="usar el extractor de Ollama en la fase 5")
    ap.add_argument("--csv", default=str(CSV_ENTRADA),
                    help="CSV de entrada (por defecto, el de salidas/)")
    args = ap.parse_args()

    requisitos.exigir()

    df = pd.read_csv(args.csv)
    if args.limite:
        df = df.head(args.limite).copy()
    print(f"Notas a reparar: {len(df):,} de {args.csv}")

    reducir = procesar.REDUCIR
    normalizar = cargar_recursos(reducir, df['texto_original'])

    usar_llm = args.con_llm and extractor.disponible()
    if args.con_llm and not usar_llm:
        print("  AVISO: se pidio --con-llm pero el extractor no responde")
    print(f"  extractor de Ollama: {'si' if usar_llm else 'no'}")

    nuevo, clasificaciones = reparar(df, normalizar, reducir, usar_llm)

    nuevo.to_csv(CSV_SALIDA, index=False, encoding="utf-8-sig")
    ruta_informe = escribir_informe(clasificaciones)
    empeoraron = informar(clasificaciones)

    print(f"\n  CSV reparado: {CSV_SALIDA}")
    print(f"  Informe:      {ruta_informe}")

    if not args.aplicar:
        print("\n  No se toco triage_limpio.csv. Revisa el informe y, si esta")
        print("  bien, repite con --aplicar.")
        return

    if empeoraron:
        print(f"\n  NO SE APLICA: {empeoraron:,} notas pierden terminologia.")
        print("  Arregla la causa y vuelve a correr antes de aplicar.")
        raise SystemExit(1)

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    copia = rutas.SALIDAS / f"triage_limpio.previo-{sello}.csv"
    shutil.copy2(args.csv, copia)
    shutil.copy2(CSV_SALIDA, args.csv)
    print(f"\n  Aplicado. Copia del anterior en {copia.name}")


if __name__ == "__main__":
    main()
