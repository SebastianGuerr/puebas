"""
Auditoria del pipeline de limpieza. Complemento de procesar.py.

POR QUE EXISTE ESTE ARCHIVO
    procesar.py generaba reporte_cambios.csv comparando texto_limpio contra
    texto_corregido. Esa comparacion solo ve la fase 2. Medido sobre la corrida
    de 30.000 notas, quedaban fuera:

        fase 1 (limpieza)      5.136 notas cambian de numero de tokens
        fase 3 (normalizacion) 8.277 notas modificadas, una hasta +49 tokens

    Ninguna de las dos dejaba rastro, asi que los errores que se ven leyendo el
    CSV no aparecian en el reporte. Este modulo audita las cuatro columnas.

QUE MIDE
    medir()      un diccionario de metricas comparables entre corridas
    comparar()   dos mediciones lado a lado, con el signo de cada cambio
    regresiones()casos concretos con OID que no deben volver a fallar

COMO SE USA
    python auditoria.py                      mide triage_limpio.csv
    python auditoria.py --guardar base.json  congela la linea base
    python auditoria.py --contra base.json   compara contra ella

El objetivo de tener numero y no impresion: cada fase del rediseno se acepta o
se rechaza contra la corrida anterior, no contra el recuerdo de como estaba.
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
CSV_POR_DEFECTO = BASE_DIR / "triage_limpio.csv"

csv.field_size_limit(10 ** 7)

COL_ID = "OID"
COL_ORIGINAL = "texto_original"
COL_CORREGIDO = "texto_corregido"
COL_NORMALIZADO = "texto_normalizado"

RE_TOKEN = re.compile(r"\S+")
RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")

# Delimitador de palabra para las busquedas de typos. Se construye desde el
# codigo del caracter para que ninguna edicion posterior lo convierta por
# accidente en un retroceso (0x08), que es lo que ya paso una vez: el patron
# quedo buscando '\\x08pacinete\\x08' y el informe daba todo correcto sin serlo.
LIMITE = chr(92) + "b"

# puntuacion que rodea a un token sin formar parte de la palabra
PUNTUACION_BORDE = ".,;:!?()[]{}\"' "

# marcas del reporte para lo que no es un reemplazo 1 a 1
BORRADO = "<borrado>"
INSERTADO = "<insertado>"

# Simbolos que en una nota clinica son contenido, no adorno:
#   +  suma hallazgos: 'cefalea + emesis' son dos sintomas, no uno
#   ?  marca sospecha: 'HVDA ?' es una hipotesis, no un diagnostico
#   () aclara: 'DM (insulinorrequiriente)'
#   *  vinneta de lista
SIMBOLOS_CLINICOS = {
    "+": "suma de hallazgos",
    "?": "sospecha diagnostica",
    "(": "aclaracion",
    "<": "menor que",
    ">": "mayor que",
}

# Simbolos que NO deben sobrevivir: no son contenido, solo marcan division, y
# limpieza.py los convierte en el separador correspondiente. Se miden aparte
# para que su desaparicion no cuente como perdida: el asterisco de '* cefalea
# * emesis' desaparece a proposito, y lo que hay que verificar es que la
# separacion entre los dos items siga ahi.
# El asterisco no esta aca: medido sobre las 1.017 notas que lo traen, casi
# siempre es una marca al final ('TENGO DOLOR EN LA CABEZA*') y no separa nada,
# asi que exigirle un separador de reemplazo reportaba un fallo inexistente.
SIMBOLOS_CONVERTIDOS = {
    "-": ("guion separador de lista", ","),
}

PROPORCION_MAYUSCULAS = 0.9

# Corrupciones confirmadas en la corrida del 2 de septiembre de 2025. Cada una
# es un termino clinico real que el pipeline convirtio en otra palabra. Son la
# prueba de regresion: si vuelven, el cambio no sirvio.
REGRESIONES = [
    (747111, "stemi", "IAM con elevacion del ST, se convirtio en 'stent'"),
    (726448, "fazecas", "escala de Fazekas, se convirtio en 'canecas'"),
    (786557, "taquicardico", "adjetivo clinico, se convirtio en 'taquicardia'"),
    (793242, "fomag", "fondo del magisterio, se convirtio en 'toma'"),
    (773416, "ir", "insulinorrequiriente en 'DM no IR', quedo como el verbo ir"),
]

# La prueba en el sentido contrario, y hace falta tanto como la de arriba.
#
# Cada freno que se anade para no corromper terminologia puede pasarse de
# frenado y dejar de corregir lo que si es un error. Eso ya ocurrio: al pasarle
# a reglas.entidades() el texto recapitalizado, el NER empezo a marcar
# 'pacinete' y 'hipotirodismo' como nombres propios y el pipeline dejo de
# arreglarlos. Las cinco regresiones de arriba seguian en verde mientras tanto,
# asi que el dano no se veia.
#
# Estos son typos inequivocos: ninguno es palabra del espanol ni terminologia,
# y todos aparecen decenas de veces en el corpus. Si alguno sobrevive a la
# correccion, hay una defensa pasada de rosca.
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
# LECTURA
# ==========================================================

def leer(ruta=CSV_POR_DEFECTO):
    ruta = Path(ruta)
    if not ruta.exists():
        raise SystemExit(f"No existe {ruta}. Corre antes procesar.py.")
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def _gritado(texto):
    letras = [c for c in texto if c.isalpha()]
    if not letras:
        return True
    return sum(1 for c in letras if c.isupper()) / len(letras) > PROPORCION_MAYUSCULAS


def _columna(filas, nombre):
    """Devuelve la columna, o la corregida si la normalizada no existe."""
    if filas and nombre in filas[0]:
        return [f[nombre] for f in filas]
    return [f.get(COL_CORREGIDO, "") for f in filas]


# ==========================================================
# MEDICION
# ==========================================================

def _frecuencias(textos):
    conteo = Counter()
    for t in textos:
        conteo.update(RE_PALABRA.findall(t.lower()))
    return conteo


def sustituciones(originales, corregidos):
    """
    Cada sustitucion distinta con su conteo.

    POR QUE SequenceMatcher Y NO zip
        La fase 1 borra y fusiona tokens, asi que las dos listas casi nunca
        estan alineadas posicion a posicion. Emparejarlas con zip produce
        pares inventados: la primera version de este modulo reportaba
        'de -> servicio' 15 veces, que no es una correccion sino el desfase
        acumulado tras un token borrado. SequenceMatcher alinea por bloques
        iguales y solo llama sustitucion a lo que de verdad se reemplazo.

    QUE SE CUENTA EN CADA CUBO
        pares       reemplazos 1 a 1: una palabra por otra. Es lo que se suele
                    entender por 'correccion'.
        movimientos tokens borrados y tokens insertados. Sin este cubo la fase 1
                    y la fase 3 quedaban invisibles: la limpieza BORRA simbolos
                    y la normalizacion en modo 'anotar' INSERTA la expansion
                    entre parentesis. Ninguna de las dos produce un reemplazo
                    1 a 1, asi que el reporte anterior las daba por inexistentes
                    aunque entre las dos tocaban 13.000 notas.
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
        # Se alinea sobre el nucleo de cada palabra, sin la puntuacion que la
        # rodea. Alinear con la puntuacion pegada convertia un cambio de
        # separador en un borrado inventado: al pasar 'HTA - DM' a 'HTA, DM' el
        # token deja de ser 'hta' y pasa a ser 'hta,', el alineador los ve
        # distintos, y 'hta' aparecia como borrado 25 veces sin que se hubiera
        # borrado nada.
        ta = [_limpiar(t) for t in RE_TOKEN.findall(antes.lower())]
        tb = [_limpiar(t) for t in RE_TOKEN.findall(despues.lower())]
        hubo_estructural = False

        for etiqueta, i1, i2, j1, j2 in SequenceMatcher(
                None, ta, tb, autojunk=False).get_opcodes():
            if etiqueta == "equal":
                continue

            if etiqueta == "replace" and (i2 - i1) == (j2 - j1):
                for x, y in zip(ta[i1:i2], tb[j1:j2]):
                    # se compara el nucleo de la palabra: 'paciente.' ->
                    # 'paciente' es puntuacion reacomodada por la fase 1, no una
                    # correccion, y llenaba el informe de riesgo con ruido
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
    """Metricas comparables entre corridas. Todo numero, nada de impresiones."""
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

    # Un termino que el hospital escribio muchas veces no es un descuido de
    # digitacion. Corregirlo es el error mas caro del pipeline, porque cambia
    # un dato clinico que estaba bien.
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

    # --- typos de control que sobrevivieron a la correccion ---
    # No se exige cero: la linea base tampoco lo lograba ('refeire' quedaba sin
    # corregir en las 48 notas donde aparece). Lo que se vigila es que no
    # aumente, porque subir significa que alguna defensa nueva se paso de
    # frenado y esta bloqueando correcciones legitimas.
    pendientes = typos_no_corregidos(filas)
    m["typos_sin_corregir"] = sum(destino for _t, _c, _o, destino in pendientes)
    m["detalle_typos"] = [
        {"typo": t, "correccion": c, "en_origen": o, "sin_corregir": d}
        for t, c, o, d in pendientes
    ]

    return m


def typos_no_corregidos(filas):
    """
    Typos que sobrevivieron a la correccion. Lista vacia = todo bien.

    Devuelve (typo, correccion, veces_en_original, veces_en_corregido).
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
    Los casos concretos que ya fallaron una vez.

    DOS NIVELES, PORQUE NO SON EL MISMO PROBLEMA
      sobrevive  el termino sigue en el texto y no se convirtio en otra
                 palabra. Es lo unico que de verdad importa: 'FOMAG' -> 'toma'
                 inventa un dato clinico, 'FOMAG' -> 'fomag' no.
      caja       ademas conserva las mayusculas del original. Es deseable pero
                 secundario, y en notas gritadas no siempre hay evidencia
                 suficiente para arriesgarla.

    Medirlos juntos escondia el avance: tras recuperar la capitalizacion,
    'fomag' dejo de corromperse pero seguia contando como fallo porque salia
    en minuscula.

    Devuelve (oid, token, sobrevive, caja, descripcion).
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

        # por token completo, no por subcadena: 'ir' aparece dentro de
        # 'irradia' y 'venir', y buscarlo con 'in' daba siempre OK
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
# REPORTE DE CAMBIOS
# ==========================================================

# Que par de columnas compara cada fase. La version anterior solo generaba la
# fila 'ortografia', y por eso la limpieza y la normalizacion podian reescribir
# el texto sin que quedara constancia de una sola sustitucion.
FASES = [
    ("limpieza", COL_ORIGINAL, "texto_limpio"),
    ("ortografia", "texto_limpio", COL_CORREGIDO),
    ("normalizacion", COL_CORREGIDO, COL_NORMALIZADO),
]


def escribir_reporte(df, ruta, columnas_disponibles=()):
    """
    Cada sustitucion distinta con su conteo y un ejemplo, fase por fase.

    df: el DataFrame de procesar.py, con las columnas intermedias todavia
        presentes. columnas_disponibles evita pedir una que no se genero (por
        ejemplo texto_normalizado cuando NORMALIZAR esta en False).

    Devuelve las filas escritas, de mayor a menor frecuencia, para que
    procesar.py pueda imprimir las primeras en pantalla.
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
# INFORME
# ==========================================================

def _fmt(valor):
    return f"{valor:,}" if isinstance(valor, int) else str(valor)


def informe(m, filas=None):
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
    """Lado a lado. El signo indica si la metrica mejoro o empeoro."""
    # para cada metrica, si subir es bueno (+1), malo (-1) o neutro (0)
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
