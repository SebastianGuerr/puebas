"""
Donde vive cada archivo de la fase de visualizacion. Nada mas.

LAS FIGURAS SON EL UNICO ARCHIVO SUELTO QUE SOBREVIVE, Y HAY UN MOTIVO
    La decision de esta sesion es que las SALIDAS DE DATOS van a la base y no a
    archivos sueltos. Un PNG no es una salida de datos: no se consulta, no se
    cruza y no se le hace un join. Guardarlo como blob en DuckDB seria meter
    medio megabyte binario en la misma tabla que los conteos para no poder
    hacer nada con el.

    Asi que las tablas van a salidas/triage.duckdb y las imagenes a
    clustering/salidas/figuras/. Las imagenes son regenerables por definicion
    -- salen de correr el comando otra vez -- y por eso la carpeta se puede
    borrar entera sin perder nada.
"""

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Las series de conteo que ya extrajo el propietario. No dependen del NLP ni
# del agrupamiento: 2.454 dias y 55.844 casillas dia x hora desde 2020.
SALIDAS_PROYECTO = RAIZ / "salidas"
DIARIO = SALIDAS_PROYECTO / "triage_diario.parquet"
HORARIO = SALIDAS_PROYECTO / "triage_horario.parquet"

# La base compartida. 'triage.duckdb' la escribe NLP/ y embedding/; mientras
# una corrida este viva, la tiene tomada y un lector tambien se queda fuera.
BASE = SALIDAS_PROYECTO / "triage.duckdb"
BASE_VISTA = SALIDAS_PROYECTO / "triage_vista.duckdb"

FIGURAS = RAIZ / "clustering" / "salidas" / "figuras"


def base_lectura():
    """
    La base que conviene abrir para LEER, que no siempre es la misma.

    DuckDB admite un solo escritor y un escritor bloquea tambien a los
    lectores. Mientras 'python -m NLP.procesar' corre -- y hoy corre durante
    dias -- abrir triage.duckdb falla. triage_vista.duckdb es la copia que
    refresca el escritor y que existe justo para esto.

    Se prefiere la vista cuando existe. Es mas vieja que la base por unos
    segundos, y para dibujar una serie de seis anos eso da igual.
    """
    if BASE_VISTA.exists():
        return BASE_VISTA
    return BASE


def figuras():
    """Crea clustering/salidas/figuras/ si hace falta y la devuelve."""
    FIGURAS.mkdir(parents=True, exist_ok=True)
    return FIGURAS
