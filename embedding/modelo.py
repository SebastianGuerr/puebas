"""
El modelo de embeddings y sus parametros. Un solo sitio decide con que se
vectoriza, porque de eso depende que una matriz vieja siga siendo comparable
con una nueva.

POR QUE SapBERT-es Y NO bge-m3
    Se midio. Los cuatro candidatos, las mismas 787 frases, el 2026-09-21. La
    tabla completa y el metodo estan en docs/MODELO.md; el resumen:

        modelo         vec1_concepto  MAP   AUC_resp  frases/s
        sapbert_es         0.877     0.572    0.827     24.8
        sapbert_xlmr       0.787     0.441    0.786     19.7
        bge_m3 (antes)     0.733     0.344    0.744      6.5
        qwen3_06b          0.656     0.315    0.674      4.4
        (piso lexico)      0.627     0.262      --        --

    Gana en calidad Y en velocidad, con la cuarta parte de los parametros del
    que sustituye. El orden sale exactamente inverso al tamano del modelo, que
    es la senal de que aqui no manda la escala sino el ajuste a la tarea:
    SapBERT se entrena con contraste sobre pares de sinonimos de UMLS, que es
    literalmente el problema de este corpus -- decidir si dos frases cortas
    nombran el mismo concepto clinico.

    'piso lexico' es TF-IDF de n-gramas de caracteres, sin semantica ninguna.
    Esta en la tabla porque un modelo que no le gane no esta aportando nada, y
    porque tres de los cuatro candidatos no le ganaban en la prueba sobre datos
    reales. Ver docs/MODELO.md, seccion sobre la fuga lexica.

NO ES UN MODELO DE sentence-transformers
    Su tarjeta indica tomar el token CLS de la ultima capa, no hacer media de
    tokens. Con mean-pooling los numeros bajan y ademas no seria el modelo que
    sus autores evaluaron. Por eso aqui se usa transformers directamente en vez
    de SentenceTransformer.

POR QUE LONGITUD_MAXIMA = 128
    El coste de un transformer crece con el cuadrado de la longitud, asi que la
    ventana no se deja en su maximo por si acaso.

    OJO: CONTAR PALABRAS NO ES CONTAR TOKENS, Y AQUI YA SE FALLO UNA VEZ
        La version anterior de este parrafo decia "mediana 6 palabras, maximo
        24, o sea unos 50 tokens". Medido de verdad con el tokenizador del
        modelo sobre las 452 frases del almacen el 2026-09-21:

            mediana 8 tokens | p95 20 | p99 61 | maximo 131

        La mediana casi coincide, pero la cola no: el maximo real es cinco
        veces el estimado, porque el modelo de NLP/ a veces devuelve una frase
        larga en vez de una canonica (la mas larga tiene 113 palabras y
        enumera seis sintomas). Estimar tokens multiplicando palabras es
        justo lo que produce este error.

    La decision se sostiene: con 128 se trunca 1 frase de 452 (0,22%), y por
    tres tokens. Pero ya no sobra sitio, asi que la columna 'tokens' del
    almacen guarda el largo real de cada frase y vectorizar.py avisa en cada
    corrida cuantas se truncaron, en vez de confiar en este parrafo.

    Ese margen lo da la columna, no la suerte: frase_procesada es la frase
    canonica que genera el modelo de NLP/, no la nota. Sobre la nota entera
    (frase_original) habria que subirlo bastante.

SIN GPU
    torch esta instalado en su version +cpu. A 24,8 frases/s medidas, las
    ~40.000 frases distintas que se esperan del corpus completo son unos 27
    minutos. Con bge-m3 eran 103. Eso deja de ser un obstaculo para rehacer el
    almacen cuando haga falta, que es justo lo que permite iterar.
"""

import numpy as np

# ==========================================================
# CONFIGURACION -- lo unico que hay que editar
# ==========================================================

MODELO = "BSC-NLP4BIA/SapBERT-from-roberta-base-biomedical-clinical-es"

# Ventana en tokens. Ver el porque en el docstring de arriba.
LONGITUD_MAXIMA = 128

# La dimension de salida. Se declara aqui porque la tabla del almacen se crea
# con el tipo FLOAT[DIMENSION] y hay que saberla antes de cargar el modelo.
# vectorizar.py comprueba que el modelo real coincida con este numero.
DIMENSION = 768

# Cuantas frases por pasada del modelo. Sobre CPU, subirlo mucho no acelera y
# si dispara la memoria por el relleno de los lotes.
LOTE = 32

# Los vectores se guardan normalizados a norma 1, para que la similitud coseno
# sea un producto punto y el clustering no tenga que normalizar nada.
NORMALIZADO = True


def identidad():
    """
    Lo que tiene que coincidir para que dos vectores sean comparables.

    Entra tal cual en el almacen. Si el almacen guarda una identidad distinta
    de esta, vectorizar.py se niega a continuar en vez de mezclar vectores que
    viven en espacios distintos y producir una matriz mitad y mitad -- un fallo
    que no da ningun error y solo se nota en que el clustering sale raro.
    """
    return {
        "modelo": MODELO,
        "pooling": "cls",
        "longitud_maxima": LONGITUD_MAXIMA,
        "dimension": DIMENSION,
        "normalizado": NORMALIZADO,
        "tipo": "float32",
    }


class Codificador:
    """
    El modelo cargado. Se instancia una vez y se reusa: traerlo a memoria es la
    parte cara cuando hay pocas frases nuevas que vectorizar.
    """

    def __init__(self):
        from transformers import AutoModel, AutoTokenizer

        self.tokenizador = AutoTokenizer.from_pretrained(MODELO)
        self.red = AutoModel.from_pretrained(MODELO).eval()

        real = int(self.red.config.hidden_size)
        if real != DIMENSION:
            raise SystemExit(
                f"{MODELO} devuelve {real} dimensiones y modelo.DIMENSION dice "
                f"{DIMENSION}. Corrige la constante: la tabla del almacen se "
                f"crea con ese tipo y no se puede cambiar sin rehacerla.")

    def codificar(self, textos, al_terminar_lote=None):
        """
        Devuelve (matriz float32 normalizada, cuantos textos se truncaron).

        al_terminar_lote recibe cuantos van, para poder informar del avance sin
        que este modulo sepa nada de como se informa.
        """
        import torch

        trozos, truncados = [], 0
        with torch.no_grad():
            for inicio in range(0, len(textos), LOTE):
                lote = textos[inicio:inicio + LOTE]
                entrada = self.tokenizador(
                    lote, padding=True, truncation=True,
                    max_length=LONGITUD_MAXIMA, return_tensors="pt")
                truncados += sum(
                    1 for texto in lote
                    if len(self.tokenizador.encode(texto)) > LONGITUD_MAXIMA)
                salida = self.red(**entrada).last_hidden_state
                # CLS, no media de tokens: lo dice la tarjeta del modelo.
                trozos.append(salida[:, 0, :].numpy())
                if al_terminar_lote:
                    al_terminar_lote(min(inicio + LOTE, len(textos)))

        matriz = np.vstack(trozos).astype(np.float32)
        if NORMALIZADO:
            matriz /= np.linalg.norm(matriz, axis=1, keepdims=True) + 1e-12
        return np.ascontiguousarray(matriz, dtype=np.float32), truncados
