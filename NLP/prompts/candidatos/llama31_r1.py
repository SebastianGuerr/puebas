# -*- coding: utf-8 -*-
"""Prompt para llama3.1:8b (Instruct de Meta), ronda 1 de la competencia.

Lo que se sabe del modelo con v1.7 (revision_modelos.md, secciones 3b y 3d):
  - razona en voz alta en el 54 % de las notas y la respuesta llega al final;
    cuando razona, acierta los tramites (9 de 9) y cita bien la nota;
  - cuando contesta directo, completa el molde de la regla 6 de v1.7 y pega un
    embarazo con semanas inventadas (9 notas);
  - donde copia la nota no inventa; donde reformula, cambia un sintoma por otro,
    pone una localizacion por defecto o invierte el sentido;
  - descarta un signo o un estado de una sola palabra porque "no dice como se
    siente", y lee una frase sin sujeto como si hablara del servicio.

Por eso este prompt:
  1. FORMATO "razonado": el razonamiento deja de ser un defecto de formato y se
     vuelve un paso obligado y corto con cuatro casillas fijas (Del paciente /
     Duda / Niega / Tiempo). La primera es una COPIA de la nota: el motivo se
     arma despues solo con lo copiado, que es donde este modelo es fiel.
  2. Sin molde de salida para el embarazo ni para nada: ninguna plantilla con
     huecos que rellenar. Solo categorias, ninguna palabra clinica concreta.
  3. La decision de abstenerse se define por lo que NO es del paciente (tramite),
     y lo que si es incluye explicitamente signo visible, estado, diagnostico
     dentro de una remision, procedimiento y control.
  4. Traducir solo lo seguro; si no, copiar con la ortografia corregida.
  5. Segunda pasada: obliga a extraer, salvo que la nota sea unicamente tramite
     (ACLARACION del reglamento del 2026-09-24).
Los filtros de produccion (posprocesar) quedan intactos.
"""

from NLP import glosario                       # para el bloque de equivalencias por nota
from NLP.prompts import v1_7 as _base          # los filtros de produccion, SIN cambios

VERSION = "llama3.1-8b-r1"
FORMATO = "razonado"          # {"razonamiento": ..., "motivo": ...}: piensa y luego responde
OPCIONES = {"num_predict": 600}   # un JSON cortado es una salida vacia: margen de sobra

_TRAMITE_PRIMERA = ('- Si en "Del paciente" escribiste nada, el motivo es exactamente: '
                    'sin motivo clinico')
# Segunda pasada (ACLARACION del reglamento, 2026-09-24): puede abstenerse SOLO si la
# nota es unicamente tramite; en cualquier otro caso obliga a extraer.
_TRAMITE_SEGUNDA = ('- Solo si lo unico que trae la nota es tramite (de donde viene, quien lo '
                    'envia, que servicio o especialidad lo manda, que es urgente), el motivo es '
                    'exactamente: sin motivo clinico. En cualquier otro caso "Del paciente" no '
                    'es nada: copia ahi lo que la nota dice de el, y el motivo nunca es sin '
                    'motivo clinico.')

PROMPT = """Eres enfermero de triage en el servicio de urgencias de un hospital publico de \
Manizales, Colombia. Te llega UNA nota de triage escrita deprisa: con erratas, abreviaturas, \
palabras populares de la region y texto administrativo mezclado. Tu trabajo es sacar de ella \
el motivo de consulta, fiel a la nota: nada de mas y nada de menos.

Respondes SOLO con un objeto JSON de dos campos, en este orden: "razonamiento" y "motivo". \
Los dos en español.

CAMPO "razonamiento" (breve, maximo 80 palabras). Escribelo siempre con estas cuatro partes, \
en este orden:
Del paciente: las palabras de la nota que dicen algo del paciente, copiadas tal cual \
(solo corrige las erratas), separadas por punto y coma. Si no hay ninguna, escribe: nada.
Duda: si la nota no afirma algo sino que lo cree, lo supone o lo da como probable, que es; \
si todo esta afirmado, escribe: no.
Niega: lo que la nota dice que el paciente niega o no tiene (no el examen fisico normal); \
si no niega nada, escribe: nada.
Tiempo: desde cuando o hace cuanto le pasa, con las mismas palabras de la nota, y a que \
se refiere; si no lo dice, escribe: no dice. La fecha de un tramite, de una consulta \
anterior o de un procedimiento no es el inicio de lo que siente.

Que cuenta como "del paciente": todo lo que diga algo de su cuerpo o de su salud, aunque \
sea una sola palabra, este mal escrito o no lo entiendas del todo: lo que siente o le duele, \
como se ve o como esta, algo que le paso, una enfermedad o diagnostico que trae (tambien \
cuando viene dentro de una remision), un procedimiento o una cirugia que le hicieron, que \
viene a control o seguimiento de una condicion que tiene, que esta en embarazo, que es un \
niño. No hace falta que sea una queja ni que diga como se siente: un signo que se ve o un \
estado del paciente ya es motivo.
Una frase sin sujeto habla del paciente: "esta ..." o "tiene ..." describen al paciente, \
nunca al hospital ni al servicio. Aun asi, si la frase solo dice de donde viene o quien lo \
envio, es tramite.

Que NO es "del paciente" (es tramite): de donde viene, quien lo remitio, derivo, envio o \
trajo, como llego, una orden, una cita o una autorizacion, el nombre de la especialidad o \
del servicio que lo manda, que lo manden como urgente, los nombres de personas, \
instituciones, EPS y lugares, el examen fisico y los signos vitales normales, los avisos \
del hospital.

CAMPO "motivo": una sola linea, en minusculas, sin punto final.
{regla_tramite}
- Si copiaste algo, el motivo se arma SOLO con eso, y lo conserva todo: \
cada sintoma o hallazgo, donde es y de que lado (solo si la nota lo dice), quien o que lo \
causo (una persona, un animal, un objeto: como lo dice la nota, sin invertir quien hizo \
que), y la condicion que la nota da del paciente (embarazo con la cifra exacta que de la \
nota, edad pediatrica).
- Si "Duda" no es no: pon "posible" o "sospecha de" delante de lo dudoso. Nunca lo afirmes.
- Si "Niega" no es nada: agrega "niega" con cada cosa negada. Nunca la afirmes ni la borres.
- Si "Tiempo" no es no dice: agregalo con las mismas palabras de la nota. No lo cambies por \
otro dia ni lo redondees.
- Cada detalle (tiempo, intensidad, lado, lugar) va pegado al sintoma al que la nota se lo \
pone; no lo pases a otro.
- Usa el termino clinico solo cuando estes seguro de que dice exactamente lo mismo, en la \
misma direccion. Si dudas, deja la palabra de la nota con la ortografia corregida: una \
palabra copiada nunca es un error, una mal traducida si. Si la nota ya trae un termino \
medico, copialo: no lo cambies por uno mas general ni por uno parecido.
- NO agregues nada que la nota no diga: ni parte del cuerpo, ni lado, ni cifra, ni \
condicion de la paciente, ni causa, ni tiempo, ni intensidad. Si la nota no dice donde, el \
motivo no dice donde. Las cifras se copian exactas, con sus decimales.
- Escribelo como descripcion clinica breve, no en primera persona, sin frases como \
"el motivo es", sin nombres de personas ni de instituciones.

Si abajo aparece una lista del hospital: las EQUIVALENCIAS traducen bien la expresion de la \
izquierda; usalas cuando esa expresion sea parte del motivo. La TERMINOLOGIA DETECTADA es \
solo una pista: usa un termino de ahi solo si dice lo mismo que la nota; si la nota lo \
niega, va negado; si es mas vago que lo que dice la nota, quedate con la nota. Los LUGARES \
se eliminan.
{glosario}
NOTA DE TRIAGE:
{nota}

{cierre}"""

_CIERRE = ('Responde ahora con el JSON: primero "razonamiento" (Del paciente, Duda, Niega, '
           'Tiempo), despues "motivo" (el motivo de consulta, o sin motivo clinico si en '
           '"Del paciente" no hay nada).')
_CIERRE_SEGUNDA = ('Responde ahora con el JSON: primero "razonamiento" (Del paciente, Duda, '
                   'Niega, Tiempo), despues "motivo": el motivo de consulta que esta nota SI '
                   'trae. Aqui sin motivo clinico solo vale si la nota es unicamente tramite.')
_AVISO_SEGUNDA = (
    'AVISO: esta nota ya se reviso y SI dice algo del paciente: un sintoma, un signo, como '
    'se ve o como esta, una enfermedad, un procedimiento o una condicion que tiene. En "Del '
    'paciente" copia esa palabra o frase, aunque sea una sola, este mal escrita o venga '
    'dentro de una remision: una enfermedad, un signo, un estado, un procedimiento o una '
    'condicion nombrados junto a la remision son del paciente. Sigue todas las demas reglas: '
    'no agregues nada que la nota no diga. Unica excepcion: si al releerla lo unico que trae '
    'es tramite (de donde viene, quien lo envia, que servicio o especialidad lo manda, que es '
    'urgente), el motivo es sin motivo clinico; no copies el tramite ni inventes un sintoma.\n\n')


def _armar(nota: str, regla_tramite: str, cierre: str) -> str:
    nota = nota.strip()
    trozo = glosario.bloque(nota)
    return PROMPT.format(nota=nota, glosario=("\n" + trozo + "\n" if trozo else ""),
                         regla_tramite=regla_tramite, cierre=cierre)


def construir(nota: str) -> str:
    """El prompt completo para una nota, con las equivalencias del glosario que
    aparecen en ESA nota (nunca el glosario entero)."""
    return _armar(nota, _TRAMITE_PRIMERA, _CIERRE)


def posprocesar(original, salida):
    return _base.posprocesar(original, salida)


def construir_segunda_pasada(nota: str) -> str:
    """Red contra el descarte falso: la misma nota, con un aviso de que SI trae algo
    del paciente, la regla del tramite cambiada y un cierre que solo admite abstenerse
    si la nota es unicamente tramite (ACLARACION del reglamento): el detector que la
    dispara tambien marca tramites puros, y ahi obligar a responder solo deja copiar el
    tramite o inventar."""
    return _AVISO_SEGUNDA + _armar(nota, _TRAMITE_SEGUNDA, _CIERRE_SEGUNDA)
