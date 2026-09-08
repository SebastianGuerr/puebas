"""
Enmascarado clinico: aparta la terminologia ANTES de que la vea el corrector.

QUE HACE, EN UNA LINEA
    Recorre la nota, decide con pesos.py que palabras son clinicas, arregla las
    que estan mal escritas usando el lexico medico, y devuelve la lista de
    tramos que el corrector de espanol no puede tocar.

EL ORDEN IMPORTA Y ESTE ES EL CAMBIO DE FONDO
    Antes:   limpieza -> LanguageTool propone -> ocho guardias vetan
    Ahora:   limpieza -> se aparta lo clinico -> LanguageTool ve solo el resto

    La diferencia no es de eficiencia sino de garantia. En el esquema viejo la
    proteccion dependia de que ningun guardia tuviera un agujero; en este,
    'epistaxis' no se corrompe porque el corrector nunca la recibe.

POR QUE PROTEGE RANGOS Y NO SUSTITUYE EL TEXTO
    La forma habitual de enmascarar es cambiar la palabra por un marcador
    ('epistaxis' -> 'MSK001'), correr el corrector y devolver el original. Aca
    no se hace, por dos razones medidas:

      el marcador rompe el contexto  LanguageTool decide por oracion. Sembrar
          la frase de marcadores le quita justo la informacion con la que
          decide, y empeora las correcciones del texto que SI hay que corregir.
      el marcador se puede corromper  si el corrector decide cambiar 'MSK001',
          la restauracion falla y se pierde el termino.

    Se protegen rangos de caracteres. El corrector ve la nota entera y con su
    contexto intacto; simplemente se descarta cualquier propuesta suya que caiga
    dentro de un rango protegido. El resultado es el mismo y no hay marcador que
    se pueda romper.

EL PROBLEMA DEL HUEVO Y LA GALLINA, Y COMO SE RESUELVE
    Para apartar 'abodominal' hay que reconocerlo como termino clinico, pero
    esta mal escrito y ningun diccionario lo contiene. Si solo se apartara lo
    que coincide exacto, los terminos mal escritos -- que son justo los que hay
    que arreglar -- quedarian expuestos al corrector de espanol, que es donde se
    corrompen.

    Se resuelve en dos pasadas:

      1. exacta   la palabra esta en el lexico clinico. Se aparta tal cual.
      2. difusa   la palabra pesa lo suficiente para ser clinica pero no esta en
                  el lexico. Se busca la forma del lexico a distancia <= 2 y, si
                  hay UNA sola, se corrige y se aparta ya corregida.

    La segunda pasada es la que arregla los casos que el corrector de espanol
    nunca pudo, porque el destino no estaba en su diccionario:

        abodominal         -> abdominal
        dilispidemia       -> dislipidemia
        craneazoencefalico -> craneoencefálico
        vasalva            -> valsalva
        venfalaxina        -> venlafaxina

    Y ante el empate se abstiene: si dos terminos clinicos estan a la misma
    distancia, elegir uno inventa un diagnostico. 'añoñ' no encuentra nada y se
    queda como esta, que es la respuesta correcta.
"""

import lexico
import linguistica
import morfologia
import pesos
import reglas
import terminologia

# ==========================================================
# CONFIGURACION
# ==========================================================

# Longitud minima para intentar el arreglo por lexico. Por debajo, la distancia
# de edicion deja de discriminar: a dos ediciones de una palabra de 4 letras hay
# medio diccionario.
LONGITUD_MINIMA_CORRECCION = 6

CORREGIR_CON_LEXICO = True


def admisible(original, candidato):
    """
    Filtra las correcciones por lexico. Salieron las dos de una medicion contra
    el conjunto de referencia, donde esta pasada bajo la precision de 97,6% a
    93,3% antes de existir.

    EL CANDIDATO TIENE QUE EXISTIR EN EL HOSPITAL
        El vocabulario del modelo biomedico se construyo sobre literatura
        clinica, que es bilingue, y trae ingles: 'oncology', 'canadian',
        'levofloxacino'. Sin este filtro produjo

            Oncologia -> oncology      canadnan -> canadian

        Una correccion que el hospital no escribio nunca no es una correccion.
        Las fuentes curadas (diccionario, catalogo, externo) no pasan por aqui:
        ahi cada entrada es una decision deliberada y puede ser legitima aunque
        el corpus todavia no la traiga.

    Y TIENE QUE PASAR POR EL GUARDIAN CLINICO
        El lexico mide parecido de escritura, no de significado. Sin consultar a
        terminologia.py produjo

            ECOGRAFICO -> ecografía     un adjetivo convertido en sustantivo

        que es exactamente lo que morfologia.cambia_categoria() existe para
        frenar. Que la correccion venga de un lexico medico no la exime del
        criterio clinico: son dos preguntas distintas.
    """
    if lexico.fuente(candidato) == lexico.BIOMEDICO and pesos.frecuencia(candidato) < 1:
        return False

    # Adjetivo contra sustantivo, sin exigir morfemas medicos.
    #
    # morfologia.cambia_categoria() solo se activa cuando una de las dos
    # palabras tiene morfemas de la lista, y por eso dejo pasar
    #
    #     ovarico -> ovario      un adjetivo convertido en sustantivo
    #
    # Ninguna de las dos los tiene, pero aca esa condicion sobra: si la palabra
    # llego hasta esta funcion es porque el candidato SI es terminologia -- sale
    # del lexico clinico. Se puede aplicar la regla completa.
    if morfologia.es_adjetivo_por_forma(original) != morfologia.es_adjetivo_por_forma(candidato):
        return False

    # Un nombre de principio activo no se alcanza desde una palabra que no lo
    # es. 'LEVOFLOXACIBNA' -> 'levofloxacino' cambia ademas el genero del
    # farmaco, que en la nomenclatura internacional distingue moleculas.
    if morfologia.parece_farmaco(candidato) and not morfologia.parece_farmaco(original):
        return False

    return terminologia.admite(original, candidato)

# nombre anterior, por si algo lo importaba
_admisible = admisible


class Nota:
    """
    El resultado de enmascarar: el texto (quiza ya con terminos arreglados) y
    los rangos que el corrector no puede tocar.
    """

    __slots__ = ("texto", "rangos", "cambios", "motivos")

    def __init__(self, texto, rangos, cambios, motivos):
        self.texto = texto
        self.rangos = rangos        # [(inicio, fin)] sobre self.texto
        self.cambios = cambios      # [(original, corregido, motivo)]
        self.motivos = motivos      # {palabra: motivo del peso}

    def protegido(self, inicio, fin):
        """True si el tramo [inicio, fin) toca algun rango protegido."""
        return any(inicio < r_fin and fin > r_ini for r_ini, r_fin in self.rangos)

    def palabras_protegidas(self):
        return {self.texto[i:f].lower() for i, f in self.rangos}


# ==========================================================
# ENMASCARADO
# ==========================================================

def enmascarar(texto, corregir=CORREGIR_CON_LEXICO):
    """
    texto: salida de limpieza.limpiar(), en minusculas.

    Devuelve una Nota con los terminos clinicos apartados y, si venian mal
    escritos y el lexico lo permite, ya corregidos.
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

        # SEGUNDA PASADA, la que resuelve el huevo y la gallina.
        #
        # Un termino mal escrito no esta en ningun lexico. Lo que si se sabe de
        # el es que ninguna palabra del espanol lo reconoce: es candidato a
        # typo. Sobre esos, y solo sobre esos, se busca la forma clinica mas
        # cercana.
        #
        # La condicion de que spaCy NO la conozca es lo que evita tocar el
        # espanol corriente: 'dificil' esta mal escrita pero spaCy la conoce, y
        # arreglarle la tilde es trabajo de LanguageTool, no del lexico medico.
        if (corregir and lexico.disponible() and desconocida and not en_lexico
                and len(palabra) >= LONGITUD_MINIMA_CORRECCION
                and not morfologia.tiene_numero(palabra)):
            candidato = lexico.cercano(palabra)
            if candidato and candidato != palabra and admisible(palabra, candidato):
                reemplazo = candidato
                cambios.append((palabra, candidato, f"lexico:{lexico.fuente(candidato)}"))

        # QUE SE APARTA, Y LA EXCEPCION QUE COSTO DOS CORRECCIONES
        #
        # Se aparta lo que ya esta arreglado contra el lexico, y lo que pesa por
        # si mismo. Pero un peso alto NO basta cuando la unica evidencia es la
        # forma de la palabra:
        #
        #     disponbilidad -> peso 0.70 por el 'morfema' dis-
        #     anteceente    -> peso 0.70 por el 'morfema' ante-
        #
        # 'dis' y 'ante' son prefijos corrientes del espanol, no solo medicos, y
        # con ellos morfologia.morfemas() da falsos positivos. Medido: esas dos
        # palabras quedaban protegidas y el corrector nunca las arreglaba, que
        # es un punto de cobertura perdido por un morfema inventado.
        #
        # La regla: si la palabra no esta en ningun lexico, ningun termino
        # clinico se le parece, y encima el espanol no la reconoce, entonces la
        # forma miente. Es un typo, y va al corrector.
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
    """Que se aparto y que se arreglo en una nota. Para revisar casos puntuales."""
    nota = enmascarar(texto)
    return {
        "texto_entrada": texto,
        "texto_salida": nota.texto,
        "terminos_apartados": sorted(nota.palabras_protegidas()),
        "correcciones_por_lexico": nota.cambios,
        "pesos": pesos.diagnosticar(texto),
    }
