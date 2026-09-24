# -*- coding: utf-8 -*-
"""
Lo que vuelve de la GPU -> resultados.parquet, emparejando SOLO en local.

    python -m NLP.nube --importar NLP/salidas/nube/respuestas.jsonl

    respuestas.jsonl   {"id","respuesta","segundos"} por linea, de correr_en_gpu.py
    mapa_local.parquet id -> OID, fecha, nota original (nunca salio de aqui)
          |
          v
    NLP.modelo.limpiar(respuesta)            el mismo limpiador de la corrida local
    quitar marcas [NOMBRE] [FECHA]...        si el modelo copio alguna
    posprocesar(nota ORIGINAL, salida)       los filtros de fidelidad del prompt,
                                             contra la nota sin enmascarar
          |
          v
    resultados.parquet  OID, fecha_triage, frase_original, frase_procesada,
                        version_prompt, modelo

POR QUE posprocesar RECIBE LA NOTA ORIGINAL Y NO LA ENMASCARADA
    Los filtros de NLP/fidelidad.py quitan de la salida el lado o la parte del
    cuerpo que la nota no dice. Tienen que mirar lo que la nota decia de verdad:
    la enmascarada tiene [FECHA] donde habia '25/12/2024' y [LUGAR] donde habia
    un barrio, y nada clinico menos. Da igual en la practica, pero la referencia
    correcta es la original y esta aqui, en el mapa.

NO ESCRIBE EN salidas/triage.duckdb
    La fusion con nota_triage es un paso aparte y explicito: fusionar_en_base().
    Mientras NLP.procesar corra, la base esta tomada; y antes de mezclar filas
    de la nube con filas locales hay que decidir si nota_triage guarda version y
    modelo por fila (pendiente en docs/HANDOFF.md).
"""

import json
import re
from pathlib import Path

import pandas as pd

from NLP import fidelidad
from NLP.nube import CARPETA, MAPA, MARCAS, RESULTADOS, REVISAR, SEGUNDA

# 'pasada' tiene los mismos valores que NLP/cadena.py: primera, segunda, revisar,
# y ademas pendiente_segunda (descarte con evidencia clinica que espera su
# segunda pasada; NO se fusiona con la base hasta tenerla).
COLUMNAS = ["OID", "fecha_triage", "frase_original", "frase_procesada", "version_prompt", "modelo",
            "pasada"]

_MARCAS = re.compile("|".join(re.escape(m) for m in MARCAS), re.I)


def leer_respuestas(ruta):
    """{id: respuesta}, y cuantas lineas no se pudieron leer. Si un id se repite
    (una corrida relanzada), gana la ultima."""
    respuestas, malas = {}, 0
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            if not linea.strip():
                continue
            try:
                registro = json.loads(linea)
                respuestas[str(registro["id"])] = str(registro.get("respuesta") or "")
            except (json.JSONDecodeError, KeyError, TypeError):
                malas += 1
    return respuestas, malas


def quitar_marcas(salida):
    """Devuelve (salida_sin_marcas, habia_marcas)."""
    limpia, cuantas = _MARCAS.subn(" ", salida or "")
    limpia = re.sub(r"\s{2,}", " ", limpia)
    limpia = re.sub(r"\s+([,.;:])", r"\1", limpia).strip(" ,.;:-")
    return limpia, cuantas > 0


def _estado_pasada(original, salida, numero):
    """La misma logica que NLP/cadena.py, repartida en dos viajes a la nube.

    Primera pasada: un descarte con evidencia clinica queda 'pendiente_segunda'.
    Segunda pasada: si sigue descartada o la respuesta inventa, queda 'revisar'
    (y la salida se deja en 'sin motivo clinico': mejor un descarte marcado que un
    motivo inventado sin marcar)."""
    necesita = fidelidad.necesita_segunda_pasada(original, salida)
    if numero == 1:
        return "pendiente_segunda" if necesita else "primera"
    if necesita or not salida or fidelidad.es_fallo(fidelidad.revisar(original, salida)):
        return "revisar"
    return "segunda"


def importar(ruta_respuestas, carpeta=CARPETA, ruta_mapa=None, informar=True):
    from NLP import modelo as motor
    from NLP.nube import exportar

    carpeta = Path(carpeta)
    ruta_mapa = Path(ruta_mapa) if ruta_mapa else carpeta / MAPA
    if not ruta_mapa.exists():
        print(f"No existe {ruta_mapa}: sin el mapa no hay forma de saber de que nota es "
              f"cada respuesta. Si se armo otro paquete despues, el mapa anterior esta "
              f"apartado como mapa_local_<fecha>.parquet: pasalo con --mapa.")
        return 1
    exportar.ampliar_cache_regex()
    mapa = pd.read_parquet(ruta_mapa).set_index("id")
    respuestas, malas = leer_respuestas(ruta_respuestas)

    rutas_prompt = mapa["ruta_prompt"].unique()
    modulos = {r: exportar.cargar_prompt(r) for r in rutas_prompt}

    filas, sin_mapa, vacias, con_marcas = [], 0, 0, 0
    for id_, respuesta in respuestas.items():
        if id_ not in mapa.index:
            sin_mapa += 1
            continue
        nota = mapa.loc[id_]
        posprocesar = getattr(modulos[nota["ruta_prompt"]], "posprocesar", lambda o, s: s)
        salida, marcas = quitar_marcas(motor.limpiar(respuesta))
        con_marcas += marcas
        original = str(nota["frase_original"])
        salida = posprocesar(original, salida) if salida else salida
        vacias += not salida
        pasada = _estado_pasada(original, salida, int(nota.get("pasada", 1) or 1))
        if pasada == "revisar":
            salida = fidelidad.SIN_MOTIVO
        filas.append({"OID": int(nota["OID"]), "fecha_triage": nota["fecha_triage"],
                      "frase_original": original, "frase_procesada": salida or None,
                      "version_prompt": nota["version_prompt"], "modelo": nota["modelo"],
                      "pasada": pasada})

    nuevos = pd.DataFrame(filas, columns=COLUMNAS)
    destino = carpeta / RESULTADOS
    anteriores = 0
    if destino.exists():
        previos = pd.read_parquet(destino)
        anteriores = len(previos)
        # gana lo nuevo: si una nota se reprocesa, la version vieja sobra
        nuevos = pd.concat([previos[~previos["OID"].isin(nuevos["OID"])], nuevos], ignore_index=True)
    nuevos = nuevos.sort_values("OID", ignore_index=True)
    nuevos.to_parquet(destino, index=False)

    # Los dos archivos de la red de seguridad. Solo OIDs, y NUNCA salen del equipo.
    pasadas = nuevos.get("pasada", pd.Series(dtype=str)).fillna("primera")
    pendientes = nuevos.loc[pasadas == "pendiente_segunda", "OID"].astype(int).tolist()
    a_revisar = nuevos.loc[pasadas == "revisar", "OID"].astype(int).tolist()
    (carpeta / SEGUNDA).write_text("\n".join(map(str, pendientes)), encoding="utf-8")
    (carpeta / REVISAR).write_text("\n".join(map(str, a_revisar)), encoding="utf-8")

    faltan = len(set(mapa.index) - set(respuestas))
    resumen = {"respuestas": len(respuestas), "lineas_ilegibles": malas,
               "emparejadas": len(filas), "sin_mapa": sin_mapa, "vacias": vacias,
               "con_marcas_quitadas": con_marcas, "faltan_del_paquete": faltan,
               "sin_motivo_clinico": int((nuevos["frase_procesada"].fillna("").str.strip().str.lower()
                                          == "sin motivo clinico").sum()),
               "resultados_antes": anteriores, "resultados_ahora": len(nuevos)}
    if informar:
        print(f"Respuestas leidas: {resumen['respuestas']:,}  (ilegibles {malas:,})")
        print(f"  emparejadas con su OID    {resumen['emparejadas']:,}")
        print(f"  sin entrada en el mapa    {sin_mapa:,}" + ("   <-- mapa equivocado?" if sin_mapa else ""))
        print(f"  vacias tras limpiar       {vacias:,}")
        print(f"  con marcas quitadas       {con_marcas:,}  (el modelo copio [NOMBRE], [FECHA]...)")
        print(f"  notas del paquete sin respuesta todavia: {faltan:,}")
        print(f"{destino}: {anteriores:,} -> {len(nuevos):,} filas")
        print(f"  descartes con evidencia clinica, esperan segunda pasada: {len(pendientes):,}"
              + (f"\n     -> python -m NLP.nube --exportar --segunda-pasada --forzar" if pendientes else ""))
        print(f"  descartados dos veces, para revision humana ({REVISAR}): {len(a_revisar):,}")
    return resumen


# ==========================================================
# LA FUSION CON LA BASE: PREPARADA, NO SE EJECUTA SOLA
# ==========================================================

def fusionar_en_base(ruta_resultados=None):
    """
    Mete resultados.parquet en nota_triage de salidas/triage.duckdb.

    NO la llama ningun otro paso. Antes de ejecutarla:
      1. que NLP.procesar no este corriendo (DuckDB admite un solo escritor);
      2. decidir si nota_triage gana las columnas version_prompt y modelo. Hoy
         no las tiene, y sin ellas una fila de la nube y una local son
         indistinguibles (docs/HANDOFF.md, 'Antes de contratar GPU').

    Usa el mismo Escritor que la corrida local, con ON CONFLICT DO UPDATE: si
    una nota ya estaba, gana la de la nube.
    """
    from NLP.nucleo import almacen

    ruta = Path(ruta_resultados) if ruta_resultados else CARPETA / RESULTADOS
    tabla = pd.read_parquet(ruta)
    tabla = tabla[tabla["frase_procesada"].notna()]
    # Un descarte que espera su segunda pasada NO entra a la base: seria un
    # paciente fuera de la cuenta que todavia puede recuperarse.
    if "pasada" in tabla.columns:
        esperando = (tabla["pasada"] == "pendiente_segunda").sum()
        if esperando:
            print(f"{esperando:,} notas esperan su segunda pasada y NO se fusionan todavia")
        tabla = tabla[tabla["pasada"] != "pendiente_segunda"]
    with almacen.Escritor(bloque=1000) as escritor:
        for fila in tabla.to_dict("records"):
            escritor.agregar({"OID": int(fila["OID"]),
                              "fecha_triage": fila["fecha_triage"],
                              "frase_original": fila["frase_original"],
                              "frase_procesada": fila["frase_procesada"]})
    print(f"{escritor.escritas:,} notas escritas en nota_triage")
    return escritor.escritas
