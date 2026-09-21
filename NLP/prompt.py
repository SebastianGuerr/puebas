# -*- coding: utf-8 -*-
"""Prompt unico de normalizacion de motivos de consulta.

Lo importan todos los `correr_*.py`, de modo que los modelos se comparan
cambiando solo el modelo y nada mas.

VERSION marca la corrida. Los resultados se escriben DEBAJO de los anteriores en
el mismo CSV, con su version al lado, para poder comparar que hacia el modelo
antes y despues.

ESTADO ACTUAL: v1.4. Es v1.3 mas el acceso contextual a DIVIPOLA y al catalogo
de sintomas del proyecto.
Antes de cada nota se le inyectan, via NLP/glosario.py, unicamente las entradas de
diccionario_siglas.json, diccionario_coloquial.json, lugares_colombia.csv y
catalogo_sintomas.json que aparecen en ESA nota, y
de correcciones_directas, y la regla 15 le dice que esa lista manda sobre su
propia interpretacion. Solo lo que aparece en la nota, nunca el glosario entero:
el modelo copia cualquier palabra que lea en el prompt.

En v1.3 se amplio el diccionario coloquial con 43 expresiones caldenses que no
estaban (chuzones, entumida, brotada, popo, pipi, dolor bajito, cordada, picadas,
un colorado...) y correcciones_directas con 8 erratas (motrada, cdolor, vitla,
onculta, pacientre, meintra, vomiro, mordeura). Eso arregla dos cosas a la vez:
el modelo recibe la equivalencia, y el corrector ortografico deja de estropear
estas palabras, porque el diccionario es tambien su lista de no tocar. Hoy
convierte `entumida` en `entubada` y `picadas` en `picaduras`.

AVISO SOBRE LA MEDICION: varias de esas equivalencias las propuso Claude y son
las mismas que estan puestas como salida_esperada en el banco. Mientras un
clinico no las valide, esas notas no miden si el modelo acierta, sino si sabe
copiar del glosario. Las dudosas son dolor bajito, chuzones, picadas y un
colorado.

v1.1. Es v1 —el prompt con el que se evaluaron los siete modelos y
se eligio qwen3:8b— con cinco reglas anadidas al final y una frase mas en la regla
2. Las nueve reglas originales no se tocaron.

Lo anadido sale de los fallos medidos en la corrida de v1 sobre las 50 notas:
  - reglas 10 y 11, contra la invencion de anatomia y de mecanismo: T-40 "le duele
    el pipi" salio como "dolor lumbar bilateral relacionado con micciones", donde
    ni el sitio, ni el lado, ni la funcion estaban en la nota.
  - regla 12, contra invertir lo que paso: en T-44 el paciente se cae DESDE un
    triturador y la respuesta fue "trauma por trituracion de plastico".
  - regla 13, contra el falso descarte: T-35 y T-39 tenian dolencia y salieron como
    "sin motivo clinico", que borra al paciente de la cuenta diaria. En T-39 ademas
    no respeto el texto exacto.
  - la frase de la regla 2 y la regla 14, contra dejar el colombianismo crudo
    (T-38, T-42).

Al retocar este texto conviene recordar lo que costo aprender en v2, v3 y v4:
cualquier palabra clinica concreta que se escriba en el prompt acaba apareciendo en
las respuestas, se ponga como ejemplo o como prohibicion. Por eso las reglas nuevas
hablan de categorias (una parte del cuerpo, un lado, una causa) y no nombran ningun
termino clinico.

--- historial de lo que se probo y por que se descarto ----------------------

v1 -> el que esta activo. Reglas numeradas y cuatro pares de ejemplo
      "entrada -> salida". Respuestas cortas y contenidas. Sobre las 30 notas con
      qwen3:8b acerto lo esencial en la mayoria; sus fallos conocidos son que
      copio el ejemplo "trauma por aplastamiento en dedo" en T-04 (que habla de un
      balon), invento lateralidad en T-03 y T-04, "pie" en T-22, una hernia activa
      en T-27 (que es un postoperatorio) y "dificultad para dormir" en T-26.

v2 -> se quitaron todos los pares de ejemplo y se explico el rol, el contexto y
      para que sirve el texto de salida. Gano donde se esperaba (T-20 paso de
      "sangrado nasal" a "epistaxis" y solto el bloque de la EPS; T-09 conservo el
      adenocarcinoma; desaparecio la copia de ejemplos), pero volvio locuaz al
      modelo, y al alargarse invento: "posible fractura de brazo izquierdo" en una
      nota que solo dice ME CAI, "parto de pretermino" en una gestante de 38
      semanas. Ademas rompio la consistencia entre T-02 y T-30, que v1 si tenia.

v3 -> v2 con la brevedad de v1 recuperada y una revision final explicita. Quito
      las invenciones grandes de v2 y conservo sus ganancias, pero siguio
      inventando de forma concentrada: cinco de siete alucinaciones eran rellenar
      una localizacion anatomica que la nota no daba. La revision final que pedia
      el prompt no se ejecutaba.

v4 -> seccion destacada contra la localizacion inventada, con la regla de que cada
      palabra tiene que proceder de la nota. Salio peor: T-07 "ESTOY BROTADA" paso
      a "dolor abdominal" y T-09 perdio el adenocarcinoma.

La leccion que dejan v2, v3 y v4, y que conviene no olvidar al retocar este texto:
**cualquier palabra concreta que aparezca en el prompt acaba en la salida, se
ponga como ejemplo o como prohibicion.** En v1 el modelo copio los ejemplos, en v2
se pego a "sin especificar" y en v4 a "dolor abdominal", que estaba escrito
justamente como lo que NO habia que responder.
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
