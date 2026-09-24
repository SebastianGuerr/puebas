"""
Rutas del paquete NLP. Unico sitio que sabe donde vive cada archivo.

LA REGLA QUE SEPARA recursos/ DE salidas/
    recursos/  se edita a mano y se versiona. Son los cuatro diccionarios que
               le dan contexto al modelo. Si se borran, se pierde trabajo
               humano y el modelo deja de entender el habla local.
    salidas/   lo produce `python -m NLP.procesar` y esta ignorado por git. Si
               se borra, se regenera volviendo a correr el proceso.

    Cuando dudes de donde poner un archivo nuevo, preguntate si un script lo
    puede volver a crear. Si la respuesta es si, va en salidas/.
"""

from pathlib import Path

PAQUETE = Path(__file__).resolve().parent

RECURSOS = PAQUETE / "recursos"
SALIDAS = PAQUETE / "salidas"
DOCS = PAQUETE / "docs"

# los cuatro diccionarios que se inyectan en el prompt (NLP/glosario.py)
SIGLAS = RECURSOS / "siglas.json"
COLOQUIALISMOS = RECURSOS / "coloquialismos.json"
LUGARES = RECURSOS / "lugares.csv"
TERMINOLOGIA_CLINICA = RECURSOS / "terminologia_clinica.json"

PROYECTO = PAQUETE.parent

# LA SALIDA DEL PROCESO: la tabla `triage` de la base compartida.
#
# Vive en la RAIZ y no dentro de NLP/ porque la comparten dos paquetes: aqui se
# escribe `triage` y embedding/ escribe `frases` y `triage_frase`. Meterla
# dentro de cualquiera de los dos haria falsa la propiedad del otro. Sigue
# siendo una salida: la regenera un script y esta ignorada por git.
BASE_DATOS = PROYECTO / "salidas" / "triage.duckdb"

# COPIA DE SOLO LECTURA, PARA MIRAR SIN BLOQUEAR
#
# DuckDB admite un solo escritor, y ademas un escritor bloquea tambien a los
# lectores (medido el 2026-09-21: con la base abierta en lectura-escritura por
# un proceso, otro no entra ni siquiera en modo lectura). Consecuencia: con la
# extension de VS Code adjunta, 'python -m NLP.procesar' no puede escribir.
#
# Esta copia rompe ese empate a medias, y conviene saber hasta donde llega.
# La refresca el propio escritor entre bloque y bloque.
#
#   LO QUE RESUELVE: con VS Code adjunto a ESTA copia, 'NLP.procesar' ya nunca
#   se cae. Antes, tener el visor abierto rompia la corrida.
#
#   LO QUE NO RESUELVE: mientras el visor la tiene abierta, Windows no deja
#   sustituir el archivo (medido: PermissionError con copyfile y con replace).
#   Asi que la copia se queda congelada en la foto que habia al conectarse y
#   solo avanza cuando el visor se desconecta y vuelve. No hay forma de tener
#   un visor de archivo viendo datos que cambian; para eso esta NLP/monitor.py,
#   que abre y cierra en cada vuelta.
BASE_VISTA = PROYECTO / "salidas" / "triage_vista.duckdb"

# LO QUE SALE A UNA GPU DE UN TERCERO Y LO QUE VUELVE. Dentro de salidas/ a
# proposito: mapa_local.parquet lleva el OID y el texto original, y esta carpeta
# esta ignorada por git. Ver NLP/docs/NUBE.md.
NUBE = SALIDAS / "nube"

# El CSV que habia antes. Ya NO se escribe; se conserva la ruta para poder
# importarlo con 'python -m NLP.procesar --importar-csv'. Ver NLP/docs/FLUJO.md.
TRIAGE_LIMPIO = SALIDAS / "triage_limpio.csv"

SALIDAS.mkdir(exist_ok=True)
BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)
