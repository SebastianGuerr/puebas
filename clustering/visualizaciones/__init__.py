"""
Ver el triage en el tiempo. Las figuras que dicen QUE se consulta y CUANDO.

POR DONDE SE ENTRA
    python -m clustering.visualizaciones              la serie total, 2020-2026
    python -m clustering.visualizaciones --categoria  por categoria, cuando exista
    python -m clustering.visualizaciones --ventana    ademas abre las ventanas

TRES MODULOS Y NO OCHO, A PROPOSITO
    rutas.py    donde vive cada archivo.
    datos.py    la tabla que alimenta TODAS las figuras, y el lift. El unico
                sitio de este paquete donde hay un calculo que pueda estar mal.
    figuras.py  las siete figuras. Ninguna toca disco ni base de datos.

    La frontera es deliberada: una figura recibe una tabla y devuelve un
    dibujo. No consulta, no agrega por su cuenta y no decide denominadores. Si
    dos figuras discreparan, el fallo esta en datos.py y en ningun otro sitio.

LA REGLA QUE HAY QUE LLEVARSE DE AQUI
    Nunca se pinta el conteo crudo de una categoria. El volumen total oscila
    7,4 veces a lo largo del dia y 1,57 a lo largo de la semana, y TODAS las
    categorias arrastran ese ciclo. Ocho categorias en conteo crudo son ocho
    copias del mismo dibujo.

    Lo que se pinta es el indice de especializacion: cuanto se sale una
    categoria de su propia cuota en esa casilla. Ver datos.py.

QUE SE PUEDE DIBUJAR HOY Y QUE NO
    La serie total: SI. salidas/triage_horario.parquet son 55.844 casillas
    dia x hora desde 2020-01-01, y no dependen del NLP ni del agrupamiento.

    Por categoria: TODAVIA NO. nota_triage no tiene columna de categoria
    porque la clasificacion no esta decidida. El camino esta escrito y probado
    contra datos sinteticos; en cuanto exista la columna, el mismo comando la
    dibuja.
"""
