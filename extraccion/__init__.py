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
    GEENENTADM    entidad administradora (EPS, aseguradora SOAT, ARL...), cruzada con
                  DIM_ENTIDAD para el nombre. Es una ORGANIZACION, no una persona, y se
                  baja solo contada por dia x hora. Anadida el 2026-09-28
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
    # --- Anadidas el 2026-09-29, ANTES de consultar ningun dato de estas tablas, para el
    # perfil del hospital (cuaderno 10). Llaves de paciente, documentos, nombres, usuarios,
    # medicos y todo texto libre. Un OID de ingreso no identifica por si solo, pero tampoco
    # sale: solo se usa dentro de la consulta para unir, y lo que sale son conteos.
    "DIM_INGRESO": {
        "GENPACIEN": "llave del paciente",
        "GEENUSUARIO": "identifica a quien registro",
        "AINCONSEC": "consecutivo de ingreso: identificador administrativo",
    },
    "DIM_FOLIO": {
        "GENPACIEN": "llave del paciente",
        "GENMEDICO": "identifica al medico",
        "GENMEDICOA": "identifica al medico",
        "HCNUMFOL": "numero de folio: identificador",
    },
    "ADNCIADMIN_DW": {
        "ACIMOTIVO": "texto libre",
        "ADNMOTANU": "texto libre",
        "GEENUSUARIO": "identifica a quien registro",
        "ADNUSUANUL": "identifica a quien anulo",
    },
    "SEGUIMIENTO_REMISIONES_DW": {
        "Cedula": "documento de identidad",
        "Nombre": "nombre",
        "Paciente": "nombre del paciente",
        "MEDICO": "identifica al medico",
        "OBSERVACIONES": "texto libre",
        "MotivoInicialConsulta": "texto libre clinico",
        "AntecentesMedicos": "texto libre clinico",
        "EnfermedadActual": "texto libre clinico",
        "MotivoRemision": "texto: tratar como libre mientras no se demuestre que es un catalogo",
        "MOTIVO": "texto: tratar como libre mientras no se demuestre que es un catalogo",
        "USUMODIFICA": "identifica a quien modifico",
        "Expr2": "contenido desconocido: sensible hasta mirarlo",
        "Expr3": "contenido desconocido: sensible hasta mirarlo",
        "ConsecIngreso": "identificador administrativo",
    },
    "DW_MATRIZ_EGRESOS": {
        "DI": "documento de identidad",
        "Edad": "edad exacta: solo en bandas",
        "Certificado_de_defuncion": "identificador de un documento",
        "certificado_de_nacido_vivo": "identificador de un documento",
    },
    "TRASLADOS_Y_EGRESOS": {
        "PACNUMDOC": "documento de identidad",
        "TERNOMCOM": "nombre",
        "AINCONSEC": "identificador administrativo",
        "EDAD": "edad exacta: solo en bandas",
        "MUNICIPIO": "residencia: el propietario decidio no usarla",
    },
    "EGRESOS_INDICADORES": {"IDENTIFICACION": "documento", "USUARIO": "nombre o usuario"},
    "EGRESOS_HASTA_JUNIO_2025": {"IDENTIFICACION": "documento", "USUARIO": "nombre o usuario"},
    "EGRESOS_TRASLADO": {"IDENTIFICACION": "documento", "USUARIO": "nombre o usuario"},
    "FACT_EGRESOS_PROBABLES": {"PACNUMDOC": "documento", "GPANOMCOM": "nombre", "AINCONSEC": "identificador"},
    "FACT_SOLICITUD_CAMA": {"oidgenpacien": "llave del paciente"},
    "SERVICIOS_AMBULATORIOS_CONEXT": {"NUMIDPACIENTE": "documento", "PACIENTE": "nombre"},
    "AREA_SERVICIO": {"GEEMAIL": "correo"},
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
