"""
Informe agregado de calidad de un CSV de triage, sin exponer texto de notas.

Responde a si el proceso conserva el motivo de consulta y cuanto recorta. Ver
NLP/docs/FLUJO.md y la bitacora de E0.5. Uso:

    python -m NLP.evaluacion.calidad
    python -m NLP.evaluacion.calidad --csv <a.csv> --comparar <b.csv> --guardar
"""

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from NLP import rutas

# Palabras por token en la ventana de bge-m3 (contrato con embedding/, PLAN §7).
TOKENS_POR_PALABRA = 1.99
VENTANA_BGE = 128

RE_PALABRA = re.compile(r"[a-záéíóúñü]+", re.IGNORECASE)
RE_GLOSA = re.compile(r"\([^)]{3,80}\)")


def cargar_lexicos():
    """Carga los dos lexicos que deciden que es terminologia clinica."""
    from NLP.depuracion import depuracion
    from NLP.reduccion import reduccion

    return depuracion.cargar(), reduccion.cargar_lexico()


def terminos(texto):
    """
    Terminologia clinica de un texto, como conjunto.

    Mismo criterio que reparacion/comparacion.py: un termino cuenta solo si los
    dos lexicos lo reconocen, que es lo que evita las falsas alarmas.
    """
    from NLP.depuracion import depuracion
    from NLP.reduccion import reduccion

    return {p for p in depuracion.terminos_clinicos(str(texto or ""))
            if reduccion._es_clinica(p)}


def palabras(texto):
    return RE_PALABRA.findall(str(texto or "").lower())


def tokens_sustituidos(antes, despues):
    """
    Cuantos tokens cambio el corrector, alineando las dos listas.

    Se cuentan solo las sustituciones: los borrados y las inserciones vienen de
    la fase 1 (simbolos, encabezados) y no son intervencion ortografica.
    Comparar por posicion inflaba la cifra: un solo borrado desalinea el resto.
    """
    import difflib

    cambios = 0
    for etiqueta, i1, i2, j1, j2 in difflib.SequenceMatcher(
            a=antes, b=despues, autojunk=False).get_opcodes():
        if etiqueta == "replace":
            cambios += min(i2 - i1, j2 - j1)
    return cambios


def _percentil(serie, q):
    return float(serie.quantile(q)) if len(serie) else 0.0


def medir(df):
    """
    Metricas agregadas de un CSV de triage.

    Ninguna clave contiene texto de notas: solo recuentos y proporciones.
    """
    filas = []
    for _, fila in df.iterrows():
        orig = str(fila.get("texto_original", ""))
        emb = str(fila.get("texto_embedding", ""))
        cor = str(fila.get("texto_corregido", ""))
        nor = str(fila.get("texto_normalizado", ""))

        t_orig, t_emb = terminos(orig), terminos(emb)
        p_orig, p_emb, p_cor = palabras(orig), palabras(emb), palabras(cor)
        tocados = tokens_sustituidos(p_orig, p_cor)

        filas.append({
            "terminos_original": len(t_orig),
            "retencion": len(t_orig & t_emb) / len(t_orig) if t_orig else None,
            "palabras_original": len(p_orig),
            "palabras_embedding": len(p_emb),
            "reduccion": 1 - len(p_emb) / len(p_orig) if p_orig else None,
            "vacio": len(p_emb) == 0,
            "muy_corto": 0 < len(p_emb) < 3,
            "glosa": bool(RE_GLOSA.search(nor or emb)),
            "tokens_estimados": len(p_emb) * TOKENS_POR_PALABRA,
            "tocada": tocados > 0,
            "tokens_tocados": tocados,
            "tokens_totales": len(p_orig),
        })

    m = pd.DataFrame(filas)
    ret = m["retencion"].dropna()
    red = m["reduccion"].dropna()
    total = len(m)
    prop = lambda serie: round(float(serie.mean()), 4) if len(serie) else None

    return {
        "notas": total,
        "notas_con_terminologia": int(m["terminos_original"].gt(0).sum()),
        "retencion_media": round(float(ret.mean()), 4) if len(ret) else None,
        "retencion_mediana": round(_percentil(ret, 0.5), 4),
        "retencion_p10": round(_percentil(ret, 0.10), 4),
        "prop_retencion_total": prop(ret == 1),
        "prop_pierden_mas_de_la_mitad": prop(ret < 0.5),
        "prop_sin_terminologia_en_embedding": prop(ret == 0),
        "reduccion_media": round(float(red.mean()), 4) if len(red) else None,
        "reduccion_mediana": round(_percentil(red, 0.5), 4),
        "notas_vacias": int(m["vacio"].sum()),
        "notas_muy_cortas": int(m["muy_corto"].sum()),
        "prop_con_glosa": prop(m["glosa"]),
        "palabras_embedding_p50": round(_percentil(m["palabras_embedding"], 0.50), 1),
        "palabras_embedding_p99": round(_percentil(m["palabras_embedding"], 0.99), 1),
        "palabras_embedding_max": int(m["palabras_embedding"].max()) if total else 0,
        "notas_sobre_ventana_bge": int((m["tokens_estimados"] > VENTANA_BGE).sum()),
        "prop_notas_tocadas_por_corrector": prop(m["tocada"]),
        "tasa_intervencion_bruta": round(
            float(m["tokens_tocados"].sum() / max(m["tokens_totales"].sum(), 1)), 5),
    }


ORDEN_INFORME = [
    ("notas", "notas en el CSV"),
    ("notas_con_terminologia", "notas con terminologia clinica en el original"),
    ("retencion_media", "retencion media de terminologia (1 = no pierde nada)"),
    ("retencion_mediana", "retencion mediana"),
    ("retencion_p10", "retencion del decil peor (p10)"),
    ("prop_retencion_total", "proporcion que conserva TODA su terminologia"),
    ("prop_pierden_mas_de_la_mitad", "proporcion que pierde mas de la mitad"),
    ("prop_sin_terminologia_en_embedding", "proporcion que se queda SIN terminologia"),
    ("reduccion_media", "recorte medio de palabras (0,60 = se queda con el 40%)"),
    ("reduccion_mediana", "recorte mediano"),
    ("notas_vacias", "notas con texto_embedding vacio"),
    ("notas_muy_cortas", "notas con menos de 3 palabras"),
    ("prop_con_glosa", "proporcion con glosa entre parentesis (E5.1)"),
    ("palabras_embedding_p50", "palabras del texto de embedding (p50)"),
    ("palabras_embedding_p99", "palabras del texto de embedding (p99)"),
    ("notas_sobre_ventana_bge", "notas que superarian la ventana de bge-m3"),
    ("prop_notas_tocadas_por_corrector", "proporcion de notas que el corrector toca"),
    ("tasa_intervencion_bruta", "tokens cambiados / tokens totales"),
]


def imprimir(metricas, otras=None, etiquetas=("actual", "comparado")):
    ancho = max(len(t) for _, t in ORDEN_INFORME)
    if otras:
        print(f"  {'':{ancho}}  {etiquetas[0]:>12}  {etiquetas[1]:>12}  {'dif':>10}")
    for clave, titulo in ORDEN_INFORME:
        valor = metricas.get(clave)
        if otras is None:
            print(f"  {titulo:{ancho}}  {valor}")
            continue
        otro = otras.get(clave)
        dif = ""
        if isinstance(valor, float) and isinstance(otro, float):
            dif = f"{otro - valor:+.4f}"
        elif isinstance(valor, int) and isinstance(otro, int):
            dif = f"{otro - valor:+}"
        print(f"  {titulo:{ancho}}  {str(valor):>12}  {str(otro):>12}  {dif:>10}")


def main():
    ap = argparse.ArgumentParser(
        description="Informe agregado de calidad de un CSV de triage.")
    ap.add_argument("--csv", default=str(rutas.TRIAGE_LIMPIO))
    ap.add_argument("--comparar", default=None,
                    help="segundo CSV; se comparan solo los OID presentes en ambos")
    ap.add_argument("--limite", type=int, default=None)
    ap.add_argument("--guardar", action="store_true")
    ap.add_argument("--item", default="calidad")
    args = ap.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    cargar_lexicos()
    df = pd.read_csv(args.csv, dtype=str, keep_default_na=False)
    otro = None
    if args.comparar:
        otro = pd.read_csv(args.comparar, dtype=str, keep_default_na=False)
        comunes = set(df["OID"]) & set(otro["OID"])
        df, otro = df[df["OID"].isin(comunes)], otro[otro["OID"].isin(comunes)]
        print(f"OID comunes a los dos CSV: {len(comunes):,}")
    if args.limite:
        df = df.head(args.limite)
        otro = otro.head(args.limite) if otro is not None else None

    print(f"\nCALIDAD DE {args.csv}  ({len(df):,} notas)\n")
    metricas = medir(df)
    metricas_otro = medir(otro) if otro is not None else None
    imprimir(metricas, metricas_otro,
             (Path(args.csv).stem[:12], Path(args.comparar).stem[:12] if args.comparar else ""))

    if args.guardar:
        carpeta = rutas.SALIDAS / "metricas"
        carpeta.mkdir(parents=True, exist_ok=True)
        destino = carpeta / f"{date.today().isoformat()}-{args.item}.json"
        contenido = {"csv": str(args.csv), "fecha": date.today().isoformat(),
                     "metricas": metricas}
        if metricas_otro:
            contenido["csv_comparado"] = str(args.comparar)
            contenido["metricas_comparado"] = metricas_otro
        destino.write_text(json.dumps(contenido, indent=2, ensure_ascii=False),
                           encoding="utf-8")
        print(f"\n  Guardado en {destino}")


if __name__ == "__main__":
    main()
