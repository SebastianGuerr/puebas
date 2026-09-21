# -*- coding: utf-8 -*-
"""Busca en los diccionarios del proyecto los terminos que aparecen en una nota.

El modelo no conoce el habla de Caldas ni las siglas de este hospital, y cuando
no las conoce se las inventa. En vez de meterle un glosario entero en el prompt
—que ademas lo contaminaria: ya se vio en v2 y v4 que cualquier palabra escrita
en el prompt termina saliendo en las respuestas— se le pasan **solo las entradas
que de verdad aparecen en la nota que esta leyendo**.

Las cuatro fuentes viven juntas en NLP/recursos/ y son lo unico que da contexto
al modelo:

    NLP/recursos/siglas.json               siglas, abreviaturas, nombres propios
    NLP/recursos/coloquialismos.json       habla popular colombiana y caldense
    NLP/recursos/lugares.csv               municipios y departamentos DIVIPOLA
    NLP/recursos/terminologia_clinica.json variantes y terminos canonicos

Se respetan las politicas que los propios diccionarios declaran:
  - de las siglas solo se expanden los grupos marcados `_grupos_expandibles`, y
    nunca las que estan en `_siglas_ambiguas`;
  - un coloquialismo que declara `contexto` solo se ofrece si alguna de esas
    palabras esta en la nota (asi `fuego` sale como herpes labial cuando la nota
    habla del labio, y no cuando habla de un arma).
"""
import csv
import json
import os
import re
import unicodedata

RECURSOS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "recursos")
SIGLAS = os.path.join(RECURSOS, "siglas.json")
COLOQUIAL = os.path.join(RECURSOS, "coloquialismos.json")
LUGARES_COLOMBIA = os.path.join(RECURSOS, "lugares.csv")
CATALOGO_SINTOMAS = os.path.join(RECURSOS, "terminologia_clinica.json")


def _sin_tildes(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower())
                   if unicodedata.category(c) != "Mn")


def _cargar():
    siglas = json.load(open(SIGLAS, encoding="utf-8"))
    coloquial = json.load(open(COLOQUIAL, encoding="utf-8"))

    expandibles = set(siglas.get("_grupos_expandibles", []))
    ambiguas = {s.lower() for s in siglas.get("_siglas_ambiguas", [])}
    propios = ("instituciones_marcas", "geografia")

    equivalencias, nombres = {}, {}
    erratas = {k.lower(): v for k, v in (siglas.get("correcciones_directas") or {}).items()
               if not k.startswith("_") and isinstance(v, str)}

    for grupo in expandibles:
        for clave, valor in (siglas.get(grupo) or {}).items():
            if clave.lower() in ambiguas or not isinstance(valor, str):
                continue
            equivalencias[clave.lower()] = valor

    for grupo in propios:
        for clave, valor in (siglas.get(grupo) or {}).items():
            if isinstance(valor, str):
                nombres[clave.lower()] = valor

    for grupo, entradas in coloquial.items():
        if grupo.startswith("_") or not isinstance(entradas, dict):
            continue
        for clave, valor in entradas.items():
            equivalencias[clave.lower()] = valor

    return equivalencias, nombres, erratas


_EQUIVALENCIAS, _NOMBRES, _ERRATAS = _cargar()


def _cargar_lugares():
    """Carga pares municipio-departamento de DIVIPOLA para el prompt."""
    if not os.path.exists(LUGARES_COLOMBIA):
        return []
    with open(LUGARES_COLOMBIA, encoding="utf-8-sig", newline="") as archivo:
        return [
            (fila["municipio"].strip(), fila["departamento"].strip())
            for fila in csv.DictReader(archivo)
            if fila.get("municipio") and fila.get("departamento")
        ]


_LUGARES = _cargar_lugares()


def _cargar_terminos_clinicos():
    """Carga variantes del catálogo de síntomas y su término canónico."""
    if not os.path.exists(CATALOGO_SINTOMAS):
        return []
    with open(CATALOGO_SINTOMAS, encoding="utf-8") as archivo:
        datos = json.load(archivo)

    terminos = []
    for canonico, informacion in datos.get("sintomas", {}).items():
        variantes = informacion.get("variantes", [])
        for variante in {canonico, *variantes}:
            if variante:
                terminos.append((variante, canonico))
    return sorted(terminos, key=lambda par: len(par[0]), reverse=True)


_TERMINOS_CLINICOS = _cargar_terminos_clinicos()


def _aparece(clave, nota_plana):
    """Coincidencia por palabra completa, sin tildes y sin distinguir mayusculas.

    El limite de palabra importa: sin el, 'pop' coincidiria dentro de 'popo' y se
    expandiria a postoperatorio una nota que habla de deposiciones.
    """
    patron = r"(?<![0-9a-z])" + re.escape(_sin_tildes(clave)) + r"(?![0-9a-z])"
    return re.search(patron, nota_plana) is not None


def buscar(nota):
    """Devuelve (equivalencias, nombres_propios, erratas) presentes en la nota.

    Cada elemento es una tupla (tal_como_aparece, significado).
    """
    plana = _sin_tildes(nota)
    halladas, propios, fallos = [], [], []

    for clave, valor in _EQUIVALENCIAS.items():
        if isinstance(valor, dict):
            contexto = [c for c in valor.get("contexto", [])]
            significado = valor.get("significado")
            if contexto and not any(_aparece(c, plana) for c in contexto):
                continue
        else:
            significado = valor
        if significado and _aparece(clave, plana):
            halladas.append((clave, significado))

    for clave, valor in _NOMBRES.items():
        if _aparece(clave, plana):
            propios.append((clave, valor))

    for clave, valor in _ERRATAS.items():
        if _aparece(clave, plana):
            fallos.append((clave, valor))

    # las expresiones largas primero: son las mas especificas y las mas utiles
    halladas.sort(key=lambda p: (-len(p[0]), p[0]))
    propios.sort(key=lambda p: (-len(p[0]), p[0]))
    fallos.sort(key=lambda p: (-len(p[0]), p[0]))
    return halladas, propios, fallos


def buscar_lugares(nota):
    """Devuelve los municipios o departamentos de DIVIPOLA presentes en la nota."""
    plana = _sin_tildes(nota)
    encontrados = []
    departamentos = set()
    for municipio, departamento in _LUGARES:
        aparece_municipio = _aparece(municipio, plana)
        aparece_departamento = _aparece(departamento, plana)
        if aparece_municipio:
            encontrados.append((municipio, departamento))
            departamentos.add(_sin_tildes(departamento))
        elif aparece_departamento and _sin_tildes(departamento) not in departamentos:
            encontrados.append(("", departamento))
            departamentos.add(_sin_tildes(departamento))
    return encontrados


def buscar_terminos_clinicos(nota):
    """Devuelve términos canónicos cuyas variantes aparecen en la nota."""
    plana = _sin_tildes(nota)
    encontrados = []
    vistos = set()
    for variante, canonico in _TERMINOS_CLINICOS:
        if _aparece(variante, plana) and _sin_tildes(canonico) not in vistos:
            encontrados.append(canonico)
            vistos.add(_sin_tildes(canonico))
    return encontrados


def bloque(nota, maximo=12):
    """Arma el trozo de prompt con lo que se encontro. Cadena vacia si no hay nada."""
    halladas, propios, fallos = buscar(nota)
    lugares = buscar_lugares(nota)
    terminos = buscar_terminos_clinicos(nota)
    if not halladas and not propios and not fallos and not lugares and not terminos:
        return ""

    partes = []
    if halladas:
        ancho = max(len(c) for c, _ in halladas[:maximo])
        lineas = "\n".join("   %-*s  =  %s" % (ancho, c, s) for c, s in halladas[:maximo])
        partes.append(
            "EQUIVALENCIAS DEL HOSPITAL QUE APARECEN EN ESTA NOTA\n\n"
            "Salen del diccionario del hospital y son fiables. Donde la nota use la "
            "expresion de la izquierda, tu respuesta usa el termino de la derecha, no tu "
            "propia interpretacion.\n\n" + lineas)

    if fallos:
        ancho = max(len(c) for c, _ in fallos[:maximo])
        lineas = "\n".join("   %-*s  ->  %s" % (ancho, c, s) for c, s in fallos[:maximo])
        partes.append(
            "ERRATAS CONOCIDAS EN ESTA NOTA\n\n"
            "Son errores de digitacion ya verificados a mano por el equipo. Lee la nota "
            "con estas palabras ya corregidas:\n\n" + lineas)

    if propios:
        lista = ", ".join(c for c, _ in propios[:maximo])
        partes.append(
            "NOMBRES PROPIOS QUE APARECEN EN ESTA NOTA\n\n"
            "Son instituciones o lugares, no dolencias. Eliminalos, como dice la regla 4:\n"
            "   " + lista)

    if lugares:
        lineas = []
        for municipio, departamento in lugares[:maximo]:
            if municipio:
                lineas.append(f"   municipio: {municipio} | departamento: {departamento}")
            else:
                lineas.append(f"   departamento: {departamento}")
        partes.append(
            "LUGARES DE COLOMBIA QUE APARECEN EN ESTA NOTA\n\n"
            "Se obtuvieron del listado oficial DIVIPOLA. Son lugares, no dolencias; "
            "eliminalos de la respuesta:\n\n" + "\n".join(lineas))

    if terminos:
        partes.append(
            "TERMINOLOGIA CLINICA DETECTADA\n\n"
            "Estas expresiones coinciden con el catálogo clínico del proyecto. "
            "Conserva el término si representa lo que afirma la nota:\n\n"
            + "\n".join(f"   {termino}" for termino in terminos[:maximo]))

    return "\n\n".join(partes)
