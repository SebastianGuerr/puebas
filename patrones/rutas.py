"""
Rutas del paquete patrones. Unico sitio que sabe donde vive cada archivo.

MISMA REGLA QUE EN NLP/, embedding/ Y clustering/
    datos/    se edita a mano y se versiona.
    salidas/  lo escribe un script y esta ignorado por git.

DE DONDE LEE ESTE PAQUETE Y POR QUE NO ESCRIBE ALLA
    Lee tres sitios y no toca ninguno:

        clustering/salidas/   asignacion.parquet, serie_diaria.csv, temas.csv
        calendarios/          clima, festivos, eventos, desastres, vigilancia
        la base (DIM_TRIAGE)  solo a traves de clustering.fechas, que ya sabe

    El motivo es el mismo que en clustering/: NLP/ y embedding/ pueden estar
    corriendo ahora mismo, y ampliar el corpus es justamente lo que hay
    pendiente. Este paquete tiene que poder correrse encima de un pipeline en
    movimiento sin estorbarlo y sin que un resultado a medias ensucie la fase
    anterior.

QUE HAY EN salidas/
    tablero.csv          LA TABLA. Un renglon por bloque de tiempo y tema, con
                         las frecuencias al lado de las variables de clima y
                         de calendario de ese mismo bloque. Es el archivo que
                         se abre primero y del que salen todos los demas.
    tablero_ancho.csv    el mismo tablero con un tema por columna, que es el
                         formato que se lee de un vistazo: una fila por bloque,
                         una columna por motivo, mas el clima. Duplica a
                         tablero.csv a proposito -- el largo es para la maquina
                         y el ancho para el ojo.
    calendario_diario.parquet
                         un renglon por dia de la ventana con TODAS las
                         variables externas ya unificadas: clima, festivos,
                         eventos, desastres y alertas de vigilancia. Es el
                         unico sitio donde se decide que significa 'ese dia
                         hubo feria' y por eso se guarda aparte.
    eventos_fechados.parquet
                         un renglon por NOTA: OID, momento, fecha, tema y el
                         clima de ese dia. Es el nivel fino, el que necesita
                         K-Prototypes y el que permite volver a agregar por
                         otro bloque sin repetir la consulta a la base.
    composicion_temporadas.csv
                         una fila por tema y una columna por temporada
                         climatica, con la fraccion de las notas de esa
                         temporada que fueron de ese tema. Es la salida del
                         analisis con MAS potencia del paquete, porque es una
                         sola prueba y no hay presupuesto de multiplicidad que
                         repartir. Leer su bloque de replicacion por ano antes
                         de creerle.
    asociacion.csv       un renglon por (tema, variable, rezago) con su
                         correlacion, su valor p crudo, su valor p corregido
                         por comparaciones multiples y si sobrevive. LEER LA
                         COLUMNA 'sobrevive' Y NO LA CORRELACION.
    modelos.csv          los coeficientes de los modelos de conteo con
                         desplazamiento, que es lo que si admite una lectura
                         de tamano de efecto.
    agrupamiento.csv     a que grupo cayo cada bloque segun cada uno de los
                         algoritmos comparados.
    familias.csv         un renglon por tema con la familia en que cayo al
                         agruparlo por la FORMA de su serie semanal. Es el
                         agrupamiento de series de panorama.py, y no tiene
                         nada que ver con agrupamiento.csv: alli las filas
                         son bloques de tiempo y aqui son temas.
    series_familias.csv  una fila por semana y una columna por familia, con
                         el porcentaje de las notas procesadas de esa semana
                         que fueron de esa familia. Es lo que se dibuja en
                         el panorama.
    rezagos_familias.csv correlacion de cada familia con la lluvia a cada
                         rezago, tras pre-blanqueo. FORMA, no prueba: no
                         lleva correccion por multiplicidad.
    comparacion.csv      las metricas que ponen a esos algoritmos en la misma
                         mesa: silueta, Davies-Bouldin, Calinski-Harabasz y
                         sobre todo la estabilidad por remuestreo.
    informe.txt          lo que hay que leer antes de creerse cualquiera de
                         los archivos anteriores.
    figuras/             los calendarios y los mapas de calor.

QUE HAY EN datos/
    variables.csv        que variable externa entra al analisis, de que
                         archivo sale y por que. Se edita a mano: es la unica
                         forma de que 'que se probo' quede escrito antes de
                         mirar los resultados y no despues. Ver asociacion.py.
"""

from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"
FIGURAS = SALIDAS / "figuras"

# ==========================================================
# ENTRADAS: de otros paquetes, solo de lectura
# ==========================================================

from clustering import rutas as rutas_clustering  # noqa: E402

ASIGNACION = rutas_clustering.ASIGNACION
SERIE_DIARIA = rutas_clustering.SERIE
COBERTURA_DIARIA = rutas_clustering.COBERTURA
TEMAS = rutas_clustering.TEMAS
ANCLAS = rutas_clustering.ANCLAS

CALENDARIOS = PROYECTO / "calendarios"
CLIMA = CALENDARIOS / "clima_unificado.csv"
FESTIVOS = CALENDARIOS / "calendario_Colombia.csv"
DESASTRES = CALENDARIOS / "desastres_manizales_2020_2026.csv"
EVENTOS = CALENDARIOS / "eventos_manizales_2020_2026.csv"
VIGILANCIA = CALENDARIOS / "vigilancia_salud_manizales_caldas.csv"

# ==========================================================
# SALIDAS
# ==========================================================

TABLERO = SALIDAS / "tablero.csv"
TABLERO_ANCHO = SALIDAS / "tablero_ancho.csv"
CALENDARIO_DIARIO = SALIDAS / "calendario_diario.parquet"
EVENTOS_FECHADOS = SALIDAS / "eventos_fechados.parquet"
TEMPORADAS = SALIDAS / "composicion_temporadas.csv"
ASOCIACION = SALIDAS / "asociacion.csv"
MODELOS = SALIDAS / "modelos.csv"
AGRUPAMIENTO = SALIDAS / "agrupamiento.csv"
COMPARACION = SALIDAS / "comparacion.csv"
FAMILIAS = SALIDAS / "familias.csv"
SERIES_FAMILIAS = SALIDAS / "series_familias.csv"
REZAGOS_FAMILIAS = SALIDAS / "rezagos_familias.csv"
INFORME = SALIDAS / "informe.txt"

# datos/ se edita a mano
VARIABLES = DATOS / "variables.csv"

DATOS.mkdir(exist_ok=True)
SALIDAS.mkdir(exist_ok=True)
FIGURAS.mkdir(exist_ok=True)
