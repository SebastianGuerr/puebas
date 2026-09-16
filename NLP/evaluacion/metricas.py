"""
Módulo de métricas del corrector: detección, corrección, F0.5, intervención,
CER/WER de control, acuerdo de motivo y kappa entre anotadores.

Definiciones exactas, ejemplos verificados a mano y decisiones de diseño en
docs/bitacora/2026-09-16-E2.2.md. Ver también PLAN.md §4.5 y §8 (E2.2).
"""

import argparse
import csv
import difflib
import json
import re
import sys
import time
from pathlib import Path

import pandas as pd

from NLP import rutas
from NLP.nucleo.salida import EscritorCSV

csv.field_size_limit(10 ** 7)

# tokens: letras (con tildes y ene), sin digitos ni separadores
TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

COLUMNAS_HISTORICO = [
    "fecha", "item", "version_corrector", "F0.5",
    "precision_deteccion", "cobertura_deteccion",
    "precision_correccion", "cobertura_correccion",
    "tasa_intervencion", "acuerdo_motivo", "notas", "comentario",
]

_RE_VERSION = re.compile(r'VERSION_CORRECTOR\s*=\s*"([^"]+)"')


# ==========================================================
# TOKENIZACION Y ALINEACION
# ==========================================================

def tokenizar(texto):
    """Lista ordenada de tokens en minuscula (tildes y ene conservadas)."""
    return TOKEN_RE.findall(str(texto).lower())


def _normalizar_forma(forma):
    """Forma comparable: recorta espacios, ya viene en minuscula."""
    return str(forma).strip()


def mapa_cambios(orig, otros):
    """
    Devuelve (cambiado, forma), dos listas del mismo largo que `orig`.

    cambiado[i]  True si el token i de `orig` queda dentro de un tramo no
                 'equal' al alinear con `otros` (difflib.SequenceMatcher).
    forma[i]     el texto que le corresponde segun esa alineacion: el propio
                 token si no cambia, o la union de los tokens de `otros` que
                 sustituyen a todo el tramo (mismo valor repetido en cada
                 indice del tramo cuando el reemplazo cubre varios tokens).

    Los tramos 'insert' (i1 == i2) no tocan ningun indice de `orig`: una
    palabra que el gold agrega sin que exista nada que corregir en el
    original queda fuera de esta representacion. Es una limitacion conocida,
    documentada en la bitacora del item, no un descuido.
    """
    sm = difflib.SequenceMatcher(a=orig, b=otros, autojunk=False)
    n = len(orig)
    cambiado = [False] * n
    forma = list(orig)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        texto = _normalizar_forma(" ".join(otros[j1:j2]))
        for i in range(i1, i2):
            cambiado[i] = True
            forma[i] = texto
    return cambiado, forma


def distancia_edicion(a, b):
    """Distancia de Levenshtein clasica entre dos secuencias (chars o tokens)."""
    n, m = len(a), len(b)
    if n == 0:
        return m
    if m == 0:
        return n
    anterior = list(range(m + 1))
    for i in range(1, n + 1):
        actual = [i] + [0] * m
        for j in range(1, m + 1):
            costo = 0 if a[i - 1] == b[j - 1] else 1
            actual[j] = min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + costo)
        anterior = actual
    return anterior[m]


# ==========================================================
# METRICA POR NOTA
# ==========================================================

def evaluar_nota(texto_original, texto_correcto, texto_corregido=None,
                  motivo_span=None, texto_embedding=None):
    """
    Cuenta bruta de una nota: aciertos/fallos de deteccion y correccion,
    numerador/denominador de intervencion, distancias de CER/WER y el
    Jaccard de motivo. Ver la bitacora del item para la definicion de cada
    campo del diccionario devuelto.
    """
    conteo = {
        "tp_det": 0, "fp_det": 0, "fn_det": 0,
        "tp_cor": 0, "fp_cor": 0, "fn_cor": 0,
        "interv_num": 0, "interv_den": 0,
        "cer_dist": 0, "cer_len": 0,
        "wer_dist": 0, "wer_len": 0,
        "jaccard": None,
        "tiene_sistema": texto_corregido is not None,
    }

    orig_tok = tokenizar(texto_original)
    gold_tok = tokenizar(texto_correcto)
    gold_cambiado, gold_forma = mapa_cambios(orig_tok, gold_tok)

    if texto_corregido is not None:
        sys_tok = tokenizar(texto_corregido)
        sys_cambiado, sys_forma = mapa_cambios(orig_tok, sys_tok)

        for i in range(len(orig_tok)):
            g, s = gold_cambiado[i], sys_cambiado[i]
            if g and s:
                conteo["tp_det"] += 1
            elif s and not g:
                conteo["fp_det"] += 1
            elif g and not s:
                conteo["fn_det"] += 1

            if not g:
                conteo["interv_den"] += 1
                if s:
                    conteo["interv_num"] += 1

            correccion_ok = s and (sys_forma[i] == gold_forma[i])
            if correccion_ok:
                conteo["tp_cor"] += 1
            else:
                if s:
                    conteo["fp_cor"] += 1
                if g:
                    conteo["fn_cor"] += 1

        cer_a = str(texto_corregido).strip().lower()
        cer_b = str(texto_correcto).strip().lower()
        conteo["cer_dist"] = distancia_edicion(cer_a, cer_b)
        conteo["cer_len"] = len(cer_b)

        wer_a = tokenizar(texto_corregido)
        wer_b = gold_tok
        conteo["wer_dist"] = distancia_edicion(wer_a, wer_b)
        conteo["wer_len"] = len(wer_b)

    if motivo_span is not None and texto_embedding is not None:
        a = set(tokenizar(motivo_span))
        b = set(tokenizar(texto_embedding))
        if a or b:
            conteo["jaccard"] = len(a & b) / len(a | b)

    return conteo


def _dividir(num, den):
    return num / den if den else 0.0


def f_beta(precision, cobertura, beta=0.5):
    """F-beta con beta=0,5: pondera la precision el doble que la cobertura."""
    if precision == 0 and cobertura == 0:
        return 0.0
    b2 = beta * beta
    denom = b2 * precision + cobertura
    return (1 + b2) * precision * cobertura / denom if denom else 0.0


# ==========================================================
# CARGA DE ARCHIVOS Y AGREGACION
# ==========================================================

def _leer_csv(ruta):
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cargar_gold(ruta):
    """Filas del gold, indexadas por OID (texto)."""
    return {str(fila["OID"]): fila for fila in _leer_csv(ruta)}


def cargar_sistema(ruta):
    """Filas del CSV del pipeline, indexadas por OID (texto)."""
    return {str(fila["OID"]): fila for fila in _leer_csv(ruta)}


def evaluar_conjunto(gold_por_oid, sistema_por_oid):
    """
    Agrega evaluar_nota() sobre todo el gold y devuelve (metricas, notas_evaluadas).

    notas_evaluadas es el numero de notas del gold que tenian fila
    correspondiente en el CSV del sistema: son las unicas que entran en
    deteccion, correccion, intervencion, CER y WER. Las que no tienen
    correspondencia se cuentan aparte y no contaminan el denominador.
    """
    total = {
        "tp_det": 0, "fp_det": 0, "fn_det": 0,
        "tp_cor": 0, "fp_cor": 0, "fn_cor": 0,
        "interv_num": 0, "interv_den": 0,
        "cer_dist": 0, "cer_len": 0,
        "wer_dist": 0, "wer_len": 0,
    }
    jaccards = []
    notas_evaluadas = 0
    notas_sin_sistema = 0

    for oid, fila in gold_por_oid.items():
        fila_sys = sistema_por_oid.get(oid)
        texto_corregido = fila_sys["texto_corregido"] if fila_sys else None
        texto_embedding = fila_sys.get("texto_embedding") if fila_sys else None

        parcial = evaluar_nota(
            fila["texto_original"], fila["texto_correcto"],
            texto_corregido=texto_corregido,
            motivo_span=fila.get("motivo_span"),
            texto_embedding=texto_embedding,
        )

        if parcial["jaccard"] is not None:
            jaccards.append(parcial["jaccard"])

        if parcial["tiene_sistema"]:
            notas_evaluadas += 1
            for clave in total:
                total[clave] += parcial[clave]
        else:
            notas_sin_sistema += 1

    precision_deteccion = _dividir(total["tp_det"], total["tp_det"] + total["fp_det"])
    cobertura_deteccion = _dividir(total["tp_det"], total["tp_det"] + total["fn_det"])
    precision_correccion = _dividir(total["tp_cor"], total["tp_cor"] + total["fp_cor"])
    cobertura_correccion = _dividir(total["tp_cor"], total["tp_cor"] + total["fn_cor"])

    metricas = {
        "precision_deteccion": precision_deteccion,
        "cobertura_deteccion": cobertura_deteccion,
        "precision_correccion": precision_correccion,
        "cobertura_correccion": cobertura_correccion,
        "F0.5": f_beta(precision_correccion, cobertura_correccion),
        "tasa_intervencion": _dividir(total["interv_num"], total["interv_den"]),
        "cer": _dividir(total["cer_dist"], total["cer_len"]),
        "wer": _dividir(total["wer_dist"], total["wer_len"]),
        "acuerdo_motivo": (sum(jaccards) / len(jaccards)) if jaccards else 0.0,
        "notas": notas_evaluadas,
        "notas_sin_sistema": notas_sin_sistema,
    }
    return metricas


# ==========================================================
# VERSION DEL CORRECTOR
# ==========================================================

def version_corrector():
    """
    Lee VERSION_CORRECTOR de procesar.py con una expresion regular, sin
    importar el modulo: importarlo tarda ~5,4 s (spaCy, LanguageTool,
    sklearn) y ese coste se pagaria en cada invocacion de este script, que se
    ejecuta muchas veces por sesion en E3-E5. Ver bitacora del item.
    """
    texto = (rutas.PAQUETE / "procesar.py").read_text(encoding="utf-8")
    m = _RE_VERSION.search(texto)
    return m.group(1) if m else "desconocida"


# ==========================================================
# KAPPA DE COHEN (E0.6)
# ==========================================================

def cohen_kappa(etiquetas_a, etiquetas_b):
    """Kappa de Cohen entre dos listas de etiquetas categoricas pareadas."""
    n = len(etiquetas_a)
    if n == 0:
        return 0.0
    categorias = sorted(set(etiquetas_a) | set(etiquetas_b))
    idx = {c: i for i, c in enumerate(categorias)}
    k = len(categorias)
    matriz = [[0] * k for _ in range(k)]
    for a, b in zip(etiquetas_a, etiquetas_b):
        matriz[idx[a]][idx[b]] += 1
    po = sum(matriz[i][i] for i in range(k)) / n
    fila = [sum(matriz[i]) for i in range(k)]
    columna = [sum(matriz[i][j] for i in range(k)) for j in range(k)]
    pe = sum(fila[i] * columna[i] for i in range(k)) / (n * n)
    if pe >= 1:
        return 1.0
    return (po - pe) / (1 - pe)


def calcular_kappa(ruta_a, ruta_b, columna="gravedad"):
    """Kappa de Cohen sobre `columna` para los OID presentes en ambos CSV."""
    a = {str(f["OID"]): f[columna] for f in _leer_csv(ruta_a)}
    b = {str(f["OID"]): f[columna] for f in _leer_csv(ruta_b)}
    comunes = sorted(set(a) & set(b))
    return cohen_kappa([a[oid] for oid in comunes], [b[oid] for oid in comunes]), len(comunes)


# ==========================================================
# PERSISTENCIA (--guardar)
# ==========================================================

def guardar_json(metricas, fecha, item, version, comentario):
    """Escribe salidas/metricas/<fecha>-<item>.json con las claves de E2.2."""
    rutas.METRICAS.mkdir(parents=True, exist_ok=True)
    cuerpo = {
        "fecha": fecha,
        "item": item,
        "version_corrector": version,
        "F0.5": round(metricas["F0.5"], 4),
        "precision_deteccion": round(metricas["precision_deteccion"], 4),
        "cobertura_deteccion": round(metricas["cobertura_deteccion"], 4),
        "precision_correccion": round(metricas["precision_correccion"], 4),
        "cobertura_correccion": round(metricas["cobertura_correccion"], 4),
        "tasa_intervencion": round(metricas["tasa_intervencion"], 4),
        "acuerdo_motivo": round(metricas["acuerdo_motivo"], 4),
        "notas": metricas["notas"],
        "comentario": comentario,
        "cer": round(metricas["cer"], 4),
        "wer": round(metricas["wer"], 4),
    }
    item_seguro = re.sub(r"[^A-Za-z0-9._-]+", "_", item)
    destino = rutas.METRICAS / f"{fecha}-{item_seguro}.json"
    destino.write_text(json.dumps(cuerpo, ensure_ascii=False, indent=1), encoding="utf-8")
    return destino, cuerpo


def agregar_historico(cuerpo):
    """Anade una fila a salidas/metricas/historico.csv (formato PLAN.md §4.5)."""
    ruta = rutas.METRICAS / "historico.csv"
    fila = pd.DataFrame([{clave: cuerpo[clave] for clave in COLUMNAS_HISTORICO}])
    escritor = EscritorCSV(ruta, COLUMNAS_HISTORICO, reanudar=True)
    escritor.agregar(fila)
    escritor.cerrar()
    return ruta


# ==========================================================
# CLI
# ==========================================================

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--gold", type=Path, default=None,
                     help="CSV del gold: OID, texto_original, texto_correcto, ...")
    ap.add_argument("--csv", type=Path, default=None,
                     help="CSV del pipeline (por defecto, TRIAGE_LIMPIO)")
    ap.add_argument("--guardar", action="store_true",
                     help="escribe el JSON del item y una fila en historico.csv")
    ap.add_argument("--item", type=str, default=None,
                     help="identificador del item, para el nombre del JSON y el historico")
    ap.add_argument("--comentario", type=str, default="",
                     help="comentario libre para la fila de historico.csv")
    ap.add_argument("--kappa-a", type=Path, default=None,
                     help="CSV de gold del primer anotador (kappa sobre 'gravedad')")
    ap.add_argument("--kappa-b", type=Path, default=None,
                     help="CSV de gold del segundo anotador")
    args = ap.parse_args()

    if args.kappa_a or args.kappa_b:
        if not (args.kappa_a and args.kappa_b):
            print("--kappa-a y --kappa-b se usan juntos", file=sys.stderr)
            return 1
        kappa, n = calcular_kappa(args.kappa_a, args.kappa_b)
        print(f"OIDs comunes: {n}")
        print(f"kappa de Cohen (gravedad): {kappa:.4f}")
        return 0

    if not args.gold:
        ap.error("--gold es obligatorio (o usa --kappa-a/--kappa-b)")

    ruta_csv = args.csv or rutas.TRIAGE_LIMPIO
    if not ruta_csv.exists():
        print(f"No existe el CSV del pipeline: {ruta_csv}", file=sys.stderr)
        return 1

    gold = cargar_gold(args.gold)
    sistema = cargar_sistema(ruta_csv)
    metricas = evaluar_conjunto(gold, sistema)
    version = version_corrector()

    print("METRICAS DEL CORRECTOR")
    print("=" * 62)
    print(f"  gold                    : {args.gold}")
    print(f"  csv del pipeline        : {ruta_csv}")
    print(f"  version_corrector       : {version}")
    print(f"  notas del gold          : {len(gold):,}")
    print(f"  notas evaluadas (con sistema): {metricas['notas']:,}")
    print(f"  notas sin correspondencia    : {metricas['notas_sin_sistema']:,}")
    print(f"  precision_deteccion     : {metricas['precision_deteccion']:.4f}")
    print(f"  cobertura_deteccion     : {metricas['cobertura_deteccion']:.4f}")
    print(f"  precision_correccion    : {metricas['precision_correccion']:.4f}")
    print(f"  cobertura_correccion    : {metricas['cobertura_correccion']:.4f}")
    print(f"  F0.5                    : {metricas['F0.5']:.4f}")
    print(f"  tasa_intervencion       : {metricas['tasa_intervencion']:.4f}")
    print(f"  acuerdo_motivo          : {metricas['acuerdo_motivo']:.4f}")
    print(f"  cer                     : {metricas['cer']:.4f}")
    print(f"  wer                     : {metricas['wer']:.4f}")

    if args.guardar:
        fecha = time.strftime("%Y-%m-%d")
        item = args.item or args.gold.stem
        destino, cuerpo = guardar_json(metricas, fecha, item, version, args.comentario)
        historico = agregar_historico(cuerpo)
        print(f"\n  JSON      : {destino}")
        print(f"  historico : {historico}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
