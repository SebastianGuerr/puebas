"""
Auditoría del pipeline de limpieza: qué cambió, cuánto y con qué riesgo.

Orquestador de E6.2 (division de archivos grandes, ver
docs/ARQUITECTURA.md #2.9): la medicion de una corrida vive en
`auditoria_medicion.py` y el daño probable en `auditoria_dano.py`; este
modulo reexporta las dos interfaces para que `NLP.evaluacion.auditoria`
siga siendo el punto de entrada unico, y añade el reporte por fase, los
informes legibles y el CLI.

USO
    python -m NLP.evaluacion.auditoria                      mide la última corrida
    python -m NLP.evaluacion.auditoria --guardar base.json  congela la línea base
    python -m NLP.evaluacion.auditoria --contra base.json   compara contra ella
"""

import argparse
import csv
import json
import sys
from pathlib import Path

from NLP.evaluacion.auditoria_medicion import (  # noqa: F401 (reexportacion)
    CSV_POR_DEFECTO, COL_ID, COL_ORIGINAL, COL_CORREGIDO, COL_NORMALIZADO,
    RE_TOKEN, RE_PALABRA, LIMITE, PUNTUACION_BORDE, BORRADO, INSERTADO,
    SIMBOLOS_CLINICOS, SIMBOLOS_CONVERTIDOS, PROPORCION_MAYUSCULAS,
    REGRESIONES, TYPOS_QUE_DEBEN_CORREGIRSE,
    leer, _sin_tildes, _gritado, _columna, _frecuencias, sustituciones,
    medir, typos_no_corregidos, regresiones,
)
from NLP.evaluacion.auditoria_dano import (  # noqa: F401 (reexportacion)
    DANO_DIVISION, DANO_DECLARADA, DANO_CONOCIDA, DANO_DISTANCIA, DANO_FRECUENCIA,
    FRACCION_DISTANCIA_MAXIMA, FACTOR_FRECUENCIA,
    _distancia, motivo_dano, dano_probable,
)


# ==========================================================
# REPORTE DE CAMBIOS POR FASE
# ==========================================================

# Que par de columnas compara cada fase. Auditar solo la ortografia dejaba a la
# limpieza y a la normalizacion reescribiendo el texto sin dejar constancia.
FASES = [
    ("limpieza", COL_ORIGINAL, "texto_limpio"),
    ("ortografia", "texto_limpio", COL_CORREGIDO),
    ("normalizacion", COL_CORREGIDO, COL_NORMALIZADO),
]


def escribir_reporte(df, ruta, columnas_disponibles=()):
    """
    Escribe el CSV con cada sustitución distinta, su frecuencia y el
    identificador de una nota donde ocurrió, fase por fase.

        df                    el DataFrame del orquestador, con las columnas
                              intermedias todavía presentes
        columnas_disponibles  evita pedir una columna que no se generó, por
                              ejemplo cuando la normalización está desactivada

    Devuelve las filas escritas ordenadas de mayor a menor frecuencia, para que
    el orquestador pueda mostrar las primeras por pantalla. Ese orden es lo que
    hace útil el informe: en lugar de leer miles de notas, se revisan las
    sustituciones más repetidas, y si entre ellas aparece un fármaco, una sigla
    o un nombre propio, hay algo que corregir en el diccionario.
    """
    presentes = set(columnas_disponibles) | set(df.columns)
    filas = []

    for fase, col_antes, col_despues in FASES:
        if col_antes not in presentes or col_despues not in presentes:
            continue
        antes = df[col_antes].astype(str).tolist()
        despues = df[col_despues].astype(str).tolist()
        ids = df[COL_ID].tolist()

        diff = sustituciones(antes, despues)

        # el OID del ejemplo se recupera buscando el texto que lo produjo
        indice = {}
        for oid, texto in zip(ids, antes):
            indice.setdefault(texto, oid)

        for cubo, ejemplos in (("pares", "ejemplos"),
                               ("movimientos", "ejemplos_movimiento")):
            for (o, c), veces in diff[cubo].most_common():
                texto_ejemplo = diff[ejemplos][(o, c)][0]
                filas.append((fase, o, c, veces, indice.get(texto_ejemplo, "")))

    filas.sort(key=lambda f: -f[3])

    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["fase", "original", "corregido", "veces", "oid_ejemplo"])
        w.writerows(filas)

    return filas


# ==========================================================
# INFORMES
# ==========================================================

def _fmt(valor):
    """Formatea un número con separador de miles; el resto, como texto."""
    return f"{valor:,}" if isinstance(valor, int) else str(valor)


def informe(m, filas=None):
    """
    Informe legible de una medición. Si se pasan también las filas del CSV,
    añade el resultado de las dos pruebas: las regresiones y los errores de
    control que deben seguir corrigiéndose.
    """
    lineas = ["MEDICION DEL PIPELINE DE LIMPIEZA", "=" * 62]
    lineas.append(f"Registros                       : {m['registros']:,}")
    lineas.append(f"Notas en mayusculas             : {m['notas_gritadas']:,} "
                  f"({m['pct_gritadas']}%)")
    lineas.append("")
    lineas.append("SIMBOLOS CLINICOS QUE SOBREVIVEN A LA FASE 1")
    for simbolo, datos in sorted(m["simbolos_clinicos"].items()):
        lineas.append(f"  {simbolo!r:5} {SIMBOLOS_CLINICOS[simbolo]:22} "
                      f"{datos['notas_destino']:>6,} / {datos['notas_origen']:<6,} "
                      f"= {datos['pct_conservado']:5.1f}%")
    lineas.append(f"  total de notas que pierden un simbolo: {m['simbolos_perdidos']:,}")
    if m.get("simbolos_convertidos"):
        lineas.append("")
        lineas.append("SIMBOLOS CONVERTIDOS EN SEPARADOR (no deben sobrevivir)")
        for simbolo, datos in sorted(m["simbolos_convertidos"].items()):
            descripcion = SIMBOLOS_CONVERTIDOS[simbolo][0]
            lineas.append(f"  {simbolo!r:5} {descripcion:26} -> {datos['separador']!r}  "
                          f"{datos['conservan_separador']:>6,} / {datos['notas_origen']:<6,} "
                          f"= {datos['pct']:5.1f}%")
    lineas.append("")
    lineas.append("VOLUMEN DE CAMBIO")
    lineas.append(f"  notas tocadas por ortografia   : {m['notas_modificadas_ortografia']:,}")
    lineas.append(f"  notas tocadas por normalizacion: {m['notas_modificadas_normalizacion']:,}")
    lineas.append(f"  tokens anadidos por anotacion  : {m['tokens_anadidos_normalizacion']:,}")
    lineas.append(f"  notas con cambio estructural   : {m['notas_con_cambio_estructural']:,}")
    lineas.append(f"  tokens borrados                : {m.get('tokens_borrados', 0):,}")
    lineas.append(f"  tokens insertados              : {m.get('tokens_insertados', 0):,}")
    lineas.append("")
    lineas.append("SUSTITUCIONES")
    lineas.append(f"  distintas                      : {m['sustituciones_distintas']:,}")
    lineas.append(f"  aplicadas                      : {m['sustituciones_aplicadas']:,}")
    lineas.append(f"    de ellas, solo tilde         : {m['sustituciones_solo_tilde']:,}")
    lineas.append(f"    cambio real de letras        : {m['sustituciones_cambio_real']:,}")
    lineas.append(f"  sobre termino frecuente (>=10) : "
                  f"{m['sustituciones_sobre_termino_frecuente']:,}   <-- riesgo clinico")

    if m["muestra_riesgo"]:
        lineas.append("")
        lineas.append("  terminos frecuentes que el pipeline reescribio:")
        for r in m["muestra_riesgo"]:
            lineas.append(f"    {r['freq_corpus']:>5} en corpus | {r['veces']:>4}x  "
                          f"{r['original']} -> {r['corregido']}")

    if filas is not None:
        lineas.append("")
        lineas.append("REGRESIONES  (sobrevive = no se convirtio en otra palabra)")
        for oid, token, sobrevive, caja, nota in regresiones(filas):
            if sobrevive is None:
                estado = "   ?  "
            elif sobrevive and caja:
                estado = "  OK  "
            elif sobrevive:
                estado = " PARCIAL"   # el termino se salvo, la caja no
            else:
                estado = " FALLA "
            lineas.append(f"  [{estado}] OID {oid} '{token}' -- {nota}")

        pendientes = typos_no_corregidos(filas)
        lineas.append("")
        lineas.append("TYPOS QUE DEBEN SEGUIR CORRIGIENDOSE  (defensa pasada de rosca)")
        if not pendientes:
            lineas.append("  ninguno de los typos de control aparece en el corpus")
        for typo, correccion, en_origen, en_destino in pendientes:
            estado = "  OK  " if en_destino == 0 else " FALLA "
            lineas.append(f"  [{estado}] {typo:16} -> {correccion:16} "
                          f"quedan {en_destino:>3} de {en_origen:>3}")

    return "\n".join(lineas)


def comparar(base, nueva):
    """
    Compara dos mediciones métrica a métrica e indica, para cada una, si el
    cambio supone una mejora o un empeoramiento.

    No todas las métricas tienen una dirección deseable: el número de
    sustituciones aplicadas, por ejemplo, no es mejor alto ni bajo, así que se
    muestra la diferencia sin calificarla.
    """
    # por metrica: subir es bueno (+1), malo (-1) o neutro (0)
    DIRECCION = {
        "simbolos_perdidos": -1,
        "sustituciones_sobre_termino_frecuente": -1,
        "notas_con_cambio_estructural": -1,
        "tokens_anadidos_normalizacion": -1,
        "notas_vacias_tras_limpieza": -1,
        "typos_sin_corregir": -1,
        "tokens_borrados": -1,
        "tokens_insertados": 0,
        "sustituciones_cambio_real": 0,
        "sustituciones_solo_tilde": 0,
        "notas_modificadas_ortografia": 0,
        "notas_modificadas_normalizacion": 0,
        "sustituciones_distintas": 0,
        "sustituciones_aplicadas": 0,
    }
    lineas = ["COMPARACION CONTRA LA LINEA BASE", "=" * 62,
              f"{'metrica':42} {'antes':>9} {'ahora':>9}  "]
    for clave, direccion in DIRECCION.items():
        if clave not in base or clave not in nueva:
            continue
        antes, ahora = base[clave], nueva[clave]
        delta = ahora - antes
        if delta == 0:
            senal = "="
        elif direccion == 0:
            senal = f"{delta:+,}"
        else:
            mejora = (delta < 0) if direccion < 0 else (delta > 0)
            senal = f"{delta:+,} {'MEJORA' if mejora else 'EMPEORA'}"
        lineas.append(f"{clave:42} {_fmt(antes):>9} {_fmt(ahora):>9}  {senal}")
    return "\n".join(lineas)


# ==========================================================
# MAIN
# ==========================================================

def main():
    """
    Mide la última corrida e imprime el informe. Con --guardar congela las
    métricas en un JSON, y con --contra las compara con uno anterior.
    """
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", type=Path, default=CSV_POR_DEFECTO)
    ap.add_argument("--guardar", type=Path, default=None,
                    help="escribe las metricas en un JSON para comparar despues")
    ap.add_argument("--contra", type=Path, default=None,
                    help="compara las metricas actuales contra ese JSON")
    args = ap.parse_args()

    filas = leer(args.csv)
    m = medir(filas)

    print(informe(m, filas))

    if args.contra:
        base = json.loads(Path(args.contra).read_text(encoding="utf-8"))
        print()
        print(comparar(base, m))

    if args.guardar:
        Path(args.guardar).write_text(
            json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nMetricas guardadas en {args.guardar}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
