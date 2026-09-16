"""
Clases fonéticas del español: agrupa palabras que suenan igual aunque se
escriban distinto (seseo, betacismo, yeísmo, h muda, g/j, qu/k, x/s).

E4.3. Medición, ejemplos y la decisión de sustituir con esto la clave
provisional de `evaluacion/pares.py`: docs/decisiones/2026-09-16-E4.3.md.
Uso desde otros módulos: docs/ARQUITECTURA.md, ficha `nucleo/fonetica.py`.
"""
import re

from NLP.nucleo import morfologia

# 'ch' y 'gue'/'gui' se protegen antes de plegar letra a letra: su sonido no
# es la suma de sus letras, y una regla de letra suelta los plegaria mal.
_CH = "\x02"
_G_DURA = "\x03"

RE_REPETIDA = re.compile(r"(.)\1+")


def clave(palabra, plegar_repetidas=True):
    """
    Clave fonética de una palabra: cómo sonaría, no cómo se escribe. Orden de
    las reglas y por qué importa: docs/decisiones/2026-09-16-E4.3.md.
    `plegar_repetidas` pliega además una letra repetida por error de tecleo.
    """
    p = morfologia.sin_tildes(str(palabra)).lower().strip()
    p = p.replace("ch", _CH)
    p = p.replace("gue", _G_DURA + "e").replace("gui", _G_DURA + "i")
    p = p.replace("qu", "k")
    p = re.sub(r"c(?=[ei])", "s", p)
    p = p.replace("z", "s")
    p = re.sub(r"g(?=[ei])", "j", p)
    p = p.replace(_G_DURA, "g")
    p = p.replace("h", "")
    p = p.replace("v", "b")
    p = p.replace("x", "s")
    p = p.replace("ll", "y")
    p = p.replace(_CH, "ch")
    if plegar_repetidas:
        p = RE_REPETIDA.sub(r"\1", p)
    return p


def coinciden(a, b):
    """True si dos palabras suenan igual (misma clave fonética)."""
    return bool(a) and bool(b) and clave(a) == clave(b)


def construir_indice(palabras):
    """
    Índice clave -> formas, para encontrar todas las palabras de una
    colección que suenan igual que una dada. `palabras` es cualquier
    iterable de formas (el corpus, el léxico clínico, o ambos).
    """
    indice = {}
    for palabra in palabras:
        indice.setdefault(clave(palabra), []).append(palabra)
    return indice


def candidatos(palabra, indice, maximo=5):
    """
    Formas del índice que suenan igual que `palabra` y no son la palabra
    misma (comparando sin tildes), en el orden del índice.
    """
    vista = clave(palabra)
    plana = morfologia.sin_tildes(str(palabra)).lower()
    salida = []
    for forma in indice.get(vista, []):
        if morfologia.sin_tildes(str(forma)).lower() == plana:
            continue
        if forma not in salida:
            salida.append(forma)
        if len(salida) >= maximo:
            break
    return salida


def diagnosticar(palabra):
    """Clave fonética de una palabra. Herramienta de inspección manual."""
    return {"palabra": palabra, "clave": clave(palabra)}
