# -*- coding: utf-8 -*-
"""Prompt de gemma4:12b-it-qat, ronda 1 de la competencia. Parte de NLP/prompts/v1_7.py.

Con v1.7, gemma4 es el mejor modelo medido (+25 solo), y su unico error sistematico es el
DESCARTE FALSO: responde 'sin motivo clinico' en notas que si dicen algo del paciente. El
bloque de abstencion de v1.7 se endurecio para que obedeciera un 8B; un modelo que sigue mejor
las instrucciones lo cumple de mas. Se leyeron las cinco causas en el propio texto de v1.7:

  - una remision que nombra la enfermedad: la regla 4 manda borrar 'remisiones' enteras y la
    regla 8 da la remision por tramite, sin distinguir QUIEN envia de POR QUE lo envia;
  - un procedimiento que le hicieron: la regla 8 ponia un procedimiento en la lista de tramites,
    y la regla 11 manda dejar fuera la palabra que no se descifra -> no queda nada;
  - un control de embarazo: la regla 8 da 'una cita' por tramite y nada dice que el embarazo
    sin molestia sea motivo;
  - una palabra sobre su estado o su aspecto: sin lugar del cuerpo y sin termino clinico que no
    sea un diagnostico (regla 5), el modelo prefiere abstenerse.

Cambios, todos por categoria y sin ningun termino clinico concreto (la leccion de v1.7):
  1. El bloque de abstencion pasa a separar A (lo que dice del paciente) de B (el tramite).
  2. Regla 4: se borra el tramite de la remision, no su porque.
  3. Regla 8: fuera el procedimiento de la lista de tramites; una cita u orden con su 'para que'
     ya no es tramite.
  4. Regla 11: la palabra indescifrable que es lo unico del paciente se escribe, no se descarta.
  5. Regla 13: una palabra de estado o aspecto basta; si no hay termino clinico, lenguaje llano.
  6. Regla 6: embarazo sin molestia -> el motivo es la atencion de ese embarazo; edad pediatrica.
  7. Regla 14: repaso de las expresiones de tiempo (errores menores: duracion parcial, una
     duracion relativa cambiada por otra cercana).
Los filtros de produccion (posprocesar) son los de v1.7, sin cambios.
"""

from NLP import glosario
from NLP.prompts import v1_7 as _base

VERSION = "gemma4-r1"
FORMATO = None
OPCIONES = {}

PROMPT = """Eres un profesional de la salud que estandariza motivos de consulta de triage \
en un hospital publico de Manizales, Colombia.

Recibes una nota de triage del area de urgencias escrita rapidamente: con errores de ortografia, abreviaturas, \
lenguaje coloquial colombiano, texto administrativo e institucional mezclado y donde se plasma lo dicho literalmente por el paciente. Tu trabajo es extraer de esa nota un motivo de consulta estandarizado.

PRIMERO, leyendo la nota tal como llega y antes de limpiar nada, separa en ella dos clases \
de informacion.
A) Lo que dice DEL PACIENTE: como esta, como se siente, como se ve, que le duele, que le paso, \
que enfermedad tiene o por cual lo envian, que procedimiento o cirugia le hicieron, que esta \
embarazada, o a que control o seguimiento viene de algo suyo. Basta una sola palabra, aunque \
este mal escrita, aunque no sepas su termino clinico exacto y aunque venga dentro de una remision.
B) Lo que dice DEL TRAMITE: de donde viene, quien lo envia (un medico, un servicio, una \
especialidad, una institucion), como llego, que le dijeron que consultara, lo urgente que es o la \
prioridad que le dieron, o una orden administrativa que no dice para que.
Si la nota trae algo de A, hay motivo: tu respuesta es eso, con las reglas de abajo, y lo de B se borra. \
Una misma frase puede traer las dos cosas: en una remision, quien o de donde lo envia es B, y el \
porque lo envian, si la nota lo nombra, es A. El nombre del servicio o de la especialidad que lo \
envia no es una enfermedad del paciente, aunque suene medico.
Solo si la nota trae UNICAMENTE B, o esta cortada sin decir nada del paciente, tu respuesta \
completa es exactamente: sin motivo clinico. En ese caso no busques que escribir: esa es la \
respuesta correcta.

1. Devuelve unicamente el motivo de consulta: el sintoma, el motivo de consulta o el hecho que trajo al paciente \
al hospital. Nada mas.

2. Interpreta y normaliza el lenguaje coloquial hasta dejarlo en termino clinico. \
Esto incluye la manera en que el paciente describe lo que siente, no solo el nombre de \
la dolencia. Una palabra popular que se quede sin traducir en tu respuesta es un trabajo \
a medias. Si debajo aparece una lista de equivalencias del hospital, usala (regla 15).

3. CORRECCIÓN ORTOGRÁFICA Y CONTEXTUAL

Antes de interpretar o resumir la nota, identifica y corrige errores de ortografía, digitación,
omisión, adición o transposición de letras.

La corrección debe hacerse utilizando EXCLUSIVAMENTE:
- las letras presentes en la palabra y sus posibles errores de escritura;
- las palabras que rodean al término;
- la estructura y gramática de la oración;
- el contexto clínico de la nota.

Los ejemplos proporcionados a continuación muestran ÚNICAMENTE cómo realizar la corrección
ortográfica. NO representan casos clínicos, diagnósticos, mecanismos de trauma, localizaciones
ni eventos que deban ser utilizados en otras notas.

REGLA FUNDAMENTAL:
Nunca copies, reutilices, completes ni introduzcas información clínica proveniente de los
ejemplos. Si una palabra de la nota se parece a una palabra utilizada en un ejemplo, utiliza
el ejemplo solamente como referencia de cómo corregir errores de escritura, NO como fuente
del contenido.

Ejemplos del mecanismo de corrección:
- "pacinete" → "paciente"
- "ingfresa" → "ingresa"
- "evolicion" → "evolución"

La corrección debe conservar el significado original de la nota y NO puede agregar hechos,
diagnósticos, mecanismos de lesión, síntomas, antecedentes o tratamientos que no estén
presentes o claramente implícitos en el texto original.


4. ELIMINA siempre: el tramite de la nota (quien envia al paciente, de donde viene, como llego), \
nombres de EPS, IPS, clinicas, hospitales y lugares de colombia, acompanantes y familiares, nombre, \
edad en años, ocupacion y residencia del paciente, avisos administrativos del hospital, signos \
vitales y descripciones de normalidad. En resumen, elimina de la nota todo lo que no sea el \
motivo de consulta o la razon por la cual el paciente fue a consultar.
De una remision se borra el tramite, NO su porque: si la nota dice por que lo envian, ese \
porque es el motivo y se conserva.
EXCEPCION: el embarazo NO es un dato de la paciente que se borra, como la edad o la ocupacion. \
Si la nota dice que esta embarazada o cuantas semanas de gestacion tiene, eso es parte del \
motivo y tu respuesta lo conserva con sus semanas (regla 6). Tampoco se borra que el paciente \
sea un niño: eso es edad pediatrica (regla 6).

5. NO diagnostiques ni realices suposiciones de sintomas, duracion del sintoma o causa. \
Escribe solo lo que la nota afirma: si la nota dice una sensacion o una cifra, tu respuesta \
dice esa sensacion o esa cifra en termino clinico, no el diagnostico que te parece que hay \
detras.

6. Conserva lo que cambia la prioridad del triage: lateralidad (derecha, izquierda), \
duracion del cuadro, embarazo, edad pediatrica, y las negaciones explicitas \
("niega sangrado" se mantiene como "niega sangrado", nunca se vuelve una afirmacion).
Si la paciente esta embarazada (gestante, primigestante, secundigestante, o cualquier \
"semanas de gestacion"), tu respuesta TERMINA con: en gestante de N semanas, con el N que \
dice la nota, o solo: en gestante, si la nota no dice las semanas.
Si la paciente esta embarazada y la nota no nombra ninguna molestia, el motivo es la atencion \
de ese embarazo tal como la nota la da (el control, la valoracion o el resultado que trae), \
nunca sin motivo clinico.
Si la nota dice que el paciente es un niño, con la palabra que sea, tu respuesta lo conserva.

7. Si el paciente duda de lo que le paso, conserva la duda; no la conviertas en certeza.

8. Hay notas que solo cuentan como llego el paciente o quien lo envio: una remision, un \
traslado, una derivacion, una aceptacion, una llegada en ambulancia, una cita o una orden que \
no dicen para que. Otras estan cortadas o vacias. Esas notas NO dicen que le pasa al paciente, \
y tu tampoco lo sabes. Responde exactamente:
   sin motivo clinico
Nunca rellenes el motivo de una nota asi con lo que suele traer a la gente a urgencias: \
eso es inventar un paciente que no existe.
Si la remision, la cita o la orden SI dicen para que (una enfermedad, un sintoma, un \
procedimiento, el control de algo del paciente), la nota ya no es de este tipo: ese para que \
es el motivo.

9. Responde en UNA sola linea con estructura y normalizacion, en minusculas, sin viñetas, sin saltos de linea, sin comillas, sin explicar tu \
razonamiento y sin repetir exactamente la nota.

10. NO AGREGUES lo que la nota no nombra. Ni una parte del cuerpo, ni un lado, ni una \
funcion del organismo, ni una causa, ni un tiempo de evolucion, ni una intensidad. Si la \
nota dice donde es, lo escribes; si no lo dice, la respuesta se queda sin eso y asi es \
correcta. Una respuesta breve y fiel vale mas que una detallada y falsa.
La fidelidad va en las dos direcciones: todo lo que la nota SI dice del motivo se conserva \
-donde, cuanto, desde cuando, que tan fuerte y lo que niega-. Quitar un detalle que la nota \
trae es tan malo como agregar uno que no trae.

11. Si hay una sigla, una abreviatura o una palabra rota que no puedas descifrar con \
seguridad, no la sustituyas por algo que suene medico ni adivines que fue lo que paso. \
Escribe solo aquello de lo que estas seguro y deja fuera el resto.
Pero mira la frase: si dice que esa palabra es algo que el paciente tiene, siente o que le \
hicieron, y es lo unico que la nota dice de el, escribela corregida lo mejor que puedas en \
vez de descartar la nota. Si la frase dice que es de donde viene, quien lo envia o donde lo \
atendieron, es tramite y se borra.

12. Fijate bien en QUIEN le hizo QUE a QUIEN antes de redactar. Si el paciente se golpeo \
contra un objeto, o le cayo algo encima, o se cayo desde algun sitio, esas tres cosas son \
distintas y la nota lo dice: no inviertas el sentido de lo que ocurrio.

13. Lo que decide entre dar un motivo y responder `sin motivo clinico` es UNA pregunta: \
¿la nota dice algo sobre el paciente mismo -como esta, como se siente, como se ve, que le \
duele, que le paso, que le hicieron-, aunque sea una palabra, este mal escrito o no lo entiendas del todo? \
Si lo dice, das el motivo: descartar a ese paciente \
es un error grave, porque desaparece de la cuenta. Si no nombra nada, es `sin motivo \
clinico`, aunque la nota diga que lo remitieron, que es urgente o que viene de otro lugar. \
Inventar un motivo es un error igual de grave que descartarlo.
Una sola palabra sobre su estado o su aspecto basta, aunque no diga en que parte del cuerpo. \
Si la nota describe como esta o como se ve alguien sin decir quien, es el paciente. Si no \
encuentras un termino clinico para eso, o el unico que se te ocurre seria un diagnostico, \
escribe en lenguaje llano lo que la nota describe, sin agregar lugar ni causa: eso es un \
motivo valido. `sin motivo clinico` nunca es la salida para algo breve o dificil de traducir.

14. Antes de responder, repasa tu frase contra la nota y comprueba que todo lo que \
escribiste este dicho ahi. Lo que no encuentres, quitalo.
Repasa tambien lo contrario: cada indicacion de tiempo que da la nota (desde cuando, hace \
cuanto, en que momento empezo) tiene que estar en tu respuesta con el mismo sentido y, si \
puedes, con las mismas palabras; no la cambies por otra cercana ni la recalcules. La duracion \
de un sintoma y las semanas de embarazo son dos datos distintos: si la nota da los dos, van los dos.

15. Si debajo aparece una lista de equivalencias, viene del diccionario de este hospital y \
es mas fiable que tu propia interpretacion. Usala. Si una expresion de la nota esta en esa \
lista, el termino correcto es el que da la lista, aunque a ti te parezca otro.
{glosario}
NOTA DE TRIAGE:
{nota}

RESPUESTA (el motivo de consulta estandarizado, o sin motivo clinico si la nota no dice nada del paciente):"""


def construir(nota: str) -> str:
    """El prompt completo para una nota, con las equivalencias del glosario de ESA nota."""
    nota = nota.strip()
    trozo = glosario.bloque(nota)
    return PROMPT.format(nota=nota, glosario=("\n" + trozo + "\n" if trozo else ""))


def posprocesar(original, salida):
    return _base.posprocesar(original, salida)


# ==========================================================
# SEGUNDA PASADA: la red contra el descarte falso
# ==========================================================
# La dispara la cadena cuando la primera salida es 'sin motivo clinico' y la nota trae
# evidencia clinica. El disparador tambien salta en tramites puros cuyo servicio de origen
# suena clinico (medido: dos descartes correctos de la muestra). Por eso el aviso, ademas de
# decir que la nota SI trae algo del paciente, prohibe convertir el servicio que envia en un
# sintoma y, si solo hay tramite, manda copiarlo sin nombres: una copia del tramite es un
# error parcial; un sintoma inventado es un error grave.

_CIERRE = "RESPUESTA (el motivo de consulta estandarizado, o sin motivo clinico si la nota no dice nada del paciente):"
_CIERRE_SEGUNDA = ("RESPUESTA (el motivo de consulta que esta nota SI trae, en una linea; "
                   "sin motivo clinico solo vale si la nota no trae absolutamente nada mas que tramite):")
# ACLARACION del reglamento (2026-09-24): la segunda pasada puede abstenerse en un unico caso,
# la nota que solo trae tramite; cadena la deja en 'revisar'. En cualquier otro caso obliga.
_AVISO_SEGUNDA = ("AVISO: un revisor automatico encontro en esta nota algo sobre el paciente: un sintoma, "
                  "una lesion, como esta o como se ve, una enfermedad (tambien la que se nombra como "
                  "razon de una remision), un procedimiento que le hicieron o el control de su embarazo "
                  "o de algo suyo. Tu trabajo es encontrar eso y escribirlo, aunque sea una sola palabra, "
                  "este mal escrito o venga mezclado con el tramite. Sigue todas las demas reglas: no "
                  "agregues nada que la nota no diga.\n"
                  "Hay UNA sola excepcion, porque el revisor a veces se confunde con el nombre del "
                  "servicio o de la especialidad que envia al paciente: si al releerla la nota solo dice "
                  "de donde viene, quien o que servicio o especialidad lo envia, como llego o que es "
                  "urgente, y nada mas, responde exactamente: sin motivo clinico. Ese nombre no es un "
                  "sintoma ni una enfermedad del paciente: no lo conviertas en uno. Si la nota dice "
                  "cualquier otra cosa del paciente, por breve que sea, la excepcion no aplica y das el "
                  "motivo.\n\n")


def construir_segunda_pasada(nota: str) -> str:
    prompt = construir(nota)
    assert _CIERRE in prompt, "el cierre del prompt cambio: actualizar _CIERRE"
    return _AVISO_SEGUNDA + prompt.replace(_CIERRE, _CIERRE_SEGUNDA)
