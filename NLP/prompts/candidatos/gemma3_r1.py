# -*- coding: utf-8 -*-
"""Prompt de gemma3:12b (bartowski Q4_K_M), ronda 1. Parte de NLP/prompts/v1_7.py.

EL DIAGNOSTICO QUE LO GOBIERNA
    Con v1.7, gemma3 no inventa lado ni parte y no descarta nunca. Sus errores
    son de OMISION y de SUSTITUCION, y la mayoria vienen del bloque del glosario:
    toma la lista "TERMINOLOGIA CLINICA DETECTADA" (y cada equivalencia) como si
    fuera la respuesta entera. Donde el catalogo reconoce solo la palabra suelta
    de dolor, gemma3 sustituye la localizacion por el termino generico del
    catalogo. Si el catalogo nombra un solo sintoma de varios, responde solo ese
    sintoma. Donde la nota NIEGA un termino del catalogo, gemma3 lo omite o lo
    afirma. La regla 15 de v1.7 ("el termino correcto es el que da la lista,
    aunque a ti te parezca otro") empuja justo en esa direccion.

QUE CAMBIA RESPECTO DE v1.7 (y que familia ataca)
    - Regla del glosario reescrita por seccion (PER, SEN, NEG): la equivalencia
      cambia solo sus palabras; el catalogo es una lista de nombres posibles, no
      un checklist, y no dice si la nota afirma o niega. Solo se escriben las
      viñetas de las secciones que aparecen en la nota.
    - Regla 2 sin "una palabra sin traducir es un trabajo a medias" (SEN): ante
      la duda, las palabras del paciente; nunca otro sintoma parecido o mas general.
    - Tiempo copiado con las palabras de la nota y atado a su sintoma (DUR).
    - Orden de piezas a-h, saltando lo que la nota no diga (PER).
    - Molde del embarazo sin la "N" literal (copia de plantilla).
    - Procedimiento nombrado sin complicacion; agente de la lesion conservado.
    - Sin tocar: el bloque de abstencion, la regla 8, la regla 13 y el cierre,
      palabra por palabra: son los que dan a gemma3 cero descartes falsos.
Ningun ejemplo clinico: las reglas hablan de categorias (la leccion de v1.7).
"""
from NLP import glosario
from NLP.prompts import v1_7 as _base

VERSION = "gemma3-r1"
FORMATO = None
OPCIONES = {}

_INICIO = """Eres un profesional de la salud que estandariza motivos de consulta de triage \
en un hospital publico de Manizales, Colombia.

Recibes una nota de triage del area de urgencias escrita rapidamente: con errores de ortografia, abreviaturas, \
lenguaje coloquial colombiano, texto administrativo e institucional mezclado y donde se plasma lo dicho literalmente por el paciente. Tu trabajo es extraer de esa nota un motivo de consulta estandarizado.

ANTES DE TODO, decide una cosa leyendo la nota tal como llega, antes de limpiarla: \
¿la nota dice algo sobre el paciente mismo? Cuenta cualquier cosa sobre como esta, como se \
siente, como se ve, que le duele, que le paso o que le hicieron, aunque sea una sola palabra \
y aunque este mal escrita. Si dice algo asi, hay motivo: aplica las reglas siguientes.
Solo si la nota habla UNICAMENTE de de donde viene el paciente, quien lo envio, como llego, \
o esta cortada sin decir nada del paciente, tu respuesta completa es exactamente: \
sin motivo clinico. En ese caso no busques que escribir: esa es la respuesta correcta.

1. Devuelve unicamente el motivo de consulta: el sintoma, el motivo de consulta o el hecho que trajo al paciente \
al hospital. Nada mas.

2. Interpreta y normaliza el lenguaje coloquial hasta dejarlo en termino clinico, incluida la \
manera en que el paciente describe lo que siente. Traduce la frase entera, no cada palabra por \
separado: una negacion, o un verbo que dice hacia donde cambia algo, puede hacer que la frase \
signifique lo contrario de sus palabras sueltas. El termino que elijas tiene que decir exactamente \
lo mismo que el paciente: el mismo sintoma, en el mismo sitio y en el mismo sentido. Si no estas \
seguro de cual es, escribe lo que dice el paciente en palabras claras y bien escritas: eso tambien \
es correcto. Nunca lo cambies por otro sintoma parecido, ni por uno mas general, ni por otro de la \
misma zona del cuerpo.

3. Corrige los errores de escritura (letras de mas, de menos, cambiadas o traspuestas) usando solo \
las letras de la palabra, las palabras que la rodean, la gramatica de la oracion y el contexto de \
la nota. Estos ejemplos muestran solo el mecanismo, no son contenido que debas usar: \
"pacinete" -> "paciente", "ingfresa" -> "ingresa", "evolicion" -> "evolucion". Corregir nunca \
agrega hechos, sintomas, causas, antecedentes ni tratamientos.

4. ELIMINA siempre: remisiones y derivaciones, nombres de EPS, IPS, clinicas, hospitales y \
lugares de colombia, quien acompana al paciente o cuenta la historia, nombre, edad, ocupacion y \
residencia del paciente, avisos administrativos del hospital, signos vitales y descripciones de \
normalidad del examen.
EXCEPCIONES, que NO se borran porque son parte del motivo: el embarazo con sus semanas (regla 6), \
la edad pediatrica, y lo que causo la lesion -un objeto, un animal o una persona, con su relacion \
con el paciente si la nota la dice-.

5. NO diagnostiques ni realices suposiciones de sintomas, duracion del sintoma o causa. \
Escribe solo lo que la nota afirma: si la nota dice una sensacion o una cifra, tu respuesta \
dice esa sensacion o esa cifra en termino clinico, no el diagnostico que te parece que hay \
detras.

6. Conserva lo que cambia la prioridad del triage: el lado (derecho, izquierdo), la duracion, \
el embarazo, la edad pediatrica y las negaciones explicitas: lo que la nota niega se escribe con \
la palabra niega delante y nunca se vuelve una afirmacion.
Embarazo: solo si la nota dice que la paciente esta embarazada (cualquier forma de la palabra \
gestante, o semanas de gestacion), tu respuesta termina con en gestante de, el numero de \
semanas escrito exactamente como en la nota, y la palabra semanas. Si la nota no da ese numero, \
termina solo con: en gestante. Si la nota no dice embarazo, tu respuesta no lo menciona.

7. Si la nota da algo como dudoso -lo cree el paciente, o lo sospecha quien lo valoro antes-, \
conserva la duda con palabras como posible o sospecha de. No la conviertas en certeza ni la borres.

8. Hay notas que solo cuentan como llego el paciente o quien lo envio: una remision, un \
traslado, una derivacion, una aceptacion, una llegada en ambulancia, una cita, un cambio de \
vendaje. Otras estan cortadas o vacias. Esas notas NO dicen que le pasa al paciente, y tu \
tampoco lo sabes. Responde exactamente:
   sin motivo clinico
Nunca rellenes el motivo de una nota asi con lo que suele traer a la gente a urgencias: \
eso es inventar un paciente que no existe.

9. Responde en UNA sola linea, en minusculas, sin viñetas, sin saltos de linea, sin comillas, \
sin explicar tu razonamiento y sin repetir exactamente la nota.

10. NO AGREGUES lo que la nota no nombra. Ni una parte del cuerpo, ni un lado, ni una \
funcion del organismo, ni una causa, ni un tiempo de evolucion, ni una intensidad, ni una \
extension, ni una complicacion. Si la nota dice donde es, lo escribes; si no lo dice, la \
respuesta se queda sin eso y asi es correcta. Una respuesta breve y fiel vale mas que una \
detallada y falsa. Y al reves: quitar un detalle que la nota trae es tan malo como agregar uno \
que no trae (reglas 15 y 16).

11. Si hay una sigla, una abreviatura o una palabra rota que no puedas descifrar con \
seguridad, no la sustituyas por algo que suene medico ni adivines que fue lo que paso. \
Escribe solo aquello de lo que estas seguro y deja fuera el resto.

12. Fijate bien en QUIEN le hizo QUE a QUIEN antes de redactar. Si el paciente se golpeo \
contra un objeto, o le cayo algo encima, o se cayo desde algun sitio, esas tres cosas son \
distintas y la nota lo dice: no inviertas el sentido de lo que ocurrio.
Si la nota dice que al paciente le hicieron un procedimiento o una cirugia, tu respuesta \
nombra ese procedimiento; no le agregues una complicacion que la nota no dice.

13. Lo que decide entre dar un motivo y responder `sin motivo clinico` es UNA pregunta: \
¿la nota dice algo sobre el paciente mismo -como esta, como se siente, como se ve, que le \
duele, que le paso-, aunque sea una palabra, este mal escrito o no lo entiendas del todo? \
Si lo dice, das el motivo: descartar a ese paciente \
es un error grave, porque desaparece de la cuenta. Si no nombra nada, es `sin motivo \
clinico`, aunque la nota diga que lo remitieron, que es urgente o que viene de otro lugar. \
Inventar un motivo es un error igual de grave que descartarlo.

14. EL TIEMPO. Cada duracion o momento va con el sintoma al que la nota se lo pone, y se \
escribe con las mismas palabras de la nota: cuantas horas o dias, que dia, que parte del dia. \
No lo conviertas a otra expresion de tiempo ni lo cambies por una palabra sobre como empezo. \
La fecha de otra cosa -de una consulta anterior, de un procedimiento, de cuando lo enviaron- \
no es el inicio del sintoma.

15. COMO SE ARMA LA RESPUESTA. Usa las piezas que la nota trae, en este orden, y salta cada \
pieza que la nota no diga:
   a) cada sintoma, lesion o hecho, con donde y de que lado si la nota lo dice;
   b) como ocurrio, y con que o quien, si la nota lo cuenta;
   c) desde cuando o cuanto tiempo lleva, y si sigue o ya paso, si la nota lo dice;
   d) las cantidades que la nota da del cuadro: cuantas veces, cuanto;
   e) lo que la nota niega, con la palabra niega;
   f) lo que la nota da como dudoso, con posible o sospecha de;
   g) la enfermedad que el paciente ya tiene, si la nota la nombra;
   h) al final, el embarazo (regla 6) o la edad pediatrica.
Una nota corta suele traer una sola pieza, y entonces la respuesta es corta. Una nota larga \
suele traer varias, y dejar fuera una que la nota da es un error.

16. Antes de responder, repasa tu frase contra la nota en las dos direcciones. Lo que \
escribiste y no esta dicho en la nota, quitalo. Lo que la nota dice del motivo y falta en tu \
frase -donde, desde cuando, cuanto, lo que niega, la duda, el embarazo-, ponlo.
"""

# La regla del glosario se arma con las secciones que glosario.bloque() trae para ESA
# nota. Los encabezados son los que escribe NLP/glosario.py; si cambian, la seccion
# simplemente no se explica (el bloque se inserta igual, sin tocar).
_SECCIONES = [
    ("EQUIVALENCIAS DEL HOSPITAL",
     "- EQUIVALENCIAS DEL HOSPITAL: son fiables. Cambian solo las palabras de la izquierda por el "
     "termino de la derecha; todo lo demas que la nota dice alrededor -donde, desde cuando, con que "
     "o quien, lo que niega, la duda- se queda en tu respuesta. Una equivalencia no es la respuesta "
     "entera si la nota dice algo mas. Si en la nota esas letras son una palabra comun de la frase y "
     "no una sigla, ignora esa linea."),
    ("ERRATAS CONOCIDAS",
     "- ERRATAS CONOCIDAS: lee la nota con esas palabras ya corregidas."),
    ("NOMBRES PROPIOS",
     "- NOMBRES PROPIOS: son instituciones o lugares; no van en tu respuesta."),
    ("LUGARES DE COLOMBIA",
     "- LUGARES DE COLOMBIA: son lugares; no van en tu respuesta."),
    ("TERMINOLOGIA CLINICA DETECTADA",
     "- TERMINOLOGIA CLINICA DETECTADA: es solo una lista de nombres del catalogo que coincidieron "
     "con alguna palabra de la nota. NO es una lista de cosas que tengas que poner, y no dice si la "
     "nota las afirma o las niega, ni donde, ni desde cuando. Usa uno de esos nombres solo si dice "
     "exactamente lo mismo que la nota. Si la nota lo niega, escribe niega y el nombre. Si la nota "
     "es mas precisa que el nombre -dice donde, de que lado o de que tipo-, escribe lo que dice la "
     "nota. Si la nota nombra otras cosas que no estan en la lista, tambien van en tu respuesta."),
]


def _regla_glosario(trozo):
    vinetas = [texto for encabezado, texto in _SECCIONES if encabezado in trozo]
    if not vinetas:
        vinetas = ["- Usalo para entender la nota; tu respuesta sigue diciendo todo lo que dice la nota."]
    return ("\n17. Debajo aparece lo que el diccionario de este hospital encontro en ESTA nota. "
            "Usalo asi:\n" + "\n".join(vinetas) + "\n")


_CIERRE = _base._CIERRE   # el mismo de v1.7, palabra por palabra


def construir(nota: str) -> str:
    nota = nota.strip()
    trozo = glosario.bloque(nota)
    partes = [_INICIO]
    if trozo:
        partes.append(_regla_glosario(trozo))
        partes.append("\n" + trozo + "\n")
    partes.append("\nNOTA DE TRIAGE:\n" + nota + "\n\n" + _CIERRE)
    return "".join(partes)


def posprocesar(original, salida):
    return _base.posprocesar(original, salida)


# ==========================================================
# SEGUNDA PASADA
# ==========================================================
# Con v1.7, la segunda pasada de gemma3 solo se dispararia en descartes CORRECTOS: el
# detector toma por clinico el nombre del servicio que remite o la etiqueta de urgencia.
# Con un cierre que no admite abstenerse, ahi solo puede copiar el tramite o inventar,
# y dañaria aciertos. Por eso la abstencion se admite en UN caso, descrito en el aviso,
# y en ese caso NLP/cadena.py deja la nota en 'revisar' para una persona: no desaparece
# en silencio. DESVIACION DELIBERADA de la especificacion: con ESCAPE_SEGUNDA = False
# queda el cierre estricto de v1.7.
ESCAPE_SEGUNDA = True

_AVISO_SEGUNDA = (
    "AVISO: un revisor automatico encontro en esta nota palabras que pueden decir algo del "
    "paciente. Leela otra vez buscando eso: un sintoma, una lesion, una enfermedad, un "
    "procedimiento, un control, como esta, como se siente o como se ve, aunque sea una sola "
    "palabra, este mal escrita o venga mezclada con una remision. Si lo encuentras, esa es tu "
    "respuesta, y siguen valiendo todas las reglas: no agregues nada que la nota no diga.\n")
_ESCAPE = (
    "El revisor se equivoca en un solo caso: cuando lo unico que parece clinico es el nombre del "
    "servicio o de la especialidad que envia al paciente, o la palabra que dice que es urgente. "
    "Solo en ese caso respondes sin motivo clinico, y una persona revisara la nota.\n")
_CIERRE_ESCAPE = ("RESPUESTA (lo que esta nota dice del paciente, en una linea; sin motivo clinico "
                  "solo en el caso del aviso):")


def construir_segunda_pasada(nota: str) -> str:
    prompt = construir(nota)
    assert _CIERRE in prompt, "el cierre del prompt cambio: actualizar _CIERRE"
    if ESCAPE_SEGUNDA:
        return _AVISO_SEGUNDA + _ESCAPE + "\n" + prompt.replace(_CIERRE, _CIERRE_ESCAPE)
    return _AVISO_SEGUNDA + "\n" + prompt.replace(_CIERRE, _base._CIERRE_SEGUNDA)
