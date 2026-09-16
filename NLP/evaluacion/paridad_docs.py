"""
Paridad entre los .py del paquete y las fichas de NLP/docs/ARQUITECTURA.md (E1.2).

Reglas, lectura de la salida y uso en los gates: NLP/docs/ARQUITECTURA.md §6.
    python -m NLP.evaluacion.paridad_docs [--estricto] [--doc RUTA]
"""

import argparse
import ast
import re
import sys
from collections import defaultdict
from pathlib import Path

from NLP import rutas

DOCUMENTO = rutas.DOCS / "ARQUITECTURA.md"

# Carpetas que nunca contienen codigo del paquete.
CARPETAS_EXCLUIDAS = {"__pycache__", ".venv", ".venv311", "venv", "env"}

# Fichas: **`archivo.py`** o **`carpeta/archivo.py`**.
RE_FICHA = re.compile(r"\*\*`([^`]+\.py)`\*\*")
RE_SECCION_2 = re.compile(r"^## 2\.\s")
RE_OTRA_SECCION = re.compile(r"^## ")
RE_SUBSECCION = re.compile(r"^### 2\.\d+\s+(.*)$")
RE_CARPETA_EN_TITULO = re.compile(r"`([^`]+/)`")
RE_HISTORIAL = re.compile(r"^##\s+(?:\d+\.\s*)?Historial\s*$")


def solo_docstring(ruta):
    """True si el modulo no tiene sentencias aparte del docstring (o esta vacio)."""
    try:
        cuerpo = ast.parse(ruta.read_text(encoding="utf-8")).body
    except (SyntaxError, UnicodeDecodeError):
        return False
    if not cuerpo:
        return True
    return (
        len(cuerpo) == 1
        and isinstance(cuerpo[0], ast.Expr)
        and isinstance(cuerpo[0].value, ast.Constant)
        and isinstance(cuerpo[0].value.value, str)
    )


def archivos_del_paquete(raiz=rutas.PAQUETE):
    """(archivos que exigen ficha, __init__.py exentos), como rutas posix relativas."""
    exigen, exentos = set(), set()
    for ruta in sorted(raiz.rglob("*.py")):
        relativa = ruta.relative_to(raiz)
        if CARPETAS_EXCLUIDAS & set(relativa.parts[:-1]):
            continue
        if any(parte.startswith(".") for parte in relativa.parts[:-1]):
            continue
        if ruta.name == "__init__.py" and solo_docstring(ruta):
            exentos.add(relativa.as_posix())
        else:
            exigen.add(relativa.as_posix())
    return exigen, exentos


def carpeta_de_subseccion(titulo):
    """Carpeta que documenta un '### 2.x ...': '' para la raiz, None si no se reconoce."""
    encaje = RE_CARPETA_EN_TITULO.search(titulo)
    if encaje:
        return encaje.group(1).strip("/")
    if re.search(r"\bra[ií]z\b", titulo, re.IGNORECASE):
        return ""
    return None


def fichas_del_documento(texto):
    """{ruta posix: [lineas]} de las fichas de §2; clave None para fichas sin carpeta."""
    fichas = defaultdict(list)
    dentro, carpeta = False, None
    for numero, linea in enumerate(texto.splitlines(), start=1):
        if RE_SECCION_2.match(linea):
            dentro = True
            continue
        if dentro and RE_OTRA_SECCION.match(linea):
            break
        if not dentro:
            continue
        sub = RE_SUBSECCION.match(linea)
        if sub:
            carpeta = carpeta_de_subseccion(sub.group(1))
            continue
        for nombre in RE_FICHA.findall(linea):
            if "/" in nombre:
                clave = nombre
            elif carpeta is None:
                clave = None
            else:
                clave = f"{carpeta}/{nombre}" if carpeta else nombre
            fichas[clave].append(numero)
    return fichas


def documentos_sin_historial(carpeta=rutas.DOCS):
    """Nombres de los .md de primer nivel de docs/ sin seccion '## Historial'."""
    sin = []
    for ruta in sorted(carpeta.glob("*.md")):
        lineas = ruta.read_text(encoding="utf-8").splitlines()
        if not any(RE_HISTORIAL.match(l) for l in lineas):
            sin.append(ruta.name)
    return sin


def comparar(exigen, fichas):
    """(faltantes, huerfanas, duplicadas) a partir de los archivos y las fichas."""
    documentados = {clave for clave in fichas if clave is not None}
    faltantes = sorted(exigen - documentados)
    huerfanas = sorted(documentados - exigen)
    duplicadas = sorted(c for c, lineas in fichas.items() if c and len(lineas) > 1)
    return faltantes, huerfanas, duplicadas


def informar(exigen, exentos, fichas, faltantes, huerfanas, duplicadas, sin_historial,
             documento):
    """Imprime el informe completo."""
    secciones = len({c for c in fichas if c is not None})
    print(f"Paquete:   {rutas.PAQUETE}")
    print(f"           {len(exigen)} archivos .py exigen ficha; "
          f"{len(exentos)} __init__.py solo con docstring, exentos")
    print(f"Documento: {documento}")
    print(f"           {secciones} fichas reconocidas en §2")
    print()
    print(f"Faltantes (archivo sin ficha): {len(faltantes)}")
    for ruta in faltantes:
        print(f"  - {ruta}")
    sin_carpeta = fichas.get(None, [])
    print(f"Huérfanas (ficha sin archivo): {len(huerfanas) + len(sin_carpeta)}")
    for ruta in huerfanas:
        print(f"  - {ruta}  (líneas {', '.join(map(str, fichas[ruta]))})")
    for numero in sin_carpeta:
        print(f"  - ficha fuera de una subsección de carpeta, línea {numero}")
    if duplicadas:
        print(f"Duplicadas (misma ficha más de una vez): {len(duplicadas)}")
        for ruta in duplicadas:
            print(f"  - {ruta}  (líneas {', '.join(map(str, fichas[ruta]))})")
    print(f"Documentos de docs/ sin sección '## Historial': {len(sin_historial)}")
    for nombre in sin_historial:
        print(f"  - {nombre}")
    print()
    print(f"Resultado: {len(faltantes)} faltantes, "
          f"{len(huerfanas) + len(sin_carpeta)} huérfanas, "
          f"{len(sin_historial)} documentos sin Historial")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--estricto", action="store_true",
                    help="codigo de salida 1 si hay faltantes, huerfanas o docs sin Historial")
    ap.add_argument("--doc", type=Path, default=DOCUMENTO,
                    help="documento a comprobar (por defecto docs/ARQUITECTURA.md)")
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    exigen, exentos = archivos_del_paquete()
    fichas = fichas_del_documento(args.doc.read_text(encoding="utf-8"))
    faltantes, huerfanas, duplicadas = comparar(exigen, fichas)
    huerfanas_total = len(huerfanas) + len(fichas.get(None, []))
    sin_historial = documentos_sin_historial()
    informar(exigen, exentos, fichas, faltantes, huerfanas, duplicadas, sin_historial,
             args.doc)

    if args.estricto and (faltantes or huerfanas_total or sin_historial):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
