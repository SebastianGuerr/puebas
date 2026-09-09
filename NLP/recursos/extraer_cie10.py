"""
Extrae el vocabulario del CIE-10-ES y lo deja en lexico_externo.txt.

LA FUENTE
    Clasificación Internacional de Enfermedades, 10.ª revisión, Modificación
    Clínica, 3.ª edición (2020). Tomo I: Diagnósticos. Ministerio de Sanidad de
    España, publicado por el BOE. El PDF vive en NLP/datos/.

POR QUÉ SOLO EL VOCABULARIO Y NO LA ESTRUCTURA
    El PDF contiene una jerarquía de códigos, y reconstruirla desde el texto
    extraído es un problema en sí mismo: la indentación por guiones, las
    remisiones y las referencias cruzadas no sobreviven bien a la extracción.

    Lo que este pipeline necesita del CIE-10 no es la jerarquía sino las
    palabras: saber que 'esplenectomia', 'odinofagia' o 'corioamnionitis'
    existen en español clínico basta para que el léxico pueda corregir hacia
    ellas y protegerlas. Extraer vocabulario es robusto y no depende de que la
    maquetación se lea correctamente.

    Si en algún momento hace falta el árbol de códigos, esa es otra tarea y
    probablemente otra fuente: el Ministerio publica las tablas en formato
    tabular, aparte del PDF.

QUÉ SE DESCARTA
    El aparato editorial de la clasificación ('véase', 'excluye', 'ncoc',
    'especificado'), que son instrucciones de uso y no terminología, y las
    palabras que aparecen una sola vez en todo el documento, casi siempre
    artefactos de la extracción.

    El Tomo I es de diagnósticos, así que no aporta nombres de principios
    activos. Para esos hace falta el nomenclátor de medicamentos, que puede
    añadirse al mismo archivo de salida con la opción --anexar.

USO
    pip install pypdf
    python -m NLP.recursos.extraer_cie10
    python -m NLP.recursos.lexico   para incorporarlo al léxico clínico
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

from NLP import rutas

PDF_POR_DEFECTO = rutas.PDF_CIE10
SALIDA = rutas.LEXICO_EXTERNO

LONGITUD_MINIMA = 4

# Palabra + guiones internos, para no partir 'post-traumatico'
RE_PALABRA = re.compile(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ][A-Za-zÁÉÍÓÚÜÑáéíóúüñ-]{3,}")

# Aparato editorial de la clasificacion, no terminologia clinica.
DESCARTAR = {
    "vease", "véase", "excluye", "incluye", "codigo", "código", "codificar",
    "ncoc", "neom", "especificado", "especificada", "especificados",
    "especificadas", "otros", "otro", "otras", "otra", "tipo", "tipos",
    "ademas", "además", "cualquier", "todos", "todas", "segun", "según",
    "primero", "segundo", "tercero", "nota", "notas", "capitulo", "capítulo",
    "seccion", "sección", "tabla", "indice", "índice", "pagina", "página",
    "adicional", "adicionales", "correspondiente", "aplicable", "utilizar",
    "usar", "sitio", "sitios", "estado", "estados", "grado", "grados",
    "parte", "partes", "forma", "formas", "caso", "casos", "debido", "debida",
    "durante", "sobre", "para", "como", "esta", "este", "esto", "estos",
    "mismo", "misma", "menos", "mas", "más", "sin", "con", "por", "que",
}

# Frecuencia minima en el PDF. Una palabra que aparece una sola vez en 1.500
# paginas suele ser un artefacto de la extraccion (palabra partida por el
# salto de columna, encabezado mal leido) y no un termino.
FRECUENCIA_MINIMA = 2


def extraer(ruta_pdf):
    """
    Recorre el PDF y devuelve un Counter con las palabras encontradas y su
    frecuencia. Informa del avance y de cuántas páginas traían texto
    extraíble, que es la señal de que la lectura funcionó.
    """
    try:
        import pypdf
    except ModuleNotFoundError:
        print("Falta pypdf. Instalar con:  pip install pypdf", file=sys.stderr)
        raise SystemExit(1)

    lector = pypdf.PdfReader(str(ruta_pdf))
    conteo = Counter()
    con_texto = 0

    for n, pagina in enumerate(lector.pages, 1):
        texto = pagina.extract_text() or ""
        if not texto:
            continue
        con_texto += 1
        conteo.update(p.lower().strip("-") for p in RE_PALABRA.findall(texto))
        if n % 250 == 0:
            print(f"  {n:,}/{len(lector.pages):,} paginas")

    print(f"  {con_texto:,} de {len(lector.pages):,} paginas con texto")
    return conteo


def filtrar(conteo):
    """
    Convierte el recuento en el conjunto de términos aprovechables.

    Descarta lo que aparece menos de FRECUENCIA_MINIMA veces, lo más corto que
    LONGITUD_MINIMA, el aparato editorial y las cadenas que no tienen forma de
    palabra española (sin vocales, con guiones sueltos o con caracteres
    extraños), que provienen de errores de extracción.
    """
    salida = set()
    for palabra, veces in conteo.items():
        if veces < FRECUENCIA_MINIMA:
            continue
        if len(palabra) < LONGITUD_MINIMA or palabra in DESCARTAR:
            continue
        # una palabra de verdad no es solo consonantes ni arranca con guion
        if not re.fullmatch(r"[a-záéíóúüñ]+(?:-[a-záéíóúüñ]+)*", palabra):
            continue
        if not re.search(r"[aeiouáéíóú]", palabra):
            continue
        salida.add(palabra)
    return salida


def main():
    """
    Extrae, filtra y escribe el vocabulario. Con --anexar conserva los términos
    que ya hubiera en el archivo, que es la vía para sumar otras fuentes sin
    perder las anteriores.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--pdf", type=Path, default=PDF_POR_DEFECTO)
    ap.add_argument("--salida", type=Path, default=SALIDA)
    ap.add_argument("--anexar", action="store_true",
                    help="conserva lo que ya haya en lexico_externo.txt")
    args = ap.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"No existe {args.pdf}")

    print(f"Leyendo {args.pdf.name}...")
    conteo = extraer(args.pdf)
    print(f"  {len(conteo):,} palabras distintas")

    terminos = filtrar(conteo)
    print(f"  {len(terminos):,} tras filtrar aparato editorial y artefactos")

    previas = set()
    if args.anexar and args.salida.exists():
        previas = {l.strip().lower() for l in
                   args.salida.read_text(encoding="utf-8").splitlines()
                   if l.strip() and not l.startswith("#")}
        print(f"  {len(previas):,} terminos ya presentes, se conservan")

    todos = sorted(terminos | previas)
    cabecera = [
        "# Lexico clinico externo, un termino por linea.",
        "# Generado por extraer_cie10.py desde el CIE-10-ES 3.a edicion (2020),",
        "# Ministerio de Sanidad de Espana, Tomo I: Diagnosticos.",
        "#",
        "# Para agregar otras fuentes (nomenclator de medicamentos del INVIMA,",
        "# SNOMED CT edicion espanola) escribe sus terminos aqui y corre:",
        "#     python -m NLP.recursos.lexico",
        "",
    ]
    args.salida.write_text("\n".join(cabecera + todos) + "\n", encoding="utf-8")

    print(f"\n{len(todos):,} terminos escritos en {args.salida.name}")
    print("Ahora corre:  python -m NLP.recursos.lexico")


if __name__ == "__main__":
    main()
