"""
El modelo de embeddings y sus parametros. Un solo sitio decide con que se
vectoriza, porque de eso depende que una matriz vieja siga siendo comparable
con una nueva.

POR QUE bge-m3
    Es multilingue de verdad (no ingles con espanol de propina), maneja bien el
    texto corto y devuelve vectores de 1024 dimensiones normalizados, que es lo
    que quiere el coseno del clustering.

POR QUE LONGITUD_MAXIMA = 128 Y NO LOS 8192 QUE TRAE DE FABRICA
    Es el ajuste que mas tiempo ahorra en toda la fase. El costo de un
    transformer crece con el cuadrado de la longitud, asi que dejar la ventana
    en 8192 se paga aunque el texto sea de seis palabras.

    Medido sobre la columna texto_embedding de la corrida de 28.095 notas:
    mediana 6 palabras, percentil 95 en 47 y el maximo en 60. Con 128 tokens
    entra el peor caso entero y sobra sitio. Ese margen existe gracias a la
    fase 5 de NLP/: sobre texto_normalizado, que llega a 405 palabras, este
    numero tendria que ser bastante mas alto.

    Si algun dia se vectoriza una columna mas larga, hay que subirlo, y como
    entra en la identidad del modelo, la matriz vieja deja de valer sola.

SIN GPU
    torch esta instalado en su version +cpu, asi que esto corre sobre los 8
    nucleos de la maquina. No es un problema para arrancar, pero es la razon de
    que el paquete entero este pensado para no repetir trabajo: deduplicar,
    apender y poder reanudar no son adornos aca, son lo que hace viable correr
    la tabla completa.
"""

import os

import numpy as np

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

MODELO = "BAAI/bge-m3"

# Ventana en tokens. Ver el porque en el docstring de arriba.
LONGITUD_MAXIMA = 128

# Vectores de norma 1: con eso el producto punto ES el coseno, que es la
# metrica con la que despues se agrupan.
NORMALIZAR = True

# Cuantos textos entran de una al modelo. Sube el uso de RAM, no el resultado.
LOTE = 64

# float32 en vez de float64: la mitad de disco y de RAM, y el modelo no produce
# mas precision que esa de todos modos.
TIPO = np.float32


def identidad():
    """
    Como se lleno la matriz. Va al manifiesto y se compara contra el de una
    corrida anterior antes de apender.

    Cambiar cualquiera de estos valores produce vectores que no viven en el
    mismo espacio que los guardados, y mezclarlos daria clusters sin sentido.
    Por eso vectorizar.py se niega a continuar si no coinciden, en vez de
    confiar en que alguien se acuerde de borrar la carpeta.
    """
    return {
        "modelo": MODELO,
        "longitud_maxima": LONGITUD_MAXIMA,
        "normalizado": NORMALIZAR,
        "tipo": np.dtype(TIPO).name,
    }


def cargar():
    """
    Trae bge-m3 a memoria y le fija la ventana. La primera vez lo descarga de
    Hugging Face (unos 2 GB) y lo deja en la cache local; las siguientes lo lee
    de ahi.

    Devuelve la pareja (modelo, dimension).
    """
    import torch
    from sentence_transformers import SentenceTransformer

    dispositivo = "cuda" if torch.cuda.is_available() else "cpu"
    if dispositivo == "cpu":
        # Sin esto torch se queda en la mitad de los nucleos en algunas
        # instalaciones de Windows.
        torch.set_num_threads(os.cpu_count() or 4)

    modelo = SentenceTransformer(MODELO, device=dispositivo)
    modelo.max_seq_length = LONGITUD_MAXIMA

    dimension = modelo.get_sentence_embedding_dimension()
    print(f"  modelo   : {MODELO}")
    print(f"  dispositivo: {dispositivo} ({os.cpu_count()} nucleos)")
    print(f"  ventana  : {LONGITUD_MAXIMA} tokens | dimension: {dimension}")
    return modelo, dimension


def codificar(modelo, textos, progreso=False):
    """
    Vectoriza una lista de textos y devuelve la matriz en TIPO.

    No deduplica ni ordena: eso ya lo hizo corpus.py. Aca solo se le pasa al
    modelo lo que haya que pasarle.
    """
    matriz = modelo.encode(
        list(textos),
        batch_size=LOTE,
        normalize_embeddings=NORMALIZAR,
        show_progress_bar=progreso,
        convert_to_numpy=True,
    )
    return np.ascontiguousarray(matriz, dtype=TIPO)
