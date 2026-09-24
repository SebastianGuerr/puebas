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

VERSION = "v1.7-14b-dev"

PROMPT = """Eres un profesional de la salud que estandariza motivos de consulta de triage \
en un hospital publico de Manizales, Colombia.

Recibes una nota de triage del area de urgencias escrita rapidamente: con errores de ortografia, abreviaturas, \
lenguaje coloquial colombiano, texto administrativo e institucional mezclado y donde se plasma lo dicho literalmente por el paciente. Tu trabajo es extraer de esa nota un motivo de consulta estandarizado.

Si la nota nombra CUALQUIER cosa que le pasa o le paso al paciente -un sintoma, una lesion, \
una agresion, una enfermedad, un procedimiento, un examen, como se siente o como se ve-, \
hay motivo y lo das, aunque la nota tambien diga que lo remitieron o de donde viene. \
La respuesta sin motivo clinico es solo para la nota que no dice NADA del paciente: \
unicamente de donde viene, quien lo envio o como llego, o que esta cortada.

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


4. ELIMINA siempre: remisiones y derivaciones, nombres de EPS, IPS, clinicas, hospitales y \
lugares de colombia, acompanantes y familiares, nombre, edad, ocupacion y residencia del paciente, \
avisos administrativos del hospital, signos vitales y descripciones de normalidad. En resumen, \
elimina de la nota todo lo que no sea el motivo de consulta o la razon por la cual el paciente fue a consultar.
EXCEPCION: el embarazo NO es un dato de la paciente que se borra, como la edad o la ocupacion. \
Si la nota dice que esta embarazada o cuantas semanas de gestacion tiene, eso es parte del \
motivo y tu respuesta lo conserva con sus semanas (regla 6).

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

7. Si el paciente duda de lo que le paso, conserva la duda; no la conviertas en certeza.

8. Hay notas que solo cuentan como llego el paciente o quien lo envio: una remision, un \
traslado, una derivacion, una aceptacion, una llegada en ambulancia, una cita, un cambio de \
vendaje. Otras estan cortadas o vacias. Esas notas NO dicen que le pasa al paciente, y tu \
tampoco lo sabes. Responde exactamente:
   sin motivo clinico
Nunca rellenes el motivo de una nota asi con lo que suele traer a la gente a urgencias: \
eso es inventar un paciente que no existe.

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

12. Fijate bien en QUIEN le hizo QUE a QUIEN antes de redactar. Si el paciente se golpeo \
contra un objeto, o le cayo algo encima, o se cayo desde algun sitio, esas tres cosas son \
distintas y la nota lo dice: no inviertas el sentido de lo que ocurrio.

13. Lo que decide entre dar un motivo y responder `sin motivo clinico` es UNA pregunta: \
¿la nota dice algo sobre el paciente mismo -como esta, como se siente, como se ve, que le \
duele, que le paso-, aunque sea una palabra, este mal escrito o no lo entiendas del todo? \
Si lo dice, das el motivo: descartar a ese paciente \
es un error grave, porque desaparece de la cuenta. Si no nombra nada, es `sin motivo \
clinico`, aunque la nota diga que lo remitieron, que es urgente o que viene de otro lugar. \
Inventar un motivo es un error igual de grave que descartarlo.

14. Antes de responder, repasa tu frase contra la nota y comprueba que todo lo que \
escribiste este dicho ahi. Lo que no encuentres, quitalo.

15. Si debajo aparece una lista de equivalencias, viene del diccionario de este hospital y \
es mas fiable que tu propia interpretacion. Usala. Si una expresion de la nota esta en esa \
lista, el termino correcto es el que da la lista, aunque a ti te parezca otro.
{glosario}
NOTA DE TRIAGE:
{nota}

RESPUESTA (el motivo de consulta estandarizado, o sin motivo clinico si la nota no dice nada del paciente):"""


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


def posprocesar(original: str, salida: str) -> str:
    """La regla 10 aplicada en codigo: quita el lado y la parte del cuerpo que la
    nota no dice. Medido el 2026-09-23: ninguna redaccion del prompt consigue que
    qwen3:8b deje de completar 'en <parte> <lado>'. Ver NLP/fidelidad.py."""
    from NLP import fidelidad
    # Una nota de tramite puro (remision, derivacion, ambulancia) con una queja
    # sin base: el prompt solo no lo consigue sin volver a inventar en otras
    # notas (balancin medido el 2026-09-23, vueltas 3 y 6).
    if fidelidad.es_tramite_puro(original, salida):
        return fidelidad.SIN_MOTIVO
    salida = fidelidad.quitar_lado_inventado(original, salida)
    salida = fidelidad.quitar_parte_inventada(original, salida)
    salida = fidelidad.quitar_embarazo_inventado(original, salida)
    salida = fidelidad.restaurar_antier(original, salida)
    return fidelidad.quitar_identificadores(original, salida)


# ==========================================================
# SEGUNDA PASADA: la red de seguridad contra el descarte falso
# ==========================================================
#
# Solo la usa NLP/cadena.py (y NLP/nube con --segunda-pasada) para las notas cuya
# primera salida fue 'sin motivo clinico' pero que SI traen algo clinico
# (fidelidad.necesita_segunda_pasada). Es el mismo prompt con dos cambios: un
# aviso al principio de que esta nota ya se reviso y SI dice algo del paciente, y
# un cierre que no admite la abstencion. El resto de las reglas sigue igual: no
# inventar, conservar negaciones y dudas.

_CIERRE = "RESPUESTA (el motivo de consulta estandarizado, o sin motivo clinico si la nota no dice nada del paciente):"
_CIERRE_SEGUNDA = ("RESPUESTA (el motivo de consulta que esta nota SI trae, en una linea; "
                   "aqui la respuesta sin motivo clinico no es valida):")
_AVISO_SEGUNDA = ("AVISO: esta nota ya fue revisada y SI dice algo sobre el paciente: un sintoma, una "
                  "lesion, una enfermedad, un procedimiento o como se siente. Tu trabajo es extraer "
                  "eso, aunque sea breve, este mal escrito o venga mezclado con una remision. Sigue "
                  "todas las demas reglas: no agregues nada que la nota no diga.\n\n")


def construir_segunda_pasada(nota: str) -> str:
    prompt = construir(nota)
    assert _CIERRE in prompt, "el cierre del prompt cambio: actualizar _CIERRE"
    return _AVISO_SEGUNDA + prompt.replace(_CIERRE, _CIERRE_SEGUNDA)
