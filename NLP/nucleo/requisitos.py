"""
Comprueba que esten los artefactos que el pipeline da por hechos antes de
arrancar (`python -m NLP.nucleo.requisitos`: informe, no cambia nada). El
incidente que motivo este modulo y el criterio para separar `exigido` de
`opcional` estan en `decisiones/2026-09-15-artefactos-y-version-corrector.md`
y en ARQUITECTURA.md §2.2 (`requisitos.py`).
"""

import sys
from pathlib import Path

from NLP import rutas

# ==========================================================
# LO QUE EL PIPELINE NECESITA
# ==========================================================

# (clave, ruta, como se construye, que se rompe sin el, exigido)
ARTEFACTOS = [
    ("lexico_clinico",
     rutas.LEXICO_CLINICO,
     "python -m NLP.recursos.lexico",
     "la fase 5 descarta toda oracion larga: se pierde el motivo de consulta",
     True),

    ("lexico_casing",
     rutas.LEXICO_CASING,
     "python -m NLP.recursos.casing",
     "no se restaura ninguna sigla a mayuscula",
     False),

    ("clasificador_frases",
     rutas.CLASIFICADOR_FRASES,
     "python -m NLP.reduccion.frases",
     "la fase 5 pierde la capa que cubre lo que los patrones no enumeran",
     False),

    ("lexico_externo",
     rutas.LEXICO_EXTERNO,
     "python -m NLP.recursos.extraer_cie10",
     "el lexico clinico se queda sin el vocabulario del CIE-10",
     True),

    ("catalogo_sintomas",
     rutas.CATALOGO_SINTOMAS,
     "viene con el repo, en embedding/datos/",
     "la depuracion no reconoce ningun sintoma",
     True),

    ("diccionario_siglas",
     rutas.DICCIONARIO_SIGLAS,
     "viene con el repo, en NLP/datos/",
     "no se expande ninguna sigla",
     True),
]

# El modelo de spaCy no es un archivo del proyecto, asi que se comprueba
# cargandolo. Es el unico requisito que no se ve con un ls.
MODELO_SPACY = "es_core_news_md"


def _hay_spacy():
    """(disponible, detalle) del modelo de spaCy que usa la capa lingüística."""
    try:
        import spacy
    except ModuleNotFoundError:
        return False, "spaCy no esta instalado"
    try:
        spacy.load(MODELO_SPACY)
    except OSError:
        return False, f"falta el modelo {MODELO_SPACY}"
    return True, ""


def revisar():
    """
    Estado de cada requisito, sin imprimir ni interrumpir.

    Devuelve (faltan_exigidos, faltan_opcionales), dos listas de tuplas
    (clave, como_construirlo, que_se_rompe).
    """
    exigidos, opcionales = [], []
    for clave, ruta, receta, dano, exigido in ARTEFACTOS:
        if Path(ruta).exists():
            continue
        (exigidos if exigido else opcionales).append((clave, receta, dano))

    hay, detalle = _hay_spacy()
    if not hay:
        exigidos.append((
            MODELO_SPACY,
            f"python -m spacy download {MODELO_SPACY}",
            "la fase 2 corrige sin vocabulario y sin proteger nombres propios"
            f" ({detalle})",
        ))
    return exigidos, opcionales


def exigir(estricto=True):
    """
    Interrumpe la corrida si falta algo cuya ausencia no se notaria despues.
    Con estricto=False solo avisa (para reconstruir un artefacto usando el
    propio pipeline, no para saltarse la comprobacion en una corrida normal).
    """
    exigidos, opcionales = revisar()

    for clave, receta, dano in opcionales:
        print(f"  AVISO: falta {clave}. {dano}.")
        print(f"         se construye con: {receta}")

    if not exigidos:
        return True

    print("", file=sys.stderr)
    print("FALTAN ARTEFACTOS SIN LOS QUE LA CORRIDA SALE MAL PERO COMPLETA:",
          file=sys.stderr)
    for clave, receta, dano in exigidos:
        print(f"\n  {clave}", file=sys.stderr)
        print(f"      sin el: {dano}", file=sys.stderr)
        print(f"      arreglo: {receta}", file=sys.stderr)
    print("", file=sys.stderr)

    if estricto:
        raise SystemExit(
            "Corrida detenida. Son artefactos que NO hacen fallar el pipeline:\n"
            "sin ellos el CSV sale entero y equivocado, y por eso se para aqui\n"
            "en vez de dejar que el error viaje al clustering."
        )
    return False


def main():
    exigidos, opcionales = revisar()
    print("REQUISITOS DEL PIPELINE\n")
    for clave, ruta, receta, dano, exigido in ARTEFACTOS:
        marca = "OK " if Path(ruta).exists() else "NO "
        print(f"  [{marca}] {'exigido ' if exigido else 'opcional'}  {clave}")
    hay, detalle = _hay_spacy()
    print(f"  [{'OK ' if hay else 'NO '}] exigido   {MODELO_SPACY}")

    if not exigidos and not opcionales:
        print("\nTodo en su sitio.")
        return
    print()
    exigir(estricto=False)


if __name__ == "__main__":
    main()
