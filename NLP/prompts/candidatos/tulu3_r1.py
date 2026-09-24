# -*- coding: utf-8 -*-
"""Prompt de tulu3:8b (Llama 3.1 8B de AllenAI), ronda 1.

Se corre como `tulu3-8b-sinsistema:latest`: su plantilla ignora el mensaje de
sistema, asi que todo va en el turno de usuario (lo que ya hace /api/generate).

QUE CAMBIA FRENTE A v1.7 Y POR QUE (medido con v1.7 sobre las 63 notas)
1. Instrucciones en ingles, salida en espanol. Tulu se entreno casi todo en
   ingles; la nota, las formas de salida y el cierre siguen en espanol.
2. Ningun molde de embarazo en el prompt general. El sufijo literal de la regla
   6 de v1.7 salio pegado en 15 notas sin embarazo (un varon incluido). Aqui el
   bloque de embarazo SOLO se inyecta si fidelidad.es_gestante(nota) lo afirma,
   igual que el glosario se inyecta por nota: lo que el modelo no lee, no lo copia.
3. Lo mismo para duda, negacion, tiempo y edad pediatrica: un bloque de
   comprobacion por nota, despues de la nota, solo con lo que ESA nota trae
   (detectores de produccion de NLP/fidelidad.py). La duda va con su tramo
   literal, que es texto de la propia nota.
4. "Conserva las palabras de la nota" en vez de "traduce todo a termino
   clinico": con v1.7 tulu cambiaba un sintoma por otro al normalizar. La lista
   de verificacion tolera el termino sin normalizar; no tolera el cambiado.
5. El glosario se enmarca como ayuda de vocabulario que no aporta hechos: un
   termino detectado dentro de una negacion sigue negado, y uno que la nota no
   afirma no entra (con v1.7 aparecio como sintoma suelto).
6. Segunda pasada en dos versiones (ACLARACION del reglamento): si la nota trae
   lenguaje de tramite, puede abstenerse cuando TODO es tramite; si no lo trae,
   cierre estricto como v1.7.
Ninguna frase ni termino de la muestra esta escrito en el prompt.
"""
import re

from NLP import fidelidad, glosario
from NLP.prompts import v1_7 as _base

VERSION = "tulu3-r1"
FORMATO = None
OPCIONES = {}

PROMPT = """You standardize the reason for consultation ("motivo de consulta") in triage notes from the emergency department of a public hospital in Manizales, Colombia. The notes are Colombian Spanish typed in a hurry: typos, hospital abbreviations, regional slang, the patient's own words, and paperwork mixed in.

Read the note and write ONE line in Spanish: the reason for consultation, or exactly: sin motivo clinico

FIRST DECIDE: does the note say anything about the patient?
Anything about the patient's own body or health counts: a symptom or complaint, how they feel, how they look, a change they noticed, something that happened to them, a disease they have, a procedure done to them, a test result, a check-up or follow-up of a condition. One word is enough, even misspelled or in slang.
- If there is at least one such thing, write it. Discarding a note that has one is the worst error: the patient disappears from the count.
- Write sin motivo clinico only when the note contains nothing but paperwork: where the patient comes from, who sent or brought them, how they arrived, an order or an appointment that does not say what it is for, how urgent the referral is, the name of a hospital service or specialty; or when the text is empty or cut off. Never fill such a note with a typical complaint: that invents a patient.

THEN WRITE THE REASON, FAITHFULLY
1. Only what the note says. Every body part, side, number, time, cause, intensity and person in your answer must be written in the note. If the note does not say where a complaint is, your answer does not say where either. A short faithful answer is correct; a detailed invented one is wrong.
2. Keep the note's own words. If the note's word for the complaint is clear, keep it: fix the spelling and write it as a short phrase in third person. Use a medical term only when it means exactly the same thing; if you are not sure, keep the note's word. Never replace a complaint with a different one, a feeling with a diagnosis, or a general complaint with a specific one, and never reverse a direction (more/less, up/down, better/worse).
3. Keep who or what caused an injury exactly as the note says. Do not change it into another cause and do not add one.
4. Leave out: names of people, doctors, institutions, insurers and places; who referred, brought or accompanies the patient; vital signs, normal exam findings and administrative text.
5. Keep every detail the note gives about the complaint: where it is and on which side, how long or since when, how strong, what the note denies, and what the note presents as uncertain (it stays uncertain).
6. Do not diagnose and do not guess. Write what the note states, not what you think is behind it. An abbreviation you cannot read with certainty is left out, not guessed.
7. Format: one line, in Spanish, lowercase, no quotes, no labels, no explanation.

Before answering, compare your line with the note: remove anything the note does not say, and put back any detail from rule 5 that you dropped.
{glosario}
NOTA DE TRIAGE:
{nota}
{revisar}
RESPUESTA (el motivo de consulta en una linea, en espanol, o sin motivo clinico si la nota no dice nada del paciente):"""

_GLOSARIO = """
HOSPITAL VOCABULARY FOR THIS NOTE. The lists below come from the hospital's dictionary and only cover words that appear in this note. An equivalence (left = right) gives the standard term for an expression the note uses: use it when the note uses that expression with that meaning. The other lists are spelling and vocabulary aids. No list adds facts: a term goes into your answer only if the note itself affirms it, a term inside a denial stays denied, and listed places and institutions are left out (rule 4).

{bloque}
"""

# ---------- comprobaciones por nota ----------
# Cada una se inyecta solo si la nota trae ese rasgo. Hablan de categorias; lo
# unico literal es texto de la propia nota o la forma de salida en espanol.

_EMBARAZO = ("- Pregnancy: the note says the patient is pregnant, and that is always something about "
             "the patient. Your answer must end with it: en gestante de N semanas, with exactly the "
             "weeks the note gives (same number, decimals included), or just: en gestante, if the "
             "note gives no weeks. Never write a number of weeks the note does not give.")

_NINO = ("- Age: the note says the patient is a child or a minor. Keep that in your answer, with the "
         "note's own word for it.")

_DUDA = ("- Uncertainty: the note presents this as uncertain, not confirmed: {tramos}. In your answer "
         "it stays uncertain: write posible or sospecha de in front of that item. Never state it as a "
         "fact. What the note states as certain stays certain.")

_NIEGA = ("- Denials: the note explicitly denies something: {tramos}. Keep every denial in your "
          "answer, complete, as: niega ... Never write a denied item as something the patient has, "
          "and never drop the denial.")

_TIEMPO = ("- Time: the note says when the complaint started or how long it has lasted. Keep it with "
           "exactly the same meaning (same number, same unit, same day word; a day word never becomes "
           "another one) and attach it to the complaint it belongs to. The day of an earlier visit or "
           "procedure is not when the complaint started.")

_REVISAR = "\nCHECK YOUR ANSWER AGAINST THIS NOTE:\n{lineas}\n"

# Edad pediatrica: las formas generales de nombrar a un menor de 18 anos.
_MENOR = re.compile(r"\bmenor(?:es)? de edad\b|\bmenor de \d+ anos\b|\bnin[oa]s?\b|\blactantes?\b|"
                    r"\bbebes?\b|\brecien nacid[oa]s?\b|\bneonat\w*|\bpediatric\w*|\binfantes?\b|"
                    r"\bpreescolar(?:es)?\b|\bescolar(?:es)?\b|\badolescentes?\b")


_VACIAS = set("los las del con por para que una uno sus mas muy".split())


def _cita(tramos):
    return "; ".join("«" + t + "»" for t in tramos)


def _tramos_duda(p):
    tramos = []
    for inicio, _, fin in fidelidad._tramos_en_duda(p):
        t = " ".join(p[inicio:fin].split()[:10]).strip(" ,.;:'\"")
        if t and t not in tramos:
            tramos.append(t)
    return tramos[:3]


# Donde termina lo negado: fin de frase, otro verbo del relato o una negacion
# nueva ('no dolor a la palpacion' ya es examen). La coma NO corta: en 'niega X,
# Y' la lista entera va negada.
_FIN_NIEGA = re.compile(r"[.;:\n(\"*]|\b(?:refiere|refiriendo|presenta|con|pero|ademas|tiene|niega|"
                        r"niegan|se|paciente|ahora|hoy|no|sin|porque|pues|ya que|desde|hace)\b")


def _tramos_niega(p):
    """Cada 'niega X' de la nota, sin los genericos ('niega otros sintomas'),
    maximo 8 palabras. Detecta con el mismo patron de produccion."""
    tramos = []
    for m in fidelidad._NIEGA.finditer(p):
        fin = _FIN_NIEGA.search(p, m.end())
        hasta = min(fin.start() if fin else len(p), m.end() + 70)
        palabras = p[m.start():hasta].split()
        contenido = [w for w in fidelidad.palabras(" ".join(palabras[1:]))
                     if len(w) >= 3 and w not in fidelidad._NEGADO_GENERICO and w not in _VACIAS]
        if not contenido:
            continue
        t = " ".join(palabras[:8]).strip(" ,.;:'\"")
        if t not in tramos:
            tramos.append(t)
    return tramos[:4]


# Las semanas de gestacion no son la duracion del cuadro: sin esto, cada nota de
# gestante recibia el aviso de tiempo por sus semanas.
_SEMANAS_GESTACION = re.compile(
    r"gestante\w*\s+(?:de|con)\s+\d+(?:[.,]\d+)?\s*\.?\s*[a-z]+|"
    r"\d+(?:[.,]\d+)?\s*\.?\s*[a-z]+\s+de\s+gest[a-z]*|\d+(?:[.,]\d+)?\s*(?:sdg|sms)\b")


# La edad tampoco: 'paciente de 45 anos' no es un cuadro de 45 anos.
_EDAD = re.compile(
    r"\d+\s*(?:anos|meses|dias)\s+de\s+(?:edad|vida|nacid\w*)|\bedad\s*:?\s*\d+\s*\w*|"
    r"\b(?:paciente|pte|nin[oa]|lactante|bebe|menor|hombre|mujer|masculino|femenino|senora?|"
    r"adulto|adulta|adolescente|joven|anciano|anciana|recien nacid[oa])\s+(?:de\s+)?\d+\s*"
    r"(?:anos|meses|dias|a)\b")


def _tiene_tiempo(nota, p):
    p = _EDAD.sub(" ", p)
    if fidelidad.es_gestante(nota):
        p = _SEMANAS_GESTACION.sub(" ", p)
    return bool(fidelidad.duraciones(p, errata=True))


def _comprobaciones(nota):
    p = fidelidad.plano(nota)
    lineas = []
    if fidelidad.es_gestante(nota):
        lineas.append(_EMBARAZO)
    if _MENOR.search(p):
        lineas.append(_NINO)
    duda = _tramos_duda(p)
    if duda:
        lineas.append(_DUDA.format(tramos=_cita(duda)))
    niega = _tramos_niega(p)
    if niega:
        lineas.append(_NIEGA.format(tramos=_cita(niega)))
    if _tiene_tiempo(nota, p):
        lineas.append(_TIEMPO)
    return _REVISAR.format(lineas="\n".join(lineas)) if lineas else ""


def construir(nota: str) -> str:
    nota = nota.strip()
    trozo = glosario.bloque(nota)
    return PROMPT.format(nota=nota,
                         glosario=_GLOSARIO.format(bloque=trozo) if trozo else "",
                         revisar=_comprobaciones(nota))


def posprocesar(original, salida):
    return _base.posprocesar(original, salida)


# ---------- segunda pasada: red contra el descarte falso ----------

_CIERRE = ("RESPUESTA (el motivo de consulta en una linea, en espanol, o sin motivo clinico si la "
           "nota no dice nada del paciente):")
_CIERRE_SEGUNDA = ("RESPUESTA (el motivo de consulta que esta nota SI trae, en una linea, en espanol; "
                   "aqui la respuesta sin motivo clinico no es valida):")
_AVISO_SEGUNDA = ("NOTICE: this note was already reviewed and it DOES say something about the patient: "
                  "a complaint, how they feel or look, an injury, a disease, a procedure, a test result "
                  "or a check-up. Your job is to find it and write it, even if it is a single word, "
                  "misspelled, in slang, or mixed with a referral. All the other rules still apply: "
                  "write only what the note says, and add nothing.\n\n")

# ACLARACION del reglamento (2026-09-24): la segunda pasada puede abstenerse solo
# si la nota es puro tramite. Se usa este cierre SOLO cuando la nota trae lenguaje
# de tramite (el mismo patron de produccion, fidelidad._TRAMITE); una nota sin
# tramite no puede ser tramite puro y conserva el cierre estricto.
_CIERRE_SEGUNDA_TRAMITE = ("RESPUESTA (lo que esta nota dice del paciente, en una linea, en espanol; "
                           "sin motivo clinico solo si todo en la nota es tramite):")
_AVISO_SEGUNDA_TRAMITE = ("NOTICE: an automatic check found a word in this note that may be about the "
                          "patient. Read it again carefully. If the note says anything about the patient "
                          "- a complaint, how they feel or look, an injury, a disease, a procedure, a test "
                          "result or a check-up, including the reason given for a referral - write it; that "
                          "is almost always the case. Only if every word of the note is paperwork (where "
                          "the patient comes from, who sent or brought them, which service or specialty "
                          "sends them, that it is urgent) is the answer: sin motivo clinico. All the other "
                          "rules still apply: write only what the note says, and add nothing.\n\n")


def construir_segunda_pasada(nota: str) -> str:
    prompt = construir(nota)
    assert _CIERRE in prompt, "el cierre del prompt cambio: actualizar _CIERRE"
    if fidelidad._TRAMITE.search(fidelidad.plano(nota)):
        return _AVISO_SEGUNDA_TRAMITE + prompt.replace(_CIERRE, _CIERRE_SEGUNDA_TRAMITE)
    return _AVISO_SEGUNDA + prompt.replace(_CIERRE, _CIERRE_SEGUNDA)
