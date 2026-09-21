"""
Control de calidad de los vectores: que esten bien antes de agrupar.

    python -m embedding.diagnostico
    python -m embedding.diagnostico --guardar    # deja el informe en docs/

POR QUE ESTO EXISTE Y NO BASTA CON QUE EL SCRIPT NO FALLE
    Una matriz de embeddings mala no da ningun error. Tiene la forma correcta,
    los numeros son finitos y el codigo corre. Los fallos que importan son
    silenciosos y solo se ven midiendo:

      - vectores sin normalizar, o normalizados a medias
      - una dimension equivocada que nadie comprueba
      - colapso: muchas frases distintas con el mismo vector
      - anisotropia: todo a la misma distancia de todo, que es lo que mata a
        un algoritmo de densidad como HDBSCAN
      - hubness: unos pocos puntos que son vecinos de todo el mundo
      - dimensiones muertas que reducen la dimension efectiva real

    Las siete pruebas de aqui cubren esos casos. Estan pensadas como compuerta
    ANTES del clustering, no como adorno: si la 4 o la 6 salen mal, agrupar es
    perder el tiempo y hay que arreglar el embedding primero.

LO QUE ESTO NO MIDE
    Si el modelo entiende de clinica. Eso lo mide comparar_modelos.py contra el
    catalogo, y esta en docs/MODELO.md. Aqui se comprueba que la matriz que
    quedo guardada es sana, que es otra pregunta.
"""

import argparse
import json
from datetime import datetime

import numpy as np
import pandas as pd

from embedding import almacen, modelo, rutas


def _pares_aleatorios(matriz, n=200_000, semilla=0):
    """Similitudes coseno de n pares al azar, sin construir la matriz entera."""
    rng = np.random.default_rng(semilla)
    total = len(matriz)
    i = rng.integers(0, total, n)
    j = rng.integers(0, total, n)
    distintos = i != j
    return np.einsum("ij,ij->i", matriz[i[distintos]], matriz[j[distintos]])


# ==========================================================
# LAS PRUEBAS
# ==========================================================

def p1_estructura(matriz, textos):
    """Forma, tipo, finitud y normalizacion. Lo que tiene que ser exacto."""
    normas = np.linalg.norm(matriz, axis=1)
    return {
        "filas": int(matriz.shape[0]),
        "dimension": int(matriz.shape[1]),
        "dimension_esperada": modelo.DIMENSION,
        "dimension_ok": matriz.shape[1] == modelo.DIMENSION,
        "dtype": str(matriz.dtype),
        "nan": int(np.isnan(matriz).sum()),
        "inf": int(np.isinf(matriz).sum()),
        "norma_min": float(normas.min()),
        "norma_max": float(normas.max()),
        "norma_desvio_max": float(np.abs(normas - 1).max()),
        "vectores_nulos": int((normas < 1e-6).sum()),
        "alineada_con_textos": len(matriz) == len(textos),
    }


def p2_colapso(matriz, textos):
    """
    Frases distintas que comparten vector, o casi.

    Un modelo roto devuelve el mismo vector para todo. Uno sano puede devolver
    vectores casi iguales para frases sinonimas, y eso es correcto: por eso se
    reportan aparte los ejemplos, para poder mirarlos.
    """
    filas_unicas = len(np.unique(matriz, axis=0))
    sim = matriz @ matriz.T
    np.fill_diagonal(sim, -np.inf)
    i, j = np.where(sim > 0.999)
    ejemplos = [(textos[a][:45], textos[b][:45], round(float(sim[a, b]), 5))
                for a, b in list(zip(i, j))[:10] if a < b]
    return {
        "vectores_distintos": int(filas_unicas),
        "vectores_repetidos": int(len(matriz) - filas_unicas),
        "pares_sobre_0999": int((i < j).sum()),
        "ejemplos": ejemplos,
    }


def p3_dimensiones(matriz):
    """
    Cuantas dimensiones trabajan de verdad.

    Si muchas tienen varianza cero, la dimension nominal miente. La dimension
    efectiva se estima con el participation ratio de los valores propios:
    (sum L)^2 / sum(L^2), que dice cuantas componentes llevan la varianza.
    """
    var = matriz.var(axis=0)
    centrada = matriz - matriz.mean(axis=0)
    valores = np.linalg.svd(centrada, compute_uv=False) ** 2
    efectiva = float(valores.sum() ** 2 / (valores ** 2).sum())
    acumulada = np.cumsum(valores) / valores.sum()
    return {
        "varianza_cero": int((var < 1e-10).sum()),
        "varianza_min": float(var.min()),
        "varianza_max": float(var.max()),
        "dimension_efectiva": round(efectiva, 1),
        "componentes_para_90pct": int(np.searchsorted(acumulada, 0.90) + 1),
        "varianza_de_la_1a_componente": round(float(acumulada[0]), 4),
    }


def p4_anisotropia(matriz):
    """
    LA PRUEBA QUE DECIDE SI SE PUEDE AGRUPAR.

    Se toma el coseno de pares al azar. Si la media es alta y la desviacion
    pequena, todas las frases estan a la misma distancia de todas y no hay
    zonas densas ni vacias que un algoritmo de densidad pueda encontrar.

    Referencia medida sobre ESTE corpus con bge-m3 (ver clustering/agrupar.py):
    media 0,469 con desviacion 0,087. Cuanto mas baja la media y mas ancha la
    distribucion, mejor para HDBSCAN.
    """
    sim = _pares_aleatorios(matriz)
    return {
        "coseno_medio": round(float(sim.mean()), 4),
        "desviacion": round(float(sim.std()), 4),
        "p1": round(float(np.percentile(sim, 1)), 4),
        "p50": round(float(np.percentile(sim, 50)), 4),
        "p99": round(float(np.percentile(sim, 99)), 4),
        "rango_98pct": round(float(np.percentile(sim, 99) -
                                   np.percentile(sim, 1)), 4),
        "referencia_bge_m3": {"media": 0.469, "desviacion": 0.087},
    }


def p5_separacion(matriz, categorias):
    """
    Pares de la misma categoria contra pares de categorias distintas.

    Es la prueba de que la geometria codifica clinica y no ruido. Sin una
    brecha clara aqui, los clusters que salgan no van a corresponder a nada.
    """
    valida = pd.notna(categorias)
    if valida.sum() < 20:
        return {"error": "muy pocas frases con categoria"}
    sub = matriz[valida]
    etq = np.asarray(categorias)[valida]
    sim = sub @ sub.T
    triangulo = np.triu_indices(len(sub), k=1)
    valores = sim[triangulo]
    misma = (etq[triangulo[0]] == etq[triangulo[1]])
    return {
        "n_frases": int(valida.sum()),
        "coseno_misma_categoria": round(float(valores[misma].mean()), 4),
        "coseno_distinta_categoria": round(float(valores[~misma].mean()), 4),
        "brecha": round(float(valores[misma].mean() -
                              valores[~misma].mean()), 4),
        "pares_misma": int(misma.sum()),
    }


def p6_hubness(matriz, textos, k=10):
    """
    Puntos que son vecinos de todo el mundo.

    En dimension alta aparecen 'hubs': unos pocos vectores que entran en la
    lista de k vecinos de casi todos. Rompen el clustering por densidad, que
    los toma por nucleos. Se mide con la asimetria de la distribucion de
    k-ocurrencias; por encima de ~2 se considera problematico.
    """
    from scipy.stats import skew

    sim = matriz @ matriz.T
    np.fill_diagonal(sim, -np.inf)
    vecinos = np.argpartition(-sim, k, axis=1)[:, :k]
    ocurrencias = np.bincount(vecinos.ravel(), minlength=len(matriz))
    orden = np.argsort(-ocurrencias)[:5]
    return {
        "k": k,
        "asimetria": round(float(skew(ocurrencias)), 3),
        "media": round(float(ocurrencias.mean()), 2),
        "maximo": int(ocurrencias.max()),
        "nunca_vecino": int((ocurrencias == 0).sum()),
        "mayores_hubs": [(textos[i][:45], int(ocurrencias[i])) for i in orden],
    }


def p7_determinismo(textos, n=24):
    """
    Volver a codificar las mismas frases da los mismos numeros.

    Si no, hay no-determinismo (dropout activo, orden de lote, hilos) y el
    almacen dejaria de ser reproducible: una frase vectorizada hoy y otra
    identica manana caerian en sitios distintos.
    """
    codificador = modelo.Codificador()
    muestra = list(textos[:n])
    a, _ = codificador.codificar(muestra)
    b, _ = codificador.codificar(muestra)
    diferencia = float(np.abs(a - b).max())
    return {
        "frases_probadas": len(muestra),
        "diferencia_maxima": diferencia,
        "identico": diferencia < 1e-6,
    }


# ==========================================================
# INFORME
# ==========================================================

def ejecutar(saltar_lentas=False):
    textos_df, matriz, indice = almacen.cargar()
    textos = textos_df["texto"].tolist()
    categorias = _categorias(textos)

    informe = {
        "cuando": datetime.now().isoformat(timespec="seconds"),
        "base": str(rutas.BASE_DATOS),
        "modelo": modelo.identidad(),
        "notas": int(len(indice)),
        "1_estructura": p1_estructura(matriz, textos),
        "2_colapso": p2_colapso(matriz, textos),
        "3_dimensiones": p3_dimensiones(matriz),
        "4_anisotropia": p4_anisotropia(matriz),
        "5_separacion": p5_separacion(matriz, categorias),
        "6_hubness": p6_hubness(matriz, textos),
    }
    if not saltar_lentas:
        informe["7_determinismo"] = p7_determinismo(textos)
    informe["veredicto"] = _veredicto(informe)
    return informe


def _categorias(textos):
    """Categoria del catalogo por coincidencia de variante, la mas larga gana."""
    with open(rutas.CATALOGO_SINTOMAS, encoding="utf-8") as archivo:
        sintomas = json.load(archivo)["sintomas"]
    tabla = sorted(((v.strip().lower(), d["categoria"])
                    for d in sintomas.values() for v in d["variantes"]),
                   key=lambda par: -len(par[0]))
    salida = []
    for texto in textos:
        bajo = texto.lower()
        salida.append(next((c for v, c in tabla if v in bajo), None))
    return np.array(salida, dtype=object)


def _veredicto(informe):
    """Las condiciones que tienen que cumplirse para que agrupar tenga sentido."""
    e, c = informe["1_estructura"], informe["2_colapso"]
    d, a = informe["3_dimensiones"], informe["4_anisotropia"]
    s, h = informe["5_separacion"], informe["6_hubness"]

    pruebas = [
        ("dimension correcta", e["dimension_ok"]),
        ("sin NaN ni infinitos", e["nan"] == 0 and e["inf"] == 0),
        ("normalizados a 1", e["norma_desvio_max"] < 1e-4),
        ("sin vectores nulos", e["vectores_nulos"] == 0),
        ("sin colapso", c["vectores_repetidos"] == 0),
        ("dimension efectiva > 10", d["dimension_efectiva"] > 10),
        ("no degenerado: 1a componente < 50% de la varianza",
         d["varianza_de_la_1a_componente"] < 0.50),
        ("espacio con rango utilizable: desviacion > 0,05",
         a["desviacion"] > 0.05),
        ("la clinica separa: brecha > 0,02",
         isinstance(s.get("brecha"), float) and s["brecha"] > 0.02),
        ("hubness bajo control: asimetria < 2", h["asimetria"] < 2.0),
    ]
    if "7_determinismo" in informe:
        pruebas.append(("reproducible", informe["7_determinismo"]["identico"]))
    return {"pasadas": sum(1 for _, ok in pruebas if ok),
            "total": len(pruebas),
            "detalle": [(nombre, bool(ok)) for nombre, ok in pruebas]}


def imprimir(informe):
    print(f"\nDIAGNOSTICO DE LOS VECTORES  ({informe['cuando']})")
    print(f"  {informe['modelo']['modelo']}")
    print(f"  {informe['1_estructura']['filas']:,} frases | "
          f"{informe['notas']:,} notas\n")

    for clave in ["1_estructura", "2_colapso", "3_dimensiones",
                  "4_anisotropia", "5_separacion", "6_hubness",
                  "7_determinismo"]:
        if clave not in informe:
            continue
        print(f"{clave.split('_', 1)[1].upper()}")
        for campo, valor in informe[clave].items():
            if campo in ("ejemplos", "mayores_hubs"):
                continue
            print(f"    {campo:34} {valor}")
        print()

    hubs = informe["6_hubness"]["mayores_hubs"]
    print("    los 5 mayores hubs (frase, veces que es vecino):")
    for texto, veces in hubs:
        print(f"      {veces:4}  {texto}")

    v = informe["veredicto"]
    print(f"\nVEREDICTO: {v['pasadas']}/{v['total']}")
    for nombre, ok in v["detalle"]:
        print(f"    [{'OK' if ok else 'FALLA'}] {nombre}")


def main():
    parser = argparse.ArgumentParser(
        description="Control de calidad de los vectores guardados.")
    parser.add_argument("--rapido", action="store_true",
                        help="salta la prueba que recarga el modelo")
    parser.add_argument("--guardar", action="store_true",
                        help="deja el informe en docs/diagnostico.json")
    args = parser.parse_args()

    informe = ejecutar(saltar_lentas=args.rapido)
    imprimir(informe)
    if args.guardar:
        destino = rutas.DOCS / "diagnostico.json"
        destino.write_text(json.dumps(informe, indent=2, ensure_ascii=False,
                                      default=str), encoding="utf-8")
        print(f"\n  -> {destino}")


if __name__ == "__main__":
    main()
