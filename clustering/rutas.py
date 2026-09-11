"""
Rutas del paquete clustering. Unico sitio que sabe donde vive cada archivo.

MISMA REGLA QUE EN NLP/ Y EN embedding/
    datos/    se edita a mano y se versiona.
    salidas/  lo escribe un script y esta ignorado por git.

ESTE PAQUETE NO ESCRIBE NADA FUERA DE SU CARPETA
    Y no es una formalidad. NLP/procesar.py y embedding/vectorizar.py pueden
    estar corriendo AHORA MISMO sobre NLP/salidas/ y embedding/salidas/: este
    paquete lee de esas dos carpetas y no toca ni un byte en ellas. Asi se puede
    explorar el agrupamiento de lo que ya salio sin esperar a que el pipeline
    termine, que es justamente para lo que se hizo.

QUE HAY EN salidas/
    asignacion.parquet   OID -> cluster. Es la salida que se cruza despues con
                         la fecha de triage y con calendarios/ para buscar
                         patrones. Un renglon por nota.
    clusters.csv         un renglon por cluster: cuantas notas, que nombre le
                         toco, su texto mas representativo. Es el archivo que
                         se abre para MIRAR el resultado.
    proyeccion.parquet   las coordenadas 2D de cada texto distinto. Se guarda
                         aparte porque dibujar el mapa otra vez no tiene por
                         que costar otra reduccion.
    mapa.png             el mapa de los clusters, para ver la forma del corpus.
    informe.txt          las metricas de la corrida y los parametros con que
                         salio. Sin esto no hay forma de comparar dos corridas.
"""

from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"

ASIGNACION = SALIDAS / "asignacion.parquet"
CLUSTERS = SALIDAS / "clusters.csv"
PROYECCION = SALIDAS / "proyeccion.parquet"
MAPA = SALIDAS / "mapa.png"
INFORME = SALIDAS / "informe.txt"

SALIDAS.mkdir(exist_ok=True)
