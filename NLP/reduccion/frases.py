"""
Clasificador de tramos: decidir si una frase habla del paciente o del servicio
(RoBERTa clinico congelado + regresion logistica), para cubrir el tramite que
los patrones de reduccion.py no enumeran. Marca, no borra: decide reduccion.py.
Ver NLP/docs/FLUJO.md seccion 7,
NLP/docs/decisiones/2026-09-16-frases-codificador.md y
NLP/docs/decisiones/2026-09-16-reduccion-clasificador-cobertura.md.
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
    La etiqueta que dan las reglas actuales, o None si ninguna se moja o si
    las dos se mojan a la vez (tramo ambiguo, no se le puede enseñar al
    clasificador con una etiqueta inventada).
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
    Escribe el conjunto de entrenamiento a datos/frases_etiquetadas.csv,
    etiquetando cada tramo con las reglas existentes (curado a mano despues,
    NO se regenera desde salidas/). Devuelve
    (n_burocraticos, n_clinicos, n_sin_etiqueta).
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


def validar_cruzado(datos=None, k=5, muestra=None, semilla=0):
    """
    Validacion cruzada estratificada sobre el conjunto etiquetado (E5.5),
    para contrastar la exactitud 0.971 que reporta entrenar() -- una sola
    particion 80/20 -- contra varios pliegues. `muestra`: submuestreo
    estratificado a ese tamano antes de vectorizar (el codificador es
    costoso sobre las 19.586 filas completas). Devuelve exactitud por
    pliegue y su media. Ver docs/decisiones/2026-09-16-E5.5.md.
    """
    import numpy as np
    import pandas as pd
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

    datos = datos or rutas.FRASES_ETIQUETADAS
    df = pd.read_csv(datos).fillna("")

    if muestra and muestra < len(df):
        df, _ = train_test_split(
            df, train_size=muestra, stratify=df["etiqueta"], random_state=semilla)

    X_txt = df["tramo"].tolist()
    y = (df["etiqueta"] == BUROCRATICO).astype(int).to_numpy()

    X = vectorizar(X_txt)
    if X is None:
        return None

    clf = LogisticRegression(max_iter=2000, class_weight="balanced")
    cv = StratifiedKFold(n_splits=k, shuffle=True, random_state=semilla)
    puntajes = cross_val_score(clf, X, y, cv=cv, scoring="accuracy")

    return {
        "filas": len(df),
        "burocraticos": int(y.sum()),
        "clinicos": int((1 - y).sum()),
        "pliegues": k,
        "exactitud_por_pliegue": [round(float(p), 4) for p in puntajes],
        "exactitud_media": round(float(np.mean(puntajes)), 4),
        "exactitud_desvio": round(float(np.std(puntajes)), 4),
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

    Se cachea por tramo (las frases estereotipadas se repiten cientos de veces
    en el corpus). Ver docs/decisiones/2026-09-16-frases-codificador.md.
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
