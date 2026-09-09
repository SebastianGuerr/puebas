"""
Auditoría del pipeline de limpieza: qué cambió, cuánto y con qué riesgo.

Mide las tres fases sobre el CSV ya generado, comparando las cuatro columnas de
texto que produce el orquestador. Medir solo el par (texto limpio, texto
corregido) dejaría fuera la limpieza y la normalización, que entre las dos
modifican miles de notas sin producir un solo reemplazo palabra por palabra.

QUÉ OFRECE
    medir()             diccionario de métricas comparables entre corridas
    comparar()          dos mediciones lado a lado, con el signo de cada cambio
    regresiones()       casos concretos, con identificador, que ya fallaron una
                        vez y no deben volver a fallar
    typos_no_corregidos() la prueba en sentido contrario: errores evidentes que
                        el corrector debe seguir arreglando
    escribir_reporte()  el CSV con cada sustitución distinta, fase por fase

LAS DOS PRUEBAS, Y POR QUÉ HACEN FALTA LAS DOS
    Las regresiones vigilan que el pipeline no corrompa terminología. Pero cada
    defensa que se añade para evitarlo puede pasarse de frenado y dejar de
    corregir lo que sí es un error, y entonces las regresiones siguen en verde
    mientras la calidad empeora. Por eso existe la lista de errores de control:
    palabras que no son español ni terminología y que deben corregirse siempre.
    Si alguna sobrevive, hay una defensa demasiado estricta.

USO
    python -m NLP.evaluacion.auditoria                      mide la última corrida
    python -m NLP.evaluacion.auditoria --guardar base.json  congela la línea base
    python -m NLP.evaluacion.auditoria --contra base.json   compara contra ella

La razón de trabajar con números y no con impresiones: cada cambio del pipeline
se acepta o se rechaza comparándolo con la corrida anterior, no con el recuerdo
de cómo estaba.
"""

import argparse
import csv
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

from NLP import rutas

CSV_POR_DEFECTO = rutas.TRIAGE_LIMPIO

csv.field_size_limit(10 ** 7)

COL_ID = "OID"
COL_ORIGINAL = "texto_original"
COL_CORREGIDO = "texto_corregido"
COL_NORMALIZADO = "texto_normalizado"

RE_TOKEN = re.compile(r"\S+")
RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")

# Delimitador de palabra para las busquedas de errores de control. Se construye
# desde el codigo del caracter para que ninguna edicion posterior lo convierta
# por accidente en un retroceso, cosa que ya ocurrio una vez y dejo el informe
# dando todo por correcto sin serlo.
LIMITE = chr(92) + "b"

# puntuacion que rodea a un token sin formar parte de la palabra
PUNTUACION_BORDE = ".,;:!?()[]{}\"' "

# marcas del reporte para lo que no es un reemplazo 1 a 1
BORRADO = "<borrado>"
INSERTADO = "<insertado>"

# Simbolos que en una nota clinica son contenido y no adorno. Se mide que
# proporcion sobrevive a la limpieza: perderlos cambia el significado de la
# nota, porque separan hallazgos o marcan que algo es una sospecha.
SIMBOLOS_CLINICOS = {
    "+": "suma de hallazgos",
    "?": "sospecha diagnostica",
    "(": "aclaracion",
    "<": "menor que",
    ">": "mayor que",
}

# Simbolos que NO deben sobrevivir: no son contenido, solo marcan division, y
# la limpieza los convierte en el separador indicado. Se miden aparte para que
# su desaparicion no cuente como perdida; lo que se verifica es que la division
# que marcaban siga representada.
#
# El asterisco queda fuera de esta tabla porque en el corpus es casi siempre una
# marca al final de la nota, que no separa nada: exigirle un separador de
# reemplazo reportaba un fallo inexistente.
SIMBOLOS_CONVERTIDOS = {
    "-": ("guion separador de lista", ","),
}

PROPORCION_MAYUSCULAS = 0.9

# Corrupciones confirmadas en corridas anteriores. Cada entrada es un termino
# clinico real que el pipeline convirtio en otra palabra, identificado por el
# OID de la nota donde ocurrio. Son la prueba de regresion: si alguna vuelve, el
# cambio que se estaba evaluando no sirve.
REGRESIONES = [
    (747111, "stemi", "IAM con elevacion del ST, se convirtio en 'stent'"),
    (726448, "fazecas", "escala de Fazekas, se convirtio en 'canecas'"),
    (786557, "taquicardico", "adjetivo clinico, se convirtio en 'taquicardia'"),
    (793242, "fomag", "fondo del magisterio, se convirtio en 'toma'"),
    (773416, "ir", "insulinorrequiriente en 'DM no IR', quedo como el verbo ir"),
    # Los tres que produjo la capa de contexto al puntuar con el promedio de los
    # subtokens en vez de con la suma. El promedio premiaba a los candidatos con
    # mas piezas, de modo que partir una palabra siempre ganaba.
    (815839, "dorada", "municipio de Caldas, se convirtio en 'morada'"),
    (803472, "afiliados", "palabra correcta, se partia en 'afilia dos'"),
]

# La prueba en sentido contrario. Son errores de digitacion inequivocos:
# ninguno es palabra del espanol ni terminologia, y todos aparecen decenas de
# veces en el corpus. Si alguno sobrevive a la correccion, hay una defensa
# pasada de rosca. Ver la explicacion en la cabecera del modulo.
TYPOS_QUE_DEBEN_CORREGIRSE = [
    ("pacinete", "paciente"),
    ("apciente", "paciente"),
    ("paicnete", "paciente"),
    ("consutla", "consulta"),
    ("dolro", "dolor"),
    ("malestra", "malestar"),
    ("evolcuion", "evolución"),
    ("abodminal", "abdominal"),
    ("refeire", "refiere"),
    ("hipotirodismo", "hipotiroidismo"),
]


# ==========================================================
# LECTURA DEL CSV
# ==========================================================

def leer(ruta=CSV_POR_DEFECTO):
    """Lee el CSV de una corrida como lista de diccionarios."""
    ruta = Path(ruta)
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre antes procesar.py.")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _sin_tildes(texto):
    """Pliega acentos para comparar. Aquí sí incluye la eñe: solo se usa para
    decidir si dos formas difieren únicamente en la tilde."""
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def _gritado(texto):
    """True si la nota está escrita casi toda en mayúsculas."""
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


def _columna(filas, nombre):
    """
    Extrae una columna del CSV. Si no está presente (porque esa fase no se
    ejecutó) devuelve la columna corregida, para que la medición no falle.
    """
    if filas and nombre in filas[0]:
        return [f[nombre] for f in filas]
    return [f.get(COL_CORREGIDO, "") for f in filas]


# ==========================================================
# MEDICIÓN
# ==========================================================

def _frecuencias(textos):
    """Recuento de palabras del corpus de entrada, para medir el riesgo."""
    conteo = Counter()
    for t in textos:
        conteo.update(RE_PALABRA.findall(t.lower()))
    return conteo


def sustituciones(originales, corregidos):
    """
    Compara dos versiones del corpus y devuelve qué cambió, agrupado por tipo.

    El resultado es un diccionario con:

        pares                reemplazos de una palabra por otra, con su
                             frecuencia. Es lo que se entiende por corrección.
        movimientos          tokens borrados e insertados. Sin este grupo, la
                             limpieza y la normalización quedarían invisibles:
                             la primera borra símbolos y la segunda inserta la
                             anotación entre paréntesis, y ninguna de las dos
                             produce un reemplazo uno a uno.
        ejemplos             una nota de muestra por cada cambio distinto
        estructurales        cuántas notas sufrieron borrados o inserciones

    El alineamiento se hace con SequenceMatcher y no emparejando por posición,
    porque la limpieza borra y fusiona tokens: al emparejar por posición, un
    token borrado desplaza todo lo que sigue e inventa sustituciones que nunca
    ocurrieron.

    Además se alinea sobre el núcleo de cada palabra, sin la puntuación que la
    rodea, porque un cambio de separador convertiría la misma palabra en un
    token distinto y aparecería como borrado.
    """
    from difflib import SequenceMatcher

    pares = Counter()
    ejemplos = {}
    movimientos = Counter()
    ejemplos_movimiento = {}
    estructurales = 0

    def _limpiar(token):
        return token.strip(PUNTUACION_BORDE)

    for antes, despues in zip(originales, corregidos):
        if antes == despues:
            continue
        # se compara el nucleo de cada palabra, sin su puntuacion (ver docstring)
        ta = [_limpiar(t) for t in RE_TOKEN.findall(antes.lower())]
        tb = [_limpiar(t) for t in RE_TOKEN.findall(despues.lower())]
        hubo_estructural = False

        for etiqueta, i1, i2, j1, j2 in SequenceMatcher(
                None, ta, tb, autojunk=False).get_opcodes():
            if etiqueta == "equal":
                continue

            if etiqueta == "replace" and (i2 - i1) == (j2 - j1):
                for x, y in zip(ta[i1:i2], tb[j1:j2]):
                    # nucleos identicos: solo cambio la puntuacion de alrededor,
                    # que es reacomodo de la fase 1 y no una correccion
                    if x == y:
                        continue
                    nx, ny = x, y
                    pares[(nx, ny)] += 1
                    ejemplos.setdefault((nx, ny), (antes, despues))
                continue

            hubo_estructural = True
            for x in ta[i1:i2]:
                clave = (x, BORRADO)
                if clave[0]:
                    movimientos[clave] += 1
                    ejemplos_movimiento.setdefault(clave, (antes, despues))
            for y in tb[j1:j2]:
                clave = (INSERTADO, y)
                if clave[1]:
                    movimientos[clave] += 1
                    ejemplos_movimiento.setdefault(clave, (antes, despues))

        if hubo_estructural:
            estructurales += 1

    return {
        "pares": pares,
        "ejemplos": ejemplos,
        "movimientos": movimientos,
        "ejemplos_movimiento": ejemplos_movimiento,
        "estructurales": estructurales,
    }


def medir(filas):
    """
    Calcula todas las métricas de una corrida y las devuelve en un diccionario
    apto para guardar en JSON y comparar con otra.

    Cubre cinco bloques: la forma del corpus de entrada, la supervivencia de los
    símbolos clínicos, el volumen de cambio por fase, las sustituciones y su
    riesgo, y los errores de control que quedaron sin corregir.
    """
    total = max(len(filas), 1)
    originales = _columna(filas, COL_ORIGINAL)
    corregidos = _columna(filas, COL_CORREGIDO)
    normalizados = _columna(filas, COL_NORMALIZADO)

    m = {"registros": len(filas)}

    # --- forma del corpus de entrada ---
    m["notas_gritadas"] = sum(1 for t in originales if _gritado(t))
    m["pct_gritadas"] = round(100 * m["notas_gritadas"] / total, 1)

    # --- simbolos clinicos que sobreviven a la fase 1 ---
    supervivencia = {}
    for simbolo, _descripcion in SIMBOLOS_CLINICOS.items():
        antes = sum(1 for t in originales if simbolo in t)
        despues = sum(1 for t in corregidos if simbolo in t)
        if antes:
            supervivencia[simbolo] = {
                "notas_origen": antes,
                "notas_destino": despues,
                "pct_conservado": round(100 * despues / antes, 1),
            }
    m["simbolos_clinicos"] = supervivencia
    m["simbolos_perdidos"] = sum(
        v["notas_origen"] - v["notas_destino"] for v in supervivencia.values())

    # los convertidos no deben sobrevivir; lo que se comprueba es que la
    # division que marcaban siga representada por su separador
    conversion = {}
    for simbolo, (descripcion, separador) in SIMBOLOS_CONVERTIDOS.items():
        origen = [t for t in originales if simbolo in t]
        if not origen:
            continue
        indices = [i for i, t in enumerate(originales) if simbolo in t]
        con_separador = sum(1 for i in indices if separador in corregidos[i])
        conversion[simbolo] = {
            "notas_origen": len(indices),
            "conservan_separador": con_separador,
            "pct": round(100 * con_separador / len(indices), 1),
            "separador": separador,
        }
    m["simbolos_convertidos"] = conversion

    # --- volumen de cambio por fase ---
    m["notas_modificadas_ortografia"] = sum(
        1 for a, b in zip(originales, corregidos) if a != b)
    m["notas_modificadas_normalizacion"] = sum(
        1 for a, b in zip(corregidos, normalizados) if a != b)
    m["tokens_anadidos_normalizacion"] = sum(
        max(0, len(RE_TOKEN.findall(b)) - len(RE_TOKEN.findall(a)))
        for a, b in zip(corregidos, normalizados))

    # --- sustituciones y su riesgo ---
    diff = sustituciones(originales, corregidos)
    conteo = diff["pares"]
    m["sustituciones_distintas"] = len(conteo)
    m["sustituciones_aplicadas"] = sum(conteo.values())
    m["notas_con_cambio_estructural"] = diff["estructurales"]
    m["tokens_borrados"] = sum(v for (o, c), v in diff["movimientos"].items()
                               if c == BORRADO)
    m["tokens_insertados"] = sum(v for (o, c), v in diff["movimientos"].items()
                                 if o == INSERTADO)

    solo_tilde = sum(v for (o, c), v in conteo.items() if _sin_tildes(o) == _sin_tildes(c))
    m["sustituciones_solo_tilde"] = solo_tilde
    m["sustituciones_cambio_real"] = m["sustituciones_aplicadas"] - solo_tilde

    # Riesgo clinico: un termino que el corpus repite muchas veces no es un
    # descuido de digitacion, asi que reescribirlo es el error mas caro del
    # pipeline. Las sustituciones de solo tilde no cuentan, porque no cambian el
    # concepto.
    freq = _frecuencias(originales)
    riesgo = []
    for (o, c), veces in conteo.items():
        if _sin_tildes(o) == _sin_tildes(c):
            continue
        fo = freq.get(o.strip(".,;:"), 0)
        if fo >= 10:
            riesgo.append((fo, veces, o, c))
    riesgo.sort(reverse=True)
    m["sustituciones_sobre_termino_frecuente"] = len(riesgo)
    m["muestra_riesgo"] = [
        {"original": o, "corregido": c, "freq_corpus": fo, "veces": v}
        for fo, v, o, c in riesgo[:15]
    ]

    # --- notas que quedaron sin contenido ---
    m["notas_vacias_tras_limpieza"] = sum(1 for t in corregidos if not t.strip())

    # --- errores de control que sobrevivieron a la correccion ---
    # No se exige cero, porque la linea base tampoco lo lograba. Lo que se
    # vigila es que la cifra no aumente: subir significa que alguna defensa
    # nueva esta bloqueando correcciones legitimas.
    pendientes = typos_no_corregidos(filas)
    m["typos_sin_corregir"] = sum(destino for _t, _c, _o, destino in pendientes)
    m["detalle_typos"] = [
        {"typo": t, "correccion": c, "en_origen": o, "sin_corregir": d}
        for t, c, o, d in pendientes
    ]

    return m


def typos_no_corregidos(filas):
    """
    Errores de control que sobrevivieron a la corrección.

    Devuelve una tupla por error presente en el corpus, con la forma
    (error, corrección esperada, notas donde aparecía, notas donde sigue). Una
    lista vacía significa que ninguno de los errores de control aparece siquiera
    en el corpus de entrada.
    """
    salida = []
    for typo, correccion in TYPOS_QUE_DEBEN_CORREGIRSE:
        patron = re.compile(LIMITE + re.escape(typo) + LIMITE,
                            re.IGNORECASE)
        en_origen = sum(1 for f in filas if patron.search(f[COL_ORIGINAL]))
        if not en_origen:
            continue
        en_destino = sum(1 for f in filas if patron.search(f[COL_CORREGIDO]))
        salida.append((typo, correccion, en_origen, en_destino))
    return salida


def regresiones(filas):
    """
    Comprueba los casos concretos que ya fallaron una vez.

    Devuelve una tupla por caso, con la forma
    (oid, token, sobrevive, caja, descripción), donde los dos indicadores miden
    cosas distintas y de distinta gravedad:

        sobrevive  el término sigue en el texto y no se convirtió en otra
                   palabra. Es lo único que de verdad importa: convertir un
                   término en otra palabra inventa un dato clínico, mientras que
                   pasarlo a minúscula no.
        caja       además conserva las mayúsculas del original. Es deseable pero
                   secundario, y en una nota gritada no siempre hay evidencia
                   para arriesgarla.

    Medirlos juntos escondía el avance, porque un término que dejaba de
    corromperse seguía contando como fallo por salir en minúscula.

    Los dos indicadores valen None cuando el caso no se puede evaluar: la nota
    no está en esta corrida, o el token ni siquiera aparece en el original.
    """
    por_oid = {str(f[COL_ID]): f for f in filas}

    def _tokens(texto, plegar):
        texto = _sin_tildes(texto) if plegar else texto
        return set(re.findall(r"[^\W\d_]+", texto, re.UNICODE))

    salida = []
    for oid, token, descripcion in REGRESIONES:
        fila = por_oid.get(str(oid))
        if fila is None:
            salida.append((oid, token, None, None, "OID ausente de esta corrida"))
            continue

        # se busca por token completo y no por subcadena: una sigla corta
        # aparece dentro de muchas palabras y la comprobacion daria OK siempre
        if token not in _tokens(fila[COL_ORIGINAL], True):
            salida.append((oid, token, None, None, "el token no esta en el original"))
            continue

        destino_plegado = _tokens(fila[COL_CORREGIDO], True)
        sobrevive = token in destino_plegado

        venia_mayuscula = token.upper() in _tokens(fila[COL_ORIGINAL], False)
        if not venia_mayuscula:
            caja = sobrevive
        else:
            caja = token.upper() in _tokens(fila[COL_CORREGIDO], False)

        salida.append((oid, token, sobrevive, caja, descripcion))
    return salida


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


# ==========================================================
# DAÑO PROBABLE
# ==========================================================
#
# POR QUÉ EXISTE ESTA FUNCIÓN, Y POR QUÉ NO BASTABA CON LO QUE YA HABÍA
#     Las dos varas anteriores necesitan que alguien haya escrito antes el caso:
#     `referencia.py` compara contra 196 correcciones anotadas a mano, y
#     REGRESIONES enumera los tokens que ya fallaron una vez. Las dos miden bien
#     lo que cubren, y las dos son ciegas a lo que nadie anotó.
#
#     Medido: tres corrupciones reales del corrector pasaron por delante de
#     ambas sin encender nada.
#
#         afiliados  ->  'afilia dos'    una palabra correcta partida en dos
#         los        ->  'lamentamos'    un artículo sustituido por un verbo
#         dorada     ->  'morada'        un municipio convertido en otra palabra
#
#     Ninguna estaba en la referencia, porque a nadie se le ocurre anotar que
#     'afiliados' no debe partirse: se anota lo que hay que arreglar, no lo que
#     no hay que romper. El conjunto de referencia mide cobertura, y este tipo
#     de fallo es daño.
#
# LA IDEA
#     El daño no hay que reconocerlo caso por caso: tiene forma propia. Una
#     corrección legítima parte de algo que está mal escrito y llega a algo
#     parecido. Cuando el punto de partida ya era correcto, o el destino no se
#     parece, o la palabra estaba declarada como intocable, la sustitución es
#     sospechosa sea cual sea la palabra.
#
#     Por eso esto no enumera nada. Recorre las sustituciones que la propia
#     corrida produjo y les aplica cinco preguntas. No prueba que haya un error
#     -- hay correcciones legítimas que disparan alguna regla -- pero pone
#     delante la lista corta donde mirar, en vez de las miles de sustituciones
#     del informe completo.

# Motivos, del más grave al más leve.
DANO_DIVISION = "palabra correcta partida en dos"
DANO_DECLARADA = "termino declarado en el diccionario"
DANO_CONOCIDA = "palabra que el espanol reconoce"
DANO_DISTANCIA = "el reemplazo no se parece al original"
DANO_FRECUENCIA = "el original es mucho mas frecuente que el reemplazo"

# Un reemplazo que comparte pocas letras con el original no es una corrección
# ortográfica: es otra palabra. El umbral es relativo a la longitud porque dos
# ediciones sobre una palabra de cuatro letras cambian el concepto y sobre una
# de quince no.
FRACCION_DISTANCIA_MAXIMA = 0.40

# Cuántas veces más frecuente tiene que ser el original para que sustituirlo
# resulte sospechoso. Una errata no es más común que su forma correcta.
FACTOR_FRECUENCIA = 10


def _distancia(a, b):
    """Distancia de edición sin dependencias externas."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    previa = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        actual = [i]
        for j, cb in enumerate(b, 1):
            actual.append(min(previa[j] + 1, actual[j - 1] + 1,
                              previa[j - 1] + (ca != cb)))
        previa = actual
    return previa[-1]


def motivo_dano(original, reemplazo, conocida=None, declarada=None, frecuencia=None):
    """
    Por qué una sustitución concreta es sospechosa, o None si no lo es.

    Las cuatro comprobaciones se aplican en orden de gravedad. Los tres últimos
    parámetros son funciones que se inyectan para poder llamar a esto sin cargar
    spaCy ni el corpus; cuando faltan, la comprobación que dependía de ellas
    simplemente no se hace.
    """
    original = str(original or "").strip()
    reemplazo = str(reemplazo or "").strip()
    if not original or not reemplazo or original == reemplazo:
        return None

    plano_o = _sin_tildes(original.lower())
    plano_r = _sin_tildes(reemplazo.lower())

    # Restaurar una tilde deja las mismas letras y no puede cambiar el
    # concepto: nunca es daño, y se descarta antes que nada.
    if plano_o == plano_r:
        return None

    if " " in reemplazo and conocida and conocida(original):
        return DANO_DIVISION

    if declarada and declarada(original):
        return DANO_DECLARADA

    # UNA EDICION O UNAS LETRAS BAILADAS ES UNA ERRATA, NO UN DESTROZO.
    #
    # Sin esta salida, la regla siguiente marcaba como sospechosas justo las
    # correcciones que mejor funcionan:
    #
    #     apra -> para      mcuho -> mucho     ahce -> hace
    #     tien -> tiene     door  -> dolor     fibre -> fiebre
    #
    # Todas son typos de teclado, y todas disparaban 'palabra que el espanol
    # reconoce' porque el vocabulario de spaCy es laxo y acepta 'apra' o 'tien'
    # como palabras. Medido sobre el informe real, eran 32 de las 76 alertas.
    #
    # Las dos formas de la errata de teclado se reconocen solas: o son las
    # mismas letras en otro orden, o falta o sobra una. Ninguna de las dos
    # puede convertir una palabra en otra que no se le parezca, que es lo que
    # esta funcion busca. Va DESPUES de las dos reglas anteriores a proposito:
    # 'dorada' -> 'morada' es una sola edicion y aun asi es daño, y lo salva
    # que el municipio este declarado en el diccionario.
    if sorted(plano_o) == sorted(plano_r) or _distancia(plano_o, plano_r) <= 1:
        return None

    if conocida and conocida(original):
        return DANO_CONOCIDA

    limite = max(1, int(len(plano_o) * FRACCION_DISTANCIA_MAXIMA))
    if _distancia(plano_o, plano_r.replace(" ", "")) > limite:
        return DANO_DISTANCIA

    if frecuencia:
        f_o, f_r = frecuencia(original), frecuencia(reemplazo)
        if f_o and f_o >= FACTOR_FRECUENCIA * max(f_r, 1):
            return DANO_FRECUENCIA

    return None


def dano_probable(filas, minimo=1):
    """
    Sustituciones sospechosas de haber estropeado la nota en vez de arreglarla.

    `filas` son las que devuelve escribir_reporte(): (fase, original, reemplazo,
    veces, oid). Devuelve la misma forma con el motivo añadido, ordenada por
    gravedad y luego por frecuencia, de modo que lo que más notas afecta salga
    primero.

    Solo mira la fase de ortografía: la limpieza no cambia palabras y la
    normalización sustituye a propósito.
    """
    try:
        from NLP.fase2_ortografia import pesos
        from NLP.nucleo import reglas
        conocida = lambda p: reglas.es_palabra_conocida(reglas.normalizar(p))
        declarada = lambda p: reglas.normalizar(p) in reglas.SIGLAS
        frecuencia = pesos.frecuencia
    except Exception:
        conocida = declarada = frecuencia = None

    orden = {DANO_DIVISION: 0, DANO_DECLARADA: 1, DANO_CONOCIDA: 2,
             DANO_DISTANCIA: 3, DANO_FRECUENCIA: 4}

    salida = []
    for fila in filas:
        fase, original, reemplazo, veces = fila[0], fila[1], fila[2], fila[3]
        oid = fila[4] if len(fila) > 4 else ""
        if fase != "ortografia" or veces < minimo:
            continue
        motivo = motivo_dano(original, reemplazo, conocida, declarada, frecuencia)
        if motivo:
            salida.append((motivo, original, reemplazo, veces, oid))

    salida.sort(key=lambda x: (orden.get(x[0], 9), -x[3]))
    return salida
