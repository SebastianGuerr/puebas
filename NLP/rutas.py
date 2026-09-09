"""
Rutas del paquete NLP. Unico sitio que sabe donde vive cada archivo.

POR QUE EXISTE ESTE ARCHIVO
    Antes cada modulo calculaba sus rutas con Path(__file__).parent, asi que
    todos daban por hecho que los .py y los datos estaban en la misma carpeta.
    Al separar el paquete en fases eso deja de ser cierto, y repetir
    'parents[1] / "datos"' en doce archivos convierte cualquier movimiento
    posterior en doce ediciones.

LA REGLA QUE SEPARA datos/ DE salidas/
    datos/    se edita a mano y se versiona. Es la fuente de verdad: los
              diccionarios, el vocabulario del CIE-10 y las correcciones de
              referencia. Si se borra, se pierde trabajo humano.
    salidas/  lo produce un script del proyecto y esta ignorado por git. Si se
              borra, se regenera corriendo el script que lo escribe.

    Cuando dudes de donde poner un archivo nuevo, preguntate si un script lo
    puede volver a crear. Si la respuesta es si, va en salidas/.
"""

from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"
DOCS = PAQUETE / "docs"

# fuentes escritas a mano (versionadas)
DICCIONARIO_SIGLAS = DATOS / "diccionario_siglas.json"
DICCIONARIO_COLOQUIAL = DATOS / "diccionario_coloquial.json"
LEXICO_EXTERNO = DATOS / "lexico_externo.txt"
REFERENCIA_CORRECCIONES = DATOS / "referencia_correcciones.json"
FRASES_ETIQUETADAS = DATOS / "frases_etiquetadas.csv"  # reduccion/frases.py, se corrige a mano
PDF_CIE10 = DATOS / "Clasif_Inter_Enfer_CIE_10_rev_3_ed.diag.pdf"

# artefactos generados (ignorados por git, se rehacen con su script)
LEXICO_CLINICO = SALIDAS / "lexico_clinico.json"      # recursos/lexico.py
LEXICO_CASING = SALIDAS / "lexico_casing.json"        # recursos/casing.py
SIGLAS_DETECTADAS = SALIDAS / "siglas_detectadas.csv"  # recursos/detectar_siglas.py
TRIAGE_LIMPIO = SALIDAS / "triage_limpio.csv"         # procesar.py
REPORTE_CAMBIOS = SALIDAS / "reporte_cambios.csv"     # procesar.py
NOTAS_DESCARTADAS = SALIDAS / "notas_descartadas.csv"  # procesar.py, fase de depuracion
CLASIFICADOR_FRASES = SALIDAS / "clasificador_frases.joblib"  # reduccion/frases.py
CACHE_CORRECCIONES = SALIDAS / "cache_correcciones.json"
MUESTRA_REVISION = SALIDAS / "muestra_revision.csv"   # evaluacion/escaneo.py
REFERENCIA = SALIDAS / "referencia.csv"               # evaluacion/referencia.py

# el catalogo de sintomas de la fase 4 lo consume lexico.py
CATALOGO_SINTOMAS = PROYECTO / "embedding" / "datos" / "catalogo_sintomas.json"

SALIDAS.mkdir(exist_ok=True)
