"""
Extrae el vocabulario del CIE-10-ES y lo deja en lexico_externo.txt.

QUE ES LA FUENTE
    Clasificacion Internacional de Enfermedades, 10.a revision, Modificacion
    Clinica, 3.a edicion (enero 2020). Tomo I: Diagnosticos. Ministerio de
    Sanidad de Espana, publicado por el BOE. 1.502 paginas.

POR QUE SOLO EL VOCABULARIO, Y NO LA ESTRUCTURA
    El PDF trae una jerarquia de codigos ('Amnesia R41.3', '- anterograda
    R41.1', '- disociativa F44.0') y la tentacion es parsearla entera para
    tener el arbol de diagnosticos. No hace falta, y parsearlo bien es dificil:
    la indentacion con guiones, los 'vease' y las referencias cruzadas hacen
    que reconstruir la jerarquia desde el texto extraido sea un proyecto en si
    mismo.

    Lo que este pipeline necesita del CIE-10 no es la jerarquia sino las
    PALABRAS: que 'esplenectomia', 'odinofagia' o 'corioamnionitis' existen en
    espanol clinico. Con eso lexico.cercano() ya puede corregir hacia ellas y
    pesos.py puede protegerlas. Extraer vocabulario es robusto y no depende de
    que la maquetacion del PDF se lea bien.

    Si algun dia hace falta el arbol de codigos (para mapear un sintoma a un
    capitulo CIE, por ejemplo), esa es otra tarea y probablemente otra fuente:
    el Ministerio publica las tablas en formato tabular aparte del PDF.

QUE SE DESCARTA
    El aparato editorial de la clasificacion: 'vease', 'excluye', 'incluye',
    'ncoc', 'neom', 'especificado'. Son instrucciones de uso de la
    clasificacion, no terminologia, y aparecen decenas de miles de veces.

MEDIDO
    26.485 palabras distintas en el PDF
    19.806 no estaban en el lexico clinico  <- el aporte neto

    De los casos que el corrector no resolvia, el CIE-10 aporta 'esplenectomia'.
    NO aporta los nombres de farmaco ('empagliflozina', 'venlafaxina',
    'irbesartan'): el Tomo I es diagnosticos. Para esos hace falta el
    nomenclator de medicamentos, que el INVIMA publica en formato tabular.

USO
    pip install pypdf
    python extraer_cie10.py
    python lexico.py            para incorporarlo al lexico clinico
"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PDF_POR_DEFECTO = BASE_DIR / "Clasif_Inter_Enfer_CIE_10_rev_3_ed.diag.pdf"
SALIDA = BASE_DIR / "lexico_externo.txt"

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
    """Quita el aparato editorial, los artefactos y lo demasiado corto."""
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
        "#     python lexico.py",
        "",
    ]
    args.salida.write_text("\n".join(cabecera + todos) + "\n", encoding="utf-8")

    print(f"\n{len(todos):,} terminos escritos en {args.salida.name}")
    print("Ahora corre:  python lexico.py")


if __name__ == "__main__":
    main()
