# -*- coding: utf-8 -*-
"""
La compuerta. Si UNA sola linea del paquete no pasa, el paquete se borra.

    python -m NLP.nube --auditar

Corre sola al final de --exportar, con la identidad de cada paciente todavia en
memoria. Suelta, vuelve a pedir a la base las cinco columnas de identidad de los
OID del mapa (solo en memoria) y repite todo.

LO QUE REVISA, LINEA POR LINEA
    formato        JSON valido, EXACTAMENTE las claves id y prompt, id de 16 hex,
                   sin repetir, y que exista en el mapa local
    su nota        el texto enmascarado que dice el mapa esta dentro del prompt
    identidad      ninguna ficha de nombre o apellido de ESE paciente, ni su
                   documento, en ninguna parte del prompt. Las palabras de la
                   lista de bloqueo no se buscan (ver enmascarar.py): es la regla
                   que protege 'dolores musculares'
    patrones       ninguna secuencia de 5+ cifras, ninguna fecha completa, ningun
                   telefono con forma de telefono, ningun correo ni URL

LO QUE REVISA DEL PAQUETE ENTERO
    cobertura      las mismas notas en el paquete y en el mapa, ni una mas
    huella         el paquete no cambio desde que se armo (sha256 de lote.json)
    azar           ni el id ni la posicion de la linea correlacionan con el OID
                   ni con la fecha (Spearman; limite 4/raiz(n): una baraja
                   honesta lo pasa con probabilidad ~1 - 6e-5)
    integridad     en una muestra, el prompt es exactamente construir(nota
                   enmascarada): no lleva nada que no venga de la plantilla, del
                   glosario o de la nota ya tapada

Y MIDE, SIN BLOQUEAR, EL SOBRE-ENMASCARADO
    Cuantos terminos clinicos del catalogo (glosario.buscar_terminos_clinicos)
    tenia cada nota antes y despues de enmascarar. Tienen que ser casi iguales:
    si el enmascarado se come sintomas, el paquete es seguro pero inutil.

SOLO CONTEOS
    Nada de lo que imprime o guarda esta auditoria lleva texto de una nota, un
    nombre o un OID. auditoria.json son numeros.
"""

import json
import math
import random
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from NLP.nube import AUDITORIA, CARPETA, LOTE, MAPA, MARCAS, OPCIONES, PAQUETE
from NLP.nube import enmascarar as em

# Independientes de los de enmascarar.py a proposito: si un patron de alli tiene
# un error, no se repite aqui.
_CIFRAS = re.compile(r"\d{5,}")
_FECHA_NUM = re.compile(r"(?<!\d)(0?[1-9]|[12]\d|3[01])\s*([/.-])\s*(0?[1-9]|1[0-2])\s*\2\s*((19|20)?\d\d)(?!\d)")
_FECHA_ISO = re.compile(r"(?<!\d)(19|20)\d\d([/.-])(0?[1-9]|1[0-2])\2(0?[1-9]|[12]\d|3[01])(?!\d)")
_FECHA_TEXTO = re.compile(
    r"\b(0?[1-9]|[12]\d|3[01])\s*(de\s+|del\s+|/|-|\.)?\s*(enero|febrero|marzo|abril|mayo|"
    r"junio|julio|agosto|septiembre|setiembre|octubre|noviembre|diciembre)\b\s*(de|del)?\s*(19|20)\d\d\b")
_TELEFONO = re.compile(r"(?<!\d)\d{3}[\s.-]\d{3}[\s.-]?\d{4}(?!\d)")
_MILES = re.compile(r"(?<![\d.,])\d{1,3}(?:[.,]\d{3}){2,}(?!\d)")
_CORREO = re.compile(r"[a-z0-9._%+-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+", re.I)
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.I)
_ID = re.compile(r"^[0-9a-f]{16}$")

MUESTRA_INTEGRIDAD = 500
# Por encima de esta fraccion de terminos clinicos perdidos se avisa. No bloquea:
# es calidad, no privacidad.
ALERTA_PERDIDA = 0.01


def _plano(texto):
    return em._plano_1a1(str(texto or ""))


def _vocabulario_esqueleto(modulo):
    """
    Las palabras que el prompt puede traer sin que vengan de la nota: las de la
    plantilla, las del glosario y las de los diccionarios. Si el apellido del
    paciente es una de ellas (Caldas, en 'departamento: CALDAS'), buscarlo en el
    prompt entero daria un falso resto; se busca entonces solo dentro de la nota.
    """
    import inspect

    from NLP import glosario, rutas

    trozos = [modulo.construir(""), inspect.getsource(glosario)]
    for ruta in (rutas.SIGLAS, rutas.COLOQUIALISMOS, rutas.TERMINOLOGIA_CLINICA, rutas.LUGARES):
        try:
            trozos.append(Path(ruta).read_text(encoding="utf-8-sig"))
        except OSError:
            pass
    return frozenset(re.findall(r"[a-z0-9]+", _plano(" ".join(trozos))))


def _spearman(a, b):
    a, b = pd.Series(a, dtype=float), pd.Series(b, dtype=float)
    validos = a.notna() & b.notna()
    if validos.sum() < 20:
        return None
    ra, rb = a[validos].rank().to_numpy(), b[validos].rank().to_numpy()
    if ra.std() == 0 or rb.std() == 0:
        return None
    return float(np.corrcoef(ra, rb)[0, 1])


def _identidades_de_la_base(mapa):
    from NLP.nube import exportar
    por_oid = exportar.traer_identidades(exportar._engine(), mapa["OID"].tolist())
    return {id_: por_oid.get(int(oid), em.Identidad()) for id_, oid in zip(mapa["id"], mapa["OID"])}


def revisar_linea(linea, por_id, identidades, vocabulario, vistos):
    """Las banderas de UNA linea (lista vacia si esta limpia)."""
    try:
        registro = json.loads(linea)
    except json.JSONDecodeError:
        return ["linea_ilegible"], None
    banderas = []
    if not isinstance(registro, dict) or set(registro) != {"id", "prompt"}:
        banderas.append("claves_distintas_de_id_prompt")
    id_ = registro.get("id") if isinstance(registro, dict) else None
    prompt = registro.get("prompt") if isinstance(registro, dict) else None
    if not isinstance(id_, str) or not _ID.match(id_):
        banderas.append("id_invalido")
    elif id_ in vistos:
        banderas.append("id_repetido")
    if isinstance(id_, str):
        vistos.add(id_)
    if not isinstance(prompt, str) or not prompt.strip():
        banderas.append("prompt_vacio")
        return banderas, id_
    if id_ not in por_id:
        banderas.append("id_sin_mapa")
    else:
        nota = str(por_id[id_]).strip()
        if nota and nota not in prompt:
            banderas.append("prompt_sin_su_nota")
        identidad = identidades.get(id_)
        if identidad is None:
            banderas.append("identidad_sin_verificar")
        else:
            dentro = em.Identidad(fuertes=identidad.fuertes & vocabulario)
            if (em.restos_de_identidad(prompt, identidad, excluir=vocabulario)
                    or em.restos_de_identidad(nota, dentro)):
                banderas.append("resto_de_identidad")

    plano = _plano(prompt)
    for marca in MARCAS:
        plano = plano.replace(marca.lower(), " ")
    if _CIFRAS.search(plano):
        banderas.append("cifras_5_o_mas")
    if _FECHA_NUM.search(plano) or _FECHA_ISO.search(plano) or _FECHA_TEXTO.search(plano):
        banderas.append("fecha_completa")
    if _TELEFONO.search(plano) or _MILES.search(plano):
        banderas.append("telefono_o_documento")
    if _CORREO.search(plano):
        banderas.append("correo")
    if _URL.search(plano):
        banderas.append("url")
    return banderas, id_


def auditar(carpeta=CARPETA, identidades=None, borrar=True, informar=True,
            muestra_integridad=MUESTRA_INTEGRIDAD):
    """
    0 si el paquete pasa. 2 si falla: el paquete se borra. 3 si no se pudo
    verificar la identidad (sin base): no se certifica, pero no se borra, porque
    la exportacion ya lo audito con la identidad en memoria.
    """
    from NLP.nube import exportar

    carpeta = Path(carpeta)
    ruta_paquete, ruta_mapa = carpeta / PAQUETE, carpeta / MAPA
    if not ruta_paquete.exists() or not ruta_mapa.exists():
        print(f"No hay paquete que auditar en {carpeta}")
        return 1
    exportar.ampliar_cache_regex()
    mapa = pd.read_parquet(ruta_mapa)
    por_id = dict(zip(mapa["id"], mapa["texto_enmascarado"]))
    modulo = exportar.cargar_prompt(mapa["ruta_prompt"].iloc[0])

    sin_base = False
    if identidades is None:
        try:
            identidades = _identidades_de_la_base(mapa)
        except Exception as error:     # sin red, sin driver, sin permiso
            print(f"No se pudo leer la identidad de la base ({type(error).__name__}).")
            identidades, sin_base = {}, True

    vocabulario = _vocabulario_esqueleto(modulo)
    fallos, lineas, vistos, orden = Counter(), 0, set(), []
    with open(ruta_paquete, encoding="utf-8") as archivo:
        for linea in archivo:
            if not linea.strip():
                continue
            lineas += 1
            banderas, id_ = revisar_linea(linea, por_id, identidades, vocabulario, vistos)
            if sin_base:
                banderas = [b for b in banderas if b != "identidad_sin_verificar"]
            fallos.update(banderas)
            orden.append(id_)

    # --- el paquete entero ---
    en_paquete = set(i for i in orden if i)
    en_mapa = set(mapa["id"])
    if en_paquete - en_mapa:
        fallos["ids_que_no_estan_en_el_mapa"] = len(en_paquete - en_mapa)
    if en_mapa - en_paquete:
        fallos["notas_del_mapa_que_faltan"] = len(en_mapa - en_paquete)

    lote = carpeta / LOTE
    if lote.exists():
        if json.loads(lote.read_text(encoding="utf-8")).get("sha256_paquete") != exportar.huella(ruta_paquete):
            fallos["paquete_modificado_despues_de_armarlo"] = 1

    posicion = {id_: k for k, id_ in enumerate(orden) if id_}
    mapa = mapa.assign(posicion=mapa["id"].map(posicion),
                       id_num=mapa["id"].map(lambda i: int(i, 16) if _ID.match(str(i)) else np.nan))
    fechas = pd.to_datetime(mapa["fecha_triage"], errors="coerce")
    fecha_num = fechas.map(lambda f: f.value if pd.notna(f) else np.nan)
    n = len(mapa)
    limite = 4 / math.sqrt(n) if n else 1
    azar = {"id_vs_oid": _spearman(mapa["id_num"], mapa["OID"]),
            "posicion_vs_oid": _spearman(mapa["posicion"], mapa["OID"]),
            "posicion_vs_fecha": _spearman(mapa["posicion"], fecha_num)}
    for nombre, rho in azar.items():
        if rho is not None and abs(rho) > limite:
            fallos["correlacion_" + nombre] = 1

    # --- integridad: el prompt es exactamente construir(nota enmascarada) ---
    elegidos = set(random.Random().sample(sorted(en_paquete & en_mapa),
                                          min(muestra_integridad, len(en_paquete & en_mapa))))
    distintos = 0
    with open(ruta_paquete, encoding="utf-8") as archivo:
        for linea in archivo:
            try:
                registro = json.loads(linea)
            except json.JSONDecodeError:
                continue
            if registro.get("id") in elegidos and modulo.construir(por_id[registro["id"]]) != registro.get("prompt"):
                distintos += 1
    if distintos:
        fallos["prompt_distinto_de_construir"] = distintos

    # --- sobre-enmascarado (no bloquea) ---
    antes, despues = int(mapa["terminos_antes"].sum()), int(mapa["terminos_despues"].sum())
    perdida = (antes - despues) / antes if antes else 0.0
    tipos = {t: {"notas": int((mapa["n_" + t] > 0).sum()), "marcas": int(mapa["n_" + t].sum())}
             for t in em.TIPOS if "n_" + t in mapa}

    informe = {
        "lineas": lineas, "notas_en_mapa": n, "fallos": dict(fallos),
        "identidad_verificada": not sin_base,
        "azar": {k: (None if v is None else round(v, 4)) for k, v in azar.items()},
        "limite_correlacion": round(limite, 4),
        "integridad_revisadas": len(elegidos),
        "enmascarado": tipos,
        "terminos_clinicos": {"antes": antes, "despues": despues,
                              "notas_con_perdida": int((mapa["terminos_despues"] < mapa["terminos_antes"]).sum()),
                              "fraccion_perdida": round(perdida, 5)},
    }
    informe["certificado"] = not fallos and not sin_base
    (carpeta / AUDITORIA).write_text(json.dumps(informe, indent=2), encoding="utf-8")

    if informar:
        _imprimir(informe)
    if fallos and borrar:
        for nombre in (PAQUETE, OPCIONES):
            (carpeta / nombre).unlink(missing_ok=True)
        print(f"\nAUDITORIA FALLIDA: paquete BORRADO. Nada de {carpeta} debe salir de aqui.")
        return 2
    if sin_base:
        print("\nNO CERTIFICADO: falto verificar la identidad contra la base. "
              "No se borro; repite --auditar con acceso a la base.")
        return 3
    print("\nAUDITORIA SUPERADA. Lo unico que sale: paquete.jsonl, opciones.json "
          "y NLP/nube/correr_en_gpu.py.")
    return 0


def _imprimir(informe):
    n = informe["notas_en_mapa"] or 1
    print(f"\nAuditoria: {informe['lineas']:,} lineas, {informe['notas_en_mapa']:,} notas en el mapa")
    if informe["fallos"]:
        print("  FALLOS (lineas o comprobaciones):")
        for nombre, cuenta in sorted(informe["fallos"].items()):
            print(f"    {nombre:<40}{cuenta:8,}")
    else:
        print("  fallos: 0")
    print(f"  azar (limite {informe['limite_correlacion']}): " +
          ", ".join(f"{k} {v}" for k, v in informe["azar"].items()))
    print(f"  integridad: {informe['integridad_revisadas']:,} prompts reconstruidos")
    print("  enmascarado            notas con     %      marcas")
    for tipo, d in informe["enmascarado"].items():
        print(f"    {tipo:<20}{d['notas']:9,}{100 * d['notas'] / n:7.1f}%{d['marcas']:10,}")
    t = informe["terminos_clinicos"]
    aviso = "   <-- REVISAR: el enmascarado se come sintomas" if t["fraccion_perdida"] > ALERTA_PERDIDA else ""
    print(f"  terminos clinicos: antes {t['antes']:,}  despues {t['despues']:,}  "
          f"(notas con perdida {t['notas_con_perdida']:,}; {100 * t['fraccion_perdida']:.2f} %){aviso}")
