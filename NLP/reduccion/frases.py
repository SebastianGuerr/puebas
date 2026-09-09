"""
Clasificador de tramos: decidir si una frase habla del paciente o del servicio.

QUÉ PROBLEMA RESUELVE, Y POR QUÉ NO LO RESUELVE UN PATRÓN MÁS
    reduccion.py quita lo que sobra de la nota con una lista de expresiones
    regulares: el bloque institucional, el examen físico, la conducta, el
    acompañante, el modo de llegada, el preámbulo temporal, los topónimos. Cada
    una tapa los casos que alguien enumeró, y se escapa el siguiente. Es el
    mismo techo que tienen las listas negras de siglas, y por la misma razón:
    enumerar no generaliza.

    Y hay mucho que enumerar. Lo que sobra son frases estereotipadas que se
    repiten casi iguales en miles de notas, pero 'casi iguales' no es 'iguales':
    en cuanto una sede cambia la redacción de su aviso, el patrón deja de
    encajar y el bloque vuelve al texto del embedding.

LA IDEA
    Una frase administrativa y una frase de paciente no se distinguen por sus
    palabras exactas sino por de qué hablan, y eso es justo lo que mide un
    codificador de frases. Se representa cada tramo como un vector y se entrena
    un clasificador pequeño encima. Lo que aprende no es la lista de frases:
    es la diferencia entre las dos poblaciones.

DE DÓNDE SALEN LAS ETIQUETAS
    De las propias reglas que ya existen. Los patrones de reduccion.py tienen
    mala cobertura pero buena precisión: cuando encajan, aciertan. Sirven
    entonces como etiquetador débil para construir el conjunto de entrenamiento
    sin etiquetar nada a mano, y el clasificador generaliza más allá de ellos.

    Los tramos en los que ninguna regla se moja quedan SIN etiqueta y no entran
    a entrenar. Entrenar sobre una etiqueta dudosa enseña la duda.

    El conjunto se escribe en datos/frases_etiquetadas.csv, que se versiona y se
    corrige a mano: es la forma de mejorar el clasificador sin tocar el código.

POR QUÉ ESTE CODIFICADOR Y NO bge-m3
    El proyecto ya tiene descargado 'roberta-base-biomedical-clinical-es', que
    usa la capa de contexto. Medido en esta máquina, sobre CPU:

        roberta-clinico   76 frases/s   ->  8,9 min para los 40.602 tramos
        bge-m3            15 frases/s   -> 46,0 min

    Cinco veces más rápido, ya está en disco, y está entrenado sobre historias
    clínicas en español, que es exactamente este dominio. bge-m3 se reserva para
    la fase de embeddings, donde hace falta un espacio multilingüe.

QUÉ HACE Y QUÉ NO
    Marca tramos, no los borra. Quien decide qué se quita es reduccion.py, y
    solo quita un tramo cuando el clasificador está seguro. Ante la duda se
    conserva, que es la asimetría de coste de todo el proyecto: arrastrar una
    frase administrativa es barato, perder el motivo de consulta no lo es.
"""

import csv
import re

from NLP import rutas

# ==========================================================
# CONFIGURACION
# ==========================================================

MODELO = "PlanTL-GOB-ES/roberta-base-biomedical-clinical-es"

# Los tramos de una nota de triage se separan por punto, punto y coma Y COMA.
# La coma es imprescindible: la nota típica del corpus es una frase corrida sin
# un solo punto, y separando solo por punto el 'tramo' es la nota entera.
RE_TRAMO = re.compile(r"\s*[.;,]\s*")

PALABRAS_MINIMAS = 2      # un tramo de una palabra no da señal suficiente
MAX_LONGITUD = 64         # subtokens; un tramo mas largo se trunca

# Probabilidad a partir de la cual se da un tramo por administrativo. Alto a
# proposito: por debajo se conserva, porque el coste de los dos errores no es
# el mismo.
UMBRAL_BUROCRATICO = 0.85

BUROCRATICO = "burocratico"
CLINICO = "clinico"

_TOK = None
_MOD = None
_CLF = None
_DISPONIBLE = None


def segmentos(texto):
    """Los tramos de una nota, ya limpios y sin los demasiado cortos."""
    return [s.strip() for s in RE_TRAMO.split(str(texto or ""))
            if len(s.split()) >= PALABRAS_MINIMAS]


# ==========================================================
# ETIQUETADO DEBIL
# ==========================================================

def etiquetar_debil(tramo):
    """
    La etiqueta que dan las reglas actuales, o None si ninguna se moja.

    Las reglas de reduccion.py deciden 'burocratico' y el léxico clínico curado
    de la depuracion decide 'clinico'. Cuando ambas cosas ocurren a la vez el
    tramo es ambiguo -- una frase de conducta que menciona un síntoma -- y se
    devuelve None: es justo el caso que el clasificador tiene que aprender a
    resolver, y no se le puede enseñar con una etiqueta inventada.
    """
    from NLP.depuracion import depuracion
    from NLP.reduccion import reduccion

    bajo = tramo.lower()
    patrones = (reduccion.RE_EXAMEN, reduccion.RE_CONDUCTA, reduccion.RE_TRAMITE,
                reduccion.RE_ACOMPANANTE, reduccion.RE_LLEGADA,
                reduccion.RE_ANTECEDENTES, reduccion.RE_PLURIPATOLOGIA)
    burocratico = (any(m in bajo for m in reduccion.MARCADORES_INSTITUCIONALES)
                   or any(p.search(tramo) for p in patrones))

    clinico = bool(depuracion.terminos_clinicos(tramo)
                   or depuracion.frases_clinicas(tramo))

    if burocratico and not clinico:
        return BUROCRATICO
    if clinico and not burocratico:
        return CLINICO
    return None


def construir_datos(csv_entrada=None, salida=None, columna="texto_normalizado"):
    """
    Escribe el conjunto de entrenamiento a partir del corpus ya procesado.

    Recorre las notas, parte en tramos, etiqueta con las reglas y guarda un
    tramo distinto por fila. Devuelve (n_burocraticos, n_clinicos, n_sin_etiqueta).

    El archivo va a datos/ y no a salidas/ a propósito: en cuanto alguien
    corrige una etiqueta a mano, deja de ser regenerable y pasa a ser trabajo
    humano que no se puede perder.
    """
    import pandas as pd

    csv_entrada = csv_entrada or rutas.TRIAGE_LIMPIO
    salida = salida or rutas.FRASES_ETIQUETADAS

    df = pd.read_csv(csv_entrada).fillna("")
    if columna not in df.columns:
        columna = "texto_corregido"

    vistos, filas = set(), []
    conteo = {BUROCRATICO: 0, CLINICO: 0, None: 0}
    for texto in df[columna]:
        for tramo in segmentos(texto):
            clave = tramo.lower()
            if clave in vistos:
                continue
            vistos.add(clave)
            etiqueta = etiquetar_debil(tramo)
            conteo[etiqueta] += 1
            if etiqueta:
                filas.append((etiqueta, tramo))

    with open(salida, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, quoting=csv.QUOTE_ALL)
        w.writerow(["etiqueta", "tramo"])
        w.writerows(sorted(filas))

    return conteo[BUROCRATICO], conteo[CLINICO], conteo[None]


# ==========================================================
# CODIFICACION
# ==========================================================

def _cargar_codificador():
    """Carga el codificador una vez. None si faltan transformers o torch."""
    global _TOK, _MOD
    if _MOD is not None:
        return _MOD
    try:
        import torch
        from transformers import AutoModel, AutoTokenizer
    except ModuleNotFoundError:
        print("Aviso: faltan transformers/torch; el clasificador de tramos queda desactivado.")
        return None
    try:
        _TOK = AutoTokenizer.from_pretrained(MODELO)
        _MOD = AutoModel.from_pretrained(MODELO)
        _MOD.eval()
        torch.set_num_threads(4)
    except Exception as exc:
        print(f"Aviso: no se pudo cargar {MODELO} ({exc}).")
        return None
    return _MOD


def vectorizar(tramos, lote=32):
    """
    Representa cada tramo como un vector, promediando los estados del
    codificador sobre los tokens reales.

    Se promedia sobre la máscara y no se toma el primer token porque este
    modelo no tiene un vector de frase entrenado: su 'pooler' sale sin
    inicializar, y usarlo sería leer ruido.
    """
    import numpy as np
    import torch

    if _cargar_codificador() is None:
        return None

    salida = []
    for i in range(0, len(tramos), lote):
        trozo = [str(t) for t in tramos[i:i + lote]]
        entrada = _TOK(trozo, padding=True, truncation=True,
                       max_length=MAX_LONGITUD, return_tensors="pt")
        with torch.no_grad():
            estados = _MOD(**entrada).last_hidden_state
        mascara = entrada["attention_mask"].unsqueeze(-1)
        vector = (estados * mascara).sum(1) / mascara.sum(1).clamp(min=1)
        salida.append(vector.numpy())
    return np.vstack(salida)


# ==========================================================
# ENTRENAMIENTO
# ==========================================================

def entrenar(datos=None, modelo=None, semilla=0):
    """
    Entrena el clasificador sobre el conjunto etiquetado y lo guarda.

    Devuelve un diccionario con las métricas sobre la parte reservada, que es
    lo único que dice si sirve. Se reserva un 20% estratificado y NO se toca
    para entrenar.
    """
    import joblib
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import classification_report
    from sklearn.model_selection import train_test_split

    datos = datos or rutas.FRASES_ETIQUETADAS
    modelo = modelo or rutas.CLASIFICADOR_FRASES

    df = pd.read_csv(datos).fillna("")
    X_txt, y = df["tramo"].tolist(), (df["etiqueta"] == BUROCRATICO).astype(int)

    tr_txt, te_txt, y_tr, y_te = train_test_split(
        X_txt, y, test_size=0.2, random_state=semilla, stratify=y)

    X_tr = vectorizar(tr_txt)
    if X_tr is None:
        return None
    X_te = vectorizar(te_txt)

    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    clf.fit(X_tr, y_tr)
    joblib.dump(clf, modelo)

    return {
        "entrenamiento": len(tr_txt),
        "reservado": len(te_txt),
        "informe": classification_report(
            y_te, clf.predict(X_te), target_names=[CLINICO, BUROCRATICO], digits=3),
        "modelo": str(modelo),
    }


# ==========================================================
# USO
# ==========================================================

def disponible():
    """True si hay un clasificador entrenado y el codificador se pudo cargar."""
    global _CLF, _DISPONIBLE
    if _DISPONIBLE is not None:
        return _DISPONIBLE
    ruta = rutas.CLASIFICADOR_FRASES
    if not ruta.exists() or _cargar_codificador() is None:
        _DISPONIBLE = False
        return False
    try:
        import joblib
        _CLF = joblib.load(ruta)
        _DISPONIBLE = True
    except Exception:
        _DISPONIBLE = False
    return _DISPONIBLE


_PROBS = {}


def probabilidades(tramos):
    """
    Probabilidad de ser administrativo, una por tramo, o None si no hay modelo.

    Se cachea por tramo. En el corpus hay 62.557 tramos pero solo 40.602
    distintos, y las frases estereotipadas -- que son justo las que interesa
    clasificar -- se repiten cientos de veces: 'paciente en el momento
    clinicamente estable' aparece 367 veces. Sin cache se vectorizaria cada una
    de esas 367 veces para obtener el mismo numero.
    """
    if not disponible() or not tramos:
        return None

    tramos = list(tramos)
    faltan = [t for t in dict.fromkeys(tramos) if t not in _PROBS]
    if faltan:
        X = vectorizar(faltan)
        if X is None:
            return None
        for t, p in zip(faltan, _CLF.predict_proba(X)[:, 1]):
            _PROBS[t] = float(p)
    return [_PROBS[t] for t in tramos]


def burocraticos(tramos, umbral=UMBRAL_BUROCRATICO):
    """
    Cuáles de los tramos son administrativos, como lista de booleanos.

    Si no hay clasificador entrenado devuelve todo False, que deja el
    comportamiento anterior intacto: las expresiones regulares siguen actuando
    y no se quita nada de más.
    """
    probs = probabilidades(tramos)
    if probs is None:
        return [False] * len(tramos)
    return [p >= umbral for p in probs]


def diagnosticar(texto):
    """Los tramos de una nota con su probabilidad y su etiqueta de regla."""
    tramos = segmentos(texto)
    probs = probabilidades(tramos)
    return [(t, None if probs is None else round(float(p), 3), etiquetar_debil(t))
            for t, p in zip(tramos, probs if probs is not None else [None] * len(tramos))]


def main():
    """python -m NLP.reduccion.frases  ->  construye el conjunto y entrena."""
    b, c, sin = construir_datos()
    print(f"Conjunto etiquetado por reglas: {b + c:,} tramos")
    print(f"  administrativos : {b:,}")
    print(f"  clinicos        : {c:,}")
    print(f"  sin etiqueta    : {sin:,}  (no entran a entrenar)")
    print(f"  -> {rutas.FRASES_ETIQUETADAS}")

    print("\nEntrenando...")
    m = entrenar()
    if m is None:
        print("  no se pudo entrenar")
        return
    print(f"  entrenamiento {m['entrenamiento']:,} | reservado {m['reservado']:,}\n")
    print(m["informe"])
    print(f"Modelo: {m['modelo']}")


if __name__ == "__main__":
    main()
