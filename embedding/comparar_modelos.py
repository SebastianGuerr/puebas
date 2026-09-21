"""
Banco de pruebas: cual modelo de embeddings sirve mejor PARA ESTE CORPUS.

POR QUE ESTE ARCHIVO EXISTE
    La eleccion de modelo no se puede tomar leyendo un leaderboard. Los
    leaderboards miden retrieval de documentos largos, casi siempre en ingles.
    Aca el texto es otra cosa: frases canonicas de 6 palabras, en espanol, con
    terminologia clinica. Un modelo puede ser el numero uno de MTEB y separar
    mal "tos" de "malestar general", que es justo lo que este proyecto necesita.

    Asi que se mide. Cuatro modelos, las mismas frases, los mismos numeros.

LOS CUATRO Y POR QUE ESOS CUATRO
    No son los cuatro "mejores" sueltos: son un diseno factorial de 2x2 que
    permite atribuir la diferencia a una causa y no solo constatarla.

                        | generalista        | clinico (metodo SapBERT)
        espanol nativo  |  --                | sapbert_es
        multilingue     | bge_m3, qwen3_06b  | sapbert_xlmr

    Comparando por columnas se responde "el preentrenamiento clinico aporta?".
    Comparando sapbert_es contra sapbert_xlmr se responde "el espanol nativo
    aporta sobre el multilingue, a igual metodo?". La literatura dice que la
    cobertura de idioma pesa mas que el dominio; aca se comprueba o se refuta.

    bge_m3 entra obligatoriamente porque es el modelo que se usa hoy: sin el no
    se puede decir "mejoro", solo "da estos numeros".

LAS TRES PRUEBAS
    A  CATALOGO (etiquetas duras). catalogo_sintomas.json trae 82 conceptos
       canonicos con 393 variantes de escritura y 18 categorias. Que dos
       variantes del mismo concepto queden juntas es la definicion misma de un
       buen embedding clinico, y aca esta etiquetado sin trabajo humano nuevo.

    B  DATOS REALES (etiquetas debiles). Las frases de
       nota_triage.frase_procesada, con la categoria que les asigna el
       catalogo por coincidencia de variante. Es
       ruidoso, pero es el texto que de verdad se va a vectorizar.
       Dentro de B, la metrica que manda es auc_respiratorio: el desenlace
       intermedio de toda la tesis es la serie respiratoria, y un modelo que no
       separa lo respiratorio del resto no sirve por bueno que sea en lo demas.

    C  COSTE. Sin GPU, sobre los hilos de torch que haya. Un modelo que gana por
       dos puntos y tarda seis veces mas puede no compensar sobre 94.000 notas.

LAS FRASES SE CONGELAN
    nota_triage crece mientras esto corre. Si cada modelo viera un corpus
    distinto, la comparacion no valdria nada. La primera corrida congela
    el set en salidas/banco_frases.csv y las demas lo reusan. Para rehacerlo
    cuando haya mas datos: --congelar.

USO
    python -m embedding.comparar_modelos --modelo sapbert_es
    python -m embedding.comparar_modelos --tabla        # compara lo que haya
    python -m embedding.comparar_modelos --congelar     # rehace el set de frases
"""

import argparse
import json
import platform
import time
from datetime import datetime

import numpy as np
import pandas as pd

from embedding import rutas

# ==========================================================
# CONFIGURACION
# ==========================================================

# Ventana igual para todos: comparar modelos con ventanas distintas mide la
# ventana, no el modelo. 128 es la misma que usa modelo.py en produccion.
LONGITUD_MAXIMA = 128
LOTE = 32

MODELOS = {
    "sapbert_es": {
        "repo": "BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es",
        "motor": "transformers",          # no es sentence-transformers
        "pooling": "cls",                 # asi lo indica su tarjeta de modelo
        "familia": "clinico espanol",
    },
    "sapbert_xlmr": {
        "repo": "cambridgeltl/SapBERT-UMLS-2020AB-all-lang-from-XLMR",
        "motor": "transformers",
        "pooling": "cls",
        "familia": "clinico multilingue",
    },
    "bge_m3": {
        "repo": "BAAI/bge-m3",
        "motor": "sentence_transformers",
        "familia": "generalista multilingue (el actual)",
    },
    "qwen3_06b": {
        "repo": "Qwen/Qwen3-Embedding-0.6B",
        "motor": "sentence_transformers",
        "familia": "generalista multilingue",
    },
}

BANCO_FRASES = rutas.BANCO_FRASES


def ruta_resultado(clave):
    """
    Los resultados van a la raiz del paquete a peticion expresa: se quieren ver
    los cuatro de un vistazo, al lado del codigo que los produjo.
    """
    return rutas.PAQUETE / f"resultado_{clave}.json"


# ==========================================================
# LOS DATOS
# ==========================================================

def leer_catalogo():
    """Las variantes del catalogo con su concepto canonico y su categoria."""
    with open(rutas.CATALOGO_SINTOMAS, encoding="utf-8") as archivo:
        sintomas = json.load(archivo)["sintomas"]

    filas = []
    for canonico, dato in sintomas.items():
        for variante in dato["variantes"]:
            filas.append({"texto": variante.strip().lower(),
                          "concepto": canonico,
                          "categoria": dato["categoria"]})
    return (pd.DataFrame(filas)
            .drop_duplicates(subset="texto")
            .reset_index(drop=True))


def etiquetar(textos, sintomas):
    """
    Categoria por coincidencia de variante, gana la variante mas larga.

    Es el mismo criterio de FlashText que usa el catalogo: 'dolor abdominal'
    tiene que ganarle a 'dolor'. Sin eso casi todo caeria en 'inespecifico'.
    """
    tabla = []
    for canonico, dato in sintomas.items():
        for variante in dato["variantes"]:
            tabla.append((variante.strip().lower(), canonico, dato["categoria"]))
    tabla.sort(key=lambda fila: -len(fila[0]))

    conceptos, categorias = [], []
    for texto in textos:
        bajo = str(texto).lower()
        hallado = (None, None)
        for variante, canonico, categoria in tabla:
            if variante in bajo:
                hallado = (canonico, categoria)
                break
        conceptos.append(hallado[0])
        categorias.append(hallado[1])
    return conceptos, categorias


def congelar():
    """Fija el set de frases reales para que los 4 modelos vean lo mismo."""
    from embedding import almacen

    con = almacen.abrir(solo_lectura=True)
    try:
        df = con.execute(
            "SELECT OID, frase_procesada FROM nota_triage").df()
    finally:
        con.close()

    texto = df["frase_procesada"].fillna("").astype(str).str.strip().str.lower()
    util = df.loc[texto != ""].copy()
    util["texto"] = texto[texto != ""]

    # Se vectoriza por texto distinto, no por nota: es lo que hace el paquete
    # en produccion y es lo que hay que cronometrar.
    distintos = util.drop_duplicates(subset="texto")[["OID", "texto"]]

    with open(rutas.CATALOGO_SINTOMAS, encoding="utf-8") as archivo:
        sintomas = json.load(archivo)["sintomas"]
    conceptos, categorias = etiquetar(distintos["texto"].tolist(), sintomas)
    distintos = distintos.assign(concepto=conceptos, categoria=categorias)

    distintos.to_csv(BANCO_FRASES, index=False, encoding="utf-8")
    cubiertas = int(distintos["categoria"].notna().sum())
    print(f"  congelado: {len(util):,} notas -> {len(distintos):,} frases "
          f"distintas, {cubiertas:,} con categoria "
          f"({100 * cubiertas / len(distintos):.1f}%)")
    return distintos


def banco_real():
    if not BANCO_FRASES.exists():
        print("  no habia set congelado, lo creo ahora")
        return congelar()
    return pd.read_csv(BANCO_FRASES)


# ==========================================================
# LOS MODELOS
# ==========================================================

def vectorizar(clave, textos):
    """Devuelve (matriz normalizada, segundos, metadatos del modelo)."""
    config = MODELOS[clave]
    import torch

    if config["motor"] == "sentence_transformers":
        from sentence_transformers import SentenceTransformer
        modelo = SentenceTransformer(config["repo"], device="cpu",
                                     trust_remote_code=True)
        modelo.max_seq_length = LONGITUD_MAXIMA
        parametros = sum(p.numel() for p in modelo.parameters())
        inicio = time.perf_counter()
        matriz = modelo.encode(textos, batch_size=LOTE,
                               normalize_embeddings=True,
                               show_progress_bar=False,
                               convert_to_numpy=True)
        segundos = time.perf_counter() - inicio
        tokenizador = modelo.tokenizer
    else:
        from transformers import AutoModel, AutoTokenizer
        tokenizador = AutoTokenizer.from_pretrained(config["repo"])
        modelo = AutoModel.from_pretrained(config["repo"]).eval()
        parametros = sum(p.numel() for p in modelo.parameters())

        trozos = []
        inicio = time.perf_counter()
        with torch.no_grad():
            for i in range(0, len(textos), LOTE):
                entrada = tokenizador(textos[i:i + LOTE], padding=True,
                                      truncation=True,
                                      max_length=LONGITUD_MAXIMA,
                                      return_tensors="pt")
                salida = modelo(**entrada).last_hidden_state
                # CLS: es el pooling que declara la tarjeta de SapBERT. Con
                # mean-pooling los numeros bajan y no seria el modelo que sus
                # autores evaluaron.
                trozos.append(salida[:, 0, :].numpy())
        segundos = time.perf_counter() - inicio
        matriz = np.vstack(trozos)
        matriz /= np.linalg.norm(matriz, axis=1, keepdims=True) + 1e-12

    matriz = np.ascontiguousarray(matriz, dtype=np.float32)
    largos = [len(tokenizador.encode(texto)) for texto in textos]
    meta = {
        "repo": config["repo"],
        "familia": config["familia"],
        "parametros": int(parametros),
        "dimension": int(matriz.shape[1]),
        "tokens_mediana": float(np.median(largos)),
        "tokens_max": int(max(largos)),
        "truncados": int(sum(1 for largo in largos if largo > LONGITUD_MAXIMA)),
    }
    return matriz, segundos, meta


# ==========================================================
# LAS METRICAS
# ==========================================================

def _similitud(matriz):
    """Coseno contra todos. Vectores normalizados -> es el producto punto."""
    sim = matriz @ matriz.T
    np.fill_diagonal(sim, -np.inf)   # nadie es su propio vecino
    return sim


def _con_pares(etiquetas):
    """Mascara de las filas cuya etiqueta existe y aparece al menos dos veces."""
    serie = pd.Series(etiquetas)
    conteo = serie.value_counts()
    return (serie.notna() & (serie.map(conteo).fillna(0) >= 2)).to_numpy()


def vecino_mas_cercano(sim, etiquetas):
    """% de frases cuyo vecino 1 comparte etiqueta."""
    etiquetas = np.asarray(etiquetas, dtype=object)
    valida = _con_pares(etiquetas)
    if valida.sum() == 0:
        return None, 0
    vecino = sim[valida].argmax(axis=1)
    acierto = etiquetas[vecino] == etiquetas[valida]
    return float(acierto.mean()), int(valida.sum())


def pureza_knn(sim, etiquetas, k=5):
    """Fraccion media de los k vecinos que comparten etiqueta."""
    etiquetas = np.asarray(etiquetas, dtype=object)
    valida = _con_pares(etiquetas)
    if valida.sum() < k + 1:
        return None, int(valida.sum())
    sub = sim[np.ix_(valida, valida)]
    etq = etiquetas[valida]
    vecinos = np.argsort(-sub, axis=1)[:, :k]
    return float((etq[vecinos] == etq[:, None]).mean()), int(valida.sum())


def map_concepto(sim, conceptos):
    """MAP: los otros sinonimos del mismo concepto, cuan arriba quedan."""
    conceptos = np.asarray(conceptos, dtype=object)
    valida = _con_pares(conceptos)
    if valida.sum() == 0:
        return None
    precisiones = []
    for i in np.flatnonzero(valida):
        orden = np.argsort(-sim[i])
        posiciones = np.flatnonzero(conceptos[orden] == conceptos[i])
        if len(posiciones) == 0:
            continue
        precisiones.append(np.mean([(j + 1) / (p + 1)
                                    for j, p in enumerate(posiciones)]))
    return float(np.mean(precisiones)) if precisiones else None


def auc_respiratorio(matriz, categorias):
    """
    Cuan bien separa lo respiratorio del resto. Centroide dejando fuera al
    propio punto: si no, cada positivo se ayuda a si mismo e infla el AUC.
    """
    from sklearn.metrics import roc_auc_score
    categorias = np.asarray(categorias, dtype=object)
    etiquetado = pd.notna(categorias)
    if etiquetado.sum() < 10:
        return None, 0
    positivo = (categorias == "respiratorio") & etiquetado
    n = int(positivo.sum())
    if n < 3 or n == int(etiquetado.sum()):
        return None, n

    suma = matriz[positivo].sum(axis=0)
    puntajes = np.empty(len(matriz))
    for i in range(len(matriz)):
        centro = (suma - matriz[i]) if positivo[i] else suma
        centro = centro / ((n - 1) if positivo[i] else n)
        centro = centro / (np.linalg.norm(centro) + 1e-12)
        puntajes[i] = matriz[i] @ centro
    return float(roc_auc_score(positivo[etiquetado], puntajes[etiquetado])), n


def silueta(matriz, etiquetas):
    from sklearn.metrics import silhouette_score
    etiquetas = np.asarray(etiquetas, dtype=object)
    valida = _con_pares(etiquetas)
    if valida.sum() < 10 or len(set(etiquetas[valida])) < 2:
        return None
    return float(silhouette_score(matriz[valida],
                                  etiquetas[valida].astype(str),
                                  metric="cosine"))


# ==========================================================
# LA CORRIDA
# ==========================================================

def correr(clave):
    cat = leer_catalogo()
    real = banco_real()
    print(f"\n{clave}  ({MODELOS[clave]['repo']})")
    print(f"  catalogo: {len(cat)} variantes | reales: {len(real)} frases")

    textos = cat["texto"].tolist() + real["texto"].astype(str).tolist()
    print(f"  vectorizando {len(textos)} frases en CPU...", flush=True)
    matriz, segundos, meta = vectorizar(clave, textos)
    corte = len(cat)
    mat_cat, mat_real = matriz[:corte], matriz[corte:]
    print(f"  {segundos:.1f} s  ({len(textos) / segundos:.1f} frases/s)")

    sim_cat = _similitud(mat_cat)
    sim_real = _similitud(mat_real)

    vec_concepto, n_concepto = vecino_mas_cercano(sim_cat, cat["concepto"].tolist())
    vec_categoria, _ = vecino_mas_cercano(sim_cat, cat["categoria"].tolist())
    pureza, n_pureza = pureza_knn(sim_real, real["categoria"].tolist(), k=5)
    auc, n_resp = auc_respiratorio(mat_real, real["categoria"].tolist())
    mapc = map_concepto(sim_cat, cat["concepto"].tolist())

    resultado = {
        "clave": clave,
        "modelo": meta,
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "maquina": {"plataforma": platform.platform(), "gpu": False},
        "config": {"longitud_maxima": LONGITUD_MAXIMA, "lote": LOTE},
        "datos": {"variantes_catalogo": len(cat), "frases_reales": len(real),
                  "reales_con_categoria": int(real["categoria"].notna().sum())},
        "A_catalogo": {
            "vecino1_mismo_concepto": vec_concepto, "n": n_concepto,
            "map_concepto": mapc,
            "vecino1_misma_categoria": vec_categoria,
            "silueta_categoria": silueta(mat_cat, cat["categoria"].tolist()),
        },
        "B_reales": {
            "pureza_knn5_categoria": pureza, "n": n_pureza,
            "auc_respiratorio": auc, "n_respiratorio": n_resp,
            "silueta_categoria": silueta(mat_real, real["categoria"].tolist()),
        },
        "C_coste": {
            "segundos": round(segundos, 2),
            "frases_por_segundo": round(len(textos) / segundos, 2),
            "segundos_por_1000": round(1000 * segundos / len(textos), 1),
            "proyeccion_40k_frases_min": round(
                40000 * segundos / len(textos) / 60, 1),
        },
    }

    destino = ruta_resultado(clave)
    destino.write_text(json.dumps(resultado, indent=2, ensure_ascii=False),
                       encoding="utf-8")
    print(f"  -> {destino.name}")
    for nombre, valor in [("vecino1 concepto", vec_concepto),
                          ("MAP concepto", mapc),
                          ("pureza knn5 real", pureza),
                          ("AUC respiratorio", auc)]:
        print(f"     {nombre:22} {valor if valor is None else round(valor, 4)}")
    return resultado


def tabla():
    filas = []
    for clave in MODELOS:
        destino = ruta_resultado(clave)
        if not destino.exists():
            print(f"  falta {destino.name}")
            continue
        r = json.loads(destino.read_text(encoding="utf-8"))
        filas.append({
            "modelo": clave,
            "dim": r["modelo"]["dimension"],
            "M_param": round(r["modelo"]["parametros"] / 1e6),
            "vec1_concepto": r["A_catalogo"]["vecino1_mismo_concepto"],
            "MAP_concepto": r["A_catalogo"]["map_concepto"],
            "vec1_categoria": r["A_catalogo"]["vecino1_misma_categoria"],
            "sil_cat": r["A_catalogo"]["silueta_categoria"],
            "knn5_real": r["B_reales"]["pureza_knn5_categoria"],
            "AUC_resp": r["B_reales"]["auc_respiratorio"],
            "frases_s": r["C_coste"]["frases_por_segundo"],
            "40k_min": r["C_coste"]["proyeccion_40k_frases_min"],
        })
    if not filas:
        print("  no hay resultados todavia")
        return
    print()
    print(pd.DataFrame(filas).set_index("modelo").to_string(
        float_format=lambda x: f"{x:.4f}"))


def main():
    parser = argparse.ArgumentParser(
        description="Compara modelos de embedding sobre este corpus.")
    parser.add_argument("--modelo", choices=list(MODELOS))
    parser.add_argument("--congelar", action="store_true",
                        help="rehace el set de frases reales desde el CSV")
    parser.add_argument("--tabla", action="store_true",
                        help="imprime la comparacion de lo ya corrido")
    args = parser.parse_args()

    if args.congelar:
        congelar()
    elif args.tabla:
        tabla()
    elif args.modelo:
        correr(args.modelo)
    else:
        parser.error("indica --modelo, --congelar o --tabla")


if __name__ == "__main__":
    main()
