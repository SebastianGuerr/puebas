# -*- coding: utf-8 -*-
"""qwen3:8b, ronda 1: extraer antes de redactar.

POR QUE UNA REDACCION DISTINTA Y NO UN RETOQUE DE v1.7
    v1.7 le pide al modelo, en un solo paso, leer, limpiar, traducir, decidir si
    abstenerse y redactar, con 15 reglas en fila. Medido (CONTEXTO, balancin del
    2026-09-23): cada regla que se endurecia torcia otra familia. Los errores que
    los filtros no tapan (duda -> certeza, negaciones fundidas, coloquialismo
    invertido, tramite copiado, descarte falso) tienen algo en comun: el rasgo
    que se pierde SI estaba en la nota, y se pierde al comprimir.

    Esta version separa el trabajo en dos campos (FORMATO = "razonado"):
      1. "razonamiento": COPIA de la nota, en casillas fijas, lo que dice del
         paciente, lo que niega, lo que duda, el tiempo y embarazo o edad
         pediatrica. Copiar es facil para un 8B; interpretar no.
      2. "motivo": se redacta SOLO con esas casillas, y cada casilla tiene su
         forma de salida («niega ...», «posible ...», las mismas palabras de
         tiempo). La negacion y la duda llegan escritas al momento de redactar.
    La decision de abstenerse deja de ser un juicio global: es «la casilla
    PACIENTE quedo vacia». Eso ataca a la vez el descarte falso (una palabra
    del paciente basta) y el tramite copiado (el tramite no entra en PACIENTE).

    Riesgo conocido (AbstentionBench): razonar empeora la abstencion. Aqui el
    razonamiento no es libre: son casillas de copia literal, sin interpretar.

REGLAS DE OFICIO QUE SE RESPETAN
    - Ningun termino clinico concreto en el texto (NLP/docs/PROMPT.md): solo
      categorias y marcadores de salida («niega», «posible», «en gestante de N
      semanas»). Sin ejemplos.
    - El glosario se inyecta por nota, sin tocarlo. Se enmarca: la terminologia
      detectada es vocabulario, no afirmacion (lista terminos negados en la nota).
    - posprocesar() es el de produccion, sin cambios.
    - La regla 4 conserva su numero: el bloque del glosario la cita.
    - Segunda pasada: obliga a extraer, salvo el unico caso que la ACLARACION del
      reglamento permite (la nota es solo tramite).
"""

from NLP import glosario
from NLP.prompts import v1_7 as _base

VERSION = "qwen3-8b-r1"
FORMATO = "razonado"
# Una nota larga llena las casillas: con el tope por defecto (500) el JSON podria
# cortarse y una salida cortada cuenta como vacia. Es un tope, no un costo fijo.
OPCIONES = {"num_predict": 800}

_CASILLAS = "PACIENTE: ... | NIEGA: ... | DUDA: ... | TIEMPO: ... | EMBARAZO O NIÑO: ..."

_INICIO = """Eres un profesional de la salud del servicio de urgencias de un hospital público de \
Manizales, Colombia. Lees notas de triage escritas a la carrera, con errores de ortografía, \
abreviaturas, habla coloquial de la región y trámites mezclados, y de cada nota sacas el motivo de \
consulta: lo que le pasa al paciente, dicho con fidelidad.

Respondes SOLO con un JSON de dos campos, en este orden: "razonamiento" y "motivo".

PASO 1 - "razonamiento". Copia de la nota lo que pide cada casilla, sin interpretar y sin \
explicar. Corrige la ortografía, pero no cambies una palabra por otra. Si en la nota no hay nada \
para una casilla, escribe: nada. Todo en una línea, así:
""" + _CASILLAS + """

PACIENTE: cada trozo que dice algo del paciente mismo: qué siente, qué le duele, cómo está o \
cómo se ve, qué le pasó, qué le hicieron, qué enfermedad tiene o por cuál lo envían, qué control o \
procedimiento viene a hacerse. Aunque sea una sola palabra y aunque venga dentro de una remisión. \
Una queja dicha con «no» (que algo no le funciona, que no puede hacer algo, que algo no se le \
quita) va aquí, con su «no». NO van aquí: de dónde viene, quién lo envía, lo trae o lo acompaña, \
cómo llegó, qué trámite le ordenaron o a dónde lo derivan, el nombre de un servicio o una \
especialidad, lo urgente que es, nombres, instituciones, signos vitales, ni lo que el examen \
encontró normal. Si la nota solo trae eso, o está cortada sin decir nada del paciente: nada.

NIEGA: cada síntoma o hecho que la nota dice que el paciente no presenta (lo que niega), copiado. \
No van los hallazgos normales del examen.

DUDA: solo si la nota da algo como no confirmado (alguien lo supone, lo cree, lo sospecha, le \
parece o no está seguro; es posible, probable o tal vez): la palabra de duda y aquello de lo que se \
duda. Que el paciente cuente, refiera o consulte por algo NO es duda.

TIEMPO: desde cuándo o hace cuánto, con las palabras exactas de la nota, y a cuál síntoma \
corresponde. La fecha de otra cosa (una consulta o un procedimiento anterior) no es el inicio del \
síntoma.

EMBARAZO O NIÑO: si está embarazada, con las semanas exactas que dice la nota (decimales \
incluidos); o si es un niño o un bebé. La edad de un adulto no va.

PASO 2 - "motivo". Escríbelo solo con lo que quedó en el razonamiento.
"""

_DECISION = """1. Si PACIENTE quedó en nada, el motivo es exactamente: sin motivo clinico
Si PACIENTE tiene algo, aunque sea una palabra, das el motivo: descartar a un paciente que sí \
dijo algo lo borra de la cuenta del hospital, y es el peor error. Inventarle un motivo a una nota \
de puro trámite es igual de grave.
"""

_DECISION_SEGUNDA = """1. Escribe el motivo con lo que quedó en PACIENTE. Aquí sin motivo clinico \
solo vale si, después de buscar, lo ÚNICO que trae la nota es trámite: de dónde viene, quién lo \
envía, qué servicio o especialidad lo manda, o la etiqueta de urgente. Una enfermedad o un \
diagnóstico por el que lo envían, una palabra sobre cómo está o cómo se ve, una lesión o algo que \
le hicieron NO son trámite: van en el motivo.
"""

_REGLAS = """2. Pasa a término clínico solo lo que tiene una traducción segura, que signifique \
exactamente lo mismo. Si no la tiene, deja las palabras del paciente con la ortografía corregida: \
una expresión sin traducir es aceptable; una traducción que cambia el órgano, el sentido o la \
dirección de lo que pasa es un error grave. Una queja con «no» conserva su «no», o su traducción \
dice lo mismo, nunca lo contrario. Una sigla que no sepas leer con seguridad no la cambies por algo \
que suene médico.
3. Lo de NIEGA va como «niega ...», cada cosa por separado. Lo de DUDA va como «posible ...». Lo \
de TIEMPO va con las mismas palabras de la nota. El embarazo va al final como «en gestante de N \
semanas», o «en gestante» si no dice las semanas. Un niño o un bebé, como «en paciente pediátrico».
4. Quita remisiones, derivaciones, acompañantes, nombres de personas, EPS, clínicas, hospitales, \
lugares, signos vitales y hallazgos normales del examen.
5. No agregues nada que la nota no diga: ni parte del cuerpo, ni lado, ni cifra, ni duración, ni \
causa, ni intensidad, ni embarazo, ni un diagnóstico que la nota no nombre. Las cifras se copian \
exactas, sin redondear. Cada síntoma va por separado y en la parte del cuerpo que dice la nota: no \
juntes dos en uno nuevo. Si la nota dice quién o qué causó la lesión, consérvalo, y no cambies lo \
que pasó por otra lesión.
6. Una sola línea, en minúsculas, con los elementos separados por comas, sin comillas, sin punto \
final y sin explicaciones.
"""

_GUIA_GLOSARIO = """
AYUDA DEL DICCIONARIO DEL HOSPITAL, solo para esta nota. Las equivalencias traducen expresiones \
de este hospital: úsalas. La terminología detectada es solo vocabulario: un término de esa lista \
entra en el motivo únicamente si la nota lo afirma del paciente; si la nota lo niega o lo pone en \
duda, va negado o en duda. Si una palabra que la lista toma por lugar o nombre describe en la nota \
lo que siente el paciente, no la quites.
"""

_CIERRE = ('Responde solo con el JSON: {"razonamiento": "' + _CASILLAS + '", "motivo": "..."}')
_CIERRE_SEGUNDA = (_CIERRE + "\nEn esta nota sin motivo clinico no es válido, salvo que lo único "
                   "que traiga sea trámite (de dónde viene, quién lo envía, qué servicio lo manda "
                   "o que es urgente).")

# ACLARACION del reglamento (2026-09-24): la segunda pasada puede abstenerse SOLO
# cuando la nota es puro tramite; cadena deja esa nota en 'revisar'. Sin esto, un
# tramite que dispara el detector (falso positivo) solo puede copiarse o inventarse.
_AVISO_SEGUNDA = """AVISO: esta nota ya se revisó y SÍ dice algo del paciente mismo: un síntoma, \
una lesión, cómo está o cómo se ve, una enfermedad por la que lo envían o algo que le hicieron. \
Puede ser una sola palabra, estar mal escrito o venir dentro de una remisión: encuéntralo y \
cópialo en PACIENTE. Todas las demás reglas siguen igual: nada que la nota no diga.

"""


def _armar(nota, decision, cierre, aviso=""):
    nota = nota.strip()
    trozo = glosario.bloque(nota)
    ayuda = (_GUIA_GLOSARIO + "\n" + trozo + "\n") if trozo else ""
    return (aviso + _INICIO + decision + _REGLAS + ayuda
            + "\nNOTA DE TRIAGE:\n" + nota + "\n\n" + cierre)


def construir(nota: str) -> str:
    return _armar(nota, _DECISION, _CIERRE)


def posprocesar(original, salida):
    return _base.posprocesar(original, salida)


def construir_segunda_pasada(nota: str) -> str:
    return _armar(nota, _DECISION_SEGUNDA, _CIERRE_SEGUNDA, aviso=_AVISO_SEGUNDA)
