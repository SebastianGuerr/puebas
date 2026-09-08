"""
Conjunto de referencia: las correcciones hechas a mano, y como se miden.

POR QUE ANOTACIONES Y NO NOTAS REESCRITAS
    Una nota de triage puede tener 400 palabras. Reescribirla entera a mano
    para corregir seis errores introduce errores nuevos de transcripcion, y
    ademas hace imposible saber DONDE estaba cada error, que es justo lo que
    hace falta para medir el corrector.

    Por eso la unidad de trabajo es la correccion: (lo que dice, lo que deberia
    decir). El texto corregido se genera aplicandolas sobre el original, asi
    que es exacto por construccion. El juicio es manual; la aplicacion no.

QUE SE MIDE CON ESTO
    aciertos     el pipeline hizo la correccion que correspondia
    omisiones    habia un error y el pipeline no lo toco
    danos        el pipeline cambio algo que estaba bien, o lo cambio mal

    Precision = aciertos / (aciertos + danos)
    Cobertura = aciertos / (aciertos + omisiones)

    La precision importa mas que la cobertura: dejar 'dias' sin tilde le cuesta
    poco al modelo siguiente, convertir 'fazecas' en 'canecas' le inyecta un
    dato falso. Por eso el objetivo es precision alta aunque la cobertura se
    quede corta.

FORMATO DEL ARCHIVO DE ANOTACIONES
    referencia_correcciones.json

    {
      "761683": {
        "correcciones": [["SUBCLNICA", "SUBCLINICA"], ["CORIOAMNINITIS", "CORIOAMNIONITIS"]],
        "problemas": ["typo", "mayusculas"],
        "duda_clinica": false,
        "comentario": ""
      }
    }

    correcciones  pares (como esta escrito, como deberia estar). Se aplican
                  respetando limites de palabra y sin distinguir mayusculas.
    problemas     etiquetas del catalogo de abajo, para el informe de estado.
    duda_clinica  true si la correccion necesita que la valide alguien clinico.
                  No soy medico: en ortografia y abreviaturas soy fiable, en
                  'esto es disnea o taquipnea' no lo soy.
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
RUTA_ANOTACIONES = BASE_DIR / "referencia_correcciones.json"
RUTA_MUESTRA = BASE_DIR / "muestra_revision.csv"
RUTA_REFERENCIA = BASE_DIR / "referencia.csv"

csv.field_size_limit(10 ** 7)

# Catalogo de problemas. Es el vocabulario con el que se documenta el estado
# del corpus: cada nota revisada se etiqueta con los que presenta.
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


from morfologia import sin_tildes  # la eñe se conserva; ver morfologia.py


# ==========================================================
# APLICACION
# ==========================================================

def aplicar(texto, correcciones):
    """
    Aplica los pares (mal, bien) sobre el texto original.

    Se respetan los limites de palabra para que corregir 'ne' no toque
    'nefropatia', y se ignoran mayusculas al buscar para que una anotacion
    sirva igual en una nota gritada y en una normal. El reemplazo conserva la
    caja que se anoto.
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
    ruta = Path(ruta)
    if not ruta.exists():
        return {}
    return json.loads(ruta.read_text(encoding="utf-8"))


def guardar_anotaciones(datos, ruta=RUTA_ANOTACIONES):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1),
                          encoding="utf-8")
    return len(datos)


def construir_referencia(muestra=RUTA_MUESTRA, anotaciones=RUTA_ANOTACIONES,
                         salida=RUTA_REFERENCIA):
    """Escribe referencia.csv con el original y el corregido a mano."""
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
# MEDICION DEL PIPELINE
# ==========================================================

def _tokens(texto, plegar_tildes=True):
    """
    Tokens de un texto. plegar_tildes=False conserva los acentos.

    OJO CON EL PLEGADO
        La primera version plegaba siempre, y con eso 'clavicula' y 'clavícula'
        eran el mismo token: toda restauracion de tilde se contaba como
        omision, y la cobertura salia 16,5% cuando el corrector si las estaba
        aplicando. Una correccion que solo anade tildes hay que evaluarla con
        los acentos puestos.
    """
    texto = str(texto).lower()
    if plegar_tildes:
        texto = sin_tildes(texto)
    return set(re.findall(r"[^\W\d_]+", texto, re.UNICODE))


def evaluar(csv_pipeline, anotaciones=RUTA_ANOTACIONES, muestra=RUTA_MUESTRA):
    """
    Compara la salida del pipeline contra las correcciones anotadas a mano.

    Para cada correccion (mal -> bien) mira que hizo el pipeline con ese token:
      acierto  el token corregido esta en su salida y el erroneo ya no
      omision  el token erroneo sigue ahi
      otro     ni uno ni otro: el pipeline lo cambio por una tercera cosa,
               que es el caso mas grave porque inventa una palabra
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
            # solo se evaluan correcciones de una palabra: las de varias
            # palabras no se pueden juzgar token a token
            if not re.fullmatch(r"[^\W\d_]+", mal, re.UNICODE):
                continue
            if not re.fullmatch(r"[^\W\d_]+", bien, re.UNICODE):
                continue
            # una correccion que solo pone tildes se juzga con los acentos
            # puestos; el resto se juzga plegado, para que 'dolro' -> 'dolor'
            # cuente igual escriba el pipeline 'dolor' o 'dólor'
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
    """Documento de estado: que problemas trae el corpus y con que frecuencia."""
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
