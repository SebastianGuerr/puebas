"""
Conjunto de referencia: las correcciones hechas a mano y cómo se miden.

Es la única vara objetiva del proyecto. El corrector se juzga comparando su
salida contra correcciones anotadas por una persona sobre notas reales.

POR QUÉ SE ANOTAN CORRECCIONES Y NO NOTAS REESCRITAS
    Una nota de triage puede tener cientos de palabras. Reescribirla entera a
    mano para arreglar unos pocos errores introduce errores nuevos de
    transcripción y, sobre todo, hace imposible saber DÓNDE estaba cada error,
    que es justo lo que hace falta para medir.

    Por eso la unidad de trabajo es la corrección: el par (lo que dice, lo que
    debería decir). El texto corregido se genera aplicando esos pares sobre el
    original, así que es exacto por construcción. El juicio es manual; la
    aplicación, no.

QUÉ SE MIDE
    aciertos    el corrector hizo la corrección que correspondía
    omisiones   había un error y no lo tocó
    daños       cambió el token por una tercera cosa, distinta del error y de
                la corrección

    precisión = aciertos / (aciertos + daños)
    cobertura = aciertos / (aciertos + omisiones)

    La precisión importa más que la cobertura: dejar una palabra sin tilde
    apenas afecta a las fases siguientes, mientras que sustituir un término por
    otro les inyecta un dato falso. El objetivo es precisión alta, aunque la
    cobertura se quede corta.

FORMATO DEL ARCHIVO DE ANOTACIONES
    Un objeto por nota, indexado por su identificador:

    {
      "761683": {
        "correcciones": [["SUBCLNICA", "SUBCLINICA"]],
        "problemas": ["typo", "mayusculas"],
        "duda_clinica": false,
        "comentario": ""
      }
    }

    correcciones   pares (como está escrito, como debería estar). Se aplican
                   respetando límites de palabra y sin distinguir mayúsculas.
    problemas      etiquetas del catálogo PROBLEMAS, para el informe de estado.
    duda_clinica   true cuando la corrección necesita validación de alguien con
                   criterio clínico. La distinción importa: en ortografía y
                   abreviaturas la anotación es fiable; en si un hallazgo es una
                   entidad clínica u otra, no.

USO
    python -m NLP.evaluacion.referencia --construir   escribe referencia.csv
    python -m NLP.evaluacion.referencia --estado      informe del corpus
    python -m NLP.evaluacion.referencia --evaluar <csv>   mide una corrida
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

from NLP import rutas

RUTA_ANOTACIONES = rutas.REFERENCIA_CORRECCIONES
RUTA_MUESTRA = rutas.MUESTRA_REVISION
RUTA_REFERENCIA = rutas.REFERENCIA

csv.field_size_limit(10 ** 7)

# Catalogo de problemas: el vocabulario con el que se documenta el estado del
# corpus. Cada nota revisada se etiqueta con los que presenta, y de ahi sale el
# informe de estado.
PROBLEMAS = {
    "typo": "error de digitacion: letras cambiadas, sobrantes o faltantes",
    "tilde": "falta una tilde que la palabra lleva",
    "palabra_partida": "una palabra cortada en dos, o dos pegadas en una",
    "abreviatura": "abreviatura de habla que hay que expandir (gral, pte)",
    "sigla_sin_expandir": "sigla clinica correcta pero no interpretable sola",
    "mayusculas": "escrita integramente en mayusculas",
    "sin_estructura": "parrafo corrido sin separacion entre ideas",
    "exceso_estructura": "plantilla con mas encabezados que contenido clinico",
    "texto_administrativo": "habla del sistema, no del paciente",
    "puntuacion": "puntuacion ausente, sobrante o mal colocada",
    "numero_pegado": "cifra pegada a una palabra (19.6SMS, 03+00PM)",
    "duplicado": "texto repetido dentro de la misma nota",
    "ilegible": "tramo que no se puede reconstruir con seguridad",
    "sin_error": "la nota esta bien escrita",
}


from NLP.nucleo.morfologia import sin_tildes  # la eñe se conserva; ver morfologia.py


# ==========================================================
# APLICACIÓN DE LAS ANOTACIONES
# ==========================================================

def aplicar(texto, correcciones):
    """
    Aplica los pares (mal, bien) sobre el texto original y devuelve el
    resultado.

    Las palabras sueltas se buscan respetando los límites de palabra, para que
    corregir un fragmento no toque una palabra que lo contiene; los tramos con
    espacios o símbolos se buscan tal cual. La búsqueda ignora mayúsculas, de
    modo que una anotación sirve igual en una nota gritada que en una normal, y
    el reemplazo conserva la forma exacta que se anotó.
    """
    for mal, bien in correcciones:
        if not mal:
            continue
        # los tramos con espacios o simbolos se buscan tal cual; las palabras
        # sueltas con limite de palabra
        if re.fullmatch(r"[^\W\d_]+", mal, re.UNICODE):
            patron = re.compile(rf"(?<![^\W\d_]){re.escape(mal)}(?![^\W\d_])",
                                re.IGNORECASE | re.UNICODE)
        else:
            patron = re.compile(re.escape(mal), re.IGNORECASE)
        texto = patron.sub(lambda _m: bien, texto)
    return texto


def cargar_anotaciones(ruta=RUTA_ANOTACIONES):
    """Lee el archivo de anotaciones. Devuelve {} si todavía no existe."""
    ruta = Path(ruta)
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_anotaciones(datos, ruta=RUTA_ANOTACIONES):
    """Escribe las anotaciones y devuelve cuántas notas se guardaron."""
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return len(datos)


def construir_referencia(muestra=RUTA_MUESTRA, anotaciones=RUTA_ANOTACIONES,
                         salida=RUTA_REFERENCIA):
    """
    Cruza la muestra revisada con sus anotaciones y escribe el CSV de
    referencia, con el texto original y el corregido a mano lado a lado.
    Devuelve el número de notas escritas.

    Las notas de la muestra que todavía no tienen anotación se omiten.
    """
    datos = cargar_anotaciones(anotaciones)
    with open(muestra, encoding="utf-8-sig", newline="") as f:
        filas = list(csv.DictReader(f))

    escritas = 0
    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["OID", "estrato", "problemas", "duda_clinica",
                    "n_correcciones", "texto_original", "texto_referencia",
                    "comentario"])
        for fila in filas:
            anotacion = datos.get(str(fila["OID"]))
            if anotacion is None:
                continue
            correcciones = anotacion.get("correcciones", [])
            w.writerow([
                fila["OID"], fila["estrato"],
                "|".join(anotacion.get("problemas", [])),
                "si" if anotacion.get("duda_clinica") else "no",
                len(correcciones),
                fila["texto_original"],
                aplicar(fila["texto_original"], correcciones),
                anotacion.get("comentario", ""),
            ])
            escritas += 1
    return escritas


# ==========================================================
# MEDICIÓN DEL PIPELINE
# ==========================================================

def _tokens(texto, plegar_tildes=True):
    """
    Conjunto de tokens de un texto, plegando los acentos o conservándolos.

    La distinción es necesaria para medir bien: si se plegaran siempre, una
    palabra y su forma acentuada serían el mismo token y toda restauración de
    tilde se contaría como omisión, hundiendo la cobertura aunque el corrector
    las estuviera aplicando correctamente.
    """
    texto = str(texto).lower()
    if plegar_tildes:
        texto = sin_tildes(texto)
    return set(re.findall(r"[^\W\d_]+", texto, re.UNICODE))


def evaluar(csv_pipeline, anotaciones=RUTA_ANOTACIONES, muestra=RUTA_MUESTRA):
    """
    Compara la salida del pipeline contra las correcciones anotadas a mano.

    Devuelve el par (recuento, detalle): un contador con las categorías del
    resultado y la lista de casos no resueltos, con su motivo.

    Para cada corrección anotada se mira qué hizo el pipeline con ese token:

        acierto   el token corregido está en su salida y el erróneo ya no
        omision   el token erróneo sigue ahí
        otro      ni uno ni otro: lo cambió por una tercera cosa. Es el caso
                  más grave, porque introduce una palabra que nadie escribió

    Solo se evalúan las correcciones de una palabra, porque las de varias no
    pueden juzgarse token a token. Las que solo añaden tildes se juzgan con los
    acentos puestos, y el resto plegando los acentos, para que una corrección
    cuente igual escriba el pipeline la forma acentuada o la llana.
    """
    datos = cargar_anotaciones(anotaciones)
    with open(muestra, encoding="utf-8-sig", newline="") as f:
        por_oid_muestra = {r["OID"]: r for r in csv.DictReader(f)}
    with open(csv_pipeline, encoding="utf-8-sig", newline="") as f:
        por_oid_pipeline = {r["OID"]: r for r in csv.DictReader(f)}

    resultado = Counter()
    detalle = []

    for oid, anotacion in datos.items():
        fila = por_oid_pipeline.get(str(oid))
        if fila is None or str(oid) not in por_oid_muestra:
            resultado["nota_ausente"] += 1
            continue

        salida_plegada = _tokens(fila["texto_corregido"], plegar_tildes=True)
        salida_exacta = _tokens(fila["texto_corregido"], plegar_tildes=False)
        for mal, bien in anotacion.get("correcciones", []):
            # solo correcciones de una palabra: ver la nota de la cabecera
            if not re.fullmatch(r"[^\W\d_]+", mal, re.UNICODE):
                continue
            if not re.fullmatch(r"[^\W\d_]+", bien, re.UNICODE):
                continue
            # las correcciones de solo tilde se juzgan con los acentos puestos
            solo_tilde = sin_tildes(mal.lower()) == sin_tildes(bien.lower())
            if solo_tilde:
                m, b = mal.lower(), bien.lower()
                salida = salida_exacta
            else:
                m, b = sin_tildes(mal.lower()), sin_tildes(bien.lower())
                salida = salida_plegada

            if b in salida and m not in salida:
                resultado["acierto"] += 1
            elif m in salida:
                resultado["omision"] += 1
                detalle.append((oid, mal, bien, "sin corregir"))
            else:
                resultado["otro"] += 1
                detalle.append((oid, mal, bien, "cambiado por otra cosa"))

    return resultado, detalle


def informe_estado(anotaciones=RUTA_ANOTACIONES):
    """
    Informe legible del trabajo de anotación: cuántas notas se revisaron,
    cuántas correcciones se anotaron, cuántas requieren validación clínica y con
    qué frecuencia aparece cada tipo de problema en el corpus.
    """
    datos = cargar_anotaciones(anotaciones)
    if not datos:
        return "Todavia no hay notas revisadas."

    conteo = Counter()
    correcciones = 0
    con_duda = 0
    for anotacion in datos.values():
        conteo.update(anotacion.get("problemas", []))
        correcciones += len(anotacion.get("correcciones", []))
        con_duda += bool(anotacion.get("duda_clinica"))

    total = len(datos)
    lineas = [
        "ESTADO DE LAS NOTAS REVISADAS A MANO",
        "=" * 62,
        f"Notas revisadas          : {total:,}",
        f"Correcciones anotadas    : {correcciones:,}",
        f"Media por nota           : {correcciones/total:.1f}",
        f"Requieren revision clinica: {con_duda:,}",
        "",
        "PROBLEMAS ENCONTRADOS",
    ]
    for problema, veces in conteo.most_common():
        descripcion = PROBLEMAS.get(problema, "")
        lineas.append(f"  {problema:22} {veces:>5,}  {100*veces/total:5.1f}%  {descripcion}")
    return "\n".join(lineas)


def main():
    """
    Punto de entrada. Las tres acciones son independientes y pueden combinarse
    en la misma invocación.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--construir", action="store_true",
                    help="escribe referencia.csv desde las anotaciones")
    ap.add_argument("--estado", action="store_true",
                    help="informe de problemas encontrados")
    ap.add_argument("--evaluar", type=Path, default=None,
                    help="mide un CSV del pipeline contra la referencia")
    args = ap.parse_args()

    if args.construir:
        print(f"referencia.csv: {construir_referencia():,} notas")
    if args.estado:
        print(informe_estado())
    if args.evaluar:
        resultado, detalle = evaluar(args.evaluar)
        aciertos = resultado["acierto"]
        danos = resultado["otro"]
        omisiones = resultado["omision"]
        total = aciertos + danos + omisiones
        print("MEDICION CONTRA EL CONJUNTO DE REFERENCIA")
        print("=" * 62)
        print(f"  correcciones evaluadas : {total:,}")
        print(f"  aciertos               : {aciertos:,}")
        print(f"  omisiones              : {omisiones:,}")
        print(f"  cambiado por otra cosa : {danos:,}")
        if aciertos + danos:
            print(f"\n  precision : {100*aciertos/(aciertos+danos):5.1f}%")
        if aciertos + omisiones:
            print(f"  cobertura : {100*aciertos/(aciertos+omisiones):5.1f}%")
        if detalle:
            print("\n  primeros casos no resueltos:")
            for oid, mal, bien, motivo in detalle[:20]:
                print(f"    OID {oid:8} {mal:20} -> {bien:20} {motivo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
