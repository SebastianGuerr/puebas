"""
Enmascarado clínico: aparta la terminología antes de que la vea el corrector.

QUÉ HACE
    Recorre la nota, decide con el peso clínico qué palabras son terminología,
    arregla contra el léxico médico las que están mal escritas y devuelve los
    tramos que el corrector de español no puede tocar.

POR QUÉ EL ORDEN IMPORTA
    El esquema anterior era: limpiar, dejar que LanguageTool propusiera y vetar
    después lo que no procedía. La protección dependía entonces de que ningún
    veto tuviera un hueco. Aquí la terminología se aparta primero, de modo que
    un término no se corrompe porque el corrector nunca llega a recibirlo.

POR QUÉ SE PROTEGEN RANGOS Y NO SE SUSTITUYE EL TEXTO
    La forma habitual de enmascarar es reemplazar la palabra por un marcador,
    correr el corrector y restaurar. Aquí no se hace, por dos motivos:

        el marcador rompe el contexto   LanguageTool decide por oración, y
            sembrarla de marcadores le quita la información con la que decide,
            empeorando las correcciones del texto que sí hay que corregir.
        el marcador se puede corromper  si el corrector decide cambiarlo, la
            restauración falla y se pierde el término.

    En su lugar se protegen rangos de caracteres: el corrector ve la nota entera
    con su contexto intacto y simplemente se descarta cualquier propuesta suya
    que caiga dentro de un rango protegido.

EL PROBLEMA DE PARTIDA, Y CÓMO SE RESUELVE
    Para apartar un término mal escrito hay que reconocerlo como término, pero
    justamente por estar mal escrito no figura en ningún léxico. Si solo se
    apartara lo que coincide de forma exacta, los términos mal escritos —que son
    los que hay que arreglar— quedarían expuestos al corrector de español, que
    es donde se corrompen.

    Se resuelve en dos pasadas:

        1. exacta   la palabra está en el léxico clínico y se aparta tal cual.
        2. difusa   la palabra pesa lo suficiente para ser clínica pero no está
                    en el léxico. Se busca la forma más cercana y, si hay una
                    sola candidata, se corrige y se aparta ya corregida.

    La segunda pasada arregla los casos que el corrector de español nunca pudo
    resolver, porque la forma correcta no estaba en su diccionario. Ante un
    empate se abstiene: si dos términos clínicos están a la misma distancia,
    elegir uno equivale a inventar un diagnóstico.
"""

from NLP.fase2_ortografia import pesos
from NLP.fase2_ortografia import terminologia
from NLP.nucleo import linguistica
from NLP.nucleo import morfologia
from NLP.nucleo import reglas
from NLP.recursos import lexico

# ==========================================================
# CONFIGURACION
# ==========================================================

# Longitud minima para intentar el arreglo por lexico. Por debajo, la distancia
# de edicion deja de discriminar: a dos ediciones de una palabra corta esta
# medio diccionario.
LONGITUD_MINIMA_CORRECCION = 6

CORREGIR_CON_LEXICO = True


def admisible(original, candidato):
    """
    True si una corrección propuesta por el léxico puede aplicarse.

    Impone cuatro condiciones, todas necesarias porque el léxico mide parecido
    de escritura y no de significado:

    1. Si el candidato viene del vocabulario biomédico, el corpus tiene que
       haberlo escrito alguna vez. Ese vocabulario se construyó sobre literatura
       clínica bilingüe y contiene términos en inglés; sin este filtro, una
       palabra española acababa convertida en su equivalente inglés. Las fuentes
       curadas no pasan por esta condición: cada entrada suya es una decisión
       deliberada y puede ser legítima aunque el corpus todavía no la use.

    2. Original y candidato deben coincidir en ser adjetivo o no serlo. Aquí se
       aplica sin exigir morfemas médicos, a diferencia de la regla general:
       si la palabra llegó hasta esta función es porque el candidato ya es
       terminología, así que la condición sobra.

    3. No se alcanza un nombre de principio activo desde una palabra que no lo
       parece. En la nomenclatura internacional, hasta la terminación distingue
       moléculas distintas.

    4. Y en cualquier caso, la corrección tiene que pasar por el guardián
       clínico. Que venga de un léxico médico no la exime del criterio clínico:
       son dos preguntas diferentes.
    """
    if lexico.fuente(candidato) == lexico.BIOMEDICO and pesos.frecuencia(candidato) < 1:
        return False

    # adjetivo contra sustantivo, sin exigir morfemas medicos (ver punto 2)
    if morfologia.es_adjetivo_por_forma(original) != morfologia.es_adjetivo_por_forma(candidato):
        return False

    # un principio activo no se alcanza desde una palabra que no lo parece
    if morfologia.parece_farmaco(candidato) and not morfologia.parece_farmaco(original):
        return False

    return terminologia.admite(original, candidato)

# alias del nombre anterior de la funcion, por compatibilidad
_admisible = admisible


class Nota:
    """
    Resultado del enmascarado de una nota.

        texto     la nota, posiblemente con términos ya corregidos contra el
                  léxico
        rangos    pares (inicio, fin) sobre `texto` que el corrector no puede
                  tocar
        cambios   correcciones aplicadas, como (original, corregido, motivo)
        motivos   por palabra, el motivo del peso clínico que se le asignó
    """

    __slots__ = ("texto", "rangos", "cambios", "motivos")

    def __init__(self, texto, rangos, cambios, motivos):
        self.texto = texto
        self.rangos = rangos        # [(inicio, fin)] sobre self.texto
        self.cambios = cambios      # [(original, corregido, motivo)]
        self.motivos = motivos      # {palabra: motivo del peso}

    def protegido(self, inicio, fin):
        """True si el tramo indicado se solapa con algún rango protegido."""
        return any(inicio < r_fin and fin > r_ini for r_ini, r_fin in self.rangos)

    def palabras_protegidas(self):
        """Conjunto de palabras apartadas, en minúscula."""
        return {self.texto[i:f].lower() for i, f in self.rangos}


# ==========================================================
# ENMASCARADO
# ==========================================================

def enmascarar(texto, corregir=CORREGIR_CON_LEXICO):
    """
    Enmascara una nota ya limpia y en minúsculas.

    Devuelve una Nota con los términos clínicos apartados y, cuando venían mal
    escritos y el léxico permite arreglarlos, ya corregidos. El texto se
    reconstruye por tramos porque una corrección puede cambiar su longitud, y
    los rangos protegidos deben referirse al texto de salida.

    Con `corregir` en False se limita a apartar, sin tocar la escritura.
    """
    texto = str(texto or "")
    if not texto:
        return Nota(texto, [], [], {})

    partes = []          # se reconstruye el texto para poder corregir en el
    rangos = []
    cambios = []
    motivos = {}
    ultimo = 0
    desplazamiento = 0   # el texto crece o encoge al corregir un termino

    for m in reglas.RE_PALABRA.finditer(texto):
        palabra = m.group(0)
        p, motivo = pesos.peso(palabra)
        motivos[palabra] = motivo

        reemplazo = palabra
        en_lexico = lexico.contiene(palabra)
        # que ningun diccionario del espanol la reconozca es la senal de typo
        desconocida = not linguistica.en_vocabulario(palabra)

        # segunda pasada: un termino mal escrito no esta en ningun lexico, pero
        # se sabe que ninguna palabra del espanol lo reconoce. Sobre esos, y
        # solo sobre esos, se busca la forma clinica mas cercana.
        #
        # Exigir que spaCy NO la conozca es lo que evita tocar el espanol
        # corriente: una palabra comun a la que le falta la tilde es trabajo de
        # LanguageTool, no del lexico medico.
        if (corregir and lexico.disponible() and desconocida and not en_lexico
                and len(palabra) >= LONGITUD_MINIMA_CORRECCION
                and not morfologia.tiene_numero(palabra)):
            candidato = lexico.cercano(palabra)
            if candidato and candidato != palabra and admisible(palabra, candidato):
                reemplazo = candidato
                cambios.append((palabra, candidato, f"lexico:{lexico.fuente(candidato)}"))

        # Que se aparta: lo ya arreglado contra el lexico y lo que pesa por si
        # mismo. Pero un peso alto no basta cuando la unica evidencia es la
        # forma de la palabra, porque prefijos como 'dis-' o 'ante-' son
        # corrientes en espanol y no solo medicos, de modo que una palabra mal
        # escrita puede heredar peso de un morfema que en realidad no tiene.
        #
        # De ahi la regla: si la palabra no esta en ningun lexico, ningun
        # termino clinico se le parece y el espanol tampoco la reconoce,
        # entonces la forma engana. Se trata como error y va al corrector.
        if reemplazo != palabra:
            proteger = True
        elif desconocida and not en_lexico:
            proteger = False
        else:
            proteger = p >= pesos.UMBRAL_PROTECCION

        if not proteger and reemplazo == palabra:
            continue

        partes.append(texto[ultimo:m.start()])
        inicio = m.start() + desplazamiento
        partes.append(reemplazo)
        desplazamiento += len(reemplazo) - len(palabra)
        if proteger:
            rangos.append((inicio, inicio + len(reemplazo)))
        ultimo = m.end()

    partes.append(texto[ultimo:])
    return Nota("".join(partes), rangos, cambios, motivos)


def diagnosticar(texto):
    """
    Qué se apartó y qué se arregló en una nota, con el peso de cada palabra.
    Herramienta de inspección manual.
    """
    nota = enmascarar(texto)
    return {
        "texto_entrada": texto,
        "texto_salida": nota.texto,
        "terminos_apartados": sorted(nota.palabras_protegidas()),
        "correcciones_por_lexico": nota.cambios,
        "pesos": pesos.diagnosticar(texto),
    }
