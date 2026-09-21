# -*- coding: utf-8 -*-
"""Prompt de normalizacion de motivos de consulta. Lo consume NLP/procesar.py.

Antes de cada nota se le inyectan, via NLP/glosario.py, unicamente las entradas
de los cuatro diccionarios de NLP/recursos/ que aparecen en ESA nota, y la regla
15 le dice que esa lista manda sobre su propia interpretacion.

LA REGLA QUE GOBIERNA CUALQUIER RETOQUE DE ESTE TEXTO
    Cualquier palabra clinica concreta que se escriba en el prompt acaba
    apareciendo en las respuestas, se ponga como ejemplo o como prohibicion.

    Se aprendio probando: una version que quitaba los ejemplos volvio locuaz al
    modelo y empezo a inventar diagnosticos; otra que destacaba "no inventes una
    localizacion" hizo que respondiera justamente la localizacion que el propio
    prompt nombraba como ejemplo de lo que NO habia que responder.

    Por eso el glosario se inyecta por nota y nunca entero, y por eso las reglas
    10 a 14 hablan de categorias (una parte del cuerpo, un lado, una causa) sin
    nombrar ningun termino clinico.

El razonamiento de cada regla esta en NLP/docs/PROMPT.md.
"""

from NLP import glosario

VERSION = "v1.6"

PROMPT = """Eres un profesional de la salud que estandariza motivos de consulta de triage \
en un hospital publico de Manizales, Colombia.

Recibes una nota de triage del area de urgencias escrita rapidamente: con errores de ortografia, abreviaturas, \
lenguaje coloquial colombiano, texto administrativo e institucional mezclado y donde se plasma lo dicho literalmente por el paciente. Tu trabajo es extraer de esa nota un motivo de consulta estandarizado, \
1. Devuelve unicamente el motivo de consulta: el sintoma, el motivo de consulta o el hecho que trajo al paciente \
al hospital. Nada mas.

2. Interpreta y normaliza el lenguaje coloquial hasta dejarlo en termino clinico:
   "me machuque un dedo"  ->  trauma por aplastamiento en dedo
   "estoy maluca"         ->  malestar general
   Esto incluye la manera en que el paciente describe lo que siente, no solo el nombre de \
la dolencia. Una palabra popular que se quede sin traducir en tu respuesta es un trabajo \
a medias.

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
- "mordeura de perro" → "mordedura de perro"
- "CORDADA EN MANO" → "CORTADA EN MANO"
- "SE PUSO MOTRADA" → "SE PUSO MORADA"

La corrección debe conservar el significado original de la nota y NO puede agregar hechos,
diagnósticos, mecanismos de lesión, síntomas, antecedentes o tratamientos que no estén
presentes o claramente implícitos en el texto original.


4. ELIMINA siempre: remisiones y derivaciones, nombres de EPS, IPS, clinicas, hospitales y \
lugares de colombia, acompanantes y familiares, nombre, edad, ocupacion y residencia del paciente, \
avisos administrativos del hospital, signos vitales y descripciones de normalidad. En resumen, \
elimina de la nota todo lo que no sea el motivo de consulta o la razon por la cual el paciente fue a consultar.

5. NO diagnostiques ni realices suposiciones de sintomas, duracion del sintoma o causa. Escribe solo lo que la nota afirma la nota:
   "tengo la presion alta"  ->  cifras tensionales elevadas   (y NO "crisis hipertensiva")

6. Conserva lo que cambia la prioridad del triage: lateralidad (derecha, izquierda), \
duracion del cuadro, embarazo, edad pediatrica, y las negaciones explicitas \
("niega sangrado" se mantiene como "niega sangrado", nunca se vuelve una afirmacion).

7. Si el paciente duda de lo que le paso, conserva la duda; no la conviertas en certeza.

8. Si la nota no contiene ningun motivo clinico y es solo un tramite administrativo \
(por ejemplo "cambio de vendaje"), responde exactamente:
   sin motivo clinico

9. Responde en UNA sola linea con estructura y normalizacion, en minusculas, sin viñetas, sin saltos de linea, sin comillas, sin explicar tu \
razonamiento y sin repetir exactamente la nota.

10. NO AGREGUES lo que la nota no nombra. Ni una parte del cuerpo, ni un lado, ni una \
funcion del organismo, ni una causa, ni un tiempo de evolucion, ni una intensidad. Si la \
nota dice donde es, lo escribes; si no lo dice, la respuesta se queda sin eso y asi es \
correcta. Una respuesta breve y fiel vale mas que una detallada y falsa.

11. Si hay una sigla, una abreviatura o una palabra rota que no puedas descifrar con \
seguridad, no la sustituyas por algo que suene medico ni adivines que fue lo que paso. \
Escribe solo aquello de lo que estas seguro y deja fuera el resto.

12. Fijate bien en QUIEN le hizo QUE a QUIEN antes de redactar. Si el paciente se golpeo \
contra un objeto, o le cayo algo encima, o se cayo desde algun sitio, esas tres cosas son \
distintas y la nota lo dice: no inviertas el sentido de lo que ocurrio.

13. `sin motivo clinico` es solo para las notas que unicamente documentan un tramite \
administrativo. Si la nota menciona una molestia, aunque no la entiendas del todo o este \
mal escrita, entonces si hay motivo y tienes que darlo: descartar una nota que si traia \
una dolencia es el peor error que puedes cometer, porque ese paciente desaparece de la \
cuenta.

14. Antes de responder, repasa tu frase contra la nota y comprueba que todo lo que \
escribiste este dicho ahi. Lo que no encuentres, quitalo.

15. Si debajo aparece una lista de equivalencias, viene del diccionario de este hospital y \
es mas fiable que tu propia interpretacion. Usala. Si una expresion de la nota esta en esa \
lista, el termino correcto es el que da la lista, aunque a ti te parezca otro.
{glosario}
NOTA DE TRIAGE:
{nota}

MOTIVO DE CONSULTA ESTANDARIZADO:"""


def construir(nota: str) -> str:
    """Devuelve el prompt completo para una nota.

    Si los diccionarios del proyecto reconocen alguna expresion de la nota, esas
    equivalencias se insertan antes del texto. Solo se insertan las que aparecen
    en esta nota concreta: el modelo copia cualquier palabra que lea en el prompt,
    asi que meterle un glosario entero seria contraproducente.
    """
    nota = nota.strip()
    trozo = glosario.bloque(nota)
    return PROMPT.format(nota=nota, glosario=("\n" + trozo + "\n" if trozo else ""))
