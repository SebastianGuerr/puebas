# -*- coding: utf-8 -*-
"""La cadena completa de UNA nota: prompt, modelo, limpieza, filtros y red de seguridad.

    salida, pasada = procesar_nota(texto, modulo_prompt, generar)

    pasada  'primera'  la primera respuesta, ya filtrada, es la que queda
            'segunda'  la primera fue un descarte falso y la segunda pasada lo arreglo
            'revisar'  descartada dos veces aunque la nota trae algo clinico: queda
                       'sin motivo clinico' Y marcada para que la mire una persona

POR QUE EXISTE LA SEGUNDA PASADA
    El descarte falso es el peor error del proyecto: el paciente sale de la cuenta
    diaria, que es justo el desenlace que se quiere predecir. Medido el 2026-09-24,
    ademas es INESTABLE: la misma nota ('remitida por... hernia discal') salio bien
    en una corrida y descartada en otra, con el mismo modelo y el mismo prompt. En
    las notas limite el modelo adivina.

    No se arregla con mas prompt -- cada vuelta que empujaba contra el descarte
    hacia inventar en otras notas (ver docs/CONTEXTO.md, el balancin) --. Se arregla
    con un paso mas: si la salida es 'sin motivo clinico' y la nota trae evidencia
    clinica (fidelidad.necesita_segunda_pasada), se repite con un prompt que no
    admite abstenerse. Cuesta una llamada mas solo en esas notas.

    Si la segunda tambien descarta, o inventa (tiene banderas fuertes), no se fuerza
    nada: queda el descarte y la marca 'revisar'. Una persona decide. Es preferible
    un descarte marcado a un motivo inventado sin marcar.
"""
from NLP import fidelidad
from NLP import modelo as motor


def _limpia(generar, prompt, texto, posprocesar):
    salida = motor.limpiar(generar(prompt))
    return posprocesar(texto, salida) if salida else salida


def procesar_nota(texto, modulo, generar, filtros=True):
    """
    texto    la nota tal como viene de la base
    modulo   el modulo de prompt: construir(), y opcionales posprocesar() y
             construir_segunda_pasada()
    generar  funcion prompt -> respuesta cruda del modelo (texto)
    filtros  False mide al modelo solo: sin posprocesar y sin segunda pasada
    """
    if not filtros:
        return motor.limpiar(generar(modulo.construir(texto))), "primera"

    posprocesar = getattr(modulo, "posprocesar", lambda original, salida: salida)
    primera = _limpia(generar, modulo.construir(texto), texto, posprocesar)
    if not fidelidad.necesita_segunda_pasada(texto, primera):
        return primera, "primera"

    construir_2 = getattr(modulo, "construir_segunda_pasada", None)
    if construir_2 is None:
        return primera, "revisar"

    segunda = _limpia(generar, construir_2(texto), texto, posprocesar)
    sigue_descartada = fidelidad.plano(segunda).strip() in ("", fidelidad.SIN_MOTIVO)
    if sigue_descartada or fidelidad.es_fallo(fidelidad.revisar(texto, segunda)):
        return fidelidad.SIN_MOTIVO, "revisar"
    return segunda, "segunda"
