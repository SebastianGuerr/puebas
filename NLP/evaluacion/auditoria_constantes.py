"""
Constantes de la auditoria del pipeline: nombres de columna, expresiones
regulares, tablas de simbolos y los casos fijos de regresion y de typos de
control. Separado de auditoria_medicion.py (E6.2, division de archivos
grandes) porque ambos, y auditoria_dano.py, leen estas mismas tablas.
Ver docs/ARQUITECTURA.md #2.9.
"""

import csv
import re

from NLP import rutas

CSV_POR_DEFECTO = rutas.TRIAGE_LIMPIO

csv.field_size_limit(10 ** 7)

COL_ID = "OID"
COL_ORIGINAL = "texto_original"
COL_CORREGIDO = "texto_corregido"
COL_NORMALIZADO = "texto_normalizado"

RE_TOKEN = re.compile(r"\S+")
RE_PALABRA = re.compile(r"[a-záéíóúüñ]+")

# Delimitador de palabra para las busquedas de errores de control. Se construye
# desde el codigo del caracter para que ninguna edicion posterior lo convierta
# por accidente en un retroceso, cosa que ya ocurrio una vez y dejo el informe
# dando todo por correcto sin serlo.
LIMITE = chr(92) + "b"

# puntuacion que rodea a un token sin formar parte de la palabra
PUNTUACION_BORDE = ".,;:!?()[]{}\"' "

# marcas del reporte para lo que no es un reemplazo 1 a 1
BORRADO = "<borrado>"
INSERTADO = "<insertado>"

# Simbolos que en una nota clinica son contenido y no adorno. Se mide que
# proporcion sobrevive a la limpieza: perderlos cambia el significado de la
# nota, porque separan hallazgos o marcan que algo es una sospecha.
SIMBOLOS_CLINICOS = {
    "+": "suma de hallazgos",
    "?": "sospecha diagnostica",
    "(": "aclaracion",
    "<": "menor que",
    ">": "mayor que",
}

# Simbolos que NO deben sobrevivir: no son contenido, solo marcan division, y
# la limpieza los convierte en el separador indicado. Se miden aparte para que
# su desaparicion no cuente como perdida; lo que se verifica es que la division
# que marcaban siga representada.
#
# El asterisco queda fuera de esta tabla porque en el corpus es casi siempre una
# marca al final de la nota, que no separa nada: exigirle un separador de
# reemplazo reportaba un fallo inexistente.
SIMBOLOS_CONVERTIDOS = {
    "-": ("guion separador de lista", ","),
}

PROPORCION_MAYUSCULAS = 0.9

# Corrupciones confirmadas en corridas anteriores. Cada entrada es un termino
# clinico real que el pipeline convirtio en otra palabra, identificado por el
# OID de la nota donde ocurrio. Son la prueba de regresion: si alguna vuelve, el
# cambio que se estaba evaluando no sirve.
REGRESIONES = [
    (747111, "stemi", "IAM con elevacion del ST, se convirtio en 'stent'"),
    (726448, "fazecas", "escala de Fazekas, se convirtio en 'canecas'"),
    (786557, "taquicardico", "adjetivo clinico, se convirtio en 'taquicardia'"),
    (793242, "fomag", "fondo del magisterio, se convirtio en 'toma'"),
    (773416, "ir", "insulinorrequiriente en 'DM no IR', quedo como el verbo ir"),
    # Los tres que produjo la capa de contexto al puntuar con el promedio de los
    # subtokens en vez de con la suma. El promedio premiaba a los candidatos con
    # mas piezas, de modo que partir una palabra siempre ganaba.
    (815839, "dorada", "municipio de Caldas, se convirtio en 'morada'"),
    (803472, "afiliados", "palabra correcta, se partia en 'afilia dos'"),
]

# La prueba en sentido contrario. Son errores de digitacion inequivocos:
# ninguno es palabra del espanol ni terminologia, y todos aparecen decenas de
# veces en el corpus. Si alguno sobrevive a la correccion, hay una defensa
# pasada de rosca. Ver la explicacion en docs/ARQUITECTURA.md #2.9.
TYPOS_QUE_DEBEN_CORREGIRSE = [
    ("pacinete", "paciente"),
    ("apciente", "paciente"),
    ("paicnete", "paciente"),
    ("consutla", "consulta"),
    ("dolro", "dolor"),
    ("malestra", "malestar"),
    ("evolcuion", "evolución"),
    ("abodminal", "abdominal"),
    ("refeire", "refiere"),
    ("hipotirodismo", "hipotiroidismo"),
]


