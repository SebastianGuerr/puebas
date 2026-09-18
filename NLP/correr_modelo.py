# -*- coding: utf-8 -*-
"""Motor compartido de las corridas de comparacion de modelos.

Lee `NLP/banco_triage_30.csv`, le pasa cada nota al modelo con el prompt de
`NLP/prompt_normalizacion.py` y escribe el resultado en
`NLP/resultado_<etiqueta>.csv` **nota por nota**: procesa una, la guarda y cierra
el archivo antes de pedir la siguiente. Si la corrida se corta a mitad de camino,
lo ya escrito queda en disco y al volver a lanzarla retoma donde iba.

No se conecta a ninguna base de datos: solo lee el CSV del banco y habla con
Ollama en localhost.
"""
import csv
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

from NLP.prompt_normalizacion import VERSION, construir

csv.field_size_limit(10 ** 7)

RAIZ = os.path.dirname(os.path.abspath(__file__))
BANCO = os.path.join(RAIZ, "banco_triage_50.csv")
OLLAMA = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")

COLUMNAS = ["corrida", "fecha", "ID", "estrato", "origen", "n_chars", "HCTMOTCON",
            "salida_esperada", "salida_modelo", "modelo",
            "segundos", "tok_entrada", "tok_salida", "veredicto_propietario"]

_PENSAMIENTO = re.compile(r"<think>.*?</think>", re.S | re.I)
_ETIQUETA = re.compile(r"^\s*(#+\s*)?(motivo(\s+de\s+consulta)?|respuesta)\s*:?\s*", re.I)


def cargar_muestra_antigua(ruta, limite=100):
    """Convierte los primeros OID del CSV antiguo al formato del corredor."""
    with open(ruta, encoding="utf-8-sig", newline="") as archivo:
        filas = list(csv.DictReader(archivo))[:limite]

    requeridas = {"OID", "texto_original", "texto_embedding"}
    faltantes = requeridas - set(filas[0]) if filas else requeridas
    if faltantes:
        raise ValueError(
            "Faltan columnas en triage_limpio_antiguo.csv: "
            + ", ".join(sorted(faltantes))
        )

    return [
        {
            "ID": fila["OID"],
            "estrato": "triage_limpio_antiguo",
            "origen": "OID:" + fila["OID"],
            "n_chars": str(len(fila["texto_original"])),
            "HCTMOTCON": fila["texto_original"],
            "salida_esperada": fila["texto_embedding"],
        }
        for fila in filas
    ]


def _limpiar(texto):
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


def _migrar(destino):
    """Deja el CSV existente listo para recibir una corrida nueva debajo.

    Los archivos de la primera version no tienen las columnas `corrida` ni
    `fecha`. Se reescriben con el encabezado nuevo, marcando lo que ya estaba
    como 'v1', y se guarda una copia .bak. No se borra ninguna fila: las
    corridas nuevas se anaden al final.
    """
    with open(destino, encoding="utf-8-sig", newline="") as f:
        viejas = list(csv.DictReader(f))
    if not viejas or "corrida" in viejas[0]:
        return len(viejas)

    os.replace(destino, destino + ".bak")
    for fila in viejas:
        fila["corrida"] = "v1"
        fila["fecha"] = ""
    with open(destino, "w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=COLUMNAS, extrasaction="ignore")
        escritor.writeheader()
        escritor.writerows(viejas)
    print("Se conservaron %d filas anteriores, marcadas como 'v1'." % len(viejas))
    print("Copia de seguridad en %s" % (os.path.basename(destino) + ".bak"))
    return len(viejas)


def _instalados():
    """Nombres exactos de los modelos que Ollama tiene descargados."""
    try:
        datos = json.loads(urllib.request.urlopen(OLLAMA + "/api/tags", timeout=30).read())
        return [m["name"] for m in datos.get("models", [])]
    except Exception:
        return []


def _verificar(modelo):
    """Falla antes de empezar, y con un mensaje util, si el modelo no esta.

    Sin esto una corrida arranca, crea el CSV vacio y se cae en la primera nota
    con un 404 crudo: fue justo lo que paso con medgemma y biomistral, que en
    esta maquina estan instalados con otro nombre.
    """
    nombres = _instalados()
    if not nombres:
        raise SystemExit(
            "Ollama no responde en %s.\nArranca el servidor con:  ollama serve" % OLLAMA)
    if modelo in nombres or (modelo + ":latest") in nombres:
        return
    raise SystemExit(
        "El modelo '%s' no esta instalado.\n\n"
        "Ollama tiene ahora mismo:\n%s\n\n"
        "Descargalo con:   ollama pull %s\n"
        "O, si ya lo bajaste con otro nombre, copia el nombre exacto de la lista\n"
        "de arriba a la constante MODELO del archivo correr_*.py que estas corriendo."
        % (modelo, "\n".join("  " + n for n in nombres), modelo))


def _generar(modelo, prompt, timeout):
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


def correr(modelo, etiqueta, timeout=1800, fuente=None, limite=None):
    """Corre el banco completo contra un modelo. Escribe una fila por nota,
    en el momento en que la nota queda procesada."""
    _verificar(modelo)
    destino = os.path.join(RAIZ, "resultado_%s.csv" % etiqueta)

    if fuente is None:
        with open(BANCO, encoding="utf-8-sig") as f:
            notas = list(csv.DictReader(f))
    else:
        notas = cargar_muestra_antigua(fuente, limite=limite or 100)

    hechas = set()
    if os.path.exists(destino):
        _migrar(destino)
        with open(destino, encoding="utf-8-sig") as f:
            # solo se saltan las notas ya hechas EN ESTA MISMA version del prompt;
            # las de versiones anteriores se conservan y se vuelven a correr
            hechas = {fila["ID"] for fila in csv.DictReader(f)
                      if fila.get("salida_modelo") and fila.get("corrida") == VERSION}
        if hechas:
            print("Reanudando %s: ya habia %d notas hechas." % (VERSION, len(hechas)))
    else:
        with open(destino, "w", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=COLUMNAS).writeheader()

    print("Modelo : %s" % modelo)
    print("Prompt : %s" % VERSION)
    print("Salida : %s" % destino)
    print("Notas  : %d  (faltan %d)\n" % (len(notas), len(notas) - len(hechas)))

    total = 0.0
    for i, nota in enumerate(notas, start=1):
        if nota["ID"] in hechas:
            continue

        segundos, respuesta = _generar(modelo, construir(nota["HCTMOTCON"]), timeout)
        salida = _limpiar(respuesta.get("response", ""))
        total += segundos

        fila = {
            "corrida": VERSION,
            "fecha": time.strftime("%Y-%m-%d %H:%M"),
            "ID": nota["ID"], "estrato": nota["estrato"], "origen": nota["origen"],
            "n_chars": nota["n_chars"], "HCTMOTCON": nota["HCTMOTCON"],
            "salida_esperada": nota["salida_esperada"], "salida_modelo": salida,
            "modelo": modelo, "segundos": round(segundos, 1),
            "tok_entrada": respuesta.get("prompt_eval_count", ""),
            "tok_salida": respuesta.get("eval_count", ""),
            "veredicto_propietario": "",
        }

        # se abre, se escribe y se cierra en cada nota: nada queda en memoria
        with open(destino, "a", encoding="utf-8-sig", newline="") as f:
            escritor = csv.DictWriter(f, fieldnames=COLUMNAS)
            escritor.writerow(fila)
            f.flush()
            os.fsync(f.fileno())

        print("[%2d/%d] %-6s %5ss  %-28.28s | %s"
              % (i, len(notas), nota["ID"], round(segundos, 1),
                 nota["HCTMOTCON"].replace("\n", " ")[:28], salida[:70]))
        sys.stdout.flush()

    print("\nListo. %d notas, %.1f s en total (%.1f s por nota)."
          % (len(notas) - len(hechas), total,
             total / max(1, len(notas) - len(hechas))))
    print("Audita el resultado en: %s" % destino)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("uso: python -m NLP.correr_modelo <modelo-ollama> <etiqueta>")
        raise SystemExit(2)
    correr(sys.argv[1], sys.argv[2])
