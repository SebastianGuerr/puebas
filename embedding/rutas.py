"""
Rutas del paquete embedding. Unico sitio que sabe donde vive cada archivo.

ESTE PAQUETE ES AUTONOMO
    No importa NLP/. Antes si lo hacia -- re-exportaba TRIAGE_LIMPIO y
    CATALOGO_SINTOMAS desde NLP/rutas.py -- y el dia que NLP/ se reorganizo,
    embedding/ dejo de poder importarse siquiera (AttributeError sobre
    CATALOGO_SINTOMAS). La frontera ahora es explicita y de una sola direccion:

        NLP/         produce la frase limpia y la deja en un CSV
        embedding/   lee ese CSV y es dueno de todo lo demas

    Lo unico compartido es la ruta de la base, que se declara aqui como
    constante. Si cambia donde vive, se cambia esa linea y nada mas.

DATOS/ Y SALIDAS/
    datos/    se edita a mano y se versiona.
    salidas/  lo escribe un script y esta ignorado por git. Si se borra, se
              regenera con 'python -m embedding.vectorizar'.

LA BASE ES COMPARTIDA Y ESTA EN LA RAIZ
    salidas/triage.duckdb, fuera de este paquete, porque la comparten dos:

        NLP/         escribe la tabla `triage`      (una fila por nota)
        embedding/   escribe `frases` y `triage_frase`

    Cada paquete es dueno de SUS tablas. Que la base este en la raiz y no
    dentro de uno de los dos es lo que hace honesta esa propiedad.

    Eso NO rompe la autonomia: compartir un archivo de datos no es lo mismo
    que importar codigo. embedding/ sigue sin importar NLP/, y lo unico comun
    es la ruta, declarada aqui como constante.

QUE HAY EN salidas/ (de este paquete)
    banco_frases.csv    el set congelado que usa comparar_modelos.py, para que
                        todos los modelos se midan sobre las mismas frases.
"""

from pathlib import Path

PAQUETE = Path(__file__).resolve().parent
PROYECTO = PAQUETE.parent

DATOS = PAQUETE / "datos"
SALIDAS = PAQUETE / "salidas"
DOCS = PAQUETE / "docs"

# ENTRADA Y SALIDA: la misma base. NLP/ escribe la tabla `triage`, que este
# paquete solo LEE; este escribe `frases` y `triage_frase`, que NLP/ no toca.
# Si cambia donde vive la base, se cambia esta linea y la de NLP/rutas.py.
BASE_DATOS = PROYECTO / "salidas" / "triage.duckdb"

# El catalogo de sintomas es de este paquete: lo usa comparar_modelos.py para
# evaluar y clustering/validacion.py para verificar. NLP/ tiene su propia copia
# en NLP/recursos/terminologia_clinica.json, que es la que se le inyecta al
# modelo generador y evoluciona por su cuenta.
CATALOGO_SINTOMAS = DATOS / "catalogo_sintomas.json"

BANCO_FRASES = SALIDAS / "banco_frases.csv"

SALIDAS.mkdir(exist_ok=True)
BASE_DATOS.parent.mkdir(parents=True, exist_ok=True)
