# -*- coding: utf-8 -*-
"""Cliente de Ollama: comprueba el servidor y genera una respuesta por nota.

Es el unico modulo que habla con el modelo. Ver NLP/docs/FLUJO.md.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

_PENSAMIENTO = re.compile(r"<think>.*?</think>", re.S | re.I)
_ETIQUETA = re.compile(r"^\s*(#+\s*)?(motivo(\s+de\s+consulta)?|respuesta)\s*:?\s*", re.I)


def limpiar(texto):
    """Quita el bloque de razonamiento de los modelos que piensan en voz alta,
    el encabezado que algunos repiten, y deja una sola linea."""
    texto = _PENSAMIENTO.sub(" ", texto or "")
    texto = texto.replace("<think>", " ").replace("</think>", " ")
    lineas = [l.strip() for l in texto.strip().splitlines() if l.strip()]
    if not lineas:
        return ""
    linea = _ETIQUETA.sub("", lineas[0]).strip(' "\'`*')
    # si la primera linea era solo el encabezado, el contenido va en la siguiente
    if not linea and len(lineas) > 1:
        linea = _ETIQUETA.sub("", lineas[1]).strip(' "\'`*')
    return linea


def instalados():
    """Nombres exactos de los modelos que Ollama tiene descargados.

    Devuelve ([], motivo) si el servidor no contesta, para que verificar()
    pueda decir QUE fallo en vez de dar siempre el mismo consejo.
    """
    try:
        datos = json.loads(urllib.request.urlopen(OLLAMA + "/api/tags", timeout=30).read())
        return [m["name"] for m in datos.get("models", [])], None
    except Exception as error:
        return [], "%s: %s" % (type(error).__name__, error)


def verificar(modelo):
    """Falla antes de empezar, y con un mensaje util, si el modelo no esta.

    Sin esto una corrida arranca, crea el CSV vacio y se cae en la primera nota
    con un 404 crudo.
    """
    nombres, fallo = instalados()
    if fallo is not None:
        raise SystemExit(
            "No se pudo consultar Ollama en %s.\nDetalle: %s\n\n"
            "Si el servidor esta apagado, arrancalo con:  ollama serve\n"
            "En Windows la aplicacion de la bandeja ya lo arranca sola: comprueba\n"
            "con  curl http://127.0.0.1:11434/api/tags  antes de reintentar."
            % (OLLAMA, fallo))
    if modelo in nombres or (modelo + ":latest") in nombres:
        return
    raise SystemExit(
        "El modelo '%s' no esta instalado.\n\n"
        "Ollama tiene ahora mismo:\n%s\n\n"
        "Descargalo con:   ollama pull %s\n"
        "O pasa el nombre exacto de la lista con  --modelo"
        % (modelo, "\n".join("  " + n for n in nombres), modelo))


def generar(modelo, prompt, timeout):
    """Una llamada a Ollama. Intenta apagar el modo razonamiento; si el modelo
    no lo admite, repite la llamada sin esa opcion."""
    base = {
        "model": modelo,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0, "top_p": 1, "seed": 7,
                    "num_predict": 200, "num_ctx": 4096},
    }
    for cuerpo in ({**base, "think": False}, base):
        datos = json.dumps(cuerpo).encode("utf-8")
        peticion = urllib.request.Request(
            OLLAMA + "/api/generate", datos, {"Content-Type": "application/json"})
        try:
            inicio = time.time()
            respuesta = json.loads(urllib.request.urlopen(peticion, timeout=timeout).read())
            return time.time() - inicio, respuesta
        except urllib.error.HTTPError as error:
            if error.code == 400 and "think" in cuerpo:
                continue          # el modelo no razona: se reintenta sin la opcion
            raise
    raise RuntimeError("no se pudo generar")
