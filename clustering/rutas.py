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
    temas.csv            un renglon por TEMA: el nivel general, el que se
                         cruza contra clima y calendario. Es el archivo que se
                         abre primero, porque es el que responde "de que viene
                         la gente al hospital".
    clusters.csv         un renglon por cluster: el nivel fino, con el tema al
                         que pertenece cada uno. Es donde se audita si la
                         fusion en temas fue razonable.
    notas.csv            las mismas notas de asignacion.parquet pero LEGIBLES y
                         ordenadas por cluster: OID, numero, nombre y el texto.
                         Es lo que se abre para responder "¿que notas agrupo
                         exactamente aqui?" sin escribir una linea de pandas.
                         Duplica asignacion.parquet a proposito: el parquet es
                         para la maquina y este para el ojo.
    proyeccion.parquet   las coordenadas 2D de cada texto distinto. Se guarda
                         aparte porque dibujar el mapa otra vez no tiene por
                         que costar otra reduccion.
    mapa.png             el mapa de los clusters, para ver la forma del corpus.
    informe.txt          las metricas de la corrida y los parametros con que
                         salio. Sin esto no hay forma de comparar dos corridas.
    barrido.csv          una fila por combinacion de parametros probada con
                         --barrido, con sus metricas. Es como se elige el
                         tamano minimo y las dimensiones sin adivinar.
    validacion.txt       lo que dice --validar: si el agrupamiento se
                         distingue de uno hecho sobre datos sin estructura, y
                         si se repite al cambiar la semilla, la dimension o el
                         20% del corpus. barrido.csv elige entre configuraciones;
                         esto dice si alguna vale.
    validacion.png       los cuatro paneles de lo mismo: el codo, la silueta
                         por grupo, la coherencia contra su suelo y las barras
                         de estabilidad. Se mira junto al .txt, que es el que
                         lleva las advertencias de como se lee cada numero.
    serie_diaria.csv     una fila por (fecha, ancla): las notas de ese tema ese
                         dia, con los denominadores al lado. Es LA tabla que se
                         cruza contra clima y calendario. Ver fechas.py.
    cobertura_diaria.csv una fila por fecha: cuantos triages hubo, a cuantos les
                         escribieron el motivo y cuantos llegaron hasta el
                         agrupamiento. Sin esto la serie de arriba no se puede
                         interpretar, porque la cobertura se mueve con el tiempo.
    informe_fase8.txt    si el proyecto esta en condiciones de cruzar contra el
                         calendario, y que falta si no.

QUE HAY EN datos/
    palabras_vacias.txt  las que no sirven para nombrar un grupo.
    anclas.csv           la identidad permanente de cada tema: id y nombre. Se
                         edita a mano (para renombrar) y se versiona.
    anclas.npy           el centroide congelado de cada ancla, alineado con el
                         CSV fila por fila.
    anclas_origen.json   de que corrida salieron y cuando. Es lo que permite
                         saber si dos series son comparables entre si.
"""

from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"

ASIGNACION = SALIDAS / "asignacion.parquet"
CLUSTERS = SALIDAS / "clusters.csv"
TEMAS = SALIDAS / "temas.csv"
NOTAS = SALIDAS / "notas.csv"
PROYECCION = SALIDAS / "proyeccion.parquet"
MAPA = SALIDAS / "mapa.png"
INFORME = SALIDAS / "informe.txt"
BARRIDO = SALIDAS / "barrido.csv"
VALIDACION = SALIDAS / "validacion.txt"
VALIDACION_FIGURA = SALIDAS / "validacion.png"

# Las anclas viven en datos/ y NO en salidas/ porque son la definicion de las
# unidades de analisis: si una corrida las sobreescribe, las series de los meses
# anteriores dejan de ser comparables con las nuevas. Ver anclas.py.
ANCLAS = DATOS / "anclas.csv"
ANCLAS_VECTORES = DATOS / "anclas.npy"
ANCLAS_ORIGEN = DATOS / "anclas_origen.json"

SERIE = SALIDAS / "serie_diaria.csv"
COBERTURA = SALIDAS / "cobertura_diaria.csv"
PUENTE = SALIDAS / "informe_fase8.txt"

SALIDAS.mkdir(exist_ok=True)
