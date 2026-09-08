"""
Eleccion del candidato de correccion.

Separado de ortografia.py porque es la logica mas delicada del pipeline y la
que concentra las mediciones. LanguageTool no ordena sus sugerencias por
probabilidad clinica, asi que la eleccion la hace este modulo.

PRIORIDAD
  1. Restauracion de tilde. Si un candidato es la misma palabra acentuada, es
     ese. 'palida' -> 'pálida', nunca -> 'salida'.
  2. Palabra conocida. Fuera de las tildes, lo que spaCy reconoce se deja como
     esta. Va DESPUES del paso 1 porque 'dias' figura en su vocabulario.
  3. Menor distancia de edicion, con la frecuencia del corpus como desempate.

MEDICIONES (corpus de 30.000 notas)
  Orden por distancia, no por posicion en la lista
      'fibre' -> ['libre','fibra','fiebre'] y 'trngo' -> ['Trajo','Trigo','Tango','Tengo'].
      Tomar el primero producia 'tiene libre' y 'trajo dolor'.

  FRECUENCIA_CANDIDATO = 3
      Una correccion que el hospital nunca escribio no es una correccion:
        desasturada -> desastrada(0)   bibasales -> binasales(0)   rechazados
        trombolfebitis -> tromboflebitis(3)   daignosticaron -> diagnosticaron(11)

  UMBRAL_TERMINO / FACTOR_TERMINO
      Un original repetido es terminologia, no descuido:
        taquicardica(43) -> taquicardia(120)  ratio 2.8   rechazado
        dolro(126)       -> dolor(10370)      ratio  82   aceptado
"""

from collections import Counter

from rapidfuzz.distance import DamerauLevenshtein

import reglas
import terminologia

MAX_CANDIDATOS = 10
LONGITUD_CANDIDATO_UNICO = 6  # a partir de aqui se acepta un candidato unico
FRECUENCIA_CANDIDATO = 3      # el candidato debe existir en las notas del hospital
FRECUENCIA_DESEMPATE = 10     # apariciones minimas para elegir entre varios
RATIO_DESEMPATE = 3           # el ganador debe superar al segundo por este factor
UMBRAL_TERMINO = 10           # a partir de aqui el original se considera termino real
FACTOR_TERMINO = 5            # y su correccion debe ser N veces mas frecuente

# Cuanto debe superar la correccion al original cuando el original figura en el
# vocabulario de spaCy. Es mas bajo que FACTOR_TERMINO a proposito: aqui ya se
# sabe que el token NO es terminologia clinica (pesos.py lo habria apartado), y
# el unico riesgo que queda es cambiar una palabra corriente por otra.
FACTOR_RESPALDO = 2

CONTEO = Counter()


def construir_lexico(textos):
    """Frecuencias de palabra sobre el corpus del hospital."""
    CONTEO.clear()
    for t in textos:
        CONTEO.update(reglas.RE_PALABRA.findall(str(t).lower()))
    return CONTEO


def frecuencia(expresion):
    partes = reglas.RE_PALABRA.findall(str(expresion).lower())
    if not partes:
        return 0
    return min(CONTEO.get(p, 0) for p in partes)


def elegir(original, sugerencias, protegidos=()):
    """Devuelve la correccion, o None si no hay evidencia suficiente."""
    original = reglas.normalizar(original)
    if not original or reglas.tiene_numero(original):
        return None

    # 1. tilde faltante: no es un error de digitacion
    for cand in sugerencias[:MAX_CANDIDATOS]:
        if reglas.es_restauracion_tilde(original, cand):
            return cand

    # 2. palabra que spaCy reconoce: ya NO es un veto, es una exigencia de
    #    respaldo. es_core_news_md se entreno con texto web y su vocabulario
    #    contiene faltas de ortografia frecuentes: 'conciente', 'transplante',
    #    'aprox', 'fibre'. Tratarlo como veto absoluto las congelaba para
    #    siempre -- medido, 106 de 106 notas con 'conciente' quedaron intactas
    #    aunque LanguageTool proponia 'consciente' correctamente.
    #
    #    La proteccion de la terminologia clinica ya no depende de esto: la hace
    #    pesos.py antes, y lo que pesa se aparta en enmascarado.py y nunca llega
    #    hasta aqui. Lo que queda es una palabra corriente del espanol, y para
    #    cambiarla basta con exigir que el corpus del hospital respalde el
    #    cambio por goleada.
    exige_respaldo = reglas.es_palabra_conocida(original)

    viables = []
    for cand in sugerencias[:MAX_CANDIDATOS]:
        norm = cand.lower().strip()
        if not norm or reglas.esta_protegido(norm, protegidos):
            continue
        if not reglas.forma_aceptable(original, norm):
            continue
        if frecuencia(norm) < FRECUENCIA_CANDIDATO:
            continue
        # el guardian clinico tiene la ultima palabra sobre el criterio ortografico
        if not terminologia.admite(original, norm):
            continue
        viables.append((DamerauLevenshtein.distance(original, norm),
                        -frecuencia(norm), cand))

    if not viables:
        terminologia.anotar_abstencion(original, "ningun candidato admisible")
        return None

    viables.sort()

    # 3. original repetido en el corpus: es terminologia.
    #
    #    Y AHORA SE EXIGE ADEMAS QUE LO PAREZCA. La regla decia 'lo que el
    #    hospital repite mucho es un termino real', y en un corpus donde todos
    #    cometen la misma falta eso es falso:
    #
    #      conciente(106) -> consciente(243)   se exigian 530: rechazado
    #
    #    'conciente' se repite 106 veces porque es una falta comun, no porque
    #    sea terminologia. Medido, quedaba sin corregir en 106 de 106 notas.
    #    'taquicardica' si tiene morfemas medicos y sigue protegida por la regla,
    #    que es para lo que se escribio.
    freq_original = frecuencia(original)
    if freq_original >= UMBRAL_TERMINO and terminologia.es_terminologia(original):
        if -viables[0][1] < freq_original * FACTOR_TERMINO:
            return None

    distancia_minima = viables[0][0]
    empatados = [v for v in viables if v[0] == distancia_minima]

    # 3bis. el original figura en el vocabulario de spaCy. Puede ser una palabra
    #       legitima o una falta tan comun que entro al corpus web con el que se
    #       entreno el modelo. Lo que las separa es como escribe el hospital: si
    #       la correccion aplasta al original en las notas, era una falta.
    #
    #         conciente(106)  -> consciente(243)   ratio 2.3   se aplica
    #         dias(4.891)     -> día(12)           ratio 0.002 se rechaza
    if exige_respaldo:
        mejor_freq = -empatados[0][1]
        if mejor_freq < max(freq_original * FACTOR_RESPALDO, FRECUENCIA_DESEMPATE):
            terminologia.anotar_abstencion(
                original, "palabra del vocabulario sin respaldo del corpus")
            return None

    # 4. un solo candidato a la distancia minima, en palabra larga
    if len(empatados) == 1 and len(original) >= LONGITUD_CANDIDATO_UNICO:
        return empatados[0][2]

    # 5. varios igual de cerca: decide el corpus, y por margen amplio
    mejor = -empatados[0][1]
    segunda = -empatados[1][1] if len(empatados) > 1 else 0
    if mejor >= FRECUENCIA_DESEMPATE and mejor >= max(segunda * RATIO_DESEMPATE, 1):
        return empatados[0][2]

    # varios candidatos igual de plausibles y ninguno domina: no hay forma de
    # saber cual quiso escribir el personal, y elegir uno inventa informacion
    terminologia.anotar_abstencion(original, "varios candidatos sin uno dominante")
    return None
