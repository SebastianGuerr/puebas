"""
El unico sitio del repositorio que habla con SQL Server. Y el protocolo para hacerlo.

    python -m extraccion --esquema        lista columnas y las clasifica. No baja datos.
    python -m extraccion --cobertura      que columnas estan llenas y desde cuando
    python -m extraccion --series         escribe salidas/*.parquet

EL PROTOCOLO, EN TRES PASOS Y EN ESTE ORDEN
    1. Mirar el ESQUEMA primero. INFORMATION_SCHEMA.COLUMNS no devuelve ni una fila
       de datos, asi que se puede consultar sin pensarlo.
    2. Clasificar las columnas. Las sensibles estan enumeradas abajo, una por una y
       con su motivo. Lo que no este en la lista blanca se trata como sensible
       mientras no se haya mirado.
    3. Consultar SOLO agregados de columnas no sensibles. Nunca 'SELECT *', nunca
       una fila de paciente, nunca un identificador en la salida.

    La regla no es 'no tocar la base'. Es 'no exponer dato personal'. Son cosas
    distintas y confundirlas costo varias sesiones de trabajo que no se hicieron.

LAS COLUMNAS SENSIBLES DE DIM_TRIAGE, UNA POR UNA
    GPADOCUME   documento de identidad del paciente
    GPANOMBRE   primer nombre
    GPASEGNOM   segundo nombre
    GPAAPELLI   primer apellido
    GPASEGAPE   segundo apellido
    GENMEDICO   identificador del medico -- no es del paciente, pero identifica a
                una persona concreta y su carga de trabajo
    HCTMOTCON   texto clinico libre. NO es identificable por diseno, pero puede
                contener nombres escritos a mano, asi que no sale de aqui: lo
                procesa NLP/ contra el modelo local y nunca se imprime en crudo

    En DIM_HCNCONTRDT:
    GENUSUARIO  identificador de quien registro

HCTEDAD ES EL CASO INTERMEDIO Y POR ESO ESTA AQUI EXPLICADO
    La edad de una persona no la identifica, pero edad + fecha + servicio reduce
    mucho el conjunto de candidatos. Por eso no se baja fila a fila: se baja
    AGREGADA EN BANDAS (0-4, 5-14, 15-44, 45-64, 65+), que es como publica sus
    datos cualquier boletin epidemiologico.

    Un conteo de 'cuantos triages de 0 a 4 anos hubo el martes' no identifica a
    nadie y es la firma mas clara que existe de una epidemia respiratoria.

LO QUE SE BAJA, Y POR QUE CADA COSA
    OID           llave. Sin ella no se puede volver a unir nada
    HCTFECTRI     la fecha y hora del triage. Es el eje de todo el proyecto
    HCNCLAURGTR   nivel de urgencia. 100% de cobertura desde 2020
    HCTEDAD       solo en bandas, ver arriba
    HCCFECTUR     hora de entrada al servicio
    HCCFECSAL     hora de salida. Con la anterior da el tiempo de estancia
"""

SENSIBLES = {
    "DIM_TRIAGE": {
        "GPADOCUME": "documento de identidad",
        "GPANOMBRE": "primer nombre",
        "GPASEGNOM": "segundo nombre",
        "GPAAPELLI": "primer apellido",
        "GPASEGAPE": "segundo apellido",
        "GENMEDICO": "identifica al medico que atendio",
        "HCTMOTCON": "texto libre; solo lo lee NLP/ contra el modelo local",
    },
    "DIM_HCNCONTRDT": {
        "GENUSUARIO": "identifica a quien registro",
    },
}

# Edad: se baja, pero nunca fila a fila. Ver la cabecera.
BANDAS_EDAD = [(0, 4), (5, 14), (15, 44), (45, 64), (65, 200)]


def es_sensible(tabla, columna):
    """True si esa columna no debe salir de la base tal cual."""
    return columna in SENSIBLES.get(tabla, {})


def motor():
    """
    La conexion. Trusted_Connection: no hay credencial que guardar en ningun sitio.

    Se importa sqlalchemy aqui dentro y no arriba para que importar este modulo
    -- por ejemplo para leer SENSIBLES -- no abra una conexion ni falle en una
    maquina sin el driver.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL

    url = URL.create(
        "mssql+pyodbc", host="ls-cobra", database="DWSES",
        query={"driver": "ODBC Driver 18 for SQL Server",
               "Trusted_Connection": "yes",
               "TrustServerCertificate": "yes"})
    return create_engine(url)
