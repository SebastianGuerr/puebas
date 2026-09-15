"""
Comprueba que estén los artefactos que el pipeline da por hechos.

    python -m NLP.nucleo.requisitos        # informe, no cambia nada

POR QUE EXISTE ESTE ARCHIVO
    El 15 de septiembre se auditó una corrida entera y el resultado era malo:
    notas mal agrupadas, motivos de consulta perdidos y correcciones que
    cambiaban el sentido. La causa no estaba en ningún algoritmo. Faltaban
    cuatro artefactos que nadie había construido, y cada módulo que los
    necesitaba reaccionaba igual: seguir adelante como si no pasara nada.

        lexico_clinico.json     cargar_lexico() devuelve 0 -> _LEXICO = set()
                                -> _es_clinica() False para TODA palabra
                                -> densidad_clinica() 0.0 para TODA oración
                                -> en _quitar_institucional(), la condición
                                   'larga y poco clínica' se cumple SIEMPRE y
                                   se descarta toda oración de 8 palabras o más.
                                Medido: el 25,1% de las notas perdía contenido
                                clínico, y el 18,1% perdía más de la mitad.

        es_core_news_md         linguistica.disponible() False
                                -> en_vocabulario() False para TODA palabra, o
                                   sea que ninguna está protegida por el
                                   diccionario, y entidades() conjunto vacío, o
                                   sea cero protección para nombres propios.
                                Es la fase 2 corrigiendo a ciegas.

        lexico_casing.json      cargar() devuelve 0 y no se restaura ninguna
                                sigla a mayúscula.

        clasificador_frases     la capa que cubre lo que los patrones no ven
                                queda fuera y nadie lo dice.

    Ninguno de los cuatro fallaba. Los cuatro DEGRADABAN EN SILENCIO, que es
    peor: una corrida que falla se repite, y una corrida que se degrada se
    publica.

EL CRITERIO PARA SEPARAR exigido DE opcional
    No es lo importante que sea el artefacto, sino si su ausencia se nota.

    Es `exigido` cuando sin él el pipeline produce un resultado COMPLETO Y
    EQUIVOCADO, porque entonces nada aguas abajo puede detectarlo: el CSV tiene
    todas sus filas y todas sus columnas llenas.

    Es `opcional` cuando su ausencia deja una señal visible -- una columna
    vacía, un aviso, menos filas -- y por tanto se puede descubrir mirando la
    salida.
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

    Con estricto=False solo avisa. Esa puerta existe para poder reconstruir un
    artefacto usando el propio pipeline -- recursos/lexico.py necesita importar
    el paquete y todavia no hay lexico --, no para saltarse la comprobacion en
    una corrida normal.
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
