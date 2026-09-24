# -*- coding: utf-8 -*-
"""
Corre el paquete contra Ollama EN LA MAQUINA REMOTA. Solo biblioteca estandar.

Este archivo es lo UNICO del proyecto que se copia a la GPU, junto con
paquete.jsonl y opciones.json. No importa nada del repositorio a proposito: la
maquina de un tercero no recibe codigo, diccionarios ni nada que no sea el texto
ya enmascarado. Guia completa, con el porque: NLP/docs/NUBE.md.

========================================================================
USO EN LA MAQUINA REMOTA (Linux con GPU NVIDIA; RunPod, Vast.ai, Lambda...)
========================================================================

0. Desde el equipo local, copiar SOLO estos tres archivos (y nada mas):

       scp -P <puerto> NLP/nube/correr_en_gpu.py \\
           NLP/salidas/nube/paquete.jsonl NLP/salidas/nube/opciones.json \\
           <usuario>@<host>:~/trabajo/

   (paquete.jsonl pesa ~7 KB por nota: ~700 MB para 94.000. Si la subida es
   lenta: gzip -k paquete.jsonl y copiar paquete.jsonl.gz; este script lo lee
   igual con --paquete paquete.jsonl.gz.)

1. Instalar Ollama y dejarlo sirviendo con varias peticiones a la vez:

       curl -fsSL https://ollama.com/install.sh | sh
       sudo systemctl stop ollama 2>/dev/null     # el servicio no ve las variables
       export OLLAMA_NUM_PARALLEL=8               # peticiones simultaneas por modelo
       export OLLAMA_MAX_LOADED_MODELS=1
       export OLLAMA_KEEP_ALIVE=30m
       nohup ollama serve > ollama.log 2>&1 &
       ollama pull qwen3:8b                        # el modelo que dice opciones.json

   NO poner OLLAMA_DEBUG=1: en modo depuracion Ollama puede escribir los
   prompts en su registro, y el registro se queda en el disco de un tercero.

   Cada peticion paralela reserva su propio contexto (num_ctx de opciones.json):
   8 x 4096 tokens con qwen3:8b caben de sobra en 24 GB. Con menos memoria,
   bajar OLLAMA_NUM_PARALLEL.

2. Comprobar y medir ANTES de la corrida larga (piloto de 30 minutos):

       python3 correr_en_gpu.py --verificar
       python3 correr_en_gpu.py --hilos 8 --piloto 30

   Al terminar el piloto imprime notas por minuto y la proyeccion del total.
   Probar --hilos 4, 8, 16 (reiniciando ollama con el OLLAMA_NUM_PARALLEL
   correspondiente) y quedarse con el que mas notas por minuto de. Lo ya
   procesado en el piloto NO se repite: la corrida larga lo salta.

3. La corrida completa, dentro de tmux o screen para que sobreviva a una
   desconexion:

       tmux new -s triage
       python3 correr_en_gpu.py --hilos 8
       (Ctrl+B y luego D para salir sin cortarla; tmux attach -t triage para volver)

   Es REANUDABLE: si se corta, se relanza igual y salta los id que ya estan
   en respuestas.jsonl. Los que fallan van a errores.jsonl (solo id y tipo de
   error) y se reintentan en la siguiente vuelta.

4. Descargar las respuestas al equipo local:

       scp -P <puerto> <usuario>@<host>:~/trabajo/respuestas.jsonl NLP/salidas/nube/

   y en local:  python -m NLP.nube --importar NLP/salidas/nube/respuestas.jsonl

5. BORRAR Y DESTRUIR. No es opcional y va en este orden:

       shred -u paquete.jsonl paquete.jsonl.gz respuestas.jsonl errores.jsonl opciones.json 2>/dev/null
       rm -f ollama.log ~/.bash_history

   y DESTRUIR la instancia desde el panel del proveedor (Terminate / Destroy,
   no Stop): una maquina detenida conserva el disco -con los datos- y sigue
   cobrando por el almacenamiento.

========================================================================
"""

import argparse
import gzip
import json
import os
import queue
import sys
import threading
import time
import urllib.error
import urllib.request

HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
if not HOST.startswith("http"):
    HOST = "http://" + HOST


# ==========================================================
# ARCHIVOS
# ==========================================================

def _abrir(ruta):
    if str(ruta).endswith(".gz"):
        return gzip.open(ruta, "rt", encoding="utf-8")
    return open(ruta, encoding="utf-8")


def ids_hechos(ruta_respuestas):
    """Los id que ya tienen respuesta. Tolera una ultima linea cortada."""
    hechos = set()
    if not os.path.exists(ruta_respuestas):
        return hechos
    with open(ruta_respuestas, encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if isinstance(registro, dict) and registro.get("id"):
                hechos.add(registro["id"])
    return hechos


def _cerrar_linea_cortada(ruta):
    """Si una corrida anterior murio a mitad de una linea, la siguiente
    respuesta se pegaria a ese trozo y se perderian las dos."""
    if os.path.exists(ruta) and os.path.getsize(ruta) > 0:
        with open(ruta, "rb") as archivo:
            archivo.seek(-1, os.SEEK_END)
            ultimo = archivo.read(1)
        if ultimo != b"\n":
            with open(ruta, "ab") as archivo:
                archivo.write(b"\n")


def contar_lineas(ruta):
    with _abrir(ruta) as archivo:
        return sum(1 for linea in archivo if linea.strip())


def leer_paquete(ruta, saltar):
    """Genera (id, prompt) sin cargar el archivo entero en memoria."""
    with _abrir(ruta) as archivo:
        for linea in archivo:
            if not linea.strip():
                continue
            registro = json.loads(linea)
            if registro["id"] not in saltar:
                yield registro["id"], registro["prompt"]


# ==========================================================
# OLLAMA
# ==========================================================

def modelos_instalados(host=HOST, timeout=30):
    with urllib.request.urlopen(host + "/api/tags", timeout=timeout) as respuesta:
        return [m["name"] for m in json.loads(respuesta.read()).get("models", [])]


class Cliente:
    """Una llamada a /api/generate. Si el modelo no admite 'think', se quita y
    no se vuelve a mandar (mismo criterio que NLP/modelo.py en local)."""

    def __init__(self, opciones, host=HOST, timeout=600):
        self.modelo = opciones["modelo"]
        self.options = opciones.get("options", {})
        self.think = opciones.get("think", False)
        self.enviar_think = "think" in opciones
        self.host = host
        self.timeout = timeout

    def generar(self, prompt):
        cuerpo = {"model": self.modelo, "prompt": prompt, "stream": False,
                  "options": self.options, "keep_alive": "30m"}
        if self.enviar_think:
            cuerpo["think"] = self.think
        peticion = urllib.request.Request(
            self.host + "/api/generate", json.dumps(cuerpo).encode("utf-8"),
            {"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(peticion, timeout=self.timeout) as respuesta:
                return json.loads(respuesta.read())
        except urllib.error.HTTPError as error:
            if error.code == 400 and self.enviar_think:
                self.enviar_think = False
                return self.generar(prompt)
            raise


# ==========================================================
# LA CORRIDA
# ==========================================================

def _formato_tiempo(segundos):
    segundos = int(max(segundos, 0))
    horas, resto = divmod(segundos, 3600)
    return f"{horas}h{resto // 60:02d}m" if horas else f"{resto // 60}m{resto % 60:02d}s"


def correr(paquete, opciones, salida, hilos=4, host=HOST, limite=None, piloto=None,
           timeout=600, reintentos=3, espera=2.0, errores=None, informar_cada=15.0,
           imprimir=print):
    """
    Devuelve un resumen: total, ya_hechas, nuevas, fallidas, segundos, notas_por_minuto.

    piloto   minutos: deja de mandar notas nuevas al cumplirse, espera las que
             estan en vuelo e imprime la proyeccion.
    limite   como mucho estas notas nuevas en esta vuelta.
    """
    if isinstance(opciones, str):
        with open(opciones, encoding="utf-8") as archivo:
            opciones = json.load(archivo)
    errores = errores or os.path.join(os.path.dirname(os.path.abspath(salida)), "errores.jsonl")
    cliente = Cliente(opciones, host, timeout)

    total = contar_lineas(paquete)
    hechos = ids_hechos(salida)
    _cerrar_linea_cortada(salida)
    pendientes = max(total - len(hechos), 0)
    imprimir(f"Paquete: {total:,} notas | ya respondidas: {len(hechos):,} | "
             f"pendientes: {pendientes:,} | modelo {cliente.modelo} | hilos {hilos}")

    cola = queue.Queue(maxsize=hilos * 4)
    candado = threading.Lock()
    estado = {"nuevas": 0, "fallidas": 0, "segundos_modelo": 0.0}
    inicio = time.time()
    fin_piloto = inicio + piloto * 60 if piloto else None
    parar = threading.Event()

    archivo_salida = open(salida, "a", encoding="utf-8")
    archivo_errores = open(errores, "a", encoding="utf-8")

    def trabajar():
        while True:
            tarea = cola.get()
            if tarea is None:
                cola.task_done()
                return
            id_, prompt = tarea
            ultimo_error = None
            for intento in range(reintentos):
                try:
                    t0 = time.time()
                    respuesta = cliente.generar(prompt)
                    segundos = time.time() - t0
                    linea = json.dumps({"id": id_, "respuesta": respuesta.get("response", ""),
                                        "segundos": round(segundos, 2),
                                        "tokens_prompt": respuesta.get("prompt_eval_count")},
                                       ensure_ascii=False)
                    with candado:
                        archivo_salida.write(linea + "\n")
                        archivo_salida.flush()
                        estado["nuevas"] += 1
                        estado["segundos_modelo"] += segundos
                    ultimo_error = None
                    break
                except Exception as error:      # red, 5xx, tiempo agotado
                    ultimo_error = error
                    time.sleep(espera * (2 ** intento))
            if ultimo_error is not None:
                # solo el id y el tipo de error: nunca el prompt
                with candado:
                    archivo_errores.write(json.dumps({"id": id_, "error": type(ultimo_error).__name__}) + "\n")
                    archivo_errores.flush()
                    estado["fallidas"] += 1
            cola.task_done()

    trabajadores = [threading.Thread(target=trabajar, daemon=True) for _ in range(hilos)]
    for hilo in trabajadores:
        hilo.start()

    def informar(final=False):
        transcurrido = max(time.time() - inicio, 1e-9)
        hechas = estado["nuevas"]
        por_minuto = 60 * hechas / transcurrido
        restantes = pendientes - hechas - estado["fallidas"]
        eta = restantes / (por_minuto / 60) if por_minuto else float("inf")
        latencia = estado["segundos_modelo"] / hechas if hechas else 0
        imprimir(("\n" if final else "\r") +
                 f"  {len(hechos) + hechas:,}/{total:,}  nuevas {hechas:,}  fallidas {estado['fallidas']:,}  "
                 f"{por_minuto:6.1f} notas/min  {latencia:5.1f} s/nota  "
                 f"faltan {_formato_tiempo(eta) if eta != float('inf') else '?'}"
                 + ("" if final else "   "), **({} if final else {"end": "", "flush": True}))

    ultimo_informe = time.time()
    mandadas = 0
    try:
        for id_, prompt in leer_paquete(paquete, hechos):
            if limite is not None and mandadas >= limite:
                break
            if fin_piloto and time.time() >= fin_piloto:
                break
            while True:
                try:
                    cola.put((id_, prompt), timeout=1)
                    break
                except queue.Full:
                    if time.time() - ultimo_informe >= informar_cada:
                        informar()
                        ultimo_informe = time.time()
            mandadas += 1
            if time.time() - ultimo_informe >= informar_cada:
                informar()
                ultimo_informe = time.time()
    except KeyboardInterrupt:
        imprimir("\nInterrumpido: se terminan las notas en vuelo; lo escrito se conserva.")
        parar.set()
    finally:
        for _ in trabajadores:
            cola.put(None)
        for hilo in trabajadores:
            hilo.join()
        with candado:
            archivo_salida.flush()
            os.fsync(archivo_salida.fileno())
            archivo_salida.close()
            archivo_errores.close()

    informar(final=True)
    transcurrido = time.time() - inicio
    por_minuto = 60 * estado["nuevas"] / transcurrido if transcurrido else 0
    resumen = {"total": total, "ya_hechas": len(hechos), "nuevas": estado["nuevas"],
               "fallidas": estado["fallidas"], "segundos": round(transcurrido, 1),
               "notas_por_minuto": round(por_minuto, 2)}
    if piloto or limite:
        faltan = total - len(hechos) - estado["nuevas"]
        if por_minuto:
            imprimir(f"PROYECCION: {faltan:,} notas pendientes a {por_minuto:.1f} notas/min "
                     f"= {_formato_tiempo(60 * faltan / por_minuto)} con {hilos} hilos.")
    if estado["fallidas"]:
        imprimir(f"{estado['fallidas']:,} notas fallaron (ver {errores}); relanzar para reintentarlas.")
    return resumen


# ==========================================================
# MAIN
# ==========================================================

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Corre paquete.jsonl contra Ollama local. Ver la cabecera del archivo.")
    parser.add_argument("--paquete", default="paquete.jsonl")
    parser.add_argument("--opciones", default="opciones.json")
    parser.add_argument("--salida", default="respuestas.jsonl")
    parser.add_argument("--hilos", type=int, default=4,
                        help="peticiones simultaneas; igual o algo mayor que OLLAMA_NUM_PARALLEL")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--piloto", type=float, default=None, metavar="MINUTOS",
                        help="corre estos minutos, mide y proyecta el total")
    parser.add_argument("--limite", type=int, default=None, help="como mucho N notas nuevas")
    parser.add_argument("--timeout", type=int, default=600, help="segundos por nota")
    parser.add_argument("--verificar", action="store_true",
                        help="comprueba Ollama, el modelo y los archivos, y sale")
    args = parser.parse_args(argv)

    for ruta in (args.paquete, args.opciones):
        if not os.path.exists(ruta):
            print(f"No existe {ruta}")
            return 1
    with open(args.opciones, encoding="utf-8") as archivo:
        opciones = json.load(archivo)

    try:
        instalados = modelos_instalados(args.host)
    except Exception as error:
        print(f"Ollama no responde en {args.host} ({type(error).__name__}).\n"
              f"Arrancalo con:  nohup ollama serve > ollama.log 2>&1 &")
        return 1
    modelo = opciones["modelo"]
    if modelo not in instalados and modelo + ":latest" not in instalados:
        print(f"El modelo {modelo} no esta descargado. Instalados: {', '.join(instalados) or 'ninguno'}\n"
              f"Descargalo con:  ollama pull {modelo}")
        return 1
    if args.verificar:
        total = contar_lineas(args.paquete)
        hechos = len(ids_hechos(args.salida))
        print(f"Ollama responde en {args.host} y tiene {modelo}.\n"
              f"Paquete: {total:,} notas; ya respondidas: {hechos:,}.\n"
              f"OLLAMA_NUM_PARALLEL del servidor: mira 'ollama.log' (linea 'OLLAMA_NUM_PARALLEL').")
        return 0

    resumen = correr(args.paquete, opciones, args.salida, hilos=args.hilos, host=args.host,
                     limite=args.limite, piloto=args.piloto, timeout=args.timeout)
    print(json.dumps(resumen))
    return 0


if __name__ == "__main__":
    sys.exit(main())
