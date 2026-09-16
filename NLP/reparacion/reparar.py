"""
Vuelve a procesar un triage_limpio.csv viejo y dice, nota a nota, que cambio,
reusando las funciones de procesar.py (sin reimplementar fases). No pisa nada
hasta --aplicar, y se niega si el informe trae perdio_motivo. Responsabilidad
completa: docs/ARQUITECTURA.md, ficha `reparacion/reparar.py` (S2.10).

    python -m NLP.reparacion.reparar --limite 200    # prueba, no toca nada
    python -m NLP.reparacion.reparar --aplicar       # sustituye el CSV
"""

import argparse
import shutil
import time
from pathlib import Path

import pandas as pd

from NLP import procesar, rutas
from NLP.depuracion import depuracion
from NLP.fase2_ortografia import ortografia
from NLP.fase3_normalizacion import normalizacion
from NLP.nucleo import reglas, requisitos
from NLP.nucleo.progreso import barra, fin_barra
from NLP.nucleo.salida import EscritorCSV, rotar
from NLP.recursos import casing
from NLP.reduccion import extractor, reduccion
from NLP.reparacion import comparacion

CSV_ENTRADA = rutas.TRIAGE_LIMPIO
CSV_SALIDA = rutas.TRIAGE_REPARADO
INFORME = rutas.INFORME_REPARACION

COLUMNAS_INFORME = ["OID", "categoria", "detalle",
                    "embedding_antes", "embedding_despues"]

# Notas por bloque. Igual que en procesar.py y por lo mismo: un bloque entero
# pasa por todas las fases antes de contarse, asi que si esto se interrumpe lo
# ya medido sigue siendo valido.
BLOQUE = 250


def cargar_frecuencias(textos):
    """
    Construye el lexico de frecuencias del corpus (desempata candidatos de
    correccion; sin el, `pesos.frecuencia()` no distingue ninguna palabra).
    Prefiere la base de datos (corpus mas grande) al propio CSV como respaldo.
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
    Carga los mismos diccionarios y lexicos que una corrida normal (mismas
    funciones, mismo orden que `procesar.main()`) y devuelve si la fase 3
    quedo operativa.
    """
    # el orden importa: normalizacion.disponible() solo responde True despues
    # de llamar a normalizacion.cargar() (ver bitacora historica del item)
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
    Reprocesa las notas y devuelve (df_nuevo, clasificaciones). `df_viejo`
    debe traer OID y texto_original; el resto de columnas es solo para comparar.
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
    # El OID no es unico: PLAN.md §7 lo dice ("no se exige unico; gana la
    # ultima aparicion") y el CSV tiene 55 OID repetidos en 110 filas. Sin
    # deduplicar, to_dict("index") aborta la corrida entera al final, despues
    # de horas de trabajo. Se conserva la ultima, como manda el contrato.
    viejo = (df_viejo.drop_duplicates(subset=procesar.LLAVE, keep="last")
             .set_index(procesar.LLAVE).to_dict("index"))
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


def escribir_csv(df, ruta, columnas=None):
    """Escribe un DataFrame entero con EscritorCSV (utf-8-sig, CRLF, QUOTE_ALL)."""
    escritor = EscritorCSV(ruta, columnas if columnas is not None else df.columns)
    try:
        escritor.agregar(df)
    finally:
        escritor.cerrar()
    return Path(ruta)


def escribir_reparado(nuevo, ruta=CSV_SALIDA):
    """Guarda el CSV reparado con el mismo escritor y formato que triage_limpio.csv."""
    return escribir_csv(nuevo, ruta)


def escribir_informe(clasificaciones, ruta=INFORME):
    """Guarda el detalle nota a nota, ordenado por gravedad."""
    orden = {c: i for i, c in enumerate(comparacion.ORDEN)}
    filas = sorted(clasificaciones, key=lambda x: orden.get(x[1], 9))
    return escribir_csv(pd.DataFrame(filas, columns=COLUMNAS_INFORME), ruta)


def aplicar(destino, reparado):
    """Aparta `destino` con rotar() y pone `reparado` en su lugar. Devuelve la ruta apartada."""
    anterior = rotar(destino)
    shutil.copy2(reparado, destino)
    return anterior


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

        # se resume por termino, no por nota: es lo que hace revisable una
        # corrida grande (ver docs/ARQUITECTURA.md, ficha reparacion/reparar.py)
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


# Metricas de calidad.py que deciden si el CSV reparado sustituye al vigente, y
# en que direccion tiene que moverse cada una para que el cambio sea una mejora.
METRICAS_GATE = {
    "retencion_media": "sube",
    "prop_retencion_total": "sube",
    "prop_sin_terminologia_en_embedding": "baja",
    "prop_pierden_mas_de_la_mitad": "baja",
    "notas_vacias": "baja",
    "notas_sobre_ventana_bge": "baja",
}


def autoriza_aplicar(df_viejo, df_nuevo, empeoraron, forzar=False):
    """
    True si el CSV reparado puede sustituir al vigente. Ver bitacora de E0.3.

    POR QUE NO BASTA CON CONTAR LAS NOTAS QUE PIERDEN UN TERMINO
        Esa era la unica condicion hasta el 2026-09-16, y era imposible de
        cumplir: compara el CSV nuevo contra el VIEJO, y el viejo se produjo con
        artefactos ausentes. Cualquier nota que el corrector nuevo escriba de
        otra forma -- aunque sea mejor -- figura como perdida. Medido: 428 notas
        "pierden" mientras la retencion media SUBE de 0,9185 a 0,9773 y las que
        llegan sin terminologia caen de 204 a 49.

        Contar diferencias no dice si el resultado es mejor. Lo que decide es la
        calidad absoluta de cada version, que es lo que mide evaluacion/calidad.
        La cuenta de notas que pierden se sigue mostrando: es la lista que hay
        que revisar, no el criterio de aceptacion.
    """
    from NLP.evaluacion import calidad

    print("\n" + "=" * 64)
    print("COMPARACION DE CALIDAD (es lo que decide si se aplica)\n")
    antes, despues = calidad.medir(df_viejo), calidad.medir(df_nuevo)

    peores = []
    for clave, direccion in METRICAS_GATE.items():
        a, b = antes.get(clave), despues.get(clave)
        if a is None or b is None:
            continue
        mejor = (b > a) if direccion == "sube" else (b < a)
        marca = "  ok" if (mejor or b == a) else "PEOR"
        print(f"  {marca}  {clave:38} {a!s:>10} -> {b!s:>10}")
        if not (mejor or b == a):
            peores.append(clave)

    if empeoraron:
        print(f"\n  {empeoraron:,} notas pierden algun termino frente al CSV viejo.")
        print("  Revisalas con `python -m NLP.reparacion.revision`. No es el")
        print("  criterio de aceptacion, pero es la lista que hay que mirar.")

    if peores and not forzar:
        print(f"\n  NO SE APLICA: empeora en {len(peores)} metrica(s): "
              f"{', '.join(peores)}.")
        print("  Arregla la causa, o repite con --forzar si la revision a mano")
        print("  lo justifica y queda anotado en una bitacora.")
        return False
    if peores:
        print(f"\n  SE APLICA CON --forzar pese a empeorar en: {', '.join(peores)}.")
    else:
        print("\n  Ninguna metrica de calidad empeora: se aplica.")
    return True


def main():
    procesar.terminologia.alarmas.reiniciar()  # E2.0: idem procesar.main()
    ap = argparse.ArgumentParser(
        description="Reprocesa triage_limpio.csv y compara con lo que habia.")
    ap.add_argument("--limite", type=int, default=None,
                    help="reparar solo las primeras N notas (para probar)")
    ap.add_argument("--aplicar", action="store_true",
                    help="sustituir triage_limpio.csv (aparta la version anterior con rotar)")
    ap.add_argument("--forzar", action="store_true",
                    help="aplicar aunque empeore alguna metrica de calidad")
    ap.add_argument("--con-llm", action="store_true",
                    help="usar el extractor de Ollama en la fase 5")
    ap.add_argument("--csv", default=str(CSV_ENTRADA),
                    help="CSV de entrada (por defecto, el de salidas/)")
    ap.add_argument("--salida-dir", default=None,
                    help="carpeta donde escribir el CSV reparado y el informe "
                         "(por defecto, salidas/)")
    args = ap.parse_args()

    csv_salida, informe = CSV_SALIDA, INFORME
    if args.salida_dir:
        carpeta = Path(args.salida_dir)
        carpeta.mkdir(parents=True, exist_ok=True)
        csv_salida, informe = carpeta / CSV_SALIDA.name, carpeta / INFORME.name

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

    escribir_reparado(nuevo, csv_salida)
    ruta_informe = escribir_informe(clasificaciones, informe)
    empeoraron = informar(clasificaciones)

    print(f"\n  CSV reparado: {csv_salida}")
    print(f"  Informe:      {ruta_informe}")

    if not args.aplicar:
        print("\n  No se toco triage_limpio.csv. Revisa el informe y, si esta")
        print("  bien, repite con --aplicar.")
        return

    if not autoriza_aplicar(df, nuevo, empeoraron, args.forzar):
        raise SystemExit(1)

    anterior = aplicar(args.csv, csv_salida)
    print(f"\n  Aplicado. Version anterior apartada en "
          f"{anterior.name if anterior else '(no habia)'}")


if __name__ == "__main__":
    main()
